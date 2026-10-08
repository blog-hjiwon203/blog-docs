# 22. 입력 검증과 JSON 바인딩

> 관련 스텝: [스텝 4](../step-04.md) (T017, T018, T019, T022, T023) · 관련 개념: [07-spring-mvc-exception-handling](./07-spring-mvc-exception-handling.md), [09-password-hashing](./09-password-hashing.md), [15-subdomain-host-routing](./15-subdomain-host-routing.md), [16-authorization-visibility](./16-authorization-visibility.md), [23-transactions-locking](./23-transactions-locking.md)

## 1. 이 문서로 배우는 것

- 요청 본문(JSON 글자)이 컨트롤러의 자바 객체(record)가 되는 과정: `HttpMessageConverter`와 Jackson 3
- Jakarta Bean Validation의 기본 애노테이션(`@NotBlank`, `@NotNull`, `@Size`, `@Email`, `@Pattern`)과 `message`
- `@Valid @RequestBody`가 실패했을 때 어떤 예외가 나고, 그것이 어떻게 `fieldErrors`가 든 400 응답이 되는지
- `@RequestParam`에 붙인 제약(메서드 검증)과 `HandlerMethodValidationException`
- 애노테이션으로 하는 검증과 서비스에서 하는 검증(`PasswordRule`, `BlogAddressRule`)을 나누는 기준
- 상태 코드 순서(404 → 401 → 403 → 400) 때문에 `@Valid`를 빼고 `RequestValidator`를 직접 부르는 경우
- Jackson 3에서 본문에 없는 기본형(`boolean`) 칸이 오류가 되는 함정과 이 프로젝트의 수정
- 본문에 있는 모르는 칸은 무시된다는 것, PATCH에서 "null은 그대로, 빈 문자열은 지우기" 설계

**먼저 알면 좋은 것**: Spring MVC 컨트롤러와 `@RestControllerAdvice`([07](./07-spring-mvc-exception-handling.md)), Java record, JSON 문법.

## 2. 왜 필요한가

서버는 화면이 보낸 값만 오리라고 믿으면 안 된다. 화면은 이메일 칸에 `type="email"`, 닉네임 칸에 `maxLength={20}`을 걸어 두었지만, 이것은 **사용자 편의**일 뿐이다. 누구나 curl이나 개발자 도구로 화면을 거치지 않고 요청을 보낼 수 있다.

```bash
curl -X POST blog.test:8080/api/auth/signup -H 'X-Requested-With: XMLHttpRequest' \
     -H 'Content-Type: application/json' \
     -d '{"email":"아무거나","code":"abc","password":"1","nickname":""}'
```

서버가 검사하지 않으면:

- 빈 닉네임, 21자 이상 닉네임이 DB까지 간다. DB 컬럼이 `VARCHAR(20)`이면 DB 오류가 나고, 그 오류는 우리 오류 처리기에서 **500**이 된다. 사용자는 "일시적인 오류"라는 엉뚱한 안내를 받는다.
- 기능 명세 AUTH-01은 "비밀번호는 8자 이상 영문+숫자", US1 수용 시나리오 2는 "**어느 항목이 왜 틀렸는지 알리고** 입력은 그대로 남는다"를 요구한다. 서버가 칸 이름(`field`)과 이유(`reason`)를 돌려줘야 화면이 그 칸 아래에 빨간 글자를 띄울 수 있다.

그래서 이 프로젝트는 모든 입력을 서버에서 검사하고, 틀리면 COM-02 모양의 400을 준다.

```json
{
  "code": "VALIDATION_FAILED",
  "message": "입력값을 확인해 주세요.",
  "fieldErrors": [{ "field": "email", "reason": "이메일 형식이 아닙니다." }]
}
```

## 3. 기본 개념

### 3.1 바인딩: JSON 글자가 자바 객체가 되기까지

HTTP 요청 본문은 그냥 **바이트(글자)**다. 컨트롤러가 `SignupRequest` 같은 객체로 받으려면 누군가 글자를 읽어 객체를 만들어야 한다. 이 일을 **바인딩(binding)** 또는 역직렬화(deserialization)라 한다.

- Spring MVC에서 이 일을 하는 부품이 `HttpMessageConverter`다. 요청의 `Content-Type: application/json`을 보고 JSON용 변환기를 고른다.
- JSON 변환기는 안에서 **Jackson** 라이브러리를 쓴다. Spring Boot 4는 **Jackson 3**을 쓴다. 패키지 이름이 2.x의 `com.fasterxml.jackson.databind`에서 `tools.jackson.databind`로 바뀌었다(이 프로젝트의 `IdempotencyInterceptor`가 `tools.jackson.databind.json.JsonMapper`를 쓴다). 단, `@JsonInclude` 같은 애노테이션은 여전히 `com.fasterxml.jackson.annotation` 패키지다(`ErrorResponse`).
- Jackson은 record를 만들 때 **정식 생성자(canonical constructor)**를 부른다. JSON의 칸 이름과 record 구성 요소 이름이 같으면 그 값을 넣고, JSON에 없는 칸은 `null`(참조형)로 넣는다.

