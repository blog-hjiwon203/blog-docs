# Spring MVC 요청 처리와 예외 처리

> 관련 스텝: [스텝 2](../step-02.md)(COM-02 오류 형식, `GlobalExceptionHandler`), [스텝 3](../step-03.md)(필터의 오류 응답, `@CurrentBlog`, 인터셉터)
> 기준 버전: Spring Boot 4.1.1, Spring Framework 7, 내장 Tomcat

## 1. 이 문서로 배우는 것

- HTTP 요청 하나가 서블릿 컨테이너 → 필터 → DispatcherServlet → 컨트롤러로 가는 길
- HandlerMapping, HandlerAdapter, HandlerInterceptor, ArgumentResolver, HttpMessageConverter가 각각 하는 일
- 필터·인터셉터·컨트롤러 어드바이스의 차이와, 각각이 **어떤 예외를 잡을 수 있는지**
- `@RestControllerAdvice`와 `@ExceptionHandler`로 오류 응답을 한 모양으로 만드는 법
- Bean Validation(`@Valid`, `@NotBlank`)과 검증 실패 예외
- 콘텐츠 협상(Accept, Content-Type)과 이 프로젝트에서 오류 본문이 비었던 사건
- 500 응답에서 내부 정보를 숨기는 이유, `ErrorCode` enum 설계
- HTTP 상태 코드의 뜻

**먼저 알면 좋은 것**: HTTP 요청·응답의 구조(메서드, 경로, 헤더, 본문, 상태 코드), JSON, [Spring Boot 기초](./01-spring-boot-basics.md)(빈, 애노테이션 기반 설정).

## 2. 왜 필요한가

API가 50개쯤 된다고 하자. 각 컨트롤러가 오류를 제멋대로 돌려주면:

```
POST /api/posts         → 400 {"error": "title is blank"}
POST /api/comments      → 400 "내용을 입력하세요"            (문자열)
GET  /api/posts/999     → 500 {"timestamp":..., "trace":"java.lang.NullPointerException at ..."}
GET  /api/nothing       → 404 (Tomcat 기본 HTML 페이지)
```

- 프론트는 API마다 다른 오류 모양을 따로 처리해야 한다.
- 500 응답에 스택 트레이스가 나가면 **내부 클래스 이름, 라이브러리 버전, SQL**이 노출된다. 공격자가 약점을 찾는 단서가 된다.
- 컨트롤러마다 `try-catch`를 쓰면 같은 코드가 반복되고, 빠뜨린 곳에서 위 문제가 다시 생긴다.

그래서 이 프로젝트는 **모든 오류를 한 곳에서 한 모양(COM-02)으로** 바꾼다.

```json
{ "code": "VALIDATION_FAILED", "message": "입력값을 확인해 주세요.",
  "fieldErrors": [{ "field": "title", "reason": "제목을 입력해 주세요." }] }
```

이것을 하려면 "예외가 어디서 생겨 어디까지 올라가는지", 즉 Spring MVC의 요청 처리 구조를 알아야 한다.

## 3. 기본 개념

### 3.1 서블릿과 서블릿 컨테이너

- **서블릿(Servlet)**: 자바에서 HTTP 요청을 받아 응답을 만드는 표준 인터페이스(`jakarta.servlet`).
- **서블릿 컨테이너**: 서블릿을 실행하는 서버. Spring Boot는 **Tomcat**을 jar 안에 넣어 함께 띄운다(내장 Tomcat).
- Spring MVC는 **DispatcherServlet**이라는 서블릿 하나로 모든 요청을 받고, 안에서 알맞은 컨트롤러로 나눠 준다(프런트 컨트롤러 패턴).

### 3.2 요청 처리의 등장인물

| 이름 | 위치 | 하는 일 |
| --- | --- | --- |
| Filter | 서블릿 **앞**(서블릿 규격) | 모든 요청·응답을 감싼다. 인증, 인코딩, 헤더 붙이기 |
| DispatcherServlet | Spring MVC의 입구 | 아래 부품들을 차례로 부른다 |
| HandlerMapping | MVC 안 | "이 요청은 어느 컨트롤러 메서드가 맡나" 찾기(`@GetMapping` 등) |
| HandlerInterceptor | MVC 안, 컨트롤러 앞뒤 | 어느 핸들러로 갈지 **안 다음에** 끼어든다(`preHandle`, `postHandle`, `afterCompletion`) |
| HandlerAdapter | MVC 안 | 찾은 메서드를 실제로 부른다 |
| HandlerMethodArgumentResolver | Adapter 안 | 메서드 인자 하나하나를 채운다(`@PathVariable`, `@RequestBody`, `@CurrentBlog`…) |
| HttpMessageConverter | Adapter 안 | JSON ↔ 자바 객체 변환(요청 본문 읽기, 응답 본문 쓰기) |
| HandlerExceptionResolver | MVC 안 | 처리 중 생긴 예외를 응답으로 바꾼다(`@ExceptionHandler`가 여기서 동작) |

