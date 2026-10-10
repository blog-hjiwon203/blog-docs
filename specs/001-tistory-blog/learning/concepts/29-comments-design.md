# 29. 댓글 설계: 글에 딸린 데이터

> 관련 스텝: [스텝 6](../step-06.md) (T044, T045), [스텝 7](../step-07.md) (T069 답글), [스텝 14](../step-14.md) (T066 댓글 고치기, 5.12), [스텝 17](../step-17.md) (T101 비밀댓글, T102 댓글 허용, 5.13) · 관련 개념: [33-isolation-deadlock](./33-isolation-deadlock.md), [08-pagination](./08-pagination.md), [16-authorization-visibility](./16-authorization-visibility.md), [17-idempotency-redis](./17-idempotency-redis.md), [22-bean-validation](./22-bean-validation.md), [24-layered-architecture-dto](./24-layered-architecture-dto.md), [25-react-forms-data](./25-react-forms-data.md), [27-soft-delete-bulk-update](./27-soft-delete-bulk-update.md), [28-thymeleaf-to-react](./28-thymeleaf-to-react.md)

## 1. 이 문서로 배우는 것

- 댓글처럼 **다른 데이터(글)에 딸린 데이터**의 권한을 어떻게 정하는지: 부모의 가시성을 물려받기
- 한 요청이 여러 조건에 걸릴 때 상태 코드를 고르는 순서(404 → 401 → 403 → 400)를 댓글 API에 적용하기
- 같은 댓글이 보는 사람마다 다르게 보이는 이유와 방법: `NORMAL`, `SECRET`, `BLINDED`
- 지우기 권한(작성자·블로그 주인)과 소프트 삭제
- 글의 `comment_count`를 따로 들고 있는 이유(비정규화)와, 숫자를 틀리지 않게 바꾸는 원자적 UPDATE
- 작성순 커서 더보기와 전체 개수(`totalCount`)
- 댓글 20개의 작성자 정보를 쿼리 한두 번으로 읽기(N+1 피하기)
- 연타 방지 두 겹: 서버의 `Idempotency-Key`와 화면의 `inFlight` ref — 실제로 있었던 "서버엔 하나, 화면엔 둘" 버그
- (스텝 7) 답글 한 단계: 자기 참조 외래 키(`parent_id`), 답글의 답글 막기, 답글이 남은 댓글을 지우면 "삭제된 댓글입니다" 자리 남기기, 부모 묶음 + 답글 한 번에 읽기

**먼저 알면 좋은 것**: 글 가시성 판단([16](./16-authorization-visibility.md)), 커서 페이지네이션([08](./08-pagination.md)), Idempotency-Key([17](./17-idempotency-redis.md)), React의 `useState`·`useRef`([25](./25-react-forms-data.md), Thymeleaf와 비교는 [28](./28-thymeleaf-to-react.md)).

## 2. 왜 필요한가

댓글 기능은 "글 아래에 글자 몇 줄 저장하기"처럼 보이지만, 실제로 만들면 이런 질문이 줄줄이 나온다.

- 비공개 글의 댓글 목록 API를 남이 부르면? 글은 404인데 댓글은 보이면, 글이 있다는 사실이 새어 나간다.
- 비회원이 **볼 수 없는 글**에 댓글을 쓰면 401(로그인 필요)이라고 답해야 할까, 404라고 답해야 할까?
- 비밀댓글은 누가 보나? 관리자가 숨긴 댓글은 작성자에게도 안 보여야 하나?
- 남의 댓글을 블로그 주인은 지울 수 있나? 서비스 관리자는?
- 글 목록마다 "댓글 2"를 보여 주려고 매번 `COUNT(*)`를 해야 하나?
- 등록 버튼을 빠르게 두 번 누르면?

기능 명세는 이렇게 정한다.

- CMT-01: 회원이 댓글을 쓰고(1~1,000자) 자기 댓글을 지운다. 연달아 눌러도 댓글은 하나다.
- CMT-02: 블로그 주인은 자기 블로그의 모든 댓글을 지운다.
- 헌법 원칙 II: 볼 수 없는 것은 존재를 숨긴다(404). 원칙 V: 관리자는 남의 글·댓글을 고치거나 지우는 API가 없다.
- data-model: `like_count`, `comment_count`는 비정규화 값이고 새로고침해도 실제 값과 같아야 한다(트랜잭션 안에서 갱신).

## 3. 기본 개념

### 3.1 딸린 데이터는 부모의 가시성을 물려받는다

댓글은 혼자 존재하지 않는다. 늘 "어떤 글의 댓글"이다. 그래서 규칙은 하나로 정리된다.

> **글을 볼 수 없는 사람에게는 그 글의 댓글도 없다.**

댓글 API(목록·쓰기·지우기)는 모두 먼저 "이 사람이 이 글을 읽을 수 있나"를 묻는다. 그 판단은 글 상세와 **같은 코드**(`PostReadService.readable`)로 한다. 규칙을 두 군데에 따로 쓰면 언젠가 어긋나고, 어긋난 곳이 정보가 새는 구멍이 된다.

Thymeleaf로 치면, 글 상세 컨트롤러에서 "볼 수 없으면 404 페이지" 판단을 했는데 댓글 목록을 따로 부르는 Ajax 컨트롤러에서 그 판단을 빼먹은 상황을 막는 것이다.

### 3.2 상태 코드 순서

한 요청이 여러 조건에 걸리면 이 프로젝트는 위에서부터 먼저 걸린 것을 준다(contracts "상태 코드 순서").

1. **404** 대상이 없거나 볼 수 없음 (로그인 여부와 상관없이)
2. **401** 로그인이 필요한데 안 함
3. **403** 로그인했지만 권한 없음 (댓글을 막은 글 `COMMENTS_DISABLED`, 남의 댓글 지우기 `FORBIDDEN`)
4. **400** 입력 오류

예외: 구독자 공개 글을 구독 안 한 사람이 열면 404 대신 403 `SUBSCRIBERS_ONLY`(Q4). 댓글도 같은 판단을 물려받는다.

왜 404가 401보다 먼저인가? 비회원이 남의 비공개 글에 댓글을 쓰려 할 때 401을 주면 "로그인하면 쓸 수 있는 글이 거기 있다"는 뜻이 된다. 404를 먼저 주면 글이 있는지조차 알 수 없다.

### 3.3 보는 사람마다 다른 응답

같은 댓글 행이라도 누가 보느냐에 따라 응답이 다르다.

| 댓글 | 작성자 본인 | 블로그 주인 | 다른 사람 |
| --- | --- | --- | --- |
| 보통 | 내용 | 내용 | 내용 |
| 비밀댓글(`is_secret`) | 내용 | 내용 | `SECRET`, 내용·작성자 `null` |
| 관리자가 숨김(`is_blinded`) | 내용 + 숨김 사유 | `BLINDED`, 내용 `null` | `BLINDED`, 내용 `null` |
| 지운 댓글(`deleted_at`) | 목록에 없음 | 목록에 없음 | 목록에 없음 |

가린 댓글도 **자리(행)는 보여 준다.** "비밀댓글입니다" 한 줄이 남는 티스토리 방식이다. 존재 자체를 숨길 만큼 민감한 것은 아니고(글은 볼 수 있는 사람이다), 대화 흐름을 위해 자리는 둔다. 대신 **내용과 작성자는 응답 JSON에서 아예 뺀다(`null`).** 화면에서만 숨기고 JSON에는 담아 보내면, 개발자 도구로 누구나 읽을 수 있기 때문이다.

### 3.4 소프트 삭제

댓글을 지우면 행을 지우지 않고 `deleted_at`에 시각을 적는다([27](./27-soft-delete-bulk-update.md)). 이유는 둘이다.

- 나중에 답글(CMT-05)이 생기면 "답글이 있는 댓글을 지우면 '삭제된 댓글입니다'로 자리를 남긴다"는 규칙이 있다. 행이 있어야 자리를 남길 수 있다.
- 신고·관리 기록이 댓글을 가리킬 수 있다.

### 3.5 비정규화 카운터

글 목록 한 줄마다 "댓글 2"가 나온다. 매번 `SELECT COUNT(*) FROM comment WHERE post_id = ? AND deleted_at IS NULL`을 하면 목록 20줄에 COUNT 20번이다. 그래서 `post.comment_count` 컬럼에 수를 **미리 적어 둔다**. 이것을 비정규화(denormalization)라 한다. 같은 정보(댓글 수)를 두 군데(comment 행 수, post.comment_count)에 두는 것이라 **둘이 어긋나지 않게 하는 책임**이 생긴다.

어긋나지 않게 하려면:

- 댓글을 저장하는 것과 수를 늘리는 것을 **같은 트랜잭션**에서 한다. 하나만 성공하는 일이 없다.
- 수를 바꿀 때 "읽고 → 더하고 → 쓰기"를 하지 않는다. 두 사람이 동시에 댓글을 달면 둘 다 2를 읽고 3을 써서 하나가 사라진다(lost update). 대신 DB에 **한 줄 UPDATE**로 "지금 값에 1을 더하라"고 시킨다: `comment_count = comment_count + 1`. DB가 행 잠금을 걸고 차례로 처리하므로 둘 다 반영된다([23](./23-transactions-locking.md)).

### 3.6 연타 방지는 두 겹

| 겹 | 막는 것 | 못 막는 것 |
| --- | --- | --- |
| 서버 `Idempotency-Key` | 같은 키로 두 번 온 요청 → 댓글 하나 | 화면이 같은 응답을 두 번 받아 두 번 붙이는 것 |
| 화면 `inFlight` ref + id 중복 확인 | 처리 중 두 번째 클릭, 같은 댓글 두 번 붙이기 | 화면을 거치지 않은 직접 요청 |

서버가 지키는 것은 **데이터**(DB에 댓글 하나), 화면이 지키는 것은 **보이는 것**(목록에 한 줄)이다. 이 둘은 다른 문제라서 둘 다 필요하다. 5.8에 실제로 겪은 일을 적었다.

## 4. 동작 원리

댓글 쓰기 요청 하나가 지나가는 길:

```
브라우저: 등록 클릭 → inFlight가 true면 무시, 아니면 true로
  POST /api/posts/9/comments   Idempotency-Key: K   {"content":"잘 읽었습니다"}
   │
   ▼ JWT 필터(누구인지) → IdempotencyInterceptor(K 처음이면 통과, 아니면 첫 응답 재사용)
   ▼ CommentController.write
     ├ @CurrentBlog                            Host → 블로그 (없으면 404)
     ├ commentService.writablePost(...)
     │    ├ postReadService.readable(...)     글을 볼 수 없으면 404, 구독자 공개면 403
     │    ├ member == null                    → 401
     │    └ !post.isCommentAllowed()          → 403 COMMENTS_DISABLED
     ├ requestValidator.validate(request)     내용 1~1,000자, parentId·secret 아직 안 됨 → 400
     └ commentService.write(...)   ── 트랜잭션 ──
          ├ writablePost(...) 다시 (같은 판단, 트랜잭션 안에서)
          ├ comment 저장
          ├ UPDATE post SET comment_count = comment_count + 1, updated_at = updated_at
          └ 저장한 댓글을 작성자와 함께 다시 읽어 CommentView로
   ▼ 201 Comment JSON
브라우저: 이미 같은 id가 목록에 있으면 붙이지 않음 → inFlight false
```

지우기는:

```
DELETE /api/comments/88
  ├ 댓글이 없거나, 이미 지웠거나, 이 블로그 글의 댓글이 아니면 404
  ├ 그 글을 볼 수 없으면 404 (readable)
  ├ 비회원 401
  ├ 작성자도 블로그 주인도 아니면 403
  └ deleted_at 기록 → flush → UPDATE comment_count - 1
```

목록은:

```
GET /api/posts/9/comments?cursor=...
  ├ readable (404·403)
  ├ 작성순 (created_at ASC, id ASC), 커서 뒤, 21개 읽기 (+작성자 함께)
  ├ 작성자들의 대표 블로그 주소를 한 번에
  ├ 보는 사람 기준으로 NORMAL/SECRET/BLINDED 정하기
  └ { content: 20개, nextCursor, totalCount }
```

## 5. 이 프로젝트에서는

### 5.1 글의 가시성 물려받기: `PostReadService.readable`

`src/main/java/com/nhnacademy/blog/post/application/PostReadService.java`

```java
@Transactional(readOnly = true)
public Post readable(Blog blog, Long postId, Long viewerId) {
    return switch (postVisibilityPolicy.decide(postId, blog, viewerId)) {
        case PostAccess.Owner owner -> owner.post();
        case PostAccess.Visible visible -> visible.post();
        case PostAccess.SubscribersOnly subscribersOnly -> throw new BusinessException(ErrorCode.SUBSCRIBERS_ONLY,
                Map.of("blogId", blog.getId(), "blogName", blog.getName(), "blogAddress", blog.getAddress()));
        case PostAccess.NotFound notFound -> throw new BusinessException(ErrorCode.NOT_FOUND);
        case PostAccess.MovedTo movedTo -> throw new BusinessException(ErrorCode.NOT_FOUND);
    };
}
```

- 글 상세 API(`detail`)와 댓글 API 세 개가 모두 이 메서드를 부른다. 판단은 스텝 3의 `PostVisibilityPolicy` 하나다([16](./16-authorization-visibility.md)).
- `Owner`와 `Visible`만 글을 돌려준다. 나머지는 예외로 끝난다.
- `MovedTo`(다른 블로그 소속 글)도 404다. 블로그 주소 API에서는 301로 보내지 않는다. 301은 화면 주소 단계에서만 한다([18](./18-spa-server-routing.md)).
- sealed 인터페이스라 `switch`가 경우를 빠짐없이 다뤘는지 컴파일러가 확인한다.

### 5.2 상태 코드 순서: `writablePost`와 컨트롤러

`src/main/java/com/nhnacademy/blog/comment/application/CommentService.java`

```java
@Transactional(readOnly = true)
public Post writablePost(Blog blog, Long postId, LoginMember member) {
    Post post = postReadService.readable(blog, postId, member == null ? null : member.id());
    if (member == null) {
        throw new BusinessException(ErrorCode.UNAUTHORIZED);
    }
    if (!post.isCommentAllowed()) {
        throw new BusinessException(ErrorCode.COMMENTS_DISABLED);
    }
    return post;
}
```

- 1줄: 글을 볼 수 있는지 **먼저**. 비회원이면 `viewerId`가 `null`이라 공개 글만 통과한다. 비공개 글이면 여기서 404로 끝나고, 아래 401에는 닿지 않는다.
- 2줄: 글은 볼 수 있는데 비회원이면 401. 화면은 이것을 받아 로그인 화면으로 보내고, 로그인 뒤 이 글로 돌아온다(spec US3 시나리오 6).
- 3줄: 댓글을 막은 글이면 403(CMT-07은 뒤 스텝이지만 `is_comment_allowed` 컬럼은 이미 있다).

`src/main/java/com/nhnacademy/blog/comment/presentation/CommentController.java`

```java
@Idempotent
@PostMapping("/api/posts/{postId}/comments")
@ResponseStatus(HttpStatus.CREATED)
public CommentResponse write(@CurrentBlog Blog blog, @AuthenticationPrincipal LoginMember member,
                             @PathVariable Long postId, @RequestBody CommentRequest request) {
    commentService.writablePost(blog, postId, member);
    requestValidator.validate(request);
    return CommentResponse.from(commentService.write(blog, postId, member, request.content()));
}
```

- `@RequestBody`에 `@Valid`를 붙이지 않았다. 붙이면 메서드에 들어오기 **전에** 검증해서 400이 404·401·403보다 먼저 나간다. 그래서 권한 판단(`writablePost`)을 먼저 하고 그다음 `requestValidator.validate`로 검증한다([22](./22-bean-validation.md)).
- `write` 안에서 `writablePost`를 한 번 더 부른다. 앞의 호출은 상태 코드 순서를 위한 것이고, 트랜잭션 안의 호출은 저장할 때 실제로 쓸 글 엔티티를 얻기 위한 것이다.
- 남은 점: `@Idempotent`의 키 검사(인터셉터)는 이 메서드보다 먼저라, 키 없이 보내면 400이 먼저 나간다([17](./17-idempotency-redis.md) 5.7).

### 5.3 요청 DTO: 아직 없는 기능은 400

`src/main/java/com/nhnacademy/blog/comment/presentation/dto/CommentRequest.java`

```java
public record CommentRequest(
        @NotBlank(message = "댓글 내용을 입력해 주세요.")
        @Size(max = 1000, message = "댓글은 1,000자까지입니다.")
        String content,

        @Null(message = "답글은 아직 달 수 없습니다.")
        Long parentId,

        @AssertFalse(message = "비밀댓글은 아직 쓸 수 없습니다.")
        Boolean secret) {
}
```

- `@NotBlank`: `null`, 빈 문자열, 공백만은 거절. 저장할 때는 `content.trim()`으로 앞뒤 공백을 지운다.
- `@Null`: 값이 있으면 실패. 답글(CMT-05)은 스텝 7이라 스텝 6에서는 `parentId`를 보내면 400이었다. 받아 놓고 조용히 무시하면 사용자는 답글이 달린 줄 안다. **스텝 7에서 `@Null`을 지우고 답글을 열었다(5.11).**
- `@AssertFalse`: `false`이거나 `null`이면 통과, `true`면 실패. 비밀댓글 쓰기(CMT-06)는 백로그다. `Boolean`(참조형)이라 안 보내도 된다([22](./22-bean-validation.md)의 기본형 함정).
- 비밀댓글을 쓰는 기능은 없지만 **보여 주는 규칙**(5.4)은 미리 만들었다. 컬럼(`is_secret`)이 있고, 나중에 쓰기만 열면 되게.

