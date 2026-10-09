# 41. 임베딩과 벡터 검색: 비슷한 글 추천

> 관련 스텝: [스텝 10](../step-10.md) (T069b, T069c, T069d) · 관련 개념: [42-second-db-async-events](./42-second-db-async-events.md), [16-authorization-visibility](./16-authorization-visibility.md), [32-search-like](./32-search-like.md), [35-spring-cache-redis](./35-spring-cache-redis.md), [05-spring-testing](./05-spring-testing.md)

## 1. 이 문서로 배우는 것

- **임베딩(embedding)**: 글을 "뜻을 담은 숫자 벡터"로 바꾸는 것. 낱말이 달라도 뜻이 비슷하면 벡터가 가깝다
- 벡터가 "가깝다"를 재는 법: **코사인 유사도**와 **코사인 거리**, 정규화(길이 1)
- 낱말 검색(LIKE, [32](./32-search-like.md))과 벡터 검색의 차이
- **pgvector**: PostgreSQL에서 벡터를 저장하고 가까운 순으로 찾기(`vector(1024)`, `<=>`), **HNSW** 근사 최근접 이웃 인덱스
- **Ollama + bge-m3**: 내 컴퓨터에서 임베딩 모델 돌리기, `/api/embed` 호출
- 추천 결과에서 **볼 수 없는 글 거르기**: 후보를 넉넉히 뽑고 가시성으로 거른다
- 진짜 모델 없이 **가짜 임베딩으로 테스트**하는 법
- 화면: 비슷한 글 카드, 빈 배열이면 숨기기

**먼저 알면 좋은 것**: 글 가시성 조건 `visibleTo`([16](./16-authorization-visibility.md)), 블로그 안 검색의 LIKE([32](./32-search-like.md)), "후보를 넉넉히 두고 읽을 때 가시성 확인"이라는 인기 글의 방식([35](./35-spring-cache-redis.md) 5.4).

## 2. 왜 필요한가

OWN-06 "글 상세 아래에 내용이 비슷한 글을 추천한다."

"비슷하다"를 낱말로 판단하면 한계가 뚜렷하다. "Spring Security 필터 체인"과 "스프링 시큐리티로 로그인 토큰 검증"은 겹치는 낱말이 거의 없다(영어·한국어 표기도 다르다). LIKE나 태그로는 둘을 이을 수 없다.

임베딩 모델은 글을 수백~수천 개의 숫자로 바꾸는데, 이 숫자들이 **뜻**을 담도록 학습되어 있다. 뜻이 비슷한 글은 숫자 벡터도 비슷한 방향을 가리킨다. 스텝 10을 만들며 실제로 재 본 값(bge-m3, 1에 가까울수록 비슷):

| 비교 | 코사인 유사도 |
| --- | --- |
| "Spring Security 필터 체인과 JWT 인증 정리" ↔ "스프링 시큐리티로 로그인 토큰 검증하기" | 0.580 |
| "Spring Security 필터 체인과 JWT 인증 정리" ↔ "제주도 3박 4일 여행 맛집 코스" | 0.353 |

겹치는 낱말이 없는데도 보안 글끼리 더 가깝다.

## 3. 기본 개념

### 3.1 벡터와 임베딩

**벡터**는 숫자를 줄지어 놓은 것이다. `[0.12, -0.03, 0.88, …]`. 칸 수를 **차원**이라 한다. bge-m3는 글 하나를 **1024차원** 벡터로 바꾼다.

**임베딩 모델**은 글 → 벡터 함수다. 같은 모델이면 같은 글은 늘 같은 벡터가 된다. 다른 모델의 벡터끼리는 비교할 수 없다(칸마다 뜻이 다르다). 그래서 모델을 바꾸면 모든 글의 임베딩을 다시 만들어야 한다.

### 3.2 가까움 재기: 코사인

두 벡터 `a`, `b`가 얼마나 같은 방향인지는 **코사인 유사도**로 잰다.

```
cos(a, b) = (a · b) / (|a| × |b|)        a · b = Σ aᵢ × bᵢ (내적), |a| = √(Σ aᵢ²) (길이)
```

