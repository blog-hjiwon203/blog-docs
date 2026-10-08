# 16. 인가와 가시성 판단: 누가 무엇을 볼 수 있나

> 관련 스텝: [스텝 3](../step-03.md) (T011, T050), [스텝 4](../step-04.md) (블로그 화면 목록·글 수·사이드바, 블로그 수정) · 관련 개념: [22-bean-validation](./22-bean-validation.md), [12-spring-security-filter-chain](./12-spring-security-filter-chain.md), [15-subdomain-host-routing](./15-subdomain-host-routing.md), [06-jpa-entity-mapping](./06-jpa-entity-mapping.md), [08-pagination](./08-pagination.md), [18-spa-server-routing](./18-spa-server-routing.md)

## 1. 이 문서로 배우는 것

- 인증(Authentication)과 인가(Authorization)의 차이
- "볼 수 없는 것은 404"로 존재를 숨기는 이유와 403과의 차이
- 여러 조건에 걸린 요청에 어떤 상태 코드를 줄지 정하는 순서(404 → 401 → 403)
- 권한 판단을 정책 객체(Policy) 한 곳에 모으는 이유
- 이 프로젝트의 글 가시성 표(질문 ①~④, 결과 6개)를 `PostVisibilityPolicy` 코드로 따라가기
- Java 21의 sealed interface, record, 패턴 매칭 switch가 판단 결과를 안전하게 만드는 방법
- 글 하나를 볼 때(상세)와 목록을 볼 때 같은 규칙을 지키게 하는 방법(`PostSpecifications`)
- 블로그 가시성(이용 제한, 주인 정지), 주인 검사(`BlogOwnerGuard`), 구독자 공개 글의 예외
- 시간에 따라 바뀌는 판단을 테스트하려고 `Clock`을 주입하는 이유
- (스텝 4) 블로그 화면 목록 조건 `listedIn`, 글 수·카테고리 글 수·사이드바가 한 조건을 쓰게 하는 법, 403이 400보다 먼저 나가게 하는 법

**먼저 알면 좋은 것**: HTTP 상태 코드 401/403/404, JPA 엔티티 연관관계, Spring 빈 주입.

## 2. 왜 필요한가

블로그 글 하나에도 "보여 줘도 되나"를 정하는 조건이 많다.

- 비공개 글, 임시저장 글, 예약 발행 전 글
- 관리자가 숨긴 글
- 이용 제한된 블로그의 글, 주인이 정지된 블로그의 글
- 삭제된 글, 삭제된 블로그의 글
- 구독자만 볼 수 있는 글
- 주인은 위 대부분을 볼 수 있어야 함(관리해야 하니까)

이 조건을 컨트롤러마다 따로 쓰면 반드시 어딘가에서 하나를 빠뜨린다. 예를 들어 글 상세 API는 숨긴 글을 막았는데, 검색 API는 막지 않으면 검색 결과로 숨긴 글의 제목이 보인다. 홈 최신 글, 카테고리 목록, 태그 목록, 사이드바 최근 글, 인기 글, 검색… 글이 나오는 곳은 열 군데가 넘는다.

헌법 원칙 II는 "볼 수 없는 글은 어디에서도 보이지 않는다"를 요구한다. 그래서 규칙을 **한 곳**에 모으고, 모든 조회가 그것을 거치게 한다. 이 문서의 주제다.

## 3. 기본 개념

### 3.1 인증과 인가

| | 인증(Authentication) | 인가(Authorization) |
| --- | --- | --- |
| 묻는 것 | **너 누구야?** | **너 이거 해도 돼?** |
| 실패하면 | 401 Unauthorized(이름과 달리 "인증 안 됨") | 403 Forbidden |
| 이 프로젝트에서 | 쿠키의 JWT로 회원 확인([11-jwt](./11-jwt.md), [12](./12-spring-security-filter-chain.md)) | 관리자 영역, 블로그 주인 검사, 글 가시성 |

인가는 다시 두 층으로 나뉜다.

- **URL·역할 단위**: "`/api/admin/**`는 ADMIN만". Spring Security 설정 한 줄로 끝난다(`SecurityConfig`).
- **데이터 단위**: "이 블로그의 주인만", "이 글을 볼 수 있는 사람만". 데이터를 봐야 판단할 수 있어서 서비스 코드에서 한다. 이 문서가 다루는 것은 주로 이쪽이다.

### 3.2 존재를 숨기는 404

비공개 글 `/15`를 남이 열면 무엇을 줘야 할까?

| 응답 | 사용자가 알게 되는 것 |
| --- | --- |
| 403 "권한이 없습니다" | "15번 글이 **있긴 하다**. 나만 못 볼 뿐." |
| 404 "찾을 수 없습니다" | 없는 글인지 못 보는 글인지 모른다 |

403은 존재 자체를 알려 준다. 글 번호를 1부터 차례로 찔러 보면 "비공개 글이 몇 개 있는지", "어느 블로그가 몰래 글을 쓰고 있는지"를 알아낼 수 있다(정보 노출). 그래서 이 프로젝트는 **볼 수 없는 글과 블로그는 로그인 여부와 상관없이 404**를 준다(헌법 II, CLAUDE.md 기술 규칙). GitHub도 남의 비공개 저장소 주소에 404를 준다.

반대로 403을 쓰는 곳도 있다. "있는 것은 알지만 이 행동은 못 한다"가 자연스러울 때다.
- 남의 블로그 **관리**(블로그 자체는 공개라 있다는 걸 이미 앎) → 403 `FORBIDDEN`
- 정지된 회원 → 403 `MEMBER_SUSPENDED`
- 구독자 공개 글(아래 3.5) → 403 `SUBSCRIBERS_ONLY`

### 3.3 상태 코드 판단 순서

한 요청이 여러 조건에 걸릴 수 있다. 비회원이 남의 비공개 글을 수정하려 하면 "로그인 안 함(401)"이기도 하고 "볼 수 없는 글(404)"이기도 하다. rest-api.md "상태 코드 순서"는 위에서부터 먼저 걸린 것을 주라고 정했다.

```
1. 404  대상이 없거나 볼 수 없음      ← 가장 먼저. 존재를 숨기려면 이게 먼저여야 한다
2. 401  로그인이 필요한데 안 함
3. 403  로그인했지만 권한 없음, 정지, 차단, 구독자 공개
4. 400 입력 오류 / 409 중복·상태 충돌
```

