# 56. 저장한 글: 멱등한 저장, 스냅숏, 읽을 때 다시 보는 가시성

> 관련 스텝: [스텝 20](../step-20.md) (T074~T077 저장한 글) · 관련 개념: [16 인가와 가시성 판단](./16-authorization-visibility.md), [17 멱등성과 Redis](./17-idempotency-redis.md), [51 구독과 알림](./51-subscription-notification.md)(INSERT IGNORE, 거르는 커서 목록), [08 페이지 처리](./08-pagination.md), [54 꾸미기와 블로그의 수명](./54-theme-move-delete-withdraw.md)(탈퇴 정리)

## 1. 이 문서로 배우는 것

- "저장" 버튼을 **멱등한 PUT·DELETE**로 만들기: 연달아 눌러도, 두 탭에서 눌러도 한 행
- **스냅숏(snapshot)**: 원본이 바뀌거나 사라질 것을 알고 "그때의 값"을 따로 남기는 설계와, 일반적인 정규화 원칙의 예외
- 목록을 그릴 때 **항목마다 가시성을 다시 판단**하기: 저장할 때 볼 수 있었던 글이 지금도 볼 수 있다는 보장은 없다
- 볼 수 없는 글을 "숨기지 않고, 이유도 말하지 않고" 보여 주는 방법
- 상태 코드 순서(404 → 401)를 지키는 이유
- 데이터 수명: 탈퇴하면 저장도 지운다, 글이 지워지면 저장은 남는다

## 2. 왜 필요한가

명세 SOC-03: "회원은 글을 저장하고 마이페이지에서 저장한 글을 본다. 저장한 글이 삭제·비공개가 되면 목록에 '볼 수 없는 글'로 남고, 저장할 때의 제목을 보여 준다."

이 문장 하나에 세 가지 문제가 들어 있다.

1. 저장 버튼은 자주 **연달아 눌린다**. 같은 글이 두 번 저장되면 안 된다.
2. 글은 저장한 뒤에 **바뀐다**. 비공개가 되고, 지워지고, 관리자가 숨기고, 구독자 공개로 바뀌고, 블로그가 이사한다. 목록은 "지금" 기준이어야 한다.
3. 볼 수 없게 된 글의 **제목은 어디서 가져오나**? 글이 지워졌거나 비공개면 글 테이블의 제목을 보여 주는 순간 남이 볼 수 없는 정보를 새는 것이다.

## 3. 기본 개념

### 3.1 멱등성 다시 보기

같은 요청을 한 번 보내든 열 번 보내든 서버 상태가 같으면 **멱등**하다([17](./17-idempotency-redis.md)). HTTP에서 PUT과 DELETE는 멱등하다고 약속한 메서드다.

| 설계 | 연달아 두 번 누르면 |
| --- | --- |
| `POST /bookmarks` (새로 만들기) | 두 번째에 409를 주거나, 막지 않으면 행이 둘 |
| `POST /bookmark/toggle` (뒤집기) | 저장 → 취소. 사용자가 본 것과 반대가 됨 |
| `PUT /posts/{id}/bookmark` (이 상태로 만들기) | 둘 다 "저장됨". 같은 결과 |

"뒤집기"는 편해 보이지만 요청 두 개가 겹치면 최종 상태를 예측할 수 없다. "**저장된 상태로**"(PUT), "**저장 안 된 상태로**"(DELETE)라고 원하는 상태를 말하면 순서가 섞여도 마지막 요청이 원하는 상태가 남는다. 공감(스텝 7)과 구독(스텝 16, [51](./51-subscription-notification.md))도 같은 방식이다.

### 3.2 DB에서 멱등하게: UNIQUE + INSERT IGNORE

"이미 있으면 넘어가기"를 자바에서 `exists` → `save`로 하면 두 요청이 동시에 `exists=false`를 보고 둘 다 넣으려 한다. 그래서 **DB가 막게** 한다.

