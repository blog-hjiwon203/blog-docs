# 23. 트랜잭션과 동시성: 잠금과 UNIQUE

> 관련 스텝: [스텝 4](../step-04.md) (T018, T022, T027) · 관련 개념: [03-flyway-migration](./03-flyway-migration.md), [06-jpa-entity-mapping](./06-jpa-entity-mapping.md), [17-idempotency-redis](./17-idempotency-redis.md), [22-bean-validation](./22-bean-validation.md)

## 1. 이 문서로 배우는 것

- 트랜잭션의 뜻과 ACID(원자성, 일관성, 격리성, 지속성)
- Spring `@Transactional`: 프록시로 동작하는 원리, 언제 롤백되나, `readOnly`, 전파(propagation) `REQUIRED`
- 가입 트랜잭션 안에서 "인증 코드 사용 표시"와 "회원 생성"이 함께 성공하거나 함께 되돌아가는 구조
- 경쟁 조건(check-then-act): 블로그 5개 한도, 대표 블로그, 주소·닉네임 중복
- 해결 도구 비교: 확인만 하기 / DB UNIQUE / 비관적 잠금(`SELECT … FOR UPDATE`) / 낙관적 잠금(`@Version`) / Redis `SET NX`
- 이 프로젝트의 선택: 회원 행 잠금(`findByIdForUpdate`), `uk_blog_address`, 계산 컬럼 `primary_owner_id` + UNIQUE
- `saveAndFlush`를 쓰는 이유, `DataIntegrityViolationException` 처리
- 동시성 테스트(`concurrentCreatesKeepLimitAndSinglePrimary`)를 읽는 법

**먼저 알면 좋은 것**: SQL의 INSERT/SELECT/UPDATE, JPA 엔티티와 영속성 컨텍스트([06](./06-jpa-entity-mapping.md)), 웹 서버가 요청을 여러 스레드로 동시에 처리한다는 것.

## 2. 왜 필요한가

명세는 이렇게 요구한다.

- BLOG-01: 활성 블로그 **6번째는 거절**. 처음 만든 블로그가 대표 블로그이고, 회원당 대표는 **하나**.
- 주소는 **한 블로그만** 쓴다. 닉네임과 이메일도 중복 불가.
- OWN-01: 인증 코드를 확인해야만 회원이 만들어진다.

가장 쉬운 구현은 "확인하고, 괜찮으면 저장"이다.

```java
long count = blogRepository.countActiveByMemberId(memberId);   // 확인: 지금 4개
if (count >= 5) throw 한도초과;
blogRepository.save(new Blog(...));                              // 저장
```

사용자 한 명이 차례로 누르면 문제없다. 그런데 서버는 요청을 **동시에** 처리한다. 블로그가 4개인 회원이 "만들기"를 빠르게 두 번 누르거나, 탭 두 개에서 동시에 누르면:

```
요청 A: count → 4  ┐ 같은 순간
요청 B: count → 4  ┘ B도 4로 봄
요청 A: 4 < 5 → 저장 (5개)
요청 B: 4 < 5 → 저장 (6개!)   ← 명세 위반
```

"확인"과 "실행" 사이에 다른 요청이 끼어드는 이 문제를 **경쟁 조건(race condition)**, 그중에서도 **check-then-act** 문제라 한다([17](./17-idempotency-redis.md)에서 Redis로 본 것과 같은 모양이다). 테스트를 한 줄씩 돌릴 때는 절대 안 보이고, 사용자가 많아지면 가끔 터진다. 그래서 설계 단계에서 막아야 한다.

또 가입은 "인증 코드에 사용 표시"와 "회원 INSERT" 두 가지를 한다. 앞의 것만 되고 뒤의 것이 실패하면, 코드는 "이미 씀"이 되었는데 회원은 없다. 사용자는 코드를 다시 받아야 한다. **둘이 함께 되거나 함께 안 되게** 묶는 것이 트랜잭션이다.

## 3. 기본 개념

### 3.1 트랜잭션과 ACID

**트랜잭션**은 DB 작업 여러 개를 "하나로 취급"하는 단위다. 끝에 **커밋(commit)**하면 모두 반영되고, **롤백(rollback)**하면 모두 없던 일이 된다.

| 성질 | 뜻 | 가입에서 |
| --- | --- | --- |
| Atomicity 원자성 | 전부 되거나 전부 안 된다 | 코드 사용 표시와 회원 INSERT가 같이 |
| Consistency 일관성 | 제약(UNIQUE, CHECK, FK)을 깨는 상태로 끝나지 않는다 | 같은 닉네임 두 명은 커밋될 수 없음 |
| Isolation 격리성 | 동시에 도는 트랜잭션이 서로의 중간 상태를 (어느 정도) 안 본다 | 커밋 전 회원은 다른 요청에 안 보임 |
| Durability 지속성 | 커밋한 것은 서버가 꺼져도 남는다 | |

