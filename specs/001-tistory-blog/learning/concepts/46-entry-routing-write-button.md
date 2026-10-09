# 상태에 따라 갈 곳 정하기: 글쓰기 버튼

> 스텝 12(T061, AUTH-04)에서 썼다. React 화면 기초는 [19 React Router와 API 클라이언트](./19-react-router-api-client.md), Thymeleaf와 비교는 [28 Thymeleaf에서 React로](./28-thymeleaf-to-react.md)를 먼저 보면 좋다.

## 1. 이 문서로 배우는 것

- 같은 버튼이 사용자 상태(블로그가 있나)에 따라 다른 곳으로 가게 하는 법
- "갈 곳 정하기"를 화면마다 따로 쓰지 않고 함수 하나에 모으는 이유와, 그 함수를 단위 테스트하는 법
- 같은 앱 안 이동(`<Link>`)과 다른 호스트로 이동(`<a href>`)의 차이
- 사용자의 "하려던 일"을 다음 화면에 넘기는 법(`?from=write`)과, 그것이 열린 리다이렉트가 되지 않게 하는 법
- 버튼을 숨기거나 바꾸는 것은 편의일 뿐, 권한은 서버가 지킨다는 것

## 2. 왜 필요한가

명세 AUTH-04: "블로그가 없는 회원이 글쓰기를 누르면 블로그 개설로, 블로그가 있으면 대표 블로그의 글쓰기로 간다."

가입한 사람이 가장 먼저 하고 싶은 일은 글쓰기다. 그런데 이 서비스에서 글은 블로그 안에 산다(`{주소}.blog.com/manage/write`). 블로그가 없으면 글을 쓸 곳이 없다.

버튼이 없거나, 눌렀는데 404가 나오면 사용자는 길을 잃는다. 그래서 버튼은 늘 보이고, 누르면 **지금 그 사람이 할 수 있는 다음 단계**로 데려간다.

- 블로그가 있다 → 바로 글쓰기
- 블로그가 없다 → "먼저 블로그가 필요합니다" 안내와 함께 개설 화면 → 만들면 바로 글쓰기

스텝 11까지는 블로그 주인이 자기 블로그에 있을 때만 글쓰기 버튼이 있었다. 플랫폼 홈에는 없었다.

## 3. 기본 개념

### 3.1 Thymeleaf로 하면

서버가 HTML을 만드는 방식이라면 이렇게 쓸 것이다.

```html
<a th:if="${me.primaryBlog != null}"
   th:href="|//${me.primaryBlog.address}.blog.com/manage/write|">글쓰기</a>
<a th:unless="${me.primaryBlog != null}" th:href="@{/blogs/new(from='write')}">글쓰기</a>
```

React도 같다. 다른 점은 판단을 **브라우저에서** 한다는 것뿐이다. 화면이 열릴 때 `GET /api/me`로 받은 `Me`의 `primaryBlog`를 보고 주소를 정한다.

### 3.2 판단을 한 곳에

글쓰기 버튼은 여러 군데 있다: 플랫폼 머리글, 남의 블로그 머리글, 앞으로 마이페이지·홈 사이드바에도 생길 수 있다. 버튼마다 `primaryBlog ? ... : ...`를 쓰면, 규칙이 바뀔 때(예: 대표 블로그가 닫혀 있으면 다른 블로그로) 모두 찾아 고쳐야 한다.

그래서 **"어디로 가나"를 계산하는 순수 함수** 하나를 둔다.

- 입력: `Me`(의 `primaryBlog`)
- 출력: 주소 문자열
- 화면 그리기, 네트워크, 상태가 없다 → 단위 테스트가 쉽다

### 3.3 `<Link>`와 `<a href>`

[19](./19-react-router-api-client.md) 3.2에서 봤듯이 `<Link to="/x">`는 페이지를 새로 받지 않고 같은 앱 안에서 화면만 바꾼다(History API). 그런데 이것은 **같은 호스트 안**에서만 된다.

| 지금 위치 | 갈 곳 | 쓸 것 |
| --- | --- | --- |
| `blog.test` | `blog.test/blogs/new` | `<Link to="/blogs/new">` (화면만 바꿈) |
| `blog.test` | `alpha.blog.test/manage/write` | 다른 호스트라 페이지를 새로 받아야 함 → 전체 주소 |
| `beta.blog.test` (남의 블로그) | `blog.test/blogs/new` | 다른 호스트 → 전체 주소 |

