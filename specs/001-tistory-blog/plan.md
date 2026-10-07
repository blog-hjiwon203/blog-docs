# 구현 계획 (Implementation Plan): 티스토리형 블로그 플랫폼 (지원)

> **이 문서는?** 지원의 구현 계획이다. 기능 명세를 어떤 기술과 구조로 만들지 정한다. 결정의 이유는 조사(research.md)에, 세부 설계는 데이터 모델과 REST API 초안에 있다. 전체 문서 안내는 [README](../../README.md)에 있다.

**브랜치**: `001-tistory-blog` | **날짜**: 2026-10-07 | **명세**: [spec.md](./spec.md)

**입력**: [기능 명세](./spec.md), 지원 개인 설계 문서 (`docs/기능명세서_지원 (개인 설계 문서).md`, 2026-10-01)

## 요약

누구나 가입해 자기 블로그(서브도메인)를 열고, WYSIWYG 에디터로 글을 발행하고, 다른 블로그 글을 읽고 댓글·공감하는 멀티 유저 블로그를 만든다. Spring Boot REST API + React SPA를 jar 하나로 함께 배포하고, Host 헤더로 블로그를 찾는다. **2주 안에 공통 P0 24개 기능(US1~US4) 전부**를 구현하고, 남는 시간에 P1 일부(이미지 이후 태그·검색·인기 글·회원정보·내 글 관리·주제)를 붙인다.

## 기술 맥락 (Technical Context)

**언어/버전**: Java 17+ (Spring Boot 3.x), TypeScript/JavaScript (React 18) — 버전은 [research.md R-01](./research.md) 기본값

**주요 의존성**: Spring Boot (Web, Security, Data JPA, Validation, Cache, Data Redis), JWT 라이브러리, OWASP Java HTML Sanitizer, jsoup / React, React Router, Vite, Tiptap, DOMPurify

**저장소**: 주 DB는 개발 H2(MySQL 호환 모드, 파일 저장) / 운영 MySQL. Redis는 캐시(@Cacheable, TTL 5분)와 연타 방지 키 저장. PostgreSQL + pgvector는 '비슷한 글 추천' 전용으로 2주 안에 도전(도전 과제, R-02). 이미지는 서버 로컬 `./uploads/`(UUID 파일명), DB에는 경로·원본 파일명·크기만.

**테스트**: JUnit 5 + Spring Boot Test + MockMvc(백엔드), Vitest(프론트, 최소) — 설계 문서에 없어 기본값으로 둠 (R-01)

**대상 플랫폼**: Linux 서버 1대, 와일드카드 도메인 `*.blog.com` → 같은 서버. 로컬은 `myblog.localhost:8080`

**프로젝트 유형**: 웹 서비스 (백엔드 + 프론트엔드, 단일 jar 배포)

**성능 목표**: 목록은 페이지 단위, 홈 인기 글·주제별 글은 서버 캐시 5분, 이미지는 리사이즈·썸네일. 수치 목표는 정하지 않음(설계 문서에 없음)

**제약**: 일정 2주. 화면은 최소화하고 백엔드에 집중. 모바일 360px부터 대응. 날짜·시각 KST

**규모/범위**: 학습용 단일 서버. 회원당 활성 블로그 최대 5개

### 주요 방식과 구현

| ID | 내 선택 | 구현 메모 |
| --- | --- | --- |
| 로그인 | 이메일(P0) + 소셜 카카오·구글(P1) | OAuth 2.0. 계정 연동 규칙은 research R-07. 이메일 인증·비밀번호 재설정은 자체 기능 |
| 블로그 수 | 여러 개, 활성 블로그 최대 5개 | 처음 만든 블로그가 대표. BLOG-06~08 구현 대상 |
| 블로그 주소 | 서브도메인 `{address}.blog.com` | Host 헤더 해석 (R-04) |
| 에디터 | WYSIWYG, Tiptap | 본문 HTML 저장, 서버 정화 + 클라이언트 정화 (R-05) |
| 글 주소 | 번호 `{address}.blog.com/{post-id}`, 전역 번호 | 다른 블로그 소속이면 볼 수 있을 때 301, 아니면 404 |
| 인기 글 | 최근 1시간 조회수, 공개 글 상위 10, 캐시 5분 | 조회 기록(view_log)으로 집계 |
| 주제 | 글마다, 고정 enum 10개 | IT·개발, 여행, 맛집·요리, 일상, 리뷰, 취미, 경제·재테크, 건강·운동, 문화·연예, 교육·학습 |
| 구독자 공개 | 구독자 공개(SUBSCRIBERS) | 구독자와 주인만 본문 열람. 구독이 필요해 2주 범위 밖 |

### 자율로 정한 값

| 항목 | 값 |
| --- | --- |
| 비밀번호 규칙 | 8자 이상, 영문+숫자, bcrypt |
| 비밀번호 재설정 링크 | 30분 유효 |
| 업로드 상한 | 파일당 10MB, jpg/png/gif/webp |
| 자동 임시저장 | 1분 간격 |
| 조회수 중복 | 같은 사용자는 일정 시간 안에 1회 (시간 [NEEDS CLARIFICATION]) |
| 목록 크기 | [research R-06](./research.md) 표 |
| 사이드바 | 최근 글·최근 댓글 각 5개 |
| 회원 정지 기간 | 7일 / 30일 / 영구 |
| 공지 노출 | 플랫폼 홈 상단 최신 1개 + 목록 |
| 글자 수 | 제목 200, 블로그 이름 50, 카테고리 이름 30 |

