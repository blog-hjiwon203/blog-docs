# 50. 같은 규칙의 두 기능을 한 코드로: 댓글과 방명록

> 관련 스텝: [스텝 14](../step-14.md) (T066, T068) · 관련 개념: [29 댓글 설계](./29-comments-design.md), [24 계층 구조와 DTO](./24-layered-architecture-dto.md), [08 페이지 처리](./08-pagination.md), [06 JPA 엔티티 매핑](./06-jpa-entity-mapping.md), [16 인가와 가시성](./16-authorization-visibility.md), [25 React 폼과 데이터](./25-react-forms-data.md), [49 완료의 정의와 요구사항 추적](./49-requirement-traceability.md)

## 1. 이 문서로 배우는 것

- 명세가 "**댓글과 같은 규칙**"이라고 할 때, 그 "같음"을 코드에서 어떻게 지키나
- 고를 수 있는 방법 넷(복사, 상속, 한 테이블, 인터페이스 + 조립기)과 이 프로젝트가 인터페이스 + 조립기를 고른 이유
- 자바 인터페이스의 `default` 메서드, 엔티티가 인터페이스를 따르게 하기
- 페이지 번호 목록에서 "무엇을 한 개로 세나"(최상위 글 기준)와 답글을 붙이는 두 번째 쿼리
- Spring Data JPA `findBy(조건, q -> q.project(...).page(...))`: 연관을 함께 읽으며 페이지 받기, `PageImpl`로 내용만 바꿔 담기
- 관리 화면의 "받은 댓글"이 무엇을 빼는가, 낱개 목록과 묶음 목록
- React에서 한 줄짜리 부품을 세 화면이 같이 쓰도록 나누기, 그 자리에서 고치기(inline edit), 바뀐 뒤 다시 받기 vs 화면에서 고치기

## 2. 왜 필요한가

명세 CMT-04: "방명록: 블로그 단위 게시판형 글. **댓글과 같은 규칙(비밀·답글)을 따른다.**"
테이블 주석(ERD)도 같다: `guestbook` — "규칙은 댓글과 같다".

"같은 규칙"은 지금 이런 것들이다(스텝 6·7, [29](./29-comments-design.md)).

| 규칙 | 내용 |
| --- | --- |
| 비밀 | 블로그 주인과 작성자만 내용을 본다. 다른 사람에게는 내용·작성자 없이 "비밀글입니다" |
| 답글 | 한 단계. 답글의 답글은 400 |
| 지운 자리 | 답글이 남은 글을 지우면 "삭제된 …입니다" 자리로 남고, 답글까지 지우면 자리도 사라진다 |
| 권한 | 쓰기는 회원, 고치기는 본인, 지우기는 본인·블로그 주인 |
| 길이 | 1~1,000자, 앞뒤 공백 제거 |
| 연타 | `Idempotency-Key`로 한 번만 |
| 작성자 | 닉네임은 대표 블로그 링크, 프로필 사진 |

방명록을 만들 때 댓글 코드를 복사해서 고치면 처음에는 같다. 그런데 나중에 한쪽만 바뀐다. 예를 들어 스텝 13b에서 댓글 작성자 사진(T055d)을 더했는데, 그때 방명록이 복사본이었다면 방명록만 사진이 빠졌을 것이다. 이번 스텝에서 댓글 **고치기**(CMT-03)를 더하는데, 고칠 수 있는지(`canEdit`)도 두 곳에 따로 써야 했을 것이다. 명세의 "같은 규칙"을 코드가 **한 곳**에서 지키게 하는 것이 이 문서의 주제다.

또 관리 화면의 받은 댓글 목록(MNG-02)은 댓글과 방명록을 탭 하나씩으로 보여 준다. 여기도 "보는 사람이 주인일 때 이 댓글은 어떻게 보이나"를 같은 규칙으로 판단해야 한다. 같은 판단을 쓰는 곳이 셋이 된다.

## 3. 기본 개념

### 3.1 네 가지 방법

| 방법 | 어떻게 | 좋은 점 | 나쁜 점 |
| --- | --- | --- | --- |
| 복사 | `GuestbookService`에 댓글의 판단 코드를 그대로 붙인다 | 빠르다, 서로 영향 없음 | 규칙이 갈라진다(위 사진 예) |
| 상속 | `@MappedSuperclass` 부모 엔티티에 공통 칸(내용, 비밀, 지운 시각)을 두고 `Comment`·`Guestbook`이 물려받는다 | 칸 선언이 한 번 | 부모 관계(`parent`)의 타입이 다르다(`Comment` vs `Guestbook`). 제네릭 부모 엔티티는 JPA 매핑이 복잡해진다. 판단 코드는 여전히 어딘가에 따로 있어야 한다 |
| 한 테이블 | 댓글과 방명록을 한 테이블에 두고 `post_id`나 `blog_id` 중 하나만 채운다 | 코드가 하나 | ERD가 이미 두 테이블이다(스텝 1에서 정함, 마이그레이션은 고치지 않는다). 숨김(`is_blinded`)은 댓글에만 있다 |
| 인터페이스 + 조립기 | 두 엔티티가 같은 **모양**(인터페이스)을 드러내고, 판단은 그 모양만 보는 부품(조립기) 하나가 한다 | 테이블·엔티티는 그대로, 판단은 한 곳 | 인터페이스 메서드를 두 엔티티가 다 채워야 한다 |