`<Link to="/manage/write">`처럼 경로만 주면 **지금 호스트** 기준이다. 플랫폼(`blog.test`)에서 누르면 `blog.test/manage/write`로 가는데, 플랫폼에는 그런 화면이 없다. 다른 호스트로 가려면 `http://alpha.blog.test:8080/...` 같은 전체 주소가 필요하다. React Router 7의 `<Link>`는 다른 출처의 전체 주소를 받으면 보통 링크처럼 페이지를 새로 받게 해 주지만, 이 프로젝트는 "호스트를 넘는 이동"이 코드에서 바로 보이도록 다른 호스트로 갈 때는 `<a href>`를 쓴다(스텝 3부터의 규칙, `blogUrl`·`platformUrl`과 함께).

글쓰기 버튼은 플랫폼에서도 블로그에서도 누르므로, 갈 곳을 **전체 주소**(`http://alpha.blog.test:8080/manage/write`)로 만들고 `<a href>`로 쓴다. 그러면 어디서 눌러도 같은 곳으로 간다.

다른 호스트로 가도 로그인이 유지되는 것은 쿠키가 `Domain=.blog.test`이기 때문이다([10 HTTP 쿠키](./10-http-cookies.md) 3.4).

### 3.4 하려던 일을 넘기기

블로그가 없어 개설 화면으로 보냈으면, 개설 화면은 두 가지를 알아야 한다.

1. 사용자가 **글을 쓰려다** 왔다 → "먼저 블로그가 필요합니다" 안내
2. 만들고 나면 → 관리 화면이 아니라 **글쓰기**로

이 정보는 주소의 쿼리로 넘긴다: `/blogs/new?from=write`. 주소에 있으니 새로 고쳐도 남고, 서버에 저장할 것도 없다.

**왜 `?redirect=http://...` 같은 주소가 아니라 `from=write`인가.** 갈 주소를 쿼리로 받으면 누군가 `?redirect=https://나쁜곳`을 넣은 링크를 퍼뜨릴 수 있다(열린 리다이렉트, [21](./21-signup-login.md)). 로그인 화면은 그래서 `safeRedirect`로 우리 주소만 허용한다. 여기서는 아예 주소를 받지 않고 **정해 둔 값 하나**(`write`)만 알아듣는다. 만든 뒤 갈 곳은 개설 화면이 방금 만든 블로그 주소로 직접 만든다. 받을 것이 적으면 검사할 것도 적다.

### 3.5 버튼은 편의, 권한은 서버

버튼이 `alpha.blog.test/manage/write`로 보내 준다고 해서, 그곳에서 글을 쓸 수 있는 것은 버튼 덕이 아니다. 누군가 주소창에 남의 블로그 `/manage/write`를 직접 쳐도, 관리 화면은 서버가 준 `blog.viewer.isOwner`를 보고 403 안내를 그리고, 그것을 우회해 글 발행 API(`POST /api/posts`, 블로그는 Host로 정함)를 직접 불러도 `BlogOwnerGuard.requireOwner`가 서버에서 막는다([16 인가와 가시성](./16-authorization-visibility.md)). 화면의 분기는 **길 안내**이고 **문**은 서버에 있다.

## 4. 동작 원리

```
화면이 열림 → useMe(): GET /api/me
  비회원(401)          → 머리글: 로그인·회원가입 (글쓰기 없음)
  회원, primaryBlog 있음 → 글쓰기 href = http://alpha.blog.test:8080/manage/write
  회원, primaryBlog 없음 → 글쓰기 href = http://blog.test:8080/blogs/new?from=write

블로그 없는 회원이 글쓰기 클릭
  → blog.test/blogs/new?from=write
     BlogCreatePage: from === 'write' → 안내 상자
     만들기 → POST /api/blogs → 201 Blog{address: 'gamma'}
     → window.location.assign(http://gamma.blog.test:8080/manage/write)
  → gamma.blog.test/manage/write : 글쓰기 화면
     (가입 직후 첫 블로그라 대표 블로그도 gamma. 다음부터 글쓰기는 바로 여기로)
```

블로그 주인이 **자기** 블로그에서 누르는 글쓰기는 그대로 그 블로그의 글쓰기다(`<Link to="/manage/write">`). 블로그를 여러 개 가진 사람이 대표가 아닌 블로그를 보고 있을 때, 그 블로그에 쓰려는 것이 자연스럽기 때문이다. **남의** 블로그에서 누르면 내 대표 블로그로 간다.

