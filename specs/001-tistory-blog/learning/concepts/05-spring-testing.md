# 05. Spring 테스트: 단위·통합 테스트, MockMvc, Testcontainers

> 관련 스텝: [스텝 1](../step-01.md), [스텝 2](../step-02.md), [스텝 3](../step-03.md), [스텝 9](../step-09.md), [스텝 11](../step-11.md) · 먼저 읽을 것: [01. Spring Boot 기초](./01-spring-boot-basics.md), [04. Docker](./04-docker-compose.md)

## 1. 이 문서로 배우는 것

- **단위 테스트**와 **통합 테스트**의 차이, 언제 무엇을 쓰는지
- `@SpringBootTest`와 **슬라이스 테스트**(`@WebMvcTest` 등), 이 프로젝트에서 `@WebMvcTest`가 깨진 이유
- Spring **테스트 컨텍스트 캐싱**과 `IntegrationTestSupport`를 공통 부모로 둔 이유
- **Testcontainers**와 `@ServiceConnection`
- **MockMvc**로 HTTP 요청을 흉내 내는 법(`perform`, `andExpect`, `jsonPath`, 헤더·쿠키)
- 테스트에서 `@Transactional`의 롤백, DB를 공유할 때 **랜덤 데이터**를 쓰는 이유
- 테스트 전용 컨트롤러(`support` 패키지)와 컴포넌트 스캔
- H2 같은 메모리 DB를 쓰지 않는 이유

**먼저 알면 좋은 것**: JUnit 5의 `@Test`, `assertThat`(AssertJ) 기본, 빈과 DI([01](./01-spring-boot-basics.md)).

---

## 2. 왜 필요한가

테스트가 없다면 "로그인한 회원이 남의 비공개 글을 열면 404인가?"를 확인하려고 매번 서버를 띄우고, 회원 둘을 가입시키고, 글을 쓰고, 브라우저로 열어 봐야 한다. 기능이 늘수록 예전 기능이 깨졌는지 다시 확인하는 일이 감당할 수 없게 커진다.

자동 테스트는 이 확인을 코드로 적어 두고 `./mvnw test` 한 번으로 전부 다시 돌린다. 스텝 3에서 `@WebMvcTest`가 깨진 것, 오류 응답이 `Accept: text/html`일 때 비어 나온 것을 사람이 아니라 테스트가 먼저 찾았다.

다만 테스트도 잘못 만들면 **느리거나**(매번 서버 전체를 띄움), **거짓말을 한다**(운영과 다른 DB에서만 통과). 이 문서는 둘 다 피하는 방법을 다룬다.

---

## 3. 기본 개념

### 3.1 테스트의 종류

| 종류 | 무엇을 | 스프링 | 속도 | 이 프로젝트 예 |
| --- | --- | --- | --- | --- |
| 단위 테스트 | 클래스 하나, 의존성은 가짜나 직접 생성 | 안 띄움 | 밀리초 | `PageQueryTest`, `HtmlSanitizerTest`, `BlogAddressRuleTest`, `BlogHostResolverTest` |
| 슬라이스 테스트 | 한 계층만(웹, JPA 등) | 일부만 | 1~3초 | (처음 `GlobalExceptionHandlerTest`가 `@WebMvcTest`였다가 바뀜) |
| 통합 테스트 | 여러 계층을 실제로 엮어서 | 전부 + 진짜 DB | 첫 번째 ~10초, 이후 빠름 | `AuthenticationIntegrationTest`, `PostVisibilityIntegrationTest` 등 |

**규칙 하나로 결과가 정해지는 로직**(주소 형식, 페이지 번호 검사, HTML 정화)은 단위 테스트로, **여러 부품이 맞물려야 하는 동작**(쿠키 → 필터 → 회원 조회 → 정지 판단 → 403 JSON)은 통합 테스트로 확인한다.

단위 테스트 예 (`src/test/java/com/nhnacademy/blog/global/web/PageQueryTest.java`):

```java
class PageQueryTest {                                  // 스프링 애노테이션이 없다 → 순수 자바
    @Test
    void defaultsToFirstPageAndListSize() {
        PageQuery query = PageQuery.of(null, null, 10);   // 그냥 static 메서드를 부른다
        assertThat(query).isEqualTo(new PageQuery(1, 10));
    }
}
```

### 3.2 `@SpringBootTest`

