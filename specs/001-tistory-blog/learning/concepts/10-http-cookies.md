# HTTP 쿠키와 로그인 상태

> 관련 스텝: [스텝 3](../step-03.md) · 관련 결정: spec.md Q6, research.md R-03, AUTH-02, AUTH-03

## 1. 이 문서로 배우는 것

- HTTP가 "상태가 없다(stateless)"는 말의 뜻과, 그래서 쿠키가 생긴 이유
- 서버가 `Set-Cookie`로 쿠키를 주고 브라우저가 `Cookie`로 돌려보내는 흐름
- 쿠키 속성 하나하나(`Domain`, `Path`, `Max-Age`/`Expires`, `HttpOnly`, `Secure`, `SameSite`)가 무엇을 정하는지
- 세션 기반 인증과 토큰 기반 인증의 차이
- 이 프로젝트가 로그인 토큰을 `localStorage`가 아니라 쿠키에 두는 이유
- 쿠키를 지우는 방법과, 지울 때 흔히 하는 실수
- 이 프로젝트의 `AuthCookieManager`가 쿠키를 만드는 방식

**먼저 알면 좋은 것**: HTTP 요청·응답이 "시작 줄 + 헤더 + 본문"으로 되어 있다는 것, 도메인 이름(`blog.test`, `alpha.blog.test`)의 구조. 브라우저 개발자 도구의 Network 탭을 열어 본 적이 있으면 실습이 쉽다.

---

## 2. 왜 필요한가

### HTTP는 요청 하나하나를 따로 본다

HTTP는 요청과 응답이 한 쌍으로 끝나는 프로토콜이다. 서버는 기본적으로 **앞의 요청을 기억하지 않는다**. 이것을 "상태가 없다(stateless)"고 한다.

```
요청 1: POST /api/auth/login  (이메일, 비밀번호)   → 200 "로그인 성공"
요청 2: GET  /api/me                              → 서버: "너 누구야?"
```

요청 2에는 "나는 방금 로그인한 그 사람이다"라는 정보가 어디에도 없다. 서버가 요청 1을 기억하고 있다 해도, 요청 2가 **같은 사람**에게서 왔다는 것을 알 방법이 없다. 같은 IP에서 여러 사람이 접속할 수도 있고(회사, 학교), 한 사람의 IP가 바뀔 수도 있다(휴대폰).

### 매번 비밀번호를 보내면?

요청마다 이메일과 비밀번호를 같이 보내면 "누구인지"는 알 수 있다. 하지만:
- 프론트가 비밀번호를 어딘가에 계속 들고 있어야 한다(유출 위험).
- 서버가 요청마다 bcrypt 비교를 해야 한다(bcrypt는 일부러 느리다. [09-password-hashing](./09-password-hashing.md)).
- 로그아웃이라는 개념이 없다.

### 그래서 "로그인했다는 증표"를 준다

로그인에 성공하면 서버가 **증표**(세션 ID나 토큰)를 주고, 브라우저가 이후 요청마다 그 증표를 자동으로 붙여 보내게 한다. 이 "자동으로 붙여 보내는" 장치가 **쿠키**다.

---

## 3. 기본 개념

### 3.1 쿠키란

쿠키는 **서버가 브라우저에게 저장해 달라고 부탁하는 작은 이름=값 쌍**이다. 브라우저는 그것을 저장했다가, 조건이 맞는 요청마다 자동으로 다시 보낸다.

| 용어 | 뜻 |
| --- | --- |
| `Set-Cookie` | 응답 헤더. 서버가 "이 쿠키를 저장해"라고 말한다. 쿠키 하나당 헤더 하나 |
| `Cookie` | 요청 헤더. 브라우저가 "저장해 둔 쿠키 여기 있어"라고 보낸다. 여러 개를 `;`로 이어 한 줄로 |
| 속성(attribute) | `Set-Cookie`에서 `이름=값` 뒤에 붙는 설정. 언제까지, 어느 주소로 보낼지 등을 정한다 |
| 세션 쿠키 | 만료 시각이 없는 쿠키. 브라우저를 닫으면 지워진다(원칙적으로) |
| 영구 쿠키 | `Max-Age`나 `Expires`가 있는 쿠키. 그 시각까지 디스크에 남는다 |

