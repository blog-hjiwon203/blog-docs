# 페이지네이션: 페이지 번호와 커서

> 관련 스텝: [스텝 2](../step-02.md)(T012 `PageQuery`, `PageResponse`, `CursorResponse`, `TimeIdCursor`), [스텝 4](../step-04.md)(블로그 메인 글 목록 `GET /api/posts`, 화면의 페이지 번호 묶음)
> 기준 버전: Spring Data JPA 4(Spring Boot 4.1.1), MySQL 8.4

## 1. 이 문서로 배우는 것

- 목록을 나눠서 주는 두 가지 방법: **페이지 번호(offset)**와 **커서(keyset)**
- 각각이 만드는 SQL, offset이 뒤로 갈수록 느려지는 이유
- 정렬 안정성: 같은 시각의 글이 있을 때 id로 순서를 확정해야 하는 이유
- 인덱스와 페이지네이션의 관계(`idx_post_home_feed` 등)
- 커서를 불투명 문자열로 주는 이유, "하나 더 읽기" 기법
- Spring Data의 `Pageable`, `PageRequest`, `Page`(0부터 셈)
- 이 프로젝트의 `PageQuery`, `PageResponse`, `CursorResponse`, `TimeIdCursor`와 문서끼리 규칙이 달랐던 사건
- (스텝 4) 처음 실제로 쓴 목록 API(블로그 메인)와, 화면에서 페이지 번호를 10개씩 묶어 보여 주는 방법

**먼저 알면 좋은 것**: SQL `ORDER BY`, `LIMIT`, `WHERE`, 인덱스가 무엇인지(책의 색인처럼 정렬된 목록), [JPA 기초](./06-jpa-entity-mapping.md), [예외 처리](./07-spring-mvc-exception-handling.md)(400 응답).

## 2. 왜 필요한가

블로그 글이 10만 개 있다. 홈 화면이 `SELECT * FROM post ORDER BY published_at DESC`로 전부 가져오면:

- DB가 10만 행을 읽고 정렬하고, 네트워크로 보내고, 서버 메모리에 올리고, JSON으로 만든다.
- 사용자는 그중 처음 20개만 본다.
- 동시에 100명이 열면 서버가 버티지 못한다.

그래서 목록은 **조금씩 나눠서** 준다. 나누는 방법에 따라 화면 모양과 성능이 달라진다.

| 화면 | 방식 | 이 프로젝트 목록 (research.md R-06) |
| --- | --- | --- |
| `◀ 1 2 3 4 5 ▶` 번호를 눌러 이동 | 페이지 번호 | 블로그 글 목록, 블로그 내 검색, 내 글 관리, 방명록 |
| 아래로 내리면 "더보기" | 커서 | 홈 최신 글, 구독 피드, 댓글 |

## 3. 기본 개념

### 3.1 페이지 번호(offset) 방식

"한 쪽에 10개씩, 3쪽을 줘" = 앞의 20개를 건너뛰고 10개.

```sql
SELECT * FROM post
 WHERE blog_id = 7 AND status = 'PUBLISHED'
 ORDER BY published_at DESC, id DESC
 LIMIT 10 OFFSET 20;               -- 3쪽 (쪽 번호 1부터: OFFSET = (3 - 1) × 10)

SELECT COUNT(*) FROM post
 WHERE blog_id = 7 AND status = 'PUBLISHED';   -- 전체 개수 → 전체 쪽 수 계산
```

응답:

```json
{ "content": [ ...10개... ], "page": 3, "size": 10, "totalElements": 57, "totalPages": 6 }
```

- **장점**: 원하는 쪽으로 바로 간다. 전체 개수와 쪽 수를 보여 줄 수 있다.
- **단점**: 뒤쪽일수록 느리다(4.1). 쪽을 넘기는 사이 새 글이 생기면 **중복·누락**이 생긴다(4.2). 개수 쿼리가 한 번 더 나간다.

### 3.2 커서(keyset) 방식

"마지막으로 본 글 **다음부터** 20개".

```sql
-- 처음
SELECT * FROM post WHERE status = 'PUBLISHED' AND visibility = 'PUBLIC'
 ORDER BY published_at DESC, id DESC
 LIMIT 21;

-- 다음 (마지막 글이 published_at = '2026-10-08 13:20:00', id = 1532 였다면)
SELECT * FROM post WHERE status = 'PUBLISHED' AND visibility = 'PUBLIC'
   AND (published_at < '2026-10-08 13:20:00'
        OR (published_at = '2026-10-08 13:20:00' AND id < 1532))
 ORDER BY published_at DESC, id DESC
 LIMIT 21;
```

응답:

```json
{ "content": [ ...20개... ], "nextCursor": "MjAyNi0xMC0wOFQxMzoyMCwxNTMy" }   // 끝이면 null
```

- **장점**: 몇 번째 페이지든 속도가 같다. 새 글이 위에 생겨도 중복·누락이 없다. 개수 쿼리가 없다.
- **단점**: "7쪽으로 바로 가기"가 안 된다. 전체 개수를 모른다. 정렬 기준이 바뀌면 커서도 바뀌어야 한다.

### 3.3 용어

| 용어 | 뜻 |
| --- | --- |
| page | 몇 번째 쪽. 이 프로젝트 API는 **1부터** |
| size | 한 쪽의 개수. 이 프로젝트는 1~50 |
| offset | 건너뛸 행 수 = (page − 1) × size |
| totalElements / totalPages | 전체 행 수 / 전체 쪽 수 |
| cursor | "여기 다음부터"를 나타내는 값. 마지막 항목의 정렬 기준 값들 |
| tie-break | 정렬 기준이 같을 때 순서를 정하는 보조 기준(여기서는 id) |

## 4. 동작 원리

### 4.1 offset이 느려지는 이유

`LIMIT 10 OFFSET 100000`이라고 해서 DB가 100001번째 행으로 바로 뛰어가지 못한다. **앞의 10만 행을 정렬 순서대로 하나씩 세면서 버린 뒤** 10개를 준다.

```
OFFSET 0       → 10행 읽음
OFFSET 1,000   → 1,010행 읽음
OFFSET 100,000 → 100,010행 읽음  (버릴 행을 읽는 데 대부분의 시간을 씀)
```

인덱스가 있어도 "몇 번째인지" 세는 일은 남는다. 블로그 한 곳의 글은 많지 않아 페이지 번호 방식이 괜찮지만, 서비스 전체 글이 모이는 홈 피드는 커서 방식을 쓴다.

### 4.2 offset의 중복·누락

사용자가 1쪽(글 1~10)을 보는 사이 새 글 A가 발행됐다.

```
1쪽을 볼 때:  [10 9 8 7 6 5 4 3 2 1] 0 -1 ...     (최신순)
2쪽을 열 때:  A [10 9 8 7 6 5 4 3 2] [1 0 -1 ...]
                                     └ OFFSET 10부터 → 글 1이 2쪽 맨 위에 또 나온다 (중복)
```

글이 지워지면 반대로 한 개를 **건너뛴다**(누락). 커서 방식은 "글 1 다음부터"라고 값으로 기억하므로 이런 일이 없다.

### 4.3 정렬 안정성과 tie-break

`ORDER BY published_at DESC`만 쓰면, **발행 시각이 같은 글 두 개**의 순서를 DB가 보장하지 않는다. 같은 쿼리를 두 번 실행해도 순서가 바뀔 수 있다.

- offset: 1쪽 끝과 2쪽 처음에 같은 글이 나오거나, 한 글이 어느 쪽에도 안 나온다.
- 커서: `published_at < '13:20'`만 쓰면 13:20에 발행된 나머지 글이 **통째로 빠진다**.

그래서 정렬 기준에 **유일한 값(id)을 마지막에** 붙인다: `ORDER BY published_at DESC, id DESC`. spec.md가 "최신순 = 처음 발행 시각 내림차순, 같으면 나중에 만든 글이 위"라고 정한 이유다.

커서 조건도 두 값을 함께 본다.

```sql
-- (published_at, id) 가 (T, I) 보다 "뒤"(더 오래된 쪽)
published_at < T OR (published_at = T AND id < I)
```

MySQL은 행 비교 문법 `(published_at, id) < (T, I)`도 지원한다. 뜻은 같지만, 인덱스를 어떻게 타는지는 `EXPLAIN`으로 확인해 보는 것이 좋다. 위처럼 풀어 쓴 형태가 흔히 쓰인다.

### 4.4 인덱스와의 관계

인덱스는 정해진 컬럼 순서로 **미리 정렬된** 목록이다. 쿼리의 `WHERE`(같다 조건)와 `ORDER BY`가 인덱스 순서와 맞으면, DB는 정렬 없이 인덱스를 앞에서부터(또는 커서 위치부터) 읽다가 `LIMIT` 개수만 채우고 멈춘다.

`erd/schema.sql`(= `V1__init.sql`)의 글 인덱스:

```sql
CREATE INDEX idx_post_blog_feed  ON post (blog_id ASC, status ASC, visibility ASC, published_at DESC, id DESC);
CREATE INDEX idx_post_home_feed  ON post (status ASC, visibility ASC, published_at DESC, id DESC);
CREATE INDEX idx_post_topic_feed ON post (topic ASC, status ASC, visibility ASC, published_at DESC);
```

