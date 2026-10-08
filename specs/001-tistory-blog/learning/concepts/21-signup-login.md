# 21. 가입·로그인·로그아웃 설계

> 관련 스텝: [스텝 4](../step-04.md) (T018, T019, T020, T026) · 관련 개념: [09-password-hashing](./09-password-hashing.md), [10-http-cookies](./10-http-cookies.md), [11-jwt](./11-jwt.md), [12-spring-security-filter-chain](./12-spring-security-filter-chain.md), [20-email-verification](./20-email-verification.md), [22-bean-validation](./22-bean-validation.md), [23-transactions-locking](./23-transactions-locking.md)

## 1. 이 문서로 배우는 것

- 가입 한 번이 화면에서 서버까지 어떤 순서로 지나가는지
- 가입 서비스의 검사 순서와, 그 전부를 **한 트랜잭션**으로 묶는 이유
- "중복 확인 후 저장" 사이의 경쟁 조건과 DB UNIQUE 제약을 마지막 방어선으로 쓰는 법
- 비밀번호 규칙(8자 이상, 영문+숫자)과 bcrypt 72바이트 한계
- **계정 열거(account enumeration)** 공격: 로그인 실패 문구를 하나로 통일하는 이유
- **타이밍 공격**: 없는 이메일에도 bcrypt 비교를 하는 이유
- 정지 회원 안내를 비밀번호가 맞은 **뒤에만** 주는 이유
- 로그아웃이 모든 블로그 주소에서 한 번에 되는 원리
- `GET /api/me`가 프론트의 "로그인 상태 확인" 역할을 하는 이유
- **열린 리다이렉트(open redirect)** 공격과 로그인 뒤 돌아갈 주소를 검사하는 법

**먼저 알면 좋은 것**: bcrypt([09](./09-password-hashing.md)), 로그인 쿠키와 JWT([10](./10-http-cookies.md), [11](./11-jwt.md)), 이메일 인증 코드([20](./20-email-verification.md)).

## 2. 왜 필요한가

스텝 3에서 "쿠키에 든 토큰으로 누구인지 아는" 장치는 만들었지만, 그 쿠키를 **처음 받는** 길이 없었다. 스텝 4는 그 입구를 만든다. 입구는 공격이 가장 많이 들어오는 곳이다.

- 남의 비밀번호를 맞혀 보려는 사람은 로그인 API를 수없이 부른다. 응답 문구나 응답 시간이 조금만 달라도 "이 이메일은 회원이다"를 알아낸다.
- 같은 닉네임으로 두 사람이 동시에 가입 버튼을 누를 수 있다.
- 로그인 화면은 `?redirect=`로 돌아갈 주소를 받는다. 이것을 검사하지 않으면 우리 로그인 화면이 피싱 사이트로 보내는 징검다리가 된다.
- 로그아웃은 "이 브라우저에서 나가기"만이 아니다. 블로그 주소가 수십 개라도(`alpha.blog.com`, `beta.blog.com`) 한 번에 모두 나가야 한다(AUTH-02).

기능 명세가 정한 것: 이메일·닉네임 중복 확인, 비밀번호 8자 이상 영문+숫자, bcrypt(AUTH-01, 공통 규칙 보안), 로그인 실패 문구 "이메일 또는 비밀번호가 맞지 않습니다"로 통일(AUTH-01), 정지 회원은 사유와 기한 안내(ADMIN-02), 로그아웃하면 모든 블로그 주소에서 비회원(AUTH-02).

## 3. 기본 개념

### 3.1 인증(authentication)의 세 단계

| 단계 | 질문 | 이 프로젝트 |
| --- | --- | --- |
| 등록(가입) | 이 사람을 무엇으로 알아볼까 | 이메일(인증됨) + 비밀번호 해시 저장 |
| 확인(로그인) | 지금 온 사람이 그 사람인가 | 이메일로 회원을 찾고 bcrypt로 비밀번호 비교 |
| 유지 | 다음 요청부터는 어떻게 알까 | 로그인 성공 시 JWT 쿠키 발급 → 요청마다 필터가 확인([11](./11-jwt.md)) |

로그인 API는 "확인"이 성공한 순간 "유지"용 쿠키를 주는 다리다. 가입도 성공하면 바로 쿠키를 줘서, 가입 직후 다시 로그인하지 않게 했다.

### 3.2 계정 열거(account enumeration)

로그인 실패 응답이 이렇다고 하자.

```
없는 이메일   → 404 "가입되지 않은 이메일입니다"
틀린 비밀번호 → 401 "비밀번호가 틀렸습니다"
```

공격자는 비밀번호를 몰라도 이메일 목록을 넣어 보며 **누가 우리 회원인지** 골라낸다. 그 목록은 피싱 메일, 다른 사이트에서 유출된 비밀번호를 대입해 보는 공격(credential stuffing)에 쓰인다. 그래서 두 경우를 **같은 상태 코드, 같은 문구**로 답한다. 이 프로젝트는 탈퇴 회원, 비밀번호가 없는 소셜 가입 회원도 같은 `401 LOGIN_FAILED`다.

### 3.3 타이밍 공격(timing attack)

문구를 통일해도 **응답 시간**이 다르면 알아낼 수 있다.

