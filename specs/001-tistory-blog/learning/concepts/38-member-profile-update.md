# 38. 회원정보 수정: 부분 수정, 비밀번호 바꾸기, 남의 것을 가리키는 번호

> 관련 스텝: [스텝 9](../step-09.md) (T055, T055a) · 관련 개념: [40-attempt-limit](./40-attempt-limit.md), [09-password-hashing](./09-password-hashing.md), [21-signup-login](./21-signup-login.md), [22-bean-validation](./22-bean-validation.md), [30-image-upload](./30-image-upload.md), [23-transactions-locking](./23-transactions-locking.md), [25-react-forms-data](./25-react-forms-data.md)

## 1. 이 문서로 배우는 것

- **PATCH로 부분 수정하기**: 보낸 칸만 바꾸고, 안 보낸 칸(null)은 그대로 두기
- 닉네임 바꾸기: 앞뒤 공백, 중복 검사에서 **나 자신은 빼기**, 대소문자만 바꾸기, 동시에 같은 닉네임을 가져갈 때(UNIQUE가 마지막 판단)
- 비밀번호 바꾸기: **지금 비밀번호 확인**이 필요한 이유, `PasswordEncoder.matches`, 새 비밀번호 규칙 재사용
- 소셜 가입 회원(비밀번호 없음)은 403
- **IDOR**(남의 것을 가리키는 번호): 프로필 사진 번호로 남의 이미지를 쓰지 못하게
- 상태 코드 순서 401 → 400을 지키려고 `@Valid` 대신 `RequestValidator`
- 화면: 마이페이지 `/me`, 사진 고르면 바로 올리고 저장, 저장 결과를 화면 상태에 반영

**먼저 알면 좋은 것**: bcrypt와 `matches`([09](./09-password-hashing.md)), 가입의 닉네임·비밀번호 규칙([21](./21-signup-login.md)), Bean Validation과 상태 코드 순서([22](./22-bean-validation.md)), 이미지 올리기([30](./30-image-upload.md)).

## 2. 왜 필요한가

AUTH-05 "닉네임, 프로필 사진, 비밀번호를 바꾼다." 화면 하나에 기능 셋이지만, 각각 함정이 있다.

- 닉네임은 **겹치면 안 된다**. 그런데 "지금 내 닉네임"과 같은지 검사하면 대소문자만 바꾸려 해도 "이미 쓰는 닉네임"이 된다.
- 비밀번호는 로그인한 상태에서 바꾸는데도 **지금 비밀번호를 다시 묻는다**. 왜?
- 프로필 사진은 "먼저 이미지를 올리고(번호를 받고) → 그 번호를 내 정보에 저장"한다. 그 번호에 **남이 올린 이미지 번호**를 넣으면?

## 3. 기본 개념

### 3.1 PUT과 PATCH, 그리고 null

| 방식 | 뜻 | 안 보낸 칸 |
| --- | --- | --- |
| `PUT` | 자원 전체를 이 내용으로 **바꾼다** | 비워진다(또는 기본값) |
| `PATCH` | 보낸 부분만 **고친다** | 그대로 |

contracts는 `PATCH /api/me { nickname?, profileImageId? }`다. `?`는 "보내도 되고 안 보내도 된다"는 뜻이다. 닉네임만 바꾸는 요청에 사진 번호가 없다고 사진이 지워지면 안 된다.

JSON을 자바 레코드로 받으면, 보내지 않은 칸은 `null`이 된다. 그래서 서비스는 "null이면 건드리지 않는다"로 짠다.

한계도 있다. 이 방식으로는 "보내지 않음"과 "null을 보냄(지우기)"을 구분하지 못한다. 그래서 지금은 **프로필 사진을 지우는(없애는) 방법이 없다**. 구분하려면 `Optional`을 칸으로 쓰거나, JSON Merge Patch(RFC 7396) 같은 규칙을 따르거나, 지우기 API를 따로 둔다. 명세에 지우기가 없어서 이 스텝에서는 하지 않았다.

### 3.2 지금 비밀번호를 다시 묻는 이유

로그인한 사람이 자리를 비운 사이 다른 사람이 그 컴퓨터로 비밀번호를 바꾸면, 진짜 주인은 **계정을 잃는다**. 로그인 쿠키를 훔친 공격자도 마찬가지다. 비밀번호를 아는 사람만 비밀번호를 바꿀 수 있게 해서, "로그인 상태를 잠깐 손에 넣은 것"이 "계정을 영영 빼앗는 것"으로 커지지 않게 한다.

