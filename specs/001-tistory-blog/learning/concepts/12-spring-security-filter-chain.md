# Spring Security 필터 체인

> 관련 스텝: [스텝 3](../step-03.md), [스텝 4](../step-04.md)(정지 사유 공유, `@PreAuthorize`를 실제 API에) · 관련 작업: T007, T008, T019, T020, ADMIN-01 · 버전: Spring Boot 4.1.1, Spring Security 7.1

## 1. 이 문서로 배우는 것

- 서블릿 필터가 무엇이고 요청이 컨트롤러에 닿기 전에 어떤 길을 지나는지
- Spring Security의 3단 구조: `DelegatingFilterProxy` → `FilterChainProxy` → `SecurityFilterChain`
- 이 프로젝트에서 실제로 돌아가는 보안 필터 11개와 각각의 역할
- 서블릿 필터들 사이의 순서(보안 체인은 -100, `@Component` 필터는 그 뒤)와 그 결과
- `SecurityContextHolder`, `Authentication`, principal, `GrantedAuthority`(`ROLE_` 접두사)
- URL 단위 권한(`authorizeHttpRequests`)과 메서드 단위 권한(`@PreAuthorize`)
- 401과 403을 정하는 곳(`AuthenticationEntryPoint`, `AccessDeniedHandler`, `@ExceptionHandler`)
- 직접 만든 필터를 끼우는 법과 `@Component`로 등록할 때의 함정
- 이 프로젝트의 `SecurityConfig`, `JwtAuthenticationFilter`, `CsrfHeaderFilter`, `LoginMember`
- (스텝 4) 필터와 로그인 API가 같은 정지 안내를 쓰게 한 `SuspensionDetails`, 실제 API에 붙은 `@PreAuthorize`

**먼저 알면 좋은 것**: [10-http-cookies](./10-http-cookies.md), [11-jwt](./11-jwt.md), Spring 빈과 `@Configuration`/`@Bean`([01-spring-boot-basics](./01-spring-boot-basics.md)), `@RestControllerAdvice`([07-spring-mvc-exception-handling](./07-spring-mvc-exception-handling.md)).

---

## 2. 왜 필요한가

로그인 확인, 권한 확인, 보안 헤더 붙이기를 **컨트롤러마다** 한다고 해 보자.

```java
@GetMapping("/api/admin/members")
public List<MemberResponse> members(HttpServletRequest request) {
    String token = readCookie(request);          // 매번
    Member member = verifyToken(token);          // 매번
    if (member == null) throw new Unauthorized();// 매번
    if (!member.isAdmin()) throw new Forbidden();// 매번
    ...
}
```

- 수십 개 API에 같은 코드가 퍼진다. 하나라도 빼먹으면 구멍이다.
- 컨트롤러가 없는 요청(정적 파일, 없는 주소, 오류 페이지)은 아예 검사를 못 한다.
- 보안 헤더 같은 "모든 응답에 공통인 일"을 넣을 곳이 없다.

그래서 **요청이 컨트롤러에 닿기 전에 반드시 지나가는 관문**에서 한꺼번에 처리한다. 그 관문이 서블릿 필터이고, Spring Security는 보안 관련 필터들을 줄 세워 둔 것이다.

---

## 3. 기본 개념

### 3.1 서블릿 필터

Spring MVC 앱은 Tomcat 같은 서블릿 컨테이너 위에서 돈다. 요청은 이렇게 들어온다.

```
Tomcat ─▶ 필터1 ─▶ 필터2 ─▶ ... ─▶ DispatcherServlet ─▶ 컨트롤러
           ◀────────── 응답은 거꾸로 되돌아 나온다 ──────────
```

필터는 `jakarta.servlet.Filter` 인터페이스를 구현한다.

```java
public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain) {
    // 1) 앞 처리: 요청을 보고, 바꾸고, 막을 수 있다
    if (막아야 함) {
        response.setStatus(403);   // 응답을 직접 쓰고
        return;                    // chain.doFilter를 안 부르면 여기서 끝. 컨트롤러에 안 간다
    }
    chain.doFilter(request, response);   // 2) 다음 필터(결국 컨트롤러)로 넘긴다
    // 3) 뒤 처리: 응답이 돌아온 뒤 할 일
}
```

핵심은 **`chain.doFilter`를 부를지 말지**다. 부르지 않으면 요청은 거기서 끝난다.

### 3.2 Spring Security의 3단 구조

```
Tomcat 필터 목록
 ├─ (순서 -100) DelegatingFilterProxy "springSecurityFilterChain"   ← 서블릿 세계와 Spring 세계를 잇는 다리
 │      │ (Spring 빈에게 위임)
 │      ▼
 │   FilterChainProxy                                                ← Spring Security의 입구
 │      │ 요청에 맞는 SecurityFilterChain을 하나 고른다
 │      ▼
 │   SecurityFilterChain (SecurityConfig에서 만든 것)
 │      ├ DisableEncodeUrlFilter
 │      ├ ...
 │      └ AuthorizationFilter
 ├─ (순서 없음 = 맨 뒤) 우리가 @Component로 만든 필터들
 └─ DispatcherServlet
```

| 이름 | 하는 일 |
| --- | --- |
| `DelegatingFilterProxy` | 서블릿 컨테이너가 아는 평범한 필터. 실제 일은 Spring 빈에게 넘긴다. Spring Boot가 자동으로 등록하고 순서는 `-100`(설정 `spring.security.filter.order`) |
| `FilterChainProxy` | 여러 `SecurityFilterChain` 중 요청에 맞는 **첫 번째** 것을 골라 실행한다. 보안 필터 실행이 끝나면 `SecurityContext`를 정리한다 |
| `SecurityFilterChain` | 보안 필터들의 목록. `HttpSecurity`로 만든다. 이 프로젝트는 하나뿐이고 모든 요청에 맞는다 |