`@SpringBootTest`는 테스트를 시작할 때 `@SpringBootApplication`을 찾아 **애플리케이션 컨텍스트를 실제와 똑같이** 만든다. 컴포넌트 스캔, 자동 설정, Flyway 실행, JPA validate까지 다 일어난다. 그래서 테스트 클래스에서 아무 빈이나 `@Autowired`로 받을 수 있다.

### 3.3 슬라이스 테스트

`@WebMvcTest`, `@DataJpaTest` 같은 애노테이션은 **한 계층에 필요한 빈만** 골라 컨텍스트를 만든다.

| 애노테이션 | 포함 | 빠지는 것 |
| --- | --- | --- |
| `@WebMvcTest` | `@Controller`, `@ControllerAdvice`, `WebMvcConfigurer`, `HandlerMethodArgumentResolver`, `Filter` 등 웹 계층 | `@Service`, `@Repository`, 일반 `@Component`, 직접 만든 `@Configuration`, DB |
| `@DataJpaTest` | 엔티티, Repository, `EntityManager` | 웹, 서비스 |

빠르고 초점이 좁다는 장점이 있지만, **어떤 빈이 포함되는지 규칙을 알아야** 한다.

### 3.4 MockMvc

서버를 실제 포트로 띄우지 않고, `DispatcherServlet`에 **가짜 HTTP 요청 객체**를 넣어 전체 처리(필터 → 컨트롤러 → 예외 처리 → JSON 변환)를 실행한다.

```java
mockMvc.perform(                                     // 요청 만들기
            get("/api/test/blog")                    //   메서드와 경로
                .header("Host", "alpha.blog.test")   //   헤더
                .cookie(loginCookies))               //   쿠키
       .andExpect(status().isOk())                   // 응답 상태 확인
       .andExpect(jsonPath("$.address").value("alpha"));   // JSON 본문의 값 확인
```

| 요소 | 쓰는 법 |
| --- | --- |
| 요청 | `get`, `post`, `put`, `delete`(정적 import `MockMvcRequestBuilders.*`) |
| 헤더 | `.header("X-Requested-With", "XMLHttpRequest")` |
| 쿠키 | `.cookie(Cookie...)` |
| 본문 | `.contentType(MediaType.APPLICATION_JSON).content("{\"title\":\"\"}")` |
| 쿼리 | `.queryParam("page", "2")` |
| 상태 | `status().isNotFound()`, `.isMovedPermanently()` |
| 헤더 확인 | `header().string("Location", "...")` |
| JSON | `jsonPath("$.code").value("NOT_FOUND")`, `jsonPath("$.detail").doesNotExist()` |
| 응답 꺼내기 | `.andReturn().getResponse().getContentAsString()` |

`jsonPath`의 `$`는 JSON 전체, `$.fieldErrors[0].field`는 "fieldErrors 배열의 첫 항목의 field"다.

### 3.5 Testcontainers와 `@ServiceConnection`

테스트를 시작할 때 Docker로 **진짜 MySQL·Redis**를 새로 띄우고, 테스트가 끝나면 지운다([04](./04-docker-compose.md)).

```java
@Bean
@ServiceConnection                 // 이 컨테이너의 주소·포트·계정을 spring.datasource.*로 연결해 줘
MySQLContainer mysqlContainer() {
    return new MySQLContainer(DockerImageName.parse("mysql:8.4"));
}
```

`@ServiceConnection`이 없던 시절에는 컨테이너 포트를 꺼내 `@DynamicPropertySource`로 `spring.datasource.url`을 직접 넣었다. 지금은 Spring Boot가 컨테이너 종류를 보고 알아서 연결 정보를 만든다. Redis처럼 전용 클래스가 없는 컨테이너는 `GenericContainer`에 `@ServiceConnection(name = "redis")`로 종류를 알려 준다.

### 3.6 H2를 쓰지 않는 이유

H2는 자바로 만든 메모리 DB라 설치 없이 빠르게 뜬다. 하지만:

- 이 프로젝트의 `schema.sql`(V1)에는 MySQL 전용 문법(`GENERATED ALWAYS AS (...) STORED` 계산 컬럼, `COMMENT`, `ON UPDATE CURRENT_TIMESTAMP(6)`)이 있어 H2에서 실행되지 않는다(research.md R-02에서 H2 2.3.232로 확인).
- 실행되더라도 정렬·문자셋·제약 동작이 MySQL과 달라, **H2에서 통과하고 운영 MySQL에서 실패**하는 일이 생긴다.

