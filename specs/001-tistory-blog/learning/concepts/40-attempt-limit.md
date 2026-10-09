# 40. 시도 횟수 제한: 비밀번호·인증 코드 무차별 대입 막기

> 관련 스텝: [스텝 9](../step-09.md) (T055a) · 관련 개념: [09-password-hashing](./09-password-hashing.md), [17-idempotency-redis](./17-idempotency-redis.md), [20-email-verification](./20-email-verification.md), [21-signup-login](./21-signup-login.md), [23-transactions-locking](./23-transactions-locking.md), [38-member-profile-update](./38-member-profile-update.md)

## 1. 이 문서로 배우는 것

- **온라인 무차별 대입**: 서버에 직접 비밀번호·코드를 계속 넣어 보는 공격과, bcrypt로는 막을 수 없는 이유
- 막는 방법들: 계정(대상)별 실패 횟수 제한, IP별 요청 제한, CAPTCHA, 점점 늘어나는 대기
- 이 프로젝트의 규칙: **15분 안에 5번 틀리면, 다섯 번째로 틀린 때부터 15분 동안 막는다**(지원 결정, research R-17)
- Redis `INCR` + `EXPIRE`로 실패 횟수 세기
- "몇 번 틀렸나 보고 → 확인"이 **동시 요청에 뚫리는 이유**와, 확인 **전에** 먼저 하나 올려 자리를 잡는 방법
- 맞으면 지우고, 틀리면 남기고, "틀린 것이 아닌 실패"는 되돌리기
- 가입하지 않은 이메일도 똑같이 세는 이유(가입 여부 숨기기)
- 계정 잠금의 약점: 남이 일부러 틀려서 내 로그인을 막을 수 있다
- 화면: 429에 "15분 뒤에 다시 시도해 주세요"

**먼저 알면 좋은 것**: bcrypt와 work factor([09](./09-password-hashing.md)), Redis·`SET NX`·TTL([17](./17-idempotency-redis.md)), 인증 코드와 1분 재발송 제한·429([20](./20-email-verification.md)), 로그인과 계정 열거 방어([21](./21-signup-login.md)), 경쟁 조건([23](./23-transactions-locking.md)).

## 2. 왜 필요한가

스텝 9를 마치고 지원이 물었다. "비밀번호 인증 틀리는 개수에 대한 제한이 있나?" 확인해 보니 **어디에도 없었다**.

| 경로 | 막는 것이 없으면 |
| --- | --- |
| 로그인 `POST /api/auth/login` | 남의 이메일에 흔한 비밀번호를 계속 넣어 본다 |
| 인증 코드 확인 `POST /api/auth/email-verifications/verify`, 가입 | 6자리 코드(100만 가지)를 10분 동안 계속 넣어 본다. 남의 이메일로 가입할 수 있다 |
| 비밀번호 변경 `PUT /api/me/password` | 잠깐 얻은 로그인 상태로 지금 비밀번호를 계속 맞혀 본다([38](./38-member-profile-update.md) 3.2의 보호가 무너진다) |

bcrypt([09](./09-password-hashing.md))는 **DB가 털린 뒤**(오프라인) 해시를 거꾸로 푸는 것을 느리게 한다. 서버에 직접 요청을 보내는 **온라인** 공격은 서버가 대신 bcrypt를 계산해 주므로, 횟수를 막지 않으면 공격자는 기다리기만 하면 된다. 게다가 bcrypt는 일부러 느려서(한 번에 수십~수백 밀리초) 대량 시도는 서버 CPU를 잡아먹는다.

## 3. 기본 개념

### 3.1 막는 방법들

| 방법 | 기준 | 장점 | 단점 |
| --- | --- | --- | --- |
| **대상별 실패 횟수 제한** (이 프로젝트) | 이메일·회원마다 | 한 계정을 노린 공격을 정확히 막음 | 남이 일부러 틀려 그 계정을 잠글 수 있음(3.5) |
| IP별 요청 제한 | 보낸 곳마다 | 여러 계정을 훑는 공격도 막음 | 공용 IP(회사·학교)가 함께 막힘, IP를 바꾸면 피함 |
| CAPTCHA | 몇 번 틀리면 사람 확인 | 자동 공격에 강함 | 외부 서비스·화면 작업 필요 |
| 점점 늘어나는 대기 | 틀릴수록 1초, 2초, 4초… | 사람에게는 거의 안 보임 | 구현이 복잡 |

