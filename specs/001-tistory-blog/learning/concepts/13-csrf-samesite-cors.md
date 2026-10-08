# CSRF, SameSite, CORS

> 관련 스텝: [스텝 3](../step-03.md) · 관련 결정: research.md R-03(쿠키 인증 + CSRF 대책), rest-api.md "인증과 보안"(`X-Requested-With`, 403 `CSRF_REJECTED`)

## 1. 이 문서로 배우는 것

- **출처(origin)**와 **사이트(site)**가 어떻게 다른지. 이 차이를 모르면 SameSite와 CORS가 헷갈린다
- 동일 출처 정책(Same-Origin Policy)이 막는 것과 막지 않는 것
- CSRF 공격이 어떻게 성립하는지(개념 수준), 왜 쿠키 인증에서 생기는지
- CSRF 대책들: 동기화 토큰, Double Submit 쿠키, SameSite, 사용자 지정 헤더, Fetch Metadata
- CORS 단순 요청과 사전 요청(preflight)의 조건
- SameSite `Strict`/`Lax`/`None`이 막는 것과 못 막는 것. **같은 사이트의 다른 블로그**는 SameSite로 막을 수 없다는 점
- CORS가 무엇이고 무엇이 **아닌지**(서버 보호 장치가 아니다)
- 이 프로젝트가 CORS 설정 없이 같은 출처로만 운영하는 이유
- `X-Requested-With` 헤더 방식과 `CsrfHeaderFilter`, Spring Security 기본 CSRF를 끈 이유

**먼저 알면 좋은 것**: [10-http-cookies](./10-http-cookies.md)(특히 Domain과 SameSite), [12-spring-security-filter-chain](./12-spring-security-filter-chain.md)(필터에서 요청을 막는 법), HTTP 메서드(GET, POST, PUT, DELETE)의 의미.

---

## 2. 왜 필요한가

쿠키는 **브라우저가 알아서** 붙여 보낸다. 이것이 편리함이자 위험이다.

지원이 `blog.test`에 로그인해 둔 채로, 다른 탭에서 어떤 사이트를 열었다고 하자. 그 사이트의 HTML 안에 우리 서버로 요청을 보내는 폼이 숨어 있고, 페이지가 열리자마자 자동으로 제출된다. 브라우저는 그 요청이 우리 서버로 가니까 **지원의 로그인 쿠키를 붙여** 보낸다. 서버는 "로그인한 지원이 보낸 요청"으로 알고 처리한다.

이것이 **CSRF**(Cross-Site Request Forgery, 사이트 간 요청 위조)다. 공격자는 쿠키 값을 몰라도 된다. 브라우저가 대신 붙여 준다.

토큰을 `localStorage`에 두고 `Authorization` 헤더로 보내는 방식은 이 문제가 거의 없다. 다른 사이트의 페이지는 우리 출처의 `localStorage`를 읽을 수 없어서 헤더를 만들 수 없기 때문이다. 이 프로젝트는 서브도메인 로그인 공유 때문에 **쿠키를 골랐으므로**(Q6, [10-http-cookies](./10-http-cookies.md) 3.11) CSRF 대책을 함께 떠안았다.

---

## 3. 기본 개념

### 3.1 출처(origin)와 사이트(site)

| | 정의 | 비교할 때 보는 것 |
| --- | --- | --- |
| **출처(origin)** | 스킴 + 호스트 + 포트 (RFC 6454) | 셋이 **모두** 같아야 같은 출처 |
| **사이트(site)** | 스킴 + 등록 가능한 도메인(eTLD+1) | 스킴과 eTLD+1만 같으면 같은 사이트. 하위 도메인과 포트는 무시 |

eTLD는 "공개 접미사"(public suffix)다. `com`, `co.kr`, `github.io`처럼 누구나 그 아래에 도메인을 등록할 수 있는 부분이다. eTLD+1은 거기에 한 단계를 더한 것, 즉 **실제로 누군가 소유하는 도메인**이다(`blog.com`).