왜 404가 401보다 먼저인가? 401을 먼저 주면, 비회원이 `/api/posts/15`를 부를 때 "로그인하세요(401)"와 "없음(404)"이 갈려서 "15번은 있구나"를 알 수 있다. 404를 먼저 판단하면 비회원에게도 정보가 새지 않는다.

입력 검증(400)이 마지막인 이유도 같다. 남의 글에 이상한 값을 보냈을 때 400이 먼저 나가면 "그 글이 있고, 내 입력만 틀렸구나"를 알게 된다.

그런데 Spring MVC에서 요청 본문에 `@Valid`를 붙이면 **컨트롤러 메서드에 들어가기 전**(인자를 만들 때) 검증이 끝난다. 주인 검사는 메서드 안에서 하므로, 남의 블로그에 틀린 값을 보내면 403보다 400이 먼저 나가 버린다. 스텝 4의 블로그 수정은 그래서 `@Valid`를 쓰지 않고 주인 검사 **뒤에** 직접 검증한다(5.7 ④, [입력 검증](./22-bean-validation.md)).

### 3.4 정책 객체(Policy)

**정책 객체**는 "이 사람이 이것을 할 수 있나"를 판단하는 규칙만 담은 클래스다. 다른 일(DB 저장, 응답 만들기)은 하지 않는다.

```java
// 나쁜 예: 판단이 여기저기 흩어짐
if (post.getVisibility() == PRIVATE && !post.getBlog().getMember().getId().equals(viewerId)) { ... }  // 상세 API
if (post.getVisibility() != PRIVATE) { ... }                                                       // 검색 API (숨김 검사 빠짐!)

// 좋은 예: 한 곳에 묻는다
PostAccess access = postVisibilityPolicy.decide(postId, requestBlog, viewerId);
```

장점:
- 규칙이 바뀌면(예: "정지 회원의 블로그도 숨긴다" 추가) 한 곳만 고친다.
- 규칙만 따로 테스트할 수 있다(`PostVisibilityIntegrationTest`).
- 컨트롤러는 "판단 결과에 따라 무엇을 응답할지"만 신경 쓴다.

### 3.5 이 프로젝트의 글 가시성 표

data-model.md "글 가시성 판단"의 표다. 위에서부터 차례로 묻는다.

| 질문 | 아니오 | 예 |
| --- | --- | --- |
| ① 글이 있나 (글·블로그 삭제 안 됨) | **404** | ②로 |
| ② 요청한 블로그 소속인가 | ③④로 볼 수 있으면 **301**(지금 소속 블로그로), 아니면 404 | ③으로 |
| ③ 보는 사람이 블로그 주인인가 | ④로 | **보임**(숨긴 글이면 사유와 함께) |
| ④ 다른 사람이 볼 수 있나 | **404**. 단, 구독만 안 한 구독자 공개 글이면 **구독 안내** | **보임** |

④의 "볼 수 있다" 조건은 모두 만족해야 한다.
- 발행됨(`status = PUBLISHED`)
- 숨김 아님(`is_blinded = 0`)
- 블로그 이용 제한 아님(`blog.is_restricted = 0`)
- 블로그 주인이 정지 중이 아님
- 공개(`PUBLIC`)이거나, 구독자 공개(`SUBSCRIBERS`)이면서 구독 중

결과는 여섯 가지다: 404(없음), 301(다른 블로그 소속), 주인에게 보임, 주인에게 숨김 사유와 함께 보임, 다른 사람에게 보임, 구독 안내(404의 예외, Q4).

**② 질문이 왜 있나**: 글 주소는 `{블로그}.blog.com/{글번호}`이고 글 번호는 전체에서 하나다. 그래서 `beta.blog.com/15`처럼 다른 블로그 주소에 A의 글 번호를 붙일 수 있다. 이때 볼 수 있는 글이면 원래 주소(`alpha.blog.com/15`)로 보내 주고, 볼 수 없으면 404로 존재를 숨긴다. 블로그 이사로 글이 옮겨 간 경우에도 옛 주소가 새 주소로 이어진다.

**구독자 공개 글의 예외(Q4)**: 구독자 공개 글을 구독하지 않은 사람이 열면 404 대신 "구독하면 볼 수 있어요" 안내를 준다. 제목과 본문은 주지 않고 블로그 정보만 준다(403 `SUBSCRIBERS_ONLY`, detail `{ blogId, blogName, blogAddress }`). 블로그가 구독을 늘리려는 기능이라 존재를 숨기는 것보다 알려 주는 쪽을 지원이 골랐다. 목록에서는 이런 글을 그냥 뺀다.

## 4. 동작 원리

### 4.1 sealed interface + record + switch로 결과 표현하기

판단 결과를 `int`나 `String`, `enum`으로 돌려줄 수도 있다. 그런데 결과마다 **들고 있어야 할 정보가 다르다**.

| 결과 | 함께 필요한 정보 |
| --- | --- |
| 404 | 없음 |
| 301 | 어느 블로그로 보낼지 |
| 주인에게 보임 | 글, 숨김 여부 |
| 보임 | 글 |
| 구독 안내 | 블로그(이름·주소를 보여 줘야 함) |

Java 21에서는 이것을 **sealed interface + record**로 표현한다.

```java
public sealed interface PostAccess {
    record NotFound() implements PostAccess { }
    record MovedTo(Blog blog) implements PostAccess { }
    record Owner(Post post, boolean blinded) implements PostAccess { }
    record Visible(Post post) implements PostAccess { }
    record SubscribersOnly(Blog blog) implements PostAccess { }
}
```

- `sealed`: 구현체를 이 다섯으로 **닫는다**. 다른 파일에서 `PostAccess`를 새로 구현할 수 없다.
- 각 결과는 자기에게 필요한 값만 가진다. `NotFound`에서 실수로 글을 꺼낼 수 없다.

쓰는 쪽은 **패턴 매칭 switch**로 받는다.

```java
return switch (access) {
    case PostAccess.MovedTo movedTo -> redirect(request, movedTo.blog());
    case PostAccess.NotFound notFound -> app(HttpStatus.NOT_FOUND);
    case PostAccess.Owner owner -> app(HttpStatus.OK);
    case PostAccess.Visible visible -> app(HttpStatus.OK);
    case PostAccess.SubscribersOnly subscribersOnly -> app(HttpStatus.OK);
};
```

