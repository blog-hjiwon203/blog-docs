# 35. 캐시: Spring Cache와 Redis로 인기 글 5분 동안 기억하기

> 관련 스텝: [스텝 8](../step-08.md) (T063), [스텝 9](../step-09.md) (T064) · 관련 개념: [39-category-hierarchy](./39-category-hierarchy.md), [17-idempotency-redis](./17-idempotency-redis.md), [01-spring-boot-basics](./01-spring-boot-basics.md), [02-configuration-profiles](./02-configuration-profiles.md), [36-ranking-aggregation](./36-ranking-aggregation.md), [16-authorization-visibility](./16-authorization-visibility.md), [05-spring-testing](./05-spring-testing.md)

## 1. 이 문서로 배우는 것

- **캐시**란 무엇이고, 언제 쓰나: 비싼 계산 결과를 잠깐 기억했다가 다시 쓰기
- 캐시의 대가: **오래된 값**(stale)을 보여 줄 수 있다는 것, 그리고 그것을 줄이는 방법
- TTL(수명)로 저절로 갱신하기: "5분마다 갱신"을 스케줄러 없이 만드는 법
- Spring의 **캐시 추상화**: `@EnableCaching`, `@Cacheable`, `CacheManager`, 캐시 이름과 키
- `@Cacheable`이 **프록시**로 동작한다는 것과, 그래서 같은 클래스 안에서 부르면 캐시가 안 되는 함정
- Redis를 캐시 저장소로 쓸 때: 키 모양(`blog:popularPosts::home`), 값 직렬화(Java 직렬화, `Serializable`), `spring.cache.redis.*` 설정
- `sync = true`: 캐시가 빈 순간 여러 요청이 한꺼번에 계산하는 것(캐시 쇄도) 막기
- **무엇을 캐시에 넣을지**: 글 내용이 아니라 글 번호와 점수만 넣고, 가시성은 읽을 때마다 다시 확인한 이유
- 테스트에서 캐시 비우기

**먼저 알면 좋은 것**: Redis 기초와 TTL([17](./17-idempotency-redis.md) 3.5), 빈과 의존성 주입([01](./01-spring-boot-basics.md)), 설정 파일([02](./02-configuration-profiles.md)), 인기 점수를 어떻게 계산하는지([36](./36-ranking-aggregation.md)).

## 2. 왜 필요한가

홈 화면의 인기 글(HOME-02)은 "최근 1시간 동안의 조회×1 + 공감×3 + 댓글×5" 순 상위 10개다. 이 점수를 구하려면 최근 1시간의 조회 기록·공감·댓글을 모두 모아 글별로 더하고 정렬해야 한다([36](./36-ranking-aggregation.md)). 홈은 서비스에서 가장 많이 열리는 화면이다. 방문자 한 명이 올 때마다 이 집계를 돌리면 DB가 같은 일을 수없이 반복한다.

그런데 명세는 처음부터 "**5분마다 갱신**"이라고 정했다(spec 7.6, HOME-02). 순위가 5분 동안 같아도 된다는 뜻이다. 그렇다면 한 번 계산한 결과를 5분 동안 **기억해 두고** 그대로 주면 된다. 그것이 캐시다.

| | 캐시 없음 | 5분 캐시 |
| --- | --- | --- |
| 1분에 홈 1000번 | 집계 1000번 | 집계 0.2번(5분에 1번) |
| 순위의 신선도 | 늘 지금 | 최대 5분 전 |

## 3. 기본 개념

### 3.1 캐시란

**캐시(cache)**: 가져오기 비싼 데이터를 더 빠른 곳에 잠깐 두고, 다음에 같은 것을 원하면 거기서 바로 주는 것. CPU 캐시, 브라우저 캐시(`/uploads` 이미지의 `Cache-Control`, [30](./30-image-upload.md)), DNS 캐시가 모두 같은 생각이다.

| 낱말 | 뜻 |
| --- | --- |
| 적중(hit) | 캐시에 값이 있어 바로 줌 |
| 실패(miss) | 캐시에 없어 원래 방법(DB 집계)으로 구하고, 그 값을 캐시에 넣음 |
| TTL(Time To Live) | 값의 수명. 지나면 지워져 다음 요청은 실패 → 새로 계산 |
| 무효화(eviction) | 수명 전에 일부러 지우기 |
| 오래된 값(stale) | 원본은 바뀌었는데 캐시에 남은 옛 값 |

이 프로젝트처럼 "필요할 때 찾아보고, 없으면 구해서 넣는" 방식을 **cache-aside**(또는 lazy loading)라 한다.