서버는 비밀번호 원문을 갖고 있지 않다. bcrypt 해시만 있다([09](./09-password-hashing.md)). 그래서 비교는 `passwordEncoder.matches(입력한 글자, 저장된 해시)`로 한다. 해시에 들어 있는 salt로 입력을 다시 해시해서 같은지 본다.

### 3.3 IDOR: 남의 것을 가리키는 번호

**IDOR(Insecure Direct Object Reference)**: 요청에 든 번호(id)를 그대로 믿고 그 자원을 쓰거나 바꾸는 취약점이다. 예:

```
PATCH /api/me  { "profileImageId": 31 }      ← 31은 다른 회원이 올린 이미지
```

서버가 "31번 이미지가 있나?"만 보면, 나는 남의 사진을 내 프로필로 쓸 수 있다. 사진이 비공개 용도로 올린 것이었다면(예: 아직 발행하지 않은 글에 넣은 사진) 남의 이미지를 엿보는 길이 되기도 한다.

막는 법은 하나다. **번호를 받으면 "그것이 이 사람이 쓸 수 있는 것인가"를 함께 본다.** 이미지 표에는 올린 사람 칸(`uploader_id`)이 있으니, "이 번호이고 **내가 올린** 이미지"인지 확인한다. 아니면 400(`profileImageId` 칸 오류)이다. 남의 이미지가 있다는 사실도 알려 주지 않도록, 없는 번호와 같은 문장("이미지를 찾을 수 없습니다")을 쓴다.

내 글 관리의 일괄 처리도 같은 생각이다. "내 글 중에서" 번호로 찾는다([37](./37-filtered-list-bulk-actions.md) 5.5).

### 3.4 "나 말고 이 닉네임을 쓰는 회원이 있나"

닉네임 중복 검사를 `existsByNickname(새 닉네임)`으로 하면 문제가 둘 있다.

1. 지금 닉네임 `Jiwon`을 `jiwon`으로 바꾸려 하면, DB 정렬 규칙(`utf8mb4_0900_ai_ci`, 대소문자 무시, [31](./31-tags-many-to-many.md) 3.5)에서 `jiwon`과 `Jiwon`이 같다. 그 행은 **나 자신**인데 "이미 쓰는 닉네임"이 된다.
2. 같은 닉네임을 그대로 다시 저장해도 409가 된다.

그래서 **나를 뺀** 회원 중에 있는지 묻는다: `existsByNicknameAndIdNot(nickname, myId)`.

그래도 "확인 → 저장" 사이에 다른 회원이 같은 닉네임으로 바꾸면 둘 다 확인을 통과한다(경쟁 조건, [23](./23-transactions-locking.md)). 마지막 판단은 DB의 `UNIQUE(nickname)`이 한다. 늦게 저장한 쪽은 `DataIntegrityViolationException`을 받고, 그것을 409 `NICKNAME_TAKEN`으로 바꾼다. 가입(스텝 4)과 같은 방식이다.

## 4. 동작 원리

### 4.1 닉네임·사진

```
blog.test/me  (MyPage)
  [사진 바꾸기] → 파일 고름
    POST /api/images                      ImageService.upload → { id: 77, thumbnailUrl }
    PATCH /api/me { profileImageId: 77 }  MeService.update
                                            77번 이미지가 있고 uploader가 나인가? 아니면 400
                                            member.changeProfileImage(77)
                                            saveAndFlush
                                          ← Me { ..., profileImageUrl: "/uploads/t_....png" }
  닉네임 칸 → [저장]
    PATCH /api/me { nickname: "  새이름 " }  앞뒤 공백 제거 → 비었으면 400
                                            나 말고 쓰는 회원? → 409
                                            member.changeNickname
                                            saveAndFlush (동시에 같은 이름이면 UNIQUE → 409)
```

### 4.2 비밀번호

```
  PUT /api/me/password { currentPassword, newPassword }
    MeService.changePassword
      비밀번호 해시가 없음(소셜 가입) → 403
      matches(currentPassword, hash) 실패 → 400 (currentPassword)
      PasswordRule.check("newPassword", ...) 실패 → 400 (newPassword)
      member.changePassword(encode(newPassword))   변경 감지 → 커밋 때 UPDATE
  ← 204
```

