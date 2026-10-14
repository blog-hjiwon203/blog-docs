# 70. CI/CD 설정 방법 여러 가지: GitHub Actions, Jenkins, GitLab CI, 클라우드, GitOps

> 관련 스텝: [스텝 24](../step-24.md) (배포) · 관련 개념: [69-ci-cd-concepts](./69-ci-cd-concepts.md)(개념), [71-ci-cd-this-project](./71-ci-cd-this-project.md)(이 프로젝트에 적용), [04-docker-compose](./04-docker-compose.md)

> **한 줄 답**: 실무에서 많이 쓰는 방식은 일곱 가지쯤으로 정리된다. 서버 한두 대에 Docker로 띄운다면 **GitHub Actions(CI) + 레지스트리에 이미지 올리기 + SSH로 서버에서 받아 교체**가 가장 흔하고, 회사 안 서버만 있으면 Jenkins나 셀프 호스티드 러너, 클라우드면 OIDC로 키 없이 클라우드 서비스에 배포, 쿠버네티스면 Argo CD 같은 GitOps를 쓴다. 이 문서는 이 프로젝트와 상관없이 일반적인 Spring Boot + Docker 앱을 기준으로 쓴다.

예시의 이름은 모두 가짜다. `owner/app`, `example.com`, `deploy` 계정은 자기 것으로 바꿔 읽는다. 개념(트리거, 산출물, 환경, 헬스 체크, OIDC)은 [69](./69-ci-cd-concepts.md)를 먼저 읽고 오면 쉽다.

## 1. 이 문서로 배우는 것

- 상황에 맞는 CI/CD 방식 고르기
- 방법 A: GitHub Actions로 PR마다 테스트하기(CI의 기본)
- 방법 B: GitHub Actions + GHCR + SSH로 서버 배포(되돌리기 포함)
- 방법 C: GitHub Actions 셀프 호스티드 러너로 서버 안에서 배포
- 방법 D: Jenkins와 Jenkinsfile
- 방법 E: GitLab CI/CD
- 방법 F: 클라우드(AWS)에 OIDC로 키 없이 배포
- 방법 G: 쿠버네티스 + Argo CD(GitOps)
- 어느 방법이든 공통인 준비물: 배포 전용 SSH 키, 서버 쪽 배포 스크립트, 비밀값 넣는 곳

## 2. 왜 필요한가

"CI/CD 설정"을 검색하면 도구마다, 글마다 모양이 달라 무엇이 표준인지 헷갈린다. 그런데 뜯어 보면 하는 일은 같다. **테스트 → 이미지 만들기 → 어딘가에 올리기 → 서버가 새 이미지로 바꾸기 → 확인.** 달라지는 것은 ① 누가 실행하나(GitHub이 빌려준 컴퓨터, 내 서버, Jenkins 서버) ② 이미지를 어떻게 건네나(파일 복사, 레지스트리) ③ 서버를 어떻게 바꾸나(ssh로 명령, 서버가 스스로 당겨 감, 클라우드 API) 세 가지뿐이다. 여러 방법을 한 번에 보면 이 세 가지가 보이고, 회사에서 처음 보는 파이프라인도 읽을 수 있게 된다.

## 3. 기본 개념: 방법 고르기

### 3.1 한눈에 비교

| 방법 | 실행하는 곳 | 이미지 건네기 | 서버 바꾸기 | 잘 맞는 곳 |
| --- | --- | --- | --- | --- |
| A. Actions PR CI | GitHub 호스티드 러너 | (배포 없음) | (배포 없음) | **모든 프로젝트의 출발점** |
| B. Actions + 레지스트리 + SSH | 호스티드 러너 | GHCR·Docker Hub | 러너가 ssh로 들어가 스크립트 실행(push 방식) | VM·서버 한두 대, 개인·스타트업 프로젝트 |
| C. 셀프 호스티드 러너 | 운영 서버(또는 사내 서버)에 깐 러너 | 같은 컴퓨터라 필요 없음 | 러너가 그 자리에서 실행 | 바깥에서 ssh로 못 들어가는 사내망 서버 |
| D. Jenkins | 직접 띄운 Jenkins 서버와 에이전트 | 사설 레지스트리·Nexus | ssh, 스크립트, 무엇이든 | 회사 안 설치형, 오래된 시스템, 복잡한 절차 |
| E. GitLab CI | GitLab 러너 | GitLab 레지스트리 | ssh, k8s 등 | 코드를 GitLab에 두는 팀 |
| F. 클라우드 관리형 | 호스티드 러너 + OIDC | ECR 등 클라우드 레지스트리 | 클라우드 API(ECS, Cloud Run 등) | AWS·GCP·Azure에서 운영 |
| G. GitOps(Argo CD) | CI는 아무 도구, 배포는 클러스터 안 Argo CD | 레지스트리 | 클러스터가 Git을 보고 스스로 맞춤(pull 방식) | 쿠버네티스 |

### 3.2 고르는 질문

1. **코드를 어디에 두나?** GitHub이면 Actions, GitLab이면 GitLab CI가 가장 자연스럽다. 둘 다 아니거나 사내 규정이 있으면 Jenkins.
2. **어디에 배포하나?** 서버(VM) → B 또는 C. 클라우드 관리형 서비스 → F. 쿠버네티스 → G.
3. **바깥(GitHub)에서 서버로 들어갈 수 있나?** 공인 IP와 ssh 포트가 열려 있으면 B. 사내망 안이라 못 들어오면 C(서버가 GitHub으로 나가서 일을 받아 옴) 또는 사내 Jenkins.
4. **운영 배포 전에 사람이 승인해야 하나?** Actions Environments의 Required reviewers, Jenkins `input`, GitLab `when: manual`로 넣는다.

