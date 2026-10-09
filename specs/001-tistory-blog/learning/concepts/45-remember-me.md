# 로그인 유지: 세션 쿠키와 영속 쿠키, 브라우저 재시작

> 스텝 12(T062, AUTH-03)에서 정리했다. 장치 대부분은 스텝 3에서 만들었고([10 HTTP 쿠키](./10-http-cookies.md), [11 JWT](./11-jwt.md)), 이 문서는 "로그인 유지"라는 기능 하나를 처음부터 끝까지 한 줄로 꿰어 본다.

## 1. 이 문서로 배우는 것

- "로그인 상태 유지" 체크박스 하나가 실제로 바꾸는 것: 쿠키의 수명과 서버 쪽 토큰의 수명
- 세션 쿠키와 영속 쿠키, 그리고 "브라우저를 닫는다"가 쿠키에 무슨 일을 하는지
- 미끄러지는 만료(sliding)와 고정 만료(absolute): 30분 무활동과 14일
- Access 토큰을 다시 받는 두 가지 방법: 필터가 조용히 다시 주기, 재발급 API
- 브라우저를 닫았다 연 상태를 테스트로 흉내 내는 법
- 로그인 유지의 보안 대가와 사용자에게 알리는 법

## 2. 왜 필요한가

로그인은 "이 요청을 보낸 사람이 누구인가"를 매번 증명하는 장치다. HTTP는 요청마다 따로라서, 증명서(쿠키)를 브라우저가 들고 있다가 요청마다 보낸다.

그런데 증명서를 **얼마나 오래** 들고 있어야 할까?

- 너무 짧으면: 글을 쓰다 30분 커피를 마시고 오면 로그아웃돼 있다. 집 컴퓨터에서 매일 로그인해야 한다.
- 너무 길면: PC방에서 로그인하고 그냥 일어나면, 다음 사람이 내 블로그 관리 화면을 연다.

정답이 사람마다, 컴퓨터마다 다르다. 그래서 **사용자에게 고르게** 한다. 이것이 "로그인 상태 유지" 체크박스다. 명세(AUTH-03)는 이렇게 정했다.

| | 고름 | 안 고름 |
| --- | --- | --- |
| 브라우저를 닫았다 열면 | 로그인 그대로 | 로그아웃 |
| 아무것도 안 하고 30분 | 로그인 그대로 | 로그아웃 |
| 계속 쓰는 동안 | 14일 뒤 로그아웃 | 계속 연장 |

## 3. 기본 개념

### 3.1 세션 쿠키와 영속 쿠키

서버가 `Set-Cookie`로 쿠키를 줄 때 수명을 적을 수 있다.

```
Set-Cookie: refresh_token=eyJ...; Max-Age=1209600; Expires=Sat, 24 Oct 2026 ...; Domain=.blog.test; HttpOnly
Set-Cookie: refresh_token=eyJ...; Domain=.blog.test; HttpOnly
```

- 첫 줄처럼 `Max-Age`(또는 `Expires`)가 있으면 **영속 쿠키**(persistent cookie). 브라우저가 디스크에 저장하고, 그 시각까지 남는다. 1209600초 = 14일.
- 둘째 줄처럼 없으면 **세션 쿠키**(session cookie). "이번 브라우저 세션 동안만"이라는 뜻이고, 브라우저를 닫으면 지운다.

여기서 "세션"은 서버의 `HttpSession`과 상관없다. 브라우저를 켠 뒤 끌 때까지라는 뜻이다.

### 3.2 "브라우저를 닫는다"의 정확한 뜻

탭 하나를 닫는 것으로는 세션 쿠키가 지워지지 않는다. **브라우저 프로그램 전체가 끝나야** 한다(맥에서는 창을 다 닫아도 Chrome이 Dock에 살아 있으면 끝난 게 아니다, `⌘Q`로 끝낸다).

그리고 [10 HTTP 쿠키](./10-http-cookies.md) 3.6의 함정: Chrome의 "시작할 때 이전 탭 열기" 같은 **세션 복원**은 세션 쿠키도 되살린다. 그래서 "안 고르면 세션 쿠키"만으로는 부족하고, 서버도 30분 무활동이면 끝낸다. 세션 복원이 쿠키를 살려도 서버가 이미 그 토큰을 버렸으면 로그인되지 않는다.

