# 69. CI/CD 개념: 파이프라인, 배포 전략, 비밀값

> 관련 스텝: [스텝 24](../step-24.md) (배포) · 관련 개념: [70-ci-cd-setup-methods](./70-ci-cd-setup-methods.md)(설정 방법 여러 가지), [71-ci-cd-this-project](./71-ci-cd-this-project.md)(이 프로젝트에 적용), [68-server-docker-dev-prod](./68-server-docker-dev-prod.md), [05-spring-testing](./05-spring-testing.md)

> **한 줄 답**: CI는 "합치기 전에 기계가 매번 빌드하고 테스트해서 망가진 코드가 main에 못 들어오게" 하는 것이고, CD는 "main에 들어간 코드를 사람 손을 덜 타고 같은 방식으로 서버까지 내보내는" 것이다. 도구(GitHub Actions, Jenkins, GitLab CI)는 이것을 자동으로 돌려 주는 실행기일 뿐이고, 핵심은 **어떤 순서로, 무엇을 검사하고, 무엇을 만들어, 어떻게 내보내고, 실패하면 어떻게 되돌리느냐**다.

설정 파일을 실제로 쓰는 법은 [70](./70-ci-cd-setup-methods.md), 이 프로젝트의 지금 배포 설정 읽기와 고치는 순서는 [71](./71-ci-cd-this-project.md)에 있다. 이 문서는 그 둘을 읽기 위한 바탕이다.

## 1. 이 문서로 배우는 것

- CI, 지속적 전달(Continuous Delivery), 지속적 배포(Continuous Deployment)의 차이
- 파이프라인의 단계: 트리거 → 빌드 → 테스트 → 패키징(산출물) → 배포 → 확인
- 산출물(artifact)과 "한 번 만들어 여러 곳에 배포"
- 브랜치 전략과 PR 검사, 브랜치 보호 규칙
- 환경(dev, staging, prod)과 승인
- 배포 전략: 다시 띄우기, 롤링, 블루·그린, 카나리
- 헬스 체크와 되돌리기(롤백), DB 마이그레이션이 끼면 왜 어려운가
- 비밀값을 파이프라인에 넘기는 방법과 OIDC
- 파이프라인이 빨라지는 법(캐시), 겹치지 않게 하는 법(동시 실행 제어)

## 2. 왜 필요한가

CI/CD가 없을 때 배포는 보통 이렇게 한다.

1. 내 노트북에서 `./mvnw package`
2. jar를 서버에 복사
3. 서버에 ssh로 들어가 옛 프로세스를 죽이고 새로 띄움

이 방식이 터지는 지점은 정해져 있다.

| 문제 | 실제로 생기는 일 |
| --- | --- |
| "내 컴퓨터에서는 됐는데" | 내 노트북에만 있던 설정·파일·JDK 버전으로 빌드된 jar가 서버에서 안 뜬다 |
| 테스트를 건너뜀 | 바쁠 때 테스트 없이 올려서 로그인이 깨진 채 배포된다 |
| 누가 무엇을 올렸는지 모름 | 서버에 떠 있는 게 어느 커밋인지 아무도 모른다. 되돌리려 해도 이전 jar가 없다 |
| 순서를 빼먹음 | 환경 변수 하나를 안 바꿔서 앱이 안 뜬다. 사람마다 순서가 다르다 |
| 비밀번호가 여기저기 | 서버 비밀번호가 팀원 노트북, 메모장, 채팅방에 퍼진다 |

CI/CD는 이것을 **글로 적힌 절차(파이프라인 파일)** 로 바꾼다. 절차가 저장소 안에 코드로 있으니 리뷰할 수 있고, 매번 같은 깨끗한 컴퓨터에서 같은 순서로 돈다. 사람은 PR을 올리고 병합하는 일만 한다.

## 3. 기본 개념

### 3.1 CI: 지속적 통합 (Continuous Integration)

**여러 사람의 변경을 자주 main에 합치되, 합칠 때마다 자동으로 빌드·테스트해서 main을 항상 "돌아가는 상태"로 유지**하는 습관이다.

- 언제 도나: PR을 열거나 PR에 커밋을 더 올릴 때(`pull_request`), main에 병합될 때(`push`)
- 무엇을 하나: 컴파일, 단위·통합 테스트, 정적 분석(린트, 포맷 검사), 보안 검사(의존성 취약점)
- 결과: PR 화면에 초록 체크 또는 빨간 X. 빨간 X면 병합 버튼을 막는다(브랜치 보호, 3.5)

