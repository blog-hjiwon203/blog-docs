# 39. 계층 데이터: 카테고리 2단계와 주제

> 관련 스텝: [스텝 9](../step-09.md) (T060, T056, T064) · 관련 개념: [06-jpa-entity-mapping](./06-jpa-entity-mapping.md), [16-authorization-visibility](./16-authorization-visibility.md), [03-flyway-migration](./03-flyway-migration.md), [31-tags-many-to-many](./31-tags-many-to-many.md), [35-spring-cache-redis](./35-spring-cache-redis.md), [36-ranking-aggregation](./36-ranking-aggregation.md)

## 1. 이 문서로 배우는 것

- **자기 참조(self-reference)**: 카테고리 표가 자기 자신을 가리키는 `parent_id`로 나무(트리)를 만드는 법
- 깊이를 **2단계로 제한**하는 이유와 검사하는 곳
- "같은 자리에서만 이름이 겹치면 안 된다"를 DB로 지키는 법: **계산 칸(generated column)** `parent_key`와 UNIQUE
- 트리를 쿼리 두 번 + 메모리 조립으로 만들기, 상위 글 수에 하위 글 수 더하기
- 상위 카테고리를 누르면 하위 글까지 나오게 하는 조건(`category = A OR category.parent = A`)
- 비공개 상위 아래의 하위도 숨기기
- 카테고리와 **별개**인 분류 축 "주제": 고정 10개를 enum으로, 화면 이름은 enum 필드로
- 주제별 글: 인기 점수 순 6개, 모자라면 최신 글로 채우기, 주제마다 다른 캐시 키

**먼저 알면 좋은 것**: `@ManyToOne`과 지연 로딩([06](./06-jpa-entity-mapping.md)), 카테고리 트리와 글 수(스텝 4의 `CategoryTreeService`), 가시성 조건([16](./16-authorization-visibility.md)), 인기 점수와 캐시([35](./35-spring-cache-redis.md), [36](./36-ranking-aggregation.md)).

## 2. 왜 필요한가

글이 쌓이면 "개발" 하나로는 부족하다. "개발 > Spring", "개발 > JPA"처럼 나누고 싶다. 명세 CAT-03은 **2단계**까지다.

> **전제** 상위 'A'와 하위 'A-1', **행동** 'A'를 누른다, **결과** 'A-1' 글도 함께 나오고 글 수도 합친 값이다. 카테고리는 2단계까지만 만들 수 있다. (spec US5 시나리오 3)

한편 홈은 블로그와 상관없이 "IT·개발", "여행" 같은 **주제**로 글을 모아 보여 준다(HOME-03). 카테고리는 블로그 주인이 자기 블로그 안에서 마음대로 만드는 것이라 블로그마다 다르다. 서비스 전체에서 같은 기준으로 묶으려면 모두가 같은 목록에서 고르는 분류가 따로 필요하다. 그것이 주제(POST-11)다.

| | 카테고리 | 주제 |
| --- | --- | --- |
| 누가 만드나 | 블로그 주인이 자유롭게 | 서비스가 정한 고정 10개 |
| 범위 | 블로그 하나 안 | 서비스 전체 |
| 모양 | 2단계 나무 | 목록 하나 |
| 쓰이는 곳 | 블로그 사이드바, 블로그 글 목록 | 홈 주제별 글 |
| 저장 | `category` 표 + `post.category_id` | `post.topic` 칸(문자열) |

## 3. 기본 개념

### 3.1 자기 참조로 나무 만들기

```sql
CREATE TABLE category (
    id BIGINT NOT NULL AUTO_INCREMENT,
    parent_id BIGINT COMMENT '상위 카테고리-----NULL 또는 1단계 상위',
    blog_id BIGINT NOT NULL,
    name VARCHAR(30) NOT NULL,
    sort_order INT NOT NULL DEFAULT 0,
    ...
);
```

| id | parent_id | name |
| --- | --- | --- |
| 1 | NULL | 개발 |
| 2 | 1 | Spring |
| 3 | 1 | JPA |
| 4 | NULL | 여행 |

`parent_id`가 같은 표의 `id`를 가리킨다. NULL이면 최상위다. 이것을 **인접 목록(adjacency list)** 방식이라 한다. 가장 단순한 트리 저장법이고, 깊이가 얕을 때 잘 맞는다.

JPA에서는 자기 자신을 가리키는 `@ManyToOne`이다.

