# 모듈 경계: 서비스를 나누지 않고 경계를 지키는 법 (모듈러 모놀리스, 공개 입구, ArchUnit)

> 관련 스텝: [스텝 19b](../../스텝-19b.md) (T114, T115) · 관련 개념: [Spring Boot 기본](../1-개발-환경과-배포/01-Spring-Boot-기초.md), [Spring Security 필터 체인](../3-보안/04-Spring-Security-필터-체인.md), [JWT](../3-보안/03-JWT-로그인-토큰.md), [가입과 로그인](../3-보안/08-가입-로그인-로그아웃.md), [시도 횟수 제한](../3-보안/10-시도-횟수-제한과-기기-쿠키.md), [계층 구조와 DTO](./03-계층-구조와-DTO.md)

## 1. 이 문서로 배우는 것

- 코드를 나누는 세 가지 크기: **패키지**, **빌드 모듈**(Maven 멀티 모듈), **서비스**(MSA). 각각 무엇을 얻고 무엇을 내주나
- 이 프로젝트가 서비스 분리(인증 서버 + 게이트웨이)와 멀티 모듈 대신 **모듈러 모놀리스**를 고른 이유
- **경계**와 **공개 입구**(public API): 바깥에 내주는 것과 숨기는 것을 나누기
- 흩어진 판단을 한 곳으로 모으기: 본인 확인(`CredentialService`), 로그인 끝내기(`LoginSessions`)
- **ArchUnit**: 컴파일러가 막지 않는 약속(패키지 경계, 계층 방향)을 테스트로 지키기. 바이트코드를 읽는다는 것의 의미(상수는 잡히지 않는다)

## 2. 왜 필요한가

이 프로젝트에는 처음부터 규칙이 있었다. "기능 패키지 안은 presentation → application → domain 한 방향, 여럿이 같이 쓰는 것은 `global/`"(CLAUDE.md). 그런데 이것은 **약속**일 뿐이었다. 누가 서비스에서 컨트롤러의 클래스를 import해도 빌드는 된다. 약속은 사람이 바쁘거나 모르면 깨진다.

인증 코드도 그랬다. 스텝 19b 전에는:

- 토큰 발급·검증, 토큰 저장소, 로그인 쿠키, 인증 필터 같은 **인증의 속**이 인증 기능(`auth/`)이 아니라 "여럿이 같이 쓰는 곳"(`global/auth/`)에 있었다. 폴더만 보고는 어디까지가 인증인지 알 수 없었다.
- 비밀번호 확인이 **두 곳에** 있었다. 비밀번호 변경(`MeService`)과 회원 탈퇴(`WithdrawalService`)가 각자 비밀번호 해시 도구(`PasswordEncoder`)와 시도 횟수 제한(`AttemptLimiter`)을 직접 불렀다. 스텝 19에서 탈퇴를 만들 때는 "비밀번호 변경과 **같은 횟수 제한 키**를 써야 우회로가 안 생긴다"를 기억해서 문자열 `"password-change:"`를 일부러 맞춰 썼다. 기억에 기대는 규칙이었다.
- 회원 화면(`MeController`)이 탈퇴 뒤 로그인 쿠키 관리자를 직접 불러 쿠키를 지웠다. 그래서 회원 기능이 쿠키 구조를 알아야 했다.

스텝 20에서 비밀번호 재설정, 기기 쿠키, 카카오·구글 로그인이 한꺼번에 들어온다. 그 전에 인증의 경계를 정리하고, 경계를 **테스트가 지키게** 했다.

## 3. 기본 개념

### 3.1 코드를 나누는 세 가지 크기

| 크기 | 무엇 | 경계를 지키는 것 | 얻는 것 | 내주는 것 |
| --- | --- | --- | --- | --- |
| 패키지 | `com.nhnacademy.blog.auth` 같은 폴더 | 사람의 약속(+ 테스트) | 거의 공짜 | 약속만으로는 깨지기 쉬움 |
| 빌드 모듈 | Maven 멀티 모듈(`blog-core`, `blog-api` …), jar가 여럿 | 컴파일러(의존을 선언하지 않은 모듈은 import 자체가 안 됨) | 강한 경계, 배치처럼 따로 실행할 묶음 | 빌드 설정, 실행 명령, 테스트 구성이 복잡해짐 |
| 서비스 | 따로 배포하는 서버(인증 서버, 게이트웨이, 블로그 서버) | 네트워크(서로 HTTP로만 부름) | 팀별 배포, 따로 늘리기, 장애 격리, 다른 기술 | 네트워크 지연·실패, 데이터 나누기, 배포·운영·테스트가 크게 늘어남 |

