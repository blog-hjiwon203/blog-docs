# CLAUDE.md

> 이 파일은 코드 저장소 루트(`~/IdeaProjects/blog`)에 `CLAUDE.md`로 복사해 쓴다. 원본은 문서 저장소 blog-docs의 `specs/001-tistory-blog/code-repo-CLAUDE.md`다.

## 이 저장소

티스토리형 블로그(지원)의 구현 코드다. GitHub: AIP-1/blog-basic-AIGJ_01_017-blog

명세·계획·작업 목록은 별도 문서 저장소에 있다. 옆 폴더 `../blog-docs`에 클론되어 있고, Claude Code는 `claude --add-dir ../blog-docs`로 열어 읽는다.

- 작업 순서와 스텝: `../blog-docs/specs/001-tistory-blog/tasks.md`의 "구현 스텝과 검토 포인트"
- 기술 결정과 구조: `../blog-docs/specs/001-tistory-blog/plan.md`, `research.md`
- 동작 기준: `spec.md`(수용 시나리오), `contracts/rest-api.md`(API), `data-model.md`
- 테이블 기준: `erd/schema.sql` (Crowfoot에서 내보낸 MySQL DDL)
- 화면 기준: `mockups/*.html`
- 확인 시나리오: `quickstart.md`

문서 저장소는 평소에는 읽기만 한다. 명세와 다르게 만들어야 할 것 같으면 구현을 멈추고 지원에게 묻는다. 지원이 정하면 그 스텝 안에서 바로 문서 저장소의 해당 문서를 고친다(`docs/...` 브랜치, 코드 PR보다 먼저 병합). PR 본문에만 적고 끝내지 않는다.

## 일하는 방식

1. 지원이 "스텝 N 진행해"라고 하면 tasks.md 표에서 스텝 N에 적힌 작업(T번호)만 한다. 다음 스텝으로 넘어가지 않는다.
2. 시작 전에 `main`에서 `step-N-짧은이름` 브랜치를 만든다.
3. 작업마다 커밋하고, 커밋 메시지에 T번호와 기능 코드를 쓴다. 예: `feat(auth): 가입 API (T018, AUTH-01)`
4. 스텝이 끝나면 `./mvnw test`를 돌리고, 문서 저장소 `tasks.md`의 작업 목록에서 그 스텝에서 끝낸 T번호의 체크박스를 `[X]`로 바꾼다(명세 반영과 같은 `docs/...` 브랜치, 2026-10-09 지원 결정). 그리고 아래를 정리한 뒤 멈춘다.
   - 끝낸 T번호와 못 끝낸 것
   - 테스트 결과
   - 바뀐 파일 목록
   - 만든 API와, contracts/rest-api.md와 다른 점이 있으면 그 이유
   - 지원이 확인할 방법(tasks.md 표의 "확인할 것"을 실제 명령·주소로)
5. 문서 저장소 `specs/001-tistory-blog/learning/`에 학습 자료를 쓴다(지원 공부용, 2026-10-08 지원 결정). 무엇을 만들었는지 나열하는 것이 아니라, 지원이 관련 개념을 처음부터 이해하고 공부할 수 있게 상세히 쓴다. 대화가 아니라 최종 결과 기준이다.
   - **개념 문서** `concepts/NN-이름.md`: 이 스텝에서 처음 쓴 개념은 새로 만들고, 이미 있는 개념에 새 내용이 생기면 보강한다. 절 순서는 기존 문서와 같다: 배우는 것 → 왜 필요한가 → 기본 개념 → 동작 원리 → 이 프로젝트에서는(실제 코드 발췌와 줄별 설명) → 자주 하는 실수 → 직접 해 보기 → 확인 문제(답은 접기) → 더 읽을거리.
   - **스텝 노트** `step-NN.md`: 한눈에 보기, 요청 흐름, "이 스텝을 이해하려면"(개념 문서 읽는 순서와 쓰인 곳), 막혔던 점, 직접 해 보기.
   - `learning/README.md` 표에 더한다. 코드 발췌는 실제 파일을 읽어 확인하고, 라이브러리 동작은 확실한 것만 쓴다.
6. push와 PR은 지원이 확인한 뒤에 한다.

## 기술 규칙

- Java 21, Spring Boot 4.1(pom.xml 기준), Maven(`./mvnw`). 3.x 예제를 그대로 쓰지 않는다(스타터 이름, Flyway 스타터, Jackson 3 등이 다르다).
- 기본 패키지 `com.nhnacademy.blog`, 아래는 기능 단위 패키지(plan.md 구조). 기능 패키지 안은 세 계층으로 나눈다(2026-10-08 지원 결정).
  - `domain/`: 엔티티, enum, Repository
  - `application/`: Service
  - `presentation/`: Controller, 요청·응답 DTO는 `presentation/dto/`
  - 의존은 presentation → application → domain 한 방향. 여러 기능이 같이 쓰는 것은 `global/`(config, entity, error, security, web).
- DB는 MySQL 8. 개발은 `docker compose up -d`, 테스트는 Testcontainers. H2는 쓰지 않는다(schema.sql이 H2에서 안 돌아감).
- 테이블은 Flyway가 만든다. `V1__init.sql`은 `../blog-docs/specs/001-tistory-blog/erd/schema.sql`을 그대로 복사한 것이고, 이미 적용된 마이그레이션 파일은 고치지 않는다. JPA는 `ddl-auto=validate`.
- 엔티티는 schema.sql의 컬럼·제약에 맞춘다. 참/거짓 컬럼 `is_x`는 필드 `x` + `@Column(name = "is_x")`, 열거값은 `EnumType.STRING`.
- 이미지 저장 폴더는 설정값 `app.upload.dir`(개발: `/Users/chosun-nhn54/IdeaProjects/blog/uploads`, git 제외).
- 볼 수 없는 글은 로그인 여부와 상관없이 404. 권한은 서버에서 검사한다(헌법 II, IV).

## 명령

```bash
docker compose up -d        # MySQL, Redis
./mvnw spring-boot:run      # http://localhost:8080
./mvnw test
cd frontend && npm run dev  # 프론트 개발 서버
```
