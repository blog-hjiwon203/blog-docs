# Research: 티스토리형 블로그 (지원)

각 항목은 **Decision / Rationale / Alternatives** 순서다. 출처는 지원 개인 설계 문서의 장 번호.

## R-01 버전과 테스트 도구 (기본값)

- **Decision**: Java 17, Spring Boot 3.x, React 18 + Vite. 테스트는 JUnit 5, Spring Boot Test, MockMvc, 프론트는 Vitest 최소.
- **Rationale**: 원 문서에 버전·테스트 도구가 없어 Spring Boot 3 기본 조합으로 둠. 바꾸면 이 항목만 고친다.

## R-02 운영 저장소 — [NEEDS CLARIFICATION]

- 원 문서 3장: "운영: MySQL, Redis, PostgreSQL".
- **현재 가정**: 주 DB는 MySQL. Redis는 캐시·토큰 차단 목록 후보, PostgreSQL은 '비슷한 글 추천'(벡터 검색, P2) 후보로 보임.
- **필요한 결정**: Redis·PostgreSQL을 2주 범위에 넣을지. 넣지 않으면 캐시는 Spring 기본(Caffeine/ConcurrentMap)으로 시작.

## R-03 인증 — 일부 미결정

- **Decision**: JWT Access Token, `Authorization: Bearer`. 비밀번호 bcrypt. 토큰 없음 401, 권한 없음 403, 남의 비공개 404.
- **Open** (원 문서 10장, 인증 학습 후 확정): 서브도메인 간 로그인 공유(상위 도메인 HttpOnly 쿠키 등), 로그인 유지(Refresh Token), 로그아웃 시 토큰 처리, 정지 회원의 기존 토큰 차단(요청마다 상태 확인 등), 쿠키 사용 시 SameSite + CSRF 토큰.
- **Note**: spec V3 규칙 "여러 블로그를 오가도 로그인 유지"를 지키려면 서브도메인 간 공유 방식이 반드시 정해져야 한다. localStorage + Bearer는 출처(origin)별이라 서브도메인마다 따로 저장됨.

## R-04 블로그 주소 해석 (4.2, 6장 ①)

- **Decision**: 정규식 `^[a-z0-9][a-z0-9-]{2,30}[a-z0-9]$`, 예약어(www, api, admin, static, mail, login 등) 거절. 요청 Host에서 서브도메인을 읽어 블로그 조회. `blog.com`, `www.blog.com`은 플랫폼 화면.
- 화면 주소는 서버가 먼저 확인(없으면 404, 이사했으면 301, 다른 블로그 소속 글이면 301)한 뒤 `index.html`을 준다. 리다이렉트를 서버가 하는 이유는 검색엔진도 따라가게 하기 위함.
- `/api/**`는 같은 출처의 상대 경로라 CORS 설정이 필요 없다.

## R-05 에디터와 XSS (7.4, 4.5)

- **Decision**: Tiptap(React, MIT), 본문 HTML 저장. 저장 전 서버에서 OWASP Java HTML Sanitizer로 허용 목록 정화(문단 제목, 굵게·기울임, 목록, 인용, 코드 블록, http/https 링크, 자체 업로드 경로 이미지). script·이벤트 속성·style 제거. 출력 시 DOMPurify로 한 번 더. 본문 외 입력은 React 자동 이스케이프만, `dangerouslySetInnerHTML`은 DOMPurify를 거친 본문에만. CSP로 인라인 스크립트 차단. 목록 요약은 jsoup으로 태그 제거.
- **Alternatives**: 마크다운(예전 선택) → WYSIWYG로 변경. Lucy XSS Filter·ESAPI는 쓰지 않음.

## R-06 페이지네이션 (4.4)

- **Decision**: 기본 offset(`?page=0&size=10`, 응답 content/page/size/totalElements/totalPages). 홈 최신 글·구독 피드는 커서 `(published_at, id)` 이후. size 1~50 보정, 음수 page는 0, 마지막 초과는 빈 content. '최신순' = published_at 내림차순, 같으면 id 내림차순. 화면 번호는 10개씩 묶음.

