# 42. 두 번째 DB와 커밋 뒤 비동기 처리

> 관련 스텝: [스텝 10](../step-10.md) (T069a, T069b) · 관련 개념: [41-embedding-vector-search](./41-embedding-vector-search.md), [01-spring-boot-basics](./01-spring-boot-basics.md), [03-flyway-migration](./03-flyway-migration.md), [04-docker-compose](./04-docker-compose.md), [05-spring-testing](./05-spring-testing.md), [23-transactions-locking](./23-transactions-locking.md), [35-spring-cache-redis](./35-spring-cache-redis.md)

## 1. 이 문서로 배우는 것

- 한 애플리케이션이 **DB 두 개**(MySQL + PostgreSQL)를 쓰는 법: 자동 설정이 멈추지 않게 두 번째 `DataSource` 만들기(`@Bean(defaultCandidate = false)`, `@Qualifier`)
- 두 번째 DB의 표를 **따로 된 Flyway**로 만들기(이력 표가 DB마다 따로)
- 두 DB 사이에는 외래 키도, 한 트랜잭션도 없다는 것과 그 결과
- **도메인 이벤트**: 글 쓰기 기능이 추천 기능을 모르게 하면서 알리기(`ApplicationEventPublisher`)
- **`@TransactionalEventListener`**: 트랜잭션이 **커밋된 뒤에만** 이벤트를 받기
- **`@Async`**: 요청 스레드와 따로 돌리기, `@EnableAsync`, 프록시라서 생기는 함정
- 부가 기능이 실패해도 본 기능을 막지 않기, 서버가 뜰 때 빠진 것 채우기
- 테스트: 컨테이너를 하나 더 띄우고 설정값으로 이어 주기(`DynamicPropertyRegistrar`), 비동기 결과 기다리기

**먼저 알면 좋은 것**: 빈과 자동 설정([01](./01-spring-boot-basics.md)), Flyway([03](./03-flyway-migration.md)), docker compose([04](./04-docker-compose.md)), Testcontainers([05](./05-spring-testing.md)), `@Transactional`과 커밋([23](./23-transactions-locking.md)), 프록시로 동작하는 어노테이션([35](./35-spring-cache-redis.md) 3.5).

## 2. 왜 필요한가

비슷한 글 추천(OWN-06)은 글 임베딩을 PostgreSQL(pgvector)에 둔다([41](./41-embedding-vector-search.md)). 주 데이터는 MySQL이다. 그래서 두 가지 문제가 생긴다.

1. **DB 두 개**: Spring Boot는 `spring.datasource.*`로 DB 하나를 자동으로 만들어 준다. 그런데 `DataSource` 빈을 하나 더 만들면 "사용자가 직접 만들었구나" 하고 **자동 설정을 멈춘다.** 그러면 MySQL·JPA·Flyway가 모두 흔들린다.
2. **언제 임베딩을 만드나**: 글을 저장할 때 바로 Ollama를 부르면, 글 저장 응답이 모델 계산(첫 호출 2초)을 기다린다. Ollama가 꺼져 있으면 글 저장까지 실패한다. 그리고 글 쓰기 코드(`post/`)가 추천(`recommend/`)을 직접 부르면, 추천을 빼고 싶을 때 글 쓰기 코드를 고쳐야 한다(명세는 "통째로 빼도 됨").

## 3. 기본 개념

### 3.1 DataSource와 자동 설정

**DataSource**는 DB 연결을 내주는 객체다(보통 연결 풀, 이 프로젝트는 HikariCP). JPA, `JdbcTemplate`, Flyway가 모두 이것을 주입받아 DB에 닿는다.

Spring Boot의 `DataSourceAutoConfiguration`은 "DataSource 빈이 **없으면** `spring.datasource.*`로 하나 만든다"(`@ConditionalOnMissingBean`)이다. 내가 하나 만들면 "있다"가 되어 자동 설정이 물러난다. 예전에는 그래서 DB 두 개를 쓰려면 주 DB까지 직접 만들고 `@Primary`를 붙여야 했다.

### 3.2 `@Bean(defaultCandidate = false)`

Spring Framework 6.2부터 `@Bean`에 `defaultCandidate = false`를 줄 수 있다. 이 빈은 **"타입만으로 고를 때의 후보"에서 빠진다.**