```java
// 나쁜 예
Member m = repo.findByEmail(email);
if (m == null) throw LOGIN_FAILED;          // 1ms 만에 실패
if (!encoder.matches(pw, m.hash)) throw ... // bcrypt 비교에 약 100ms
```

bcrypt는 일부러 느린 함수라([09](./09-password-hashing.md)) 한 번 비교에 수십~수백 ms가 걸린다. 없는 이메일은 1ms, 있는 이메일은 100ms면 시간만 재도 회원 여부가 보인다. 해결은 **없는 이메일이어도 가짜 해시와 bcrypt 비교를 한 번 하는 것**이다. 그러면 두 경우 모두 비슷한 시간이 걸린다.

### 3.4 확인 후 저장의 경쟁 조건과 UNIQUE

```
요청 A: existsByNickname("지원") → false ┐
요청 B: existsByNickname("지원") → false ┘ 거의 동시
요청 A: INSERT ... nickname='지원'  → 성공
요청 B: INSERT ... nickname='지원'  → ?
```

애플리케이션의 "확인"만으로는 동시 요청을 막을 수 없다([17](./17-idempotency-redis.md) 3.6과 같은 구조). 그래서 DB에 `UNIQUE(nickname)` 제약이 있다(ERD `uk_member_nickname`). B의 INSERT는 DB가 거절한다. 애플리케이션은 그 오류를 잡아 사용자에게 맞는 409로 바꾸면 된다.

- 앞의 `exists` 확인은 **친절한 오류**를 주려는 것(대부분의 경우 여기서 걸림)
- UNIQUE 제약은 **정확성**을 지키는 마지막 방어선(드문 동시 요청)

### 3.5 열린 리다이렉트(open redirect)

로그인이 필요한 화면에서 넘어오면 로그인 주소에 원래 주소가 붙는다.

```
https://blog.com/login?redirect=https://jiwon.blog.com/manage
```

로그인 뒤 `redirect`로 그냥 보내면, 공격자가 이런 링크를 뿌릴 수 있다.

```
https://blog.com/login?redirect=https://blog-com-login.evil.com/
```

사용자는 진짜 `blog.com`에서 로그인했으니 안심한다. 그런데 로그인 직후 가짜 사이트로 넘어가 "비밀번호가 틀렸습니다. 다시 입력해 주세요"를 보고 비밀번호를 또 입력한다. 우리 도메인의 신뢰를 공격자가 빌려 쓰는 것이다. 막는 법은 **돌아갈 주소를 우리 서비스 주소로 제한**하는 것이다(기능 명세 계정과 소셜 연동 "우리 서비스 주소만 허용").

## 4. 동작 원리

### 4.1 가입 한 바퀴

```
[화면 SignupPage]
 ① 코드 받기    POST /api/auth/email-verifications           ([20] 참고)
 ② 확인         POST /api/auth/email-verifications/verify    → verified=true면 가입 버튼 켜짐
 ③ 닉네임 칸을 떠날 때  GET /api/auth/nickname-availability?nickname=
 ④ 가입하기     POST /api/auth/signup {email, code, password, nickname}
      │
      ▼ [서버]
   CsrfHeaderFilter (X-Requested-With 확인) → @Valid로 형식 검사(400)
   AuthController.signup
     └ AuthService.signup  ─────────── @Transactional 시작
         ├ PasswordRule.check          8자+영문+숫자, 72바이트 이하 → 아니면 400
         ├ existsByEmail               → 409 EMAIL_TAKEN
         ├ existsByNickname            → 409 NICKNAME_TAKEN
         ├ EmailVerificationService.consume  → 400 INVALID/EXPIRED, 맞으면 verified_at 기록
         └ saveAndFlush(회원)          UNIQUE 위반이면 → 409
                                     ─────────── 커밋 (실패면 전부 롤백)
     ├ AuthCookieManager.login(…, rememberMe=false)  → Set-Cookie 두 개
     └ 201 Me
 ⑤ 화면: /blogs/new(블로그 만들기)로 이동
```

순서의 이유:
- **비밀번호 규칙을 먼저**: DB를 보지 않고 판단할 수 있는 것은 먼저 한다.
- **중복 확인을 코드 사용보다 먼저**: 코드를 쓴 뒤 중복으로 실패해도 트랜잭션이 되돌려 주긴 하지만, 사용자에게 "닉네임이 중복"을 먼저 알려 주는 것이 자연스럽다.
- **코드 사용과 회원 저장이 한 트랜잭션**: 회원 저장이 실패하면 `verified_at`도 되돌아가 같은 코드로 다시 가입할 수 있다(테스트 `duplicateEmailOrNicknameIs409`).

### 4.2 로그인 판단 순서

```
POST /api/auth/login {email, password, rememberMe?}
  ├ 이메일로 회원 찾기
  ├ bcrypt 비교 (회원이 없거나 비밀번호 해시가 없으면 가짜 해시와 비교)
  ├ 회원 없음 / 해시 없음(소셜) / 비밀번호 틀림 / 탈퇴  → 401 LOGIN_FAILED (모두 같은 문구)
  ├ 정지 중                                              → 403 MEMBER_SUSPENDED {reason, reasonMessage, suspendedUntil}
  └ 쿠키 발급 + 200 Me
```

정지 확인이 **비밀번호 확인 뒤**인 이유: 순서를 바꾸면 비밀번호를 몰라도 "이 이메일은 정지된 회원"이라는 정보(가입 여부 + 제재 사유)를 얻는다. 비밀번호를 맞힌 사람, 즉 본인에게만 사유를 알려 준다.