테스트 DB와 운영 DB를 같게 하는 것이 테스트가 거짓말하지 않게 하는 가장 확실한 방법이다.

---

## 4. 동작 원리

### 4.1 테스트 컨텍스트 캐싱

`@SpringBootTest`로 컨텍스트를 만드는 데는 시간이 든다(이 프로젝트는 컨테이너 시작 포함 약 10초). Spring 테스트 프레임워크는 **설정이 같은 테스트 클래스끼리 컨텍스트를 재사용**한다.

```
"설정"을 이루는 것 (이 중 하나라도 다르면 새 컨텍스트)
- 설정 클래스 (@SpringBootTest가 찾은 BlogApplication)
- @Import 한 클래스 (TestcontainersConfiguration)
- 활성 프로필, @TestPropertySource
- @MockitoBean 같은 빈 교체
- @AutoConfigureMockMvc 같은 컨텍스트 커스터마이저
```

```
테스트 실행 순서              컨텍스트
AuthenticationIntegrationTest  ─ 새로 만듦 (컨테이너 2개 시작, Flyway 실행) ~10초
CurrentBlogIntegrationTest     ─ 같은 설정 → 재사용                          ~0.5초
PostVisibilityIntegrationTest  ─ 재사용                                     ~0.4초
...
```

그래서 모든 통합 테스트가 **같은 부모**를 상속하게 했다(5.1). 어떤 테스트에만 `@Import(다른설정.class)`를 하나 더 붙이면, 그 테스트를 위해 컨텍스트와 **컨테이너가 새로** 뜬다. `TestcontainersConfiguration`의 컨테이너는 빈이라서, 컨텍스트가 하나면 컨테이너도 한 쌍만 뜬다.

### 4.2 `@SpringBootTest`가 테스트 클래스까지 스캔하는 이유

`@SpringBootTest`는 `BlogApplication`의 `@ComponentScan`을 그대로 쓴다. 테스트를 돌릴 때는 `src/test/java`의 클래스도 클래스패스에 있으므로, `com.nhnacademy.blog.support.TestApiController`(`@RestController`) 같은 클래스도 **함께 스캔되어 빈이 된다**. 이것을 이용해 테스트 전용 API를 둔다(5.4).

단, Spring Boot는 스캔할 때 **테스트용 설정이 앱 설정에 섞이지 않게** 몇 가지를 뺀다(`TypeExcludeFilter`).
- `@TestConfiguration`이 붙은 클래스는 스캔에서 빠진다 → `TestcontainersConfiguration`을 `@Import`로 명시적으로 넣는 이유.
- 테스트 클래스 안의 중첩 클래스도 빠진다.

### 4.3 `@Transactional` 테스트

테스트 메서드(또는 클래스)에 `@Transactional`을 붙이면, 테스트가 트랜잭션 안에서 실행되고 **끝나면 커밋하지 않고 롤백**한다. 테스트가 만든 데이터가 DB에 남지 않는다.

```
테스트 시작 → 트랜잭션 시작
  owner, other, blog, post 저장 (INSERT)
  검증
테스트 끝   → 롤백 (INSERT가 모두 취소됨)
```

주의:
- MockMvc 요청은 같은 스레드에서 실행되므로 테스트 트랜잭션에 참여한다. 실제 포트로 띄우는 테스트(`webEnvironment = RANDOM_PORT`)는 요청이 다른 스레드라 롤백되지 않는다.
- 롤백 때문에 **커밋 시점에만 일어나는 일**(DB 제약 일부, 커밋 후 이벤트)은 확인되지 않을 수 있다.
- JPA는 변경을 모았다가 `flush` 때 SQL을 보낸다. 같은 트랜잭션에서 `JdbcTemplate`으로 SQL을 직접 실행하려면 그 전에 `flush`로 JPA 변경을 DB에 보내고, 실행 후 `clear`로 JPA가 들고 있던 옛 객체를 비워야 새 값을 다시 읽는다(5.3).

### 4.4 DB를 공유하는 테스트와 랜덤 데이터

`@Transactional`이 없는 통합 테스트(MockMvc로 로그인 쿠키·Redis까지 확인하는 테스트)는 데이터가 **커밋되어 남는다**. 컨텍스트와 컨테이너를 공유하니 다음 테스트도 그 데이터를 본다. 그래서 회원 이메일, 닉네임, 블로그 주소에 **매번 다른 랜덤 값**을 쓴다. 고정 값(`a@blog.test`)을 쓰면 두 번째 테스트가 UNIQUE 제약에 걸린다. 테스트 실행 순서에 기대지 않게 되는 효과도 있다.