```java
@ManyToOne(fetch = FetchType.LAZY)
@JoinColumn(name = "parent_id")
private Category parent;
```

### 3.2 왜 2단계로 막나

깊이에 제한이 없으면:

- "이 카테고리 아래 **모든** 글"을 구하려면 자손을 끝까지 따라가야 한다. SQL로는 재귀 쿼리(`WITH RECURSIVE`)가 필요하다.
- 사이드바·선택 상자가 깊어져 화면이 복잡해진다.

2단계면 "A의 글 + A의 바로 아래 글"이 곧 "A 아래 모든 글"이다. 조건 하나(`category = A OR category.parent = A`)로 끝난다. 티스토리도 2단계다.

제한은 **추가할 때** 검사한다. 고르는 상위가 이미 하위면(상위가 있으면) 3단계가 되므로 409 `CATEGORY_DEPTH`. 나중에 드래그로 상하위를 바꾸는 기능(CAT-04, 백로그)도 같은 검사를 해야 한다(하위가 있는 카테고리를 다른 카테고리 아래로 옮기면 3단계).

### 3.3 "같은 자리에서만" 이름이 겹치면 안 된다

"개발 > 기타"와 "여행 > 기타"는 둘 다 있어도 된다. 최상위 "개발"과 그 아래 "개발"도 괜찮다. 막을 것은 **같은 상위 아래**(또는 둘 다 최상위)에서 같은 이름이다. 즉 UNIQUE(blog_id, parent_id, name)이다.

그런데 MySQL의 UNIQUE는 **NULL을 서로 다른 값으로 본다**. 최상위는 `parent_id`가 NULL이라, (블로그 3, NULL, "개발")이 두 번 들어가도 UNIQUE가 막지 못한다.

ERD는 이것을 **계산 칸**으로 풀었다.

```sql
parent_key BIGINT GENERATED ALWAYS AS (IFNULL(parent_id, 0)) STORED NOT NULL,
CONSTRAINT uk_category_blog_id_parent_key_name UNIQUE (blog_id, parent_key, name)
```

- `GENERATED ALWAYS AS (식)`: 다른 칸에서 DB가 계산해 채우는 칸. 직접 넣을 수 없다.
- `IFNULL(parent_id, 0)`: 최상위면 0. 그래서 최상위끼리도 같은 값(0)으로 비교된다.
- `STORED`: 계산한 값을 실제로 저장한다(인덱스·UNIQUE에 쓰려면 필요).

JPA 엔티티는 이 칸을 **매핑하지 않는다**(DB가 채우므로). `ddl-auto=validate`는 엔티티에 있는 칸이 표에 있는지만 보므로 엔티티에 없는 칸이 있어도 괜찮다.

자바도 같은 규칙으로 미리 검사한다(친절한 409를 주려고). 대소문자는 DB 정렬 규칙처럼 무시한다([31](./31-tags-many-to-many.md) 3.5). 그래도 동시에 같은 이름을 넣으면 UNIQUE가 마지막으로 막고, 그 예외를 409로 바꾼다.

### 3.4 트리를 읽는 법: 쿼리 두 번 + 메모리 조립

트리를 JPA 연관(`List<Category> children`)으로 따라가면 상위마다 하위를 읽는 쿼리가 나간다(N+1). 이 프로젝트는 스텝 4부터 이렇게 했다.

1. 블로그의 카테고리를 **모두** 한 번에 읽는다(정렬 순서대로).
2. 카테고리별 글 수를 GROUP BY로 한 번에 센다(보는 사람 기준).
3. 메모리에서 `parent_id`로 묶어 나무를 만든다. 상위의 글 수 = 자기 글 수 + 하위 글 수의 합.

블로그 하나의 카테고리는 많아야 수십 개라 전부 읽어도 가볍다. 스텝 4에서 이 조립을 미리 만들어 두어서, 스텝 9에서는 **하위를 만들 수 있게만** 하면 사이드바·글 수가 그대로 동작했다.

### 3.5 주제는 enum으로

주제는 고정 10개고 코드가 그 값을 알아야 한다(주제별 쿼리, 화면 탭). 그래서 DB 표가 아니라 자바 **enum**으로 두고, DB에는 이름 글자(`IT_DEV`)를 저장한다(`EnumType.STRING`, CLAUDE.md). DB에는 CHECK 제약이 있어서 다른 글자는 들어가지 못한다.

