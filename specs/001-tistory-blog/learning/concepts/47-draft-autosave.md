# 임시저장과 자동 저장: 글의 상태, 처음 POST 그 뒤 PUT, 1분 타이머

> 스텝 13(T059, POST-08)에서 썼다. 먼저 [25 React 폼과 데이터 불러오기](./25-react-forms-data.md)(제어 컴포넌트, `useEffect`), [17 멱등성과 Redis](./17-idempotency-redis.md)(Idempotency-Key), [22 입력 검증](./22-bean-validation.md)을 보면 좋다.

## 1. 이 문서로 배우는 것

- 글의 **상태**(임시저장 → 발행)와 "되돌릴 수 없는 이동"을 서버 규칙으로 지키는 법
- 상태에 따라 달라지는 검증(발행만 제목 필수)을 어디에 두나
- 임시저장을 **처음 한 번 POST, 그 뒤로는 PUT**으로 나누는 이유와 연타 방지 키
- 브라우저에서 1분마다 무언가를 하는 법: `setInterval`, 그리고 React에서 생기는 **낡은 값(stale closure)** 문제와 `useRef`
- 자동 저장이 지켜야 할 것: 바뀐 것만, 한 번에 하나씩, 불러오기 전에는 저장하지 않기
- 임시저장 글이 남에게 새지 않는 이유(가시성 판단)

## 2. 왜 필요한가

긴 글을 쓰다가 브라우저가 꺼지거나 실수로 탭을 닫으면 다 날아간다. 그리고 글을 한 번에 다 쓰는 사람은 드물다. 오늘 반쯤 쓰고, 내일 이어 쓰고, 다 되면 발행한다.

명세 POST-08: "수동 저장과 1분 간격 자동 저장, 임시저장 목록에서 불러오기. 주인에게만 보인다." 수용 시나리오(US5-1): 글을 쓰는 중 1분이 지나거나 저장을 누르면 임시저장되고, 임시저장 목록에서 불러와 이어 쓸 수 있다.

이것을 만들려면 세 가지를 정해야 한다.

1. 서버: 아직 발행하지 않은 글을 어떻게 저장하고, 누구에게 보여 주나
2. 서버: 임시저장 글이 발행 글이 되는 규칙
3. 화면: 언제, 어떻게 저장 요청을 보내나

## 3. 기본 개념

### 3.1 글의 상태와 이동

`post.status` 칸은 처음부터(스텝 1의 schema.sql) `DRAFT`, `PUBLISHED`, `SCHEDULED` 셋이었다. 스텝 12까지는 `PUBLISHED`만 받았다.

상태 사이의 이동을 그림으로 그리면(상태 기계):

```
         POST(DRAFT)           PUT(PUBLISHED)
 (없음) ─────────────▶ DRAFT ─────────────────▶ PUBLISHED
   │                    │ ▲                         │
   │                    └─┘ PUT(DRAFT): 다시 저장    └─▶ PUT(DRAFT): 400 (되돌릴 수 없음)
   └──────────────────────────────────────────────▶ PUBLISHED
                    POST(PUBLISHED): 바로 발행
```

- `DRAFT → PUBLISHED`: 그때가 **처음 발행 시각**(`published_at`). 목록 순서의 기준이다.
- `PUBLISHED → DRAFT`: 막는다(API 명세). 한 번 발행한 글은 이미 누군가 봤고, 주소가 공유됐고, 댓글이 달렸을 수 있다. 숨기고 싶으면 비공개로 바꾼다.

규칙은 **서버**에 둔다. 화면이 "발행한 글에는 임시저장 버튼을 안 보여 준다"고 해도, 누군가 API를 직접 부를 수 있기 때문이다.

### 3.2 상태에 따라 달라지는 검증

발행은 제목이 필수(1~200자)이고, 임시저장은 제목이 비어도 된다. 그런데 Bean Validation의 `@NotBlank`는 칸 하나만 보고 판단한다. "status가 PUBLISHED일 때만"을 표현하지 못한다.

방법은 몇 가지다.

| 방법 | 설명 |
| --- | --- |
| 검증 그룹(`groups`) | `@NotBlank(groups = Publish.class)`, 컨트롤러가 status를 보고 그룹을 골라 검증. 설정이 늘어난다 |
| 클래스 수준 제약 | `@ValidPost`를 직접 만들어 객체 전체를 본다. 코드가 흩어진다 |
| **검증 뒤 한 번 더 확인하는 메서드** | 형식(길이 등)은 애너테이션, 칸 사이의 규칙은 DTO 메서드 |

