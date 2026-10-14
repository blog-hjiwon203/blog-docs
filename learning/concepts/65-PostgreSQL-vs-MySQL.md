# 65. MySQL과 PostgreSQL: 비교, 옮기는 이유, 옮기는 법

> 관련 스텝: [스텝 10](../스텝-10.md)(두 번째 DB), [스텝 22](../스텝-22.md)(의미 검색), [스텝 23](../스텝-23.md)(T123~T128 코드 옮기기), [스텝 24](../스텝-24.md)(T129~T132 데이터 옮기기·전환) · 관련 개념: [41-임베딩과-벡터-검색](./41-임베딩과-벡터-검색.md), [42-두-번째-DB와-비동기-처리](./42-두-번째-DB와-비동기-처리.md), [66-의미-검색](./66-의미-검색.md), [68-서버와-Docker-개발용-운영용](./68-서버와-Docker-개발용-운영용.md), [03-Flyway-마이그레이션](./03-Flyway-마이그레이션.md), [32-블로그-안-검색-LIKE](./32-블로그-안-검색-LIKE.md), [33-격리-수준과-데드락](./33-격리-수준과-데드락.md), [57-스팸-차단과-금칙어](./57-스팸-차단과-금칙어.md), [64-캐시-저장소-고르기](./64-캐시-저장소-고르기.md)

> **한 줄 요약**: 벡터 검색이 필요해 PostgreSQL(pgvector)을 하나 더 들였다가, 두 DB를 오가는 비용 때문에 주 데이터까지 PostgreSQL로 합쳤다(2026-10-13 지원 결정). 옮길 때 문법 오류(`INSERT IGNORE`, `UPDATE … JOIN`)는 금방 드러난다. 어려운 것은 **오류 없이 결과만 달라지는 차이**다. 대표가 대소문자 비교이고, `citext`만으로는 부족하고 드라이버 설정(`stringtype=unspecified`)까지 맞춰야 했다.

> 이 문서는 옛 개념 65(PostgreSQL vs MySQL), 67(MySQL에서 PostgreSQL로 옮기기), 68의 데이터 옮기기 부분을 하나로 합친 것이다(2026-10-13). 서버·Docker·포트 이야기는 [68](./68-서버와-Docker-개발용-운영용.md)에 남았다.

## 1. 이 문서로 배우는 것

- MySQL과 PostgreSQL의 같은 점과 다른 점(문법, 타입, 글자 비교, 격리 수준, 확장)
- 이 프로젝트에 PostgreSQL이 왜 들어왔나, 벡터를 MySQL이 아니라 pgvector에 두는 이유
- 두 DB를 하나로 합치는 이유와 장단점, 선택지 비교
- 옮기기의 세 겹: 스키마, 쿼리, 조용한 의미 차이
- **대소문자 구분 문제와 해결**: citext, 드라이버 타입 함정, ILIKE, 자바 비교 맞추기
- `updated_at`, 격리 수준·잠금, Flyway 파일을 새로 쓰는 경우
- 벡터 거리와 가시성 조건을 JPA Criteria 한 쿼리로(hibernate-vector)
- 운영 데이터 옮기기: COPY 글자 형식, 이스케이프, 외래 키 순서, 번호 시퀀스, 행 수·내용 대조, 전환과 되돌리기

**먼저 알면 좋은 것**: 임베딩과 pgvector([41](./41-임베딩과-벡터-검색.md)), 두 번째 DB와 최종 일관성([42](./42-두-번째-DB와-비동기-처리.md)), Flyway([03](./03-Flyway-마이그레이션.md)), 격리 수준([33](./33-격리-수준과-데드락.md)), 개발용·운영용 서버와 Docker([68](./68-서버와-Docker-개발용-운영용.md)).

## 2. 왜 필요한가

이 블로그의 DB는 세 단계를 거쳤다.

| 시기 | 구조 | 이유 |
| --- | --- | --- |
| 처음(R-02, 2026-10-07) | MySQL 하나 | 주 데이터. 운영은 학교가 나눠 준 MySQL(s4) |
| 스텝 10 | MySQL + 추천 전용 PostgreSQL | 비슷한 글 추천에 벡터 검색이 필요. 추천은 도전 과제라 떼어 낼 수 있게 따로 |
| 스텝 23·24 | **PostgreSQL 하나** | 의미 검색에서 두 DB를 오가는 비용이 커지고, 운영 데이터가 아주 적을 때(글 3개) 옮기기로 |

DB를 고르고, 둘로 나누고, 다시 합치면서 생긴 질문에 답한다: 두 DB는 무엇이 다른가, 왜 PostgreSQL이 필요했나, 합치면 무엇이 좋고 무엇을 잃나, 어떻게 옮기나.

## 3. 기본 개념

### 3.1 같은 점

둘 다 **관계형 DB**다. 표·행·칸, SQL, 기본 키·외래 키·UNIQUE, 트랜잭션과 격리 수준, B-Tree 인덱스, CTE(`WITH`)와 윈도 함수(MySQL은 8.0부터)를 쓴다. JPA로 짠 평범한 CRUD는 드라이버와 방언만 바꾸면 거의 그대로 돈다.

### 3.2 다른 점

| 항목 | MySQL 8 (InnoDB) | PostgreSQL 17 |
| --- | --- | --- |
| 확장 | 없음. 기능은 버전에 따라 들어옴 | `CREATE EXTENSION`(pgvector, PostGIS, pg_trgm, citext …) |
| 벡터 검색 | 8에는 없음. 9에 `VECTOR` 타입이 생겼지만 판·버전마다 거리 계산·인덱스 지원이 다름 | pgvector: `vector(n)`, 거리 연산자 `<=>`, HNSW 인덱스 |
| 글자 비교 | 칸의 콜레이션. 흔한 `utf8mb4_0900_ai_ci`는 대소문자·악센트 무시 | 기본은 대소문자 구분 |
| 있으면 무시하고 넣기 | `INSERT IGNORE`(다른 오류도 삼킴) | `INSERT … ON CONFLICT DO NOTHING`(중복만) |
| 다른 표를 보며 고치기·지우기 | `UPDATE a JOIN b … SET`, `DELETE a FROM a JOIN b` | `UPDATE a SET … FROM b`, `DELETE FROM a USING b` |
| 넣은 행 바로 받기 | 없음 | `RETURNING` |
| 수정 시각 자동 갱신 | `ON UPDATE CURRENT_TIMESTAMP` | 없음(트리거나 앱) |
| 번호 자동 증가 | `AUTO_INCREMENT` | `GENERATED … AS IDENTITY`(시퀀스) |
| 참/거짓 | `TINYINT(1)` (0/1) | `BOOLEAN` |
| 날짜 시각 | `DATETIME` | `TIMESTAMP` / `TIMESTAMPTZ`(시간대 있음) |
| 긴 글자 | `MEDIUMTEXT` 등 | `TEXT` |
| JSON·배열·UUID | `JSON` / 없음 / 문자열 | `JSON`·`JSONB` / 배열 / `UUID` |
| 부분 인덱스(`WHERE` 조건) | 없음 | 있음 |
| 기본 격리 수준 | REPEATABLE READ | READ COMMITTED |
| 빈 자리(gap) 잠금 | 있음 | 없음 |
| DDL과 트랜잭션 | 자동 커밋(마이그레이션이 중간에 실패하면 반쯤 남음) | 트랜잭션 안에서 되돌림 |
| 연결 | 연결마다 스레드 | 연결마다 프로세스(연결이 많으면 풀러) |
| 정리 작업 | 거의 없음 | VACUUM(자동) |
| 구하기 쉬움 | 공용 호스팅·학교 서버에 흔함 | 클라우드 관리형은 흔함 |

