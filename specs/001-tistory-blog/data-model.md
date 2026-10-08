# 데이터 모델 (Data Model): 티스토리형 블로그 (지원)

> **이 문서는?** 지원 서비스의 테이블·컬럼·제약과 글 가시성 판단 순서다. 기능 명세의 핵심 엔티티를 실제 저장 구조로 옮긴 것이다. 전체 문서 안내는 [README](../../README.md)에 있다.

원본 ERD 탭은 예전 ID 기준이라, 이 문서는 원본 본문(4~6장)과 기능 명세 핵심 개체에서 다시 뽑았다. 지금 기능 코드 기준이다([지원이 확인할 것](./review.md) 16). 2026-10-08에 Crowfoot ERD(문서 버전 74)와 맞췄고, 2026-10-09 `post.content_text`를 더했다(버전 79). 컬럼 타입·인덱스·DDL 전체는 [ERD](./erd/README.md)와 [schema.sql](./erd/schema.sql)에 있고, 둘이 다르면 Crowfoot ERD가 맞다.

공통 규칙(아래 표에서는 생략):

- 모든 테이블에 `id`(PK, bigint, 자동 증가). 연결 테이블 `post_tag`만 (post_id, tag_id) 복합 키. 논리명은 `<테이블 논리명> ID`(예: 회원 ID), 그 키를 그대로 가리키는 외래 키도 같은 이름(member_id = 회원 ID). 역할이 있는 외래 키는 역할 이름(받는 회원, 차단된 회원 ID 등).
- `created_at`은 정렬·기간 집계·화면 표시에 쓰는 테이블에만 둔다. `tag`, `post_tag`, `category`, `blog_visit`, `blog_banned_word`에는 없다. 고칠 수 있는 테이블에는 `updated_at`.
- 열거값은 VARCHAR + CHECK(JPA `EnumType.STRING`). 화면 안내 문구는 DB가 아니라 Java enum 필드에 둔다.
- 참/거짓 컬럼은 `is_` 접두사(`is_primary`, `is_restricted`, `is_blinded` 등). Java 필드는 접두사 없이(`restricted`) 두고 `@Column(name = "is_restricted")`로 잇는다.
- 제재 사유는 대상 테이블에 두지 않고 `moderation_log`에만 남긴다. 대상의 사유는 그 대상의 최신 제재 행에서 읽는다.

## 회원·인증

**member**
| 컬럼 | 타입 | 규칙 |
| --- | --- | --- |
| email | varchar, NULL | UNIQUE. 이메일 가입 회원만 값이 있고 모두 인증된 회원 |
| password_hash | varchar, NULL | bcrypt |
| nickname | varchar(20) | UNIQUE |
| profile_image_id | FK image, NULL | |
| role | enum USER, ADMIN | 가입은 항상 USER. ADMIN은 data.sql로만 |
| status | enum ACTIVE, SUSPENDED, WITHDRAWN | 모든 로그인 경로에서 먼저 확인 |
| suspended_until | datetime, NULL | NULL + SUSPENDED = 영구. 정지 사유는 `moderation_log`의 최신 SUSPEND 행 |
| withdrawn_at | datetime, NULL | |

**social_account**: member_id, provider(KAKAO, GOOGLE), provider_user_id. UNIQUE(provider, provider_user_id), UNIQUE(member_id, provider).

**email_verification** (OWN-01): email, code, expires_at, verified_at. 가입 전 단계라 회원과 관계가 없고 이메일 값으로 찾는다. 인덱스 (email, created_at DESC).

**password_reset_token** (OWN-02): member_id, token_hash(링크 토큰의 SHA-256, UNIQUE, 원문은 저장하지 않음), expires_at(30분), used_at(한 번 쓰면 기록).

## 블로그

