# JWT와 로그인 토큰 설계

> 관련 스텝: [스텝 3](../step-03.md) · 관련 결정: research.md R-03, AUTH-02, AUTH-03, ADMIN-02

## 1. 이 문서로 배우는 것

- JWT가 무엇이고 `헤더.내용.서명` 세 부분이 각각 무엇인지
- 표준 클레임(`sub`, `exp`, `iat`, `jti`)과 이 프로젝트가 더한 클레임(`typ`, `role`, `rem`)
- 서명이 막는 것과 **막지 못하는 것**(내용은 누구나 읽는다)
- HS256(대칭 키)과 RS256(비대칭 키)의 차이, 비밀 키 길이
- Access 토큰과 Refresh 토큰을 나누는 이유
- JWT의 가장 큰 약점인 "무효화"를 어떻게 푸는지(짧은 수명, Redis 허용 목록·차단 목록)
- Refresh 토큰 교체(rotation)와, 이 프로젝트가 대신 **Redis TTL 연장**을 고른 이유
- 무활동 30분 로그아웃 설계
- `JwtTokenProvider` 코드 한 줄씩

**먼저 알면 좋은 것**: [10-http-cookies](./10-http-cookies.md)(토큰을 어떻게 실어 나르는지), Base64가 바이트를 글자로 바꾸는 방식이라는 것, 해시 함수(같은 입력 → 같은 출력, 거꾸로 못 돌림)의 기본 개념.

---

## 2. 왜 필요한가

로그인한 사용자를 요청마다 알아보려면 "증표"가 필요하다([10-http-cookies](./10-http-cookies.md) 2절). 가장 단순한 증표는 **무작위 문자열(세션 ID)**이다. 서버가 `abc123 → 회원 7번`을 저장소에 적어 두고, 요청이 올 때마다 저장소를 찾아본다.

이 방식의 불편한 점:
- 요청마다 저장소 조회가 필요하다.
- 서버를 여러 대로 늘리면 모든 서버가 같은 저장소를 봐야 한다.

그래서 이런 생각이 나왔다. **"증표 안에 '회원 7번, 30분 뒤 만료'를 직접 적고, 서버만 만들 수 있는 도장을 찍자."** 그러면 서버는 저장소를 보지 않고 **도장(서명)만 확인**하면 된다. 이것이 JWT다.

대가도 있다. 저장소를 보지 않으니, 이미 나눠 준 증표를 **중간에 취소하기 어렵다**. 이 문서의 절반은 이 대가를 어떻게 치르는지에 대한 이야기다.

---

## 3. 기본 개념

### 3.1 JWT의 모양

JWT(JSON Web Token, RFC 7519)는 점(`.`) 두 개로 나뉜 세 부분이다.

```
eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiI3IiwiZXhwIjoxNzYwMDAwMDAwfQ.k3vZ...서명...
└──────── 헤더 ───────┘ └──────────────── 내용(payload) ──────────┘ └─ 서명 ─┘
```

각 부분은 JSON을 **Base64URL**로 인코딩한 것이다. Base64URL은 Base64에서 URL에 문제가 되는 `+`, `/`를 `-`, `_`로 바꾸고 끝의 `=`를 뺀 것이다(RFC 4648 5절). 그래서 쿠키나 URL에 그대로 넣을 수 있다.

디코딩하면:

```json
// 헤더: 어떤 방식으로 서명했나
{ "alg": "HS256" }

// 내용: 클레임(claim)들
{
  "jti": "5b1f...uuid",          // 토큰 고유 번호
  "sub": "7",                    // 누구의 토큰인가 (회원 id)
  "iat": 1760000000,             // 발급 시각 (초 단위 유닉스 시간)
  "exp": 1760001800,             // 만료 시각
  "typ": "ACCESS",               // (이 프로젝트) Access인지 Refresh인지
  "role": "USER"                 // (이 프로젝트) 역할
}
```

**인코딩은 암호화가 아니다.** Base64URL은 누구나 되돌릴 수 있다. 쿠키에서 토큰을 꺼내 jwt.io에 붙이면 내용이 그대로 보인다.

### 3.2 클레임

RFC 7519이 정한 등록 클레임(registered claims):