```
                                   출처(origin)              사이트(site)
http://blog.test:8080            http, blog.test, 8080     http + blog.test
http://alpha.blog.test:8080      http, alpha.blog.test, 8080   http + blog.test
http://alpha.blog.test:5173      http, alpha.blog.test, 5173   http + blog.test
https://blog.test                https, blog.test, 443     https + blog.test
http://evil.example              http, evil.example, 80    http + evil.example

blog.test:8080 vs alpha.blog.test:8080   → 다른 출처, 같은 사이트
alpha.blog.test:8080 vs :5173            → 다른 출처(포트), 같은 사이트
http://blog.test vs https://blog.test    → 다른 출처, 다른 사이트(스킴이 다르면 다른 사이트로 보는 "schemeful same-site")
blog.test vs evil.example                → 다른 출처, 다른 사이트
```

이 프로젝트에서 중요한 사실: **모든 블로그 주소(`*.blog.com`)는 서로 같은 사이트다.** 지원의 블로그 `alpha.blog.com`과 낯선 사람의 블로그 `evil.blog.com`도 같은 사이트다.

### 3.2 동일 출처 정책 (Same-Origin Policy)

브라우저의 기본 보안 규칙이다. **한 출처의 스크립트는 다른 출처의 응답을 읽을 수 없다.**

| 다른 출처에 대해 | 가능? |
| --- | --- |
| 요청을 **보내기**(링크, 폼 제출, `<img src>`, 단순 `fetch`) | 대부분 가능 |
| 응답을 **읽기**(`fetch` 결과, iframe 안 DOM) | 기본적으로 불가 |
| `localStorage`, 쿠키(`document.cookie`) 읽기 | 불가 |

핵심: 동일 출처 정책은 **읽기**를 막는다. **보내기**는 대부분 막지 않는다. CSRF는 "응답을 읽을 필요 없이, 보내기만 하면 피해가 생기는" 공격이라 동일 출처 정책만으로는 막을 수 없다.

### 3.3 CSRF가 성립하는 조건

다음이 **모두** 맞으면 CSRF가 가능하다.
1. 서버가 **쿠키만으로** 사용자를 확인한다.
2. 상태를 바꾸는 요청(글 삭제, 비밀번호 변경)을 **다른 사이트에서 만들 수 있는 모양**으로 받는다(폼으로 보낼 수 있는 POST 등).
3. 그 요청에 **공격자가 미리 알 수 없는 값**이 필요 없다.

개념 그림:

```
지원의 브라우저
 ├─ 탭 1: blog.test (로그인, 쿠키 있음)
 └─ 탭 2: 악성 페이지
          <form action="http://blog.test/api/어떤-변경" method="POST"> ... </form>
          페이지가 열리면 폼을 자동 제출
              │
              ▼  브라우저: "blog.test로 가는 요청이네, blog.test 쿠키를 붙이자"
          서버: 쿠키 OK → 지원의 요청으로 처리
```

대책은 위 조건 중 하나를 깨는 것이다.

### 3.4 CSRF 대책들

| 대책 | 원리 | 깨는 조건 |
| --- | --- | --- |
| **동기화 토큰**(Synchronizer Token) | 서버가 무작위 토큰을 세션에 저장하고 폼·요청에 넣게 함. 요청의 토큰과 세션 값이 같아야 통과 | 3: 공격자는 토큰을 모름 |
| **Double Submit 쿠키** | 토큰을 쿠키와 요청 본문/헤더 양쪽에 넣고 같은지 비교(세션 불필요). 서명된 토큰을 권장 | 3 |
| **SameSite 쿠키** | 다른 사이트에서 시작된 요청에는 쿠키를 안 실음 | 1: 쿠키가 안 감 |
| **사용자 지정 헤더** | 상태 변경 API는 특정 헤더가 있어야 통과. 다른 출처는 브라우저 규칙(CORS) 때문에 그 헤더를 붙여 보낼 수 없음 | 2: 폼으로 만들 수 없는 모양 |
| **Fetch Metadata** | 브라우저가 붙이는 `Sec-Fetch-Site`(same-origin, same-site, cross-site) 헤더로 출처를 판단 | 2 |
| Origin/Referer 확인 | 요청의 `Origin` 헤더가 우리 출처인지 확인 | 2 |

