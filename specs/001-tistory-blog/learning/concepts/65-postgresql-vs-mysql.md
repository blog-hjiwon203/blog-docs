# 65. PostgreSQL vs MySQL: DB 두 개를 하나로 합쳐도 될까

> 관련 스텝: [스텝 1](../step-01.md), [스텝 10](../step-10.md) (T069a~d) · 관련 개념: [42-second-db-async-events](./42-second-db-async-events.md), [41-embedding-vector-search](./41-embedding-vector-search.md), [03-flyway-migration](./03-flyway-migration.md), [32-search-like](./32-search-like.md), [57-spam-block-banned-words](./57-spam-block-banned-words.md), [33-isolation-deadlock](./33-isolation-deadlock.md), [64-cache-store-choice](./64-cache-store-choice.md)

> **한 줄 답**: 설계만 보면 **PostgreSQL 하나에 pgvector를 같이 두는 것**이 가장 낫다. 추천의 "볼 수 없는 글 빼기"를 SQL 한 번에 하고, 외래 키와 한 트랜잭션을 쓸 수 있기 때문이다. 그래도 지금 MySQL을 주 DB로 둔 데는 이유가 있다. 운영 서버의 DB가 MySQL이고(추측, 5.2), 코드가 MySQL 전용 문법과 대소문자 무시 비교에 기대고 있다(5.4).

## 1. 이 문서로 배우는 것

- PostgreSQL과 MySQL의 **같은 점**(관계형, SQL, 트랜잭션, JPA로 거의 같게 씀)과 **다른 점**(확장, 문법, 문자열 비교, 기능 범위)
- 이 프로젝트가 DB를 **두 개** 쓰는 구조와 그 대가
- 선택지 셋 비교: ① 지금처럼 둘 ② 전부 PostgreSQL ③ 전부 MySQL
- "설계상 가장 나은 방안"을 고르는 근거: 데이터를 한 곳에 두면 얻는 것
- 이 프로젝트를 PostgreSQL로 옮길 때 고칠 곳(실제로 센 개수)
- 두 DB가 오히려 나은 경우

**먼저 알면 좋은 것**: 두 번째 DB와 최종 일관성([42](./42-second-db-async-events.md) 3.3), pgvector와 추천에서 볼 수 없는 글 거르기([41](./41-embedding-vector-search.md) 3.4, 3.6), Flyway([03](./03-flyway-migration.md)).

## 2. 왜 필요한가

스텝 10에서 "비슷한 글 추천"을 만들며 PostgreSQL을 하나 더 띄웠다. 주 데이터는 MySQL, 글 임베딩만 PostgreSQL이다. 그러자 이런 질문이 생긴다.

- 두 DB는 무엇이 다른가? 그냥 하나로 합치면 안 되나?
- 합친다면 어느 쪽으로? 시간을 생각하지 않으면 무엇이 설계상 가장 나은가?

[42](./42-second-db-async-events.md)는 "두 DB를 어떻게 함께 쓰나"를 다뤘다. 이 문서는 한 걸음 물러서서 "애초에 둘이어야 하나"를 판단한다.

## 3. 기본 개념

### 3.1 같은 점

둘 다 **관계형 DB**다. 표·행·칸, SQL, 기본 키·외래 키·UNIQUE, 트랜잭션과 격리 수준, 인덱스(B-Tree)를 쓴다. JPA로 짠 평범한 CRUD는 드라이버와 방언(dialect)만 바꾸면 거의 그대로 돈다. 학교 실습·작은 서비스에서는 어느 쪽을 골라도 큰 차이가 없다.

### 3.2 이 프로젝트에 영향을 주는 차이

