# 24. 계층 구조와 DTO: 엔티티를 화면까지 보내지 않는 이유

> 관련 스텝: [스텝 4](../step-04.md) (T018, T022, T023, T024, T025) · 관련 개념: [06-jpa-entity-mapping](./06-jpa-entity-mapping.md), [07-spring-mvc-exception-handling](./07-spring-mvc-exception-handling.md), [16-authorization-visibility](./16-authorization-visibility.md), [23-transactions-locking](./23-transactions-locking.md)

## 1. 이 문서로 배우는 것

- 계층형 구조(layered architecture)란 무엇이고, 이 프로젝트의 세 계층 `presentation` → `application` → `domain`이 각각 무엇을 맡는지
- "의존은 한 방향"이 무슨 뜻이고 왜 지키는지
- 엔티티를 API 응답으로 바로 내보내면 생기는 문제 네 가지
- DTO(Data Transfer Object)와 Java `record`
- `spring.jpa.open-in-view: false`의 뜻과 `LazyInitializationException`
- 트랜잭션이 끝나기 전에 필요한 값을 꺼내 두는 방법 세 가지
- 이 프로젝트의 "application 결과 → presentation 응답" 두 겹 패턴과 `from`/`of` 매핑
- 스텝 4에서 실제로 부딪힌 판단들: 컨트롤러가 리포지토리를 쓰던 초안, `open()`이 돌려준 엔티티, `updateInfo()`가 다시 읽는 이유, 목록에서 `post.getBlog()`를 읽지 않는 이유
- 응답 시각을 `+09:00`으로 맞추는 `DateTimes`, 주인에게만 보이는 필드를 `@JsonInclude(NON_NULL)`로 빼는 방법

**먼저 알면 좋은 것**: 엔티티와 지연 로딩(LAZY), 영속성 컨텍스트([06](./06-jpa-entity-mapping.md)), 컨트롤러와 서비스가 무엇인지 정도.

## 2. 왜 필요한가

스텝 4에서 처음으로 "화면이 부르는 API"가 여러 개 생겼다. 가입, 로그인, 내 정보, 블로그 개설, 블로그 정보, 글 목록, 사이드바. 이 API들은 모두 DB에서 엔티티(`Member`, `Blog`, `Post`, `Comment`, `Category`)를 읽어 JSON으로 돌려준다.

가장 쉬운 방법은 컨트롤러에서 엔티티를 그대로 `return`하는 것이다. Spring이 Jackson으로 JSON을 만들어 준다. 그런데 그렇게 하면:

- `Member`를 그대로 내보내면 **`passwordHash`가 응답에 실린다**. 보안 사고다.
- `Blog` → `member` → … 처럼 연관을 따라가다 서로를 가리키면 JSON이 **끝없이** 이어지거나 오류가 난다.
- `Blog.member`는 지연 로딩이라, 트랜잭션이 끝난 뒤 Jackson이 읽으려 하면 **예외**가 난다.
- 나중에 컬럼 이름을 바꾸면 **API 모양이 함께 바뀌어** 프론트가 깨진다.

또 코드가 늘어나면 "어디에 무엇을 두는가"가 흐려진다. 컨트롤러가 SQL을 직접 부르고, 서비스가 HTTP 상태 코드를 만들고, 엔티티가 JSON 모양을 알기 시작한다. 이걸 막으려고 2026-10-08에 지원이 **기능 패키지 안을 세 계층으로 나누기**로 정했다(CLAUDE.md, plan.md 구조 결정).

## 3. 기본 개념

### 3.1 계층형 구조

프로그램을 **역할별 층**으로 나누고, 위층이 아래층만 부르게 하는 구조다.

```
      ┌────────────────────────────┐
      │ presentation  (HTTP 담당)   │  Controller, 요청·응답 DTO
      └─────────────┬──────────────┘
                    │ 부른다
      ┌─────────────▼──────────────┐
      │ application   (일의 순서)   │  Service, 트랜잭션
      └─────────────┬──────────────┘
                    │ 부른다
      ┌─────────────▼──────────────┐
      │ domain        (규칙과 데이터)│  Entity, enum, Repository
      └────────────────────────────┘
```

| 계층 | 이 프로젝트 폴더 | 하는 일 | 모르는 것 |
| --- | --- | --- | --- |
| presentation | `blog/presentation/`, `…/presentation/dto/` | URL·메서드 매핑, 요청 본문 받기, 권한 검사 호출, 응답 JSON 모양 만들기 | 테이블, SQL |
| application | `blog/application/` | 한 번의 "일"(가입, 개설, 사이드바 만들기)을 순서대로. `@Transactional` 범위 | HTTP, JSON 모양, 쿠키 |
| domain | `blog/domain/` | 엔티티와 그 규칙(`Blog.changeInfo`, `BlogAddressRule`), 리포지토리 | 서비스, 컨트롤러 |

여러 기능이 같이 쓰는 것(설정, 오류 응답, 보안, 가시성)은 `global/`에 둔다.

### 3.2 의존은 한 방향

