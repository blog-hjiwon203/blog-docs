# Docker와 서버: 이미지·컨테이너·Compose, 개발용과 운영용

> 관련 스텝: [스텝 1](../../스텝-01.md) · [스텝 24](../../스텝-24.md) (T129)
> 관련 개념: [Flyway](../2-데이터/02-Flyway-마이그레이션.md), [테스트](./04-Spring-테스트.md)(Testcontainers), [설정과 프로필](./02-설정과-프로필.md), [PostgreSQL vs MySQL](../2-데이터/03-PostgreSQL-vs-MySQL.md)(DB 비교·옮기기), [임베딩과 의미 검색](../2-데이터/11-임베딩과-의미-검색.md), [이중화와 롤링 배포](./06-이중화와-롤링-배포.md)

> **한 줄 답**: Docker는 프로그램과 설정을 통째로 묶은 **이미지**를 받아 격리된 상자(**컨테이너**)로 띄우는 도구이고, Docker Compose는 그런 컨테이너 여러 개를 파일 하나로 정의해 명령 하나로 띄운다. Docker는 서버를 대신하는 게 아니라 **서버(컴퓨터)에 프로그램을 상자째 띄우는 도구**이고, 컴퓨터마다 따로 있다. 그래서 개발용(노트북)과 운영용(s2)이 두 벌이고, 노트북의 Docker 화면에는 운영 컨테이너가 보이지 않는다. 포트를 여는 것은 바깥에서 들어올 문을 다는 일일 뿐, 위치와는 상관이 없다.

> 이 문서는 두 시기의 이야기를 합쳤다. 1~3.5, 4.1, 5.1~5.3은 **스텝 1**(개발 환경을 처음 만들 때, 그때 DB는 MySQL 8.4) 기준이고, 3.6~3.8, 4.2, 5.4~5.6은 **스텝 24**(운영 DB를 서버의 PostgreSQL로 옮길 때) 기준이다. 개발 DB도 스텝 23에서 PostgreSQL(`blog-postgres`)로 바뀌었고 `blog-mysql`은 더 쓰지 않는다(3.8 표). 원리(이미지, 볼륨, 포트, healthcheck)는 그대로다.

> 데이터를 MySQL에서 PostgreSQL로 옮기는 이야기(COPY, 이스케이프, 시퀀스, 전환과 되돌리기)는 [PostgreSQL vs MySQL](../2-데이터/03-PostgreSQL-vs-MySQL.md)에 합쳤다(2026-10-13).

## 1. 이 문서로 배우는 것

- **이미지**와 **컨테이너**가 무엇이고 가상머신과 무엇이 다른지
- `docker-compose.yml`의 항목(`image`, `environment`, `command`, `ports`, `volumes`, `healthcheck`)이 하는 일
- 컨테이너를 지워도 **데이터가 남는 원리**(볼륨)
- 포트 충돌을 알아보고 해결하는 방법(스텝 1의 로컬 Redis 사건)
- 자주 쓰는 명령과 `down`과 `down -v`의 차이
- 서버, Docker, 컨테이너, 이미지의 관계. 서버에서도 Docker를 쓰는 이유
- 포트와 docker 네트워크: 건물·방·현관문 비유
- 개발용과 운영용이 왜 두 벌인가, 연결 정보는 어디에 있나
- 이 프로젝트에서 무엇이 어느 컴퓨터에 있는가(스텝 24 전과 후)
- 같은 컨테이너에 DB를 하나 더 만들기, 비밀번호를 명령줄에 쓰지 않기

**먼저 알면 좋은 것**: 터미널 기본 명령, "포트"가 무엇인지(한 컴퓨터에서 여러 프로그램이 네트워크를 나눠 쓰는 번호).

---

## 2. 왜 필요한가

### 2.1 개발 환경: 누가 띄워도 같은 DB

블로그 서버를 띄우려면 MySQL 8과 Redis가 필요하다(스텝 1 기준. 지금은 PostgreSQL과 Redis). 직접 설치한다면:

- macOS에 MySQL을 설치하고, 계정과 DB를 만들고, 문자셋을 utf8mb4로 바꾸고, 시간대를 맞춘다.
- 팀원 PC가 Windows면 설치 방법이 다르다. 누구는 MySQL 8.0, 누구는 8.4라 동작이 미묘하게 다르다.
- 다른 프로젝트가 MySQL 5.7을 요구하면 둘을 한 컴퓨터에 깔기 어렵다.
- 다 쓰고 지우려면 흔적이 여기저기 남는다.

