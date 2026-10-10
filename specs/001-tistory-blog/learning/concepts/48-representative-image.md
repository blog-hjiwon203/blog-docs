# 대표 이미지: 고른 값 검증, 기본값으로 돌아가기, 한 번에 불러오기

> 스텝 13(T058, POST-07)에서 썼다. 이미지 올리기와 썸네일은 [30 이미지 올리기](./30-image-upload.md), IDOR(남의 것을 가리키는 번호)는 [38 회원정보 수정](./38-member-profile-update.md)에서 먼저 다뤘다.

## 1. 이 문서로 배우는 것

- "사용자가 고른 번호"를 서버가 믿지 않고 확인하는 법: 있나, **허용된 후보 안에 있나**
- 고르지 않았을 때의 기본값(본문 첫 이미지)과, 고른 것이 사라졌을 때 기본값으로 돌아가기
- 외래 키 `ON DELETE SET NULL`이 하는 일
- 목록 한 페이지의 대표 이미지를 쿼리 몇 번으로 구하나(N+1 피하기)
- 화면에서 "고른 값"과 "실제로 보낼 값"을 나누는 파생 값(derived state)
- 화면이 번호를 모르는 문제와, 편집용 응답에 후보 목록을 더한 이유

## 2. 왜 필요한가

글 목록, 홈, 링크 공유 미리보기에는 글마다 사진 한 장이 붙는다. 스텝 7부터는 **본문의 첫 이미지**가 그 사진이었다. 그런데 첫 사진이 늘 글을 잘 대표하지는 않는다. 여행기의 첫 사진이 공항 표지판일 수도 있다.

명세 POST-07: "본문 이미지 중 고른다. 고르지 않으면 본문 첫 이미지가 대표다." API 명세의 글 저장 본문에는 처음부터 `thumbnailImageId` 칸이 있었고(스텝 12까지는 보내면 400), 테이블에도 `post.thumbnail_image_id`가 있었다.

## 3. 기본 개념

### 3.1 고른 번호를 믿지 않는다

화면은 본문 이미지 중에서만 고르게 보여 준다. 하지만 요청은 누구나 만들 수 있다. `"thumbnailImageId": 12345`에서 12345가

- 없는 이미지라면? 외래 키 위반으로 500이 날 수 있다.
- **남이 올린, 내 글에 없는 이미지**라면? 내 글 목록에 남의 사진이 대표로 걸린다. 그 사진이 비공개 글에만 있던 것이라면, 공개 목록으로 새어 나간다.

[38](./38-member-profile-update.md)의 프로필 사진은 "내가 올린 이미지인가"를 확인했다. 대표 이미지는 규칙이 다르다: **이 글의 본문에 들어 있나**. 본문에 이미 있는 이미지는 글을 볼 수 있는 사람에게 이미 보이는 것이라, 대표로 걸어도 새로 드러나는 것이 없다. 명세 문장도 그대로 "본문 이미지 중"이다.

규칙을 정리하면:

| 보낸 값 | 결과 |
| --- | --- |
| `null` 또는 칸 없음 | 고르지 않음 → 본문 첫 이미지 |
| 본문에 든 이미지 번호 | 그 이미지 |
| 없는 번호, 본문에 없는 이미지 | 400 `thumbnailImageId` |

확인은 **정화한 본문**으로 한다. 정화 전 본문에 `<img src="/uploads/남의것.png">`를 넣고 그 번호를 고른 뒤, 정화가 그 태그를 지운다면? 정화 전 본문으로 확인하면 통과해 버린다. 저장되는 것과 같은 본문으로 확인해야 한다.

### 3.2 기본값으로 돌아가기

"고르지 않으면 첫 이미지"를 어떻게 저장할까?

- (가) 고르지 않으면 서버가 첫 이미지 번호를 찾아 칸에 넣는다
- (나) 칸을 `null`로 두고, **보여 줄 때** 첫 이미지를 찾는다

(가)는 글을 고쳐 첫 사진을 바꿀 때마다 칸도 다시 계산해야 하고, "주인이 고른 것"과 "자동으로 들어간 것"을 구분하지 못한다. 수정 화면에서 "자동" 버튼이 켜져 있어야 하는지 알 수 없다. 이 프로젝트는 (나)다: `null` = 자동.

### 3.3 `ON DELETE SET NULL`