```sql
CONSTRAINT ck_post_topic CHECK (topic IS NULL OR topic IN ('IT_DEV', 'TRAVEL', ...))
```

화면 이름("IT·개발")은 enum 상수에 필드로 붙인다. 이름이 바뀌어도 저장된 값(`IT_DEV`)은 그대로다. `ORDINAL`(순서 번호)로 저장하지 않는 이유와 같다. 중간에 주제 하나를 끼우면 번호가 밀려 모든 글의 주제가 바뀐다.

### 3.6 주제별 글: 인기 순 + 최신으로 채우기

> 그 주제의 글 6개를 HOME-02와 같은 인기 점수 순으로 보여 준다. 6개가 안 되면 그 주제의 최신 글로 채운다. (HOME-03)

1. 인기 점수 쿼리([36](./36-ranking-aggregation.md))에 `AND p.topic = :topic`만 더해 그 주제의 순위를 구한다(5분 캐시, 주제마다 키가 다름).
2. 볼 수 있는 글을 순위대로 6개까지.
3. 모자라면 그 주제의 최신 글을 **앞에서 고른 글을 빼고** 모자란 만큼 더한다.

최신 글로 채우는 부분은 캐시하지 않는다. `idx_post_topic_feed(topic, status, visibility, published_at)` 인덱스로 몇 개만 읽어 가볍고, 새 글이 바로 보이는 편이 낫다.

## 4. 동작 원리

### 4.1 하위 카테고리 추가

```
myblog.blog.test/manage/categories  (CategoriesPage)
  "개발" 줄의 [하위 추가] → "Spring" → [추가]
  POST /api/categories { name: "Spring", parentId: 1 }
    CategoryController.create        주인 확인(401·403) → 이름 1~30자(400)
    CategoryService.create
      parent(blog, 1)                이 블로그의 카테고리가 아니면 400(parentId)
                                     이미 하위면 409 CATEGORY_DEPTH
      nameTaken(blog, 개발, "Spring") 같은 상위 아래 같은 이름이면 409 NAME_TAKEN
      sortOrder = 그 상위의 하위 중 가장 큰 순서 + 1
      saveAndFlush                   동시에 같은 이름이면 UNIQUE(blog_id, parent_key, name) → 409
  ← 201 { id: 2, name: "Spring", parentId: 1, sortOrder: 0 }
```

### 4.2 상위 카테고리 글 목록

```
GET /api/posts?categoryId=1
  PostQueryService.inCategory
    1번이 이 블로그의 카테고리인가, 주인이 아니면 숨긴(비공개) 카테고리가 아닌가 → 아니면 404
    WHERE ... AND (post.category_id = 1 OR category.parent_id = 1)
```

이 조건은 스텝 4부터 있었다(하위가 생길 것을 미리 넣어 둠). 스텝 9에서 비공개 **상위** 아래의 하위 카테고리 번호로 직접 열어도 404가 되게 고쳤다. 사이드바 트리가 비공개 상위의 하위까지 숨기는 것과 규칙을 맞췄다. 지금은 카테고리를 비공개로 바꾸는 기능(CAT-05)이 아직 없어서 화면에서는 볼 일이 없다.

## 5. 이 프로젝트에서는

### 5.1 `category/application/CategoryService.create`

```java
@Transactional
public Category create(Blog blog, String rawName, Long parentId) {
    String name = rawName.trim();
    Category parent = parent(blog, parentId);
    if (nameTaken(blog, parent, name)) {
        throw new BusinessException(ErrorCode.NAME_TAKEN);
    }
    int sortOrder = parent == null
            ? categoryRepository.findMaxRootSortOrder(blog.getId()) + 1
            : categoryRepository.findMaxChildSortOrder(parent.getId()) + 1;
    return saveUnique(Category.create(blog, parent, name, sortOrder));
}

private Category parent(Blog blog, Long parentId) {
    if (parentId == null) {
        return null;
    }
    Category parent = categoryRepository.findById(parentId)
            .filter(category -> category.belongsTo(blog))
            .orElseThrow(() -> BusinessException.invalidField("parentId", "상위 카테고리를 찾을 수 없습니다."));
    if (parent.isChild()) {
        throw new BusinessException(ErrorCode.CATEGORY_DEPTH);
    }
    return parent;
}

/** 같은 자리(parent가 null이면 최상위)에 같은 이름이 있는가. 대소문자는 DB 정렬 규칙대로 같게 본다. */
private boolean nameTaken(Blog blog, Category parent, String name) {
    return parent == null
            ? categoryRepository.existsByBlogIdAndParentIsNullAndName(blog.getId(), name)
            : categoryRepository.existsByParentIdAndName(parent.getId(), name);
}
```

