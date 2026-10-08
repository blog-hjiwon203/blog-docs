# 비밀번호 저장: 해시, salt, bcrypt

> 관련 스텝: [스텝 2](../step-02.md)(T013 관리자 초기 계정), [스텝 3](../step-03.md)(`SecurityConfig.passwordEncoder`), 스텝 4(가입·로그인)
> 기준 버전: Spring Security 7.1.1(`spring-security-crypto`), MySQL 8.4

## 1. 이 문서로 배우는 것

- 암호화와 해시의 차이, 비밀번호는 왜 해시로 저장하는지
- SHA-256 같은 빠른 해시가 비밀번호에 위험한 이유(레인보우 테이블, GPU 무차별 대입)
- salt와 work factor(cost)가 막는 것
- bcrypt 문자열 `$2a$10$...`을 읽는 법
- bcrypt, scrypt, Argon2 비교
- Spring Security의 `PasswordEncoder`, `BCryptPasswordEncoder`, `DelegatingPasswordEncoder`(`{bcrypt}` 접두사)
- 이 프로젝트의 관리자 초기 계정 해시를 만든 방법, 개발용 비밀번호를 운영 전에 바꿔야 하는 이유
- 비밀번호 규칙과 bcrypt의 72바이트 제한

**먼저 알면 좋은 것**: [Flyway](./03-flyway-migration.md)(V2 데이터 마이그레이션), [Spring Boot 기초](./01-spring-boot-basics.md)(빈).

## 2. 왜 필요한가

회원 테이블에 비밀번호를 그대로 저장했다고 하자.

```
id | email            | password
 1 | a@blog.test      | sunshine1
 2 | b@blog.test      | qwer1234!
```

DB가 한 번이라도 유출되면(백업 파일 분실, SQL 인젝션, 내부자, 로그에 쿼리가 찍힘) 모든 회원의 비밀번호가 그대로 드러난다. 사람들은 **같은 비밀번호를 여러 사이트에 쓰므로**, 피해는 우리 서비스에서 끝나지 않는다.

그렇다고 비밀번호를 "암호화"해서 저장하면?

```
password = AES_암호화(sunshine1, 서버의_키)
```

키가 서버에 있어야 로그인할 때 풀 수 있다. DB와 키가 함께 털리면(같은 서버에 있으니 흔하다) 전부 풀린다. 그리고 애초에 **서버가 원래 비밀번호를 알 필요가 없다.** 로그인은 "입력한 것이 가입 때와 같은가"만 확인하면 된다.

그래서 비밀번호는 **되돌릴 수 없는 형태(해시)**로만 저장한다. spec.md 보안 규칙 "비밀번호는 복원할 수 없는 형태로만 저장한다"가 이것이다.

## 3. 기본 개념

### 3.1 암호화 vs 해시

| | 암호화(encryption) | 해시(hash) |
| --- | --- | --- |
| 방향 | 양방향: 키가 있으면 원래 값으로 되돌림 | 단방향: 되돌릴 수 없음 |
| 키 | 필요 | 필요 없음 |
| 출력 길이 | 입력에 따라 달라짐 | 고정(예: SHA-256은 항상 256비트) |
| 같은 입력 | (방식에 따라) 같은 출력 | 항상 같은 출력 |
| 쓰는 곳 | 나중에 원래 값이 필요한 것(카드 번호, 개인 정보) | 원래 값이 필요 없는 확인(비밀번호, 파일 무결성) |

해시로 로그인하는 방법:

```
가입:   저장값 = hash("sunshine1")              → DB에 저장
로그인: hash(입력값) == 저장값 ?                  → 같으면 성공
```

### 3.2 빠른 해시가 비밀번호에 위험한 이유

SHA-256은 **빠르게 계산하도록** 설계됐다(파일 검증, 블록체인 등). 이것이 비밀번호에서는 약점이다.

**레인보우 테이블(미리 계산한 표)**: 공격자는 흔한 비밀번호 수억 개의 SHA-256 값을 **미리** 계산해 둔다.

