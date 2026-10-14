# 71. 이 프로젝트의 CI/CD: 지금 설정 읽기와 고치는 순서

> 관련 스텝: [스텝 24](../step-24.md) (배포) · 관련 개념: [69-ci-cd-concepts](./69-ci-cd-concepts.md)(개념), [70-ci-cd-setup-methods](./70-ci-cd-setup-methods.md)(설정 방법 여러 가지), [68-server-docker-dev-prod](./68-server-docker-dev-prod.md)(서버와 Docker), [03-flyway-migration](./03-flyway-migration.md)

> **한 줄 답**: 지금 now-log는 "main에 병합 → 테스트 → 이미지를 파일로 만들어 서버에 복사 → 서버에서 `deploy.sh`로 다시 띄우기"까지 이미 자동이다. 부족한 것은 **PR 단계의 검사, 비밀번호 대신 배포 키, 이미지 버전(SHA 태그)과 되돌리기** 세 가지다. 이 순서대로 하나씩 PR로 고치면 [70](./70-ci-cd-setup-methods.md)의 방법 A + B 모양이 된다.

이 문서는 2026-10-14의 now-log `main`(`.github/workflows/deploy.yml`, `deploy/deploy.sh`, `Dockerfile`)을 기준으로 썼다. 5장의 설정은 **제안**이고 아직 저장소에 들어가지 않았다.

## 1. 이 문서로 배우는 것

- 지금 `deploy.yml`을 한 줄씩 읽기: 트리거, 잡, 비밀값이 서버까지 가는 길
- `deploy.sh`와 `Dockerfile`이 파이프라인에서 맡는 일
- 지금 설정의 잘된 점과 빈 곳
- 고치는 순서 일곱 단계와 각 단계의 파일·확인 방법
- 되돌리기와 Flyway 마이그레이션을 함께 생각하기

## 2. 왜 필요한가

지금 배포는 잘 돌아가고 있다. 그런데 이런 일이 생기면 막힌다.

- PR에서 테스트가 깨졌는지 모른 채 병합 → main에서 처음 빨간 X를 보고, 그동안 배포는 멈춘다
- 새 버전이 서버에서 안 뜬다 → 옛 이미지는 이미 지워졌고(`docker rmi`), 다시 만들려면 옛 커밋으로 되돌리는 PR을 올리고 테스트·빌드를 처음부터 기다려야 한다
- 학교 서버 비밀번호를 바꾸거나 계정이 털린다 → GitHub Secrets의 `SSH_PASSWORD`는 서버의 모든 일을 할 수 있는 비밀번호라 범위를 좁힐 수 없다

이 셋을 미리 막아 두는 것이 이 문서의 목표다.

## 3. 기본 개념: 지금 설정 읽기

### 3.1 저장소가 둘이다

| 저장소 | 역할 | 워크플로에서 도는 것 |
| --- | --- | --- |
| `blog-hjiwon203/now-log` | 본 저장소. 여기서 배포한다 | test + deploy |
| `AIP-1/blog-basic-AIGJ_01_017-blog` | 과제 제출용 사본 | test만 (`if: github.repository == ...`로 deploy를 막음) |

같은 워크플로 파일이 두 저장소에 다 있어도, deploy 잡의 `if`가 저장소 이름을 확인해 본 저장소에서만 서버를 건드린다. 포크한 사람이 실수로 배포를 시도하는 것도 같은 줄이 막는다.

### 3.2 `deploy.yml` 읽기

