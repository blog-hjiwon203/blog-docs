# 스텝 4. 가입과 블로그 개설

> 작업: T017, T018, T019, T020, T022, T023, T024, T025, T026, T027 · 코드 브랜치: `step-4-signup-blog` · 날짜: 2026-10-08

## 한눈에 보기

처음으로 **사람이 쓸 수 있는 화면**이 생겼다. 이메일 인증 → 가입 → 블로그 개설 → 블로그 메인과 사이드바 → 로그아웃까지 한 바퀴가 돈다(quickstart "P0 한 바퀴" 1~2).

| 기능 | API | 핵심 파일 |
| --- | --- | --- |
| 이메일 인증 (OWN-01) | `POST /api/auth/email-verifications`, `.../verify` | `auth/application/EmailVerificationService`, `EmailSender`, `LoggingEmailSender` |
| 가입·로그인·로그아웃 (AUTH-01·02) | `POST /api/auth/signup`, `/login`, `/logout`, `GET /api/auth/nickname-availability` | `auth/application/AuthService`, `auth/domain/PasswordRule`, `global/auth/SuspensionDetails` |
| 내 정보 | `GET /api/me` | `member/application/MeService`, `member/presentation/dto/MeResponse` |
| 블로그 개설 (BLOG-01) | `GET /api/blogs/address-availability`, `POST /api/blogs` | `blog/application/BlogService`, `MemberRepository.findByIdForUpdate` |
| 블로그 정보 (BLOG-02·03) | `GET /api/blog`, `PATCH /api/blog` | `blog/application/BlogQueryService`, `global/web/RequestValidator` |
| 블로그 메인 글 목록 (BLOG-03) | `GET /api/posts?page=&categoryId=` | `post/application/PostQueryService`, `PostRepository`(EntityGraph) |
| 사이드바 (BLOG-04) | `GET /api/blog/sidebar` | `blog/application/SidebarService`, `category/application/CategoryTreeService`, `PostCountRepositoryImpl` |
| 화면 | `/signup`, `/login`, `/blogs/new`, `{주소}/`, `{주소}/category/{id}`, `{주소}/manage`, `{주소}/manage/settings` | `frontend/src/pages/**`, `components/**`, `app/useMe.ts`, `app/useBlog.ts` |

스텝 3에서 만든 장치(로그인 쿠키, `@CurrentBlog`, `PostSpecifications`, `BlogOwnerGuard`)를 실제 API가 처음으로 쓴다.

## 요청 흐름

### 가입에서 내 블로그까지

```
blog.test/signup (React)
 ① 코드 받기  POST /api/auth/email-verifications {email}
      EmailVerificationService.send
        ├ 이미 가입한 이메일? → 409 EMAIL_TAKEN
        ├ Redis SET NX email-verification:cooldown:{email} (1분) 실패 → 429 + retryAfterSeconds
        ├ 6자리 코드(SecureRandom) → email_verification 행 (10분 유효)
        └ LoggingEmailSender: 서버 로그 "[개발용 메일] ... 인증 코드: 482913"
 ② 확인      POST .../verify {email, code}  → 200 (코드를 쓰지 않음, 화면 표시용)
 ③ 가입      POST /api/auth/signup {email, code, password, nickname}
      AuthService.signup  ── 트랜잭션 하나 ──────────────────────────────┐
        ├ PasswordRule(8자+영문+숫자, 72바이트 이하) → 400               │
        ├ 이메일·닉네임 중복 → 409                                        │
        ├ EmailVerificationService.consume → verified_at 기록(같은 트랜잭션) │
        └ member 저장 (UNIQUE 위반이면 409)                               │
      ────────────────────────────────────────────────────────────────┘
      AuthCookieManager.login → Set-Cookie access_token, refresh_token (Domain=.blog.test)
      → 201 Me → 화면이 /blogs/new로
 ④ 개설      POST /api/blogs {address, name, description}
      BlogService.open  ── 트랜잭션 ──
        ├ SELECT ... FROM member WHERE id=? FOR UPDATE   (같은 회원의 개설을 한 줄로)
        ├ 주소 규칙·예약어 → 400 BLOG_ADDRESS_INVALID
        ├ 활성 블로그 5개 → 409 BLOG_LIMIT_EXCEEDED
        ├ 주소 쓰였나(삭제된 블로그 포함) → 409 BLOG_ADDRESS_TAKEN
        └ 저장 (활성 블로그가 없으면 대표)
      → 201 Blog → 화면이 alpha.blog.test/manage로 (다른 호스트라 페이지를 새로 연다)
```

