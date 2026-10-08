# 02. 설정과 프로필: application.yml, dev/prod, 환경 변수, 시간대

> 관련 스텝: [스텝 1](../step-01.md), [스텝 3](../step-03.md) · 먼저 읽을 것: [01. Spring Boot 기초](./01-spring-boot-basics.md)

## 1. 이 문서로 배우는 것

- `application.yml`의 구조와 YAML 문법
- **프로필**로 개발·운영 설정을 나누는 방법, `spring.profiles.default`와 `spring.profiles.active`
- 설정값이 여러 곳에 있을 때 **무엇이 이기는지**(우선순위)
- `${ENV:기본값}` 자리표시자와 **비밀값을 저장소에 두지 않는** 방법
- 이 프로젝트의 설정값 하나하나가 무슨 뜻인지
- 시간대(Asia/Seoul)를 왜, 어디서 맞추는지

**먼저 알면 좋은 것**: 환경 변수(`export NAME=value`)가 무엇인지, `@ConfigurationProperties`([01 문서](./01-spring-boot-basics.md) 4.1절).

---

## 2. 왜 필요한가

같은 코드가 여러 곳에서 돈다.

| 어디서 | DB | Redis | 플랫폼 주소 | 쿠키 Secure |
| --- | --- | --- | --- | --- |
| 지원 노트북 | `localhost:3306` (docker compose) | `localhost:6379` | `blog.test` | 끔(http) |
| 테스트 | Testcontainers가 띄운 임의 포트 | 임의 포트 | `blog.test` | 끔 |
| 운영 서버 | 운영 MySQL | 운영 Redis | `blog.com` | 켬(https) |

이 값들을 코드에 적으면 환경마다 코드를 고쳐 다시 빌드해야 한다. 더 나쁜 것은 **운영 DB 비밀번호가 git에 올라가는 것**이다. 한번 커밋된 비밀번호는 지워도 기록에 남고, 저장소를 볼 수 있는 모든 사람이 운영 DB에 들어갈 수 있다.

그래서 **코드는 하나, 설정은 밖에서**가 원칙이다. Spring Boot는 이것을 "외부화된 설정(Externalized Configuration)"이라고 부른다.

---

## 3. 기본 개념

### 3.1 YAML 문법

YAML은 들여쓰기로 계층을 나타내는 설정 형식이다. 같은 내용을 `.properties`로 쓰면 이렇다.

```yaml
spring:
  jpa:
    hibernate:
      ddl-auto: validate
app:
  auth:
    access-token-ttl: 30m
```

```properties
spring.jpa.hibernate.ddl-auto=validate
app.auth.access-token-ttl=30m
```

| 규칙 | 예 |
| --- | --- |
| 들여쓰기는 **공백**(탭 금지), 같은 단계는 같은 칸 수 | 2칸 |
| `키: 값` (콜론 뒤 공백 필수) | `port: 6379` |
| 주석은 `#` | `# 개발용` |
| 목록은 `- ` | `command:` 아래 `- --character-set-server=utf8mb4` |
| 특수 문자가 있으면 따옴표 | `key-prefix: "blog:"` (콜론이 들어 있어서) |

### 3.2 프로필

프로필은 **설정 묶음의 이름표**다. `application-{프로필}.yml` 파일은 그 프로필이 켜졌을 때만 읽힌다.

```
src/main/resources/
├─ application.yml          항상 읽힘 (공통)
├─ application-dev.yml      dev 프로필일 때만
└─ application-prod.yml     prod 프로필일 때만
```

- 같은 키가 둘 다에 있으면 **프로필 파일이 이긴다**. 공통 파일에 기본값을 두고, 프로필 파일에서 다른 것만 덮어쓴다.
- 프로필을 켜는 방법: `--spring.profiles.active=prod`(명령줄), `SPRING_PROFILES_ACTIVE=prod`(환경 변수).
- `spring.profiles.default: dev`: **아무 프로필도 켜지 않았을 때** 쓸 프로필. 개발자가 매번 `-Dspring.profiles.active=dev`를 붙이지 않아도 된다. `active`를 주면 `default`는 무시된다.

### 3.3 우선순위: 같은 키가 여러 곳에 있으면

Spring Boot는 여러 곳에서 설정을 읽고, **위쪽이 아래쪽을 덮어쓴다**(자주 쓰는 것만 추림).

```
높음  1. 명령줄 인자            java -jar app.jar --app.domain.platform=blog.kr
  │   2. 환경 변수              APP_DOMAIN_PLATFORM=blog.kr
  │   3. 프로필 설정 파일        application-prod.yml
  ▼   4. 기본 설정 파일          application.yml
낮음
```