Docker는 **"MySQL 8.4가 설치되고 설정된 상태"를 통째로 묶은 이미지**를 내려받아 격리된 상자(컨테이너)로 띄운다. Docker Compose는 그런 컨테이너 여러 개(MySQL + Redis)를 **파일 하나로 정의하고 명령 하나로** 띄운다. 누가 실행해도 같은 환경이 나온다.

### 2.2 운영 서버: 어디에 무엇이 떠 있나

스텝 24에서 운영 DB를 옮기며 지원이 계속 헷갈린 질문들이다.

- 운영용 PostgreSQL은 어디 떠 있나? 노트북 Docker에는 개발용만 보인다.
- 할당받은 포트가 아니라 내부 포트로 열었으니 노트북에 띄운 것 아닌가?
- 다 서버에 띄울 거면 Docker는 왜 필요한가?
- PostgreSQL 연결 정보는 하나만 넣은 기억이 나는데, 노트북 것과 서버 것은 뭐가 다른가?

이 그림이 없으면 "노트북 Docker를 꺼도 운영이 괜찮나", "DB 포트를 열어야 하나" 같은 판단을 할 수 없다.

---

## 3. 기본 개념

### 3.1 이미지와 컨테이너

| 용어 | 비유 | 설명 |
| --- | --- | --- |
| 이미지 | 설치 CD, 클래스 | 프로그램과 필요한 파일·설정을 묶은 **읽기 전용** 꾸러미. `mysql:8.4`처럼 `이름:태그` |
| 컨테이너 | 설치해서 실행 중인 프로그램, 객체 | 이미지로 만든 **실행 중인** 격리 환경. 같은 이미지로 여러 개를 만들 수 있다 |
| 레지스트리 | 앱 스토어 | 이미지를 올리고 내려받는 곳. 기본은 Docker Hub |
| 볼륨 | 외장 하드 | 컨테이너 밖에 두는 저장 공간. 컨테이너를 지워도 남는다 |

```
Docker Hub ── pull ──▶ 이미지 mysql:8.4 ── run ──▶ 컨테이너 blog-mysql
                                          └─ run ──▶ (같은 이미지로 다른 컨테이너도 가능)
```

### 3.2 가상머신과 차이

```
가상머신(VM)                          컨테이너
┌────────┐ ┌────────┐                ┌────────┐ ┌────────┐
│ 앱     │ │ 앱     │                │ MySQL  │ │ Redis  │
│ 게스트 OS│ │ 게스트 OS│              └────────┘ └────────┘
└────────┘ └────────┘                ┌─────────────────────┐
┌─────────────────────┐              │ 컨테이너 런타임        │
│ 하이퍼바이저           │              │ (리눅스 커널을 함께 씀) │
└─────────────────────┘              └─────────────────────┘
        호스트 OS                              호스트 OS
```

| | 가상머신 | 컨테이너 |
| --- | --- | --- |
| 격리 단위 | 운영체제 전체 | 프로세스(커널은 공유) |
| 크기 | GB 단위 | MB~수백 MB |
| 시작 | 수십 초~분 | 1초 안팎 |

macOS는 리눅스 커널이 아니라서, Docker Desktop이나 OrbStack이 **보이지 않는 작은 리눅스 VM**을 띄우고 그 안에서 컨테이너를 돌린다. 그래서 Docker Desktop(또는 OrbStack)이 켜져 있어야 `docker` 명령이 동작한다. 스텝 1 시작 때 "Cannot connect to the Docker daemon"이 나온 것은 이 VM(데몬)이 꺼져 있었기 때문이다. 두 프로그램을 동시에 켜면 서로 충돌하므로 하나만 쓴다.

### 3.3 포트 매핑

컨테이너는 자기만의 네트워크를 가진다. 컨테이너 안의 MySQL은 컨테이너 안에서 3306을 연다. 내 PC(호스트)에서 접근하려면 **호스트 포트를 컨테이너 포트에 이어** 줘야 한다.

```
ports:
  - "3306:3306"
     호스트  컨테이너

내 PC의 localhost:3306 ──▶ 컨테이너 blog-mysql의 3306
```

`"13306:3306"`으로 쓰면 내 PC에서는 13306으로 접속한다. 같은 호스트 포트를 두 프로그램이 동시에 쓸 수는 없다(5.2 포트 충돌). 운영 서버에서 이 "호스트 포트"가 어떤 의미인지는 3.7의 건물·현관문 비유로 다시 본다.