- `parentId == null`이면 최상위(스텝 5와 같음).
- `.filter(category -> category.belongsTo(blog))`: **남의 블로그 카테고리 번호**를 넣어 그 아래에 내 카테고리를 만들지 못하게 한다([38](./38-member-profile-update.md) 3.3의 IDOR과 같은 생각). 본문의 칸이 틀린 것이라 404가 아니라 400(`parentId`)으로 했다. 글 저장의 `categoryId`와 같은 방식이다.
- `parent.isChild()`: 상위가 이미 하위면 3단계. `Category`에 더한 메서드(`parent != null`).
- `nameTaken`: 최상위끼리, 같은 상위의 하위끼리만 비교(3.3).
- 순서: 그 자리의 맨 아래. 하위 순서는 하위끼리 센다.
- 이름 바꾸기(`rename`)도 같은 `nameTaken(blog, category.getParent(), name)`으로 바꿨다. 스텝 5 코드는 최상위끼리만 비교해서, 하위가 생기면 "다른 상위 아래의 같은 이름"으로도 409가 났을 것이다.

### 5.2 요청과 컨트롤러

```java
public record CategoryRequest(
        @NotBlank(message = "카테고리 이름을 입력해 주세요.")
        @Size(max = 30, message = "카테고리 이름은 30자까지입니다.")
        String name,

        Long parentId) {
}
```

스텝 5에서는 `parentId`에 `@Null`("하위 카테고리는 아직 만들 수 없습니다")을 붙여 막아 두었다. "아직 없는 기능의 값은 조용히 버리지 않고 400"이라는 이 프로젝트의 규칙이다. 스텝 9에서 그것을 풀었다. 대신 **이름 바꾸기**(`PATCH`)에서 `parentId`를 보내면 400이다. 상위를 바꾸는 것은 드래그 순서 바꾸기(CAT-04)의 일이라서다.

응답 `CategoryCreatedResponse`에 `parentId`를 더했다.

### 5.3 트리 (스텝 4 코드, 바뀌지 않음)

`category/application/CategoryTreeService.tree`가 3.4의 방식이다. 이번 스텝에서 고치지 않았다. 하위가 생기자 사이드바·`GET /api/categories`의 `children`과 상위 글 수 합산이 그대로 동작했다. 테스트 `parentListAndCountIncludeSubcategoryPosts`가 상위 글 수 2(상위 1 + 하위의 공개 글 1, 비공개 글은 빠짐)를 확인한다.

### 5.4 화면

- 카테고리 관리(`CategoriesPage`): 최상위 줄마다 [하위 추가]. 하위 줄은 `└`와 들여쓰기로 보이고 [하위 추가]가 없다(2단계). 이 구분은 `child` 속성으로 넘긴다.
- 하위가 있는 상위를 지우면 409 `CATEGORY_HAS_CHILDREN` → "하위부터 지워 주세요".
- 글쓰기·글 관리의 카테고리 선택 상자: 상위 다음에 그 하위를 `└ Spring`으로 넣는다. `<select>` 안에는 다른 태그를 넣을 수 없어서 줄바꿈 없는 공백(` `)으로 들여쓴다. 보통 공백은 앞쪽이 지워져 보인다.

```tsx
{categories?.categories.flatMap((category) => [
  <option key={category.id} value={category.id}>{category.name}</option>,
  ...category.children.map((child) => (
    <option key={child.id} value={child.id}>{`  └ ${child.name}`}</option>
  )),
])}
```

`flatMap`: 상위 하나마다 [상위, 하위1, 하위2…] 배열을 만들고, 그 배열들을 한 줄로 이어 붙인다.

### 5.5 주제: `post/domain/Topic.java`와 `GET /api/topics`

```java
public enum Topic {
    IT_DEV("IT·개발"),
    TRAVEL("여행"),
    ...
    EDUCATION("교육·학습");

    private final String displayName;

    Topic(String displayName) {
        this.displayName = displayName;
    }

    public String getDisplayName() {
        return displayName;
    }
}
```