체인을 여러 개 둘 수도 있다(예: `/api/**`용, 화면용). 이 프로젝트는 하나로 충분하다.

### 3.3 이 프로젝트에서 실제로 도는 보안 필터

앱 시작 로그(`DefaultSecurityFilterChain`을 DEBUG로 켜면 보인다)에서 확인한 실제 목록이다.

```
Will secure any request with filters:
 1. DisableEncodeUrlFilter
 2. WebAsyncManagerIntegrationFilter
 3. SecurityContextHolderFilter
 4. HeaderWriterFilter
 5. SecurityContextHolderAwareRequestFilter
 6. CsrfHeaderFilter               ← 우리가 만든 것
 7. JwtAuthenticationFilter        ← 우리가 만든 것
 8. AnonymousAuthenticationFilter
 9. SessionManagementFilter
10. ExceptionTranslationFilter
11. AuthorizationFilter
```

| 필터 | 하는 일 |
| --- | --- |
| DisableEncodeUrlFilter | URL에 세션 ID(`;jsessionid=`)가 붙지 않게 한다 |
| WebAsyncManagerIntegrationFilter | 비동기 요청에서도 `SecurityContext`가 이어지게 한다 |
| SecurityContextHolderFilter | 요청 시작에 `SecurityContext`를 준비하고, 끝나면 비운다 |
| HeaderWriterFilter | 보안 응답 헤더를 붙인다(아래 표) |
| SecurityContextHolderAwareRequestFilter | `request.isUserInRole()` 같은 서블릿 API가 Spring Security와 맞게 동작하게 감싼다 |
| **CsrfHeaderFilter** | 상태를 바꾸는 `/api/` 요청에 `X-Requested-With` 헤더가 없으면 403 |
| **JwtAuthenticationFilter** | 쿠키의 JWT로 회원을 찾아 `SecurityContext`에 넣는다. 정지·탈퇴 확인 |
| AnonymousAuthenticationFilter | 아직 아무도 로그인 처리를 안 했으면 "익명 사용자"(`AnonymousAuthenticationToken`)를 넣는다 |
| SessionManagementFilter | 세션 관련 처리. STATELESS라 할 일이 거의 없다 |
| ExceptionTranslationFilter | 뒤(AuthorizationFilter)에서 던진 보안 예외를 401/403 응답으로 바꾼다 |
| AuthorizationFilter | `authorizeHttpRequests` 규칙으로 이 요청을 허용할지 정한다 |

`.csrf().disable()`, `.formLogin().disable()` 등으로 끈 필터(`CsrfFilter`, `UsernamePasswordAuthenticationFilter`, `LogoutFilter`, `BasicAuthenticationFilter`, `RequestCacheAwareFilter`)는 목록에 없다. 기능을 끄면 필터 자체가 빠진다.

`HeaderWriterFilter`가 붙이는 헤더(개발 서버 응답에서 확인):

```
X-Content-Type-Options: nosniff          ← 브라우저가 Content-Type을 멋대로 추측하지 않게
X-XSS-Protection: 0                      ← 옛 브라우저의 XSS 필터를 끔(오히려 문제를 일으켜서)
Cache-Control: no-cache, no-store, max-age=0, must-revalidate
Pragma: no-cache
Expires: 0                               ← 로그인한 화면이 캐시에 남지 않게
X-Frame-Options: DENY                    ← 다른 사이트가 우리 페이지를 iframe에 넣지 못하게
```

HTTPS에서는 `Strict-Transport-Security`(HSTS)도 붙는다.

### 3.4 서블릿 필터들 사이의 순서

Spring Boot는 `Filter` 타입 빈을 **모두** 서블릿 컨테이너에 등록한다. 순서는 `@Order`나 `Ordered`로 정하고, 정하지 않으면 가장 뒤(`Ordered.LOWEST_PRECEDENCE`)다.

```
순서 -100  DelegatingFilterProxy(보안 체인 전체)
순서 없음  ContentSecurityPolicyFilter(@Component)   ← CSP 헤더
순서 없음  ResponseCachingFilter(@Component)         ← 연타 방지용 응답 저장
           DispatcherServlet
```

**결과**: 보안 체인 안의 필터가 응답을 직접 쓰고 끝내면(예: `CsrfHeaderFilter`의 403, 인증 실패의 401), 뒤에 있는 `ContentSecurityPolicyFilter`까지 요청이 오지 않는다. 그래서 그 응답에는 **CSP 헤더가 없다**. 실제로 확인한 결과:

```
404 (컨트롤러까지 감)     → Content-Security-Policy 있음
403 CSRF_REJECTED (보안)  → Content-Security-Policy 없음, X-Frame-Options 등은 있음(HeaderWriterFilter가 앞이라)
```

이 응답들은 JSON이라 CSP가 없어도 실제 위험은 거의 없다. 모든 응답에 CSP를 붙이고 싶다면 CSP를 Spring Security의 헤더 설정(`http.headers(h -> h.contentSecurityPolicy(...))`)으로 옮겨 `HeaderWriterFilter`가 붙이게 하면 된다.

### 3.5 SecurityContext, Authentication, principal

"지금 이 요청의 사용자는 누구인가"를 담는 그릇이다.

```
SecurityContextHolder            (정적 접근 지점, 기본은 ThreadLocal)
 └─ SecurityContext              (요청 하나의 보안 정보)
     └─ Authentication           (인증 결과)
         ├─ principal            누구인가 → 이 프로젝트: LoginMember(id, role)
         ├─ credentials          비밀번호 등 → 이 프로젝트: null(토큰으로 이미 확인)
         ├─ authorities          권한 목록 → [ROLE_USER] 또는 [ROLE_ADMIN]
         └─ isAuthenticated()    true
```

