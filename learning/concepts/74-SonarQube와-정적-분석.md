# 74. SonarQube와 정적 분석: 코드 품질을 숫자로 보기

> 관련 개념: [05-Spring-테스트](./05-Spring-테스트.md)(테스트), [69-CI-CD-개념](./69-CI-CD-개념.md), [71-CI-CD-우리-프로젝트-적용](./71-CI-CD-우리-프로젝트-적용.md)(워크플로)

> **한 줄 답**: SonarQube는 코드를 **실행하지 않고 읽어서** 버그가 될 만한 곳, 보안 위험, 읽기 어려운 코드를 찾아 주는 서버다. 테스트 커버리지는 스스로 재지 않고, **JaCoCo(자바)·Vitest(프론트)가 만든 보고서 파일을 읽어서** 보여 준다. now-log는 main에 병합될 때마다 GitHub Actions가 테스트를 돌리고, 결과를 기관 SonarQube(`s4.java21.net:9000`)로 보낸다.

이 문서는 2026-10-16 `sonar-connect` 브랜치(`pom.xml`, `frontend/vite.config.ts`, `.github/workflows/sonar.yml`)를 기준으로 썼다.

## 1. 이 문서로 배우는 것

- 정적 분석과 동적 분석(테스트)의 차이
- SonarQube의 구성: 스캐너, 서버, Compute Engine
- 이슈의 종류, 품질 프로필(Quality Profile), 품질 게이트(Quality Gate)
- "새 코드(New Code)"라는 생각과 기준(Previous version, Number of days)
- 커버리지가 재어지는 원리: JaCoCo 에이전트, V8 커버리지, `jacoco.xml`과 `lcov.info`
- now-log의 설정을 줄마다 읽기, `@{argLine}`이 필요한 이유

## 2. 왜 필요한가

테스트는 "내가 확인하려고 적은 경우"만 확인한다. 이런 것은 테스트로 잡기 어렵다.

- `equals`를 고쳤는데 `hashCode`는 안 고쳤다
- `Optional.get()`을 확인 없이 부른다
- 같은 30줄이 세 파일에 복사돼 있어서 한 곳만 고쳐진다
- 비밀번호 같은 값이 코드에 문자열로 박혀 있다
- 테스트가 400개인데, 사실 어떤 패키지는 한 줄도 실행되지 않는다

사람이 리뷰로 매번 찾기에는 너무 많다. 정적 분석 도구는 수천 개의 규칙으로 코드 전체를 매번 똑같이 훑는다. 사람은 도구가 못 보는 것(설계, 명세와 맞는지)에 집중할 수 있다.

## 3. 기본 개념

### 3.1 정적 분석 vs 동적 분석

| | 정적 분석 | 동적 분석 |
| --- | --- | --- |
| 방법 | 코드를 실행하지 않고 읽는다(구문 트리, 데이터 흐름) | 실제로 실행한다 |
| 예 | SonarQube, IntelliJ 검사, oxlint, SpotBugs | 단위·통합 테스트, 부하 테스트 |
| 잘 찾는 것 | 패턴으로 보이는 실수, 복잡도, 중복, 위험한 API 사용 | 결과가 맞는지, 실제 DB·Redis와 맞물리는지 |
| 못 찾는 것 | 요구사항과 맞는지 | 테스트하지 않은 경우 |

둘은 서로를 대신하지 않는다. 커버리지는 둘을 잇는 숫자다. "테스트(동적)가 코드(정적)의 어디까지 닿았나"를 보여 준다.

### 3.2 SonarQube의 구성

```
 내 컴퓨터 / GitHub Actions                      SonarQube 서버 (s4.java21.net:9000)
┌──────────────────────────────┐   보고서 업로드   ┌───────────────────────────────┐
│ 스캐너 (sonar-maven-plugin)    │ ───────────────▶ │ Compute Engine: 보고서 처리      │
│ - 소스 읽기, 규칙으로 분석      │   토큰으로 인증    │ DB: 결과 저장                    │
│ - jacoco.xml, lcov.info 읽기   │                  │ 웹 화면: 대시보드, 이슈, 게이트   │
└──────────────────────────────┘                  └───────────────────────────────┘
```

