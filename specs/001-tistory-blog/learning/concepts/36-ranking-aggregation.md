# 36. 집계 쿼리로 순위 매기기: 인기 점수와 태그별 글 수

> 관련 스텝: [스텝 8](../step-08.md) (T063, T054), [스텝 9](../step-09.md) (T064) · 관련 개념: [39-category-hierarchy](./39-category-hierarchy.md), [35-spring-cache-redis](./35-spring-cache-redis.md), [34-view-count](./34-view-count.md), [06-jpa-entity-mapping](./06-jpa-entity-mapping.md), [08-pagination](./08-pagination.md), [16-authorization-visibility](./16-authorization-visibility.md), [31-tags-many-to-many](./31-tags-many-to-many.md)

## 1. 이 문서로 배우는 것

- **집계(aggregation)**: `GROUP BY`와 `COUNT`·`SUM`으로 여러 행을 묶어 숫자 하나로
- 서로 다른 세 테이블(조회 기록, 공감, 댓글)의 활동을 **`UNION ALL`로 이어 붙여** 한 번에 점수 매기기
- "행마다 가중치를 하나씩 붙이고 더한다" = "개수 × 가중치의 합"
- 최근 1시간만 읽기: 시각 칸 인덱스와 **활동에서 출발하는** 쿼리
- 정렬이 흔들리지 않게 하는 **동점 처리**(`ORDER BY score DESC, post_id DESC`)
- 이 쿼리를 JPA가 아니라 **`NamedParameterJdbcTemplate`으로 SQL 그대로** 쓴 이유
- SQL에서 미리 거르는 것과, 자바(Specification)에서 다시 거르는 것을 나눈 기준
- 같은 집계 기법으로 만든 **태그 목록과 글 수**(TAG-03): Criteria API의 조인 + `GROUP BY`
- 가중치를 설정으로 빼기, 집계를 테스트할 데이터 만들기

**먼저 알면 좋은 것**: SQL `SELECT`·`JOIN`·`WHERE`, 인덱스가 무엇인지([08](./08-pagination.md)), 조회 기록 테이블([34](./34-view-count.md)), 가시성 조건 Specification([16](./16-authorization-visibility.md), [06](./06-jpa-entity-mapping.md)), 태그 연결 테이블([31](./31-tags-many-to-many.md)).

## 2. 왜 필요한가

홈 인기 글(HOME-02)의 규칙은 이렇다.

> 인기 점수 = 최근 1시간의 **조회 수 × 1** + **공감 수 × 3** + **댓글 수 × 5**. 공개 글 중 점수 순 상위 10개.

처음 원본 명세는 "조회수 순"이었는데, 지원이 "조회수만이 아니라 공감·댓글에 가중치를 곱해 계산하자"고 바꿨다(research R-12). 조회만 많은 글(제목 낚시)보다 사람들이 반응한 글이 위에 오게 하려는 것이다.

이 점수는 어떤 테이블에도 칸으로 없다. 세 테이블에 흩어진 행을 **세어서 계산**해야 한다.

| 재료 | 테이블 | "최근 1시간" 기준 칸 | 셀 때 조건 |
| --- | --- | --- | --- |
| 조회 | `view_log` | `viewed_at` | 없음(이미 5분 중복은 빼고 기록됨, [34](./34-view-count.md)) |
| 공감 | `post_like` | `created_at` | 없음(공감을 끄면 행이 지워짐) |
| 댓글 | `comment` | `created_at` | 지우지 않았고(`deleted_at IS NULL`) 숨기지 않은(`is_blinded = 0`) 댓글 |

`post.like_count`·`comment_count` 같은 누적 칸은 쓸 수 없다. "최근 1시간" 것만 세야 하기 때문이다. 시각이 있는 행 자체를 세야 한다.

## 3. 기본 개념

### 3.1 `GROUP BY`와 집계 함수

```sql
SELECT post_id, COUNT(*) AS views
FROM view_log
WHERE viewed_at >= '2026-10-09 03:06:00'
GROUP BY post_id;
```

| post_id | views |
| --- | --- |
| 8 | 3 |
| 10 | 1 |

`GROUP BY post_id`는 같은 `post_id`를 가진 행들을 한 묶음으로 만든다. `COUNT(*)`는 묶음 안의 행 수, `SUM(칸)`은 묶음 안 값의 합이다. 묶은 뒤에는 묶음 하나가 결과 한 줄이 된다.

### 3.2 세 테이블을 하나로: `UNION ALL`

