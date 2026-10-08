# 27. 소프트 삭제와 일괄 수정

> 관련 스텝: [스텝 5](../step-05.md) (T029, T032, T033, T034, T040) · 관련 개념: [06-jpa-entity-mapping](./06-jpa-entity-mapping.md), [16-authorization-visibility](./16-authorization-visibility.md), [23-transactions-locking](./23-transactions-locking.md), [24-layered-architecture-dto](./24-layered-architecture-dto.md)

## 1. 이 문서로 배우는 것

- 하드 삭제와 소프트 삭제의 차이, 이 프로젝트가 글을 소프트 삭제하는 이유(헌법 III, Q3)
- 소프트 삭제를 하면 모든 조회에 "삭제 안 됨" 조건이 들어가야 하는 이유
- 글을 지울 때 딸린 데이터(댓글·공감·알림)를 어떻게 다루는지, 왜 한 트랜잭션인지
- JPA 변경 감지(dirty checking): `save()` 없이 수정이 저장되는 원리
- 일괄 수정: `@Modifying` JPQL과 네이티브 쿼리
- 일괄 수정이 영속성 컨텍스트를 건너뛰는 함정과 `clearAutomatically`
- MySQL `ON UPDATE CURRENT_TIMESTAMP`와 JPA Auditing의 차이, 수정 시각을 지키는 `p.updatedAt = p.updatedAt`
- 카테고리 삭제 시 글을 미분류로 옮기기, 하위가 있으면 409

**먼저 알면 좋은 것**: 엔티티와 영속성 컨텍스트([06](./06-jpa-entity-mapping.md)), `@Transactional`([23](./23-transactions-locking.md)), 글 가시성 조건([16](./16-authorization-visibility.md)).

## 2. 왜 필요한가

글 삭제를 `DELETE FROM post WHERE id = 15`로 하면 간단하다. 그런데 이 프로젝트에는 이런 요구가 있다.

- **헌법 원칙 III "공유된 주소는 깨지지 않는다"**: 글 번호는 플랫폼 전체에서 하나이고 다시 쓰지 않는다. 지운 글의 주소는 404가 되어야지, 다른 글로 이어지면 안 된다.
- **기록은 남는다**: spec POST-03 "삭제는 소프트 삭제다(기록은 남고 사용자에게만 사라짐)". 신고·관리 이력(관리자가 숨긴 글을 작성자가 지웠는지 등)을 나중에 따라갈 수 있어야 한다.
- **Q3 결정**: 지원이 2026-10-07에 "글 삭제 방식 = 소프트 삭제"로 정했다.

한편 글을 지우면 딸린 것도 정리해야 한다. spec: "그 글의 댓글·공감·알림도 함께 사라진다. 블로그 글 수·공감 수 같은 수치에서도 바로 빠진다."

딸린 것이 여러 행이면 엔티티를 하나씩 읽어 고치는 대신 SQL 한 번으로 바꾸는 **일괄 수정**이 필요하다. 카테고리를 지울 때 그 카테고리의 글 수십 개를 미분류로 옮기는 것도 같다. 그리고 일괄 수정에는 JPA를 쓸 때 꼭 알아야 할 함정이 있다(4.3).

## 3. 기본 개념

### 3.1 하드 삭제와 소프트 삭제

| | 하드 삭제 | 소프트 삭제 |
| --- | --- | --- |
| 방법 | `DELETE FROM post ...` | `UPDATE post SET deleted_at = NOW() ...` |
| 행 | 사라짐 | 남음 |
| 되살리기 | 백업에서만 | `deleted_at = NULL` |
| 조회 | 신경 쓸 것 없음 | **모든 조회에 `deleted_at IS NULL`** |
| 번호(AUTO_INCREMENT) | 다시 쓰이지는 않지만, 행이 없어 "지운 글인지 없던 번호인지" 모름 | 지운 글이라는 사실이 남음 |
| 저장 공간 | 줄어듦 | 계속 쌓임 |

소프트 삭제의 가장 큰 비용은 **잊어버리기 쉬운 조건**이다. 목록 한 곳에서 `deleted_at IS NULL`을 빼먹으면 지운 글이 다시 보인다. 그래서 이 프로젝트는 그 조건을 한 곳(`PostSpecifications`, `PostVisibilityPolicy`)에 모아 모든 조회가 거기를 지나게 했다([16](./16-authorization-visibility.md)).