OWASP *Cross-Site Request Forgery Prevention Cheat Sheet*는 토큰 방식을 기본으로, SameSite와 사용자 지정 헤더, Fetch Metadata를 추가 방어(defense in depth)로 소개한다. **어떤 CSRF 대책도 XSS 앞에서는 무력하다.** 우리 출처에서 실행되는 악성 스크립트는 토큰을 읽고, 헤더를 붙이고, 같은 출처 요청을 보낼 수 있다. 그래서 XSS 방어([14-xss-sanitize-csp](./14-xss-sanitize-csp.md))가 CSRF 방어의 전제다.

### 3.5 SameSite 자세히

| 값 | 같은 사이트 요청 | 다른 사이트에서 링크로 이동(GET, 최상위) | 다른 사이트의 폼 POST | 다른 사이트의 `<img>`, `<iframe>`, `fetch` |
| --- | --- | --- | --- | --- |
| `Strict` | 보냄 | **안 보냄** | 안 보냄 | 안 보냄 |
| `Lax` | 보냄 | **보냄** | 안 보냄 | 안 보냄 |
| `None`(+`Secure` 필수) | 보냄 | 보냄 | 보냄 | 보냄 |

- `Strict`는 가장 안전하지만, 검색 결과나 카카오톡 링크로 들어온 사용자가 첫 화면에서 로그아웃 상태로 보인다. 블로그 서비스에는 불편하다.
- `Lax`는 "다른 사이트에서 링크를 눌러 들어오는 것"은 로그인 상태로 보여 주고, 다른 사이트가 몰래 보내는 POST에는 쿠키를 안 붙인다. 그래서 **GET으로 상태를 바꾸지 않는다**는 규칙과 짝이다. GET으로 삭제하는 API가 있으면 `Lax`는 그것을 막지 못한다.
- SameSite를 지정하지 않은 쿠키는 최근 Chrome 등이 `Lax`로 취급한다(다만 Chrome은 지정하지 않은 쿠키에 한해 발급 직후 짧은 시간 동안 다른 사이트의 최상위 POST에도 쿠키를 보내는 예외를 두었다). 이 프로젝트처럼 **명시적으로 `Lax`를 주는 것**이 예측 가능하다.

**SameSite가 못 막는 것: 같은 사이트의 다른 하위 도메인.** SameSite는 "사이트"를 기준으로 판단한다. `evil.blog.com`(낯선 사람의 블로그)에서 시작된 요청은 `blog.com`과 **같은 사이트**이므로 `Lax`든 `Strict`든 쿠키가 실린다. 블로그 서비스는 다른 사람이 만든 콘텐츠가 같은 사이트 안에 있는 구조라, SameSite만으로는 부족하다. 그래서:
- 블로그 본문에서 스크립트가 실행되지 못하게 정화한다([14-xss-sanitize-csp](./14-xss-sanitize-csp.md)).
- 상태 변경 API에 사용자 지정 헤더를 요구한다. `evil.blog.com`과 `blog.com`은 같은 사이트지만 **다른 출처**라서, 헤더를 붙인 요청은 CORS 사전 요청을 거쳐야 하고 우리 서버가 허락하지 않으므로 보내지지 않는다(3.6, 3.7).

### 3.6 CORS: 무엇이고 무엇이 아닌가

CORS(Cross-Origin Resource Sharing)는 동일 출처 정책에 **구멍을 내는** 장치다. 서버가 "이 출처는 내 응답을 읽어도 된다"고 응답 헤더로 허락한다.

```
요청:  Origin: https://other.example
응답:  Access-Control-Allow-Origin: https://other.example
       Access-Control-Allow-Credentials: true      ← 쿠키를 포함한 요청의 응답도 읽게 하려면
```

