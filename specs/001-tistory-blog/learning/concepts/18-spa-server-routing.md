# 18. SPA와 서버 라우팅: 화면 주소는 누가 처리하나

> 관련 스텝: [스텝 3](../step-03.md) (T010), [스텝 1](../step-01.md) (T002, T004) · 관련 개념: [15-subdomain-host-routing](./15-subdomain-host-routing.md), [16-authorization-visibility](./16-authorization-visibility.md), [19-react-router-api-client](./19-react-router-api-client.md), [07-spring-mvc-exception-handling](./07-spring-mvc-exception-handling.md)

## 1. 이 문서로 배우는 것

- MPA(여러 페이지 앱)와 SPA(한 페이지 앱)의 차이
- 브라우저 History API(`pushState`)와 클라이언트 라우팅
- SPA에서 새로고침하거나 주소를 직접 치면 생기는 문제와 "서버 폴백"
- Spring Boot가 정적 파일(`static/`)을 내주는 방식과, 화면 주소와 정적 파일을 구분하는 법
- 이 프로젝트의 `SpaForwardController`: 경로 패턴 정규식, 404 상태로 `index.html`을 주는 이유, 301 리다이렉트
- 301·302·307·308의 차이와 검색엔진
- 블로그 이사·다른 블로그 글의 301, 글 확인을 이사 확인보다 먼저 하는 이유
- Vite 개발 서버(번들링, HMR)와 빌드 결과, jar 하나로 배포하는 방법, 개발 중 두 서버(5173, 8080) 구조

**먼저 알면 좋은 것**: HTML·JS를 브라우저가 받아 화면을 그린다는 것, HTTP 상태 코드, [15](./15-subdomain-host-routing.md)의 Host 해석.

## 2. 왜 필요한가

이 프로젝트의 화면은 React로 만든 **SPA**다. SPA는 처음에 `index.html` 하나를 받고, 이후 화면 이동은 브라우저 안의 자바스크립트가 한다. 그런데 사용자가 `alpha.blog.com/15`를 **주소창에 직접 치거나 새로고침**하면 브라우저는 서버에 `GET /15`를 보낸다. 서버에 `/15`라는 파일은 없다.

- 아무 처리도 안 하면: 서버가 404를 준다. 링크를 공유받은 사람은 글을 볼 수 없다.
- 모든 주소에 무조건 `index.html`을 주면: 화면은 뜨지만,
  - 없는 블로그(`nobody.blog.com`)도 200이라 검색엔진이 "있는 페이지"로 색인한다.
  - 이사한 블로그의 옛 주소가 새 주소로 넘어가지 않는다(검색엔진이 옛 주소를 계속 가진다).
  - 다른 블로그 주소에 붙은 글 번호(`beta.blog.com/15`)가 엉뚱한 블로그 화면으로 뜬다.

그래서 이 프로젝트는 **서버가 먼저 확인하고** `index.html`을 준다(원본 6장 ①, rest-api.md "화면 주소 단계에서 서버가 하는 일"). 확인 결과에 따라 200, 404, 301이 갈린다.

## 3. 기본 개념

### 3.1 MPA와 SPA

```
MPA (Multi-Page Application)                  SPA (Single-Page Application)
───────────────────────────                   ─────────────────────────────
/        → 서버가 home.html 만들어 줌           /   → index.html + app.js (한 번)
/15      → 서버가 post.html 만들어 줌           /15 → 자바스크립트가 화면만 바꿈, 데이터는 /api/posts/15
/manage  → 서버가 manage.html 만들어 줌         /manage → 자바스크립트가 화면만 바꿈
매번 페이지 전체를 새로 받음                     처음 한 번만 HTML·JS, 이후는 JSON만
```

| | MPA (예: JSP, Thymeleaf) | SPA (예: React) |
| --- | --- | --- |
| 화면 이동 | 매번 새 HTML, 깜빡임 | 부분만 바뀜, 앱처럼 부드러움 |
| 서버 역할 | HTML을 만듦 | JSON API만 줌(+ index.html) |
| 첫 로딩 | 빠름 | JS를 받아 실행해야 해서 상대적으로 느림 |
| 검색엔진 | HTML에 내용이 바로 있음 | 내용이 JS로 그려짐(그래서 og 태그 등 별도 처리, SOC-02) |