- `DataSource`를 타입으로 찾는 곳(JPA, Flyway, 자동 설정의 "있나?" 검사)에는 보이지 않는다. 그래서 주 DB 자동 설정이 그대로 돈다.
- 이 빈은 **이름표(`@Qualifier`)를 짚어야만** 주입된다.

```java
@Bean(defaultCandidate = false)
@Qualifier("recommend")
public HikariDataSource recommendDataSource(...) { ... }

// 쓰는 쪽
public PostEmbeddingRepository(@Qualifier("recommend") NamedParameterJdbcTemplate jdbc) { ... }
```

스텝 10에서 이렇게 만든 뒤 테스트를 돌려 보니, MySQL 마이그레이션 3개와 추천 DB 마이그레이션 1개가 따로 적용되고 JPA도 그대로 MySQL을 썼다.

### 3.3 DB 두 개 사이에 없는 것

- **외래 키**: `post_embedding.post_id`는 MySQL `post.id`를 가리키지만, 다른 DB라 외래 키를 걸 수 없다. 글을 지우면 **애플리케이션이** 임베딩도 지워야 한다. 지우다 실패해 남은 행은 나중에 정리한다(5.6 `sync`).
- **한 트랜잭션**: MySQL 커밋과 PostgreSQL 쓰기를 하나로 묶을 수 없다(분산 트랜잭션은 이 규모에선 과하다). 그래서 "글 저장이 먼저 확실히 끝나고(커밋), 그다음 임베딩"으로 순서를 정한다. 임베딩이 실패해도 글은 저장돼 있고, 다음 기회(수정, 서버 시작)에 다시 만든다. 이렇게 "결국에는 맞춰지는" 방식을 **최종 일관성**(eventual consistency)이라 한다.
- **조인**: 두 DB의 표를 SQL 하나로 조인할 수 없다. 추천은 PostgreSQL에서 번호를 뽑고 MySQL에서 그 번호로 읽는 두 단계다([41](./41-embedding-vector-search.md) 3.6).

### 3.4 도메인 이벤트

**이벤트**는 "이런 일이 일어났다"는 알림 객체다. 알리는 쪽은 **누가 듣는지 모른다.**

```java
// 글 쓰기 쪽 (post)
events.publishEvent(new PostContentChangedEvent(saved.getId()));

// 추천 쪽 (recommend)
@TransactionalEventListener
public void onContentChanged(PostContentChangedEvent event) { ... }
```

- `post` 패키지는 `recommend`를 import하지 않는다. 의존 방향이 `recommend → post`(추천이 글 이벤트를 안다) 하나뿐이다.
- 추천을 통째로 빼면 듣는 쪽만 사라지고 글 쓰기 코드는 그대로다.
- 이벤트는 레코드 하나(`PostContentChangedEvent(Long postId)`)다. 글 전체가 아니라 번호만 담는다. 받는 쪽이 필요할 때 최신 상태를 읽는다.

### 3.5 `@TransactionalEventListener`: 커밋된 뒤에만

평범한 `@EventListener`는 `publishEvent`를 부른 **그 자리에서 바로** 실행된다. 글 저장 트랜잭션이 아직 커밋되지 않은 상태다. 그러면:

- 그 뒤에 글 저장이 실패해 롤백되면, 없는 글의 임베딩을 만들어 버린다.
- 다른 스레드에서 글을 읽으면 아직 커밋 전이라 옛 내용(또는 없음)이 보인다(격리 수준, [33](./33-isolation-deadlock.md)).

`@TransactionalEventListener`는 이벤트를 **트랜잭션이 끝날 때까지 미뤘다가** 정한 단계에 실행한다. 기본 단계가 `AFTER_COMMIT`이다. 커밋에 성공했을 때만 실행되고, 롤백되면 실행되지 않는다.

| 단계 | 언제 |
| --- | --- |
| `AFTER_COMMIT` (기본) | 커밋 성공 뒤 |
| `AFTER_ROLLBACK` | 롤백 뒤 |
| `AFTER_COMPLETION` | 어느 쪽이든 끝난 뒤 |
| `BEFORE_COMMIT` | 커밋 직전(아직 같은 트랜잭션) |