주의: **격리성이 경쟁 조건을 자동으로 막아 주지는 않는다.** MySQL InnoDB의 기본 격리 수준(REPEATABLE READ)에서 평범한 SELECT는 잠그지 않고 읽는다. 위의 A와 B는 각자 트랜잭션 안에 있어도 둘 다 "4개"를 본다. 막으려면 3.4의 도구가 필요하다.

### 3.2 Spring `@Transactional`

```java
@Transactional
public Member signup(...) { ... }
```

- 메서드가 시작될 때 트랜잭션을 열고, **정상으로 끝나면 커밋**, **런타임 예외(`RuntimeException`)가 밖으로 나가면 롤백**한다. 체크 예외(`Exception`을 상속하고 `RuntimeException`이 아닌 것)는 기본으로 롤백하지 않는다. 이 프로젝트의 `BusinessException`은 `RuntimeException`이라 던지면 롤백된다.
- **프록시**로 동작한다. Spring은 `AuthService` 빈 대신 그것을 감싼 대리 객체를 다른 빈에 넣어 주고, 대리 객체가 "트랜잭션 열기 → 진짜 메서드 → 커밋/롤백"을 한다. 그래서 **같은 클래스 안에서 `this.다른메서드()`로 부르면 프록시를 거치지 않아 그 메서드의 `@Transactional`은 무시된다.**
- `@Transactional(readOnly = true)`: 읽기만 한다는 표시. Hibernate가 변경 감지(dirty checking)를 위한 스냅숏을 덜 만들고, 끝날 때 flush하지 않는다. 조회 서비스에 붙인다.
- JPA는 트랜잭션 안에서만 지연 로딩(LAZY)이 된다. 이 프로젝트는 `open-in-view: false`라 **컨트롤러에서는 트랜잭션이 이미 끝났다.** 응답에 필요한 연관 엔티티는 서비스 안에서 읽어 둬야 한다.

### 3.3 전파: 트랜잭션 안에서 트랜잭션 메서드를 부르면

기본 전파 방식은 **`REQUIRED`**다. "이미 트랜잭션이 있으면 거기에 **합류**하고, 없으면 새로 연다."

```
AuthService.signup  @Transactional  ── 트랜잭션 T 시작
   └ EmailVerificationService.consume  @Transactional  ── T에 합류 (새로 열지 않음)
        └ verified_at = now  (아직 커밋 안 됨, T 안의 변경)
   └ memberRepository.saveAndFlush(...)  ── 실패하면 예외 → T 전체 롤백 → verified_at도 사라짐
```

다른 빈의 메서드라 프록시를 거치고, `REQUIRED`라 같은 트랜잭션을 쓴다. 그래서 가입이 실패하면 코드 사용 표시도 같이 되돌아간다.

### 3.4 경쟁 조건을 막는 도구

| 도구 | 방법 | 장점 | 단점·한계 |
| --- | --- | --- | --- |
| 애플리케이션에서 확인만 | `exists...` 후 저장 | 친절한 오류 문장 | **동시 요청에 뚫린다** |
| DB UNIQUE 제약 | 같은 값 두 번째 INSERT를 DB가 거절 | 무조건 막힌다(마지막 방어선). 서버가 여러 대여도 됨 | "값 하나가 겹치면 안 됨"만 표현 가능. "5개까지" 같은 개수 규칙은 못 함. 위반 시 예외를 오류 코드로 바꿔야 함 |
| 비관적 잠금 `SELECT … FOR UPDATE` | 읽으면서 행을 잠가 다른 트랜잭션이 기다리게 함 | 개수 규칙처럼 "읽고 판단하고 쓰기"를 통째로 직렬화 | 기다리는 동안 느려짐, 잠금 순서가 꼬이면 데드락 |
| 낙관적 잠금 `@Version` | 수정 시 버전 번호가 그대로인지 확인, 바뀌었으면 실패 | 잠그지 않아 빠름 | **이미 있는 행을 수정**할 때 쓰는 것. 새 행 INSERT 경쟁에는 안 맞음. 실패 시 재시도 필요 |
| Redis `SET NX` | 키 하나로 "하나만 통과" | DB 밖, 여러 서버 공유 | Redis가 죽거나 키가 남는 경우 처리 필요([17](./17-idempotency-redis.md)) |