조회·공감·댓글을 따로 세서 자바에서 더할 수도 있다. 하지만 그러면 쿼리가 셋이고, 각 쿼리의 결과를 모두 가져와야 상위 10개를 고를 수 있다. 한 쿼리로 하는 방법이 있다.

**`UNION ALL`**은 여러 `SELECT`의 결과를 **위아래로 이어 붙인다**. 칸 수와 종류가 같아야 한다. (`UNION`은 같은 줄을 하나로 합치므로 여기서는 쓰면 안 된다. 같은 글에 조회가 두 번이면 `(8, 1)` 줄이 두 개여야 한다.)

핵심 요령은 **행마다 그 행의 가중치를 붙이는 것**이다.

```sql
SELECT post_id, 1 AS weight FROM view_log  WHERE viewed_at  >= :since   -- 조회 한 행 = 1점
UNION ALL
SELECT post_id, 3          FROM post_like WHERE created_at >= :since   -- 공감 한 행 = 3점
UNION ALL
SELECT post_id, 5          FROM comment   WHERE created_at >= :since AND deleted_at IS NULL AND is_blinded = 0  -- 댓글 = 5점
```

결과(활동 행 목록):

| post_id | weight |
| --- | --- |
| 8 | 1 |
| 8 | 1 |
| 8 | 3 |
| 10 | 1 |
| 10 | 5 |

이것을 `post_id`로 묶어 `SUM(weight)`을 하면, 글 8은 1 + 1 + 3 = 5, 글 10은 1 + 5 = 6이다. 이것이 정확히 "조회 수 × 1 + 공감 수 × 3 + 댓글 수 × 5"다. 조회가 n개면 1이 n번 더해지니 n × 1이기 때문이다.

### 3.3 활동에서 출발하기와 인덱스

반대 방향으로도 짤 수 있다. "모든 공개 글에 대해, 각각 최근 1시간 조회 수를 세는 서브쿼리 + 공감 수 서브쿼리 + 댓글 수 서브쿼리". 그러면 글이 10만 개면 10만 번 × 3개의 서브쿼리다. 대부분의 글은 최근 1시간에 아무 활동이 없는데도.

이 프로젝트는 **최근 활동 행에서 출발**한다. ERD에는 이 쿼리를 위한 인덱스가 처음부터 있다.

```sql
CREATE INDEX idx_view_log_viewed_at ON view_log (viewed_at ASC);
CREATE INDEX idx_post_like_created_at ON post_like (created_at ASC);
CREATE INDEX idx_comment_created_at ON comment (created_at ASC);
```

`viewed_at >= :since` 조건은 이 인덱스로 "최근 1시간" 구간만 읽는다. 1년치 기록이 쌓여도(실제로는 7일 뒤 지움) 읽는 양은 최근 1시간 활동량에 비례한다.

### 3.4 동점 처리: 정렬을 결정적으로

점수가 같은 글이 여러 개면 DB는 그 사이의 순서를 **보장하지 않는다**. 같은 쿼리를 두 번 돌려도 순서가 바뀔 수 있다. 랭킹이 새로고침마다 흔들리면 이상하고, 상위 N개를 자를 때 경계에 걸친 글이 들어갔다 빠졌다 한다. 페이지 나누기에서 배운 "정렬 안정성"과 같은 문제다([08](./08-pagination.md)).

그래서 마지막에 **유일한 칸**을 하나 더 둔다.

```sql
ORDER BY score DESC, post_id DESC
```

점수가 같으면 `post_id`가 큰 글(나중에 쓴 글)이 위다. `post_id`는 겹치지 않으므로 순서가 하나로 정해진다.

### 3.5 JPA 대신 SQL을 그대로 쓴 이유

지금까지 이 프로젝트는 대부분 JPA(엔티티, Specification, 파생 쿼리)를 썼다. 이 쿼리는 다르다.

- **엔티티 하나가 아니다.** 세 테이블을 이어 붙인 가상의 표를 다시 묶는다.
- **`UNION ALL`을 FROM 안에 넣는다.** JPQL·Criteria API는 FROM 절의 서브쿼리와 UNION을 쓰기 어렵다(Hibernate 6부터 일부 되지만 표준 JPA는 아니다).
- **결과가 엔티티가 아니라 숫자 두 개**(글 번호, 점수)다.

이럴 때는 SQL을 그대로 쓰는 것이 읽기 쉽다. Spring의 `NamedParameterJdbcTemplate`은 `:since` 같은 **이름 붙은 자리**에 값을 넣어 실행하고, 결과의 각 줄을 함수로 객체로 바꿔 준다. 값은 바인딩 변수로 가서 SQL 주입 걱정이 없다.