### 3.3 흐름 그림

```
HTTP 요청
   │
   ▼
┌──────────────────── Tomcat ───────────────────────────────────────────────┐
│  Filter 1 → Filter 2 → ... (Spring Security 필터 체인도 여기 하나로 들어 있음) │
│      │                                                                      │
│      ▼                                                                      │
│  ┌──────────────── DispatcherServlet ─────────────────────────────────────┐ │
│  │ ① HandlerMapping: GET /api/test/blog → TestApiController.blog()       │ │
│  │ ② Interceptor.preHandle()        (false면 여기서 끝)                   │ │
│  │ ③ HandlerAdapter                                                       │ │
│  │     ├ ArgumentResolver: @CurrentBlog Blog blog ← Host로 블로그 찾기     │ │
│  │     ├ HttpMessageConverter(읽기): @RequestBody JSON → 객체, @Valid 검증 │ │
│  │     ├ 컨트롤러 메서드 실행                                              │ │
│  │     └ HttpMessageConverter(쓰기): 반환값 → JSON                         │ │
│  │ ④ Interceptor.postHandle()                                             │ │
│  │    (②~④ 어디서든 예외 → HandlerExceptionResolver → @ExceptionHandler)  │ │
│  │ ⑤ Interceptor.afterCompletion()  (예외가 나도 항상)                     │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│      │                                                                      │
│  Filter들의 뒷부분(chain.doFilter 다음 코드)                                │
└─────────────────────────────────────────────────────────────────────────────┘
   │
   ▼
HTTP 응답
```

### 3.4 필터, 인터셉터, 컨트롤러 어드바이스 비교

| | Filter | HandlerInterceptor | @RestControllerAdvice |
| --- | --- | --- | --- |
| 규격 | 서블릿(Spring 몰라도 됨) | Spring MVC | Spring MVC |
| 언제 | DispatcherServlet **앞뒤** | 컨트롤러가 정해진 **다음** | 예외가 났을 때 |
| 아는 것 | 요청·응답 원본 | 어느 컨트롤러 메서드인지(`HandlerMethod`, 애노테이션) | 예외 객체 |
| 정적 파일·없는 주소에도 동작 | 예 | 핸들러가 있어야(정적 리소스 핸들러 포함) | — |
| 그 안의 예외를 `@ExceptionHandler`가 잡나 | **아니오**(DispatcherServlet 밖) | 예 | — |
| 이 프로젝트 예 | `JwtAuthenticationFilter`, `CsrfHeaderFilter`, `ContentSecurityPolicyFilter`, `ResponseCachingFilter` | `IdempotencyInterceptor` | `GlobalExceptionHandler` |

핵심: **필터에서 생긴 문제는 `@RestControllerAdvice`가 모른다.** 그래서 필터는 오류 응답을 스스로 써야 한다(5.5 `ErrorResponseWriter`).

### 3.5 Bean Validation

요청 값이 규칙에 맞는지 애노테이션으로 선언한다(`jakarta.validation`, 구현은 Hibernate Validator. `spring-boot-starter-validation`이 넣는다).

```java
public record SignupRequest(
        @NotBlank(message = "이메일을 입력해 주세요.") @Email String email,
        @Size(min = 8, message = "비밀번호는 8자 이상입니다.") String password) {
}

@PostMapping("/api/auth/signup")
public Me signup(@Valid @RequestBody SignupRequest request) { ... }   // @Valid가 검증을 켠다
```

| 애노테이션 | 뜻 |
| --- | --- |
| `@NotNull` | null 아님 |
| `@NotBlank` | null 아님 + 공백만 있는 문자열 아님(문자열용) |
| `@Size(min, max)` | 길이·개수 범위 |
| `@Email`, `@Pattern(regexp)` | 형식 |
| `@Min`, `@Max`, `@Positive` | 숫자 범위 |

### 3.6 콘텐츠 협상

- 요청 `Accept` 헤더: "나는 이런 형식의 응답을 원한다". 브라우저 주소창은 `text/html,...`, `fetch`는 보통 `*/*`, 이 프로젝트 API 클라이언트는 `application/json`.
- 요청 `Content-Type`: "내가 보내는 본문은 이 형식이다".
- 응답 `Content-Type`: "내가 돌려주는 본문은 이 형식이다".
- Spring은 반환값을 쓸 때 **반환 타입과 Accept를 보고** 쓸 수 있는 HttpMessageConverter를 고른다. JSON 변환기(Jackson)는 `application/json`(그리고 `+json`)만 만든다.

