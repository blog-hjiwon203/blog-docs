# 스텝 2. 모든 기능이 쓰는 바닥

> 작업: T005, T021, T028, T043, T006, T012, T013, T014 · 코드 PR: [#2](https://github.com/AIP-1/blog-basic-AIGJ_01_017-blog/pull/2) · 날짜: 2026-10-08

## 한눈에 보기

여러 기능이 같이 쓰는 부품 다섯 가지를 만들었다.

| 부품 | 파일 | 나중에 누가 쓰나 |
| --- | --- | --- |
| 엔티티(테이블 ↔ 자바 클래스) | `member/domain/Member`, `blog/domain/Blog`, `post/domain/Post`, `category/domain/Category`, `comment/domain/Comment` | 모든 기능 |
| 생성·수정 시각 공통 처리 | `global/entity/BaseCreatedEntity`, `BaseTimeEntity`, `global/config/JpaConfig` | 모든 엔티티 |
| 오류 응답 형식 | `global/error/ErrorCode`, `ErrorResponse`, `BusinessException`, `GlobalExceptionHandler` | 모든 API |
| 목록 페이지 처리 | `global/web/PageQuery`, `PageResponse`, `CursorResponse`, `TimeIdCursor` | 글·댓글·방명록 목록 |
| 본문 정화와 요약 | `global/security/HtmlSanitizer`, `SummaryExtractor`, `ContentSecurityPolicyFilter` | 글 발행·수정(스텝 5) |

그리고 `V2__admin_account.sql`로 관리자 초기 계정을 넣었다.

## 패키지 구조 (스텝 2 끝에 정함)

```
com.nhnacademy.blog
├─ member/                 ← 기능 단위
│  ├─ domain/              엔티티, enum, Repository
│  ├─ application/         Service            (스텝 4부터)
│  └─ presentation/        Controller, dto/   (스텝 4부터)
├─ blog/ post/ category/ comment/ ...
└─ global/                 여러 기능이 같이 쓰는 것
   ├─ config/ entity/ error/ security/ web/
```

- **기능 단위(package-by-feature)**: "회원 기능을 고치려면 `member/`만 보면 된다". 계층 단위(`controller/`, `service/`, `repository/`를 최상위에 두는 방식)는 기능 하나를 고칠 때 여러 폴더를 오가야 한다.
- **안에서 세 계층**: 의존은 presentation → application → domain 한 방향이다. domain은 웹(Controller, HTTP)을 모른다. DDD(도메인 주도 설계)에서 흔히 쓰는 구조다.

## 이 스텝을 이해하려면 (읽는 순서)

| 순서 | 개념 문서 | 이 스텝에서 그 개념이 쓰인 곳 |
| --- | --- | --- |
| 1 | [JPA 엔티티 매핑과 영속성 컨텍스트](./concepts/06-jpa-entity-mapping.md) | 이미 있는 테이블에 엔티티 맞추기(`is_` 컬럼, enum, `mediumtext`, 계산 컬럼), setter 없는 엔티티, JPA Auditing(`BaseCreatedEntity`/`BaseTimeEntity`) |
| 2 | [Spring MVC 요청 흐름과 예외 처리](./concepts/07-spring-mvc-exception-handling.md) | `ErrorCode`, `BusinessException`, `GlobalExceptionHandler`, 500에서 내부 정보를 숨기는 이유, 405 추가 |
| 3 | [페이지네이션: 페이지 번호와 커서](./concepts/08-pagination.md) | `PageQuery`(1부터, 범위 밖 400), `TimeIdCursor`, size+1개 읽기 |
| 4 | [XSS, HTML 정화, CSP](./concepts/14-xss-sanitize-csp.md) | `HtmlSanitizer` 허용 목록, `SummaryExtractor`, `ContentSecurityPolicyFilter` |
| 5 | [비밀번호 해시와 bcrypt](./concepts/09-password-hashing.md) | `V2__admin_account.sql`의 관리자 비밀번호 해시 |
| 6 | [Spring 테스트](./concepts/05-spring-testing.md)의 슬라이스 테스트 부분 | `@WebMvcTest`에 기본 보안이 걸린 이유 |

## 막혔던 점

- **`@WebMvcTest`에 기본 보안이 걸림**: 슬라이스 테스트는 직접 만든 `SecurityConfig`를 읽지 않아 모든 요청이 401이었다. 처음에는 `@AutoConfigureMockMvc(addFilters = false)`로 피했고, 스텝 3에서 웹 설정이 늘면서 결국 통합 테스트로 옮겼다([Spring 테스트](./concepts/05-spring-testing.md)의 슬라이스 테스트 절).
- **임시 보안 설정**: 기본 Spring Security는 모든 요청을 막아서 "없는 주소는 404" 확인이 안 됐다. 전부 허용하는 임시 `SecurityConfig`를 두고 스텝 3에서 채웠다.
- **405 코드 추가**: 있는 주소를 잘못된 방식(GET 대신 POST)으로 부르면 405 `METHOD_NOT_ALLOWED`. rest-api.md에 없던 코드라 지원 확인 후 문서에 더했다.

## 직접 해 보기

```bash
curl -i localhost:8080/api/no-such-path        # 404 + COM-02 + CSP 헤더
./mvnw test -Dtest=HtmlSanitizerTest           # 어떤 HTML이 지워지는지 테스트 이름으로 확인
docker exec blog-mysql mysql -ublog -pblog blog -e "SELECT email, role, password_hash FROM member"
```

IntelliJ에서 `EntityMappingTest`를 열고 `@Column(name = "is_primary")`를 지운 뒤 테스트를 돌려 보면, validate가 어떤 오류를 내는지 볼 수 있다.

## 더 공부할 거리

- JPA 지연 로딩(LAZY)과 N+1 문제, `join fetch`
- `EnumType.ORDINAL`이 위험한 이유
- offset 페이지네이션이 느려지는 이유와 keyset 페이지네이션
- XSS의 종류(저장형, 반사형, DOM 기반)와 CSP 지시어
- bcrypt, scrypt, Argon2의 차이
