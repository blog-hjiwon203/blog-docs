# 03. Flyway와 DB 마이그레이션

> 관련 스텝: [스텝 1](../step-01.md)(V1), [스텝 2](../step-02.md)(V2, validate) · 먼저 읽을 것: [02. 설정과 프로필](./02-configuration-profiles.md) · 다음: [06. JPA 엔티티 매핑](./06-jpa-entity-mapping.md)

## 1. 이 문서로 배우는 것

- 스키마(테이블 구조)를 코드처럼 관리해야 하는 이유
- **마이그레이션**이 무엇이고 Flyway가 어떻게 실행하는지
- 파일 이름 규칙, `flyway_schema_history` 테이블, **체크섬**
- 이미 적용된 파일을 고치면 생기는 일과 올바른 변경 방법
- JPA `ddl-auto`의 값별 의미와 이 프로젝트가 `validate`를 쓰는 이유
- MySQL에서 DDL이 실패하면 **되돌려지지 않는** 점
- 데이터 마이그레이션(V2 관리자 계정), ERD → `schema.sql` → V1 흐름과 64자 사건

**먼저 알면 좋은 것**: `CREATE TABLE`, `ALTER TABLE`, `INSERT`가 무엇인지, 트랜잭션(커밋·롤백)의 뜻.

---

## 2. 왜 필요한가

DB 테이블을 손으로 만든다고 해 보자.

- 지원이 노트북 MySQL에서 `ALTER TABLE post ADD COLUMN topic ...`을 실행했다. 팀원 노트북, 테스트 DB, 운영 DB에도 **똑같이, 같은 순서로** 실행해야 한다. 하나라도 빠지면 그 환경에서만 "컬럼이 없다" 오류가 난다.
- 석 달 뒤 "운영 DB에는 어떤 변경까지 들어가 있지?"를 아무도 모른다.
- 새 팀원이 오면 지금 스키마를 처음부터 만드는 방법이 없다.

코드는 git으로 "언제, 누가, 무엇을" 바꿨는지 남는데 DB 구조는 남지 않는 것이 문제다. **마이그레이션 도구**는 스키마 변경을 번호 붙은 SQL 파일로 저장소에 두고, 각 DB에 **어디까지 적용했는지 기록**하면서 빠진 것만 실행한다.

---

## 3. 기본 개념

### 3.1 용어

| 용어 | 뜻 |
| --- | --- |
| 스키마 | 테이블, 컬럼, 제약, 인덱스 같은 DB 구조 |
| 마이그레이션 | 스키마(또는 데이터)를 한 단계 바꾸는 SQL 묶음 하나. 파일 하나 = 버전 하나 |
| DDL | 구조를 바꾸는 SQL(`CREATE`, `ALTER`, `DROP`) |
| DML | 데이터를 바꾸는 SQL(`INSERT`, `UPDATE`, `DELETE`) |
| 체크섬 | 파일 내용으로 계산한 숫자. 내용이 한 글자만 바뀌어도 달라진다 |

### 3.2 파일 이름 규칙

```
V2__admin_account.sql
│ │ │
│ │ └─ 설명 (밑줄은 공백으로 표시됨: "admin account")
│ └─── 밑줄 두 개 (구분자)
└───── V + 버전 번호 (1, 2, 3 ... 또는 1.1, 2026.10.08 등)
```

| 접두사 | 뜻 | 실행 |
| --- | --- | --- |
| `V` | 버전 마이그레이션 | 버전 순서대로 **한 번만** |
| `R` | 반복 마이그레이션(뷰, 함수 등) | 내용이 바뀔 때마다 다시 |
| `U` | 되돌리기(유료 기능) | 이 프로젝트에서는 안 씀 |

- 위치: `src/main/resources/db/migration/` (`spring.flyway.locations: classpath:db/migration`).
- 밑줄이 하나면(`V2_admin.sql`) 버전으로 인식되지 않는다.

### 3.3 `flyway_schema_history`

Flyway는 대상 DB에 이 테이블을 만들고, 적용한 마이그레이션마다 한 행을 남긴다.

| installed_rank | version | description | script | checksum | success |
| --- | --- | --- | --- | --- | --- |
| 1 | 1 | init | V1__init.sql | 123456789 | 1 |
| 2 | 2 | admin account | V2__admin_account.sql | -98765432 | 1 |

다음에 앱이 뜨면 Flyway는 파일 목록과 이 테이블을 비교해서

