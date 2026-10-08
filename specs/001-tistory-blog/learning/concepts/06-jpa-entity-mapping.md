# JPA와 엔티티 매핑

> 관련 스텝: [스텝 2](../step-02.md)(엔티티 다섯 개, JPA Auditing), [스텝 3](../step-03.md)(`join fetch`, Specification), [스텝 4](../step-04.md)(`@EntityGraph`, 리포지토리 조각, 상위 N개 조회, 잠금 쿼리)
> 기준 버전: Spring Boot 4.1.1, Spring Data JPA 4, Hibernate 7, MySQL 8.4

## 1. 이 문서로 배우는 것

- ORM이 무엇이고 왜 쓰는지, JPA·Hibernate·Spring Data JPA가 각각 무엇인지
- 엔티티와 영속성 컨텍스트(1차 캐시, 변경 감지, flush, clear), 엔티티 생명주기
- 이미 있는 테이블에 엔티티를 맞추는 방법: `@Id`, `@Column`, `is_` 컬럼, enum, `mediumtext`, 계산 컬럼
- 연관 관계 `@ManyToOne`, 지연 로딩(LAZY)과 프록시, `LazyInitializationException`, N+1 문제와 `join fetch`
- setter 없는 엔티티, 정적 생성 메서드, `protected` 기본 생성자
- `@MappedSuperclass`와 JPA Auditing
- Repository 메서드 이름 쿼리, `@Query`(JPQL), Specification(Criteria API)
- `ddl-auto=validate`가 잡아 주는 것, 트랜잭션 기초
- (스텝 4) `@EntityGraph`로 목록에서 연관 함께 읽기, 리포지토리 조각(custom fragment)으로 집계 쿼리 붙이기, `findBy(spec, ...)`로 개수 쿼리 없이 상위 N개, Specification을 조인에 다시 쓰기, `@Lock` 쿼리 메서드

**먼저 알면 좋은 것**: SQL의 SELECT·JOIN·서브쿼리, 자바 클래스와 인터페이스, [Flyway](./03-flyway-migration.md)(테이블을 누가 만드는지), [Spring Boot 기초](./01-spring-boot-basics.md)(빈, 자동 설정).

## 2. 왜 필요한가

JDBC만으로 회원 한 명을 읽는 코드를 떠올려 보자.

```java
PreparedStatement ps = connection.prepareStatement(
        "SELECT id, email, nickname, role, status FROM member WHERE id = ?");
ps.setLong(1, id);
ResultSet rs = ps.executeQuery();
if (rs.next()) {
    Member m = new Member();
    m.setId(rs.getLong("id"));
    m.setEmail(rs.getString("email"));
    m.setNickname(rs.getString("nickname"));
    m.setRole(Role.valueOf(rs.getString("role")));   // 문자열 → enum 변환도 직접
    ...
}
```

이런 코드는 테이블마다, 쿼리마다 반복된다. 문제는 양만이 아니다.

| 문제 | 예 |
| --- | --- |
| 반복 | SELECT 결과를 객체로 옮기고, 객체를 INSERT 파라미터로 옮기는 코드를 테이블마다 쓴다 |
| 컬럼 추가에 약함 | `member`에 컬럼 하나를 더하면 그 테이블을 쓰는 SQL·매핑 코드를 모두 찾아 고친다 |
| 객체와 테이블의 모양 차이 | 자바는 `post.getBlog().getMember()`처럼 **참조**로 따라가지만, DB는 `post.blog_id`라는 **숫자**로 이어진다 |
| 같은 행, 다른 객체 | 같은 회원을 두 번 읽으면 서로 다른 객체 두 개가 생겨, 하나를 고쳐도 다른 하나는 모른다 |

**ORM(Object-Relational Mapping)**은 "이 클래스는 이 테이블, 이 필드는 이 컬럼"이라는 **매핑 정보**만 주면 SQL 생성과 객체 변환을 대신해 주는 기술이다. 위 코드는 다음 한 줄이 된다.

```java
Member member = memberRepository.findById(id).orElseThrow();
```

## 3. 기본 개념

### 3.1 JPA, Hibernate, Spring Data JPA

세 이름이 섞여 쓰이지만 층이 다르다.

```
 우리 코드        memberRepository.findById(1L)
     │
 Spring Data JPA  인터페이스만 쓰면 구현을 만들어 줌 (JpaRepository, 메서드 이름 쿼리, Specification)
     │
 JPA (Jakarta Persistence)   표준 "규격": @Entity, EntityManager, JPQL, Criteria API  (jakarta.persistence.*)
     │
 Hibernate        JPA 규격을 실제로 구현한 라이브러리 (SQL 생성, 1차 캐시, 프록시)
     │
 JDBC → MySQL 드라이버 → MySQL
```

- **JPA**는 인터페이스와 애노테이션의 묶음이다. 그래서 import가 `jakarta.persistence.Entity`처럼 표준 패키지다.
- **Hibernate**가 그 규격을 구현한다. Spring Boot의 `spring-boot-starter-data-jpa`가 Hibernate를 기본으로 넣는다.
- **Spring Data JPA**는 JPA 위에서 Repository 구현을 자동으로 만들어 주는 Spring 프로젝트다. `MemberRepository`는 인터페이스뿐인데 동작하는 이유가 이것이다.

### 3.2 엔티티

**엔티티(entity)**는 `@Entity`가 붙어 테이블 한 행과 짝이 되는 클래스다.

```java
@Entity                       // JPA가 관리하는 클래스
@Table(name = "member")       // 짝이 되는 테이블
public class Member {
    @Id                                                   // 기본 키
    @GeneratedValue(strategy = GenerationType.IDENTITY)   // 값은 DB가 만든다(AUTO_INCREMENT)
    private Long id;

    @Column(name = "nickname", nullable = false, length = 20)
    private String nickname;
}
```

### 3.3 영속성 컨텍스트

**영속성 컨텍스트(persistence context)**는 "지금 JPA가 관리하고 있는 엔티티들의 보관함"이다. 보통 트랜잭션 하나에 하나가 생기고, `EntityManager`가 이것을 다룬다.

| 기능 | 뜻 | 효과 |
| --- | --- | --- |
| 1차 캐시 | 한 번 읽은 엔티티를 id로 기억 | 같은 트랜잭션에서 같은 id를 다시 찾으면 SQL 없이 같은 객체를 준다 |
| 동일성 보장 | 같은 행 = 같은 객체 | `find(1) == find(1)`이 `true` |
| 변경 감지(dirty checking) | 처음 읽은 상태(스냅숏)와 지금 상태를 비교 | 필드만 바꾸면 커밋할 때 UPDATE가 저절로 나간다. `save()`를 다시 부를 필요 없다 |
| 쓰기 지연 | INSERT·UPDATE를 모았다가 flush 때 보낸다 | (IDENTITY 전략은 예외. 아래 4.2) |

- **flush**: 영속성 컨텍스트의 변경 내용을 SQL로 DB에 **보내는** 것. 커밋 직전, JPQL 쿼리 실행 직전에 자동으로 일어나고 `entityManager.flush()`로 직접 할 수도 있다. flush는 커밋이 아니다(트랜잭션은 계속 열려 있다).
- **clear**: 영속성 컨텍스트를 비운다. 이후 같은 id를 찾으면 DB에서 다시 읽는다.