### 4.3 로그아웃이 모든 블로그 주소에 통하는 원리

로그인 쿠키는 `Domain=.blog.test`로 발급된다([10](./10-http-cookies.md)). 브라우저는 `blog.test`, `alpha.blog.test`, `beta.blog.test` 어디에 요청하든 **같은 쿠키 하나**를 보낸다. 그래서:

1. 어느 주소에서든 `POST /api/auth/logout`을 부르면
2. 서버가 Redis에서 Refresh 토큰을 지우고, Access 토큰은 만료 때까지 차단 목록에 넣는다(토큰 자체를 무효로)
3. 같은 `Domain=.blog.test`로 `Max-Age=0` 쿠키를 보내 브라우저의 쿠키를 지운다

쿠키가 하나뿐이니 한 번 지우면 모든 주소에서 사라진다. 2번이 있는 이유: 누군가 쿠키 값을 복사해 뒀다가(또는 쿠키 삭제를 무시하는 클라이언트로) 다시 보내도, 서버에서 이미 무효라 통하지 않는다(테스트 `oldCookiesNoLongerWorkAfterLogout`).

### 4.4 프론트는 로그인 상태를 어떻게 아나

로그인 쿠키는 **HttpOnly**라 자바스크립트가 `document.cookie`로 읽을 수 없다(XSS로 토큰을 훔치지 못하게, [10](./10-http-cookies.md)). 그래서 프론트는 쿠키를 직접 보는 대신 서버에 묻는다.

```
GET /api/me  → 200 Me(닉네임, 대표 블로그…)  = 회원
             → 401                            = 비회원
```

머리글의 "로그인/회원가입" 대 "내 블로그/로그아웃", 관리 화면의 접근 안내 모두 이 응답으로 정한다. 이 화면 판단은 **안내용**이다. 진짜 권한 검사는 각 API에서 서버가 다시 한다(헌법 원칙 IV).

## 5. 이 프로젝트에서는

### 5.1 비밀번호 규칙: PasswordRule

`src/main/java/com/nhnacademy/blog/auth/domain/PasswordRule.java`

```java
public static final int MIN_LENGTH = 8;
public static final int MAX_BYTES = 72;

private static final Pattern LETTER = Pattern.compile("[A-Za-z]");
private static final Pattern DIGIT = Pattern.compile("\\d");

/** 규칙에 맞지 않으면 400 VALIDATION_FAILED(field)를 던진다. */
public static void check(String field, String password) {
    if (password == null || password.length() < MIN_LENGTH
            || !LETTER.matcher(password).find() || !DIGIT.matcher(password).find()) {
        throw BusinessException.invalidField(field, "비밀번호는 8자 이상, 영문과 숫자를 함께 써 주세요.");
    }
    if (password.getBytes(StandardCharsets.UTF_8).length > MAX_BYTES) {
        throw BusinessException.invalidField(field, "비밀번호가 너무 깁니다.");
    }
}
```

- `Pattern`을 `static final`로 한 번만 컴파일한다. 정규식 컴파일은 비용이 있어서 호출마다 만들지 않는다.
- `matcher(...).find()`: 문자열 **어딘가에** 영문이 하나라도 있나. `matches()`는 문자열 **전체**가 패턴과 같아야 해서 여기에 맞지 않다.
- **72바이트**: bcrypt는 입력의 앞 72바이트만 쓴다. Spring Security의 `BCryptPasswordEncoder`는 72바이트를 넘는 비밀번호를 `encode`하면 예외를 던지므로, 검사하지 않으면 500이 난다(스텝 3 학습 자료에서 찾은 문제, [09](./09-password-hashing.md)). 글자 수가 아니라 **UTF-8 바이트 수**로 센다. 영문은 1글자 1바이트, 한글은 3바이트라 한글이 섞이면 24~25자에서 넘는다.
- 규칙을 DTO의 `@Pattern`이 아니라 클래스 하나에 둔 이유: 나중에 비밀번호 변경(AUTH-05), 재설정(OWN-02)도 같은 규칙을 쓴다. 바이트 검사는 애노테이션 하나로 표현하기 어렵다.
- 위치가 `auth/domain`인 이유: 화면·DB와 상관없는 업무 규칙이라서다.

### 5.2 가입: AuthService.signup

`src/main/java/com/nhnacademy/blog/auth/application/AuthService.java`

```java
@Transactional
public Member signup(String rawEmail, String code, String password, String rawNickname) {
    String email = Emails.normalize(rawEmail);
    String nickname = rawNickname.trim();
    PasswordRule.check("password", password);
    if (memberRepository.existsByEmail(email)) {
        throw new BusinessException(ErrorCode.EMAIL_TAKEN);
    }
    if (memberRepository.existsByNickname(nickname)) {
        throw new BusinessException(ErrorCode.NICKNAME_TAKEN);
    }
    emailVerificationService.consume(email, code);
    try {
        return memberRepository.saveAndFlush(Member.ofEmail(email, passwordEncoder.encode(password), nickname));
    } catch (DataIntegrityViolationException e) {
        // 중복 확인과 저장 사이에 같은 값으로 먼저 가입한 사람이 있다
        throw new BusinessException(isNicknameConflict(e) ? ErrorCode.NICKNAME_TAKEN : ErrorCode.EMAIL_TAKEN);
    }
}

private boolean isNicknameConflict(DataIntegrityViolationException e) {
    String message = e.getMostSpecificCause().getMessage();
    return message != null && message.contains("uk_member_nickname");
}
```