주의: 트랜잭션 **밖에서** 발행한 이벤트는 기본적으로 **아예 실행되지 않는다**(기다릴 커밋이 없어서). 그래서 이벤트는 `@Transactional` 메서드(`PostService.publish/edit/delete`) 안에서 발행한다. 트랜잭션 밖에서도 받고 싶으면 `fallbackExecution = true`를 준다.

일괄 삭제(`ManagePostService.delete`)는 바깥 트랜잭션 하나에서 `PostService.delete`를 여러 번 부른다([37](./37-filtered-list-bulk-actions.md)). 이벤트도 여러 개 나가고, 바깥 트랜잭션이 커밋된 뒤 한꺼번에 처리된다.

### 3.6 `@Async`

`@Async`가 붙은 메서드는 **다른 스레드에서** 실행되고, 부른 쪽은 기다리지 않는다. `@EnableAsync`로 켜고, 스레드는 Spring Boot가 만들어 주는 실행기(`applicationTaskExecutor`, 스레드 풀)에서 나온다.

`@TransactionalEventListener` + `@Async`를 함께 쓰면: 커밋된 뒤, 요청 스레드가 아니라 다른 스레드에서 임베딩을 만든다. 글 저장 응답은 임베딩을 기다리지 않는다.

`@Async`도 `@Transactional`·`@Cacheable`처럼 **프록시**로 동작한다([35](./35-spring-cache-redis.md) 3.5). 같은 클래스 안에서 `this.method()`로 부르면 비동기가 되지 않는다. 그래서 이벤트 받기(`PostEmbeddingListener`)와 실제 일(`PostEmbeddingService`)을 다른 클래스로 나눴다.

비동기 메서드에서 난 예외는 부른 쪽에 전달되지 않는다(이미 응답이 나갔다). 그냥 두면 로그에만 남는다. 그래서 서비스 안에서 잡아 **경고로 남기고 넘어간다**(5.6).

## 4. 동작 원리

```
요청 스레드                                               비동기 스레드(applicationTaskExecutor)
POST /api/posts
  PostService.publish  [트랜잭션 시작]
    post 저장, 태그 연결
    publishEvent(PostContentChangedEvent(12))   → 보류
  [커밋] ─────────────────────────────────────→  PostEmbeddingListener.onContentChanged
← 201 (임베딩을 기다리지 않음)                        PostEmbeddingService.refresh(12)
                                                       MySQL: 12번 글 읽기(커밋된 내용)
                                                       Ollama: 임베딩
                                                       PostgreSQL: upsert
                                                       실패하면 경고 로그만

서버 시작 → ApplicationReadyEvent
  PostEmbeddingListener.onReady (@Async)  →  PostEmbeddingService.sync()
                                               발행 글 번호(MySQL) vs 임베딩 번호(PostgreSQL)
                                               없는 것은 만들고, 지워진 글의 것은 지움
```

## 5. 이 프로젝트에서는

### 5.1 docker compose (`docker-compose.yml`)

```yaml
  postgres:
    image: pgvector/pgvector:pg17
    container_name: blog-postgres
    environment:
      POSTGRES_DB: recommend
      ...
  ollama:
    image: ollama/ollama:latest
    container_name: blog-ollama
    volumes:
      - ollama:/root/.ollama

volumes:
  ...
  ollama:
    external: true
```

- `pgvector/pgvector:pg17`: pgvector가 미리 설치된 PostgreSQL 17 이미지.
- `ollama` 볼륨은 `external: true`다. compose가 새로 만들지 않고, 지원이 **이미 만들어 둔** `ollama` 볼륨(bge-m3가 받아져 있음)을 그대로 쓴다. 그래서 모델을 다시 받지 않는다. 볼륨이 없는 컴퓨터에서는 `docker volume create ollama` 뒤 `docker exec blog-ollama ollama pull bge-m3`.

### 5.2 `recommend/config/RecommendDataSourceConfig.java`