그래서 운영에서는 파일을 고치지 않고 환경 변수 하나로 값을 바꿀 수 있다. 환경 변수 이름은 키를 대문자로, 점(`.`)과 하이픈(`-`)을 밑줄(`_`)로 바꾼 것이다: `app.auth.jwt-secret` → `APP_AUTH_JWT_SECRET`.

### 3.4 자리표시자 `${...}`

설정값 안에서 다른 값(대개 환경 변수)을 꺼내 쓴다.

| 쓰는 법 | 뜻 |
| --- | --- |
| `${DB_URL}` | 환경 변수 `DB_URL`. **없으면 시작 실패** |
| `${REDIS_PORT:6379}` | 없으면 `6379` |
| `${REDIS_PASSWORD:}` | 없으면 빈 문자열 |

운영에 꼭 있어야 하는 값(DB 주소, 서명 키)은 기본값을 두지 **않는다**. 빠뜨리면 서버가 뜨지 않아서, 잘못된 값으로 조용히 도는 것보다 낫다.

### 3.5 비밀값을 다루는 원칙

| 값 | 어디에 |
| --- | --- |
| 개발용 DB 계정(`blog/blog`), 개발용 서명 키 | 저장소에 둬도 됨. 내 노트북의 Docker에서만 쓰는 값이고, **이름에 "dev-only"를 넣어** 운영에 쓰면 안 된다는 것을 드러낸다 |
| 운영 DB 비밀번호, 운영 JWT 서명 키 | 저장소에 두지 않는다. 운영 서버의 환경 변수(또는 비밀 관리 서비스)로만 |

---

## 4. 동작 원리

서버가 시작될 때(01 문서 4절의 2단계) Spring Boot는 이렇게 설정을 모은다.

```
1. 활성 프로필 결정
   spring.profiles.active가 있으면 그것, 없으면 spring.profiles.default(dev)
2. 설정 출처를 우선순위 순서로 모아 Environment를 만든다
   [명령줄] [환경 변수] [application-dev.yml] [application.yml] ...
3. 값을 꺼낼 때(예: app.domain.platform) 위에서부터 찾아 처음 나온 값을 쓴다
4. ${...} 자리표시자를 같은 방식으로 풀어 넣는다
5. @ConfigurationProperties 클래스, 자동 설정(spring.datasource.* 등)이 이 값으로 만들어진다
```

테스트에서는 한 단계가 더 있다. Testcontainers의 `@ServiceConnection`이 컨테이너 주소를 **연결 정보로 직접 넣어서**, `application-dev.yml`의 `localhost:3306`보다 이긴다. 그래서 테스트도 dev 프로필로 뜨지만 개발 DB가 아니라 테스트 컨테이너에 붙는다([05 문서](./05-spring-testing.md)).

---

## 5. 이 프로젝트에서는

### 5.1 공통 설정: `src/main/resources/application.yml`

```yaml
spring:
  application:
    name: blog                     # 로그 줄에 [blog]로 찍히는 이름
  profiles:
    default: dev                   # 프로필을 안 주면 dev
  jpa:
    open-in-view: false            # (5.4 참고) 화면 렌더링까지 DB 연결을 붙잡지 않는다
    hibernate:
      ddl-auto: validate           # 테이블은 Flyway가 만들고, JPA는 엔티티와 맞는지 확인만 (03 문서)
    properties:
      hibernate:
        jdbc:
          time_zone: Asia/Seoul    # 시각을 DB에 쓰고 읽을 때 기준 시간대
  flyway:
    enabled: true
    locations: classpath:db/migration   # src/main/resources/db/migration의 V*.sql
  cache:
    type: redis                    # @Cacheable 저장소를 Redis로
    redis:
      time-to-live: 5m             # 캐시 항목은 5분 뒤 사라짐 (인기 글 등, R-10)
      key-prefix: "blog:"          # Redis 키 앞에 붙여 다른 용도의 키와 구분
  jackson:
    time-zone: Asia/Seoul          # JSON으로 시각을 내보낼 때 기준 시간대

server:
  error:                           # Spring Boot 기본 오류 응답(/error)에 내부 정보를 넣지 않는다
    include-stacktrace: never
    include-message: never
    include-exception: false
    include-binding-errors: never

app:                               # 여기부터는 이 프로젝트가 만든 설정 (spring.*이 아님)
  upload:
    dir: ${APP_UPLOAD_DIR:./uploads}   # 이미지 저장 폴더
  domain:
    platform: blog.com             # 블로그 주소는 {address}.{platform} → DomainProperties
  auth:                            # → AuthProperties
    access-token-ttl: 30m          # Access 토큰 수명
    refresh-token-ttl: 14d         # "로그인 유지"를 골랐을 때 Refresh 토큰 수명
    idle-timeout: 30m              # 안 골랐을 때 무활동으로 로그아웃되는 시간
    cookie-secure: true            # 쿠키 Secure 속성(HTTPS에서만 보냄)
  idempotency:
    ttl: 10m                       # 연타 방지 키를 기억하는 시간 → IdempotencyProperties
```