**언제 무엇을**: 단순한 CRUD, 이미 MySQL이 주어진 환경, 대소문자 무시가 기본이길 원하면 MySQL. 벡터·지도·JSON 같은 확장, 복잡한 쿼리, 엄격한 정합성이 필요하면 PostgreSQL.

### 3.3 왜 PostgreSQL이 들어왔나: 벡터를 어디에 둘까

비슷한 글(OWN-06)과 의미 검색(OWN-07)은 **벡터 검색**이다. 글마다 임베딩(숫자 1,024개)을 두고, 검색어나 이 글의 임베딩과 **가까운** 글을 찾는다([41](./41-임베딩과-벡터-검색.md)). 방법은 넷이다.

| 방법 | 글이 적을 때 | 글이 많아지면 | 가시성 조건(볼 수 있는 글만) |
| --- | --- | --- | --- |
| ① MySQL에 벡터를 JSON·BLOB으로, 자바에서 코사인 계산 | 됨 | 글 전부를 읽어 계산 → 글 수만큼 느려짐 | DB에서 거른 뒤 자바에서 |
| ② MySQL 9 `VECTOR` | 학교 MySQL(8 계열)에는 타입이 없음 | 거리 계산·벡터 인덱스 지원이 판마다 다름(확인 필요) | — |
| ③ 전용 벡터 DB(Qdrant 등) | 서버 하나 더 | 잘 버팀 | 두 DB를 오감 |
| ④ **PostgreSQL + pgvector** | 됨 | HNSW 인덱스로 버팀 | **같은 쿼리에서** |

벡터를 pgvector에 두는 이유:

1. **거리 계산을 DB가 한다.** `embedding <=> 검색어`가 코사인 거리이고, 그대로 `ORDER BY`한다. ①은 글 전부를 읽어 자바가 계산한다.
2. **인덱스가 있다.** HNSW는 전부 읽지 않고 가까운 글을 찾는다. 학교 MySQL에는 벡터 인덱스가 없다.
3. **조건과 함께 찾는다.** "볼 수 있는 글 가운데 가까운 순"을 SQL 하나로. pgvector 0.8의 반복 스캔이 조건 때문에 결과가 모자라는 문제를 줄인다.
4. **주 데이터와 같은 DB에 둘 수 있다.** 외래 키·한 트랜잭션·조인을 쓴다(3.4). 이번에 합친 이유다.
5. **운영에서 쓸 수 있었다.** 학교 MySQL은 버전·확장을 바꿀 수 없다. pgvector는 Docker 이미지 하나(`pgvector/pgvector:pg17`)로 띄울 수 있었다.

솔직히 말하면 **"꼭" 필요한 것은 아니다.** 글이 몇 개뿐인 지금은 ①로도 된다. 그래도 글이 쌓여도 버티고, 가시성 조건을 DB에서 함께 걸고, 운영할 것을 하나로 줄이려면 ④가 가장 맞았다.

### 3.4 데이터를 한 곳에 두면 얻는 것

| 두 DB 사이에 없는 것 | 한 DB면 |
| --- | --- |
| 외래 키 | `post_embedding.post_id → post.id`(`ON DELETE CASCADE`). 없는 글의 임베딩은 들어갈 수 없다 |
| 한 트랜잭션 | 글과 임베딩 행이 같이 커밋·롤백(임베딩 계산 자체는 여전히 커밋 뒤 비동기) |
| 조인 | 가까운 글 찾기 + 볼 수 있는지 확인을 SQL 하나로 |

두 DB일 때 의미 검색은 세 번 일했다([66](./66-의미-검색.md)): ① PostgreSQL에서 가까운 글 번호 100개 → ② MySQL에서 그중 볼 수 있는 글 → ③ 자바에서 순서 맞춰 자르기. 블로그 안 검색은 그 블로그의 글 번호를 전부 PostgreSQL에 넘겼고, 비슷한 글은 볼 수 없는 글을 빼고도 채우려고 후보를 30개씩 넉넉히 뽑았다. 한 DB면 조건을 먼저 걸고 가까운 순으로 LIMIT 한다.

### 3.5 옮기기는 세 겹이다

| 겹 | 무엇 | 틀리면 |
| --- | --- | --- |
| ① 스키마 | 표 정의(Flyway SQL) | 서버가 안 뜬다(바로 보임) |
| ② 쿼리 | 네이티브 SQL, 테스트의 SQL | 그 기능을 부를 때 500(테스트가 있으면 보임) |
| ③ 의미 | 글자 비교, 격리 수준, 시간대, 드라이버가 보내는 타입 | **오류 없이 결과가 다르다**(테스트가 그 경우를 짚어야 보임) |

스텝 23에서 처음 돌린 테스트 409개 중 실패는 9개였다(①·②). ③은 테스트가 그 경우를 직접 확인하지 않으면 통과한 채로 남는다. 그래서 ③의 목록을 먼저 만들고 항목마다 테스트가 있는지 본다.

### 3.6 대소문자 구분: 문제와 해결

**문제.** MySQL의 `utf8mb4_0900_ai_ci`는 대소문자(ci)와 악센트(ai)를 **알아서** 무시했다. `Java`와 `java`는 같은 태그였고, `Test@x.com`이 있으면 `test@x.com`으로 가입할 수 없었다. PostgreSQL은 기본이 대소문자 구분이다. 그대로 옮기면 오류 하나 없이 중복 가입·중복 태그가 들어가고 검색 결과가 줄어든다.

**PostgreSQL에서 무시하는 방법**

| 방법 | 같음 비교 | UNIQUE | LIKE | 메모 |
| --- | --- | --- | --- | --- |
| `lower(x) = lower(y)` | 됨 | `lower(x)` 인덱스 | `lower(x) LIKE lower(p)` | 쿼리마다 잊지 않고 써야 함 |
| `ILIKE` | (LIKE 전용) | | 됨 | 검색에만 |
| `citext` 확장 | 됨 | 그냥 UNIQUE | 됨 | 칸 타입만 바꾸면 쿼리는 그대로 |
| 비결정적 콜레이션 | 됨 | 됨 | **17까지 불가** | 악센트 무시도 되지만 LIKE가 막힘 |