### 3.4 엔티티 생명주기

```
  new Member(...)                 ← 비영속(new/transient): JPA가 모름
        │ persist() / save()
        ▼
     영속(managed)                ← 영속성 컨텍스트가 관리. 변경 감지 대상
        │ clear() / 트랜잭션 끝 / detach()
        ▼
     준영속(detached)             ← 예전엔 관리됐지만 지금은 아님. 고쳐도 DB에 안 감
        │ remove()(영속 상태에서)
        ▼
     삭제(removed)                ← 커밋 때 DELETE
```

### 3.5 연관 관계와 지연 로딩

```java
@ManyToOne(fetch = FetchType.LAZY)   // 글 여러 개(Many) → 블로그 하나(One)
@JoinColumn(name = "blog_id")        // 외래 키 컬럼 이름
private Blog blog;
```

- 테이블에는 `post.blog_id`(숫자)가 있고, 엔티티에는 `Blog` 객체 참조가 있다. JPA가 둘을 잇는다.
- **EAGER(즉시 로딩)**: 글을 읽을 때 블로그도 바로 함께 읽는다. `@ManyToOne`의 JPA 기본값이다.
- **LAZY(지연 로딩)**: 글만 읽고, 블로그 자리에는 **프록시**(가짜 객체)를 넣어 둔다. `post.getBlog().getName()`처럼 실제 값이 필요해지는 순간 SELECT가 나간다.

```
post.getBlog()          → Blog 프록시 (아직 SQL 없음, id만 알고 있음)
post.getBlog().getId()  → Hibernate는 보통 SQL 없이 id를 준다(프록시가 id를 들고 있음)
post.getBlog().getName()→ 이때 SELECT ... FROM blog WHERE id = ?
```

실무에서는 `@ManyToOne`을 **항상 LAZY로** 둔다. EAGER는 필요 없는 테이블까지 매번 읽고, 목록에서 N+1(아래 4.4)을 숨겨서 만든다.

## 4. 동작 원리

### 4.1 앱이 뜰 때: 매핑 확인 (`ddl-auto=validate`)

`application.yml`의 `spring.jpa.hibernate.ddl-auto` 값에 따라 Hibernate가 시작할 때 하는 일이 다르다.

| 값 | 하는 일 | 이 프로젝트 |
| --- | --- | --- |
| `create` | 테이블을 지우고 엔티티를 보고 새로 만든다 | 쓰면 안 됨(데이터 날아감) |
| `update` | 모자란 컬럼을 더한다(지우지는 않음) | 쓰지 않음(기록이 안 남음) |
| `validate` | **엔티티와 테이블이 맞는지 확인만** 한다. 틀리면 앱이 안 뜬다 | ✅ |
| `none` | 아무것도 안 한다 | — |

테이블은 [Flyway](./03-flyway-migration.md)가 만들고, Hibernate는 확인만 한다. `validate`가 확인하는 것은 **엔티티에 매핑된 테이블과 컬럼이 있는지, 타입이 맞는지**다. 엔티티에 없는 컬럼이 테이블에 더 있는 것은 문제 삼지 않는다. 그래서 계산 컬럼을 매핑하지 않아도 앱이 뜬다.

예: `@Column(name = "is_primary")`를 빼먹고 필드 이름이 `primary`면, Hibernate는 `primary`라는 컬럼을 찾다가 없어서 `Schema-validation: missing column [primary] in table [blog]` 같은 오류로 시작을 멈춘다.

### 4.2 저장할 때 (`save` → INSERT)

`memberRepository.save(member)`가 하는 일:

1. Spring Data의 `SimpleJpaRepository.save()`가 "새 엔티티인가"를 본다. id가 `null`이면 새 것이다.
2. 새 것이면 `entityManager.persist(member)`를 부른다.
3. `IDENTITY` 전략은 **id를 DB가 만들기** 때문에, Hibernate는 persist 순간 바로 INSERT를 보내고 `AUTO_INCREMENT`로 생긴 id를 받아 필드에 넣는다(쓰기 지연이 안 되는 이유).
4. JPA Auditing 리스너가 INSERT 전에 `createdAt`, `updatedAt`을 채운다(4.5).
5. INSERT 문에는 **매핑된 모든 컬럼**이 들어간다. 필드가 `null`이면 DB `DEFAULT`가 아니라 `NULL`이 들어간다. 그래서 `Member` 생성자에서 `role = Role.USER`처럼 값을 직접 넣는다.

### 4.3 읽을 때와 고칠 때

```java
@Transactional
public void rename(Long blogId, String name) {
    Blog blog = blogRepository.findById(blogId).orElseThrow();  // SELECT, 스냅숏 저장
    blog.rename(name);                                           // 필드만 바꿈 (SQL 없음)
}                                                                // 커밋 직전 flush: 스냅숏과 비교 → UPDATE blog SET name=? ...
```

`save()`를 다시 부르지 않아도 UPDATE가 나간다. 이것이 변경 감지다. 단, **트랜잭션 안에서 읽은(영속) 엔티티**여야 한다.

### 4.4 N+1 문제와 `join fetch`

글 10개를 읽고 각 글의 블로그 이름을 찍는다고 하자(LAZY).

```
SELECT * FROM post LIMIT 10                 ← 1번
SELECT * FROM blog WHERE id = 3             ← 글 1의 블로그
SELECT * FROM blog WHERE id = 7             ← 글 2의 블로그
...                                          ← 최대 10번 더
```

처음 쿼리 1번 + 연관 엔티티마다 N번 = **N+1**. 글이 100개면 쿼리가 101번 나간다.

해결 방법 중 가장 기본은 **`join fetch`**다. JPQL에서 "연관 엔티티를 JOIN으로 한 번에 함께 읽어 프록시가 아니라 진짜 객체로 채워라"는 뜻이다.

```sql
-- select p from Post p join fetch p.blog b join fetch b.member where p.id = :id 가 만드는 SQL(개념)
SELECT p.*, b.*, m.* FROM post p
  JOIN blog b ON b.id = p.blog_id
  JOIN member m ON m.id = b.member_id
 WHERE p.id = ?
```

- `join fetch`: 내부 조인. 연관 대상이 반드시 있을 때.
- `left join fetch`: 외부 조인. 연관 대상이 없을 수도 있을 때(예: 이사 안 한 블로그의 `movedToBlog`는 null).

### 4.5 `LazyInitializationException`과 `open-in-view`

LAZY 프록시는 **영속성 컨텍스트가 열려 있을 때만** 진짜 값을 읽어 올 수 있다. 트랜잭션이 끝난 뒤 프록시에 손대면 Hibernate가 `LazyInitializationException`(could not initialize proxy - no Session)을 던진다.

Spring Boot는 기본으로 **Open Session In View(OSIV)**를 켜서, HTTP 요청이 끝날 때까지 영속성 컨텍스트를 열어 둔다. 그러면 컨트롤러나 뷰에서도 지연 로딩이 된다. 대신:

- 요청 내내 DB 커넥션을 붙잡아 커넥션 풀이 빨리 바닥난다.
- 어디서 SQL이 나가는지 코드만 봐서는 알기 어렵다.

이 프로젝트는 `spring.jpa.open-in-view: false`로 껐다. 그래서 **필요한 연관 엔티티는 Repository에서 `join fetch`로 미리 읽어 오는 것**이 규칙이다.