### 3.2 캐시의 대가: 오래된 값

캐시를 쓰면 원본이 바뀌어도 수명 동안 옛 값이 나간다. 인기 글 순위가 5분 늦게 바뀌는 것은 명세가 허락한 것이라 괜찮다. 하지만 이런 경우는 다르다.

> 5시 00분에 순위를 계산해 캐시했다. 5시 02분에 2위 글의 주인이 그 글을 **비공개**로 바꿨다. 5시 03분에 홈을 연 사람에게 그 글이 보여도 될까?

안 된다. 헌법 원칙 II는 "볼 수 없는 글은 모든 목록에서 빠진다"이다([16](./16-authorization-visibility.md)). 5분이라도 비공개 글의 제목이 홈에 걸리면 안 된다.

이 프로젝트의 답은 **캐시에 넣는 것을 줄이는 것**이다(5.4).

- 캐시에는 **순위(글 번호와 점수)**만 둔다. 이것은 5분 늦어도 된다.
- 제목·요약·블로그 이름 같은 **글 내용**과 **볼 수 있는지**는 요청마다 DB에서 새로 읽는다. 글 번호 10개로 찾는 가벼운 쿼리라 부담이 없다.

### 3.3 TTL로 "5분마다 갱신"

"5분마다 갱신"을 만드는 방법은 두 가지다.

| 방법 | 동작 | 장단점 |
| --- | --- | --- |
| **TTL 캐시** (이 스텝) | 값에 5분 수명을 준다. 수명이 끝난 뒤 처음 온 요청이 다시 계산 | 간단. 아무도 안 오면 계산도 안 함. 수명이 끝난 직후 첫 요청이 계산을 기다린다 |
| 스케줄러 | `@Scheduled`로 5분마다 미리 계산해 저장 | 요청은 늘 빠름. 계산 시각이 정확히 5분 간격. 서버가 여러 대면 누가 계산할지 정해야 함 |

명세(research R-13)는 나중에 랭킹 전체보기(HOME-05)를 만들 때 스케줄러가 상위 100개 스냅숏을 만드는 방식으로 바꾸기로 했다(작업 T078, 백로그). 이 스텝은 작업 목록(T063)대로 `@Cacheable` + 5분 TTL이다.

### 3.4 Spring 캐시 추상화

Spring은 캐시를 **어노테이션 하나로** 쓸 수 있게 해 준다. 저장소가 무엇이든(자바 메모리, Redis, Caffeine…) 코드는 같고 설정만 다르다. 이것을 **캐시 추상화**라 한다.

| 구성 요소 | 하는 일 |
| --- | --- |
| `@EnableCaching` | 캐시 어노테이션을 켠다. 이 프로젝트는 `global/config/CacheConfig` |
| `CacheManager` | 이름으로 캐시를 꺼내 주는 관리자. Redis 스타터가 있고 `spring.cache.type: redis`면 `RedisCacheManager` |
| `Cache` | 이름 하나짜리 키-값 저장소(예: `popularPosts`) |
| `@Cacheable(cacheNames, key)` | "이 메서드 결과를 이 캐시에 이 키로 기억해라". 적중이면 **메서드 본문을 실행하지 않는다** |
| `@CacheEvict` | 캐시에서 지운다(이 스텝에서는 안 씀) |
| `@CachePut` | 늘 실행하고 결과로 캐시를 덮어쓴다(안 씀) |

키를 정하지 않으면 Spring이 메서드 인자로 키를 만든다. 인자가 없는 메서드라 이 프로젝트는 고정 키 `'home'`을 줬다. `key` 값은 SpEL(스프링 표현식)이라 글자는 작은따옴표로 감싼다. 나중에 주제별 글(HOME-03)을 캐시하면 `key = "#topic"`처럼 인자를 키로 쓸 수 있다.

### 3.5 프록시: 캐시는 메서드 호출을 가로채서 동작한다

`@Cacheable`이 붙은 빈을 다른 빈에 주입하면, 실제로 주입되는 것은 원래 객체가 아니라 그것을 감싼 **프록시**다. `@Transactional`과 같은 원리다([23](./23-transactions-locking.md)).

```
HomeService ──snapshot()──▶ [PopularRanking 프록시] ──캐시 확인──▶ Redis
                                 │ 적중: 바로 반환 (원래 메서드 실행 안 함)
                                 │ 실패: ▼
                                 └──▶ PopularRanking.snapshot() 실제 실행 → 결과를 Redis에 저장 → 반환
```