---

## 5. 이 프로젝트에서는

### 5.1 통합 테스트의 공통 부모

`src/test/java/com/nhnacademy/blog/IntegrationTestSupport.java`

```java
@SpringBootTest                                  // 애플리케이션 전체를 띄운다
@AutoConfigureMockMvc                            // MockMvc 빈을 만든다 (보안 필터 포함)
@Import(TestcontainersConfiguration.class)       // 테스트용 MySQL·Redis 컨테이너
public abstract class IntegrationTestSupport {
}
```

모든 통합 테스트는 `class XxxTest extends IntegrationTestSupport`로 시작한다. 설정이 같으니 컨텍스트 하나를 함께 쓴다(4.1).

`src/test/java/com/nhnacademy/blog/TestcontainersConfiguration.java`

```java
@TestConfiguration(proxyBeanMethods = false)     // 테스트 전용 설정. 스캔에서 빠지므로 @Import로 넣는다
public class TestcontainersConfiguration {

    @Bean
    @ServiceConnection                           // → spring.datasource.url/username/password 자동 연결
    MySQLContainer mysqlContainer() {
        return new MySQLContainer(DockerImageName.parse("mysql:8.4"))           // docker-compose와 같은 이미지
                .withCommand("--character-set-server=utf8mb4", "--collation-server=utf8mb4_0900_ai_ci");
    }

    @Bean
    @ServiceConnection(name = "redis")           // → spring.data.redis.host/port 자동 연결
    GenericContainer<?> redisContainer() {
        return new GenericContainer<>(DockerImageName.parse("redis:7.4")).withExposedPorts(6379);
    }
}
```

`application-dev.yml`에는 `localhost:3306`이 적혀 있지만, `@ServiceConnection`이 준 연결 정보가 이겨서 테스트는 개발 DB를 건드리지 않는다.

### 5.2 MockMvc 통합 테스트 예

`src/test/java/com/nhnacademy/blog/global/host/CurrentBlogIntegrationTest.java`

```java
@Test
void subdomainResolvesToBlog() throws Exception {
    Blog blog = testBlogs.create(testMembers.create());            // 랜덤 주소의 블로그를 실제 DB에 저장

    mockMvc.perform(get("/api/test/blog")
                    .header("Host", TestBlogs.host(blog) + ":8080"))   // "t1a2b3c4d5e.blog.test:8080"
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.address").value(blog.getAddress()));
}
```

`Host` 헤더를 바꾸는 것만으로 서브도메인 요청을 흉내 낸다. 브라우저도 `/etc/hosts`도 필요 없다.

`src/test/java/com/nhnacademy/blog/global/auth/AuthenticationIntegrationTest.java`

```java
@Test
void stateChangingApiNeedsCsrfHeader() throws Exception {
    mockMvc.perform(post("/api/test/echo"))                                    // 헤더 없이
            .andExpect(status().isForbidden())
            .andExpect(jsonPath("$.code").value("CSRF_REJECTED"));
    mockMvc.perform(post("/api/test/echo")
                    .header(CsrfHeaderFilter.HEADER, CsrfHeaderFilter.EXPECTED_VALUE))   // 헤더 붙여서
            .andExpect(status().isOk());
}
```

같은 요청을 조건만 바꿔 두 번 보내 "있으면 통과, 없으면 막힘"을 한 테스트에서 보인다.

### 5.3 `@Transactional` 통합 테스트

`src/test/java/com/nhnacademy/blog/global/visibility/PostVisibilityIntegrationTest.java`

```java
@Transactional                                   // 테스트마다 롤백
class PostVisibilityIntegrationTest extends IntegrationTestSupport {
    ...
    /** 아직 기능이 없는 상태 변경은 SQL로 하고, 영속성 컨텍스트를 비워 다시 읽게 한다. */
    private void sql(String sql, Object... args) {
        entityManager.flush();                   // JPA가 모아 둔 INSERT를 먼저 DB로
        jdbcTemplate.update(sql, args);          // 예: UPDATE post SET is_blinded = 1 WHERE id = ?
        entityManager.clear();                   // JPA가 들고 있던 옛 Post 객체를 버림 → 다음 조회는 DB에서
    }
}
```

