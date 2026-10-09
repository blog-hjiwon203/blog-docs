# 37. 거르기 조건이 있는 목록과 일괄 처리: 내 글 관리

> 관련 스텝: [스텝 9](../step-09.md) (T067) · 관련 개념: [06-jpa-entity-mapping](./06-jpa-entity-mapping.md), [08-pagination](./08-pagination.md), [16-authorization-visibility](./16-authorization-visibility.md), [27-soft-delete-bulk-update](./27-soft-delete-bulk-update.md), [32-search-like](./32-search-like.md), [23-transactions-locking](./23-transactions-locking.md), [25-react-forms-data](./25-react-forms-data.md)

## 1. 이 문서로 배우는 것

- **동적 쿼리**: 사용자가 고른 조건만 WHERE에 붙이는 법. Specification을 `and`로 조합하기
- 두 시각을 한 줄로 섞는 정렬 `COALESCE(published_at, updated_at)`과, 그것을 페이지 쿼리에 거는 법(정렬을 Specification 안에서)
- 개수 쿼리와 내용 쿼리: 페이지가 쿼리를 두 번 보내는 이유와 정렬을 개수 쿼리에 걸지 않는 이유
- 거르기 값 검사를 **주인 확인 뒤에** 하는 이유(상태 코드 순서 401 → 403 → 400)
- **일괄 처리**: 여러 글 번호를 받아 한 트랜잭션으로 바꾸기. 남의 글·지운 글·없는 번호를 어떻게 다루나
- 글 하나 처리 규칙을 **재사용**해서 일괄 삭제 만들기
- LIKE 이스케이프를 공용 도구로 옮기기(`LikePatterns`)
- 화면: 거르기 조건을 **주소(쿼리 문자열)**에 두기, 체크박스로 여러 개 고르기, "이 페이지 모두 선택"

**먼저 알면 좋은 것**: Specification과 `findAll(spec, pageable)`([06](./06-jpa-entity-mapping.md)), 페이지 번호 방식([08](./08-pagination.md)), 주인 검사와 가시성([16](./16-authorization-visibility.md)), 소프트 삭제([27](./27-soft-delete-bulk-update.md)), LIKE 이스케이프([32](./32-search-like.md)).

## 2. 왜 필요한가

글이 수십 개가 되면 주인은 "비공개 글만 보기", "Spring 카테고리 글만 보기", "제목에 '정리'가 들어간 글 찾기" 같은 일을 하고 싶다. 그리고 찾은 글 여러 개를 **한 번에** 비공개로 바꾸거나 지우고 싶다. 명세 MNG-01이 바로 이것이다.

> 상태·카테고리 필터, 검색, 공개 범위 일괄 변경·삭제. 20개씩 페이지. (spec US8 시나리오 1·2)

블로그 메인 글 목록(스텝 4)과 다른 점이 셋 있다.

| | 블로그 메인 목록 | 내 글 관리 |
| --- | --- | --- |
| 보는 사람 | 누구나 | 주인만 |
| 나오는 글 | 볼 수 있는 발행 글(주인에게는 비공개·숨김 포함) | **지우지 않은 모든 글**(임시저장·예약 포함) |
| 조건 | 카테고리 또는 태그 하나 | 상태·공개 범위·카테고리·검색어를 **골라서 겹쳐** |

## 3. 기본 개념

### 3.1 동적 쿼리

"고른 조건만 붙이는" 쿼리를 **동적 쿼리**라 한다. 조건이 4개면 조합이 16가지라, 쿼리를 16개 미리 써 둘 수는 없다.

문자열로 SQL을 이어 붙이는 방법도 있다(`"... WHERE 1=1" + (status != null ? " AND status = ?" : "")`). 하지만 괄호·AND 위치를 틀리기 쉽고, 사용자 값을 문자열에 붙이면 SQL 주입 위험이 있다.

JPA에서는 **Specification**(조건 하나를 담은 객체)을 만들어 `and`로 잇는다([06](./06-jpa-entity-mapping.md)). 조건이 없으면 그냥 안 붙이면 된다.

```java
Specification<Post> condition = mine(blog);
if (status != null)  condition = condition.and(상태가 status);
if (q != null)       condition = condition.and(제목 LIKE q);
```

값은 Criteria API가 **바인딩 변수**로 보내서 주입 걱정이 없다.

