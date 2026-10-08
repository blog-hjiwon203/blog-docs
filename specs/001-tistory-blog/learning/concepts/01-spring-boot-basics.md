# 01. Spring Boot 기초: 컨테이너, 빈, 의존성 주입, 자동 설정, Maven

> 관련 스텝: [스텝 1](../step-01.md), 이후 모든 스텝 · 다음에 읽을 것: [02. 설정과 프로필](./02-configuration-profiles.md)

## 1. 이 문서로 배우는 것

- 스프링 **컨테이너**가 무엇이고, **빈(bean)**이 어떻게 만들어져 서로 연결되는지
- **의존성 주입(DI)**, 그중 이 프로젝트가 쓰는 **생성자 주입**
- `@Component`, `@Configuration`, `@Bean`의 차이
- Spring Boot의 **스타터**와 **자동 설정(auto-configuration)**이 하는 일
- Maven의 **부모 POM / BOM**으로 버전을 관리하는 방법, `./mvnw`와 Maven 생명주기
- `@ConfigurationProperties`를 record로 받는 방법
- Spring Boot **4**에서 3.x와 달라진 점

**먼저 알면 좋은 것**: 자바 클래스·인터페이스·생성자, 애노테이션(`@`)이 무엇인지 정도.

---

## 2. 왜 필요한가

스프링 없이 블로그 서버를 만든다고 해 보자. 글 서비스는 글 저장소가 필요하고, 저장소는 DB 연결이 필요하다.

```java
public class Main {
    public static void main(String[] args) {
        DataSource dataSource = new HikariDataSource(/* URL, 계정, 비밀번호 ... */);
        PostRepository postRepository = new JdbcPostRepository(dataSource);
        BlogRepository blogRepository = new JdbcBlogRepository(dataSource);
        HtmlSanitizer sanitizer = new HtmlSanitizer();
        PostService postService = new PostService(postRepository, blogRepository, sanitizer);
        PostController controller = new PostController(postService);
        // 웹 서버를 띄우고, URL과 controller 메서드를 하나씩 연결하고 ...
    }
}
```

문제가 여러 개 보인다.

| 문제 | 설명 |
| --- | --- |
| 조립 코드가 커진다 | 클래스가 100개가 되면 `main`이 수백 줄의 `new`가 된다. 순서도 맞춰야 한다(저장소보다 DB 연결을 먼저) |
| 바꾸기 어렵다 | 테스트할 때 가짜 저장소로 바꾸려면 조립 코드를 고쳐야 한다 |
| 하나만 있어야 할 것이 여러 개 생긴다 | DB 연결 풀을 실수로 두 번 만들면 연결이 두 배로 열린다 |
| 반복 작업 | 웹 서버, JSON 변환, 트랜잭션, 보안 필터를 매번 직접 설정해야 한다 |

스프링은 이 **조립을 대신 해 주는 상자(컨테이너)**다. 개발자는 "나는 이런 부품이고, 이런 부품이 필요하다"만 선언하고, 만들고 연결하는 일은 컨테이너가 한다. Spring Boot는 그 위에 "웹 서버·DB 연결·JSON 같은 흔한 부품은 미리 조립해 둘게"를 더한 것이다.

---

## 3. 기본 개념

### 3.1 용어

| 용어 | 뜻 |
| --- | --- |
| 스프링 컨테이너 (`ApplicationContext`) | 객체를 만들고, 서로 연결하고, 생명주기를 관리하는 상자 |
| 빈(bean) | 컨테이너가 만들어 관리하는 객체. 기본은 **싱글턴**(애플리케이션에 하나) |
| 의존성(dependency) | 어떤 클래스가 일하려면 필요한 다른 객체. `PostService`는 `PostRepository`에 의존한다 |
| 의존성 주입(DI) | 필요한 객체를 스스로 `new`하지 않고 **밖에서 넣어 받는 것** |
| 제어의 역전(IoC) | 객체를 만들고 연결하는 주도권이 개발자 코드에서 컨테이너로 넘어간 것 |
| 컴포넌트 스캔 | 패키지를 뒤져 `@Component` 계열 애노테이션이 붙은 클래스를 찾아 빈으로 등록하는 것 |

### 3.2 빈을 등록하는 두 가지 방법

**(1) 클래스에 애노테이션 붙이기 → 컴포넌트 스캔이 찾는다**