- **ThreadLocal**: 서블릿 컨테이너는 요청 하나를 스레드 하나로 처리한다. `SecurityContextHolder`는 기본적으로 스레드마다 따로 저장해서, 다른 요청의 사용자와 섞이지 않는다. 요청이 끝나면 `SecurityContextHolderFilter`/`FilterChainProxy`가 비운다(비우지 않으면 스레드 풀에서 그 스레드를 다음 요청이 쓸 때 앞 사람으로 보이는 사고가 난다).
- **GrantedAuthority와 `ROLE_` 접두사**: 권한은 문자열이다. `hasRole("ADMIN")`은 내부에서 `"ROLE_ADMIN"` 권한이 있는지 본다. `hasAuthority("ADMIN")`은 접두사 없이 정확히 `"ADMIN"`을 본다. 그래서 `LoginMember.authorities()`가 `"ROLE_" + role.name()`을 만든다.
- **익명 사용자**: 로그인하지 않으면 `AnonymousAuthenticationFilter`가 principal이 문자열 `"anonymousUser"`이고 권한이 `ROLE_ANONYMOUS`인 `AnonymousAuthenticationToken`을 넣는다. "Authentication이 null"이 아니라는 점에 주의한다.

### 3.6 세션을 만들지 않는다 (STATELESS)

기본 Spring Security는 로그인하면 `HttpSession`에 `SecurityContext`를 저장하고, 다음 요청에서 세션에서 꺼낸다. 이 프로젝트는 쿠키의 JWT로 매 요청 다시 확인하므로 세션이 필요 없다.

```java
.sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
```

`STATELESS`는 Spring Security가 세션을 만들지도, 쓰지도 않게 한다. 매 요청 `JwtAuthenticationFilter`가 `SecurityContext`를 새로 채운다.

### 3.7 URL 단위 권한: authorizeHttpRequests

```java
.authorizeHttpRequests(auth -> auth
        .requestMatchers("/api/admin/**").hasRole("ADMIN")   // 관리자만
        .anyRequest().permitAll())                            // 나머지는 일단 통과
```

- 규칙은 **위에서부터** 처음 맞는 것이 적용된다. `anyRequest()`는 항상 마지막에 둔다.
- `AuthorizationFilter`(체인 맨 끝)가 이 규칙으로 판단한다. 거절이면 예외를 던지고, 바로 앞의 `ExceptionTranslationFilter`가 받아 응답으로 바꾼다.

"나머지는 permitAll"인 이유: 이 서비스는 같은 주소라도 **로그인 여부, 블로그 주인 여부, 글 공개 범위**에 따라 결과가 달라진다. 그런 판단은 URL만으로 할 수 없어서 서비스 계층(가시성 정책, 주인 검사, [16-authorization-visibility](./16-authorization-visibility.md))과 메서드 보안이 맡는다.

### 3.8 메서드 단위 권한: @PreAuthorize

```java
@Configuration
@EnableMethodSecurity            // 이걸 켜야 @PreAuthorize가 동작
public class SecurityConfig { ... }

@GetMapping("/api/test/me")
@PreAuthorize("isAuthenticated()")   // 로그인한 사람만
public Map<String, Object> me(@AuthenticationPrincipal LoginMember member) { ... }
```

- `@PreAuthorize`는 Spring AOP 프록시가 메서드 **호출 직전**에 SpEL 식을 평가한다. 거짓이면 `AuthorizationDeniedException`(Spring Security 6.3부터, `AccessDeniedException`의 하위 클래스)을 던진다.
- 이 예외는 **컨트롤러 안에서** 던져지므로 Spring MVC의 `@ExceptionHandler`가 먼저 잡는다. 필터 체인의 `ExceptionTranslationFilter`까지 가지 않는다. 그래서 "비회원이면 401"을 `GlobalExceptionHandler`가 직접 판단해야 한다(5.5).

### 3.9 401과 403은 누가 정하나

| 상황 | 예외 | 처리하는 곳 | 이 프로젝트 응답 |
| --- | --- | --- | --- |
| URL 규칙 거절 + 익명 | `AccessDeniedException` | `ExceptionTranslationFilter` → `AuthenticationEntryPoint` | 401 `UNAUTHORIZED` |
| URL 규칙 거절 + 로그인함 | `AccessDeniedException` | `ExceptionTranslationFilter` → `AccessDeniedHandler` | 403 `FORBIDDEN` |
| `@PreAuthorize` 거절 | `AuthorizationDeniedException` | `GlobalExceptionHandler` | 익명이면 401, 아니면 403 |
| 서비스에서 주인 아님 | `BusinessException(FORBIDDEN)` | `GlobalExceptionHandler` | 403 |

`ExceptionTranslationFilter`는 `AccessDeniedException`을 받으면 현재 사용자가 익명인지 본다. 익명이면 "로그인부터 해라"(EntryPoint, 401), 아니면 "권한이 없다"(Handler, 403).

### 3.10 OncePerRequestFilter

직접 필터를 만들 때는 `jakarta.servlet.Filter` 대신 Spring의 `OncePerRequestFilter`를 상속하는 경우가 많다.
- 요청 하나에서 **한 번만** 실행되게 보장한다. 서블릿은 한 요청 안에서 forward, include, 오류 처리 dispatch로 필터를 다시 지날 수 있는데, 그때 다시 실행하지 않는다(요청 속성에 "이미 지남" 표시를 남긴다).
- `doFilterInternal(HttpServletRequest, HttpServletResponse, FilterChain)`만 구현하면 되고, 형변환이 필요 없다.
- `shouldNotFilter(request)`를 재정의해 특정 요청을 건너뛸 수 있다(이 프로젝트의 `ResponseCachingFilter`가 POST API만 처리하는 방식).

### 3.11 직접 만든 필터를 체인에 넣기, 그리고 @Component 함정

```java
.addFilterBefore(csrfFilter, AnonymousAuthenticationFilter.class)
.addFilterBefore(jwtFilter, AnonymousAuthenticationFilter.class)
```

