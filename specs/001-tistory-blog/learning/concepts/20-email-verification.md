# 20. 이메일 인증 코드와 요청 제한

> 관련 스텝: [스텝 4](../step-04.md) (T017), [스텝 9](../step-09.md) (T055a) · 관련 개념: [40-attempt-limit](./40-attempt-limit.md), [17-idempotency-redis](./17-idempotency-redis.md), [21-signup-login](./21-signup-login.md), [06-jpa-entity-mapping](./06-jpa-entity-mapping.md), [07-spring-mvc-exception-handling](./07-spring-mvc-exception-handling.md), [05-spring-testing](./05-spring-testing.md)

## 1. 이 문서로 배우는 것

- 이메일 인증을 왜 하는지, 이 서비스에서 언제 하는지(OWN-01, 회원을 만들기 **전** 단계)
- 인증 방식 두 가지: 코드를 입력하는 방식과 링크를 누르는 방식
- 인증 코드를 만들 때 `Random`이 아니라 `SecureRandom`을 쓰는 이유
- 6자리, 10분, 1분 같은 숫자를 정하는 기준
- 같은 이메일로 코드를 여러 번 받았을 때 "가장 최근 코드만" 보는 방법과 그 쿼리를 빠르게 하는 인덱스
- "확인만 하는 것(verify)"과 "써 버리는 것(consume)"을 나눈 이유
- 요청 제한(rate limit): 1분 안에 다시 보내기를 Redis `SET NX`와 TTL로 막는 방법, 429와 `retryAfterSeconds`
- 메일 보내기를 인터페이스(`EmailSender`) 뒤로 숨기는 이유(의존성 역전), 개발 중에는 로그로 대신 보내기
- 이메일을 소문자로 맞추는 정규화
- 이 설계에 남아 있는 위험: 가입 여부 노출, 코드 무차별 대입

**먼저 알면 좋은 것**: Spring의 `@Service`와 `@Transactional`, JPA 엔티티와 Repository([06](./06-jpa-entity-mapping.md)), Redis의 `SET NX`와 TTL([17](./17-idempotency-redis.md)).

## 2. 왜 필요한가

이메일 인증 없이 가입을 받으면 이런 일이 생긴다.

- **남의 이메일로 가입**: `jiwon@example.com`의 주인이 아닌 사람이 그 주소로 가입한다. 진짜 주인은 나중에 가입하려 할 때 "이미 가입된 이메일"을 보게 된다. 비밀번호 재설정(OWN-02) 메일은 진짜 주인에게 가므로, 재설정 링크가 엉뚱한 계정을 열게 된다.
- **오타로 연락 불가**: `jiwon@exmaple.com`처럼 틀리게 적으면, 비밀번호를 잊었을 때 다시 들어올 방법이 없다.
- **스팸 계정 대량 생성**: 아무 문자열이나 이메일로 넣어 계정을 수백 개 만들 수 있다.

그래서 기능 명세 OWN-01은 "가입할 때 이메일로 인증 코드를 보내고, 코드를 확인해야만 회원이 만들어진다"고 정했다. 원본 문서에는 "가입 후 인증 전에는 글 발행 제한"이라는 다른 안도 있었지만, 이 서비스는 **회원을 만들기 전에** 인증을 끝내기로 했다(spec.md 명확화, review.md 1). 그래서 `member` 테이블에는 "인증 안 된 회원"이 없다. `email` 칸에 값이 있으면 모두 인증된 이메일이다.

그런데 인증 메일 자체도 악용될 수 있다. 버튼을 연타하거나 스크립트로 남의 주소에 인증 메일을 수천 통 보내면, 그 사람의 메일함이 넘치고 우리 메일 서버는 스팸 발송지로 찍힌다. 그래서 **같은 이메일로 1분 안에 다시 보내기를 막는 요청 제한**이 함께 필요하다.

## 3. 기본 개념

### 3.1 코드 방식과 링크 방식

| 방식 | 사용자가 하는 일 | 장점 | 단점 |
| --- | --- | --- | --- |
| 코드 입력 | 메일에 온 `482913`을 가입 화면에 입력 | 가입 화면을 떠나지 않는다. 휴대폰으로 메일을 보고 PC에 입력해도 된다 | 짧은 코드라 맞힐 수 있는 확률이 있다(3.4) |
| 링크 클릭 | 메일의 `https://.../verify?token=긴무작위값`을 누름 | 토큰이 길어 맞히기 불가능에 가깝다 | 메일을 연 기기에서 새 탭이 열린다. 가입 화면 상태를 이어 가기 어렵다 |

이 서비스는 가입 화면 한 장에서 끝내려고 **코드 방식**을 골랐다. 비밀번호 재설정(OWN-02)은 반대로 **링크 방식**이다(가입 화면이 없고, 링크 하나로 새 비밀번호 화면을 열면 되므로).

### 3.2 난수: Random과 SecureRandom

인증 코드는 **추측할 수 없어야** 한다. Java에는 난수 생성기가 두 종류 있다.

