# XSS 방어: 본문 정화와 CSP

> 관련 스텝: [스텝 2](../step-02.md)(T014), [스텝 5](../step-05.md)(T031·T032 글 발행·수정에서 사용), [스텝 6](../step-06.md)(T045 글 상세, DOMPurify) · 관련 결정: research.md R-05, spec.md "보안(원본 4.5)"

## 1. 이 문서로 배우는 것

- XSS(Cross-Site Scripting)가 무엇이고 세 종류(저장형, 반사형, DOM 기반)가 어떻게 다른지
- 블로그 서비스에서 저장형 XSS가 특히 위험한 이유
- "출력할 때 이스케이프"와 "입력을 정화"의 차이, 언제 무엇을 쓰는지
- 차단 목록(blocklist)이 실패하는 이유와 허용 목록(allowlist)
- OWASP Java HTML Sanitizer의 정책 만드는 법(`HtmlPolicyBuilder`)
- 이 프로젝트 `HtmlSanitizer`의 허용 목록 한 줄씩, 그리고 실제 정화 결과
- `rel="nofollow noopener noreferrer"`의 뜻
- 정화 결과에서 `=`가 `&#61;`로 바뀌는 이유
- jsoup으로 요약 만들기와 코드 포인트(이모지) 자르기
- React의 자동 이스케이프, `dangerouslySetInnerHTML`, DOMPurify
- CSP 헤더의 지시어 하나하나와, CSP가 "두 번째 방어선"인 이유

**먼저 알면 좋은 것**: HTML 태그와 속성, 브라우저가 HTML을 읽어 화면과 스크립트를 실행한다는 것, [10-http-cookies](./10-http-cookies.md)(HttpOnly), [13-csrf-samesite-cors](./13-csrf-samesite-cors.md)(XSS 앞에서 CSRF 대책이 무력한 이유).

---

## 2. 왜 필요한가

이 서비스의 글 본문은 **HTML**이다. 에디터(Tiptap)에서 굵게, 목록, 코드 블록, 이미지를 넣으면 그 결과가 HTML로 저장되고, 다른 사람이 글을 열면 그 HTML이 그대로 화면에 그려진다(R-05).

그런데 HTML에는 서식만 있는 것이 아니다. `<script>`, `onerror="..."`, `href="javascript:..."`처럼 **실행되는 코드**도 들어갈 수 있다. 누군가 본문에 그런 것을 넣어 발행하면, 그 글을 여는 **모든 사람의 브라우저에서 그 코드가 실행된다**. 이것이 XSS다.

실행된 스크립트는 우리 사이트의 일부로 취급되므로:
- 그 사람으로 로그인된 상태에서 API를 부를 수 있다(글 삭제, 댓글 작성, 설정 변경). 쿠키가 HttpOnly라 토큰을 훔치지는 못해도, **그 페이지 안에서** 요청을 보내면 쿠키가 자동으로 실린다.
- 같은 출처 요청이라 CSRF 대책(헤더 확인)도 통과한다([13-csrf-samesite-cors](./13-csrf-samesite-cors.md) 3.4).
- 화면을 바꿔 가짜 로그인 창을 띄울 수 있다.

화면(에디터)에서 막는 것만으로는 부족하다. 공격자는 화면을 거치지 않고 API로 직접 HTML을 보낼 수 있다. 그래서 명세가 "화면을 거치지 않고 요청을 직접 보내도 같다"고 적었다(spec.md 보안).

---

## 3. 기본 개념

### 3.1 XSS의 세 종류

| 종류 | 악성 코드가 어디에 있나 | 예(개념) | 이 서비스에서 |
| --- | --- | --- | --- |
| **저장형**(Stored) | 서버 DB에 저장됨 | 글 본문에 `<img src=x onerror=...>`를 저장, 글을 여는 모든 사람에게 실행 | **가장 중요**. 글 본문, 댓글 |
| **반사형**(Reflected) | 요청(URL 등)에 들어 있고 응답에 그대로 반사됨 | 검색어를 화면에 "○○ 검색 결과"로 그대로 출력하는데, 검색어에 스크립트를 넣은 링크를 피해자가 클릭 | 검색 화면 등에서 입력을 그대로 HTML로 출력하면 생김 |
| **DOM 기반** | 서버를 거치지 않고, 프론트 코드가 URL 등을 읽어 DOM에 넣음 | `element.innerHTML = location.hash`처럼 브라우저 쪽 코드가 원인 | React에서 `dangerouslySetInnerHTML`을 잘못 쓰면 생김 |

### 3.2 블로그에서 저장형 XSS가 특히 위험한 이유

- **한 번 심으면 계속 실행된다.** 글이 홈의 인기 글에 올라가면 많은 사람이 연다.
- **모든 블로그가 같은 사이트다.** `*.blog.com`은 같은 사이트라 SameSite 쿠키가 실린다([13-csrf-samesite-cors](./13-csrf-samesite-cors.md) 3.5). 그리고 글을 연 주소(블로그 주소)에서 스크립트가 돌면 그 블로그 출처의 API를 부를 수 있다.
- **관리자도 글을 연다.** 신고된 글을 확인하는 서비스 관리자의 브라우저에서 실행되면, 관리자 권한으로 API가 불릴 수 있다.

### 3.3 출력 이스케이프와 입력 정화

**출력 이스케이프**(escape): 글자를 HTML이 아니라 **글자로** 보이게 바꾼다.

```
입력:  <b>안녕</b>
출력:  &lt;b&gt;안녕&lt;/b&gt;      → 화면에는 "<b>안녕</b>" 글자가 그대로 보임(굵게 안 됨)
```

| 글자 | 이스케이프 |
| --- | --- |
| `<` | `&lt;` |
| `>` | `&gt;` |
| `&` | `&amp;` |
| `"` | `&quot;` 또는 `&#34;` |
| `'` | `&#39;` |

제목, 댓글, 닉네임, 블로그 이름처럼 **서식이 필요 없는 입력**은 이스케이프만 하면 된다. 서버는 글자 그대로 저장하고, 화면에 넣을 때 이스케이프한다(React가 자동으로 해 준다, 3.8). spec.md의 "본문 외 입력은 글자 그대로만 보인다"가 이것이다.