이 프로젝트는 넷째를 골랐다. 테이블과 엔티티는 각자의 사정(글에 달림 vs 블로그에 달림, 숨김 칸이 있음 vs 없음)을 그대로 두고, **규칙이 보는 부분만** 공통으로 꺼냈다.

### 3.2 인터페이스는 "이렇게 생겼다"는 약속

자바 인터페이스는 메서드 이름과 모양만 정한다. 클래스가 `implements`로 그 약속을 따르면, 그 인터페이스 타입을 받는 코드는 어느 클래스인지 몰라도 된다.

```java
interface CommentEntry {
    boolean isSecret();
    boolean isDeleted();
    ...
}
class Comment implements CommentEntry { ... }     // 글의 댓글
class Guestbook implements CommentEntry { ... }   // 블로그의 방명록

void judge(CommentEntry entry) { if (entry.isSecret()) ... }   // 둘 다 받는다
```

**`default` 메서드**: 자바 8부터 인터페이스에 몸통이 있는 메서드를 둘 수 있다. 다른 메서드만으로 계산되는 것(예: "이 회원이 썼나" = `getMember().getId()`와 비교)은 인터페이스에 한 번 쓰면 두 클래스가 같이 쓴다.

Thymeleaf로 비유하면, `th:fragment`로 만든 조각이 받는 변수의 **이름**만 맞으면 어느 컨트롤러가 넘긴 객체든 그릴 수 있는 것과 비슷하다. 다만 자바는 컴파일러가 "그 이름의 메서드가 정말 있나"를 확인해 준다.

### 3.3 조립기(assembler)

"엔티티 → 화면에 나갈 모양"으로 바꾸는 일을 맡는 부품을 흔히 조립기라고 부른다. 이 프로젝트에서는 `CommentViews`가 그 일을 한다: 엔티티 목록과 보는 사람을 받아 `CommentView`(보는 사람 기준의 상태, 고칠 수 있나, 지울 수 있나, 작성자 링크·사진)를 만든다. 서비스(`CommentService`, `GuestbookService`, `ManageCommentService`)는 **무엇을 읽을지**만 정하고, **어떻게 보일지**는 조립기에 맡긴다.

### 3.4 페이지 번호 목록에서 "한 개"는 무엇인가

방명록은 "최신순 20개씩 페이지"다(spec US7 3번, research "방명록 페이지 20 최신순"). 그런데 답글이 있다. 20개를 셀 때 답글도 셀까?

- 답글도 세면: 한 글에 답글이 25개면 그 글 하나로 페이지가 넘치고, 부모와 답글이 페이지 사이로 갈라진다.
- **최상위 글만 세면**: 한 페이지 = 최상위 글 20개 + 각자의 답글 전부. 답글이 부모와 함께 있다.

댓글의 커서 목록(스텝 7)과 같은 생각이다. 그래서 두 번 읽는다: (1) 최상위 글 한 페이지, (2) 그 글들의 답글 `parent IN (...)`. 페이지 수(`totalPages`)도 최상위 글 기준이다. 지웠지만 답글이 남은 글은 "자리"로 보이므로 이것도 한 개로 센다.

### 3.5 "받은" 댓글

관리 화면(MNG-02)은 "받은 댓글·방명록 목록, 삭제, 답글 바로 쓰기"다. "받은"이므로 **블로그 주인 자신이 쓴 것은 뺀다**(주인이 단 답글을 주인이 관리 목록에서 다시 볼 필요가 없다). 주인이 답글을 달면 목록에는 안 생기고 "답글을 달았습니다"만 보인다. 답글은 글 상세나 방명록에서 보인다. 이 해석은 API 명세에 적었다.

또 관리 목록은 **낱개**다. 글 상세처럼 부모 안에 답글을 묶지 않고, 남이 쓴 답글도 한 줄로 나온다(`parentId`로 답글인지 안다). 주인은 "무엇이 새로 왔나"를 보려는 것이라 시간순 한 줄이 맞다.

## 4. 동작 원리

```
          ┌──────────── 무엇을 읽나 ────────────┐      ┌──── 어떻게 보이나 ────┐
GET /api/posts/{id}/comments → CommentService.list ─┐
GET /api/guestbook           → GuestbookService.list ┼─→ CommentViews.threads ─→ CommentView ─→ CommentResponse
GET /api/manage/comments     → ManageCommentService  ┘   CommentViews.flat
POST·PATCH (쓰기·고치기)      → 각 서비스               ─→ CommentViews.one

CommentViews.view(entry, 블로그, 보는 사람):
  지운 글?            → DELETED (내용·작성자 없음, 고치기·지우기 없음)
  숨긴 댓글?          → 작성자면 NORMAL + 사유, 아니면 BLINDED      (방명록은 늘 아님)
  비밀이고 주인·작성자가 아님? → SECRET
  그 밖               → NORMAL
  canEdit   = 작성자 && 숨기지 않음
  canDelete = 작성자 || 블로그 주인
  작성자 대표 블로그 주소·사진 = 목록 전체의 작성자를 모아 한 번씩 읽은 맵에서
```