**함정: 드라이버가 보내는 타입.** citext 칸을 만들고 끝났다고 생각하기 쉽다. psql에서 해 보면(스텝 23에서 실제로 돌린 결과):

```sql
CREATE TEMP TABLE t (e citext UNIQUE);
INSERT INTO t VALUES ('Test@X.com');
SELECT e = 'test@x.com'::varchar AS v,   -- f  ← 대소문자를 가림!
       e = 'test@x.com'::text    AS t,   -- f
       e = 'test@x.com'          AS u,   -- t  (타입 없는 글자)
       e LIKE 'test%'::varchar   AS l    -- t
FROM t;
```

PostgreSQL은 연산자를 고를 때 양쪽 타입을 본다. 오른쪽이 `varchar`면 citext를 text로 바꿔 `text = text`(대소문자 구분)를 고르고, 타입 없는 글자면 왼쪽 칸 타입(citext)에 맞춘다. 그런데 JDBC 드라이버(PgJDBC)는 자바 `String`을 기본으로 **`varchar`로 보낸다.** 그러니 JPA의 `where m.nickname = ?`는 대소문자를 가린다.

**해결 (네 가지)**

| 무엇 | 어디 | 어떻게 |
| --- | --- | --- |
| ① citext 칸 | 이메일, 닉네임, 블로그 주소, 카테고리, 태그, 금칙어 | 타입을 `CITEXT`로, 길이는 `CHECK (char_length(x) <= n)`, 엔티티에 `columnDefinition = "citext"` |
| ② `stringtype=unspecified` | DB 접속 설정 | 글자 값을 타입 없이 보내 칸 타입(citext)을 따르게. **빼면 태그 테스트 3개가 500** |
| ③ `ILIKE` | 글·블로그 검색, 내 글 관리 검색, 관리자 회원 검색 | 일반 칸의 LIKE는 대소문자를 가려서 ILIKE로 |
| ④ 자바 비교 맞추기 | 태그 이름 합치기(`TagNames`) | 악센트까지 무시하던 `Collator`를 소문자 비교로. DB와 규칙이 다르면 "자바는 같다, DB는 다르다"가 생김 |

**잃은 것**: 악센트 무시. citext는 소문자로 바꿔 비교할 뿐이라 `Café` ≠ `cafe`다. 한글에는 영향이 없어 지원이 받아들였다. 악센트까지 무시하는 비결정적 콜레이션은 LIKE가 막혀서 고르지 않았다.

### 3.7 updated_at은 누가 채우나

MySQL의 `ON UPDATE CURRENT_TIMESTAMP`는 행의 **어떤 칸이든 바뀌면** 수정 시각을 지금으로 바꾼다. 그래서 "작성자가 고친 것이 아니면 수정 시각을 그대로 둔다"(조회수, 댓글 수, 관리자 숨김, [53](./53-서비스-관리와-제재-이력.md))를 지키려고 쿼리마다 `updated_at = updated_at`을 일부러 썼다(15곳).

PostgreSQL에는 이 기능이 없다. **트리거를 두지 않으면** 엔티티를 고칠 때만 JPA(`@LastModifiedDate`)가 채우고, 벌크 UPDATE(JPQL `update`, 네이티브 SQL)는 시각을 건드리지 않는다. 그래서 15곳은 하는 일이 없어져 지웠다. 트리거로 흉내 냈다면 이 15곳을 하나하나 다시 막아야 했다.

### 3.8 격리 수준과 잠금

| | MySQL InnoDB | PostgreSQL |
| --- | --- | --- |
| 기본 격리 | REPEATABLE READ: 첫 읽기 때 스냅샷을 계속 봄 | READ COMMITTED: **문장마다** 그때까지 커밋된 것을 봄 |
| 빈 자리(gap) 잠금 | 있음 | 없음 |
| 외래 키 확인 | 부모 행에 공유 잠금(S) | 부모 행에 `FOR KEY SHARE`(키가 아닌 칸의 UPDATE와 안 부딪힘) |
| "있으면 무시" 중 다른 트랜잭션이 같은 키를 넣는 중 | `INSERT IGNORE`가 그 행에 공유 잠금 | `ON CONFLICT DO NOTHING`이 상대가 끝나기를 기다림 |

MySQL에서는 "공감 INSERT(외래 키 공유 잠금)와 공감 수 UPDATE(배타 잠금)가 엇갈려 데드락"이 났다([33](./33-격리-수준과-데드락.md)). PostgreSQL에서는 생기지 않는다. 그래도 **글 행을 먼저 잠그는 코드는 남겼다.** 같은 글의 공감·댓글·조회 기록을 차례로 처리해 뒤 요청이 앞 요청의 결과를 보고 판단하게 하는 역할(줄 세우기)이 있기 때문이다. 동시성 테스트(공감 연타, 같은 새 태그 동시 저장, 조회수 연타)는 그대로 통과했다.

### 3.9 데이터 옮기기의 기본

- **COPY 글자 형식**: PostgreSQL `COPY … FROM STDIN`(psql은 `\copy`)은 한 줄이 한 행, 칸은 탭, NULL은 `\N`, 값 안의 역슬래시·탭·줄바꿈은 `\\`·`\t`·`\n`(`\r`)이다. MySQL에서 이 모양으로 꺼내면 그대로 흘려 넣는다. 단, `mysql -B`의 기본 출력은 **NULL과 글자 'NULL'이 둘 다 `NULL`**이라 쓸 수 없다.
- **외래 키 순서**: 글은 블로그를 가리키므로 블로그보다 먼저 넣으면 실패한다. 표 순서를 따지는 대신, 넣는 세션만 `session_replication_role = replica`로 외래 키 트리거를 끈다. 원본(MySQL)이 이미 외래 키로 맞던 데이터라 괜찮다. 슈퍼유저만 쓸 수 있다.
- **번호 시퀀스**: id가 `GENERATED BY DEFAULT AS IDENTITY`라 옛 번호를 그대로 넣을 수 있다(`ALWAYS`면 못 넣음). 하지만 시퀀스는 1에 머문다. 맞추지 않으면 **첫 가입이 id 1과 부딪혀 500**이다. `setval(…, max(id) + 1, false)`.

### 3.10 전환과 되돌리기

1. **멈추는 시간**: 옮기는 동안 새 글이 쓰이면 빠진다. 앱을 멈추고 옮긴다.
2. **확인 기준**: 표마다 행 수가 같아야 앱을 다시 띄운다. 행 수가 같아도 이스케이프가 틀리면 내용이 다를 수 있어 몇 표는 내용까지 대조한다.
3. **되돌릴 길**: 옛 DB(s4 MySQL)는 읽기만 하고 지우지 않는다. 이전 커밋으로 다시 배포하면 옛 `deploy.sh`가 MySQL로 앱을 띄운다(GitHub secrets `DB_*`를 며칠 남김). 되돌리면 그 사이 PostgreSQL에 새로 쓰인 글은 잃는다.

## 4. 동작 원리

### 4.1 선택지 셋과 판단