**비관적 잠금**: "누가 동시에 고칠 것"이라고 비관해서 먼저 잠근다. MySQL InnoDB에서 `SELECT ... FOR UPDATE`는 읽은 행에 **배타 잠금**을 걸고, 같은 행을 `FOR UPDATE`로 읽으려는 다른 트랜잭션은 **앞의 트랜잭션이 커밋·롤백할 때까지 기다린다.** 잠금은 문장이 끝나도 풀리지 않고 **트랜잭션 끝까지** 유지된다.

**낙관적 잠금**: "거의 안 겹치겠지"라고 낙관하고 잠그지 않는다. 대신 `UPDATE ... SET version = 6 WHERE id = ? AND version = 5`처럼 고치고, 바뀐 행이 0개면 누가 먼저 고친 것이라 실패시킨다.

### 3.5 데드락

트랜잭션 A가 행 1을 잠그고 행 2를 기다리는데, B가 행 2를 잠그고 행 1을 기다리면 둘 다 영원히 기다린다. 이것이 **데드락**이다. InnoDB는 이것을 감지해 한쪽을 강제로 롤백시킨다(오류가 난다). 예방법: **여러 행을 잠글 때는 모든 코드가 같은 순서로 잠근다**, 잠그는 범위를 작게, 트랜잭션을 짧게.

## 4. 동작 원리

블로그가 4개인 회원의 개설 요청 A, B가 동시에 온다. `BlogService.open`은 맨 처음에 **회원 행을 잠근다.**

```
시간 ─────────────────────────────────────────────────────────────▶
요청 A  BEGIN  SELECT member FOR UPDATE ✔(잠금 얻음)
               count = 4 → 4 < 5
               주소 확인 → INSERT blog → COMMIT (잠금 풀림)
요청 B  BEGIN  SELECT member FOR UPDATE ……… 기다림 ……… ✔(A 커밋 뒤 잠금 얻음)
                                                     count = 5 → 409 BLOG_LIMIT_EXCEEDED
                                                     ROLLBACK
```

- 잠그는 대상이 "블로그"가 아니라 "**회원 행**"인 이유: 아직 없는 6번째 블로그 행은 잠글 수 없다. 대신 "이 회원의 블로그를 만드는 일"을 회원 행 하나로 줄 세운다. 같은 회원의 개설 요청은 차례로, **다른 회원**의 요청은 다른 행을 잠그므로 서로 기다리지 않는다.
- 대표 블로그도 같은 줄에서 판단한다. A가 첫 블로그면 `count == 0 → 대표`, B는 A가 커밋한 뒤 `count == 1`을 보므로 대표가 아니다.
- **주소 중복은 다른 회원끼리도** 겹칠 수 있어 회원 잠금으로는 못 막는다. 그건 `uk_blog_address` UNIQUE가 막는다.

| 규칙 | 경쟁 상대 | 막는 것 |
| --- | --- | --- |
| 활성 블로그 5개 | 같은 회원의 동시 요청 | 회원 행 잠금 |
| 대표 블로그 하나 | 같은 회원의 동시 요청 | 회원 행 잠금 + DB의 `uk_blog_primary_owner_id` |
| 주소 중복 | 아무 회원 | `uk_blog_address` |
| 이메일·닉네임 중복(가입) | 아무 사람 | `uk_member_email`, `uk_member_nickname` |

## 5. 이 프로젝트에서는

### 5.1 가입: 한 트랜잭션으로 묶기

`src/main/java/com/nhnacademy/blog/auth/application/AuthService.java`

```java
@Transactional
public Member signup(String rawEmail, String code, String password, String rawNickname) {
    String email = Emails.normalize(rawEmail);
    String nickname = rawNickname.trim();
    PasswordRule.check("password", password);
    if (memberRepository.existsByEmail(email)) {
        throw new BusinessException(ErrorCode.EMAIL_TAKEN);
    }
    if (memberRepository.existsByNickname(nickname)) {
        throw new BusinessException(ErrorCode.NICKNAME_TAKEN);
    }
    emailVerificationService.consume(email, code);
    try {
        return memberRepository.saveAndFlush(Member.ofEmail(email, passwordEncoder.encode(password), nickname));
    } catch (DataIntegrityViolationException e) {
        // 중복 확인과 저장 사이에 같은 값으로 먼저 가입한 사람이 있다
        throw new BusinessException(isNicknameConflict(e) ? ErrorCode.NICKNAME_TAKEN : ErrorCode.EMAIL_TAKEN);
    }
}
```