**입력 정화**(sanitize): HTML을 **살려야** 하는 경우다. 본문은 굵게, 목록이 실제로 보여야 하므로 이스케이프할 수 없다. 대신 HTML을 분석해서 **허용한 태그·속성만 남기고 나머지를 지운다**.

| | 이스케이프 | 정화 |
| --- | --- | --- |
| 결과 | HTML이 글자로 보임 | 허용한 HTML만 동작 |
| 쓰는 곳 | 제목, 댓글, 닉네임 등 거의 모든 입력 | 글 본문(서식 필요) |
| 어려움 | 쉬움(규칙이 단순) | 어려움(HTML은 복잡) → 검증된 라이브러리를 쓴다 |

### 3.4 차단 목록은 왜 실패하나

"`<script>`를 지우자"는 생각은 실패한다. 실행 방법이 너무 많기 때문이다.

```
<script>...</script>
<SCRIPT>...</SCRIPT>                          ← 대소문자
<img src=x onerror=...>                       ← 이벤트 속성 (onerror, onload, onclick, onmouseover ...)
<svg onload=...>                              ← 다른 태그
<a href="javascript:...">                     ← URL 스킴
<a href="jav&#x61;script:...">                ← HTML 엔티티로 숨김
<iframe src="data:text/html,...">             ← data URL
<scr<script>ipt>...                           ← 지우고 나면 다시 만들어지는 조각
```

새 태그, 새 속성, 브라우저의 관대한 파싱 규칙이 계속 생기므로 "나쁜 것 목록"은 영원히 불완전하다.

**허용 목록**은 반대로 "이것만 남긴다"다. 목록에 없는 것은 **모르는 것이라도** 지운다. 새로운 공격 방법이 나와도 허용 목록에 없으면 살아남지 못한다. OWASP가 HTML 정화에 허용 목록을 권하는 이유다.

### 3.5 OWASP Java HTML Sanitizer

OWASP 프로젝트가 만든 자바 라이브러리다. 동작 방식:
1. 입력을 HTML 파서로 **토큰(태그, 속성, 글자)으로 나눈다**. 문자열 치환이 아니다.
2. 각 태그가 정책에 허용됐는지 본다. 아니면 태그를 버린다(글자 내용은 대개 남기고, `<script>`·`<style>` 같은 것은 내용째 버린다).
3. 허용된 태그의 속성을 하나씩 정책과 비교한다. 아니면 속성을 버린다.
4. URL 속성(`href`, `src`)은 허용한 프로토콜만 통과시킨다.
5. **새로 HTML을 써서** 돌려준다. 입력을 그대로 돌려주지 않으므로 이상한 모양(닫히지 않은 태그, 대문자 태그)도 정규화된다.

5번이 중요하다. 정화기는 "깨끗한 부분만 다시 써 준다". 그래서 출력의 모양이 입력과 조금 다르다(3.7).

정책을 만드는 도구가 `HtmlPolicyBuilder`다.

| 메서드 | 뜻 |
| --- | --- |
| `allowElements("p", "br")` | 이 태그들을 허용 |
| `allowAttributes("href").onElements("a")` | `a` 태그의 `href` 속성 허용 |
| `.matching(Pattern)` | 그 속성 값이 이 정규식에 맞을 때만 |
| `allowUrlProtocols("http", "https")` | URL 속성에 허용할 프로토콜(그 밖의 `javascript:`, `data:` 등은 거절) |
| `requireRelsOnLinks("nofollow", ...)` | 남은 링크에 `rel` 값을 강제로 붙임 |
| `toFactory()` | 만든 정책(`PolicyFactory`). 불변이라 여러 스레드가 함께 써도 된다 |

### 3.6 rel="nofollow noopener noreferrer"

| 값 | 뜻 | 막는 것 |
| --- | --- | --- |
| `noopener` | 링크로 연 새 창이 `window.opener`로 원래 페이지에 접근하지 못하게 | 새 창이 원래 탭을 가짜 페이지로 바꾸는 공격(reverse tabnabbing) |
| `noreferrer` | 링크를 따라갈 때 `Referer` 헤더를 보내지 않음(`noopener` 효과도 포함) | 원래 페이지 주소(비공개 글 주소 등)가 외부로 새는 것 |
| `nofollow` | 검색 엔진에게 "이 링크를 추천하는 것이 아니다" | 사용자 콘텐츠의 링크를 이용한 검색 순위 스팸 |

이 프로젝트의 정책은 `target` 속성을 허용하지 않아 링크가 새 창으로 열리지 않지만, 브라우저가 사용자의 가운데 클릭 등으로 새 창을 열 수 있으므로 `noopener`를 함께 둔다.

### 3.7 정화 결과에서 글자가 바뀌는 이유

OWASP 정화기는 출력할 때 HTML에서 의미를 가질 수 있는 글자를 **숫자 문자 참조**로 바꾼다. 실제로 확인한 결과:

```
입력:  <p>1 + 1 = 2, a@b.com, "인용" 'x' &amp; &lt;b&gt;</p>
출력:  <p>1 &#43; 1 &#61; 2, a&#64;b.com, &#34;인용&#34; &#39;x&#39; &amp; &lt;b&gt;</p>
```

`+`, `=`, `@`, `"`, `'`가 바뀌었다. 브라우저는 `&#61;`를 `=`로 보여 주므로 **화면에는 똑같이** 보인다. 이렇게 하는 이유는, 정화한 HTML이 나중에 어떤 맥락(속성 값 안, 템플릿 안 등)에 들어가더라도 그 글자들이 구문으로 해석될 여지를 없애려는 보수적인 선택이다.

결과: DB의 `content_html`은 입력과 글자 단위로 다르다. "저장한 HTML과 입력이 같아야 한다"는 테스트를 쓰면 안 되고, 코드 블록 안의 `=`도 바뀐다는 점을 기억한다.

### 3.8 React의 자동 이스케이프와 dangerouslySetInnerHTML

React는 JSX에 넣는 값을 **자동으로 이스케이프**한다.

```tsx
const title = '<img src=x onerror=alert(1)>'
return <h1>{title}</h1>        // 화면에 글자 그대로 보임. 실행 안 됨
```

그래서 제목, 댓글, 닉네임은 그냥 `{값}`으로 넣으면 안전하다.

HTML을 살려서 넣어야 하는 본문은 `dangerouslySetInnerHTML`을 써야 한다. 이름 그대로 위험하다는 표시다.