## 4. 동작 원리

### 4.1 예외가 응답이 되기까지

컨트롤러에서 `throw new BusinessException(ErrorCode.NICKNAME_TAKEN)`이 일어나면:

1. 예외가 HandlerAdapter를 거쳐 DispatcherServlet까지 올라온다.
2. DispatcherServlet이 등록된 **HandlerExceptionResolver**들에게 차례로 묻는다. 순서는 대략:
   1. `ExceptionHandlerExceptionResolver`: `@ExceptionHandler` 메서드를 찾는다(컨트롤러 안 → `@ControllerAdvice` 순서).
   2. `ResponseStatusExceptionResolver`: `@ResponseStatus`가 붙은 예외, `ResponseStatusException`.
   3. `DefaultHandlerExceptionResolver`: Spring 표준 예외(없는 주소, 잘못된 메서드 등)를 상태 코드로. **본문은 비워 두고** `response.sendError(...)`만 한다.
3. `@ExceptionHandler`는 **가장 구체적인 예외 타입**에 맞는 메서드가 선택된다. `BusinessException` 핸들러가 있으면 `Exception` 핸들러보다 먼저 쓰인다.
4. 핸들러가 돌려준 `ResponseEntity`가 HttpMessageConverter로 JSON이 된다.
5. 어떤 리졸버도 처리하지 못하면 예외가 서블릿 컨테이너까지 올라가고, Spring Boot의 `/error`(BasicErrorController)가 응답을 만든다.

### 4.2 Spring이 대신 던지는 예외들

컨트롤러 코드가 실행되기도 전에 Spring이 던지는 예외가 많다. 이것도 잡아야 모든 오류가 COM-02 모양이 된다.

| 예외 | 언제 | 이 프로젝트 응답 |
| --- | --- | --- |
| `MethodArgumentNotValidException` | `@Valid @RequestBody` 검증 실패 | 400 + fieldErrors |
| `BindException` | `@ModelAttribute`(쿼리 파라미터 → 객체) 바인딩·검증 실패. 위 예외의 **부모 클래스** | 400 + fieldErrors |
| `HandlerMethodValidationException` | `@RequestParam @Min(1) int page` 같은 **메서드 인자 자체**의 제약 위반(Spring 6.1+) | 400 + fieldErrors |
| `HttpMessageNotReadableException` | 본문이 JSON이 아님, 형식이 깨짐, 타입이 안 맞음 | 400 (파서 메시지는 숨김) |
| `HttpMediaTypeNotSupportedException` | `Content-Type`이 지원 안 하는 형식 | 400 |
| `MethodArgumentTypeMismatchException` | `/posts/abc`를 `@PathVariable Long id`로 받으려 함 | 400 + `{field: "id"}` |
| `MissingServletRequestParameterException` | 필수 `@RequestParam` 없음 | 400 |
| `NoResourceFoundException` | 맞는 컨트롤러도 정적 파일도 없음(Spring 6.1+) | 404 |
| `HttpRequestMethodNotSupportedException` | 주소는 있는데 메서드가 다름(GET만 있는데 POST) | 405 |

`MethodArgumentNotValidException`은 `BindException`의 하위 클래스라서, `BindException` 핸들러 하나로 둘 다 잡힌다.

### 4.3 응답 Content-Type이 정해지는 과정

`ResponseEntity<ErrorResponse>`를 돌려줄 때:

1. 응답에 **이미 Content-Type이 정해져 있으면**(예: `ResponseEntity.contentType(APPLICATION_JSON)`) 그 형식을 쓸 수 있는 변환기를 고른다. Accept는 따지지 않는다.
2. 정해져 있지 않으면, 요청의 `Accept`와 "이 타입을 쓸 수 있는 형식들"을 맞춰 본다.
   - `Accept: application/json` 또는 `*/*` → JSON으로 쓴다.
   - `Accept: text/html`만 → `ErrorResponse`를 HTML로 쓸 변환기가 없다 → `HttpMediaTypeNotAcceptableException`(406 상황).
3. 예외 처리 중에 다시 이 문제가 나면, 그 `@ExceptionHandler` 응답은 버려지고 남은 리졸버가 처리한다.

### 4.4 ArgumentResolver가 인자를 채우는 과정