엔티티가 `Comment`든 `Guestbook`이든 `view`는 `CommentEntry`의 메서드만 부른다.

## 5. 이 프로젝트에서는

### 5.1 공통 모양: `comment/domain/CommentEntry.java`

```java
public interface CommentEntry {

    Long getId();

    /** 답글이면 부모의 id, 최상위면 null. */
    Long getParentId();

    Member getMember();

    String getContent();

    boolean isSecret();

    /** 관리자가 숨겼나(ADMIN-03). 방명록에는 숨김이 없어 늘 false다. */
    boolean isBlinded();

    boolean isDeleted();

    LocalDateTime getCreatedAt();

    LocalDateTime getUpdatedAt();

    default boolean isWrittenBy(Long memberId) {
        return memberId != null && memberId.equals(getMember().getId());
    }

}
```

- 규칙이 **보는 것만** 넣었다. 댓글의 `getPost()`, 방명록의 `getBlog()`는 넣지 않았다. 규칙은 "어디에 달렸나"를 몰라도 된다.
- `getParentId()`: 부모 **엔티티**(`Comment getParent()`, `Guestbook getParent()`)는 타입이 달라 공통 메서드가 될 수 없다. id만 꺼내면 같다. `parent == null ? null : parent.getId()`라 지연 로딩된 부모의 id만 읽는다(Hibernate는 프록시의 id를 DB에 가지 않고 준다).
- `getCreatedAt()`·`getUpdatedAt()`: 두 엔티티 모두 `BaseTimeEntity`를 물려받아 이미 있다. 인터페이스에 적기만 하면 된다.
- `isWrittenBy`: 전에는 `Comment`에 있던 메서드다. `default`로 옮겨 방명록도 같이 쓴다.
- `isBlinded()`: 방명록 테이블에는 `is_blinded`가 없다(ERD). `Guestbook`은 늘 `false`를 돌려준다. 인터페이스는 둘 다 가진 것만이 아니라 **규칙이 묻는 것**을 담고, 없는 쪽은 "해당 없음" 값을 준다.

### 5.2 판단 한 곳: `comment/application/CommentViews.java`

```java
private CommentView view(CommentEntry entry, Blog blog, Long viewerId, Authors authors) {
    boolean author = entry.isWrittenBy(viewerId);
    boolean blogOwner = blog.isOwnedBy(viewerId);
    if (entry.isDeleted()) {
        // 답글이 남아 자리만 있는 부모. 누구에게나 내용·작성자 없이, 다시 지우거나 고칠 것도 없다
        return new CommentView(entry, CommentView.State.DELETED, null, null, false, false, null, List.of());
    }
    CommentView.State state;
    Map<String, String> blind = null;
    if (entry.isBlinded()) {
        state = author ? CommentView.State.NORMAL : CommentView.State.BLINDED;
        blind = author ? blindReason(entry) : null;
    } else if (entry.isSecret() && !author && !blogOwner) {
        state = CommentView.State.SECRET;
    } else {
        state = CommentView.State.NORMAL;
    }
    Member member = entry.getMember();
    return new CommentView(entry, state, authors.addresses().get(member.getId()),
            authors.photos().get(member.getProfileImageId()), author && !entry.isBlinded(), author || blogOwner,
            blind, List.of());
}
```

- 스텝 6·7에서 `CommentService` 안에 있던 판단을 그대로 옮겼다(지움 → 숨김 → 비밀 → 보통, [29](./29-comments-design.md) 5.4). 바뀐 것은 받는 타입(`Comment` → `CommentEntry`)과 새 칸 `canEdit`이다.
- `blog`: 방명록은 블로그에, 댓글은 그 블로그의 글에 달린다. "블로그 주인인가"는 둘 다 **그 블로그**로 판단한다. 비밀 규칙의 "글 주인"은 이 블로그에서는 블로그 주인과 같다(글은 블로그 주인만 쓴다).
- 숨긴 이유(`blindReason`)는 관리 이력에서 찾는다. 처음에는 서비스가 함수로 넘겼는데, 관리 화면 서비스(다른 패키지)도 같은 것을 넘겨야 해서 조립기 안으로 옮겼다. 방명록은 `isBlinded()`가 늘 `false`라 부를 일이 없다.

세 가지 진입점:

```java
/** 최상위 글과 그 답글들을 묶는다. 답글은 replies 안에 받은 순서대로 붙는다. */
public List<CommentView> threads(List<? extends CommentEntry> parents, List<? extends CommentEntry> replies,
                                 Blog blog, Long viewerId) {
    Authors authors = authors(Stream.concat(parents.stream(), replies.stream()).toList(), viewerId);
    Map<Long, List<CommentView>> repliesByParent = replies.stream().collect(Collectors.groupingBy(
            CommentEntry::getParentId, LinkedHashMap::new,
            Collectors.mapping(reply -> view(reply, blog, viewerId, authors), Collectors.toList())));
    return parents.stream()
            .map(parent -> view(parent, blog, viewerId, authors)
                    .withReplies(repliesByParent.getOrDefault(parent.getId(), List.of())))
            .toList();
}

/** 답글을 붙이지 않은 낱개 목록(관리 화면의 받은 댓글, 방금 쓰거나 고친 글). */
public List<CommentView> flat(List<? extends CommentEntry> entries, Blog blog, Long viewerId) { ... }

public CommentView one(CommentEntry entry, Blog blog, Long viewerId) {
    return flat(List.of(entry), blog, viewerId).getFirst();
}
```

