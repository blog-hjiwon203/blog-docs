# 스텝 20. 저장한 글·스팸 차단·방문 통계·랭킹·기기 쿠키 (앱 키가 필요 없는 것 먼저)

> 작업: T055b, T074~T085 · 코드 브랜치: `step-20-stats-bookmark-ranking` · 날짜: 2026-10-11 · 남은 작업: T088(메일), T099·T100(카카오·구글). 앱 키를 받은 뒤 이어서 한다(2026-10-11 지원 결정)

## 한눈에 보기

스텝 20의 작업 가운데 외부 서비스 키(SMTP, 카카오·구글 OAuth)가 필요 없는 것을 먼저 끝냈다.

| 작업 | 만든 것 | 핵심 파일 |
| --- | --- | --- |
| T074~T077 저장한 글 | 글 상세 "저장"(멱등 PUT·DELETE, 저장할 때 제목·블로그 이름 스냅숏), 마이페이지 "저장한 글"(볼 수 없게 된 글은 스냅숏 제목과 "볼 수 없는 글", 목록에서 바로 취소), 탈퇴하면 저장 삭제 | `bookmark/…`, `components/BookmarkButton.tsx`, `components/MeTabs.tsx`, `pages/me/BookmarksPage.tsx`, `member/domain/MemberTraceCleaner` |
| T084·T085 스팸·차단 | 블로그 주인의 회원 차단(기존 구독 삭제)·해제, 금칙어 100개(대소문자 무시), 댓글·방명록·구독에 검사 연결, 댓글 관리에서 바로 차단, 스팸·차단 화면 | `manage/application/SpamGuard`, `BlogSpamService`, `ManageSpamController`, `pages/manage/ManageSpamPage.tsx` |
| T082·T083·T085 방문 통계 | 블로그 화면 요청마다 하루 한 번 방문 기록(주인 제외, Referer로 유입 종류), 새벽 0시 10분 모으기(지난 7일 다시, 누적 다시 계산, 오래된 기록 정리), 관리 홈 오늘·어제·누적과 최근 댓글·글, 일·주·월 그래프, 인기 글, 유입 경로 | `manage/domain/BlogStatsRepository`, `ReferrerType`, `manage/application/VisitRecorder`, `StatsAggregator`, `BlogStatsService`, `global/config/SpaForwardController`, `pages/manage/ManageStatsPage.tsx`, `ManageHomePage.tsx` |
| T078~T081 랭킹 | 인기 블로거(7일 블로그 점수, 정시 칸 캐시), 랭킹 전체보기(인기 글·인기 블로거 100위까지 20개씩, 기준 시각이 바뀌면 409), 추천 블로그 5(내 블로그·구독 중 제외) | `ranking/…`, `home/application/HomeService.popularRanking`, `pages/ranking/RankingPage.tsx`, `components/BlogCardItem.tsx`, `pages/home/HomePage.tsx`, `pages/feed/FeedPage.tsx` |
| T055b 기기 쿠키 | 로그인에 성공한 브라우저에 서명된 기기 쿠키(1년). 그 회원의 기기 쿠키를 가진 로그인은 틀린 횟수를 기기로 센다(남이 내 이메일을 잠가도 들어옴) | `auth/application/DeviceTokens`, `AuthService`, `auth/presentation/AuthCookieManager`, `AuthController` |

## 요청 흐름

```
[저장] PUT {블로그}/api/posts/20/bookmark → 볼 수 있는 글?(404) → 회원?(401) → INSERT IGNORE(스냅숏) → { bookmarked }
[저장한 글] GET blog.com/api/me/bookmarks → 저장 최신순 21개 → 항목마다 PostVisibilityPolicy → 글 또는 스냅숏

[차단] POST {블로그}/api/manage/blocked-members → 주인? → 회원 확인 → INSERT IGNORE(409) → 구독 삭제
[댓글] POST …/comments → 404 → 401 → 댓글 허용 403 → 차단 403 BLOCKED_BY_BLOG → 금칙어 400 BANNED_WORD → 저장
[댓글 고치기] PATCH /api/comments/{id} → 404 → 401 → 본인·숨김 403 → 차단 403 → 금칙어 400 → 저장 (방명록도 같음)

[방문] GET {블로그}/20 (화면) → SpaForwardController → VisitRecorder(주인 제외) → INSERT IGNORE blog_visit
[새벽 0:10] StatsAggregator.run → 지난 7일 지우고 다시 모으기 → 누적 다시 계산 → 방문 7일, 조회 7일+1시간 넘은 것 지우기
[관리 홈] GET /api/manage/stats → 오늘(바로 셈) + 어제(요약) + 누적(요약 합 + 오늘)

[홈 인기 블로거] GET /api/home/bloggers → 지금 칸(정시) → 캐시(키 = 정시) 없으면 [정시−7일, 정시) 점수 100 → 볼 수 있는 것만 → 5
[랭킹 더보기] GET /api/ranking/bloggers?snapshotAt=…&offset=20 → 기준 시각 같으면 21~40위, 다르면 409 RANKING_UPDATED
[추천] GET /api/recommend/blogs → 같은 순위표에서 내 블로그·구독 중 빼고 5

[로그인] POST /api/auth/login (Cookie: device) → 서명 맞고 이 이메일의 회원? → "login-device:{nonce}" : "login:{email}"로 횟수 → 성공하면 새 기기 쿠키
```