`NamedParameterJdbcTemplate`은 `spring-boot-starter-data-jpa`(JDBC 포함)가 있으면 Spring Boot가 빈으로 만들어 둔다. 따로 설정하지 않고 주입받으면 된다.

### 3.6 어디서 거르나: SQL과 Specification

"공개 글만"이라는 조건을 어디에 둘까?

| 조건 | 어디서 | 이유 |
| --- | --- | --- |
| 글이 발행됨, 공개, 삭제 안 됨, 숨김 안 됨 | **SQL에서 미리** (`JOIN post`) | 비공개 글에 활동이 많으면 상위 100개 후보 자리를 차지해 공개 글이 밀려난다 |
| 블로그 삭제·이용 제한, 주인 정지 등 **전체** 가시성 | **자바에서 다시** (`PostSpecifications.visibleTo`) | 가시성 규칙은 한 곳(`PostSpecifications`)에만 둔다는 원칙([16](./16-authorization-visibility.md)). 캐시된 5분 동안 바뀐 것도 여기서 걸러진다([35](./35-spring-cache-redis.md)) |

SQL에 넣은 것은 "후보를 고를 때 자리 낭비를 줄이는" 용도고, **진짜 판단은 자바의 Specification**이다. SQL 쪽 조건이 조금 덜 엄격해도(예: 이용 제한 블로그를 SQL에서 못 거름) 결과는 맞다.

## 4. 동작 원리

### 4.1 전체 쿼리

```sql
SELECT activity.post_id, SUM(activity.weight) AS score
FROM (
    SELECT post_id, :viewWeight AS weight FROM view_log WHERE viewed_at >= :since
    UNION ALL
    SELECT post_id, :likeWeight FROM post_like WHERE created_at >= :since
    UNION ALL
    SELECT post_id, :commentWeight FROM comment
    WHERE created_at >= :since AND deleted_at IS NULL AND is_blinded = 0
) activity
JOIN post p ON p.id = activity.post_id
WHERE p.status = 'PUBLISHED' AND p.visibility = 'PUBLIC' AND p.deleted_at IS NULL AND p.is_blinded = 0
GROUP BY activity.post_id
ORDER BY score DESC, activity.post_id DESC
LIMIT :limit
```

DB가 하는 일을 순서대로:

1. **FROM 안의 서브쿼리**: 세 테이블에서 `since` 이후 행을 인덱스로 찾아 `(post_id, weight)` 줄로 만들고 이어 붙인다. 이 임시 표에 `activity`라는 이름을 붙인다(FROM 안의 서브쿼리에는 이름이 꼭 있어야 한다).
2. **JOIN post**: 활동마다 글을 붙인다. 기본 키로 찾으니 빠르다.
3. **WHERE**: 공개·발행·삭제 안 됨·숨김 안 됨이 아닌 글의 활동은 버린다.
4. **GROUP BY + SUM**: 글별로 점수를 더한다.
5. **ORDER BY + LIMIT**: 점수 높은 순, 동점이면 id 큰 순으로 100개.

가중치 자리 `:viewWeight` 등은 설정값(1, 3, 5)이 들어간다. 가중치가 SQL 글자가 아니라 **값**이라, 설정을 바꿔도 SQL은 그대로다.

### 4.2 예로 계산해 보기

최근 1시간 활동이 이렇다고 하자.

| 글 | 조회 | 공감 | 댓글(살아 있는) | 점수 |
| --- | --- | --- | --- | --- |
| A | 400 | 0 | 0 | 400 |
| B | 300 | 20 | 10 | 300 + 60 + 50 = **410** |
| C (비공개) | 1000 | 0 | 0 | SQL에서 빠짐 |
| D | 0 | 0 | 200개, 모두 지운 댓글 | 0 → 활동 행이 없어 결과에 없음 |

결과: B(410), A(400). 조회는 A가 더 많지만 B가 위다. spec US5 시나리오 6 "조회만 많은 글보다 공감·댓글이 함께 많은 글이 위에 온다". 테스트가 바로 이 숫자로 확인한다(5.4).

### 4.3 활동이 없는 글

활동 행이 하나도 없는 글은 `activity`에 나타나지 않으므로 결과에도 없다. 그래서 최근 1시간에 아무 일도 없으면 인기 글은 **빈 목록**이다. 화면은 "최근 1시간 동안 읽힌 글이 없습니다"를 보여 준다. (주제별 글 HOME-03은 "6개가 안 되면 최신 글로 채운다"는 규칙이 따로 있다. 스텝 9.)