"A가 B에 의존한다" = A의 코드에 B가 `import`되어 있다는 뜻이다.

- 허용: `presentation → application → domain`
- 금지: `application → presentation`, `domain → application`

왜 한 방향인가? **아래층을 바꿔도 위층만 영향을 받게** 하려는 것이다. 응답 JSON 모양(presentation)을 바꿀 때 서비스(application)를 고칠 일이 없어야 한다. 반대로 서비스가 `BlogResponse`를 `import`하고 있다면, 응답 필드 하나를 바꿀 때 서비스까지 고쳐야 하고, 같은 서비스를 다른 화면(관리 API, 배치 작업)에서 쓰기도 어렵다.

### 3.3 엔티티를 응답으로 내보내면 생기는 문제

| 문제 | 예 | 결과 |
| --- | --- | --- |
| 내부 필드 노출 | `Member.passwordHash`, `Blog.totalVisitorCount`, `deletedAt` | 비밀번호 해시가 응답에 실림, 보여 주면 안 되는 상태가 드러남 |
| 순환 참조 | `Comment.parent` → `Comment` → …, 양방향 연관 | JSON이 끝없이 이어지거나 직렬화 오류 |
| 지연 로딩 | `Blog.member`가 LAZY 프록시 | 트랜잭션 밖에서 읽으면 `LazyInitializationException` |
| API가 테이블에 묶임 | 컬럼 `is_primary` → 필드 `primary` | DB를 고치면 API 모양이 바뀌어 프론트가 깨짐. 반대로 API 요구(`isOwner` 같은 "보는 사람 기준" 값)는 테이블에 없음 |

마지막 줄이 특히 중요하다. `GET /api/blog` 응답의 `viewer.isOwner`, `postCount`(보는 사람이 볼 수 있는 글 수), `owner.primaryBlogAddress`는 **어느 테이블의 컬럼도 아니다**. 계산해서 만드는 값이다. 엔티티로는 이런 응답을 표현할 수 없다.

### 3.4 DTO와 record

**DTO(Data Transfer Object)**: 계층 사이나 네트워크로 **데이터만 옮기는** 객체. 규칙(메서드 로직)이 없고 값만 담는다.

Java 16부터 있는 `record`가 DTO에 딱 맞다.

```java
public record BlogRef(Long id, String address, String name) {
}
```

이 한 줄로 Java가 만들어 주는 것:
- `private final` 필드 3개와, 셋을 모두 받는 생성자
- 읽는 메서드 `id()`, `address()`, `name()` (`getId()`가 아니라 이름 그대로)
- `equals`, `hashCode`, `toString`

값을 바꾸는 메서드(setter)가 없어서 **한 번 만들면 바뀌지 않는다(불변)**. Jackson은 record의 각 구성 요소를 JSON 필드로 쓴다. `BlogRef(1, "jiwon", "지원의 기록")` → `{"id":1,"address":"jiwon","name":"지원의 기록"}`.

### 3.5 open-in-view와 LazyInitializationException

JPA에서 연관을 `LAZY`로 두면, 엔티티를 읽을 때 연관 대상은 **프록시(가짜 객체)**로 채워 두고, 실제로 필드를 읽는 순간 SQL을 보낸다([06](./06-jpa-entity-mapping.md)). 이 "나중에 SQL 보내기"는 **영속성 컨텍스트(DB 연결)가 살아 있을 때만** 된다.

Spring Boot 기본값은 `open-in-view: true`다. 요청이 끝날 때까지 영속성 컨텍스트를 열어 두어서, 컨트롤러나 JSON 변환 중에도 지연 로딩이 된다. 편하지만:
- 요청 내내 DB 연결을 붙잡는다(느린 응답이 연결 풀을 말린다).
- 화면 그리는 중에 SQL이 몰래 나가서 N+1이 눈에 안 띈다.

이 프로젝트는 꺼 두었다.

`src/main/resources/application.yml`

```yaml
spring:
  jpa:
    open-in-view: false
```

그러면 **서비스의 `@Transactional` 메서드가 끝나는 순간** 영속성 컨텍스트가 닫힌다. 그 뒤 컨트롤러에서 아직 안 읽은 LAZY 연관을 건드리면:

```
org.hibernate.LazyInitializationException: could not initialize proxy [Member#3] - no Session
```

"필요한 것은 트랜잭션 안에서 다 읽어 와라"는 규칙이 코드로 강제되는 셈이다.

## 4. 동작 원리

### 4.1 요청 하나가 계층을 지나는 길 (`GET /api/blog`)

```
HTTP 요청 (Host: jiwon.blog.test)
   │
   ▼ presentation
BlogController.blog(@CurrentBlog Blog blog)
   │   @CurrentBlog: findByAddress (join fetch member) 로 블로그 + 주인을 함께 읽음
   │
   ▼ application  ── @Transactional(readOnly = true) 시작
BlogQueryService.detail(blog, viewerId)
   │   글 수 count, 구독자 수, 구독 여부, 대표 블로그 주소, 이용 제한 사유를 계산
   │   → BlogDetail(blog, ownerPrimaryBlogAddress, postCount, ...) record 로 묶음
   │                ── 트랜잭션 끝, 영속성 컨텍스트 닫힘
   ▼ presentation
BlogResponse.from(detail)
   │   blog.getName(), blog.getMember().getNickname() ... 를 읽어 응답 record 를 만듦
   │   (member 는 이미 join fetch 로 읽혀 있어서 SQL 없이 된다)
   ▼
Jackson → JSON
```

