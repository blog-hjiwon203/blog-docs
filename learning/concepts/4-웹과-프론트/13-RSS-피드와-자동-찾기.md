# RSS 피드와 자동 찾기: 표준대로 쓰고, 읽는 쪽이 고른다

> 관련 스텝: [스텝 26](../../스텝-26.md) (T141~T143) · 관련 개념: [글 공유 미리보기: Open Graph](./12-Open-Graph-공유-미리보기.md), [SPA와 서버 라우팅](./06-SPA와-서버-라우팅.md), [인가와 가시성](../3-보안/07-인가와-가시성.md), [XSS 방어 본문 정화와 CSP](../3-보안/06-XSS-방어-본문-정화와-CSP.md), [카테고리 계층](../2-데이터/08-카테고리-계층.md), [Spring 테스트](../1-개발-환경과-배포/04-Spring-테스트.md)

## 1. 이 문서로 배우는 것

- **피드**가 무엇이고, 사이트가 왜 피드를 내는지: 사람 대신 프로그램이 "새 글"을 가져가는 통로
- **RSS 2.0**의 모양: `rss` → `channel` → `item`, 칸마다의 뜻(`title`, `link`, `description`, `guid`, `pubDate`, `category`)
- RSS 2.0이 **정하지 않는 것**과, 그 빈칸을 메우는 다른 표준들: **Content 모듈**(`content:encoded`), **자동 찾기**(`<link rel="alternate">`), **Atom**(RFC 4287)
- **표준을 지켜도 서로 어긋나는 이유**: 표준은 칸의 모양과 뜻을 정하고, 어느 칸을 읽을지는 읽는 쪽이 정한다
- SPA에서 자동 찾기 태그를 **서버가** 넣어야 하는 이유(Open Graph와 같은 이유)
- XML을 손으로 이어 붙이지 않고 **StAX**로 쓰기, XML에 넣을 수 없는 글자, RFC 822 날짜와 시간대
- 피드는 **비회원 기준**: 로그인한 주인이 열어도 비공개 글이 섞이지 않아야 하는 이유

**먼저 알면 좋은 것**: 서버가 화면 주소에서 `index.html`을 주는 방식([SPA와 서버 라우팅](./06-SPA와-서버-라우팅.md)), `index.html`의 head에 서버가 태그를 끼워 넣는 방법([Open Graph](./12-Open-Graph-공유-미리보기.md)), 비회원이 볼 수 있는 글의 조건([인가와 가시성](../3-보안/07-인가와-가시성.md)).

## 2. 왜 필요한가

지원이 만드는 다른 앱(LOLog)이 여러 블로그의 글을 가져와 쓰려고 한다. 티스토리·네이버 블로그는 블로그마다 RSS 주소가 있어서, 앱은 그 주소를 주기적으로 읽어 새 글을 찾는다. now-log에는 그런 통로가 없었다. 앱이 글을 가져가려면 블로그 화면 HTML을 긁어야 하는데, now-log 화면은 React가 그리므로 HTML에는 글이 없다([SPA와 서버 라우팅](./06-SPA와-서버-라우팅.md)). API(`/api/posts`)는 now-log 화면 전용 모양이라 다른 프로그램이 쓰라고 약속한 것이 아니다.

**피드**는 "이 사이트의 최근 글 목록"을 프로그램이 읽기 좋은 모양(XML)으로 내놓은 주소다. 피드 리더(Feedly, Inoreader, Thunderbird 등)와 다른 서비스가 모두 같은 표준을 읽으므로, now-log가 표준대로 피드를 내면 특정 앱 하나가 아니라 피드를 읽는 모든 프로그램이 now-log 블로그를 구독할 수 있다.

## 3. 기본 개념

### 3.1 RSS 2.0의 모양

RSS 2.0은 RSS Advisory Board가 관리하는 명세다. XML 문서 하나가 블로그 하나다.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>                         ← 블로그(사이트) 하나
    <title>소소한 하루</title>        ← 필수
    <link>https://now-log.java21.net/@my-daily</link>   ← 필수
    <description>평범한 날들의 기록</description>        ← 필수
    <item>                          ← 글 하나. 여러 개
      <title>9월 한 달 회고</title>
      <link>https://now-log.java21.net/@my-daily/44</link>
      <guid isPermaLink="true">https://now-log.java21.net/@my-daily/44</guid>
      <pubDate>Thu, 15 Oct 2026 13:59:27 +0900</pubDate>
      <category>일상/회고</category>
      <description>9월이 끝났어요. …</description>
    </item>
  </channel>