- **분석은 스캐너 쪽(우리 컴퓨터나 GitHub Actions 러너)에서 한다.** 서버는 결과를 받아 저장하고 보여 준다. 그래서 스캐너가 소스와 보고서 파일에 접근할 수 있어야 한다.
- 스캐너가 업로드를 끝내도 화면에 바로 나오지 않는다. 서버의 Compute Engine이 백그라운드에서 처리한 뒤에 보인다(보통 몇 초~몇십 초).
- 스캐너는 서버에서 규칙(품질 프로필)과 설정을 받아 온다. 어떤 규칙을 쓸지는 서버가 정한다.

### 3.3 이슈와 보안 핫스팟

SonarQube가 찾은 문제 하나하나를 **이슈**라고 한다. 이슈는 소프트웨어 품질 중 어디에 영향을 주는지로 나눈다.

| 품질 | 뜻 | 예전 이름 |
| --- | --- | --- |
| Reliability(신뢰성) | 잘못 동작할 수 있다 | Bug |
| Security(보안) | 공격에 쓰일 수 있다 | Vulnerability |
| Maintainability(유지보수성) | 동작은 하지만 고치기 어렵다 | Code Smell |

이슈마다 심각도(Blocker, High, Medium, Low, Info)가 붙는다.

**보안 핫스팟(Security Hotspot)**은 이슈와 다르다. "여기는 보안에 민감한 코드니 사람이 보고 괜찮은지 판단해 달라"는 표시다. 예를 들어 CSRF 보호를 끄는 설정, 쿠키 설정 같은 곳이다. 확인하고 Safe/Fixed로 표시하면 된다. 문제라고 단정하는 것이 아니다.

### 3.4 품질 프로필과 품질 게이트

- **품질 프로필(Quality Profile)**: 언어별로 **어떤 규칙을 켤지**의 목록이다. 기본은 "Sonar way"다.
- **품질 게이트(Quality Gate)**: 분석 결과가 **통과인지 실패인지** 정하는 조건 묶음이다. 기본 "Sonar way" 게이트는 **새 코드**에 대해 대략 이렇게 묻는다.
  - 새 이슈가 없는가
  - 새 보안 핫스팟을 모두 검토했는가
  - 새 코드 커버리지가 80% 이상인가
  - 새 코드의 중복 줄이 3% 이하인가

게이트가 "전체 코드"가 아니라 "새 코드"를 보는 것이 핵심이다. 오래된 프로젝트에 처음 붙이면 옛 이슈가 수백 개 나온다. 그걸 다 고치기 전까지 매번 실패하면 아무도 안 본다. 그래서 **"앞으로 쓰는 코드만큼은 깨끗하게"**(Clean as You Code)를 기본으로 한다.

### 3.5 새 코드(New Code)의 기준

"새 코드"가 어디부터인지는 프로젝트마다 정한다. 처음 프로젝트를 만들 때 묻는 "choose the baseline for new code"가 이것이다.

| 기준 | 새 코드 | 어울리는 경우 |
| --- | --- | --- |
| Previous version | 프로젝트 버전(`pom.xml`의 `<version>`)이 바뀐 뒤 바뀐 코드 | 릴리스마다 버전을 올리는 프로젝트 |
| Number of days | 최근 N일 동안 바뀐 코드 | 버전 없이 계속 배포하는 프로젝트 |
| Reference branch | 기준 브랜치와 다른 코드 | 브랜치 분석이 되는 판(Developer 이상) |

now-log는 **Previous version**을 골랐다(2026-10-16). 그런데 지금 `pom.xml`의 버전은 `0.0.1-SNAPSHOT`에서 바뀐 적이 없다. 그래서 첫 분석 뒤 바뀐 모든 코드가 계속 "새 코드"로 쌓인다. 릴리스를 시작할 때 `<version>`을 `0.1.0`, `0.2.0`… 으로 올리면, 그때부터 "이번 릴리스에서 바뀐 코드"가 새 코드가 된다.