`BlogResponse.from`은 트랜잭션 **밖**에서 실행된다. 그래서 여기서 읽는 값은 모두 **이미 메모리에 있어야** 한다.

### 4.2 트랜잭션 안에서 필요한 값을 꺼내 두는 방법 세 가지

| 방법 | 어떻게 | 이 프로젝트에서 |
| --- | --- | --- |
| ① 미리 같이 읽기 | `join fetch`, `@EntityGraph`로 연관까지 한 SQL에 읽음 | `BlogRepository.findByAddress`(주인·이사 대상), `PostRepository.findAll(spec, pageable)`의 `@EntityGraph("category")` |
| ② 트랜잭션 안에서 값만 옮기기 | 서비스 안에서 엔티티를 읽어 필요한 값만 record로 옮김 | `SidebarService.toRecentComment`가 댓글 작성자 닉네임을 꺼내 `Sidebar.RecentComment`에 담음 |
| ③ 초기화가 필요 없는 값만 쓰기 | 프록시의 `getId()`는 SQL 없이 됨 | `comment.getPost().getId()`, `category.getParent().getId()` |

③은 Hibernate의 동작이다. 프록시는 만들 때 이미 외래 키 값(=대상의 id)을 알고 있어서, `getId()`만 부르면 DB에 가지 않는다. 다른 필드(`getName()` 등)를 부르면 그때 초기화(SQL)가 일어난다.

### 4.3 왜 두 겹인가: application 결과와 presentation 응답

서비스는 계산 결과를 돌려줘야 하는데, `BlogResponse`(presentation)를 만들어 돌려주면 의존 방향이 거꾸로 된다. 그래서:

```
application  : BlogDetail(blog, ownerPrimaryBlogAddress, postCount, subscriberCount, owner, subscribed, restriction)
                   ↑ 서비스가 만든다. HTTP·JSON 모양을 모른다.
presentation : BlogResponse.from(BlogDetail)  → { id, address, ..., owner: {...}, viewer: {isOwner, subscribed} }
                   ↑ 컨트롤러가 부른다. JSON 필드 이름, 중첩 모양, 숨길 값을 정한다.
```

서비스는 "무엇을 계산했는가"를, 응답 DTO는 "API 명세(contracts/rest-api.md)에 맞는 모양"을 책임진다. 같은 `BlogDetail`을 나중에 다른 응답(예: 관리자 화면)이 다르게 그릴 수도 있다.

## 5. 이 프로젝트에서는

### 5.1 패키지 모양

```
blog/
├── domain/        Blog, BlogRepository, BlogAddressRule, ListLayout, AccentColor
├── application/   BlogService, BlogQueryService, SidebarService, AddressCheck, BlogDetail, Sidebar
└── presentation/  BlogController, SidebarController
    └── dto/       BlogCreateRequest, BlogUpdateRequest, BlogResponse, SidebarResponse, AddressAvailabilityResponse
```

`auth/`, `member/`, `post/`, `category/`도 같은 모양이다. 짝을 표로 정리하면:

| application 결과 | presentation 응답 | API |
| --- | --- | --- |
| `MeResult` | `MeResponse` | `GET /api/me`, 가입, 로그인 |
| `BlogDetail` | `BlogResponse` (+ `MemberSummaryResponse`) | `GET/PATCH /api/blog`, `POST /api/blogs` |
| `AddressCheck` | `AddressAvailabilityResponse` | `GET /api/blogs/address-availability` |
| `Sidebar` (+ `CategoryTree`) | `SidebarResponse` (+ `CategoryTreeResponse`) | `GET /api/blog/sidebar` |
| `Page<Post>` (엔티티, 카테고리 미리 읽음) | `PostSummaryResponse` | `GET /api/posts` |

### 5.2 MeResult → MeResponse

`src/main/java/com/nhnacademy/blog/member/application/MeResult.java`

```java
public record MeResult(Member member, Blog primaryBlog) {
}
```

- 서비스가 돌려주는 "재료"다. 엔티티 두 개를 묶었을 뿐이다. `primaryBlog`는 대표 블로그가 없으면 `null`.

`src/main/java/com/nhnacademy/blog/member/presentation/dto/MeResponse.java`