| 항목 | MySQL 8 (InnoDB) | PostgreSQL 17 |
| --- | --- | --- |
| 확장(extension) | 없음. 기능은 버전에 따라 들어옴 | `CREATE EXTENSION`으로 기능을 붙임. **pgvector**, PostGIS(지도), pg_trgm(유사 문자열) 등 |
| 벡터 검색 | MySQL 9부터 `VECTOR` 타입이 있지만, 거리 계산과 벡터 인덱스는 일반(Community) 판에 없다(확인 필요: 버전마다 바뀜) | pgvector로 `vector(n)`, 거리 연산자 `<=>`, HNSW 인덱스 |
| 문자열 비교 | 칸의 콜레이션을 따름. 이 프로젝트 `utf8mb4_0900_ai_ci`는 **대소문자 무시** | 기본은 **대소문자 구분**. 무시하려면 `ILIKE`, `lower()`, `citext` 확장, 비결정적 콜레이션 |
| "있으면 무시하고 넣기" | `INSERT IGNORE` | `INSERT … ON CONFLICT DO NOTHING` |
| 다른 표를 보며 고치기 | `UPDATE a JOIN b ON … SET …` | `UPDATE a SET … FROM b WHERE …` |
| 수정 시각 자동 갱신 | 칸 정의에 `ON UPDATE CURRENT_TIMESTAMP` | 없음. 트리거를 만들거나 애플리케이션(JPA Auditing)이 넣음 |
| 계산 칸 | `GENERATED ALWAYS AS (…) STORED` | 같은 문법 있음(STORED만) |
| 번호 자동 증가 | `AUTO_INCREMENT` | `GENERATED … AS IDENTITY`(또는 `BIGSERIAL`) |
| 날짜 시각 | `DATETIME(6)` (시간대 없음) | `TIMESTAMP` / `TIMESTAMPTZ`(시간대 있음) |
| 부분 인덱스 | 없음(계산 칸 + UNIQUE로 흉내) | `CREATE UNIQUE INDEX … WHERE 조건` |
| 기본 격리 수준 | REPEATABLE READ | READ COMMITTED |
| DDL과 트랜잭션 | `CREATE TABLE` 등이 자동 커밋. 마이그레이션 중간 실패 시 반쯤 남음 | DDL도 트랜잭션 안에서 되돌릴 수 있음 |

마지막 세 줄은 이 프로젝트에서 바로 문제가 되진 않지만, 옮길 때 행동이 달라지는 지점이라 적었다. 격리 수준이 다르면 [33](./33-isolation-deadlock.md)에서 본 잠금·스냅샷 동작도 조금 달라진다.

### 3.3 데이터를 한 곳에 두면 얻는 것

[42](./42-second-db-async-events.md) 3.3에 "DB 두 개 사이에 없는 것"이 있다.

| DB 사이에 없는 것 | 한 DB면 |
| --- | --- |
| 외래 키 | `post_embedding.post_id → post.id`, `ON DELETE CASCADE`로 글을 지우면 임베딩도 저절로 |
| 한 트랜잭션 | 글 저장과 임베딩 행이 같이 커밋되거나 같이 롤백(임베딩 계산 자체는 여전히 커밋 뒤 비동기가 낫다) |
| 조인 | 가까운 글 찾기 + 볼 수 있는지 확인을 SQL 하나로 |

마지막이 특히 크다. 지금은 이렇게 두 번 묻는다([41](./41-embedding-vector-search.md) 3.6).

```
① PostgreSQL: 이 글과 가까운 글 30개 (후보)
② MySQL:      그중 보는 사람이 볼 수 있는 글 → 6개 채우기
```

볼 수 없는 글이 많으면 30개를 뽑아도 6개가 안 찰 수 있다. 그래서 후보를 넉넉히(`CANDIDATES = 30`) 뽑는다. 한 DB면 이렇게 된다.

```sql
SELECT p.id
FROM post_embedding e
JOIN post p ON p.id = e.post_id
WHERE e.post_id <> :postId
  AND p.status = 'PUBLISHED' AND p.deleted_at IS NULL
  AND p.visibility = 'PUBLIC' AND NOT p.is_blinded   -- 실제로는 가시성 조건 전체(블로그 상태 등)
ORDER BY e.embedding <=> (SELECT embedding FROM post_embedding WHERE post_id = :postId)
LIMIT 6;
```