여러 개를 함께 쓰는 서비스가 많다. 이 프로젝트는 명세에 정한 것이 없어서 지원에게 물었고, 가장 단순하고 효과가 큰 **대상별 실패 횟수 제한**을 15분·5번으로 정했다.

### 3.2 규칙을 정확히

> 같은 대상으로 **15분 안에 5번** 틀리면, **다섯 번째로 틀린 때부터 15분 동안** 429. 막힌 동안은 **맞는 값도** 받지 않는다. **맞히면** 틀린 횟수를 지운다.

| 대상 | 키 | 무엇을 세나 |
| --- | --- | --- |
| 로그인 | 이메일 | `LOGIN_FAILED`(없는 이메일, 틀린 비밀번호, 탈퇴, 소셜 가입) |
| 인증 코드 | 이메일 | `INVALID_VERIFICATION_CODE`(틀리거나 이미 쓴 코드) |
| 비밀번호 변경 | 회원 번호 | 지금 비밀번호 틀림 |

"맞는 값도 받지 않는다"가 중요하다. 막힌 동안 맞는 값을 받아 준다면, 공격자는 "429가 아닌 응답이 나올 때까지" 계속 넣어 보면 되므로 제한이 아무 의미가 없다.

틀린 것이 아닌 실패는 세지 않는다. 비밀번호는 맞았는데 정지된 회원(403 `MEMBER_SUSPENDED`), 코드는 맞았는데 10분이 지난 경우(400 `VERIFICATION_EXPIRED`)는 공격자가 얻는 것이 없다.

### 3.3 Redis로 세기: `INCR`과 `EXPIRE`

```
INCR attempt:login:a@b.com        키가 없으면 0에서 1로 만들고 1을 돌려준다. 있으면 +1
EXPIRE attempt:login:a@b.com 900  이 키를 900초(15분) 뒤에 지운다
TTL attempt:login:a@b.com         남은 초. 막힌 동안은 이것이 retryAfterSeconds
DEL attempt:login:a@b.com         맞히면 지운다
```

DB 표 대신 Redis를 쓰는 이유는 인증 메일 재발송 제한([20](./20-email-verification.md))과 같다. 잠깐만 필요한 숫자이고, 요청마다 읽고 쓰며, TTL로 저절로 사라진다.

### 3.4 "보고 → 확인"은 동시 요청에 뚫린다

처음 떠오르는 방법은 이렇다.

```java
// 나쁜 예
if (실패 횟수(email) >= 5) throw 429;
if (!비밀번호_맞나()) { 실패_횟수_올리기(email); throw 401; }
```

공격자가 요청 100개를 **동시에** 보내면? 100개 모두 "지금 4번"을 보고 통과해서 비밀번호를 확인한다. 제한이 5번이 아니라 105번이 된다. 확인 후 행동(check-then-act) 경쟁 조건이다([23](./23-transactions-locking.md), [17](./17-idempotency-redis.md) 3.6).

해결은 **확인하기 전에 먼저 한 번을 예약**하는 것이다.

```java
long n = INCR(key);          // 동시에 와도 1, 2, 3, … 서로 다른 번호를 받는다(Redis는 명령을 하나씩 처리)
if (n > 5) throw 429;        // 6번째부터는 확인하지 않는다
확인();                        // 그래서 확인은 최대 5번만 일어난다
```

`INCR`은 명령 하나라 중간에 끼어들 수 없다. 100개가 동시에 와도 번호 1~5를 받은 다섯 요청만 비밀번호를 확인하고 나머지는 429다. 스텝 9의 테스트 `concurrentGuessesGetOnlyFiveTries`가 12개를 동시에 보내 정확히 5개만 401(확인함), 7개가 429인지 본다.

