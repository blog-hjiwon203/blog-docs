# 49. 완료의 정의와 요구사항 추적: 명세 문장에서 화면 입구까지

> 관련 스텝: [스텝 13b](../step-13b.md) (T023a, T045a, T054a, 그리고 전체 점검에서 나온 T055d·T034a·T033a·T030a·T067a·T051a·T055e·T008a) · 관련 개념: [38 회원정보 수정](./38-member-profile-update.md) 5.7, [46 상태에 따라 갈 곳 정하기](./46-entry-routing-write-button.md) 3.3, [16 인가와 가시성](./16-authorization-visibility.md), [05 Spring 테스트](./05-spring-testing.md), [44 휴대폰 화면 점검](./44-mobile-responsive-check.md)

## 1. 이 문서로 배우는 것

- **완료의 정의**(Definition of Done): "작업이 끝났다"를 무엇으로 판단하나
- **요구사항 추적**(traceability): 명세 문장 하나를 API → 화면 → 눈에 보이는 입구까지 따라가는 법
- 기능이 "반쯤" 남는 전형적인 자리: `null`로 써 둔 응답 칸, 번호 없는 "나중에" 주석, 아무도 부르지 않는 API
- 계층별(수평)로 만들 때와 기능별(수직)로 만들 때 빈 곳이 어디에 생기나
- 테스트 고정 데이터(fixture)가 조건을 안 맞춰서 "서버 버그처럼 보이는" 실패
- 이 스텝에서 채운 세 빈 곳(블로그 프로필 이미지, 닉네임 링크, 관리 화면 태그 목록)의 코드
- 한 번 더, 이번에는 **전부** 찾기: 서버 API 전체와 화면 호출을 기계로 대조하고, 기능 영역을 나눠 명세 문장을 대조하는 법(5.7)

## 2. 왜 필요한가

스텝 13까지 체크박스 `[X]`가 붙은 작업이 60개를 넘었다. 테스트 300여 개도 다 통과했다. 그런데 지원이 화면을 눌러 보다가 이런 것을 찾았다.

| 날짜 | 찾은 것 | 명세 | 무엇이 빠졌나 |
| --- | --- | --- | --- |
| 2026-10-11 | 블로그를 5개까지 만들 수 있다는데 두 번째 블로그를 만드는 버튼이 없다 | BLOG-01 | 규칙·API·화면은 있고 **입구**가 없음 |
| 2026-10-11 | 마이페이지로 가는 버튼이 안 보인다 | BLOG-08 | 입구는 있는데 **보이지 않음**(밑줄 친 닉네임 글자) |

이어서 완료 작업을 명세 문장과 하나씩 대조했더니 더 나왔다(이 스텝 13b가 채운 것).

| 명세 문장 | 체크된 작업 | 빠진 것 |
| --- | --- | --- |
| BLOG-02 "블로그 이름, 소개글, **프로필 이미지**를 바꾼다" | T023 `[X]` | API에 칸 없음, 응답은 늘 `null`, 화면에 사진 칸 없음 |
| BLOG-08 "**댓글 작성자 닉네임 링크**는 대표 블로그로 간다" | (서버는 스텝 6) | 서버는 주소를 주는데 화면이 그냥 굵은 글자로 그림 |
| TAG-03 "블로그 태그와 글 수를 보여 준다" + 목업 관리 화면 6번 | T054 `[X]` | 사이드바에는 있지만 관리 화면에서 `GET /api/tags`를 부르지 않음 |

셋 다 **오류가 나지 않는다**. 테스트도 통과한다. 화면도 깨지지 않는다. 그냥 기능이 없을 뿐이다. 이런 빈 곳은 코드를 실행해서는 찾을 수 없고, **명세를 기준으로 거꾸로 따라가야** 보인다. 이 문서는 그 방법이다.

## 3. 기본 개념

### 3.1 완료의 정의(Definition of Done)

"T023 끝"이라고 할 때 무엇이 참이어야 하나? 사람마다 다르게 생각하면 체크박스의 뜻이 흔들린다.

- 코드를 썼다? → 그 코드가 명세의 무엇을 하는지 모른다.
- 테스트가 통과한다? → 테스트는 **쓴 것**만 확인한다. 안 쓴 기능의 테스트는 없다.
- 커밋이 있다? → 커밋 메시지에 T번호가 있다는 것뿐이다.

완료의 정의는 팀이 정하는 **체크리스트**다. 이 프로젝트는 2026-10-11 지원의 지적 뒤에 이렇게 정했다(코드 저장소 메모리 `feature-needs-visible-entry`).

> 체크박스를 `[X]`로 바꾸기 전에, 그 작업의 기능 코드를 spec.md 문장 그대로 다시 읽는다. 문장의 항목마다
> (1) API가 있나, (2) 화면이 그 API를 부르나, (3) 화면까지 눈에 보이는 입구가 있나를 확인한다. 목업의 해당 번호 칸과도 대조한다.

Thymeleaf로 만들 때를 떠올리면 쉽다. 컨트롤러 메서드(`@GetMapping("/manage/tags")`)를 만들고 템플릿까지 썼어도, **메뉴에 링크를 안 걸면** 사용자는 그 화면이 있는지 모른다. "주소를 직접 치면 된다"는 완료가 아니다.