비밀번호를 바꿔도 **지금 로그인 상태는 그대로**다. 다른 기기에서 로그인해 둔 세션(Refresh 토큰)도 지금은 끊지 않는다. 명세에 정한 것이 없어서다. "비밀번호를 바꾸면 다른 기기는 모두 로그아웃"은 흔한 보안 기능이라 뒤에 더할 만하다(스텝 노트의 "아직 채우지 않은 것").

## 5. 이 프로젝트에서는

### 5.1 `member/domain/Member.java`에 더한 메서드

```java
/** 회원정보 수정 (AUTH-05). 중복 검사는 MeService가 하고, 마지막 판단은 DB UNIQUE가 한다. */
public void changeNickname(String nickname) {
    this.nickname = nickname;
}

public void changeProfileImage(Long profileImageId) {
    this.profileImageId = profileImageId;
}

/** 이메일 가입 회원의 비밀번호 바꾸기. bcrypt 해시를 받는다. */
public void changePassword(String passwordHash) {
    this.passwordHash = passwordHash;
}
```

setter 대신 **뜻이 있는 이름**의 메서드를 둔다. `changePassword`는 원문이 아니라 해시를 받는다. 엔티티가 `PasswordEncoder`를 알 필요가 없게, 해시는 서비스가 만든다.

### 5.2 `member/application/MeService.update`

```java
@Transactional
public void update(Long memberId, String rawNickname, Long profileImageId) {
    Member member = member(memberId);
    if (rawNickname != null) {
        String nickname = rawNickname.trim();
        if (nickname.isEmpty()) {
            throw BusinessException.invalidField("nickname", "닉네임을 입력해 주세요.");
        }
        if (memberRepository.existsByNicknameAndIdNot(nickname, memberId)) {
            throw new BusinessException(ErrorCode.NICKNAME_TAKEN);
        }
        member.changeNickname(nickname);
    }
    if (profileImageId != null) {
        imageRepository.findById(profileImageId)
                .filter(image -> memberId.equals(image.getUploaderId()))
                .orElseThrow(() -> BusinessException.invalidField("profileImageId", "이미지를 찾을 수 없습니다."));
        member.changeProfileImage(profileImageId);
    }
    try {
        memberRepository.saveAndFlush(member);
    } catch (DataIntegrityViolationException e) {
        // 확인과 저장 사이에 다른 회원이 같은 닉네임을 가져갔다 (UNIQUE uk_member_nickname)
        throw new BusinessException(ErrorCode.NICKNAME_TAKEN);
    }
}
```

- `rawNickname != null`, `profileImageId != null`: PATCH의 "보낸 칸만"(3.1).
- `trim()` 뒤 비었는지: 가입과 같은 규칙. `"   "`은 닉네임이 아니다. 20자 제한은 DTO의 `@Size`가 먼저 본다.
- `existsByNicknameAndIdNot`: 파생 쿼리. `WHERE nickname = ? AND id <> ?`(3.4).
- `.filter(image -> memberId.equals(image.getUploaderId()))`: IDOR 막기(3.3). `memberId.equals(...)`로 쓰면 `getUploaderId()`가 null이어도 NPE가 나지 않는다.
- `saveAndFlush`: 그냥 두면 UPDATE는 트랜잭션이 **커밋될 때** 나가서, UNIQUE 위반 예외가 이 메서드 밖(커밋 시점)에서 나 409로 바꿀 수 없다. `flush`로 지금 UPDATE를 보내 예외를 여기서 잡는다. 가입·카테고리와 같은 요령이다.

### 5.3 `MeService.changePassword`

```java
@Transactional
public void changePassword(Long memberId, String currentPassword, String newPassword) {
    Member member = member(memberId);
    if (member.getPasswordHash() == null) {
        throw new BusinessException(ErrorCode.FORBIDDEN);
    }
    if (!passwordEncoder.matches(currentPassword, member.getPasswordHash())) {
        throw BusinessException.invalidField("currentPassword", "지금 비밀번호가 맞지 않습니다.");
    }
    PasswordRule.check("newPassword", newPassword);
    member.changePassword(passwordEncoder.encode(newPassword));
}
```