```java
@Bean(defaultCandidate = false)
@Qualifier(QUALIFIER)
public HikariDataSource recommendDataSource(RecommendProperties properties) {
    HikariDataSource dataSource = DataSourceBuilder.create()
            .type(HikariDataSource.class)
            .url(properties.datasource().url())
            .username(properties.datasource().username())
            .password(properties.datasource().password())
            .build();
    dataSource.setPoolName("recommend");
    return dataSource;
}

@Bean(defaultCandidate = false)
@Qualifier(QUALIFIER)
public NamedParameterJdbcTemplate recommendJdbcTemplate(@Qualifier(QUALIFIER) DataSource recommendDataSource) {
    Flyway.configure()
            .dataSource(recommendDataSource)
            .locations("classpath:db/recommend")
            .load()
            .migrate();
    return new NamedParameterJdbcTemplate(recommendDataSource);
}
```

- `DataSourceBuilder`: Spring Boot가 주는 DataSource 만들기 도구. 접속 정보는 `app.recommend.datasource.*`(dev는 `application-dev.yml`, prod는 환경 변수 `RECOMMEND_DB_URL` 등)에서 온다.
- `setPoolName("recommend")`: 로그에 "recommend - Start completed."처럼 어느 풀인지 보인다.
- **Flyway를 하나 더**: 주 DB의 Flyway(자동 설정, `db/migration`)와 따로, 추천 DB에는 `db/recommend`를 적용한다. DB마다 이력 표(`flyway_schema_history`)가 따로 생긴다. Flyway를 빈으로 하나 더 등록하면 주 DB의 Flyway 자동 설정과 부딪힐 수 있어서, 빈으로 두지 않고 `JdbcTemplate`을 만들 때 그 자리에서 마이그레이션한다. 이 빈을 쓰는 곳(임베딩 저장소)이 생기기 전에 표가 만들어진다.
- PostgreSQL용 Flyway는 `flyway-database-postgresql` 의존성이 따로 필요하다(Flyway 10부터 DB별 모듈로 나뉨, MySQL용 `flyway-mysql`과 같은 이유).

### 5.3 이벤트 발행: `post/application/PostService.java`

```java
@Transactional
public Post publish(Blog blog, PostCommand command) {
    ...
    Post saved = postRepository.save(post);
    // 받는 쪽(추천 임베딩)은 이 트랜잭션이 커밋된 뒤에 움직인다(@TransactionalEventListener)
    events.publishEvent(new PostContentChangedEvent(saved.getId()));
    return saved;
}
```

- `ApplicationEventPublisher`를 주입받아 쓴다. `edit`도 같은 이벤트, `delete`는 `PostDeletedEvent`.
- 공개 범위만 바꾸는 경우(`changeVisibility`)는 내용이 그대로라 이벤트를 내지 않는다. 볼 수 있는지는 추천할 때 거른다.

### 5.4 이벤트 받기: `recommend/application/PostEmbeddingListener.java`

```java
@Async
@TransactionalEventListener
public void onContentChanged(PostContentChangedEvent event) {
    postEmbeddingService.refresh(event.postId());
}

@Async
@TransactionalEventListener
public void onDeleted(PostDeletedEvent event) {
    postEmbeddingService.remove(event.postId());
}

/** 서버가 다 뜬 뒤 한 번, 임베딩이 없는 발행 글을 채운다. */
@Async
@EventListener(ApplicationReadyEvent.class)
public void onReady() {
    postEmbeddingService.sync();
}
```

- 이 클래스는 "언제"만 정하고, "무엇을"은 `PostEmbeddingService`에 맡긴다(프록시 함정 피하기, 3.6).
- `ApplicationReadyEvent`: 서버가 요청을 받을 준비를 마쳤을 때 한 번. 이것도 `@Async`라 서버 시작을 늦추지 않는다.

### 5.5 `global/config/AsyncConfig.java`

```java
@Configuration
@EnableAsync
public class AsyncConfig {
}
```

`@EnableAsync`가 없으면 `@Async`는 그냥 무시되고 같은 스레드에서 돈다(오류도 안 난다).

### 5.6 실패를 삼키는 `PostEmbeddingService`

```java
public void refresh(long postId) {
    try {
        Post post = postRepository.findById(postId).orElse(null);
        if (post == null || post.isDeleted() || post.getStatus() != PostStatus.PUBLISHED) {
            postEmbeddingRepository.delete(postId);
            return;
        }
        postEmbeddingRepository.save(postId, embeddingClient.embed(text(post)));
    } catch (RuntimeException e) {
        log.warn("글 {}의 임베딩을 만들지 못했습니다: {}", postId, e.toString());
    }
}
```