| 클래스 | 만드는 방식 | 예측 | 용도 |
| --- | --- | --- | --- |
| `java.util.Random` | 시드(seed)에서 정해진 공식으로 다음 수를 계산(선형 합동 생성기) | 앞에서 나온 값 몇 개를 보면 다음 값을 계산할 수 있다 | 게임, 시뮬레이션, 테스트 데이터 |
| `java.security.SecureRandom` | 운영체제가 모은 예측 불가능한 값(엔트로피)을 바탕으로 함 | 앞의 값을 알아도 다음 값을 알 수 없게 설계됨 | 비밀번호 재설정 토큰, 인증 코드, 세션 ID 등 **보안용** |

공격자가 자기 이메일로 인증 코드를 여러 번 받아 보면 `Random`이 낸 값의 흐름을 볼 수 있다. 그러면 다른 사람에게 간 다음 코드를 계산할 수 있다. 그래서 보안에 쓰는 값은 항상 `SecureRandom`이다.

### 3.3 TTL: 코드는 언제까지 유효한가

인증 코드에는 **수명**이 있어야 한다. 메일함이 나중에 털리거나, 오래된 메일이 다른 사람에게 보여도 이미 지난 코드는 쓸 수 없어야 하기 때문이다.

| 값 | 이 서비스 | 너무 짧으면 | 너무 길면 |
| --- | --- | --- | --- |
| 코드 길이 | 숫자 6자리(100만 가지) | 맞히기 쉽다 | 입력이 번거롭다 |
| 코드 수명 | 10분 | 메일이 늦게 오면 가입을 못 한다 | 맞혀 볼 시간이 늘고, 유출된 코드가 오래 살아 있다 |
| 다시 받기 간격 | 1분 | 메일 폭탄을 못 막는다 | 메일이 안 온 사용자가 오래 기다린다 |

이 값들은 기능 명세에 없어서 API 명세를 정리하며 정했다(rest-api.md "이 문서에서 채운 값", review.md B-23).

### 3.4 무차별 대입(brute force)

6자리 숫자는 100만 가지다. 한 번 시도할 때 맞힐 확률은 100만분의 1이지만, **시도 횟수에 제한이 없으면** 10분 동안 수십만 번 요청을 보내 볼 수 있다. 그래서 짧은 코드를 쓰는 서비스는 보통 다음 중 하나를 같이 둔다.

- 코드 하나당 틀릴 수 있는 횟수 제한(예: 5번 틀리면 그 코드는 폐기)
- IP·이메일당 확인 요청 속도 제한

스텝 4에서는 두지 않았다가(5.8 남은 위험), 스텝 9에서 **같은 이메일로 15분 안에 5번 틀리면 15분 동안 막는** 제한을 더했다(T055a, [40](./40-attempt-limit.md)).

### 3.5 요청 제한(rate limiting)과 429

**요청 제한**은 "같은 주체가 일정 시간에 할 수 있는 요청 수"를 정하는 것이다. HTTP에는 이것을 위한 상태 코드가 있다.

- **429 Too Many Requests** (RFC 6585): "너무 많이 보냈으니 나중에 다시 하라."
- 얼마나 기다리면 되는지는 표준 `Retry-After` 헤더로 줄 수도 있고, 본문에 담을 수도 있다. 이 프로젝트는 본문 `detail.retryAfterSeconds`로 준다(rest-api.md 오류 표).

가장 단순한 형태가 "**마지막 요청 뒤 N초 동안 금지**"(쿨다운)다. 이것은 Redis 키 하나로 만들 수 있다. "키가 있으면 금지 중, TTL이 남은 시간"이다.

### 3.6 의존성 역전: 메일 보내기를 인터페이스 뒤로

서비스 코드가 "SMTP 서버에 접속해 메일을 보내는 클래스"를 직접 쓰면:
- 개발 중에도 진짜 메일 서버가 있어야 한다.
- 테스트할 때마다 메일이 나간다.
- 메일 업체를 바꾸면 서비스 코드를 고쳐야 한다.

그래서 서비스는 **"메일을 보낼 수 있는 무언가"라는 인터페이스**에만 의존하고, 실제로 무엇이 보낼지는 바깥(스프링 빈 설정)에서 정한다. 이것을 **의존성 역전 원칙**(DIP)이라 한다. 상위 정책(가입 규칙)이 하위 세부(SMTP)에 끌려가지 않고, 세부가 정책이 정한 약속(인터페이스)을 따른다.

```
EmailVerificationService ──의존──▶ EmailSender (인터페이스)
                                        ▲          ▲
                              구현 ─────┘          └───── 구현 (나중에)
                      LoggingEmailSender          SmtpEmailSender
                      (로그로만 남김)              (실제 메일)
```

## 4. 동작 원리

가입 화면에서 사용자가 하는 일과 서버가 하는 일:

