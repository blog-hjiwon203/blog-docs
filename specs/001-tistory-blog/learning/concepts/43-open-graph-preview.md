# 43. 글 공유 미리보기: Open Graph와 서버가 넣는 메타 태그

> 관련 스텝: [스텝 11](../step-11.md) (T072) · 관련 개념: [18-spa-server-routing](./18-spa-server-routing.md), [14-xss-sanitize-csp](./14-xss-sanitize-csp.md), [16-authorization-visibility](./16-authorization-visibility.md), [28-thymeleaf-to-react](./28-thymeleaf-to-react.md), [30-image-upload](./30-image-upload.md)

## 1. 이 문서로 배우는 것

- 메신저·SNS에 링크를 붙이면 나오는 **미리보기 카드**는 어떻게 만들어지나: 링크 미리보기 봇과 **Open Graph** 태그
- **SPA의 약점**: 봇은 자바스크립트를 실행하지 않아 React가 그린 제목을 못 본다. 그래서 **서버가 HTML에 직접** 넣는다
- `og:title`, `og:description`, `og:image`, `og:url`, `og:type`, `og:site_name`, `twitter:card`
- 사용자가 쓴 글자를 HTML 속성에 넣을 때의 **이스케이프**(XSS)
- `og:image`·`og:url`은 **절대 주소**여야 하는 이유
- 응답 헤더의 **charset**: HTML 안 `<meta charset>`만으로는 부족할 때
- **볼 수 없는 글은 미리보기도 없다**: 봇은 비회원이다

**먼저 알면 좋은 것**: 서버가 화면 주소에 `index.html`을 주는 방식([18](./18-spa-server-routing.md)), XSS와 이스케이프([14](./14-xss-sanitize-csp.md)), 서버 렌더링과 클라이언트 렌더링의 차이([28](./28-thymeleaf-to-react.md)).

## 2. 왜 필요한가

카카오톡이나 슬랙에 `alpha.blog.com/12`를 붙이면, 보통 제목·요약·사진이 든 카드가 뜬다. 스텝 11 전에는 이 블로그 링크를 붙이면 제목이 **"블로그"**(모든 화면 공통인 `index.html`의 `<title>`)뿐이었다.

```html
<!-- 스텝 11 전 /12 응답 -->
<title>블로그</title>
<div id="root"></div>   ← 글 제목·본문은 브라우저에서 React가 API를 불러 그린다
```

사람의 브라우저는 자바스크립트를 실행해 글을 그리지만, 미리보기를 만드는 서버(봇)는 **HTML만 받아 보고 자바스크립트는 실행하지 않는다**(대부분의 링크 미리보기 봇이 그렇다). 그래서 봇에게는 모든 글이 "블로그"라는 같은 빈 페이지다. Thymeleaf처럼 서버가 HTML을 다 그려 주는 방식이었다면 처음부터 제목이 들어 있었을 것이다([28](./28-thymeleaf-to-react.md)). SPA는 이 부분을 따로 챙겨야 한다.

## 3. 기본 개념

### 3.1 Open Graph

**Open Graph**는 페이스북이 만든 약속으로, `<head>`에 `<meta property="og:…">`를 넣어 "이 페이지를 공유하면 이렇게 보여 달라"고 알린다. 카카오톡·슬랙·디스코드 등 대부분이 읽는다.

| 태그 | 뜻 | 이 프로젝트 값 |
| --- | --- | --- |
| `og:type` | 페이지 종류 | `article` |
| `og:site_name` | 사이트 이름 | 블로그 이름 |
| `og:title` | 카드 제목 | 글 제목 |
| `og:description` | 카드 설명 | 글 요약(본문 앞부분, `post.summary`) |
| `og:image` | 카드 사진 | 대표 이미지 = 본문 첫 이미지의 썸네일(절대 주소) |
| `og:url` | 이 페이지의 대표 주소 | `http(s)://{주소}.blog.com/{id}` |
| `twitter:card` | X(트위터) 카드 모양 | 사진이 있으면 `summary_large_image`, 없으면 `summary` |

함께 `<title>`도 "글 제목 - 블로그 이름"으로 바꾸고, 검색 엔진용 `<meta name="description">`도 넣는다.

### 3.2 서버가 HTML에 넣기

화면 주소(`/12`)는 원래도 서버가 먼저 받는다. 블로그·글이 있는지 확인하고 `index.html`을 준다([18](./18-spa-server-routing.md), `SpaForwardController`). 그 자리에서 `index.html` 글자를 읽어 `</head>` 바로 앞에 태그를 끼워 넣으면 된다. React 앱은 그대로 돌고, 봇은 넣어 준 태그를 읽는다.

