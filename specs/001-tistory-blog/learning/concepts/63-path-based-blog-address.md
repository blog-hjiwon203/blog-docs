# 63. 블로그 주소를 경로로: 서브도메인에서 `blog.com/@주소`로

> 관련 스텝: [스텝 21](../step-21.md) (T116~T119, 2026-10-12 지원 결정) · 관련 개념: [15 서브도메인과 Host 라우팅](./15-subdomain-host-routing.md)(꼭 먼저, 바뀌기 전 구조), [10 HTTP 쿠키](./10-http-cookies.md), [13 CSRF, SameSite, CORS](./13-csrf-samesite-cors.md), [18 SPA와 서버 라우팅](./18-spa-server-routing.md), [19 React Router와 API 클라이언트](./19-react-router-api-client.md), [43 Open Graph](./43-open-graph-preview.md), [61 소셜 로그인](./61-oauth-social-login.md)(열린 리다이렉트)

## 1. 이 문서로 배우는 것

- 서브도메인 주소(`alpha.blog.com`)와 경로 주소(`blog.com/@alpha`)가 DNS·인증서·웹 서버(nginx `server_name`)에서 각각 무엇을 요구하는지, 그리고 배포 환경 때문에 바꿀 수밖에 없었던 이유
- API가 "어느 블로그에 대한 요청인지"를 아는 세 방법: **Host 헤더**, **사용자 지정 헤더**, **경로 한 칸**. 이 프로젝트가 고른 ①안(`X-Blog-Address` 헤더)과 고르지 않은 ②안(`/api/blogs/{주소}/…`)의 저울질
- 사용자 지정 요청 헤더가 CORS·CSRF와 어떻게 얽히는지(같은 출처라서 문제가 없는 이유)
- 쿠키 `Domain` 속성: **host-only 쿠키**와 **도메인 쿠키**, 예전에는 `Domain`이 꼭 필요했고 지금은 필요 없는 이유
- `/@주소/…` 화면 주소를 서버가 먼저 확인하기(404, 이사 301, 공유 미리보기)
- React Router `basename`으로 블로그 화면 안의 링크를 그대로 두기
- 같은 출처 기준으로 열린 리다이렉트 막기
- Spring 경로 패턴(`{이름:정규식}`)에 `/`를 넣으면 서버가 뜨지 않는 함정

**먼저 알면 좋은 것**: [15](./15-subdomain-host-routing.md)의 DNS·Host 헤더·`@CurrentBlog`, [10](./10-http-cookies.md)의 Domain 속성, [18](./18-spa-server-routing.md)의 `SpaForwardController`, [19](./19-react-router-api-client.md)의 `BrowserRouter`·`api()`. 이 문서는 그 위에서 "무엇이 바뀌었고 왜"를 다룬다.

## 2. 왜 필요한가

스텝 3부터 블로그 주소는 티스토리처럼 서브도메인이었다(`alpha.blog.com`, [15](./15-subdomain-host-routing.md)). 개발 컴퓨터에서는 `/etc/hosts`나 dnsmasq로 `*.blog.test`를 모두 내 컴퓨터로 보내서 잘 돌았다.

배포할 곳은 학교 서버다. 학교 nginx가 `now-log.java21.net` **한 이름**을 받아 우리 앱(포트 8460)으로 넘겨 준다. 여기서 문제가 드러났다.

```
now-log.java21.net          → DNS에 있음 → 학교 nginx → 우리 앱      ✔
alpha.now-log.java21.net    → DNS에 없음 → 브라우저가 "그런 이름 없음"  ✘ (서버까지 오지도 않음)
```

서브도메인 블로그를 열려면 DNS에 와일드카드 레코드(`*.now-log.java21.net`)가 있어야 하고, 학교 nginx도 그 이름들을 우리 앱으로 넘기게 설정돼 있어야 하며, HTTPS라면 와일드카드 인증서까지 필요하다. 셋 다 우리가 손댈 수 없는 학교 쪽 설정이다. [15](./15-subdomain-host-routing.md) 3.6에서 본 것처럼 DNS에서 실패한 요청은 서버 코드로 고칠 수 없다.

그래서 블로그 주소를 **플랫폼 주소 아래의 경로**로 바꿨다(research.md R-04, 2026-10-12 지원 결정).

```
전: http://alpha.blog.com/12          http://alpha.blog.com/manage/write
후: http://blog.com/@alpha/12         http://blog.com/@alpha/manage/write
```

이름이 하나뿐이니 DNS·nginx·인증서는 지금 그대로 충분하다. 대신 코드에서 "어느 블로그인가"를 Host로 알던 곳을 모두 바꿔야 했다. 이 문서는 그 바꾼 자리들과, 각 자리에서 고른 방법의 이유를 다룬다.

## 3. 기본 개념

### 3.1 서브도메인 주소와 경로 주소가 각각 요구하는 것

