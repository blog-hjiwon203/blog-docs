# 04. Docker와 Docker Compose

> 관련 스텝: [스텝 1](../step-01.md) · 함께 읽을 것: [03. Flyway](./03-flyway-migration.md), [05. 테스트](./05-spring-testing.md)(Testcontainers)

## 1. 이 문서로 배우는 것

- **이미지**와 **컨테이너**가 무엇이고 가상머신과 무엇이 다른지
- `docker-compose.yml`의 항목(`image`, `environment`, `command`, `ports`, `volumes`, `healthcheck`)이 하는 일
- 컨테이너를 지워도 **데이터가 남는 원리**(볼륨)
- 포트 충돌을 알아보고 해결하는 방법(스텝 1의 로컬 Redis 사건)
- 자주 쓰는 명령과 `down`과 `down -v`의 차이

**먼저 알면 좋은 것**: 터미널 기본 명령, "포트"가 무엇인지(한 컴퓨터에서 여러 프로그램이 네트워크를 나눠 쓰는 번호).

---

## 2. 왜 필요한가

블로그 서버를 띄우려면 MySQL 8과 Redis가 필요하다. 직접 설치한다면:

- macOS에 MySQL을 설치하고, 계정과 DB를 만들고, 문자셋을 utf8mb4로 바꾸고, 시간대를 맞춘다.
- 팀원 PC가 Windows면 설치 방법이 다르다. 누구는 MySQL 8.0, 누구는 8.4라 동작이 미묘하게 다르다.
- 다른 프로젝트가 MySQL 5.7을 요구하면 둘을 한 컴퓨터에 깔기 어렵다.
- 다 쓰고 지우려면 흔적이 여기저기 남는다.

Docker는 **"MySQL 8.4가 설치되고 설정된 상태"를 통째로 묶은 이미지**를 내려받아 격리된 상자(컨테이너)로 띄운다. Docker Compose는 그런 컨테이너 여러 개(MySQL + Redis)를 **파일 하나로 정의하고 명령 하나로** 띄운다. 누가 실행해도 같은 환경이 나온다.

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

`"13306:3306"`으로 쓰면 내 PC에서는 13306으로 접속한다. 같은 호스트 포트를 두 프로그램이 동시에 쓸 수는 없다(3.5 포트 충돌).

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

---

## 4. 동작 원리: `docker compose up -d`가 하는 일

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

---

## 5. 이 프로젝트에서는

`docker-compose.yml` (저장소 루트)

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

**스프링과 연결되는 곳**: `application-dev.yml`의 `jdbc:mysql://localhost:3306/blog`, `username: blog`, `redis.host: localhost`, `port: 6379`가 위 값과 짝이다([02](./02-configuration-profiles.md)).

**테스트와의 관계**: 테스트는 이 compose를 쓰지 않는다. Testcontainers가 **같은 이미지**(`mysql:8.4`, `redis:7.4`)로 테스트용 컨테이너를 새로 띄우고, 빈 포트를 골라 연결한다([05](./05-spring-testing.md)). 그래서 테스트 중 `docker ps`를 보면 컨테이너가 더 보인다. 같은 이미지를 써야 개발에서 되는 것이 테스트에서도 된다.

### 5.1 스텝 1의 포트 충돌 사건

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

### 5.2 다른 프로세스를 끌 때의 주의

스텝 2에서 8080 포트를 다른 서버가 쓰고 있었는데, 정리하면서 `pkill -f com.nhnacademy.blog.BlogApplication`을 실행했다. 이 명령은 이름이 맞는 **모든** 프로세스를 끄기 때문에 IntelliJ에서 띄운 서버까지 꺼졌을 수 있다. 포트를 쓰는 프로세스를 정확히 끄려면 PID를 확인하고 그 PID만 끈다.

```bash
lsof -tiTCP:8080 -sTCP:LISTEN     # PID만 출력
kill <PID>
```

---

## 6. 자주 하는 실수와 함정

