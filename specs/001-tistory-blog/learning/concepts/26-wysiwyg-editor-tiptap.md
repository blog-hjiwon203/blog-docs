# 26. WYSIWYG 에디터와 Tiptap

> 관련 스텝: [스텝 5](../step-05.md) (T035, T035a, T031) · 관련 개념: [14-xss-sanitize-csp](./14-xss-sanitize-csp.md), [17-idempotency-redis](./17-idempotency-redis.md), [19-react-router-api-client](./19-react-router-api-client.md), [25-react-forms-data](./25-react-forms-data.md)

## 1. 이 문서로 배우는 것

- WYSIWYG 에디터와 마크다운 에디터의 차이, 이 프로젝트가 WYSIWYG를 고른 대가
- 브라우저 `contenteditable`만으로 에디터를 만들기 어려운 이유
- ProseMirror의 세 가지 핵심: 문서 모델, 스키마, 트랜잭션
- Tiptap의 구조: `Editor`, 확장(Extension), `StarterKit`, 명령 체인
- 에디터가 만드는 HTML과 서버 정화 허용 목록(`HtmlSanitizer`)을 맞추는 이유
- 이중 정화: 프론트 에디터는 편의, 서버 정화가 보안
- React에서 Tiptap을 쓸 때의 함정: 본문 다시 넣기와 커서, 툴바 다시 그리기, 선택 유지
- 한 에디터에서 WYSIWYG와 마크다운을 섞어 쓰기: 입력 규칙(input rule)과 마크다운 붙여넣기 (T035a)
- 라이브러리 버전을 고르는 기준(공급망 위험)
- 헤드리스 Chrome으로 에디터에 실제로 입력하고 발행해 확인하는 방법

**먼저 알면 좋은 것**: HTML 태그, React의 상태와 `useEffect`([25](./25-react-forms-data.md)), XSS와 허용 목록 정화([14](./14-xss-sanitize-csp.md)).

## 2. 왜 필요한가

블로그 글은 서식이 있다. 문단 제목, 굵게, 목록, 인용, 코드 블록, 링크. 사용자가 서식을 넣는 방법은 크게 둘이다.

| 방식 | 사용자가 보는 것 | 저장하는 것 | 장점 | 단점 |
| --- | --- | --- | --- | --- |
| 마크다운 | `## 제목`, `**굵게**` 같은 기호 | 마크다운 글자 | 저장 값이 단순하고 안전하게 다루기 쉬움 | 기호를 배워야 함 |
| WYSIWYG (What You See Is What You Get) | 워드처럼 굵은 글자가 바로 굵게 | HTML | 티스토리와 같은 쓰는 경험 | 저장 값이 HTML이라 위험 |

이 프로젝트는 티스토리와 같은 경험을 위해 WYSIWYG를 골랐다. plan.md "복잡도 기록"에 그 대가가 적혀 있다: **HTML을 저장하므로 서버 정화가 필수**이고, 화면에 그릴 때도 한 번 더 거른다(이중 정화).

에디터를 직접 만들지 않고 라이브러리(Tiptap)를 쓰는 이유는 3장에서 본다. 한 줄로: 브라우저가 주는 편집 기능은 브라우저마다 다른 HTML을 만들고, 우리가 허락한 서식만 만들게 통제하기 어렵다.

## 3. 기본 개념

### 3.1 contenteditable의 한계

HTML 요소에 `contenteditable="true"`를 붙이면 브라우저가 그 안을 편집할 수 있게 해 준다. 그러면 에디터가 다 된 것 같지만:

- 같은 Enter 키에 어떤 브라우저는 `<div>`를, 어떤 브라우저는 `<p>`나 `<br>`을 넣는다.
- 굵게 명령(`document.execCommand('bold')`)은 `<b>`를 쓰기도, `<strong>`을 쓰기도, `<span style="font-weight:bold">`를 쓰기도 한다. `execCommand` 자체가 표준에서 "쓰지 말 것"으로 분류됐다.
- 다른 사이트에서 복사해 붙여 넣으면 그 사이트의 스타일·스크립트 속성이 그대로 들어온다.
- "지금 커서가 굵은 글자 안에 있나?" 같은 질문에 답하려면 DOM을 직접 뒤져야 한다.

즉 **문서의 진짜 모양이 DOM**이라서, 우리가 원하는 모양을 강제할 수 없다.

### 3.2 ProseMirror: 문서를 따로 들고 있는 에디터

ProseMirror는 이 문제를 이렇게 푼다.

| 개념 | 뜻 | 비유 |
| --- | --- | --- |
| **문서 모델** | 에디터가 문서를 DOM이 아니라 자기 자료구조(노드 트리)로 들고 있다 | 원본은 엑셀 시트, 화면은 그 시트를 그린 그림 |
| **스키마** | 어떤 노드(문단, 제목, 목록…)와 마크(굵게, 링크…)가 있을 수 있는지 정한 규칙 | 시트의 열 정의. 정의에 없는 열은 들어갈 수 없음 |
| **트랜잭션** | 문서를 바꾸는 모든 일은 "변경 묶음"으로 적용된다 | 시트 수정 기록 |
| **뷰** | 문서 모델을 DOM으로 그리고, 키 입력을 트랜잭션으로 바꾼다 | 화면 |