- 이벤트에는 번호만 있으므로 **지금 상태를 다시 읽는다**. 그사이 지워졌으면 임베딩을 지운다.
- 커밋 뒤라 다른 스레드(여기)에서 읽어도 새 내용이 보인다.
- 모든 예외를 잡아 경고로 남긴다. Ollama가 꺼져 있어도 글 쓰기와 서버는 멀쩡하다. 단위 테스트 `embeddingServerFailureIsSwallowed`가 "Connection refused"를 던지는 가짜 클라이언트로 이것을 확인한다.

```java
public int sync() {
    List<Long> published = postRepository.findPublishedIds();
    Set<Long> embedded = new HashSet<>(postEmbeddingRepository.findAllPostIds());
    Set<Long> stale = new HashSet<>(embedded);
    published.forEach(stale::remove);
    postEmbeddingRepository.deleteAll(stale);
    ... 임베딩이 없는 발행 글마다 refresh
}
```

- 두 DB를 맞추는 정리 작업이다. 이미 있던 글(스텝 10 전), Ollama가 꺼져 있던 사이에 쓴 글을 채우고, 지우다 실패해 남은 임베딩을 지운다(3.3의 외래 키가 없는 빈자리). 스텝 10을 만들며 개발 서버를 띄우자 발행 글 12개의 임베딩이 이렇게 채워졌다.
- 글이 아주 많아지면 번호 전부를 메모리에 올리는 방식은 무겁다. 그때는 나눠 읽기(페이지)나 "임베딩 만든 시각" 칸으로 바꾼다.

### 5.7 테스트

`TestcontainersConfiguration`에 pgvector 컨테이너를 더하고, 접속 정보를 설정값으로 넣는다.

```java
@Bean
PostgreSQLContainer recommendPostgresContainer() {
    return new PostgreSQLContainer(DockerImageName.parse("pgvector/pgvector:pg17").asCompatibleSubstituteFor("postgres"))
            .withDatabaseName("recommend");
}

@Bean
DynamicPropertyRegistrar recommendDataSourceProperties(PostgreSQLContainer recommendPostgresContainer) {
    return registry -> {
        registry.add("app.recommend.datasource.url", recommendPostgresContainer::getJdbcUrl);
        ...
    };
}
```

- MySQL·Redis에는 `@ServiceConnection`을 붙였지만 PostgreSQL에는 붙이지 않는다. 붙이면 Spring Boot가 이것을 **주 DB 연결**로 써 버린다. 우리 설정값(`app.recommend.datasource.*`)으로 이어 주는 게 맞다.
- `asCompatibleSubstituteFor("postgres")`: "이 이미지는 postgres와 같은 것으로 봐도 된다." Testcontainers는 이미지 이름이 `postgres`가 아니면 확인을 위해 이렇게 적어 달라고 한다.
- `DynamicPropertyRegistrar`(Spring 6.2): 컨테이너가 뜬 뒤에야 알 수 있는 값(임의 포트)을 설정으로 넣는다.

비동기 결과는 바로 확인할 수 없으니 **조건이 맞을 때까지 잠깐 기다린다.**

```java
static void await(BooleanSupplier condition) throws InterruptedException {
    long deadline = System.currentTimeMillis() + 5000;
    while (!condition.getAsBoolean()) {
        if (System.currentTimeMillis() > deadline) {
            throw new AssertionError("5초 안에 조건이 맞지 않았습니다");
        }
        Thread.sleep(50);
    }
}
```

`Thread.sleep(2000)`처럼 정해진 시간만큼 자는 것보다 낫다. 빨리 끝나면 빨리 넘어가고, 느린 컴퓨터에서도 5초까지 기다린다.

| 테스트 | 확인하는 것 |
| --- | --- |
| `PostEmbeddingIntegrationTest.publishEditAndDeleteKeepTheEmbeddingInStep` | 발행하면 임베딩이 생기고, 수정하면 바뀌고, 삭제하면 사라짐 |
| `…syncFillsMissingEmbeddingsAndDropsDeletedOnes` | 임베딩이 없는 글을 채우고, 없는 글의 임베딩을 지움 |
| `PostEmbeddingServiceTest.embeddingServerFailureIsSwallowed` | 임베딩 서버 실패가 밖으로 새지 않음 |
| `…textIsTitleThenBodyCutAtTwoThousandChars` | 넣는 글자 = 제목 + 본문, 2,000자까지 |