`app.*`는 Spring이 모르는 이 프로젝트만의 키라서, 각각 받는 record가 있다.

| 키 | 받는 클래스 | 쓰는 곳 | 자세히 |
| --- | --- | --- | --- |
| `app.domain.platform` | `global/host/DomainProperties` | 서브도메인 해석, 쿠키 도메인 | [15](./15-subdomain-host-routing.md) |
| `app.auth.*` | `global/auth/AuthProperties` | JWT 발급, 쿠키, 무활동 로그아웃 | [11](./11-jwt.md), [10](./10-http-cookies.md) |
| `app.idempotency.ttl` | `global/web/IdempotencyProperties` | 연타 방지 | [17](./17-idempotency-redis.md) |
| `app.upload.dir` | (스텝 7에서 사용) | 이미지 저장 | — |

**`server.error.*`를 끈 이유**: Spring Boot는 처리되지 않은 오류를 `/error`로 보내 기본 JSON을 만든다. 설정에 따라 예외 클래스 이름, 메시지, 스택 트레이스가 들어갈 수 있다. 이 프로젝트는 오류를 `GlobalExceptionHandler`가 COM-02 모양으로 만들지만, 그 손을 벗어난 오류(필터 단계 등)에서도 내부 정보가 새지 않게 막아 둔다([07](./07-spring-mvc-exception-handling.md)).

### 5.2 개발 설정: `application-dev.yml`

```yaml
spring:
  datasource:
    url: jdbc:mysql://localhost:3306/blog?connectionTimeZone=Asia/Seoul&characterEncoding=UTF-8
    #     ↑ JDBC 드라이버 종류  ↑ docker compose가 연 포트  ↑ DB 이름  ↑ 연결 옵션
    username: blog                 # docker-compose.yml의 MYSQL_USER와 같아야 함
    password: blog
  data:
    redis:
      host: localhost
      port: 6379

app:
  upload:
    dir: /Users/chosun-nhn54/IdeaProjects/blog/uploads    # 개발용 절대 경로 (git 제외)
  domain:
    platform: blog.test            # /etc/hosts에 등록한 개발용 도메인
  auth:
    jwt-secret: dev-only-jwt-secret-change-me-0123456789abcdef   # 개발 전용, 32바이트 이상
    cookie-secure: false           # http://blog.test:8080에서는 Secure 쿠키를 받을 수 없다
```

- `cookie-secure`는 공통 파일에서 `true`, 개발 파일에서 `false`로 **덮어썼다**. 안전한 쪽을 기본으로 두고, 개발에서만 푼다.
- `jwt-secret`은 공통 파일에 **없다**. 기본값이 없으니 운영에서 빠뜨리면 시작이 실패한다.

### 5.3 운영 설정: `application-prod.yml`

```yaml
spring:
  datasource:
    url: ${DB_URL}                 # 기본값 없음 → 반드시 줘야 함
    username: ${DB_USERNAME}
    password: ${DB_PASSWORD}
  data:
    redis:
      host: ${REDIS_HOST}
      port: ${REDIS_PORT:6379}     # 대부분 6379라 기본값
      password: ${REDIS_PASSWORD:} # 비밀번호 없는 Redis도 있어 빈 값 허용

app:
  upload:
    dir: ${APP_UPLOAD_DIR}
  domain:
    platform: ${APP_PLATFORM_DOMAIN:blog.com}
  auth:
    jwt-secret: ${JWT_SECRET}      # 운영 서명 키는 환경 변수로만
```

운영 실행 예:

```bash
export SPRING_PROFILES_ACTIVE=prod
export DB_URL='jdbc:mysql://db.internal:3306/blog?connectionTimeZone=Asia/Seoul'
export DB_USERNAME=blog DB_PASSWORD='...' REDIS_HOST=redis.internal
export JWT_SECRET="$(openssl rand -base64 48)"
export APP_UPLOAD_DIR=/var/blog/uploads
java -jar blog.jar
```

### 5.4 `spring.jpa.open-in-view: false`