| | ① MySQL + PostgreSQL(스텝 22까지) | ② 전부 PostgreSQL + pgvector(지금) | ③ 전부 MySQL |
| --- | --- | --- | --- |
| 가시성 거르기 | 두 번 묻고 후보를 넉넉히 | SQL 한 번 | 벡터를 BLOB으로 두고 자바 계산 |
| 외래 키·트랜잭션 | 없음 | 있음 | 있음 |
| 운영할 것 | DB·DataSource·Flyway·테스트 컨테이너 2벌 | 1벌 | 1벌 |
| 글이 많아지면 | HNSW | HNSW | 글 수만큼 느려짐 |
| 운영 제약 | 맞음(주 DB는 학교 MySQL) | 운영 DB를 우리가 띄워야 함 | 맞음 |

설계만 보면 ②가 가장 낫다. 스텝 22까지 ①이었던 것은 운영 DB가 학교 MySQL로 주어졌고 추천은 떼어 낼 수 있는 도전 과제였기 때문이다. 의미 검색까지 생기자 ①의 비용이 커졌고, 운영 데이터가 아주 적을 때 ②로 옮겼다. ①이 나은 경우도 있다: 벡터 데이터나 검색 부하가 커서 본 DB와 따로 키워야 할 때, 본 DB를 고를 수 없을 때.

### 4.2 MySQL 전용 SQL 바꾸기

```sql
-- 있으면 무시하고 넣기
INSERT IGNORE INTO post_like (post_id, member_id) VALUES (?, ?);                     -- MySQL
INSERT INTO post_like (post_id, member_id) VALUES (?, ?) ON CONFLICT DO NOTHING;     -- PostgreSQL

-- 다른 표를 보며 고치기·지우기
UPDATE post p JOIN post_like l ON l.post_id = p.id
SET p.like_count = p.like_count - 1 WHERE l.member_id = ?;                           -- MySQL
UPDATE post p SET like_count = p.like_count - 1
FROM post_like l WHERE l.post_id = p.id AND l.member_id = ?;                         -- PostgreSQL

DELETE l FROM post_like l JOIN post p ON p.id = l.post_id WHERE p.blog_id = ?;       -- MySQL
DELETE FROM post_like l USING post p WHERE p.id = l.post_id AND p.blog_id = ?;       -- PostgreSQL
```

- 둘 다 "넣은 행 수"(0 또는 1)를 돌려주므로 그 수로 판단하는 코드는 그대로다. `INSERT IGNORE`는 CHECK 위반·길이 초과도 경고로 삼키지만 `ON CONFLICT DO NOTHING`은 중복만 넘긴다. 더 안전하다.
- PostgreSQL에서는 `SET`의 왼쪽에 별칭을 붙이지 않는다(`SET p.like_count`는 오류). 조인 조건은 `WHERE`로 간다.

### 4.3 이미 적용된 Flyway 파일을 새로 쓰기

원칙은 "이미 적용된 파일은 고치지 않는다"다([03](./03-Flyway-마이그레이션.md)). 그런데 이번에는 **DB 자체가 새것**이라 Flyway 이력이 비어 있다. MySQL용 V1~V4를 고친 것이 아니라 PostgreSQL용 V1·V2를 새로 시작한 것이다. 옛 이력은 옛 DB(s4)에 남는다. V3(본문 글자 칸)은 새 V1에 처음부터 넣었고, V4(이미 있던 블로그에 사이드바 행 채우기)는 빈 DB에 할 일이 없다. 운영 데이터는 V4가 적용된 MySQL에서 그대로 옮겨 온다.

### 4.4 벡터 거리와 가시성을 한 쿼리로

가시성 조건은 SQL이 아니라 **JPA Criteria**(`PostSpecifications.visibleTo`, `listedIn`)로 짜여 있다. SQL로 한 벌 더 쓰면 두 벌을 같이 고쳐야 한다. 그래서 반대로 임베딩 표를 엔티티(`PostEmbedding`)로 만들어 Criteria 쪽으로 데려왔다. hibernate-vector 모듈이 pgvector의 `vector` 칸을 `float[]`로 읽고 `cosine_distance` 함수를 등록한다.

```
from Post p, PostEmbedding e
where e.postId = p.id and (visibleTo 조건) and cosine_distance(e.embedding, :검색어) <= 0.60
order by cosine_distance(…), p.id desc   offset … limit …
```

### 4.5 운영 전환 순서 (research R-02)

```
① 코드 PR 병합 → GitHub Actions 배포
   deploy.sh: PostgreSQL 컨테이너 안에 blog DB가 없으면 만듦 → 앱을 blog DB로 띄움
   앱: Flyway V1·V2 → 빈 표 + 초기 관리자 행 → 사이트가 빈 DB로 뜸(몇 분)
② 지원이 s2에서 bash ~/now-log/deploy/migrate-from-mysql.sh
   앱 멈춤 → 표 비움 → 표마다 s4 MySQL → \copy → 시퀀스 → 행 수 비교 → 앱 다시 띄움
③ 앱이 뜨면서 발행 글 임베딩을 새로 만듦(PostEmbeddingListener.onReady)
④ 며칠 지켜본 뒤: GitHub secrets DB_* 지우기, 옛 recommend DB 정리
```

①과 ② 사이의 가입·글은 ②가 지운다. 데이터가 적고 몇 분이라 받아들였다.

## 5. 이 프로젝트에서는

### 5.1 무엇이 바뀌었나, 장점과 단점

```
전 (스텝 22까지)                                  후 (스텝 24부터)
s2: aigj017-app ──▶ s4 MySQL (회원·글)             s2: aigj017-app ──▶ aigj017-recommend-db
          └──────▶ aigj017-recommend-db                                 └ blog DB (회원·글·임베딩)
                     └ recommend DB (임베딩만)
```

| 장점 | 단점 |
| --- | --- |
| 의미 검색·비슷한 글이 쿼리 한 번(가시성 + 가까운 순 + 페이지) | 학교가 관리하던 DB를 떠나 우리 컨테이너로. 백업 없음(지원 결정) |
| 임베딩이 글과 외래 키로 묶여 정합성을 DB가 지킴 | 악센트 무시를 잃음(Café ≠ cafe) |
| DB 연결·Flyway·테스트 컨테이너 2벌 → 1벌, 개발 MySQL 컨테이너 없음 | 검색어 벡터를 넘기려고 Hibernate 내부 클래스에 의존(5.6) |
| `ON CONFLICT`가 `INSERT IGNORE`보다 엄격 | 컨테이너·secret 이름에 `recommend`가 남아 어색함 |
| pgvector·부분 인덱스 등 확장을 바로 씀, 글자·의미 검색 섞기도 쿼리 하나로 가능 | 전환할 때 몇 분 동안 사이트가 빈 DB로 보임 |

### 5.2 스키마: 변환 스크립트로 만든 V1