### 5.4 보는 사람마다 다른 댓글: `CommentView`

> **(스텝 14에서 바뀜)** 아래 판단 코드는 스텝 14에서 방명록과 같이 쓰려고 `comment/application/CommentViews.java`로 옮겼고, `CommentView`는 `Comment` 대신 댓글·방명록 공통 모양 `CommentEntry`를 들고 `canEdit`·작성자 사진 칸이 늘었다. 판단 순서(지움 → 숨김 → 비밀 → 보통)는 그대로다. 옮긴 이유와 지금 코드는 [50 같은 규칙의 두 기능을 한 코드로](./50-shared-rules-comment-guestbook.md)에 있다. 이 절은 처음 만든 모양으로 읽는다.

`src/main/java/com/nhnacademy/blog/comment/application/CommentView.java`

```java
public record CommentView(Comment comment, State state, String authorPrimaryBlogAddress, boolean canDelete,
                          Map<String, String> blind) {

    public enum State {
        NORMAL,
        SECRET,
        BLINDED
    }

    /** 내용과 작성자를 보여 줘도 되는가. */
    public boolean showsContent() {
        return state == State.NORMAL;
    }

}
```

`CommentService.view`가 상태를 정한다.

```java
private CommentView view(Comment comment, Blog blog, Long viewerId, String authorAddress) {
    boolean author = comment.isWrittenBy(viewerId);
    boolean blogOwner = blog.isOwnedBy(viewerId);
    CommentView.State state;
    Map<String, String> blind = null;
    if (comment.isBlinded()) {
        // 작성자 본인에게는 내용과 숨김 사유를 보여 주고, 다른 사람에게는 자리만 (ADMIN-03)
        state = author ? CommentView.State.NORMAL : CommentView.State.BLINDED;
        blind = author ? blindReason(comment) : null;
    } else if (comment.isSecret() && !author && !blogOwner) {
        state = CommentView.State.SECRET;   // 글 주인과 작성자만 본다 (CMT-06)
    } else {
        state = CommentView.State.NORMAL;
    }
    return new CommentView(comment, state, authorAddress, author || blogOwner, blind);
}
```

- 숨김을 비밀보다 **먼저** 본다. 관리자가 숨긴 비밀댓글은 블로그 주인에게도 숨김이다.
- 숨김 사유는 댓글 행이 아니라 `moderation_log`의 최신 BLIND 행에서 읽는다(`blindReason`). 작성자에게만 준다.
- `canDelete`는 작성자이거나 블로그 주인일 때 `true`. 화면은 이것으로 "삭제" 버튼을 보일지 정한다. 진짜 검사는 지우기 API가 다시 한다(5.5).

응답으로 바꿀 때 가린다. `src/main/java/com/nhnacademy/blog/comment/presentation/dto/CommentResponse.java`

```java
public static CommentResponse from(CommentView view) {
    Comment comment = view.comment();
    boolean shows = view.showsContent();
    return new CommentResponse(comment.getId(), comment.getParent() == null ? null : comment.getParent().getId(),
            shows ? MemberSummaryResponse.of(comment.getMember(), view.authorPrimaryBlogAddress()) : null,
            shows ? comment.getContent() : null, comment.isSecret(), view.state().name(),
            DateTimes.toOffset(comment.getCreatedAt()),
            comment.getUpdatedAt().equals(comment.getCreatedAt()) ? null : DateTimes.toOffset(comment.getUpdatedAt()),
            new Viewer(false, view.canDelete()), view.blind(), List.of());
}
```

- `shows`가 거짓이면 `author`와 `content`가 `null`이다. JSON에 아예 들어가지 않으니 화면을 고쳐도 볼 수 없다.
- `updatedAt`은 생성 시각과 같으면 `null`("수정됨"을 안 붙임). 수정(CMT-03)은 아직 없어 늘 `null`이다.
- `canEdit`은 수정 기능이 없어 `false`, `replies`는 답글 전이라 빈 목록이다.

### 5.5 지우기 권한과 소프트 삭제

`CommentService.delete`

```java
@Transactional
public void delete(Blog blog, Long commentId, LoginMember member) {
    Long viewerId = member == null ? null : member.id();
    Comment comment = commentRepository.findWithPostById(commentId)
            .filter(found -> !found.isDeleted())
            .filter(found -> found.getPost().getBlog().getId().equals(blog.getId()))
            .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));
    postReadService.readable(blog, comment.getPost().getId(), viewerId);
    if (member == null) {
        throw new BusinessException(ErrorCode.UNAUTHORIZED);
    }
    if (!comment.isWrittenBy(viewerId) && !blog.isOwnedBy(viewerId)) {
        throw new BusinessException(ErrorCode.FORBIDDEN);
    }
    comment.delete(LocalDateTime.now(clock));
    // 댓글 수 UPDATE가 영속성 컨텍스트를 비우므로(clearAutomatically) 삭제를 먼저 DB에 보낸다
    commentRepository.flush();
    postRepository.addCommentCount(comment.getPost().getId(), -1);
}
```

- `findWithPostById`는 댓글과 글, 블로그, 블로그 주인을 한 쿼리로 읽는다(`join fetch`). 이 블로그 글의 댓글인지 보려면 글의 블로그가 필요하다.
- 이미 지운 댓글, 다른 블로그 글의 댓글은 404다. 같은 댓글을 두 번 지우면 두 번째는 404(`authorAndBlogOwnerCanDeleteOthersCannot` 테스트).
- 권한: 작성자(CMT-01) 또는 블로그 주인(CMT-02). **서비스 관리자는 없다.** 관리자는 지우는 대신 숨김(BLIND)으로 처리하고, 숨김은 되돌릴 수 있다(헌법 원칙 V).
- `comment.delete(now)`는 `deleted_at`만 적는다. 변경 감지로 저장된다([27](./27-soft-delete-bulk-update.md)).
- **순서가 중요하다.** `addCommentCount`는 `@Modifying(clearAutomatically = true)`라 실행 뒤 영속성 컨텍스트를 비운다. 그 전에 `flush()`로 `deleted_at` 변경을 DB에 보내지 않으면, 변경 감지 대상이 사라져 **삭제가 저장되지 않는다.**

### 5.6 댓글 수: 원자적 UPDATE

`src/main/java/com/nhnacademy/blog/post/domain/PostRepository.java`

```java
@Modifying(clearAutomatically = true)
@Query("update Post p set p.commentCount = p.commentCount + :delta, p.updatedAt = p.updatedAt where p.id = :postId")
int addCommentCount(@Param("postId") Long postId, @Param("delta") int delta);
```

- `p.commentCount + :delta`: DB가 지금 값에 더한다. 자바에서 읽어 더해 쓰는 것이 아니라 동시 요청에도 수가 틀리지 않는다(3.5).
- `p.updatedAt = p.updatedAt`: `post.updated_at`은 MySQL `ON UPDATE CURRENT_TIMESTAMP`라 어떤 UPDATE든 시각이 바뀐다. 댓글이 달린 것은 **글을 고친 것이 아니므로** 같은 값을 다시 넣어 바뀌지 않게 한다. 글 상세의 "수정 2026.10.08"은 작성자가 고쳤을 때만 나와야 한다([27](./27-soft-delete-bulk-update.md)). 테스트 `memberWritesCommentAndCountGoesUp`이 댓글을 단 뒤 `updated_at = created_at`이고 상세의 `updatedAt`이 없음을 확인한다.
- 쓰기에서는 `+1`, 지우기에서는 `-1`. 둘 다 댓글 저장·삭제와 같은 트랜잭션이라 하나만 반영되는 일이 없다.

쓰기 쪽 전체:

```java
@Transactional
public CommentView write(Blog blog, Long postId, LoginMember member, String content) {
    Post post = writablePost(blog, postId, member);
    Comment comment = commentRepository.save(
            Comment.write(post, memberRepository.getReferenceById(member.id()), content.trim(), false));
    postRepository.addCommentCount(post.getId(), 1);
    Comment saved = commentRepository.findBy(
            (root, query, cb) -> cb.equal(root.get("id"), comment.getId()),
            query -> query.project("member").first()).orElseThrow();
    return view(saved, blog, member.id(), primaryBlogAddresses.of(List.of(member.id()), member.id())
            .get(member.id()));
}
```

- `getReferenceById`: 회원 행을 읽지 않고 id만 든 프록시를 만든다. 외래 키만 필요할 때 SELECT를 아낀다.
- `save` 뒤 `addCommentCount`가 영속성 컨텍스트를 비우므로, 응답에 쓸 댓글은 **작성자와 함께 다시 읽는다**(`project("member")`). 비워진 뒤의 `comment` 객체로 작성자 닉네임을 읽으면 트랜잭션 밖에서 지연 로딩이 터질 수 있다([24](./24-layered-architecture-dto.md)).