"숨김 처리" 기능은 아직 없지만 가시성 판단은 숨긴 글을 다뤄야 한다. 그래서 상태를 SQL로 직접 만들고, `flush`·`clear`로 JPA와 DB가 같은 값을 보게 한다. `clear`를 빠뜨리면 JPA는 1차 캐시의 옛 객체(숨김 아님)를 돌려줘서 테스트가 엉뚱하게 실패한다.

`@Transactional`을 붙이지 **않은** 테스트도 있다. `AuthenticationIntegrationTest`는 로그인 쿠키를 만들 때 Redis에 토큰을 저장하고 MockMvc 요청이 그것을 읽는데, 이런 흐름은 커밋된 실제 상태로 확인하는 편이 운영과 같다. 대신 4.4의 랜덤 데이터 규칙을 지킨다.

### 5.4 테스트 전용 도우미와 API (`support` 패키지)

`src/test/java/com/nhnacademy/blog/support/`

| 클래스 | 하는 일 |
| --- | --- |
| `TestMembers` (`@Component`) | 랜덤 이메일·닉네임으로 회원 저장, 로그인 쿠키 만들기, V2 관리자 찾기 |
| `TestBlogs` (`@Component`) | 랜덤 주소로 블로그 저장, 삭제·이용 제한·이사·주인 정지를 SQL로 |
| `TestApiController` | `/api/test/me`(로그인 필요), `/api/test/blog`(`@CurrentBlog`), `/api/admin/test` 등 |
| `TestErrorController` | 검증 실패·형식 오류·500 등 오류를 일부러 일으킴 |
| `TestIdempotentController` | `@Idempotent` API. 실제 실행 횟수를 센다 |

```java
// TestMembers
public Member create() {
    String suffix = UUID.randomUUID().toString().substring(0, 8);          // 매번 다른 값
    return memberRepository.save(Member.ofEmail(suffix + "@blog.test", "hash", "m-" + suffix));
}

public Cookie[] loginCookies(Member member, boolean rememberMe) {
    MockHttpServletResponse response = new MockHttpServletResponse();
    cookieManager.login(response, member, rememberMe);                     // 실제 로그인 쿠키 발급 코드를 그대로 씀
    return response.getCookies();                                          // MockMvc .cookie(...)에 넣을 수 있다
}
```

**왜 테스트 전용 API가 필요했나**: 스텝 3은 인증·주소 해석·연타 방지 **장치**만 만들고, 그 장치를 쓰는 실제 API(로그인, 글 발행)는 스텝 4·5에 생긴다. 장치를 HTTP 요청 단위로 확인하려면 장치를 쓰는 API가 있어야 해서, 테스트 소스에만 작은 컨트롤러를 둔다. `src/test`에 있으므로 운영 jar에는 들어가지 않는다.

### 5.5 `@WebMvcTest`가 깨진 이야기

스텝 2의 `GlobalExceptionHandlerTest`는 처음에 `@WebMvcTest`였다.

1. **스텝 2**: 모든 요청이 401·403. `@WebMvcTest`는 직접 만든 `SecurityConfig`(`@Configuration`)를 포함하지 않아 Spring Security **기본 설정**(전부 로그인 필요)이 걸렸다. `@AutoConfigureMockMvc(addFilters = false)`로 보안 필터를 끄고 넘어갔다.
2. **스텝 3**: `WebConfig`(`WebMvcConfigurer`)와 `CurrentBlogArgumentResolver`(`HandlerMethodArgumentResolver`)가 생겼다. 둘은 웹 계층이라 `@WebMvcTest`에 **포함**되는데, 리졸버가 생성자에서 받는 `BlogHostResolver`, `BlogVisibilityPolicy`(일반 `@Component`)는 **빠진다**. 그래서 `No qualifying bean of type 'BlogHostResolver'`로 컨텍스트가 뜨지 않았다.

해결 방법은 둘이었다.
- 빠진 빈을 `@MockitoBean`으로 채운다 → 웹 설정이 늘 때마다 목록이 늘고, 가짜 빈 조합마다 컨텍스트가 새로 생긴다.
- **통합 테스트로 바꾼다** ← 선택. 오류를 일으키는 컨트롤러를 `support/TestErrorController`로 옮기고 `IntegrationTestSupport`를 상속했다. 이미 떠 있는 컨텍스트를 재사용하니 느려지지도 않는다.

배운 점: 슬라이스 테스트는 **포함 규칙을 알고, 의존성이 적은 계층**에 쓴다. 의존 관계가 얽힌 웹 설정 전체를 볼 때는 통합 테스트가 단순하다.