줄별로:
- `Emails.normalize`: 소문자로 맞춘다([20](./20-email-verification.md) 5.2).
- `rawNickname.trim()`: `" 지원 "`과 `"지원"`이 다른 닉네임이 되지 않게 앞뒤 공백을 지운다. DTO의 `@NotBlank`가 공백뿐인 닉네임은 미리 막았다.
- `existsBy...`: Spring Data가 `SELECT ... LIMIT 1` 형태로 만든다. 친절한 오류를 위한 1차 확인이다.
- `consume`: 같은 트랜잭션에 참여한다([23](./23-transactions-locking.md)).
- `Member.ofEmail(...)`: 가입은 항상 `role=USER`, `status=ACTIVE`다(엔티티 생성자에서 정함). 요청으로 역할을 받지 않으니 누가 `"role":"ADMIN"`을 보내도 소용없다.
- `passwordEncoder.encode(password)`: bcrypt 해시. 같은 비밀번호도 매번 다른 salt라 결과가 다르다([09](./09-password-hashing.md)).
- **`saveAndFlush`인 이유**: `save`만 하면 INSERT는 트랜잭션 커밋 때 나간다. 그러면 UNIQUE 위반 예외가 이 메서드를 **빠져나간 뒤**(커밋 시점) 터져서 `try-catch`로 잡을 수 없다. `flush`로 INSERT를 지금 보내야 여기서 잡힌다.
- `DataIntegrityViolationException`: Spring이 DB 제약 위반을 감싸는 예외다. `getMostSpecificCause()`로 가장 안쪽 원인(MySQL 드라이버의 SQL 예외)을 꺼내면 메시지에 `Duplicate entry '지원' for key 'member.uk_member_nickname'`처럼 제약 이름이 들어 있다. 제약 이름으로 어느 칸이 겹쳤는지 구분한다. 그래서 ERD에서 제약 이름을 정해 두는 것이 중요하다.
- 예외를 잡고 `BusinessException`(RuntimeException)을 다시 던지면 트랜잭션은 롤백된다. `verified_at` 기록도 함께 사라진다.

### 5.3 로그인: AuthService.login

```java
/** 없는 이메일로 로그인할 때도 비밀번호를 비교해, 응답 시간으로 가입 여부를 알 수 없게 한다. */
private final String dummyPasswordHash;
...
this.dummyPasswordHash = passwordEncoder.encode("dummy-password-for-timing-1");
```

```java
@Transactional(readOnly = true)
public Member login(String rawEmail, String password) {
    Optional<Member> found = memberRepository.findByEmail(Emails.normalize(rawEmail));
    String hash = found.map(Member::getPasswordHash).orElse(null);
    boolean matches = passwordEncoder.matches(password, hash == null ? dummyPasswordHash : hash);
    if (hash == null || !matches || found.get().isWithdrawn()) {
        throw new BusinessException(ErrorCode.LOGIN_FAILED);
    }
    Member member = found.get();
    if (member.isSuspendedAt(LocalDateTime.now(clock))) {
        throw new BusinessException(ErrorCode.MEMBER_SUSPENDED, suspensionDetails.of(member));
    }
    return member;
}
```

- 가짜 해시는 서비스가 만들어질 때 **한 번** 만든다. 요청마다 `encode`하면 로그인 실패마다 bcrypt를 두 번 돌리게 된다.
- `hash == null`인 경우: 회원이 없거나, 소셜 가입 회원(비밀번호 없음)이다. 이때도 가짜 해시와 비교해 시간을 맞춘다. 결과는 버리고 `LOGIN_FAILED`.
- `if` 조건의 순서: `hash == null`이 먼저라 `found.get()`이 빈 Optional에서 불리는 일이 없다(`||`는 앞이 참이면 뒤를 보지 않는다).
- 탈퇴 회원: 탈퇴 처리 때 `email`을 비우므로(data-model 탈퇴 처리) 보통은 `findByEmail`에서 안 나온다. 그래도 상태를 한 번 더 본다.
- 정지는 비밀번호가 맞은 뒤에만 본다(4.2). 정지 종료 시각이 지났으면 `isSuspendedAt`이 false라 그대로 로그인된다.
- 로그인 요청 DTO는 이메일 형식(`@Email`)을 보지 않는다. 형식이 틀린 이메일에 400을 주면 "형식이 틀림"과 "없는 회원"이 다른 응답이 되기 때문에, 그냥 찾아서 없으면 401로 같게 답한다.

### 5.4 정지 사유: SuspensionDetails (필터와 공유)

`src/main/java/com/nhnacademy/blog/global/auth/SuspensionDetails.java`

```java
public SuspensionDetail of(Member member) {
    SanctionReason reason = moderationLogRepository
            .findFirstByTargetTypeAndTargetIdAndActionOrderByCreatedAtDescIdDesc(
                    ModerationTargetType.MEMBER, member.getId(), ModerationAction.SUSPEND)
            .map(ModerationLog::getReason)
            .orElse(null);
    OffsetDateTime until = member.getSuspendedUntil() == null
            ? null
            : member.getSuspendedUntil().atZone(clock.getZone()).toOffsetDateTime();
    return new SuspensionDetail(reason == null ? null : reason.name(),
            reason == null ? null : reason.getMessage(), until);
}
```