**CORS가 아닌 것**:
- 서버를 보호하는 장치가 아니다. CORS 헤더가 없어도 **단순 요청은 서버에 도착하고 처리된다**. 브라우저가 그 응답을 스크립트에게 **보여 주지 않을** 뿐이다.
- 그래서 "CORS를 안 열었으니 다른 사이트가 우리 API를 못 부른다"는 틀린 말이다. 폼 POST 같은 단순 요청은 그대로 도착한다. 이것이 CSRF가 존재하는 이유다.
- curl, 서버 간 호출, 모바일 앱에는 CORS가 없다. 브라우저의 규칙일 뿐이다.

### 3.7 단순 요청과 사전 요청(preflight)

다른 출처로 `fetch`할 때, 브라우저는 요청을 두 종류로 나눈다(Fetch 표준).

**단순 요청**: 아래를 모두 만족. 바로 보낸다(응답 읽기만 CORS로 판단).
- 메서드가 `GET`, `HEAD`, `POST` 중 하나
- 직접 넣은 헤더가 CORS 허용 목록(`Accept`, `Accept-Language`, `Content-Language`, `Content-Type`, `Range`)뿐
- `Content-Type`이 `application/x-www-form-urlencoded`, `multipart/form-data`, `text/plain` 중 하나

HTML 폼이 만들 수 있는 요청은 전부 단순 요청이다(폼은 이 세 Content-Type만 쓸 수 있고 헤더를 못 넣는다).

**사전 요청이 필요한 요청**: 하나라도 벗어나면.
- `PUT`, `DELETE`, `PATCH`
- `X-Requested-With` 같은 사용자 지정 헤더
- `Content-Type: application/json`

브라우저는 본 요청 전에 먼저 묻는다.

```
OPTIONS /api/posts/15
Origin: http://evil.blog.test:8080
Access-Control-Request-Method: DELETE
Access-Control-Request-Headers: x-requested-with

→ 서버가 Access-Control-Allow-Origin 등을 주지 않으면
  브라우저는 본 요청(DELETE)을 **보내지 않는다**
```

이것이 "사용자 지정 헤더" 대책이 동작하는 원리다. 다른 출처는 그 헤더를 붙인 요청을 **보낼 수조차 없고**, 헤더 없이 보내면 서버가 거절한다.

### 3.8 이 프로젝트가 CORS 설정을 하지 않는 이유

이 프로젝트는 **화면과 API가 항상 같은 출처**에 있게 만들었다.

| 환경 | 화면 | API | 출처 |
| --- | --- | --- | --- |
| 운영 | `alpha.blog.com/` (jar 안의 index.html) | `alpha.blog.com/api/...` | 같음 |
| 개발(서버만) | `alpha.blog.test:8080/` | `alpha.blog.test:8080/api/...` | 같음 |
| 개발(Vite) | `alpha.blog.test:5173/` | `alpha.blog.test:5173/api/...` → Vite가 8080으로 넘김 | 브라우저 입장에서 같음 |

프론트는 API를 항상 **상대 경로**(`/api/...`)로 부르므로 지금 보고 있는 주소와 같은 출처로 간다. CORS를 열 필요가 없고, 열지 않았으므로 다른 출처(다른 블로그 포함)는 사용자 지정 헤더를 붙인 요청을 보낼 수 없다. CORS를 열지 않는 것 자체가 방어의 일부다.

주의: 블로그 주소 화면에서 **플랫폼 전용 API**(rest-api.md의 Host 범위 P)를 직접 부르면 다른 출처가 된다. 그런 기능(로그인, 가입)은 플랫폼 주소의 화면으로 이동해서 처리한다(T015의 "401 → 플랫폼 로그인 후 원래 주소 복귀").

### 3.9 Spring Security 기본 CSRF를 끈 이유

Spring Security는 기본으로 `CsrfFilter`(동기화 토큰 방식)를 켠다. POST·PUT·PATCH·DELETE 요청에 CSRF 토큰이 없으면 403을 준다. 토큰은 기본적으로 **HttpSession**에 저장한다.