### 3.4 볼륨: 데이터가 남는 원리

컨테이너 안에서 쓴 파일은 **컨테이너를 지우면 함께 사라진다**. MySQL 데이터가 그렇게 되면 곤란하다. 그래서 MySQL이 데이터를 쓰는 폴더(`/var/lib/mysql`)를 **컨테이너 밖의 볼륨**에 연결한다.

```
volumes:
  - mysql-data:/var/lib/mysql
    볼륨 이름   컨테이너 안 경로

컨테이너 blog-mysql ──쓰기──▶ /var/lib/mysql ═══ 볼륨 mysql-data (Docker가 관리하는 저장 공간)
컨테이너를 지우고 새로 만들어도, 같은 볼륨을 연결하면 테이블과 데이터가 그대로 있다
```

| 종류 | 쓰는 법 | 특징 |
| --- | --- | --- |
| 이름 있는 볼륨 | `mysql-data:/var/lib/mysql` | Docker가 위치를 관리. DB 데이터에 적합 |
| 바인드 마운트 | `./data:/var/lib/mysql` | 내 PC의 폴더를 직접 연결. 파일을 눈으로 볼 수 있음 |

### 3.5 healthcheck

컨테이너가 **시작됐다**와 **요청을 받을 수 있다**는 다르다. MySQL은 컨테이너가 뜬 뒤에도 초기화(계정 생성 등)에 몇 초가 걸린다. healthcheck는 주기적으로 명령을 실행해 성공하면 `healthy`로 표시한다.

```
docker compose ps
NAME         STATUS
blog-mysql   Up 2 seconds (health: starting)    ← 아직 준비 중
blog-mysql   Up 15 seconds (healthy)            ← 이제 접속 가능
```

다른 서비스가 `depends_on: condition: service_healthy`로 "healthy가 될 때까지 기다렸다 시작"할 수도 있다(이 프로젝트는 Spring Boot를 compose 밖에서 띄워서 쓰지 않는다).

### 3.6 서버와 Docker

여기부터는 노트북 밖, 운영 서버 이야기다(스텝 24).

- **서버**는 컴퓨터다. 이 프로젝트에는 컴퓨터가 셋 나온다: 지원 노트북, 학교 실습 서버 **s2**, 학교 DB 서버 **s4**.
- 3.1의 이미지·컨테이너는 서버에서도 그대로다. 운영에서 쓰는 이미지는 `pgvector/pgvector:pg17`, `redis:7.4` 같은 것이다.
- **Docker**는 컴퓨터 안에 컨테이너를 만들어 돌리는 도구다. **컴퓨터마다 따로 있다.** 노트북의 Docker Desktop 화면에는 노트북의 컨테이너만 보인다. s2의 컨테이너를 보려면 s2에 ssh로 들어가 `docker ps`를 친다.

**왜 서버에서도 Docker를 쓰나**

| | 서버에 직접 설치 | Docker로 띄우기 |
| --- | --- | --- |
| 권한 | 관리자(sudo)가 필요한데 학생 계정에는 보통 없음 | `docker run`이면 됨 |
| 다른 학생과 충돌 | 서버에 PostgreSQL이 하나라 버전·포트·설정을 같이 씀 | 각자 컨테이너, 이름(`aigj017-…`)만 다르면 안 겹침 |
| 확장(pgvector) | 직접 빌드해 설치 | 이미지에 들어 있음 |
| 지우기·다시 띄우기 | 설치 파일이 여기저기 남음 | `docker rm`이면 사라짐(데이터는 볼륨에 남음) |
| 개발과 같나 | 버전·설정이 달라지기 쉬움 | 노트북·테스트·운영이 **같은 이미지** |

### 3.7 포트와 docker 네트워크: 건물·방·현관문

비유: 컴퓨터는 **건물**, 컨테이너는 건물 안의 **방**이다.

- **방 안의 포트**(예: PostgreSQL 5432)는 같은 건물 안 복도에서 방을 찾아가는 번호다. 같은 docker 네트워크(복도)에 있는 컨테이너끼리는 **컨테이너 이름과 이 번호**로 바로 닿는다: `aigj017-recommend-db:5432`. 컨테이너마다 번호 공간이 따로라, 다른 학생의 PostgreSQL도 5432를 써도 부딪히지 않는다. (스텝 1의 compose도 같은 원리로 네트워크 `blog_default`를 만들어 서비스 이름으로 서로 찾게 한다. 4.1)
- **건물 현관문**(서버 포트)은 건물 **바깥**에서 들어오는 문이다. `-p 8460:8460`은 "현관문 8460을 이 방으로 연결"이라는 뜻이다(3.3의 포트 매핑과 같은 것). s2는 공용 건물이라 학교가 학생마다 현관문 번호를 나눠 줬다(지원은 8460~8469).

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