- `List<? extends CommentEntry>`: **와일드카드**. `List<Comment>`는 `List<CommentEntry>`의 하위 타입이 아니다(자바 제네릭은 그렇게 동작한다). `? extends`로 "`CommentEntry`이거나 그 하위 타입의 목록"을 받으면 `List<Comment>`와 `List<Guestbook>`을 둘 다 넘길 수 있다. 읽기만 하므로 이것으로 충분하다.
- `groupingBy(..., LinkedHashMap::new, ...)`: 답글을 부모 id로 묶되, 받은 순서(작성순)를 지킨다.
- `authors(...)`: 목록 전체의 작성자를 모아 대표 블로그 주소와 사진을 **한 번씩** 읽는다(N+1 방지, 스텝 13b T055d).

### 5.3 방명록 엔티티: `comment/domain/Guestbook.java`

```java
@Entity
@Table(name = "guestbook")
public class Guestbook extends BaseTimeEntity implements CommentEntry {
    ...
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "parent_id")
    private Guestbook parent;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "blog_id", nullable = false)
    private Blog blog;
    ...
    public static Guestbook reply(Guestbook parent, Member member, String content, boolean secret) {
        return new Guestbook(parent.blog, member, parent, content, secret);
    }
    ...
    @Override
    public boolean isBlinded() {
        return false;
    }
```

- 칸은 `V1__init.sql`의 `guestbook`과 같다(`ddl-auto=validate`가 시작할 때 맞는지 본다). 스텝 1에 테이블이 이미 있었고, 이번에 엔티티를 처음 썼다.
- `reply`는 부모의 블로그를 그대로 쓴다. 답글이 다른 블로그로 갈 수 없다.
- 패키지는 `comment/`다(plan.md "comment/ # 댓글·답글·방명록"). 같은 규칙을 쓰는 것끼리 둔다.

### 5.4 방명록 목록: `GuestbookService.list`

```java
Specification<Guestbook> condition = (root, query, cb) -> {
    Subquery<Long> liveReply = query.subquery(Long.class);
    Root<Guestbook> reply = liveReply.from(Guestbook.class);
    liveReply.select(reply.get("id")).where(
            cb.equal(reply.get("parent"), root),
            cb.isNull(reply.get("deletedAt")));
    return cb.and(
            cb.equal(root.get("blog").get("id"), blog.getId()),
            cb.isNull(root.get("parent")),
            cb.or(cb.isNull(root.get("deletedAt")), cb.exists(liveReply)));
};
Page<Guestbook> parents = guestbookRepository.findBy(condition,
        query -> query.project("member").page(page.toPageable(NEWEST)));
List<Guestbook> replies = parents.isEmpty() ? List.of() : guestbookRepository.findBy(
        (root, query, cb) -> cb.and(
                root.get("parent").in(parents.getContent()),
                cb.isNull(root.get("deletedAt"))),
        query -> query.sortBy(WRITTEN_ORDER).project("member").all());
List<CommentView> views = commentViews.threads(parents.getContent(), replies, blog, viewerId);
return new PageImpl<>(views, parents.getPageable(), parents.getTotalElements());
```

- 조건은 댓글 목록과 같다: 이 블로그의, 최상위인, (지우지 않았거나 살아 있는 답글이 있는) 글. `cb.exists(서브쿼리)`가 "살아 있는 답글이 있나"다([29](./29-comments-design.md) 5.11).
- `findBy(조건, q -> ...)`: Spring Data JPA의 **fluent query**. 조건(Specification)으로 찾되, 받는 방법을 람다로 고른다.
  - `project("member")`: 작성자를 **함께 읽는다**. Spring Data JPA는 이 이름을 엔티티 그래프(fetch graph) 힌트로 넘겨, 작성자를 따로 읽는 쿼리가 글마다 나가지 않게 한다. 스텝 6부터 댓글 목록이 쓰던 방법이다.
  - `page(Pageable)`: 그 페이지의 내용과 **전체 개수 쿼리**(`count`)를 같이 돌려준다. 페이지 번호 목록에는 전체 수가 있어야 마지막 페이지를 안다.
  - `sortBy(...).all()`: 페이지 없이 전부.
- 정렬 `NEWEST` = `createdAt DESC, id DESC`. 같은 시각에 쓴 글이 있어도 순서가 늘 같게 id로 한 번 더 정한다([08](./08-pagination.md)).
- `PageImpl`: 받은 `Page<Guestbook>`의 페이지 정보(번호, 크기, 전체 수)는 그대로 두고 **내용만** `CommentView`로 바꾼 새 `Page`를 만든다. 컨트롤러는 `PageResponse.from(page, CommentResponse::from)`으로 `{ content, page, size, totalElements, totalPages }`를 내보낸다(블로그 글 목록과 같은 모양).
- `page.toPageable(...)`: 화면의 페이지는 1부터, Spring Data는 0부터라 `PageQuery`가 하나 뺀다. `page=0`이면 400이다(`PageQuery.of`).