`V1__init.sql`(PostgreSQL)은 MySQL V1을 작은 스크립트로 바꿔 만들었다(칸 200개 남짓을 손으로 옮기면 하나쯤 빠뜨리기 쉽다). 만든 뒤 개발 PostgreSQL에 적용해 오류가 없는지 먼저 봤다. 한 표:

```sql
CREATE TABLE member (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY,
    email CITEXT,
    password_hash VARCHAR(100),
    nickname CITEXT NOT NULL,
    ...
    updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    CONSTRAINT uk_member_email UNIQUE (email),
    CONSTRAINT uk_member_nickname UNIQUE (nickname),
    ...
    CONSTRAINT ck_member_email_length CHECK (char_length(email) <= 255),
    CONSTRAINT ck_member_nickname_length CHECK (char_length(nickname) <= 20)
);
```

- `email CITEXT` + `uk_member_email`: 대소문자만 다른 이메일은 UNIQUE 위반.
- `ck_member_nickname_length`: citext에는 길이가 없어 원래의 `VARCHAR(20)`을 CHECK로.
- `updated_at`에 `ON UPDATE`가 없다(3.7).

`ddl-auto=validate`가 칸 타입을 비교하므로 citext 칸에는 `columnDefinition`을 적는다.

```java
@Column(name = "nickname", nullable = false, length = 20, columnDefinition = "citext")
private String nickname;
```

### 5.3 접속 설정: stringtype과 HNSW

`application.yml`:

```yaml
spring:
  datasource:
    hikari:
      data-source-properties:
        stringtype: unspecified
      connection-init-sql: "SET hnsw.ef_search = 200; SET hnsw.iterative_scan = strict_order"
```

- `stringtype: unspecified`: 3.6의 함정 막기. 개발·운영·테스트가 모두 이 파일을 읽어서 접속 주소마다 붙이지 않아도 된다. CLAUDE.md에 "빼지 않는다"로 적어 두었다.
- `hnsw.ef_search = 200`: HNSW가 한 번에 보는 후보 수. 기본 40이면 가까운 순 100개를 다 못 본다([66](./66-의미-검색.md)).
- `hnsw.iterative_scan = strict_order`(pgvector 0.8부터): 가시성 조건을 같은 쿼리에서 거르니, 인덱스가 찾은 후보가 많이 걸러져 LIMIT를 못 채우면 인덱스를 더 읽는다. 가까운 순서는 지킨다.

### 5.4 대소문자 무시 검색: ILIKE를 Criteria로

표준 JPA에는 `ilike`가 없다. Spring Data가 넘겨주는 `cb`는 Hibernate 구현이라 `HibernateCriteriaBuilder`로 바꿔 부른다. `global/web/LikePatterns.java`:

```java
public static Predicate containsIgnoreCase(CriteriaBuilder cb, Expression<String> column, String pattern) {
    return ((HibernateCriteriaBuilder) cb).ilike(column, pattern, ESCAPE);
}
```

- `pattern`은 `%검색어%`로, `%`·`_`를 이스케이프한 것이다([32](./32-블로그-안-검색-LIKE.md)).
- `SearchService`, `ManagePostService`, `AdminMemberService`가 이 한 곳을 쓴다.

### 5.5 MySQL 전용 SQL 목록

| 무엇 | 곳 | 바꾼 것 |
| --- | --- | --- |
| `INSERT IGNORE` | 공감·저장·신고·구독·차단·금칙어·태그·방문 기록 (8곳) | `ON CONFLICT DO NOTHING` |
| `UPDATE … JOIN` | `MemberTraceCleaner`(2), `BlogContentCleaner`(1), `BlogStatsRepository.refreshTotals`(1) | `UPDATE … FROM` |
| `DELETE x FROM … JOIN` | `BlogContentCleaner`(3) | `DELETE … USING` |
| `is_blinded = 0` | 인기 점수·블로그 점수 SQL | `= FALSE` |
| `updated_at = updated_at` | JPQL 8곳, 네이티브 SQL 7곳 | 지움(3.7) |

`member/domain/MemberTraceCleaner.java`(탈퇴한 회원이 쓴 댓글 수만큼 글마다 댓글 수 줄이기):

```java
jdbcTemplate.update("""
        UPDATE post p SET comment_count = p.comment_count - c.n
        FROM (SELECT post_id, COUNT(*) AS n FROM comment
              WHERE member_id = ? AND deleted_at IS NULL GROUP BY post_id) c
        WHERE c.post_id = p.id""", memberId);
```

- `FROM (부분 쿼리) c`: 글마다 지울 댓글 수를 먼저 세어 표처럼 쓴다.
- `WHERE c.post_id = p.id`: MySQL의 `JOIN … ON`이 하던 일.
- `SET comment_count`: 왼쪽에 `p.`를 붙이지 않는다.

### 5.6 한 쿼리로 가까운 글 찾기

`recommend/domain/PostEmbeddingRepository.java`:

```java
public List<NearPost> findNear(float[] query, Specification<Post> visible, Double minSimilarity, Long excludePostId,
                               int offset, int limit, String... fetch) {
    CriteriaBuilder cb = entityManager.getCriteriaBuilder();
    CriteriaQuery<Tuple> criteria = cb.createTupleQuery();
    Root<Post> post = criteria.from(Post.class);
    for (String path : fetch) {
        // 미분류 글(category 없음)도 나오게 LEFT. 그냥 fetch하면 INNER JOIN이라 빠진다
        post.fetch(path, JoinType.LEFT);
    }
    Root<PostEmbedding> embedding = criteria.from(PostEmbedding.class);
    Expression<Double> distance = distance(cb, embedding, query);
    criteria.multiselect(post, distance)
            .where(conditions(cb, criteria, post, embedding, distance, visible, minSimilarity, excludePostId))
            .orderBy(cb.asc(distance), cb.desc(post.get("id")));
    ...
}
```

- `criteria.from` 두 번: 글과 임베딩을 함께 읽고 `conditions`에서 `e.postId = p.id`로 잇는다.
- `visible.toPredicate(…)`(`conditions` 안): 글 목록과 **같은** 가시성 코드를 건다. 전체 의미 검색과 비슷한 글은 `visibleTo`, 블로그 안 검색은 `listedIn`.
- `multiselect(post, distance)`: 유사도(`1 - 거리`)를 같이 받는다.
- `setFirstResult/setMaxResults`(생략한 부분): DB가 페이지를 자른다.

거리 식:

```java
private static Expression<Double> distance(CriteriaBuilder cb, Root<PostEmbedding> embedding, float[] query) {
    SqmExpression<float[]> column = (SqmExpression<float[]>) embedding.<float[]>get("embedding");
    return cb.function("cosine_distance", Double.class, column, ((SqmCriteriaNodeBuilder) cb).value(query, column));
}
```

- `cb.literal(query)`로 넘기면 `float[]`가 **배열 타입**이 되어 hibernate-vector가 "인자는 vector여야 한다"며 거절한다.
- `value(query, column)`: "이 값의 타입은 저 칸(vector)을 따른다". SQL에 `cast(? as vector)`로 들어간다. 공개 API에 없어 Hibernate 구현 클래스를 쓴다. Hibernate를 올릴 때 확인할 자리다.