### 5.7 목록: 작성순 커서, totalCount, 작성자 한 번에

```java
@Transactional(readOnly = true)
public CommentPage list(Blog blog, Long postId, Long viewerId, TimeIdCursor cursor) {
    Post post = postReadService.readable(blog, postId, viewerId);
    Specification<Comment> condition = (root, query, cb) -> cb.and(
            cb.equal(root.get("post").get("id"), post.getId()),
            cb.isNull(root.get("deletedAt")));
    if (cursor != null) {
        condition = condition.and((root, query, cb) -> cb.or(
                cb.greaterThan(root.get("createdAt"), cursor.time()),
                cb.and(cb.equal(root.get("createdAt"), cursor.time()), cb.greaterThan(root.get("id"), cursor.id()))));
    }
    List<Comment> comments = commentRepository.findBy(condition,
            query -> query.sortBy(WRITTEN_ORDER).project("member").limit(PAGE_SIZE + 1).all());
    Map<Long, String> addresses = primaryBlogAddresses.of(
            comments.stream().map(comment -> comment.getMember().getId()).distinct().toList(), viewerId);
    List<CommentView> views = comments.stream()
            .map(comment -> view(comment, blog, viewerId, addresses.get(comment.getMember().getId())))
            .toList();
    return new CommentPage(views, commentRepository.countByPostIdAndDeletedAtIsNull(post.getId()));
}
```

- **작성순**(`createdAt ASC, id ASC`)이라 커서 조건은 `>`다. 최신순(홈)은 `<`다. 방향만 반대이고 원리는 같다([08](./08-pagination.md)).
- `limit(PAGE_SIZE + 1)`: 21개를 읽어 21번째가 있으면 다음 묶음이 있다는 뜻이다. 자르고 커서를 만드는 일은 컨트롤러의 `CursorResponse.of`가 한다.
- `project("member")`: Spring Data JPA의 `findBy` 플루언트 쿼리에서 함께 읽을 연관을 정한다. 이 프로젝트에서는 작성자를 같이 읽어 응답 매핑(트랜잭션 밖)에서 닉네임을 읽을 수 있다. 테스트가 작성자 닉네임을 확인하므로 실제로 함께 읽힌 것이 검증된다.
- **N+1 피하기**: 댓글 20개의 작성자마다 "대표 블로그 주소"를 하나씩 찾으면 쿼리가 20번이다. `PrimaryBlogAddresses.of(작성자 id 목록)`는 `where member_id in (...)`으로 한 번에 읽는다.

`src/main/java/com/nhnacademy/blog/blog/application/PrimaryBlogAddresses.java`

```java
@Transactional(readOnly = true)
public Map<Long, String> of(Collection<Long> memberIds, Long viewerId) {
    if (memberIds.isEmpty()) {
        return Map.of();
    }
    return blogRepository.findPrimaryByMemberIds(memberIds).stream()
            .filter(blog -> blogVisibilityPolicy.canView(blog, viewerId))
            .collect(Collectors.toMap(blog -> blog.getMember().getId(), Blog::getAddress));
}
```

- 빈 목록이면 쿼리를 하지 않는다(`IN ()`은 SQL 문법 오류가 날 수 있다).
- 대표 블로그가 제한·정지 등으로 보는 사람이 볼 수 없으면 맵에서 빠지고, 응답의 `primaryBlogAddress`가 `null`이 된다(닉네임 링크를 안 걸음, BLOG-08).
- `totalCount`는 `countByPostIdAndDeletedAtIsNull`로 센다. 화면 머리의 "댓글 22"는 지금 불러온 20개가 아니라 전체 수다. 가려진 비밀·숨김 댓글도 센다(자리는 있으니까).

### 5.8 화면: 두 겹 연타 방지와 실제로 겪은 버그

`frontend/src/components/Comments.tsx`

```tsx
const [submitting, setSubmitting] = useState(false)
// 버튼은 다음 그리기에서야 꺼지므로, 그 사이 두 번째 클릭은 ref로 바로 막는다
const inFlight = useRef(false)
// 등록 한 번에 키 하나. 실패해 다시 누르면 같은 키로, 성공하면 다음 댓글을 위해 새 키로
const idempotencyKey = useRef(newIdempotencyKey())
```

```tsx
async function submit(event: FormEvent) {
  event.preventDefault()
  if (!content.trim()) {
    setError('댓글 내용을 입력해 주세요.')
    return
  }
  if (inFlight.current) {
    return
  }
  inFlight.current = true
  setSubmitting(true)
  setError(null)
  try {
    const created = await api<Comment>(`/api/posts/${postId}/comments`, {
      method: 'POST', body: { content: content.trim() }, idempotencyKey: idempotencyKey.current,
    })
    idempotencyKey.current = newIdempotencyKey()
    setContent('')
    // 다음 묶음이 남아 있으면 새 댓글은 그 끝에 있으므로, 다 불러온 경우에만 바로 붙인다
    // 같은 키의 재시도면 서버가 같은 댓글을 다시 돌려주므로, 이미 있는 댓글은 붙이지 않는다
    if (!nextCursor && !comments.some((comment) => comment.id === created.id)) {
      setComments((previous) => [...previous, created])
      setTotalCount(totalCount + 1)
      onCountChange(totalCount + 1)
    }
  } catch (caught) {
    setError(fieldMessages(caught).content ?? errorMessage(caught))
  } finally {
    inFlight.current = false
    setSubmitting(false)
  }
}
```

**무슨 일이 있었나.** 처음에는 `inFlight`도 id 확인도 없었다. 버튼은 `disabled={submitting}`이라 "누르면 꺼지니 괜찮다"고 생각했다. 헤드리스 Chrome으로 등록 버튼을 `click(); click()` 두 번 빠르게 눌러 확인했더니:

```
댓글 수 표시: 댓글 1
댓글들: B가 쓴 댓글입니다 | B가 쓴 댓글입니다     ← 화면엔 둘
totalCount 1 ['B가 쓴 댓글입니다']                 ← 서버(API)엔 하나
```

- 서버는 맞았다. 두 요청이 같은 키 K를 들고 갔고, 인터셉터가 두 번째 요청에 첫 응답을 그대로 돌려줬다([17](./17-idempotency-redis.md)). DB에는 댓글 하나다.
- 화면이 틀렸다. `setSubmitting(true)`는 **다음 그리기**에서야 버튼을 끈다. 두 번째 클릭은 그 전에 들어와 `submit`을 한 번 더 실행했다. 그리고 두 응답(같은 댓글)을 각각 목록에 붙였다.

**고친 것.**

- `inFlight` ref: `useRef`는 값을 바꾸면 **즉시** 바뀌고 다시 그리기를 기다리지 않는다. 첫 클릭이 `true`로 바꾸면 두 번째 클릭은 첫 줄에서 바로 돌아간다. 화면 표시용 `submitting`(state)과 실제로 막는 `inFlight`(ref)를 나눈 것이다.
- id 중복 확인: 그래도 같은 댓글이 두 번 오면(네트워크 재시도 등) 이미 있는 id는 붙이지 않는다.
- 키는 **성공하면 새로**, 실패하면 그대로다. 실패 뒤 다시 누르면 같은 키라 서버가 이어서 처리하고, 성공 뒤 새 댓글은 새 키라 새 요청이 된다.

고친 뒤 같은 방법으로 두 번 눌렀을 때 `댓글 2 | B가 쓴 댓글입니다 | 두 번 눌러도 하나`, API도 2개였다.

Thymeleaf 폼이었다면? 폼 제출은 페이지 이동이라 두 번 눌러도 브라우저가 두 번째 이동으로 덮는다. 서버의 PRG(Post-Redirect-Get)와 중복 방지는 여전히 필요하지만, "화면에 두 번 붙는" 문제는 생기지 않는다. React처럼 **페이지를 그대로 둔 채 결과를 화면 상태에 더하는 방식**에서 새로 생기는 종류의 버그다([28](./28-thymeleaf-to-react.md)).

### 5.9 비회원과 막힌 글

```tsx
{!commentAllowed && <p className="small muted">이 글에는 댓글을 쓸 수 없습니다.</p>}
{commentAllowed && me.status === 'anonymous' && (
  <a className="btn" href={loginUrl()} style={{ justifySelf: 'start' }}>로그인하고 댓글 쓰기</a>
)}
```

- 비회원에게는 쓰기 칸 대신 로그인 링크를 준다. `loginUrl()`은 지금 주소를 `redirect`에 담아, 로그인 뒤 이 글로 돌아온다.
- 화면이 칸을 숨겨도 API를 직접 부르면 서버가 401·403으로 막는다. 화면 검사는 안내용이다(헌법 원칙 IV).

### 5.10 테스트

`src/test/java/com/nhnacademy/blog/comment/CommentIntegrationTest.java`