### 4.6 JPA Auditing

1. `@EnableJpaAuditing`이 Auditing 기능을 켠다.
2. `@EntityListeners(AuditingEntityListener.class)`가 붙은 엔티티는 저장·수정 직전에 리스너가 불린다(JPA 콜백 `@PrePersist`, `@PreUpdate` 시점).
3. 리스너가 `@CreatedDate` 필드에는 저장 시각, `@LastModifiedDate` 필드에는 수정 시각을 넣는다.

### 4.7 Spring Data의 쿼리 만드는 세 가지 방법

| 방법 | 예 | 쓰는 때 |
| --- | --- | --- |
| 메서드 이름 쿼리 | `existsByMemberIdAndBlogId(...)` | 조건이 단순할 때 |
| `@Query`(JPQL) | `select b from Blog b join fetch b.member ...` | join fetch, 조건이 이름으로 쓰기 길 때 |
| Specification(Criteria API) | `PostSpecifications.visibleTo(...)` | 조건을 **조합**하거나 실행 중에 바꿀 때 |

메서드 이름 쿼리는 Spring Data가 앱 시작 때 이름을 **파싱**해서 JPQL로 바꾼다.

```
findFirst  By  TargetType And TargetId And Action  OrderBy CreatedAt Desc Id Desc
   │       │      └──────── WHERE 조건 ───────┘           └────── ORDER BY ──────┘
 첫 1건   조건 시작
```

이름이 틀리면(없는 필드) 앱이 **시작할 때** 실패한다. 실행해 봐야 아는 SQL 문자열 오류보다 빨리 알 수 있다.

**JPQL**은 SQL처럼 생겼지만 **테이블이 아니라 엔티티와 필드 이름**을 쓴다. `select b from Blog b where b.address = :address`의 `Blog`는 클래스, `address`는 필드다.

### 4.8 (스텝 4) 목록 조회에 더 쓴 도구

세 가지 방법만으로는 아쉬운 경우가 스텝 4에서 생겼다.

| 하고 싶은 것 | 도구 | 동작 |
| --- | --- | --- |
| Specification 목록에서도 N+1 없이 연관을 함께 읽기 | `@EntityGraph(attributePaths = "category")` | Repository 메서드에 붙이면 그 조회의 SELECT에 연관을 fetch 조인으로 더한다. `join fetch`를 JPQL 문자열 없이 거는 방법이다 |
| 이름으로도, `@Query`로도 만들기 어려운 쿼리(동적 조건 + group by) | **리포지토리 조각(custom fragment)** | 인터페이스 `XxxRepository`를 따로 만들고 구현 클래스를 `XxxRepositoryImpl`로 지으면, Spring Data가 이름 규칙(`Impl` 접미사)으로 찾아 Repository에 끼워 넣는다 |
| 정렬 후 상위 N개만, 전체 개수는 필요 없음 | `JpaSpecificationExecutor.findBy(spec, q -> q.sortBy(...).limit(N).all())` | 흐르는 쿼리(fluent query) API. `Pageable`로 첫 페이지를 받으면 Spring Data가 `Page`를 채우려고 개수(COUNT) 쿼리를 따로 내지만, 이 방법은 목록 쿼리 하나만 나간다 |

**페이지 조회 = 쿼리 두 번**: `findAll(spec, pageable)`은 `Page`를 돌려주므로 목록 SELECT(`LIMIT/OFFSET`)와 전체 개수 `SELECT COUNT(...)`를 함께 실행한다. `@EntityGraph`는 목록 SELECT에만 적용되고, 개수 쿼리에는 fetch 조인이 붙지 않는다(개수를 세는 데 카테고리 이름은 필요 없다).

## 5. 이 프로젝트에서는

코드 경로는 코드 저장소 `src/main/java/com/nhnacademy/blog/` 기준이다.

### 5.1 `blog/domain/Blog.java`: 이미 있는 테이블에 맞춘 엔티티

```java
@Entity
@Table(name = "blog")
public class Blog extends BaseTimeEntity {          // created_at, updated_at은 부모에

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)   // blog.id BIGINT AUTO_INCREMENT
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)              // 자기 자신(blog)을 가리키는 외래 키
    @JoinColumn(name = "moved_to_blog_id")          // NULL이면 이사 안 함
    private Blog movedToBlog;

    @Column(name = "profile_image_id")              // 이미지 엔티티가 아직 없어 숫자로만
    private Long profileImageId;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)  // 주인은 반드시 있다
    @JoinColumn(name = "member_id", nullable = false)
    private Member member;

    @Column(name = "address", nullable = false, updatable = false, length = 32)
    private String address;                         // updatable=false: UPDATE문에 넣지 않음(주소 불변)

    @Column(name = "is_primary", nullable = false)
    private boolean primary;                        // 컬럼은 is_primary, 필드는 primary

    @Enumerated(EnumType.STRING)
    @Column(name = "list_layout", nullable = false, length = 10)
    private ListLayout listLayout;                  // DB에는 'LIST' / 'THUMBNAIL' 문자열
```

- **`is_` 접두사**: 자바 관례상 boolean getter는 `isXxx()`다. 필드 이름을 `isPrimary`로 하면 getter가 `isIsPrimary()`처럼 어색해지고, 일부 라이브러리(JSON 변환 등)가 속성 이름을 `primary`로 읽어 헷갈린다. 그래서 data-model.md 규칙대로 **필드는 접두사 없이, 컬럼 이름은 `@Column`으로** 잇는다. MySQL의 `TINYINT(1)`은 JDBC 드라이버가 boolean으로 다룬다.
- **`EnumType.STRING`**: 기본값 `ORDINAL`은 enum의 **순서 번호**(0, 1, 2…)를 저장한다. 나중에 enum 중간에 값을 끼우면 이미 저장된 숫자의 뜻이 바뀌어 데이터가 조용히 망가진다. 문자열로 저장하면 순서를 바꿔도 안전하고, DB를 직접 봐도 읽힌다. 테이블의 `CHECK (list_layout IN ('LIST','THUMBNAIL'))`와도 짝이 맞는다.
- **계산 컬럼 `primary_owner_id`는 매핑하지 않는다**. V1__init.sql에는 이렇게 있다.

  ```sql
  primary_owner_id BIGINT GENERATED ALWAYS AS
      (CASE WHEN is_primary = 1 AND deleted_at IS NULL THEN member_id END) STORED,
  CONSTRAINT uk_blog_primary_owner_id UNIQUE (primary_owner_id)
  ```

  "회원당 대표 블로그 하나"를 DB가 보장하는 장치다. 값은 DB가 계산하므로, 엔티티에 필드를 두면 Hibernate가 INSERT·UPDATE에 그 컬럼을 넣으려다 MySQL이 거절한다(계산 컬럼에는 값을 쓸 수 없다). 꼭 읽어야 하면 `@Column(insertable = false, updatable = false)`로 둘 수 있지만, 지금은 읽을 일이 없어 아예 두지 않았다. `validate`는 엔티티에 있는 컬럼만 보므로 문제없다. `category.parent_key`도 같다.

### 5.2 `post/domain/Post.java`: `mediumtext`

```java
/** 서버 정화(HtmlSanitizer)를 거친 본문. */
@Column(name = "content_html", nullable = false, columnDefinition = "mediumtext")
private String contentHtml;
```