### 3.2 요구사항 추적(traceability)

명세 문장 하나가 코드의 어디에서 이루어지는지 **양방향으로** 이을 수 있는 성질이다.

```
명세 문장 ──→ API(계약) ──→ 서버 코드 ──→ 응답 칸 ──→ 화면 컴포넌트 ──→ 입구(버튼·링크·메뉴)
   ↑                                                                              │
   └──────────────────────── 테스트·확인 시나리오 ←──────────────────────────────┘
```

- **앞으로 추적**: 명세 문장 → 그것을 이루는 코드. "BLOG-02의 프로필 이미지는 어디서 저장하지?" 답이 없으면 빠진 것이다.
- **뒤로 추적**: 코드 → 그 코드가 존재하는 이유(명세). "`BlogResponse.profileImageUrl`은 왜 있지?" → BLOG-02. 그런데 값이 늘 `null`이면, 칸은 있고 기능은 없는 것이다.

큰 회사에서는 이것을 표(추적 매트릭스, traceability matrix)로 관리한다. 행은 요구사항, 열은 설계·코드·테스트이고 칸에 파일이나 테스트 이름을 적는다. 이 프로젝트에서는 tasks.md의 `(BLOG-02)` 같은 기능 코드와 목업의 "이 화면이 부르는 API" 표가 그 역할을 나눠 맡는다.

### 3.3 문장을 항목으로 쪼갠다

명세 문장은 대개 여러 항목을 한 줄에 담는다. 쪼개지 않으면 "대부분 됐으니 됐다"가 된다.

BLOG-02 "블로그 이름(1~50자), 소개글, 프로필 이미지를 바꾼다."

| 항목 | API | 화면이 부르나 | 입구 |
| --- | --- | --- | --- |
| 이름(1~50자) | `PATCH /api/blog {name}` ✔ | 설정 화면 ✔ | 관리 → 블로그 설정 ✔ |
| 소개글 | `{description}` ✔ | ✔ | ✔ |
| 프로필 이미지 | ✘ (칸 없음) | ✘ | ✘ |
| (보이는 곳) 사이드바·머리글 | 응답 칸은 있으나 늘 `null` | 빈 동그라미 | — |

세 항목 중 둘이 되어서 T023은 `[X]`가 됐다. 한 줄씩 쪼개 보면 셋째 줄이 통째로 비어 있다.

### 3.4 반쯤 된 기능이 숨는 자리

이번 점검에서 빈 곳은 늘 비슷한 모양으로 숨어 있었다.

1. **`null`을 써 둔 응답 칸**: `BlogResponse`의 `blog.getDescription(), null,`. 계약대로 칸이 있으니 화면 코드는 그 칸을 읽고, 값이 없으니 빈 동그라미를 그린다. 아무도 실패하지 않는다.
2. **번호 없는 "나중에"**: 주석 "프로필 이미지는 스텝 7에서 채운다". 스텝 7의 작업 목록(T036~)에는 그 일이 없었다. tasks.md에 T번호가 없는 일은 아무 스텝도 하지 않는다.
3. **아무도 부르지 않는 API**: `GET /api/tags`. 테스트는 있고 잘 돈다. 그런데 `frontend/src`에서 `'/api/tags'`를 찾으면 한 곳도 안 나왔다(사이드바는 `/api/blog/sidebar` 안에 태그를 같이 받는다).
4. **받기만 하고 안 쓰는 응답 칸**: 댓글의 `author.primaryBlogAddress`. 서버는 스텝 6부터 정확히 계산해 줬다(볼 수 없는 블로그면 `null`까지). 화면은 `<b>{comment.author?.nickname}</b>`만 그렸다.
5. **보이지 않는 입구**: 링크인데 밑줄 친 글자라 버튼으로 안 보이거나, 링크가 아닌 그냥 글자.

1·2는 서버 코드에서, 3·4는 화면 코드에서, 5는 실제 화면에서만 보인다. 그래서 점검도 세 군데를 다 봐야 한다.

### 3.5 수평으로 만들 때와 수직으로 만들 때

- **수평(계층별)**: 스텝 4에서 블로그 API를 만들고, 다른 스텝에서 화면을 만들고, 또 다른 스텝에서 이미지를 만든다. 계층마다 "나는 내 몫을 했다"가 되고, 계층 사이에 걸친 항목(사진: 이미지 기능 + 블로그 API + 설정 화면 + 사이드바)이 떨어지기 쉽다.
- **수직(기능별, vertical slice)**: "블로그 프로필 이미지" 하나를 API부터 화면 입구까지 한 번에 만든다. 끝나면 사용자가 바로 눌러 볼 수 있다.

이 프로젝트의 스텝은 대체로 수직이지만, 스텝 4의 T023처럼 의존 기능(이미지)이 아직 없으면 "나중에"로 잘린다. 잘린 조각에는 **반드시 T번호를 붙여** 남겨야 수직이 다시 이어진다. 이번 스텝의 T023a·T045a·T054a가 그 조각들에 늦게 붙인 번호다(번호 규칙은 원래 작업 번호 + 글자, T055c와 같다).