조건을 먼저 걸고 가까운 순으로 자르니 "모자라면 더 뽑기"가 필요 없다. (참고: HNSW 인덱스는 근사 검색이라, 조건이 아주 까다로우면 인덱스가 찾은 후보가 걸러져 모자랄 수 있다. pgvector 0.8부터 이를 보완하는 반복 스캔 옵션이 있다.)

## 4. 동작 원리: 선택지 셋 비교

| | ① 지금: MySQL + PostgreSQL | ② 전부 PostgreSQL + pgvector | ③ 전부 MySQL |
| --- | --- | --- | --- |
| 추천 가시성 거르기 | 두 번 묻고 후보를 넉넉히 | **SQL 한 번** | 벡터를 BLOB/JSON으로 두고 자바에서 계산, 또는 MySQL 9 `VECTOR`(거리 계산 제약) |
| 외래 키·트랜잭션 | 없음, 정리 작업으로 맞춤 | **있음** | 있음 |
| 운영할 것 | DB 두 개, DataSource 두 개, Flyway 두 벌, 테스트 컨테이너 둘 | **하나씩** | 하나씩 |
| 글이 많아지면 | 잘 버팀(HNSW) | **잘 버팀(HNSW)** | 자바 계산은 글 수만큼 느려짐 |
| 기능째 빼기 | 쉬움(설정 하나로 끔) | 쉬움(표 하나, 설정으로 끔) | 쉬움 |
| 지금 코드에서 바꿀 양 | 없음 | 많음(5.4) | 추천 부분만 |
| 운영 서버 제약 | 맞음(운영은 MySQL, 추천은 꺼 둠) | 운영 DB를 바꿀 수 있어야 함 | 맞음 |

**설계만 보면 ②가 가장 낫다.** 데이터의 진실이 한 곳에 있어서 규칙(외래 키, 가시성)을 DB가 함께 지키고, 운영할 것이 줄고, 규모가 커져도 벡터 검색이 버틴다.

**③은 작은 규모에서만 맞는 임시 방안**이다. 글 전부의 벡터를 읽어 자바에서 코사인을 계산하면 글 수에 비례해 느려진다. 수천 개까지는 괜찮지만 설계로 권할 답은 아니다.

**①이 더 나은 경우**도 있다. 벡터 데이터가 아주 커서 본 DB와 따로 키워야 할 때, 검색 부하가 본 DB를 느리게 할 때, 전용 벡터 DB(Qdrant, Pinecone 등)를 쓸 때다. 또는 지금처럼 **본 DB를 고를 수 없는데**(운영 제약) 벡터 기능이 필요할 때다.

## 5. 이 프로젝트에서는

### 5.1 지금 구조

| | 개발 (`docker-compose.yml`) | 운영 (`deploy/deploy.sh`) |
| --- | --- | --- |
| 주 DB | `mysql:8.4`, 콜레이션 `utf8mb4_0900_ai_ci` | `DB_URL=jdbc:mysql://${DB_ADDRESS}…` (서버가 띄우지 않고 받아 씀) |
| 추천 DB | `pgvector/pgvector:pg17` | 없음. `APP_RECOMMEND_ENABLED` 기본 `false`라 추천이 꺼짐 |
| Flyway | `db/migration`(MySQL), `db/recommend`(PostgreSQL) | `db/migration`만 |

추천 쪽 설정은 `recommend/config/RecommendDataSourceConfig`가 `@ConditionalOnProperty(name = "app.recommend.enabled", matchIfMissing = true)`로 켜고 끈다. 두 번째 DataSource를 만드는 법은 [42](./42-second-db-async-events.md) 3.2.

### 5.2 왜 주 DB가 MySQL인가

- 처음 설계(research R-02)에서 주 DB를 MySQL로, 추천은 도전 과제라 떼어 낼 수 있게 PostgreSQL로 나눴다([41](./41-embedding-vector-search.md) 3.4).
- 운영 서버의 DB 주소를 `DB_ADDRESS`로 받아 `jdbc:mysql://`로 붙는다. 배포 스크립트가 DB 컨테이너를 띄우지 않으므로, **학교 실습 서버가 MySQL을 제공하는 것으로 보인다**(코드에서 추측한 것). 그렇다면 ②로 가려면 운영 DB부터 바꿀 수 있어야 한다.