```java
public record MeResponse(Long id, String email, String nickname, String profileImageUrl, String role,
                         boolean hasPassword, BlogRef primaryBlog, List<SocialAccount> socialAccounts,
                         long unreadNotificationCount) {

    public record BlogRef(Long id, String address, String name) {

        static BlogRef from(Blog blog) {
            return blog == null ? null : new BlogRef(blog.getId(), blog.getAddress(), blog.getName());
        }

    }

    public record SocialAccount(String provider, String linkedAt) {
    }

    public static MeResponse from(MeResult result) {
        Member member = result.member();
        return new MeResponse(member.getId(), member.getEmail(), member.getNickname(), null,
                member.getRole().name(), member.getPasswordHash() != null, BlogRef.from(result.primaryBlog()),
                List.of(), 0);
    }

}
```

줄별로:
- `hasPassword`: 응답에는 **해시 자체가 아니라** "비밀번호가 있는가"만 보낸다(`member.getPasswordHash() != null`). 엔티티를 그대로 내보냈다면 해시가 실렸을 것이다.
- `member.getRole().name()`: enum을 문자열 `"USER"`로. 열거값은 ERD의 영문 코드 그대로 준다(rest-api.md 요청·응답 형식).
- `BlogRef.from`: 블로그 엔티티에서 `id`, `address`, `name` 세 개만 뽑는다. `deletedAt`, `totalVisitorCount` 같은 것은 나가지 않는다.
- `profileImageUrl`은 `null`, `socialAccounts`는 빈 목록, `unreadNotificationCount`는 `0`: 이미지(스텝 7), 소셜 연동·알림(백로그)이 아직 없다. **응답 모양은 명세대로 미리 맞춰 두고** 값만 나중에 채운다. 프론트는 지금부터 이 모양으로 코드를 짤 수 있다.
- `from`이 `static`이고 이름이 `from`: "이것으로부터 만든다"는 뜻의 흔한 이름 짓기다. 인자가 둘 이상이면 `of`를 쓴다(아래 `MemberSummaryResponse.of`, `PostSummaryResponse.of`).

### 5.3 BlogDetail → BlogResponse

`src/main/java/com/nhnacademy/blog/blog/application/BlogDetail.java`

```java
public record BlogDetail(Blog blog, String ownerPrimaryBlogAddress, long postCount, long subscriberCount,
                         boolean owner, boolean subscribed, Restriction restriction) {

    public record Restriction(String reason, String reasonMessage) {
    }

}
```

`src/main/java/com/nhnacademy/blog/blog/presentation/dto/BlogResponse.java`

```java
public static BlogResponse from(BlogDetail detail) {
    Blog blog = detail.blog();
    Restriction restriction = detail.restriction() == null
            ? null
            : new Restriction(detail.restriction().reason(), detail.restriction().reasonMessage());
    return new BlogResponse(blog.getId(), blog.getAddress(), blog.getName(), blog.getDescription(), null,
            MemberSummaryResponse.of(blog.getMember(), detail.ownerPrimaryBlogAddress()), blog.getSkin(),
            blog.getListLayout().name(), blog.getAccentColor().name(), detail.postCount(),
            detail.subscriberCount(), new Viewer(detail.owner(), detail.subscribed()), restriction);
}
```

- `BlogDetail.Restriction`(application)과 `BlogResponse.Restriction`(presentation)이 **따로** 있다. 모양은 같지만, 응답 쪽을 바꿔도(필드 이름 변경 등) 서비스에 영향이 없게 하려는 것이다.
- `blog.getMember()`: 트랜잭션 밖이지만 안전하다. `blog`는 `@CurrentBlog`가 `findByAddress`(`join fetch b.member`)로 읽어 와서 주인이 이미 메모리에 있다(방법 ①).
- `new Viewer(detail.owner(), detail.subscribed())`: `{ "isOwner": ..., "subscribed": ... }`. **보는 사람에 따라 달라지는 값**이라 테이블 어디에도 없다.

`src/main/java/com/nhnacademy/blog/member/presentation/dto/MemberSummaryResponse.java`

```java
public record MemberSummaryResponse(Long id, String nickname, String profileImageUrl, String primaryBlogAddress) {

    public static MemberSummaryResponse of(Member member, String primaryBlogAddress) {
        return new MemberSummaryResponse(member.getId(), member.getNickname(), null, primaryBlogAddress);
    }

}
```

`MemberSummary`는 블로그 주인, 나중에는 댓글 작성자 등 여러 곳에서 쓰는 공통 모양이라 `member/presentation/dto`에 두었다.

### 5.4 Sidebar: 트랜잭션 안에서 값만 옮기기 (방법 ②)

`src/main/java/com/nhnacademy/blog/blog/application/Sidebar.java`

```java
public record Sidebar(Blog blog, CategoryTree categories, List<RecentPost> recentPosts,
                      List<RecentComment> recentComments) {

    public record RecentPost(Long id, String title) {
    }

    /** content·authorNickname은 state가 NORMAL일 때만 있다. */
    public record RecentComment(Long id, Long postId, String content, String authorNickname, CommentState state) {
    }
    ...
}
```

`src/main/java/com/nhnacademy/blog/blog/application/SidebarService.java`