홈 최신 글 쿼리와 `idx_post_home_feed`를 나란히 보면:

```
WHERE status = 'PUBLISHED'         ← 인덱스 1번 컬럼 (같다)
  AND visibility = 'PUBLIC'        ← 인덱스 2번 컬럼 (같다)
  AND (published_at, id) 커서 조건  ← 인덱스 3·4번 컬럼 (범위 시작점)
ORDER BY published_at DESC, id DESC ← 인덱스 3·4번 순서와 같음 → 정렬 단계 없음
LIMIT 21                            ← 21개 읽고 멈춤
```

- 인덱스 끝에 `id DESC`까지 넣은 것이 tie-break와 짝이다.
- 같다 조건 컬럼을 앞에, 정렬 컬럼을 뒤에 두는 것이 원칙이다. 순서가 바뀌면 인덱스를 써도 정렬을 따로 해야 한다.
- MySQL 8은 `DESC` 인덱스를 실제로 내림차순으로 저장한다(8.0부터).

### 4.5 "하나 더 읽기" 기법

커서 방식에서 "다음이 있는가"를 알려면 `COUNT`를 해야 할까? 아니다. **size보다 하나 더(size + 1개)** 읽으면 된다.

```
size = 20, LIMIT 21로 읽음
  ├ 21개가 왔다 → 다음이 있다. 앞 20개만 주고, 20번째 항목으로 nextCursor를 만든다
  └ 20개 이하   → 끝이다. 전부 주고 nextCursor = null
```

### 4.6 커서를 불투명 문자열로 주는 이유

커서 안에는 `published_at`과 `id`가 들어 있다. 그대로 `?after=2026-10-08T13:20:00&afterId=1532`처럼 줘도 동작은 한다. 그래도 base64로 감싼 하나의 문자열로 주는 이유:

- **프론트가 해석하지 않게** 한다. 정렬 기준이 바뀌거나 값이 더해져도(예: 인기순 점수) API 모양이 그대로다.
- 파라미터 하나로 끝난다. "이 둘은 짝"이라는 규칙을 프론트가 지킬 필요가 없다.
- URL에 넣기 안전한 글자만 쓴다(`Base64.getUrlEncoder()`는 `+`, `/` 대신 `-`, `_`를 쓴다).

base64는 **암호화가 아니다**. 누구나 풀 수 있다. 숨기려는 것이 아니라 "해석하지 말라"는 약속이다. 그래서 서버는 받은 커서를 믿지 않고, 형식이 틀리면 400을 준다.

### 4.7 Spring Data의 페이지 도구

| 타입 | 뜻 |
| --- | --- |
| `Pageable` | "몇 쪽, 몇 개, 어떤 정렬"을 담는 인터페이스 |
| `PageRequest.of(page, size, sort)` | `Pageable` 만들기. **page는 0부터** |
| `Sort.by(Direction.DESC, "publishedAt").and(Sort.by(Direction.DESC, "id"))` | 정렬 |
| `Page<T>` | 결과. `getContent()`, `getNumber()`(0부터), `getSize()`, `getTotalElements()`, `getTotalPages()` |
| `Slice<T>` | 개수 쿼리 없이 "다음이 있나"(`hasNext()`)만 아는 결과(내부적으로 하나 더 읽음) |

```java
Page<Post> page = postRepository.findAll(spec, PageRequest.of(0, 10, sort));
// 실행되는 쿼리: SELECT ... LIMIT 10 OFFSET 0  +  SELECT COUNT(...)
```

Repository 메서드가 `Page<T>`를 돌려주면 Spring Data가 내용 쿼리와 **개수 쿼리를 둘 다** 실행한다.

## 5. 이 프로젝트에서는

경로는 코드 저장소 `src/main/java/com/nhnacademy/blog/global/web/` 기준이다. 스텝 3까지는 이 도구를 쓰는 목록 API가 없었고, 스텝 4의 블로그 글 목록(5.7)에서 처음 썼다.

### 5.1 요청 검증: `PageQuery.java`