- 소셜 가입 회원은 `password_hash`가 NULL이다. 바꿀 비밀번호가 없으니 403(contracts "이메일 가입 회원만(아니면 403)").
- 지금 비밀번호가 틀리면 400이고, 칸 이름 `currentPassword`를 준다. 오류 코드를 새로 만들지 않고 `VALIDATION_FAILED`의 칸 오류로 했다. 화면은 그 칸 아래에 문장을 보여 준다. 로그인 실패(401 `LOGIN_FAILED`)와 달리 이미 로그인한 사람이라 401은 맞지 않다.
- 확인 순서: 지금 비밀번호 → 새 비밀번호 규칙. 지금 비밀번호를 모르는 사람에게는 새 비밀번호 규칙을 알려 줄 필요가 없다.
- (T055a) 지금 비밀번호 비교는 `attemptLimiter.attempt("password-change:" + memberId, ...)` 안에서 한다. 15분 안에 5번 틀리면 15분 동안 429다. 이것이 없으면 잠깐 얻은 로그인 상태로 지금 비밀번호를 계속 맞혀 볼 수 있어서 3.2의 보호가 무너진다([40](./40-attempt-limit.md)). 위 발췌는 제한을 더하기 전 모습이다.
- `PasswordRule.check`: 가입과 **같은 규칙**(8자 이상, 영문+숫자, 72바이트, [09](./09-password-hashing.md)).
- 마지막 줄은 `save`가 없다. 트랜잭션 안에서 읽은 엔티티의 값을 바꾸면 커밋 때 UPDATE가 나간다(변경 감지).

### 5.4 `member/presentation/MeController.java`

```java
@PatchMapping("/api/me")
@PreAuthorize("isAuthenticated()")
public MeResponse update(@AuthenticationPrincipal LoginMember member, @RequestBody MeUpdateRequest request) {
    requestValidator.validate(request);
    meService.update(member.id(), request.nickname(), request.profileImageId());
    return MeResponse.from(meService.me(member.id()));
}
```

- `@PreAuthorize("isAuthenticated()")`: 비회원 401. 메서드 실행 직전에 검사한다([12](./12-spring-security-filter-chain.md)).
- `@Valid`를 붙이지 않고 본문에서 `requestValidator.validate(request)`를 부른다. `@Valid`는 **인자를 만들 때** 검사해서, 비회원이 틀린 값을 보내면 401보다 400이 먼저 난다([22](./22-bean-validation.md)). 테스트 `anonymousGets401BeforeInputErrors`가 이 순서를 본다.
- 응답은 바뀐 `Me`. 화면이 이 값으로 머리글의 닉네임·사진을 바로 바꾼다.
- `MeResponse.profileImageUrl`: 스텝 2부터 `null`로 두던 칸을 채웠다. 사진 원본이 아니라 **썸네일**(`t_….png`) 주소다. 프로필 사진은 작게 보이므로 400px 썸네일이면 충분하다([30](./30-image-upload.md)).

### 5.5 화면: `pages/me/MyPage.tsx`

```tsx
const meState = useMe()
// 저장한 뒤의 내 정보. 저장 전에는 처음 불러온 값을 쓴다
const [saved, setMe] = useState<Me | null>(null)
const me = saved ?? (meState.status === 'member' ? meState.me : null)
```

- `useMe()`는 화면을 열 때 `GET /api/me`로 한 번 읽는다. 저장하면 서버가 돌려준 새 `Me`를 `saved`에 두고, 화면은 `saved`가 있으면 그것을 쓴다. 처음 값을 `useEffect`로 상태에 복사하지 않고 **그릴 때 계산**한다. 처음에는 effect 안에서 `setMe(meState.me)`로 복사했는데, 린터(oxlint `set-state-in-effect`)가 "effect 안에서 바로 상태를 바꾸면 불필요하게 한 번 더 그린다"고 경고해서 바꿨다.
- 비회원이면 로그인 화면으로 보낸다(`redirectToLogin`, 돌아올 주소 포함).
- 소셜 가입 회원(`hasPassword: false`)에게는 비밀번호 칸 대신 안내 문장을 보여 준다(목업 mypage).

```tsx
async function changePhoto(event: ChangeEvent<HTMLInputElement>) {
  const file = event.target.files?.[0]
  event.target.value = ''
  ...
  const image = await uploadFile<{ id: number }>('/api/images', file)
  onSaved(await api<Me>('/api/me', { method: 'PATCH', body: { profileImageId: image.id } }))
}
```