- `post_bookmark`에 `UNIQUE(member_id, post_id)`가 있다(schema.sql).
- `INSERT IGNORE`는 UNIQUE에 걸리면 오류 대신 **0행**을 넣고 끝난다(MySQL). 동시에 들어와도 한 요청만 1행, 나머지는 0행.

### 3.3 스냅숏: 일부러 복사해 두는 값

데이터베이스 설계의 기본은 "같은 사실은 한 곳에"(정규화)다. 글 제목은 `post.title`에만 있어야 하고, 다른 곳에서는 `post_id`로 찾아간다. 그런데 이 원칙의 **예외**가 있다. "그때의 값"이 필요할 때다.

| 예 | 왜 복사하나 |
| --- | --- |
| 주문서의 상품 가격 | 상품 가격이 나중에 바뀌어도 주문할 때 낸 금액은 그대로여야 한다 |
| 관리 이력의 사유(스텝 18, [53](./53-admin-moderation-audit.md)) | 고치지 않는 기록 |
| **저장한 글의 제목·블로그 이름** | 글이 지워지거나 비공개가 되어 원본을 보여 줄 수 없을 때 "무엇을 저장했었는지"는 알려 줘야 한다 |

`post_bookmark.title_snapshot`, `blog_name_snapshot`이 그 칸이다. 저장할 때 한 번 쓰고 고치지 않는다.

스냅숏 제목은 **저장한 사람이 그때 이미 본 값**이다. 그래서 글이 비공개가 된 뒤에 보여 줘도 새는 정보가 없다. 반대로 글 테이블의 **지금 제목**을 보여 주면, 주인이 비공개로 바꾼 뒤 고친 제목이 남에게 보인다.

### 3.4 저장할 때의 판단과 읽을 때의 판단

권한 판단을 **언제** 하느냐는 두 가지다.

- **쓸 때(저장할 때)**: 볼 수 없는 글은 저장할 수도 없다(404). 저장 버튼이 있는 글 상세를 볼 수 있어야 저장하니 당연하다.
- **읽을 때(목록을 그릴 때)**: 저장할 때 볼 수 있었어도, 지금도 볼 수 있는지 **다시** 본다. 저장 행에 "볼 수 있음" 같은 칸을 두면 글이 바뀔 때마다 모든 저장 행을 고쳐야 하고, 하나라도 빠지면 새는 곳이 생긴다.

알림(스텝 16, [51](./51-subscription-notification.md) 3.3)도 "문구는 쓸 때, 링크·가시성은 읽을 때"였다. 바뀔 수 있는 판단은 읽을 때 한다.

### 3.5 이유를 말하지 않는 "볼 수 없음"

볼 수 없게 된 이유는 여러 가지다: 지워짐, 비공개, 관리자 숨김, 구독자 공개(구독을 끊음), 블로그 삭제·이용 제한, 주인 정지·탈퇴. 이 중 "비공개로 바뀌었다"나 "관리자가 숨겼다"를 알려 주면 **남의 글의 상태**를 알려 주는 것이다. 이 서비스는 볼 수 없는 글을 처음부터 404로 다뤘다([16](./16-authorization-visibility.md), 헌법 II). 그래서 목록도 `visible: false` 하나로만 말한다.

## 4. 동작 원리

```
[저장] PUT /api/posts/20/bookmark  (블로그 주소)
  → BookmarkService.save
      postReadService.readable(blog, 20, 회원?)   ← 볼 수 없으면 404, 구독자 공개면 403
      회원이 아니면 401
      INSERT IGNORE post_bookmark(post_id, member_id, title_snapshot, blog_name_snapshot)
  ← { bookmarked: true }

[목록] GET /api/me/bookmarks?cursor=  (플랫폼 주소)
  → SELECT … WHERE member_id = ? ORDER BY created_at DESC, id DESC LIMIT 21
  → 행마다 PostVisibilityPolicy.decide(post_id, 블로그 없음, 나)
        Visible / Owner(숨김 아님) → { postId, post: PostSummary, visible: true, savedAt }
        그 밖(NotFound, SubscribersOnly, 숨긴 내 글)  → { postId, visible: false, titleSnapshot, blogNameSnapshot, savedAt }
  ← { content: [...20], nextCursor }

[목록에서 취소] DELETE /api/me/bookmarks/20
  → DELETE … WHERE member_id = 나 AND post_id = 20   ← 글을 확인하지 않는다(볼 수 없게 된 글도 지워야 해서)
```