### 5.5 받은 댓글: `manage/application/ManageCommentService`

```java
public Page<ReceivedComment> comments(Blog blog, PageQuery page) {
    Long ownerId = blog.getMember().getId();
    Specification<Comment> condition = (root, query, cb) -> cb.and(
            cb.equal(root.get("post").get("blog").get("id"), blog.getId()),
            cb.isNull(root.get("post").get("deletedAt")),
            cb.isNull(root.get("deletedAt")),
            cb.notEqual(root.get("member").get("id"), ownerId));
    Page<Comment> found = commentRepository.findBy(condition,
            query -> query.project("member", "post").page(page.toPageable(NEWEST)));
    List<CommentView> views = commentViews.flat(found.getContent(), blog, ownerId);
    List<ReceivedComment> rows = new ArrayList<>();
    for (int i = 0; i < views.size(); i++) {
        Comment comment = found.getContent().get(i);
        rows.add(new ReceivedComment(views.get(i), comment.getPost().getId(), comment.getPost().getTitle()));
    }
    return new PageImpl<>(rows, found.getPageable(), found.getTotalElements());
}
```

- `root.get("post").get("blog").get("id")`: 댓글 → 글 → 블로그로 조인해 "이 블로그 글의 댓글". 지운 글(`post.deletedAt`)의 댓글도 뺀다. 글을 지우면 댓글도 지우지만([29](./29-comments-design.md) 5.5), 조건으로 한 번 더 막아 둔다.
- `notEqual(member.id, ownerId)`: 3.5의 "받은". 
- `project("member", "post")`: 화면에 글 제목을 보여 주므로 글도 함께 읽는다.
- `flat(..., ownerId)`: 보는 사람은 주인이다. 그래서 비밀글은 내용이 보이고(`NORMAL`), `canDelete`는 늘 `true`, `canEdit`은 남의 글이라 `false`다. 화면은 이 값대로 버튼을 그린다.
- 같은 순서로 만든 두 목록(엔티티, 뷰)을 번호로 짝지어 글 id·제목을 붙인다. `flat`은 받은 순서를 그대로 지킨다(`stream().map(...).toList()`).
- 방명록 탭(`guestbook`)은 같은 모양이고 글이 없다(`ReceivedComment(view, null, null)`).
- 응답 `ReceivedCommentResponse`는 `Comment` 응답 칸 전부 + `post: { id, title } | null`이다(API 명세 `[{ ...Comment, post }]`). 자바 레코드에는 "다른 레코드의 칸을 펼쳐 넣기"가 없어 `CommentResponse`를 만든 뒤 칸을 하나씩 옮겼다.
- 지우기와 답글은 따로 API를 만들지 않았다. 관리 화면도 글 상세·방명록과 같은 `DELETE /api/comments/{id}`, `POST /api/posts/{id}/comments`를 부른다. 권한 판단(주인은 지울 수 있다)이 이미 그 API에 있다. 같은 일을 하는 API를 두 벌 두면 규칙이 또 갈라진다.

### 5.6 화면 부품 나누기: `CommentItem`, `CommentForm`

스텝 6의 `Comments.tsx`에는 댓글 한 줄(`CommentItem`)과 쓰기 칸(`CommentForm`)이 파일 안의 비공개 함수로 있었다. 방명록 화면과 관리 화면도 같은 한 줄을 그려야 해서 `components/`의 파일로 꺼냈다. Thymeleaf로 치면 한 템플릿 안의 조각을 `fragments/comment.html`로 옮겨 `th:replace`로 여러 화면이 부르게 한 것이다.

```tsx
// frontend/src/components/CommentItem.tsx
export type CommentKind = 'comment' | 'guestbook'

const HIDDEN_LABEL: Record<CommentKind, Record<'SECRET' | 'BLINDED' | 'DELETED', string>> = {
  comment: { SECRET: '비밀댓글입니다.', BLINDED: '관리자가 숨긴 댓글입니다.', DELETED: '삭제된 댓글입니다.' },
  guestbook: { SECRET: '비밀글입니다.', BLINDED: '관리자가 숨긴 글입니다.', DELETED: '삭제된 글입니다.' },
}

export default function CommentItem({ comment, kind = 'comment', onDelete, onReply, onEdit, isReply = false, extra }: {
  ...
  /** 고친 내용을 서버에 보내고 고친 댓글을 돌려준다. 실패하면 오류를 던진다 */
  onEdit?: (comment: Comment, content: string) => Promise<void>
  /** 작성자 줄에 덧붙일 것(관리 화면의 글 제목 등) */
  extra?: ReactNode
}) {
  const [editing, setEditing] = useState(false)
  const hidden = comment.state === 'NORMAL' ? null : HIDDEN_LABEL[kind][comment.state]
```