다른 방법으로는 서버 렌더링(SSR, 예: Next.js)이나 미리 렌더링(prerender)이 있다. 이 프로젝트는 미리보기에 필요한 것이 태그 몇 개라 가장 단순한 "글자 끼워 넣기"를 골랐다.

### 3.3 속성 값은 이스케이프한다

제목은 사용자가 쓴 글자다. 제목이 `"><script>alert(1)</script>`라면?

```html
<meta property="og:title" content=""><script>alert(1)</script>">   ← 이스케이프 안 하면 스크립트가 끼어든다
<meta property="og:title" content="&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt;">   ← 이스케이프하면 글자일 뿐
```

이 HTML은 사람의 브라우저도 받으므로, 이스케이프하지 않으면 그대로 **저장형 XSS**가 된다([14](./14-xss-sanitize-csp.md)). `"`, `<`, `>`, `&`를 엔티티(`&quot;`, `&lt;`, `&gt;`, `&amp;`)로 바꾼다. Spring의 `HtmlUtils.htmlEscape`가 해 준다.

### 3.4 절대 주소와 charset

- **절대 주소**: 봇은 이 HTML을 다른 서버에서 받아 처리한다. `/uploads/t_a.png` 같은 상대 주소는 어느 사이트 기준인지 몰라 사진을 못 가져오는 경우가 많다. `og:image`·`og:url`은 `http://alpha.blog.test:8080/uploads/t_a.png`처럼 쓴다.
- **charset**: 응답 헤더가 `Content-Type: text/html`(인코딩 없음)이면, 헤더만 보는 프로그램은 다른 인코딩(ISO-8859-1 등)으로 읽어 한글이 깨질 수 있다. 브라우저는 HTML 안의 `<meta charset="UTF-8">`을 보고 맞게 읽지만, 봇이 다 그렇다는 보장은 없다. 헤더를 `text/html;charset=UTF-8`로 보낸다.

charset 문제는 실제로 테스트에서 드러났다. 테스트 도구(MockMvc)가 헤더에 인코딩이 없어 ISO-8859-1로 읽었고, 미리보기 한글이 `ì ëª©`처럼 깨져 단언이 실패했다. 태그는 맞게 들어가 있었지만, 헤더를 고쳐야 할 이유가 그렇게 보였다.

### 3.5 봇은 비회원이다

미리보기 봇은 로그인하지 않는다. 그래서 **비회원이 볼 수 있는 글만** 미리보기를 만든다.

- 비공개 글: 주인이 자기 글 주소를 열어도 미리보기 태그를 넣지 않는다. 넣으면 주인이 그 링크를 어딘가에 붙였을 때 비공개 글의 제목·요약이 카드로 퍼진다.
- 구독자 공개·숨긴 글·없는 글: 넣지 않는다.

"볼 수 없는 글은 어디에도 내용이 나오지 않는다"(헌법 원칙 II, [16](./16-authorization-visibility.md))를 미리보기에도 적용한 것이다.

## 4. 동작 원리

```
GET http://alpha.blog.test:8080/12   (브라우저든 봇이든)
  SpaForwardController.page → blogPage
    블로그 확인, /12는 글 주소
    PostVisibilityPolicy.decide(12, blog, 보는 사람)
      볼 수 없음 → 404 화면 / 다른 블로그 글 → 301 / 구독자 공개 → 그냥 index.html
      볼 수 있음(주인 포함) → postPage
        PostPreviewService.preview(blog, 12)
          decide(12, blog, null)  ← 비회원 기준으로 다시
            Visible이 아니면 빈 값 → 그냥 index.html
            Visible → 제목·요약·첫 이미지 썸네일·블로그 이름
        index.html 글자를 읽어
          <title>을 "제목 - 블로그 이름"으로
          </head> 앞에 og:… 태그 (값은 이스케이프, 주소는 절대)
  ← 200, Content-Type: text/html;charset=UTF-8
```

## 5. 이 프로젝트에서는

### 5.1 `post/application/PostPreviewService.java`

```java
@Transactional(readOnly = true)
public Optional<PostPreview> preview(Blog blog, Long postId) {
    if (!(postVisibilityPolicy.decide(postId, blog, null) instanceof PostAccess.Visible visible)) {
        return Optional.empty();
    }
    Post post = visible.post();
    String image = postThumbnails.of(List.of(post)).get(post.getId());
    return Optional.of(new PostPreview(post.getId(), post.getTitle(), post.getSummary(), image, blog.getName()));
}
```

