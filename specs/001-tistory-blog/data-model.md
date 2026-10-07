# 데이터 모델 (Data Model): 티스토리형 블로그 (지원)

> **이 문서는?** 지원 서비스의 테이블·컬럼·제약과 글 가시성 판단 순서다. 기능 명세의 핵심 엔티티를 실제 저장 구조로 옮긴 것이다. 전체 문서 안내는 [README](../../README.md)에 있다.

원본 ERD 탭은 예전 ID 기준이라, 이 문서는 원본 본문(4~6장)과 기능 명세 핵심 개체에서 다시 뽑은 초안이다. 지금 기능 코드 기준이다([지원이 확인할 것](./review.md) 16). 공통 컬럼 `id`(PK, bigint), `created_at`, `updated_at`은 생략.

## 회원·인증

**member**
| 컬럼 | 타입 | 규칙 |
| --- | --- | --- |
| email | varchar, NULL | UNIQUE. 이메일 가입 회원만 값이 있고 모두 인증된 회원 |
| password_hash | varchar, NULL | bcrypt |
| nickname | varchar | |
| profile_image_id | FK image, NULL | |
| role | enum USER, ADMIN | 가입은 항상 USER. ADMIN은 data.sql로만 |
| status | enum ACTIVE, SUSPENDED, WITHDRAWN | 모든 로그인 경로에서 먼저 확인 |
| suspended_until | datetime, NULL | NULL + SUSPENDED = 영구 |
| suspend_reason | varchar, NULL | |
| withdrawn_at | datetime, NULL | |

**social_account**: member_id, provider(KAKAO, GOOGLE), provider_user_id. UNIQUE(provider, provider_user_id), UNIQUE(member_id, provider).

**email_verification** (OWN-01): email, code, expires_at. **password_reset_token** (OWN-02): member_id, token, expires_at(30분).

## 블로그

**blog**
| 컬럼 | 타입 | 규칙 |
| --- | --- | --- |
| member_id | FK member | 주인 1명 |
| address | varchar | UNIQUE, 불변. 삭제돼도 행이 남아 영구 예약 |
| name | varchar(50) | |
| description | varchar, NULL | |
| profile_image_id | FK image, NULL | |
| is_primary | boolean | 회원당 하나. 처음 만든 블로그 |
| moved_to_blog_id | FK blog, NULL | 이사 대상. 연쇄 이사 시 최종 대상으로 갱신 |
| restricted | boolean, restrict_reason | ADMIN-05 |
| skin | varchar | BLOG-05 (P2) |
| deleted_at | datetime, NULL | 소프트 삭제. 활성 = deleted_at IS NULL |

## 글

**post**
| 컬럼 | 타입 | 규칙 |
| --- | --- | --- |
| id | bigint | 전역 번호 = 글 주소 `{address}.blog.com/{id}` |
| blog_id | FK blog | 이사로 바뀔 수 있음. 옛 주소는 서버가 301 |
| category_id | FK category, NULL | NULL = 미분류 |
| title | varchar(200) | |
| content_html | text | 서버 정화 후 저장 |
| summary | varchar | jsoup으로 태그 제거한 요약 |
| thumbnail_image_id | FK image, NULL | 미지정 시 첫 이미지 |
| status | enum DRAFT, PUBLISHED, SCHEDULED | |
| visibility | enum PUBLIC, PRIVATE, SUBSCRIBERS | 기본 PUBLIC |
| topic | enum, NULL | 10개 고정, NULL = 주제 없음 |
| published_at | datetime, NULL | 처음 발행 시각. 정렬 기준. 수정해도 불변 |
| scheduled_at | datetime, NULL | POST-13 |
| view_count | bigint | 표시용 누적 |
| like_count, comment_count | int | 비정규화. 새로고침 시 실제 값과 같아야 함(트랜잭션 안에서 갱신) |
| comment_allowed | boolean | CMT-07 |
| blinded | boolean, blind_reason | ADMIN-03 |
| deleted_at | datetime, NULL | 소프트 삭제(Q3). 삭제하면 그 글의 댓글·공감·알림도 같은 트랜잭션에서 소프트 삭제 또는 제거 |

인덱스: (blog_id, status, visibility, published_at DESC, id DESC), (status, visibility, published_at DESC, id DESC) — 홈 커서.

**view_log**: post_id, viewer_key(회원 id 또는 익명 식별자), viewed_at. 같은 viewer_key가 5분 안에 다시 열면 기록하지 않는다(Q2). 최근 1시간 인기 점수 집계에 사용.

**인기 점수** (HOME-02, HOME-03): 최근 1시간 안의 `view_log` 수×1 + `post_like` 수(created_at 기준)×3 + 삭제·숨김 안 된 `comment` 수×5. 5분마다 계산해 Redis 캐시에 둔다. 가중치는 설정값으로 둔다.

**image**: path(`./uploads/{uuid}.{ext}`), original_name, size, uploader_id, thumbnail_path.

**category**: blog_id, parent_id(NULL 또는 1단계 상위), name(30), sort_order, is_private(P2). UNIQUE(blog_id, parent_id, name). '전체 글'·'미분류'는 행이 아니라 가상 항목.

**tag**: blog_id, name. UNIQUE(blog_id, name). **post_tag**: post_id, tag_id. PK(post_id, tag_id). 글당 최대 10개는 서비스에서 검사.

## 소통

**comment**: post_id, member_id, parent_id(NULL 또는 1단계), content(1,000), is_secret, deleted_at(소프트 삭제, 답글 있으면 '삭제된 댓글입니다' 표시), blinded, blind_reason.

**guestbook**: blog_id, member_id, parent_id, content, is_secret, deleted. 규칙은 댓글과 같음.

**post_like**: member_id, post_id. UNIQUE(member_id, post_id) — 연타 방지 겸용.

**subscription**: member_id, blog_id. UNIQUE(member_id, blog_id). 자기 블로그 구독은 서비스에서 거절.

**notification** (P2): receiver_id, type(COMMENT, REPLY, LIKE, SUBSCRIBE, SANCTION), target 정보, read_at.

## 추천 (PostgreSQL + pgvector, 도전 과제)

**post_embedding**: post_id(MySQL post.id, FK 아님), embedding(vector), updated_at. 글 삭제·비공개 전환 시 함께 지우거나 조회 시 가시성으로 거른다.

## 관리

**report** (P2): reporter_id, target_type(POST, COMMENT, BLOG), target_id, reason(SPAM, ADULT, ABUSE, COPYRIGHT, ETC), description(기타일 때 필수), status(PENDING, DONE). UNIQUE(reporter_id, target_type, target_id).

**moderation_log**: admin_id, action(BLIND, UNBLIND, SUSPEND, UNSUSPEND, RESTRICT_BLOG, UNRESTRICT_BLOG, REJECT_REPORT), target_type, target_id, reason, created_at. INSERT만, 수정·삭제 API 없음.

**notice**: admin_id, title, content.

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

## 탈퇴 처리 (AUTH-06, Q1)

한 트랜잭션으로: member.status=WITHDRAWN, withdrawn_at, email·password_hash 비우기, social_account 삭제 → 그 회원의 blog.deleted_at, post.deleted_at, comment·guestbook.deleted_at 기록 → 그 회원의 post_like, subscription 삭제(공감 수·구독자 수 갱신). 블로그 주소는 행이 남아 영구 예약된다.