없어진 것: 블로그 안 검색의 글 번호 목록(`PostCountRepository.findIds`), 비슷한 글의 후보 30개(`CANDIDATES`), 두 번째 DataSource와 Flyway(`RecommendDataSourceConfig`, `db/recommend`). 의미 검색 503은 이제 임베딩 서버(Ollama)에 닿지 않을 때만이고, DB 오류는 다른 API처럼 500이다.

### 5.7 테스트에서 만난 차이

| MySQL | PostgreSQL | 메모 |
| --- | --- | --- |
| `NOW() - INTERVAL 2 HOUR` | `NOW() - INTERVAL '2 hour'` | 숫자와 단위를 따옴표 안에 |
| `NOW(6) - INTERVAL ? MINUTE` | `NOW() - ? * INTERVAL '1 minute'` | 자리표시자는 곱하기로 |
| `UPDATE … LIMIT 1` | `WHERE id = (SELECT MIN(id) …)` | UPDATE에 LIMIT 없음 |
| `CAST(x AS CHAR)` | `CAST(x AS TEXT)` | PostgreSQL `CHAR`는 **한 글자**라 잘림 |
| `table_schema = DATABASE()` | `table_schema = current_schema()` | |

`NOW()`의 시간대: 테스트용 MySQL 컨테이너는 UTC였다. PgJDBC는 JVM 시간대(테스트는 Asia/Seoul)를 세션 시간대로 보내서, PostgreSQL의 `NOW()`가 앱이 넣는 시각과 같은 한국 시간이 되었다.

### 5.8 이전 스크립트: 칸 하나를 COPY 모양으로

`deploy/migrate-from-mysql.sh`:

```bash
read -r -d '' CELL <<'SQL' || true
IFNULL(REPLACE(REPLACE(REPLACE(REPLACE(CAST(`@` AS CHAR), CHAR(92 USING utf8mb4), CHAR(92, 92 USING utf8mb4)), CHAR(9 USING utf8mb4), CHAR(92, 116 USING utf8mb4)), CHAR(10 USING utf8mb4), CHAR(92, 110 USING utf8mb4)), CHAR(13 USING utf8mb4), CHAR(92, 114 USING utf8mb4)), CHAR(92, 78 USING utf8mb4))
SQL
```

- `mysql -N -B --raw`(머리줄 없이, 탭으로, 이스케이프 없이)로 받고, 이스케이프는 이 SELECT 식이 한다. 그래야 NULL은 `\N`, 글자 'NULL'은 그대로다.
- `CHAR(92 USING utf8mb4)`: 글자 번호 92(역슬래시). 9는 탭, 10은 줄바꿈, 13은 CR, 116·110·114·78은 `t`·`n`·`r`·`N`. "역슬래시 → 둘, 탭 → `\t`, 줄바꿈 → `\n`, NULL → `\N`"이 된다.
- `'\t'` 같은 문자열 이스케이프를 쓰지 않은 이유: MySQL은 `sql_mode`에 `NO_BACKSLASH_ESCAPES`가 있으면 문자열의 역슬래시를 그냥 글자로 본다. 학교 MySQL 설정을 모르니 글자 번호로 썼다. `USING utf8mb4`가 없으면 `CHAR()`가 바이너리 문자열을 돌려준다.
- 역슬래시를 **맨 먼저** 바꾼다. 나중에 바꾸면 방금 만든 `\t`의 역슬래시까지 두 배가 된다.
- `CAST(… AS CHAR)`: 시각은 `2026-10-13 12:00:00.123456`처럼 나와 TIMESTAMP가, `TINYINT(1)`의 0/1은 BOOLEAN이 그대로 받는다.
- `<<'SQL'`(따옴표 친 here-doc): bash가 안의 글자를 건드리지 않는다. `@` 자리에 칸 이름을 끼운다(`${CELL//@/$c}`).

표 하나를 옮기는 줄:

```bash
mysql_q "SELECT $SELECT_COLS FROM \`$t\`" \
  | docker exec -i -e PGOPTIONS='-c session_replication_role=replica' "$PG" \
      psql -X -q -v ON_ERROR_STOP=1 -U blog -d "$PG_DB" -c "\\copy \"$t\" ($PG_COLS) FROM STDIN"
```

- 칸 목록은 PostgreSQL에서 읽고(계산 칸 빼고) 같은 순서로 MySQL에서 SELECT한다.
- 파이프로 바로 흘려서 중간 파일이 없다. `PGOPTIONS`로 이 세션만 외래 키 확인을 끈다(3.9).
- `ON_ERROR_STOP`과 `set -o pipefail`: 한 표라도 실패하면 멈춘다.
- MySQL 비밀번호는 `read -s`로 받아 임시 설정 파일(`--defaults-extra-file`)로 넘긴다. 명령줄에 쓰면 `ps`에 보인다.

### 5.9 시험과 운영 결과

- **노트북 시험**(개발 MySQL → 개발 PostgreSQL의 시험 DB): 26개 표 행 수가 같았다(글 33, 회원 17 …). 글마다 본문·제목 MD5와 시각(마이크로초), 회원의 이메일·비밀번호 해시·상태, 계산 칸을 두 DB에서 뽑아 `diff`해도 같았다. 줄바꿈·역슬래시가 든 글도 있었다. 다음 글 번호는 34(max + 1). 그 DB로 앱을 띄우니 옛 비밀번호 로그인, 임베딩 다시 만들기, 글자·의미 검색이 됐다.
- **운영(2026-10-13)**: 첫 실행은 확인 질문 전에 끝나 아무것도 바뀌지 않았고, 두 번째에 26개 표 행 수가 모두 같았다(블로그 3, 글 3, 회원 4, 댓글 1 …). 사이트가 다시 뜨고, 글자 검색에 옛 글 두 개, 의미 검색 "메모리에 데이터 저장하기" → "캐시 저장소 고르기" 0.49(MySQL 때 0.48, 임베딩을 다시 만들어 조금 다름).

## 6. 자주 하는 실수와 함정