CI의 핵심은 "도구를 깔았다"가 아니라 **실패하면 합치지 않는다**는 규칙이다. 테스트가 빨간데 병합할 수 있으면 CI가 있어도 없는 것과 같다.

### 3.2 CD: 두 가지 뜻

CD는 두 가지 뜻으로 쓰인다. 차이는 **운영 배포 직전에 사람이 버튼을 누르느냐** 하나다.

| | 지속적 전달 (Continuous Delivery) | 지속적 배포 (Continuous Deployment) |
| --- | --- | --- |
| 자동으로 되는 것 | 빌드, 테스트, 배포 가능한 산출물 만들기, 보통 스테이징까지 배포 | 운영 배포까지 전부 |
| 운영에 나가는 때 | 사람이 승인 버튼을 누를 때 | 테스트를 통과하면 바로 |
| 잘 맞는 곳 | 배포 시간을 정해 두는 회사, 규제가 있는 서비스, 테스트를 아직 다 믿기 어려울 때 | 테스트가 탄탄하고 되돌리기가 쉬운 서비스, 작은 팀 |

이 프로젝트는 main에 병합하면 바로 운영 서버로 나가므로 **지속적 배포**다. 병합 버튼이 사실상 승인 버튼 역할을 한다.

### 3.3 파이프라인, 잡, 스텝

도구마다 이름은 조금 다르지만 구조는 같다.

```
파이프라인(워크플로)  ← 파일 하나. "main에 push되면 이걸 해라"
 ├─ 잡(job) test       ← 깨끗한 컴퓨터(러너/에이전트) 한 대에서 도는 묶음
 │   ├─ 스텝: 코드 받기
 │   ├─ 스텝: JDK 설치
 │   └─ 스텝: ./mvnw test
 └─ 잡(job) deploy     ← test가 성공해야 시작(needs / 단계 순서)
     ├─ 스텝: 이미지 빌드
     └─ 스텝: 서버에 배포
```

- **트리거**: 파이프라인을 시작시키는 사건. push, PR, 시간 예약(cron), 수동 실행 버튼, 다른 파이프라인 완료 등
- **러너(runner)/에이전트(agent)**: 실제로 명령을 실행하는 컴퓨터. GitHub이 빌려주는 것(호스티드)과 내가 준비한 것(셀프 호스티드)이 있다
- **잡은 서로 다른 컴퓨터**에서 돈다. 그래서 test 잡에서 만든 파일은 deploy 잡에 저절로 넘어가지 않는다. 넘기려면 산출물로 올리고 내려받거나, 레지스트리에 이미지를 올려야 한다
- **스텝은 같은 컴퓨터**에서 차례로 돈다. 앞 스텝이 실패하면 뒤 스텝은 기본적으로 건너뛴다

### 3.4 산출물(artifact)과 "한 번 만들어 여러 곳에"

산출물은 파이프라인이 만들어 내는 배포 가능한 결과물이다. 자바라면 jar, 요즘은 대부분 **Docker 이미지**다.

중요한 원칙: **산출물은 한 번만 만들고, 같은 것을 스테이징과 운영에 차례로 배포한다.** 스테이징용으로 한 번, 운영용으로 또 한 번 빌드하면 그 사이 의존성 버전이 바뀌어 "스테이징에서 확인한 것과 운영에 나간 것이 다른" 일이 생긴다. 환경마다 다른 것은 **설정(환경 변수, 비밀값)** 으로만 바꾼다. (12-Factor App의 "빌드, 릴리스, 실행 단계 분리")

이미지를 보관하는 곳을 **컨테이너 레지스트리**라고 한다.

| 레지스트리 | 특징 |
| --- | --- |
| Docker Hub | 가장 유명. 무료 계정은 비공개 저장소 수와 내려받기 횟수 제한이 있다 |
| GHCR (GitHub Container Registry, `ghcr.io`) | GitHub 저장소와 붙어 있고 Actions의 `GITHUB_TOKEN`으로 바로 올릴 수 있다 |
| AWS ECR, Google Artifact Registry, Azure ACR | 각 클라우드 안에서 쓰기 좋다. 권한을 클라우드 계정(IAM)으로 관리 |
| Harbor, Nexus | 회사가 직접 띄우는 사설 레지스트리 |

### 3.5 이미지 태그: `latest`만 쓰면 안 되는 이유

`latest`는 "가장 최근 것"이라는 약속이 없는, 그냥 이름표다. `latest`만 쓰면

