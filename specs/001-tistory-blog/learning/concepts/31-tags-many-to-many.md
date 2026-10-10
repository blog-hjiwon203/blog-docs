# 31. 태그와 다대다 관계

> 관련 스텝: [스텝 7](../step-07.md) (T038, T039), [스텝 8](../step-08.md) (T054), [스텝 9a](../step-09a.md) (T038a), [스텝 17](../step-17.md) (T098 이름 바꾸기·지우기 5.12, 글 없는 태그 지우기 5.13) · 관련 개념: [36-ranking-aggregation](./36-ranking-aggregation.md), [06-jpa-entity-mapping](./06-jpa-entity-mapping.md), [08-pagination](./08-pagination.md), [16-authorization-visibility](./16-authorization-visibility.md), [22-bean-validation](./22-bean-validation.md), [25-react-forms-data](./25-react-forms-data.md), [28-thymeleaf-to-react](./28-thymeleaf-to-react.md), [32-search-like](./32-search-like.md)

## 1. 이 문서로 배우는 것

- **다대다(N:M) 관계**를 테이블로 나타내는 법: 연결 테이블 `post_tag`
- JPA `@ManyToMany`와 `@JoinTable`: 연결 테이블을 엔티티 없이 매핑하기, 주인 쪽(owning side)
- 컬렉션을 `List`가 아니라 `Set`으로 두는 이유
- 태그 이름 정리 규칙(앞뒤 공백, 앞의 `#`, 빈 이름, 30자, 대소문자만 다른 이름, 10개)과 그 규칙을 **서버에 두는** 이유
- "있으면 쓰고 없으면 만든다"(`TagService.resolve`)
- MySQL **정렬 규칙(collation)** 이 대소문자를 무시하게 만드는 원리
- 태그별 글 목록: Specification에서 `join("tags")`로 거르기, 없는 태그는 404
- `@ManyToMany`로 충분할 때와 연결 테이블을 엔티티로 올려야 할 때
- 화면의 태그 입력: 쉼표·Enter, 붙여 넣기, 한글 조합 중 Enter(`isComposing`), 실제로 고친 "바다,산" 버그
- 태그 칩 주소 `/tag/{이름}`과 `encodeURIComponent`

**먼저 알면 좋은 것**: 엔티티와 연관관계, 지연 로딩, Specification([06](./06-jpa-entity-mapping.md)), 글 목록의 가시성 조건([16](./16-authorization-visibility.md)), React 상태와 폼([25](./25-react-forms-data.md), Thymeleaf 비교는 [28](./28-thymeleaf-to-react.md)).

## 2. 왜 필요한가

글에 "spring", "jpa" 같은 태그를 달고, 태그를 누르면 그 태그가 달린 글만 모아 보는 기능이다(TAG-01, TAG-02). 만들어 보면 질문이 생긴다.

- 글 하나에 태그가 여러 개, 태그 하나에 글이 여러 개다. 표 하나로 어떻게 담나?
- 사용자가 `#Spring`, ` spring `, `SPRING`을 섞어 쓰면 다른 태그인가?
- 처음 쓰는 태그는 누가 만드나? 미리 만들어 둬야 하나?
- 글을 고쳐 태그를 빼면 그 태그 자체도 지우나?
- 태그 목록 주소에 없는 이름을 넣으면?
- 한글 태그를 치다가 Enter를 누르면 글자가 반만 들어가는 일은 없나?

명세는 이렇다.

- TAG-01: 글에 태그를 최대 10개 단다. 대소문자만 다른 이름은 같은 태그다. 블로그에 없는 이름은 새로 만든다.
- TAG-02: `/tag/{이름}`에서 그 태그가 달린 글을 최신순으로 본다. 보는 사람이 볼 수 있는 글만.
- data-model: `tag(blog_id, name)`은 블로그 안에서 하나(UNIQUE). 글당 10개는 서비스가 검사한다.

## 3. 기본 개념

### 3.1 다대다는 연결 테이블로

관계형 DB의 칸 하나에는 값 하나만 넣는다. 그래서 "글 7의 태그는 spring, jpa"를 `post` 표의 칸 하나에 `spring,jpa`처럼 넣지 않는다. 그렇게 넣으면 "jpa가 달린 글"을 찾을 때 문자열을 뒤져야 하고, 태그 이름을 바꾸면 모든 글을 고쳐야 한다.

대신 세 표로 나눈다.

```
post            post_tag                 tag
+----+------+   +---------+--------+     +----+---------+--------+
| id | ...  |   | post_id | tag_id |     | id | blog_id | name   |
+----+------+   +---------+--------+     +----+---------+--------+
| 7  | ...  |   | 7       | 1      |     | 1  | 3       | spring |
| 8  | ...  |   | 7       | 2      |     | 2  | 3       | jpa    |
+----+------+   | 8       | 1      |     +----+---------+--------+
                +---------+--------+
```

`post_tag`의 한 줄이 "글 7에 태그 1이 달렸다"는 사실 하나다. 이런 표를 **연결 테이블**(join table, 교차 테이블)이라 한다. 다대다는 사실 "글 1 : 연결 N"과 "태그 1 : 연결 N", 일대다 두 개다. Crowfoot에서 ERD를 그릴 때도 N:M을 연결 테이블과 1:N 관계 두 개로 그렸다.

이 프로젝트의 실제 DDL(`erd/schema.sql`)이다.

```sql
CREATE TABLE tag (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '태그 ID',
    blog_id BIGINT NOT NULL COMMENT '블로그 ID',
    name VARCHAR(30) NOT NULL COMMENT '이름',
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '수정 일시',
    PRIMARY KEY (id),
    CONSTRAINT uk_tag_blog_id_name UNIQUE (blog_id, name)
) COMMENT='태그';
CREATE TABLE post_tag (
    post_id BIGINT NOT NULL COMMENT '글 ID',
    tag_id BIGINT NOT NULL COMMENT '태그 ID',
    PRIMARY KEY (post_id, tag_id)
) COMMENT='글 태그-----글당 최대 10개는 서비스에서 검사';
...
ALTER TABLE post_tag ADD CONSTRAINT fk_post_tag_post FOREIGN KEY (post_id) REFERENCES post (id) ON DELETE CASCADE;
ALTER TABLE post_tag ADD CONSTRAINT fk_post_tag_tag FOREIGN KEY (tag_id) REFERENCES tag (id) ON DELETE CASCADE;
```

- `post_tag`의 기본 키가 `(post_id, tag_id)` 두 칸 묶음이다. 같은 글에 같은 태그가 두 번 달릴 수 없다.
- 태그는 **블로그마다** 따로다. A 블로그의 "spring"과 B 블로그의 "spring"은 다른 행이다. `UNIQUE (blog_id, name)`이 블로그 안에서 이름이 하나임을 지킨다.
- 외래 키의 `ON DELETE CASCADE`는 글이나 태그 행이 **실제로 지워질 때** 연결 행도 같이 지운다. 이 프로젝트에서 글 삭제는 소프트 삭제(`deleted_at`, [27](./27-soft-delete-bulk-update.md))라 글 쪽 CASCADE는 평소에는 일어나지 않는다. 지운 글은 목록 조건(`listedIn`)이 거른다. 태그 쪽 CASCADE는 스텝 17부터 쓴다. 주인이 태그를 지우거나, 글이 하나도 남지 않은 태그를 서버가 지울 때 그 태그의 연결 행(지운 글의 연결 포함)을 DB가 같이 지운다(5.12, 5.13).
- "글당 10개"는 표의 제약으로 나타내기 어렵다(행 개수 제한). 그래서 서비스 코드가 검사한다고 주석에 적었다.

### 3.2 JPA로 매핑하는 두 방법

연결 테이블을 JPA로 다루는 길은 둘이다.

| | `@ManyToMany` + `@JoinTable` | 연결 테이블을 엔티티로 (`PostTag`) |
| --- | --- | --- |
| 코드 | `Post.tags`가 `Set<Tag>` | `Post` 1:N `PostTag` N:1 `Tag` |
| 연결 테이블 칸 | 두 외래 키뿐 | 칸을 더할 수 있다(단 시각, 순서, 단 사람) |
| 연결 행 다루기 | 컬렉션에 넣고 빼면 Hibernate가 INSERT/DELETE | `PostTag`를 직접 저장·삭제 |
| 연결 테이블만 조회 | 어렵다 | Repository로 바로 |

스텝 7에서는 `post_tag`가 외래 키 두 칸뿐이라 `@ManyToMany`로 충분하다고 보고 그렇게 만들었다. 스텝 9a에서 지원이 이것을 다시 보고 **연결 테이블 엔티티(`PostTag`)로 바꿨다**(T038a). 칸이 없어도 `@ManyToMany`의 단점이 그대로 남기 때문이다.

- 연결 테이블에 칸(단 시각, 순서)이 생기면 매핑을 통째로 바꿔야 한다. 처음부터 엔티티면 칸 하나만 더하면 된다.
- 연결 행에 어떤 INSERT·DELETE가 나가는지 코드에서 보이지 않는다. 컬렉션 종류와 Hibernate 버전에 따라 "모두 지우고 다시 넣기"가 나가기도 한다(3.4).
- ERD의 표(`post_tag`)와 코드의 클래스가 1:1로 맞지 않아 읽는 사람이 헷갈린다.

그래서 실무에서는 `@ManyToMany`를 거의 쓰지 않고 연결 엔티티로 푸는 것을 권한다. 바꾼 코드는 5.11에 있다. 아래 5.2·5.6의 코드 발췌는 스텝 7 당시(`@ManyToMany`) 모습이다.

### 3.3 주인 쪽(owning side)

양쪽 엔티티가 서로를 가리키는 관계에서, **연결 테이블을 고칠 책임**은 한쪽에만 있다. 그쪽을 주인이라 한다. `@JoinTable`을 붙인 쪽이 주인이고, 반대쪽은 `mappedBy`로 "저쪽이 주인"이라고만 적는다.

이 프로젝트는 `Post`에만 `tags`가 있고 `Tag`에는 `posts`가 없다(단방향). 글에서 태그를 찾는 일은 많지만, 태그 엔티티에서 글 컬렉션을 꺼낼 일은 없다. 태그별 글 목록은 쿼리(Specification)로 찾는다. 쓰지 않는 반대쪽 컬렉션을 두면, 양쪽을 같이 맞춰야 하는 부담과 실수로 큰 컬렉션을 불러올 위험만 생긴다.

### 3.4 `List`가 아니라 `Set`

Hibernate는 순서 칸(`@OrderColumn`)이 없는 `List` 연관을 **bag**(중복을 허락하고 순서가 없는 묶음)으로 다룬다. bag에는 이런 성질이 있다.

- 원소 하나만 바뀌어도 어느 행인지 특정할 수 없어, 연결 행을 **모두 지우고 다시 넣는** 방식으로 반영하기 쉽다.
- bag 두 개를 한 쿼리에서 `join fetch`하면 `MultipleBagFetchException`이 난다.

`Set`은 원소가 겹치지 않는다. `post_tag`의 기본 키 `(post_id, tag_id)`와 뜻이 같다. 이 프로젝트는 `LinkedHashSet`을 써서 넣은 순서도 유지한다. 다만 화면에 보낼 때는 이름순으로 정렬해 보내므로(`tagNames()`), 순서를 저장하지는 않는다.

`Set`에 엔티티를 넣으면 같은지 비교에 `equals`/`hashCode`가 쓰인다. `Tag`는 이 둘을 따로 정의하지 않아 **객체가 같은지**(같은 인스턴스인지)로 비교한다. 한 트랜잭션(영속성 컨텍스트) 안에서는 같은 행이 늘 같은 인스턴스이므로 이 프로젝트의 쓰임새에서는 문제가 없다. 서로 다른 트랜잭션에서 읽은 엔티티를 한 `Set`에 섞는 코드라면 `equals`를 따로 생각해야 한다.

