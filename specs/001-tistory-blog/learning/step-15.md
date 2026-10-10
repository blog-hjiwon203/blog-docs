# 스텝 15. 전체 검색

> 작업: T065 · 코드 브랜치: `step-15-search` · 날짜: 2026-10-11 · 백로그 추천 순서의 네 번째 스텝

## 한눈에 보기

플랫폼 머리글에 검색창이 생겼다. 모든 블로그의 글과 블로그를 찾는다. 블로그 안 검색(스텝 7)과 같은 API 경로를 쓰고, 요청 주소(Host)가 플랫폼이면 전체 검색, 블로그면 지금까지처럼 그 블로그 안 검색이다. 새 테이블은 없다.

| 무엇 | 만든 것 | 핵심 파일 |
| --- | --- | --- |
| 글 검색 | 플랫폼 주소의 `GET /api/search?q=&type=post&page=`: 모든 블로그에서 남에게 보이는 글(홈 최신 글과 같은 조건) 중 제목·본문 글자·태그 이름에 검색어가 든 것, 최신순 10 | `SearchService.searchAll`, `matches` |
| 블로그 검색 | `type=blog`: 이름·소개에 검색어가 든, 남에게 보이는 블로그(지움·이용 제한·주인 정지·이사 제외), 새로 만든 순 10. 한 줄에 사진·소개·주인(대표 블로그 링크·사진)·구독자 수 | `SearchService.searchBlogs`, `BlogSearchService`, `SubscriptionRepository.countByBlogIds`, `BlogSearchResponse` |
| 같은 경로 나누기 | 한 메서드에서 Host를 보고 나눔. 블로그 쪽 판단은 `@CurrentBlog`와 같은 `CurrentBlogArgumentResolver.resolve` | `SearchController`, `CurrentBlogArgumentResolver` |
| 화면 | 플랫폼 머리글 검색창, `/search?q=&type=&page=`(글·블로그 탭, 개수, 페이지 번호, 결과 없음 안내). 글 한 줄은 홈 최신 글과 같은 `PlatformPostItem` | `PlatformHeader.tsx`, `pages/search/GlobalSearchPage.tsx`, `components/PlatformPostItem.tsx` |

## 요청 흐름

```
플랫폼 머리글 검색창 "spring" → /search?q=spring&type=post
GET blog.test/api/search?q=spring&type=post&page=1
  → SearchController: BlogHostResolver.resolve → Platform
  → SearchService.searchAll: visibleTo(보는 사람) AND (제목 OR 본문 글자 OR 태그 이름 LIKE '%spring%')
     project("blog","category"), publishedAt DESC, id DESC, 10개 + 전체 수
  → PostSummary(블로그 주소·이름 포함) → 제목을 누르면 {address}.blog.test/{id}

"블로그" 탭 → GET …&type=blog
  → SearchService.searchBlogs(이름·소개 LIKE, 남에게 보이는 블로그)
  → BlogSearchService: 구독자 수(group by 한 번), 사진(한 번), 주인 대표 블로그(한 번)

블로그 머리글 검색창 → GET alpha.blog.test/api/search?q=… → Host가 블로그 → resolve(블로그, 404 판단) → 그 블로그 안 검색(스텝 7 그대로)
```

## 이 스텝을 이해하려면 (읽는 순서)

| 순서 | 개념 문서 | 이 스텝에서 쓰인 곳 |
| --- | --- | --- |
| 1 | [32 블로그 안 검색](./concepts/32-search-like.md) (복습 + 5.9 보강) | 스텝 7의 LIKE·이스케이프·EXISTS. 5.9: 찾기 조건은 같고 범위만 바꾸는 Specification, 블로그 검색 조건, 구독자 수를 `group by` 한 번으로, 테스트마다 고유한 검색어 |
| 2 | [15 서브도메인과 Host 라우팅](./concepts/15-subdomain-host-routing.md) (복습 + 5.7 보강) | Host 세 갈래, `@CurrentBlog`. 5.7: Spring이 Host로 메서드를 고르지 못해 한 메서드에서 나누기, 인자 해석기의 몸통을 `resolve`로 꺼내기, 고르지 않은 대안 |
| 3 | (복습) [16 인가와 가시성](./concepts/16-authorization-visibility.md), [50 같은 규칙의 두 기능을 한 코드로](./concepts/50-shared-rules-comment-guestbook.md) 5.4 | `visibleTo`와 `isOpenToOthers`(한 개를 볼 때와 목록의 조건을 같게), `findBy`의 `project`·`page` |