### 3.2 영속성 컨텍스트와 변경 감지

JPA는 트랜잭션마다 **영속성 컨텍스트**라는 작업 공간을 둔다. 트랜잭션 안에서 `findById`로 읽은 엔티티는 이 공간에 올라가고, JPA는 읽을 때의 값(스냅숏)을 기억한다.

트랜잭션이 끝날 때(커밋 직전, flush) JPA는 공간 안의 엔티티를 스냅숏과 비교해 **바뀐 칸이 있으면 UPDATE를 직접 만든다**. 이것이 **변경 감지(dirty checking)**다.

```java
@Transactional
public void rename(Long id, String name) {
    Category category = repository.findById(id).orElseThrow(); // 공간에 올라감 + 스냅숏
    category.rename(name);                                      // 필드만 바꿈
}                                                               // 커밋 전 비교 → UPDATE category SET name=?
```

`save()`를 부르지 않아도 저장된다. 조건은 두 가지다.

1. 엔티티가 **지금 트랜잭션의 영속성 컨텍스트에 있어야** 한다(다른 트랜잭션에서 읽어 온 엔티티는 "준영속"이라 비교 대상이 아니다).
2. 트랜잭션이 **커밋되어야** 한다(예외로 롤백되면 UPDATE도 없다).

### 3.3 일괄 수정(bulk update)

변경 감지는 엔티티 하나씩이다. 글 100개를 미분류로 옮기려면 100개를 읽고 100번 UPDATE한다. 그 대신 SQL 한 문장으로 바꾸는 것이 일괄 수정이다.

```sql
UPDATE post SET category_id = NULL WHERE category_id = 7
```

Spring Data JPA에서는 리포지토리 메서드에 `@Query`로 UPDATE/DELETE 문을 적고 **`@Modifying`**을 붙인다. `@Modifying`이 없으면 Spring Data는 그 쿼리를 조회로 보고 실행하다 실패한다. 돌려주는 `int`는 바뀐 행 수다.

| 종류 | 쓰는 언어 | 이 프로젝트 예 |
| --- | --- | --- |
| JPQL 일괄 수정 | 엔티티 이름·필드 이름(`Post p`, `p.category`) | `uncategorize`, `softDeleteByPostId` |
| 네이티브 일괄 수정 | 테이블·컬럼 이름(`post_like`, `post_id`), `nativeQuery = true` | `deleteLikes`, `deleteNotifications` |

네이티브 쿼리를 쓴 이유: 공감(`post_like`)과 알림(`notification`) 엔티티는 아직 없다(공감은 스텝 7, 알림은 백로그). 엔티티가 없으면 JPQL에서 이름을 쓸 수 없으므로 테이블에 직접 쓴다. 엔티티가 생기면 JPQL로 바꿀 수 있다.

### 3.4 수정 시각을 남기는 두 장치

이 프로젝트의 `updated_at`에는 두 장치가 함께 있다.

| 장치 | 어디 | 언제 값을 넣나 |
| --- | --- | --- |
| JPA Auditing `@LastModifiedDate` | `BaseTimeEntity` | JPA가 엔티티를 저장할 때(변경 감지 UPDATE 포함). **일괄 수정에는 동작하지 않는다**(엔티티를 거치지 않으니까) |
| MySQL `ON UPDATE CURRENT_TIMESTAMP(6)` | `V1__init.sql`의 컬럼 정의 | 행이 UPDATE되어 **값이 실제로 바뀌는 칸이 있을 때**, 그 문장이 `updated_at`을 직접 정하지 않았으면 지금 시각으로 |

그래서 일괄 수정을 하면 Auditing은 안 움직이지만 MySQL이 `updated_at`을 지금으로 바꾼다. 카테고리를 지워 글이 미분류로 옮겨지면 그 글들의 수정 시각이 바뀌어 버린다. 그런데 spec POST-02의 "수정 시각"은 **작성자가 글을 고친 시각**이다. 작성자는 아무것도 안 고쳤다.

MySQL은 UPDATE 문이 그 칸을 **직접 정하면** `ON UPDATE`를 적용하지 않는다. 그래서 `updated_at = updated_at`(지금 값 그대로 다시 넣기)을 함께 적으면 수정 시각이 지켜진다.