핵심은 **스키마**다. 스키마에 "취소선"이 없으면, 취소선이 든 HTML을 붙여 넣어도 문서 모델에 들어갈 자리가 없어 취소선이 떨어져 나간다. 그래서 에디터가 만드는 HTML은 스키마가 정한 모양으로만 나온다.

### 3.3 Tiptap: ProseMirror를 쓰기 쉽게

ProseMirror는 강력하지만 저수준이다. Tiptap은 그 위에 쓰기 쉬운 층을 얹는다.

- **Editor**: 에디터 하나. 문서, 스키마, 명령을 들고 있다.
- **Extension(확장)**: 스키마 조각과 명령, 단축키를 묶은 것. `Bold` 확장은 "굵게 마크 + `toggleBold` 명령 + Ctrl/⌘+B"를 더한다.
- **StarterKit**: 자주 쓰는 확장(문단, 제목, 굵게, 기울임, 목록, 인용, 코드 블록, 링크 등)을 한 번에 넣는 꾸러미. `configure`로 각 확장을 켜고 끄거나 옵션을 준다. 확장 이름에 `false`를 주면 그 확장을 넣지 않는다.
- **명령 체인**: `editor.chain().focus().toggleBold().run()`
  - `chain()`: 명령을 여러 개 이어 붙여 **트랜잭션 하나**로 적용하겠다.
  - `focus()`: 에디터에 포커스를 돌려준다(툴바 버튼을 누르면 포커스가 버튼으로 가기 때문).
  - `toggleBold()`: 선택한 글자의 굵게를 켜거나 끈다.
  - `run()`: 여기까지 모은 것을 실제로 실행한다. `run()`을 빼면 아무 일도 안 일어난다.
- `editor.isActive('bold')`: 지금 커서 위치가 굵게인가. 툴바 버튼의 켜짐 표시에 쓴다.
- `editor.getHTML()`: 문서 모델을 HTML 문자열로 바꿔 준다. 저장할 때 쓴다.
- `editor.commands.setContent(html)`: HTML을 읽어 문서를 통째로 바꾼다. 스키마에 없는 것은 버려진다.

### 3.4 이중 정화

```
[브라우저] Tiptap 스키마 ──▶ 허락한 서식만 담긴 HTML
             │  (그러나 요청은 누구나 직접 만들 수 있다: curl, 개발자 도구)
             ▼
[서버]     HtmlSanitizer(허용 목록) ──▶ DB에 저장   ← 보안은 여기서 지킨다
             ▼
[브라우저] DOMPurify(스텝 6) ──▶ 화면에 넣기       ← 혹시 모를 구멍을 한 번 더
```

- 에디터의 스키마는 **편의**다. 사용자가 실수로 이상한 서식을 넣지 않게 한다. 공격자는 에디터를 거치지 않고 API를 직접 부를 수 있으므로 보안 장치가 아니다.
- 서버 정화가 **보안**이다(spec 공통 규칙 보안: "화면을 거치지 않고 요청을 직접 보내도 같다").
- 화면에 그릴 때 DOMPurify를 한 번 더 거치는 것은 스텝 6 글 상세에서 한다.

### 3.5 WYSIWYG와 마크다운을 함께 (T035a)

에디터를 고르는 방식은 보통 둘 중 하나다.

| 방식 | 쓰는 법 | 저장 |
| --- | --- | --- |
| WYSIWYG | 버튼으로 서식, 보이는 그대로 | HTML |
| 마크다운 에디터 | `## 제목`, `**굵게**`처럼 기호로 쓰고 옆에서 미리보기 | 마크다운 글자 |

지원은 둘 중 하나를 고르게 하지 않고 **한 에디터에서 섞어 쓰게** 정했다(2026-10-08, spec POST-01). Notion·Typora·티스토리 새 에디터가 이렇게 동작한다. 화면은 WYSIWYG 하나이고, 그 안에서 마크다운 기호를 치면 그 자리에서 서식으로 바뀐다. 저장은 계속 HTML이라 서버 정화·DB·API는 그대로다.

이것을 만드는 장치가 두 가지다.

- **입력 규칙(input rule)**: 글자를 칠 때마다 커서 앞의 글자를 정규식으로 보고, 맞으면 그 글자를 서식으로 바꾼다. `## `를 치는 순간 문단이 제목이 되는 식이다. ProseMirror에 있는 기능이고, Tiptap의 각 확장(제목, 굵게, 목록 등)이 자기 규칙을 가지고 있어 StarterKit만 켜도 대부분 된다.
- **마크다운 붙여넣기**: 다른 곳에서 쓴 마크다운 글을 통째로 붙여넣으면, 마크다운을 해석해 문서 모델로 바꿔 넣는다. Tiptap 공식 `@tiptap/markdown` 확장이 해석(내부에서 `marked` 라이브러리 사용)을 맡고, "언제 해석할지"는 이 프로젝트가 붙여넣기 처리기로 정한다.

입력 규칙은 **사용자가 칠 때만** 동작한다. 저장된 HTML을 불러오거나 붙여넣을 때는 동작하지 않는다. 그래서 붙여넣기는 따로 처리해야 한다.