```
5e884898da2...  ← "password"
ef92b778bafe... ← "12345678"
...
```

유출된 DB의 해시값을 이 표에서 찾기만 하면 된다. 계산할 필요도 없다.

**GPU 무차별 대입**: 표에 없는 비밀번호도, GPU는 SHA-256을 초당 수십억 번 계산할 수 있다. 8자리 영문 소문자+숫자 조합(36⁸ ≈ 2.8조)은 짧은 시간 안에 다 시도된다.

**같은 비밀번호 = 같은 해시**: 해시값이 같은 회원들은 비밀번호가 같다는 것이 바로 보인다. 하나만 풀면 모두 풀린다.

### 3.3 salt

**salt**는 회원마다 다른 **무작위 값**을 비밀번호에 섞어 해시하는 것이다. salt는 비밀이 아니고 해시와 함께 저장한다.

```
회원 1: salt = "x8Kd..."  저장값 = hash("x8Kd..." + "sunshine1")
회원 2: salt = "Qp2m..."  저장값 = hash("Qp2m..." + "sunshine1")   ← 같은 비밀번호, 다른 해시
```

| salt가 막는 것 | 이유 |
| --- | --- |
| 레인보우 테이블 | salt마다 표를 새로 만들어야 하므로 미리 계산이 무의미 |
| 같은 비밀번호 알아보기 | 같은 비밀번호도 해시가 다름 |
| 한 번에 여러 명 풀기 | 회원마다 따로 공격해야 함 |

salt는 **무차별 대입 자체를 느리게 하지는 못한다.** 한 명을 노리면 그 salt로 계속 시도하면 된다. 그래서 다음 개념이 필요하다.

### 3.4 work factor(cost): 일부러 느리게

비밀번호용 해시는 **일부러 느리게** 만든다. 정상 사용자는 로그인할 때 한 번만 계산하니 0.1초여도 괜찮지만, 공격자는 수십억 번을 계산해야 하므로 그대로 수십억 배 느려진다.

```
SHA-256 한 번      : 아주 빠름 (마이크로초보다 짧음)
bcrypt cost 10 한 번: 약 70ms   (이 프로젝트 개발 PC에서 측정, 아래 5.4)
→ 공격자의 시도 속도가 수만 배 이상 떨어진다
```

**cost**는 그 느린 정도를 정하는 값이고, 컴퓨터가 빨라지면 cost를 올려 따라간다.

### 3.5 비밀번호 전용 해시 함수

| 알고리즘 | 나온 해 | 느리게 만드는 방법 | 특징 |
| --- | --- | --- | --- |
| bcrypt | 1999 | 반복 횟수(2^cost) | 오래 검증됨, 거의 모든 언어 지원. 입력 72바이트 제한 |
| scrypt | 2009 | 반복 + **메모리**를 많이 씀 | GPU·전용 하드웨어 공격에 더 강함 |
| Argon2(id) | 2015 | 시간 + 메모리 + 병렬도를 따로 조절 | 비밀번호 해싱 대회(PHC) 우승. 새로 만들면 권장되는 경우가 많음 |
| PBKDF2 | 2000 | 반복 횟수 | 표준(NIST) 규정 때문에 쓰는 곳이 있음. 메모리를 안 써 GPU에 약한 편 |

이 프로젝트는 **bcrypt**를 쓴다(data-model.md·ERD의 `password_hash` 설명 "bcrypt", research.md R-03). Spring Security가 기본으로 지원하고, 명세가 정한 값이다.

## 4. 동작 원리

### 4.1 bcrypt 문자열 읽기

bcrypt 결과는 salt와 설정까지 **한 문자열**에 담는다. 그래서 salt 컬럼이 따로 필요 없다.

```
$2a$10$1XrAfK4aVBNuC7uNq35kiuugsN.I0RN6Ynqh4Bj6xqJy4B1SUTfB6
 │  │  └──────────┬─────────┘└──────────────┬──────────────┘
 │  │       salt (22자)                해시 결과 (31자)
 │  └ cost = 10  → 2^10 = 1,024번 반복
 └ 버전(2a)
```