먼저 올렸으니, 결과에 따라 정리한다.

| 결과 | 할 일 |
| --- | --- |
| 맞음 | 키를 지운다(초기화) |
| 틀림 | 올린 수를 그대로 둔다. 이것이 다섯 번째(`n == 5`)면 수명을 15분으로 다시 잡는다(그때부터 15분 막음) |
| 틀린 것이 아닌 실패, 그 밖의 예외 | 올린 수를 되돌린다(`DECR`) |

### 3.5 가입 여부를 숨기기와 계정 잠금의 약점

로그인은 가입하지 않은 이메일도 **똑같이 센다**. 가입한 이메일만 막히면, 공격자는 "6번째에 429가 나오면 가입한 이메일"로 회원 목록을 알아낼 수 있다(계정 열거, [21](./21-signup-login.md) 3.2). 이 프로젝트는 응답 문장(LOGIN_FAILED 하나로 통일)과 응답 시간(없는 이메일도 가짜 해시와 비교)까지 맞춰 왔으니, 제한도 같아야 한다.

대상별 제한의 알려진 약점: **남이 내 이메일로 일부러 5번 틀리면 나도 15분 동안 로그인하지 못한다**(잠금 악용, 서비스 거부). 막는 방법으로 IP별 제한을 함께 두거나, 막힌 상태에서도 새 기기 인증(메일 링크)으로 들어오게 하는 방법이 있다. 이 프로젝트는 15분이면 풀리므로 받아들였고, research R-17에 "남은 것"으로 적었다.

인증 코드는 **새 코드를 받아도 틀린 횟수가 그대로**다. 새로 받을 때 지운다면, 공격자는 1분마다 새 코드를 받아(재발송 제한 1분) 5번씩 넣어 볼 수 있다. 틀린 횟수가 15분 동안 남아 있으면 그 길이 막힌다.

## 4. 동작 원리

### 4.1 로그인

```
POST /api/auth/login { email: "a@b.com", password: "..." }
  AuthService.login
    attemptLimiter.attempt("login:a@b.com", 확인, LOGIN_FAILED이면 틀림)
      INCR attempt:login:a@b.com → n
      n == 1(또는 수명이 없음) → EXPIRE 15분
      n > 5 → 429 { retryAfterSeconds: TTL }               ← 확인하지 않음
      확인: 회원 찾기 → bcrypt 비교 → 틀리면 LOGIN_FAILED
        맞음  → DEL (초기화)
        틀림  → 그대로, n == 5면 EXPIRE 15분(지금부터 막음) → 401
    정지 회원인지(맞힌 뒤에만) → 403 MEMBER_SUSPENDED
```

### 4.2 시간으로 보기

```
10:00  틀림 1   (키 생김, 10:15까지)
10:03  틀림 2
10:05  틀림 3
10:06  틀림 4
10:07  틀림 5   → 수명을 다시 15분으로: 10:22까지 막힘
10:08  맞는 비밀번호 → 429, retryAfterSeconds ≈ 840
10:22  키가 사라짐 → 다시 시도 가능
```

10:00에 한 번 틀리고 10:16에 또 틀리면, 10:15에 키가 사라졌으므로 새로 1부터 센다. "15분 안에 5번"이 이 뜻이다.

## 5. 이 프로젝트에서는

### 5.1 `global/auth/AttemptLimiter.java`

```java
public <T> T attempt(String key, Supplier<T> check, Predicate<BusinessException> isFailure) {
    String redisKey = PREFIX + key;
    Long reserved = redis.opsForValue().increment(redisKey);
    long count = reserved == null ? 1 : reserved;
    // 처음이거나, INCR 뒤 수명을 못 붙이고 끊겼던 키(수명 없음)면 15분 수명을 붙인다
    Long ttl = redis.getExpire(redisKey);
    if (count == 1 || ttl == null || ttl < 0) {
        redis.expire(redisKey, properties.window());
    }
    if (count > properties.maxFailures()) {
        throw locked(redisKey);
    }
    try {
        T result = check.get();
        redis.delete(redisKey);
        return result;
    } catch (BusinessException e) {
        if (isFailure.test(e)) {
            if (count == properties.maxFailures()) {
                // 다섯 번째로 틀림: 지금부터 15분 동안 막는다
                redis.expire(redisKey, properties.window());
            }
        } else {
            redis.opsForValue().decrement(redisKey);
        }
        throw e;
    } catch (RuntimeException e) {
        redis.opsForValue().decrement(redisKey);
        throw e;
    }
}
```

