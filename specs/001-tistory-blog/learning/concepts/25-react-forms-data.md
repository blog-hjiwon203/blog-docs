# 25. React 폼과 데이터 불러오기

> 관련 스텝: [스텝 4](../step-04.md) (T026), [스텝 5](../step-05.md) (T035 글쓰기·수정, 카테고리 관리), [스텝 6](../step-06.md) (T045 홈·글 상세·댓글, T051 오류 화면·관리자 영역), [스텝 7](../step-07.md) (T048 공감·검색, T037 사진 올리기) · 관련 개념: [30-image-upload](./30-image-upload.md), [31-tags-many-to-many](./31-tags-many-to-many.md), [32-search-like](./32-search-like.md), [28-thymeleaf-to-react](./28-thymeleaf-to-react.md), [29-comments-design](./29-comments-design.md), [19-react-router-api-client](./19-react-router-api-client.md), [14-xss-sanitize-csp](./14-xss-sanitize-csp.md), [16-authorization-visibility](./16-authorization-visibility.md), [18-spa-server-routing](./18-spa-server-routing.md), [15-subdomain-host-routing](./15-subdomain-host-routing.md)

## 1. 이 문서로 배우는 것

- 상태(`useState`)와 다시 그리기(re-render)의 관계
- 제어 컴포넌트: `value` + `onChange`로 입력 칸을 React 상태와 묶기
- `<form onSubmit>`, `event.preventDefault()`, `noValidate`
- 비동기 제출과 `submitting` 상태로 버튼 막기
- 서버 오류(COM-02 본문)를 입력 칸별로 보여 주기, 입력값을 지우지 않는 이유
- 단계가 있는 폼(코드 받기 → 확인 → 가입)과 "앞 단계가 바뀌면 뒤 단계 초기화"
- `onBlur`로 칸을 벗어날 때 중복 확인하기
- `useEffect`로 데이터 불러오기, 정리 함수(cleanup)와 `active` 플래그
- 커스텀 훅(`useMe`, `useBlog`)과 판별 유니온(discriminated union) 상태
- oxlint `set-state-in-effect` 경고가 뜻하는 것
- React Router: 중첩 `Routes`, `NavLink`, `useParams`, `useSearchParams`, `navigate`와 `window.location.assign`의 차이
- 화면의 권한 검사는 안내용이라는 원칙, React의 자동 이스케이프
- 페이지 번호 묶음 계산(`pageGroup`)과 Vitest, macOS 파일 이름 대소문자 문제
- (스텝 6) 댓글 목록·더보기·쓰기·지우기, `useRef`로 연타를 즉시 막기, 상태 갱신 함수 안에서 부모 콜백을 부르지 않기
- (스텝 6) 판별 유니온으로 화면 상태 나누기(불러오는 중·성공·404·구독 안내·오류)와 오류 화면
- (스텝 7) 낙관적 갱신(누르자마자 화면부터 바꾸고 서버 값으로 맞추기)과 실패 시 되돌리기 — 공감 버튼
- (스텝 7) `key`의 진짜 역할: 같은 부모 아래 형제의 `key`가 겹치면 생긴 "공감 버튼 두 개" 버그
- (스텝 7) 검색어를 주소(`?q=&page=`)에 두기: `useSearchParams`로 공유·새로고침·뒤로 가기에 강한 화면
- (스텝 7) 파일 올리기: `FormData`와 `fetch`, `Content-Type`을 직접 쓰지 않는 이유

**먼저 알면 좋은 것**: [19](./19-react-router-api-client.md)의 컴포넌트·JSX·props, `api()` 래퍼와 `ApiError`, `async`/`await`.

## 2. 왜 필요한가

스텝 3까지 화면은 "스텝 4에서 만듭니다"라는 글자뿐이었다. 스텝 4에서 사용자가 **입력하고, 서버에 보내고, 결과를 보는** 화면이 처음 생겼다.

- 가입: 이메일 → 인증 코드 받기 → 코드 확인 → 비밀번호·닉네임 → 가입. 단계마다 서버를 부르고, 실패하면 **어느 칸이 왜 틀렸는지** 보여 줘야 한다(spec US1 수용 시나리오 2: "어느 항목이 왜 틀렸는지 알리고 입력은 그대로 남는다").
- 로그인: 실패 문구, 정지 회원 안내, 로그인 뒤 원래 보던 블로그 주소로 돌아가기.
- 블로그 개설: 주소를 입력하면 쓸 수 있는지 바로 알려 주기.
- 블로그 메인: 화면을 열자마자 블로그 정보·사이드바·글 목록을 **불러와서** 그리기. 페이지·카테고리를 바꾸면 다시 불러오기.

이걸 하려면 "입력값을 어디에 두는가", "서버 응답이 오면 화면을 어떻게 바꾸는가", "화면을 열 때 데이터를 언제 불러오는가"를 알아야 한다.

## 3. 기본 개념

### 3.1 상태와 다시 그리기

React 컴포넌트는 **함수**다. 함수가 돌려준 JSX가 화면이 된다. 화면을 바꾸려면 **상태(state)**를 바꾼다.

```tsx
const [email, setEmail] = useState('')
```

- `useState('')`: 초깃값 `''`인 상태 하나를 만든다. `[현재 값, 바꾸는 함수]`를 돌려준다.
- `setEmail('a@b.com')`을 부르면 React가 **컴포넌트 함수를 다시 실행**(re-render)하고, 이번에는 `email`이 `'a@b.com'`이다. 새 JSX와 이전 JSX를 비교해 바뀐 부분만 실제 화면(DOM)에 반영한다.
- 일반 변수(`let email = ''`)는 함수가 다시 실행될 때마다 처음 값으로 돌아가고, 바꿔도 다시 그려지지 않는다. 그래서 화면에 영향을 주는 값은 상태로 둔다.
- `setX`는 그 자리에서 값을 바꾸지 않는다. **다음 그리기**에서 새 값이 보인다. 이전 값을 바탕으로 바꿀 때는 함수형으로 쓴다: `setErrors((previous) => ({ ...previous, email: '...' }))`.

### 3.2 제어 컴포넌트(controlled component)

입력 칸의 값을 **React 상태가 쥐고** 있는 방식이다.

```tsx
<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} />
```

1. 사용자가 글자를 친다 → `onChange` → `setEmail(새 값)`
2. 다시 그리기 → `value={email}`로 칸에 새 값이 보인다

값이 항상 상태에 있으니, 제출할 때 칸을 뒤질 필요 없이 `email`을 쓰면 된다. 다른 상태에 따라 칸을 막거나(`disabled={verified}`) 비울 수도 있다. `value`만 주고 `onChange`를 빼면 칸이 **입력되지 않는다**(React가 값을 계속 되돌리므로).

### 3.3 form, onSubmit, preventDefault, noValidate

```tsx
<form onSubmit={submit} noValidate> ... <button type="submit">가입하기</button> </form>
```

- 버튼을 누르거나 칸에서 Enter를 치면 `submit` 이벤트가 난다.
- 브라우저 기본 동작은 **폼 내용을 들고 페이지를 새로 여는 것**이다. SPA에서는 원하지 않으므로 `event.preventDefault()`로 막고 직접 `fetch`한다.
- `noValidate`: `type="email"`, `required` 같은 **브라우저 기본 검사 말풍선**을 끈다. 오류 문구를 서버·화면 규칙에 맞춰 칸 아래에 직접 보여 주려고 끈다. 로그인 화면은 일부러 켜 두어서(`required`) 빈 칸이면 브라우저가 막는다.
- `type="button"`인 버튼(코드 받기, 확인)은 폼을 제출하지 않는다. 폼 안의 `<button>`은 기본이 `type="submit"`이라 **명시하지 않으면 누를 때마다 가입이 제출된다**.

### 3.4 비동기 제출과 버튼 막기

서버 응답은 시간이 걸린다. 그동안 버튼을 또 누르면 요청이 두 번 간다. `submitting` 상태로 막는다.

```
누름 → setSubmitting(true) → 버튼 disabled → await api(...) → finally setSubmitting(false)
```

이건 **더블 클릭만** 막는다. 재전송까지 막는 것은 서버의 일이다([17](./17-idempotency-redis.md)).

### 3.5 useEffect: 그린 뒤에 할 일

화면을 열 때 서버에서 데이터를 불러오는 것은 "그리기" 자체가 아니라 **그린 뒤의 부수 효과(side effect)**다.

```tsx
useEffect(() => {
  // 그린 뒤 실행
  return () => { /* 정리: 다음 실행 전이나 화면에서 사라질 때 */ }
}, [의존값들])
```

- 두 번째 인자(의존 배열)의 값이 **바뀔 때마다** 다시 실행된다. `[]`면 처음 한 번.
- 정리 함수는 다음 실행 **직전**과 컴포넌트가 사라질 때 불린다.
- 개발 모드의 `<StrictMode>`(main.tsx)는 문제를 찾으려고 효과를 **일부러 한 번 더** 실행한다(설치 → 정리 → 다시 설치). 그래서 개발 중에는 `/api/me` 요청이 두 번 보일 수 있다. 정리 함수를 제대로 쓰면 결과는 같다.

### 3.6 늦게 온 응답 문제

1페이지를 보다 2페이지를 눌렀다. 요청이 둘 나갔는데 **1페이지 응답이 늦게** 도착하면, 화면은 2페이지 버튼이 눌린 채 1페이지 글을 보여 준다. 해결은 "이미 지난 효과의 응답은 버린다".

```tsx
useEffect(() => {
  let active = true
  api(...).then((result) => { if (active) setPosts(result) })
  return () => { active = false }      // 다음 효과가 시작되면 이전 것은 비활성
}, [page])
```

### 3.7 커스텀 훅과 판별 유니온