- `case PostAccess.MovedTo movedTo`: "MovedTo이면 그 객체를 `movedTo` 변수로". 형변환이 필요 없다.
- **`default`가 없다.** sealed라서 컴파일러가 다섯 경우를 다 다뤘는지 안다. 나중에 결과를 하나 더 만들면(예: `record Blocked(...)`), 이 switch를 처리하지 않은 **모든 곳이 컴파일 오류**가 난다. 판단 결과를 빠뜨린 채 배포될 수 없다. `default`를 쓰면 이 장점이 사라지니 일부러 쓰지 않는다.

`enum`으로 했다면 결과에 데이터를 붙이기 어렵고, `if-else` 사슬로 했다면 하나를 빠뜨려도 컴파일러가 모른다.

### 4.2 상세 판단과 목록 조건

글 **하나**는 자바 코드로 판단하면 된다. 그런데 **목록**은 다르다.

```
// 나쁜 방법: 다 읽고 자바에서 거르기
List<Post> all = postRepository.findAll(PageRequest.of(0, 10));
List<Post> visible = all.stream().filter(p -> policy.decide(p, ...).canRead()).toList();
```

- 10개를 읽었는데 걸러서 3개만 남으면 한 페이지에 3개만 보인다.
- 전체 개수(`totalElements`)가 볼 수 없는 글까지 센다. "글 57개"인데 실제로 볼 수 있는 건 40개.
- 볼 수 없는 글까지 DB에서 다 읽어 와서 느리다.

그래서 목록은 같은 ④ 조건을 **SQL의 WHERE 절**로 바꿔서 DB가 거르게 한다. 이것이 `PostSpecifications.visibleTo`다. 대신 **같은 규칙이 두 군데(자바 판단, 쿼리 조건)에 있게 된다.** 한쪽만 고치면 상세에서는 안 보이는 글이 목록에는 보이는 사고가 난다. 이 위험은 테스트로 막는다(5.4).

### 4.3 Specification

Spring Data JPA의 `Specification<T>`는 "WHERE 조건 조각"을 자바 객체로 만든 것이다. 조각을 `and`/`or`로 조합할 수 있다.

```java
postRepository.findAll(
    PostSpecifications.inBlog(blogId)                    // WHERE post.blog_id = ?
        .and(PostSpecifications.visibleTo(viewerId, now)), // AND (가시성 조건)
    pageable);
```

내부에서는 JPA **Criteria API**로 조건을 만든다. `root`는 조회 대상(Post), `cb`(CriteriaBuilder)는 조건을 만드는 도구, `query`는 서브쿼리 등을 만들 때 쓴다. Repository가 `JpaSpecificationExecutor<Post>`를 상속하면 `findAll(spec, pageable)`을 쓸 수 있다.

### 4.4 (스텝 4) 블로그 화면의 목록은 무엇을 보여 주나

스텝 3에는 목록 조건이 두 개였다: 남이 보는 `visibleTo`, 주인이 보는 `ownerView`(삭제 안 된 **모든** 글). 블로그 메인 목록을 만들면서 `ownerView`를 그대로 쓰면 주인의 블로그 메인에 **임시저장 글**이 섞인다. 임시저장 글은 발행 시각(`published_at`)이 없어 최신순 정렬에서도 자리가 없다. 블로그 메인은 "발행된 글을 보여 주는 곳"이고, 임시저장·예약 글은 관리 화면의 글 관리(MNG-01)에서 본다.

그래서 블로그 화면용 조건 `listedIn`을 따로 두었다.

| 보는 사람 | 블로그 화면(메인, 카테고리, 사이드바, 글 수)에 나오는 글 |
| --- | --- |
| 블로그 주인 | 삭제 안 된 **발행** 글 전부. 비공개·구독자 공개·숨긴 글 포함. 임시저장·예약 글은 빠짐 |
| 그 밖의 사람 | `visibleTo`와 같음(남이 볼 수 있는 글만) |

data-model.md는 "주인이 자기 블로그를 볼 때만 ④를 건너뛴다"고만 적었다. ④에는 "발행됨"도 들어 있어서, 글자 그대로면 임시저장 글도 나와야 한다. `listedIn`은 이것을 블로그 화면에 맞게 **"발행됨"은 남기고 나머지 ④(숨김·공개 범위·이용 제한·정지)만 건너뛰는 것**으로 좁혀 해석했다. 이 해석은 지원 확인을 받아 data-model.md에 적어야 하는 항목이다(스텝 4 보고에서 질문).

### 5.1 PostVisibilityPolicy: 표를 코드로

`src/main/java/com/nhnacademy/blog/global/visibility/PostVisibilityPolicy.java`

```java
public PostAccess decide(Long postId, Blog requestBlog, Long viewerId) {
    return postRepository.findWithBlogById(postId)               // (a)
            .map(post -> decide(post, requestBlog, viewerId))
            .orElseGet(PostAccess.NotFound::new);                // (b)
}
```

- (a) 글과 블로그, 블로그 주인을 **한 번의 쿼리로** 읽는다(`join fetch`). 판단 중에 `post.getBlog().getMember()`를 쓰는데, 이 프로젝트는 `open-in-view: false`라 트랜잭션 밖에서 지연 로딩하면 예외가 난다([06](./06-jpa-entity-mapping.md)). 그래서 필요한 것을 미리 다 읽어 온다.
- (b) 글 번호가 없으면 404. `NotFound::new`는 "`new NotFound()`를 하는 함수"를 넘기는 메서드 참조다.

```java
public PostAccess decide(Post post, Blog requestBlog, Long viewerId) {
    Blog blog = post.getBlog();
    // ① 있나
    if (post.isDeleted() || blog.isDeleted()) {
        return new PostAccess.NotFound();
    }
    PostAccess access = decideInOwnBlog(post, viewerId);
    // ② 요청한 블로그 소속인가
    if (requestBlog != null && !requestBlog.getId().equals(blog.getId())) {
        return access.canRead() ? new PostAccess.MovedTo(blog) : new PostAccess.NotFound();
    }
    return access;
}
```

