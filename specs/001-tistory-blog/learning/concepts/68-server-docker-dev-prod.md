# 68. 서버와 Docker: 개발용과 운영용, 포트와 docker 네트워크

> 관련 스텝: [스텝 24](../step-24.md) (T129) · 관련 개념: [65-postgresql-vs-mysql](./65-postgresql-vs-mysql.md)(DB 비교·옮기기), [42-second-db-async-events](./42-second-db-async-events.md)

> **한 줄 요약**: Docker는 서버를 대신하는 게 아니라 **서버(컴퓨터)에 프로그램을 상자째 띄우는 도구**이고, 컴퓨터마다 따로 있다. 그래서 개발용(노트북)과 운영용(s2)이 두 벌이고, 노트북의 Docker 화면에는 운영 컨테이너가 보이지 않는다. 포트를 여는 것은 바깥에서 들어올 문을 다는 일일 뿐, 위치와는 상관이 없다.

> 데이터를 MySQL에서 PostgreSQL로 옮기는 이야기(COPY, 이스케이프, 시퀀스, 전환과 되돌리기)는 [65](./65-postgresql-vs-mysql.md)에 합쳤다(2026-10-13).

## 1. 이 문서로 배우는 것

- 서버, Docker, 컨테이너, 이미지의 관계. 서버에서도 Docker를 쓰는 이유
- 포트와 docker 네트워크: 건물·방·현관문 비유
- 개발용과 운영용이 왜 두 벌인가, 연결 정보는 어디에 있나
- 이 프로젝트에서 무엇이 어느 컴퓨터에 있는가(스텝 24 전과 후)
- 같은 컨테이너에 DB를 하나 더 만들기, 비밀번호를 명령줄에 쓰지 않기

## 2. 왜 필요한가

스텝 24에서 운영 DB를 옮기며 지원이 계속 헷갈린 질문들이다.

- 운영용 PostgreSQL은 어디 떠 있나? 노트북 Docker에는 개발용만 보인다.
- 할당받은 포트가 아니라 내부 포트로 열었으니 노트북에 띄운 것 아닌가?
- 다 서버에 띄울 거면 Docker는 왜 필요한가?
- PostgreSQL 연결 정보는 하나만 넣은 기억이 나는데, 노트북 것과 서버 것은 뭐가 다른가?

이 그림이 없으면 "노트북 Docker를 꺼도 운영이 괜찮나", "DB 포트를 열어야 하나" 같은 판단을 할 수 없다.

## 3. 기본 개념

### 3.1 서버와 Docker

- **서버**는 컴퓨터다. 이 프로젝트에는 컴퓨터가 셋 나온다: 지원 노트북, 학교 실습 서버 **s2**, 학교 DB 서버 **s4**.
- **이미지**는 프로그램이 설치된 상자의 틀이다(`pgvector/pgvector:pg17`, `redis:7.4`). **컨테이너**는 그 틀로 띄운 상자 하나다.
- **Docker**는 컴퓨터 안에 컨테이너를 만들어 돌리는 도구다. **컴퓨터마다 따로 있다.** 노트북의 Docker Desktop 화면에는 노트북의 컨테이너만 보인다. s2의 컨테이너를 보려면 s2에 ssh로 들어가 `docker ps`를 친다.

**왜 서버에서도 Docker를 쓰나**

| | 서버에 직접 설치 | Docker로 띄우기 |
| --- | --- | --- |
| 권한 | 관리자(sudo)가 필요한데 학생 계정에는 보통 없음 | `docker run`이면 됨 |
| 다른 학생과 충돌 | 서버에 PostgreSQL이 하나라 버전·포트·설정을 같이 씀 | 각자 컨테이너, 이름(`aigj017-…`)만 다르면 안 겹침 |
| 확장(pgvector) | 직접 빌드해 설치 | 이미지에 들어 있음 |
| 지우기·다시 띄우기 | 설치 파일이 여기저기 남음 | `docker rm`이면 사라짐(데이터는 볼륨에 남음) |
| 개발과 같나 | 버전·설정이 달라지기 쉬움 | 노트북·테스트·운영이 **같은 이미지** |

### 3.2 포트와 docker 네트워크: 건물·방·현관문