- `existsByEmail`, `existsByNickname`: 대부분의 중복은 여기서 친절한 409로 끝난다. 하지만 동시 가입에는 뚫릴 수 있는 "확인만"이다.
- `emailVerificationService.consume`: 같은 트랜잭션에 합류해 `verified_at`을 적는다(3.3).
- `saveAndFlush`: `save`는 INSERT를 바로 보내지 않고 영속성 컨텍스트에 모아 뒀다가 **커밋할 때** 보낼 수 있다. 그러면 UNIQUE 위반 예외가 메서드가 끝난 뒤(프록시가 커밋할 때) 나서 이 `try` 안에서 잡을 수 없다. `saveAndFlush`는 **지금 바로** INSERT를 DB에 보내므로, 위반이 이 줄에서 예외로 터진다. (`Member`는 `IDENTITY` 키라 실제로는 `save`도 id를 얻으려고 바로 INSERT하지만, 그 동작에 기대지 않고 의도를 코드로 드러낸다.)
- `DataIntegrityViolationException`: Spring이 DB 제약 위반을 감싼 예외다. 메시지의 제약 이름(`uk_member_nickname`)으로 어느 칸이 겹쳤는지 구별한다. 제약 이름은 Flyway `V1__init.sql`에서 정했다.
- 예외를 잡아 `BusinessException`을 다시 던지므로 트랜잭션은 여전히 롤백된다. `consume`이 적은 `verified_at`도 사라진다.

`src/main/java/com/nhnacademy/blog/auth/application/EmailVerificationService.java`

```java
/** 가입 트랜잭션 안에서 부른다. 가입이 실패하면 함께 되돌아가 코드를 다시 쓸 수 있다. */
@Transactional
public void consume(String rawEmail, String code) {
    check(Emails.normalize(rawEmail), code).markVerified(LocalDateTime.now(clock));
}
```

`markVerified`는 엔티티 필드만 바꾼다. UPDATE 문은 따로 쓰지 않았다. 트랜잭션이 커밋될 때 Hibernate가 바뀐 엔티티를 찾아 UPDATE를 보낸다(변경 감지, [06](./06-jpa-entity-mapping.md)).

테스트 `SignupIntegrationTest.duplicateEmailOrNicknameIs409`가 롤백을 확인한다.

```java
signup(email, code, "password1", existing.getNickname())
        .andExpect(status().isConflict())
        .andExpect(jsonPath("$.code").value("NICKNAME_TAKEN"));
// 실패한 가입은 코드를 쓰지 않았으므로 같은 코드로 다시 할 수 있다
signup(email, code, "password1", uniqueNickname()).andExpect(status().isCreated());
```

이 테스트에서는 닉네임 확인이 `consume`보다 먼저라 코드가 아예 안 쓰였다. 순서와 상관없이, `consume` 뒤에 실패해도(UNIQUE 위반) 롤백으로 같은 결과가 된다는 것이 트랜잭션이 주는 보장이다.

### 5.2 블로그 개설: 회원 행 잠금

`src/main/java/com/nhnacademy/blog/member/domain/MemberRepository.java`

```java
/**
 * 회원 행을 잠그고 읽는다(SELECT ... FOR UPDATE). 같은 회원의 요청을 한 줄로 세울 때 쓴다.
 * 예: 블로그 개설에서 동시에 두 번 와도 5개 한도와 대표 블로그를 한 번씩 차례로 판단한다.
 */
@Lock(LockModeType.PESSIMISTIC_WRITE)
@Query("select m from Member m where m.id = :id")
Optional<Member> findByIdForUpdate(@Param("id") Long id);
```

- `@Lock(LockModeType.PESSIMISTIC_WRITE)`: JPA 표준 잠금 모드. MySQL에서 Hibernate는 이 쿼리 끝에 `for update`를 붙인다.
- `@Query`를 직접 쓴 이유: 이미 있는 `findById`는 `JpaRepository`가 주는 메서드라 잠금을 붙일 수 없어서, 이름이 다른 메서드를 만들었다. 이름에 `ForUpdate`를 넣어 부르는 쪽에서 잠금을 알아보게 했다.
- 잠금은 **트랜잭션 안에서만** 의미가 있다. 트랜잭션 없이 부르면 문장이 끝나자마자 풀린다(Spring Data는 트랜잭션 없는 잠금 쿼리에 예외를 내기도 한다). 그래서 `@Transactional` 메서드 안에서 부른다.

`src/main/java/com/nhnacademy/blog/blog/application/BlogService.java`

```java
@Transactional
public Blog open(Long memberId, String address, String name, String description) {
    Member member = memberRepository.findByIdForUpdate(memberId)
            .orElseThrow(() -> new BusinessException(ErrorCode.UNAUTHORIZED));
    checkAddressRule(address);
    long activeCount = blogRepository.countActiveByMemberId(memberId);
    if (activeCount >= Blog.MAX_ACTIVE_PER_MEMBER) {
        throw new BusinessException(ErrorCode.BLOG_LIMIT_EXCEEDED);
    }
    if (blogRepository.existsByAddress(address)) {
        throw new BusinessException(ErrorCode.BLOG_ADDRESS_TAKEN);
    }
    try {
        return blogRepository.saveAndFlush(
                Blog.open(member, address, name.trim(), blankToNull(description), activeCount == 0));
    } catch (DataIntegrityViolationException e) {
        // 확인과 저장 사이에 다른 회원이 같은 주소로 먼저 개설했다
        throw new BusinessException(ErrorCode.BLOG_ADDRESS_TAKEN);
    }
}
```