### 3.2 History API와 클라이언트 라우팅

브라우저에는 **새로고침 없이 주소만 바꾸는** 기능이 있다.

```js
history.pushState(null, '', '/15')   // 주소창이 /15로 바뀜. 서버 요청은 없음
window.addEventListener('popstate', () => { /* 뒤로 가기 처리 */ })
```

React Router의 `BrowserRouter`는 이 API로 주소를 바꾸고, 주소에 맞는 컴포넌트를 그린다([19](./19-react-router-api-client.md)). 링크를 누르면:

```
<Link to="/15"> 클릭
  → history.pushState('/15')        (서버 요청 없음)
  → React Router가 /:postId 경로에 맞는 <PostPage>를 그림
  → PostPage가 fetch('/api/posts/15')로 데이터만 받음
```

### 3.3 새로고침 문제와 서버 폴백

```
사용자가 /15에서 F5
  → 브라우저: GET /15  (서버로!)
  → 서버: /15? 그런 파일 없음 → 404  ✗
```

해결은 "**화면 주소로 온 요청에는 `index.html`을 준다**"(서버 폴백, fallback)이다. `index.html`이 로드되면 React Router가 주소창의 `/15`를 보고 알맞은 화면을 그린다.

```
GET /15 → 서버: 화면 주소다 → index.html → 브라우저가 app.js 실행 → React Router가 /15를 보고 PostPage
```

단, 모든 요청에 `index.html`을 주면 안 된다.
- `/api/...`는 JSON API다. 없는 API에 HTML이 가면 프론트가 JSON 파싱에서 깨진다.
- `/assets/index-a1b2c3.js` 같은 **정적 파일**은 파일 그대로 줘야 한다. 없는 JS 파일에 HTML을 주면 브라우저가 "JS 문법 오류"를 낸다.
- `/uploads/...`는 업로드 이미지다.

### 3.4 Spring Boot의 정적 리소스

Spring Boot는 클래스패스의 `static/` 폴더(`src/main/resources/static`) 파일을 그 경로 그대로 내준다.

```
src/main/resources/static/index.html          → GET /index.html
src/main/resources/static/favicon.svg         → GET /favicon.svg
src/main/resources/static/assets/index-xx.js  → GET /assets/index-xx.js
```

요청이 오면 Spring MVC는 **컨트롤러(`@GetMapping`) 매핑을 먼저** 찾고, 맞는 게 없으면 정적 리소스 처리기로 넘긴다. 정적 파일도 없으면 `NoResourceFoundException` → 이 프로젝트에서는 `GlobalExceptionHandler`가 JSON 404로 바꾼다([07](./07-spring-mvc-exception-handling.md)).

그래서 화면 주소용 컨트롤러는 **정적 파일 경로와 겹치지 않게** 패턴을 짜야 한다. 컨트롤러가 `/**`를 다 잡아 버리면 JS 파일 요청까지 컨트롤러로 와서 정적 파일이 서빙되지 않는다.

### 3.5 리다이렉트 상태 코드

| 코드 | 이름 | 의미 | 다시 요청할 때 메서드 | 검색엔진 |
| --- | --- | --- | --- | --- |
| 301 | Moved Permanently | 영구 이동 | 브라우저가 POST를 GET으로 바꿔 보낼 수 있음 | 새 주소로 색인을 옮김 |
| 302 | Found | 임시 이동 | (301과 같음) | 옛 주소를 유지 |
| 307 | Temporary Redirect | 임시 이동 | **메서드·본문 유지** | 옛 주소 유지 |
| 308 | Permanent Redirect | 영구 이동 | **메서드·본문 유지** | 새 주소로 옮김 |