```sql
ALTER TABLE post ADD CONSTRAINT fk_post_image FOREIGN KEY (thumbnail_image_id)
    REFERENCES image (id) ON DELETE SET NULL;
```

외래 키는 "이 칸의 값은 image 테이블에 있는 id여야 한다"는 약속이다. 가리키던 image 행이 지워지면 DB가 어떻게 할지 정한다.

| 옵션 | image 행을 지우면 |
| --- | --- |
| `RESTRICT`(기본) | 가리키는 글이 있으면 지우기 실패 |
| `CASCADE` | 가리키는 **글도** 지움 (대표 이미지 때문에 글이 사라짐!) |
| `SET NULL` | 글의 칸만 `null`로 |

`SET NULL`이면 이미지가 지워졌을 때 대표 이미지 칸이 `null` = 자동(3.2)이 된다. 규칙 하나로 자연스럽게 "본문 첫 이미지로 돌아가기"가 된다. 지금은 이미지를 지우는 기능이 없지만(백로그), 테이블은 처음부터 이렇게 설계됐다.

### 3.4 N+1을 피해 한 페이지를 구하기

목록 한 페이지(10개)마다 대표 이미지 썸네일 주소가 필요하다. 글마다 이미지를 따로 조회하면 쿼리가 글 수만큼 나간다(N+1, [06 JPA](./06-jpa-entity-mapping.md)).

```
글 10개 → 대표 이미지를 고른 글의 이미지 번호들을 모아 한 번에: findAllById([3, 8, 15])
       → 나머지 글은 본문 첫 이미지 주소들을 모아 한 번에: findByPathIn(['/uploads/a.png', ...])
```

글이 몇 개든 쿼리는 최대 두 번이다. 고른 이미지가 (어떤 이유로) 없으면 그 글은 두 번째 묶음으로 넘겨 첫 이미지를 쓴다.

### 3.5 화면이 번호를 모르는 문제

본문 HTML에는 이미지 **주소**만 있다(`<img src="/uploads/a.png">`). 서버 정화가 `src`와 `alt`만 남기므로 `data-id` 같은 칸을 몰래 넣어 둘 수도 없다. 그런데 서버에 보낼 것은 이미지 **번호**다.

- 이 화면에서 방금 올린 이미지: 올리기 응답 `{ id, url, thumbnailUrl }`에 번호가 있다.
- 예전에 올려 본문에 이미 있는 이미지(수정 화면): 화면은 번호를 모른다.

그래서 편집용 글 조회 `GET /api/manage/posts/{id}` 응답에 **본문에 든 이미지 목록** `images: [{ id, url, thumbnailUrl }]`(본문 순서)과 고른 번호 `thumbnailImageId`를 더했다. API 명세에 없던 칸이라 명세에 더했다(스텝 노트의 "명세와 다른 것").

다른 방법도 생각해 볼 수 있다: 저장 본문에 번호 대신 주소(`thumbnailUrl`)를 받기. 그러면 API 명세의 `thumbnailImageId`와 테이블의 외래 키를 바꿔야 한다. 이미 정해진 모양을 지키고 응답에 칸을 더하는 쪽이 바꾸는 범위가 작다.

### 3.6 고른 값과 실제로 보낼 값 (파생 값)

화면에서 두 번째 이미지를 대표로 고른 뒤, 본문에서 그 이미지를 지웠다. 이제 무엇을 보내야 할까? 그대로 보내면 3.1의 규칙으로 400이다.

방법:

- (가) 본문이 바뀔 때마다 "고른 이미지가 아직 있나" 확인해 state를 고친다 → `useEffect`로 state를 고치면 한 번 더 그리고, 놓치기 쉽다
- (나) state에는 **사용자가 누른 것**만 두고, 보낼 값은 그릴 때마다 **계산**한다

React에서는 (나)를 권한다(다른 state에서 계산할 수 있는 값은 state로 두지 않는다). 이 프로젝트:

```
thumbnailId (state)   : 사용자가 마지막으로 누른 이미지 번호 (또는 null)
choices (계산)        : 지금 본문에 든 이미지 중 번호를 아는 것
보낼 값 (계산)        : thumbnailId가 choices에 있으면 그것, 없으면 null
```