```tsx
<div dangerouslySetInnerHTML={{ __html: post.contentHtml }} />   // 이스케이프 없이 HTML로 넣음
```

이 프로젝트의 규칙(R-05, rest-api.md):
- `dangerouslySetInnerHTML`은 **본문(`contentHtml`)에만** 쓴다.
- 넣기 전에 **DOMPurify**(브라우저용 HTML 정화 라이브러리)를 한 번 더 거친다(스텝 6, 5.6).
- 서버 정화가 **필수**이고 DOMPurify는 **보조**다. 서버 정화를 건너뛴 데이터(예: 과거 데이터, 다른 클라이언트)가 있을 수 있어 두 번 막는다.

### 3.9 CSP (Content-Security-Policy)

정화를 아무리 잘해도 실수나 라이브러리 취약점이 있을 수 있다. CSP는 **"이 페이지에서 무엇을 실행·불러올 수 있는지"를 서버가 응답 헤더로 브라우저에 알려 주는** 장치다. 정화를 뚫고 스크립트가 HTML에 들어가도, 브라우저가 CSP에 맞지 않으면 실행하지 않는다.

```
Content-Security-Policy: default-src 'self'; script-src 'self'; ...
```

| 지시어 | 정하는 것 |
| --- | --- |
| `default-src` | 따로 정하지 않은 종류의 기본값 |
| `script-src` | 스크립트를 어디서 불러와 실행할 수 있나 |
| `style-src` | CSS |
| `img-src` | 이미지 |
| `font-src` | 글꼴 |
| `connect-src` | `fetch`, XHR, WebSocket이 연결할 곳 |
| `object-src` | `<object>`, `<embed>`(플러그인) |
| `base-uri` | `<base href>`로 바꿀 수 있는 기준 주소 |
| `form-action` | 폼이 제출될 수 있는 곳 |
| `frame-ancestors` | **다른 페이지가 이 페이지를** iframe에 넣을 수 있나 |

| 값 | 뜻 |
| --- | --- |
| `'self'` | 같은 출처 |
| `'none'` | 아무것도 |
| `'unsafe-inline'` | 인라인(`<script>...</script>`, `style="..."`, `onclick=`) 허용 |
| `data:`, `blob:` | 그 스킴의 URL 허용 |

**`script-src 'self'`의 효과**: `'unsafe-inline'`이 없으면 다음이 모두 막힌다.
- 인라인 `<script>코드</script>`
- 이벤트 속성 `onerror="..."`, `onclick="..."`
- `href="javascript:..."`

저장형 XSS의 대부분이 이 셋이라, `script-src 'self'` 하나로 큰 효과가 있다. 그래서 React 앱도 인라인 스크립트 없이 만들어야 한다(Vite 빌드 결과는 외부 파일 `<script type="module" src="/assets/...">`라 맞는다).

---

## 4. 동작 원리

### 4.1 글 하나가 저장되고 보이기까지 (스텝 5에서 완성)

```
[에디터] Tiptap이 HTML을 만듦
   │ POST /api/posts  { contentHtml: "<p>...</p>" }
   ▼
[서버] HtmlSanitizer.sanitize(contentHtml)      ← 1차 방어: 허용 목록 정화
       SummaryExtractor.extract(정화된 HTML)     ← 목록용 요약(태그 없는 글자)
       DB 저장 (content_html, summary)
   │
   │ GET /api/posts/15
   ▼
[프론트] DOMPurify.sanitize(contentHtml)         ← 2차 방어
         <div dangerouslySetInnerHTML=... />
   ▼
[브라우저] CSP 헤더 확인: 인라인 스크립트 실행 금지 ← 3차 방어
```

### 4.2 정화기 안에서 일어나는 일 (예)

```
입력: <p onclick="x()" style="color:red">글 <b>굵게</b></p><img src="https://evil/t.png" onerror="y()"><script>z()</script>

파싱 → [p onclick style] "글 " [b] "굵게" [/b] [/p] [img src onerror] [script] "z()" [/script]

p     허용 → onclick: 허용 목록에 없음 → 버림, style: 없음 → 버림
b     허용
img   허용 → src: /uploads/... 패턴에 안 맞음 → 버림, onerror → 버림
script 허용 안 함 → 태그와 내용째 버림

출력: <p>글 <b>굵게</b></p><img />
```

마지막 `<img />`처럼 **허용된 태그가 속성을 다 잃고 남을 수 있다**(5.2 표의 실제 결과).

---

## 5. 이 프로젝트에서는

### 5.1 `HtmlSanitizer`

경로: `src/main/java/com/nhnacademy/blog/global/security/HtmlSanitizer.java`

```java
/** 링크는 http/https 절대 주소만. 상대 주소와 javascript: 등은 지운다. */
private static final Pattern LINK_HREF = Pattern.compile("^https?://\\S+$", Pattern.CASE_INSENSITIVE);

/** 이미지는 이 서비스에 올린 파일만 (/uploads/{uuid}.{ext}). */
private static final Pattern UPLOADED_IMAGE_SRC =
        Pattern.compile("^/uploads/[A-Za-z0-9_-]+\\.(jpg|jpeg|png|gif|webp)$", Pattern.CASE_INSENSITIVE);

/** 코드 블록 언어 표시 (에디터가 붙이는 class="language-java"). */
private static final Pattern CODE_LANGUAGE_CLASS = Pattern.compile("^language-[A-Za-z0-9+#_-]{1,30}$");

private static final PolicyFactory POLICY = new HtmlPolicyBuilder()
        .allowElements("p", "br")                                          // ① 문단, 줄바꿈
        .allowElements("h1", "h2", "h3", "h4", "h5", "h6")                 // ② 문단 제목
        .allowElements("strong", "b", "em", "i")                           // ③ 굵게·기울임
        .allowElements("ul", "ol", "li")                                   // ④ 목록
        .allowElements("blockquote")                                       // ⑤ 인용
        .allowElements("pre", "code")                                      // ⑥ 코드 블록
        .allowAttributes("class").matching(CODE_LANGUAGE_CLASS).onElements("code")   // ⑦ 언어 표시만
        .allowElements("a")                                                // ⑧ 링크
        .allowUrlProtocols("http", "https")                                // ⑨ URL 프로토콜
        .allowAttributes("href").matching(LINK_HREF).onElements("a")       // ⑩ 절대 http(s) 주소만
        .requireRelsOnLinks("nofollow", "noopener", "noreferrer")          // ⑪
        .allowElements("img")                                              // ⑫ 이미지
        .allowAttributes("src").matching(UPLOADED_IMAGE_SRC).onElements("img")       // ⑬ 우리 업로드만
        .allowAttributes("alt").onElements("img")                          // ⑭ 대체 글자
        .toFactory();
```

