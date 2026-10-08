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

## 개념

### 1. JPA 엔티티를 이미 있는 테이블에 맞추기

보통은 엔티티를 먼저 쓰고 테이블을 만들지만, 이 프로젝트는 **테이블(ERD)이 먼저**고 엔티티를 거기에 맞춘다. `ddl-auto=validate`가 둘이 다르면 앱을 띄우지 않는다.

| 테이블 | 엔티티 | 이유 |
| --- | --- | --- |
| `is_primary TINYINT(1)` | `boolean primary` + `@Column(name = "is_primary")` | Java 필드에는 `is` 접두사를 빼는 규칙(data-model.md). getter가 `isPrimary()`가 된다 |
| `role VARCHAR(10)` + CHECK | `@Enumerated(EnumType.STRING) Role role` | 숫자(ORDINAL)로 저장하면 enum 순서를 바꿀 때 데이터가 망가진다 |
| `content_html MEDIUMTEXT` | `@Column(columnDefinition = "mediumtext")` | 그냥 `String`이면 validate가 `varchar(255)`를 기대해서 실패 |
| `blog_id BIGINT` + FK | `@ManyToOne(fetch = LAZY) Blog blog` | 외래 키는 객체 참조로. `LAZY`라 필요할 때만 읽는다 |
| `primary_owner_id GENERATED ... STORED` | **매핑하지 않음** | DB가 계산하는 컬럼이라 JPA가 쓰면 안 된다. validate는 엔티티에 있는 컬럼만 확인한다 |
| `profile_image_id` | `Long profileImageId` | 이미지 엔티티는 스텝 7. 그때 객체 참조로 바꿀 수 있다 |

- **setter를 두지 않는다.** 대신 의미 있는 이름의 생성 메서드(`Member.ofEmail(...)`, `Blog.open(...)`, `Post.published(...)`)를 둔다. "어떻게 만들어지는가"가 코드에 드러나고, 아무 데서나 값을 바꾸지 못한다.
- `protected` 기본 생성자는 JPA가 객체를 만들 때 쓴다.
- DB 기본값(`DEFAULT 'USER'`)이 있어도 생성자에서 값을 넣는다. JPA는 INSERT에 모든 컬럼을 넣기 때문에, 필드가 null이면 DB 기본값이 아니라 NULL이 들어간다.

**코드에서**: `post/domain/Post.java`, 테스트 `global/entity/EntityMappingTest.java`(엔티티 다섯 개를 실제 MySQL에 저장하고 다시 읽음).

### 2. JPA Auditing

`created_at`, `updated_at`을 서비스 코드에서 매번 넣지 않게 한다.
- `@EnableJpaAuditing`(`JpaConfig`)을 켜고, 공통 부모에 `@EntityListeners(AuditingEntityListener.class)`, 필드에 `@CreatedDate`/`@LastModifiedDate`.
- 테이블마다 시각 컬럼이 달라서 부모를 둘로 나눴다: `created_at`만 있는 테이블은 `BaseCreatedEntity`, 둘 다 있으면 `BaseTimeEntity`. `category`처럼 `updated_at`만 있으면 엔티티에 직접 둔다.
- `@EnableJpaAuditing`을 `BlogApplication`이 아니라 별도 `@Configuration`에 둔 이유: `@WebMvcTest` 같은 슬라이스 테스트가 JPA 없이 뜰 때 "JPA metamodel must not be empty" 오류가 나는 것을 피하려고.

### 3. 전역 예외 처리와 COM-02 오류 형식

모든 오류가 같은 모양으로 나가야 프론트가 한 곳에서 처리할 수 있다.

```json
{ "code": "VALIDATION_FAILED", "message": "입력값을 확인해 주세요.",
  "fieldErrors": [{ "field": "title", "reason": "제목을 입력해 주세요." }] }
```

- `ErrorCode` enum: rest-api.md 오류 표의 코드 전부. 각각 HTTP 상태와 화면에 띄울 문장을 가진다.
- `BusinessException`: 서비스에서 `throw new BusinessException(ErrorCode.NICKNAME_TAKEN)`처럼 던진다.
- `@RestControllerAdvice` `GlobalExceptionHandler`: 예외 종류별로 `ErrorResponse`를 만든다.
  - `@Valid` 실패 → 400 + `fieldErrors`
  - 없는 주소 → 404 (`NoResourceFoundException`)
  - 그 밖의 모든 예외 → 500 `INTERNAL_ERROR`. **예외 메시지·스택·SQL은 응답에 넣지 않고 로그에만** 남긴다(내부 정보가 공격에 쓰일 수 있음).