- 정지 사유는 회원 행이 아니라 `moderation_log`의 **최신 SUSPEND 행**에 있다(data-model 공통 규칙). 
- `suspendedUntil`이 null이면 영구 정지다. 화면은 "영구 정지"로 보여 준다.
- 스텝 3에서는 이 코드가 `JwtAuthenticationFilter` 안의 private 메서드였다(이미 로그인한 정지 회원을 막을 때 씀). 로그인 API도 같은 응답을 줘야 해서 빈으로 꺼내 둘이 함께 쓴다. 같은 규칙을 두 곳에 복사하면 한쪽만 고치는 실수가 생긴다.

### 5.5 컨트롤러: 쿠키 발급과 로그아웃

`src/main/java/com/nhnacademy/blog/auth/presentation/AuthController.java`

```java
/** 가입하면 바로 로그인된다(로그인 유지는 고르지 않은 상태). */
@PostMapping("/api/auth/signup")
@ResponseStatus(HttpStatus.CREATED)
public MeResponse signup(@Valid @RequestBody SignupRequest request, HttpServletResponse response) {
    Member member = authService.signup(request.email(), request.code(), request.password(), request.nickname());
    cookieManager.login(response, member, false);
    return MeResponse.from(meService.me(member.getId()));
}

@PostMapping("/api/auth/login")
public MeResponse login(@Valid @RequestBody LoginRequest request, HttpServletResponse response) {
    Member member = authService.login(request.email(), request.password());
    cookieManager.login(response, member, request.keepLoggedIn());
    return MeResponse.from(meService.me(member.getId()));
}

@PostMapping("/api/auth/logout")
@PreAuthorize("isAuthenticated()")
@ResponseStatus(HttpStatus.NO_CONTENT)
public void logout(HttpServletRequest request, HttpServletResponse response) {
    cookieManager.logout(request, response);
}
```

- 쿠키 발급은 서비스가 아니라 **컨트롤러**에서 한다. 쿠키는 HTTP의 일이라 표현 계층(presentation)의 몫이고, 서비스는 "이 회원이 맞다"까지만 책임진다([24](./24-layered-architecture-dto.md)).
- `cookieManager.login(response, member, rememberMe)`: Refresh 토큰을 Redis에 저장하고 Access·Refresh 쿠키 두 개를 붙인다(스텝 3, [11](./11-jwt.md)). `rememberMe`면 Refresh 쿠키에 14일 `Max-Age`, 아니면 브라우저를 닫으면 사라지는 쿠키 + 무활동 30분.
- 가입·로그인 모두 응답 본문으로 `Me`를 준다. 프론트가 곧바로 닉네임·대표 블로그를 알 수 있다.
- 로그아웃은 회원만(`@PreAuthorize("isAuthenticated()")`) — API 명세가 "회원"으로 정했다. 비회원이 부르면 401이다. 프론트의 로그아웃 버튼은 `allowAnonymous: true`로 불러, 이미 쿠키가 만료된 상태여도 로그인 화면으로 튕기지 않고 홈으로 간다.

**rememberMe와 Jackson 3**

`src/main/java/com/nhnacademy/blog/auth/presentation/dto/LoginRequest.java`

```java
public record LoginRequest(
        @NotBlank(message = "이메일을 입력해 주세요.")
        String email,

        @NotBlank(message = "비밀번호를 입력해 주세요.")
        String password,

        Boolean rememberMe) {

    /** 생략하면 로그인 유지를 고르지 않은 것이다. */
    public boolean keepLoggedIn() {
        return Boolean.TRUE.equals(rememberMe);
    }

}
```

처음에는 `boolean rememberMe`(기본형)였다. 서버를 띄워 curl로 `{"email":..,"password":..}`만 보내 보니 **400**이 왔다. Jackson 3은 기본형 칸이 본문에 없으면 오류로 보는 것이 기본값이기 때문이다(테스트는 항상 `rememberMe`를 넣어 보내 이 경우를 못 잡았다). 감싼 타입 `Boolean`으로 바꿔 없으면 null, null은 "유지 안 함"으로 처리했다. 자세한 원리는 [22](./22-bean-validation.md).

**AuthCookieManager.logout** (스텝 3 코드, `global/auth/AuthCookieManager.java`)

```java
public void logout(HttpServletRequest request, HttpServletResponse response) {
    readCookie(request, ACCESS_COOKIE)
            .flatMap(token -> tokenProvider.parse(token, TokenType.ACCESS))
            .ifPresent(claims -> tokenStore.blockAccess(claims.id(), claims.expiresAt()));
    readCookie(request, REFRESH_COOKIE)
            .flatMap(token -> tokenProvider.parse(token, TokenType.REFRESH))
            .ifPresent(claims -> tokenStore.deleteRefresh(claims.id()));
    clear(response);
}
```

Access 토큰은 차단 목록에(만료 때까지), Refresh 토큰은 살아 있는 목록에서 삭제, 그리고 `clear`가 `Domain=.blog.test; Max-Age=0` 쿠키 두 개를 보낸다(4.3).

### 5.6 내 정보: GET /api/me