```java
/** 댓글 작성자 닉네임처럼 지연 로딩되는 값은 이 트랜잭션 안에서 꺼내 기록(record)으로 넘긴다. */
@Transactional(readOnly = true)
public Sidebar sidebar(Blog blog, Long viewerId) {
    LocalDateTime now = LocalDateTime.now(clock);
    return new Sidebar(blog, categoryTreeService.tree(blog, viewerId), recentPosts(blog, viewerId, now),
            recentComments(blog, viewerId, now));
}
...
private static Sidebar.RecentComment toRecentComment(Comment comment) {
    Sidebar.CommentState state = comment.isBlinded() ? Sidebar.CommentState.BLINDED
            : comment.isSecret() ? Sidebar.CommentState.SECRET
            : Sidebar.CommentState.NORMAL;
    boolean shown = state == Sidebar.CommentState.NORMAL;
    return new Sidebar.RecentComment(comment.getId(), comment.getPost().getId(),
            shown ? comment.getContent() : null, shown ? comment.getMember().getNickname() : null, state);
}
```

- `comment.getMember()`는 LAZY 프록시다. `getNickname()`을 부르는 순간 SQL이 나간다. 이 줄이 **`@Transactional` 메서드 안**(`sidebar` → `recentComments` → `toRecentComment`)에서 실행되므로 된다. 같은 일을 컨트롤러의 `SidebarResponse.from`에서 했다면 `LazyInitializationException`이다.
- `comment.getPost().getId()`: 프록시의 id라 SQL이 없다(방법 ③).
- 비밀·숨긴 댓글이면 내용과 닉네임을 **애초에 record에 담지 않는다**(`null`). 응답 만드는 쪽에서 실수로 내보낼 수 없다.

presentation은 받은 record를 응답 모양으로만 바꾼다.

`src/main/java/com/nhnacademy/blog/blog/presentation/dto/SidebarResponse.java`

```java
public static SidebarResponse from(Sidebar sidebar) {
    Blog blog = sidebar.blog();
    return new SidebarResponse(List.of(
            new Module("PROFILE", new Profile(blog.getName(), blog.getDescription(), null)),
            new Module("CATEGORY", CategoryTreeResponse.from(sidebar.categories())),
            new Module("RECENT_POST", sidebar.recentPosts().stream()
                    .map(post -> new RecentPost(post.id(), post.title()))
                    .toList()),
            new Module("RECENT_COMMENT", sidebar.recentComments().stream()
                    .map(comment -> new RecentComment(comment.id(), comment.postId(), comment.content(),
                            comment.authorNickname(), comment.state().name()))
                    .toList())));
}
```

- 명세의 `{ modules: [{ type, data }] }` 모양(rest-api.md 사이드바 응답)을 만드는 일은 presentation의 몫이다. 서비스는 "모듈"이라는 화면 개념을 모른다.
- `Module(String type, Object data)`: `data`가 모듈마다 모양이 달라 `Object`다. Jackson은 실제 객체의 타입을 보고 JSON을 만든다.

### 5.5 isPrivate를 주인에게만: @JsonInclude(NON_NULL)

`src/main/java/com/nhnacademy/blog/category/presentation/dto/CategoryTreeResponse.java`

```java
public record CategoryTreeResponse(long totalCount, long uncategorizedCount, List<Node> categories) {

    @JsonInclude(JsonInclude.Include.NON_NULL)
    public record Node(Long id, String name, Boolean isPrivate, long postCount, int sortOrder, List<Node> children) {
    }

    public static CategoryTreeResponse from(CategoryTree tree) {
        return new CategoryTreeResponse(tree.totalCount(), tree.uncategorizedCount(),
                tree.categories().stream().map(node -> toNode(node, tree.ownerView())).toList());
    }

    private static Node toNode(CategoryTree.Node node, boolean ownerView) {
        return new Node(node.id(), node.name(), ownerView ? node.privateCategory() : null, node.postCount(),
                node.sortOrder(), node.children().stream().map(child -> toNode(child, ownerView)).toList());
    }

}
```

- 명세: "`isPrivate`는 주인에게만 준다"(rest-api.md CAT).
- `isPrivate`를 `boolean`이 아니라 **`Boolean`**(객체)으로 둔 이유: `null`을 담으려고. 기본형 `boolean`은 `null`이 될 수 없다.
- `@JsonInclude(NON_NULL)`: 값이 `null`인 필드는 JSON에서 **아예 뺀다**. 주인이 아니면 `"isPrivate": null`이 아니라 필드 자체가 없다.
- 이 애노테이션은 `Node`에만 붙였다. `SidebarResponse.RecentComment`의 `content: null`은 명세가 `null`로 주라고 했으므로 그대로 나가야 한다. 어디에 붙이는지가 중요하다.
- `import com.fasterxml.jackson.annotation.JsonInclude`: Spring Boot 4는 Jackson 3(`tools.jackson` 패키지)을 쓰지만, **애노테이션은 Jackson 2와 같은 `com.fasterxml.jackson.annotation` 패키지**에 남아 있다. `ErrorResponse`도 같은 import를 쓴다.

### 5.6 컨트롤러가 리포지토리를 직접 쓰던 초안 (계층 위반)

T022를 처음 짤 때 컨트롤러가 이렇게 생겼었다.

