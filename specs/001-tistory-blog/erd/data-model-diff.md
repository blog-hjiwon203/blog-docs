# ERD와 data-model.md의 차이

> **이 문서는?** Crowfoot ERD 문서 "티스토리 클론 블로그 (지원)"이 [data-model.md](../data-model.md)와 어디가 다른지 정리한 것이다.

- Crowfoot 문서: https://crowfoot.java21.net/workspaces/49/models/665 (MySQL, 테이블 25개, 관계 37개)
- 요구사항 79건 = 기능 코드 77개(코드 하나당 1건, COM-01 포함) + 공통 규칙 2건. 확정 76건은 모두 테이블에 반영됨, 제외 2건(OWN-04, SUB-05), 검토 중 1건(OWN-06). 2026-10-08: MNG-03·MNG-04도 확정해 ERD에 넣음(data-model.md에는 아직 없음). 2026-10-08: 원본 "계획 없음"이던 SOC-03, SUB-06, HOME-04, HOME-05를 확정(PR #3).
- 요구사항 번호: Crowfoot이 REQ-001~079를 자동으로 붙인다(바꿀 수 없음). 제목이 기능 코드로 시작한다(예: "POST-03 글 삭제"). 조회 화면 기능은 읽는 테이블에 연결했다.
- 그룹: 회원·인증, 블로그, 글, 카테고리·태그, 소통, 관리

## 1. data-model.md에 없던 것을 더함

| 위치 | 바꾼 것 | 이유 |
| --- | --- | --- |
| category | 계산 컬럼 `parent_key = IFNULL(parent_id, 0)`, UNIQUE(blog_id, parent_key, name) | data-model의 UNIQUE(blog_id, parent_id, name)는 MySQL에서 NULL끼리 중복을 허용해 **최상위 카테고리 이름 중복을 못 막는다** |
| blog | 계산 컬럼 `primary_owner_id`(대표이고 삭제 안 됐을 때만 member_id) + UNIQUE | "회원당 대표 블로그 하나"를 DB에서도 보장 |
| member | `nickname` UNIQUE, 길이 20 | AUTH-01 "닉네임 중복 확인". 길이는 명세에 없어 Claude가 20자로 정함 |
| blog | `list_layout`(LIST, THUMBNAIL) | BLOG-05 "메인 글 목록 형태"가 data-model에 빠져 있었다 |
| password_reset_token | `token` → `token_hash`(SHA-256), `used_at` 추가 | 원문 토큰을 DB에 두지 않고, 링크를 한 번만 쓰게 |
| email_verification | `verified_at` 추가 | 인증 완료 후 가입까지 이어 주는 표시 |
| image | `content_type`, CHECK size ≤ 10MB | POST-05 형식·크기 규칙 |
| report | `result`(BLIND, RESTRICT_BLOG, SUSPEND, REJECT), `processed_at` | ADMIN-04 처리 결과 4가지 |
| notification | `receiver_id`, `target_type`/`target_id`, `message` | data-model은 "target 정보"로만 적혀 있었다 |
| guestbook | `deleted`(boolean) → `deleted_at` | 소프트 삭제(Q1) 규칙을 댓글과 맞춤 |
| 인덱스 | 주제별 글(topic, status, visibility, published_at), 예약 발행(status, scheduled_at), 조회 중복 확인(post_id, viewer_key, viewed_at), 인기 점수용 created_at/viewed_at | HOME-03, POST-13, POST-09(Q2), HOME-02(Q7) |
| 열거값 | VARCHAR + CHECK. 주제 코드는 IT_DEV, TRAVEL, FOOD, DAILY, REVIEW, HOBBY, FINANCE, HEALTH, CULTURE, EDUCATION | JPA EnumType.STRING에 맞춤. 주제 영문 코드는 Claude가 정함 |
| post_bookmark (새 테이블) | member_id, post_id, title_snapshot, blog_name_snapshot, created_at. UNIQUE(member_id, post_id), (member_id, created_at DESC, id DESC) 인덱스 | SOC-03 (2026-10-08). 볼 수 없게 된 글은 저장 시점 제목만 보여 준다 |
| blog_visit, blog_daily_stat, blog_referrer_daily (새 테이블), blog.total_visitor_count | 방문 = 블로그·날짜·visitor_key 하나(UNIQUE). 매일 새벽 일별 통계·유입 경로로 모으고 누적에 더함. blog_visit은 7일 보관 | MNG-03 (2026-10-08). data-model.md에 없음 |
| blog_blocked_member, blog_banned_word (새 테이블) | 차단 회원은 그 블로그에 댓글·방명록·구독 불가, UNIQUE(blog_id, blocked_member_id). IP 차단 없음. 금칙어 UNIQUE(blog_id, word), 블로그당 100개 | MNG-04 (2026-10-08 지원 결정). data-model.md에 없음 |

## 2. 일부러 넣지 않은 것

- `post_embedding`(PostgreSQL + pgvector, OWN-06): 도전 과제라 ERD 본체에서 뺐다.
- Idempotency-Key(발행·댓글): Redis에 두므로 테이블 없음.
- 인기 글·인기 블로거 순위 스냅숏(HOME-02·04·05, SUB-06): Redis라 테이블 없음.

## 3. 명세에는 있는데 data-model에도 ERD에도 없는 것

- **MNG-03 방문자 수·통계, MNG-04 스팸·차단 (P2)**: 2026-10-08 ERD에는 넣었다(위 1장 표). data-model.md와 tasks.md에는 아직 없다.

## 4. 외래 키 동작

- 소프트 삭제라 연쇄 삭제는 쓰지 않는다. 예외: `post_tag`(글·태그가 지워지면 함께 삭제).
- `post.category_id`는 카테고리를 지우면 NULL(미분류, CAT-01).
- 이미지 참조(`profile_image_id`, `thumbnail_image_id`)는 이미지를 지우면 NULL.
- `image.uploader_id`는 외래 키 없이 둔다(회원 ↔ 이미지 순환 참조 제거, 2026-10-08 지원 결정). 인덱스만 있다.

## 5. 2026-10-08 지원 검토 반영

- 제재 사유는 `moderation_log`에만 둔다(reason 코드 SPAM·ADULT·ABUSE·COPYRIGHT·ETC + reason_detail, 제재 조치엔 reason 필수). `member.suspend_reason`, `blog.restrict_reason`, `post.blind_reason`, `comment.blind_reason` 삭제. 안내 문구는 Java enum 필드.
- 참/거짓 컬럼은 is_ 접두사: `post.is_blinded`, `post.is_comment_allowed`, `comment.is_blinded` (기존 is_primary, is_restricted, is_private, is_secret).
- created_at 삭제: tag, post_tag, category, blog_visit, blog_banned_word. social_account는 연동 시각이라 남김.
- `image.uploader_id`는 외래 키 없이 유지(순환 참조 없는 쪽이 낫다고 판단).
- 공지 알림은 보류.