### 3.5 정렬 규칙(collation)과 대소문자

MySQL은 문자열을 비교할 때 칸의 **정렬 규칙**을 따른다. 이 프로젝트의 DB는 `docker-compose.yml`과 테스트 컨테이너 모두 `--collation-server=utf8mb4_0900_ai_ci`로 띄운다. 이름의 뜻은 이렇다.

| 조각 | 뜻 |
| --- | --- |
| `utf8mb4` | 문자 집합. 이모지까지 담는 UTF-8 |
| `0900` | 유니코드 정렬 알고리즘(UCA) 9.0.0 기준 |
| `ai` | accent insensitive: `é`와 `e`를 같게 본다 |
| `ci` | case insensitive: `A`와 `a`를 같게 본다 |

그래서 `WHERE name = 'SPRING'`은 `spring` 행도 찾고, `UNIQUE (blog_id, name)`은 `spring`이 있으면 `Spring`을 막는다. **대소문자 무시를 Java 코드가 아니라 DB가 해 준다.** `TagRepository`의 주석이 이 사실을 적어 둔 것이다.

실제 개발 DB에서 확인한 결과다(직접 해 보기 7.3).

```
accent_eq  case_eq  trail_eq
1          1        0
```

`'café' = 'cafe'`가 1(같다), `'Spring' = 'SPRING'`이 1, `'a ' = 'a'`가 0이다. 마지막은 `0900` 계열 정렬 규칙이 끝 공백을 무시하지 않는(NO PAD) 규칙이라서다. 태그 이름은 저장 전에 `trim`하므로 이 차이로 문제가 생기지는 않는다.

### 3.6 규칙은 서버에, 화면은 안내만

"앞의 #을 뗀다", "10개까지" 같은 규칙은 화면(TagInput)에도 있고 서버(TagNames)에도 있다. 둘 중 **진짜는 서버**다. API는 화면 말고도 curl이나 다른 프로그램이 부를 수 있다. 화면의 규칙은 사용자가 저장 버튼을 누르기 전에 바로 알게 해 주는 편의일 뿐이다. 이것은 [16](./16-authorization-visibility.md)의 "화면의 권한 검사는 안내용"과 같은 원칙이다.

## 4. 동작 원리

### 4.1 태그를 달아 발행할 때

```
POST /api/posts  { "title": ..., "tagNames": ["spring", " #Security ", "Spring", ""] }
  PostSaveRequest → PostCommand(tagNames)
  PostService.publish  (@Transactional)
    Post.published(...)                          글 엔티티 만들기 (아직 INSERT 전)
    tagService.resolve(blog, tagNames)
      TagNames.normalize  → ["spring", "Security"]      정리: 공백·# 떼기, 빈 것 버림, 대소문자·악센트 중복 합침
      findByBlogIdAndNameIn(blogId, [spring, Security])  SELECT ... WHERE blog_id=? AND name IN (?, ?)
      없는 이름만 insertIfAbsent                     INSERT IGNORE INTO tag (blog_id, name) ...
              → findLockedByBlogIdAndName         SELECT ... FOR SHARE (방금 넣었거나 남이 먼저 넣은 행)
    post.replaceTags(tags)                       Set을 비우고 새 태그를 넣음
    postRepository.save(post)                    INSERT INTO post ...
  트랜잭션 커밋 직전 flush                        INSERT INTO post_tag (post_id, tag_id) ... 태그 수만큼
```

순서가 중요하다. 태그 정리에서 400(`tagNames` 칸 오류, `TOO_MANY_TAGS`)이 나면 예외가 트랜잭션 밖으로 나가 **아무것도 저장되지 않는다**. 테스트 `tooManyTooLongOrSlashedTagsAreRejected`가 11개를 보낸 뒤 `tag` 표가 비어 있음(`tagCount()).isZero()`)을 확인한다.

### 4.2 글을 고쳐 태그를 바꿀 때

```
PUT /api/posts/{id}  { "tagNames": ["jpa", "mysql"] }      원래 태그: spring, jpa
  PostService.edit
    findEditable → post (이 트랜잭션에서 읽은 영속 엔티티)
    post.edit(...)
    post.replaceTags(resolve(...))   → tags = {jpa, mysql}  (mysql은 새로 만듦)
  커밋 때 변경 감지: post_tag에서 (id, spring) 연결이 빠지고 (id, mysql) 연결이 생긴다
```

스텝 7~16에서는 `tag` 표의 "spring" 행을 **지우지 않았다**. 다른 글이 쓰고 있을 수 있고, 나중에 다시 쓸 수도 있다고 보았다. 아무 글도 쓰지 않는 태그는 목록 쿼리가 "글이 있는 태그만" 골라 화면에서만 감췄다(5.10).

스텝 17에서 이 방식의 구멍이 드러나 바꿨다(2026-10-11 지원 결정, 5.13). 지금은 수정이 끝날 때 **빠진 태그 가운데 어느 글에도 남지 않은 것을 지운다**. "spring"을 다른 글이 쓰고 있으면 남고, 아무도 안 쓰면 지워진다. 테스트 `editingReplacesTagsAndRemovesTagsNoPostUses`가 수정 뒤 블로그 태그가 `jpa, mysql` 두 개임을 확인한다. 다음에 누가 "spring"을 다시 달면 새로 만든다.

컬렉션을 `clear()` 뒤 `addAll()` 하면 Hibernate가 `post_tag`에 DELETE·INSERT를 몇 번 보내는지는 컬렉션 종류와 Hibernate 버전에 따라 다르다. 궁금하면 SQL 로그를 켜고 직접 본다(7.4).

### 4.3 태그별 글 목록

```
GET http://alpha.blog.test/api/posts?tag=SPRING&page=1
  PostController → PostQueryService.blogPosts(blog, viewerId, null, "SPRING", page)
    listedIn(blog, viewerId, now)                    볼 수 있는 글 조건 (16)
    taggedWith(blog, "SPRING")
      findByBlogIdAndName(blogId, "SPRING")          정렬 규칙 덕에 "spring" 행을 찾음, 없으면 404
      → (root, query, cb) -> post JOIN post_tag JOIN tag ... WHERE tag.id = 1
  findAll(조건, 최신순 10개)                         내용 쿼리 + 전체 개수 쿼리
```

조인이지만 **태그 id 하나**로 거르므로 글 하나당 연결 행도 하나만 맞는다. 그래서 같은 글이 두 번 나오지 않는다. 검색처럼 "이름에 글자가 들어간 태그"로 거르면 한 글의 여러 태그가 동시에 맞을 수 있어 중복이 생긴다. 검색은 그래서 조인 대신 EXISTS를 쓴다([32](./32-search-like.md)).

## 5. 이 프로젝트에서는

### 5.1 `tag/domain/Tag.java`

```java
@Entity
@Table(name = "tag")
@EntityListeners(AuditingEntityListener.class)
public class Tag {

    public static final int MAX_NAME_LENGTH = 30;

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "blog_id", nullable = false)
    private Blog blog;

    @Column(name = "name", nullable = false, length = MAX_NAME_LENGTH)
    private String name;

    @LastModifiedDate
    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;
```

- `MAX_NAME_LENGTH = 30`: 표의 `VARCHAR(30)`과 같은 값이다. 정리 규칙(`TagNames`)도 이 상수를 쓴다. 숫자를 한 곳에만 두면 표와 검사가 어긋나지 않는다.
- `@ManyToOne(fetch = LAZY)`: 태그는 한 블로그에 속한다. 블로그는 필요할 때만 읽는다.
- 다른 엔티티와 달리 공통 부모(`BaseTimeEntity`)를 쓰지 않는다. `tag` 표에는 `created_at`이 없고 `updated_at`만 있어서, 클래스 주석에 그 이유를 적었다.
- `posts` 컬렉션이 없다. 단방향이다(3.3).

### 5.2 `post/domain/Post.java`의 태그 부분

```java
    /** 글에 단 태그 (TAG-01). 연결 테이블 post_tag(post_id, tag_id). 글당 10개는 TagNames가 검사한다. */
    @ManyToMany
    @JoinTable(name = "post_tag",
            joinColumns = @JoinColumn(name = "post_id"),
            inverseJoinColumns = @JoinColumn(name = "tag_id"))
    private Set<Tag> tags = new LinkedHashSet<>();
```

- `@ManyToMany`: 기본 fetch가 LAZY다. 글을 읽을 때 태그는 실제로 꺼낼 때 따로 읽는다.
- `@JoinTable(name = "post_tag")`: 연결 테이블 이름. 없으면 Hibernate가 `post_tags` 같은 이름을 지어내는데, `ddl-auto=validate`라 이름이 틀리면 앱이 뜨지 않는다.
- `joinColumns`: 연결 테이블에서 **이쪽(글)** 을 가리키는 칸. `inverseJoinColumns`: **저쪽(태그)** 을 가리키는 칸.
- 처음부터 빈 `LinkedHashSet`으로 둔다. `null` 검사 없이 바로 쓸 수 있다.

```java
    /** 태그를 통째로 바꾼다. 빠진 태그는 연결만 끊기고 블로그 태그는 남는다. */
    public void replaceTags(Collection<Tag> newTags) {
        tags.clear();
        tags.addAll(newTags);
    }

    /** 태그 이름, 가나다순. 트랜잭션 안에서 불러야 한다(지연 로딩). */
    public List<String> tagNames() {
        return tags.stream().map(Tag::getName).sorted(Comparator.naturalOrder()).toList();
    }
```

- `replaceTags`: 필드를 새 컬렉션으로 **바꿔 끼우지 않고**(`this.tags = new ...`) 같은 컬렉션을 비우고 채운다. Hibernate는 영속 엔티티의 컬렉션을 자기 래퍼(`PersistentSet`)로 바꿔 끼워 변화를 추적한다. 필드를 통째로 바꾸면 그 추적 정보가 끊긴다.
- `tagNames()`: 지연 로딩이라 트랜잭션 밖(`open-in-view=false`, [24](./24-layered-architecture-dto.md))에서 부르면 `LazyInitializationException`이 난다. 그래서 `PostService.managed`, `PostReadService`처럼 트랜잭션 안에서 이름 목록으로 꺼내 결과 레코드(`ManagedPost`, `PostView`)에 담아 넘긴다.

### 5.3 `tag/domain/TagNames.java`: 정리 규칙

```java
    public static List<String> normalize(List<String> raw) {
        if (raw == null) {
            return List.of();
        }
        Map<String, String> unique = new TreeMap<>(nameComparator());
        List<String> ordered = new ArrayList<>();
        for (String name : raw) {
            String trimmed = name == null ? "" : name.trim().replaceFirst("^#+", "").trim();
            if (trimmed.isEmpty()) {
                continue;
            }
            if (trimmed.length() > Tag.MAX_NAME_LENGTH) {
                throw BusinessException.invalidField("tagNames", "태그는 " + Tag.MAX_NAME_LENGTH + "자까지입니다.");
            }
            if (trimmed.contains("/")) {
                // 태그 목록 주소 /tag/{이름}에서 %2F가 되어 보안 방화벽이 거절한다 (spec TAG-01)
                throw BusinessException.invalidField("tagNames", "태그에는 /를 쓸 수 없습니다.");
            }
            if (unique.putIfAbsent(trimmed, trimmed) == null) {
                ordered.add(trimmed);
            }
        }
        if (unique.size() > MAX_PER_POST) {
            throw new BusinessException(ErrorCode.TOO_MANY_TAGS);
        }
        return ordered;
    }

    /** DB처럼 대소문자·악센트를 무시하고 이름을 비교한다. Collator는 스레드 안전하지 않아 쓸 때마다 만든다. */
    public static Collator nameComparator() {
        Collator collator = Collator.getInstance(Locale.ROOT);
        collator.setStrength(Collator.PRIMARY);
        return collator;
    }
```