HandlerAdapter는 컨트롤러 메서드의 **인자마다** 등록된 `HandlerMethodArgumentResolver`들에게 "이 인자 처리할 수 있니?"(`supportsParameter`)를 묻고, 처음 "예"라고 한 리졸버의 `resolveArgument`로 값을 받는다. `@PathVariable`, `@RequestParam`, `@RequestBody`, `@AuthenticationPrincipal`도 모두 이 구조다. 우리가 만든 리졸버는 `WebMvcConfigurer.addArgumentResolvers`로 추가한다. 리졸버 안에서 던진 예외도 컨트롤러 안의 예외처럼 `@ExceptionHandler`가 잡는다.

## 5. 이 프로젝트에서는

경로는 코드 저장소 `src/main/java/com/nhnacademy/blog/` 기준이다.

### 5.1 오류 코드 설계: `global/error/ErrorCode.java`

```java
public enum ErrorCode {

    VALIDATION_FAILED(HttpStatus.BAD_REQUEST, "입력값을 확인해 주세요."),
    IDEMPOTENCY_KEY_REQUIRED(HttpStatus.BAD_REQUEST, "요청 키가 필요합니다."),
    ...
    NOT_FOUND(HttpStatus.NOT_FOUND, "요청한 내용을 찾을 수 없습니다."),
    METHOD_NOT_ALLOWED(HttpStatus.METHOD_NOT_ALLOWED, "지원하지 않는 요청 방식입니다."),
    ...
    INTERNAL_ERROR(HttpStatus.INTERNAL_SERVER_ERROR, "일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.");

    private final HttpStatus status;
    private final String message;
```

- **코드 이름이 곧 API 약속**이다. 응답의 `code`는 `errorCode.name()`이라 `"NICKNAME_TAKEN"` 같은 문자열이 된다. 프론트는 이 문자열로 분기한다(예: `MEMBER_SUSPENDED`면 정지 안내 화면).
- 상태 코드와 문장을 **한 곳에** 둔다. 같은 오류가 API마다 다른 상태 코드로 나가는 일을 막는다.
- `message`는 "화면에 그대로 띄워도 되는 문장"이다. 기술 용어를 넣지 않는다.
- 목록은 contracts/rest-api.md 오류 표를 그대로 옮겼다. 표에 없던 405는 지원 확인 후 문서에도 추가했다.

### 5.2 응답 본문: `global/error/ErrorResponse.java`

```java
@JsonInclude(JsonInclude.Include.NON_NULL)       // null인 필드는 JSON에서 아예 빠진다
public record ErrorResponse(String code, String message, List<FieldErrorDetail> fieldErrors, Object detail) {

    public static ErrorResponse of(ErrorCode errorCode) { ... }           // code + message만
    public static ErrorResponse of(BusinessException e) { ... }           // + fieldErrors/detail이 있으면
    public static ErrorResponse validation(List<FieldErrorDetail> fieldErrors) {
        ...
        return new ErrorResponse(errorCode.name(), errorCode.getMessage(), fieldErrors.isEmpty() ? null : fieldErrors,
                null);                                                    // 빈 목록은 null → 빠짐
    }
}
```

- `@JsonInclude(NON_NULL)`이 없으면 `{"code":"NOT_FOUND","message":"...","fieldErrors":null,"detail":null}`처럼 의미 없는 키가 나간다.
- `detail`이 `Object`인 이유: 오류마다 덧붙일 정보 모양이 다르다. 정지면 `{reason, reasonMessage, suspendedUntil}`, 구독자 전용이면 `{blogId, blogName, blogAddress}`.
- 애노테이션은 `com.fasterxml.jackson.annotation` 패키지다. Boot 4는 Jackson 3(`tools.jackson`)을 쓰지만 **애노테이션은 예전 패키지를 그대로** 쓴다.

### 5.3 서비스에서 던지는 예외: `global/error/BusinessException.java`

```java
throw new BusinessException(ErrorCode.NICKNAME_TAKEN);                       // 기본
throw new BusinessException(ErrorCode.MEMBER_SUSPENDED, suspensionDetail);   // detail 포함
throw BusinessException.invalidField("cursor", "목록 위치가 올바르지 않습니다. ...");  // 입력 오류 하나
```

`RuntimeException`을 상속한다. 체크 예외가 아니라서 메서드마다 `throws`를 쓰지 않아도 되고, `@Transactional` 안에서 던지면 기본 규칙대로 롤백된다.

### 5.4 전역 예외 처리: `global/error/GlobalExceptionHandler.java`