### 3.2 주고받는 모양

```
[응답] 서버 → 브라우저
HTTP/1.1 200 OK
Set-Cookie: access_token=eyJhbGci...; Path=/; Domain=.blog.test; HttpOnly; SameSite=Lax
Set-Cookie: refresh_token=eyJhbGci...; Path=/; Domain=.blog.test; Max-Age=1209600; Expires=...; HttpOnly; SameSite=Lax

[다음 요청] 브라우저 → 서버
GET /api/me HTTP/1.1
Host: alpha.blog.test
Cookie: access_token=eyJhbGci...; refresh_token=eyJhbGci...
```

눈여겨볼 점:
- `Set-Cookie`에는 속성이 붙지만, `Cookie` 요청 헤더에는 **이름=값만** 간다. 서버는 요청을 받았을 때 그 쿠키의 만료 시각이나 Domain을 알 수 없다.
- 쿠키 두 개면 `Set-Cookie` 헤더가 두 줄이다. 쿠키 하나에 여러 쿠키를 넣을 수 없다.

### 3.3 속성 한눈에 보기

| 속성 | 정하는 것 | 생략하면 | 예 |
| --- | --- | --- | --- |
| `Domain` | 어느 호스트로 보낼지 | 쿠키를 준 그 호스트에만(host-only) | `Domain=.blog.test` |
| `Path` | 어느 경로로 보낼지 | 요청 경로의 "디렉터리" | `Path=/` |
| `Max-Age` | 몇 초 뒤에 지울지 | 세션 쿠키 | `Max-Age=1209600`(14일) |
| `Expires` | 어느 시각에 지울지 | 세션 쿠키 | `Expires=Thu, 22 Oct 2026 ...` |
| `HttpOnly` | 자바스크립트에서 못 읽게 | JS로 읽을 수 있음 | `HttpOnly` |
| `Secure` | HTTPS일 때만 보내게 | HTTP로도 보냄 | `Secure` |
| `SameSite` | 다른 사이트에서 시작된 요청에도 보낼지 | 브라우저 기본값(최근 Chrome은 Lax로 취급) | `SameSite=Lax` |

아래에서 하나씩 자세히 본다.

### 3.4 Domain: 어느 호스트에 보내나

- **Domain을 생략**하면 host-only 쿠키다. `blog.test`가 준 쿠키는 `blog.test`에만 가고 `alpha.blog.test`에는 **안 간다**.
- **Domain을 지정**하면 그 도메인과 **모든 하위 도메인**에 간다. `Domain=blog.test`면 `blog.test`, `alpha.blog.test`, `beta.blog.test` 모두.
- 앞의 점(`.blog.test`)은 옛 규격(RFC 2109)의 흔적이다. 지금 규격(RFC 6265)에서는 앞 점을 무시하므로 `Domain=.blog.test`와 `Domain=blog.test`는 같다.
- 서버는 **자기와 관계없는 도메인**에 쿠키를 줄 수 없다. `alpha.blog.test`는 `Domain=blog.test`를 줄 수 있지만(상위 도메인), `other.com`이나 `com` 같은 공개 접미사(public suffix)에는 줄 수 없다. 브라우저가 거부한다.
- `localhost`에서 응답한 `Domain=.blog.test` 쿠키도 브라우저가 거부한다(요청 호스트가 그 도메인에 속하지 않으므로). 이 프로젝트에서 로그인을 확인할 때 `localhost` 대신 `blog.test`로 접속해야 하는 이유다(quickstart.md).

```
Domain=.blog.test 쿠키가 가는 곳
  blog.test            ✔
  www.blog.test        ✔
  alpha.blog.test      ✔
  a.b.blog.test        ✔ (하위 도메인이면 몇 단계든)
  blog.test.evil.com   ✘
  evilblog.test        ✘ (문자열이 끝이 같아도 점 경계가 아니면 아님)
  localhost            ✘
```

### 3.5 Path

`Path=/api`면 `/api`, `/api/me`처럼 그 경로 아래 요청에만 쿠키가 간다. 이 프로젝트는 화면 주소 요청(`/manage/...`)에서도 로그인 상태를 알아야 하므로(스텝 3의 화면 주소 처리) `Path=/`로 모든 경로에 보낸다.