### 5.6 동시성 테스트

`IdempotencyIntegrationTest.concurrentDoubleClickRunsOnce`는 스레드 두 개로 같은 키의 요청을 **동시에** 보내 컨트롤러가 한 번만 실행되는지 본다. 컨트롤러가 300ms 잠들게 해서 두 요청이 확실히 겹치게 만든다. "두 번 누르기"를 순서대로 보내는 테스트(`sameKeyTwiceGivesOneResult`)만으로는 동시에 들어온 경우를 확인할 수 없다.

### 5.7 (스텝 8·9) 서비스 전체를 보는 목록 테스트와 간섭

4.4의 "랜덤 데이터"는 회원·블로그처럼 **내가 만든 것만 보는** 테스트에는 충분하다. 그런데 홈 최신 글, 홈 인기 글, 주제별 글처럼 **서비스 전체의 글을 모아 보는** 기능은 다른 테스트가 남긴 글도 함께 보인다. 스텝 9에서 실제로 두 번 깨졌다.

1. 주제별 글 테스트가 "빠져야 할 글"로 조회 1000번짜리 글을 만들자, 홈 인기 글 테스트의 "내 글이 1위"가 깨졌다.
2. 주제별 글 테스트가 채우는 글을 2099년 날짜로 두자, 같은 방법(먼 미래 날짜로 늘 맨 위에 오게)을 쓰던 홈 최신 글 테스트에 그 글이 섞였다.

**혼자 돌리면 통과하고 전체를 돌리면 실패**해서 알아차렸다. 실행 순서에 따라 결과가 달라지는 테스트는 믿을 수 없다. 이 프로젝트가 고른 방법:

| 방법 | 쓴 곳 |
| --- | --- |
| 정확한 위치 대신 **앞뒤 관계**와 **빠진 것**을 확인 | `HomePopularIntegrationTest`(A가 B보다 앞, 비공개 글이 없다) |
| 다른 테스트가 쓰지 않는 **값 공간**을 쓴다 | `HomeTopicIntegrationTest`는 다른 테스트가 쓰지 않는 주제(HEALTH) |
| 남이 쓰는 값 공간(먼 미래 날짜)을 **빌리지 않는다** | 채우는 글을 현재 시각 근처로 |
| 테스트마다 공유 상태를 비운다 | 캐시 테스트의 `@BeforeEach`에서 `cacheManager.getCache(...).clear()` |

다른 선택지로는 테스트마다 표를 비우기(`TRUNCATE`)나 `@Transactional` 롤백이 있다. 하지만 MockMvc로 실제 커밋·Redis까지 보는 테스트가 많고 표를 비우면 느려져서 쓰지 않았다(4.3, 4.4).

---

### 5.8 (스텝 11) 사용자 순서대로 따라가는 시나리오 테스트

기능별 테스트(가입 테스트, 글쓰기 테스트, 공감 테스트…)는 각자 필요한 데이터를 도우미(`TestMembers`, `TestPosts`)로 바로 만든다. 빠르고 정확하지만, "사람이 실제로 밟는 순서대로 이어 붙였을 때 되는가"는 따로 확인되지 않는다. 스텝 11의 `QuickstartScenarioIntegrationTest`는 문서 `quickstart.md`의 "P0 한 바퀴"와 "권한·가시성" 표를 **그 순서 그대로** 따라간다.

- 가입부터 진짜 API다: 인증 코드 보내기 → DB에서 코드 읽기(`TestEmails.latestCode`) → 확인 → 가입 → 로그인 → 블로그 개설 → 글쓰기(이미지 올리기 포함) → 로그아웃 → 다른 회원으로 댓글·공감 → 주인이 댓글 삭제.
- **응답의 쿠키를 다음 요청에 붙인다.** 브라우저가 하는 일을 흉내 낸다. 로그아웃 응답이 주는 "지우는 쿠키"(`Max-Age=0`)는 빼고 들고 다닌다(`liveCookies`). 쿠키의 `Domain`이 `.blog.test`인지도 확인해, 플랫폼 주소에서 받은 로그인이 블로그 주소에서도 통하는 이유(R-03)를 테스트로 남겼다.
- 문서와 테스트가 짝이라, quickstart가 바뀌면 이 테스트도 고친다. quickstart에도 "이 표는 이 테스트가 자동 확인한다"고 적었다.