</rss>
```

| 칸 | 뜻 (RSS 2.0) | 필수 |
| --- | --- | --- |
| `channel/title`·`link`·`description` | 사이트 이름, 사이트 주소, 사이트 설명 | 셋 다 필수 |
| `item/title` | 글 제목 | `title`이나 `description` 중 하나는 있어야 한다 |
| `item/link` | 글 주소 | 선택 |
| `item/description` | 글의 **요약(synopsis)**. HTML을 이스케이프해서 넣을 수 있다 | 선택 |
| `item/guid` | 글마다 유일한 값. `isPermaLink="true"`(기본값)면 그 값이 글 주소다 | 선택 |
| `item/pubDate` | 글을 쓴 시각, **RFC 822** 날짜 형식 | 선택 |
| `item/category` | 분류. 여러 번 쓸 수 있고, 값은 `/`로 나눈 **계층 경로**로 쓸 수 있다 | 선택 |

`item` 아래 칸은 모두 선택이다. 그래서 "RSS 2.0을 지켰다"는 말만으로는 피드에 무엇이 들어 있는지 알 수 없다. 이것이 3.3의 이야기다.

### 3.2 RSS 2.0의 빈칸을 메우는 표준들

**Content 모듈의 `content:encoded`**: RSS 2.0에는 "전체 본문" 칸이 따로 없다. `description`은 요약이라고 되어 있다. 그래서 RSS 1.0 시절 만든 Content 모듈(`http://purl.org/rss/1.0/modules/content/`)의 `content:encoded`에 전체 본문 HTML을 넣는 방식이 널리 쓰인다. 다른 이름공간(namespace)의 요소라 RSS 2.0 문서에 그대로 섞어 쓸 수 있다.

```xml
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
  …
  <description>요약 300자</description>
  <content:encoded>&lt;p&gt;전체 본문&lt;/p&gt;</content:encoded>
```

**자동 찾기(Autodiscovery)**: 사람은 보통 피드 주소가 아니라 블로그 주소를 안다. 블로그 주소를 받은 프로그램이 피드 주소를 찾는 방법은 HTML 표준(WHATWG)의 `rel="alternate"` 링크다. RSS Advisory Board의 RSS Autodiscovery 문서도 같은 모양을 정한다.

```html
<head>
  <link rel="alternate" type="application/rss+xml" title="소소한 하루" href="https://now-log.java21.net/@my-daily/rss">
</head>
```

"이 페이지의 다른 표현(alternate)이 이 주소에 RSS 모양으로 있다"는 뜻이다. 리더는 블로그 HTML을 받아 이 태그를 찾고, 없으면 플랫폼마다 아는 규칙(티스토리는 `/rss` 등)으로 추측한다.

**`atom:link rel="self"`**: 피드가 자기 주소를 적어 두는 칸이다. 피드 파일이 복사돼 돌아다녀도 원래 주소를 알 수 있다. RSS Advisory Board가 권하고, W3C 피드 검사기는 이 칸이 없으면 알려 준다.

**Atom(RFC 4287)**: RSS의 모호한 곳을 고치려고 IETF가 만든 다른 피드 형식이다. 요약(`summary`)과 본문(`content`)을 처음부터 나누고, 글 고유값(`id`)과 시각(`updated`, 시간대 필수)을 필수로 둔다. `category`에는 어느 분류 체계인지(`scheme`)를 붙일 수 있어 카테고리와 태그를 구별할 수도 있다. now-log는 RSS 2.0 + Content 모듈로 같은 정보를 담을 수 있어서 Atom은 내지 않았다(research R-19).

### 3.3 표준을 지켜도 어긋나는 이유: 칸은 쓰는 쪽, 고르기는 읽는 쪽

표준은 **칸의 모양과 뜻**을 정한다. **어느 칸을 읽을지**는 읽는 쪽이 정한다. 그래서 쓰는 쪽과 읽는 쪽이 둘 다 표준을 지켜도 결과가 어긋날 수 있다.

| 쓰는 쪽(블로그) | 읽는 쪽 A: `description`만 읽음 | 읽는 쪽 B: `content:encoded` 먼저, 없으면 `description` |
| --- | --- | --- |
| 티스토리(전체 공개 설정): `description`에 본문 전체 | 본문 전체 | 본문 전체 |
| WordPress: `description` 요약, `content:encoded` 본문 | **요약만** | 본문 전체 |
| now-log: `description` 요약, `content:encoded` 본문 | **요약만** | 본문 전체 |