- `addFilterBefore(새 필터, 기준 필터 클래스)`: 기준 필터 바로 앞에 넣는다. 같은 기준으로 두 번 넣으면 **먼저 넣은 것이 앞**이다(실제 목록에서 CsrfHeaderFilter → JwtAuthenticationFilter 순서).
- `AnonymousAuthenticationFilter` 앞에 넣는 이유: 우리가 로그인 사용자를 넣기 **전에** 익명 사용자가 들어가면 안 된다. 익명 필터는 "아직 비어 있으면" 익명을 넣으므로, 우리 필터가 먼저 채우면 그대로 둔다.

**함정**: 이 필터들에 `@Component`를 붙이면, Spring Boot가 `Filter` 빈을 서블릿 컨테이너에도 **따로 등록**한다(3.4). 그러면 같은 필터가 보안 체인 안에서 한 번, 체인 밖에서 또 한 번 걸린다. 일반 `Filter`면 두 번 실행되고, `OncePerRequestFilter`는 두 번째를 건너뛰지만 의도하지 않은 등록이 생긴다. 해결책은 둘 중 하나다.
- 빈으로 만들지 않고 `SecurityConfig` 안에서 `new`로 만든다(이 프로젝트의 방식).
- 빈으로 두되 `FilterRegistrationBean`으로 서블릿 등록을 끈다(`setEnabled(false)`).

### 3.12 @AuthenticationPrincipal

```java
public Map<String, Object> me(@AuthenticationPrincipal LoginMember member)
```

`SecurityContext`의 `Authentication.getPrincipal()`을 그대로 꺼내 준다. principal이 `LoginMember`가 아니면(익명 사용자의 `"anonymousUser"` 문자열) **null**을 준다. 그래서 공개 API에서 "비회원이면 null"로 쓸 수 있다.

컨트롤러가 아닌 곳(필터, 인자 해석기)에서는 이 애노테이션을 쓸 수 없으므로 `LoginMembers.current()`를 만들었다(5.4).

---

## 4. 동작 원리: 요청 세 개 따라가기

### 4.1 비회원이 `GET /api/admin/members`

```
SecurityContextHolderFilter : 빈 SecurityContext 준비
HeaderWriterFilter          : 보안 헤더 예약
CsrfHeaderFilter            : GET이라 통과
JwtAuthenticationFilter     : 쿠키 없음 → 아무것도 안 하고 통과
AnonymousAuthenticationFilter: 비어 있으니 AnonymousAuthenticationToken 넣음
ExceptionTranslationFilter  : try { chain.doFilter } catch ...
AuthorizationFilter         : /api/admin/** → hasRole(ADMIN)? 익명은 아님 → AccessDeniedException
ExceptionTranslationFilter  : catch! 익명이네 → AuthenticationEntryPoint
                              → errorResponseWriter.write(UNAUTHORIZED) → 401 JSON
(컨트롤러에 가지 않음)
```

### 4.2 일반 회원이 같은 요청

```
JwtAuthenticationFilter     : 쿠키 JWT 검증 → DB에서 회원 → LoginMember(7, USER), [ROLE_USER] 저장
AnonymousAuthenticationFilter: 이미 있으니 그대로
AuthorizationFilter         : ROLE_ADMIN 없음 → AccessDeniedException
ExceptionTranslationFilter  : 익명 아님 → AccessDeniedHandler → 403 FORBIDDEN JSON
```

### 4.3 비회원이 `@PreAuthorize("isAuthenticated()")` API를 부름

```
... AnonymousAuthenticationToken ...
AuthorizationFilter         : permitAll → 통과
DispatcherServlet → 컨트롤러 프록시
  @PreAuthorize 평가: isAuthenticated()? 익명이라 false → AuthorizationDeniedException
  → ExceptionHandlerExceptionResolver → GlobalExceptionHandler.handleAccessDenied
     익명이네 → 401 UNAUTHORIZED
```

---

## 5. 이 프로젝트에서는

### 5.1 `SecurityConfig`

경로: `src/main/java/com/nhnacademy/blog/global/config/SecurityConfig.java`

```java
@Configuration
@EnableMethodSecurity                                       // @PreAuthorize 켜기
public class SecurityConfig {

    @Bean
    SecurityFilterChain securityFilterChain(HttpSecurity http, AuthCookieManager cookieManager,
                                            JwtTokenProvider tokenProvider, TokenStore tokenStore,
                                            MemberRepository memberRepository,
                                            SuspensionDetails suspensionDetails,          // 스텝 4: 정지 사유 읽기
                                            ErrorResponseWriter errorResponseWriter, AuthProperties authProperties,
                                            Clock clock) throws Exception {
        // 필터는 빈이 아니라 여기서 new로 만든다 (3.11의 함정 회피)
        JwtAuthenticationFilter jwtFilter = new JwtAuthenticationFilter(cookieManager, tokenProvider, tokenStore,
                memberRepository, suspensionDetails, errorResponseWriter, authProperties, clock);
        CsrfHeaderFilter csrfFilter = new CsrfHeaderFilter(errorResponseWriter);

        return http
                .csrf(AbstractHttpConfigurer::disable)            // 기본 CSRF 토큰 끄기 → 헤더 방식으로 대체
                .httpBasic(AbstractHttpConfigurer::disable)       // 브라우저 기본 로그인 창 끄기
                .formLogin(AbstractHttpConfigurer::disable)       // /login 폼 끄기 (React가 화면 담당)
                .logout(AbstractHttpConfigurer::disable)          // /logout 끄기 (스텝 4의 POST /api/auth/logout이 대신함)
                .requestCache(AbstractHttpConfigurer::disable)    // 로그인 후 원래 주소로 돌려보내기 저장 끄기
                .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .authorizeHttpRequests(auth -> auth
                        .requestMatchers("/api/admin/**").hasRole("ADMIN")
                        .anyRequest().permitAll())
                .exceptionHandling(exceptions -> exceptions
                        .authenticationEntryPoint((request, response, e) ->
                                errorResponseWriter.write(response, ErrorCode.UNAUTHORIZED))   // 401 JSON
                        .accessDeniedHandler((request, response, e) ->
                                errorResponseWriter.write(response, ErrorCode.FORBIDDEN)))     // 403 JSON
                .addFilterBefore(csrfFilter, AnonymousAuthenticationFilter.class)
                .addFilterBefore(jwtFilter, AnonymousAuthenticationFilter.class)
                .build();
    }

    @Bean
    PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }
}
```

