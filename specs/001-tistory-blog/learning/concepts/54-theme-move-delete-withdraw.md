# 54. 꾸미기와 블로그의 수명: CSS 변수 테마, 정해진 칸 전체 교체, 이사와 301, 지우기의 연쇄와 탈퇴

> 관련 스텝: [스텝 19](../step-19.md) (T105, T086, T087, T106, T107, T108) · 관련 개념: [27 소프트 삭제와 일괄 수정](./27-soft-delete-bulk-update.md), [39 계층 데이터](./39-category-hierarchy.md) 5.9, [31 태그와 다대다](./31-tags-many-to-many.md) 5.13, [16 인가와 가시성](./16-authorization-visibility.md), [03 Flyway 마이그레이션](./03-flyway-migration.md), [53 서비스 관리](./53-admin-moderation-audit.md)

## 1. 이 문서로 배우는 것

- **CSS 변수 하나로 테마 바꾸기**: 포인트 색 6색을 `--brand` 변수로, 스킨을 `<html data-skin>`으로 입히는 방법
- **정해진 칸들을 통째로 교체하는 API**: 사이드바 모듈 8종을 "순서대로 8개 전부" 받아 검사하고 저장하기, 행이 없는 옛 블로그 채우기(마이그레이션)와 기본값
- **이사와 301**: 글 번호를 그대로 둔 채 블로그만 바꾸면 옛 주소가 저절로 이어지는 이유, 연쇄 이사를 "최종 블로그"로 저장해 한 번에 보내기, 순환 막기
- **지우기의 연쇄**: 블로그를 지우면 무엇을 함께 지우고 무엇을 남기나, 지운 블로그의 옛 주소는 어떻게 되나
- **탈퇴**: 회원의 흔적을 정리하는 순서, 공감 수·댓글 수 같은 **저장된 수치**를 맞추는 SQL, 로그인 수단 지우기

## 2. 왜 필요한가

블로그는 한 번 만들고 끝나지 않는다. 주인은 모양을 바꾸고, 글을 다른 블로그로 옮기고, 블로그를 닫고, 서비스를 떠난다. 이때 두 가지가 깨지기 쉽다.

1. **남이 가진 링크.** 누군가 카톡으로 보낸 `a.blog.com/15`가 이사 뒤에 404가 되면 그 링크는 죽는다. 검색 엔진에 올라간 주소도 마찬가지다. 301(영구 이동)로 새 주소를 알려 주면 브라우저와 검색 엔진이 따라간다.
2. **저장된 수치.** 이 프로젝트는 글마다 공감 수(`like_count`)와 댓글 수(`comment_count`)를 칸에 저장해 둔다(목록마다 세지 않으려고). 탈퇴한 회원의 공감과 댓글을 지우면서 이 칸을 맞추지 않으면 "공감 3"인데 실제로는 2인 글이 생긴다(spec AUTH-06 "수치가 실제와 맞는다").

## 3. 기본 개념

### 3.1 CSS 사용자 정의 속성(변수)

`--brand: #1f7a5c`처럼 `--`로 시작하는 속성은 값을 담는 변수다. `var(--brand)`로 꺼내 쓴다. 변수는 **상속**된다. `<html>`에 정하면 그 안의 모든 요소가 같은 값을 본다.

```css
:root { --brand: #1f7a5c; }               /* 기본 */
.btn.primary { background: var(--brand); }
.chip.brand  { color: var(--brand); }
```

자바스크립트로 `document.documentElement.style.setProperty('--brand', '#c0306e')`를 부르면 그 순간 `var(--brand)`를 쓰는 모든 곳이 분홍이 된다. 버튼·링크·칩을 하나씩 고치지 않는다. Thymeleaf라면 레이아웃 `<head>`에 `<style th:inline="css">:root { --brand: [[${blog.accentColor.hex}]]; }</style>`를 넣는 것과 같다.

**속성 선택자**는 "속성 값이 이것인 요소 안"을 고른다. `[data-skin="MAGAZINE"] .post-head h1 { font-family: Georgia, serif }`는 `<html data-skin="MAGAZINE">` 아래의 글 제목만 바꾼다. 스킨마다 CSS 파일을 따로 두지 않고, 같은 파일 안에서 속성 하나로 갈라 쓴다.

### 3.2 "정해진 칸 전체 교체" API

사이드바 모듈은 정확히 8종이고 블로그마다 한 번씩만 있다(spec BLOG-05). 이런 데이터를 바꾸는 API는 두 모양이 있다.

| 모양 | 예 | 장점 | 단점 |
| --- | --- | --- | --- |
| 하나씩 | `PATCH /modules/TAG {sortOrder: 3}` | 요청이 작다 | 순서를 바꾸면 여러 칸이 함께 바뀌어 요청이 여러 번, 중간에 실패하면 순서가 꼬인다 |
| 전체 교체 | `PUT /modules [8개를 원하는 순서로]` | 한 번에, 최종 모양 하나로 검사 | 매번 8개를 다 보낸다 |