- 전체 길이는 항상 **60자**다. 이 프로젝트의 `member.password_hash`는 `VARCHAR(100)`이라 넉넉하다.
- 글자는 bcrypt 전용 base64(`./A-Za-z0-9`)라 `.`과 `/`가 섞여 있다.
- cost를 1 올리면 계산량이 **두 배**가 된다.

### 4.2 가입과 로그인에서 일어나는 일

```
가입: encode("admin1234!")
  1. 무작위 salt 16바이트 생성
  2. bcrypt(cost=10, salt, "admin1234!") 계산
  3. "$2a$10$" + salt + 결과 → DB에 저장

로그인: matches("입력값", 저장값)
  1. 저장값에서 버전·cost·salt를 꺼낸다
  2. 같은 cost·salt로 입력값을 다시 계산
  3. 결과가 저장값과 같은가 → true / false
```

그래서 **같은 비밀번호를 두 번 encode하면 결과가 다르다**(salt가 다르니까). 비교는 반드시 `matches()`로 하고, `encode(입력) == 저장값`처럼 하면 항상 실패한다.

### 4.3 72바이트 제한

bcrypt 알고리즘은 입력의 **앞 72바이트만** 쓴다. 예전 구현들은 넘는 부분을 조용히 잘랐다. 그러면 "앞 72바이트만 같은 다른 비밀번호"도 로그인되는 문제가 생긴다.

Spring Security 7.1.1의 `BCryptPasswordEncoder`는 72바이트를 넘는 입력을 **거부**한다(아래 5.4에서 확인).

```
IllegalArgumentException: password cannot be more than 72 bytes
```

바이트는 글자 수가 아니다. UTF-8에서 영문·숫자는 1바이트, **한글은 3바이트**다. 한글 비밀번호는 24자면 72바이트다.

## 5. 이 프로젝트에서는

### 5.1 비밀번호 인코더 빈: `global/config/SecurityConfig.java`

```java
/** 비밀번호 해시 (bcrypt). 관리자 초기 계정(V2)도 같은 방식이다. */
@Bean
PasswordEncoder passwordEncoder() {
    return new BCryptPasswordEncoder();          // 기본 cost 10, 버전 2a
}
```

- `PasswordEncoder`는 Spring Security의 인터페이스다. 핵심 메서드는 두 개: `encode(raw)`(해시 만들기), `matches(raw, encoded)`(확인).
- **인터페이스 타입**으로 빈을 등록하면, 서비스는 `PasswordEncoder`만 알고 bcrypt인지 Argon2인지 모른다. 알고리즘을 바꿀 때 이 메서드만 고치면 된다.
- 스텝 4의 가입 서비스는 `passwordEncoder.encode(request.password())`로 저장하고, 로그인 서비스는 `passwordEncoder.matches(request.password(), member.getPasswordHash())`로 확인한다.

### 5.2 관리자 초기 계정: `src/main/resources/db/migration/V2__admin_account.sql`

```sql
-- 서비스 관리자 초기 계정 (ADMIN-01). 관리자는 이 데이터로만 정한다.
-- 개발용 값이다: admin@blog.test / admin1234! (bcrypt). 운영에 올리기 전에 비밀번호를 바꾼다.
INSERT INTO member (email, password_hash, nickname, role, status)
VALUES ('admin@blog.test', '$2a$10$1XrAfK4aVBNuC7uNq35kiuugsN.I0RN6Ynqh4Bj6xqJy4B1SUTfB6', 'admin', 'ADMIN', 'ACTIVE');
```