이 프로젝트가 끈 이유:
- 세션을 쓰지 않는다(`STATELESS`, [12-spring-security-filter-chain](./12-spring-security-filter-chain.md) 3.6). 세션 저장소 대신 쿠키 저장소(`CookieCsrfTokenRepository`)를 쓰는 방법도 있지만, SPA가 토큰 쿠키를 읽어 헤더로 다시 보내야 해서 구성이 늘어난다.
- R-03 결정이 "SameSite=Lax + 사용자 지정 헤더 확인 **또는** CSRF 토큰"이었고, 같은 출처 SPA + JSON API 구조에서는 헤더 방식이 단순하다.

끈다는 것은 "CSRF 대책을 안 한다"가 아니라 "**다른 방식으로 직접** 한다"는 뜻이다. 대신 그 대책(`CsrfHeaderFilter`)을 테스트로 확인해야 한다.

---

## 4. 동작 원리

### 4.1 여러 경로의 요청이 어떻게 처리되나

```
(가) 우리 화면의 fetch, POST /api/posts, X-Requested-With 있음, 같은 출처
     → 쿠키 실림, 헤더 있음 → CsrfHeaderFilter 통과 → 처리

(나) 다른 사이트(evil.example)의 숨은 폼, POST /api/posts
     → 단순 요청이라 서버에 도착
     → SameSite=Lax: 다른 사이트의 POST라 쿠키 안 실림 → 비회원
     → 헤더도 없음 → CsrfHeaderFilter가 403 CSRF_REJECTED

(다) 같은 사이트 다른 블로그(evil.blog.test)의 숨은 폼, POST /api/posts
     → 같은 사이트라 SameSite=Lax여도 쿠키 실림!
     → 하지만 폼은 헤더를 못 넣음 → CsrfHeaderFilter가 403 CSRF_REJECTED

(라) evil.blog.test의 스크립트(본문 정화를 뚫었다고 가정)가 fetch로 헤더를 넣어 POST
     → 다른 출처 + 사용자 지정 헤더 → 사전 요청(OPTIONS)
     → 우리 서버는 CORS 허용 헤더를 주지 않음 → 브라우저가 본 요청을 안 보냄

(마) 다른 사이트의 링크를 눌러 GET /some-page 로 이동
     → Lax: 최상위 GET 이동이라 쿠키 실림 → 로그인 상태로 보임(의도한 동작)
     → GET은 상태를 바꾸지 않으므로 안전
```

(다)가 SameSite만으로는 부족하고 헤더 확인이 필요한 이유, (라)가 CORS를 열지 않는 것이 방어인 이유다.

### 4.2 CSRF 대책이 판단하지 않는 요청

- `GET`, `HEAD`, `OPTIONS`: 상태를 바꾸지 않는다는 약속이 있으므로 검사하지 않는다. **API 설계에서 GET으로 상태를 바꾸지 않아야** 이 전제가 성립한다.
- `/api/`가 아닌 경로: 화면 주소(HTML)는 GET뿐이다.

---

## 5. 이 프로젝트에서는

### 5.1 `CsrfHeaderFilter`

경로: `src/main/java/com/nhnacademy/blog/global/auth/CsrfHeaderFilter.java`

```java
/**
 * 쿠키 인증의 CSRF 대책 (R-03). 상태를 바꾸는 API 요청은 X-Requested-With: XMLHttpRequest가 있어야 한다.
 * 다른 사이트의 폼이나 단순 요청은 이 헤더를 붙일 수 없다. SameSite=Lax 쿠키와 함께 쓴다.
 */
public class CsrfHeaderFilter extends OncePerRequestFilter {

    public static final String HEADER = "X-Requested-With";
    public static final String EXPECTED_VALUE = "XMLHttpRequest";

    private static final Set<String> STATE_CHANGING_METHODS = Set.of("POST", "PUT", "PATCH", "DELETE");

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        boolean stateChanging = STATE_CHANGING_METHODS.contains(request.getMethod());   // GET 등은 검사 안 함
        boolean api = request.getRequestURI().startsWith("/api/");                      // API만
        if (stateChanging && api && !EXPECTED_VALUE.equals(request.getHeader(HEADER))) {
            errorResponseWriter.write(response, ErrorCode.CSRF_REJECTED);               // 403 + COM-02 JSON
            return;                                                                      // 컨트롤러에 안 감
        }
        chain.doFilter(request, response);
    }
}
```