```java
// 초안 (지금은 없음)
Blog created = blogService.open(member.id(), request.address(), request.name(), request.description());
Blog blog = blogRepository.findByAddress(created.getAddress()).orElseThrow();   // presentation → domain 직접
return BlogResponse.from(blogQueryService.detail(blog, member.id()));
```

"응답에 주인 정보가 필요하니 주인까지 읽어 오자"는 의도였다. 동작은 하지만:
- presentation이 application을 건너뛰고 domain(리포지토리)을 불렀다.
- 이 `findByAddress`는 트랜잭션 밖에서 따로 실행되는 조회 한 번이 더 생긴다.

지금 코드(`BlogController.create`)는 리포지토리를 지우고 `open()`의 반환값을 그대로 쓴다.

```java
Blog blog = blogService.open(member.id(), request.address(), request.name(), request.description());
return BlogResponse.from(blogQueryService.detail(blog, member.id()));
```

### 5.7 open()이 돌려준 블로그의 member는 왜 밖에서 읽어도 되나

`src/main/java/com/nhnacademy/blog/blog/application/BlogService.java`

```java
/**
 * ...
 * 돌려주는 블로그의 주인(member)은 이 트랜잭션에서 읽은 엔티티라 트랜잭션 밖에서도 읽을 수 있다.
 */
@Transactional
public Blog open(Long memberId, String address, String name, String description) {
    Member member = memberRepository.findByIdForUpdate(memberId)
            .orElseThrow(() -> new BusinessException(ErrorCode.UNAUTHORIZED));
    ...
    return blogRepository.saveAndFlush(
            Blog.open(member, address, name.trim(), blankToNull(description), activeCount == 0));
```

- `findByIdForUpdate`(`SELECT ... FOR UPDATE`, [23](./23-transactions-locking.md))가 `Member`를 **실제로 읽은 엔티티**(프록시가 아님)다. 모든 필드가 이미 채워져 있다.
- 새 `Blog`를 만들 때 그 `member`를 직접 넣었으므로 `blog.getMember()`는 바로 그 실제 객체다.
- 트랜잭션이 끝나 영속성 컨텍스트가 닫혀도, **이미 메모리에 있는 값을 읽는 것**은 SQL이 필요 없어 된다. 예외가 나는 것은 "아직 안 읽은 프록시를 초기화하려 할 때"뿐이다.

### 5.8 updateInfo()는 왜 다시 읽나

```java
@Transactional
public Blog updateInfo(String address, String name, String description) {
    Blog blog = blogRepository.findByAddress(address)
            .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));
    blog.changeInfo(name == null ? null : name.trim(), description);
    return blog;
}
```

컨트롤러는 이미 `@CurrentBlog Blog blog`를 가지고 있다. 그걸 그대로 고치면 안 되나?

- 그 `blog`는 인자 해석기가 **트랜잭션 밖**에서 읽은 것이라 **준영속(detached)** 상태다. 영속성 컨텍스트가 관리하지 않으므로 `changeInfo`로 필드를 바꿔도 **변경 감지(dirty checking)가 일어나지 않아 UPDATE가 안 나간다**.
- 그래서 트랜잭션 안에서 다시 읽어(영속 상태) 고친다. 메서드가 끝날 때 Hibernate가 바뀐 필드를 보고 UPDATE를 보낸다.
- `findById`가 아니라 `findByAddress`를 쓰는 이유: 응답(`BlogResponse.from`)이 `blog.getMember().getNickname()`을 읽는다. `findById`로 읽으면 `member`는 LAZY 프록시라 트랜잭션 밖에서 예외가 난다. `findByAddress`는 `join fetch b.member`라 주인까지 읽혀 있다(방법 ①).

### 5.9 PostSummaryResponse.of는 왜 요청 블로그를 받나

`src/main/java/com/nhnacademy/blog/post/presentation/dto/PostSummaryResponse.java`

```java
/** blog는 목록을 부른 블로그다. post.getBlog()는 지연 로딩이라 읽지 않는다. */
public static PostSummaryResponse of(Post post, Blog blog) {
    Category category = post.getCategory();
    return new PostSummaryResponse(post.getId(), post.getTitle(), post.getSummary(), null,
            new BlogRef(blog.getId(), blog.getAddress(), blog.getName()),
            category == null ? null : new CategoryRef(category.getId(), category.getName()),
            post.getTopic() == null ? null : post.getTopic().name(),
            DateTimes.toOffset(post.getPublishedAt()), post.getLikeCount(), post.getCommentCount());
}
```

- 블로그 메인 목록의 글은 **모두 요청한 블로그의 글**이다(조건에 `inBlog`가 들어 있다). 그래서 글마다 `post.getBlog()`를 읽을 필요가 없다. 읽으면 트랜잭션 밖이라 예외, 트랜잭션 안이었다면 (1차 캐시가 없을 때) 쿼리가 더 나갈 수 있다.
- `post.getCategory().getName()`은 된다. `PostRepository`가 목록 조회에 `@EntityGraph(attributePaths = "category")`를 붙여 카테고리를 함께 읽기 때문이다([06](./06-jpa-entity-mapping.md)).