```
파일:  V1  V2  V3
기록:  V1  V2
       └───┴── 이미 적용됨: 체크섬만 비교
               V3: 새 파일 → 실행하고 기록 추가
```

### 3.4 JPA `ddl-auto`

JPA(Hibernate)도 엔티티를 보고 테이블을 만들 수 있다. `spring.jpa.hibernate.ddl-auto` 값에 따라 다르다.

| 값 | 하는 일 | 쓸 만한 곳 |
| --- | --- | --- |
| `create` | 시작할 때 테이블을 지우고 엔티티대로 새로 만듦 | 학습용 장난감 |
| `create-drop` | `create` + 끝날 때 지움 | 일회성 테스트 |
| `update` | 엔티티에 있고 테이블에 없는 것을 추가(지우거나 바꾸지는 않음) | 위험. 의도치 않은 컬럼이 운영에 생긴다 |
| `validate` | 아무것도 바꾸지 않고, 엔티티와 테이블이 맞는지만 확인. 다르면 시작 실패 | **이 프로젝트** |
| `none` | 아무것도 안 함 | 확인도 원하지 않을 때 |

Flyway와 JPA가 둘 다 테이블을 바꾸면 누가 원본인지 모르게 된다. 그래서 **바꾸는 것은 Flyway만, JPA는 확인만**으로 역할을 나눴다.

---

## 4. 동작 원리

앱이 시작될 때 순서(01 문서 4절의 6단계 안):

```
1. DataSource(DB 연결 풀) 생성
2. FlywayAutoConfiguration → Flyway.migrate()
   2-1. flyway_schema_history가 없으면 만든다
   2-2. classpath:db/migration의 파일을 버전 순으로 읽는다
   2-3. 이미 적용된 파일: 체크섬을 기록과 비교 → 다르면 "Validate failed" 로 시작 중단
   2-4. 기록에 실패(success=0)한 행이 있으면 시작 중단 (repair 필요)
   2-5. 새 파일: 실행 → 성공하면 기록(success=1)
3. EntityManagerFactory 생성 → ddl-auto=validate로 엔티티 ↔ 테이블 비교
4. 나머지 빈 생성 → 서버 시작
```

Flyway가 JPA보다 **먼저** 실행되도록 Spring Boot가 순서를 잡아 준다. 그래야 validate가 최신 테이블과 비교한다.

### 4.1 체크섬과 "이미 적용된 파일은 고치지 않는다"

V1을 적용한 뒤 V1 파일의 주석 한 줄만 고쳐도 체크섬이 달라진다. 다음 시작에서:

```
Validate failed: Migrations have failed validation
Migration checksum mismatch for migration version 1
-> Applied to database : 1234567
-> Resolved locally    : 7654321
```

Flyway가 이렇게 깐깐한 이유는, **이미 운영 DB에 적용된 변경은 파일을 고쳐도 운영 DB에 다시 실행되지 않기** 때문이다. 파일과 실제 DB가 달라지는 것을 막으려고 시작을 멈춘다.

**올바른 변경 방법**: 기존 파일은 그대로 두고 새 번호 파일을 더한다.

```sql
-- V3__post_add_pinned.sql
ALTER TABLE post ADD COLUMN is_pinned TINYINT(1) NOT NULL DEFAULT 0;
```

예외: **아직 어디에도 적용되지 않은** 파일은 고쳐도 된다. 스텝 1에서 V1이 Flyway 실패로 개발 DB에 적용되지 않았을 때 V1을 새 `schema.sql`로 다시 복사한 것이 그 경우다.

### 4.2 MySQL DDL은 롤백되지 않는다

PostgreSQL은 DDL도 트랜잭션 안에서 실행돼서 마이그레이션 중간에 실패하면 통째로 되돌아간다. **MySQL은 `CREATE TABLE`, `ALTER TABLE` 같은 DDL을 실행할 때마다 암묵적으로 커밋**한다. 그래서:

```
V1__init.sql (CREATE TABLE 26개 + ALTER TABLE 38개 + CREATE INDEX 20개)
  CREATE TABLE member ...            ✓ 커밋됨
  CREATE TABLE social_account ...    ✓ 커밋됨
  ...
  CREATE TABLE blog_referrer_daily   ✗ 오류
  → 앞의 테이블들은 남아 있고, flyway_schema_history에는 실패 기록
```