### 3.3 push 방식과 pull 방식

- **push 방식**(B, D, E, F): CI가 운영 환경에 접속할 권한(ssh 키, 클라우드 권한)을 갖고 밀어 넣는다. 이해하기 쉽다. 대신 CI가 털리면 운영도 털린다.
- **pull 방식**(C 일부, G): 운영 쪽이 정해진 곳(Git 저장소, GitHub)을 보다가 스스로 가져간다. CI가 운영 접속 정보를 갖지 않는다. 설정이 조금 더 복잡하다.

## 4. 동작 원리: 방법별 설정

### 4.0 공통 준비물

#### 배포 전용 SSH 키 (B, D, E에서 사용)

비밀번호 대신 **배포에만 쓰는 키 한 쌍**을 만든다. 내 개인 키를 쓰지 않는다.

```bash
# 내 노트북에서. 암호 없이(-N "") 만든다. CI가 사람 없이 써야 하기 때문
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ./deploy_key -N ""
# deploy_key      : 개인 키 → CI의 비밀값(SSH_PRIVATE_KEY)에 넣는다
# deploy_key.pub  : 공개 키 → 서버의 ~/.ssh/authorized_keys에 한 줄 추가

# 서버의 호스트 키(지문)를 받아 둔다. CI가 "진짜 그 서버"인지 확인하는 데 쓴다
ssh-keyscan -p 22 server.example.com > known_hosts
# 받은 지문이 서버의 진짜 지문인지 서버에서 한 번 대조한다: ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

서버 쪽에서는 배포 전용 계정(`deploy`)을 만들고 docker 그룹에 넣는 것이 일반적이다. docker 그룹은 사실상 root 권한이므로 이 계정의 키는 운영 비밀번호만큼 소중하게 다룬다. 다 넣었으면 노트북의 `deploy_key` 파일은 지운다.

`authorized_keys`에서 그 키에 제한을 거는 방법도 있다. 예: `restrict,command="bash ~/app/deploy.sh" ssh-ed25519 AAAA...` 처럼 쓰면 이 키로는 그 스크립트만 실행할 수 있다(태그는 `SSH_ORIGINAL_COMMAND`로 받아야 하니 스크립트를 그에 맞게 짠다).

#### 서버 쪽 배포 스크립트 (B, C, D, E에서 공통)

어느 도구로 부르든 서버에서 하는 일은 같으므로 **서버에 스크립트 하나를 두고 CI는 그것만 부르게** 하는 것이 관리하기 쉽다. 아래는 레지스트리에서 이미지를 받아 교체하고, 헬스 체크에 실패하면 직전 이미지로 되돌리는 예다.

```bash
#!/usr/bin/env bash
# ~/app/deploy.sh  사용법: TAG=<커밋 SHA> bash ~/app/deploy.sh
set -euo pipefail

IMAGE=ghcr.io/owner/app
NAME=app
NEW="$IMAGE:${TAG:?TAG가 필요합니다}"

docker pull "$NEW"
# 지금 떠 있는 컨테이너의 이미지를 기억해 둔다(되돌리기용)
prev="$(docker inspect --format '{{.Config.Image}}' "$NAME" 2>/dev/null || true)"

run() {
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  # 비밀값은 서버의 ~/app/.env(권한 600)에서 읽는다. 다른 방법은 4.0의 "비밀값을 어디에 두나"
  docker run -d --name "$NAME" --restart unless-stopped \
    -p 127.0.0.1:8080:8080 --env-file "$HOME/app/.env" "$1" >/dev/null
}

healthy() {
  for _ in $(seq 1 60); do
    if curl -fsS http://127.0.0.1:8080/actuator/health 2>/dev/null | grep -q '"status":"UP"'; then
      return 0
    fi
    sleep 2
  done
  return 1
}

run "$NEW"
if healthy; then
  echo "배포 성공: $NEW"
  exit 0
fi

echo "헬스 체크 실패. 마지막 로그:" >&2
docker logs --tail 100 "$NAME" >&2 || true
if [ -n "$prev" ] && [ "$prev" != "$NEW" ]; then
  echo "직전 이미지로 되돌립니다: $prev" >&2
  run "$prev"
  healthy && echo "되돌리기 완료" >&2 || echo "되돌린 버전도 뜨지 않습니다. 직접 확인하세요" >&2
fi
exit 1   # 실패로 끝내야 CI 화면이 빨갛게 된다
```

헬스 체크 주소 `/actuator/health`는 `spring-boot-starter-actuator`를 넣어야 생긴다. 바깥에 다 열지 않도록 `management.endpoints.web.exposure.include=health` 정도만 연다.

Docker Compose로 띄운다면 `run` 부분은 이렇게 바뀐다.

```yaml
# docker-compose.prod.yml
services:
  app:
    image: ghcr.io/owner/app:${TAG}
    env_file: .env
    ports: ["127.0.0.1:8080:8080"]
    restart: unless-stopped
