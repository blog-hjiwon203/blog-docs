# 44. 휴대폰 화면: 반응형 CSS와 헤드리스 Chrome으로 점검하기

> 관련 스텝: [스텝 11](../step-11.md) (T071) · 관련 개념: [28-thymeleaf-to-react](./28-thymeleaf-to-react.md), [37-filtered-list-bulk-actions](./37-filtered-list-bulk-actions.md), [19-react-router-api-client](./19-react-router-api-client.md)

## 1. 이 문서로 배우는 것

- **반응형(responsive)** 화면: 같은 HTML이 화면 폭에 따라 다르게 배치되는 것
- `<meta name="viewport">`가 하는 일과, 없으면 휴대폰에서 생기는 일
- **미디어 쿼리** `@media (max-width: 760px)`, 이 프로젝트의 기준 폭
- 휴대폰에서 자주 깨지는 것: 넘치는 긴 낱말·주소·코드, **표**
- 표를 좁은 화면에서 **카드로 바꾸는** 법(`data-label`과 `::before`)
- 사람이 눈으로 보기 전에 **기계로 먼저 재기**: 헤드리스 Chrome + DevTools 프로토콜(CDP)로 360px 화면을 열어 가로 넘침을 재고 스크린숏 남기기
- "넘침 없음"과 "보기 좋음"은 다르다: 스크린숏을 직접 봐야 찾은 문제

**먼저 알면 좋은 것**: CSS 기본(박스, flex, grid), React 화면 구조([28](./28-thymeleaf-to-react.md)), 내 글 관리 화면([37](./37-filtered-list-bulk-actions.md) 5.7).

## 2. 왜 필요한가

비기능 요구 "반응형: 휴대폰(360px)에서도 쓸 수 있다"(T071). 블로그는 휴대폰으로 읽는 사람이 많다. 360px은 흔한 안드로이드 휴대폰의 CSS 폭이다(실제 픽셀은 더 많지만, 기기가 화면 배율로 나눠 CSS에서는 360px로 보인다).

PC에서만 만들고 확인하면 휴대폰에서 이런 일이 생긴다.

- 화면이 옆으로 밀려 **가로 스크롤**이 생긴다(긴 주소·코드·넓은 사진 때문에).
- 칸이 좁아 글자가 한 글자씩 세로로 쌓인다.
- 버튼이 화면 밖으로 나가 누를 수 없다.

## 3. 기본 개념

### 3.1 viewport 메타 태그

```html
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
```

이것이 없으면 휴대폰 브라우저는 "PC용 페이지겠지" 하고 화면을 980px쯤으로 그린 뒤 **통째로 축소**해 보여 준다. 글자가 깨알만 해지고, 미디어 쿼리도 980px 기준으로 동작한다. `width=device-width`는 "기기 폭(360px)을 그대로 CSS 폭으로 써라"는 뜻이다. Vite로 만든 이 프로젝트의 `index.html`에는 처음부터 들어 있다.

### 3.2 미디어 쿼리

```css
.cols { display: grid; grid-template-columns: minmax(0, 1fr) 260px; gap: 24px; }
@media (max-width: 760px) { .cols { grid-template-columns: minmax(0, 1fr); } }
```

`@media (max-width: 760px)`: 화면 폭이 760px **이하**일 때만 안의 규칙을 적용한다. 이 프로젝트는 760px을 기준으로 PC(본문 + 오른쪽 사이드바 2칸)와 휴대폰(1칸, 사이드바는 본문 아래)을 나눈다. 목업(`mockups/assets/mock.css`)에서 정한 값이다.

`minmax(0, 1fr)`의 `0`이 중요하다. 그냥 `1fr`이면 칸의 최소 폭이 "안의 내용이 가장 넓은 만큼"이라, 긴 코드 한 줄이 칸을 화면보다 넓게 밀어낸다. 최소를 0으로 두면 칸은 화면 폭을 지키고, 넘치는 내용은 그 안에서 처리된다.

### 3.3 넘치는 내용 다루기