- 사진은 고르는 즉시 올리고 저장한다(목업의 "사진 바꾸기" 버튼 하나). 두 요청이 이어진다: 올리기(번호 받기) → 내 정보에 번호 저장.
- `event.target.value = ''`: 같은 파일을 다시 골라도 `onChange`가 다시 일어나게 입력을 비운다.
- 머리글(`PlatformHeader`)의 닉네임은 이제 `/me` 링크다.

### 5.6 테스트 `MeUpdateIntegrationTest`

| 테스트 | 확인하는 것 |
| --- | --- |
| `anonymousGets401BeforeInputErrors` | 비회원은 틀린 입력이어도 401 |
| `nicknameChangesUnlessAnotherMemberUsesIt` | 앞뒤 공백 제거, 다른 회원 닉네임(대소문자만 다름) 409, 내 닉네임의 대소문자만 바꾸기는 됨, 공백뿐·21자 400 |
| `profileImageMustBeMyOwnUpload` | 남이 올린 이미지 번호 400, 내 이미지면 `profileImageUrl`이 썸네일, 칸을 안 보내면 사진 그대로 |
| `passwordChangeNeedsCurrentPasswordAndFollowsSignupRule` | 지금 비밀번호 틀림 400(currentPassword), 규칙 위반 400(newPassword), 바꾼 뒤 옛 비밀번호로 로그인 실패·새 비밀번호로 성공 |
| `socialMemberHasNoPasswordToChange` | 소셜 회원 403 |

## 6. 자주 하는 실수와 함정

- **PATCH에서 안 보낸 칸을 null로 덮어쓴다.** 닉네임만 바꿨는데 사진이 사라진다. null이면 건드리지 않는다.
- **닉네임 중복 검사에서 나를 빼지 않는다.** 대소문자만 바꾸거나 같은 이름으로 다시 저장할 때 409.
- **중복 검사만 믿는다.** 동시 요청은 둘 다 통과한다. UNIQUE와 `saveAndFlush` + 예외 변환.
- **비밀번호 변경에 지금 비밀번호를 묻지 않는다.** 잠깐 얻은 로그인 상태로 계정을 빼앗긴다.
- **비밀번호를 `equals`로 비교한다.** 저장된 것은 해시다. `matches`를 쓴다.
- **새 비밀번호 규칙을 따로 만든다.** 가입과 달라진다. `PasswordRule`을 재사용한다.
- **받은 번호를 그대로 믿는다(IDOR).** 남의 이미지·글·카테고리를 내 것처럼 쓰게 된다. "내 것 중에서" 찾는다.
- **"남의 것"과 "없는 것"에 다른 문장을 준다.** 남의 자원이 있다는 정보를 흘린다.
- **`@Valid`로 검사해 401보다 400이 먼저 난다.** 로그인 확인 뒤에 검사한다.
- **처음 불러온 서버 값을 effect로 상태에 복사한다.** 한 번 더 그리고, 값이 둘로 갈라진다. 그릴 때 계산하거나 저장 결과만 따로 둔다.

## 7. 직접 해 보기

준비: 코드 저장소 루트에서 `./scripts/build-frontend.sh && ./mvnw spring-boot:run`, 이메일로 가입한 회원으로 로그인.

### 7.1 화면

1. `http://blog.test:8080/me`를 연다(머리글의 닉네임을 눌러도 된다).
2. 사진을 고른다. 동그란 사진이 바로 바뀌는지 본다.
3. 닉네임의 대소문자만 바꿔 저장해 본다. 저장된다. 다른 회원의 닉네임을 넣으면 "이미 쓰고 있는 닉네임입니다".
4. 비밀번호를 틀리게 넣으면 "지금 비밀번호가 맞지 않습니다"가 그 칸 아래에 나온다.

### 7.2 IDOR 막는 것 보기

```bash
X="X-Requested-With: XMLHttpRequest"; J="Content-Type: application/json"
# B가 올린 이미지 번호를 A의 쿠키로 저장해 본다
curl -s -b jarA.txt -H "$X" -H "$J" -X PATCH -d '{"profileImageId": B의_이미지_번호}' localhost:8080/api/me -H "Host: blog.test"
# {"code":"VALIDATION_FAILED",...,"fieldErrors":[{"field":"profileImageId","reason":"이미지를 찾을 수 없습니다."}]}
```

### 7.3 401이 400보다 먼저