이 프로젝트는 이미 `PostSaveRequest.checkSupported()`라는 "애너테이션 검사 뒤에 부르는 메서드"가 있었다(아직 없는 기능 값을 400으로). 그래서 제목 규칙도 거기로 옮겼다. `@Size(max = 200)`은 상태와 상관없으니 애너테이션에 남았다.

### 3.3 처음 POST, 그 뒤 PUT

임시저장 글은 **여러 번** 저장된다(1분마다). 매번 POST로 새 글을 만들면 글이 수십 개 생긴다. 그래서:

- 처음 한 번: `POST /api/posts` (status `DRAFT`) → 서버가 글 번호(id)를 준다
- 그 뒤: `PUT /api/posts/{id}` → 같은 글을 고친다
- 발행: 이미 번호가 있으면 `PUT /api/posts/{id}` (status `PUBLISHED`)

**왜 첫 POST에 Idempotency-Key가 필요한가** ([17](./17-idempotency-redis.md)): 첫 POST의 응답이 네트워크에서 사라지면 화면은 번호를 모른다. 다시 보내면 글이 두 개가 된다. 같은 키로 다시 보내면 서버가 처음 응답(같은 번호)을 돌려준다. PUT은 같은 요청을 여러 번 보내도 결과가 같아(멱등) 키가 필요 없다.

이 화면은 **발행용 키와 첫 임시저장용 키를 따로** 둔다. 둘은 다른 요청이다. 같은 키를 쓰면, 첫 임시저장 응답을 서버가 기억하고 있다가 발행 요청에도 그 응답(status `DRAFT`)을 돌려준다.

### 3.4 브라우저에서 1분마다: `setInterval`

```js
const timer = setInterval(() => console.log('1분'), 60_000)
clearInterval(timer)   // 멈춤
```

React 컴포넌트에서는 화면이 열릴 때 시작하고, 닫힐 때 멈춰야 한다. `useEffect`가 그 자리다([25](./25-react-forms-data.md)).

```tsx
useEffect(() => {
  const timer = setInterval(save, 60_000)
  return () => clearInterval(timer)   // 화면을 떠날 때
}, [])
```

### 3.5 낡은 값 문제 (stale closure)

위 코드에는 함정이 있다. React 컴포넌트 함수는 **입력할 때마다 다시 실행**되고, 그때마다 `title`, `save`가 새로 만들어진다. 그런데 `useEffect(..., [])`는 **처음 한 번만** 실행됐으므로, 타이머가 들고 있는 `save`는 **처음 그렸을 때의 `save`**이고, 그 안의 `title`은 처음 값(빈 문자열)이다.

```
1번째 그리기: title = ''      save₁ (title=''를 봄)  ← 타이머가 이것을 잡음
2번째 그리기: title = '안'    save₂
3번째 그리기: title = '안녕'  save₃
1분 뒤: 타이머가 save₁ 실행 → 빈 제목을 저장!
```

Thymeleaf로 치면, 페이지를 처음 그릴 때의 모델 값을 자바스크립트에 박아 넣고, 사용자가 입력해도 그 값만 쓰는 것과 같다.

해결은 여러 가지인데, 이 프로젝트는 **ref에 최신 함수를 넣어 두는** 방법을 썼다.

- `useRef`는 그리기를 다시 해도 **같은 상자**를 준다. 상자 안의 `.current`는 마음대로 바꿀 수 있고, 바꿔도 다시 그리지 않는다.
- 그리기마다 `autoSave.current = (최신 값을 보는 새 함수)`로 바꿔 넣는다.
- 타이머는 상자를 들고 있다가, 1분마다 **그때의** `autoSave.current()`를 부른다.

다른 방법: `useEffect(..., [title, contentHtml, ...])`로 값이 바뀔 때마다 타이머를 다시 만들기. 그러면 입력할 때마다 1분이 처음부터 다시 세져서, 계속 입력하는 사람은 영원히 자동 저장되지 않는다.

### 3.6 자동 저장이 지켜야 할 것