## 4. 동작 원리

### 4.1 에디터 HTML과 서버 허용 목록을 맞춰야 하는 이유

서버의 `HtmlSanitizer`는 허용 목록에 없는 태그를 지운다(태그는 지우고 안의 글자는 남긴다). 그러면:

| 에디터가 만든 것 | 서버 허용 목록에 | 저장 결과 | 사용자가 느끼는 것 |
| --- | --- | --- | --- |
| `<strong>굵게</strong>` | 있음 | 그대로 | 정상 |
| `<s>취소선</s>` | 없음 | `취소선` | "취소선을 넣었는데 저장하니 사라졌다" |
| `<hr>` | 없음 | 사라짐 | "구분선이 없어졌다" |

그래서 **에디터 버튼은 서버가 남기는 서식에만** 둔다. 이 프로젝트는 서버가 지우는 밑줄(`u`), 취소선(`s`), 구분선(`hr`)을 에디터에서 끄고, 제목도 툴바에서 h2·h3만 쓴다(서버는 h1~h6를 다 허용하지만 글 제목이 이미 가장 큰 제목이라 본문에는 h2부터 쓴다).

### 4.2 React와 Tiptap: 누가 본문을 들고 있나

제어 컴포넌트([25](./25-react-forms-data.md))에서는 React 상태가 입력값의 주인이다. 에디터는 다르다. **문서의 주인은 Tiptap**이고 React는 바뀐 결과(HTML)를 받아 둘 뿐이다.

```
사용자 입력 → Tiptap 문서 변경 → onUpdate → onChange(getHTML()) → 화면 상태 contentHtml
                                                               (발행할 때 이 값을 보냄)
```

반대 방향(React → Tiptap)으로 매번 본문을 다시 넣으면 문제가 생긴다. `setContent`는 문서를 통째로 바꾸므로 **커서가 맨 끝으로 튄다**. 그래서 이 프로젝트는 "수정 화면에서 서버에서 불러온 본문"만 넣는다(`initialHtml`). 입력할 때마다 바뀌는 `contentHtml`은 에디터에 다시 넣지 않는다.

### 4.3 툴바 켜짐 표시와 다시 그리기

React는 상태가 바뀌어야 컴포넌트를 다시 그린다. Tiptap 3의 `useEditor`는 기본값으로 **트랜잭션마다 다시 그리지 않는다**(`shouldRerenderOnTransaction` 기본 false, 성능 때문). 그러면 커서를 굵은 글자로 옮겨도 툴바의 "굵게" 버튼이 켜짐으로 바뀌지 않는다. 이 프로젝트는 `shouldRerenderOnTransaction: true`로 켰다. 글 하나를 쓰는 화면이라 다시 그리는 비용이 문제가 되지 않는다.

### 4.4 버튼을 눌러도 선택이 유지되게

글자를 드래그로 선택하고 "굵게" 버튼을 누르면, 마우스를 누르는 순간 포커스가 버튼으로 옮겨 가 에디터의 선택이 풀릴 수 있다. 버튼의 `onMouseDown`에서 `event.preventDefault()`를 부르면 브라우저 기본 동작(포커스 이동)이 막혀 선택이 남는다. 그다음 `onClick`에서 `chain().focus()...`로 명령을 실행한다.

### 4.5 입력 규칙이 동작하는 순서

`이건 **굵게**`를 치는 과정을 보자.

```
'이건 **굵게*'  → 굵게 규칙의 식 /\*\*([^*]+)\*\*$/ 에 아직 안 맞음
'이건 **굵게**' → 마지막 *를 치는 순간 맞음
                → 규칙의 handler가 '**굵게**' 범위를 '굵게'(굵게 마크)로 바꾸는 트랜잭션을 만든다
                → 화면에는 '이건 굵게'만 보인다
```

규칙의 식은 `$`로 끝나서 **커서 바로 앞**에서만 맞는다. 문단 중간에 예전에 쳐 둔 `**`가 있어도 지금 치는 자리가 아니면 바뀌지 않는다. handler가 `null`을 돌려주면 "바꾸지 않음"이라 글자는 친 그대로 남는다. 이 프로젝트의 링크 규칙은 주소가 http/https가 아니면 `null`을 돌려 `javascript:` 링크를 막는다.

### 4.6 붙여넣기가 동작하는 순서

```
사용자가 붙여넣음 → 브라우저 paste 이벤트
  → ProseMirror가 editorProps.handlePaste(view, event)를 먼저 부른다
      ├ true를 돌려주면: "내가 처리했다" → 기본 붙여넣기를 하지 않음
      └ false를 돌려주면: 기본 붙여넣기(HTML이면 스키마에 맞게 걸러 넣고, 글자면 문단으로)
```

이 프로젝트는 클립보드에 `text/html`이 없고(서식 없는 글자), 그 글자가 마크다운처럼 보일 때만 직접 처리한다. 웹 페이지에서 복사한 서식 있는 글은 기본 붙여넣기에 맡긴다.

## 5. 이 프로젝트에서는

### 5.1 확장 설정

