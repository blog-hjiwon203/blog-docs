# 스텝 3. 로그인·주소·권한 판단 장치

> 작업: T007, T008, T009, T010, T011, T050, T015, T016 · 코드 PR: [#3](https://github.com/AIP-1/blog-basic-AIGJ_01_017-blog/pull/3) · 날짜: 2026-10-08

## 한눈에 보기

화면은 없고, 앞으로 모든 기능이 거쳐 갈 **판단 장치 네 가지**를 만들었다.

| 장치 | 묻는 것 | 핵심 파일 |
| --- | --- | --- |
| 로그인 | 이 요청을 보낸 사람이 누구인가, 정지·탈퇴했나 | `global/auth/JwtAuthenticationFilter`, `JwtTokenProvider`, `AuthCookieManager`, `TokenStore` |
| 주소 해석 | `alpha.blog.test`는 어느 블로그인가 | `global/host/BlogHostResolver`, `@CurrentBlog` |
| 가시성 | 이 사람이 이 글을 볼 수 있나 | `global/visibility/PostVisibilityPolicy`, `PostSpecifications` |
| 연타 방지 | 같은 요청이 두 번 왔나 | `global/web/IdempotencyInterceptor` |

그리고 화면 주소를 처리하는 `SpaForwardController`, 프론트의 라우터와 API 클라이언트(`frontend/src/app`, `frontend/src/api`)를 만들었다.

## 요청 하나가 지나가는 길

로그인한 사용자가 브라우저에서 `http://alpha.blog.test:8080/15`를 연다.

```
브라우저 ── Cookie: access_token=..., refresh_token=...
   │
   ▼  Spring Security 필터 체인 (SecurityConfig, 서블릿 필터 순서 -100이라 가장 먼저)
① CsrfHeaderFilter                   GET이라 통과 (POST·PUT·DELETE의 /api/는 X-Requested-With 확인)
② JwtAuthenticationFilter            access_token 검증 → 회원 조회 → 정지·탈퇴 확인
   │                                 → SecurityContext에 LoginMember(id, role) 저장
③ AuthorizationFilter                /api/admin/**만 ADMIN 확인, 나머지 통과
   │
   ▼  @Component로 등록한 일반 서블릿 필터 (보안 체인 다음)
④ ContentSecurityPolicyFilter        응답에 CSP 헤더를 붙인다
   ResponseCachingFilter             POST API만 응답 본문을 잡아 둔다(연타 방지용)
   │
   ▼  DispatcherServlet
⑤ SpaForwardController.page()        /api/가 아니고 확장자도 없으니 여기로
   ├─ BlogHostResolver               Host "alpha.blog.test" → 주소 "alpha" → blog 행
   ├─ /15는 글 주소 → PostVisibilityPolicy.decide(15, alpha 블로그, 로그인한 회원 id)
   │     ① 글·블로그가 삭제됐나  ② alpha 소속인가  ③ 주인인가  ④ 남이 볼 수 있나
   └─ 결과에 따라: 볼 수 있음 → 200 index.html / 다른 블로그 글 → 301 / 못 봄 → 404 index.html
   │
   ▼
브라우저가 React 앱을 띄우고, React가 /api/... 로 글 내용을 다시 요청한다
```

## 개념

### 1. JWT와 쿠키

**JWT(JSON Web Token)**는 `헤더.내용.서명` 세 부분을 점으로 이은 문자열이다. 내용(회원 id, 역할, 만료 시각)은 누구나 읽을 수 있지만, **서명은 서버의 비밀 키로만** 만들 수 있다. 그래서 서버는 DB를 보지 않고도 "내가 발급한 토큰이고 위조되지 않았다"를 확인할 수 있다.

| 토큰 | 수명 | 하는 일 |
| --- | --- | --- |
| Access | 30분 | 요청마다 "누구인가"를 증명 |
| Refresh | 로그인 유지 14일 / 아니면 무활동 30분 | Access가 끝나면 새 Access를 받는 데 씀 |

- 짧은 Access + 긴 Refresh로 나누는 이유: Access가 털려도 30분이면 끝난다. Refresh는 Redis에 살아 있는 것만 기록해서 로그아웃하면 즉시 무효로 만들 수 있다.
- 로그아웃한 Access 토큰은 만료 때까지 Redis에 "막힌 토큰"으로 둔다(`TokenStore.blockAccess`).
- 라이브러리는 **Nimbus**(`spring-security-oauth2-jose`)를 썼다. Spring Security가 버전을 관리하고, 많이 쓰는 jjwt는 Jackson 2를 끌고 와서 Boot 4의 Jackson 3과 섞이기 때문이다.

**쿠키에 넣는 이유(Q6, R-03)**: 토큰을 `localStorage`에 두면 `blog.test`와 `alpha.blog.test`가 서로 다른 저장소라 로그인이 공유되지 않는다. 쿠키는 `Domain=.blog.test`로 주면 모든 하위 주소가 함께 받는다.

쿠키 속성:

| 속성 | 뜻 | 막는 것 |
| --- | --- | --- |
| `HttpOnly` | 자바스크립트로 읽을 수 없음 | XSS로 토큰 훔치기 |
| `Secure` | HTTPS에서만 보냄(개발은 http라 끔) | 네트워크 엿보기 |
| `SameSite=Lax` | 다른 사이트에서 오는 POST에는 안 보냄 | CSRF 대부분 |
| `Domain=.blog.test` | 모든 블로그 주소에서 보냄 | (로그인 공유) |
| `Max-Age` 없음 | 브라우저를 닫으면 사라짐(세션 쿠키) | — |

**코드에서**: `JwtTokenProvider`(발급·검증), `AuthCookieManager`(쿠키 쓰기·읽기·지우기, 스텝 4의 로그인 API가 `login()`을 부른다), `TokenStore`(Redis 키 `auth:refresh:{jti}`, `auth:blocked-access:{jti}`).

### 2. 로그인 유지와 무활동 30분 (AUTH-03)

처음 구현은 "로그인 유지를 안 고르면 브라우저를 닫을 때까지"였는데, 브라우저의 탭 복원 기능 때문에 사실상 기한이 없었다. 지원이 **무활동 30분**으로 정했다.

- 로그인 유지를 안 고르면 Refresh 토큰을 Redis에 TTL 30분으로 저장한다.
- 로그인한 요청이 올 때마다 `EXPIRE`로 30분을 다시 센다(`TokenStore.extendRefresh`).
- 토큰을 새로 바꿔 주는(rotation) 방식이 아니라 Redis TTL만 늘리는 방식이라, 동시에 온 두 요청이 서로의 토큰을 무효로 만드는 경쟁 문제가 없다.
- Access 토큰이 끝나면 프론트가 refresh API를 부르는 대신, **필터가 살아 있는 Refresh로 새 Access 쿠키를 응답에 실어 준다**.

### 3. Spring Security 필터 체인

Spring Security는 Controller 앞에 **필터 여러 개를 줄 세운** 것이다. 요청은 필터를 하나씩 지나고, 어느 필터든 응답을 바로 쓰고 끝낼 수 있다.

`SecurityConfig`에서 한 일:
- 세션을 만들지 않음(`STATELESS`): 로그인 상태는 쿠키의 JWT로만 판단.
- 기본 CSRF 토큰, 폼 로그인, HTTP Basic을 끔.
- 직접 만든 필터 두 개를 `AnonymousAuthenticationFilter` 앞에 끼움: `CsrfHeaderFilter`, `JwtAuthenticationFilter`.
- `/api/admin/**`는 `hasRole("ADMIN")`, 나머지는 열어 둠. 로그인이 필요한 API는 메서드에 `@PreAuthorize("isAuthenticated()")`를 붙인다(`@EnableMethodSecurity`).
- 401·403도 COM-02 모양으로: `authenticationEntryPoint`, `accessDeniedHandler`에서 `ErrorResponseWriter`로 JSON을 쓴다. 필터는 Controller 밖이라 `@RestControllerAdvice`가 잡지 못하기 때문이다.

**`@Component`로 등록하지 않은 이유**: 필터를 `@Component`로 두면 Spring Boot가 일반 서블릿 필터로도 등록해서 두 번 실행된다. 그래서 `SecurityConfig` 안에서 `new`로 만들어 체인에만 넣었다.

### 4. CSRF와 X-Requested-With

CSRF는 사용자가 로그인한 채로 나쁜 사이트를 열었을 때, 그 사이트가 우리 서버로 요청을 보내게 해서 쿠키가 자동으로 실려 가는 공격이다.

- `SameSite=Lax`로 다른 사이트의 POST에는 쿠키가 안 실린다.
- 한 겹 더: 상태를 바꾸는 `/api/` 요청은 `X-Requested-With: XMLHttpRequest` 헤더가 있어야 한다. 다른 사이트의 `<form>`은 사용자 지정 헤더를 붙일 수 없고, `fetch`로 붙이려 하면 브라우저가 사전 요청(preflight)을 보내는데 우리 서버는 CORS를 허용하지 않으니 막힌다.
- 프론트의 `api()` 함수가 GET이 아니면 이 헤더를 자동으로 붙인다.
- SameSite의 "같은 사이트"는 `blog.test`와 그 하위 주소 전체다. 다른 사람의 블로그(`evil.blog.test`)도 같은 사이트라 SameSite만으로는 막지 못한다. 그래서 본문 정화(스텝 2)로 블로그 안에서 스크립트가 돌지 못하게 하는 것과 이 헤더 확인이 함께 필요하다.

### 5. 정지·탈퇴 회원 (T008)

토큰은 유효해도 그 사이에 회원이 정지됐을 수 있다. 그래서 필터가 **요청마다 DB에서 회원 상태를 확인**한다(id로 한 행 읽기라 빠르다).
- 정지 중 + `/api/` 요청 → 403 `MEMBER_SUSPENDED`, `detail`에 사유와 정지 종료 시각(사유는 `moderation_log`의 최신 SUSPEND 행). 쿠키도 지운다.
- 정지 중 + 화면 요청 → 비회원으로 그린다. 화면이 JSON 오류로 깨지지 않게 하려는 것이고, 화면이 부르는 첫 API에서 정지 안내를 받는다.
- 정지 종료 시각이 지났으면 정지가 아니다(`Member.isSuspendedAt(now)`).
- 탈퇴 → 쿠키를 지우고 비회원. 로그인이 필요한 요청은 그대로 401.

### 6. 서브도메인으로 블로그 찾기 (T009)

`BlogHostResolver.resolve(serverName)`이 Host를 세 가지로 나눈다(sealed interface `RequestHost`).

| Host | 결과 |
| --- | --- |
| `blog.test`, `www.blog.test` | `Platform` |
| `alpha.blog.test` | `BlogAddress("alpha")` |
| `a.b.blog.test`, `abc.blog.test`(4자 미만), `admin.blog.test`(예약어), `other.com` | `Unknown` |

- 플랫폼 주소는 설정값 `app.domain.platform`(개발 `blog.test`, 운영 `blog.com`).
- 블로그 API는 컨트롤러 인자에 `@CurrentBlog Blog blog`를 쓰면 `CurrentBlogArgumentResolver`가 블로그를 찾아 넣어 준다. 없거나 볼 수 없거나 이사한 블로그(주인 제외)면 그 자리에서 404.
- 주인 검사 `BlogOwnerGuard.requireOwner(blog, member)`: 비회원 401, 남 403. 404는 블로그를 찾을 때 이미 걸렀다. 상태 코드 순서(rest-api.md)가 404 → 401 → 403인 이유는 **없는 것과 못 보는 것을 구분하지 못하게** 하려는 것이다(헌법 II).

### 7. 글 가시성 판단 (T011)

data-model.md 표를 코드로 옮겼다. 결과는 sealed interface `PostAccess`의 다섯 종류(+ 주인용 숨김 표시)다.

```java
return switch (access) {
    case PostAccess.MovedTo m      -> 301
    case PostAccess.NotFound n     -> 404
    case PostAccess.Owner o        -> 보임 (o.blinded()면 숨김 사유와 함께)
    case PostAccess.Visible v      -> 보임
    case PostAccess.SubscribersOnly s -> 구독 안내 (제목·본문 없이)
};
```

- **sealed + switch**를 쓴 이유: 결과 종류를 하나 더 만들면, 처리하지 않은 `switch`에서 컴파일 오류가 난다. 판단 결과를 빠뜨릴 수 없다.
- **목록은 같은 규칙을 쿼리 조건으로**: 목록 화면에서 글을 하나씩 판단하면 느리고 페이지 개수도 틀린다. `PostSpecifications.visibleTo(viewerId, now)`가 ④를 JPA Criteria 조건(WHERE 절)으로 만든다. 테스트 `listConditionMatchesDetailDecision`이 상세 판단과 목록 조건이 같은 글을 고르는지 확인한다.
- 구독 여부를 보려고 `subscription` 엔티티를, 정지 사유를 보려고 `moderation_log` 엔티티를 이 스텝에서 먼저 만들었다.

### 8. 화면 주소 처리 (T010)

React 앱은 화면 이동을 브라우저 안에서 하지만, 사용자가 주소를 직접 치거나 새로고침하면 서버로 요청이 온다. 서버는 `index.html`을 주기 전에 먼저 확인한다(검색엔진도 301을 따라가게).

- 매핑: `/`, `/{s1}`, `/{s1}/{s2}` … 5단계까지. 첫 단계가 `api`, `uploads`, `assets`이거나 점(`.`)이 있는 경로는 제외한다(정적 파일은 Spring의 정적 리소스 처리로 간다).
- 없는 블로그면 **404 상태로 index.html**을 준다. React가 404 화면을 그리고, 검색엔진은 404로 안다.
- 글 주소 `/{id}`는 **블로그 이사 확인보다 먼저** 판단한다. 이사한 블로그에 남은 글을 블로그 이사 301로 보내면, 새 블로그에서는 "다른 블로그 글"이라 다시 옛 주소로 보내는 무한 루프가 생기기 때문이다.
- 프론트를 빌드하지 않았으면 안내 문구 HTML을 준다.

### 9. 멱등성 키, 연타 방지 (T016)

발행 버튼을 두 번 누르면 글이 두 개 생긴다. 프론트가 버튼을 막아도, 네트워크 재전송이나 빠른 클릭은 서버까지 올 수 있다.

```
1번째 요청 Idempotency-Key: K
  → Redis SET NX "idempotency:{회원}:{POST}:{경로}:K" = PENDING (10분)   ← 원자적. 성공한 한 요청만 실행
  → 컨트롤러 실행 → 201 응답
  → afterCompletion: 응답(상태, Location, 본문)을 같은 키에 저장
2번째 요청 같은 K
  → SET NX 실패 → 저장된 응답을 그대로 돌려줌 (컨트롤러는 실행 안 됨)
```

- 응답 본문을 저장하려면 이미 내보낸 본문을 다시 읽어야 한다. 그래서 `ResponseCachingFilter`가 POST API 응답을 `ContentCachingResponseWrapper`로 감싸 메모리에 잡아 둔다.
- 첫 요청이 실패(2xx가 아님)하면 키를 지워 다시 시도할 수 있게 한다.
- 두 요청이 **동시에** 오면 두 번째는 3초까지 기다렸다가 첫 응답을 받는다. 넘으면 429.
- 키에 회원 id를 넣어서, 남이 같은 키를 보내도 남의 응답을 받지 않는다.
- 공감·구독은 이 장치가 아니라 DB UNIQUE 제약과 PUT/DELETE로 같은 효과를 낸다(R-09).

### 10. 프론트: 주소로 화면 나누기와 API 클라이언트 (T015)

- `app/host.ts`의 `parseHost`: `window.location.hostname`으로 플랫폼/블로그를 나누고, `App.tsx`가 `PlatformRoutes` 또는 `BlogRoutes`를 그린다.
- `api/client.ts`의 `api()`:
  - 쿠키는 브라우저가 자동으로 보낸다(같은 출처, `credentials: 'same-origin'`).
  - GET이 아니면 `X-Requested-With`, 연타 방지 대상이면 `Idempotency-Key`(`newIdempotencyKey()` = `crypto.randomUUID()`).
  - 오류는 `ApiError`(status, code, fieldErrors, detail)로 던진다.
  - 401이면 `blog.test/login?redirect={지금 주소}`로 보낸다.
- React Router는 **7**을 썼다. 8은 React 19가 필요한데 plan.md는 React 18이다.
- Vite 개발 서버를 `alpha.blog.test:5173`으로도 열 수 있게 `allowedHosts: ['.blog.test']`. 프록시가 Host 헤더를 그대로 넘겨서 백엔드가 블로그를 찾는다.

## 테스트 구조

- `IntegrationTestSupport`: `@SpringBootTest` + `@AutoConfigureMockMvc` + Testcontainers. **모든 통합 테스트가 이것을 상속**해서 설정이 같으므로, Spring이 컨텍스트와 컨테이너를 한 번만 띄우고 재사용한다(첫 테스트 약 10초, 나머지는 밀리초).
- `src/test/.../support/`: 테스트 전용 API(`/api/test/**`)와 데이터 도우미(`TestMembers`, `TestBlogs`). 아직 기능이 없는 상태(정지, 이사, 삭제)는 SQL로 만든다.
- 테스트가 DB를 함께 쓰므로 이메일·주소를 매번 랜덤으로 만든다. 가시성 테스트는 `@Transactional`이라 끝나면 되돌린다.

## 막혔던 점

- **`@WebMvcTest`가 깨짐**: 슬라이스 테스트는 `WebMvcConfigurer`와 인자 해석기는 읽고, 그것이 쓰는 `BlogHostResolver` 같은 일반 빈은 읽지 않는다. 웹 설정이 늘 때마다 깨질 구조라서, 오류 처리 테스트를 통합 테스트로 옮겼다.
- **브라우저 주소창으로 없는 API를 열면 본문이 빔**: `Accept: text/html` 요청에는 Spring이 JSON을 쓸 수 없다고 판단한다. 오류 응답에 `contentType(APPLICATION_JSON)`을 미리 지정해서 해결했다.
- **로그인 유지 동작**: 위 2번 참고. 명세에 없던 부분이라 지원이 정하고 spec.md, research.md에 반영했다.

## 직접 해 보기

```bash
./mvnw test -Dtest='AuthenticationIntegrationTest,IdleTimeoutIntegrationTest'   # 로그인·정지·탈퇴·무활동
./mvnw test -Dtest='CurrentBlogIntegrationTest,SpaForwardIntegrationTest'       # 주소 해석·301·404
./mvnw test -Dtest=PostVisibilityIntegrationTest                                # 가시성 결과 6개
./mvnw test -Dtest=IdempotencyIntegrationTest                                   # 같은 키 두 번
cd frontend && npm test

# 서버 띄워서
curl -i -X POST localhost:8080/api/anything                  # 403 CSRF_REJECTED
curl -i localhost:8080/api/admin/x                           # 401 UNAUTHORIZED
curl -i -H "Host: nobody-here.blog.test" localhost:8080/     # 404 HTML
docker exec blog-redis redis-cli KEYS 'auth:*'               # 스텝 4에서 로그인하면 토큰 키가 보인다
```

JWT 내용을 보고 싶으면 테스트에서 만든 `access_token` 값을 jwt.io에 붙여 본다(서명 키는 넣지 않아도 내용은 보인다. 그래서 JWT에 비밀 정보를 넣으면 안 된다).

## 더 공부할 거리

- JWT의 서명 알고리즘(HS256 대칭 키, RS256 비대칭 키)과 키 교체
- Refresh 토큰 rotation과 재사용 감지
- Spring Security의 `SecurityFilterChain` 순서, `OncePerRequestFilter`
- SameSite `Strict`·`Lax`·`None`의 차이와 CORS preflight
- Redis `SET NX`로 만드는 분산 락, TTL
- Java 21 sealed interface와 패턴 매칭 switch
- JPA Criteria API와 Specification, QueryDSL