`src/main/java/com/nhnacademy/blog/member/presentation/MeController.java`

```java
@GetMapping("/api/me")
@PreAuthorize("isAuthenticated()")
public MeResponse me(@AuthenticationPrincipal LoginMember member) {
    return MeResponse.from(meService.me(member.id()));
}
```

`MeResponse`(`member/presentation/dto/MeResponse.java`)는 `hasPassword`(비밀번호 해시가 있으면 이메일 가입 회원), `primaryBlog`(대표 블로그, 없으면 null)를 준다. `primaryBlog`가 null이면 머리글이 "내 블로그" 대신 "블로그 만들기"를 보여 준다(AUTH-04). 프로필 이미지·소셜 연동·알림 수는 기능이 생기면 채우고, 지금은 `null`, `[]`, `0`이다.

프론트의 훅 `frontend/src/app/useMe.ts`:

```ts
api<Me>('/api/me', { allowAnonymous: true })
  .then((me) => active && setState({ status: 'member', me }))
  .catch(() => active && setState({ status: 'anonymous' }))
```

`allowAnonymous: true`라 401이어도 로그인 화면으로 보내지 않고 "비회원"으로 그린다([25](./25-react-forms-data.md)).

### 5.7 프론트: 가입 화면의 상태와 열린 리다이렉트 방어

**가입 화면** `frontend/src/pages/auth/SignupPage.tsx`

```tsx
function changeEmail(value: string) {
  // 이메일을 바꾸면 인증을 다시 받아야 한다
  setEmail(value)
  setCodeSent(false)
  setVerified(false)
}
...
<button className="btn primary" type="submit" disabled={!verified || submitting}>가입하기</button>
```

- 인증을 받은 뒤 이메일 칸을 바꾸면 `verified`를 되돌린다. 화면에서 "인증된 이메일"과 "보낼 이메일"이 달라지지 않게 한다(서버도 가입 때 다시 확인하므로 이것은 편의다).
- 가입 실패는 `signupErrors(error)`가 칸별 문장으로 나눈다. `EMAIL_TAKEN`은 이메일 칸 아래, `NICKNAME_TAKEN`은 닉네임 칸 아래, 코드 오류는 코드 칸 아래. 입력값은 지우지 않는다(spec US1 수용 시나리오 2 "입력은 그대로 남는다").

**돌아갈 주소 검사** `frontend/src/app/host.ts`

```ts
export function safeRedirect(target: string | null, platform: string = PLATFORM_DOMAIN): string | null {
  if (!target) {
    return null
  }
  let url: URL
  try {
    url = new URL(target)
  } catch {
    return null
  }
  const host = url.hostname.toLowerCase()
  const ours = host === platform || host.endsWith(`.${platform}`)
  return (url.protocol === 'http:' || url.protocol === 'https:') && ours ? url.href : null
}
```

- `new URL(target)`: 문자열을 브라우저와 같은 규칙으로 해석한다. 직접 문자열을 자르면 `https://blog.test@evil.com/`(앞부분은 사용자 정보, 실제 호스트는 `evil.com`) 같은 속임수에 넘어간다. `URL`의 `hostname`은 진짜 호스트를 준다. 상대 주소(`/relative`)는 기준 주소가 없어 예외 → null.
- `host === platform || host.endsWith('.' + platform)`: `blog.test`이거나 `*.blog.test`. 점을 붙여 비교하는 이유: 그냥 `endsWith('blog.test')`면 `evilblog.test`가 통과한다.
- 프로토콜을 `http:`·`https:`로 제한: `javascript:alert(1)`로 이동시키면 우리 페이지에서 스크립트가 실행된다.

`frontend/src/pages/auth/LoginPage.tsx`에서 쓰는 곳:

```tsx
const redirect = safeRedirect(params.get('redirect'))
if (redirect) {
  // 블로그 주소는 다른 호스트라 페이지를 새로 연다. 쿠키가 .{플랫폼}이라 거기서도 로그인 상태다
  window.location.assign(redirect)
} else {
  navigate('/')
}
```

블로그 주소는 다른 호스트라 React Router의 `navigate`(같은 페이지 안 이동)로 갈 수 없어 `window.location.assign`으로 새로 연다.

### 5.8 테스트