크기가 클수록 경계는 강해지지만 비용도 커진다. 그래서 "어느 크기가 맞나"는 **얻으려는 것이 무엇인가**로 정한다.

### 3.2 서비스로 나누면 안 되는 경우: 분산 모놀리스

서비스를 나누는 진짜 이유는 대개 넷이다. 팀이 여럿이라 따로 배포하고 싶을 때, 한쪽만 많이 늘려야 할 때, 한쪽이 죽어도 다른 쪽은 살아야 할 때, 기술이 달라야 할 때. 이 프로젝트는 하나도 해당하지 않는다(개발자 한 명, 배포 한 번, 작은 트래픽, 같은 Spring Boot).

게다가 회원 표(`member`)를 인증(비밀번호·상태)과 블로그(닉네임, 작성자, 정지면 블로그 숨김)가 함께 쓴다. 서버만 나누고 DB를 같이 쓰면 **분산 모놀리스**가 된다. 경계는 없는데 네트워크 비용과 장애 지점만 늘어나는, MSA에서 가장 피하라는 모양이다. 명세의 "정지하면 다음 요청부터 막힌다"(ADMIN-02)는 결국 회원 상태를 봐야 해서, 게이트웨이의 토큰 검사만으로도 끝나지 않는다.

### 3.3 모듈러 모놀리스

**실행은 하나(모놀리스), 안은 경계가 분명한 모듈들.** 이 정도 규모에서 실무가 권하는 모양이다. 경계가 이미 있으면 나중에 정말 떼어 낼 일이 생겨도 쉽다. 반대로 경계가 없는 코드를 서비스로 떼려면 먼저 경계부터 만들어야 한다.

모듈마다 두 가지를 나눈다.

- **공개 입구**(public API): 바깥이 써도 되는 것. 적고, 바뀌지 않게 지킨다.
- **속**(internals): 모듈 안에서만 쓰는 것. 마음대로 바꿔도 바깥이 깨지지 않는다.

Thymeleaf 프로젝트로 비유하면, 서비스의 public 메서드는 다른 컨트롤러가 불러도 되는 입구이고, 서비스 안의 private 메서드는 속이다. 이것을 클래스 하나가 아니라 **패키지 묶음** 단위로 하는 것이다. Java의 `private`·`package-private`은 패키지 하나까지만 막아 줘서, 여러 하위 패키지(`auth.application`, `auth.presentation` …)로 된 모듈은 언어만으로 지킬 수 없다. 그래서 테스트로 지킨다(3.4).

### 3.4 ArchUnit: 구조 규칙을 테스트로

ArchUnit은 컴파일된 클래스(바이트코드)를 읽어 "어느 클래스가 어느 클래스에 기대나"를 그래프로 만들고, 규칙을 어긴 곳을 찾아 테스트를 실패시키는 라이브러리다. JUnit 테스트처럼 돌아서 `./mvnw test`에 끼어든다.

```java
noClasses().that().resideInAPackage("..domain..")
        .should().dependOnClassesThat().resideInAnyPackage("..application..", "..presentation..")
```

- `..domain..`의 `..`은 "아무 패키지나"다. `com.nhnacademy.blog.post.domain`, `com.nhnacademy.blog.auth.domain` 모두 해당한다.
- 규칙은 영어 문장처럼 읽힌다: "domain에 있는 어떤 클래스도 application·presentation에 있는 클래스에 기대면 안 된다".
- **바이트코드를 읽는다**는 것이 중요하다. 소스의 import가 아니라 실제로 컴파일된 참조를 본다. 그래서 import 없이 전체 이름(`com.nhnacademy...AuthCookieManager`)으로 써도 잡힌다. 반대로 **`static final` 상수**(문자열·숫자)는 컴파일러가 값을 복사해 넣어 참조가 남지 않으므로 잡히지 않는다(5.5에서 직접 확인).

## 4. 동작 원리

**정리 전과 후의 의존**

