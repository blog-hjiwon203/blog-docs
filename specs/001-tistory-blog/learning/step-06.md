# 스텝 6. 읽기·댓글·권한 (P0 완성)

> 작업: T041, T057, T042, T044, T045, T051, T052 · 코드 브랜치: `step-6-read-comment` · 날짜: 2026-10-09

## 한눈에 보기

다른 사람이 홈에서 글을 발견해 읽고 댓글을 다는 부분을 만들었다. 이것으로 **가입 → 블로그 개설 → 발행 → 홈에서 발견 → 읽기 → 댓글** 한 바퀴(P0)가 돈다. 남의 글을 고치려 하거나 볼 수 없는 글을 열면 서버가 막고, 화면은 404·403 오류 화면을 보여 준다.

| 기능 | API | 핵심 파일 |
| --- | --- | --- |
| 글 상세 (POST-04) | `GET /api/posts/{id}` | `post/application/PostReadService`, `PostView`, `presentation/dto/PostDetailResponse` |
| 이전·다음 글 (POST-10) | 글 상세 응답의 `prev`, `next` | `PostReadService.neighbor` |
| 홈 최신 글 (HOME-01) | `GET /api/home/latest?cursor=` | `home/application/HomeService`, `home/presentation/HomeController` |
| 댓글 (CMT-01, CMT-02) | `GET·POST /api/posts/{id}/comments`, `DELETE /api/comments/{id}` | `comment/application/CommentService`, `CommentView`, `CommentController` |
| 공통 부품 | — | `blog/application/PrimaryBlogAddresses`(작성자 대표 블로그 주소를 한 번에) |
| 화면 | `/`(홈), `{주소}/{글 번호}`, `/admin` | `pages/home/HomePage`, `pages/post/PostPage`, `components/Comments`, `components/ErrorPage`, `pages/admin/AdminPage`, `app/sanitize.ts` |
| 권한 시험 (T052) | — | `src/test/.../security/AccessControlIntegrationTest` |

**T057(이전·다음 글)은 원래 백로그였다.** spec POST-04(P0)와 US3 시나리오 3이 글 상세에 이전·다음 글을 보여 주라고 해서, 지원이 스텝 6으로 앞당기기로 정했다(2026-10-08, tasks.md 반영).

## 요청 흐름

### 홈에서 글을 열고 댓글을 달기까지

```
blog.test/                         HomePage
  GET /api/home/latest             HomeService: 모든 블로그에서 볼 수 있는 글(visibleTo), (발행 시각, id) 최신순 21개 읽음
                                   → 20개 + nextCursor ("더보기"는 이 커서로 이어 읽음)
  글 제목 클릭 → <a href="http://alpha.blog.test/9">   (다른 호스트라 페이지를 새로 연다)

alpha.blog.test/9                  SpaForwardController: 글 9를 볼 수 있나 판단 → index.html
  PostPage
  GET /api/posts/9                 PostReadService.detail
                                     readable(): PostVisibilityPolicy.decide → Owner·Visible이면 글
                                                 SubscribersOnly → 403, NotFound·MovedTo → 404
                                     neighbor(): 같은 블로그, 볼 수 있는 글 중 바로 앞·뒤 하나씩
  화면: sanitizePostHtml(contentHtml)로 DOMPurify 한 번 더 → dangerouslySetInnerHTML

  GET /api/posts/9/comments        CommentService.list: 같은 readable() 판단 → 작성순 20개 + totalCount
                                   보는 사람마다 SECRET·BLINDED는 내용·작성자를 null로 가림
  댓글 등록 (회원)
  POST /api/posts/9/comments  Idempotency-Key
                                   readable(404) → 비회원 401 → 댓글 막힘 403 → 입력 400
                                   저장 + UPDATE post SET comment_count = comment_count + 1
```

### 권한 판단 두 가지