- ①~⑥: spec.md 보안이 정한 "허용한 서식"(문단 제목, 굵게·기울임, 목록, 인용, 코드 블록)을 그대로 옮겼다. `<u>`, `<s>`, `<hr>`, `<table>`, `<div>`, `<span>`은 목록에 없어서 지워진다(글자는 남는다).
- ⑦ `class`는 아무 값이나 허용하면 페이지의 CSS 규칙을 이용한 화면 위장이 가능하다. 에디터가 쓰는 `language-xxx` 모양만 받는다.
- ⑨ 프로토콜만 제한하면 `/relative` 같은 상대 주소는 통과한다. 그래서 ⑩에서 정규식으로 **절대 http(s) 주소만** 받는다. spec.md "링크(http/https만)"를 엄격히 해석한 것이다.
- ⑬ 외부 이미지(`https://...`)를 막는 이유: 외부 서버가 이미지 요청을 이용해 "누가 언제 이 글을 열었는지"를 추적할 수 있고(트래킹 픽셀), 이미지 내용이 나중에 바뀔 수도 있다. spec.md "직접 올린 이미지"만 허용한다. `data:` URL도 정규식에 안 맞아 지워진다.
- `POLICY`가 `static final`인 이유: 정책 만들기는 비용이 있고, `PolicyFactory`는 불변이라 한 번 만들어 계속 쓴다.

실제 정화 결과(이 정책으로 직접 돌려 확인):

| 입력 | 출력 |
| --- | --- |
| `<p>안녕</p><script>alert('xss')</script>` | `<p>안녕</p>` |
| `<script>var x=1;</script>남은 글자` | `남은 글자` |
| `<style>p{color:red}</style><p>p</p>` | `<p>p</p>` |
| `<svg onload=alert(1)><circle/></svg>그림` | `그림` |
| `<a href="javascript:alert(1)">bad</a>` | `bad` (href가 지워지고, 속성 없는 `a`는 빠지고 글자만) |
| `<p><a href="https://spring.io" target="_blank">s</a></p>` | `<p><a href="https://spring.io" rel="nofollow noopener noreferrer">s</a></p>` |
| `<A HREF="HTTPS://EXAMPLE.COM">up</A>` | `<a href="HTTPS://EXAMPLE.COM" rel="nofollow noopener noreferrer">up</a>` |
| `<img src="https://evil.example/t.png" alt="x">` | `<img alt="x" />` (src만 지워지고 빈 이미지가 남음) |
| `<p>줄<br>바꿈</p>` | `<p>줄<br />바꿈</p>` |

마지막에서 둘째 줄처럼 외부 이미지는 `src`가 지워진 `<img>`가 남는다. 실행되는 것은 없지만 화면에 빈 이미지 칸이 생길 수 있다. 정책에서 `src`가 없는 `img`를 빼려면 정화 후 한 번 더 처리하거나 정책을 조정해야 한다(앞으로 고칠 거리).

### 5.2 `SummaryExtractor`

경로: `src/main/java/com/nhnacademy/blog/global/security/SummaryExtractor.java`

```java
public static final int MAX_LENGTH = 300;          // post.summary 컬럼 VARCHAR(300)
private static final String ELLIPSIS = "…";       // 한 글자짜리 말줄임표

public String extract(String html) {
    if (html == null || html.isBlank()) {
        return "";
    }
    String text = Jsoup.parse(html).text().strip();               // ① 태그 없는 글자만
    if (text.codePointCount(0, text.length()) <= MAX_LENGTH) {    // ② "글자 수"를 코드 포인트로 셈
        return text;
    }
    int end = text.offsetByCodePoints(0, MAX_LENGTH - ELLIPSIS.length());   // ③ 299글자 위치
    return text.substring(0, end).stripTrailing() + ELLIPSIS;
}
```

- ① jsoup의 `text()`는 모든 태그를 없애고 글자만 남기며, 블록 요소 사이와 연속 공백을 공백 하나로 정리한다. 요약은 **글자만** 남으므로 목록 화면에서 이스케이프만 하면 된다(HTML이 아니다).
- ② 자바 `String.length()`는 UTF-16 `char` 개수다. 이모지 `😀` 같은 문자는 `char` **두 개**(서로게이트 쌍)로 저장된다. `length()`로 300을 세면 실제 글자 수와 다르고, `substring(0, 299)`가 이모지 가운데를 잘라 깨진 글자가 생길 수 있다. 코드 포인트는 유니코드 문자 하나를 하나로 센다. MySQL `utf8mb4`의 `VARCHAR(300)`도 문자(코드 포인트) 단위로 센다.
- 한계: 국기 이모지나 피부색이 붙은 이모지처럼 **코드 포인트 여러 개가 합쳐 한 글자로 보이는** 경우(grapheme cluster)는 여전히 중간이 잘릴 수 있다. 요약에서는 감수할 만한 수준이다.

### 5.3 `ContentSecurityPolicyFilter`

경로: `src/main/java/com/nhnacademy/blog/global/security/ContentSecurityPolicyFilter.java`

```java
@Component
public class ContentSecurityPolicyFilter extends OncePerRequestFilter {

    static final String POLICY = String.join("; ",
            "default-src 'self'",                    // 기본: 같은 출처만
            "script-src 'self'",                     // 스크립트: 같은 출처 파일만. 인라인·이벤트 속성·javascript: 금지
            "style-src 'self' 'unsafe-inline'",      // CSS: 인라인 style 허용 (아래 설명)
            "img-src 'self' data: blob:",            // 이미지: 같은 출처 + data/blob (에디터 미리보기)
            "font-src 'self' data:",
            "connect-src 'self'",                    // fetch는 같은 출처 /api 만
            "object-src 'none'",                     // 플러그인(<object>, <embed>) 금지
            "base-uri 'self'",                       // <base href>로 상대 주소 기준 바꾸기 금지
            "form-action 'self'",                    // 폼은 같은 출처로만 제출
            "frame-ancestors 'none'");               // 다른 사이트가 우리를 iframe에 넣기 금지(클릭재킹)

    @Override
    protected void doFilterInternal(...) {
        response.setHeader("Content-Security-Policy", POLICY);
        filterChain.doFilter(request, response);
    }
}
```