### 5.3 그래서 이 프로젝트의 답

- **처음부터 고를 수 있었다면**: ② PostgreSQL 하나 + pgvector.
- **지금 운영 DB가 MySQL로 정해져 있다면**: ① 그대로(추천은 개발에서만 켬)가 현실적인 답이다. 추천을 운영에도 켜고 싶은데 DB를 하나만 쓸 수 있다면 ③(자바 계산)이 차선이다.

### 5.4 PostgreSQL로 옮길 때 고칠 곳 (코드에서 센 것)

| 무엇 | 어디 | 개수 | 바꾸는 법 |
| --- | --- | --- | --- |
| `INSERT IGNORE` | 공감, 구독, 저장, 태그, 신고, 차단, 금칙어, 방문 기록 Repository의 네이티브 쿼리 | 8곳 | `INSERT … ON CONFLICT DO NOTHING`. "넣은 행 수"(0 또는 1)로 판단하는 코드는 그대로 동작 |
| `UPDATE … JOIN` | `MemberTraceCleaner`(2), `BlogContentCleaner`(1), `BlogStatsRepository`(1) | 4곳 | `UPDATE … SET … FROM … WHERE …` |
| `ON UPDATE CURRENT_TIMESTAMP` | `V1__init.sql`의 `updated_at` | 9개 표 | 트리거, 또는 JPA Auditing에 맡기고 네이티브 UPDATE에서 직접 넣기. "숨겨도 수정 시각 그대로"([53](./53-admin-moderation-audit.md)) 같은 규칙을 다시 확인 |
| 계산 칸 | `blog.primary_owner_id`, `category.parent_key` | 2개 | 같은 문법이 되지만, PostgreSQL은 부분 UNIQUE 인덱스(`WHERE is_primary AND deleted_at IS NULL`)로 계산 칸 없이 더 간단히 됨 |
| 대소문자 무시 비교 | 검색 LIKE([32](./32-search-like.md)), 금칙어 UNIQUE([57](./57-spam-block-banned-words.md)), 태그 이름 | 여러 곳 | **가장 위험.** 문법 오류 없이 결과만 달라진다. `ILIKE`·`lower()` 인덱스·`citext`·비결정적 콜레이션 중 하나로 맞추고 테스트로 확인 |
| 표 정의 | `V1__init.sql` 371줄(ERD의 schema.sql) | 1개 파일 | `AUTO_INCREMENT`→`IDENTITY`, `DATETIME(6)`→`TIMESTAMP(6)`, `COMMENT` 문법, 엔진·문자셋 옵션 삭제 |
| 설정·도구 | `pom.xml`(MySQL 드라이버·`flyway-mysql`), `docker-compose.yml`, `TestcontainersConfiguration`, `application-*.yml` | 몇 곳 | PostgreSQL 쪽으로. 두 번째 DataSource(`RecommendDataSourceConfig`)와 `db/recommend`는 없앰 |

ENUM 칸은 쓰지 않아서(문자열 + 자바 enum) 고칠 것이 없다. JPA로 짠 대부분의 코드와 Specification도 그대로다.

## 6. 자주 하는 실수와 함정

