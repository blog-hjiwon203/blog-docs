# 51. 구독과 알림: 멱등한 요청, 부수 효과, 읽을 때 거르기

> 관련 스텝: [스텝 16](../step-16.md) (T089~T093, T113) · 관련 개념: [17 멱등성과 Redis](./17-idempotency-redis.md), [16 인가와 가시성](./16-authorization-visibility.md), [29 댓글 설계](./29-comments-design.md), [33 격리 수준과 데드락](./33-isolation-deadlock.md), [42 두 번째 DB와 비동기 이벤트](./42-second-db-async-events.md), [08 페이지 처리](./08-pagination.md), [19 React Router와 API 클라이언트](./19-react-router-api-client.md), [43 공유 미리보기](./43-open-graph-preview.md)

## 1. 이 문서로 배우는 것

- 구독처럼 "켜고 끄는" 기능을 **멱등한 PUT·DELETE**로 만드는 이유와, 글 쓰기처럼 연타 방지 키가 필요한 POST와의 차이
- `INSERT IGNORE`가 돌려주는 **넣은 행 수**로 "새로 생겼나"를 알아내고, 그때만 부수 효과(알림)를 일으키기
- 알림 같은 **부수 효과**를 어디서 만드나: 같은 트랜잭션에서 직접 부르기 vs 이벤트 vs 비동기
- 무엇을 **쓸 때** 정해 두고(알림 문구), 무엇을 **읽을 때** 정하나(갈 주소, 아직 볼 수 있나)
- 읽을 때 걸러 내는 커서 목록: 한 묶음이 20개보다 적어질 때 다음 커서를 어디서 잡나
- 구독자 공개 글: 404(없음)와 403(있지만 조건이 필요함)을 가르는 기준
- 브라우저 클립보드와 **보안 컨텍스트**, 개발 주소(http)에서의 대안

## 2. 왜 필요한가

명세 US6(구독·피드·구독자 공개·공유)과 US12(알림)의 수용 시나리오:

- B가 A 블로그를 **구독하고 해제**하면 A의 구독자 수가 1 오르고 다시 내려간다. **연달아 눌러도 한 번으로** 센다(SUB-01).
- 구독한 블로그들의 새 글이 피드에 최신순 20개씩 더보기로, **중복·누락 없이** 보인다(SUB-02).
- 구독자 공개 글은 구독자와 주인만 본문을 본다. 구독하지 않은 C에게는 목록·검색·홈·인기 글·피드·글 수에서 빠지고, **링크로 직접 열면 404 대신 "구독자 공개 글입니다"와 구독 버튼**이 보인다(POST-12).
- 글 주소 복사나 SNS 공유를 누르면 **바뀌지 않는 글 주소**가 공유된다(SOC-02).
- 내 글에 댓글·답글·공감, 새 구독자가 생기면 **알림**이 생기고, 읽음 처리할 수 있다(SUB-04).

하나씩은 단순해 보이지만, 같이 놓으면 질문이 생긴다. 구독 버튼을 두 번 누르면 알림이 두 번 가나? 알림을 보낸 뒤 그 글이 지워지면? 알림의 "갈 주소"를 저장해 둘까 매번 만들까? 이 문서는 그 질문들의 답이다.

## 3. 기본 개념

### 3.1 멱등(idempotent)

같은 요청을 한 번 보내든 열 번 보내든 **서버의 상태가 같으면** 멱등하다고 한다([17](./17-idempotency-redis.md)).

| 요청 | 멱등인가 | 이유 |
| --- | --- | --- |
| `PUT /api/blogs/7/subscription` | 예 | "7번 블로그를 구독한 상태로 만들어라". 이미 구독이면 그대로 |
| `DELETE /api/blogs/7/subscription` | 예 | "구독하지 않은 상태로". 이미 아니면 그대로 |
| `POST /api/posts` | 아니오 | "글을 하나 더 만들어라". 두 번이면 두 개 |
| `POST /api/posts/12/comments` | 아니오 | 댓글이 두 개 |

HTTP 명세(RFC 9110)도 PUT·DELETE를 멱등한 메서드로, POST를 그렇지 않은 메서드로 정한다. 그래서 이 프로젝트에서

- 글·댓글·방명록 쓰기(POST)는 `Idempotency-Key`를 받아 같은 키의 두 번째 요청에 처음 응답을 돌려준다(스텝 3·6).
- 구독(PUT·DELETE)과 공감(PUT·DELETE, 스텝 7)은 키가 필요 없다. 요청 자체가 "상태를 이렇게 만들어라"라서, 두 번 와도 결과가 같다.

**"구독 토글" API를 만들지 않은 이유**: `POST /subscription/toggle` 하나로 켜고 끄면, 연타한 두 요청이 "켜고 → 끄고"가 되어 사용자가 원한 것과 반대가 된다. 상태를 말하는 PUT·DELETE는 순서가 섞여도 마지막에 보낸 뜻대로 끝난다.

### 3.2 "있나 보고 넣기"의 틈과 `INSERT IGNORE`