줄별로:

1. `findByIdForUpdate`: **가장 먼저** 잠근다. 잠금 전에 센 `count`는 믿을 수 없기 때문이다. 같은 회원의 두 번째 요청은 여기서 기다린다.
2. `checkAddressRule`: 형식·예약어(400, [22](./22-bean-validation.md)).
3. `countActiveByMemberId`: 잠금을 쥔 상태에서 센다. 앞 요청이 커밋한 블로그까지 보인다(InnoDB에서 `FOR UPDATE`로 기다렸다 이어 가는 트랜잭션의 일반 SELECT가 앞 커밋을 보는지는 격리 수준에 따라 미묘하다. 이 프로젝트의 동시성 테스트(5.5)가 실제로 5개에서 멈추는 것을 확인했다).
4. `activeCount == 0`이면 대표 블로그. 판단과 저장이 같은 잠금 안이라 두 요청이 둘 다 "0"을 볼 수 없다.
5. `existsByAddress`: 대부분의 주소 중복은 여기서 409.
6. `saveAndFlush` + `catch`: 다른 회원이 같은 주소로 동시에 개설한 경우는 회원 잠금으로 못 막으므로, DB UNIQUE가 막고 그 예외를 409로 바꾼다.

### 5.3 DB가 지키는 마지막 방어선

`src/main/resources/db/migration/V1__init.sql` (ERD에서 내보낸 것, blog 테이블 일부)

```sql
    is_primary TINYINT(1) NOT NULL DEFAULT 0 COMMENT '대표 블로그 여부',
    ...
    deleted_at DATETIME COMMENT '삭제 시각',
    ...
    primary_owner_id BIGINT GENERATED ALWAYS AS (CASE WHEN is_primary = 1 AND deleted_at IS NULL THEN member_id END) STORED COMMENT '대표 블로그 주인(유니크용)-----회원당 대표 블로그 하나를 DB에서 보장하는 계산 컬럼',
    ...
    CONSTRAINT uk_blog_address UNIQUE (address),
    CONSTRAINT uk_blog_primary_owner_id UNIQUE (primary_owner_id),
```

- `uk_blog_address`: 주소는 한 행만. 삭제된 블로그도 행이 남으므로(소프트 삭제) 삭제된 주소도 다시 못 쓴다.
- **"회원당 대표 하나"는 `UNIQUE(member_id, is_primary)`로는 안 된다.** 그러면 `is_primary = 0`인 블로그도 회원당 하나밖에 못 만든다. 그래서 **계산 컬럼(generated column)** `primary_owner_id`를 둔다.
  - 대표이고 삭제되지 않은 블로그면 값이 `member_id`, 아니면 `NULL`.
  - MySQL의 UNIQUE는 `NULL`끼리는 겹쳐도 된다. 그래서 대표가 아닌 블로그들(`NULL`)은 몇 개든 괜찮고, 대표 블로그는 회원마다 하나만 들어간다.
  - `STORED`: 값을 실제로 저장해 인덱스를 걸 수 있게 한다. DB가 채우는 컬럼이라 `Blog` 엔티티는 이 컬럼을 매핑하지 않는다(엔티티 주석 참고). JPA가 INSERT에 값을 넣으려 하면 오류가 나기 때문이다.
- 애플리케이션 잠금(5.2)에 버그가 생겨도 DB가 대표 두 개를 거절한다. **애플리케이션 검사는 친절한 오류를 위해, DB 제약은 절대 깨지지 않기 위해** 둘 다 둔다.

같은 생각의 다른 예: `category.parent_key` 계산 컬럼(`IFNULL(parent_id, 0)`)도 NULL끼리 겹쳐도 되는 UNIQUE의 성질을 피해 최상위 카테고리 이름 중복을 막는다([06](./06-jpa-entity-mapping.md)).

### 5.4 왜 이 도구들을 골랐나