| 테스트 | 확인하는 것 |
| --- | --- |
| `memberWritesCommentAndCountGoesUp` | 201, 앞뒤 공백 제거, 작성자 닉네임, `comment_count` 1, 글의 `updated_at` 그대로 |
| `doubleClickMakesOneComment` | 같은 키 두 번 → 댓글 하나, `totalCount` 1 |
| `anonymousIsAskedToLoginButHiddenPostIs404` | 공개 글엔 비회원 401, 비공개 글엔 비회원·남 모두 404, 목록도 404 |
| `invalidOrUnsupportedInputIs400` | 공백·1,001자 400, `parentId`·`secret` 400, 1,000자는 201 |
| `commentsDisabledPostRejects` | 댓글을 막은 글은 403 `COMMENTS_DISABLED`(빈 내용이어도 403이 먼저) |
| `listIsInWrittenOrderTwentyAtATime` | 작성순, 20개 + 커서, 다음 묶음 2개, 끝이면 `nextCursor` 없음 |
| `secretAndBlindedCommentsAreMasked` | 남에게 SECRET·BLINDED와 null 내용, 주인은 비밀 내용 봄, 작성자는 둘 다 봄, 지운 댓글 없음 |
| `authorAndBlogOwnerCanDeleteOthersCannot` | 비회원 401, 남 403, `canDelete` 표시, 작성자·주인 204, 두 번째 404, 수 0 |
| `commentOfAnotherBlogIs404OnThisAddress` | 다른 블로그 글의 댓글을 이 주소로 지우면 404, 댓글은 그대로 |

### 5.11 (스텝 7) 답글 한 단계

명세 CMT-05: 댓글에 답글을 달 수 있고 **한 단계까지만**이다. 답글이 있는 댓글을 지우면 답글은 남기고 그 자리에 "삭제된 댓글입니다"를 보여 준다.

#### 표: 자기 자신을 가리키는 외래 키

`comment` 테이블에는 처음부터(V1) `parent_id` 칸이 있었다. 같은 `comment` 테이블의 다른 행을 가리키는 외래 키다(자기 참조). 최상위 댓글은 `parent_id`가 `NULL`이고, 답글은 부모 댓글의 id를 가진다.

```
id | post_id | parent_id | content
 1 |      10 |      NULL | B의 댓글          ← 최상위
 2 |      10 |         1 | A의 답글          ← 1의 답글
 3 |      10 |      NULL | C의 댓글          ← 최상위
```

엔티티는 `src/main/java/com/nhnacademy/blog/comment/domain/Comment.java`에 이미 있었다.

```java
@ManyToOne(fetch = FetchType.LAZY)
@JoinColumn(name = "parent_id")
private Comment parent;
...
public static Comment reply(Comment parent, Member member, String content, boolean secret) {
    return new Comment(parent.getPost(), member, parent, content, secret);
}
```

- `@ManyToOne`의 대상이 자기 클래스(`Comment`)다. JPA에서 자기 참조는 다른 연관과 똑같이 쓴다([06](./06-jpa-entity-mapping.md)).
- `reply`는 글을 따로 받지 않고 **부모의 글**을 쓴다. 답글이 부모와 다른 글에 붙는 일이 구조상 생기지 않는다.

"몇 단계까지"는 표가 정하지 않는다. `parent_id`만 있으면 답글의 답글의 답글도 저장할 수 있다. 한 단계 규칙은 서버 코드가 지킨다.

#### 쓰기: 부모가 될 수 있는 댓글인가

요청 DTO에서 `parentId`의 `@Null`을 지웠다(5.3). 서비스의 `write`가 `parentId`를 받으면 `parentOf`로 부모를 찾는다.

```java
Comment comment = commentRepository.save(parentId == null
        ? Comment.write(post, author, content.trim(), false)
        : Comment.reply(parentOf(post, parentId), author, content.trim(), false));
...
private Comment parentOf(Post post, Long parentId) {
    Comment parent = commentRepository.findById(parentId)
            .filter(found -> found.getPost().getId().equals(post.getId()) && !found.isDeleted())
            .orElseThrow(() -> BusinessException.invalidField("parentId", "답글을 달 댓글을 찾을 수 없습니다."));
    if (parent.getParent() != null) {
        throw BusinessException.invalidField("parentId", "답글에는 답글을 달 수 없습니다.");
    }
    return parent;
}
```

줄별로:

- `findById(parentId)`: 부모 후보를 읽는다. 없으면 빈 `Optional`.
- `.filter(... post.getId() ... && !found.isDeleted())`: **주소의 글과 같은 글**의 댓글이고 지우지 않은 것만 통과한다. 이 검사가 없으면 `POST /api/posts/10/comments`에 다른 글(심지어 볼 수 없는 비공개 글)의 댓글 id를 넣어 그 글에 답글을 붙일 수 있다. 존재를 숨기는 원칙과 맞추려고 "다른 글의 댓글"과 "없는 댓글"은 같은 메시지다.
- `orElseThrow(... invalidField("parentId", ...))`: 400 `VALIDATION_FAILED`에 `fieldErrors[0].field = "parentId"`. 글 자체는 볼 수 있는 상태라(앞에서 `writablePost` 통과) 404가 아니라 "보낸 값이 틀렸다"는 400이다.
- `parent.getParent() != null`: 부모가 이미 답글이면 거절한다. 이것이 "한 단계"를 지키는 한 줄이다.
- 상태 코드 순서는 그대로다: 글 404 → 비회원 401 → 댓글 막힘 403 → 입력 400(부모 검사 포함).

화면도 답글에는 "답글" 버튼을 그리지 않는다. 그래도 API를 직접 부르면 서버가 막는다(화면 검사는 안내용).

#### 지우기: 답글이 있으면 자리를 남긴다

지우기 코드(`delete`)는 스텝 6과 거의 같다. 소프트 삭제라 행은 남고 `deleted_at`만 찍힌다. 그래서 답글의 `parent_id`가 가리키는 부모 행도 그대로 있다. 다른 것은 **목록을 읽는 쪽**이다.

#### 목록: 부모 묶음과 답글을 따로, 한 번씩

```java
Specification<Comment> condition = (root, query, cb) -> {
    Subquery<Long> liveReply = query.subquery(Long.class);
    Root<Comment> reply = liveReply.from(Comment.class);
    liveReply.select(reply.get("id")).where(
            cb.equal(reply.get("parent"), root),
            cb.isNull(reply.get("deletedAt")));
    return cb.and(
            cb.equal(root.get("post").get("id"), post.getId()),
            cb.isNull(root.get("parent")),
            cb.or(cb.isNull(root.get("deletedAt")), cb.exists(liveReply)));
};
```

이 조건이 만드는 SQL을 풀어 쓰면 대략 이렇다.

```sql
SELECT c.* FROM comment c
WHERE c.post_id = 10
  AND c.parent_id IS NULL                                   -- 최상위 댓글만
  AND (c.deleted_at IS NULL                                 -- 지우지 않았거나
       OR EXISTS (SELECT r.id FROM comment r                -- 지웠어도 살아 있는 답글이 있으면
                  WHERE r.parent_id = c.id AND r.deleted_at IS NULL))
ORDER BY c.created_at, c.id
LIMIT 21
```

- `query.subquery(...)`와 `cb.exists(...)`: Criteria API로 상관 서브쿼리(바깥 행 `c`를 안에서 참조)를 만든다. `reply.get("parent")`와 `root`를 같다고 놓은 것이 `r.parent_id = c.id`다.
- **커서와 20개 묶음은 최상위 댓글 기준**이다. 답글까지 섞어 20개로 자르면 부모는 1쪽, 답글은 2쪽에 갈라질 수 있다.

답글은 두 번째 쿼리로 한 번에 읽는다.

```java
List<Comment> replies = parents.isEmpty() ? List.of() : commentRepository.findBy(
        (root, query, cb) -> cb.and(
                root.get("parent").in(parents),
                cb.isNull(root.get("deletedAt"))),
        query -> query.sortBy(WRITTEN_ORDER).project("member").all());
```

- `root.get("parent").in(parents)`: `WHERE parent_id IN (1, 3, ...)`. 부모마다 답글을 따로 읽으면 N+1이다([06](./06-jpa-entity-mapping.md)).
- `project("member")`: 작성자를 함께 읽는다(5.7과 같은 방법).
- 답글은 개수 제한 없이 모두 붙인다. 한 단계라 한 댓글의 답글 수가 아주 많아지는 경우는 드물다고 보고 단순하게 갔다.

그다음 `Collectors.groupingBy(reply -> reply.getParent().getId(), LinkedHashMap::new, ...)`로 부모 id별로 묶고, 부모의 `CommentView`에 `withReplies(...)`로 붙인다. `LinkedHashMap`과 `toList()`는 넣은 순서를 지켜 작성순이 유지된다.

`totalCount`는 `countByPostIdAndDeletedAtIsNull`로 **지우지 않은 댓글과 답글 모두**를 센다. 글의 `comment_count`와 같은 기준이다(지울 때 −1, 답글을 쓸 때도 +1). "삭제된 댓글입니다" 자리는 세지 않는다.