## 4. 동작 원리

### 4.1 글 삭제 한 번에 일어나는 일

```
DELETE /api/posts/15  (주인)
  └ PostService.delete  ─── @Transactional 하나 ───────────────────────────┐
     ① findOwned: 가시성 판단 → 주인인지(아니면 404/401/403)                 │
     ② DELETE FROM notification WHERE (POST 15) OR (COMMENT ∈ 15의 댓글)   │
     ③ DELETE FROM post_like WHERE post_id = 15                            │
     ④ UPDATE comment SET deleted_at = now, updated_at = updated_at        │
          WHERE post_id = 15 AND deleted_at IS NULL     ← 영속성 컨텍스트 비움 │
     ⑤ findById(15) → post.delete(now)  → 커밋 때 변경 감지로                 │
          UPDATE post SET deleted_at = now, updated_at = now                │
  ─────────────────────────────────────────────────────────────────────────┘
```

- **한 트랜잭션인 이유**: ②~⑤ 중 하나라도 실패하면 모두 되돌아가야 한다. 공감은 지워졌는데 글은 그대로 남는 중간 상태가 생기면 공감 수가 틀어진다(헌법 VI "숫자는 틀리지 않는다").
- **알림을 ②에서 먼저 지우는 이유**: 알림 조건이 "이 글의 댓글 id 목록"을 쓰는데, 댓글은 소프트 삭제라 행이 남으므로 순서는 사실 상관없다. 다만 "딸린 것 → 글 자신" 순서로 읽히게 두었다.
- **댓글은 소프트, 공감·알림은 하드인 이유**: 댓글은 사용자가 쓴 글이라 기록으로 남긴다(신고·관리 대상이 될 수 있다). 공감과 알림은 "켜짐/받음" 같은 상태라 남길 이유가 없고, 남기면 공감 수·알림 수 계산마다 삭제 조건을 또 붙여야 한다. data-model.md도 "그 글의 댓글·공감·알림도 같은 트랜잭션에서 소프트 삭제 또는 제거"라고 적었다.
- **"수치에서 바로 빠진다"**: 블로그 글 수와 목록은 매번 `deleted_at IS NULL` 조건으로 세므로 따로 숫자를 줄일 필요가 없다.

### 4.2 수정·공개 범위 변경은 변경 감지로

```java
Post post = findEditable(blog, postId, member);   // 이 트랜잭션에서 읽음
post.edit(...);                                   // 필드만 바꿈
return post;                                      // 커밋 때 UPDATE
```

`findOwned`(그리고 `findEditable`)가 같은 트랜잭션 안에서 불려야 하는 이유가 3.2의 조건 1이다. `edit`가 `@Transactional`이고, 그 안에서 `findEditable`을 부르면(같은 객체 안 호출이라 새 트랜잭션이 생기지 않는다) 가시성 판단이 읽은 글이 바로 이 트랜잭션의 영속성 컨텍스트에 있다. 그래서 `save()` 없이 저장된다.

### 4.3 일괄 수정의 함정: 영속성 컨텍스트와 DB가 어긋난다

일괄 수정은 **영속성 컨텍스트를 거치지 않고 DB에 바로** 간다. 그래서:

```java
Post post = postRepository.findById(15).orElseThrow();  // 컨텍스트: category = Java
postRepository.uncategorize(javaId);                     // DB: category_id = NULL
post.getCategory();                                      // 컨텍스트는 여전히 Java (낡은 값)
```

같은 트랜잭션에서 그 엔티티를 다시 읽어도, JPA는 이미 컨텍스트에 있는 엔티티를 그대로 돌려준다(DB에 다시 묻지 않는다). 낡은 값을 보게 되고, 그 상태로 변경 감지가 돌면 **낡은 값을 다시 덮어쓸** 수도 있다.

해결: `@Modifying(clearAutomatically = true)`. 일괄 수정을 실행한 뒤 영속성 컨텍스트를 **비운다**. 이후 읽는 엔티티는 DB에서 새로 읽힌다.

대가: 비우기 전에 컨텍스트에 있던 엔티티는 모두 준영속이 된다. 그 엔티티를 고쳐도 변경 감지가 되지 않는다. 그래서 `PostService.delete`는 댓글 일괄 수정(④) **뒤에** 글을 `findById`로 **다시 읽어** 지운다(⑤). ①에서 읽은 글 객체를 그대로 `delete(now)` 하면 저장되지 않는다.