### 3.3 미끄러지는 만료와 고정 만료

| | 미끄러지는 만료(sliding) | 고정 만료(absolute) |
| --- | --- | --- |
| 뜻 | 쓸 때마다 기한이 다시 처음부터 | 처음 정한 시각에 끝, 써도 늘지 않음 |
| 이 프로젝트 | 유지 안 함: 요청마다 30분으로 되돌림 | 유지 함: 로그인 뒤 14일 |
| 장점 | 쓰는 동안 끊기지 않음 | 훔친 토큰도 언젠가 반드시 끝남 |
| 단점 | 계속 쓰면 영원히 안 끝남 | 쓰던 중에도 끝날 수 있음 |

"유지 함"에 미끄러지는 만료를 쓰면 매일 들어오는 사람은 영원히 로그인 상태다. 그 쿠키를 누가 훔치면 그 사람도 영원히 쓴다. 그래서 14일은 고정으로 두었다(테스트 `activityDoesNotShortenRememberMe`가 "요청해도 30분으로 줄지 않는다"를 지킨다. 늘지도 않는다).

### 3.4 토큰 두 개, 수명 두 개

이 프로젝트의 로그인 쿠키는 둘이다([11 JWT](./11-jwt.md) 3.5).

| 쿠키 | 쿠키 수명 | 서버 쪽 수명 |
| --- | --- | --- |
| `access_token` | 항상 세션 쿠키 | JWT 만료 30분 |
| `refresh_token` (유지 함) | 영속 쿠키 14일 | Redis 키 14일(고정) |
| `refresh_token` (유지 안 함) | 세션 쿠키 | Redis 키 30분(요청마다 연장) |

`access_token`을 항상 세션 쿠키로 주는 이유: 브라우저를 닫았다 열면 Access는 없고 Refresh만 남는다. 그러면 서버는 Refresh를 Redis에서 확인하는 길로 간다. 그 길에서 로그아웃 여부, 30분 무활동 여부를 확인할 수 있다.

### 3.5 Access 토큰을 다시 받는 두 방법

Access 토큰(30분)이 끝나면 Refresh 토큰으로 새로 받아야 한다. 방법이 둘이다.

**(가) 재발급 API를 부른다.** 흔한 SPA 방식.

```
GET /api/posts → 401 (Access 만료)
POST /api/auth/token/refresh → 새 Access 쿠키
GET /api/posts 다시 → 200
```

화면 코드가 "401이면 재발급 후 다시 시도"를 해야 하고, 동시에 요청 여러 개가 401을 받으면 재발급을 한 번만 하도록 줄 세워야 한다.

**(나) 서버 필터가 요청을 처리하면서 조용히 다시 준다.** 이 프로젝트의 방식(R-03).

```
GET /api/posts (Access 없음 또는 만료, Refresh 있음)
  필터: Refresh가 Redis에 살아 있다 → 이 회원으로 처리 + Set-Cookie: access_token=새것
→ 200
```

화면은 아무것도 몰라도 된다. 쿠키가 HttpOnly라 자바스크립트가 어차피 토큰을 못 보니, 서버가 처리하는 쪽이 자연스럽다.

그래도 API 명세에는 `POST /api/auth/token/refresh`가 있다. 스텝 12에서 이것을 만들었다. 하는 일은 (나)를 일부러 한 번 일으키는 것이다. 예를 들어 오래 열어 둔 글쓰기 화면이 "저장 전에 로그인이 살아 있나"를 확인할 때 쓸 수 있다.

## 4. 동작 원리

### 4.1 로그인

```
POST /api/auth/login {email, password, rememberMe: true}
  AuthService.login: 비밀번호 확인 (시도 제한 포함, 40 문서)
  AuthCookieManager.login(response, member, true)
    Refresh JWT 만들기 (jti = 무작위 id)
    Redis SET auth:refresh:{jti} = 회원id, TTL = 14일          ← 유지 안 함이면 30분
    Set-Cookie: refresh_token=...; Max-Age=1209600            ← 유지 안 함이면 Max-Age 없음
    Set-Cookie: access_token=...  (Max-Age 없음)
```