### 3.8 개발용과 운영용은 두 벌이다

같은 프로그램을 두 컴퓨터에 하나씩 띄운다. 데이터도, 연결 정보도 따로이고 서로 연결되지 않는다.

| 프로그램 | 개발용 (지원 노트북) | 운영용 |
| --- | --- | --- |
| PostgreSQL | `blog-postgres`, `localhost:5432`, `blog`/`blog` | `aigj017-recommend-db` (s2), `blog` 계정, 비밀번호는 GitHub secret `RECOMMEND_DB_PASSWORD` |
| Redis | `blog-redis` | `aigj017-redis` (s2) |
| Ollama | `blog-ollama` | `aigj017-ollama` (s2) |
| 블로그 앱 | `./mvnw spring-boot:run` (8080, 컨테이너 아님) | `aigj017-app` (s2, 8460), `aigj017-app-2` (s2, 8461). 스텝 25부터 두 대, 학교 nginx upstream이 나눠 보냄([이중화와 롤링 배포](./06-이중화와-롤링-배포.md)) |
| MySQL | `blog-mysql` (스텝 23부터 안 씀) | s4 학교 MySQL (스텝 24 전까지. 우리가 띄운 것 아님) |
| 메일 | `blog-mailpit`(가짜 메일함) | 없음(Gmail로 실제 발송) |

- 개발용 비밀번호(`blog`)는 공개돼도 상관없어서 `docker-compose.yml`·`application-dev.yml`에 적혀 있다. 지원이 따로 설정할 것이 없다.
- 운영 비밀번호는 GitHub secrets에만 있고, 배포할 때 `deploy.sh`가 꺼내 쓴다. 주소·사용자 이름은 `deploy.sh`에 적혀 있다.
- **노트북 Docker를 꺼도 운영은 그대로다.** 꺼지는 것은 노트북의 개발 서버와 `./mvnw test`(Testcontainers도 Docker를 쓴다)뿐이다. 배포는 GitHub Actions가 GitHub 서버에서 이미지를 만들어 s2로 보내므로 노트북과 상관없다.

---

## 4. 동작 원리

### 4.1 `docker compose up -d`가 하는 일 (개발용, 스텝 1)

```
1. 현재 폴더의 docker-compose.yml을 읽는다 (프로젝트 이름 = 폴더 이름 "blog")
2. 네트워크 blog_default를 만든다 (같은 compose의 컨테이너끼리 서비스 이름으로 통신 가능)
3. 볼륨 blog_mysql-data가 없으면 만든다
4. 이미지가 PC에 없으면 Docker Hub에서 pull (mysql:8.4, redis:7.4)
5. 컨테이너를 만든다: 환경 변수·명령·포트·볼륨을 붙여서
6. 컨테이너를 시작한다. -d(detached)라 터미널을 돌려준다
7. healthcheck가 5초마다 실행된다
```

MySQL 이미지는 **데이터 폴더가 비어 있을 때만** `MYSQL_DATABASE`, `MYSQL_USER` 같은 환경 변수로 DB와 계정을 만든다. 볼륨에 이미 데이터가 있으면 환경 변수를 바꿔도 다시 만들지 않는다(6절의 함정).

### 4.2 누가 운영 컨테이너를 띄우나 (운영용, 스텝 24)

운영에는 compose 파일이 없다. GitHub Actions가 서버에 들어가 스크립트로 `docker run`을 차례로 실행한다.

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

---

## 5. 이 프로젝트에서는

### 5.1 개발용 `docker-compose.yml` (스텝 1 기준)

`docker-compose.yml` (저장소 루트). 아래는 스텝 1에 만든 모양이다. 지금은 MySQL 자리가 PostgreSQL(`blog-postgres`)로 바뀌었고(스텝 23), Ollama·Mailpit도 함께 띄운다(3.8 표).