Path는 보안 경계가 아니다. 같은 출처의 다른 경로 페이지는 자바스크립트로 그 쿠키를 읽는 방법이 있으므로, "민감한 쿠키를 Path로 숨긴다"는 생각은 틀렸다(MDN에 같은 경고가 있다).

### 3.6 Max-Age, Expires, 세션 쿠키

- `Max-Age=초`: 지금부터 몇 초 뒤에 지운다. `Expires=날짜`: 그 날짜에 지운다. 둘 다 있으면 **Max-Age가 우선**이다(RFC 6265).
- 둘 다 없으면 **세션 쿠키**다. 브라우저를 닫으면 지워진다.
- Spring의 `ResponseCookie`는 `maxAge`를 주면 `Max-Age`와 `Expires`를 함께 써 준다(옛 브라우저 호환).

**함정: 세션 쿠키가 다시 살아난다.** Chrome의 "시작할 때 이전 탭 열기" 같은 **세션 복원** 기능은 탭과 함께 세션 쿠키도 되살린다(MDN의 `Set-Cookie` 문서에도 경고가 있다). 그래서 "로그인 유지를 안 고르면 세션 쿠키로 주면 된다"만으로는 실제로 로그아웃되지 않을 수 있다. 이 프로젝트는 이 문제 때문에 **서버 쪽에서도** 무활동 30분이 지나면 Refresh 토큰을 끝낸다([11-jwt](./11-jwt.md)의 무활동 로그아웃).

### 3.7 HttpOnly

`HttpOnly`가 붙은 쿠키는 자바스크립트의 `document.cookie`로 읽을 수 없다. 브라우저가 HTTP 요청에 붙여 보낼 때만 쓴다.

```js
// 개발자 도구 콘솔에서
document.cookie   // access_token, refresh_token은 보이지 않는다
```

막는 것: 페이지에 악성 스크립트가 들어왔을 때(XSS) **토큰 값을 훔쳐 다른 곳으로 보내는 것**.
못 막는 것: 그 악성 스크립트가 **그 페이지 안에서** 우리 API를 부르는 것(브라우저가 쿠키를 자동으로 붙이므로). 그래서 XSS 자체를 막는 것이 따로 필요하다([14-xss-sanitize-csp](./14-xss-sanitize-csp.md)).

### 3.8 Secure

`Secure`가 붙은 쿠키는 HTTPS 요청에만 실린다. 공용 와이파이에서 평문 HTTP를 엿보는 공격자가 쿠키를 보지 못하게 한다. 또 최근 브라우저는 `http:` 페이지가 `Secure` 쿠키를 **설정하는 것 자체**를 거부한다(`localhost`는 브라우저마다 예외가 있다).

이 프로젝트는 개발 환경이 `http://blog.test:8080`이라 `Secure`를 켜면 쿠키가 아예 저장되지 않는다. 그래서 `app.auth.cookie-secure`를 설정값으로 두고 **운영(true), 개발(false)**로 나눴다.

### 3.9 SameSite

요청이 **다른 사이트에서 시작됐을 때**(예: 다른 사이트의 폼이 우리 서버로 POST) 쿠키를 보낼지 정한다. CSRF 공격을 막는 핵심 장치라서 [13-csrf-samesite-cors](./13-csrf-samesite-cors.md)에서 자세히 다룬다. 요약하면:

| 값 | 다른 사이트에서 시작된 요청에 쿠키를 |
| --- | --- |
| `Strict` | 절대 보내지 않는다(다른 사이트의 링크를 눌러 들어와도 처음엔 로그아웃 상태로 보임) |
| `Lax` | 링크를 눌러 이동하는 GET(최상위 이동)에만 보낸다. 폼 POST, `fetch`, `<img>`, `<iframe>`에는 안 보낸다 |
| `None` | 항상 보낸다. 반드시 `Secure`와 함께 써야 한다 |

여기서 "사이트"는 출처(origin)와 다르다. `blog.test`와 `alpha.blog.test`는 **출처는 다르지만 같은 사이트**다. 그래서 블로그 주소끼리 이동해도 `Lax` 쿠키가 따라간다.

### 3.10 세션 기반 인증과 토큰 기반 인증

