# CI/CD: 개념, 설정 방법 여러 가지, 이 프로젝트에 적용

> 관련 스텝: [스텝 24](../../스텝-24.md) (배포)
> 관련 개념: [Docker와 서버](./03-Docker와-서버.md)(서버와 Docker), [Spring 테스트](./04-Spring-테스트.md), [Flyway 마이그레이션](../2-데이터/02-Flyway-마이그레이션.md), [이중화와 롤링 배포](./06-이중화와-롤링-배포.md)

> **한 줄 답**: CI는 "합치기 전에 기계가 매번 빌드하고 테스트해서 망가진 코드가 main에 못 들어오게" 하는 것이고, CD는 "main에 들어간 코드를 사람 손을 덜 타고 같은 방식으로 서버까지 내보내는" 것이다. 도구(GitHub Actions, Jenkins, GitLab CI)는 이것을 자동으로 돌려 주는 실행기일 뿐이고, 핵심은 **어떤 순서로, 무엇을 검사하고, 무엇을 만들어, 어떻게 내보내고, 실패하면 어떻게 되돌리느냐**다. 실무에서 많이 쓰는 설정 방식은 일곱 가지쯤으로 정리되는데, 서버 한두 대에 Docker로 띄운다면 **GitHub Actions(CI) + 레지스트리에 이미지 올리기 + SSH로 서버에서 받아 교체**가 가장 흔하다(회사 안 서버만 있으면 Jenkins나 셀프 호스티드 러너, 클라우드면 OIDC로 키 없이 클라우드 서비스에 배포, 쿠버네티스면 Argo CD 같은 GitOps). now-log는 "main에 병합 → 테스트 → 이미지를 파일로 만들어 서버에 복사 → 서버에서 `deploy.sh`로 다시 띄우기"까지 이미 자동이고, 부족한 것은 **PR 단계의 검사, 비밀번호 대신 배포 키, 이미지 버전(SHA 태그)과 되돌리기** 세 가지다. 이 순서대로 하나씩 PR로 고치면 4장의 방법 A + B 모양이 된다.

이 문서는 세 부분으로 읽는다. **3장 3.1~3.11과 4장 앞부분**은 CI/CD 개념, **3.12~3.14와 4.0~4.7**은 이 프로젝트와 상관없이 일반적인 Spring Boot + Docker 앱을 기준으로 한 설정 방법 여러 가지, **5장**은 이 프로젝트의 지금 배포 설정 읽기와 고치는 순서다. 앞 둘은 5장을 읽기 위한 바탕이다.

> **5장의 기준 시점**: 5장은 2026-10-14의 now-log `main`(`.github/workflows/deploy.yml`, `deploy/deploy.sh`, `Dockerfile`)을 기준으로 썼다. 5.9부터의 단계별 설정은 **제안**이고 아직 저장소에 들어가지 않았다.
>
> **2026-10-15 바뀐 점 (스텝 25)**: 배포가 "다시 띄우기"에서 **앱 두 대 롤링**으로 바뀌었다([이중화와 롤링 배포](./06-이중화와-롤링-배포.md)). 그 과정에서 5장의 제안 중 일부를 다른 모양으로 했다.
> - **6단계 Actuator**: 했다. `/actuator/health/readiness`(readinessState·db·redis), health만 열고 details 숨김, 메일 검사 끔. 보안 설정은 이미 `permitAll`이라 따로 열 필요가 없었다. 6단계에 적은 대로 Ollama는 넣지 않았다
> - **5단계 되돌리기**: SHA 태그·GHCR 없이, 배포 한 번 안에서 **배포 전 이미지 ID**로 되돌린다. 옛 이미지는 두 대가 모두 바뀐 뒤에만 지운다. 그래서 "배포 도중 실패하면 되돌리기"는 되지만, 며칠 전 버전으로 손으로 되돌리기는 여전히 안 된다(서버에 남는 이미지가 직전 하나뿐)
> - 5.1 표, 5.4·5.7의 설명(다시 띄우기 전략, Redis를 매번 다시 만듦, `docker rm -f`, 로그 한 줄로 확인, 성공하면 옛 이미지 삭제)은 2026-10-14 기준이다. 지금은 Redis는 PING 되면 그대로, `docker stop -t 70`, readiness 확인, 다 끝난 뒤 삭제다
> - 1~4단계(PR CI, 브랜치 보호, 배포 키, production 환경)와 SHA 태그·GHCR는 아직이다