| 부분 | 내용 | 뜻 |
| --- | --- | --- |
| `on: push: branches: [main]` | main에 커밋이 들어오면(=PR 병합) | 지속적 배포. 병합 버튼이 곧 운영 배포 버튼 |
| `on: workflow_dispatch` | Actions 탭의 Run workflow 버튼 | 코드 변경 없이 다시 배포(비밀값을 바꾼 뒤 등) |
| `concurrency: group: deploy`, `cancel-in-progress: false` | 같은 그룹은 하나씩, 앞 것을 취소하지 않음 | 두 번 연달아 병합해도 배포가 겹치지 않고 차례로 |
| 잡 `test` | checkout → JDK 21(temurin, Maven 캐시) → `./mvnw -B test` | Testcontainers가 러너의 docker로 PostgreSQL·Redis를 띄워 테스트 |
| 잡 `deploy`의 `needs: test` | test가 성공해야 시작 | 테스트를 건너뛴 배포는 불가능 |
| `docker build` + `docker save \| gzip` | 이미지 `aigj017/now-log:latest`를 만들어 tar.gz 파일로 | 레지스트리를 쓰지 않고 파일로 건넴 |
| `appleboy/scp-action` | tar.gz, `deploy.sh`, `migrate-from-mysql.sh`를 서버 `~/now-log`로 복사 | 접속은 `SSH_ADDRESS`·`SSH_PORT`·`SSH_ID`·`SSH_PASSWORD` |
| `appleboy/ssh-action`의 `env` + `envs` | 비밀값 9개를 러너 환경 변수로 만들고, `envs`에 적힌 이름만 ssh 너머로 넘김 | 서버 셸에서 `$JWT_SECRET` 등으로 보인다 |
| `command_timeout: 10m`, `script: bash ~/now-log/deploy/deploy.sh` | 서버에서 스크립트 실행, 10분 넘으면 실패 | 처음 배포 때 Ollama 모델 내려받기가 길어서 넉넉히 |

### 3.3 `deploy.sh`가 하는 일

```
필수 환경 변수 확인 (RECOMMEND_DB_PASSWORD, REDIS_PASSWORD, JWT_SECRET)
  → 지금 이미지 ID 기억(old_image) → tar.gz를 docker load → 파일 삭제
  → docker 네트워크 aigj017-net 없으면 만들기
  → Redis: 매번 지우고 다시 띄움(비밀번호가 바뀌었을 수 있어서, 데이터는 볼륨에)
  → PostgreSQL·Ollama: 떠 있지 않을 때만 띄움(데이터 볼륨, 모델 1.2GB)
  → DB 계정 비밀번호를 secret 값으로 다시 맞춤, blog DB 없으면 만듦
  → bge-m3 모델 pull(이미 있으면 바로 끝)
  → 앱 컨테이너 지우고 새로 띄움(-e 이름만 넘겨 비밀값이 명령줄에 안 보이게)
  → 로그에 "Started BlogApplication"이 나올 때까지 최대 3분
       ├ 뜸 → 옛 이미지 삭제(docker rmi old_image), 성공
       └ 컨테이너가 멈췄거나 3분 넘음 → 로그 80줄 출력, 실패(exit 1)
```

### 3.4 `Dockerfile`이 하는 일

세 단계 빌드다. 그래서 **프론트엔드 빌드 오류도 deploy 잡의 `docker build`에서야 드러난다**(test 잡은 백엔드 테스트만 한다).

1. `node:24-alpine`: `npm ci`, `npm run build`
2. `eclipse-temurin:21-jdk`: 의존성 내려받기 → 1의 결과를 `static`에 복사 → `package -DskipTests`(테스트는 test 잡에서 이미 했으니 건너뜀)
3. `eclipse-temurin:21-jre`: jar만 담은 작은 실행 이미지, `prod` 프로필, 한국 시간

### 3.5 잘된 점

- 테스트를 통과해야만 배포된다(`needs: test`)
- 배포가 겹치지 않는다(`concurrency`)
- 비밀값이 저장소에 없고, 서버 명령줄(`ps`)에도 안 보인다(`-e 이름`, psql 변수)
- 서버에서 할 일이 스크립트 하나에 있어 읽고 고치기 쉽다
- 앱이 안 뜨면 잡이 빨갛게 끝나고 로그가 Actions 화면에 남는다
- 공용 서버를 배려한다(`aigj017-` 이름, `docker image prune` 안 씀, Ollama CPU·메모리 제한)