- **무엇을 부품이 알고, 무엇을 화면이 아나.** 부품은 "한 줄을 어떻게 그리나"만 안다. 어느 API를 부를지는 모른다. 그래서 지우기·답글·고치기는 함수(`onDelete`, `onReply`, `onEdit`)로 받는다. 글 상세는 `/api/comments/{id}`, 방명록은 `/api/guestbook/{id}`를 부르는 함수를 넘긴다.
- `kind`: 서버 응답 모양은 같고 **문구만** 다르다("비밀댓글입니다" vs "비밀글입니다"). `Record<키, 값>` 타입은 모든 키에 값이 있어야 컴파일된다. 새 상태가 생기면 빠뜨린 문구를 TypeScript가 알려 준다.
- `extra`: 관리 화면은 작성자 줄에 "어느 글에 달렸나" 링크를 덧붙인다. `ReactNode`(그릴 수 있는 무엇이든)를 받아 그 자리에 넣는다. 부품이 관리 화면을 알 필요가 없다.
- 버튼은 서버의 `viewer.canEdit`·`viewer.canDelete`를 따른다. 화면이 "작성자인가"를 다시 계산하지 않는다(권한은 서버, [16](./16-authorization-visibility.md)).

**그 자리에서 고치기(inline edit).** `editing`이 `true`면 내용 자리에 `<textarea>`와 저장·취소가 나온다.

```tsx
async function submit(event: FormEvent) {
  event.preventDefault()
  setSaving(true)
  setError(null)
  try {
    await onSave(comment, content.trim())
    onClose()
  } catch (caught) {
    setError(fieldMessages(caught).content ?? errorMessage(caught))
  } finally {
    setSaving(false)
  }
}
```

- 실패하면 칸을 닫지 않고 오류를 그 아래에 보인다(쓴 내용이 남는다). 성공하면 닫는다. 그래서 `onEdit`은 실패를 **던지는** 함수다(삼키면 부품이 실패를 모른다).
- 내용이 그대로면 저장 버튼이 꺼진다(`content.trim() === comment.content`). 고치지 않은 저장으로 "수정됨"이 붙지 않게.

**`CommentForm`의 비밀글 칸.** `allowSecret`이면 "비밀글" 체크 칸이 보이고 `secret`을 함께 보낸다. 방명록만 켠다. 댓글의 비밀댓글(CMT-06)은 백로그라 서버가 400을 주므로 댓글 칸에서는 끈다. 같은 부품이 두 규칙의 **차이**도 한 곳에서 드러낸다.

### 5.7 바뀐 뒤 화면을 어떻게 맞추나: 다시 받기 vs 화면에서 고치기

| 화면 | 바뀐 일 | 방법 | 이유 |
| --- | --- | --- | --- |
| 글 상세 댓글 | 쓰기·답글·지우기·고치기 | 화면에서 고침(`added`, `afterDelete`, `afterEdit`) | 커서 목록이라 다시 받으면 "더보기"로 불러온 것을 잃는다 |
| 방명록 | 쓰기·답글·지우기 | 지금 페이지를 **다시 받음**(`reload`) | 페이지 번호 목록이라 하나 생기거나 사라지면 페이지 경계가 밀린다(1페이지의 마지막이 2페이지로). 화면에서 맞추기 어렵다 |
| 방명록 | 고치기 | 화면에서 고침(`afterEdit`) | 개수가 그대로라 페이지가 밀리지 않는다 |
| 관리 | 지우기 | 다시 받음 | 방명록과 같은 이유 |
| 관리 | 답글 | 아무것도 안 바꾸고 "답글을 달았습니다" | 주인의 답글은 "받은" 목록에 나오지 않는다(3.5) |

방명록에서 새 최상위 글을 2페이지에서 쓰면 그 글은 1페이지 맨 위에 생긴다. 그래서 1페이지로 옮긴다(`navigate('?page=1')`).

`afterEdit`은 순수 함수라 Vitest로 확인했다(`commentList.test.ts`): 부모를 고쳐도 답글이 남는지, 답글을 고치면 그 부모 안에서만 바뀌는지.

### 5.8 입구

| 기능 | 입구 |
| --- | --- |
| 댓글 고치기 | 글 상세, 내 댓글의 "수정" |
| 방명록 | 블로그 머리글(모든 블로그 화면) "방명록" → `/guestbook` |
| 받은 댓글·방명록 | 관리 메뉴 "댓글·방명록" → `/manage/comments`, 탭 두 개 |

[49](./49-requirement-traceability.md)의 세 질문(API · 화면이 부르나 · 보이는 입구)을 스텝을 끝내기 전에 이 표로 확인했다.

### 5.9 테스트

| 테스트 | 확인하는 것 |
| --- | --- |
| `GuestbookIntegrationTest.memberWritesAndEveryoneSeesNewestFirstInPagesOf20` | 22개 → 1페이지 20개(새 글이 맨 위), 2페이지 2개, `totalPages` 2, `page=0`은 400 |
| `doubleClickMakesOneEntryAndAnonymousMustLogIn` | 같은 키 두 번 → 한 개, 비회원 401(틀린 입력이어도), 공백 400 |
| `secretEntryIsSeenOnlyByBlogOwnerAndAuthor` | 주인·작성자는 NORMAL과 내용, 다른 회원·비회원은 SECRET과 내용·작성자 없음 |
| `repliesAreOneLevelAndDeletedParentWithRepliesStaysAsPlaceholder` | 답글은 부모 안, 답글의 답글 400, 부모를 지우면 DELETED 자리, 답글까지 지우면 0개 |
| `onlyAuthorEditsAndAuthorOrOwnerDeletes` | 고치기는 작성자만(주인 403), 지우기는 작성자·주인(남 403), 지운 뒤 404 |
| `entryOfAnotherBlogIs404HereAndHiddenBlogHasNoGuestbook` | 다른 블로그의 글은 이 주소에서 404·답글 400, 이용 제한된 블로그의 방명록 404 |
| `ManageCommentIntegrationTest.ownerSeesReceivedCommentsOfOwnBlogOnlyNewestFirstWithPost` | 주인 답글·지운 댓글·지운 글의 댓글·남의 블로그 댓글이 빠짐, 비밀댓글 내용이 보임, `post.id`·`title` |
| `guestbookTabListsReceivedEntriesIncludingReplies` | 남이 단 답글도 한 줄(`parentId`), 주인 답글 빠짐, `post` 없음 |
| `onlyOwnerAndPermissionBeforeInputErrors` | 비회원 401 → 남 403 → 알 수 없는 type·page 400 |