- `decide(postId, blog, null)`: 보는 사람을 `null`(비회원)로 넘겨 **봇의 눈**으로 판단한다. 글 상세와 같은 가시성 판단을 재사용한다([16](./16-authorization-visibility.md)).
- `instanceof PostAccess.Visible visible`: 패턴 매칭. `Visible`일 때만 그 안의 글을 `visible`로 꺼내 쓴다. 주인(`Owner`)·구독자 공개(`SubscribersOnly`)·없음(`NotFound`)은 모두 빈 값.
- 이미지는 목록 썸네일과 같은 규칙(본문 첫 이미지의 썸네일, [30](./30-image-upload.md) `PostThumbnails`). 대표 이미지 고르기(POST-07)가 생기면 여기만 바꾸면 된다.

### 5.2 `global/config/SpaForwardController.java`

```java
private ResponseEntity<Resource> postPage(HttpServletRequest request, Blog blog, Long postId) {
    return postPreviewService.preview(blog, postId)
            .map(preview -> html(HttpStatus.OK, withPreview(indexHtml(), preview, request, blog)))
            .orElseGet(() -> app(HttpStatus.OK));
}

private String withPreview(String html, PostPreview preview, HttpServletRequest request, Blog blog) {
    String title = preview.title() + " - " + preview.blogName();
    StringBuilder tags = new StringBuilder()
            .append(meta("og:type", "article"))
            .append(meta("og:site_name", preview.blogName()))
            .append(meta("og:title", preview.title()))
            .append(meta("og:url", blogHostResolver.blogUrl(request, blog, "/" + preview.postId())));
    ...
    if (preview.imagePath() != null) {
        tags.append(meta("og:image", blogHostResolver.blogUrl(request, blog, preview.imagePath())));
    }
    ...
    String titleTag = "<title>" + HtmlUtils.htmlEscape(title) + "</title>";
    return html.replaceFirst("<title>[^<]*</title>", Matcher.quoteReplacement(titleTag))
            .replace("</head>", tags + "</head>");
}

private static String meta(String property, String content) {
    return "<meta property=\"" + property + "\" content=\"" + HtmlUtils.htmlEscape(content) + "\">\n";
}
```

- `Optional.map(...).orElseGet(...)`: 미리보기가 있으면 태그를 넣은 HTML, 없으면 원래 `index.html`.
- `meta(...)`: 모든 값이 `HtmlUtils.htmlEscape`를 거친다(3.3). 태그 이름(`og:title`)은 우리가 정한 글자라 그대로 둔다.
- `blogHostResolver.blogUrl(request, blog, 경로)`: 요청의 scheme·포트를 살려 `http://alpha.blog.test:8080/…` 같은 절대 주소를 만든다(3.4). 이사 301에서 쓰던 그 메서드다.
- `replaceFirst("<title>[^<]*</title>", Matcher.quoteReplacement(titleTag))`: 제목에 `$`나 `\`가 있으면 `replaceFirst`가 그것을 정규식 치환 기호로 해석해 버린다. `Matcher.quoteReplacement`로 글자 그대로 넣는다.
- `.replace("</head>", tags + "</head>")`: `</head>` 바로 앞에 끼워 넣는다. `replace`는 정규식이 아니라 글자 그대로 바꾼다.
- `indexHtml()`: 빌드된 `static/index.html`을 매 요청 읽는다. 프론트를 다시 빌드하면 바로 반영된다. 빌드가 없으면(백엔드만 띄운 개발 중) 안내용 HTML에 넣는다. 안내 HTML에도 `<head>`가 있게 바꿔서, 프론트 빌드가 없는 테스트 환경에서도 미리보기를 확인할 수 있다.

```java
private static final MediaType HTML_UTF8 = new MediaType(MediaType.TEXT_HTML, StandardCharsets.UTF_8);
```

모든 HTML 응답의 `Content-Type`을 이것으로 바꿨다(3.4).

### 5.3 테스트

| 테스트 (`SpaForwardIntegrationTest`) | 확인하는 것 |
| --- | --- |
| `publicPostPageCarriesEscapedOpenGraphTags` | 제목에 `<b>`·`"`·`<script>`, 요약에 `&`를 넣은 공개 글 → 모든 값이 엔티티로 바뀌어 들어가고 `<script>alert(1)` 글자는 HTML에 없음. `og:url`·`og:image`가 절대 주소, `<title>`도 바뀜 |
| `postsOthersCannotSeeGetNoPreviewEvenForTheOwner` | 비공개 글을 주인이 열어도, 구독자 공개 글, 블로그 메인에는 `og:title`이 없음 |

실서버에서도 `curl -s -D - http://{주소}.blog.test:8081/15`로 `Content-Type: text/html;charset=UTF-8`과 태그를 확인했다(긴 요약의 `…`은 `&hellip;`로 들어간다).

## 6. 자주 하는 실수와 함정