```java
/**
 * 페이지 번호 목록 요청 (contracts/rest-api.md 목록). page는 1부터, size는 1~50.
 * 생략하면 page 1, size는 목록마다 정한 기본값이다. 범위를 벗어나면 400 VALIDATION_FAILED.
 */
public record PageQuery(int page, int size) {

    public static final int MAX_SIZE = 50;

    public static PageQuery of(Integer page, Integer size, int defaultSize) {   // Integer: 안 보냈으면 null
        List<FieldErrorDetail> errors = new ArrayList<>();
        if (page != null && page < 1) {
            errors.add(new FieldErrorDetail("page", "페이지는 1부터입니다."));
        }
        if (size != null && (size < 1 || size > MAX_SIZE)) {
            errors.add(new FieldErrorDetail("size", "한 번에 1~" + MAX_SIZE + "개까지 볼 수 있습니다."));
        }
        if (!errors.isEmpty()) {                       // 둘 다 틀렸으면 둘 다 알려 준다
            throw BusinessException.fieldErrors(ErrorCode.VALIDATION_FAILED, errors);
        }
        return new PageQuery(page == null ? 1 : page, size == null ? defaultSize : size);
    }

    /** Spring Data는 0부터 세므로 하나 뺀다. */
    public Pageable toPageable(Sort sort) {
        return PageRequest.of(page - 1, size, sort);
    }
}
```

- **size 상한이 있는 이유**: `?size=100000`으로 한 번에 다 가져가는 요청을 막는다. 페이지네이션의 목적(2절)을 지키는 장치다.
- **기본값을 인자로 받는 이유**: 목록마다 기본 개수가 다르다(블로그 글 10, 내 글 관리 20, 방명록 20). 컨트롤러가 `PageQuery.of(page, size, 10)`처럼 부른다.
- **API는 1부터, 내부는 0부터**: 사람에게 보이는 쪽 번호는 1부터가 자연스럽다. Spring Data와의 차이는 이 클래스 한 곳(`toPageable`)에서만 맞춘다.

### 5.2 응답: `PageResponse.java`

```java
public record PageResponse<T>(List<T> content, int page, int size, long totalElements, int totalPages) {

    public static <T> PageResponse<T> from(Page<T> page) {
        return new PageResponse<>(page.getContent(), page.getNumber() + 1, page.getSize(),  // 0부터 → 1부터
                page.getTotalElements(), page.getTotalPages());
    }

    public static <E, T> PageResponse<T> from(Page<E> page, Function<E, T> mapper) {
        return from(page.map(mapper));                   // 엔티티 → 응답 DTO로 바꾸면서
    }
}
```

- `Page`를 그대로 JSON으로 내보내지 않는 이유: `Page` 객체를 직렬화하면 `pageable`, `sort`, `first`, `last` 같은 Spring 내부 구조가 그대로 나가고, Spring 버전에 따라 모양이 바뀔 수 있다. API 모양은 rest-api.md가 정한 다섯 필드로 고정한다.
- 마지막 쪽을 넘는 번호(`?page=99`)는 오류가 아니라 **빈 `content`**다(R-06). `Page`가 원래 그렇게 동작한다.

### 5.3 커서 응답: `CursorResponse.java`

```java
public record CursorResponse<T>(List<T> content, String nextCursor) {

    /**
     * 한 개 더 읽은 결과(size + 1개)로 응답을 만든다. 넘친 것이 있으면 마지막 항목으로 다음 커서를 만든다.
     */
    public static <T> CursorResponse<T> of(List<T> fetched, int size, Function<T, String> cursorOf) {
        if (fetched.size() <= size) {                              // 다 왔다 = 끝
            return new CursorResponse<>(List.copyOf(fetched), null);
        }
        List<T> content = List.copyOf(fetched.subList(0, size));   // 넘친 하나는 버림
        return new CursorResponse<>(content, cursorOf.apply(content.getLast()));   // 실제로 준 마지막 항목 기준
    }
}
```

- 4.5의 "하나 더 읽기"를 그대로 옮겼다. 쓰는 쪽은 `LIMIT size + 1`로 읽어 넘긴다.
- 다음 커서는 **넘친 21번째가 아니라 실제로 준 20번째 항목**으로 만든다. 21번째로 만들면 다음 요청이 21번째를 건너뛴다.
- `content.getLast()`는 Java 21의 `SequencedCollection` 메서드다.

### 5.4 커서 값: `TimeIdCursor.java`

```java
public record TimeIdCursor(LocalDateTime time, long id) {

    private static final String SEPARATOR = ",";

    public String encode() {
        String raw = time + SEPARATOR + id;           // "2026-10-08T13:20,1532"
        return Base64.getUrlEncoder().withoutPadding().encodeToString(raw.getBytes(StandardCharsets.UTF_8));
    }

    /** null이면 처음부터라는 뜻이라 null을 돌려준다. 형식이 틀리면 400. */
    public static TimeIdCursor decode(String cursor) {
        if (cursor == null) {
            return null;
        }
        try {
            String raw = new String(Base64.getUrlDecoder().decode(cursor), StandardCharsets.UTF_8);
            String[] parts = raw.split(SEPARATOR, -1);
            if (parts.length != 2) {
                throw invalid();
            }
            return new TimeIdCursor(LocalDateTime.parse(parts[0]), Long.parseLong(parts[1]));
        } catch (IllegalArgumentException | DateTimeParseException e) {   // base64·숫자·날짜 형식 오류 모두
            throw invalid();
        }
    }
```