- `style-src 'unsafe-inline'`을 허용한 이유: 에디터(Tiptap)와 React 컴포넌트가 `style="..."`을 직접 쓰는 경우가 많다. 인라인 스타일은 스크립트보다 위험이 훨씬 작고, **본문 HTML의 `style` 속성은 `HtmlSanitizer`가 먼저 지운다**.
- `img-src data: blob:`: 에디터에서 이미지를 올리기 전 미리보기를 `blob:`/`data:` URL로 보여 줄 수 있어서. 본문에 저장되는 이미지는 정화기가 `/uploads/...`만 남기므로 이 허용이 본문에 영향을 주지 않는다.
- `frame-ancestors 'none'`은 Spring Security가 붙이는 `X-Frame-Options: DENY`와 같은 목적의 최신 방식이다. `frame-ancestors`는 `<meta>` 태그로는 지정할 수 없고 응답 헤더로만 된다.
- 개발 중 Vite 개발 서버(5173)는 이 헤더를 붙이지 않는다. CSP는 jar로 서빙될 때(8080) 확인한다.

**주의(필터 순서)**: 이 필터는 `@Component`로 등록된 일반 서블릿 필터라 Spring Security 필터 체인 **다음**에 실행된다. 보안 체인이 직접 쓰고 끝내는 응답(CSRF 403, 인증 401)에는 CSP 헤더가 붙지 않는다. JSON 응답이라 실제 위험은 거의 없지만, 모든 응답에 붙이려면 Spring Security의 `headers().contentSecurityPolicy(...)`로 옮긴다([12-spring-security-filter-chain](./12-spring-security-filter-chain.md) 3.4).

### 5.4 테스트

- `src/test/java/com/nhnacademy/blog/global/security/HtmlSanitizerTest.java`: 스크립트, 이벤트 속성, style 제거, 허용 서식 유지, `&#61;` 변환, 링크 rel, 업로드 이미지만 허용, 모르는 태그는 글자만, code의 class 제한.
- `SummaryExtractorTest.java`: 태그 제거, 300자 자르기, 이모지 안 깨짐.
- `ContentSecurityPolicyFilterTest.java`: 응답에 CSP 헤더가 있는지.

### 5.5 (스텝 5) 발행·수정이 정화를 거치는 곳

스텝 2에서 만든 `HtmlSanitizer`와 `SummaryExtractor`를 스텝 5의 글 발행·수정이 실제로 부른다.

`src/main/java/com/nhnacademy/blog/post/application/PostService.java`

```java
public Post publish(Blog blog, PostCommand command) {
    String contentHtml = htmlSanitizer.sanitize(command.contentHtml());
    Post post = Post.published(blog, category(blog, command.categoryId()), command.title().trim(), contentHtml,
            summaryExtractor.extract(contentHtml), command.visibility(), command.topic(),
            LocalDateTime.now(clock));
    return postRepository.save(post);
}
```

- 첫 줄에서 요청 본문을 정화하고, **정화된** HTML만 다음 줄로 넘긴다. 원본(`command.contentHtml()`)은 저장되지 않는다.
- 요약은 정화된 HTML에서 만든다. 정화 전 HTML로 만들면 지워질 `<script>` 안의 글자가 요약에 섞일 수 있다.
- 수정(`edit`)도 같은 두 줄(`sanitize` → `extract`)을 거친다. 화면(에디터)을 거치지 않고 curl로 직접 보내도 같은 길이다.

**테스트** `src/test/.../post/PostWriteIntegrationTest.publishSanitizesBodyAndReturnsPostUrl`

| 보낸 본문 | 저장된 본문 | 요약 |
| --- | --- | --- |
| `<h2>제목</h2><p onclick="x()">본문 <b>굵게</b></p><script>alert(1)</script>` | `<h2>제목</h2><p>본문 <b>굵게</b></p>` | `제목 본문 굵게` |

이벤트 속성(`onclick`)과 `<script>`가 통째로 사라지고, 요약은 태그 없는 글자만 남는다.

**실서버에서 본 결과** (스텝 5 확인, curl로 직접 발행)

| 보낸 것 | 저장된 것 |
| --- | --- |
| `<a href="https://spring.io" target="_blank">링크</a>` | `<a href="https://spring.io" rel="nofollow noopener noreferrer">링크</a>` (`target` 지움, `rel` 붙임, 3.6) |
| `<code class="language-java">int x = 1;</code>` | `<code class="language-java">int x &#61; 1;</code>` (`=`가 문자 참조로, 3.7) |
| `<img src=x onerror=alert(1)>` | 없음. `src`가 업로드 경로가 아니라 지워지고, `onerror`도 지워져 남는 속성이 없는 `<img>`는 통째로 빠졌다 |

`alt`가 있는 외부 이미지는 `<img alt="..." />`로 남는다(5.1 표). 이 남은 문제는 이미지 업로드를 만드는 스텝 7에서 다룬다.

**에디터와 허용 목록 맞추기.** 스텝 5의 Tiptap 에디터는 서버 허용 목록에 있는 서식만 켠다(문단 제목, 굵게·기울임, 목록, 인용, 코드 블록, http/https 링크). 밑줄(`<u>`)·취소선(`<s>`)·구분선(`<hr>`)은 허용 목록에 없어서 에디터에서도 끈다. 켜 두면 에디터에서는 보이는데 저장하면 사라지는 서식이 생긴다. 자세한 설정은 [26](./26-wysiwyg-editor-tiptap.md).

### 5.6 (스텝 6) 화면 쪽 정화: DOMPurify와 dangerouslySetInnerHTML

스텝 6에서 글 상세 화면이 생기면서 4.1 그림의 "2차 방어"가 실제 코드가 됐다. 이로써 이중 정화가 처음부터 끝까지 이어진다.