이름이 `use`로 시작하고 안에서 다른 훅을 쓰는 함수가 **커스텀 훅**이다. 여러 화면이 같은 "상태 + 효과"를 쓸 때 묶는다. `useMe`는 머리글이 있는 모든 화면이 쓴다.

상태 모양은 **판별 유니온**으로 했다.

```ts
type MeState = { status: 'loading' } | { status: 'anonymous' } | { status: 'member'; me: Me }
```

`status`(판별 필드)를 보면 나머지 모양이 정해진다. `if (me.status === 'member')` 안에서만 TypeScript가 `me.me`를 쓸 수 있게 해 준다. `me: Me | null`과 `loading: boolean`을 따로 두면 "로딩 중인데 me가 있다" 같은 말이 안 되는 조합이 생길 수 있는데, 유니온은 그런 상태를 **만들 수 없게** 한다.

## 4. 동작 원리

### 4.1 블로그 메인을 열 때

```
alpha.blog.test:5173/category/3?page=2
   │ App → parseHost → BlogRoutes → "/category/:categoryId" → BlogMainPage
   ▼
첫 그리기: useMe → loading, useBlog → loading  → 화면은 null(아무것도 안 그림)
   │
   ▼ 그린 뒤 효과들이 동시에 출발
 ① GET /api/me              (useMe)       → member 또는 anonymous
 ② GET /api/blog            (useBlog)     → ok / notFound
 ③ GET /api/blog/sidebar                   → 사이드바 모듈
 ④ GET /api/posts?page=2&categoryId=3      → 글 목록 (의존: categoryId, page)
   │ 응답이 올 때마다 set... → 다시 그리기
   ▼
blog ok → 머리글·프로필·목록·사이드바가 차례로 채워짐
404 → <NotFoundPage />

사용자가 "3" 페이지 링크를 누름 → URL만 ?page=3 으로 바뀜(페이지 새로 열지 않음)
   → page 값이 바뀜 → ④ 효과의 정리(active=false) → ④ 다시 실행
```

### 4.2 가입 폼의 단계

```
email 입력 ──[코드 받기]──▶ POST /email-verifications ─202─▶ codeSent=true
                                                    ─409/429─▶ errors.email
code 입력  ──[확인]──────▶ POST /email-verifications/verify ─200─▶ verified=true (코드 칸 잠금)
                                                           ─400─▶ errors.code
email 다시 바꿈 ─────────▶ codeSent=false, verified=false   (처음부터)
nickname 칸 벗어남(blur) ─▶ GET /nickname-availability ─▶ nicknameOk / errors.nickname
[가입하기] (verified일 때만 켜짐) ─▶ POST /signup ─201─▶ navigate('/blogs/new')
                                              ─4xx─▶ 칸별 오류, 입력값은 그대로
```

## 5. 이 프로젝트에서는

### 5.1 서버 오류를 칸별 문장으로: api/errors.ts

`frontend/src/api/errors.ts`

```ts
/** 입력 칸 아래에 띄울 오류. 칸 이름(field)별 문장이다. */
export type FieldMessages = Record<string, string>

/** 400 VALIDATION_FAILED 등의 fieldErrors를 칸별 문장으로. */
export function fieldMessages(error: unknown): FieldMessages {
  if (!(error instanceof ApiError)) {
    return {}
  }
  return Object.fromEntries(error.fieldErrors.map((fieldError) => [fieldError.field, fieldError.reason]))
}
```

- 서버 오류 본문은 `{ code, message, fieldErrors: [{ field, reason }] }`이다(COM-02, [07](./07-spring-mvc-exception-handling.md)). `api()`가 이걸 `ApiError`로 바꿔 던진다([19](./19-react-router-api-client.md)).
- `Object.fromEntries([['password', '비밀번호는 ...']])` → `{ password: '비밀번호는 ...' }`. 화면에서는 `errors.password`로 그 칸 아래에 띄운다.
- `error: unknown`: `catch`로 잡힌 값은 무엇이든 될 수 있어서(네트워크 오류는 `TypeError`) `instanceof`로 확인한 뒤에만 `fieldErrors`를 읽는다.

```ts
/** 429의 남은 초 */
export function retryAfterSeconds(error: unknown): number | null {
  if (error instanceof ApiError && typeof error.detail?.retryAfterSeconds === 'number') {
    return error.detail.retryAfterSeconds
  }
  return null
}
```

`detail`은 오류마다 모양이 달라서 `typeof`로 숫자인지 확인한다. `?.`는 `detail`이 없으면 에러 대신 `undefined`를 준다.

### 5.2 가입 화면: SignupPage

`frontend/src/pages/auth/SignupPage.tsx`

**상태**

```tsx
const [email, setEmail] = useState('')
const [code, setCode] = useState('')
const [password, setPassword] = useState('')
const [nickname, setNickname] = useState('')
const [codeSent, setCodeSent] = useState(false)
const [verified, setVerified] = useState(false)
const [nicknameOk, setNicknameOk] = useState<boolean | null>(null)
const [errors, setErrors] = useState<FieldMessages>({})
const [submitting, setSubmitting] = useState(false)
```

- 입력값 4개, 단계 표시 2개(`codeSent`, `verified`), 닉네임 확인 결과(`null` = 아직 모름), 칸별 오류, 제출 중.

**앞 단계가 바뀌면 뒤 단계 초기화**

```tsx
function changeEmail(value: string) {
  // 이메일을 바꾸면 인증을 다시 받아야 한다
  setEmail(value)
  setCodeSent(false)
  setVerified(false)
}
```

`a@x.com`으로 인증받고 이메일을 `b@x.com`으로 바꾼 뒤 가입하면? 서버가 코드를 다시 확인하므로 어차피 400이지만, 화면이 "이메일이 확인되었습니다"를 계속 보여 주면 사용자가 헷갈린다. 화면 상태도 서버 규칙과 맞춘다.

**제출**

```tsx
async function submit(event: FormEvent) {
  event.preventDefault()
  if (!PASSWORD_RULE.test(password)) {
    setError('password', '비밀번호는 8자 이상, 영문과 숫자를 함께 써 주세요.')
    return
  }
  setSubmitting(true)
  setErrors({})
  try {
    await api<Me>('/api/auth/signup', {
      method: 'POST',
      body: { email: email.trim(), code, password, nickname: nickname.trim() },
    })
    navigate('/blogs/new')
  } catch (error) {
    setErrors(signupErrors(error))
    if (error instanceof ApiError && (error.code === 'INVALID_VERIFICATION_CODE' || isExpired(error))) {
      setVerified(false)
    }
  } finally {
    setSubmitting(false)
  }
}
```

- `PASSWORD_RULE`(`/^(?=.*[A-Za-z])(?=.*\d).{8,}$/`)로 화면에서 먼저 걸러 서버 왕복을 줄인다. **서버도 같은 규칙을 다시 본다**(`PasswordRule`). 화면 검사는 편의, 서버 검사가 진짜다. 72바이트 제한은 서버에만 있다.
- `setErrors({})`: 새로 제출할 때 이전 오류를 지운다.
- 실패해도 `setEmail('')` 같은 것을 **하지 않는다**. 입력값이 상태에 그대로 있으니 칸에도 그대로 남는다. 오타 하나 때문에 다 다시 쓰게 하지 않는다(수용 시나리오 2).
- 코드가 틀렸거나 만료면 `verified`를 풀어 다시 확인하게 한다.
- `finally`: 성공·실패와 상관없이 버튼을 다시 켠다.

**오류 코드 → 칸**

```tsx
function signupErrors(error: unknown): FieldMessages {
  if (!(error instanceof ApiError)) {
    return { form: errorMessage(error) }
  }
  switch (error.code) {
    case 'EMAIL_TAKEN':
      return { email: emailMessage(error) }
    case 'NICKNAME_TAKEN':
      return { nickname: error.message }
    case 'INVALID_VERIFICATION_CODE':
    case 'VERIFICATION_EXPIRED':
      return { code: codeMessage(error) }
    case 'VALIDATION_FAILED':
      return fieldMessages(error)
    default:
      return { form: error.message }
  }
}
```

- 409 `EMAIL_TAKEN`처럼 `fieldErrors`가 없는 오류도 코드를 보고 **해당 칸**에 붙인다. 어느 칸 문제인지 모르는 것은 `form`(버튼 위)에 띄운다.
- `BlogCreatePage`의 `createErrors`도 같은 모양이다(`BLOG_ADDRESS_INVALID`, `BLOG_ADDRESS_TAKEN` → `address`).

**칸 하나**

```tsx
<div className="field">
  <label className="label" htmlFor="code">인증 코드</label>
  <div className="row nowrap">
    <input id="code" type="text" inputMode="numeric" maxLength={6} value={code} disabled={verified}
           onChange={(event) => setCode(event.target.value)} />
    <button className="btn" type="button" onClick={verifyCode} disabled={!codeSent || verified || !code}>
      확인
    </button>
  </div>
  {verified && <p className="ok">이메일이 확인되었습니다.</p>}
  {errors.code && <p className="err">{errors.code}</p>}
</div>
```

- `htmlFor="code"` ↔ `id="code"`: 라벨을 누르면 칸에 커서가 간다(JSX에서는 `for` 대신 `htmlFor`). 화면 읽기 프로그램도 칸 이름을 읽는다.
- `inputMode="numeric"`: 휴대폰에서 숫자 키패드를 띄운다.
- `{조건 && <p>...</p>}`: 조건이 참일 때만 그린다.
- `disabled={!codeSent || verified || !code}`: 코드를 받기 전, 이미 확인한 뒤, 빈 칸이면 확인 버튼을 끈다.

**onBlur로 중복 확인**

```tsx
<input id="nickname" type="text" maxLength={20} value={nickname}
       onChange={(event) => { setNickname(event.target.value); setNicknameOk(null) }}
       onBlur={checkNickname} />
```