| | 읽기용 `PostReadService.readable` | 쓰기용 `PostService.findOwned` |
| --- | --- | --- |
| 쓰는 곳 | 글 상세, 댓글 목록·쓰기·지우기 | 글 수정·삭제·공개 범위, 편집용 조회 |
| 주인 | 통과 | 통과 |
| 남이 볼 수 있는 글 | 통과 | 비회원 401, 회원 403 |
| 구독자 공개를 구독 안 함 | 403 `SUBSCRIBERS_ONLY` | 비회원 401, 회원 403 |
| 볼 수 없는 글, 다른 블로그 글 | 404 | 404 |

둘 다 스텝 3의 `PostVisibilityPolicy` 하나를 거친다. 판단 규칙은 한 곳에 있고, 상황에 맞게 상태 코드로 바꾸는 것만 다르다.

## 이 스텝을 이해하려면 (읽는 순서)

Thymeleaf로 화면을 만들어 봤다면 [28 Thymeleaf에서 React로](./concepts/28-thymeleaf-to-react.md)를 먼저 읽는다. 글 상세 화면이 "서버가 그린 HTML"이 아니라 "빈 HTML + JSON"으로 만들어지는 이유가 있다.

| 순서 | 개념 문서 | 이 스텝에서 그 개념이 쓰인 곳 |
| --- | --- | --- |
| 1 | [16 인가와 가시성 판단](./concepts/16-authorization-visibility.md)의 스텝 6 부분 | `PostReadService.readable`, 위 비교 표, 관리자 영역, T052 |
| 2 | [29 댓글 설계](./concepts/29-comments-design.md) | 댓글이 글의 판단을 물려받음, 보는 사람마다 다른 댓글, 댓글 수, 연타 두 겹 |
| 3 | [08 페이지네이션](./concepts/08-pagination.md)의 스텝 6 부분 | 홈·댓글 커서, 이전·다음 글 |
| 4 | [14 XSS, HTML 정화, CSP](./concepts/14-xss-sanitize-csp.md)의 스텝 6 부분 | DOMPurify, `dangerouslySetInnerHTML`, 이중 정화의 끝 |
| 5 | [17 멱등성과 Redis](./concepts/17-idempotency-redis.md)의 스텝 6 부분 | 댓글 연타 방지, 화면에서도 막아야 했던 이유 |
| 6 | [24 계층 구조와 DTO](./concepts/24-layered-architecture-dto.md)의 스텝 6 부분 | `PrimaryBlogAddresses`, `PostView`·`CommentView`, 연관 함께 읽기 |
| 7 | [25 React 폼과 데이터 불러오기](./concepts/25-react-forms-data.md)의 스텝 6 부분 | `Comments`, `useRef`로 즉시 막기, 오류 화면 |

## 막혔던 점

- **댓글을 빠르게 두 번 누르면 화면에 두 개**: 서버는 같은 연타 방지 키라 댓글을 하나만 만들고 두 요청에 같은 응답을 줬다. 그런데 화면이 두 응답을 각각 목록에 붙였다. 헤드리스 Chrome에서 등록 버튼을 두 번 눌러 본 결과로 찾았다. 진행 중이면 두 번째 클릭을 바로 막는 `useRef`(state는 다음 그리기에서야 바뀌어 늦다)와, 이미 있는 id면 붙이지 않는 확인을 더했다([29](./concepts/29-comments-design.md), [25](./concepts/25-react-forms-data.md)).
- **DOMPurify 3.4.15에 보안 권고 2건**: 설치 직후 `npm audit`가 알려 줬다. 3.4.16에서 고쳐졌고, 오늘 기준 나온 지 16일이라 2주 기준도 넘어 3.4.16으로 올렸다. 이 프로젝트가 쓰지 않는 `IN_PLACE` 모드의 문제였다.
- **"고친 적 없음"을 어떻게 알까**: 글 상세의 `updatedAt`은 발행 뒤 고친 적이 없으면 `null`이어야 한다(contracts). Auditing은 처음 저장할 때 생성·수정 시각에 같은 값을 넣는다. 둘이 다르면 그 뒤에 고친 것이다. 댓글 수 갱신처럼 작성자가 고치지 않은 변경은 `updated_at`을 그대로 두도록 일괄 UPDATE를 썼다([27](./concepts/27-soft-delete-bulk-update.md)의 기법).
- **확인 서버가 뜨기 전에 확인 스크립트가 돌았음**: 대기 반복문이 어제 로그의 "Started" 줄을 잡았다. 오늘 날짜가 찍힌 줄을 기다리게 바꿨다.
- **지원이 8080에 띄운 서버**: 끄지 않고 확인용 서버를 8081로 따로 띄웠다(스텝 5와 같음).