```java
@Component          // "이 클래스를 빈으로 만들어 줘"
public class HtmlSanitizer { ... }
```

`@Component`의 의미를 더 분명히 한 변형들이 있다. 기능은 거의 같고, 역할을 드러내고 몇몇 추가 동작이 붙는다.

| 애노테이션 | 쓰는 곳 | 추가로 하는 일 |
| --- | --- | --- |
| `@Component` | 일반 부품 | — |
| `@Service` | 업무 로직(서비스 계층) | 표시용 |
| `@Repository` | 저장소 | DB 예외를 스프링 예외로 바꿔 줌 |
| `@Controller`, `@RestController` | 웹 요청 처리 | URL과 메서드를 연결(핸들러 매핑) 대상이 됨 |
| `@Configuration` | 설정 클래스 | 안에 `@Bean` 메서드를 둠 |

**(2) 설정 클래스의 `@Bean` 메서드 → 메서드가 돌려준 객체가 빈이 된다**

```java
@Configuration
public class ClockConfig {
    @Bean
    Clock clock() {                   // 메서드 이름 "clock"이 빈 이름
        return Clock.systemDefaultZone();
    }
}
```

`Clock`은 JDK 클래스라 소스에 `@Component`를 붙일 수 없다. 이렇게 **남이 만든 클래스**를 빈으로 만들거나, 만들 때 설정이 필요할 때 `@Bean`을 쓴다.

### 3.3 의존성 주입의 세 가지 방식

```java
// (1) 생성자 주입 — 이 프로젝트가 쓰는 방식
@Component
public class TokenStore {
    private final StringRedisTemplate redis;
    private final Clock clock;

    public TokenStore(StringRedisTemplate redis, Clock clock) {   // 컨테이너가 알맞은 빈을 찾아 넣는다
        this.redis = redis;
        this.clock = clock;
    }
}

// (2) 필드 주입 — 테스트 코드에서만 쓴다
@Autowired
MockMvc mockMvc;

// (3) setter 주입 — 거의 안 쓴다
@Autowired
public void setRedis(StringRedisTemplate redis) { ... }
```

**생성자 주입을 쓰는 이유**

| 이유 | 설명 |
| --- | --- |
| `final`로 둘 수 있다 | 한 번 받은 의존성이 바뀌지 않는다 |
| 빠뜨릴 수 없다 | 필요한 것이 없으면 컨테이너가 시작할 때 바로 실패한다(실행 중에 `NullPointerException`이 나는 것보다 낫다) |
| 테스트가 쉽다 | 스프링 없이 `new TokenStore(가짜Redis, 고정Clock)`으로 만들 수 있다 |
| 의존성이 드러난다 | 생성자 인자가 7개가 되면 "이 클래스가 너무 많은 일을 한다"는 신호가 보인다 |

생성자가 하나뿐이면 `@Autowired`를 붙이지 않아도 된다(Spring 4.3부터).

### 3.4 `@Configuration`과 `@Bean`의 관계

`@Configuration` 클래스 안의 `@Bean` 메서드를 다른 `@Bean` 메서드가 직접 호출해도, 스프링은 **같은 빈을 돌려준다**(클래스를 프록시로 감싸 호출을 가로챈다). `@Configuration(proxyBeanMethods = false)`로 끄면 매번 새 객체가 생기는 대신 시작이 조금 빨라진다. 이 프로젝트의 `TestcontainersConfiguration`이 `@TestConfiguration(proxyBeanMethods = false)`를 쓰는데, `@Bean` 메서드끼리 서로 부르지 않기 때문이다.

### 3.5 스타터 (starter)

스타터는 **"이 기능을 쓰려면 필요한 라이브러리 묶음"**을 하나의 의존성으로 만든 것이다. 코드가 거의 없고 pom만 있다.

```
spring-boot-starter-flyway  (pom만 있음)
 ├─ spring-boot-starter        (로깅, 기본 자동 설정)
 ├─ spring-boot-starter-jdbc   (DataSource, HikariCP)
 ├─ spring-boot-flyway         (Flyway 자동 설정 코드)
 └─ flyway-core                (Flyway 본체)
```

### 3.6 자동 설정 (auto-configuration)

자동 설정은 **"이 라이브러리가 클래스패스에 있고, 개발자가 직접 만든 빈이 없으면, 기본값으로 만들어 준다"**는 조건부 `@Configuration`이다.