```
[코드 받기] POST /api/auth/email-verifications {email}
   ├ 이메일 정규화(소문자)
   ├ 이미 이메일로 가입한 회원이 있나 → 있으면 409 EMAIL_TAKEN
   ├ Redis SET email-verification:cooldown:{email} 1 NX EX 60
   │     실패(1분 안에 또 옴) → 429, detail.retryAfterSeconds = 남은 TTL
   ├ SecureRandom으로 6자리 코드
   ├ email_verification 행 INSERT (expires_at = 지금 + 10분)
   └ EmailSender.send(...)                → 202 Accepted (본문 없음)

[확인]     POST /api/auth/email-verifications/verify {email, code}
   ├ 그 이메일의 가장 최근 행 하나
   ├ 이미 썼거나(verified_at 있음) 코드가 다름 → 400 INVALID_VERIFICATION_CODE
   ├ 시간이 지남                              → 400 VERIFICATION_EXPIRED
   └ 200 (아무것도 바꾸지 않음)

[가입하기] POST /api/auth/signup {email, code, password, nickname}
   └ 같은 확인을 서버가 한 번 더 하고 verified_at = 지금 ── 회원 INSERT와 한 트랜잭션
```

### 4.1 확인(verify)과 사용(consume)을 나눈 이유

화면에서 "확인" 버튼은 **사용자에게 결과를 빨리 보여 주기 위한 것**이다. 여기서 코드를 써 버리면(verified_at 기록) 문제가 생긴다.

- 확인 뒤 닉네임이 중복이라 가입이 실패하면, 사용자는 코드를 새로 받아야 한다.
- 더 근본적으로, **화면 단계의 확인은 믿을 수 없다**. 공격자는 화면을 건너뛰고 `POST /api/auth/signup`만 직접 보낼 수 있다. 그래서 가입 요청에서 서버가 코드를 **다시** 확인해야 한다(헌법 원칙 IV "권한은 서버가 지킨다").

그래서:
- `verify`: 읽기 전용 트랜잭션, 아무것도 바꾸지 않는다. 몇 번 눌러도 된다.
- `consume`: 가입 트랜잭션 안에서 불리고 `verified_at`을 남긴다. 가입이 실패해 트랜잭션이 되돌아가면 `verified_at`도 되돌아가, 같은 코드로 다시 가입할 수 있다. 가입이 성공하면 그 코드는 다시 쓸 수 없다.

### 4.2 "가장 최근 코드만" 보는 이유

사용자가 "코드 받기"를 두 번 누르면(1분 지난 뒤) 행이 두 개 생긴다. 메일함에는 코드 두 개가 있다. 둘 다 받아 주면 맞힐 수 있는 코드가 늘어난다. 그래서 **가장 최근 행 하나**만 본다. 예전 코드를 입력하면 `INVALID_VERIFICATION_CODE`다.

"가장 최근 하나"는 SQL로 `WHERE email = ? ORDER BY created_at DESC, id DESC LIMIT 1`이다. 이것을 빠르게 하려고 ERD에 인덱스가 있다.

```sql
CREATE INDEX idx_email_verification_email_created_at ON email_verification (email ASC, created_at DESC);
```

인덱스가 `(email, created_at DESC)` 순서라, MySQL은 그 이메일 칸으로 바로 가서 맨 앞 하나만 읽으면 된다(정렬 작업이 따로 필요 없다). `id DESC`를 더 붙인 이유는 같은 시각(마이크로초까지 같은)에 두 행이 생겨도 순서가 정해지게 하려는 것이다([08](./08-pagination.md)의 정렬 안정성과 같은 이야기).

### 4.3 쿨다운을 DB가 아니라 Redis SET NX로

DB로도 할 수 있다. "가장 최근 행의 created_at이 1분 안이면 거절". 하지만 확인과 INSERT가 두 단계라, 같은 순간에 두 요청이 오면 둘 다 "1분 안에 보낸 적 없음"을 보고 둘 다 메일을 보낸다(경쟁 조건, [17](./17-idempotency-redis.md) 3.6).

Redis `SET key 1 NX EX 60`은 "없을 때만 저장"을 **명령 하나**로 하므로 동시에 와도 하나만 성공한다. 키는 60초 뒤 Redis가 알아서 지운다. 거절할 때는 `TTL key`로 남은 초를 읽어 `retryAfterSeconds`로 준다.

## 5. 이 프로젝트에서는

### 5.1 엔티티: EmailVerification

`src/main/java/com/nhnacademy/blog/auth/domain/EmailVerification.java`

```java
@Entity
@Table(name = "email_verification")
public class EmailVerification extends BaseCreatedEntity {
    ...
    public static EmailVerification issue(String email, String code, LocalDateTime expiresAt) {
        return new EmailVerification(email, code, expiresAt);
    }

    public boolean matches(String inputCode) {
        return code.equals(inputCode);
    }

    public boolean isExpiredAt(LocalDateTime now) {
        return !expiresAt.isAfter(now);
    }

    /** 이미 가입에 쓴 코드인가. */
    public boolean isUsed() {
        return verifiedAt != null;
    }

    /** 가입에 썼다고 남긴다. */
    public void markVerified(LocalDateTime now) {
        this.verifiedAt = now;
    }
```