### 3.6 빈 곳

| 빈 곳 | 생기는 일 | 고치는 단계 |
| --- | --- | --- |
| PR에서 아무 검사도 안 돔 | 깨진 코드가 병합된 뒤에 안다. 필수 검사 지정 불가 | 1, 2 |
| 프론트엔드 빌드를 배포 때만 함 | 화면 코드 오류가 운영 배포 직전에 드러난다 | 1 |
| SSH 비밀번호로 접속, 서버 지문 확인 없음 | 비밀번호 하나로 서버 전부. 중간자 공격을 못 알아챔 | 3 |
| 비밀값이 저장소 전체 범위(Repository secrets) | 어느 워크플로든 운영 비밀값을 읽을 수 있다 | 4 |
| 이미지 태그가 `latest` 하나, 성공하면 옛 이미지 삭제 | 무엇이 떠 있는지 모르고, 되돌릴 이미지가 없다 | 5 |
| 이미지를 매번 통째로 scp(수백 MB) | 느리고, 바뀌지 않은 레이어도 다시 보낸다 | 5 |
| 실패하면 멈춰 있을 뿐 되돌리지 않음 | 새 버전이 안 뜨면 블로그가 내려간 채로 남는다 | 5 |
| "떴다"의 기준이 로그 한 줄 | Redis·Ollama 연결 문제는 못 잡는다 | 6 |

## 4. 동작 원리: 비밀값이 서버까지 가는 길

```
GitHub Repository secrets (암호화 저장)
   │  워크플로 실행 때만 꺼내짐, 로그에는 *** 로 가려짐
   ▼
러너의 환경 변수 (ssh-action의 env:)
   │  envs: 에 적힌 이름만, ssh 연결 안에서
   ▼
서버의 deploy.sh 셸 환경 변수 ($JWT_SECRET ...)
   │  docker run -e JWT_SECRET  (값 없이 이름만 → 명령줄·ps에 안 보임)
   ▼
앱 컨테이너 환경 변수 → application-prod.yml의 ${JWT_SECRET}
   (주의: 서버에서 docker inspect aigj017-app 하면 보인다. docker 권한 = 비밀값 열람 권한)
```

개선 4단계(production 환경)는 맨 위 칸을 "Repository secrets"에서 "production 환경의 secrets"로 좁히는 일이고, 개선 3단계(배포 키)는 두 번째 화살표의 ssh 접속을 비밀번호에서 키로 바꾸는 일이다.

## 5. 이 프로젝트에서는: 고치는 순서

한 단계 = PR 하나로 한다. 각 단계가 끝나면 Actions 탭에서 실제로 돌아간 것을 확인하고 다음으로 간다.

### 1단계. PR에서 테스트와 프론트 빌드 돌리기

**파일 추가**: `.github/workflows/ci.yml`

```yaml
# PR마다 백엔드 테스트와 프론트 빌드. 배포는 하지 않는다(배포는 deploy.yml)
name: ci

on:
  pull_request:

permissions:
  contents: read

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  backend:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-java@v5
        with:
          distribution: temurin
          java-version: '21'
          cache: maven
      - run: ./mvnw -B test

  frontend:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-node@v5
        with:
          node-version: '24'          # Dockerfile의 node:24와 맞춘다
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - run: npm ci
      - run: npm run build
```

`deploy.yml`의 `test` 잡은 그대로 둔다(main에서 한 번 더 확인하는 안전장치).

**확인**: 이 PR 자체에서 `ci / backend`, `ci / frontend`가 초록으로 뜨는지 PR의 Checks 탭에서 본다.

### 2단계. main 브랜치 보호

now-log 저장소 Settings → Rules → Rulesets → New branch ruleset (또는 Settings → Branches → Add rule)

- Target: `main`
- Require a pull request before merging
- Require status checks to pass → `backend`, `frontend` 추가(1단계 PR에서 한 번 돌아야 목록에 뜬다)
- Block force pushes