| 테스트 파일 | 테스트 | 확인하는 것 |
| --- | --- | --- |
| `SignupIntegrationTest` | `signupCreatesMemberAndLogsIn` | 201 Me, bcrypt로 저장(원문과 다르고 `matches` 참), `verified_at` 기록, 응답 쿠키로 `/api/me` 200 |
| | `noMemberWithoutVerifiedCode` | 틀린 코드·받은 적 없는 이메일 → 400, 회원 없음 |
| | `codeCannotBeUsedTwice` | 같은 코드로 두 번째 가입 → 409(이미 가입됨) |
| | `duplicateEmailOrNicknameIs409` | 닉네임 중복 409, **같은 코드로 다시 가입하면 성공**(롤백 확인) |
| | `passwordNeedsEightCharsWithLettersAndDigits` | 7자, 숫자 없음, 영문 없음, 한글로 72바이트 초과 → 400 `password` |
| | `nicknameAvailability`, `meIs401ForAnonymous` | 닉네임 확인 API, 비회원 `/api/me` 401 |
| `LoginIntegrationTest` | `loginIssuesCookiesSharedByAllBlogAddresses` | 쿠키 2개 `Domain=.blog.test`, 유지 안 함이면 `Max-Age` 없음, 블로그 Host에서 `/api/me` 200 |
| | `rememberMeKeepsRefreshCookieFor14Days` | Refresh 쿠키 `Max-Age=1209600`(14일) |
| | `wrongPasswordAndUnknownEmailGetSameAnswer` | 틀린 비밀번호, 없는 이메일, 100자 비밀번호 → 모두 같은 401 문구 |
| | `withdrawnMemberIsTreatedAsUnknown` | 탈퇴 회원 → 401 |
| | `suspendedMemberGetsReasonOnlyWithRightPassword` | 정지 회원 + 틀린 비밀번호 → 401, 맞으면 403 + 사유·기한 |
| | `rememberMeCanBeOmitted` | `rememberMe` 없이 로그인 200(Jackson 3 버그 수정 확인) |
| `LogoutIntegrationTest` | `logoutClearsCookiesForAllBlogAddresses` | 블로그 Host에서 로그아웃해도 `Domain=.blog.test; Max-Age=0` |
| | `oldCookiesNoLongerWorkAfterLogout` | 지운 쿠키를 다시 보내도 401(Access·Refresh 모두 무효) |
| | `anonymousLogoutIs401` | 비회원 로그아웃 401 |

`TestMembers.createWithPassword`는 진짜 bcrypt 해시로 회원을 만든다(기존 `create()`는 해시 자리에 `"hash"` 문자열이라 로그인 API로는 못 들어간다).

## 6. 자주 하는 실수와 함정

1. **실패 이유별로 다른 문구**: "없는 이메일"과 "틀린 비밀번호"를 구분하면 회원 목록이 새어 나간다.
2. **없는 이메일은 바로 실패**: 응답 시간 차이로 회원 여부가 보인다. 가짜 해시와 비교한다.
3. **정지 안내를 비밀번호 확인 전에**: 비밀번호를 몰라도 제재 사실을 알게 된다.
4. **`save` 뒤 `try-catch`로 UNIQUE 위반 잡기**: INSERT가 커밋 때 나가므로 잡히지 않는다. `saveAndFlush`.
5. **중복 확인만 믿기**: 동시 요청은 확인을 둘 다 통과한다. DB UNIQUE가 최종 방어선이다.
6. **비밀번호 길이를 글자 수로만**: bcrypt 한계는 바이트다. 한글 비밀번호가 500 오류를 낸다.
7. **요청 DTO에 기본형 `boolean`**: Jackson 3에서 칸을 생략하면 400. 선택 칸은 `Boolean`.
8. **`redirect`를 검사 없이 이동**: 피싱 징검다리가 된다. `endsWith('blog.test')`처럼 점 없이 비교해도 뚫린다.
9. **쿠키만 지우고 토큰은 그대로**: 복사해 둔 토큰은 만료 때까지 쓸 수 있다. 서버에서도 무효로 만든다.
10. **화면 판단을 권한 검사로 착각**: `useMe`로 버튼을 숨겨도 API는 서버가 다시 막아야 한다.

## 7. 직접 해 보기

**실습 1. 테스트 돌리기**

```bash
./mvnw test -Dtest='SignupIntegrationTest,LoginIntegrationTest,LogoutIntegrationTest'
cd frontend && npm test        # safeRedirect 테스트(host.test.ts)
```

**실습 2. curl로 한 바퀴** (서버를 띄운 뒤)

```bash
R='--resolve blog.test:8080:127.0.0.1 --resolve alpha.blog.test:8080:127.0.0.1'
H='-H X-Requested-With:XMLHttpRequest -H Content-Type:application/json'
# bash에서 실행한다(zsh는 변수를 나눠 읽지 않는다)
curl -s $R $H -X POST http://blog.test:8080/api/auth/email-verifications -d '{"email":"me2@example.com"}'
# 서버 로그에서 [개발용 메일]의 인증 코드를 확인
curl -s $R $H -c jar.txt -X POST http://blog.test:8080/api/auth/signup \
  -d '{"email":"me2@example.com","code":"코드","password":"password1","nickname":"나"}'
curl -s $R -b jar.txt http://alpha.blog.test:8080/api/me          # 다른 호스트인데 로그인 상태(쿠키 Domain)
curl -s $R $H -b jar.txt -c jar.txt -X POST http://alpha.blog.test:8080/api/auth/logout -w '%{http_code}\n'
curl -s $R -b jar.txt http://blog.test:8080/api/me                # 401
```

`jar.txt`를 열어 보면 쿠키 도메인이 `.blog.test`로 적혀 있다.

**실습 3. 로그인 실패 문구 비교**

```bash
curl -s $R $H -X POST http://blog.test:8080/api/auth/login -d '{"email":"me2@example.com","password":"wrong1234"}'
curl -s $R $H -X POST http://blog.test:8080/api/auth/login -d '{"email":"nobody@example.com","password":"wrong1234"}'
```

두 응답이 글자 하나까지 같은지 본다. `-w '%{time_total}\n'`을 붙여 시간도 비교해 본다. 그다음 `AuthService.login`에서 회원이 없을 때 바로 `throw`하도록 바꾸고 다시 재 보면, 없는 이메일 쪽이 확연히 빨라진다. 되돌린다.