```
{"email":"a@b.com","password":"pw"}   ──Jackson──▶   new LoginRequest("a@b.com", "pw", null)
                                                                              ↑ rememberMe가 없어서 null
```

바인딩 자체가 실패하는 경우도 있다. JSON 문법이 틀렸거나(`{"email":`), 숫자 칸에 글자를 넣었거나, 기본형 칸에 값이 없거나(3.5). 이때 Spring은 `HttpMessageNotReadableException`을 던진다.

### 3.2 Bean Validation (Jakarta Validation)

**Bean Validation**은 "필드에 애노테이션으로 규칙을 적어 두면 검증기(Validator)가 한꺼번에 검사해 주는" 자바 표준이다. 지금 이름은 Jakarta Validation이고(패키지 `jakarta.validation`), 구현체는 Hibernate Validator다. `spring-boot-starter-validation`이 둘을 가져온다.

| 애노테이션 | 통과하는 값 | `null`이면 |
| --- | --- | --- |
| `@NotNull` | `null`이 아닌 모든 값 | 실패 |
| `@NotBlank` | 공백이 아닌 글자가 하나라도 있는 문자열 | 실패 |
| `@NotEmpty` | 길이가 1 이상(공백만이어도 통과) | 실패 |
| `@Size(min, max)` | 길이가 범위 안 | **통과** |
| `@Email` | 이메일 형식 | **통과** |
| `@Pattern(regexp)` | 정규식에 **전체가** 맞음 | **통과** |

마지막 세 개가 `null`을 통과시키는 게 핵심이다. Bean Validation은 "값이 있어야 한다"(`@NotNull`, `@NotBlank`)와 "값이 있다면 이런 모양이어야 한다"(`@Size`, `@Email`, `@Pattern`)를 따로 둔다. 그래서 필수 칸에는 `@NotBlank`를 함께 붙이고, 선택 칸(PATCH의 각 칸, 블로그 소개)에는 모양 규칙만 붙인다.

`message`는 실패했을 때의 문장이다. 이 프로젝트는 이 문장을 그대로 `fieldErrors[].reason`에 넣어 화면에 띄우므로, 사용자가 읽을 수 있는 한국어 문장으로 쓴다.

```java
@NotBlank(message = "닉네임을 입력해 주세요.")
@Size(max = 20, message = "닉네임은 20자까지입니다.")
String nickname
```

### 3.3 `@Valid`: 검증을 언제 하나

애노테이션은 적어 두기만 해서는 아무 일도 안 한다. 누군가 `validator.validate(객체)`를 불러야 한다. Spring MVC에서는 컨트롤러 인자에 `@Valid`를 붙이면 **인자를 만든 직후, 메서드를 부르기 전에** 검증한다.

```java
public MeResponse login(@Valid @RequestBody LoginRequest request, ...)
```

검증에 실패하면 메서드는 실행되지 않고 `MethodArgumentNotValidException`이 난다. 이 예외는 `BindException`의 하위 클래스라서, `@ExceptionHandler(BindException.class)` 하나로 둘 다 받을 수 있다.

### 3.4 메서드 검증: `@RequestParam`에 붙인 제약

`@RequestParam String nickname`처럼 **객체가 아닌 단일 값**에도 제약을 붙일 수 있다. Spring Framework 6.1부터 MVC가 컨트롤러 메서드 인자의 제약 애노테이션을 보고 **내장 메서드 검증**을 한다. 실패하면 `HandlerMethodValidationException`이 난다. 예전처럼 컨트롤러 클래스에 `@Validated`를 붙이지 않아도 된다.

### 3.5 기본형 칸과 "값 없음"

자바 `boolean`, `int` 같은 **기본형(primitive)**은 `null`이 될 수 없다. 그래서 JSON에 그 칸이 없을 때 무엇을 넣을지가 문제다.

- `Boolean`(참조형)이면 `null`을 넣으면 된다.
- `boolean`(기본형)이면 `false`를 넣을지, "값이 없다"고 오류를 낼지 Jackson 설정(`DeserializationFeature.FAIL_ON_NULL_FOR_PRIMITIVES`)에 따라 다르다.

이 프로젝트(Spring Boot 4.1, Jackson 3 기본 설정)에서는 **`boolean` 칸이 본문에 없으면 바인딩이 실패해 400이 났다**. 실제로 겪은 일은 5.6에 적었다. 그래서 생략할 수 있는 참/거짓 칸은 `Boolean`으로 받는다.

### 3.6 검증을 어디서 하나: 애노테이션 vs 서비스

| 검증 | 어디서 | 예 |
| --- | --- | --- |
| 모양: 필수, 길이, 형식 | 요청 DTO의 애노테이션 | 이메일 형식, 닉네임 20자, 인증 코드 숫자 6자리 |
| 업무 규칙: 여러 조건이 얽히거나 다른 곳에서도 쓰는 규칙 | 도메인의 규칙 클래스, 서비스 | 비밀번호 "8자+영문+숫자+72바이트 이하", 블로그 주소 "형식·예약어" |
| DB를 봐야 아는 것 | 서비스 | 이메일·닉네임 중복(409), 주소 중복(409), 블로그 5개 한도(409) |