**blog**
| 컬럼 | 타입 | 규칙 |
| --- | --- | --- |
| member_id | FK member | 주인 1명 |
| address | varchar | UNIQUE, 불변. 삭제돼도 행이 남아 영구 예약 |
| name | varchar(50) | |
| description | varchar, NULL | |
| profile_image_id | FK image, NULL | |
| is_primary | boolean | 회원당 하나. 처음 만든 블로그. 계산 컬럼 `primary_owner_id`(대표이고 삭제 안 됐을 때만 member_id) + UNIQUE로 DB에서도 보장 |
| moved_to_blog_id | FK blog, NULL | 이사 대상. 연쇄 이사 시 최종 대상으로 갱신 |
| is_restricted | boolean | ADMIN-05. 사유는 `moderation_log`의 최신 RESTRICT_BLOG 행 |
| skin | varchar | BLOG-05 (P2) |
| list_layout | enum LIST, THUMBNAIL | BLOG-05 메인 글 목록 형태 |
| accent_color | enum BLUE, GREEN, ORANGE, PINK, PURPLE, GRAY | BLOG-05 스킨 포인트 색. 기본 BLUE |
| total_visitor_count | bigint | MNG-03 누적 방문자. 매일 새벽 전날 방문자 수를 더함(오늘 방문자는 미포함) |
| deleted_at | datetime, NULL | 소프트 삭제. 활성 = deleted_at IS NULL |

**blog_sidebar_module** (BLOG-04, BLOG-05): 블로그 사이드바의 모듈 순서와 표시 여부.
| 컬럼 | 타입 | 규칙 |
| --- | --- | --- |
| blog_id | FK blog | |
| module_type | enum PROFILE, CATEGORY, TAG, RECENT_POST, RECENT_COMMENT, VISITOR, POPULAR_POST, SUBSCRIBE | UNIQUE(blog_id, module_type) |
| sort_order | int | 위에서부터 순서 |
| is_visible | boolean | PROFILE은 항상 1 (CHECK) |
| updated_at | datetime | |

블로그를 만들 때 8개 행을 같은 트랜잭션에서 넣는다. PROFILE, CATEGORY, TAG, RECENT_POST, RECENT_COMMENT 순으로 보이고, VISITOR·POPULAR_POST·SUBSCRIBE는 숨김으로 뒤에 둔다. 모듈별 개수는 코드 상수(최근 글·댓글·인기 글 5개)다. 새 모듈은 이미 있는 데이터를 읽는다: VISITOR는 오늘 `blog_visit` 수, 어제 `blog_daily_stat`, 누적 `blog.total_visitor_count`. POPULAR_POST는 볼 수 있는 글 중 `post.view_count` 상위 5개. SUBSCRIBE는 구독 버튼과 구독자 수(`subscription`).

## 글

**post**
| 컬럼 | 타입 | 규칙 |
| --- | --- | --- |
| id | bigint | 전역 번호 = 글 주소 `{address}.blog.com/{id}` |
| blog_id | FK blog | 이사로 바뀔 수 있음. 옛 주소는 서버가 301 |
| category_id | FK category, NULL | NULL = 미분류 |
| title | varchar(200) | |
| content_html | mediumtext | 서버 정화 후 저장 |
| content_text | mediumtext | 본문에서 HTML 태그를 뺀 글자(jsoup). 블로그 안 검색(SRCH-01)이 제목·태그 이름과 함께 이 칸을 본다. 2026-10-09 지원 결정으로 추가(Flyway V3) |
| summary | varchar | jsoup으로 태그 제거한 요약 |
| thumbnail_image_id | FK image, NULL | 미지정 시 첫 이미지 |
| status | enum DRAFT, PUBLISHED, SCHEDULED | |
| visibility | enum PUBLIC, PRIVATE, SUBSCRIBERS | 기본 PUBLIC |
| topic | enum, NULL | 10개 고정, NULL = 주제 없음 |
| published_at | datetime, NULL | 처음 발행 시각. 정렬 기준. 수정해도 불변 |
| scheduled_at | datetime, NULL | POST-13 |
| view_count | bigint | 표시용 누적 |
| like_count, comment_count | int | 비정규화. 새로고침 시 실제 값과 같아야 함(트랜잭션 안에서 갱신) |
| is_comment_allowed | boolean | CMT-07 |
| is_blinded | boolean | ADMIN-03. 사유는 `moderation_log`의 최신 BLIND 행 |
| deleted_at | datetime, NULL | 소프트 삭제(Q3). 삭제하면 그 글의 댓글·공감·알림도 같은 트랜잭션에서 소프트 삭제 또는 제거 |

