# 티스토리형 블로그 문서 (지원)

지원의 기능명세서(`docs/기능명세서_지원 (개인 설계 문서).md`, 이하 **원본**)를 [GitHub Spec Kit](https://github.com/github/spec-kit) 형식으로 정리한 저장소다. 원본의 기능 코드(`AUTH-01` 등)를 그대로 쓰고, 옮기며 고친 곳은 원본 검토에 모았다. 이 저장소 루트에서 Claude Code를 열면 `/speckit-*` 스킬을 바로 쓸 수 있다.

> **확인하거나 정할 게 있는지 보려면 [지원이 확인할 것](specs/001-tistory-blog/review.md) 하나만 보면 된다.** 지원이 정한 것(A), Claude가 임의로 정한 것(B), 확인만 하면 되는 것(C)이 모두 거기 있다.

## 문서 안내

어떤 질문이 생겼을 때 어느 문서를 보면 되는지 정리한 표다. 위에서 아래로 갈수록 "무엇을"에서 "어떻게"로 내려간다.

| 문서 | 무엇을 담나 | 이런 질문이 생기면 본다 |
| --- | --- | --- |
| [헌법](.specify/memory/constitution.md) | 이 서비스가 절대 어기면 안 되는 원칙 7개 | "비공개 글은 403이야 404야?", "관리자가 글을 지워도 돼?" |
| [기능 명세](specs/001-tistory-blog/spec.md) | 사용자가 확인할 수 있는 동작 전부. 주요 방식, 유저 스토리, 권한, 공통 규칙, 기능 코드별 요구사항, 미결정 사항 | "이 기능이 어떻게 동작해야 해?", "우선순위가 뭐야?", "아직 안 정해진 건?" |
| [지원이 확인할 것](specs/001-tistory-blog/review.md) | 지원이 정한 Q1~Q7, Claude가 임의로 정한 것, 원본을 옮기며 찾은 문제 16건 | "내가 정하거나 확인할 게 뭐야?", "원본이랑 왜 달라?" |
| [명세 품질 체크리스트](specs/001-tistory-blog/checklists/requirements.md) | 기능 명세가 구현 계획으로 넘어가도 될 만큼 완성됐는지 점검표 | "명세에 빠진 게 있어?" |
| [구현 계획](specs/001-tistory-blog/plan.md) | 기술 스택, 주요 방식의 구현, 자율 값, 헌법 점검, 폴더 구조 | "무슨 기술로 만들어?", "폴더는 어떻게 나눠?" |
| [조사](specs/001-tistory-blog/research.md) | 기술 결정 하나하나의 결정·이유·대안, 남은 미결정 | "왜 JWT야?", "Redis는 어디에 써?", "연타 방지는 어떻게 해?" |
| [데이터 모델](specs/001-tistory-blog/data-model.md) | 테이블과 컬럼, 제약, 글 가시성 판단 순서 | "post 테이블에 뭐가 있어?", "이 글을 누가 볼 수 있어?" |
| [ERD](specs/001-tistory-blog/erd/README.md) | Crowfoot에서 설계한 ERD 사본: 관계도(Mermaid), 테이블별 컬럼·키·제약, 실행 가능한 DDL, 데이터 모델을 ERD에 맞춘 이력 | "테이블끼리 어떻게 이어져?", "실제 DDL은?" |
| [REST API 명세](specs/001-tistory-blog/contracts/rest-api.md) | 엔드포인트, 요청·응답 본문, 응답 코드 규칙, 오류 코드 목록 | "글 목록 API 경로가 뭐야?", "몇 번 상태 코드를 줘?" |
| [화면 목업](specs/001-tistory-blog/mockups/README.md) | 화면 31개의 정적 HTML 목업과 화면마다 부르는 API | "이 화면은 어떻게 생겼어?", "이 화면은 어떤 API를 불러?" |
| [빠른 시작](specs/001-tistory-blog/quickstart.md) | 로컬 실행 방법과 손으로 확인하는 검증 시나리오 | "어떻게 띄워?", "다 만들었는지 어떻게 확인해?" |
| [작업 목록](specs/001-tistory-blog/tasks.md) | 2주 일정에 맞춘 작업 T001~T073과 백로그 작업 T074~T087, 순서와 의존 관계 | "오늘 뭐 해?", "이건 몇 주차야?" |
| [구현 노트](specs/001-tistory-blog/learning/README.md) | 스텝마다 무엇을 어떤 방식으로 만들었는지 공부용 정리(쓴 개념, 고른 이유, 요청 흐름, 막혔던 점) | "이건 어떻게 동작해?", "왜 이렇게 만들었어?" |
| [기능명세서_지원 원본](docs/기능명세서_지원%20%28개인%20설계%20문서%29.md) | 위 문서들의 원본인 개인 설계 문서 | "원래 문서 문장 그대로 보고 싶어", "예전 ID가 지금 어느 코드야?" (원본 5.15) |

### 문서끼리의 관계

```
기능명세서_지원 원본
 ├─ 지원이 확인할 것 (정할 것, Claude가 정한 것, 원본 검토)
 └─ 헌법 (원칙)
     └─ 기능 명세 (무엇을)
         ├─ 명세 품질 체크리스트
         └─ 구현 계획 (어떻게)
             ├─ 조사 (왜 그렇게 정했나)
             ├─ 데이터 모델 · ERD · REST API 명세 · 화면 목업 (설계)
             ├─ 빠른 시작 (어떻게 확인하나)
             └─ 작업 목록 (언제, 어떤 순서로)
```

- 동작이 바뀌면 기능 명세를 먼저 고치고, 구현 계획과 작업 목록을 따라 고친다. 반대 방향으로는 고치지 않는다.
- 원본 문서(`docs/`)는 기록용으로 그대로 둔다. 지금 기준은 Spec Kit 문서들이고, 원본과 달라진 곳은 원본 검토에 이유가 있다.

## 자주 쓰는 표기

| 표기 | 뜻 | 정의된 곳 |
| --- | --- | --- |
| `POST-01` 같은 코드 | 원본 기능 코드 (영역코드-번호). 모든 문서가 이 코드로 기능을 가리킨다 | 원본 5장, 기능 명세 |
| `OWN-01`~`OWN-06` | 원본 5.14 자체 기능에 새로 붙인 코드 | 기능 명세 표기 |
| (원본 4.2) | 원본 문서의 절 번호 | 원본 |
| (채움) | 원본에 없어 채운 값 | 원본 검토 10 |
| P0 / P1 / P2 | 기능 등급: 필수 / 권장 / 확장 | 헌법 원칙 VII |
| 스토리 우선순위 P1 / P2 / P3 | Spec Kit 표기. 각각 기능 등급 P0 / P1 / P2와 같다 | 기능 명세 머리말 |
| US1~US15 | 유저 스토리 번호. 머리에 확인하는 기능 코드가 있다 | 기능 명세 |
| SC-001~007 | 성공 기준 | 기능 명세 |
| Q1~Q7 | 원본에서 정해지지 않았던 질문. 2026-10-07 지원이 모두 정함 | 기능 명세 명확화, 지원이 확인할 것 A |
| R-01~R-11 | 기술 결정 항목 | 조사 |
| T001~T087 | 작업 번호 | 작업 목록 |
| [W1] / [W2a] / [W2b] | 1주차 / 2주차 전반 / 2주차 후반 | 작업 목록 |
| `[NEEDS CLARIFICATION]` | 아직 정해지지 않아 확인이 필요한 곳 (Spec Kit 예약 표기라 영어로 둔다) | 모든 문서 |

## 원본 설계 문서와의 대응

| 기능명세서_지원 | 이 저장소 |
| --- | --- |
| 1장 개요, 2장 선택 항목 | 기능 명세 개요·주요 방식, 구현 계획 주요 방식과 구현 |
| 3장 기술 스택 | 구현 계획 기술 맥락, 조사 R-01·R-02 |
| 4장 공통 구현 정책 (권한, 주소, 페이지네이션, 보안, 계정 연동) | 기능 명세 권한·공통 규칙, 조사 R-03~R-08 |
| 5장 기능별 구현 | 기능 명세 기능 요구사항(같은 기능 코드), 데이터 모델, REST API 명세 |
| 5.14 자체 기능 | 기능 명세 OWN-01~06, 작업 목록 10a단계 |
| 6장 화면 주소와 주요 흐름 | REST API 명세, 화면 목업, 데이터 모델 가시성 판단, 빠른 시작 |
| 7장 일정 | 작업 목록 [W1]·[W2a]·[W2b] |
| 8장 자율로 정한 값 | 구현 계획 자율로 정한 값 |
| 9장 다른 점, 10장 남은 일 | 기능 명세 명확화 Q1~Q7, 조사 R-11, 원본 검토 11 |

## Claude Code에서 쓰는 법

`/speckit-specify`(기능 명세), `/speckit-plan`(구현 계획), `/speckit-tasks`(작업 목록)는 이미 끝난 상태다. 구현은 이 저장소가 아니라 코드 저장소 [AIP-1/blog-basic-AIGJ_01_017-blog](https://github.com/AIP-1/blog-basic-AIGJ_01_017-blog)에 한다.

### 폴더 배치 (지원 컴퓨터)

```
~/IdeaProjects/
├── blog/         # 코드 저장소 클론 (IntelliJ 프로젝트). 여기서 Claude Code를 연다
└── blog-docs/    # 이 문서 저장소 클론. Claude Code가 읽기만 한다
```

`~/Documents/blog_project/docs`는 원본 기능명세서 보관용이라 구현에 쓰지 않는다.

### 처음 한 번

```bash
cd ~/IdeaProjects
git clone https://github.com/blog-hjiwon203/blog-docs.git
cp blog-docs/specs/001-tistory-blog/code-repo-CLAUDE.md blog/CLAUDE.md
cd blog && git add CLAUDE.md && git commit -m "docs: CLAUDE.md 추가" && git push
```

### 스텝마다

1. 문서가 바뀌었으면 `cd ~/IdeaProjects/blog-docs && git pull`
2. IntelliJ 터미널에서 `cd ~/IdeaProjects/blog && claude --add-dir ../blog-docs`
3. "스텝 1 진행해"처럼 [작업 목록의 구현 스텝](specs/001-tistory-blog/tasks.md#구현-스텝과-검토-포인트) 번호를 준다
4. Claude Code가 멈추고 정리해 주면 표의 "확인할 것"으로 확인하고, push → PR → 병합
5. 다음 스텝

`--add-dir`로 연 폴더의 `.claude/skills/`는 같이 읽히므로 코드 저장소에서도 `/speckit-analyze` 같은 Spec Kit 스킬을 쓸 수 있다. 반대로 이 저장소의 CLAUDE.md는 읽히지 않으니, 코드 작업 규칙은 코드 저장소의 CLAUDE.md에 둔다.

## 폴더 구성

```
.
├── .claude/skills/speckit-*/      # Claude Code용 Spec Kit 스킬
├── .specify/
│   ├── memory/constitution.md     # 헌법
│   └── templates/, scripts/, workflows/  # Spec Kit 1.1.2 기본 파일 (수정하지 않음)
├── specs/001-tistory-blog/        # 기능 명세, 구현 계획, 작업 목록
└── docs/                          # 원본 설계 문서
```