```java
// 실제 코드를 단순화한 모양
@AutoConfiguration
@ConditionalOnClass(Flyway.class)                  // Flyway 라이브러리가 있을 때만
@ConditionalOnProperty(prefix = "spring.flyway", name = "enabled", matchIfMissing = true)
public class FlywayAutoConfiguration {

    @Bean
    @ConditionalOnMissingBean                       // 개발자가 직접 Flyway 빈을 만들지 않았을 때만
    Flyway flyway(DataSource dataSource, FlywayProperties properties) { ... }
}
```

| 조건 애노테이션 | 뜻 |
| --- | --- |
| `@ConditionalOnClass` | 이 클래스가 클래스패스에 있으면 |
| `@ConditionalOnMissingBean` | 같은 타입의 빈이 아직 없으면(개발자 설정이 이긴다) |
| `@ConditionalOnProperty` | 설정값이 이러면 |
| `@ConditionalOnBean` | 이 빈이 있으면 |

그래서 "`pom.xml`에 의존성 하나만 넣었는데 기능이 켜진다"가 가능하다. 그리고 개발자가 같은 타입의 빈을 직접 만들면 자동 설정이 물러난다. 이 프로젝트의 `SecurityConfig`가 `SecurityFilterChain` 빈을 직접 만들자 Spring Boot의 기본 보안 설정(모든 요청에 로그인 요구)이 꺼진 것이 그 예다.

### 3.7 Maven, 부모 POM, BOM

**Maven**은 자바 빌드 도구다. `pom.xml`에 무엇이 필요한지 적으면 라이브러리를 내려받고(`~/.m2/repository`), 컴파일하고, 테스트하고, jar로 묶는다.

**부모 POM**: `pom.xml`의 `<parent>`에 `spring-boot-starter-parent`를 두면 부모의 설정을 물려받는다. 그중 핵심이 **BOM(Bill of Materials)**, 즉 "이 Spring Boot 버전과 함께 검증된 라이브러리 버전 목록"이다.

```xml
<parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>4.1.1</version>      <!-- 이 숫자 하나가 수백 개 라이브러리 버전을 정한다 -->
</parent>

<dependency>
    <groupId>org.flywaydb</groupId>
    <artifactId>flyway-mysql</artifactId>
    <!-- version이 없다: BOM이 12.4.0으로 정해 준다 -->
</dependency>
```

BOM에 없는 라이브러리(OWASP Sanitizer, jsoup)만 `<properties>`에 버전을 적는다. 버전을 섞어 쓰다가 서로 맞지 않아 실행 중에 `NoSuchMethodError`가 나는 일을 막아 준다.

### 3.8 Maven 생명주기와 `./mvnw`

Maven은 정해진 **단계(phase)**를 순서대로 실행한다. 뒤 단계를 부르면 앞 단계가 모두 먼저 실행된다.

```
validate → compile → test-compile → test → package → verify → install
                                     ↑        ↑
                          ./mvnw test   ./mvnw package (테스트까지 하고 jar 생성)
```

| 명령 | 하는 일 |
| --- | --- |
| `./mvnw compile` | `src/main/java` 컴파일 |
| `./mvnw test` | 컴파일 + 테스트 실행(Surefire 플러그인) |
| `./mvnw package` | 테스트 + `target/blog-0.0.1-SNAPSHOT.jar` 생성 |
| `./mvnw spring-boot:run` | 컴파일 후 앱 실행(Spring Boot 플러그인의 goal) |
| `./mvnw dependency:tree` | 어떤 라이브러리가 어디서 왔는지 트리로 |
| `./mvnw test -Dtest=클래스명` | 테스트 클래스 하나만 |

**`mvnw`(Maven Wrapper)**: 컴퓨터에 Maven이 설치돼 있지 않아도, `.mvn/wrapper/maven-wrapper.properties`에 적힌 버전(3.9.16)을 내려받아 쓴다. 누가 빌드해도 같은 Maven 버전이 된다.

---

## 4. 동작 원리: `SpringApplication.run`이 하는 일

`./mvnw spring-boot:run`을 하면 대략 이런 순서로 일이 일어난다.