- 서버에 떠 있는 게 어느 커밋인지 알 수 없고
- 이전 버전으로 되돌리려 해도 이전 이미지가 이미 덮어써져 이름이 없다

그래서 실무에서는 **커밋 SHA**(`ghcr.io/me/app:3f2a9c1`)나 **버전**(`v1.4.2`)으로 태그하고, 편의로 `latest`를 함께 붙인다. 배포할 때는 SHA 태그를 지정한다.

### 3.6 브랜치 전략과 PR 검사

| 전략 | 모양 | 어울리는 곳 |
| --- | --- | --- |
| GitHub Flow (트렁크 기반에 가까움) | main 하나 + 짧게 사는 기능 브랜치. PR로 main에 합치고, main은 늘 배포 가능 | 웹 서비스 대부분, 작은 팀, 이 프로젝트 |
| Git Flow | main, develop, feature, release, hotfix 브랜치 | 정해진 날 릴리스하는 앱(모바일 앱, 설치형 제품) |
| 환경 브랜치 | dev, staging, main 브랜치가 각 환경과 짝 | 오래된 회사 프로젝트에서 자주 보임. 브랜치끼리 내용이 어긋나기 쉬움 |

**브랜치 보호 규칙**(GitHub: Settings → Branches 또는 Rulesets)으로 main을 지킨다.

- Require a pull request before merging: main에 직접 push 금지
- Require status checks to pass: 지정한 CI 잡(예: `test`)이 초록이어야 병합 가능
- Require branches to be up to date: main의 최신 내용과 합친 상태로 테스트됐어야 병합 가능
- Require approvals: 리뷰어 승인 수

CI 잡을 "필수 검사"로 지정하려면 그 잡이 **PR에서 한 번이라도 돌아야** 목록에 나타난다. push to main에만 걸린 워크플로는 PR에서 돌지 않으므로 필수 검사로 지정할 수 없다.

### 3.7 환경(environment)과 승인

| 환경 | 용도 |
| --- | --- |
| local | 내 노트북. `docker compose`로 DB를 띄움 |
| dev | 개발자가 마음대로 올려 보는 공용 서버 |
| staging | 운영과 같은 모양의 리허설 서버. 운영 직전 마지막 확인 |
| prod | 실제 사용자가 쓰는 운영 |

GitHub Actions의 **Environments** 기능은 환경마다

- 그 환경에서만 보이는 비밀값(Environment secrets)
- 배포 전 승인자(Required reviewers), 대기 시간(Wait timer)
- 어느 브랜치에서만 배포할 수 있는지(Deployment branches)

를 정하게 해 준다. 운영 비밀값을 `production` 환경에만 넣어 두면, 아무 PR 워크플로가 운영 비밀번호를 읽을 수 없다.

### 3.8 배포 전략

| 전략 | 하는 일 | 끊김 | 되돌리기 | 비용 |
| --- | --- | --- | --- | --- |
| 다시 띄우기 (Recreate) | 옛 것을 끄고 새 것을 띄움 | 뜨는 동안 끊김(수십 초) | 옛 이미지로 다시 띄움 | 서버 한 대면 됨 |
| 롤링 (Rolling) | 여러 대 중 몇 대씩 차례로 교체 | 거의 없음 | 다시 차례로 교체 | 서버 여러 대 |
| 블루·그린 (Blue-Green) | 새 버전(그린)을 옆에 따로 띄우고 확인한 뒤, 앞단(nginx, 로드밸런서)이 가리키는 곳을 한 번에 바꿈 | 없음 | 가리키는 곳을 다시 블루로 | 잠깐 두 벌 |
| 카나리 (Canary) | 새 버전에 사용자 일부(1%, 10%...)만 보내고 오류율을 보며 늘림 | 없음 | 비율을 0으로 | 트래픽 나누기 장치와 모니터링 필요 |

서버 한 대짜리 학습 프로젝트는 **다시 띄우기**로 충분하다. 끊김 없이 하고 싶으면 한 서버 안에서 포트 두 개로 블루·그린을 흉내 낼 수 있다(nginx `upstream`을 바꾸고 `nginx -s reload`).

### 3.9 헬스 체크와 되돌리기

배포는 "명령이 성공했다"가 아니라 **"새 버전이 실제로 요청을 처리한다"** 를 확인해야 끝난다.