- 1이면 같은 방향(아주 비슷), 0이면 직각(관계없음), -1이면 반대.
- 벡터의 **길이를 1로 맞춰 두면**(정규화) 분모가 1이라 코사인 유사도 = 내적이다. bge-m3가 돌려주는 벡터는 이미 길이가 1이었다(직접 확인: `1.0`).

pgvector는 "작을수록 가까운" **거리**로 정렬한다. 코사인 거리 = `1 - 코사인 유사도`. 0이면 같고, 2면 정반대다.

| pgvector 연산자 | 뜻 |
| --- | --- |
| `<->` | 유클리드(L2) 거리 |
| `<#>` | 내적의 음수(정렬용) |
| `<=>` | **코사인 거리** (이 프로젝트) |

### 3.3 낱말 검색과 벡터 검색

| | LIKE·태그 ([32](./32-search-like.md)) | 벡터 검색 |
| --- | --- | --- |
| 무엇을 보나 | 글자가 들어 있나 | 뜻이 가까운가 |
| "스프링"으로 "Spring" 찾기 | 못 함 | 됨 |
| 결과 | 맞다/아니다 | 가까운 순서 |
| 비용 | 싸다 | 글마다 모델 계산이 필요(저장할 때 한 번) |
| 쓰임 | 사용자가 친 검색어 찾기 | 추천, "이런 글은 어때요" |

검색창은 사용자가 원하는 낱말이 정확히 들어간 글을 찾는 게 맞아 LIKE를 그대로 둔다. 추천은 뜻이 비슷한 글이 필요해 임베딩을 쓴다.

### 3.4 pgvector와 HNSW

**pgvector**는 PostgreSQL 확장이다. `CREATE EXTENSION vector`로 켜면 `vector(n)` 칸 타입과 거리 연산자가 생긴다.

```sql
SELECT post_id FROM post_embedding ORDER BY embedding <=> :나의벡터 LIMIT 30;
```

행이 많아지면 모든 행과 거리를 재는 것이 느리다. **HNSW**(Hierarchical Navigable Small World)는 가까운 벡터끼리 여러 층의 그래프로 이어 두고, 위층에서 크게 건너뛰다 아래층에서 좁혀 가며 찾는 인덱스다. **근사**(approximate)라서 아주 드물게 진짜 가장 가까운 것을 놓칠 수 있지만, 훨씬 빠르다. 추천에는 그 정도 오차가 문제되지 않는다.

```sql
CREATE INDEX ... ON post_embedding USING hnsw (embedding vector_cosine_ops);
```

`vector_cosine_ops`는 "코사인 거리로 찾는 인덱스"라는 뜻이다. 쿼리의 연산자(`<=>`)와 맞아야 인덱스를 쓴다. 행이 적으면 PostgreSQL이 인덱스 대신 전부 읽는 편을 고르기도 한다.

왜 MySQL이 아니라 PostgreSQL인가: 이 프로젝트를 설계할 때(research R-02) 벡터 검색은 pgvector로 하기로 정했다. 주 데이터는 MySQL 하나로 두고, PostgreSQL에는 글 번호와 임베딩만 둔다. 추천은 도전 과제라 일정이 밀리면 기능째 뺄 수 있게 떼어 두려는 뜻이다. 두 DB를 함께 쓰는 법은 [42](./42-second-db-async-events.md).

### 3.5 Ollama와 bge-m3

**Ollama**는 언어·임베딩 모델을 내 컴퓨터에서 돌려 HTTP API로 내주는 프로그램이다. 이 프로젝트는 docker compose의 `ollama` 서비스로 띄우고, 지원이 이미 받아 둔 docker 볼륨(`ollama`)의 모델을 쓴다.

**bge-m3**: 100개가 넘는 언어를 다루는 다국어 임베딩 모델. 한국어·영어가 섞인 글도 같은 공간의 벡터로 바꾼다. 1024차원.

외부 API(Voyage, OpenAI)를 고르지 않은 이유(지원 결정, R-02): API 키와 비용이 없고, **글 내용이 밖으로 나가지 않는다**. 비공개 글도 임베딩을 만들어 둘 수 있다(추천할 때 거른다).

```
POST http://localhost:11434/api/embed
{ "model": "bge-m3", "input": "스프링 시큐리티 필터 체인 정리" }
→ { "embeddings": [[0.0123, -0.0456, ...1024개...]], ... }
```