- `@Bean` 메서드의 매개변수로 다른 빈(`AuthCookieManager` 등)을 받으면 Spring이 넣어 준다.
- 끈 기능들은 서버가 HTML 로그인 화면을 그리는 전통적인 앱에 맞춘 기본값이다. 화면은 React가 그리고 서버는 JSON API만 주므로 필요 없다.
- `requestCache`를 끄는 이유: 기본값은 401 때 원래 요청을 세션에 저장해 로그인 후 되돌려 보내는데, 세션을 안 쓰고 "돌아갈 주소"는 프론트가 `?redirect=`로 관리한다.
- EntryPoint/Handler에서 `ErrorResponseWriter`를 쓰는 이유: 필터 단계는 `@RestControllerAdvice` 밖이라, COM-02 JSON을 직접 써야 한다.

### 5.2 `JwtAuthenticationFilter`

경로: `src/main/java/com/nhnacademy/blog/global/auth/JwtAuthenticationFilter.java` (토큰 부분은 [11-jwt](./11-jwt.md) 5.2)

```java
public class JwtAuthenticationFilter extends OncePerRequestFilter {   // @Component 아님

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        Optional<String> accessCookie = cookieManager.readCookie(request, AuthCookieManager.ACCESS_COOKIE);
        Optional<String> refreshCookie = cookieManager.readCookie(request, AuthCookieManager.REFRESH_COOKIE);
        if (accessCookie.isEmpty() && refreshCookie.isEmpty()) {
            chain.doFilter(request, response);       // 비회원: 아무것도 안 하고 다음으로
            return;
        }
        ... (토큰 → memberId)
        Optional<Member> member = memberId.flatMap(memberRepository::findById);
        if (member.isEmpty() || member.get().isWithdrawn()) {
            cookieManager.clear(response);           // 쓸모없는 쿠키 정리
            chain.doFilter(request, response);       // 비회원으로 계속
            return;
        }

        if (member.get().isSuspendedAt(LocalDateTime.now(clock))) {
            if (isApiRequest(request)) {
                cookieManager.clear(response);
                errorResponseWriter.write(response,
                        new BusinessException(ErrorCode.MEMBER_SUSPENDED, suspensionDetails.of(member.get())));
                return;                              // chain.doFilter를 안 부름 → 여기서 끝
            }
            chain.doFilter(request, response);       // 화면 요청은 비회원으로 그림
            return;
        }

        LoginMember loginMember = new LoginMember(member.get().getId(), member.get().getRole());
        ... (Access 재발급, 무활동 연장)
        UsernamePasswordAuthenticationToken authentication =
                UsernamePasswordAuthenticationToken.authenticated(loginMember, null, loginMember.authorities());
        SecurityContextHolder.getContext().setAuthentication(authentication);   // ← "이 요청은 회원 7번"
        chain.doFilter(request, response);
    }
}
```

읽는 포인트:
- **모든 갈래가 `chain.doFilter`를 부르거나 `return`으로 끝난다.** 정지 회원 API 요청만 응답을 직접 쓰고 끝낸다. 나머지 실패는 "비회원으로 계속"이다. 로그인이 필요한지는 뒤(URL 규칙, `@PreAuthorize`, 서비스)가 판단한다. 필터가 401을 직접 주지 않는 이유는 공개 API(글 읽기)도 같은 필터를 지나기 때문이다.
- `UsernamePasswordAuthenticationToken.authenticated(...)`: 이름과 달리 "아이디·비밀번호 로그인"에만 쓰는 것이 아니라, principal과 권한을 담은 **인증 완료 객체**를 만드는 범용 구현이다. `authenticated` 정적 메서드는 `isAuthenticated() == true`로 만든다.
- 정지 사유는 `moderation_log`의 최신 SUSPEND 행에서 읽어 `detail`에 넣는다(ADMIN-02). 스텝 3에서는 이 필터 안의 private 메서드 `suspensionDetail()`이 읽었고, 스텝 4에서 `SuspensionDetails` 컴포넌트로 옮겼다(5.6).

### 5.3 `CsrfHeaderFilter`

경로: `src/main/java/com/nhnacademy/blog/global/auth/CsrfHeaderFilter.java` (CSRF 개념은 [13-csrf-samesite-cors](./13-csrf-samesite-cors.md))

```java
private static final Set<String> STATE_CHANGING_METHODS = Set.of("POST", "PUT", "PATCH", "DELETE");

protected void doFilterInternal(...) {
    boolean stateChanging = STATE_CHANGING_METHODS.contains(request.getMethod());
    boolean api = request.getRequestURI().startsWith("/api/");
    if (stateChanging && api && !EXPECTED_VALUE.equals(request.getHeader(HEADER))) {
        errorResponseWriter.write(response, ErrorCode.CSRF_REJECTED);   // 403, 여기서 끝
        return;
    }
    chain.doFilter(request, response);
}
```

`JwtAuthenticationFilter`보다 **앞**에 있어서, 헤더가 없는 요청은 토큰 검사나 DB 조회도 하지 않고 바로 거절된다.

### 5.4 `LoginMember`와 `LoginMembers`