| 규칙 | 왜 |
| --- | --- |
| 바뀐 것이 없으면 건너뜀 | 1분마다 같은 내용을 보내면 서버와 DB만 바쁘다. 수정 시각도 쓸데없이 바뀐다 |
| 아무것도 안 쓴 새 글은 건너뜀 | 글쓰기 화면을 열어 두기만 해도 빈 임시저장 글이 쌓인다 |
| 한 번에 하나씩 | 첫 POST가 끝나기 전에 다음 저장이 나가면 번호가 없어 POST가 또 나간다(글 두 개). 자동 저장과 발행이 겹쳐도 순서가 섞인다 |
| 발행한 글을 고칠 때는 안 함 | 발행 글은 임시저장으로 못 돌린다(3.1) |
| **불러오기 전에는 안 함** | 아래 |

마지막 줄은 이 스텝에서 만들다 찾은 함정이다. 임시저장 글을 고치는 화면은 열리자마자 서버에서 글을 불러온다. 처음 만든 코드는 "수정 화면이면 상태를 `DRAFT`로 시작"했다. 그런데 불러오기가 1분 넘게 걸리거나 실패하면, 타이머가 **빈 입력값**을 그 글에 `PUT`해서 쓰던 글을 지워 버린다. 그래서 상태를 `LOADING`으로 시작하고, 불러온 뒤에야 `DRAFT`로 바꾼다. `LOADING`이면 자동 저장하지 않는다.

### 3.7 "바뀐 것"을 아는 법: 스냅숏

저장할 입력값(제목, 본문, 카테고리, 태그, 주제, 공개 범위, 대표 이미지)을 `JSON.stringify`로 한 줄 문자열로 만든다. 마지막으로 저장한(또는 불러온) 때의 문자열을 기억해 두고, 지금 것과 같으면 바뀐 것이 없다. 객체를 칸마다 비교하는 것보다 단순하다. 배열의 순서(태그)도 그대로 비교된다.

### 3.8 임시저장 글은 누가 보나

[16 인가와 가시성](./16-authorization-visibility.md)의 판단은 처음부터 "남에게 보이는 글은 `status = PUBLISHED`"였다(`PostVisibilityPolicy`, `PostSpecifications.visibleTo`). 블로그 화면의 주인 목록(`listedIn`)도 발행 글만이다. 그래서 임시저장 글은:

- 남: 상세·목록·검색·인기 글·비슷한 글 어디에도 없다(404)
- 주인: 블로그 화면에는 없고, 관리 화면의 "글 관리"(상태: 임시저장)에만 있다

스텝 13에서 가시성 코드는 한 줄도 바꾸지 않았다. 처음 설계할 때 "발행 글만"을 조건에 넣어 둔 덕이다. 대신 테스트로 확인했다(5.5).

## 4. 동작 원리

```
글쓰기 화면 열림 (/manage/write)          상태 NEW, 번호 없음
  제목 입력 … 1분
  타이머 → autoSave.current()
    autoSaveNeeded: NEW이고 무언가 썼고 바뀌었다 → 저장
    serially: 나가 있는 요청 없음
    POST /api/posts {status: DRAFT} + Idempotency-Key(draftKey) → 201 {id: 16}
    번호 16 기억, 상태 DRAFT, "임시저장됨 13:05"
  본문 입력 … 1분
    PUT /api/posts/16 {status: DRAFT} → 200
  입력 없음 … 1분
    스냅숏이 같다 → 건너뜀
  발행 클릭
    serially: (자동 저장이 나가 있으면 끝나기를 기다림)
    PUT /api/posts/16 {status: PUBLISHED}
      서버: 제목 검사 → post.publish(now) → published_at = now
    → /16 으로 이동

다음 날: 관리 → 글 관리 → 상태 "임시저장" → 제목(없으면 "(제목 없음)") 클릭
  /manage/posts/16/edit  상태 LOADING
  GET /api/manage/posts/16 → status DRAFT, 본문 … → 상태 DRAFT, 스냅숏 기억
  이어 쓰기 → 1분마다 PUT
```

## 5. 이 프로젝트에서는

### 5.1 요청 DTO: `post/presentation/dto/PostSaveRequest.java`