```
1. main() → SpringApplication.run(BlogApplication.class)
2. 설정 읽기: application.yml + 프로필 파일 + 환경 변수 → Environment
3. 컴포넌트 스캔: com.nhnacademy.blog 아래 모든 패키지에서 @Component 계열 클래스 찾기
4. 자동 설정 후보 읽기: 각 라이브러리 jar의
      META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports
   → @Conditional 조건을 평가해 살아남은 것만 적용
5. 빈 정의(설계도) 목록 완성
6. 빈 생성: 의존 관계를 따라 필요한 것부터 만든다
      DataSource → Flyway(마이그레이션 실행) → EntityManagerFactory(validate) → Repository → ...
7. 내장 톰캣 시작 (8080)
8. "Started BlogApplication in 2.7 seconds"
```

- `@SpringBootApplication`은 세 애노테이션을 합친 것이다: `@SpringBootConfiguration`(설정 클래스), `@EnableAutoConfiguration`(4번), `@ComponentScan`(3번, 이 클래스가 있는 패키지부터).
- 그래서 `BlogApplication`은 **최상위 패키지**(`com.nhnacademy.blog`)에 있어야 한다. 그 아래 패키지만 스캔되기 때문이다.
- 6번에서 의존하는 빈이 없거나 두 개 이상이면 시작이 실패한다(`NoSuchBeanDefinitionException`, `NoUniqueBeanDefinitionException`). 순환 의존(A가 B를, B가 A를 필요)도 생성자 주입에서는 시작할 때 실패한다.
- 자동 설정이 무엇을 켰는지 보려면 `--debug`로 실행하면 "CONDITIONS EVALUATION REPORT"가 나온다.

### 4.1 `@ConfigurationProperties`가 값을 넣는 과정

```
application.yml                         AuthProperties (record)
app:                                    ┌──────────────────────────────┐
  auth:                                 │ String   jwtSecret           │
    jwt-secret: dev-only-...     ──────▶│ Duration accessTokenTtl      │ ← "30m"을 Duration으로 변환
    access-token-ttl: 30m        ──────▶│ Duration refreshTokenTtl     │ ← "14d"
    refresh-token-ttl: 14d       ──────▶│ Duration idleTimeout         │
    idle-timeout: 30m            ──────▶│ boolean  cookieSecure        │ ← "true"
    cookie-secure: true          ──────▶└──────────────────────────────┘
```

- `jwt-secret`(케밥 표기)과 `jwtSecret`(카멜 표기)을 같은 것으로 본다(**relaxed binding**). 환경 변수 `APP_AUTH_JWT_SECRET`도 같은 값으로 연결된다.
- `30m`, `14d`, `10m` 같은 문자열은 `Duration`으로 바뀐다(`s`, `m`, `h`, `d` 등).
- record는 생성자로 값을 받는다(**생성자 바인딩**). 만든 뒤 값을 바꿀 수 없어서 설정값이 실행 중에 바뀌지 않는다.
- `@ConfigurationPropertiesScan`이 이런 클래스를 찾아 빈으로 등록한다.

---

## 5. 이 프로젝트에서는

### 5.1 시작 클래스

`src/main/java/com/nhnacademy/blog/BlogApplication.java`

```java
@SpringBootApplication                 // 설정 + 자동 설정 + com.nhnacademy.blog 아래 컴포넌트 스캔
@ConfigurationPropertiesScan           // @ConfigurationProperties record를 찾아 빈으로 등록
public class BlogApplication {

    public static void main(String[] args) {
        TimeZone.setDefault(TimeZone.getTimeZone("Asia/Seoul"));   // JVM 기본 시간대 (02 문서 참고)
        SpringApplication.run(BlogApplication.class, args);         // 위 4절의 과정 시작
    }
}
```

### 5.2 설정값을 record로 받기

`src/main/java/com/nhnacademy/blog/global/auth/AuthProperties.java`

```java
@ConfigurationProperties(prefix = "app.auth")          // app.auth.* 값을 이 record로
public record AuthProperties(String jwtSecret,          // app.auth.jwt-secret
                             Duration accessTokenTtl,   // app.auth.access-token-ttl
                             Duration refreshTokenTtl,  // app.auth.refresh-token-ttl
                             Duration idleTimeout,      // app.auth.idle-timeout
                             boolean cookieSecure) {    // app.auth.cookie-secure
}
```

`src/main/java/com/nhnacademy/blog/global/host/DomainProperties.java`

```java
@ConfigurationProperties(prefix = "app.domain")
public record DomainProperties(String platform) {      // app.domain.platform (개발 blog.test, 운영 blog.com)

    public String cookieDomain() {                      // record에도 메서드를 둘 수 있다
        return "." + platform;                          // ".blog.test" → 모든 하위 주소가 받는 쿠키 도메인
    }

    public String blogHost(String address) {
        return address + "." + platform;                // "alpha" → "alpha.blog.test"
    }
}
```