| 클레임 | 뜻 | 이 프로젝트 |
| --- | --- | --- |
| `iss` | 발급자 | 안 씀(발급자와 사용자가 같은 서버) |
| `sub` | 주체(누구의 토큰인가) | 회원 id |
| `aud` | 받는 쪽 | 안 씀 |
| `exp` | 만료 시각 | Access 30분, Refresh 14일 |
| `nbf` | 이 시각 전에는 무효 | 안 씀 |
| `iat` | 발급 시각 | 씀 |
| `jti` | 토큰 고유 ID | UUID. Redis 키로 씀 |

나머지는 서비스가 정하는 비공개 클레임(private claims)이다. 이 프로젝트는 세 개를 더했다.

| 클레임 | 값 | 왜 |
| --- | --- | --- |
| `typ` | `ACCESS` / `REFRESH` | Refresh 토큰을 Access 자리에 넣어 쓰는 것을 막으려고 |
| `role` | `USER` / `ADMIN` | Access 토큰에만 |
| `rem` | `true` / `false` | Refresh 토큰에만. 로그인 유지를 골랐나(무활동 만료 적용 여부) |

주의: JOSE **헤더**에도 `typ`라는 칸이 있다(토큰 종류, 보통 `JWT`). 이 프로젝트의 `typ`는 헤더가 아니라 **내용(payload)**에 넣은 비공개 클레임이라 서로 다른 것이다.

### 3.3 서명

서명은 "헤더.내용" 문자열에 비밀 정보로 도장을 찍은 값이다.

```
서명 = HMAC-SHA256( 비밀 키, base64url(헤더) + "." + base64url(내용) )
```

서버가 토큰을 받으면 같은 계산을 다시 해서 토큰의 서명과 비교한다. 내용이 한 글자라도 바뀌었으면 서명이 맞지 않는다.

**서명이 막는 것과 못 막는 것**

| 막는 것 | 못 막는 것 |
| --- | --- |
| 내용 바꾸기(`sub`를 7 → 1로, `role`을 USER → ADMIN으로) | 내용 읽기. 누구나 Base64URL을 풀면 본다 |
| 서버 몰래 토큰 만들기 | 훔친 토큰을 그대로 쓰기(토큰을 가진 사람 = 주인으로 취급) |
| | 이미 준 토큰을 만료 전에 취소하기 |

그래서:
- **JWT에 비밀(비밀번호, 개인정보)을 넣지 않는다.**
- 훔치기 어렵게 보관한다(HttpOnly 쿠키, HTTPS).
- 수명을 짧게 한다.

### 3.4 HS256과 RS256

| | HS256 (HMAC + SHA-256) | RS256 (RSA 서명 + SHA-256) |
| --- | --- | --- |
| 키 | 비밀 키 하나(서명·검증 같은 키) | 개인 키로 서명, 공개 키로 검증 |
| 맞는 경우 | 발급하는 서버 = 검증하는 서버 | 발급 서버와 검증 서버가 다름(예: 인증 서버 따로, 여러 서비스) |
| 위험 | 검증하는 쪽도 위조할 수 있음(같은 키) | 공개 키는 퍼뜨려도 안전 |
| 속도 | 빠름 | 상대적으로 느림 |

이 프로젝트는 서버 하나가 발급과 검증을 다 하므로 HS256이면 충분하다.

**비밀 키 길이**: RFC 7518(JWA) 3.2절은 HS256에 **해시 출력 크기(256비트 = 32바이트) 이상**의 키를 쓰라고 한다. 짧은 키는 무차별 대입으로 찾아낼 수 있고, 찾으면 누구든 관리자 토큰을 만들 수 있다. 그래서 코드가 32바이트 미만이면 앱을 띄우지 않는다(5.1).

### 3.5 Access 토큰과 Refresh 토큰

토큰 수명을 정할 때 두 요구가 부딪힌다.
- **짧아야 한다**: 훔쳐 간 토큰이 오래 쓰이면 안 된다. 취소도 어렵다.
- **길어야 한다**: 30분마다 다시 로그인하라고 하면 아무도 안 쓴다.

해법은 토큰을 둘로 나누는 것이다.

| | Access 토큰 | Refresh 토큰 |
| --- | --- | --- |
| 하는 일 | 요청마다 "누구인가" 증명 | Access가 만료되면 새 Access 받기 |
| 수명 | 짧게(30분) | 길게(로그인 유지 14일) |
| 검사 | 서명·만료 + 차단 목록 | 서명·만료 + **Redis에 살아 있는지** |
| 얼마나 자주 쓰나 | 매 요청 | 가끔(30분에 한 번꼴) |