```java
public record PostSaveRequest(
        @Size(max = 200, message = "제목은 200자까지입니다.")
        String title,
        ...
        @NotNull(message = "저장 상태를 골라 주세요.")
        PostStatus status,
        ...) {

    public void checkSupported() {
        List<FieldErrorDetail> errors = new ArrayList<>();
        if (status == PostStatus.PUBLISHED && (title == null || title.isBlank())) {
            errors.add(new FieldErrorDetail("title", "제목을 입력해 주세요."));
        }
        if (status == PostStatus.SCHEDULED) {
            errors.add(new FieldErrorDetail("status", "예약 발행은 아직 할 수 없습니다.")); // POST-13
        }
        ...
    }

    public PostCommand toCommand() {
        return new PostCommand(title == null ? "" : title.trim(), contentHtml == null ? "" : contentHtml, categoryId,
                topic, visibility, tagNames, status, thumbnailImageId);
    }
```

- `@NotBlank`가 빠지고 `@Size`만 남았다. 길이는 상태와 상관없는 형식 규칙이다.
- `checkSupported()`: 발행일 때만 제목 필수. 메시지는 예전 `@NotBlank`와 같게 두어, 화면과 기존 테스트(`blankTitleIsNotPublished`)가 그대로 통한다.
- 예약 발행(`SCHEDULED`)은 아직 백로그라 400. 임시저장(`DRAFT`)은 이제 통과한다.
- `toCommand()`: 제목 `null`(본문에서 빠짐)을 빈 문자열로. DB의 `title` 칸은 `NOT NULL`이라 `null`을 넣을 수 없다. 앞뒤 공백도 여기서 한 번만 뗀다.

### 5.2 엔티티: `post/domain/Post.java`

```java
public void publish(LocalDateTime now) {
    if (status == PostStatus.PUBLISHED) {
        return;
    }
    this.status = PostStatus.PUBLISHED;
    this.publishedAt = now;
}
```

- 상태를 바꾸는 일을 엔티티 메서드 하나로. 서비스가 `setStatus`, `setPublishedAt`을 따로 부르면 "발행하면서 발행 시각을 안 넣는" 실수가 생긴다.
- 이미 발행한 글이면 아무것도 안 한다. 그래서 발행 글을 `PUBLISHED`로 다시 저장(수정)해도 처음 발행 시각이 바뀌지 않는다(POST-02의 "목록 순서 그대로").

### 5.3 서비스: `post/application/PostService.java`

```java
@Transactional
public Post create(Blog blog, PostCommand command) {
    Category category = category(blog, command.categoryId());
    PostBody body = body(command.contentHtml());
    ...
    Post post = command.status() == PostStatus.DRAFT
            ? Post.draft(blog, category, command.title(), body, command.visibility(), command.topic())
            : Post.published(blog, category, command.title(), body, command.visibility(), command.topic(),
                    LocalDateTime.now(clock));
```

- 이름이 `publish`에서 `create`로 바뀌었다. 이제 새 글은 발행일 수도 임시저장일 수도 있다.
- `Post.draft`는 스텝 2부터 있던 팩토리다(그동안은 테스트 코드만 썼다). 발행 시각이 없다.

```java
@Transactional
public Post edit(Blog blog, Long postId, LoginMember member, PostCommand command) {
    Post post = findEditable(blog, postId, member);
    if (command.status() == PostStatus.DRAFT && !post.isDraft()) {
        throw BusinessException.invalidField("status", "발행한 글은 임시저장으로 되돌릴 수 없습니다. 비공개로 바꿔 주세요.");
    }
    ...
    post.edit(category, command.title(), body, command.visibility(), command.topic());
    ...
    if (command.status() == PostStatus.PUBLISHED) {
        post.publish(LocalDateTime.now(clock));
    }
```

- 2줄: 주인 검사·숨김 검사가 먼저(404 → 401 → 403 순서, [16](./16-authorization-visibility.md)).
- 3~5줄: 되돌리기 금지를 **값을 바꾸기 전에** 검사한다. 뒤에서 검사하면 이미 바뀐 본문이 트랜잭션 롤백으로 되돌려지긴 하지만, 읽는 사람이 "고친 뒤 거절"로 오해하기 쉽다.
- 마지막: `PUBLISHED`로 저장하면 `publish`. 임시저장 글이면 이때 발행되고, 발행 글이면 아무 일도 없다(5.2).

### 5.4 화면: `frontend/src/components/editor/draft.ts`