```yaml
# 개발용 MySQL 8, Redis. 실행: docker compose up -d
services:
  mysql:                                   # 서비스 이름. compose 안에서 이 이름으로 서로 찾는다
    image: mysql:8.4                       # MySQL 8.4 LTS. 태그를 정확히 적어 누구나 같은 버전
    container_name: blog-mysql             # docker exec blog-mysql ... 처럼 쓰는 이름
    environment:                           # 처음 데이터 폴더가 빌 때 MySQL 이미지가 읽는 값
      MYSQL_DATABASE: blog                 #   DB "blog"를 만든다
      MYSQL_USER: blog                     #   일반 계정 blog / blog 를 만든다 (application-dev.yml과 같아야 함)
      MYSQL_PASSWORD: blog
      MYSQL_ROOT_PASSWORD: root            #   관리자 root 비밀번호
      TZ: Asia/Seoul                       # 컨테이너 시간대 → NOW(), CURRENT_TIMESTAMP가 한국 시간
    command:                               # mysqld를 시작할 때 붙일 옵션
      - --character-set-server=utf8mb4     #   한글·이모지를 저장할 수 있는 문자셋
      - --collation-server=utf8mb4_0900_ai_ci   # 정렬·비교 규칙 (MySQL 8 기본)
    ports:
      - "3306:3306"                        # 내 PC localhost:3306 → 컨테이너 3306
    volumes:
      - mysql-data:/var/lib/mysql          # 데이터는 볼륨에. 컨테이너를 지워도 남는다
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost", "-uroot", "-proot"]   # 응답하면 성공
      interval: 5s                         # 5초마다
      timeout: 3s                          # 3초 안에 답이 없으면 실패 한 번
      retries: 20                          # 20번 연속 실패하면 unhealthy

  redis:
    image: redis:7.4
    container_name: blog-redis
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]   # PONG이 오면 성공
      interval: 5s
      timeout: 3s
      retries: 20
    # 볼륨 없음: Redis는 캐시·토큰·연타 방지 키처럼 사라져도 되는 값만 둔다

volumes:
  mysql-data:                              # 이름 있는 볼륨 선언 (실제 이름은 blog_mysql-data)
```

**스프링과 연결되는 곳**: `application-dev.yml`의 `jdbc:mysql://localhost:3306/blog`, `username: blog`, `redis.host: localhost`, `port: 6379`가 위 값과 짝이다([설정과 프로필](./02-설정과-프로필.md)).

**테스트와의 관계**: 테스트는 이 compose를 쓰지 않는다. Testcontainers가 **같은 이미지**(`mysql:8.4`, `redis:7.4`)로 테스트용 컨테이너를 새로 띄우고, 빈 포트를 골라 연결한다([Spring 테스트](./04-Spring-테스트.md)). 그래서 테스트 중 `docker ps`를 보면 컨테이너가 더 보인다. 같은 이미지를 써야 개발에서 되는 것이 테스트에서도 된다.

### 5.2 스텝 1의 포트 충돌 사건

스텝 1 점검에서 `lsof`로 포트를 보니 Homebrew로 설치된 Redis가 이미 6379를 쓰고 있었다.

```bash
lsof -iTCP:6379 -sTCP:LISTEN -P
# redis-ser 541 ... TCP localhost:6379 (LISTEN)
brew services list | grep redis
# redis  started
```

이 상태에서 `docker compose up -d`를 하면 6379를 열 수 없어 Redis 컨테이너가 실패한다(`port is already allocated` 또는 `address already in use`). 해결은 둘 중 하나였다.

- (a) 로컬 Redis를 끈다: `brew services stop redis` ← 지원이 고름
- (b) compose 쪽 포트를 바꾼다: `"6380:6379"` + `application-dev.yml`의 `port: 6380`

### 5.3 다른 프로세스를 끌 때의 주의

스텝 2에서 8080 포트를 다른 서버가 쓰고 있었는데, 정리하면서 `pkill -f com.nhnacademy.blog.BlogApplication`을 실행했다. 이 명령은 이름이 맞는 **모든** 프로세스를 끄기 때문에 IntelliJ에서 띄운 서버까지 꺼졌을 수 있다. 포트를 쓰는 프로세스를 정확히 끄려면 PID를 확인하고 그 PID만 끈다.

```bash
lsof -tiTCP:8080 -sTCP:LISTEN     # PID만 출력
kill <PID>
```

### 5.4 같은 컨테이너에 DB를 하나 더 (스텝 24)

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
- 앱에 넘기는 주소: `jdbc:postgresql://aigj017-recommend-db:5432/blog`. 컨테이너 이름이 곧 주소다(3.7).
- `-d recommend`로 접속해 확인하므로, 옛 `recommend` DB를 지우려면 이 줄부터 바꿔야 한다.