- **"SQL은 표준이니 DB만 바꾸면 된다"고 믿는다.** 네이티브 쿼리와 마이그레이션 SQL은 DB마다 다르다. 이 프로젝트만 해도 `INSERT IGNORE` 8곳, `UPDATE … JOIN` 4곳이 바로 문법 오류가 난다.
- **문법 오류보다 무서운 "조용한 차이"를 놓친다.** 대소문자 비교가 바뀌면 검색 결과가 줄고 금칙어 "Casino"/"casino"가 둘 다 들어간다. 오류가 안 나서 테스트가 없으면 모른다.
- **DB 두 개를 한 트랜잭션처럼 믿는다.** MySQL이 롤백돼도 PostgreSQL 쓰기는 남는다([42](./42-second-db-async-events.md) 6절).
- **기능 하나 때문에 DB를 하나 더 들인다.** 운영할 것(백업, 연결, 마이그레이션, 테스트)이 두 배가 된다. 먼저 "본 DB에 확장으로 붙일 수 있나"를 본다.
- **벡터를 MySQL에 넣고 SQL로 거리 계산하려 한다.** 일반 MySQL 판에서는 거리 함수·벡터 인덱스가 없어서 결국 전부 읽어야 한다.
- **격리 수준 차이를 잊는다.** 기본값이 REPEATABLE READ(MySQL)에서 READ COMMITTED(PostgreSQL)로 바뀌면, 같은 트랜잭션에서 두 번 읽은 값이 달라질 수 있다. 동시성 테스트([23](./23-transactions-locking.md), [33](./33-isolation-deadlock.md))를 다시 돌린다.

## 7. 직접 해 보기

준비: `docker compose up -d`.

### 7.1 같은 비교, 다른 결과: 대소문자

```bash
docker exec -it blog-mysql mysql -ublog -pblog blog -e "SELECT 'JPA' LIKE '%jpa%' AS mysql_like;"
docker exec -it blog-postgres psql -U blog -d recommend -c "SELECT 'JPA' LIKE '%jpa%' AS pg_like, 'JPA' ILIKE '%jpa%' AS pg_ilike;"
```

MySQL은 1, PostgreSQL `LIKE`는 false, `ILIKE`는 true.

### 7.2 "있으면 무시하고 넣기" 두 가지

```bash
docker exec -it blog-postgres psql -U blog -d recommend -c "
CREATE TEMP TABLE t (id int PRIMARY KEY);
INSERT INTO t VALUES (1) ON CONFLICT DO NOTHING;
INSERT INTO t VALUES (1) ON CONFLICT DO NOTHING;   -- INSERT 0 0
SELECT * FROM t;"
```

MySQL이라면 `INSERT IGNORE INTO t VALUES (1)` 두 번째에 `0 rows affected`.

### 7.3 MySQL 전용 문법 세어 보기

코드 저장소에서:

```bash
grep -rn 'INSERT IGNORE' src/main/java | grep -vE ':[0-9]+:\s+(\*|//)' | wc -l   # 8
grep -c 'ON UPDATE' src/main/resources/db/migration/V1__init.sql                  # 9
grep -rnE 'UPDATE [a-z_]+ [a-z]+\s+JOIN' src/main/java                            # 4줄
```

### 7.4 추천을 꺼 보기

`application-dev.yml`에 `app.recommend.enabled: false`를 넣고 서버를 띄운다. PostgreSQL 컨테이너를 멈춰도(`docker stop blog-postgres`) 서버가 뜨고, 글 상세의 "비슷한 글"은 빈 목록이 된다. 확인 후 되돌린다.

## 8. 확인 문제

1. JPA로 짠 평범한 CRUD는 DB를 바꿔도 거의 그대로인데, 이 프로젝트를 옮길 때 고칠 것이 생기는 이유는?
<details><summary>답</summary>네이티브 쿼리(INSERT IGNORE, UPDATE … JOIN)와 Flyway SQL(AUTO_INCREMENT, ON UPDATE, DATETIME)이 MySQL 문법이고, 대소문자 무시 비교를 MySQL 콜레이션에 기대기 때문이다.</details>

2. PostgreSQL에 있고 MySQL에 없는 것 중 이 프로젝트가 PostgreSQL을 들인 직접적인 이유는?
<details><summary>답</summary>확장(extension), 그중 pgvector. 벡터 칸, 코사인 거리 연산자 <code>&lt;=&gt;</code>, HNSW 인덱스로 비슷한 글을 찾는다.</details>

3. 설계상 "PostgreSQL 하나 + pgvector"가 가장 나은 이유 세 가지는?
<details><summary>답</summary>① 가까운 글 찾기와 가시성 거르기를 SQL 한 번에(후보를 넉넉히 뽑을 필요 없음) ② 외래 키(ON DELETE CASCADE)로 글을 지우면 임베딩도 정리 ③ DB·DataSource·Flyway·테스트 컨테이너가 하나라 운영이 단순.</details>