### 3.6 테스트가 통과한다는 것의 뜻

테스트는 **쓴 사람이 생각한 것**을 확인한다. 생각하지 못한 항목에는 테스트도 없다. 그래서

- 테스트 통과 = "만든 것이 의도대로 돈다"이지, "명세가 다 됐다"가 아니다.
- 반대로, 명세 항목마다 테스트 이름을 붙일 수 있으면 추적이 쉬워진다. 이번 스텝은 항목마다 테스트를 하나씩 더했다(5.5).

## 4. 동작 원리: 점검을 실제로 하는 순서

### 4.1 명세에서 출발

1. spec.md에서 기능 코드(BLOG-02 등)의 문장을 그대로 읽는다.
2. 문장을 항목으로 쪼갠다(3.3 표).
3. contracts/rest-api.md에서 그 기능 코드가 붙은 API 줄을 찾는다. 요청 칸·응답 칸이 항목마다 있나.
4. 목업(`mockups/*.html`)의 "이 화면이 부르는 API" 표에서 그 기능 코드가 있는 화면과 번호를 찾는다.

### 4.2 코드로 확인 (grep이 가장 빠르다)

```bash
# (1) 응답 칸이 늘 null인가: DTO에서 null을 직접 넘기는 곳
grep -rn ", null," src/main/java --include='*Response.java'

# (2) 번호 없는 "나중에"
grep -rn "스텝 [0-9]*에서\|나중에\|TODO" src/main/java frontend/src

# (3) 계약의 API를 화면이 부르나
grep -rn "'/api/tags'" frontend/src

# (4) 응답 칸을 화면이 쓰나
grep -rn "primaryBlogAddress" frontend/src
```

(1)은 거짓 경보도 나온다(정말 없어야 하는 값도 있다). 나온 줄마다 명세와 견주어 본다.

### 4.3 화면으로 확인

마지막은 사람처럼 눌러 보는 것이다. "홈에서 시작해 클릭만으로 그 기능까지 갈 수 있나." 이 스텝에서는 헤드리스 Chrome([44](./44-mobile-responsive-check.md) 4절)으로 세 화면을 열어 DOM을 읽었다. 결과는 5.6.

### 4.4 찾은 것을 처리

1. 목록으로 정리하고 중요도를 매긴다(높음: 명세의 P0 항목이 통째로 없음, 중간: 서버는 되고 화면만 없음, 낮음: 편의).
2. 지원이 무엇을 언제 할지 정한다(이번에는 높음·중간 3개를 스텝 13b로, 낮음 4개는 다음으로).
3. tasks.md에 T번호와 스텝을 붙인다. 번호가 없으면 또 잊힌다.

## 5. 이 프로젝트에서는

### 5.1 BLOG-02 프로필 이미지: `null`을 실제 값으로 (T023a)

전:

```java
// blog/presentation/dto/BlogResponse.java (스텝 13까지)
return new BlogResponse(blog.getId(), blog.getAddress(), blog.getName(), blog.getDescription(), null,
        MemberSummaryResponse.of(blog.getMember(), detail.ownerPrimaryBlogAddress()), ...
```

후:

```java
return new BlogResponse(blog.getId(), blog.getAddress(), blog.getName(), blog.getDescription(),
        detail.profileImageUrl(),
        MemberSummaryResponse.of(blog.getMember(), detail.ownerPrimaryBlogAddress()), ...
```

- DTO는 값을 **옮기기만** 한다. 값을 만드는 것은 서비스(`BlogQueryService.detail`이 `ProfileImages.thumbnailUrl(blog.getProfileImageId())`로)다. 계층 구조([24](./24-layered-architecture-dto.md))대로다.
- 사이드바도 같은 모양이었다: `new Profile(blog.getName(), blog.getDescription(), null)` → `sidebar.profileImageUrl()`.
- 저장 쪽(`PATCH /api/blog`의 `profileImageId`, 주인이 올린 이미지만)과 설정 화면의 두 단계 저장은 [38](./38-member-profile-update.md) 5.7에 자세히 있다.

### 5.2 BLOG-08 닉네임 링크: 이미 있는 값을 쓰기 (T045a)

서버는 바꾼 것이 없다. `PrimaryBlogAddresses`가 스텝 6부터 "대표 블로그가 없거나 보는 사람이 볼 수 없으면(이용 제한, 주인 정지) 없는 것으로" 계산해 `MemberSummary.primaryBlogAddress`에 넣어 줬다. 화면에 컴포넌트 하나를 더했다.

```tsx
// frontend/src/components/AuthorName.tsx
export default function AuthorName({ author, bold = false }: { author: MemberSummary; bold?: boolean }) {
  const name = bold ? <b>{author.nickname}</b> : author.nickname
  if (!author.primaryBlogAddress) {
    return <span>{name}</span>
  }
  return <a href={blogUrl(author.primaryBlogAddress)} title={`${author.nickname}의 블로그`}>{name}</a>
}
```