**OSIV(Open Session In View)**는 HTTP 요청이 끝날 때까지 JPA 영속성 컨텍스트(와 DB 연결)를 열어 두는 설정이다. 기본값은 `true`이고, 그러면 컨트롤러나 JSON 변환 중에 지연 로딩(LAZY) 필드를 건드려도 쿼리가 나간다.

| | `true` (기본) | `false` (이 프로젝트) |
| --- | --- | --- |
| 지연 로딩 | 어디서든 됨 | 트랜잭션(서비스) 안에서만. 밖에서 건드리면 `LazyInitializationException` |
| DB 연결 | 요청이 끝날 때까지 붙잡음 | 트랜잭션이 끝나면 바로 반납 |
| 쿼리 위치 | 화면 코드에서 몰래 쿼리가 나갈 수 있음 | 서비스·저장소에서만 |

`false`로 두면 필요한 데이터를 서비스나 저장소에서 **미리 읽어야** 한다. 그래서 이 프로젝트는 `BlogRepository.findByAddress`, `PostRepository.findWithBlogById`에서 `join fetch`로 블로그 주인을 함께 읽는다([06](./06-jpa-entity-mapping.md)). 처음에는 불편하지만 쿼리가 어디서 나가는지 예측할 수 있고 연결을 오래 잡지 않는다.

### 5.5 시간대를 맞춘 곳

한국 서비스라 모든 시각을 Asia/Seoul로 맞춘다. 한 곳이라도 빠지면 9시간 차이가 난다.

| 위치 | 설정 | 무엇에 영향 |
| --- | --- | --- |
| JVM | `BlogApplication.main`의 `TimeZone.setDefault(TimeZone.getTimeZone("Asia/Seoul"))` | `LocalDateTime.now()`, `Clock.systemDefaultZone()`, 로그 시각. 서버가 UTC로 설정된 클라우드에 올라가도 같다 |
| Hibernate | `spring.jpa.properties.hibernate.jdbc.time_zone: Asia/Seoul` | 엔티티의 날짜·시각을 DB에 쓰고 읽을 때 |
| JDBC 연결 | URL의 `connectionTimeZone=Asia/Seoul` | MySQL 드라이버가 서버 시각을 해석할 때 |
| MySQL 컨테이너 | `docker-compose.yml`의 `TZ: Asia/Seoul` | `NOW()`, `DEFAULT CURRENT_TIMESTAMP` |
| JSON | `spring.jackson.time-zone: Asia/Seoul` | 응답의 시각 표기(`+09:00`) |

`created_at`은 DB 기본값(`CURRENT_TIMESTAMP`)이 아니라 JPA Auditing이 자바 시각으로 채우고, 일부 테스트는 SQL의 `NOW()`로 값을 바꾼다. 양쪽이 같은 시간대여야 비교가 맞는다.

---

## 6. 자주 하는 실수와 함정

| 실수 | 증상 | 해결 |
| --- | --- | --- |
| YAML에 탭 사용 | 시작할 때 YAML 파싱 오류 | 공백으로 |
| 들여쓰기가 한 칸 어긋남 | 키가 엉뚱한 부모 밑으로 들어가 값이 안 먹음(오류 없이!) | IDE의 YAML 구조 보기로 확인 |
| `key-prefix: blog:` (따옴표 없음) | 파싱 오류 또는 의도와 다른 값 | `"blog:"` |
| 운영 비밀값을 `application-prod.yml`에 직접 적음 | git 기록에 영구히 남음 | `${ENV}`로 |
| 프로필 이름 오타(`--spring.profiles.active=prd`) | `application-prd.yml`이 없으니 공통 설정만으로 뜸. 운영인데 `blog.com`이 아닌 값이나 `localhost` DB를 찾음 | 시작 로그의 `The following 1 profile is active: "prod"` 확인 |
| `${DB_URL}`인데 환경 변수를 안 줌 | `Could not resolve placeholder 'DB_URL'`로 시작 실패 | 의도된 동작. 환경 변수를 준다 |
| 공통 파일에 `cookie-secure: false` | 운영에서도 http로 쿠키가 새어 나감 | 안전한 값을 공통에, 푸는 값은 dev에만 |
| 시간대를 한 곳만 맞춤 | 글 작성 시각이 9시간 어긋남 | 5.5 표의 모든 곳 |

---

## 7. 직접 해 보기

1. **어떤 프로필로 떴는지 확인**
   ```bash
   ./mvnw spring-boot:run 2>&1 | grep "profile"
   ```
   기대: `No active profile set, falling back to 1 default profile: "dev"`.