`frontend/src/components/editor/Editor.tsx`

```tsx
const editorExtensions = [
  StarterKit.configure({
    heading: { levels: [2, 3] },
    strike: false,
    underline: false,
    horizontalRule: false,
    link: { openOnClick: false, autolink: true, protocols: ['http', 'https'], defaultProtocol: 'https' },
  }),
]
```

- `heading: { levels: [2, 3] }`: 문단 제목은 h2·h3만 스키마에 있다.
- `strike: false`, `underline: false`, `horizontalRule: false`: 서버 허용 목록에 없는 태그를 만드는 확장을 아예 넣지 않는다. 붙여 넣기로 들어와도 스키마에 자리가 없어 떨어진다.
- `link`: Tiptap 3의 StarterKit에는 링크 확장이 들어 있다.
  - `openOnClick: false`: 편집 중에 링크를 누르면 링크로 이동하지 않고 커서만 놓는다.
  - `autolink: true`: `https://...`를 치면 자동으로 링크가 된다.
  - `protocols`·`defaultProtocol`: 링크로 인정할 주소 방식. 서버도 http/https만 남긴다([14](./14-xss-sanitize-csp.md)의 `LINK_HREF`).
- 상수를 컴포넌트 밖에 둔 이유: 컴포넌트 안에 두면 다시 그릴 때마다 새 배열이 만들어진다. 밖에 두면 한 번만 만든다. `export`하지 않은 이유는 oxlint의 `only-export-components` 규칙(이 파일은 컴포넌트만 내보내야 Vite의 빠른 새로 고침이 동작) 때문이다.

### 5.2 에디터 만들기

```tsx
const editor = useEditor({
  extensions: editorExtensions,
  content: initialHtml,
  // 버튼의 켜짐 표시(굵게 등)를 커서가 움직일 때마다 다시 그린다
  shouldRerenderOnTransaction: true,
  onUpdate: ({ editor: current }) => onChange(current.getHTML()),
})
```

- `content`: 처음 그릴 본문. 새 글이면 빈 문자열이다.
- `onUpdate`: 문서가 바뀔 때마다 불린다. HTML로 바꿔 부모(`PostWritePage`)의 상태로 올린다.
- `editor`는 처음 그릴 때 `null`일 수 있어서 툴바는 `null`을 받으면 빈 막대를 그린다.

### 5.3 불러온 본문 넣기

```tsx
useEffect(() => {
  if (editor && initialHtml !== editor.getHTML()) {
    editor.commands.setContent(initialHtml, { emitUpdate: false })
  }
  // 불러온 본문(initialHtml)이 바뀔 때만 넣는다. 입력할 때마다 넣으면 커서가 맨 끝으로 튄다
}, [editor, initialHtml])
```

- 수정 화면은 처음에 빈 본문으로 그려지고, `GET /api/manage/posts/{id}` 응답이 오면 `initialHtml`이 바뀐다. 그때 한 번 넣는다.
- `emitUpdate: false`: 이 변경으로 `onUpdate`를 부르지 않는다. 불러온 값을 넣은 것뿐이라 "사용자가 바꿨다"로 치지 않는다. 부모는 불러올 때 `contentHtml`도 같이 채워 두었다(`PostWritePage`의 `setContentHtml(post.contentHtml)`).
- `PostWritePage`는 `loadedHtml`(불러온 본문)과 `contentHtml`(지금 본문)을 따로 들고 있고, 에디터에는 `loadedHtml`만 준다. 4.2의 "커서 튐"을 피하는 구조다.

### 5.4 툴바

```tsx
const chain = () => editor.chain().focus()
const button = (label: string, active: boolean, run: () => void) => (
  <button key={label} type="button" className={active ? 'btn on' : 'btn'} aria-pressed={active}
          onMouseDown={(event) => event.preventDefault()} onClick={run}>
    {label}
  </button>
)
```

- `type="button"`: 폼 안의 버튼은 기본이 `submit`이다. 이것을 빼면 "굵게"를 누를 때마다 글이 발행된다.
- `aria-pressed`: 화면 낭독기에 "켜진 버튼"임을 알린다.
- `onMouseDown`의 `preventDefault`: 4.4의 선택 유지.

```tsx
{button('굵게', editor.isActive('bold'), () => chain().toggleBold().run())}
{button('제목', editor.isActive('heading', { level: 2 }), () => chain().toggleHeading({ level: 2 }).run())}
{button('코드', editor.isActive('codeBlock'), () => chain().toggleCodeBlock().run())}
```

이미지 버튼은 `disabled`다. 이미지 업로드(POST-05)는 스텝 7이다.

### 5.5 링크 넣기

```tsx
function toggleLink() {
  if (editor!.isActive('link')) {
    chain().unsetLink().run()
    return
  }
  const url = window.prompt('링크 주소 (http:// 또는 https://)')
  if (url && /^https?:\/\/\S+$/i.test(url.trim())) {
    chain().setLink({ href: url.trim() }).run()
  } else if (url) {
    window.alert('http:// 또는 https://로 시작하는 주소만 넣을 수 있습니다.')
  }
}
```