## 5. 이 프로젝트에서는

### 5.1 저장: `bookmark/domain/PostBookmarkRepository`

```java
@Modifying
@Query(value = """
        INSERT IGNORE INTO post_bookmark (post_id, member_id, title_snapshot, blog_name_snapshot)
        VALUES (:postId, :memberId, :title, :blogName)""", nativeQuery = true)
int insertIfAbsent(@Param("postId") Long postId, @Param("memberId") Long memberId, @Param("title") String title,
                   @Param("blogName") String blogName);

@Modifying
@Query(value = "DELETE FROM post_bookmark WHERE member_id = :memberId AND post_id = :postId", nativeQuery = true)
int deleteIfPresent(@Param("memberId") Long memberId, @Param("postId") Long postId);
```

- `nativeQuery = true`: JPQL에는 `INSERT IGNORE`가 없어서 MySQL 문장을 그대로 쓴다.
- `@Modifying`: 조회가 아니라 바꾸는 문장이라고 Spring Data에 알린다. 돌려받는 `int`는 바뀐 행 수다.
- 다시 저장하면 0행이라 **처음 저장한 시각·제목이 남는다**. 그 사이 제목이 바뀌었어도 스냅숏은 처음 값이다. 목록 순서(저장 최신순)도 처음 저장한 때 기준이다.
- `created_at`은 DB 기본값(`CURRENT_TIMESTAMP`)으로 채워진다.

### 5.2 상태 코드 순서: `BookmarkService.savable`

```java
private Post savable(Blog blog, Long postId, LoginMember member) {
    Post post = postReadService.readable(blog, postId, member == null ? null : member.id());
    if (member == null) {
        throw new BusinessException(ErrorCode.UNAUTHORIZED);
    }
    return post;
}
```

- **글 확인이 먼저, 로그인 확인이 나중**이다. 거꾸로 하면 비회원이 아무 번호에나 저장을 눌렀을 때 "있는 글이면 401, 없는 글이면 404"가 아니라 늘 401이 나온다. 이건 괜찮아 보이지만, 공감·댓글 등 다른 API는 모두 "404 → 401" 순서다(contracts "상태 코드 순서"). 한 서비스 안에서 순서가 다르면, 순서 차이로 비공개 글의 존재를 알아내는 틈이 생긴다. 그래서 같은 순서를 따른다.
- `postReadService.readable`은 글 상세가 쓰는 판단 그대로다. 볼 수 없으면 404, 구독자 공개인데 구독하지 않았으면 403.

### 5.3 목록: 항목마다 다시 판단

```java
for (PostBookmark bookmark : bookmarks) {
    Post post = switch (postVisibilityPolicy.decide(bookmark.getPostId(), null, memberId)) {
        case PostAccess.Owner owner -> owner.blinded() ? null : owner.post();
        case PostAccess.Visible visible -> visible.post();
        default -> null;
    };
    items.add(new SavedItem(bookmark, post));
}
```