```java
/** 로그인한 회원. 컨트롤러에서 @AuthenticationPrincipal LoginMember로 받는다. 비회원이면 null이다. */
public record LoginMember(Long id, Role role) {
    public List<GrantedAuthority> authorities() {
        return List.of(new SimpleGrantedAuthority("ROLE_" + role.name()));   // hasRole("ADMIN")과 짝
    }
}

/** 컨트롤러 밖(필터, 인자 해석기)에서 지금 로그인한 회원을 꺼낸다. */
public final class LoginMembers {
    public static Optional<LoginMember> current() {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (authentication != null && authentication.getPrincipal() instanceof LoginMember member) {
            return Optional.of(member);          // 익명("anonymousUser")이면 여기 안 걸림
        }
        return Optional.empty();
    }
}
```

- principal에 `Member` 엔티티가 아니라 **작은 record**를 넣는다. 엔티티는 JPA 영속성 컨텍스트에 묶여 있어서 요청 내내 들고 다니면 지연 로딩 오류 등 문제가 생기고, 필요한 것은 id와 역할뿐이다.
- `instanceof LoginMember member`는 Java 16+의 패턴 매칭이다(검사와 형변환을 한 번에).

### 5.5 `GlobalExceptionHandler`의 401/403 구분

경로: `src/main/java/com/nhnacademy/blog/global/error/GlobalExceptionHandler.java`

```java
/** 메서드 보안(@PreAuthorize)에 걸림. 비회원이면 로그인 필요(401), 회원이면 권한 없음(403). */
@ExceptionHandler(AccessDeniedException.class)
public ResponseEntity<ErrorResponse> handleAccessDenied(AccessDeniedException e) {
    Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
    boolean anonymous = authentication == null || authentication instanceof AnonymousAuthenticationToken
            || !authentication.isAuthenticated();
    return error(anonymous ? ErrorCode.UNAUTHORIZED : ErrorCode.FORBIDDEN);
}
```

`ExceptionTranslationFilter`가 하는 "익명이면 401, 아니면 403" 판단을 MVC 쪽에서 똑같이 한다(3.8, 4.3). 이 처리기가 없으면 `@ExceptionHandler(Exception.class)`가 잡아 500이 되거나, 모두 403이 된다.

---

### 5.6 (스텝 4) 필터와 API가 같은 정지 안내를 쓰기: `SuspensionDetails`

정지된 회원은 두 곳에서 403 `MEMBER_SUSPENDED`를 받는다.

| 언제 | 어디서 |
| --- | --- |
| 이미 로그인한 쿠키로 API를 부를 때 | `JwtAuthenticationFilter`(필터) |
| 로그인 버튼을 누를 때(비밀번호가 맞은 뒤) | `AuthService.login`(서비스, 스텝 4) |

두 곳의 안내(사유, 사유 문구, 기한)가 같아야 한다. 스텝 3에서는 필터 안 private 메서드에만 있었으므로, 로그인 API를 만들면서 복사하지 않고 **빈 하나로 꺼냈다**.

경로: `src/main/java/com/nhnacademy/blog/global/auth/SuspensionDetails.java`

```java
@Component
public class SuspensionDetails {

    private final ModerationLogRepository moderationLogRepository;
    private final Clock clock;

    public SuspensionDetails(ModerationLogRepository moderationLogRepository, Clock clock) {
        this.moderationLogRepository = moderationLogRepository;
        this.clock = clock;
    }

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

}
```

- `@Component`라 빈이다. 그런데 필터(`JwtAuthenticationFilter`)는 빈이 아니라 `SecurityConfig`에서 `new`로 만든다(3.11). 그래서 필터는 이 빈을 **스스로 주입받지 못하고**, `SecurityConfig`의 `@Bean` 메서드가 매개변수로 받아 생성자에 넘긴다(5.1의 바뀐 부분). 필터가 하던 일이 빈으로 옮겨 가면 이렇게 "설정 클래스가 받아서 넘겨 주는" 줄이 바뀐다.
- `SuspensionDetails` 자체는 서블릿 필터가 아니라 그냥 컴포넌트이므로, `@Component`를 붙여도 3.11의 "필터가 두 번 걸리는" 함정과 상관없다.
- 서비스 쪽: `AuthService`가 생성자로 주입받아 `throw new BusinessException(ErrorCode.MEMBER_SUSPENDED, suspensionDetails.of(member))`로 쓴다([가입과 로그인](./21-signup-login.md)).
- 테스트: `LoginIntegrationTest.suspendedMemberGetsReasonOnlyWithRightPassword`(로그인 쪽), `AuthenticationIntegrationTest`의 정지 회원 테스트(필터 쪽)가 같은 `detail.reason`, `detail.reasonMessage`, `detail.suspendedUntil`을 확인한다.

### 5.7 (스텝 4) `@PreAuthorize`가 실제 API에

스텝 3에는 테스트 전용 `/api/test/me`에만 붙어 있었다. 스텝 4에서 실제 API에 처음 붙었다.

| API | 비회원이 부르면 |
| --- | --- |
| `GET /api/me` (`MeController.me`) | 401. 프론트는 이것으로 로그인 상태를 안다(`allowAnonymous`로 불러 이동하지 않음) |
| `POST /api/auth/logout` (`AuthController.logout`) | 401 (rest-api.md 권한 "회원") |
| `GET /api/blogs/address-availability`, `POST /api/blogs` (`BlogController`) | 401 |

```java
@PostMapping("/api/auth/logout")
@PreAuthorize("isAuthenticated()")
@ResponseStatus(HttpStatus.NO_CONTENT)
public void logout(HttpServletRequest request, HttpServletResponse response) {
    cookieManager.logout(request, response);
}
```

- URL 규칙(`authorizeHttpRequests`)은 `/api/admin/**`만 다루고 나머지는 `permitAll`이다. 그래서 "로그인만 하면 되는" API는 이처럼 메서드에 표시한다. 블로그 **주인**인지는 `@PreAuthorize`가 아니라 `BlogOwnerGuard`가 본다. 블로그를 먼저 찾아야(404) 주인인지 알 수 있기 때문이다([가시성](./16-authorization-visibility.md)).
- 비회원이 걸리면 3.8·5.5대로 `GlobalExceptionHandler`가 401로 바꾼다. 테스트: `SignupIntegrationTest.meIs401ForAnonymous`, `LogoutIntegrationTest.anonymousLogoutIs401`, `BlogCreateIntegrationTest.loginIsRequired`.
- 로그아웃에 `@PreAuthorize`가 있어도 `.logout(disable)` 덕분에 Spring Security 기본 `/logout`과 섞이지 않는다.