- `extends BaseCreatedEntity`: 이 테이블은 `created_at`만 있고 `updated_at`이 없어서([06](./06-jpa-entity-mapping.md) Auditing) created만 있는 부모를 쓴다. `created_at`은 "최근 코드" 정렬에 쓰인다.
- 회원과 관계(`@ManyToOne`)가 없다. 가입 **전** 단계라 회원 행이 아직 없기 때문이다. 이메일 문자열로만 찾는다.
- `isExpiredAt`이 `!expiresAt.isAfter(now)`인 이유: 만료 시각과 정확히 같은 순간도 만료로 본다. "만료 시각이 지금보다 뒤일 때만 유효"를 뒤집은 것이다.
- 지금 시각을 엔티티가 직접 구하지 않고(`LocalDateTime.now()` 없음) 인자로 받는다. 서비스가 `Clock` 빈에서 시각을 넘기므로, 테스트에서 시각을 바꿀 수 있다.
- 상태를 바꾸는 메서드는 `markVerified` 하나뿐이다. setter를 열지 않아 "검증에 쓴다"는 뜻이 코드에 드러난다.

`src/main/java/com/nhnacademy/blog/auth/domain/EmailVerificationRepository.java`

```java
/** 그 이메일로 가장 최근에 보낸 코드. 인덱스 (email, created_at DESC)를 탄다. */
Optional<EmailVerification> findFirstByEmailOrderByCreatedAtDescIdDesc(String email);
```

Spring Data의 메서드 이름 규칙이다. `findFirst`(LIMIT 1) + `ByEmail`(WHERE email = ?) + `OrderByCreatedAtDescIdDesc`(정렬). 이름만으로 4.2의 SQL이 만들어진다.

### 5.2 이메일 정규화: Emails

`src/main/java/com/nhnacademy/blog/auth/domain/Emails.java`

```java
public static String normalize(String email) {
    return email == null ? null : email.trim().toLowerCase(Locale.ROOT);
}
```

- `Jiwon@Example.com`과 `jiwon@example.com`을 같은 주소로 저장·검색하려고 소문자로 맞춘다. 대부분의 메일 서비스가 대소문자를 구분하지 않는다.
- `Locale.ROOT`: 그냥 `toLowerCase()`는 컴퓨터의 언어 설정을 따른다. 터키어 설정에서는 `I`가 점 없는 `ı`로 바뀌어 `ADMIN` 같은 문자열이 엉뚱하게 바뀐다. 언어와 상관없는 변환을 하려면 `Locale.ROOT`를 준다.
- 참고로 MySQL의 기본 정렬 규칙(`utf8mb4_0900_ai_ci`, ci = case insensitive)은 비교 때 대소문자를 무시한다. 그래도 저장되는 값을 한 가지로 맞춰 두면 화면 표시와 다른 DB로 옮길 때가 깔끔하다.
- 앞뒤 공백 제거(`trim`)도 하지만, 요청 DTO의 `@Email` 검사가 먼저 돌아 공백이 섞인 값은 그 전에 400이 된다([22](./22-bean-validation.md)).

### 5.3 서비스: EmailVerificationService

`src/main/java/com/nhnacademy/blog/auth/application/EmailVerificationService.java`

**상수**

```java
static final Duration CODE_TTL = Duration.ofMinutes(10);
static final Duration RESEND_INTERVAL = Duration.ofMinutes(1);
private static final String COOLDOWN_PREFIX = "email-verification:cooldown:";
...
private final SecureRandom random = new SecureRandom();
```

`SecureRandom`은 만들 때 비용이 조금 들어서 필드 하나를 재사용한다. 여러 스레드가 함께 써도 안전하다.

**send: 코드 보내기**

```java
@Transactional
public void send(String rawEmail) {
    String email = Emails.normalize(rawEmail);
    if (memberRepository.existsByEmail(email)) {
        throw new BusinessException(ErrorCode.EMAIL_TAKEN);
    }
    // 1분 안에 다시 요청하면 거절한다. SET NX라 동시에 두 번 와도 하나만 통과한다
    String cooldownKey = COOLDOWN_PREFIX + email;
    if (!Boolean.TRUE.equals(redis.opsForValue().setIfAbsent(cooldownKey, "1", RESEND_INTERVAL))) {
        Long seconds = redis.getExpire(cooldownKey);
        throw new BusinessException(ErrorCode.TOO_MANY_REQUESTS,
                new RetryAfterDetail(seconds == null || seconds < 1 ? 1 : seconds));
    }

    String code = "%06d".formatted(random.nextInt(1_000_000));
    verificationRepository.save(EmailVerification.issue(email, code, LocalDateTime.now(clock).plus(CODE_TTL)));
    emailSender.send(email, "[블로그] 이메일 인증 코드",
            "인증 코드: " + code + "\n" + CODE_TTL.toMinutes() + "분 안에 가입 화면에 입력해 주세요.");
}
```