```

```bash
TAG="$TAG" docker compose -f docker-compose.prod.yml pull app
TAG="$TAG" docker compose -f docker-compose.prod.yml up -d app
```

#### 비밀값을 어디에 두나

| 두는 곳 | 장점 | 단점 |
| --- | --- | --- |
| 서버의 `.env` 파일(권한 600) | 단순. CI가 운영 비밀번호를 몰라도 된다 | 서버에 평문 파일. 바꿀 때 서버에 들어가야 함 |
| CI 비밀값 → ssh 환경 변수 → `docker run -e 이름` | 비밀값을 한곳(CI)에서 관리. 서버에 파일 없음 | CI가 운영 비밀번호를 모두 앎. 컨테이너 환경 변수는 `docker inspect`로 보임 |
| 클라우드 비밀 관리 도구(Secrets Manager, Vault) | 교체·접근 기록, 권한 관리 | 설정이 더 필요. 클라우드나 Vault 서버가 있어야 함 |

어느 쪽이든 **저장소 파일, 이미지 안, 로그**에는 넣지 않는다.

---

### 4.1 방법 A: GitHub Actions로 PR마다 테스트하기

모든 프로젝트의 출발점이다. 배포는 하지 않고, PR과 main에서 빌드·테스트만 한다.

**파일**: `.github/workflows/ci.yml`

```yaml
name: ci

on:
  pull_request:            # PR을 열거나 커밋을 더 올릴 때
  push:
    branches: [main]       # 병합된 뒤에도 한 번 더
  workflow_dispatch:       # Actions 탭의 Run workflow 버튼

permissions:
  contents: read           # GITHUB_TOKEN은 코드 읽기만

# 같은 PR에 커밋을 연달아 올리면 이전 실행은 취소(배포가 아니니 취소해도 된다)
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
          cache: maven            # ~/.m2를 캐시(pom.xml이 같으면 재사용)
      # verify = 컴파일 + 테스트 + 패키징 + 검사 플러그인. Testcontainers는 러너의 docker를 그대로 쓴다
      - run: ./mvnw -B verify
      # 실패했을 때 테스트 보고서를 내려받을 수 있게
      - if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: surefire-reports
          path: target/surefire-reports/

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
          node-version: '24'
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - run: npm ci
      - run: npm run lint --if-present
      - run: npm run build
```

Gradle 프로젝트라면 `actions/setup-java`의 `cache: gradle`을 쓰거나 `gradle/actions/setup-gradle@v4`를 넣고 `./gradlew build`를 부른다.

**Testcontainers 대신 서비스 컨테이너**를 쓰는 방법도 있다. 잡 옆에 DB를 띄워 준다.

```yaml
  backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:17
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_DB: app
        ports: ["5432:5432"]
        options: >-
          --health-cmd "pg_isready -U postgres"
          --health-interval 5s --health-timeout 5s --health-retries 10
    steps:
      # ...
      - run: ./mvnw -B verify
        env:
          SPRING_DATASOURCE_URL: jdbc:postgresql://localhost:5432/app
          SPRING_DATASOURCE_USERNAME: postgres
          SPRING_DATASOURCE_PASSWORD: test
```

Testcontainers를 이미 쓰고 있다면 그대로 두는 편이 낫다. 노트북과 CI가 같은 방식으로 DB를 띄우기 때문이다.

**마무리 설정**: 이 워크플로가 PR에서 한 번 돈 뒤, Settings → Branches(또는 Rules → Rulesets)에서 main에 "Require status checks to pass"를 켜고 `backend`, `frontend`를 고른다. 이제 빨간 PR은 병합되지 않는다.

**함께 두면 좋은 것**: `.github/dependabot.yml`로 의존성과 Action 버전을 자동으로 올리는 PR을 받는다.

```yaml
version: 2
updates:
  - package-ecosystem: maven
    directory: /
    schedule: { interval: weekly }
  - package-ecosystem: npm
    directory: /frontend
    schedule: { interval: weekly }
  - package-ecosystem: github-actions
    directory: /
    schedule: { interval: weekly }
```

---

### 4.2 방법 B: GitHub Actions + GHCR + SSH로 서버 배포

서버 한두 대에 Docker로 띄우는 경우 가장 흔한 모양이다. CI(방법 A)는 그대로 두고 배포 워크플로를 따로 만든다.

**흐름**: main 병합 → 테스트 → 이미지 빌드해서 GHCR에 `:SHA`와 `:latest`로 push → (운영 환경 승인) → ssh로 서버에 들어가 `TAG=SHA bash ~/app/deploy.sh` → 서버가 pull하고 교체, 헬스 체크, 실패면 되돌림.

**준비**

1. 4.0의 배포 키를 만들고 서버 `authorized_keys`에 공개 키를 넣는다.
2. 저장소 Settings → Environments → New environment `production`
   - Environment secrets: `SSH_HOST`, `SSH_PORT`, `SSH_USER`, `SSH_PRIVATE_KEY`(deploy_key 내용 전체), `SSH_KNOWN_HOSTS`(known_hosts 내용)
   - Deployment branches: `main`만
   - Required reviewers: 승인을 받고 싶으면 사람 지정(공개 저장소는 무료, 비공개 저장소는 유료 요금제에서 쓸 수 있다)
3. 서버에서 GHCR에 로그인해 둔다. 패키지가 공개면 필요 없다. 비공개면 GitHub에서 `read:packages` 권한만 있는 토큰(PAT)을 만들어 서버에서 한 번:
   ```bash
   echo "<토큰>" | docker login ghcr.io -u <내 GitHub 아이디> --password-stdin
   ```
4. 서버에 `~/app/deploy.sh`(4.0)와 `~/app/.env`를 둔다.

**파일**: `.github/workflows/deploy.yml`

```yaml
name: deploy

on:
  push:
    branches: [main]
    paths-ignore: ['**.md', 'docs/**']   # 문서만 바뀌면 배포하지 않음
  workflow_dispatch:

# 배포는 취소하지 않고 차례로
concurrency:
  group: deploy-production
  cancel-in-progress: false

env:
  IMAGE: ghcr.io/owner/app      # 반드시 소문자