이미지를 지웠다가 되돌리기(Ctrl+Z)하면 `thumbnailId`는 그대로라 다시 그 이미지가 대표로 켜진다. (가)였다면 이미 `null`로 지워져 있었을 것이다.

## 4. 동작 원리

```
[수정 화면 열기]
GET /api/manage/posts/16
  ← { ..., thumbnailImageId: null, images: [{id:41,url:a,…}, {id:42,url:b,…}] }
  knownImages = { a: 41, b: 42 }, thumbnailId = null
  choices = 본문의 [a, b] → 버튼: [자동✓] [a] [b]

[b를 누름]  thumbnailId = 42 → [자동] [a] [b✓]
[이미지 c를 새로 올림]  knownImages에 c 추가 → [자동] [a] [b✓] [c]
[발행]
PUT /api/posts/16 { …, thumbnailImageId: 42 }
  PostService: 본문 정화 → 정화된 본문에 b의 주소가 있나? 있다 → post.thumbnail_image_id = 42

[블로그 목록]
GET /api/posts
  PostThumbnails.of(10개)
    고른 글: findAllById([42]) → 42의 썸네일
    나머지: 본문 첫 이미지 주소들 → findByPathIn
  ← content[].thumbnailUrl
```

공유 미리보기(`og:image`, [43](./43-open-graph-preview.md))도 `PostThumbnails.of`를 쓰므로 따로 고칠 것 없이 고른 이미지가 나온다.

## 5. 이 프로젝트에서는

### 5.1 `image/application/PostThumbnails.java`

```java
@Transactional(readOnly = true)
public Map<Long, String> of(Collection<Post> posts) {
    Map<Long, String> thumbnails = new HashMap<>();
    List<Post> withoutChosen = new ArrayList<>();

    Set<Long> chosenIds = posts.stream().map(Post::getThumbnailImageId)
            .filter(Objects::nonNull).collect(Collectors.toSet());
    Map<Long, Image> chosen = chosenIds.isEmpty() ? Map.of() : imageRepository.findAllById(chosenIds).stream()
            .collect(Collectors.toMap(Image::getId, Function.identity()));
    for (Post post : posts) {
        Image image = post.getThumbnailImageId() == null ? null : chosen.get(post.getThumbnailImageId());
        if (image != null && image.getThumbnailPath() != null) {
            thumbnails.put(post.getId(), image.getThumbnailPath());
        } else {
            withoutChosen.add(post);
        }
    }
    ... (withoutChosen은 예전처럼 본문 첫 이미지를 findByPathIn 한 번으로)
```

- 5~6줄: 고른 이미지 번호만 모은다. 고른 글이 하나도 없으면 쿼리를 아예 안 한다(`Map.of()`).
- 7줄: `findAllById` 한 번(`WHERE id IN (...)`).
- 9~15줄: 고른 이미지를 찾았으면 그 썸네일, 못 찾았으면 "고르지 않은 글" 묶음으로 넘긴다(3.4).

```java
public void requireInBody(Long imageId, String html) {
    if (imageId == null) {
        return;
    }
    boolean inBody = imageRepository.findById(imageId)
            .map(image -> imagePaths(html).contains(image.getPath()))
            .orElse(false);
    if (!inBody) {
        throw BusinessException.invalidField("thumbnailImageId", "본문에 넣은 이미지 중에서 골라 주세요.");
    }
}
```

- `null`이면 고르지 않은 것이라 통과.
- 이미지가 없으면(`Optional.empty`) `false`, 있으면 그 주소가 본문 이미지 주소들에 있나.
- 없는 번호와 본문에 없는 번호를 **같은 메시지**로 거절한다. "그런 이미지는 없습니다"와 "본문에 없습니다"를 나누면, 남의 이미지 번호가 있는지 없는지를 알려 주게 된다.

```java
private static Set<String> imagePaths(String html) {
    Set<String> paths = new LinkedHashSet<>();
    ...
    Matcher matcher = IMAGE_SRC.matcher(html);
    while (matcher.find()) {
        paths.add(matcher.group(1));
    }
    return paths;
}
```

