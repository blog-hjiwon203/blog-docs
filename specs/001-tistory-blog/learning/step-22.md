# 스텝 22. 의미 검색

> 작업: T120, T121, T122 · 코드 브랜치: `step-22-semantic-search` · 날짜: 2026-10-13 · 결정: research.md R-02(의미 검색), spec OWN-07, 2026-10-13 지원 결정

## 한눈에 보기

검색 화면에 **"글자로 찾기 | 의미로 찾기"** 탭을 더했다. 의미로 찾기는 비슷한 글 추천(스텝 10)이 만들어 둔 글 임베딩(PostgreSQL pgvector)으로, 검색어와 **뜻이 가까운 글**을 가까운 순으로 보여 준다. "자바 공부"로 "스프링 부트 입문기"를 찾는 식이다. 전체 검색과 블로그 안 검색 모두에 있다.

결정 세 가지(2026-10-13 지원 결정):

- 주 DB(MySQL)와 추천 DB(PostgreSQL)를 **합치지 않고** 지금 구조로 만든다. 합칠지는 이 기능을 써 본 뒤 정한다([65](./concepts/65-postgresql-vs-mysql.md)).
- 화면은 **탭으로 나눈다.** 두 결과를 점수로 섞지 않는다(RRF는 고르지 않음).
- 임베딩에 넣는 글자에 **태그를 더한다.** 이미 있는 임베딩은 서버가 뜰 때 다시 만든다.

| 작업 | 만든 것 | 핵심 파일 |
| --- | --- | --- |
| T120 임베딩 글자에 태그 | 넣는 글자를 `제목\n태그: a, b\n본문 글자` 앞 2,000자로. 표에 `text_version` 칸(옛 방식 1, 지금 2)을 더하고, 서버 시작 때 `sync()`가 버전이 다른 임베딩을 다시 만든다. 태그 이름 바꾸기·지우기 때 그 태그가 달린 글마다 `PostContentChangedEvent`를 보낸다 | `recommend/application/PostEmbeddingService`, `recommend/domain/PostEmbeddingRepository`, `db/recommend/V2__post_embedding_text_version.sql`, `post/domain/PostRepository.findTagNames`, `tag/domain/TagRepository.findPostIdsByTagId`, `tag/application/TagManageService` |
| T121 의미 검색 API | `GET /api/search?mode=semantic`. 검색어 임베딩(Redis 캐시 5분) → 유사도 0.40 이상 가까운 순 100개 → 가시성으로 거르기 → 10개씩. 블로그 안은 MySQL에서 볼 수 있는 글 번호를 먼저 읽어 그 안에서만. 응답 `[{ post, similarity }]`. 추천을 껐거나 Ollama·추천 DB에 닿지 않으면 503 `SEMANTIC_SEARCH_UNAVAILABLE`. 추천 DB 연결마다 `SET hnsw.ef_search = 200` | `search/application/SemanticSearchService`, `QueryEmbeddings`, `SemanticSearchProperties`, `SemanticHit`, `search/presentation/SearchController`, `dto/SemanticSearchResponse`, `recommend/domain/NearPost`, `recommend/config/RecommendDataSourceConfig`, `post/domain/PostCountRepository.findIds`, `global/error/ErrorCode`, `application.yml`(`app.search.semantic`) |
| T122 화면 | 검색 방식 탭(주소 `?mode=semantic`), 글 줄에 "가까움 0.58", 의미로 찾기에서는 글/블로그 탭 숨김, 결과 없음·쓸 수 없음 안내 | `frontend/src/components/SearchModeTabs.tsx`, `app/searchMode.ts`, `pages/search/GlobalSearchPage.tsx`, `BlogSearchPage.tsx`, `components/PlatformPostItem.tsx`, `PostItem.tsx`, `api/types.ts`(`SemanticHit`) |

## 요청 흐름