설정값을 코드 곳곳에서 `@Value("${app.domain.platform}")`로 꺼내는 대신 한 record에 모으면, 이름 오타를 컴파일러가 잡고, 관련 값이 한눈에 보이고, 테스트에서 `new DomainProperties("blog.com")`처럼 직접 만들 수 있다(`BlogHostResolverTest`가 그렇게 한다).

### 5.3 생성자 주입과 `@Bean`

`src/main/java/com/nhnacademy/blog/global/auth/JwtTokenProvider.java`

```java
@Component
public class JwtTokenProvider {
    ...
    public JwtTokenProvider(AuthProperties properties, Clock clock) {   // 두 빈을 컨테이너가 넣어 준다
        byte[] secret = properties.jwtSecret().getBytes(StandardCharsets.UTF_8);
        if (secret.length < MIN_SECRET_BYTES) {
            throw new IllegalStateException("app.auth.jwt-secret은 32바이트 이상이어야 합니다.");
        }                                                               // 설정이 잘못되면 시작할 때 바로 실패
        ...
    }
}
```

- `AuthProperties`는 `@ConfigurationPropertiesScan`이 등록한 빈, `Clock`은 아래 `ClockConfig`의 `@Bean`이다.
- 생성자에서 설정값을 검사하므로, 서명 키가 짧으면 **요청이 들어올 때가 아니라 서버가 뜰 때** 실패한다.

`src/main/java/com/nhnacademy/blog/global/config/ClockConfig.java`

```java
@Configuration
public class ClockConfig {
    @Bean
    Clock clock() {                         // "지금 시각"도 빈으로 둔다
        return Clock.systemDefaultZone();
    }
}
```

`LocalDateTime.now()`를 코드 곳곳에서 부르면 테스트에서 시각을 고정할 수 없다. `Clock` 빈을 주입받아 `LocalDateTime.now(clock)`으로 쓰면, 테스트에서 고정된 `Clock`을 넣어 "정지 종료 시각이 지난 경우" 같은 상황을 만들 수 있다.

### 5.4 `@EnableXxx`로 기능 켜기

`src/main/java/com/nhnacademy/blog/global/config/CacheConfig.java`, `JpaConfig.java`

```java
@Configuration
@EnableCaching          // @Cacheable 같은 캐시 애노테이션이 동작하게 한다
public class CacheConfig { }

@Configuration
@EnableJpaAuditing      // @CreatedDate, @LastModifiedDate가 동작하게 한다
public class JpaConfig { }
```

`@EnableXxx`는 "이 기능에 필요한 빈들을 등록해 줘"라는 스위치다. `@EnableJpaAuditing`을 `BlogApplication`이 아니라 따로 둔 이유는 [05. 테스트](./05-spring-testing.md)의 슬라이스 테스트 절을 본다.

### 5.5 `pom.xml`

`pom.xml`의 의존성은 이렇게 나뉜다.

| 의존성 | 무엇을 켜나 |
| --- | --- |
| `spring-boot-starter-webmvc` | 내장 톰캣, Spring MVC, JSON(Jackson 3) |
| `spring-boot-starter-data-jpa` | Hibernate 7, Spring Data JPA, HikariCP |
| `spring-boot-starter-flyway` + `flyway-mysql` | 시작할 때 마이그레이션 실행 |
| `spring-boot-starter-data-redis` | Redis 클라이언트(Lettuce), `StringRedisTemplate` |
| `spring-boot-starter-cache` | 캐시 추상화 |
| `spring-boot-starter-security` | Spring Security 7 |
| `spring-security-oauth2-jose` | JWT 서명·검증(Nimbus). 스타터가 아니라 라이브러리라 자동 설정 없이 직접 씀 |
| `spring-boot-starter-validation` | `@NotBlank` 같은 입력 검증 |
| `mysql-connector-j` (`runtime`) | MySQL JDBC 드라이버. 코드가 직접 쓰지 않으니 실행할 때만 필요 |
| `*-test`, `testcontainers-*` (`test`) | 테스트할 때만 |

`<scope>`는 "언제 필요한가"다. `compile`(기본)은 항상, `runtime`은 실행할 때만, `test`는 테스트할 때만 클래스패스에 들어간다.