- enum 상수도 생성자와 필드를 가질 수 있다. `IT_DEV("IT·개발")`은 생성자에 이름을 넘긴 것이다.
- `TopicController`가 `Topic.values()`를 `[{ code: "IT_DEV", name: "IT·개발" }, ...]`로 돌려준다. 글쓰기 화면의 주제 선택 상자와 홈 탭이 같이 쓴다. 이름을 화면 코드에 따로 적지 않아서 한 곳만 고치면 된다.
- 글 저장 본문의 `topic`은 스텝 5부터 받고 있었다(글 저장 DTO의 `Topic topic`). 화면에 선택 상자가 없었을 뿐이다. "주제 없음"은 `null`.
- 모르는 주제 글자(`"SPORTS"`)를 보내면 JSON을 enum으로 바꾸다 실패해 400이다(`TopicIntegrationTest`).

### 5.6 주제별 글: `HomeService.topicPosts`

```java
@Transactional(readOnly = true)
public List<Post> topicPosts(Topic topic) {
    List<Post> ranked = visibleInRankOrder(popularRanking.topicSnapshot(topic), TOPIC_SIZE);
    if (ranked.size() >= TOPIC_SIZE) {
        return ranked;
    }
    List<Long> rankedIds = ranked.stream().map(Post::getId).toList();
    Specification<Post> latest = PostSpecifications.visibleTo(null, LocalDateTime.now(clock))
            .and((root, query, cb) -> cb.equal(root.get("topic"), topic));
    if (!rankedIds.isEmpty()) {
        latest = latest.and((root, query, cb) -> cb.not(root.get("id").in(rankedIds)));
    }
    List<Post> filler = postRepository.findBy(latest, query -> query.sortBy(LATEST).project("blog", "category")
            .limit(TOPIC_SIZE - ranked.size()).all());
    return Stream.concat(ranked.stream(), filler.stream()).toList();
}
```

- `popularRanking.topicSnapshot(topic)`: 홈 인기 글과 같은 `@Cacheable`이고 키만 주제별이다(`key = "#topic.name()"` → Redis `blog:topicPosts::IT_DEV`, [35](./35-spring-cache-redis.md)). 후보는 30개.
- `visibleInRankOrder`: 홈 인기 글에서 쓰던 "캐시된 순위 → 지금 볼 수 있는 글만 순위대로"를 메서드로 뽑아 두 곳이 같이 쓴다.
- `cb.not(root.get("id").in(rankedIds))`: 이미 고른 글은 빼고 채운다(같은 글이 두 번 나오지 않게). 목록이 비면 `IN ()`이 SQL 오류라 비었을 때는 이 조건을 붙이지 않는다.
- `Stream.concat`: 두 목록을 이어 붙인다.
- 컨트롤러는 `/api/home/topics/{topic}`의 글자를 enum 이름과 **정확히** 비교해 찾고, 없으면 404다. `health`(소문자)도 404다. `@PathVariable Topic topic`으로 받으면 Spring이 바꾸다 실패해 400이 나는데, "없는 주제 = 없는 자원"이라 404가 맞다고 봤다.
- 홈 화면(`HomePage`의 `TopicSection`)은 주제 탭(목업의 `tabs`)과 카드 6개(`grid-cards`)다. 처음엔 첫 탭(IT·개발).

### 5.7 테스트

| 테스트 | 확인하는 것 |
| --- | --- |
| `CategoryIntegrationTest.subcategoriesGoUnderTheirParentInOrder` | 하위가 그 상위 아래 순서대로, 상위와 같은 이름의 하위는 됨 |
| `…subcategoryRulesDepthNamesAndParentOwnership` | 3단계 409, 같은 상위 아래 같은 이름(대소문자 무시) 409, 다른 상위 아래는 됨, 하위 이름 바꾸기도 같은 자리에서만, 이름 변경의 parentId 400, 남의 블로그 상위 400 |
| `…parentListAndCountIncludeSubcategoryPosts` | 상위 목록에 하위 글, 상위 글 수 = 합 |
| `TopicIntegrationTest` | 주제 10개와 이름, 글 주제 고르기·바꾸기·지우기(null), 모르는 주제 400 |
| `HomeTopicIntegrationTest` | 인기 순 3개 + 최신 3개 = 6, 다른 주제·주제 없음·비공개 글 제외, 모르는 주제·소문자 404 |

## 6. 자주 하는 실수와 함정