"바뀐 코드"는 git 기록(blame)으로 판단한다. 그래서 CI에서 저장소를 얕게(최근 커밋 하나만) 받으면 모든 줄이 방금 바뀐 것처럼 보인다. `fetch-depth: 0`이 필요한 이유다(5.3).

### 3.6 Community Build의 한계

기관 서버는 **SonarQube Community Build 25.1**이다(`/api/server/version`으로 확인). 무료판이라 **브랜치·PR별 분석이 없다.** 프로젝트 하나에 결과가 한 줄로만 쌓인다. 그래서 PR 브랜치를 분석하면 main의 결과를 덮어쓴다. now-log는 **main에 병합된 뒤에만** 분석한다.

## 4. 동작 원리: 커버리지는 어떻게 재는가

SonarQube는 테스트를 돌리지 않는다. **커버리지 보고서 파일을 읽기만 한다.** 보고서는 언어마다 다른 도구가 만든다.

### 4.1 JaCoCo (자바)

1. `prepare-agent` 골이 Maven 속성 `argLine`에 `-javaagent:.../jacocoagent.jar=destfile=target/jacoco.exec` 같은 값을 넣는다.
2. surefire가 테스트용 JVM을 띄울 때 그 `argLine`을 붙인다. 에이전트는 클래스가 메모리에 올라올 때 바이트코드에 "이 줄 지나감" 표시(probe)를 끼워 넣는다. 소스나 `.class` 파일은 바뀌지 않는다.
3. 테스트가 끝나면 지나간 표시를 `target/jacoco.exec`(바이너리)에 쓴다.
4. `report` 골이 `jacoco.exec`와 컴파일된 클래스를 맞춰 `target/site/jacoco/jacoco.xml`(SonarQube용)과 HTML 보고서를 만든다.

```
./mvnw verify
  test 단계:   prepare-agent → argLine 설정 → surefire가 JVM에 에이전트 붙여 테스트 → jacoco.exec
  verify 단계: report → jacoco.xml, index.html
```

### 4.2 V8 커버리지 (프론트)

Vitest는 Node.js의 JavaScript 엔진(V8)이 원래 갖고 있는 커버리지 기능을 켠다(`@vitest/coverage-v8`). 코드를 바꿔 끼우지 않고 엔진이 "어느 함수·블록이 실행됐는지"를 센다. 결과를 **lcov** 형식으로 쓴다.

```
SF:src/app/host.ts     ← 파일 (Source File)
DA:12,3                ← 12번 줄이 3번 실행됨
DA:13,0                ← 13번 줄은 실행 안 됨
end_of_record
```

### 4.3 경로가 맞아야 한다

SonarQube는 보고서 안의 파일 경로를 자기가 분석한 소스 파일과 맞춰 본다. 경로가 다르면 커버리지가 0%로 나온다. 오류도 나지 않는다. Vitest는 `frontend/`에서 돌기 때문에 `SF:src/app/host.ts`라고 쓰는데, 스캐너는 저장소 루트에서 `frontend/src/app/host.ts`로 안다. 그래서 워크플로에서 앞에 `frontend/`를 붙인다(5.3).

## 5. 이 프로젝트에서는

### 5.1 `pom.xml`: 속성

```xml
<jacoco.version>0.8.15</jacoco.version>
<!-- JaCoCo가 채운다. 채우지 않을 때(jacoco.skip)도 surefire의 @{argLine}이 깨지지 않게 빈 값을 둔다 -->
<argLine></argLine>
<sonar-maven-plugin.version>5.8.0.7211</sonar-maven-plugin.version>

<sonar.projectKey>now-log</sonar.projectKey>
<sonar.projectName>now-log</sonar.projectName>
<sonar.sources>pom.xml,src/main/java,src/main/resources,frontend/src</sonar.sources>
<sonar.tests>src/test/java,frontend/src</sonar.tests>
<sonar.test.inclusions>src/test/java/**,frontend/src/**/*.test.ts,frontend/src/**/*.test.tsx</sonar.test.inclusions>
<sonar.exclusions>src/main/resources/static/**,frontend/src/**/*.test.ts,frontend/src/**/*.test.tsx</sonar.exclusions>
<sonar.coverage.jacoco.xmlReportPaths>${project.build.directory}/site/jacoco/jacoco.xml</sonar.coverage.jacoco.xmlReportPaths>
<sonar.javascript.lcov.reportPaths>frontend/coverage/lcov.info</sonar.javascript.lcov.reportPaths>
```