한 줄씩 보자.

1. `raw == null`이면 빈 목록. `tagNames` 칸을 아예 안 보낸 요청도 받는다.
2. `new TreeMap<>(nameComparator())`: 키 비교를 `equals`가 아니라 **주어진 비교기**로 하는 지도다. 비교기가 "같다(0)"고 하면 같은 키다. 그래서 `Café`를 넣은 뒤 `cafe`를 `putIfAbsent`하면 이미 있는 키로 본다.
3. `ordered`: `TreeMap`은 키를 정렬해 들고 있어 들어온 순서를 잃는다. 처음 쓴 순서를 지키려고 따로 목록을 둔다. `putIfAbsent`가 `null`을 돌려주면(새 키였으면) 목록에도 더한다. 값으로 **처음 쓴 모양**이 남는다. `["spring", "Spring"]`이면 `spring`이 남는다.
4. `trim()` → `replaceFirst("^#+", "")` → 다시 `trim()`: ` #Security `는 앞뒤 공백을 떼고(`#Security`), 앞의 `#`들을 떼고(`Security`), `# spring`처럼 `#` 뒤에 공백이 있으면 한 번 더 뗀다. 정규식 `^#+`는 "맨 앞에서 시작하는 # 한 개 이상"이다. 가운데 `#`(`C#`)은 남는다.
5. 비었으면 건너뛴다. `""`, `"  "`, `"#"`는 오류가 아니라 무시한다.
6. 30자를 넘으면 400. `invalidField("tagNames", ...)`라 응답의 `fieldErrors[0].field`가 `tagNames`다. 화면은 이 칸 이름으로 태그 입력 아래에 문장을 띄운다(`errors.tagNames`).
   `/`가 들어 있어도 같은 400이다. 태그 `a/b`의 목록 주소는 `/tag/a%2Fb`가 되는데, Spring Security의 기본 방화벽(`StrictHttpFirewall`)이 인코딩된 슬래시가 든 주소를 거절한다. 방화벽을 푸는 대신 이름에서 막기로 했다(2026-10-09 지원 결정, spec TAG-01).
7. **정리한 뒤** 10개를 센다. `["a", "A", "#a", ... ]`처럼 겹치는 이름으로 11개를 보내도 정리해서 10개 이하면 통과다.

**`Collator`와 PRIMARY.** `java.text.Collator`는 언어 규칙대로 문자열을 비교하는 도구다. 비교의 세밀함(strength)을 정할 수 있다.

| strength | 무엇이 다르면 다르다고 보나 | 예 |
| --- | --- | --- |
| `PRIMARY` | 기본 글자만 | `a` = `A` = `á` |
| `SECONDARY` | 기본 글자 + 악센트 | `a` = `A`, `a` ≠ `á` |
| `TERTIARY`(기본값) | + 대소문자 | `a` ≠ `A` |

DB 칸의 정렬 규칙 `utf8mb4_0900_ai_ci`는 이름 그대로 악센트 무시(ai)·대소문자 무시(ci)다(3.5). 그래서 Java에서는 PRIMARY로 맞췄다. 둘 다 유니코드 정렬 알고리즘(UCA)에 바탕을 두지만 버전과 세부 규칙이 완전히 같다고 장담할 수는 없다. 그래서 **최종 판단은 DB에 맡기는 장치**를 5.4에 따로 두었다.

> **처음 코드는 `toLowerCase`였다.** 대소문자만 무시하고 악센트는 구분했다. DB에 `Café`가 있는데 `cafe`를 보내면, `IN` 조회는 DB 규칙으로 `Café`를 찾아오지만 Java는 `café`(소문자 키)와 `cafe`를 다른 키로 보고 새 태그를 저장하려 했다. DB의 UNIQUE가 이를 막아 **500**이 났다. 학습 문서를 쓰다가 의심이 들어 테스트(`accentOnlyDifferenceIsTheSameTagLikeTheDatabaseSays`)로 확인하고 고쳤다.

### 5.4 `tag/application/TagService.java`: 있으면 쓰고 없으면 만들기

```java
    @Transactional
    public List<Tag> resolve(Blog blog, List<String> rawNames) {
        List<String> names = TagNames.normalize(rawNames);
        if (names.isEmpty()) {
            return List.of();
        }
        Map<String, Tag> existing = new TreeMap<>(TagNames.nameComparator());
        tagRepository.findByBlogIdAndNameIn(blog.getId(), names).forEach(tag -> existing.putIfAbsent(tag.getName(), tag));
        return names.stream()
                .map(name -> existing.computeIfAbsent(name, missing -> create(blog, missing)))
                .distinct()
                .toList();
    }

    /** 없으면 넣고, 넣었든 다른 트랜잭션이 먼저 넣었든 DB의 그 행을 읽는다. 같은 이름 판단은 DB가 한다. */
    private Tag create(Blog blog, String name) {
        tagRepository.insertIfAbsent(blog.getId(), name);
        return tagRepository.findLockedByBlogIdAndName(blog.getId(), name).orElseThrow();
    }
```

- `findByBlogIdAndNameIn`: Spring Data가 메서드 이름으로 `WHERE blog_id = ? AND name IN (?, ?, ...)`를 만든다. 태그가 10개여도 **쿼리 한 번**이다. 이름마다 `findByBlogIdAndName`을 부르면 10번이 된다.
- `IN` 비교도 정렬 규칙을 따른다. 요청이 `SPRING`이고 표에 `spring`이 있으면 `spring` 행이 나온다.
- 그래서 결과를 **DB와 같은 비교기**(5.3)를 쓰는 `TreeMap`에 담는다. DB가 돌려준 이름(`spring`, `Café`)과 요청 이름(`SPRING`, `cafe`)의 모양이 달라도 같은 키로 찾는다.
- `computeIfAbsent`: 지도에 없으면 `create`로 만들고 그 결과를 지도에도 넣는다. 만들 때는 사용자가 쓴 모양(`name`)으로 만든다. 처음 쓴 사람이 `Spring`으로 썼으면 그 블로그의 태그 이름은 `Spring`이다.
- `.distinct()`: Java 비교기와 DB 규칙이 아주 드물게 달라 두 이름이 같은 DB 행으로 모이면 같은 태그가 두 번 나온다. 한 번만 남긴다.
- `@Transactional`: 글 저장 트랜잭션 안에서 부르므로 그 트랜잭션에 합류한다(전파 REQUIRED, [23](./23-transactions-locking.md)). 글 저장이 실패하면 새로 만든 태그도 같이 롤백된다.

**새 태그 만들기: `INSERT IGNORE` + 공유 잠금 읽기** (`tag/domain/TagRepository.java`)

처음 코드는 `tagRepository.save(Tag.create(blog, name))`였다. 같은 블로그 주인이 같은 새 태그(`동시`)를 단 글을 **동시에** 저장하면 두 트랜잭션이 모두 "없다"고 보고 INSERT해서, 늦은 쪽이 UNIQUE 위반으로 500이 났다(`sameNewTagFromConcurrentPostsIsCreatedOnce` 테스트로 확인). 지금은 이렇다.

```java
    @Modifying
    @Query(value = "INSERT IGNORE INTO tag (blog_id, name) VALUES (:blogId, :name)", nativeQuery = true)
    int insertIfAbsent(@Param("blogId") Long blogId, @Param("name") String name);

    @Lock(LockModeType.PESSIMISTIC_READ)
    @Query("select t from Tag t where t.blog.id = :blogId and t.name = :name")
    Optional<Tag> findLockedByBlogIdAndName(@Param("blogId") Long blogId, @Param("name") String name);
```

- `INSERT IGNORE`: UNIQUE에 걸리면 오류 대신 0행으로 끝난다. **같은 이름인지는 DB가 판단**하므로 Java 비교기와 DB 규칙이 조금 달라도 안전하다. 공감의 `post_like`와 같은 방법이다([33](./33-isolation-deadlock.md)). `updated_at`은 칸 기본값(`CURRENT_TIMESTAMP(6)`)이 채운다.
- 그다음 읽기는 **잠금 읽기**여야 한다. 평범한 SELECT는 이 트랜잭션이 처음 읽은 때의 스냅샷을 보므로, 다른 트랜잭션이 막 커밋한 태그가 안 보일 수 있다(문서 33의 공감 수 버그와 같은 이유).
- `PESSIMISTIC_READ`(MySQL에서 `FOR SHARE`)인 이유: 처음에는 `PESSIMISTIC_WRITE`(`FOR UPDATE`)로 했더니 동시 테스트에서 **데드락**이 났다. `INSERT IGNORE`가 중복을 만나면 InnoDB는 그 인덱스 행에 공유(S) 잠금을 걸어 둔다. 늦은 트랜잭션 여럿이 모두 S 잠금을 쥔 채 배타(X) 잠금으로 올리려 하면, 서로 상대의 S 잠금이 풀리기를 기다린다. 읽기만 하면 되므로 S 잠금으로 충분하고, S끼리는 서로 막지 않는다.
- 이 테스트는 다섯 글을 동시에 저장해 모두 201, 태그 1개, 연결 행 5개인지 본다. 세 번 연달아 돌려 확인했다.
- (스텝 17) 이미 있는 태그를 찾는 줄도 바뀌었다. 평범하게 찾은 뒤 **번호로 잠그며 다시 읽는다**(`findLockedByIdIn`). 태그가 지워질 수 있게 되어서다. 이유와, 이름으로 잠갔다가 데드락이 난 이야기는 5.13.

### 5.5 `post/application/PostService.java`: 발행·수정에서 부르기

```java
    @Transactional
    public Post publish(Blog blog, PostCommand command) {
        Post post = Post.published(blog, category(blog, command.categoryId()), command.title().trim(),
                body(command.contentHtml()), command.visibility(), command.topic(), LocalDateTime.now(clock));
        post.replaceTags(tagService.resolve(blog, command.tagNames()));
        return postRepository.save(post);
    }
```

```java
    @Transactional
    public Post edit(Blog blog, Long postId, LoginMember member, PostCommand command) {
        Post post = findEditable(blog, postId, member);
        post.edit(category(blog, command.categoryId()), command.title().trim(), body(command.contentHtml()),
                command.visibility(), command.topic());
        post.replaceTags(tagService.resolve(blog, command.tagNames()));
        return post;
    }
```

- 발행: 글을 만들고, 태그를 붙이고, 저장한다. `save(post)`가 글을 INSERT하고, 커밋 때 연결 행을 INSERT한다.
- 수정: `findEditable`이 404 → 401 → 403 순서로 권한을 먼저 본다. 남의 글에 태그를 보내도 태그 정리·생성까지 가지 않는다. 수정은 `save`를 부르지 않는다. 영속 엔티티라 변경 감지가 커밋 때 반영한다([27](./27-soft-delete-bulk-update.md)).
- 스텝 5까지 `PostSaveRequest`는 `tagNames`를 보내면 "아직 없는 기능"으로 400을 줬다. 스텝 7에서 그 거절을 빼고 `toCommand`가 `tagNames`를 넘기게 했다.

### 5.6 `post/application/PostQueryService.java`: 태그별 목록