Refresh 토큰은 가끔만 쓰이므로 쓸 때마다 Redis를 확인해도 부담이 적다. 그래서 Refresh 쪽에 "취소 가능" 장치를 몰아 둔다.

### 3.6 무효화 문제와 해결책

JWT는 서명만 확인하면 유효하므로, "로그아웃했다"는 사실을 토큰은 모른다. 해결책은 서버에 **조금의 상태**를 두는 것이다.

| 방법 | 내용 | 이 프로젝트 |
| --- | --- | --- |
| 짧은 수명 | 최악의 경우에도 피해 기간이 짧다 | Access 30분 |
| 허용 목록(allowlist) | 살아 있는 토큰만 저장. 없으면 거절 | Refresh 토큰: `auth:refresh:{jti}` |
| 차단 목록(denylist) | 취소된 토큰을 저장. 있으면 거절 | Access 토큰: `auth:blocked-access:{jti}`(로그아웃 시) |
| 회원 상태 확인 | 토큰과 상관없이 DB에서 정지·탈퇴 확인 | 요청마다(아래 3.9) |

차단 목록 항목은 그 토큰의 **만료 시각까지만** 있으면 된다. 만료되면 어차피 서명 검사에서 떨어지므로 Redis TTL을 남은 수명으로 준다.

### 3.7 Refresh 토큰 교체(rotation)와 이 프로젝트의 선택

**교체(rotation)**: Refresh 토큰을 쓸 때마다 새 Refresh 토큰을 주고 옛 것은 무효로 한다. 누군가 옛 Refresh 토큰을 다시 쓰면 "도난"으로 보고 그 사용자의 토큰을 전부 끊는다(재사용 감지). OAuth 2.0 보안 모범 사례(RFC 9700)가 공개 클라이언트에 권하는 방법이다.

교체의 함정은 **동시 요청**이다.

```
Access가 막 만료된 상태에서 화면이 API 두 개를 동시에 부름
  요청 A: refresh R1로 새 Access + 새 Refresh R2 발급, R1 무효화
  요청 B: refresh R1로... 이미 무효! → 재사용으로 오인 → 로그아웃
```

이를 피하려면 "옛 토큰을 몇 초간 봐 주기" 같은 장치가 더 필요하다.

이 프로젝트는 교체 대신 **같은 Refresh 토큰을 쓰고, Redis의 TTL만 늘리는** 방식을 골랐다.
- 동시 요청이 와도 같은 Redis 키를 확인하므로 서로 방해하지 않는다.
- 로그아웃하면 Redis 키를 지워 즉시 무효.
- 도난 감지는 교체 방식보다 약하다. 대신 HttpOnly·SameSite 쿠키와 XSS 방어로 훔치기 어렵게 한다.

### 3.8 무활동 30분 로그아웃 (AUTH-03)

지원이 정한 규칙: 로그인 유지를 고르지 않으면 **30분 동안 아무 요청이 없을 때** 로그아웃.

```
로그인(유지 안 함)  : Redis SET auth:refresh:{jti} = 회원id, TTL 30분
로그인한 요청마다   : Redis EXPIRE auth:refresh:{jti} 30분   ← 다시 30분
30분 동안 요청 없음 : Redis가 키를 지움
그 뒤 요청          : Access는 이미 만료(30분), Refresh는 Redis에 없음 → 비회원
```

왜 늦어도 30분 뒤에 끝나는가: Access 토큰은 마지막 요청 **이전**에 발급됐고 수명이 30분이다. Refresh 키는 마지막 요청 **때** 30분으로 늘어났다. 그래서 마지막 요청에서 30분이 지나면 둘 다 끝나 있다.

로그인 유지를 고르면 Redis TTL이 토큰 만료(14일)까지이고 요청마다 늘리지 않는다.

### 3.9 토큰이 유효해도 DB를 한 번 본다

토큰 안의 정보는 **발급 시점**의 사실이다. 그 사이에 회원이 정지되거나 탈퇴했을 수 있다. 명세(ADMIN-02)는 "이미 로그인한 정지 회원은 다음 요청부터 막는다"이다. 그래서 필터가 요청마다 `memberRepository.findById`로 상태를 확인한다. 기본 키 조회 한 번이라 빠르다.

같은 이유로 역할도 **토큰의 `role`이 아니라 DB의 `role`**을 쓴다(5.2). 토큰의 `role`은 지금은 참고용이다.

### 3.10 라이브러리: 왜 Nimbus인가