4. 지금 추천이 후보를 30개 뽑는 이유와, 한 DB면 왜 필요 없나?
<details><summary>답</summary>PostgreSQL에서 가까운 글을 뽑은 뒤 MySQL에서 볼 수 없는 글을 빼면 모자랄 수 있어서 넉넉히 뽑는다. 한 DB면 가시성 조건을 먼저 걸고 가까운 순으로 LIMIT 하므로 모자라지 않는다(단, 근사 인덱스의 한계는 남음).</details>

5. 전부 MySQL로 하고 자바에서 코사인을 계산하는 방식(③)의 한계는?
<details><summary>답</summary>모든 글의 벡터를 읽어 비교해야 해서 글 수에 비례해 느려진다. 인덱스가 없다. 작은 규모의 임시 방안이다.</details>

6. 그런데도 이 프로젝트가 주 DB를 MySQL로 둔 이유(코드에서 보이는 것)는?
<details><summary>답</summary>운영 배포가 DB를 띄우지 않고 <code>DB_ADDRESS</code>로 받아 <code>jdbc:mysql://</code>로 붙는다. 운영 DB가 MySQL로 주어진 것으로 보이고, 추천은 운영에서 꺼 둔다(<code>APP_RECOMMEND_ENABLED</code> 기본 false).</details>

7. PostgreSQL로 옮길 때 가장 위험한 차이는? 왜 위험한가?
<details><summary>답</summary>문자열 대소문자 비교. MySQL 콜레이션(<code>utf8mb4_0900_ai_ci</code>)은 대소문자를 무시하지만 PostgreSQL 기본은 구분한다. 문법 오류 없이 검색 결과나 금칙어·태그 UNIQUE 판단만 달라져서 테스트가 없으면 알아차리기 어렵다.</details>

8. `INSERT IGNORE`를 PostgreSQL로 바꾸면? "넣은 행 수"로 판단하던 코드는?
<details><summary>답</summary><code>INSERT … ON CONFLICT DO NOTHING</code>. 이미 있으면 0행, 새로 넣으면 1행을 돌려주므로 행 수로 판단하는 코드는 그대로 쓸 수 있다.</details>

9. DB 두 개(①)가 오히려 나은 경우는?
<details><summary>답</summary>벡터 데이터나 검색 부하가 커서 본 DB와 따로 키워야 할 때, 전용 벡터 DB를 쓸 때, 본 DB를 고를 수 없는데(운영 제약) 벡터 기능이 필요할 때.</details>

10. `ON UPDATE CURRENT_TIMESTAMP`가 없는 PostgreSQL에서 수정 시각을 맞추는 방법 두 가지는? 이 프로젝트에서 조심할 규칙은?
<details><summary>답</summary>트리거로 UPDATE 때 넣기, 또는 애플리케이션(JPA Auditing·네이티브 UPDATE에서 직접)이 넣기. "관리자가 숨겨도 수정 시각은 그대로" 같은 규칙이 있어서, 트리거를 쓰면 이 경우를 따로 막아야 한다.</details>

## 9. 더 읽을거리

- PostgreSQL 문서, "INSERT … ON CONFLICT", "UPDATE … FROM", "Partial Indexes", "Collation Support"(비결정적 콜레이션)
- MySQL 8.4 레퍼런스, "INSERT IGNORE", "Multiple-Table UPDATE", "Automatic Initialization and Updating for TIMESTAMP and DATETIME"
- pgvector README: HNSW, 거르기와 반복 인덱스 스캔(iterative index scans)
- MySQL 9 "The VECTOR Type"(일반 판에서 쓸 수 있는 함수가 무엇인지 확인)
- [42](./42-second-db-async-events.md): 지금 구조(DB 두 개)를 어떻게 함께 돌리나
- [41](./41-embedding-vector-search.md): 임베딩과 pgvector 기초