- **①**: 글이 삭제됐거나(소프트 삭제, `deleted_at`이 있음) 블로그가 삭제됐으면 주인이라도 404.
- 표에서는 ②가 ③④보다 위지만, ②의 "아니오" 쪽이 "③④로 볼 수 있으면 301"이라 ③④ 결과가 먼저 필요하다. 그래서 `decideInOwnBlog`(③④)를 먼저 계산해 두고 ②에서 쓴다.
- **②**: `requestBlog`는 요청 Host의 블로그다. 어느 주소에서 불러도 같은 API(rest-api.md의 `*` 범위)는 null을 넘겨 ②를 건너뛴다. 소속이 다르면, 볼 수 있을 때만 301 대상 블로그를 알려 준다. 볼 수 없으면 404라서 "다른 블로그에 그 번호의 글이 있다"는 사실도 숨겨진다.
- `access.canRead()`는 `PostAccess`의 default 메서드로, `Owner`나 `Visible`일 때 true다. 구독 안내(`SubscribersOnly`)는 읽을 수 있는 것이 아니므로 301이 아니라 404가 된다.

```java
private PostAccess decideInOwnBlog(Post post, Long viewerId) {
    Blog blog = post.getBlog();
    // ③ 주인인가
    if (blog.isOwnedBy(viewerId)) {
        return new PostAccess.Owner(post, post.isBlinded());
    }
    // ④ 다른 사람이 볼 수 있나
    boolean openExceptAudience = post.getStatus() == PostStatus.PUBLISHED
            && !post.isBlinded()
            && blogVisibilityPolicy.isOpenToOthers(blog);
    if (!openExceptAudience) {
        return new PostAccess.NotFound();
    }
    return switch (post.getVisibility()) {
        case PUBLIC -> new PostAccess.Visible(post);
        case PRIVATE -> new PostAccess.NotFound();
        case SUBSCRIBERS -> isSubscribed(viewerId, blog)
                ? new PostAccess.Visible(post)
                : new PostAccess.SubscribersOnly(blog);
    };
}
```

- **③**: `blog.isOwnedBy(viewerId)`는 `memberId != null && memberId.equals(member.getId())`다(`Blog.java`). 비회원(null)은 절대 주인이 아니다. 주인은 임시저장·비공개·숨긴 글도 본다. 숨긴 글이면 `blinded = true`라서, 화면이 관리 이력(`moderation_log`)의 숨김 사유를 함께 보여 줄 수 있다.
- **④를 두 단계로 나눈 이유**: "공개 범위를 뺀 나머지 조건"(`openExceptAudience`)을 먼저 본다. 구독 안내는 "**나머지 조건은 모두 맞고** 구독만 안 한" 경우에만 준다. 숨긴 구독자 글을 구독 안내로 보여 주면 숨긴 글이 있다는 사실이 새기 때문이다.
- `switch (post.getVisibility())`: enum에 대한 switch 식이다. `PUBLIC`, `PRIVATE`, `SUBSCRIBERS` 셋을 다 다뤄서 `default`가 필요 없고, enum에 값이 추가되면 컴파일 오류가 난다.
- **구독 여부**는 비회원이면 false, 회원이면 `subscription` 테이블에서 `exists` 쿼리로 확인한다.

### 5.2 BlogVisibilityPolicy: 블로그 단위 판단

`src/main/java/com/nhnacademy/blog/global/visibility/BlogVisibilityPolicy.java`

```java
public boolean canView(Blog blog, Long viewerId) {
    if (blog.isDeleted()) {
        return false;                    // 삭제된 블로그는 아무도 못 본다
    }
    if (blog.isOwnedBy(viewerId)) {
        return true;                     // 이용 제한·정지라도 주인은 본다
    }
    return isOpenToOthers(blog);
}

public boolean isOpenToOthers(Blog blog) {
    return !blog.isDeleted()
            && !blog.isRestricted()                                         // ADMIN-05 이용 제한
            && !blog.getMember().isSuspendedAt(LocalDateTime.now(clock));   // ADMIN-02 정지 중에는 모든 블로그 숨김
}
```

글 판단(④)과 블로그 API(`@CurrentBlog`, [15](./15-subdomain-host-routing.md)), 화면 주소 처리([18](./18-spa-server-routing.md))가 모두 이 정책을 쓴다. "이용 제한 블로그는 주인만"이라는 규칙이 한 곳에 있다.

**정지 종료 시각**: `Member.isSuspendedAt(now)`

```java
public boolean isSuspendedAt(LocalDateTime now) {
    return status == MemberStatus.SUSPENDED && (suspendedUntil == null || suspendedUntil.isAfter(now));
}
```

- `suspendedUntil == null`이면 영구 정지(data-model.md).
- 종료 시각이 지났으면 `status`가 아직 `SUSPENDED`여도 정지가 아니다. "기간이 끝나면 자동 해제"(ADMIN-02)를 스케줄러가 상태를 바꾸기 전에도 지키기 위해서다.

### 5.3 Clock 주입: 시간을 테스트할 수 있게

`LocalDateTime.now()`를 코드 안에서 바로 부르면, "정지 종료 시각이 지난 경우"를 테스트하려면 실제로 시간이 지나야 한다. 그래서 **현재 시각을 알려 주는 객체(`java.time.Clock`)를 빈으로 주입**하고 `LocalDateTime.now(clock)`을 쓴다.

`src/main/java/com/nhnacademy/blog/global/config/ClockConfig.java`

```java
@Bean
Clock clock() {
    return Clock.systemDefaultZone();
}
```

운영에서는 진짜 시계를, 테스트에서는 `Clock.fixed(Instant.parse("2026-10-08T00:00:00Z"), ZoneId.of("Asia/Seoul"))` 같은 멈춘 시계를 넣어 "지금"을 마음대로 정할 수 있다. 지금 테스트는 정지 종료 시각을 2000년(이미 지남), 2099년(아직 안 지남)으로 넣어서 실제 시계로도 판단이 갈리게 했다(`AuthenticationIntegrationTest`).

> 목록 조건 `PostSpecifications.visibleTo(viewerId, now)`는 `now`를 인자로 받는다. 부르는 쪽(스텝 4 이후 서비스)이 `LocalDateTime.now(clock)`을 넘겨야 상세 판단과 같은 시계를 쓴다.

### 5.4 PostSpecifications: 같은 규칙을 쿼리로

`src/main/java/com/nhnacademy/blog/global/visibility/PostSpecifications.java`