- **"SQL은 표준이니 DB만 바꾸면 된다"고 믿는다.** 네이티브 쿼리와 마이그레이션 SQL은 DB마다 다르다. 이 프로젝트만 해도 `INSERT IGNORE` 8곳, `UPDATE`·`DELETE … JOIN` 7곳이 바로 오류였다.
- **칸만 citext로 바꾸고 드라이버 타입을 잊는다.** `citext = varchar`는 대소문자를 가린다. 대소문자만 다른 값으로 가입·검색하는 테스트로 확인한다.
- **자바와 DB의 "같은 이름" 규칙이 어긋난다.** DB는 소문자 비교인데 자바가 악센트까지 무시하면, 자바는 Café와 cafe를 하나로 합치고 DB는 다르게 저장한다.
- **트리거로 `ON UPDATE`를 흉내 낸다.** "수정 시각 그대로" 규칙이 있는 곳마다 다시 막아야 한다.
- **`INSERT IGNORE`와 `ON CONFLICT DO NOTHING`을 같다고 믿는다.** MySQL은 다른 오류도 삼킨다.
- **격리 수준 차이를 잊는다.** 잠금·스냅샷을 전제로 한 코드는 동시성 테스트로 다시 확인한다.
- **Criteria `fetch`를 그냥 쓴다.** 기본이 INNER JOIN이라 미분류 글이 사라진다. 이번에도 의미 검색이 0개를 돌려줘서 생성된 SQL을 보고 찾았다.
- **근사 인덱스와 같은 쿼리 안의 조건.** HNSW는 후보를 `ef_search`개까지만 보고 걸러진 뒤 모자라면 결과가 적다. `iterative_scan`을 켠다.
- **빌드 폴더에 지운 마이그레이션이 남는다.** `target/classes`에 남은 V3를 Flyway가 실행했다. 지운 뒤에는 `./mvnw clean`.
- **NULL과 글자 'NULL'을 구분하지 않는다.** `mysql -B` 기본 출력은 둘 다 `NULL`.
- **역슬래시를 나중에 이스케이프한다.** `\t`가 `\\t`가 된다.
- **번호 시퀀스를 안 맞춘다.** 옮긴 직후엔 멀쩡하다가 첫 가입에서 500.
- **행 수만 보고 끝낸다.** 몇 표는 내용까지 대조한다.
- **옛 DB를 바로 지운다.** 되돌릴 길이 없어진다.
- **질문이 나오기 전에 답을 친다.** 운영 첫 실행에서 스크립트가 확인 질문 전에 끝났는데 `yes`를 쳐서 셸의 `yes` 명령(무한히 `y` 출력)이 돌았다. 질문 줄이 보일 때만 답하고, 출력은 `| tee ~/migrate.log`로 남긴다.

## 7. 직접 해 보기

준비: `docker compose up -d`(개발 PostgreSQL `blog-postgres`).

### 7.1 citext와 드라이버 타입

```bash
docker exec -it blog-postgres psql -U blog -d blog -c "
SELECT 'Java'::citext = 'java'          AS untyped,
       'Java'::citext = 'java'::varchar AS as_varchar,
       'Java'::citext = 'java'::citext  AS as_citext,
       'JPA' LIKE '%jpa%' AS like_, 'JPA' ILIKE '%jpa%' AS ilike_;"
```

`untyped`·`as_citext`·`ilike_`는 참, `as_varchar`·`like_`는 거짓이다.

### 7.2 stringtype을 꺼 보기

`application.yml`에서 `data-source-properties:`와 `stringtype: unspecified` 두 줄을 주석으로 막고 `./mvnw test -Dtest=TagIntegrationTest`. 대소문자만 다른 태그를 쓰는 테스트 3개가 201 대신 500으로 실패한다(이미 있는 태그를 `varchar`로 찾아 "CAFÉ"로 "Café"를 못 찾고, 넣기는 citext UNIQUE에 걸려 0행, 다시 읽기도 못 찾음). 확인 후 되돌린다.

### 7.3 있으면 무시하고 넣기, UPDATE … FROM

```bash
docker exec -it blog-postgres psql -U blog -d blog -c "
CREATE TEMP TABLE t (id int PRIMARY KEY);
INSERT INTO t VALUES (1) ON CONFLICT DO NOTHING;
INSERT INTO t VALUES (1) ON CONFLICT DO NOTHING;"     # 두 번째는 INSERT 0 0

docker exec -it blog-postgres psql -U blog -d blog -c "
BEGIN;
UPDATE post p SET comment_count = p.comment_count + c.n
FROM (SELECT post_id, COUNT(*) AS n FROM comment GROUP BY post_id) c WHERE c.post_id = p.id;
SELECT id, comment_count FROM post ORDER BY id LIMIT 3;
ROLLBACK;"
```

### 7.4 생성된 SQL 보기

```bash
./mvnw test -Dtest='SimilarPostIntegrationTest' -Dspring.jpa.show-sql=true 2>&1 | grep -m1 'cast(? as vector)'
```

`from post p1_0 … left join category …, post_embedding pe1_0 where pe1_0.post_id=p1_0.id and …`. `JoinType.LEFT`를 지우고 다시 돌리면 미분류 글을 쓰는 테스트가 실패한다.

### 7.5 격리 수준

psql 창 두 개. 창 A `BEGIN; SELECT like_count FROM post WHERE id = 1;`, 창 B `UPDATE post SET like_count = like_count + 1 WHERE id = 1;`, 창 A에서 다시 SELECT하면 **바뀐 값**이 보인다(READ COMMITTED). `BEGIN ISOLATION LEVEL REPEATABLE READ;`로 시작하면 옛 값이 보인다.

### 7.6 COPY 형식 손으로 써 보기

```bash
docker exec -i blog-postgres psql -U blog -d blog <<'EOF'
CREATE TEMP TABLE t (a text, b int);
\copy t FROM STDIN
첫 줄\t바뀜	1
\N	2
역슬래시 \\ 하나	3
\.
SELECT a, a IS NULL AS is_null, b FROM t;
EOF
```

(가운데 칸 구분은 진짜 탭이다.) `\t`는 탭 글자로, `\N`은 NULL로, `\\`는 역슬래시 하나로 들어간다.

### 7.7 시퀀스를 안 맞추면

```bash
docker exec -i blog-postgres psql -U blog -d blog <<'EOF'
CREATE TEMP TABLE s (id bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, v text);
INSERT INTO s (id, v) VALUES (1, '옮긴 행');
INSERT INTO s (v) VALUES ('새 행');   -- 오류: id 1 중복
EOF
```

`SELECT setval(pg_get_serial_sequence('s', 'id'), 2, false);` 뒤에는 새 행이 2번으로 들어간다.

### 7.8 이전 스크립트 시험

[스텝 노트 24](../스텝-24.md)의 "직접 해 보기"대로 시험 DB(`migtest`)를 만들고 V1·V2를 적용한 뒤, 환경 변수로 개발 MySQL과 시험 DB를 가리켜 `bash deploy/migrate-from-mysql.sh --yes`. 끝나면 `DROP DATABASE migtest`.

## 8. 확인 문제

1. 이 프로젝트에 PostgreSQL이 처음 들어온 이유는? 꼭 필요했나?
<details><summary>답</summary>비슷한 글·의미 검색에 벡터 검색이 필요했다. pgvector는 거리 계산(&lt;=&gt;)과 HNSW 인덱스를 DB에서 하고, 가시성 조건과 한 쿼리로 찾을 수 있다. 꼭은 아니다. 글이 몇 개면 MySQL에 벡터를 BLOB으로 두고 자바에서 계산해도 된다. 글이 쌓이면 느려진다.</details>