2. **명령줄 인자가 파일을 이기는지 확인**
   ```bash
   ./mvnw spring-boot:run -Dspring-boot.run.arguments=--app.domain.platform=blog.kr
   curl -s -o /dev/null -w "%{http_code}\n" -H "Host: blog.kr:8080" localhost:8080/
   curl -s -o /dev/null -w "%{http_code}\n" -H "Host: nobody-here.blog.kr:8080" localhost:8080/
   ```
   기대: 첫 줄 200(플랫폼), 둘째 줄 404(없는 블로그). 플랫폼 주소가 `blog.kr`로 바뀌었다.

3. **환경 변수로 덮어쓰기**
   ```bash
   APP_DOMAIN_PLATFORM=blog.kr ./mvnw spring-boot:run
   ```
   2번과 같은 결과가 나온다(점과 하이픈이 밑줄로 바뀐 이름).

4. **필수 값 빠뜨리기**
   ```bash
   ./mvnw spring-boot:run -Dspring-boot.run.profiles=prod
   ```
   기대: `DB_URL` 자리표시자를 풀 수 없다는 오류로 시작 실패. 기본값이 없는 설계가 어떻게 지켜 주는지 본다.

5. **시간대 확인**
   ```bash
   docker exec blog-mysql mysql -ublog -pblog -e "SELECT NOW(), @@system_time_zone"
   date
   ```
   두 시각이 같은지 본다.

---

## 8. 확인 문제

1. `application.yml`과 `application-dev.yml`에 같은 키 `app.auth.cookie-secure`가 다른 값으로 있다. dev 프로필에서는 어느 값이 쓰이나?
   <details><summary>답</summary>`application-dev.yml`의 `false`. 프로필 파일이 기본 파일을 덮어쓴다.</details>

2. 운영 서버에서 파일을 고치지 않고 플랫폼 주소를 바꾸는 방법 두 가지는?
   <details><summary>답</summary>환경 변수 `APP_DOMAIN_PLATFORM`(운영 파일이 `${APP_PLATFORM_DOMAIN:blog.com}`이므로 이 경우 `APP_PLATFORM_DOMAIN`도 가능), 또는 명령줄 인자 `--app.domain.platform=...`.</details>

3. `jwt-secret`에 기본값(`${JWT_SECRET:something}`)을 두지 않은 이유는?
   <details><summary>답</summary>운영에서 환경 변수를 빠뜨렸을 때 아무도 모르는 약한 기본 키로 조용히 돌아가는 대신, 서버가 아예 뜨지 않게 해서 바로 알아차리게 하려고.</details>

4. `spring.profiles.default`와 `spring.profiles.active`의 차이는?
   <details><summary>답</summary>`active`는 켤 프로필을 정하고, `default`는 `active`가 없을 때만 쓰는 대체 프로필이다.</details>

5. `open-in-view: false`일 때, 컨트롤러에서 `post.getBlog().getMember().getNickname()`을 부르면 어떤 일이 생길 수 있나? 어떻게 피하나?
   <details><summary>답</summary>트랜잭션이 끝나 영속성 컨텍스트가 닫혔으므로 지연 로딩이 안 돼 `LazyInitializationException`이 난다. 서비스(트랜잭션) 안에서 필요한 값을 DTO로 옮기거나, 저장소에서 `join fetch`로 함께 읽는다.</details>

6. 개발 노트북에서는 시각이 맞는데 UTC로 설정된 클라우드 서버에 올렸더니 작성 시각이 9시간 이르게 보인다. 이 프로젝트의 어떤 설정이 이것을 막나?
   <details><summary>답</summary>`BlogApplication.main`의 `TimeZone.setDefault(Asia/Seoul)`(JVM 기본 시간대)와 Hibernate `jdbc.time_zone`, JDBC `connectionTimeZone`, Jackson `time-zone` 설정.</details>

7. `server.error.include-stacktrace: never`가 막는 위험은?
   <details><summary>답</summary>기본 오류 응답에 스택 트레이스(클래스 이름, 라이브러리 버전, 코드 위치)가 담겨 공격자가 내부 구조를 알게 되는 것.</details>

---

## 9. 더 읽을거리

- Spring Boot 공식 문서 "Externalized Configuration" — 우선순위 전체 목록, relaxed binding, 자리표시자 (https://docs.spring.io/spring-boot/)
- Spring Boot 공식 문서 "Profiles"
- Spring Boot 공식 문서 "Common Application Properties" — `spring.jpa.open-in-view`, `server.error.*` 등 모든 키
- The Twelve-Factor App, "III. Config" (https://12factor.net/config) — 설정을 환경에 두는 이유
- YAML 명세 (https://yaml.org/)