목록이 작고 "순서"가 핵심이면 전체 교체가 낫다. 카테고리 순서 바꾸기([39](./39-category-hierarchy.md) 5.9)와 같은 판단이다. 대신 서버가 "8종이 정확히 한 번씩인가"를 검사해야 한다.

### 3.3 301과 "번호는 그대로"

HTTP 301(Moved Permanently)은 "이 주소는 이제 저기"라는 뜻이다. 브라우저는 `Location` 헤더의 주소로 바로 다시 요청하고, 검색 엔진은 색인을 새 주소로 옮긴다(302는 "잠깐 저기"라 옮기지 않는다).

이 프로젝트에서 글 주소는 `{블로그 주소}.blog.com/{글 번호}`이고 **글 번호는 플랫폼 전체에서 하나**다(spec 글 주소). 그래서 글을 옮길 때 번호를 바꾸지 않고 `post.blog_id`만 바꾸면 된다. 옛 주소 `a/15`가 오면 서버는 "15번 글은 지금 b에 있다"를 보고 `b/15`로 301한다. 이 판단은 스텝 2부터 화면 주소 단계(`SpaForwardController`)에 있었다. 스텝 19는 글을 옮기는 쪽을 만들었다.

### 3.4 연쇄를 "최종 값"으로 저장하기

A가 B로 이사하고, 나중에 B가 C로 이사하면 A의 방문자는 C로 가야 한다(spec US10 2번 "한 번에 C로"). 방법은 둘이다.

| 방법 | 저장 | 읽을 때 |
| --- | --- | --- |
| 따라가기 | A→B, B→C | A를 열면 B, B를 열면 C… 끝까지 따라간다(301 두 번, 또는 서버가 반복) |
| 최종으로 저장 | A→C, B→C | 한 번에 C |

이 프로젝트는 둘째다(ERD `moved_to_blog_id` 주석 "연쇄 이사 시 최종 대상으로 갱신"). 대신 **쓸 때** 일이 늘어난다. B를 C로 보낼 때 "B를 가리키던 A들"도 C로 바꿔야 한다. 그리고 순환(C를 다시 A로)을 막아야 한다. 최종으로 저장하면 순환 검사가 쉽다. "대상의 최종이 나 자신인가"만 보면 된다.

### 3.5 소프트 삭제의 연쇄

블로그·글·댓글은 지워도 행을 남긴다(소프트 삭제, [27](./27-soft-delete-bulk-update.md)). 블로그를 지울 때 무엇까지 함께 지우나는 규칙으로 정해야 한다.

| 대상 | 블로그 삭제 때 | 이유 |
| --- | --- | --- |
| 블로그 행 | `deleted_at`, 행은 남김 | 주소를 영구 예약(다시 개설 불가), 이사 연결 유지 |
| 남은 글 | `deleted_at` | "옮기지 않은 글 N개가 함께 삭제됩니다"(BLOG-07) |
| 그 글의 댓글 | `deleted_at` | 글 하나 삭제(POST-03)와 같은 규칙 |
| 그 글의 공감·알림 | 행 삭제 | 글 하나 삭제와 같은 규칙(되살릴 일이 없는 부수 데이터) |
| 옮긴 글 | 그대로 | 이미 다른 블로그 소속 |

### 3.6 저장된 수치 맞추기: UPDATE … JOIN

탈퇴하는 회원이 공감을 누른 글이 50개면, 50개 글의 `like_count`를 하나씩 줄여야 한다. 글을 50번 읽고 고치는 대신 MySQL의 **다중 테이블 UPDATE**로 한 문장에 한다.

```sql
UPDATE post p JOIN post_like l ON l.post_id = p.id
SET p.like_count = p.like_count - 1
WHERE l.member_id = ?;
```

`JOIN`으로 "이 회원이 공감한 글"만 골라 그 글들의 칸을 줄인다. 댓글은 한 글에 여러 개를 썼을 수 있어 **글마다 몇 개인지 먼저 세고**(부분 쿼리 GROUP BY) 그만큼 줄인다(5.6).

## 4. 동작 원리

**글 옮기기와 옛 주소**:

```
갑: 글 관리 → 글 31 선택 → "갑의 이사 블로그"로 옮기기
  POST a.blog.com/api/blog/move-posts {postIds:[31], targetBlogId:10}
    → 대상이 갑의 지우지 않은 다른 블로그인가(아니면 400 INVALID_MOVE_TARGET)
    → 글 31의 태그 이름 ["이사"] → 대상 블로그의 태그로 다시 연결(없으면 만듦)
    → UPDATE post SET blog_id=10, category_id=NULL, updated_at=updated_at WHERE id IN (31)
    → 옛 블로그에 글이 없어진 태그 지우기
을: a.blog.com/31 → SpaForwardController
    → 글 31은 블로그 10(move) 소속, 볼 수 있음 → 301 Location: move.blog.com/31
```

**이사 대상 지정과 연쇄**:

```
A→B 지정:  A.moved_to = B
B→C 지정:  대상 C의 최종 = C(이사 안 함) → B.moved_to = C
           UPDATE blog SET moved_to = C WHERE moved_to = B   ← A도 C로
C→A 시도:  대상 A의 최종 = A.moved_to = C = 나 자신 → 400 INVALID_MOVE_TARGET
```

**탈퇴 한 번의 순서** (한 트랜잭션):

```
DELETE /api/me {password}
 1. 본인 확인 (틀리면 401, 15분 5번이면 429)
 2. 회원의 블로그마다: 남은 글의 공감·알림 지우기 → 댓글·글 소프트 삭제 → 블로그 deleted_at
 3. 회원이 누른 공감: 글마다 like_count - 1 → post_like 행 삭제
 4. 회원의 구독 삭제(구독자 수는 행을 세므로 따로 맞출 것 없음)
 5. 회원의 댓글: 글마다 comment_count - n → 댓글 소프트 삭제, 방명록 소프트 삭제
 6. 소셜 연동 삭제
 7. member: status=WITHDRAWN, withdrawn_at, email=NULL, password_hash=NULL
 → 204 + 쿠키 삭제
```

순서에 이유가 있다. 3은 **지우기 전에** 수를 줄여야 한다(지운 뒤에는 무엇을 줄일지 모른다). 5도 같다. 2를 3보다 먼저 하면 자기 블로그 글에 누른 공감도 3에서 함께 정리된다(이미 지운 글이라 수치가 틀려도 보일 일이 없다).

## 5. 이 프로젝트에서는

### 5.1 테마 입히기: `frontend/src/app/blogTheme.ts`

```ts
export const ACCENTS: Record<AccentColor, { label: string; brand: string; soft: string }> = {
  BLUE: { label: '파랑', brand: '#2563c9', soft: '#e3ecfa' },
  ...
}

export function applyBlogTheme(blog: Pick<Blog, 'skin' | 'accentColor'> | null, root: HTMLElement = document.documentElement) {
  if (!blog) {
    delete root.dataset.skin
    root.style.removeProperty('--brand')
    root.style.removeProperty('--brand-soft')
    return
  }
  const accent = ACCENTS[blog.accentColor] ?? ACCENTS.BLUE
  root.dataset.skin = blog.skin
  root.style.setProperty('--brand', accent.brand)
  root.style.setProperty('--brand-soft', accent.soft)
}
```

- 서버는 색 **이름**(`PINK`)만 저장하고(ERD CHECK 6색), 실제 색 값은 화면이 정한다. 색을 조금 바꾸고 싶을 때 DB를 고치지 않는다.
- `root.dataset.skin = 'MAGAZINE'`은 `<html data-skin="MAGAZINE">`을 만든다. `dataset`은 `data-*` 속성을 자바스크립트 객체처럼 다루게 해 준다.
- `root`를 인자로 받는 이유: 단위 테스트에서 가짜 객체를 넘겨 "무엇을 정했나"만 확인한다(`blogTheme.test.ts`, 브라우저 없이).
- 부르는 곳은 `useBlog` 훅 하나다. 블로그 주소의 모든 화면(메인, 글, 방명록, 검색, 관리)이 이 훅으로 블로그를 받으므로 한 곳에서 입히면 다 된다. 꾸미기를 "적용"하면 같은 훅의 `setBlog`가 다시 입혀 새로고침 없이 바뀐다.

```css
[data-skin="MAGAZINE"] .post-head h1 { font-family: Georgia, "Noto Serif KR", serif; font-size: 34px; }
[data-skin="NOTE"] body { background-image: repeating-linear-gradient(var(--paper) 0 27px, var(--line) 27px 28px); }
```

- 노트 스킨의 줄 바탕은 그림 파일이 아니라 `repeating-linear-gradient`다. 27px 동안 종이색, 1px 선을 되풀이한다. 선 색도 변수(`--line`)라 어두운 모드에서도 맞는다.

### 5.2 사이드바 모듈: `blog/application/SidebarModules`

```java
@Transactional
public void replace(Long blogId, List<Slot> requested) {
    validate(requested);
    Map<SidebarModuleType, BlogSidebarModule> existing = repository.findByBlogIdOrderBySortOrderAscIdAsc(blogId)
            .stream().collect(Collectors.toMap(BlogSidebarModule::getModuleType, Function.identity()));
    for (int i = 0; i < requested.size(); i++) {
        Slot slot = requested.get(i);
        BlogSidebarModule module = existing.get(slot.type());
        if (module == null) {
            repository.save(BlogSidebarModule.of(blogId, slot.type(), i, slot.visible()));
        } else {
            module.place(i, slot.visible());
        }
    }
}

private static void validate(List<Slot> requested) {
    Set<SidebarModuleType> types = ...EnumSet...;
    if (requested.size() != SidebarModuleType.values().length || types.size() != requested.size()) {
        throw BusinessException.invalidField("modules", "모듈 8종을 한 번씩 보내 주세요.");
    }
    ... PROFILE을 숨기면 "블로그 홈 바로가기는 숨길 수 없습니다."
}
```