- **SPA에서 React로 `<title>`·메타 태그를 바꾸고 끝낸다.** 브라우저 탭 제목은 바뀌지만 봇은 자바스크립트를 실행하지 않아 못 본다.
- **사용자 글자를 이스케이프 없이 속성에 넣는다.** 저장형 XSS. 모든 값을 이스케이프한다.
- **상대 주소를 `og:image`에 넣는다.** 사진이 안 나온다.
- **로그인한 사람 기준으로 미리보기를 만든다.** 주인이 비공개 글 링크를 붙이면 제목이 새어 나간다. 비회원 기준.
- **`replaceFirst`에 사용자 글자를 그대로 치환 문자열로 넣는다.** `$1` 같은 글자가 깨진다. `Matcher.quoteReplacement`.
- **헤더에 charset이 없다.** 일부 도구가 한글을 깨뜨린다.
- **미리보기를 바꿨는데 카드가 그대로다.** 메신저들은 미리보기를 한동안 캐시한다(카카오·페이스북 등은 캐시를 지우는 도구를 따로 둔다). 서버 문제가 아닐 수 있다.

## 7. 직접 해 보기

```bash
# 공개 글
curl -s -D - http://{주소}.blog.test:8080/{공개 글 id} | grep -iE "content-type|og:|<title>"
# 비공개 글로 바꾼 뒤 → og: 줄이 없어야 한다
```

제목에 `"><b>굵게</b>`를 넣어 발행하고 위 명령으로 보면 `&quot;&gt;&lt;b&gt;`로 들어간 것이 보인다.

외부에서 실제 카드를 보려면 서버가 인터넷에서 닿아야 한다(로컬 `blog.test`는 메신저 서버가 접근할 수 없다). 배포한 뒤 카카오톡 "공유 디버거"나 페이스북 "공유 디버거"에 주소를 넣으면 봇이 본 태그를 보여 준다.

```bash
./mvnw test -Dtest=SpaForwardIntegrationTest
```

## 8. 확인 문제

1. React 앱에서 `document.title`을 글 제목으로 바꾸는데도 링크 미리보기에 "블로그"만 나오는 이유는?
<details><summary>답</summary>미리보기 봇은 HTML만 받고 자바스크립트를 실행하지 않는다. 서버가 준 index.html에는 공통 제목 "블로그"만 있다.</details>

2. 이 프로젝트가 미리보기 태그를 넣는 곳과 방법은?
<details><summary>답</summary>화면 주소를 받는 SpaForwardController가 글 주소면 index.html 글자를 읽어 &lt;/head&gt; 앞에 og 태그를 끼워 넣고 &lt;title&gt;도 바꿔서 준다.</details>

3. og 값에 HtmlUtils.htmlEscape를 쓰는 이유는?
<details><summary>답</summary>제목·요약·블로그 이름은 사용자가 쓴 글자라 "나 &lt;가 있으면 태그를 깨고 스크립트가 끼어든다(저장형 XSS). 엔티티로 바꿔 글자로만 들어가게 한다.</details>

4. og:image와 og:url을 절대 주소로 쓰는 이유는?
<details><summary>답</summary>봇이 다른 서버에서 HTML을 처리하므로 상대 주소는 어느 사이트 기준인지 몰라 사진·주소를 못 쓴다.</details>

5. 주인이 자기 비공개 글을 열 때도 미리보기를 넣지 않는 이유는?
<details><summary>답</summary>미리보기는 봇(비회원)이 보는 것이다. 주인 기준으로 넣으면 그 링크를 어딘가에 붙였을 때 비공개 글의 제목·요약이 카드로 퍼진다. 그래서 비회원 기준(decide(…, null))으로 판단한다.</details>

6. 응답 헤더에 charset=UTF-8을 붙인 이유와, 그것이 드러난 계기는?
<details><summary>답</summary>헤더에 인코딩이 없으면 헤더만 보는 프로그램이 다른 인코딩으로 읽어 한글이 깨질 수 있다. 테스트 도구가 ISO-8859-1로 읽어 미리보기 한글이 깨지며 단언이 실패해서 드러났다.</details>

7. 제목을 &lt;title&gt;에 넣을 때 Matcher.quoteReplacement가 필요한 이유는?
<details><summary>답</summary>replaceFirst의 치환 문자열에서 $와 \는 특별한 뜻이라, 제목에 그 글자가 있으면 깨지거나 예외가 난다. quoteReplacement로 글자 그대로 넣는다.</details>

## 9. 더 읽을거리

- The Open Graph protocol (ogp.me)
- X(트위터) Cards 문서(`twitter:card`)
- 카카오 개발자 문서, 웹 페이지 스크랩과 공유 디버거
- Spring Framework `HtmlUtils`, `MediaType`
- SPA의 SEO와 미리보기: 서버 렌더링(SSR), 미리 렌더링(prerender), 동적 렌더링
