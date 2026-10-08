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

## 이 스텝을 이해하려면 (읽는 순서)

위 흐름의 칸마다 개념 문서가 하나씩 있다. 위에서 아래로 읽으면 요청이 지나가는 순서와 같다.

| 순서 | 개념 문서 | 이 스텝에서 그 개념이 쓰인 곳 |
| --- | --- | --- |
| 1 | [HTTP 쿠키](./concepts/10-http-cookies.md) | 토큰을 localStorage가 아니라 쿠키에 둔 이유, `Domain=.blog.test`, HttpOnly·Secure·SameSite, `AuthCookieManager` |
| 2 | [JWT와 로그인 토큰 설계](./concepts/11-jwt.md) | Access/Refresh 분리, Redis로 무효화, 무활동 30분 로그아웃, `JwtTokenProvider`, Nimbus를 고른 이유 |
| 3 | [Spring Security 필터 체인](./concepts/12-spring-security-filter-chain.md) | `SecurityConfig`, `JwtAuthenticationFilter`, 정지·탈퇴 회원 처리, 401·403 JSON, 필터 순서 |
| 4 | [CSRF, SameSite, CORS](./concepts/13-csrf-samesite-cors.md) | `CsrfHeaderFilter`(X-Requested-With), SameSite만으로 부족한 이유, CORS 없이 같은 출처로 운영 |
| 5 | [서브도메인과 Host 라우팅](./concepts/15-subdomain-host-routing.md) | `BlogHostResolver`, `BlogAddressRule`, `@CurrentBlog`, `/etc/hosts` |
| 6 | [인가와 가시성 판단](./concepts/16-authorization-visibility.md) | 존재를 숨기는 404, 404 → 401 → 403 순서, `PostVisibilityPolicy`(sealed + switch), `PostSpecifications`, `BlogOwnerGuard` |
| 7 | [SPA와 서버 라우팅](./concepts/18-spa-server-routing.md) | `SpaForwardController`, 404 상태로 index.html, 301과 무한 리다이렉트를 피한 순서 |
| 8 | [멱등성과 Redis](./concepts/17-idempotency-redis.md) | `IdempotencyInterceptor`, `SET NX`, `ResponseCachingFilter` |
| 9 | [React Router와 API 클라이언트](./concepts/19-react-router-api-client.md) | `parseHost`, `api()` 래퍼, Vitest 테스트 |
| 10 | [Spring 테스트](./concepts/05-spring-testing.md)의 컨텍스트 캐싱 부분 | `IntegrationTestSupport`를 공통 부모로 둔 이유, 테스트 전용 API(`support/`) |

## 막혔던 점

- **`@WebMvcTest`가 깨짐**: 슬라이스 테스트는 `WebMvcConfigurer`와 인자 해석기는 읽고, 그것이 쓰는 `BlogHostResolver` 같은 일반 빈은 읽지 않는다. 웹 설정이 늘 때마다 깨질 구조라서, 오류 처리 테스트를 통합 테스트로 옮겼다.
- **브라우저 주소창으로 없는 API를 열면 본문이 빔**: `Accept: text/html` 요청에는 Spring이 JSON을 쓸 수 없다고 판단한다. 오류 응답에 `contentType(APPLICATION_JSON)`을 미리 지정해서 해결했다.
- **로그인 유지 동작**: 처음에는 로그인 유지를 안 고르면 "브라우저를 닫을 때까지"였는데, 탭 복원 때문에 사실상 기한이 없었다. 무활동 30분으로 바꿨다([JWT 문서](./concepts/11-jwt.md)의 무활동 로그아웃 절). 명세에 없던 부분이라 지원이 정하고 spec.md, research.md에 반영했다.

## 학습 자료를 쓰며 찾은 남은 문제

개념 문서를 쓰면서 코드와 다시 맞춰 보다 찾은 것이다. 아직 고치지 않았고, 표의 "언제"에 고친다.

| 문제 | 영향 | 언제 | 자세히 |
| --- | --- | --- | --- |
| `crypto.randomUUID()`는 HTTPS나 localhost에서만 있다. 개발 주소 `http://alpha.blog.test`에서는 없어서 `newIdempotencyKey()`가 오류를 낸다 | 글 발행·댓글의 연타 방지 키를 못 만듦 | 스텝 5 전 | [19](./concepts/19-react-router-api-client.md) |
| `api()`는 204만 본문 없음으로 처리한다. 202처럼 본문 없는 다른 2xx는 `json()`에서 실패한다 | 이메일 인증 요청(202) | 스텝 4 | [19](./concepts/19-react-router-api-client.md) |
| bcrypt는 72바이트까지만 받는다. 넘으면 예외라 500이 난다. 한글은 25자부터 걸린다 | 가입·비밀번호 변경 | 스텝 4(최대 길이를 지원이 정함) | [09](./concepts/09-password-hashing.md) |
| 보안 필터가 직접 쓰는 401·403 응답에는 CSP 헤더가 없다(CSP 필터가 보안 체인 뒤에서 실행) | JSON 응답이라 영향 작음 | 정리할 때 | [12](./concepts/12-spring-security-filter-chain.md) |
| 화면 주소는 5단계까지만, 점(`.`)이 들어간 경로는 정적 파일로 본다 | 태그 `node.js` 같은 화면 주소가 404 | 스텝 7 태그 화면 | [18](./concepts/18-spa-server-routing.md) |
| 외부 이미지는 `src`만 지워지고 `<img alt="..." />`가 남는다 | 빈 이미지 칸 | 스텝 5·7 | [14](./concepts/14-xss-sanitize-csp.md) |
| `@Idempotent`는 POST에서만 동작한다(`ResponseCachingFilter`가 POST만 감쌈). 처리 중 서버가 죽으면 키가 10분 동안 `PENDING`으로 남는다 | 지금 대상은 모두 POST라 영향 없음 | 대상이 늘 때 | [17](./concepts/17-idempotency-redis.md) |
| `listConditionMatchesDetailDecision` 테스트는 상세 판단을 직접 부르지 않고 기대값을 손으로 적었다 | 상세 규칙만 바꾸면 테스트가 못 잡음 | 스텝 6 목록 API | [16](./concepts/16-authorization-visibility.md) |

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