## 5. 이 프로젝트에서는

### 5.1 `home/domain/PopularScoreRepository.java`

```java
@Repository
public class PopularScoreRepository {

    private static final String SQL = """
            SELECT activity.post_id, SUM(activity.weight) AS score
            FROM (
            ...
            LIMIT :limit
            """;

    private final NamedParameterJdbcTemplate jdbcTemplate;

    public PopularScoreRepository(NamedParameterJdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    /** since 이후 활동으로 점수가 높은 글 limit개. 점수가 같으면 나중에 쓴 글(id가 큰 글)이 위다. 활동이 없는 글은 없다. */
    public List<PostScore> topScores(LocalDateTime since, int viewWeight, int likeWeight, int commentWeight,
                                     int limit) {
        MapSqlParameterSource params = new MapSqlParameterSource()
                .addValue("since", since)
                .addValue("viewWeight", viewWeight)
                .addValue("likeWeight", likeWeight)
                .addValue("commentWeight", commentWeight)
                .addValue("limit", limit);
        return jdbcTemplate.query(SQL, params,
                (row, rowNum) -> new PostScore(row.getLong("post_id"), row.getLong("score")));
    }
}
```

- `"""` … `"""`: 자바 텍스트 블록. 여러 줄 SQL을 그대로 쓸 수 있다.
- `@Repository`: 인터페이스(`JpaRepository`)가 아니라 **직접 만든 클래스**도 저장소 역할이면 이 어노테이션을 붙인다. DB 예외를 스프링 예외(`DataAccessException`)로 바꿔 주는 대상이 된다. 계층 규칙대로 `home/domain/`에 두었다(CLAUDE.md, [24](./24-layered-architecture-dto.md)).
- `MapSqlParameterSource`: 이름 → 값. `LocalDateTime`도 그대로 넣으면 드라이버가 DATETIME으로 보낸다.
- `jdbcTemplate.query(SQL, params, rowMapper)`: 결과의 줄마다 람다를 불러 `PostScore`로 만든다. `row`는 JDBC의 `ResultSet`이고, `getLong("score")`는 `SUM`의 결과(MySQL에서는 DECIMAL)를 `long`으로 읽는다.

부르는 쪽은 [35](./35-spring-cache-redis.md)의 `PopularRanking.snapshot()`이다. `since = 지금 − 1시간(window)`, 가중치는 `PopularProperties`, `limit`은 후보 수 100.

### 5.2 같은 기법으로: 태그 목록과 글 수 (T054, TAG-03)

사이드바와 `GET /api/tags`의 태그 목록도 집계다. "태그마다 그 태그가 달린, **보는 사람이 볼 수 있는** 글 수". 이번에는 JPA Criteria API로 만들었다. 가시성 조건(`listedIn`)이 이미 Specification이라 그대로 붙일 수 있기 때문이다. 카테고리별 글 수(`countByCategory`, 스텝 4)와 같은 모양이다.

`post/domain/PostCountRepositoryImpl.java`:

```java
@Override
public Map<Long, Long> countByTag(Specification<Post> condition) {
    CriteriaBuilder cb = entityManager.getCriteriaBuilder();
    CriteriaQuery<Tuple> query = cb.createTupleQuery();
    Root<Post> post = query.from(Post.class);
    Join<Post, Tag> tag = post.join("tags");
    query.multiselect(tag.get("id"), cb.count(post))
            .where(condition.toPredicate(post, query, cb))
            .groupBy(tag.get("id"));

    Map<Long, Long> counts = new HashMap<>();
    for (Tuple row : entityManager.createQuery(query).getResultList()) {
        counts.put(row.get(0, Long.class), row.get(1, Long.class));
    }
    return counts;
}
```

만들어지는 SQL은 대략 이렇다.

```sql
SELECT pt.tag_id, COUNT(p.id)
FROM post p
JOIN post_tag pt ON pt.post_id = p.id
JOIN blog b ON ...                            -- 가시성 조건이 붙이는 조인
WHERE p.blog_id = ? AND (가시성 조건)
GROUP BY pt.tag_id
```