혼자 하는 프로젝트라 승인 수(Required approvals)는 0으로 두어도 된다. 핵심은 **빨간 PR이 병합되지 않게** 하는 것이다. Claude가 만든 PR도 이 규칙을 똑같이 따른다.

**확인**: 테스트 하나를 일부러 깨뜨린 PR을 올려 병합 버튼이 막히는지 보고, PR은 닫는다.

### 3단계. SSH 비밀번호 대신 배포 전용 키

```bash
# 노트북에서
ssh-keygen -t ed25519 -C "now-log-deploy" -f ./now-log-deploy -N ""

# 공개 키를 학교 서버 내 계정에 등록 (비밀번호로 한 번 접속)
ssh-copy-id -i ./now-log-deploy.pub -p <SSH_PORT> <SSH_ID>@s2.java21.net

# 키로 접속되는지 확인
ssh -i ./now-log-deploy -p <SSH_PORT> <SSH_ID>@s2.java21.net 'echo ok'

# 서버 지문(SHA256:...) 확인. appleboy 액션의 fingerprint에 넣는다
ssh-keyscan -p <SSH_PORT> s2.java21.net 2>/dev/null | ssh-keygen -lf -
```

학교 서버가 키 접속을 막아 두었다면 여기서 `echo ok`가 안 된다. 그때는 이 단계를 건너뛰고 서버 관리자에게 묻는다.

**GitHub Secrets**: `SSH_KEY`(now-log-deploy 파일 내용 전체), `SSH_FINGERPRINT`(ed25519 줄의 `SHA256:...`)를 추가한다.

**`deploy.yml` 수정**: scp-action과 ssh-action 둘 다

```yaml
          host: ${{ secrets.SSH_ADDRESS }}
          port: ${{ secrets.SSH_PORT }}
          username: ${{ secrets.SSH_ID }}
          key: ${{ secrets.SSH_KEY }}                 # password 대신
          fingerprint: ${{ secrets.SSH_FINGERPRINT }} # 진짜 그 서버인지 확인
```

**확인**: main에 병합된 배포가 초록이면 `SSH_PASSWORD` secret을 지운다. 노트북의 `now-log-deploy` 개인 키 파일도 지운다(GitHub에만 있으면 된다. 잃어버리면 새로 만들면 된다).

### 4단계. 운영 비밀값을 production 환경으로

Settings → Environments → New environment `production`

- Deployment branches and tags: Selected → `main`
- Environment secrets: 지금 Repository secrets에 있는 배포용 값들(SSH_*, RECOMMEND_DB_PASSWORD, REDIS_PASSWORD, JWT_SECRET, KAKAO_*, GOOGLE_*, MAIL_*)을 같은 이름으로 옮긴다
- (선택) Required reviewers에 나를 넣으면 배포 전에 승인 버튼을 눌러야 한다. 공개 저장소라 무료로 쓸 수 있다. 지속적 배포를 지속적 전달로 바꾸는 스위치다

**`deploy.yml` 수정**: deploy 잡에 두 줄

```yaml
  deploy:
    needs: test
    if: github.repository == 'blog-hjiwon203/now-log'
    runs-on: ubuntu-latest
    environment:
      name: production
      url: https://now-log.java21.net
```

**확인**: 배포가 초록이고, 저장소 첫 화면 오른쪽 "Deployments"에 production이 생겼는지 본다. 그 뒤 Repository secrets의 같은 값들을 지운다(Environment secrets가 같은 이름이면 그쪽이 우선이지만, 남겨 두면 범위를 좁힌 의미가 없다).

### 5단계. 이미지를 SHA 태그로, GHCR에 올리고, 실패하면 되돌리기

가장 큰 변경이다. 먼저 **서버가 GHCR에 닿는지** 확인한다.

```bash
# 학교 서버에서. 401이 나오면 닿는 것이다(로그인 안 해서 401, 연결은 됨)
curl -s -o /dev/null -w '%{http_code}\n' https://ghcr.io/v2/
```

#### 5-A. 닿으면: GHCR (권장)