### 4.2 브라우저를 닫았다 연 뒤

```
브라우저 시작: 세션 쿠키(access_token, 유지 안 함의 refresh_token)는 사라짐
GET /api/me  Cookie: refresh_token=...    ← 유지 함이면 이것만 남아 있음
  JwtAuthenticationFilter
    access 없음 → refresh 해석 → Redis에 auth:refresh:{jti} 있나? 있다
    DB에서 회원 상태 확인(정지·탈퇴)
    Set-Cookie: access_token=새것
→ 200 Me
```

유지 안 함이었다면 보낼 쿠키가 하나도 없으므로 비회원이고 `/api/me`는 401이다.

### 4.3 재발급 API

```
POST /api/auth/token/refresh   (X-Requested-With 헤더, 쿠키)
  필터: 4.2와 같다. 필요하면 새 Access 쿠키를 응답에 이미 넣음
  AuthController.refresh: @PreAuthorize("isAuthenticated()")
    로그인 상태면 → 204
    아니면       → 401 (Refresh 없음, Redis에서 지워짐(로그아웃·30분 무활동), 탈퇴)
  정지 회원은 컨트롤러까지 오지 않는다: 필터가 403 MEMBER_SUSPENDED + 쿠키 삭제
```

Access가 아직 유효하면 새 쿠키를 주지 않고 204만 준다. Access 만료까지 남은 시간이 짧아도, 다음 요청에서 만료돼 있으면 필터가 그때 준다.

## 5. 이 프로젝트에서는

### 5.1 체크박스 → 요청 본문: `LoginPage.tsx`, `LoginRequest`

```tsx
const [rememberMe, setRememberMe] = useState(false)
...
await api<Me>('/api/auth/login', { method: 'POST', body: { email: email.trim(), password, rememberMe } })
...
<span className="hint" style={{ marginTop: -8 }}>
  {rememberMe
    ? '브라우저를 닫아도 14일 동안 로그인이 유지됩니다. 여럿이 쓰는 컴퓨터에서는 고르지 마세요.'
    : '고르지 않으면 브라우저를 닫거나 30분 동안 아무것도 하지 않을 때 로그아웃됩니다.'}
</span>
```

- 기본값은 `false`(안 고름). 공용 컴퓨터에서 무심코 로그인해도 안전한 쪽이 기본이다.
- 안내 문구는 스텝 12에서 더했다. 체크박스가 무엇을 바꾸는지 고르는 순간 보여 준다. 고르면 위험(공용 컴퓨터)을, 안 고르면 불편(30분)을 알린다.

```java
public record LoginRequest(
        ...
        Boolean rememberMe) {

    /** 생략하면 로그인 유지를 고르지 않은 것이다. */
    public boolean keepLoggedIn() {
        return Boolean.TRUE.equals(rememberMe);
    }
}
```

- `boolean`이 아니라 `Boolean`: 본문에서 빠져도 오류가 아니게([22 입력 검증](./22-bean-validation.md)의 기본형 칸 누락).
- `Boolean.TRUE.equals(rememberMe)`: `null`이면 `false`. `rememberMe == true`로 쓰면 `null`일 때 언박싱에서 `NullPointerException`이다.

### 5.2 수명을 정하는 곳: `AuthCookieManager.login`, `TokenStore.saveRefresh`

```java
public void login(HttpServletResponse response, Member member, boolean rememberMe) {
    IssuedToken refreshToken = tokenProvider.createRefreshToken(member.getId(), rememberMe);
    tokenStore.saveRefresh(refreshToken, member.getId(), rememberMe ? null : authProperties.idleTimeout());
    addCookie(response, REFRESH_COOKIE, refreshToken.value(),
            rememberMe ? authProperties.refreshTokenTtl() : null);
    issueAccess(response, new LoginMember(member.getId(), member.getRole()));
}
```

- 2줄: Refresh JWT 안에도 `rememberMe`를 적는다. 필터가 나중에 "이 토큰은 30분 연장 대상인가"를 Redis를 따로 보지 않고 안다.
- 3줄: Redis 수명. 유지 함이면 `null`을 넘겨 토큰 만료(14일)까지, 안 함이면 30분.
- 4~5줄: 쿠키 수명. `null`이면 세션 쿠키(`addCookie`가 `maxAge`를 안 씀).