### 3.2 페이지는 쿼리를 두 번 보낸다

`findAll(spec, pageable)`은 `Page`를 돌려준다. `Page`에는 그 페이지의 글 20개와 **전체 개수**(`totalElements`, 그래서 `totalPages`)가 있다. 그래서 Spring Data JPA는 쿼리를 둘 보낸다.

```sql
-- 내용 쿼리
SELECT ... FROM post WHERE (조건) ORDER BY ... LIMIT 20 OFFSET 20;
-- 개수 쿼리
SELECT COUNT(p.id) FROM post p WHERE (조건);
```

같은 Specification이 두 쿼리에 모두 쓰인다. 개수 쿼리에 정렬을 붙이면 쓸모없을 뿐 아니라, DB에 따라 오류가 나기도 한다. 그래서 Specification 안에서 정렬을 걸 때는 "지금 만드는 쿼리가 개수 쿼리인가"를 봐야 한다(5.2).

### 3.3 두 시각을 한 줄로 섞는 정렬: `COALESCE`

명세(contracts)는 "내 글 20 **최신순**(임시저장은 **수정 시각순**)"이다. 발행한 글은 처음 발행 시각(`published_at`)이 있고, 임시저장 글은 그것이 없다(NULL). 둘을 한 목록에 섞으려면 "발행 시각이 있으면 그것, 없으면 수정 시각"으로 줄 세운다.

```sql
ORDER BY COALESCE(published_at, updated_at) DESC, id DESC
```

`COALESCE(a, b)`는 앞에서부터 NULL이 아닌 첫 값을 돌려준다. 마지막의 `id DESC`는 같은 시각일 때 순서를 하나로 정하는 동점 처리다([36](./36-ranking-aggregation.md) 3.4).

`Sort.by("publishedAt")` 같은 Spring Data의 정렬 객체는 칸 이름만 받아서 이런 식은 표현할 수 없다. 그래서 Criteria API로 직접 `query.orderBy(cb.desc(cb.coalesce(...)))`를 건다.

### 3.4 일괄 처리의 세 가지 질문

여러 글 번호 `[12, 15, 999]`를 받아 한 번에 바꿀 때 정해야 할 것.

1. **남의 글·지운 글·없는 번호가 섞여 있으면?**
   - (가) 하나라도 이상하면 전체를 거절(404)
   - (나) **내 글인 것만 바꾸고, 바꾼 수를 알려 준다**
2. **중간에 하나가 실패하면?** 이미 바꾼 것은 그대로? 모두 되돌림?
3. **글 하나 처리와 규칙이 같은가?**

이 프로젝트의 답:

1. (나). 명세 응답이 `{ updatedCount }`·`{ deletedCount }`라 "몇 개를 바꿨다"를 알려 주는 모양이다. 다른 사람이 동시에 글을 지웠거나, 다른 탭에서 이미 지운 글이 섞여도 나머지는 처리된다. 남의 글은 조회 조건(`이 블로그`)에서 빠지므로 **건드릴 방법이 없다**.
2. **모두 되돌린다.** 서비스 메서드 하나가 `@Transactional`이라, 중간에 예외가 나면 앞의 변경도 롤백된다.
3. **같다.** 공개 범위는 글 하나 변경(POST-06)처럼 숨긴 글도 바꿀 수 있고 구독자 공개는 막는다. 삭제는 글 하나 삭제(`PostService.delete`)를 **그대로 불러** 댓글·공감·알림 처리가 똑같다.

### 3.5 조건 값 검사도 상태 코드 순서를 따른다

이 프로젝트의 상태 코드 순서는 **404 → 401 → 403 → 400**이다(contracts). 비회원이 `?status=이상한값`으로 남의 관리 API를 부르면 400("값이 틀렸다")보다 401("로그인하세요")이 먼저여야 한다. 그렇지 않으면 로그인도 안 한 사람이 입력 검사 규칙을 알아낼 수 있고, 무엇보다 "이 API는 주인만"이라는 사실이 흐려진다.

그런데 `@RequestParam PostStatus status`처럼 enum으로 받으면, Spring이 **메서드에 들어가기 전에** 글자를 enum으로 바꾸다 실패해 400을 낸다. 주인 확인(메서드 첫 줄)보다 먼저다. 그래서 거르기 값은 **글자로 받고**, 주인 확인 **뒤에** 직접 enum으로 바꾼다(5.3).