## 이 스텝을 이해하려면 (읽는 순서)

| 순서 | 개념 문서 | 이 스텝에서 쓰인 곳 |
| --- | --- | --- |
| 1 | [56 저장한 글](./concepts/56-bookmark-snapshot.md) (새 문서) | 멱등한 저장, 스냅숏(정규화의 예외), 읽을 때 다시 보는 가시성, 이유를 말하지 않는 "볼 수 없음", 목록에서의 취소 |
| 2 | [57 스팸 막기](./concepts/57-spam-block-banned-words.md) (새 문서) | 서비스 정지와 블로그 차단, 검사를 한 곳에, 검사 순서, 차단과 함께 지우는 구독, 금칙어와 콜레이션, 상태 코드 고르기 |
| 3 | [58 방문 통계](./concepts/58-visit-stats-nightly-batch.md) (새 문서) | 하루 방문자, 원본과 요약, 멱등한 배치(지우고 넣기·다시 계산), Referer와 한계, SPA에서 방문을 아는 곳, 그래프 빈 칸 |
| 4 | [59 시간 칸 스냅숏](./concepts/59-hourly-snapshot-ranking.md) (새 문서) | 작업 대신 시간 칸 캐시, 결정적 계산, 더보기 중 순위 고정과 409, 블로그 점수 SQL, 추천 |
| 5 | [60 기기 쿠키](./concepts/60-device-cookie-lockout.md) (새 문서) | 잠금 악용, HMAC 서명, nonce, 고정 시간 비교, 용도별 키, 시도 키 바꾸기, 막지 못하는 것 |
| 6 | (복습) [35 캐시](./concepts/35-spring-cache-redis.md), [36 집계 쿼리](./concepts/36-ranking-aggregation.md), [40 시도 횟수 제한](./concepts/40-attempt-limit.md), [52 예약 작업](./concepts/52-scheduled-jobs-proxy.md), [16 가시성 판단](./concepts/16-authorization-visibility.md) | 랭킹 캐시와 점수 SQL, 기기 쿠키가 바꾸는 시도 키, 새벽 작업의 트랜잭션 위치, 저장 목록의 가시성 |

## 막혔던 점

- **랭킹 글 테스트가 혼자서만 실패**: 조회 기록을 SQL의 `NOW() - INTERVAL 1 MINUTE`으로 넣었더니 "최근 1시간" 인기 글에 안 나왔다. 테스트 DB 컨테이너의 `NOW()`는 UTC라 한국 시간보다 9시간 앞선 시각이 들어갔다. 자바에서 한국 시간으로 만들어 넣었다([59](./concepts/59-hourly-snapshot-ranking.md) 5.6).
- **전체 테스트에서 로그인 테스트 두 개가 실패**: 로그인 응답에 `device` 쿠키가 하나 더 생겨, 쿠키를 "정확히 이것들"로 확인하던 테스트가 깨졌다. 로그인 쿠키만 골라 보도록 고쳤다([60](./concepts/60-device-cookie-lockout.md) 5.4).
- **랭킹 블로거 테스트가 전체 실행에서만 실패**: "1위는 A"를 확인했는데, 다른 테스트가 같은 DB에 만든 블로그 점수가 더 높았다. "A는 순위 안에, 이용 제한한 B는 없음"으로 바꿨다.
- **린트 `set-state-in-effect`**: 랭킹 화면에서 `useEffect` 안에서 바로 상태를 바꾸는 코드가 oxlint에 걸렸다. "받기(`fetchFirst`)"와 "화면에 반영(`apply`)"을 나눴고, 409 뒤 처음부터 다시 받을 때도 같은 두 함수를 쓴다.
- **브라우저 확인에서 Referer**: 헤드리스 Chrome에 `Referer`를 직접 넣었더니 Chrome이 "invalid referrer"로 요청을 취소했다(브라우저는 Referer를 스스로 정한다). 유입 경로는 curl로 확인했다(`search.naver.com` → SEARCH). 그 설정이 남아 다음 화면들까지 막혔던 것도 지우고 다시 확인했다.
- **화면 확인에서 고친 것 두 가지**:
  - 관리 홈의 최근 댓글에서 비밀·숨김·삭제 댓글이 "알 수 없음 · (내용 없음)"으로 보였다. 댓글 화면과 같은 상태 문구("비밀댓글입니다." 등)로 바꿨다.
  - 랭킹·홈·추천의 블로그 카드에서 이름이 오른쪽 끝으로 밀렸다. 카드가 순위 목록용 3칸 grid를 빌려 써서, 4칸(순위·사진·이름·버튼)일 때 사진이 넓은 칸을 차지했다. 카드 전용 배치(`.blog-card`)로 바꿨다.
