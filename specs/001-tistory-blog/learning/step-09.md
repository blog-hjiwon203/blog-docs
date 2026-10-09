# 스텝 9. 회원정보·주제·하위 카테고리·내 글 관리

> 작업: T055, T055a, T056, T060, T064, T067 · 코드 브랜치: `step-9-manage-topics` · 날짜: 2026-10-09

## 한눈에 보기

블로그 주인이 쓰기 편해지는 기능을 만들었다. 마이페이지에서 닉네임·프로필 사진·비밀번호를 바꾸고, 글에 주제(IT·개발 등 10개)를 고르고, 카테고리 아래 하위 카테고리를 만든다. 홈에는 주제 탭이 생기고, 관리 화면에서는 내 글을 걸러 보고 여러 개를 한 번에 비공개로 바꾸거나 지운다.

| 기능 | API | 핵심 파일 |
| --- | --- | --- |
| 회원정보 수정 (AUTH-05) | `PATCH /api/me { nickname?, profileImageId? }` → Me, `PUT /api/me/password { currentPassword, newPassword }` → 204 | `member/application/MeService`, `member/presentation/MeController`, `Member` |
| 마이페이지 화면 | `blog.test/me` | `frontend/src/pages/me/MyPage.tsx`, 머리글의 닉네임 링크 |
| 글 주제 (POST-11) | `GET /api/topics` → `[{ code, name }]`, 글 저장의 `topic` | `post/domain/Topic`, `post/presentation/TopicController`, `PostWritePage`의 주제 선택 |
| 하위 카테고리 (CAT-03) | `POST /api/categories { name, parentId }` → 201 `{ id, name, parentId, sortOrder }`, 3단계 409 `CATEGORY_DEPTH` | `category/application/CategoryService`, `CategoriesPage`의 [하위 추가] |
| 홈 주제별 글 (HOME-03) | `GET /api/home/topics/{topic}` → PostSummary 6개 | `HomeService.topicPosts`, `PopularRanking.topicSnapshot`, `PopularScoreRepository.topScoresInTopic`, `HomePage`의 주제 탭 |
| 내 글 관리 (MNG-01) | `GET /api/manage/posts?status=&visibility=&categoryId=&q=&page=`, `PATCH`·`DELETE /api/manage/posts` | `manage/application/ManagePostService`, `manage/presentation/ManagePostController`, `pages/manage/ManagePostsPage.tsx` |
| 시도 횟수 제한 (T055a, 지원이 스텝 중에 추가) | 로그인·인증 코드·비밀번호 변경을 15분 안에 5번 틀리면(같은 IP는 셋을 합쳐 20번) 15분 동안 429 `{ retryAfterSeconds }` | `global/auth/AttemptLimiter`, `AttemptLimitProperties`, `AuthService.login`, `EmailVerificationService.check`, `MeService.changePassword`, `frontend/src/api/errors.ts`, 테스트용 `TestWebConfiguration` |
| 공용 도구 | — | `global/web/LikePatterns`(검색에서 옮김) |
| 테스트 | — | `AttemptLimitIntegrationTest`, `errors.test.ts`, `MeUpdateIntegrationTest`, `TopicIntegrationTest`, `CategoryIntegrationTest`, `HomeTopicIntegrationTest`, `ManagePostIntegrationTest` |

**지원이 정한 것 (2026-10-09, 명세에 정해지지 않았던 것, contracts에 반영)**