## 4. 동작 원리

### 4.1 목록

```
myblog.blog.test/manage/posts?status=PUBLISHED&categoryId=3&q=정리&page=2      (화면 주소)
  GET /api/manage/posts?status=PUBLISHED&categoryId=3&q=정리&page=2
    ManagePostController.posts
      blogOwnerGuard.requireOwner        비회원 401, 주인 아님 403
      parse(status), parse(visibility)   모르는 값이면 400(그 칸)
      query(q)                           앞뒤 공백 제거, 비면 조건 없음, 100자 넘으면 400
    ManagePostService.posts
      mine(blog)                         이 블로그 AND 지우지 않음
      .and(newestFirst())                ORDER BY COALESCE(published_at, updated_at) DESC, id DESC
      .and(status = PUBLISHED)
      .and(category = 3 OR category.parent = 3)     없거나 남의 카테고리면 404
      .and(title LIKE '%정리%' ESCAPE '\')
      findAll(조건, 2페이지·20개)       내용 쿼리 + 개수 쿼리
      숨긴 글만 골라 사유 읽기          moderation_log 최신 BLIND
    썸네일 붙이기(PostThumbnails)
  ← { content: [{ ..., status, visibility, scheduledAt, blinded, blind }], page, size, totalElements, totalPages }
```

### 4.2 일괄 공개 범위 변경

```
PATCH /api/manage/posts  { postIds: [12, 15, 999], visibility: "PRIVATE" }
  주인 확인 → 입력 검사(postIds 1~100개, visibility 필수, SUBSCRIBERS면 400)
  ManagePostService.changeVisibility                      [트랜잭션]
    SELECT * FROM post WHERE blog_id = ? AND deleted_at IS NULL AND id IN (12, 15, 999)
      → 12, 15만 나옴 (999는 없음)
    post.changeVisibility(PRIVATE) 두 번              변경 감지 → 커밋 때 UPDATE 두 번
  ← { updatedCount: 2 }
```

### 4.3 일괄 삭제

```
DELETE /api/manage/posts  { postIds: [12, 15] }
  ManagePostService.delete                                [트랜잭션]
    내 글 번호만 고름 → [12, 15]
    postService.delete(blog, 12, member)   알림 삭제, 공감 삭제, 댓글 소프트 삭제, 글 소프트 삭제
    postService.delete(blog, 15, member)   (같은 트랜잭션에 합류)
  ← { deletedCount: 2 }
```

`PostService.delete`에도 `@Transactional`이 붙어 있지만, 기본 전파(`REQUIRED`)라 바깥 트랜잭션에 **합류**한다([23](./23-transactions-locking.md)). 그래서 두 글 삭제가 하나의 트랜잭션이다.

## 5. 이 프로젝트에서는

### 5.1 `manage/application/ManagePostService.posts`

```java
@Transactional(readOnly = true)
public ManagedPostPage posts(Blog blog, ManagePostFilter filter, PageQuery page) {
    Specification<Post> condition = mine(blog).and(newestFirst());
    if (filter.status() != null) {
        condition = condition.and((root, query, cb) -> cb.equal(root.get("status"), filter.status()));
    }
    if (filter.visibility() != null) {
        condition = condition.and((root, query, cb) -> cb.equal(root.get("visibility"), filter.visibility()));
    }
    if (filter.categoryId() != null) {
        condition = condition.and(inCategory(blog, filter.categoryId()));
    }
    if (filter.q() != null) {
        String pattern = LikePatterns.contains(filter.q());
        condition = condition.and((root, query, cb) -> cb.like(root.get("title"), pattern, LikePatterns.ESCAPE));
    }
    // 정렬은 newestFirst가 쿼리에 직접 건다. 페이지 요청에는 정렬을 넣지 않는다(넣으면 그것으로 덮인다)
    Page<Post> posts = postRepository.findAll(condition, page.toPageable(Sort.unsorted()));
    Map<Long, Map<String, String>> blindReasons = new LinkedHashMap<>();
    posts.getContent().stream()
            .filter(Post::isBlinded)
            .forEach(post -> blindReasons.put(post.getId(), postService.blindReason(post)));
    return new ManagedPostPage(posts, blindReasons);
}
```