- `time`에는 목록에 따라 다른 시각이 들어간다. 최신순 글 목록은 `published_at`, 작성순 댓글은 `created_at`. 그래서 이름이 `PublishedCursor`가 아니라 `TimeIdCursor`다.
- `LocalDateTime.toString()`은 ISO-8601이고 초 이하가 있으면 그대로 남는다(`2026-10-08T13:20:00.123456`). `post.published_at`이 `DATETIME(6)`(마이크로초)이라 정밀도를 잃지 않고 왕복한다(테스트 `roundTrip`).
- `withoutPadding()`: base64 끝의 `=`를 빼서 URL에 그대로 넣기 쉽게 한다. 디코더는 패딩이 없어도 읽는다.
- `Long.parseLong`이 던지는 `NumberFormatException`은 `IllegalArgumentException`의 하위 클래스라서 같은 `catch`에 잡힌다.

### 5.5 커서를 쓰는 쿼리 모양 (스텝 6에서 만들 홈 최신 글 예시)

아직 코드에 없다. 위 도구들이 어떻게 맞물리는지 보여 주는 예다.

```java
TimeIdCursor after = TimeIdCursor.decode(cursor);                 // 처음이면 null
List<Post> fetched = postQueryRepository.findHomeFeed(after, size + 1);   // WHERE 커서 조건 ... LIMIT size+1
return CursorResponse.of(fetched, size,
        post -> new TimeIdCursor(post.getPublishedAt(), post.getId()).encode());
```

### 5.6 (스텝 4) 처음 쓴 곳: 블로그 메인 글 목록

**서버**: `post/presentation/PostController.java`, `post/application/PostQueryService.java`

```java
@GetMapping("/api/posts")
public PageResponse<PostSummaryResponse> posts(@CurrentBlog Blog blog,
                                               @RequestParam(required = false) Integer page,
                                               @RequestParam(required = false) Integer size,
                                               @RequestParam(required = false) Long categoryId) {
    PageQuery pageQuery = PageQuery.of(page, size, PostQueryService.BLOG_PAGE_SIZE);
    return PageResponse.from(
            postQueryService.blogPosts(blog, LoginMembers.currentId(), categoryId, pageQuery),
            post -> PostSummaryResponse.of(post, blog));
}
```

```java
public static final int BLOG_PAGE_SIZE = 10;
private static final Sort LATEST = Sort.by(Sort.Order.desc("publishedAt"), Sort.Order.desc("id"));
...
return postRepository.findAll(condition, page.toPageable(LATEST));
```

- `Integer page`, `Integer size`(`int`가 아님): 안 보내면 null이 되어야 `PageQuery.of`가 기본값(1쪽, 10개)을 넣을 수 있다.
- `PageQuery.of`를 `@CurrentBlog` 뒤, 메서드 안에서 부른다. 없는 블로그에 `?page=0`을 보내면 400이 아니라 404가 먼저 나간다(상태 코드 순서, [가시성](./16-authorization-visibility.md)).
- 정렬 `publishedAt DESC, id DESC`: spec "목록과 페이지"의 "최신순 = 처음 발행 시각 내림차순, 같으면 나중에 만든 글이 위". 4.3의 tie-break 그대로다. 글을 수정해도 `published_at`은 바뀌지 않으므로 순서가 그대로다.
- `condition`은 가시성 조건(`listedIn`)이라, 목록 쿼리와 개수 쿼리가 같은 조건을 쓴다. 6절의 "개수에 볼 수 없는 글이 섞이는" 실수를 피한다.
- `PageResponse.from(page, mapper)`로 엔티티를 응답 DTO로 바꾼다.

**테스트**: `src/test/.../post/BlogPostListIntegrationTest.java`의 `latestFirstTenPerPageAndTieBrokenById`

```java
LocalDateTime base = LocalDateTime.of(2026, 10, 1, 9, 0);
Post[] posts = new Post[12];
for (int i = 0; i < 12; i++) {
    posts[i] = testPosts.published(blog, null, Visibility.PUBLIC, base.plusHours(i));
}
// 발행 시각이 같으면 나중에 만든 글이 위다
Post sameTime = testPosts.published(blog, null, Visibility.PUBLIC, base.plusHours(11));

list(null, "")
        .andExpect(jsonPath("$.content", hasSize(10)))
        .andExpect(jsonPath("$.totalElements").value(13))
        .andExpect(jsonPath("$.totalPages").value(2))
        .andExpect(jsonPath("$.content[0].id").value(sameTime.getId()))
        .andExpect(jsonPath("$.content[1].id").value(posts[11].getId()))
        ...
list(null, "?page=2")
        .andExpect(jsonPath("$.content[*].id", contains(posts[2].getId().intValue(),
                posts[1].getId().intValue(), posts[0].getId().intValue())));
list(null, "?page=999").andExpect(status().isOk()).andExpect(jsonPath("$.content", hasSize(0)));
list(null, "?size=51").andExpect(status().isBadRequest());
list(null, "?page=0").andExpect(status().isBadRequest());
```