| 내용 | 처리 | 이 프로젝트 |
| --- | --- | --- |
| 긴 낱말·주소(띄어쓰기 없음) | 줄 중간에서 끊기 | `.prose { overflow-wrap: anywhere }` |
| 코드 블록 | 줄을 바꾸지 않고 상자 안에서 가로 스크롤 | `.prose pre { overflow-x: auto }` |
| 큰 사진 | 폭에 맞춰 줄이기 | `.prose img { max-width: 100%; height: auto }` |
| 탭 줄(주제 탭, 관리 메뉴) | 한 줄로 두고 가로로 밀기 | `.tabs`, 좁은 화면의 `.manage-nav`에 `overflow-x: auto` |
| 표 | 상자 안 가로 스크롤(`.table-wrap { overflow-x: auto }`) 또는 **카드로 바꾸기** | 3.4 |

"상자 안 가로 스크롤"은 괜찮다. 문제는 **페이지 전체**가 옆으로 밀리는 것이다.

### 3.4 표를 카드로

표는 칸 수가 고정이라 좁은 화면에 약하다. 칸을 줄일 수 없으면 브라우저는 각 칸을 최대한 좁혀, 긴 제목 칸이 한 글자 폭이 된다. 두 가지 길이 있다.

1. 표에 최소 폭을 주고 상자 안에서 가로로 밀게 하기: 쉽지만 휴대폰에서 옆으로 밀며 보는 것은 불편하다.
2. **좁은 화면에서는 행마다 카드로**: 머리줄을 숨기고, 각 칸 앞에 이름표를 붙여 위아래로 쌓는다.

```css
@media (max-width: 760px) {
  .manage-table thead { display: none; }                          /* 머리줄 숨김 */
  .manage-table tr { display: grid; grid-template-columns: 28px minmax(0, 1fr); }   /* 행 = 카드 */
  .manage-table td.pick { grid-row: span 5; }                     /* 체크박스는 왼쪽 세로 한 칸 */
  .manage-table td[data-label]::before { content: attr(data-label) " · "; }        /* "상태 · " 이름표 */
}
```

- `display: grid`로 바꾸면 `<tr>`은 더 이상 표의 줄이 아니라 격자 상자가 된다. `<td>`는 그 안의 칸.
- `attr(data-label)`: HTML 속성 값을 CSS 글자로 꺼낸다. `<td data-label="상태">`면 앞에 "상태 · "가 붙는다. 머리줄이 숨어도 무슨 값인지 알 수 있다.
- HTML은 하나이고 CSS만 다르다. PC에서는 그대로 표다.

## 4. 동작 원리: 기계로 먼저 재기

화면이 열몇 개라 하나씩 휴대폰으로 열어 보는 것은 느리고 빠뜨리기 쉽다. 스텝 11에서는 **헤드리스 Chrome**(창 없이 도는 Chrome)을 프로그램으로 조종했다.

```
1. Chrome을 --headless --remote-debugging-port=9333으로 띄운다
2. Node 스크립트가 DevTools 프로토콜(CDP, WebSocket)로 붙는다
3. Emulation.setDeviceMetricsOverride { width: 360, height: 800, deviceScaleFactor: 2, mobile: true }
   + 안드로이드 휴대폰 User-Agent                                   ← 휴대폰처럼 보이게
4. 로그인이 필요한 화면은 Network.setCookie로 로그인 쿠키를 넣는다(Domain=.blog.test)
5. 화면마다 Page.navigate → 로드 + 1.5초(React가 API를 불러 그릴 시간)
6. Runtime.evaluate로 재기:
     document.documentElement.scrollWidth > clientWidth 면 페이지가 옆으로 밀린 것
     화면 오른쪽 끝을 넘는 요소 중, 가로 스크롤 상자(overflow-x: auto) 안에 있지 않은 것을 목록으로
7. Page.captureScreenshot { captureBeyondViewport: true }로 긴 스크린숏 저장
```

재는 코드의 핵심:

```js
const w = document.documentElement.clientWidth
for (const el of document.querySelectorAll('body *')) {
  const r = el.getBoundingClientRect()
  if (r.width > 0 && r.right > w + 1) {
    // 조상 중에 overflow-x가 auto/scroll/hidden인 상자가 있으면 그 안의 일이라 괜찮다
    ...
  }
}
```

- `getBoundingClientRect()`: 요소가 화면 어디에 그려졌는지(왼쪽·오른쪽 끝). 오른쪽 끝이 화면 폭을 넘으면 넘친 것.
- 코드 블록이나 탭 줄처럼 **일부러 가로로 밀게 만든 상자** 안의 요소는 빼야 거짓 경보가 없다.

이 스크립트는 지원의 컴퓨터 임시 폴더에서 돌렸고 코드 저장소에는 넣지 않았다(Chrome 경로·포트에 기대는 확인용 도구라서).

## 5. 이 프로젝트에서는

### 5.1 확인한 화면과 결과

확인용 회원·블로그를 만들고, 일부러 **나쁜 경우**를 넣은 글 3개를 썼다: 아주 긴 제목, 띄어쓰기 없는 긴 낱말, 200자 코드 한 줄, 1600px 넓은 사진, 120자 주소, 긴 카테고리·태그 이름, 긴 댓글.

| 화면 | 가로 넘침 | 눈으로 본 결과 |
| --- | --- | --- |
| 홈, 로그인, 가입, 마이페이지, 블로그 만들기 | 없음 | 괜찮음(주제 탭은 가로로 밀기, 인기 글 제목은 말줄임) |
| 블로그 메인, 태그·검색 목록 | 없음 | 괜찮음(사이드바가 본문 아래로) |
| 글 상세(비회원·주인), 404 | 없음 | 괜찮음(코드는 상자 안 스크롤, 긴 낱말·주소는 줄바꿈, 비슷한 글 카드 2열) |
| 관리 홈·글쓰기·카테고리·블로그 설정 | 없음 | 괜찮음 |
| **내 글 관리** | 없음 | **깨짐**: 표가 상자 안에 있어 넘침은 없었지만, 제목 칸이 한 글자 폭으로 눌려 세로로 길게 늘어짐 |

16개 화면 모두 "가로 넘침 없음"이었는데도 내 글 관리는 쓸 수 없는 모양이었다. **기계 측정은 "옆으로 밀리나"만 알려 준다.** 스크린숏을 직접 봐서 찾았다.

### 5.2 고친 것: `pages/manage/ManagePostsPage.tsx`와 `index.css`

```tsx
<table className="manage-table">
...
<td className="pick"><input type="checkbox" ... /></td>
<td className="title">...</td>
<td data-label="상태">...</td>
<td data-label="공개">{VISIBILITY_LABEL[post.visibility]}</td>
<td data-label="카테고리">{post.category?.name ?? '미분류'}</td>
<td className="num" data-label="날짜">{date}</td>
```

CSS는 3.4와 같다. 고친 뒤 다시 재고 스크린숏을 보니, 글마다 "체크박스 | 제목", 그 아래 "상태 · 발행 / 공개 · 공개 / 카테고리 · … / 날짜 · …" 카드로 보였다.

머리줄을 숨기면서 머리줄의 "이 페이지 모두 선택" 체크박스도 사라졌다. 좁은 화면에서만 보이는 "모두" 체크박스를 위쪽 도구 줄에 더했다.

```css
.mobile-only { display: none; }
@media (max-width: 760px) { .mobile-only { display: inline-flex; } }
```

PC에서는 머리줄에 있으니 두 개가 보이지 않게 숨긴다.

## 6. 자주 하는 실수와 함정