## 6. 자주 하는 실수와 함정

1. **커스텀 필터에 `@Component`를 붙인다.** 서블릿 컨테이너에 따로 등록되어 체인 밖에서 한 번 더 걸린다(3.11).
2. **`authorizeHttpRequests`에서 `anyRequest()`를 먼저 쓴다.** 규칙은 위에서부터 맞추므로 뒤의 규칙이 적용되지 않는다(Spring Security는 이 경우 설정 오류를 낸다).
3. **`hasRole("ROLE_ADMIN")`이라고 쓴다.** `hasRole`이 접두사를 붙이므로 `ROLE_ROLE_ADMIN`을 찾게 된다(최근 버전은 오류를 낸다). `hasRole("ADMIN")` 또는 `hasAuthority("ROLE_ADMIN")`.
4. **필터에서 `chain.doFilter`를 빼먹는다.** 응답을 쓰지도 않고 끝내면 빈 200 응답이 나간다.
5. **응답을 쓴 뒤 `chain.doFilter`도 부른다.** 이미 커밋된 응답에 컨트롤러가 다시 쓰려 해서 `IllegalStateException`이 나거나 응답이 섞인다. 응답을 썼으면 반드시 `return`.
6. **`@EnableMethodSecurity`를 빼먹는다.** `@PreAuthorize`가 조용히 무시되고 모두 통과한다. 테스트로 확인해야 하는 이유다.
7. **`@PreAuthorize` 거절이 필터에서 처리된다고 생각한다.** MVC의 `@ExceptionHandler`가 먼저 잡는다. 전역 `Exception` 처리기가 있으면 500이 될 수 있다.
8. **"인증 = null이면 비회원"으로 판단한다.** 익명 필터 뒤에서는 `AnonymousAuthenticationToken`이 들어 있다. `instanceof`로 확인한다.
9. **필터 순서가 응답 헤더에 미치는 영향을 잊는다.** 보안 체인이 끝낸 응답에는 뒤쪽 서블릿 필터의 헤더(이 프로젝트의 CSP)가 붙지 않는다(3.4).
10. **(스텝 4) 필터의 로직을 서비스에 복사한다.** 정지 안내처럼 같은 판단이 필터와 서비스 양쪽에 필요하면 빈으로 꺼내 둘이 함께 쓴다. 복사하면 한쪽만 고쳐져 안내가 달라진다.
11. **(스텝 4) 빈으로 만들지 않은 필터에 `@Autowired`를 기대한다.** `new`로 만든 객체에는 Spring이 주입하지 않는다. 필요한 빈은 `SecurityConfig`가 받아 생성자로 넘긴다.

---

## 7. 직접 해 보기

### 실습 1: 필터 목록 보기

```bash
./mvnw spring-boot:run -Dspring-boot.run.arguments="--logging.level.org.springframework.security.web.DefaultSecurityFilterChain=DEBUG"
```

로그에서 `Will secure any request with filters:`를 찾는다. 3.3의 목록과 같은가? `SecurityConfig`에서 `.formLogin(...disable)` 줄을 지우고 다시 띄우면 어떤 필터가 늘어나는가(`UsernamePasswordAuthenticationFilter` 등)? 확인 후 되돌린다.

### 실습 2: 401, 403, CSRF 403과 헤더

서버를 띄우고:

```bash
curl -i localhost:8080/api/admin/x                     # 401 UNAUTHORIZED
curl -i -X POST localhost:8080/api/anything             # 403 CSRF_REJECTED, CSP 헤더 없음
curl -i localhost:8080/api/anything                     # 404 NOT_FOUND, CSP 헤더 있음
```

세 응답의 헤더를 비교해 3.4의 설명(보안 체인이 끝낸 응답에는 CSP가 없다)을 확인한다.

### 실습 3: 테스트로 확인

```bash
./mvnw test -Dtest=AuthenticationIntegrationTest
```

`adminAreaIsForAdminsOnly`, `stateChangingApiNeedsCsrfHeader`, `anonymousGets401OnLoginRequiredApi`를 읽고, `GlobalExceptionHandler.handleAccessDenied`의 `anonymous ? UNAUTHORIZED : FORBIDDEN`을 항상 `FORBIDDEN`으로 바꾸면 어느 테스트가 깨지는지 예상한 뒤 돌려 본다. 되돌린다.

### 실습 4: @Component 함정 보기

테스트용으로 `jakarta.servlet.Filter`를 직접 구현한 작은 필터(`doFilter`에서 `System.out.println("hit " + request.getRequestURI())` 후 `chain.doFilter`)를 만들고 `@Component`를 붙인다. `SecurityConfig`에서도 `.addFilterBefore(그 필터 빈, AnonymousAuthenticationFilter.class)`로 넣는다. 앱을 띄우고 요청을 한 번 보내면 `hit`이 **두 번** 찍힌다(보안 체인 안에서 한 번, 서블릿 필터로 한 번). `OncePerRequestFilter`를 상속하게 바꾸면 한 번만 찍힌다. 확인 후 지운다.

### 실습 5 (스텝 4): 로그인 API와 필터가 같은 정지 안내를 주는지

```bash
./mvnw test -Dtest='LoginIntegrationTest#suspendedMemberGetsReasonOnlyWithRightPassword,AuthenticationIntegrationTest'
```