줄별로:

- `attempt(key, check, isFailure)`: 세 곳(로그인, 인증 코드, 비밀번호 변경)이 같은 규칙을 쓰게 하나로 만든 메서드다. 무엇을 확인할지(`check`)와 어떤 예외가 "틀림"인지(`isFailure`)만 넘긴다. 제네릭 `<T>`는 확인이 돌려주는 값(로그인이면 `Member`)을 그대로 돌려주려는 것이다.
- `increment`: Redis `INCR`. 확인 **전에** 자리를 잡는다(3.4). Spring Data Redis는 이 결과를 `Long`(null일 수 있는 타입)으로 주므로 null을 한 번 걸렀다.
- `getExpire` < 0이면 수명을 붙인다: `INCR` 뒤 `EXPIRE` 전에 서버가 죽으면 **수명 없는 키**가 남아 그 계정이 영원히 막힐 수 있다. 다음 시도 때 수명이 없으면(`-1`) 붙여서 그런 키가 남지 않게 했다. (두 명령을 Lua 스크립트 하나로 묶는 방법도 있다.)
- `count > maxFailures`: 6번째부터는 확인하지 않고 429. `locked`가 남은 수명(`TTL`)을 `RetryAfterDetail`에 담는다. 1초 미만이면 1로.
- 맞으면 `delete`, 틀리면 다섯 번째일 때만 수명 다시 잡기, 틀린 것이 아니면 `decrement`(3.4의 표).
- `catch (RuntimeException e)`: DB 오류 같은 예상 못 한 예외도 시도를 되돌린다. 서버 탓인 실패로 사용자가 막히면 안 된다.
- 설정은 `AttemptLimitProperties`(`app.attempt-limit.max-failures: 5`, `window: 15m`)다. 코드를 고치지 않고 바꿀 수 있다.

### 5.2 로그인: `AuthService.login`

```java
String email = Emails.normalize(rawEmail);
Member member = attemptLimiter.attempt("login:" + email, () -> {
    Optional<Member> found = memberRepository.findByEmail(email);
    String hash = found.map(Member::getPasswordHash).orElse(null);
    boolean matches = passwordEncoder.matches(password, hash == null ? dummyPasswordHash : hash);
    if (hash == null || !matches || found.get().isWithdrawn()) {
        throw new BusinessException(ErrorCode.LOGIN_FAILED);
    }
    return found.get();
}, e -> e.getErrorCode() == ErrorCode.LOGIN_FAILED);
if (member.isSuspendedAt(LocalDateTime.now(clock))) {
    throw new BusinessException(ErrorCode.MEMBER_SUSPENDED, suspensionDetails.of(member));
}
```

- 키는 **정규화한 이메일**(소문자, 앞뒤 공백 제거, [20](./20-email-verification.md) 5.2). `A@B.com`과 `a@b.com`이 다른 키가 되면 대소문자만 바꿔 제한을 피할 수 있다.
- 람다 안이 스텝 4의 로그인 확인 그대로다. 없는 이메일도 가짜 해시와 비교하고 같은 `LOGIN_FAILED`를 던지므로, 제한도 똑같이 걸린다(3.5).
- 정지 확인은 람다 **밖**이다. 비밀번호가 맞으면 람다가 끝나며 횟수가 지워지고, 그다음 403이 난다.

### 5.3 인증 코드: `EmailVerificationService.check`