- `@JsonInclude(NON_NULL)`: `fieldErrors`, `detail`은 있을 때만 JSON에 나온다.

### 4. 페이지 번호와 커서

| 방식 | 요청 | 쓰는 곳 | 장단점 |
| --- | --- | --- | --- |
| 페이지 번호(offset) | `?page=2&size=10` | 블로그 글 목록, 방명록 | 몇 쪽인지 보여 줄 수 있음. 뒤 페이지일수록 DB가 앞을 건너뛰느라 느림 |
| 커서(keyset) | `?cursor=...&size=20` | 홈 최신 글, 피드, 댓글 | 항상 빠름. 중간에 새 글이 들어와도 중복·누락 없음. 몇 쪽인지는 모름 |

- `PageQuery.of(page, size, 기본값)`: page는 **1부터**(rest-api.md). Spring Data는 0부터 세서 `toPageable`에서 1을 뺀다. 범위를 벗어나면 400.
- `TimeIdCursor`: 마지막 항목의 `(시각, id)`를 base64로 감싼 문자열. 프론트는 해석하지 않고 그대로 돌려보낸다. 시각만 쓰면 같은 시각의 글이 겹치므로 id를 같이 쓴다.
- `CursorResponse.of(size+1개 읽은 결과, size, ...)`: 하나 더 읽어 보고 남으면 다음 커서를 만든다(개수 쿼리 없이 "더 있나"를 아는 방법).

**문서끼리 달랐던 점**: tasks.md·research.md는 "page 0부터, 범위 밖은 보정", rest-api.md는 "page 1부터, 범위 밖은 400"이었다. 지원이 rest-api.md 쪽으로 정하고 다른 문서를 고쳤다.

### 5. XSS 정화(허용 목록)와 CSP

블로그 본문은 HTML이라 `<script>`나 `onerror=` 같은 것을 넣어 다른 사람 브라우저에서 코드를 실행시킬 수 있다(XSS).

- **허용 목록(allowlist)** 방식: "위험한 것을 지운다"가 아니라 "허용한 것만 남긴다". 새로운 공격 방법이 나와도 허용 목록에 없으면 지워진다.
- `HtmlSanitizer`(OWASP Java HTML Sanitizer): 문단, 제목, 굵게·기울임, 목록, 인용, 코드 블록(`class="language-java"`만), 링크(`http/https`만, `rel="nofollow noopener noreferrer"` 자동), 이미지(`/uploads/{uuid}.{확장자}`만).
- 정화기는 코드 안의 `=` 같은 글자를 `&#61;`로 바꾼다. 브라우저에는 똑같이 보인다.
- `SummaryExtractor`(jsoup): 태그를 모두 지운 글자만 300자로. 이모지처럼 두 `char`로 된 글자가 잘리지 않게 코드 포인트 기준으로 자른다.
- **CSP(Content-Security-Policy) 헤더**: 정화를 뚫고 스크립트가 들어와도 브라우저가 실행하지 않게 하는 두 번째 방어선. `script-src 'self'`라 인라인 스크립트와 외부 스크립트가 막힌다.
- 서버 정화가 필수이고, 프론트의 DOMPurify(스텝 5)는 보조다. 화면을 거치지 않고 API를 직접 부르는 공격도 있기 때문이다.

### 6. 관리자 초기 계정과 bcrypt

- 관리자는 가입으로 만들 수 없고 데이터로만 넣는다(ADMIN-01). Flyway `V2__admin_account.sql`.
- 비밀번호는 bcrypt 해시로 저장한다. bcrypt는 일부러 느리고(cost 10), 같은 비밀번호도 매번 다른 해시가 나온다(salt). 해시는 프로젝트의 `spring-security-crypto`로 만들었다.
- 개발용 값(`admin@blog.test` / `admin1234!`)이다. 운영 전에 바꿔야 한다.

## 막혔던 점

- **`@WebMvcTest`에 기본 보안이 걸림**: 슬라이스 테스트는 직접 만든 `SecurityConfig`를 읽지 않아 모든 요청이 401이었다. 처음에는 `@AutoConfigureMockMvc(addFilters = false)`로 피했고, 스텝 3에서 웹 설정이 늘면서 결국 통합 테스트로 옮겼다(스텝 3 노트).
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