- 정규식 `<img[^>]*\ssrc="(/uploads/[^"]+)"`: 정화를 거친 본문은 img가 `src="/uploads/..."` 꼴만 남는다(HtmlSanitizer). 그래서 HTML 파서 없이 정규식으로 충분하다. 정화하지 않은 임의의 HTML이라면 정규식은 위험하다.
- `LinkedHashSet`: 본문 순서를 지키면서 같은 이미지가 두 번 나와도 한 번만. 첫 이미지(`firstImage`), 후보 목록(`bodyImages`), 검사(`requireInBody`)가 모두 이 함수를 쓴다. 규칙이 한 곳이다.

### 5.2 `post/application/PostService.java`

```java
Category category = category(blog, command.categoryId());
PostBody body = body(command.contentHtml());
postThumbnails.requireInBody(command.thumbnailImageId(), body.html());
post.edit(category, command.title(), body, command.visibility(), command.topic());
post.changeThumbnail(command.thumbnailImageId());
```

- 2줄: 정화가 먼저. 3줄은 **정화된** `body.html()`로 확인한다(3.1).
- 3줄이 4~5줄보다 먼저: 거절할 요청이면 엔티티를 건드리기 전에 끝낸다.
- `changeThumbnail(null)`도 그대로 저장한다. 수정에서 "자동"으로 돌리는 것이 이것이다.

### 5.3 편집용 응답: `post/presentation/dto/ManagedPostResponse.java`

```java
public record ManagedPostResponse(..., Map<String, String> blind,
                                  Long thumbnailImageId, List<BodyImage> images) {

    /** 본문에 든 이미지 { id, url, thumbnailUrl } (POST /api/images 응답과 같은 모양). */
    public record BodyImage(Long id, String url, String thumbnailUrl) {
    }
```

- 올리기 응답과 같은 모양이라, 화면은 둘을 같은 타입(`UploadedImage`)으로 한 맵에 모은다.
- 이미지 엔티티(`Image`)를 그대로 내보내지 않고 필요한 세 칸만([24 DTO](./24-layered-architecture-dto.md)). 올린 사람 번호, 원래 파일 이름 같은 것이 응답에 섞이지 않는다.

### 5.4 화면: `frontend/src/components/editor/thumbnail.ts`

```ts
export function thumbnailChoices(html: string, known: Record<string, UploadedImage>): UploadedImage[] {
  return bodyImageUrls(html).flatMap((url) => (known[url] ? [known[url]] : []))
}

export function effectiveThumbnail(selectedId: number | null, choices: UploadedImage[]): number | null {
  return selectedId !== null && choices.some((image) => image.id === selectedId) ? selectedId : null
}
```

- `thumbnailChoices`: 본문 순서대로, 번호를 아는 이미지만. `flatMap`에서 `[]`를 돌려주면 그 항목은 빠진다(`filter` + `map`을 한 번에).
- `effectiveThumbnail`: 3.6의 "보낼 값". 고른 이미지가 본문에서 사라졌으면 `null`.
- `bodyImageUrls`의 정규식은 서버(`PostThumbnails`)와 같은 규칙이다. 둘이 다르면 화면은 후보로 보여 줬는데 서버가 400을 주는 일이 생긴다.

### 5.5 화면: `pages/manage/PostWritePage.tsx`

```tsx
const [knownImages, setKnownImages] = useState<Record<string, UploadedImage>>({})
const [thumbnailId, setThumbnailId] = useState<number | null>(null)
...
const choices = thumbnailChoices(contentHtml, knownImages)
const chosenThumbnail = effectiveThumbnail(thumbnailId, choices)
...
<Editor initialHtml={loadedHtml} onChange={setContentHtml}
        onImageUploaded={(image) => setKnownImages((previous) => ({ ...previous, [image.url]: image }))} />
```

- `knownImages`: 주소 → 이미지. 불러올 때 `post.images`로 채우고, 올릴 때마다 더한다.
- `onImageUploaded`: 에디터에 새로 단 콜백. 에디터가 이미지를 올려 본문에 넣은 뒤 부른다. `setKnownImages(previous => ...)`처럼 함수로 넘기는 것은 여러 장을 연달아 올릴 때 앞 결과를 덮지 않기 위해서다.
- 저장 본문의 `thumbnailImageId`는 `effectiveThumbnail(thumbnailId, choices)`. 자동 저장의 스냅숏([47](./47-draft-autosave.md))에도 들어가, 대표 이미지만 바꿔도 "바뀐 것"이 된다.

