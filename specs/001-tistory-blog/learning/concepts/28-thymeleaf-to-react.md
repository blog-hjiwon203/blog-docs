# 28. Thymeleaf에서 React로: 서버가 그리는 화면과 브라우저가 그리는 화면

> 관련 스텝: [스텝 1](../step-01.md) (T002, T004), [스텝 3](../step-03.md) (T010, T015), [스텝 4](../step-04.md) (T026), [스텝 5](../step-05.md) (T035) · 관련 개념: [07-spring-mvc-exception-handling](./07-spring-mvc-exception-handling.md), [18-spa-server-routing](./18-spa-server-routing.md), [19-react-router-api-client](./19-react-router-api-client.md), [22-bean-validation](./22-bean-validation.md), [24-layered-architecture-dto](./24-layered-architecture-dto.md), [25-react-forms-data](./25-react-forms-data.md)

## 1. 이 문서로 배우는 것

Thymeleaf(또는 JSP)로 화면을 만들어 본 사람이 이 프로젝트의 React 화면을 이해하도록 다리를 놓는다.

- 서버 렌더링(Thymeleaf)과 클라이언트 렌더링(React)이 **누가, 언제, 어디서** HTML을 만드는지
- 같은 "블로그 메인" 화면을 두 방식으로 만들면 컨트롤러·템플릿·데이터 흐름이 어떻게 달라지는지
- Thymeleaf에는 없던 **빌드** 단계가 왜 생겼고, 무엇을 하는지(TypeScript·JSX 변환, 묶기, 파일 이름 해시)
- `frontend/src`의 원본과 `src/main/resources/static`의 결과물이 어떻게 다른지
- 폼 제출, 입력 오류 표시, 로그인 확인, 페이지 이동이 두 방식에서 어떻게 다른지
- 개발 서버(`npm run dev`)와 빌드(`./scripts/build-frontend.sh`)를 언제 쓰는지
- 두 방식을 섞는 법과, 이 프로젝트에서 섞을 자리(T072)

**먼저 알면 좋은 것**: Thymeleaf로 `@Controller` + `Model` + `templates/*.html`을 써 본 경험. 이 문서는 그것을 출발점으로 삼는다.

## 2. 왜 필요한가

Thymeleaf에 익숙하면 이 프로젝트에서 이런 질문이 생긴다.

- 컨트롤러가 왜 화면(뷰 이름)이 아니라 JSON만 돌려주지?
- `templates/` 폴더가 없는데 화면은 어디서 오지?
- 왜 `./scripts/build-frontend.sh`를 돌려야 화면이 바뀌지? Thymeleaf는 HTML만 고치면 됐는데.
- `SpaForwardController` 하나가 모든 화면 주소에 같은 `index.html`을 주는데, 그러면 화면은 어떻게 달라지지?

답은 하나로 모인다. **HTML을 만드는 곳이 서버에서 브라우저로 옮겨 갔다.** 이 한 가지 차이가 컨트롤러 모양, 폴더 구조, 빌드 단계, 폼 처리 방식까지 바꾼다.

## 3. 기본 개념

### 3.1 화면을 그린다는 것

브라우저가 보여 주는 것은 결국 HTML(+CSS)이다. 차이는 **완성된 HTML을 누가 만드느냐**다.

| | 서버 렌더링 (Thymeleaf, JSP) | 클라이언트 렌더링 (React) |
| --- | --- | --- |
| HTML을 만드는 곳 | 서버(Java) | 브라우저(JavaScript) |
| 서버가 보내는 것 | 데이터가 다 들어간 HTML | 거의 빈 HTML + JS 파일, 그리고 따로 JSON |
| 데이터를 넣는 법 | 컨트롤러가 `Model`에 담고 템플릿이 `th:text`로 꺼냄 | JS가 `fetch('/api/...')`로 JSON을 받아 화면에 넣음 |
| 다른 화면으로 갈 때 | 서버에 새 페이지 요청 → 새 HTML 전체 | 브라우저 안에서 화면만 바꿈(서버에는 필요한 JSON만) |
| 화면 파일 위치 | `src/main/resources/templates/` | `frontend/src/` (원본), `static/` (빌드 결과) |
| 원본을 서버가 바로 쓰나 | 예 | 아니오, 빌드해서 바꾼 결과를 쓴다 |