## 1. 이 문서로 배우는 것

**개념**

- CI, 지속적 전달(Continuous Delivery), 지속적 배포(Continuous Deployment)의 차이
- 파이프라인의 단계: 트리거 → 빌드 → 테스트 → 패키징(산출물) → 배포 → 확인
- 산출물(artifact)과 "한 번 만들어 여러 곳에 배포"
- 브랜치 전략과 PR 검사, 브랜치 보호 규칙
- 환경(dev, staging, prod)과 승인
- 배포 전략: 다시 띄우기, 롤링, 블루·그린, 카나리
- 헬스 체크와 되돌리기(롤백), DB 마이그레이션이 끼면 왜 어려운가
- 비밀값을 파이프라인에 넘기는 방법과 OIDC
- 파이프라인이 빨라지는 법(캐시), 겹치지 않게 하는 법(동시 실행 제어)

**설정 방법 여러 가지**

- 상황에 맞는 CI/CD 방식 고르기
- 방법 A: GitHub Actions로 PR마다 테스트하기(CI의 기본)
- 방법 B: GitHub Actions + GHCR + SSH로 서버 배포(되돌리기 포함)
- 방법 C: GitHub Actions 셀프 호스티드 러너로 서버 안에서 배포
- 방법 D: Jenkins와 Jenkinsfile
- 방법 E: GitLab CI/CD
- 방법 F: 클라우드(AWS)에 OIDC로 키 없이 배포
- 방법 G: 쿠버네티스 + Argo CD(GitOps)
- 어느 방법이든 공통인 준비물: 배포 전용 SSH 키, 서버 쪽 배포 스크립트, 비밀값 넣는 곳

**이 프로젝트에 적용**

- 지금 `deploy.yml`을 한 줄씩 읽기: 트리거, 잡, 비밀값이 서버까지 가는 길
- `deploy.sh`와 `Dockerfile`이 파이프라인에서 맡는 일
- 지금 설정의 잘된 점과 빈 곳
- 고치는 순서 일곱 단계와 각 단계의 파일·확인 방법
- 되돌리기와 Flyway 마이그레이션을 함께 생각하기

## 2. 왜 필요한가

### 2.1 손으로 배포하면 터지는 지점

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

### 2.2 도구마다 모양이 달라 보여도 하는 일은 같다

"CI/CD 설정"을 검색하면 도구마다, 글마다 모양이 달라 무엇이 표준인지 헷갈린다. 그런데 뜯어 보면 하는 일은 같다. **테스트 → 이미지 만들기 → 어딘가에 올리기 → 서버가 새 이미지로 바꾸기 → 확인.** 달라지는 것은 ① 누가 실행하나(GitHub이 빌려준 컴퓨터, 내 서버, Jenkins 서버) ② 이미지를 어떻게 건네나(파일 복사, 레지스트리) ③ 서버를 어떻게 바꾸나(ssh로 명령, 서버가 스스로 당겨 감, 클라우드 API) 세 가지뿐이다. 여러 방법을 한 번에 보면 이 세 가지가 보이고, 회사에서 처음 보는 파이프라인도 읽을 수 있게 된다.

### 2.3 now-log 배포가 지금 막히는 곳

now-log의 지금 배포는 잘 돌아가고 있다. 그런데 이런 일이 생기면 막힌다.