- 화면 주소는 GET이라 301과 308의 차이(메서드 유지)는 상관없다. 오래되고 모든 클라이언트가 확실히 아는 301을 쓴다.
- **영구**(301)를 쓰는 이유: 블로그 이사는 되돌리지 않는 변화이고, 검색엔진이 옛 주소의 색인과 평판을 새 주소로 옮기게 하려는 것이다(R-04 "리다이렉트를 서버가 하는 이유는 검색엔진도 따라가게 하기 위함").
- 브라우저는 301을 **강하게 캐시**한다. 잘못된 301을 한 번 내보내면 사용자 브라우저가 서버에 묻지도 않고 계속 이동시킬 수 있다. 그래서 301 규칙은 테스트로 꼼꼼히 확인한다.
- 리다이렉트는 응답의 `Location` 헤더에 새 주소를 담는다.

### 3.6 404 상태로 index.html을 주는 이유

없는 블로그 주소에 무엇을 줘야 할까?

| 응답 | 사람이 보는 것 | 검색엔진이 아는 것 |
| --- | --- | --- |
| 200 + index.html | React가 "페이지를 찾을 수 없습니다" | **있는 페이지**로 색인(이른바 soft 404) |
| 404 + JSON | 브라우저에 JSON 글자 | 없는 페이지 |
| **404 + index.html** | React가 404 화면 | **없는 페이지** |

이 프로젝트는 세 번째를 쓴다. 사람에게는 앱의 404 화면을, 검색엔진에는 정확한 상태 코드를 준다.

## 4. 동작 원리

화면 주소 요청 하나가 처리되는 순서다.

```
GET /category/3   Host: alpha.blog.test
 │
 ├─ 보안 필터: 로그인 회원 확인 (화면 요청이면 정지 회원도 비회원으로)
 │
 ├─ 컨트롤러 매핑 찾기
 │    SpaForwardController 패턴에 맞나? (/api, /uploads, /assets 아님, 점 없음, 5단계 이하)
 │    └ 맞음 → page()
 │
 ├─ Host 해석 (BlogHostResolver)
 │    Platform  → 200 index.html
 │    Unknown   → .blog.test 아래 주소면 404 index.html, 아니면(localhost 등) 200
 │    BlogAddress → blogPage()
 │
 └─ blogPage()
      블로그 없음/삭제         → 404
      경로가 /{숫자}(글 주소)  → 글 가시성 판단 → 301 / 404 / 200     ← 블로그 이사보다 먼저!
      블로그 볼 수 없음        → 404
      블로그 이사함            → 주인의 /manage/** 면 200, 아니면 새 블로그로 301 (새 블로그 삭제됐으면 404)
      그 밖                   → 200 index.html
```

200을 받은 브라우저는 `index.html` → `/assets/index-해시.js`(정적 파일, 컨트롤러를 거치지 않음) → React 실행 → React Router가 `/category/3` 화면 → `/api/...`로 데이터 요청.

## 5. 이 프로젝트에서는

`src/main/java/com/nhnacademy/blog/global/config/SpaForwardController.java`

### 5.1 경로 패턴

```java
private static final String FIRST = "{s1:(?!api$|uploads$|assets$)[^.]+}";

@GetMapping({
        "/",
        "/" + FIRST,
        "/" + FIRST + "/{s2:[^.]+}",
        "/" + FIRST + "/{s2:[^.]+}/{s3:[^.]+}",
        "/" + FIRST + "/{s2:[^.]+}/{s3:[^.]+}/{s4:[^.]+}",
        "/" + FIRST + "/{s2:[^.]+}/{s3:[^.]+}/{s4:[^.]+}/{s5:[^.]+}"})
```

Spring의 경로 패턴에서 `{이름:정규식}`은 **경로 한 칸(segment, `/`와 `/` 사이)**이 그 정규식에 맞을 때만 매칭된다.

| 조각 | 뜻 |
| --- | --- |
| `[^.]+` | 점(`.`)이 아닌 글자 1개 이상. **점이 있으면 파일**로 보고 제외한다(`favicon.svg`, `index-a1b2.js`) |
| `(?!api$\|uploads$\|assets$)` | **부정 전방 탐색(negative lookahead)**. "이 칸이 정확히 `api`, `uploads`, `assets`가 아니어야 한다". `$`가 있어서 `apidocs`처럼 `api`로 시작하는 다른 이름은 통과한다 |
| 첫 칸에만 `FIRST` | `/api/...`, `/uploads/...`, `/assets/...`는 첫 칸에서 걸러진다 |
| 1~5칸을 따로 나열 | `{이름:정규식}`은 한 칸만 맞추고 여러 칸을 한 번에 맞추는 `**`에는 정규식 조건을 걸 수 없어서, "모든 칸에 점이 없어야 한다"를 표현하려면 깊이별로 나열하는 것이 가장 단순하다 |