18번 문서의 MPA(여러 페이지 앱)·SPA(한 페이지 앱) 구분이 이것이다.

### 3.2 Thymeleaf의 한 바퀴

```
브라우저 GET /posts
  → @Controller가 서비스에서 글 목록을 받아 model.addAttribute("posts", posts)
  → return "blog/main"                      (뷰 이름)
  → Thymeleaf가 templates/blog/main.html을 읽고 th:each, th:text를 실제 값으로 바꿈
  → 완성된 HTML 응답
브라우저: 받은 HTML을 그대로 그림. 끝.
```

템플릿 파일은 **서버가 실행 중에 읽는다.** 그래서 HTML을 고치면(캐시를 끈 개발 설정이면) 새로고침만으로 바뀐다. 빌드할 것이 없다.

### 3.3 React의 한 바퀴

```
브라우저 GET /posts  (화면 주소)
  → SpaForwardController가 static/index.html을 줌   (모든 화면 주소에 같은 파일)
브라우저: index.html 안의 <script src="/assets/index-xxxx.js">를 받아 실행
  → React가 주소(/posts)를 보고 어떤 화면을 그릴지 고름 (React Router)
  → 그 화면이 fetch('/api/posts')로 JSON 요청
  → @RestController가 PageResponse를 JSON으로 응답
  → React가 JSON으로 <article> 등을 만들어 <div id="root"> 안에 넣음
```

요청이 **두 종류**로 나뉜다. 화면 주소 요청(`/posts`)은 늘 같은 껍데기를 받고, 데이터는 `/api/...` 요청으로 따로 받는다.

### 3.4 빌드가 하는 일

React 화면의 원본은 `.tsx` 파일이다. 브라우저는 이것을 그대로 실행하지 못한다. 이유는 세 가지다.

| 원본에 있는 것 | 브라우저가 못 읽는 이유 | 빌드가 바꾸는 모양 |
| --- | --- | --- |
| TypeScript 타입 `post: PostSummary` | 브라우저는 JavaScript만 안다 | 타입을 지운 JS. 지우기 전에 `tsc`가 타입 오류를 검사한다 |
| JSX `<h3>{post.title}</h3>` | JS 문법이 아니다 | `jsx("h3", { children: post.title })` 같은 함수 호출 |
| `import { useState } from 'react'` | 브라우저는 `react`라는 이름이 `node_modules`의 어느 파일인지 모른다 | React·Tiptap 코드까지 파일 몇 개로 묶음(bundling) |

여기에 더해 빌드는 공백·긴 이름을 줄이고(minify), 파일 이름에 내용 해시를 붙인다(`index-P2-O7soy.js`). 내용이 바뀌면 이름도 바뀌므로, 브라우저가 옛 파일을 캐시에서 꺼내 쓰는 일이 없다.

Thymeleaf에 빗대면 이렇다. Thymeleaf는 **요청마다 서버에서** 템플릿을 HTML로 바꾸고, React 빌드는 **배포 전에 한 번** 원본을 브라우저용 JS로 바꾼다.

### 3.5 화면이 "하나"라는 뜻

Thymeleaf 앱은 화면마다 템플릿 파일과 컨트롤러 메서드가 있다. React 앱은 서버 입장에서 화면이 `index.html` 하나다. `/manage/write`와 `/category/5`가 다른 화면으로 보이는 것은 **브라우저의 React Router가 주소를 보고 다른 컴포넌트를 고르기** 때문이다(19번 문서). 그래서 서버에는 "어떤 화면 주소든 `index.html`을 준다"는 컨트롤러 하나(`SpaForwardController`)면 된다.

## 4. 동작 원리

### 4.1 같은 화면, 두 가지 구현

블로그 메인의 글 목록 한 줄을 두 방식으로 만든다고 하자.

**Thymeleaf였다면** (이 프로젝트에 없는 예시 코드)