- **검사**: 크기가 8이고, 서로 다른 종류가 8개면(`EnumSet` 크기) "8종이 정확히 한 번씩"이다. 중복이 있으면 `EnumSet`이 줄어들어 걸린다.
- **저장**: 요청의 **자리 번호**(`i`)가 곧 순서다. 화면이 보낸 `sortOrder` 같은 숫자를 믿지 않는다.
- **지우고 다시 넣지 않는 이유**: `UNIQUE (blog_id, module_type)`라, 같은 트랜잭션에서 DELETE와 INSERT의 순서가 엇갈리면(Hibernate는 INSERT를 DELETE보다 먼저 보낼 수 있다) UNIQUE 위반이 날 수 있다. 있는 행은 고치고 없는 행만 만든다.
- PROFILE은 DB에도 CHECK(`ck_blog_sidebar_module_profile_visible`)가 있다. 자바가 먼저 400으로 막는다.

**행이 없는 블로그.** 스텝 19 전에 만든 블로그에는 모듈 행이 없다. 두 겹으로 다뤘다.

```sql
-- V4__blog_sidebar_module_defaults.sql
INSERT INTO blog_sidebar_module (blog_id, module_type, sort_order, is_visible)
SELECT b.id, m.module_type, m.sort_order, m.is_visible
FROM blog b CROSS JOIN (SELECT 'PROFILE' AS module_type, 0 AS sort_order, 1 AS is_visible UNION ALL ...) m
WHERE NOT EXISTS (SELECT 1 FROM blog_sidebar_module s WHERE s.blog_id = b.id);
```

- `CROSS JOIN`은 블로그마다 8줄을 만든다(블로그 수 × 8). `NOT EXISTS`로 이미 행이 있는 블로그는 건너뛴다. 이미 적용된 V1은 고치지 않고 새 파일 V4로 더했다([03](./03-flyway-migration.md)).
- 그래도 행이 없는 블로그(테스트가 저장소로 직접 만든 블로그 등)는 `of()`가 **기본 순서로 채워** 읽는다. 마이그레이션에만 기대지 않는다.
- 사이드바 API는 **보이는 모듈의 데이터만** 읽는다. 숨긴 인기 글 모듈 때문에 쿼리가 나가지 않는다.

**방문자 수 모듈의 0.** 오늘 방문(`blog_visit`)을 남기는 쪽과 새벽 집계는 스텝 20(T082)이다. 그래서 지금은 오늘·어제·누적이 모두 0이다. 읽는 쪽(`BlogVisitCounter`)은 테이블이 이미 있어 먼저 만들었다.

### 5.3 순서 바꾸기 화면: 순수 함수 + 끌어서 놓기 + 버튼

```ts
export function moveModule(items: SidebarModuleItem[], from: number, to: number): SidebarModuleItem[] {
  if (from === to || from < 0 || to < 0 || from >= items.length || to >= items.length) {
    return items
  }
  const next = [...items]
  const [moved] = next.splice(from, 1)
  next.splice(to, 0, moved)
  return next
}
```

- 끌어서 놓기(`onDrop`)와 "↑ ↓" 버튼이 **같은 함수**를 부른다. 스텝 17에서 카테고리를 끌어서만 옮길 수 있어 "키보드만 쓰는 사람은 못 옮긴다"고 남겨 둔 것을 이번에는 처음부터 버튼으로 함께 풀었다.
- 바뀌지 않으면 같은 배열을 돌려준다(`next !== items`로 "저장할 것이 생겼나"를 판단, [39](./39-category-hierarchy.md) 5.9와 같은 방식).

### 5.4 이사: `blog/application/BlogMoveService`

```java
@Transactional
public int movePosts(Blog blog, Collection<Long> postIds, Long targetBlogId) {
    ...
    Blog target = ownTarget(blog, targetBlogId);
    List<Post> posts = postRepository.findAll(PostSpecifications.inBlog(blog.getId())
            .and(PostSpecifications.ownerView())
            .and((root, query, cb) -> root.get("id").in(postIds)));
    Set<Long> oldTagIds = new HashSet<>();
    for (Post post : posts) {
        oldTagIds.addAll(post.tagIds());
        post.replaceTags(tagService.resolve(target, post.tagNames()));
    }
    List<Long> ids = posts.stream().map(Post::getId).toList();
    postRepository.moveTo(ids, target);
    tagService.removeUnused(oldTagIds);
    ...
}
```

- **이 블로그의 지우지 않은 글만** 고른다(`inBlog`, `ownerView`). 남의 글 번호나 지운 글 번호가 섞여 와도 건너뛴다(조용히 무시, `movedCount`로 몇 개를 옮겼는지 알려 줌).
- 태그는 블로그마다 따로라([31](./31-tags-many-to-many.md)), 이름으로 대상 블로그의 태그를 찾거나 만든다(`resolve`). 옛 블로그에서 글이 없어진 태그는 스텝 17의 규칙대로 지운다(`removeUnused`).
- 블로그·카테고리를 바꾸는 것은 JPQL 일괄 UPDATE다(`p.updatedAt = p.updatedAt`). 작성자가 글을 고친 것이 아니라서 글 머리에 "수정 …"이 붙지 않게 했다([53](./53-admin-moderation-audit.md) 5.5와 같은 방법).
- 순서가 중요하다. 태그 연결을 엔티티로 바꾼 **뒤에** 일괄 UPDATE를 한다. 일괄 UPDATE는 영속성 컨텍스트를 비우므로(`clearAutomatically`), 그 뒤에는 `post` 엔티티를 고쳐도 반영되지 않는다.