- 개수 규칙(5개)은 UNIQUE로 표현할 수 없다 → **비관적 잠금**.
- 낙관적 잠금(`@Version`)은 "있는 행 수정"용이다. 블로그 개설은 새 행 INSERT라 버전을 비교할 행이 없다. 회원 행에 버전을 두고 개설 때마다 올리는 방법도 있지만, 실패하면 재시도 코드가 필요하다. 블로그 개설은 드물고 짧은 작업이라 기다리게 하는 편이 단순하다.
- Redis `SET NX`로 회원별 락을 걸 수도 있지만, 판단에 쓰는 데이터가 MySQL에 있으므로 같은 DB 트랜잭션 안에서 잠그는 것이 정확하다(Redis 락과 DB 트랜잭션은 따로 커밋된다).
- 중복(주소, 이메일, 닉네임) → **UNIQUE**가 가장 확실하고, 앞의 `exists` 확인은 대부분의 경우에 친절한 문장을 주기 위해 둔다.

데드락: 지금 잠그는 행은 `open`의 회원 행 하나뿐이라 순서 문제가 없다. 나중에 두 회원 행을 함께 잠그는 코드(예: 블로그 이사가 두 주인을 건드린다면)가 생기면 **id가 작은 쪽부터** 같은 순서로 잠근다.

### 5.5 동시성 테스트 읽기

`src/test/java/com/nhnacademy/blog/blog/BlogCreateIntegrationTest.java`

```java
@Test
void concurrentCreatesKeepLimitAndSinglePrimary() throws Exception {
    List<Callable<Integer>> requests = new ArrayList<>();
    for (int i = 0; i < 7; i++) {
        String address = uniqueAddress();
        requests.add(() -> create(address).andReturn().getResponse().getStatus());
    }

    List<Integer> statuses = new ArrayList<>();
    try (ExecutorService executor = Executors.newFixedThreadPool(7)) {
        for (Future<Integer> result : executor.invokeAll(requests)) {
            statuses.add(result.get());
        }
    }

    assertThat(statuses).filteredOn(code -> code == 201).hasSize(5);
    assertThat(statuses).filteredOn(code -> code == 409).hasSize(2);
    assertThat(jdbcTemplate.queryForObject(
            "SELECT COUNT(*) FROM blog WHERE member_id = ? AND is_primary = 1", Integer.class, member.getId()))
            .isEqualTo(1);
}
```

- 블로그가 없는 회원 한 명이 서로 다른 주소 7개로 **동시에** 개설한다(주소가 다르니 주소 UNIQUE는 상관없고, 순수하게 개수·대표 규칙만 본다).
- `Callable<Integer>`: 결과(상태 코드)를 돌려주는 작업. `Runnable`과 달리 값을 돌려준다.
- `Executors.newFixedThreadPool(7)`: 스레드 7개. `invokeAll`은 작업을 한꺼번에 던지고 모두 끝날 때까지 기다린다. `result.get()`은 각 작업의 결과를 꺼낸다(작업에서 예외가 났으면 여기서 다시 던진다).
- `try (ExecutorService ...)`: Java 21부터 `ExecutorService`가 `AutoCloseable`이라 블록이 끝나면 정리된다.
- MockMvc는 실제 네트워크 없이 같은 JVM에서 요청을 처리하지만, 7개 스레드가 각자 트랜잭션을 열고 같은 MySQL(Testcontainers)에 접속하므로 DB 잠금은 실제처럼 동작한다.
- 기대값: 201 다섯, 409(`BLOG_LIMIT_EXCEEDED`) 둘, 대표 블로그 하나. 어느 요청이 대표가 되는지는 매번 다를 수 있어서 개수만 본다.

이 테스트가 통과한다고 "언제나 안전하다"는 증명은 아니다. 동시성 버그는 타이밍에 달려 있어서, 잠금이 없는 코드도 운 좋게 통과할 수 있다(7장 실습 2). 그래도 스레드 수를 한도보다 크게 잡아 경쟁을 일부러 만들면, 잠금이 빠졌을 때 실패할 가능성이 높다.

## 6. 자주 하는 실수와 함정

1. **확인 후 저장만 믿기**: `exists` → `save`는 동시 요청에 뚫린다. 중복은 UNIQUE, 개수는 잠금.
2. **잠금보다 먼저 세기**: `count`를 먼저 하고 나중에 잠그면 소용없다. 잠금이 맨 앞이다.
3. **트랜잭션 밖에서 `FOR UPDATE`**: 문장이 끝나면 바로 풀린다. `@Transactional` 메서드 안에서.
4. **같은 클래스 안 호출로 `@Transactional` 기대**: `this.consume()`은 프록시를 안 거친다. 트랜잭션 메서드는 다른 빈으로 나눠 부른다(`EmailVerificationService`가 따로인 이유 중 하나).
5. **체크 예외로 롤백 기대**: 기본은 런타임 예외만 롤백. 이 프로젝트의 예외는 모두 런타임 예외.
6. **예외를 잡고 삼키기**: `catch (DataIntegrityViolationException e) { return null; }`처럼 끝내면 메서드는 정상 종료로 보이고, 트랜잭션은 "롤백만 가능" 표시가 된 상태로 커밋을 시도하다 다른 예외(`UnexpectedRollbackException`)가 나거나, 앞의 변경이 커밋될 수 있다. 잡았으면 의미 있는 예외로 다시 던진다.
7. **`save` 후 바로 위반을 잡으려 하기**: INSERT가 커밋 때 나가면 `try` 밖에서 터진다. 잡아야 하면 `saveAndFlush`.
8. **`UNIQUE(member_id, is_primary)`로 대표 하나 표현**: 대표 아닌 블로그도 하나밖에 못 만든다. 계산 컬럼 + UNIQUE.
9. **잠금 범위가 너무 큼**: 테이블 전체나 많은 행을 오래 잠그면 다른 사용자가 줄줄이 기다린다. 회원 행 하나처럼 작게, 트랜잭션은 짧게(트랜잭션 안에서 메일 발송 같은 느린 일을 하지 않는다).
10. **동시성 테스트 한 번 통과로 안심**: 타이밍이 우연히 좋았을 수 있다.