```java
private EmailVerification check(String email, String code) {
    return attemptLimiter.attempt("email-code:" + email, () -> {
        EmailVerification latest = verificationRepository.findFirstByEmailOrderByCreatedAtDescIdDesc(email)
                .filter(verification -> !verification.isUsed() && verification.matches(code))
                .orElseThrow(() -> new BusinessException(ErrorCode.INVALID_VERIFICATION_CODE));
        if (latest.isExpiredAt(LocalDateTime.now(clock))) {
            throw new BusinessException(ErrorCode.VERIFICATION_EXPIRED);
        }
        return latest;
    }, e -> e.getErrorCode() == ErrorCode.INVALID_VERIFICATION_CODE);
}
```

- `verify`(확인 버튼)와 `consume`(가입할 때)이 모두 이 `check`를 거치므로 두 길이 같은 횟수를 나눠 쓴다. 가입 요청으로 코드를 맞혀 보는 길도 막힌다.
- 만료(`VERIFICATION_EXPIRED`)는 세지 않는다. 코드가 맞았다는 뜻이기 때문이다.
- [20](./20-email-verification.md) 5.8에 "남은 위험"으로 적어 두었던 "코드 무차별 대입"이 이것으로 막혔다.

### 5.4 비밀번호 변경: `MeService.changePassword`

```java
// 지금 비밀번호를 15분 안에 5번 틀리면 15분 동안 429 (T055a, R-17)
attemptLimiter.attempt("password-change:" + memberId, () -> {
    if (!passwordEncoder.matches(currentPassword, member.getPasswordHash())) {
        throw BusinessException.invalidField("currentPassword", "지금 비밀번호가 맞지 않습니다.");
    }
    return null;
}, e -> true);
PasswordRule.check("newPassword", newPassword);
```

- 키는 회원 번호다. 로그인한 사람만 오므로 이메일이 아니라 회원으로 센다.
- 람다 안에서 던지는 것은 "지금 비밀번호 틀림" 하나뿐이라 `e -> true`(모두 틀림).
- 새 비밀번호 규칙 검사는 람다 **밖**이다. 지금 비밀번호가 맞으면 횟수가 지워지고, 새 비밀번호가 규칙에 안 맞아 400이 나도 세지 않는다.
- 돌려줄 값이 없어서 `return null`. `Supplier<T>`에 맞추려는 것이다.

### 5.5 화면: `api/errors.ts`

```ts
export function errorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return '일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.'
  }
  const seconds = retryAfterSeconds(error)
  if (error.code === 'TOO_MANY_REQUESTS' && seconds !== null) {
    return `여러 번 시도해 잠시 막혔습니다. ${waitText(seconds)} 뒤에 다시 시도해 주세요.`
  }
  return error.message
}

/** 기다릴 시간: 1분이 안 되면 초, 그 이상은 분(올림). */
export function waitText(seconds: number): string {
  return seconds < 60 ? `${seconds}초` : `${Math.ceil(seconds / 60)}분`
}
```

- 로그인·가입·마이페이지가 모두 `errorMessage`로 문장을 만들므로 한 곳만 고쳤다. 899초면 "15분 뒤".
- 올림(`Math.ceil`): 899초를 내림하면 "14분 뒤"라 그때 다시 해도 막혀 있다.
- `errors.test.ts`(Vitest)가 문장과 경계(59초, 60초, 61초)를 확인한다.

### 5.6 테스트 `AttemptLimitIntegrationTest`

| 테스트 | 확인하는 것 |
| --- | --- |
| `fiveWrongPasswordsLockLoginForFifteenMinutesEvenForTheRightPassword` | 5번 틀린 뒤 맞는 비밀번호도 429, `retryAfterSeconds` 890~900, 키를 지우면(15분 지난 것처럼) 다시 로그인 |
| `successResetsTheCount` | 4번 틀리고 맞히면 키가 사라지고, 다시 4번 틀려도 막히지 않음 |
| `unknownEmailIsLimitedTheSameWaySoItRevealsNothing` | 가입하지 않은 이메일도 6번째에 429 |
| `concurrentGuessesGetOnlyFiveTries` | 동시에 12번 → 정확히 5번만 401(확인함), 7번 429 |
| `fiveWrongVerificationCodesLockTheEmailEvenForTheRightCode` | 인증 코드 5번 틀린 뒤 맞는 코드도 429 |
| `fiveWrongCurrentPasswordsLockPasswordChange` | 지금 비밀번호 5번 틀린 뒤 맞아도 429, 다른 회원은 상관없음 |