A처럼 읽는 프로그램에 맞추겠다고 now-log가 `description`에 본문 전체를 넣으면, 이번에는 일반 리더 목록의 요약 자리에 글 전체가 나온다. 한 앱에 맞추면 표준의 뜻이 비틀린다. 그래서 일을 이렇게 나눈다.

- **쓰는 쪽**: 표준이 마련한 칸을 **뜻에 맞게, 빠짐없이** 채운다. 요약은 요약 칸, 본문은 본문 칸에 넣는다.
- **읽는 쪽**: **좋은 칸부터** 찾고 없으면 다음 칸으로 넘어간다(B). 이렇게 읽으면 어느 블로그든 맞는다.

다만 읽는 쪽이 고를 수 있는 것은 **쓰는 쪽이 준 것 안에서만**이다. 쓰는 쪽이 꼭 지켜야 하는 것이 남는다.

| 쓰는 쪽 몫 | 안 지키면 읽는 쪽은 |
| --- | --- |
| 전체 본문을 어딘가에 준다 | 요약밖에 못 얻는다 |
| 자동 찾기 태그를 둔다 | 블로그 주소로 피드를 못 찾는다 |
| `category`에 카테고리만 넣는다 | 태그가 섞이면 다시 나눌 수 없다(RSS 2.0에는 태그 칸이 없다) |
| `pubDate`에 시간대를 붙인다 | 몇 시인지 모른다 |
| 비회원이 볼 수 있는 글만 넣는다 | 비공개 글인지 알 길이 없다 |

이 프로젝트에서 실제로 그랬다. LOLog 명세 초안은 "`description`만 쓴다"였고, now-log는 표준대로 `description`에 요약을 넣었다. 둘 다 RSS 2.0이지만 그대로 붙이면 LOLog는 300자 요약으로 카드를 만든다. 지원은 now-log를 LOLog에 맞추지 않고 표준대로 두기로 했다(2026-11-12). 맞추는 일은 읽는 쪽 몫이다. 이렇게 서로 기대하는 칸을 글로 적어 둔 것이 **계약**이다. now-log 쪽 계약은 `contracts/rest-api.md`의 RSS 피드 표다.

### 3.4 피드는 비회원이 본다

피드를 읽는 프로그램은 로그인하지 않는다. 그리고 피드 응답은 리더 서비스·캐시를 거쳐 여러 사람에게 그대로 나눠질 수 있다(`Cache-Control: max-age=300`로 캐시해도 된다고 알리기도 한다). 로그인한 사람마다 다른 피드를 주면, 주인 브라우저로 받은 "비공개 글이 섞인 응답"이 캐시에 남아 남에게 갈 수 있다. 그래서 now-log는 로그인 쿠키가 있어도 **늘 비회원 기준**으로 피드를 만든다. 주인이 자기 블로그 피드를 열어도 비공개·구독자 공개 글은 없다. 기준이 하나면 누가 받아도 같은 응답이라 새어 나갈 것이 없다. 같은 이유로 공유 미리보기도 비회원 기준이다([Open Graph](./12-Open-Graph-공유-미리보기.md) 3.5).

블로그가 다른 사람에게 닫혀 있으면(이용 제한, 주인 정지) 피드는 404다. 블로그 화면도 남에게는 404이므로 같은 규칙이다([인가와 가시성](../3-보안/07-인가와-가시성.md)).

## 4. 동작 원리

```
[리더] GET https://now-log.java21.net/@my-daily          ← 사람이 준 블로그 주소
   → SpaForwardController: 블로그 확인 → 200 index.html
     head에 <link rel="alternate" type="application/rss+xml" href=".../@my-daily/rss"> (다른 사람에게 열린 블로그만)
[리더] HTML에서 alternate 링크를 찾음
[리더] GET https://now-log.java21.net/@my-daily/rss
   → RssFeedController (주소 /@{address}/rss, SpaForwardController보다 구체적이라 여기로)
   → RssFeedService.find("my-daily")
        없음·지움 → 404 / 이사 → 301 /@새주소/rss / 이용 제한·주인 정지 → 404
        PostSpecifications.inBlog + visibleTo(null) → 최신 20개 + 카테고리
   → RssFeedWriter: StAX로 XML, 이미지 /uploads/… → 전체 주소
   ← 200 application/rss+xml;charset=UTF-8, Cache-Control: max-age=300
[리더] guid로 이미 읽은 글은 건너뛰고 새 글만 보여 줌. 몇 분~몇십 분 뒤 다시 읽음
```