- `ManagePostFilter`: 거르기 조건 네 개를 묶은 레코드. null이면 그 조건을 걸지 않는다.
- `mine(blog)`: `PostSpecifications.inBlog(blogId).and(PostSpecifications.ownerView())` — 이 블로그의, 지우지 않은 글. 주인이 자기 블로그를 볼 때의 조건을 가시성 판단 쪽에 이미 만들어 두었다([16](./16-authorization-visibility.md)). 임시저장·예약 글도 나온다(블로그 메인 `listedIn`과 다른 점).
- 람다 `(root, query, cb) -> ...` 하나가 Specification 하나다. 바깥 변수(`filter.status()`)를 그대로 쓴다.
- `LikePatterns.contains(q)`: `%`, `_`, `\`를 이스케이프한 뒤 앞뒤에 `%`를 붙인다(5.4). 내 글 관리는 **제목만** 찾는다. 블로그 안 검색(본문·태그까지)과 목적이 다르다. 내 글을 찾을 때는 제목이면 충분하고, 본문 LIKE는 무겁다.
- `page.toPageable(Sort.unsorted())`: 페이지 번호·크기만 담고 정렬은 비운다. `Pageable`에 정렬이 있으면 Spring Data가 그것을 `ORDER BY`로 써서 Specification이 건 정렬을 덮는다.
- 숨긴 글의 사유는 글 행이 아니라 관리 이력(`moderation_log`)의 최신 BLIND 행에 있다(ADMIN-03). 숨긴 글만 골라 읽으므로 대부분의 페이지에서는 쿼리가 늘지 않는다. 숨긴 글이 많으면 글마다 한 번씩 읽어 N+1이 되는데, 숨긴 글은 드물어서 받아들였다.

### 5.2 정렬을 거는 Specification

```java
/** 발행 시각(없으면 수정 시각) 최신순, 같으면 id 큰 순. 개수 쿼리에는 걸지 않는다. */
private static Specification<Post> newestFirst() {
    return (root, query, cb) -> {
        if (query.getResultType() != Long.class && query.getResultType() != long.class) {
            query.orderBy(cb.desc(cb.coalesce(root.get("publishedAt"), root.get("updatedAt"))),
                    cb.desc(root.get("id")));
        }
        return null;
    };
}
```

- Specification은 보통 조건(`Predicate`)을 돌려주지만, `query`(지금 만드는 CriteriaQuery)를 받으므로 정렬도 걸 수 있다. 조건이 없으니 `null`을 돌려준다. `and`로 이을 때 null인 조건은 무시된다.
- `query.getResultType()`: 개수 쿼리는 결과가 `Long`이다. 그때는 정렬을 걸지 않는다(3.2).
- `cb.coalesce(a, b)`: SQL `COALESCE(a, b)`.
- 테스트 `listsAllMyPostsNewestFirstWithStateAndBlindReason`이 "임시저장(수정 시각 = 지금) → 숨긴 글 → 비공개 → 오래된 글" 순서를 확인한다.

### 5.3 `ManagePostController`: 주인 확인 뒤에 값 읽기

```java
@GetMapping("/api/manage/posts")
public PageResponse<ManagedPostSummaryResponse> posts(@CurrentBlog Blog blog,
                                                      @AuthenticationPrincipal LoginMember member,
                                                      @RequestParam(required = false) String status,
                                                      @RequestParam(required = false) String visibility,
                                                      @RequestParam(required = false) Long categoryId,
                                                      @RequestParam(required = false) String q,
                                                      @RequestParam(required = false) Integer page) {
    blogOwnerGuard.requireOwner(blog, member);
    ManagePostFilter filter = new ManagePostFilter(parse(PostStatus.class, "status", status),
            parse(Visibility.class, "visibility", visibility), categoryId, query(q));
    ...
}