- **viewport 메타 태그가 없다.** 휴대폰이 PC 폭으로 그리고 축소한다.
- **grid 칸을 `1fr`로만 둔다.** 긴 내용이 칸을 밀어 페이지가 옆으로 넘친다. `minmax(0, 1fr)`.
- **긴 낱말·주소·코드를 생각하지 않는다.** 실제 글에는 꼭 나온다. 시험 글에 일부러 넣는다.
- **표를 그대로 둔다.** 칸이 한 글자 폭으로 눌린다. 카드로 바꾸거나 가로 스크롤 상자에 넣는다.
- **숨긴 요소에 있던 기능을 잊는다.** 머리줄의 "모두 선택"처럼 같이 사라진다.
- **기계 측정만 믿는다.** 넘침은 없어도 보기 나쁠 수 있다. 스크린숏을 본다.
- **PC 브라우저 창을 좁히는 것으로만 확인한다.** 휴대폰 User-Agent·터치·배율이 다르다. 개발자 도구의 기기 모드나 실제 휴대폰으로도 본다.

## 7. 직접 해 보기

1. Chrome에서 블로그를 열고 개발자 도구 → 기기 툴바(Cmd+Shift+M) → 폭 360으로 맞춘다. 홈, 글 상세, `/manage/posts`를 본다.
2. `index.css`의 `@media (max-width: 760px) { .manage-table ... }` 블록을 지우고 다시 빌드해서 내 글 관리가 어떻게 깨지는지 본다. 끝나면 되돌린다.
3. 콘솔에서 넘침 재기:

```js
document.documentElement.scrollWidth > document.documentElement.clientWidth   // true면 페이지가 옆으로 밀림
[...document.querySelectorAll('body *')].filter(e => e.getBoundingClientRect().right > innerWidth + 1)
```

4. 띄어쓰기 없는 200자 낱말을 제목으로 글을 써 보고 목록·상세가 어떻게 보이는지 본다.

## 8. 확인 문제

1. viewport 메타 태그가 없으면 휴대폰에서 무슨 일이 생기나?
<details><summary>답</summary>브라우저가 PC용 페이지로 보고 약 980px 폭으로 그린 뒤 통째로 축소한다. 글자가 아주 작아지고 미디어 쿼리도 그 폭 기준으로 동작한다.</details>

2. grid 칸에 `1fr` 대신 `minmax(0, 1fr)`을 쓰는 이유는?
<details><summary>답</summary>1fr의 최소 폭은 안의 내용 중 가장 넓은 것이라 긴 코드 한 줄이 칸을 화면보다 넓게 민다. 최소를 0으로 두면 칸이 화면 폭을 지킨다.</details>

3. 표를 좁은 화면에서 카드로 바꿀 때 `data-label`과 `::before`가 하는 일은?
<details><summary>답</summary>머리줄을 숨기면 각 값이 무엇인지 모르게 되므로, td의 data-label 값을 ::before의 content: attr(data-label)로 꺼내 값 앞에 이름표로 붙인다.</details>

4. 16개 화면이 모두 "가로 넘침 없음"이었는데 내 글 관리가 깨져 있던 이유는?
<details><summary>답</summary>표가 가로 스크롤 상자 안에 있어 페이지는 넘치지 않았지만, 브라우저가 칸들을 최대한 좁혀 제목 칸이 한 글자 폭이 되었다. 측정은 넘침만 알려 주고 보기 좋은지는 알려 주지 않는다.</details>

5. 헤드리스 Chrome으로 휴대폰 화면을 흉내 낼 때 설정한 것들은?
<details><summary>답</summary>Emulation.setDeviceMetricsOverride로 폭 360, 높이 800, 배율 2, mobile: true, 그리고 안드로이드 휴대폰 User-Agent. 로그인이 필요한 화면은 Network.setCookie로 로그인 쿠키를 넣었다.</details>

## 9. 더 읽을거리

- MDN, "Viewport meta tag", "Using media queries", "Responsive design"
- MDN, CSS Grid `minmax()`, `attr()`
- Chrome DevTools Protocol 문서: `Emulation`, `Network.setCookie`, `Page.captureScreenshot`, `Runtime.evaluate`
- Playwright·Puppeteer: CDP를 감싼 브라우저 자동화 도구(화면 테스트를 코드 저장소에 넣고 싶을 때)