```java
@RestControllerAdvice                                  // 모든 컨트롤러에 적용, 반환값을 본문으로 씀
public class GlobalExceptionHandler {

    @ExceptionHandler(BusinessException.class)
    public ResponseEntity<ErrorResponse> handleBusiness(BusinessException e) {
        return ResponseEntity.status(e.getErrorCode().getStatus()).contentType(MediaType.APPLICATION_JSON)
                .body(ErrorResponse.of(e));
    }

    /** @Valid 본문, @ModelAttribute 검증 실패. MethodArgumentNotValidException도 여기로 온다. */
    @ExceptionHandler(BindException.class)
    public ResponseEntity<ErrorResponse> handleBind(BindException e) {
        List<FieldErrorDetail> fieldErrors = e.getBindingResult().getFieldErrors().stream()
                .map(error -> new FieldErrorDetail(error.getField(),
                        error.isBindingFailure() ? INVALID_FORMAT : error.getDefaultMessage()))
                .toList();
        return validation(fieldErrors);
    }
```

- `getFieldErrors()`: 어느 필드가 왜 틀렸는지. `getDefaultMessage()`는 `@NotBlank(message = "...")`에 쓴 문장이다.
- `isBindingFailure()`: 검증 규칙 위반이 아니라 **타입 변환 실패**(숫자 자리에 글자)다. 이때 기본 메시지는 `Failed to convert property value of type 'java.lang.String' to required type 'int'...` 같은 내부 문장이라, "형식이 올바르지 않습니다."로 바꾼다.

```java
    /** 본문이 JSON이 아니거나 형식이 맞지 않음. 파서 메시지는 내부 정보라 내보내지 않는다. */
    @ExceptionHandler({HttpMessageNotReadableException.class, HttpMediaTypeNotSupportedException.class})
    public ResponseEntity<ErrorResponse> handleUnreadable(Exception e) {
        return validation(List.of());
    }
```

Jackson 파서 메시지에는 클래스 이름과 위치가 들어 있다. 그대로 내보내지 않는다(테스트 `unreadableBodyIsValidationFailedWithoutParserMessage`가 본문에 "jackson"이 없는지 확인).

```java
    /** 메서드 보안(@PreAuthorize)에 걸림. 비회원이면 로그인 필요(401), 회원이면 권한 없음(403). */
    @ExceptionHandler(AccessDeniedException.class)
    public ResponseEntity<ErrorResponse> handleAccessDenied(AccessDeniedException e) {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        boolean anonymous = authentication == null || authentication instanceof AnonymousAuthenticationToken
                || !authentication.isAuthenticated();
        return error(anonymous ? ErrorCode.UNAUTHORIZED : ErrorCode.FORBIDDEN);
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorResponse> handleUnexpected(Exception e) {
        log.error("예상하지 못한 오류", e);         // 스택은 서버 로그에만
        return error(ErrorCode.INTERNAL_ERROR);    // 응답에는 정해진 문장만
    }
```

- `@PreAuthorize`는 컨트롤러 메서드를 부르는 **프록시**에서 검사하므로 예외가 MVC 안에서 난다 → 어드바이스가 잡는다. 비회원이 막힌 것과 회원이 권한 없는 것을 401/403으로 나눈다([보안 필터 체인](./12-spring-security-filter-chain.md)).
- `Exception` 핸들러가 마지막 그물이다. 더 구체적인 핸들러가 없는 모든 예외가 여기로 온다.

`application.yml`의 `server.error.include-stacktrace: never` 등은 어드바이스까지 오지 못한 오류(4.1의 5번, `/error`)에서도 내부 정보가 안 나가게 하는 **두 번째 안전장치**다.

### 5.5 필터에서 오류 응답 쓰기: `global/error/ErrorResponseWriter.java`

```java
@Component
public class ErrorResponseWriter {

    private final JsonMapper jsonMapper;          // Jackson 3의 ObjectMapper (Boot가 빈으로 만들어 둠)

    private void write(HttpServletResponse response, ErrorCode errorCode, ErrorResponse body) throws IOException {
        response.setStatus(errorCode.getStatus().value());
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.setCharacterEncoding("UTF-8");   // 한글 문장이 깨지지 않게
        jsonMapper.writeValue(response.getOutputStream(), body);
    }
}
```

필터(`CsrfHeaderFilter`, `JwtAuthenticationFilter`)와 Spring Security의 401·403 처리기는 DispatcherServlet 밖이라 `@RestControllerAdvice`의 도움을 못 받는다. 그래서 같은 `ErrorResponse`를 같은 `JsonMapper`로 **직접** 쓴다. 덕분에 필터에서 막힌 요청도 같은 모양이다.

```
curl -X POST localhost:8080/api/anything
→ 403 {"code":"CSRF_REJECTED","message":"허용되지 않은 요청입니다."}   (CsrfHeaderFilter가 씀)
```