컨트롤러에서 이렇게 부른다.

`src/main/java/com/nhnacademy/blog/post/presentation/PostController.java`

```java
return PageResponse.from(
        postQueryService.blogPosts(blog, LoginMembers.currentId(), categoryId, pageQuery),
        post -> PostSummaryResponse.of(post, blog));
```

`PageResponse.from(page, mapper)`가 `Page<Post>`의 각 글을 `PostSummaryResponse`로 바꾼다. 람다 `post -> PostSummaryResponse.of(post, blog)`가 `blog`를 붙잡아 둔다.

### 5.10 응답 시각을 +09:00으로: DateTimes

`src/main/java/com/nhnacademy/blog/global/web/DateTimes.java`

```java
public final class DateTimes {

    public static final ZoneId KST = ZoneId.of("Asia/Seoul");

    private DateTimes() {
    }

    public static OffsetDateTime toOffset(LocalDateTime dateTime) {
        return dateTime == null ? null : dateTime.atZone(KST).toOffsetDateTime();
    }

}
```

- DB의 `DATETIME`은 시간대가 없어서 엔티티 필드는 `LocalDateTime`(`2026-10-08T09:00`)이다. 그대로 JSON으로 보내면 "어느 나라 9시인지" 알 수 없다.
- 명세는 한국 시간 ISO-8601 `2026-10-08T09:00:00+09:00`이다(rest-api.md 요청·응답 형식). `atZone(KST)`로 "이건 서울 시각이다"를 붙이고 `toOffsetDateTime()`으로 `+09:00`이 붙은 값으로 바꾼다.
- 응답 DTO의 필드 타입을 `OffsetDateTime`으로 두면 Jackson이 `+09:00`을 포함해 쓴다. 테스트 `latestFirstTenPerPageAndTieBrokenById`가 `"2026-10-01T20:00:00+09:00"`을 확인한다.
- 이 변환은 **응답 모양**의 일이라 엔티티가 아니라 응답 DTO에서 부른다.

## 6. 자주 하는 실수와 함정

1. **엔티티를 컨트롤러에서 그대로 return**: 비밀번호 해시 노출, 순환 참조, LAZY 예외. 항상 응답 DTO로 바꾼다.
2. **서비스가 응답 DTO를 만들어 돌려줌**: `application → presentation` 의존이 생긴다. 서비스는 application 결과(record)나 엔티티를 돌려준다.
3. **트랜잭션 밖에서 LAZY 연관 읽기**: `open-in-view: false`라 `LazyInitializationException`. 미리 읽거나(join fetch/EntityGraph), 트랜잭션 안에서 값만 옮긴다.
4. **"getId()도 위험하겠지"라고 모두 fetch**: 프록시의 id는 초기화 없이 읽힌다. 필요 없는 join fetch는 쿼리를 무겁게 만든다.
5. **준영속 엔티티를 고치고 저장됐다고 믿음**: 트랜잭션 밖에서 읽은 엔티티는 변경 감지가 안 된다. 트랜잭션 안에서 다시 읽어 고친다(`updateInfo`).
6. **`@JsonInclude(NON_NULL)`을 클래스 전체·전역에 붙임**: 명세상 `null`로 나가야 하는 필드(`content: null`, `primaryBlog: null`)까지 사라져 프론트가 `undefined`를 받는다. 필요한 record에만 붙인다.
7. **"숨길 값"을 응답 DTO에서 지우면 된다고 생각함**: 비밀댓글 내용은 서비스에서 애초에 record에 담지 않았다(`shown ? ... : null`). 담아 두면 다른 응답이 실수로 내보낼 수 있다.
8. **LocalDateTime을 그대로 응답**: 시간대 정보가 없어 프론트가 UTC로 해석하면 9시간이 어긋날 수 있다. `DateTimes.toOffset`.
9. **원시형 `boolean`으로 "없음"을 표현하려 함**: `boolean`은 `null`이 될 수 없다. 없을 수 있으면 `Boolean`.

## 7. 직접 해 보기

**실습 1. 엔티티를 그대로 내보내면?**

1. 공부용 브랜치를 만든다: `git switch -c study/entity-response`
2. `MeController.me`를 잠시 이렇게 바꾼다.
   ```java
   @GetMapping("/api/me")
   @PreAuthorize("isAuthenticated()")
   public Object me(@AuthenticationPrincipal LoginMember member) {
       return meService.me(member.id()).member();   // 엔티티 그대로
   }
   ```
3. `./mvnw test -Dtest=SignupIntegrationTest` 또는 서버를 띄워 로그인 후 `/api/me`를 열어 본다.
4. 기대 결과: 응답에 `passwordHash`가 보인다. 왜 DTO가 필요한지 눈으로 확인한다. `git restore .`로 되돌린다.

**실습 2. LazyInitializationException 만들어 보기**