로그인 "증표"를 무엇으로 하느냐에 따라 두 방식이 있다.

```
세션 기반                                      토큰 기반 (JWT)
────────────────────────────────────          ────────────────────────────────────
로그인 → 서버 메모리/DB에 세션 생성             로그인 → 서버가 서명한 토큰 생성
       → 쿠키에 세션 ID(JSESSIONID=abc)               → 쿠키(또는 헤더)에 토큰
요청   → 서버가 세션 저장소에서 abc 조회        요청   → 서버가 서명만 검사(저장소 조회 없음)
       → 회원 정보 얻음                                → 토큰 안의 회원 id를 믿음
로그아웃 → 세션 삭제(즉시 무효)                 로그아웃 → 토큰은 만료 전까지 유효(무효화 장치 필요)
```

| | 세션 기반 | 토큰 기반 |
| --- | --- | --- |
| 서버에 저장 | 세션 전체 | (원칙적으로) 없음 |
| 서버 여러 대 | 세션 저장소를 공유해야 함(예: Spring Session + Redis) | 서명 키만 같으면 됨 |
| 즉시 로그아웃 | 쉬움 | 어려움(차단 목록 등 필요) |
| 증표에 담긴 정보 | 없음(ID만) | 회원 id, 역할, 만료 시각 |

**중요: 세션 방식이든 토큰 방식이든 "쿠키에 담을 수 있다".** 쿠키는 운반 수단이고, 세션/토큰은 운반하는 내용물이다. 둘을 헷갈리지 않는다.

이 프로젝트는 **토큰(JWT)을 쿠키에 담고**, 로그아웃과 무활동 만료를 위해 Redis에 약간의 상태(살아 있는 Refresh 토큰, 막힌 Access 토큰)를 둔다. 순수한 무상태 방식과 세션 방식의 중간쯤이다.

### 3.11 왜 localStorage가 아니라 쿠키인가 (Q6, R-03)

SPA(React 앱)에서는 토큰을 `localStorage`에 두고 요청마다 `Authorization: Bearer ...` 헤더로 보내는 방식도 흔하다. 이 프로젝트가 그렇게 하지 않은 이유는 **블로그가 서브도메인**이기 때문이다.

```
localStorage는 출처(origin)마다 따로다
  http://blog.test:8080         → 저장소 A  (여기서 로그인 → 토큰이 A에)
  http://alpha.blog.test:8080   → 저장소 B  (B는 비어 있음 → 로그아웃 상태!)
```

`blog.test`에서 로그인하고 내 블로그 `alpha.blog.test/manage`로 가면 로그아웃 상태가 된다. 이것은 P0 한 바퀴("로그인 → 내 블로그에서 글쓰기")를 막는다(review.md 3, Q6).

쿠키는 `Domain=.blog.test`로 주면 모든 하위 도메인이 함께 받으므로 이 문제가 저절로 풀린다.

덤으로 얻는 것: `HttpOnly` 쿠키는 XSS가 토큰 값을 훔쳐 가지 못한다. `localStorage`는 같은 출처의 어떤 스크립트든 읽을 수 있다.
대신 떠안는 것: 쿠키는 자동으로 실려 가므로 **CSRF 대책이 필요하다**([13-csrf-samesite-cors](./13-csrf-samesite-cors.md)).

---

## 4. 동작 원리

### 4.1 브라우저가 쿠키를 저장할 때

`Set-Cookie`를 받으면 브라우저는 대략 이렇게 한다(RFC 6265 5.3을 줄인 것).

1. `이름=값`과 속성을 읽는다.
2. `Domain`이 있으면, 요청 호스트가 그 도메인에 속하는지 확인한다. 아니면 **버린다**. 공개 접미사면 버린다.
3. `Domain`이 없으면 host-only로 표시한다.
4. `Max-Age`/`Expires`로 만료 시각을 정한다. 없으면 세션 쿠키. 이미 지난 시각이면 **같은 이름·Domain·Path 쿠키를 지운다**.
5. `Secure`인데 HTTP 페이지면 저장하지 않는다(최근 브라우저).
6. 같은 (이름, Domain, Path) 쿠키가 이미 있으면 **덮어쓴다**. 셋 중 하나라도 다르면 **별개의 쿠키**로 따로 저장한다.