비우기 전에 아직 DB에 안 간 변경이 있으면 그것도 함께 사라진다. 그래서 `clearAutomatically`를 쓰는 메서드 앞에서는 엔티티를 고치지 않거나, 필요하면 `flushAutomatically = true`로 먼저 내보낸다. 이 프로젝트의 삭제 흐름은 ①~③에서 엔티티를 고치지 않으므로 문제가 없다.

## 5. 이 프로젝트에서는

### 5.1 엔티티의 삭제·수정 메서드

`src/main/java/com/nhnacademy/blog/post/domain/Post.java`

```java
/** 공개 범위만 바꾼다 (POST-06). */
public void changeVisibility(Visibility visibility) {
    this.visibility = visibility;
}

/** 소프트 삭제 (POST-03). 행은 남고 사용자에게만 사라진다. */
public void delete(LocalDateTime now) {
    this.deletedAt = now;
}
```

- 세터(`setDeletedAt`) 대신 뜻이 있는 이름(`delete`)으로 둔다. "삭제"가 앞으로 다른 일(예: 삭제 시각 말고 다른 표시)을 더 하게 되어도 부르는 쪽은 그대로다.
- 시각을 인자로 받는 이유: `LocalDateTime.now()`를 안에서 부르면 테스트에서 시각을 바꿀 수 없다. 서비스가 `Clock` 빈으로 만든 시각을 넘긴다.

### 5.2 글 삭제 서비스

`src/main/java/com/nhnacademy/blog/post/application/PostService.java`

```java
@Transactional
public void delete(Blog blog, Long postId, LoginMember member) {
    Long id = findOwned(blog, postId, member).getId();
    LocalDateTime now = LocalDateTime.now(clock);
    postRepository.deleteNotifications(id);
    postRepository.deleteLikes(id);
    // 댓글 일괄 수정이 영속성 컨텍스트를 비우므로(clearAutomatically) 글은 그 뒤에 다시 읽어 지운다
    commentRepository.softDeleteByPostId(id, now);
    postRepository.findById(id).orElseThrow().delete(now);
}
```

- `findOwned(...)`: 지운 글·남의 블로그 글·볼 수 없는 글은 404, 볼 수 있는데 주인이 아니면 401/403([16](./16-authorization-visibility.md)). 숨긴 글도 지울 수는 있다(수정과 달리 `findEditable`을 쓰지 않는다. contracts "숨긴 글도 삭제는 됨").
- `.getId()`만 쓰는 이유: 이 객체는 ④에서 컨텍스트가 비면 준영속이 되므로 고칠 대상으로 쓰지 않는다.
- 마지막 줄의 `delete(now)`는 변경 감지로 저장된다. `post`의 `updated_at`은 Auditing이 지금으로 바꾼다(작성자가 한 행동이라 맞다).

### 5.3 일괄 수정 쿼리들

`src/main/java/com/nhnacademy/blog/comment/domain/CommentRepository.java`

```java
@Modifying(clearAutomatically = true)
@Query("update Comment c set c.deletedAt = :now, c.updatedAt = c.updatedAt"
        + " where c.post.id = :postId and c.deletedAt is null")
int softDeleteByPostId(@Param("postId") Long postId, @Param("now") LocalDateTime now);
```

- `c.updatedAt = c.updatedAt`: 3.4의 기법. 댓글 작성자가 고친 것이 아니므로 댓글의 수정 시각을 바꾸지 않는다.
- `c.deletedAt is null`: 이미 지운 댓글의 삭제 시각을 덮어쓰지 않는다(언제 지웠는지가 기록이다).
- `clearAutomatically = true`: 4.3.

`src/main/java/com/nhnacademy/blog/post/domain/PostRepository.java`

```java
@Modifying
@Query(value = "DELETE FROM post_like WHERE post_id = :postId", nativeQuery = true)
int deleteLikes(@Param("postId") Long postId);

@Modifying
@Query(value = "DELETE FROM notification WHERE (target_type = 'POST' AND target_id = :postId)"
        + " OR (target_type = 'COMMENT' AND target_id IN (SELECT id FROM comment WHERE post_id = :postId))",
        nativeQuery = true)
int deleteNotifications(@Param("postId") Long postId);
```