### 블로그 메인 한 화면

`alpha.blog.test:8080/`을 열면 서버가 `SpaForwardController`로 블로그를 확인하고 `index.html`을 준다(스텝 3). React가 뜬 뒤 API 네 개를 부른다.

```
GET /api/me            로그인 상태 (쿠키가 .blog.test라 플랫폼에서 로그인했어도 여기서 보인다)
GET /api/blog          @CurrentBlog → BlogQueryService.detail → 이름, 주인, 볼 수 있는 글 수, viewer.isOwner
GET /api/blog/sidebar  SidebarService → 카테고리 트리·글 수, 최근 글 5, 최근 댓글 5
GET /api/posts?page=1  PostQueryService.blogPosts → PostSpecifications.listedIn + 최신순 10개
```

목록·개수·사이드바가 모두 **같은 가시성 조건 `PostSpecifications.listedIn`**을 쓴다. 비회원에게는 볼 수 있는 글만, 주인에게는 비공개·숨긴 글을 포함한 발행 글 전부다(임시저장·예약 글은 주인에게도 블로그 화면에 나오지 않는다).

## 이 스텝을 이해하려면 (읽는 순서)

| 순서 | 개념 문서 | 이 스텝에서 그 개념이 쓰인 곳 |
| --- | --- | --- |
| 1 | [20 이메일 인증 코드와 요청 제한](./concepts/20-email-verification.md) | `EmailVerificationService`, Redis 1분 제한, `EmailSender` 인터페이스 |
| 2 | [21 가입·로그인·로그아웃 설계](./concepts/21-signup-login.md) | `AuthService`, 실패 문구 통일, 타이밍, 정지 안내 순서, 로그아웃, `safeRedirect` |
| 3 | [09 비밀번호 해시와 bcrypt](./concepts/09-password-hashing.md)의 스텝 4 부분 | `PasswordRule`의 72바이트 제한 |
| 4 | [22 입력 검증과 JSON 바인딩](./concepts/22-bean-validation.md) | `@Valid`, `@RequestParam` 제약, `RequestValidator`, Jackson 3의 `boolean` 누락 오류 |
| 5 | [23 트랜잭션과 동시성](./concepts/23-transactions-locking.md) | 가입 트랜잭션, `findByIdForUpdate`, UNIQUE와 `DataIntegrityViolationException`, 동시 개설 테스트 |
| 6 | [24 계층 구조와 DTO](./concepts/24-layered-architecture-dto.md) | `application` 결과(`BlogDetail`, `Sidebar`) → `presentation` 응답, `open-in-view: false` |
| 7 | [06 JPA 엔티티 매핑](./concepts/06-jpa-entity-mapping.md)의 스텝 4 부분 | `@EntityGraph`, 리포지토리 조각(`PostCountRepositoryImpl`), `findBy(...).limit(5)` |
| 8 | [16 인가와 가시성 판단](./concepts/16-authorization-visibility.md)의 스텝 4 부분 | `listedIn`, 사이드바 댓글의 가시성, 403이 400보다 먼저 |
| 9 | [08 페이지네이션](./concepts/08-pagination.md)의 스텝 4 부분 | 블로그 메인 10개씩, 페이지 번호 10개 묶음 |
| 10 | [12 Spring Security 필터 체인](./concepts/12-spring-security-filter-chain.md)의 스텝 4 부분 | `SuspensionDetails`, `@PreAuthorize("isAuthenticated()")` |
| 11 | [25 React 폼과 데이터 불러오기](./concepts/25-react-forms-data.md) | 가입·개설·설정 폼, `useMe`·`useBlog`, 중첩 라우트 |
| 12 | [19 React Router와 API 클라이언트](./concepts/19-react-router-api-client.md)의 스텝 4 부분 | 본문 없는 2xx 처리, 새 라우트 |