테스트용 가짜 임베딩은 [41](./41-embedding-vector-search.md) 5.7.

## 6. 자주 하는 실수와 함정

- **두 번째 `DataSource`를 평범한 `@Bean`으로 만든다.** 주 DB 자동 설정이 멈추고, JPA·Flyway가 엉뚱한 DB를 쓰거나 "DataSource가 둘"이라며 뜨지 않는다. `defaultCandidate = false` + `@Qualifier`, 또는 주 DB를 직접 만들고 `@Primary`.
- **테스트 컨테이너에 `@ServiceConnection`을 붙인다.** 두 번째 DB가 주 DB 자리를 차지한다.
- **Flyway 위치를 같은 폴더로 둔다.** MySQL 스크립트가 PostgreSQL에 돌거나 반대가 된다. 폴더(`db/migration`, `db/recommend`)를 나눈다.
- **두 DB를 한 트랜잭션처럼 믿는다.** MySQL이 롤백돼도 PostgreSQL 쓰기는 남는다. 커밋 뒤에 쓰고, 어긋남은 정리 작업으로 맞춘다.
- **`@EventListener`로 받는다.** 커밋 전에 실행되어 롤백된 글의 임베딩이 생기거나, 다른 스레드에서 옛 내용을 읽는다.
- **`@TransactionalEventListener`인데 트랜잭션 밖에서 발행한다.** 아무 일도 안 일어난다(`fallbackExecution` 없이는).
- **`@EnableAsync`를 빠뜨린다.** 같은 스레드에서 돌아 글 저장이 느려진다. 오류가 없어 알아차리기 어렵다.
- **같은 클래스 안에서 `@Async` 메서드를 부른다.** 프록시를 거치지 않아 비동기가 아니다.
- **비동기 작업의 예외를 그냥 둔다.** 아무도 모르게 사라진다. 잡아서 남기고, 정리 작업으로 다시 맞출 길을 둔다.
- **비동기 결과를 `Thread.sleep`으로 기다리는 테스트.** 느린 컴퓨터에서 깨지고, 빠른 컴퓨터에서는 쓸데없이 느리다. 조건이 맞을 때까지 짧게 돌며 기다린다.

## 7. 직접 해 보기

### 7.1 두 DB 보기

```bash
docker compose up -d
docker exec -it blog-postgres psql -U blog -d recommend -c '\d post_embedding'
docker exec -it blog-postgres psql -U blog -d recommend -c 'select version, description from flyway_schema_history'
docker exec -it blog-mysql mysql -ublog -pblog blog -e 'select version, description from flyway_schema_history'
```

DB마다 이력 표가 따로 있고 버전 번호도 따로 매겨진다.

### 7.2 비동기 눈으로 보기

서버 로그를 보면서 글을 발행한다. 요청 로그는 `http-nio-...` 스레드, 임베딩 쪽(실패 경고 등)은 `task-1` 같은 다른 스레드 이름으로 찍힌다. Ollama를 끄고(`docker stop blog-ollama`) 글을 발행해 보면, 발행은 바로 성공하고 로그에 "임베딩을 만들지 못했습니다" 경고가 남는다.

### 7.3 커밋 전과 후 (공부용 브랜치에서)

`PostEmbeddingListener`의 `@TransactionalEventListener`를 `@EventListener`로 바꾸고 `@Async`를 지운 뒤, `PostEmbeddingService.refresh`에서 읽은 글 제목을 로그로 찍어 본다. 수정할 때 **옛 제목**이 보이거나(커밋 전), 테스트가 흔들리는지 본다. 끝나면 `git restore .`.

### 7.4 테스트

```bash
./mvnw test -Dtest='PostEmbeddingIntegrationTest,PostEmbeddingServiceTest,SimilarPostIntegrationTest'
```

처음에는 pgvector 이미지를 받느라 느리다(스텝 10 첫 실행 32초).

## 8. 확인 문제