이 상태에서는 다시 실행해도 "이미 테이블이 있다" 또는 "실패한 마이그레이션이 있다"로 막힌다. 해결:

- 개발 DB: 볼륨을 지우고 처음부터(`docker compose down -v` → `up -d`, [04 문서](./04-docker-compose.md)). 또는 생긴 테이블을 지우고 `flyway repair`로 실패 기록을 정리.
- 운영 DB: 손으로 정리해야 해서 위험하다. 그래서 **운영에 가기 전에 테스트(Testcontainers)에서 반드시 한 번 실행**해 본다.

스텝 1에서 V1이 실패했을 때 `./mvnw spring-boot:run`을 **일부러 개발 DB에 돌리지 않은** 이유가 이것이다. 테스트는 매번 새 컨테이너라 부분 적용이 남지 않는다.

### 4.3 데이터 마이그레이션

마이그레이션은 구조만이 아니라 **꼭 있어야 하는 데이터**에도 쓴다. 이 프로젝트는 관리자를 가입으로 만들 수 없고 데이터로만 정하기 때문에(ADMIN-01), 관리자 계정을 V2로 넣었다. 모든 환경(개발, 테스트, 운영)에 똑같이 한 번만 들어간다는 장점이 있다.

---

## 5. 이 프로젝트에서는

### 5.1 흐름: ERD → schema.sql → V1

```
Crowfoot ERD (문서 665)         ← 원본. 여기서 고친다
   │ 내보내기(export_ddl)
   ▼
blog-docs/specs/001-tistory-blog/erd/schema.sql   ← 문서 저장소에 버전 관리
   │ 그대로 복사 (한 글자도 고치지 않음)
   ▼
blog/src/main/resources/db/migration/V1__init.sql ← Flyway가 실행
   │
   ▼
MySQL: 테이블 26개 + flyway_schema_history
```

`V1__init.sql`의 첫 줄:

```sql
-- Crowfoot 문서 665 버전 75 (2026-10-08)에서 내보낸 MySQL DDL. 직접 고치지 말고 Crowfoot을 고친 뒤 다시 내보낸다.
```

원본이 하나(ERD)라서, 문서의 표와 실제 DB가 어긋나지 않는다. 같은 내용인지는 `cmp`로 확인한다.

```bash
cmp ../blog-docs/specs/001-tistory-blog/erd/schema.sql src/main/resources/db/migration/V1__init.sql && echo same
```

### 5.2 64자 사건 (스텝 1)

처음 내보낸 `schema.sql`(버전 74)로 테스트를 돌리자:

```
SQLSyntaxErrorException: Identifier name
'uk_blog_referrer_daily_blog_id_stat_date_referrer_type_referrer_host' is too long
```

- MySQL은 테이블·컬럼·인덱스·제약 이름을 **64자**까지만 허용한다. Crowfoot이 `uk_{테이블}_{컬럼들}`로 이름을 자동으로 지어 68자가 됐다.
- 다른 문제가 더 있는지 보려고, 그 이름만 줄인 **임시 사본**을 개발 MySQL의 임시 DB(`scratch`)에 실행해 봤다 → 테이블 26개가 다 생김.
- V1을 직접 고치지 않고 **원본(Crowfoot)**에서 `uk_blog_referrer_daily_key`로 바꿔 다시 내보냈다(버전 75). 사본만 고치면 다음에 다시 내보낼 때 같은 문제가 돌아온다.

```sql
-- V1__init.sql 282행 (버전 75)
CONSTRAINT uk_blog_referrer_daily_key UNIQUE (blog_id, stat_date, referrer_type, referrer_host)
```

### 5.3 V2: 관리자 초기 계정

`src/main/resources/db/migration/V2__admin_account.sql`

```sql
-- 서비스 관리자 초기 계정 (ADMIN-01). 관리자는 이 데이터로만 정한다.
-- 개발용 값이다: admin@blog.test / admin1234! (bcrypt). 운영에 올리기 전에 비밀번호를 바꾼다.
INSERT INTO member (email, password_hash, nickname, role, status)
VALUES ('admin@blog.test', '$2a$10$1XrAfK4aVBNuC7uNq35kiuugsN.I0RN6Ynqh4Bj6xqJy4B1SUTfB6', 'admin', 'ADMIN', 'ACTIVE');
```