## 7. 직접 해 보기

**실습 1. MySQL에서 잠금 기다리기 체험**

```bash
docker compose up -d
docker exec -it blog-mysql mysql -ublog -pblog blog     # 터미널 두 개에서 각각
```

```sql
-- 터미널 1
START TRANSACTION;
SELECT id, nickname FROM member WHERE id = 1 FOR UPDATE;   -- 잠금 얻음

-- 터미널 2
START TRANSACTION;
SELECT id, nickname FROM member WHERE id = 1 FOR UPDATE;   -- 멈춰서 기다린다

-- 터미널 1
COMMIT;                                                    -- 이 순간 터미널 2가 결과를 받는다

-- 터미널 2
COMMIT;
```

터미널 2에서 `FOR UPDATE` 없이 `SELECT ... WHERE id = 1;`을 하면 기다리지 않고 바로 읽힌다. 평범한 SELECT는 잠그지 않는다는 것을 확인한다. 50초쯤 계속 기다리게 두면 `Lock wait timeout exceeded` 오류가 난다(`innodb_lock_wait_timeout` 기본값).

**실습 2. 잠금을 빼고 동시성 테스트 돌리기**

1. `BlogService.open`의 `memberRepository.findByIdForUpdate(memberId)`를 `memberRepository.findById(memberId)`로 바꾼다.
2. `./mvnw test -Dtest=BlogCreateIntegrationTest#concurrentCreatesKeepLimitAndSinglePrimary`를 여러 번 돌린다.
3. 기대 결과: 201이 6개 이상이 되거나, 대표가 둘이 되려다 `uk_blog_primary_owner_id` 위반으로 예상하지 못한 409·500이 섞여 실패할 수 있다. **하지만 매번 실패하지는 않을 수 있다.** 스레드들이 우연히 차례로 실행되면 통과한다. 이것이 동시성 버그가 "가끔" 터지는 이유다. 되돌린다.

**실습 3. UNIQUE가 마지막에 막는 것 보기**

```sql
-- 회원 1에게 대표 블로그를 둘 만들어 보기
INSERT INTO blog (member_id, address, name, is_primary) VALUES (1, 'primary-a', 'A', 1);
INSERT INTO blog (member_id, address, name, is_primary) VALUES (1, 'primary-b', 'B', 1);
-- ERROR 1062: Duplicate entry '1' for key 'blog.uk_blog_primary_owner_id'
INSERT INTO blog (member_id, address, name, is_primary) VALUES (1, 'normal-c', 'C', 0);   -- 성공
SELECT address, is_primary, primary_owner_id FROM blog WHERE member_id = 1;
DELETE FROM blog WHERE address IN ('primary-a', 'normal-c');
```

`primary_owner_id`가 대표 블로그에만 채워지는 것을 눈으로 확인한다.

**실습 4. 롤백 확인**

`AuthService.signup`에서 `emailVerificationService.consume(email, code);` 바로 다음 줄에 `if (true) throw new BusinessException(ErrorCode.NICKNAME_TAKEN);`을 임시로 넣고, `SignupIntegrationTest`를 하나 새로 만들어 "실패 후 같은 코드로 verify가 여전히 200인지"를 본다. 트랜잭션 롤백으로 `verified_at`이 비어 있어야 한다. 되돌린다.

## 8. 확인 문제

1. 블로그가 4개인 회원이 동시에 두 번 개설하면, 확인만 하는 코드에서 무슨 일이 생기나?
<details><summary>답</summary>두 요청이 둘 다 count 4를 보고 둘 다 저장해 6개가 된다. 확인과 저장 사이에 다른 요청이 끼어드는 경쟁 조건(check-then-act)이다.</details>