```java
    @Transactional(readOnly = true)
    public Page<Post> blogPosts(Blog blog, Long viewerId, Long categoryId, String tag, PageQuery page) {
        Specification<Post> condition = PostSpecifications.listedIn(blog, viewerId, LocalDateTime.now(clock));
        if (categoryId != null) {
            condition = condition.and(inCategory(blog, viewerId, categoryId));
        }
        if (tag != null) {
            condition = condition.and(taggedWith(blog, tag));
        }
        return postRepository.findAll(condition, page.toPageable(LATEST));
    }

    private Specification<Post> taggedWith(Blog blog, String name) {
        Tag tag = tagRepository.findByBlogIdAndName(blog.getId(), name.trim())
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));
        return (root, query, cb) -> cb.equal(root.join("tags").get("id"), tag.getId());
    }
```

- 블로그 메인 목록과 **같은 메서드**에 조건 하나(`taggedWith`)를 더했다. 볼 수 있는 글 조건(`listedIn`), 최신순 정렬, 10개씩 페이지가 그대로 따라온다. 태그 목록을 위해 가시성 규칙을 다시 쓰지 않는다.
- 태그를 먼저 이름으로 찾는다. 없으면 404. 이 블로그에 그런 태그가 없다는 뜻이다. (스텝 17부터는 태그가 있어도 보는 사람이 볼 수 있는 글이 하나도 없으면 404다, 5.13.) 화면(`BlogMainPage`)은 404를 받으면 "찾을 수 없음" 화면을 보여 준다.
- `root.join("tags")`: `Post.tags` 필드 이름으로 조인한다. JPA가 `@JoinTable` 정보를 보고 `post → post_tag → tag` 두 번 조인하는 SQL을 만든다. 연결 테이블을 코드에서 직접 부르지 않는다.
- `.get("id")`와 태그 id 비교: 이름이 아니라 **id**로 비교한다. 이름 비교는 위의 `findByBlogIdAndName`에서 한 번만 한다.
- 태그는 블로그마다 따로라 `blogId`로 먼저 좁힌다. 다른 블로그의 태그 이름으로는 이 블로그의 글이 나오지 않는다.

컨트롤러는 쿼리 문자열 한 칸을 더 받는다.

```java
@RequestParam(required = false) String tag) {
```

Thymeleaf로 화면을 만들 때 `@RequestParam String tag`로 받아 Model에 담던 것과 같은 받기다. 다른 점은 결과를 HTML이 아니라 JSON(`PageResponse`)으로 돌려준다는 것뿐이다.

### 5.7 테스트 `TagIntegrationTest`

```java
    @Test
    void tagsAreCleanedDedupedAndCreatedOnce() throws Exception {
        long id = publish("[\"spring\", \" #Security \", \"Spring\", \"\", \"spring\"]");

        mockMvc.perform(get("/api/posts/" + id).header(HttpHeaders.HOST, TestBlogs.host(blog)))
                .andExpect(jsonPath("$.tags", contains("Security", "spring")));
        assertThat(tagCount()).isEqualTo(2);

        // 다른 글에서 대소문자만 다르게 써도 같은 태그를 쓴다
        publish("[\"SPRING\", \"jpa\"]");
        assertThat(tagCount()).isEqualTo(3);
    }
```

나중에 더한 두 테스트(5.3, 5.4의 버그):

| 테스트 | 확인하는 것 |
| --- | --- |
| `accentOnlyDifferenceIsTheSameTagLikeTheDatabaseSays` | `Café`가 있는 블로그에 `cafe`·`résumé`·`resume`을 달면 201, 태그는 `Café`·`résumé` 두 개 |
| `sameNewTagFromConcurrentPostsIsCreatedOnce` | 같은 새 태그를 단 글 다섯 개를 동시에 저장해도 모두 201, 태그 1개, 연결 행 5개 |

- 다섯 개를 보냈지만 정리하면 `spring`, `Security` 둘이다. 글 상세의 `tags`는 이름순인데 `Security`가 `spring`보다 앞이다. Java의 `Comparator.naturalOrder()`는 유니코드 값 순서라 대문자(`S`=83)가 소문자(`s`=115)보다 앞이기 때문이다. DB 정렬 규칙과 다른 순서라는 점에 주의한다.
- 두 번째 글의 `SPRING`은 새 태그를 만들지 않는다. 블로그 태그는 `spring`, `Security`, `jpa` 세 개다.

```java
    @Test
    void listsPostsByTagIgnoringCase() throws Exception {
        long springPost = publish("[\"spring\"]");
        long both = publish("[\"Spring\", \"jpa\"]");
        publish("[\"jpa\"]");
        long privatePost = publish("[\"spring\"]");
        send(patch("/api/posts/" + privatePost + "/visibility"), "{\"visibility\":\"PRIVATE\"}")
                .andExpect(status().isNoContent());

        mockMvc.perform(get("/api/posts").param("tag", "SPRING").header(HttpHeaders.HOST, TestBlogs.host(blog)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.content[*].id", contains((int) both, (int) springPost)));
        mockMvc.perform(get("/api/posts").param("tag", "없는태그").header(HttpHeaders.HOST, TestBlogs.host(blog)))
                .andExpect(status().isNotFound());
    }
```

- 비공개로 바꾼 글(`privatePost`)은 비회원 목록에 없다. 태그 목록이 블로그 목록의 가시성 조건을 그대로 쓰는지 확인한다.
- 순서가 `both, springPost`: 최신순이다.

### 5.8 화면: `TagInput.tsx`와 `tagNames.ts`

글쓰기 화면(`PostWritePage`)은 태그 목록을 상태로 들고 있다가 저장할 때 `tagNames`로 보낸다.

```tsx
const [tagNames, setTagNames] = useState<string[]>([])
...
<TagInput tags={tagNames} onChange={setTagNames} />
{errors.tagNames && <p className="err">{errors.tagNames}</p>}
```

Thymeleaf라면 `<input name="tagNames" value="spring,jpa">`처럼 쉼표로 이은 문자열을 폼으로 보내고 컨트롤러에서 나눴을 것이다. React 화면은 배열을 상태로 들고 있다가 JSON 배열로 그대로 보낸다. 서버 오류는 `fieldErrors`의 `tagNames` 칸으로 돌아와 `BindingResult`의 `th:errors="*{tagNames}"`와 같은 자리에 뜬다([25](./25-react-forms-data.md)).

태그 규칙은 화면 부품에서 떼어 **순수 함수**로 뒀다.

```ts
export function addTags(tags: string[], rawNames: string[]): { tags: string[]; message: string | null } {
  const result = [...tags]
  let message: string | null = null
  for (const raw of rawNames) {
    const name = raw.trim().replace(/^#+/, '').trim()
    if (!name || result.some((tag) => sameName(tag, name))) {
      continue
    }
    if (name.length > MAX_LENGTH) {
      message = `태그는 ${MAX_LENGTH}자까지입니다.`
    } else if (result.length >= MAX_TAGS) {
      message = `태그는 ${MAX_TAGS}개까지 달 수 있습니다.`
    } else {
      result.push(name)
    }
  }
  return { tags: result, message }
}

/** 쉼표가 들어온 입력(붙여 넣기 포함)을 다 쓴 이름들과 아직 쓰는 중인 마지막 조각으로 나눈다. */
export function splitDraft(value: string): { done: string[]; rest: string } {
  const parts = value.split(',')
  return { done: parts.slice(0, -1), rest: parts[parts.length - 1] }
}
```

`sameName`은 서버와 같은 기준(대소문자·악센트 무시)으로 비교한다.

```ts
export function sameName(a: string, b: string): boolean {
  return a.localeCompare(b, undefined, { sensitivity: 'base' }) === 0
}
```

`localeCompare`의 `sensitivity: 'base'`는 Java `Collator`의 PRIMARY와 같은 뜻이다(기본 글자만 비교). `'accent'`면 악센트까지, `'case'`면 대소문자까지 구분한다.

- `[...tags]`: 받은 배열을 고치지 않고 복사본을 고친다. React는 상태 배열을 직접 바꾸면 바뀐 줄 모른다. 새 배열을 만들어 `onChange`로 넘겨야 다시 그린다.
- 서버의 `TagNames`와 같은 규칙(앞의 `#`, 대소문자 중복, 30자, 10개)이다. 다만 서버는 넘치면 요청 전체를 400으로 거절하고, 화면은 넘치는 이름만 빼고 안내 문구를 띄운다. 입력 중에는 거절보다 안내가 낫기 때문이다.
- `splitDraft("바다,산,")` → `done: ["바다", "산"]`, `rest: ""`. 마지막 쉼표 뒤 조각은 아직 쓰는 중으로 본다.

부품은 이 두 함수를 부른다.

```tsx
  function commit(names: string[]) {
    const result = addTags(tags, names)
    setMessage(result.message)
    if (result.tags.length !== tags.length) {
      onChange(result.tags)
    }
  }

  function add() {
    setDraft('')
    commit([draft])
  }

  function onDraftChange(value: string) {
    const { done, rest } = splitDraft(value)
    setDraft(rest)
    if (done.length > 0) {
      commit(done)
    }
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    // 한글 조합 중의 Enter는 글자를 끝내는 키라 태그로 넣지 않는다
    if (event.nativeEvent.isComposing) {
      return
    }
    if (event.key === 'Enter') {
      event.preventDefault()
      add()
    } else if (event.key === 'Backspace' && draft === '' && tags.length > 0) {
      onChange(tags.slice(0, -1))
    }
  }
```

- `onDraftChange`: 입력값이 바뀔 때마다(타자든 붙여 넣기든) 쉼표로 나눈다. 쉼표 앞 조각들은 태그로 달고, 남은 조각만 입력 칸에 둔다.
- Enter: `preventDefault()`로 폼 제출(글 발행)을 막고 지금 입력을 태그로 단다.
- 빈 칸에서 Backspace: 마지막 태그를 뺀다.
- 입력 칸을 벗어나면(`onBlur={add}`) 쓰던 이름도 단다. 태그를 쓰다 바로 발행 버튼을 눌러도 빠지지 않는다.

**`isComposing`과 한글.** 한글은 자모를 조합해 글자를 만든다(IME). "산"을 치는 동안 브라우저는 조합 중 상태이고, 이때 누른 Enter는 "조합을 끝내라"는 뜻으로도 쓰인다. 조합 중 Enter를 태그 달기로 처리하면, 브라우저에 따라 조합이 끝나기 전 값(`사`)이 태그가 되거나 Enter가 두 번 처리되어 빈 태그와 글자가 섞인다. `event.nativeEvent.isComposing`이 참이면 아무것도 하지 않는다. React의 `KeyboardEvent`는 브라우저 이벤트를 감싼 것이라, 원래 이벤트의 `isComposing`은 `nativeEvent`에서 꺼낸다.

**실제로 고친 버그: 붙여 넣은 "바다,산"이 한 태그가 됨 (커밋 e5ad8a6).** 처음 만든 부품은 쉼표를 `onKeyDown`에서만 처리했다(`event.key === ','`). 손으로 쉼표 키를 누르면 keydown이 생겨 문제가 없었다. 그런데 `바다,산`을 **붙여 넣으면** keydown은 생기지 않고 입력값만 바뀐다. 헤드리스 Chrome으로 글자를 넣어 본 확인에서 `#바다,산` 태그 하나가 생겼다. 서버의 `TagNames`는 쉼표를 나누지 않으므로(쉼표도 이름의 글자) 그대로 저장됐다. 고친 방법은 키가 아니라 **입력값**을 보고 나누는 것이다(`onDraftChange` + `splitDraft`). 키보드, 붙여 넣기, 모바일 자동완성 등 값이 들어오는 모든 길이 `onChange`를 지나기 때문이다. 같이 바꾼 것들은 이렇다.