- `post.join("tags")`: `Post.tags`(`@ManyToMany`)를 따라 `post_tag`로 조인한다([31](./31-tags-many-to-many.md)). 글 하나에 태그가 셋이면 세 줄이 되고, 태그별로 묶으면 각 태그에 1씩 더해진다.
- `createTupleQuery()` + `multiselect(...)`: 엔티티가 아니라 칸 두 개(태그 id, 개수)를 꺼낸다. `Tuple`은 "여러 값 한 줄".
- `condition.toPredicate(post, query, cb)`: 넘겨받은 Specification을 이 쿼리의 WHERE로 바꾼다. 가시성 판단을 다시 짜지 않고 **재사용**한다.
- 결과는 `태그 id → 글 수` 지도. 글이 하나도 없는 태그는 조인에서 아예 안 나와 지도에 없다.

`tag/application/TagListService.java`:

```java
@Transactional(readOnly = true)
public List<TagCount> tags(Blog blog, Long viewerId) {
    Map<Long, Long> counts = postRepository.countByTag(
            PostSpecifications.listedIn(blog, viewerId, LocalDateTime.now(clock)));
    Comparator<TagCount> byName = Comparator.comparing(TagCount::name, TagNames.nameComparator());
    return tagRepository.findByBlogId(blog.getId()).stream()
            .filter(tag -> counts.containsKey(tag.getId()))
            .map(tag -> new TagCount(tag.getId(), tag.getName(), counts.get(tag.getId())))
            .sorted(Comparator.comparingLong(TagCount::postCount).reversed().thenComparing(byName))
            .toList();
}
```

- `listedIn(blog, viewerId, now)`: 블로그 화면 목록과 같은 조건. 주인은 비공개·숨긴 글을 포함한 발행 글 전부, 다른 사람은 볼 수 있는 글만([16](./16-authorization-visibility.md)). 그래서 같은 블로그라도 **보는 사람마다 글 수가 다르다**.
- `filter(counts.containsKey(...))`: 볼 수 있는 글이 **0개인 태그는 뺀다**. 비공개 글에만 단 태그 `#이직준비`가 다른 사람의 사이드바에 "이직준비 0"으로 보이면, 숨긴 글의 내용을 태그 이름으로 흘리는 것이다(헌법 원칙 II). 글이 다 지워진 태그도 이렇게 자연스럽게 사라진다(스텝 7에서 미뤄 둔 "글이 없는 태그" 문제, [31](./31-tags-many-to-many.md) 4.2).
- 정렬: 글 수 많은 순(`reversed()`), 같으면 이름순. 이름 비교는 태그 이름 규칙과 같은 `Collator`(대소문자·악센트 무시, [31](./31-tags-many-to-many.md) 3.5)라 `Spring`과 `apple`이 대문자 때문에 앞뒤가 바뀌지 않는다.
- 태그 행(`findByBlogId`)과 개수(`countByTag`)를 **쿼리 두 번**으로 가져와 자바에서 합친다. 태그 이름을 GROUP BY 쿼리에 같이 넣을 수도 있지만, 블로그 하나의 태그는 많아야 수백 개라 이쪽이 읽기 쉽다.

`SidebarService`는 이것을 불러 사이드바의 `TAG` 모듈로 넣는다. 모듈 순서는 명세(BLOG-04)대로 프로필, 카테고리, **태그**, 최근 글, 최근 댓글이다.

```java
return new Sidebar(blog, categoryTreeService.tree(blog, viewerId), tagListService.tags(blog, viewerId),
        recentPosts(blog, viewerId, now), recentComments(blog, viewerId, now));
```

화면 `components/Sidebar.tsx`는 목업 blog-main처럼 `spring 14` 모양의 칩을 그리고, 누르면 `/tag/{이름}` 목록으로 간다(이름은 `encodeURIComponent`).

### 5.3 설정으로 뺀 가중치

`app.popular.view-weight` 등(application.yml). 가중치를 바꾸고 서버를 다시 띄우면, 다음 캐시 계산부터 새 가중치가 쓰인다. 코드를 고칠 일이 없다([35](./35-spring-cache-redis.md) 5.7).

### 5.4 테스트 데이터를 SQL로 만들기

인기 점수 테스트(`HomePopularIntegrationTest`)는 조회 수백 개를 API로 만들지 않고 **SQL로 바로** 넣는다.

```java
private void views(Post post, int count, LocalDateTime at) {
    List<Object[]> rows = new ArrayList<>();
    for (int i = 0; i < count; i++) {
        rows.add(new Object[]{post.getId(), "t:" + UUID.randomUUID(), at});
    }
    jdbcTemplate.batchUpdate("INSERT INTO view_log (post_id, viewer_key, viewed_at) VALUES (?, ?, ?)", rows);
}
```