- `X-Requested-With: XMLHttpRequest`는 jQuery 시절부터 "자바스크립트가 보낸 요청"을 표시하던 관례적인 헤더다. 값 자체에 비밀은 없다. 중요한 것은 **값이 아니라 "사용자 지정 헤더가 있다"는 사실**이다. 그것이 단순 요청이 아니라는 증거이고, 다른 출처는 CORS 허락 없이 그런 요청을 보낼 수 없다.
- 보안 필터 체인에서 `JwtAuthenticationFilter`보다 앞이라, 헤더가 없으면 토큰 검사와 DB 조회 없이 바로 거절된다([12-spring-security-filter-chain](./12-spring-security-filter-chain.md) 3.3).

### 5.2 기본 CSRF 끄기와 SameSite

`src/main/java/com/nhnacademy/blog/global/config/SecurityConfig.java`:

```java
.csrf(AbstractHttpConfigurer::disable)
...
.addFilterBefore(csrfFilter, AnonymousAuthenticationFilter.class)
```

`src/main/java/com/nhnacademy/blog/global/auth/AuthCookieManager.java`:

```java
ResponseCookie.from(name, value)
        .domain(domainProperties.cookieDomain())
        ...
        .sameSite("Lax");
```

### 5.3 프론트가 헤더를 붙이는 곳

`frontend/src/api/client.ts`:

```ts
export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? 'GET'
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (method !== 'GET') {
    headers['X-Requested-With'] = 'XMLHttpRequest'     // 상태를 바꾸는 요청에 자동으로
  }
  ...
  const response = await fetch(path, {
    method,
    headers,
    credentials: 'same-origin',                          // 같은 출처에만 쿠키(기본값과 같음)
    ...
  })
```

- 모든 API 호출이 이 함수를 거치므로, 화면 코드에서 헤더를 잊을 일이 없다.
- `path`가 항상 `/api/...` 상대 경로라 지금 주소와 같은 출처로 간다(3.8).
- `credentials: 'same-origin'`: 같은 출처 요청에만 쿠키를 싣는다. 실수로 다른 출처를 부르더라도 로그인 쿠키가 따라가지 않는다.

### 5.4 같은 출처를 만드는 설정

`frontend/vite.config.ts`:

```ts
server: {
  allowedHosts: ['.blog.test'],         // alpha.blog.test:5173 으로도 열 수 있게
  proxy: {
    '/api': 'http://localhost:8080',    // 브라우저는 5173에 보내고, Vite가 8080으로 넘김
    '/uploads': 'http://localhost:8080',
  },
},
```

`allowedHosts`는 Vite 개발 서버가 모르는 Host 헤더의 요청을 거절하게 하는 장치(DNS rebinding 대책)다. `.blog.test`로 시작점을 주면 그 하위 도메인을 허용한다. 다른 Host로 오면 403이다.

### 5.5 테스트

`src/test/java/com/nhnacademy/blog/global/auth/AuthenticationIntegrationTest.java`:

```java
@Test
void stateChangingApiNeedsCsrfHeader() throws Exception {
    mockMvc.perform(post("/api/test/echo"))
            .andExpect(status().isForbidden())
            .andExpect(jsonPath("$.code").value("CSRF_REJECTED"));
    mockMvc.perform(post("/api/test/echo").header(CsrfHeaderFilter.HEADER, CsrfHeaderFilter.EXPECTED_VALUE))
            .andExpect(status().isOk());
}
```

다른 테스트들도 POST·PUT 요청마다 이 헤더를 붙인다. 붙이지 않으면 403이라 모든 테스트가 이 대책을 간접적으로 확인한다.

---

## 6. 자주 하는 실수와 함정

