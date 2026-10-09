# 스텝 10. 비슷한 글 추천

> 작업: T069a, T069b, T069c, T069d · 코드 브랜치: `step-10-recommend` · 날짜: 2026-10-10

## 한눈에 보기

글 내용을 임베딩(뜻을 담은 숫자 벡터)으로 바꿔 PostgreSQL(pgvector)에 두고, 글 상세 아래에 내용이 비슷한 글을 보여 준다. 임베딩은 내 컴퓨터의 Ollama + bge-m3로 만든다.

| 작업 | 만든 것 | 핵심 파일 |
| --- | --- | --- |
| T069a | docker compose에 PostgreSQL(pgvector)·Ollama(이미 받아 둔 `ollama` 볼륨), 두 번째 DataSource, 추천 DB 전용 Flyway(`db/recommend`), 테스트용 pgvector 컨테이너 | `docker-compose.yml`, `recommend/config/RecommendDataSourceConfig`, `RecommendProperties`, `db/recommend/V1__post_embedding.sql`, `TestcontainersConfiguration` |
| T069b | 발행·수정이 커밋된 뒤 비동기로 임베딩을 만들어 저장, 삭제하면 지움, 서버 시작 때 빠진 글 채우기, 실패는 경고만 | `post/application/PostContentChangedEvent`·`PostDeletedEvent`, `recommend/application/PostEmbeddingListener`·`PostEmbeddingService`·`OllamaEmbeddingClient`, `recommend/domain/PostEmbeddingRepository`, `global/config/AsyncConfig` |
| T069c | `GET /api/posts/{id}/similar?size=5` → `PostSummary[]`. 코사인 거리 후보 30개를 보는 사람 기준 가시성으로 거름, 다른 블로그 포함, 준비 안 됐으면 빈 배열 | `recommend/application/SimilarPostService`, `recommend/presentation/SimilarPostController` |
| T069d | 글 상세의 이전·다음 글과 댓글 사이에 "비슷한 글" 카드, 빈 배열이면 숨김 | `frontend/src/components/SimilarPosts.tsx`, `pages/post/PostPage.tsx` |
| 테스트 | 가짜 임베딩(낱말 주머니)으로 규칙 확인 | `TestRecommendConfiguration`, `PostEmbeddingIntegrationTest`, `PostEmbeddingServiceTest`, `SimilarPostIntegrationTest` |

**지원이 정한 것 (2026-10-10, research R-02)**: 임베딩은 로컬 **Ollama + bge-m3**(1024차원, 다국어). 지원의 docker `ollama` 볼륨에 모델이 이미 있었다. 외부 API(Voyage·OpenAI)는 키·비용과 글이 밖으로 나가는 점 때문에 고르지 않았다. 나머지(넣는 글자 제목+본문 2,000자, 발행 글 모두 임베딩하고 추천할 때 거르기, 커밋 뒤 비동기, 후보 30개, size 1~10)는 Claude가 정해 R-02에 적었다.

## 요청 흐름

```
글 발행 POST /api/posts
  PostService.publish [트랜잭션] → 저장 → PostContentChangedEvent 발행(보류)
  [커밋] → 201 응답 (임베딩을 기다리지 않음)
     └─(다른 스레드) PostEmbeddingListener → PostEmbeddingService.refresh
           MySQL에서 글 읽기 → Ollama /api/embed(bge-m3) → PostgreSQL post_embedding upsert

글 상세 GET /api/posts/12  →  화면이 이어서 GET /api/posts/12/similar?size=5
  SimilarPostService
    12번을 볼 수 있나(404·403)
    PostgreSQL: 12번과 코사인 거리(<=>) 가까운 다른 글 30개
    MySQL: 그중 보는 사람이 볼 수 있는 글(visibleTo)
    가까운 순 5개 → 카드 (빈 배열이면 영역 숨김)
```

## 이 스텝을 이해하려면 (읽는 순서)