**주소 다툼**: `/@my-daily/rss`는 화면 주소 패턴(`/{s1}/{s2}`)에도 맞는다. Spring MVC는 여러 패턴이 맞으면 더 구체적인 쪽을 고른다. `/@{address}/rss`는 변수가 하나이고 나머지가 고정 글자라, 변수가 둘인 화면 패턴보다 구체적이다. 테스트(`RssFeedIntegrationTest`)가 이 주소에서 XML을 받는 것으로 확인한다.

## 5. 이 프로젝트에서는

### 5.1 `rss/application/RssFeedService.java`: 어떤 블로그, 어떤 글

```java
@Transactional(readOnly = true)
public RssFeedLookup find(String address) {
    Optional<Blog> found = blogAddressResolver.findBlog(address);      // ①
    if (found.isEmpty()) {
        return new RssFeedLookup.NotFound();
    }
    Blog blog = found.get();
    if (blog.isMoved()) {                                              // ②
        Blog target = blog.getMovedToBlog();
        return target.isDeleted() ? new RssFeedLookup.NotFound() : new RssFeedLookup.MovedTo(target.getAddress());
    }
    if (!blogVisibilityPolicy.isOpenToOthers(blog)) {                  // ③
        return new RssFeedLookup.NotFound();
    }
    return new RssFeedLookup.Found(new RssFeed(blog.getAddress(), blog.getName(), blog.getDescription(),
            items(blog)));
}
```

- ① 주소 규칙·예약어 검사와 DB 조회는 화면 주소와 같은 `BlogAddressResolver`를 쓴다. `/@admin/rss`도 404다.
- ② 이사한 블로그는 지워졌어도 새 블로그로 보낸다. 화면 주소(`SpaForwardController`)와 같은 순서다. 리더는 301을 따라가 새 주소를 기억한다.
- ③ `isOpenToOthers`는 "삭제 아님, 이용 제한 아님, 주인 정지 아님"이다. `canView(blog, viewerId)`가 아니라 이것을 쓰는 것이 "비회원 기준"이다. 주인이라도 예외가 없다.

```java
private List<RssFeed.Item> items(Blog blog) {
    Specification<Post> condition = PostSpecifications.inBlog(blog.getId())
            .and(PostSpecifications.visibleTo(null, LocalDateTime.now(clock)));   // ④
    List<Post> posts = postRepository.findBy(condition,
            query -> query.sortBy(LATEST).project("category").limit(SIZE).all()); // ⑤
    return posts.stream()
            .map(post -> new RssFeed.Item(post.getId(), post.getTitle(), post.getSummary(), post.getContentHtml(),
                    categoryPath(post.getCategory()), post.getPublishedAt()))
            .toList();
}

static String categoryPath(Category category) {
    if (category == null) {
        return null;
    }
    return category.isChild() ? category.getParent().getName() + "/" + category.getName() : category.getName();  // ⑥
}
```

- ④ `visibleTo(null, now)`: 비회원(`viewerId = null`)이 볼 수 있는 글이다. 전체 공개, 발행됨, 숨김 아님, 비공개 카테고리 아님, 지우지 않음. 목록·검색이 쓰는 조건을 그대로 써서 "목록에 없는데 피드에는 있는 글"이 생기지 않는다([인가와 가시성](../3-보안/07-인가와-가시성.md)).
- ⑤ 최신순(발행 시각, 같으면 번호) 20개. `project("category")`로 카테고리를 함께 읽는다(같은 카테고리 글 목록 `sameCategory`와 같은 방식). `Page`가 아니라 개수 쿼리가 없는 `limit`이다.
- ⑥ RSS 2.0의 `/` 계층 표기다. 카테고리는 두 단계까지라([카테고리 계층](../2-데이터/08-카테고리-계층.md)) 상위 이름 하나만 붙이면 된다. **태그는 피드 어디에도 넣지 않는다.**

모든 칸 값을 트랜잭션 안에서 `RssFeed`(record)로 옮긴다. 화면 쪽은 엔티티를 만지지 않으므로 지연 로딩 오류(`open-in-view: false`)가 생기지 않는다.