### 5.6 Spring Boot 4에서 달라진 점 (3.x 예제를 그대로 쓰면 안 되는 이유)

| 항목 | 3.x | 4.x (이 프로젝트) |
| --- | --- | --- |
| 웹 스타터 | `spring-boot-starter-web` | `spring-boot-starter-webmvc` |
| 자동 설정 위치 | `spring-boot-autoconfigure` jar 하나에 거의 다 | 기능별 모듈로 나뉨(예: `spring-boot-flyway` 안의 `org.springframework.boot.flyway.autoconfigure.FlywayAutoConfiguration`) |
| Flyway | `flyway-core`만 넣어도 자동 설정 | `spring-boot-starter-flyway`가 있어야 자동 설정 모듈이 들어온다 |
| 테스트 | `spring-boot-starter-test` 하나 | 기능별 테스트 스타터(`-webmvc-test`, `-data-jpa-test` …) |
| `@AutoConfigureMockMvc`, `@WebMvcTest` 패키지 | `org.springframework.boot.test.autoconfigure.web.servlet` | `org.springframework.boot.webmvc.test.autoconfigure` |
| JSON | Jackson 2 (`com.fasterxml.jackson.databind`) | Jackson 3 (`tools.jackson.databind`). 애노테이션은 `com.fasterxml.jackson.annotation` 그대로 |
| Testcontainers | 1.x: 모듈 `mysql`, 클래스 `org.testcontainers.containers.MySQLContainer` | 2.x: 모듈 `testcontainers-mysql`, 클래스 `org.testcontainers.mysql.MySQLContainer` |

인터넷 예제를 볼 때는 **버전**과 **import 경로**부터 확인한다.

---

## 6. 자주 하는 실수와 함정

| 실수 | 증상 | 해결 |
| --- | --- | --- |
| 시작 클래스보다 위 패키지에 컴포넌트를 둠 | 빈이 등록되지 않아 `NoSuchBeanDefinitionException` | 모든 코드는 `com.nhnacademy.blog` 아래에 |
| 같은 타입 빈을 두 개 만듦 | `NoUniqueBeanDefinitionException` | 하나로 줄이거나 `@Primary`, `@Qualifier` |
| 서블릿 필터를 `@Component`로 등록하고 Security 체인에도 넣음 | 필터가 요청마다 **두 번** 실행 | Security 체인에만 넣을 필터는 `@Component`를 빼고 `SecurityConfig`에서 `new` (이 프로젝트의 `JwtAuthenticationFilter`, `CsrfHeaderFilter`) |
| `new`로 직접 만든 객체에 `@Autowired`를 기대함 | 필드가 `null` | 컨테이너가 만든 객체에만 주입된다 |
| 버전을 BOM과 다르게 지정 | 실행 중 `NoSuchMethodError`, `ClassNotFoundException` | BOM이 관리하는 라이브러리는 버전을 쓰지 않는다 |
| 3.x 예제의 import를 그대로 씀 | 컴파일 오류(패키지 없음) | 5.6 표 확인 |
| 생성자 순환 의존 | 시작할 때 `BeanCurrentlyInCreationException` | 설계를 고쳐 한쪽 의존을 없앤다(대개 역할이 섞였다는 신호) |

---

## 7. 직접 해 보기

1. **자동 설정 보고서 보기**
   ```bash
   ./mvnw spring-boot:run -Dspring-boot.run.arguments=--debug 2>&1 | grep -A3 "FlywayAutoConfiguration"
   ```
   "matched"(조건 통과)로 나오는지 본다. `pom.xml`에서 `spring-boot-starter-flyway`를 잠시 지우고(`flyway-mysql`은 남겨 둔 채) 다시 실행하면, Flyway 자동 설정이 사라지고 **마이그레이션이 실행되지 않아** JPA validate가 실패하는 것을 볼 수 있다. 확인 후 되돌린다.

2. **의존성 트리 보기**
   ```bash
   ./mvnw dependency:tree -Dincludes=org.flywaydb
   ```
   `flyway-core`가 어느 스타터를 거쳐 들어왔는지, 버전이 무엇인지 확인한다.

3. **설정 검사로 시작 실패 만들기**
   `application-dev.yml`의 `app.auth.jwt-secret`을 `short`로 바꾸고 실행한다. 로그에 `app.auth.jwt-secret은 32바이트 이상이어야 합니다.`가 나오고 서버가 뜨지 않는다. 되돌린다.