```java
@Controller
public class BlogPageController {
    @GetMapping("/")
    public String main(@RequestParam(defaultValue = "1") int page, Model model) {
        model.addAttribute("posts", postQueryService.blogPosts(blog, viewerId, null, PageQuery.of(page, null, 10)));
        return "blog/main";                 // templates/blog/main.html
    }
}
```

```html
<!-- templates/blog/main.html -->
<article class="post-item" th:each="post : ${posts.content}">
  <h3><a th:href="@{/{id}(id=${post.id})}" th:text="${post.title}">제목</a></h3>
  <p th:if="${post.summary}" th:text="${post.summary}">요약</p>
  <div class="meta">
    <span th:text="${post.category} ? ${post.category.name} : '미분류'"></span>
    <span th:text="${#temporals.format(post.publishedAt, 'yyyy.MM.dd')}"></span>
  </div>
</article>
```

**이 프로젝트(React)**

서버: 데이터만 JSON으로 준다. `src/main/java/com/nhnacademy/blog/post/presentation/PostController.java`

```java
@GetMapping("/api/posts")
public PageResponse<PostSummaryResponse> posts(@CurrentBlog Blog blog,
                                               @RequestParam(required = false) Integer page,
                                               @RequestParam(required = false) Integer size,
                                               @RequestParam(required = false) Long categoryId) {
    PageQuery pageQuery = PageQuery.of(page, size, PostQueryService.BLOG_PAGE_SIZE);
    return PageResponse.from(
            postQueryService.blogPosts(blog, LoginMembers.currentId(), categoryId, pageQuery),
            post -> PostSummaryResponse.of(post, blog));
}
```

브라우저: JSON을 받아 HTML을 만든다. `frontend/src/pages/blog/BlogMainPage.tsx`

```tsx
function PostItem({ post, owner }: { post: PostSummary; owner: boolean }) {
  return (
    <article className="post-item">
      <div className="row between nowrap">
        <h3><Link to={`/${post.id}`}>{post.title}</Link></h3>
        {owner && <Link className="small" to={`/manage/posts/${post.id}/edit`}>수정</Link>}
      </div>
      {post.summary && <p>{post.summary}</p>}
      <div className="meta">
        <span>{post.category?.name ?? '미분류'}</span>
        <span>{formatDate(post.publishedAt)}</span>
        <span>공감 {post.likeCount}</span>
        <span>댓글 {post.commentCount}</span>
      </div>
    </article>
  )
}
```

나란히 놓으면 대응 관계가 보인다.

| Thymeleaf | React(JSX) | 뜻 |
| --- | --- | --- |
| `th:each="post : ${posts.content}"` | `posts.content.map((post) => <PostItem ... />)` | 반복 |
| `th:text="${post.title}"` | `{post.title}` | 값 넣기(둘 다 글자를 이스케이프한다) |
| `th:if="${post.summary}"` | `{post.summary && <p>...</p>}` | 조건부로 그리기 |
| `th:href="@{/{id}(id=${post.id})}"` | `` <Link to={`/${post.id}`}> `` | 링크 |
| `class="..."` | `className="..."` | JSX에서는 `class`가 JS 예약어라 `className` |
| `model.addAttribute("posts", ...)` | `useState` + `api('/api/posts')` | 화면에 쓸 데이터 |

차이는 **데이터를 넣는 시점**이다. Thymeleaf는 서버에서 응답을 보내기 전에, React는 브라우저에서 JSON이 도착한 뒤에 넣는다.

### 4.2 빌드 전과 후

원본 `frontend/index.html`:

```html
<body>
  <div id="root"></div>
  <script type="module" src="/src/main.tsx"></script>
</body>
```

빌드 결과 `frontend/dist/index.html` (→ `static/index.html`로 복사됨):

```html
<head>
  ...
  <script type="module" crossorigin src="/assets/index-P2-O7soy.js"></script>
  <link rel="stylesheet" crossorigin href="/assets/index-DNUW8DUQ.css">
</head>
<body>
  <div id="root"></div>
</body>
```