- `batchUpdate`: 같은 INSERT를 값만 바꿔 여러 번 묶어 보낸다.
- `at`을 인자로 받아 **2시간 전 활동**도 만든다. 그것이 빠지는지 확인한다.
- 공감은 회원마다 하나(UNIQUE)라 회원을 공감 수만큼 만들고, 댓글은 `deleted_at`을 채운 "지운 댓글"도 만든다.
- 처음엔 조회를 수천 개 넣었더니 테스트가 34초 걸렸다. 다른 테스트가 남기는 활동(공감 몇 개)보다 충분히 크면 되므로 수백 개로 줄여 15초가 됐다.

테스트 DB를 여러 테스트가 같이 쓰므로, 다른 테스트가 남긴 활동 위에 내 글이 오도록 점수를 넉넉히 줬다. 그리고 "정확히 몇 등"보다 "B가 A보다 위", "빠져야 할 글이 없다"를 본다.

태그 목록 테스트(`TagIntegrationTest.tagListCountsOnlyPostsTheViewerCanSeeMostUsedFirst`)는 공개 글 둘(`spring, jpa`, `spring, alpha`), 비공개 글(`spring, secret`), 숨긴 글(`blind-only`)을 만들고:

| 보는 사람 | 결과 |
| --- | --- |
| 비회원 | `spring 2, alpha 1, jpa 1` (secret·blind-only 없음, 같은 수는 이름순) |
| 주인 | `spring 3, alpha 1, blind-only 1, jpa 1, secret 1` |

### 5.5 (스텝 9) 같은 SQL에 조건 하나 더하기: 주제별 순위

주제별 글(HOME-03)도 "같은 인기 점수"라, 5.1의 SQL에 **주제 조건만** 더해 다시 쓴다. SQL을 둘로 복사하지 않고, 글 조건 끝에 자리(`%s`)를 하나 두고 두 가지로 채웠다.

```java
private static final String SQL = """
        ...
        WHERE p.status = 'PUBLISHED' AND p.visibility = 'PUBLIC' AND p.deleted_at IS NULL AND p.is_blinded = 0%s
        ...
        """;

private static final String ALL = SQL.formatted("");
private static final String BY_TOPIC = SQL.formatted(" AND p.topic = :topic");
```

- `formatted`로 **우리가 정한 글자**(SQL 조각)만 넣는다. 사용자 값(주제)은 여전히 `:topic` 바인딩 변수로 간다. 사용자 값을 `formatted`로 SQL에 넣으면 SQL 주입이다.
- 두 SQL은 클래스가 처음 쓰일 때 한 번 만들어진다(`static final`).
- `topScoresInTopic(topic, ...)`이 `BY_TOPIC`을 쓴다. 후보는 30개(6개만 보이므로), 캐시 키는 주제마다 다르다([35](./35-spring-cache-redis.md) 5.9).
- 활동이 없어 6개가 안 되면 최신 글로 채운다([39](./39-category-hierarchy.md) 5.6).

**테스트끼리의 간섭**: 주제별 글 테스트가 "다른 주제·주제 없는 글은 빠진다"를 보려고 활동이 많은 글을 만들자, 홈 인기 글 테스트가 기대하던 "내 글이 1·2위"가 깨졌다(테스트끼리 DB를 같이 쓰므로). 인기 글 테스트를 "몇 위"가 아니라 **"A가 B보다 앞", "빠질 글이 없다"**로 바꿨다. 또 채우는 글을 먼 미래 시각에 두었더니 홈 최신 글 테스트의 미래 글과 섞여 그 테스트가 깨져서, 현재 시각 근처로 옮겼다([05](./05-spring-testing.md) 5.7).

## 6. 자주 하는 실수와 함정