## 막혔던 점

- **로그인 요청에 `rememberMe`를 빼면 400**: 통합 테스트는 늘 `rememberMe`를 보내서 통과했는데, 서버를 띄워 curl로 한 바퀴 돌릴 때 드러났다. Jackson 3은 본문에 없는 `boolean` 같은 기본형 칸을 오류로 본다. `Boolean`으로 바꾸고 "생략하면 유지 안 함"으로 처리했다([22](./concepts/22-bean-validation.md)). 테스트가 보내는 요청 모양만 확인하면 놓친다는 예다.
- **주인이 아닌 사람이 잘못된 본문을 보내면 403이 아니라 400**: `@Valid`는 컨트롤러 메서드에 들어오기 전에 검증해서 주인 검사보다 먼저 실패한다. 상태 코드 순서(404 → 401 → 403 → 400)를 지키려고 본문 검증을 주인 검사 뒤로 옮겼다(`RequestValidator`).
- **macOS에서 `Pagination.tsx`와 `pagination.ts`가 부딪힘**: 파일 시스템이 대소문자를 구분하지 않아 TypeScript가 같은 파일로 본다(TS1149). 도우미를 `pageGroup.ts`로 바꿨다.
- **예약어 테스트가 실패**: `www`, `api`는 3자라 예약어 검사 전에 길이 규칙(4~32자)에서 `INVALID`가 된다. 코드가 맞고 테스트 기대가 틀렸다. 4자 이상 예약어로 바꿨다.
- **카테고리 화면에서 글 한 줄이 세로로 늘어남**: `.cols` 그리드 칸이 사이드바 높이만큼 늘어나고, 안의 `.stack` 그리드가 행을 늘렸다. `align-items: start`, `align-content: start`로 고쳤다. 헤드리스 Chrome 스크린샷으로 찾았다.
- **컨트롤러가 리포지토리를 직접 부름**: 개설 응답을 만들려고 컨트롤러에서 `BlogRepository`를 불렀다가, presentation → application → domain 규칙에 어긋나 서비스가 돌려준 엔티티를 쓰도록 고쳤다([24](./concepts/24-layered-architecture-dto.md)).

## 명세와 다르거나 아직 채우지 않은 것

| 항목 | 지금 | 이유 |
| --- | --- | --- |
| 사이드바 모듈 | PROFILE, CATEGORY, RECENT_POST, RECENT_COMMENT를 고정 순서로 | 태그(TAG)는 스텝 7, 모듈 순서·표시 설정과 `blog_sidebar_module` 행 만들기는 백로그 T086 |
| 블로그 수정 `PATCH /api/blog` | 이름·소개만 | 프로필 이미지는 스텝 7, 스킨·목록 형태·포인트 색은 백로그(BLOG-05) |
| `profileImageUrl`, `socialAccounts`, `unreadNotificationCount` | `null`, `[]`, `0` | 이미지(스텝 7), 소셜·알림(백로그) |
| 블로그 화면에서 주인이 보는 글 | 발행 글 전부(비공개·숨김 포함), 임시저장·예약 제외 | data-model "주인은 ④를 건너뛴다"를 블로그 화면에 맞게 좁힘 — **지원 확인 필요** |
| 비밀번호 최대 길이 | 72바이트(bcrypt 한도) | 스텝 3에서 "지원이 정함"으로 남긴 항목 — **지원 확인 필요** |
| 로그인 화면의 "로그인 상태 유지" | 체크박스 있음(기본 꺼짐) | API가 스텝 3부터 지원. 목업 login에 있음 |

## 남은 문제