- `PostVisibilityPolicy.decide`는 글 상세·이전 다음 글·알림이 모두 쓰는 판단이다([16](./16-authorization-visibility.md)). 두 번째 인자 `null`은 "어느 블로그 주소에서 보는지 따지지 않는다"는 뜻이다. 목록은 플랫폼 주소에서 여러 블로그의 글을 모아 보기 때문이다.
- 결과가 sealed 타입(`PostAccess`)이라 `switch`가 경우를 빠짐없이 다룬다. `default`는 NotFound와 SubscribersOnly다.
- **내 글이어도 관리자가 숨긴 글은 볼 수 없음**으로 둔다. 글 상세에서 주인은 숨긴 글을 "숨겨진 글" 안내와 함께 보지만, 저장 목록에서 다시 펼쳐 보일 이유는 없다.
- 항목마다 판단하므로 20개면 판단 20번이다. 판단 자체가 글 하나를 읽는 일이라 지금 규모에서는 문제 없다. 많아지면 글을 한 번에 읽어 판단하는 쪽으로 바꾼다.
- 21개를 읽어 21번째가 있으면 다음 커서를 만든다([08](./08-pagination.md)). 커서는 (저장 시각, 행 번호)라 같은 시각에 저장한 것도 빠지지 않는다.

### 5.4 응답 모양: `SavedPostResponse`

```java
@JsonInclude(JsonInclude.Include.NON_NULL)
public record SavedPostResponse(Long postId, PostSummaryResponse post, boolean visible, String titleSnapshot,
                                String blogNameSnapshot, OffsetDateTime savedAt) {
```

- `@JsonInclude(NON_NULL)`: `null`인 칸은 JSON에서 아예 뺀다. 볼 수 있는 항목에는 `titleSnapshot`이 없고, 볼 수 없는 항목에는 `post`가 없다. 화면은 `visible`만 보고 분기한다.
- 볼 수 없는 항목에도 `postId`는 준다. 목록에서 바로 "저장 취소"(`DELETE /api/me/bookmarks/{postId}`)를 하려면 번호가 필요하다. 번호는 저장한 사람이 이미 알던 값이라 새는 것이 없다.

### 5.5 목록에서 바로 취소: 글을 확인하지 않는 DELETE

```java
@Transactional
public void remove(Long memberId, Long postId) {
    bookmarkRepository.deleteIfPresent(memberId, postId);
}
```

- 글 상세의 DELETE와 달리 **글이 볼 수 있는지 보지 않는다**. 지워진 글의 저장을 지우려는데 "그 글은 없습니다(404)"가 나오면 영영 지울 수 없다.
- `WHERE member_id = 나`가 권한 검사다. 남의 저장은 조건에 걸리지 않아 0행이다.

### 5.6 데이터 수명

| 일 | 저장은 |
| --- | --- |
| 글 삭제(소프트 삭제) | 남는다. 목록에 "볼 수 없는 글"과 저장할 때 제목 |
| 글 비공개·숨김·구독자 공개 | 남는다. 다시 공개되면 저절로 "볼 수 있음"으로(읽을 때 판단이라) |
| 글 제목 수정 | 볼 수 있으면 지금 제목(`post.title`), 볼 수 없으면 저장할 때 제목 |
| 블로그 이사 | 글 번호가 그대로라 저장도 그대로, 링크는 새 주소(T106) |
| **저장한 회원 탈퇴** | `MemberTraceCleaner`가 그 회원의 저장 행을 지운다(T077) |

탈퇴 정리는 스텝 19의 순서([54](./54-theme-move-delete-withdraw.md))에 한 줄 더한 것이다. 저장은 본인만 보는 데이터라 탈퇴 뒤 남길 이유가 없다.

### 5.7 화면