```java
@Transactional
public void moveTo(Blog blog, Long targetBlogId) {
    Blog target = ownTarget(blog, targetBlogId);
    Blog last = target.isMoved() ? target.getMovedToBlog() : target;
    if (last.getId().equals(blog.getId()) || last.isDeleted()) {
        throw new BusinessException(ErrorCode.INVALID_MOVE_TARGET);
    }
    Blog managed = blogRepository.findById(blog.getId()).orElseThrow();
    managed.moveTo(last);
    blogRepository.retarget(blog.getId(), last);   // update Blog b set b.movedToBlog = :target where b.movedToBlog.id = :blogId
}
```

- `target.getMovedToBlog()`가 곧 최종이다. 늘 최종으로 저장하므로 한 번만 보면 된다(3.4).
- `retarget`: 이 블로그로 이사해 오던 블로그들(A→이 블로그)을 새 최종으로 바꾼다. 이것이 "A가 한 번에 C로"를 만든다.
- 남의 블로그를 대상으로 주면 404가 아니라 400 `INVALID_MOVE_TARGET`이다. "남의 블로그 번호가 있다"를 404로 가르지 않고 모두 같은 400으로 답한다(대상 번호는 내 블로그 목록에서 고르므로 404를 볼 일도 없다).

### 5.5 지운 블로그의 옛 주소: `SpaForwardController`

테스트를 쓰다 버그를 찾았다. 이사 블로그로 글을 옮긴 뒤 **옛 블로그를 지우면**, 옮긴 글의 옛 주소가 301이 아니라 404였다. spec의 표는 "옛 블로그 주소(이사함, **삭제 여부 무관**) → 새 블로그로 301", "옮긴 글 → 새 블로그의 같은 글로 301"이다. 화면 주소 처리가 블로그를 찾자마자 "지워졌으면 404"로 끝내고 있었다.

```java
Blog blog = found.get();
...
if (postPath.matches()) {
    // 글 주소는 글이 지금 있는 블로그로 판단: 옮긴 글은 301, 함께 지워진 글은 404
    return switch (postVisibilityPolicy.decide(postId, blog, viewerId)) { ... };
}
// 이사한 블로그는 지워졌어도 새 블로그로 보낸다
if (blog.isDeleted() && !blog.isMoved()) {
    return app(HttpStatus.NOT_FOUND);
}
if (!blog.isDeleted() && !blogVisibilityPolicy.canView(blog, viewerId)) {
    return app(HttpStatus.NOT_FOUND);
}
if (blog.isMoved()) {
    // 주인은 옛 블로그 관리 화면을 계속 쓴다. 지운 블로그의 관리 화면은 없다
    if (isManagePath(path) && blog.isOwnedBy(viewerId) && !blog.isDeleted()) { ... }
    ...
}
```

- "지웠나"를 맨 앞에서 보지 않고, **글 주소 판단 뒤**, **이사 여부와 함께** 본다. 지웠고 이사도 안 했으면 404, 지웠지만 이사했으면 301이다.
- 글 판단(`PostVisibilityPolicy.decide`)은 글이 속한 블로그를 기준으로 한다. 옮긴 글은 새 블로그 소속이라 `MovedTo`(301), 함께 지워진 글은 `NotFound`(404)가 된다. 이 판단은 고치지 않았다.
- 새 테스트(`deletingBlogDeletesRemainingPostsKeepsAddressAndMoveLink`, `moveTargetFollowsChainAndRejectsCycle`)가 지운 블로그의 옮긴 글 301, 옮기지 않은 글 404, 이사한 블로그를 지운 뒤 301, 최종 블로그까지 지우면 404를 확인한다.

### 5.6 블로그 단위로 지우기: `BlogContentCleaner`, 회원 흔적 정리: `MemberTraceCleaner`

글 하나 삭제는 엔티티로 했다(`PostService.delete`: 공감·알림 지우기, 댓글 소프트 삭제, 글 `delete`). 블로그에 글이 300개면 이것을 300번 부르는 대신 블로그 단위 SQL 몇 문장으로 같은 규칙을 지킨다.

```java
// BlogContentCleaner.deletePosts (요약)
DELETE l FROM post_like l JOIN post p ON p.id = l.post_id WHERE p.blog_id = ? AND p.deleted_at IS NULL
DELETE n FROM notification n JOIN post p ON n.target_type = 'POST' AND n.target_id = p.id WHERE ...
UPDATE comment c JOIN post p ON p.id = c.post_id SET c.deleted_at = ?, c.updated_at = c.updated_at WHERE ...
UPDATE post SET deleted_at = ?, updated_at = updated_at WHERE blog_id = ? AND deleted_at IS NULL
```