멱등하게 만들려면 "이미 있으면 넣지 않기"가 필요하다. 두 번에 나눠 하면 틈이 생긴다.

```
요청 1: SELECT … 없음 ────────────── INSERT  ✔
요청 2:        SELECT … 없음 ──────────────── INSERT  ✘ UNIQUE(member_id, blog_id) 위반 → 500
```

한 문장으로 하면 틈이 없다. MySQL의 `INSERT IGNORE`는 UNIQUE에 걸리는 행을 **오류 없이 건너뛰고**, 실제로 넣은 행 수를 돌려준다(넣었으면 1, 건너뛰었으면 0). 공감(스텝 7)과 같은 방법이다.

이 "넣은 행 수"가 이번 스텝에서 하나 더 쓸모가 있다. **새로 구독했을 때만 알림을 보낸다.** 연타한 두 번째 요청은 0을 받으니 알림을 만들지 않는다.

### 3.3 부수 효과(side effect)를 어디서 일으키나

"댓글을 쓰면 글 주인에게 알림"에서 알림은 댓글 쓰기의 **부수 효과**다. 만드는 방법은 크게 셋이다.

| 방법 | 어떻게 | 좋은 점 | 나쁜 점 |
| --- | --- | --- | --- |
| 직접 부르기 | `CommentService.write`가 `notificationService.commented(...)`를 부른다 | 단순, 같은 트랜잭션이라 댓글이 실패하면 알림도 없음 | 댓글 기능이 알림 기능을 안다(의존) |
| 이벤트(같은 트랜잭션) | 댓글이 "댓글이 생겼다" 이벤트를 내고, 알림이 듣는다(`@EventListener`) | 댓글이 알림을 모른다 | 흐름이 코드에서 잘 안 보인다 |
| 커밋 뒤 비동기 | `@TransactionalEventListener(AFTER_COMMIT)` + `@Async` | 알림이 느리거나 실패해도 댓글은 빠르게 끝남 | 알림이 빠질 수 있다(재시도 필요), 테스트가 어렵다 |

이 프로젝트는 **직접 부르기**를 골랐다. 알림은 행 하나 INSERT라 빠르고, "댓글은 됐는데 알림은 없음"이 생기지 않는다. 스텝 10의 임베딩(외부 Ollama를 부르고 몇 초 걸림)은 셋째 방법을 썼다([42](./42-second-db-async-events.md)). **오래 걸리거나 밖으로 나가는 일**이면 비동기, **같은 DB에 한 줄 쓰는 일**이면 같은 트랜잭션, 이것이 이 프로젝트의 기준이다.

### 3.4 쓸 때 정하는 것, 읽을 때 정하는 것

알림 한 줄에는 "누가 무엇을 했다"(문구)와 "누르면 갈 곳"(링크)이 있다.

- **문구는 쓸 때 정한다.** "하늘님이 \"Spring 정리\"에 댓글을 남겼습니다." 나중에 하늘이 닉네임을 바꾸거나 글 제목이 바뀌어도, 그때 일어난 일을 그대로 보여 주는 것이 자연스럽다(메일함의 옛 메일 제목이 바뀌지 않는 것과 같다). 그래서 `notification.message`에 저장한다.
- **링크와 "아직 볼 수 있나"는 읽을 때 정한다.** 글이 지워졌거나, 비공개로 바뀌었거나, 블로그가 이용 제한되면 그 알림은 목록에서 빠져야 한다(contracts). 저장해 둔 링크로는 이것을 알 수 없다. 대상 종류와 번호(`target_type`, `target_id`)만 저장하고, 읽을 때 그 대상을 다시 찾아 가시성을 판단한다. 주소 모양(서브도메인, 포트)도 요청에 따라 달라서(개발 `:8080`, `:5173`) 저장하지 않는다.

### 3.5 걸러 내는 커서 목록

알림 목록은 "최신순 20개씩 더보기"(커서, [08](./08-pagination.md))인데, 읽을 때 일부를 빼야 한다.

```
DB에서 21개 읽음 (하나 더 = 다음이 있나)
 → 앞 20개 중 볼 수 없는 3개를 뺌 → 17개 보냄
 → 다음 커서 = 20번째 "읽은" 행의 (createdAt, id)
```

- 다음 커서를 **보낸 것의 마지막(17번째)**으로 잡으면, 18~20번째로 읽었다가 뺀 행 다음부터가 아니라 그 앞부터 다시 읽게 되어, 뺀 행을 또 읽고 또 뺀다(낭비, 경우에 따라 같은 묶음 반복). **읽은 것의 마지막**으로 잡아야 한다.
- 대가: 한 묶음이 20개보다 적을 수 있다. 다 빠지면 빈 묶음에 "더보기"가 남을 수도 있다. 알림은 대부분 볼 수 있는 대상이라 받아들였다. 정확히 20개를 채우려면 모자랄 때 더 읽는 반복이 필요하다.

### 3.6 404와 403: "없음"과 "있지만 조건이 필요함"