| | 서브도메인 `alpha.blog.com/12` | 경로 `blog.com/@alpha/12` |
| --- | --- | --- |
| DNS | `*.blog.com` 와일드카드 레코드 | `blog.com` 레코드 하나 |
| 웹 서버(nginx) | `server_name`에 `*.blog.com`(또는 `.blog.com`)도 받게 | `server_name blog.com` 하나 |
| HTTPS 인증서 | `*.blog.com` 와일드카드 인증서(Let's Encrypt는 DNS-01로만) | `blog.com` 인증서 하나 |
| 로컬 개발 | hosts에 블로그마다 한 줄, 또는 dnsmasq | hosts에 `blog.test` 한 줄 |
| 출처(origin) | 블로그마다 다른 출처 | 모든 블로그가 **한 출처** |
| 로그인 쿠키 공유 | `Domain=.blog.com` 도메인 쿠키가 필요 | host-only 쿠키로 저절로 |
| 서버가 블로그를 아는 곳 | Host 헤더 | 화면은 경로, API는 따로 정해야 함(3.3) |

**가상 호스트와 `server_name`.** nginx는 한 IP·포트로 온 요청을 Host 헤더로 나눠 다른 사이트로 보낸다([15](./15-subdomain-host-routing.md) 3.8). 그 기준이 `server` 블록의 `server_name`이다.

```nginx
server {
    listen 80;
    server_name now-log.java21.net;          # 이 이름으로 온 요청만
    location / { proxy_pass http://127.0.0.1:8460; }
}
```

서브도메인 블로그를 받으려면 `server_name now-log.java21.net *.now-log.java21.net;`처럼 와일드카드 이름도 적어야 한다(nginx 설명서의 "Server names": `*.example.org`, 또는 `example.org`와 그 아래를 함께 뜻하는 `.example.org`). 학교 nginx는 학생마다 이름 하나를 정해 넘겨 주는 구조라 이것을 기대할 수 없었다. 그리고 nginx가 받아 주더라도 DNS에 와일드카드 레코드가 없으면 요청이 nginx까지 오지도 않는다.

**경로 방식에서 `@`를 붙이는 이유.** 플랫폼 화면에는 이미 `/login`, `/me`, `/admin`, `/search` 같은 경로가 있다. 블로그 주소를 그냥 첫 칸에 두면(`blog.com/alpha`) `login`이라는 블로그와 로그인 화면을 구분할 수 없고, 나중에 플랫폼 화면을 더할 때마다 이미 있는 블로그 주소와 부딪힐 수 있다. 블로그 주소는 영문 소문자·숫자·하이픈만 쓰므로 `@`로 시작하는 첫 칸은 **블로그만** 쓸 수 있다. 미디엄·벨로그처럼 `@`를 쓰는 서비스가 흔한 것도 같은 이유다.

### 3.2 화면 주소와 API 주소는 따로 생각한다

SPA에서 요청은 두 종류다([18](./18-spa-server-routing.md)).

| 요청 | 누가 보내나 | 예 |
| --- | --- | --- |
| 화면 주소 | 브라우저 주소창(새로고침, 링크, 북마크) | `GET /@alpha/12` (HTML) |
| API | 화면의 자바스크립트(`fetch`) | `GET /api/posts/12` (JSON) |

화면 주소는 사람이 보고 공유하는 주소라서 `/@alpha/12`로 바꾸는 것이 이번 일의 목적이다. API 주소는 사람이 보지 않는다. 예전에는 화면과 API가 같은 호스트(`alpha.blog.com`)였으니 API도 Host로 블로그를 알았다. 이제 API의 호스트는 언제나 `blog.com`이라 Host에는 블로그 정보가 없다. **API에게 블로그를 알려 줄 다른 길**이 필요하다.

### 3.3 "어느 블로그"를 API에 알리는 세 방법

| 방법 | 예 | 장점 | 단점 |
| --- | --- | --- | --- |
| Host 헤더 | `Host: alpha.blog.com` + `GET /api/posts/12` | 주소에 드러나지 않음, 화면과 같은 기준 | 서브도메인이 있어야 함. 이번에 쓸 수 없게 됨 |
| **사용자 지정 헤더 (①안)** | `X-Blog-Address: alpha` + `GET /api/posts/12` | API 경로가 그대로, 바꿀 곳이 "헤더를 읽는 곳" 하나 | 주소만 보고는 어느 블로그인지 모름(로그, 캐시에서 헷갈릴 수 있음) |
| 경로 한 칸 (②안) | `GET /api/blogs/alpha/posts/12` | 주소만 보고 블로그를 앎, REST 교과서에 가까움 | 블로그 API 59개의 경로·계약·테스트·프론트 호출을 모두 바꿈 |

①안을 고른 이유는 **바꾸는 범위**다. 이 프로젝트의 블로그 API는 모두 `@CurrentBlog Blog blog` 인자 하나로 블로그를 받는다([15](./15-subdomain-host-routing.md) 5.4). 그 인자를 만드는 곳이 Host 대신 헤더를 읽게 바꾸면, 59개 API의 컨트롤러·계약(rest-api.md)·테스트 경로가 그대로다. ②안은 더 "정석"처럼 보이지만, 같은 기능을 하는 코드를 바꾸는 양이 훨씬 많고 계약 문서 전체를 고쳐야 한다. 이것이 지원이 정한 저울질이다(research.md R-04 "고르지 않은 대안").

①안에서 지킨 규칙:

- 헤더가 **없으면 플랫폼** 요청이다(`GET /api/home/posts` 같은 플랫폼 API는 아무것도 붙이지 않는다).
- 헤더의 주소가 규칙에 맞지 않거나 예약어면, 없는 블로그와 같이 **404**다.
- 같은 경로가 플랫폼과 블로그에서 다른 일을 하는 `GET /api/search`([15](./15-subdomain-host-routing.md) 5.7)는 이제 Host가 아니라 **헤더가 있는지**로 나눈다.

**헤더는 "어느 블로그"를 고르는 값이지 권한이 아니다.** 누구나 curl로 `X-Blog-Address: 아무거나`를 붙일 수 있다. 괜찮다. 예전 Host도 마찬가지로 아무나 바꿀 수 있는 값이었다. 블로그를 고른 **다음에** 서버가 그 블로그를 볼 수 있는지(가시성, [16](./16-authorization-visibility.md)), 주인인지(`BlogOwnerGuard`)를 로그인 쿠키로 따로 검사한다. "주소창에 다른 블로그 주소를 치는 것"과 같은 일이라 새로운 위험이 생기지 않는다.

### 3.4 사용자 지정 헤더와 CORS·CSRF

[13](./13-csrf-samesite-cors.md) 3.7에서 본 대로, **다른 출처**로 보내는 `fetch`에 사용자 지정 헤더(`X-Blog-Address`, `X-Requested-With`)를 넣으면 브라우저가 먼저 OPTIONS 사전 요청(preflight)을 보내고, 서버가 허락하지 않으면 본 요청을 보내지 않는다.

이 프로젝트에서는 문제가 되지 않는다. 화면과 API가 **같은 출처**이기 때문이다.

| 환경 | 화면 | API | 출처 |
| --- | --- | --- | --- |
| 운영 | `http://now-log.java21.net/@alpha/12` | `http://now-log.java21.net/api/posts/12` | 같음 |
| 개발(서버만) | `http://blog.test:8080/@alpha/12` | `http://blog.test:8080/api/...` | 같음 |
| 개발(Vite) | `http://blog.test:5173/@alpha/12` | `http://blog.test:5173/api/...` → Vite가 8080으로 넘김 | 브라우저 입장에서 같음 |

같은 출처 요청에는 CORS 규칙이 아예 적용되지 않으므로 사전 요청도 없다. 이미 상태를 바꾸는 요청마다 `X-Requested-With`를 붙이고 있었던 것과 같은 상황이다.

오히려 경로 방식이 되면서 출처 관계가 **더 단순**해졌다.

```
전: blog.test:8080 / alpha.blog.test:8080 / beta.blog.test:8080  → 서로 다른 출처, 같은 사이트
후: blog.test:8080 (/, /@alpha, /@beta 모두)                     → 한 출처
```

- **CSRF 대책은 그대로 필요하다.** 다른 사이트의 숨은 폼은 여전히 우리 주소로 POST를 보낼 수 있다. `X-Requested-With` 검사(`CsrfHeaderFilter`)와 `SameSite=Lax`는 바뀌지 않는다. 다른 사이트의 스크립트는 다른 출처라 `X-Requested-With`를 붙이면 사전 요청에서 막힌다.
- **대신 한 출처라서 XSS의 영향이 넓어진다.** 예전에는 `evil.blog.com`의 스크립트가 `alpha.blog.com`의 API 응답을 읽을 수 없었다(다른 출처). 이제는 `/@evil/12`에서 돈 스크립트도 같은 출처라서 `X-Requested-With`를 붙여 어떤 API든 로그인한 사람의 이름으로 부를 수 있다. 본문 정화(OWASP Sanitizer + DOMPurify)와 CSP([14](./14-xss-sanitize-csp.md))가 지금은 더 중요한 방어선이다. [15](./15-subdomain-host-routing.md) 3.10 표의 "모든 블로그가 같은 출처라 한 블로그의 XSS가 전체에 영향"이 바로 이것이다.

### 3.5 쿠키 Domain: host-only 쿠키와 도메인 쿠키

[10](./10-http-cookies.md) 3.4의 요약:

| `Set-Cookie`에 | 이름 | 어디로 보내나 |
| --- | --- | --- |
| `Domain` 없음 | host-only 쿠키 | 쿠키를 준 그 호스트에만(`blog.test`에만, `alpha.blog.test`에는 안 감) |
| `Domain=blog.test` | 도메인 쿠키 | `blog.test`와 그 아래 모든 호스트 |

둘 다 **포트와 경로의 앞부분**은 따로 따진다(포트는 보지 않고, 경로는 `Path` 속성으로).

**예전에는 Domain이 꼭 필요했다.** 로그인은 플랫폼(`blog.test`)에서 하고, 글쓰기는 내 블로그(`alpha.blog.test`)에서 한다. host-only 쿠키면 `alpha.blog.test`로 가는 순간 로그아웃 상태가 된다. 그래서 `Domain=.blog.test`로 줘서 모든 블로그 주소가 같은 로그인 쿠키를 받게 했다.

**지금은 Domain이 필요 없다.** 플랫폼과 모든 블로그 화면이 한 호스트(`blog.test`)라서, host-only 쿠키도 `/`, `/@alpha/manage`, `/@beta/12` 어디서든 같이 간다(`Path=/`). 그리고 필요 없는 범위를 열어 두지 않는 것이 안전하다. 도메인 쿠키는 그 아래 **모든** 호스트로 가므로, 같은 도메인 아래에 다른 서비스가 생기면 그 서비스에도 로그인 쿠키가 간다.

그래서 로그인(access·refresh), 기기(device), 비회원 방문자(visitor_id), 소셜 state(oauth_state) 쿠키 모두 `Domain`을 뺐다(research.md R-03).

> **Path로 블로그마다 쿠키를 나누면?** `Path=/@alpha`로 주면 그 쿠키는 `/@alpha/…` 요청에만 간다. 하지만 RFC 6265(8.6절)가 밝히듯 Path는 **보안 경계가 아니다**. 같은 출처의 다른 경로에서 돈 스크립트가 그 경로의 페이지를 열어 접근할 수 있다. 블로그 사이의 분리를 쿠키 경로에 기대지 않는다.

덤으로, 쿠키에 Domain이 없으니 `http://localhost:8080`으로 열어도 로그인이 된다(예전에는 `localhost` 응답의 `Domain=.blog.test` 쿠키를 브라우저가 버렸다, [10](./10-http-cookies.md) 3.4). 다만 메일·소셜 로그인 링크는 설정된 플랫폼 주소(`blog.test`)로 만들어지므로 개발은 여전히 `blog.test`로 연다.

### 3.6 SPA 서버 라우팅: `/@주소/…`

[18](./18-spa-server-routing.md)의 원칙은 그대로다. 서버가 화면 주소를 먼저 확인하고 `index.html`을 준다.

| 요청 | 전(서브도메인) | 후(경로) |
| --- | --- | --- |
| 블로그 첫 화면 | `alpha.blog.com/` | `blog.com/@alpha` |
| 없는 블로그 | `nobody.blog.com/` → 404 | `blog.com/@nobody` → 404 |
| 예약어 | `admin.blog.com/` → 404 | `blog.com/@admin` → 404 |
| 이사한 블로그 | `old.blog.com/category/3` → 301 `new.blog.com/category/3` | `/@old/category/3` → 301 `/@new/category/3` |
| 다른 블로그 소속 글 | `beta.blog.com/15` → 301 `alpha.blog.com/15` | `/@beta/15` → 301 `/@alpha/15` |
| 공유 미리보기 `og:url` | `http://alpha.blog.com/15` | `http://blog.com/@alpha/15` |
| 공유 미리보기 `og:image` | `http://alpha.blog.com/uploads/…` | `http://blog.com/uploads/…` (`/@alpha`를 붙이지 않음) |
| 플랫폼 화면 | Host가 `blog.com` | `/@`로 시작하지 않는 모든 경로 |

바뀐 것은 "블로그를 어디서 읽나"(Host → 경로 첫 칸)와 "블로그 안 경로가 무엇인가"(전체 경로 → `@주소` 뒤 나머지)뿐이다. 301은 **블로그 안 경로를 그대로 두고 앞의 `@주소`만 바꾼다**.

서버가 만드는 블로그 링크(알림 링크, 301 `Location`, `og:url`, 글 저장 응답의 `url`)는 모두 `http(s)://{플랫폼}/@{주소}/…` 전체 주소다.

**블로그 화면 주소와 파일 주소는 다르다.** 서브도메인 때는 `alpha.blog.com/15`(화면)와 `alpha.blog.com/uploads/a.png`(사진)가 같은 호스트 아래 있어서 "블로그 주소 + 경로"로 둘 다 만들 수 있었다. 경로 방식에서 `/@alpha`는 **화면에만** 붙는다. 사진(`/uploads/…`), 빌드 파일(`/assets/…`), API(`/api/…`)는 블로그와 관계없이 플랫폼 바로 아래에서 나간다. `/@alpha/uploads/a.png`는 `SpaForwardController`가 블로그 화면으로 받으려 하다 점(`.`) 때문에 맞지 않아 404가 된다. 공유 미리보기를 가져가는 봇은 자바스크립트를 돌리지 않으므로([43](./43-open-graph-preview.md)) 서버가 만든 이 HTML의 주소가 그대로 쓰인다.

### 3.7 React Router `basename`

블로그 화면의 링크는 그동안 `<Link to="/manage/write">`, `navigate('/12')`처럼 블로그 안 경로로 쓰여 있었다. 경로 방식에서는 이것이 `/@alpha/manage/write`가 되어야 한다. 모든 링크에 `/@alpha`를 붙여 고치는 대신 **라우터의 기준 경로**를 바꿨다.

`<BrowserRouter basename="/@alpha">`는 React Router에게 "이 앱은 `/@alpha` 아래에 산다"고 알린다.

| 앱 코드 | 실제 주소창 |
| --- | --- |
| `<Link to="/manage/write">` | `/@alpha/manage/write` |
| `navigate('/12')` | `/@alpha/12` |
| 주소창 `/@alpha/category/3` | 라우트는 `/category/3`으로 맞춤 |

- 라우터는 주소창 경로에서 basename을 떼고 라우트를 고르고, 링크를 만들 때는 앞에 붙인다. 그래서 `BlogRoutes`의 `path="/category/:categoryId"`, `path="/:postId"`는 한 글자도 바꾸지 않았다.
- basename 비교는 대소문자를 가리지 않는다. 설치된 React Router 7.18.4의 `stripBasename`은 `pathname.toLowerCase().startsWith(basename.toLowerCase())`로 비교한다(`node_modules/react-router/dist/development/chunk-*.mjs`에서 확인). 그래서 `/@Alpha/12`로 들어와도 화면이 그려진다.
- **basename 밖으로 가는 이동은 라우터로 하지 않는다.** 블로그 화면에서 `<Link to="/login">`을 쓰면 `/@alpha/login`이 된다. 플랫폼 화면(로그인, 마이페이지)이나 다른 블로그로 갈 때는 `platformUrl()`·`blogUrl()`로 만든 전체 주소를 `<a href>`나 `location.assign`으로 연다. 페이지를 새로 여는 것이고, 새로 연 페이지에서 `App`이 다시 플랫폼/블로그를 고른다.

Thymeleaf로 비유하면, 앱을 `server.servlet.context-path=/@alpha`로 띄운 것과 비슷하다. 템플릿의 `@{/manage}`가 `/@alpha/manage`가 되듯, 링크는 앱 안의 경로로 쓰고 앞부분은 틀이 붙인다.

### 3.8 같은 출처 기준의 열린 리다이렉트 막기

로그인 화면은 `?redirect=`의 주소로 돌아간다. 아무 주소나 받으면 `?redirect=https://evil.example`로 피싱 사이트에 보내는 **열린 리다이렉트**가 된다([21](./21-signup-login.md), [61](./61-oauth-social-login.md)).

- **전**: "플랫폼 주소이거나 `*.blog.test` 블로그 주소"를 받아야 했다. 호스트 이름 끝을 비교하는 규칙이 필요했다(`endsWith(".blog.test")`, 점을 빼먹으면 `evilblog.test`가 통과하는 함정, [15](./15-subdomain-host-routing.md) 6장).
- **후**: 블로그도 같은 출처 아래 경로라 **지금 페이지와 출처(스킴+호스트+포트)가 같은가** 하나만 보면 된다. 브라우저의 `URL` 객체가 `origin`을 계산해 주므로 문자열을 직접 자를 필요가 없다.

서버 쪽(소셜 로그인 뒤 돌아갈 곳)도 "호스트가 플랫폼 주소와 같은가"로 줄었다.

## 4. 동작 원리

로그인한 주인이 `http://blog.test:8080/@alpha/manage/write`를 새로고침하고 글을 발행하는 흐름이다.

```
[화면 주소] GET /@alpha/manage/write     Host: blog.test:8080   Cookie: access_token=…(host-only)
  → SpaForwardController.page
      경로 "/@alpha/manage/write" → "/@"로 시작 → 주소 "alpha", 블로그 안 경로 "/manage/write"
      findBlog("alpha") → 있음 → 볼 수 있나·이사했나 → 관리 화면 → 200 index.html
[브라우저] App: parseLocation("/@alpha/manage/write") → { blog, alpha }
      <BrowserRouter basename="/@alpha"> → 라우트 "/manage/*" → 글쓰기 화면
[API] POST /api/posts     Host: blog.test:8080
        X-Blog-Address: alpha          ← api()가 지금 경로에서 읽어 붙임
        X-Requested-With: XMLHttpRequest
        Cookie: access_token=…          ← 같은 호스트라 그대로 감
  → CsrfHeaderFilter 통과 → 로그인 회원
  → @CurrentBlog: BlogAddressResolver.resolve → 헤더 "alpha" → BlogAddress("alpha") → DB → 볼 수 있나 → Blog
  → 주인인가(BlogOwnerGuard) → 저장
  ← 201 { id: 33, url: "http://blog.test:8080/@alpha/33" }
[브라우저] navigate("/33") → 주소창 /@alpha/33 (basename이 붙음)
```

헤더가 없는 경우:

```
GET /api/blog                    (X-Blog-Address 없음)  → resolve = Platform → findBlog 빈 값 → 404
GET /api/blog  X-Blog-Address: alpha                    → 200
GET /api/blog  X-Blog-Address: admin                    → Unknown(예약어) → 404
```

## 5. 이 프로젝트에서는

### 5.1 `BlogAddressResolver`: 블로그를 정하는 한 곳

`src/main/java/com/nhnacademy/blog/global/host/BlogAddressResolver.java` (스텝 21에서 `BlogHostResolver`를 바꿔 만든 것)

```java
/** 블로그 화면이 블로그 API를 부를 때 붙이는 헤더. 값은 블로그 주소(alpha). */
public static final String HEADER = "X-Blog-Address";
/** 화면 주소에서 블로그 주소 앞에 붙는 글자: /@alpha. */
public static final String PATH_PREFIX = "/@";
```

- 헤더 이름과 경로 앞글자를 상수로 둔다. 서버 코드와 테스트(`TestBlogs.HEADER`)가 같은 상수를 쓰므로 글자가 어긋날 일이 없다.

```java
/** API 요청이 가리키는 곳. X-Blog-Address가 없으면 플랫폼이다. */
public RequestBlog resolve(HttpServletRequest request) {
    String address = request.getHeader(HEADER);
    return address == null ? new RequestBlog.Platform() : resolveAddress(address);
}

/** 블로그 주소 값을 규칙으로 확인한다. 대소문자는 가리지 않는다. */
public RequestBlog resolveAddress(String rawAddress) {
    String address = rawAddress.trim().toLowerCase(Locale.ROOT);
    return BlogAddressRule.isUsable(address) ? new RequestBlog.BlogAddress(address) : new RequestBlog.Unknown();
}
```

- `request.getHeader(HEADER)`: 헤더 이름은 대소문자를 가리지 않는다(서블릿 `getHeader`가 그렇게 찾는다). `x-blog-address`로 와도 같다.
- 헤더가 없으면(`null`) 플랫폼. 예전 `BlogHostResolver.resolve(serverName)`에서 Host를 플랫폼·블로그·알 수 없음으로 나누던 자리를 그대로 이어받았다.
- `resolveAddress`는 **화면 경로에서 꺼낸 주소에도** 쓴다(5.3). 헤더든 경로든 같은 규칙(`BlogAddressRule`: 4~32자, 예약어 거절)을 한 곳에서 본다. `trim()`은 헤더 값 앞뒤의 공백을 지운다.
- 소문자로 바꾸는 이유도 그대로다. 주소는 소문자로만 저장되므로 `My-Blog`로 와도 `my-blog`를 찾는다. `Locale.ROOT`는 터키어 로케일의 `I` 문제를 피한다([15](./15-subdomain-host-routing.md) 5.1).

`src/main/java/com/nhnacademy/blog/global/host/RequestBlog.java`

```java
public sealed interface RequestBlog {
    record Platform() implements RequestBlog { }
    record BlogAddress(String address) implements RequestBlog { }
    record Unknown() implements RequestBlog { }
}
```

- 예전 `RequestHost`와 모양이 같고 이름만 바뀌었다. 이제 Host를 해석한 결과가 아니라 "요청이 가리키는 블로그"라서 이름을 바꿨다.

```java
/** API 요청이 가리키는 블로그. 플랫폼·규칙에 맞지 않는 주소면 빈 값. … */
public Optional<Blog> findBlog(HttpServletRequest request) {
    return resolve(request) instanceof RequestBlog.BlogAddress(String address)
            ? blogRepository.findByAddress(address) : Optional.empty();
}

/** 화면 주소의 블로그 주소(/@alpha/… 의 alpha)로 찾는다. */
public Optional<Blog> findBlog(String rawAddress) {
    return resolveAddress(rawAddress) instanceof RequestBlog.BlogAddress(String address)
            ? blogRepository.findByAddress(address) : Optional.empty();
}
```

- 같은 이름의 메서드가 둘이다(오버로딩). 요청을 주면 헤더에서, 문자열을 주면 그 문자열에서 주소를 읽는다. 앞은 API(`@CurrentBlog`)가, 뒤는 화면 주소(`SpaForwardController`)가 쓴다.
- `instanceof RequestBlog.BlogAddress(String address)`: Java 21 record 패턴([15](./15-subdomain-host-routing.md) 5.1).

```java
/** 블로그 화면의 경로. path가 "/"면 블로그 첫 화면(/@alpha), 아니면 /@alpha/12 꼴. */
public static String blogPath(String address, String pathAndQuery) {
    return PATH_PREFIX + address + ("/".equals(pathAndQuery) ? "" : pathAndQuery);
}

public String blogUrl(HttpServletRequest request, Blog blog, String pathAndQuery) {
    return platformUrl(request, blogPath(blog.getAddress(), pathAndQuery));
}

public String platformUrl(HttpServletRequest request, String pathAndQuery) {
    return url(request, platform(), pathAndQuery);
}
```

- `blogPath("alpha", "/")` → `/@alpha`, `blogPath("alpha", "/12")` → `/@alpha/12`. 첫 화면은 끝에 `/`를 붙이지 않는다(R-04 "블로그 첫 화면은 끝에 `/`를 붙이지 않은 `/@{주소}`").
- **블로그 주소 = 플랫폼 주소 + 블로그 경로**가 되었다. 예전에는 `blogHost("gamma")` → `gamma.blog.test`처럼 호스트를 만들었는데, 이제 호스트는 언제나 플랫폼이고 경로만 다르다. 그래서 `blogUrl`이 `platformUrl`을 부르는 한 줄이 됐다.
- `url(...)`(파일 아래쪽)은 그대로다. 요청의 스킴과 포트를 따라가므로 개발(`http://blog.test:8080`)과 운영(`http://now-log.java21.net`)에서 같은 코드가 맞는 주소를 만든다. 운영은 nginx 뒤라서 `application-prod.yml`에 `server.forward-headers-strategy: native`를 두었다. nginx가 넘기는 `X-Forwarded-*` 헤더로 원래 스킴·포트를 알게 하는 설정이다학교 nginx 설정(`~/nginx/now-log.java21.net.conf`)은 `proxy_set_header Host $host`, `X-Forwarded-For`, `X-Forwarded-Proto`를 넘긴다. `$host`에는 포트가 없어서 서버가 만드는 링크는 `http://now-log.java21.net/@…`(포트 없음)이 된다. 배포 뒤 실제 응답으로 한 번 더 본다(7장 실습 6).

`src/main/java/com/nhnacademy/blog/global/host/DomainProperties.java`

```java
@ConfigurationProperties(prefix = "app.domain")
public record DomainProperties(String platform) {
}
```

- 예전에 있던 `cookieDomain()`(`"." + platform`)과 `blogHost(address)`가 사라졌다. 쿠키에 Domain을 두지 않고(5.5), 블로그 호스트를 만들 일이 없어서다. 남은 것은 플랫폼 주소 하나다.

### 5.2 `@CurrentBlog`와 `GET /api/search`: 바뀐 것이 거의 없다

`src/main/java/com/nhnacademy/blog/global/host/CurrentBlogArgumentResolver.java`

```java
public Blog resolve(HttpServletRequest request) {
    Long viewerId = LoginMembers.currentId();
    Blog blog = blogAddressResolver.findBlog(request)
            .filter(found -> blogVisibilityPolicy.canView(found, viewerId))
            .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));
    // 이사한 블로그는 주인만 옛 주소의 API를 쓴다 (BLOG-06)
    if (blog.isMoved() && !blog.isOwnedBy(viewerId)) {
        throw new BusinessException(ErrorCode.NOT_FOUND);
    }
    return blog;
}
```

- [15](./15-subdomain-host-routing.md) 5.4와 비교하면 `blogHostResolver`가 `blogAddressResolver`로 바뀐 것 말고는 같다. 볼 수 있는지, 이사했는지 판단은 손대지 않았다.
- **이것이 ①안의 핵심 이득이다.** 블로그 API 59개가 모두 이 인자 해석기를 거치므로, 판단 하나를 바꾸면 모두 바뀐다. 컨트롤러 코드는 한 줄도 고치지 않았다.

`src/main/java/com/nhnacademy/blog/search/presentation/SearchController.java`

```java
if (!(blogAddressResolver.resolve(request) instanceof RequestBlog.Platform)) {
    Blog blog = currentBlog.resolve(request);
    return posts(searchService.search(blog, viewerId, q, pageQuery), blog);
}
```

- 같은 경로가 두 가지 일을 하는 검색([15](./15-subdomain-host-routing.md) 5.7)은 "헤더가 없으면 플랫폼(전체 검색), 있으면 그 블로그 안 검색"이 되었다. 구조는 그대로이고, 나누는 기준만 Host에서 헤더로 옮겼다.

### 5.3 `SpaForwardController`: `/@주소/…`를 먼저 확인하기

`src/main/java/com/nhnacademy/blog/global/config/SpaForwardController.java`

```java
private static final String FIRST = "{s1:(?!api$|uploads$|assets$)[^.]+}";
/** 디코딩한 경로(%40 → @). Spring MVC가 주소를 맞출 때 쓰는 것과 같은 방식이다. */
private static final UrlPathHelper PATH_HELPER = new UrlPathHelper();

@GetMapping({
        "/",
        "/" + FIRST,
        "/" + FIRST + "/{s2:[^.]+}",
        "/" + FIRST + "/{s2:[^.]+}/{s3:[^.]+}",
        "/" + FIRST + "/{s2:[^.]+}/{s3:[^.]+}/{s4:[^.]+}",
        "/" + FIRST + "/{s2:[^.]+}/{s3:[^.]+}/{s4:[^.]+}/{s5:[^.]+}",
        // 태그 이름에는 점이 들어갈 수 있다(node.js). 확장자로 보지 않는다 (TAG-02)
        "/{s1:@[^.]+}/tag/{name:.+}"})
```

- 1~5칸 패턴은 [18](./18-spa-server-routing.md) 5.1과 같다. `@alpha`도 점이 없는 한 칸이라 `FIRST`에 맞는다. 따로 블로그용 패턴을 만들 필요가 없었다.
- **칸 하나를 블로그 주소가 쓴다.** 예전에는 블로그 안 경로가 5칸까지 됐지만 이제 `@alpha`가 첫 칸이라 블로그 안 경로는 4칸까지다. 가장 깊은 블로그 화면 `/@alpha/manage/posts/12/edit`이 정확히 5칸이라 들어맞는다. 더 깊은 블로그 화면을 만들면 패턴을 늘려야 한다.
- **태그 줄만 바뀌었다.** 예전 `"/tag/{name:.+}"`(서브도메인에서는 블로그 안 경로가 곧 전체 경로)를 `"/{s1:@[^.]+}/tag/{name:.+}"`로 바꿨다. 첫 칸이 `@`로 시작해야 하고, 태그 이름 칸은 `.+`라서 `node.js`처럼 점이 있어도 된다. 다른 줄은 모든 칸에 점이 없어야 해서 `/@alpha/tag/node.js`는 이 줄만 맞는다.
- 이 줄을 처음 쓸 때 서버가 뜨지 않은 일은 6장 함정 1에 있다.

```java
public ResponseEntity<Resource> page(HttpServletRequest request, HttpServletResponse response) {
    String path = PATH_HELPER.getPathWithinApplication(request);
    if (!path.startsWith(BlogAddressResolver.PATH_PREFIX)) {
        return app(HttpStatus.OK);
    }
    // /@alpha/12 → 주소 alpha, 블로그 안 경로 /12. 블로그 안 경로가 없으면 첫 화면(/)
    String rest = path.substring(BlogAddressResolver.PATH_PREFIX.length());
    int slash = rest.indexOf('/');
    String address = slash < 0 ? rest : rest.substring(0, slash);
    String blogPath = slash < 0 ? "/" : rest.substring(slash);
    return blogPage(request, response, address, blogPath);
}
```

1. `getPathWithinApplication`: 요청 경로를 **디코딩해서** 준다(`UrlPathHelper`는 기본으로 디코딩한다). `@`는 경로에 그대로 써도 되는 글자라 브라우저는 보통 `/@alpha`로 보내지만, 어떤 도구가 `/%40alpha`로 바꿔 보내도 같은 주소로 읽기 위해서다. `request.getRequestURI()`는 디코딩하지 않은 원문이라 `%40`이 그대로 남는다.
2. `/@`로 시작하지 않으면 플랫폼 화면이다. 예전에는 Host가 이상하면(`a.b.blog.test`) 404, 이 서비스 주소가 아니면(`localhost`) 200으로 갈렸는데([18](./18-spa-server-routing.md) 5.2), 이제 Host를 보지 않으므로 그 구분(`isUnderPlatform`)이 사라졌다. 없는 플랫폼 경로(`/nothing`)는 예전처럼 React의 `NotFoundPage`가 그린다.
3. `rest`: `@`까지 뗀 나머지. `alpha/manage/write`.
4. 첫 `/` 앞이 주소, 그 뒤가 블로그 안 경로. `/` 가 없으면(`/@alpha`) 블로그 첫 화면 `/`.
5. `blogPage`는 예전과 같은 판단(없음·볼 수 없음 404, 이사 301, 다른 블로그 소속 글 301, 관리 화면, 방문 기록)을 **블로그 안 경로** 기준으로 한다. 예전에는 `request.getRequestURI()`가 곧 블로그 안 경로였는데, 이제는 인자로 받은 `path`를 쓴다.

```java
private ResponseEntity<Resource> blogPage(HttpServletRequest request, HttpServletResponse response,
                                          String address, String path) {
    Optional<Blog> found = blogAddressResolver.findBlog(address);
    if (found.isEmpty()) {
        return app(HttpStatus.NOT_FOUND);
    }
```

- `findBlog(address)`가 규칙 검사와 DB 조회를 한 번에 한다. `@admin`(예약어), `@ab`(3자), `@nobody-here-x`(없음) 모두 여기서 빈 값 → 404.

```java
/** 같은 블로그 안 경로(path)를 새 블로그 주소로 301. */
private ResponseEntity<Resource> redirect(HttpServletRequest request, Blog target, String path) {
    String query = request.getQueryString();
    String pathAndQuery = path + (query == null ? "" : "?" + query);
    return ResponseEntity.status(HttpStatus.MOVED_PERMANENTLY)
            .location(URI.create(blogAddressResolver.blogUrl(request, target, pathAndQuery)))
            .build();
}
```

공유 미리보기의 두 주소는 서로 다른 함수로 만든다.

```java
        .append(meta("og:url", blogAddressResolver.blogUrl(request, blog, "/" + preview.postId())));
…
if (preview.imagePath() != null) {
    // 이미지는 블로그 경로가 아니라 /uploads/…에서 나간다(스텝 21)
    tags.append(meta("og:image", blogAddressResolver.platformUrl(request, preview.imagePath())));
}
```

- `og:url`은 글 **화면**이라 `blogUrl` → `http://blog.test/@alpha/33`.
- `og:image`는 **파일**이라 `platformUrl` → `http://blog.test/uploads/….png`. 처음에는 서브도메인 때처럼 둘 다 `blogUrl`로 만들어 `…/@alpha/uploads/….png`(404)가 나갔다. 학습 자료를 쓰며 코드를 다시 읽다가 찾아 고쳤다(6장 함정 2). 테스트 `publicPostPageCarriesEscapedOpenGraphTags`가 이제 `http://blog.test/uploads/t_og-{주소}.png`를 기대한다.

```java
/** 같은 블로그 안 경로(path)를 새 블로그 주소로 301. */
```

- 예전에는 `request.getRequestURI()`(전체 경로)를 새 호스트에 붙였다. 지금 전체 경로는 `/@old/category/3`이라 그대로 붙이면 `/@new/@old/category/3`이 된다. 그래서 **블로그 안 경로 `path`**(`/category/3`)를 받아 `blogUrl`이 `/@new`를 앞에 붙인다. 이 실수를 막는 것이 테스트 `movedBlogRedirectsWithSamePathExceptOwnersManagePages`다(5.7).

### 5.4 소셜 로그인 뒤 돌아갈 곳: `SocialAuthService.safeRedirect`

`src/main/java/com/nhnacademy/blog/auth/application/SocialAuthService.java`

```java
/** 로그인 뒤 돌아갈 곳. 우리 서비스 주소(플랫폼 호스트, 블로그는 그 아래 /@주소)나 경로만, 아니면 홈. */
private String safeRedirect(String redirect) {
    if (redirect == null || redirect.isBlank()) {
        return "/";
    }
    if (redirect.startsWith("/") && !redirect.startsWith("//") && !redirect.startsWith("/\\")) {
        return redirect;
    }
    try {
        URI uri = URI.create(redirect);
        boolean web = "http".equals(uri.getScheme()) || "https".equals(uri.getScheme());
        if (web && hostResolver.platform().equalsIgnoreCase(uri.getHost())) {
            return redirect;
        }
    } catch (IllegalArgumentException e) {
        // 주소 모양이 아니면 홈으로
    }
    return "/";
}
```

- 바뀐 줄은 `if (web && …)` 하나다. 예전에는 "호스트를 블로그 주소 해석기에 넣어 `Unknown`이 아니면"(플랫폼이나 `*.blog.test`)이었고, 지금은 "호스트가 플랫폼 주소와 같으면"이다. 블로그 화면도 플랫폼 호스트 아래라 이것으로 충분하다.
- `//evil.com`(스킴 없이 호스트로 가는 주소)과 `/\evil.com`(일부 브라우저가 `//`처럼 읽음)을 경로로 보지 않는 검사는 그대로다([61](./61-oauth-social-login.md)).
- 이 검사는 호스트만 본다. 포트나 스킴이 달라도(`http://blog.test:9999/`) 통과한다. 같은 호스트 이름이라 다른 사람의 사이트로 보내는 일은 아니어서 그대로 두었다. 프론트의 `safeRedirect`(5.6)는 포트까지 같은 출처를 요구해 더 좁다.

### 5.5 쿠키에서 Domain 빼기: `AuthCookieManager`, `VisitorKeys`

`src/main/java/com/nhnacademy/blog/auth/presentation/AuthCookieManager.java`

```java
/** maxAge가 null이면 브라우저를 닫을 때 사라지는 쿠키다. */
private void addCookie(HttpServletResponse response, String name, String value, Duration maxAge) {
    ResponseCookie.ResponseCookieBuilder cookie = ResponseCookie.from(name, value)
            .path("/")
            .httpOnly(true)
            .secure(authProperties.cookieSecure())
            .sameSite("Lax");
    if (maxAge != null) {
        cookie.maxAge(maxAge);
    }
    response.addHeader(HttpHeaders.SET_COOKIE, cookie.build().toString());
}
```

- 스텝 21에서 지운 줄은 `.domain(domainProperties.cookieDomain())` 하나다. `ResponseCookie`는 domain을 정하지 않으면 `Set-Cookie`에 `Domain`을 쓰지 않는다. 그래서 브라우저는 host-only 쿠키로 저장한다.
- 이 도우미로 access·refresh·device 쿠키를 주고 지우므로, 주는 쪽과 지우는 쪽이 같은 속성(Domain 없음, `Path=/`)을 쓴다. [10](./10-http-cookies.md) 4.3의 "지울 때 Domain이 다르면 다른 쿠키"라는 실수가 생기지 않는다.
- `Path=/`는 그대로다. 쿠키가 `/@alpha/…`, `/@beta/…`, `/api/…` 모두에 가야 하기 때문이다.

`src/main/java/com/nhnacademy/blog/global/web/VisitorKeys.java`

```java
public VisitorKeys(@Value("${app.auth.cookie-secure}") boolean cookieSecure) {
    this.cookieSecure = cookieSecure;
}

private String issue(HttpServletResponse response) {
    String visitorId = UUID.randomUUID().toString();
    ResponseCookie cookie = ResponseCookie.from(COOKIE, visitorId)
            .path("/")
            .httpOnly(true)
            .secure(cookieSecure)
            …
```

- 비회원 방문자 쿠키(`visitor_id`, [34](./34-view-count.md))도 같다. 생성자에서 `DomainProperties`를 받을 이유가 없어져 뺐다. 예전 주석의 "모든 블로그 주소에서 같은 비회원으로 보인다"는 이제 Domain 없이도 참이다(한 호스트).

테스트 `LoginIntegrationTest`는 이것을 직접 확인한다.

```java
// 블로그도 플랫폼 주소 아래 /@주소라 Domain 없이 이 주소 하나에만 둔다(스텝 21)
assertThat(setCookies).hasSize(2).allSatisfy(cookie -> assertThat(cookie).doesNotContain("Domain="));
```

### 5.6 프론트: `host.ts`, `App.tsx`, `client.ts`

`frontend/src/app/host.ts`

```ts
/** /@alpha 또는 /@alpha/… 의 alpha. 주소 규칙(영문 소문자·숫자·하이픈)은 서버가 다시 본다 */
const BLOG_PATH = /^\/@([A-Za-z0-9-]+)(?=\/|$)/

/** 경로(location.pathname)로 플랫폼·블로그를 나눈다 */
export function parseLocation(pathname: string): Host {
  const match = BLOG_PATH.exec(pathname)
  return match ? { kind: 'blog', address: match[1].toLowerCase() } : { kind: 'platform' }
}
```

- 정규식 조각: `^\/@`(경로가 `/@`로 시작), `([A-Za-z0-9-]+)`(주소에 쓸 수 있는 글자를 잡아 둠, 대문자도 받고 아래에서 소문자로), `(?=\/|$)`(바로 뒤가 `/`이거나 끝. **전방 탐색**이라 그 `/`는 잡지 않는다). 그래서 `/@a.b/1`은 `a` 뒤가 `.`이라 맞지 않아 플랫폼이 된다.
- 예전 `parseHost(hostname)`는 호스트 이름을 보고, 플랫폼 주소를 `VITE_PLATFORM_DOMAIN` 설정(없으면 `'blog.test'`)에서 읽었다. 이제 경로만 보므로 플랫폼 주소를 알 필요가 없다.
- 길이·예약어 같은 규칙은 검사하지 않는다. `/@admin`은 서버가 먼저 404를 주므로 프론트가 그 경로로 블로그 화면을 그릴 일이 없다.

```ts
/** 플랫폼 화면의 전체 주소. 블로그 화면에서 로그인·마이페이지로 보낼 때 쓴다(라우터 밖으로 새로 연다) */
export function platformUrl(path: string, location: Location = window.location): string {
  return `${location.origin}${path}`
}

/** 블로그 화면의 전체 주소. path가 '/'면 블로그 첫 화면(/@alpha) */
export function blogUrl(address: string, path = '/', location: Location = window.location): string {
  return `${location.origin}${blogBase(address)}${path === '/' ? '' : path}`
}
```

- `location.origin`은 `http://blog.test:5173`처럼 스킴·호스트·포트다. 플랫폼도 블로그도 **지금 출처** 아래라서 설정값이 필요 없다.
- **피한 운영 버그**: 예전 코드는 `${location.protocol}//${PLATFORM_DOMAIN}${port}${path}`였고, `PLATFORM_DOMAIN`은 `import.meta.env.VITE_PLATFORM_DOMAIN ?? 'blog.test'`였다. Vite는 `VITE_`로 시작하는 환경 변수를 **빌드할 때** 코드에 박아 넣는데, 배포용 Docker 빌드에서는 이 값을 정한 적이 없었다. 그대로 배포했다면 운영 화면의 "로그인" "내 블로그" 링크가 모두 `http://blog.test/…`(개발용 이름)로 가서 깨졌을 것이다. 지금은 모든 주소가 `location.origin` 기준이라 어디에 배포해도 맞고, `VITE_PLATFORM_DOMAIN`은 없앴다(`vite-env.d.ts`).
- `blogDisplayAddress`(사람에게 보여 줄 `blog.test:5173/@alpha`)는 `location.host`(포트 포함 호스트)를 쓴다. 블로그 개설 화면의 주소 칸 앞글자, 마이페이지의 블로그 주소가 이것이다.

```ts
export function safeRedirect(target: string | null, location: Location = window.location): string | null {
  if (!target) {
    return null
  }
  let url: URL
  try {
    url = new URL(target)
  } catch {
    return null
  }
  return (url.protocol === 'http:' || url.protocol === 'https:') && url.origin === location.origin ? url.href : null
}
```

- `new URL(target)`: 주소를 해석한다. 상대 주소(`/relative`)는 기준 없이 해석할 수 없어 예외 → `null`. 로그인 화면에 오는 `redirect`는 언제나 전체 주소로 만들기 때문이다.
- `url.origin === location.origin`: 3.8의 "같은 출처만". `javascript:alert(1)`은 프로토콜 검사에서, `http://alpha.blog.test:5173/`(예전 서브도메인 주소)·`http://blog.test:8080/`(다른 포트)은 출처 검사에서 걸린다(`host.test.ts`).

`frontend/src/app/App.tsx`

```tsx
export default function App() {
  const host = parseLocation(window.location.pathname)
  return host.kind === 'platform'
    ? <BrowserRouter><PlatformRoutes /></BrowserRouter>
    : <BrowserRouter basename={blogBase(host.address)}><BlogRoutes /></BrowserRouter>
}
```

- 페이지를 열 때 한 번 경로를 보고 라우터를 고른다. 블로그면 `basename="/@alpha"`(3.7).
- 플랫폼과 블로그를 **다른 라우터**로 나눴으므로, 블로그 화면 안에서 `<Link>`로는 플랫폼 화면에 갈 수 없다. `BlogHeader`의 "마이페이지", "서비스 관리"가 `<a href={platformUrl('/me')}>`인 이유다. 이 이동은 페이지를 새로 읽고, 새 페이지에서 `App`이 플랫폼 라우터를 고른다.

`frontend/src/api/client.ts`

```ts
/** 블로그 화면이면 { 'X-Blog-Address': 주소 }, 플랫폼 화면이면 빈 값 */
function blogHeader(): Record<string, string> {
  const address = currentBlogAddress()
  return address ? { 'X-Blog-Address': address } : {}
}

async function request<T>(path: string, options: RequestOptions, retryIfSuspended: boolean): Promise<T> {
  const method = options.method ?? 'GET'
  const headers: Record<string, string> = { Accept: 'application/json', ...blogHeader() }
  if (method !== 'GET') {
    headers['X-Requested-With'] = 'XMLHttpRequest'
  }
```

- **API 클라이언트 한 곳에서** 헤더를 붙인다. 화면 코드(`api('/api/posts/12')`)는 헤더를 모른다. 서버의 `@CurrentBlog`와 짝을 이루는 구조다. 화면마다 헤더를 붙였다면 하나만 빠뜨려도 그 화면이 플랫폼 요청이 되어 404가 났을 것이다.
- `...blogHeader()`: 객체 펼치기(spread). 빈 객체면 아무것도 더하지 않는다.
- `currentBlogAddress()`는 **요청을 보내는 순간의** `window.location.pathname`을 본다. 블로그 화면은 언제나 같은 블로그 안에서만 움직이므로(다른 블로그로는 새 페이지) 값이 바뀌지 않는다.
- 사진 올리기(`uploadFile`)는 `api()`를 거치지 않고 `fetch`를 직접 쓰므로 같은 `blogHeader()`를 따로 붙였다.

`frontend/src/components/ShareButtons.tsx`

```tsx
const url = blogUrl(currentBlogAddress() ?? '', `/${postId}`)
```

- 예전 `${window.location.origin}/${postId}`는 서브도메인에서는 맞았지만 지금은 `http://blog.test/12`(블로그 없는 플랫폼 경로)가 된다. 공유 주소는 `/@alpha/12`여야 한다. 이처럼 **`location.origin`에 경로를 바로 붙이던 곳**이 경로 방식에서 조용히 틀리는 자리다.

### 5.7 테스트

`src/test/java/com/nhnacademy/blog/support/TestBlogs.java`

```java
/** 블로그 화면이 블로그 API를 부를 때 붙이는 헤더 (스텝 21). 값은 blog.getAddress(). */
public static final String HEADER = BlogAddressResolver.HEADER;

/** 블로그 화면의 전체 주소: http://blog.test/@주소/글. path가 "/"면 블로그 첫 화면. */
public static String url(Blog blog, String path) {
    return "http://blog.test" + BlogAddressResolver.blogPath(blog.getAddress(), path);
}
```

- 수십 개 통합 테스트가 `.header("Host", blog.getAddress() + ".blog.test")`로 블로그를 정하던 것을 `.header(TestBlogs.HEADER, blog.getAddress())`로 바꿨다(T119). 301·알림 링크 기대값은 `TestBlogs.url(blog, "/category/3?page=2")`로 만든다.
- 테스트 도우미가 운영 코드의 상수·함수(`HEADER`, `blogPath`)를 그대로 쓴다. 규칙이 바뀌면 테스트 기대값도 함께 바뀐다. 반대로 `blogPath`가 틀리면 테스트도 같이 틀리므로, `blogPath` 자체는 `BlogAddressResolverTest`가 글자 그대로의 기대값으로 따로 확인한다.

`src/test/java/com/nhnacademy/blog/global/host/BlogAddressResolverTest.java`

```java
@Test
void withoutHeaderItIsThePlatformWhateverTheHost() {
    MockHttpServletRequest request = new MockHttpServletRequest();
    request.setServerName("alpha.blog.com");
    assertThat(resolver.resolve(request)).isInstanceOf(RequestBlog.Platform.class);
}
```

- 예전 방식으로 들어와도(호스트가 `alpha.blog.com`) 헤더가 없으면 플랫폼이다. **Host는 이제 블로그를 정하지 않는다**는 것을 못 박는 테스트다.
- `headerNamesTheBlog`(`My-Blog` → `my-blog`), `addressesBreakingTheRuleOrReservedAreUnknown`(`abc`, `admin`, `a.b` → `Unknown`), `blogUrlKeepsSchemePortAndPathOnThePlatformHost`(`http://blog.com:8080/@gamma/15?x=1`, `https://blog.com/@gamma`)가 나머지 규칙을 확인한다.

`src/test/java/com/nhnacademy/blog/global/config/SpaForwardIntegrationTest.java`

```java
/** 플랫폼 화면 주소. */
private MockHttpServletRequestBuilder platformPage(String path) {
    return get(path).accept(MediaType.TEXT_HTML);
}

/** 블로그 화면 주소 /@{address}{path} (스텝 21). path가 "/"면 /@{address}. */
private MockHttpServletRequestBuilder blogPage(String address, String path) {
    return get(BlogAddressResolver.blogPath(address, path)).accept(MediaType.TEXT_HTML);
}
```

```java
mockMvc.perform(blogPage(oldBlog.getAddress(), "/category/3").queryParam("page", "2"))
        .andExpect(status().isMovedPermanently())
        .andExpect(header().string("Location", TestBlogs.url(newBlog, "/category/3?page=2")));
```

- 이사 301이 **블로그 안 경로와 쿼리를 그대로** 새 주소로 옮기는지 본다. 5.3의 `/@new/@old/…` 실수가 있으면 여기서 깨진다.
- `blogPagesServeTheApp`은 `/@주소/tag/node.js`(태그 줄 패턴), `unknownBlogAddressIs404Page`는 `/@nobody-here`·`/@admin`을 확인한다.

`QuickstartScenarioIntegrationTest`는 quickstart의 사람 시나리오를 그대로 따라 하는 테스트라, 요청 도우미 `send(...)`가 블로그 API일 때만 헤더를 붙인다.

```java
// 블로그 API면 블로그 화면처럼 X-Blog-Address로 블로그를 알린다(null이면 플랫폼)
if (blogAddress != null) {
    request.header(TestBlogs.HEADER, blogAddress);
}
```

프론트 테스트: `host.test.ts`(경로 판별, 같은 출처 주소 만들기, `safeRedirect`), `client.test.ts`의 "상태를 바꾸는 요청에는 CSRF 헤더와 연타 방지 키를 붙인다"가 `/@alpha/manage`에서 부를 때 `X-Blog-Address: alpha`가 붙는지 확인한다.

## 6. 자주 하는 실수와 함정

1. **경로 패턴 `{이름:정규식}` 안에 `/`를 쓰기.** 태그 줄을 처음에는 정규식 안에 `/`가 들어간 모양으로 썼다(첫 칸에 `/`가 없다는 뜻을 담으려고). 서버가 시작하다가 `Expected close capture character after variable name }` 오류로 멈췄다. Spring의 경로 패턴 해석기는 패턴을 `/`로 칸을 나누며 읽기 때문에, 중괄호 안의 `/`도 칸 나눔으로 읽혀 변수가 닫히지 않은 것으로 본다. `{…}` 하나는 원래 한 칸만 맞추므로 "`/`가 없다"를 따로 쓸 필요가 없다. `{s1:@[^.]+}`로 고쳤다. 테스트가 아니라 **시작할 때** 깨지므로, 패턴을 고친 뒤에는 서버(또는 통합 테스트 하나)를 꼭 띄워 본다.
2. **`location.origin`이나 `request.getRequestURI()`에 경로를 그대로 붙이기.** 서브도메인에서는 "호스트 = 블로그"라서 맞던 코드가 경로 방식에서 조용히 틀린다. 공유 주소(`origin + /12`), 이사 301(`새 주소 + getRequestURI()`)이 그랬다. 블로그 주소는 늘 `blogUrl`·`blogPath`로 만든다. **반대로 파일 주소에는 `/@주소`를 붙이지 않는다.** 서브도메인 때는 "블로그 주소 + `/uploads/…`"가 맞았지만 경로 방식에서는 `/@alpha/uploads/…`가 404다. 공유 미리보기 `og:image`가 실제로 이렇게 틀렸다가 고쳐졌다(5.3). 화면이면 `blogUrl`, 사진·`/assets`·API면 `platformUrl`.
3. **블로그 화면에서 `<Link to="/login">`.** basename이 붙어 `/@alpha/login`이 되고, 블로그 라우터에는 그런 라우트가 없어 `NotFoundPage`가 뜬다. 플랫폼 화면으로는 `platformUrl()` + `<a href>`.
4. **API 호출마다 헤더를 직접 붙이기.** 하나만 빠뜨려도 그 요청이 플랫폼 요청이 되어 404. `api()`·`uploadFile()` 한 곳에서 붙인다. `fetch`를 새로 직접 쓰는 곳이 생기면 그곳도 `blogHeader()`가 필요하다.
5. **헤더를 권한으로 착각하기.** `X-Blog-Address`는 누구나 아무 값으로 보낼 수 있다. 권한은 언제나 로그인 쿠키와 `BlogOwnerGuard`·가시성 판단으로 본다.
6. **헤더에 따라 응답이 다른 GET을 캐시하기.** 같은 `/api/blog`가 헤더마다 다른 블로그를 돌려준다. 브라우저나 중간 서버(CDN)가 주소만 보고 캐시하면 다른 블로그의 응답이 섞인다. 지금은 API 응답을 HTTP 캐시하지 않지만(Spring Security가 기본으로 `Cache-Control: no-cache, no-store …`를 붙인다), 캐시를 켜게 되면 응답에 `Vary: X-Blog-Address`를 붙여야 한다. ②안(경로에 주소)이었다면 생기지 않는 문제다.
7. **브라우저에 남은 예전 Domain 쿠키.** 스텝 21 전에 `blog.test`에서 로그인했던 브라우저에는 `Domain=.blog.test`인 `access_token`이 남아 있을 수 있다. 새 서버는 Domain 없는 `access_token`을 준다. 쿠키는 (이름, Domain, Path)가 모두 같아야 같은 쿠키라서([10](./10-http-cookies.md) 4.1) 브라우저에 **같은 이름의 쿠키가 둘** 생기고 둘 다 보낸다. 경로가 같으면 브라우저는 먼저 만든(옛) 쿠키를 앞에 보낸다(RFC 6265 5.4). 처음에는 서버가 첫 번째 값을 읽고 로그아웃은 Domain 없는 쪽만 지워서, 옛 Refresh 쿠키로 "로그아웃했는데 다시 로그인되는" 일이 생길 수 있었다. 그래서 같은 이름이 둘 오면 **뒤(새) 값을 읽고**, 옛 `Domain=.{플랫폼}` 쿠키는 지우라고 응답하게 했다(`AuthCookieManager.readCookie`·`expireLegacyDomainCookies`, `LogoutIntegrationTest.legacyDomainCookieIsIgnoredAndExpired`). 배포된 사이트도 스텝 21 전에는 `Domain=.now-log.java21.net` 쿠키를 줬으므로 같은 일이 생긴다. 쿠키를 바꿀 때는 이미 나간 쿠키가 어떻게 남는지까지 생각해야 한다.
8. **5칸 패턴을 잊고 깊은 블로그 화면 만들기.** 블로그 안 경로는 이제 4칸까지다(5.3). `/@alpha/manage/a/b/c/d`처럼 깊은 화면을 만들면 새로고침에서 JSON 404가 난다([18](./18-spa-server-routing.md) 6장의 6칸 함정과 같다).
9. **Vite 개발 서버의 `/@` 경로와 겹치는 블로그 이름.** Vite 개발 서버는 `/@`로 시작하는 몇몇 경로를 자기 것으로 쓴다. 설치된 Vite 8.3.3 코드에서 `/@vite/client`, `/@vite/env`, `/@fs/`, `/@id/`를, `@vitejs/plugin-react`에서 `/@react-refresh`를 확인했다. `fs`, `id`는 4자보다 짧아 블로그 주소가 될 수 없지만, `vite`와 `react-refresh`는 주소 규칙에 맞고 예약어도 아니다. 그런 블로그를 **Vite 개발 서버(5173)에서** 열면 그 정확한 경로(예: 블로그 `react-refresh`의 첫 화면 `/@react-refresh`)는 Vite가 가져가 블로그 화면 대신 자바스크립트 파일이 나올 수 있다. 운영과 `:8080`(Spring이 직접 줌)에는 이런 일이 없다. 개발에서 불편하면 예약어에 넣는 방법이 있다(지금은 넣지 않았다).
10. **경로 방식이면 보안이 그대로라고 생각하기.** 쿠키·CSRF는 더 단순해졌지만, 모든 블로그가 한 출처가 되어 XSS 한 번의 피해가 전체로 커졌다(3.4).

## 7. 직접 해 보기

준비: `/etc/hosts`에 `127.0.0.1 blog.test` 한 줄(블로그마다 줄을 더할 필요가 없다), `docker compose up -d`, `./mvnw spring-boot:run`. 아래 `alpha`는 내가 가진 블로그 주소로 바꾼다.

**실습 1. 화면 주소의 상태 코드**

```bash
for p in /@alpha /@alpha/category/0 /@alpha/tag/node.js /@alpha/guestbook /@alpha/manage \
         /@nobody-here-x /@admin /@alpha/99999999 /login; do
  printf '%-28s ' "$p"; curl -s -o /dev/null -w '%{http_code}\n' "http://blog.test:8080$p"
done
```

기대: 블로그 화면들과 `/login`은 200, `/@nobody-here-x`·`/@admin`·`/@alpha/99999999`는 404(본문은 index.html). `curl -s -o /dev/null -w '%{http_code}\n' 'http://blog.test:8080/%40alpha'`도 200인지 보면 5.3의 디코딩을 확인할 수 있다.

**실습 2. 헤더로 블로그 고르기**

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://blog.test:8080/api/blog                              # 404 (헤더 없음 = 플랫폼)
curl -s -o /dev/null -w '%{http_code}\n' -H 'X-Blog-Address: alpha' http://blog.test:8080/api/blog  # 200
curl -s -o /dev/null -w '%{http_code}\n' -H 'X-Blog-Address: ALPHA' http://blog.test:8080/api/blog  # 200 (소문자로)
curl -s -o /dev/null -w '%{http_code}\n' -H 'X-Blog-Address: admin' http://blog.test:8080/api/blog  # 404 (예약어)
curl -s -o /dev/null -w '%{http_code}\n' -H 'Host: alpha.blog.test' http://localhost:8080/api/blog   # 404 (Host는 이제 안 봄)
```

**실습 3. 쿠키에 Domain이 없는지**

브라우저로 `http://blog.test:8080/login`에서 로그인 → 개발자 도구 → Application → Cookies → `http://blog.test:8080`. `access_token`의 Domain 칸이 `.blog.test`가 아니라 `blog.test`(앞 점 없음, host-only)인지 본다. Network 탭에서 로그인 응답의 `Set-Cookie`에 `Domain=`이 없는 것도 본다. 그다음 `/@alpha/manage`로 가서 로그인 상태가 이어지는지 본다. 6장 함정 7의 옛 쿠키가 보이면 지운다.

**실습 4. basename 링크 따라가기 (브라우저)**

이번 스텝에서 **브라우저로 눌러 보는 확인은 아직 하지 못했다**(서버 응답과 테스트로만 확인). 직접 해 본다.

1. `http://blog.test:8080/@alpha`를 연다. 글 제목, 카테고리, 태그, 방명록 링크를 차례로 누르며 주소창이 `/@alpha/…`로 바뀌는지, 새로고침해도 같은 화면인지 본다.
2. 관리 → 글쓰기 → 발행. 주소창이 `/@alpha/{새 번호}`가 되는지 본다.
3. 개발자 도구 Network에서 아무 `/api/…` 요청을 눌러 Request Headers에 `X-Blog-Address: alpha`가 있는지, 플랫폼 홈(`/`)의 `/api/home/posts`에는 없는지 본다.
4. 블로그 머리글의 "마이페이지"·로고(플랫폼 홈)를 눌러 `/me`, `/`로 가는지(`/@alpha/me`가 아닌지) 본다.
5. 글 상세의 "주소 복사"가 `http://blog.test:8080/@alpha/{번호}`를 복사하는지 본다.
6. 로그아웃 상태로 `/@alpha/manage`를 열어 로그인 화면으로 갔다가, 로그인 뒤 `/@alpha/manage`로 돌아오는지 본다(`safeRedirect`).

**실습 5. 공유 미리보기와 이사 301**

```bash
curl -s http://blog.test:8080/@alpha/{공개 글 번호} | grep -o '<meta property="og:\(url\|image\)"[^>]*>'
# <meta property="og:url" content="http://blog.test:8080/@alpha/{번호}">
# <meta property="og:image" content="http://blog.test:8080/uploads/….">   (사진이 있는 글이면, /@alpha 없음)
```

블로그 이사를 해 봤다면 `curl -sI 'http://blog.test:8080/@옛주소/category/3?page=2' | grep -i '^location'` → `http://blog.test:8080/@새주소/category/3?page=2`.

**실습 6. 운영 주소 확인 (배포 뒤)**

`http://now-log.java21.net/@{주소}`를 열고, 글 저장 응답의 `url`과 알림 링크가 `http://now-log.java21.net/@…`인지(포트 `:8460`이 붙지 않았는지) 본다. 붙어 있다면 학교 nginx가 `X-Forwarded-*` 헤더를 넘기지 않는 것이다(5.1).

**실습 7. 패턴 함정 재현**

`SpaForwardController`의 태그 줄 `"/{s1:@[^.]+}/tag/{name:.+}"`를 `"/{s1:@[^/.]+}/tag/{name:.+}"`로 바꾸고 `./mvnw test -Dtest=SpaForwardIntegrationTest`를 돌린다. 컨텍스트가 뜨지 않으며 원인에 패턴 오류가 보인다. 되돌린다.

```bash
./mvnw test -Dtest='BlogAddressResolverTest,SpaForwardIntegrationTest,CurrentBlogIntegrationTest,QuickstartScenarioIntegrationTest'
cd frontend && npx vitest run src/app/host.test.ts src/api/client.test.ts
```

## 8. 확인 문제

1. 서브도메인 블로그 주소를 배포 서버에서 쓸 수 없었던 이유는? 서버 코드로 해결할 수 없는 이유는?
<details><summary>답</summary>배포 서버(학교 nginx, <code>now-log.java21.net</code>)는 이름이 하나뿐이고 와일드카드 DNS(<code>*.now-log.java21.net</code>)가 없다. <code>alpha.now-log.java21.net</code>은 DNS에서 이름을 찾지 못해 요청이 서버에 닿지도 않으므로, 서버 코드로는 고칠 수 없다(nginx의 <code>server_name</code>과 HTTPS 와일드카드 인증서도 학교 쪽 설정이다).</details>

2. 블로그 경로에 `@`를 붙인 이유는?
<details><summary>답</summary>블로그 주소는 영문 소문자·숫자·하이픈만 쓰므로 <code>@</code>로 시작하는 첫 칸은 블로그만 쓴다. 그래서 <code>/login</code>, <code>/me</code> 같은 플랫폼 경로와, 앞으로 더할 플랫폼 경로와도 부딪히지 않는다.</details>

3. API에 블로그를 알리는 방법으로 `X-Blog-Address` 헤더(①안)를 고르고 `/api/blogs/{주소}/…`(②안)를 고르지 않은 이유는? ①안이 대신 떠안은 단점 하나는?
<details><summary>답</summary>블로그 API는 모두 <code>@CurrentBlog</code> 인자 해석기 한 곳에서 블로그를 받으므로, 그곳이 Host 대신 헤더를 읽게 하면 59개 API의 경로·계약·테스트가 그대로다. ②안은 그 모두를 바꿔야 한다. 대신 주소만 보고는 어느 블로그인지 알 수 없어서, 로그를 볼 때 헷갈리거나 HTTP 캐시를 쓰면 <code>Vary: X-Blog-Address</code>가 필요하다.</details>

4. 누구나 `X-Blog-Address`를 마음대로 붙일 수 있는데 괜찮은 이유는?
<details><summary>답</summary>헤더는 어느 블로그에 대한 요청인지 고르는 값일 뿐 권한이 아니다. 주소창에 다른 블로그 주소를 치는 것과 같다. 고른 뒤에 서버가 로그인 쿠키로 가시성(볼 수 있나)과 주인 여부를 따로 검사한다. 예전 Host 헤더도 마찬가지로 아무나 바꿀 수 있었다.</details>

5. 화면이 API에 `X-Blog-Address`·`X-Requested-With` 같은 사용자 지정 헤더를 붙여도 사전 요청(preflight)이 생기지 않는 이유는?
<details><summary>답</summary>화면과 API가 같은 출처(같은 스킴·호스트·포트)이기 때문이다. 사전 요청은 다른 출처로 보내는 요청에만 있는 CORS 규칙이다. 개발에서 Vite를 써도 브라우저는 <code>blog.test:5173</code>의 <code>/api</code>를 부르고, Vite가 8080으로 넘기므로 브라우저 입장에서는 같은 출처다.</details>

6. 예전에는 로그인 쿠키에 `Domain=.blog.test`가 꼭 필요했고 지금은 필요 없는 이유는? 필요 없는데 남겨 두면 안 되는 이유는?
<details><summary>답</summary>예전에는 로그인하는 플랫폼(<code>blog.test</code>)과 블로그(<code>alpha.blog.test</code>)가 다른 호스트라, host-only 쿠키면 블로그로 가는 순간 로그아웃 상태였다. 지금은 모두 한 호스트 아래 경로라 host-only 쿠키(<code>Path=/</code>)가 모든 화면에 간다. 도메인 쿠키는 그 아래 모든 호스트로 가므로, 같은 도메인 아래 다른 서비스가 생기면 로그인 쿠키가 거기에도 간다. 필요 없는 범위는 열지 않는다.</details>

7. 경로 방식으로 바뀌면서 XSS의 위험은 어떻게 달라졌나?
<details><summary>답</summary>모든 블로그가 한 출처가 되었다. 한 블로그 글에서 스크립트가 돌면 같은 출처라서 <code>X-Requested-With</code>를 붙여 어떤 API든 로그인한 사람의 이름으로 부를 수 있다. 예전에는 블로그마다 출처가 달라 다른 블로그 API의 응답을 읽을 수 없었다. 그래서 본문 정화와 CSP가 더 중요해졌다.</details>

8. `<BrowserRouter basename="/@alpha">`에서 `<Link to="/manage">`는 어떤 주소가 되나? 블로그 화면에서 로그인 화면으로 갈 때 `<Link to="/login">`을 쓰면 안 되는 이유는?
<details><summary>답</summary><code>/@alpha/manage</code>가 된다. 같은 이유로 <code>/login</code>도 <code>/@alpha/login</code>이 되어 블로그 라우터의 "없는 화면"이 뜬다. 플랫폼 화면은 다른 라우터라서 <code>platformUrl('/login')</code>로 만든 전체 주소를 <code>&lt;a href&gt;</code>로 열어 페이지를 새로 읽게 한다.</details>

9. 이사한 블로그의 301 주소를 `blogUrl(…, request.getRequestURI())`로 만들면 어떤 주소가 되나?
<details><summary>답</summary><code>getRequestURI()</code>는 <code>/@old/category/3</code> 전체라서 <code>/@new/@old/category/3</code>이 된다. <code>@주소</code> 뒤의 블로그 안 경로(<code>/category/3</code>)만 넘겨야 <code>/@new/category/3</code>이 된다.</details>

10. 프론트의 `safeRedirect`가 `http://alpha.blog.test:5173/`과 `http://blog.test:8080/`(지금 페이지는 `http://blog.test:5173`)을 모두 막는 이유는?
<details><summary>답</summary>같은 출처(스킴+호스트+포트)만 받기 때문이다. 앞의 것은 호스트가, 뒤의 것은 포트가 다르다. 블로그도 같은 출처 아래 경로라 "출처가 같은가" 하나로 충분하고, 호스트 이름 끝을 자르는 규칙이 필요 없어졌다.</details>

11. 경로 패턴의 `{이름:정규식}` 안에 `/`를 넣으면(실습 7의 `"/{s1:@[^/.]+}/tag/{name:.+}"`처럼) 서버가 뜨지 않는 이유와 고친 모양은?
<details><summary>답</summary>Spring 경로 패턴 해석기는 <code>/</code>를 칸 나눔으로 읽어서, 중괄호 안의 <code>/</code> 때문에 변수가 닫히지 않은 것으로 보고 "Expected close capture character after variable name }" 오류를 낸다. <code>{…}</code>는 원래 한 칸만 맞추므로 <code>/</code>를 뺀 <code>{s1:@[^.]+}</code>로 충분하다.</details>

12. 글의 대표 사진 `/uploads/a.png`로 공유 미리보기 `og:image`를 만들 때 `blogUrl`이 아니라 `platformUrl`을 쓰는 이유는?
<details><summary>답</summary><code>/@주소</code>는 블로그 화면 주소에만 붙는다. 사진은 블로그와 관계없이 플랫폼 아래 <code>/uploads/…</code>에서 나가므로, <code>blogUrl</code>로 만들면 <code>/@alpha/uploads/a.png</code>가 되어 404다. 서브도메인 때는 호스트만 바뀌어서 둘 다 맞았던 것이 경로 방식에서 갈라졌다.</details>

13. 예전 프론트의 `VITE_PLATFORM_DOMAIN ?? 'blog.test'`가 운영에서 어떤 문제를 일으켰을까? 지금은 왜 생기지 않나?
<details><summary>답</summary>Vite는 <code>VITE_</code> 환경 변수를 빌드할 때 코드에 박는데, 배포용 Docker 빌드에서 이 값을 정하지 않아 기본값 <code>blog.test</code>가 들어갔을 것이다. 운영 화면의 로그인·블로그 링크가 모두 <code>http://blog.test/…</code>로 가서 깨진다. 지금은 모든 주소를 <code>location.origin</code>(지금 출처) 기준으로 만들어 설정이 필요 없고, 변수도 없앴다.</details>

## 9. 더 읽을거리

- nginx 문서 "Server names"(`server_name`의 와일드카드 이름, `.example.org`): https://nginx.org/en/docs/http/server_names.html
- RFC 6265 "HTTP State Management Mechanism": 5.2.3 Domain 속성, 5.3 저장 규칙(host-only-flag), 5.4 보낼 때 순서, 8.6 "Weak Integrity"(Path는 보안 경계가 아님)
- MDN "Same-origin policy", "Cross-Origin Resource Sharing (CORS)"의 simple requests와 preflight
- MDN "Vary" 헤더
- OWASP Cheat Sheet "Unvalidated Redirects and Forwards"
- React Router 문서 `<BrowserRouter basename>`
- Spring Framework 레퍼런스 "URI Patterns"(`PathPattern`, `{name:regex}`), `UrlPathHelper` Javadoc
- Spring Boot 레퍼런스 "Running Behind a Front-end Proxy Server"(`server.forward-headers-strategy`)
- Vite 문서 "Env Variables and Modes"(`import.meta.env`, 빌드할 때 바뀌는 값)