자동 저장할지 판단하는 순수 함수. 화면 없이 테스트한다([46](./46-entry-routing-write-button.md)의 `writeUrl`과 같은 방식).

```ts
export function autoSaveNeeded(state: AutoSaveState): boolean {
  if (state.status !== 'NEW' && state.status !== 'DRAFT') {
    return false
  }
  if (state.busy || state.blinded || state.snapshot === state.lastSaved) {
    return false
  }
  return state.status === 'DRAFT' || state.title.trim() !== '' || !isEmptyBody(state.html)
}
```

- 1~3줄: 새 글과 임시저장 글만. `LOADING`(불러오는 중), `PUBLISHED`는 여기서 걸러진다(3.6).
- 4~6줄: 저장 중이거나, 숨긴 글이거나, 바뀐 것이 없으면 건너뜀.
- 7줄: 새 글은 무언가 써야 저장. 이미 임시저장된 글은 내용을 다 지운 것도 "바뀐 것"이니 저장한다.

`isEmptyBody`: Tiptap은 빈 본문을 `<p></p>`로 준다. 태그를 지우고 공백만 남으면 빈 본문, 단 이미지(`<img`)가 있으면 빈 본문이 아니다.

### 5.5 화면: `pages/manage/PostWritePage.tsx`

**타이머와 ref** (3.5):

```tsx
const autoSave = useRef<() => void>(() => {})
autoSave.current = () => {
  const body = formValues()
  const run = autoSaveNeeded({
    status: postState, busy: inFlight.current !== null, blinded: blind !== null,
    title, html: contentHtml, snapshot: snapshotOf(body), lastSaved: lastSaved.current,
  })
  if (run) {
    void saveDraft()
  }
}
useEffect(() => {
  const timer = window.setInterval(() => autoSave.current(), AUTO_SAVE_MS)
  return () => window.clearInterval(timer)
}, [])
```

- 2줄: 그리기마다 최신 값을 보는 함수로 바꿔 넣는다.
- 12줄: 타이머는 함수가 아니라 **상자(`autoSave`)**를 들고 있다가 그때의 `.current`를 부른다.
- 13줄: 화면을 떠나면 타이머를 멈춘다. 안 멈추면 다른 화면에서도 1분마다 저장 요청이 나간다.
- `void saveDraft()`: 결과(Promise)를 기다리지 않는다는 표시. 실패는 `saveDraft` 안에서 화면에 알린다.

**한 번에 하나씩**:

```tsx
async function serially<T>(request: () => Promise<T>): Promise<T> {
  while (inFlight.current) {
    await inFlight.current.catch(() => undefined)
  }
  const running = request()
  inFlight.current = running
  try {
    return await running
  } finally {
    inFlight.current = null
  }
}
```

- `inFlight`: 나가 있는 저장 요청(Promise). 없으면 `null`.
- 2~4줄: 있으면 끝나기를 기다린다. 앞 요청이 실패해도(`catch`) 다음 요청은 보낸다.
- 5줄: `request`는 **함수**로 받는다. 기다린 뒤에 실행해야 그때의 글 번호(`savedId.current`)를 본다. 발행 버튼은 `() => savedId.current !== null ? PUT : POST`를 넘기므로, 자동 저장의 첫 POST가 끝나 번호가 생겼으면 PUT으로 간다.
- 자바스크립트는 한 줄기(single thread)라 "검사(`while`) → 넣기(`inFlight.current = running`)" 사이에 다른 코드가 끼어들지 않는다. 그래서 자바의 `synchronized` 없이도 둘이 동시에 나가지 않는다.

**처음 POST, 그 뒤 PUT** (3.3):

```tsx
await serially(async () => {
  if (savedId.current === null) {
    const saved = await api<PostSaved>('/api/posts',
      { method: 'POST', body, idempotencyKey: draftKey.current })
    savedId.current = String(saved.id)
    loadDraftCount()
  } else {
    await api<PostSaved>(`/api/posts/${savedId.current}`, { method: 'PUT', body })
  }
})
lastSaved.current = snapshotOf(values)
```

- `savedId`: 수정 화면이면 주소의 번호로 시작하고, 새 글이면 첫 임시저장 뒤에 생긴다. 바뀌어도 화면을 다시 그릴 필요가 없어 `useState`가 아니라 `useRef`.
- 마지막 줄: 저장을 **시작할 때의** 값으로 스냅숏을 남긴다. 저장하는 동안 사용자가 더 입력했으면 다음 1분에 그것이 "바뀐 것"으로 저장된다.