이 프로젝트는 "볼 수 없는 글은 로그인 여부와 상관없이 404"가 원칙이다(헌법 II, [16](./16-authorization-visibility.md)). 남의 비공개 글이 있다는 사실조차 알려 주지 않는다.

구독자 공개 글은 예외로 **403 `SUBSCRIBERS_ONLY`**다(spec 결정 Q4). 이 글은 숨기려는 것이 아니라 **구독을 권하는** 것이라, "구독하면 볼 수 있다"고 알려야 한다. 대신 제목·본문은 응답에 넣지 않고 블로그 이름만 준다. 스텝 3부터 가시성 판단이 이것을 알고 있었고(`PostAccess.SubscribersOnly`), 이번에는 화면의 안내에 구독 버튼을 달았다.

### 3.7 보안 컨텍스트(secure context)

브라우저의 일부 기능은 **HTTPS나 localhost**에서만 쓸 수 있다. 엿듣는 사람이 있을 수 있는 평문 HTTP 페이지에 강한 기능을 주지 않으려는 것이다. 클립보드 쓰기(`navigator.clipboard.writeText`)가 그중 하나다. 개발 주소 `http://alpha.blog.test`는 보안 컨텍스트가 아니라 `navigator.clipboard`가 없다. 스텝 5에서 `crypto.randomUUID`가 없던 것과 같은 사정이다([19](./19-react-router-api-client.md) 5.4).

## 4. 동작 원리

```
[구독]  을이 갑 블로그 "구독하기"
  PUT /api/blogs/7/subscription
    → 블로그 7: 볼 수 있나·이사하지 않았나(아니면 404) → 자기 블로그면 400
    → INSERT IGNORE subscription(을, 7) ─ 1행? ── 예 → INSERT notification(갑, SUBSCRIBE, BLOG 7, "을님이 …구독")
                                         └ 0행(이미 구독) → 알림 없음
    → { subscribed: true, subscriberCount: COUNT(*) }

[댓글]  병이 갑의 글 12에 을의 댓글 88로 답글
  POST /api/posts/12/comments { parentId: 88 }  (한 트랜잭션)
    → INSERT comment 95, 글 12 comment_count + 1
    → 알림: 을(부모 작성자)에게 REPLY(COMMENT 95), 갑(글 주인)에게 COMMENT(COMMENT 95)
           갑 == 부모 작성자이면 REPLY 하나만, 병 == 받는 사람이면 보내지 않음

[알림 목록]  갑이 /me/notifications
  GET /api/me/notifications
    → notification WHERE receiver = 갑 ORDER BY created_at DESC, id DESC LIMIT 21
    → 행마다: COMMENT → 댓글이 있나·지우지 않았나·글을 갑이 볼 수 있나 → 링크 {블로그}/12#comment-95
              POST → 글을 볼 수 있나 → {블로그}/12
              BLOG → 블로그를 볼 수 있나 → {블로그}/
    → 볼 수 없는 것은 빼고, 다음 커서는 읽은 20번째 행
  누르면 PUT /api/me/notifications/{id}/read → link로 이동(다른 호스트라 페이지를 새로 엶)
```

## 5. 이 프로젝트에서는

### 5.1 구독: `subscription/application/SubscriptionService`

```java
@Transactional
public SubscriptionResult subscribe(Long blogId, LoginMember member) {
    Blog blog = subscribable(blogId, member);
    if (blog.isOwnedBy(member.id())) {
        throw BusinessException.invalidField("blogId", "자기 블로그는 구독할 수 없습니다.");
    }
    if (subscriptionRepository.insertIfAbsent(member.id(), blog.getId()) == 1) {
        // 새로 구독했을 때만 주인에게 알린다(연타한 두 번째 요청은 알리지 않음, SUB-04)
        notificationService.subscribed(blog, memberRepository.getReferenceById(member.id()));
    }
    return new SubscriptionResult(true, subscriptionRepository.countByBlogId(blog.getId()));
}

/** 이사한 블로그는 새 블로그를 구독하게 한다(옛 블로그는 301되는 자리라 404). */
private Blog subscribable(Long blogId, LoginMember member) {
    Long viewerId = member == null ? null : member.id();
    return blogRepository.findWithMemberById(blogId)
            .filter(blog -> blogVisibilityPolicy.canView(blog, viewerId) && !blog.isMoved())
            .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));
}
```

- **블로그를 번호로 받는다**(`/api/blogs/{blogId}/subscription`). 구독 버튼은 블로그 화면뿐 아니라 검색 결과·피드(스텝 20의 추천 블로그)에도 놓일 수 있어, 어느 호스트에서 불러도 같도록 Host가 아니라 번호로 가리킨다(API 명세의 Host `*`).
- 볼 수 없는 블로그는 **404**다. 이용 제한된 블로그를 번호로 구독해서 "이 번호의 블로그가 있다"는 것을 알 수 없게 한다.
- **구독자 수는 매번 센다**(`COUNT(*)`). 글의 공감 수처럼 블로그 행에 칸을 두고 더하고 빼는 방법(비정규화 카운터, [29](./29-comments-design.md) 3.5)도 있지만, ERD의 `blog`에는 구독자 수 칸이 없고 `subscription(blog_id)` 조회는 외래 키 인덱스로 빠르다. 많아지면 칸을 더하는 것이 다음 단계다.
- `memberRepository.getReferenceById(...)`: 회원을 SELECT하지 않고 **프록시**만 만든다. 알림 문구에 닉네임이 필요해 `getNickname()`을 부르는 순간 그때 읽는다(같은 트랜잭션이라 가능).