- 1줄: `MemberSummary`를 통째로 받는다. 닉네임과 주소가 늘 같이 다니니 따로 받으면 엇갈릴 수 있다.
- 2줄: 댓글은 닉네임을 굵게, 글 상세의 작성자 줄은 보통 글자로 그렸다. 모양은 그대로 두고 링크만 씌운다.
- 3~5줄: 주소가 없으면 링크 없이 글자만. **서버가 "볼 수 없다"고 판단한 블로그로 가는 링크를 화면이 만들지 않는다.** 화면이 따로 판단하지 않고 서버 값만 따른다([16](./16-authorization-visibility.md)).
- 6줄: 대표 블로그는 다른 호스트(`{address}.blog.test`)라 `react-router`의 `<Link>`가 아니라 `<a href>`다. 이 프로젝트의 규칙이다([46](./46-entry-routing-write-button.md) 3.3). `blogUrl`이 지금 주소의 프로토콜·포트를 그대로 붙인다(개발 `:5173`이나 `:8080`).
- `title`: 마우스를 올리면 "을의 블로그"처럼 어디로 가는지 알려 준다. 링크 글자가 닉네임뿐이라 목적지가 글자에 없기 때문이다.

쓰는 곳:

```tsx
// components/Comments.tsx
{comment.author && <AuthorName author={comment.author} bold />}
// pages/post/PostPage.tsx
<AuthorName author={post.author} />
```

`comment.author`는 비밀댓글·숨긴 댓글이면 서버가 빼고 준다(`null`). 그래서 `&&`로 감쌌다. 실제로 그런 댓글은 위에서 "비밀댓글입니다" 줄로 따로 그려 이 줄까지 오지 않지만, 타입(`author: MemberSummary | null`)이 그렇게 말하니 따른다.

### 5.3 TAG-03 관리 화면 태그 목록: 부르지 않던 API를 부르기 (T054a)

```tsx
// frontend/src/pages/manage/CategoriesPage.tsx
function TagSection() {
  const [tags, setTags] = useState<TagCount[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api<TagCount[]>('/api/tags')
      .then(setTags)
      .catch((caught: unknown) => setError(errorMessage(caught)))
  }, [])
  ...
            {tags.map((tag) => (
              <tr key={tag.id}>
                <td><Link to={`/tag/${encodeURIComponent(tag.name)}`}>{tag.name}</Link></td>
                <td className="num">{tag.postCount}</td>
              </tr>
            ))}
```

- `useState<TagCount[] | null>(null)`: `null`은 "아직 안 불러옴", `[]`는 "불러왔는데 없음". 둘을 나눠야 불러오는 중에 "아직 태그가 없습니다"가 잠깐 깜빡이지 않는다([25](./25-react-forms-data.md)).
- `GET /api/tags`는 보는 사람 기준으로 센다(`TagListService`, `PostSpecifications.listedIn`). 관리 화면은 주인이 보니 **비공개 글도 센다**. 같은 API를 남이 부르면 공개 글만 세고, 비공개 글에만 단 태그는 아예 빠진다. 화면은 이 차이를 몰라도 된다. 서버가 판단한다.
- 이름은 같은 블로그 호스트의 태그별 글 목록(`/tag/spring`)이라 `<Link>`다(5.2와 반대 경우).
- `encodeURIComponent`: 태그에 `#`, `/`, 공백이 있으면 주소가 깨진다. 사이드바와 같은 방식.
- 표는 기존 `.table-wrap` 모양을 썼다. 360px 화면에서도 가로로 넘치지 않는다([44](./44-mobile-responsive-check.md)).
- 메뉴 이름을 "카테고리"에서 "카테고리·태그"로 바꿨다(목업과 같은 이름). **입구의 이름**이 기능을 말해야 사용자가 태그 목록을 찾으러 그 메뉴를 누른다.
- 이름 바꾸기·지우기(TAG-04)는 백로그라 버튼을 두지 않았다. 없는 기능의 버튼을 그려 두면 그것도 "반쯤 된 기능"이다.

### 5.4 테스트 고정 데이터가 조건을 숨긴 일

BLOG-08의 서버 동작을 지키는 테스트가 없어서 하나 더했다. 처음 쓴 코드:

```java
Blog readerBlog = testBlogs.create(reader);   // 댓글 쓴 사람의 블로그
...
list(post, null, null)
        .andExpect(jsonPath("$.content[0].author.primaryBlogAddress").value(readerBlog.getAddress()));
```

결과: `expected:<td98c7bfea2> but was:<null>`. 서버가 주소를 안 준다? 화면 링크가 안 나오던 이유가 서버였나?

원인은 테스트 쪽이었다. `TestBlogs.create`는 `Blog.open(owner, address, name, false)` — **대표가 아닌** 블로그를 만든다. 실제 서비스(`BlogService.open`)는 회원의 첫 블로그를 대표로 만들지만, 테스트 도우미는 그 규칙을 건너뛰고 엔티티를 바로 저장한다. 대표 블로그가 없는 회원이니 `null`이 맞는 답이었다.