- **헬스 체크**: 앱이 뜬 뒤 정해진 주소(Spring Boot Actuator의 `/actuator/health`)를 불러 `UP`인지 본다. DB·Redis 연결까지 확인해 준다
- **스모크 테스트**: 배포 직후 핵심 화면 몇 개(첫 화면, 로그인 API)를 불러 200이 오는지만 빠르게 본다
- **자동 되돌리기**: 헬스 체크가 실패하면 직전 버전 이미지로 다시 띄운다. 그러려면 **직전 이미지가 남아 있어야** 한다(3.5)

#### DB 마이그레이션이 끼면

코드는 이전 이미지로 되돌리면 끝이지만, **DB 구조는 되돌아가지 않는다.** Flyway가 새 버전에서 컬럼을 지웠다면 옛 코드는 그 컬럼을 찾다가 실패한다. 그래서 실무에서는 DB 변경을 **늘리기 → 옮기기 → 줄이기(expand → migrate → contract)** 세 번의 배포로 나눈다.

1. 늘리기: 새 컬럼을 추가만 한다(옛 코드도 그대로 돈다)
2. 옮기기: 새 코드가 새 컬럼을 쓰고, 데이터를 채운다
3. 줄이기: 옛 코드가 다시 올 일이 없을 때 옛 컬럼을 지운다

이렇게 하면 어느 단계에서든 코드를 한 칸 되돌려도 DB와 맞는다. ([03 Flyway](./03-flyway-migration.md)의 "추가 → 채우기 → NOT NULL"과 같은 생각이다.)

### 3.10 비밀값을 파이프라인에 넘기기

파이프라인은 서버 비밀번호, DB 비밀번호, 레지스트리 토큰 같은 값을 써야 한다. 저장소 파일에 적으면 안 되니 **도구의 비밀값 저장소**에 넣고 실행할 때 꺼내 쓴다.

| 방법 | 설명 |
| --- | --- |
| CI 도구의 비밀값 저장소 | GitHub Secrets(저장소·환경·조직 단위), GitLab CI/CD Variables(masked, protected), Jenkins Credentials. 로그에 찍히면 `***`로 가린다 |
| 외부 비밀 관리 도구 | HashiCorp Vault, AWS Secrets Manager, GCP Secret Manager. 파이프라인이나 앱이 실행 중에 직접 꺼내 온다. 교체·감사 기록이 강하다 |
| **OIDC (키 없는 인증)** | GitHub Actions가 "나는 이 저장소의 main 브랜치 워크플로다"라는 짧게 사는 토큰을 발급받고, 클라우드(AWS, GCP, Azure)가 그 토큰을 믿고 몇 분짜리 임시 권한을 준다. **오래 사는 클라우드 키를 Secrets에 아예 넣지 않는다.** 클라우드에 배포할 때 요즘 표준 |

주의할 점

- 비밀값은 **로그에 찍지 않는다**. 가림 처리는 값이 그대로 찍힐 때만 동작한다. base64로 바꾸거나 한 글자씩 나눠 찍으면 그대로 보인다
- **포크에서 온 PR**에는 GitHub이 비밀값을 넘기지 않는다(`pull_request` 이벤트). 그래서 공개 저장소의 PR CI는 비밀값 없이 돌 수 있게 짠다. `pull_request_target`은 비밀값이 넘어가지만 포크의 코드를 실행하면 비밀값을 훔칠 수 있으니 쓰지 않는 것이 기본이다
- 워크플로의 `GITHUB_TOKEN` 권한은 `permissions:`로 필요한 만큼만 준다(`contents: read` 기본)
- 서버 접속은 비밀번호보다 **SSH 키**, 그것도 배포 전용 키를 쓴다. 키는 서버의 `authorized_keys`에서 지우면 바로 끊을 수 있다

### 3.11 빠르게, 겹치지 않게

- **의존성 캐시**: 매번 Maven 라이브러리 수백 MB를 내려받지 않게 `~/.m2`를 캐시한다(`actions/setup-java`의 `cache: maven`)
- **Docker 레이어 캐시**: 바뀌지 않은 레이어(의존성 내려받기)를 다시 만들지 않는다. Dockerfile에서 `pom.xml`만 먼저 복사해 `dependency:go-offline`을 하는 이유다
- **동시 실행 제어**: 연달아 두 번 병합하면 배포 두 개가 동시에 서버를 건드릴 수 있다. GitHub Actions `concurrency`, Jenkins `disableConcurrentBuilds()`, GitLab `resource_group`으로 하나씩 돌게 한다
- **경로 필터**: 문서만 바뀌었으면 배포하지 않는다(`paths-ignore: ['**.md']`)

## 4. 동작 원리