- 글 상세: `components/BookmarkButton.tsx`. 글 상세 응답의 `viewer.bookmarked`로 처음 상태를 그린다. 누르면 공감 버튼처럼 **먼저 바꿔 보이고**(낙관적 갱신, [25](./25-react-forms-data.md)) PUT/DELETE의 응답 `bookmarked`로 맞춘다. 실패하면 원래 상태로 되돌리고 오류를 보인다. 요청이 가는 동안 또 누르면 무시한다(`useRef`의 `inFlight`). 비회원은 로그인 화면으로 갔다가 돌아온다(`redirectToLogin`).
- 마이페이지: `components/MeTabs.tsx`(내 정보·저장한 글·알림 탭), `pages/me/BookmarksPage.tsx`(`/me/bookmarks`). 볼 수 없는 항목은 저장할 때 제목·블로그 이름과 "볼 수 없는 글" 표시로 남고, 누르면 글로 가지 않고 "더 이상 볼 수 없는 글입니다." 안내만 띄운다(이유는 알리지 않는다). 항목마다 "저장 취소" 버튼이 있고 누르면 그 자리에서 사라진다.

Thymeleaf로 치면 `th:if="${item.visible}"`로 두 가지 조각을 나눠 그리는 것과 같다. 다른 점은 데이터를 서버가 HTML로 만들지 않고 JSON으로 주고, 화면이 `{item.visible ? … : …}`로 고른다는 것뿐이다.

### 5.8 테스트: `BookmarkIntegrationTest`

- `saveIsIdempotentAndListShowsInvisiblePostsBySnapshot`: 비회원 PUT 401 → 같은 글에 PUT 두 번 → 행은 글마다 하나, 글 상세 `viewer.bookmarked: true` → 주인이 둘째 글을 비공개로 바꾸고 제목도 바꿈 → 목록 첫 줄은 `visible:false`, 처음 제목 스냅숏, `post` 칸 없음 → 그 글 주소는 404, 목록의 DELETE로는 지워짐 → 글 상세 DELETE는 `bookmarked:false` → 비회원 목록 401.
- `bookmarksPageByTwenty`: 21개 저장 → 첫 묶음 20개와 `nextCursor`, 다음 묶음 1개와 `nextCursor: null`.

## 6. 자주 하는 실수와 함정

- **"뒤집기" API**: 겹친 요청에서 상태가 엉킨다. 원하는 상태를 말하는 PUT·DELETE로.
- **`exists` 후 `save`**: 동시 요청에 행이 둘(또는 UNIQUE 오류 500). DB의 UNIQUE와 `INSERT IGNORE`로.
- **저장 행에 "볼 수 있음"을 저장**: 글이 바뀔 때마다 고쳐야 하고 하나라도 빠지면 샌다. 읽을 때 판단한다.
- **볼 수 없는 글을 목록에서 빼 버림**: 사용자는 저장한 글이 왜 사라졌는지 모른다. 명세도 "남긴다"고 했다.
- **볼 수 없는 글에 지금 제목을 보여 줌**: 비공개 뒤 고친 제목이 샌다. 스냅숏을 쓴다.
- **이유를 알려 줌("비공개로 바뀌었습니다")**: 남의 글 상태를 알려 주는 것이다.
- **목록의 취소에도 글 확인을 붙임**: 지운 글의 저장을 영영 못 지운다.
- **탈퇴 정리에 새 테이블을 빠뜨림**: 기능을 더할 때마다 "회원이 지워지면 이 행은?"을 묻는다.

## 7. 직접 해 보기

준비: `docker compose up -d`, `./mvnw spring-boot:run`, 회원 둘(갑: 블로그 주인, 을: 독자).

1. 을로 갑의 글 상세 → "☆ 저장" → "★ 저장됨". 버튼을 빠르게 여러 번 눌러 본다.
2. DB에서 행이 하나인지 본다.

   ```sql
   SELECT member_id, post_id, title_snapshot, created_at FROM post_bookmark ORDER BY id DESC LIMIT 5;
   ```

3. 마이페이지 → "저장한 글" 탭. 글이 보인다.
4. 갑으로 그 글을 비공개로 바꾸고 제목도 고친다. 을의 저장한 글을 새로 고치면 "지금은 볼 수 없는 글"과 **처음 제목**이 보인다.
5. 갑이 다시 공개로 바꾸면 을의 목록에 **고친 제목**이 링크로 보인다.
6. 을의 목록에서 "저장 취소" → 사라짐.