저장소가 공개이므로 패키지도 공개로 두면 서버에서 로그인 없이 받을 수 있다. 처음 push한 뒤 GitHub 프로필 → Packages → now-log → Package settings → Change visibility → Public.

**`deploy.yml`의 deploy 잡을 build와 deploy 둘로 나눈다**

```yaml
env:
  IMAGE: ghcr.io/blog-hjiwon203/now-log

jobs:
  test:
    # (지금 그대로)

  build:
    needs: test
    if: github.repository == 'blog-hjiwon203/now-log'
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v5
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: |
            ${{ env.IMAGE }}:${{ github.sha }}
            ${{ env.IMAGE }}:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: production
      url: https://now-log.java21.net
    steps:
      - uses: actions/checkout@v5
      - name: 서버로 스크립트 보내기
        uses: appleboy/scp-action@v1
        with:
          host: ${{ secrets.SSH_ADDRESS }}
          port: ${{ secrets.SSH_PORT }}
          username: ${{ secrets.SSH_ID }}
          key: ${{ secrets.SSH_KEY }}
          fingerprint: ${{ secrets.SSH_FINGERPRINT }}
          source: deploy/deploy.sh,deploy/migrate-from-mysql.sh   # tar.gz는 이제 안 보냄
          target: now-log
      - name: 서버에서 실행
        uses: appleboy/ssh-action@v1
        env:
          IMAGE_TAG: ${{ github.sha }}
          RECOMMEND_DB_PASSWORD: ${{ secrets.RECOMMEND_DB_PASSWORD }}
          # ... (나머지 비밀값 지금 그대로)
        with:
          host: ${{ secrets.SSH_ADDRESS }}
          port: ${{ secrets.SSH_PORT }}
          username: ${{ secrets.SSH_ID }}
          key: ${{ secrets.SSH_KEY }}
          fingerprint: ${{ secrets.SSH_FINGERPRINT }}
          envs: IMAGE_TAG,RECOMMEND_DB_PASSWORD,REDIS_PASSWORD,JWT_SECRET,KAKAO_CLIENT_ID,KAKAO_CLIENT_SECRET,GOOGLE_CLIENT_ID,GOOGLE_CLIENT_SECRET,MAIL_USERNAME,MAIL_PASSWORD
          command_timeout: 10m
          script: bash ~/now-log/deploy/deploy.sh
```

**`deploy.sh` 수정**: 바뀌는 곳만

```bash
IMAGE_REPO=ghcr.io/blog-hjiwon203/now-log
IMAGE="$IMAGE_REPO:${IMAGE_TAG:?IMAGE_TAG가 비어 있습니다}"

echo "== 이미지 받기"
docker pull "$IMAGE"
# 지금 떠 있는 앱의 이미지(되돌리기용). 처음 배포면 비어 있다
prev_image="$(docker inspect --format '{{.Config.Image}}' "$APP" 2>/dev/null || true)"
```

앱을 띄우는 `docker run`과 "뜰 때까지 기다림" 부분을 함수 두 개로 묶는다.

```bash
start_app() {   # $1 = 띄울 이미지
  docker rm -f "$APP" >/dev/null 2>&1 || true
  DB_PASSWORD="$RECOMMEND_DB_PASSWORD" docker run -d --name "$APP" ... "$1" >/dev/null   # 옵션은 지금 그대로
}

wait_app() {    # 뜨면 0, 못 뜨면 1
  for _ in $(seq 1 90); do
    if [ "$(docker inspect --format '{{.State.Running}}' "$APP")" != "true" ]; then
      return 1
    fi
    if docker logs "$APP" 2>&1 | grep -q "Started BlogApplication"; then
      return 0
    fi
    sleep 2
  done
  return 1
}

start_app "$IMAGE"
if wait_app; then
  echo "배포 완료($IMAGE_TAG): https://now-log.java21.net"
  # 이 저장소 이미지 중 최근 3개만 남긴다(되돌리기용). 다른 학생 이미지는 건드리지 않는다
  docker images "$IMAGE_REPO" --format '{{.Repository}}:{{.Tag}}' | tail -n +4 | xargs -r docker rmi >/dev/null 2>&1 || true
  exit 0
fi

echo "새 버전이 뜨지 않았습니다. 마지막 로그:" >&2
docker logs --tail 80 "$APP" >&2 || true
if [ -n "$prev_image" ] && [ "$prev_image" != "$IMAGE" ]; then
  echo "직전 이미지로 되돌립니다: $prev_image" >&2
  start_app "$prev_image"
  if wait_app; then echo "되돌리기 완료" >&2; else echo "되돌린 버전도 뜨지 않습니다" >&2; fi
fi
exit 1   # 되돌렸어도 이번 배포는 실패로 표시
```