/** 비었으면 거르지 않는다. 모르는 값이면 400(그 칸). */
private static <E extends Enum<E>> E parse(Class<E> type, String field, String value) {
    if (value == null || value.isBlank()) {
        return null;
    }
    return Arrays.stream(type.getEnumConstants())
            .filter(constant -> constant.name().equals(value))
            .findFirst()
            .orElseThrow(() -> BusinessException.invalidField(field, "알 수 없는 값입니다."));
}
```

- `status`·`visibility`를 `String`으로 받는다(3.5). `blogOwnerGuard.requireOwner`가 첫 줄이라 비회원은 401, 다른 회원은 403이 먼저 난다. 테스트 `onlyOwnerCanUseIt`이 남이 `?status=이상한값`을 보내도 403인지 본다.
- `<E extends Enum<E>>`: 어떤 enum이든 받는 제네릭 메서드. `type.getEnumConstants()`가 그 enum의 모든 값이다. `Enum.valueOf`를 쓰면 틀린 값에 `IllegalArgumentException`이 나는데, 그것을 받아 바꾸는 것과 같은 일이다.
- `categoryId`는 숫자라 `Long`으로 받았다. 숫자가 아닌 글자를 보내면 메서드 전에 400이 나는데, 화면은 숫자만 보내므로 받아들였다.

### 5.4 공용으로 옮긴 `global/web/LikePatterns`

스텝 7의 검색(`SearchService.escapeLike`)에 있던 이스케이프를 내 글 관리도 쓰게 되어 공용 자리로 옮겼다.

```java
public final class LikePatterns {

    public static final char ESCAPE = '\\';

    /** 글자가 어디에든 들어 있는 것: %글자%. */
    public static String contains(String text) {
        return "%" + escape(text) + "%";
    }

    static String escape(String text) {
        return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_");
    }
}
```

같은 규칙이 두 군데 복사돼 있으면 한쪽만 고치는 실수가 생긴다. 기능 패키지(`manage`)가 다른 기능 패키지(`search`)에 기대지 않도록 `global/`에 두었다(CLAUDE.md의 패키지 규칙). 테스트 `filtersByStatusVisibilityCategoryAndTitle`이 `q=100%`로 "100%"가 든 제목만 나오는지 본다.

### 5.5 일괄 공개 범위 변경·삭제

```java
@Transactional
public int changeVisibility(Blog blog, Collection<Long> postIds, Visibility visibility) {
    List<Post> posts = postRepository.findAll(mine(blog).and(idIn(postIds)));
    posts.forEach(post -> post.changeVisibility(visibility));
    return posts.size();
}