```
[에디터] Tiptap: 허용 서식만 켬 (26)          ← 쓰는 사람의 편의, 보안 아님
   ▼ POST /api/posts
[서버] HtmlSanitizer로 정화해서 저장 (5.1, 5.5)  ← 1차 방어, 필수
   ▼ GET /api/posts/{id}
[화면] sanitizePostHtml(DOMPurify) (이 절)       ← 2차 방어, 보조
   ▼ dangerouslySetInnerHTML
[브라우저] CSP: 인라인 스크립트 실행 금지 (5.3)   ← 3차 방어
```

`frontend/src/app/sanitize.ts`

```ts
const ALLOWED_TAGS = ['p', 'br', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong', 'b', 'em', 'i', 'ul', 'ol', 'li',
  'blockquote', 'pre', 'code', 'a', 'img']
const ALLOWED_ATTR = ['href', 'rel', 'src', 'alt', 'class']

export function sanitizePostHtml(html: string): string {
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS,
    ALLOWED_ATTR,
    // 링크는 http/https, 이미지는 이 서비스에 올린 파일만 (서버 규칙과 같음)
    ALLOWED_URI_REGEXP: /^(?:https?:\/\/|\/uploads\/)/i,
  })
}
```

- `ALLOWED_TAGS`, `ALLOWED_ATTR`: 서버 `HtmlSanitizer`의 허용 목록(5.1)과 **같은 태그·속성**만 남긴다. DOMPurify는 기본값으로도 스크립트·이벤트 속성을 지우지만, 기본값은 서버보다 훨씬 넓다(`<table>`, `<span style>` 등). 두 허용 목록이 같아야 "서버가 남긴 것만 화면에 나온다"가 성립한다.
- `ALLOWED_URI_REGEXP`: `href`·`src` 같은 주소 속성에 허용할 모양. `http://`, `https://`로 시작하는 주소와 `/uploads/`(이 서비스에 올린 이미지)만 통과한다. `javascript:alert(1)`은 여기서 걸러진다. 서버의 `LINK_HREF`, `UPLOADED_IMAGE_SRC` 정규식과 같은 규칙이다.
- 이 함수는 **본문 한 곳에만** 쓴다. 제목·댓글·닉네임은 HTML이 아니라 글자이므로 정화하지 않고 React의 `{값}`에 맡긴다(3.8).

`frontend/src/pages/post/PostPage.tsx`

```tsx
<div className="prose" dangerouslySetInnerHTML={{ __html: sanitizePostHtml(post.contentHtml) }} />
```

- `dangerouslySetInnerHTML`은 React가 이스케이프하지 않고 **HTML로 해석해서** 넣으라는 뜻이다. 이름에 `dangerously`를 붙이고 값을 `{ __html: ... }` 객체로 감싸게 한 것은, 실수로 쓰지 않게 일부러 불편하게 만든 장치다. 코드 리뷰에서 이 이름이 보이면 "여기 들어가는 값이 정화됐나"를 확인하라는 신호다.
- **Thymeleaf에 빗대면**: `th:text="${post.title}"`은 HTML을 이스케이프해서 글자로 넣고, `th:utext="${post.contentHtml}"`은 이스케이프 없이(unescaped) HTML로 넣는다. React의 `{값}`이 `th:text`, `dangerouslySetInnerHTML`이 `th:utext`에 해당한다. Thymeleaf에서도 `th:utext`에는 정화한 값만 넣어야 했던 것과 같다([28](./28-thymeleaf-to-react.md)).
- 서버가 이미 정화했는데 또 거르는 이유는 7번 확인 문제와 같다. 정책을 바꾸기 전의 옛 데이터, 서버를 거치지 않은 경로, 서버 정화기 자체의 결함에 대비한다.

**버전 고르기.** 처음에는 나온 지 2주가 넘은 3.4.15를 설치했다. 그런데 `npm audit`이 3.4.15 이하에 보안 권고 두 건을 알렸다. 둘 다 `IN_PLACE` 옵션(정화 결과를 새 문자열로 돌려주지 않고 DOM 노드를 그 자리에서 고치는 모드)에서 생기는 문제였다. 이 프로젝트는 문자열을 받아 문자열을 돌려주는 기본 방식만 써서 해당하지 않지만, 고친 3.4.16도 2주가 지났기에 3.4.16으로 올렸다(`--save-exact`로 버전 고정). 이후 `npm audit`은 0건이다. "오래된 버전이 더 안전하다"가 아니라, **새로 나온 버전을 며칠 피하되 알려진 취약점은 고친 버전을 고른다**는 두 기준을 함께 본다([26](./26-wysiwyg-editor-tiptap.md)의 버전 고르기와 같은 기준).

**확인.** 스텝 6 확인 때 헤드리스 Chrome으로 글 상세를 열어, 서버가 정화해 저장한 본문(제목, 굵게, 링크, 목록, 인용, 코드 블록)이 DOMPurify를 거친 뒤에도 그대로 보이는 것을 봤다. 두 허용 목록이 맞으면 정상 서식은 2차 정화에서 사라지지 않는다.

---

## 6. 자주 하는 실수와 함정

1. **정규식이나 `replace`로 직접 정화한다.** HTML 파싱 규칙을 다 흉내 낼 수 없다. 검증된 라이브러리를 쓴다.
2. **프론트(DOMPurify)에서만 정화한다.** API를 직접 부르면 우회된다. 서버 정화가 필수다.
3. **저장할 때만 정화하고 정책을 바꾼 뒤 옛 데이터를 잊는다.** 정책을 넓혔다 좁히면 옛 데이터에는 이전 정책의 HTML이 남아 있다. 출력 쪽 DOMPurify가 이런 경우의 보조 방어다.
4. **`href`에 프로토콜 제한만 둔다.** 상대 주소, 프로토콜 상대 주소(`//evil.example`)가 남을 수 있다. 이 프로젝트는 정규식으로 절대 http(s)만 받는다.
5. **본문이 아닌 곳에 `dangerouslySetInnerHTML`을 쓴다.** 제목·댓글은 `{값}`으로 넣는다.
6. **CSP에 `'unsafe-inline'`을 `script-src`에 넣는다.** CSP의 XSS 방어 효과가 대부분 사라진다.
7. **CSP가 있으니 정화를 느슨하게 한다.** CSP는 두 번째 방어선이다. 오래된 브라우저, 잘못된 설정, 스크립트 외의 공격(가짜 폼, 화면 위장)이 있다.
8. **`String.length()`로 글자 수를 센다.** 이모지가 깨진다. 코드 포인트로 센다.
9. **정화 결과가 입력과 같기를 기대한다.** `=`, `@`, `+` 등은 문자 참조로 바뀐다.
10. **에디터에서 서버가 지우는 서식을 켜 둔다.** 쓰는 사람은 밑줄이 보였는데 발행하면 사라져 "버그"로 느낀다. 에디터 기능과 서버 허용 목록을 같이 바꾼다(스텝 5, 5.5).
11. **요약을 정화 전 HTML로 만든다.** 지워질 내용이 목록 요약에 나온다. 정화 → 요약 순서를 지킨다.
12. **DOMPurify를 기본 설정으로만 쓴다.** 스크립트는 막지만 서버가 지운 태그(`<table>`, `style` 속성 등)는 통과시킨다. 서버 허용 목록과 같게 맞춘다(스텝 6, 5.6).
13. **`dangerouslySetInnerHTML`에 정화 함수를 빼고 값을 바로 넣는다.** 서버 정화만 믿게 된다. `sanitizePostHtml(...)`을 거친 값만 넣는다.