그래서 **같은 클래스 안에서** `this.snapshot()`으로 부르면 프록시를 거치지 않아 캐시가 전혀 안 된다. 이 프로젝트가 순위 계산(`PopularRanking`)과 그것을 쓰는 쪽(`HomeService`)을 **다른 클래스**로 나눈 이유다. 같은 이유로 `private` 메서드에 `@Cacheable`을 붙여도 소용없다.

### 3.6 Redis에 캐시가 저장되는 모양

`application.yml`:

```yaml
spring:
  cache:
    type: redis
    redis:
      time-to-live: 5m
      key-prefix: "blog:"
```

- `type: redis`: 캐시 저장소를 Redis로(스텝 1부터 있던 설정).
- `time-to-live: 5m`: 이 캐시 관리자가 만드는 모든 캐시 값의 수명 5분. Redis 키에 TTL이 걸린다.
- `key-prefix: "blog:"`: Redis 키 앞에 붙는 말. 멱등성 키(`idempotency:…`) 같은 다른 용도의 키와 섞이지 않는다.

실제 Redis 키는 **접두어 + 캐시 이름 + `::` + 키**였다(스텝 8에서 개발 서버로 확인).

```
$ docker exec blog-redis redis-cli keys 'blog:popular*'
blog:popularPosts::home
$ docker exec blog-redis redis-cli ttl 'blog:popularPosts::home'
268                                        ← 남은 수명(초), 300에서 줄어든다
```

### 3.7 값은 Java 직렬화로 저장된다

Redis는 바이트를 저장한다. 자바 객체를 바이트로 바꾸는 방법(**직렬화**)이 필요하다. 이 프로젝트처럼 따로 정하지 않으면 Spring Data Redis의 캐시는 **Java 기본 직렬화**(`JdkSerializationRedisSerializer`)를 쓴다. 실제 값의 앞부분을 보면 Java 직렬화의 표시 `ac ed 00 05`와 클래스 이름이 보인다.

```
$ docker exec blog-redis redis-cli get 'blog:popularPosts::home' | xxd | head -3
00000000: aced 0005 7372 0034 636f 6d2e 6e68 6e61  ....sr.4com.nhna
00000010: 6361 6465 6d79 2e62 6c6f 672e 686f 6d65  cademy.blog.home
00000020: 2e61 7070 6c69 6361 7469 6f6e 2e50 6f70  .application.Pop
```

그래서 캐시에 넣는 클래스는 `java.io.Serializable`을 구현해야 한다. 안 하면 저장할 때 직렬화 실패 예외가 난다. `PopularSnapshot`과 `PostScore`가 `implements Serializable`인 이유다. `LocalDateTime`, `List.of`/`stream().toList()`로 만든 목록은 이미 직렬화된다.

Java 직렬화는 간단하지만 단점이 있다(6장 함정). 많이 쓰는 대안은 JSON 직렬화다. 이 프로젝트는 캐시 값이 작고 하나뿐이라 기본값을 그대로 썼다.

### 3.8 `sync = true`: 캐시 쇄도 막기

5분 수명이 끝난 바로 그 순간 요청 100개가 동시에 오면? 100개 모두 "실패"를 보고 100번 집계를 돌린다. 이것을 **캐시 쇄도(cache stampede, thundering herd)**라 한다. 캐시가 막아 주던 부하가 한꺼번에 DB로 몰린다.

`@Cacheable(sync = true)`로 하면 같은 키를 동시에 원하는 스레드 중 **하나만** 메서드를 실행하고, 나머지는 그 결과가 캐시에 들어갈 때까지 기다렸다가 그 값을 받는다. 다만 이 잠금은 **서버(JVM) 하나 안에서**만 통한다. 서버가 여러 대면 서버마다 한 번씩은 계산할 수 있다. 그 정도면 충분하고, 서버 간까지 막으려면 Redis `SET NX` 잠금([17](./17-idempotency-redis.md) 3.6)이나 스케줄러(3.3)를 쓴다.

## 4. 동작 원리

### 4.1 홈 인기 글 요청 한 번

```
blog.test/  (HomePage)
  GET /api/home/popular
    HomeController.popular
      HomeService.popular()                                        [읽기 전용 트랜잭션]
        popularRanking.snapshot()          ← 프록시
          Redis GET blog:popularPosts::home
            있음(적중) → PopularSnapshot(snapshotAt, [글번호·점수 최대 100개]) 역직렬화
            없음(실패) → 집계 SQL 실행(36) → Redis SET … (TTL 300초) → 반환
        글 번호들로 DB 조회: visibleTo(비회원 기준) AND id IN (…)   ← 매번
        순위 순서대로 줄 세우고, 볼 수 없는 글은 빼고, 10개까지
      썸네일 붙이기(PostThumbnails)
  ← { snapshotAt: "2026-10-09T04:06:26.69+09:00", items: [{ rank: 1, post: {...} }, ...] }
```