```
[화면] /search?q=자바 공부&mode=semantic   (블로그 화면이면 /@alpha/search?...)
  → GET /api/search?q=자바 공부&mode=semantic&page=1     (블로그면 X-Blog-Address: alpha)
[SearchController] mode 검사 → 블로그 헤더 있음: search(blog) / 없음: searchAll
[SemanticSearchService]
  검색어 정리(빈 값 400 q) → (블로그 안) MySQL listedIn 글 번호
  → QueryEmbeddings.embed  ── Redis blog:semanticQuery::자바 공부, 없으면 Ollama bge-m3
  → PostgreSQL: 거리 <= 0.60 [AND post_id IN (…)] ORDER BY 거리 LIMIT 100
  → MySQL: visibleTo / listedIn + id IN (…)  → PostgreSQL 순서대로 → page번째 10개
  ← 200 { content: [{ post: PostSummary, similarity: 0.58 }], totalElements, … }
  (부품 없음·Ollama·추천 DB 오류 → 503 SEMANTIC_SEARCH_UNAVAILABLE)

[글 쪽] 글 저장·태그 이름 바꾸기·지우기 → (커밋 뒤 비동기) PostEmbeddingService.refresh
  → "제목\n태그: …\n본문" → Ollama → post_embedding(text_version = 2)
[서버 시작] sync: 임베딩 없거나 text_version ≠ 2인 발행 글을 다시 만듦
```

## 이 스텝을 이해하려면 (읽는 순서)

| 순서 | 개념 문서 | 이 스텝에서 쓰인 곳 |
| --- | --- | --- |
| 1 | (복습) [41 임베딩과 벡터 검색](./concepts/41-embedding-vector-search.md) 3장 | 임베딩, 코사인 유사도·거리, pgvector와 HNSW, 비슷한 글 추천에서 볼 수 없는 글 빼기 |
| 2 | (복습) [42 두 번째 DB와 비동기 이벤트](./concepts/42-second-db-async-events.md) | `@TransactionalEventListener` + `@Async`: 태그 이름을 바꿀 때도 같은 이벤트를 쓴다 |
| 3 | [66 의미 검색](./concepts/66-semantic-search.md) (새 문서) | 이 스텝 전부: 기준값을 재서 정하기, 뽑고 → 거르고 → 자르기, 블로그 안은 범위 먼저, `ef_search`, 캐시, `text_version`, 503 |
| 4 | (복습) [35 Spring Cache와 Redis](./concepts/35-spring-cache-redis.md), [52 스케줄 작업과 프록시](./concepts/52-scheduled-jobs-proxy.md) | `@Cacheable`은 프록시가 건다 → 캐시 메서드를 `QueryEmbeddings`로 따로 둔 이유 |
| 5 | (복습) [32 글자 검색](./concepts/32-search-like.md) | 글자 검색과 같은 가시성(`visibleTo`, `listedIn`), 검색어 정리(`normalize`) |
| 6 | (참고) [65 PostgreSQL vs MySQL](./concepts/65-postgresql-vs-mysql.md) | DB가 하나라면 뽑기와 거르기를 SQL 한 번에. 이번에 합치지 않은 이유 |

## 막혔던 점

- **기준값을 몇으로 할지**: bge-m3의 유사도는 0.2~0.6에 몰려 있어 "얼마면 관련 있다"가 뻔하지 않았다. 개발 Ollama로 글 6개 × 검색어 9개를 재 보니 관련 있는 글 0.42~0.58, 관련 없는 글 0.21~0.39라 0.40으로 정했다(개념 66 3.3의 표). 경계가 깔끔하지 않아 설정값으로 두었다.
- **개발 DB로 본 실제 결과는 거칠었다**: 확인용 서버(8081)에서 개발 DB 글 26개로 검색해 보니, "자바 공부"에 "JPA N+1과 fetch join"(0.44)과 함께 "제주 3박 4일 동선"(0.43)도 나왔다. 개발 글이 대부분 "스텝 5 확인 글" 같은 짧은 시험 글이라 뜻이 약하다. 운영에 진짜 글이 쌓이면 다시 재서 기준값을 고친다.
- **2쪽이 비었다(테스트가 잡음)**: 처음에 `PageRequest.of(page.page(), page.size())`로 썼다. 이 프로젝트의 `PageQuery`는 1부터라 한 쪽씩 밀렸다. `page=2&size=1` 테스트가 실패해 `page.toPageable(Sort.unsorted())`로 고쳤다.
- **HNSW가 40개만 준다**: pgvector 문서를 다시 읽다 `hnsw.ef_search` 기본값 40을 봤다. 비슷한 글 추천(30개)은 괜찮았지만 의미 검색은 100개까지 본다. 개발 DB는 글이 적어 인덱스를 안 쓰므로 드러나지 않는 문제라, 연결마다 200으로 올렸다(`connectionInitSql`).
- **비동기 스레드에서 태그 읽기**: `post.tagNames()`는 지연 로딩이라 트랜잭션 없는 비동기 스레드에서 부르면 예외가 난다(그리고 `refresh`가 예외를 경고로만 남겨 조용히 실패한다). 태그 이름을 쿼리 하나(`findTagNames`)로 읽었다.
- **가짜 임베딩의 해시 충돌**: 테스트의 가짜 임베딩은 낱말을 해시로 1,024칸에 넣는다. 테스트 낱말끼리 같은 칸이면 계산한 유사도가 어긋나고, 다른 테스트 글의 낱말과 칸이 겹치면 전체 검색에 남의 글이 섞일 수 있다. 낱말끼리 칸이 겹치지 않는 표식을 고르고(`distinctMark`), 전체 검색은 이 테스트의 글만 골라 순서를 본다. CI에서 가끔 실패하는 테스트를 만들지 않으려고 했다.
- **JsonPath 필터는 배열을 돌려준다**: `$.content[?(@.post.id == 12)].similarity`는 값 하나가 아니라 배열이다. `List`로 받아 첫 값을 쓴다.
- **실제 서버(8081)에서 확인한 것**: 서버가 뜨자 개발 DB 발행 글 26개가 모두 `text_version = 2`로 다시 만들어졌다. 같은 검색어의 첫 요청 0.86초, 두 번째 0.03초(Redis에 `blog:semanticQuery::…` 키). `mode=vector`는 400 `mode`. 배포용 화면 파일에 "의미로 찾기"가 들어 있다.
- **브라우저로 눌러 보는 확인은 못 했다**: 이번에도 브라우저 도구가 없어 탭을 실제로 눌러 보지 않았다. 프론트 단위 테스트(`searchMode.test.ts`)와 타입 검사, 빌드로 확인했다.
- **전체 테스트**: 백엔드 `./mvnw test` 409개, 프론트 `npx vitest run` 86개 통과. `tsc -b`, `oxlint`, `vite build` 통과.

