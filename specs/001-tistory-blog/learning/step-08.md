# 스텝 8. 조회수·인기 글

> 작업: T053, T054, T063 · 코드 브랜치: `step-8-views-popular` · 날짜: 2026-10-09

## 한눈에 보기

글을 열면 조회수가 오르고(같은 사람이 5분 안에 다시 보면 안 셈), 홈에 최근 1시간 조회·공감·댓글로 매긴 인기 글 10개가 보이고, 블로그 사이드바에 태그 목록과 글 수가 보인다.

| 기능 | API | 핵심 파일 |
| --- | --- | --- |
| 조회 기록과 조회수 (POST-09) | `POST /api/posts/{id}/views` → 204. 상세의 `viewCount` | `post/application/ViewService`, `post/domain/ViewLog`, `ViewLogRepository`, `PostRepository.increaseViewCount`, `global/web/VisitorKeys` |
| 사이드바 태그 목록 (TAG-03) | `GET /api/tags` → `[{ id, name, postCount }]`, 사이드바 `TAG` 모듈 | `tag/application/TagListService`, `PostCountRepository.countByTag`, `tag/presentation/TagController`, `blog/application/SidebarService` |
| 홈 인기 글 (HOME-02) | `GET /api/home/popular` → `{ snapshotAt, items: [{ rank, post }] }` | `home/application/PopularRanking`(5분 캐시), `HomeService.popular`, `home/domain/PopularScoreRepository`, `PopularProperties` |
| 화면 | 글 상세 "조회 N", 사이드바 태그 칩, 홈 인기 글 | `pages/post/PostPage`, `components/Sidebar`, `pages/home/HomePage` |
| 테스트 | — | `ViewCountIntegrationTest`, `HomePopularIntegrationTest`, `TagIntegrationTest`, `SidebarIntegrationTest` |

**지원이 정한 것 (2026-10-09, 명세에 빈칸이던 것)**

- 비회원 "익명 식별자"(data-model `view_log.viewer_key`): 서버가 처음 보는 비회원에게 임의 값(UUID) 쿠키 `visitor_id`를 1년짜리로 준다(`Domain=.{platform}`, HttpOnly). 키는 회원 `m:{id}`, 비회원 `a:{uuid}`.
- 블로그 주인이 자기 글을 봐도 조회수를 센다(명세에 빼라는 말이 없음. 방문 통계 MNG-03만 주인을 뺀다).
- 최근 1시간 활동이 없는 글은 인기 글에 없다(활동이 없으면 빈 목록).

## 요청 흐름

### 글을 열 때

```
myfirst.blog.test/8                PostPage
  GET /api/posts/8                   본문, viewCount(이번 조회 전 값)
  본문이 보이면 한 번 (useRef로 StrictMode 두 번 막음)
  POST /api/posts/8/views            PostController.view
                                       ① readable: 볼 수 없으면 404·403        [읽기 트랜잭션]
                                       ② VisitorKeys: m:42 / a:uuid (없으면 Set-Cookie visitor_id)
                                       ③ ViewService.record                    [쓰기 트랜잭션]
                                            글 행 FOR UPDATE (첫 문장)
                                            5분 안 같은 키의 기록? → 있으면 끝
                                            INSERT view_log, view_count + 1
                                     ← 204 (셌든 안 셌든)
  GET /api/blog/sidebar              PROFILE, CATEGORY, TAG(보는 사람 기준 글 수), RECENT_POST, RECENT_COMMENT
```

### 홈을 열 때

```
blog.test/                         HomePage
  GET /api/home/popular              HomeService.popular
                                       PopularRanking.snapshot()  ← @Cacheable, Redis blog:popularPosts::home (5분)
                                         없으면: 최근 1시간 view_log×1 + post_like×3 + comment×5 를
                                                 UNION ALL → GROUP BY → 상위 100 후보
                                       후보 번호로 글 읽기 + 비회원 기준 가시성 (매번)
                                       순위대로 10개
                                     ← { snapshotAt, items: [{ rank, post }] }   "최근 1시간 · 04:06 기준"
  GET /api/home/latest               (스텝 6과 같음)
```

