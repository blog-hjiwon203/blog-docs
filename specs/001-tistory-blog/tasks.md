---
description: "지원 서비스 구현 작업 (2주 일정 기준)"
---

# 작업 목록 (Tasks): 티스토리형 블로그 (지원)

> **이 문서는?** 지원의 2주 작업 목록이다. 구현 계획을 실제로 할 일(T001~T087, 2주 범위는 T073까지)로 쪼개 주차와 순서, 의존 관계를 붙였다. 실제 구현은 아래 [구현 스텝과 검토 포인트](#구현-스텝과-검토-포인트)대로 한 스텝씩 하고, 스텝마다 지원이 확인한 뒤 넘어간다. 전체 문서 안내는 [README](../../README.md)에 있다.

**입력**: `specs/001-tistory-blog/` 의 spec.md, plan.md, research.md, data-model.md, contracts/rest-api.md, erd/schema.sql(테이블의 기준), mockups/(화면의 기준)

**선행 문서**: plan.md, spec.md

**테스트**: spec의 핵심 규칙(가시성 404, 권한, 연타, 주소 불변)은 MockMvc 통합 테스트로 남긴다. 나머지는 2주차 후반 "테스트 보강"에서.

**일정 표시**: `[W1]` 1주차, `[W2a]` 2주차 전반, `[W2b]` 2주차 후반 (원본 7장). 표시 없는 단계는 2주 범위 밖.

## 구현 스텝과 검토 포인트

아래 "N단계"는 유저 스토리별 묶음이고, 실제로 만드는 순서는 이 표의 **스텝**이다. 한 스텝은 브랜치·PR 하나 크기로, 끝나면 앱이 뜨고 테스트가 통과하는 상태여야 한다.

**Claude Code CLI에 시키는 법**: 코드 저장소(`~/IdeaProjects/blog`)에서 `claude --add-dir ../blog-docs`로 열고 "스텝 3 진행해"처럼 스텝 번호를 준다. 코드 저장소의 `CLAUDE.md`([원본](./code-repo-CLAUDE.md))에 따라 그 스텝의 작업만 하고, 아래 "끝났을 때 보여 줄 것"을 정리한 뒤 멈춘다. 이 표의 체크박스는 스텝이 병합된 뒤 문서 저장소에서 따로 `[X]`로 바꾼다. 지원이 "확인할 것"을 보고 PR을 병합하면 다음 스텝을 시킨다.

**모든 스텝에 공통으로 끝났을 때 보여 줄 것**: `./mvnw test` 결과, 바뀐 파일 목록, 만든 API 목록(contracts/rest-api.md와 다른 점이 있으면 그 이유), 미룬 것.

| 스텝 | 주차 | 작업 | 확인할 것 (지원) |
| --- | --- | --- | --- |
| 1 프로젝트 뼈대 | W1 | T001~T004, T016a | `docker compose up -d` 후 `./mvnw spring-boot:run`이 뜨고 MySQL에 테이블 26개가 생김(Flyway), `npm run dev` 화면이 뜨고 `/api` 프록시가 됨, `./mvnw test` 통과 |
| 2 공통 기반·핵심 엔티티 | W1 | T005, T006, T012, T013, T014, T021, T028, T043 | 앱이 뜰 때 엔티티 검증(validate)이 통과하는지, 일부러 낸 400·404·500 응답 모양이 COM-02대로인지(500에 스택 없음), ADMIN 계정이 들어갔는지, 정화 테스트에서 `<script>`·`onerror`가 빠지는지 |
| 3 인증 틀·주소 해석·가시성 | W1 | T007~T011, T015, T016, T050 | `alpha.blog.test:8080`이 블로그로, `blog.test:8080`이 플랫폼으로 해석되는지(R-04), 가시성 판단 단위 테스트(볼 수 없는 글 404가 401보다 먼저), Idempotency-Key 같은 키 두 번에 같은 응답 |
| 4 가입·블로그 개설 (US1) | W1 | T017~T020, T022~T027 | quickstart "P0 한 바퀴" 1~2, 블로그 주소 사이 로그인 유지, 6번째 블로그 거절. 화면은 목업 signup·login·blog-create·blog-main과 비교 |
| 5 글쓰기 (US2 글·카테고리) | W1 | T029~T035, T040 | quickstart 3 중 이미지·태그를 뺀 부분, 수정 후 주소·순서 불변, 카테고리 삭제 시 미분류. 목업 manage-write·manage-categories |
| 6 읽기·댓글·권한 (US3 일부, US4) | W1 | T041, T042, T044, T045, T051, T052 | **1주차 시연**: quickstart "P0 한 바퀴" 1~6(공감 제외), "권한·가시성" 표 전부. 목업 home·post-detail·errors |
| 7 이미지·태그·공감·검색·답글 | W2a | T036~T039, T046~T049, T069 | quickstart 3 전체(이미지·태그), 공감 연타 1개, 블로그 검색, 답글 있는 댓글 삭제 표시. 목업 blog-search·post-detail |
| 8 조회수·인기 글 | W2a | T053, T054, T063 | 같은 사람 5분 안 재조회는 조회수 그대로, 홈 인기 글(캐시 5분), 사이드바 태그 목록 |
| 9 회원정보·주제·하위 카테고리·내 글 관리 | W2b | T055, T056, T060, T064, T067 | 회원정보 수정, 주제별 글 탭, 하위 카테고리 트리와 상위 합산, 내 글 관리 필터·일괄 변경. 목업 mypage·manage-posts·home |
| 10 비슷한 글 추천 (도전, 빼도 됨) | W2b | T069a~T069d | 시작 전에 임베딩 방법(R-02 미결정)을 정한다. 볼 수 없는 글이 추천에 안 나오는지 |
| 11 마무리 | W2b | T070~T073 | quickstart 전 항목, 360px 화면, 글 링크 공유 미리보기 |

- 스텝 1의 T016a는 Redis뿐 아니라 개발용 MySQL도 같은 `docker-compose.yml`에 넣는다(R-02).
- 핵심 엔티티(T021 `blog`, T028 `post`·`category`, T043 `comment`)는 스텝 2에서 먼저 만든다. 스텝 3의 주소 해석(T009), 가시성 판단(T011), 주인 검사(T050)가 이 엔티티를 쓰기 때문이다.
- T050(`BlogOwnerGuard`)은 6단계에 적혀 있지만 블로그 수정(T023)이 먼저 쓰므로 스텝 3에서 만든다.
- 엔티티를 만드는 작업(T005, T021, T028, T038, T043 등)은 `erd/schema.sql`의 컬럼·제약에 맞춘다. 테이블은 스텝 1에서 Flyway로 한 번에 다 만들어 두고, 엔티티는 스텝마다 필요한 것만 쓴다.
- 스텝 안에서 명세와 다르게 해야 할 것이 생기면 구현을 멈추고 지원에게 묻는다. 명세를 바꾸기로 하면 이 저장소(blog-docs)의 문서를 먼저 고친다.
- 백로그(T057~T059, T060a~T062, T065, T066, T068, T074~T087)는 스텝 11 이후 지원이 고른 순서대로 스텝 12부터 붙인다.

---

## 형식: `[ID] [P?] [스토리] [주차] 설명 (기능 코드)`

- **[P]**: 다른 파일을 건드리고 의존이 없어 병렬로 할 수 있음
- **[스토리]**: spec 유저 스토리(US1~US16)
- 경로는 코드 저장소(plan.md 구조) 기준: `src/main/java/com/nhnacademy/blog/...`, `frontend/src/...`

---

## 1단계: 프로젝트 준비 (Setup)

- [ ] T001 [W1] 이미 만든 Maven 프로젝트(Spring Boot 4.1.1, Java 21, Web MVC·Security·Data JPA·Validation·MySQL 드라이버 있음)에 의존성 추가: Cache, Data Redis, Flyway(`spring-boot-starter-flyway`, `flyway-mysql`), Testcontainers MySQL in `pom.xml`. 커밋된 `.DS_Store`를 지우고 `.gitignore`에 추가
- [ ] T002 [P] [W1] Vite + React + TypeScript 프로젝트, `/api` → 8080 프록시 in `frontend/vite.config.ts`
- [ ] T003 [P] [W1] `application.properties`를 `application.yml`로 바꾸고 프로필 분리(dev: docker compose MySQL, prod: MySQL), `jpa.hibernate.ddl-auto=validate`, `TZ=Asia/Seoul`, `app.upload.dir`(dev 기본값 `/Users/chosun-nhn54/IdeaProjects/blog/uploads`, `.gitignore`에 `uploads/`), 문서 저장소의 `erd/schema.sql`을 `db/migration/V1__init.sql`로 복사 in `src/main/resources/` (R-02)
- [ ] T004 [P] [W1] 프론트 빌드 결과를 `src/main/resources/static`으로 복사하는 빌드 스크립트

---

## 2단계: 기반 작업 (Foundational, 모든 스토리의 전제)

**⚠️ 이 단계가 끝나야 스토리 작업을 시작한다**

- [ ] T005 [W1] 공통 엔티티 기반(BaseTimeEntity), `member` 엔티티(role, status) in `member/` (data-model)
- [ ] T006 [W1] 공통 오류 응답 형식과 `@RestControllerAdvice` (400 fieldErrors, 401, 403, 404, 409, 500은 내부 정보 없이) in `global/error/` (COM-02)
- [ ] T007 [W1] JWT 발급·검증 필터(`.blog.com` HttpOnly 쿠키로 발급, SameSite=Lax + CSRF 대책, R-03), Spring Security 설정(`/api/admin/**` hasRole ADMIN, 나머지 permitAll + 메서드 단위 인증) in `global/config/SecurityConfig.java` (COM-01, ADMIN-01, AUTH-03)
- [ ] T008 [W1] 요청마다 member.status 확인(SUSPENDED → 403 + 사유·기한, WITHDRAWN → 401) in JWT 필터 (ADMIN-02 대비, R-03)
- [ ] T009 [W1] Host 헤더 → 블로그 해석 `BlogHostResolver` (플랫폼 도메인 / 서브도메인 / 없으면 404 / 이사 301) in `global/host/` (R-04)
- [ ] T010 [W1] 화면 주소 처리: `/api/**` 외 요청은 블로그·글 확인 후 `index.html` 포워드, 301은 서버가 직접 in `global/config/SpaForwardController.java` (6장 ①)
- [ ] T011 [W1] 가시성 판단 `PostVisibilityPolicy` (data-model 글 가시성 판단, 볼 수 없는 글은 401보다 먼저 404)와 목록용 공통 조건(Specification/QueryDSL) in `global/visibility/` (COM-01, POST-04)
- [ ] T012 [W1] 페이지 요청 보정(size 1~50, page 음수→0)과 페이지·커서 응답 DTO in `global/web/` (R-06)
- [ ] T013 [P] [W1] ADMIN 초기 계정(ERD의 "data.sql")을 Flyway `V2__admin_account.sql`로 넣기 in `src/main/resources/db/migration/` (ADMIN-01)
- [ ] T014 [P] [W1] XSS: OWASP HTML Sanitizer 허용 목록 `HtmlSanitizer`, jsoup 요약 `SummaryExtractor`, CSP 헤더 in `global/security/` (R-05, 기능 명세 공통 규칙 보안)
- [ ] T015 [P] [W1] 프론트 라우터: 플랫폼 도메인 / 블로그 서브도메인 분기, API 클라이언트(쿠키 자동 전송 + CSRF 헤더, 401 → 플랫폼 로그인 후 원래 주소 복귀) in `frontend/src/app/`, `frontend/src/api/`
- [ ] T016 [W1] 연타 방지: `Idempotency-Key` 인터셉터, 키·첫 응답을 Redis에 짧은 TTL로 저장 in `global/web/` (R-09, POST-01, CMT-01)
- [ ] T016a [P] [W1] Redis 연결 설정, Spring Cache 저장소를 Redis로, 로컬 `docker-compose.yml`(MySQL 8, Redis) in `global/config/`, 저장소 루트 (R-02)

**중간 점검**: 인증·권한·Host 해석·가시성 판단이 준비됨

---

## 3단계: US1 가입하고 내 블로그 열기 (P1) 🎯 MVP

**목표**: 가입 → 블로그 개설 → 블로그 메인·사이드바 → 로그아웃
**독립 테스트**: quickstart "P0 한 바퀴" 1~2

- [ ] T017 [P] [US1] [W1] 이메일 인증 코드 발송·확인 (개발은 로그 출력, 메일 발송은 2주차로 미뤄도 됨) in `auth/` (OWN-01, 가입에 필요해 1주차)
- [ ] T018 [US1] [W1] 가입 API: 인증 코드 확인 후 회원 생성, 이메일·닉네임 중복, 비밀번호 8자+영문+숫자, bcrypt in `auth/` (AUTH-01)
- [ ] T019 [US1] [W1] 로그인 API: 실패 문구 통일, 정지 회원 안내, 토큰 발급 in `auth/` (AUTH-01)
- [ ] T020 [US1] [W1] 로그아웃: 모든 블로그 주소에서 로그아웃 상태 (쿠키 삭제 + 토큰 무효화) (AUTH-02)
- [ ] T021 [P] [US1] [W1] `blog` 엔티티(address UNIQUE, is_primary, moved_to_blog_id, deleted_at) in `blog/`
- [ ] T022 [US1] [W1] 주소 확인 API(정규식·예약어·중복, 삭제된 주소 포함) + 개설 API(활성 5개 한도, 첫 블로그 대표) in `blog/` (BLOG-01)
- [ ] T023 [US1] [W1] 블로그 정보 조회·수정 API (주소 수정 불가) in `blog/` (BLOG-02)
- [ ] T024 [US1] [W1] 블로그 메인 글 목록 API(published_at DESC, id DESC, 페이지 10, 가시성 조건) in `post/` (BLOG-03)
- [ ] T025 [US1] [W1] 사이드바 API: 이름·소개, 카테고리·글 수(CAT-03 전에는 한 단계, '미분류'는 글이 없으면 숨김), 최근 글 5, 최근 댓글 5 (볼 수 없는 글과 그 댓글 제외) in `blog/` (BLOG-04)
- [ ] T026 [P] [US1] [W1] 화면: 가입, 로그인, 블로그 개설(주소 변경 불가 안내), 블로그 메인, 사이드바, 블로그 설정 in `frontend/src/pages/`
- [ ] T027 [US1] [W1] 통합 테스트: 주소 규칙·중복·삭제된 주소 거절, 6번째 블로그 거절 in `src/test/.../blog/`

**중간 점검**: US1 단독 동작

---

## 4단계: US2 글 쓰고 발행·수정·삭제하기 (P1)

**목표**: 블로그 주인이 글을 발행·수정·삭제, 카테고리·태그·이미지
**독립 테스트**: quickstart "P0 한 바퀴" 3, spec US2 수용 시나리오

- [ ] T028 [P] [US2] [W1] `post`, `category` 엔티티 in `post/`, `category/`
- [ ] T029 [US2] [W1] 카테고리 추가·이름 변경(1~30자)·삭제(소속 글 미분류로) API in `category/` (CAT-01)
- [ ] T030 [US2] [W1] 카테고리별 글 목록 `/category/{id}` (상위는 하위 포함·합산, CAT-03 이후 적용) in `post/` (CAT-02)
- [ ] T031 [US2] [W1] 글 발행 API: 제목 1~200자 필수, 주제·카테고리(기본 미분류)·공개 범위, 서버 정화, 요약 생성, published_at 기록, Idempotency-Key in `post/` (POST-01)
- [ ] T032 [US2] [W1] 글 수정 API: 주인만, 주소·published_at·수치·순서 불변 in `post/` (POST-02)
- [ ] T033 [US2] [W1] 글 삭제 API: 주인만, 소프트 삭제(`deleted_at`), 댓글·공감·알림 함께 처리(한 트랜잭션), 글 수·공감 수에서 바로 빠짐 in `post/` (POST-03)
- [ ] T034 [US2] [W1] 공개 범위 변경 API (PUBLIC, PRIVATE; SUBSCRIBERS는 구독 이후) in `post/` (POST-06)
- [ ] T035 [P] [US2] [W1] 화면: Tiptap 에디터(허용 서식만), 글쓰기·수정, 카테고리 관리, 삭제 확인 in `frontend/src/components/editor/`, `pages/manage/`
- [ ] T036 [US2] [W2a] 이미지 업로드 API: 10MB, 확장자+실제 내용 검사(위장 파일 거절), UUID 파일명으로 `app.upload.dir`(개발: `/Users/chosun-nhn54/IdeaProjects/blog/uploads`)에 저장, `/uploads/**`로 서빙, 리사이즈·썸네일, EXIF 방향 보정, GIF 유지 in `image/` (POST-05, plan 저장소)
- [ ] T037 [US2] [W2a] 에디터 이미지 버튼 ↔ 업로드 API 연결, 여러 장은 고른 순서대로 in `frontend/src/components/editor/` (POST-05)
- [ ] T038 [P] [US2] [W2a] `tag`, `post_tag` 엔티티, 글 작성·수정 시 태그 최대 10개·중복 제거·없는 이름 자동 생성 in `tag/` (TAG-01)
- [ ] T039 [US2] [W2a] 태그별 글 목록 `/tag/{name}` in `post/` (TAG-02)
- [ ] T040 [US2] [W1] 통합 테스트: 수정 후 주소·순서 불변, 카테고리 삭제 시 미분류, 비공개 전환 시 목록·개수에서 빠짐 in `src/test/.../post/`

**중간 점검**: US1 + US2 동작

---

## 5단계: US3 독자가 발견하고 읽고 반응하기 (P1)

**목표**: 홈 → 글 상세 → 검색 → 댓글·공감
**독립 테스트**: quickstart "P0 한 바퀴" 4~6

- [ ] T041 [US3] [W1] 글 상세 API: 글 가시성 판단(질문 4개), 다른 블로그 소속이면 301/404, 주인에게만 수정·삭제 플래그 in `post/` (POST-04)
- [ ] T042 [US3] [W1] 홈 최신 글 API: 커서 `(published_at, id)`, 20개, 숨긴 글·블로그 제외 in `home/` (HOME-01)
- [ ] T043 [P] [US3] [W1] `comment` 엔티티 (parent_id, deleted_at, is_secret, is_blinded) in `comment/`
- [ ] T044 [US3] [W1] 댓글 작성(회원만, 1~1,000자(채움), Idempotency-Key)·조회(작성순 더보기 20)·본인 삭제·주인 삭제 API in `comment/` (CMT-01, CMT-02)
- [ ] T045 [P] [US3] [W1] 화면: 홈, 글 상세(DOMPurify 후 렌더), 댓글 in `frontend/src/pages/`
- [ ] T046 [US3] [W2a] 공감 API: PUT/DELETE 멱등, `post_like` UNIQUE, like_count 트랜잭션 갱신 in `reaction/` (SOC-01)
- [ ] T047 [US3] [W2a] 블로그 내 검색 API: 제목·본문·태그, 대소문자 무시, trim·공백만 거절, 최신순 페이지 10, 가시성 조건 in `search/` (SRCH-01)
- [ ] T048 [P] [US3] [W2a] 화면: 공감 버튼(즉시 반영), 블로그 검색(검색어 유지, 결과 주소 공유 가능) in `frontend/src/`
- [ ] T049 [US3] [W2a] 통합 테스트: 비회원 댓글·공감 401, 공감 연타 1개, 댓글 수·공감 수 일치 in `src/test/`

---

## 6단계: US4 접근 제어·오류·관리자 영역 (P1)

**목표**: 화면이 아니라 서버에서 권한이 지켜짐
**독립 테스트**: quickstart "권한·가시성" 표

- [ ] T050 [US4] [W1] 서비스 계층 주인 검사 공통화 `BlogOwnerGuard` in `global/` (COM-01)
- [ ] T051 [P] [US4] [W1] 화면: 404·403 페이지, 입력 오류 항목 표시(입력 유지), 관리자 영역 진입 보호 `/admin` in `frontend/src/` (COM-02, ADMIN-01)
- [ ] T052 [US4] [W1] 통합 테스트: 남의 비공개 글 404, 남의 수정 403, 일반 회원 `/api/admin/**` 403, 다른 블로그 주소+글 번호 301/404, 500 응답에 스택 없음 in `src/test/.../security/`

**중간 점검**: P0 24개 중 1주차 분량 완성 → "가입 → 개설 → 발행 → 홈 발견 → 읽기·댓글" 한 바퀴

---

## 7단계: US5 글쓰기·블로그 정리 편의 (P2) — 2주 범위 일부

- [ ] T053 [US5] [W2a] `view_log` 기록 + 중복 조회 판정(같은 사용자 5분) + view_count in `post/` (POST-09)
- [ ] T054 [US5] [W2a] 사이드바 태그 목록·글 수 in `blog/` (TAG-03)
- [ ] T055 [US5] [W2b] 회원정보 수정: 닉네임·프로필·비밀번호 in `member/` (AUTH-05)
- [ ] T056 [US5] [W2b] 주제 enum, 글 작성 시 주제 선택 in `post/` (POST-11, 밀리면 확장으로)
- [ ] T057 [US5] 이전·다음 글(볼 수 없는 글 건너뜀) (POST-10)
- [ ] T058 [US5] 대표 이미지 선택, 미지정 시 첫 이미지 (POST-07)
- [ ] T059 [US5] 임시저장 수동·자동(1분) + 이어쓰기 (POST-08)
- [ ] T060 [US5] [W2b] 하위 카테고리 2단계, 사이드바 트리와 상위 목록 합산 켜기 in `category/`, `blog/` (CAT-03, 원본 검토 6)
- [ ] T060a [US5] 드래그로 순서·상하위 변경 (CAT-04)
- [ ] T061 [US5] 블로그 없는 회원 글쓰기 → 개설 안내 (AUTH-04)
- [ ] T062 [US5] 로그인 유지(브라우저를 닫아도 유지, 만료가 긴 Refresh Token 쿠키) (AUTH-03)

## 8단계: US7 탐색 (P2) — 2주 범위 일부

- [ ] T063 [US7] [W2a] 인기 점수 계산(최근 1시간 조회×1 + 공감×3 + 댓글×5, 가중치는 설정값)과 인기 글 API: 공개 글 상위 10, @Cacheable(Redis) 5분 in `home/` (HOME-02, R-12)
- [ ] T064 [US7] [W2b] 주제별 글 API: 주제 탭별 인기 점수 순 6개, 모자라면 최신 글로 채움, 캐시 5분 in `home/` (HOME-03)
- [ ] T065 [US7] 전체 검색 (SRCH-02)
- [ ] T066 [US7] 댓글 수정 (CMT-03), 방명록 (CMT-04)

## 9단계: US8 내 블로그 관리 (P2) — 2주 범위 일부

- [ ] T067 [US8] [W2b] 내 글 관리 API·화면: 상태·카테고리 필터, 검색, 페이지 20, 블라인드 사유 표시(최신 BLIND 관리 이력), 일괄 공개 범위 변경·삭제 in `manage/` (MNG-01)
- [ ] T068 [US8] 댓글 관리 (MNG-02)

## 10단계: US11 일부 앞당김 (P3)

- [ ] T069 [US11] [W2a] 답글 1단계, 답글 있는 댓글 삭제 시 '삭제된 댓글입니다' 표시 in `comment/` (CMT-05)

---

## 10a단계: US15 비슷한 글 추천 (OWN-06, 도전 과제) [W2b]

**목표**: 글 상세 아래 비슷한 글 몇 개. 일정이 밀리면 이 단계 전체를 백로그로 돌린다(다른 단계와 의존 없음).

- [ ] T069a [W2b] docker compose에 PostgreSQL + pgvector 추가, 두 번째 DataSource 설정(추천 전용) in `recommend/config/` (R-02)
- [ ] T069b [W2b] `post_embedding(post_id, embedding vector)` 테이블, 발행·수정 시 비동기로 임베딩 생성·저장 in `recommend/` (임베딩 방법은 R-02 미결정)
- [ ] T069c [W2b] 비슷한 글 API: 코사인 유사도 상위 N에서 보는 사람이 볼 수 없는 글 제외(가시성 판단 재사용) in `recommend/`
- [ ] T069d [P] [W2b] 글 상세 하단 '비슷한 글' 영역 in `frontend/src/pages/post/`

---

## 11단계: 마무리 (Polish) [W2b]

- [ ] T070 [W2b] 테스트 보강: quickstart 전 항목을 MockMvc·수동으로 확인
- [ ] T071 [P] [W2b] 모바일 360px 레이아웃 확인 (비기능 반응형)
- [ ] T072 [P] [W2b] 글 상세 Open Graph 메타 태그 (서버가 index.html에 주입) (비기능 공유 미리보기, 원본 4.5)
- [ ] T073 [W2b] 버그 수정, 문서 정리

---

## 2주 범위 밖 (백로그)

| 스토리 | 기능 |
| --- | --- |
| US5, US10 | 소셜 로그인(AUTH-01 P1, R-07), 소셜 연동(OWN-03), 비밀번호 재설정(OWN-02), 개설 안내(AUTH-04), 로그인 유지 화면(AUTH-03) |
| US6 | 구독·피드·구독자 수·공유 (SUB-01~03, SOC-02) |
| US9 | 회원 정지 화면·API, 게시물 블라인드 (ADMIN-02, 03) |
| US10 | 블로그 이사·삭제·대표·꾸미기(사이드바 모듈 순서·표시 포함, 아래 "백로그: 사이드바"), 탈퇴(블로그·글·댓글 모두 소프트 삭제, Q1) (BLOG-05~08, AUTH-06, R-08) |
| US11 | 구독자 공개(구독 필요. 목록에서 빼고 링크로 열면 구독 안내, Q4), 예약 발행, 카테고리 비공개, 태그 관리, 비밀댓글, 댓글 허용 |
| US12~14 | 알림, 통계, 스팸, 신고, 블로그 제한, 공지·이력·대시보드. 통계·스팸 작업은 아래 "백로그: US13" |
| US15 | 같은 카테고리 다른 글(OWN-05). 비슷한 글 추천(OWN-06)은 10a단계(도전 과제) |
| US16 | 저장, 추천 블로그, 인기 블로거, 랭킹 전체보기 (SOC-03, SUB-06, HOME-04, HOME-05). 작업은 아래 "백로그: US16" |

맞구독(SUB-05)은 2026-10-08 지원 결정으로 넣지 않는다.

### 백로그: US16 저장한 글과 랭킹 (2026-10-08 방식 확정)

- [ ] T074 [US16] `post_bookmark` 엔티티(UNIQUE(member_id, post_id), 저장 시 제목·블로그 이름 스냅숏), 저장·취소 멱등 API in `bookmark/` (SOC-03)
- [ ] T075 [US16] 저장한 글 목록 API: 커서 20, 볼 수 없는 글은 스냅숏 제목과 `visible:false`만, 가시성 판단 재사용 in `bookmark/` (SOC-03)
- [ ] T076 [P] [US16] 화면: 글 상세 저장 버튼, 마이페이지 "저장한 글"(볼 수 없는 글 표시·안내, 항목별 저장 취소) in `frontend/src/` (SOC-03)
- [ ] T077 [US16] 탈퇴 처리에 저장 삭제 추가 (AUTH-06과 함께, SOC-03)
- [ ] T078 [US16] 인기 글 스냅숏을 상위 100개·계산 시각 포함으로 바꾸기 (HOME-02, R-13)
- [ ] T079 [US16] 블로그 점수 스케줄러(1시간, 7일 창), Redis 스냅숏 100, view_log 7일 보관 정리 작업 in `ranking/` (HOME-04, R-13)
- [ ] T080 [US16] API: 홈 인기 블로거 5, 추천 블로그 5(자기·구독 중 제외), 랭킹 전체보기(스냅숏 시각 불일치 시 409) in `ranking/` (HOME-04, SUB-06, HOME-05)
- [ ] T081 [P] [US16] 화면: 홈 인기 블로거, 구독 피드의 추천 블로그(빈 피드 포함), `/ranking` 탭 2개와 기준 시각 표시 in `frontend/src/` (HOME-04, SUB-06, HOME-05)

---

### 백로그: US13 방문 통계와 스팸 차단 (2026-10-08 ERD 반영)

- [ ] T082 [US13] `blog_visit` 기록(블로그·날짜·방문자 하루 1회, 주인 제외, Referer로 유입 종류·사이트), 새벽 집계 작업(`blog_daily_stat`, `blog_referrer_daily`, `blog.total_visitor_count`), 7일 지난 방문 기록 삭제 in `manage/stats/` (MNG-03)
- [ ] T083 [US13] 통계 API: 관리 홈(오늘·어제·누적, 최근 댓글·글 요약), 일·주·월 그래프, 인기 글(누적·7일), 유입 경로 in `manage/stats/` (MNG-03)
- [ ] T084 [US13] `blog_blocked_member`, `blog_banned_word` 엔티티와 관리 API(차단 시 기존 구독 삭제, 금칙어 100개), 댓글·방명록 작성과 구독에 차단·금칙어 검사 연결 in `manage/` (MNG-04)
- [ ] T085 [P] [US13] 화면: 관리 홈 통계, 통계 그래프·유입 경로, 차단 회원·금칙어 관리, 댓글 관리에서 바로 차단 in `frontend/src/pages/manage/` (MNG-03, MNG-04)

### 백로그: 사이드바 모듈과 포인트 색 (2026-10-08 지원 결정)

- [ ] T086 [US10] `blog_sidebar_module` 엔티티, 블로그 개설 시 8개 행 생성(새 3종은 숨김)과 기존 블로그 채우기, 사이드바 API를 모듈 순서·표시 여부대로 내려 주기, 방문자 수·인기 글 5·구독 모듈 데이터, 모듈 조회·전체 교체 API(PROFILE 숨김·중복·누락 400), `blog.accent_color` 저장 in `blog/` (BLOG-04, BLOG-05)
- [ ] T087 [P] [US10] 화면: 블로그 꾸미기에서 사이드바 모듈 끌어서 순서 바꾸기와 보이기·숨기기, 포인트 색 6색 고르기(스킨 CSS 변수 하나로 적용) in `frontend/src/pages/manage/` (BLOG-05)

## 의존 관계와 실행 순서

- 프로젝트 준비 → 기반 작업(T005~T016) → US1 → US2 → US3, US4는 기반 작업 직후 병행 가능
- T009 주소 해석, T011 가시성, T050 주인 검사는 T021·T028(엔티티)에 의존
- T031 발행은 T014(정화)·T016(연타 방지)에 의존
- T036 이미지 업로드 → T037 에디터 연결
- T053 view_log, T046 공감, T044 댓글 → T063 인기 점수·인기 글 → T064 주제별 글
- T016a(Redis) → T016, T063, T064
- 10a단계는 T031(발행)과 T011(가시성)에만 의존하고, 다른 작업이 기다리지 않는다
- T046 공감, T047 검색은 US2 글·태그(T038) 이후

## 구현 전략

1. **1주차**: 스텝 1~6 ([W1] 전부) → P0 한 바퀴 시연 (quickstart 1~6, 권한 표)
2. **2주차 전반**: 스텝 7~8. 이미지, 공감, 답글, 태그·검색, 조회수·인기 글
3. **2주차 후반**: 스텝 9~11. 회원정보, 내 글 관리, 주제, 하위 카테고리, (도전) 비슷한 글 추천, 테스트·문서
4. 스텝이 끝날 때마다 위 표의 "확인할 것"으로 지원이 확인하고 PR을 병합한다. 커밋 메시지에 기능 코드를 쓴다 (constitution VII)