- `password_hash`는 bcrypt 해시다. 평문 비밀번호는 파일 어디에도 없다([09](./09-password-hashing.md)).
- `created_at`, `updated_at`은 적지 않았다. 테이블의 `DEFAULT CURRENT_TIMESTAMP(6)`이 채운다.
- 이 파일은 저장소에 있으므로 해시가 공개된다. 개발용 값이라 운영 전에는 비밀번호를 바꿔야 한다. 새 해시를 다시 마이그레이션 파일로 넣으면 그것도 저장소에 공개되므로, 운영에서는 비밀번호 변경 기능이나 운영 DB 작업 같은 별도 절차가 필요하다(아직 정하지 않았다).

### 5.4 설정

`application.yml`

```yaml
spring:
  jpa:
    hibernate:
      ddl-auto: validate              # JPA는 확인만
  flyway:
    enabled: true
    locations: classpath:db/migration
```

`pom.xml`

```xml
<artifactId>spring-boot-starter-flyway</artifactId>   <!-- Boot 4: 자동 설정 모듈을 가져온다 -->
<artifactId>flyway-mysql</artifactId>                 <!-- Flyway 10+는 DB별 모듈을 따로 넣는다 -->
```

### 5.5 validate가 잡아 준 것

`ddl-auto=validate`는 엔티티 필드 하나하나를 테이블 컬럼과 비교한다. 예를 들어 `Post.contentHtml`을 그냥 `String`으로 두면 Hibernate는 `varchar(255)`를 기대하는데 테이블은 `mediumtext`라서 시작이 실패한다. 그래서 `@Column(columnDefinition = "mediumtext")`를 붙였다([06](./06-jpa-entity-mapping.md)). 엔티티와 테이블이 어긋나는 것을 **실행 중이 아니라 시작할 때** 알 수 있다.

### 5.6 테스트에서

`src/test/java/com/nhnacademy/blog/BlogApplicationTests.java`

```java
@Test
void flywayCreatesAllErdTables() {
    Integer tables = jdbcTemplate.queryForObject(
            "SELECT COUNT(*) FROM information_schema.tables "
                    + "WHERE table_schema = DATABASE() AND table_type = 'BASE TABLE' "
                    + "AND table_name <> 'flyway_schema_history'",   // Flyway 기록 테이블은 빼고
            Integer.class);

    assertThat(tables).isEqualTo(26);                                 // ERD의 테이블 수
}
```

`AdminAccountMigrationTest`는 V2가 넣은 관리자의 역할·상태·비밀번호 해시를 확인한다. 둘 다 Testcontainers의 새 MySQL에서 V1, V2를 처음부터 실행한 결과를 본다.

---

## 6. 자주 하는 실수와 함정

| 실수 | 증상 | 해결 |
| --- | --- | --- |
| 적용된 V 파일을 수정 | `checksum mismatch`로 시작 실패 | 되돌리고 새 번호 파일로 |
| 두 사람이 같은 번호(V3)를 만듦 | 병합 후 하나가 무시되거나 오류 | 브랜치를 합치기 전에 번호 확인. 날짜 버전(`V2026_10_08_1__`)을 쓰는 팀도 있다 |
| 밑줄 하나(`V3_add.sql`) | 파일이 무시됨 | `V3__add.sql` |
| `ddl-auto=update`로 운영 | 엔티티 실수가 운영 스키마에 그대로 반영 | `validate` |
| MySQL에서 마이그레이션 중간 실패 | 테이블 일부만 생성, 이후 시작마다 실패 | 개발은 볼륨 초기화, 운영은 미리 테스트로 검증 |
| 이름이 64자 초과 | `Identifier name ... is too long` | 짧은 이름 규칙 |
| 마이그레이션에 환경별 데이터(테스트 회원 등)를 넣음 | 운영 DB에 테스트 데이터가 들어감 | 테스트 데이터는 테스트 코드에서 만든다(`TestMembers`) |
| `flyway-mysql`을 빼먹음 | `Unsupported Database: MySQL` | DB별 모듈 추가 |

---

## 7. 직접 해 보기

1. **기록 테이블 보기**
   ```bash
   docker exec blog-mysql mysql -ublog -pblog blog \
     -e "SELECT installed_rank, version, description, checksum, success FROM flyway_schema_history"
   ```

2. **체크섬 위반 만들어 보기** (개발 DB에서, 끝나면 되돌린다)
   - `V2__admin_account.sql` 맨 아래에 빈 주석 줄 `-- test`를 더하고 `./mvnw spring-boot:run`.
   - 기대: `Migration checksum mismatch for migration version 2`로 시작 실패.
   - 파일을 되돌리면 다시 뜬다.