줄별로:
1. 이메일을 정규화한다. 이후 모든 비교·저장은 정규화된 값으로 한다.
2. `existsByEmail`: 이미 이메일로 가입한 회원이 있으면 409. 메일을 보내 봐야 가입할 수 없으니 먼저 알려 준다. 소셜 가입 회원은 `email`이 NULL이라 걸리지 않는다(같은 사람이 이메일로 따로 가입할 수 있다, spec 4.6).
3. `setIfAbsent(key, "1", 1분)`: Redis `SET key 1 NX PX 60000`. 값 `"1"`은 의미가 없고 **키가 있는지**만 중요하다. `Boolean.TRUE.equals`로 비교하는 이유는 [17](./17-idempotency-redis.md) 5.3과 같다(null 가능).
4. 실패하면 `getExpire(key)`로 남은 초를 읽는다. Redis `TTL` 명령이다. 키가 그 사이에 사라졌으면 `-2`가 오는데, 1보다 작으면 1로 맞춰 "1초 뒤 다시"라고 답한다.
5. `"%06d".formatted(random.nextInt(1_000_000))`: 0~999999 중 하나를 6자리로 맞춘다. `42`면 `"000042"`. 앞자리 0을 빼먹으면 5자리 이하 코드가 생겨 화면의 "숫자 6자리" 검사와 어긋난다. `nextInt(1_000_000)`은 범위 안에서 고르게 뽑는다(`% 1000000`으로 자르면 값이 한쪽으로 몰릴 수 있다).
6. 행을 저장하고 메일을 보낸다. 메일은 트랜잭션 안에서 보낸다. 실제 SMTP로 바꿀 때는 "DB는 되돌아갔는데 메일은 나간" 경우가 생길 수 있어, 트랜잭션이 끝난 뒤 보내도록 바꾸는 것을 고려해야 한다(지금은 로그라 상관없다).

참고: 쿨다운 키는 DB 저장보다 **먼저** 만든다. DB 저장이 실패하면 사용자는 1분을 기다려야 한다. 반대 순서면 동시 요청이 둘 다 DB에 들어가므로, 드문 실패 쪽을 감수했다.

**verify와 consume**

```java
@Transactional(readOnly = true)
public void verify(String rawEmail, String code) {
    check(Emails.normalize(rawEmail), code);
}

/** 가입 트랜잭션 안에서 부른다. 가입이 실패하면 함께 되돌아가 코드를 다시 쓸 수 있다. */
@Transactional
public void consume(String rawEmail, String code) {
    check(Emails.normalize(rawEmail), code).markVerified(LocalDateTime.now(clock));
}

/** 가장 최근 코드만 본다. 틀렸거나 이미 썼으면 INVALID, 맞지만 시간이 지났으면 EXPIRED. */
private EmailVerification check(String email, String code) {
    EmailVerification latest = verificationRepository.findFirstByEmailOrderByCreatedAtDescIdDesc(email)
            .filter(verification -> !verification.isUsed() && verification.matches(code))
            .orElseThrow(() -> new BusinessException(ErrorCode.INVALID_VERIFICATION_CODE));
    if (latest.isExpiredAt(LocalDateTime.now(clock))) {
        throw new BusinessException(ErrorCode.VERIFICATION_EXPIRED);
    }
    return latest;
}
```

- `consume`의 `@Transactional`은 기본 전파(REQUIRED)라, `AuthService.signup`의 트랜잭션 안에서 불리면 **새 트랜잭션을 만들지 않고 그 트랜잭션에 참여**한다([23](./23-transactions-locking.md)). 그래서 회원 저장이 실패하면 `verified_at`도 함께 되돌아간다.
- `markVerified`는 `save`를 부르지 않는다. 트랜잭션 안에서 읽은 엔티티는 영속성 컨텍스트가 관리하고, 필드를 바꾸면 커밋 때 UPDATE가 나간다(변경 감지, [06](./06-jpa-entity-mapping.md)).
- 판단 순서: 행이 없거나, 이미 썼거나, 코드가 다르면 → INVALID. 그다음 만료면 → EXPIRED. 틀린 코드에 "만료"라고 답하지 않는다. 코드가 맞을 때만 만료를 알려 준다.

### 5.4 429의 detail: RetryAfterDetail

`src/main/java/com/nhnacademy/blog/global/error/RetryAfterDetail.java`

```java
public record RetryAfterDetail(long retryAfterSeconds) {
}
```

`BusinessException(ErrorCode.TOO_MANY_REQUESTS, detail)`로 던지면 `GlobalExceptionHandler`가 오류 본문의 `detail`에 넣는다([07](./07-spring-mvc-exception-handling.md)).

```json
{ "code": "TOO_MANY_REQUESTS", "message": "잠시 후 다시 시도해 주세요.", "detail": { "retryAfterSeconds": 42 } }
```

연타 방지([17](./17-idempotency-redis.md))의 429는 `Map.of("retryAfterSeconds", 1)`로 같은 모양을 만든다. 프론트는 `retryAfterSeconds(error)`(`frontend/src/api/errors.ts`)로 숫자를 꺼내 "잠시 후 다시 시도해 주세요. (42초)"를 띄운다.

### 5.5 메일 보내기: EmailSender와 LoggingEmailSender