- 네이티브 쿼리라 테이블·컬럼 이름을 쓴다.
- 알림은 "대상 종류 + 대상 번호"로 무엇을 가리키는지 적는 구조다(data-model notification). 글 자체를 가리키는 알림(공감 알림 등)과 그 글의 댓글을 가리키는 알림(댓글 알림)을 함께 지운다.
- 이 둘에는 `clearAutomatically`가 없다. 지우는 테이블에 해당하는 엔티티가 컨텍스트에 없으니 어긋날 것이 없다.

### 5.4 카테고리 삭제: 글은 미분류로

```java
/**
 * 카테고리를 지울 때 그 카테고리의 글을 미분류로 옮긴다 (CAT-01). 삭제된 글도 함께 옮겨 외래 키가 남지 않게 한다.
 * updated_at은 MySQL ON UPDATE로 바뀌지 않게 그대로 다시 넣는다. 작성자가 고친 것이 아니라서 수정 시각을 남기지 않는다.
 */
@Modifying(clearAutomatically = true)
@Query("update Post p set p.category = null, p.updatedAt = p.updatedAt where p.category.id = :categoryId")
int uncategorize(@Param("categoryId") Long categoryId);
```

- **삭제된 글도 함께 옮기는 이유**: 조건에 `deleted_at is null`을 붙이지 않았다. 지운 글이 없어진 카테고리 번호를 계속 가리키면, 그 번호의 카테고리 행이 없는데 글은 그 번호를 들고 있는 상태가 된다(나중에 글을 되살리면 문제가 된다). 그래서 지운 글까지 모두 미분류로 바꾼다.
- `categoryId=0` 목록(미분류)이 곧 "카테고리가 NULL인 글"이라 따로 할 일이 없다.

`src/main/java/com/nhnacademy/blog/category/application/CategoryService.java`

```java
@Transactional
public void delete(Blog blog, Long categoryId) {
    Category category = find(blog, categoryId);
    if (categoryRepository.existsByParentId(category.getId())) {
        throw new BusinessException(ErrorCode.CATEGORY_HAS_CHILDREN);
    }
    postRepository.uncategorize(category.getId());
    categoryRepository.deleteById(category.getId());
}
```

- 하위 카테고리가 있으면 409 `CATEGORY_HAS_CHILDREN`. 하위를 어떻게 할지(같이 지울지, 위로 올릴지) 사용자가 먼저 정해야 해서 거절한다. 지금은 하위를 만드는 화면이 없지만(CAT-03은 스텝 9) 규칙은 미리 둔다.
- 카테고리 자체는 **하드 삭제**다. 카테고리는 주소가 공유되는 대상이 아니고(`/category/7`이 깨져도 글 주소는 그대로), 기록할 이유가 없다. 지운 카테고리 번호로 목록을 열면 404다.
- 순서: 글을 먼저 옮기고(`uncategorize`) 카테고리를 지운다. 반대면 글이 없는 카테고리를 잠깐 가리키는 순간이 생긴다.
- `uncategorize`가 컨텍스트를 비우므로, `find`로 읽은 `category` 객체는 그 뒤 준영속이다. 그래서 `delete(category)`가 아니라 `deleteById(id)`로 지운다.

### 5.5 테스트

`src/test/.../category/CategoryIntegrationTest.java`

```java
@Test
void deletingMovesPostsToUncategorizedWithoutTouchingUpdatedAt() throws Exception {
    Category category = categoryRepository.save(Category.create(blog, null, "A", 0));
    Post first = testPosts.published(blog, category, Visibility.PUBLIC, LocalDateTime.now().minusHours(2));
    Post second = testPosts.published(blog, category, Visibility.PRIVATE, LocalDateTime.now().minusHours(1));
    jdbcTemplate.update("UPDATE post SET updated_at = '2026-01-01 00:00:00' WHERE blog_id = ?", blog.getId());

    perform(delete("/api/categories/" + category.getId()), ownerCookies, null).andExpect(status().isNoContent());

    ...
    assertThat(jdbcTemplate.queryForList(
            "SELECT CAST(updated_at AS CHAR) FROM post WHERE blog_id = ?", String.class, blog.getId()))
            .allSatisfy(updatedAt -> assertThat(updatedAt).startsWith("2026-01-01 00:00:00"));
```