- 입력 칸 `maxLength`를 `MAX_LENGTH + 1`에서 `(MAX_LENGTH + 1) * MAX_TAGS`로 늘렸다. 31자 제한이면 여러 태그를 한 번에 붙여 넣을 때 잘린다.
- 규칙을 `tagNames.ts`로 떼고 `tagNames.test.ts`(Vitest)로 시험했다. 화면을 띄우지 않고 함수만 부르면 되니 시험이 쉽다.

```ts
  it('붙여 넣은 "바다,산,"은 두 이름을 끝내고 남은 조각은 비어 있다', () => {
    expect(splitDraft('바다,산,')).toEqual({ done: ['바다', '산'], rest: '' })
  })
```

### 5.9 태그 칩과 `/tag/{이름}` 주소

글 상세(`PostPage`)는 태그를 링크로 보여 준다.

```tsx
{post.tags.map((tag) => <Link key={tag} className="chip" to={`/tag/${encodeURIComponent(tag)}`}>#{tag}</Link>)}
```

`encodeURIComponent`는 주소에 그대로 넣으면 뜻이 바뀌는 글자를 `%XX`로 바꾼다. 태그 `C#`을 그대로 넣으면 `/tag/C#`이 되고, 브라우저는 `#` 뒤를 조각(fragment)으로 보아 `/tag/C`를 연다. 인코딩하면 `/tag/C%23`이다. 한글도 `%EC%97%AC...`로 바뀐다(브라우저 주소창은 보기 좋게 한글로 보여 줄 수 있다). Thymeleaf의 `th:href="@{/tag/{name}(name=${tag})}"`가 경로 변수를 알아서 인코딩해 주던 일을 여기서는 직접 한다.

라우터(`app/routes.tsx`)는 이 주소를 블로그 메인 화면으로 보낸다.

```tsx
<Route path="/tag/:tagName" element={<BlogMainPage />} />
```

`BlogMainPage`는 `useParams()`로 `tagName`을 꺼내(이미 디코딩된 값) API 쿼리 문자열 `tag=`에 넣는다. `URLSearchParams`가 다시 인코딩한다. 서버가 404를 주면 `postsNotFound`로 "찾을 수 없음" 화면을 그린다. 목록 제목은 `#태그이름`, 페이지 링크는 `/tag/{이름}?page=2`다.

### 5.10 (스텝 8) 사이드바 태그 목록과 글 수 (T054, TAG-03)

블로그 태그와 각 태그의 글 수를 `GET /api/tags`와 사이드바 `TAG` 모듈(카테고리 다음)로 보여 준다. 응답 한 줄은 `{ id, name, postCount }`, 글 수 많은 순이고 같으면 이름순(이 문서의 `Collator` 비교)이다.

- 글 수는 **보는 사람 기준**이다. 블로그 화면 목록과 같은 조건(`listedIn`)으로 `post JOIN post_tag`를 태그별로 센다(`PostCountRepository.countByTag`). 주인에게는 비공개·숨긴 글도 세고, 다른 사람에게는 볼 수 있는 글만 센다.
- 볼 수 있는 글이 0개인 태그는 **목록에서 빠진다**. 비공개 글에만 단 태그 이름이 새지 않게 하려는 것이고, 4.2에서 미뤄 둔 "아무 글도 쓰지 않는 태그"도 이렇게 화면에서 사라진다. 스텝 16까지는 행이 남아서 관리 화면에서 문제가 됐고, 스텝 17부터는 행도 지운다(5.13).
- 쿼리와 코드 설명은 집계를 다루는 [36](./36-ranking-aggregation.md) 5.2에 있다. 테스트는 `TagIntegrationTest.tagListCountsOnlyPostsTheViewerCanSeeMostUsedFirst`.
- 사이드바에 모듈이 하나 늘어 최근 글·최근 댓글의 위치가 한 칸씩 밀렸다. 사이드바를 위치(`modules[2]`)로 확인하던 다른 테스트 세 개도 함께 고쳤다.

### 5.11 (스텝 9a) `@ManyToMany`에서 `PostTag` 중간 엔티티로

DB는 그대로다(`post_tag(post_id, tag_id)`, 마이그레이션 없음). 바뀐 것은 자바 쪽 매핑과 그것을 쓰는 쿼리 네 곳이다.

`tag/domain/PostTag.java`:

```java
@Entity
@Table(name = "post_tag")
public class PostTag {

    @EmbeddedId
    private PostTagId id = new PostTagId();

    @MapsId("postId")
    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "post_id")
    private Post post;

    @MapsId("tagId")
    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "tag_id")
    private Tag tag;
    ...
}
```

- 키가 두 칸(`post_id`, `tag_id`)이라 **복합 키 클래스** `PostTagId`(`@Embeddable`)를 둔다. JPA는 복합 키 클래스에 `Serializable`과 `equals`·`hashCode`를 요구한다. 키 값이 같으면 같은 행이라는 판단을 이 둘로 하기 때문이다.
- `@EmbeddedId`: 키를 그 클래스 하나로 담는다.
- `@MapsId("postId")`: "키의 `postId` 칸은 이 `post` 연관의 id로 채운다." 이것이 없으면 `post_id` 칸을 키와 연관에서 **두 번** 매핑하게 되어 Hibernate가 오류를 낸다. 글을 처음 저장할 때(아직 id가 없을 때)도, 글이 INSERT되어 id가 생긴 뒤 키를 채워 준다.
- 두 연관 모두 LAZY.

`Post`의 태그 부분:

```java
@OneToMany(mappedBy = "post", cascade = CascadeType.ALL, orphanRemoval = true)
private Set<PostTag> postTags = new LinkedHashSet<>();

public void replaceTags(Collection<Tag> newTags) {
    Set<Long> wanted = newTags.stream().map(Tag::getId).collect(Collectors.toSet());
    postTags.removeIf(postTag -> !wanted.contains(postTag.getTag().getId()));
    Set<Long> current = postTags.stream().map(postTag -> postTag.getTag().getId()).collect(Collectors.toSet());
    newTags.stream()
            .filter(tag -> !current.contains(tag.getId()))
            .forEach(tag -> postTags.add(PostTag.of(this, tag)));
}
```

- `mappedBy = "post"`: 연결 행을 고칠 책임(주인, 3.3)은 `PostTag.post` 쪽에 있다. `Post`는 목록을 들고만 있다.
- `cascade = ALL`: 글에 `PostTag`를 넣고 글을 저장하면 연결 행도 INSERT된다. 그래서 `PostTagRepository`를 따로 두지 않고 예전처럼 `post.replaceTags(...)` 한 줄로 쓴다.
- `orphanRemoval = true`: 목록에서 뺀 `PostTag`(고아)는 DELETE된다.
- `replaceTags`는 이제 **차이만** 반영한다. 빠진 태그의 연결만 빼고, 새 태그의 연결만 더한다. 그대로인 태그는 건드리지 않는다. 비교는 태그 id로 한다(`PostTag`는 `equals`를 따로 두지 않았다).

실제로 나가는 SQL(태그 `spring, jpa`인 글을 `jpa, mysql`로 고칠 때, `show-sql`로 확인):

```
insert into post_tag (post_id,tag_id) values (?,?)        ← mysql 하나
delete from post_tag where post_id=? and tag_id=?          ← spring 하나
```

`jpa`의 행은 그대로다. 이것이 "어떤 SQL이 나가는지 코드에 보인다"는 뜻이다.

**N+1과 `@BatchSize`**: 처음 바꾸고 SQL을 보니 태그 이름을 읽을 때 `select ... from tag where id=?`가 **태그마다** 하나씩 나갔다. `PostTag.tag`가 LAZY라 하나씩 프록시를 초기화하기 때문이다(`@ManyToMany`일 때는 연결 테이블과 태그를 한 번에 읽었다). `Tag` 클래스에 `@BatchSize(size = 10)`를 붙였다. 아직 안 읽은 태그 프록시를 10개까지 모아 `where id in (?, ?, ...)` 한 번으로 읽는다. 글당 태그는 10개까지라 한 번으로 끝난다. ([06](./06-jpa-entity-mapping.md)의 N+1)

쿼리 경로도 연결 엔티티를 거치게 바꿨다.

| 쓰는 곳 | 전 | 후 |
| --- | --- | --- |
| 태그별 글 목록 `PostQueryService.taggedWith` | `root.join("tags").get("id")` | `root.join("postTags").get("tag").get("id")` |
| 검색 `SearchService` | `sameRow.join("tags")` | `sameRow.join("postTags").join("tag")` |
| 태그 글 수 `PostCountRepositoryImpl.countByTag` | `post.join("tags")` | `post.join("postTags")` 후 `get("tag").get("id")` |

동작이 같은지는 원래 있던 테스트(`TagIntegrationTest`의 정리·수정·동시 생성·태그 목록, `SearchIntegrationTest`, `SidebarIntegrationTest`, 글 쓰기·상세 테스트)가 그대로 통과하는 것으로 확인했다. 전체 278개 통과.

### 5.12 (스텝 17) 태그 이름 바꾸기·지우기 (T098, TAG-04)

명세 US11 6번: "같은 블로그에 같은 이름은 둘 수 없고, 태그를 지워도 글은 남는다."

**이름 바꾸기**: 글에 달 때와 **같은 이름 규칙**을 써야 한다. 그래서 `TagNames`에 한 이름용 `normalizeOne`을 더했다(앞뒤 공백·앞의 `#` 떼기, 1~30자, `/` 금지). 규칙을 두 번 쓰면 "글에는 못 다는 이름으로 바꿀 수 있는" 틈이 생긴다.

```java
// TagManageService.rename
String name = TagNames.normalizeOne(rawName);
boolean taken = tagRepository.findByBlogIdAndName(blog.getId(), name)
        .filter(other -> !other.getId().equals(tag.getId()))
        .isPresent();
if (taken) {
    throw new BusinessException(ErrorCode.NAME_TAKEN);
}
tag.rename(name);
tagRepository.saveAndFlush(tag);   // 그 사이 같은 이름이 생기면 DataIntegrityViolation → 409
```

- `findByBlogIdAndName`은 DB 정렬 규칙(`utf8mb4_0900_ai_ci`)으로 비교해서 `JPA`와 `jpa`, `Café`와 `cafe`를 같은 이름으로 찾는다(5.3). **자기 자신은 빼고** 본다. 그래야 `spring` → `Spring`처럼 대소문자만 바꾸는 것이 된다(회원 닉네임과 같은 문제, [38](./38-member-profile-update.md) 3.4).
- 두 태그를 합치기(같은 이름으로 바꾸면 두 태그의 글을 하나로)는 하지 않았다. 409로 막고, 주인이 한쪽을 지우게 한다. 합치기는 글마다 연결을 옮기고 중복 연결을 지워야 해서 따로 기능이 필요하다.

**지우기**: 태그 행만 지우면 된다. 연결(`post_tag`)은 외래 키의 `ON DELETE CASCADE`(3.1)가 같이 지운다.

```java
// TagManageService.delete
tagRepository.delete(find(blog, tagId));
```

- 연결만 지워지므로 **글은 남는다**. 글의 태그 목록에서 그 이름만 빠진다.
- 처음에는 "외래 키가 있으니 연결을 먼저 지워야 한다"고 생각해 `DELETE FROM post_tag WHERE tag_id = ?`를 먼저 보냈다. 스키마를 다시 읽어 보니 `fk_post_tag_tag`에 `ON DELETE CASCADE`가 있었다. 외래 키는 **CASCADE가 없을 때만** 부모 행 삭제를 막는다. 쓸데없는 문장이라 지웠다. 외래 키를 볼 때는 "있다"만 보지 말고 `ON DELETE` 동작까지 본다.
- 글 쪽에서 `post.postTags`를 하나씩 지우는 방법(5.11의 `orphanRemoval`)은 그 태그가 달린 글을 전부 읽어야 한다. DB가 한 번에 지우는 쪽이 낫다. 이 트랜잭션은 글을 읽지 않으므로 영속성 컨텍스트에 옛 연결이 남을 일도 없다.