```java
// subscription/domain/SubscriptionRepository.java
@Modifying
@Query(value = "INSERT IGNORE INTO subscription (member_id, blog_id) VALUES (:memberId, :blogId)", nativeQuery = true)
int insertIfAbsent(@Param("memberId") Long memberId, @Param("blogId") Long blogId);
```

- `nativeQuery = true`: `INSERT IGNORE`는 MySQL 문법이라 JPQL로 쓸 수 없다. 이 프로젝트는 MySQL만 쓰므로(H2를 쓰지 않음, CLAUDE.md) 괜찮다.
- `@Modifying`: SELECT가 아닌 쿼리라는 표시. 돌려주는 `int`가 바뀐 행 수다.

**`IGNORE`가 건너뛰는 것은 UNIQUE만이 아니다.** 외래 키 위반, 칸 길이 초과 같은 다른 오류도 경고로 바꾸고 0을 돌려준다. 그래서 넣기 전에 블로그가 있는지(`subscribable`)를 먼저 확인한다. 없는 블로그 번호로 0이 나와 "이미 구독 중"처럼 보이는 일이 없게.

### 5.2 피드: `subscription/application/FeedService`

```java
Specification<Post> subscribed = (root, query, cb) -> {
    Subquery<Long> mine = query.subquery(Long.class);
    Root<Subscription> subscription = mine.from(Subscription.class);
    mine.select(subscription.get("id")).where(
            cb.equal(subscription.get("blog"), root.get("blog")),
            cb.equal(subscription.get("member").get("id"), memberId));
    return cb.exists(mine);
};
Specification<Post> condition = PostSpecifications.visibleTo(memberId, LocalDateTime.now(clock))
        .and(subscribed);
```

- "구독한 블로그의 글" = 글의 블로그에 대해 내 구독 행이 **있는**(EXISTS) 글. 구독 표와 조인하면 같은 글이 두 번 나올 일은 없지만(구독은 블로그마다 하나), EXISTS가 뜻을 그대로 말한다.
- 범위는 홈 최신 글과 같은 `visibleTo(memberId, …)`다([32](./32-search-like.md) 5.9). 구독자 공개 글도 나온다(구독했으니까). 구독한 블로그가 이용 제한되면 그 글은 빠진다.
- 커서는 `(publishedAt, id)`로 홈과 같다. 읽는 중에 새 글이 올라와도 이미 받은 것보다 "앞"에 생기므로 다음 묶음과 겹치지 않는다(시나리오 2의 "중복·누락 없이").

### 5.3 구독자 공개 열기 (T091)

서버에서 바뀐 것은 **막고 있던 400 세 곳을 지운 것**뿐이다: 글 저장(`PostSaveRequest.checkSupported`), 공개 범위 바꾸기(`VisibilityRequest`), 일괄 변경(`ManagePostController`). 구독자 공개를 판단하는 쪽은 스텝 3(T011)부터 이미 구독을 보고 있었다.

```java
// global/visibility/PostSpecifications.visibleTo (스텝 3부터)
Predicate audience = cb.equal(post.get("visibility"), Visibility.PUBLIC);
if (viewerId != null) {
    Subquery<Long> subscribed = query.subquery(Long.class);
    ...
    audience = cb.or(audience, cb.and(
            cb.equal(post.get("visibility"), Visibility.SUBSCRIBERS), cb.exists(subscribed)));
}
```

판단을 먼저 만들고 입력을 나중에 연 순서가 좋았다. 구독이 없을 때 구독자 공개 글을 만들 수 있었다면, 아무도 볼 수 없는 글이 생겼을 것이다(review C-7, 스텝 5의 400).

화면의 안내는 이렇다.

```tsx
// frontend/src/pages/post/PostPage.tsx
<SubscribeButton blogId={blogState.blog.id} me={me} subscribed={blogState.blog.viewer.subscribed}
                 onChange={(subscribed, subscriberCount) => {
                   setBlog({ ...blogState.blog, subscriberCount,
                     viewer: { ...blogState.blog.viewer, subscribed } })
                   if (subscribed) {
                     setReloadKey((key) => key + 1)
                   }
                 }} />
```

- 403 응답에는 블로그 이름만 있고 번호가 없다. 블로그 번호는 같은 화면이 이미 읽은 `GET /api/blog`(useBlog)에 있다.
- 구독하면 `reloadKey`를 올려 글을 다시 받는다. 글을 불러오는 `useEffect`의 의존 배열에 `reloadKey`를 넣어 두면, 값이 바뀔 때 effect가 다시 돈다. "다시 받기 버튼"을 만들지 않고 상태 하나로 다시 부르는 React의 흔한 방법이다.
- 비회원에게는 버튼 대신 "로그인하고 구독하기"(로그인 뒤 이 글로 돌아옴, 시나리오 3 "비회원이면 로그인 안내가 함께").