- `<argLine></argLine>`: 기본값을 빈 값으로 둔다. 아래 `@{argLine}`이 JaCoCo를 건너뛴 실행(`-Djacoco.skip=true`)에서도 깨지지 않게 한다.
- `sonar.projectKey`: 서버에 만든 프로젝트의 키와 같아야 한다. 다르면 스캐너가 새 프로젝트를 만들려고 하고, 권한이 없으면 실패한다.
- `sonar.sources`: Maven 스캐너는 기본으로 `src/main/java`와 `pom.xml`만 본다. 프론트도 같이 보려고 `frontend/src`를 더했다. `src/main/resources`를 넣어야 `application.yml`, SQL 파일의 문제(비밀값 하드코딩 등)도 본다.
- `sonar.tests` + `sonar.test.inclusions`: 프론트는 테스트 파일(`*.test.ts`)이 소스 옆에 있다. 같은 폴더를 소스와 테스트 양쪽에 넣고, 테스트 쪽은 `*.test.ts`만 고르게 한다.
- `sonar.exclusions`: 반대로 소스 쪽에서는 `*.test.ts`를 뺀다. 한 파일이 소스와 테스트 양쪽에 잡히면 분석이 실패한다. `src/main/resources/static/**`은 프론트 빌드 결과(압축된 JS)라 뺀다. git에도 없다.
- 마지막 두 줄: 커버리지 보고서 위치. 4장의 두 도구가 만든 파일이다.

### 5.2 `pom.xml`: 플러그인

```xml
<plugin>
    <groupId>org.apache.maven.plugins</groupId>
    <artifactId>maven-surefire-plugin</artifactId>
    <configuration>
        <!-- @{argLine}: JaCoCo가 앞에서 넣은 커버리지 에이전트 설정을 이어 붙인다 -->
        <argLine>@{argLine} -Duser.timezone=Asia/Seoul</argLine>
    </configuration>
</plugin>
<plugin>
    <groupId>org.jacoco</groupId>
    <artifactId>jacoco-maven-plugin</artifactId>
    <version>${jacoco.version}</version>
    <executions>
        <execution>
            <goals><goal>prepare-agent</goal></goals>
        </execution>
        <execution>
            <id>report</id>
            <phase>verify</phase>
            <goals><goal>report</goal></goals>
        </execution>
    </executions>
</plugin>
```

`@{argLine}`이 이 설정의 함정이다. 원래 surefire 설정은 `<argLine>-Duser.timezone=Asia/Seoul</argLine>`이었다. 이렇게 **직접 값을 적으면 JaCoCo가 `argLine` 속성에 넣은 에이전트 설정을 덮어쓴다.** 그러면 테스트는 통과하는데 `jacoco.exec`가 생기지 않고, 커버리지는 0%가 된다.

- `${argLine}`: pom을 읽는 순간 바꾼다. 그때는 JaCoCo가 아직 값을 넣기 전이라 빈 값이다.
- `@{argLine}`: surefire가 실행되는 순간 바꾼다(늦은 치환). 그때는 `prepare-agent`가 이미 값을 넣어 두었다.

`prepare-agent`는 phase를 적지 않았다. 기본 phase가 `initialize`라 테스트보다 먼저 돈다.

### 5.3 `.github/workflows/sonar.yml`