@Transactional
public int delete(Blog blog, Collection<Long> postIds, LoginMember member) {
    List<Long> ids = postRepository.findAll(mine(blog).and(idIn(postIds))).stream().map(Post::getId).toList();
    ids.forEach(id -> postService.delete(blog, id, member));
    return ids.size();
}
```

- `mine(blog).and(idIn(postIds))`: **"이 블로그의 지우지 않은 글" 중에서** 받은 번호. 남의 글 번호를 넣어도 이 조건에서 빠지므로 권한 검사가 따로 필요 없다. 이렇게 "고칠 수 있는 범위 안에서 찾기"가 가장 안전한 방식이다(번호로 찾은 뒤 주인인지 확인하는 것보다 빠뜨릴 틈이 적다).
- 공개 범위: 엔티티 값을 바꾸면 커밋 때 UPDATE가 나간다(변경 감지, [06](./06-jpa-entity-mapping.md)). JPQL 한 문장(`update Post set visibility = ... where id in ...`)으로도 할 수 있지만, 글 하나 바꾸기와 **같은 엔티티 메서드**를 거치게 해서 규칙(나중에 생길 알림 등)이 한 곳에 모이게 했다. 한 번에 100개까지라 성능 차이도 작다.
- 삭제: `postService.delete`는 글마다 가시성 판단(`findOwned`)부터 다시 한다. 앞에서 내 글만 골랐으니 통과한다. 글 하나 삭제와 결과가 완전히 같다.
- 반환값이 실제로 처리한 수다. 이미 지운 글을 다시 지우면 0이다(테스트에서 확인).

### 5.6 요청 DTO의 검사

```java
public record BulkVisibilityRequest(
        @NotEmpty(message = "글을 골라 주세요.")
        @Size(max = 100, message = "한 번에 100개까지 바꿀 수 있습니다.")
        List<Long> postIds,

        @NotNull(message = "공개 범위를 골라 주세요.")
        Visibility visibility) {
}
```

- `@NotEmpty`: null이거나 빈 목록이면 400. 빈 목록이면 SQL `IN ()`이 문법 오류가 되기도 한다.
- `@Size(max = 100)`: 한 번에 너무 많은 글을 처리하지 않게. 화면은 한 페이지(20개)씩 고르므로 넉넉하다.
- 검사는 `requestValidator.validate(request)`로 주인 확인 **뒤에** 한다. `@Valid`를 매개변수에 붙이면 메서드 전에 검사해 400이 401보다 먼저 난다([22](./22-bean-validation.md)).
- DELETE에 본문을 싣는다. HTTP는 DELETE 본문의 의미를 정하지 않아 쓰지 않는 서버·프록시도 있지만, contracts가 이 모양으로 정했고 Spring은 `@RequestBody`로 읽는다.

### 5.7 화면: `pages/manage/ManagePostsPage.tsx`

```tsx
const [params, setParams] = useSearchParams()
const status = params.get('status') ?? ''
const categoryId = params.get('categoryId') ?? ''
const q = params.get('q') ?? ''
const page = Number(params.get('page') ?? '1')
...
/** 거르기 조건을 바꾸면 1페이지부터. 빈 값은 주소에서 뺀다 */
function filter(name: string, value: string) {
  const next = new URLSearchParams(params)
  if (value) {
    next.set(name, value)
  } else {
    next.delete(name)
  }
  next.delete('page')
  setParams(next)
}
```

- 거르기 조건을 React 상태가 아니라 **주소의 쿼리 문자열**에 둔다(블로그 안 검색과 같은 방식, [25](./25-react-forms-data.md)). 새로고침하거나 뒤로 가기를 해도 같은 목록이고, 주소를 공유할 수 있다. Thymeleaf로 치면 `<form method="get">`의 값이 주소에 붙고 컨트롤러가 `@RequestParam`으로 읽는 것과 같다.
- `setParams`로 주소가 바뀌면 `params`가 바뀌고 → `load`가 새로 만들어지고 → `useEffect([load])`가 다시 불러온다.
- 조건을 바꾸면 `page`를 지운다. 3페이지를 보다가 조건을 바꾸면 결과가 1페이지밖에 없을 수 있기 때문이다.

```tsx
const pageIds = posts?.content.map((post) => post.id) ?? []
const allSelected = pageIds.length > 0 && pageIds.every((id) => selected.includes(id))
...
<input type="checkbox" aria-label="이 페이지 모두 선택" checked={allSelected}
       onChange={() => setSelected(allSelected ? [] : pageIds)} />