### 5.6 ArgumentResolver: `global/host/CurrentBlogArgumentResolver.java`

```java
@Override
public boolean supportsParameter(MethodParameter parameter) {           // 이 인자를 내가 맡나?
    return parameter.hasParameterAnnotation(CurrentBlog.class) && Blog.class.equals(parameter.getParameterType());
}

@Override
public Blog resolveArgument(MethodParameter parameter, ModelAndViewContainer mavContainer,
                            NativeWebRequest webRequest, WebDataBinderFactory binderFactory) {
    HttpServletRequest request = webRequest.getNativeRequest(HttpServletRequest.class);
    Long viewerId = LoginMembers.currentId();                            // 보안 필터가 넣어 둔 로그인 회원
    Blog blog = blogHostResolver.findBlog(request)                       // Host → 블로그
            .filter(found -> blogVisibilityPolicy.canView(found, viewerId))
            .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));   // → 어드바이스가 404 JSON으로
    ...
    return blog;
}
```

`WebConfig.addArgumentResolvers`로 등록한다. 그러면 컨트롤러는 이렇게 쓴다.

```java
@GetMapping("/api/test/blog")
public Map<String, String> blog(@CurrentBlog Blog blog) {   // 블로그 찾기·404 처리를 신경 쓰지 않는다
    return Map.of("address", blog.getAddress());
}
```

"Host로 블로그 찾고, 볼 수 없으면 404"를 블로그 API마다 반복하지 않게 하는 장치다([서브도메인](./15-subdomain-host-routing.md)).

### 5.7 사건: 브라우저 주소창으로 없는 API를 열면 본문이 비었다

스텝 3에서 `SpaForwardIntegrationTest.assetsAndApiAreNotPages`가 실패했다.

```java
mockMvc.perform(get("/api/missing").header("Host", "blog.test").accept(MediaType.TEXT_HTML))
        .andExpect(status().isNotFound())
        .andExpect(jsonPath("$.code").value("NOT_FOUND"));   // ← No value at JSON path "$.code"
```

상태는 404였는데 본문이 비어 있었다. 4.3의 흐름으로 보면:

1. `/api/missing`에 맞는 핸들러가 없음 → `NoResourceFoundException`.
2. 어드바이스의 `handleNotFound`가 `ResponseEntity<ErrorResponse>`를 돌려줌. 이때는 Content-Type을 정하지 않았다.
3. 요청 `Accept`가 `text/html`뿐이라 `ErrorResponse`를 쓸 변환기를 찾지 못함.
4. 어드바이스 응답이 버려지고, `DefaultHandlerExceptionResolver`가 `NoResourceFoundException`을 처리 → **본문 없는 404**.

해결: 모든 오류 응답에 `contentType(MediaType.APPLICATION_JSON)`을 미리 넣었다(4.3의 1번 경로). 오류 응답은 Accept와 상관없이 항상 JSON이다. 이 결정은 rest-api.md "요청·응답 형식"에도 적었다.

배운 점: "정상 응답은 Accept에 맞춰" 협상하는 것이 맞지만, **오류 응답은 협상에 실패하면 아무것도 못 보여 준다.** 오류 형식은 고정하는 편이 안전하다.

### 5.8 인터셉터: `global/web/IdempotencyInterceptor.java`

`@Idempotent`가 붙은 메서드인지는 **어느 핸들러로 갈지 정해진 뒤에야** 알 수 있다. 그래서 필터가 아니라 인터셉터다.

```java
@Override
public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) ... {
    if (!(handler instanceof HandlerMethod method) || !method.hasMethodAnnotation(Idempotent.class)) {
        return true;                                  // 대상이 아니면 그냥 통과
    }
    ...                                               // 키가 없으면 BusinessException → 어드바이스가 400
    replay(response, waitForFirstResponse(redisKey));
    return false;                                     // false: 컨트롤러를 부르지 않고 여기서 끝
}
```

`preHandle`에서 던진 `BusinessException`도 MVC 안이라 어드바이스가 400 JSON으로 바꾼다([멱등성](./17-idempotency-redis.md)).

## 6. HTTP 상태 코드