#### 보여 주기: DELETED 상태

```java
if (comment.isDeleted()) {
    // 답글이 남아 자리만 있는 부모. 누구에게나 내용·작성자 없이, 다시 지울 것도 없다
    return new CommentView(comment, CommentView.State.DELETED, null, false, null, List.of());
}
```

- 지운 댓글이 목록에 나오는 경우는 "답글이 남은 부모"뿐이다(위 조건). 내용·작성자는 비밀댓글처럼 서버가 `null`로 보낸다(5.4와 같은 원칙). 지운 내용을 화면에서 가리는 것이 아니라 아예 보내지 않는다.
- `canDelete`는 `false`. 이미 지운 것을 또 지울 수 없다.

응답은 이런 모양이다.

```json
{ "id": 1, "parentId": null, "state": "DELETED", "content": null, "author": null,
  "replies": [ { "id": 2, "parentId": 1, "state": "NORMAL", "content": "A의 답글", ... } ] }
```

#### 화면: Comments.tsx와 commentList.ts

`frontend/src/components/Comments.tsx`는 최상위 댓글을 그리고 그 아래 `comment.replies`를 `isReply`로 들여 그린다. Thymeleaf라면 `th:each` 안에 `th:each`를 한 번 더 쓴 것과 같다([28](./28-thymeleaf-to-react.md)).

새 답글을 붙일 때는 부모를 찾아 그 `replies`에만 더한다. 이미 있는 id면 붙이지 않는 연타 대비(5.8)도 답글에 똑같이 했다.

```tsx
const parent = comments.find((comment) => comment.id === created.parentId)
if (!parent || parent.replies.some((reply) => reply.id === created.id)) {
  return
}
setComments(comments.map((comment) => (comment.id === created.parentId
  ? { ...comment, replies: [...comment.replies, created] } : comment)))
```

- `map`으로 **새 배열**을 만들고, 바뀌는 부모만 `{ ...comment, replies: [...] }`로 새 객체를 만든다. React는 state가 새 값이어야 다시 그린다. 기존 배열에 `push`하면 같은 배열이라 화면이 안 바뀔 수 있다([25](./25-react-forms-data.md)).

지운 뒤의 목록 규칙은 서버의 목록 규칙과 같아야 한다(새로고침했을 때 화면이 달라지면 안 됨). 규칙이 조금 복잡해서 화면 코드와 떼어 `commentList.ts`의 순수 함수로 만들고 Vitest로 확인했다.

```ts
export function afterDelete(comments: Comment[], target: Comment): Comment[] {
  if (target.parentId === null) {
    return comments.flatMap((comment) => {
      if (comment.id !== target.id) {
        return [comment]
      }
      return comment.replies.length > 0
        ? [{ ...comment, state: 'DELETED' as const, content: null, author: null,
          viewer: { canEdit: false, canDelete: false } }]
        : []
    })
  }
  return comments.flatMap((comment) => {
    if (comment.id !== target.parentId) {
      return [comment]
    }
    const replies = comment.replies.filter((reply) => reply.id !== target.id)
    return comment.state === 'DELETED' && replies.length === 0 ? [] : [{ ...comment, replies }]
  })
}
```

- `flatMap`은 원소마다 배열을 돌려받아 이어 붙인다. `[]`를 돌려주면 빠지고, `[x]`면 남는다. "빼거나 바꾸거나 그대로"를 한 번에 표현하기 좋다.
- 최상위 댓글을 지우면: 답글이 있으면 DELETED 자리로 바꾸고, 없으면 뺀다.
- 답글을 지우면: 그 부모에서 답글만 빼고, 부모가 DELETED 자리인데 마지막 답글이 사라졌으면 자리도 뺀다. 서버 목록 조건의 `EXISTS(살아 있는 답글)`과 같은 규칙이다.

`frontend/src/components/commentList.test.ts`의 네 테스트가 이 네 경우를 하나씩 확인한다.

#### 테스트

`src/test/java/com/nhnacademy/blog/comment/ReplyIntegrationTest.java`

| 테스트 | 확인하는 것 |
| --- | --- |
| `repliesAreNestedUnderParentInWrittenOrder` | 답글은 목록 최상위에 따로 나오지 않고 부모의 `replies`에 작성순으로 |
| `replyOfReplyAndForeignParentAreRejected` | 답글의 답글, 다른 글의 댓글, 지운 댓글을 부모로 주면 400 `parentId` |
| `deletedParentWithRepliesStaysAsPlaceholder` | 답글 있는 부모를 지우면 DELETED 자리(내용·작성자 null), 답글까지 지우면 자리도 사라짐 |

`src/test/java/com/nhnacademy/blog/reaction/CountConsistencyIntegrationTest.java`의 `commentCountMatchesRowsAfterRepliesAndDeletes`는 댓글·답글을 쓰고 지운 뒤 `comment_count`가 지우지 않은 행 수와 같은지 본다.

#### 동시성: 글 행을 먼저 잠근다

스텝 7에서 공감을 만들다가, 같은 글에 댓글 INSERT와 댓글 수 UPDATE가 동시에 몰리면 데드락이 날 수 있다는 것을 알았다. `write`와 `delete`도 공감처럼 `postRepository.lockById(...)`로 글 행을 먼저 잠근다. 왜 그런지는 [33 격리 수준, 스냅샷, 데드락](./33-isolation-deadlock.md)에서 자세히 다룬다.

### 5.12 (스텝 14) 댓글 고치기: 본인만, 숨긴 댓글은 안 된다

명세 CMT-03은 "본인만"이다. API 명세는 `PATCH /api/comments/{id}` `{ content }` → `Comment`, "숨긴 댓글은 403"이다. 수용 시나리오(spec US7 2번)는 "내 댓글과 남의 댓글을 수정하려 하면 내 댓글만 고쳐진다"다.

**상태 코드 순서.** 지우기(5.5)와 같은 순서를 지킨다. 같은 댓글에 대해 고치기와 지우기가 다른 순서로 답하면, 어느 쪽 응답이 정보를 흘리는지 따로 따져야 한다.

```
없는 댓글·지운 댓글·다른 블로그 댓글·볼 수 없는 글의 댓글  → 404
비회원                                                  → 401
본인이 아님(블로그 주인도) 또는 관리자가 숨긴 댓글           → 403
내용이 비었거나 1,000자 넘음                               → 400
```

```java
// comment/application/CommentService.java
@Transactional
public CommentView edit(Blog blog, Long commentId, LoginMember member, String content) {
    Comment comment = editable(blog, commentId, member);
    comment.edit(content.trim());
    // updatedAt(@LastModifiedDate)이 응답에 들어가도록 UPDATE를 먼저 보낸다
    commentRepository.flush();
    return commentViews.one(comment, blog, member.id());
}

private Comment editable(Blog blog, Long commentId, LoginMember member) {
    Comment comment = visibleComment(blog, commentId, member);
    if (!comment.isWrittenBy(member.id()) || comment.isBlinded()) {
        throw new BusinessException(ErrorCode.FORBIDDEN);
    }
    return comment;
}

/** 이 블로그 글의, 지우지 않은, 글을 볼 수 있는 댓글. 그다음 로그인했는지 본다(404 → 401 순서). */
private Comment visibleComment(Blog blog, Long commentId, LoginMember member) {
    Comment comment = commentRepository.findWithPostById(commentId)
            .filter(found -> !found.isDeleted())
            .filter(found -> found.getPost().getBlog().getId().equals(blog.getId()))
            .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));
    postReadService.readable(blog, comment.getPost().getId(), member == null ? null : member.id());
    if (member == null) {
        throw new BusinessException(ErrorCode.UNAUTHORIZED);
    }
    return comment;
}
```

- `visibleComment`: 지우기에 있던 앞부분(404 판단과 401)을 꺼내 고치기와 같이 쓴다. 스텝 6의 `delete`가 하던 일과 한 줄도 다르지 않다.
- **블로그 주인도 남의 댓글은 고칠 수 없다.** 주인은 지울 수만 있다(CMT-02). 남이 쓴 글을 주인이 고칠 수 있으면 작성자가 하지 않은 말을 작성자 이름으로 남길 수 있다. 그래서 `isWrittenBy`만 본다(`|| blog.isOwnedBy`가 없다).
- **숨긴 댓글**: ADMIN-03 "작성자는 수정할 수 없고 삭제는 할 수 있다". 고칠 수 있으면 관리자가 숨긴 뒤 내용을 바꿔 숨긴 이유를 지울 수 있다. 숨긴 댓글은 작성자 본인에게 내용이 보이지만(5.4) `canEdit`은 `false`다.
- 컨트롤러는 `checkEditable`(읽기 전용 트랜잭션으로 같은 판단만)을 먼저 부르고, 그다음 `requestValidator.validate`로 입력을 본다. 401·403이 400보다 먼저 나오게 하는 이 프로젝트의 방식이다(5.2, [22](./22-bean-validation.md)). 판단을 두 번 하는 대가로 순서를 지킨다.