```
정리 전
  member.application.MeService ──► PasswordEncoder, AttemptLimiter("password-change:"), PasswordRule
  member.application.WithdrawalService ──► PasswordEncoder, AttemptLimiter("password-change:")   ← 같은 판단 두 벌
  member.presentation.MeController ──► global.auth.AuthCookieManager.clear()                      ← 쿠키 구조를 앎
  global.web.VisitorKeys ──► global.auth.AuthProperties                                           ← 인증 설정 전체를 앎
  global/auth/ = 입구(LoginMember …) + 속(토큰·쿠키·필터 …)이 한 폴더

정리 후
  member.application.MeService ─────────► auth.application.CredentialService.changePassword
  member.application.WithdrawalService ─► auth.application.CredentialService.verifyCurrentPassword
  member.presentation.MeController ─────► auth.presentation.LoginSessions.end
  global.web.VisitorKeys ───────────────► @Value("${app.auth.cookie-secure}") 값 하나
  global/auth/ = 입구만(LoginMember, LoginMembers, BlogOwnerGuard, SuspensionDetail(s))
  auth/domain       TokenStore, TokenClaims, TokenType, IssuedToken (+ 원래 있던 EmailVerification, PasswordRule …)
  auth/application  JwtTokenProvider, AttemptLimiter, AttemptLimitProperties, AuthProperties, CredentialService (+ AuthService …)
  auth/presentation AuthCookieManager, JwtAuthenticationFilter, CsrfHeaderFilter, LoginSessions (+ AuthController …)

  ArchitectureTest: "auth·global.config 밖에서 auth의 속 금지", "PasswordEncoder 금지", "계층 한 방향"
```

**보안 설정은 예외다.** 필터를 Spring Security에 끼우는 `global/config/SecurityConfig`는 인증의 속(필터, 쿠키 관리자, 토큰 도구)을 알아야 한다. 조립하는 곳은 조립되는 부품을 아는 것이 자연스럽다. 그래서 규칙에서 `global.config`를 함께 빼 두었다.

**옮긴 클래스는 세 계층 규칙대로 나눴다.** 값과 저장소(토큰 내용, 토큰 저장소)는 domain, 동작(토큰 발급·검증, 시도 횟수 제한, 본인 확인)은 application, HTTP를 다루는 것(쿠키, 필터)은 presentation이다. 옮긴 뒤에도 계층 방향 규칙이 통과하는 것을 테스트가 확인한다.

## 5. 이 프로젝트에서는

### 5.1 본인 확인을 한 곳에: `auth/application/CredentialService`

```java
public void verifyCurrentPassword(Member member, String rawPassword, Supplier<BusinessException> mismatch) {
    attemptLimiter.attempt(key(member), () -> {
        if (rawPassword == null || member.getPasswordHash() == null
                || !passwordEncoder.matches(rawPassword, member.getPasswordHash())) {
            throw mismatch.get();
        }
        return null;
    }, e -> true);
}

public void changePassword(Member member, String currentPassword, String newPassword) {
    if (!hasPassword(member)) {
        throw new BusinessException(ErrorCode.FORBIDDEN);
    }
    verifyCurrentPassword(member, currentPassword,
            () -> BusinessException.invalidField("currentPassword", "지금 비밀번호가 맞지 않습니다."));
    PasswordRule.check("newPassword", newPassword);
    member.changePassword(passwordEncoder.encode(newPassword));
}

private static String key(Member member) {
    return "password-change:" + member.getId();
}
```

- 횟수 제한 키를 만드는 곳이 `key()` 하나다. 이제 탈퇴 화면이든 비밀번호 변경이든 **같은 함수를 부르면 같은 횟수**를 쓴다. 기억할 필요가 없다.
- 틀렸을 때 어떤 오류를 낼지는 **부르는 쪽이 정한다**(`Supplier<BusinessException> mismatch`). 비밀번호 변경은 400(어느 칸이 틀렸는지), 탈퇴는 401 `LOGIN_FAILED`(본인 확인 실패, API 명세)다. 판단은 하나, 응답은 쓰임새대로다.
- `Supplier`는 "필요할 때 만들어 주는 함수"다. 맞으면 오류 객체를 아예 만들지 않는다.

부르는 쪽은 짧아졌다.