화면: 관리 "카테고리·태그"의 태그 표에 "이름 변경"(그 자리에서 고치기)과 "삭제"(글 수를 알려 주는 확인 창).

### 5.13 (스텝 17) 글이 하나도 남지 않은 태그는 지운다 (TAG-03, TAG-04)

**발견한 문제.** 스텝 17을 마친 뒤 지원이 "태그 달린 글이 삭제되면 관리창에서 그 태그가 사라지는지 등 여러 경우를 고려해 보라"고 했다. 따져 보니 관리 화면의 태그 표가 블로그 사이드바와 **같은 API**(`GET /api/tags`, 5.10)를 쓰고 있었다. 그 API는 주인에게도 "발행한 글에 달린 태그"만 센다. 그래서 이런 일이 생겼다.

| 경우 | 화면 | DB | 문제 |
| --- | --- | --- | --- |
| 태그가 달린 글을 모두 삭제 | 표에서 사라짐 | 태그 행은 남음 | 다른 태그를 그 이름으로 바꾸면 "이미 있습니다"(409)인데 그런 태그는 표에 없다. `/tag/그이름`은 404가 아니라 빈 목록 |
| 글을 고쳐 태그를 뺌 | 위와 같음 | 위와 같음 | 위와 같음 |
| 임시저장·예약 글에만 단 태그 | 표에 없음 | 있음 | 이름을 바꾸거나 지울 방법이 없다 |
| 비공개 글에만 단 태그 | 주인에게만 보임 | 있음 | 다른 사람이 `/tag/이름`을 열면 빈 목록이라 그 이름이 있다는 것은 알 수 있다 |

뿌리는 하나다. **화면에서는 없는 태그가 DB에는 있다.** 사이드바용 목록은 "보이는 글이 있는 태그만" 거르는 것이 맞다(비공개 글의 태그 이름이 새지 않게). 하지만 그 거르기로 "글 없는 태그"까지 감춰 두니, 감춰진 행이 이름 검사·주소·관리에서 다시 튀어나왔다.

**정한 규칙**(2026-10-11 지원 결정): 지우지 않은 글이 하나도 없는 태그는 **없는 태그다. 서버가 지운다.** 티스토리도 이렇게 동작한다. 다른 방법은 "남겨 두고 관리 표에 글 0개로 보여 주기"였다. 이 방법은 주인이 직접 정리해야 하고, 블로그 화면과 관리 화면에서 "태그가 있다"의 뜻이 달라진다.

**언제 지우나.** 글의 태그가 줄어드는 곳은 두 곳뿐이다. 글을 지울 때(하나 삭제와 글 관리 일괄 삭제는 같은 메서드를 쓴다)와 글을 고칠 때다. 두 곳 모두 **바뀌기 전에 달려 있던 태그 번호**를 들고 있다가, 끝에서 정리를 부른다.

```java
// PostService.delete (요약)
Post post = postRepository.findById(id).orElseThrow();
Set<Long> tagIds = post.tagIds();          // 지우기 전에 달려 있던 태그
post.delete(now);                          // deleted_at만 채운다(소프트 삭제)
tagService.removeUnused(tagIds);           // 그 가운데 남은 글이 없는 태그를 지운다

// PostService.edit (요약)
Set<Long> oldTagIds = post.tagIds();
post.replaceTags(tagService.resolve(blog, command.tagNames()));
...
tagService.removeUnused(oldTagIds);        // 빠진 태그 가운데 남은 글이 없는 것
```

```java
// TagRepository
@Modifying(flushAutomatically = true)
@Query(value = """
        DELETE FROM tag
        WHERE id IN (:tagIds)
          AND NOT EXISTS (SELECT 1 FROM post_tag pt JOIN post p ON p.id = pt.post_id
                          WHERE pt.tag_id = tag.id AND p.deleted_at IS NULL)""", nativeQuery = true)
int deleteUnused(@Param("tagIds") Collection<Long> tagIds);
```

줄별로:
- `WHERE id IN (:tagIds)`: 블로그 태그 전부가 아니라 **방금 영향을 받은 태그만** 본다. 블로그 전체를 훑으면 다른 사람이 막 만든(아직 글에 연결하기 전인) 태그까지 지울 수 있다.
- `NOT EXISTS (... p.deleted_at IS NULL)`: "지우지 않은 글에 연결된 적이 없는" 태그만. 지운 글의 연결은 세지 않는다. 지운 글은 되살리는 기능이 없으므로 그 연결은 의미가 없다.
- 태그 행이 지워지면 `ON DELETE CASCADE`가 지운 글의 연결 행도 같이 지운다.
- `NOT EXISTS`의 부분 쿼리가 바깥 `tag`를 가리킨다(`pt.tag_id = tag.id`). MySQL은 DELETE의 부분 쿼리가 **지우는 표 자신을 FROM에 두는 것**은 막지만(오류 1093), 이렇게 바깥 행을 참조만 하는 것은 된다.
- `flushAutomatically = true`: 이 DELETE는 DB에 직접 가는 SQL이라, 같은 트랜잭션에서 JPA로 바꾼 것(글의 `deleted_at`, `replaceTags`가 지운 연결 행)이 **아직 DB에 안 갔으면** 남은 글을 잘못 센다. 이 옵션은 쿼리 전에 영속성 컨텍스트를 먼저 DB로 보낸다(flush).
  - 실험해 보니 이 옵션을 빼도 테스트는 통과했다. Hibernate는 flush 모드가 기본값(AUTO)이면 네이티브 쿼리 앞에서 스스로 flush한다. 네이티브 SQL은 어느 표를 건드리는지 알 수 없어서다.
  - 그래도 옵션을 남겼다. "이 쿼리는 앞의 변경이 DB에 있어야 맞다"는 의도가 코드에 보이고, Hibernate의 기본 동작에 기대지 않는다.
- `clearAutomatically`는 **켜지 않았다**. 켜면 영속성 컨텍스트가 비워져 `edit`이 돌려주는 글 객체가 관리 밖(detached)이 된다. 그 뒤로 이 트랜잭션은 지워진 태그를 가리키는 연결을 더 바꾸지 않으므로 비울 필요도 없다.

**관리 화면 전용 목록.** 블로그 화면용 `GET /api/tags`는 그대로 두고 `GET /api/manage/tags`(주인만)를 새로 만들었다.

```java
// TagListService.managed (요약)
Map<Long, Long> all = postRepository.countByTag(inBlog(blog).and(ownerView()));        // 지우지 않은 글 전부
Map<Long, Long> published = postRepository.countByTag(listedIn(blog, ownerId, now));   // 블로그 화면에 나오는 글
return tags.map(tag -> new ManagedTag(id, name, all.getOrDefault(id, 0L), published.getOrDefault(id, 0L)))
```

- `postCount`는 임시저장·예약 글까지 센다. 그래서 초안에만 단 태그도 표에 나오고 이름을 바꾸거나 지울 수 있다.
- `publishedCount`가 0이면 그 태그 주소에는 글이 없다(404). 화면은 그때 이름에 링크를 걸지 않고 "1 (발행 0)"처럼 보여 준다.
- 같은 `countByTag`에 조건만 바꿔 두 번 부른다. 가시성 조건을 한 곳(`PostSpecifications`)에 둔 덕이다([16](./16-authorization-visibility.md)).
- Thymeleaf로 치면 같은 표 조각을 블로그 화면과 관리 화면이 함께 쓰다가, 관리 화면에 필요한 칸이 달라져 **관리 화면용 컨트롤러 메서드를 따로** 둔 것이다.

**태그 주소도 같은 규칙.** `/tag/이름`(API `GET /api/posts?tag=`)은 태그가 있어도 **보는 사람이 볼 수 있는 글이 하나도 없으면 404**다.

```java
if (tag != null) {
    condition = condition.and(taggedWith(blog, tag));
    if (!postRepository.exists(condition)) {
        throw new BusinessException(ErrorCode.NOT_FOUND);
    }
}
```

비공개 글에만 단 태그를 다른 사람이 열면, "없는 태그"와 같은 404가 된다. 사이드바에서 빠지는 것과 같은 규칙이다(헌법 원칙 II: 볼 수 없는 것은 있는지도 모르게).

**지워지는 태그에 글을 연결하는 경우.** 태그가 지워질 수 있게 되자 새 경쟁이 생겼다. 글 저장이 "jpa 태그가 있네"라고 읽은 뒤, 커밋 전에 다른 요청이 그 태그를 지운다. 그러면 글 저장은 없는 태그에 연결 행을 넣다가 외래 키 오류(500)를 낸다. 그래서 이미 있는 태그는 **잠그며 다시 읽는다**.

```java
// TagService.resolve (요약)
List<Long> found = tagRepository.findByBlogIdAndNameIn(blog.getId(), names).stream().map(Tag::getId).toList();
lockExisting(found).forEach(tag -> existing.putIfAbsent(tag.getName(), tag));   // select ... where id in (...) for share
```

- 잠금 읽기는 스냅샷이 아니라 **지금 커밋된 행**을 본다. 그사이 지워진 태그는 결과에 없다. 그 이름은 "없는 태그"로 넘어가 새로 만들어진다(5.4의 `INSERT IGNORE`).
- 공유 잠금(`FOR SHARE`)을 쥐고 있는 동안 태그를 지우려는 쪽(배타 잠금이 필요하다)은 이 글 저장이 끝날 때까지 기다린다.

**처음에는 이름으로 잠갔다가 데드락이 났다.** 처음 코드는 `where t.blog.id = :blogId and t.name in :names`에 바로 `FOR SHARE`를 붙였다. 그러자 기존 테스트 `sameNewTagFromConcurrentPostsIsCreatedOnce`(같은 새 태그 `동시`로 글 다섯 개를 동시에 저장)가 `Deadlock found when trying to get lock`으로 깨졌다.

- 이름 `동시`는 아직 **없다**. 없는 값을 인덱스(`UNIQUE(blog_id, name)`)로 잠그며 찾으면, InnoDB는 행이 아니라 그 값이 들어갈 **빈 자리(gap)** 를 잠근다. 나중에 그 자리에 다른 트랜잭션이 끼워 넣지 못하게 하려는 것이다([33](./33-isolation-deadlock.md)).
- 빈 자리 공유 잠금끼리는 서로 막지 않는다. 다섯 트랜잭션이 모두 같은 빈 자리를 잠근다.
- 그다음 각자 `INSERT IGNORE`로 그 자리에 넣으려 한다. 넣으려면 "끼워 넣기 의도" 잠금이 필요한데, 이 잠금은 **남이 쥔 빈 자리 잠금과 부딪친다**. A는 B의 빈 자리 잠금을, B는 A의 빈 자리 잠금을 기다린다. 데드락이다.
- 고친 방법: 잠금 없이 이름으로 찾은 뒤, **찾은 행만 기본 키로 잠근다**. 기본 키로 있는 행을 잠그면 그 행 하나만 잠기고 빈 자리는 잠기지 않는다. 아직 없는 이름은 잠그지 않고 5.4의 `INSERT IGNORE` 경로로 간다.
- 같은 이름이 블로그에 이미 있을 때만 잠금이 생기므로, 새 태그를 동시에 만드는 경우는 스텝 9a와 똑같이 동작한다. 테스트가 다시 통과했다.