- PR에서 테스트가 깨졌는지 모른 채 병합 → main에서 처음 빨간 X를 보고, 그동안 배포는 멈춘다
- 새 버전이 서버에서 안 뜬다 → 옛 이미지는 이미 지워졌고(`docker rmi`), 다시 만들려면 옛 커밋으로 되돌리는 PR을 올리고 테스트·빌드를 처음부터 기다려야 한다
- 학교 서버 비밀번호를 바꾸거나 계정이 털린다 → GitHub Secrets의 `SSH_PASSWORD`는 서버의 모든 일을 할 수 있는 비밀번호라 범위를 좁힐 수 없다

이 셋을 미리 막아 두는 것이 5장의 목표다.

## 3. 기본 개념

### 3.1 CI: 지속적 통합 (Continuous Integration)

**여러 사람의 변경을 자주 main에 합치되, 합칠 때마다 자동으로 빌드·테스트해서 main을 항상 "돌아가는 상태"로 유지**하는 습관이다.

- 언제 도나: PR을 열거나 PR에 커밋을 더 올릴 때(`pull_request`), main에 병합될 때(`push`)
- 무엇을 하나: 컴파일, 단위·통합 테스트, 정적 분석(린트, 포맷 검사), 보안 검사(의존성 취약점)
- 결과: PR 화면에 초록 체크 또는 빨간 X. 빨간 X면 병합 버튼을 막는다(브랜치 보호, 3.6)

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