```java
// MeService
public void changePassword(Long memberId, String currentPassword, String newPassword) {
    credentialService.changePassword(member(memberId), currentPassword, newPassword);
}

// WithdrawalService
private void confirm(Member member, String password) {
    credentialService.verifyCurrentPassword(member, password, () -> new BusinessException(ErrorCode.LOGIN_FAILED));
}
```

### 5.2 로그인 끝내기: `auth/presentation/LoginSessions`

```java
public void end(HttpServletRequest request, HttpServletResponse response) {
    cookieManager.logout(request, response);
}
```

- 로그아웃과 같은 일을 한다: 지금 Access 토큰을 막고(Redis 차단 목록), Refresh 토큰을 지우고, 쿠키를 지운다.
- 정리 전 탈퇴는 **쿠키만** 지웠다. 그래서 탈퇴 직전에 복사해 둔 쿠키로 요청하면, 토큰 자체는 살아 있었다(인증 필터가 탈퇴 회원을 비회원으로 돌려보내긴 했다). 이제 토큰도 막힌다. 입구를 하나로 모으면서 tasks T108의 "쿠키·토큰 무효화"가 글자 그대로 맞게 됐다. 동작이 바뀐 곳은 이 하나다(더 안전한 쪽으로).
- 쿠키를 다루므로 presentation에 둔다. 회원 기능의 presentation(`MeController`)이 부른다. presentation → presentation이지만 **다른 기능의 공개 입구**라 경계 규칙에 맞다.

### 5.3 설정 값 하나만: `global/web/VisitorKeys`

방문자 쿠키(`visitor_id`)는 로그인 쿠키와 같은 Secure 설정을 쓴다. 정리 전에는 이 값 하나를 얻으려고 인증 설정 전체(`AuthProperties`, JWT 비밀키 포함)를 주입받았다.

```java
public VisitorKeys(DomainProperties domainProperties, @Value("${app.auth.cookie-secure}") boolean cookieSecure) {
```

필요한 것만 받으면 인증 설정의 구조가 바뀌어도 이 클래스는 상관없다. "아는 것을 최소로"(최소 지식)라는 경계의 기본 원칙이다.

### 5.4 경계 테스트: `src/test/.../ArchitectureTest`

```java
@AnalyzeClasses(packages = "com.nhnacademy.blog", importOptions = ImportOption.DoNotIncludeTests.class)
class ArchitectureTest {

    private static final String AUTH = "com.nhnacademy.blog.auth..";
    private static final String SECURITY_CONFIG = "com.nhnacademy.blog.global.config..";

    @ArchTest
    static final ArchRule authInternalsStayInsideAuth = noClasses()
            .that().resideOutsideOfPackages(AUTH, SECURITY_CONFIG)
            .should().dependOnClassesThat(resideInAPackage(AUTH)
                    .and(not(belongToAnyOf(CredentialService.class, LoginSessions.class))))
            .because("인증의 속은 auth 안에만 둔다. …");

    @ArchTest
    static final ArchRule passwordHashingStaysInsideAuth = noClasses()
            .that().resideOutsideOfPackages(AUTH, SECURITY_CONFIG)
            .should().dependOnClassesThat().areAssignableTo(PasswordEncoder.class)
            .because("비밀번호 확인·바꾸기는 auth의 CredentialService가 한다 (스텝 19b)");

    @ArchTest static final ArchRule domainDoesNotKnowUpperLayers = …;
    @ArchTest static final ArchRule applicationDoesNotKnowPresentation = …;
}
```

- `@AnalyzeClasses`가 패키지 아래 클래스를 한 번 읽어 두고, `@ArchTest`가 붙은 규칙마다 테스트 하나를 만든다(규칙 4개 = 테스트 4개).
- `ImportOption.DoNotIncludeTests`: 테스트 코드는 검사하지 않는다. 테스트는 로그인 쿠키를 직접 만드는 등 속을 들여다봐도 된다.
- 첫 규칙의 뜻: "auth와 보안 설정 밖의 클래스는, auth 패키지의 클래스 중 공개 입구 둘(`CredentialService`, `LoginSessions`)이 **아닌** 것에 기대면 안 된다". `resideInAPackage(AUTH).and(not(...))`처럼 조건을 이어 붙인다.
- `.because(...)`의 문장은 실패 메시지에 그대로 나온다. 규칙을 어긴 사람이 "왜"를 바로 읽게 한다.
- `global.auth`의 입구(`LoginMember` 등)는 `auth` 패키지가 아니므로 이 규칙과 상관없이 어디서나 쓴다.
- DB도 Spring도 띄우지 않아서 1초 남짓이면 끝난다.