### 4.2 5분 동안 무엇이 바뀌고 무엇이 그대로인가

| 사건 | 홈 인기 글에 언제 반영되나 |
| --- | --- |
| 어떤 글의 조회·공감·댓글이 늘어 순위가 바뀜 | 캐시가 끝난 뒤(최대 5분) |
| 순위 안의 글이 비공개·숨김·삭제됨, 블로그가 이용 제한됨 | **바로**. 그 글은 빠지고 아래 순위가 올라온다 |
| 순위 안의 글 제목을 고침 | **바로**(글 내용은 매번 DB에서 읽음) |
| 공감 수 표시 | **바로**(`likeCount`도 글에서 읽음) |

### 4.3 후보를 100개 두는 이유

캐시에는 상위 10개가 아니라 **상위 100개 후보**를 둔다. 10개만 두면, 그중 3개가 비공개가 되었을 때 5분 동안 7개만 보인다. 100개를 두면 빠진 자리를 11·12·13위가 채운다. 랭킹 전체보기(HOME-05)도 100위까지라 나중에 같은 값을 쓸 수 있다.

## 5. 이 프로젝트에서는

### 5.1 `global/config/CacheConfig.java` (스텝 1부터)

```java
@Configuration
@EnableCaching
public class CacheConfig {
}
```

`@EnableCaching`이 있어야 `@Cacheable`이 붙은 빈을 프록시로 감싼다. 저장소와 TTL은 코드가 아니라 `application.yml`(3.6)에서 정한다. 스텝 1에 만들어 두고 스텝 8에서 처음 썼다.

### 5.2 `home/application/PopularRanking.java`

```java
@Component
public class PopularRanking {

    public static final String CACHE = "popularPosts";

    static final int CANDIDATES = 100;

    private final PopularScoreRepository popularScoreRepository;
    private final PopularProperties properties;
    private final Clock clock;
    ...
    @Cacheable(cacheNames = CACHE, key = "'home'", sync = true)
    public PopularSnapshot snapshot() {
        LocalDateTime now = LocalDateTime.now(clock);
        return new PopularSnapshot(now, popularScoreRepository.topScores(now.minus(properties.window()),
                properties.viewWeight(), properties.likeWeight(), properties.commentWeight(), CANDIDATES));
    }
}
```

- `CACHE = "popularPosts"`: 캐시 이름을 상수로 둬서 테스트가 같은 이름으로 비울 수 있다.
- `cacheNames = CACHE, key = "'home'"`: Redis 키 `blog:popularPosts::home`.
- `sync = true`: 3.8.
- `public`: 프록시가 가로챌 수 있는 공개 메서드여야 한다.
- 메서드 본문은 **실패일 때만** 실행된다. 그러므로 `now`는 "계산한 시각"이고, 그대로 `snapshotAt`이 되어 화면에 "04:06 기준"으로 보인다.
- 실제 집계는 `PopularScoreRepository.topScores`([36](./36-ranking-aggregation.md)).

### 5.3 `PopularSnapshot`과 `PostScore`

```java
public record PopularSnapshot(LocalDateTime snapshotAt, List<PostScore> scores) implements Serializable {
}

public record PostScore(long postId, long score) implements Serializable {
}
```

- 레코드(record)도 `Serializable`을 구현할 수 있다. 필드가 모두 직렬화 가능해야 한다.
- 글 엔티티(`Post`)가 아니라 **번호와 점수만** 담는다. 엔티티를 캐시하면 지연 로딩 프록시·영속성 컨텍스트와 얽혀 꺼낼 때 문제가 생기고, 내용이 5분 늦어진다.

### 5.4 `HomeService.popular`: 캐시된 순위 + 매번 가시성