jobs:
  test:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-java@v5
        with: { distribution: temurin, java-version: '21', cache: maven }
      - run: ./mvnw -B verify

  build:
    needs: test
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write             # GHCR에 올리기
    steps:
      - uses: actions/checkout@v5
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}   # 따로 만들 필요 없는 자동 토큰
      - uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: |
            ${{ env.IMAGE }}:${{ github.sha }}
            ${{ env.IMAGE }}:latest
          # Docker 레이어 캐시를 GitHub Actions 캐시에 저장
          cache-from: type=gha
          cache-to: type=gha,mode=max

  deploy:
    needs: build
    runs-on: ubuntu-latest
    permissions:
      contents: read
    environment:
      name: production                 # 이 환경의 비밀값·승인 규칙이 적용된다
      url: https://example.com
    steps:
      - name: SSH 준비
        env:
          SSH_PRIVATE_KEY: ${{ secrets.SSH_PRIVATE_KEY }}
          SSH_KNOWN_HOSTS: ${{ secrets.SSH_KNOWN_HOSTS }}
        run: |
          install -m 700 -d ~/.ssh
          printf '%s\n' "$SSH_PRIVATE_KEY" > ~/.ssh/deploy_key
          chmod 600 ~/.ssh/deploy_key
          printf '%s\n' "$SSH_KNOWN_HOSTS" > ~/.ssh/known_hosts
      - name: 서버에서 새 이미지로 교체
        run: |
          ssh -i ~/.ssh/deploy_key -p "${{ secrets.SSH_PORT }}" \
            "${{ secrets.SSH_USER }}@${{ secrets.SSH_HOST }}" \
            "TAG=${{ github.sha }} bash ~/app/deploy.sh"