```bash
./mvnw test -Dtest=BookmarkIntegrationTest
```

## 8. 확인 문제

1. 저장 API를 `POST /bookmark/toggle`이 아니라 PUT·DELETE로 만든 이유는?
<details><summary>답</summary>뒤집기는 요청이 겹치면 최종 상태가 순서에 따라 달라진다. PUT(저장된 상태로)·DELETE(저장 안 된 상태로)는 원하는 상태를 말하므로 몇 번 보내도 같은 결과다(멱등).</details>

2. 자바에서 `existsBy…`로 확인하고 `save`하는 대신 `INSERT IGNORE`를 쓴 이유는?
<details><summary>답</summary>동시에 온 두 요청이 모두 "없음"을 보고 둘 다 넣으려 할 수 있다. UNIQUE 제약과 INSERT IGNORE면 DB가 한 행만 남기고 나머지는 0행으로 끝낸다.</details>

3. 정규화 원칙을 어기고 제목을 `post_bookmark`에 복사해 두는 이유는?
<details><summary>답</summary>글이 지워지거나 비공개가 되면 글의 지금 제목을 보여 줄 수 없다(새는 정보). 저장할 때 사용자가 이미 본 제목을 남겨 두면 "무엇을 저장했었는지"를 안전하게 보여 줄 수 있다.</details>

4. 글이 비공개가 된 뒤 주인이 제목을 바꿨다. 저장한 사람의 목록에 보이는 제목은? 다시 공개되면?
<details><summary>답</summary>비공개 동안은 저장할 때의 제목(스냅숏). 다시 공개되면 읽을 때 "볼 수 있음"으로 판단되어 지금 제목(post.title)이 보인다.</details>

5. 저장 행에 `visible` 칸을 두지 않고 목록을 그릴 때마다 판단하는 이유는?
<details><summary>답</summary>가시성은 글·블로그·주인·구독 상태에 따라 계속 바뀐다. 저장해 두면 그 모든 변경에서 저장 행을 고쳐야 하고, 빠뜨리면 볼 수 없는 글이 보인다. 판단을 한 곳(PostVisibilityPolicy)에서 읽을 때 하면 언제나 지금 기준이다.</details>

6. 비회원이 없는 글 번호에 저장을 누르면 404, 있는 공개 글이면 401이다. 왜 이 순서인가?
<details><summary>답</summary>이 서비스의 다른 API(공감·댓글)가 모두 "볼 수 없으면 404 → 로그인 401" 순서다. 같은 순서를 지켜야 API마다 응답 차이로 비공개 글의 존재를 알아내는 틈이 생기지 않는다.</details>

7. 마이페이지 목록의 "저장 취소"가 글을 확인하지 않는 이유와, 그래도 남의 저장을 지울 수 없는 이유는?
<details><summary>답</summary>볼 수 없게 된 글의 저장을 지우려는데 글 확인을 하면 404가 나와 지울 수 없다. DELETE 조건에 member_id = 로그인한 나가 있어 남의 저장 행은 걸리지 않는다.</details>

8. 회원이 탈퇴하면 그 회원의 저장은? 저장된 글의 주인이 탈퇴하면?
<details><summary>답</summary>저장한 회원이 탈퇴하면 그 회원의 저장 행을 지운다(T077). 글 주인이 탈퇴하면 글을 볼 수 없게 되므로 저장한 사람의 목록에 "볼 수 없는 글"과 스냅숏 제목으로 남는다.</details>

## 9. 더 읽을거리

- RFC 9110 "Idempotent Methods"(PUT·DELETE)
- MySQL 문서 "INSERT Statement"의 `IGNORE`
- Spring Data JPA 문서 "Modifying Queries"(`@Modifying`)
- Jackson `@JsonInclude(Include.NON_NULL)`
- Martin Fowler, "Snapshot"(Analysis Patterns, 시점 값 남기기)