첫 호출은 모델을 메모리에 올리느라 2초쯤 걸렸고, 그다음은 짧은 글이면 금방이다.

### 3.6 추천에서 볼 수 없는 글 빼기

임베딩 표에는 **모든 발행 글**(비공개·숨긴 글 포함)이 있다. 그래서 가장 가까운 글이 비공개일 수 있다. 헌법 원칙 II(볼 수 없는 글은 추천에서도 빠짐, spec "볼 수 없는 글" 표)를 지키려고:

1. PostgreSQL에서 가까운 순 **후보 30개**를 뽑는다.
2. MySQL에서 그 번호들 중 **보는 사람이 볼 수 있는 글**(`visibleTo(viewerId)`)만 읽는다.
3. 후보 순서대로 줄 세워 `size`개(기본 5)를 돌려준다.

후보를 넉넉히 두는 이유는 인기 글과 같다([35](./35-spring-cache-redis.md) 4.3). 몇 개가 빠져도 5개를 채운다. 두 DB는 조인할 수 없어서(서로 다른 서버) 이렇게 두 번에 나눠 읽는다.

## 4. 동작 원리

```
글 발행·수정 (커밋 뒤, 다른 스레드에서)                                        [42]
  PostEmbeddingService.refresh(postId)
    MySQL에서 글 읽기 → 지웠거나 발행 글이 아니면 임베딩 지움
    글자 = 제목 + "\n" + 본문 글자(content_text) 앞부분, 합쳐 2,000자까지
    Ollama /api/embed → 1024개 숫자
    PostgreSQL: INSERT ... ON CONFLICT (post_id) DO UPDATE    (있으면 바꿈)

글 상세 화면 → GET /api/posts/12/similar?size=5
  SimilarPostController: size 1~10 아니면 400
  SimilarPostService.similar
    ① 12번 글을 볼 수 있나(PostReadService.readable): 아니면 404·403
    ② PostgreSQL: 12번의 임베딩과 가까운 다른 글 30개 (<=>)         없으면 빈 목록
    ③ MySQL: 그중 보는 사람이 볼 수 있는 글 (visibleTo + id IN (...))
    ④ ②의 순서대로 5개
  ← PostSummary[] (다른 블로그 글 포함)
```

## 5. 이 프로젝트에서는