| 코드 | 이름 | 뜻 | 이 프로젝트 예 |
| --- | --- | --- | --- |
| 200 | OK | 성공, 본문 있음 | 조회, 수정 |
| 201 | Created | 새 자원을 만들었다. `Location` 헤더에 새 주소 | 글 작성(`TestIdempotentController`가 흉내) |
| 204 | No Content | 성공, 본문 없음 | 로그아웃(스텝 4) |
| 301 | Moved Permanently | 영구 이동. 브라우저·검색엔진이 새 주소를 기억 | 이사한 블로그, 다른 블로그 글 |
| 400 | Bad Request | 요청이 잘못됨(입력 오류) | `VALIDATION_FAILED`, `IDEMPOTENCY_KEY_REQUIRED` |
| 401 | Unauthorized | **인증** 필요(누구인지 모름). 이름과 달리 "로그인 필요"의 뜻 | `UNAUTHORIZED`, `LOGIN_FAILED` |
| 403 | Forbidden | 누구인지는 알지만 **권한** 없음 | `FORBIDDEN`, `CSRF_REJECTED`, `MEMBER_SUSPENDED` |
| 404 | Not Found | 없음. 이 프로젝트는 "볼 수 없음"도 404(존재를 숨김) | `NOT_FOUND` |
| 405 | Method Not Allowed | 주소는 있는데 그 메서드는 안 됨 | `METHOD_NOT_ALLOWED` |
| 409 | Conflict | 지금 상태와 충돌(중복 등) | `NICKNAME_TAKEN`, `BLOG_LIMIT_EXCEEDED` |
| 429 | Too Many Requests | 너무 자주 요청 | 인증 메일 1분 제한, 연타 방지 대기 초과 |
| 500 | Internal Server Error | 서버의 예상 못 한 오류 | `INTERNAL_ERROR` |

- 4xx는 **클라이언트가 고쳐야 할** 문제, 5xx는 **서버** 문제다. 사용자의 입력 실수를 500으로 내보내면 안 된다(모니터링에서 진짜 장애와 섞인다).
- 여러 조건에 동시에 걸리면 rest-api.md "상태 코드 순서"대로 404 → 401 → 403 → 400/409를 먼저 준다. 볼 수 없는 글에 401을 주면 "그 글이 있다"는 사실이 새기 때문이다.

## 7. 자주 하는 실수와 함정

| 실수 | 결과 | 대책 |
| --- | --- | --- |
| 필터 안의 오류를 `@ExceptionHandler`로 잡으려 함 | 안 잡힘. Tomcat 기본 응답이나 `/error`로 감 | 필터는 `ErrorResponseWriter`로 직접 쓴다 |
| `@Valid`를 빼먹음 | 검증 애노테이션이 있어도 검사 안 함 | 컨트롤러 인자에 `@Valid` |
| `Exception` 핸들러에서 `e.getMessage()`를 응답에 넣음 | SQL·클래스 이름 노출 | 정해진 문장만, 상세는 로그 |
| 오류 응답 Content-Type을 정하지 않음 | Accept가 `text/html`이면 본문이 빔(5.7) | `contentType(APPLICATION_JSON)` |
| 입력 실수를 `IllegalArgumentException`으로 던짐 | `Exception` 핸들러에 걸려 500 | `BusinessException(VALIDATION_FAILED)` 또는 Bean Validation |
| 401과 403을 섞어 씀 | 프론트가 로그인 화면으로 보내야 할지 판단 못 함 | 비회원 401, 회원인데 권한 없음 403 |
| `@ExceptionHandler`를 컨트롤러 안에도 만듦 | 그 컨트롤러에서는 전역 핸들러보다 먼저 쓰여 모양이 달라질 수 있음 | 전역 하나로 |

## 8. 직접 해 보기

서버를 띄운다(`docker compose up -d`, `./mvnw spring-boot:run`).

1. **오류 모양 비교**
   ```bash
   curl -i localhost:8080/api/no-such-path                        # 404 JSON
   curl -i -H "Accept: text/html" localhost:8080/api/no-such-path # 그래도 404 JSON (5.7)
   curl -i -X POST localhost:8080/api/no-such-path                # 403 CSRF_REJECTED (필터가 먼저 막음)
   curl -i -X POST -H "X-Requested-With: XMLHttpRequest" localhost:8080/api/no-such-path   # 404 JSON
   ```
   마지막 두 줄의 차이를 3.3 그림으로 설명해 본다(어느 단계에서 응답이 만들어졌나).

2. **5.7 사건 재현**
   - `GlobalExceptionHandler.error()`에서 `.contentType(MediaType.APPLICATION_JSON)`을 지운다.
   - `./mvnw test -Dtest=SpaForwardIntegrationTest#assetsAndApiAreNotPages`
   - 기대: `No value at JSON path "$.code"`로 실패. 되돌린다.

3. **검증 메시지 따라가기**
   - 테스트 전용 `support/TestErrorController.TitleRequest`의 `@NotBlank(message = ...)` 문장을 바꾸고 `GlobalExceptionHandlerTest#validationFailureHasFieldErrors`를 돌린다. 어디서 문장이 응답까지 오는지 `handleBind`를 따라가 본다.