```tsx
<div className="thumb-pick" role="radiogroup" aria-labelledby="thumbnail-label">
  <button type="button" role="radio" aria-checked={chosenThumbnail === null} ...>자동 …</button>
  {choices.map((image, index) => (
    <button key={image.id} type="button" role="radio" aria-checked={chosenThumbnail === image.id}
            aria-label={`본문 ${index + 1}번째 이미지`} ...>
      <img src={image.thumbnailUrl} alt="" />
    </button>
  ))}
</div>
```

- 하나만 고르는 선택지라 `role="radiogroup"`·`role="radio"`·`aria-checked`로 화면 낭독기에 "라디오 버튼, 선택됨"을 알린다. 사진만 있는 버튼이라 `aria-label`로 이름을 준다.
- `type="button"`: 폼 안의 버튼은 기본이 `submit`이라, 안 쓰면 누르는 순간 발행된다.
- 후보가 하나도 없으면(본문에 사진이 없으면) 이 칸 자체를 그리지 않는다.

### 5.6 테스트

- `ThumbnailIntegrationTest`(서버):
  - `withoutChoiceFirstBodyImageIsThumbnail`: 고르지 않으면 첫 이미지 썸네일(US5 수용 시나리오 2)
  - `chosenBodyImageIsThumbnailEverywhere`: 고른 두 번째 이미지가 블로그 목록·관리 목록에, 편집용 조회에 `thumbnailImageId`와 본문 순서의 `images`
  - `imageNotInBodyIsRejected`: 본문에 없는 내 이미지, 없는 번호 → 400
  - `editingKeepsRuleAndCanClearChoice`: 고른 이미지를 본문에서 빼며 그대로 보내면 400, `null`로 보내면 다시 첫 이미지
- `thumbnail.test.ts`(Vitest 3개): 본문 순서·중복, 번호 아는 것만, 지우면 `null`
- 헤드리스 Chrome(스텝 노트): 임시저장 글을 열어 두 번째 이미지를 고르고 발행 → 블로그 목록 썸네일이 두 번째 이미지의 것.

## 6. 자주 하는 실수와 함정

- **고른 번호를 그대로 저장**: 남의 이미지·없는 번호가 들어간다(3.1).
- **정화 전 본문으로 확인**: 정화가 지우는 태그로 검사를 통과시킬 수 있다.
- **"자동"을 첫 이미지 번호로 저장**: 첫 사진이 바뀌어도 대표가 그대로고, 주인이 고른 것과 구분이 안 된다(3.2).
- **글마다 이미지 조회**: 목록 한 페이지에 쿼리 수십 번(3.4).
- **고른 값을 `useEffect`로 고쳐 맞춤**: 한 번 더 그리고, 되돌리기에서 선택을 잃는다. 계산으로 구한다(3.6).
- **화면과 서버의 "본문 이미지" 규칙이 다름**: 화면 후보인데 서버가 400.
- **폼 안의 `<button>`에 `type` 빼먹기**: 대표 이미지를 누르면 발행된다.

## 7. 직접 해 보기

### 7.1 화면

1. 글쓰기에서 사진 두 장을 넣는다. 본문 아래에 "대표 이미지" 칸이 생기고 [자동] [1] [2].
2. [2]를 고르고 발행 → 블로그 메인과 홈 목록의 썸네일이 두 번째 사진.
3. 수정 화면을 다시 열면 [2]가 켜져 있다. 본문에서 두 번째 사진을 지우면 [자동]이 켜진다. Ctrl+Z로 되돌리면 다시 [2].
4. `curl -s http://{주소}.blog.test:8080/{글 번호} | grep og:image`로 미리보기 이미지가 두 번째 사진의 썸네일인지 본다.

### 7.2 API로 거절 보기

수정 화면을 연 채 개발자 도구 Network에서 `GET /api/manage/posts/{id}` 응답의 `images`를 본다. 다른 글에 올린 이미지 번호로:

```js
await fetch('/api/posts/{id}', { method: 'PUT', headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
  body: JSON.stringify({ title: 't', contentHtml: '<p>x</p>', visibility: 'PUBLIC', status: 'PUBLISHED', thumbnailImageId: {다른 번호} }) }).then(r => r.json())
```

400과 `fieldErrors[0].field = "thumbnailImageId"`.

### 7.3 쿼리 수 보기