`String` 필드는 기본적으로 `varchar(255)`로 여겨진다. 테이블은 `MEDIUMTEXT`(최대 약 16MB)라서 `validate`가 타입이 다르다고 실패한다. `columnDefinition`으로 "이 컬럼은 mediumtext"라고 알려 주면 맞춰진다. 블로그 본문은 HTML이라 `TEXT`(64KB)로는 모자랄 수 있어 ERD가 `MEDIUMTEXT`를 골랐다.

### 5.3 setter 없는 엔티티와 생성 메서드: `member/domain/Member.java`

```java
protected Member() {                 // JPA 전용. 리플렉션으로 객체를 만들 때 쓴다
}

private Member(String email, String passwordHash, String nickname) {
    this.email = email;
    this.passwordHash = passwordHash;
    this.nickname = nickname;
    this.role = Role.USER;           // 가입은 항상 USER (DB DEFAULT에 기대지 않음)
    this.status = MemberStatus.ACTIVE;
}

/** 이메일 가입 회원. 가입은 항상 USER다. */
public static Member ofEmail(String email, String passwordHash, String nickname) { ... }

/** 소셜 가입 회원. 이메일·비밀번호가 없다. */
public static Member ofSocial(String nickname) { ... }

/** 지금 정지 중인가. 정지 종료 시각이 지났으면 정지가 아니다. */
public boolean isSuspendedAt(LocalDateTime now) {
    return status == MemberStatus.SUSPENDED && (suspendedUntil == null || suspendedUntil.isAfter(now));
}
```

- **기본 생성자가 왜 필요한가**: JPA는 DB에서 읽은 행으로 객체를 만들 때 **인자 없는 생성자**로 빈 객체를 만든 뒤 필드를 채운다. JPA 규격상 `public` 또는 `protected`여야 한다. `protected`로 두면 우리 코드(다른 패키지)는 실수로 `new Member()`를 부를 수 없다.
- **setter를 두지 않는 이유**: `member.setRole(Role.ADMIN)`이 아무 데서나 가능하면 "관리자는 데이터로만 정한다"(ADMIN-01) 같은 규칙을 코드가 지킬 수 없다. 대신 `ofEmail`, `ofSocial`처럼 **뜻이 있는 이름**으로만 만들게 하고, 상태 변경도 `suspend(...)`처럼 의미 있는 메서드로만 하게 한다(앞으로의 스텝).
- **판단을 엔티티에**: "정지 중인가"는 `status`와 `suspendedUntil` 두 필드로 정해지는 규칙이다. 이것을 엔티티 메서드로 두면 필터·가시성 판단 등 여러 곳이 같은 규칙을 쓴다.

### 5.4 공통 부모와 Auditing: `global/entity/`, `global/config/JpaConfig.java`

```java
@MappedSuperclass                                    // 테이블이 아니다. 필드만 자식에게 물려준다
@EntityListeners(AuditingEntityListener.class)       // 저장·수정 직전에 시각을 채울 리스너
public abstract class BaseCreatedEntity {
    @CreatedDate
    @Column(name = "created_at", nullable = false, updatable = false)  // 한 번 쓰면 안 바뀜
    private LocalDateTime createdAt;
}

@MappedSuperclass
public abstract class BaseTimeEntity extends BaseCreatedEntity {
    @LastModifiedDate
    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;
}
```

```java
@Configuration
@EnableJpaAuditing          // Auditing 켜기
public class JpaConfig {
}
```

- `@MappedSuperclass`와 `@Entity` 상속의 차이: `@Entity` 부모는 그 자체가 테이블이 되고 상속 전략(JOINED 등)이 필요하다. `@MappedSuperclass`는 **필드 정의만 물려주는** 틀이다. `blog` 테이블 하나에 부모 필드까지 다 들어 있다.
- 부모가 둘인 이유: 테이블마다 시각 컬럼이 다르다. `created_at`만(`moderation_log`, `subscription`), 둘 다(`member`, `blog`, `post`, `comment`), `updated_at`만(`category`). `category`는 부모 없이 `@EntityListeners`와 `@LastModifiedDate`를 엔티티에 직접 붙였다.
- `@EnableJpaAuditing`을 `BlogApplication`에 붙이지 않고 별도 설정 클래스에 둔 이유: `@WebMvcTest` 같은 슬라이스 테스트는 JPA를 띄우지 않는데, 메인 클래스에 붙어 있으면 그 테스트에서도 Auditing이 켜지려다 실패한다([테스트](./05-spring-testing.md)).

### 5.5 `join fetch`: `blog/domain/BlogRepository.java`, `post/domain/PostRepository.java`

```java
/** 주소로 찾는다. 삭제된 블로그도 나온다(주소는 영구 예약). 주인과 이사 대상을 함께 읽는다. */
@Query("select b from Blog b join fetch b.member left join fetch b.movedToBlog where b.address = :address")
Optional<Blog> findByAddress(@Param("address") String address);
```

```java
/** 가시성 판단에 필요한 블로그와 블로그 주인을 함께 읽는다. 삭제된 글도 나온다. */
@Query("select p from Post p join fetch p.blog b join fetch b.member where p.id = :id")
Optional<Post> findWithBlogById(@Param("id") Long id);
```

왜 꼭 필요했나: 이 프로젝트는 `open-in-view: false`이고, 이 메서드를 부르는 곳(주소 해석, 가시성 판단, 화면 주소 처리)에는 `@Transactional`이 없다. Repository 메서드가 끝나면 영속성 컨텍스트가 닫힌다. 그 뒤 `blog.getMember().isSuspendedAt(now)`를 부르면, `member`가 프록시일 경우 `LazyInitializationException`이 난다. `join fetch`로 처음부터 진짜 `Member`를 채워 두었기 때문에 안전하다.

- `b.member`는 반드시 있으므로 `join fetch`, `b.movedToBlog`는 없을 수 있으므로 `left join fetch`. 거꾸로 `movedToBlog`에 그냥 `join fetch`를 쓰면 이사하지 않은 블로그는 결과에서 **사라진다**(내부 조인은 짝이 없는 행을 버린다).
- 메서드 이름은 `findByAddress`지만 `@Query`가 붙어 있으면 이름 파싱이 아니라 `@Query`의 JPQL이 쓰인다.

### 5.6 메서드 이름 쿼리: `subscription/domain/SubscriptionRepository.java`, `admin/domain/ModerationLogRepository.java`

```java
boolean existsByMemberIdAndBlogId(Long memberId, Long blogId);
```

- `existsBy`: 있는지 없는지만 본다(행 전체를 읽지 않음).
- `MemberId`: `Subscription.member.id`를 따라간다. 연관 엔티티의 id는 조인 없이 외래 키 컬럼(`member_id`)으로 비교할 수 있다.

```java
Optional<ModerationLog> findFirstByTargetTypeAndTargetIdAndActionOrderByCreatedAtDescIdDesc(
        ModerationTargetType targetType, Long targetId, ModerationAction action);
```

"이 회원의 SUSPEND 기록 중 가장 최근 것 1건"이다. 같은 시각에 기록이 둘이면 순서가 정해지지 않으므로 `IdDesc`를 더해 **항상 같은 결과**가 나오게 했다(정렬 안정성, [페이지네이션](./08-pagination.md)에서 다시 나온다). 이름이 길지만, `@Query`를 쓰는 것보다 실수할 곳이 적어서 이대로 두었다.