2. 블로그 5개 한도를 DB UNIQUE 제약으로 막을 수 없는 이유와, 이 프로젝트가 쓴 방법은?
<details><summary>답</summary>UNIQUE는 "같은 값이 둘이면 안 됨"만 표현하고 "다섯 개까지" 같은 개수 규칙은 표현하지 못한다. 회원 행을 <code>SELECT … FOR UPDATE</code>(<code>findByIdForUpdate</code>)로 잠가 같은 회원의 개설 요청을 차례로 처리한다.</details>

3. 블로그 행이 아니라 회원 행을 잠그는 이유는?
<details><summary>답</summary>아직 만들어지지 않은 6번째 블로그 행은 잠글 수 없다. "이 회원의 블로그 만들기"를 회원 행 하나로 줄 세우면, 같은 회원 요청만 기다리고 다른 회원끼리는 서로 막지 않는다.</details>

4. 주소 중복은 회원 잠금으로 막을 수 없다. 왜이며 무엇이 막나?
<details><summary>답</summary>서로 다른 회원이 같은 주소로 동시에 개설할 수 있는데, 둘은 다른 회원 행을 잠그므로 서로 기다리지 않는다. <code>uk_blog_address</code> UNIQUE가 두 번째 INSERT를 거절하고, 서비스가 <code>DataIntegrityViolationException</code>을 409 <code>BLOG_ADDRESS_TAKEN</code>으로 바꾼다.</details>

5. `save` 대신 `saveAndFlush`를 쓰는 이유는?
<details><summary>답</summary><code>save</code>는 INSERT를 커밋할 때까지 미룰 수 있어서 UNIQUE 위반 예외가 메서드 밖(커밋 시점)에서 터진다. <code>saveAndFlush</code>는 INSERT를 바로 보내 <code>try</code> 안에서 예외를 잡아 오류 코드로 바꿀 수 있다.</details>

6. 가입 중 회원 INSERT가 실패하면 인증 코드의 `verified_at`은 어떻게 되나? 그 이유는?
<details><summary>답</summary>함께 롤백되어 비어 있다. <code>consume</code>은 기본 전파 <code>REQUIRED</code>로 <code>signup</code>의 트랜잭션에 합류하고, 런타임 예외가 나가면 트랜잭션 전체가 롤백되기 때문이다. 그래서 같은 코드로 다시 가입할 수 있다.</details>

7. "회원당 대표 블로그 하나"를 `UNIQUE(member_id, is_primary)`로 하면 안 되는 이유와 실제 방법은?
<details><summary>답</summary>대표가 아닌 블로그(<code>is_primary = 0</code>)도 회원당 하나로 제한되어 버린다. 대표이고 삭제되지 않았을 때만 <code>member_id</code>, 아니면 <code>NULL</code>인 계산 컬럼 <code>primary_owner_id</code>에 UNIQUE를 건다. MySQL UNIQUE는 <code>NULL</code>끼리 겹쳐도 되므로 대표만 하나로 제한된다.</details>

8. 같은 클래스 안에서 `@Transactional` 메서드를 `this`로 부르면 어떻게 되나?
<details><summary>답</summary>Spring 트랜잭션은 프록시가 처리하는데, <code>this</code> 호출은 프록시를 거치지 않아 그 메서드의 <code>@Transactional</code> 설정이 적용되지 않는다(바깥 트랜잭션이 있으면 그냥 그 안에서 실행된다).</details>

9. 낙관적 잠금(`@Version`)이 블로그 개설 경쟁에 잘 맞지 않는 이유는?
<details><summary>답</summary>낙관적 잠금은 이미 있는 행을 수정할 때 버전이 그대로인지 비교하는 방식이다. 블로그 개설은 새 행을 INSERT하는 일이라 비교할 행이 없고, 실패하면 재시도 코드도 필요하다.</details>

## 9. 더 읽을거리

- MySQL 8.0 레퍼런스, "InnoDB Locking", "Locking Reads (SELECT ... FOR UPDATE)", "Deadlocks in InnoDB", "Transaction Isolation Levels"
- MySQL 8.0 레퍼런스, "CREATE TABLE and Generated Columns", "Secondary Indexes and Generated Columns"
- Spring Framework 레퍼런스, "Transaction Management": 선언적 트랜잭션, 프록시, 롤백 규칙, 전파
- Spring Data JPA 레퍼런스, "Locking" (`@Lock`)
- Jakarta Persistence 명세, `LockModeType` (PESSIMISTIC_WRITE, OPTIMISTIC)
- Java `java.util.concurrent`: `ExecutorService`, `Callable`, `Future`
- data-model.md blog 테이블(`primary_owner_id`), contracts/rest-api.md 409 오류 목록
