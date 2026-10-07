# Data Model: 티스토리형 블로그 (지원)

원 문서의 ERD 탭은 아직 예전 ID 기준이라, 이 문서는 설계 문서 본문(4~6장)과 spec Key Entities에서 다시 뽑은 초안이다. ERD 탭을 갱신할 때 이 문서와 맞춘다. 공통 컬럼 `id`(PK, bigint), `created_at`, `updated_at`은 생략.

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

**email_verification** (자체 기능): email, code, expires_at. **password_reset_token** (자체 기능): member_id, token, expires_at(30분).

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
| title | varchar(200) | spec Q1 확정 후 조정 |
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
| deleted_at | datetime, NULL | 소프트/하드 미정(R-11) |

인덱스: (blog_id, status, visibility, published_at DESC, id DESC), (status, visibility, published_at DESC, id DESC) — 홈 커서.

**view_log**: post_id, viewer_key(회원 id 또는 익명 식별자), viewed_at. 최근 1시간 인기 글 집계와 중복 조회 판정에 사용.

**image**: path(`./uploads/{uuid}.{ext}`), original_name, size, uploader_id, thumbnail_path.

**category**: blog_id, parent_id(NULL 또는 1단계 상위), name(30), sort_order, is_private(P2). UNIQUE(blog_id, parent_id, name). '전체 글'·'미분류'는 행이 아니라 가상 항목.

**tag**: blog_id, name. UNIQUE(blog_id, name). **post_tag**: post_id, tag_id. PK(post_id, tag_id). 글당 최대 10개는 서비스에서 검사.

## 소통

**comment**: post_id, member_id, parent_id(NULL 또는 1단계), content(1,000), is_secret, deleted(답글 있으면 '삭제된 댓글' 표시용), blinded, blind_reason.

**guestbook**: blog_id, member_id, parent_id, content, is_secret, deleted. 규칙은 댓글과 같음.

**post_like**: member_id, post_id. UNIQUE(member_id, post_id) — 연타 방지 겸용.

**subscription**: member_id, blog_id. UNIQUE(member_id, blog_id). 자기 블로그 구독은 서비스에서 거절.

**notification** (P2): receiver_id, type(COMMENT, REPLY, LIKE, SUBSCRIBE, SANCTION), target 정보, read_at.

## 추천 (PostgreSQL + pgvector, stretch)

**post_embedding**: post_id(MySQL post.id, FK 아님), embedding(vector), updated_at. 글 삭제·비공개 전환 시 함께 지우거나 조회 시 가시성으로 거른다.

## 관리

**report** (P2): reporter_id, target_type(POST, COMMENT, BLOG), target_id, reason(SPAM, ADULT, ABUSE, COPYRIGHT, ETC), description(기타일 때 필수), status(PENDING, DONE). UNIQUE(reporter_id, target_type, target_id).

**moderation_log**: admin_id, action(BLIND, UNBLIND, SUSPEND, UNSUSPEND, RESTRICT_BLOG, UNRESTRICT_BLOG, REJECT_REPORT), target_type, target_id, reason, created_at. INSERT만, 수정·삭제 API 없음.

**notice**: admin_id, title, content.

## 가시성 판단 (모든 글 조회 공통)

spec FR-029 순서를 하나의 조건으로 모아 모든 목록·개수·검색·상세에 적용한다 (원 문서 6장 ②).

1. 글이 없거나 deleted → 404
2. 블로그가 삭제·제한됐거나 주인이 정지 상태(지원 선택, spec Q5 대기)이고 보는 사람이 주인이 아님 → 404
3. 요청 블로그와 소속이 다름 → 볼 수 있으면 소속 블로그로 301, 아니면 404
4. 보는 사람이 블로그 주인 → 모두 보임 (blinded면 사유 표시)
5. blinded → 404
6. status ≠ PUBLISHED → 404
7. visibility: PUBLIC → 보임 / PRIVATE → 404 / SUBSCRIBERS → 구독자면 보임, 아니면 404