6번이 쿠키를 지울 때 흔한 실수의 원인이다(아래 4.3).

### 4.2 브라우저가 쿠키를 보낼 때

요청을 보낼 때마다 저장된 쿠키를 훑어서 다음을 모두 만족하는 것만 `Cookie` 헤더에 넣는다.

1. 요청 호스트가 쿠키의 Domain에 맞는다(host-only면 정확히 같아야 함).
2. 요청 경로가 쿠키의 Path 아래다.
3. `Secure` 쿠키면 요청이 HTTPS다.
4. 만료되지 않았다.
5. `SameSite` 조건에 맞는다(다른 사이트에서 시작된 요청이면 Lax/Strict 규칙 적용).

포트는 보지 않는다. 그래서 `blog.test:8080`이 준 쿠키가 `alpha.blog.test:5173`(Vite 개발 서버)에도 간다. 이 프로젝트에서 Vite 개발 서버를 `.blog.test` 주소로 열 수 있게 한 이유다.

### 4.3 쿠키를 지우는 법

서버가 쿠키를 직접 지울 수는 없다. **"이 쿠키를 이미 만료된 것으로 덮어써"**라고 `Set-Cookie`를 보낸다.

```
Set-Cookie: access_token=; Path=/; Domain=.blog.test; Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT; HttpOnly; SameSite=Lax
```

반드시 **처음 줄 때와 같은 이름, Domain, Path**로 보내야 한다. 예를 들어 처음에 `Domain=.blog.test`로 줬는데 지울 때 Domain을 빼면, 브라우저는 그것을 host-only인 **다른 쿠키**로 보고 원래 쿠키는 그대로 남는다. "로그아웃 버튼을 눌렀는데 로그인이 유지돼요"의 흔한 원인이다.

### 4.4 이 프로젝트에서 로그인 상태가 이어지는 그림

```
1) blog.test에서 로그인 (스텝 4에서 만들 API가 AuthCookieManager.login 호출)
   ← Set-Cookie: access_token (세션 쿠키, JWT 30분)
   ← Set-Cookie: refresh_token (로그인 유지면 14일 쿠키, 아니면 세션 쿠키)

2) alpha.blog.test/manage 로 이동
   → Cookie: access_token=...; refresh_token=...   (Domain=.blog.test라서 같이 감)
   서버의 JwtAuthenticationFilter가 access_token을 검증 → 로그인 상태

3) 30분 뒤 access_token의 JWT가 만료
   → Cookie: access_token=(만료된 JWT); refresh_token=...
   필터가 refresh_token이 Redis에 살아 있는지 확인 → 새 access_token을 Set-Cookie로 줌

4) 로그아웃 (AuthCookieManager.logout)
   ← Set-Cookie: access_token=; Max-Age=0; Domain=.blog.test; Path=/
   ← Set-Cookie: refresh_token=; Max-Age=0; Domain=.blog.test; Path=/
   + Redis에서 refresh 삭제, access는 차단 목록에 → 모든 블로그 주소에서 로그아웃(AUTH-02)
```

---

## 5. 이 프로젝트에서는

### 5.1 쿠키를 만드는 곳: `AuthCookieManager.addCookie`

경로: `src/main/java/com/nhnacademy/blog/global/auth/AuthCookieManager.java`

```java
/** maxAge가 null이면 브라우저를 닫을 때 사라지는 쿠키다. */
private void addCookie(HttpServletResponse response, String name, String value, Duration maxAge) {
    ResponseCookie.ResponseCookieBuilder cookie = ResponseCookie.from(name, value)
            .domain(domainProperties.cookieDomain())     // ① ".blog.test" (운영 ".blog.com")
            .path("/")                                   // ② 모든 경로
            .httpOnly(true)                              // ③ JS로 못 읽음
            .secure(authProperties.cookieSecure())       // ④ 운영 true, 개발 false
            .sameSite("Lax");                            // ⑤ 다른 사이트의 POST에는 안 감
    if (maxAge != null) {
        cookie.maxAge(maxAge);                           // ⑥ 있으면 영구 쿠키, 없으면 세션 쿠키
    }
    response.addHeader(HttpHeaders.SET_COOKIE, cookie.build().toString());  // ⑦
}
```