GitHub Actions를 예로, PR을 올리고 병합할 때 일어나는 일이다.

```
지원: 기능 브랜치 push → PR 열기
   │
   ▼  (pull_request 이벤트)
GitHub: .github/workflows/*.yml 중 pull_request에 걸린 것을 찾음
   │
   ▼
호스티드 러너(ubuntu 가상 머신 한 대, 매번 새것) 배정
   ├─ actions/checkout: PR 브랜치를 main과 합친 상태(merge commit)로 받음
   ├─ JDK 21 설치, ~/.m2 캐시 복원
   ├─ ./mvnw test (Testcontainers가 러너의 docker로 PostgreSQL·Redis를 띄움)
   └─ 결과를 PR의 Checks 탭에 보고 → 초록/빨강
   │
   ▼  (브랜치 보호: 초록이어야 병합 버튼 활성)
지원: Merge
   │
   ▼  (push 이벤트, main)
GitHub: push에 걸린 워크플로 실행
   ├─ test 잡 (다시 한 번)
   └─ deploy 잡 (needs: test)
        ├─ 이미지 빌드, 레지스트리에 push (또는 파일로 복사)
        ├─ ssh로 서버 접속 → 새 이미지로 컨테이너 교체
        └─ 헬스 체크 → 실패면 이전 이미지로 되돌림, 잡을 빨강으로
   │
   ▼
러너 가상 머신은 버려짐 (다음 실행은 다시 깨끗한 새 머신)
```

러너가 매번 새것이라는 점이 CI의 장점(누가 돌려도 같은 결과)이자, 캐시를 따로 설정해야 하는 이유다.

## 5. 이 프로젝트에서는

자세한 것은 [71](./71-ci-cd-this-project.md)에 있다. 요약하면

| 항목 | 지금 |
| --- | --- |
| CI/CD 도구 | GitHub Actions, `.github/workflows/deploy.yml` 한 파일 |
| 트리거 | main에 push(=병합), 수동 실행(`workflow_dispatch`) |
| 테스트 | `./mvnw -B test` (Testcontainers) |
| 산출물 | Docker 이미지 `aigj017/now-log:latest`를 `docker save`로 파일(tar.gz)로 만들어 scp로 복사 |
| 배포 | ssh로 서버에서 `deploy/deploy.sh` 실행 → 이미지 load, 컨테이너 다시 띄우기 |
| 전략 | 다시 띄우기(Recreate) |
| 확인 | 로그에 `Started BlogApplication`이 나올 때까지 최대 3분 기다림 |
| 비밀값 | Repository secrets → ssh 환경 변수 → `docker run -e 이름` |
| 겹침 방지 | `concurrency: deploy` |

## 6. 자주 하는 실수와 함정

| 실수 | 왜 문제인가 | 이렇게 |
| --- | --- | --- |
| CI가 main push에만 걸려 있음 | 깨진 코드가 이미 main에 들어온 뒤에야 안다. 필수 검사로 지정도 못 한다 | `pull_request`에도 테스트를 건다 |
| 테스트를 `-DskipTests`로 건너뛰는 배포 | 급할 때마다 건너뛰게 되고, 결국 배포가 테스트 없이 나간다 | 테스트 잡을 `needs`로 묶어 건너뛸 수 없게 |
| `latest` 태그만 사용 | 무엇이 떠 있는지 모르고, 되돌릴 이미지가 없다 | SHA 태그 + `latest` |
| 환경마다 다시 빌드 | 스테이징과 운영 산출물이 다를 수 있다 | 한 번 빌드, 설정만 다르게 |
| 비밀값을 `echo`로 확인 | 가림이 안 되는 형태로 찍히면 로그에 남는다(공개 저장소면 누구나 본다) | 길이나 존재 여부만 확인 |
| 배포 끝 = 명령 성공 | 컨테이너는 떴지만 DB 연결 실패로 500만 내는 상태를 "성공"으로 본다 | 헬스 체크까지 하고 끝 |
| 마이그레이션과 코드 되돌리기를 한 번에 생각 | 컬럼을 지운 배포를 되돌리면 옛 코드가 깨진다 | 늘리기 → 옮기기 → 줄이기 |
| 외부 Action을 `@main`으로 사용 | 그 저장소가 바뀌거나 탈취되면 내 비밀값이 새어 나간다 | 버전 태그(`@v5`) 이상, 민감하면 커밋 SHA로 고정. Dependabot으로 갱신 |
| 파이프라인을 손으로만 고치고 실행 안 해 봄 | YAML 들여쓰기 하나로 배포가 멈춘다 | `workflow_dispatch`로 돌려 보고, 작은 PR로 고친다 |