```java
// support/TestBlogs.java (더함)
/** 회원의 대표 블로그. 대표는 회원마다 하나라(UNIQUE primary_owner_id) 대표가 없는 회원에게만 쓴다. */
public Blog createPrimary(Member owner) {
    String address = "t" + UUID.randomUUID().toString().replace("-", "").substring(0, 10);
    return blogRepository.save(Blog.open(owner, address, "블로그 " + address, true));
}
```

배울 점:

- **고정 데이터는 실제 규칙을 건너뛴다.** 빠르고 단순하게 만들려고 서비스를 거치지 않으니, 서비스가 채우는 상태(대표 여부, 글 수, 발행 시각…)가 실제와 다를 수 있다.
- **실패하면 먼저 "입력이 내가 생각한 상태인가"를 본다.** 서버를 고치기 전에 DB 상태를 확인했다면 바로 보였다. 반대로, 고정 데이터 탓인 줄 모르고 서버를 "고쳤다면" 멀쩡한 규칙을 망쳤을 것이다.
- 기존 `create`의 뜻을 바꾸지 않고 `createPrimary`를 더했다. `create`를 쓰는 테스트 수십 개가 "대표 아님"에 기대고 있을 수 있다.

같은 테스트에서 대표 블로그가 이용 제한되면 주소가 `null`이 되는 것(= 화면에 링크가 없음)도 확인했다.

```java
testBlogs.restrict(readerBlog);
list(post, null, null).andExpect(jsonPath("$.content[0].author.primaryBlogAddress").doesNotExist());
```

### 5.5 항목마다 테스트 하나

| 명세 항목 | 테스트 |
| --- | --- |
| BLOG-02 프로필 이미지 저장·표시 | `BlogInfoIntegrationTest.ownerSetsProfileImageAndItShowsInBlogInfoAndSidebar` |
| BLOG-08 닉네임 링크(서버가 주는 주소) | `CommentIntegrationTest.commentAuthorLinksToTheirPrimaryBlogOnlyWhenTheyHaveOne` |
| TAG-03 주인은 비공개 글도 센다 | `TagIntegrationTest`(스텝 7부터 있음, 관리 화면이 이 API를 쓰게 됨) |

화면 컴포넌트(`AuthorName`, `TagSection`) 자체의 자동 테스트는 없다. 이 프로젝트의 프론트 테스트는 판단 함수(`writeLink`, `commentList` 등)만 Vitest로 보고, 화면은 브라우저로 확인한다(다음 절).

### 5.6 브라우저로 확인한 것

확인용 서버(8081)와 헤드리스 Chrome으로, 회원 셋(갑: 블로그 주인, 을: 대표 블로그 있음, 병: 블로그 없음)을 만들어 봤다.

| 화면 | 확인 | 결과 |
| --- | --- | --- |
| 관리 → 블로그 설정 | 사진 고르기 → 미리 보기와 "저장을 눌러야…" → 저장 | "저장했습니다", 동그라미에 새 사진 |
| 블로그 홈 | 사이드바 맨 위 `img.avatar` | 같은 썸네일, 실제로 읽힘(`naturalWidth` 120) |
| 글 상세 | 작성자 갑 → 갑의 블로그, 댓글 을 → 을의 블로그, 병 → 링크 없음 | 기대대로 |
| 관리 → 카테고리·태그 | 태그 표 | spring 2, jpa 1, secret 1(비공개 글 포함). 같은 API를 비회원이 부르면 spring 1, jpa 1 |

확인 중에 스크립트가 글 저장 본문에 `tags`라고 써서(실제 칸 이름은 `tagNames`) 태그 표가 비어 나왔다. 서버는 모르는 칸을 무시한다. 이것도 5.4와 같은 종류의 실수다. "화면이 비었다"를 보고 바로 화면 코드를 의심하지 않고, `GET /api/tags`를 직접 불러 **입력 데이터부터** 확인했다.

### 5.7 두 번째 점검: 이번에는 전부 찾는다

세 빈 곳을 채워 PR을 올린 뒤, 지원이 "스텝 14로 넘어가기 전에 **기능 명세 기준으로** 화면에 연결 안 된 것을 **전부** 찾아 고친다"고 정했다. 처음 점검은 손으로 떠오르는 곳을 본 것이라 빠뜨린 것이 있을 수 있다. 이번에는 두 방향으로 빠짐없이 훑었다.

**(가) 서버 API → 화면 호출: 기계로 전부.** 컨트롤러의 매핑 주석을 모두 뽑고, 경로마다 `frontend/src`에서 부르는 곳을 찾았다.

```bash
# 컨트롤러의 모든 API (메서드 경로)
grep -rhoE '@(Get|Post|Put|Patch|Delete)Mapping\("[^"]+"' src/main/java \
  | sed -E 's/@([A-Za-z]+)Mapping\("/\1 /;s/"$//' | sort -u > endpoints.txt

# 경로마다 화면에서 부르는 파일 ({id} 같은 자리는 아무 글자로)
while read m p; do
  case "$p" in /api/*) ;; *) continue ;; esac   # 화면 주소(SpaForwardController)는 뺀다
  re=$(echo "$p" | sed -E 's/\{[^}]+\}/[^"`'"'"' ]*/g; s#/#\\/#g')
  hits=$(grep -rlE "$re" frontend/src | grep -v '\.test\.' | xargs -n1 basename | tr '\n' ' ')
  printf "%-7s %-45s %s\n" "$m" "$p" "${hits:-—— 없음}"