- 지금 비밀번호가 틀리면 새 오류 코드 없이 400 `VALIDATION_FAILED`의 칸 오류(`currentPassword`)로 준다.
- 프로필 사진은 **본인이 올린 이미지**만 쓸 수 있다(남의 이미지 번호면 400 `profileImageId`). Me의 `profileImageUrl`은 썸네일 주소다.
- 비밀번호를 바꿔도 다른 기기의 로그인은 끊지 않는다.
- 하위 카테고리의 상위 번호가 이 블로그의 것이 아니면 400(`parentId`). 이름 변경(`PATCH`)에서 `parentId`를 보내면 400(상위 바꾸기는 CAT-04).
- 모르는 주제 주소(`/api/home/topics/SPORTS`, 소문자 `health`)는 404.
- 비밀번호·인증 코드 시도 제한(research R-17): 로그인(이메일별)·인증 코드(이메일별)·비밀번호 변경(회원별)을 15분 안에 5번 틀리면 다섯 번째로 틀린 때부터 15분 동안 429. 막힌 동안은 맞는 값도 거절, 맞히면 횟수 초기화, 가입하지 않은 이메일도 똑같이 센다. 스텝 9를 확인하던 지원이 "틀리는 횟수 제한이 있나?"라고 물어 없던 것을 알고 더했다. 이어서 IP별 제한도 더했다: 같은 IP는 셋을 합쳐 15분 안에 20번(20은 공용 IP를 생각한 Claude 기본값, 설정값), 맞혀도 IP 횟수는 지우지 않는다. 운영에서 프록시 뒤에 두면 `server.forward-headers-strategy` 설정이 필요하다.
- 스텝이 끝나면 Claude Code가 tasks.md 체크박스를 `[X]`로 바꾼다(CLAUDE.md).
- 내 글 관리 검색 `q`는 **제목만** 찾는다. 일괄 처리는 이 블로그의 지우지 않은 글만 처리하고 남의 글·지운 글·없는 번호는 건너뛰어 그 수를 뺀 `updatedCount`·`deletedCount`를 준다. 한 번에 100개까지.

## 요청 흐름

### 내 글 여러 개를 비공개로

```
myblog.blog.test/manage/posts?categoryId=1          ManagePostsPage (조건은 주소에)
  GET /api/manage/posts?categoryId=1&page=1           주인 확인(401·403) → 조건 값 검사(400)
                                                      이 블로그·지우지 않은 글 AND 카테고리 1 또는 그 하위
                                                      ORDER BY COALESCE(published_at, updated_at) DESC, id DESC
                                                      20개 + 전체 개수, 숨긴 글은 사유
  체크박스 두 개 → "비공개로" [적용]
  PATCH /api/manage/posts { postIds: [12, 15], visibility: "PRIVATE" }
                                                      내 글 중에서 번호로 찾음 → changeVisibility → 한 트랜잭션
                                                    ← { updatedCount: 2 } → 목록 다시 불러옴
```

### 하위 카테고리와 주제를 골라 발행하고, 홈에서 보기

```
/manage/categories   "개발" [하위 추가] "Spring"
  POST /api/categories { name: "Spring", parentId: 1 }   상위가 이미 하위면 409, 같은 자리 같은 이름 409
/manage/write        카테고리 "└ Spring", 주제 "IT·개발" → 발행
  POST /api/posts { categoryId: 2, topic: "IT_DEV", ... }
블로그 사이드바       개발 (1) > Spring (1)   — 상위 글 수에 하위 글 수가 합쳐짐
blog.test/          주제별 글 [IT·개발] 탭
  GET /api/topics                                       탭 10개
  GET /api/home/topics/IT_DEV                           주제별 인기 순위(Redis blog:topicPosts::IT_DEV, 5분)
                                                        볼 수 있는 글만 순위대로, 6개 안 되면 그 주제 최신 글로 채움
```

### 마이페이지

```
blog.test/me       MyPage
  [사진 바꾸기] → POST /api/images → PATCH /api/me { profileImageId }   내가 올린 이미지인가
  닉네임 [저장] → PATCH /api/me { nickname }                             나 말고 쓰는 회원? 409
  [변경]        → PUT /api/me/password                                   지금 비밀번호 확인 → 규칙 → bcrypt
```

## 이 스텝을 이해하려면 (읽는 순서)

| 순서 | 개념 문서 | 이 스텝에서 그 개념이 쓰인 곳 |
| --- | --- | --- |
| 1 | [38 회원정보 수정](./concepts/38-member-profile-update.md) | `MeService.update`·`changePassword`, IDOR 막기, 마이페이지 |
| 1-1 | [40 시도 횟수 제한](./concepts/40-attempt-limit.md) | `AttemptLimiter`, 로그인·인증 코드·비밀번호 변경의 15분·5번, 동시 시도, 429 안내 문장 |
| 2 | [39 계층 데이터: 카테고리 2단계와 주제](./concepts/39-category-hierarchy.md) | 하위 카테고리, `parent_key` 계산 칸, `Topic` enum, 주제별 글 |
| 3 | [37 거르기 조건이 있는 목록과 일괄 처리](./concepts/37-filtered-list-bulk-actions.md) | 내 글 관리 목록·일괄 처리, `LikePatterns`, 주소에 둔 거르기 조건 |
| 4 | [35 캐시](./concepts/35-spring-cache-redis.md)의 5.9, [36 집계 순위](./concepts/36-ranking-aggregation.md)의 5.5 | 주제별 캐시 키 `#topic.name()`, 같은 SQL에 주제 조건 |
| 5 | [05 Spring 테스트](./concepts/05-spring-testing.md)의 5.7 | 서비스 전체 목록 테스트끼리의 간섭과 고친 방법 |
| 6 | [32 검색](./concepts/32-search-like.md) 끝 절 | LIKE 이스케이프를 공용으로 옮김 |