`application-dev.yml`에 `spring.jpa.show-sql: true`를 잠깐 켜고 블로그 메인을 연다. 목록 쿼리 뒤에 이미지 쿼리가 많아야 두 번(`... where i1_0.id in (...)`, `... where i1_0.path in (...)`)인지 본다. 끝나면 되돌린다.

### 7.4 테스트

```bash
./mvnw test -Dtest='ThumbnailIntegrationTest,PostThumbnailsTest'
cd frontend && npx vitest run src/components/editor/thumbnail.test.ts
```

## 8. 확인 문제

1. 대표 이미지 검사가 "내가 올린 이미지인가"가 아니라 "본문에 들어 있나"인 이유는?

<details><summary>답</summary>

명세가 "본문 이미지 중 고른다"이고, 본문에 든 이미지는 그 글을 볼 수 있는 사람에게 이미 보이므로 대표로 걸어도 새로 드러나는 것이 없다. 반대로 본문에 없는 이미지를 막아야 남의 (비공개 글에만 있던) 사진이 내 목록에 걸리지 않는다.

</details>

2. `requireInBody`에 정화 **전** 본문을 넘기면 어떤 구멍이 생기나?

<details><summary>답</summary>

정화가 지우는 형태로 img를 넣고 그 번호를 고르면, 검사는 통과하지만 저장된 본문에는 그 이미지가 없다. 결국 본문에 없는 이미지가 대표가 된다. 저장되는 것과 같은 정화된 본문으로 검사해야 한다.

</details>

3. 고른 대표 이미지 행이 DB에서 지워지면 그 글의 대표 이미지는? 무엇 덕분인가?

<details><summary>답</summary>

`thumbnail_image_id`가 `null`이 되어 본문 첫 이미지로 돌아간다. 외래 키의 `ON DELETE SET NULL`과 "`null` = 자동" 규칙 덕이다.

</details>

4. 글 10개 목록에서 3개는 대표 이미지를 골랐고 7개는 안 골랐다. `PostThumbnails.of`가 이미지 테이블에 보내는 쿼리는 몇 번인가?

<details><summary>답</summary>

많아야 두 번. 고른 이미지 번호 3개를 `findAllById` 한 번, 나머지 7개의 첫 이미지 주소를 `findByPathIn` 한 번(본문에 이미지가 없는 글뿐이면 이것도 안 한다).

</details>

5. 화면에서 `thumbnailId` state를 본문이 바뀔 때마다 `useEffect`로 `null`로 고치지 않고, 그릴 때 `effectiveThumbnail`로 계산하는 이유는?

<details><summary>답</summary>

다른 state(본문, 고른 번호)에서 계산할 수 있는 값을 따로 state로 두면 맞추는 코드가 필요하고 한 번 더 그린다. 또 사진을 지웠다 되돌리면, 계산 방식은 사용자가 고른 번호가 남아 있어 다시 켜지지만 고쳐 맞추는 방식은 이미 지워져 있다.

</details>

6. 수정 화면이 본문 이미지의 번호를 알려면 왜 편집용 응답에 `images`가 필요한가?

<details><summary>답</summary>

본문 HTML에는 주소만 있고 번호는 없다(정화가 `src`·`alt` 말고는 지운다). 이 화면에서 올린 이미지는 올리기 응답으로 번호를 알지만, 예전에 올린 이미지는 서버가 알려 줘야 한다.

</details>

## 9. 더 읽을거리

- MySQL 8.4 Reference Manual, [FOREIGN KEY Constraints](https://dev.mysql.com/doc/refman/8.4/en/create-table-foreign-keys.html): `ON DELETE` 옵션
- React 문서, [Choosing the State Structure](https://react.dev/learn/choosing-the-state-structure): 계산할 수 있는 값은 state로 두지 않기
- WAI-ARIA Authoring Practices, [Radio Group Pattern](https://www.w3.org/WAI/ARIA/apg/patterns/radio/)
- OWASP, [Insecure Direct Object Reference Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Insecure_Direct_Object_Reference_Prevention_Cheat_Sheet.html)
- 이 저장소: [30 이미지 올리기](./30-image-upload.md), [38 회원정보 수정](./38-member-profile-update.md)의 IDOR, [43 Open Graph](./43-open-graph-preview.md), [06 JPA](./06-jpa-entity-mapping.md)의 N+1