### 5.2 `rss/presentation/RssFeedWriter.java`: StAX로 XML 쓰기

XML을 문자열로 이어 붙이면(`"<title>" + title + "</title>"`) 제목에 `<`나 `&`가 들어 있을 때 문서가 깨진다. 이어 붙이는 대신 JDK에 들어 있는 **StAX**(`javax.xml.stream.XMLStreamWriter`)로 요소를 하나씩 쓴다. `writeCharacters`가 `<`·`&` 같은 글자를 이스케이프하므로, 제목은 늘 "글자"로 들어간다. 라이브러리를 더하지 않아도 된다.

```java
XMLStreamWriter xml = FACTORY.createXMLStreamWriter(out, StandardCharsets.UTF_8.name());
xml.writeStartDocument(StandardCharsets.UTF_8.name(), "1.0");
xml.writeStartElement("rss");
xml.writeAttribute("version", "2.0");
xml.writeNamespace("content", CONTENT_NS);          // ① xmlns:content="http://purl.org/rss/1.0/modules/content/"
xml.writeNamespace("atom", ATOM_NS);
xml.writeStartElement("channel");

element(xml, "title", feed.name());
element(xml, "link", urls.blog());
// channel/description은 필수 칸이라 소개글이 없으면 블로그 이름을 쓴다
element(xml, "description", isBlank(feed.description()) ? feed.name() : feed.description());   // ②
```

- ① 이름공간 선언을 맨 위 `rss`에 한 번 해 두고, 아래에서 `writeStartElement("content", "encoded", CONTENT_NS)`로 `content:encoded`를 쓴다.
- ② `channel/description`은 필수다. 소개글을 비워 둔 블로그도 있으니 이름으로 채운다.

```java
private static void writeItem(XMLStreamWriter xml, RssFeed.Item item, Urls urls) throws XMLStreamException {
    String link = urls.post(item.postId());
    xml.writeStartElement("item");
    element(xml, "title", item.title());
    element(xml, "link", link);
    xml.writeStartElement("guid");
    xml.writeAttribute("isPermaLink", "true");          // ③
    xml.writeCharacters(link);
    xml.writeEndElement();
    element(xml, "pubDate", rfc822(item.publishedAt()));
    if (item.category() != null) {
        element(xml, "category", item.category());      // ④
    }
    if (!isBlank(item.summary())) {
        element(xml, "description", item.summary());    // ⑤
    }
    xml.writeStartElement("content", "encoded", CONTENT_NS);
    xml.writeCharacters(xmlSafe(urls.absoluteImages().apply(item.contentHtml())));   // ⑥
    xml.writeEndElement();
    xml.writeEndElement();
}
```

- ③ 리더는 `guid`로 "이미 본 글"을 가린다. 글 번호는 플랫폼 전체에서 하나이고 수정해도 바뀌지 않으므로 글 주소를 그대로 쓴다. 다른 블로그로 옮긴 글은 주소가 바뀌어 새 글로 보일 수 있다(드문 일이라 받아들였다, R-19).
- ④ 미분류 글은 `category` 칸이 없다. 빈 `<category/>`를 두면 "이름이 빈 카테고리"로 읽힐 수 있다.
- ⑤ 요약은 `Post.summary`(본문 글자 300자, 태그 없음)다. 목록에 쓰는 것과 같다.
- ⑥ 본문 HTML은 `content:encoded`에 **이스케이프해서** 넣는다(`<p>` → `&lt;p&gt;`). 리더가 XML을 풀면 원래 HTML이 나온다. CDATA(`<![CDATA[ … ]]>`)로 감싸는 방법도 있지만 본문에 `]]>`가 들어 있으면 깨지므로, 이스케이프만 쓴다. 본문 이미지 `src="/uploads/…"`는 now-log 안에서만 통하는 상대 주소라 전체 주소로 바꾼다(정화 규칙상 링크 `href`는 이미 절대 주소만 남는다, [XSS 방어](../3-보안/06-XSS-방어-본문-정화와-CSP.md)).

```java
static String rfc822(LocalDateTime dateTime) {
    // DB 시각은 시간대 없는 한국 시간이라 +0900을 붙인다
    return RFC_822.format(dateTime.atZone(DateTimes.KST));    // ⑦ Thu, 12 Nov 2026 14:30:00 +0900
}

static String xmlSafe(String text) {                          // ⑧
    …
    text.codePoints().filter(RssFeedWriter::allowedInXml).forEach(safe::appendCodePoint);
    …
}
```