| 확인하는 것 | 줄 |
| --- | --- |
| 한 쪽 10개, 전체 13개면 2쪽 | `hasSize(10)`, `totalElements 13`, `totalPages 2` |
| 발행 시각이 같으면 id가 큰(나중에 만든) 글이 위 | `posts[11]`과 같은 시각인 `sameTime`이 0번 |
| 2쪽은 나머지 3개 | `page=2` → posts[2], [1], [0] |
| 마지막 쪽을 넘으면 빈 목록(200) | `page=999` |
| 범위 밖은 400 | `size=51`, `page=0` |

처음 이 테스트를 쓸 때 2쪽 기대값을 2개로 잘못 적어 실패했다(13개 = 10 + 3). 테스트가 틀릴 수도 있다는 것, 실패하면 코드와 기대값 중 어느 쪽이 틀렸는지 먼저 따져야 한다는 것을 보여 준 예다.

**화면: 페이지 번호 10개 묶음**: `frontend/src/components/pageGroup.ts`, `Pagination.tsx`

spec "목록과 페이지"는 "페이지 번호는 10개씩 묶어 보여 주고 이전·다음 버튼을 둔다"고 정했다. 25쪽이 있고 지금 15쪽이면 `[이전] 11 12 … 20 [다음]`이다. 계산은 화면과 떼어 순수 함수로 두었다.