자바에서 JWT를 다루는 대표 라이브러리는 jjwt와 Nimbus JOSE+JWT다.

- Spring Boot 4는 JSON 처리에 **Jackson 3**(패키지 `tools.jackson`)을 쓴다.
- jjwt의 JSON 모듈(`jjwt-jackson`)은 **Jackson 2**(패키지 `com.fasterxml.jackson.databind`)에 의존한다. 넣으면 Jackson 두 버전이 함께 들어온다.
- Nimbus는 자체 JSON 처리를 쓰고, Spring Security가 `spring-security-oauth2-jose` 모듈로 감싸서 **버전을 관리**해 준다. `NimbusJwtEncoder`/`NimbusJwtDecoder`가 바로 쓸 수 있는 형태로 있다.

---

## 4. 동작 원리

### 4.1 발급 (로그인 성공 때)

```
AuthCookieManager.login(response, member, rememberMe)
  ① JwtTokenProvider.createRefreshToken(id, rememberMe)
       claims = {jti: 새 UUID, sub: id, iat: 지금, exp: 지금+14일, typ: REFRESH, rem: rememberMe}
       header = {alg: HS256}
       서명 → "xxxxx.yyyyy.zzzzz"
  ② TokenStore.saveRefresh(토큰, id, rememberMe ? null : 30분)
       Redis SET auth:refresh:{jti} = id, TTL = min(14일 남은 시간, 30분 또는 없음)
  ③ Set-Cookie: refresh_token=... (유지면 Max-Age 14일, 아니면 세션 쿠키)
  ④ issueAccess → createAccessToken(id, role) → Set-Cookie: access_token=... (세션 쿠키)
```

### 4.2 검증 (요청마다, `JwtAuthenticationFilter`)

```
쿠키 둘 다 없음 ─────────────────────────────────→ 비회원으로 통과
access_token 파싱
  ├ 서명 OK, exp OK, typ=ACCESS, 차단 목록에 없음 → memberId (A)
  └ 아니면 → refresh_token 파싱
              ├ 서명 OK, exp OK, typ=REFRESH, Redis에 살아 있음 → memberId (R)
              └ 아니면 → 없음
DB에서 회원 조회
  ├ 없음/탈퇴    → 쿠키 지우고 비회원으로 통과
  ├ 정지 + /api/ → 쿠키 지우고 403 MEMBER_SUSPENDED (끝)
  ├ 정지 + 화면  → 비회원으로 통과
  └ 정상         → (R 경로였으면) 새 access_token Set-Cookie
                   (rem=false면) Redis EXPIRE 30분
                   SecurityContext에 LoginMember 저장 → 통과
```

### 4.3 Nimbus 디코더가 확인하는 것

`NimbusJwtDecoder.decode(token)`은 다음을 확인하고, 하나라도 틀리면 `JwtException`을 던진다.
1. 세 부분 형식, Base64URL, JSON이 올바른가.
2. 헤더의 `alg`가 설정한 알고리즘(HS256)인가.
3. 서명이 맞는가.
4. Spring Security 7의 기본 검증기(`JwtValidators.createDefault()`):
   - 헤더 `typ`가 `JWT`이거나 비어 있는가(`JwtTypeValidator`)
   - `exp`가 지나지 않았고 `nbf`가 오지 않았는가. **60초 오차**를 봐준다(`JwtTimestampValidator`, 서버 시계가 조금씩 다를 수 있어서)
   - 인증서 바인딩 클레임이 있으면 맞는가(이 프로젝트 토큰에는 없음)

60초 오차 때문에 "만료 시각이 정확히 지난 순간"에는 아직 통과할 수 있다는 점을 기억한다.

### 4.4 로그아웃

```
AuthCookieManager.logout(request, response)
  access_token 파싱 성공 → TokenStore.blockAccess(jti, exp) : Redis SET auth:blocked-access:{jti}, TTL=남은 수명
  refresh_token 파싱 성공 → TokenStore.deleteRefresh(jti)    : Redis DEL auth:refresh:{jti}
  clear(response) → 두 쿠키 Max-Age=0
```

이 브라우저 말고 다른 곳(예: 훔쳐 간 사람)에 같은 토큰이 있어도, Access는 차단 목록에 걸리고 Refresh는 Redis에 없어서 더는 못 쓴다.

---

## 5. 이 프로젝트에서는

### 5.1 `JwtTokenProvider`

경로: `src/main/java/com/nhnacademy/blog/global/auth/JwtTokenProvider.java`