**불러오기 전에는 저장 안 함** (3.6): `useState<PostState>(editing ? 'LOADING' : 'NEW')`, 불러온 뒤 `setPostState(post.status)`.

### 5.6 테스트

- `DraftIntegrationTest`(서버):
  - `draftWithoutTitleIsSavedAndOnlyOwnerSeesIt`: 제목 없이 201, 발행 시각 없음, 블로그 목록(주인에게도)에 없음, 남과 비회원은 404, 주인은 임시저장 목록·편집용 조회로 본다
  - `draftIsSavedAgainThenPublished`: 다시 저장해도 임시저장, 제목 없이 발행 400(글은 그대로), 제목 넣고 발행하면 발행 시각이 생기고 남도 본다
  - `publishedPostCannotGoBackToDraft`: 400 `status`
  - `onlyOwnerSavesDrafts`: 남의 임시저장 글 PUT은 404(있는 줄도 모름), 남의 블로그에 POST는 403
- `draft.test.ts`(화면 판단, Vitest 7개)
- 헤드리스 Chrome으로 실제 화면 확인(스텝 노트): 새 글에 제목·본문을 넣고 64초 기다리면 임시저장 글이 1개 늘고 "임시저장됨 hh:mm", 1분 더 기다려도 더 늘지 않음.

## 6. 자주 하는 실수와 함정

- **`setInterval` 안에서 state를 직접 읽음**: 낡은 값(3.5). 화면에는 최신 값이 보이는데 저장되는 것은 처음 값이라 찾기 어렵다.
- **값이 바뀔 때마다 타이머를 다시 만듦**: 계속 입력하는 동안 자동 저장이 한 번도 안 된다.
- **언마운트 때 `clearInterval`을 안 함**: 화면을 떠나도 1분마다 요청이 나간다. React 개발 모드(StrictMode)는 effect를 두 번 실행하므로 타이머가 두 개 돈다([34](./34-view-count.md)의 StrictMode).
- **저장을 겹쳐 보냄**: 첫 POST 응답 전에 두 번째 저장이 나가면 글이 두 개 생긴다.
- **불러오기 전 자동 저장**: 빈 입력값으로 글을 덮는다(3.6).
- **발행과 임시저장에 같은 연타 방지 키**: 발행 요청이 첫 임시저장의 응답(DRAFT)을 받는다.
- **되돌리기 금지를 화면에서만**: API를 직접 부르면 뚫린다. 서버가 400.
- **임시저장 글을 목록 조건에서 빼먹음**: 이 프로젝트는 처음부터 `PUBLISHED` 조건이 있었다. 새로 만드는 목록(예: 백로그의 전체 검색)도 같은 Specification을 써야 한다.

## 7. 직접 해 보기

### 7.1 화면

```bash
./scripts/build-frontend.sh && ./mvnw spring-boot:run
```

1. 내 블로그 `/manage/write`에서 제목만 쓰고 1분 기다린다. 위쪽에 "임시저장됨 hh:mm", "임시저장 목록"의 수가 1 늘어난다.
2. 탭을 닫는다. 관리 → 글 관리 → 상태 "임시저장"에서 그 글을 열어 이어 쓴다.
3. 제목을 지우고 발행 → "제목을 입력해 주세요." 제목을 넣고 발행 → 글 상세로 간다.
4. 다른 브라우저(또는 시크릿 창)로 임시저장 글 번호의 주소를 열면 404.

### 7.2 낡은 값 직접 보기 (공부용 브랜치에서)

`PostWritePage.tsx`의 타이머 effect를 이렇게 바꾸고 `AUTO_SAVE_MS`를 10초(`10_000`)로 줄인다.

```tsx
useEffect(() => {
  const timer = window.setInterval(() => console.log('타이머가 보는 제목:', title), AUTO_SAVE_MS)
  return () => window.clearInterval(timer)
}, [])
```

개발 서버에서 제목을 입력하며 콘솔을 보면 계속 빈 문자열이다. 끝나면 `git restore .`.

### 7.3 API로