| 목록 | 방식 | 크기 | 정렬 |
| --- | --- | --- | --- |
| 블로그 글 목록(카테고리·태그 포함), 블로그 내 검색 | 페이지 | 10 | 최신순 |
| 홈 최신 글, 구독 피드 | 커서 더보기 | 20 | 최신순 |
| 내 글 관리 | 페이지 | 20 | 최신순 |
| 댓글 | 더보기 | 20 (답글은 부모에 포함) | 작성순 |
| 방명록 | 페이지 | 20 | 최신순 |
| 인기 글 | 없음 | 상위 10 | 인기 점수 |
| 주제별 글 | 없음 | 6 | 인기 점수 |
| 사이드바 최근 글·댓글 | 없음 | 각 5 | 최신순 |
| 카테고리·태그 목록 | 없음 | 전체 | sort_order / 글 수 |

## R-07 계정·소셜 연동 (4.6)

- **Decision**: 처음 가입한 방식이 기본 수단. 묶는 길은 "로그인 상태에서 마이페이지 소셜 연동" 하나뿐이고, 더할 수 있는 것은 소셜뿐. 이메일이 같다고 합치지 않고 충돌하면 거절.
- 소셜 신규 가입: 닉네임 확인 후 member(email·password NULL) + social_account를 한 트랜잭션. 제공사 이메일은 저장하지 않음.
- 연동 거절: 이미 다른 회원에 연결된 소셜 계정, 같은 제공사 중복. 해제 후 로그인 수단이 남지 않으면 거절.
- 모든 로그인 경로에서 member.status 먼저 확인(SUSPENDED → 사유·기한 안내, WITHDRAWN → 없는 계정).
- OAuth state 검증 + 복귀 주소는 우리 서비스 주소만 허용.
- 이메일 로그인 실패 문구는 가입 여부를 드러내지 않게 통일.
- 탈퇴: 본인 확인 후 한 트랜잭션으로 status=WITHDRAWN, withdrawn_at, email·password_hash 비우기, social_account 행 직접 삭제, 제공사 연결 해제. 블로그·글·댓글은 spec Q2 결정 전까지 남김.

## R-08 블로그 이사·삭제 (4.2)

- 이사 대상은 같은 회원의 활성 블로그만(자기 자신·삭제된 블로그 불가). 옛 블로그 홈은 301, 주인은 관리 화면 접근 가능.
- 글 이동과 이사는 별개: 옮긴 글만 301, 옮기지 않은 글은 옛 블로그에 남음. 옮긴 글 카테고리는 '미분류', 태그는 이름으로 대상 블로그 태그에 다시 연결.
- 연쇄 이사 A→B→C면 A의 대상도 C로 갱신(리다이렉트 1회, 순환 없음).
- 삭제는 소프트 삭제(deleted_at). 개설 한도 5개는 활성 블로그만 셈.
- 이사 간 새 블로그(B)를 삭제하면 A의 리다이렉트도 끊기고 없는 블로그.

## R-09 연타 방지 — [NEEDS CLARIFICATION]

- spec FR-025, FR-048, FR-055, FR-058, NFR-003 요구. 원 문서: "버튼 비활성화 + 서버 측 중복 방지(10장)".
- **후보**: (a) 클라이언트가 만든 Idempotency-Key 헤더를 짧은 TTL로 저장, (b) 공감·구독은 DB UNIQUE 제약(member_id, post_id / member_id, blog_id)으로 충분, 발행·댓글은 (a).
- **권장 기본값**: 공감·구독은 UNIQUE 제약, 발행·댓글은 Idempotency-Key. 확정 전까지 이 기본값으로 tasks에 넣었다.

## R-10 홈 섹션 API (5.10)

- 섹션별 API를 따로 두고 프론트에서 Promise.all. 인기 글·주제별 글은 @Cacheable TTL 5분. 통합 `/api/home`은 섹션 5개 초과 또는 앱이 생기면 검토.

## R-11 남은 결정 (원 문서 10장)

| 항목 | 상태 |
| --- | --- |
| 구독자 공개 글을 비구독자의 블로그 목록에 표시할지 | 미정 (V8) |
| 비회원 댓글 | 보류 (spec과 충돌) |
| 글 삭제 소프트/하드, 조회수 중복 판정 시간 | 미정 |
| 예전 '블로그 커스텀'(사이드바 구성 변경) | 빼 둠 (BLOG-04 고정 사이드바와 충돌) |
| ERD·API 명세 탭의 통합 ID 갱신 | 할 일 (contracts/rest-api.md가 초안) |