- **비슷한 글 테스트가 전체 실행에서 실패**: 고치기 검사 테스트를 더하자 `SimilarPostIntegrationTest`가 깨졌다. 혼자 돌리면 통과했다. 테스트는 "먼 글(제주 바다 여행)도 비슷한 글 5개 안에 있다"고 가정했는데, 같은 DB에 다른 테스트가 만든 글이 늘면서 먼 글이 5개 밖으로 밀렸다. 가까운 글이 들어 있는지와, 먼 글이 들어 있을 때만 순서를 보도록 고쳤다. "1위는 A" 랭킹 테스트와 같은 종류의 문제다(테스트끼리 데이터를 나눠 쓴다).
- **확인용 데이터 글자 깨짐**: MySQL 명령줄로 한글 닉네임을 넣을 때 `--default-character-set=utf8mb4`를 빠뜨려 깨졌다. 다시 넣었다.
- **차단 뒤 추천에 갑이 다시 보임**: 확인 중 을을 차단해서 을의 갑 구독이 지워졌고, 그래서 을의 추천에 갑이 나왔다. 버그가 아니라 의도한 동작이다(차단하면 구독 삭제 → 구독 중이 아니니 추천 대상).

## 명세와 다르거나 아직 채우지 않은 것

| 항목 | 지금 | 언제 |
| --- | --- | --- |
| 인기 블로거 갱신 방식 | 1시간마다 도는 작업 대신 정시 칸 캐시(결과는 R-13과 같음) | research.md R-13 구현 메모에 적음 |
| 새벽 작업 | "전날을 누적에 더하기" 대신 지난 7일 다시 모으기·누적 다시 계산 | research.md R-14 구현 메모에 적음 |
| 댓글·방명록 **고치기**의 차단·금칙어 검사 | 처음엔 명세대로 "새로 쓸 때"만 검사했다. 보고에서 물었고 지원이 "고칠 때도 검사"로 정해, 고치기에도 넣고 spec MNG-04·계약을 고쳤다(지우기는 막지 않음) | 2026-10-11 지원 결정, 반영 끝 |
| 금칙어 100개 한도 | 세고 넣기라 두 탭에서 동시에 넣으면 101개가 될 수 있음 | 받아들임([57](./concepts/57-spam-block-banned-words.md) 5.4) |
| 같은 칸 안의 순위 | 칸 기간 안의 행이 지워지면(구독 취소 등) 다시 계산한 값이 조금 다를 수 있음 | 받아들임([59](./concepts/59-hourly-snapshot-ranking.md) 6장) |
| 비밀번호 재설정·메일로 잠금 풀기 | 아직 | T088, SMTP 키를 받은 뒤 |
| 소셜 로그인·연동, 소셜 회원 탈퇴 본인 확인 | 아직 | T099·T100, 카카오·구글 키를 받은 뒤 |

## 직접 해 보기

```bash
./mvnw test -Dtest='BookmarkIntegrationTest,SpamIntegrationTest,StatsIntegrationTest,RankingIntegrationTest,DeviceCookieIntegrationTest'
cd frontend && npx vitest run src/app/stats.test.ts
```

화면에서:

1. 을로 갑의 글 → "☆ 저장" → 마이페이지 → "저장한 글". 갑이 그 글을 비공개로 바꾸면 "볼 수 없는 글"([56](./concepts/56-bookmark-snapshot.md) 7장).
2. 갑으로 관리 → 댓글·방명록 → 을 "차단" → 을이 댓글을 쓰면 "이 블로그에서 차단되었습니다." → 관리 → 스팸·차단에서 해제, 금칙어 추가([57](./concepts/57-spam-block-banned-words.md) 7장).
3. 다른 브라우저로 갑의 블로그를 열고 갑으로 관리 홈 → 오늘 1. 관리 → 통계 › 방문 통계([58](./concepts/58-visit-stats-nightly-batch.md) 7장).
4. 홈의 "인기 블로거"와 "랭킹 전체보기", 구독 피드 아래 "추천 블로그"([59](./concepts/59-hourly-snapshot-ranking.md) 7장).
5. 로그인한 브라우저는 그대로 두고, 다른 곳에서 같은 이메일로 5번 틀린 뒤 원래 브라우저로 로그인([60](./concepts/60-device-cookie-lockout.md) 7장).