4. **내부 정보가 숨겨지는지**
   - `./mvnw test -Dtest=GlobalExceptionHandlerTest#unexpectedErrorHidesInternals`를 돌리고 콘솔 로그에서 `select * from secret-table`을 찾는다. 로그에는 있고 응답에는 없다.

5. **디버거로 흐름 보기**
   - IntelliJ에서 `DispatcherServlet.doDispatch`, `CurrentBlogArgumentResolver.resolveArgument`, `GlobalExceptionHandler.handleBusiness`에 중단점을 걸고 `CurrentBlogIntegrationTest#platformOrUnknownAddressIsNotFound`를 디버그 실행한다. 호출 스택(Frames)에서 3.3 그림의 단계를 찾아본다.

## 9. 확인 문제

1. `JwtAuthenticationFilter`에서 던진 예외를 `GlobalExceptionHandler`가 잡지 못하는 이유는?
   <details><summary>답</summary>필터는 DispatcherServlet 밖(앞)에서 실행된다. @ExceptionHandler는 DispatcherServlet 안의 HandlerExceptionResolver가 처리하므로 필터의 예외에는 닿지 않는다.</details>

2. `@Idempotent` 확인을 필터가 아니라 인터셉터로 만든 이유는?
   <details><summary>답</summary>어떤 컨트롤러 메서드가 요청을 맡는지, 그 메서드에 @Idempotent가 붙었는지는 HandlerMapping이 핸들러를 정한 뒤에야 알 수 있다. 인터셉터의 preHandle은 그 handler(HandlerMethod)를 받는다.</details>

3. `MethodArgumentNotValidException`용 핸들러를 따로 만들지 않았는데도 `@Valid @RequestBody` 실패가 400 fieldErrors로 나오는 이유는?
   <details><summary>답</summary>MethodArgumentNotValidException은 BindException의 하위 클래스라서 BindException 핸들러가 함께 처리한다.</details>

4. `/api/posts/abc`(id 자리에 글자)를 부르면 어떤 예외가 나고 응답은 무엇인가?
   <details><summary>답</summary>MethodArgumentTypeMismatchException. 400 VALIDATION_FAILED, fieldErrors에 {field: "id", reason: "형식이 올바르지 않습니다."}.</details>

5. 오류 응답에 `contentType(APPLICATION_JSON)`을 미리 정하면 무엇이 달라지나?
   <details><summary>답</summary>Spring이 Accept 헤더로 형식을 협상하지 않고 정해진 JSON으로 쓴다. Accept가 text/html이어도 JSON 본문이 나간다.</details>

6. 500 응답에 예외 메시지를 넣으면 안 되는 이유 두 가지는?
   <details><summary>답</summary>(1) SQL, 클래스 이름, 라이브러리 버전 같은 내부 정보가 공격 단서가 된다. (2) 사용자에게 뜻 없는 기술 문장이 보인다. 상세는 서버 로그에 남기고 응답은 정해진 문장만 준다.</details>

7. 401과 403의 차이를 이 프로젝트 예로 설명하라.
   <details><summary>답</summary>401은 누구인지 모를 때(비회원이 로그인 필요한 API를 부름, /api/admin/**에 비로그인 접근). 403은 누구인지는 알지만 권한이 없을 때(일반 회원이 /api/admin/** 접근, 남의 블로그 설정 변경, CSRF 헤더 없음, 정지 회원).</details>

8. `ErrorResponse`에 `@JsonInclude(NON_NULL)`이 없으면 404 응답 JSON은 어떻게 보이나?
   <details><summary>답</summary>{"code":"NOT_FOUND","message":"요청한 내용을 찾을 수 없습니다.","fieldErrors":null,"detail":null}처럼 null 필드가 함께 나간다.</details>

## 10. 더 읽을거리

- Spring Framework Reference, Web Servlet 장 — DispatcherServlet, Interception, Exceptions(`@ExceptionHandler`), Validation, Content Negotiation: https://docs.spring.io/spring-framework/reference/web/webmvc.html
- Spring Boot Reference, "Servlet Web Applications" — Error Handling(`/error`, `server.error.*`)
- Jakarta Bean Validation 명세와 Hibernate Validator 문서 — 제약 애노테이션 목록
- MDN Web Docs, HTTP response status codes: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status
- MDN Web Docs, Content negotiation: https://developer.mozilla.org/en-US/docs/Web/HTTP/Content_negotiation
- 이 저장소: [contracts/rest-api.md](../../contracts/rest-api.md) "오류 본문", "상태 코드 순서"