```java
@Transactional(readOnly = true)
public PopularPosts popular() {
    PopularSnapshot snapshot = popularRanking.snapshot();
    List<Long> rankedIds = snapshot.scores().stream().map(PostScore::postId).toList();
    if (rankedIds.isEmpty()) {
        return new PopularPosts(snapshot.snapshotAt(), List.of());
    }
    Specification<Post> condition = PostSpecifications.visibleTo(null, LocalDateTime.now(clock))
            .and((root, query, cb) -> root.get("id").in(rankedIds));
    Map<Long, Post> visible = postRepository.findBy(condition, query -> query.project("blog", "category").all())
            .stream()
            .collect(Collectors.toMap(Post::getId, Function.identity()));
    List<Post> ranked = rankedIds.stream()
            .map(visible::get)
            .filter(Objects::nonNull)
            .limit(POPULAR_SIZE)
            .toList();
    return new PopularPosts(snapshot.snapshotAt(), ranked);
}
```

- `popularRanking.snapshot()`: **다른 빈**이라 프록시를 거친다(3.5).
- `rankedIds.isEmpty()`: 최근 1시간 활동이 하나도 없으면 빈 목록. `id IN ()`은 SQL 오류라 미리 끝낸다.
- `visibleTo(null, now)`: **비회원 기준** 가시성. 명세가 "공개 글 상위 10"이라 로그인한 사람에게도 같은 목록이다. 구독자 공개 글은 처음부터 순위에 들지 않는다. 블로그 삭제·이용 제한, 주인 정지까지 모든 목록과 같은 조건이다([16](./16-authorization-visibility.md)).
- `.and(... in(rankedIds))`: 후보 번호 안에서만 찾는다. 최대 100개 번호, 기본 키로 찾는 쿼리라 가볍다.
- `project("blog", "category")`: 목록 한 줄에 블로그 이름·카테고리가 나가므로 함께 읽는다(N+1 방지, 홈 최신 글과 같은 방식).
- DB 결과는 순서가 없으므로 `Map`에 넣고, **캐시의 순위 순서대로** 다시 꺼낸다. 볼 수 없어서 DB가 안 돌려준 글은 `null`이라 `filter`로 빠진다.
- `limit(POPULAR_SIZE)`: 10개까지. 순위 번호는 컨트롤러에서 1부터 다시 매기므로 빠진 글이 있어도 1, 2, 3…으로 이어진다.

### 5.5 `HomeController.popular`와 응답

```java
@GetMapping("/api/home/popular")
public PopularPostsResponse popular() {
    PopularPosts popular = homeService.popular();
    List<Post> posts = popular.posts();
    Map<Long, String> thumbnails = postThumbnails.of(posts);
    return new PopularPostsResponse(DateTimes.toOffset(popular.snapshotAt()), IntStream.range(0, posts.size())
            .mapToObj(i -> new PopularPostsResponse.Item(i + 1, PostSummaryResponse.of(posts.get(i),
                    posts.get(i).getBlog(), thumbnails.get(posts.get(i).getId()))))
            .toList());
}
```

- 응답 모양은 contracts의 `{ snapshotAt, items: [{ rank, post }] }` 그대로다. `post`는 홈 최신 글과 같은 `PostSummary`라 화면이 같은 타입을 쓴다.
- `IntStream.range(0, n)`: 0부터 n−1까지 번호를 만들어 `i + 1`을 순위로 쓴다.
- `DateTimes.toOffset`: 다른 응답처럼 `+09:00`이 붙은 시각.

### 5.6 화면: `pages/home/HomePage.tsx`의 `PopularSection`

```tsx
return (
  <section className="section">
    <h2>인기 글 <small>최근 1시간 · {formatTime(popular.snapshotAt)} 기준</small></h2>
    {popular.items.length === 0
      ? <p className="muted">최근 1시간 동안 읽힌 글이 없습니다.</p>
      : (
        <div className="rank-list">
          {popular.items.map(({ rank, post }) => (
            <div key={post.id} className="rank">
              <b>{rank}</b>
              <a href={blogUrl(post.blog.address, `/${post.id}`)}>{post.title}</a>
              <a className="small muted" href={blogUrl(post.blog.address)}>{post.blog.name}</a>
            </div>
          ))}
        </div>
      )}
  </section>
)
```

- 목업 home.html의 "인기 글 · 최근 1시간 · 10:35 기준"과 `rank-list` 모양을 옮겼다. CSS도 목업의 `.rank-list`, `.rank`를 `index.css`에 더했다.
- `formatTime`: `"2026-10-09T04:06:26+09:00"` → `"04:06"`(앞에서 11~16번째 글자, `app/format.ts`).
- 인기 글 요청이 실패하면 영역을 숨긴다(`popular`가 null). 홈의 다른 부분(최신 글)은 그대로 보인다.
- 글은 다른 호스트(블로그 주소)라 `<Link>`가 아니라 `<a href>`다(홈 최신 글과 같음, [19](./19-react-router-api-client.md)).