예:

| 요청 경로 | 매칭? | 이유 |
| --- | --- | --- |
| `/` | 예 | |
| `/login`, `/15`, `/category/3` | 예 | |
| `/manage/posts/12/edit` | 예 | 4칸 |
| `/favicon.svg` | 아니오 | 점 → 정적 파일 처리 |
| `/assets/index-a1b2.js` | 아니오 | 첫 칸 `assets` |
| `/api/posts` | 아니오 | 첫 칸 `api` → API 컨트롤러 또는 JSON 404 |
| `/a/b/c/d/e/f` | 아니오 | 6칸 → 정적 리소스 처리 → JSON 404(아래 함정 참고) |

### 5.2 Host별 분기

```java
public ResponseEntity<Resource> page(HttpServletRequest request) {
    return switch (blogHostResolver.resolve(request)) {
        case RequestHost.Platform platform -> app(HttpStatus.OK);
        case RequestHost.Unknown unknown -> isUnderPlatform(request) ? app(HttpStatus.NOT_FOUND) : app(HttpStatus.OK);
        case RequestHost.BlogAddress blogAddress -> blogPage(request);
    };
}
```

- `RequestHost`가 sealed interface라 세 경우를 다 다뤘는지 컴파일러가 확인한다([16](./16-authorization-visibility.md)).
- `Unknown`이 두 가지로 갈린다. `admin.blog.test`(예약어), `a.b.blog.test`처럼 **블로그 주소 모양인데 규칙에 안 맞으면** 없는 블로그라 404. `localhost`처럼 아예 이 서비스 도메인이 아니면(개발 중 `localhost:8080`으로 접속) 플랫폼 화면처럼 200을 준다.

### 5.3 블로그 화면 판단

```java
private ResponseEntity<Resource> blogPage(HttpServletRequest request) {
    Optional<Blog> found = blogHostResolver.findBlog(request);
    if (found.isEmpty() || found.get().isDeleted()) {
        return app(HttpStatus.NOT_FOUND);                       // (1) 없거나 삭제된 블로그
    }
    Blog blog = found.get();
    Long viewerId = LoginMembers.currentId();
    String path = request.getRequestURI();

    var postPath = POST_PATH.matcher(path);                     // (2) ^/(\d{1,18})$
    if (postPath.matches()) {
        return switch (postVisibilityPolicy.decide(Long.valueOf(postPath.group(1)), blog, viewerId)) {
            case PostAccess.MovedTo movedTo -> redirect(request, movedTo.blog());
            case PostAccess.NotFound notFound -> app(HttpStatus.NOT_FOUND);
            case PostAccess.Owner owner -> app(HttpStatus.OK);
            case PostAccess.Visible visible -> app(HttpStatus.OK);
            case PostAccess.SubscribersOnly subscribersOnly -> app(HttpStatus.OK);
        };
    }

    if (!blogVisibilityPolicy.canView(blog, viewerId)) {
        return app(HttpStatus.NOT_FOUND);                       // (3) 이용 제한·주인 정지(주인이 아니면)
    }
    if (blog.isMoved()) {                                       // (4) 이사한 블로그
        if (isManagePath(path) && blog.isOwnedBy(viewerId)) {
            return app(HttpStatus.OK);
        }
        Blog target = blog.getMovedToBlog();
        return target.isDeleted() ? app(HttpStatus.NOT_FOUND) : redirect(request, target);
    }
    return app(HttpStatus.OK);
}
```