먼저 알고 있으면 좋은 문서: [09 비밀번호 해시](./concepts/09-password-hashing.md), [22 입력 검증](./concepts/22-bean-validation.md)(401이 400보다 먼저), [16 인가와 가시성](./concepts/16-authorization-visibility.md)(`ownerView`, `visibleTo`), [06 JPA](./concepts/06-jpa-entity-mapping.md)(Specification), [25 React 폼](./concepts/25-react-forms-data.md)(`useSearchParams`).

## 막혔던 점

- **테스트끼리 IP가 쌓임**: IP별 제한을 넣자 MockMvc 요청이 모두 127.0.0.1이라, 여러 테스트의 로그인 실패가 한 IP에 20번 넘게 쌓여 뒤 테스트가 429를 받을 수 있었다. 테스트 요청마다 다른 주소를 주는 `TestWebConfiguration`을 더했다([40](./concepts/40-attempt-limit.md) 5.6).

- **비밀번호를 틀리는 횟수에 제한이 없었다**: 스텝 9를 확인하던 지원의 질문으로 알았다. 로그인·인증 코드·비밀번호 변경 모두 몇 번이든 넣어 볼 수 있었다(스텝 4 학습 문서 20의 "남은 위험"에 적혀만 있던 것). 지원이 15분·5번으로 정해 명세(spec, contracts, research R-17, tasks T055a)에 먼저 적고 만들었다. "보고 → 확인"이 동시 요청에 뚫리지 않게 확인 전에 `INCR`로 자리를 잡는다([40](./concepts/40-attempt-limit.md) 3.4).
- **확인용 서버를 띄우다 지원의 서버를 끔**: 8080이 이미 쓰이고 있어 새 서버가 뜨지 못했는데, 정리하려고 이름으로 프로세스를 모두 끄다 지원이 띄워 둔 8080 서버까지 꺼졌다. 그 뒤로는 8081에 띄우고 그 포트의 프로세스만 끈다.

- **혼자 돌리면 통과, 전체를 돌리면 실패 (두 번)**: 주제별 글 테스트가 만든 "활동 많은 다른 주제 글"이 홈 인기 글 테스트의 1·2위를 밀어냈고, 고친 뒤에는 채우는 글을 2099년 날짜에 둔 것이 홈 최신 글 테스트의 미래 글과 섞였다. 인기 글 테스트를 "몇 위"가 아니라 "앞뒤 관계"로 바꾸고, 미래 날짜를 쓰지 않게 했다([05](./concepts/05-spring-testing.md) 5.7).
- **이름 바꾸기도 같은 자리에서만 비교해야 했다**: 스텝 5의 이름 중복 검사는 최상위끼리만 봤다. 하위가 생기면 다른 상위 아래의 같은 이름으로 잘못 409가 난다. 추가·이름 바꾸기 모두 같은 `nameTaken(blog, 상위, 이름)`을 쓰게 했다([39](./concepts/39-category-hierarchy.md) 5.1).
- **두 시각을 섞는 정렬**: "최신순, 임시저장은 수정 시각순"을 `Sort.by`로 표현할 수 없어서 Specification 안에서 `COALESCE`로 정렬을 걸고, 개수 쿼리에는 걸지 않게 했다([37](./concepts/37-filtered-list-bulk-actions.md) 5.2).
- **enum 쿼리 파라미터가 401보다 먼저 400**: 거르기 값을 글자로 받아 주인 확인 뒤에 바꾼다([37](./concepts/37-filtered-list-bulk-actions.md) 3.5).
- **effect 안에서 상태 복사 경고**: 마이페이지에서 처음 받은 내 정보를 `useEffect`로 상태에 복사하자 oxlint가 경고했다. 저장 결과만 상태로 두고 그릴 때 고르게 바꿨다([38](./concepts/38-member-profile-update.md) 5.5).
- **선택 상자 들여쓰기**: `<option>` 안에는 태그를 못 넣어서 하위 카테고리를 줄바꿈 없는 공백(` `)과 `└`로 들여썼다.