## 5. 이 프로젝트에서는

### 5.1 `frontend/src/app/writeLink.ts`

```ts
// 글쓰기 버튼이 갈 곳 (AUTH-04). 플랫폼 주소와 블로그 주소 어디서 눌러도 같은 곳으로 가도록 전체 주소를 만든다

import type { Me } from '../api/types'
import { blogUrl, platformUrl } from './host'

/** 블로그 개설 화면에 글쓰기에서 왔다고 알리는 값. 개설 화면이 안내 문구를 띄우고, 만든 뒤 바로 글쓰기로 보낸다. */
export const FROM_WRITE = 'write'

/** 대표 블로그가 있으면 그 블로그의 글쓰기, 없으면 블로그 개설(안내 포함). */
export function writeUrl(me: Pick<Me, 'primaryBlog'>, location: Location = window.location): string {
  if (me.primaryBlog) {
    return blogUrl(me.primaryBlog.address, '/manage/write', location)
  }
  return platformUrl(`/blogs/new?from=${FROM_WRITE}`, location)
}
```

- `FROM_WRITE`: 보내는 쪽(`writeUrl`)과 받는 쪽(`BlogCreatePage`)이 같은 상수를 쓴다. 한쪽만 `'writing'`으로 바뀌는 실수를 막는다.
- `Pick<Me, 'primaryBlog'>`: TypeScript 타입 도구. `Me`에서 `primaryBlog` 칸만 뽑은 타입이다. 이 함수는 그 칸만 보므로, 테스트에서 `Me` 전체(닉네임, 이메일…)를 만들 필요 없이 `{ primaryBlog: null }`만 넘기면 된다.
- `location` 인자: 기본값은 브라우저의 `window.location`. 테스트에서는 가짜 `{ protocol, port }`를 넘겨 "8080 포트에서 열었을 때"를 흉내 낸다. `host.ts`의 `blogUrl`·`platformUrl`과 같은 방식이다.
- `blogUrl`·`platformUrl`은 지금 주소의 프로토콜과 포트를 유지한다. 개발 서버(5173)에서 열면 5173으로, jar(8080)로 열면 8080으로 간다.

### 5.2 `frontend/src/app/writeLink.test.ts`

```ts
describe('writeUrl (AUTH-04)', () => {
  const location = { protocol: 'http:', port: '8080' } as Location

  it('대표 블로그가 있으면 그 블로그의 글쓰기로 간다', () => {
    const me = { primaryBlog: { id: 1, address: 'alpha', name: '알파' } }
    expect(writeUrl(me, location)).toBe('http://alpha.blog.test:8080/manage/write')
  })

  it('블로그가 없으면 글쓰기에서 왔다는 표시와 함께 블로그 개설로 간다', () => {
    expect(writeUrl({ primaryBlog: null }, location)).toBe('http://blog.test:8080/blogs/new?from=write')
  })
})
```

명세 문장 두 개가 테스트 두 개가 됐다. 화면을 띄우지 않고 1밀리초 안에 돈다. 판단을 함수로 빼낸 덕이다.

### 5.3 머리글: `PlatformHeader.tsx`, `BlogHeader.tsx`

```tsx
{me.status === 'member' && (
  <div className="row">
    <a className="btn primary" href={writeUrl(me.me)}>글쓰기</a>
    {me.me.primaryBlog
      ? <a className="btn" href={blogUrl(me.me.primaryBlog.address)}>내 블로그</a>
      : <Link className="btn" to="/blogs/new">블로그 만들기</Link>}
```

- 글쓰기가 가장 자주 하는 일이라 강조 버튼(`primary`)이고, 내 블로그·블로그 만들기는 보통 버튼으로 내렸다.
- "블로그 만들기"는 같은 호스트(플랫폼) 안 이동이라 `<Link>`, 글쓰기는 다른 호스트일 수 있어 `<a href>`.

```tsx
{blog.viewer.isOwner
  ? <Link className="btn primary" to="/manage/write">글쓰기</Link>
  : <a className="btn primary" href={writeUrl(me.me)}>글쓰기</a>}
```

- `blog.viewer.isOwner`: 블로그 정보 API가 "지금 보는 사람이 주인인가"를 알려 준다. 서버가 판단한 값이다.
- 주인이면 이 블로그의 글쓰기(같은 호스트라 `<Link>`). 아니면 내 대표 블로그(또는 개설).

