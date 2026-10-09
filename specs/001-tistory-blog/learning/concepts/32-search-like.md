# 32. 블로그 안 검색: LIKE와 비정규화 칸

> 관련 스텝: [스텝 7](../step-07.md) (T047, T048), [스텝 9](../step-09.md) (T067) · 관련 개념: [37-filtered-list-bulk-actions](./37-filtered-list-bulk-actions.md), [03-flyway-migration](./03-flyway-migration.md), [06-jpa-entity-mapping](./06-jpa-entity-mapping.md), [08-pagination](./08-pagination.md), [14-xss-sanitize-csp](./14-xss-sanitize-csp.md), [16-authorization-visibility](./16-authorization-visibility.md), [19-react-router-api-client](./19-react-router-api-client.md), [25-react-forms-data](./25-react-forms-data.md), [28-thymeleaf-to-react](./28-thymeleaf-to-react.md), [31-tags-many-to-many](./31-tags-many-to-many.md)

## 1. 이 문서로 배우는 것

- SQL `LIKE`로 "글자가 들어간" 행 찾기와 그 한계
- LIKE의 특수 문자 `%`, `_`를 **글자 그대로** 찾게 하는 이스케이프
- 대소문자를 무시하는 검색이 DB 정렬 규칙(`utf8mb4_0900_ai_ci`)에서 오는 원리
- 본문 HTML이 아니라 **글자만 담은 칸**(`content_text`)에서 찾는 이유: 비정규화
- 이미 운영 중인 표에 NOT NULL 칸을 더하는 Flyway 마이그레이션 순서(더하기 → 채우기 → NOT NULL)
- 태그 이름 검색을 조인이 아니라 **EXISTS 부분 쿼리**로 하는 이유
- `%검색어%`가 B-tree 인덱스를 못 쓰는 이유와, 느려지면 옮길 곳(FULLTEXT, 검색 엔진)
- 검색어를 주소(`?q=&page=`)에 두어 결과를 나눌 수 있게 하는 화면

**먼저 알면 좋은 것**: Specification과 Criteria API([06](./06-jpa-entity-mapping.md)), 볼 수 있는 글 조건 `listedIn`([16](./16-authorization-visibility.md)), Flyway 체크섬([03](./03-flyway-migration.md)), 본문 정화([14](./14-xss-sanitize-csp.md)), 다대다 태그([31](./31-tags-many-to-many.md)).

## 2. 왜 필요한가

블로그 머리글의 검색 칸에 "jpa"를 치면 이 블로그에서 제목·본문·태그에 jpa가 들어간 글이 나와야 한다(SRCH-01, P0). 쉬워 보이지만 이런 질문이 있다.

- 본문은 HTML(`<p><strong>JPA</strong> 정리</p>`)로 저장된다. "strong"을 검색하면 모든 굵은 글씨가 있는 글이 나와도 될까?
- "100%"를 검색하면 "1000원짜리" 글까지 나온다면?
- `JPA`, `jpa`, `Jpa`는 같은 검색어인가?
- 같은 글이 제목에도 맞고 태그에도 맞으면 두 번 나오나?
- 비공개 글이 검색 결과에 섞이면? (목록 제목만 보여도 정보가 샌다)
- 검색 결과 주소를 친구에게 보내면 같은 결과가 보이나?

명세와 결정은 이렇다.

- SRCH-01: 블로그 안에서 제목+본문+태그 키워드 검색, 10개씩 페이지.
- tasks T047: 대소문자 무시, 앞뒤 공백 제거, 공백뿐이면 거절, 최신순 10개, 가시성 조건.
- research **R-16**(2026-10-09 지원 결정): `post.content_text`(본문에서 HTML 태그를 뺀 글자, 저장할 때 jsoup으로 만든다)를 더하고, 제목·`content_text`·태그 이름에서 `LIKE '%검색어%'`로 찾는다. 대소문자는 정렬 규칙으로 무시한다. 기존 글은 Flyway V3에서 채운다. 대안이었던 `content_html` LIKE는 HTML 태그 이름까지 걸리고, MySQL FULLTEXT ngram은 빠르지만 규칙이 복잡하다. 글이 많아져 느려지면 FULLTEXT로 옮긴다.

## 3. 기본 개념

### 3.1 LIKE와 와일드카드

`LIKE`는 패턴으로 문자열을 비교한다. 패턴에서 두 글자가 특별하다.

| 패턴 글자 | 뜻 | 예 |
| --- | --- | --- |
| `%` | 아무 글자 0개 이상 | `'%jpa%'`: 어디든 jpa가 들어감 |
| `_` | 아무 글자 정확히 1개 | `'a_b'`: a, 한 글자, b |

"들어간"을 찾으려면 검색어 앞뒤에 `%`를 붙인다: `title LIKE '%jpa%'`.

### 3.2 이스케이프: 사용자가 친 `%`는 글자다

사용자가 "100%"를 검색했다고 하자. 그대로 패턴에 넣으면 `'%100%%'`다. 끝의 `%`는 와일드카드라 "100이 들어간 모든 글"이 나온다. "1000원짜리"도 걸린다. `_`도 마찬가지로 `a_b`를 검색하면 `axb`, `a b`까지 걸린다.

사용자의 글자를 글자로 찾게 하려면 특수 문자 앞에 **이스케이프 문자**를 붙이고, 쿼리에 어떤 글자가 이스케이프 문자인지 알린다.

```sql
title LIKE '%100\%%' ESCAPE '\'
```