**`flush()`를 왜 부르나.** 응답의 `updatedAt`은 "고친 적이 없으면 `null`"이고, 고쳤는지는 `updatedAt != createdAt`으로 본다(`CommentResponse`). `updatedAt`은 `@LastModifiedDate`라 JPA가 **UPDATE를 보내기 직전**(`@PreUpdate`)에 채운다. 그런데 변경 감지의 UPDATE는 보통 트랜잭션이 끝날 때 나간다. 그 전에 응답을 만들면 `updatedAt`이 아직 옛값(= `createdAt`)이라 "수정됨"이 빠진다. `flush()`로 UPDATE를 먼저 보내면 그때 `updatedAt`이 채워지고, 같은 객체로 응답을 만든다.

**글은 그대로다.** 댓글을 고쳐도 글의 `updated_at`이나 `comment_count`는 바뀌지 않는다. 댓글 수는 행 수라 고치기와 상관없고, 글의 "수정" 표시는 글 내용을 고쳤을 때만이다(5.6과 같은 생각). 테스트 `authorEditsOwnCommentAndSeesEditedTime`이 댓글 수가 그대로인지 본다.

**화면.** `viewer.canEdit`이 `true`인 댓글에 "수정"이 보이고, 누르면 그 자리에 고치는 칸이 열린다. 저장하면 서버가 돌려준 댓글로 목록의 같은 id를 바꾼다(`afterEdit`, 답글을 고치면 그 부모 안에서만 바꾼다). 고친 댓글에는 "수정됨"이 붙는다. 댓글 한 줄과 쓰기 칸은 방명록·관리 화면과 같이 쓰려고 `CommentItem`·`CommentForm`으로 나눴다([50](./50-shared-rules-comment-guestbook.md) 5.6).

테스트 `CommentEditIntegrationTest`:

| 테스트 | 확인하는 것 |
| --- | --- |
| `authorEditsOwnCommentAndSeesEditedTime` | 작성자에게만 `canEdit`, 고치면 앞뒤 공백을 지운 내용과 `updatedAt`, 다시 읽어도 같음, 댓글 수 그대로 |
| `onlyAuthorCanEditAndPermissionComesBeforeInputErrors` | 비회원 401(틀린 입력이어도), 블로그 주인 403, 작성자의 1,001자·공백 400, 실패한 요청 뒤 내용 그대로 |
| `blindedDeletedOrHiddenCommentsCannotBeEdited` | 숨긴 댓글 403과 `canEdit: false`, 지운 댓글 404, 비공개 글의 댓글 404 |

### 5.13 (스텝 17) 비밀댓글과 댓글 허용 (T101 CMT-06, T102 CMT-07)

두 기능 모두 **판단은 이미 있었고 입력만 열었다.**

- 비밀댓글: 보는 사람 기준 판단(비밀이면 글 주인과 작성자만 내용, 다른 사람에게는 `SECRET`)은 스텝 6부터 있었고, 스텝 14에서 방명록과 같이 쓰도록 `CommentViews`로 옮겼다([50](./50-shared-rules-comment-guestbook.md)). 이번에는 댓글 쓰기의 `secret`을 막던 `@AssertFalse`(5.3 "아직 없는 기능은 400")를 지우고 저장에 넘겼다. 화면은 댓글·답글 칸에 "비밀댓글" 체크(방명록과 같은 `CommentForm`, 글자만 다름).
- 댓글 허용: 글을 쓸 수 있는지(`writablePost`)가 스텝 6부터 `post.isCommentAllowed()`를 보고 403 `COMMENTS_DISABLED`를 주고 있었다. 글 저장에서 `commentAllowed: false`를 막던 400을 지우고, 글쓰기 화면에 "댓글 허용" 체크를 더했다. **보내지 않으면 새 글은 허용, 수정은 그대로**다(PATCH처럼, [38](./38-member-profile-update.md) 3.1). 댓글을 막아도 이미 달린 댓글은 보인다. 글 상세는 쓰기 칸 대신 "이 글에는 댓글을 쓸 수 없습니다"를 그린다(스텝 6부터).

5.3에서 "아직 없는 기능의 칸은 조용히 버리지 말고 400"으로 해 둔 덕에, 기능을 열 때 바꿀 곳이 400을 지우는 한 줄로 분명했다. 버렸다면 어디서 값이 사라지는지 찾아야 했을 것이다.

## 6. 자주 하는 실수와 함정

1. **댓글 API에서 글 가시성을 따로 짜기**: 글 상세와 규칙이 어긋나면 비공개 글의 댓글이 새거나, 볼 수 있는 글에 댓글을 못 쓴다. 같은 판단 코드를 부른다.
2. **401을 404보다 먼저**: 비회원에게 "로그인하면 쓸 수 있다"고 답하면 비공개 글이 있다는 사실이 드러난다.
3. **`@Valid`로 본문을 먼저 검증**: 권한 없는 사람에게 403 대신 400이 나간다. 권한 판단 뒤에 검증한다.
4. **화면에서만 가리기**: JSON에 비밀댓글 내용을 담고 화면에서 "비밀댓글입니다"로 바꾸면 개발자 도구로 다 보인다. 서버가 `null`로 보낸다.
5. **카운터를 "읽고 더해서 쓰기"**: 동시에 댓글이 달리면 하나가 사라진다. `count = count + 1` 한 줄 UPDATE.
6. **카운터 UPDATE가 `updated_at`을 바꿈**: MySQL `ON UPDATE`라 댓글만 달려도 "수정됨"이 붙는다. `updatedAt = updatedAt`.
7. **`clearAutomatically` 전에 flush 안 함**: 그 전의 변경(댓글 삭제)이 저장되지 않는다.
8. **작성자마다 쿼리**: 20개 목록에 쿼리 20번(N+1). `IN`으로 한 번에.
9. **관리자에게 삭제 권한 주기**: 헌법 원칙 V 위반. 관리자는 숨김(되돌릴 수 있음)만.
10. **버튼 `disabled`만으로 연타를 막았다고 생각**: state는 다음 그리기에서 반영된다. 즉시 막으려면 ref.
11. **같은 응답을 두 번 붙임**: 서버가 같은 키에 같은 응답을 주는 것은 정상이다. 화면이 id로 중복을 거른다.
12. **(답글) 부모가 같은 글인지 안 봄**: 주소의 글과 다른 글(비공개 글 포함)의 댓글에 답글을 붙일 수 있다. `parentOf`가 같은 글인지 확인한다.
13. **(답글) 답글을 지운 부모를 그냥 목록에서 뺌**: 답글이 고아가 되어 사라지거나, 누구에게 단 답글인지 모르게 된다. 살아 있는 답글이 있으면 DELETED 자리로 남긴다.
14. **(스텝 14) 주인에게 남의 댓글 고치기를 열어 주기**: 지우기 권한(본인·주인)을 그대로 복사하면 생긴다. 고치기는 본인만이다.
15. **(스텝 14) 고친 뒤 flush 없이 응답 만들기**: `@LastModifiedDate`가 아직 채워지지 않아 "수정됨"이 빠진다(5.12).
14. **(답글) 답글까지 섞어 20개로 자르기**: 부모와 답글이 다른 쪽에 갈라진다. 묶음은 최상위 기준, 답글은 부모에 모두 붙인다.
15. **(답글) 화면의 지운 뒤 규칙과 서버의 목록 규칙이 다름**: 새로고침하면 화면이 바뀐다. 같은 규칙을 순수 함수로 떼어 테스트했다.

## 7. 직접 해 보기

**실습 1. 테스트**

```bash
./mvnw test -Dtest=CommentIntegrationTest
```

**실습 2. curl로 상태 코드 순서 보기** (bash, `docker compose up -d && ./mvnw spring-boot:run`)

```bash
R="--resolve myblog.blog.test:8080:127.0.0.1"
H='-H X-Requested-With:XMLHttpRequest -H Content-Type:application/json'
# 공개 글 12에 비회원: 401
curl -s $R $H -H "Idempotency-Key: $(uuidgen)" -X POST myblog.blog.test:8080/api/posts/12/comments -d '{"content":"x"}'
# 비공개 글 13에 비회원: 401이 아니라 404
curl -s $R $H -H "Idempotency-Key: $(uuidgen)" -X POST myblog.blog.test:8080/api/posts/13/comments -d '{"content":"x"}'
# 로그인 쿠키(jar)로 빈 내용: 400
curl -s $R $H -b jar -H "Idempotency-Key: $(uuidgen)" -X POST myblog.blog.test:8080/api/posts/12/comments -d '{"content":" "}'
```

**실습 3. 카운터를 일부러 틀리게**

`PostRepository.addCommentCount`의 식에서 `p.updatedAt = p.updatedAt`을 지우고 `memberWritesCommentAndCountGoesUp`을 돌린다. `updated_at`이 바뀌어 실패한다. 되돌린다.