2. 벡터를 학교 MySQL이 아니라 pgvector에 둔 이유 세 가지는?
<details><summary>답</summary>① 거리 계산과 정렬을 DB가 한다 ② HNSW 인덱스로 글이 많아도 전부 읽지 않는다 ③ 가시성 조건과 같은 쿼리에서 찾는다. 그리고 학교 MySQL(8 계열)에는 벡터 타입·인덱스가 없고 우리가 버전을 바꿀 수 없다.</details>

3. 두 DB를 하나로 합쳐서 얻은 것과 잃은 것은?
<details><summary>답</summary>얻은 것: 검색이 쿼리 한 번, 외래 키로 정합성, 운영할 것이 한 벌. 잃은 것: 학교가 관리하던 DB(이제 우리 책임, 백업 없음), 악센트 무시, Hibernate 내부 API 의존, 전환 때 몇 분의 빈 사이트.</details>

4. 옮기기의 세 겹 중 테스트를 돌려도 드러나지 않을 수 있는 것은?
<details><summary>답</summary>의미(글자 비교, 격리 수준, 시간대, 드라이버 타입). 실행은 되고 결과만 다르다. 테스트가 그 경우를 직접 짚어야 드러난다.</details>

5. 칸이 citext인데 JPA로 `where nickname = ?`를 하면 대소문자를 가리는 이유와 해결은?
<details><summary>답</summary>PgJDBC가 String을 varchar로 보내서 PostgreSQL이 text = text(대소문자 구분)를 고른다. 접속 설정 <code>stringtype=unspecified</code>로 타입 없이 보내면 칸의 타입(citext)을 따른다.</details>

6. 대소문자 무시를 위해 한 네 가지는? 잃은 것은?
<details><summary>답</summary>① 이름 칸 citext(길이는 CHECK) ② stringtype=unspecified ③ 검색은 ILIKE ④ 자바 태그 비교를 소문자 비교로. 잃은 것은 악센트 무시(Café ≠ cafe).</details>

7. 비결정적 콜레이션 대신 citext를 고른 이유는?
<details><summary>답</summary>PostgreSQL 17까지 비결정적 콜레이션 칸에는 LIKE를 쓸 수 없다. citext는 같음 비교·UNIQUE·LIKE가 모두 된다.</details>

8. MySQL에서 `updated_at = updated_at`을 쓴 이유와 PostgreSQL에서 지운 이유는?
<details><summary>답</summary>MySQL의 ON UPDATE CURRENT_TIMESTAMP가 어떤 칸이든 바뀌면 수정 시각을 바꿔서 일부러 막았다. PostgreSQL에는 그 기능이 없고 트리거도 두지 않아 벌크 UPDATE는 원래 시각을 건드리지 않는다.</details>

9. `INSERT IGNORE`와 `ON CONFLICT DO NOTHING`의 공통점과 차이는?
<details><summary>답</summary>둘 다 이미 있으면 0행. INSERT IGNORE는 CHECK 위반·길이 초과도 경고로 삼키고, ON CONFLICT DO NOTHING은 UNIQUE·기본 키 충돌만 넘긴다.</details>

10. MySQL에서 나던 "공감 INSERT와 공감 수 UPDATE의 데드락"이 PostgreSQL에서 안 나는 이유는? 글 행 잠금을 남긴 이유는?
<details><summary>답</summary>외래 키 확인이 FOR KEY SHARE라 키가 아닌 칸의 UPDATE(FOR NO KEY UPDATE)와 부딪히지 않는다. 글 행 잠금은 같은 글의 요청을 차례로 처리하는 줄 세우기 역할이 있어서 남겼다.</details>

11. `cb.literal(query)`로 cosine_distance를 부르면 실패한 이유는?
<details><summary>답</summary>Hibernate가 float[]를 배열 타입으로 보고 hibernate-vector가 vector 인자가 아니라며 거절한다. 칸의 타입을 물려받는 값(<code>value(query, column)</code>)으로 넘기면 <code>cast(? as vector)</code>가 된다.</details>

12. 이미 적용된 Flyway 파일은 고치지 않는 것이 원칙인데 V1을 새로 쓰고 V3·V4를 지워도 된 이유는?
<details><summary>답</summary>DB 자체가 새 PostgreSQL이라 Flyway 이력이 비어 있다. 옛 이력은 옛 DB에 남는다. V4(이미 있던 블로그 채우기)는 빈 DB에 할 일이 없고, 운영 데이터는 V4가 적용된 MySQL에서 옮겨 온다.</details>

13. MySQL에서 꺼낼 때 `--raw` + SELECT에서 직접 이스케이프하고, 그것도 글자 번호(`CHAR(92 …)`)로 쓴 이유는?
<details><summary>답</summary>기본 출력은 NULL과 글자 'NULL'을 구분하지 못한다. 문자열 이스케이프('\t')는 sql_mode의 NO_BACKSLASH_ESCAPES에 따라 뜻이 달라져서, 설정과 상관없는 글자 번호로 썼다.</details>

14. 옮긴 뒤 시퀀스를 맞추지 않으면 언제 어떤 문제가 생기나?
<details><summary>답</summary>옮긴 직후엔 멀쩡하다가 첫 가입·글쓰기에서 시퀀스가 1을 줘서 이미 있는 id 1과 부딪혀 500.</details>

15. 되돌릴 길로 남겨 둔 것과, 되돌릴 때 잃는 것은?
<details><summary>답</summary>s4 MySQL(지우지 않음)과 GitHub secrets DB_*(옛 deploy.sh가 씀). 이전 커밋으로 다시 배포하면 MySQL로 돌아간다. 그 사이 PostgreSQL에 새로 쓰인 데이터는 잃는다.</details>

## 9. 더 읽을거리

- PostgreSQL 문서: "citext"(Limitations), "Collation Support"(비결정적 콜레이션), "INSERT … ON CONFLICT", "UPDATE … FROM", "DELETE … USING", "Transaction Isolation", "Explicit Locking", "Identity Columns", "COPY"(Text Format), "session_replication_role", "Sequence Manipulation Functions"
- MySQL 8.4 레퍼런스: "INSERT IGNORE", "Multiple-Table UPDATE", "Automatic Initialization and Updating for TIMESTAMP and DATETIME", mysql 클라이언트 `--batch`·`--raw`, "Server SQL Modes"(NO_BACKSLASH_ESCAPES)
- MySQL 9 "The VECTOR Type"(판마다 쓸 수 있는 함수 확인)
- PgJDBC 문서: 접속 설정 `stringtype`
- pgvector README: HNSW, "Filtering", "Iterative Index Scans"
- Hibernate ORM 문서: "Vector module"
- [41](./41-임베딩과-벡터-검색.md): 임베딩과 pgvector 기초 · [42](./42-두-번째-DB와-비동기-처리.md): 두 DB를 함께 돌리던 방법 · [66](./66-의미-검색.md): 두 DB 때의 의미 검색 · [68](./68-서버와-Docker-개발용-운영용.md): 서버·Docker·개발용과 운영용