## 헌법 점검 (Constitution Check)

*관문: 조사(0단계) 전에 통과하고, 설계(1단계) 후 다시 확인한다.*

| 원칙 | 상태 | 근거 |
| --- | --- | --- |
| I. 명세는 동작, 계획은 기술 | ✅ | 스택·구조·구현 수치는 이 계획과 조사에만 둠 |
| II. 비공개는 존재를 숨긴다 | ✅ | 남의 비공개 글·블라인드 글·제한 블로그 모두 404. 예전 안내 문구('블라인드된 게시물입니다')는 버림. 목록 totalElements도 볼 수 있는 글만 셈 |
| III. 공유된 주소는 깨지지 않는다 | ✅ | 블로그 소프트 삭제로 주소 영구 예약, 글 전역 번호 불변, 이사·글 이동 시 서버에서 301 |
| IV. 권한은 서버가 지킨다 | ✅ | Spring Security(URL·role) + 서비스 계층 주인 검사. XSS 이중 정화, CSP. 토큰 방식이라 CSRF 해당 없음(쿠키 도입 시 재검토) |
| V. 제재는 숨김이며 되돌릴 수 있다 | ✅ | 블라인드·정지·블로그 제한 모두 상태값, 해제 시 원복. 관리 이력은 조회만 |
| VI. 입력과 숫자는 잃거나 틀리지 않는다 | ✅ | 공감·구독은 DB UNIQUE, 발행·댓글은 Idempotency-Key(Redis TTL) (R-09 확정) |
| VII. 추적 가능한 ID | ✅ | 기능 ID 사용. 설계 문서의 ERD·API 탭은 예전 ID라 갱신 예정 |

**설계 후 재확인**: data-model과 contracts가 II(가시성 필터를 공통 쿼리 조건으로), III(블로그 deleted_at, moved_to_blog_id), V(블라인드 컬럼)를 반영함 → 통과. VI도 R-09 확정으로 통과.

## 프로젝트 구조

### 문서 (이 기능)

```text
specs/001-tistory-blog/
├── spec.md              # 기능 명세
├── plan.md              # 이 파일
├── research.md          # 기술 결정과 미결정
├── data-model.md        # 엔티티·테이블
├── quickstart.md        # 로컬 실행과 수용 시나리오 검증
├── contracts/
│   └── rest-api.md      # REST API 초안
├── checklists/requirements.md
└── tasks.md             # 2주 일정 기준 작업
```

### 소스 코드 (저장소 루트)

```text
backend/
├── build.gradle
└── src/
    ├── main/java/com/blog/
    │   ├── global/          # config(Security, Cache, Web), error(공통 오류 응답), host(서브도메인 해석), visibility(가시성 판단)
    │   ├── auth/            # 가입·로그인·JWT·소셜
    │   ├── member/
    │   ├── blog/            # 개설·정보·사이드바·이사·삭제
    │   ├── post/            # 글·조회 기록·주제
    │   ├── category/
    │   ├── tag/
    │   ├── comment/         # 댓글·답글·방명록
    │   ├── reaction/        # 공감
    │   ├── subscription/
    │   ├── search/
    │   ├── home/
    │   ├── manage/          # 블로그 주인 관리
    │   ├── admin/           # 서비스 관리
    │   ├── image/
    │   └── recommend/       # 비슷한 글 추천 (PostgreSQL + pgvector, 도전 과제)
    ├── main/resources/      # application.yml, data.sql(ADMIN 초기 계정), static/(React 빌드 결과)
    └── test/java/com/blog/

frontend/
├── vite.config.ts           # /api → localhost:8080 프록시
└── src/
    ├── app/                 # 라우터: 플랫폼 도메인 / 블로그 서브도메인 분기
    ├── pages/               # home, auth, blog, post, manage, admin
    ├── components/          # editor(Tiptap), sidebar, pagination
    └── api/
```

**구조 결정**: 웹 애플리케이션 구조. 빌드 시 `frontend/dist`를 `backend/src/main/resources/static`으로 복사해 jar 하나로 배포한다. 백엔드는 기능(도메인) 단위 패키지.

## 복잡도 기록 (Complexity Tracking)

| 항목 | 이유 | 더 단순한 대안을 안 쓴 이유 |
| --- | --- | --- |
| 서브도메인 주소 | 티스토리와 같은 경험 | 경로 방식이 더 단순하지만 학습 목표. 대신 블로그 간 로그인 공유 문제(R-03)를 떠안음 |
| 저장소 3종(MySQL, Redis, PostgreSQL) | Redis는 캐시·연타 방지, PostgreSQL은 벡터 검색 | 벡터 검색을 MySQL로 하기 어려움. PostgreSQL은 추천 기능에만 쓰고, 일정이 밀리면 통째로 뺄 수 있게 분리 |
| XSS 이중 정화 | WYSIWYG HTML 저장 | 마크다운이면 단순하지만 티스토리와 같은 편집 경험을 위해 WYSIWYG를 고름. 서버 정화가 필수, 클라이언트는 보조 |
| 자체 기능: 비회원 댓글 | 예전 설계 | **구현 보류** (기능 명세 Q5). 넣으면 권한표와 연타·스팸 대책을 다시 정해야 함 |