### 5.5 비밀번호를 명령줄에 쓰지 않기

```bash
DB_PASSWORD="$RECOMMEND_DB_PASSWORD" docker run -d --name "$APP" … -e DB_PASSWORD …
```

`-e DB_PASSWORD=값`으로 쓰면 그 값이 명령줄에 들어가 서버의 다른 사용자도 `ps`로 볼 수 있다. 공용 서버라 특히 조심한다. 앞에 변수를 붙여 이 명령의 환경으로만 주고, `-e DB_PASSWORD`(값 없이)로 "이 환경 변수를 그대로 넘겨라"라고 한다.

### 5.6 운영 DB 들여다보기

포트를 열지 않았으니 노트북 IntelliJ에서는 바로 붙을 수 없다. s2에서:

```bash
docker exec -it aigj017-recommend-db psql -U blog -d blog     # 컨테이너 안이라 비밀번호 없음
docker run --rm -it --network aigj017-net postgres:17 psql -h aigj017-recommend-db -U blog -d blog   # 다른 컨테이너에서(비밀번호 필요)
```

나중에 노트북에서 보고 싶으면 할당 포트 하나를 `127.0.0.1`에만 열고 SSH 터널로 들어가는 방법이 있다(지금은 하지 않음).

---

## 6. 자주 하는 실수와 함정

### 6.1 개발 환경에서

| 실수 | 증상 | 해결 |
| --- | --- | --- |
| Docker Desktop/OrbStack을 안 켬 | `Cannot connect to the Docker daemon` | 앱을 켠다(하나만) |
| 호스트 포트가 이미 사용 중 | `port is already allocated` | `lsof -iTCP:포트 -sTCP:LISTEN -P`로 범인을 찾아 끄거나 포트를 바꾼다 |
| 볼륨이 있는 채로 `MYSQL_PASSWORD`를 바꿈 | 새 비밀번호로 접속 실패 | 환경 변수는 첫 초기화 때만 쓰인다. 데이터를 버려도 되면 `down -v` 후 `up -d` |
| `down -v`를 습관처럼 씀 | 개발 DB 데이터가 몽땅 사라짐 | 평소엔 `down` 또는 `stop`. `-v`는 초기화가 목적일 때만 |
| `image: mysql` (태그 없음) | `latest`를 받아 어느 날 버전이 바뀜 | 태그를 정확히(`mysql:8.4`) |
| healthy 전에 앱을 띄움 | 첫 연결 실패 | `docker compose ps`에서 healthy 확인 후 |
| compose 파일이 없는 폴더에서 명령 | `no configuration file provided` | 저장소 루트에서 실행 |
| 마이그레이션 실패로 DB가 반쯤 만들어짐 | 다시 시작해도 Flyway 오류 | 개발 DB는 `down -v`로 초기화([Flyway 마이그레이션](../2-데이터/02-Flyway-마이그레이션.md) 4.2) |

### 6.2 운영 서버에서

- **노트북 Docker 화면에서 운영 컨테이너를 찾는다.** Docker는 컴퓨터마다 따로다. 운영은 s2에서 `docker ps`.
- **"포트를 안 열었으니 노트북 것"이라고 생각한다.** 포트를 여는 것은 바깥에서 들어올 문을 다는 것일 뿐이다.
- **DB 포트를 아무 데나 연다.** 인터넷에서 DB 로그인을 시도할 수 있게 된다. 같은 서버 안의 앱만 쓰면 열 필요가 없다.
- **`mysql:8.4` 컨테이너가 MySQL 서버라고 생각한다.** s4에 접속하려고 `docker run --rm … mysql:8.4 mysql -h s4…`로 띄운 것은 **접속 프로그램**만 잠깐 빌린 것이다(`--rm`이라 끝나면 사라짐).
- **볼륨을 지운다.** 컨테이너는 다시 만들면 되지만 볼륨에는 운영 데이터가 있다. 백업이 없다.
- **비밀번호를 명령줄에 쓴다.** `ps`와 셸 기록에 남는다.

---

## 7. 직접 해 보기

### 7.1 노트북에서 (개발용)

자주 쓰는 명령(저장소 루트에서):