```java
public static Specification<Post> visibleTo(Long viewerId, LocalDateTime now) {
    return (root, query, cb) -> {
        Join<Post, Blog> blog = root.join("blog");                      // JOIN blog
        Join<Blog, Member> owner = blog.join("member");                 // JOIN member (블로그 주인)

        Predicate ownerNotSuspended = cb.or(
                cb.notEqual(owner.get("status"), MemberStatus.SUSPENDED),          // 정지가 아니거나
                cb.and(cb.isNotNull(owner.get("suspendedUntil")),                  // 기한이 있고
                        cb.lessThanOrEqualTo(owner.<LocalDateTime>get("suspendedUntil"), now)));  // 이미 지남

        Predicate audience = cb.equal(root.get("visibility"), Visibility.PUBLIC);  // 공개
        if (viewerId != null) {
            Subquery<Long> subscribed = query.subquery(Long.class);
            var subscription = subscribed.from(Subscription.class);
            subscribed.select(subscription.get("id")).where(
                    cb.equal(subscription.get("blog"), blog),
                    cb.equal(subscription.get("member").get("id"), viewerId));
            audience = cb.or(audience, cb.and(                                     // 또는 구독자 공개 + 구독 중
                    cb.equal(root.get("visibility"), Visibility.SUBSCRIBERS), cb.exists(subscribed)));
        }

        return cb.and(
                cb.isNull(root.get("deletedAt")),            // ① 글 삭제 안 됨
                cb.isNull(blog.get("deletedAt")),            // ① 블로그 삭제 안 됨
                cb.equal(root.get("status"), PostStatus.PUBLISHED),   // ④ 발행됨
                cb.isFalse(root.get("blinded")),             // ④ 숨김 아님
                cb.isFalse(blog.get("restricted")),          // ④ 이용 제한 아님
                ownerNotSuspended,                           // ④ 주인 정지 아님
                audience);                                   // ④ 공개 범위
    };
}
```

만들어지는 SQL은 대략 이렇다.

```sql
SELECT p.* FROM post p
JOIN blog b ON b.id = p.blog_id
JOIN member m ON m.id = b.member_id
WHERE p.deleted_at IS NULL AND b.deleted_at IS NULL
  AND p.status = 'PUBLISHED' AND p.is_blinded = 0 AND b.is_restricted = 0
  AND (m.status <> 'SUSPENDED' OR (m.suspended_until IS NOT NULL AND m.suspended_until <= ?))
  AND (p.visibility = 'PUBLIC'
       OR (p.visibility = 'SUBSCRIBERS'
           AND EXISTS (SELECT s.id FROM subscription s WHERE s.blog_id = b.id AND s.member_id = ?)))
```

자바 판단(`isSuspendedAt`)과 비교해 보자. 자바는 "정지 중 = SUSPENDED이고 (기한 없음 또는 기한이 미래)", 쿼리는 그 부정인 "정지 아님 = SUSPENDED 아님 또는 (기한 있고 기한 ≤ now)"다. 드모르간 법칙으로 같은 조건이다.

`'member'` 같은 문자열은 **엔티티의 필드 이름**이다(컬럼 이름 `member_id`가 아님). 오타를 내면 컴파일은 되고 실행할 때 오류가 난다. 메타모델(`Post_`)이나 QueryDSL을 쓰면 컴파일 시점에 잡을 수 있지만, 이 프로젝트는 아직 쓰지 않는다.

**주인 보기**: 주인이 자기 블로그를 볼 때만 `ownerView()`(삭제 안 된 모든 글)를 쓴다. 그 밖에는 자기 글이라도 `visibleTo`다. 예를 들어 홈 최신 글에는 내 비공개 글이 나오지 않는다(data-model.md "주인이 자기 블로그를 볼 때만 ④를 건너뛴다").

**두 규칙이 같은지 확인하는 테스트**: `src/test/.../global/visibility/PostVisibilityIntegrationTest.java`의 `listConditionMatchesDetailDecision`

```java
Post publicPost = published(Visibility.PUBLIC);
Post subscribersPost = published(Visibility.SUBSCRIBERS);
Post privatePost = published(Visibility.PRIVATE);
Post draft = ...draft...;
Post blinded = ...숨김...;
Post deleted = ...삭제...;
subscriptionRepository.save(Subscription.subscribe(other, blog));     // other는 구독 중

assertThat(ids(visibleTo(null, now))).containsExactly(publicPost.getId());           // 비회원: 공개 글만
assertThat(ids(visibleTo(other.getId(), now)))
        .containsExactlyInAnyOrder(publicPost.getId(), subscribersPost.getId());     // 구독자: + 구독자 글
assertThat(ids(ownerView())).containsExactlyInAnyOrder(... 삭제 글만 빼고 다섯 개 ...);  // 주인
// 주인을 정지시키면 남에게는 아무 글도 안 보인다
```

같은 테스트 클래스의 다른 테스트들이 상세 판단(`policy.decide`)에서 같은 글들이 어떤 결과를 내는지 확인한다. 둘을 함께 보면 "상세에서 `Visible`인 글 = 목록에 나오는 글"이 맞는지 알 수 있다. 다만 이 테스트는 상세 판단을 직접 불러 비교하지는 않고 기대값을 손으로 적어 둔 것이라, 규칙을 바꿀 때는 두 쪽 테스트를 함께 고쳐야 한다.

### 5.5 BlogOwnerGuard: 주인 검사

`src/main/java/com/nhnacademy/blog/global/auth/BlogOwnerGuard.java`

```java
public LoginMember requireOwner(Blog blog, LoginMember member) {
    if (member == null) {
        throw new BusinessException(ErrorCode.UNAUTHORIZED);   // 401
    }
    if (!blog.isOwnedBy(member.id())) {
        throw new BusinessException(ErrorCode.FORBIDDEN);      // 403
    }
    return member;
}
```

블로그 수정, 글쓰기, 카테고리 관리처럼 **주인만 하는 일**의 입구에서 부른다. 블로그가 있는지(404)는 `@CurrentBlog`가 이미 걸렀으므로 여기서는 401 → 403 순서만 지키면 된다. 남의 블로그 관리는 블로그 자체가 공개라 "있다는 것"이 이미 알려져 있으므로 404가 아니라 403이다.

통합 테스트 `CurrentBlogIntegrationTest.ownerGuardOrder401Then403`이 비회원 401, 남 403, 주인 200을 확인하고, `missingBlogIs404BeforeLoginCheck`가 없는 블로그에서는 로그인하지 않아도 401이 아니라 404가 먼저 나가는 것을 확인한다.

스텝 4에서 이 검사가 처음으로 실제 API에 쓰였다: `PATCH /api/blog`(블로그 이름·소개 수정). 코드는 5.7 ④.

### 5.6 화면과 API에서 결과를 어떻게 쓰나