| 순서 | 개념 문서 | 이 스텝에서 쓰인 곳 |
| --- | --- | --- |
| 1 | [41 임베딩과 벡터 검색](./concepts/41-embedding-vector-search.md) | 임베딩·코사인·pgvector·HNSW·Ollama, 추천에서 볼 수 없는 글 거르기, 가짜 임베딩 테스트, 화면 |
| 2 | [42 두 번째 DB와 커밋 뒤 비동기 처리](./concepts/42-second-db-async-events.md) | `defaultCandidate = false` DataSource, 추천 DB Flyway, 이벤트·`@TransactionalEventListener`·`@Async`, sync, 테스트 컨테이너 |

먼저 알고 있으면 좋은 문서: [16 인가와 가시성](./concepts/16-authorization-visibility.md), [35 캐시](./concepts/35-spring-cache-redis.md)(후보를 넉넉히 두고 읽을 때 가시성 확인, 프록시 함정), [23 트랜잭션](./concepts/23-transactions-locking.md), [05 Spring 테스트](./concepts/05-spring-testing.md).

## 막혔던 점

- **임베딩 방법이 정해져 있지 않았다**: tasks.md가 "시작 전에 정한다(R-02 미결정)"였다. 선택지를 물었더니 지원이 "ollama 모델이 받아져 있을 것"이라고 했다. Mac에 Ollama 앱은 없었지만 docker `ollama` 볼륨에 `bge-m3`가 있어, compose가 그 볼륨을 쓰게 했다(`external: true`).
- **실제 모델이 생각한 모양인지**: 코드를 짜기 전에 `/api/embed`를 직접 불러 1024차원, 길이 1.0인 것을 확인했고, 보안 글끼리(0.58)가 보안·여행(0.35)보다 가까운 것도 재 봤다.
- **DB 두 개와 자동 설정**: DataSource를 하나 더 만들면 주 DB 자동 설정이 멈춘다. `@Bean(defaultCandidate = false)` + `@Qualifier`로 피했고, 테스트 로그에서 MySQL 마이그레이션 3개와 추천 DB 마이그레이션 1개가 따로 적용되는 것을 확인했다.
- **테스트에서 비동기 기다리기**: 임베딩이 다른 스레드에서 만들어져 바로 확인할 수 없다. 조건이 맞을 때까지 50ms씩 돌며 최대 5초 기다리는 `await`를 썼다.
- **처음 테스트가 느림**: pgvector 이미지를 받느라 첫 실행이 32초 걸렸다. 그다음부터는 평소 속도.

## 명세와 다르거나 아직 채우지 않은 것

| 항목 | 지금 | 언제 |
| --- | --- | --- |
| 글 주인이 자기 비공개 글을 볼 때 추천 | 보는 사람 기준 `visibleTo`라 주인의 비공개 글도 추천에 나오지 않는다 | 필요하면 |
| 글이 아주 많을 때 sync | 발행 글 번호 전부를 읽어 비교한다 | 글이 많아지면 나눠 읽기 |
| 같은 카테고리 다른 글(OWN-05, 목업의 같은 자리) | 없음 | 백로그 |
| 운영 | `RECOMMEND_DB_URL` 등 환경 변수와 Ollama 서버 필요 | 배포 때 |

## 직접 해 보기

```bash
docker compose up -d                     # mysql, redis, postgres, ollama
./mvnw test -Dtest='SimilarPostIntegrationTest,PostEmbeddingIntegrationTest,PostEmbeddingServiceTest'
```

브라우저로(코드 저장소 맨 위 폴더에서 `./scripts/build-frontend.sh && ./mvnw spring-boot:run`):

1. 서버가 뜨면 이미 있던 발행 글의 임베딩이 채워진다: `docker exec blog-postgres psql -U blog -d recommend -tAc "select count(*) from post_embedding"`.
2. 비슷한 주제의 글 두세 개와 다른 주제의 글을 쓰고, 한 글을 열어 아래 "비슷한 글"에 비슷한 주제가 먼저 오는지 본다.
3. 그중 하나를 비공개로 바꾸고 시크릿 창(비회원)에서 다시 열면 추천에서 빠진다.

```bash
curl -s -H "Host: {주소}.blog.test" "localhost:8080/api/posts/{글번호}/similar?size=5" | python3 -m json.tool
```

스텝 10을 만들며 8081 확인 서버로 돌려 보니, 개발 DB의 발행 글 12개가 서버 시작 때 진짜 bge-m3로 임베딩되었고, 1번 글의 추천 5개에 비공개인 4번 글은 없었다.