비유: 컴퓨터는 **건물**, 컨테이너는 건물 안의 **방**이다.

- **방 안의 포트**(예: PostgreSQL 5432)는 같은 건물 안 복도에서 방을 찾아가는 번호다. 같은 docker 네트워크(복도)에 있는 컨테이너끼리는 **컨테이너 이름과 이 번호**로 바로 닿는다: `aigj017-recommend-db:5432`. 컨테이너마다 번호 공간이 따로라, 다른 학생의 PostgreSQL도 5432를 써도 부딪히지 않는다.
- **건물 현관문**(서버 포트)은 건물 **바깥**에서 들어오는 문이다. `-p 8460:8460`은 "현관문 8460을 이 방으로 연결"이라는 뜻이다. s2는 공용 건물이라 학교가 학생마다 현관문 번호를 나눠 줬다(지원은 8460~8469).

```
          인터넷 (사용자)
               │  https://now-log.java21.net → 학교 nginx
       현관문 8460 (할당받은 번호)
┌──────────── s2 건물 ─────────────────────────────┐
│              ▼                                    │
│        [앱 방] aigj017-app                        │
│              │ 복도(docker 네트워크 aigj017-net)   │
│              ▼                                    │
│        [DB 방] aigj017-recommend-db (5432)        │
│        현관문 연결 없음                            │
└───────────────────────────────────────────────────┘
```

운영 PostgreSQL은 현관문을 열지 않았다. 같은 s2 안의 앱만 복도로 들어가면 되고, 바깥에서 DB 로그인을 시도할 수 있게 되면 위험하기 때문이다. **포트를 열었는지와 어느 컴퓨터에 있는지는 상관이 없다.**

노트북의 개발 DB가 `5432:5432`로 현관문을 연 것은, 노트북에서 **직접** 실행한 개발 서버(`./mvnw spring-boot:run`, 컨테이너가 아님)가 `localhost:5432`로 들어가야 하기 때문이다.

### 3.3 개발용과 운영용은 두 벌이다

같은 프로그램을 두 컴퓨터에 하나씩 띄운다. 데이터도, 연결 정보도 따로이고 서로 연결되지 않는다.

| 프로그램 | 개발용 (지원 노트북) | 운영용 |
| --- | --- | --- |
| PostgreSQL | `blog-postgres`, `localhost:5432`, `blog`/`blog` | `aigj017-recommend-db` (s2), `blog` 계정, 비밀번호는 GitHub secret `RECOMMEND_DB_PASSWORD` |
| Redis | `blog-redis` | `aigj017-redis` (s2) |
| Ollama | `blog-ollama` | `aigj017-ollama` (s2) |
| 블로그 앱 | `./mvnw spring-boot:run` (8080, 컨테이너 아님) | `aigj017-app` (s2, 8460) |
| MySQL | `blog-mysql` (스텝 23부터 안 씀) | s4 학교 MySQL (스텝 24 전까지. 우리가 띄운 것 아님) |
| 메일 | `blog-mailpit`(가짜 메일함) | 없음(Gmail로 실제 발송) |

- 개발용 비밀번호(`blog`)는 공개돼도 상관없어서 `docker-compose.yml`·`application-dev.yml`에 적혀 있다. 지원이 따로 설정할 것이 없다.
- 운영 비밀번호는 GitHub secrets에만 있고, 배포할 때 `deploy.sh`가 꺼내 쓴다. 주소·사용자 이름은 `deploy.sh`에 적혀 있다.
- **노트북 Docker를 꺼도 운영은 그대로다.** 꺼지는 것은 노트북의 개발 서버와 `./mvnw test`(Testcontainers도 Docker를 쓴다)뿐이다. 배포는 GitHub Actions가 GitHub 서버에서 이미지를 만들어 s2로 보내므로 노트북과 상관없다.

## 4. 동작 원리: 누가 운영 컨테이너를 띄우나

```
지원: PR 병합
  → GitHub Actions(GitHub 서버): 테스트 → 앱 이미지 빌드 → scp로 s2에 이미지·deploy.sh 보냄
  → ssh로 s2에 들어가 bash ~/now-log/deploy/deploy.sh   (지원 계정으로 docker run 하는 것과 같다)
     네트워크 aigj017-net → Redis → PostgreSQL(없으면 만듦) → blog DB(없으면 만듦)
     → Ollama → 앱(-p 8460:8460)
```