### 5.7 Specification과 Criteria API: `global/visibility/PostSpecifications.java`

글 목록은 "누가 보느냐"에 따라 조건이 달라진다(비회원, 회원, 구독자, 주인). 문자열 JPQL을 `if`로 이어 붙이면 실수하기 쉽다. **Specification**은 조건 하나를 객체로 만들어 `and`, `or`로 조합하게 해 준다. 안에서는 JPA **Criteria API**로 조건을 자바 코드로 만든다.

```java
public static Specification<Post> visibleTo(Long viewerId, LocalDateTime now) {
    return (root, query, cb) -> {                         // root = Post, cb = 조건을 만드는 도구
        Join<Post, Blog> blog = root.join("blog");         // JOIN blog
        Join<Blog, Member> owner = blog.join("member");    // JOIN member (블로그 주인)

        Predicate ownerNotSuspended = cb.or(               // 주인이 정지 중이 아님
                cb.notEqual(owner.get("status"), MemberStatus.SUSPENDED),
                cb.and(cb.isNotNull(owner.get("suspendedUntil")),
                        cb.lessThanOrEqualTo(owner.<LocalDateTime>get("suspendedUntil"), now)));

        Predicate audience = cb.equal(root.get("visibility"), Visibility.PUBLIC);
        if (viewerId != null) {                            // 회원이면 "구독 중인 구독자 공개 글"도
            Subquery<Long> subscribed = query.subquery(Long.class);
            var subscription = subscribed.from(Subscription.class);
            subscribed.select(subscription.get("id")).where(
                    cb.equal(subscription.get("blog"), blog),               // 바깥 쿼리의 blog와 연결
                    cb.equal(subscription.get("member").get("id"), viewerId));
            audience = cb.or(audience, cb.and(
                    cb.equal(root.get("visibility"), Visibility.SUBSCRIBERS), cb.exists(subscribed)));
        }

        return cb.and(
                cb.isNull(root.get("deletedAt")),
                cb.isNull(blog.get("deletedAt")),
                cb.equal(root.get("status"), PostStatus.PUBLISHED),
                cb.isFalse(root.get("blinded")),
                cb.isFalse(blog.get("restricted")),
                ownerNotSuspended,
                audience);
    };
}
```

이것이 만드는 SQL을 개념적으로 쓰면:

```sql
SELECT p.* FROM post p
  JOIN blog b   ON b.id = p.blog_id
  JOIN member m ON m.id = b.member_id
 WHERE p.deleted_at IS NULL AND b.deleted_at IS NULL
   AND p.status = 'PUBLISHED' AND p.is_blinded = 0 AND b.is_restricted = 0
   AND (m.status <> 'SUSPENDED' OR (m.suspended_until IS NOT NULL AND m.suspended_until <= ?))
   AND (p.visibility = 'PUBLIC'
        OR (p.visibility = 'SUBSCRIBERS'
            AND EXISTS (SELECT s.id FROM subscription s WHERE s.blog_id = b.id AND s.member_id = ?)))
```

- **상관 서브쿼리**: 서브쿼리 안의 `s.blog_id = b.id`가 바깥 쿼리의 `b`를 가리킨다. 글마다 "그 블로그를 이 사람이 구독하나"를 따진다.
- **`EXISTS`**: 행이 하나라도 있으면 참. 개수를 세지 않아 `COUNT`보다 싸다.
- 사용하는 쪽: `PostRepository`가 `JpaSpecificationExecutor<Post>`를 상속해서 `findAll(spec)`, `findAll(spec, pageable)`, `count(spec)`을 쓸 수 있다. 조합은 `PostSpecifications.inBlog(blogId).and(visibleTo(viewerId, now))`처럼 한다.
- `root.get("deletedAt")`처럼 **필드 이름을 문자열**로 쓴다. 오타는 실행 시점에야 드러난다. 이 프로젝트는 테스트(`PostVisibilityIntegrationTest`)로 이것을 막는다. 문자열 대신 쓸 수 있는 도구로 JPA 메타모델(`Post_.deletedAt`)이나 QueryDSL이 있다.
- 상세 판단(`PostVisibilityPolicy`)과 목록 조건이 **같은 규칙**이어야 한다. 테스트 `listConditionMatchesDetailDecision`이 두 결과가 같은 글을 고르는지 확인한다([권한·가시성](./16-authorization-visibility.md)).

### 5.8 트랜잭션

지금까지(스텝 1~3)는 서비스 클래스가 없어 `@Transactional`을 직접 쓴 곳이 테스트뿐이다. 스텝 4부터 서비스에 붙인다. 기초만 정리한다.

```java
@Service
public class BlogService {
    @Transactional                       // 메서드 시작에 트랜잭션 시작, 정상 끝나면 커밋, RuntimeException이면 롤백
    public Blog open(...) { ... }

    @Transactional(readOnly = true)      // 읽기만: Hibernate가 변경 감지용 스냅숏을 덜 만들고 flush를 하지 않는다
    public Blog find(...) { ... }
}
```

- Spring Data의 기본 Repository 메서드(`findById`, `save` 등)에는 이미 트랜잭션이 붙어 있다. 그래서 Repository를 한 번 부르는 것은 트랜잭션 없이도 된다.
- 여러 Repository 호출을 **하나로 묶어야**(모두 성공 또는 모두 실패) 할 때 서비스에 `@Transactional`을 붙인다. 예: 블로그 개설 + 사이드바 모듈 8개 생성(data-model.md).
- `@Transactional`은 **프록시**로 동작한다. 같은 클래스 안에서 `this.other()`로 부르면 프록시를 거치지 않아 트랜잭션이 적용되지 않는다.
- 테스트 클래스에 붙인 `@Transactional`(예: `PostVisibilityIntegrationTest`)은 테스트가 끝나면 **롤백**한다. 테스트끼리 데이터가 섞이지 않는다.
- 스텝 4에서 실제로 서비스에 붙였다(`BlogService.open`, `AuthService.signup` 등). 위의 "블로그 개설 + 사이드바 모듈 8개"는 사이드바 설정 기능(T086, 백로그)에서 더하고, 스텝 4의 개설은 블로그 행 하나만 만든다. 트랜잭션과 동시 요청, 잠금은 [트랜잭션과 잠금](./23-transactions-locking.md)에서 자세히 다룬다.

### 5.9 (스텝 4) 목록·집계 쿼리

**① `@EntityGraph`로 Specification 목록에 카테고리 함께 읽기**: `post/domain/PostRepository.java`

```java
public interface PostRepository extends JpaRepository<Post, Long>, JpaSpecificationExecutor<Post>,
        PostCountRepository {
    ...
    /**
     * 글 목록(페이지). 목록 한 줄에 카테고리 이름이 나가므로 카테고리를 함께 읽는다(N+1 방지).
     * 개수 쿼리에는 이 fetch가 붙지 않는다.
     */
    @Override
    @EntityGraph(attributePaths = "category")
    Page<Post> findAll(Specification<Post> spec, Pageable pageable);
}
```