| 명령 | 하는 일 |
| --- | --- |
| `docker compose up -d` | 만들고 백그라운드로 시작 |
| `docker compose ps` | 상태(healthy 여부) |
| `docker compose logs -f mysql` | 로그 따라 보기(Ctrl+C로 빠져나옴) |
| `docker compose exec mysql mysql -ublog -pblog blog` | 컨테이너 안에서 MySQL 접속 |
| `docker exec -it blog-redis redis-cli` | 컨테이너 이름으로 Redis 접속 |
| `docker compose stop` | 멈춤(컨테이너 유지) |
| `docker compose down` | 멈추고 컨테이너·네트워크 삭제. **볼륨은 남음** |
| `docker compose down -v` | 위 + **볼륨까지 삭제 → 데이터 전부 사라짐** |
| `docker volume ls` | 볼륨 목록 |

실습:

1. **데이터가 남는지 확인**
   ```bash
   docker compose exec mysql mysql -ublog -pblog blog -e "SELECT COUNT(*) FROM member"
   docker compose down          # 컨테이너 삭제
   docker compose up -d         # 다시 만듦
   docker compose exec mysql mysql -ublog -pblog blog -e "SELECT COUNT(*) FROM member"
   ```
   기대: 두 숫자가 같다(볼륨 덕분). `down -v`였다면 테이블 자체가 없다.

2. **healthcheck 상태 변화 보기**
   ```bash
   docker compose restart mysql && watch -n1 docker compose ps
   ```
   `health: starting` → `healthy`로 바뀌는 데 몇 초 걸리는지 본다.

3. **Redis 들여다보기** (스텝 4에서 로그인하면 토큰 키가 생긴다)
   ```bash
   docker exec -it blog-redis redis-cli
   > KEYS *
   > TTL auth:refresh:<id>
   ```

4. **포트를 바꿔 보기** (연습 후 되돌린다)
   `ports: - "13306:3306"`으로 바꾸고 `docker compose up -d` → `application-dev.yml`의 URL도 `localhost:13306`으로 바꿔야 앱이 붙는다는 것을 확인한다.

5. **이미지와 컨테이너 구분**
   ```bash
   docker images | grep -E "mysql|redis"     # 이미지
   docker ps -a  | grep blog                 # 컨테이너
   ```

### 7.2 노트북과 서버를 오가며 (운영용)

6. **어디에 무엇이**: 노트북에서 `docker ps --format '{{.Names}}  {{.Ports}}'` → `blog-*`와 열린 포트. s2에 ssh로 들어가 같은 명령 → `aigj017-*`, 앱만 `8460`이 열려 있다.
7. **복도로 닿기**: s2에서 `docker run --rm --network aigj017-net postgres:17 pg_isready -h aigj017-recommend-db` → 이름으로 닿는다. `--network`를 빼면 이름을 못 찾는다.
8. **DB 목록**: s2에서 `docker exec aigj017-recommend-db psql -U blog -l` → `blog`와 `recommend`.
9. **노트북 Docker를 끄고**: https://now-log.java21.net 이 그대로 열리는지 본다.

---

## 8. 확인 문제

1. 이미지와 컨테이너의 관계를 클래스와 객체에 비유해 설명하라.
   <details><summary>답 보기</summary>이미지는 읽기 전용 설계도(클래스), 컨테이너는 그 이미지로 만든 실행 중인 인스턴스(객체)다. 같은 이미지로 여러 컨테이너를 만들 수 있다.</details>

2. `docker compose down`과 `docker compose down -v`의 차이는?
   <details><summary>답 보기</summary>둘 다 컨테이너와 네트워크를 지우지만, `-v`는 볼륨까지 지워 DB 데이터가 사라진다.</details>

3. `ports: - "3306:3306"`에서 앞과 뒤 숫자는 각각 무엇인가?
   <details><summary>답 보기</summary>앞은 호스트(내 PC) 포트, 뒤는 컨테이너 안 포트다.</details>

4. 볼륨이 있는 상태에서 `MYSQL_PASSWORD`를 `blog2`로 바꾸고 `up -d` 했더니 `blog2`로 접속이 안 된다. 왜인가?
   <details><summary>답 보기</summary>MySQL 이미지는 데이터 폴더가 비어 있을 때(최초 초기화)만 환경 변수로 계정을 만든다. 볼륨에 기존 데이터가 있으니 이전 비밀번호가 그대로다.</details>

5. Redis에는 볼륨을 두지 않았다. 왜 괜찮은가?
   <details><summary>답 보기</summary>이 프로젝트에서 Redis에는 캐시, 토큰 상태, 연타 방지 키처럼 사라져도 다시 만들어지거나 짧게만 필요한 값만 두기 때문이다. 원본 데이터는 MySQL에 있다. (개발 중 Redis를 재시작하면 로그인 상태가 풀리는 정도의 영향이 있다.)</details>

