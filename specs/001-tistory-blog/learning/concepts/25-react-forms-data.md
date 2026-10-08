# 25. React 폼과 데이터 불러오기

> 관련 스텝: [스텝 4](../step-04.md) (T026) · 관련 개념: [19-react-router-api-client](./19-react-router-api-client.md), [14-xss-sanitize-csp](./14-xss-sanitize-csp.md), [16-authorization-visibility](./16-authorization-visibility.md), [18-spa-server-routing](./18-spa-server-routing.md), [15-subdomain-host-routing](./15-subdomain-host-routing.md)

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
- `*`: 아직 없는 관리 화면(글쓰기는 스텝 5)은 "준비 중"을 보여 준다.

페이지 번호는 주소의 쿼리 `?page=2`에 둔다.

```tsx
const [params] = useSearchParams()
const page = Math.max(Number(params.get('page')) || 1, 1)
```

- 상태가 아니라 **주소**에 두는 이유: 새로고침해도, 링크를 공유해도 같은 페이지가 열린다. 뒤로 가기도 페이지별로 된다.
- `Number(null)`은 `0`, `Number('abc')`는 `NaN`이라 `|| 1`로 1이 된다. `Math.max(..., 1)`로 0 이하를 막는다.

### 5.7 화면의 권한 검사는 안내용

`ManagePage`는 `blog.viewer.isOwner`가 `false`면 "권한이 없습니다"를 그린다. 그렇다고 이게 보안은 아니다. 브라우저 개발자 도구로 코드를 바꾸거나 `curl`로 `PATCH /api/blog`를 직접 부를 수 있다. **진짜 검사는 서버**(`BlogOwnerGuard.requireOwner` → 401/403)가 한다(헌법 원칙 IV, [16](./16-authorization-visibility.md)). 화면 검사는 주인이 아닌 사람에게 쓸모없는 버튼을 보여 주지 않는 **친절**이다.

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

8. `ManagePage`의 "권한이 없습니다" 화면만으로 남의 블로그 설정을 막을 수 없는 이유는?
<details><summary>답</summary>화면 코드는 사용자가 바꾸거나 건너뛸 수 있고 API를 직접 부를 수 있다. 실제 검사는 서버의 BlogOwnerGuard가 401/403으로 한다.</details>

9. 댓글 내용 `<script>...</script>`가 사이드바에서 실행되지 않는 이유는?
<details><summary>답</summary>JSX의 {값}은 문자열을 HTML로 해석하지 않고 글자 그대로 넣기 때문이다(자동 이스케이프).</details>

10. `pagination.ts`와 `Pagination.tsx`가 함께 있을 때 TS1149가 난 이유는?
<details><summary>답</summary>macOS 파일 시스템은 대소문자를 구분하지 않아, 확장자를 뺀 import 경로 './pagination'과 '../../components/Pagination'이 같은 파일로 풀려 TypeScript가 대소문자만 다른 이름으로 같은 파일을 부른다고 막았다.</details>

## 9. 더 읽을거리

- React 공식 문서 react.dev: "State: A Component's Memory", "Reacting to Input with State", "Synchronizing with Effects", "You Might Not Need an Effect", "Reusing Logic with Custom Hooks"
- React 공식 문서: "Sharing State Between Components", 폼 요소(`<input>`, `<form>`) 레퍼런스
- React Router 공식 문서: `Routes`/`Route`(중첩·index), `NavLink`, `useParams`, `useSearchParams`, `useNavigate`
- TypeScript 핸드북: "Narrowing", "Discriminated unions"
- MDN: `Event.preventDefault()`, `HTMLFormElement` `novalidate`, `URLSearchParams`, `Location.assign()`, History API
- OWASP Cheat Sheet: "Unvalidated Redirects and Forwards"
- Vitest 공식 문서
- 화면 목업 signup, login, blog-create, blog-main, manage-settings