| 문제 | 영향 | 언제 | 자세히 |
| --- | --- | --- | --- |
| 이메일 인증 코드 확인에 시도 횟수 제한이 없다. 6자리라 10분 안에 많이 시도하면 맞힐 수 있다 | 남의 이메일로 가입 | 메일 실제 발송 전 | [20](./concepts/20-email-verification.md) |
| 비공개 카테고리(CAT-05)의 글도 주인이 아닌 사람의 `totalCount`(전체 글 수)에는 들어간다 | 지금은 비공개로 바꾸는 기능이 없어 영향 없음 | CAT-05 | [16](./concepts/16-authorization-visibility.md) |
| 사이드바 최근 댓글의 작성자 닉네임을 댓글마다 따로 읽는다(최대 5번) | 쿼리 몇 개 | 성능 정리 때 | [06](./concepts/06-jpa-entity-mapping.md) |
| 스텝 3에서 남긴 `crypto.randomUUID()`(HTTP 개발 주소에서 없음) | 글 발행 연타 방지 키 | 스텝 5 전 | [19](./concepts/19-react-router-api-client.md) |

스텝 3의 남은 문제 중 "본문 없는 202 처리"와 "bcrypt 72바이트"는 이 스텝에서 고쳤다.

## 직접 해 보기

```bash
./mvnw test -Dtest='EmailVerificationIntegrationTest,SignupIntegrationTest,LoginIntegrationTest,LogoutIntegrationTest'
./mvnw test -Dtest='BlogCreateIntegrationTest,BlogInfoIntegrationTest,BlogPostListIntegrationTest,SidebarIntegrationTest'
cd frontend && npm test
```

서버를 띄워 한 바퀴(브라우저 없이). `--resolve`가 `/etc/hosts` 대신 이름을 127.0.0.1로 돌린다.

```bash
docker compose up -d && ./mvnw spring-boot:run      # 다른 터미널에서
R="--resolve blog.test:8080:127.0.0.1 --resolve myblog.blog.test:8080:127.0.0.1"
H='-H X-Requested-With:XMLHttpRequest -H Content-Type:application/json'
curl -s $R $H -X POST blog.test:8080/api/auth/email-verifications -d '{"email":"me@example.com"}' -w '%{http_code}\n'
# 서버 로그에서 "[개발용 메일]"의 인증 코드를 찾는다
curl -s $R $H -c jar -X POST blog.test:8080/api/auth/signup \
  -d '{"email":"me@example.com","code":"123456","password":"password1","nickname":"나"}'
curl -s $R $H -b jar -X POST blog.test:8080/api/blogs -d '{"address":"myblog","name":"내 블로그"}'
curl -s $R -b jar myblog.blog.test:8080/api/blog          # 같은 쿠키로 블로그 주소에서 viewer.isOwner: true
curl -s $R myblog.blog.test:8080/api/blog/sidebar
docker exec blog-redis redis-cli --scan --pattern 'auth:*'   # 로그인 토큰 키
docker exec blog-redis redis-cli --scan --pattern 'email-verification:*'
```

zsh에서는 `$R`이 한 덩어리로 넘어가므로 bash에서 치거나 옵션을 직접 쓴다.

브라우저로 보려면 `/etc/hosts`에 `127.0.0.1 blog.test myblog.blog.test`를 넣고 `http://blog.test:8080/signup`을 연다. hosts를 바꾸기 싫으면 Chrome을 `--host-resolver-rules="MAP blog.test 127.0.0.1, MAP *.blog.test 127.0.0.1"`로 띄운다.

## 더 공부할 거리

- 계정 열거(account enumeration)와 타이밍 공격, OWASP Authentication Cheat Sheet
- 메일 발송: Spring `JavaMailSender`, 발송을 트랜잭션 뒤로 미루기(`@TransactionalEventListener`)
- 트랜잭션 격리 수준과 MySQL InnoDB의 잠금(레코드 락, 갭 락), 데드락
- 낙관적 잠금(`@Version`)과 비관적 잠금의 선택 기준
- Jackson 3에서 바뀐 기본 설정
- React의 `useEffect` 정리 함수, 데이터 불러오기 라이브러리(TanStack Query)