## 명세와 다르거나 아직 채우지 않은 것

- **결과가 100개보다 적을 수 있다**: 가까운 100개를 뽑은 뒤 볼 수 없는 글을 빼므로, 비공개 글이 많으면 결과가 줄어든다. 의미 검색은 앞쪽 결과만 쓸모 있다고 보고 받아들였다(R-02).
- **블로그 안 검색의 `IN (…)` 목록**: 블로그의 볼 수 있는 글 번호를 모두 PostgreSQL에 보낸다. 글이 수만 개인 블로그라면 목록이 길어진다. 그 규모가 되면 DB를 합치는 쪽([65](./concepts/65-postgresql-vs-mysql.md))으로 푼다.
- **검색 횟수 제한은 없다**: 검색어마다 Ollama가 계산한다(처음 한 번, 이후 5분 캐시). 운영 Ollama는 CPU 4개·메모리 4GB로 묶어 두었다(2차 배포). 남용이 보이면 IP별 제한을 더한다.
- **운영 배포 때 임베딩을 한 번 다시 만든다**: 운영의 기존 임베딩은 모두 `text_version = 1`이라, 배포 후 서버가 뜰 때 모든 발행 글을 다시 만든다(글 수만큼 Ollama 계산, 몇 초~몇 분). 그동안 아직 안 바뀐 글은 옛 임베딩으로 검색된다.

## 직접 해 보기

1. **API**: `curl -s -G http://localhost:8080/api/search --data-urlencode 'q=자바 공부' -d mode=semantic | python3 -m json.tool | head -30` → `similarity`가 큰 순.
2. **화면**: `http://blog.test:8080/search?q=자바 공부` → "의미로 찾기" → 주소에 `&mode=semantic`, 글마다 "가까움 0.xx". 내 블로그 `/@{주소}/search?q=…`에서도 같은 탭. 주인이면 자기 비공개 글도 나오고, 로그아웃하면 사라진다.
3. **쓸 수 없을 때**: `docker compose stop ollama` → 의미로 찾기 → "지금은 의미 검색을 쓸 수 없습니다. 글자로 찾기를 이용해 주세요." → 글자로 찾기는 된다 → `docker compose start ollama`.
4. **태그**: 관리 화면에서 태그 이름을 바꾸고 `docker compose exec postgres psql -U blog -d recommend -c "select post_id, text_version, updated_at from post_embedding order by updated_at desc limit 5"` → 그 글들의 `updated_at`이 방금.
5. **기준값**: `app.search.semantic.min-similarity`를 0.30·0.50으로 바꿔 같은 검색어의 결과 수를 비교([66](./concepts/66-semantic-search.md) 7.5).
6. **테스트**: `./mvnw test -Dtest='SemanticSearch*,PostEmbedding*,RecommendDisabled*'`