done < endpoints.txt
```

API 45개 중 "없음"은 둘이었다. `PATCH /api/posts/{id}/visibility`(빈 곳)와 `POST /api/auth/token/refresh`(필터가 알아서 재발급해서 화면이 부를 필요가 없게 **설계된** 것, [45](./45-remember-me.md)). 이 대조는 경로 앞부분만 맞아도 걸리는 느슨한 방법이라, "있음"으로 나온 줄도 실제 호출(메서드까지)을 한 번 더 뽑아 확인했다(`grep -rnE "api(<[^>]*>)?\(" frontend/src`).

**(나) 명세 문장 → API·화면·입구: 영역별로 나눠 전부.** tasks.md에서 `[X]` 작업의 기능 코드를 모두 뽑았다(50개 남짓). 사람 하나가 한 번에 보기에는 많아서 세 묶음(인증·홈·관리자 / 블로그·카테고리·태그 / 글·댓글·검색)으로 나눠 동시에 대조했다. 묶음마다 같은 지시를 줬다: 3.3처럼 문장을 항목으로 쪼개고, 4절의 세 질문을 묻고, 목업의 번호와 대조하고, 3.4의 숨는 자리를 찾고, **백로그로 미룬 항목은 빈 곳으로 세지 말 것**, 모든 주장은 파일과 줄로.

**결과와 처리.** 백로그(비밀댓글, 구독, 태그 이름 변경, 꾸미기·이사·삭제, 서비스 관리 기능 본체)는 빼고, 이미 만든 기능에서 나온 것은 모두 고쳤다.

| 작업 | 명세 | 빠진 것 | 종류(3.4) |
| --- | --- | --- | --- |
| T023a 추가분 | BLOG-02 | 블로그 메인 위쪽 프로필 상자가 빈 동그라미(사이드바에만 사진을 넣음) | 같은 값을 그리는 곳 하나를 빠뜨림 |
| T055d | AUTH-05 | 글쓴이·댓글 작성자 사진. `MemberSummaryResponse`가 `profileImageUrl`에 `null`을 써 둠 | `null` 응답 칸 |
| T034a | POST-06 | 글 상세에서 주인이 공개 범위 바꾸기(목업 12번) | 부르지 않는 API |
| T033a | POST-03 | 글 상세 삭제가 실패해도 아무 반응 없음 | 오류 경로가 없음 |
| T030a | CAT-02 | 글 상세·목록·글 관리의 카테고리 이름이 링크가 아님 | 보이지 않는 입구 |
| T067a | MNG-01 | 상태 필터에 백로그 기능 "예약"이 보임 | 없는 기능의 칸 |
| T051a | ADMIN-01 | `/admin`으로 가는 버튼이 없음 | 입구 없음 |
| T055e | BLOG-08 | 블로그·관리 머리글에 "내 블로그"가 없음(플랫폼에만) | 입구가 한쪽에만 |
| T008a | ADMIN-02 | 로그인한 채로 정지되면 사유가 안 보임. 확인하다 보니 블로그 글은 **500 화면**이었다 | 화면이 오류를 삼킴 + 버그 |

T008a의 500은 점검 표만 봤으면 몰랐다. 브라우저로 직접 정지 회원이 되어 열어 봐서 찾았다(원인과 고친 법은 [19](./19-react-router-api-client.md) 5.8). **표의 "빠진 것"을 고친 뒤에도 실제로 눌러 보는 것**이 4.3이 따로 있는 이유다.

**T055d에서 피한 함정 두 개.**

```java
// image/application/ProfileImages.java
public Map<Long, String> thumbnailUrls(Collection<Long> imageIds) {
    var ids = imageIds.stream().filter(Objects::nonNull).distinct().toList();
    if (ids.isEmpty()) {
        return new HashMap<>();
    }
    return imageRepository.findAllById(ids).stream()
            .filter(image -> image.getThumbnailPath() != null)
            .collect(Collectors.toMap(Image::getId, Image::getThumbnailPath, (a, b) -> a, HashMap::new));
}
```

- **N+1**: 댓글 20개의 작성자 사진을 하나씩 `findById`로 읽으면 쿼리 20번이다. 작성자들의 사진 번호를 모아 `findAllById` 한 번으로 읽는다. 대표 블로그 주소(`PrimaryBlogAddresses.of`)를 한 번에 구하던 것과 같은 방식이다([48](./48-representative-image.md) "한 페이지 쿼리 두 번").
- **`Map.of().get(null)`은 예외다.** 사진이 없는 회원은 사진 번호가 `null`이고, 부르는 쪽은 `photos.get(member.getProfileImageId())`로 꺼낸다. `Map.of()`(불변 맵)는 `get(null)`에 `NullPointerException`을 던진다. 일반 `HashMap`은 `null`을 돌려준다. 그래서 빈 경우에도, `toMap`의 결과도 `HashMap`으로 만들었다. `Collectors.toMap`의 기본 결과도 지금은 `HashMap`이지만 문서가 그 종류를 약속하지 않으므로 네 번째 인자(`HashMap::new`)로 못 박았다.

## 6. 자주 하는 실수와 함정

- **"테스트가 다 통과하니 끝"**: 테스트는 쓴 것만 본다. 명세 문장을 항목으로 쪼개 대조한다.
- **응답 칸을 `null`로 써 두고 번호를 안 붙인다**: 오류 없이 영영 빈다. 미룰 때는 tasks.md에 T번호를 만든다.
- **"스텝 N에서" 주석만 남긴다**: 스텝 N의 작업 목록에 없으면 아무도 안 한다.
- **API만 만들고 화면이 부르는지 안 본다**: `grep "'/api/...'" frontend/src`로 한 번 찾아본다.
- **입구가 "있다"로 끝낸다**: 보여야 한다. 링크처럼 보이지 않는 글자, 메뉴 이름이 기능을 말하지 않는 입구는 사용자에게 없는 것과 같다.
- **화면이 권한을 판단한다**: 닉네임 링크를 "블로그가 있으면" 화면이 따로 계산하면, 서버가 숨긴 블로그(이용 제한)로 가는 링크가 생길 수 있다. 서버가 준 값만 쓴다.
- **고정 데이터의 상태를 확인하지 않고 서버를 고친다**: 실패하면 먼저 입력이 생각한 상태인지 본다(5.4).
- **기존 테스트 도우미의 뜻을 바꾼다**: `create`를 대표로 바꾸면 다른 테스트가 조용히 달라진다. 새 도우미를 더한다.
- **없는 기능의 버튼을 그려 둔다**: 누르면 400이나 아무 일도 없는 버튼은 또 하나의 빈 곳이다. 기능이 생길 때 버튼도 생긴다.

## 7. 직접 해 보기

### 7.1 점검을 직접 해 본다

5.7 (가)의 스크립트를 코드 저장소 루트에서 그대로 돌려 본다. 지금은 "없음"이 `POST /api/auth/token/refresh` 하나만 나와야 한다. 다음 스텝(14)에서 API를 만들면 다시 돌려, 새 API가 "없음"으로 나오지 않는지 본다.

그다음 4절 순서를 손으로 따라 해 본다. 예: 스텝 14가 만들 CMT-03 "댓글 수정"의 명세 문장을 읽고, 목업 post-detail 7번(`PATCH /api/comments/{id}`, 본인만)과 대조해 "API · 화면이 부르나 · 입구(댓글의 '수정' 버튼)" 표를 미리 만들어 둔다. 스텝이 끝날 때 이 표의 칸이 다 차 있어야 완료다.

### 7.2 `null` 응답 칸 찾기

```bash
grep -rn ", null" src/main/java --include='*Response.java'
```

나온 줄마다 "정말 없어야 하는 값인가, 아직 안 채운 값인가"를 명세로 판단해 본다. 예: `MemberSummaryResponse.of`의 `profileImageUrl`(댓글 작성자 사진)은 어느 쪽인가?

### 7.3 이번 스텝 확인

준비: `./scripts/build-frontend.sh && ./mvnw spring-boot:run`, 블로그가 있는 회원으로 로그인.

1. `http://{내주소}.blog.test:8080/manage/settings` → "이미지 바꾸기" → 사진 고르기 → 저장 → 블로그 홈 사이드바 맨 위.
2. 다른 회원(대표 블로그 있음)으로 내 글에 댓글 → 그 닉네임을 누르면 그 사람 블로그.
3. 블로그 없는 회원으로 댓글 → 닉네임이 링크가 아님.
4. 관리 → 카테고리·태그 → 태그 표. 비공개 글에만 단 태그가 보이는지, 로그아웃하고 사이드바에서는 안 보이는지.