- `--restart unless-stopped`: 서버가 재부팅돼도 docker가 컨테이너를 다시 띄운다.
- 데이터는 **볼륨**(`aigj017-recommend-data`, `aigj017-redis-data`, `aigj017-ollama`)과 `~/uploads`에 있다. 컨테이너를 지워도 남고, 볼륨을 지우면 사라진다(백업 없음, `docker volume rm`·`docker system prune --volumes` 금지).

스텝 24 전과 후:

```
스텝 24 전                                       스텝 24 후
s2: aigj017-app ──▶ s4 MySQL (회원·글)            s2: aigj017-app ──▶ aigj017-recommend-db
          └──────▶ aigj017-recommend-db                                 └ blog DB (회원·글·임베딩)
                     └ recommend DB (임베딩만)                          └ recommend DB (옛 임베딩)
```

## 5. 이 프로젝트에서는

### 5.1 같은 컨테이너에 DB를 하나 더

`deploy/deploy.sh`:

```bash
# 주 DB(blog)가 없으면 만든다. 표는 앱이 뜰 때 Flyway가 만든다. 옛 recommend DB(스텝 22까지의 임베딩)는 건드리지 않는다
if [ -z "$(docker exec "$DB" psql -U blog -d recommend -tAc "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'")" ]; then
  docker exec "$DB" createdb -U blog "$DB_NAME"
  echo "   $DB_NAME DB를 새로 만들었습니다. 운영 데이터를 옮기려면 deploy/migrate-from-mysql.sh를 실행하세요"
fi
```

- 컨테이너(`aigj017-recommend-db`)는 2차 배포 때 추천용으로 만든 것을 그대로 쓴다. PostgreSQL 하나 안에 DB를 여러 개 둘 수 있어서 `blog` DB를 하나 더 만든다. 이름에 `recommend`가 남은 이유다.
- 컨테이너 안에서 `psql`·`createdb`를 실행하면 비밀번호 없이 된다(같은 컨테이너 안의 접속은 믿는 설정).
- 앱에 넘기는 주소: `jdbc:postgresql://aigj017-recommend-db:5432/blog`. 컨테이너 이름이 곧 주소다(3.2).
- `-d recommend`로 접속해 확인하므로, 옛 `recommend` DB를 지우려면 이 줄부터 바꿔야 한다.

### 5.2 비밀번호를 명령줄에 쓰지 않기

```bash
DB_PASSWORD="$RECOMMEND_DB_PASSWORD" docker run -d --name "$APP" … -e DB_PASSWORD …
```

`-e DB_PASSWORD=값`으로 쓰면 그 값이 명령줄에 들어가 서버의 다른 사용자도 `ps`로 볼 수 있다. 공용 서버라 특히 조심한다. 앞에 변수를 붙여 이 명령의 환경으로만 주고, `-e DB_PASSWORD`(값 없이)로 "이 환경 변수를 그대로 넘겨라"라고 한다.

### 5.3 운영 DB 들여다보기

포트를 열지 않았으니 노트북 IntelliJ에서는 바로 붙을 수 없다. s2에서:

```bash
docker exec -it aigj017-recommend-db psql -U blog -d blog     # 컨테이너 안이라 비밀번호 없음
docker run --rm -it --network aigj017-net postgres:17 psql -h aigj017-recommend-db -U blog -d blog   # 다른 컨테이너에서(비밀번호 필요)
```

나중에 노트북에서 보고 싶으면 할당 포트 하나를 `127.0.0.1`에만 열고 SSH 터널로 들어가는 방법이 있다(지금은 하지 않음).

## 6. 자주 하는 실수와 함정