`src/main/java/com/nhnacademy/blog/auth/application/EmailSender.java`

```java
public interface EmailSender {

    void send(String to, String subject, String text);

}
```

`src/main/java/com/nhnacademy/blog/auth/application/LoggingEmailSender.java`

```java
@Component
public class LoggingEmailSender implements EmailSender {

    private static final Logger log = LoggerFactory.getLogger(LoggingEmailSender.class);

    @Override
    public void send(String to, String subject, String text) {
        log.info("[개발용 메일] 받는 사람: {}, 제목: {}\n{}", to, subject, text);
    }

}
```

- `EmailVerificationService`의 생성자는 `EmailSender` 타입을 받는다. 스프링이 그 타입의 빈을 찾아 넣는데, 지금은 `LoggingEmailSender` 하나뿐이라 그것이 들어간다.
- 실제 메일을 붙일 때(tasks T017 "메일 발송은 2주차로 미뤄도 됨"): `SmtpEmailSender implements EmailSender`를 만들고, 두 구현 중 무엇을 쓸지는 프로필(`@Profile("prod")`)이나 설정값으로 고른다. `EmailVerificationService`는 한 줄도 바뀌지 않는다.
- 로그의 `{}`는 SLF4J 자리표시자다. 문자열을 `+`로 이어 붙이지 않아, 로그 수준이 꺼져 있으면 문자열을 만들지도 않는다.
- 주의: 운영에서 인증 코드를 로그에 남기면 로그를 볼 수 있는 사람이 남의 가입을 대신할 수 있다. 이 구현은 **개발용**이다.

### 5.6 컨트롤러와 요청 DTO

`src/main/java/com/nhnacademy/blog/auth/presentation/EmailVerificationController.java`

```java
/** 202: 요청을 받았고 메일은 따로 간다. 이미 가입된 이메일 409, 1분 안에 다시 요청 429. */
@PostMapping("/api/auth/email-verifications")
public ResponseEntity<Void> send(@Valid @RequestBody EmailVerificationRequest request) {
    emailVerificationService.send(request.email());
    return ResponseEntity.accepted().build();
}

/** 화면 단계 확인. 맞으면 200, 틀리면 400 INVALID_VERIFICATION_CODE, 시간이 지났으면 400 VERIFICATION_EXPIRED. */
@PostMapping("/api/auth/email-verifications/verify")
public ResponseEntity<Void> verify(@Valid @RequestBody EmailCodeRequest request) {
    emailVerificationService.verify(request.email(), request.code());
    return ResponseEntity.ok().build();
}
```

- **202 Accepted**: "요청은 받았고, 처리(메일 도착)는 따로 일어난다"는 뜻이다. 메일이 실제로 도착했는지는 서버가 알 수 없으므로 200보다 정확하다.
- 두 응답 모두 **본문이 없다**. 그래서 프론트 `api()`가 본문 없는 200·202를 처리하도록 스텝 4에서 고쳤다(`response.text()`가 비어 있으면 `undefined`, [25](./25-react-forms-data.md)).
- `EmailCodeRequest`의 `@Pattern(regexp = "\\d{6}")`: 코드는 숫자 6자리만 받는다. 형식이 틀리면 DB를 보기도 전에 400 `VALIDATION_FAILED`(fieldErrors `code`)다.

### 5.7 테스트

`src/test/java/com/nhnacademy/blog/auth/EmailVerificationIntegrationTest.java`, 도우미 `src/test/java/com/nhnacademy/blog/support/TestEmails.java`

메일이 로그로만 나가므로 테스트는 **DB에서 코드를 읽는다**.

```java
public String latestCode(String email) {
    return jdbcTemplate.queryForObject(
            "SELECT code FROM email_verification WHERE email = ? ORDER BY created_at DESC, id DESC LIMIT 1",
            String.class, email);
}

public void expireLatest(String email) {
    jdbcTemplate.update("UPDATE email_verification SET expires_at = NOW() - INTERVAL 1 MINUTE WHERE email = ?",
            email);
}
```

`TestEmails.unique()`가 테스트마다 다른 이메일을 만든다. 테스트들이 같은 DB와 Redis를 함께 쓰므로(컨텍스트 재사용, [05](./05-spring-testing.md)), 같은 이메일을 쓰면 다른 테스트의 쿨다운에 걸린다.

| 테스트 | 확인하는 것 |
| --- | --- |
| `sendsSixDigitCodeAndVerifiesIt` | 202, 코드가 숫자 6자리, 확인 200, 확인을 두 번 해도 200(코드를 쓰지 않음) |
| `emailIsComparedIgnoringCase` | 대문자로 받은 코드를 소문자 이메일로 확인 가능 |
| `wrongCodeIsRejected` | 틀린 코드, 코드를 받은 적 없는 이메일 → 400 INVALID |
| `expiredCodeIsRejected` | 만료 시각을 과거로 바꾸면 400 EXPIRED |
| `resendWithinOneMinuteIs429` | 바로 다시 받기 → 429, `detail.retryAfterSeconds`가 숫자 |
| `registeredEmailIs409` | 가입한 이메일 → 409 EMAIL_TAKEN |
| `invalidInputIs400` | 이메일 형식, 코드 형식 → 400 fieldErrors |