1. `BlogService.updateInfo`의 `findByAddress`를 `findById`로 바꾸고(주소 대신 id를 넘기도록 잠시 수정) 
2. `./mvnw test -Dtest=BlogInfoIntegrationTest#ownerUpdatesNameAndDescription`
3. 기대 결과: 응답을 만들 때(`BlogResponse.from`이 `blog.getMember().getNickname()`을 읽을 때) `LazyInitializationException` → 500. 되돌린다.

**실습 3. 실행되는 SQL 보기**

`application-dev.yml`에 잠시 추가하고 서버를 띄운다.

```yaml
logging:
  level:
    org.hibernate.SQL: debug
```

블로그 메인 `GET /api/posts`를 부르면 글 목록 select 하나(카테고리 left join 포함)와 count 하나만 나오는지, 사이드바를 부르면 댓글 작성자 조회가 따로 나가는지 본다.

**실습 4. isPrivate가 사라지는 것 보기**

```bash
./mvnw test -Dtest=SidebarIntegrationTest#privateCategoryIsHiddenFromOthers
```

`CategoryTreeResponse.Node`의 `@JsonInclude`를 지우고 `categoriesInOrderWithVisiblePostCounts`를 돌리면 `isPrivate").doesNotExist()` 확인이 실패한다(`null`로 나오므로). 되돌린다.

## 8. 확인 문제

1. 이 프로젝트의 세 계층과 각자 모르는 것을 하나씩 말하라.
<details><summary>답</summary>presentation(Controller, DTO)은 테이블·SQL을 모르고, application(Service)은 HTTP·JSON 모양을 모르고, domain(Entity, Repository)은 서비스·컨트롤러를 모른다.</details>

2. 서비스가 `BlogResponse`를 돌려주면 안 되는 이유는?
<details><summary>답</summary>application이 presentation에 의존하게 되어 의존 방향이 거꾸로 된다. 응답 모양을 바꿀 때 서비스를 고쳐야 하고, 같은 서비스를 다른 응답에 쓰기 어려워진다.</details>

3. `open-in-view: false`에서 컨트롤러가 `blog.getMember().getNickname()`을 읽어도 되는 경우와 안 되는 경우는?
<details><summary>답</summary>blog를 join fetch로 주인까지 함께 읽었거나(findByAddress), 트랜잭션 안에서 실제 Member 엔티티를 넣어 만든 경우(open)는 된다. findById처럼 member가 아직 초기화되지 않은 프록시면 영속성 컨텍스트가 닫혀 LazyInitializationException이 난다.</details>

4. `comment.getPost().getId()`는 SQL을 보내지 않는 이유는?
<details><summary>답</summary>Hibernate 프록시는 만들 때 외래 키 값(대상의 id)을 이미 알고 있어서, getId()만으로는 초기화가 필요 없기 때문이다.</details>

5. `updateInfo`가 컨트롤러의 `@CurrentBlog` 블로그를 그대로 고치지 않고 다시 읽는 이유 두 가지는?
<details><summary>답</summary>① 그 블로그는 트랜잭션 밖에서 읽은 준영속 엔티티라 고쳐도 변경 감지가 안 되어 UPDATE가 나가지 않는다. ② 응답에 주인 닉네임이 필요해서 주인을 함께 읽는 findByAddress로 영속 상태로 읽는다.</details>

6. `CategoryTreeResponse.Node.isPrivate`가 `Boolean`이고 `@JsonInclude(NON_NULL)`이 붙은 이유는?
<details><summary>답</summary>주인이 아닌 사람에게는 isPrivate를 아예 주지 않아야 해서, null을 담을 수 있는 Boolean으로 두고 null인 필드를 JSON에서 빼도록 했다.</details>

7. 응답 시각을 `LocalDateTime` 그대로 보내지 않는 이유는?
<details><summary>답</summary>시간대 정보가 없어 어느 지역 시각인지 알 수 없다. 명세대로 한국 시간 +09:00을 붙이려고 DateTimes.toOffset으로 OffsetDateTime으로 바꾼다.</details>

8. 블로그 메인 목록에서 `PostSummaryResponse.of(post, blog)`가 `post.getBlog()`를 읽지 않는 이유는?
<details><summary>답</summary>목록의 글은 모두 요청한 블로그 소속이라 이미 가진 블로그를 쓰면 되고, post.getBlog()는 LAZY라 트랜잭션 밖에서 읽으면 예외가 나기 때문이다.</details>

## 9. 더 읽을거리

- Martin Fowler, "Patterns of Enterprise Application Architecture"의 Layering, Data Transfer Object
- Java 언어 명세 / JEP 395 "Records"
- Spring Boot 레퍼런스, `spring.jpa.open-in-view` 속성 설명
- Hibernate ORM 사용자 가이드, "Fetching", 프록시와 `LazyInitializationException`
- Jackson 애노테이션 `@JsonInclude` 문서
- `java.time` 패키지: `LocalDateTime`, `ZonedDateTime`, `OffsetDateTime` 차이
- plan.md 구조 결정(2026-10-08 계층 나누기), contracts/rest-api.md 주요 응답 객체