처음 이 방식으로 배포할 때는 서버에 떠 있는 앱의 이미지가 옛 이름 `aigj017/now-log:latest`라서 `prev_image`가 그 이름이 된다. 이것도 되돌리기 대상으로 잘 동작한다. 새 방식이 두세 번 성공하면 `docker rmi aigj017/now-log:latest`로 옛 이미지를 정리한다.

**손으로 되돌리기**도 쉬워진다. 서버에서

```bash
# Actions 화면이나 git log에서 잘 돌던 커밋 SHA를 찾아서
IMAGE_TAG=<그 SHA> RECOMMEND_DB_PASSWORD=... bash ~/now-log/deploy/deploy.sh
```

를 해도 되고, [70](./70-ci-cd-setup-methods.md) 4.2처럼 `workflow_dispatch`에 `tag` 입력을 받게 하면 버튼으로 할 수 있다.

#### 5-B. 닿지 않으면: 파일 복사는 그대로, 태그만 SHA로

`docker build -t aigj017/now-log:${{ github.sha }}`로 만들고, `docker save`도 그 태그로 한다. `deploy.sh`는 5-A와 같게 고치되 `docker pull` 대신 지금처럼 `docker load`, `IMAGE_REPO=aigj017/now-log`로 둔다. 매번 통째로 보내는 느림은 남지만, **최근 3개 이미지가 서버에 남아 되돌리기는 된다.**

### 6단계. (선택) 헬스 체크를 Actuator로

지금 기준인 "로그에 `Started BlogApplication`"은 Flyway·DB 연결까지는 확인해 준다(이게 실패하면 그 줄이 안 나온다). Redis·Ollama 연결과 "요청을 실제로 받는지"까지 보려면 Spring Boot Actuator를 쓴다.

1. `pom.xml`에 `spring-boot-starter-actuator`
2. `application.yml`
   ```yaml
   management:
     endpoints:
       web:
         exposure:
           include: health          # health만 연다
     endpoint:
       health:
         show-details: never        # 바깥에는 UP/DOWN만
   ```
3. Spring Security 설정에서 `/actuator/health`를 로그인 없이 열기(`permitAll`)
4. `wait_app`의 로그 확인을 `curl -fsS http://localhost:8460/actuator/health | grep -q '"status":"UP"'`로 바꾸기

Ollama 같은 외부 API가 잠깐 느릴 때도 DOWN이 되면 배포가 괜히 되돌려질 수 있으니, 어떤 구성 요소를 헬스 체크에 넣을지(`management.health.<이름>.enabled`)는 정하고 넣는다.

### 7단계. 작은 정리

| 할 일 | 방법 | 효과 |
| --- | --- | --- |
| 문서만 바뀌면 배포 안 함 | `push`에 `paths-ignore: ['**.md']` | 쓸데없는 재시작이 줄어듦 |
| GITHUB_TOKEN 권한 줄이기 | 파일 맨 위 `permissions: contents: read`, 필요한 잡만 더 | 워크플로가 털려도 할 수 있는 일이 적음 |
| 잡 시간 제한 | `timeout-minutes: 20`(test), `30`(deploy) | 멈춘 잡이 6시간(기본값) 붙잡지 않음 |
| Action 버전 자동 갱신 | `.github/dependabot.yml`에 `github-actions` | 오래된 Action의 보안 문제를 PR로 알려 줌 |