- ⑦ `DateTimeFormatter.RFC_1123_DATE_TIME`은 RFC 822 형식에서 연도를 네 자리로 쓴 것이다(RSS 2.0 명세도 네 자리 연도를 권한다). 요일·달 이름은 영어로 고정이라 서버 언어 설정과 상관없다. `LocalDateTime`에는 시간대가 없으니 `atZone(KST)`로 붙인다. 이것을 빠뜨리면 형식은 맞아도 9시간 어긋난다.
- ⑧ XML 1.0에는 넣을 수 없는 글자가 있다(탭·줄바꿈·CR 말고 U+0000~U+001F 같은 제어 문자). 이스케이프로도 못 넣는다. 제목에 하나라도 섞이면 피드 전체가 깨진 XML이 되어 리더가 아무 글도 못 읽는다. StAX가 이런 글자를 걸러 준다고 기대하지 않고 직접 뺀다.

### 5.3 `rss/presentation/RssFeedController.java`: 주소와 응답

```java
@GetMapping("/@{address}/rss")
public ResponseEntity<byte[]> feed(@PathVariable String address, HttpServletRequest request) {
    return switch (rssFeedService.find(address)) {
        case RssFeedLookup.NotFound notFound -> ResponseEntity.status(HttpStatus.NOT_FOUND).build();   // ①
        case RssFeedLookup.MovedTo movedTo -> ResponseEntity.status(HttpStatus.MOVED_PERMANENTLY)
                .location(URI.create(feedUrl(request, movedTo.address())))
                .build();
        case RssFeedLookup.Found found -> ResponseEntity.ok()
                .header("Content-Type", RSS_UTF8)                                                  // ②
                .cacheControl(CACHE)                                                               // ③
                .body(RssFeedWriter.write(found.feed(), urls(request, found.feed())));
    };
}
```

- ① 피드는 JSON API가 아니라서 오류 본문 없이 상태 코드만 준다. 리더는 상태 코드만 본다.
- ② `application/rss+xml;charset=UTF-8`. 바이트로 보내고 글자 인코딩을 헤더에 밝힌다(XML 선언에도 `UTF-8`).
- ③ `Cache-Control: max-age=300`. 리더는 같은 피드를 자주 읽으므로 5분 동안은 다시 묻지 않아도 된다고 알린다.
- 결과를 sealed interface(`RssFeedLookup`)로 받아 `switch`로 나눈다. 글 가시성의 `PostAccess`와 같은 방식이라, 경우를 하나 빠뜨리면 컴파일이 안 된다.

### 5.4 `global/config/SpaForwardController.java`: 자동 찾기 태그

```java
private ResponseEntity<Resource> blogApp(HttpServletRequest request, Blog blog) {
    return blogVisibilityPolicy.isOpenToOthers(blog)
            ? html(HttpStatus.OK, withFeedLink(indexHtml(), request, blog))
            : app(HttpStatus.OK);
}

private String withFeedLink(String html, HttpServletRequest request, Blog blog) {
    if (!blogVisibilityPolicy.isOpenToOthers(blog)) {
        return html;
    }
    String tag = "<link rel=\"alternate\" type=\"application/rss+xml\" title=\""
            + HtmlUtils.htmlEscape(blog.getName()) + "\" href=\""
            + HtmlUtils.htmlEscape(blogAddressResolver.blogUrl(request, blog, "/rss")) + "\">\n";
    return html.replace("</head>", tag + "</head>");
}
```

- 공유 미리보기(Open Graph)와 같은 자리, 같은 방법이다. 리더는 자바스크립트를 실행하지 않으므로 React가 head를 바꿔서는 소용이 없다.
- 블로그 이름은 사용자가 쓴 글자라 `HtmlUtils.htmlEscape`로 이스케이프한다. 이름이 `"><script>`여도 속성 값 안의 글자일 뿐이다.
- 다른 사람에게 닫힌 블로그(이용 제한 블로그를 주인이 보는 경우)에는 넣지 않는다. 피드가 404인데 "여기 피드가 있다"고 알리면 안 된다.
- 블로그 첫 화면, 카테고리·태그·검색·방명록, 글 화면에 넣는다. 관리 화면과 404·301 응답, 플랫폼 화면에는 넣지 않는다.

### 5.5 화면: 머리글의 RSS 링크