### 5.4 알림 만들기: `notification/application/NotificationService`

```java
public void commented(Comment comment) {
    Member author = comment.getMember();
    Post post = comment.getPost();
    Long ownerId = post.getBlog().getMember().getId();
    Long parentAuthorId = comment.getParent() == null ? null : comment.getParent().getMember().getId();
    if (parentAuthorId != null) {
        send(author, parentAuthorId, NotificationType.REPLY, NotificationTargetType.COMMENT, comment.getId(),
                author.getNickname() + "님이 내 댓글에 답글을 남겼습니다.");
    }
    if (!ownerId.equals(parentAuthorId)) {
        send(author, ownerId, NotificationType.COMMENT, NotificationTargetType.COMMENT, comment.getId(),
                author.getNickname() + "님이 \"" + post.getTitle() + "\"에 댓글을 남겼습니다.");
    }
}

private void send(Member actor, Long receiverId, NotificationType type, NotificationTargetType targetType,
                  Long targetId, String message) {
    if (receiverId.equals(actor.getId())) {
        return;
    }
    notificationRepository.save(Notification.of(receiverId, type, targetType, targetId, message));
}
```

- **같은 일로 두 번 알리지 않는다.** 내 글의 내 댓글에 답글이 달리면, 나는 "글 주인"이자 "부모 댓글 작성자"다. 둘 다 보내면 같은 답글로 알림이 두 개다. 더 구체적인 REPLY 하나만 보낸다.
- **내가 한 일은 나에게 알리지 않는다**(`send`의 첫 줄). 내 글에 내가 댓글을 달거나 공감해도 알림이 없다.
- 대상은 **댓글 번호**다(`COMMENT`). 글 번호로 하면 "그 댓글로 바로 가기"(`#comment-95`)를 만들 수 없고, 댓글이 지워졌는지도 알 수 없다.
- 공감은 `LikeService.like`에서 `insertIfAbsent == 1`일 때만 `liked`를 부른다(5.1과 같은 이유).
- 방명록에는 알림을 보내지 않는다. ERD의 알림 종류(`ck_notification_type`)에 방명록이 없다. 명세 SUB-04도 "내 글에 댓글·답글·공감, 새 구독자, 제재·해제"다.
- `Notification.of`는 문구가 255자(칸 길이)를 넘으면 잘라 "…"를 붙인다. 긴 글 제목이 들어가도 INSERT가 실패하지 않게.

### 5.5 알림 읽기: 읽을 때 거르기

```java
private Optional<NotificationView> view(Notification notification) {
    Long receiverId = notification.getReceiverId();
    return switch (notification.getTargetType()) {
        case COMMENT -> commentRepository.findWithPostById(notification.getTargetId())
                .filter(comment -> !comment.isDeleted())
                .flatMap(comment -> readable(comment.getPost(), receiverId)
                        .map(blog -> new NotificationView(notification, blog,
                                "/" + comment.getPost().getId() + "#comment-" + comment.getId())));
        case POST -> { … postVisibilityPolicy.decide(notification.getTargetId(), null, receiverId) … }
        case BLOG -> blogRepository.findWithMemberById(notification.getTargetId())
                .filter(blog -> blogVisibilityPolicy.canView(blog, receiverId) && !blog.isMoved())
                .map(blog -> new NotificationView(notification, blog, "/"));
        case MEMBER -> Optional.of(new NotificationView(notification, null, "/me"));
    };
}
```

- 글·댓글은 **글 상세와 같은 가시성 판단**(`PostVisibilityPolicy.decide`)을 쓴다. 받는 사람이 그 글을 열 수 있을 때만 알림이 남는다. 알림을 받은 뒤 글이 비공개로 바뀌면 사라진다.
- `switch`가 `enum`의 모든 값을 다루므로 `default`가 없다. 새 대상 종류를 더하면 컴파일러가 빠진 갈래를 알려 준다.
- 링크는 컨트롤러가 `BlogHostResolver.blogUrl(request, blog, path)`로 만든다. 요청과 같은 프로토콜·포트에 그 블로그의 서브도메인을 붙인다. `MEMBER`(제재, 스텝 18)는 플랫폼의 마이페이지다(`platformUrl`).
- 대가: 알림 20개를 읽으면 대상 확인 쿼리가 알림마다 나간다(최대 20번 남짓). 알림 화면은 자주 열지 않고 한 묶음이 작아서 받아들였다. 많아지면 종류별로 대상 번호를 모아 한 번에 읽는다(작성자 사진처럼, [50](./50-shared-rules-comment-guestbook.md) 5.2).