| 결과 | 화면 주소 `/{id}` (`SpaForwardController`) | 글 상세 API (스텝 6 예정) |
| --- | --- | --- |
| `NotFound` | 404 상태로 index.html | 404 `NOT_FOUND` |
| `MovedTo` | 301 지금 블로그로 | (화면 단계에서 이미 301) |
| `Owner` | 200 | 200, 숨김이면 사유 포함 |
| `Visible` | 200 | 200 |
| `SubscribersOnly` | 200 (화면이 API 응답으로 안내) | 403 `SUBSCRIBERS_ONLY` + 블로그 정보 |

### 5.7 (스텝 4) 블로그 화면: 목록·글 수·사이드바가 한 조건을 쓴다

**① `listedIn`**: `global/visibility/PostSpecifications.java`

```java
public static Specification<Post> listedIn(Blog blog, Long viewerId, LocalDateTime now) {
    return (root, query, cb) -> listedIn(root, query, cb, blog, viewerId, now);
}

/** listedIn을 다른 엔티티의 조인(댓글 → 글 등)에 쓸 때. post는 Root이거나 Join이다. */
public static Predicate listedIn(From<?, Post> post, CriteriaQuery<?> query, CriteriaBuilder cb, Blog blog,
                                 Long viewerId, LocalDateTime now) {
    Predicate inBlog = cb.equal(post.get("blog").get("id"), blog.getId());
    if (blog.isOwnedBy(viewerId)) {
        return cb.and(inBlog, cb.isNull(post.get("deletedAt")),
                cb.equal(post.get("status"), PostStatus.PUBLISHED));
    }
    return cb.and(inBlog, visibleTo(post, query, cb, viewerId, now));
}
```

- 블로그 조건(`inBlog`)이 안에 들어 있어, 부르는 쪽이 `inBlog`를 따로 붙이다 빠뜨릴 일이 없다.
- 주인 쪽에 블로그 삭제 조건이 없는 이유: 이 조건을 쓰는 API는 모두 `@CurrentBlog`를 거쳐, 삭제된 블로그면 이미 404가 났다.
- `From<?, Post>` 버전이 있어 댓글 → 글 조인에도 쓴다(아래 ③, [JPA](./06-jpa-entity-mapping.md) 5.9 ④).

**② 이 조건을 쓰는 곳**

| 숫자·목록 | 코드 | 비회원이 비공개 글 1개 + 공개 글 1개인 블로그를 볼 때 |
| --- | --- | --- |
| 블로그 정보의 `postCount` | `BlogQueryService.detail` → `postRepository.count(listedIn(...))` | 1 |
| 블로그 메인 글 목록과 `totalElements` | `PostQueryService.blogPosts` → `findAll(listedIn(...), pageable)` | 공개 글 1개 |
| 카테고리 트리의 글 수, 전체 글, 미분류 | `CategoryTreeService.tree` → `countByCategory(listedIn(...))` | 합계 1 |
| 사이드바 최근 글 5 | `SidebarService.recentPosts` | 공개 글 1개 |
| 사이드바 최근 댓글 5 | `SidebarService.recentComments`(댓글 JOIN 글에 같은 조건) | 공개 글의 댓글만 |

다섯 군데가 같은 조건을 쓰므로 "목록에는 3개인데 글 수는 4"처럼 숫자가 어긋나지 않고, 비공개 글의 제목이 사이드바 최근 글에 새지 않는다. 테스트: `BlogInfoIntegrationTest.blogInfoCountsOnlyPostsTheViewerCanSee`, `BlogPostListIntegrationTest.othersSeeOnlyVisiblePostsAndOwnerSeesAllPublished`, `SidebarIntegrationTest.categoriesInOrderWithVisiblePostCounts`, `recentCommentsSkipHiddenPostsAndMaskSecretOrBlinded`.

**③ 최근 댓글: 볼 수 있는 글의 댓글이라도 내용은 가린다**: `blog/application/SidebarService.java`

```java
private static Sidebar.RecentComment toRecentComment(Comment comment) {
    Sidebar.CommentState state = comment.isBlinded() ? Sidebar.CommentState.BLINDED
            : comment.isSecret() ? Sidebar.CommentState.SECRET
            : Sidebar.CommentState.NORMAL;
    boolean shown = state == Sidebar.CommentState.NORMAL;
    return new Sidebar.RecentComment(comment.getId(), comment.getPost().getId(),
            shown ? comment.getContent() : null, shown ? comment.getMember().getNickname() : null, state);
}
```

- 글 단위 가시성(볼 수 없는 글의 댓글은 아예 빠짐)과 댓글 단위 가림(비밀·숨김 댓글은 `state`만)이 두 겹이다. 지운 댓글(`deleted_at`)은 쿼리에서 뺀다.
- 사이드바에서는 주인에게도 비밀댓글 내용을 주지 않는다(rest-api.md "사이드바 응답"). 글 상세의 댓글 목록(스텝 6)은 글 주인·작성자에게 비밀댓글 내용을 보여 주므로 규칙이 다르다.

**④ 비공개 카테고리**: 주인이 아니면 트리와 목록에서 없는 카테고리다.

```java
// category/application/CategoryTreeService.tree
// 주인이 아니면 비공개 카테고리(CAT-05)는 없는 것처럼, 그 아래 카테고리도 함께 뺀다
List<Category> categories = categoryRepository.findByBlogIdOrderBySortOrderAscIdAsc(blog.getId()).stream()
        .filter(category -> owner || !category.isPrivateCategory())
        .toList();
```

```java
// post/application/PostQueryService.inCategory
// 다른 블로그의 카테고리, 주인이 아닌 사람에게 비공개 카테고리는 없는 것과 같다
Category category = categoryRepository.findById(categoryId)
        .filter(found -> found.getBlog().getId().equals(blog.getId()))
        .filter(found -> !found.isPrivateCategory() || blog.isOwnedBy(viewerId))
        .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));
```

- 다른 블로그의 카테고리 번호를 붙여도, 비공개 카테고리 번호를 붙여도 똑같이 404다. "그 번호가 있긴 하다"를 알려 주지 않는다(3.2).
- 트리 응답의 `isPrivate`는 주인에게만 준다(`CategoryTreeResponse`가 주인이 아니면 null로 두고 JSON에서 뺀다).
- 아직 남은 점: 비공개 카테고리 기능(CAT-05)은 백로그라 지금은 `is_private`를 바꿀 API가 없다. 그래서 (가) 주인이 아닌 사람의 `totalCount`에는 비공개 카테고리 글도 세어지고 (나) 비공개 상위 카테고리 아래의 공개 하위 카테고리 번호로 목록을 직접 요청하면 열린다. CAT-05를 만들 때 글 조건에 카테고리 공개 여부를 넣어 함께 고친다.