- `/src/main.tsx`(원본)가 `/assets/index-P2-O7soy.js`(빌드 결과)로 바뀌었다.
- `<div id="root"></div>`는 비어 있다. 글 목록도, 블로그 이름도 HTML에 없다. 전부 JS가 실행된 뒤에 채운다. Thymeleaf 응답과 가장 크게 다른 점이다.
- `index-P2-O7soy.js`는 약 600KB다. React, React Router, Tiptap, 그리고 우리가 쓴 모든 화면이 한 파일에 줄여서 묶여 있다. 열어 보면 `var e=Object.create,t=Object.defineProperty,...`처럼 사람이 읽기 어려운 모양이다.

### 4.3 빌드 스크립트

`scripts/build-frontend.sh`

```bash
cd "$ROOT/frontend"
npm ci                     # package-lock.json에 적힌 버전 그대로 설치
npm run build              # tsc -b && vite build → frontend/dist/

rm -rf "$STATIC"
mkdir -p "$STATIC"
cp -R dist/. "$STATIC/"    # src/main/resources/static/ 으로 복사
```

- `npm run build`는 `package.json`의 `"build": "tsc -b && vite build"`다. 먼저 `tsc`가 타입 오류를 검사하고, 통과하면 Vite가 변환·묶기를 한다.
- 결과를 `static/`에 두면 Spring Boot가 정적 파일로 내보내고, `./mvnw package` 때 jar 안에도 들어간다.
- `static/`은 `.gitignore`에 있다. 원본만 git에 두고 결과물은 각자 만든다(Java의 `target/`과 같은 대접).

### 4.4 개발할 때는 빌드 없이

```
브라우저 → http://alpha.blog.test:5173   (Vite 개발 서버, npm run dev)
            ├ /src/main.tsx 등 화면 파일: 요청이 올 때마다 그 파일만 바로 변환해서 줌
            └ /api/**, /uploads/**: 8080(Spring)으로 넘김 (vite.config.ts의 proxy)
```

`frontend/vite.config.ts`

```ts
server: {
  allowedHosts: ['.blog.test'],
  proxy: {
    '/api': 'http://localhost:8080',
    '/uploads': 'http://localhost:8080',
  },
},
```

개발 서버는 파일을 저장하면 브라우저 화면을 바로 바꿔 준다(HMR). Thymeleaf에서 템플릿 캐시를 끄고 새로고침하던 경험과 비슷하지만, 새로고침조차 필요 없다.

| 상황 | 쓰는 것 | 주소 |
| --- | --- | --- |
| 화면을 고치면서 보기 | `./mvnw spring-boot:run` + `cd frontend && npm run dev` | `:5173` |
| 완성본을 8080 하나로 확인, 배포 | `./scripts/build-frontend.sh` 후 서버 재시작 | `:8080` |

`spring-boot:run`은 시작할 때 `static/` 파일을 읽어 가므로, 빌드한 뒤에는 **서버를 다시 켜야** 8080에 새 화면이 나온다.

## 5. 이 프로젝트에서는

### 5.1 컨트롤러가 둘로 나뉜다

Thymeleaf 앱의 `@Controller` 하나가 하던 일을 이 프로젝트는 둘로 나눈다.

| 할 일 | Thymeleaf | 이 프로젝트 |
| --- | --- | --- |
| 화면 주소에 HTML 주기 | 화면마다 `@Controller` 메서드 + 템플릿 | `SpaForwardController` 하나가 모든 화면 주소에 `index.html` |
| 화면에 들어갈 데이터 | `Model` | `@RestController`의 JSON (`/api/**`) |
| 이 주소를 볼 수 있나(404·301) | 각 컨트롤러가 판단 | `SpaForwardController`가 먼저 판단, API도 다시 판단 |

`src/main/java/com/nhnacademy/blog/global/config/SpaForwardController.java`의 핵심:

```java
private ResponseEntity<Resource> app(HttpStatus status) {
    return ResponseEntity.status(status)
            .contentType(MediaType.TEXT_HTML)
            .cacheControl(CacheControl.noCache())
            .body(INDEX.exists() ? INDEX : notBuilt());
}
```