댓글 쪽 기존 테스트(`CommentIntegrationTest`, `ReplyIntegrationTest`)는 판단을 `CommentViews`로 옮긴 뒤에도 그대로 통과했다. **옮기기 전과 뒤에 같은 테스트가 통과한다**는 것이 리팩터링이 동작을 바꾸지 않았다는 근거다.

## 6. 자주 하는 실수와 함정

- **"같은 규칙"을 복사로 구현한다**: 처음에는 같고, 다음 기능(사진, 고치기)에서 갈라진다.
- **공통 인터페이스에 한쪽만의 것을 넣는다**: `getPost()`를 넣으면 방명록이 의미 없는 값을 돌려줘야 한다. 규칙이 묻는 것만 넣는다.
- **`List<CommentEntry>`로 받는다**: `List<Comment>`를 넘길 수 없다. 읽기만 하면 `List<? extends CommentEntry>`.
- **답글까지 세어 페이지를 자른다**: 부모와 답글이 페이지 사이로 갈라진다. 최상위 글을 세고 답글은 따로 붙인다.
- **정렬에 id를 빼먹는다**: 같은 시각의 글이 페이지마다 다른 순서로 나와 겹치거나 빠진다.
- **연관을 함께 읽지 않는다**: 목록 20개에 작성자를 읽는 쿼리 20번(N+1). `project("member")`.
- **관리 화면용 지우기·답글 API를 따로 만든다**: 권한 판단이 두 벌이 된다. 이미 있는 API를 부른다.
- **페이지 목록에서 쓰기·지우기 뒤 화면만 고친다**: 페이지 경계가 밀려 다음 페이지와 겹친다. 다시 받는다.
- **부품이 API를 직접 부른다**: 세 화면이 서로 다른 API를 쓰는데 부품이 한쪽을 알면 다른 화면에서 쓸 수 없다. 할 일은 함수로 받는다.
- **고치기 실패를 부품 밖에서 삼킨다**: 칸이 닫히고 쓴 내용을 잃는다. 던져서 부품이 오류를 보이게 한다.

## 7. 직접 해 보기

### 7.1 화면

준비: `./scripts/build-frontend.sh && ./mvnw spring-boot:run`, 회원 둘(A: 블로그 주인, B: 방문자).

1. B로 A의 글에 댓글을 쓰고 "수정" → 고쳐서 저장. "수정됨"이 붙는다. A로 보면 B의 댓글에는 "삭제"만 있다.
2. B로 A의 블로그 머리글 "방명록" → "비밀글"을 켜고 하나, 끄고 하나 남긴다.
3. 로그아웃하고 방명록을 보면 비밀글은 "비밀글입니다."다. A로 보면 내용이 보이고 "비밀" 표시가 붙는다.
4. A로 관리 → "댓글·방명록" → 댓글 탭에서 B의 댓글 "답글" → 등록. "답글을 달았습니다". 글 상세에서 답글이 보인다.
5. 방명록 탭에서 B의 비밀글이 내용과 함께 보이는지 본다.

### 7.2 페이지 경계

방명록에 글을 21개 남기고(`for` 문으로 `curl`), 2페이지를 열어 둔 채 1페이지에서 하나를 지운다. 2페이지를 새로고침하면 1페이지의 마지막이었던 글이 내려와 있다. 5.7의 "다시 받는" 이유다.

### 7.3 리팩터링 확인

`CommentViews.view`의 비밀 조건에서 `!blogOwner`를 지우고 테스트를 돌려 본다.

```bash
./mvnw test -Dtest='GuestbookIntegrationTest,ManageCommentIntegrationTest,CommentIntegrationTest'
```

방명록의 `secretEntryIsSeenOnlyByBlogOwnerAndAuthor`와 관리 화면의 비밀댓글 확인이 **함께** 실패한다. 한 곳을 고치면 세 기능이 같이 바뀐다는 것을 눈으로 본다(끝나면 `git restore .`).

## 8. 확인 문제

1. 명세의 "방명록은 댓글과 같은 규칙"을 복사로 구현하면 어떤 문제가 생기나? 이 프로젝트에서 실제로 생길 뻔한 예는?
<details><summary>답</summary>나중에 한쪽만 바뀌어 규칙이 갈라진다. 스텝 13b의 작성자 프로필 사진, 스텝 14의 고치기 가능 여부(canEdit)를 댓글에만 더하고 방명록에는 빠뜨릴 수 있었다.</details>