- `JpaSpecificationExecutor`가 이미 가진 `findAll(Specification, Pageable)`을 **다시 선언(@Override)**하고 애노테이션만 붙였다. 구현은 Spring Data가 그대로 만들고, 실행할 때 `category`를 fetch 조인으로 더한다.
- 블로그 메인 목록(`PostQueryService.blogPosts`)의 한 줄마다 카테고리 이름(`PostSummaryResponse.category`)이 나간다. 이것이 없으면 10줄에 카테고리 SELECT가 최대 10번 더 나간다(N+1, 4.4).
- 이 Repository의 **모든** `findAll(spec, pageable)` 호출에 적용된다. 카테고리가 필요 없는 페이지 조회에서도 조인이 붙는다는 점은 알고 쓴다.
- 글의 `blog`는 fetch하지 않는다. 목록은 언제나 한 블로그 안이라, 응답의 `blog` 칸은 요청한 블로그(`@CurrentBlog`)로 채운다(`PostSummaryResponse.of(post, blog)`). `post.getBlog()`는 프록시라 트랜잭션 밖에서 `getAddress()`를 부르면 `LazyInitializationException`이다(`getId()`만은 프록시가 이미 알고 있어 괜찮다).

**② 리포지토리 조각으로 카테고리별 글 수**: `post/domain/PostCountRepository.java`, `PostCountRepositoryImpl.java`

```java
public interface PostCountRepository {

    /** 조건에 맞는 글 수를 카테고리별로. 키 null은 미분류다. */
    Map<Long, Long> countByCategory(Specification<Post> condition);

}
```

```java
/**
 * select category_id, count(*) from post where (가시성 조건) group by category_id
 */
class PostCountRepositoryImpl implements PostCountRepository {

    private final EntityManager entityManager;

    PostCountRepositoryImpl(EntityManager entityManager) {
        this.entityManager = entityManager;
    }

    @Override
    public Map<Long, Long> countByCategory(Specification<Post> condition) {
        CriteriaBuilder cb = entityManager.getCriteriaBuilder();
        CriteriaQuery<Tuple> query = cb.createTupleQuery();
        Root<Post> post = query.from(Post.class);
        Join<Post, Category> category = post.join("category", JoinType.LEFT);
        query.multiselect(category.get("id"), cb.count(post))
                .where(condition.toPredicate(post, query, cb))
                .groupBy(category.get("id"));

        Map<Long, Long> counts = new HashMap<>();
        for (Tuple row : entityManager.createQuery(query).getResultList()) {
            counts.put(row.get(0, Long.class), row.get(1, Long.class));
        }
        return counts;
    }

}
```

줄별로:
- `PostRepository extends ..., PostCountRepository`: Repository 인터페이스가 조각 인터페이스도 상속한다. 호출하는 쪽은 `postRepository.countByCategory(...)`로 다른 메서드처럼 쓴다.
- 클래스 이름 `PostCountRepositoryImpl`: **조각 인터페이스 이름 + `Impl`**. Spring Data가 이 이름으로 구현을 찾아 Repository 프록시에 연결한다. 이름이 다르면 구현이 연결되지 않아, Spring Data가 `countByCategory`를 메서드 이름 쿼리로 해석하려 한다. 원하는 쿼리가 아니므로 시작이나 호출 때 오류가 난다.
- `EntityManager`: JPA의 핵심 객체. Spring Data 없이 직접 쿼리를 만들고 실행할 때 쓴다. 생성자로 주입받는다.
- `createTupleQuery()` + `multiselect(...)`: 엔티티 하나가 아니라 **값 여러 개**(카테고리 id, 개수)를 한 행으로 받는다. `Tuple`은 그런 행이다.
- `post.join("category", JoinType.LEFT)`: 미분류 글(category NULL)도 세려면 외부 조인이어야 한다. 내부 조인이면 미분류가 사라진다(5.5와 같은 이유).
- `condition.toPredicate(post, query, cb)`: 밖에서 받은 Specification(가시성 조건)을 이 쿼리에 그대로 끼운다. **목록과 개수가 같은 조건**을 쓰게 하는 핵심이다([가시성](./16-authorization-visibility.md)).
- `groupBy(category.get("id"))`: SQL `GROUP BY category_id`. 결과 맵에서 키 `null`이 미분류 수다(`HashMap`은 null 키를 허용한다).
- 쓰는 곳: `category/application/CategoryTreeService.tree()`가 이 맵으로 트리 노드마다 글 수를 붙이고, 하위 카테고리 수를 상위에 더한다.

**③ `findBy`로 상위 5개만**: `blog/application/SidebarService.java`

```java
private List<Sidebar.RecentPost> recentPosts(Blog blog, Long viewerId, LocalDateTime now) {
    return postRepository.findBy(PostSpecifications.listedIn(blog, viewerId, now),
                    query -> query.sortBy(LATEST_POSTS).limit(RECENT_SIZE).all())
            .stream()
            .map(post -> new Sidebar.RecentPost(post.getId(), post.getTitle()))
            .toList();
}
```

- `findBy(spec, 함수)`: 조건(spec)을 주고, 함수 안에서 정렬(`sortBy`), 개수 제한(`limit`), 결과 모양(`all()`은 List)을 고른다.
- `LATEST_POSTS`는 `Sort.by(desc("publishedAt"), desc("id"))`, `RECENT_SIZE`는 5. 실행되는 SQL은 `... ORDER BY published_at DESC, id DESC LIMIT 5` 하나다. 사이드바는 "전체 몇 개"가 필요 없으니 COUNT 쿼리를 낼 이유가 없다.
- `CommentRepository`도 `JpaSpecificationExecutor<Comment>`를 상속해 최근 댓글 5개를 같은 방식으로 읽는다.

**④ Specification을 조인에 다시 쓰기**: `global/visibility/PostSpecifications.java`

스텝 3의 `visibleTo`는 `root`(글이 FROM의 주인공)에서만 쓸 수 있었다. 사이드바 최근 댓글은 FROM의 주인공이 **댓글**이고 글은 조인 대상이다. 그래서 조건을 `From<?, Post>`(Root와 Join의 공통 부모 타입)를 받는 메서드로 꺼냈다.

```java
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

```java
// SidebarService.recentComments
Specification<Comment> condition = (root, query, cb) -> {
    Join<Comment, Post> post = root.join("post");          // FROM comment JOIN post
    return cb.and(cb.isNull(root.get("deletedAt")),
            PostSpecifications.listedIn(post, query, cb, blog, viewerId, now));
};
```

- `Root<Post>`도 `Join<Comment, Post>`도 `From<?, Post>`다. 그래서 같은 조건 코드를 글 목록과 댓글 목록이 함께 쓴다. 볼 수 없는 글의 댓글이 사이드바에 새는 일을 규칙 하나로 막는다(헌법 원칙 II).
- 조건 내용(주인은 왜 발행 글 전부인지)은 [가시성](./16-authorization-visibility.md)에서 설명한다.

**⑤ 파생 쿼리와 잠금 쿼리**

```java
// blog/domain/BlogRepository.java
boolean existsByAddress(String address);       // 삭제된 블로그 주소도 true(영구 예약)

@Query("select count(b) from Blog b where b.member.id = :memberId and b.deletedAt is null")
long countActiveByMemberId(@Param("memberId") Long memberId);

// subscription/domain/SubscriptionRepository.java
long countByBlogId(Long blogId);               // SELECT COUNT(*) ... WHERE blog_id = ?

// category/domain/CategoryRepository.java
List<Category> findByBlogIdOrderBySortOrderAscIdAsc(Long blogId);