- `INDEX`는 `static/index.html`이다. 빌드하지 않았으면 없어서 `notBuilt()` 안내를 준다. 빌드 없이 서버만 띄웠을 때 "프론트 빌드가 없습니다"가 나오는 이유다.
- 없는 블로그면 같은 `index.html`을 **404 상태로** 준다. React는 그 화면에서 404 페이지를 그리고, 검색 엔진은 상태 코드를 보고 없는 페이지로 안다(18번 문서 3.6).

### 5.2 폼 제출

| | Thymeleaf | 이 프로젝트 (`SignupPage`, `PostWritePage`) |
| --- | --- | --- |
| 보내는 법 | `<form method="post" th:action="@{/signup}" th:object="${form}">` → 브라우저가 페이지째 POST | `api('/api/auth/signup', { method: 'POST', body })` → JS가 JSON으로 보냄. 페이지는 그대로 |
| 서버가 받는 것 | `@ModelAttribute SignupForm` (폼 값) | `@RequestBody SignupRequest` (JSON) |
| 성공 뒤 | `return "redirect:/blogs/new"` (PRG 패턴) | 201 JSON → 화면이 `navigate('/blogs/new')` |
| CSRF | Spring Security가 폼에 숨은 토큰(`_csrf`)을 넣음 | `X-Requested-With` 헤더 + SameSite 쿠키(13번 문서) |

### 5.3 입력 오류 보여 주기

Thymeleaf:

```java
public String signup(@Valid @ModelAttribute("form") SignupForm form, BindingResult result) {
    if (result.hasErrors()) {
        return "auth/signup";                // 같은 템플릿을 다시 그림, 입력값은 form에 남아 있음
    }
    ...
}
```

```html
<input th:field="*{password}">
<p class="err" th:if="${#fields.hasErrors('password')}" th:errors="*{password}"></p>
```

이 프로젝트: 서버는 400 JSON(`fieldErrors`)만 주고, 화면이 그것을 칸 아래에 놓는다.

```json
{ "code": "VALIDATION_FAILED", "message": "입력값을 확인해 주세요.",
  "fieldErrors": [{ "field": "password", "reason": "비밀번호는 8자 이상, 영문과 숫자를 함께 써 주세요." }] }
```

`frontend/src/api/errors.ts`

```ts
export function fieldMessages(error: unknown): FieldMessages {
  if (!(error instanceof ApiError)) {
    return {}
  }
  return Object.fromEntries(error.fieldErrors.map((fieldError) => [fieldError.field, fieldError.reason]))
}
```

입력값이 남아 있는 이유도 다르다. Thymeleaf는 서버가 같은 값을 템플릿에 다시 채워 주고, React는 **페이지를 다시 그리지 않으니** `useState`에 든 값이 그대로 있다(25번 문서).

### 5.4 로그인 상태 알기

Thymeleaf에서는 서버가 HTML을 만들 때 로그인 정보를 알고 있으니 `sec:authorize`나 `${#authentication}`으로 바로 머리글을 바꾼다. 이 프로젝트의 화면은 브라우저에서 그려지고, 로그인 쿠키는 HttpOnly라 JS가 읽지 못한다. 그래서 화면이 서버에 물어본다. `frontend/src/app/useMe.ts`

```ts
api<Me>('/api/me', { allowAnonymous: true })
  .then((me) => active && setState({ status: 'member', me }))
  .catch(() => active && setState({ status: 'anonymous' }))
```

응답이 오기 전 잠깐은 로그인 여부를 모른다(`'loading'`). Thymeleaf에는 없던 상태다.

### 5.5 그래도 권한은 서버가 지킨다

React 화면의 "주인이 아니면 관리 화면을 안 보여 줌"(`ManagePage`)은 **안내일 뿐**이다. JS는 사용자 브라우저에서 돌아서 얼마든지 고칠 수 있다. 실제 권한은 API가 다시 검사한다(`BlogOwnerGuard`, `PostService.findOwned`, 헌법 IV). Thymeleaf에서 `sec:authorize`로 버튼을 숨겨도 컨트롤러에서 다시 막아야 했던 것과 같다.

### 5.6 두 방식을 섞는다면