3. **새 마이그레이션 흐름 연습** (브랜치에서만, 커밋하지 않는다)
   - `V3__practice.sql`에 `CREATE TABLE practice (id BIGINT PRIMARY KEY);`를 쓰고 실행.
   - `flyway_schema_history`에 3번이 생긴 것을 확인.
   - 연습이 끝나면 파일을 지우고, 개발 DB는 `docker compose down -v && docker compose up -d`로 초기화한다(볼륨이 지워져 모든 데이터가 사라진다).

4. **validate 실패 보기**
   - `Post.java`의 `@Column(name = "content_html", ..., columnDefinition = "mediumtext")`에서 `columnDefinition`을 지우고 `./mvnw test -Dtest=BlogApplicationTests`.
   - 기대: `Schema-validation: wrong column type encountered in column [content_html]` 비슷한 오류. 되돌린다.

5. **schema.sql과 V1이 같은지 확인**
   ```bash
   cmp ../blog-docs/specs/001-tistory-blog/erd/schema.sql src/main/resources/db/migration/V1__init.sql && echo same
   ```

---

## 8. 확인 문제

1. 손으로 `ALTER TABLE`을 실행하는 대신 마이그레이션 파일을 쓰면 무엇이 좋아지나? 두 가지 이상.
   <details><summary>답</summary>모든 환경(개발·테스트·운영)에 같은 변경이 같은 순서로 적용된다. 변경 이력이 git에 남는다. 각 DB에 어디까지 적용됐는지 `flyway_schema_history`로 알 수 있다. 새 환경을 처음부터 만들 수 있다.</details>

2. 이미 운영에 적용된 `V2`의 오타를 고치고 싶다. 어떻게 해야 하나?
   <details><summary>답</summary>V2는 그대로 두고, 고치는 내용을 새 번호 파일(V3 등)로 더한다. V2를 고치면 체크섬이 달라져 시작이 실패하고, 고쳐도 운영 DB에는 다시 실행되지 않는다.</details>

3. 이 프로젝트가 `ddl-auto=update`가 아니라 `validate`를 쓰는 이유는?
   <details><summary>답</summary>스키마의 원본은 ERD와 Flyway 파일 하나여야 하는데, JPA가 테이블을 바꾸면 원본이 둘이 된다. validate는 바꾸지 않고 엔티티가 테이블과 맞는지만 확인해서, 어긋나면 시작할 때 알려 준다.</details>

4. MySQL에서 V1 실행 중 25번째 `CREATE TABLE`에서 실패했다. DB에는 무엇이 남나?
   <details><summary>답</summary>앞의 24개 테이블. MySQL DDL은 문장마다 암묵적으로 커밋되어 롤백되지 않는다. `flyway_schema_history`에는 실패 기록이 남아 다음 시작도 막힌다.</details>

5. 64자 문제를 V1을 직접 고치지 않고 Crowfoot에서 고친 이유는?
   <details><summary>답</summary>V1은 ERD에서 내보낸 schema.sql의 사본이다. 사본만 고치면 원본(ERD)과 달라지고, 다음에 ERD를 다시 내보낼 때 같은 문제가 돌아온다.</details>

6. 관리자 계정을 `data.sql`이나 애플리케이션 시작 코드가 아니라 Flyway V2로 넣으면 좋은 점은?
   <details><summary>답</summary>모든 환경에 정확히 한 번만 들어가고(기록으로 중복 방지), 언제 들어갔는지 이력이 남으며, 스키마 변경과 같은 순서 체계 안에서 관리된다.</details>

7. 앱 시작 때 Flyway와 JPA validate 중 무엇이 먼저 실행되어야 하나? 왜?
   <details><summary>답</summary>Flyway가 먼저. 테이블을 최신 상태로 만든 다음에 validate가 엔티티와 비교해야 맞는 결과가 나온다.</details>

---

## 9. 더 읽을거리

- Flyway 공식 문서 "Concepts > Migrations", "Commands > migrate / validate / repair" (https://documentation.red-gate.com/flyway)
- Spring Boot 공식 문서 "Database Initialization > Use a Higher-level Database Migration Tool"
- Hibernate ORM 사용자 가이드 "Schema generation" — `hbm2ddl.auto` 값
- MySQL 8.4 Reference Manual "Statements That Cause an Implicit Commit", "Identifier Length Limits"
