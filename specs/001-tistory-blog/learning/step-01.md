# 스텝 1. 실행 환경

> 작업: T001, T002, T003, T004, T016a · 코드 PR: [#1](https://github.com/AIP-1/blog-basic-AIGJ_01_017-blog/pull/1) · 날짜: 2026-10-08

## 한눈에 보기

기능은 하나도 없고, **기능을 만들 수 있는 판**을 깔았다.

```
docker compose up -d   →  MySQL 8(3306) + Redis(6379) 컨테이너
./mvnw spring-boot:run →  Spring Boot(8080) 시작 → Flyway가 V1__init.sql 실행 → 빈 테이블 26개
./mvnw test            →  Testcontainers가 테스트용 MySQL·Redis 컨테이너를 따로 띄움
npm run dev            →  Vite(5173), /api 요청은 8080으로 넘김
```

| 파일 | 하는 일 |
| --- | --- |
| `pom.xml` | Cache, Data Redis, Flyway(+`flyway-mysql`), Testcontainers 의존성 |
| `docker-compose.yml` | 개발용 MySQL 8.4, Redis 7.4 (healthcheck 포함) |
| `src/main/resources/application.yml` | 모든 환경 공통 설정 |
| `application-dev.yml`, `application-prod.yml` | 환경별 설정(DB 주소, 업로드 폴더) |
| `db/migration/V1__init.sql` | ERD에서 내보낸 `schema.sql`을 그대로 복사 |
| `…/blog/global/config/CacheConfig.java` | `@EnableCaching`, Redis 캐시 TTL 5분 |
| `src/test/…/TestcontainersConfiguration.java` | 테스트용 MySQL·Redis 컨테이너 |
| `frontend/` | Vite + React 18 + TypeScript |
| `scripts/build-frontend.sh` | 프론트 빌드 결과를 `src/main/resources/static`으로 복사 |

## 개념

### 1. Maven과 스타터 의존성

Spring Boot는 기능마다 **스타터**(`spring-boot-starter-xxx`)를 두고, 스타터 하나가 그 기능에 필요한 라이브러리 묶음과 자동 설정을 가져온다. 버전은 부모 POM(`spring-boot-starter-parent` 4.1.1)이 관리하므로 `<version>`을 쓰지 않는다.

**Spring Boot 4에서 바뀐 점**(3.x 예제를 그대로 쓰면 안 되는 이유):
- 웹 스타터 이름이 `spring-boot-starter-web` → `spring-boot-starter-webmvc`.
- Flyway는 `flyway-core`만 넣으면 자동 설정이 안 되고 `spring-boot-starter-flyway`가 필요하다. MySQL을 쓰면 `flyway-mysql`도 따로 넣는다.
- 테스트 스타터가 기능별로 나뉜다(`spring-boot-starter-webmvc-test`, `-data-jpa-test` 등).
- Jackson 3(패키지 `tools.jackson`)을 쓴다. 애노테이션(`@JsonInclude` 등)은 예전 패키지 `com.fasterxml.jackson.annotation` 그대로다.
- Testcontainers 2.x는 모듈 이름이 `testcontainers-mysql`, 클래스가 `org.testcontainers.mysql.MySQLContainer`다(1.x는 `mysql`, `org.testcontainers.containers.MySQLContainer`).

**코드에서**: `pom.xml`. 버전을 확인하려면 `~/.m2/repository/org/springframework/boot/spring-boot-dependencies/4.1.1/*.pom`에서 `testcontainers.version` 등을 찾는다.

### 2. Spring 프로필

같은 코드를 개발·운영에서 다른 설정으로 돌리려고 설정 파일을 나눈다.
- `application.yml`: 공통. `spring.profiles.default: dev`라서 아무 프로필도 안 주면 dev로 뜬다.
- `application-dev.yml`: docker compose의 MySQL(`localhost:3306`, 계정 blog/blog), 업로드 폴더 절대 경로.
- `application-prod.yml`: `${DB_URL}`처럼 **환경 변수**로 받는다. 비밀번호를 저장소에 남기지 않기 위해서다.

운영에서는 `java -jar app.jar --spring.profiles.active=prod`처럼 켠다.

### 3. Flyway: 테이블은 SQL 파일로 만든다

JPA의 `ddl-auto=create`는 엔티티를 보고 테이블을 만들어 주지만, 실제 서비스에서는 쓰지 않는다. 어떤 SQL이 언제 실행됐는지 기록이 남지 않기 때문이다. Flyway는 `db/migration/V{번호}__{설명}.sql` 파일을 번호 순서대로 **한 번씩만** 실행하고 `flyway_schema_history` 테이블에 기록한다.

- 이미 실행된 파일을 고치면 체크섬이 달라져 앱이 뜨지 않는다. 그래서 바꿀 때는 새 번호 파일(`V3__...`)을 더한다.
- JPA는 `ddl-auto=validate`로 **엔티티와 테이블이 맞는지 확인만** 한다. 안 맞으면 앱이 뜰 때 실패한다(스텝 2에서 이 덕을 봤다).

**코드에서**: `application.yml`의 `spring.flyway`, `spring.jpa.hibernate.ddl-auto`.

### 4. Docker Compose와 Testcontainers

- **Docker Compose**: 개발 중 계속 켜 두는 MySQL·Redis. 데이터는 `mysql-data` 볼륨에 남는다. `healthcheck`는 컨테이너가 "떴다"가 아니라 "요청을 받을 수 있다"를 확인한다.
- **Testcontainers**: 테스트가 시작될 때 **새 컨테이너**를 띄우고 끝나면 지운다. 개발 DB를 더럽히지 않고, 누가 돌려도 같은 결과가 나온다.
- `@ServiceConnection`(Spring Boot 3.1+)을 컨테이너 빈에 붙이면, 컨테이너의 주소·포트·계정을 Spring이 알아서 `spring.datasource.*`, `spring.data.redis.*`에 넣는다. 예전에는 `@DynamicPropertySource`로 직접 넣었다.

**코드에서**: `src/test/…/TestcontainersConfiguration.java`. MySQL은 `@ServiceConnection`, Redis는 전용 클래스가 없어 `GenericContainer`에 `@ServiceConnection(name = "redis")`로 종류를 알려 준다.

**왜 H2를 안 쓰나**: ERD의 `schema.sql`에 MySQL 전용 문법(`GENERATED ALWAYS AS ... STORED` 계산 컬럼)이 있어 H2에서 실행되지 않는다(research.md R-02). 테스트 DB와 운영 DB가 같아야 "테스트는 통과했는데 운영에서 깨지는" 일이 줄어든다.

### 5. 시간대

`TZ=Asia/Seoul` 요구를 세 곳에서 맞췄다.
- JVM 기본 시간대: `BlogApplication.main`의 `TimeZone.setDefault(...)` → `LocalDateTime.now()`가 서버 위치와 상관없이 한국 시간.
- Hibernate가 DB에 시각을 쓸 때: `hibernate.jdbc.time_zone: Asia/Seoul`.
- MySQL 컨테이너: `TZ: Asia/Seoul`, JDBC URL의 `connectionTimeZone=Asia/Seoul`.

### 6. Vite 프록시와 jar 하나 배포

- 개발 중: 프론트(5173)와 백엔드(8080)가 따로 뜬다. 브라우저가 `/api/...`를 5173에 보내면 Vite가 8080으로 넘긴다(`vite.config.ts`의 `server.proxy`). 브라우저 입장에서는 같은 출처라 CORS 설정이 필요 없다.
- 배포: `scripts/build-frontend.sh`가 `npm run build` 결과(`frontend/dist`)를 `src/main/resources/static`에 복사하고, Spring Boot가 그 정적 파일을 함께 서빙한다. 그래서 jar 하나로 배포된다. `static/`은 빌드 결과라 git에서 뺐다.

## 막혔던 점

**ERD 제약 이름이 MySQL 64자 제한을 넘었다.** 첫 `./mvnw test`에서 Flyway가 실패했다.

```
Identifier name 'uk_blog_referrer_daily_blog_id_stat_date_referrer_type_referrer_host' is too long
```

- 원인: MySQL은 테이블·컬럼·제약 이름이 64자까지다. Crowfoot이 `uk_{테이블}_{컬럼들}`로 자동으로 이름을 지어 68자가 됐다.
- 다른 문제가 더 있는지 보려고, 그 이름만 줄인 임시 사본을 개발 MySQL의 임시 DB에 돌려 봤다 → 테이블 26개가 모두 생김.
- V1은 `schema.sql` 그대로여야 하므로 코드에서 고치지 않고 Crowfoot에서 `uk_blog_referrer_daily_key`로 바꾼 뒤 다시 내보냈다(문서 버전 75).
- 배운 점: 명세(ERD)가 원본이면 **원본을 고치고 다시 내려받는다**. 사본만 고치면 다음에 다시 내보낼 때 같은 문제가 돌아온다.

**포트 충돌.** 로컬에 Homebrew Redis가 6379를 쓰고 있어서 `brew services stop redis`로 껐다. `lsof -iTCP:6379 -sTCP:LISTEN`으로 누가 포트를 쓰는지 볼 수 있다.

## 직접 해 보기

```bash
docker compose up -d && docker compose ps            # 두 컨테이너가 healthy인지
./mvnw spring-boot:run                               # 로그에서 "Migrating schema" 찾기
docker exec blog-mysql mysql -ublog -pblog blog -e "SHOW TABLES; SELECT * FROM flyway_schema_history"
./mvnw test                                          # 테스트 중 docker ps를 보면 컨테이너가 하나 더 뜬다
cd frontend && npm run dev                           # http://localhost:5173
```

## 더 공부할 거리

- Flyway의 `baseline`, `repair`, `outOfOrder`가 각각 언제 필요한가
- Spring Boot 자동 설정이 어떻게 동작하나(`@ConditionalOnClass`, `AutoConfiguration.imports`)
- Testcontainers의 컨테이너 재사용(`reuse`)과 Spring 테스트 컨텍스트 캐싱
- Docker 볼륨과 바인드 마운트의 차이