애노테이션은 짧고 한눈에 보이지만, **한 칸만** 보고 **오류 코드는 항상 `VALIDATION_FAILED`**다. 오류 코드가 달라야 하거나(주소 규칙은 `BLOG_ADDRESS_INVALID`), 같은 규칙을 가입·비밀번호 변경처럼 여러 곳에서 쓰거나, 규칙이 바이트 수처럼 애노테이션으로 표현하기 어색하면 코드로 쓴다.

## 4. 동작 원리

`POST /api/auth/signup`에 형식이 틀린 이메일이 왔을 때:

```
요청 본문 {"email":"not-an-email", ...}
   │
   ▼ DispatcherServlet → 컨트롤러 메서드를 찾음 → 인자 만들기 시작
① RequestResponseBodyMethodProcessor (@RequestBody 담당)
   ├ HttpMessageConverter(Jackson)로 JSON → SignupRequest
   │    └ 실패(문법 오류, 기본형 칸 없음 등) → HttpMessageNotReadableException
   └ @Valid가 있으니 Validator로 검증
        └ 실패 → MethodArgumentNotValidException (BindException의 하위)
   │
   ▼ (메서드는 실행되지 않음)
② GlobalExceptionHandler
   ├ handleBind(BindException)            → 400, fieldErrors = [{field, reason}, ...]
   ├ handleMethodValidation(...)          → 400, @RequestParam 제약 실패
   └ handleUnreadable(...)                → 400, fieldErrors 없음 (파서 메시지는 내부 정보라 숨김)
```

중요한 점: **인자 만들기(①)는 메서드 몸통보다 먼저 일어난다.** 그러니 메서드 안에 쓴 주인 검사(403)보다 `@Valid` 검증(400)이 항상 먼저다. 5.4에서 이것이 왜 문제가 되는지 본다.

## 5. 이 프로젝트에서는

### 5.1 요청 DTO: 애노테이션으로 모양 검사

`src/main/java/com/nhnacademy/blog/auth/presentation/dto/SignupRequest.java`

```java
/** 가입 요청. 비밀번호 규칙은 서비스의 PasswordRule이 본다. */
public record SignupRequest(
        @NotBlank(message = "이메일을 입력해 주세요.")
        @Email(message = "이메일 형식이 아닙니다.")
        @Size(max = 255, message = "이메일이 너무 깁니다.")
        String email,

        @NotBlank(message = "인증 코드를 입력해 주세요.")
        @Pattern(regexp = "\\d{6}", message = "인증 코드는 숫자 6자리입니다.")
        String code,

        @NotBlank(message = "비밀번호를 입력해 주세요.")
        String password,

        @NotBlank(message = "닉네임을 입력해 주세요.")
        @Size(max = 20, message = "닉네임은 20자까지입니다.")
        String nickname) {
}
```