```tsx
{/* 피드는 React 화면이 아니라 서버가 주는 XML이라 Link가 아니라 a로 연다 (SUB-07) */}
<a href={blogUrl(blog.address, '/rss')} type="application/rss+xml" title={`${blog.name} RSS 피드`}>RSS</a>
```

React Router의 `<Link>`는 페이지를 새로 받지 않고 화면만 바꾼다. 그러면 `/rss`가 React의 "없는 화면"이 된다. 서버가 주는 문서로 가려면 보통 `<a>`를 쓴다. Thymeleaf로 치면 `th:href`로 다른 컨트롤러 주소에 링크하는 것과 같다. 개발 서버(5173)는 `/api`·`/uploads`만 Spring Boot로 넘기므로 `vite.config.ts`에 `'^/@[^/]+/rss$'`(`^`로 시작하는 키는 정규식)를 더했다.

### 5.6 테스트: `RssFeedIntegrationTest`

피드를 글자 비교가 아니라 **XML 파서**(`DocumentBuilderFactory`, 이름공간 인식)로 읽어 칸을 확인한다. 리더가 읽는 방식과 같아야 이스케이프·이름공간 실수를 잡는다.

- 공개 글 둘 + 빠져야 할 글 여섯(비공개, 구독자 공개, 임시저장, 숨김, 지움, 비공개 카테고리) → `item`이 정확히 둘, 최신순
- 하위 카테고리 글의 `category`가 `["여행/제주"]` 하나(태그를 달아 두고도 태그가 없음을 확인)
- `content:encoded`에 `src="http://blog.test/uploads/abc.png"`
- 주인 쿠키로 열어도 비공개 글 없음, 21개 중 20개, 빈 블로그, 제어 문자와 `<`·`&` 제목
- 404(없음·예약어·지움·이용 제한(주인 포함)·주인 정지), 이사 301과 이사 대상 삭제 404
- 블로그 화면·카테고리·글 화면에 자동 찾기 태그, 관리 화면·플랫폼 화면·이용 제한 블로그에는 없음

## 6. 자주 하는 실수와 함정

- **"RSS 2.0을 지켰으니 다 맞겠지"**: 칸이 모두 선택이라 무엇을 담았는지는 표준이 보장하지 않는다. 서로 기대하는 칸을 계약으로 적는다(3.3).
- **한 소비자에 맞춰 칸의 뜻을 바꾸기**: `description`에 본문을 넣으면 그 앱은 맞지만 일반 리더가 어긋난다. 읽는 쪽이 고르게 하고, 쓰는 쪽은 뜻대로 채운다.
- **태그를 `category`에 섞기**: 흔한 방식이지만, 읽는 쪽이 카테고리로 거를 때 태그가 섞여 다시 나눌 수 없다.
- **자동 찾기 태그를 React로 넣기**: `document.head`에 넣어도 리더는 자바스크립트를 실행하지 않아 못 본다. 서버가 HTML에 넣는다.
- **문자열로 XML 만들기**: 제목 하나의 `&` 때문에 피드 전체가 깨진다. StAX 같은 XML 작성기를 쓴다. 이스케이프로도 못 넣는 제어 문자도 따로 뺀다.
- **시간대 없는 `pubDate`**: `LocalDateTime`을 그대로 형식에 넣을 수 없다(`RFC_1123_DATE_TIME`은 시간대가 있어야 한다). UTC로 착각해 붙이면 9시간 어긋난다.
- **상대 주소 이미지**: `src="/uploads/a.png"`는 리더 안에서 리더의 주소를 기준으로 풀려 깨진다. 전체 주소로 바꾼다.
- **로그인한 사람 기준으로 피드 만들기**: 캐시·공유를 거쳐 비공개 글이 샌다. 피드는 비회원 기준 하나로.
- **화면 패턴에 먹히는 주소**: `/@{주소}/rss`를 만들어 놓고 테스트하지 않으면 SPA 화면 패턴이 가져갈 수 있다. 실제 요청으로 XML이 오는지 확인한다.

## 7. 직접 해 보기