인덱스: (blog_id, status, visibility, published_at DESC, id DESC), (status, visibility, published_at DESC, id DESC) — 홈 커서. (topic, status, visibility, published_at DESC) — 주제별 글. (status, scheduled_at) — 예약 발행.

**view_log**: post_id, viewer_key(회원 id 또는 익명 식별자), viewed_at. 같은 viewer_key가 5분 안에 다시 열면 기록하지 않는다(Q2). 최근 1시간 인기 점수와 최근 7일 블로그 점수 집계에 사용.

**인기 점수** (HOME-02, HOME-03): 최근 1시간 안의 `view_log` 수×1 + `post_like` 수(created_at 기준)×3 + 삭제·숨김 안 된 `comment` 수×5. 5분마다 계산해 Redis에 상위 100개 스냅숏(순위, 점수, 계산 시각)으로 둔다. 홈은 상위 10개, 랭킹 전체보기(HOME-05)는 같은 스냅숏을 이어서 본다. 가중치는 설정값으로 둔다.

**블로그 점수** (HOME-04, SUB-06, HOME-05): 최근 7일 동안 그 블로그의 볼 수 있는 글이 받은 `view_log` 수×1 + `post_like` 수×3 + `comment` 수×5 + 그 블로그의 새 `subscription` 수×10. 공개 글이 없는 블로그, 삭제·이용 제한 블로그, 주인이 정지·탈퇴한 블로그는 뺀다. 1시간마다 계산해 Redis에 상위 100개 스냅숏으로 둔다. 추천 블로그(SUB-06)는 이 스냅숏에서 자기 블로그와 구독 중인 블로그를 뺀 5개. 기간·가중치는 설정값.

**view_log 보관**: 블로그 점수가 7일치를 쓰므로 7일보다 오래된 행은 매일 지운다.

**image**: path(`/uploads/{uuid}.{ext}`), thumbnail_path(`/uploads/t_{uuid}.jpg` 또는 `.png`, 400px), original_name, content_type(jpg/png/gif/webp), size(CHECK ≤ 10MB), uploader_id. path·thumbnail_path에는 화면이 그대로 쓰는 주소를 저장하고, 실제 파일은 설정값 `app.upload.dir` 폴더에 같은 파일 이름으로 둔다(R-15). `uploader_id`는 회원 ↔ 이미지 순환 참조를 피하려고 외래 키 없이 두고(인덱스만), 서버가 로그인 회원으로 채운다.

**category**: blog_id, parent_id(NULL 또는 1단계 상위), name(30), sort_order, is_private(P2). 계산 컬럼 `parent_key = IFNULL(parent_id, 0)`과 UNIQUE(blog_id, parent_key, name). MySQL UNIQUE는 NULL끼리 중복을 허용해서 (blog_id, parent_id, name)만으로는 최상위 이름 중복을 못 막기 때문이다. '전체 글'·'미분류'는 행이 아니라 가상 항목.

**tag**: blog_id, name. UNIQUE(blog_id, name). **post_tag**: post_id, tag_id. PK(post_id, tag_id). 글당 최대 10개는 서비스에서 검사.

## 소통

**comment**: post_id, member_id, parent_id(NULL 또는 1단계), content(1,000), is_secret, is_blinded(사유는 `moderation_log`), deleted_at(소프트 삭제, 답글 있으면 '삭제된 댓글입니다' 표시).

**guestbook**: blog_id, member_id, parent_id, content(1,000), is_secret, deleted_at. 규칙은 댓글과 같음.