| 섞는 법 | 모양 | 이 프로젝트 |
| --- | --- | --- |
| Thymeleaf 페이지 + React 섬 | 페이지는 Thymeleaf가 그리고, 에디터·댓글처럼 상호작용 많은 칸만 React가 붙음 | 쓰지 않음. 화면 전체를 React로 정했다(plan.md) |
| React 앱 + Thymeleaf 껍데기 | `index.html`을 정적 파일 대신 템플릿으로 주고, 서버가 페이지마다 `<title>`, `og:` 메타 태그 등을 끼워 넣음 | **T072(공유 미리보기)**에서 검토할 자리. 메타 태그 몇 개라면 `SpaForwardController`가 문자열로 끼워 넣는 방법도 있다 |

서버 렌더링이 꼭 필요한 이유는 대개 두 가지다. 첫 화면을 빨리 보여 주고 싶을 때, 그리고 JS를 실행하지 않는 봇(공유 미리보기, 일부 검색 엔진)에게 내용을 보여 줘야 할 때다. 이 블로그에서는 두 번째가 글 공유 미리보기(SOC-02)로 나타난다.

## 6. 자주 하는 실수와 함정

1. **프론트를 고치고 8080으로 확인**: `static/`에는 예전 빌드가 있다. 빌드 스크립트 → 서버 재시작을 하거나 5173 개발 서버로 본다.
2. **`static/`의 파일을 직접 고치기**: 다음 빌드에 지워진다. 원본은 `frontend/src`다.
3. **`.tsx`를 `static/`에 넣기**: 브라우저가 실행하지 못한다. 반드시 빌드 결과를 넣는다.
4. **화면에서만 권한 검사**: JS는 고칠 수 있다. 서버 API가 다시 막아야 한다.
5. **`index.html`에 데이터가 있다고 생각하기**: React 앱의 첫 HTML은 비어 있다. 공유 미리보기 봇은 JS를 실행하지 않으므로, 글 제목을 보여 주려면 서버가 HTML에 넣어야 한다(T072).
6. **`@Controller`와 `@RestController` 헷갈리기**: `@Controller` 메서드가 문자열을 돌려주면 뷰 이름으로 해석된다(Thymeleaf가 없으면 오류). JSON을 주려면 `@RestController` 또는 `@ResponseBody`다. 이 프로젝트에서 `@Controller`는 `ResponseEntity<Resource>`를 돌려주는 `SpaForwardController` 하나뿐이다.
7. **번들이 커짐**: 라이브러리를 더할 때마다 `index-xxxx.js`가 커진다(지금 약 600KB, Tiptap이 큰 몫). 필요하면 화면별로 나눠 불러오는 방법(코드 분할)이 있다.

## 7. 직접 해 보기

**실습 1. 빌드 결과 보기**

```bash
cd frontend && npm run build
cat dist/index.html                 # <div id="root"></div>가 비어 있는 것 확인
ls -la dist/assets                  # 해시가 붙은 JS·CSS
head -c 300 dist/assets/index-*.js  # 줄여진 코드
```

`src/pages/home/HomePage.tsx`의 글자 하나를 바꾸고 다시 빌드하면 JS 파일 이름의 해시가 바뀐다.

**실습 2. 서버가 주는 것과 화면에 보이는 것 비교**

```bash
./scripts/build-frontend.sh && ./mvnw spring-boot:run
curl -s http://alpha.blog.test:8080/ | grep root     # HTML에는 글 목록이 없다
curl -s http://alpha.blog.test:8080/api/posts        # 글 목록은 여기
```

브라우저에서 같은 주소를 열고 개발자 도구 Network 탭을 보면, 문서(`/`) 하나와 `api/me`, `api/blog`, `api/blog/sidebar`, `api/posts` 요청이 따로 보인다. Elements 탭에는 JS가 채운 `<article>`들이 있다(페이지 소스 보기에는 없다).

**실습 3. 개발 서버로 바로 바뀌는 것 보기**

```bash
cd frontend && npm run dev
```

`http://alpha.blog.test:5173`을 열어 둔 채 `BlogMainPage.tsx`의 `'미분류'`를 다른 글자로 바꾸고 저장하면 새로고침 없이 바뀐다. 끝나면 되돌린다.

**실습 4. 빌드 없이 서버만**