**남은 경쟁.** 글 A를 지우는 요청과, 같은 태그로 글 B를 저장하는 요청이 거의 같은 순간에 오면, A의 정리가 B의 연결을 보지 못하고 태그를 지울 수 있다(그러면 B에서 그 태그만 빠진다). 정리 쪽도 잠그면 막을 수 있지만, 같은 주인이 두 탭에서 동시에 해야 생기는 일이라 받아들였다.

확인은 테스트 두 개다. `tagWithNoPostLeftIsRemovedWhenPostsAreDeletedOrUntagged`는 글 삭제와 태그 빼기 뒤 태그가 사라지는지, 404·409를 본다. `manageTagListIncludesDraftOnlyTagsAndTagPageHidesInvisibleOnes`는 관리 목록, 권한, 태그 주소 404를 본다. 브라우저에서는 글 상세의 "삭제"를 누른 뒤 관리 표에서 그 글에만 있던 태그가 사라지는지 보았다. 그 이름으로 다른 태그를 바꿀 수 있는지, 초안 태그가 "1 (발행 0)"으로 링크 없이 나오는지, `/tag/초안태그`가 404 화면인지도 확인했다.

## 6. 자주 하는 실수와 함정

- **태그를 글 표의 문자열 칸에 쉼표로 이어 저장한다.** 태그별 목록이 `LIKE '%spring%'`이 되어 `springboot`까지 걸리고, 이름 바꾸기와 개수 세기가 어려워진다. 다대다는 연결 테이블로.
- **`@ManyToMany`에 `List`를 쓴다.** bag이 되어 수정 때 연결 행을 모두 지우고 다시 넣기 쉽고, 다른 bag과 함께 `join fetch`하면 `MultipleBagFetchException`이 난다. 중복 없는 관계면 `Set`.
- **컬렉션 필드를 새 객체로 바꿔 끼운다.** `this.tags = new HashSet<>(newTags)`는 Hibernate의 추적용 컬렉션을 버린다. 비우고 채운다(`clear` + `addAll`).
- **`@ManyToMany`를 쓴다.** 칸이 없어도 나가는 SQL이 숨고, 칸이 생기면 매핑을 통째로 바꿔야 한다. 처음부터 연결 엔티티(`PostTag`)로 푼다(5.11).
- **연결 엔티티의 다른 쪽을 LAZY로 두고 목록에서 하나씩 꺼낸다.** 태그마다 SELECT가 나간다(N+1). `@BatchSize`나 fetch join으로 묶는다.
- **복합 키 연결 엔티티에서 `@MapsId`를 빠뜨린다.** 같은 칸을 키와 연관에서 두 번 매핑하게 된다.
- **같은 이름 판단이 Java와 DB에서 다르다.** DB 정렬 규칙이 `_cs`나 `_bin`이면 `Spring`과 `spring`이 다른 행이 된다. 반대로 이 프로젝트처럼 `_ai_ci`면 DB가 **악센트까지** 무시한다. Java가 `toLowerCase`로만 비교하면 `cafe`를 새 이름으로 보고 저장하려다 UNIQUE 위반 500이 난다(이 프로젝트에서 실제로 났다, 5.3). Java 비교를 DB 규칙에 맞추고, 최종 판단은 `INSERT IGNORE`로 DB에 맡긴다.
- **"없으면 만들기"를 확인 → INSERT로 한다.** 동시에 두 요청이 "없다"를 확인하면 둘 다 INSERT한다. UNIQUE 제약이 막아 주지만 늦은 쪽은 500이다. `INSERT IGNORE` 뒤에 잠금 읽기로 DB의 행을 가져온다(5.4).
- **`INSERT IGNORE` 뒤 `FOR UPDATE`로 읽는다.** 중복을 만난 트랜잭션들이 이미 공유 잠금을 쥐고 있어, 배타 잠금으로 올리다 데드락이 난다. 읽기만 하면 `FOR SHARE`.
- **태그 목록 주소에 이름을 인코딩하지 않는다.** `#`, `?`, `/`가 든 태그에서 주소가 깨진다. `encodeURIComponent`를 쓴다.
- **점이 든 이름을 확장자로 본다.** 서버의 화면 주소 처리(`SpaForwardController`)는 원래 경로 조각을 `[^.]+`(점이 없는 글자)로만 받아서, `/tag/node.js`를 **새로 열거나 새로고침**하면 404였다(화면 안에서 칩을 누를 때는 브라우저 안 라우터가 처리해 문제가 안 보였다). 태그 주소만 `/tag/{name:.+}`로 따로 받게 고쳤다(`SpaForwardIntegrationTest`).
- **슬래시가 든 이름을 받는다.** `a/b` 태그는 `/tag/a%2Fb`가 된다. Spring Security의 기본 방화벽(`StrictHttpFirewall`)은 인코딩된 슬래시(`%2F`)가 든 주소를 거절해 태그 목록을 열 수 없다. 방화벽을 풀면 경로 조작 공격을 막는 장치를 함께 끄게 되므로, 이 프로젝트는 이름에서 `/`를 막았다(400, spec TAG-01).
- **조합 중 Enter를 처리한다.** 한글 태그의 마지막 글자가 빠지거나 두 번 들어간다. `isComposing`을 먼저 본다.
- **키 이벤트로만 입력을 처리한다.** 붙여 넣기, 자동완성, 음성 입력은 keydown이 없다. 값은 `onChange`에서 본다(5.8의 버그).
- **화면 규칙만 믿는다.** API를 직접 부르면 11개도, 31자도 들어온다. 서버의 `TagNames`가 진짜 검사다.
- **목록에서 감추기만 하고 행은 남긴다.** 감춘 행이 이름 중복 검사, 주소, 관리 화면에서 다시 나타난다. "없는 것"이면 DB에서도 없애거나, 모든 곳에서 같은 기준으로 감춘다(5.13).
- **블로그 화면용 API를 관리 화면에 그대로 쓴다.** 두 화면이 보여 줄 범위(발행 글만 / 초안까지)가 다르면 관리용을 따로 둔다.
- **외래 키의 `ON DELETE`를 보지 않는다.** CASCADE면 자식 행을 먼저 지울 필요가 없다. 없으면 부모 삭제가 막힌다. 둘 다 스키마 한 줄로 갈린다.
- **직접 SQL 전에 flush를 잊는다.** 같은 트랜잭션에서 JPA로 바꾼 것이 아직 DB에 없으면 네이티브 쿼리가 옛 상태를 본다. `@Modifying(flushAutomatically = true)`나 `flush()`.
- **없을 수도 있는 값을 잠그며 찾는다.** InnoDB가 빈 자리를 잠가, 같은 값을 넣으려는 트랜잭션끼리 데드락이 난다. 있는 행만 기본 키로 잠근다.

## 7. 직접 해 보기

준비: `docker compose up -d`, 서버 실행(`./mvnw spring-boot:run`), A 계정으로 로그인한 쿠키 파일 `jarA.txt`. 블로그 주소는 `alpha`라고 하자. dnsmasq를 설정했다면 `--resolve`는 없어도 된다.

### 7.1 태그 달아 발행하고 정리 결과 보기

```bash
R=(--resolve alpha.blog.test:8080:127.0.0.1)
curl -s "${R[@]}" -b jarA.txt -H 'X-Requested-With: XMLHttpRequest' -H 'Content-Type: application/json' \
  -H "Idempotency-Key: $(uuidgen)" -X POST http://alpha.blog.test:8080/api/posts \
  -d '{"title":"태그 실습","contentHtml":"<p>본문</p>","visibility":"PUBLIC","status":"PUBLISHED",
       "tagNames":["spring"," #Security ","Spring","","#"]}'
# {"id":15,...}
curl -s "${R[@]}" http://alpha.blog.test:8080/api/posts/15 | python3 -c "import json,sys;print(json.load(sys.stdin)['tags'])"
# ['Security', 'spring']  — 대문자가 앞(유니코드 순)
```

11개를 보내 `TOO_MANY_TAGS`, 31자 이름을 보내 `fieldErrors[0].field == "tagNames"`도 확인한다.

### 7.2 태그별 목록과 404

```bash
curl -s "${R[@]}" -G http://alpha.blog.test:8080/api/posts --data-urlencode 'tag=SPRING' | python3 -m json.tool | head -20
curl -s "${R[@]}" -G http://alpha.blog.test:8080/api/posts --data-urlencode 'tag=없는태그' -o /dev/null -w '%{http_code}\n'   # 404
```

`--data-urlencode`가 한글을 인코딩해 준다. `-G`는 그 값을 본문이 아니라 쿼리 문자열로 붙이라는 뜻이다.

### 7.3 DB에서 표와 정렬 규칙 보기

```bash
docker exec -it blog-mysql mysql --default-character-set=utf8mb4 -ublog -pblog blog
```

```sql
SELECT t.id, t.name, pt.post_id FROM tag t LEFT JOIN post_tag pt ON pt.tag_id = t.id ORDER BY t.id;
SHOW INDEX FROM tag;                       -- uk_tag_blog_id_name (blog_id, name)
SELECT COLUMN_NAME, COLLATION_NAME FROM information_schema.COLUMNS
 WHERE TABLE_SCHEMA = 'blog' AND TABLE_NAME = 'tag';
SELECT 'café' = 'cafe' COLLATE utf8mb4_0900_ai_ci AS accent_eq,
       'Spring' = 'SPRING' COLLATE utf8mb4_0900_ai_ci AS case_eq,
       'a ' = 'a' COLLATE utf8mb4_0900_ai_ci AS trail_eq;
SELECT 'Spring' = 'SPRING' COLLATE utf8mb4_bin AS bin_eq;   -- 0: 이진 비교는 대소문자를 구분
```

`--default-character-set=utf8mb4`를 빼면 클라이언트 문자 집합이 달라져 `é` 같은 글자의 비교 결과가 틀리게 나올 수 있다. 처음 이 실습을 할 때 실제로 `accent_eq`가 0으로 나왔다가 이 옵션을 주고 1이 됐다.

### 7.4 수정 때 나가는 SQL 보기

`application-dev.yml`에 잠깐 더하고(끝나면 되돌린다) 서버를 다시 띄운다.

```yaml
logging:
  level:
    org.hibernate.SQL: debug
```

글 15의 태그를 `["jpa","mysql"]`로 바꾸는 `PUT /api/posts/15`를 보내고 로그에서 `post_tag`가 들어간 줄을 찾는다. 몇 줄의 DELETE·INSERT가 나가는지, `tag` 표에 INSERT가 몇 번 나가는지 센다. `Set`을 `List`로 바꿔(연습 브랜치에서) 다시 해 보면 차이가 보일 수 있다.

### 7.5 화면

1. 글쓰기 화면의 태그 칸에 `바다` Enter, `산,` 을 친다 → 칩 두 개.
2. 메모장에 `여행,사진,여행`을 써서 복사해 붙여 넣는다 → 칩 `여행`, `사진`(중복 하나 빠짐).
3. 한글로 `고양이`를 치고 마지막 글자 조합 중에 Enter → `고양이` 하나만 달린다.
4. 발행 뒤 글 상세의 `#사진` 칩을 누른다 → `/tag/사진`, 제목이 `#사진`.
5. 주소를 `/tag/없는태그`로 바꿔 연다 → 찾을 수 없음 화면.
6. `node.js` 태그를 달고 그 칩을 누른 뒤 새로고침해 본다. 고치기 전에는 여기서 404였다(6절).
7. 다른 글에 `Café` 태그를 단 뒤 새 글에 `cafe`를 달아 발행한다. 새 태그가 생기지 않고 칩은 `#Café`로 보인다.

### 7.6 테스트