### 적용 순서 한눈에

```
1 PR CI ─→ 2 브랜치 보호 ─→ 3 배포 키 ─→ 4 production 환경 ─→ 5 SHA 태그·GHCR·되돌리기 ─→ 6 Actuator ─→ 7 정리
 (파일 1개)   (설정 화면)      (secret 2개)    (설정 화면 + 2줄)     (deploy.yml·deploy.sh)        (선택)
```

1~4는 각각 작고 독립적이라 하루에 끝낼 수 있다. 5는 배포 방식이 바뀌므로 따로 시간을 잡고, 병합 직후 Actions 로그와 블로그 화면을 함께 본다.

### 되돌리기와 Flyway

5단계로 이미지는 되돌릴 수 있게 되지만 **DB는 되돌아가지 않는다.** 되돌린 옛 앱이 새 DB와 맞는지는 이렇게 판단한다.

| 새 버전의 마이그레이션 | 옛 이미지로 되돌리면 |
| --- | --- |
| 표·컬럼 **추가**만 | 대체로 괜찮다. `ddl-auto: validate`는 엔티티에 없는 컬럼이 DB에 더 있는 것은 문제 삼지 않는다. Flyway도 기본 설정에서 "앱이 모르는 더 새 버전"(future)은 무시한다. 단, 새 컬럼이 `NOT NULL`이고 기본값이 없으면 옛 앱의 INSERT가 실패한다 |
| 컬럼 **삭제·이름 변경**, 타입 변경 | 옛 앱이 시작 때 `validate`에서 실패한다. 되돌리기가 안 된다 |

그래서 컬럼 삭제·이름 변경은 [69](./69-ci-cd-concepts.md) 3.9의 **늘리기 → 옮기기 → 줄이기**로 나눠 배포한다. 새 컬럼은 처음에 NULL 허용(또는 기본값)으로 추가하는 [03](./03-flyway-migration.md)의 순서가 그대로 되돌리기 안전장치가 된다.

## 6. 자주 하는 실수와 함정

| 실수 | 왜 문제인가 | 이렇게 |
| --- | --- | --- |
| 브랜치 보호에서 필수 검사를 `test`(deploy.yml)로 지정 | 그 잡은 PR에서 돌지 않아 목록에 없거나, 지정하면 PR이 영원히 "대기 중" | 1단계의 `backend`, `frontend`를 지정 |
| 환경 secrets로 옮기고 deploy 잡에 `environment:`를 안 붙임 | 잡이 환경 secrets를 못 읽어 `RECOMMEND_DB_PASSWORD 이 비어 있습니다`로 실패 | `environment: production` |
| 배포 키를 만들고 `SSH_PASSWORD`부터 지움 | 키 접속이 안 되면 배포가 멈춘다 | 키로 배포가 한 번 성공한 뒤 지움 |
| GHCR 패키지를 비공개로 둔 채 서버에서 pull | `unauthorized` | 공개로 바꾸거나 서버에서 `read:packages` 토큰으로 로그인 |
| `deploy.sh`에서 `docker image prune -a` | 공용 서버의 다른 학생 이미지까지 지운다 | 내 이미지 저장소 이름으로 골라 지움 |
| 되돌렸는데 잡이 초록 | 사람이 실패를 모르고 넘어간다 | 되돌린 뒤에도 `exit 1` |
| 컬럼 이름 바꾸는 마이그레이션과 코드를 한 PR에 | 배포 실패 시 되돌릴 수 없다 | 늘리기 → 옮기기 → 줄이기 |
| AIP-1 사본 저장소에 같은 변경을 안 함 | 제출 사본만 옛 방식으로 남음(배포는 안 하니 위험은 적다) | 제출 시점에 사본을 now-log에서 다시 맞춤 |