`src/main/resources/static`을 잠시 다른 이름으로 옮기고 서버를 다시 띄워 `http://alpha.blog.test:8080/`을 열면 "프론트 빌드가 없습니다" 안내가 나온다. 되돌린다.

## 8. 확인 문제

1. Thymeleaf 앱과 이 프로젝트에서 "블로그 메인" HTML 안의 글 제목은 각각 언제, 어디서 들어가나?
<details><summary>답</summary>Thymeleaf는 서버가 응답을 보내기 전에 템플릿의 <code>th:text</code>를 채워 넣는다. 이 프로젝트는 서버가 빈 <code>index.html</code>을 보내고, 브라우저에서 React가 <code>/api/posts</code> JSON을 받은 뒤 넣는다.</details>

2. Thymeleaf에는 없던 빌드 단계가 React에 필요한 이유 세 가지는?
<details><summary>답</summary>브라우저는 TypeScript 타입 문법을 모르고, JSX는 JS 문법이 아니며, <code>import ... from 'react'</code>처럼 패키지 이름으로 가져오는 것을 찾지 못한다. 빌드가 타입을 지우고, JSX를 함수 호출로 바꾸고, 라이브러리까지 파일 몇 개로 묶는다.</details>

3. 화면 주소가 여러 개인데 `SpaForwardController`가 모두 같은 `index.html`을 줘도 되는 이유는?
<details><summary>답</summary>어느 화면을 그릴지는 브라우저의 React Router가 주소를 보고 정하기 때문이다. 서버는 앱(index.html과 JS)을 전달하고, 404·301 같은 판단만 먼저 한다.</details>

4. 프론트 코드를 고쳤는데 <code>http://alpha.blog.test:8080</code>에서 그대로라면 무엇을 해야 하나?
<details><summary>답</summary><code>./scripts/build-frontend.sh</code>로 다시 빌드해 <code>static/</code>에 넣고 서버를 다시 켠다. 또는 개발 중이면 <code>npm run dev</code>로 띄운 5173 주소에서 본다.</details>

5. Thymeleaf의 <code>BindingResult</code> + <code>th:errors</code>에 해당하는 것이 이 프로젝트에서는 무엇인가?
<details><summary>답</summary>서버의 400 응답 본문 <code>fieldErrors</code>(<code>GlobalExceptionHandler</code>가 만든다)와, 그것을 칸별 문장으로 바꾸는 <code>fieldMessages</code>, 그리고 칸 아래에 <code>{errors.password && &lt;p className="err"&gt;...}</code>로 그리는 화면 코드다.</details>

6. React 화면에서 관리 메뉴를 숨겼다면 서버 권한 검사는 빼도 되나?
<details><summary>답</summary>안 된다. 화면 코드는 사용자 브라우저에서 돌아 고칠 수 있고, API는 화면 없이도 직접 부를 수 있다. 권한은 서버가 지킨다(헌법 IV).</details>

7. 이 프로젝트에서 Thymeleaf 같은 서버 템플릿이 쓸모 있을 자리는 어디고 왜인가?
<details><summary>답</summary>T072 글 공유 미리보기다. 공유 미리보기 봇은 JS를 실행하지 않아 빈 <code>index.html</code>만 보므로, 서버가 글 제목·요약·대표 이미지를 <code>og:</code> 메타 태그로 HTML에 넣어 줘야 한다.</details>

## 9. 더 읽을거리

- Thymeleaf 공식 문서 "Tutorial: Thymeleaf + Spring" (비교용)
- React 공식 문서 "Describing the UI", "Writing Markup with JSX": https://react.dev/learn
- Vite 공식 문서 "Why Vite", "Building for Production": https://vite.dev/guide/
- MDN "Introducing JavaScript objects"와 "JavaScript modules" (import가 브라우저에서 동작하는 방식)
- Spring Boot 레퍼런스 "Static Content" (`static/` 폴더를 내보내는 규칙)
- 이 저장소: [18 SPA와 서버 라우팅](./18-spa-server-routing.md), [19 React Router와 API 클라이언트](./19-react-router-api-client.md), [25 React 폼과 데이터 불러오기](./25-react-forms-data.md)