**⑤ 주인 검사 뒤에 입력 검증**: `blog/presentation/BlogController.java`

```java
/** 주인만. 비회원 401, 남의 블로그 403, 그다음 입력 오류 400 순서다. */
@PatchMapping("/api/blog")
public BlogResponse update(@CurrentBlog Blog blog, @AuthenticationPrincipal LoginMember member,
                           @RequestBody BlogUpdateRequest request) {
    blogOwnerGuard.requireOwner(blog, member);
    requestValidator.validate(request);
    Blog updated = blogService.updateInfo(blog.getAddress(), request.name(), request.description());
    return BlogResponse.from(blogQueryService.detail(updated, member.id()));
}
```

순서: `@CurrentBlog`(인자 해석, 404) → `requireOwner`(401 → 403) → `requestValidator.validate`(400). `@RequestBody`에 `@Valid`가 없다는 점이 핵심이다. 테스트 `BlogInfoIntegrationTest.onlyOwnerCanUpdateAndPermissionComesBeforeInputErrors`가 51자 이름을 보내 비회원 401, 남 403, 주인 400을 확인한다. `RequestValidator`의 동작은 [입력 검증](./22-bean-validation.md)에 있다. 다만 JSON 자체가 깨진 본문(파싱 실패)은 인자를 만들 수 없어 여전히 400이 먼저 나간다.

## 6. 자주 하는 실수와 함정

1. **판단을 복사해서 쓰기**: 컨트롤러에 `if (post.isPrivate())`를 직접 쓰기 시작하면 규칙이 흩어진다. 항상 정책에 묻는다.
2. **목록을 자바로 거르기**: 페이지 크기와 전체 개수가 틀어진다. 목록은 Specification으로.
3. **상세와 목록 중 한쪽만 고치기**: 규칙이 바뀌면 `PostVisibilityPolicy`와 `PostSpecifications`, 테스트 양쪽을 함께 고친다.
4. **403으로 존재를 알려 주기**: 볼 수 없는 글·블로그는 404. 403은 "있다는 걸 이미 아는" 경우에만.
5. **401을 404보다 먼저 판단하기**: 서비스 코드에서 "로그인했나"를 글·블로그 조회보다 먼저 검사하면 순서가 뒤집혀, 비회원이 없는 글과 있는 글을 구분할 수 있게 된다. 대상을 먼저 찾고(404), 그다음 로그인(401), 그다음 권한(403)을 본다. `@CurrentBlog`는 인자 해석 단계에서 블로그를 먼저 찾으므로 이 순서가 자연스럽게 지켜진다.
6. **null 회원 비교**: `blog.getMember().getId().equals(viewerId)`는 viewerId가 null일 때는 괜찮지만 반대로 `viewerId.equals(...)`는 NPE가 난다. `isOwnedBy`처럼 null을 먼저 처리한다.
7. **`switch`에 `default` 넣기**: sealed/enum의 "빠뜨리면 컴파일 오류" 보호가 사라진다.
8. **`LocalDateTime.now()` 직접 호출**: 시간 관련 판단을 테스트하기 어려워진다. `Clock`을 주입한다.
9. **지연 로딩 예외**: 정책에 넘기는 `Post`가 블로그·주인을 읽지 않은 상태면 `LazyInitializationException`. `findWithBlogById`로 읽은 것을 넘긴다.
10. **(스텝 4) 숫자마다 조건을 따로 쓰기**: 글 수는 `countByBlogId`, 목록은 `listedIn`처럼 나누면 비공개 글이 글 수에만 세어진다. 블로그 화면의 모든 목록·개수는 `listedIn` 하나로.
11. **(스텝 4) 주인 화면이라고 `ownerView`를 쓰기**: 임시저장 글이 블로그 메인에 섞인다. 블로그 화면은 `listedIn`, 관리 화면의 글 관리(스텝 9 MNG-01)가 `ownerView` 쪽이다.
12. **(스텝 4) 주인 검사가 있는 API에 `@Valid`**: 남의 블로그에 틀린 값을 보내면 403 대신 400이 나간다.

## 7. 직접 해 보기

**실습 1. 결과 6개 테스트 돌리기**

```bash
./mvnw test -Dtest=PostVisibilityIntegrationTest
```

IntelliJ에서 테스트 메서드 이름을 보면 표의 결과와 1:1로 대응한다(`privatePostIs404ToOthersEvenWhenLoggedIn`, `blindedPostIsShownOnlyToOwnerWithFlag`, `subscribersOnlyPostShowsNoticeUntilSubscribed`, `postOfAnotherBlogRedirectsOnlyWhenVisible` 등).

**실습 2. 규칙 하나를 빼고 무엇이 깨지는지 보기**

1. `PostVisibilityPolicy`의 `&& !post.isBlinded()`를 지운다.
2. `./mvnw test -Dtest=PostVisibilityIntegrationTest`
3. 기대 결과: `blindedPostIsShownOnlyToOwnerWithFlag`가 실패한다. 그런데 `listConditionMatchesDetailDecision`은 **통과한다**(목록 쪽 조건은 그대로라서). 이것이 "규칙이 두 군데에 있다"는 뜻이다. 되돌린다.

**실습 3. sealed의 컴파일 보호 확인**

1. `PostAccess`에 `record Blocked() implements PostAccess { }`를 추가한다.
2. `./mvnw compile`
3. 기대 결과: `SpaForwardController`의 switch에서 "the switch expression does not cover all possible input values" 오류. 되돌린다.

**실습 4. 상태 코드 순서**

```bash
./mvnw test -Dtest='CurrentBlogIntegrationTest#missingBlogIs404BeforeLoginCheck+ownerGuardOrder401Then403'
```

**실습 5. (스텝 4) 블로그 화면의 숫자가 같은 조건을 쓰는지**

```bash
./mvnw test -Dtest='BlogInfoIntegrationTest,BlogPostListIntegrationTest,SidebarIntegrationTest'
```