`\%`는 "글자 %"다. 이스케이프 문자 자체(`\`)를 검색하려면 `\\`로 쓴다. 그래서 바꾸는 순서가 중요하다. **`\`를 먼저** 두 배로 만들고 그다음 `%`, `_` 앞에 `\`를 붙인다. 순서를 바꾸면 방금 붙인 `\`를 다시 두 배로 만들어 버린다.

이것은 SQL 주입(injection)과 다른 문제다. 이 프로젝트는 값을 늘 매개변수(`?`)로 넘겨 SQL 문법이 깨질 일은 없다. 이스케이프는 **결과가 틀리는 것**을 막는다.

### 3.3 대소문자 무시는 정렬 규칙이 한다

MySQL은 칸의 정렬 규칙(collation)대로 문자열을 비교하고, `LIKE`도 그 규칙을 따른다. 이 프로젝트의 DB는 `docker-compose.yml`과 테스트 컨테이너가 모두 `--collation-server=utf8mb4_0900_ai_ci`로 뜬다. `ci`(case insensitive)라 `'JPA' LIKE '%jpa%'`가 참이다. `ai`(accent insensitive)라 악센트도 무시한다. 그래서 코드에서 `LOWER(title) LIKE LOWER(?)`처럼 쓰지 않는다. 칸에 함수를 씌우면 쿼리가 복잡해지고, 혹시 쓸 수 있었던 인덱스도 못 쓴다. 자세한 정렬 규칙 이야기는 [31의 3.5](./31-tags-many-to-many.md)에 있다.

`erd/schema.sql`의 `CREATE TABLE`에는 정렬 규칙이 적혀 있지 않다. 표와 칸은 DB 기본값을 물려받는다. 그래서 정렬 규칙은 DB 서버를 띄우는 설정(`docker-compose.yml`, `TestcontainersConfiguration`)에 있고, 실제 칸에 무엇이 적용됐는지는 `information_schema.COLUMNS`로 확인한다(7.4). 운영 DB를 다른 정렬 규칙으로 만들면 검색 동작이 달라진다는 뜻이기도 하다.

### 3.4 HTML에서 찾으면 안 되는 이유와 비정규화 칸

본문은 정화된 HTML로 `content_html`에 저장된다([14](./14-xss-sanitize-csp.md)).

```html
<p><strong>JPA</strong> 정리 &amp; 팁</p>
```

여기에 `LIKE '%strong%'`을 하면 맞는다. 사용자는 "strong"이라는 글자를 쓴 적이 없다. `amp`, `href`, `src`, `uploads` 같은 말도 마찬가지로 HTML 속성과 문자 참조 때문에 걸린다. 반대로 `&`를 검색하면 HTML에는 `&amp;`로 들어 있어 사용자 생각과 다르게 동작한다.

해결은 **글자만 따로 담은 칸**을 두는 것이다.

```
content_html:  <p><strong>JPA</strong> 정리 &amp; 팁</p>
content_text:  JPA 정리 & 팁
```

`content_text`는 `content_html`에서 계산할 수 있는 값이다. 계산할 수 있는 값을 따로 저장하는 것을 **비정규화**라 한다. 글 목록의 `comment_count`와 같은 종류다([29](./29-comments-design.md)). 얻는 것은 검색이 쿼리 한 줄이 된다는 것이고, 생기는 책임은 **두 칸이 늘 맞아야 한다**는 것이다. 이 프로젝트는 본문이 바뀌는 곳(발행·수정)이 `Post` 생성자와 `edit` 두 곳뿐이고, 둘 다 `PostBody(html, text, summary)` 하나를 받아 세 칸을 한꺼번에 채운다. 한 칸만 바꾸는 길이 없게 만든 것이다.

### 3.5 EXISTS 부분 쿼리

태그는 글마다 여럿이다. "이름에 jpa가 들어간 태그가 달린 글"을 조인으로 찾으면 이렇게 된다.

```sql
SELECT p.* FROM post p
  JOIN post_tag pt ON pt.post_id = p.id
  JOIN tag t ON t.id = pt.tag_id
 WHERE t.name LIKE '%jpa%'
```

글 7에 `jpa`, `spring-data-jpa` 두 태그가 있으면 글 7이 **두 줄** 나온다. `DISTINCT`로 줄일 수는 있지만, 페이지 처리를 하면 "10개"를 셀 때와 전체 개수를 셀 때 모두 중복을 신경 써야 한다. 제목·본문 조건과 `OR`로 묶으면 더 헷갈린다. 게다가 태그가 하나도 없는 글은 (안쪽) 조인에서 빠져 제목·본문 검색에서도 사라진다. 그래서 외부 조인을 써야 하는 등 일이 늘어난다.

EXISTS는 "조건에 맞는 행이 **하나라도 있는가**"만 묻는다.

```sql
SELECT p.* FROM post p
 WHERE p.title LIKE ? OR p.content_text LIKE ?
    OR EXISTS (SELECT 1 FROM post_tag pt JOIN tag t ON t.id = pt.tag_id
                WHERE pt.post_id = p.id AND t.name LIKE ?)
```

바깥 행(`p`) 하나마다 참·거짓 하나가 나오므로 글은 많아야 한 번 나온다. 안쪽 쿼리가 바깥 행의 `p.id`를 쓰므로 **상관(correlated) 부분 쿼리**라 한다. 태그 없는 글도 제목·본문 조건으로 그대로 찾힌다.

### 3.6 `%검색어%`와 인덱스

B-tree 인덱스는 값을 **정렬해서** 저장한다. 사전에서 "spr"로 시작하는 단어는 한 구간에 모여 있으니 바로 찾을 수 있다. 그래서 그 칸에 인덱스가 있으면 `LIKE 'spr%'`(앞이 고정)는 인덱스로 구간을 찾을 수 있다. 하지만 `LIKE '%spr%'`는 "어디든 spr이 들어간" 값이라 정렬 순서와 상관이 없다. 사전에서 "가운데에 spr이 들어간 단어"를 찾으려면 처음부터 끝까지 읽어야 하는 것과 같다. 그래서 앞에 `%`가 있는 LIKE는 각 행을 하나씩 읽어 비교한다.

이 프로젝트는 그래도 괜찮다고 판단했다. 검색은 **한 블로그 안**에서만 하고, 조건에 `blog_id = ?`(+ 상태, 공개 범위)가 같이 붙는다. `post` 표에는 `idx_post_blog_feed(blog_id, status, visibility, published_at, id)` 인덱스가 있어 옵티마이저가 이 블로그의 글로 먼저 좁힌 뒤 그 행들만 LIKE로 비교할 수 있다. 실제로 어떤 인덱스를 고르는지는 데이터 양에 따라 달라지므로 `EXPLAIN`으로 확인한다(7.4). 블로그 하나의 글이 수천 개 정도라면 충분히 빠르다.

글이 아주 많아지거나 플랫폼 전체 검색(SRCH-02)을 하면 다른 도구가 필요하다.

| 방법 | 특징 |
| --- | --- |
| LIKE `%...%` (지금) | 단순, 정확한 부분 문자열, 인덱스를 못 씀 |
| MySQL FULLTEXT 인덱스 | 단어 단위 역색인. 한국어처럼 띄어쓰기로 단어가 잘 안 나뉘는 글은 MySQL에 들어 있는 **ngram 파서**(글자 n개씩 잘라 색인, 기본 2글자)를 쓴다. 토큰보다 짧은 검색어, 불용어, 결과 순서 같은 규칙을 따로 익혀야 한다 |
| 검색 엔진(Elasticsearch, OpenSearch 등) | 형태소 분석, 오타, 관련도 순위. 별도 서버와 DB와의 동기화가 필요 |

R-16은 "느려지면 FULLTEXT로 옮긴다"고 적었다. 그때도 `content_text` 칸은 그대로 쓸모가 있다. FULLTEXT 인덱스를 걸 대상이 바로 이 칸이기 때문이다.

## 4. 동작 원리

### 4.1 검색 요청 하나

```
브라우저: alpha.blog.test/search?q=JPA
  BlogSearchPage: useSearchParams → q="JPA", page=1
  GET http://alpha.blog.test/api/search?q=JPA&page=1
    SearchController: @CurrentBlog(Host → alpha 블로그), q, page, size
      PageQuery.of(page, size, 10)                      페이지 1부터, 기본 10개
      SearchService.search(blog, viewerId, "JPA", pageQuery)
        normalize: strip → 비었으면 400(q), 100자 넘으면 400(q)
        pattern = "%" + escapeLike("JPA") + "%"           → "%JPA%"
        listedIn(blog, viewerId, now)  AND  matches
          matches = title LIKE p  OR  content_text LIKE p  OR  EXISTS(태그 이름 LIKE p)
        findAll(조건, 최신순 페이지)
          → SELECT ... LIMIT 10        (내용)
          → SELECT COUNT(...) ...       (전체 개수, totalElements·totalPages용)
      PostThumbnails.of(글들) → 썸네일 주소
  ← PageResponse<PostSummaryResponse>
  화면: "'JPA' 검색 결과 2", 글 목록(PostItem), 페이지 번호 링크 /search?q=JPA&page=2
```

### 4.2 글을 저장할 때 `content_text`가 채워지는 곳

```
PostService.publish / edit
  body(rawHtml)
    html = htmlSanitizer.sanitize(rawHtml)          정화 (14)
    text = summaryExtractor.plainText(html)         jsoup으로 태그를 뺀 글자
    summary = summaryExtractor.extract(html)        글자에서 300자 요약
    → new PostBody(html, text, summary)
  Post.published(..., body, ...) / post.edit(..., body, ...)
    contentHtml = body.html(); contentText = body.text(); summary = body.summary()
```

글자는 **정화한 뒤의** HTML에서 뽑는다. 정화에서 지워진 `<script>` 안 글자 같은 것이 검색 칸에 들어가지 않는다.

### 4.3 이미 있던 글은? (V3 마이그레이션)

`content_text`를 NOT NULL로 더하려면 이미 있는 글에도 값이 있어야 한다. 한 번에 `ADD COLUMN ... NOT NULL`을 하면 MySQL은 기존 행을 기본값(MEDIUMTEXT라 빈 문자열에 해당)으로 채우거나 오류를 낸다. 어느 쪽이든 기존 글이 검색되지 않는다. 그래서 세 단계로 나눈다.

```
1. 칸을 NULL 허용으로 더한다
2. 기존 행을 채운다
3. NOT NULL로 바꾼다
```

## 5. 이 프로젝트에서는

### 5.1 `search/application/SearchService.java`

```java
    @Transactional(readOnly = true)
    public Page<Post> search(Blog blog, Long viewerId, String rawQuery, PageQuery page) {
        String query = normalize(rawQuery);
        String pattern = "%" + escapeLike(query) + "%";
        Specification<Post> matches = (root, criteria, cb) -> {
            // 태그 이름은 글마다 여럿이라, 조인하면 같은 글이 여러 번 나온다. 그래서 EXISTS 부분 쿼리로 본다
            Subquery<Long> tagged = criteria.subquery(Long.class);
            Root<Post> sameRow = tagged.correlate(root);
            Join<Post, Tag> tag = sameRow.join("tags");
            tagged.select(tag.get("id")).where(cb.like(tag.get("name"), pattern, ESCAPE));
            return cb.or(
                    cb.like(root.get("title"), pattern, ESCAPE),
                    cb.like(root.get("contentText"), pattern, ESCAPE),
                    cb.exists(tagged));
        };
        return postRepository.findAll(
                PostSpecifications.listedIn(blog, viewerId, LocalDateTime.now(clock)).and(matches),
                page.toPageable(LATEST));
    }
```

한 줄씩 보자.

- `normalize(rawQuery)`: 검색어 정리(5.2). 여기서 400이 나면 쿼리를 하나도 보내지 않는다.
- `"%" + escapeLike(query) + "%"`: 사용자 글자를 이스케이프한 뒤 앞뒤에 와일드카드를 붙인다. 이스케이프는 **사용자 부분에만** 한다. 앞뒤 `%`까지 이스케이프하면 "들어간"이 아니라 "정확히 %JPA%"를 찾게 된다.
- `criteria.subquery(Long.class)`: 부분 쿼리를 만든다. `Long`은 안쪽 SELECT가 돌려줄 값의 타입이다(EXISTS는 값이 아니라 행이 있는지만 보므로 무엇을 고르든 상관없다. 여기서는 태그 id).
- `tagged.correlate(root)`: 안쪽 쿼리에서 **바깥의 같은 글 행**을 가리키는 별칭을 만든다. 이것이 "상관" 부분 쿼리의 핵심이다. 이 별칭에서 `join("tags")`하면 "바깥 글의 태그들"이 된다. SQL로는 `WHERE pt.post_id = p.id`가 생긴다.
- `cb.like(..., pattern, ESCAPE)`: 세 번째 인자가 이스케이프 문자다. JPQL/SQL에 `escape '\'`가 붙는다. 세 LIKE 모두에 같이 준다.
- `cb.or(...)`: 셋 중 하나라도 맞으면 된다.
- `listedIn(...).and(matches)`: **볼 수 있는 글 조건을 먼저**, 그리고 검색 조건. 블로그 메인 목록과 같은 `listedIn`이다([16](./16-authorization-visibility.md)). 주인에게는 자기 비공개 글도 나오고, 남에게는 공개·볼 수 있는 글만 나온다. 검색이라고 가시성 규칙을 따로 쓰지 않는다.
- `LATEST`: `publishedAt` 내림차순, 같으면 `id` 내림차순. 같은 시각의 글 순서가 페이지마다 흔들리지 않게 두 번째 정렬 키를 둔다([08](./08-pagination.md)).

클래스 상수는 이렇다.

```java
    public static final int PAGE_SIZE = 10;
    public static final int MAX_QUERY_LENGTH = 100;

    private static final Sort LATEST = Sort.by(Sort.Order.desc("publishedAt"), Sort.Order.desc("id"));
    private static final char ESCAPE = '\\';
```

Java 문자 리터럴 `'\\'`는 백슬래시 한 글자다(Java 소스에서 `\`를 쓰려면 두 번 쓴다).

### 5.2 검색어 정리와 이스케이프

```java
    /** 앞뒤 공백을 떼고, 비었거나 공백뿐이면 400, 너무 길면 400. */
    static String normalize(String rawQuery) {
        String query = rawQuery == null ? "" : rawQuery.strip();
        if (query.isEmpty()) {
            throw BusinessException.invalidField("q", "검색어를 입력해 주세요.");
        }
        if (query.length() > MAX_QUERY_LENGTH) {
            throw BusinessException.invalidField("q", "검색어는 " + MAX_QUERY_LENGTH + "자까지입니다.");
        }
        return query;
    }

    /** LIKE의 특수 문자(%, _)를 글자 그대로 찾게 한다. 안 하면 "100%"가 "100"으로 시작하는 모든 글에 걸린다. */
    static String escapeLike(String query) {
        return query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_");
    }
```

- `rawQuery == null`: 컨트롤러가 `@RequestParam(required = false)`로 받는다. `q`가 아예 없어도 Spring의 "필수 파라미터 없음" 오류가 아니라 이 메서드의 400(`fieldErrors[0].field == "q"`)이 나온다. 응답 모양을 한 가지로 맞추려는 것이다.
- `strip()`: `trim()`과 비슷하지만 유니코드 공백(전각 공백 등)까지 뗀다.
- 100자 제한: 아주 긴 검색어로 모든 행에 긴 패턴 비교를 시키는 것을 막는다. 화면의 검색 칸에도 `maxLength={100}`이 있지만 진짜 검사는 서버다.
- `escapeLike`: Java 문자열 리터럴로 읽으면 헷갈린다. 실제 글자로 보면 `\` → `\\`, `%` → `\%`, `_` → `\_`다. **`\`를 먼저** 바꾼다(3.2).
- 두 메서드가 `static`이고 `private`이 아니다(패키지 범위). 같은 패키지의 단위 테스트에서 DB 없이 바로 부를 수 있다.

### 5.3 `search/presentation/SearchController.java`

```java
    @GetMapping("/api/search")
    public PageResponse<PostSummaryResponse> search(@CurrentBlog Blog blog,
                                                    @RequestParam(required = false) String q,
                                                    @RequestParam(required = false) Integer page,
                                                    @RequestParam(required = false) Integer size) {
        PageQuery pageQuery = PageQuery.of(page, size, SearchService.PAGE_SIZE);
        Page<Post> posts = searchService.search(blog, LoginMembers.currentId(), q, pageQuery);
        Map<Long, String> thumbnails = postThumbnails.of(posts.getContent());
        return PageResponse.from(posts, post -> PostSummaryResponse.of(post, blog, thumbnails.get(post.getId())));
    }
```

- `@CurrentBlog Blog blog`: Host 헤더의 블로그 주소로 블로그를 찾는다([15](./15-subdomain-host-routing.md)). 그래서 이 API는 **블로그 주소**(`alpha.blog.test`)에서 부른다. contracts의 표에서 "B"가 이 뜻이다. 플랫폼 전체 검색(SRCH-02, 플랫폼 주소 `P`, `type=post|blog`)은 백로그다.
- `LoginMembers.currentId()`: 비회원이면 `null`. 가시성 판단에 쓴다. 검색은 누구나 할 수 있다.
- `PageQuery.of(page, size, 10)`: 페이지는 1부터, 크기는 기본 10·최대 50. 잘못된 값이면 400.
- 응답은 블로그 메인 목록과 **같은 모양**(`PageResponse<PostSummaryResponse>`)이다. 화면이 같은 목록 부품(`PostItem`)과 페이지 부품(`Pagination`)을 그대로 쓴다. 썸네일도 같은 `PostThumbnails`로 한 번에 구한다.

Thymeleaf로 같은 기능을 만든다면 이렇게 했을 것이다.

```html
<form th:action="@{/search}" method="get">
  <input type="search" name="q" th:value="${q}">
  <button>검색</button>
</form>
```

```java
@GetMapping("/search")
public String search(@RequestParam String q, @RequestParam(defaultValue = "1") int page, Model model) {
    model.addAttribute("posts", searchService.search(...));
    return "search";
}
```

GET 폼이라 제출하면 주소가 `/search?q=JPA`가 되고, 그 주소를 나누면 같은 결과가 나온다. 이 프로젝트도 **같은 성질**을 지킨다. 다만 서버가 HTML을 그리는 대신, 화면이 주소의 `q`를 읽어 `/api/search`를 부르고 JSON으로 그린다([28](./28-thymeleaf-to-react.md)).

### 5.4 `global/security/SummaryExtractor.java`: 글자 뽑기

```java
    /** 본문 전체 글자(검색용, SRCH-01). &amp;amp; 같은 문자 참조도 글자로 풀린다. */
    public String plainText(String html) {
        if (html == null || html.isBlank()) {
            return "";
        }
        return Jsoup.parse(html).text().strip();
    }

    public String extract(String html) {
        String text = plainText(html);
        ...
```

- `Jsoup.parse(html)`: HTML을 브라우저처럼 문서 나무(DOM)로 읽는다. 정규식으로 `<...>`를 지우는 것과 달리 태그 구조와 문자 참조를 제대로 이해한다.
- `.text()`: 모든 요소의 글자를 이어 붙인다. 블록 요소 사이에는 공백을 넣고, 여러 공백은 하나로 줄인다. `&amp;`는 `&`로 풀린다.
- 원래 요약(`extract`)만 있던 클래스에서 글자 뽑기를 `plainText`로 떼어 냈다. 요약은 이제 `plainText` 결과를 300자로 자른 것이다. 같은 글자를 한 방법으로만 만든다.

### 5.5 `Post.java`의 `contentText`와 `PostBody`

```java
    @Column(name = "content_text", nullable = false, columnDefinition = "mediumtext")
    private String contentText;
```

```java
    public void edit(Category category, String title, PostBody body, Visibility visibility, Topic topic) {
        this.category = category;
        this.title = title;
        this.contentHtml = body.html();
        this.contentText = body.text();
        this.summary = body.summary();
        ...
```

- `columnDefinition = "mediumtext"`: `ddl-auto=validate`가 칸 타입을 확인할 때 `String`의 기본 기대값(`varchar(255)`)이 아니라 `mediumtext`로 맞추게 한다. 본문(`content_html`)과 같은 타입이다. MEDIUMTEXT는 최대 16MB 정도까지 담는다.
- 생성자와 `edit`이 낱개 문자열 세 개가 아니라 `PostBody` 레코드 하나를 받는다(`record PostBody(String html, String text, String summary)`). 스텝 5까지는 `(contentHtml, summary)`를 따로 받았는데, 칸이 셋이 되면서 "HTML만 바꾸고 글자는 깜빡하는" 실수를 타입으로 막았다. 셋을 만드는 곳은 `PostService.body()` 하나다.

### 5.6 `db/migration/V3__post_content_text.sql`

```sql
-- 블로그 안 검색(SRCH-01)용 본문 글자 칸 (research R-16, Crowfoot ERD 버전 79, 2026-10-09 지원 결정).
-- 본문 HTML의 태그 이름(strong, href 등)으로 검색에 걸리지 않게, 태그를 뺀 글자를 따로 둔다.
-- 앞으로는 저장할 때 서버가 jsoup으로 채운다. 이미 있는 글은 여기서 정규식으로 태그만 지워 채운다.

ALTER TABLE post ADD COLUMN content_text MEDIUMTEXT NULL COMMENT '본문 글자-----...';

UPDATE post SET content_text = TRIM(REGEXP_REPLACE(content_html, '<[^>]+>', ' '));

ALTER TABLE post MODIFY COLUMN content_text MEDIUMTEXT NOT NULL COMMENT '본문 글자-----...';
```

- **왜 V1을 고치지 않고 V3를 더했나.** V1(`schema.sql` 복사본)은 이미 지원의 개발 DB와 모든 테스트 DB에 적용됐다. Flyway는 적용한 파일의 체크섬을 `flyway_schema_history`에 남기고, 파일이 바뀌면 다음 실행에서 검증 오류로 멈춘다([03](./03-flyway-migration.md)). 이미 적용한 마이그레이션은 고치지 않고, 바꿀 내용을 새 버전으로 더한다. 그래서 문서 쪽의 순서는 이랬다. Crowfoot ERD에 칸을 더해 버전 79로 만들고, `erd/schema.sql`을 다시 내보내고, 같은 변경을 V3로 적었다. 새로 만드는 DB는 V1 → V2 → V3를 차례로 적용해 같은 모양이 된다.
- **1단계** NULL 허용으로 더한다. 기존 행은 NULL이 된다.
- **2단계** 기존 행을 채운다. 여기서는 jsoup을 쓸 수 없다(SQL 마이그레이션이라 Java가 없다). MySQL 8의 `REGEXP_REPLACE`로 `<`부터 `>`까지를 공백으로 바꾸고 앞뒤 공백을 뗀다. 태그를 빈 문자열이 아니라 **공백**으로 바꾸는 이유는 `<p>가</p><p>나</p>`가 `가나`로 붙지 않게 하기 위해서다.
- **3단계** NOT NULL로 바꾼다. 이제 모든 행에 값이 있으니 바꿀 수 있다. 엔티티의 `nullable = false`와 맞는다.
- **jsoup과 결과가 조금 다르다.** 정규식 채우기는 `&amp;` 같은 문자 참조를 풀지 않고, 공백도 여러 개가 남을 수 있다. 그 글을 한 번 수정하면 jsoup 결과로 바뀐다. 개발 DB의 테스트용 글에만 해당해 이 정도로 충분하다고 봤다. 운영 데이터가 많았다면 Java로 채우는 일회성 작업(Flyway의 Java 마이그레이션 등)을 고려한다.

### 5.7 테스트 `SearchIntegrationTest`

준비에서 글 세 개를 발행한다.

```java
        security = publish("Spring Security 정리", "<p>필터 체인</p>", "[]", "PUBLIC");
        jpa = publish("두 번째 글", "<p><strong>JPA</strong> 정리 &amp; 팁</p>", "[]", "PUBLIC");
        docker = publish("세 번째 글", "<p>컨테이너</p>", "[\"Docker\"]", "PUBLIC");
```

```java
    @Test
    void findsInTitleTextAndTagIgnoringCase() throws Exception {
        search("SECURITY", null).andExpect(jsonPath("$.content[*].id", contains((int) security)));
        search("jpa", null).andExpect(jsonPath("$.content[*].id", contains((int) jpa)));
        search("docker", null).andExpect(jsonPath("$.content[*].id", contains((int) docker)));
        // 같은 글이 제목·본문 둘 다 맞아도 한 번만 나온다, 최신순
        search("정리", null).andExpect(jsonPath("$.content[*].id", contains((int) jpa, (int) security)))
                .andExpect(jsonPath("$.totalElements").value(2));
    }
```

- 제목(`SECURITY` → `Spring Security 정리`), 본문 글자(`jpa` → `<strong>JPA</strong>`), 태그(`docker` → `Docker`)에서 각각 찾는다. 모두 대소문자가 다르다.
- "정리"는 글 1의 제목과 글 2의 본문에 있다. 두 개, 최신순, `totalElements`도 2다(중복 없음).

```java
    @Test
    void htmlTagNamesAndEntitiesDoNotMatch() throws Exception {
        search("strong", null).andExpect(jsonPath("$.content", empty()));
        search("amp", null).andExpect(jsonPath("$.content", empty()));
        // 문자 참조는 글자로 풀려 저장되어 & 로 찾힌다
        search("& 팁", null).andExpect(jsonPath("$.content[*].id", contains((int) jpa)));
    }
```

R-16 결정이 지키려던 것을 그대로 시험한다. `content_html`에서 찾았다면 처음 두 줄이 실패한다.

```java
    @Test
    void likeWildcardsAreLiteral() throws Exception {
        long sale = publish("할인 100% 후기", "<p>x</p>", "[]", "PUBLIC");
        publish("1000원짜리", "<p>x</p>", "[]", "PUBLIC");
        publish("a_b 표기", "<p>x</p>", "[]", "PUBLIC");

        search("100%", null).andExpect(jsonPath("$.content[*].id", contains((int) sale)));
        search("_", null).andExpect(jsonPath("$.totalElements").value(1));
    }
```

이스케이프를 빼면 `100%`가 `1000원짜리`에도 걸리고, `_`는 "아무 글자 하나"라 모든 글이 걸린다.

```java
    @Test
    void onlyVisiblePostsAreFound() throws Exception {
        long hidden = publish("비공개 Security 메모", "<p>x</p>", "[]", "PRIVATE");

        search("security", null).andExpect(jsonPath("$.content[*].id", contains((int) security)));
        search("security", owner).andExpect(jsonPath("$.content[*].id", contains((int) hidden, (int) security)));
    }
```

같은 검색어라도 비회원에게는 비공개 글이 없고, 주인에게는 있다.

```java
    @Test
    void blankOrTooLongQueryIs400() throws Exception {
        search("   ", null).andExpect(status().isBadRequest()).andExpect(jsonPath("$.fieldErrors[0].field").value("q"));
        mockMvc.perform(get("/api/search").header(HttpHeaders.HOST, TestBlogs.host(blog)))
                .andExpect(status().isBadRequest());
        search("가".repeat(101), null).andExpect(status().isBadRequest());
    }
```

### 5.8 화면: 검색 칸과 결과 화면

머리글(`components/BlogHeader.tsx`)의 검색 칸이다.

```tsx
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [q, setQ] = useState(params.get('q') ?? '')

  function search(event: FormEvent) {
    event.preventDefault()
    if (q.trim()) {
      navigate(`/search?${new URLSearchParams({ q: q.trim() })}`)
    }
  }
  ...
      <form className="search-box" role="search" onSubmit={search}>
        <input type="search" value={q} maxLength={100} placeholder="이 블로그에서 검색" aria-label="블로그 내 검색"
               onChange={(event) => setQ(event.target.value)} />
        <button className="btn" type="submit">검색</button>
      </form>
```

- `useState(params.get('q') ?? '')`: 결과 화면에서도 칸에 지금 검색어가 남아 있게, 처음 값을 주소에서 읽는다. Thymeleaf의 `th:value="${q}"`와 같은 일이다.
- `onSubmit` + `preventDefault()`: 브라우저의 기본 폼 제출(페이지 전체 새로 받기)을 막고, 화면 안에서 `/search?q=...`로 **주소만** 바꾼다([25](./25-react-forms-data.md)). 결과는 Thymeleaf GET 폼과 같다. 주소에 검색어가 남는다.
- `new URLSearchParams({ q })`: 쿼리 문자열을 인코딩해서 만든다. 한글, `&`, `#`, `%`가 든 검색어도 안전하다. 문자열 이어 붙이기(`'/search?q=' + q`)를 하면 `a&b`가 `q=a`와 `b`라는 두 매개변수로 쪼개진다.
- 공백뿐이면 이동하지 않는다. 서버도 400을 주지만 굳이 요청하지 않는다.
- `<form role="search">`, `type="search"`, `aria-label`: 화면 읽기 프로그램이 "검색 영역"으로 알려 준다.

결과 화면(`pages/search/BlogSearchPage.tsx`)이다.

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
      .then((found) => {
        if (active) {
          setResult(found)
          setError(null)
        }
      })
      .catch((caught: unknown) => {
        if (active) {
          setResult(null)
          setError(caught instanceof ApiError && caught.fieldErrors.length > 0
            ? caught.fieldErrors[0].reason : errorMessage(caught))
        }
      })
    return () => {
      active = false
    }
  }, [q, page])
```

- **상태의 원천은 주소다.** 검색어와 페이지를 `useState`에 따로 두지 않고 매번 `useSearchParams()`로 주소에서 읽는다. 그래서 주소를 복사해 보내면 같은 결과, 새로고침해도 같은 결과, 뒤로 가기를 누르면 이전 검색어의 결과가 나온다. Thymeleaf에서 `@RequestParam`으로 매 요청 주소에서 읽던 것과 같은 생각이다.
- `Math.max(Number(...) || 1, 1)`: `page`가 없거나 숫자가 아니거나 0 이하면 1.
- 의존 배열 `[q, page]`: 둘 중 하나가 바뀌면(새 검색, 페이지 이동) 다시 부른다.
- `active` 깃발: 빠르게 검색어를 두 번 바꾸면 응답이 늦게 온 앞의 요청이 나중 결과를 덮어쓸 수 있다. 정리 함수에서 `active = false`로 만들어 늦게 온 응답을 버린다([25의 3.6](./25-react-forms-data.md)).
- 400이면 서버가 준 칸별 문장(`검색어를 입력해 주세요.`)을 그대로 보여 준다.

페이지 링크도 검색어를 지킨다.

```tsx
<Pagination page={result.page} totalPages={result.totalPages}
            href={(number) => `/search?${new URLSearchParams({ q, page: String(number) })}`} />
```

라우터(`app/routes.tsx`)에 `<Route path="/search" element={<BlogSearchPage />} />`를 더했다. 블로그 주소의 화면이라 서버의 화면 주소 처리(`SpaForwardController`)가 `/search`를 `index.html`로 돌려준다([18](./18-spa-server-routing.md)).

### (스텝 9) 이스케이프를 `global/web/LikePatterns`로 옮겼다

스텝 9의 내 글 관리(MNG-01)도 제목 검색에 같은 LIKE 이스케이프가 필요해, 위에서 본 `SearchService.escapeLike`와 `ESCAPE` 상수를 공용 클래스 `global/web/LikePatterns`로 옮겼다. 규칙은 그대로다. 지금 `SearchService`는 이렇게 쓴다.

```java
String pattern = LikePatterns.contains(query);          // "%" + 이스케이프한 글자 + "%"
...
cb.like(root.get("title"), pattern, LikePatterns.ESCAPE)
```

같은 규칙을 두 곳에 복사해 두면 한쪽만 고치는 실수가 생기고, 기능 패키지(`manage`)가 다른 기능 패키지(`search`)를 가져다 쓰는 것도 피하고 싶었다. 이 문서 5장의 코드 발췌는 스텝 7 당시 모습이다. 자세한 것은 [37](./37-filtered-list-bulk-actions.md) 5.4.

## 6. 자주 하는 실수와 함정

- **HTML 칸에서 LIKE로 찾는다.** `strong`, `href`, `amp`로 엉뚱한 글이 걸리고 `&` 검색이 틀린다. 글자만 담은 칸에서 찾는다.
- **사용자 입력을 그대로 패턴에 넣는다.** `%`, `_`가 와일드카드로 동작해 결과가 틀린다. 이스케이프하고 `ESCAPE`를 지정한다. 백슬래시를 먼저 바꾼다.
- **앞뒤 `%`까지 이스케이프한다.** 그러면 "들어간"이 아니라 글자 그대로 `%jpa%`를 찾는다.
- **`LOWER()`를 칸에 씌운다.** 정렬 규칙이 이미 대소문자를 무시한다. 함수를 씌우면 쿼리만 복잡해진다. 반대로 정렬 규칙이 `_bin`이나 `_cs`인 DB로 옮기면 대소문자 무시가 사라진다는 점을 기억한다.
- **여럿인 쪽(태그)을 조인해 OR로 묶는다.** 같은 글이 여러 번 나오고 전체 개수가 틀리며, 안쪽 조인이면 태그 없는 글이 빠진다. EXISTS를 쓴다.
- **검색만 가시성 조건을 빼먹는다.** 목록에서는 숨긴 비공개 글이 검색에서 제목과 요약까지 보인다. 목록과 같은 `listedIn`을 쓴다.
- **비정규화 칸을 한 곳에서만 채운다.** 발행에서는 `content_text`를 채우고 수정에서 빠뜨리면, 고친 글이 옛 내용으로 검색된다. 이 프로젝트는 `PostBody` 하나로 세 칸을 늘 같이 바꾼다.
- **이미 적용한 V1을 고친다.** 체크섬이 달라져 Flyway가 앱을 띄우지 않는다. 새 버전 파일로 더한다.
- **NOT NULL 칸을 한 번에 더한다.** 기존 행이 빈 값이 되거나 마이그레이션이 실패한다. 더하기 → 채우기 → NOT NULL.
- **검색어를 화면 상태에만 둔다.** 새로고침하면 사라지고 주소를 나눌 수 없다. 주소의 쿼리 문자열을 원천으로 쓴다.
- **쿼리 문자열을 문자열 이어 붙이기로 만든다.** `&`, `#`, `%`, 한글에서 깨진다. `URLSearchParams`를 쓴다.
- **"LIKE는 늘 느리다"거나 "늘 괜찮다"고 단정한다.** 표 크기와 다른 조건으로 좁힐 수 있는지에 달렸다. `EXPLAIN`으로 확인한다.

## 7. 직접 해 보기

준비: `docker compose up -d`, 서버 실행, A 계정 쿠키 `jarA.txt`, 블로그 주소 `alpha`.

### 7.1 검색 요청

```bash
R=(--resolve alpha.blog.test:8080:127.0.0.1)
U=http://alpha.blog.test:8080
curl -s "${R[@]}" -G $U/api/search --data-urlencode 'q=jpa' | python3 -m json.tool | head -30
curl -s "${R[@]}" -G $U/api/search --data-urlencode 'q=   ' | python3 -m json.tool        # 400, field q
curl -s "${R[@]}" -o /dev/null -w '%{http_code}\n' $U/api/search                           # 400
curl -s "${R[@]}" -b jarA.txt -G $U/api/search --data-urlencode 'q=비공개' | python3 -c \
  "import json,sys;print(json.load(sys.stdin)['totalElements'])"                            # 주인은 비공개 글도
```

`--data-urlencode 'q=100%'`를 쓰면 curl이 `%`를 `%25`로 바꿔 보낸다. 직접 `?q=100%`라고 주소에 쓰면 `%`가 잘못된 인코딩으로 읽힐 수 있다.

### 7.2 HTML이 아니라 글자에서 찾는지

```bash
curl -s "${R[@]}" -b jarA.txt -H 'X-Requested-With: XMLHttpRequest' -H 'Content-Type: application/json' \
  -H "Idempotency-Key: $(uuidgen)" -X POST $U/api/posts \
  -d '{"title":"검색 실습","contentHtml":"<p><strong>굵게</strong> 100% &amp; a_b</p>","visibility":"PUBLIC","status":"PUBLISHED"}'
for q in strong amp '100%' '&' '_' 굵게; do
  printf '%-8s ' "$q"; curl -s "${R[@]}" -G $U/api/search --data-urlencode "q=$q" | python3 -c \
    "import json,sys;print(json.load(sys.stdin)['totalElements'])"
done
```

`strong`, `amp`는 이 글에서 0건이어야 한다(다른 글에 그 글자가 실제로 있으면 나올 수 있다).

### 7.3 DB에서 두 칸 비교

```bash
docker exec -it blog-mysql mysql --default-character-set=utf8mb4 -ublog -pblog blog
```

```sql
SELECT id, LEFT(content_html, 60) AS html, LEFT(content_text, 60) AS text FROM post ORDER BY id DESC LIMIT 5;
-- V3로 채운 옛 글과 jsoup으로 채운 새 글의 차이(문자 참조, 공백)를 찾아본다
SELECT id, content_text FROM post WHERE content_text LIKE '%&amp;%';
SELECT version, description, checksum FROM flyway_schema_history;
```

### 7.4 정렬 규칙과 EXPLAIN

```sql
SELECT COLUMN_NAME, COLLATION_NAME FROM information_schema.COLUMNS
 WHERE TABLE_SCHEMA = 'blog' AND TABLE_NAME = 'post' AND COLUMN_NAME IN ('title', 'content_text');
SELECT 'Spring JPA' LIKE '%jpa%' AS ci, '100% 할인' LIKE '%100\%%' AS escaped, '1000원' LIKE '%100\%%' AS escaped2;

SHOW INDEX FROM post;
EXPLAIN SELECT id FROM post WHERE title LIKE '%spring%';
EXPLAIN SELECT id FROM post WHERE title LIKE 'spring%';
EXPLAIN SELECT id FROM post WHERE blog_id = 1 AND status = 'PUBLISHED' AND title LIKE '%spring%';
```

개발 DB에서 처음 두 `EXPLAIN`은 모두 `type: ALL`(표 전체 읽기)이었다. `title`에는 인덱스가 없기 때문이다. 연습 브랜치에서 `CREATE INDEX ix_tmp_title ON post (title);`를 만들고 다시 보면, `'spring%'`는 인덱스 범위 검색을 쓸 수 있고 `'%spring%'`는 여전히 쓸 수 없는 차이를 볼 수 있다(행이 아주 적으면 옵티마이저가 그래도 전체 읽기를 고를 수 있다). 실습이 끝나면 `DROP INDEX ix_tmp_title ON post;`로 지운다. 세 번째 쿼리에서 `key`에 `idx_post_blog_feed`가 나오는지 본다.

### 7.5 실제로 나가는 SQL

`application-dev.yml`에 잠깐 `logging.level.org.hibernate.SQL: debug`를 더하고 검색을 한 번 한다. 로그에서 `exists(select ...)`, `like ? escape '\'`, 그리고 전체 개수를 세는 두 번째 `select count(...)`를 찾는다.

### 7.6 화면

1. 블로그 머리글 검색 칸에 `JPA`를 치고 Enter → 주소가 `/search?q=JPA`.
2. 결과 2쪽으로 간 뒤 주소를 복사해 시크릿 창에서 연다 → 같은 2쪽(비회원이라 비공개 글은 빠짐).
3. 뒤로 가기 → 1쪽. 새로고침 → 검색 칸에 `JPA`가 남아 있다.
4. 검색 칸에 공백만 넣고 Enter → 이동하지 않는다. 주소를 `/search?q=%20`으로 직접 열면 서버의 400 문장이 보인다.

### 7.7 테스트

```bash
./mvnw test -Dtest=SearchIntegrationTest
```

연습 브랜치에서 `escapeLike`의 첫 `replace("\\", "\\\\")`를 맨 뒤로 옮기거나, `search`에서 `contentText` 대신 `contentHtml`로 바꿔 보고 어느 테스트가 깨지는지 확인한다.

## 8. 확인 문제

1. `LIKE '%100%%'`가 "1000원짜리"에도 맞는 이유와, 고치는 방법은?
<details><summary>답</summary>사용자가 친 끝의 <code>%</code>도 와일드카드(아무 글자 0개 이상)로 해석되어 "100이 들어간 모든 문자열"이 된다. 사용자 글자 안의 <code>%</code>, <code>_</code>, <code>\</code> 앞에 이스케이프 문자를 붙이고 <code>ESCAPE '\'</code>로 알린다(<code>%100\%%</code>).</details>

2. `escapeLike`에서 `\`를 가장 먼저 바꿔야 하는 이유는?
<details><summary>답</summary><code>%</code>를 <code>\%</code>로 바꾼 뒤에 <code>\</code>를 두 배로 만들면, 방금 붙인 이스케이프 문자까지 <code>\\%</code>로 바뀌어 "글자 \ 다음 와일드카드 %"가 된다.</details>

3. 코드 어디에도 대소문자를 바꾸는 부분이 없는데 `SECURITY`로 `Spring Security`가 찾히는 이유는?
<details><summary>답</summary>칸의 정렬 규칙이 <code>utf8mb4_0900_ai_ci</code>(대소문자 무시)라 MySQL이 LIKE 비교에서 대소문자를 구분하지 않는다.</details>

4. `content_html`에서 검색하지 않고 `content_text`를 따로 둔 이유와, 그 대가는?
<details><summary>답</summary>HTML의 태그 이름·속성·문자 참조(<code>strong</code>, <code>href</code>, <code>&amp;amp;</code>)가 검색에 걸리기 때문이다. 대가는 비정규화라 두 칸이 늘 맞아야 한다는 책임이다. 이 프로젝트는 <code>PostBody</code>로 html·text·summary를 늘 함께 바꿔 지킨다.</details>

5. V3 마이그레이션이 `ADD COLUMN ... NOT NULL` 한 줄이 아니라 세 단계인 이유는?
<details><summary>답</summary>기존 행에 값이 없으므로 NOT NULL로 바로 더하면 빈 값으로 채워지거나 실패한다. NULL 허용으로 더하고, 기존 행을 채우고, 그다음 NOT NULL로 바꾼다.</details>

6. 칸 하나를 더하는데 V1을 고치지 않고 V3를 새로 만든 이유는?
<details><summary>답</summary>V1은 이미 여러 DB에 적용되어 Flyway가 체크섬을 기록했다. 파일을 고치면 검증에 실패해 앱이 뜨지 않는다. 적용된 마이그레이션은 그대로 두고 바뀔 내용을 새 버전으로 더한다.</details>

7. 태그 이름 검색을 조인이 아니라 EXISTS로 하는 이유를 두 가지 들어라.
<details><summary>답</summary>한 글의 여러 태그가 맞으면 조인은 같은 글을 여러 줄 돌려줘 목록과 전체 개수가 틀린다. 안쪽 조인이면 태그 없는 글이 제목·본문 검색에서도 빠진다. EXISTS는 바깥 글마다 참·거짓만 보므로 둘 다 생기지 않는다.</details>

8. `tagged.correlate(root)`는 무엇을 하나?
<details><summary>답</summary>부분 쿼리 안에서 바깥 쿼리의 같은 글 행을 가리키는 별칭을 만든다. 거기서 <code>join("tags")</code>하면 "바깥 글의 태그들"이 되어 <code>post_tag.post_id = 바깥 post.id</code> 조건이 생긴다(상관 부분 쿼리).</details>

9. `title`에 B-tree 인덱스가 있어도 `LIKE '%spring%'`이 그 인덱스로 구간을 찾지 못하는 이유는?
<details><summary>답</summary>B-tree는 값의 앞에서부터 정렬해 저장한다. 앞이 고정된 <code>'spring%'</code>은 정렬된 한 구간이지만, 앞에 <code>%</code>가 있으면 맞는 값이 정렬 순서 곳곳에 흩어져 있어 구간을 정할 수 없다.</details>

10. 검색 결과 화면이 검색어를 `useState`가 아니라 주소(`useSearchParams`)에서 읽는 이유는?
<details><summary>답</summary>주소가 원천이면 결과 주소를 나누거나 새로고침해도 같은 결과가 나오고, 뒤로 가기가 이전 검색으로 돌아간다. Thymeleaf GET 폼과 <code>@RequestParam</code>의 성질과 같다.</details>

11. 검색에도 `PostSpecifications.listedIn`을 쓰는 이유는?
<details><summary>답</summary>검색 결과도 글 목록이라 볼 수 없는 글의 제목·요약이 보이면 안 된다. 목록과 같은 조건 하나를 써야 규칙이 어긋나지 않는다(주인에게는 비공개 글도 나온다).</details>

## 9. 더 읽을거리

- MySQL 8.4 Reference Manual: "String Comparison Functions and Operators"(`LIKE`, `ESCAPE`), "Character Sets, Collations, Unicode", "ngram Full-Text Parser", "Full-Text Search Functions"
- MySQL 8.4 Reference Manual: "Regular Expressions"(`REGEXP_REPLACE`), "EXPLAIN Output Format"
- Use The Index, Luke! (Markus Winand): "LIKE Filters"(앞에 `%`가 있을 때 인덱스)
- jsoup 문서: `Jsoup.parse`, `Element.text()`
- Flyway 문서: "Migrations"(버전 마이그레이션, 체크섬과 validate)
- 이 저장소: `research.md` R-16, `erd/schema.sql`의 `post.content_text`(ERD 버전 79), `contracts/rest-api.md`의 `GET /api/search`