- ① `DomainProperties.cookieDomain()`은 `"." + platform`이다. 플랫폼 주소는 설정값 `app.domain.platform`(개발 `blog.test`, 운영 `blog.com`)이라, 코드에 도메인을 박아 두지 않는다.
- ⑤ Servlet의 `jakarta.servlet.http.Cookie` 클래스에는 오랫동안 SameSite를 정하는 메서드가 없었다. 그래서 Spring의 `ResponseCookie` 빌더로 헤더 문자열을 직접 만들어 넣는다.
- ⑦ `addHeader`(set이 아니라 add)라서 쿠키 두 개면 `Set-Cookie` 헤더가 두 줄 생긴다.

### 5.2 쿠키의 종류와 수명

```java
public static final String ACCESS_COOKIE = "access_token";
public static final String REFRESH_COOKIE = "refresh_token";

public void login(HttpServletResponse response, Member member, boolean rememberMe) {
    IssuedToken refreshToken = tokenProvider.createRefreshToken(member.getId(), rememberMe);
    tokenStore.saveRefresh(refreshToken, member.getId(), rememberMe ? null : authProperties.idleTimeout());
    addCookie(response, REFRESH_COOKIE, refreshToken.value(),
            rememberMe ? authProperties.refreshTokenTtl() : null);   // 로그인 유지면 14일, 아니면 세션 쿠키
    issueAccess(response, new LoginMember(member.getId(), member.getRole()));
}

public void issueAccess(HttpServletResponse response, LoginMember member) {
    IssuedToken accessToken = tokenProvider.createAccessToken(member.id(), member.role());
    addCookie(response, ACCESS_COOKIE, accessToken.value(), null);   // 항상 세션 쿠키
}
```

| 쿠키 | 쿠키 수명 | 안의 JWT 수명 | 서버 쪽 상태 |
| --- | --- | --- | --- |
| `access_token` | 세션 쿠키 | 30분 | 로그아웃하면 Redis 차단 목록 |
| `refresh_token`(로그인 유지) | 14일 | 14일 | Redis에 14일 |
| `refresh_token`(유지 안 함) | 세션 쿠키 | 14일 | Redis에 **30분, 요청마다 연장** |

`access_token`을 세션 쿠키로 둬도 되는 이유: 로그인 유지를 고른 사람이 브라우저를 다시 열면 `access_token`은 없고 `refresh_token`만 있다. 그러면 필터가 Refresh로 새 Access를 만들어 준다.

"쿠키 수명"과 "안의 JWT 수명"이 다를 수 있다는 점을 기억한다. 쿠키가 살아 있어도 안의 JWT가 만료됐으면 서버는 거절한다.

### 5.3 쿠키 지우기

```java
public void clear(HttpServletResponse response) {
    addCookie(response, ACCESS_COOKIE, "", Duration.ZERO);
    addCookie(response, REFRESH_COOKIE, "", Duration.ZERO);
}
```

지울 때도 같은 `addCookie`를 써서 Domain, Path가 **줄 때와 반드시 같다**(4.3의 함정을 구조로 막음). 실제로 나가는 헤더는 이렇다(개발 서버에서 확인).

```
Set-Cookie: access_token=; Path=/; Domain=.blog.test; Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT; HttpOnly; SameSite=Lax
Set-Cookie: refresh_token=; Path=/; Domain=.blog.test; Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT; HttpOnly; SameSite=Lax
```

`clear`는 로그아웃 말고도 망가진 토큰, 탈퇴한 회원, 정지된 회원일 때 필터가 부른다([12-spring-security-filter-chain](./12-spring-security-filter-chain.md)).

### 5.4 쿠키 읽기

```java
public Optional<String> readCookie(HttpServletRequest request, String name) {
    Cookie[] cookies = request.getCookies();     // 쿠키가 하나도 없으면 null (빈 배열이 아님!)
    if (cookies == null) {
        return Optional.empty();
    }
    return Arrays.stream(cookies)
            .filter(cookie -> name.equals(cookie.getName()))
            .map(Cookie::getValue)
            .filter(value -> !value.isBlank())   // 지우는 중인 빈 값은 없는 것으로
            .findFirst();
}
```