2. 상속(`@MappedSuperclass`) 대신 인터페이스를 고른 이유는?
<details><summary>답</summary>두 엔티티의 부모 관계 타입(Comment vs Guestbook)과 달린 곳(글 vs 블로그)이 달라 공통 부모 엔티티로 묶으려면 제네릭 매핑이 필요하고 복잡해진다. 규칙이 보는 메서드만 인터페이스로 꺼내면 엔티티와 테이블은 그대로 두고 판단은 한 곳에서 할 수 있다.</details>

3. `CommentEntry`에 `getPost()`를 넣지 않은 이유는?
<details><summary>답</summary>규칙(비밀, 지운 자리, 권한)은 어디에 달렸는지 몰라도 판단할 수 있고, 방명록에는 글이 없어 의미 없는 값을 돌려줘야 한다. 인터페이스에는 규칙이 묻는 것만 둔다.</details>

4. 방명록에는 `is_blinded` 칸이 없는데 `isBlinded()`를 어떻게 했나?
<details><summary>답</summary>Guestbook이 늘 false를 돌려준다. 규칙은 "숨겼나"를 묻고, 숨김이 없는 쪽은 "아니다"가 맞는 답이다.</details>

5. `threads`가 `List<CommentEntry>`가 아니라 `List<? extends CommentEntry>`를 받는 이유는?
<details><summary>답</summary>자바 제네릭에서 List&lt;Comment&gt;는 List&lt;CommentEntry&gt;의 하위 타입이 아니라서 넘길 수 없다. ? extends는 CommentEntry나 그 하위 타입의 목록을 받는다. 읽기만 하므로 충분하다.</details>

6. 방명록 20개 페이지에서 답글을 세지 않는 이유와, 그 대신 쿼리를 어떻게 나눴나?
<details><summary>답</summary>답글까지 세면 부모와 답글이 페이지 사이로 갈라지고 답글 많은 글 하나로 페이지가 넘친다. 최상위 글 한 페이지를 읽고(전체 수 포함), 그 글들의 답글을 parent IN (...)으로 한 번 더 읽어 부모 안에 붙인다.</details>

7. `findBy(조건, q -> q.project("member").page(pageable))`에서 `project`와 `page`가 각각 하는 일은?
<details><summary>답</summary>project("member")는 작성자를 함께 읽게 해(엔티티 그래프) 글마다 작성자 쿼리가 나가지 않게 한다. page는 그 페이지의 내용과 전체 개수(count 쿼리)를 함께 Page로 돌려준다.</details>

8. 관리 화면 받은 댓글 목록에서 주인이 쓴 것을 빼는 이유와, 그래서 답글을 단 뒤 화면이 하는 일은?
<details><summary>답</summary>명세가 "받은" 댓글·방명록이라 주인 자신의 글은 관리할 대상이 아니다. 주인이 답글을 달아도 목록에 새 줄이 생기지 않으므로 "답글을 달았습니다"만 보이고, 답글은 글 상세·방명록에서 보인다.</details>

9. 관리 화면의 지우기·답글을 위해 새 API를 만들지 않은 이유는?
<details><summary>답</summary>글 상세·방명록의 지우기·쓰기 API에 이미 권한 판단(주인은 지울 수 있다, 회원은 쓸 수 있다)과 연타 방지가 있다. 같은 일을 하는 API를 하나 더 두면 판단이 두 벌이 되어 갈라질 수 있다.</details>

10. 방명록에서 지운 뒤에는 다시 받고, 고친 뒤에는 화면에서만 바꾸는 이유는?
<details><summary>답</summary>지우거나 새로 쓰면 개수가 바뀌어 페이지 경계가 밀린다(1페이지 마지막이 2페이지로). 화면에서 맞추기 어렵다. 고치기는 개수가 그대로라 같은 id의 내용만 바꾸면 된다.</details>

11. `CommentItem`이 API를 직접 부르지 않고 `onEdit`·`onDelete` 함수를 받는 이유는?
<details><summary>답</summary>글 상세는 /api/comments, 방명록은 /api/guestbook, 관리 화면은 탭에 따라 둘 중 하나를 부른다. 부품이 한 API를 알면 다른 화면에서 쓸 수 없다. 부품은 그리기만 알고, 할 일은 화면이 넘긴다.</details>

12. 리팩터링(판단을 `CommentViews`로 옮김)이 동작을 바꾸지 않았다는 근거는?
<details><summary>답</summary>옮기기 전부터 있던 댓글 테스트(CommentIntegrationTest, ReplyIntegrationTest 등)가 옮긴 뒤에도 고치지 않고 그대로 통과했다.</details>

## 9. 더 읽을거리

- Oracle Java Tutorials, "Interfaces"(default 메서드 포함), "Wildcards"(Upper Bounded Wildcards)
- Spring Data JPA 레퍼런스, "Specifications"와 fluent query(`findBy`), "Paging, Iterating Large Results, Sorting"
- Martin Fowler, *Refactoring* 2판, "Extract Function", "Combine Functions into Class"
- React 문서, "Passing Props to a Component", "Sharing State Between Components"
- contracts/rest-api.md "CMT 댓글 · 방명록", "관리" 표, data-model.md "guestbook"