```bash
curl -s -H "$X" -H "$J" -X PATCH -d '{"nickname":""}' localhost:8080/api/me -H "Host: blog.test" -o /dev/null -w '%{http_code}\n'   # 401
```

### 7.4 테스트

```bash
./mvnw test -Dtest=MeUpdateIntegrationTest
```

## 8. 확인 문제

1. PUT과 PATCH의 차이와, contracts가 내 정보 수정에 PATCH를 쓴 이유는?
<details><summary>답</summary>PUT은 자원 전체를 보낸 내용으로 바꾸고, PATCH는 보낸 부분만 고친다. 닉네임만 바꾸는 요청에 사진이 없다고 사진이 지워지면 안 되므로 PATCH이고, null인 칸은 건드리지 않는다.</details>

2. 지금 방식으로 프로필 사진을 지울 수 없는 이유는?
<details><summary>답</summary>보내지 않은 칸과 null을 보낸 칸이 둘 다 자바에서 null이라 구분하지 못한다. 지우려면 Optional 칸, JSON Merge Patch 규칙, 따로 둔 지우기 API 같은 방법이 필요하다.</details>

3. 닉네임 중복을 `existsByNickname`이 아니라 `existsByNicknameAndIdNot`으로 검사하는 이유는?
<details><summary>답</summary>DB 정렬 규칙이 대소문자를 무시해서, 내 닉네임의 대소문자만 바꾸거나 같은 이름으로 다시 저장할 때 나 자신이 "이미 쓰는 회원"으로 걸린다. 나를 빼고 묻는다.</details>

4. 그래도 `saveAndFlush`와 `DataIntegrityViolationException` 처리가 필요한 이유는?
<details><summary>답</summary>확인과 저장 사이에 다른 회원이 같은 닉네임을 가져가면 둘 다 확인을 통과한다. 마지막 판단은 UNIQUE 제약이 하고, flush로 이 메서드 안에서 UPDATE를 보내야 그 예외를 잡아 409로 바꿀 수 있다.</details>

5. 로그인한 사람에게도 지금 비밀번호를 묻는 이유는?
<details><summary>답</summary>자리를 비운 사이나 쿠키를 훔친 사람이 비밀번호까지 바꾸면 주인이 계정을 영영 잃는다. 비밀번호를 아는 사람만 바꾸게 해서 잠깐 얻은 로그인 상태가 계정 탈취로 커지지 않게 한다.</details>

6. IDOR이 무엇이고, 프로필 사진에서 어떻게 막았나?
<details><summary>답</summary>요청의 번호를 그대로 믿고 그 자원을 쓰는 취약점. 이미지 번호를 받으면 그 이미지의 uploader_id가 나인지 함께 확인하고, 아니면 없는 것과 같은 400을 준다.</details>

7. 지금 비밀번호가 틀렸을 때 401이 아니라 400(칸 오류)인 이유는?
<details><summary>답</summary>이미 로그인한 사람의 요청이라 "로그인이 필요하다"는 401은 맞지 않다. 입력 하나가 틀린 것이라 그 칸(currentPassword)에 문장을 준다.</details>

8. 이 컨트롤러가 `@Valid` 대신 `RequestValidator`를 쓰는 이유는?
<details><summary>답</summary>@Valid는 인자를 만들 때(메서드 전) 검사해서 비회원의 틀린 입력에 401보다 400이 먼저 난다. 상태 코드 순서 401 → 400을 지키려고 로그인 확인 뒤 본문에서 검사한다.</details>

9. 마이페이지가 서버에서 받은 내 정보를 effect로 상태에 복사하지 않고 그릴 때 계산하는 이유는?
<details><summary>답</summary>effect 안에서 바로 상태를 바꾸면 한 번 더 그리게 되고(린터 경고), 같은 값이 두 곳에 갈라진다. 저장 결과(saved)가 있으면 그것, 없으면 처음 불러온 값을 쓰면 된다.</details>

## 9. 더 읽을거리

- RFC 5789(PATCH), RFC 7396(JSON Merge Patch)
- OWASP, "Insecure Direct Object Reference Prevention Cheat Sheet", "Authentication Cheat Sheet"(비밀번호 변경 시 재인증)
- Spring Security 레퍼런스, `PasswordEncoder`, `@PreAuthorize`
- Spring Data JPA 레퍼런스, 파생 쿼리 키워드(`Not`)
- React 문서, "You Might Not Need an Effect"