**post_like**: member_id, post_id. UNIQUE(member_id, post_id) — 연타 방지 겸용.

**subscription**: member_id, blog_id. UNIQUE(member_id, blog_id). 자기 블로그 구독과, 그 블로그에서 차단된 회원의 구독(MNG-04)은 서비스에서 거절.

**post_bookmark** (SOC-03): member_id, post_id, title_snapshot(varchar 200), blog_name_snapshot(varchar 50), created_at. UNIQUE(member_id, post_id) — 연타 방지 겸용. 저장 목록은 (member_id, created_at DESC, id DESC) 커서. 글이 삭제돼도 행은 남기고(볼 수 없는 글로 표시), 탈퇴하면 그 회원의 행을 지운다. 볼 수 없는 글은 `title_snapshot`·`blog_name_snapshot`만 내려 주고 저장 취소에 쓸 글 번호 외에 지금 제목·본문은 내려 주지 않는다(헌법 원칙 II 예외).

**notification** (P2): receiver_id, type(COMMENT, REPLY, LIKE, SUBSCRIBE, SANCTION), target_type(POST, COMMENT, BLOG, MEMBER), target_id, message(표시 문구), read_at. 받는 회원 한 명당 한 행이다. 공지를 모든 회원에게 알리는 기능은 보류(2026-10-08 지원 결정).

## 블로그 관리 (MNG-03, MNG-04)

**blog_visit** (MNG-03): blog_id, visit_date, visitor_key(회원 id 또는 익명 식별자, view_log와 같은 방식), referrer_type(SEARCH, SNS, DIRECT, INTERNAL, OTHER), referrer_host(직접 방문이면 빈 값). UNIQUE(blog_id, visit_date, visitor_key) — 방문자는 블로그·날짜마다 한 번만 센다. 블로그 주인 본인의 방문은 세지 않는다. 유입 경로는 그날 첫 방문의 Referer로 정한다. 7일 뒤 지운다.

**blog_daily_stat** (MNG-03): blog_id, stat_date, visitor_count, view_count. UNIQUE(blog_id, stat_date). 매일 새벽 전날 `blog_visit`을 모아 만든다. 어제 방문자와 일·주·월 그래프(주·월은 일별 합)에 쓴다. 오늘 방문자는 `blog_visit`에서 바로 센다.

**blog_referrer_daily** (MNG-03): blog_id, stat_date, referrer_type, referrer_host, visit_count. UNIQUE(blog_id, stat_date, referrer_type, referrer_host). 유입 경로 화면용.

MNG-03의 인기 글 순위는 테이블을 따로 두지 않고 누적은 `post.view_count`, 최근 7일은 `view_log`를 쓴다.

**blog_blocked_member** (MNG-04): blog_id, blocked_member_id, memo, created_at. UNIQUE(blog_id, blocked_member_id). 차단된 회원은 그 블로그에 댓글·방명록을 쓸 수 없고 구독할 수 없다. 차단하면 그 회원의 기존 구독을 지운다. IP 차단은 하지 않는다(댓글은 회원만 쓰므로, 2026-10-08 지원 결정). 블로그 주인이 쓰는 기능이라 `moderation_log`에 남기지 않는다.

**blog_banned_word** (MNG-04): blog_id, word(30). UNIQUE(blog_id, word). 블로그당 최대 100개. 댓글·방명록을 새로 쓸 때 대소문자를 무시하고 포함 여부를 검사한다.

## 추천 (PostgreSQL + pgvector, 도전 과제)

**post_embedding**: post_id(MySQL post.id, FK 아님), embedding(vector), updated_at. 글 삭제·비공개 전환 시 함께 지우거나 조회 시 가시성으로 거른다.

## 관리

**report** (P2): reporter_id, target_type(POST, COMMENT, BLOG), target_id, reason(SPAM, ADULT, ABUSE, COPYRIGHT, ETC), description(ETC면 필수), status(PENDING, DONE), result(BLIND, RESTRICT_BLOG, SUSPEND, REJECT), processed_at. UNIQUE(reporter_id, target_type, target_id).