---

## 7. 직접 해 보기

### 실습 1: 정화 결과 직접 보기

`HtmlSanitizerTest`에 테스트를 하나 더해서 여러 입력을 넣어 보고 결과를 출력한다.

```java
@Test
void playground() {
    for (String html : List.of(
            "<p style=\"color:red\">빨강</p>",
            "<table><tr><td>표</td></tr></table>",
            "<a href=\"//evil.example\">프로토콜 상대 주소</a>",
            "<img src=\"/uploads/abc.PNG\">",
            "<code class=\"language-c++\">x</code>")) {
        System.out.println(html + "  =>  " + sanitizer.sanitize(html));
    }
}
```

```bash
./mvnw test -Dtest=HtmlSanitizerTest#playground
```

각 결과가 왜 그렇게 나오는지 5.1의 정책 줄과 연결해 설명해 본다. 끝나면 테스트를 지운다.

### 실습 2: 허용 목록 바꿔 보기

정책에 `.allowElements("u")`를 더하면 `<u>밑줄</u>`이 남는지 확인한다. 반대로 `.allowAttributes("href").matching(LINK_HREF)`를 `.allowAttributes("href")`로 바꾸면 `keepsOnlyHttpLinksWithSafeRel` 테스트의 어느 단언이 깨지는가(상대 주소 `/relative`가 남는다)? 되돌린다.

### 실습 3: CSP가 막는 것 보기

1. `./scripts/build-frontend.sh && ./mvnw spring-boot:run`
2. `http://blog.test:8080`을 열고 개발자 도구 콘솔에서:
   ```js
   const img = document.createElement('img'); img.src = 'x'; img.setAttribute('onerror', 'console.log("실행됨")'); document.body.append(img)
   ```
3. "실행됨"이 찍히지 않고 콘솔에 CSP 위반 메시지(`Refused to execute inline event handler...`)가 보인다.
4. 같은 것을 Vite 개발 서버(`http://localhost:5173`, CSP 없음)에서 하면 "실행됨"이 찍힌다. 차이가 곧 CSP의 효과다.

### 실습 4: 응답 헤더 확인

```bash
curl -s -D - -o /dev/null localhost:8080/ | grep -i content-security
curl -s -D - -o /dev/null -X POST localhost:8080/api/x | grep -i content-security   # 아무것도 안 나옴(5.3 주의)
```

### 실습 5: 이모지 자르기

`SummaryExtractorTest.doesNotSplitEmoji`를 읽고, `extract` 안의 `offsetByCodePoints`를 `MAX_LENGTH - 1`(char 기준 자르기)로 바꿔 돌려 본다. 어떤 단언이 깨지는가? 되돌린다.

---

### 실습 6 (스텝 5): API로 위험한 본문을 직접 발행해 보기

서버를 띄우고 로그인 쿠키를 받은 뒤([21](./21-signup-login.md) 실습) 에디터를 거치지 않고 보낸다.

```bash
curl -s --resolve alpha.blog.test:8080:127.0.0.1 -b jar -X POST http://alpha.blog.test:8080/api/posts \
  -H 'X-Requested-With: XMLHttpRequest' -H 'Content-Type: application/json' -H "Idempotency-Key: $(uuidgen)" \
  -d '{"title":"XSS 시험","contentHtml":"<p onmouseover=\"alert(1)\">안녕</p><img src=x onerror=alert(1)>","visibility":"PRIVATE","status":"PUBLISHED"}'
# 응답의 id로 편집용 글을 열어 저장된 본문을 본다
curl -s --resolve alpha.blog.test:8080:127.0.0.1 -b jar http://alpha.blog.test:8080/api/manage/posts/{id}
```

기대: `contentHtml`이 `<p>안녕</p>`만 남는다. 공개 범위를 비공개로 해 두면 시험 글이 남에게 보이지 않는다.

### 실습 7 (스텝 6): 화면 쪽 정화를 직접 보기

브라우저에서 아무 글 상세를 열고 개발자 도구 콘솔에서 DOMPurify가 하는 일을 흉내 내 본다. 프론트 개발 서버(`npm run dev`)라면 모듈을 바로 불러올 수 있다.

```js
const { sanitizePostHtml } = await import('/src/app/sanitize.ts')
sanitizePostHtml('<p onclick="x()">a</p><a href="javascript:alert(1)">b</a><table><tr><td>c</td></tr></table>')
// 기대: '<p>a</p><a>b</a>c' — onclick, javascript: 주소, 허용 목록에 없는 table 태그가 지워지고 글자는 남는다
```

그다음 `sanitize.ts`에서 `ALLOWED_TAGS`에 `'table', 'tr', 'td'`를 잠시 넣고 다시 불러 보면 표가 남는다. 서버 허용 목록과 어긋난 상태가 어떤 것인지 보는 실습이다. 끝나면 되돌린다.

## 8. 확인 문제

1. 저장형, 반사형, DOM 기반 XSS의 차이를 "악성 코드가 어디에 있나"로 설명하라.
<details><summary>답</summary>

저장형: 서버 DB에 저장되어 그 데이터를 보는 모든 사람에게 실행. 반사형: 요청(URL 등)에 들어 있고 서버 응답에 그대로 반사되어 실행. DOM 기반: 서버를 거치지 않고 프론트 코드가 URL 등을 읽어 DOM에 넣으면서 실행.
</details>