```bash
# 로그인 쿠키를 c.txt에 담은 뒤
curl -s -b c.txt -H 'Host: {주소}.blog.test' -H 'X-Requested-With: XMLHttpRequest' \
  -H 'Content-Type: application/json' -H "Idempotency-Key: $(uuidgen)" \
  -d '{"title":"","contentHtml":"<p>쓰는 중</p>","visibility":"PUBLIC","status":"DRAFT"}' \
  http://localhost:8080/api/posts
```

201과 `"status":"DRAFT"`. 받은 번호로 `PUT .../api/posts/{id}`에 `"status":"PUBLISHED"`(제목 없이) → 400 `title`.

### 7.4 테스트

```bash
./mvnw test -Dtest=DraftIntegrationTest
cd frontend && npx vitest run src/components/editor/draft.test.ts
```

## 8. 확인 문제

1. 임시저장은 제목이 비어도 되는데, 왜 `title` 칸에서 `@NotBlank`를 지우고 `@Size`는 남겼나?

<details><summary>답</summary>

`@NotBlank`는 상태에 따라 달라지는 규칙(발행만 필수)이라 애너테이션 하나로 표현할 수 없어 `checkSupported()`로 옮겼다. 200자 제한은 상태와 상관없는 형식 규칙이라 애너테이션에 남았다.

</details>

2. 자동 저장이 1분마다 `POST /api/posts`를 보내면 무슨 일이 생기나?

<details><summary>답</summary>

1분마다 새 임시저장 글이 생긴다. 처음 한 번만 POST로 번호를 받고, 그 뒤로는 그 번호로 PUT해야 같은 글이 고쳐진다.

</details>

3. 타이머 effect가 `[]`일 때, 타이머 안에서 `title` state를 직접 읽으면 무엇이 보이나? 이 프로젝트는 어떻게 피했나?

<details><summary>답</summary>

처음 그렸을 때의 값(빈 문자열)이 계속 보인다(낡은 값). 그리기마다 최신 값을 보는 함수를 `useRef` 상자(`autoSave.current`)에 넣고, 타이머는 상자의 `.current`를 부른다.

</details>

4. 새 글에서 자동 저장의 첫 POST가 아직 응답을 기다리는 중에 발행을 누르면? `serially`가 없으면?

<details><summary>답</summary>

`serially`가 있으면 발행은 첫 POST가 끝나기를 기다린 뒤, 그때 생긴 번호로 PUT(PUBLISHED)한다. 글은 하나다. 없으면 발행도 번호가 없어 POST(PUBLISHED)로 나가, 임시저장 글과 발행 글 두 개가 생긴다.

</details>

5. 수정 화면의 처음 상태를 `DRAFT`로 두면 어떤 위험이 있나?

<details><summary>답</summary>

글을 불러오기 전(또는 불러오기 실패)에 타이머가 돌면, 빈 입력값을 그 글에 PUT해 쓰던 내용을 지운다. 그래서 `LOADING`으로 시작하고 불러온 뒤 실제 상태로 바꾼다.

</details>

6. 스텝 13에서 가시성 코드(`PostVisibilityPolicy`, `PostSpecifications`)를 고치지 않았는데도 임시저장 글이 남에게 안 보이는 이유는?

<details><summary>답</summary>

처음부터 "남에게 보이는 글"과 "블로그 화면의 주인 목록" 조건에 `status = PUBLISHED`가 들어 있었다. 임시저장 글은 그 조건에 걸리지 않는다. 테스트(`draftWithoutTitleIsSavedAndOnlyOwnerSeesIt`)가 확인한다.

</details>

## 9. 더 읽을거리

- MDN, [setInterval](https://developer.mozilla.org/en-US/docs/Web/API/Window/setInterval)
- React 문서, [Referencing values with refs](https://react.dev/learn/referencing-values-with-refs), [Synchronizing with Effects](https://react.dev/learn/synchronizing-with-effects)
- Dan Abramov, [Making setInterval Declarative with React Hooks](https://overreacted.io/making-setinterval-declarative-with-react-hooks/): 낡은 값 문제와 ref 해법
- RFC 9110, 9.2.2 Idempotent Methods: PUT은 멱등, POST는 아님
- 이 저장소: [17 멱등성](./17-idempotency-redis.md), [16 인가와 가시성](./16-authorization-visibility.md), [25 React 폼](./25-react-forms-data.md)