### 5.7 설정값 `PopularProperties`

```java
@ConfigurationProperties(prefix = "app.popular")
public record PopularProperties(Duration window, int viewWeight, int likeWeight, int commentWeight) {
}
```

```yaml
app:
  popular:
    window: 1h
    view-weight: 1
    like-weight: 3
    comment-weight: 5
```

가중치는 명세에서 "Claude가 정한 기본값, 설정으로 바꾼다"고 한 값이다(research R-12). `view-weight`처럼 하이픈으로 쓴 이름이 레코드의 `viewWeight`에 붙는다(느슨한 바인딩, [02](./02-configuration-profiles.md)). `1h`는 `Duration`으로 바뀐다. 레코드를 빈으로 등록하는 것은 `BlogApplication`의 `@ConfigurationPropertiesScan`이 한다([01](./01-spring-boot-basics.md)).

캐시 수명(5분)은 이 레코드가 아니라 `spring.cache.redis.time-to-live`다. 다른 캐시가 생기면 같이 5분이 된다(주제별 글도 5분이라 명세와 맞다).

### 5.8 테스트 `HomePopularIntegrationTest`

```java
@BeforeEach
void setUp() {
    Objects.requireNonNull(cacheManager.getCache(PopularRanking.CACHE)).clear();
    ...
}
```

- Testcontainers의 Redis는 테스트 클래스끼리 **같이 쓴다**([05](./05-spring-testing.md)). 앞 테스트가 남긴 캐시가 있으면 새로 넣은 데이터가 안 보이므로, 테스트마다 `CacheManager`로 캐시를 비운다.

| 테스트 | 확인하는 것 |
| --- | --- |
| `likesAndCommentsWeighMoreThanViewsAndOnlyRecentPublicActivityCounts` | 조회 400(400점)보다 조회 300 + 공감 20 + 댓글 10(410점)이 위. 2시간 전 활동, 비공개 글, 이용 제한 블로그의 글, 지운 댓글만 많은 글은 빠짐 ([36](./36-ranking-aggregation.md)) |
| `rankingIsCachedButPostsThatBecameHiddenDropOutAtOnce` | ① 점수가 바뀌어도 캐시 동안 같은 순위·같은 `snapshotAt` ② 캐시 안의 1위 글을 비공개로 바꾸면 **바로** 빠지고 2위가 1위로 ③ 캐시를 비우면 새로 계산 |

②가 3.2의 "오래된 값" 문제를 막았는지 보는 테스트다. ①이 통과한다는 것은 캐시가 실제로 Redis에 저장되고 꺼내진다는 뜻이기도 하다(직렬화가 안 되면 여기서 실패한다).

### 5.9 (스텝 9) 인자마다 다른 캐시: 주제별 글

홈 주제별 글(HOME-03)은 주제가 10개라 순위도 10개다. 같은 메서드를 주제마다 따로 캐시하려면 **인자를 키에 넣는다**.

```java
@Cacheable(cacheNames = TOPIC_CACHE, key = "#topic.name()", sync = true)
public PopularSnapshot topicSnapshot(Topic topic) {
    ...
}
```

- `#topic`: SpEL에서 메서드 인자 `topic`을 가리킨다. `.name()`으로 enum 이름 글자(`IT_DEV`)를 키로 쓴다. Redis 키는 `blog:topicPosts::IT_DEV`, `blog:topicPosts::TRAVEL`…처럼 주제마다 따로 생기고, 각각 5분 TTL이다.
- 인자 이름으로 `#topic`을 쓰려면 컴파일된 클래스에 매개변수 이름이 남아 있어야 한다. Spring Boot의 Maven 설정은 `-parameters`로 컴파일해 이름을 남긴다.
- 캐시 이름을 홈 인기 글(`popularPosts`)과 나눠서 따로 비울 수 있다. 테스트(`HomeTopicIntegrationTest`)도 `TOPIC_CACHE`만 비운다.
- 6개를 채우는 최신 글은 캐시하지 않는다. 자세한 것은 [39](./39-category-hierarchy.md) 3.6, 5.6.

## 6. 자주 하는 실수와 함정

