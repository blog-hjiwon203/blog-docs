# REST API 명세 (지원)

> **이 문서는?** 지원 서비스의 REST API 명세다. 프론트와 백엔드가 주고받는 약속(경로, 요청, 응답, 오류 코드)을 정한다. 어느 화면이 어느 API를 부르는지는 [화면 목업](../mockups/README.md)에 있다. 전체 문서 안내는 [README](../../../README.md)에 있다.

[기능 명세](../spec.md)의 기능 코드 전부(P0·P1·P2, 제외된 OWN-04·SUB-05 빼고)를 다루고, 필드 이름과 값은 [ERD](../erd/README.md)(Crowfoot 문서 버전 74)를 따른다. 표의 오른쪽 열은 기능 코드다. 경로·필드 이름은 바꿔도 되지만 **응답 코드 규칙은 기능 명세를 따른다**.

## 이번 정리에서 바뀐 것 (2026-10-08)

초안에서 아래를 고치고 채웠다. 새로 정한 값은 맨 아래 [이 문서에서 채운 값](#이-문서에서-채운-값)에 모았다.

- **빠졌던 기능을 채웠다**: 사이드바 모듈 순서·표시(BLOG-05, PR #8에서 정한 것), 알림(SUB-04), 예약 발행(POST-13), 대표 이미지(POST-07), 댓글 허용(CMT-07), 카테고리 비공개(CAT-05), 블로그 꾸미기(BLOG-05), 블로그 삭제 경고 수(BLOG-07), 방명록 수정(CMT-04), 소셜 가입의 닉네임 확인 단계(AUTH-01), 소셜 재인증 탈퇴(AUTH-06), 회원 상세(ADMIN-02), 공지 목록·상세(ADMIN-06), 관리 이력 검색 조건(ADMIN-06).
- **내 정보 경로를 `/api/me/**`로 모았다**: 초안의 `/api/members/me/**`와 `/api/me/bookmarks`가 섞여 있었다.
- **편집용 글 조회를 따로 두었다**: `GET /api/manage/posts/{id}`. 임시저장·예약·숨긴 글도 주인이 불러와야 해서 읽기용 상세와 나눴다.
- **이메일 인증을 두 단계로 나눴다**: 코드 확인(`/verify`)으로 화면에서 바로 결과를 보여 주고, 가입 요청에서 서버가 한 번 더 확인한다.
- **비밀번호 재설정을 요청·변경 두 경로로 나눴다**.
- **요청·응답 본문, 오류 코드 목록, 주요 응답 객체 모양을 적었다**.
- **Host 범위를 표마다 적었다**: 블로그 주소에서만 되는 API와 어디서나 되는 API를 구분한다.

## 공통

### 주소와 Host 범위

| 표기 | 뜻 | 예 |
| --- | --- | --- |
| **P** | 플랫폼 주소에서 부른다 | `blog.com/api/...` |
| **B** | 블로그 주소에서 부른다. Host의 서브도메인으로 블로그를 정한다. 없거나 볼 수 없는 블로그면 404 | `myblog.blog.com/api/...` |
| **\*** | 어느 주소에서 불러도 같다. 대상은 경로의 ID로 정한다 | `/api/blogs/{blogId}/subscription` |

- 이사한 블로그(`moved_to_blog_id`가 있음)의 Host로 **B** API를 부르면, 주인이 아닌 사람에게는 404다. 화면 주소는 서버가 먼저 301로 보내므로 프론트가 이 404를 볼 일은 거의 없다. 주인은 옛 블로그 관리 API를 계속 쓴다(BLOG-06).
- **B** API에서 글 번호가 Host 블로그 소속이 아니면 404다. 다른 블로그로 보내는 301은 화면 주소 단계에서 서버가 한다([화면 주소 단계](#화면-주소-단계에서-서버가-하는-일-api-없음)).

### 인증과 보안

- 인증은 `Domain=.blog.com; HttpOnly; Secure; SameSite=Lax` 쿠키다(Q6, [조사](../research.md) R-03). Refresh Token 쿠키를 함께 준다. 로그인 유지(AUTH-03)를 고르면 14일 남는 쿠키, 고르지 않으면 브라우저를 닫으면 사라지는 쿠키이고 30분 동안 요청이 없으면 서버에서 끝난다(R-03). Access 토큰이 끝나면 서버가 요청을 처리하면서 새 Access 쿠키를 준다.
- 상태를 바꾸는 요청(POST·PUT·PATCH·DELETE)은 `X-Requested-With: XMLHttpRequest` 헤더가 없으면 403 `CSRF_REJECTED`다.
- 정지된 회원이 이미 로그인한 상태로 API를 부르면 그 요청부터 403 `MEMBER_SUSPENDED`와 쿠키 삭제다(ADMIN-02). 화면 주소 요청은 403 대신 비회원으로 그리고, 화면이 부르는 첫 API에서 정지 안내를 받는다(화면이 JSON 오류로 깨지지 않게, 2026-10-08 지원 확인).
- 탈퇴한 회원의 쿠키가 남아 있으면 쿠키를 지우고 비회원으로 처리한다. 로그인이 필요한 요청은 그대로 401이다(2026-10-08 지원 확인).
- 본문 HTML(`contentHtml`)은 서버가 허용 목록으로 정화해 저장하고, 그 밖의 문자열은 글자 그대로 돌려준다. 프론트는 `contentHtml`만 DOMPurify를 한 번 더 거쳐 넣고, 나머지는 텍스트로 넣는다.

### 요청·응답 형식

- 본문은 JSON(`application/json; charset=UTF-8`). 이미지 업로드만 `multipart/form-data`.
- 오류 응답은 `Accept`와 상관없이 JSON이다. 브라우저 주소창으로 API를 열어도 같은 오류 본문이 나온다.
- 시각은 한국 시간 ISO-8601(`2026-10-08T13:20:00+09:00`). 날짜만 있는 값은 `2026-10-08`.
- ID는 숫자. 글 번호 `id`가 곧 글 주소의 번호다(`{address}.blog.com/{id}`).
- 열거값은 ERD의 영문 코드 그대로다(`PUBLIC`, `SUBSCRIBERS`, `IT_DEV` 등). 화면 문구는 프론트가 코드로 고르고, 제재 사유 안내 문구만 서버가 `reasonMessage`로 준다.
- 성공 코드: 조회·변경 200, 생성 201(본문에 새 자원), 본문 없는 성공 204.

### 목록

| 방식 | 요청 | 응답 |
| --- | --- | --- |
| 페이지 번호 | `?page=1&size=10` (`page`는 1부터) | `{ "content": [...], "page": 1, "size": 10, "totalElements": 57, "totalPages": 6 }` |
| 더보기(커서) | `?cursor=...&size=20` (처음엔 `cursor` 없이) | `{ "content": [...], "nextCursor": "MjAyNi0xMC0w..." }` 끝이면 `nextCursor: null` |

- `size`는 1~50만 받고, 생략하면 기능 명세 [목록과 페이지](../spec.md) 표의 개수다. 범위를 벗어나면 400.
- 커서는 서버가 만든 불투명 문자열이다(안에는 마지막 항목의 `publishedAt,id` 등). 프론트는 해석하지 않고 그대로 돌려보낸다.
- 모든 목록과 개수는 보는 사람이 볼 수 있는 글만 센다([데이터 모델](../data-model.md) 글 가시성 판단).

### 연타 방지

- 글 발행·임시저장 생성(`POST /api/posts`), 댓글 작성, 방명록 작성은 `Idempotency-Key` 헤더(UUID)를 받는다. 같은 키로 다시 오면 처음 응답을 그대로 돌려준다(R-09). 키가 없으면 400. 키는 회원과 경로마다 따로이고 10분 동안 기억한다. 처음 요청이 실패(2xx가 아님)하면 같은 키로 다시 보낼 수 있고, 처음 요청이 아직 처리 중이면 서버가 3초까지 기다렸다가 그 응답을 주며 넘으면 429 `TOO_MANY_REQUESTS`다(2026-10-08 지원 확인).
- 공감·저장·구독은 `PUT`(켜기)·`DELETE`(끄기)라 몇 번 와도 결과가 같다. 이미 켜진 것을 켜거나 꺼진 것을 꺼도 200이다.

### 상태 코드 순서

한 요청이 여러 조건에 걸리면 위에서부터 먼저 걸린 것을 준다.

1. **404** 대상이 없거나 볼 수 없음(로그인 여부와 상관없이, 헌법 원칙 II)
2. **401** 로그인이 필요한 행동인데 로그인 안 함·만료
3. **403** 로그인했지만 권한 없음, 정지, 차단, 구독자 공개
4. **400** 입력 오류 / **409** 중복·상태 충돌

예외: 구독하지 않은 사람이 구독자 공개 글 상세를 열면 404 대신 403 `SUBSCRIBERS_ONLY`(Q4).

### 오류 본문

```json
{
  "code": "VALIDATION_FAILED",
  "message": "입력값을 확인해 주세요.",
  "fieldErrors": [{ "field": "title", "reason": "제목을 입력해 주세요." }]
}
```

`message`는 화면에 그대로 띄워도 되는 문장이다. 스택, SQL, 클래스 이름 같은 내부 정보는 담지 않는다(COM-02). 오류마다 더 줄 정보가 있으면 `detail` 객체에 담는다.

| 상태 | code | 언제 | detail |
| --- | --- | --- | --- |
| 400 | `VALIDATION_FAILED` | 형식·길이·필수값 오류 | `fieldErrors` |
| 400 | `IDEMPOTENCY_KEY_REQUIRED` | 연타 방지 대상에 키 없음 | |
| 400 | `INVALID_VERIFICATION_CODE` | 이메일 인증 코드가 틀림 | |
| 400 | `VERIFICATION_EXPIRED` | 인증 코드 만료 | |
| 400 | `RESET_TOKEN_INVALID` | 재설정 링크가 틀렸거나 만료·사용됨 | |
| 400 | `BLOG_ADDRESS_INVALID` | 주소 규칙 위반·예약어 | `fieldErrors` |
| 400 | `UNSUPPORTED_IMAGE` | jpg/png/gif/webp가 아님(파일 앞부분으로 판단), 파일 이름의 확장자가 jpg·jpeg·png·gif·webp가 아니거나 실제 형식과 다름 | |
| 400 | `IMAGE_TOO_LARGE` | 10MB 초과 | |
| 400 | `TOO_MANY_TAGS` | 태그 10개 초과 | |
| 400 | `BANNED_WORD` | 댓글·방명록에 그 블로그 금칙어 | |
| 400 | `INVALID_MOVE_TARGET` | 이사 대상이 자기 자신·삭제·남의 블로그 | |
| 401 | `UNAUTHORIZED` | 로그인 필요 | |
| 401 | `LOGIN_FAILED` | 이메일 또는 비밀번호가 맞지 않음(탈퇴 회원 포함) | |
| 403 | `FORBIDDEN` | 권한 없음(남의 블로그 관리, 관리자 영역 등) | |
| 403 | `CSRF_REJECTED` | CSRF 헤더 없음 | |
| 403 | `MEMBER_SUSPENDED` | 정지 회원 | `{ reason, reasonMessage, suspendedUntil }` (영구면 `null`) |
| 403 | `BLOCKED_BY_BLOG` | 그 블로그에서 차단된 회원이 댓글·방명록·구독 | |
| 403 | `SUBSCRIBERS_ONLY` | 구독자 공개 글을 구독 안 한 사람이 엶 | `{ blogId, blogName, blogAddress }` (제목·본문 없음) |
| 403 | `COMMENTS_DISABLED` | 댓글을 막은 글에 댓글 | |
| 403 | `POST_BLINDED` | 숨긴 글을 작성자가 수정 | `{ reason, reasonMessage }` |
| 404 | `NOT_FOUND` | 없거나 볼 수 없음 | |
| 405 | `METHOD_NOT_ALLOWED` | 있는 주소를 지원하지 않는 방식(GET·POST 등)으로 부름 | |
| 409 | `EMAIL_TAKEN` | 이메일 가입 회원 중 같은 이메일 | |
| 409 | `NICKNAME_TAKEN` | 닉네임 중복 | |
| 409 | `BLOG_ADDRESS_TAKEN` | 쓰는 중이거나 삭제된 블로그의 주소 | |
| 409 | `BLOG_LIMIT_EXCEEDED` | 활성 블로그 5개에서 개설 | |
| 409 | `PRIMARY_BLOG` | 대표 블로그 삭제 시도 | |
| 409 | `CATEGORY_HAS_CHILDREN` | 하위가 있는 카테고리 삭제 | |
| 409 | `CATEGORY_DEPTH` | 3단계가 되는 순서 변경·추가 | |
| 409 | `NAME_TAKEN` | 카테고리·태그 이름 중복 | |
| 409 | `SOCIAL_ALREADY_LINKED` | 다른 회원에 연결된 소셜 계정 | |
| 409 | `PROVIDER_ALREADY_LINKED` | 같은 제공사가 이미 연결됨 | |
| 409 | `LAST_LOGIN_METHOD` | 해제하면 로그인 수단이 없음 | |
| 409 | `ALREADY_REPORTED` | 같은 대상을 다시 신고 | |
| 409 | `ALREADY_BLOCKED` | 이미 차단한 회원 | |
| 409 | `BANNED_WORD_LIMIT` | 금칙어 100개 초과 | |
| 409 | `RANKING_UPDATED` | 랭킹 더보기 중 스냅숏이 바뀜 | `{ snapshotAt }` (새 기준 시각) |
| 429 | `TOO_MANY_REQUESTS` | 인증 메일·재설정 메일을 1분 안에 다시 요청, 같은 연타 방지 키의 처음 요청이 3초 넘게 처리 중, 로그인 비밀번호(이메일별)·인증 코드(이메일별)·비밀번호 변경의 지금 비밀번호(회원별)를 15분 안에 5번 틀림(다섯 번째부터 15분 동안), 같은 IP에서 이 셋을 합쳐 15분 안에 20번 틀림(research R-17) | `{ retryAfterSeconds }` |
| 500 | `INTERNAL_ERROR` | 예상하지 못한 오류 | |

### 제재 사유

관리자 제재(ADMIN-02·03·05)와 신고(ADMIN-04)는 같은 사유 코드를 쓴다. 요청에는 `reason`과, `ETC`일 때만 `reasonDetail`(200자, 신고는 `description` 500자)을 보낸다. 응답에는 서버 enum의 안내 문구 `reasonMessage`를 함께 준다.

| reason | 화면 이름 |
| --- | --- |
| `SPAM` | 스팸·광고 |
| `ADULT` | 음란·유해 |
| `ABUSE` | 욕설·비방 |
| `COPYRIGHT` | 저작권 침해 |
| `ETC` | 기타 (설명 필수) |

## 주요 응답 객체

여러 API가 같이 쓰는 모양이다. 아래 표에서는 이 이름으로 가리킨다.

**MemberSummary** — 댓글 작성자, 블로그 주인 등

```json
{ "id": 7, "nickname": "지원", "profileImageUrl": "/uploads/a1.webp", "primaryBlogAddress": "jiwon" }
```

`primaryBlogAddress`는 대표 블로그가 없거나 볼 수 없으면 `null`이다(BLOG-08 닉네임 링크).

**Me** — `GET /api/me`

```json
{
  "id": 7, "email": "jiwon@example.com", "nickname": "지원", "profileImageUrl": null,
  "role": "USER", "hasPassword": true,
  "primaryBlog": { "id": 3, "address": "jiwon", "name": "지원의 기록" },
  "socialAccounts": [{ "provider": "KAKAO", "linkedAt": "2026-10-08T10:00:00+09:00" }],
  "unreadNotificationCount": 2
}
```

`email`은 소셜 가입 회원이면 `null`, `hasPassword`는 이메일 가입 회원만 `true`. `primaryBlog`가 `null`이면 글쓰기 버튼이 블로그 개설로 간다(AUTH-04).

**Blog** — `GET /api/blog`

```json
{
  "id": 3, "address": "jiwon", "name": "지원의 기록", "description": "개발 공부 기록",
  "profileImageUrl": null, "owner": { "...": "MemberSummary" },
  "skin": "BASIC", "listLayout": "LIST", "accentColor": "BLUE",
  "postCount": 42, "subscriberCount": 18,
  "viewer": { "isOwner": false, "subscribed": true },
  "restriction": null
}
```

`viewer.subscribed`는 비회원이면 `false`. `restriction`은 주인에게만, 이용 제한 중일 때 `{ "reason": "SPAM", "reasonMessage": "..." }`(ADMIN-05).

**PostSummary** — 목록 한 줄

```json
{
  "id": 1532, "title": "Spring Security 정리", "summary": "필터 체인부터...",
  "thumbnailUrl": "/uploads/t_a1.jpg",
  "blog": { "id": 3, "address": "jiwon", "name": "지원의 기록" },
  "category": { "id": 11, "name": "Spring" }, "topic": "IT_DEV",
  "publishedAt": "2026-10-08T09:00:00+09:00", "likeCount": 5, "commentCount": 2
}
```

`category`가 `null`이면 미분류. `thumbnailUrl`은 대표 이미지(POST-07)의 썸네일, 없으면 본문 첫 이미지, 그것도 없으면 `null`. 주인 목록(MNG-01)에는 `status`, `visibility`, `scheduledAt`, `blinded`가 더 붙는다.

**PostDetail** — `GET /api/posts/{id}`

```json
{
  "id": 1532, "blog": { "id": 3, "address": "jiwon", "name": "지원의 기록" },
  "title": "Spring Security 정리", "contentHtml": "<p>...</p>",
  "category": { "id": 11, "name": "Spring" }, "tags": ["spring", "security"], "topic": "IT_DEV",
  "visibility": "PUBLIC", "publishedAt": "2026-10-08T09:00:00+09:00", "updatedAt": "2026-10-08T11:30:00+09:00",
  "viewCount": 120, "likeCount": 5, "commentCount": 2, "commentAllowed": true,
  "author": { "...": "MemberSummary" },
  "viewer": { "isOwner": false, "liked": false, "bookmarked": true },
  "blind": null,
  "prev": { "id": 1501, "title": "이전 글 제목" }, "next": null
}
```

`blind`는 숨긴 글을 작성자가 볼 때만 `{ reason, reasonMessage }`(ADMIN-03). `prev`·`next`는 같은 블로그 발행 순서에서 볼 수 있는 글만(POST-10). `updatedAt`은 발행 후 고친 적이 없으면 `null`.

**Comment** — 댓글·방명록 공통

```json
{
  "id": 88, "parentId": null, "author": { "...": "MemberSummary" },
  "content": "잘 읽었습니다", "secret": false, "state": "NORMAL",
  "createdAt": "2026-10-08T10:00:00+09:00", "updatedAt": null,
  "viewer": { "canEdit": false, "canDelete": true },
  "replies": [ { "...": "Comment (replies 없음)" } ]
}
```

| state | 뜻 | content·author |
| --- | --- | --- |
| `NORMAL` | 보통 | 그대로 |
| `SECRET` | 비밀댓글인데 보는 사람이 글 주인·작성자가 아님(CMT-06) | `null` ("비밀댓글입니다") |
| `DELETED` | 지웠지만 답글이 있어 자리만 남음(CMT-05) | `null` ("삭제된 댓글입니다") |
| `BLINDED` | 관리자가 숨김(ADMIN-03). 작성자 본인에게는 `NORMAL`과 `blind` 사유 | `null` ("관리자가 숨긴 댓글") |

답글이 없는 삭제 댓글은 목록에서 빠진다.

## 엔드포인트

권한 열: **누구나** · **회원**(로그인) · **본인** · **주인**(Host 블로그 주인) · **관리자**(ADMIN).

### AUTH 회원·인증

| 메서드 | 경로 | Host | 권한 | 설명 | ID |
| --- | --- | --- | --- | --- | --- |
| POST | /api/auth/email-verifications | P | 누구나 | `{ email }` → 202. 인증 코드 메일 발송. 이메일 가입 회원 중 중복이면 409 `EMAIL_TAKEN`, 1분 안에 다시 요청하면 429 | OWN-01 |
| POST | /api/auth/email-verifications/verify | P | 누구나 | `{ email, code }` → 200. 화면 단계 확인용(코드를 쓰지는 않음) | OWN-01 |
| GET | /api/auth/nickname-availability?nickname= | P | 누구나 | `{ available }`. 형식 오류면 400 | AUTH-01 |
| POST | /api/auth/signup | P | 누구나 | `{ email, code, password, nickname }` → 201 `Me` + 로그인 쿠키. 서버가 코드를 다시 확인하고 `verified_at`을 남긴다. 비밀번호는 8자 이상 영문+숫자, 72바이트 이하(아니면 400 `VALIDATION_FAILED`, `field: password`) | AUTH-01, OWN-01 |
| POST | /api/auth/login | P | 누구나 | `{ email, password, rememberMe }` → 200 `Me` + 쿠키. 실패 401 `LOGIN_FAILED`, 정지 403 `MEMBER_SUSPENDED` | AUTH-01, AUTH-03, ADMIN-02 |
| POST | /api/auth/logout | \* | 회원 | 204. 쿠키 삭제 + 토큰 무효화. 모든 블로그 주소에서 로그아웃 | AUTH-02 |
| POST | /api/auth/token/refresh | \* | 누구나 | Refresh 쿠키로 Access 쿠키 재발급(Access가 끝났으면 새 쿠키, 살아 있으면 그대로) → 204. Refresh가 없거나 끝났거나 탈퇴면 401. 정지면 다른 API와 같이 403 `MEMBER_SUSPENDED`(정지 사유, 2026-10-10 지원 결정) | AUTH-03 |
| GET | /api/auth/oauth/{provider}/authorize?mode=&redirect= | P | 누구나 | `provider`: `kakao`·`google`. `mode`: `login`(기본)·`link`·`reauth`. state를 만들고 제공사로 302 | AUTH-01, OWN-03, AUTH-06 |
| GET | /api/auth/oauth/{provider}/callback | P | 누구나 | state 확인 후 302. 아래 [소셜 로그인 흐름](#소셜-로그인-흐름) | AUTH-01, OWN-03 |
| POST | /api/auth/oauth/signup | P | 누구나 | `{ signupToken, nickname }` → 201 `Me` + 쿠키. 처음 보는 소셜 계정의 닉네임 확인 단계 | AUTH-01 |
| POST | /api/auth/password-reset | P | 누구나 | `{ email }` → 202. 가입된 이메일이 아니어도 같은 응답(가입 여부를 드러내지 않음) | OWN-02 |
| PUT | /api/auth/password-reset | P | 누구나 | `{ token, newPassword }` → 204. 틀렸거나 30분 지났거나 쓴 링크면 400 `RESET_TOKEN_INVALID` | OWN-02 |

#### 소셜 로그인 흐름

| mode | 상황 | 콜백 결과 |
| --- | --- | --- |
| `login` | 연결된 소셜 계정, 활동 회원 | 쿠키 발급, `redirect`로 302 (우리 서비스 주소만, 아니면 홈) |
| `login` | 연결된 소셜 계정, 정지 회원 | `blog.com/login?error=MEMBER_SUSPENDED`로 302 (화면이 `POST /api/auth/login`과 같은 안내) |
| `login` | 처음 보는 소셜 계정 | `blog.com/signup/social?token={signupToken}`으로 302. 토큰은 10분 유효, 제공사 이메일은 담지 않음 |
| `link` | 처음 보는 소셜 계정 | 연결 후 `blog.com/me?linked={provider}` |
| `link` | 다른 회원에 연결됨 / 같은 제공사 이미 연결 | `blog.com/me?error=SOCIAL_ALREADY_LINKED` / `PROVIDER_ALREADY_LINKED` |
| `reauth` | 로그인한 회원 본인의 소셜 계정 | 10분짜리 재인증 표시를 남기고 `blog.com/me/withdraw?reauth=ok` |

### ME 내 정보 (마이페이지)

| 메서드 | 경로 | Host | 권한 | 설명 | ID |
| --- | --- | --- | --- | --- | --- |
| GET | /api/me | \* | 회원 | `Me`. 비회원이면 401 (프론트는 로그인 상태 확인에 씀) | AUTH-04, AUTH-05 |
| PATCH | /api/me | P | 회원 | `{ nickname?, profileImageId? }` → `Me`. 보내지 않은 칸은 그대로. 닉네임 중복 409(대소문자만 바꾸기는 됨). `profileImageId`는 본인이 올린 이미지만(아니면 400 `fieldErrors[].field = profileImageId`). `Me.profileImageUrl`은 썸네일 주소 | AUTH-05 |
| PUT | /api/me/password | P | 회원 | `{ currentPassword, newPassword }` → 204. 이메일 가입 회원만(아니면 403). 지금 비밀번호가 틀리면 400(`fieldErrors[].field = currentPassword`), 새 비밀번호는 가입 규칙(`newPassword`). 지금 로그인과 다른 기기 로그인은 그대로 | AUTH-05 |
| DELETE | /api/me/social/{provider} | P | 회원 | 204. 남는 로그인 수단이 없으면 409 `LAST_LOGIN_METHOD`. 연동은 `authorize?mode=link` | OWN-03 |
| DELETE | /api/me | P | 회원 | `{ password }`(이메일 가입) 또는 `{}`(소셜 재인증 10분 안) → 204 + 쿠키 삭제. 본인 확인 실패 401 | AUTH-06 |
| GET | /api/me/blogs | P | 회원 | 내 활성 블로그 `[{ id, address, name, isPrimary, movedTo, postCount }]` | BLOG-08 |
| PUT | /api/me/primary-blog | P | 회원 | `{ blogId }` → 204. 내 활성 블로그만 | BLOG-08 |
| GET | /api/me/bookmarks?cursor= | P | 회원 | 저장한 글 20, 저장 최신순. 볼 수 있으면 `{ post: PostSummary, savedAt, visible: true }`, 볼 수 없으면 `{ postId, visible: false, titleSnapshot, blogNameSnapshot, savedAt }` | SOC-03 |
| DELETE | /api/me/bookmarks/{postId} | P | 회원 | 204. 목록에서 바로 저장 취소(볼 수 없는 글도) | SOC-03 |
| GET | /api/me/notifications?cursor= | P | 회원 | 알림 20 최신순 `[{ id, type, message, link, read, createdAt }]` | SUB-04 |
| GET | /api/me/notifications/unread-count | \* | 회원 | `{ count }`. 상단 종 표시 | SUB-04 |
| PUT | /api/me/notifications/{id}/read | P | 본인 | 204 | SUB-04 |
| PUT | /api/me/notifications/read-all | P | 회원 | 204 | SUB-04 |

알림 `type`은 `COMMENT`, `REPLY`, `LIKE`, `SUBSCRIBE`, `SANCTION`. `link`는 눌렀을 때 갈 화면 주소다(`https://jiwon.blog.com/1532#comment-88`). 대상이 지워졌거나 볼 수 없게 된 알림은 목록에서 빠진다.

### BLOG 블로그

| 메서드 | 경로 | Host | 권한 | 설명 | ID |
| --- | --- | --- | --- | --- | --- |
| GET | /api/blogs/address-availability?address= | P | 회원 | `{ available, reason }`. `reason`: `INVALID`·`RESERVED`·`TAKEN` | BLOG-01 |
| POST | /api/blogs | P | 회원 | `{ address, name, description? }` → 201 `Blog`. 6번째 409 `BLOG_LIMIT_EXCEEDED`. 첫 블로그는 대표 | BLOG-01 |
| GET | /api/blog | B | 누구나 | `Blog` | BLOG-03, SUB-03 |
| PATCH | /api/blog | B | 주인 | `{ name?, description?, profileImageId?, skin?, listLayout?, accentColor? }` → `Blog`. `skin`: 미리 만든 2~3종, `listLayout`: `LIST`·`THUMBNAIL`, `accentColor`: `BLUE`·`GREEN`·`ORANGE`·`PINK`·`PURPLE`·`GRAY` | BLOG-02, BLOG-05 |
| GET | /api/blog/sidebar | B | 누구나 | 보이는 모듈만 주인이 정한 순서로 `{ modules: [{ type, data }] }`. 아래 [사이드바 응답](#사이드바-응답) | BLOG-04, BLOG-05 |
| GET | /api/blog/sidebar/modules | B | 주인 | 모듈 8개 전부 `[{ moduleType, isVisible }]` 순서대로(숨긴 것 포함) | BLOG-05 |
| PUT | /api/blog/sidebar/modules | B | 주인 | `[{ moduleType, isVisible }]` 8개를 원하는 순서로 전체 교체 → 204. 8종이 정확히 한 번씩이 아니거나 `PROFILE`을 숨기면 400 `VALIDATION_FAILED` | BLOG-05 |
| POST | /api/blog/move-posts | B | 주인 | `{ postIds, targetBlogId }` → `{ movedCount }`. 카테고리는 미분류, 태그는 이름으로 다시 연결 | BLOG-06 |
| PUT | /api/blog/moved-to | B | 주인 | `{ targetBlogId }` → 204. 연쇄는 최종 블로그로 저장, 순환이면 400 `INVALID_MOVE_TARGET` | BLOG-06 |
| DELETE | /api/blog/moved-to | B | 주인 | 204. 이사 지정 취소 | BLOG-06 |
| GET | /api/blog/deletion-preview | B | 주인 | `{ remainingPostCount, isPrimary }`. 삭제 경고 "옮기지 않은 글 N개" | BLOG-07 |
| DELETE | /api/blog | B | 주인 | `{ confirmAddress }`(주소를 다시 입력) → 204. 대표면 409 `PRIMARY_BLOG` | BLOG-07 |

#### 사이드바 응답

```json
{
  "modules": [
    { "type": "PROFILE", "data": { "name": "지원의 기록", "description": "개발 공부 기록", "profileImageUrl": null } },
    { "type": "CATEGORY", "data": { "...": "카테고리 트리 응답과 같음" } },
    { "type": "TAG", "data": [{ "id": 1, "name": "spring", "postCount": 14 }] },
    { "type": "RECENT_POST", "data": [{ "id": 1532, "title": "..." }] },
    { "type": "RECENT_COMMENT", "data": [{ "id": 88, "postId": 1532, "content": "...", "authorNickname": "하늘", "state": "NORMAL" }] },
    { "type": "VISITOR", "data": { "today": 37, "yesterday": 52, "total": 4318 } },
    { "type": "POPULAR_POST", "data": [{ "id": 1201, "title": "...", "viewCount": 1204 }] },
    { "type": "SUBSCRIBE", "data": { "blogId": 3, "subscriberCount": 18, "subscribed": false } }
  ]
}
```

- 숨긴 모듈은 `modules`에 없다. `PROFILE`은 항상 있다. 새 블로그는 `VISITOR`·`POPULAR_POST`·`SUBSCRIBE`가 숨김으로 시작한다(BLOG-05).
- 개수는 고정이다: 최근 글·최근 댓글·인기 글 각 5개. 인기 글은 누적 조회수 순, 볼 수 있는 글만.
- 비밀댓글·숨긴 댓글은 `RECENT_COMMENT`에서 `state`만 주고 `content`는 `null`이다. 볼 수 없는 글의 댓글은 빠진다.

### POST 글

| 메서드 | 경로 | Host | 권한 | 설명 | ID |
| --- | --- | --- | --- | --- | --- |
| GET | /api/posts?page=&size=&categoryId=&tag= | B | 누구나 | 블로그 글 목록 10, 최신순. `categoryId`면 하위 카테고리 글 포함, `categoryId=0`은 미분류. 주인에게는 비공개·숨긴 글을 포함한 발행 글 전부(임시저장·예약 제외) | BLOG-03, CAT-02, TAG-02 |
| GET | /api/posts/{id} | B | 누구나 | `PostDetail`. 볼 수 없으면 404, 구독자 공개를 구독 안 한 사람이 열면 403 `SUBSCRIBERS_ONLY` | POST-04, POST-10, POST-12 |
| POST | /api/posts | B | 주인 | [글 저장 본문](#글-저장-본문) → 201 `{ id, status, url }`. `Idempotency-Key` 필수 | POST-01, POST-08, POST-13 |
| GET | /api/manage/posts/{id} | B | 주인 | 편집용. 본문 + 임시저장·예약·숨김 상태와 `blind` 사유 | POST-02, POST-08 |
| PUT | /api/posts/{id} | B | 주인 | [글 저장 본문](#글-저장-본문) → 200 `{ id, status, url }`. 숨긴 글이면 403 `POST_BLINDED`. 자동 임시저장도 이 경로 | POST-02, POST-08 |
| DELETE | /api/posts/{id} | B | 주인 | 204. 소프트 삭제, 숨긴 글도 삭제는 됨 | POST-03 |
| PATCH | /api/posts/{id}/visibility | B | 주인 | `{ visibility }` → 204 | POST-06, POST-12 |
| POST | /api/posts/{id}/views | B | 누구나 | 204(셌든 안 셌든 같음). 같은 조회자 5분 안 중복은 세지 않음. 비회원에게 `visitor_id` 쿠키가 없으면 응답에 `Set-Cookie`로 준다. 볼 수 없는 글은 상세와 같이 404·403. 주인 본인 조회도 셈 | POST-09 |
| POST | /api/images | \* | 회원 | multipart `file` → 201 `{ id, url, thumbnailUrl }`. 400 `UNSUPPORTED_IMAGE`·`IMAGE_TOO_LARGE`. 본문·프로필·블로그 이미지 공통 | POST-05, AUTH-05, BLOG-02 |
| GET | /api/topics | \* | 누구나 | 고정 주제 10개 `[{ code, name }]` | POST-11, HOME-03 |
| GET | /api/posts/{id}/same-category?size=5 | B | 누구나 | 같은 카테고리의 다른 글(볼 수 있는 글만) `PostSummary[]` | OWN-05 |
| GET | /api/posts/{id}/similar?size=5 | B | 누구나 | 비슷한 글(pgvector, 볼 수 있는 글만, 다른 블로그 포함) `PostSummary[]`. 추천이 준비 안 됐으면 빈 배열 | OWN-06 |

#### 글 저장 본문

```json
{
  "title": "Spring Security 정리",
  "contentHtml": "<p>...</p>",
  "categoryId": 11,
  "tagNames": ["spring", "security"],
  "topic": "IT_DEV",
  "visibility": "PUBLIC",
  "status": "PUBLISHED",
  "scheduledAt": null,
  "thumbnailImageId": 501,
  "commentAllowed": true
}
```

| status | 뜻 | 규칙 |
| --- | --- | --- |
| `DRAFT` | 임시저장 | 제목이 비어도 된다. 주인에게만 보인다 |
| `PUBLISHED` | 발행 | 제목 1~200자 필수. 처음 발행이면 `publishedAt`을 지금으로, 다시 저장해도 바뀌지 않는다 |
| `SCHEDULED` | 예약 발행 | `scheduledAt`(지금보다 뒤) 필수. 그 시각에 서버가 `PUBLISHED`·`PUBLIC`으로 바꾸고 그 시각이 `publishedAt` |

- `categoryId`가 `null`이면 미분류. `topic`이 `null`이면 주제 없음.
- `tagNames` 최대 10개(넘으면 400 `TOO_MANY_TAGS`). 블로그에 없는 이름은 새 태그가 된다(TAG-01). 이름은 앞뒤 공백과 앞의 `#`을 떼고 30자까지, `/`가 들어 있으면 400(`fieldErrors[].field = tagNames`). 대소문자·악센트만 다른 이름은 같은 태그다.
- `thumbnailImageId`는 본문에 들어간 이미지 중 하나. `null`이면 본문 첫 이미지(POST-07).
- `visibility`: `PUBLIC`·`PRIVATE`·`SUBSCRIBERS`. SUB-01이 생기기 전에는 `SUBSCRIBERS`를 400으로 막는다(review C-7).
- 발행한 글을 `DRAFT`로 되돌릴 수는 없다(400). 예약 글은 `DRAFT`로 되돌려 예약을 취소한다.

### CAT 카테고리 · TAG 태그

| 메서드 | 경로 | Host | 권한 | 설명 | ID |
| --- | --- | --- | --- | --- | --- |
| GET | /api/categories | B | 누구나 | 트리. 주인이 아니면 비공개 카테고리와 그 글 수는 빠짐 | CAT-01, CAT-05, BLOG-04 |
| POST | /api/categories | B | 주인 | `{ name, parentId? }` → 201 `{ id, name, parentId, sortOrder }`. 같은 자리(최상위끼리, 같은 상위의 하위끼리) 이름 중복 409 `NAME_TAKEN`, 하위의 하위 409 `CATEGORY_DEPTH`, 이 블로그 카테고리가 아닌 `parentId`는 400 | CAT-01, CAT-03 |
| PATCH | /api/categories/{id} | B | 주인 | `{ name?, isPrivate? }` → 204. `parentId`를 보내면 400(상위 바꾸기는 `PUT /api/categories/order`) | CAT-01, CAT-05 |
| DELETE | /api/categories/{id} | B | 주인 | 204. 글은 미분류로. 하위가 있으면 409 `CATEGORY_HAS_CHILDREN` | CAT-01 |
| PUT | /api/categories/order | B | 주인 | `[{ id, parentId, sortOrder }]` 전체 → 204. 드래그 앤 드롭 결과 한 번에 | CAT-04 |
| GET | /api/tags | B | 누구나 | `[{ id, name, postCount }]` 글 수순 | TAG-03 |
| PATCH | /api/tags/{id} | B | 주인 | `{ name }` → 204. 중복 409 `NAME_TAKEN` | TAG-04 |
| DELETE | /api/tags/{id} | B | 주인 | 204. 글은 남고 연결만 끊김 | TAG-04 |

카테고리 트리 응답:

```json
{
  "totalCount": 42,
  "uncategorizedCount": 3,
  "categories": [
    { "id": 10, "name": "개발", "isPrivate": false, "postCount": 30, "sortOrder": 0,
      "children": [{ "id": 11, "name": "Spring", "isPrivate": false, "postCount": 12, "sortOrder": 0, "children": [] }] }
  ]
}
```

`postCount`는 하위 글을 포함한 볼 수 있는 글 수다(CAT-02). `uncategorizedCount`가 0이면 화면에서 미분류를 숨긴다(review B-10). `isPrivate`는 주인에게만 준다.

### CMT 댓글 · 방명록

| 메서드 | 경로 | Host | 권한 | 설명 | ID |
| --- | --- | --- | --- | --- | --- |
| GET | /api/posts/{id}/comments?cursor= | B | 누구나 | `Comment` 20 작성순, 답글은 부모 안에. `+ totalCount` | CMT-01, CMT-05, CMT-06 |
| POST | /api/posts/{id}/comments | B | 회원 | `{ content, parentId?, secret }` → 201 `Comment`. `Idempotency-Key` 필수. 차단 403 `BLOCKED_BY_BLOG`, 금칙어 400 `BANNED_WORD`, 댓글 막힘 403 `COMMENTS_DISABLED`, 답글의 답글 400 | CMT-01, CMT-05, CMT-06, CMT-07, MNG-04 |
| PATCH | /api/comments/{id} | B | 본인 | `{ content }` → `Comment`. 숨긴 댓글은 403 | CMT-03 |
| DELETE | /api/comments/{id} | B | 본인·주인 | 204. 답글이 있으면 자리만 남김 | CMT-01, CMT-02 |
| GET | /api/guestbook?page= | B | 누구나 | `Comment` 페이지 20 최신순, 답글은 부모 안에 | CMT-04 |
| POST | /api/guestbook | B | 회원 | `{ content, parentId?, secret }` → 201. `Idempotency-Key`, 차단·금칙어는 댓글과 같음 | CMT-04, MNG-04 |
| PATCH | /api/guestbook/{id} | B | 본인 | `{ content }` → `Comment` | CMT-04 |
| DELETE | /api/guestbook/{id} | B | 본인·주인 | 204 | CMT-04 |

### SOC 반응

| 메서드 | 경로 | Host | 권한 | 설명 | ID |
| --- | --- | --- | --- | --- | --- |
| PUT | /api/posts/{id}/like | B | 회원 | → `{ liked: true, likeCount }` | SOC-01 |
| DELETE | /api/posts/{id}/like | B | 회원 | → `{ liked: false, likeCount }` | SOC-01 |
| PUT | /api/posts/{id}/bookmark | B | 회원 | → `{ bookmarked: true }`. 저장 시점 제목·블로그 이름을 남김 | SOC-03 |
| DELETE | /api/posts/{id}/bookmark | B | 회원 | → `{ bookmarked: false }` | SOC-03 |

공유(SOC-02)는 API가 없다. 화면이 글 주소를 복사하거나 SNS 공유 주소를 열고, 미리보기는 [화면 주소 단계](#화면-주소-단계에서-서버가-하는-일-api-없음)의 메타 태그가 맡는다.

### SUB 구독 · 피드

| 메서드 | 경로 | Host | 권한 | 설명 | ID |
| --- | --- | --- | --- | --- | --- |
| PUT | /api/blogs/{blogId}/subscription | \* | 회원 | → `{ subscribed: true, subscriberCount }`. 차단된 회원 403 `BLOCKED_BY_BLOG`, 자기 블로그 400 | SUB-01, SUB-03, MNG-04 |
| DELETE | /api/blogs/{blogId}/subscription | \* | 회원 | → `{ subscribed: false, subscriberCount }` | SUB-01 |
| GET | /api/feed?cursor= | P | 회원 | 구독한 블로그의 새 글 `PostSummary` 20 최신순 | SUB-02 |
| GET | /api/recommend/blogs | P | 누구나 | 추천 블로그 5 `[{ blog, owner, subscriberCount, recentPostTitle }]`. 비회원은 인기 블로거와 같음 | SUB-06 |

### SRCH 검색 · HOME 홈

| 메서드 | 경로 | Host | 권한 | 설명 | ID |
| --- | --- | --- | --- | --- | --- |
| GET | /api/search?q=&page= | B | 누구나 | 블로그 안 제목·본문·태그 검색 `PostSummary` 10 최신순 | SRCH-01 |
| GET | /api/search?q=&type=post&page= | P | 누구나 | 전체 글 검색 `PostSummary` 10 | SRCH-02 |
| GET | /api/search?q=&type=blog&page= | P | 누구나 | 블로그 이름·소개 검색 `[{ blog, owner, subscriberCount }]` 10 | SRCH-02 |
| GET | /api/home/latest?cursor= | P | 누구나 | 모든 블로그 공개 글 `PostSummary` 20 최신순 | HOME-01 |
| GET | /api/home/popular | P | 누구나 | 인기 점수 상위 10 `{ snapshotAt, items: [{ rank, post }] }`. 5분 스냅숏 | HOME-02 |
| GET | /api/home/topics/{topic} | P | 누구나 | 주제별 `PostSummary[]` 6. 인기 점수 순(주제마다 5분 캐시), 모자라면 그 주제의 최신 글. `topic`은 주제 code(`IT_DEV` 등), 모르는 값은 404 | HOME-03 |
| GET | /api/home/bloggers | P | 누구나 | 인기 블로거 상위 5 `{ snapshotAt, items: [{ rank, blog, owner }] }`. 1시간 스냅숏 | HOME-04 |
| GET | /api/ranking/posts?snapshotAt=&offset= | P | 누구나 | 인기 글 100위까지 20개씩. 처음엔 `snapshotAt` 없이. 스냅숏이 바뀌었으면 409 `RANKING_UPDATED` | HOME-05 |
| GET | /api/ranking/bloggers?snapshotAt=&offset= | P | 누구나 | 인기 블로거 100위까지 20개씩. 같은 규칙 | HOME-05 |
| GET | /api/notices?page= | P | 누구나 | 공지 목록 10 최신순 `[{ id, title, createdAt }]` | ADMIN-06 |
| GET | /api/notices/latest | P | 누구나 | 홈 상단 최신 공지 1개 또는 `null` | ADMIN-06 |
| GET | /api/notices/{id} | P | 누구나 | `{ id, title, content, createdAt, updatedAt }` | ADMIN-06 |

### MNG 블로그 관리

모두 **B**, **주인**만. 블로그 관리 화면(`{address}.blog.com/manage/...`)이 부른다.

| 메서드 | 경로 | 설명 | ID |
| --- | --- | --- | --- |
| GET | /api/manage/posts?status=&visibility=&categoryId=&q=&page= | 내 글 20 최신순(임시저장은 수정 시각순). `categoryId`는 하위 포함, `0`은 미분류. `q`는 제목만 찾는다. 숨긴 글은 `blinded: true`와 `blind` 사유 | MNG-01, POST-08, ADMIN-03 |
| PATCH | /api/manage/posts | `{ postIds, visibility }` → `{ updatedCount }` 일괄 공개 범위. `postIds` 1~100개. 이 블로그의 지우지 않은 글만 바꾸고 남의 글·지운 글·없는 번호는 건너뛴다(수에서 빠짐). 한 트랜잭션 | MNG-01 |
| DELETE | /api/manage/posts | `{ postIds }` → `{ deletedCount }` 일괄 삭제(글 하나 삭제와 같은 처리). `postIds` 1~100개, 건너뛰는 규칙은 위와 같음 | MNG-01 |
| GET | /api/manage/comments?type=comment\|guestbook&page= | 받은 댓글·방명록 20 최신순 `[{ ...Comment, post: { id, title } \| null }]` | MNG-02 |
| GET | /api/manage/stats | 관리 홈 `{ today, yesterday, total, recentComments[5], recentPosts[5] }` | MNG-03 |
| GET | /api/manage/stats/visitors?unit=day\|week\|month&from=&to= | `[{ date, visitorCount, viewCount }]`. 주·월은 일별 합 | MNG-03 |
| GET | /api/manage/stats/popular-posts?range=all\|7d | `[{ rank, post, viewCount }]` 10 | MNG-03 |
| GET | /api/manage/stats/referrers?from=&to= | `{ byType: [{ type, count }], bySite: [{ type, host, count }] }` | MNG-03 |
| GET | /api/manage/blocked-members?page= | `[{ member: MemberSummary, memo, blockedAt }]` 20 | MNG-04 |
| POST | /api/manage/blocked-members | `{ memberId, memo? }` → 201. 그 회원의 이 블로그 구독을 지움. 중복 409 `ALREADY_BLOCKED` | MNG-04 |
| DELETE | /api/manage/blocked-members/{memberId} | 204 | MNG-04 |
| GET | /api/manage/banned-words | `[{ id, word }]` 전체 | MNG-04 |
| POST | /api/manage/banned-words | `{ word }`(1~30자) → 201. 중복 409 `NAME_TAKEN`, 100개 초과 409 `BANNED_WORD_LIMIT` | MNG-04 |
| DELETE | /api/manage/banned-words/{id} | 204 | MNG-04 |

- 관리 홈의 `today`는 오늘 지금까지의 방문자(`blog_visit` 실시간), `yesterday`는 `blog_daily_stat`, `total`은 `blog.total_visitor_count + today`.
- 차단할 회원은 MNG-02 댓글 목록이나 글 댓글의 작성자에서 고른다(`memberId`).
- 이사 대상 블로그를 고를 때는 `GET /api/me/blogs`를 쓴다.

### REPORT 신고

| 메서드 | 경로 | Host | 권한 | 설명 | ID |
| --- | --- | --- | --- | --- | --- |
| POST | /api/reports | \* | 회원 | `{ targetType, targetId, reason, description? }` → 201. `targetType`: `POST`·`COMMENT`·`BLOG`. 같은 대상 다시 신고 409 `ALREADY_REPORTED`, 볼 수 없는 대상 404 | ADMIN-04 |

### ADMIN 서비스 관리

모두 **P**, **관리자**만(`/api/admin/**` hasRole ADMIN, 아니면 403).

| 메서드 | 경로 | 설명 | ID |
| --- | --- | --- | --- |
| GET | /api/admin/dashboard | `{ todaySignups, todayPosts, pendingReports, recentModerations[5] }` | ADMIN-06 |
| GET | /api/admin/members?q=&status=&page= | 이메일·닉네임 검색, 상태 필터. 20 | ADMIN-02 |
| GET | /api/admin/members/{id} | `{ member, createdAt, blogs[], reportCount, moderations[] }` | ADMIN-02 |
| POST | /api/admin/members/{id}/suspension | `{ period: 7D\|30D\|PERMANENT, reason, reasonDetail? }` → 204. 그 회원의 모든 블로그를 숨기고 알림 | ADMIN-02, SUB-04 |
| DELETE | /api/admin/members/{id}/suspension | 204. 해제 이력 남김 | ADMIN-02 |
| POST | /api/admin/posts/{id}/blind | `{ reason, reasonDetail? }` → 204 | ADMIN-03 |
| DELETE | /api/admin/posts/{id}/blind | 204 | ADMIN-03 |
| POST | /api/admin/comments/{id}/blind | `{ reason, reasonDetail? }` → 204 | ADMIN-03 |
| DELETE | /api/admin/comments/{id}/blind | 204 | ADMIN-03 |
| POST | /api/admin/blogs/{id}/restriction | `{ reason, reasonDetail? }` → 204 | ADMIN-05 |
| DELETE | /api/admin/blogs/{id}/restriction | 204 | ADMIN-05 |
| GET | /api/admin/reports?status=PENDING&page= | 대상별 묶음, 신고 수 많은 순 `[{ targetType, targetId, targetPreview, reportCount, reasons: { SPAM: 3 }, firstReportedAt }]` | ADMIN-04 |
| GET | /api/admin/reports/{targetType}/{targetId} | 그 대상의 신고 목록 `[{ reporter, reason, description, createdAt }]` | ADMIN-04 |
| POST | /api/admin/reports/{targetType}/{targetId}/resolve | `{ result: BLIND\|RESTRICT_BLOG\|SUSPEND\|REJECT, reason?, reasonDetail?, period? }` → 204. 대상의 대기 신고 모두 처리 완료, 관리 이력 남김. `SUSPEND`는 작성자 정지(`period` 필수) | ADMIN-04 |
| GET | /api/admin/moderation-logs?targetType=&targetId=&adminId=&from=&to=&page= | 조회만 20 최신순. 수정·삭제 API 없음 | ADMIN-06 |
| POST | /api/admin/notices | `{ title, content }` → 201 | ADMIN-06 |
| PUT | /api/admin/notices/{id} | `{ title, content }` → 204 | ADMIN-06 |
| DELETE | /api/admin/notices/{id} | 204 | ADMIN-06 |

- 제재 대상이 받는 알림(`SANCTION`)과 화면 안내는 `reasonMessage`로 정해진 문구를 쓴다.
- 관리자는 남의 글·댓글을 고치거나 지우는 API가 없다(헌법 원칙 V).

## 화면 주소 단계에서 서버가 하는 일 (API 없음)

`/api/`로 시작하지 않는 요청은 서버가 아래를 처리한 뒤 React 앱(`index.html`)을 준다(원본 6장 ①, 작업 T010).

| 일 | 규칙 | ID |
| --- | --- | --- |
| 블로그 확인 | 없거나 볼 수 없는 블로그 404 화면. 이사한 블로그는 새 블로그 같은 경로로 301 (주인의 `/manage/**`는 예외). 이사 간 블로그가 삭제됐으면 404. 글 주소 `/{id}`는 아래 글 확인이 먼저다 | BLOG-06, COM-01 |
| 글 확인 | `/{id}`가 다른 블로그 소속이고 볼 수 있으면 지금 블로그로 301, 아니면 404 화면. 이사한 블로그에 남은(옮기지 않은) 글은 옛 주소에서 그대로 보인다(블로그 301을 먼저 하면 옛 주소↔새 주소 무한 리다이렉트, 2026-10-08 지원 확인) | POST-04, SC-005 |
| 방문 기록 | 블로그 주소의 화면 요청마다 `blog_visit`에 블로그·날짜·방문자 하나를 남긴다. 유입 종류·호스트는 `Referer`로 정하고, 주인 본인은 세지 않는다 | MNG-03 |
| 공유 미리보기 | 글 주소면 `index.html`에 `og:title`·`og:description`(요약)·`og:image`(대표 이미지)를 넣는다. 볼 수 없는 글이면 넣지 않는다 | SOC-02 |

## 화면별 API

어느 화면이 어느 API를 부르는지는 [화면 목업](../mockups/README.md)의 화면 목록에 있다. 목업 각 화면 아래에도 그 화면이 부르는 API를 적었다.

## 이 문서에서 채운 값

기능 명세나 ERD에 없어서 API를 정리하며 Claude가 정한 값이다. [지원이 확인할 것](../review.md) B-23에도 올렸다.

| 항목 | 정한 값 | 다른 선택지 |
| --- | --- | --- |
| 이메일 인증 코드 | 6자리 숫자, 10분 유효. 같은 이메일로 1분 안에 다시 보내면 429 | 다른 길이·시간 |
| 재설정 메일 다시 보내기 | 1분 안에 다시 요청하면 429. 가입 안 된 이메일도 같은 응답 | 가입 안 된 이메일이면 알려 주기 |
| 페이지 번호 | 1부터. page가 1보다 작거나 size가 1~50 밖이면 400 (지원 확인 2026-10-08) | 0부터(Spring 기본), 범위 밖은 보정 |
| 잘못된 요청 방식 | 405 `METHOD_NOT_ALLOWED` (지원 확인 2026-10-08) | 404 |
| CSRF 대책 | `X-Requested-With` 헤더 확인 | CSRF 토큰 |
| 임시저장 제목 | 비어도 저장 | 임시저장에도 제목 필수 |
| 발행 글 되돌리기 | 발행한 글은 임시저장으로 못 돌림(비공개로 바꾸면 됨) | 되돌리기 허용 |
| 댓글 막은 글에 댓글 | 403 `COMMENTS_DISABLED` | 400 |
| 블로그 삭제 확인 | 주소를 다시 입력해야 삭제 | 확인 창만 |
| 소셜 가입 토큰·재인증 | 각 10분 유효 | 다른 시간 |
| 공지 수정·삭제 | 관리자가 자기 공지를 고치고 지울 수 있음 | 작성만 |
| 같은 카테고리·비슷한 글 개수 | 각 5개 | 다른 개수 |
| 내 정보 경로 | `/api/me/**`로 통일 | `/api/members/me/**` |
| 비회원 조회자 식별 | 서버가 주는 `visitor_id` 쿠키(UUID, 1년, 모든 블로그 주소 공통). 키는 회원 `m:{id}`, 비회원 `a:{uuid}` (지원 확인 2026-10-09) | IP 주소, 브라우저 지문 |
| 주인 본인 조회 | 조회수에 셈 (지원 확인 2026-10-09) | 빼기 |
| 비밀번호 변경의 지금 비밀번호 틀림 | 400 `VALIDATION_FAILED`, 칸 `currentPassword` (지원 확인 2026-10-09) | 새 오류 코드, 401 |
| 프로필 사진 이미지 | 본인이 올린 이미지만, 응답은 썸네일 주소 (지원 확인 2026-10-09) | 아무 이미지 |
| 비밀번호 변경 뒤 다른 기기 | 로그인 유지 (지원 확인 2026-10-09) | 모두 로그아웃 |
| 남의 블로그 상위 카테고리·이름 변경의 `parentId` | 400 (지원 확인 2026-10-09) | 404, 무시 |
| 모르는 주제 주소 | 404 (지원 확인 2026-10-09) | 400 |
| 내 글 관리 검색·일괄 처리 | 검색은 제목만. 일괄 처리는 내 글만 처리하고 나머지는 건너뛰어 수로 알림, 100개까지 (지원 확인 2026-10-09) | 본문까지 검색, 하나라도 틀리면 전체 거절 |