- **`UNION`을 쓴다.** 같은 줄을 합쳐 버려 같은 글의 조회 두 번이 한 번이 된다. 이어 붙이기만 하려면 `UNION ALL`.
- **FROM 안 서브쿼리에 이름을 안 붙인다.** MySQL은 `Every derived table must have its own alias` 오류.
- **동점 정렬을 안 정한다.** 새로고침마다 순위가 흔들리고, 상위 N개 경계의 글이 들어갔다 빠졌다 한다. 유일한 칸을 마지막 정렬 기준으로.
- **누적 칸으로 "최근" 점수를 계산한다.** `like_count`는 처음부터의 합계라 최근 1시간 것을 알 수 없다. 시각이 있는 행을 센다.
- **지운·숨긴 댓글을 센다.** 스팸 댓글을 지워도 순위가 그대로다. 조건을 빠뜨리지 않는다.
- **모든 글에서 출발해 서브쿼리를 붙인다.** 글이 많아지면 활동이 없는 글까지 매번 훑는다. 최근 활동에서 출발하고 시각 인덱스를 쓴다.
- **가시성을 SQL에만 두고 자바 규칙과 따로 관리한다.** 블로그 이용 제한 같은 규칙이 바뀌면 한쪽만 고쳐진다. 최종 판단은 `PostSpecifications` 한 곳.
- **태그 글 수를 모든 글 기준으로 센다.** 비공개 글의 태그가 다른 사람에게 보이고, 글 수로 비공개 글이 있다는 것까지 드러난다. 보는 사람 기준으로 센다.
- **글이 0개인 태그를 "0"으로 보여 준다.** 위와 같은 이유로 뺀다.
- **집계 쿼리를 요청마다 돌린다.** 홈처럼 자주 열리는 곳이면 캐시한다([35](./35-spring-cache-redis.md)).

## 7. 직접 해 보기

### 7.1 MySQL에서 직접 점수 매기기

```bash
docker exec -it blog-mysql mysql -ublog -pblog blog
```

```sql
-- 조회 기록이 있는 글별 개수(최근 1시간)
SELECT post_id, COUNT(*) FROM view_log WHERE viewed_at >= NOW() - INTERVAL 1 HOUR GROUP BY post_id;

-- UNION ALL만 먼저 보기 (묶기 전 활동 줄)
SELECT post_id, 1 AS w FROM view_log WHERE viewed_at >= NOW() - INTERVAL 1 HOUR
UNION ALL SELECT post_id, 3 FROM post_like WHERE created_at >= NOW() - INTERVAL 1 HOUR
UNION ALL SELECT post_id, 5 FROM comment WHERE created_at >= NOW() - INTERVAL 1 HOUR AND deleted_at IS NULL AND is_blinded = 0;

-- 전체 점수 (5.1의 SQL에서 :자리를 값으로)
SELECT a.post_id, SUM(a.w) AS score FROM ( ...위 UNION ALL... ) a
JOIN post p ON p.id = a.post_id
WHERE p.status = 'PUBLISHED' AND p.visibility = 'PUBLIC' AND p.deleted_at IS NULL AND p.is_blinded = 0
GROUP BY a.post_id ORDER BY score DESC, a.post_id DESC LIMIT 10;
```

`UNION ALL`을 `UNION`으로 바꿔 점수가 어떻게 줄어드는지 본다. (개발 DB의 MySQL 컨테이너 시간대와 앱의 시간대가 다르면 `NOW()`가 몇 시간 어긋날 수 있다. 그럴 땐 시각을 직접 적는다.)

### 7.2 인덱스를 타는지

```sql
EXPLAIN SELECT post_id FROM view_log WHERE viewed_at >= NOW() - INTERVAL 1 HOUR;
```

`key`에 `idx_view_log_viewed_at`, `type`에 `range`가 보이면 구간만 읽는 것이다. 데이터가 아주 적으면 MySQL이 인덱스 대신 전체를 읽는 게 낫다고 판단할 수도 있다.

### 7.3 가중치 바꿔 보기

`application.yml`의 `like-weight`를 `100`으로 바꾸고 서버를 다시 띄운다. 캐시를 지우고(`redis-cli del 'blog:popularPosts::home'`) 홈 인기 글 순서가 공감 많은 글 위주로 바뀌는지 본다. 끝나면 되돌린다.

### 7.4 태그 목록이 보는 사람마다 다른지

```bash
curl -s -H "Host: {주소}.blog.test" localhost:8080/api/tags            # 비회원
curl -s -b jarOwner.txt -H "Host: {주소}.blog.test" localhost:8080/api/tags   # 주인
```

주인으로 비공개 글에만 새 태그를 달아 발행하고, 두 결과를 비교한다.

### 7.5 테스트

```bash
./mvnw test -Dtest='HomePopularIntegrationTest,TagIntegrationTest,SidebarIntegrationTest'
```

## 8. 확인 문제

1. 인기 점수를 `post.like_count`, `comment_count` 같은 누적 칸으로 계산할 수 없는 이유는?
<details><summary>답</summary>누적 칸은 처음부터의 합계라 "최근 1시간" 것만 골라낼 수 없다. 시각 칸이 있는 행(view_log.viewed_at, post_like.created_at, comment.created_at)을 세야 한다.</details>

