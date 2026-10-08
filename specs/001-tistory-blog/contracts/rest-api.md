# REST API 초안 (지원)

> **이 문서는?** 지원 서비스의 REST API 초안이다. 프론트와 백엔드가 주고받는 약속(경로, 요청, 응답 코드)을 정한다. 전체 문서 안내는 [README](../../../README.md)에 있다.

원본 4~6장과 기능 명세의 기능 코드에서 뽑은 초안이다. 오른쪽 열은 기능 코드다. 경로·필드 이름은 바꿔도 되지만 **응답 코드 규칙은 기능 명세를 따른다**.

## 공통

- JSON. 인증은 `.blog.com` 상위 도메인 HttpOnly 쿠키로 전달한다(Q6, [조사](../research.md) R-03). 상태를 바꾸는 요청에는 CSRF 대책(사용자 지정 헤더 확인 또는 CSRF 토큰)을 함께 둔다.
- 블로그 범위 API는 Host의 서브도메인으로 블로그를 정한다(`myblog.blog.com/api/...`). 플랫폼 API는 `blog.com/api/...`.
- 응답 코드: 404 없음 또는 볼 수 없음(기능 명세 "볼 수 없는 글", 로그인 여부보다 먼저), 401 로그인이 필요한 행동에 로그인 안 함·만료, 403 권한 없음, 409 중복(주소·이메일·태그 등), 400 입력 오류.
- 오류 본문(형식은 확정 전): `{ "code": "BLOG_ADDRESS_TAKEN", "message": "...", "fieldErrors": [{ "field": "address", "reason": "..." }] }`. 내부 정보는 담지 않는다(COM-02).
- 페이지 응답: `{ content, page, size, totalElements, totalPages }`. 커서 응답: `{ content, nextCursor }` (`nextCursor` = 마지막 글의 `publishedAt,id`).
- 연타 방지: 발행·댓글 POST는 `Idempotency-Key` 헤더(R-09 기본값).

## AUTH (플랫폼)

| 메서드 | 경로 | 설명 | ID |
| --- | --- | --- | --- |
| POST | /api/auth/email-verifications | 인증 코드 발송 | OWN-01 |
| POST | /api/auth/signup | 이메일·코드·비밀번호·닉네임 → 회원 생성 | AUTH-01 |
| POST | /api/auth/login | 로그인, `.blog.com` 쿠키 발급. 정지면 403 + 사유·기한 | AUTH-01, ADMIN-02 |
| POST | /api/auth/logout | 쿠키 삭제, 모든 블로그 주소에서 로그아웃 | AUTH-02 |
| GET | /api/auth/oauth/{provider}/authorize?redirect= | state 생성, 제공사로 이동 | AUTH-01 (P1) |
| GET | /api/auth/oauth/{provider}/callback | state 검증, 로그인 또는 닉네임 확인 단계 | AUTH-01 (P1) |
| POST | /api/auth/password-reset | 재설정 링크 발송 / PUT으로 변경 | OWN-02 |
| GET/PATCH | /api/members/me | 내 정보 조회·닉네임·프로필·비밀번호 변경 | AUTH-05 |
| POST/DELETE | /api/members/me/social/{provider} | 소셜 연동·해제 (R-07 거절 조건) | OWN-03 |
| DELETE | /api/members/me | 본인 확인 후 탈퇴 | AUTH-06 |

## BLOG

| 메서드 | 경로 | 설명 | ID |
| --- | --- | --- | --- |
| GET | /api/blogs/address-availability?address= | 규칙·예약어·중복 확인 | BLOG-01 |
| POST | /api/blogs | 개설 (활성 5개 초과 시 409) | BLOG-01 |
| GET | /api/members/me/blogs | 내 블로그 목록 | BLOG-08 |
| GET | /api/blog | 현재 Host 블로그 정보 | BLOG-03 |
| PATCH | /api/blog | 이름·소개·프로필 (주인) | BLOG-02 |
| GET | /api/blog/sidebar | 카테고리 트리·글 수, 태그, 최근 글 5, 최근 댓글 5 | BLOG-04 |
| POST | /api/blog/move-posts | `{ postIds, targetBlogId }` | BLOG-06 |
| PUT | /api/blog/moved-to | 이사 대상 지정 | BLOG-06 |
| PUT | /api/members/me/primary-blog | 대표 지정 | BLOG-08 |
| DELETE | /api/blog | 소프트 삭제 (대표면 409) | BLOG-07 |

## POST

| 메서드 | 경로 | 설명 | ID |
| --- | --- | --- | --- |
| GET | /api/posts?page=&size= | 블로그 글 목록 (+`categoryId`, `tag`) | BLOG-03, CAT-02, TAG-02 |
| POST | /api/posts | 발행 또는 임시저장(`status`) | POST-01, POST-08 |
| GET | /api/posts/{id} | 상세 + 이전·다음 글. 가시성 판단(data-model). 구독 안 한 사람이 구독자 공개 글을 열면 403 `SUBSCRIBERS_ONLY` + `{ blogName }`만(제목·본문 없음), 화면은 구독 안내 | POST-04, POST-10, POST-12 |
| PUT | /api/posts/{id} | 수정 (주인) | POST-02 |
| DELETE | /api/posts/{id} | 삭제 (주인) | POST-03 |
| PATCH | /api/posts/{id}/visibility | 공개 범위 변경 | POST-06 |
| POST | /api/posts/{id}/views | 조회 기록 (중복 판정) | POST-09 |
| POST | /api/images | multipart, 10MB, jpg/png/gif/webp → `{ id, url, thumbnailUrl }` | POST-05 |
| GET | /api/topics | 고정 주제 목록 | POST-11 |
| GET | /api/posts/{id}/same-category | 같은 카테고리의 다른 글 (볼 수 있는 글만) | OWN-05 |
| GET | /api/posts/{id}/similar | 비슷한 글 추천 (pgvector, 볼 수 있는 글만) | OWN-06 |