**실습 4. flush를 빼 보기**

`CommentService.delete`에서 `commentRepository.flush();`를 지우고 `authorAndBlogOwnerCanDeleteOthersCannot`를 돌려 본다. 지운 댓글이 목록에 남는지, 수와 목록이 어긋나는지 본다. 되돌린다.

**실습 5. 연타 버그 다시 만들기**

`Comments.tsx`에서 `if (inFlight.current) { return }`와 `!comments.some(...)` 조건을 지우고 `npm run dev`로 띄운다. 개발자 도구 콘솔에서

```js
const b = [...document.querySelectorAll('#comments button')].find(x => x.textContent === '등록'); b.click(); b.click()
```

를 실행하면 화면엔 둘, 새로고침하면 하나다. 되돌린다.

**실습 6. 비밀댓글 가림 확인**

```bash
docker exec blog-mysql mysql -ublog -pblog blog -e "UPDATE comment SET is_secret = 1 WHERE id = {댓글 id}"
```

비회원·다른 회원·블로그 주인·작성자로 `GET /api/posts/{id}/comments`를 불러 `state`와 `content`를 비교한다.

**실습 7. (스텝 7) 답글과 삭제 자리**

```bash
./mvnw test -Dtest='ReplyIntegrationTest' && (cd frontend && npx vitest run commentList)
```

브라우저에서: B로 댓글 → A로 그 댓글에 "답글" → B로 자기 댓글 삭제 → "삭제된 댓글입니다" 아래에 A의 답글이 남는지 본다. A가 답글도 지우면 자리째 사라진다. 새로고침해도 같은지 확인한다.

curl로 답글의 답글을 시도해 400과 `fieldErrors[0].field == "parentId"`를 확인한다.

```bash
curl -s $R $H -b jar -H "Idempotency-Key: $(uuidgen)" -X POST myblog.blog.test:8080/api/posts/12/comments \
  -d '{"content":"답글의 답글","parentId":{답글 id}}'
```

## 8. 확인 문제

1. 댓글 API가 글 상세와 같은 `PostReadService.readable`을 부르는 이유는?
<details><summary>답</summary>댓글은 글에 딸린 데이터라 글을 볼 수 없는 사람에게는 댓글도 없어야 한다. 판단 코드를 하나로 두어야 글과 댓글의 규칙이 어긋나 비공개 글의 존재가 새는 일이 없다.</details>

2. 비회원이 남의 비공개 글에 댓글을 쓰면 401이 아니라 404인 이유는?
<details><summary>답</summary>401은 "로그인하면 할 수 있다", 즉 그 글이 있다는 뜻이 된다. 볼 수 없는 글은 존재를 숨기므로 로그인 여부보다 먼저 404를 준다(헌법 원칙 II).</details>

3. 비밀댓글을 화면에서만 가리지 않고 응답 JSON의 content·author를 null로 보내는 이유는?
<details><summary>답</summary>화면에서만 가리면 JSON에는 내용이 담겨 있어 개발자 도구나 직접 요청으로 누구나 읽을 수 있다. 보여 주면 안 되는 값은 서버가 아예 보내지 않는다.</details>

4. `comment_count`를 따로 두는 이유와, 생기는 책임은?
<details><summary>답</summary>목록마다 COUNT 쿼리를 하지 않으려고(비정규화). 대신 댓글 행 수와 어긋나지 않게 할 책임이 생겨, 저장·삭제와 같은 트랜잭션에서 원자적 UPDATE(count = count ± 1)로 바꾼다.</details>

5. `UPDATE ... SET comment_count = comment_count + 1`이 "읽고 1 더해 쓰기"보다 나은 이유는?
<details><summary>답</summary>두 요청이 동시에 읽고 쓰면 같은 값을 읽어 하나가 사라진다(lost update). 한 줄 UPDATE는 DB가 행 잠금으로 차례로 처리해 둘 다 반영된다.</details>

6. `CommentService.delete`에서 `flush()`를 `addCommentCount`보다 먼저 하는 이유는?
<details><summary>답</summary><code>addCommentCount</code>는 <code>clearAutomatically = true</code>라 실행 뒤 영속성 컨텍스트를 비운다. 그 전에 flush하지 않으면 <code>deleted_at</code> 변경이 DB로 가기 전에 사라져 삭제가 저장되지 않는다.</details>

7. 서비스 관리자에게 댓글 삭제 권한이 없는 이유는?
<details><summary>답</summary>헌법 원칙 V(제재는 숨김이며 되돌릴 수 있다). 관리자는 지우지 않고 숨김(BLIND)으로 처리하고, 숨김은 해제할 수 있다.</details>

8. 서버의 Idempotency-Key가 있는데도 화면에 같은 댓글이 두 번 붙은 이유와 고친 방법은?
<details><summary>답</summary>버튼을 끄는 <code>setSubmitting</code>은 다음 그리기에서 반영되어 두 번째 클릭이 들어왔고, 서버는 같은 키라 같은 댓글을 두 번 돌려줬다. 화면이 그 두 응답을 각각 붙였다. 즉시 바뀌는 <code>useRef</code>(inFlight)로 처리 중 클릭을 막고, 이미 있는 id는 붙이지 않게 했다.</details>

9. 댓글 20개를 보여 줄 때 작성자 대표 블로그 주소를 쿼리 한 번으로 읽는 방법은?
<details><summary>답</summary>작성자 id를 모아 <code>PrimaryBlogAddresses.of(ids)</code>로 <code>where member_id in (...)</code> 한 번에 읽고, 맵에서 꺼내 쓴다. 작성자마다 찾으면 N+1이다.</details>

10. (스텝 7) "한 단계 답글"은 테이블 구조가 아니라 어디서 지키나? 왜 그렇게 해도 되나?
<details><summary>답</summary><code>parent_id</code> 칸은 몇 단계든 저장할 수 있다. 서비스의 <code>parentOf</code>가 부모의 <code>parent</code>가 있으면(이미 답글이면) 400으로 막는다. 댓글은 이 서비스로만 저장되므로 한 곳에서 지키면 된다.</details>

11. (스텝 7) 답글이 있는 댓글을 지우면 응답 JSON에서 그 댓글은 어떻게 보이나? 왜 내용을 보내지 않나?
<details><summary>답</summary><code>state: "DELETED"</code>, <code>content</code>·<code>author</code>는 <code>null</code>, <code>replies</code>에 살아 있는 답글. 지운 내용은 더 이상 보여 줄 수 없는 데이터라, 화면에서 가리지 않고 서버가 보내지 않는다.</details>

12. (스텝 7) 목록을 최상위 댓글 20개 + 그 답글 전부로 읽을 때 쿼리는 몇 번이고, 왜 그렇게 나눴나?
<details><summary>답</summary>부모 21개(다음 묶음 확인용 1개 포함) 한 번, 그 부모들의 답글을 <code>parent_id IN (...)</code>으로 한 번(작성자 주소는 따로 한 번). 답글까지 섞어 자르면 부모와 답글이 쪽 사이로 갈라지고, 부모마다 답글을 읽으면 N+1이 된다.</details>

13. (스텝 14) 블로그 주인은 남의 댓글을 지울 수는 있는데 고칠 수는 없다. 왜 다르게 했나?
<details><summary>답</summary>지우기는 내 블로그에서 글을 치우는 일이라 주인 권한(CMT-02)이다. 고치기는 그 사람이 한 말을 바꾸는 일이라, 주인이 할 수 있으면 작성자가 하지 않은 말을 작성자 이름으로 남길 수 있다. 명세도 CMT-03 "본인만"이다.</details>

14. (스텝 14) 댓글을 고친 뒤 응답을 만들기 전에 <code>commentRepository.flush()</code>를 부르는 이유는?
<details><summary>답</summary><code>updatedAt</code>은 <code>@LastModifiedDate</code>라 UPDATE를 보내기 직전에 채워진다. 변경 감지는 보통 트랜잭션 끝에 UPDATE를 보내므로, 그 전에 응답을 만들면 <code>updatedAt</code>이 <code>createdAt</code>과 같아 응답의 <code>updatedAt</code>이 null(고친 적 없음)이 된다. flush로 UPDATE를 먼저 보내 값을 채운다.</details>

## 9. 더 읽을거리

- data-model.md "소통" 절(comment), contracts/rest-api.md "CMT 댓글"과 "Comment" 응답 객체
- Spring Data JPA 레퍼런스 "Modifying Queries"(`@Modifying`, `clearAutomatically`), "Query by Example and Specifications"의 fluent API(`findBy`)
- Hibernate 문서 "Fetching"(N+1과 `join fetch`)
- React 문서 "Referencing Values with Refs"(`useRef`가 다시 그리기를 일으키지 않는 이유): https://react.dev/learn/referencing-values-with-refs
- MySQL 문서 "InnoDB Locking"(UPDATE의 행 잠금)
