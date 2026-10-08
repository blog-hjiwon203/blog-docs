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
| [23 트랜잭션과 동시성](./concepts/23-transactions-locking.md) | `@Transactional`, 경쟁 조건, 비관적 잠금(`FOR UPDATE`), UNIQUE 제약, 동시성 테스트 |

### 3부. 보안

| 문서 | 다루는 것 |
| --- | --- |
| [10 HTTP 쿠키](./concepts/10-http-cookies.md) | 쿠키 속성 하나하나, 세션과 토큰, 서브도메인 쿠키 공유 |
| [11 JWT와 로그인 토큰 설계](./concepts/11-jwt.md) | JWT 구조와 서명, Access/Refresh, 무효화, 무활동 로그아웃 |
| [12 Spring Security 필터 체인](./concepts/12-spring-security-filter-chain.md) | FilterChainProxy, SecurityContext, 인가 설정, 메서드 보안, 커스텀 필터 |
| [13 CSRF, SameSite, CORS](./concepts/13-csrf-samesite-cors.md) | 출처와 사이트, CSRF 공격과 대책, preflight, CORS가 아닌 것 |
| [14 XSS, HTML 정화, CSP](./concepts/14-xss-sanitize-csp.md) | XSS 종류, 허용 목록 정화, CSP 지시어 |
| [20 이메일 인증 코드와 요청 제한](./concepts/20-email-verification.md) | 인증 코드 설계, `SecureRandom`, Redis로 1분 재요청 제한, 메일 발송 인터페이스 |
| [21 가입·로그인·로그아웃 설계](./concepts/21-signup-login.md) | 가입 트랜잭션, 계정 열거·타이밍 공격 방어, 정지 안내, 로그아웃, 열린 리다이렉트 |

### 4부. 이 블로그의 구조와 프론트

| 문서 | 다루는 것 |
| --- | --- |
| [15 서브도메인과 Host 라우팅](./concepts/15-subdomain-host-routing.md) | DNS, `/etc/hosts`, Host 헤더, 멀티테넌시, 인자 해석기 |
| [16 인가와 가시성 판단](./concepts/16-authorization-visibility.md) | 인증과 인가, 존재를 숨기는 404, 정책 객체, sealed 타입과 switch |
| [17 멱등성과 Redis](./concepts/17-idempotency-redis.md) | 멱등성, 중복 요청, Idempotency-Key, Redis 기초와 `SET NX` |
| [18 SPA와 서버 라우팅](./concepts/18-spa-server-routing.md) | History API, 서버 폴백, 301/302, Vite 개발 서버와 빌드 |
| [19 React Router와 API 클라이언트](./concepts/19-react-router-api-client.md) | React 기초, React Router 7, fetch, TypeScript, Vitest |
| [24 계층 구조와 DTO](./concepts/24-layered-architecture-dto.md) | presentation/application/domain, 엔티티 대신 DTO, `open-in-view`와 지연 로딩 |
| [25 React 폼과 데이터 불러오기](./concepts/25-react-forms-data.md) | 제어 컴포넌트, 폼 제출과 칸별 오류, `useEffect`와 커스텀 훅, 중첩 라우트 |

## 공부하는 법

1. **스텝 노트**의 "한눈에 보기"로 그 스텝이 무엇을 남겼는지 본다.
2. 스텝 노트의 **"이 스텝을 이해하려면"** 표 순서대로 개념 문서를 읽는다.
3. 개념 문서의 **"이 프로젝트에서는"** 절을 IntelliJ에서 실제 파일을 열어 놓고 읽는다. 디버거 중단점을 걸고 테스트를 돌리면 흐름이 눈으로 보인다.
4. **"직접 해 보기"**를 실행한다. 코드를 바꿔 보는 실습은 브랜치를 따로 만들어서 하고, 끝나면 되돌린다(`git switch -c study/xxx`, `git restore .`).
5. **확인 문제**를 답을 보기 전에 먼저 풀어 본다.