```

- 고른 글은 번호 배열 `selected`에 둔다. 체크박스 하나가 그 배열에 번호를 넣고 뺀다(`toggle`).
- "모두 선택"은 **이 페이지의** 글만이다. 다른 페이지로 가면(`load` 뒤) 고른 것을 비운다. 보이지 않는 글이 함께 지워지는 사고를 막는다.
- 일괄 처리 뒤에는 목록을 다시 불러온다. 비공개로 바꾼 글이 "공개만 보기" 조건에서 빠지는 것처럼, 결과가 조건에 따라 달라지기 때문이다.
- 삭제는 `window.confirm`으로 개수를 보여 주고 묻는다(목업 "선택한 글 2개를 삭제할까요?").
- 숨긴 글은 제목 옆에 "숨김: 저작권 침해" 칩. 상태·공개 범위는 영어 코드를 한국어 이름으로 바꾸는 표(`STATUS_LABEL`)로 보여 준다.

### 5.8 테스트 `ManagePostIntegrationTest`

| 테스트 | 확인하는 것 |
| --- | --- |
| `onlyOwnerCanUseIt` | 세 API 모두 비회원 401, 다른 회원 403(틀린 status를 보내도 403이 먼저) |
| `listsAllMyPostsNewestFirstWithStateAndBlindReason` | 임시저장·비공개·숨긴 글 포함 4개(지운 글·남의 글 없음), COALESCE 정렬, 숨김 사유 |
| `filtersByStatusVisibilityCategoryAndTitle` | 상태·공개 범위·상위 카테고리(하위 포함)·하위·미분류(0)·`q=100%` 이스케이프·빈 검색어, 틀린 status 400, 남의 카테고리 404 |
| `pagesOfTwenty` | 25개면 2페이지에 5개 |
| `bulkVisibilityChangesOnlyMyPosts` | 남의 글·지운 글·없는 번호 섞어 보내면 2개만, 남의 글 그대로, 바뀐 글이 블로그 목록에서 바로 빠짐, 구독자 공개·빈 목록 400 |
| `bulkDeleteRemovesPostsWithTheirCommentsAndLikes` | 2개 삭제, 댓글 소프트 삭제·공감 삭제, 남의 글 그대로, 다시 지우면 0 |

## 6. 자주 하는 실수와 함정

- **조건을 문자열 SQL로 이어 붙인다.** `"AND title LIKE '%" + q + "%'"`는 SQL 주입. Specification이나 바인딩 변수로.
- **`Pageable`에 정렬을 넣고 Specification에도 정렬을 건다.** `Pageable`의 정렬이 Specification의 정렬을 덮는다. 한 곳에서만.
- **개수 쿼리에 정렬을 건다.** `query.getResultType()`으로 구분한다.
- **NULL이 섞인 칸으로만 정렬한다.** MySQL은 내림차순에서 NULL을 맨 뒤로 보낸다. 임시저장 글이 늘 맨 아래로 간다. `COALESCE`로 대신할 값을 준다.
- **enum 쿼리 파라미터를 그대로 받는다.** 틀린 값의 400이 401·403보다 먼저 난다(이 프로젝트의 순서와 어긋남).
- **일괄 처리에서 번호로 찾은 뒤 권한을 따로 검사한다.** 검사를 빠뜨리면 남의 글이 바뀐다(IDOR, [38](./38-member-profile-update.md) 3.3). "내 글 중에서" 찾는다.
- **일괄 처리를 글마다 다른 트랜잭션으로 한다.** 중간에 실패하면 반만 바뀐다.
- **일괄 삭제를 따로 구현한다.** 글 하나 삭제에 있던 댓글·공감·알림 처리를 빠뜨리기 쉽다. 같은 메서드를 부른다.
- **화면의 "모두 선택"이 다른 페이지의 글까지 포함한다.** 보이지 않는 글이 지워진다.
- **LIKE 이스케이프를 복사해 쓴다.** 고칠 때 한쪽을 빠뜨린다. 공용으로.

## 7. 직접 해 보기

준비: `docker compose up -d`, 코드 저장소 루트에서 `./scripts/build-frontend.sh && ./mvnw spring-boot:run`, 블로그 주인으로 로그인.

### 7.1 화면

1. `http://{주소}.blog.test:8080/manage/posts`를 연다. 상태·카테고리를 바꾸면 주소가 `?status=PUBLISHED&categoryId=3`처럼 바뀌는지 본다. 그 주소를 새 탭에 붙여 넣어도 같은 목록이다.
2. 글 두 개를 고르고 "비공개로" → [적용]. 다른 브라우저(비회원)로 블로그 메인을 열어 두 글이 없는지 본다.
3. 제목 검색에 `%`를 넣어 본다. 모든 글이 아니라 `%`가 든 제목만 나온다.

### 7.2 API

```bash
H="Host: {주소}.blog.test"; X="X-Requested-With: XMLHttpRequest"
curl -s -b jar.txt -H "$H" "localhost:8080/api/manage/posts?status=PUBLISHED&page=1" | python3 -m json.tool | head -30
curl -s -b jar.txt -H "$H" -H "$X" -H "Content-Type: application/json" -X PATCH \
     -d '{"postIds":[12,15,999999],"visibility":"PRIVATE"}' localhost:8080/api/manage/posts     # {"updatedCount":2}
curl -s -H "$H" "localhost:8080/api/manage/posts?status=BOGUS" -o /dev/null -w '%{http_code}\n'  # 비회원이라 401 (400 아님)
```

### 7.3 SQL 보기

`application-dev.yml`에 `spring.jpa.show-sql: true`를 잠시 켜고 목록을 부른다. `order by coalesce(p1_0.published_at,p1_0.updated_at) desc`가 붙은 내용 쿼리와, 정렬이 없는 `select count(...)` 쿼리 두 개가 나오는지 본다.

### 7.4 테스트

```bash
./mvnw test -Dtest=ManagePostIntegrationTest
```

## 8. 확인 문제

1. 동적 쿼리를 문자열로 이어 붙이지 않고 Specification으로 만드는 이유 두 가지는?
<details><summary>답</summary>AND·괄호 위치를 틀리기 쉬운 문자열 조립을 피하고, 사용자 값이 바인딩 변수로 가서 SQL 주입이 생기지 않는다. 조건이 없으면 그냥 붙이지 않으면 된다.</details>