### 5.5 규칙이 정말 잡는지 확인하기

규칙이 늘 통과하면 "규칙이 아무것도 안 잡는 것"일 수도 있다. 일부러 어겨 보았다.

1. `MeService`에 `private static final Class<?> PROBE = AuthCookieManager.class;`를 넣었다 → `authInternalsStayInsideAuth`와 `applicationDoesNotKnowPresentation` **두 규칙이 실패**했다(application이 presentation 클래스를 참조했으므로 계층 규칙에도 걸린다).
2. `PasswordEncoder.class` 참조를 넣었다 → `passwordHashingStaysInsideAuth` 실패.
3. 처음에는 `private static final String PROBE = AuthCookieManager.ACCESS_COOKIE;`(문자열 상수)로 시험했는데 **잡히지 않았다**. `static final` 문자열은 컴파일러가 값(`"access_token"`)을 그대로 복사해 넣어서, 컴파일된 `MeService`에는 `AuthCookieManager`를 가리키는 흔적이 없다. ArchUnit은 바이트코드를 읽으므로 볼 수 없다. 상수 공유는 이 규칙의 빈틈이라는 것을 알고 쓴다(쿠키 이름 같은 상수를 바깥에서 써야 하면 입구 메서드로 내준다).

시험한 코드는 되돌렸다.

### 5.6 옮긴 것과 그대로인 것

- 패키지 선언과 import만 바뀌었다. 클래스 이름, 메서드, 동작은 그대로다. `git mv`로 옮겨 Git 이력이 이어진다(`git log --follow`로 옛 경로의 이력도 본다).
- 인증의 속을 시험하던 테스트 셋(시도 횟수 제한, 인증, 30분 만료)도 `test/.../global/auth`에서 `test/.../auth`로 옮겼다.
- 학습 문서의 파일 경로(`global/auth/JwtAuthenticationFilter` 등 11개 클래스)를 새 경로로 고쳤다. 옛 스텝 노트도 지금 파일을 열 수 있게 했다.
- 테스트는 정리 전 363개 + 경계 4개 = 367개가 모두 통과했다. 동작이 그대로인지는 이 테스트들이 지켜 준다.

## 6. 자주 하는 실수와 함정

- **"나중에 MSA로 갈 거니까" 지금 서비스를 나눈다.** 나눌 이유(팀·배포·확장·장애 격리)가 없으면 비용만 온다. 경계를 먼저 만들면 나중에 떼기 쉽다.
- **서버만 나누고 DB를 같이 쓴다.** 분산 모놀리스. 경계는 그대로 없고 네트워크만 끼어든다.
- **공통(`global`, `common`) 폴더에 아무거나 넣는다.** "여럿이 쓴다"는 이유로 한 기능의 속까지 들어가면, 그 기능의 경계가 사라진다. 공통에는 정말 공통인 것(오류 형식, 페이지 값)과 **입구**만 둔다.
- **같은 판단을 두 곳에 둔다.** 한쪽만 고치면 둘이 달라진다(횟수 제한 키를 맞춰 써야 했던 일). 판단은 하나, 응답 모양은 부르는 쪽이 정하게 한다(5.1의 `Supplier`).
- **설정 객체를 통째로 주입받는다.** 값 하나가 필요하면 값 하나만.
- **규칙 테스트가 통과하는 것만 보고 믿는다.** 일부러 어겨서 실패하는지 본다(5.5).
- **ArchUnit이 상수도 잡는다고 믿는다.** `static final` 상수는 값이 복사되어 잡히지 않는다.
- **예외를 너무 넓게 둔다.** `global..` 전체를 예외로 두면 규칙이 무의미해진다. 조립하는 곳(`global.config`)만 뺀다.

## 7. 직접 해 보기

### 7.1 규칙 어겨 보기 (연습 브랜치)

```java
// member/application/MeService.java 맨 위 필드로 넣어 보기
private static final Class<?> PROBE = com.nhnacademy.blog.auth.domain.TokenStore.class;
```

```bash
./mvnw test -Dtest=ArchitectureTest
```