```

비밀값을 `run:` 안에 `${{ secrets.X }}`로 바로 쓰지 않고 `env:`로 넘긴 뒤 `"$X"`로 쓰는 것은, 값에 따옴표나 `$` 같은 글자가 있어도 셸 문법이 깨지지 않게 하기 위해서다.

**ssh 대신 Action을 쓰는 모양**: `appleboy/ssh-action`은 위의 "SSH 준비"와 `ssh` 명령을 한 스텝으로 해 준다.

```yaml
      - uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.SSH_HOST }}
          port: ${{ secrets.SSH_PORT }}
          username: ${{ secrets.SSH_USER }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          fingerprint: ${{ secrets.SSH_HOST_FINGERPRINT }}   # 서버 지문(SHA256:...) 확인
          script: TAG=${{ github.sha }} bash ~/app/deploy.sh
```

**레지스트리를 못 쓰는 경우**(서버가 바깥 레지스트리에 못 나가는 등): `docker save | gzip`으로 이미지를 파일로 만들어 `scp`로 보내고 서버에서 `docker load`한다. 동작은 하지만 매번 수백 MB를 통째로 보내고(레이어 재사용이 안 됨), 서버에 이전 버전이 남지 않으면 되돌리기 어렵다.

**되돌리기를 손으로 하고 싶을 때**: `workflow_dispatch`에 입력을 받아 원하는 태그로 다시 배포하게 한다.

```yaml
on:
  workflow_dispatch:
    inputs:
      tag:
        description: '배포할 이미지 태그(커밋 SHA). 비우면 이번 커밋'
        required: false
# ...
          "TAG=${{ inputs.tag || github.sha }} bash ~/app/deploy.sh"
```

이전에 잘 돌던 커밋 SHA를 넣고 Run workflow를 누르면 그 이미지로 돌아간다(레지스트리에 남아 있으니 다시 빌드하지 않는다. 이때는 test·build 잡을 건너뛰도록 `if: inputs.tag == ''`를 붙인다).

---

### 4.3 방법 C: 셀프 호스티드 러너로 서버 안에서 배포

GitHub이 빌려주는 컴퓨터 대신 **내 서버에 러너 프로그램을 깔아** 워크플로를 그 서버에서 실행한다. 러너가 GitHub으로 나가서 "할 일 있나요?"를 묻는 방식이라, **바깥에서 서버로 들어오는 ssh 포트가 없어도** 된다.

**설치** (저장소 Settings → Actions → Runners → New self-hosted runner 화면에 나오는 명령을 그대로 따른다)

```bash
# 서버에서, 배포 전용 계정으로
mkdir actions-runner && cd actions-runner
# (화면에 나온 버전의 tar.gz를 내려받아 푼다)
./config.sh --url https://github.com/owner/app --token <화면의 토큰> --labels prod --unattended
sudo ./svc.sh install deploy    # 서비스로 등록(재부팅해도 다시 뜸)
sudo ./svc.sh start
```

**워크플로**: 테스트와 이미지 빌드는 호스티드 러너에서, 배포만 내 서버 러너에서.

```yaml
  deploy:
    needs: build
    runs-on: [self-hosted, linux, prod]    # 라벨로 내 서버 러너를 고른다
    environment: production
    steps:
      - run: TAG=${{ github.sha }} bash ~/app/deploy.sh
```

**주의**

- **공개 저장소에는 쓰지 않는다.** 누군가 포크해서 워크플로를 고친 PR을 보내면 그 코드가 내 서버에서 돌 수 있다. GitHub도 공개 저장소의 셀프 호스티드 러너를 권하지 않는다.
- 러너 계정은 docker 그룹에 들어가므로 서버 root와 같은 위험도다. 운영 서버에 두기 싫으면 사내망의 별도 빌드 서버에 러너를 두고 거기서 ssh로 운영 서버에 들어가게 한다.
- 호스티드 러너와 달리 실행이 끝나도 파일이 남는다. 작업 폴더가 쌓이고, 이전 실행의 파일이 다음 실행에 섞일 수 있다.

---

### 4.4 방법 D: Jenkins

Jenkins는 내가 직접 띄우는 CI 서버다. 플러그인이 아주 많고, 어떤 Git 서버·어떤 배포 대상과도 붙는다. 대신 Jenkins 서버 자체(업데이트, 플러그인 호환, 백업, 보안)를 직접 관리해야 한다.

**설치** (Docker로)

```bash
docker run -d --name jenkins --restart unless-stopped \
  -p 8080:8080 -p 50000:50000 \
  -v jenkins_home:/var/jenkins_home \
  jenkins/jenkins:lts-jdk21

# 처음 화면에서 물어보는 관리자 비밀번호
docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
```

브라우저로 `http://서버:8080`에 들어가 "Install suggested plugins"를 고르고, 추가로 **GitHub Branch Source, Docker Pipeline, SSH Agent, Credentials Binding**을 깐다.

**에이전트**: 빌드를 Jenkins 컨트롤러(위 컨테이너)에서 직접 돌리지 말고 **에이전트**(빌드용 컴퓨터)를 따로 붙이는 것이 권장이다. Docker 이미지를 만들려면 에이전트에 docker가 있어야 한다. 아래 예는 `docker` 라벨이 붙은 에이전트가 있다고 본다.

**비밀값**: Manage Jenkins → Credentials에 등록하고 ID로 부른다.

| ID | 종류 | 내용 |
| --- | --- | --- |
| `ghcr` | Username with password | GitHub 아이디 / `write:packages` 토큰 |
| `deploy-ssh` | SSH Username with private key | `deploy` / deploy_key |

**파일**: 저장소 맨 위 `Jenkinsfile`

```groovy
pipeline {
  agent { label 'docker' }

  options {
    disableConcurrentBuilds()                // 겹치지 않게
    timeout(time: 30, unit: 'MINUTES')
    buildDiscarder(logRotator(numToKeepStr: '30'))
  }

  environment {
    IMAGE = 'ghcr.io/owner/app'
  }

  stages {
    stage('Test') {
      steps {
        sh './mvnw -B verify'
      }
      post {
        always { junit 'target/surefire-reports/*.xml' }   // 테스트 결과를 Jenkins 화면에
      }
    }

    stage('Build image') {
      when { branch 'main' }                   // PR 브랜치에서는 테스트만
      steps {
        withCredentials([usernamePassword(credentialsId: 'ghcr',
                          usernameVariable: 'REG_USER', passwordVariable: 'REG_PASS')]) {
          // 작은따옴표 ''' : Groovy가 아니라 셸이 변수를 풀게 해서 비밀값이 Groovy 문자열에 섞이지 않게
          sh '''
            echo "$REG_PASS" | docker login ghcr.io -u "$REG_USER" --password-stdin
            docker build -t "$IMAGE:$GIT_COMMIT" -t "$IMAGE:latest" .
            docker push "$IMAGE:$GIT_COMMIT"
            docker push "$IMAGE:latest"
          '''
        }
      }
    }

    stage('Approve') {
      when { branch 'main' }
      steps {
        timeout(time: 1, unit: 'HOURS') {
          input message: '운영에 배포할까요?', ok: '배포'
        }
      }
    }

    stage('Deploy') {
      when { branch 'main' }
      steps {
        sshagent(credentials: ['deploy-ssh']) {
          sh 'ssh -o StrictHostKeyChecking=yes -p 22 deploy@server.example.com "TAG=$GIT_COMMIT bash ~/app/deploy.sh"'
        }
      }
    }
  }

  post {
    failure { echo '실패 알림을 여기서 보낸다(Slack, 메일 플러그인)' }
  }
}
```

`StrictHostKeyChecking=yes`이므로 에이전트의 `~/.ssh/known_hosts`에 서버 지문을 미리 넣어 둔다.

**잡 만들기와 GitHub 연결**

1. New Item → **Multibranch Pipeline** → Branch Sources에 GitHub 저장소 추가(GitHub App이나 토큰 자격 증명). 브랜치와 PR마다 Jenkinsfile을 찾아 자동으로 잡을 만든다.
2. GitHub 저장소 Settings → Webhooks → Payload URL `https://jenkins.example.com/github-webhook/`, 이벤트 push와 pull request. 이제 push하면 바로 빌드가 시작된다(Jenkins가 바깥에서 닿는 주소에 있어야 한다. 안 되면 주기적으로 확인하는 Scan 간격을 둔다).
3. GitHub Branch Source가 빌드 결과를 PR에 상태로 올려 주므로, 브랜치 보호에서 필수 검사로 지정할 수 있다.

**Jenkins를 고를 때 따져 볼 것**: 플러그인 업데이트가 서로 안 맞아 깨지는 일이 잦고, Jenkins 서버가 모든 비밀값을 가진 표적이 된다. 코드가 GitHub에 있고 새로 시작한다면 Actions가 관리할 것이 훨씬 적다. Jenkins는 이미 회사에 있거나, 사내망에서만 돌아야 하거나, 여러 시스템을 엮는 복잡한 절차가 있을 때 고른다.

---

### 4.5 방법 E: GitLab CI/CD

코드를 GitLab에 두면 저장소 맨 위 `.gitlab-ci.yml` 하나로 CI/CD가 켜진다. 레지스트리(`$CI_REGISTRY_IMAGE`)와 환경, 수동 승인이 기본으로 들어 있다.

**비밀값**: Settings → CI/CD → Variables. `Masked`(로그 가림), `Protected`(보호 브랜치에서만 보임)를 켠다. SSH 키는 **File** 종류로 넣으면 변수 값이 "그 내용을 담은 임시 파일 경로"가 된다.

```yaml
stages: [test, build, deploy]

# MR 파이프라인과 기본 브랜치 파이프라인만 돌게(같은 커밋에 두 번 돌지 않게)
workflow:
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH

variables:
  MAVEN_OPTS: "-Dmaven.repo.local=$CI_PROJECT_DIR/.m2/repository"

test:
  stage: test
  image: eclipse-temurin:21-jdk
  # Testcontainers가 쓸 docker. 러너가 privileged 모드여야 한다
  services:
    - name: docker:27-dind
      alias: docker
  variables:
    DOCKER_HOST: tcp://docker:2375
    DOCKER_TLS_CERTDIR: ""
    TESTCONTAINERS_HOST_OVERRIDE: docker
  cache:
    key: maven
    paths: [.m2/repository]
  script:
    - ./mvnw -B verify
  artifacts:
    when: always
    reports:
      junit: target/surefire-reports/TEST-*.xml   # MR 화면에 테스트 결과

build:
  stage: build
  image: docker:27
  services: ["docker:27-dind"]
  variables:
    DOCKER_TLS_CERTDIR: "/certs"
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
  script:
    - echo "$CI_REGISTRY_PASSWORD" | docker login -u "$CI_REGISTRY_USER" --password-stdin "$CI_REGISTRY"
    - docker build -t "$CI_REGISTRY_IMAGE:$CI_COMMIT_SHA" -t "$CI_REGISTRY_IMAGE:latest" .
    - docker push "$CI_REGISTRY_IMAGE:$CI_COMMIT_SHA"
    - docker push "$CI_REGISTRY_IMAGE:latest"

deploy_production:
  stage: deploy
  image: alpine:3.20
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
      when: manual               # 버튼을 눌러야 배포(지속적 전달)
  environment:
    name: production
    url: https://example.com
  resource_group: production     # 배포가 겹치지 않게
  before_script:
    - apk add --no-cache openssh-client
    - chmod 600 "$SSH_PRIVATE_KEY"            # File 종류 변수 = 파일 경로
    - mkdir -p ~/.ssh && cp "$SSH_KNOWN_HOSTS" ~/.ssh/known_hosts
  script:
    - ssh -i "$SSH_PRIVATE_KEY" deploy@$DEPLOY_HOST "TAG=$CI_COMMIT_SHA bash ~/app/deploy.sh"
```

GitLab의 Environments 화면에서 배포 기록을 보고, 예전 배포의 **Rollback(재배포)** 버튼으로 그 커밋의 deploy 잡을 다시 돌릴 수 있다. 서버가 레지스트리에서 받으려면 서버에서 `read_registry` 권한의 Deploy Token으로 `docker login registry.gitlab.com`을 해 둔다.

---

### 4.6 방법 F: 클라우드(AWS)에 OIDC로 키 없이 배포

클라우드에서는 서버에 ssh로 들어가지 않고 **클라우드 API로 "이 이미지로 바꿔"** 라고 요청한다. 권한은 OIDC로 받는다([69](./69-ci-cd-concepts.md) 3.10). 예는 AWS ECS(Fargate)다. GCP Cloud Run, Azure Container Apps도 모양이 같다.

**준비 (AWS 콘솔, 한 번)**

1. IAM → Identity providers → `token.actions.githubusercontent.com` 추가(Audience `sts.amazonaws.com`)
2. IAM 역할 `github-deploy` 만들기. 신뢰 정책에서 **이 저장소의 production 환경만** 이 역할을 쓸 수 있게 묶는다.
   ```json
   {
     "Effect": "Allow",
     "Principal": { "Federated": "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com" },
     "Action": "sts:AssumeRoleWithWebIdentity",
     "Condition": {
       "StringEquals": {
         "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
         "token.actions.githubusercontent.com:sub": "repo:owner/app:environment:production"
       }
     }
   }
   ```
   권한은 ECR push, ECS 서비스 갱신에 필요한 만큼만 붙인다.
3. ECR 저장소 `app`, ECS 클러스터·서비스를 만든다. DB 비밀번호 같은 앱 비밀값은 **Secrets Manager**에 넣고 태스크 정의의 `secrets`로 연결한다. CI는 운영 DB 비밀번호를 아예 모른다.

**워크플로의 deploy 잡**

```yaml
  deploy:
    needs: test
    runs-on: ubuntu-latest
    environment: production
    permissions:
      id-token: write        # OIDC 토큰 발급에 필요
      contents: read
    steps:
      - uses: actions/checkout@v5
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/github-deploy
          aws-region: ap-northeast-2
      - id: ecr
        uses: aws-actions/amazon-ecr-login@v2
      - name: 이미지 빌드·push
        env:
          IMAGE: ${{ steps.ecr.outputs.registry }}/app:${{ github.sha }}
        run: |
          docker build -t "$IMAGE" .
          docker push "$IMAGE"
          echo "IMAGE=$IMAGE" >> "$GITHUB_ENV"
      - id: taskdef
        uses: aws-actions/amazon-ecs-render-task-definition@v1
        with:
          task-definition: deploy/ecs-task-def.json
          container-name: app
          image: ${{ env.IMAGE }}
      - uses: aws-actions/amazon-ecs-deploy-task-definition@v2
        with:
          task-definition: ${{ steps.taskdef.outputs.task-definition }}
          cluster: production
          service: app
          wait-for-service-stability: true   # 새 태스크가 헬스 체크를 통과할 때까지 기다림
```

ECS는 롤링 배포를 하고, 서비스에 **배포 회로 차단기(deployment circuit breaker)와 롤백**을 켜 두면 새 태스크가 계속 실패할 때 이전 태스크 정의로 스스로 돌아간다. 블루·그린이 필요하면 CodeDeploy와 연결한다.

AWS 안에서만 하고 싶으면 CodePipeline + CodeBuild(빌드) + CodeDeploy(배포)로 같은 일을 한다. 단순한 웹 앱 한 개라면 Elastic Beanstalk, App Runner처럼 더 손이 덜 가는 서비스도 있다.

---

### 4.7 방법 G: 쿠버네티스 + Argo CD (GitOps)

GitOps는 "운영에 떠 있어야 하는 모습"을 **Git 저장소(매니페스트 저장소)에 적어 두고, 클러스터 안의 도구가 그 모습과 실제를 계속 맞추는" 방식이다.

```
앱 저장소 ─(CI: 테스트, 이미지 빌드·push)→ 레지스트리
     └─(CI: 매니페스트 저장소의 이미지 태그를 새 SHA로 바꾸는 커밋/PR)
매니페스트 저장소 ←(Argo CD가 보고 있다가)── 클러스터에 적용
```

- CI는 **클러스터 접속 권한이 없다.** 매니페스트 저장소에 커밋할 권한만 있다(pull 방식).
- 배포 기록 = Git 기록. 되돌리기 = 그 커밋을 `git revert`.
- 누가 클러스터에서 손으로 바꾸면 Argo CD가 Git대로 되돌린다(selfHeal).

**매니페스트 저장소**의 Deployment 일부(쿠버네티스가 헬스 체크로 롤링 교체)

```yaml
# apps/app/base/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata: { name: app }
spec:
  replicas: 2
  strategy:
    rollingUpdate: { maxUnavailable: 0, maxSurge: 1 }   # 새 것이 준비돼야 옛 것을 내림
  selector: { matchLabels: { app: app } }
  template:
    metadata: { labels: { app: app } }
    spec:
      containers:
        - name: app
          image: ghcr.io/owner/app:latest     # kustomize가 SHA 태그로 바꿈
          ports: [{ containerPort: 8080 }]
          envFrom: [{ secretRef: { name: app-secrets } }]
          readinessProbe:
            httpGet: { path: /actuator/health/readiness, port: 8080 }
          livenessProbe:
            httpGet: { path: /actuator/health/liveness, port: 8080 }
```

**Argo CD Application** (클러스터에 한 번 등록)

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: app
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/owner/deploy-manifests
    targetRevision: main
    path: apps/app/overlays/production
  destination:
    server: https://kubernetes.default.svc
    namespace: app
  syncPolicy:
    automated: { prune: true, selfHeal: true }
```

**앱 저장소 CI의 마지막 스텝**(이미지 push 뒤)

```bash
git clone https://x-access-token:${MANIFEST_TOKEN}@github.com/owner/deploy-manifests.git
cd deploy-manifests/apps/app/overlays/production
kustomize edit set image ghcr.io/owner/app=ghcr.io/owner/app:${GITHUB_SHA}
git commit -am "app: ${GITHUB_SHA}"
git push        # 운영은 직접 push 대신 PR로 올려 승인받기도 한다
```

쿠버네티스의 Secret은 base64일 뿐 암호화가 아니므로, Git에 넣을 때는 Sealed Secrets, SOPS, 또는 External Secrets Operator(Vault·클라우드 비밀 관리 도구에서 가져옴)를 쓴다. Flux도 Argo CD와 같은 일을 하는 GitOps 도구다.

## 5. 이 프로젝트에서는

이 프로젝트(GitHub에 코드, 학교 서버 한 대, Docker로 띄움, 바깥에서 ssh로 들어갈 수 있음)는 **방법 A + 방법 B**가 맞는다. 지금은 B와 비슷하지만 레지스트리 대신 파일 복사를 쓰고, A(PR 테스트)가 없다. 공개 저장소라 방법 C(셀프 호스티드 러너)는 쓰지 않는 것이 맞다. 무엇을 어떤 순서로 바꾸면 되는지는 [71](./71-ci-cd-this-project.md)에 정리했다.

## 6. 자주 하는 실수와 함정

| 실수 | 왜 문제인가 | 이렇게 |
| --- | --- | --- |
| GHCR 이미지 이름에 대문자 | `ghcr.io/Owner/App`은 push가 거부된다 | 이미지 이름은 소문자로 |
| `packages: write` 권한을 안 줌 | GHCR push가 `denied`로 실패 | 그 잡의 `permissions`에 추가 |
| 서버에서 GHCR 로그인 안 함 | 비공개 패키지 pull이 `unauthorized` | `read:packages` 토큰으로 한 번 로그인, 또는 패키지 공개 |
| `StrictHostKeyChecking=no` | 중간에서 서버인 척하는 상대에게 키와 비밀값을 넘길 수 있다 | `known_hosts`나 지문을 비밀값으로 두고 확인 |
| 공개 저장소에 셀프 호스티드 러너 | 포크 PR의 코드가 내 서버에서 실행될 수 있다 | 공개 저장소는 호스티드 러너 + ssh |
| Jenkinsfile에서 큰따옴표로 비밀값 | `"... ${PASS}"`는 Groovy가 먼저 풀어 경고·노출 위험 | `sh '''...$PASS...'''` 작은따옴표 |
| GitLab dind인데 러너가 privileged가 아님 | Testcontainers와 docker build가 docker에 연결 못 함 | 러너 설정 `privileged = true`, 또는 kaniko·buildah로 빌드 |
| OIDC 신뢰 정책의 `sub`를 `repo:owner/*`처럼 넓게 | 다른 저장소·브랜치의 워크플로도 운영 권한을 받는다 | 저장소와 환경(또는 브랜치)까지 정확히 |
| 배포 스크립트가 실패해도 0으로 끝남 | CI가 초록인데 운영은 죽어 있다 | `set -euo pipefail`, 헬스 체크 실패 시 `exit 1` |
| 되돌리기를 생각 안 하고 옛 이미지를 바로 지움 | 실패했을 때 돌아갈 이미지가 없다 | SHA 태그로 레지스트리에 남기고, 서버는 오래된 것만 정리 |

## 7. 직접 해 보기

연습용 저장소(빈 Spring Boot 프로젝트 하나)를 만들어 해 본다. 운영 서버를 건드리지 않는다.

1. **방법 A**: 4.1의 `ci.yml`을 넣고 PR을 올려 Checks 탭에 `backend`가 초록으로 뜨는지 본다. 테스트를 일부러 깨뜨려 빨간 X를 본 뒤, 브랜치 보호에 필수 검사로 지정하고 병합 버튼이 막히는지 확인한다.
2. **GHCR까지만**: 4.2의 `build` 잡만 넣고 main에 병합한다. 내 GitHub 프로필의 Packages에 이미지가 생기고, 태그에 커밋 SHA가 붙었는지 본다. 노트북에서 `docker pull ghcr.io/<나>/<저장소>:<SHA>`로 받아 본다.
3. **배포 연습**: 서버 대신 노트북에서 4.0의 `deploy.sh`를 돌려 본다(`TAG=<SHA> bash deploy.sh`). 이어서 일부러 안 뜨는 이미지 태그(예: 잘못된 환경 변수로 실패하는 버전)를 넣어 되돌리기가 동작하는지 본다.
4. **Jenkins 맛보기**: 4.4의 명령으로 노트북에 Jenkins를 띄우고 Pipeline 잡에 `pipeline { agent any; stages { stage('hi') { steps { sh 'echo hello' } } } }`를 넣어 돌려 본다. 화면의 Stage View가 Actions의 잡 화면과 어떻게 대응되는지 비교한다.

## 8. 확인 문제

1. 사내망 안에 있어 바깥에서 ssh로 들어갈 수 없는 서버에 GitHub 코드로 배포하고 싶다. 어떤 방법들이 있나?
<details><summary>답</summary>그 서버(또는 같은 사내망의 빌드 서버)에 셀프 호스티드 러너를 깔아 러너가 GitHub으로 나가서 일을 받아 오게 하거나(방법 C), 사내 Jenkins가 webhook 대신 주기적으로 저장소를 확인하게 하거나(방법 D), 서버가 레지스트리를 주기적으로 보고 새 이미지를 당겨 오게(pull 방식) 한다.</details>

2. 4.2에서 `docker/login-action`의 비밀번호로 쓴 `secrets.GITHUB_TOKEN`은 누가 만들었나? 따로 등록해야 하나?
<details><summary>답</summary>GitHub이 워크플로 실행마다 자동으로 만들어 주는 토큰이라 등록할 필요가 없다. 권한은 `permissions:`로 정하고(여기서는 `packages: write`), 실행이 끝나면 만료된다.</details>

3. Jenkinsfile에서 `sh "docker login -p ${REG_PASS}"`처럼 큰따옴표를 쓰면 왜 안 좋은가?
<details><summary>답</summary>Groovy가 셸보다 먼저 문자열 안의 비밀값을 풀어 넣기 때문에 비밀값이 Groovy 쪽 문자열과 명령줄(ps로 보임)에 들어간다. 작은따옴표로 셸이 환경 변수를 풀게 하고, 비밀번호는 `--password-stdin`으로 넘긴다.</details>

4. 방법 B(push 방식)와 방법 G(GitOps, pull 방식)에서 CI가 털렸을 때 공격자가 얻는 것은 각각 무엇인가?
<details><summary>답</summary>B는 CI가 운영 서버 ssh 키(와 경우에 따라 운영 비밀값)를 갖고 있으므로 운영 서버에 바로 들어갈 수 있다. G는 CI가 매니페스트 저장소 쓰기 권한만 가지므로 공격자는 커밋을 남겨야 하고(기록이 남고 PR 승인을 걸 수 있음), 클러스터 자격 증명은 얻지 못한다.</details>

5. OIDC 신뢰 정책에서 `sub`를 `repo:owner/app:environment:production`으로 묶었다. 같은 저장소의 기능 브랜치 워크플로가 이 역할을 쓰려 하면?
<details><summary>답</summary>거부된다. 그 워크플로의 토큰 `sub`는 `repo:owner/app:ref:refs/heads/기능브랜치`(또는 다른 환경)라 조건과 맞지 않는다. production 환경(배포 브랜치를 main으로 제한)을 거친 잡만 받는다.</details>

## 9. 더 읽을거리

- GitHub Docs: "Building and testing Java with Maven", "Publishing Docker images", "Working with the Container registry", "Using environments for deployment", "About self-hosted runners"(보안 항목), "Configuring OpenID Connect in Amazon Web Services"
- docker/build-push-action README의 "Cache management"(type=gha)
- Jenkins 문서: "Pipeline Syntax", "Using credentials", "Branches and Pull Requests"(Multibranch)
- GitLab 문서: "Get started with GitLab CI/CD", "Use Docker to build Docker images", "Environments and deployments", "CI/CD variables"
- Testcontainers 문서: "Continuous Integration"(GitLab dind 설정)
- AWS 문서: "Deploying to Amazon ECS with GitHub Actions", ECS "deployment circuit breaker"
- Argo CD 문서: "Getting Started", "Automated Sync Policy"; OpenGitOps 원칙