```java
public void saveRefresh(IssuedToken refreshToken, Long memberId, Duration idleTimeout) {
    Duration ttl = untilExpiry(refreshToken.expiresAt());
    if (idleTimeout != null && idleTimeout.compareTo(ttl) < 0) {
        ttl = idleTimeout;
    }
    ...
    redis.opsForValue().set(REFRESH_PREFIX + refreshToken.id(), String.valueOf(memberId), ttl);
```

- 둘 중 짧은 쪽을 TTL로 쓴다. 무활동 기한이 있어도 토큰 자체 만료를 넘지는 않는다.

설정값은 `application.yml`의 `app.auth`: `access-token-ttl: 30m`, `refresh-token-ttl: 14d`, `idle-timeout: 30m`.

### 5.3 요청마다: `JwtAuthenticationFilter`

```java
LoginMember loginMember = new LoginMember(member.get().getId(), member.get().getRole());
if (accessMemberId.isEmpty()) {
    cookieManager.issueAccess(response, loginMember);
}
refresh.filter(claims -> !claims.rememberMe())
        .ifPresent(claims -> tokenStore.extendRefresh(claims.id(), authProperties.idleTimeout()));
```

- 2~4줄: Access로 확인하지 못했고(없거나 만료) Refresh로 확인했으면 새 Access 쿠키. 3.5의 (나).
- 5~6줄: 유지 안 함인 Refresh만 Redis 기한을 다시 30분으로(`EXPIRE`). 미끄러지는 만료. 유지 함은 건드리지 않아 고정 만료.

### 5.4 재발급 API: `AuthController.refresh` (스텝 12)

```java
@PostMapping("/api/auth/token/refresh")
@PreAuthorize("isAuthenticated()")
@ResponseStatus(HttpStatus.NO_CONTENT)
public void refresh() {
}
```

본문이 비어 있다. 일은 이미 필터가 다 했고, 컨트롤러는 "필터를 지나 로그인 상태로 왔나"만 답한다.

- `@PreAuthorize("isAuthenticated()")`: 비회원이면 401(이 프로젝트의 인증 실패 처리).
- POST인 이유: 쿠키를 새로 주는(상태를 바꾸는) 요청이다. 그래서 CSRF 대책인 `X-Requested-With` 헤더도 필요하다([13 CSRF](./13-csrf-samesite-cors.md)).
- 비어 있는 메서드가 어색하면, "컨트롤러가 직접 `issueAccess`를 부르면 되지 않나?"를 생각해 보자. 필터가 이미 새 쿠키를 넣었으면 같은 이름의 `Set-Cookie`가 두 번 나간다. 브라우저는 뒤의 것을 쓰니 동작은 하지만, 같은 일을 두 곳에서 하게 된다.

### 5.5 브라우저 재시작을 흉내 내는 테스트: `KeepLoggedInIntegrationTest`

MockMvc에는 브라우저가 없다. 그래서 "브라우저를 닫았다 연다"를 **규칙으로 옮겨** 흉내 낸다: 응답의 `Set-Cookie` 중 `Max-Age`가 있는 것만 다음 요청에 보낸다.

```java
/** 응답의 Set-Cookie 가운데 브라우저를 닫아도 남는 것(Max-Age가 있는 것)만 다음 요청에 보낸다. */
private Cookie[] cookiesSurvivingRestart(MvcResult login) {
    List<String> setCookies = login.getResponse().getHeaders(HttpHeaders.SET_COOKIE);
    return setCookies.stream()
            .filter(header -> header.contains("Max-Age="))
            .map(header -> HttpCookie.parse(header).getFirst())
            .map(parsed -> new Cookie(parsed.getName(), parsed.getValue()))
            .toArray(Cookie[]::new);
}
```

- 3줄: 로그인 응답의 `Set-Cookie` 헤더 문자열들.
- 5줄: 영속 쿠키만 남긴다. 세션 쿠키는 브라우저를 닫으면 사라지므로 버린다.
- 6줄: `java.net.HttpCookie.parse`는 `Set-Cookie` 값 한 줄을 이름·값·속성으로 나눠 준다(목록을 돌려주므로 `getFirst()`, Java 21의 `List.getFirst`).
- 7줄: MockMvc 요청에 넣을 `jakarta.servlet.http.Cookie`로 바꾼다. 브라우저도 다음 요청에는 이름=값만 보낸다.