- 수정 시각을 일부러 과거(2026-01-01)로 맞춰 두고 카테고리를 지운다. `ON UPDATE`가 동작했다면 지금 시각으로 바뀌었을 것이다. 그대로이므로 `p.updatedAt = p.updatedAt`이 효과가 있다는 증거다.
- 비공개 글(`second`)도 함께 옮겨지는 것을 본다. 일괄 수정은 가시성과 상관없이 그 카테고리의 모든 글을 바꾼다.

`src/test/.../post/PostWriteIntegrationTest.java`의 `deleteHidesPostAndCleansCommentsLikesNotifications`:

| 확인 | 기대 |
| --- | --- |
| `post.deleted_at` | 값 있음(행은 남음) |
| 댓글 `deleted_at` | 값 있음 |
| `post_like` 행 | 0 |
| 그 글·댓글을 가리키는 `notification` 행 | 0 |
| 주인의 블로그 글 목록 | 0개 |
| 사이드바 최근 댓글 | 비어 있음 |
| 같은 글을 다시 삭제 | 404(지운 글은 없는 글) |

`PostLifecycleIntegrationTest`(T040)는 같은 흐름을 API로만 돌린다: 카테고리를 만들어 글 두 개를 넣고 지우면 미분류 목록에 2개, 사이드바 미분류 수 2.

## 6. 자주 하는 실수와 함정

1. **조회 한 곳에서 `deleted_at IS NULL`을 빼먹음**: 지운 글이 다시 보인다. 조건을 한 곳에 모은다.
2. **일괄 수정 뒤 컨텍스트의 낡은 엔티티를 씀**: 값이 어긋나거나 덮어쓴다. `clearAutomatically = true`, 그리고 그 뒤에는 다시 읽는다.
3. **`clearAutomatically` 뒤에 앞서 읽은 엔티티를 고침**: 준영속이라 저장되지 않는다. 조용히 무시되므로 테스트로만 잡힌다.
4. **`@Modifying` 빼먹기**: Spring Data가 UPDATE를 조회로 실행하려다 오류가 난다.
5. **일괄 수정에 Auditing이 동작한다고 믿음**: 엔티티를 거치지 않으니 `@LastModifiedDate`는 안 움직인다. 반대로 MySQL `ON UPDATE`는 움직인다.
6. **"고친 적 없는" 행의 수정 시각이 바뀜**: 시스템이 한 정리(미분류로 옮김, 딸린 댓글 삭제)는 `updated_at = updated_at`으로 지킨다.
7. **딸린 데이터 정리를 트랜잭션 밖에서**: 중간에 실패하면 공감 수와 실제 공감이 어긋난다.
8. **트랜잭션 밖에서 읽은 엔티티를 고치고 저장을 기대함**: 변경 감지는 같은 트랜잭션의 엔티티만 본다.

## 7. 직접 해 보기

**실습 1. 테스트 돌리기**

```bash
./mvnw test -Dtest='CategoryIntegrationTest,PostWriteIntegrationTest,PostLifecycleIntegrationTest'
```

**실습 2. 수정 시각 지키기를 빼 보기**

1. `PostRepository.uncategorize`의 쿼리에서 `, p.updatedAt = p.updatedAt`을 지운다.
2. `./mvnw test -Dtest=CategoryIntegrationTest#deletingMovesPostsToUncategorizedWithoutTouchingUpdatedAt`
3. 기대: `updated_at`이 지금 시각으로 바뀌어 실패한다. 되돌린다.

**실습 3. clearAutomatically를 빼 보기**

1. `CommentRepository.softDeleteByPostId`의 `@Modifying(clearAutomatically = true)`를 `@Modifying`으로 바꾼다.
2. `PostService.delete`의 마지막 줄을 `findOwned(...)`로 읽은 객체에 `delete(now)`를 부르는 식으로 바꿔 보고, 원래대로도 돌려 본다.
3. 어느 조합에서 글이 지워지고 어느 조합에서 안 지워지는지 `deleteHidesPostAndCleansCommentsLikesNotifications`로 확인한다. 되돌린다.

**실습 4. SQL 로그로 일괄 수정 보기**

`application-dev.yml`에 잠깐 `logging.level.org.hibernate.SQL: debug`를 넣고 서버를 띄운 뒤 글을 지워 본다. `delete from notification`, `delete from post_like`, `update comment ... updated_at=updated_at`, `update post set deleted_at=...` 순서로 찍힌다. 끝나면 지운다.