- **노트북 Docker 화면에서 운영 컨테이너를 찾는다.** Docker는 컴퓨터마다 따로다. 운영은 s2에서 `docker ps`.
- **"포트를 안 열었으니 노트북 것"이라고 생각한다.** 포트를 여는 것은 바깥에서 들어올 문을 다는 것일 뿐이다.
- **DB 포트를 아무 데나 연다.** 인터넷에서 DB 로그인을 시도할 수 있게 된다. 같은 서버 안의 앱만 쓰면 열 필요가 없다.
- **`mysql:8.4` 컨테이너가 MySQL 서버라고 생각한다.** s4에 접속하려고 `docker run --rm … mysql:8.4 mysql -h s4…`로 띄운 것은 **접속 프로그램**만 잠깐 빌린 것이다(`--rm`이라 끝나면 사라짐).
- **볼륨을 지운다.** 컨테이너는 다시 만들면 되지만 볼륨에는 운영 데이터가 있다. 백업이 없다.
- **비밀번호를 명령줄에 쓴다.** `ps`와 셸 기록에 남는다.

## 7. 직접 해 보기

1. **어디에 무엇이**: 노트북에서 `docker ps --format '{{.Names}}  {{.Ports}}'` → `blog-*`와 열린 포트. s2에 ssh로 들어가 같은 명령 → `aigj017-*`, 앱만 `8460`이 열려 있다.
2. **복도로 닿기**: s2에서 `docker run --rm --network aigj017-net postgres:17 pg_isready -h aigj017-recommend-db` → 이름으로 닿는다. `--network`를 빼면 이름을 못 찾는다.
3. **DB 목록**: s2에서 `docker exec aigj017-recommend-db psql -U blog -l` → `blog`와 `recommend`.
4. **노트북 Docker를 끄고**: https://now-log.java21.net 이 그대로 열리는지 본다.

## 8. 확인 문제

1. 노트북의 Docker Desktop에 운영 컨테이너가 보이지 않는 이유는?
<details><summary>답</summary>Docker는 컴퓨터마다 따로 돈다. 운영 컨테이너는 s2 서버의 Docker 안에 있고, Docker Desktop은 노트북의 Docker만 보여 준다.</details>

2. 운영 PostgreSQL에 서버 포트를 열지 않았는데도 앱이 접속할 수 있는 이유는?
<details><summary>답</summary>앱과 DB가 같은 s2의 같은 docker 네트워크(aigj017-net)에 있어서 컨테이너 이름과 내부 포트(aigj017-recommend-db:5432)로 바로 닿는다. 서버 포트는 서버 바깥에서 들어올 때만 필요하다.</details>

3. 서버에서도 프로그램을 직접 설치하지 않고 Docker로 띄우는 이유는?
<details><summary>답</summary>공용 서버라 관리자 권한 없이 띄울 수 있고, 다른 학생과 버전·포트가 부딪히지 않는다. 개발·테스트·운영이 같은 이미지라 환경 차이가 줄고, 지우거나 다시 띄우기 쉽다.</details>

4. 노트북의 개발 DB는 왜 `5432:5432`로 포트를 열었나?
<details><summary>답</summary>개발 서버(./mvnw spring-boot:run)는 컨테이너가 아니라 노트북에서 직접 돌아서, localhost:5432(현관문)로 들어가야 DB에 닿는다.</details>

5. 지원이 직접 넣은 운영 DB 연결 정보는 무엇이고, 나머지(주소·사용자)는 어디에 있나?
<details><summary>답</summary>GitHub secret RECOMMEND_DB_PASSWORD(비밀번호)만 넣었다. 주소(aigj017-recommend-db:5432/blog)와 사용자(blog)는 deploy.sh에 적혀 있다. 개발용 연결 정보는 코드(docker-compose.yml, application-dev.yml)에 있다.</details>

6. `-e DB_PASSWORD="$값"` 대신 `DB_PASSWORD="$값" docker run … -e DB_PASSWORD`로 쓴 이유는?
<details><summary>답</summary>앞의 방법은 비밀번호가 docker 명령줄에 들어가 서버의 다른 사용자도 ps로 볼 수 있다. 뒤의 방법은 이 명령의 환경 변수로만 주고 docker에는 변수 이름만 넘긴다.</details>

## 9. 더 읽을거리

- Docker 문서: "Docker overview"(이미지와 컨테이너), "Networking overview"(사용자 정의 브리지 네트워크와 컨테이너 이름), "Publishing ports", "Volumes"
- PostgreSQL 공식 이미지 문서(`POSTGRES_DB`, `POSTGRES_USER`, 처음 한 번만 만드는 초기화)
- [65](./65-postgresql-vs-mysql.md): MySQL과 PostgreSQL 비교, 데이터 옮기기
