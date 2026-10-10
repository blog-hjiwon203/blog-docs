# 스텝 16. 구독·공유·알림

> 작업: T089, T090, T091, T092, T093, T113 · 코드 브랜치: `step-16-subscribe` · 날짜: 2026-10-11 · 백로그를 크게 묶은 다섯 스텝 중 첫째(2026-10-11 지원 결정)

## 한눈에 보기

독자가 블로그를 구독하고, 구독한 블로그의 새 글을 피드에서 보고, 글 주소를 복사·공유한다. 주인은 구독자에게만 보이는 글을 쓴다. 내 글에 댓글·답글·공감, 새 구독자가 생기면 머리글에 "알림 n"이 뜬다. 테이블(`subscription`, `notification`)은 스텝 1부터 있었고, 구독자 공개를 판단하는 코드는 스텝 3부터 있었다.

| 작업 | 만든 것 | 핵심 파일 |
| --- | --- | --- |
| T089 구독 (SUB-01, SUB-03) | `PUT`·`DELETE /api/blogs/{blogId}/subscription`: 회원만, 멱등(`INSERT IGNORE`·`DELETE`), 자기 블로그 400, 볼 수 없거나 이사한 블로그 404, `{ subscribed, subscriberCount }` | `subscription/application/SubscriptionService`, `SubscriptionRepository.insertIfAbsent`, `SubscriptionController` |
| T090 구독 피드 (SUB-02) | `GET /api/feed?cursor=`: 구독한 블로그의 볼 수 있는 글(구독자 공개 포함) 최신순 커서 20 | `FeedService`, `FeedController` |
| T091 구독자 공개 (POST-12) | 글 저장·공개 범위 바꾸기·일괄 변경에서 `SUBSCRIBERS`를 막던 400 세 곳을 지움. 화면: 글쓰기·글 상세·글 관리의 "구독자 공개", 안내 화면의 구독 버튼(구독하면 바로 본문) | `PostSaveRequest`, `VisibilityRequest`, `ManagePostController`, `PostPage.tsx`, `PostWritePage.tsx` |
| T092 공유 (SOC-02) | 글 상세 "주소 복사"(http 개발 주소에서도 되게 대안 포함), X·페이스북 공유 주소 | `app/share.ts`, `components/ShareButtons.tsx` |
| T093 화면 | 블로그 프로필 상자의 구독 버튼, 플랫폼 머리글 "구독 피드"와 `/feed`(더보기, 빈 피드 안내) | `components/SubscribeButton.tsx`, `pages/feed/FeedPage.tsx`, `PlatformHeader.tsx` |
| T113 알림 (SUB-04) | 댓글·답글·공감·구독 때 같은 트랜잭션에서 만들기(내가 한 일·연타·중복 제외), 목록(대상이 지워졌거나 볼 수 없으면 뺌, 링크는 그 블로그 주소)·안 읽은 수·읽음·모두 읽음, `/api/me`의 `unreadNotificationCount`, 세 머리글의 "알림 n", `/me/notifications` | `notification/`, `CommentService`, `LikeService`, `MeService`, `pages/me/NotificationsPage.tsx`, `app/notifications.ts` |

## 요청 흐름

```
[구독] 을이 갑 블로그 "구독하기" → PUT /api/blogs/7/subscription
        → 볼 수 있는 블로그? → 자기 블로그? → INSERT IGNORE ─ 1행이면 갑에게 SUBSCRIBE 알림
        → { subscribed: true, subscriberCount: 1 } → 버튼 "구독 중", "구독자 1명"

[구독자 공개] 정이 갑의 구독자 공개 글 → GET /api/posts/23 → 403 SUBSCRIBERS_ONLY(블로그 이름만)
        → "구독자 공개 글입니다" + 구독하기 → PUT …/subscription → reloadKey + 1 → GET /api/posts/23 → 200 본문

[피드] 을 → 머리글 "구독 피드" → GET /api/feed → visibleTo(을) AND EXISTS(을의 구독, 글의 블로그) → 20 + 다음 커서

[알림] 병이 갑의 글에 댓글 → 같은 트랜잭션에서 INSERT notification(갑, COMMENT, 댓글 95)
        갑 → 머리글 "알림 1"(/api/me의 unreadNotificationCount) → /me/notifications
        → GET /api/me/notifications → 댓글 95가 있고 갑이 그 글을 볼 수 있나 → 링크 http://{갑 블로그}/12#comment-95
        → 누르면 PUT …/{id}/read → 그 주소로
```

## 이 스텝을 이해하려면 (읽는 순서)

| 순서 | 개념 문서 | 이 스텝에서 쓰인 곳 |
| --- | --- | --- |
| 1 | [51 구독과 알림](./concepts/51-subscription-notification.md) (새 문서) | 멱등한 PUT·DELETE와 토글을 만들지 않은 이유, `INSERT IGNORE`의 넣은 행 수로 알림을 한 번만, 알림을 같은 트랜잭션에서 만들기와 다른 방법, 쓸 때 정하는 문구·읽을 때 정하는 링크와 가시성, 거르는 커서 목록, 404와 403(구독자 공개), 클립보드와 보안 컨텍스트 |
| 2 | (복습) [17 멱등성](./concepts/17-idempotency-redis.md), [16 인가와 가시성](./concepts/16-authorization-visibility.md) | POST의 연타 방지 키와 PUT의 멱등, `visibleTo`가 스텝 3부터 구독을 보던 코드 |
| 3 | (복습) [42 두 번째 DB와 비동기 이벤트](./concepts/42-second-db-async-events.md), [32 블로그 안 검색](./concepts/32-search-like.md) 5.9 | 비동기로 하지 않은 이유의 비교 대상, 피드의 범위(`visibleTo`)와 EXISTS |