## 이 스텝을 이해하려면 (읽는 순서)

| 순서 | 개념 문서 | 이 스텝에서 그 개념이 쓰인 곳 |
| --- | --- | --- |
| 1 | [34 조회수: 누가 봤는지, 5분 중복, 동시 새로고침](./concepts/34-view-count.md) | `VisitorKeys`, `ViewService.record`, `ViewLog`, 글 상세의 조회 요청 |
| 2 | [33 격리 수준, 스냅샷, 데드락](./concepts/33-isolation-deadlock.md)의 5.7 | 조회수에서 다시 만난 데드락과 옛 스냅샷, 잠금을 첫 문장으로 |
| 3 | [36 집계 쿼리로 순위 매기기](./concepts/36-ranking-aggregation.md) | 인기 점수 SQL(`PopularScoreRepository`), 태그별 글 수(`countByTag`, `TagListService`) |
| 4 | [35 캐시: Spring Cache와 Redis](./concepts/35-spring-cache-redis.md) | `@Cacheable`과 프록시, Redis 키·직렬화, 캐시에 번호만 두고 가시성은 매번 |
| 5 | [31 태그와 다대다 관계](./concepts/31-tags-many-to-many.md)의 5.10 | 사이드바 태그 목록, 글이 없는 태그 숨기기 |

먼저 알고 있으면 좋은 문서: [10 HTTP 쿠키](./concepts/10-http-cookies.md)(방문자 쿠키 속성), [17 멱등성과 Redis](./concepts/17-idempotency-redis.md)(Redis 기초, TTL), [23 트랜잭션과 동시성](./concepts/23-transactions-locking.md), [16 인가와 가시성 판단](./concepts/16-authorization-visibility.md)(`visibleTo`, `listedIn`).

## 막혔던 점

- **잠금 없이는 조회 기록도 데드락**: 동시성 테스트가 정말 잠금을 필요로 하는지 보려고 `lockById`를 빼고 세 번 돌렸더니 세 번 모두 `Deadlock found`로 500이었다. 공감(스텝 7)과 같은 "자식 INSERT의 외래 키 S 잠금 + 부모 UPDATE의 X 잠금" 고리다. 조회도 글 행부터 잠근다([34](./concepts/34-view-count.md) 4.2).
- **잠금 위치**: 공감처럼 같은 트랜잭션 안에서 가시성을 먼저 확인하면, 그 평범한 SELECT가 스냅샷을 정해 잠금 뒤의 "5분 안 기록?" 확인이 앞 요청의 기록을 못 본다. 가시성 확인을 컨트롤러에서 따로 하고 `record`는 잠금을 첫 문장으로 했다([34](./concepts/34-view-count.md) 4.4).
- **개발 모드에서 처음 온 비회원은 2번 세짐**: StrictMode가 effect를 두 번 불러 쿠키 없는 요청 두 개가 서로 다른 방문자가 됐다. `useRef`로 같은 글이면 다시 보내지 않게 했다.
- **캐시에 무엇을 넣을지**: 인기 글을 통째로 5분 캐시하면, 그 사이 비공개가 된 글이 홈에 남는다(헌법 원칙 II 위반). 캐시에는 순위(글 번호·점수 100개)만 두고, 글과 가시성은 매번 읽는다. 테스트로 "캐시 안의 1위를 비공개로 바꾸면 바로 빠지고 2위가 1위"를 확인했다([35](./concepts/35-spring-cache-redis.md)).
- **사이드바 위치로 확인하던 테스트 세 개가 깨짐**: TAG 모듈이 카테고리 다음에 들어가 최근 글·댓글이 한 칸씩 밀렸다. 전체 테스트를 돌려서 `PostLifecycleIntegrationTest`, `PostWriteIntegrationTest`에서도 발견했다.
- **인기 점수 테스트가 34초**: 조회 기록을 수천 행 넣었다. 다른 테스트의 활동보다 크기만 하면 되므로 수백 행으로 줄여 15초가 됐다.