- **관리자를 데이터로만 정하는 이유**(ADMIN-01): 가입 API로 `role=ADMIN`을 만들 길이 있으면 그 길이 공격 대상이 된다. 가입은 항상 USER(`Member.ofEmail`)이고, 관리자는 마이그레이션으로만 생긴다.
- **해시는 SQL 안에서 만들 수 없다.** MySQL에는 bcrypt 함수가 없다. 그래서 스텝 2에서 프로젝트가 이미 쓰는 라이브러리(`spring-security-crypto` 7.1.1 jar)로 작은 자바 프로그램을 돌려 해시를 만들고 그 문자열을 SQL에 붙였다.

  ```java
  BCryptPasswordEncoder e = new BCryptPasswordEncoder();
  String h = e.encode("admin1234!");
  System.out.println(h + " " + e.matches("admin1234!", h));   // 해시와 확인 결과(true)를 함께 출력
  ```

  같은 라이브러리·같은 설정으로 만들었으니, 앱의 `matches()`가 그대로 확인할 수 있다. 테스트 `member/domain/AdminAccountMigrationTest`가 `new BCryptPasswordEncoder().matches("admin1234!", admin.getPasswordHash())`로 이것을 확인한다.

- **운영 전에 바꿔야 하는 이유**:
  - 이 파일은 git 저장소에 있다. 해시만 있어도 원래 비밀번호가 `admin1234!`라는 것이 **주석에 적혀 있고**, 주석이 없더라도 흔한 비밀번호는 해시를 대입 공격으로 금방 찾는다.
  - 관리자 계정은 모든 회원을 정지하고 글을 숨길 수 있다. 가장 먼저 노려진다.
  - Flyway는 이미 적용된 파일을 고칠 수 없으므로(체크섬, [Flyway](./03-flyway-migration.md)), 운영용 비밀번호는 **새 마이그레이션**(예: 운영에서만 실행되는 위치의 `V{n}__...`)이나 운영 DB에서 직접 UPDATE하는 절차로 바꾼다. 어떤 방법으로 할지는 운영 배포 때 정한다(아직 미정).

### 5.3 `{bcrypt}` 접두사와 `DelegatingPasswordEncoder`

Spring Security에는 여러 알고리즘을 섞어 쓸 수 있는 `DelegatingPasswordEncoder`가 있다. `PasswordEncoderFactories.createDelegatingPasswordEncoder()`로 만들며, 저장값 앞에 **알고리즘 이름**을 붙인다.

```
{bcrypt}$2a$10$...        ← bcrypt로 확인
{argon2}$argon2id$v=19... ← Argon2로 확인
```

- 장점: 알고리즘을 바꿔도 예전 회원의 해시를 그대로 확인할 수 있다. 새로 가입하거나 로그인할 때 새 알고리즘으로 다시 저장해 서서히 옮길 수 있다.
- 이 프로젝트는 **접두사 없는 bcrypt**를 쓴다. 인코더도 `BCryptPasswordEncoder`, V2의 해시도 `$2a$...`로 시작한다. 둘이 짝이 맞다.
- 섞으면 안 된다. 접두사 없는 해시를 위임 인코더로 확인하면 예외가 난다(5.4에서 확인).

  ```
  IllegalArgumentException: Given that there is no default password encoder configured, each password
  must have a password encoding prefix. ...
  ```

  나중에 위임 인코더로 바꾸려면 기존 해시 앞에 `{bcrypt}`를 붙이는 마이그레이션을 함께 해야 한다.

### 5.4 직접 확인한 사실 (spring-security-crypto 7.1.1, 이 문서 작성 때 실행)

| 실험 | 결과 |
| --- | --- |
| `encode("admin1234!")` 두 번 | 결과가 서로 다름, 둘 다 60자 |
| 영문 73자 `encode` | `IllegalArgumentException: password cannot be more than 72 bytes` |
| 한글 25자(75바이트) `encode` | 같은 예외 |
| 위임 인코더 `encode` | `{bcrypt}$2a$10...`로 시작 |
| 위임 인코더로 접두사 없는 해시 `matches` | `IllegalArgumentException`(접두사 필요) |
| V2 해시를 `BCryptPasswordEncoder.matches("admin1234!", ...)` | `true` |
| cost 10 / cost 12 한 번 계산 | 약 68ms / 약 275ms (개발 PC, 한 번 측정이라 참고용) |

### 5.5 비밀번호 규칙 (스텝 4에서 만들 것)

tasks.md T018: "비밀번호 8자+영문+숫자, bcrypt". 해시와 규칙은 맡은 일이 다르다.