```java
private static final String CLAIM_TYPE = "typ";
private static final String CLAIM_ROLE = "role";
private static final String CLAIM_REMEMBER_ME = "rem";
private static final int MIN_SECRET_BYTES = 32;            // HS256 = 256비트 이상 (RFC 7518)

public JwtTokenProvider(AuthProperties properties, Clock clock) {
    byte[] secret = properties.jwtSecret().getBytes(StandardCharsets.UTF_8);
    if (secret.length < MIN_SECRET_BYTES) {                 // 짧은 키면 앱이 아예 뜨지 않게
        throw new IllegalStateException("app.auth.jwt-secret은 32바이트 이상이어야 합니다.");
    }
    SecretKey key = new SecretKeySpec(secret, "HmacSHA256");
    this.properties = properties;
    this.clock = clock;                                      // 테스트에서 시각을 바꿀 수 있게 주입
    this.encoder = NimbusJwtEncoder.withSecretKey(key).algorithm(MacAlgorithm.HS256).build();
    this.decoder = NimbusJwtDecoder.withSecretKey(key).macAlgorithm(MacAlgorithm.HS256).build();
}
```

- 키는 설정값 `app.auth.jwt-secret`. 개발은 `application-dev.yml`의 고정 문자열, 운영은 `application-prod.yml`의 `${JWT_SECRET}`(환경 변수). 운영 키를 저장소에 남기지 않는다.
- 생성자에서 키를 검사하므로 잘못된 설정은 **앱 시작 때** 바로 드러난다(요청을 받고 나서 터지는 것보다 낫다).

```java
public IssuedToken createAccessToken(Long memberId, Role role) {
    Instant now = clock.instant();
    JwtClaimsSet.Builder claims = baseClaims(memberId, now, now.plus(properties.accessTokenTtl()))
            .claim(CLAIM_TYPE, TokenType.ACCESS.name())
            .claim(CLAIM_ROLE, role.name());
    return encode(claims.build());
}

private JwtClaimsSet.Builder baseClaims(Long memberId, Instant issuedAt, Instant expiresAt) {
    return JwtClaimsSet.builder()
            .id(UUID.randomUUID().toString())     // jti: Redis 키로 쓸 고유 번호
            .subject(String.valueOf(memberId))    // sub: 표준상 문자열
            .issuedAt(issuedAt)
            .expiresAt(expiresAt);
}

private IssuedToken encode(JwtClaimsSet claims) {
    JwsHeader header = JwsHeader.with(MacAlgorithm.HS256).build();
    String value = encoder.encode(JwtEncoderParameters.from(header, claims)).getTokenValue();
    return new IssuedToken(value, claims.getId(), claims.getExpiresAt());   // 값 + jti + 만료 시각
}
```

`IssuedToken`에 jti와 만료 시각을 같이 돌려주는 이유: 호출하는 쪽(`TokenStore.saveRefresh`)이 토큰을 다시 파싱하지 않고 바로 Redis 키와 TTL을 정할 수 있게.

```java
/** 서명·만료·형식이 맞으면 내용을, 아니면 빈 값을 준다. */
public Optional<TokenClaims> parse(String token, TokenType expectedType) {
    if (token == null || token.isBlank()) {
        return Optional.empty();
    }
    try {
        Jwt jwt = decoder.decode(token);                                   // 4.3의 검사 전부
        TokenType type = TokenType.valueOf(jwt.getClaimAsString(CLAIM_TYPE));
        if (type != expectedType) {                                        // Refresh를 Access 자리에 못 씀
            return Optional.empty();
        }
        Role role = type == TokenType.ACCESS ? Role.valueOf(jwt.getClaimAsString(CLAIM_ROLE)) : null;
        boolean rememberMe = Boolean.TRUE.equals(jwt.getClaimAsBoolean(CLAIM_REMEMBER_ME));
        return Optional.of(new TokenClaims(type, Long.valueOf(jwt.getSubject()), role, jwt.getId(),
                jwt.getExpiresAt(), rememberMe));
    } catch (JwtException | IllegalArgumentException | NullPointerException e) {
        return Optional.empty();                                           // 어떤 이유든 "유효하지 않음"
    }
}
```