15분을 기다릴 수 없으니 Redis 키를 지워 "시간이 지난 것"을 흉내 냈다.

## 6. 자주 하는 실수와 함정

- **"bcrypt가 느리니 괜찮다"고 생각한다.** bcrypt는 DB가 털린 뒤의 오프라인 공격을 늦춘다. 온라인 공격은 횟수 제한이 막는다.
- **막힌 동안 맞는 값을 받아 준다.** 공격자는 429가 아닌 응답이 나올 때까지 넣어 보면 된다.
- **"몇 번 틀렸나 보고 → 확인"으로 짠다.** 동시 요청이 모두 통과한다. 먼저 `INCR`로 자리를 잡는다.
- **`INCR` 뒤 `EXPIRE`를 빠뜨리거나 실패를 생각하지 않는다.** 수명 없는 키가 남아 계정이 영원히 막힌다.
- **틀린 것이 아닌 실패까지 센다.** 정지 회원·만료 코드·서버 오류로 사용자가 막힌다.
- **가입한 이메일만 센다.** 막히는지로 가입 여부가 드러난다.
- **이메일을 정규화하지 않고 키로 쓴다.** 대소문자만 바꿔 제한을 피한다.
- **새 인증 코드를 받을 때 횟수를 지운다.** 재발송으로 제한을 풀 수 있다.
- **남은 시간을 내림해서 보여 준다.** "14분 뒤"에 해도 막혀 있다.
- **IP별 제한 없이 대상별 제한만 믿는다.** 여러 계정을 하나씩 훑는 공격(비밀번호 하나를 수많은 이메일에)은 막지 못하고, 남이 일부러 내 계정을 잠글 수 있다. 필요해지면 함께 둔다.

## 7. 직접 해 보기

준비: 코드 저장소 루트에서 `./mvnw spring-boot:run`.

### 7.1 로그인 잠금

```bash
E="probe$RANDOM@example.com"
for i in 1 2 3 4 5 6; do
  curl -s -X POST -H "Host: blog.test" -H "X-Requested-With: XMLHttpRequest" -H "Content-Type: application/json" \
       -d "{\"email\":\"$E\",\"password\":\"wrong1234\"}" localhost:8080/api/auth/login; echo
done
# 다섯 번은 LOGIN_FAILED, 여섯 번째는 {"code":"TOO_MANY_REQUESTS",...,"detail":{"retryAfterSeconds":900}}
docker exec blog-redis redis-cli get "attempt:login:$E"   # 6
docker exec blog-redis redis-cli ttl "attempt:login:$E"   # 900 이하로 줄어듦
docker exec blog-redis redis-cli del "attempt:login:$E"   # 풀기
```

스텝 9를 만들며 실제로 돌린 결과가 위와 같았다.

### 7.2 화면

로그인 화면에서 내 계정 비밀번호를 5번 틀리고, 6번째에 맞는 비밀번호를 넣는다. "여러 번 시도해 잠시 막혔습니다. 15분 뒤에 다시 시도해 주세요."가 보인다. `redis-cli del`로 풀고 다시 로그인한다.

### 7.3 "보고 → 확인"이 뚫리는 것 보기 (공부용 브랜치에서)

`AttemptLimiter.attempt`를 "GET으로 횟수를 보고, 5 이상이면 429, 확인 뒤 틀리면 INCR"로 바꾸고 테스트를 돌린다.

```bash
git switch -c study/attempt-race
./mvnw test -Dtest='AttemptLimitIntegrationTest#concurrentGuessesGetOnlyFiveTries'   # 401이 5개보다 많아져 실패할 수 있다(동시성이라 매번은 아님, 몇 번 돌려 본다)
git restore . && git switch -
```

### 7.4 테스트