### 5.4 개설 화면: `pages/blog/BlogCreatePage.tsx`

```tsx
const [params] = useSearchParams()
const fromWrite = params.get('from') === FROM_WRITE
...
window.location.assign(blogUrl(blog.address, fromWrite ? '/manage/write' : '/manage'))
...
{fromWrite && (
  <div className="box" role="status">
    <b>글을 쓰려면 먼저 블로그가 필요합니다</b>
    <span className="small">블로그를 만들면 바로 글쓰기 화면으로 이어집니다.</span>
  </div>
)}
```

- `useSearchParams`: React Router의 훅. 주소의 `?from=write`를 읽는다. Thymeleaf의 `${param.from}`과 같다.
- `=== FROM_WRITE`: 정해 둔 값과 같을 때만 참. 다른 값이나 없으면 평소 개설 화면(만든 뒤 관리 화면).
- 만든 뒤 갈 곳은 쿼리에서 받지 않고 **방금 만든 블로그 주소**로 직접 만든다(3.4).
- `role="status"`: 화면 낭독기에 "알림 문구"라고 알려 준다.

가입 직후에는 `SignupPage`가 이미 `/blogs/new`로 보낸다(스텝 4). 그래서 "가입 → 블로그 만들기"와 "글쓰기 → 블로그 만들기 → 글쓰기" 두 길이 모두 개설 화면을 지난다.

### 5.5 서버 쪽은 바뀐 것이 없다

판단 재료인 `Me.primaryBlog`는 스텝 4부터 있다(`SignupIntegrationTest`: 가입 직후 없음, `BlogCreateIntegrationTest`: 첫 블로그를 만들면 그것이 대표). API 명세 `Me` 설명에도 "`primaryBlog`가 `null`이면 글쓰기 버튼이 블로그 개설로 간다(AUTH-04)"라고 적혀 있다. 기능 하나가 화면만으로 끝나는 경우도 있다. 대신 판단에 쓰는 값은 서버가 주고, 서버가 테스트한다.

## 6. 자주 하는 실수와 함정

- **경로만 쓴 `<Link>`로 다른 블로그에 가려 함**: 플랫폼에서 `<Link to="/manage/write">`는 `blog.test/manage/write`(없는 화면)로 간다. 경로는 지금 호스트 기준이다. 호스트가 바뀌면 전체 주소(`blogUrl`)와 `<a href>`.
- **버튼마다 판단 복사**: 3.2. 규칙이 바뀌면 한 곳만 고쳐진다.
- **쿼리로 갈 주소 받기**: `?next=` 같은 것을 그대로 `location.assign`하면 열린 리다이렉트. 정해 둔 값만 알아듣거나, 우리 주소인지 검사한다(`safeRedirect`).
- **버튼을 숨기면 안전하다고 생각**: 숨긴 버튼의 주소는 누구나 칠 수 있다. 서버 권한 검사가 진짜다.
- **`Me` 전체를 받는 함수**: 테스트할 때마다 가짜 회원 전체를 만들어야 한다. 필요한 칸만 받는 타입(`Pick`)이 테스트를 가볍게 한다.

## 7. 직접 해 보기

### 7.1 블로그 없는 회원

```bash
./scripts/build-frontend.sh && ./mvnw spring-boot:run
```

1. `http://blog.test:8080/signup`에서 새로 가입한다. 가입 뒤 개설 화면으로 오지만, 만들지 말고 머리글의 `blog` 로고로 홈에 간다.
2. 머리글에 **글쓰기**와 **블로그 만들기**가 보인다. 글쓰기에 마우스를 올려 브라우저 왼쪽 아래 주소가 `.../blogs/new?from=write`인지 본다.
3. 누르면 "글을 쓰려면 먼저 블로그가 필요합니다" 상자가 있는 개설 화면. 주소·이름을 넣고 만든다.
4. `{주소}.blog.test:8080/manage/write` 글쓰기 화면으로 바로 간다.
5. 홈으로 돌아와 글쓰기에 마우스를 올리면 이제 `{주소}.blog.test:8080/manage/write`.

### 7.2 남의 블로그에서

다른 회원의 블로그(`{다른주소}.blog.test:8080`)를 연다. 머리글의 글쓰기는 그 블로그가 아니라 **내** 대표 블로그의 글쓰기다. 관리 버튼은 없다.

### 7.3 문은 서버에