`request.getCookies()`가 쿠키가 없을 때 **null**을 돌려준다는 점이 Servlet API의 함정이다.

### 5.5 설정값

`src/main/resources/application.yml`, `application-dev.yml`:

```yaml
app:
  domain:
    platform: blog.com          # dev: blog.test
  auth:
    access-token-ttl: 30m
    refresh-token-ttl: 14d
    idle-timeout: 30m
    cookie-secure: true         # dev: false (http://blog.test:8080)
```

---

## 6. 자주 하는 실수와 함정

1. **지울 때 Domain/Path를 다르게 준다.** 원래 쿠키는 남고 새 빈 쿠키가 하나 더 생긴다. 줄 때와 지울 때 같은 코드를 쓴다.
2. **`localhost`로 접속해서 로그인 쿠키를 확인한다.** `Domain=.blog.test` 쿠키는 `localhost` 응답에서 저장되지 않는다. `/etc/hosts`에 `blog.test`를 등록하고 그 주소로 연다.
3. **개발 환경에서 `Secure`를 켠다.** HTTP 페이지라 쿠키가 저장되지 않아 "로그인은 성공했는데 로그인이 안 된" 상태가 된다.
4. **세션 쿠키면 브라우저를 닫을 때 반드시 사라진다고 믿는다.** 세션 복원 기능이 되살린다. 만료는 서버에서도 관리한다.
5. **`HttpOnly`면 XSS가 안전하다고 생각한다.** 토큰 탈취는 막지만, 악성 스크립트가 쿠키가 자동으로 실리는 요청을 보내는 것은 못 막는다.
6. **SameSite만 있으면 CSRF가 끝난다고 생각한다.** 같은 사이트의 다른 하위 도메인(다른 사람 블로그)에서 오는 요청은 SameSite가 막지 못한다([13-csrf-samesite-cors](./13-csrf-samesite-cors.md)).
7. **쿠키에 큰 값을 넣는다.** 브라우저는 쿠키 하나에 약 4KB까지만 보장한다(RFC 6265 권고 최소치). 요청마다 실려 가므로 크기가 곧 트래픽이다. JWT에 정보를 많이 넣지 않는 이유 중 하나다.
8. **`request.getCookies()`의 null을 처리하지 않는다.** NullPointerException.

---

## 7. 직접 해 보기

준비: `/etc/hosts`에 `127.0.0.1 blog.test alpha.blog.test` 등록, `docker compose up -d`, `./mvnw spring-boot:run`.

### 실습 1: 응답의 Set-Cookie 보기

스텝 4에서 로그인 API가 생기기 전에는 망가진 쿠키를 보내 `clear`를 일으켜 볼 수 있다.

```bash
curl -s -D - -o /dev/null -H "Host: blog.test" -b "access_token=broken" localhost:8080/api/x | grep -i set-cookie
```

기대 결과: `Max-Age=0`이 붙은 `Set-Cookie` 두 줄. Domain, Path가 들어 있는지 확인한다.

### 실습 2: 테스트로 쿠키 속성 확인

```bash
./mvnw test -Dtest=AuthenticationIntegrationTest#loginCookiesAreSharedAcrossBlogAddresses
```

테스트 코드(`src/test/.../global/auth/AuthenticationIntegrationTest.java`)를 열어 어떤 속성을 검사하는지 읽는다. `cookieManager.login(response, member, true)`의 `true`를 `false`로 바꾸면 어느 단언이 깨지는지 예상해 보고 돌려 본다.

### 실습 3: Domain을 빼 보기

`AuthCookieManager.addCookie`에서 `.domain(...)` 줄을 주석 처리하고 실습 2를 다시 돌린다. 어떤 단언이 실패하는가? 그 상태로 운영에 나가면 사용자에게 무슨 일이 생기는가(블로그 주소로 가면 로그아웃)? 확인 후 원래대로 돌린다.

### 실습 4: 브라우저에서 보기 (스텝 4 이후)