- MySQL의 `DELETE 별칭 FROM … JOIN …`은 "조인으로 고른 행 중 이 표의 행만" 지운다. 표준 SQL에는 없는 MySQL 문법이다.
- 글을 지우기 **전에** 지울 글 번호를 읽어 두고(`findLiveIdsByBlogId`), 끝난 뒤 글마다 `PostDeletedEvent`를 낸다. 추천용 임베딩([42](./42-second-db-async-events.md))이 지운 글을 빼게 하려는 것이다.
- `JdbcTemplate`이 JPA와 **같은 트랜잭션**에서 돈다. Spring의 `JpaTransactionManager`가 트랜잭션의 DB 연결을 JDBC 쪽에도 내주기 때문이다. 그래서 중간에 실패하면 SQL도 엔티티 변경도 함께 되돌아간다.

```java
// MemberTraceCleaner.clean (요약)
UPDATE post p JOIN post_like l ON l.post_id = p.id
SET p.like_count = p.like_count - 1, p.updated_at = p.updated_at WHERE l.member_id = ?
DELETE FROM post_like WHERE member_id = ?
DELETE FROM subscription WHERE member_id = ?
UPDATE post p JOIN (SELECT post_id, COUNT(*) AS n FROM comment
                    WHERE member_id = ? AND deleted_at IS NULL GROUP BY post_id) c ON c.post_id = p.id
SET p.comment_count = p.comment_count - c.n, p.updated_at = p.updated_at
UPDATE comment SET deleted_at = ?, updated_at = updated_at WHERE member_id = ? AND deleted_at IS NULL
UPDATE guestbook SET deleted_at = ?, updated_at = updated_at WHERE member_id = ? AND deleted_at IS NULL
DELETE FROM social_account WHERE member_id = ?
```

- 공감: 한 회원은 한 글에 공감 하나(UNIQUE)라 `- 1`이면 된다.
- 댓글: 한 글에 여러 개를 썼을 수 있어, 부분 쿼리로 **글마다 지울 댓글 수 `n`**을 세고 그만큼 줄인다. 그다음 소프트 삭제한다. 순서를 바꾸면 이미 지운 댓글이라 `deleted_at IS NULL` 조건에 걸리지 않아 0을 세게 된다.
- 답글이 달린 댓글은 지워도 자리가 남는다(`DELETED` 상태, "삭제된 댓글입니다"). 댓글을 보여 주는 쪽이 스텝 6부터 그렇게 그렸다. 탈퇴 테스트가 이것을 확인한다.
- 구독자 수는 칸에 저장하지 않고 **행을 세므로** 지우기만 하면 맞는다. 저장된 수치(like_count, comment_count)만 따로 맞춰야 한다.

### 5.7 탈퇴: `member/application/WithdrawalService`

```java
@Transactional
public void withdraw(Long memberId, String password) {
    Member member = memberRepository.findById(memberId)
            .filter(found -> !found.isWithdrawn())
            .orElseThrow(() -> new BusinessException(ErrorCode.UNAUTHORIZED));
    confirm(member, password);
    LocalDateTime now = LocalDateTime.now(clock);
    for (Blog blog : blogRepository.findActiveByMemberId(memberId)) {
        blogDeletionService.deleteWithPosts(blog.getId());
    }
    memberTraceCleaner.clean(memberId, now);
    memberRepository.findById(memberId).orElseThrow().withdraw(now);
}
```

```java
// Member.withdraw
public void withdraw(LocalDateTime now) {
    this.status = MemberStatus.WITHDRAWN;
    this.withdrawnAt = now;
    this.email = null;
    this.passwordHash = null;
    this.suspendedUntil = null;
}
```

- 회원 행은 남긴다(spec 계정과 소셜 연동 "회원 기록은 남기고"). 글·댓글의 작성자로 이어져 있고, 관리 이력도 회원 번호를 가리킨다.
- **이메일을 비우는** 이유: 로그인은 이메일로 회원을 찾는다. 비우면 그 이메일로는 아무도 찾을 수 없어 "없는 계정"과 같고(LOGIN_FAILED), `UNIQUE(email)`이 풀려 같은 이메일로 다시 가입할 수 있다.
- 대표 블로그도 지운다. 블로그 삭제 API는 대표를 막지만(409), 탈퇴는 모든 블로그를 지우므로 대표 검사를 거치지 않는 `deleteWithPosts`를 쓴다.
- 이미 나간 로그인 쿠키는? 인증 필터가 요청마다 회원을 읽어 **탈퇴 회원이면 쿠키를 지우고 비회원으로** 본다(스텝 4부터). 그래서 다른 기기의 로그인도 다음 요청에서 끊긴다. 응답에서도 쿠키를 지운다.
- 본인 확인은 비밀번호 변경과 **같은 횟수 제한 키**(`password-change:{회원}`)를 쓴다. 탈퇴 화면이 비밀번호를 무작정 맞혀 보는 또 하나의 문이 되지 않게 했다.
- 소셜로만 가입한 회원의 재인증(카카오로 본인 확인)은 소셜 로그인(스텝 20 T099)과 함께 붙인다. 지금은 소셜 가입 회원이 없다.