- 실패 이유(만료, 위조, 형식 오류)를 구분하지 않고 빈 값을 준다. 필터 입장에서는 모두 "이 토큰으로는 로그인 안 됨"이고, 이유를 응답에 드러낼 필요가 없다.
- `IllegalArgumentException`은 `TokenType.valueOf`/`Role.valueOf`에 모르는 값이 왔을 때, `NullPointerException`은 클레임이 없을 때다. 서명이 맞는 토큰이면 우리가 만든 것이라 이런 일이 없어야 하지만, 키가 바뀌지 않은 채 클레임 구조가 바뀌는 경우 등을 대비한다.

### 5.2 `JwtAuthenticationFilter` 중 토큰 부분

경로: `src/main/java/com/nhnacademy/blog/global/auth/JwtAuthenticationFilter.java`

```java
Optional<Long> accessMemberId = accessCookie
        .flatMap(token -> tokenProvider.parse(token, TokenType.ACCESS))
        .filter(claims -> !tokenStore.isAccessBlocked(claims.id()))     // 로그아웃한 Access 거절
        .map(TokenClaims::memberId);
Optional<TokenClaims> refresh = refreshCookie
        .flatMap(token -> tokenProvider.parse(token, TokenType.REFRESH));
Optional<Long> memberId = accessMemberId.or(() -> refresh               // Access가 안 되면 Refresh로
        .filter(claims -> tokenStore.isRefreshActive(claims.id()))      // Redis에 살아 있는 것만
        .map(TokenClaims::memberId));

Optional<Member> member = memberId.flatMap(memberRepository::findById);  // 3.9: 요청마다 DB 확인
...
LoginMember loginMember = new LoginMember(member.get().getId(), member.get().getRole());  // 역할은 DB 값
if (accessMemberId.isEmpty()) {
    cookieManager.issueAccess(response, loginMember);                    // Refresh로 들어왔으면 새 Access
}
refresh.filter(claims -> !claims.rememberMe())
        .ifPresent(claims -> tokenStore.extendRefresh(claims.id(), authProperties.idleTimeout()));  // 3.8
```

**조용한 재발급**: 일반적인 구조는 "Access 만료 → API가 401 → 프론트가 `/api/auth/token/refresh` 호출 → 원래 요청 재시도"다. 이 프로젝트는 필터가 같은 요청 안에서 새 Access 쿠키를 응답에 실어 준다. 프론트가 재시도 로직을 가질 필요가 없고, 화면 주소 요청(HTML)에서도 로그인 상태가 이어진다. rest-api.md의 refresh API는 명시적으로 갱신하고 싶을 때를 위해 남아 있다.

### 5.3 `TokenStore`

경로: `src/main/java/com/nhnacademy/blog/global/auth/TokenStore.java`

```java
private static final String REFRESH_PREFIX = "auth:refresh:";
private static final String BLOCKED_ACCESS_PREFIX = "auth:blocked-access:";

/** idleTimeout이 null이면 토큰 만료 때까지(로그인 유지), 아니면 무활동 시간만큼 둔다. */
public void saveRefresh(IssuedToken refreshToken, Long memberId, Duration idleTimeout) {
    Duration ttl = untilExpiry(refreshToken.expiresAt());          // 토큰 남은 수명(약 14일)
    if (idleTimeout != null && idleTimeout.compareTo(ttl) < 0) {
        ttl = idleTimeout;                                         // 더 짧은 쪽(30분)
    }
    if (!ttl.isZero()) {
        redis.opsForValue().set(REFRESH_PREFIX + refreshToken.id(), String.valueOf(memberId), ttl);
    }
}

/** 활동이 있었으니 무활동 기한을 다시 센다. 이미 끝났으면 false. */
public boolean extendRefresh(String refreshTokenId, Duration idleTimeout) {
    return Boolean.TRUE.equals(redis.expire(REFRESH_PREFIX + refreshTokenId, idleTimeout));
}
```

- Redis `SET key value EX 초`는 값과 TTL을 한 번에 저장한다. TTL이 지나면 Redis가 키를 지운다.
- Redis `EXPIRE key 초`는 **이미 있는 키**의 TTL을 다시 정한다. 키가 없으면 아무것도 하지 않고 0(false)을 돌려준다. 그래서 무활동으로 이미 지워진 세션이 되살아나지 않는다.
- 값으로 회원 id를 넣지만 지금 코드는 키가 있는지(`hasKey`)만 본다. 나중에 "이 회원의 모든 세션 끊기" 같은 기능을 만들 때 쓸 수 있다.

### 5.4 설정값