2. 행마다 가중치를 붙여 `UNION ALL`로 이어 붙인 뒤 `SUM`하면 왜 "개수 × 가중치의 합"이 되나?
<details><summary>답</summary>조회가 n개면 가중치 1인 줄이 n개라 합이 n × 1, 공감 m개면 3이 m번 더해져 m × 3. 글별로 묶어 더하면 각 재료의 개수 × 가중치를 모두 더한 값이 된다.</details>

3. `UNION ALL` 대신 `UNION`을 쓰면 무엇이 틀리나?
<details><summary>답</summary>UNION은 같은 줄을 하나로 합친다. 같은 글의 조회 두 번이 (글, 1) 한 줄이 되어 점수가 줄어든다.</details>

4. 모든 글에서 출발하지 않고 최근 활동에서 출발하는 이유와, 그것을 빠르게 하는 장치는?
<details><summary>답</summary>대부분의 글은 최근 1시간에 활동이 없으므로 모든 글을 훑으면 낭비다. 시각 칸 인덱스(idx_view_log_viewed_at 등)로 최근 구간만 읽는다.</details>

5. `ORDER BY score DESC` 뒤에 `post_id DESC`를 붙인 이유는?
<details><summary>답</summary>점수가 같으면 DB가 순서를 보장하지 않아 순위가 흔들리고 상위 N개 경계가 바뀐다. 유일한 칸을 마지막 기준으로 두어 순서를 하나로 정한다.</details>

6. 이 쿼리를 JPA가 아니라 `NamedParameterJdbcTemplate`으로 쓴 이유는?
<details><summary>답</summary>엔티티 하나가 아니라 세 테이블을 FROM 안 서브쿼리에서 UNION ALL로 이어 붙이는 쿼리라 JPQL·Criteria로 쓰기 어렵고, 결과도 엔티티가 아니라 숫자 두 개다. SQL 그대로가 읽기 쉽다. 이름 붙은 자리로 값을 바인딩해 SQL 주입도 없다.</details>

7. SQL에서 공개·발행 조건을 미리 거르는데, 자바에서 `visibleTo`로 다시 거르는 이유는?
<details><summary>답</summary>SQL 조건은 비공개 글이 후보 자리를 차지하지 않게 하려는 것이고, 최종 가시성(블로그 삭제·이용 제한, 주인 정지 등)은 규칙을 한 곳에 둔 PostSpecifications로 판단한다. 캐시된 5분 동안 바뀐 상태도 여기서 걸러진다.</details>

8. 태그 목록에서 볼 수 있는 글이 0개인 태그를 빼는 이유는?
<details><summary>답</summary>비공개·숨긴 글에만 단 태그 이름이 다른 사람에게 보이면 숨긴 글의 내용이 새어 나간다(헌법 원칙 II). 글이 모두 지워진 태그도 함께 사라진다.</details>

9. 같은 블로그의 태그 글 수가 보는 사람마다 다른 이유는?
<details><summary>답</summary>글 수를 블로그 화면 목록과 같은 조건 listedIn으로 세기 때문이다. 주인에게는 비공개·숨긴 글도 포함되고, 다른 사람에게는 볼 수 있는 글만 센다.</details>

10. `countByTag`가 `Tuple`과 `multiselect`를 쓰는 이유는?
<details><summary>답</summary>엔티티가 아니라 태그 id와 개수, 칸 두 개를 한 줄로 꺼내기 위해서다. Tuple은 여러 값 한 줄을 담는 JPA 타입이다.</details>

## 9. 더 읽을거리

- MySQL 8.4 레퍼런스, "UNION Clause", "Derived Tables", "Aggregate Functions"(`SUM`, `COUNT`), "GROUP BY Handling"
- MySQL 8.4 레퍼런스, "EXPLAIN Output Format"(`type: range`), "Range Optimization"
- Spring Framework 레퍼런스, "Data Access with JDBC" → `NamedParameterJdbcTemplate`, `RowMapper`
- Jakarta Persistence 명세, Criteria API(`Tuple`, `multiselect`, `groupBy`)
- 시간에 따라 점수가 줄어드는 랭킹(Hacker News·Reddit 공식): 오래된 활동에 낮은 가중치를 주는 방법
- 실시간 랭킹을 Redis Sorted Set으로 유지하는 방법(`ZINCRBY`)과, 이 프로젝트처럼 주기적으로 다시 계산하는 방법의 비교