2. `findAll(spec, pageable)`이 쿼리를 두 번 보내는 이유는?
<details><summary>답</summary>그 페이지의 글(LIMIT·OFFSET)을 가져오는 내용 쿼리와, 전체 페이지 수를 알기 위한 COUNT 쿼리가 따로 필요하기 때문이다. 같은 Specification이 두 쿼리에 쓰인다.</details>

3. 임시저장과 발행 글을 한 목록에서 정렬하려고 쓴 식과, 그것을 `Sort.by`로 못 쓰는 이유는?
<details><summary>답</summary><code>ORDER BY COALESCE(published_at, updated_at) DESC, id DESC</code>. Sort.by는 칸 이름만 받아 식을 표현하지 못한다. 그래서 Specification 안에서 Criteria로 직접 orderBy를 걸고, Pageable에는 정렬을 넣지 않는다.</details>

4. `newestFirst()`가 `query.getResultType()`을 보는 이유는?
<details><summary>답</summary>같은 Specification이 COUNT 쿼리에도 쓰이기 때문이다. 결과가 Long인 개수 쿼리에는 정렬을 걸지 않는다.</details>

5. `status`를 enum이 아니라 String으로 받는 이유는?
<details><summary>답</summary>enum으로 받으면 틀린 값의 변환 오류(400)가 메서드 첫 줄의 주인 확인(401·403)보다 먼저 난다. 상태 코드 순서 401 → 403 → 400을 지키려고 주인 확인 뒤에 직접 바꾼다.</details>

6. 일괄 변경에 남의 글 번호가 섞여 있으면 어떻게 되나? 별도 권한 검사 없이 안전한 이유는?
<details><summary>답</summary>"이 블로그의 지우지 않은 글" 중에서 번호로 찾으므로 남의 글은 결과에 없고 바뀌지 않는다. updatedCount에도 세지 않는다. 고칠 수 있는 범위 안에서만 찾기 때문에 권한 검사를 빠뜨릴 틈이 없다.</details>

7. 일괄 삭제가 `PostService.delete`를 글마다 부르는 이유와, 그래도 한 트랜잭션인 이유는?
<details><summary>답</summary>글 하나 삭제의 규칙(알림·공감 삭제, 댓글 소프트 삭제)을 그대로 쓰려고. PostService.delete의 @Transactional은 기본 전파 REQUIRED라 바깥 ManagePostService.delete의 트랜잭션에 합류한다. 중간에 실패하면 모두 되돌아간다.</details>

8. 화면의 거르기 조건을 React 상태가 아니라 주소에 둔 이점은?
<details><summary>답</summary>새로고침·뒤로 가기에도 같은 목록이 나오고, 주소를 공유하거나 즐겨찾기할 수 있다. 서버 렌더링에서 GET 폼 값이 주소에 붙는 것과 같다.</details>

9. "이 페이지 모두 선택"이 다른 페이지 글을 포함하지 않게 한 이유는?
<details><summary>답</summary>보이지 않는 글까지 한 번에 지워지는 사고를 막기 위해서다. 페이지를 옮기면 선택도 비운다.</details>

10. LIKE 이스케이프를 `global/web/LikePatterns`로 옮긴 이유는?
<details><summary>답</summary>검색과 내 글 관리가 같은 규칙을 쓰므로 한 곳에 두어 함께 고치게 하고, 한 기능 패키지가 다른 기능 패키지(search)에 기대지 않게 하려고.</details>

## 9. 더 읽을거리

- Spring Data JPA 레퍼런스, "Specifications", "Paging and Sorting"
- Jakarta Persistence 명세, Criteria API(`CriteriaBuilder.coalesce`, `CriteriaQuery.orderBy`, `getResultType`)
- MySQL 8.4 레퍼런스, "Flow Control Functions"(`COALESCE`), "ORDER BY Optimization"(NULL 정렬 순서)
- OWASP, "Insecure Direct Object Reference Prevention Cheat Sheet"
- React Router 문서, `useSearchParams`
- 대량 일괄 처리: JPQL 일괄 UPDATE와 변경 감지의 차이([27](./27-soft-delete-bulk-update.md)), 배치 크기(`hibernate.jdbc.batch_size`)