4. **빈이 몇 개인지 세어 보기**
   `BlogApplicationTests`에 다음을 잠시 넣고 실행한다.
   ```java
   @Autowired ApplicationContext context;
   @Test void beans() {
       System.out.println(context.getBeanDefinitionCount());
       System.out.println(context.getBean(DomainProperties.class));
   }
   ```
   개발자가 만든 빈보다 자동 설정이 만든 빈이 훨씬 많다는 것을 볼 수 있다.

5. **`./mvnw` 단계 차이**
   `./mvnw package -DskipTests` 후 `ls target/*.jar`, `java -jar target/blog-0.0.1-SNAPSHOT.jar`로 jar를 직접 실행해 본다(Docker의 MySQL·Redis가 떠 있어야 한다).

---

## 8. 확인 문제

1. 의존성 주입을 쓰지 않고 클래스 안에서 `new`로 의존 객체를 만들면 테스트할 때 어떤 점이 불편한가?
   <details><summary>답</summary>가짜 객체(예: 고정된 Clock, 가짜 저장소)로 바꿔 끼울 수 없다. 클래스 안에서 진짜 객체를 만들어 버리므로, 테스트하려면 진짜 DB·진짜 시각에 의존하게 된다.</details>

2. `JwtTokenProvider`는 `@Component`이고 `Clock`은 `@Bean`으로 등록됐다. 왜 `Clock`에는 `@Component`를 쓰지 않았나?
   <details><summary>답</summary>`Clock`은 JDK 클래스라 소스에 애노테이션을 붙일 수 없고, `Clock.systemDefaultZone()`처럼 만드는 방법을 지정해야 하기 때문이다. 남이 만든 클래스나 생성 방법이 필요한 객체는 `@Bean` 메서드로 등록한다.</details>

3. 자동 설정에서 `@ConditionalOnMissingBean`이 중요한 이유는?
   <details><summary>답</summary>개발자가 같은 타입의 빈을 직접 만들면 자동 설정이 물러나게 해서, 기본값은 주되 개발자가 언제든 덮어쓸 수 있게 하기 때문이다. 예: `SecurityConfig`가 `SecurityFilterChain`을 만들자 기본 보안 설정이 꺼졌다.</details>

4. `pom.xml`의 `flyway-mysql`에는 `<version>`이 없는데 어떻게 버전이 정해지나?
   <details><summary>답</summary>부모 POM `spring-boot-starter-parent` 4.1.1이 가져오는 BOM(`spring-boot-dependencies`)이 Flyway 버전(12.4.0)을 관리한다.</details>

5. `mysql-connector-j`의 scope가 `runtime`인 이유는?
   <details><summary>답</summary>코드가 MySQL 드라이버 클래스를 직접 import하지 않고 JDBC 표준 인터페이스만 쓰므로, 컴파일할 때는 필요 없고 실행할 때만 있으면 되기 때문이다.</details>

6. `application.yml`의 `app.auth.access-token-ttl: 30m`이 `AuthProperties`의 어느 필드에 어떤 타입으로 들어가나?
   <details><summary>답</summary>`accessTokenTtl` 필드에 `Duration`(30분)으로 들어간다. 케밥 표기와 카멜 표기를 같게 보는 relaxed binding과 문자열 → Duration 변환이 함께 일어난다.</details>

7. Spring Boot 3.x 블로그 글의 `import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;`를 이 프로젝트에 붙이면 어떻게 되나?
   <details><summary>답</summary>Spring Boot 4에서는 패키지가 `org.springframework.boot.webmvc.test.autoconfigure`로 바뀌어 컴파일 오류가 난다.</details>

---

## 9. 더 읽을거리

- Spring Framework 공식 문서 "The IoC Container" — 빈, DI, `@Configuration`
- Spring Boot 공식 문서 "Developing with Spring Boot" — 스타터, 자동 설정, `@SpringBootApplication` (https://docs.spring.io/spring-boot/)
- Spring Boot 공식 문서 "Externalized Configuration" — `@ConfigurationProperties`, relaxed binding
- Spring Boot 공식 문서 "Creating Your Own Auto-configuration" — `@Conditional` 계열
- Apache Maven "Introduction to the Build Lifecycle" (https://maven.apache.org/guides/introduction/introduction-to-the-lifecycle.html)
- Spring Boot 4.0 Migration Guide (GitHub spring-projects/spring-boot 위키)