### 7.4 테스트

```bash
./mvnw test -Dtest='BlogInfoIntegrationTest,CommentIntegrationTest,TagIntegrationTest'
```

5.4를 직접 겪어 보려면 `commentAuthorLinks…` 테스트의 `createPrimary`를 `create`로 바꿔 돌려 본다(끝나면 `git restore .`).

## 8. 확인 문제

1. 체크박스가 `[X]`이고 테스트가 다 통과하는데도 기능이 빠질 수 있는 이유는?
<details><summary>답</summary>테스트는 만든 사람이 생각한 것만 확인한다. 명세 문장의 한 항목(예: 프로필 이미지)을 아예 안 만들었으면 그 테스트도 없다. 오류도 나지 않는다. 명세 문장을 항목으로 쪼개 API·화면·입구를 하나씩 대조해야 보인다.</details>

2. 이 프로젝트의 완료 확인 세 질문은?
<details><summary>답</summary>명세 문장의 항목마다 (1) API가 있나, (2) 화면이 그 API를 부르나, (3) 화면까지 눈에 보이는 입구가 있나. 목업의 해당 번호와도 대조한다.</details>

3. `BlogResponse`가 `profileImageUrl` 자리에 `null`을 써 둔 것이 왜 특히 찾기 어려운 빈 곳인가?
<details><summary>답</summary>계약대로 칸이 있어서 화면 코드도 그 칸을 읽고, 값이 없으면 빈 동그라미를 그리는 정상 경로로 처리된다. 오류·경고·실패한 테스트가 하나도 없다.</details>