`SuspensionDetails.of`의 `reason.getMessage()`를 `"바뀐 문구"`로 바꿔 보면 두 쪽 응답이 함께 바뀐다(테스트는 문구 존재만 보므로 통과한다). 문구가 한 곳에서 정해진다는 것을 확인하고 되돌린다.

### 실습 6: 디버거로 따라가기

IntelliJ에서 `JwtAuthenticationFilter.doFilterInternal` 첫 줄과 `TestApiController.me`에 중단점을 걸고 `loginCookieAuthenticates` 테스트를 디버그 실행한다. 호출 스택(Frames)에서 `FilterChainProxy`, `DelegatingFilterProxy`를 찾아본다.

---

## 8. 확인 문제

1. `DelegatingFilterProxy`와 `FilterChainProxy`는 각각 무엇을 하는가?
<details><summary>답</summary>

`DelegatingFilterProxy`는 서블릿 컨테이너에 등록된 일반 필터로, 실제 처리를 Spring 빈(`springSecurityFilterChain` = `FilterChainProxy`)에 넘기는 다리다. `FilterChainProxy`는 요청에 맞는 `SecurityFilterChain`을 골라 그 안의 보안 필터들을 실행한다.
</details>

2. `JwtAuthenticationFilter`를 `AnonymousAuthenticationFilter` 앞에 넣은 이유는?
<details><summary>답</summary>

익명 필터는 SecurityContext가 비어 있으면 익명 사용자를 넣는다. 우리 필터가 먼저 로그인 사용자를 채워야 익명으로 덮이지 않는다.
</details>

3. `hasRole("ADMIN")`이 확인하는 권한 문자열은?
<details><summary>답</summary>

`ROLE_ADMIN`. 그래서 `LoginMember.authorities()`가 `"ROLE_" + role.name()`을 만든다.
</details>

4. 비회원이 `/api/admin/x`를 부르면 401, 일반 회원이면 403이다. 이 둘을 가르는 곳은?
<details><summary>답</summary>

`ExceptionTranslationFilter`. `AuthorizationFilter`가 던진 `AccessDeniedException`을 받아 사용자가 익명이면 `AuthenticationEntryPoint`(401), 아니면 `AccessDeniedHandler`(403)를 부른다.
</details>

5. `@PreAuthorize("isAuthenticated()")`에 비회원이 걸렸는데 `GlobalExceptionHandler`에 `AccessDeniedException` 처리기가 없다면 어떻게 되는가?
<details><summary>답</summary>

예외가 컨트롤러 안에서 나므로 MVC의 예외 처리가 먼저 잡는다. `@ExceptionHandler(Exception.class)`가 잡아 500 INTERNAL_ERROR가 된다. 그래서 익명이면 401로 바꾸는 처리기를 따로 두었다.
</details>

6. CSRF 헤더가 없는 POST에 대한 403 응답에는 CSP 헤더가 없다. 왜인가?
<details><summary>답</summary>

`CsrfHeaderFilter`는 보안 체인(서블릿 필터 순서 -100) 안에 있고, CSP를 붙이는 `ContentSecurityPolicyFilter`는 `@Component`라 그 뒤에 등록된다. 보안 체인에서 응답을 쓰고 끝내면 뒤 필터까지 가지 않는다.
</details>

7. principal에 `Member` 엔티티 대신 `LoginMember` record를 넣는 이유는?
<details><summary>답</summary>

필요한 것은 id와 역할뿐이고, 엔티티는 영속성 컨텍스트에 묶여 있어 요청 내내 들고 다니면 지연 로딩 오류 등의 문제가 생긴다. 작은 불변 객체가 안전하다.
</details>

8. 필터를 `@Component`로 등록하면 생기는 문제와 해결 방법 두 가지는?
<details><summary>답</summary>

Spring Boot가 Filter 빈을 서블릿 컨테이너에도 등록해 보안 체인 밖에서 한 번 더 걸린다. 해결: 빈으로 만들지 않고 SecurityConfig에서 new로 만들거나, FilterRegistrationBean으로 서블릿 등록을 끈다.
</details>

9. (스텝 4) `JwtAuthenticationFilter`는 `SuspensionDetails` 빈을 어떻게 받나? 왜 그렇게 해야 하나?
<details><summary>답</summary>

`SecurityConfig`의 `securityFilterChain` <code>@Bean</code> 메서드가 매개변수로 빈을 받아 필터 생성자에 넘긴다. 필터는 <code>@Component</code>가 아니라 <code>new</code>로 만들므로(두 번 걸리는 함정 회피) Spring이 직접 주입하지 않기 때문이다.
</details>

10. (스텝 4) `POST /api/blogs`에는 `@PreAuthorize("isAuthenticated()")`를 쓰고, `PATCH /api/blog`(블로그 수정)에는 쓰지 않고 `BlogOwnerGuard`를 쓰는 이유는?
<details><summary>답</summary>

블로그 개설은 "로그인했는가"만 보면 되지만, 블로그 수정은 "이 블로그의 주인인가"를 봐야 하고 그 전에 블로그가 있는지(404)를 먼저 판단해야 한다. `@CurrentBlog`로 블로그를 찾은 뒤 `BlogOwnerGuard`가 401 → 403을 판단해야 상태 코드 순서가 지켜진다.
</details>

---

## 9. 더 읽을거리

- Spring Security 레퍼런스, *Architecture*(DelegatingFilterProxy, FilterChainProxy, SecurityFilterChain, 필터 순서): https://docs.spring.io/spring-security/reference/servlet/architecture.html
- Spring Security 레퍼런스, *Authorize HttpServletRequests*, *Method Security*
- Spring Security 레퍼런스, *Servlet Authentication Architecture*(SecurityContextHolder, Authentication)
- Spring Boot 레퍼런스, *Servlet Web Applications – Servlets, Filters, and Listeners*(Filter 빈 자동 등록)
- 이어서 읽기: [13-csrf-samesite-cors](./13-csrf-samesite-cors.md), [16-authorization-visibility](./16-authorization-visibility.md)