**실습 5. 지운 글 확인**

```bash
docker exec -it blog-mysql mysql -ublog -pblog blog \
  -e "SELECT id, title, deleted_at FROM post WHERE deleted_at IS NOT NULL ORDER BY id DESC LIMIT 5"
```

행은 남아 있고, API·화면에서는 404다.

## 8. 확인 문제

1. 글을 하드 삭제하지 않고 소프트 삭제하는 이유 두 가지는?
<details><summary>답</summary>글 번호(주소)가 지운 글이었다는 사실을 남겨 404로 일관되게 답하고 다시 쓰이지 않게 하려고(헌법 III), 그리고 관리·신고 이력을 따라갈 수 있게 기록을 남기려고(POST-03, Q3).</details>

2. 소프트 삭제의 가장 큰 비용은 무엇이고 이 프로젝트는 어떻게 줄였나?
<details><summary>답</summary>모든 조회에 "삭제 안 됨" 조건을 붙여야 하고 한 곳만 빠져도 지운 글이 보인다. 조건을 PostSpecifications·PostVisibilityPolicy 한 곳에 모아 모든 목록·개수·상세가 그것을 쓰게 했다.</details>

3. `PostService.edit`가 `save()`를 부르지 않는데도 수정이 저장되는 이유는?
<details><summary>답</summary>같은 트랜잭션 안에서 읽은 엔티티는 영속성 컨텍스트에 있고, 커밋 전에 JPA가 스냅숏과 비교해 바뀐 칸의 UPDATE를 만든다(변경 감지).</details>

4. `PostService.delete`가 마지막에 글을 `findById`로 다시 읽는 이유는?
<details><summary>답</summary>댓글 일괄 수정의 `clearAutomatically = true`가 영속성 컨텍스트를 비워, 앞에서 읽은 글 객체가 준영속이 되었기 때문이다. 준영속 객체를 고쳐도 저장되지 않는다.</details>

5. 카테고리를 지울 때 글의 `updated_at`이 바뀌지 않게 한 방법과, 그것이 필요한 이유는?
<details><summary>답</summary>UPDATE 문에 `updated_at = updated_at`을 함께 적어 MySQL `ON UPDATE CURRENT_TIMESTAMP`가 동작하지 않게 했다. 수정 시각은 작성자가 글을 고친 시각인데, 카테고리 삭제는 작성자가 글을 고친 것이 아니기 때문이다.</details>

6. 공감·알림은 지우고 댓글은 소프트 삭제하는 이유는?
<details><summary>답</summary>댓글은 사용자가 쓴 내용이라 기록으로 남길 가치가 있다. 공감과 알림은 상태일 뿐이라 남길 이유가 없고, 남기면 공감 수·알림 수를 셀 때마다 삭제 조건을 또 붙여야 한다.</details>

7. 공감과 알림을 지우는 쿼리를 JPQL이 아니라 네이티브 쿼리로 쓴 이유는?
<details><summary>답</summary>공감(스텝 7)과 알림(백로그) 엔티티가 아직 없어 JPQL에서 이름을 쓸 수 없기 때문이다.</details>

8. `uncategorize`에 `deleted_at is null` 조건을 붙이지 않은 이유는?
<details><summary>답</summary>지운 글도 없어진 카테고리 번호를 가리키지 않게 하려고. 지운 글을 나중에 되살리거나 확인할 때 없는 카테고리를 가리키는 일이 없게 모두 미분류로 바꾼다.</details>

## 9. 더 읽을거리

- Spring Data JPA 레퍼런스: "Modifying Queries"(`@Modifying`, `clearAutomatically`, `flushAutomatically`)
- Hibernate 문서: Persistence context, Flushing, Bulk operations(HQL update/delete)
- MySQL 8.4 Reference Manual: "Automatic Initialization and Updating for TIMESTAMP and DATETIME"
- Spring Data JPA 레퍼런스: Auditing(`@LastModifiedDate`)
- 이 프로젝트: spec.md POST-03·Q3, data-model.md post·comment, [16 인가와 가시성 판단](./16-authorization-visibility.md), [23 트랜잭션과 동시성](./23-transactions-locking.md)