**여기서도 간섭이 있었다(5.7).** 처음에는 "로그아웃 뒤 홈 최신 글 첫 페이지에 그 글이 있다"로 확인했는데, 혼자 돌리면 통과하고 전체를 돌리면 실패했다. 홈 최신 글 테스트가 2099년 날짜 글을 만들어 두어 첫 페이지 20개를 차지했기 때문이다. "첫 페이지"가 아니라 **그 글이 있어야 할 자리에 커서를 맞춰**(그 글의 발행 시각, 그 글 번호 + 1) 다음 묶음을 읽고, 맨 앞에 그 글이 있는지 본다. 비공개로 바꾼 뒤에는 같은 자리에 없는지 본다.

또 하나: 처음 쓴 "비공개로 바꾸면 글 수에서 빠진다" 단언은 **처음부터 0이어도 통과**하는 약한 확인이었다. 바꾸기 전에 1이었는지를 먼저 확인하는 줄을 더했다. "뒤가 기대와 같다"만이 아니라 "앞은 달랐다"도 확인해야 바뀐 것을 증명한다.

## 6. 자주 하는 실수와 함정

| 실수 | 증상 | 해결 |
| --- | --- | --- |
| 테스트마다 `@MockitoBean`, `@Import`를 다르게 붙임 | 컨텍스트가 여러 개 생겨 테스트가 느려지고 컨테이너도 여러 쌍 | 공통 부모를 쓰고, 꼭 필요할 때만 다르게 |
| 고정 이메일·주소로 데이터 생성 | 두 번째 실행부터 UNIQUE 위반 | 랜덤 값(`UUID`) |
| `@Transactional` 테스트에서 JDBC로 바꾼 값을 JPA로 다시 읽음 | 옛 값이 보임 | `flush` → SQL → `clear` |
| H2로 테스트 | MySQL 전용 문법에서 실패, 또는 운영과 다른 결과 | Testcontainers MySQL |
| Docker를 끈 채 `./mvnw test` | `Could not find a valid Docker environment` | Docker Desktop/OrbStack 켜기 |
| `@WebMvcTest`에서 일반 `@Component`를 기대 | `NoSuchBeanDefinitionException` | 포함 규칙 확인, 또는 통합 테스트 |
| 상태 코드만 확인 | 404인데 본문이 비어 있는 버그를 놓침(스텝 3에서 실제로 있었음) | `jsonPath("$.code")`까지 확인 |
| 테스트가 실행 순서에 기댐 | 단독 실행은 되는데 전체 실행에서 실패(또는 그 반대) | 각 테스트가 자기 데이터를 만든다 |
| `System.out`으로 확인 | 자동 검증이 안 됨 | `assertThat`, `andExpect` |

---

## 7. 직접 해 보기

1. **하나만, 메서드 하나만 실행**
   ```bash
   ./mvnw test -Dtest=PageQueryTest
   ./mvnw test -Dtest='AuthenticationIntegrationTest#stateChangingApiNeedsCsrfHeader'
   ```

2. **컨텍스트 재사용 눈으로 보기**
   ```bash
   ./mvnw test 2>&1 | grep -E "Tests run:.*in com" 
   ```
   첫 통합 테스트만 `Time elapsed`가 10초 안팎이고 나머지는 1초 미만인 것을 본다. 테스트 중에 다른 터미널에서 `docker ps`를 보면 Testcontainers 컨테이너가 한 쌍만 있다.

3. **컨텍스트를 일부러 쪼개 보기** (확인 후 되돌린다)
   `NotFoundIntegrationTest`에 `@TestPropertySource(properties = "app.idempotency.ttl=1m")`를 붙이고 전체 테스트를 돌린다. 그 테스트를 위해 컨텍스트가 하나 더 생겨 전체 시간이 늘고, `docker ps`에 컨테이너가 한 쌍 더 보인다.

4. **`clear`를 빼 보기**
   `PostVisibilityIntegrationTest.sql()`에서 `entityManager.clear();`를 주석 처리하고 `blindedPostIsShownOnlyToOwnerWithFlag`를 돌린다. 숨김 처리가 반영되지 않아 테스트가 실패하는 것을 본다. 되돌린다.

5. **MockMvc 응답 전체 출력**
   테스트에 `.andDo(print())`(`MockMvcResultHandlers.print`)를 붙이면 요청·응답 헤더와 본문이 모두 콘솔에 찍힌다. 쿠키의 `Set-Cookie` 속성을 눈으로 확인해 본다.