```yaml
on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  analyze:
    if: github.repository == 'blog-hjiwon203/now-log'
    steps:
      - uses: actions/checkout@v5
        with:
          fetch-depth: 0
      ...
      - name: 프론트 테스트 + 커버리지
        working-directory: frontend
        run: |
          npm ci
          npm run test -- --coverage
          sed -i 's#^SF:#SF:frontend/#' coverage/lcov.info

      - name: 백엔드 테스트 + SonarQube 분석
        env:
          SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
          SONAR_HOST_URL: ${{ secrets.SONAR_HOST_URL }}
        run: ./mvnw -B verify sonar:sonar
```

| 줄 | 뜻 |
| --- | --- |
| `on: push: branches: [main]` | Community Build라 main만 분석한다(3.6) |
| `if: github.repository == ...` | 제출용 원본 저장소에는 토큰이 없다. 거기서는 돌지 않게 한다 |
| `fetch-depth: 0` | git 기록 전체를 받는다. 새 코드 판단(blame)에 필요하다(3.5) |
| `npm run test -- --coverage` | `--` 뒤의 인자는 npm이 아니라 `vitest run`에 넘어간다 |
| `sed ... SF:frontend/` | lcov 경로를 저장소 루트 기준으로 바꾼다(4.3) |
| `SONAR_TOKEN`, `SONAR_HOST_URL` | 스캐너가 이 이름의 환경 변수를 읽는다. pom에 적지 않으니 토큰이 코드에 남지 않는다 |
| `./mvnw -B verify sonar:sonar` | `verify`까지 돌아야 테스트, `jacoco.xml`이 먼저 생긴다. 그다음 `sonar:sonar`가 분석해서 올린다 |

배포(`deploy.yml`)와 다른 파일로 둔 이유: SonarQube 서버가 꺼져 있거나 토큰이 만료돼도 **배포는 막히지 않아야** 한다. 같은 잡에 넣으면 분석 실패가 배포 실패가 된다.

### 5.4 `frontend/vite.config.ts`

```ts
test: {
  environment: 'node',
  coverage: {
    provider: 'v8',
    reporter: ['text-summary', 'lcov'],
    include: ['src/**/*.{ts,tsx}'],
  },
},
```

- `provider: 'v8'`: 4.2의 방식. `@vitest/coverage-v8` 패키지가 필요하다. 버전은 `vitest`와 같게 맞춘다.
- `reporter`: `text-summary`는 터미널에 요약, `lcov`는 `coverage/lcov.info`와 HTML 보고서.
- `include`: 테스트가 한 번도 불러오지 않은 파일도 0%로 센다. 이게 없으면 테스트가 닿은 파일만 세서 커버리지가 실제보다 높아 보인다.

### 5.5 처음 잰 숫자 (2026-10-16)

| | 결과 |
| --- | --- |
| 백엔드 테스트 | 417개, 실패 0 |
| 백엔드 라인 커버리지 (JaCoCo) | 93.4% |
| 프론트 라인 커버리지 (V8) | 9.6% (화면 컴포넌트에 테스트가 거의 없음, 테스트는 `app/`, `api/`의 순수 함수 위주) |

프론트 숫자가 낮은 것이 이상한 것은 아니다. 지금까지 판단 로직을 순수 함수로 빼서 그것만 테스트했기 때문이다([46](./46-글쓰기-버튼-갈-곳-정하기.md)). 품질 게이트는 **새 코드**만 보므로, 앞으로 새로 쓰는 프론트 코드에 테스트를 붙이면 된다.

## 6. 자주 하는 실수와 함정