## 명세와 다르거나 아직 채우지 않은 것

| 항목 | 지금 | 언제 |
| --- | --- | --- |
| 이전·다음 글 (T057) | 스텝 6에서 만듦 | 백로그에서 앞당김(지원 결정) |
| 글 상세의 태그, 공감 버튼, 저장 | `tags: []`, 공감 수만 표시, `liked`·`bookmarked`는 `false` | 스텝 7 (태그·공감), 백로그 (저장) |
| 조회수 | `viewCount`는 표시용 값만(아직 늘지 않음) | 스텝 8 |
| 답글, 비밀댓글 쓰기, 댓글 수정 | `parentId`·`secret: true`를 보내면 400. 화면에도 없음 | 스텝 7 (T069), 백로그 |
| 구독자 공개 글 안내 화면 | 안내 문구만, 구독 버튼 없음 | 구독(SUB-01) |
| 서비스 관리 화면 | 들어오는 것만 막음(일반 회원 403) | 관리자 기능 스텝 |

## 남은 문제

| 문제 | 영향 | 언제 |
| --- | --- | --- |
| 댓글을 다 불러오기 전(더보기가 남음)에 새 댓글을 쓰면, 그 댓글은 마지막 묶음을 불러올 때 보인다 | 바로 안 보여 헷갈릴 수 있음 | 화면 정리 때 |
| 스텝 5에서 남긴 `Idempotency-Key` 없는 요청의 400 순서 | 댓글 쓰기도 같음 | 정리할 때 |

## 직접 해 보기

```bash
./mvnw test -Dtest='PostDetailIntegrationTest,HomeLatestIntegrationTest,CommentIntegrationTest,AccessControlIntegrationTest'
cd frontend && npm test
```

브라우저로 P0 한 바퀴 (quickstart 1~6, 공감 제외):

1. `./scripts/build-frontend.sh && ./mvnw spring-boot:run`
2. A로 로그인해 내 블로그에 글을 발행한다.
3. 로그아웃하고 `http://blog.test:8080/` 홈의 최신 글에서 그 글을 찾아 연다.
4. B로 가입·로그인하고 그 글에 댓글을 단다. 등록을 빠르게 두 번 눌러도 하나다.
5. A로 다시 로그인해 B의 댓글을 지운다(삭제 버튼이 보임). B의 댓글에 수정 버튼은 없다.
6. A의 글을 비공개로 바꾸고 시크릿 창에서 그 글 주소를 연다 → 404 화면.
7. B로 로그인한 채 `http://blog.test:8080/admin` → 403 화면.

```bash
# 화면 없이 권한 표 확인 (bash)
R="--resolve alpha.blog.test:8080:127.0.0.1 --resolve beta.blog.test:8080:127.0.0.1"
curl -s $R -o /dev/null -w '%{http_code}\n' alpha.blog.test:8080/api/posts/{A의 비공개 글}   # 404
curl -s $R -o /dev/null -w '%{http_code} %{redirect_url}\n' beta.blog.test:8080/{A의 공개 글}  # 301 → alpha
curl -s -b jarB -o /dev/null -w '%{http_code}\n' blog.test:8080/api/admin/dashboard          # 403
```

## 더 공부할 거리

- 커서 페이지네이션에서 정렬 키가 겹칠 때(같은 시각) 순서를 정하는 법
- 비정규화(댓글 수 칸)와 정합성: 원자적 UPDATE, 주기적 다시 세기
- DOMPurify 설정(`ALLOWED_TAGS`, `ALLOWED_URI_REGEXP`)과 Trusted Types
- 낙관적 UI 업데이트(서버 응답 전에 화면부터 바꾸기)와 그때 필요한 중복 처리