"같은 코드로 두 번 가입 못 함", "가입 실패 시 코드 재사용 가능"은 가입 테스트([21](./21-signup-login.md))에서 확인한다.

### 5.8 남은 위험(아직 고치지 않음)

| 위험 | 내용 | 대책 후보 |
| --- | --- | --- |
| 코드 무차별 대입 | ~~`verify`와 `signup`의 코드 확인에 시도 횟수 제한이 없다~~ → **스텝 9에서 고침**: 같은 이메일로 15분 안에 5번 틀리면 15분 동안 429 | 이메일별 실패 횟수(Redis `INCR` + TTL), [40](./40-attempt-limit.md) |
| 가입 여부 노출 | `send`가 409 `EMAIL_TAKEN`을 주므로, 아무 이메일이나 넣어 보면 우리 회원인지 알 수 있다(계정 열거) | 가입된 이메일에도 202를 주고 "이미 가입된 계정입니다" 안내 메일을 보내기. 대신 가입 화면에서 바로 알려 주는 편의는 사라진다 |

두 번째는 의도한 트레이드오프다. API 명세가 409를 정했고(가입 화면에서 "이미 가입한 이메일입니다. 로그인해 주세요"를 바로 보여 주는 편의), 로그인과 비밀번호 재설정에서는 반대로 가입 여부를 숨긴다([21](./21-signup-login.md) 3.2). 첫 번째는 지원이 정할 것으로 남겨 두었고, 스텝 9에서 지원이 15분·5번으로 정했다(research R-17).

## 6. 자주 하는 실수와 함정

1. **`Random`으로 코드 만들기**: 앞의 코드들을 보고 다음 코드를 계산할 수 있다. 보안 값은 `SecureRandom`.
2. **앞자리 0 빼먹기**: `String.valueOf(random.nextInt(1_000_000))`은 `"42"`가 될 수 있다. `%06d`로 맞춘다.
3. **화면의 "확인"만 믿고 가입 처리**: 공격자는 가입 API만 직접 부른다. 가입 요청에서 서버가 다시 확인한다.
4. **확인 단계에서 코드를 써 버리기**: 가입이 다른 이유로 실패하면 코드를 새로 받아야 한다. 쓰는 것은 가입 트랜잭션 안에서.
5. **예전 코드도 받아 주기**: 맞힐 수 있는 코드 수가 늘어난다. 가장 최근 하나만.
6. **"최근 1분 안에 보냈나"를 DB 조회 후 INSERT로**: 동시 요청이 둘 다 통과한다. 원자적인 `SET NX`를 쓴다.
7. **`toLowerCase()`에 Locale 빼먹기**: 서버 언어 설정에 따라 결과가 달라진다. `Locale.ROOT`.
8. **운영에서 로그 메일 구현을 그대로 쓰기**: 인증 코드가 로그 파일에 남는다. 운영은 실제 메일 구현으로 바꿔야 한다.
9. **테스트에서 같은 이메일 재사용**: 다른 테스트가 만든 쿨다운 키(1분) 때문에 429가 나 엉뚱한 실패가 생긴다.

## 7. 직접 해 보기

**실습 1. 테스트 돌리기**

```bash
./mvnw test -Dtest=EmailVerificationIntegrationTest
```

**실습 2. 서버에서 코드 받아 보기**

```bash
docker compose up -d
./mvnw spring-boot:run          # 다른 터미널
```

```bash
curl -i --resolve blog.test:8080:127.0.0.1 \
  -H 'X-Requested-With: XMLHttpRequest' -H 'Content-Type: application/json' \
  -X POST http://blog.test:8080/api/auth/email-verifications -d '{"email":"me@example.com"}'
# HTTP/1.1 202
```

서버 로그(`spring-boot:run`을 띄운 터미널)에 이렇게 나온다.

```
... LoggingEmailSender : [개발용 메일] 받는 사람: me@example.com, 제목: [블로그] 이메일 인증 코드
인증 코드: 482913
10분 안에 가입 화면에 입력해 주세요.
```

로그를 파일로 남겼다면 `grep -A2 '\[개발용 메일\]' server.log`로 찾는다.

**실습 3. 쿨다운 들여다보기**

같은 curl을 바로 다시 보내면 429와 남은 초가 온다. Redis에서 키를 본다.

```bash
docker exec blog-redis redis-cli TTL email-verification:cooldown:me@example.com    # 예: (integer) 47
docker exec blog-redis redis-cli DEL email-verification:cooldown:me@example.com    # 지우면 바로 다시 보낼 수 있다
```

**실습 4. 코드 확인과 만료**