4. "스텝 7에서 채운다" 주석이 실제로 스텝 7에서 채워지지 않은 이유와 막는 법은?
<details><summary>답</summary>스텝 7은 tasks.md의 작업 목록(T번호)만 했고, 그 일에는 T번호가 없었다. 미루는 일은 주석이 아니라 tasks.md에 T번호로 남긴다.</details>

5. 닉네임 링크를 만들 때 "그 회원이 블로그를 가지고 있나"를 화면이 따로 확인하지 않고 `primaryBlogAddress`가 있을 때만 링크를 거는 이유는?
<details><summary>답</summary>서버가 대표 블로그가 없거나 보는 사람이 볼 수 없으면(이용 제한, 주인 정지) null을 준다. 화면이 따로 판단하면 서버가 숨긴 블로그로 가는 링크가 생길 수 있다. 볼 수 있는지는 서버가 정한다.</details>

6. 닉네임 링크는 `<a href>`이고 태그 표의 이름은 `<Link>`인 이유는?
<details><summary>답</summary>대표 블로그는 다른 호스트({address}.blog.test)라 페이지를 새로 받아야 하고, 이 프로젝트는 호스트를 넘는 이동을 a로 쓴다. 태그별 글 목록은 같은 블로그 호스트의 경로라 React Router의 Link로 화면만 바꾼다.</details>

7. 관리 화면 태그 표에는 비공개 글에만 단 태그가 보이는데 사이드바(비회원)에는 안 보인다. 화면 코드에 그런 분기가 없는데 어떻게 그렇게 되나?
<details><summary>답</summary>GET /api/tags가 보는 사람 기준(listedIn)으로 글을 센다. 주인이면 비공개 글도 세고, 남이면 공개 글만 세고 글이 0인 태그는 뺀다. 화면은 받은 대로 그린다.</details>

8. `TestBlogs.create`로 만든 블로그로 `primaryBlogAddress`를 기대했더니 `null`이었다. 원인과, `create`를 고치지 않고 `createPrimary`를 더한 이유는?
<details><summary>답</summary>create는 대표가 아닌 블로그를 만든다(서비스의 "첫 블로그는 대표" 규칙을 거치지 않는다). 대표 블로그가 없는 회원이니 null이 맞다. create를 쓰는 다른 테스트가 "대표 아님"에 기대고 있을 수 있어 뜻을 바꾸지 않고 새 도우미를 더했다.</details>

9. 관리 화면에 태그 "이름 변경·삭제" 버튼을 미리 그려 두지 않은 이유는?
<details><summary>답</summary>TAG-04는 백로그라 API가 없다. 눌러도 동작하지 않는 버튼은 또 하나의 반쯤 된 기능이고, 사용자에게 기능이 있는 것처럼 보인다. 기능이 생길 때 버튼도 같이 만든다.</details>

10. 계층별(수평)로 나눠 만들 때 빈 곳이 잘 생기는 자리는 어디이고, 이 프로젝트는 어떻게 다시 이었나?
<details><summary>답</summary>여러 계층·기능에 걸친 항목(블로그 사진 = 이미지 기능 + 블로그 API + 설정 화면 + 사이드바)이 "다른 계층이 하겠지"로 떨어진다. 잘린 조각에 T번호(T023a처럼 원래 번호 + 글자)를 붙여 한 스텝에서 API부터 입구까지 수직으로 채웠다.</details>

11. 두 번째 점검에서 "서버 API → 화면 호출" 대조를 기계로 하고도, 명세 문장 대조를 따로 한 이유는?
<details><summary>답</summary>API 대조는 "만든 API를 화면이 부르나"만 안다. 명세에는 있는데 API부터 없는 항목(블로그 프로필 이미지 저장처럼)이나, API는 불리는데 응답 칸이 null인 것, 입구가 안 보이는 것은 API 목록에 나타나지 않는다. 명세 문장에서 출발해야 보인다.</details>

12. 사진이 없는 회원의 `photos.get(member.getProfileImageId())`가 예외를 낼 수 있는 경우는?
<details><summary>답</summary>photos가 Map.of() 같은 불변 맵이면 get(null)에 NullPointerException을 던진다. 사진이 없는 회원의 사진 번호는 null이다. 그래서 thumbnailUrls는 늘 null 키 조회를 받는 HashMap을 돌려준다.</details>

## 9. 더 읽을거리

- Scrum Guide, "Definition of Done" 절
- Karl Wiegers, Joy Beatty, *Software Requirements* (3판), 요구사항 추적 장
- Martin Fowler, "Test Coverage"(커버리지가 말해 주는 것과 말해 주지 않는 것), bliki
- Jeff Patton, *User Story Mapping* (수직으로 자른 이야기)
- MDN, `<a>` 요소와 `title` 속성, 접근성 관점의 링크 글자