2. 글 제목은 이스케이프하고, 글 본문은 정화하는 이유는?
<details><summary>답</summary>

제목은 서식이 필요 없으니 글자로만 보이면 된다(이스케이프). 본문은 굵게·목록 등 HTML이 실제로 동작해야 하므로 이스케이프할 수 없고, 허용한 태그·속성만 남기는 정화를 한다.
</details>

3. "`<script>`만 지우면 된다"는 방식이 실패하는 예를 두 가지 들라.
<details><summary>답</summary>

이벤트 속성(`<img src=x onerror=...>`), `javascript:` URL(`<a href="javascript:...">`), `<svg onload=...>`, 엔티티로 숨긴 스킴 등. 차단 목록은 새 방법을 따라갈 수 없다.
</details>

4. 정책에서 `allowUrlProtocols("http", "https")`만 두고 `href`의 정규식을 빼면 무엇이 통과하는가?
<details><summary>답</summary>

상대 주소(`/relative`)처럼 프로토콜이 없는 URL이 통과한다. 이 프로젝트는 "링크는 http/https만"을 지키려고 절대 주소 정규식을 함께 둔다.
</details>

5. `rel="noopener"`가 막는 공격은?
<details><summary>답</summary>

링크로 연 새 창이 `window.opener`로 원래 탭에 접근해 다른 페이지(가짜 로그인 화면 등)로 바꾸는 공격(reverse tabnabbing).
</details>

6. CSP `script-src 'self'`(unsafe-inline 없음)가 막는 것 세 가지는?
<details><summary>답</summary>

인라인 `<script>` 블록, `onerror=` 같은 이벤트 속성, `javascript:` URL 실행.
</details>

7. 서버 정화가 있는데 프론트에서 DOMPurify를, 그리고 CSP를 또 두는 이유는?
<details><summary>답</summary>

방어를 여러 겹으로 둔다(defense in depth). 정화 라이브러리의 취약점, 정책 변경 전의 옛 데이터, 서버를 거치지 않은 데이터 경로가 있을 수 있다. CSP는 그래도 들어온 스크립트의 실행을 브라우저가 막는다.
</details>

8. 요약을 300자로 자를 때 `String.length()`가 아니라 코드 포인트로 세는 이유는?
<details><summary>답</summary>

이모지 같은 문자는 UTF-16 char 두 개라 length로 세면 실제 글자 수와 다르고, 중간을 자르면 깨진 문자가 생긴다. MySQL utf8mb4 VARCHAR(300)도 문자 단위로 센다.
</details>

---

9. (스텝 5) 글 요약을 정화하기 전의 HTML에서 만들면 어떤 문제가 생기나?
<details><summary>답</summary>정화하면 지워질 내용(예: <code>&lt;script&gt;</code> 안의 글자, 이벤트 속성에 넣은 문장)이 목록의 요약에 그대로 나올 수 있다. 그래서 <code>PostService</code>는 정화된 본문으로 요약을 만든다.</details>

10. (스텝 5) 에디터에서 밑줄 버튼을 켜 두면 어떻게 되나?
<details><summary>답</summary>에디터에는 밑줄이 보이지만 서버 허용 목록에 <code>&lt;u&gt;</code>가 없어서 저장할 때 지워진다. 쓰는 사람은 서식이 사라진 것으로 느낀다. 그래서 에디터 기능을 허용 목록에 맞춰 끈다.</details>

11. (스텝 6) React의 `{post.title}`과 `dangerouslySetInnerHTML`은 Thymeleaf의 무엇에 해당하고, 어느 쪽에 정화한 값만 넣어야 하나?
<details><summary>답</summary><code>{post.title}</code>은 이스케이프하는 <code>th:text</code>, <code>dangerouslySetInnerHTML</code>은 이스케이프하지 않는 <code>th:utext</code>에 해당한다. HTML로 해석되는 <code>dangerouslySetInnerHTML</code>(<code>th:utext</code>)에는 정화한 값만 넣는다. 이 프로젝트는 본문에만 쓰고 <code>sanitizePostHtml</code>을 거친다.</details>

12. (스텝 6) DOMPurify의 허용 태그를 서버 `HtmlSanitizer`와 같게 맞춘 이유는?
<details><summary>답</summary>DOMPurify 기본값은 서버보다 넓어서, 서버를 거치지 않은 데이터나 옛 데이터에 있는 서버 미허용 태그·속성(<code>&lt;table&gt;</code>, <code>style</code> 등)이 화면에 나올 수 있다. 같게 맞추면 "서버가 허용한 것만 화면에 나온다"가 화면 쪽에서도 지켜지고, 정상 서식은 2차 정화에서 사라지지 않는다.</details>

13. (스텝 6) 3.4.15를 설치했다가 3.4.16으로 바꾼 이유와, 이 프로젝트가 그 권고에 해당하지 않았는데도 올린 이유는?
<details><summary>답</summary><code>npm audit</code>이 3.4.15 이하에 <code>IN_PLACE</code> 모드 관련 보안 권고 두 건을 알렸다. 이 프로젝트는 문자열을 돌려받는 기본 방식만 써서 직접 해당하지는 않지만, 고친 3.4.16도 나온 지 2주가 지나 "새 버전 피하기" 기준을 함께 만족했기 때문에 알려진 취약점이 없는 버전으로 올렸다.</details>

## 9. 더 읽을거리

- OWASP, *Cross Site Scripting Prevention Cheat Sheet*: https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html
- OWASP, *DOM based XSS Prevention Cheat Sheet*
- OWASP Java HTML Sanitizer 프로젝트: https://github.com/OWASP/java-html-sanitizer
- MDN, *Content Security Policy (CSP)*: https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP
- MDN, *rel=noopener*, *rel=noreferrer*
- React 문서, *dangerouslySetInnerHTML*
- DOMPurify: https://github.com/cure53/DOMPurify (설정 옵션 `ALLOWED_TAGS`, `ALLOWED_ATTR`, `ALLOWED_URI_REGEXP`)
- Thymeleaf 문서, *Unescaped Text* (`th:utext`)
- jsoup 문서, *Element.text()*
- 이어서 읽기: [13-csrf-samesite-cors](./13-csrf-samesite-cors.md), [12-spring-security-filter-chain](./12-spring-security-filter-chain.md)