- **같은 클래스 안에서 `@Cacheable` 메서드를 부른다.** 프록시를 거치지 않아 캐시가 안 된다. 오류도 안 나서 알아차리기 어렵다. 클래스를 나눈다(3.5).
- **`private` 메서드나 `final` 클래스에 붙인다.** 프록시가 가로챌 수 없다.
- **`@EnableCaching`을 빠뜨린다.** 어노테이션이 그냥 무시된다.
- **엔티티를 캐시한다.** 지연 로딩 연관, 영속성 컨텍스트와 얽히고, 내용·권한 변경이 수명 동안 반영되지 않는다. 번호나 DTO를 캐시한다.
- **보는 사람마다 다른 결과를 고정 키로 캐시한다.** 로그인한 사람마다 볼 수 있는 글이 다른데(구독자 공개) 키를 `'home'` 하나로 두면, 처음 계산한 사람의 결과가 모두에게 나간다. 이 프로젝트는 "공개 글"만 순위에 넣어 모두에게 같게 했고, 가시성은 캐시 밖에서 다시 본다.
- **`Serializable`을 빠뜨린다.** Java 직렬화를 쓰는 Redis 캐시에 저장할 때 예외.
- **캐시 값 클래스의 모양을 바꿔 배포한다.** Java 직렬화는 클래스 구조가 바뀌면(필드 추가 등) 옛 값을 읽지 못한다. 배포 직후 Redis에 남은 옛 값을 꺼내다 오류가 날 수 있다. 수명(5분)이 지나면 사라지지만, 배포 때 캐시를 비우거나, 키 접두어에 버전을 붙이거나, JSON 직렬화를 쓰는 방법이 있다. 이 프로젝트는 아직 대비하지 않았다.
- **TTL을 안 준다.** `spring.cache.redis.time-to-live`가 없으면 값이 영원히 남아 순위가 바뀌지 않는다.
- **테스트끼리 캐시를 공유하는 것을 잊는다.** 앞 테스트의 값이 남아 "데이터를 넣었는데 안 보인다". `CacheManager`로 비운다.
- **캐시 쇄도를 생각하지 않는다.** 무거운 계산일수록 `sync = true`나 미리 계산(스케줄러)을 쓴다.
- **"캐시 = 빠르다"만 보고 아무 데나 붙인다.** 자주 바뀌고 정확해야 하는 값(공감 수, 내 글 목록)은 캐시하면 사용자가 "눌렀는데 안 바뀌네"를 본다. 오래돼도 되는 값에만.

## 7. 직접 해 보기

준비: `docker compose up -d`, `./mvnw spring-boot:run`.

### 7.1 캐시 키와 수명 보기

```bash
curl -s -H "Host: blog.test" localhost:8080/api/home/popular | python3 -m json.tool | head -20
docker exec blog-redis redis-cli keys 'blog:*'
docker exec blog-redis redis-cli ttl 'blog:popularPosts::home'        # 300 이하
sleep 5; docker exec blog-redis redis-cli ttl 'blog:popularPosts::home' # 5 줄어듦
```

### 7.2 같은 snapshotAt, 지우면 새로

```bash
for i in 1 2 3; do curl -s -H "Host: blog.test" localhost:8080/api/home/popular | grep -o '"snapshotAt":"[^"]*"'; done   # 셋 다 같음
docker exec blog-redis redis-cli del 'blog:popularPosts::home'
curl -s -H "Host: blog.test" localhost:8080/api/home/popular | grep -o '"snapshotAt":"[^"]*"'                           # 새 시각
```

### 7.3 값이 Java 직렬화인지 보기

```bash
docker exec blog-redis redis-cli get 'blog:popularPosts::home' | xxd | head -3   # aced 0005 …
```

### 7.4 캐시가 정말 SQL을 아끼는지 보기

`application-dev.yml`에 잠시 `logging.level.org.springframework.jdbc.core: DEBUG`를 넣고 서버를 다시 띄운다. `/api/home/popular`를 여러 번 부르면 `SELECT activity.post_id, SUM(...)` 집계 SQL은 처음 한 번만 로그에 나오고, 글을 찾는 JPA 쿼리는 매번 나온다(JPA 쿼리를 보려면 `spring.jpa.show-sql: true`).

### 7.5 프록시 함정 체험 (공부용 브랜치에서)

`HomeService`에 `PopularRanking`의 `snapshot` 내용을 그대로 옮긴 메서드를 만들고 `@Cacheable`을 붙인 뒤, `popular()`에서 `this.`로 부르게 바꾼다. 7.1의 `keys`에 캐시 키가 생기지 않는다. 확인 후 `git restore .`.

### 7.6 테스트

```bash
./mvnw test -Dtest=HomePopularIntegrationTest
```

## 8. 확인 문제

1. 인기 글에 캐시를 쓸 수 있는 근거가 된 명세 문구는?
<details><summary>답</summary>"5분마다 갱신"(spec 7.6, HOME-02). 순위가 5분 동안 같아도 된다는 뜻이라 한 번 계산한 결과를 5분 동안 다시 써도 된다.</details>