1. `http://blog.test:8080`에서 로그인한다.
2. 개발자 도구 → Application → Cookies에서 `access_token`, `refresh_token`의 Domain, Expires, HttpOnly, SameSite 열을 본다.
3. 콘솔에서 `document.cookie`를 쳐서 두 쿠키가 보이지 않는 것을 확인한다(HttpOnly).
4. `http://alpha.blog.test:8080`으로 가서 Network 탭의 요청 헤더에 `Cookie`가 실려 있는지 본다.

---

## 8. 확인 문제

1. `alpha.blog.test`가 `Domain` 속성 없이 쿠키를 주면, `beta.blog.test` 요청에 그 쿠키가 실리는가?
<details><summary>답</summary>

실리지 않는다. Domain을 생략하면 host-only 쿠키라 정확히 `alpha.blog.test`에만 간다.
</details>

2. `Set-Cookie: a=1; Max-Age=60; Expires=(1년 뒤)`면 쿠키는 언제 지워지는가?
<details><summary>답</summary>

60초 뒤. 둘 다 있으면 Max-Age가 우선이다.
</details>

3. 로그아웃에서 `Set-Cookie: access_token=; Max-Age=0; Path=/`만 보냈는데(Domain 없음) 로그인이 유지된다. 왜인가?
<details><summary>답</summary>

원래 쿠키는 `Domain=.blog.test`였다. Domain이 다르면 다른 쿠키로 취급되어, 새 host-only 쿠키를 만들자마자 지울 뿐 원래 쿠키는 남는다. 지울 때도 같은 이름, Domain, Path로 보내야 한다.
</details>

4. `HttpOnly` 쿠키를 쓰면 XSS로부터 완전히 안전한가?
<details><summary>답</summary>

아니다. 스크립트가 토큰 값을 읽어 가는 것은 막지만, 그 페이지 안에서 API를 부르면 브라우저가 쿠키를 자동으로 붙인다. XSS 자체를 막아야 한다.
</details>

5. 이 프로젝트가 토큰을 `localStorage`에 두지 않은 가장 큰 이유는?
<details><summary>답</summary>

`localStorage`는 출처마다 따로라 `blog.test`에서 로그인해도 `alpha.blog.test`에서는 로그아웃 상태가 된다. 쿠키는 `Domain=.blog.test`로 모든 블로그 주소가 공유한다(Q6).
</details>

6. 개발 환경에서 `cookie-secure`를 `false`로 둔 이유는?
<details><summary>답</summary>

개발 서버가 `http://blog.test:8080`(HTTPS가 아님)이다. 최근 브라우저는 HTTP 페이지가 Secure 쿠키를 설정하는 것을 거부하므로 쿠키가 저장되지 않는다.
</details>

7. 로그인 유지를 고르지 않으면 `refresh_token`을 세션 쿠키로 주는데, 그것만으로는 부족해서 서버에서 무활동 30분을 따로 관리한다. 왜인가?
<details><summary>답</summary>

브라우저의 세션 복원 기능이 세션 쿠키를 되살릴 수 있고, 브라우저를 닫지 않으면 기한이 없다. 그래서 Redis의 Refresh 토큰 TTL을 30분으로 두고 요청마다 연장한다.
</details>

8. `access_token` 쿠키는 세션 쿠키인데, 로그인 유지를 고른 사람이 다음 날 브라우저를 열면 어떻게 로그인 상태가 되는가?
<details><summary>답</summary>

`access_token`은 사라졌지만 14일짜리 `refresh_token`이 남아 있다. 첫 요청에서 필터가 Refresh 토큰이 Redis에 살아 있는지 확인하고 새 Access 쿠키를 응답에 실어 준다.
</details>

---

## 9. 더 읽을거리

- RFC 6265, *HTTP State Management Mechanism* (쿠키 규격): https://www.rfc-editor.org/rfc/rfc6265
- MDN, *Using HTTP cookies*: https://developer.mozilla.org/en-US/docs/Web/HTTP/Cookies
- MDN, *Set-Cookie* 헤더(속성별 설명, 세션 복원 경고): https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie
- OWASP, *Session Management Cheat Sheet* (쿠키 속성 권장값)
- Spring Framework `ResponseCookie` API 문서
- 이어서 읽기: [11-jwt](./11-jwt.md) → [12-spring-security-filter-chain](./12-spring-security-filter-chain.md) → [13-csrf-samesite-cors](./13-csrf-samesite-cors.md)
