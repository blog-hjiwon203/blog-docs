# 1팀 블로그 명세 (Spec Kit 형식) · 지원 작업본

> 공통 Spec Kit 명세(constitution, spec)에 지원의 plan·tasks를 더한 작업본이다. 원본 문서는 `docs/`에 있다(통합 기능명세서 v0.2, 지원 개인 설계 문서). 이 저장소 루트에서 Claude Code를 열면 `/speckit-*` 스킬을 바로 쓸 수 있다.


`docs/1팀 블로그 통합 기능명세서.md` v0.2를 [GitHub Spec Kit](https://github.com/github/spec-kit) 구조로 다시 정리한 것이다. 내용(71개 기능, 선택 8개, 미결정 9개)은 그대로이고 형식만 바꿨다.

## 파일 구성

```
spec-kit/
├── .claude/skills/speckit-*/                # Claude Code용 Spec Kit 스킬 (specify init --integration claude)
├── .specify/
│   ├── memory/constitution.md               # 세 서비스가 꼭 지킬 원칙 7개
│   ├── templates/, scripts/bash/, workflows/ # Spec Kit 1.1.2 기본 파일
│   └── feature.json                         # 현재 기능 폴더 = specs/001-tistory-blog
└── specs/001-tistory-blog/
    ├── spec.md                              # 유저 스토리, 수용 기준, FR, 성공 기준 (공통)
    ├── plan.md, research.md, data-model.md  # 지원: 스택·선택 항목·설계 결정
    ├── contracts/rest-api.md, quickstart.md # 지원: API 초안, 로컬 검증 시나리오
    ├── tasks.md                             # 지원: 2주 일정 기준 T001~T073
    └── checklists/requirements.md           # spec 품질 체크리스트
```

## 원본과 대응

| 원본 통합 명세서 | Spec Kit |
| --- | --- |
| 1.3 통합 원칙, 3장 권한, 4장 공통 정책, 8장 비기능 | constitution.md 원칙 I~VII |
| 5장 기능 목록 + 6장 기능 상세 | spec.md 유저 스토리 14개, FR-001~083 |
| 4장 공통 정책 | FR-001~010, Edge Cases |
| 8장 비기능 요구사항 | NFR-001~004, SC-002~008 |
| 7장 선택 항목 | spec.md "선택 항목 (Variation Points)" V1~V8 |
| 9.1 확정 사항 | Clarifications > 확정 사항 |
| 9.2 미결정 사항 | `[NEEDS CLARIFICATION]` + Q1~Q9 |
| 2장 용어, 데이터 | Key Entities |
| 부록 A·B·C | 원본에 그대로 둠 |

우선순위: 스토리 **P1 = 원본 P0**, **P2 = 원본 P1**, **P3 = 원본 P2**. 각 FR 끝의 `[POST-01 · P0]`로 원본 ID와 등급을 추적한다.

## Claude Code에서 쓰는 법

이 폴더는 `specify init --here --integration claude`로 만든 구조에 공통 constitution과 spec을 채운 상태다. `/speckit-specify`는 이미 끝난 것으로 보고 다음 단계부터 진행한다.

1. 이 폴더 전체(`.claude`, `.specify` 포함)를 자기 저장소 루트에 복사하고 그 폴더에서 Claude Code를 연다.
2. `/speckit-clarify`: 미결정 Q1~Q9 정리 (최소 Q1)
3. (지원은 완료) `/speckit-plan <내 스택과 선택 항목 V1~V8>`: plan.md, research.md, data-model.md, contracts/ 생성. Constitution Check는 원칙 I~VII로 채워진다
4. (지원은 완료) `/speckit-tasks`: tasks.md 생성. P1 스토리(US1~US4)부터 MVP 순서
5. `/speckit-analyze`로 일관성 확인 후 `/speckit-implement`
6. spec.md의 Acceptance Scenarios로 서로의 서비스를 교차 테스트한다

plan과 tasks는 기술 스택마다 달라지므로 공통 폴더에는 두지 않는다(constitution 원칙 I). `.specify/feature.json`은 체크아웃마다 다른 로컬 상태라 git에서 제외되므로, 새로 클론했다면 `SPECIFY_FEATURE_DIRECTORY=specs/001-tistory-blog`를 지정하거나 이 파일을 다시 만든다.