- **surefire `argLine`을 직접 써서 JaCoCo를 덮어쓰기** → 커버리지 0%, 오류 없음(5.2).
- **`mvn sonar:sonar`만 돌리기** → 테스트를 안 돌리니 `jacoco.xml`이 없다. 커버리지 0%. `verify`와 같이 돌린다.
- **보고서 경로 불일치** → 역시 0%, 오류 없음. 스캐너 로그에서 "Could not resolve N file paths" 같은 경고를 찾는다(4.3).
- **얕은 clone** → 모든 줄이 새 코드가 되거나, 스캐너가 "Shallow clone detected" 경고를 낸다.
- **토큰을 pom이나 워크플로에 직접 적기** → git 기록에 영원히 남는다. 반드시 Secrets로.
- **http 서버** → 기관 서버가 `http://`라 토큰이 암호화되지 않고 전송된다. 우리가 바꿀 수 없으니, 토큰은 분석 전용(권한이 좁은 것)으로 만들고 새어 나갔다 싶으면 바로 폐기한다.
- **커버리지 숫자를 목표로 삼기** → 아무것도 확인하지 않는 테스트로도 숫자는 오른다. 커버리지는 "여기는 테스트가 아예 안 닿았다"를 찾는 용도다.
- **이슈를 무조건 고치기** → 규칙이 틀린 경우도 있다. 이유가 있으면 화면에서 "Accept"(받아들임) 또는 "False Positive"로 표시하고 이유를 적는다.

## 7. 직접 해 보기

1. 백엔드 커버리지 보고서 열기
   ```bash
   ./mvnw verify
   open target/site/jacoco/index.html
   ```
   패키지 → 클래스 → 소스로 들어가면 줄마다 초록(실행됨)·빨강(안 됨)·노랑(분기 일부만)이 보인다.
2. `@{argLine}` 실험: `pom.xml`에서 `@{argLine} `을 지우고 `./mvnw verify`를 돌린다. `target/jacoco.exec`가 생기는지, 보고서가 어떻게 되는지 본다. 끝나면 `git restore pom.xml`.
3. 프론트 커버리지
   ```bash
   cd frontend && npm run test -- --coverage
   open coverage/index.html
   ```
4. SonarQube 화면에서: Issues 탭에서 심각도 High인 것 하나를 열어 규칙 설명("Why is this an issue?")을 읽는다. Security Hotspots 탭에서 하나를 검토해 본다.

## 8. 확인 문제

1. SonarQube 서버가 테스트를 돌리지 않는데 커버리지를 어떻게 아는가?
2. surefire에 `<argLine>-Xmx1g</argLine>`이라고 적었더니 커버리지가 0%가 됐다. 왜이고, 어떻게 고치나?
3. 기본 품질 게이트가 전체 코드가 아니라 새 코드만 보는 이유는?
4. now-log가 PR마다 분석하지 않고 main에서만 분석하는 이유는?
5. 프로젝트 기준을 Previous version으로 정했는데 `pom.xml` 버전을 계속 `0.0.1-SNAPSHOT`으로 두면 어떻게 되나?

<details>
<summary>답 보기</summary>

1. 스캐너가 JaCoCo의 `jacoco.xml`, Vitest의 `lcov.info`를 읽어 함께 올린다. 테스트와 보고서 생성은 CI(`./mvnw verify`, `npm run test -- --coverage`)가 한다.
2. 직접 적은 값이 JaCoCo가 넣은 `argLine` 속성(에이전트 설정)을 덮어써서 에이전트가 붙지 않았다. `<argLine>@{argLine} -Xmx1g</argLine>`처럼 늦은 치환으로 이어 붙인다.
3. 옛 이슈가 많은 프로젝트도 "앞으로 쓰는 코드"부터 깨끗하게 만들 수 있게. 전체를 보면 옛 이슈 때문에 게이트가 늘 실패하고 결국 아무도 안 본다.
4. 기관 서버가 Community Build라 브랜치·PR별 분석이 없다. PR 브랜치를 분석하면 main 결과를 덮어쓴다.
5. 버전이 바뀌지 않으니 첫 분석 이후 바뀐 모든 코드가 계속 새 코드로 쌓인다. 릴리스마다 버전을 올려야 "이번 릴리스의 새 코드"가 된다.

</details>

## 9. 더 읽을거리

- SonarQube 문서: https://docs.sonarsource.com/sonarqube-community-build/
- SonarScanner for Maven: https://docs.sonarsource.com/sonarqube-community-build/analyzing-source-code/scanners/sonarscanner-for-maven/
- JaCoCo Maven 플러그인 (`prepare-agent`, `report`): https://www.jacoco.org/jacoco/trunk/doc/maven.html
- Vitest 커버리지: https://vitest.dev/guide/coverage