```java
@Test
void rememberMeSurvivesBrowserRestart() throws Exception {
    Member member = testMembers.createWithPassword(PASSWORD);
    Cookie[] afterRestart = cookiesSurvivingRestart(login(member, true));

    assertThat(afterRestart).extracting(Cookie::getName).containsExactly(AuthCookieManager.REFRESH_COOKIE);
    mockMvc.perform(get("/api/me").cookie(afterRestart))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.id").value(member.getId()));
}
```

- 5줄: 재시작 뒤 남은 쿠키가 **refresh_token 하나뿐**인지부터 확인한다. 이것이 맞아야 6줄이 "Refresh로 되살아났다"를 시험하는 것이 된다. Access가 남아 있었다면 6줄은 아무것도 증명하지 못한다.
- 6~8줄: 명세의 수용 시나리오 "로그인 유지를 고른 회원이 브라우저를 닫았다 열면 로그인이 유지된다"(spec.md US5 수용 시나리오 10).

`withoutRememberMeBrowserRestartLogsOut`은 반대쪽: 남는 쿠키가 없고 `/api/me`가 401.

나머지 셋은 재발급 API: Refresh만 보내면 204와 새 `access_token`(세션 쿠키), 쿠키가 없거나 로그아웃한 Refresh면 401, 탈퇴 401·정지 403.

## 6. 자주 하는 실수와 함정

- **탭을 닫고 "로그아웃 안 되는데요?"**: 세션 쿠키는 브라우저 전체가 끝나야 지워진다. 맥은 `⌘Q`. 세션 복원이 켜져 있으면 그래도 살아난다. 그때는 서버의 30분이 막는다.
- **로그인 유지에 미끄러지는 만료**: 3.3. 매일 쓰면 영원히 안 끝나고, 훔친 쿠키도 영원히 쓰인다.
- **Access 쿠키도 영속 쿠키로**: 브라우저를 다시 열어도 Access가 남아 30분 동안 Redis 확인 없이 들어온다. 로그아웃한 Access는 차단 목록으로 막지만, 확인할 곳이 늘어난다.
- **쿠키만 지우고 서버 토큰은 그대로**: 로그아웃이 쿠키 삭제만 하면, 그 전에 복사해 둔 쿠키는 계속 통한다. 이 프로젝트는 Redis의 Refresh 키를 지우고 Access를 차단 목록에 올린다(`logoutInvalidatesBothTokens`, `refreshApiNeedsLiveRefreshToken`).
- **테스트가 아무것도 증명하지 못함**: 재시작 흉내에서 Access 쿠키도 같이 보내면, Refresh가 없어도 통과한다. 남은 쿠키가 무엇인지 먼저 단언한다(5.5).
- **`Boolean`을 `==`로**: `null` 언박싱 NPE. `Boolean.TRUE.equals(x)`.

## 7. 직접 해 보기

### 7.1 쿠키 수명 보기

```bash
./mvnw spring-boot:run
```

`http://blog.test:8080/login`에서 "로그인 상태 유지"를 고르고 로그인한다. 개발자 도구 → Application → Cookies → `http://blog.test:8080`:

- `refresh_token`의 Expires/Max-Age 칸이 14일 뒤 날짜
- `access_token`은 "Session"

로그아웃하고 이번에는 고르지 않고 로그인하면 둘 다 "Session"이다.

### 7.2 브라우저 재시작

1. 유지를 고르고 로그인 → 브라우저를 완전히 끈다(`⌘Q`) → 다시 켜서 `blog.test:8080` → 머리글에 닉네임이 보인다.
2. Cookies를 보면 `access_token`이 다시 생겨 있다. 첫 요청 때 필터가 새로 준 것이다.
3. 유지를 고르지 않고 같은 것을 하면 로그인 버튼이 보인다(세션 복원이 꺼져 있을 때. 켜져 있으면 7.3).

### 7.3 Redis에서 보기

```bash
docker exec -it blog-redis redis-cli
KEYS auth:refresh:*
TTL auth:refresh:{위에서 나온 jti}
```