그다음 `PostSpecifications.listedIn`의 주인 쪽에서 `cb.equal(post.get("status"), PostStatus.PUBLISHED)`를 지우고 다시 돌린다. 기대: 주인이 볼 때 임시저장 글까지 세어져 `blogInfoCountsOnlyPostsTheViewerCanSee`(주인 postCount 2)와 `othersSeeOnlyVisiblePostsAndOwnerSeesAllPublished`가 실패한다. 되돌린다.

**실습 6. (스텝 4) 403과 400의 순서**

`BlogController.update`의 파라미터를 `@Valid @RequestBody BlogUpdateRequest request`로 바꾸고 `requestValidator.validate(request);` 줄을 지운 뒤 `BlogInfoIntegrationTest#onlyOwnerCanUpdateAndPermissionComesBeforeInputErrors`를 돌린다. 기대: 남의 회원이 51자 이름을 보낸 경우 403이 아니라 400이 나와 실패한다. 되돌린다.

**실습 7. 만들어지는 SQL 보기**

`application-dev.yml`에 잠깐 `spring.jpa.show-sql: true`를 넣고 테스트를 돌리면, `listConditionMatchesDetailDecision`이 실행하는 SQL에서 `exists (select ... from subscription ...)`를 볼 수 있다. 확인 후 지운다.

## 8. 확인 문제

1. 인증과 인가의 차이를 이 프로젝트 예로 설명하라.
<details><summary>답</summary>인증은 쿠키의 JWT로 "누구인지" 확인하는 것(실패 401), 인가는 "그 사람이 이 블로그를 관리해도 되나, 이 글을 봐도 되나"를 판단하는 것(실패 403, 또는 존재를 숨기는 404)이다.</details>

2. 비공개 글을 남이 열 때 403이 아니라 404를 주는 이유는?
<details><summary>답</summary>403은 그 글이 존재한다는 사실을 알려 준다. 404를 주면 없는 글과 못 보는 글을 구분할 수 없어 정보가 새지 않는다(헌법 II).</details>

3. 비회원이 없는 블로그의 관리 API를 부르면 401과 404 중 무엇이 나가야 하나? 이 프로젝트에서 그 순서를 지키게 하는 구조는?
<details><summary>답</summary>404다. <code>@CurrentBlog</code> 인자 해석이 컨트롤러 실행 전에 블로그를 찾아 없으면 404를 던지고, 주인 검사(<code>BlogOwnerGuard</code>, 401/403)는 컨트롤러 안에서 그 뒤에 일어난다.</details>

4. 숨긴 구독자 공개 글을 구독하지 않은 사람이 열면 결과는? 구독 안내가 아닌 이유는?
<details><summary>답</summary>404(<code>NotFound</code>)다. 구독 안내는 "나머지 조건은 다 맞고 구독만 안 한" 경우에만 주므로, 숨긴 글을 구독 안내로 보여 주면 숨긴 글이 있다는 사실이 새기 때문이다.</details>

5. `beta.blog.com/15`(15번은 alpha의 공개 글)를 열면? alpha의 비공개 글이면?
<details><summary>답</summary>공개 글이면 <code>MovedTo(alpha)</code>로 <code>alpha.blog.com/15</code>에 301, 비공개 글이면 404다(남에게 <code>canRead</code>가 아니므로).</details>

6. 글 목록을 다 읽은 뒤 자바에서 가시성으로 거르면 생기는 문제 두 가지는?
<details><summary>답</summary>한 페이지에 나오는 개수가 들쭉날쭉해지고, 전체 개수가 볼 수 없는 글까지 세어 틀린다(그리고 불필요한 데이터를 읽어 느리다).</details>

7. `PostAccess` switch에 `default`를 쓰지 않는 이유는?
<details><summary>답</summary>sealed interface라 컴파일러가 모든 경우를 다뤘는지 확인해 준다. 결과 종류가 늘면 처리하지 않은 switch가 모두 컴파일 오류가 나서 빠뜨릴 수 없다. <code>default</code>를 쓰면 새 결과가 조용히 default로 흘러간다.</details>

8. 정지 종료 시각 판단에 `LocalDateTime.now()` 대신 `LocalDateTime.now(clock)`을 쓰는 이유는?
<details><summary>답</summary>테스트에서 <code>Clock</code>을 고정된 시계로 바꿔 "지금"을 마음대로 정할 수 있어서, 시간이 실제로 지나지 않아도 정지 해제 같은 시간 판단을 검증할 수 있기 때문이다.</details>

9. (스텝 4) 블로그 주인이 자기 블로그 메인을 볼 때 나오는 글과 나오지 않는 글은?
<details><summary>답</summary>삭제되지 않은 발행 글은 비공개·구독자 공개·숨긴 글까지 모두 나온다. 임시저장·예약 글과 삭제한 글은 나오지 않는다(<code>listedIn</code>의 주인 쪽 조건). 임시저장·예약 글은 관리 화면의 글 관리에서 본다.</details>

10. (스텝 4) 블로그 정보의 글 수, 카테고리 트리의 글 수, 사이드바 최근 글이 모두 `listedIn`을 쓰는 이유는?
<details><summary>답</summary>같은 사람에게 보이는 숫자와 목록이 서로 맞아야 하고(목록 3개인데 글 수 4 같은 어긋남 방지), 비공개 글이 개수나 사이드바 제목으로 새지 않게 하려는 것이다. 조건이 한 곳에 있으면 규칙을 바꿀 때도 한 곳만 고친다.</details>

11. (스텝 4) `PATCH /api/blog`에서 `@Valid`를 쓰지 않고 `requestValidator.validate(request)`를 주인 검사 뒤에 부르는 이유는?
<details><summary>답</summary><code>@Valid</code>는 컨트롤러 메서드에 들어가기 전에 검증해서, 남의 블로그에 틀린 값을 보내면 403보다 400이 먼저 나간다. 상태 코드 순서(404 → 401 → 403 → 400)를 지키려면 주인 검사를 먼저 하고 그다음 검증해야 한다.</details>

## 9. 더 읽을거리

- data-model.md "글 가시성 판단", rest-api.md "상태 코드 순서"
- OWASP, "Insecure Direct Object Reference(IDOR)"와 Broken Access Control (OWASP Top 10 A01)
- MDN Web Docs, HTTP 상태 코드 401, 403, 404
- Spring Data JPA 레퍼런스, "Specifications"
- Jakarta Persistence 명세, Criteria API
- JEP 409 (Sealed Classes), JEP 441 (Pattern Matching for switch), JEP 395 (Records)
- `java.time.Clock` Javadoc