1. 블로그가 없거나 삭제됐으면 404 화면.
2. **글 주소**(`/` 뒤에 숫자 1~18자리만)면 글 가시성 판단([16](./16-authorization-visibility.md))으로 결정한다. 18자리로 제한한 이유는 `Long` 최댓값(약 9.2×10¹⁸, 19자리)을 넘는 숫자가 `Long.valueOf`에서 예외를 내지 않게 하려는 것이다. 구독자 공개 글(`SubscribersOnly`)은 200을 준다. 화면이 뜬 뒤 React가 API를 부르면 API가 403 `SUBSCRIBERS_ONLY`와 블로그 정보를 주고, React가 구독 안내를 그린다.
3. 이용 제한 블로그, 주인이 정지된 블로그는 주인이 아니면 404.
4. 이사한 블로그: 주인의 관리 화면(`/manage`, `/manage/...`)은 옛 주소에서 계속 쓴다(BLOG-06). 나머지는 새 블로그의 **같은 경로**로 301. 이사 간 블로그가 삭제됐으면 리다이렉트도 끊기고 404(R-08).

### 5.4 글 확인을 이사 확인보다 먼저 하는 이유

블로그 A가 C로 이사했지만, 글 15는 A에 남겨 뒀다(글 이동과 블로그 이사는 별개, R-08). 만약 이사 확인을 먼저 하면:

```
GET a.blog.com/15
  → A는 이사함 → 301 c.blog.com/15
GET c.blog.com/15
  → 글 15는 A 소속 → ②"다른 블로그 소속, 볼 수 있음" → 301 a.blog.com/15
GET a.blog.com/15
  → A는 이사함 → 301 c.blog.com/15
  ... 무한 반복 (브라우저: "리디렉션한 횟수가 너무 많습니다")
```

글 주소를 먼저 판단하면, 글 15는 A 소속이므로 `a.blog.com/15`에서 그대로 200이다. 글이 C로 옮겨 간 경우에는 ②에서 `c.blog.com/15`로 301이 되고, C에서는 C 소속이라 200으로 끝난다. 테스트 `SpaForwardIntegrationTest.postLeftInMovedBlogStaysAtOldAddress`가 이 경우를 확인한다(rest-api.md "화면 주소 단계"에 지원 확인으로 기록).

### 5.5 응답 만들기

```java
private ResponseEntity<Resource> redirect(HttpServletRequest request, Blog target) {
    String query = request.getQueryString();
    String pathAndQuery = request.getRequestURI() + (query == null ? "" : "?" + query);
    return ResponseEntity.status(HttpStatus.MOVED_PERMANENTLY)
            .location(URI.create(blogHostResolver.blogUrl(request, target, pathAndQuery)))
            .build();
}
```

경로와 쿼리스트링(`?page=2`)을 그대로 붙여, 같은 화면의 새 주소로 보낸다. 주소 조립은 [15](./15-subdomain-host-routing.md)의 `blogUrl`이다.

```java
private static final Resource INDEX = new ClassPathResource("static/index.html");

private ResponseEntity<Resource> app(HttpStatus status) {
    return ResponseEntity.status(status)
            .contentType(MediaType.TEXT_HTML)
            .cacheControl(CacheControl.noCache())
            .body(INDEX.exists() ? INDEX : notBuilt());
}
```

- 정적 파일 `static/index.html`을 **원하는 상태 코드와 함께** 직접 응답한다. 정적 리소스 처리기로 넘기면(forward) 상태 코드를 마음대로 정하기 어렵다.
- `Cache-Control: no-cache`: "저장은 해도 되지만 쓸 때마다 서버에 확인하라"는 뜻이다("저장하지 마라"는 `no-store`). 새 버전을 배포하면 `index.html` 안의 JS 파일 이름(해시)이 바뀌는데, 브라우저가 옛 `index.html`을 계속 쓰면 옛 JS를 받는다. 그래서 `index.html`은 매번 확인하게 한다.
- `notBuilt()`: 프론트를 빌드하지 않고 백엔드만 띄웠을 때 빈 화면 대신 "빌드하세요" 안내를 준다.

### 5.6 테스트

`src/test/.../global/config/SpaForwardIntegrationTest.java`의 주요 테스트:

| 테스트 | 확인 |
| --- | --- |
| `platformPagesServeTheApp` | `blog.test/`, `/signup`, `localhost/login` → 200 HTML |
| `unknownBlogAddressIs404Page` | 없는 블로그·예약어 → 404 HTML |
| `movedBlogRedirectsWithSamePathExceptOwnersManagePages` | 이사 → 301 `Location: http://{새}.blog.test/category/3?page=2`, 주인 관리 화면 200 |
| `movedToDeletedBlogIs404` | 이사 간 블로그가 삭제 → 404 |
| `postOfAnotherBlogRedirectsWhenVisible` | 다른 블로그 글 공개 → 301, 비공개 → 404 |
| `invisiblePostIs404PageEvenWhenLoggedIn` | 남의 비공개 글 → 비회원·다른 회원 404, 주인 200 |
| `postLeftInMovedBlogStaysAtOldAddress` | 위 5.4 |
| `assetsAndApiAreNotPages` | `/assets/missing.js`, `/api/missing` → JSON 404 |

### 5.7 Vite: 개발 서버와 빌드

**개발 중 두 서버**

```
브라우저 ─▶ http://alpha.blog.test:5173   (Vite 개발 서버)
              ├ /, /15, /manage ...  → Vite가 index.html과 소스(.tsx)를 바로 변환해 줌
              ├ /api/..., /uploads/... → 프록시 → http://localhost:8080 (Spring Boot)
              └ 소스 저장 → HMR로 화면만 갱신
```

- **번들링**: 수십·수백 개 소스 파일(`.tsx`)을 브라우저가 실행할 수 있는 JS 몇 개로 묶고 변환(TypeScript·JSX → JS)하는 일.
- Vite 개발 서버는 미리 다 묶지 않고, 브라우저가 요청하는 파일을 그때그때 변환해 준다(브라우저의 ES 모듈 기능 이용). 그래서 시작이 빠르다.
- **HMR(Hot Module Replacement)**: 소스를 저장하면 페이지 전체를 새로고침하지 않고 바뀐 모듈만 바꿔 끼운다. 입력하던 상태가 유지된다.
- 개발 서버에서는 `SpaForwardController`를 거치지 않는다(Vite가 화면 주소에 index.html을 준다). 그래서 **301·404 화면 동작은 8080으로 접속해야** 확인할 수 있다.
- 프록시와 `allowedHosts`는 [15](./15-subdomain-host-routing.md) 5.6 참고.

**빌드 결과**

```bash
cd frontend && npm run build      # tsc -b(타입 검사) && vite build
```

```
frontend/dist/
├── index.html                      ← <script src="/assets/index-BuzWKI_C.js">
├── favicon.svg
└── assets/
    ├── index-BuzWKI_C.js           ← 파일 내용의 해시가 이름에 들어감
    └── index-Ch9eZn3x.css
```

- 파일 이름의 **해시**는 내용이 바뀔 때만 바뀐다. 그래서 JS·CSS는 브라우저가 오래 캐시해도 안전하고(내용이 바뀌면 이름이 바뀌니까), `index.html`만 매번 확인하면 된다(위 `no-cache`).
- `npm run build`의 `tsc -b`가 먼저 타입 오류를 검사한다. 타입 오류가 있으면 빌드가 실패한다([19](./19-react-router-api-client.md)의 사건).

**jar 하나로 배포**

`scripts/build-frontend.sh`

```bash
set -euo pipefail                         # 명령 하나라도 실패하면 즉시 멈춤
ROOT="$(cd "$(dirname "$0")/.." && pwd)"  # 스크립트 위치 기준으로 저장소 루트 찾기
STATIC="$ROOT/src/main/resources/static"

cd "$ROOT/frontend"
npm ci                                    # package-lock.json 그대로 설치 (재현 가능)
npm run build

rm -rf "$STATIC"                          # 옛 빌드 결과 지우기 (해시 다른 옛 파일이 남지 않게)
mkdir -p "$STATIC"
cp -R dist/. "$STATIC/"
```

- `npm ci`와 `npm install`의 차이: `ci`는 `package-lock.json`에 적힌 버전 그대로 깨끗하게 설치한다. 배포 빌드는 매번 같은 결과가 나와야 하므로 `ci`를 쓴다.
- 그다음 `./mvnw package`를 하면 `static/`이 jar 안에 들어가, `java -jar`로 띄운 서버가 API와 화면을 함께 서빙한다.
- `src/main/resources/static/`은 빌드 결과라 `.gitignore`에 있다.