이렇게 하면 어느 단계에서든 코드를 한 칸 되돌려도 DB와 맞는다. ([Flyway](../2-데이터/02-Flyway-마이그레이션.md)의 "추가 → 채우기 → NOT NULL"과 같은 생각이다.) 이 프로젝트에서 되돌린 옛 앱이 새 DB와 맞는지 판단하는 표는 5장 [되돌리기와 Flyway](#되돌리기와-flyway)에 있다.

> **이 프로젝트에서는 (스텝 25)**: 같은 서버에 앱 두 대를 두고 롤링으로 바꿨다. 헬스 체크는 Actuator의 `/actuator/health/readiness`(DB·Redis 포함), 실패하면 배포 전 이미지 ID로 바꾼 앱을 거꾸로 되돌린다. 롤링에서는 배포하는 동안 옛 버전과 새 버전이 함께 떠 있으므로, 늘리기 → 옮기기 → 줄이기가 되돌리기뿐 아니라 **배포 중**에도 필요하다. [이중화와 롤링 배포](./06-이중화와-롤링-배포.md)

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

여기까지가 개념이다. 아래 3.12~3.14는 이 개념을 실제 도구로 옮길 때 **어떤 방식을 고를지**를 정리한다.

### 3.12 한눈에 비교

| 방법 | 실행하는 곳 | 이미지 건네기 | 서버 바꾸기 | 잘 맞는 곳 |
| --- | --- | --- | --- | --- |
| A. Actions PR CI | GitHub 호스티드 러너 | (배포 없음) | (배포 없음) | **모든 프로젝트의 출발점** |
| B. Actions + 레지스트리 + SSH | 호스티드 러너 | GHCR·Docker Hub | 러너가 ssh로 들어가 스크립트 실행(push 방식) | VM·서버 한두 대, 개인·스타트업 프로젝트 |
| C. 셀프 호스티드 러너 | 운영 서버(또는 사내 서버)에 깐 러너 | 같은 컴퓨터라 필요 없음 | 러너가 그 자리에서 실행 | 바깥에서 ssh로 못 들어가는 사내망 서버 |
| D. Jenkins | 직접 띄운 Jenkins 서버와 에이전트 | 사설 레지스트리·Nexus | ssh, 스크립트, 무엇이든 | 회사 안 설치형, 오래된 시스템, 복잡한 절차 |
| E. GitLab CI | GitLab 러너 | GitLab 레지스트리 | ssh, k8s 등 | 코드를 GitLab에 두는 팀 |
| F. 클라우드 관리형 | 호스티드 러너 + OIDC | ECR 등 클라우드 레지스트리 | 클라우드 API(ECS, Cloud Run 등) | AWS·GCP·Azure에서 운영 |
| G. GitOps(Argo CD) | CI는 아무 도구, 배포는 클러스터 안 Argo CD | 레지스트리 | 클러스터가 Git을 보고 스스로 맞춤(pull 방식) | 쿠버네티스 |

### 3.13 고르는 질문

1. **코드를 어디에 두나?** GitHub이면 Actions, GitLab이면 GitLab CI가 가장 자연스럽다. 둘 다 아니거나 사내 규정이 있으면 Jenkins.
2. **어디에 배포하나?** 서버(VM) → B 또는 C. 클라우드 관리형 서비스 → F. 쿠버네티스 → G.
3. **바깥(GitHub)에서 서버로 들어갈 수 있나?** 공인 IP와 ssh 포트가 열려 있으면 B. 사내망 안이라 못 들어오면 C(서버가 GitHub으로 나가서 일을 받아 옴) 또는 사내 Jenkins.
4. **운영 배포 전에 사람이 승인해야 하나?** Actions Environments의 Required reviewers, Jenkins `input`, GitLab `when: manual`로 넣는다.

### 3.14 push 방식과 pull 방식

- **push 방식**(B, D, E, F): CI가 운영 환경에 접속할 권한(ssh 키, 클라우드 권한)을 갖고 밀어 넣는다. 이해하기 쉽다. 대신 CI가 털리면 운영도 털린다.
- **pull 방식**(C 일부, G): 운영 쪽이 정해진 곳(Git 저장소, GitHub)을 보다가 스스로 가져간다. CI가 운영 접속 정보를 갖지 않는다. 설정이 조금 더 복잡하다.

## 4. 동작 원리

### 한 번의 PR이 지나가는 길

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

이제 이 흐름을 방법별로 실제 설정 파일에 옮겨 본다. 4.0~4.7의 예시 이름은 모두 가짜다. `owner/app`, `example.com`, `deploy` 계정은 자기 것으로 바꿔 읽는다.

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

클라우드에서는 서버에 ssh로 들어가지 않고 **클라우드 API로 "이 이미지로 바꿔"** 라고 요청한다. 권한은 OIDC로 받는다(위 3.10). 예는 AWS ECS(Fargate)다. GCP Cloud Run, Azure Container Apps도 모양이 같다.

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

이 프로젝트(GitHub에 코드, 학교 서버 한 대, Docker로 띄움, 바깥에서 ssh로 들어갈 수 있음)는 **방법 A + 방법 B**가 맞는다. 지금은 B와 비슷하지만 레지스트리 대신 파일 복사를 쓰고, A(PR 테스트)가 없다. 공개 저장소라 방법 C(셀프 호스티드 러너)는 쓰지 않는 것이 맞다. 아래 5.1~5.8은 지금 설정 읽기, 5.9부터는 무엇을 어떤 순서로 바꾸면 되는지다. (기준 시점과 2026-10-15에 바뀐 점은 문서 맨 위 안내를 본다.)

### 5.1 지금 한눈에

2026-10-14 기준 요약이다.

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

### 5.2 저장소가 둘이다

| 저장소 | 역할 | 워크플로에서 도는 것 |
| --- | --- | --- |
| `blog-hjiwon203/now-log` | 본 저장소. 여기서 배포한다 | test + deploy |
| `AIP-1/blog-basic-AIGJ_01_017-blog` | 과제 제출용 사본 | test만 (`if: github.repository == ...`로 deploy를 막음) |

같은 워크플로 파일이 두 저장소에 다 있어도, deploy 잡의 `if`가 저장소 이름을 확인해 본 저장소에서만 서버를 건드린다. 포크한 사람이 실수로 배포를 시도하는 것도 같은 줄이 막는다.

### 5.3 `deploy.yml` 읽기

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

### 5.4 `deploy.sh`가 하는 일

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

### 5.5 `Dockerfile`이 하는 일

세 단계 빌드다. 그래서 **프론트엔드 빌드 오류도 deploy 잡의 `docker build`에서야 드러난다**(test 잡은 백엔드 테스트만 한다).

1. `node:24-alpine`: `npm ci`, `npm run build`
2. `eclipse-temurin:21-jdk`: 의존성 내려받기 → 1의 결과를 `static`에 복사 → `package -DskipTests`(테스트는 test 잡에서 이미 했으니 건너뜀)
3. `eclipse-temurin:21-jre`: jar만 담은 작은 실행 이미지, `prod` 프로필, 한국 시간

### 5.6 잘된 점

- 테스트를 통과해야만 배포된다(`needs: test`)
- 배포가 겹치지 않는다(`concurrency`)
- 비밀값이 저장소에 없고, 서버 명령줄(`ps`)에도 안 보인다(`-e 이름`, psql 변수)
- 서버에서 할 일이 스크립트 하나에 있어 읽고 고치기 쉽다
- 앱이 안 뜨면 잡이 빨갛게 끝나고 로그가 Actions 화면에 남는다
- 공용 서버를 배려한다(`aigj017-` 이름, `docker image prune` 안 씀, Ollama CPU·메모리 제한)

### 5.7 빈 곳

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

### 5.8 비밀값이 서버까지 가는 길

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

### 5.9 고치는 순서

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

를 해도 되고, 위 4.2처럼 `workflow_dispatch`에 `tag` 입력을 받게 하면 버튼으로 할 수 있다.

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

그래서 컬럼 삭제·이름 변경은 위 3.9의 **늘리기 → 옮기기 → 줄이기**로 나눠 배포한다. 새 컬럼은 처음에 NULL 허용(또는 기본값)으로 추가하는 [Flyway 마이그레이션](../2-데이터/02-Flyway-마이그레이션.md)의 순서가 그대로 되돌리기 안전장치가 된다.

## 6. 자주 하는 실수와 함정

### 6.1 개념에서

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

### 6.2 도구를 설정할 때

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

### 6.3 이 프로젝트를 고칠 때

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

### 7.1 지금 파이프라인 들여다보기

1. GitHub에서 now-log 저장소의 **Actions** 탭을 열고 최근 `deploy` 실행 하나를 눌러 본다. `test`와 `deploy` 잡이 어떤 순서로 돌았는지, 각 스텝이 몇 초 걸렸는지 본다.
2. `deploy` 잡의 "서버에서 실행" 스텝 로그에서 비밀값이 `***`로 가려졌는지 확인한다.
3. **Settings → Branches**(또는 Rules)에서 main에 보호 규칙이 있는지 본다. 없다면 5장의 1단계를 먼저 하고 다시 와서 "Require status checks"에 지정해 본다(`test`가 아니라 1단계의 `backend`·`frontend`. 6.3 첫 줄).
4. 일부러 테스트 하나를 깨뜨린 PR을 올려 PR 화면에 빨간 X가 뜨고 병합 버튼이 막히는지 본다(병합하지 말고 닫는다).

### 7.2 연습용 저장소에서 방법 익히기

연습용 저장소(빈 Spring Boot 프로젝트 하나)를 만들어 해 본다. 운영 서버를 건드리지 않는다.

5. **방법 A**: 4.1의 `ci.yml`을 넣고 PR을 올려 Checks 탭에 `backend`가 초록으로 뜨는지 본다. 테스트를 일부러 깨뜨려 빨간 X를 본 뒤, 브랜치 보호에 필수 검사로 지정하고 병합 버튼이 막히는지 확인한다.
6. **GHCR까지만**: 4.2의 `build` 잡만 넣고 main에 병합한다. 내 GitHub 프로필의 Packages에 이미지가 생기고, 태그에 커밋 SHA가 붙었는지 본다. 노트북에서 `docker pull ghcr.io/<나>/<저장소>:<SHA>`로 받아 본다.
7. **배포 연습**: 서버 대신 노트북에서 4.0의 `deploy.sh`를 돌려 본다(`TAG=<SHA> bash deploy.sh`). 이어서 일부러 안 뜨는 이미지 태그(예: 잘못된 환경 변수로 실패하는 버전)를 넣어 되돌리기가 동작하는지 본다.
8. **Jenkins 맛보기**: 4.4의 명령으로 노트북에 Jenkins를 띄우고 Pipeline 잡에 `pipeline { agent any; stages { stage('hi') { steps { sh 'echo hello' } } } }`를 넣어 돌려 본다. 화면의 Stage View가 Actions의 잡 화면과 어떻게 대응되는지 비교한다.

### 7.3 now-log에 적용하며

9. now-log Actions 탭에서 가장 최근 `deploy` 실행을 열어 5.3 표의 각 줄이 어느 스텝에 해당하는지 짝지어 본다. "서버에서 실행" 스텝 로그 끝의 `배포 완료` 줄을 찾는다.
10. 학교 서버에서 `docker images aigj017/now-log`를 쳐서 이미지가 몇 개 남아 있는지 본다(지금은 1개일 것이다. 5단계 뒤에는 최대 3개).
11. 1단계 `ci.yml`을 PR로 올려 Checks 탭에 두 잡이 뜨는 것을 본다. 이어서 2단계 브랜치 보호를 켠다.
12. 3단계의 `ssh-keyscan ... | ssh-keygen -lf -`로 서버 지문을 확인하고, 처음 ssh로 접속할 때 나왔던 지문과 같은지 비교한다.

## 8. 확인 문제

1. 지속적 전달과 지속적 배포의 차이를 한 문장으로 말해 보자. 이 프로젝트는 어느 쪽인가?
<details><summary>답 보기</summary>운영 배포 직전에 사람이 승인하면 지속적 전달, 테스트를 통과하면 바로 운영에 나가면 지속적 배포다. 이 프로젝트는 main 병합 즉시 운영으로 나가므로 지속적 배포다.</details>

2. test 잡에서 `target/app.jar`를 만들었는데 deploy 잡에서 그 파일이 없다고 나온다. 왜인가?
<details><summary>답 보기</summary>잡마다 다른 러너(컴퓨터)에서 돌기 때문이다. 산출물로 올렸다 내려받거나(`actions/upload-artifact`·`download-artifact`), deploy 잡에서 다시 만들거나, 이미지를 레지스트리에 올려 넘겨야 한다.</details>

3. 왜 이미지에 커밋 SHA 태그를 붙이는가? 두 가지 이유를 말해 보자.
<details><summary>답 보기</summary>① 지금 서버에 떠 있는 게 어느 커밋인지 알 수 있다. ② 이전 버전 이미지가 이름을 가진 채 남아 있어 그 태그로 바로 되돌릴 수 있다.</details>

4. `user.nickname` 컬럼을 `display_name`으로 바꾸고 싶다. 한 번의 배포로 이름을 바꾸면 되돌리기가 왜 위험하고, 어떻게 나누면 되는가?
<details><summary>답 보기</summary>이름을 바꾼 뒤 코드를 이전 이미지로 되돌리면 옛 코드는 `nickname`을 찾다가 실패한다. ① `display_name` 추가(옛 코드는 무시) ② 새 코드가 두 컬럼에 쓰고 `display_name`을 읽으며 데이터 채움 ③ 옛 코드가 돌아올 일이 없을 때 `nickname` 삭제, 세 번으로 나눈다.</details>

5. 공개 저장소에 낯선 사람이 포크해서 PR을 보냈다. 이 PR의 CI에서 `secrets.SSH_PASSWORD`는 무슨 값인가? 왜 그렇게 설계됐나?
<details><summary>답 보기</summary>빈 값이다. 포크 PR은 남이 쓴 코드를 내 러너에서 실행하는 것이므로, 비밀값을 넘기면 그 코드가 비밀값을 밖으로 보낼 수 있기 때문이다.</details>

6. OIDC를 쓰면 GitHub Secrets에 무엇을 넣지 않아도 되나?
<details><summary>답 보기</summary>오래 사는 클라우드 접근 키(AWS Access Key 등). GitHub이 실행마다 발급하는 짧은 토큰을 클라우드가 믿고 몇 분짜리 임시 권한을 준다.</details>

7. 사내망 안에 있어 바깥에서 ssh로 들어갈 수 없는 서버에 GitHub 코드로 배포하고 싶다. 어떤 방법들이 있나?
<details><summary>답 보기</summary>그 서버(또는 같은 사내망의 빌드 서버)에 셀프 호스티드 러너를 깔아 러너가 GitHub으로 나가서 일을 받아 오게 하거나(방법 C), 사내 Jenkins가 webhook 대신 주기적으로 저장소를 확인하게 하거나(방법 D), 서버가 레지스트리를 주기적으로 보고 새 이미지를 당겨 오게(pull 방식) 한다.</details>

8. 4.2에서 `docker/login-action`의 비밀번호로 쓴 `secrets.GITHUB_TOKEN`은 누가 만들었나? 따로 등록해야 하나?
<details><summary>답 보기</summary>GitHub이 워크플로 실행마다 자동으로 만들어 주는 토큰이라 등록할 필요가 없다. 권한은 `permissions:`로 정하고(여기서는 `packages: write`), 실행이 끝나면 만료된다.</details>

9. Jenkinsfile에서 `sh "docker login -p ${REG_PASS}"`처럼 큰따옴표를 쓰면 왜 안 좋은가?
<details><summary>답 보기</summary>Groovy가 셸보다 먼저 문자열 안의 비밀값을 풀어 넣기 때문에 비밀값이 Groovy 쪽 문자열과 명령줄(ps로 보임)에 들어간다. 작은따옴표로 셸이 환경 변수를 풀게 하고, 비밀번호는 `--password-stdin`으로 넘긴다.</details>

10. 방법 B(push 방식)와 방법 G(GitOps, pull 방식)에서 CI가 털렸을 때 공격자가 얻는 것은 각각 무엇인가?
<details><summary>답 보기</summary>B는 CI가 운영 서버 ssh 키(와 경우에 따라 운영 비밀값)를 갖고 있으므로 운영 서버에 바로 들어갈 수 있다. G는 CI가 매니페스트 저장소 쓰기 권한만 가지므로 공격자는 커밋을 남겨야 하고(기록이 남고 PR 승인을 걸 수 있음), 클러스터 자격 증명은 얻지 못한다.</details>

11. OIDC 신뢰 정책에서 `sub`를 `repo:owner/app:environment:production`으로 묶었다. 같은 저장소의 기능 브랜치 워크플로가 이 역할을 쓰려 하면?
<details><summary>답 보기</summary>거부된다. 그 워크플로의 토큰 `sub`는 `repo:owner/app:ref:refs/heads/기능브랜치`(또는 다른 환경)라 조건과 맞지 않는다. production 환경(배포 브랜치를 main으로 제한)을 거친 잡만 받는다.</details>

12. 지금 설정에서 프론트엔드에 문법 오류가 있는 PR을 병합하면 어디서, 언제 알게 되나? 1단계 뒤에는?
<details><summary>답 보기</summary>지금은 main 병합 뒤 deploy 잡의 `docker build`(Dockerfile 1단계 `npm run build`)에서 처음 실패한다. 이미 main에 들어간 뒤다. 1단계 뒤에는 PR의 `ci / frontend`에서 실패해 병합 전에 안다(2단계를 하면 병합도 막힌다).</details>

13. `ssh-action`의 `env:`에 `JWT_SECRET`을 넣었는데 `envs:`에 적는 것을 빼먹었다. 무슨 일이 생기나?
<details><summary>답 보기</summary>러너에는 값이 있지만 ssh 너머 서버 셸로 넘어가지 않아, `deploy.sh`의 필수 값 확인에서 "JWT_SECRET 이 비어 있습니다"로 실패한다.</details>

14. 5단계 뒤, 새 버전이 Redis 비밀번호 오류로 뜨지 않았다. `deploy.sh`는 무엇을 하고 Actions 화면은 무슨 색이 되나?
<details><summary>답 보기</summary>`wait_app`이 실패하면 로그 80줄을 찍고, 직전 이미지(`prev_image`)로 앱을 다시 띄워 뜨는지 확인한 뒤 `exit 1`로 끝낸다. 블로그는 옛 버전으로 계속 돌고, Actions는 빨갛게 표시된다.</details>

15. 새 버전에서 `post.summary` 컬럼을 추가(NULL 허용)했다가 배포가 실패해 옛 이미지로 되돌렸다. 옛 앱은 뜨나?
<details><summary>답 보기</summary>뜬다. 옛 엔티티에 없는 컬럼이 DB에 더 있는 것은 `ddl-auto: validate`가 문제 삼지 않고, NULL 허용이라 옛 앱의 INSERT도 된다. Flyway는 옛 앱이 모르는 새 버전 기록을 기본으로 무시한다.</details>

16. 4단계에서 Required reviewers를 켜면 이 프로젝트의 CD는 3.2의 두 가지 뜻 중 무엇이 되나?
<details><summary>답 보기</summary>지속적 전달(Continuous Delivery). 운영 배포 직전에 사람이 승인 버튼을 눌러야 나가기 때문이다.</details>

## 9. 더 읽을거리

- GitHub Docs: "Understanding GitHub Actions", "Using environments for deployment"(또는 "Managing environments for deployment")
- GitHub Docs: "About protected branches", "About rulesets", "Managing rulesets for a repository"
- GitHub Docs: "Security hardening for GitHub Actions"(외부 Action 고정, `pull_request_target` 주의), "About self-hosted runners"(보안 항목)
- GitHub Docs: "About security hardening with OpenID Connect", "Configuring OpenID Connect in Amazon Web Services"
- GitHub Docs: "Building and testing Java with Maven", "Publishing Docker images", "Working with the Container registry"(패키지 공개 설정)
- docker/build-push-action README의 "Cache management"(type=gha)
- appleboy/ssh-action, appleboy/scp-action README: `key`, `fingerprint`, `envs`
- Jenkins 문서: "Pipeline Syntax", "Using credentials", "Branches and Pull Requests"(Multibranch)
- GitLab 문서: "Get started with GitLab CI/CD", "Use Docker to build Docker images", "Environments and deployments", "CI/CD variables"
- Testcontainers 문서: "Continuous Integration"(GitLab dind 설정)
- AWS 문서: "Deploying to Amazon ECS with GitHub Actions", ECS "deployment circuit breaker"
- Argo CD 문서: "Getting Started", "Automated Sync Policy"; OpenGitOps 원칙
- Martin Fowler, "Continuous Integration", "BlueGreenDeployment", "CanaryRelease"
- The Twelve-Factor App, "V. Build, release, run", "III. Config"
- Spring Boot 문서: "Actuator: Endpoints"(health, exposure, show-details)
- Flyway 문서: `ignoreMigrationPatterns`(future 마이그레이션 무시 기본값)
- now-log 저장소: `.github/workflows/deploy.yml`, `deploy/deploy.sh`, `Dockerfile`(주석에 이유가 적혀 있다)
- [서버와 Docker](./03-Docker와-서버.md): 어느 컨테이너가 어느 컴퓨터에 있는지