## CAT · TAG

| 메서드 | 경로 | 설명 | ID |
| --- | --- | --- | --- |
| GET/POST | /api/categories | 트리 조회·추가 | CAT-01 |
| PATCH/DELETE | /api/categories/{id} | 이름 변경·삭제(글은 미분류로, 하위 있으면 409) | CAT-01, CAT-03 |
| PUT | /api/categories/order | 순서·상하위 일괄 변경 | CAT-04 |
| GET | /api/tags | 블로그 태그와 글 수 | TAG-03 |
| PATCH/DELETE | /api/tags/{id} | 이름 변경·삭제 | TAG-04 |

## CMT · SOC

| 메서드 | 경로 | 설명 | ID |
| --- | --- | --- | --- |
| GET | /api/posts/{id}/comments?cursor= | 작성순 20, 답글 포함 | CMT-01 |
| POST | /api/posts/{id}/comments | `{ content, parentId?, secret? }` | CMT-01, CMT-05, CMT-06 |
| PATCH | /api/comments/{id} | 본인만 | CMT-03 |
| DELETE | /api/comments/{id} | 본인 또는 블로그 주인 | CMT-01, CMT-02 |
| GET/POST | /api/guestbook | 방명록 페이지 20 | CMT-04 |
| DELETE | /api/guestbook/{id} | 본인 또는 주인 | CMT-04 |
| PUT/DELETE | /api/posts/{id}/like | 공감·취소 (멱등) → `{ liked, likeCount }` | SOC-01 |
| PUT/DELETE | /api/posts/{id}/bookmark | 저장·취소 (멱등) → `{ bookmarked }` | SOC-03 |
| GET | /api/me/bookmarks?cursor= | 저장한 글 20 (본인만). 볼 수 없는 글은 `{ postId, visible: false, titleSnapshot, blogNameSnapshot, savedAt }`만 | SOC-03 |

## SUB · SRCH · HOME (플랫폼 범위 포함)

| 메서드 | 경로 | 설명 | ID |
| --- | --- | --- | --- |
| PUT/DELETE | /api/blogs/{blogId}/subscription | 구독·해제 (멱등) | SUB-01 |
| GET | /api/feed?cursor= | 구독 피드 20 | SUB-02 |
| GET | /api/search?q=&page= | 블로그 내 검색 (블로그 Host) | SRCH-01 |
| GET | /api/search?q=&type=post\|blog | 전체 검색 (플랫폼 Host) | SRCH-02 |
| GET | /api/home/latest?cursor= | 홈 최신 글 20 | HOME-01 |
| GET | /api/home/popular | 인기 점수(최근 1시간 조회×1 + 공감×3 + 댓글×5) 상위 10 (스냅숏 5분) | HOME-02 |
| GET | /api/home/bloggers | 인기 블로거 상위 5 (블로그 점수, 스냅숏 1시간) | HOME-04 |
| GET | /api/recommend/blogs | 추천 블로그 5 (인기 블로거에서 자기·구독 중 블로그 제외) | SUB-06 |
| GET | /api/ranking/{posts\|bloggers}?snapshotAt=&offset= | 랭킹 전체보기 100위까지 20개씩. `snapshotAt`이 지금 스냅숏과 다르면 `409` + 새 스냅숏 시각 | HOME-05 |
| GET | /api/home/topics/{topic} | 주제별 인기 점수 순 6, 모자라면 최신 글 | HOME-03 |
| GET | /api/notices | 공지 | ADMIN-06 |

## MNG (블로그 Host, 주인만)

| 메서드 | 경로 | 설명 | ID |
| --- | --- | --- | --- |
| GET | /api/manage/posts?status=&categoryId=&q=&page= | 내 글 관리 20, 블라인드 사유 포함 | MNG-01 |
| PATCH/DELETE | /api/manage/posts (일괄) | 공개 범위 변경·삭제 | MNG-01 |
| GET | /api/manage/comments?page= | 받은 댓글·방명록 | MNG-02 |
| GET | /api/manage/stats | 오늘·어제·누적 방문자 | MNG-03 |

## ADMIN (플랫폼 Host, hasRole ADMIN)

| 메서드 | 경로 | 설명 | ID |
| --- | --- | --- | --- |
| GET | /api/admin/members?q=&status= | 회원 조회 | ADMIN-02 |
| POST/DELETE | /api/admin/members/{id}/suspension | 정지(7/30일/영구 + 사유)·해제 | ADMIN-02 |
| POST/DELETE | /api/admin/posts/{id}/blind, /api/admin/comments/{id}/blind | 블라인드·해제 (사유 필수) | ADMIN-03 |
| POST/DELETE | /api/admin/blogs/{id}/restriction | 블로그 제한·해제 | ADMIN-05 |
| POST | /api/reports | 회원 신고 (중복 409) | ADMIN-04 |
| GET/POST | /api/admin/reports, /api/admin/reports/{targetKey}/resolve | 대상별 묶음, 결과 선택 | ADMIN-04 |
| GET | /api/admin/moderation-logs | 조회만 | ADMIN-06 |
| POST | /api/admin/notices | 공지 작성 | ADMIN-06 |
| GET | /api/admin/dashboard | 오늘 가입자, 새 글, 대기 신고, 최근 제재 | ADMIN-06 |