**실습 4. Redis 토큰 보기**

```bash
docker exec blog-redis redis-cli --scan --pattern 'auth:*'
```

로그인하면 `auth:refresh:...`가 생기고, 로그아웃하면 그 키가 사라지고 `auth:blocked-access:...`가 생긴다.

**실습 5. 열린 리다이렉트 시험**

`/etc/hosts`에 `blog.test`를 넣고 브라우저에서 `http://blog.test:5173/login?redirect=https://evil.com/`으로 로그인한다. 홈으로 가는지 본다. `?redirect=http://alpha.blog.test:5173/manage`면 그 주소로 간다.

## 8. 확인 문제

1. 로그인 실패 문구를 "이메일 또는 비밀번호가 맞지 않습니다" 하나로 통일하는 이유는?
<details><summary>답</summary>"없는 이메일"과 "틀린 비밀번호"를 구분해 답하면 공격자가 비밀번호 없이도 어떤 이메일이 회원인지 알아낼 수 있다(계정 열거).</details>

2. 없는 이메일로 로그인할 때도 bcrypt 비교를 하는 이유는?
<details><summary>답</summary>bcrypt는 느린 함수라, 없는 이메일만 바로 실패하면 응답 시간 차이로 회원 여부가 드러난다(타이밍 공격). 가짜 해시와 비교해 두 경우의 시간을 비슷하게 맞춘다.</details>

3. 정지 회원 안내를 비밀번호 확인 뒤에 하는 이유는?
<details><summary>답</summary>먼저 하면 비밀번호를 모르는 사람도 그 이메일이 회원이고 정지됐다는 사실(사유까지)을 알 수 있다. 비밀번호를 맞힌 본인에게만 알려 준다.</details>

4. 닉네임 중복을 `existsByNickname`으로 확인했는데도 UNIQUE 제약이 필요한 이유는?
<details><summary>답</summary>동시에 온 두 가입 요청이 둘 다 "없음"을 확인하고 둘 다 저장하려 할 수 있다(경쟁 조건). DB UNIQUE 제약이 두 번째 INSERT를 거절하는 최종 방어선이고, 앞의 확인은 친절한 오류를 위한 것이다.</details>

5. 가입에서 `save` 대신 `saveAndFlush`를 쓴 이유는?
<details><summary>답</summary><code>save</code>만 하면 INSERT가 커밋 때 나가서 UNIQUE 위반 예외가 메서드 밖에서 터진다. <code>flush</code>로 지금 INSERT를 보내야 <code>try-catch</code>로 잡아 409로 바꿀 수 있다.</details>

6. 닉네임이 중복돼 가입이 실패했을 때, 같은 인증 코드로 다시 가입할 수 있는 이유는?
<details><summary>답</summary>코드 사용(<code>verified_at</code> 기록)과 회원 저장이 한 트랜잭션이라, 가입이 실패해 롤백되면 <code>verified_at</code>도 되돌아가기 때문이다.</details>

7. 비밀번호 최대 길이를 글자 수가 아니라 UTF-8 바이트 수로 검사하는 이유는?
<details><summary>답</summary>bcrypt는 앞 72바이트만 쓰고, Spring Security는 넘으면 예외를 던진다. 한글은 한 글자가 3바이트라 글자 수로 세면 한도를 넘는 비밀번호를 통과시켜 500이 난다.</details>

8. `alpha.blog.test`에서 로그아웃했는데 `beta.blog.test`에서도 로그아웃되는 이유는?
<details><summary>답</summary>로그인 쿠키가 <code>Domain=.blog.test</code> 하나라 모든 블로그 주소가 같은 쿠키를 쓴다. 서버가 같은 도메인으로 <code>Max-Age=0</code> 쿠키를 보내 지우고, 토큰도 Redis에서 무효로 만든다.</details>

9. 프론트가 로그인 상태를 `document.cookie`가 아니라 `GET /api/me`로 확인하는 이유는?
<details><summary>답</summary>로그인 쿠키가 HttpOnly라 자바스크립트가 읽을 수 없다. 서버에 물어 200이면 회원, 401이면 비회원으로 그린다.</details>

10. `safeRedirect`에서 `host.endsWith('.blog.test')`처럼 점을 붙여 비교하는 이유와, `new URL()`로 해석하는 이유는?
<details><summary>답</summary>점 없이 비교하면 <code>evilblog.test</code>가 통과한다. 문자열을 직접 자르면 <code>https://blog.test@evil.com/</code> 같은 사용자 정보 속임수에 넘어가므로, 브라우저와 같은 규칙으로 진짜 호스트를 주는 <code>URL</code>을 쓴다.</details>

## 9. 더 읽을거리

- OWASP Cheat Sheet: Authentication(오류 메시지, 계정 열거), Unvalidated Redirects and Forwards
- OWASP Cheat Sheet: Password Storage(bcrypt, 72바이트)
- Spring Security 레퍼런스: `BCryptPasswordEncoder`, `@PreAuthorize`
- Spring Framework 레퍼런스: `DataIntegrityViolationException`과 예외 변환
- Spring Data JPA: `saveAndFlush`, 영속성 컨텍스트와 flush 시점
- MDN: `URL` 생성자, `Set-Cookie`의 `Domain`·`Max-Age`
- spec.md AUTH-01·02·03, ADMIN-02, rest-api.md AUTH·ME 표
