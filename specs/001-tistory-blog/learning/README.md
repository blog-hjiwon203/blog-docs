# 구현 노트와 학습 자료 (지원 공부용)

> **이 문서는?** 이 프로젝트를 만들며 쓴 기술과 개념을 공부하기 위한 자료다. 두 종류가 있다.
> - **개념 문서**(`concepts/`): 개념 하나를 처음부터 설명한다. 왜 필요한지, 어떻게 동작하는지, 이 프로젝트 코드에서 어떻게 쓰였는지, 직접 해 볼 실습과 확인 문제까지 담았다.
> - **스텝 노트**(`step-NN.md`): 그 스텝에서 무엇을 만들었는지, 이해하려면 어떤 개념 문서를 어떤 순서로 읽으면 되는지, 막혔던 점을 정리한 지도다.

코드 경로는 코드 저장소(`~/IdeaProjects/blog`, GitHub [AIP-1/blog-basic-AIGJ_01_017-blog](https://github.com/AIP-1/blog-basic-AIGJ_01_017-blog)) 기준이다.

## 스텝 노트

| 스텝 | 노트 | 만든 것 |
| --- | --- | --- |
| 1 | [실행 환경](./step-01.md) | Docker로 MySQL·Redis, Flyway로 테이블 26개, Testcontainers, Vite |
| 2 | [모든 기능이 쓰는 바닥](./step-02.md) | 엔티티, 오류 응답, 페이지 처리, 관리자 계정, 본문 정화 |
| 3 | [로그인·주소·권한 판단 장치](./step-03.md) | JWT 쿠키 인증, 서브도메인 해석, 글 가시성, 연타 방지, 프론트 라우터 |
| 4 | [가입과 블로그 개설](./step-04.md) | 이메일 인증, 가입·로그인·로그아웃, 블로그 개설·정보, 블로그 메인 글 목록, 사이드바, 첫 화면들 |
| 5 | [글쓰기](./step-05.md) | 카테고리 관리, 글 발행·수정·삭제·공개 범위, Tiptap 에디터 |
| 6 | [읽기·댓글·권한 (P0 완성)](./step-06.md) | 글 상세·이전·다음 글, 홈 최신 글, 댓글, 오류 화면, 관리자 영역 보호, 권한 시험 |
| 7 | [이미지·태그·공감·검색·답글](./step-07.md) | 사진 올리기와 썸네일, 태그와 태그별 목록, 공감, 블로그 안 검색, 답글, 동시성 버그 두 개 |
| 8 | [조회수·인기 글](./step-08.md) | 조회 기록과 5분 중복 판정, 방문자 쿠키, 사이드바 태그 목록, 인기 점수 집계와 5분 Redis 캐시 |
| 9 | [회원정보·주제·하위 카테고리·내 글 관리](./step-09.md) | 닉네임·사진·비밀번호 바꾸기, 비밀번호·인증 코드 시도 제한, 글 주제와 홈 주제별 글, 하위 카테고리, 내 글 거르기·일괄 처리, 테스트 간섭 |
| 9a | [보완: 이미지 확장자 검사, 태그 중간 엔티티](./step-09a.md) | 스텝 1~7 대조에서 나온 빈 곳: 확장자 허용 목록, EXIF 테스트, `@ManyToMany`를 `PostTag` 엔티티로 |
| 10 | [비슷한 글 추천](./step-10.md) | Ollama bge-m3 임베딩, PostgreSQL pgvector, 두 번째 DB, 커밋 뒤 비동기, 비슷한 글 API와 카드 |
| 11 | [마무리](./step-11.md) | quickstart 시나리오 테스트, 휴대폰 360px 점검과 표→카드, 글 공유 미리보기(Open Graph), README·quickstart 정리 |
| 12 | [글쓰기 버튼 안내·로그인 유지](./step-12.md) | 대표 블로그 글쓰기 또는 개설 안내 → 만든 뒤 글쓰기, Access 재발급 API, 브라우저 재시작 시나리오 테스트, 로그인 유지 안내 |
| 13 | [임시저장·대표 이미지](./step-13.md) | 제목 없이 임시저장, 1분 자동 저장, 불러와 이어 쓰고 발행, 대표 이미지 고르기와 본문 첫 이미지 기본값, 보완: 마이페이지 내 블로그(두 번째 블로그 입구, 대표 바꾸기) |

## 개념 문서

모든 개념 문서는 같은 순서로 되어 있다: 배우는 것 → 왜 필요한가 → 기본 개념 → 동작 원리 → 이 프로젝트에서는 → 자주 하는 실수 → 직접 해 보기 → 확인 문제 → 더 읽을거리.

### 1부. 환경과 도구

| 문서 | 다루는 것 |
| --- | --- |
| [01 Spring Boot 기초](./concepts/01-spring-boot-basics.md) | 스프링 컨테이너와 빈, 의존성 주입, 스타터와 자동 설정, Maven, Spring Boot 4에서 바뀐 점, `@ConfigurationProperties` |
| [02 설정 파일과 프로필](./concepts/02-configuration-profiles.md) | `application.yml`, dev/prod 프로필, 설정 우선순위, 환경 변수, 이 프로젝트의 설정값 하나하나 |
| [03 Flyway와 스키마 마이그레이션](./concepts/03-flyway-migration.md) | 마이그레이션, 체크섬, `ddl-auto`, ERD → schema.sql → V1 흐름 |
| [04 Docker와 Docker Compose](./concepts/04-docker-compose.md) | 이미지와 컨테이너, compose 파일 항목, 볼륨, 포트, healthcheck |
| [05 Spring 테스트와 Testcontainers](./concepts/05-spring-testing.md) | 단위·통합·슬라이스 테스트, 컨텍스트 캐싱, `@ServiceConnection`, MockMvc |

### 2부. 데이터와 웹

| 문서 | 다루는 것 |
| --- | --- |
| [06 JPA 엔티티 매핑](./concepts/06-jpa-entity-mapping.md) | ORM, 영속성 컨텍스트, 연관관계와 LAZY, N+1과 join fetch, Auditing, Specification |
| [07 Spring MVC 요청 흐름과 예외 처리](./concepts/07-spring-mvc-exception-handling.md) | DispatcherServlet, 필터·인터셉터·인자 해석기, `@RestControllerAdvice`, 콘텐츠 협상, HTTP 상태 코드 |
| [08 페이지네이션](./concepts/08-pagination.md) | offset과 keyset(커서), 정렬 안정성, 인덱스, Spring Data `Pageable` |
| [09 비밀번호 해시와 bcrypt](./concepts/09-password-hashing.md) | 해시와 암호화, salt, cost, bcrypt 구조와 72바이트 제한 |
| [22 입력 검증과 JSON 바인딩](./concepts/22-bean-validation.md) | Jackson 3 바인딩, Bean Validation, `@Valid`와 상태 코드 순서, 기본형 칸 누락 |
| [29 댓글 설계](./concepts/29-comments-design.md) | 글에 딸린 데이터의 권한, 보는 사람마다 다른 댓글, 댓글 수, 연타 두 겹, 답글 한 단계 |
| [31 태그와 다대다 관계](./concepts/31-tags-many-to-many.md) | `@ManyToMany`와 조인 테이블, 이름 정리 규칙, 태그별 목록, 태그 입력 칸 |
| [32 블로그 안 검색: LIKE와 비정규화 칸](./concepts/32-search-like.md) | 글자만 담은 칸과 마이그레이션, LIKE 이스케이프, EXISTS 서브쿼리, 인덱스 한계, 검색어를 주소에 |
| [47 임시저장과 자동 저장](./concepts/47-draft-autosave.md) | 글의 상태와 되돌릴 수 없는 이동, 상태별 검증, 처음 POST 그 뒤 PUT, `setInterval`과 낡은 값·`useRef`, 저장 줄 세우기, 스냅숏 |
| [48 대표 이미지](./concepts/48-representative-image.md) | 고른 번호 검증(본문 안에 있나), `null` = 자동, `ON DELETE SET NULL`, 한 페이지 쿼리 두 번, 파생 값 |
| [27 소프트 삭제와 일괄 수정](./concepts/27-soft-delete-bulk-update.md) | 소프트 삭제, 딸린 데이터 처리, 변경 감지, `@Modifying`, 수정 시각 지키기 |
| [23 트랜잭션과 동시성](./concepts/23-transactions-locking.md) | `@Transactional`, 경쟁 조건, 비관적 잠금(`FOR UPDATE`), UNIQUE 제약, 동시성 테스트, 대표 블로그 바꾸기(끄고 flush 켜기) |
| [33 격리 수준, 스냅샷, 데드락](./concepts/33-isolation-deadlock.md) | 격리 수준과 MVCC, 일관된 읽기와 잠금 읽기, 외래 키 공유 잠금과 데드락, 공감 버튼에서 겪은 두 버그 |
| [34 조회수: 누가 봤는지, 5분 중복, 동시 새로고침](./concepts/34-view-count.md) | 조회자 키와 방문자 쿠키, 시간 창 중복 판정, 기록 테이블과 누적 칸, 잠금을 첫 문장으로, StrictMode effect 두 번 |
| [36 집계 쿼리로 순위 매기기](./concepts/36-ranking-aggregation.md) | `GROUP BY`·`SUM`, `UNION ALL`로 가중치 점수, 시각 인덱스, 동점 처리, `NamedParameterJdbcTemplate`, 태그별 글 수 |
| [43 글 공유 미리보기: Open Graph](./concepts/43-open-graph-preview.md) | 봇은 자바스크립트를 안 돌린다, 서버가 넣는 og 태그, 이스케이프, 절대 주소, charset, 비회원 기준 |
| [44 휴대폰 화면: 반응형과 헤드리스 Chrome 점검](./concepts/44-mobile-responsive-check.md) | viewport, 미디어 쿼리, `minmax(0, 1fr)`, 표를 카드로, CDP로 360px 화면 재기·스크린숏 |
| [41 임베딩과 벡터 검색](./concepts/41-embedding-vector-search.md) | 임베딩, 코사인 유사도·거리, pgvector `<=>`와 HNSW, Ollama bge-m3, 추천에서 볼 수 없는 글 거르기, 가짜 임베딩 테스트 |
| [42 두 번째 DB와 커밋 뒤 비동기 처리](./concepts/42-second-db-async-events.md) | `@Bean(defaultCandidate = false)` DataSource, DB별 Flyway, 최종 일관성, 이벤트·`@TransactionalEventListener`·`@Async`, 비동기 테스트 |
| [37 거르기 조건이 있는 목록과 일괄 처리](./concepts/37-filtered-list-bulk-actions.md) | 동적 Specification, `COALESCE` 정렬과 개수 쿼리, 주인 확인 뒤 값 검사, 일괄 변경·삭제, `LikePatterns`, 주소에 둔 거르기 조건 |
| [39 계층 데이터: 카테고리 2단계와 주제](./concepts/39-category-hierarchy.md) | 자기 참조 트리, 2단계 제한, 계산 칸 `parent_key`와 UNIQUE, 주제 enum, 주제별 글 채우기 |
| [30 이미지 업로드와 처리](./concepts/30-image-upload.md) | multipart, 크기 제한, 매직 넘버, Thumbnailator·EXIF, WebP 플러그인, `/uploads` 내보내기와 캐시, 목록 썸네일 |

### 3부. 보안

| 문서 | 다루는 것 |
| --- | --- |
| [10 HTTP 쿠키](./concepts/10-http-cookies.md) | 쿠키 속성 하나하나, 세션과 토큰, 서브도메인 쿠키 공유 |
| [11 JWT와 로그인 토큰 설계](./concepts/11-jwt.md) | JWT 구조와 서명, Access/Refresh, 무효화, 무활동 로그아웃 |
| [12 Spring Security 필터 체인](./concepts/12-spring-security-filter-chain.md) | FilterChainProxy, SecurityContext, 인가 설정, 메서드 보안, 커스텀 필터 |
| [13 CSRF, SameSite, CORS](./concepts/13-csrf-samesite-cors.md) | 출처와 사이트, CSRF 공격과 대책, preflight, CORS가 아닌 것 |
| [14 XSS, HTML 정화, CSP](./concepts/14-xss-sanitize-csp.md) | XSS 종류, 허용 목록 정화, CSP 지시어 |
| [20 이메일 인증 코드와 요청 제한](./concepts/20-email-verification.md) | 인증 코드 설계, `SecureRandom`, Redis로 1분 재요청 제한, 메일 발송 인터페이스 |
| [40 시도 횟수 제한](./concepts/40-attempt-limit.md) | 온라인 무차별 대입, 대상별(15분·5번)·IP별(20번) 실패 횟수, Redis `INCR`로 동시 시도까지 막기, 가입 여부 숨기기, 잠금 악용, 프록시 뒤의 IP |
| [38 회원정보 수정](./concepts/38-member-profile-update.md) | PATCH 부분 수정, 나를 뺀 닉네임 중복, 지금 비밀번호 확인, IDOR(남의 것을 가리키는 번호), 마이페이지 |
| [21 가입·로그인·로그아웃 설계](./concepts/21-signup-login.md) | 가입 트랜잭션, 계정 열거·타이밍 공격 방어, 정지 안내, 로그아웃, 열린 리다이렉트 |
| [45 로그인 유지](./concepts/45-remember-me.md) | 세션 쿠키와 영속 쿠키, 브라우저 재시작, 미끄러지는 만료와 고정 만료, 필터 재발급과 재발급 API, 재시작 흉내 테스트 |

### 4부. 이 블로그의 구조와 프론트

| 문서 | 다루는 것 |
| --- | --- |
| [15 서브도메인과 Host 라우팅](./concepts/15-subdomain-host-routing.md) | DNS, `/etc/hosts`, Host 헤더, 멀티테넌시, 인자 해석기 |
| [16 인가와 가시성 판단](./concepts/16-authorization-visibility.md) | 인증과 인가, 존재를 숨기는 404, 정책 객체, sealed 타입과 switch |
| [17 멱등성과 Redis](./concepts/17-idempotency-redis.md) | 멱등성, 중복 요청, Idempotency-Key, Redis 기초와 `SET NX` |
| [35 캐시: Spring Cache와 Redis](./concepts/35-spring-cache-redis.md) | 캐시와 오래된 값, TTL, `@Cacheable`과 프록시, Redis 키·Java 직렬화, `sync`, 캐시에 번호만 두기 |
| [18 SPA와 서버 라우팅](./concepts/18-spa-server-routing.md) | History API, 서버 폴백, 301/302, Vite 개발 서버와 빌드 |
| [28 Thymeleaf에서 React로](./concepts/28-thymeleaf-to-react.md) | 서버 렌더링과 클라이언트 렌더링, 같은 화면 두 가지 구현, 빌드가 하는 일, 개발 서버와 빌드 스크립트 (Thymeleaf를 알면 React 문서보다 먼저) |
| [19 React Router와 API 클라이언트](./concepts/19-react-router-api-client.md) | React 기초, React Router 7, fetch, TypeScript, Vitest |
| [46 상태에 따라 갈 곳 정하기: 글쓰기 버튼](./concepts/46-entry-routing-write-button.md) | 판단을 순수 함수 하나에, `Pick`과 단위 테스트, 호스트를 넘는 이동, `?from=`으로 하려던 일 넘기기와 열린 리다이렉트, 버튼은 안내이고 권한은 서버 |
| [24 계층 구조와 DTO](./concepts/24-layered-architecture-dto.md) | presentation/application/domain, 엔티티 대신 DTO, `open-in-view`와 지연 로딩 |
| [25 React 폼과 데이터 불러오기](./concepts/25-react-forms-data.md) | 제어 컴포넌트, 폼 제출과 칸별 오류, `useEffect`와 커스텀 훅, 중첩 라우트, 낙관적 갱신, key, `FormData` |
| [26 WYSIWYG 에디터와 Tiptap](./concepts/26-wysiwyg-editor-tiptap.md) | ProseMirror와 Tiptap, 허용 서식 맞추기, 이중 정화, 에디터 상태 |

## 공부하는 법

1. **스텝 노트**의 "한눈에 보기"로 그 스텝이 무엇을 남겼는지 본다.
2. 스텝 노트의 **"이 스텝을 이해하려면"** 표 순서대로 개념 문서를 읽는다.
3. 개념 문서의 **"이 프로젝트에서는"** 절을 IntelliJ에서 실제 파일을 열어 놓고 읽는다. 디버거 중단점을 걸고 테스트를 돌리면 흐름이 눈으로 보인다.
4. **"직접 해 보기"**를 실행한다. 코드를 바꿔 보는 실습은 브랜치를 따로 만들어서 하고, 끝나면 되돌린다(`git switch -c study/xxx`, `git restore .`).
5. **확인 문제**를 답을 보기 전에 먼저 풀어 본다.