**안 읽은 수는 거르지 않는다.** `countByReceiverIdAndReadAtIsNull`은 행 수만 센다. 그래서 대상이 지워진 알림이 남아 있으면 머리글은 "알림 2"인데 목록에는 1개일 수 있다. 정확히 하려면 셀 때도 모든 대상을 확인해야 해서, 머리글을 그릴 때마다 무거워진다. "모두 읽음"을 누르면 맞춰진다. 이 차이는 API 명세에 적었다.

### 5.6 머리글의 알림 수

`GET /api/me`의 `unreadNotificationCount`는 스텝 4(내 정보 API)부터 칸만 있고 늘 0이었다(스텝 13b의 `null` 응답 칸과 같은 종류, [49](./49-requirement-traceability.md) 3.4). 이번에 실제 수를 넣었다. 머리글은 이미 `useMe()`로 내 정보를 받으므로, 알림 수를 위해 API를 하나 더 부르지 않는다. 별도 `GET /api/me/notifications/unread-count`도 계약대로 만들었다(다른 화면이 수만 다시 받을 때).

```ts
// frontend/src/app/notifications.ts
export function notificationLabel(unread: number): string {
  return unread > 0 ? `알림 ${unread > 99 ? '99+' : unread}` : '알림'
}
```

처음에는 이 함수를 `PlatformHeader.tsx`에 두고 내보냈는데, 린터(oxlint `only-export-components`)가 "컴포넌트 파일이 컴포넌트가 아닌 것을 내보내면 개발 중 화면 새로 고침(Fast Refresh)이 페이지 전체를 다시 불러온다"고 경고해 `app/`으로 옮겼다(스텝 3의 같은 규칙, [19](./19-react-router-api-client.md) 5.7).

### 5.7 공유: `app/share.ts`

```ts
export async function copyText(text: string): Promise<boolean> {
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text)
      return true
    } catch {
      // 권한 거부 등은 아래 방법으로 한 번 더
    }
  }
  const area = document.createElement('textarea')
  area.value = text
  ...
  area.select()
  try {
    return document.execCommand('copy')
  } finally {
    document.body.removeChild(area)
  }
}
```

- 보안 컨텍스트면 표준 `navigator.clipboard`, 아니면(개발 주소) 보이지 않는 입력칸에 넣고 골라서 `execCommand('copy')`. `execCommand`는 오래된 방법이라 문서에서 "쓰지 말 것"(deprecated)으로 표시돼 있지만, 브라우저들은 아직 지원하고 http 페이지에서 되는 거의 유일한 방법이다.
- **사용자가 직접 누른 클릭에서만 복사된다.** 브라우저는 페이지가 몰래 클립보드를 바꾸지 못하게, 사용자 입력(클릭·키) 처리 중에만 복사를 허락한다. 헤드리스 Chrome으로 확인할 때 스크립트로 `button.click()`을 부르면 실패했고, 실제 마우스 이벤트(`Input.dispatchMouseEvent`)로 누르면 "주소를 복사했습니다"가 나왔다. 실패하면 화면에 주소를 그대로 보여 줘 손으로 복사할 수 있게 했다.
- 공유 주소는 `{지금 블로그 주소}/{글 번호}`다. 글 주소에 제목이 들어가지 않아, 제목을 고쳐도 공유한 링크가 그대로 산다(시나리오 4의 "바뀌지 않는 글 주소").
- SNS 버튼은 각 서비스의 공유 주소(X `twitter.com/intent/tweet`, 페이스북 `sharer.php`)를 새 창으로 연다. 카카오톡 공유는 카카오 SDK와 앱 키가 필요해 넣지 않았다. 공유된 링크의 미리보기 카드는 스텝 11의 Open Graph가 만든다([43](./43-open-graph-preview.md)).

### 5.8 테스트

| 테스트 | 확인하는 것 |
| --- | --- |
| `SubscriptionIntegrationTest.subscribeAndUnsubscribeAreIdempotentAndCountFollows` | 구독 두 번 → 1명, `viewer.subscribed`, 해제 두 번 → 0명 |
| `onlyMembersOtherThanOwnerCanSubscribeVisibleBlogs` | 비회원 401, 자기 블로그 400, 없는 번호·이용 제한 404 |
| `feedShowsVisiblePostsOfSubscribedBlogsNewestFirstWithCursor` | 비회원 401, 구독 전 빈 피드, 구독한 블로그의 공개 글만 20 + 1, 비공개·남의 블로그 제외, 다음 커서 |
| `subscribersOnlyPostIsForSubscribersAndOwner` | 구독자·주인 200, 비구독자·비회원 403 `SUBSCRIBERS_ONLY`(제목 없음), 비구독자의 목록·글 수에서 빠짐, 구독자 피드에 나옴 |
| `NotificationIntegrationTest.commentLikeAndSubscribeNotifyOwnerButNotYourself` | 댓글·공감(연타해도 하나)·구독 알림, 문구와 링크, 내가 한 일은 없음, `/api/me`의 수 |
| `replyNotifiesParentAuthorAndOwnerOnce` | 답글은 부모 작성자에게 REPLY와 주인에게 COMMENT, 주인이 부모 작성자면 REPLY 하나 |
| `notificationsOfGoneTargetsDropOutAndReadingWorks` | 글을 지우면 그 글의 알림이 목록에서 빠짐, 남의 알림 읽기 404, 읽음·모두 읽음, 안 읽은 수(지운 대상 포함), 비회원 401 |