```bash
curl -i --resolve blog.test:8080:127.0.0.1 -H 'X-Requested-With: XMLHttpRequest' -H 'Content-Type: application/json' \
  -X POST http://blog.test:8080/api/auth/email-verifications/verify -d '{"email":"me@example.com","code":"482913"}'
docker exec -it blog-mysql mysql -ublog -pblog blog \
  -e "SELECT email, code, expires_at, verified_at, created_at FROM email_verification ORDER BY id DESC LIMIT 3;"
```

`expires_at`을 과거로 바꾼(`UPDATE ... SET expires_at = NOW() - INTERVAL 1 MINUTE`) 뒤 다시 확인하면 `VERIFICATION_EXPIRED`가 온다.

**실습 5. 경쟁 조건 만들어 보기**

`EmailVerificationService.send`의 쿨다운을 "확인 후 저장"으로 바꿔 본다(`hasKey` 확인 뒤 `set`). 두 터미널에서 같은 이메일로 동시에 curl을 보내면(또는 `& ` 로 두 개 띄우기) 둘 다 202가 나오는 경우가 생긴다. 원래대로 되돌린다.

## 8. 확인 문제

1. 이 서비스가 이메일 인증을 "가입 후"가 아니라 "회원을 만들기 전"에 하도록 한 결과, `member.email`에 대해 무엇을 믿을 수 있게 됐나?
<details><summary>답</summary><code>email</code> 칸에 값이 있는 회원은 모두 인증을 마친 회원이다. "인증 안 된 회원" 상태가 없어서 그 상태를 따로 검사할 필요가 없다.</details>

2. 인증 코드를 `java.util.Random`으로 만들면 안 되는 이유는?
<details><summary>답</summary><code>Random</code>은 시드에서 정해진 공식으로 수를 계산하므로, 공격자가 자기 이메일로 코드를 여러 번 받아 보면 다음 값을 예측할 수 있다. 보안용 값은 예측할 수 없게 설계된 <code>SecureRandom</code>을 쓴다.</details>

3. verify와 consume을 나눈 이유 두 가지는?
<details><summary>답</summary>(1) 화면의 확인 단계에서 코드를 써 버리면 가입이 다른 이유로 실패했을 때 코드를 새로 받아야 한다. (2) 화면 단계 확인은 건너뛸 수 있으므로 가입 요청에서 서버가 다시 확인하고 그때 써야 한다. consume은 가입 트랜잭션 안에서 불려 가입이 실패하면 함께 되돌아간다.</details>

4. 같은 이메일로 코드를 두 번 받았을 때 첫 번째 코드를 입력하면 어떻게 되고, 그렇게 한 이유는?
<details><summary>답</summary>400 INVALID_VERIFICATION_CODE다. 가장 최근 행만 보기 때문이다. 예전 코드도 받아 주면 맞힐 수 있는 코드 수가 늘어난다.</details>

5. 1분 쿨다운을 "가장 최근 행의 created_at이 1분 안인가"로 검사하면 생기는 문제는?
<details><summary>답</summary>확인과 INSERT가 두 단계라, 동시에 온 두 요청이 둘 다 "없음"을 보고 둘 다 메일을 보낸다(경쟁 조건). Redis <code>SET NX</code>는 확인과 저장이 한 명령이라 하나만 통과한다.</details>

6. 429 응답에서 프론트가 남은 시간을 아는 방법은?
<details><summary>답</summary>오류 본문의 <code>detail.retryAfterSeconds</code>. 서버는 쿨다운 키의 남은 TTL(<code>getExpire</code>)을 넣어 준다.</details>

7. `EmailSender`를 인터페이스로 둔 덕분에 실제 메일 발송을 붙일 때 바뀌는 것과 바뀌지 않는 것은?
<details><summary>답</summary>새 구현 클래스(예: SMTP)를 만들고 어느 구현을 쓸지 빈 설정(프로필 등)만 바꾼다. <code>EmailVerificationService</code>는 인터페이스에만 의존하므로 바뀌지 않는다.</details>

8. 이 설계에 남아 있는 보안 위험 두 가지와 대책 후보는?
<details><summary>답</summary>(1) 코드 확인 시도 횟수 제한이 없어 6자리를 무차별 대입할 수 있다 → 코드별 실패 횟수 제한, 요청 속도 제한. (2) 409 EMAIL_TAKEN으로 가입 여부가 드러난다 → 가입된 이메일에도 202를 주고 안내 메일 보내기(가입 화면의 즉시 안내 편의와 맞바꿈).</details>

## 9. 더 읽을거리

- RFC 6585 "Additional HTTP Status Codes" 4절 429 Too Many Requests
- RFC 9110 15.3.3 "202 Accepted", 10.2.3 "Retry-After"
- OWASP Cheat Sheet: Authentication(계정 열거), Forgot Password(토큰·코드 설계)
- Java API 문서: `java.security.SecureRandom`, `java.util.Random`의 "not cryptographically secure" 안내
- Spring Data JPA 레퍼런스 "Query Methods" 중 `First`/`Top`, `OrderBy`
- Redis 문서: SET(NX, EX), TTL
- Robert C. Martin, 의존성 역전 원칙(DIP)
- rest-api.md "이 문서에서 채운 값"(6자리·10분·1분), spec.md OWN-01