### 5.8 화면의 입구

| 기능 | 입구 |
| --- | --- |
| 꾸미기 | 관리 → 블로그 설정 "꾸미기"(스킨 3, 포인트 색 6, 리스트·썸네일, 적용) |
| 사이드바 | 같은 화면 "사이드바"(끌어서 또는 ↑↓, 보이기, 사이드바 저장) |
| 글 옮기기 | 관리 → 글 관리에서 글을 고르고 "다른 블로그로 옮기기" → 옮기기 |
| 이사 지정·취소 | 블로그 설정 "블로그 이사" |
| 블로그 삭제 | 블로그 설정 "블로그 삭제"(남은 글 수, 주소 입력, 대표면 안내만) |
| 탈퇴 | 마이페이지 "회원 탈퇴" → `/me/withdraw` |

- 사이드바의 구독 모듈은 블로그 주인에게 버튼을 그리지 않는다(자기 블로그는 구독할 수 없다, 400). 처음에는 그려져 있었고 브라우저 확인에서 찾았다.
- 탈퇴 화면은 `DELETE /api/me`를 `allowAnonymous`로 부른다. 비밀번호가 틀린 401을 api 클라이언트가 "로그인이 필요하다"로 보고 로그인 화면으로 보내지 않게 하려는 것이다.

## 6. 자주 하는 실수와 함정