## 6. 자주 하는 실수와 함정

1. **`@GetMapping("/**")`로 전부 잡기**: 정적 파일(JS, CSS, 이미지)까지 컨트롤러로 와서 `index.html`이 대신 나간다. 브라우저 콘솔에 "Unexpected token '<'"(JS 자리에 HTML이 옴)가 뜨면 이 문제다.
2. **모든 화면 주소에 200**: 없는 페이지가 검색엔진에 색인된다(soft 404).
3. **잘못된 301**: 브라우저가 오래 기억한다. 개발 중 잘못 낸 301 때문에 이상하면 브라우저 캐시를 지우거나 시크릿 창으로 확인한다.
4. **리다이렉트 순서**: 블로그 이사와 글 소속 판단 순서를 바꾸면 무한 리다이렉트(5.4).
5. **6칸 이상의 화면 주소**: 지금 패턴은 5칸까지라, React Router에 6칸 이상 경로를 만들면 새로고침 시 JSON 404가 나온다. 깊은 화면 주소를 만들면 패턴도 늘려야 한다.
6. **점이 들어간 화면 주소**: `/tag/node.js` 같은 경로는 점 때문에 정적 파일로 취급되어 새로고침 시 404가 된다. 태그 화면 주소를 만들 때(스텝 7) 태그 이름을 경로에 그대로 넣지 않거나 패턴을 조정해야 한다.
7. **개발 서버(5173)에서 301 확인**: Vite는 서버 로직을 모른다. 8080으로 확인한다.
8. **`index.html`을 길게 캐시**: 배포 후에도 옛 JS를 받는다. `index.html`은 `no-cache`, 해시 파일은 길게.
9. **빌드 없이 jar 만들기**: `static/`이 비어 화면 대신 "프론트 빌드가 없습니다" 안내가 나온다. `scripts/build-frontend.sh`를 먼저 돌린다.

## 7. 직접 해 보기

**실습 1. SPA의 새로고침 문제 눈으로 보기**

```bash
cd frontend && npm run dev
```

브라우저에서 `http://localhost:5173/login`을 열고 개발자 도구 Network 탭을 본다. 주소창에 직접 쳤을 때는 문서(`login`) 요청이 서버로 가고, 앱 안에서 링크로 이동하면(스텝 4 이후 화면에 링크가 생기면) 문서 요청 없이 주소만 바뀐다.

**실습 2. 서버의 화면 주소 처리**

```bash
./scripts/build-frontend.sh && ./mvnw spring-boot:run
curl -s -o /dev/null -w "%{http_code} %{content_type}\n" -H "Host: blog.test" localhost:8080/login            # 200 text/html
curl -s -o /dev/null -w "%{http_code} %{content_type}\n" -H "Host: nobody-here.blog.test" localhost:8080/    # 404 text/html
curl -s -o /dev/null -w "%{http_code} %{content_type}\n" -H "Host: blog.test" localhost:8080/favicon.svg      # 200 image/svg+xml
curl -s -H "Host: blog.test" localhost:8080/assets/none.js                                                    # JSON 404
curl -sI -H "Host: blog.test" localhost:8080/ | grep -i cache-control                                         # no-cache
```

**실습 3. 정적 파일을 가로채는 실수 재현**

1. `SpaForwardController`의 매핑을 `@GetMapping("/**")` 하나로 바꾼다.
2. 서버를 다시 띄우고 `curl -s -H "Host: blog.test" localhost:8080/favicon.svg | head -c 50`
3. 기대 결과: SVG 대신 `<!doctype html>`이 나온다. 되돌린다.

**실습 4. 무한 리다이렉트 재현**

1. `blogPage()`에서 `if (blog.isMoved()) {...}` 블록을 글 주소 판단(`postPath.matches()`) **위로** 옮긴다.
2. `./mvnw test -Dtest=SpaForwardIntegrationTest#postLeftInMovedBlogStaysAtOldAddress`
3. 기대 결과: 200이 아니라 301이 나와 실패한다(실제 브라우저였다면 왕복이 반복된다). 되돌린다.