1. **GET으로 상태를 바꾼다.** `GET /api/posts/15/delete` 같은 API는 `Lax` 쿠키가 실리는 링크 이동으로 실행될 수 있고, 헤더 검사도 GET을 보지 않는다.
2. **"CORS를 안 열었으니 CSRF가 없다."** 단순 요청(폼 POST)은 CORS와 상관없이 서버에 도착한다.
3. **"SameSite=Lax니까 끝."** 같은 사이트의 다른 하위 도메인(다른 사람의 블로그)은 막지 못한다.
4. **CORS를 `Access-Control-Allow-Origin: *` + 쿠키로 연다.** 브라우저는 자격 증명(쿠키)이 있는 요청에 `*`를 허락하지 않는다. 그래서 요청 `Origin`을 그대로 되돌려 주는 설정을 하는 경우가 있는데, 그러면 **모든 출처**가 사용자 지정 헤더를 붙여 보낼 수 있게 되어 헤더 대책이 무너진다. CORS를 열 때는 허용 출처를 명시한다.
5. **JSON API는 폼으로 못 보내니 안전하다고 생각한다.** 서버가 `Content-Type`을 엄격히 확인하지 않으면 `text/plain` 폼으로 JSON 모양의 본문을 보낼 수 있다. 헤더 검사는 본문 모양과 상관없이 막는다.
6. **기본 CSRF를 끄고 대체 대책을 안 만든다.** "STATELESS니까 CSRF가 필요 없다"는 말은 토큰을 헤더로 보낼 때만 맞다. 쿠키 인증이면 필요하다.
7. **XSS를 방치한다.** 우리 출처에서 실행되는 스크립트는 헤더를 붙이고 같은 출처 요청을 보낼 수 있어 모든 CSRF 대책을 우회한다.

---

## 7. 직접 해 보기

### 실습 1: curl로 헤더 대책 보기

```bash
curl -i -X POST localhost:8080/api/anything                                         # 403 CSRF_REJECTED
curl -i -X POST -H "X-Requested-With: XMLHttpRequest" localhost:8080/api/anything   # 404 NOT_FOUND (필터 통과)
curl -i localhost:8080/api/anything                                                 # GET은 검사 안 함 → 404
```

curl은 브라우저가 아니라서 헤더를 마음대로 붙일 수 있다. 그래서 헤더 대책은 "공격자의 도구"가 아니라 "**피해자의 브라우저**"를 이용한 공격을 막는 장치라는 점을 기억한다.

### 실습 2: 출처와 사이트 판별 연습

다음 쌍이 같은 출처인지, 같은 사이트인지 표로 정리해 본다.
- `http://blog.test:8080` / `http://blog.test:5173`
- `http://alpha.blog.test` / `http://beta.blog.test`
- `https://blog.com` / `http://blog.com`
- `https://user.github.io` / `https://other.github.io` (`github.io`는 공개 접미사)

마지막 쌍은 공개 접미사 때문에 **다른 사이트**다. `github.io`가 공개 접미사 목록에 있어서, 그 아래의 각 사용자 페이지가 서로 다른 "등록 가능한 도메인"이 된다.

### 실습 3: 브라우저에서 사전 요청 보기 (스텝 4 이후)

1. `http://alpha.blog.test:8080`을 열고 개발자 도구 콘솔에서 **다른 출처**로 헤더를 붙여 요청해 본다.
   ```js
   fetch('http://beta.blog.test:8080/api/test', { method: 'POST', headers: { 'X-Requested-With': 'XMLHttpRequest' } })
   ```
2. 콘솔에 CORS 오류가 나고, Network 탭에 `OPTIONS` 요청만 보이고 `POST`는 나가지 않은 것을 확인한다.
3. 같은 출처(`fetch('/api/...', ...)`)로 바꾸면 사전 요청 없이 바로 간다.

### 실습 4: SameSite를 바꿔 보기

`AuthCookieManager`의 `.sameSite("Lax")`를 `"Strict"`로 바꾸고, 다른 사이트(예: 로컬 파일로 연 HTML의 `<a href="http://blog.test:8080/">`)에서 링크를 눌러 들어오면 첫 요청에 쿠키가 실리는지 Network 탭에서 확인한다. `Strict`에서는 안 실린다. 되돌린다.

---

## 8. 확인 문제