- **테마 색을 컴포넌트마다 props로 내려보낸다.** 바꿀 곳이 수십 군데가 된다. CSS 변수 하나를 바꾼다.
- **서버에 색 값(#c0306e)을 저장한다.** 디자인을 다듬을 때 DB를 고쳐야 한다. 이름(PINK)을 저장하고 값은 화면이 정한다.
- **순서를 클라이언트가 보낸 숫자로 저장한다.** 1, 5, 9나 중복 숫자가 온다. 배열의 자리로 다시 매긴다.
- **UNIQUE가 걸린 행을 지우고 다시 넣는다.** 같은 트랜잭션에서 INSERT가 DELETE보다 먼저 나가 위반이 날 수 있다. 있는 행을 고친다.
- **글을 옮기며 번호를 새로 매긴다.** 옛 링크를 이을 방법이 없어진다. 번호는 그대로, 소속만 바꾼다.
- **연쇄 이사를 읽을 때마다 따라간다.** 순환이 생기면 끝나지 않는다. 최종으로 저장하고, 쓸 때 순환을 막는다.
- **"지웠나"를 맨 앞에서 404로 끝낸다.** 이사·옮긴 글처럼 지운 뒤에도 이어져야 하는 주소가 끊긴다(5.5).
- **행을 지운 뒤 수치를 맞추려 한다.** 무엇을 줄일지 모른다. 수치를 먼저 줄이고 지운다.
- **저장된 수치를 루프로 하나씩 고친다.** 글이 많으면 문장이 수백 개다. UPDATE … JOIN 한 문장.
- **탈퇴 뒤에도 이메일을 남긴다.** 같은 이메일로 다시 가입할 수 없고, 로그인 판단이 상태 확인에 기대게 된다.
- **본인 확인에 횟수 제한을 빠뜨린다.** 비밀번호 변경은 막아 두고 탈퇴 화면으로 맞혀 보는 길이 열린다.

## 7. 직접 해 보기

### 7.1 화면

1. 관리 → 블로그 설정 → 꾸미기에서 "매거진", "분홍", "썸네일" → 적용. 개발자 도구 Elements에서 `<html data-skin="MAGAZINE" style="--brand: #c0306e; …">`를 본다. 블로그 홈이 카드 목록이다.
2. 사이드바에서 "구독 버튼과 구독자 수"를 끌어 "카테고리" 위에 놓고, 방문자 수·인기 글을 보이기로 → 사이드바 저장. 다른 브라우저(로그인 안 함)로 블로그를 연다.
3. 블로그를 하나 더 만들고(마이페이지 "블로그 만들기"), 글 관리에서 글 하나를 "다른 블로그로 옮기기". 옛 주소 `http://{옛 주소}.blog.test:8080/{번호}`를 열면 새 블로그로 넘어간다(주소창이 바뀐다).
4. 새 블로그의 설정 → 블로그 이사에서 대상 지정 → 그 블로그 홈이 대상으로 넘어간다 → 지정 취소.
5. 새 블로그를 삭제(주소 입력). 옮긴 글의 옛 주소는 404(그 글이 함께 지워졌으므로).
6. 테스트용 회원으로 마이페이지 → 회원 탈퇴 → 틀린 비밀번호 → "비밀번호가 맞지 않습니다." → 맞는 비밀번호 → 홈, 머리글이 로그인 전 모양.

### 7.2 301 직접 보기

```bash
curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' http://{옛 블로그}.blog.test:8080/{옮긴 글 번호}
# 301 http://{새 블로그}.blog.test:8080/{같은 번호}
```

### 7.3 DB에서

```sql
SELECT module_type, sort_order, is_visible FROM blog_sidebar_module WHERE blog_id = {번호} ORDER BY sort_order;
SELECT id, address, moved_to_blog_id, deleted_at FROM blog WHERE member_id = {회원 번호};
SELECT id, status, email, withdrawn_at FROM member WHERE status = 'WITHDRAWN';
```

### 7.4 순서 바꿔 보기 (연습 브랜치)

`MemberTraceCleaner.clean`에서 댓글 수를 줄이는 UPDATE와 댓글 소프트 삭제의 순서를 바꾸고 `WithdrawalIntegrationTest`를 돌려 본다. 댓글 수가 줄지 않아 `commentCount` 확인에서 실패해야 한다.

### 7.5 테스트

```bash
./mvnw test -Dtest='BlogDecorateMoveDeleteIntegrationTest,WithdrawalIntegrationTest,SidebarIntegrationTest'
cd frontend && npx vitest run src/app/blogTheme.test.ts src/pages/manage/sidebarModules.test.ts
```

## 8. 확인 문제

1. 포인트 색을 바꿨는데 버튼·링크·칩이 새로고침 없이 한꺼번에 바뀐다. 무엇 하나를 바꿨기 때문인가?
<details><summary>답</summary>html 요소의 CSS 사용자 정의 속성 --brand. 변수는 상속되어, var(--brand)를 쓰는 모든 규칙이 같은 값을 다시 읽는다.</details>

2. 사이드바 모듈 PUT에서 "8종이 정확히 한 번씩"을 어떻게 확인하나? 왜 행을 지우고 다시 넣지 않나?
<details><summary>답</summary>요청 크기가 8이고, 종류를 EnumSet에 담은 크기도 8이면 중복도 빠짐도 없다. UNIQUE(blog_id, module_type)라 같은 트랜잭션에서 INSERT가 DELETE보다 먼저 나가면 위반이 날 수 있어, 있는 행은 고치고 없는 행만 만든다.</details>

3. 글을 다른 블로그로 옮겼는데 옛 주소가 저절로 이어지는 이유는?
<details><summary>답</summary>글 번호가 플랫폼 전체에서 하나이고, 옮길 때 번호는 그대로 두고 blog_id만 바꾼다. 화면 주소 단계가 "이 번호의 글은 지금 어느 블로그 소속인가"를 보고 다르면 301한다(스텝 2부터 있던 판단).</details>

4. A→B, B→C 이사에서 A를 C로 한 번에 보내려고 쓸 때 하는 일 두 가지는?
<details><summary>답</summary>B의 대상을 C로 정할 때 C가 이미 이사했으면 그 최종으로 저장하고, B를 대상으로 두었던 블로그들(A)의 대상을 C로 바꾼다(retarget). 읽을 때는 한 번만 보면 된다.</details>

5. 옛 블로그를 지웠는데 옮긴 글의 옛 주소가 404였다. 원인과 고친 방법은?
<details><summary>답</summary>화면 주소 처리가 블로그를 찾자마자 "지워졌으면 404"로 끝내서 글 판단까지 가지 않았다. 글 주소 판단을 먼저 하고(옮긴 글 301, 함께 지워진 글 404), 블로그 주소는 "지웠고 이사도 안 했으면 404"로 바꿨다.</details>

6. 탈퇴할 때 댓글 수를 맞추는 UPDATE를 댓글 소프트 삭제보다 먼저 해야 하는 이유는?
<details><summary>답</summary>댓글 수를 줄일 양을 "그 회원의 지우지 않은 댓글 수"로 세는데, 먼저 지우면 deleted_at IS NULL에 걸리는 댓글이 없어 0을 센다.</details>

7. 탈퇴한 회원의 이메일을 비우는 이유 두 가지는?
<details><summary>답</summary>로그인은 이메일로 회원을 찾으므로 비우면 그 계정으로 로그인할 수 없다(없는 계정과 같음). UNIQUE(email)이 풀려 같은 이메일로 다시 가입할 수 있다.</details>

## 9. 더 읽을거리

- MDN, Using CSS custom properties (variables): https://developer.mozilla.org/en-US/docs/Web/CSS/Using_CSS_custom_properties
- MDN, Attribute selectors와 `HTMLElement.dataset`: https://developer.mozilla.org/en-US/docs/Web/CSS/Attribute_selectors, https://developer.mozilla.org/en-US/docs/Web/API/HTMLElement/dataset
- MDN, 301 Moved Permanently: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/301
- MySQL 8.0 레퍼런스, UPDATE(다중 테이블)와 DELETE(다중 테이블): https://dev.mysql.com/doc/refman/8.0/en/update.html, https://dev.mysql.com/doc/refman/8.0/en/delete.html
- Flyway 문서, Versioned migrations: https://documentation.red-gate.com/fd/migrations-184127470.html