## 7. 직접 해 보기

1. now-log Actions 탭에서 가장 최근 `deploy` 실행을 열어 3.2 표의 각 줄이 어느 스텝에 해당하는지 짝지어 본다. "서버에서 실행" 스텝 로그 끝의 `배포 완료` 줄을 찾는다.
2. 학교 서버에서 `docker images aigj017/now-log`를 쳐서 이미지가 몇 개 남아 있는지 본다(지금은 1개일 것이다. 5단계 뒤에는 최대 3개).
3. 1단계 `ci.yml`을 PR로 올려 Checks 탭에 두 잡이 뜨는 것을 본다. 이어서 2단계 브랜치 보호를 켠다.
4. 3단계의 `ssh-keyscan ... | ssh-keygen -lf -`로 서버 지문을 확인하고, 처음 ssh로 접속할 때 나왔던 지문과 같은지 비교한다.

## 8. 확인 문제

1. 지금 설정에서 프론트엔드에 문법 오류가 있는 PR을 병합하면 어디서, 언제 알게 되나? 1단계 뒤에는?
<details><summary>답</summary>지금은 main 병합 뒤 deploy 잡의 `docker build`(Dockerfile 1단계 `npm run build`)에서 처음 실패한다. 이미 main에 들어간 뒤다. 1단계 뒤에는 PR의 `ci / frontend`에서 실패해 병합 전에 안다(2단계를 하면 병합도 막힌다).</details>

2. `ssh-action`의 `env:`에 `JWT_SECRET`을 넣었는데 `envs:`에 적는 것을 빼먹었다. 무슨 일이 생기나?
<details><summary>답</summary>러너에는 값이 있지만 ssh 너머 서버 셸로 넘어가지 않아, `deploy.sh`의 필수 값 확인에서 "JWT_SECRET 이 비어 있습니다"로 실패한다.</details>

3. 5단계 뒤, 새 버전이 Redis 비밀번호 오류로 뜨지 않았다. `deploy.sh`는 무엇을 하고 Actions 화면은 무슨 색이 되나?
<details><summary>답</summary>`wait_app`이 실패하면 로그 80줄을 찍고, 직전 이미지(`prev_image`)로 앱을 다시 띄워 뜨는지 확인한 뒤 `exit 1`로 끝낸다. 블로그는 옛 버전으로 계속 돌고, Actions는 빨갛게 표시된다.</details>

4. 새 버전에서 `post.summary` 컬럼을 추가(NULL 허용)했다가 배포가 실패해 옛 이미지로 되돌렸다. 옛 앱은 뜨나?
<details><summary>답</summary>뜬다. 옛 엔티티에 없는 컬럼이 DB에 더 있는 것은 `ddl-auto: validate`가 문제 삼지 않고, NULL 허용이라 옛 앱의 INSERT도 된다. Flyway는 옛 앱이 모르는 새 버전 기록을 기본으로 무시한다.</details>

5. 4단계에서 Required reviewers를 켜면 이 프로젝트의 CD는 69의 두 가지 뜻 중 무엇이 되나?
<details><summary>답</summary>지속적 전달(Continuous Delivery). 운영 배포 직전에 사람이 승인 버튼을 눌러야 나가기 때문이다.</details>

## 9. 더 읽을거리

- now-log 저장소: `.github/workflows/deploy.yml`, `deploy/deploy.sh`, `Dockerfile`(주석에 이유가 적혀 있다)
- [68 서버와 Docker](./68-server-docker-dev-prod.md): 어느 컨테이너가 어느 컴퓨터에 있는지
- appleboy/ssh-action, appleboy/scp-action README: `key`, `fingerprint`, `envs`
- GitHub Docs: "Managing rulesets for a repository", "Managing environments for deployment", "Working with the Container registry"(패키지 공개 설정)
- Spring Boot 문서: "Actuator: Endpoints"(health, exposure, show-details)
- Flyway 문서: `ignoreMigrationPatterns`(future 마이그레이션 무시 기본값)