- 이미 링크면 끄고, 아니면 주소를 묻는다.
- 정규식은 서버 `HtmlSanitizer`의 `LINK_HREF`(`^https?://\S+$`)와 같다. 같은 규칙을 화면에서 먼저 알려 주면 "저장했더니 링크가 사라졌다"를 막는다. `javascript:alert(1)` 같은 주소는 여기서도, 서버에서도 걸린다.
- `window.prompt`는 단순하지만 꾸밀 수 없다. 나중에 작은 입력 상자로 바꿀 수 있다.

### 5.6 실제로 저장된 HTML

스텝 5 확인 때 curl로 이런 본문을 보냈다.

```html
<h2>소제목</h2><p>본문 <strong>굵게</strong> <a href="https://spring.io" target="_blank">링크</a></p>
<pre><code class="language-java">int x = 1;</code></pre><img src=x onerror=alert(1)>
```

`GET /api/manage/posts/{id}`로 다시 읽은 저장값:

```html
<h2>소제목</h2><p>본문 <strong>굵게</strong> <a href="https://spring.io" rel="nofollow noopener noreferrer">링크</a></p><pre><code class="language-java">int x &#61; 1;</code></pre>
```

| 바뀐 것 | 이유 |
| --- | --- |
| `target="_blank"`가 사라짐 | 허용 목록에 `target` 속성이 없다 |
| `rel="nofollow noopener noreferrer"`가 붙음 | `requireRelsOnLinks`. 새 창으로 열린 페이지가 `window.opener`로 우리 페이지를 조작하는 것을 막고, 검색 엔진에 이 링크를 추천하지 않는다고 알린다 |
| `<img src=x onerror=...>`가 통째로 사라짐 | `src`가 `/uploads/...` 꼴이 아니라 지워졌고, 속성이 없는 `img`는 남지 않았다 |
| `=`가 `&#61;`로 바뀜 | 정화기가 출력할 때 일부 문자를 문자 참조로 적는다. 브라우저에서는 똑같이 `=`로 보인다 |

브라우저에서 실제로 쓴 글은 `<p>에디터로 쓴 <strong>굵은 글자</strong></p>`였고 그대로 저장됐다. 에디터와 허용 목록이 맞으니 사용자가 쓴 서식이 그대로 남는다.

### 5.7 버전 고르기

```bash
npm install --save-exact @tiptap/react@3.31.3 @tiptap/starter-kit@3.31.3 @tiptap/pm@3.31.3
```

- 그때 최신은 3.31.4였지만 나온 지 8일밖에 안 됐다. 나온 지 2주가 넘은 3.31.3을 골랐다. npm 패키지가 탈취되어 악성 버전이 올라오는 일(공급망 공격)은 보통 며칠 안에 발견·삭제되기 때문에, 막 나온 버전을 바로 쓰지 않으면 그 위험을 피할 수 있다.
- `--save-exact`: `package.json`에 `^3.31.3`이 아니라 `3.31.3`으로 적는다. `^`면 나중에 `npm install`할 때 3.x의 더 새 버전이 깔릴 수 있다.
- 세 패키지는 서로 같은 버전을 요구한다(`@tiptap/react`의 peerDependencies에 `@tiptap/pm: 3.31.3`). 하나만 올리면 경고가 나거나 동작이 어긋난다.

### 5.8 브라우저에서 입력·발행을 확인한 방법

로그인 쿠키가 필요한 화면을 사람 손 없이 확인하려고 헤드리스 Chrome을 DevTools 프로토콜(CDP)로 조종했다.

1. Chrome을 `--headless=new --remote-debugging-port=9334`로 띄우고 `/json`에서 웹소켓 주소를 얻는다.
2. `Network.setCookie`로 curl 로그인에서 받은 `access_token`, `refresh_token`을 `.blog.test` 도메인에 넣는다.
3. `Page.navigate`로 `/manage/write`를 연다.
4. `Runtime.evaluate`로 제목 칸, `.ProseMirror`에 포커스를 주고 `Input.insertText`로 글자를 친다(실제 키 입력처럼 에디터에 들어간다). 툴바의 "굵게"는 `Runtime.evaluate`로 `click()`.
5. "발행"을 누른 뒤 `location.href`가 `/7`(새 글 번호)인지 보고, `Page.captureScreenshot`으로 화면을 남긴다.

이때 `typeof crypto.randomUUID`가 `undefined`로 나와, HTTP 개발 주소에서 연타 방지 키 대체 코드가 실제로 쓰인 것도 확인했다([17](./17-idempotency-redis.md), [19](./19-react-router-api-client.md)).

### 5.9 마크다운 입력 (T035a)

`frontend/src/components/editor/markdown.ts`: 화면과 떨어진 순수 함수라 Vitest로 바로 시험한다(`markdown.test.ts`).