2. TTL 캐시와 스케줄러 방식의 차이를 하나씩 말하라.
<details><summary>답</summary>TTL 캐시는 수명이 끝난 뒤 처음 온 요청이 계산한다(간단, 아무도 안 오면 계산 안 함, 첫 요청이 기다림). 스케줄러는 정해진 간격으로 미리 계산해 둔다(요청은 늘 빠름, 서버가 여러 대면 누가 계산할지 정해야 함).</details>

3. `PopularRanking`과 `HomeService`를 다른 클래스로 나눈 이유는?
<details><summary>답</summary><code>@Cacheable</code>은 프록시가 메서드 호출을 가로채서 동작한다. 같은 클래스 안에서 this로 부르면 프록시를 거치지 않아 캐시가 안 된다.</details>

4. 캐시에 글 엔티티나 글 내용이 아니라 글 번호와 점수만 넣은 이유는?
<details><summary>답</summary>5분 동안 글이 비공개·삭제되거나 블로그가 이용 제한되면 바로 목록에서 빠져야 한다(헌법 원칙 II). 순위만 캐시하고 글 내용과 가시성은 매번 DB에서 읽어 확인한다. 엔티티는 지연 로딩·영속성 컨텍스트와 얽혀 캐시하기에도 맞지 않는다.</details>

5. 후보를 10개가 아니라 100개 두는 이유는?
<details><summary>답</summary>읽을 때 볼 수 없게 된 글이 빠지면 그 자리를 다음 순위가 채워 10개를 유지하기 위해서. 랭킹 전체보기(100위까지)도 나중에 같은 값을 쓸 수 있다.</details>

6. Redis에 저장된 캐시 키 모양은? 어떤 설정과 코드가 그 모양을 만드나?
<details><summary>답</summary><code>blog:popularPosts::home</code>. 접두어 <code>blog:</code>는 <code>spring.cache.redis.key-prefix</code>, <code>popularPosts</code>는 <code>cacheNames</code>, <code>home</code>은 <code>key = "'home'"</code>.</details>

7. `PopularSnapshot`이 `Serializable`을 구현해야 하는 이유는?
<details><summary>답</summary>따로 정하지 않은 Redis 캐시는 값을 Java 기본 직렬화로 바이트로 바꿔 저장한다. Serializable이 아니면 저장할 때 예외가 난다. 실제 값 앞에 Java 직렬화 표시 aced0005가 있다.</details>

8. `sync = true`가 막는 문제는? 한계는?
<details><summary>답</summary>캐시가 빈 순간 같은 키로 동시에 온 요청들이 모두 계산하는 캐시 쇄도를 막는다. 한 스레드만 계산하고 나머지는 결과를 기다린다. 한 서버(JVM) 안에서만 통하므로 서버가 여러 대면 서버마다 한 번씩은 계산할 수 있다.</details>

9. 로그인한 사람에게도 비회원 기준(`visibleTo(null)`)으로 거르는 이유는?
<details><summary>답</summary>명세가 "공개 글 상위 10"이라 모두에게 같은 목록이다. 사람마다 다른 결과를 고정 키 하나로 캐시하면 처음 계산한 사람의 결과가 모두에게 나가는 문제도 생기지 않는다.</details>

10. 통합 테스트가 시작할 때 캐시를 비우는 이유는?
<details><summary>답</summary>Testcontainers의 Redis를 여러 테스트가 같이 쓰므로, 앞 테스트가 남긴 순위가 남아 있으면 새로 넣은 데이터가 5분 동안 반영되지 않아 테스트가 틀린다.</details>

## 9. 더 읽을거리

- Spring Framework 레퍼런스, "Cache Abstraction"(`@Cacheable`, `sync`, 키 생성, "Proxy mode"의 자기 호출 제한)
- Spring Boot 레퍼런스, "Caching" → "Redis"(`spring.cache.redis.time-to-live`, `key-prefix`, `RedisCacheManagerBuilderCustomizer`)
- Spring Data Redis 레퍼런스, "Redis Cache"(`RedisCacheConfiguration`, 직렬화 설정)
- 『이펙티브 자바』 12장 "직렬화"(Java 직렬화를 피해야 하는 이유)
- 캐시 쇄도(cache stampede)와 대책: 잠금, 확률적 조기 만료, 미리 계산
- Redis Sorted Set(`ZADD`, `ZREVRANGE`)으로 실시간 랭킹을 만드는 방법