남의 블로그 `{다른주소}.blog.test:8080/manage/write`를 주소창에 직접 친다. 관리 화면은 "블로그 주인만 볼 수 있습니다"(403)를 그린다. 화면을 건너뛰고 API를 직접 불러도 서버가 막는다: 그 블로그 주소에서 개발자 도구 Console로

```js
await fetch('/api/posts', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest', 'Idempotency-Key': crypto.randomUUID() }, body: '{}' }).then(r => r.status)
```

403(주인 아님)이 나온다. 주인 검사가 입력 검사보다 먼저라 본문이 비어 있어도 400이 아니다.

### 7.4 테스트

```bash
cd frontend && npx vitest run src/app/writeLink.test.ts
```

`writeLink.ts`에서 `FROM_WRITE`를 `'writing'`으로 바꾸고 다시 돌리면 무엇이 실패하나? 개설 화면은 같은 상수를 쓰므로 함께 바뀌어 동작은 그대로다(테스트의 기대 주소만 다르다). 상수를 쓰지 않고 양쪽에 `'write'`를 따로 적었다면 어떻게 됐을지 생각해 본다. 끝나면 `git restore .`.

## 8. 확인 문제

1. 플랫폼 머리글에서 "블로그 만들기"는 `<Link>`인데 "글쓰기"는 `<a href>`인 이유는?

<details><summary>답</summary>

블로그 만들기(`/blogs/new`)는 같은 호스트(플랫폼) 안 이동이라 `<Link>`로 화면만 바꿀 수 있다. 글쓰기는 블로그가 있으면 `{주소}.blog.test`라는 다른 호스트로 가므로 페이지를 새로 받아야 하고, 경로만 주는 `<Link to="/manage/write">`로는 플랫폼 안의 없는 화면으로 가 버린다. 그래서 전체 주소를 만들어 `<a href>`로 쓴다.

</details>

2. 개설 화면이 "만든 뒤 갈 곳"을 `?next=http://...`로 받지 않고 `?from=write`만 받는 이유는?

<details><summary>답</summary>

갈 주소를 쿼리로 받으면 다른 사이트 주소를 넣은 링크로 사용자를 보낼 수 있다(열린 리다이렉트). 정해 둔 값 하나만 알아듣고, 갈 주소는 방금 만든 블로그 주소로 화면이 직접 만들면 검사할 것이 없다.

</details>

3. 블로그 두 개(`alpha` 대표, `beta`)를 가진 회원이 `beta.blog.test`를 보다가 글쓰기를 누르면 어디로 가나? 남의 블로그 `gamma.blog.test`에서 누르면?

<details><summary>답</summary>

`beta`에서는 자기 블로그라 `beta`의 글쓰기(`/manage/write`). `gamma`에서는 주인이 아니라 대표 블로그 `alpha`의 글쓰기.

</details>

4. 머리글에서 글쓰기 버튼을 아예 빼 버리면, 블로그 없는 회원이 남의 블로그 `/manage/write`에 들어가 글을 쓸 수 있게 되나?

<details><summary>답</summary>

아니다. 버튼은 길 안내일 뿐이고, 글 발행 API가 서버에서 블로그 주인인지 확인한다(`BlogOwnerGuard`). 버튼이 있든 없든 서버가 막는다.

</details>

5. `writeUrl`이 `me: Me`가 아니라 `me: Pick<Me, 'primaryBlog'>`를 받아서 좋은 점은?

<details><summary>답</summary>

함수가 실제로 쓰는 칸만 요구하므로 테스트에서 `{ primaryBlog: null }`처럼 작게 넘길 수 있다. 또 함수가 다른 칸(닉네임 등)에 기대지 않는다는 것이 타입에 드러난다.

</details>

## 9. 더 읽을거리

- React Router, [useSearchParams](https://reactrouter.com/api/hooks/useSearchParams), [Link](https://reactrouter.com/api/components/Link)
- TypeScript Handbook, [Utility Types: `Pick`](https://www.typescriptlang.org/docs/handbook/utility-types.html#picktype-keys)
- OWASP, [Unvalidated Redirects and Forwards Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Unvalidated_Redirects_and_Forwards_Cheat_Sheet.html)
- 이 저장소: [19 React Router와 API 클라이언트](./19-react-router-api-client.md) 5.1 `host.ts`, [21 가입·로그인](./21-signup-login.md)의 열린 리다이렉트, [16 인가와 가시성](./16-authorization-visibility.md)