```yaml
app:
  auth:
    access-token-ttl: 30m
    refresh-token-ttl: 14d
    idle-timeout: 30m
    jwt-secret: ...   # dev: application-dev.yml, prod: ${JWT_SECRET}
```

`AuthProperties`(record + `@ConfigurationProperties(prefix = "app.auth")`)가 이 값을 `Duration`으로 받는다. `30m`, `14d` 같은 표기는 Spring Boot가 `Duration`으로 바꿔 준다([02-configuration-profiles](./02-configuration-profiles.md)).

---

## 6. 자주 하는 실수와 함정

1. **JWT에 민감한 정보를 넣는다.** 내용은 누구나 읽는다. 이메일, 전화번호도 넣지 않는다.
2. **"서명했으니 안전하다"며 토큰만 믿는다.** 정지·탈퇴·역할 변경은 토큰에 반영되지 않는다. 이 프로젝트는 요청마다 DB를 본다.
3. **짧은 비밀 키, 소스에 박힌 운영 키.** 개발 키(`dev-only-jwt-secret-...`)가 운영에 쓰이면 누구나 관리자 토큰을 만들 수 있다. 운영은 반드시 환경 변수로 다른 키를 준다.
4. **헤더의 `alg`를 그대로 믿는다.** 예전 라이브러리에는 토큰이 `alg: none`이라고 하면 서명 검사를 건너뛰는 문제가 있었다(RFC 8725가 경고). 이 프로젝트는 디코더에 HS256을 고정해 두었다.
5. **Refresh 토큰을 Access처럼 쓸 수 있게 둔다.** 수명이 긴 토큰이 매 요청에 쓰이게 된다. `typ` 클레임으로 구분한다.
6. **로그아웃 = 쿠키 삭제로 끝낸다.** 브라우저의 쿠키만 지워지고 토큰 자체는 살아 있다. 다른 곳에 복사된 토큰은 계속 쓰인다. 서버 쪽 무효화(Redis)가 필요하다.
7. **시계 오차를 잊는다.** 디코더는 60초를 봐준다. 테스트에서 "만료 직후 거절"을 확인하려면 60초 이상 지난 시각으로 만들어야 한다.
8. **Refresh 교체를 넣으면서 동시 요청을 생각하지 않는다.** 화면이 API를 여러 개 동시에 부르면 정상 사용자가 로그아웃된다(3.7).

---

## 7. 직접 해 보기

### 실습 1: 토큰을 열어 보기

```bash
./mvnw test -Dtest=AuthenticationIntegrationTest#loginCookieAuthenticates
```

이 테스트가 만드는 토큰을 보려면 `src/test/.../support/TestMembers.java`의 `loginCookies`에 `System.out.println(...)`을 잠시 넣어 쿠키 값을 출력하고, 그 값을 jwt.io의 Encoded 칸에 붙인다. 오른쪽에 헤더와 내용이 그대로 보인다(서명 키를 넣지 않아도). `sub`, `exp`, `jti`, `typ`, `role`을 찾아본다. 확인 후 출력 줄을 지운다.

### 실습 2: 내용을 바꾸면?

jwt.io에서 내용의 `"role": "USER"`를 `"ADMIN"`으로 고치면 토큰 문자열의 가운데 부분이 바뀐다. 이 토큰을 서버로 보내면 어떻게 될지 예상해 본다(서명이 맞지 않아 `parse`가 빈 값 → 비회원 → `/api/admin/**`은 401).

### 실습 3: 짧은 키로 앱 띄우기

```bash
./mvnw spring-boot:run -Dspring-boot.run.arguments="--app.auth.jwt-secret=short"
```

기대 결과: 시작 단계에서 `app.auth.jwt-secret은 32바이트 이상이어야 합니다.`로 실패.

### 실습 4: 무활동 만료 관찰

```bash
./mvnw test -Dtest=IdleTimeoutIntegrationTest
```

테스트 코드를 읽고, `application.yml`의 `idle-timeout`을 `1m`으로 바꾸면 어느 테스트가 깨지는지(30분을 기대하는 단언) 확인한다. 원래대로 돌린다.

### 실습 5: Redis에서 토큰 상태 보기 (스텝 4 이후)

로그인한 뒤:

```bash
docker exec blog-redis redis-cli KEYS 'auth:*'
docker exec blog-redis redis-cli TTL auth:refresh:<jti>     # 로그인 유지 안 함이면 1800 이하
```

API를 한 번 부른 뒤 다시 `TTL`을 보면 1800 가까이로 돌아와 있다(연장).