## 7. 직접 해 보기

1. GitHub에서 now-log 저장소의 **Actions** 탭을 열고 최근 `deploy` 실행 하나를 눌러 본다. `test`와 `deploy` 잡이 어떤 순서로 돌았는지, 각 스텝이 몇 초 걸렸는지 본다.
2. `deploy` 잡의 "서버에서 실행" 스텝 로그에서 비밀값이 `***`로 가려졌는지 확인한다.
3. **Settings → Branches**(또는 Rules)에서 main에 보호 규칙이 있는지 본다. 없다면 [71](./71-ci-cd-this-project.md)의 1단계를 먼저 하고 다시 와서 "Require status checks"에 `test`를 지정해 본다.
4. 일부러 테스트 하나를 깨뜨린 PR을 올려 PR 화면에 빨간 X가 뜨고 병합 버튼이 막히는지 본다(병합하지 말고 닫는다).

## 8. 확인 문제

1. 지속적 전달과 지속적 배포의 차이를 한 문장으로 말해 보자. 이 프로젝트는 어느 쪽인가?
<details><summary>답</summary>운영 배포 직전에 사람이 승인하면 지속적 전달, 테스트를 통과하면 바로 운영에 나가면 지속적 배포다. 이 프로젝트는 main 병합 즉시 운영으로 나가므로 지속적 배포다.</details>

2. test 잡에서 `target/app.jar`를 만들었는데 deploy 잡에서 그 파일이 없다고 나온다. 왜인가?
<details><summary>답</summary>잡마다 다른 러너(컴퓨터)에서 돌기 때문이다. 산출물로 올렸다 내려받거나(`actions/upload-artifact`·`download-artifact`), deploy 잡에서 다시 만들거나, 이미지를 레지스트리에 올려 넘겨야 한다.</details>

3. 왜 이미지에 커밋 SHA 태그를 붙이는가? 두 가지 이유를 말해 보자.
<details><summary>답</summary>① 지금 서버에 떠 있는 게 어느 커밋인지 알 수 있다. ② 이전 버전 이미지가 이름을 가진 채 남아 있어 그 태그로 바로 되돌릴 수 있다.</details>

4. `user.nickname` 컬럼을 `display_name`으로 바꾸고 싶다. 한 번의 배포로 이름을 바꾸면 되돌리기가 왜 위험하고, 어떻게 나누면 되는가?
<details><summary>답</summary>이름을 바꾼 뒤 코드를 이전 이미지로 되돌리면 옛 코드는 `nickname`을 찾다가 실패한다. ① `display_name` 추가(옛 코드는 무시) ② 새 코드가 두 컬럼에 쓰고 `display_name`을 읽으며 데이터 채움 ③ 옛 코드가 돌아올 일이 없을 때 `nickname` 삭제, 세 번으로 나눈다.</details>

5. 공개 저장소에 낯선 사람이 포크해서 PR을 보냈다. 이 PR의 CI에서 `secrets.SSH_PASSWORD`는 무슨 값인가? 왜 그렇게 설계됐나?
<details><summary>답</summary>빈 값이다. 포크 PR은 남이 쓴 코드를 내 러너에서 실행하는 것이므로, 비밀값을 넘기면 그 코드가 비밀값을 밖으로 보낼 수 있기 때문이다.</details>

6. OIDC를 쓰면 GitHub Secrets에 무엇을 넣지 않아도 되나?
<details><summary>답</summary>오래 사는 클라우드 접근 키(AWS Access Key 등). GitHub이 실행마다 발급하는 짧은 토큰을 클라우드가 믿고 몇 분짜리 임시 권한을 준다.</details>

## 9. 더 읽을거리

- GitHub Docs, "Understanding GitHub Actions"와 "Using environments for deployment"
- GitHub Docs, "About protected branches", "About rulesets"
- GitHub Docs, "Security hardening for GitHub Actions"(외부 Action 고정, `pull_request_target` 주의)
- GitHub Docs, "About security hardening with OpenID Connect"
- Martin Fowler, "Continuous Integration", "BlueGreenDeployment", "CanaryRelease"
- The Twelve-Factor App, "V. Build, release, run", "III. Config"
- 이어서: [70 설정 방법 여러 가지](./70-ci-cd-setup-methods.md) → [71 이 프로젝트에 적용](./71-ci-cd-this-project.md)