## 막혔던 점

- **판단은 이미 있었다**: 구독자 공개를 열려고 보니, 가시성 판단(`PostVisibilityPolicy`, `PostSpecifications.visibleTo`)이 스텝 3부터 구독을 보고 있어서 서버에서 바꾼 것은 400 세 곳을 지운 것뿐이었다. 대신 "구독자 공개는 400"을 기대하던 기존 테스트 세 곳을 새 규칙에 맞게 고쳤다.
- **같은 일로 알림 두 개**: 처음 생각에는 답글이면 부모 작성자에게 REPLY, 글 주인에게 COMMENT를 늘 보냈다. 내 글의 내 댓글에 답글이 달리면 같은 답글로 두 개가 온다. 주인이 부모 작성자이면 REPLY 하나만 보내게 했다(`replyNotifiesParentAuthorAndOwnerOnce`).
- **알림 수와 목록 개수가 다를 수 있음**: 목록은 지워졌거나 볼 수 없게 된 대상의 알림을 빼지만 안 읽은 수는 행 수다. 셀 때마다 대상을 확인하면 머리글이 무거워져서 받아들이고 API 명세에 적었다.
- **컴포넌트 파일에서 함수 내보내기**: 알림 버튼 글자 함수를 `PlatformHeader.tsx`에서 내보냈더니 린터가 Fast Refresh 경고를 냈다. `app/notifications.ts`로 옮기고 단위 테스트를 붙였다.
- **"모두 읽음" 뒤에도 머리글은 "알림 2"**: 머리글은 화면을 열 때 받은 내 정보(`/api/me`)의 수를 그렸다. 스텝 끝의 API 대조에서 `GET /api/me/notifications/unread-count`를 부르는 화면이 없다고 나와 살펴보다 찾았다. 알림 화면이 읽은 뒤 브라우저 이벤트(`notifications-changed`)를 보내고, 머리글이 그 API로 수를 다시 받게 했다(`app/useUnreadCount.ts`). 브라우저에서 "알림 2" → "모두 읽음" → "알림"을 확인했다.
- **복사가 실패로 보임**: 헤드리스 Chrome에서 스크립트로 `button.click()`을 부르면 "복사하지 못했습니다". 브라우저가 사용자 입력 중에만 복사를 허락하기 때문이다. 실제 마우스 이벤트(`Input.dispatchMouseEvent`)로 누르니 "주소를 복사했습니다"([51](./concepts/51-subscription-notification.md) 5.7).
- **화면은 실제 브라우저로 확인**: 8081 확인용 서버와 헤드리스 Chrome으로
  - 을: 갑 블로그 프로필 상자 "구독하기" → "구독 중", "구독자 0명" → "구독자 1명"
  - 정: 갑의 구독자 공개 글(23) → "구독자 공개 글입니다"와 "구독하기", 제목 없음 → 누르면 "구독자만 보는 글"과 본문
  - 정: X·페이스북 공유 링크가 글 주소(`b13a22029.blog.test:8081/23`)를 담음
  - 을: 플랫폼 머리글 "홈, 구독 피드, … 알림, 마이페이지" → `/feed`에 "구독자만 보는 글", "공개 글"
  - 갑: 블로그 머리글 "알림 2" → 정·을의 구독 알림(●) → 하나를 누르면 갑 블로그로, 돌아오면 "알림 1", "모두 읽음"이면 ● 없음
  - 360px 블로그 머리글 버튼이 줄바꿈되어 가로 넘침 없음
  - 확인용으로 갑 블로그에 구독자 공개 글 23을 만들었고, 을·정이 갑 블로그를 구독한 상태로 개발 DB에 남아 있다.

## 명세와 다르거나 아직 채우지 않은 것

| 항목 | 지금 | 언제 |
| --- | --- | --- |
| 구독·피드·알림 API의 세부(멱등, 404·400, 알림을 언제 만드나, 목록이 20개보다 적을 수 있음, 안 읽은 수의 범위) | API 명세에 적음 | 반영함 |
| 제재·해제 알림(SANCTION) | 알림 종류와 링크(마이페이지)는 준비됨. 보낼 곳(관리자 정지)이 아직 없음 | 스텝 18 T094에 붙임(tasks에 적음) |
| 추천 블로그(피드 오른쪽, 목업 feed 2번) | 없음 | 스텝 20 T080·T081 |
| 블로그 사이드바의 구독 모듈(BLOG-05) | 구독 버튼은 블로그 프로필 상자에 있음 | 스텝 19 T086 |
| 차단된 회원의 구독 403(MNG-04) | 없음 | 스텝 20 T084 |
| 방명록 알림 | 알림 종류에 없어 보내지 않음(ERD, SUB-04) | 그대로 |
| 카카오톡 공유 | 카카오 SDK·앱 키가 필요해 X·페이스북만 | 필요하면 |

## 직접 해 보기

```bash
./mvnw test -Dtest='SubscriptionIntegrationTest,NotificationIntegrationTest'
cd frontend && npx vitest run src/app/share.test.ts src/app/notifications.test.ts && cd ..
```

화면: [51](./concepts/51-subscription-notification.md) 7.1(구독 → 구독자 공개 글 → 피드 → 알림 → 주소 복사), 7.2(구독을 세 번 보내도 알림 하나).