- `onBlur`: 칸에서 **포커스가 빠질 때**. 글자마다(`onChange`) 서버를 부르면 요청이 너무 많다.
- 글자를 바꾸면 `setNicknameOk(null)`로 이전 확인 결과를 지운다. "쓸 수 있는 닉네임입니다"가 바뀐 닉네임에 남아 있으면 안 된다.
- 블로그 개설의 주소 칸(`BlogCreatePage`)도 같은 방식으로 `GET /api/blogs/address-availability`를 부르고 `reason`(`INVALID`·`RESERVED`·`TAKEN`)에 따라 문구를 고른다.

### 5.3 로그인 뒤 돌아가기: navigate와 window.location.assign

`frontend/src/pages/auth/LoginPage.tsx`

```tsx
const redirect = safeRedirect(params.get('redirect'))
if (redirect) {
  // 블로그 주소는 다른 호스트라 페이지를 새로 연다. 쿠키가 .{플랫폼}이라 거기서도 로그인 상태다
  window.location.assign(redirect)
} else {
  navigate('/')
}
```

| | `navigate('/path')` (React Router) | `window.location.assign(url)` |
| --- | --- | --- |
| 하는 일 | 주소창만 바꾸고(History API) React가 다른 화면을 그림 | 브라우저가 그 주소를 **새로 연다** |
| 갈 수 있는 곳 | **같은 호스트** 안의 경로 | 어디든 |
| 페이지 상태 | 유지(JS 메모리 그대로) | 처음부터 |

`blog.test`에서 `alpha.blog.test`로 가는 것은 **다른 호스트(출처)**라 History API로 갈 수 없다. 그래서 블로그 개설 후(`window.location.assign(blogUrl(blog.address, '/manage'))`), 로그인 후 블로그로 돌아갈 때, 로그아웃 후 플랫폼 홈으로 갈 때는 `window.location.assign`을 쓴다. 같은 플랫폼 안(가입 → `/blogs/new`)은 `navigate`.

`safeRedirect`는 `redirect` 값이 **우리 서비스 주소일 때만** 돌려준다(`frontend/src/app/host.ts`). 아무 주소나 따라가면 `blog.test/login?redirect=https://evil.com`이라는 링크로 우리 로그인 화면을 거쳐 가짜 사이트로 보내는 **열린 리다이렉트(open redirect)**가 된다.

```ts
const host = url.hostname.toLowerCase()
const ours = host === platform || host.endsWith(`.${platform}`)
return (url.protocol === 'http:' || url.protocol === 'https:') && ours ? url.href : null
```

`endsWith('.blog.test')`처럼 **점을 붙여** 비교하는 이유: `evilblog.test`는 `blog.test`로 끝나지만 우리 주소가 아니다. `javascript:` 같은 프로토콜도 막는다. 테스트는 `host.test.ts`의 `safeRedirect`.

### 5.4 커스텀 훅: useMe, useBlog

`frontend/src/app/useMe.ts`

```ts
export type MeState = { status: 'loading' } | { status: 'anonymous' } | { status: 'member'; me: Me }

export function useMe(): MeState {
  const [state, setState] = useState<MeState>({ status: 'loading' })
  useEffect(() => {
    let active = true
    api<Me>('/api/me', { allowAnonymous: true })
      .then((me) => active && setState({ status: 'member', me }))
      .catch(() => active && setState({ status: 'anonymous' }))
    return () => {
      active = false
    }
  }, [])
  return state
}
```

- 로그인 쿠키는 HttpOnly라 자바스크립트가 읽을 수 없다([10](./10-http-cookies.md)). 그래서 "로그인했나"를 서버(`GET /api/me`)에 묻는다.
- `allowAnonymous: true`: 401이어도 로그인 화면으로 보내지 않는다. 비회원이 홈을 보는 건 정상이니까.
- `active && setState(...)`: 화면이 사라진 뒤 도착한 응답은 버린다.

`frontend/src/app/useBlog.ts`는 `GET /api/blog`를 같은 방식으로 부르고, 404면 `notFound`, 다른 오류면 `error`로 나눈다. 두 번째 반환값 `(blog) => setState({ status: 'ok', blog })`는 블로그 설정에서 저장한 뒤 머리글의 블로그 이름을 바로 바꾸는 데 쓴다(`BlogSettingsPage`의 `onSaved`).

화면 쪽:

```tsx
{me.status === 'anonymous' && <a className="btn" href={loginUrl()}>로그인</a>}
{me.status === 'member' && (
  <div className="row">
    {blog.viewer.isOwner && <Link className="btn" to="/manage">관리</Link>}
    <span className="small">{me.me.nickname}</span>
    <LogoutButton />
  </div>
)}
```

(`frontend/src/components/BlogHeader.tsx`) `loading`일 때는 둘 다 그리지 않아 "로그인" 버튼이 잠깐 깜빡이지 않는다.

### 5.5 글 목록 불러오기와 set-state-in-effect

`frontend/src/pages/blog/BlogMainPage.tsx`

```tsx
useEffect(() => {
  let active = true
  const query = new URLSearchParams({ page: String(page) })
  if (categoryId !== undefined) {
    query.set('categoryId', categoryId)
  }
  api<PageResponse<PostSummary>>(`/api/posts?${query}`, { allowAnonymous: true })
    .then((result) => {
      if (active) {
        setPosts(result)
        setError(null)
        setPostsNotFound(false)
      }
    })
    .catch((caught: unknown) => {
      if (!active) {
        return
      }
      setPosts(null)
      if (caught instanceof ApiError && caught.status === 404) {
        setPostsNotFound(true)
      } else {
        setError(errorMessage(caught))
      }
    })
  return () => {
    active = false
  }
}, [categoryId, page])
```

- 의존 배열 `[categoryId, page]`: 카테고리나 페이지가 바뀌면 다시 불러온다.
- `URLSearchParams`: `page=2&categoryId=3`처럼 쿼리를 안전하게 만든다(특수 문자 인코딩).
- 다른 블로그의 카테고리 번호면 서버가 404를 주고, 화면은 404 화면을 그린다.

처음 짠 코드는 효과 맨 앞에서 `setError(null); setPostsNotFound(false)`를 **바로** 불렀다. oxlint가 경고했다.

```
warning react(set-state-in-effect): Calling setState synchronously within an effect can trigger cascading renders
```

효과는 그린 **뒤**에 실행되는데, 그 안에서 바로 상태를 바꾸면 "그림 → 효과 → 상태 변경 → 또 그림"이 한 번 더 생긴다. 효과는 외부(서버)와 맞추는 용도이고, 상태 변경은 **외부에서 결과가 왔을 때** 하라는 뜻이다. 그래서 초기화를 응답이 왔을 때(`.then` 안)로 옮겼다. 응답 콜백은 비동기라 경고 대상이 아니다.

### 5.6 React Router: 중첩 Routes, NavLink, useParams, useSearchParams

`frontend/src/app/routes.tsx`