**moderation_log**: admin_id, action(BLIND, UNBLIND, SUSPEND, UNSUSPEND, RESTRICT_BLOG, UNRESTRICT_BLOG, REJECT_REPORT), target_type(POST, COMMENT, BLOG, MEMBER, REPORT), target_id, reason, reason_detail, created_at. INSERT만, 수정·삭제 API 없음. 제재 사유를 저장하는 유일한 곳이다.

- reason: 신고 사유와 같은 코드(SPAM, ADULT, ABUSE, COPYRIGHT, ETC). 제재(BLIND, SUSPEND, RESTRICT_BLOG)에는 필수(CHECK). 관리자가 사유를 직접 쓰지 않고 고르며, 사용자에게 보이는 안내 문구는 Java enum 필드에 둔다.
- reason_detail(200): reason이 ETC면 필수(CHECK).
- 인덱스 (target_type, target_id, created_at DESC): 대상의 최신 제재 행을 바로 찾는다.

**notice**: admin_id, title, content, created_at, updated_at.

## 글 가시성 판단 (모든 글 조회 공통)

기능 명세 "볼 수 없는 글" 정의와 POST-04를 하나의 조건으로 모아 모든 목록·개수·검색·상세에 적용한다. 원본 6장 ② 그림(질문 4개, 결과 6개)이 내보내기에서 빠져 원본 다른 절로 다시 만들었다([지원이 확인할 것](./review.md) 9).

| 질문 | 아니오 | 예 |
| --- | --- | --- |
| ① 글이 있나 (삭제 안 됨, 블로그도 삭제 안 됨) | **404** | ②로 |
| ② 요청한 블로그 소속인가 | ③④를 거쳐 볼 수 있으면 **301**(지금 소속 블로그), 아니면 404 | ③으로 |
| ③ 보는 사람이 블로그 주인인가 | ④로 | **보임** (숨긴 글이면 숨김 사유와 함께) |
| ④ 다른 사람이 볼 수 있나: 발행됨, 숨김 아님, 블로그 제한 아님, 주인 정지 아님, 그리고 공개이거나 구독자 공개+구독 중 | **404** (존재를 숨김). 단, 나머지 조건은 모두 맞고 구독만 안 한 구독자 공개 글이면 **구독 안내**(제목·본문 없이, Q4) | **보임** |

결과 6개: 404(없음), 301(다른 블로그 소속), 주인에게 보임, 주인에게 숨김 사유와 함께 보임, 다른 사람에게 보임, 404(볼 수 없음). 2026-10-07 Q4 결정으로 "구독 안내"가 하나 더 생겼다(상세 화면에서만, 목록에서는 404와 같이 빠짐).

목록용 조건은 ④를 쿼리 조건으로 바꾼 것이다. 주인이 자기 블로그를 볼 때만 ④를 건너뛴다.

블로그 화면(메인 글 목록, 카테고리별 목록, 글 수, 사이드바 최근 글·최근 댓글)에서 주인이 보는 글은 **삭제되지 않은 발행 글 전부**다. 비공개·구독자 공개·숨긴 글은 들어가고, 임시저장·예약 글은 빠진다(관리 화면의 글 관리에서 본다). 발행 순서로 정렬하는 목록이라 발행 시각이 없는 글을 넣지 않는다(2026-10-08 지원 결정, 코드 `PostSpecifications.listedIn`).

## 탈퇴 처리 (AUTH-06, Q1)

한 트랜잭션으로: member.status=WITHDRAWN, withdrawn_at, email·password_hash 비우기, social_account 삭제 → 그 회원의 blog.deleted_at, post.deleted_at, comment·guestbook.deleted_at 기록 → 그 회원의 post_like, subscription, post_bookmark 삭제(공감 수·구독자 수 갱신). 블로그 주소는 행이 남아 영구 예약된다.