실패 메시지에서 `Rule '…' was violated (1 times)`와 `.because(...)`의 문장, 어긴 위치(`Field <…MeService.PROBE> …`)를 찾아본다. 같은 자리에 `AuthCookieManager.ACCESS_COOKIE` 문자열 상수를 넣으면 왜 통과하는지 생각해 본다.

### 7.2 규칙 더해 보기

"`comment` 기능의 클래스는 `post.presentation`에 기대지 않는다" 같은 규칙을 한 줄 더 써 보고, 지금 코드가 통과하는지 본다.

### 7.3 이력 따라가기

```bash
git log --follow --oneline -- src/main/java/com/nhnacademy/blog/auth/presentation/JwtAuthenticationFilter.java
```

옮기기 전(`global/auth/`) 커밋까지 이어지는지 본다.

### 7.4 화면

로그인 → 마이페이지 비밀번호 변경(틀린 지금 비밀번호 → "지금 비밀번호가 맞지 않습니다.") → 로그아웃 → 로그인 → 회원 탈퇴. 모두 스텝 19와 같이 동작해야 한다.

## 8. 확인 문제

1. 인증을 별도 서비스(인증 서버 + 게이트웨이)로 나누지 않은 이유를 이 프로젝트의 사정으로 두 가지 말해 보라.
<details><summary>답</summary>나눌 이유(팀별 배포, 따로 늘리기, 장애 격리, 다른 기술)가 없다. 회원 표를 인증과 블로그가 함께 써서 서버만 나누면 DB를 같이 쓰는 분산 모놀리스가 된다. 정지하면 다음 요청부터 막아야 해서 게이트웨이의 토큰 검사만으로 끝나지 않는다는 것도 이유다.</details>

2. Java의 `private`·`package-private`만으로 `auth` 모듈의 경계를 지킬 수 없는 이유는?
<details><summary>답</summary>package-private은 패키지 하나까지만 막는다. auth 모듈은 auth.domain, auth.application, auth.presentation처럼 여러 패키지라, 모듈 안에서 서로 쓰려면 public이어야 하고 그러면 바깥에서도 쓸 수 있다. 그래서 ArchUnit 같은 테스트나 빌드 모듈로 지킨다.</details>

3. `CredentialService.verifyCurrentPassword`가 오류를 직접 정하지 않고 `Supplier<BusinessException>`을 받는 이유는?
<details><summary>답</summary>판단(맞나, 횟수 제한)은 하나로 두고, 틀렸을 때의 응답은 쓰임새마다 다르기 때문이다. 비밀번호 변경은 400(currentPassword 칸), 탈퇴는 401 LOGIN_FAILED다. Supplier라 맞을 때는 오류 객체를 만들지도 않는다.</details>

4. 규칙 테스트에 `static final String` 상수 참조를 넣었더니 통과했다. 왜인가?
<details><summary>답</summary>ArchUnit은 바이트코드를 읽는데, static final 상수는 컴파일러가 값을 복사해 넣어서 그 클래스를 가리키는 참조가 남지 않는다. 클래스 참조(.class, 필드 타입, 메서드 호출)는 남아서 잡힌다.</details>

5. 탈퇴 처리에서 이번에 동작이 바뀐 곳은 무엇이고 왜 바뀌었나?
<details><summary>답</summary>전에는 쿠키만 지웠고, 이제 LoginSessions.end가 로그아웃처럼 Access 토큰을 막고 Refresh 토큰을 지운 뒤 쿠키를 지운다. 로그인 끝내기를 인증의 입구 하나로 모으면서 로그아웃과 같은 일을 하게 됐다(T108의 "쿠키·토큰 무효화"에 맞음).</details>

## 9. 더 읽을거리

- ArchUnit 사용자 가이드: https://www.archunit.org/userguide/html/000_Index.html
- Spring Modulith 레퍼런스(Spring의 모듈러 모놀리스 도구, 이 프로젝트는 쓰지 않았지만 같은 생각): https://docs.spring.io/spring-modulith/reference/
- Martin Fowler, "MonolithFirst": https://martinfowler.com/bliki/MonolithFirst.html
- Martin Fowler, "Microservice Premium"(서비스 분리에 드는 비용): https://martinfowler.com/bliki/MicroservicePremium.html
- Java 언어 명세, 상수 표현식과 컴파일 시점 상수(왜 상수가 복사되나): https://docs.oracle.com/javase/specs/jls/se21/html/jls-15.html#jls-15.29
