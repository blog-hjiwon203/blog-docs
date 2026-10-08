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

## 이 스텝을 이해하려면 (읽는 순서)

이 스텝은 "코드를 돌릴 판"을 깐 것이라, 아래 순서로 읽으면 판이 어떻게 짜였는지 보인다.

| 순서 | 개념 문서 | 이 스텝에서 그 개념이 쓰인 곳 |
| --- | --- | --- |
| 1 | [Spring Boot 기초: 컨테이너, 빈, 스타터, 자동 설정](./concepts/01-spring-boot-basics.md) | `pom.xml`에 스타터를 더하자 Redis·Flyway·캐시가 설정 없이 켜진 이유. Spring Boot 4에서 바뀐 이름들 |
| 2 | [설정 파일과 프로필](./concepts/02-configuration-profiles.md) | `application.yml`과 `-dev`·`-prod`, 시간대를 다섯 곳에서 맞춘 이유 |
| 3 | [Flyway와 스키마 마이그레이션](./concepts/03-flyway-migration.md) | `V1__init.sql`, `ddl-auto=validate`, 64자 제약 이름 사건 |
| 4 | [Docker와 Docker Compose](./concepts/04-docker-compose.md) | `docker-compose.yml`의 항목 하나하나, 6379 포트 충돌 |
| 5 | [Spring 테스트와 Testcontainers](./concepts/05-spring-testing.md) | `TestcontainersConfiguration`, `@ServiceConnection`, H2를 안 쓰는 이유 |
| 6 | [SPA와 서버 라우팅](./concepts/18-spa-server-routing.md)의 Vite·빌드 부분 | `vite.config.ts` 프록시, `scripts/build-frontend.sh`로 jar 하나 배포 |

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