1. `http://alpha.blog.test:8080`과 `http://beta.blog.test:8080`은 같은 출처인가? 같은 사이트인가?
<details><summary>답</summary>

다른 출처(호스트가 다름), 같은 사이트(eTLD+1이 `blog.test`로 같음).
</details>

2. 동일 출처 정책이 있는데도 CSRF가 가능한 이유는?
<details><summary>답</summary>

동일 출처 정책은 다른 출처의 응답을 **읽는 것**을 막을 뿐, 요청을 **보내는 것**(폼 제출 등)은 막지 않는다. CSRF는 응답을 읽지 않아도 요청이 처리되기만 하면 피해가 생긴다.
</details>

3. 쿠키에 `SameSite=Lax`를 줬는데도 헤더 확인(`CsrfHeaderFilter`)이 필요한 이유를 이 서비스의 구조로 설명하라.
<details><summary>답</summary>

모든 블로그가 같은 사이트(`*.blog.com`)라, 다른 사람의 블로그에서 시작된 요청에도 Lax 쿠키가 실린다. 그 블로그는 다른 출처이므로 사용자 지정 헤더를 붙여 보낼 수 없고(폼은 불가, fetch는 사전 요청에서 막힘), 헤더 확인이 이것을 막는다.
</details>

4. `X-Requested-With` 헤더의 **값**이 비밀이 아닌데도 대책이 되는 이유는?
<details><summary>답</summary>

중요한 것은 값이 아니라 사용자 지정 헤더가 있다는 사실이다. 그런 요청은 단순 요청이 아니라서, 다른 출처는 CORS 사전 요청을 통과해야만 보낼 수 있다. 서버가 CORS를 허락하지 않으므로 보낼 수 없다. HTML 폼은 헤더를 아예 넣을 수 없다.
</details>

5. CORS 설정을 하지 않으면 다른 사이트의 폼 POST가 서버에 도착하지 않는가?
<details><summary>답</summary>

도착한다. 폼 POST는 단순 요청이라 사전 요청 없이 보내지고 서버가 처리한다. CORS는 브라우저가 응답을 스크립트에 보여 줄지 정할 뿐이다.
</details>

6. Spring Security의 기본 CSRF를 끈 것은 CSRF 대책을 포기한 것인가?
<details><summary>답</summary>

아니다. 세션 기반 토큰 방식 대신 SameSite=Lax 쿠키 + 사용자 지정 헤더 확인(`CsrfHeaderFilter`)으로 직접 막는다(R-03).
</details>

7. 이 프로젝트가 CORS 설정 없이 동작하는 이유는?
<details><summary>답</summary>

화면과 API가 항상 같은 출처에 있다. 운영과 서버 단독 개발은 같은 서버가 HTML과 API를 함께 주고, Vite 개발 서버는 `/api`를 프록시로 넘겨 브라우저 입장에서 같은 출처다. 프론트는 API를 상대 경로로 부른다.
</details>

8. XSS가 생기면 CSRF 대책이 왜 소용없어지는가?
<details><summary>답</summary>

우리 출처에서 실행되는 스크립트는 같은 출처 요청을 보낼 수 있고, 사용자 지정 헤더를 붙이거나 토큰을 읽을 수 있다. 브라우저 입장에서 정상 요청과 구분할 수 없다.
</details>

---

## 9. 더 읽을거리

- OWASP, *Cross-Site Request Forgery Prevention Cheat Sheet*: https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html
- MDN, *Same-origin policy*: https://developer.mozilla.org/en-US/docs/Web/Security/Same-origin_policy
- MDN, *Cross-Origin Resource Sharing (CORS)*(단순 요청, 사전 요청): https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS
- MDN, *Set-Cookie – SameSite*
- web.dev, *Understanding "same-site" and "same-origin"*
- RFC 6454, *The Web Origin Concept*
- Public Suffix List: https://publicsuffix.org/
- Spring Security 레퍼런스, *Cross Site Request Forgery (CSRF)*
- 이어서 읽기: [14-xss-sanitize-csp](./14-xss-sanitize-csp.md)