- 유지 함: 약 1209600에서 줄어든다. 화면을 눌러도 다시 늘지 않는다.
- 유지 안 함: 1800 이하. 화면을 누를 때마다 1800으로 돌아간다.
- 유지 안 함인 키를 `DEL`하고 화면을 새로 고치면: Access가 아직 살아 있으면 30분 안에는 로그인 상태다. `access_token` 쿠키도 지우면 즉시 로그아웃된다.

### 7.4 재발급 API

로그인한 브라우저의 개발자 도구 Console에서:

```js
await fetch('/api/auth/token/refresh', { method: 'POST', headers: { 'X-Requested-With': 'XMLHttpRequest' } }).then(r => r.status)
```

204. Cookies에서 `access_token`을 지우고 다시 부르면 204와 함께 Network 탭의 응답 헤더에 새 `Set-Cookie: access_token=`이 보인다.

### 7.5 테스트

```bash
./mvnw test -Dtest='KeepLoggedInIntegrationTest,IdleTimeoutIntegrationTest,LoginIntegrationTest'
```

## 8. 확인 문제

1. `Set-Cookie: a=1; Domain=.blog.test; HttpOnly`는 영속 쿠키인가, 세션 쿠키인가?

<details><summary>답</summary>

세션 쿠키. `Max-Age`도 `Expires`도 없다. 브라우저를 끝내면 지워진다.

</details>

2. 로그인 유지를 고른 회원이 14일 동안 매일 글을 쓴다. 15일째 아침에는?

<details><summary>답</summary>

다시 로그인해야 한다. 유지 함은 고정 만료라 요청해도 Redis 기한이 늘지 않고, 쿠키도 14일에 끝난다.

</details>

3. 로그인 유지를 고르지 않은 회원이 세션 복원이 켜진 Chrome을 닫고, 2시간 뒤 다시 열었다. 세션 쿠키가 되살아났는데 왜 로그아웃 상태인가?

<details><summary>답</summary>

Access 토큰(JWT 만료 30분)은 이미 끝났고, Refresh 토큰의 Redis 키는 마지막 요청 뒤 30분에 사라졌다. 쿠키는 있어도 서버가 받아 주지 않는다.

</details>

4. `KeepLoggedInIntegrationTest.rememberMeSurvivesBrowserRestart`에서 `containsExactly(REFRESH_COOKIE)` 줄을 지우면 무엇을 놓칠 수 있나?

<details><summary>답</summary>

실수로 `access_token`까지 영속 쿠키로 주게 바뀌어도 테스트가 통과한다. 그러면 `/api/me`의 200은 Access로 얻은 것이라, Refresh로 로그인이 되살아나는지는 시험하지 못한다.

</details>

5. 재발급 API가 컨트롤러에서 직접 새 Access 쿠키를 주지 않는 이유는?

<details><summary>답</summary>

필터가 이미 필요할 때 새 Access 쿠키를 줬다. 컨트롤러도 주면 같은 쿠키 `Set-Cookie`가 두 번 나가고, 재발급 규칙이 두 곳에 생긴다.

</details>

6. 정지된 회원이 재발급 API를 부르면 401이 아니라 403인 이유는?

<details><summary>답</summary>

필터가 컨트롤러보다 먼저 회원 상태를 보고, 정지면 모든 API에서 403 `MEMBER_SUSPENDED`와 정지 사유를 준다. 그래야 화면이 "정지됐다, 사유는…"을 보여 줄 수 있다. API 명세의 이 줄은 "정지·탈퇴면 401"이라 지원 확인이 필요하다(스텝 12 노트).

</details>

## 9. 더 읽을거리

- MDN, [Set-Cookie](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie): `Max-Age`, `Expires`, 세션 쿠키와 세션 복원 경고
- RFC 6265, HTTP State Management Mechanism: 5.3절 쿠키 저장 규칙(영속 여부)
- OWASP, [Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html): idle timeout과 absolute timeout, "Remember Me"
- 이 저장소: [10 HTTP 쿠키](./10-http-cookies.md), [11 JWT](./11-jwt.md) 3.5~3.8, [21 가입·로그인](./21-signup-login.md)