6. **나만의 테스트 하나 쓰기**
   `CurrentBlogIntegrationTest`를 본떠 "주소가 3자(`abc.blog.test`)면 404"를 확인하는 테스트를 추가해 본다.

---

## 8. 확인 문제

1. `HtmlSanitizerTest`는 단위 테스트, `AuthenticationIntegrationTest`는 통합 테스트다. 각각 그렇게 만든 이유는?
   <details><summary>답</summary>HTML 정화는 입력 문자열 → 출력 문자열로 결과가 정해지는 순수 로직이라 스프링 없이 빠르게 확인할 수 있다. 인증은 쿠키 → 보안 필터 → DB 회원 조회 → Redis 토큰 확인 → JSON 오류 응답까지 여러 부품이 맞물려야 해서 전체를 띄워 확인한다.</details>

2. 모든 통합 테스트가 `IntegrationTestSupport`를 상속하는 이유는?
   <details><summary>답</summary>설정(애노테이션, @Import)이 같아야 Spring 테스트 프레임워크가 컨텍스트와 Testcontainers 컨테이너를 재사용한다. 하나로 맞추면 전체 테스트 시간이 크게 줄어든다.</details>

3. `TestcontainersConfiguration`은 왜 컴포넌트 스캔으로 잡히지 않고 `@Import`로 넣어야 하나?
   <details><summary>답</summary>`@TestConfiguration`이 붙은 클래스는 Spring Boot의 TypeExcludeFilter가 컴포넌트 스캔에서 빼기 때문이다(테스트 설정이 의도치 않게 다른 컨텍스트에 섞이지 않게).</details>

4. `@ServiceConnection`이 하는 일은?
   <details><summary>답</summary>컨테이너의 주소·포트·계정 같은 연결 정보를 Spring Boot의 연결 설정(spring.datasource.*, spring.data.redis.* 등)으로 자동 등록한다. `@DynamicPropertySource`로 직접 넣지 않아도 된다.</details>

5. `@Transactional` 테스트 안에서 `jdbcTemplate.update(...)` 전후에 `flush`와 `clear`를 하는 이유는?
   <details><summary>답</summary>`flush`는 JPA가 아직 보내지 않은 변경(INSERT)을 DB에 먼저 반영해 SQL이 그 행을 볼 수 있게 한다. `clear`는 JPA 1차 캐시의 옛 객체를 비워, 다음 조회가 SQL로 바뀐 값을 DB에서 다시 읽게 한다.</details>

6. `@WebMvcTest`로 쓴 오류 처리 테스트가 스텝 3에서 깨진 원인은?
   <details><summary>답</summary>`@WebMvcTest`는 웹 계층의 `CurrentBlogArgumentResolver`는 포함했지만, 그것이 생성자로 받는 `BlogHostResolver` 같은 일반 `@Component`는 포함하지 않아 빈을 찾지 못했다.</details>

7. 커밋되는 통합 테스트에서 이메일을 `a@blog.test`로 고정하면 어떤 문제가 생기나?
   <details><summary>답</summary>테스트들이 같은 DB(같은 컨테이너)를 공유하므로, 두 번째로 같은 이메일을 저장하는 테스트에서 UNIQUE 제약 위반이 난다. 실행 순서에 따라 성공·실패가 달라질 수도 있다.</details>

8. H2 대신 Testcontainers MySQL을 쓰는 이유 두 가지는?
   <details><summary>답</summary>V1의 MySQL 전용 문법(계산 컬럼 등)이 H2에서 실행되지 않는다. 실행되더라도 동작이 미묘하게 달라 H2에서만 통과하는 거짓 성공이 생긴다. 운영과 같은 DB로 테스트해야 결과를 믿을 수 있다.</details>

---

## 9. 더 읽을거리

- Spring Boot 공식 문서 "Testing" — `@SpringBootTest`, 슬라이스 테스트 목록, `@ServiceConnection` (https://docs.spring.io/spring-boot/)
- Spring Framework 공식 문서 "Testing > Context Caching", "MockMvc"
- Testcontainers 공식 문서 (https://java.testcontainers.org/) — MySQL 모듈, GenericContainer
- JUnit 5 User Guide (https://junit.org/junit5/docs/current/user-guide/)
- AssertJ 문서 (https://assertj.github.io/doc/)
- JsonPath 문법 (https://github.com/json-path/JsonPath)