1. DataSource 빈을 하나 더 평범하게 만들면 무슨 일이 생기나?
<details><summary>답</summary>DataSourceAutoConfiguration이 "DataSource가 이미 있다"며 물러나 주 DB 자동 설정이 멈춘다. JPA·Flyway가 흔들린다.</details>

2. `@Bean(defaultCandidate = false)`가 이 문제를 푸는 방식은?
<details><summary>답</summary>타입만으로 고를 때의 후보에서 빠져서, 자동 설정의 "있나?" 검사와 JPA·Flyway의 주입에 보이지 않는다. @Qualifier로 이름을 짚어야만 주입된다.</details>

3. 두 DB 사이에 외래 키와 한 트랜잭션이 없어서 이 프로젝트가 대신 한 것은?
<details><summary>답</summary>글을 지우면 애플리케이션이 임베딩도 지우고, 글 저장이 커밋된 뒤에 임베딩을 쓰며, 어긋난 것은 서버 시작 때 sync로 맞춘다(최종 일관성).</details>

4. 글 쓰기 쪽이 추천 쪽을 직접 부르지 않고 이벤트를 내는 이유는?
<details><summary>답</summary>post가 recommend를 모르게 해서, 추천을 통째로 빼도 글 쓰기 코드를 고치지 않게 한다. 의존 방향이 recommend → post 하나뿐이다.</details>

5. `@EventListener` 대신 `@TransactionalEventListener`를 쓰는 이유는?
<details><summary>답</summary>커밋에 성공한 뒤에만 실행해서, 롤백된 글의 임베딩을 만들지 않고, 다른 스레드에서 읽어도 커밋된 새 내용이 보이게 하려고.</details>

6. `@TransactionalEventListener`가 아무 일도 하지 않는 경우는?
<details><summary>답</summary>이벤트를 트랜잭션 밖에서 발행했을 때. 기다릴 커밋이 없어 실행되지 않는다(fallbackExecution = true면 실행).</details>

7. `@Async`가 비동기로 돌지 않는 경우 두 가지는?
<details><summary>답</summary>@EnableAsync가 없을 때, 같은 클래스 안에서 this로 부를 때(프록시를 거치지 않음).</details>

8. 비동기 임베딩이 실패해도 예외를 던지지 않고 경고만 남기는 이유와, 그 대신 마련한 것은?
<details><summary>답</summary>응답이 이미 나간 뒤라 예외가 아무에게도 가지 않고, 추천은 부가 기능이라 글 쓰기·서버를 막으면 안 된다. 서버 시작 때 sync가 빠진 임베딩을 다시 만든다.</details>

9. 테스트에서 PostgreSQL 컨테이너에 `@ServiceConnection`을 붙이지 않은 이유는?
<details><summary>답</summary>붙이면 Spring Boot가 그것을 주 DB 연결로 써 버린다. 두 번째 DB라 DynamicPropertyRegistrar로 app.recommend.datasource.* 설정에 이어 준다.</details>

10. 비동기 결과를 기다릴 때 `Thread.sleep(2000)` 대신 조건을 돌며 기다리는 이유는?
<details><summary>답</summary>빨리 끝나면 바로 넘어가고, 느린 환경에서도 최대 시간까지 기다려서 테스트가 덜 흔들리고 덜 느리다.</details>

## 9. 더 읽을거리

- Spring Boot 레퍼런스, "Data Access" → "Configure Two DataSources"
- Spring Framework 레퍼런스, `@Bean`의 `defaultCandidate`, "Standard and Custom Events", "Transaction-bound Events"(`@TransactionalEventListener`), "Annotation Support for Scheduling and Asynchronous Execution"(`@Async`)
- Spring Boot 레퍼런스, "Task Execution and Scheduling"(`applicationTaskExecutor`)
- Flyway 문서, 여러 DB와 DB별 모듈(`flyway-database-postgresql`)
- Testcontainers 문서, PostgreSQL 모듈, `asCompatibleSubstituteFor`; Spring Framework `DynamicPropertyRegistrar`
- 트랜잭셔널 아웃박스(outbox) 패턴: 이벤트를 DB에 먼저 기록해 "커밋됐는데 이벤트가 사라지는" 일까지 막는 방법
