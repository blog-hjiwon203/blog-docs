# 19. React 화면 나누기와 API 클라이언트

> 관련 스텝: [스텝 3](../step-03.md) (T015), [스텝 1](../step-01.md) (T002), [스텝 4](../step-04.md) (화면 라우트 추가, 본문 없는 2xx 처리) · 관련 개념: [25-react-forms-data](./25-react-forms-data.md), [21-signup-login](./21-signup-login.md), [15-subdomain-host-routing](./15-subdomain-host-routing.md), [18-spa-server-routing](./18-spa-server-routing.md), [13-csrf-samesite-cors](./13-csrf-samesite-cors.md), [17-idempotency-redis](./17-idempotency-redis.md), [07-spring-mvc-exception-handling](./07-spring-mvc-exception-handling.md)

## 1. 이 문서로 배우는 것

- React 컴포넌트, JSX, props의 아주 기초(이 프로젝트 화면을 읽을 수 있을 만큼)
- React Router 7로 주소마다 다른 화면 그리기(`BrowserRouter`, `Routes`, `Route`, `useParams`, `useSearchParams`, `/manage/*`)
- 왜 React Router 8이 아니라 7을 쓰나
- 주소(플랫폼/블로그)에 따라 다른 라우트 묶음을 그리는 방법(`host.ts`, `App.tsx`)
- `fetch` API 기초: Promise, `async`/`await`, `Response.ok`, `json()`, `credentials`
- 이 프로젝트의 `api()` 함수를 한 줄씩: 헤더, `ApiError`, 본문 없는 성공(202·204), 401이면 로그인 후 원래 주소로, `allowAnonymous`
- 연타 방지 키(`crypto.randomUUID`)와 그 함정
- TypeScript 기초: `type`/`interface`, 유니온 타입, `unknown`과 타입 단언, 제네릭
- Vitest로 테스트하기(`vi.fn`, `vi.stubGlobal`), oxlint, 빌드에서 테스트 타입 오류가 났던 사건

**먼저 알면 좋은 것**: 자바스크립트 기본 문법(함수, 객체, 화살표 함수), HTML 태그. Java를 아는 사람 기준으로 비교해 설명한다.

## 2. 왜 필요한가

프론트에는 두 가지 공통 장치가 필요하다.

**① 주소마다 다른 화면.** 같은 React 앱이 `blog.test`(플랫폼: 홈, 로그인)와 `alpha.blog.test`(블로그: 글 목록, 글, 관리)에서 모두 뜬다([15](./15-subdomain-host-routing.md)). 경로도 `/15`, `/manage/posts`처럼 다양하다. 주소를 보고 알맞은 화면을 고르는 장치가 없으면, 화면마다 `if (location.pathname === ...)`을 쓰게 된다.

**② API 호출 공통 처리.** 화면마다 서버 API를 부른다. 그때마다 지켜야 할 약속이 있다.
- 상태를 바꾸는 요청에는 CSRF 대책 헤더 `X-Requested-With`([13](./13-csrf-samesite-cors.md))
- 연타 방지 대상에는 `Idempotency-Key`([17](./17-idempotency-redis.md))
- 오류는 COM-02 모양(`code`, `message`, `fieldErrors`)으로 오니 같은 방식으로 꺼내기
- 401이면 로그인 화면으로, 로그인 뒤에는 원래 보던 곳으로

이걸 화면마다 `fetch`로 직접 쓰면 반드시 하나를 빠뜨린다. 그래서 `api()` 함수 하나에 모았다.

## 3. 기본 개념

### 3.1 React 컴포넌트, JSX, props

React 화면은 **컴포넌트**(화면 조각을 돌려주는 함수)의 조합이다.

```tsx
// frontend/src/pages/blog/BlogMainPage.tsx (스텝 3 때의 자리 화면. 스텝 4에서 진짜 화면으로 바뀌었다)
export default function BlogMainPage({ address }: { address: string }) {
  return (
    <main>
      <h1>{address} 블로그</h1>
      <p>블로그 메인은 스텝 4에서 만듭니다.</p>
    </main>
  )
}
```

- **JSX**: 자바스크립트 안에 HTML처럼 쓰는 문법. 빌드할 때 `React.createElement(...)` 같은 함수 호출로 바뀐다. `{address}`처럼 중괄호 안에는 자바스크립트 값을 넣는다. 값은 **자동으로 이스케이프**되어, `address`에 `<script>`가 들어 있어도 글자로 보인다(XSS 방지, [14](./14-xss-sanitize-csp.md)).
- **props**: 부모가 자식에게 넘기는 값. `<BlogMainPage address="alpha" />`로 쓰면 함수의 인자 `{ address }`로 받는다. Java로 치면 생성자 인자에 가깝다.
- `{ address }: { address: string }`: 인자 객체를 구조 분해해서 `address`만 꺼내고, 그 타입을 TypeScript로 적은 것이다.
- 조건부로 그리기: `{params.get('redirect') && <p>...</p>}` — 앞이 참(빈 문자열·null이 아님)일 때만 뒤를 그린다.

앱의 시작점은 `frontend/src/main.tsx`다.