```bash
./mvnw test -Dtest=AttemptLimitIntegrationTest
cd frontend && npm test
```

## 8. 확인 문제

1. bcrypt를 쓰는데도 로그인 시도 횟수 제한이 필요한 이유는?
<details><summary>답</summary>bcrypt는 DB가 털린 뒤 해시를 푸는 오프라인 공격을 느리게 한다. 서버에 직접 요청하는 온라인 공격은 서버가 대신 계산해 주므로 횟수를 막지 않으면 계속 시도할 수 있고, 느린 bcrypt 때문에 서버 CPU 부담도 커진다.</details>

2. 막힌 동안 맞는 비밀번호도 429로 거절해야 하는 이유는?
<details><summary>답</summary>맞는 값을 받아 주면 공격자는 429가 아닌 응답이 나올 때까지 계속 넣어 보면 되어 제한이 의미가 없어진다.</details>

3. "실패 횟수를 보고 5 이상이면 거절 → 확인 → 틀리면 올리기"가 동시 요청에 뚫리는 이유와 이 프로젝트의 해결은?
<details><summary>답</summary>동시에 온 요청들이 모두 같은 횟수(예: 4)를 보고 통과해 확인을 한다. 확인 전에 INCR로 먼저 하나 올려 서로 다른 번호를 받게 하고, 번호가 5를 넘으면 확인하지 않는다. INCR은 명령 하나라 끼어들 수 없다.</details>

4. 먼저 올린 수를 결과에 따라 어떻게 정리하나?
<details><summary>답</summary>맞으면 키를 지운다. 틀리면 그대로 두고, 다섯 번째로 틀렸으면 수명을 15분으로 다시 잡는다. 틀린 것이 아닌 실패(정지 회원, 만료 코드, 서버 오류)는 DECR로 되돌린다.</details>

5. 가입하지 않은 이메일로 로그인해도 똑같이 세는 이유는?
<details><summary>답</summary>가입한 이메일만 막히면 6번째에 429가 나오는지로 가입 여부를 알아낼 수 있다(계정 열거). 응답 문장·시간과 함께 제한도 같게 한다.</details>

6. 인증 코드를 새로 받아도 틀린 횟수를 지우지 않는 이유는?
<details><summary>답</summary>지우면 1분마다 새 코드를 받아 5번씩 넣어 보는 식으로 제한을 피할 수 있다.</details>

7. `INCR` 뒤 수명이 없으면 붙이는 줄은 무엇을 막나?
<details><summary>답</summary>INCR과 EXPIRE 사이에 서버가 끊기면 수명 없는 키가 남아 그 이메일이 영원히 막힐 수 있다. 다음 시도 때 수명이 없으면 붙여 그런 키가 남지 않게 한다.</details>

8. 대상별 실패 횟수 제한의 약점은?
<details><summary>답</summary>남이 내 이메일로 일부러 5번 틀리면 나도 15분 동안 로그인하지 못한다. 그리고 비밀번호 하나를 수많은 이메일에 넣어 보는 공격은 막지 못한다. IP별 제한 등을 함께 두어 보완한다.</details>

9. 화면에서 남은 시간을 올림해서 보여 주는 이유는?
<details><summary>답</summary>899초를 내림하면 "14분 뒤"가 되는데, 그때 다시 시도해도 아직 막혀 있다. 올림해야 안내한 시간 뒤에 실제로 풀린다.</details>

## 9. 더 읽을거리

- OWASP, "Authentication Cheat Sheet"(Account Lockout, Protect Against Automated Attacks), "Credential Stuffing Prevention Cheat Sheet"
- NIST SP 800-63B, 5.2.2 "Rate Limiting (Throttling)"
- RFC 6585 (429 Too Many Requests), RFC 9110의 `Retry-After`
- Redis 문서, `INCR`(rate limiter 패턴), `EXPIRE`, Lua 스크립트로 여러 명령을 원자적으로
- 토큰 버킷·슬라이딩 윈도 같은 요청 제한 알고리즘, Bucket4j 같은 라이브러리