- **깊이 검사를 화면에만 둔다.** API를 직접 부르면 3단계가 생긴다. 서버가 검사한다.
- **UNIQUE에 NULL 칸을 넣고 안심한다.** MySQL은 NULL끼리 중복을 허용한다. 최상위 이름 중복이 들어간다. 계산 칸(`IFNULL(parent_id, 0)`)으로.
- **이름 중복을 블로그 전체에서 검사한다.** "개발 > 기타"와 "여행 > 기타"를 막아 버린다. 같은 자리끼리만.
- **상위 번호를 그대로 믿는다.** 남의 블로그 카테고리 아래에 만들어진다. "내 블로그 카테고리 중에서" 찾는다.
- **트리를 연관 컬렉션으로 따라가며 읽는다.** 상위마다 쿼리(N+1). 한 번에 읽고 메모리에서 묶는다.
- **상위 목록에 하위 글을 빼먹는다.** `category = A`만 보면 하위 글이 안 나온다. `OR category.parent = A`.
- **주제를 `EnumType.ORDINAL`로 저장한다.** 주제 하나를 중간에 넣으면 기존 글의 주제가 모두 밀린다.
- **화면 이름을 프론트에 따로 적는다.** 서버와 이름이 갈라진다. `GET /api/topics` 하나로.
- **채우는 최신 글에서 이미 고른 글을 빼지 않는다.** 같은 글이 두 번 나온다.
- **`IN ()`에 빈 목록을 넘긴다.** SQL 오류. 비었으면 조건을 붙이지 않는다.

## 7. 직접 해 보기

준비: 코드 저장소 루트에서 `./scripts/build-frontend.sh && ./mvnw spring-boot:run`, 블로그 주인으로 로그인.

### 7.1 하위 카테고리 (확인할 것)

1. `/manage/categories`에서 "개발"을 만들고 [하위 추가]로 "Spring"을 만든다.
2. 글을 "└ Spring"으로 하나, "개발"로 하나 발행한다.
3. 블로그 사이드바의 "개발 (2)"를 누르면 두 글이 모두 나온다. "Spring (1)"은 하나.
4. "Spring"에서 [하위 추가]가 없는지, API로 Spring 아래에 만들면 409인지 본다.

```bash
curl -s -b jar.txt -H "Host: {주소}.blog.test" -H "X-Requested-With: XMLHttpRequest" -H "Content-Type: application/json" \
     -X POST -d '{"name":"Boot","parentId":{Spring 번호}}' localhost:8080/api/categories
# {"code":"CATEGORY_DEPTH","message":"카테고리는 2단계까지 만들 수 있습니다."}
```

### 7.2 DB의 계산 칸

```bash
docker exec -it blog-mysql mysql -ublog -pblog blog -e "SELECT id, blog_id, parent_id, parent_key, name FROM category ORDER BY blog_id, parent_key, sort_order;"
# 내 블로그 번호(위 결과의 blog_id)로 같은 이름의 최상위를 두 번 넣어 본다
docker exec -it blog-mysql mysql -ublog -pblog blog -e "INSERT INTO category (blog_id, name) VALUES ({블로그 번호}, '중복시험'), ({블로그 번호}, '중복시험');"
# Duplicate entry ... for key ...uk_category_blog_id_parent_key_name 오류가 나고 두 줄 모두 들어가지 않는다
```

### 7.3 주제

1. 글쓰기 화면의 "주제"에서 "여행"을 고르고 발행한다.
2. 홈의 "주제별 글"에서 "여행" 탭을 누르면 그 글이 보인다. 다른 회원으로 그 글에 공감·댓글을 달고 캐시를 지우면(`redis-cli del 'blog:topicPosts::TRAVEL'`) 인기 순으로 앞에 온다.

```bash
curl -s -H "Host: blog.test" localhost:8080/api/topics | python3 -m json.tool | head
curl -s -H "Host: blog.test" localhost:8080/api/home/topics/TRAVEL | python3 -m json.tool | head -20
docker exec blog-redis redis-cli keys 'blog:topicPosts*'
```

### 7.4 테스트

```bash
./mvnw test -Dtest='CategoryIntegrationTest,TopicIntegrationTest,HomeTopicIntegrationTest'
```

## 8. 확인 문제

1. 인접 목록(parent_id) 방식으로 2단계 카테고리를 저장할 때, "A 아래 모든 글"을 구하는 조건은? 깊이에 제한이 없으면 무엇이 필요해지나?
<details><summary>답</summary><code>category = A OR category.parent = A</code>. 깊이 제한이 없으면 자손을 끝까지 따라가야 해서 재귀 쿼리(WITH RECURSIVE)나 다른 저장 방식이 필요하다.</details>