```ts
export function isSafeLinkUrl(url: string): boolean {
  return /^https?:\/\/\S+$/i.test(url)
}

export const MARKDOWN_LINK = /\[([^\]]+)\]\(([^)\s]+)\)$/

export function looksLikeMarkdown(text: string): boolean {
  const blockSyntax = /^(#{1,6}\s|[-*+]\s|\d+\.\s|>\s?|```)/m
  const inlineSyntax = /\*\*[^*\n]+\*\*|\[[^\]\n]+\]\(https?:\/\/[^)\s]+\)/
  return blockSyntax.test(text) || inlineSyntax.test(text)
}
```

- `isSafeLinkUrl`: 서버 `HtmlSanitizer`의 링크 규칙(`^https?://\S+$`)과 같다. 툴바 링크 버튼과 마크다운 링크 규칙이 함께 쓴다.
- `MARKDOWN_LINK`: `[글자](주소)`의 닫는 괄호까지 친 순간을 찾는다. 1번 묶음이 글자, 2번이 주소.
- `looksLikeMarkdown`: 붙여넣은 글이 마크다운인지 가늠한다. `/m` 플래그라 `^`가 **줄마다** 맞는다. `#해시태그`(# 뒤에 공백 없음), `snake_case`, `2*3=6`처럼 기호가 섞인 평범한 문장은 마크다운으로 보지 않아 그대로 붙는다.

`frontend/src/components/editor/Editor.tsx`의 링크 입력 규칙:

```ts
const MarkdownLinkInput = Extension.create({
  name: 'markdownLinkInput',
  addInputRules() {
    return [
      new InputRule({
        find: MARKDOWN_LINK,
        handler: ({ state, range, match }) => {
          const [, text, href] = match
          const link = state.schema.marks.link
          if (!link || !isSafeLinkUrl(href)) {
            return null
          }
          state.tr.replaceWith(range.from, range.to, state.schema.text(text, [link.create({ href })]))
            // 링크 뒤에 이어 치는 글자는 링크가 아니게
            .removeStoredMark(link)
        },
      }),
    ]
  },
})
```

- `Extension.create`: 노드나 마크를 더하지 않고 기능만 더하는 확장. 여기서는 입력 규칙 하나.
- `find`: 커서 앞 글자에 맞출 식. `range`는 그 글자 범위(`[스프링](https://spring.io)` 전체).
- `state.schema.text(text, [link.create({ href })])`: 링크 마크가 붙은 글자 노드. 범위를 이것으로 바꾸면 기호는 사라지고 링크만 남는다.
- `removeStoredMark(link)`: 바꾼 뒤 이어서 치는 글자에 링크가 번지지 않게 한다.
- Tiptap 기본 입력 규칙에 링크가 없어서 직접 만들었다(제목·굵게·기울임·목록·인용·코드 블록은 StarterKit의 확장들에 이미 있다).

확장 목록과 붙여넣기 처리:

```ts
const editorExtensions = [
  StarterKit.configure({ /* 5.1과 같음 */ }),
  Markdown,
  MarkdownLinkInput,
]

const editorRef = useRef<TiptapEditor | null>(null)
const editor = useEditor({
  extensions: editorExtensions,
  content: initialHtml,
  contentType: 'html',
  ...
  editorProps: {
    handlePaste: (_view, event) => {
      const clipboard = event.clipboardData
      const text = clipboard?.getData('text/plain') ?? ''
      // 웹 페이지에서 복사한 서식 있는 글(text/html)은 Tiptap 기본 붙여넣기에 맡긴다
      if (!editorRef.current || clipboard?.getData('text/html') || !looksLikeMarkdown(text)) {
        return false
      }
      editorRef.current.commands.insertContent(text, { contentType: 'markdown' })
      return true
    },
  },
})

useEffect(() => {
  editorRef.current = editor
}, [editor])
```

- `Markdown`: `@tiptap/markdown` 확장. `insertContent(text, { contentType: 'markdown' })`처럼 "이 글자는 마크다운"이라고 알려 주면 해석해서 넣는다. 확장이 붙여넣기를 스스로 가로채지는 않아서, 붙여넣기 처리기를 직접 달았다.
- `contentType: 'html'`: 저장된 본문은 HTML이라고 분명히 적었다. `setContent`로 불러올 때도 같은 값을 준다.
- `editorRef`: 처리기는 에디터를 만들 때 정해지는데, 그때는 아직 `editor` 값이 없다. 만들어진 에디터를 `useEffect`에서 ref에 넣고 처리기는 ref로 꺼낸다. ref를 그리는 중에(render) 바꾸면 oxlint가 경고한다(`react(refs)`). 그래서 `useEffect` 안에서 넣었다.
- 붙여넣은 마크다운도 결국 HTML로 저장되고 서버가 정화한다. 마크다운 안에 `<script>`를 써도 스키마와 서버 정화를 지나며 사라진다.

**실제로 확인한 결과** (헤드리스 Chrome, 5.8과 같은 방법으로 한 글자씩 입력하고 붙여넣기 이벤트를 보냄):

| 친 것 / 붙여넣은 것 | 에디터 HTML |
| --- | --- |
| `## 제목입니다` | `<h2>제목입니다</h2>` |
| `이건 **굵게** 그리고 *기울임* 입니다` | `<p>이건 <strong>굵게</strong> 그리고 <em>기울임</em> 입니다</p>` |
| `[스프링](https://spring.io)` | `<a href="https://spring.io" ...>스프링</a>` |
| `[링크](javascript:alert(1))` | 바뀌지 않고 글자 그대로 |
| `- 목록 하나`, `> 인용문` | `<ul><li>…`, `<blockquote>…` |
| 붙여넣기 `### 소제목`, `1. 첫째`, ` ```java `, `[블로그](https://blog.test)` | `<h3>`, `<ol><li>`, `<pre><code class="language-java">`, `<a>` |

발행 뒤 서버에 저장된 본문에서는 `target`이 지워지고 `rel="nofollow noopener noreferrer"`가 붙었다(5.6과 같은 정화).

## 6. 자주 하는 실수와 함정

1. **에디터 버튼과 서버 허용 목록이 어긋남**: 저장 후 서식이 사라진다. 버튼을 더할 때는 `HtmlSanitizer`도 함께 본다.
2. **에디터 정화를 보안으로 믿음**: API는 에디터 없이 부를 수 있다. 서버 정화가 빠지면 XSS다.
3. **입력할 때마다 `setContent`**: 커서가 끝으로 튀고, 한글 입력(조합 중인 글자)이 깨질 수 있다. 불러온 본문만 넣는다.
4. **`run()` 빼먹기**: `chain().toggleBold()`만 쓰면 아무 일도 안 일어난다.
5. **툴바 버튼에 `type="button"` 빼먹기**: 폼이 제출된다.
6. **툴바 켜짐 표시가 안 바뀜**: Tiptap 3 기본은 트랜잭션마다 다시 그리지 않는다. `shouldRerenderOnTransaction: true` 또는 `useEditorState`.
7. **링크 주소를 화면에서만 검사**: 서버도 같은 규칙으로 지운다. 둘이 다르면 사용자가 헷갈린다.
8. **`^` 버전으로 설치**: 다른 컴퓨터나 나중에 다른 버전이 깔린다. `package-lock.json`도 커밋한다.
9. **붙여넣은 글을 무조건 마크다운으로 해석**: `snake_case_name`의 `_`나 `2*3*4`의 `*`가 기울임이 되는 식으로 글이 망가진다. 마크다운다운 모양이 있을 때만 해석한다(`looksLikeMarkdown`).
10. **마크다운 링크는 화면 기호라 안전하다고 생각**: `[누르세요](javascript:...)`도 링크가 될 수 있다. 입력 규칙에서 주소를 검사하고, 서버 정화가 한 번 더 지운다.
11. **입력 규칙이 저장된 본문에도 동작한다고 생각**: 입력 규칙은 칠 때만 동작한다. 불러오기나 붙여넣기는 따로 처리해야 한다.

## 7. 직접 해 보기

**실습 1. 에디터 만져 보기**

```bash
cd frontend && npm run dev     # /etc/hosts에 블로그 주소가 있어야 한다
```

`http://{내 주소}.blog.test:5173/manage/write`에서 제목·굵게·목록·코드 블록을 넣고 발행한다. 수정 화면(`/manage/posts/{id}/edit`)을 다시 열어 서식이 그대로인지 본다(spec US2 시나리오 1).

**실습 2. 붙여 넣기로 스키마 확인**

워드나 웹 페이지에서 취소선·색 글자를 복사해 에디터에 붙여 넣는다. 취소선과 색은 사라지고 글자만 남는다. 스키마에 없는 마크라서다.

**실습 3. 서버 정화 직접 보기**

```bash
R="--resolve myblog.blog.test:8080:127.0.0.1"   # bash에서
curl -s $R -b jar -H X-Requested-With:XMLHttpRequest -H Content-Type:application/json \
  -H "Idempotency-Key: $(uuidgen)" -X POST myblog.blog.test:8080/api/posts \
  -d '{"title":"정화","contentHtml":"<p style=\"color:red\" onclick=\"x()\">a</p><s>b</s><a href=\"javascript:alert(1)\">c</a>","visibility":"PUBLIC","status":"PUBLISHED"}'
curl -s $R -b jar myblog.blog.test:8080/api/manage/posts/{위에서 받은 id}
```

`style`, `onclick`, `<s>`, `javascript:` 링크가 어떻게 바뀌는지 본다.

**실습 4. 다시 그리기 끄기**

`Editor.tsx`에서 `shouldRerenderOnTransaction: true`를 지우고 dev 서버에서 굵은 글자 안으로 커서를 옮겨 본다. "굵게" 버튼 색이 바뀌지 않는다. 되돌린다.

**실습 5. 마크다운으로 쓰고 붙여넣기 (T035a)**

`npm run dev`로 띄운 글쓰기 화면에서 아래를 차례로 쳐 본다. 각 줄을 치는 순간 서식이 바뀌는지 본다.

```
## 제목
이건 **굵게** 그리고 *기울임*
- 목록
> 인용
[스프링](https://spring.io)
[나쁜 링크](javascript:alert(1))
```

마지막 줄은 바뀌지 않아야 한다. 그다음 메모장에 마크다운 글(제목, 번호 목록, ```로 감싼 코드)을 써서 복사해 붙여넣고, 서식으로 바뀌는지 본다. `snake_case_name 변수`처럼 평범한 문장을 붙여넣으면 그대로 붙는다.

## 8. 확인 문제

1. WYSIWYG 에디터를 고르면 서버 정화가 필수가 되는 이유는?
<details><summary>답</summary>저장하는 값이 HTML이라, 에디터를 거치지 않고 API를 직접 부르면 스크립트나 이벤트 속성이 든 HTML도 보낼 수 있기 때문이다. 에디터의 스키마는 편의일 뿐 보안 장치가 아니다.</details>

2. ProseMirror의 스키마가 하는 일을 붙여 넣기 예로 설명하라.
<details><summary>답</summary>문서에 들어갈 수 있는 노드와 마크를 정한다. 취소선이 스키마에 없으면 취소선이 든 HTML을 붙여 넣어도 문서 모델에 자리가 없어 취소선은 버려지고 글자만 남는다.</details>

3. 에디터에서 취소선 버튼을 켜 두면 생기는 문제는?
<details><summary>답</summary>서버 HtmlSanitizer 허용 목록에 `s`가 없어 저장할 때 취소선이 지워진다. 사용자는 넣은 서식이 사라졌다고 느낀다.</details>

4. 수정 화면에서 지금 본문(`contentHtml`)이 아니라 불러온 본문(`loadedHtml`)만 에디터에 넣는 이유는?
<details><summary>답</summary>`setContent`는 문서를 통째로 바꿔 커서를 끝으로 보낸다. 입력할 때마다 지금 본문을 다시 넣으면 글자를 칠 때마다 커서가 튄다.</details>

5. `chain().focus().toggleBold().run()`에서 `focus()`와 `run()`의 역할은?
<details><summary>답</summary>`focus()`는 툴바 버튼으로 갔던 포커스를 에디터로 되돌린다. `run()`은 이어 붙인 명령을 실제로 실행한다. 빼면 아무 일도 안 일어난다.</details>

6. 저장된 링크에 `target="_blank"`가 사라지고 `rel="nofollow noopener noreferrer"`가 붙은 이유는?
<details><summary>답</summary>허용 목록에 `target` 속성이 없어 지워졌고, 정화 정책의 `requireRelsOnLinks`가 링크마다 rel 값을 붙인다. noopener·noreferrer는 열린 페이지가 우리 페이지를 조작하거나 주소를 넘겨받지 못하게 한다.</details>

7. 나온 지 8일 된 최신 버전 대신 2주 넘은 버전을 `--save-exact`로 설치한 이유는?
<details><summary>답</summary>탈취된 악성 버전은 보통 며칠 안에 발견되어 내려가므로 막 나온 버전을 피하면 공급망 공격 위험이 줄어든다. `--save-exact`는 나중에 설치할 때 다른 버전이 깔리지 않게 버전을 고정한다.</details>

8. `## `를 치면 제목이 되는데, 저장된 HTML을 불러올 때 들어 있는 `## ` 글자는 왜 제목이 되지 않나?
<details><summary>답</summary>입력 규칙은 사용자가 글자를 칠 때 커서 앞 글자를 보고 동작한다. 불러오기(<code>setContent</code>)나 붙여넣기는 입력이 아니라서 규칙이 돌지 않는다. 그래서 마크다운 붙여넣기는 <code>handlePaste</code>로 따로 처리했다.</details>

9. 붙여넣은 글을 늘 마크다운으로 해석하지 않고 `looksLikeMarkdown`으로 먼저 보는 이유는?
<details><summary>답</summary>평범한 문장에 섞인 <code>*</code>, <code>_</code>, <code>#</code>가 기울임·제목 등으로 바뀌어 글이 망가지기 때문이다. 줄 앞의 <code>## </code>, <code>- </code>, <code>```</code>나 <code>**굵게**</code>, <code>[글자](주소)</code>처럼 마크다운에만 있는 모양이 있을 때만 해석한다.</details>

10. 마크다운 입력을 더했는데도 서버 코드, DB, API가 바뀌지 않은 이유는?
<details><summary>답</summary>마크다운은 입력하는 방법일 뿐이고, 에디터가 만드는 결과는 여전히 같은 HTML이기 때문이다. 서버는 지금처럼 HTML을 받아 정화해 저장한다. 마크다운 원문을 따로 저장하지 않기로 했다(spec 2026-10-08 지원 결정).</details>

## 9. 더 읽을거리

- ProseMirror 가이드 "Input rules"(prosemirror-inputrules), Tiptap 문서 "Input rules", "Markdown" 확장: https://tiptap.dev/docs
- CommonMark 명세(마크다운 표준 문법): https://commonmark.org

- Tiptap 문서: Getting started(React), StarterKit, Link 확장, Commands — https://tiptap.dev/docs
- ProseMirror Guide(문서 모델, 스키마, 트랜잭션) — https://prosemirror.net/docs/guide/
- MDN: `contenteditable`, `Document.execCommand`(사용 중단 안내)
- MDN: `rel="noopener"`, `rel="noreferrer"`
- OWASP Cheat Sheet: Cross Site Scripting Prevention
- Chrome DevTools Protocol 문서: `Input.insertText`, `Runtime.evaluate`, `Network.setCookie`
- 이 프로젝트: [14 XSS, HTML 정화, CSP](./14-xss-sanitize-csp.md), plan.md 복잡도 기록