// member/domain/MemberRepository.java
@Lock(LockModeType.PESSIMISTIC_WRITE)
@Query("select m from Member m where m.id = :id")
Optional<Member> findByIdForUpdate(@Param("id") Long id);
```

- `countBy...`: 개수만 센다. `existsBy...`와 같이 행을 읽어 오지 않는다.
- `countActiveByMemberId`는 "삭제 안 됨" 조건이 붙어 이름으로 쓰기 어색해서 `@Query`로 썼다. `@Query`가 있으면 이름은 아무렇게나 지어도 된다.
- `OrderBySortOrderAscIdAsc`: 주인이 정한 순서, 같으면 만든 순서. 정렬을 이름에 넣으면 호출할 때 `Sort`를 넘기지 않아도 된다.
- `@Lock(PESSIMISTIC_WRITE)`: MySQL에서는 `SELECT ... FOR UPDATE`가 된다. 트랜잭션 안에서만 의미가 있다(트랜잭션이 끝날 때 잠금이 풀린다). 블로그 개설이 같은 회원의 동시 요청을 한 줄로 세우는 데 쓴다. 자세한 내용은 [트랜잭션과 잠금](./23-transactions-locking.md).

**⑥ `open-in-view: false`에서 응답 만들기**

스텝 4에서 서비스가 생기자 "트랜잭션이 끝난 뒤 컨트롤러가 응답 DTO를 만들 때 지연 로딩이 터지지 않게" 하는 규칙이 필요해졌다. 이 프로젝트는 세 가지를 쓴다.

| 방법 | 예 |
| --- | --- |
| 필요한 연관을 미리 읽기 | `@EntityGraph`(①), `findByAddress`의 `join fetch`(`BlogService.updateInfo`가 이것으로 다시 읽음) |
| 트랜잭션 안에서 값을 꺼내 기록(record)으로 넘기기 | `SidebarService`가 댓글 작성자 닉네임을 트랜잭션 안에서 꺼내 `Sidebar.RecentComment`로 만든다 |
| 이미 읽힌 엔티티를 쓰기 | `BlogService.open`이 잠금으로 읽은 `Member`를 새 블로그에 넣어, 트랜잭션 밖에서도 주인 닉네임을 읽을 수 있다 |

계층마다 무엇을 넘기는지는 [계층 구조와 DTO](./24-layered-architecture-dto.md)에서 다룬다.

## 6. 자주 하는 실수와 함정

| 실수 | 결과 | 이 프로젝트의 대책 |
| --- | --- | --- |
| `@Enumerated`를 빼먹음 | 기본값 ORDINAL → 숫자로 저장, `validate`에서 타입 불일치 | 모든 enum에 `EnumType.STRING` |
| `@ManyToOne`을 EAGER로 둠 | 필요 없는 조인, 목록에서 N+1 | 전부 LAZY |
| 트랜잭션 밖에서 LAZY 연관에 접근 | `LazyInitializationException` | 필요한 연관은 `join fetch` |
| `join fetch`를 컬렉션(`@OneToMany`)에 쓰고 페이지네이션 | Hibernate가 경고를 내고 **메모리에서** 자른다 | 아직 `@OneToMany`를 쓰지 않음 |
| 계산 컬럼을 그냥 매핑 | INSERT 때 MySQL 오류 | 매핑하지 않음 |
| DB DEFAULT에 기대고 필드를 null로 둠 | NOT NULL 컬럼에 NULL INSERT → 오류 | 생성자에서 기본값 지정 |
| 테스트에서 `jdbcTemplate.update(...)`로 바꾼 뒤 같은 트랜잭션에서 엔티티를 다시 읽음 | 1차 캐시 때문에 **바뀌기 전 값**이 나온다 | `flush()` 후 SQL 실행, 그다음 `clear()`(`PostVisibilityIntegrationTest.sql()`) |
| `equals/hashCode`를 모든 필드로 만듦 | 프록시·지연 로딩과 섞여 이상하게 동작 | 엔티티에 만들지 않음 |
| 엔티티를 그대로 JSON 응답으로 | LAZY 프록시 직렬화 오류, 비밀번호 해시 같은 필드 노출 | 스텝 4부터 응답 DTO(`presentation/dto`)를 따로 둔다 |
| 상위 N개만 필요한데 `findAll(spec, PageRequest.of(0, 5))` | `Page`를 채우려고 COUNT 쿼리가 하나 더 나감 | `findBy(spec, q -> q.sortBy(...).limit(5).all())` (5.9 ③) |
| 조각 구현 클래스 이름을 `PostCountRepositoryImplementation` 등으로 지음 | Spring Data가 구현을 못 찾고 메서드 이름 쿼리로 해석하려다 오류 | `{조각 인터페이스 이름}Impl` (5.9 ②) |
| 미분류까지 세는 집계에 내부 조인 | category가 NULL인 글이 집계에서 사라짐 | `JoinType.LEFT` |
| `@Lock` 메서드를 서비스 트랜잭션 밖에서 부름 | 잠금은 그 메서드를 감싼 트랜잭션이 끝날 때 풀린다. "읽고 → 확인하고 → 저장"을 한 트랜잭션으로 묶지 않으면 그 사이를 지켜 주지 못한다 | 잠금 메서드는 `@Transactional` 서비스 메서드 안에서 부른다 |

## 7. 직접 해 보기

1. **validate가 잡는 것 보기**
   - `Blog.java`의 `@Column(name = "is_primary", nullable = false)`를 `@Column(nullable = false)`로 바꾼다.
   - `./mvnw test -Dtest=BlogApplicationTests`
   - 기대: 컨텍스트 시작 실패, 로그에 `Schema-validation: missing column [primary] in table [blog]`. 확인 후 되돌린다.

2. **SQL 눈으로 보기**
   - `application-dev.yml`에 임시로 다음을 넣는다.
     ```yaml
     spring:
       jpa:
         show-sql: true
         properties:
           hibernate:
             format_sql: true
     ```
   - `./mvnw test -Dtest=PostVisibilityIntegrationTest` 실행 후 로그에서 `join` 과 `exists`가 들어간 SELECT를 찾는다. 5.7의 SQL과 비교한다. 확인 후 되돌린다.

3. **join fetch를 빼면**
   - `PostRepository.findWithBlogById`의 JPQL에서 `join fetch b.member`를 지운다.
   - `./mvnw test -Dtest=SpaForwardIntegrationTest`
   - 기대: 블로그 주인 정보를 읽는 곳에서 `LazyInitializationException`(또는 그로 인한 500). 왜 그런지 4.5와 연결해 설명해 본다. 되돌린다.

4. **1차 캐시 체험**
   - `PostVisibilityIntegrationTest.sql()`에서 `entityManager.clear();`를 지우고 `blindedPostIsShownOnlyToOwnerWithFlag`를 돌린다.
   - 기대: SQL로 `is_blinded = 1`로 바꿨는데 엔티티는 여전히 `false`라 테스트가 실패한다. 되돌린다.

5. **(스텝 4) 페이지 조회는 쿼리 두 번, findBy는 한 번**
   - 2번처럼 `show-sql`을 켜고 `./mvnw test -Dtest=BlogPostListIntegrationTest#latestFirstTenPerPageAndTieBrokenById`를 돌린다.
   - 기대: 글 목록 SELECT(`left join category`, `limit`)와 `select count(...)`가 짝으로 보인다. 개수 쿼리에는 category 조인이 없는 것도 확인한다.
   - 이어서 `./mvnw test -Dtest=SidebarIntegrationTest#recentPostsAreLatestFiveVisibleOnes` — 최근 글 SELECT는 `limit 5` 하나뿐이고 count가 없다.