| 장치 | 막는 것 |
| --- | --- |
| 규칙(최소 길이, 영문+숫자) | 너무 쉬운 비밀번호. 해시가 아무리 느려도 `1234`는 금방 맞춘다 |
| bcrypt(salt, cost) | DB가 털렸을 때 원래 비밀번호를 알아내기 |
| 최대 길이 | bcrypt 72바이트 제한에 걸려 500이 나는 것. 가입 단계에서 400으로 미리 막는다 |

스텝 4에서 `@Size(max = ...)`나 바이트 길이 검사를 넣을 때, 한글이 3바이트라는 점을 함께 고려한다. 정확한 최대 길이는 명세에 없어 그때 정한다.

로그인 실패 문구를 하나로 통일하는 것(T019, `LOGIN_FAILED` "이메일 또는 비밀번호가 맞지 않습니다.")도 같은 흐름의 방어다. "없는 이메일"과 "비밀번호 틀림"을 구분해 알려 주면, 공격자가 어떤 이메일이 가입돼 있는지 알아낸다.

## 6. 자주 하는 실수와 함정

| 실수 | 결과 |
| --- | --- |
| `MD5`, `SHA-256`으로 비밀번호 해시 | 빠른 해시라 GPU 대입에 금방 풀림 |
| salt 없이 해시 | 레인보우 테이블, 같은 비밀번호 노출 |
| 모든 회원에 같은 salt(고정값) | salt가 없는 것과 거의 같음 |
| `encode(입력).equals(저장값)`으로 비교 | 매번 salt가 달라 항상 실패. `matches()`를 써야 함 |
| 비밀번호를 로그에 남김(요청 본문 로깅 등) | 해시가 소용없어짐 |
| 해시를 응답 JSON에 포함(엔티티를 그대로 반환) | 대입 공격 재료를 넘겨줌 → 응답 DTO에서 뺀다 |
| 개발용 관리자 비밀번호로 운영 배포 | 저장소를 본 누구나 관리자 로그인 |
| 72바이트 넘는 입력을 검사 없이 encode | 예외 → 500. 가입 단계에서 400으로 막아야 함 |
| cost를 너무 높게(예: 16) | 로그인 한 번에 수 초, 로그인 폭주 시 서버 CPU 고갈(이것 자체가 서비스 거부 공격 수단) |
| 접두사 있는/없는 해시를 섞음 | 위임 인코더에서 예외 |

## 7. 직접 해 보기

1. **같은 비밀번호, 다른 해시**
   - 테스트 하나를 임시로 만든다(`src/test/java/.../PasswordPlayTest.java`).
     ```java
     @Test
     void play() {
         BCryptPasswordEncoder encoder = new BCryptPasswordEncoder();
         String a = encoder.encode("admin1234!");
         String b = encoder.encode("admin1234!");
         System.out.println(a + "\n" + b);
         assertThat(a).isNotEqualTo(b);
         assertThat(encoder.matches("admin1234!", a)).isTrue();
         assertThat(encoder.matches("admin1234!", b)).isTrue();
     }
     ```
   - `./mvnw test -Dtest=PasswordPlayTest` — 출력된 두 문자열에서 4.1처럼 cost와 salt 부분을 찾아본다.

2. **cost에 따른 시간**
   - 같은 테스트에서 `new BCryptPasswordEncoder(4)`, `(10)`, `(12)`, `(14)`로 `encode`에 걸린 시간을 `System.nanoTime()`으로 재 본다. cost가 1 오를 때 시간이 대략 두 배가 되는지 본다.

3. **72바이트 제한**
   - `encoder.encode("가".repeat(24))`(72바이트)와 `encoder.encode("가".repeat(25))`(75바이트)를 각각 실행해 본다.

4. **DB의 해시 보기**
   ```bash
   docker exec blog-mysql mysql -ublog -pblog blog -e "SELECT email, password_hash, LENGTH(password_hash) FROM member"
   ```
   관리자 행의 해시가 60자인지 본다.