```bash
./mvnw test -Dtest=TagIntegrationTest
cd frontend && npx vitest run src/components/editor/tagNames.test.ts
```

(스텝 17) `./mvnw test -Dtest='PostSettingsIntegrationTest#renameAndDeleteTagsKeepPosts'`. 관리 → 카테고리·태그의 태그 표에서 `spring`을 `Spring`으로 바꾸면 되고, 다른 태그 이름(`JPA`가 있을 때 `jpa`)으로 바꾸면 "같은 이름의 태그가 이미 있습니다."가 뜬다. 태그를 지운 뒤 그 태그가 달렸던 글을 열면 글은 남고 태그만 빠져 있다. DB에서 `SELECT * FROM post_tag WHERE tag_id = {지운 번호};`가 빈다.

(스텝 17, 5.13) 글 하나에만 단 태그를 만들고 그 글을 지운 뒤 관리 표와 DB(`SELECT * FROM tag WHERE name = '그이름';`)를 본다. 둘 다 없어야 한다. 연습 브랜치에서 `deleteUnused`의 `flushAutomatically = true`를 지우고 `tagWithNoPostLeftIsRemovedWhenPostsAreDeletedOrUntagged`를 돌려 보면 그래도 통과한다(Hibernate의 AUTO flush). SQL 로그(`spring.jpa.show-sql: true`)를 켜고, `DELETE FROM tag` 앞에 `update post set deleted_at=...`가 먼저 나가는지 순서를 본다. `findLockedByIdIn` 대신 이름으로 잠그는 쿼리(`where t.blog.id = :blogId and t.name in :names`에 `@Lock(PESSIMISTIC_READ)`)로 바꾸고 `sameNewTagFromConcurrentPostsIsCreatedOnce`를 돌려 데드락 로그를 찾아본다.

`TagNames.normalize`의 `putIfAbsent`를 `put`으로 바꿔 보면(연습 브랜치) 어떤 테스트가 왜 깨지는지 본다.

연습 브랜치에서 `findLockedByBlogIdAndName`의 `PESSIMISTIC_READ`를 `PESSIMISTIC_WRITE`로 바꾸고 `sameNewTagFromConcurrentPostsIsCreatedOnce`를 몇 번 돌려 본다. 로그에서 `Deadlock found when trying to get lock`을 찾는다. `@Lock`을 아예 지우면(평범한 SELECT) 어떻게 되는지도 보고, 이유를 [33](./33-isolation-deadlock.md)과 이어 생각해 본다.

## 8. 확인 문제

1. 글의 태그를 `post` 표의 문자열 칸 하나에 쉼표로 이어 저장하면 생기는 문제를 두 가지 들어라.
<details><summary>답</summary>태그별 글 찾기가 문자열 검색(LIKE)이 되어 느리고 틀린다(<code>spring</code>이 <code>springboot</code>에 걸림). 태그 이름을 바꾸거나 태그별 글 수를 세려면 모든 글의 문자열을 고치거나 뒤져야 한다. 같은 글에 같은 태그가 두 번 들어가는 것도 DB가 막지 못한다.</details>

2. `post_tag`의 기본 키가 `(post_id, tag_id)`인 것이 지켜 주는 것은?
<details><summary>답</summary>같은 글에 같은 태그가 두 번 연결되지 않는다. 연결 한 줄이 "글 X에 태그 Y"라는 사실 하나라서, 두 칸 묶음이 곧 행의 정체다.</details>

3. 이 프로젝트에서 `@ManyToMany`로 충분한 이유와, 연결 엔티티로 바꿔야 하는 때는?
<details><summary>답</summary><code>post_tag</code>에 외래 키 두 칸만 있고 늘 글 쪽에서만 다루기 때문이다. 단 시각, 표시 순서처럼 연결 자체에 칸이 필요해지거나 연결 행을 따로 조회·관리해야 하면 <code>PostTag</code> 엔티티와 1:N 두 개로 바꾼다.</details>

4. `Post.tags`를 `List`가 아니라 `Set`으로 둔 이유는?
<details><summary>답</summary>순서 칸이 없는 List는 Hibernate에서 bag이 되어, 바뀔 때 연결 행을 모두 지우고 다시 넣기 쉽고 bag 여러 개를 한 번에 fetch join하면 예외가 난다. 태그 연결은 중복이 없어야 하므로 Set이 뜻에도 맞다.</details>

5. `replaceTags`가 `this.tags = new LinkedHashSet<>(newTags)`가 아니라 `clear()` + `addAll()`인 이유는?
<details><summary>답</summary>영속 엔티티의 컬렉션은 Hibernate가 변화를 추적하는 래퍼(PersistentSet)다. 필드를 새 객체로 바꾸면 그 추적이 끊긴다. 같은 컬렉션을 비우고 채워야 변경 감지가 연결 행을 바르게 반영한다.</details>

6. 요청이 `tag=SPRING`인데 표에는 `spring`만 있다. 어떻게 찾아지나? 이 동작은 어디서 오나?
<details><summary>답</summary>MySQL 칸의 정렬 규칙이 <code>utf8mb4_0900_ai_ci</code>(대소문자·악센트 무시)라 <code>name = 'SPRING'</code>이 <code>spring</code> 행과 같다고 판단한다. Java 코드가 아니라 DB의 정렬 규칙이 한다. UNIQUE 제약도 같은 규칙으로 중복을 판단한다.</details>

7. `TagService.resolve`가 DB에서 찾은 태그를 `Collator`(PRIMARY) 비교기를 쓰는 지도에 담는 이유는? `toLowerCase` 키였을 때 무슨 일이 있었나?
<details><summary>답</summary>DB는 정렬 규칙(<code>utf8mb4_0900_ai_ci</code>)대로 대소문자와 악센트를 무시하고 찾아 주지만, 돌려준 이름(<code>Café</code>)과 요청 이름(<code>cafe</code>)의 모양은 다를 수 있다. DB와 같은 기준으로 비교해야 "이미 있다"를 판단하고 새 태그를 또 만들지 않는다. <code>toLowerCase</code> 키는 악센트를 구분해서 <code>cafe</code>를 새 태그로 저장하려다 UNIQUE 위반 500이 났다.</details>

8. `["a","A","#a"," a ", ...]`처럼 겹치는 이름을 포함해 11개를 보냈는데 정리 뒤 9개다. 400이 날까?
<details><summary>답</summary>나지 않는다. <code>TagNames.normalize</code>는 정리한 뒤의 개수로 10개를 센다.</details>

9. 태그별 목록은 `join("tags")`를 쓰는데도 같은 글이 두 번 나오지 않는다. 검색은 왜 조인 대신 EXISTS를 쓰나?
<details><summary>답</summary>태그별 목록은 태그 id 하나와 같은지 보므로 글마다 맞는 연결 행이 최대 하나다. 검색은 "이름에 검색어가 들어간 태그"라 한 글의 여러 태그가 동시에 맞을 수 있고, 조인하면 그 수만큼 같은 글이 반복된다. EXISTS는 있는지만 보므로 글이 한 번만 나온다.</details>

10. 붙여 넣은 `바다,산`이 한 태그가 됐던 원인과 고친 방법은?
<details><summary>답</summary>쉼표를 keydown에서만 처리했는데 붙여 넣기는 keydown이 없다. 입력값이 바뀔 때(onChange) 쉼표로 나누도록 바꿨다(<code>splitDraft</code>). 값이 들어오는 모든 길이 onChange를 지난다.</details>

11. 태그 입력에서 `event.nativeEvent.isComposing`을 먼저 확인하는 이유는?
<details><summary>답</summary>한글 같은 IME 입력은 조합 중에 Enter가 조합을 끝내는 데 쓰인다. 이때 태그를 달면 덜 완성된 글자가 들어가거나 Enter가 두 번 처리된다. 조합 중이면 무시한다.</details>

12. 태그 칩 주소에 `encodeURIComponent`를 쓰지 않으면 `C#` 태그는 어떻게 되나?
<details><summary>답</summary><code>/tag/C#</code>이 되어 브라우저가 <code>#</code> 뒤를 조각으로 보고 <code>/tag/C</code>를 연다. 인코딩하면 <code>/tag/C%23</code>이다.</details>

13. 같은 새 태그를 단 글을 동시에 저장할 때 `INSERT IGNORE` 뒤의 읽기가 평범한 SELECT면 안 되는 이유와, `FOR UPDATE`가 아니라 `FOR SHARE`인 이유는?
<details><summary>답</summary>평범한 SELECT는 이 트랜잭션의 옛 스냅샷을 읽어, 다른 트랜잭션이 막 커밋한 태그를 못 볼 수 있다. 잠금 읽기는 최신 커밋을 본다. <code>INSERT IGNORE</code>가 중복을 만나면 그 행에 공유 잠금을 걸어 두므로, 여럿이 배타 잠금으로 올리려 하면 서로 기다려 데드락이 난다. 읽기만 하면 되니 공유 잠금으로 충분하다.</details>

14. (스텝 9a) `@ManyToMany` 대신 `PostTag` 엔티티로 바꾼 이유 세 가지와, `@MapsId`가 하는 일은?
<details><summary>답</summary>연결 테이블에 칸이 생기면 매핑을 통째로 바꿔야 하고, 나가는 INSERT·DELETE가 코드에서 보이지 않으며, ERD의 표와 클래스가 1:1로 맞지 않는다. @MapsId는 복합 키의 칸(postId, tagId)을 연관(post, tag)의 id로 채워서, 같은 칸을 두 번 매핑하지 않게 한다.</details>

15. (스텝 17) 글을 지운 뒤 태그를 정리하는 `DELETE ... NOT EXISTS` 쿼리 앞에서 flush가 필요한 이유는? 이 프로젝트에서 `flushAutomatically`를 빼도 테스트가 통과한 까닭은?
<details><summary>답</summary>글의 <code>deleted_at</code>은 JPA 변경 감지로 바뀌어 flush 전에는 DB에 없다. 그 상태로 직접 SQL을 보내면 글이 아직 살아 있다고 보고 태그를 지우지 않는다. Hibernate는 flush 모드가 AUTO이면 네이티브 쿼리 앞에서 스스로 flush해서 옵션 없이도 통과했다. 옵션은 그 기본 동작에 기대지 않고 의도를 드러내려고 둔다.</details>

16. (스텝 17) 이미 있는 태그를 이름으로 잠그며 찾으면 왜 데드락이 날 수 있나?
<details><summary>답</summary>찾는 이름이 아직 없으면 InnoDB가 그 값이 들어갈 빈 자리(gap)를 잠근다. 빈 자리 공유 잠금끼리는 함께 걸리지만, 그 자리에 INSERT하려면 남의 빈 자리 잠금이 풀리기를 기다려야 한다. 여러 트랜잭션이 같은 새 이름을 넣으려 하면 서로 기다린다. 있는 행만 기본 키로 잠그면 빈 자리가 잠기지 않는다.</details>

## 9. 더 읽을거리

- Hibernate ORM User Guide, "Collections" 장: bag, set, list의 차이와 `@ManyToMany`
- Jakarta Persistence 명세의 `@ManyToMany`, `@JoinTable`
- Vlad Mihalcea, "The best way to use the @ManyToMany annotation with JPA and Hibernate" (Set을 쓰는 이유)
- MySQL 8.4 Reference Manual, "Character Sets, Collations, Unicode" 장과 "Trailing Space Handling in Comparisons"(PAD SPACE와 NO PAD)
- MDN, `KeyboardEvent.isComposing`, `encodeURIComponent()`
- 이 저장소: `erd/schema.sql`의 `tag`, `post_tag`, `data-model.md`의 TAG 부분, `contracts/rest-api.md`의 `GET /api/posts?tag=`