## 명세와 다르거나 아직 채우지 않은 것

| 항목 | 지금 | 언제 |
| --- | --- | --- |
| 프로필 사진 지우기 | 바꾸기만 됨(PATCH에서 "안 보냄"과 "null"을 구분하지 못함) | 필요하면 |
| 비밀번호 변경 뒤 다른 기기 로그아웃 | 안 함 | 필요하면 |
| 소셜 연동·내 블로그 목록·대표 블로그·탈퇴 (마이페이지 나머지) | 없음 | OWN-03, BLOG-08, AUTH-06 (백로그) |
| 드래그로 순서·상하위 바꾸기 | 없음. 이름 변경에서 `parentId`는 400 | T060a (CAT-04, 백로그) |
| 비공개 카테고리 | 바꾸는 기능 없음(CAT-05). 트리·목록의 숨김 규칙만 맞춰 둠 | 백로그 |
| 임시저장·예약 글 | 아직 만들 수 없어 글 관리 상태 거르기는 늘 "발행"만 나옴 | T058·T059 (백로그) |
| 다른 블로그로 옮기기 (글 관리 화면의 버튼) | 없음 | BLOG-06 (백로그) |
| 내 글 관리 검색 범위 | 제목만 | 필요하면 본문까지 |

## 직접 해 보기

```bash
./mvnw test -Dtest='AttemptLimitIntegrationTest,MeUpdateIntegrationTest,TopicIntegrationTest,CategoryIntegrationTest,HomeTopicIntegrationTest,ManagePostIntegrationTest'
cd frontend && npm test
```

브라우저로 (코드 저장소 루트에서 `./scripts/build-frontend.sh && ./mvnw spring-boot:run`):

1. **회원정보**: `http://blog.test:8080/me`에서 사진·닉네임·비밀번호를 바꾼다. 로그아웃 후 새 비밀번호로 로그인된다. (목업 mypage와 비교)
2. **하위 카테고리**: `/manage/categories`에서 "개발" 아래 "Spring"을 만들고, 글을 하나씩 "개발"·"└ Spring"으로 발행한다. 사이드바의 "개발"을 누르면 두 글이 모두 나오고 글 수가 2다.
3. **주제**: 글쓰기에서 주제를 "여행"으로 발행하고, 홈의 주제별 글 "여행" 탭에서 본다. (목업 home과 비교)
4. **내 글 관리**: `/manage/posts`에서 글 두 개를 골라 "비공개로" [적용]. 시크릿 창(비회원)으로 블로그 메인을 열면 두 글이 없다. 상태·카테고리를 바꾸면 주소가 바뀌고, 그 주소를 새로 열어도 같은 목록이다. (목업 manage-posts와 비교)
5. **시도 제한**: 로그아웃하고 로그인 비밀번호를 5번 틀린 뒤 맞는 비밀번호를 넣으면 "여러 번 시도해 잠시 막혔습니다. 15분 뒤에 다시 시도해 주세요."가 나온다. 풀려면 `docker exec blog-redis redis-cli del "attempt:login:{이메일}"`. 같은 컴퓨터에서 여러 이메일로 20번 틀리면 IP도 막힌다(`attempt:ip:127.0.0.1`을 지워 푼다).

```bash
H="Host: {주소}.blog.test"; X="X-Requested-With: XMLHttpRequest"; J="Content-Type: application/json"
curl -s -H "Host: blog.test" localhost:8080/api/topics
curl -s -H "Host: blog.test" localhost:8080/api/home/topics/IT_DEV | python3 -m json.tool | head
curl -s -b jar.txt -H "$H" "localhost:8080/api/manage/posts?visibility=PRIVATE"
curl -s -b jar.txt -H "$H" -H "$X" -H "$J" -X PATCH -d '{"postIds":[글번호들],"visibility":"PUBLIC"}' localhost:8080/api/manage/posts
```

## 더 공부할 거리

- 트리 저장 방식 비교(인접 목록, 경로 열거, 중첩 집합, 클로저 테이블)와 재귀 CTE
- JSON Merge Patch(RFC 7396)로 "지우기"까지 되는 부분 수정
- 비밀번호 변경 시 모든 Refresh 토큰 무효화(토큰 버전·세대 번호)
- 테스트 격리 전략: 테스트마다 표 비우기, 데이터베이스를 테스트 클래스마다 따로, 랜덤 데이터와 상대 비교