## 막혔던 점

- **같은 경로 두 메서드는 안 된다**: 처음에는 플랫폼용 메서드를 하나 더 만들려 했지만, 같은 `@GetMapping("/api/search")` 두 개는 시작할 때 모호한 매핑 오류이고 Host로 고를 방법이 없다. 한 메서드에서 `RequestHost`로 나눴다([15](./concepts/15-subdomain-host-routing.md) 5.7).
- **`post.getBlog()`를 트랜잭션 밖에서 읽을 뻔함**: 응답을 만들 때 글마다 `post.getBlog()`를 쓰게 고쳤는데, 블로그 안 검색은 글을 읽을 때 블로그를 함께 읽지 않는다(그 블로그를 이미 아니까). 트랜잭션이 끝난 뒤라 지연 로딩이 실패할 수 있어, 블로그 안 검색은 알고 있는 블로그를 넘기고 전체 검색만 `project("blog", …)`로 함께 읽은 블로그를 쓴다.
- **전체 검색 테스트는 DB 전체가 범위**: 다른 테스트가 남긴 글에 같은 단어가 있으면 개수가 틀린다. 테스트마다 `"q" + UUID 10자`를 검색어로 썼다.
- **검색 화면의 입력칸 모양**: 처음 화면은 입력칸에 스타일이 없어 머리글 검색창과 달랐다. 브라우저 확인에서 보고 같은 `search-box`로 맞췄다.
- **화면은 실제 브라우저로 확인**: 8081 확인용 서버와 헤드리스 Chrome으로, 홈 머리글 검색창에 비공개 글 제목("개발 글")을 넣으면 "글 0개", 공개 글("공개 글")은 1개와 그 블로그 주소 링크(`b13a22029.blog.test:8081/20`), 블로그 탭에서 "갑의"를 찾으면 사진·주인·"구독 0". 휴대폰 폭(360px) 홈에서 머리글 검색창이 줄바꿈되어 가로로 넘치지 않음.

## 명세와 다르거나 아직 채우지 않은 것

| 항목 | 지금 | 언제 |
| --- | --- | --- |
| 전체 검색에서 주인의 비공개 글 | 나오지 않는다(홈과 같이 남에게 보이는 글만). API 명세에 적음 | 반영함 |
| 블로그 검색 정렬과 응답 모양 | 새로 만든 순, `blog`에 `description`·`profileImageUrl`. API 명세에 적음 | 반영함 |
| 알 수 없는 `type` | 400 `fieldErrors[].field = type`. API 명세에 적음 | 반영함 |
| 블로그 구독자 수 | 구독(스텝 16) 전이라 늘 0 | 스텝 16 |

## 직접 해 보기

```bash
./mvnw test -Dtest='GlobalSearchIntegrationTest,SearchIntegrationTest'
curl -s 'http://blog.test:8080/api/search?q=spring&type=post' | head -c 300; echo
curl -s 'http://blog.test:8080/api/search?q=spring&type=blog' | head -c 300; echo
curl -s -o /dev/null -w '%{http_code}\n' 'http://blog.test:8080/api/search?q=spring&type=user'   # 400
```

화면: 홈 머리글 검색창 → 글 탭·블로그 탭 → 내 비공개 글 제목으로 찾으면 0개(내 블로그 머리글 검색창에서는 나온다).