기존 테스트 세 곳(`PostWriteIntegrationTest` 2곳, `ManagePostIntegrationTest` 1곳)은 "구독자 공개는 400"을 기대하고 있었다. 규칙이 바뀌었으니 "된다"로 고치고, 목록에서 빠지는지까지 확인하게 했다.

## 6. 자주 하는 실수와 함정

- **켜고 끄는 기능을 토글 하나로 만든다**: 연타한 두 요청이 서로를 지운다. 상태를 말하는 PUT·DELETE로.
- **"있나 보고 넣기"를 두 번에 나눈다**: 동시에 온 두 요청 중 하나가 UNIQUE 오류로 500. 한 문장(`INSERT IGNORE`, `ON DUPLICATE KEY`)으로.
- **`INSERT IGNORE`가 UNIQUE만 무시한다고 믿는다**: 외래 키 위반도 0이 된다. 대상이 있는지 먼저 확인한다.
- **연타·재시도마다 알림을 만든다**: "넣은 행 수"가 1일 때만.
- **자기 행동을 자기에게 알린다**, **같은 일로 두 번 알린다**(글 주인 = 부모 댓글 작성자).
- **알림에 링크를 저장한다**: 대상이 지워지거나 비공개로 바뀌어도 알 수 없고, 호스트·포트가 바뀌면 틀린다. 대상 종류와 번호만 저장하고 읽을 때 만든다.
- **걸러 낸 목록의 다음 커서를 "보낸 것의 마지막"으로 잡는다**: 뺀 행을 다시 읽는다. "읽은 것의 마지막"으로.
- **판단보다 입력을 먼저 연다**: 구독자 공개를 구독보다 먼저 열면 아무도 못 보는 글이 생긴다.
- **http 개발 주소에서 `navigator.clipboard`를 그냥 부른다**: 없다(보안 컨텍스트). 대안과 실패 안내를 둔다.
- **스크립트 클릭으로 복사를 시험하고 "안 된다"고 결론 낸다**: 사용자 입력이 아니라서 막힌 것이다.

## 7. 직접 해 보기

### 7.1 화면

준비: `./scripts/build-frontend.sh && ./mvnw spring-boot:run`, 회원 셋(A: 블로그 주인, B, C).

1. B로 A의 블로그 → 프로필 상자의 "구독하기" → "구독 중", 구독자 1명. 한 번 더 누르면 해제되고 0명.
2. A로 글쓰기에서 "구독자 공개"를 골라 발행.
3. C로 그 글 주소를 연다 → "구독자 공개 글입니다"와 "구독하기". 누르면 바로 본문이 열린다.
4. B로 플랫폼 머리글 "구독 피드" → A의 글들(구독자 공개 글 포함).
5. A로 머리글 "알림 2" → B·C의 구독 알림. 하나를 누르면 그 블로그로 가고, 돌아오면 "알림 1".
6. 글 상세 "주소 복사"를 눌러 붙여 넣어 본다.

### 7.2 멱등과 알림

```bash
X="X-Requested-With: XMLHttpRequest"
for i in 1 2 3; do
  curl -s -X PUT -H "$X" -b jarB.txt -H "Host: blog.test" localhost:8080/api/blogs/7/subscription; echo
done
# 셋 다 {"subscribed":true,"subscriberCount":1}, A의 알림은 하나
```

### 7.3 DB에서 보기

```sql
SELECT * FROM subscription WHERE blog_id = 7;
SELECT receiver_id, type, target_type, target_id, message, read_at FROM notification ORDER BY id DESC LIMIT 5;
INSERT IGNORE INTO subscription (member_id, blog_id) VALUES (2, 7);   -- 이미 있으면 "0 rows affected"
SHOW WARNINGS;                                                         -- Duplicate entry … 경고
```

### 7.4 테스트

```bash
./mvnw test -Dtest='SubscriptionIntegrationTest,NotificationIntegrationTest'
cd frontend && npx vitest run src/app/share.test.ts src/app/notifications.test.ts
```

## 8. 확인 문제

1. 구독을 `POST /subscription/toggle`이 아니라 PUT·DELETE로 만든 이유는?
<details><summary>답</summary>PUT·DELETE는 "구독한 상태로/안 한 상태로 만들어라"라서 몇 번 보내도 결과가 같다(멱등). 토글은 연타한 두 요청이 "켜고 → 끄고"가 되어 사용자 뜻과 반대가 될 수 있다.</details>

2. 구독에 `Idempotency-Key`가 필요 없는데 댓글 쓰기에는 필요한 이유는?
<details><summary>답</summary>댓글 쓰기(POST)는 보낼 때마다 새 댓글을 만드는 요청이라 같은 요청을 알아볼 키가 필요하다. 구독(PUT)은 요청 자체가 결과 상태를 말하므로 두 번 와도 상태가 같다.</details>