2. UNIQUE(blog_id, parent_id, name)만으로 최상위 이름 중복을 막지 못하는 이유와 이 프로젝트의 해결은?
<details><summary>답</summary>MySQL UNIQUE는 NULL끼리를 서로 다른 값으로 본다. 최상위는 parent_id가 NULL이라 중복이 들어간다. IFNULL(parent_id, 0)인 계산 칸 parent_key를 두고 UNIQUE(blog_id, parent_key, name)으로 막는다.</details>

3. 엔티티에 `parent_key`를 매핑하지 않아도 되는 이유는?
<details><summary>답</summary>DB가 계산해 채우는 칸이라 애플리케이션이 넣지 않는다. ddl-auto=validate는 엔티티에 있는 칸이 표에 있는지만 보므로 엔티티에 없는 칸이 있어도 된다.</details>

4. 하위 카테고리를 만들 때 409 `CATEGORY_DEPTH`가 나는 경우는?
<details><summary>답</summary>고른 상위가 이미 하위 카테고리일 때(상위가 있을 때). 그 아래에 만들면 3단계가 된다.</details>

5. 이름 중복 검사를 "같은 자리"로 바꾸면서 이름 바꾸기(rename)도 고친 이유는?
<details><summary>답</summary>예전 코드는 최상위끼리만 비교했다. 하위가 생기면 하위 이름을 바꿀 때 다른 상위 아래의 같은 이름이나 최상위 이름과 잘못 비교된다. 그 카테고리의 상위 아래에서만 비교해야 한다.</details>

6. 트리를 쿼리 두 번 + 메모리 조립으로 만드는 이유는?
<details><summary>답</summary>연관 컬렉션을 따라가면 상위마다 하위를 읽는 쿼리가 나간다(N+1). 블로그 하나의 카테고리는 적어서 전부 읽고, 글 수도 GROUP BY 한 번으로 센 뒤 메모리에서 묶는 편이 빠르고 단순하다.</details>

7. 카테고리와 주제를 따로 두는 이유는?
<details><summary>답</summary>카테고리는 블로그마다 주인이 자유롭게 만들어 서비스 전체 기준이 될 수 없다. 홈에서 블로그를 넘어 같은 기준으로 묶으려면 모두가 같은 고정 목록에서 고르는 주제가 필요하다.</details>

8. 주제를 ORDINAL이 아니라 STRING으로 저장하는 이유는?
<details><summary>답</summary>ORDINAL은 순서 번호라 중간에 주제를 하나 넣거나 순서를 바꾸면 기존 글의 주제가 모두 바뀐다. 이름 글자는 순서와 상관없다.</details>

9. 주제별 글에서 최신 글로 채울 때 `NOT IN(이미 고른 글)`을 거는 이유와, 고른 글이 없을 때 그 조건을 빼는 이유는?
<details><summary>답</summary>인기 순으로 이미 고른 글이 최신 글에도 있으면 같은 글이 두 번 나온다. 목록이 비면 IN ()이 SQL 오류가 되므로 조건을 붙이지 않는다.</details>

10. 주제별 순위의 캐시 키는 어떻게 주제마다 달라지나?
<details><summary>답</summary><code>@Cacheable(cacheNames = "topicPosts", key = "#topic.name()")</code>로 메서드 인자의 이름을 키로 쓴다. Redis 키가 blog:topicPosts::IT_DEV처럼 주제마다 다르다.</details>

## 9. 더 읽을거리

- MySQL 8.4 레퍼런스, "CREATE TABLE and Generated Columns", "Unique Indexes"(NULL 허용), "WITH (Common Table Expressions)"의 재귀 CTE
- 트리 저장 방식 비교: 인접 목록, 경로 열거(path enumeration), 중첩 집합(nested set), 클로저 테이블 — 빌 카윈, 『SQL 안티패턴』 "순진한 트리"
- Hibernate ORM 문서, 자기 참조 연관
- 『이펙티브 자바』 아이템 34 "int 상수 대신 열거 타입을 사용하라", 아이템 35 "ordinal 메서드 대신 인스턴스 필드를 사용하라"
- Spring Framework 레퍼런스, "Cache Abstraction" → 키 생성(SpEL `#인자이름`)