**실습 5. 빌드 결과 살펴보기**

```bash
cd frontend && npm run build && ls dist/assets && grep -o 'assets/[^"]*' dist/index.html
```

소스를 한 글자 바꾸고 다시 빌드하면 JS 파일 이름의 해시가 바뀌는 것을 볼 수 있다.

## 8. 확인 문제

1. SPA에서 새로고침하면 서버로 어떤 요청이 가고, 서버가 아무것도 안 하면 어떻게 되나?
<details><summary>답</summary>주소창의 경로(예: <code>GET /15</code>)로 문서 요청이 간다. 서버에 그 경로의 파일이나 매핑이 없으면 404가 나서 화면이 뜨지 않는다.</details>

2. 화면 주소 컨트롤러가 점(`.`)이 있는 경로를 받지 않는 이유는?
<details><summary>답</summary>점이 있는 경로는 <code>favicon.svg</code>, <code>index-해시.js</code> 같은 정적 파일이라 정적 리소스 처리기가 파일 그대로 내줘야 한다. 컨트롤러가 받으면 파일 대신 index.html이 나간다.</details>

3. `(?!api$|uploads$|assets$)`에서 `$`를 빼면 무엇이 달라지나?
<details><summary>답</summary>"api로 시작하는" 모든 칸이 제외되어 <code>/apidocs</code>, <code>/assets-guide</code> 같은 화면 주소까지 컨트롤러가 받지 못한다. <code>$</code>가 있어야 정확히 그 이름일 때만 제외한다.</details>

4. 없는 블로그에 200 + index.html이 아니라 404 + index.html을 주는 이유는?
<details><summary>답</summary>사람에게는 React의 404 화면을 보여 주면서, 검색엔진에는 "없는 페이지"라는 정확한 상태를 알려 색인되지 않게 하기 위해서다(soft 404 방지).</details>

5. 블로그 이사에 302가 아니라 301을 쓰는 이유는?
<details><summary>답</summary>이사는 영구적인 변화라, 검색엔진이 옛 주소의 색인을 새 주소로 옮기게 하려면 영구 이동(301)이어야 한다. 302는 임시 이동이라 옛 주소를 유지한다.</details>

6. 이사한 블로그에 남은 글을 처리할 때 글 판단을 먼저 하지 않으면 어떤 일이 생기나?
<details><summary>답</summary>옛 블로그 주소 → (블로그 이사) 새 주소 → (글은 옛 블로그 소속) 옛 주소 → … 로 301이 무한 반복된다.</details>

7. `index.html`에는 `no-cache`를 주고 `assets/index-해시.js`는 길게 캐시해도 되는 이유는?
<details><summary>답</summary>JS 파일 이름에 내용의 해시가 들어 있어 내용이 바뀌면 이름이 바뀐다. index.html만 매번 확인하면 새 이름을 받게 되므로, 해시 파일은 오래 캐시해도 옛 코드를 쓰지 않는다.</details>

8. 개발 서버(5173)로 접속하면 왜 이사 301을 확인할 수 없나?
<details><summary>답</summary>화면 주소 요청을 Vite가 직접 처리해 index.html을 주고, Spring Boot의 <code>SpaForwardController</code>를 거치지 않기 때문이다. API(<code>/api</code>)만 8080으로 넘어간다.</details>

## 9. 더 읽을거리

- MDN Web Docs, "History API" (`pushState`, `popstate`)
- MDN Web Docs, HTTP 리다이렉트(301, 302, 307, 308), `Cache-Control`
- RFC 9110 HTTP Semantics, 15.4 Redirection 3xx
- Google 검색 센터 문서, "리디렉션과 Google 검색", "소프트 404 오류"
- Spring Framework 레퍼런스, Web MVC "URI Patterns"(`PathPattern`), "Static Resources"
- Spring Boot 레퍼런스, "Static Content"
- Vite 문서, "Why Vite", "Building for Production", "Server Options"
- npm 문서, `npm ci`