- record 구성 요소에 붙인 애노테이션은 필드에도 전달되어 Validator가 읽는다.
- `email`: 비었는지(`@NotBlank`), 형식(`@Email`), 길이(`@Size(max = 255)`, DB 컬럼 `VARCHAR(255)`). 세 개가 각각 다른 문장을 낸다.
- `code`: `@Pattern("\\d{6}")`. 자바 문자열에서 `\`는 `\\`로 쓴다. `@Pattern`은 문자열 **전체**가 맞아야 통과라서 `^`, `$`가 없어도 "숫자 정확히 6개"다.
- `password`: 비었는지만 본다. 나머지 규칙은 서비스의 `PasswordRule`(5.3).
- `nickname`: 20자. DB가 `VARCHAR(20)`이라 여기서 막지 않으면 DB 오류(500)가 된다.

컨트롤러는 `@Valid`만 붙인다(`auth/presentation/AuthController.java`).

```java
@PostMapping("/api/auth/signup")
@ResponseStatus(HttpStatus.CREATED)
public MeResponse signup(@Valid @RequestBody SignupRequest request, HttpServletResponse response) {
```

### 5.2 실패가 fieldErrors가 되는 곳

`src/main/java/com/nhnacademy/blog/global/error/GlobalExceptionHandler.java` (스텝 2)

```java
/** @Valid 본문, @ModelAttribute 검증 실패. MethodArgumentNotValidException도 여기로 온다. */
@ExceptionHandler(BindException.class)
public ResponseEntity<ErrorResponse> handleBind(BindException e) {
    List<FieldErrorDetail> fieldErrors = e.getBindingResult().getFieldErrors().stream()
            .map(error -> new FieldErrorDetail(error.getField(),
                    error.isBindingFailure() ? INVALID_FORMAT : error.getDefaultMessage()))
            .toList();
    return validation(fieldErrors);
}

/** @RequestParam, @PathVariable 등 메서드 인자 검증 실패. */
@ExceptionHandler(HandlerMethodValidationException.class)
public ResponseEntity<ErrorResponse> handleMethodValidation(HandlerMethodValidationException e) {
    List<FieldErrorDetail> fieldErrors = e.getParameterValidationResults().stream()
            .flatMap(result -> result.getResolvableErrors().stream()
                    .map(error -> new FieldErrorDetail(result.getMethodParameter().getParameterName(),
                            error.getDefaultMessage())))
            .toList();
    return validation(fieldErrors);
}
```

- `getBindingResult().getFieldErrors()`: 실패한 칸마다 하나씩. `getField()`는 칸 이름(`email`), `getDefaultMessage()`는 애노테이션의 `message`.
- `isBindingFailure()`: 검증 실패가 아니라 **값 변환 실패**(예: 숫자 칸에 글자)면 `true`다. 이때 기본 메시지는 영어 내부 문장이라 "형식이 올바르지 않습니다."로 바꾼다.
- 메서드 검증은 칸 이름 대신 **파라미터 이름**(`nickname`)을 `field`로 쓴다. 파라미터 이름을 읽으려면 컴파일 때 `-parameters` 옵션이 필요한데, Spring Boot의 Maven 부모 설정이 켜 준다.

`@RequestParam` 제약의 예(`AuthController`):

```java
@GetMapping("/api/auth/nickname-availability")
public NicknameAvailabilityResponse nicknameAvailability(
        @RequestParam @NotBlank(message = "닉네임을 입력해 주세요.")
        @Size(max = 20, message = "닉네임은 20자까지입니다.") String nickname) {
    return new NicknameAvailabilityResponse(authService.isNicknameAvailable(nickname));
}
```

테스트 `SignupIntegrationTest.nicknameAvailability`가 `"a".repeat(21)`에 400과 `fieldErrors[0].field == "nickname"`을 확인한다.

### 5.3 서비스에서 하는 검증

**비밀번호 규칙** `src/main/java/com/nhnacademy/blog/auth/domain/PasswordRule.java`

```java
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

- `LETTER.matcher(password).find()`: `find()`는 "어딘가에 하나라도 있나"다. `matches()`(전체가 맞나)와 다르다.
- 두 번째 조건은 **글자 수가 아니라 바이트 수**다. bcrypt는 72바이트까지만 쓰고, 넘으면 Spring Security의 인코더가 예외를 던져 500이 된다([09](./09-password-hashing.md)). 한글은 UTF-8에서 한 글자 3바이트라 25자부터 걸린다. 이런 규칙은 `@Size`(글자 수)로 표현할 수 없다.
- `field`를 인자로 받는 이유: 가입에서는 `password`, 나중에 비밀번호 변경(AUTH-05)에서는 `newPassword` 칸이다. 같은 규칙을 칸 이름만 바꿔 쓴다.
- `BusinessException.invalidField`는 `VALIDATION_FAILED` + `fieldErrors` 하나를 만든다. 응답 모양은 애노테이션 검증과 똑같다. 화면은 어디서 검사했는지 몰라도 된다.

`AuthService.signup`은 이것을 **중복 확인보다 먼저** 부른다. 형식이 틀린 입력에 DB를 볼 필요가 없어서다.

**블로그 주소 규칙** `src/main/java/com/nhnacademy/blog/blog/application/BlogService.java`

```java
private void checkAddressRule(String address) {
    String reason = null;
    if (!BlogAddressRule.hasValidFormat(address)) {
        reason = "영문 소문자·숫자·하이픈 4~32자로, 하이픈으로 시작하거나 끝날 수 없습니다.";
    } else if (BlogAddressRule.isReserved(address)) {
        reason = "쓸 수 없는 주소입니다.";
    }
    if (reason != null) {
        throw BusinessException.fieldErrors(ErrorCode.BLOG_ADDRESS_INVALID,
                List.of(new FieldErrorDetail("address", reason)));
    }
}
```

- 주소는 `@Pattern`으로도 형식을 볼 수 있지만 서비스에서 본다. 이유 셋: ① API 명세가 주소 오류에 `VALIDATION_FAILED`가 아닌 **`BLOG_ADDRESS_INVALID`**를 정했다. ② 같은 규칙(`BlogAddressRule`)을 Host 해석([15](./15-subdomain-host-routing.md))과 주소 확인 API(`checkAddress`)도 쓴다. 규칙이 한 곳에 있어야 셋이 어긋나지 않는다. ③ 예약어 목록은 정규식이 아니다.
- 그래서 `BlogCreateRequest`의 `address`에는 `@NotNull`만 있다(값이 아예 없으면 `VALIDATION_FAILED`).

### 5.4 상태 코드 순서와 RequestValidator

API 명세는 "한 요청이 여러 조건에 걸리면 **404 → 401 → 403 → 400/409** 순서"라고 정했다([16](./16-authorization-visibility.md)). 남의 블로그 정보를 바꾸려는 사람이 이름을 51자로 보냈다면, 답은 400이 아니라 **403**이어야 한다. 400을 주면 "권한은 있는데 입력만 틀렸다"고 잘못 알려 주는 셈이다.

그런데 4절에서 봤듯이 `@Valid`는 메서드 몸통보다 먼저 실행된다.

```java
// 이렇게 쓰면 남의 블로그에 51자 이름 → 400 (주인 검사까지 못 감)
public BlogResponse update(@CurrentBlog Blog blog, @AuthenticationPrincipal LoginMember member,
                           @Valid @RequestBody BlogUpdateRequest request) {
    blogOwnerGuard.requireOwner(blog, member);   // 403은 여기서
```

그래서 `@Valid`를 빼고, 주인 검사 **뒤에** 직접 검증한다.

`src/main/java/com/nhnacademy/blog/blog/presentation/BlogController.java`

```java
@PatchMapping("/api/blog")
public BlogResponse update(@CurrentBlog Blog blog, @AuthenticationPrincipal LoginMember member,
                           @RequestBody BlogUpdateRequest request) {
    blogOwnerGuard.requireOwner(blog, member);
    requestValidator.validate(request);
    Blog updated = blogService.updateInfo(blog.getAddress(), request.name(), request.description());
    return BlogResponse.from(blogQueryService.detail(updated, member.id()));
}
```

- `@CurrentBlog`(인자 해석기)가 먼저 실행되어 없는 블로그면 **404**.
- `requireOwner`: 비회원 **401**, 남이면 **403**.
- 그다음 `requestValidator.validate`: 틀리면 **400**.

`src/main/java/com/nhnacademy/blog/global/web/RequestValidator.java`

```java
public <T> T validate(T request) {
    List<FieldErrorDetail> errors = validator.validate(request).stream()
            .sorted(Comparator.comparing(violation -> violation.getPropertyPath().toString()))
            .map(RequestValidator::toFieldError)
            .toList();
    if (!errors.isEmpty()) {
        throw BusinessException.fieldErrors(ErrorCode.VALIDATION_FAILED, errors);
    }
    return request;
}
```

- `validator`는 `jakarta.validation.Validator`다. Spring Boot가 만들어 둔 검증기 빈을 생성자로 받는다. `@Valid`가 안에서 쓰는 것과 같은 검증기다.
- `validator.validate(request)`는 실패한 제약마다 `ConstraintViolation` 하나를 담은 `Set`을 돌려준다. `Set`이라 순서가 정해져 있지 않아서, 칸 이름(`getPropertyPath()`)으로 정렬해 응답이 매번 같은 순서가 되게 했다.
- `getMessage()`가 애노테이션의 `message`다. 응답 모양은 `handleBind`가 만드는 것과 같다.

테스트 `BlogInfoIntegrationTest`:

```java
void onlyOwnerCanUpdateAndPermissionComesBeforeInputErrors() throws Exception {
    String invalid = "{\"name\":\"" + "가".repeat(51) + "\"}";

    update(null, invalid).andExpect(status().isUnauthorized());
    update(testMembers.loginCookies(other), invalid)
            .andExpect(status().isForbidden())
            .andExpect(jsonPath("$.code").value("FORBIDDEN"));
    update(testMembers.loginCookies(owner), invalid)
            .andExpect(status().isBadRequest())
            .andExpect(jsonPath("$.fieldErrors[0].field").value("name"));
    update(testMembers.loginCookies(owner), "{\"name\":\"   \"}")
            .andExpect(status().isBadRequest());
}
```

같은 잘못된 본문을 비회원·남·주인이 보내면 각각 401·403·400이다.

한계: JSON 문법 자체가 틀린 본문은 여전히 403보다 먼저 400이다. `@RequestBody`가 객체를 만드는 단계(바인딩)는 메서드보다 먼저라 피할 수 없다. 화면이 만드는 요청에서는 일어나지 않는 경우라 그대로 둔다.

로그인·가입처럼 권한 검사가 없는 API는 그냥 `@Valid`를 쓴다. 순서가 문제 되는 것은 "주인만" 같은 권한 검사가 있는 쓰기 API다. 스텝 5의 글 수정(`PUT /api/posts/{id}`)도 같은 방식을 쓴다.

### 5.5 PATCH: null은 그대로, 빈 문자열은 지우기

`src/main/java/com/nhnacademy/blog/blog/presentation/dto/BlogUpdateRequest.java`

```java
public record BlogUpdateRequest(
        @Size(min = 1, max = 50, message = "블로그 이름은 1~50자입니다.")
        @Pattern(regexp = "(?s).*\\S.*", message = "블로그 이름을 입력해 주세요.")
        String name,

        @Size(max = 500, message = "소개는 500자까지입니다.")
        String description) {
}
```

- PATCH는 "보낸 칸만 바꾼다"다. 그래서 `@NotBlank`를 쓰지 않는다. `@NotBlank`는 `null`도 실패시키므로, 소개만 바꾸려고 `name`을 안 보낸 요청까지 막아 버린다.
- 대신 "보냈다면 공백만은 안 된다"를 `@Pattern("(?s).*\\S.*")`로 쓴다. `\S`는 공백이 아닌 글자 하나, `.*`는 아무 글자 여러 개. 즉 "어딘가에 공백 아닌 글자가 하나 있다". `(?s)`는 `.`이 줄바꿈도 받게 하는 옵션이다(없으면 줄바꿈이 든 이름이 틀린 것으로 나온다). `@Pattern`은 `null`을 통과시키므로 안 보낸 경우는 괜찮다.

엔티티 `src/main/java/com/nhnacademy/blog/blog/domain/Blog.java`

```java
public void changeInfo(String name, String description) {
    if (name != null) {
        this.name = name;
    }
    if (description != null) {
        this.description = description.isBlank() ? null : description;
    }
}
```

| 보낸 본문 | `name` | `description` |
| --- | --- | --- |
| `{"name":"새 이름"}` | 바뀜 | 그대로(`null`이라) |
| `{"description":""}` | 그대로 | **지워짐**(DB `NULL`) |
| `{"description":"새 소개"}` | 그대로 | 바뀜 |

JSON에서 "칸을 안 보냄"과 "칸에 `null`을 보냄"은 바인딩 뒤 둘 다 `null`이라 구별되지 않는다. 그래서 지우기 신호를 빈 문자열로 정했다. 이름 앞뒤 공백은 서비스(`BlogService.updateInfo`)가 `trim()`한다.

### 5.6 본문에 없는 boolean 칸: 실제로 겪은 일

처음에 로그인 요청은 이랬다.

```java
public record LoginRequest(@NotBlank String email, @NotBlank String password, boolean rememberMe) { }
```

통합 테스트는 늘 `"rememberMe":false`를 넣어 보내서 통과했다. 스텝 4를 마치고 실제 서버에 curl로 한 바퀴 돌리다가, `rememberMe` 없이 보낸 로그인이 **400 `VALIDATION_FAILED`(fieldErrors 없음)**로 돌아왔다. 틀린 비밀번호의 401도, 맞는 비밀번호의 200도 아니었다.

- fieldErrors가 없다는 것은 검증(`handleBind`)이 아니라 **바인딩 실패**(`handleUnreadable`)라는 뜻이다.
- Jackson 3 기본 설정에서는 기본형 `boolean` 칸이 본문에 없으면 값을 만들지 못해 역직렬화가 실패했고, Spring이 이것을 `HttpMessageNotReadableException`으로 바꿨다.

수정: 생략할 수 있는 칸이므로 `Boolean`으로 받고, `null`을 "고르지 않음"으로 읽는 메서드를 둔다.

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

- `Boolean.TRUE.equals(rememberMe)`: `rememberMe`가 `null`이어도 NPE 없이 `false`. `if (rememberMe)`로 쓰면 언박싱 중 NPE가 난다.
- 재발을 막는 테스트 `LoginIntegrationTest.rememberMeCanBeOmitted`가 `rememberMe` 없는 본문으로 200과 "Max-Age 없는 쿠키(브라우저를 닫으면 사라짐)"를 확인한다.

교훈: **테스트가 늘 모든 칸을 채워 보내면 "칸을 생략한 요청"은 아무도 검사하지 않는다.** 선택 칸이 있는 API는 생략한 요청을 하나 테스트한다.

### 5.7 모르는 칸은 무시된다

`BlogInfoIntegrationTest.ownerUpdatesNameAndDescription`은 일부러 `"address":"changed-address"`를 함께 보낸다.

```java
update(testMembers.loginCookies(owner), """
        {"name":"  새 이름 ","description":"새 소개","address":"changed-address"}
        """)
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.name").value("새 이름"))
        .andExpect(jsonPath("$.description").value("새 소개"))
        // 주소는 바꿀 수 없다
        .andExpect(jsonPath("$.address").value(blog.getAddress()));
```

`BlogUpdateRequest`에 `address`가 없으니 Jackson은 그 칸을 버리고 200이 났다(Spring Boot의 기본 Jackson 설정은 모르는 칸에 실패하지 않는다). 주소를 바꿀 길은 요청 DTO에 없고, 엔티티 컬럼도 `updatable = false`라 이중으로 막혀 있다. **요청 DTO에 받을 칸만 두는 것** 자체가 "바꾸면 안 되는 칸을 못 바꾸게" 하는 방어다. 엔티티를 요청 본문으로 바로 받으면(`@RequestBody Blog`) 이 방어가 사라진다.

### 5.8 @Email은 앞뒤 공백을 거절한다

처음 쓴 테스트는 `"  " + 이메일 + " "`처럼 공백을 붙여 보내고 "서버가 다듬어 준다"를 확인하려 했다. 결과는 202가 아니라 **400**이었다. `@Email`은 공백이 붙은 값을 이메일 형식으로 보지 않는다. 검증은 서비스의 `Emails.normalize`(소문자로 맞추기)보다 먼저 일어나므로, 서버가 다듬을 기회가 없다. 이 동작이 맞다고 보고 테스트를 "대소문자만 다른 이메일"(`emailIsComparedIgnoringCase`)로 바꿨다. 공백 다듬기는 화면이 보낼 때 `email.trim()`으로 한다.

## 6. 자주 하는 실수와 함정

1. **`@Size`, `@Email`, `@Pattern`만 붙이고 필수라고 믿기**: 셋 다 `null`을 통과시킨다. 필수 칸에는 `@NotBlank`(문자열)나 `@NotNull`을 함께.
2. **`@NotEmpty`로 공백 거르기**: `"   "`은 길이가 3이라 통과한다. 공백만인 값을 막으려면 `@NotBlank`.
3. **`@Valid` 빼먹기**: 애노테이션을 다 적어도 `@Valid`(또는 `validator.validate`)가 없으면 검사가 안 된다. 잘못된 값이 DB까지 가서 500이 된다.
4. **권한 검사가 있는 API에 `@Valid`**: 남이 보낸 잘못된 입력에 403 대신 400이 나간다. 주인 검사 뒤 `RequestValidator`.
5. **선택 칸을 기본형으로**: `boolean`, `int` 칸을 생략하면 바인딩이 실패할 수 있다. 생략 가능한 칸은 `Boolean`, `Integer`.
6. **`if (boxedBoolean)`**: `null`이면 NPE. `Boolean.TRUE.equals(...)`.
7. **글자 수와 바이트 수 혼동**: `@Size`는 글자 수다. bcrypt 72바이트, DB의 바이트 제한 같은 것은 코드로 바이트를 센다.
8. **같은 규칙을 여러 곳에 따로 쓰기**: 주소 규칙을 `@Pattern`, Host 해석, 주소 확인 API에 각각 쓰면 언젠가 어긋난다. 규칙 클래스 하나(`BlogAddressRule`)를 같이 쓴다.
9. **파서 오류 메시지를 그대로 내보내기**: `HttpMessageNotReadableException`의 메시지에는 클래스 이름 같은 내부 정보가 들어 있다. 이 프로젝트는 fieldErrors 없는 400만 준다(COM-02).
10. **엔티티를 `@RequestBody`로 바로 받기**: 바꾸면 안 되는 칸(주소, 주인, 역할)까지 클라이언트가 채울 수 있다. 요청 DTO에는 받을 칸만.

## 7. 직접 해 보기

**실습 1. 검증 오류 모양 보기** (서버를 띄우고 `/etc/hosts`에 `blog.test`가 있을 때. 없으면 `-H 'Host: blog.test'`와 `localhost:8080`)

```bash
curl -s -X POST localhost:8080/api/auth/signup -H 'Host: blog.test' \
  -H 'X-Requested-With: XMLHttpRequest' -H 'Content-Type: application/json' \
  -d '{"email":"x","code":"12","password":"","nickname":""}' | jq
```

`fieldErrors`에 칸 몇 개가 나오는지, 각각의 `reason`이 어느 애노테이션의 `message`인지 짝지어 본다. 한 칸에 두 애노테이션이 함께 실패하면 두 줄이 나온다.

**실습 2. 바인딩 실패와 검증 실패 구별하기**

```bash
# JSON 문법 오류 → fieldErrors 없음 (handleUnreadable)
curl -s -X POST localhost:8080/api/auth/login -H 'Host: blog.test' \
  -H 'X-Requested-With: XMLHttpRequest' -H 'Content-Type: application/json' -d '{"email":' | jq
# 빈 이메일 → fieldErrors 있음 (handleBind)
curl -s -X POST localhost:8080/api/auth/login -H 'Host: blog.test' \
  -H 'X-Requested-With: XMLHttpRequest' -H 'Content-Type: application/json' -d '{"email":"","password":"a"}' | jq
```

**실습 3. boolean 함정 되살려 보기**

1. `LoginRequest`의 `Boolean rememberMe`를 `boolean rememberMe`로, `keepLoggedIn()`을 `return rememberMe;`로 바꾼다.
2. `./mvnw test -Dtest=LoginIntegrationTest#rememberMeCanBeOmitted`
3. 기대 결과: 200이 아니라 400으로 실패한다. 되돌린다.

**실습 4. 상태 코드 순서 깨 보기**

1. `BlogController.update`에서 `requestValidator.validate(request);`를 지우고 파라미터를 `@Valid @RequestBody BlogUpdateRequest request`로 바꾼다.
2. `./mvnw test -Dtest=BlogInfoIntegrationTest#onlyOwnerCanUpdateAndPermissionComesBeforeInputErrors`
3. 기대 결과: 남(other)의 요청이 403이 아니라 400이 되어 실패한다. 비회원(401)도 400이 된다. 되돌린다.

**실습 5. `(?s)` 빼 보기**

`BlogUpdateRequest`의 정규식을 `".*\\S.*"`로 바꾸고, 테스트를 하나 만들어 `{"name":"첫 줄\n둘째 줄"}`을 보내 본다. 줄바꿈 때문에 `.`이 맞지 않아 400이 된다. 되돌린다.

## 8. 확인 문제

1. `@Size(max = 20) String nickname`만 붙였을 때 닉네임 칸을 아예 안 보내면 어떻게 되나? 필수로 만들려면?
<details><summary>답</summary><code>@Size</code>는 <code>null</code>을 통과시키므로 검증을 통과한다(그 뒤 서비스나 DB에서 문제가 된다). 필수로 만들려면 <code>@NotBlank</code>를 함께 붙인다.</details>

2. 같은 400 `VALIDATION_FAILED`인데 `fieldErrors`가 있을 때와 없을 때는 각각 어떤 상황인가?
<details><summary>답</summary>있으면 객체는 만들어졌고 제약 검증에 실패한 것(<code>handleBind</code>, <code>handleMethodValidation</code>, 서비스의 <code>invalidField</code>). 없으면 JSON 자체를 객체로 만들지 못한 바인딩 실패(<code>handleUnreadable</code>)다. 문법 오류, 기본형 칸 누락 등.</details>

3. `PATCH /api/blog`에 `@Valid`를 쓰지 않고 `RequestValidator`를 메서드 안에서 부르는 이유는?
<details><summary>답</summary><code>@Valid</code>는 메서드 몸통보다 먼저 실행되어, 주인 검사(401·403)보다 입력 오류(400)가 먼저 나간다. 명세의 순서(404 → 401 → 403 → 400)를 지키려면 주인 검사 뒤에 검증해야 한다.</details>

4. 블로그 주소 규칙을 `@Pattern`이 아니라 서비스에서 검사하는 이유 두 가지는?
<details><summary>답</summary>명세가 주소 오류에 <code>VALIDATION_FAILED</code>가 아닌 <code>BLOG_ADDRESS_INVALID</code>를 정했고, 같은 규칙(<code>BlogAddressRule</code>)을 Host 해석과 주소 확인 API도 써서 한 곳에 두어야 어긋나지 않는다. 예약어 목록은 정규식으로 쓰기도 어색하다.</details>

5. `LoginRequest`의 `rememberMe`를 `Boolean`으로 바꾼 이유와, 값을 읽을 때 `Boolean.TRUE.equals`를 쓰는 이유는?
<details><summary>답</summary>기본형 <code>boolean</code>이면 칸을 생략한 요청이 Jackson 3 기본 설정에서 바인딩 실패(400)가 됐다. <code>Boolean</code>이면 생략 시 <code>null</code>이 들어오는데, <code>if (rememberMe)</code>는 <code>null</code> 언박싱에서 NPE가 나므로 <code>Boolean.TRUE.equals</code>로 <code>null</code>을 <code>false</code>로 읽는다.</details>

6. PATCH 본문에서 소개를 지우려면 무엇을 보내나? 왜 `null`이 아닌가?
<details><summary>답</summary>빈 문자열 <code>""</code>. 바인딩 뒤에는 "칸을 안 보냄"과 "<code>null</code>을 보냄"이 둘 다 <code>null</code>이라 구별할 수 없고, <code>null</code>은 "그대로 두기"로 쓰기 때문이다.</details>

7. 블로그 수정 본문에 `"address"`를 넣어 보내도 주소가 바뀌지 않는 이유 두 가지는?
<details><summary>답</summary>요청 DTO <code>BlogUpdateRequest</code>에 <code>address</code> 칸이 없어 Jackson이 무시하고, 엔티티의 <code>address</code> 컬럼이 <code>updatable = false</code>라 UPDATE 문에도 들어가지 않는다.</details>

8. `@Pattern(regexp = ".*\\S.*")`에 `(?s)`를 붙인 이유는?
<details><summary>답</summary>기본적으로 정규식의 <code>.</code>은 줄바꿈과 맞지 않아, 줄바꿈이 든 값은 전체 일치에 실패한다. <code>(?s)</code>를 붙이면 <code>.</code>이 줄바꿈도 받아 "어딘가에 공백 아닌 글자가 있나"만 본다.</details>

## 9. 더 읽을거리

- Jakarta Validation 명세와 Hibernate Validator 레퍼런스: 내장 제약 목록(`@NotBlank`, `@Size`, `@Email`, `@Pattern`)
- Spring Framework 레퍼런스, Web MVC "Validation" (메서드 검증, `HandlerMethodValidationException`, 6.1 변경)
- Spring Framework 레퍼런스, "HTTP Message Conversion", `@RequestBody`
- Spring Boot 레퍼런스, "JSON" / Jackson 설정(`spring.jackson.*`)과 Spring Boot 4의 Jackson 3 이전 안내
- Jackson 3 `DeserializationFeature` 문서(`FAIL_ON_NULL_FOR_PRIMITIVES`, `FAIL_ON_UNKNOWN_PROPERTIES`)
- contracts/rest-api.md "상태 코드 순서", "오류 본문"