### 5.1 표: `src/main/resources/db/recommend/V1__post_embedding.sql`

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE post_embedding (
    post_id    BIGINT PRIMARY KEY,
    embedding  vector(1024) NOT NULL,   -- Ollama bge-m3는 1024차원
    updated_at TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX idx_post_embedding_embedding ON post_embedding USING hnsw (embedding vector_cosine_ops);
```

- `post_id`는 MySQL `post.id`다. 서로 다른 DB라 **외래 키를 걸 수 없다.** 글을 지우면 애플리케이션이 이 행도 지운다(5.3).
- `vector(1024)`: 차원을 정해 둔다. 다른 차원의 벡터를 넣으면 오류다. 모델을 바꾸면 이 숫자도 바뀐다.

### 5.2 `recommend/application/OllamaEmbeddingClient.java`

```java
@Override
public float[] embed(String text) {
    EmbedResponse response = restClient.post()
            .uri("/api/embed")
            .contentType(MediaType.APPLICATION_JSON)
            .body(new EmbedRequest(model, text))
            .retrieve()
            .body(EmbedResponse.class);
    if (response == null || response.embeddings() == null || response.embeddings().isEmpty()) {
        throw new IllegalStateException("Ollama가 임베딩을 돌려주지 않았습니다");
    }
    List<Double> values = response.embeddings().getFirst();
    ...
}

record EmbedRequest(String model, String input) {
}

record EmbedResponse(List<List<Double>> embeddings) {
}
```

- `RestClient`: Spring 6.1부터 있는 HTTP 클라이언트. 요청을 이어서 쓰고(`post().uri().body().retrieve()`), JSON은 Jackson이 레코드와 바꿔 준다.
- `EmbedRequest`·`EmbedResponse`: Ollama의 JSON 모양 그대로인 레코드. `embeddings`가 2중 목록인 이유는 `input`에 여러 글을 한 번에 보낼 수도 있어서다. 하나만 보내므로 첫 번째만 쓴다.
- 생성자에서 연결·읽기 제한 시간(`app.recommend.timeout`, 30초)을 준다. Ollama가 멈추면 스레드가 무한히 기다리지 않는다.
- `EmbeddingClient`는 인터페이스다. 테스트는 이 자리에 가짜를 넣는다(5.6). 나중에 외부 API로 바꿔도 이 클래스만 바꾸면 된다.

### 5.3 `recommend/domain/PostEmbeddingRepository.java`

```java
public void save(long postId, float[] embedding) {
    jdbc.update("""
            INSERT INTO post_embedding (post_id, embedding, updated_at)
            VALUES (:postId, CAST(:embedding AS vector), now())
            ON CONFLICT (post_id) DO UPDATE SET embedding = EXCLUDED.embedding, updated_at = now()
            """, Map.of("postId", postId, "embedding", toLiteral(embedding)));
}

public List<Long> findNearest(long postId, int limit) {
    return jdbc.queryForList("""
            SELECT other.post_id
            FROM post_embedding me
            JOIN post_embedding other ON other.post_id <> me.post_id
            WHERE me.post_id = :postId
            ORDER BY other.embedding <=> me.embedding, other.post_id DESC
            LIMIT :limit
            """, new MapSqlParameterSource().addValue("postId", postId).addValue("limit", limit), Long.class);
}
```

- JPA는 주 DB(MySQL)만 쓴다. 이 표는 JDBC로 SQL을 그대로 쓴다(`NamedParameterJdbcTemplate`, [36](./36-ranking-aggregation.md) 3.5와 같은 방식).
- 벡터를 `'[0.1,0.2,…]'` 글자로 보내고 `CAST(... AS vector)`로 바꾼다(`toLiteral`). pgvector 전용 자바 라이브러리를 쓰지 않으려고 이렇게 했다.
- `ON CONFLICT (post_id) DO UPDATE`: PostgreSQL의 "있으면 바꾸고 없으면 넣기"(upsert). 글을 고쳐 다시 만들 때 같은 메서드를 쓴다. `EXCLUDED`는 넣으려던 새 값이다.
- `findNearest`: 이 글(`me`)의 벡터와 다른 글(`other`)의 거리 순. 자기 자신은 `other.post_id <> me.post_id`로 뺀다. 이 글의 임베딩이 없으면 `me`가 없어 결과가 비고, 그래서 추천이 빈 배열이 된다. 같은 거리면 최근 글(번호 큰 것)을 먼저 둬서 순서를 하나로 정한다.

### 5.4 `recommend/application/SimilarPostService.java`

```java
@Transactional(readOnly = true)
public List<Post> similar(Blog blog, Long postId, Long viewerId, int size) {
    postReadService.readable(blog, postId, viewerId);
    List<Long> nearest = nearest(postId);
    if (nearest.isEmpty()) {
        return List.of();
    }
    Specification<Post> condition = PostSpecifications.visibleTo(viewerId, LocalDateTime.now(clock))
            .and((root, query, cb) -> root.get("id").in(nearest));
    Map<Long, Post> visible = postRepository.findBy(condition, query -> query.project("blog", "category").all())
            .stream()
            .collect(Collectors.toMap(Post::getId, Function.identity()));
    return nearest.stream()
            .map(visible::get)
            .filter(Objects::nonNull)
            .limit(size)
            .toList();
}

private List<Long> nearest(Long postId) {
    try {
        return postEmbeddingRepository.findNearest(postId, CANDIDATES);
    } catch (DataAccessException e) {
        log.warn("비슷한 글 후보를 읽지 못했습니다(추천 DB): {}", e.toString());
        return List.of();
    }
}
```

- `readable`: 원래 글을 볼 수 없으면 추천도 404·403(글 상세와 같은 판단). 남의 비공개 글 번호로 "비슷한 글"을 물어 그 글이 무엇에 관한 것인지 짐작하는 길을 막는다.
- `visibleTo(viewerId)`: **보는 사람 기준**이다. 구독자 공개 글은 구독자에게만 추천된다. 인기 글(모두에게 같은 공개 글, 비회원 기준)과 다른 점이다. 추천은 캐시하지 않으므로 사람마다 달라도 된다.
- 블로그 조건이 없다. **다른 블로그의 글도** 추천한다(contracts "다른 블로그 포함").
- 결과 순서는 MySQL이 돌려준 순서가 아니라 `nearest`(가까운 순)다. `Map`에 넣고 후보 순서대로 다시 꺼낸다(인기 글과 같은 요령).
- 추천 DB에 닿지 않으면(`DataAccessException`) 경고만 남기고 빈 목록. 추천은 부가 기능이라 글 상세 화면을 깨뜨리지 않는다.

### 5.5 `recommend/presentation/SimilarPostController.java`

`GET /api/posts/{id}/similar?size=5`. `size`가 없으면 5, 1~10을 벗어나면 400(`fieldErrors[].field = size`). 응답은 목록과 같은 `PostSummary[]`이고, 각 글의 블로그 주소를 함께 준다(다른 블로그 글일 수 있어서).

### 5.6 화면: `frontend/src/components/SimilarPosts.tsx`

```tsx
if (posts.length === 0) {
  return null
}
return (
  <section className="section" aria-label="비슷한 글">
    <h2>비슷한 글</h2>
    <div className="grid-cards">
      {posts.map((post) => (
        <a key={post.id} className="card" href={blogUrl(post.blog.address, `/${post.id}`)}>
          ...
```

- 목업(post-detail)대로 이전·다음 글과 댓글 사이에 카드로 둔다. 카드 모양(`grid-cards`, `card`)은 홈 주제별 글과 같다.
- 빈 배열이면 **영역을 통째로 숨긴다**(목업 "빈 배열이면 섹션 숨김"). 추천이 아직 준비 안 됐을 때(임베딩을 만드는 중, Ollama가 꺼짐) "비슷한 글 없음"이 덩그러니 보이지 않게.
- 다른 블로그 글일 수 있어 `<Link>`가 아니라 `<a href>`로 그 블로그 주소를 연다([19](./19-react-router-api-client.md)).
- `key={`similar-${post.id}`}`로 글이 바뀌면 컴포넌트를 새로 만든다(이전·다음 글로 옮겨 가도 앞 글의 추천이 남지 않게, [25](./25-react-forms-data.md)).

### 5.7 가짜 임베딩으로 테스트: `TestRecommendConfiguration`

진짜 모델로 테스트하면 Ollama를 띄워야 하고, 느리고, 결과가 모델에 따라 조금씩 다르다. 테스트에는 **뜻이 아니라 낱말로 가까워지는** 가짜를 쓴다.

```java
public static float[] bagOfWords(String text) {
    float[] vector = new float[DIMENSIONS];
    for (String word : text.toLowerCase(Locale.ROOT).split("[^\\p{L}\\p{N}]+")) {
        if (!word.isEmpty()) {
            vector[Math.floorMod(word.hashCode(), DIMENSIONS)] += 1;
        }
    }
    ... 길이 1로 맞춤
}
```

- **낱말 주머니(bag of words)**: 낱말마다 해시로 칸 하나를 골라 1을 더한다. 겹치는 낱말이 많을수록 같은 칸이 커져 코사인이 커진다. 1024차원이라 표(`vector(1024)`)에 그대로 들어간다.
- `@Primary`로 등록해 진짜 `OllamaEmbeddingClient` 대신 주입된다. 테스트는 "가까운 순, 비공개 제외, 다른 블로그 포함" 같은 **우리 코드의 규칙**을 확인하는 것이지, 모델의 품질을 시험하는 게 아니다. 모델 품질은 2장처럼 직접 재 봤다.
- `SimilarPostIntegrationTest`는 낱말에 테스트마다 다른 표식(`mark`)을 붙인다. 테스트끼리 DB를 같이 쓰므로([05](./05-spring-testing.md) 5.7) 다른 테스트의 글과 가까워지지 않게 하려는 것이다.

| 테스트 | 확인하는 것 |
| --- | --- |
| `closestVisiblePostsFirstIncludingOtherBlogs` | 가장 비슷한 비공개 글과 자기 글은 빠짐, 다른 블로그 글 포함, 가까운 글이 먼 글보다 앞, `size=1`이면 1개 |
| `sizeMustBeOneToTen` | `size` 0·11은 400 |
| `invisibleSourcePostIsNotFoundAndMissingEmbeddingGivesEmptyList` | 비공개 원글 404, 임베딩이 없으면 빈 배열 |

## 6. 자주 하는 실수와 함정

- **임베딩 표의 결과를 그대로 보여 준다.** 비공개·숨긴 글이 추천에 나온다. 가시성으로 다시 거른다.
- **후보를 딱 size개만 뽑는다.** 몇 개가 걸러지면 모자란다. 넉넉히 뽑는다.
- **모델을 바꾸고 예전 임베딩을 그대로 둔다.** 다른 모델의 벡터끼리는 비교가 안 된다. 모두 다시 만든다(차원도 바뀔 수 있다).
- **거리 연산자와 인덱스 종류가 다르다.** `<=>`(코사인)로 찾는데 인덱스는 `vector_l2_ops`면 인덱스를 못 쓴다.
- **정규화를 생각하지 않는다.** 길이가 다른 벡터에 내적을 쓰면 긴 글이 무조건 가깝게 나올 수 있다. 코사인을 쓰거나 길이를 1로 맞춘다.
- **임베딩을 요청 안에서 만든다.** 글 저장이 모델 계산(수백 ms~수 초)을 기다린다. 커밋 뒤 비동기로([42](./42-second-db-async-events.md)).
- **추천 실패가 글 상세를 깨뜨린다.** 추천 DB·모델이 꺼져도 빈 배열로 넘어간다.
- **테스트에 진짜 모델을 쓴다.** 느리고 결과가 흔들린다. 우리 규칙은 가짜로, 모델 품질은 따로 잰다.
- **글 전체를 통째로 넣는다.** 모델 입력 길이를 넘거나 느려진다. 앞부분(제목 + 2,000자)만 넣는다.

## 7. 직접 해 보기

준비: `docker compose up -d`(postgres, ollama 포함), 코드 저장소 루트에서 `./scripts/build-frontend.sh && ./mvnw spring-boot:run`.

### 7.1 임베딩 직접 만들어 보기

```bash
curl -s localhost:11434/api/embed -d '{"model":"bge-m3","input":"스프링 시큐리티 필터 체인 정리"}' \
  | python3 -c "import sys,json,math; v=json.load(sys.stdin)['embeddings'][0]; print(len(v), round(math.sqrt(sum(x*x for x in v)),4))"
# 1024 1.0   (1024차원, 길이 1)
```

두 문장의 코사인 유사도를 재 본다(2장의 표처럼). 비슷한 뜻, 같은 낱말이 많은 다른 뜻, 전혀 다른 뜻을 견주어 본다.

### 7.2 저장된 임베딩 보기

```bash
docker exec -it blog-postgres psql -U blog -d recommend
```

```sql
SELECT post_id, updated_at, vector_dims(embedding) FROM post_embedding ORDER BY post_id;
-- 1번 글과 가까운 순
SELECT other.post_id, round((other.embedding <=> me.embedding)::numeric, 3) AS distance
FROM post_embedding me JOIN post_embedding other ON other.post_id <> me.post_id
WHERE me.post_id = 1 ORDER BY distance LIMIT 5;
```

### 7.3 API와 화면

```bash
curl -s -H "Host: {주소}.blog.test" "localhost:8080/api/posts/{글번호}/similar?size=5" | python3 -m json.tool
```

스텝 10을 만들며 개발 DB로 돌려 보니, 서버가 뜰 때 발행 글 12개의 임베딩이 채워지고, 비공개인 글은 추천에서 빠졌다. 글 상세 화면 아래에 "비슷한 글" 카드가 보인다. Ollama를 끄고(`docker stop blog-ollama`) 새 글을 써 보자. 임베딩을 만들지 못하므로(서버 로그에 경고) 그 글에는 비슷한 글 영역이 보이지 않아야 한다(빈 배열). 다시 켜고 서버를 다시 띄우면 시작할 때 빠진 임베딩을 채운다.

### 7.4 테스트

```bash
./mvnw test -Dtest='SimilarPostIntegrationTest,PostEmbeddingIntegrationTest,PostEmbeddingServiceTest'
```

## 8. 확인 문제

1. 임베딩으로 비슷한 글을 찾으면 LIKE·태그로 찾을 때보다 나은 점은?
<details><summary>답</summary>글자가 아니라 뜻이 가까운 글을 찾는다. "Spring Security"와 "스프링 시큐리티로 로그인 토큰 검증"처럼 겹치는 낱말이 없어도 가깝게 나온다.</details>

2. 코사인 유사도와 코사인 거리의 관계, pgvector에서 코사인 거리 연산자는?
<details><summary>답</summary>코사인 거리 = 1 - 코사인 유사도. 작을수록 비슷하다. 연산자는 &lt;=&gt;.</details>

3. 벡터 길이를 1로 맞추면(정규화) 무엇이 좋은가?
<details><summary>답</summary>코사인 유사도의 분모가 1이 되어 내적과 같아진다. 글 길이처럼 벡터 크기에 영향을 주는 요소가 비교를 흔들지 않는다.</details>

4. HNSW 인덱스가 하는 일과, "근사"라는 말의 뜻은?
<details><summary>답</summary>가까운 벡터끼리 여러 층의 그래프로 이어 두어 모든 행과 거리를 재지 않고 가까운 것을 빨리 찾는다. 근사라서 아주 드물게 진짜 가장 가까운 것을 놓칠 수 있다. 추천에는 그 정도 오차가 괜찮다.</details>

5. 임베딩 표에 비공개 글도 넣어 두는데 추천에 나오지 않는 이유는?
<details><summary>답</summary>PostgreSQL에서 후보 30개를 뽑은 뒤 MySQL에서 보는 사람이 볼 수 있는 글(visibleTo)만 남기기 때문이다. 두 DB는 조인할 수 없어 두 번에 나눠 읽는다.</details>

6. 추천 후보를 size(5)개가 아니라 30개 뽑는 이유는?
<details><summary>답</summary>볼 수 없는 글이 걸러져도 size개를 채우기 위해서다.</details>

7. 원래 글을 볼 수 없으면 추천도 404인 이유는?
<details><summary>답</summary>남의 비공개 글 번호로 비슷한 글을 물어 그 글의 주제를 짐작하는 길을 막는다. 글 상세와 같은 가시성 판단을 쓴다.</details>

8. 인기 글은 비회원 기준으로, 비슷한 글은 보는 사람 기준으로 거르는 이유는?
<details><summary>답</summary>인기 글은 순위를 캐시해 모두에게 같은 "공개 글" 목록을 준다. 비슷한 글은 캐시하지 않고 요청마다 계산하므로 보는 사람에 맞춰(구독자 공개 글 등) 거를 수 있다.</details>

9. 테스트에 진짜 bge-m3 대신 가짜(낱말 주머니)를 쓰는 이유와, 그래도 확인되는 것은?
<details><summary>답</summary>Ollama 없이 빠르고 결과가 늘 같다. 가까운 순 정렬, 비공개·자기 글 제외, 다른 블로그 포함, size 처리 같은 우리 코드의 규칙을 확인한다. 모델 품질은 따로 재 본다.</details>

10. 모델을 다른 것으로 바꾸면 무엇을 해야 하나?
<details><summary>답</summary>모든 글의 임베딩을 새 모델로 다시 만든다. 다른 모델의 벡터끼리는 비교할 수 없다. 차원이 다르면 표의 vector(n)도 바꾼다.</details>

## 9. 더 읽을거리

- pgvector README: 거리 연산자, HNSW·IVFFlat 인덱스, `vector_cosine_ops`
- Ollama API 문서, "Generate Embeddings"(`/api/embed`)
- BGE-M3 모델 카드(다국어·다기능 임베딩)
- Yu. A. Malkov, D. A. Yashunin, "Efficient and robust approximate nearest neighbor search using Hierarchical Navigable Small World graphs"
- 정보 검색 교과서의 벡터 공간 모델, TF-IDF와 코사인 유사도(낱말 주머니가 어디서 왔는지)
- 하이브리드 검색: LIKE·전문 검색과 벡터 검색을 섞기