6. healthcheck가 없으면 어떤 문제가 생길 수 있나?
   <details><summary>답 보기</summary>컨테이너가 떴지만 MySQL이 아직 초기화 중일 때 앱이 접속을 시도해 실패할 수 있다. 준비됐는지 알 방법이 없다.</details>

7. 테스트는 compose의 MySQL 대신 무엇을 쓰고, 왜 같은 이미지 태그를 쓰는가?
   <details><summary>답 보기</summary>Testcontainers가 띄우는 새 컨테이너를 쓴다. 개발과 테스트가 같은 MySQL 버전이어야 한쪽에서만 되는 문제를 막을 수 있다.</details>

8. 노트북의 Docker Desktop에 운영 컨테이너가 보이지 않는 이유는?
   <details><summary>답 보기</summary>Docker는 컴퓨터마다 따로 돈다. 운영 컨테이너는 s2 서버의 Docker 안에 있고, Docker Desktop은 노트북의 Docker만 보여 준다.</details>

9. 운영 PostgreSQL에 서버 포트를 열지 않았는데도 앱이 접속할 수 있는 이유는?
   <details><summary>답 보기</summary>앱과 DB가 같은 s2의 같은 docker 네트워크(aigj017-net)에 있어서 컨테이너 이름과 내부 포트(aigj017-recommend-db:5432)로 바로 닿는다. 서버 포트는 서버 바깥에서 들어올 때만 필요하다.</details>

10. 서버에서도 프로그램을 직접 설치하지 않고 Docker로 띄우는 이유는?
    <details><summary>답 보기</summary>공용 서버라 관리자 권한 없이 띄울 수 있고, 다른 학생과 버전·포트가 부딪히지 않는다. 개발·테스트·운영이 같은 이미지라 환경 차이가 줄고, 지우거나 다시 띄우기 쉽다.</details>

11. 노트북의 개발 DB는 왜 `5432:5432`로 포트를 열었나?
    <details><summary>답 보기</summary>개발 서버(./mvnw spring-boot:run)는 컨테이너가 아니라 노트북에서 직접 돌아서, localhost:5432(현관문)로 들어가야 DB에 닿는다.</details>

12. 지원이 직접 넣은 운영 DB 연결 정보는 무엇이고, 나머지(주소·사용자)는 어디에 있나?
    <details><summary>답 보기</summary>GitHub secret RECOMMEND_DB_PASSWORD(비밀번호)만 넣었다. 주소(aigj017-recommend-db:5432/blog)와 사용자(blog)는 deploy.sh에 적혀 있다. 개발용 연결 정보는 코드(docker-compose.yml, application-dev.yml)에 있다.</details>

13. `-e DB_PASSWORD="$값"` 대신 `DB_PASSWORD="$값" docker run … -e DB_PASSWORD`로 쓴 이유는?
    <details><summary>답 보기</summary>앞의 방법은 비밀번호가 docker 명령줄에 들어가 서버의 다른 사용자도 ps로 볼 수 있다. 뒤의 방법은 이 명령의 환경 변수로만 주고 docker에는 변수 이름만 넘긴다.</details>

---

## 9. 더 읽을거리

- Docker 공식 문서 "Get started", "Docker overview"(이미지와 컨테이너) (https://docs.docker.com/get-started/)
- Docker 공식 문서 "Compose file reference" — `services`, `ports`, `volumes`, `healthcheck` (https://docs.docker.com/reference/compose-file/)
- Docker 공식 문서 "Volumes" (https://docs.docker.com/engine/storage/volumes/)
- Docker 공식 문서 "Networking overview"(사용자 정의 브리지 네트워크와 컨테이너 이름), "Publishing ports"
- Docker Hub의 `mysql` 공식 이미지 설명 — 환경 변수와 초기화 규칙 (https://hub.docker.com/_/mysql)
- Docker Hub의 `redis` 공식 이미지 설명 (https://hub.docker.com/_/redis)
- PostgreSQL 공식 이미지 문서(`POSTGRES_DB`, `POSTGRES_USER`, 처음 한 번만 만드는 초기화)
- [PostgreSQL vs MySQL](../2-데이터/03-PostgreSQL-vs-MySQL.md): MySQL과 PostgreSQL 비교, 데이터 옮기기