```bash
docker compose up -d && ./mvnw spring-boot:run      # 8080
# 1) 피드 받기: 상태 코드, Content-Type, Cache-Control
curl -i http://localhost:8080/@my-daily/rss | head -20
# 2) XML이 맞는지(macOS에는 xmllint가 있다)
curl -s http://localhost:8080/@my-daily/rss | xmllint --noout - && echo ok
# 3) 카테고리 목록: 태그가 섞이지 않았는지
curl -s http://localhost:8080/@my-daily/rss | grep -o '<category>[^<]*</category>' | sort | uniq -c
# 4) 자동 찾기 태그
curl -s http://localhost:8080/@my-daily | grep -o '<link rel="alternate"[^>]*>'
# 5) 글 하나를 비공개로 바꾼 뒤 1)을 다시 → 그 글이 빠진다(5분 캐시는 브라우저·리더 쪽 이야기라 curl은 바로 바뀐다)
```

- 운영 배포 뒤에는 피드 주소를 [W3C Feed Validation Service](https://validator.w3.org/feed/)에 넣어 본다.
- 피드 리더(Feedly, Thunderbird 등)에 블로그 주소(`…/@my-daily`)만 넣어 보고, 리더가 자동 찾기로 피드를 찾는지 본다.
- `RssFeedWriter.xmlSafe`를 잠깐 빼고 `escapesTextAndDropsCharactersXmlCannotHold` 테스트를 돌려 보면, 제어 문자 하나로 파서가 문서 전체를 거부하는 것을 볼 수 있다.

## 8. 확인 문제

1. RSS 2.0에서 `channel`의 필수 칸 셋은?
   <details><summary>답</summary>`title`, `link`, `description`. now-log는 소개글이 비면 `description`에 블로그 이름을 쓴다.</details>
2. now-log 피드의 `description`과 `content:encoded`에는 각각 무엇이 들어가고, 왜 그렇게 나눴나?
   <details><summary>답</summary>`description`은 300자 요약, `content:encoded`는 전체 본문 HTML이다. RSS 2.0에서 `description`의 뜻이 요약이고, 본문 칸은 Content 모듈이 마련했기 때문이다. 어느 칸을 읽을지는 읽는 쪽이 정한다.</details>
3. 어떤 앱이 `description`만 읽는다. now-log가 앱에 맞추지 않으면 그 앱은 어떻게 고치면 되나?
   <details><summary>답</summary>`content:encoded`가 있으면 그것을, 없으면 `description`을 읽는다. 그러면 now-log·WordPress·티스토리 모두 맞는다.</details>
4. 블로그 주소만 받은 리더가 피드 주소를 찾는 표준 방법은? now-log에서 이 태그를 React가 아니라 서버가 넣는 이유는?
   <details><summary>답</summary>HTML head의 `<link rel="alternate" type="application/rss+xml" href="…">`(HTML 표준, RSS Autodiscovery). 리더는 자바스크립트를 실행하지 않고 서버가 준 HTML만 보기 때문이다.</details>
5. 하위 카테고리 "제주"(상위 "여행") 글의 `category` 값은? 그 글에 태그 "바다"가 있으면 피드에 어떻게 나오나?
   <details><summary>답</summary>`여행/제주` 하나. 태그는 피드에 나오지 않는다.</details>
6. 블로그 주인이 로그인한 채 자기 피드를 열면 비공개 글이 보이나? 왜?
   <details><summary>답</summary>보이지 않는다. 피드는 늘 비회원 기준이다. 리더는 로그인하지 않고, 피드 응답은 캐시·공유를 거쳐 퍼질 수 있기 때문이다.</details>
7. 제목에 U+0001 글자가 있는 글이 하나 있다. 거르지 않으면 어떻게 되나?
   <details><summary>답</summary>XML 1.0에 넣을 수 없는 글자라 피드 전체가 깨진 문서가 되고, 리더는 그 블로그의 글을 하나도 못 읽는다. 이스케이프로도 못 넣으므로 빼야 한다.</details>
8. 이사한 블로그의 옛 피드 주소를 열면? 이사 간 블로그가 지워졌으면?
   <details><summary>답</summary>`/@새주소/rss`로 301. 이사 간 블로그가 지워졌으면 404. 블로그 화면 주소와 같은 규칙이다.</details>

## 9. 더 읽을거리

- RSS 2.0 Specification (RSS Advisory Board, rssboard.org/rss-specification)
- RSS Autodiscovery (RSS Advisory Board, rssboard.org/rss-autodiscovery)
- RDF Site Summary 1.0 Modules: Content (`content:encoded`)
- RFC 4287 The Atom Syndication Format
- HTML Living Standard, link type `alternate`
- W3C Feed Validation Service (validator.w3.org/feed)
- Java `javax.xml.stream.XMLStreamWriter`, `DateTimeFormatter.RFC_1123_DATE_TIME`