```tsx
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

- `/category/:categoryId`: `:`로 시작하는 부분은 변수다. 화면에서 `useParams()`로 꺼낸다(`const { categoryId } = useParams()`, 값은 문자열 `'3'`).
- `/manage/*`: `/manage`로 시작하는 모든 주소를 `ManagePage`에 맡긴다. 나머지 경로는 `ManagePage` 안의 `Routes`가 고른다.

`frontend/src/pages/manage/ManagePage.tsx`

```tsx
<nav className="manage-nav" aria-label="관리 메뉴">
  <div className="sec">블로그 관리</div>
  <NavLink to="/manage" end>관리 홈</NavLink>
  <div className="sec">설정</div>
  <NavLink to="/manage/settings">블로그 설정</NavLink>
</nav>
<Routes>
  <Route index element={<ManageHomePage blog={blog} />} />
  <Route path="settings" element={<BlogSettingsPage blog={blog} onSaved={setBlog} />} />
  <Route path="*" element={<main className="page"><p className="muted">준비 중인 화면입니다.</p></main>} />
</Routes>
```

- 안쪽 `Routes`의 경로는 **바깥 `/manage/` 기준 상대 경로**다. `index`는 `/manage` 자체, `settings`는 `/manage/settings`.
- `NavLink`는 지금 주소와 맞으면 `active` 클래스를 붙인다. CSS의 `.manage-nav a.active`가 초록 배경을 칠한다.
- `end`: `/manage` 링크가 `/manage/settings`에서도 "맞음"으로 보이지 않게, **정확히 같을 때만** active로.
- `*`: 아직 없는 관리 화면은 "준비 중"을 보여 준다. 스텝 5에서 글쓰기·수정·카테고리가 이 안에 더해졌다(5.10).

페이지 번호는 주소의 쿼리 `?page=2`에 둔다.

```tsx
const [params] = useSearchParams()
const page = Math.max(Number(params.get('page')) || 1, 1)
```

- 상태가 아니라 **주소**에 두는 이유: 새로고침해도, 링크를 공유해도 같은 페이지가 열린다. 뒤로 가기도 페이지별로 된다.
- `Number(null)`은 `0`, `Number('abc')`는 `NaN`이라 `|| 1`로 1이 된다. `Math.max(..., 1)`로 0 이하를 막는다.

### 5.7 화면의 권한 검사는 안내용

`ManagePage`는 `blog.viewer.isOwner`가 `false`면 403 오류 화면("접근 권한이 없습니다", 스텝 6부터 `ErrorPage`)을 그린다. 그렇다고 이게 보안은 아니다. 브라우저 개발자 도구로 코드를 바꾸거나 `curl`로 `PATCH /api/blog`를 직접 부를 수 있다. **진짜 검사는 서버**(`BlogOwnerGuard.requireOwner` → 401/403)가 한다(헌법 원칙 IV, [16](./16-authorization-visibility.md)). 화면 검사는 주인이 아닌 사람에게 쓸모없는 버튼을 보여 주지 않는 **친절**이다.

### 5.8 React는 글자를 자동으로 이스케이프한다

`frontend/src/components/Sidebar.tsx`

```tsx
function CommentItem({ comment }: { comment: RecentComment }) {
  const text = comment.state === 'SECRET' ? '비밀댓글입니다'
    : comment.state === 'BLINDED' ? '관리자가 숨긴 댓글입니다'
      : `${comment.content} · ${comment.authorNickname}`
  return (
    <li className="small">
      <Link to={`/${comment.postId}#comment-${comment.id}`}>{text}</Link>
    </li>
  )
}
```

댓글 내용이 `<img src=x onerror=alert(1)>`이어도 `{text}`는 **글자 그대로** 화면에 나온다. JSX의 `{값}`은 문자열을 HTML로 해석하지 않고 텍스트로 넣기 때문이다. 블로그 이름·소개·닉네임·글 제목도 모두 같다(명세 보안: "본문 외 입력은 글자 그대로만 보인다"). HTML로 넣는 `dangerouslySetInnerHTML`은 글 본문(`contentHtml`)에만, DOMPurify를 거쳐 쓴다(스텝 6, [14](./14-xss-sanitize-csp.md)).

### 5.9 페이지 묶음 계산과 파일 이름 대소문자

`frontend/src/components/pageGroup.ts`

```ts
export function pageGroup(current: number, totalPages: number): PageGroup {
  if (totalPages < 1) {
    return { pages: [], prev: null, next: null }
  }
  const start = Math.floor((current - 1) / PAGE_GROUP) * PAGE_GROUP + 1
  const end = Math.min(start + PAGE_GROUP - 1, totalPages)
  const pages = Array.from({ length: Math.max(end - start + 1, 0) }, (_, i) => start + i)
  return { pages, prev: start > 1 ? start - 1 : null, next: end < totalPages ? end + 1 : null }
}
```

- 명세: 페이지 번호는 10개씩 묶고 이전·다음 버튼(spec 목록과 페이지).
- 15페이지면 `start = floor(14/10)*10+1 = 11`, `end = min(20, 전체)`. 이전 버튼은 10, 다음은 21.
- 계산을 컴포넌트(`Pagination.tsx`)에서 떼어 **순수 함수**로 둔 이유: 화면 없이 Vitest로 바로 시험할 수 있다(`pageGroup.test.ts`).

처음에는 이 파일 이름이 `pagination.ts`였다. 그러자 `npx tsc -b`가 실패했다.

```
error TS1149: File name '.../components/pagination.ts' differs from already included file name
'.../components/Pagination.ts' only in casing.
```

macOS 기본 파일 시스템(APFS)은 **대소문자를 구분하지 않는다**. `Pagination.tsx`(컴포넌트)를 `'../../components/Pagination'`으로, 계산 파일을 `'./pagination'`으로 불렀는데, 확장자를 빼고 보면 두 이름이 대소문자만 다르다. TypeScript가 "같은 파일을 다른 이름으로 부른다"고 보고 막은 것이다(리눅스 CI처럼 구분하는 곳에서는 또 다르게 동작해 더 위험하다). 이름을 겹치지 않게 `pageGroup.ts`로 바꿔 해결했다.

### 5.10 (스텝 5) 글쓰기·수정 한 화면, 카테고리 관리

**라우트 더하기** (`frontend/src/pages/manage/ManagePage.tsx`)

```tsx
<NavLink to="/manage/write">글쓰기</NavLink>
...
<Route path="write" element={<PostWritePage key="new" />} />
<Route path="posts/:postId/edit" element={<PostWritePage key="edit" />} />
<Route path="categories" element={<CategoriesPage />} />
```

새 글과 수정은 거의 같은 화면이라 컴포넌트 하나(`PostWritePage`)로 만들고, `useParams()`의 `postId`가 있으면 수정으로 본다(`const editing = postId !== undefined`).

**`key`를 다르게 준 이유.** React는 같은 자리에 같은 컴포넌트가 다시 오면 **이미 있는 것을 재사용**하고 상태(`useState`)를 그대로 둔다. 수정 화면(`/manage/posts/6/edit`)에서 메뉴의 "글쓰기"를 누르면 같은 `PostWritePage`가 같은 자리에 오므로, `key`가 없으면 방금 보던 글의 제목·본문이 새 글 화면에 그대로 남는다. `key`가 바뀌면 React는 다른 컴포넌트로 보고 **버리고 새로 만든다**. 상태와 연타 방지 키(`useRef`)도 새로 시작한다.

**불러온 본문과 입력 중인 본문을 나눈 이유** (`pages/manage/PostWritePage.tsx`)

```tsx
const [contentHtml, setContentHtml] = useState('')   // 지금 에디터에 쓰인 본문. 저장할 때 보낸다
const [loadedHtml, setLoadedHtml] = useState('')     // 서버에서 불러온 본문. 에디터에 한 번 넣을 값
...
<Editor initialHtml={loadedHtml} onChange={setContentHtml} />
```

에디터(Tiptap)는 제목 칸처럼 `value`/`onChange`로 매번 값을 주고받는 **제어 컴포넌트가 아니다**. 내용을 에디터가 스스로 들고 있고, 바뀔 때마다 `onChange`로 알려 줄 뿐이다. 만약 입력 중인 `contentHtml`을 다시 `initialHtml`로 넘기면, 글자를 칠 때마다 에디터 내용을 통째로 다시 넣게 되어 커서가 맨 끝으로 튄다. 그래서 "처음 넣을 값"(`loadedHtml`, 수정 화면에서 불러왔을 때 한 번 바뀜)과 "지금 값"(`contentHtml`)을 따로 둔다. 에디터 쪽은 `initialHtml`이 바뀔 때만 내용을 넣는다.

```tsx
// components/editor/Editor.tsx
useEffect(() => {
  if (editor && initialHtml !== editor.getHTML()) {
    editor.commands.setContent(initialHtml, { emitUpdate: false })
  }
}, [editor, initialHtml])
```

`emitUpdate: false`는 "프로그램이 넣은 내용은 사용자가 고친 것으로 알리지 마라"다. 에디터 자체는 [26](./26-wysiwyg-editor-tiptap.md).

**삭제 확인 창.** 삭제는 되돌릴 수 없어 한 번 더 묻는다(POST-03 "확인 창을 거쳐").

```tsx
async function remove() {
  if (!window.confirm('이 글을 삭제할까요? 댓글과 공감도 함께 사라집니다.')) {
    return
  }
  try {
    await api(`/api/posts/${postId}`, { method: 'DELETE' })
    navigate('/')
  } catch (error) {
    setErrors({ form: errorMessage(error) })
  }
}
```

`window.confirm`은 브라우저 기본 확인 창으로, 확인이면 `true`, 취소면 `false`를 돌려주고 그동안 화면 코드가 멈춘다. 모양을 꾸밀 수 없지만 따로 만들 것이 없다. 카테고리 삭제도 같은 방식으로 "글 N개가 미분류로 옮겨집니다"를 미리 보여 준다(`CategoriesPage`의 `CategoryRow.remove`).

**카테고리 화면: 다시 불러오기를 함수 하나로** (`pages/manage/CategoriesPage.tsx`)

```tsx
const load = useCallback(() => {
  api<CategoryTree>('/api/categories')
    .then(setTree)
    .catch((caught: unknown) => setError(errorMessage(caught)))
}, [])

useEffect(() => {
  load()
}, [load])
...
<CategoryRow key={category.id} category={category} onChanged={load} onError={setError} />
```

- 추가·이름 변경·삭제가 끝나면 목록과 글 수가 바뀌므로 서버에서 다시 받는다. 화면에서 직접 고치는 것보다 단순하고, 서버가 계산한 글 수와 어긋나지 않는다.
- `useCallback(함수, [])`은 다시 그려도 **같은 함수 객체**를 준다. 그냥 `const load = () => ...`로 만들면 그릴 때마다 새 함수가 되어, `useEffect(..., [load])`가 그릴 때마다 다시 실행되고 → 불러와서 `setTree` → 다시 그리기 → 또 불러오기가 끝없이 반복된다.
- 행 하나(`CategoryRow`)를 컴포넌트로 뺀 이유: "이름 변경 중인가"(`editing`)와 고치는 중인 이름(`name`)은 행마다 따로다. 행 컴포넌트가 자기 상태를 들고, 끝나면 `onChanged`(부모의 `load`)를 부른다.

**주인에게만 보이는 수정 링크** (`pages/blog/BlogMainPage.tsx`)

```tsx
{owner && <Link className="small" to={`/manage/posts/${post.id}/edit`}>수정</Link>}
```

블로그 머리글에는 주인에게만 "글쓰기" 버튼(`/manage/write`)이 보인다. 5.7과 같이 이것은 안내이고, 남이 이 주소를 직접 열어도 서버가 편집용 조회(`GET /api/manage/posts/{id}`)에서 403·404로 막는다.

### 5.11 (스텝 6) 댓글, 글 상세, 홈, 오류 화면

**Thymeleaf에 빗대 보기.** 지금까지와 같은 대응이다([28](./28-thymeleaf-to-react.md)).

| 하는 일 | Thymeleaf | 이 프로젝트 (React) |
| --- | --- | --- |
| 댓글 목록 그리기 | 컨트롤러가 `model.addAttribute("comments", ...)`, 템플릿이 `th:each="c : ${comments}"` | `useEffect`에서 `/api/posts/{id}/comments`를 불러 `comments` 상태에 넣고 `comments.map((comment) => <CommentItem .../>)` |
| 댓글 쓰기 | `<form method="post">` → 서버가 저장 → `redirect:/posts/{id}` (페이지 전체를 새로 받음) | `fetch` POST → 응답으로 받은 댓글 하나를 목록 상태에 붙임 (페이지는 그대로) |
| 댓글 더보기 | 다음 페이지 링크(`?page=2`)로 새 페이지 | 받은 `nextCursor`로 다음 묶음을 불러와 기존 목록 뒤에 이어 붙임 |
| 없는 글 | 컨트롤러가 404 상태와 오류 템플릿 | API 404를 받으면 `ErrorPage status={404}` 컴포넌트를 그림 |

**Comments: 목록·더보기·쓰기·지우기** (`frontend/src/components/Comments.tsx`)

```tsx
const [comments, setComments] = useState<Comment[]>([])
const [nextCursor, setNextCursor] = useState<string | null>(null)
const [totalCount, setTotalCount] = useState(0)
const [content, setContent] = useState('')
const [error, setError] = useState<string | null>(null)
const [submitting, setSubmitting] = useState(false)
// 버튼은 다음 그리기에서야 꺼지므로, 그 사이 두 번째 클릭은 ref로 바로 막는다
const inFlight = useRef(false)
// 등록 한 번에 키 하나. 실패해 다시 누르면 같은 키로, 성공하면 다음 댓글을 위해 새 키로
const idempotencyKey = useRef(newIdempotencyKey())
```

- 처음 묶음은 `useEffect`에서 `active` 플래그와 함께 불러온다(5.5와 같은 모양). 더보기(`loadMore`)는 버튼을 누를 때 부르는 일반 함수라 효과가 아니다.
- 비회원에게는 쓰기 칸 대신 "로그인하고 댓글 쓰기" 링크(`loginUrl()`)를 보여 준다. 로그인하면 `redirect`로 이 글에 돌아온다(spec US3 시나리오 6).
- 지우기 버튼은 서버가 준 `viewer.canDelete`가 참일 때만 보인다. 작성자와 블로그 주인만 참이다. 이것도 안내이고 서버가 다시 검사한다(5.7).
- 비밀댓글·숨긴 댓글은 서버가 `state`로 알려 주고 내용을 `null`로 보낸다. 화면은 `state`를 보고 "비밀댓글입니다." 같은 문구만 그린다([29](./29-comments-design.md)).

**`useRef`로 연타를 즉시 막기: 실제로 난 버그**

```tsx
async function submit(event: FormEvent) {
  event.preventDefault()
  ...
  if (inFlight.current) {
    return
  }
  inFlight.current = true
  setSubmitting(true)
  ...
  try {
    const created = await api<Comment>(`/api/posts/${postId}/comments`, {
      method: 'POST', body: { content: content.trim() }, idempotencyKey: idempotencyKey.current,
    })
    idempotencyKey.current = newIdempotencyKey()
    setContent('')
    // 같은 키의 재시도면 서버가 같은 댓글을 다시 돌려주므로, 이미 있는 댓글은 붙이지 않는다
    if (!nextCursor && !comments.some((comment) => comment.id === created.id)) {
      setComments((previous) => [...previous, created])
      setTotalCount(totalCount + 1)
      onCountChange(totalCount + 1)
    }
  } finally {
    inFlight.current = false
    setSubmitting(false)
  }
}
```

처음에는 `submitting` 상태로 등록 버튼을 끄는 것(3.4)만 있었다. 헤드리스 Chrome으로 등록 버튼을 **빠르게 두 번** 눌러 확인해 보니 이랬다.

| | 서버 | 화면 |
| --- | --- | --- |
| 고치기 전 | 댓글 **하나**(같은 연타 방지 키라 두 번째 요청은 첫 응답을 그대로 받음, [17](./17-idempotency-redis.md)) | 같은 댓글이 **두 줄** |

원인은 상태가 바뀌는 시점이다. `setSubmitting(true)`는 값을 바로 바꾸지 않고 "다음에 그릴 때 true로" 예약한다. 두 클릭이 같은 그리기 사이에 들어오면, 두 번째 클릭이 실행될 때도 버튼은 아직 켜져 있고 `submitting`도 아직 `false`다. 그래서 요청이 두 번 나갔고, 두 응답(같은 댓글)이 둘 다 목록에 붙었다.

고친 방법 두 가지:
1. `useRef`: `ref.current`는 **바꾸는 즉시** 바뀐 값이 읽힌다(다시 그리기를 기다리지 않는다). 그래서 두 번째 클릭은 `inFlight.current`가 `true`인 것을 보고 바로 돌아간다. 화면에 보일 값(버튼 꺼짐)은 상태, 즉시 판단할 값은 ref로 나눴다.
2. 같은 `id`의 댓글이 이미 있으면 붙이지 않는다. 같은 키로 재시도해 같은 응답이 온 경우까지 막는 두 번째 안전장치다.

고친 뒤 같은 확인에서 서버·화면 모두 댓글 하나였다.

**상태 갱신 함수 안에서 부모 콜백을 부르지 않기.** 처음에는 이렇게 썼다.

```tsx
// 처음 코드 (고침)
setTotalCount((count) => {
  onCountChange(count + 1)   // 부모(글 상세)의 댓글 수도 갱신
  return count + 1
})
```

`setX(이전값 => 새값)`에 넘기는 함수는 **새 값을 계산만 하는 함수**여야 한다. React는 개발 모드의 StrictMode에서 이런 함수를 일부러 두 번 불러 부작용이 있는지 드러낸다. 그 안에서 부모 상태를 바꾸는 콜백을 부르면 그것도 두 번 불린다. 그래서 새 값을 먼저 계산하고(`totalCount + 1`), `setTotalCount`와 `onCountChange`를 따로 부르게 고쳤다.

**글 상세: 판별 유니온으로 화면 상태 나누기** (`frontend/src/pages/post/PostPage.tsx`)

```tsx
type PostState = { status: 'loading' } | { status: 'ok'; post: PostDetail } | { status: 'notFound' }
  | { status: 'subscribersOnly'; blogName: string } | { status: 'error' }
```

```tsx
if (error instanceof ApiError && error.code === 'SUBSCRIBERS_ONLY') {
  setState({ status: 'subscribersOnly', blogName: String(error.detail?.blogName ?? '') })
} else if (error instanceof ApiError && error.status === 404) {
  setState({ status: 'notFound' })
} else {
  setState({ status: 'error' })
}
```

- 3.7의 판별 유니온을 화면 상태 다섯 가지로 넓혔다. `status`로 갈라 놓으면 `post`는 `'ok'`일 때만, `blogName`은 `'subscribersOnly'`일 때만 존재해서, "글이 없는데 글 제목을 그리는" 실수를 TypeScript가 막는다.
- 서버 오류 코드(16번 문서의 `readable`)가 화면 상태로 1:1 대응한다: 404 → `ErrorPage status={404}`, 403 `SUBSCRIBERS_ONLY` → 구독 안내 상자(제목·본문 없음), 그 밖의 오류 → `ErrorPage status={500}`.
- 본문은 `dangerouslySetInnerHTML`에 정화 함수를 거쳐 넣는다([14](./14-xss-sanitize-csp.md) 5.6).

**오류 화면** (`frontend/src/components/ErrorPage.tsx`): 401·403·404·500 문구를 한 컴포넌트에 모았다(목업 errors). 401이면 로그인 버튼, 그 밖에는 홈으로 버튼. 블로그 주소에서 본 403에는 "이 블로그 처음으로"도 보인다. `NotFoundPage`도 이제 `<ErrorPage status={404} />` 한 줄이다. 오류 화면에 서버 내부 정보를 보여 줄 일이 없는 것은, 서버가 애초에 응답에 담지 않기 때문이다(COM-02).

**관리자 영역** (`frontend/src/pages/admin/AdminPage.tsx`): 비회원은 `redirectToLogin()`, `me.role`이 `ADMIN`이 아니면 `<ErrorPage status={403} />`. 5.7과 같이 안내용이고, 실제 보호는 서버의 `/api/admin/**`(16번 문서 5.9).

**홈의 글 링크는 `<a href>`** (`frontend/src/pages/home/HomePage.tsx`)

```tsx
<h3><a href={blogUrl(post.blog.address, `/${post.id}`)}>{post.title}</a></h3>
```

홈은 플랫폼 주소(`blog.test`)이고 글은 각 블로그 주소(`alpha.blog.test`)에 있다. 다른 호스트라 React Router의 `<Link>`(같은 호스트 안 이동)를 쓸 수 없고, 보통 링크로 페이지를 새로 연다(5.3의 `navigate`와 `window.location.assign`의 차이와 같은 이유).

### 5.12 (스텝 7) 공감 버튼, 검색, 파일 올리기

**Thymeleaf에 빗대 보기.**

| 하는 일 | Thymeleaf | 이 프로젝트 (React) |
| --- | --- | --- |
| 공감 누르기 | `<form method="post" action="/posts/9/like">` → 서버 저장 → 글 페이지로 redirect, 새 숫자가 그려진 페이지를 통째로 다시 받음 | 누르는 순간 화면의 하트와 숫자부터 바꾸고, `PUT /api/posts/9/like` 응답의 실제 값으로 맞춤 |
| 검색 | `<form method="get" action="/search"><input name="q">` → 주소가 `/search?q=...`가 되고 컨트롤러가 `@RequestParam q`로 받음 | `navigate('/search?q=...')`로 주소만 바꾸고, 검색 화면이 `useSearchParams()`로 `q`를 읽어 API를 부름 |
| 사진 올리기 | `<form method="post" enctype="multipart/form-data"><input type="file" name="file">` | `FormData`에 파일을 담아 `fetch`로 보냄, 페이지는 그대로 |

**공감 버튼: 낙관적 갱신** (`frontend/src/components/LikeButton.tsx`)

공감은 누르면 바로 반응해야 하는 버튼이다. 서버 응답을 기다렸다가 하트를 채우면, 느린 네트워크에서는 눌렸는지 모를 정도로 늦다. 그래서 **성공할 것이라고 보고(낙관적으로) 화면부터 바꾸고**, 응답이 오면 서버 값으로 맞추며, 실패하면 되돌린다. 이것을 낙관적 갱신(optimistic update)이라고 한다.

```tsx
const [liked, setLiked] = useState(initialLiked)
const [count, setCount] = useState(initialCount)
const [error, setError] = useState<string | null>(null)
const inFlight = useRef(false)

async function toggle() {
  if (me.status !== 'member') {
    redirectToLogin()
    return
  }
  if (inFlight.current) {
    return
  }
  inFlight.current = true
  const next = !liked
  // 먼저 바꿔 보여 주고(낙관적 갱신), 실패하면 되돌린다
  setLiked(next)
  setCount(count + (next ? 1 : -1))
  setError(null)
  try {
    const result = await api<{ liked: boolean; likeCount: number }>(`/api/posts/${postId}/like`,
      { method: next ? 'PUT' : 'DELETE' })
    setLiked(result.liked)
    setCount(result.likeCount)
  } catch (caught) {
    setLiked(liked)
    setCount(count)
    setError(errorMessage(caught))
  } finally {
    inFlight.current = false
  }
}
```

줄별로:

- `useState(initialLiked)`: 처음 값은 글 상세 응답의 `viewer.liked`와 `likeCount`다. `useState`의 인자는 **처음 한 번만** 쓰인다. 그래서 다른 글로 넘어갈 때는 `key`로 버튼을 새로 만든다(아래 key 이야기).
- `me.status !== 'member'`: 비회원이면 요청하지 않고 로그인 화면으로 보낸다. 로그인 뒤 이 글로 돌아온다(spec US3 시나리오 6). 서버도 401로 막는다.
- `inFlight` ref: 요청이 진행 중이면 다음 클릭을 바로 무시한다. 스텝 6 댓글의 연타 방지와 같은 이유다(state는 다음 그리기에서야 바뀌므로 ref로 즉시).
- `const next = !liked`: 누른 결과(켜기·끄기)를 정한다. 서버 API가 **토글이 아니라 "켜기 PUT, 끄기 DELETE"**인 것이 중요하다. 같은 요청이 두 번 가도 결과가 같다(멱등, [17](./17-idempotency-redis.md)). "토글" API였다면 재시도나 중복 요청이 상태를 거꾸로 뒤집는다.
- `setLiked(next); setCount(...)`: 응답 전에 화면부터 바꾼다.
- `setLiked(result.liked); setCount(result.likeCount)`: 서버가 돌려준 **실제** 값으로 맞춘다. 그 사이 다른 사람이 공감했다면 숫자가 1보다 더 바뀔 수 있다.
- `catch`에서 `setLiked(liked)`: 이 함수가 시작될 때의 값(클로저에 잡힌 값)으로 되돌린다. 네트워크 오류나 403이면 화면이 거짓말을 하지 않게.

낙관적 갱신은 "서버가 거의 항상 성공하고, 실패해도 되돌리기 쉬운" 동작에만 쓴다. 공감은 딱 맞다. 반대로 결제나 글 발행처럼 실패가 의미 있는 동작은 응답을 기다린다.

> 이 버튼을 만들며 서버 쪽에서도 버그 두 개를 만났다. 같은 글에 동시에 공감이 몰리면 데드락이 났고, 같은 사람이 동시에 여러 번 누르면 늦게 처리된 응답이 옛 공감 수(0)를 돌려줬다. 화면이 "서버 값으로 맞추기" 때문에 그 0을 그대로 보여 줄 뻔했다. [33](./33-isolation-deadlock.md)에서 자세히 다룬다.

**key가 겹치면 생긴 일: 공감 버튼이 두 개** (`frontend/src/pages/post/PostPage.tsx`)

스텝 7 화면을 헤드리스 Chrome으로 확인하다가, 글 상세에 공감 버튼이 **두 개** 그려진 것을 발견했다. 하나를 눌러도 숫자가 안 바뀌었다. 원인은 이 두 줄이었다.

```tsx
<LikeButton key={post.id} postId={post.id} ... />
...
<Comments key={post.id} postId={post.id} ... />
```

`key`는 React가 "이전 그리기의 어느 자식이 이번 그리기의 어느 자식인가"를 맞추는 이름표다. 보통 `map`으로 만든 목록에서 쓰지만, 고정된 자식에 줘도 같은 규칙이 적용된다. **같은 부모 아래 형제끼리는 `key`가 달라야 한다.** 둘 다 `10`이면 React가 둘을 구분하지 못한다. React 문서는 key가 겹치면 자식이 중복되거나 빠질 수 있다고 경고한다(개발 모드 콘솔에 "Encountered two children with the same key" 경고가 뜬다).

실제로 일어난 순서는 이렇다.

1. 처음 그릴 때는 정상이다.
2. 댓글을 불러온 `Comments`가 `onCountChange`로 부모의 댓글 수를 바꾼다. `PostPage`의 상태가 바뀌어 `Article`을 다시 그린다.
3. 다시 그릴 때 key가 같은 두 형제를 맞추다가 꼬여, 공감 버튼 DOM이 하나 더 남았다. 화면 맨 위의 버튼은 React가 더 이상 관리하지 않는 사본이었고, 그걸 누르면 클릭 처리기는 돌지만(요청은 감) 그 사본의 글자는 바뀌지 않았다.

고친 코드:

```tsx
<LikeButton key={`like-${post.id}`} postId={post.id} me={me} initialLiked={post.viewer.liked}
            initialCount={post.likeCount} />
...
<Comments key={`comments-${post.id}`} postId={post.id} me={me} commentAllowed={post.commentAllowed}
          onCountChange={onCommentCount} />
```

여기서 `key`를 준 목적은 목록 구분이 아니라 **"글이 바뀌면 이 컴포넌트를 새로 만들어라"**다. 이전 글 → 다음 글로 넘어가면 `post.id`가 바뀌어 key가 달라지고, React는 이전 버튼을 버리고 새로 만든다. 그래서 `useState(initialLiked)`가 새 글의 값으로 다시 시작한다(스텝 5의 글쓰기·수정 화면 `key`와 같은 기법). 이 목적은 살리면서 형제끼리는 겹치지 않게 접두어를 붙였다.

> Thymeleaf에는 이런 문제가 없다. 매 요청마다 HTML 전체를 새로 만들기 때문이다. React는 이전 화면을 **고쳐서** 새 화면을 만들기 때문에(재조정, reconciliation), 무엇이 무엇인지 맞추는 이름표가 필요하다([28](./28-thymeleaf-to-react.md)).

**검색: 검색어는 주소에** (`frontend/src/components/BlogHeader.tsx`, `frontend/src/pages/search/BlogSearchPage.tsx`)

머리글의 검색 상자는 제출하면 주소만 바꾼다.

```tsx
function search(event: FormEvent) {
  event.preventDefault()
  if (q.trim()) {
    navigate(`/search?${new URLSearchParams({ q: q.trim() })}`)
  }
}
```

- `preventDefault()`: 브라우저의 기본 폼 제출(페이지 새로 열기)을 막는다(5.2와 같음).
- `new URLSearchParams({ q })`: 한글·공백·`&` 같은 글자를 주소에 넣을 수 있게 인코딩한다. 직접 `'/search?q=' + q`로 붙이면 검색어에 `&page=3`이 들어 있을 때 주소가 깨진다.
- 공백만이면 이동하지 않는다. 서버도 400으로 막는다([32](./32-search-like.md)).

검색 결과 화면은 검색어를 **상태가 아니라 주소에서** 읽는다.

```tsx
const [params] = useSearchParams()
const q = params.get('q') ?? ''
const page = Math.max(Number(params.get('page')) || 1, 1)
...
useEffect(() => {
  let active = true
  if (!q.trim()) {
    return
  }
  const query = new URLSearchParams({ q, page: String(page) })
  api<PageResponse<PostSummary>>(`/api/search?${query}`, { allowAnonymous: true })
    .then((found) => { if (active) { setResult(found); setError(null) } })
    ...
  return () => { active = false }
}, [q, page])
```

- 주소가 곧 화면의 상태라서: 결과 주소를 복사해 남에게 보내면 같은 결과가 보이고, 새로고침해도 검색어가 남고, 뒤로 가기로 이전 검색어로 돌아간다(tasks T048 "검색어 유지, 결과 주소 공유 가능").
- `[q, page]` 의존성: 페이지 번호를 누르면 주소가 `?q=...&page=2`로 바뀌고, 효과가 다시 돌아 다음 쪽을 부른다.
- `active` 플래그: "고양"을 검색하고 바로 "고양이"를 검색했을 때 늦게 온 "고양" 응답이 덮어쓰지 않게(5.5).
- `Number(params.get('page')) || 1`: 주소에 `page=abc`가 와도 `NaN || 1`로 1쪽.

Thymeleaf의 `<form method="get">` + `@RequestParam`과 결과가 같다. 다른 점은 페이지를 새로 받지 않고 주소와 목록만 바뀐다는 것이다.

**파일 올리기: FormData** (`frontend/src/api/client.ts`)

```ts
export async function uploadFile<T>(path: string, file: File, field = 'file'): Promise<T> {
  const form = new FormData()
  form.append(field, file)
  const response = await fetch(path, {
    method: 'POST',
    headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
    credentials: 'same-origin',
    body: form,
  })
  ...
}
```

- `FormData`: `<form enctype="multipart/form-data">`가 보내는 본문을 자바스크립트로 만드는 객체다. `append('file', file)`은 `<input type="file" name="file">`과 같다. 서버의 `@RequestPart(name = "file")`이 이 이름으로 받는다.
- **`Content-Type`을 직접 쓰지 않는다.** 본문이 `FormData`면 브라우저가 `multipart/form-data; boundary=----...`를 알아서 붙인다. boundary는 파트 사이 구분 문자열이라, 직접 `multipart/form-data`만 쓰면 boundary가 빠져 서버가 본문을 못 나눈다. 그래서 JSON용 `api()`와 따로 만들었다(`api()`는 `Content-Type: application/json`을 붙인다).
- `X-Requested-With`: 다른 API와 같은 CSRF 대비 머리글([13](./13-csrf-samesite-cors.md)).
- 서버 쪽 처리(크기 제한, 형식 검사, 썸네일)와 에디터 버튼 연결은 [30 이미지 업로드와 처리](./30-image-upload.md)에서 다룬다.

**태그 입력** (`frontend/src/components/editor/TagInput.tsx`)은 한글 조합 중 Enter 처리(`isComposing`)와 붙여 넣은 쉼표 나누기 버그가 있었다. [31 태그와 다대다 관계](./31-tags-many-to-many.md)에서 다룬다.

## 6. 자주 하는 실수와 함정

1. **폼 안의 버튼에 `type` 안 쓰기**: 기본이 `submit`이라 "코드 받기"를 누를 때 가입이 제출된다. 제출 버튼이 아니면 `type="button"`.
2. **`preventDefault()` 빼먹기**: 페이지가 새로 열리고 상태가 사라진다.
3. **`value`만 주고 `onChange` 없음**: 칸에 글자가 안 쳐진다.
4. **실패하면 입력값을 비움**: 사용자가 다 다시 쓴다. 상태를 그대로 두면 칸도 그대로다.
5. **앞 단계가 바뀌었는데 뒤 단계 표시가 남음**: 이메일을 바꿨는데 "확인됨"이 남는 식. 바꿀 때 함께 초기화한다.
6. **효과에서 늦게 온 응답을 그대로 반영**: 다른 페이지 글이 보인다. `active` 플래그.
7. **효과 안에서 바로 setState**: 다시 그리기가 한 번 더 생긴다(oxlint `set-state-in-effect`). 응답이 왔을 때 바꾸거나, 그리는 중에 계산한다.
8. **다른 서브도메인으로 `navigate`**: 같은 호스트 안 경로로 해석되어 엉뚱한 화면이 열린다. `window.location.assign`.
9. **redirect 값을 그대로 따라감**: 열린 리다이렉트. `safeRedirect`처럼 우리 주소만.
10. **화면 검사만 믿음**: 버튼을 숨겨도 API는 열려 있다. 서버가 검사한다.
11. **대소문자만 다른 파일 이름**: macOS에서는 같은 파일로, 리눅스에서는 다른 파일로 취급된다. 이름 자체를 다르게.
12. **StrictMode에서 요청이 두 번 보인다고 놀람**: 개발 모드에서만 효과를 한 번 더 실행한다. 정리 함수가 맞으면 문제없다.
13. **(스텝 5) 같은 컴포넌트를 두 라우트에 쓰면서 `key`를 안 줌**: 수정 화면에서 "글쓰기"로 가도 이전 글 내용이 남는다. 라우트마다 다른 `key`.
14. **(스텝 5) 에디터에 입력 중인 값을 다시 넣기**: 칠 때마다 내용을 통째로 바꿔 커서가 튄다. 불러온 값과 입력 중인 값을 나눈다.
15. **(스텝 5) 효과의 의존성에 매번 새로 만드는 함수**: `useEffect(..., [load])`의 `load`를 `useCallback` 없이 만들면 무한히 다시 불러온다.
16. **(스텝 6) 상태만으로 연타를 막으려 함**: 버튼은 다음 그리기에서야 꺼진다. 그 사이의 두 번째 클릭은 `useRef`로 막는다.
17. **(스텝 6) `setX(이전값 => ...)` 안에서 다른 일을 함**: 갱신 함수는 계산만 한다. StrictMode에서 두 번 불릴 수 있다.
18. **(스텝 6) 다른 블로그 주소로 `<Link>`**: 같은 호스트 경로로 해석된다. 다른 호스트는 `<a href>`.
19. **(스텝 7) 형제 컴포넌트에 같은 `key`**: 다시 그릴 때 자식이 복제되거나 빠진다. 공감 버튼이 두 개 그려졌다. 형제끼리는 key가 달라야 한다.
20. **(스텝 7) 낙관적 갱신만 하고 서버 값으로 안 맞춤**: 다른 사람의 공감이 반영되지 않고, 실패해도 화면이 거짓말을 한다. 응답 값으로 맞추고 실패하면 되돌린다.
21. **(스텝 7) 토글 API에 낙관적 갱신**: 재시도·중복 요청이 상태를 뒤집는다. "켜기 PUT, 끄기 DELETE"처럼 결과가 정해진 요청으로.
22. **(스텝 7) 검색어를 state에만 둠**: 새로고침하면 사라지고 결과 주소를 나눌 수 없다. 주소(`?q=`)에 둔다.
23. **(스텝 7) `FormData`를 보내며 `Content-Type: multipart/form-data`를 직접 씀**: boundary가 빠져 서버가 못 읽는다. 브라우저에 맡긴다.

## 7. 직접 해 보기

**실습 1. 프론트 테스트와 검사**

```bash
cd frontend
npm test            # client, host(safeRedirect), pageGroup
npx tsc -b          # 타입 검사
npm run lint        # oxlint
```

**실습 2. 화면을 띄워 가입부터 블로그까지**

`/etc/hosts`에 한 줄을 더한다(관리자 권한 필요, quickstart).

```
127.0.0.1 blog.test alpha.blog.test beta.blog.test gamma.blog.test
```

```bash
docker compose up -d
./mvnw spring-boot:run              # 터미널 1
cd frontend && npm run dev          # 터미널 2
```

1. `http://blog.test:5173/signup`에서 이메일 → 코드 받기. 코드는 **서버 로그**(`[개발용 메일]`)에 나온다.
2. 일부러 틀린 코드, 7자 비밀번호, 이미 있는 닉네임을 넣어 칸별 오류와 **입력값이 남는 것**을 확인한다.
3. 가입 → 블로그 만들기 → `alpha.blog.test:5173/manage`로 넘어가는지(다른 호스트라 페이지가 새로 열림).
4. 관리 메뉴에서 "블로그 설정"을 누르면 초록 배경이 옮겨 가는지(`NavLink` active).
5. 개발자 도구 Network 탭에서 블로그 메인의 `/api/me`, `/api/blog`, `/api/blog/sidebar`, `/api/posts` 네 요청을 본다.

`/etc/hosts`를 못 고치면 Chrome을 이렇게 띄워도 된다(그 창에서만 `*.blog.test`가 내 컴퓨터를 가리킨다).

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --user-data-dir=/tmp/blog-chrome \
  --host-resolver-rules="MAP blog.test 127.0.0.1, MAP *.blog.test 127.0.0.1" \
  http://blog.test:5173/signup
```

**실습 3. 늦게 온 응답 흉내 내기**

`BlogMainPage`의 효과에서 `if (active)`를 지우고, 개발자 도구 Network에서 "Slow 3G"로 바꾼 뒤 페이지 번호를 빠르게 여러 번 누른다. 마지막에 누른 페이지가 아닌 글이 보일 수 있다. 되돌린다.

**실습 4. 열린 리다이렉트 막힘 확인**

`http://blog.test:5173/login?redirect=https://example.com`으로 로그인하면 example.com이 아니라 홈으로 간다. `redirect=http://alpha.blog.test:5173/manage`면 그 블로그 관리 화면으로 간다.

**실습 5. set-state-in-effect 경고 다시 보기**

`BlogMainPage` 효과 맨 앞에 `setError(null)`을 넣고 `npm run lint`. 경고를 보고 되돌린다.

**실습 6. (스텝 5) `key`를 빼 보기**

`ManagePage.tsx`의 두 `PostWritePage`에서 `key`를 지우고 `npm run dev`로 띄운다. 블로그 메인에서 글의 "수정"을 눌러 수정 화면을 연 뒤, 왼쪽 메뉴의 "글쓰기"를 누른다. 기대: 제목 칸에 방금 글의 제목이 그대로 남아 있다. `key`를 되돌리면 빈 화면이 된다.

**실습 7. (스텝 6) 연타 버그 되살려 보기**

1. `Comments.tsx`의 `submit`에서 `if (inFlight.current) { return }` 블록과 `comments.some(...)` 조건을 잠시 지운다.
2. `npm run dev`로 띄워 로그인한 상태로 글 상세를 열고, 개발자 도구 콘솔에서 등록 버튼을 한 번에 두 번 누른다.
   ```js
   const b = [...document.querySelectorAll('#comments button')].find(x => x.textContent === '등록'); b.click(); b.click()
   ```
3. 기대: 서버에는 댓글이 하나(새로고침하면 하나)인데, 누른 직후 화면에는 두 줄이 보인다. 되돌리고 같은 것을 하면 한 줄이다.

**실습 8. (스텝 6) 오류 화면 보기**

남의 비공개 글 주소(`http://alpha.blog.test:5173/{비공개 글 번호}`)를 로그아웃한 창에서 열면 404 화면, 일반 회원으로 `http://blog.test:5173/admin`을 열면 403 화면이 나온다.

**실습 (스텝 7) A. key를 다시 겹쳐 보기**

`PostPage.tsx`에서 두 key를 다시 `key={post.id}`로 바꾸고 `npm run dev`로 띄운다. 댓글이 있는 글을 열고 개발자 도구 콘솔의 key 경고와, Elements 탭에서 공감 버튼이 몇 개인지 본다. 되돌린다.

**실습 (스텝 7) B. 낙관적 갱신의 되돌리기 보기**

개발자 도구 Network 탭에서 "Offline"을 켜고 공감을 누른다. 하트가 채워졌다가 오류 문구와 함께 원래대로 돌아오는지 본다. "Slow 3G"로 바꾸고 누르면 응답 전에 이미 바뀌어 있는 것을 볼 수 있다.

**실습 (스텝 7) C. 검색 주소 나누기**

블로그에서 검색한 뒤 주소창의 주소를 시크릿 창에 붙여 넣는다. 같은 결과가 보인다(시크릿 창은 비회원이라 비공개 글은 빠진다). 2쪽으로 간 뒤 뒤로 가기를 눌러 1쪽으로 돌아오는지도 본다.

## 8. 확인 문제

1. 일반 변수 대신 `useState`를 쓰는 이유는?
<details><summary>답</summary>일반 변수는 컴포넌트 함수가 다시 실행될 때마다 처음 값으로 돌아가고, 바꿔도 다시 그리기가 일어나지 않는다. 상태는 값을 기억하고, set 함수를 부르면 React가 다시 그린다.</details>

2. 폼 안의 "코드 받기" 버튼에 `type="button"`을 쓰지 않으면?
<details><summary>답</summary>폼 안의 버튼은 기본이 submit이라 누를 때마다 폼이 제출되어 가입 요청이 나간다.</details>

3. 가입이 실패해도 입력 칸이 비지 않는 이유는 코드로 무엇 때문인가?
<details><summary>답</summary>칸이 제어 컴포넌트라 값이 상태에 있고, 실패 처리에서 입력 상태를 지우지 않고 errors만 바꾸기 때문이다.</details>

4. 이메일을 바꾸면 `codeSent`, `verified`를 false로 되돌리는 이유는?
<details><summary>답</summary>인증은 이메일마다 따로라, 바뀐 이메일은 다시 코드를 받아 확인해야 한다. 화면이 이전 이메일의 "확인됨"을 계속 보여 주면 서버 규칙과 어긋난다.</details>

5. 글 목록 효과의 `active` 플래그는 무엇을 막나?
<details><summary>답</summary>페이지나 카테고리가 바뀐 뒤 늦게 도착한 이전 요청의 응답이 화면을 덮어쓰는 것을 막는다. 정리 함수에서 active=false로 만들어 그 응답을 버린다.</details>

6. 로그인 뒤 블로그 주소로 돌아갈 때 `navigate`가 아니라 `window.location.assign`을 쓰는 이유는?
<details><summary>답</summary>blog.test와 alpha.blog.test는 다른 호스트라 History API(navigate)로 이동할 수 없고, 브라우저가 그 주소를 새로 열어야 한다.</details>

7. `safeRedirect`가 `host.endsWith('.blog.test')`처럼 점을 붙여 비교하는 이유는?
<details><summary>답</summary>evilblog.test처럼 blog.test로 끝나는 남의 도메인을 우리 주소로 오인하지 않으려고. 점을 붙이면 진짜 하위 도메인만 맞는다.</details>

8. `ManagePage`의 403 화면("접근 권한이 없습니다")만으로 남의 블로그 설정을 막을 수 없는 이유는?
<details><summary>답</summary>화면 코드는 사용자가 바꾸거나 건너뛸 수 있고 API를 직접 부를 수 있다. 실제 검사는 서버의 BlogOwnerGuard가 401/403으로 한다.</details>

9. 댓글 내용 `<script>...</script>`가 사이드바에서 실행되지 않는 이유는?
<details><summary>답</summary>JSX의 {값}은 문자열을 HTML로 해석하지 않고 글자 그대로 넣기 때문이다(자동 이스케이프).</details>

10. `pagination.ts`와 `Pagination.tsx`가 함께 있을 때 TS1149가 난 이유는?
<details><summary>답</summary>macOS 파일 시스템은 대소문자를 구분하지 않아, 확장자를 뺀 import 경로 './pagination'과 '../../components/Pagination'이 같은 파일로 풀려 TypeScript가 대소문자만 다른 이름으로 같은 파일을 부른다고 막았다.</details>

11. (스텝 5) 글쓰기와 수정 라우트에 같은 `PostWritePage`를 쓰면서 `key="new"`, `key="edit"`를 준 이유는?
<details><summary>답</summary>React는 같은 자리에 같은 컴포넌트가 오면 재사용해 상태를 남긴다. 수정 화면에서 글쓰기로 옮겨 가도 이전 글의 제목·본문이 남는다. <code>key</code>가 다르면 다른 컴포넌트로 보고 새로 만들어 상태가 처음부터 시작한다.</details>

12. (스텝 5) `CategoriesPage`에서 `load`를 `useCallback`으로 감싸지 않으면 어떻게 되나?
<details><summary>답</summary>그릴 때마다 새 함수가 만들어져 <code>useEffect(..., [load])</code>가 매번 다시 실행된다. 불러오기 → <code>setTree</code> → 다시 그리기 → 또 불러오기가 끝없이 반복된다.</details>

13. (스텝 6) 등록 버튼을 `submitting` 상태로 꺼 두었는데도 빠른 두 번째 클릭이 요청을 또 보낸 이유와, `useRef`가 이를 막는 이유는?
<details><summary>답</summary><code>setSubmitting(true)</code>는 다음 그리기에서 반영되므로, 두 클릭이 같은 그리기 사이에 오면 두 번째 클릭 때도 버튼이 켜져 있고 <code>submitting</code>도 false다. <code>ref.current</code>는 바꾸는 즉시 바뀐 값이 읽혀서 두 번째 클릭이 <code>inFlight.current === true</code>를 보고 바로 돌아간다.</details>

14. (스텝 6) 서버는 댓글을 하나만 만들었는데 화면에 두 줄이 보인 이유는?
<details><summary>답</summary>같은 연타 방지 키라 서버는 두 번째 요청에 첫 응답(같은 댓글)을 그대로 돌려줬고, 화면은 두 응답을 모두 목록에 붙였다. 그래서 같은 <code>id</code>가 이미 있으면 붙이지 않는 확인을 더했다.</details>

15. (스텝 6) 글 상세의 화면 상태를 `{ status: ... }` 판별 유니온으로 둔 이점은?
<details><summary>답</summary><code>post</code>는 <code>'ok'</code>일 때만, <code>blogName</code>은 <code>'subscribersOnly'</code>일 때만 있어서, 상태를 확인하지 않고 글 제목을 그리려 하면 TypeScript가 막는다. 서버 응답(404, 403 SUBSCRIBERS_ONLY, 그 밖의 오류)을 화면 하나씩에 빠짐없이 대응시킬 수 있다.</details>

16. (스텝 7) 공감 버튼이 응답 전에 화면부터 바꾸는데도, 응답이 오면 다시 `setLiked(result.liked)`, `setCount(result.likeCount)`를 하는 이유는?
<details><summary>답</summary>화면이 바꾼 값은 추측이다. 그 사이 다른 사람이 공감했거나, 서버가 이미 켜져 있던 상태였다면 실제 값이 다르다. 서버가 돌려준 값이 진짜라서 그것으로 맞춘다.</details>

17. (스텝 7) 공감 API가 "토글(누를 때마다 뒤집기)"이 아니라 켜기 PUT·끄기 DELETE인 것이 낙관적 갱신에 왜 중요한가?
<details><summary>답</summary>요청이 중복되거나 재시도되어도 결과가 같다(멱등). 토글이면 같은 요청이 두 번 가면 켰다가 다시 꺼져서, 화면이 보여 준 상태와 서버 상태가 어긋난다.</details>

18. (스텝 7) `LikeButton`과 `Comments`에 같은 `key={post.id}`를 줬을 때 공감 버튼이 두 개 그려진 이유는? key를 왜 아예 빼지 않고 `like-${post.id}`로 바꿨나?
<details><summary>답</summary>같은 부모 아래 형제의 key가 같으면 React가 다시 그릴 때 어느 것이 어느 것인지 맞추지 못해 자식이 복제되거나 빠질 수 있다. key를 둔 목적은 글이 바뀌면 컴포넌트를 새로 만들어 <code>useState</code>의 처음 값(새 글의 공감 상태)으로 다시 시작하게 하는 것이라 빼지 않고, 형제끼리 겹치지 않게 접두어를 붙였다.</details>

19. (스텝 7) 검색 결과 화면이 검색어를 `useState`가 아니라 `useSearchParams`로 읽는 이점 세 가지는?
<details><summary>답</summary>결과 주소를 나누면 같은 결과가 보인다, 새로고침해도 검색어가 남는다, 뒤로 가기·앞으로 가기로 이전 검색·쪽으로 이동한다.</details>

20. (스텝 7) `uploadFile`이 `Content-Type` 머리글을 쓰지 않는 이유는?
<details><summary>답</summary>본문이 <code>FormData</code>면 브라우저가 파트 구분자(boundary)를 포함한 <code>multipart/form-data; boundary=...</code>를 붙인다. 직접 쓰면 boundary가 없어 서버가 파트를 나누지 못한다.</details>

## 9. 더 읽을거리

- React 공식 문서 react.dev: "State: A Component's Memory", "Reacting to Input with State", "Synchronizing with Effects", "You Might Not Need an Effect", "Reusing Logic with Custom Hooks"
- React 공식 문서: "Sharing State Between Components", 폼 요소(`<input>`, `<form>`) 레퍼런스
- React 공식 문서: "Referencing Values with Refs"(`useRef`), "Queueing a Series of State Updates", `StrictMode`
- React 공식 문서: "Rendering Lists"(key 규칙), "Preserving and Resetting State"(key로 컴포넌트 새로 만들기)
- MDN: `FormData`, "Using FormData Objects"
- React Router 공식 문서: `Routes`/`Route`(중첩·index), `NavLink`, `useParams`, `useSearchParams`, `useNavigate`
- TypeScript 핸드북: "Narrowing", "Discriminated unions"
- MDN: `Event.preventDefault()`, `HTMLFormElement` `novalidate`, `URLSearchParams`, `Location.assign()`, History API
- OWASP Cheat Sheet: "Unvalidated Redirects and Forwards"
- Vitest 공식 문서
- 화면 목업 signup, login, blog-create, blog-main, manage-settings