3. `INSERT IGNORE`의 반환값으로 무엇을 하고, 그 전에 블로그가 있는지 확인하는 이유는?
<details><summary>답</summary>넣은 행 수(1이면 새 구독, 0이면 이미 구독)로 새 구독일 때만 알림을 보낸다. IGNORE는 외래 키 위반 같은 다른 오류도 0으로 바꾸므로, 없는 블로그 번호가 "이미 구독 중"처럼 보이지 않게 먼저 확인한다.</details>

4. 알림을 이벤트나 비동기가 아니라 같은 트랜잭션에서 직접 만든 이유와, 임베딩(스텝 10)은 다르게 한 이유는?
<details><summary>답</summary>알림은 같은 DB에 한 줄 쓰는 빠른 일이라, 같은 트랜잭션이면 "댓글은 됐는데 알림은 없음"이 생기지 않는다. 임베딩은 외부 서비스를 부르고 몇 초 걸려 글 저장을 늦추면 안 되므로 커밋 뒤 비동기로 했다.</details>

5. 알림의 문구는 저장하고 링크는 저장하지 않는 이유는?
<details><summary>답</summary>문구는 그때 일어난 일(그때의 닉네임·제목)을 보여 주는 기록이다. 링크와 "아직 볼 수 있나"는 지금 상태(글이 지워졌나, 비공개가 됐나)와 요청의 호스트·포트에 따라 달라서, 대상 종류·번호만 두고 읽을 때 만든다.</details>

6. 내 글의 내 댓글에 다른 사람이 답글을 달면 알림이 몇 개 오나? 왜?
<details><summary>답</summary>REPLY 하나다. 나는 글 주인이자 부모 댓글 작성자라 COMMENT와 REPLY 둘 다 해당하지만, 같은 일로 두 번 알리지 않으려고 더 구체적인 REPLY만 보낸다.</details>

7. 알림 목록에서 볼 수 없는 알림을 뺄 때 다음 커서를 "보낸 마지막"이 아니라 "읽은 마지막"으로 잡는 이유는?
<details><summary>답</summary>보낸 마지막으로 잡으면 그 뒤에 읽었다가 뺀 행들을 다음 요청이 다시 읽어 또 빼게 된다. 읽은 마지막 다음부터 읽어야 뺀 행을 건너뛴다.</details>

8. 머리글의 "알림 2"와 목록의 개수가 다를 수 있는 경우와, 그렇게 둔 이유는?
<details><summary>답</summary>대상(글·댓글)이 지워졌거나 볼 수 없게 된 안 읽은 알림이 있으면, 수는 행 수라 세지만 목록에서는 빠진다. 수를 셀 때마다 모든 대상을 확인하면 머리글이 무거워지므로 받아들였고, 모두 읽음으로 맞춰진다.</details>

9. 구독자 공개 글을 구독하지 않은 사람이 열면 404가 아니라 403인 이유는? 그래도 숨기는 것은?
<details><summary>답</summary>숨기려는 글이 아니라 구독을 권하는 글이라 "구독하면 볼 수 있다"고 알려야 한다(Q4). 대신 제목과 본문은 응답에 넣지 않고 블로그 이름만 준다.</details>

10. 구독자 공개 글을 스텝 5에서는 400으로 막았다가 이번에 연 이유는?
<details><summary>답</summary>구독이 없을 때 구독자 공개 글을 만들면 주인 말고 아무도 볼 수 없는 글이 된다. 판단(가시성)은 스텝 3부터 있었고, 구독 기능이 생긴 이번에 입력을 열었다.</details>

11. 개발 주소에서 `navigator.clipboard`가 없는 이유와, 헤드리스 Chrome에서 스크립트 클릭으로 복사가 실패한 이유는?
<details><summary>답</summary>http://alpha.blog.test는 HTTPS도 localhost도 아니라 보안 컨텍스트가 아니어서 클립보드 API가 없다. 또 브라우저는 사용자 입력(실제 클릭·키) 처리 중에만 복사를 허락하는데, 스크립트의 button.click()은 사용자 입력이 아니다.</details>

12. 구독 버튼 API가 블로그 주소(Host)가 아니라 블로그 번호로 블로그를 가리키는 이유는?
<details><summary>답</summary>구독 버튼은 블로그 화면뿐 아니라 검색 결과·피드처럼 플랫폼 주소의 화면에도 놓인다. 번호로 가리키면 어느 주소에서 불러도 같은 API다.</details>

## 9. 더 읽을거리

- RFC 9110 "HTTP Semantics" 9.2.2 Idempotent Methods
- MySQL 문서 "INSERT Statement"의 IGNORE, "SHOW WARNINGS"
- Spring 문서 "Transaction-bound Events"(`@TransactionalEventListener`)
- MDN "Secure contexts", "Clipboard API", "Document.execCommand()"
- MDN "User activation"(사용자 입력이 필요한 브라우저 기능)
- contracts/rest-api.md "SUB 구독 · 피드", "ME"의 알림 줄, data-model.md notification