## 명세와 다르거나 아직 채우지 않은 것

| 항목 | 지금 | 언제 |
| --- | --- | --- |
| 비회원 식별 방식 | `visitor_id` 쿠키(UUID, 1년). 명세는 "익명 식별자"만 적었음 | 지원 결정, data-model·contracts·spec POST-09에 반영 |
| 주인 본인 조회 | 셈 | 지원 결정, 같은 문서에 반영 |
| 인기 글 계산 방식 | `@Cacheable` 5분 TTL, 후보 100개. research R-13의 "스케줄러가 상위 100개 스냅숏"은 아님 | T078(백로그, 랭킹 전체보기와 함께) |
| `view_log` 7일 지난 행 지우기 | 없음. 계속 쌓인다 | 블로그 점수·통계(T080·T083) 때 |
| 사이드바 인기 글 모듈(누적 조회수 순) | 없음 | T086(사이드바 설정) |
| 조회수 조작 방지 | 쿠키를 안 보내면 매번 새 비회원. 요청 횟수 제한 없음 | 필요할 때 |
| 캐시 값 직렬화 | Java 기본 직렬화. 값 클래스 모양을 바꿔 배포하면 남은 옛 값(최대 5분)을 못 읽을 수 있음 | 필요하면 JSON 직렬화로 |

## 직접 해 보기

```bash
./mvnw test -Dtest='ViewCountIntegrationTest,HomePopularIntegrationTest,TagIntegrationTest,SidebarIntegrationTest'
cd frontend && npm test
```

API로 (공개 글이 있는 블로그 주소 `myfirst`, 글 `8`):

```bash
H="Host: myfirst.blog.test"; X="X-Requested-With: XMLHttpRequest"; rm -f jar.txt
for i in 1 2 3; do curl -s -o /dev/null -w "%{http_code}\n" -c jar.txt -b jar.txt -X POST -H "$H" -H "$X" localhost:8080/api/posts/8/views; done
curl -s -H "$H" localhost:8080/api/posts/8 | grep -o '"viewCount":[0-9]*'     # 세 번 보냈지만 1만 늘었음
curl -s -H "$H" localhost:8080/api/tags                                        # [{id, name, postCount}] 글 수 순
curl -s -H "Host: blog.test" localhost:8080/api/home/popular | python3 -m json.tool | head
docker exec blog-redis redis-cli ttl 'blog:popularPosts::home'                # 300 이하로 줄어듦
```

브라우저로:

1. **코드 저장소 루트**(`~/IdeaProjects/blog`, `frontend` 폴더가 아님)에서 `./scripts/build-frontend.sh && ./mvnw spring-boot:run`
2. 글 하나를 열어 "조회 N"을 본다. 새로고침하면 N+1, 5분 안에 다시 새로고침해도 N+1 그대로다.
3. 다른 회원 B로 다른 글에 공감·댓글을 여러 개 단다. 홈(`http://blog.test:8080`)의 인기 글은 5분 안에는 그대로이고, 5분 뒤(또는 `redis-cli del 'blog:popularPosts::home'` 뒤) 공감·댓글 많은 글이 위로 온다.
4. 인기 글에 있는 글을 주인이 비공개로 바꾸고 홈을 새로고침하면 바로 빠진다.
5. 블로그 사이드바의 태그 칩(`spring 3`)을 눌러 태그 목록으로 간다. 비공개 글에만 단 태그는 시크릿 창(비회원)에서 보이지 않는다.

## 더 공부할 거리

- `@Scheduled`로 순위를 미리 계산하기와 서버가 여러 대일 때 한 대만 돌리게 하기(ShedLock 같은 도구)
- Redis Sorted Set으로 실시간 랭킹 유지하기(`ZINCRBY`, `ZREVRANGE`)
- 조회수를 Redis에 모았다가 주기적으로 DB에 반영하는 쓰기 버퍼링
- 시간이 지나면 점수가 줄어드는 랭킹 공식(감쇠, decay)