```tsx
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

- `index.html`의 `<div id="root">` 안에 React가 화면을 그린다.
- `!`는 TypeScript의 "null이 아님" 단언이다(`getElementById`는 못 찾으면 null을 돌려줄 수 있어서).
- `StrictMode`: 개발 중에만 컴포넌트를 일부러 두 번 실행하는 등 실수를 찾아 주는 모드. 운영 빌드에는 영향이 없다.

### 3.2 React Router 7

`react-router` 패키지가 주소(URL)와 화면을 연결한다. 7부터는 예전의 `react-router-dom`이 `react-router`로 합쳐져 `import ... from 'react-router'`로 쓴다.

| 요소 | 역할 |
| --- | --- |
| `<BrowserRouter>` | 브라우저 주소창과 History API([18](./18-spa-server-routing.md) 3.2)를 연결. 앱 바깥에 하나 |
| `<Routes>` | 안의 `<Route>` 중 지금 주소에 **가장 잘 맞는 하나**를 고름 |
| `<Route path="..." element={...}>` | 이 경로면 이 화면 |
| `:postId` | 경로 변수. `/15`면 `postId = "15"` |
| `*` | 나머지 전부(splat). `/manage/*`는 `/manage`, `/manage/posts/3`을 모두 받음. 단독 `*`는 "어디에도 안 맞으면" |
| `useParams()` | 경로 변수 읽기 |
| `useSearchParams()` | 쿼리스트링(`?redirect=...`) 읽기 |
| `<Link to="/15">` | 새로고침 없이 이동하는 링크(스텝 4부터 사용) |

**경로 순위**: `Routes`는 적힌 순서가 아니라 **구체적인 정도**로 고른다. `/manage`가 `/:postId`(아무 한 칸)에도 맞지만, 고정 글자 `manage`가 있는 `/manage/*`가 더 구체적이라 그쪽이 선택된다.

**`use`로 시작하는 함수(훅, Hook)**: 컴포넌트 안에서만, 그리고 항상 같은 순서로 불러야 한다(조건문 안에서 부르면 안 됨). `.oxlintrc.json`의 `react/rules-of-hooks` 규칙이 이걸 검사한다.

**왜 8이 아니라 7인가**: React Router 8.4.0의 필수 조건(peerDependencies)은 `react >= 19.2.7`이다. plan.md는 React 18이므로, React 18을 지원하는 7의 최신(7.18.4)을 골랐다(plan.md 주요 의존성에 기록). 버전을 고를 때는 `npm view react-router@8 peerDependencies`로 함께 쓰는 라이브러리의 요구 버전을 먼저 확인한다.

### 3.3 fetch와 Promise, async/await

`fetch`는 브라우저 내장 HTTP 요청 함수다.

```ts
const response = await fetch('/api/posts/15')   // 응답이 올 때까지 기다림
if (response.ok) {                               // 상태 코드가 200~299이면 true
  const post = await response.json()             // 본문을 JSON으로 읽기(이것도 기다림)
}
```

- **Promise**: "나중에 값이 생길 약속" 객체. 네트워크처럼 시간이 걸리는 일은 결과 대신 Promise를 먼저 돌려준다.
- **`async` 함수 / `await`**: `await`는 Promise가 끝날 때까지 이 함수의 실행을 멈추고 값을 꺼낸다. `await`는 `async` 함수 안에서만 쓴다. 기다리는 동안 브라우저는 멈추지 않고 다른 일을 한다.
- `async` 함수는 항상 Promise를 돌려준다. 안에서 `throw`하면 그 Promise가 **거부(reject)**되고, 부르는 쪽은 `try/catch`나 `.catch()`로 받는다.

**fetch의 중요한 성질: HTTP 오류로는 실패하지 않는다.** 404, 500 응답도 "응답을 받았으니 성공"이라 Promise가 정상으로 끝난다. 네트워크가 끊겼을 때만 거부된다. 그래서 반드시 `response.ok`나 `response.status`를 직접 확인해야 한다. `api()`가 이걸 대신 해 준다.

**`json()`은 본문이 비면 실패한다.** 204 No Content처럼 본문이 없는 응답에 `json()`을 부르면 오류가 난다.

**`credentials` 옵션**: 요청에 쿠키를 실을지 정한다.

| 값 | 뜻 |
| --- | --- |
| `'omit'` | 쿠키를 보내지 않음 |
| `'same-origin'` (기본값) | 같은 출처 요청에만 쿠키를 보냄 |
| `'include'` | 다른 출처 요청에도 쿠키를 보냄(서버의 CORS 허용 필요) |

이 프로젝트의 API는 항상 **같은 출처**다. `alpha.blog.test:5173`에서 `/api/...`를 부르면 같은 주소로 가고(개발 중에는 Vite가 8080으로 넘겨 줌), 운영에서는 같은 서버다. 그래서 `'same-origin'`으로 충분하고, 로그인 쿠키(`HttpOnly`라 자바스크립트로 읽을 수는 없음)는 브라우저가 알아서 싣는다. `'include'`가 필요 없으니 CORS도 열지 않는다.

### 3.4 TypeScript 기초

TypeScript는 자바스크립트에 **타입**을 붙인 언어다. 빌드할 때 타입을 검사하고, 실행할 때는 타입이 지워진 자바스크립트가 된다.

| 문법 | 뜻 | 이 프로젝트 예 |
| --- | --- | --- |
| `interface X { a: string }` | 객체 모양 정의 | `FieldError`, `ErrorBody`, `RequestOptions` |
| `type X = ...` | 타입에 이름 붙이기(유니온 등 무엇이든) | `Host`, `Method` |
| `a?: string` | 있어도 되고 없어도 되는 필드(`string \| undefined`) | `fieldErrors?`, `idempotencyKey?` |
| `'GET' \| 'POST'` | **유니온 타입**: 이 중 하나 | `Method` |
| `Record<string, string>` | 키·값이 문자열인 객체 | `headers` |
| `unknown` | "무엇인지 모름". 쓰기 전에 확인하거나 단언해야 함 | `body?: unknown`, `detail?: Record<string, unknown>` |
| `x as T` | **타입 단언**: "내가 보장할게, 이건 T야". 실행 시 검사는 없음 | `(await response.json()) as T` |
| `function api<T>(...)` | **제네릭**: 부르는 쪽이 타입을 정함(Java의 `<T>`와 같음) | `api<PostResponse>('/api/posts/1')` |

**구분된 유니온(discriminated union)**: `host.ts`의 `Host` 타입.

```ts
export type Host = { kind: 'platform' } | { kind: 'blog'; address: string }
```

`kind` 값으로 어느 쪽인지 구분한다. `if (host.kind === 'blog')` 안에서는 TypeScript가 `host.address`가 있다는 것을 안다. Java의 sealed interface + record([15](./15-subdomain-host-routing.md)의 `RequestHost`)와 같은 생각이다.

**`unknown`과 `any`**: `any`는 타입 검사를 꺼 버린다(무엇이든 허용). `unknown`은 "모르니까 확인하기 전엔 못 씀"이다. 외부에서 온 값(서버 응답, `catch`로 잡은 오류)에는 `unknown`이 안전하다.

**이 프로젝트의 tsconfig에서 알아 둘 옵션** (`frontend/tsconfig.app.json`):
- `"erasableSyntaxOnly": true`: 타입만 지우면 자바스크립트가 되는 문법만 허용한다. 그래서 `enum`과 생성자 매개변수 프로퍼티(`constructor(readonly status: number)`)를 못 쓴다. `ApiError`가 필드를 따로 선언하고 생성자에서 넣는 이유다.
- `"noUnusedLocals"`, `"noUnusedParameters"`: 안 쓰는 변수·인자가 있으면 오류.
- `"verbatimModuleSyntax": true`: 타입만 가져올 때는 `import type`을 써야 한다.

## 4. 동작 원리

브라우저에서 `http://alpha.blog.test:8080/manage/posts`를 열면:

```
1. 서버(SpaForwardController)가 index.html을 줌 ([18])
2. 브라우저가 /assets/index-해시.js 실행 → main.tsx → <App />
3. App: parseHost("alpha.blog.test") → { kind: 'blog', address: 'alpha' }
        → <BrowserRouter><BlogRoutes /></BrowserRouter>   (스텝 3에서는 address="alpha"를 넘겼다. 5.2)
4. BlogRoutes: 지금 경로 /manage/posts
        /             안 맞음
        /:postId      한 칸만 받으므로 안 맞음 (두 칸이라)
        /manage/*     맞음 → <ManagePage />
5. ManagePage가 api('/api/me'), api('/api/blog')를 부름 (스텝 4)
        → 비회원이면 http://blog.test:8080/login?redirect=http%3A%2F%2Falpha.blog.test%3A8080%2Fmanage%2Fposts 로 이동
6. 로그인 화면이 로그인 성공 후 redirect 주소로 돌려보냄 (우리 주소인지 safeRedirect로 확인, [21](./21-signup-login.md))
```

## 5. 이 프로젝트에서는

### 5.1 host.ts: 주소 판별

`frontend/src/app/host.ts`

```ts
export const PLATFORM_DOMAIN: string = import.meta.env.VITE_PLATFORM_DOMAIN ?? 'blog.test'
```

- `import.meta.env`: Vite가 빌드할 때 넣어 주는 환경 변수. **`VITE_`로 시작하는 것만** 브라우저 코드에 들어간다(비밀 값이 실수로 노출되지 않게). 운영 빌드에서는 `VITE_PLATFORM_DOMAIN=blog.com npm run build`처럼 준다.
- `??`: 왼쪽이 `null`/`undefined`면 오른쪽 값. 지정하지 않으면 개발용 `blog.test`.
- 타입 선언은 `src/vite-env.d.ts`의 `ImportMetaEnv`에 있다.

```ts
export function parseHost(hostname: string, platform: string = PLATFORM_DOMAIN): Host {
  const host = hostname.toLowerCase()
  if (host === platform || host === `www.${platform}` || LOCAL_HOSTS.has(host)) {
    return { kind: 'platform' }                  // blog.test, www.blog.test, localhost, 127.0.0.1
  }
  const suffix = `.${platform}`
  if (host.endsWith(suffix)) {
    const address = host.slice(0, -suffix.length)   // 뒤에서 suffix 길이만큼 잘라냄
    if (address && !address.includes('.')) {
      return { kind: 'blog', address }               // alpha.blog.test → alpha
    }
  }
  return { kind: 'platform' }
}
```

- `platform`을 기본값이 있는 인자로 받는 이유: 테스트에서 `parseHost('My-Blog.blog.com', 'blog.com')`처럼 다른 도메인을 넣어 볼 수 있게.
- 서버의 `BlogHostResolver`와 같은 생각이지만, 주소 규칙(정규식·예약어) 검사는 하지 않는다. 화면을 주기 전에 서버가 없는·예약어 블로그를 이미 404로 막았기 때문이다.
- `` `www.${platform}` ``: 템플릿 문자열. Java의 `"www." + platform`.

```ts
export function platformUrl(path: string, location: Location = window.location): string {
  const port = location.port ? `:${location.port}` : ''
  return `${location.protocol}//${PLATFORM_DOMAIN}${port}${path}`
}
```

블로그 주소에서 플랫폼의 로그인 화면으로 보낼 때 쓴다. 지금 프로토콜(`http:`)과 포트(`8080`이나 `5173`)를 유지한다. `location`을 인자로 받는 이유는 역시 테스트에서 가짜 위치를 넣기 위해서다.

### 5.2 App.tsx와 routes.tsx

`frontend/src/app/App.tsx`

```tsx
export default function App() {
  const host = parseHost(window.location.hostname)
  return (
    <BrowserRouter>
      {host.kind === 'platform' ? <PlatformRoutes /> : <BlogRoutes />}
    </BrowserRouter>
  )
}
```

- `window.location.hostname`은 포트를 뺀 호스트 이름(`alpha.blog.test`).
- `조건 ? A : B`로 두 라우트 묶음 중 하나를 그린다.
- 스텝 3에서는 `<BlogRoutes address={host.address} />`로 주소를 넘겼다. `host.kind === 'platform'`이 거짓인 쪽이라 TypeScript가 `host`를 `{ kind: 'blog'; address }`로 좁혀 `host.address`를 허용했다(3.4).
- **스텝 4에서 address를 넘기지 않게 바꾼 이유**: 블로그 화면이 그리는 내용(이름, 글, 사이드바)은 모두 서버 API(`/api/blog`, `/api/posts`, `/api/blog/sidebar`)가 **요청 Host**로 블로그를 찾아 준다([15](./15-subdomain-host-routing.md)). 화면이 주소를 들고 다닐 필요가 없고, 들고 다니면 서버가 찾은 블로그와 다른 값을 쓸 위험만 생긴다. 블로그 정보를 읽는 일은 훅 `useBlog()`가 맡는다([25](./25-react-forms-data.md)).

`frontend/src/app/routes.tsx`

```tsx
export function PlatformRoutes() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route path="/blogs/new" element={<BlogCreatePage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}

/** 블로그 주소({address}.blog.com)의 화면. 블로그는 Host로 정하므로 주소를 따로 넘기지 않는다 */
export function BlogRoutes() {
  return (
    <Routes>
      <Route path="/" element={<BlogMainPage />} />
      <Route path="/category/:categoryId" element={<BlogMainPage />} />
      <Route path="/:postId" element={<PostPage />} />
      <Route path="/manage/*" element={<ManagePage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
```

스텝 4에서 더한 라우트:

| 주소 | 화면 | 쪽 |
| --- | --- | --- |
| `blog.com/signup` | 회원가입 | 플랫폼 |
| `blog.com/blogs/new` | 블로그 개설 | 플랫폼 |
| `{주소}.blog.com/category/:categoryId` | 블로그 메인과 같은 화면, 그 카테고리 글만(`0`은 미분류) | 블로그 |
| `{주소}.blog.com/manage/*` 안의 `""`(관리 홈), `settings` | 관리 홈, 블로그 설정 | 블로그 (중첩 라우팅) |

- 같은 컴포넌트(`BlogMainPage`)를 두 경로에 걸고, 화면 안에서 `useParams()`의 `categoryId`가 있는지로 전체/카테고리를 나눈다.
- `/category/5`는 두 칸이라 한 칸만 받는 `/:postId`와 겹치지 않는다.
- `/manage/*` 안의 중첩 `<Routes>`는 `ManagePage.tsx`에 있다(`<Route index ...>`, `<Route path="settings" ...>`). 화면 구성은 [25](./25-react-forms-data.md).

- 마지막 `path="*"`는 어디에도 안 맞을 때의 404 화면이다. 서버가 404 상태로 index.html을 줬을 때도([18](./18-spa-server-routing.md)) 결국 이 화면이 그려진다.
- `/manage/*`의 `*`는 스텝 4부터 관리 화면 안에 `<Routes>`를 하나 더 두는 **중첩 라우팅**을 위한 자리다.

경로 변수와 쿼리 읽기:

```tsx
// pages/post/PostPage.tsx
const { postId } = useParams()                  // /15 → postId = "15" (문자열)

// pages/auth/LoginPage.tsx
const [params] = useSearchParams()              // ?redirect=...
params.get('redirect')                          // 디코딩된 값. 없으면 null
```

`useSearchParams`는 `[현재 값, 바꾸는 함수]` 배열을 돌려주고, 여기서는 첫 번째만 꺼낸다(배열 구조 분해).

### 5.3 api(): 한 줄씩

`frontend/src/api/client.ts`

**오류 타입**

```ts
export interface ErrorBody {
  code: string
  message: string
  fieldErrors?: FieldError[]
  detail?: Record<string, unknown>
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly fieldErrors: FieldError[]
  readonly detail?: Record<string, unknown>

  constructor(status: number, body: ErrorBody) {
    super(body.message)                       // Error.message = 화면에 띄울 문장
    this.status = status
    this.code = body.code                     // 'NICKNAME_TAKEN' 같은 코드로 분기
    this.fieldErrors = body.fieldErrors ?? [] // 없으면 빈 배열 → 화면에서 항상 배열로 다룸
    this.detail = body.detail                 // MEMBER_SUSPENDED의 사유·기한 등
  }
}
```

`ErrorBody`는 서버 `ErrorResponse`(COM-02, [07](./07-spring-mvc-exception-handling.md))와 같은 모양이다. 화면은 `catch (e) { if (e instanceof ApiError && e.code === 'NICKNAME_TAKEN') ... }`처럼 코드로 분기하고, 입력 칸 옆에는 `fieldErrors`의 `reason`을 띄운다.

**요청 옵션**

```ts
type Method = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

export interface RequestOptions {
  method?: Method
  body?: unknown
  idempotencyKey?: string
  allowAnonymous?: boolean
}
```

`method`를 문자열이 아니라 유니온으로 둬서 `'GTE'` 같은 오타가 빌드에서 걸린다.

**본체**

```ts
export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? 'GET'
  const headers: Record<string, string> = { Accept: 'application/json' }   // (1)
  if (method !== 'GET') {
    headers['X-Requested-With'] = 'XMLHttpRequest'                          // (2)
  }
  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'                            // (3)
  }
  if (options.idempotencyKey) {
    headers['Idempotency-Key'] = options.idempotencyKey                     // (4)
  }

  const response = await fetch(path, {
    method,
    headers,
    credentials: 'same-origin',                                             // (5)
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  })

  if (response.ok) {
    // 202·204처럼 본문이 없는 성공도 있다
    const text = await response.text()
    return (text ? JSON.parse(text) : undefined) as T                       // (6)
  }

  const error = new ApiError(response.status, await readError(response))  // (7)
  if (response.status === 401 && !options.allowAnonymous) {
    redirectToLogin()                                                       // (8)
  }
  throw error
}
```

1. JSON 응답을 원한다고 알린다.
2. GET이 아니면 CSRF 대책 헤더. 서버의 `CsrfHeaderFilter`가 POST·PUT·PATCH·DELETE의 `/api/`에 이 헤더가 없으면 403 `CSRF_REJECTED`를 준다([13](./13-csrf-samesite-cors.md)).
3. 본문이 있을 때만 JSON이라고 알린다.
4. 연타 방지 대상(글 발행, 댓글·방명록 작성)이면 키를 싣는다([17](./17-idempotency-redis.md)).
5. 같은 출처라 쿠키가 실린다(위 3.3).
6. 성공. 본문을 먼저 **글자로** 읽고(`text()`), 비었으면 `undefined`, 있으면 `JSON.parse`. 스텝 3에서는 `response.status === 204`일 때만 `json()`을 건너뛰었는데, 스텝 4의 이메일 인증 요청(`202 Accepted`)과 코드 확인(`200`, 본문 없음)은 204가 아닌데도 본문이 없어 `json()`이 실패했을 것이다. 상태 코드로 맞히지 말고 **본문이 실제로 있는지**로 판단하도록 바꿨다. 테스트 `client.test.ts`의 '본문 없는 200·202도 성공이다'가 이것을 확인한다. `as T`는 "부른 쪽이 말한 타입이라고 믿겠다"는 단언이다. 실행 중에 모양을 검사하지는 않으므로, 서버와 프론트의 응답 모양을 rest-api.md로 맞춰 둔다.
7. 실패. 본문을 COM-02로 읽어 `ApiError`를 만든다.
8. 401이면 로그인 화면으로 보낸다. 그래도 `throw`는 한다. 이동하는 짧은 사이에 부른 쪽 코드가 "성공한 것처럼" 진행하지 않게 하려는 것이다.

**오류 본문 읽기**

```ts
async function readError(response: Response): Promise<ErrorBody> {
  try {
    const body = (await response.json()) as Partial<ErrorBody>
    return body.code && body.message ? (body as ErrorBody) : UNKNOWN_ERROR
  } catch {
    return UNKNOWN_ERROR
  }
}
```

- 프록시나 서버가 죽어 HTML 오류 페이지(502 등)가 오면 `json()`이 실패한다 → 일반 오류 문구로.
- JSON이어도 `code`·`message`가 없으면(우리 서버가 아닌 응답) 일반 오류로.
- `Partial<ErrorBody>`: 모든 필드를 선택적으로 만든 타입. "아직 확인 안 했으니 다 없을 수도 있다".
- `catch {`: 오류 객체를 안 쓰면 변수 없이 쓸 수 있다.

**로그인 후 복귀**

```ts
export function loginUrl(returnTo: string = window.location.href): string {
  return platformUrl(`/login?redirect=${encodeURIComponent(returnTo)}`)
}

export function redirectToLogin(returnTo?: string): void {
  window.location.assign(loginUrl(returnTo))
}
```

- 지금 주소 전체(`http://alpha.blog.test:8080/manage`)를 `redirect` 쿼리에 담아 **플랫폼** 로그인 화면으로 보낸다. 로그인은 플랫폼 주소에서 하고, 쿠키는 `.blog.test`라 블로그 주소에서도 로그인 상태가 된다([10](./10-http-cookies.md)).
- `encodeURIComponent`: 주소 안의 `:`, `/`, `?`, `&`를 `%3A` 같은 형태로 바꿔, 쿼리 값 안에 안전하게 넣는다. 안 하면 `?redirect=http://a.blog.test/x?page=2&y=1`의 `&y=1`이 로그인 주소의 다른 쿼리로 잘못 읽힌다.
- `window.location.assign`: 페이지를 그 주소로 이동한다(다른 출처라 React Router의 이동이 아니라 진짜 페이지 이동).
- **스텝 4에서 지킬 것**: 로그인 화면은 `redirect` 값을 그대로 믿으면 안 된다. 아무 주소나 허용하면 `?redirect=https://evil.example`로 피싱 사이트에 보내는 **오픈 리다이렉트** 취약점이 된다. 우리 서비스 주소(`blog.test`와 그 하위)인지 확인한 뒤 이동한다(rest-api.md 소셜 로그인 흐름에도 "우리 서비스 주소만"이 있다).

**allowAnonymous**: "로그인했나?"만 확인하고 싶은 호출(예: 화면 위 내 정보 표시)은 401이어도 로그인 화면으로 끌려가면 안 된다. 그때 `api('/api/me', { allowAnonymous: true })`로 부르고 `catch`에서 비회원으로 처리한다.

### 5.4 연타 방지 키

```ts
export function newIdempotencyKey(): string {
  return crypto.randomUUID()
}
```

`crypto.randomUUID()`는 무작위 UUID(버전 4) 문자열을 만든다. 서버는 이 형식(UUID)만 받는다.

쓰는 법(스텝 5 이후):

```ts
const key = newIdempotencyKey()              // 버튼을 누를 때 한 번
await api('/api/posts', { method: 'POST', body: draft, idempotencyKey: key })
// 실패해서 재시도할 때는 같은 key를 다시 쓴다. 새로 만들면 중복 방지가 안 된다
```

**함정: 보안 컨텍스트에서만 동작한다.** 브라우저의 `crypto.randomUUID`는 **보안 컨텍스트**(HTTPS, 또는 `localhost`·`127.0.0.1`)에서만 존재한다. 로컬 개발 주소 `http://alpha.blog.test:5173`나 `http://blog.test:8080`은 HTTPS도 localhost도 아니라서 `crypto.randomUUID`가 `undefined`이고, 부르면 `TypeError`가 난다. 운영은 HTTPS라 괜찮지만 개발 중 발행 버튼이 깨진다. 테스트(Vitest, Node 환경)에서는 Node에 `crypto.randomUUID`가 있어 통과하므로 테스트로는 드러나지 않는다. 스텝 5에서 글 발행을 붙이기 전에, 보안 컨텍스트가 아니어도 되는 `crypto.getRandomValues`로 UUID v4를 만드는 방식으로 바꿔야 한다.

### 5.5 Vitest로 테스트하기

`frontend/src/api/client.test.ts`

```ts
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const assign = vi.fn()                                   // (1) 가짜 함수

function jsonResponse(status: number, body?: unknown): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })                                                     // (2) 진짜 Response 객체를 직접 만듦
}

beforeEach(() => {
  vi.stubGlobal('window', {                              // (3) 전역 window를 가짜로
    location: { protocol: 'http:', port: '8080', href: 'http://alpha.blog.test:8080/manage', assign },
  })
})

afterEach(() => {
  vi.unstubAllGlobals()                                  // (4) 원래대로
  assign.mockReset()
})
```

1. `vi.fn()`: 불렸는지, 무슨 인자로 불렸는지 기록하는 가짜 함수(Java의 Mockito `mock`과 비슷). `window.location.assign` 대신 넣어서 실제로 페이지를 이동하지 않고 "어디로 이동하려 했나"만 확인한다.
2. `Response`는 브라우저와 Node(18 이상)에 내장된 클래스라 테스트에서 응답을 직접 만들 수 있다.
3. `vi.stubGlobal(이름, 값)`: 전역 변수를 테스트 동안만 바꾼다. 테스트는 Node 환경(`vite.config.ts`의 `test.environment: 'node'`)이라 원래 `window`가 없다.
4. 다른 테스트에 영향이 없게 되돌린다.

```ts
it('상태를 바꾸는 요청에는 CSRF 헤더와 연타 방지 키를 붙인다', async () => {
  const fetchMock = vi.fn().mockResolvedValue(jsonResponse(201, { id: 2 }))   // fetch가 201을 돌려주게
  vi.stubGlobal('fetch', fetchMock)
  const key = newIdempotencyKey()

  await api('/api/posts', { method: 'POST', body: { title: 't' }, idempotencyKey: key })

  const [, init] = fetchMock.mock.calls[0]               // 첫 호출의 두 번째 인자(옵션)
  expect(init.headers['X-Requested-With']).toBe('XMLHttpRequest')
  expect(init.headers['Idempotency-Key']).toBe(key)
})
```

- `mockResolvedValue(v)`: 부르면 `v`로 끝나는 Promise를 돌려주는 가짜 함수.
- `mock.calls[0]`: 첫 번째 호출의 인자 배열. `[, init]`은 첫 번째(경로)는 버리고 두 번째만 꺼내는 구조 분해다.

```ts
it('401이면 플랫폼 로그인 화면으로 보내고 지금 주소로 돌아오게 한다', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(401, { code: 'UNAUTHORIZED', message: '...' })))

  await expect(api('/api/me')).rejects.toBeInstanceOf(ApiError)        // 오류로 끝나야 하고
  expect(assign).toHaveBeenCalledWith(                                  // 로그인 화면으로 이동하려 했어야 함
    'http://blog.test:8080/login?redirect=' + encodeURIComponent('http://alpha.blog.test:8080/manage'))
})
```

`expect(promise).rejects`: Promise가 거부되는지 확인한다. 꼭 `await`해야 한다(안 하면 확인 전에 테스트가 끝난다).

### 5.6 빌드에서 테스트 타입 오류가 난 사건

스텝 3에서 `npm test`는 통과했는데 `npm run build`가 실패했다.

```
src/api/client.test.ts:64:12 - error TS18046: 'error' is of type 'unknown'.
```

원인:
- 처음 코드는 `const error = await api('/api/posts').catch((e) => e)`였다.
- `api('/api/posts')`처럼 타입 인자 없이 부르면 `T`를 추론할 데가 없어 `unknown`이 된다. `.catch((e) => e)`의 결과 타입은 "`T` 또는 `catch`가 돌려준 것"이라 결국 `unknown`이다.
- `unknown`인 `error`에 `error.code`를 쓰면 TypeScript가 막는다.
- **Vitest는 테스트를 실행할 때 타입 검사를 하지 않는다**(타입을 지우고 바로 실행). 그래서 `npm test`는 통과했고, 타입 검사를 하는 `tsc -b`(빌드의 첫 단계)에서야 드러났다.

고친 코드:

```ts
const error = (await api('/api/posts').catch((e: unknown) => e)) as ApiError
```

결과 전체를 `ApiError`로 단언했다. 처음 시도한 `.catch((e: unknown) => e as ApiError)`는 실패했다. `catch` 안에서만 단언해도 바깥 결과는 여전히 "`unknown`(성공 쪽) 또는 `ApiError`"라서 합치면 `unknown`이기 때문이다.

교훈: **`npm test` 통과 ≠ 빌드 통과.** 커밋 전에 `npm test && npm run build && npm run lint`를 함께 돌린다.

### 5.7 oxlint

`npm run lint`는 **oxlint**(Rust로 만든 빠른 자바스크립트·타입스크립트 린터)를 돌린다. 린터는 문법은 맞지만 실수일 가능성이 높은 코드를 찾는다.

`frontend/.oxlintrc.json`

```json
{
  "plugins": ["react", "typescript", "oxc"],
  "rules": {
    "react/rules-of-hooks": "error",
    "react/only-export-components": ["warn", { "allowConstantExport": true }]
  }
}
```

- `rules-of-hooks`: 훅을 조건문·반복문 안에서 부르면 오류.
- `only-export-components`: 컴포넌트 파일에서 컴포넌트가 아닌 것을 함께 내보내면 HMR이 페이지 전체를 새로고침하게 되어 경고한다.

## 6. 자주 하는 실수와 함정

1. **fetch가 404·500에서 예외를 낼 거라 기대하기**: 내지 않는다. `response.ok`를 본다(`api()`가 대신 함).
2. **본문 없는 응답에 `json()` 부르기**: 오류. 204만 특별 취급하면 202·200처럼 본문 없이 끝나는 다른 성공에서 깨진다. (스텝 4에서 해결: `api()`가 `text()`로 읽고 빈 문자열이면 `undefined`, 5.3 (6). 스텝 3 노트의 "남은 문제" 202 항목이 이것이다.)
3. **`redirect` 값을 그대로 이동**: 오픈 리다이렉트. 우리 도메인인지 확인한다. (스텝 4의 로그인 화면은 `safeRedirect()`로 확인한다, [21](./21-signup-login.md).)
4. **`encodeURIComponent` 빼먹기**: 돌아올 주소의 쿼리가 깨진다.
5. **재시도마다 새 연타 방지 키**: 중복 방지가 안 된다.
6. **`crypto.randomUUID`를 http 개발 주소에서 부르기**: `TypeError`(5.4).
7. **`as T`를 검사로 착각**: 단언은 실행 중 아무것도 확인하지 않는다.
8. **훅을 조건문 안에서 부르기**: React가 상태를 엉뚱한 컴포넌트에 연결한다. lint가 막는다.
9. **`npm test`만 돌리고 커밋**: 타입 오류는 빌드에서만 잡힌다.
10. **`credentials: 'include'`로 바꾸기**: 필요 없고, 다른 출처 요청까지 쿠키를 싣게 된다.
11. **`vi.stubGlobal` 후 되돌리지 않기**: 다음 테스트가 가짜 `fetch`를 그대로 쓴다.

## 7. 직접 해 보기

**실습 1. 테스트·빌드·린트**

```bash
cd frontend
npm test          # 스텝 4 기준 17개 통과(client, host, pageGroup)
npm run build     # tsc -b && vite build
npm run lint
```

**실습 2. 빌드에서만 잡히는 타입 오류 재현**

1. `client.test.ts`의 `const error = (await api('/api/posts').catch((e: unknown) => e)) as ApiError`를 `const error = await api('/api/posts').catch((e) => e)`로 바꾼다.
2. `npm test` → 통과. `npm run build` → `TS18046` 오류.
3. 되돌린다.

**실습 3. CSRF 헤더 빼 보기**

1. `client.ts`에서 `headers['X-Requested-With'] = 'XMLHttpRequest'` 줄을 주석 처리한다.
2. `npm test` → "상태를 바꾸는 요청에는 CSRF 헤더…" 테스트가 실패한다. 실제 서버라면 403 `CSRF_REJECTED`가 났을 것이다. 되돌린다.

**실습 4. 보안 컨텍스트 확인** (hosts에 `blog.test`를 등록한 뒤)

```bash
npm run dev
```

브라우저에서 `http://localhost:5173`과 `http://blog.test:5173`을 각각 열고 개발자 도구 콘솔에 친다.

```js
window.isSecureContext     // localhost: true, blog.test: false
typeof crypto.randomUUID   // localhost: 'function', blog.test: 'undefined'
```

**실습 5. 라우트 확인**

`npm run dev` 후 `http://localhost:5173/login`, `/signup`, `/blogs/new`(비회원이면 로그인 화면으로 간다)를 차례로 열어 본다. `http://localhost:5173/없는주소`는 404 화면이다. (스텝 3에서는 로그인 자리 화면이 `redirect` 값을 그대로 보여 줬는데, 스텝 4의 진짜 로그인 화면은 보여 주지 않고 로그인 뒤 그 주소로 이동한다.)

**실습 6. 경로 순위**

`routes.tsx`의 `BlogRoutes`에서 `/manage/*`와 `/:postId` 줄의 순서를 바꿔도 `/manage`가 여전히 관리 화면인지 확인한다(hosts 등록 후 `http://alpha.blog.test:5173/manage`). 순서가 아니라 구체적인 정도로 고른다는 것을 확인하고 되돌린다.

## 8. 확인 문제

1. `fetch('/api/x')`가 404 응답을 받으면 Promise는 성공인가 실패인가? 이 프로젝트는 어떻게 처리하나?
<details><summary>답</summary>성공(정상 이행)이다. fetch는 네트워크 오류일 때만 거부된다. <code>api()</code>가 <code>response.ok</code>를 확인해 실패면 <code>ApiError</code>를 던진다.</details>

2. `api()`가 GET이 아닐 때만 `X-Requested-With`를 붙이는 이유는?
<details><summary>답</summary>서버의 CSRF 대책이 상태를 바꾸는 요청(POST·PUT·PATCH·DELETE)에만 이 헤더를 요구하기 때문이다. GET은 상태를 바꾸지 않아 검사하지 않는다.</details>

3. 401에서 `redirectToLogin()`을 부른 뒤에도 `throw`하는 이유는?
<details><summary>답</summary>페이지가 이동하는 짧은 사이에 부른 쪽 코드가 성공으로 착각하고 다음 처리를 이어 가지 않게 하려는 것이다.</details>

4. `credentials: 'same-origin'`으로도 로그인 쿠키가 실리는 이유는?
<details><summary>답</summary>API를 항상 같은 출처(같은 주소의 <code>/api/...</code>)로 부르기 때문이다. 개발 중에는 Vite가 같은 주소로 받아 8080으로 넘기고, 운영은 같은 서버다.</details>

5. `type Host = { kind: 'platform' } | { kind: 'blog'; address: string }`에서 `host.address`를 쓰려면?
<details><summary>답</summary><code>host.kind === 'blog'</code>로 먼저 확인해야 한다. 그 분기 안에서 TypeScript가 타입을 좁혀 <code>address</code>를 허용한다.</details>

6. `npm test`는 통과했는데 `npm run build`가 실패할 수 있는 이유는?
<details><summary>답</summary>Vitest는 실행할 때 타입 검사를 하지 않고, 빌드의 <code>tsc -b</code>가 타입 검사를 하기 때문이다.</details>

7. React Router를 8이 아니라 7로 고른 이유는?
<details><summary>답</summary>8은 React 19.2.7 이상을 요구(peerDependencies)하는데, 이 프로젝트는 plan.md대로 React 18을 쓰기 때문이다.</details>

8. 로그인 화면이 `redirect` 값을 확인 없이 이동하면 어떤 취약점이 되나?
<details><summary>답</summary>오픈 리다이렉트다. 공격자가 <code>?redirect=https://evil.example</code> 링크를 퍼뜨리면, 진짜 로그인 뒤 피싱 사이트로 보내져 사용자가 속기 쉽다.</details>

9. (스텝 4) `api()`가 성공 응답을 `response.status === 204`로 나누지 않고 `text()`로 읽어 빈 문자열인지 보는 이유는?
<details><summary>답</summary>본문이 없는 성공은 204만이 아니다. 이메일 인증 요청은 202, 코드 확인은 본문 없는 200이다. 상태 코드로 나누면 이런 응답에서 <code>json()</code>이 실패한다. 본문이 실제로 있는지로 판단하면 어떤 2xx든 처리된다.</details>

10. (스텝 4) `BlogRoutes`가 더는 `address` prop을 받지 않는다. 블로그 화면은 어느 블로그인지 어떻게 아나?
<details><summary>답</summary>화면이 <code>/api/blog</code>, <code>/api/posts</code>, <code>/api/blog/sidebar</code>를 부르면 서버가 요청 Host(<code>alpha.blog.test</code>)로 블로그를 찾아 준다(<code>@CurrentBlog</code>). 화면은 주소를 들고 다닐 필요가 없다.</details>

## 9. 더 읽을거리

- React 공식 문서: https://react.dev/learn (Describing the UI, Rules of Hooks)
- React Router 문서: https://reactrouter.com (v7 "Declarative mode": `BrowserRouter`, `Routes`, `Route`, 경로 순위)
- MDN Web Docs: Fetch API, `Response`, `Request.credentials`, `encodeURIComponent`, `Crypto.randomUUID()`, Secure contexts
- TypeScript Handbook: https://www.typescriptlang.org/docs/handbook/ (Narrowing, Generics, `unknown`)
- TypeScript tsconfig 레퍼런스: `erasableSyntaxOnly`, `verbatimModuleSyntax`
- Vitest 문서: https://vitest.dev (Mocking, `vi.fn`, `vi.stubGlobal`)
- Vite 문서: "Env Variables and Modes"
- OWASP, "Unvalidated Redirects and Forwards"