```ts
export const PAGE_GROUP = 10

/** 페이지 번호를 10개씩 묶어 보여 준다 (spec 목록과 페이지). current는 1부터. */
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

- `start`: 15쪽이면 `floor(14 / 10) * 10 + 1 = 11`. `current - 1`로 0부터 센 뒤 나누는 것이 요령이다(10쪽은 `floor(9/10)=0`이라 1~10 묶음에 들어간다).
- `end`: 묶음 끝과 실제 마지막 쪽 중 작은 것. 25쪽이 끝이면 21~25.
- `prev`: 이전 묶음의 **마지막** 쪽(11~20 묶음이면 10). `next`: 다음 묶음의 **첫** 쪽(21).
- 테스트 `pageGroup.test.ts`가 첫 묶음, 가운데 묶음, 마지막 묶음, 글이 없을 때를 확인한다.

```tsx
export default function Pagination({ page, totalPages, href }: {
  page: number
  totalPages: number
  href: (page: number) => string
}) {
  const group = pageGroup(page, totalPages)
  if (totalPages <= 1) {
    return null
  }
  return (
    <nav className="pager" aria-label="페이지">
      {group.prev !== null && <Link to={href(group.prev)}>이전</Link>}
      {group.pages.map((number) => (
        <Link key={number} to={href(number)} className={number === page ? 'on' : undefined}
              aria-current={number === page ? 'page' : undefined}>
          {number}
        </Link>
      ))}
      {group.next !== null && <Link to={href(group.next)}>다음</Link>}
    </nav>
  )
}
```

- 쪽 번호를 **주소**(`/?page=3`, `/category/5?page=2`)에 둔다. 새로고침하거나 주소를 공유해도 같은 쪽이 열린다. `href`를 밖에서 받아 전체 글·카테고리 목록이 같은 컴포넌트를 쓴다.
- `aria-current="page"`: 화면 읽기 프로그램에 "지금 쪽"을 알린다.
- 파일 이름 사건: 처음에 계산 함수를 `pagination.ts`로 지었더니 `Pagination.tsx`와 대소문자만 달라, macOS(대소문자를 구분하지 않는 파일 시스템)에서 TypeScript가 두 파일을 같은 파일로 보고 오류를 냈다. 그래서 `pageGroup.ts`로 바꿨다.

### 5.7 사건: 문서끼리 규칙이 달랐다

스텝 2의 T012를 만들려고 문서를 읽었더니 셋이 서로 달랐다.

| 문서 | 규칙 |
| --- | --- |
| tasks.md T012 | "size 1~50 **보정**, page 음수→0" |
| research.md R-06 | "`?page=0&size=10`, size 1~50 보정, 음수 page는 0" |
| contracts/rest-api.md | "`page`는 **1부터**, size 범위를 벗어나면 **400**" |

**보정**(범위 밖이면 가장 가까운 값으로 바꿔서 처리)과 **거절**(400)은 프론트가 받는 결과가 다르다. 보정하면 `?size=1000`이 조용히 50개를 돌려주고, 거절하면 프론트가 잘못을 바로 안다. 이것은 구현이 정할 일이 아니라 **API 약속**이라 지원에게 물었고, 지원이 rest-api.md(1부터, 400)로 정했다. 그 뒤 tasks.md와 research.md를 rest-api.md에 맞게 고쳤다.

배운 점: 문서가 여러 개면 서로 어긋나기 쉽다. 프론트와 백엔드가 함께 보는 **API 명세를 기준**으로 삼고, 어긋남을 찾으면 구현하기 전에 정리한다.

## 6. 자주 하는 실수와 함정

| 실수 | 결과 |
| --- | --- |
| `ORDER BY`에 유일한 값을 넣지 않음 | 같은 값끼리 순서가 바뀌어 중복·누락 |
| 커서 조건을 `published_at < T`만 씀 | 같은 시각의 나머지 글이 통째로 빠짐 |
| 커서를 넘친 마지막 항목으로 만듦 | 그 항목이 다음 요청에서 빠짐 |
| API의 page(1부터)를 그대로 `PageRequest.of`에 넣음 | 첫 쪽을 건너뛰고 2쪽부터 나옴 |
| size 상한 없음 | `?size=1000000`으로 전부 가져가기 |
| `Page` 객체를 그대로 응답 | Spring 내부 필드가 노출, 버전마다 모양 변경 |
| 목록 개수를 셀 때 가시성 조건을 빼먹음 | "글 57개"인데 실제로 보이는 건 50개(볼 수 없는 글 개수가 샘) — 개수 쿼리도 같은 Specification으로 |
| 인덱스와 정렬 방향·컬럼 순서가 다름 | 인덱스를 써도 따로 정렬(filesort), 느려짐 |
| 커서를 서버가 믿고 그대로 SQL에 넣음 | 형식 오류가 500으로 — 디코드 실패는 400으로 |

## 7. 직접 해 보기

1. **offset이 느려지는 것 보기(MySQL)**
   ```bash
   docker exec -it blog-mysql mysql -ublog -pblog blog
   ```
   ```sql
   EXPLAIN SELECT id FROM post WHERE status='PUBLISHED' AND visibility='PUBLIC'
    ORDER BY published_at DESC, id DESC LIMIT 20;
   ```
   `key` 칸에 `idx_post_home_feed`가 나오고 `Extra`에 `Using filesort`가 **없는지** 본다. 그다음 `ORDER BY published_at ASC`로 바꿔 다시 `EXPLAIN` 하고 차이를 본다(행이 적으면 옵티마이저가 인덱스를 안 쓸 수도 있다. 스텝 5 이후 글을 많이 넣고 다시 해 보면 좋다).

2. **커서 풀어 보기**
   ```bash
   echo 'MjAyNi0xMC0wOFQxMzoyMCwxNTMy' | base64 -d     # → 2026-10-08T13:20,1532
   ```
   base64는 암호화가 아니라는 것을 확인한다.

3. **경계 테스트 바꿔 보기**
   - `PageQueryTest.acceptsSizeBounds`에 `PageQuery.of(1, 51, 10)`을 넣어 실패하는지 본다.
   - `./mvnw test -Dtest='PageQueryTest,TimeIdCursorTest'`

4. **중복 현상 손으로 재현하기**
   - 종이에 글 15개(1~15, 큰 번호가 최신)를 쓰고 size=5로 1쪽을 본다(15~11). 새 글 16을 더한 뒤 2쪽(OFFSET 5)을 계산한다. 어떤 글이 두 번 나오는가? 같은 상황을 커서(마지막 = 11)로 계산하면?

5. **(스텝 4) 블로그 메인 목록 테스트와 페이지 번호 묶음**
   ```bash
   ./mvnw test -Dtest='BlogPostListIntegrationTest#latestFirstTenPerPageAndTieBrokenById'
   cd frontend && npx vitest run src/components/pageGroup.test.ts
   ```
   `PostQueryService.LATEST`에서 `Sort.Order.desc("id")`를 지우고 다시 돌려 보자. 같은 발행 시각인 두 글(sameTime, posts[11])의 순서가 보장되지 않아 테스트가 실패하거나 우연히 통과한다. "우연히 통과"도 문제라는 점이 tie-break가 필요한 이유다. 되돌린다.

6. **0부터/1부터 실수 체험**
   - `PageQuery.toPageable`의 `page - 1`을 `page`로 바꾸고 `PageQueryTest`를 돌린다. 어떤 테스트가 왜 실패하는지 본다. 되돌린다.

## 8. 확인 문제

1. `LIMIT 20 OFFSET 200000`이 `LIMIT 20 OFFSET 0`보다 느린 이유는?
   <details><summary>답</summary>DB는 OFFSET 위치로 바로 뛰지 못하고, 정렬 순서대로 앞의 200,000행을 읽어서 버린 뒤 20개를 준다.</details>

2. 커서 방식에서 `ORDER BY published_at DESC, id DESC`의 `id DESC`는 왜 필요한가?
   <details><summary>답</summary>발행 시각이 같은 글들의 순서를 확정(tie-break)하기 위해서다. 없으면 같은 시각 글의 순서가 바뀌고, 커서 조건으로 다음 위치를 정확히 표현할 수 없어 글이 빠지거나 겹친다.</details>

3. 마지막으로 받은 글이 (13:20, 1532)일 때 다음 페이지의 WHERE 조건을 써라.
   <details><summary>답</summary>published_at &lt; '13:20' OR (published_at = '13:20' AND id &lt; 1532) — 최신순(내림차순) 기준.</details>

4. `CursorResponse.of`가 COUNT 쿼리 없이 "다음이 있는지"를 아는 방법은?
   <details><summary>답</summary>size + 1개를 읽어서, size보다 많이 오면 다음이 있다고 본다. 넘친 1개는 버리고 size번째 항목으로 nextCursor를 만든다.</details>

5. 이 프로젝트 API에서 `?page=0`을 보내면 어떻게 되나? Spring Data의 `PageRequest.of(0, ...)`과 어떻게 다른가?
   <details><summary>답</summary>400 VALIDATION_FAILED, fieldErrors에 page. API의 page는 1부터라 0은 잘못된 값이다. Spring Data의 0은 첫 쪽이다. PageQuery.toPageable이 1을 빼서 맞춘다.</details>

6. 커서를 base64 문자열로 주면 보안상 안전해지는가?
   <details><summary>답</summary>아니다. base64는 누구나 풀 수 있는 인코딩이다. 목적은 프론트가 해석·조립하지 않게 하는 것(불투명성)이고, 서버는 받은 커서를 검증해야 한다.</details>

7. 홈 최신 글에 `idx_post_home_feed (status, visibility, published_at DESC, id DESC)`가 잘 맞는 이유를 쿼리와 연결해 설명하라.
   <details><summary>답</summary>WHERE의 같다 조건(status, visibility)이 인덱스 앞쪽 컬럼과 같고, ORDER BY(published_at DESC, id DESC)가 인덱스 뒤쪽 순서와 같다. DB가 정렬 없이 인덱스를 커서 위치부터 읽다가 LIMIT 개수에서 멈출 수 있다.</details>

8. 페이지 번호 방식에서 마지막 쪽을 넘는 `?page=99`의 응답은?
   <details><summary>답</summary>오류가 아니라 content가 빈 배열인 정상 응답(200)이다. totalElements, totalPages는 실제 값.</details>

9. (스텝 4) 블로그 메인 컨트롤러가 `page`, `size`를 `int`가 아니라 `Integer`로 받는 이유는?
   <details><summary>답</summary>안 보낸 값을 null로 받아야 <code>PageQuery.of</code>가 기본값(1쪽, 10개)을 넣을 수 있다. <code>int</code>는 null이 될 수 없어 안 보냈을 때 처리가 어렵다(필수 값이 되거나 0이 들어간다).</details>

10. (스텝 4) 총 25쪽, 지금 15쪽일 때 화면의 페이지 번호와 이전·다음 버튼이 가리키는 쪽은?
   <details><summary>답</summary>번호는 11~20, 이전은 10쪽(이전 묶음의 마지막), 다음은 21쪽(다음 묶음의 첫 쪽)이다(<code>pageGroup(15, 25)</code>).</details>

## 9. 더 읽을거리

- Spring Data JPA Reference — Paging and Sorting, `Page`와 `Slice`의 차이: https://docs.spring.io/spring-data/jpa/reference/
- MySQL 8.4 Reference Manual — "LIMIT Query Optimization", "ORDER BY Optimization", "Descending Indexes", `EXPLAIN` 출력 읽기: https://dev.mysql.com/doc/refman/8.4/en/
- Use The Index, Luke! — "Paging Through Results"(offset과 keyset 비교): https://use-the-index-luke.com/sql/partial-results/fetch-next-page
- 이 저장소: [research.md R-06](../../research.md), [contracts/rest-api.md "목록"](../../contracts/rest-api.md), [spec.md "목록과 페이지"](../../spec.md)