5. **관리자 계정 테스트 따라가기**
   - `./mvnw test -Dtest=AdminAccountMigrationTest`
   - 테스트의 `"admin1234!"`를 다른 문자열로 바꾸면 실패하는 것을 보고 되돌린다.

실습용 테스트 파일은 끝나면 지운다.

## 8. 확인 문제

1. 비밀번호를 암호화(AES)가 아니라 해시로 저장하는 이유는?
   <details><summary>답</summary>서버는 원래 비밀번호를 알 필요가 없고(같은지 확인만 하면 됨), 암호화는 키가 함께 털리면 전부 복호화된다. 해시는 되돌릴 수 없다.</details>

2. salt가 막는 것과 막지 못하는 것을 하나씩 말하라.
   <details><summary>답</summary>막는 것: 레인보우 테이블(미리 계산한 표), 같은 비밀번호를 쓰는 회원 알아보기. 막지 못하는 것: 한 회원을 노린 무차별 대입 자체의 속도. 그것은 work factor(cost)가 막는다.</details>

3. `$2a$10$1XrAfK4aVBNuC7uNq35kiu...`에서 10은 무엇이고, 12로 바꾸면 계산량은 몇 배가 되나?
   <details><summary>답</summary>cost(work factor). 반복 횟수가 2^cost라 10→12면 2^2 = 4배.</details>

4. 같은 비밀번호를 `encode`하면 매번 다른 값이 나오는데, 로그인은 어떻게 확인하나?
   <details><summary>답</summary>matches()가 저장값에서 cost와 salt를 꺼내, 입력값을 같은 cost·salt로 다시 계산해 비교한다.</details>

5. 이 프로젝트의 V2 해시를 `PasswordEncoderFactories.createDelegatingPasswordEncoder()`로 확인하면 어떻게 되나? 왜인가?
   <details><summary>답</summary>IllegalArgumentException. 위임 인코더는 저장값 앞의 {알고리즘} 접두사로 어떤 인코더를 쓸지 정하는데, V2 해시에는 접두사가 없다(기본 인코더도 설정돼 있지 않음).</details>

6. 한글로만 된 비밀번호는 몇 글자부터 bcrypt로 해시할 수 없나(이 프로젝트의 Spring Security 기준)?
   <details><summary>답</summary>UTF-8에서 한글 한 글자는 3바이트라 24자 = 72바이트까지 되고, 25자(75바이트)부터 "password cannot be more than 72 bytes" 예외가 난다.</details>

7. `V2__admin_account.sql`의 비밀번호를 운영에서 그대로 쓰면 안 되는 이유는? 바꿀 때 V2 파일을 고치면 안 되는 이유는?
   <details><summary>답</summary>저장소를 볼 수 있는 누구나 비밀번호(주석에 있고, 흔한 비밀번호라 해시로도 금방 찾음)를 알 수 있고, 관리자는 권한이 가장 크다. V2는 이미 적용된 마이그레이션이라 고치면 Flyway 체크섬이 달라져 앱이 뜨지 않는다. 새 마이그레이션이나 운영 절차로 바꾼다.</details>

8. 로그인 실패 문구를 "없는 이메일"과 "비밀번호 틀림"으로 나누지 않는 이유는?
   <details><summary>답</summary>나누면 공격자가 어떤 이메일이 가입돼 있는지 알아낼 수 있다(계정 열거). 하나의 문구(LOGIN_FAILED)로 통일한다.</details>

## 9. 더 읽을거리

- Spring Security Reference, "Password Storage" — `PasswordEncoder`, `DelegatingPasswordEncoder`, 알고리즘별 인코더: https://docs.spring.io/spring-security/reference/features/authentication/password-storage.html
- OWASP Password Storage Cheat Sheet — 알고리즘 선택과 권장 설정: https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
- OWASP Authentication Cheat Sheet — 실패 문구 통일, 비밀번호 규칙: https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html
- Password Hashing Competition(Argon2): https://www.password-hashing.net/
- 이 저장소: [data-model.md](../../data-model.md) `member.password_hash`, [research.md R-03](../../research.md)