| 실수 | 증상 | 해결 |
| --- | --- | --- |
| Docker Desktop/OrbStack을 안 켬 | `Cannot connect to the Docker daemon` | 앱을 켠다(하나만) |
| 호스트 포트가 이미 사용 중 | `port is already allocated` | `lsof -iTCP:포트 -sTCP:LISTEN -P`로 범인을 찾아 끄거나 포트를 바꾼다 |
| 볼륨이 있는 채로 `MYSQL_PASSWORD`를 바꿈 | 새 비밀번호로 접속 실패 | 환경 변수는 첫 초기화 때만 쓰인다. 데이터를 버려도 되면 `down -v` 후 `up -d` |
| `down -v`를 습관처럼 씀 | 개발 DB 데이터가 몽땅 사라짐 | 평소엔 `down` 또는 `stop`. `-v`는 초기화가 목적일 때만 |
| `image: mysql` (태그 없음) | `latest`를 받아 어느 날 버전이 바뀜 | 태그를 정확히(`mysql:8.4`) |
| healthy 전에 앱을 띄움 | 첫 연결 실패 | `docker compose ps`에서 healthy 확인 후 |
| compose 파일이 없는 폴더에서 명령 | `no configuration file provided` | 저장소 루트에서 실행 |
| 마이그레이션 실패로 DB가 반쯤 만들어짐 | 다시 시작해도 Flyway 오류 | 개발 DB는 `down -v`로 초기화([03](./03-flyway-migration.md) 4.2) |

---

## 7. 직접 해 보기

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

---

## 8. 확인 문제

1. 이미지와 컨테이너의 관계를 클래스와 객체에 비유해 설명하라.
   <details><summary>답</summary>이미지는 읽기 전용 설계도(클래스), 컨테이너는 그 이미지로 만든 실행 중인 인스턴스(객체)다. 같은 이미지로 여러 컨테이너를 만들 수 있다.</details>

2. `docker compose down`과 `docker compose down -v`의 차이는?
   <details><summary>답</summary>둘 다 컨테이너와 네트워크를 지우지만, `-v`는 볼륨까지 지워 DB 데이터가 사라진다.</details>

3. `ports: - "3306:3306"`에서 앞과 뒤 숫자는 각각 무엇인가?
   <details><summary>답</summary>앞은 호스트(내 PC) 포트, 뒤는 컨테이너 안 포트다.</details>

4. 볼륨이 있는 상태에서 `MYSQL_PASSWORD`를 `blog2`로 바꾸고 `up -d` 했더니 `blog2`로 접속이 안 된다. 왜인가?
   <details><summary>답</summary>MySQL 이미지는 데이터 폴더가 비어 있을 때(최초 초기화)만 환경 변수로 계정을 만든다. 볼륨에 기존 데이터가 있으니 이전 비밀번호가 그대로다.</details>

5. Redis에는 볼륨을 두지 않았다. 왜 괜찮은가?
   <details><summary>답</summary>이 프로젝트에서 Redis에는 캐시, 토큰 상태, 연타 방지 키처럼 사라져도 다시 만들어지거나 짧게만 필요한 값만 두기 때문이다. 원본 데이터는 MySQL에 있다. (개발 중 Redis를 재시작하면 로그인 상태가 풀리는 정도의 영향이 있다.)</details>

6. healthcheck가 없으면 어떤 문제가 생길 수 있나?
   <details><summary>답</summary>컨테이너가 떴지만 MySQL이 아직 초기화 중일 때 앱이 접속을 시도해 실패할 수 있다. 준비됐는지 알 방법이 없다.</details>

7. 테스트는 compose의 MySQL 대신 무엇을 쓰고, 왜 같은 이미지 태그를 쓰는가?
   <details><summary>답</summary>Testcontainers가 띄우는 새 컨테이너를 쓴다. 개발과 테스트가 같은 MySQL 버전이어야 한쪽에서만 되는 문제를 막을 수 있다.</details>

---

## 9. 더 읽을거리

- Docker 공식 문서 "Get started", "Docker overview" (https://docs.docker.com/get-started/)
- Docker 공식 문서 "Compose file reference" — `services`, `ports`, `volumes`, `healthcheck` (https://docs.docker.com/reference/compose-file/)
- Docker 공식 문서 "Volumes" (https://docs.docker.com/engine/storage/volumes/)
- Docker Hub의 `mysql` 공식 이미지 설명 — 환경 변수와 초기화 규칙 (https://hub.docker.com/_/mysql)
- Docker Hub의 `redis` 공식 이미지 설명 (https://hub.docker.com/_/redis)