6. **(스텝 4) @EntityGraph를 빼면**
   - `PostRepository`의 `@EntityGraph(attributePaths = "category")` 줄을 지우고 `BlogPostListIntegrationTest#filtersByCategoryIncludingChildrenAndUncategorized`를 돌린다.
   - 기대: 응답을 만들 때(트랜잭션 밖) `post.getCategory().getName()`이 프록시라 `LazyInitializationException` → 500으로 실패한다. 되돌린다.

7. **ORDINAL의 위험**
   - 종이에: `enum PostStatus { DRAFT, PUBLISHED, SCHEDULED }`를 ORDINAL로 저장했다고 하자. 중간에 `REVIEW`를 끼워 `{ DRAFT, REVIEW, PUBLISHED, SCHEDULED }`가 되면, DB에 `1`로 저장된 기존 발행 글은 무엇이 되는가?

## 8. 확인 문제

1. JPA, Hibernate, Spring Data JPA는 각각 무엇인가? `jakarta.persistence.Entity`는 어디에 속하나?
   <details><summary>답</summary>JPA는 자바의 ORM 표준 규격(인터페이스·애노테이션), Hibernate는 그 구현체, Spring Data JPA는 JPA 위에서 Repository 구현을 자동으로 만들어 주는 Spring 프로젝트다. <code>jakarta.persistence.Entity</code>는 JPA 규격에 속한다.</details>

2. 트랜잭션 안에서 `blog.rename("새 이름")`만 부르고 `save()`를 부르지 않았다. UPDATE가 나가는가? 나간다면 언제인가?
   <details><summary>답</summary>나간다. 영속 상태 엔티티는 변경 감지 대상이라, 커밋 직전 flush 때 처음 읽은 스냅숏과 비교해 바뀐 필드로 UPDATE를 만든다.</details>

3. 이 프로젝트에서 `primary_owner_id` 컬럼을 엔티티에 두지 않았는데도 `ddl-auto=validate`가 통과하는 이유는?
   <details><summary>답</summary>validate는 엔티티에 매핑된 테이블·컬럼이 DB에 있는지와 타입을 확인한다. 테이블에만 있고 엔티티에 없는 컬럼은 확인하지 않는다.</details>

4. `findByAddress`에서 `b.movedToBlog`에 `left join fetch` 대신 `join fetch`를 쓰면 어떤 블로그가 조회되지 않는가?
   <details><summary>답</summary>이사하지 않은(moved_to_blog_id가 NULL인) 블로그. 내부 조인은 짝이 없는 행을 버린다. 대부분의 블로그가 조회되지 않게 된다.</details>

5. `open-in-view`를 끈 상태에서 `post.getBlog().getMember().getStatus()`를 트랜잭션 밖에서 부르면 어떻게 되는가? 어떻게 막나?
   <details><summary>답</summary>blog나 member가 LAZY 프록시라면 LazyInitializationException이 난다. Repository에서 join fetch로 필요한 연관을 미리 읽어 오거나(이 프로젝트 방식), 서비스 메서드를 @Transactional로 감싸 그 안에서 접근한다.</details>

6. 글 20개 목록을 그리면서 각 글의 블로그 이름을 LAZY로 읽으면 쿼리가 최대 몇 번 나가나? 이 문제를 무엇이라 부르나?
   <details><summary>답</summary>최대 21번(목록 1번 + 글마다 1번). N+1 문제. 같은 블로그는 1차 캐시 덕에 한 번만 읽으므로 실제로는 서로 다른 블로그 수만큼이다.</details>

7. 엔티티의 기본 생성자를 `private`이 아니라 `protected`로 두는 이유는?
   <details><summary>답</summary>JPA 규격이 public 또는 protected 기본 생성자를 요구한다(Hibernate가 객체를 만들고 지연 로딩 프록시를 하위 클래스로 만들 때 필요). protected면 다른 패키지의 우리 코드는 부를 수 없어, 정적 생성 메서드로만 만들게 할 수 있다.</details>

8. `findFirstByTargetTypeAndTargetIdAndActionOrderByCreatedAtDescIdDesc`에서 `IdDesc`를 뺀다면 어떤 문제가 생길 수 있나?
   <details><summary>답</summary>created_at이 같은 기록이 둘 이상이면 어느 것이 "첫 번째"인지 DB가 보장하지 않는다. 같은 요청에도 다른 사유가 나올 수 있다. id로 순서를 확정해야 결과가 항상 같다.</details>

9. (스텝 4) `findAll(spec, pageable)`에 `@EntityGraph(attributePaths = "category")`를 붙였다. 목록 SELECT와 개수 쿼리에는 각각 어떤 변화가 있나?
   <details><summary>답</summary>목록 SELECT에는 category가 fetch 조인으로 더해져 글마다 카테고리를 따로 읽지 않는다(N+1 방지). 개수 쿼리에는 fetch 조인이 붙지 않는다.</details>

10. (스텝 4) 사이드바 최근 댓글에 "볼 수 없는 글의 댓글 제외" 조건을 걸 때 `PostSpecifications.visibleTo(Long, LocalDateTime)`(Specification<Post>)를 그대로 쓸 수 없었던 이유와 해결 방법은?
    <details><summary>답</summary>Specification&lt;Post&gt;는 글이 쿼리의 Root일 때 쓰는데, 최근 댓글 쿼리의 Root는 댓글이고 글은 Join이다. 조건을 Root와 Join의 공통 타입 <code>From&lt;?, Post&gt;</code>를 받는 메서드(<code>listedIn(From, query, cb, ...)</code>)로 꺼내, 댓글 → 글 조인에도 같은 조건을 붙였다.</details>

11. (스텝 4) `PostCountRepositoryImpl`을 Spring Data가 어떻게 찾아 `PostRepository`에 연결하나?
    <details><summary>답</summary><code>PostRepository</code>가 조각 인터페이스 <code>PostCountRepository</code>를 상속하고, Spring Data가 "조각 인터페이스 이름 + Impl" 이름의 클래스를 찾아 그 메서드의 구현으로 쓴다.</details>

## 9. 더 읽을거리

- Jakarta Persistence 3.2 명세 — 엔티티, 영속성 컨텍스트, JPQL, Criteria API의 원문: https://jakarta.ee/specifications/persistence/
- Hibernate ORM User Guide — 지연 로딩, 프록시, fetch 전략, 스키마 검증: https://hibernate.org/orm/documentation/
- Spring Data JPA Reference — 메서드 이름 쿼리 키워드 표, `@Query`, Specification, Auditing: https://docs.spring.io/spring-data/jpa/reference/
- Spring Data JPA Reference의 "Custom Repository Implementations"(조각과 `Impl` 접미사), "Entity Graphs", "Fluent Query API"(`findBy`), "Locking"
- Spring Boot Reference의 "Data Access" 장 — `spring.jpa.*` 설정, Open Session In View 경고
- 이 저장소: [data-model.md](../../data-model.md)(컬럼 규칙), [erd/schema.sql](../../erd/schema.sql)