---

## 8. 확인 문제

1. JWT의 내용 부분을 Base64URL로 풀면 누구나 읽을 수 있다. 그러면 서명은 무엇을 보장하는가?
<details><summary>답</summary>

내용이 서버가 만든 그대로이고 바뀌지 않았음(무결성, 발급자 확인). 비밀 유지는 보장하지 않는다.
</details>

2. 이 프로젝트가 RS256이 아니라 HS256을 쓰는 이유는?
<details><summary>답</summary>

토큰을 발급하는 서버와 검증하는 서버가 같아서 비밀 키를 나눠 줄 상대가 없다. 다른 서비스가 검증만 해야 한다면 공개 키로 검증하는 RS256이 맞다.
</details>

3. Access 토큰을 30분, Refresh 토큰을 14일로 나눈 이유를 "도난"과 "편의" 두 관점에서 설명하라.
<details><summary>답</summary>

도난: 매 요청에 실려 다니는 Access는 짧게 해서 훔쳐도 금방 못 쓰게 한다. 편의: Refresh로 새 Access를 받으니 30분마다 다시 로그인하지 않는다. 가끔만 쓰는 Refresh는 Redis로 살아 있는지 확인해 즉시 무효화할 수 있다.
</details>

4. 로그아웃했는데도 훔쳐 간 Access 토큰이 남은 수명 동안 쓰이지 않게 하는 장치는?
<details><summary>답</summary>

`TokenStore.blockAccess`: 그 Access 토큰의 jti를 남은 수명만큼 Redis 차단 목록에 둔다. 필터가 `isAccessBlocked`로 거절한다.
</details>

5. Refresh 토큰 교체(rotation) 대신 Redis TTL 연장을 고른 이유는?
<details><summary>답</summary>

교체 방식은 화면이 API를 동시에 여러 개 부를 때, 먼저 교체한 요청 때문에 나머지 요청이 옛 토큰을 쓴 것이 되어 정상 사용자가 로그아웃될 수 있다. 같은 토큰을 쓰고 Redis TTL만 늘리면 이 경쟁이 없다. 대신 도난 감지는 약해진다.
</details>

6. 로그인 유지를 고르지 않은 사용자가 마지막 요청 뒤 40분 만에 돌아왔다. 어떻게 되는가? 단계별로 설명하라.
<details><summary>답</summary>

Access JWT는 마지막 요청 이전에 발급되어 30분 수명이 지났다 → parse 실패. Refresh 쿠키는 브라우저에 있어도 Redis 키가 마지막 요청 후 30분에 지워졌다 → isRefreshActive false. 회원을 못 찾아 쿠키를 지우고 비회원으로 처리한다. 로그인이 필요한 API면 401.
</details>

7. 토큰이 유효한데도 필터가 요청마다 DB에서 회원을 읽는 이유는?
<details><summary>답</summary>

토큰은 발급 시점의 정보다. 그 뒤 정지·탈퇴·역할 변경이 있었을 수 있고, 명세는 정지된 회원을 다음 요청부터 막으라고 한다(ADMIN-02).
</details>

8. jjwt 대신 Nimbus를 고른 이유는?
<details><summary>답</summary>

jjwt의 JSON 모듈은 Jackson 2에 의존하는데 Spring Boot 4는 Jackson 3을 쓴다. Nimbus는 Spring Security(`spring-security-oauth2-jose`)가 감싸서 버전을 관리하고 Jackson 버전 문제가 없다.
</details>

---

## 9. 더 읽을거리

- RFC 7519, *JSON Web Token (JWT)*: https://www.rfc-editor.org/rfc/rfc7519
- RFC 7515, *JSON Web Signature (JWS)*, RFC 7518, *JSON Web Algorithms (JWA)*(HS256 키 길이 3.2절)
- RFC 8725, *JSON Web Token Best Current Practices*(alg 고정, 알고리즘 혼동 공격)
- RFC 9700, *Best Current Practice for OAuth 2.0 Security*(Refresh 토큰 교체)
- OWASP, *JSON Web Token for Java Cheat Sheet*
- Spring Security 레퍼런스, *OAuth 2.0 Resource Server – JWT*(`NimbusJwtDecoder`, 검증기)
- jwt.io(토큰 디코딩 도구. 운영 토큰은 붙이지 않는다)
- 이어서 읽기: [12-spring-security-filter-chain](./12-spring-security-filter-chain.md)
