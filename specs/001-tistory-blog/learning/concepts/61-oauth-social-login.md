# 61. 소셜 로그인: OAuth 2.0 인가 코드 흐름

> 관련 스텝: [스텝 20b](../step-20b.md) (T099, T100) · 관련 개념: [10 HTTP 쿠키](./10-http-cookies.md)(꼭 먼저), [13 CSRF, SameSite, CORS](./13-csrf-samesite-cors.md)(꼭 먼저), [15 서브도메인과 Host 라우팅](./15-subdomain-host-routing.md), [17 멱등성과 Redis](./17-idempotency-redis.md), [21 가입과 로그인](./21-signup-login.md)(열린 리다이렉트), [23 트랜잭션과 동시성](./23-transactions-locking.md), [33 격리 수준](./33-isolation-deadlock.md), [55 모듈 경계](./55-module-boundary-archunit.md)

## 1. 이 문서로 배우는 것

- **OAuth 2.0**이 푸는 문제와 등장인물: 자원 소유자, 클라이언트, 인가 서버, 자원 서버
- **인가 코드 흐름(authorization code flow)** 한 바퀴: authorize 주소 → 제공사 로그인 → 리다이렉트 URI로 code → 서버가 code를 토큰으로 바꾸기 → 회원 번호 읽기
- 리다이렉트 URI를 제공사 콘솔에 **미리 등록**하는 이유, 클라이언트 시크릿을 서버에만 두는 이유
- OAuth(권한 위임)와 **OpenID Connect**(로그인)의 차이: 구글 `scope=openid`와 `sub`, 카카오 `/v2/user/me`의 `id`
- **`state` 파라미터와 로그인 CSRF**, 이 프로젝트가 state를 **Redis와 브라우저 쿠키 두 곳**에 두는 이유
- 콜백 뒤에 **한 번 더 건너뛰는 이유**(callback → 플랫폼 주소의 `complete?ticket=`)
- Redis로 **한 번만 쓰는 표** 만들기: "읽고 지우기"에서 지우기에 성공한 한 번만 이긴다
- 처음 보는 소셜 계정의 **가입 토큰과 닉네임 확인**, 회원과 연동을 한 트랜잭션으로
- **계정 연동 규칙**(R-07): 이메일로 합치지 않기, 제공사당 하나, 소셜 계정은 회원 하나에만, 마지막 로그인 수단은 해제 불가(회원 행 잠금)
- 소셜로 가입한 회원의 **탈퇴 본인 확인(재인증)**: 카카오 `prompt=login`, 구글 `max_age=0`, 10분짜리 표시를 한 번만
- **열린 리다이렉트** 막기(`safeRedirect`)와, 제공사 이메일을 **받지도 저장하지도 않는** 이유

## 2. 왜 필요한가

"카카오로 계속하기" 버튼은 흔하지만, 속을 모르고 만들면 구멍이 많이 생긴다.

- **비밀번호를 우리가 받으면 안 된다.** 사용자가 카카오 비밀번호를 우리 화면에 넣게 하면, 우리 서버가 그 비밀번호를 알게 된다. 우리가 털리면 사용자의 카카오 계정까지 털린다. 사용자는 **카카오 화면에서** 로그인하고, 우리는 "이 사람이 카카오 회원 123번이다"라는 사실만 받아야 한다.
- **돌아오는 길이 공격 통로가 된다.** 제공사는 로그인이 끝나면 브라우저를 우리 주소로 돌려보낸다. 이 주소는 누구나 브라우저에 칠 수 있다. 아무 검사 없이 "돌아왔으니 로그인"이라고 하면, 남이 만든 주소를 열기만 해도 남의 계정으로 로그인되는 일이 생긴다(4.3 로그인 CSRF).
- **계정이 섞인다.** "카카오 이메일이 우리 회원 이메일과 같으니 같은 사람"이라고 합치면, 남의 이메일로 만든 소셜 계정으로 그 회원 계정에 들어올 수 있다(3.7).

기능 명세는 이렇게 정했다(spec "계정과 소셜 연동", research R-07).

- 처음 가입한 방식이 기본 수단이다. 수단을 더하는 길은 **로그인한 상태에서 마이페이지 연동** 하나뿐이다.
- 이메일이 같다고 회원을 합치지 않는다. 제공사 이메일은 저장하지 않는다.
- 소셜 계정 하나는 회원 하나에만, 회원은 제공사마다 하나만. 해제하면 로그인 수단이 하나도 없어지는 경우는 거절.
- OAuth state를 검증하고, 돌아갈 곳은 우리 서비스 주소만.
- 소셜로만 가입한 회원은 비밀번호가 없으니, 탈퇴 본인 확인은 **소셜로 다시 로그인**(재인증)으로 한다(AUTH-06).

## 3. 기본 개념

### 3.1 OAuth 2.0이 푸는 문제와 등장인물

OAuth 2.0(RFC 6749)은 원래 **권한 위임**을 위한 규약이다. "사진 인화 서비스가 내 구글 포토의 사진을 읽게 허락한다"처럼, 비밀번호를 넘기지 않고 **제한된 권한(토큰)**만 넘긴다.

| 역할 | 뜻 | 이 프로젝트에서 |
| --- | --- | --- |
| 자원 소유자(resource owner) | 데이터의 주인, 허락하는 사람 | 카카오·구글 계정을 가진 사용자 |
| 클라이언트(client) | 권한을 받으려는 앱 | 우리 블로그 서버 |
| 인가 서버(authorization server) | 로그인시키고 허락을 받아 토큰을 주는 곳 | `kauth.kakao.com`, `accounts.google.com`·`oauth2.googleapis.com` |
| 자원 서버(resource server) | 토큰을 받고 데이터를 주는 API | `kapi.kakao.com`, `openidconnect.googleapis.com` |

클라이언트는 미리 제공사 콘솔에 **앱을 등록**해 두 가지를 받는다.

- **클라이언트 ID**(`client_id`): 앱 이름표. 주소에 그대로 나가도 되는 공개 값이다.
- **클라이언트 시크릿**(`client_secret`): 앱의 비밀번호. 서버만 알고, 브라우저에는 절대 보내지 않는다.

우리 서버처럼 시크릿을 안전하게 숨길 수 있는 클라이언트를 **기밀 클라이언트(confidential client)**라고 한다. 브라우저에서만 도는 앱이나 휴대폰 앱은 시크릿을 숨길 수 없어 **공개 클라이언트(public client)**라 하고, 다른 장치(PKCE)를 쓴다.

### 3.2 인가 코드 흐름 한 바퀴

OAuth에는 여러 흐름이 있고, 서버가 있는 웹 앱의 표준은 **인가 코드 흐름**이다.

```
 브라우저                      우리 서버                     제공사(카카오)
   │ ① "카카오로 계속하기"         │                              │
   │──GET /authorize────────────▶│ state 만들기                  │
   │◀─302 kauth.kakao.com/oauth/authorize?client_id&redirect_uri&state
   │──────────────────────────────────────────────────────────▶│ ② 카카오 로그인 화면
   │                              │                              │   (사용자가 카카오에서 로그인·동의)
   │◀─302 {redirect_uri}?code=XYZ&state=…────────────────────────│ ③ 브라우저를 돌려보냄
   │──GET /callback?code&state──▶│                              │
   │                              │──POST /oauth/token (code, client_id, client_secret)─▶│ ④ 서버끼리
   │                              │◀──{ access_token }───────────│
   │                              │──GET /v2/user/me (Bearer access_token)──────────────▶│ ⑤
   │                              │◀──{ id: 123 }───────────────│
   │◀─ 로그인 쿠키, 302 ──────────│ ⑥ "카카오 123번"인 회원으로 로그인
```

- ①의 **authorize 주소**에 붙는 것: `response_type=code`(코드를 달라), `client_id`, `redirect_uri`(끝나면 돌아올 곳), `state`(3.5), 필요하면 `scope`(무엇을 허락받을지).
- ③에서 제공사가 브라우저에 주는 **code**(인가 코드)는 "이 사용자가 이 앱에 허락했다"는 **짧게 사는 일회용 교환권**이다. 이것만으로는 아무것도 못 한다. RFC 6749는 code를 짧게(최대 10분 권장) 살게 하고, 한 번만 쓰게 하라고 정한다.
- ④는 **브라우저를 거치지 않고 서버끼리** 한다. code와 함께 **클라이언트 시크릿**을 보내므로, code를 훔친 사람이 있어도 시크릿이 없으면 토큰으로 바꿀 수 없다.
- ⑤ 받은 **액세스 토큰**으로 "이 토큰의 주인은 누구냐"를 묻는다.

왜 처음부터 토큰을 브라우저에 주지 않고 code를 거칠까? 브라우저를 오가는 주소는 방문 기록, 서버 로그, `Referer` 헤더 등 여러 곳에 남는다. 그 길에는 **혼자서는 쓸모없는 짧은 code**만 지나가게 하고, 진짜 토큰은 서버끼리의 연결로만 받는다.

### 3.3 리다이렉트 URI를 미리 등록하는 이유

제공사 콘솔에 "이 앱은 끝나면 **이 주소로만** 돌려보낸다"를 등록하고, authorize 주소의 `redirect_uri`가 등록한 것과 **글자 하나까지 같아야** 받아 준다(구글·카카오 모두). 등록이 없다면 공격자가 `redirect_uri=https://evil.example/steal`로 바꾼 authorize 주소를 피해자에게 보내, 피해자의 code를 자기 서버로 받아 갈 수 있다.

토큰 교환(④)에도 같은 `redirect_uri`를 다시 보낸다. 제공사가 "code를 줄 때 쓴 주소와 같은가"를 확인한다.

구글은 등록하는 주소에 규칙이 더 있다.

- `https`여야 한다. 예외는 `http://localhost`뿐이다.
- 도메인은 공개 최상위 도메인(`.com`, `.net` 등)으로 끝나야 한다. 개발용 `blog.test`는 `.test`가 공개 도메인이 아니라 등록할 수 없다.

그래서 이 프로젝트는 개발에서 콜백을 `http://localhost:8080/api/auth/oauth/google/callback`으로 등록한다. 이것이 3.6의 "한 번 더 건너뛰기"를 낳는다.

### 3.4 OAuth는 로그인이 아니다: OpenID Connect

OAuth 2.0 자체는 "이 토큰으로 사진을 읽어도 된다"는 **권한**만 다루고, "이 사람이 누구다"를 표준으로 말하지 않는다. 그래서 로그인에 쓰려면 "토큰의 주인이 누구냐"를 알아내는 방법이 따로 필요하다.

- **카카오**: 액세스 토큰으로 `GET https://kapi.kakao.com/v2/user/me`를 부르면 응답의 `id`(숫자)가 카카오 회원 번호다. 이메일·닉네임 같은 다른 정보는 콘솔에서 **동의 항목**을 켜야 들어오고, 이 프로젝트는 켜지 않는다.
- **구글**: **OpenID Connect(OIDC)**를 쓴다. OIDC는 OAuth 2.0 위에 "로그인"을 얹은 표준이다. `scope=openid`를 요청하면 로그인 흐름이 되고, userinfo 주소(`https://openidconnect.googleapis.com/v1/userinfo`)가 돌려주는 **`sub`**(subject)가 그 구글 계정의 고유 번호다. `sub`는 구글 계정마다 다르고 다시 쓰이지 않는다. 구글도 이메일이 아니라 `sub`를 계정 식별자로 쓰라고 안내한다.

OIDC는 토큰 교환 응답에 **ID 토큰**(서명된 JWT, 그 안에 `sub`)도 준다. ID 토큰의 서명을 확인하면 userinfo를 한 번 더 부르지 않아도 된다. 이 프로젝트는 서명 확인 코드를 더 두지 않으려고, 받은 액세스 토큰으로 userinfo를 불러 `sub`를 읽는 쉬운 길을 골랐다.

| 제공사 | 받는 것 | 이 프로젝트가 쓰는 값 |
| --- | --- | --- |
| 카카오 | `/v2/user/me` 응답 | `id` (예: `4012345678`) |
| 구글 | `scope=openid`, userinfo 응답 | `sub` (예: `1098…`) |

DB에는 `social_account(provider, provider_user_id)`로 `KAKAO, 4012345678`처럼 저장한다.

### 3.5 `state`와 로그인 CSRF

`state`는 authorize 주소에 붙여 보내면 제공사가 **그대로 돌려주는** 값이다. 클라이언트는 돌아온 state가 "내가 이 브라우저에 보낸 그 값"인지 확인한다. 이것으로 막는 공격이 **로그인 CSRF**다.

```
공격자: 자기 브라우저로 "카카오로 계속하기" → 자기 카카오 계정으로 로그인
        → 제공사가 돌려보내는 주소 https://우리/callback?code=공격자코드&state=…
        → 이 주소를 따라가지 않고 멈춰서 복사
공격자: 이 주소를 피해자에게 링크로 보냄(또는 이미지 태그에 넣음)
피해자: 열기만 함 → 우리 서버가 code를 바꿔 보니 "공격자 카카오 계정" → 피해자 브라우저가 공격자 계정으로 로그인
```

피해자는 자기 계정인 줄 알고 글을 쓰거나 개인 정보를 넣는다. 그것이 모두 공격자 계정에 쌓이고 공격자는 나중에 본다. 일반 CSRF([13](./13-csrf-samesite-cors.md))가 "피해자 계정으로 원치 않는 일을 시키는" 것이라면, 로그인 CSRF는 "피해자를 **공격자 계정으로** 로그인시키는" 것이다.

막는 법: 흐름을 시작할 때 **추측할 수 없는 state**를 만들어 **시작한 브라우저에 묶어 두고**, 돌아왔을 때 "이 브라우저가 시작한 흐름의 state인가"를 본다. 공격자가 보낸 주소의 state는 공격자 브라우저에 묶인 값이라, 피해자 브라우저에는 맞는 짝이 없다.

"브라우저에 묶는" 보통의 방법은 서버 세션(또는 쿠키)에 state를 두는 것이다. 이 프로젝트는 세션이 없고(JWT 쿠키, [11](./11-jwt.md)), 콜백 주소가 플랫폼 주소와 달라서(3.6) 조금 다르게 한다(3.6, 4.2).

### 3.6 콜백과 로그인 쿠키를 주는 곳이 다를 때: 한 번 더 건너뛰기

이 프로젝트의 로그인 쿠키는 `Domain=.blog.test`(운영은 `.{플랫폼 도메인}`)다. 그래서 플랫폼 주소와 모든 블로그 주소(`alpha.blog.test`)가 같은 로그인 쿠키를 쓴다([10](./10-http-cookies.md), [15](./15-subdomain-host-routing.md)).

브라우저는 응답한 호스트와 **상관없는 도메인의 쿠키를 받아 주지 않는다**. `http://localhost:8080/api/auth/oauth/google/callback`의 응답에 `Set-Cookie: access_token=…; Domain=.blog.test`를 넣어도 브라우저는 버린다. 즉 **구글이 돌려보내는 콜백(localhost)에서는 로그인 쿠키를 줄 수 없다**.

그래서 흐름을 둘로 나눴다.

```
callback (localhost:8080, 제공사가 오는 곳)
  : state 확인·한 번 쓰기 → code를 회원 번호로 바꾸기 → 2분짜리 "표(ticket)"에 담기
  → 302 http://blog.test:8080/api/auth/oauth/complete?ticket=…   (시작한 플랫폼 주소)
complete (blog.test, 로그인을 시작한 곳)
  : 표를 한 번 쓰기 → 이 브라우저의 state 쿠키와 표의 state가 같은가 → 로그인 쿠키(Domain=.blog.test) → 갈 곳으로 302
```

`complete`는 **로그인을 시작한 그 플랫폼 주소**(`origin`, 예: `http://blog.test:8080`)에서 열리므로 `.blog.test` 쿠키를 줄 수 있다. 또 시작할 때 이 주소에 심은 **state 쿠키를 읽을 수 있다**. 콜백(localhost)에서는 blog.test의 쿠키가 오지 않으니, state를 브라우저와 맞춰 보는 일도 `complete`에서 한다.

운영처럼 콜백을 `https://blog.com/...`으로 등록할 수 있으면 건너뛰기가 없어도 되지만, 개발과 운영의 흐름을 같게 두려고 늘 건너뛴다.

### 3.7 이메일로 합치지 않는 이유와 제공사 이메일을 저장하지 않는 이유

"카카오 이메일이 `jiwon@x.com`이고, 우리 회원 중에 `jiwon@x.com`이 있으니 같은 사람"이라고 자동으로 합치는 서비스가 있다. 편하지만 위험하다.

- 제공사가 준 이메일이 **확인된 이메일인지** 늘 보장되지 않는다. 확인 안 된 이메일을 넣을 수 있는 제공사라면, 공격자가 **남의 이메일로 소셜 계정을 만들어** 그 사람의 우리 계정에 들어올 수 있다(계정 탈취).
- 사용자가 제공사에서 이메일을 바꾸면 우리 쪽 판단이 흔들린다.
- 이메일이 같다는 것은 "같은 사람일 것 같다"이지 "본인임이 증명됐다"가 아니다.

그래서 R-07은 **수단을 더하는 길을 "로그인한 상태에서 마이페이지 연동" 하나**로 정했다. 로그인한 상태라는 것이 "이 계정의 주인"이라는 증명이고, 그 상태에서 소셜 로그인까지 마치면 "이 소셜 계정의 주인"도 증명된다. 두 증명이 같은 브라우저에서 이어질 때만 묶는다.

이메일로 합치지 않으니 제공사 이메일은 쓸 데가 없다. **쓰지 않는 개인 정보는 받지도 저장하지도 않는다**(최소 수집). 카카오는 동의 항목을 켜지 않고, 구글은 `scope=openid`만(`email`·`profile` 없이) 요청한다. 털려도 내줄 것이 적다.

### 3.8 한 번만 쓰는 값: Redis "읽고 지우기"

state, 표(ticket), 가입 토큰, 재인증 표시는 모두 **한 번만** 쓰여야 한다. 같은 콜백 주소가 두 번 열리거나(새로고침, 뒤로 가기, 공격자의 재전송) 동시에 두 번 와도 한 번만 통과해야 한다.

Redis에서 "읽고 → 지우기"를 두 명령으로 하면 사이에 틈이 있다.

```
요청 A: 읽기(있음)                         요청 B: 읽기(있음)
요청 A: DEL → 1 (내가 지웠다)              요청 B: DEL → 0 (이미 없었다)
```

둘 다 읽기에는 성공하지만, **`DEL`은 한 명령이라 둘 중 하나만 1(지운 키 수)을 받는다.** 그래서 "지우기에 성공한 쪽만 쓴다"로 하면 정확히 한 번만 통과한다. 이 프로젝트의 `take`가 이것이다(5.2).

값이 문자열 하나라면 Redis 6.2부터 있는 `GETDEL`(읽고 지우기를 한 명령으로)도 쓸 수 있다. 이 프로젝트는 여러 칸을 Redis 해시(hash)에 담아서 `HGETALL` + `DEL`로 했다.

### 3.9 다시 로그인하게 하기: `prompt=login`과 `max_age=0`

탈퇴처럼 되돌릴 수 없는 일 앞에서는 "지금 이 브라우저 앞에 있는 사람이 정말 주인인가"를 다시 확인한다. 비밀번호 회원은 비밀번호를 다시 넣게 하면 된다. 소셜 회원은 **소셜로 다시 로그인**하게 하는데, 문제가 있다. 사용자가 이미 카카오·구글에 로그인해 있으면 제공사는 **묻지 않고 바로** code를 돌려준다. 그러면 자리를 비운 PC에서 남이 버튼만 눌러도 확인이 끝난다.

그래서 authorize 주소에 "이미 로그인해 있어도 다시 로그인시켜 달라"를 붙인다. 붙이는 방법이 제공사마다 다르다.

| 제공사 | 방법 | 비고 |
| --- | --- | --- |
| 카카오 | `prompt=login` | 기존 로그인과 상관없이 다시 로그인 화면 |
| 구글 | `max_age=0` (OIDC) | 구글의 `prompt`는 `none`·`consent`·`select_account`만 받고 `login`이 없다 |

OIDC의 `max_age`는 "로그인한 지 이 초보다 오래됐으면 다시 로그인시켜라"는 뜻이라 `0`이면 늘 다시 로그인이다. OIDC 표준은 `max_age`를 쓴 클라이언트가 ID 토큰의 `auth_time`(실제 로그인한 시각)을 확인하라고 권한다. 이 프로젝트는 ID 토큰을 읽지 않아 그 확인은 하지 않는다(6장 "남은 것").

## 4. 동작 원리

### 4.1 전체 흐름

```
[시작] 브라우저: <a href="/api/auth/oauth/kakao/authorize?mode=login&redirect=…">  (blog.test)
  OAuthController.authorize
    link·reauth인데 비회원 → /login?redirect=/me(또는 /me/withdraw)
    SocialAuthService.start: 앱 키 없음 → /login?error=OAUTH_UNAVAILABLE
       state(256비트) → Redis oauth:state:{state} = {provider, mode, origin, redirect?, memberId?} 10분
    Set-Cookie oauth_state={state}; Path=/api/auth/oauth; HttpOnly; SameSite=Lax; Max-Age=600
    302 https://kauth.kakao.com/oauth/authorize?response_type=code&client_id&redirect_uri&state

[제공사] 로그인·동의 → 302 http://localhost:8080/api/auth/oauth/kakao/callback?code=…&state=…

[콜백] OAuthController.callback (localhost)
  SocialAuthService.callback
    take(oauth:state:{state}) 없음·다른 제공사 → blog.test/login?error=OAUTH_FAILED
    error 있음(취소) → {origin}/login?error=OAUTH_CANCELLED  (mode에 맞는 화면)
    code → 토큰 → 회원 번호 (실패 → OAUTH_FAILED)
    Redis oauth:ticket:{ticket} = {…state 데이터, state, providerUserId} 2분
  302 {origin}/api/auth/oauth/complete?ticket=…

[끝내기] OAuthController.complete (blog.test, state 쿠키가 따라옴)
  state 쿠키 지우기
  SocialAuthService.complete
    take(oauth:ticket:{ticket}) 없음, 또는 표의 state ≠ 쿠키 → /login?error=OAUTH_FAILED
    mode LOGIN  → 연결된 계정? 정지면 쿠키 없이 /login?error=MEMBER_SUSPENDED&reasonMessage=…&until=…
                  → 로그인 쿠키 + redirect(우리 주소만)
                  처음 보는 계정 → Redis oauth:signup:{token} 10분 → /signup/social?token=…&provider=kakao
    mode LINK   → 시작한 회원 = 지금 회원? → 연동 → /me?linked=kakao  (거절은 /me?error=…)
    mode REAUTH → 시작한 회원 = 지금 회원? 그 회원의 소셜 계정? → Redis oauth:reauth:{회원} 10분 → /me/withdraw?reauth=ok

[가입] POST /api/auth/oauth/signup { signupToken, nickname } → 회원 + social_account 한 트랜잭션 → 201 Me + 로그인 쿠키
[해제] DELETE /api/me/social/{provider} → 회원 행 잠금 → 남는 수단 없으면 409 LAST_LOGIN_METHOD
[탈퇴] DELETE /api/me {} → oauth:reauth:{회원}을 DEL해서 1이면 본인 확인 끝(한 번만)
```

### 4.2 state를 두 곳에 두는 이유

| 어디에 | 무엇을 막나 / 무엇에 쓰나 | 없으면 |
| --- | --- | --- |
| **Redis** `oauth:state:{state}` (10분) | 우리가 만든 값인가, 아직 안 썼나, 10분 안인가. 그리고 이 흐름의 **맥락**(무엇을 하려는지 mode, 돌아갈 origin·redirect, 시작한 회원)을 담는다 | 콜백(localhost)은 blog.test 쿠키를 못 받으니, 콜백에서 state가 진짜인지도, 어디로 돌려보낼지도 알 수 없다 |
| **브라우저 쿠키** `oauth_state` (10분, 시작한 플랫폼 주소에만) | **시작한 브라우저와 끝내는 브라우저가 같은가** | Redis만 보면 state는 "진짜"이기만 하면 통과한다. 공격자가 자기 흐름의 콜백 주소를 피해자에게 열게 하면, 진짜 state라서 피해자가 공격자 계정으로 로그인된다(3.5) |

콜백에서는 Redis로 "진짜인가·한 번만"을 보고, complete에서는 쿠키로 "같은 브라우저인가"를 본다. 둘이 합쳐져야 3.5의 공격이 막힌다.

```
공격자 브라우저: authorize → state=S (Redis에 S, 공격자 브라우저 쿠키에 S)
              → 카카오 로그인 → callback?code=C&state=S 주소를 따라가지 않고 복사
피해자 브라우저: callback?code=C&state=S 열기
              → Redis에 S 있음 → 표 T(state=S) → complete?ticket=T (blog.test)
              → 피해자 브라우저의 oauth_state 쿠키: 없음(또는 피해자가 시작한 다른 값)
              → S와 다름 → /login?error=OAUTH_FAILED, 로그인 쿠키 없음
```

`link`·`reauth`는 한 겹 더 있다. state에 **시작한 회원 번호**를 적어 두고, complete에서 **지금 로그인한 회원**과 같아야 한다. 공격자가 자기 연동 흐름을 피해자에게 열게 해 "공격자의 소셜 계정을 피해자 계정에 연결"하는 길을 막는다.

### 4.3 state 쿠키의 속성

| 속성 | 값 | 이유 |
| --- | --- | --- |
| Domain | 없음 | 플랫폼 주소에서만 쓴다. 블로그 주소와 나눌 필요가 없다(Domain이 없으면 그 호스트에만) |
| Path | `/api/auth/oauth` | 이 아래 요청에만 따라간다. 다른 API에는 실리지 않는다 |
| HttpOnly | 예 | 자바스크립트로 읽을 일이 없다 |
| SameSite | `Lax` | `Strict`면 안 된다. complete로 오는 이동은 **다른 사이트(localhost, 또는 제공사)에서 시작된 이동**이다. Lax는 다른 사이트에서 온 **최상위 GET 이동**에는 쿠키를 보내고, Strict는 보내지 않는다([13](./13-csrf-samesite-cors.md)) |
| Max-Age | 600(10분) | Redis의 state 수명과 같다 |

### 4.4 한 번만 쓰는 값들의 수명

| Redis 키 | 수명 | 언제 지우나 | 왜 이 길이 |
| --- | --- | --- | --- |
| `oauth:state:{state}` | 10분 | 콜백에서(take) | 제공사 화면에서 로그인·동의하는 시간 |
| `oauth:ticket:{ticket}` | 2분 | complete에서(take) | 콜백 → complete는 바로 이어지는 302라 짧게 |
| `oauth:signup:{token}` | 10분 | 가입에 **성공했을 때** | 닉네임을 고르는 시간. 닉네임이 겹쳐 실패하면 다시 써야 하므로 성공할 때만 지운다 |
| `oauth:reauth:{회원 번호}` | 10분 | 탈퇴할 때(DEL이 1이면 통과) | 확인 뒤 탈퇴 버튼을 누를 시간 |

## 5. 이 프로젝트에서는

### 5.1 제공사 하나: `auth/application/OAuthClient`, `KakaoOAuthClient`, `GoogleOAuthClient`

제공사마다 다른 것(주소, 파라미터, 응답 모양)을 인터페이스 하나 뒤에 숨겼다.

```java
public interface OAuthClient {

    SocialProvider provider();

    /** 앱 키가 설정되어 있나. */
    boolean configured();

    /** reauth면 이미 제공사에 로그인해 있어도 다시 확인하게 한다(탈퇴 본인 확인). */
    String authorizeUrl(String state, boolean reauth);

    /** code → 제공사 회원 번호. 실패하면 예외. */
    String fetchUserId(String code);

}
```

- 흐름(state, 표, 가입·연동 판단)은 `SocialAuthService` 하나가 하고, 제공사별 차이는 이 두 메서드에만 있다. 네이버를 더한다면 구현 하나만 더한다.
- 테스트는 이 인터페이스의 가짜(5.8)로 진짜 카카오 없이 흐름 전체를 돈다.

카카오의 authorize 주소:

```java
    @Override
    public String authorizeUrl(String state, boolean reauth) {
        UriComponentsBuilder uri = UriComponentsBuilder.fromUriString("https://kauth.kakao.com/oauth/authorize")
                .queryParam("response_type", "code")
                .queryParam("client_id", properties.clientId())
                .queryParam("redirect_uri", properties.redirectUri())
                .queryParam("state", state);
        if (reauth) {
            uri.queryParam("prompt", "login");
        }
        return uri.encode().toUriString();
    }
```

- `response_type=code`: 인가 코드 흐름(3.2).
- `redirect_uri`: 설정값. 카카오 콘솔에 등록한 주소와 글자까지 같아야 한다(3.3).
- `scope`가 없다: 동의 항목을 받지 않는다. 회원 번호(`id`)는 동의 없이 온다.
- `prompt=login`: 재인증일 때만(3.9).
- `.encode()`: `redirect_uri`의 `:`, `/` 같은 글자를 주소 안에 넣을 수 있게 퍼센트 인코딩한다.

code를 회원 번호로 바꾸기:

```java
    @Override
    public String fetchUserId(String code) {
        MultiValueMap<String, String> form = new LinkedMultiValueMap<>();
        form.add("grant_type", "authorization_code");
        form.add("client_id", properties.clientId());
        form.add("redirect_uri", properties.redirectUri());
        form.add("code", code);
        if (properties.clientSecret() != null && !properties.clientSecret().isBlank()) {
            form.add("client_secret", properties.clientSecret());
        }
        TokenResponse token = restClient.post()
                .uri("https://kauth.kakao.com/oauth/token")
                .contentType(MediaType.APPLICATION_FORM_URLENCODED)
                .body(form)
                .retrieve()
                .body(TokenResponse.class);
        if (token == null || token.access_token() == null) {
            throw new IllegalStateException("카카오가 토큰을 주지 않았습니다");
        }
        UserResponse user = restClient.get()
                .uri("https://kapi.kakao.com/v2/user/me")
                .header("Authorization", "Bearer " + token.access_token())
                .retrieve()
                .body(UserResponse.class);
        if (user == null || user.id() == null) {
            throw new IllegalStateException("카카오가 회원 번호를 주지 않았습니다");
        }
        return String.valueOf(user.id());
    }

    record TokenResponse(String access_token) {
    }

    record UserResponse(Long id) {
    }
```

- 3.2의 ④⑤다. **서버에서 서버로** 보내는 요청이라 브라우저는 시크릿을 볼 수 없다.
- 토큰 교환은 JSON이 아니라 **폼 형식**(`application/x-www-form-urlencoded`)이다. OAuth 2.0 표준이 그렇게 정했다. `MultiValueMap`을 body로 주면 `RestClient`가 폼으로 바꿔 보낸다.
- `grant_type=authorization_code`: "인가 코드를 토큰으로 바꾸겠다".
- 카카오는 클라이언트 시크릿을 콘솔에서 켰을 때만 요구해서, 값이 있을 때만 보낸다.
- `Authorization: Bearer {토큰}`: "이 토큰을 가진 사람으로서 묻는다"(Bearer = 가진 사람).
- 응답 record에는 **필요한 칸만** 둔다. 진짜 응답에는 `refresh_token`, `expires_in` 같은 칸이 더 온다. record에 없는 칸이 와도 괜찮은지는 Jackson의 "모르는 칸이면 실패" 설정에 달렸고, 테스트는 가짜 제공사라 **진짜 응답으로는 아직 확인하지 않았다**(6장 "남은 것"). 액세스 토큰은 회원 번호를 읽은 뒤 **버린다**. 우리는 카카오 API를 더 부를 일이 없어 저장하지 않는다.
- 실패하면 예외. 부르는 쪽(`callback`)이 잡아서 `OAUTH_FAILED`로 돌려보낸다(5.3).

구글은 다른 곳만 보면 된다.

```java
        UriComponentsBuilder uri = UriComponentsBuilder.fromUriString("https://accounts.google.com/o/oauth2/v2/auth")
                .queryParam("response_type", "code")
                .queryParam("client_id", properties.clientId())
                .queryParam("redirect_uri", properties.redirectUri())
                .queryParam("scope", "openid")
                .queryParam("state", state)
                .queryParam("prompt", "select_account");
        if (reauth) {
            // 탈퇴 본인 확인: 이미 로그인해 있어도 다시 확인하게 한다(OpenID Connect max_age=0)
            uri.queryParam("max_age", "0");
        }
```

```java
        UserInfo user = restClient.get()
                .uri("https://openidconnect.googleapis.com/v1/userinfo")
                .header("Authorization", "Bearer " + token.access_token())
                .retrieve()
                .body(UserInfo.class);
        …
        return user.sub();
    …
    record UserInfo(String sub) {
    }
```

- `scope=openid`만: 로그인(OIDC)이지만 이메일·프로필은 받지 않는다(3.7).
- `prompt=select_account`: 늘 계정 고르는 화면을 보인다. 구글 계정이 여럿인 사람이 엉뚱한 계정으로 바로 들어가는 것을 막는다.
- `max_age=0`: 재인증(3.9).
- 구글은 토큰 교환에 `client_secret`이 늘 필요해 조건 없이 보낸다.

앱 키는 설정값이다.

```java
@ConfigurationProperties(prefix = "app.oauth")
public record OAuthProperties(Provider kakao, Provider google) {

    public record Provider(String clientId, String clientSecret, String redirectUri) {

        public boolean configured() {
            return clientId != null && !clientId.isBlank() && redirectUri != null && !redirectUri.isBlank();
        }

    }

}
```

- `application.yml`에는 빈 값만 두고, 진짜 값은 git에 올리지 않는 `config/application-dev.yml`(틀은 `.example`)이나 운영 환경 변수로 준다([02](./02-configuration-profiles.md)).
- 키가 비어 있으면 `configured()`가 false → `OAuthClients.configured(provider)`가 빈 값 → 버튼을 눌러도 `/login?error=OAUTH_UNAVAILABLE`("지금은 이 소셜 로그인을 쓸 수 없습니다")로 돌아온다. 키가 없는 개발 PC에서도 서버가 뜨고 나머지 기능은 그대로 쓴다.

### 5.2 흐름: `auth/application/SocialAuthService`

**시작**

```java
    public Optional<Start> start(SocialProvider provider, OAuthMode mode, String redirect, Long memberId,
                                 String origin) {
        return clients.configured(provider).map(client -> {
            String state = randomToken();
            Map<String, String> data = new HashMap<>();
            data.put("provider", provider.name());
            data.put("mode", mode.name());
            data.put("origin", origin);
            if (redirect != null) {
                data.put("redirect", redirect);
            }
            if (memberId != null) {
                data.put("memberId", memberId.toString());
            }
            put(STATE_PREFIX + state, data, STATE_TTL);
            return new Start(state, client.authorizeUrl(state, mode == OAuthMode.REAUTH));
        });
    }
```

- `randomToken()`: `SecureRandom` 32바이트(256비트)를 URL용 Base64로. 추측할 수 없어야 state가 의미 있다([60](./60-device-cookie-lockout.md) 3.3과 같은 이유).
- Redis 해시 하나에 이 흐름의 맥락을 담는다(4.2 표). `origin`은 컨트롤러가 만든 "지금 요청과 같은 프로토콜·포트의 플랫폼 주소"(예: `http://blog.test:8080`)다. 콜백(localhost)에서 이 값을 꺼내 어디로 돌려보낼지 안다.
- 돌려준 `Start.state`는 컨트롤러가 쿠키에 넣는다(5.4). Redis와 쿠키, 두 곳이다(4.2).

**콜백**

```java
    public Optional<String> callback(SocialProvider provider, String code, String state, String error) {
        Optional<Map<String, String>> found = take(STATE_PREFIX, state)
                .filter(data -> provider.name().equals(data.get("provider")));
        if (found.isEmpty()) {
            return Optional.empty();
        }
        Map<String, String> data = found.get();
        String origin = data.get("origin");
        OAuthMode mode = OAuthMode.valueOf(data.get("mode"));
        if (error != null || code == null || code.isBlank()) {
            return Optional.of(origin + failure(mode, "OAUTH_CANCELLED"));
        }
        String providerUserId;
        try {
            providerUserId = clients.configured(provider).orElseThrow().fetchUserId(code);
        } catch (RuntimeException e) {
            log.warn("{} 회원 번호를 받지 못했습니다: {}", provider, e.toString());
            return Optional.of(origin + failure(mode, "OAUTH_FAILED"));
        }
        String ticket = randomToken();
        Map<String, String> ticketData = new HashMap<>(data);
        ticketData.put("state", state);
        ticketData.put("providerUserId", providerUserId);
        put(TICKET_PREFIX + ticket, ticketData, TICKET_TTL);
        return Optional.of(origin + "/api/auth/oauth/complete?ticket=" + ticket);
    }
```

- `take`: state를 **읽고 지운다**. 한 번 쓴 state로 다시 오면(새로고침, 재전송) 없음 → 로그인 화면(3.8).
- `.filter(provider 같은가)`: 구글 흐름의 state를 카카오 콜백에 들고 와도 거절.
- `error`: 사용자가 제공사 화면에서 "취소"를 누르면 제공사가 `error=access_denied`를 붙여 돌려보낸다. 시작한 화면(로그인·마이페이지·탈퇴)에 "취소했습니다"를 보이게 돌려보낸다(`failure`).
- 토큰 교환 실패(네트워크, 잘못된 키, 만료된 code)는 서버 로그에 남기고 사용자에게는 `OAUTH_FAILED`만. 제공사의 오류 내용을 화면에 그대로 보이지 않는다.
- 표에는 state 데이터 전부 + **state 자신** + 회원 번호를 담는다. state 자신을 담는 이유는 complete에서 쿠키와 비교하려고(4.2).
- 여기서는 **로그인 쿠키를 주지 않는다**. 이 응답은 localhost에서 나가므로 줄 수 없다(3.6).

**끝내기**

```java
    public Completion complete(String ticket, String stateCookie, Long currentMemberId) {
        Optional<Map<String, String>> found = take(TICKET_PREFIX, ticket)
                .filter(data -> data.get("state").equals(stateCookie));
        if (found.isEmpty()) {
            return Completion.to("/login?error=OAUTH_FAILED");
        }
        Map<String, String> data = found.get();
        SocialProvider provider = SocialProvider.valueOf(data.get("provider"));
        String providerUserId = data.get("providerUserId");
        Long startedBy = Optional.ofNullable(data.get("memberId")).map(Long::valueOf).orElse(null);
        return switch (OAuthMode.valueOf(data.get("mode"))) {
            case LOGIN -> login(provider, providerUserId, data.get("redirect"));
            case LINK -> startedBy == null || !startedBy.equals(currentMemberId)
                    ? Completion.to(failure(OAuthMode.LINK, "OAUTH_FAILED"))
                    : link(startedBy, provider, providerUserId);
            case REAUTH -> startedBy == null || !startedBy.equals(currentMemberId)
                    ? Completion.to(failure(OAuthMode.REAUTH, "OAUTH_FAILED"))
                    : reauth(startedBy, provider, providerUserId);
        };
    }
```

- `data.get("state").equals(stateCookie)`: **로그인 CSRF를 막는 줄**이다(4.2). 쿠키가 없으면 `stateCookie`가 null이라 `equals`가 false.
- 표도 `take`라 한 번만. 표를 먼저 지우고 나서 쿠키를 비교하므로, 쿠키가 틀린 시도에도 표는 사라진다. 공격자가 같은 표로 여러 번 맞혀 볼 수 없다.
- `startedBy.equals(currentMemberId)`: 연동·재인증은 **시작한 회원과 끝내는 회원이 같아야** 한다(4.2 마지막 문단). 중간에 로그아웃하고 다른 계정으로 로그인했어도 거절된다.
- `switch`가 enum의 모든 값을 다루므로 `default`가 없다. 나중에 mode를 더하면 컴파일러가 빠진 곳을 알려 준다([16](./16-authorization-visibility.md) sealed·switch와 같은 생각).

**로그인 또는 가입 안내**

```java
    private Completion login(SocialProvider provider, String providerUserId, String redirect) {
        Optional<SocialAccount> account = socialAccountRepository.findByProviderAndProviderUserId(provider,
                providerUserId);
        if (account.isEmpty()) {
            String token = randomToken();
            put(SIGNUP_PREFIX + token, Map.of("provider", provider.name(), "providerUserId", providerUserId),
                    SIGNUP_TTL);
            return Completion.to("/signup/social?token=" + token + "&provider=" + provider.path());
        }
        Optional<Member> member = memberRepository.findById(account.get().getMemberId())
                .filter(found -> !found.isWithdrawn());
        if (member.isEmpty()) {
            return Completion.to("/login?error=OAUTH_FAILED");
        }
        if (member.get().isSuspendedAt(LocalDateTime.now(clock))) {
            return Completion.to(suspendedNotice(suspensionDetails.of(member.get())));
        }
        return new Completion(safeRedirect(redirect), member.get());
    }

    private static String suspendedNotice(SuspensionDetail detail) {
        StringBuilder location = new StringBuilder("/login?error=MEMBER_SUSPENDED");
        if (detail.reasonMessage() != null) {
            location.append("&reasonMessage=").append(URLEncoder.encode(detail.reasonMessage(), StandardCharsets.UTF_8));
        }
        if (detail.suspendedUntil() != null) {
            location.append("&until=").append(URLEncoder.encode(detail.suspendedUntil().toString(), StandardCharsets.UTF_8));
        }
        return location.toString();
    }
```

- **찾는 기준은 `(제공사, 제공사 회원 번호)`뿐**이다. 이메일은 어디에도 없다(3.7).
- 처음 보는 계정이면 **바로 회원을 만들지 않는다.** 가입 토큰(10분)을 만들고 닉네임 화면으로 보낸다. 주소에는 제공사 회원 번호가 아니라 **임의 토큰**만 나간다. 회원 번호를 주소에 넣으면 남이 그 번호로 가입을 끝낼 수 있다.
- 정지 회원은 로그인 쿠키 없이 로그인 화면으로. "모든 로그인 경로에서 상태를 먼저 본다"(R-07).
- **정지 안내를 이메일 로그인과 같게**: 이메일 로그인은 403 `MEMBER_SUSPENDED`의 JSON `detail`(사유 문장, 기한)로 로그인 화면에 정지 안내(`SuspensionNotice`)를 그린다([21](./21-signup-login.md) 5.4). 소셜 로그인은 JSON 응답이 아니라 302 이동이라 `detail`을 실을 곳이 없다. 그래서 같은 값을 만드는 `SuspensionDetails.of(member)`(필터·이메일 로그인과 같은 곳)로 사유·기한을 구해 **돌아가는 주소의 쿼리**에 붙인다(`reasonMessage`, `until`). 값이 없으면 그 칸은 빼고, 기한이 없으면 영구 정지다.
- `URLEncoder.encode`: 사유 문장의 한글·공백·`&` 같은 글자가 주소의 다른 칸을 깨뜨리지 않게 퍼센트 인코딩한다.
- 주소에 사유가 보이지만, 방금 그 소셜 계정으로 로그인한 **본인의 브라우저**에만 가는 주소라 이메일 로그인의 403 응답과 알려 주는 정보가 같다.
- 탈퇴 회원은 `social_account` 행이 지워져서(5.6) 보통 여기까지 오지 않는다. 혹시 남아 있으면 실패로 둔다.

**닉네임 확인 뒤 가입**

```java
    @Transactional
    public Member signup(String signupToken, String rawNickname) {
        Map<String, String> data = read(SIGNUP_PREFIX, signupToken)
                .orElseThrow(() -> new BusinessException(ErrorCode.SOCIAL_SIGNUP_EXPIRED));
        …
        if (memberRepository.existsByNickname(nickname)) {
            throw new BusinessException(ErrorCode.NICKNAME_TAKEN);
        }
        if (socialAccountRepository.findByProviderAndProviderUserId(provider, providerUserId).isPresent()) {
            throw new BusinessException(ErrorCode.SOCIAL_ALREADY_LINKED);
        }
        Member member;
        try {
            member = memberRepository.saveAndFlush(Member.ofSocial(nickname));
        } catch (DataIntegrityViolationException e) {
            throw new BusinessException(ErrorCode.NICKNAME_TAKEN);
        }
        try {
            socialAccountRepository.saveAndFlush(SocialAccount.link(member.getId(), provider, providerUserId));
        } catch (DataIntegrityViolationException e) {
            throw new BusinessException(ErrorCode.SOCIAL_ALREADY_LINKED);
        }
        redis.delete(SIGNUP_PREFIX + signupToken);
        return member;
    }
```

- `read`(지우지 않고 읽기): 닉네임이 겹쳐 409가 나면 사용자가 다른 닉네임으로 **같은 토큰을 다시** 써야 한다. 그래서 **성공한 뒤에만** 지운다.
- `Member.ofSocial(nickname)`: 이메일·비밀번호가 `null`인 회원(R-07).
- **회원과 연동을 한 트랜잭션**: 같은 토큰으로 두 탭에서 동시에 가입하면 둘 다 미리 확인을 통과할 수 있다. 그러면 두 번째의 `social_account` INSERT가 UNIQUE `(provider, provider_user_id)`에 걸린다. 예외로 트랜잭션이 되돌아가 **방금 만든 회원도 함께 사라진다.** 연동 없는 빈 회원이 남지 않는다. "확인 → 저장 사이의 경쟁은 UNIQUE가 마지막으로 막는다"([21](./21-signup-login.md) 3.4, [23](./23-transactions-locking.md))와 같은 생각이다.
- `saveAndFlush`: INSERT를 **지금** 보내야 UNIQUE 위반이 이 `try` 안에서 잡힌다. `save`만 하면 INSERT가 커밋 때로 미뤄져 예외가 엉뚱한 곳(트랜잭션 끝)에서 난다.

**연동**

```java
    private Completion link(Long memberId, SocialProvider provider, String providerUserId) {
        Optional<SocialAccount> owner = socialAccountRepository.findByProviderAndProviderUserId(provider,
                providerUserId);
        if (owner.isPresent()) {
            return Completion.to(owner.get().getMemberId().equals(memberId)
                    ? "/me?linked=" + provider.path()
                    : failure(OAuthMode.LINK, ErrorCode.SOCIAL_ALREADY_LINKED.name()));
        }
        if (socialAccountRepository.findByMemberIdAndProvider(memberId, provider).isPresent()) {
            return Completion.to(failure(OAuthMode.LINK, ErrorCode.PROVIDER_ALREADY_LINKED.name()));
        }
        try {
            socialAccountRepository.saveAndFlush(SocialAccount.link(memberId, provider, providerUserId));
        } catch (DataIntegrityViolationException e) {
            // 확인과 저장 사이에 같은 계정·같은 제공사가 먼저 연결됐다
            …
        }
        return Completion.to("/me?linked=" + provider.path());
    }
```

R-07의 두 거절이 DB의 두 UNIQUE와 하나씩 짝이다.

| 규칙 | 미리 확인 | 마지막으로 막는 것 | 화면 |
| --- | --- | --- | --- |
| 소셜 계정 하나는 회원 하나에만 | `findByProviderAndProviderUserId` | `UNIQUE (provider, provider_user_id)` | `SOCIAL_ALREADY_LINKED` "이미 다른 계정에 연결된 소셜 계정입니다." |
| 회원은 제공사마다 하나 | `findByMemberIdAndProvider` | `UNIQUE (member_id, provider)` | `PROVIDER_ALREADY_LINKED` |

- 이미 **내** 계정에 연결된 것이면 성공으로 본다(같은 일을 두 번 해도 결과가 같게, [17](./17-idempotency-redis.md)).
- 이 메서드에는 `@Transactional`이 없다. 저장이 실패하면 예외를 던지는 대신 **오류 주소로 돌려보내야** 하는데, 트랜잭션 안에서 UNIQUE 위반이 나면 그 트랜잭션은 되돌릴 수밖에 없게 표시된다. 그래서 저장 하나가 저마다의 트랜잭션(`saveAndFlush`가 Spring Data 기본 트랜잭션)으로 돈다.

**해제: 마지막 로그인 수단 지키기**

```java
    @Transactional
    public void unlink(Long memberId, SocialProvider provider) {
        Member member = memberRepository.findByIdForUpdate(memberId)
                .orElseThrow(() -> new BusinessException(ErrorCode.UNAUTHORIZED));
        Optional<SocialAccount> account = socialAccountRepository.findByMemberIdAndProvider(memberId, provider);
        if (account.isEmpty()) {
            return;
        }
        boolean otherMethodLeft = credentialService.hasPassword(member)
                || socialAccountRepository.countByMemberId(memberId) > 1;
        if (!otherMethodLeft) {
            throw new BusinessException(ErrorCode.LAST_LOGIN_METHOD);
        }
        socialAccountRepository.delete(account.get());
    }
```

- "해제해도 다른 수단이 남나" = 비밀번호가 있거나, 소셜이 2개 이상.
- **`findByIdForUpdate`(회원 행 `SELECT … FOR UPDATE`)가 왜 필요한가**: 카카오·구글이 둘 다 연결된 소셜 회원이 두 탭에서 동시에 둘을 해제한다고 하자. 잠금이 없으면 두 요청이 모두 "지금 2개 → 1개는 남는다"를 보고 둘 다 지운다. 로그인 수단이 0개인 회원, 영영 못 들어오는 계정이 생긴다. 회원 행을 먼저 잠그면 두 번째 요청은 첫 번째가 커밋할 때까지 기다린다.
- 기다린 뒤 두 번째 요청이 세면 1개로 보인다. InnoDB의 REPEATABLE READ에서 일반 SELECT가 보는 스냅숏은 그 트랜잭션의 **첫 일반 읽기** 때 만들어진다. 이 메서드의 첫 문장이 잠금 읽기(`FOR UPDATE`)라, 일반 읽기(`findByMemberIdAndProvider`, `countByMemberId`)는 잠금을 얻은 **뒤**에 스냅숏을 만들고 먼저 끝난 해제를 본다. "잠금을 첫 문장으로"([33](./33-isolation-deadlock.md), [34](./34-view-count.md))가 여기서도 쓰였다.
- 연결되지 않은 제공사를 해제하면 할 일이 없어 그대로 204다(멱등한 DELETE).

**재인증**

```java
    private Completion reauth(Long memberId, SocialProvider provider, String providerUserId) {
        boolean mine = socialAccountRepository.findByProviderAndProviderUserId(provider, providerUserId)
                .filter(account -> account.getMemberId().equals(memberId))
                .isPresent();
        if (!mine) {
            return Completion.to(failure(OAuthMode.REAUTH, "REAUTH_FAILED"));
        }
        credentialService.markSocialReauthenticated(memberId);
        return Completion.to("/me/withdraw?reauth=ok");
    }
```

- "아무 카카오로 다시 로그인"이 아니라 **이 회원에 연결된 그 카카오 계정**이어야 한다. 다른 사람 카카오로 로그인하면 `REAUTH_FAILED`.
- 확인 표시는 인증의 입구 `CredentialService`가 남긴다(5.5). 회원 기능(탈퇴)은 그 입구만 부른다([55](./55-module-boundary-archunit.md)).

**돌아갈 곳: 열린 리다이렉트 막기**

```java
    private String safeRedirect(String redirect) {
        if (redirect == null || redirect.isBlank()) {
            return "/";
        }
        if (redirect.startsWith("/") && !redirect.startsWith("//") && !redirect.startsWith("/\\")) {
            return redirect;
        }
        try {
            URI uri = URI.create(redirect);
            boolean web = "http".equals(uri.getScheme()) || "https".equals(uri.getScheme());
            if (web && uri.getHost() != null && !(hostResolver.resolve(uri.getHost()) instanceof RequestHost.Unknown)) {
                return redirect;
            }
        } catch (IllegalArgumentException e) {
            // 주소 모양이 아니면 홈으로
        }
        return "/";
    }
```

- 로그인 전 보던 글(예: `http://alpha.blog.test/12`)로 돌아가야 해서 `redirect`를 받는다. 이것을 검사 없이 쓰면 `redirect=https://evil.example/가짜-로그인`을 붙인 진짜 우리 로그인 링크가 피싱에 쓰인다(열린 리다이렉트, [21](./21-signup-login.md) 3.5).
- `/feed` 같은 우리 경로는 된다. 그러나 `//evil.example`은 브라우저가 "같은 프로토콜의 `evil.example`"로 읽고, `/\evil.example`도 일부 브라우저가 `\`를 `/`로 바꿔 같은 뜻이 된다. 그래서 둘을 뺀다.
- 절대 주소는 `http`·`https`이고, 호스트가 **우리 플랫폼이나 블로그 주소**로 해석될 때만([15](./15-subdomain-host-routing.md)의 `BlogHostResolver`). `javascript:` 같은 다른 scheme은 안 된다.
- 프론트에도 같은 검사(`app/host.ts`의 `safeRedirect`)가 있지만, 이 302는 서버가 내므로 서버가 다시 검사한다. 화면 검사는 안내일 뿐이다(헌법 IV).

**한 번만 쓰기**

```java
    private void put(String key, Map<String, String> data, Duration ttl) {
        redis.opsForHash().putAll(key, data);
        redis.expire(key, ttl);
    }

    /** 읽고 지운다. 동시에 두 번 와도 지우기에 성공한 한 번만 쓴다. */
    private Optional<Map<String, String>> take(String prefix, String token) {
        return read(prefix, token).filter(data -> Boolean.TRUE.equals(redis.delete(prefix + token)));
    }
```

- `opsForHash().putAll`: Redis 해시(`HSET` 여러 칸)에 맥락을 한 번에. `expire`로 수명.
- `take`: 3.8의 "지우기에 성공한 쪽만". `redis.delete(key)`는 지웠으면 `true`, 이미 없었으면 `false`다.

### 5.3 주소: `auth/presentation/OAuthController`

```java
    @GetMapping("/api/auth/oauth/{provider}/authorize")
    public ResponseEntity<Void> authorize(@PathVariable String provider, @RequestParam(required = false) String mode,
                                          @RequestParam(required = false) String redirect,
                                          HttpServletRequest request, HttpServletResponse response) {
        SocialProvider socialProvider = provider(provider);
        OAuthMode oauthMode = OAuthMode.fromParam(mode);
        Long memberId = LoginMembers.currentId();
        String origin = hostResolver.platformUrl(request, "");
        if (oauthMode != OAuthMode.LOGIN && memberId == null) {
            String back = oauthMode == OAuthMode.LINK ? "/me" : "/me/withdraw";
            return found(origin + "/login?redirect=" + URLEncoder.encode(back, StandardCharsets.UTF_8));
        }
        return socialAuthService.start(socialProvider, oauthMode, redirect, memberId, origin)
                .map(start -> {
                    cookieManager.issueOAuthState(response, start.state(), SocialAuthService.STATE_TTL);
                    return found(start.providerUrl());
                })
                .orElseGet(() -> found(origin + SocialAuthService.failure(oauthMode, "OAUTH_UNAVAILABLE")));
    }
```

- 이 세 GET(authorize·callback·complete)은 **브라우저가 주소를 직접 여는** 화면 이동이라 JSON 대신 **302**로 답한다. 프론트의 버튼도 `fetch`가 아니라 `<a href>`다(5.7). `fetch`로는 다른 사이트(카카오) 로그인 화면으로 옮겨 갈 수 없다.
- `platformUrl(request, "")`: 지금 요청과 같은 프로토콜·포트로 만든 플랫폼 주소. 8080에서 시작하면 `http://blog.test:8080`, 8081에서 시작하면 `…:8081`로 돌아온다.
- 연동·재인증은 로그인한 회원만. 비회원이 열면 로그인 화면으로 보내고, 로그인 뒤 돌아올 곳(`/me`, `/me/withdraw`)을 붙인다.
- 모르는 제공사(`naver`)는 404(`provider()`가 `NOT_FOUND`).

```java
    @GetMapping("/api/auth/oauth/complete")
    public ResponseEntity<Void> complete(@RequestParam(required = false) String ticket, HttpServletRequest request,
                                         HttpServletResponse response) {
        String stateCookie = cookieManager.readCookie(request, AuthCookieManager.OAUTH_STATE_COOKIE).orElse(null);
        cookieManager.clearOAuthState(response);
        SocialAuthService.Completion completion = socialAuthService.complete(ticket, stateCookie,
                LoginMembers.currentId());
        if (completion.login() != null) {
            cookieManager.login(response, completion.login(), false);
        }
        return found(completion.location());
    }
```

- 쿠키를 읽고 **바로 지운다**(`Max-Age=0`). 성공이든 실패든 이 흐름의 state는 끝났다.
- 쿠키 다루기는 presentation(`AuthCookieManager`), 판단은 application(`SocialAuthService`)이다. 서비스는 문자열 하나(`stateCookie`)만 받는다([24](./24-layered-architecture-dto.md)).
- 로그인이면 일반 로그인과 같은 로그인 쿠키(로그인 유지는 고르지 않은 상태). 소셜 로그인 화면에는 "로그인 상태 유지" 칸이 없어서다.

### 5.4 state 쿠키: `AuthCookieManager.issueOAuthState`

```java
    public void issueOAuthState(HttpServletResponse response, String state, Duration maxAge) {
        response.addHeader(HttpHeaders.SET_COOKIE, oauthStateCookie(state, maxAge));
    }

    public void clearOAuthState(HttpServletResponse response) {
        response.addHeader(HttpHeaders.SET_COOKIE, oauthStateCookie("", Duration.ZERO));
    }

    private String oauthStateCookie(String value, Duration maxAge) {
        return ResponseCookie.from(OAUTH_STATE_COOKIE, value)
                .path(OAUTH_PATH)
                .httpOnly(true)
                .secure(authProperties.cookieSecure())
                .sameSite("Lax")
                .maxAge(maxAge)
                .build()
                .toString();
    }
```

- 로그인 쿠키용 `addCookie`(Domain=`.blog.test`, Path=`/`)를 쓰지 않고 따로 만들었다. **Domain을 넣지 않아** 시작한 플랫폼 호스트에만 저장되고, Path가 `/api/auth/oauth`라 이 아래 요청에만 따라간다(4.3).
- 지우기는 같은 이름·같은 Path로 `Max-Age=0`을 다시 보내는 것이다. Path가 다르면 브라우저는 다른 쿠키로 보고 지우지 않는다([10](./10-http-cookies.md)).

### 5.5 탈퇴 본인 확인: `CredentialService`

```java
    public void verifyForWithdrawal(Member member, String password) {
        if (password != null && !password.isEmpty()) {
            verifyCurrentPassword(member, password, () -> new BusinessException(ErrorCode.LOGIN_FAILED));
            return;
        }
        if (!Boolean.TRUE.equals(redis.delete(REAUTH_PREFIX + member.getId()))) {
            throw new BusinessException(ErrorCode.LOGIN_FAILED);
        }
    }

    /** 연결된 소셜 계정으로 다시 로그인했다(SocialAuthService의 reauth). 10분 안에 탈퇴하면 비밀번호 대신 쓴다. */
    void markSocialReauthenticated(Long memberId) {
        redis.opsForValue().set(REAUTH_PREFIX + memberId, "1", REAUTH_TTL);
    }
```

- 비밀번호를 보냈으면 비밀번호로(스텝 19b와 같고, 같은 시도 횟수 제한).
- 비워 보냈으면(`DELETE /api/me {}`) 재인증 표시를 **지워 본다**. 지우기에 성공(=10분 안에 재인증했고 아직 안 씀)해야 통과. 읽고 지우기를 따로 하지 않고 `DEL` 한 번으로 "있었나 + 한 번만"을 같이 본다(3.8).
- `markSocialReauthenticated`는 `public`이 아니다. 같은 패키지(`auth/application`)의 `SocialAuthService`만 부를 수 있다. 회원 기능이 "재인증했다고 치기"를 부를 길이 없다([55](./55-module-boundary-archunit.md)).
- 이메일 회원도 소셜을 연동했으면 이 길로 탈퇴할 수 있다(테스트 `reauthMarkIsUsedOnce`).

### 5.6 탈퇴와 소셜 연동: `MemberTraceCleaner`, `MeResponse`

탈퇴하면 `MemberTraceCleaner`가 `DELETE FROM social_account WHERE member_id = ?`로 연동 행을 지운다. 그래서 같은 카카오 계정으로 다시 오면 **처음 보는 계정**이 되어 새로 가입할 수 있다(테스트 `socialOnlyMemberWithdrawsAfterReauthAndTheAccountCanSignUpAgain`). 카카오 쪽의 "앱 연결 끊기"(카카오 unlink, 구글 토큰 철회)는 하지 않는다(2026-10-12 지원 결정, research R-07 구현 메모). 그 사람의 카카오 계정 설정 "연결된 서비스"에는 남아 있어 본인이 거기서 끊는다. 카카오 unlink는 모든 사용자를 다룰 수 있는 어드민 키가 필요해 공용 서버에 두기 위험하고, 구글은 토큰을 저장하지 않아서다.

마이페이지는 `GET /api/me`의 `socialAccounts`로 연결 상태를 그린다.

```java
                result.socialAccounts().stream()
                        .map(account -> new SocialAccount(account.provider(), DateTimes.toOffset(account.linkedAt())))
                        .toList(),
```

- `linkedAt`은 `social_account.created_at`(연동한 때)이다. 소셜로 가입한 회원은 `email`이 `null`, `hasPassword`가 `false`다. 화면은 `hasPassword`로 "비밀번호 칸"과 "소셜로 본인 확인" 버튼 중 무엇을 보일지 정한다.

### 5.7 화면: `app/social.ts`, `LoginPage`, `SignupSocialPage`, `MyPage`, `WithdrawPage`

```ts
export function socialAuthorizeUrl(provider: SocialPath, mode: SocialMode, redirect?: string | null): string {
  const params = new URLSearchParams({ mode })
  if (redirect) {
    params.set('redirect', redirect)
  }
  return `/api/auth/oauth/${provider}/authorize?${params.toString()}`
}
```

- 버튼은 이 주소의 `<a href>`다. Thymeleaf로 치면 `th:href`로 서버 주소에 링크를 건 것과 같다. 누르면 **페이지가 통째로** 서버로 이동하고, 서버의 302를 따라 카카오 화면으로 간다.
- 끝나면 서버가 `?error=…`, `?linked=…`, `?reauth=ok`를 붙여 화면으로 돌려보낸다. 화면은 이것을 읽어 문장을 보인다(`socialErrorMessage`). 서버가 오류를 JSON이 아니라 **주소로** 전하는 이유는 이 응답이 `fetch`가 아니라 페이지 이동이기 때문이다.
- `LoginPage`: "카카오로 계속하기"·"구글로 계속하기". 로그인 화면의 `redirect`를 그대로 넘겨, 소셜 로그인 뒤에도 보던 곳으로 돌아간다. 정지로 돌아왔으면 주소의 값으로 이메일 로그인과 같은 정지 안내를 처음부터 그린다.

```tsx
  // 소셜 로그인한 계정이 정지 중이면 서버가 사유·기한을 붙여 돌려보낸다(이메일 로그인과 같은 안내)
  const [suspension, setSuspension] = useState<SuspensionDetail | null>(params.get('error') === 'MEMBER_SUSPENDED'
    ? { reason: null, reasonMessage: params.get('reasonMessage'), suspendedUntil: params.get('until') }
    : null)
```

  `useState`의 처음 값을 주소에서 만든다. 이메일 로그인이 403을 받았을 때 `setSuspension(caught.detail)`로 넣는 것과 **같은 모양**(`SuspensionDetail`)이라, 같은 `SuspensionNotice` 부품이 그대로 그린다. 이때 `error` 상태는 비워 둬 "로그인에 실패했습니다" 같은 문장이 겹치지 않게 한다.
- `SignupSocialPage`(`/signup/social?token=…&provider=…`): 닉네임 확인. `SOCIAL_SIGNUP_EXPIRED`면 "가입 시간이 지났습니다"와 "카카오로 다시 시작" 버튼.
- `MyPage`의 소셜 계정 연동: 제공사마다 "연결됨 날짜 / 해제" 또는 "연결 안 됨 / 연결". `LAST_LOGIN_METHOD`면 "로그인 수단이 하나도 남지 않아 해제할 수 없습니다."
- `WithdrawPage`: 비밀번호가 없는 회원에게 연결된 제공사의 "카카오로 본인 확인" 버튼. `?reauth=ok`로 돌아오면 "10분 안에 탈퇴해 주세요"와 함께 탈퇴 버튼이 열리고 `{}`를 보낸다. 10분이 지나 401이면 다시 확인하라고 안내한다.

### 5.8 테스트: `FakeOAuthClients`, `SocialLoginIntegrationTest`

테스트에서 진짜 카카오에 갈 수는 없다. `OAuthClients`를 상속한 가짜를 `@Primary`로 둔다.

```java
@Component
@Primary
public class FakeOAuthClients extends OAuthClients {

    public FakeOAuthClients() {
        super(Arrays.stream(SocialProvider.values()).<OAuthClient>map(FakeClient::new).toList());
    }

    record FakeClient(SocialProvider provider) implements OAuthClient {
        …
        @Override
        public String fetchUserId(String code) {
            if (code.startsWith("fail")) {
                throw new IllegalStateException("토큰 교환 실패");
            }
            return code;
        }
    }
}
```

- `@Primary`: 같은 타입의 빈이 둘(진짜 `OAuthClients`, 가짜)이면 이것을 주입한다. 테스트 소스에만 있어 운영에는 없다.
- **code가 곧 회원 번호**라서, 테스트가 콜백에 `code=abc`를 주면 "제공사 회원 abc"로 로그인한 셈이 된다. 앱 키도 늘 "설정됨"이다.
- 그 위의 흐름(state, 쿠키, 표, 가입, 연동, 잠금)은 모두 **진짜 코드**로 돈다. 제공사와 이야기하는 부분만 가짜다.

`flow(...)` 도우미가 authorize → callback → complete 한 바퀴를 돈다. 주요 시험:

| 테스트 | 확인하는 것 |
| --- | --- |
| `firstSocialLoginAsksNicknameThenSignsUpAndNextTimeLogsIn` | 처음 → 닉네임 화면, 가입(이메일 없음, `hasPassword=false`), 같은 토큰 두 번째는 `SOCIAL_SIGNUP_EXPIRED`, 다음부터는 바로 로그인하고 블로그 주소로 돌아감 |
| `stateMustComeFromThisBrowserAndBeUsedOnce` | **state 쿠키 없이 complete → 로그인 안 됨**(로그인 CSRF), 같은 state 두 번, 모르는 state, 다른 제공사의 state 모두 실패 |
| `onlyOurAddressesAreAllowedAsRedirect` | `https://evil.example/steal`, `//evil.example` → `/`, `/feed`는 그대로 |
| `suspendedMemberIsSentToLoginWithNotice` | 정지 회원은 로그인 쿠키 없이 `/login?error=MEMBER_SUSPENDED&until=…`(사유 기록이 없는 테스트 데이터라 `reasonMessage`는 없음) |
| `linkAddsAnotherProviderAndRejectsTakenOrDuplicateProvider` | 연동, 같은 제공사 하나 더 → `PROVIDER_ALREADY_LINKED`, 남의 것 → `SOCIAL_ALREADY_LINKED`, 연동한 구글로 로그인하면 그 회원 |
| `lastLoginMethodCannotBeUnlinked` | 이메일 회원은 소셜을 다 해제 가능, 소셜 회원의 마지막 하나는 409, 없는 연결 해제는 204, `naver`는 404 |
| `socialOnlyMemberWithdrawsAfterReauthAndTheAccountCanSignUpAgain` | 재인증 전 `{}` 탈퇴 401, 남의 카카오로 재인증 → `REAUTH_FAILED`, 재인증 주소에 reauth 표시, 탈퇴 뒤 같은 카카오는 새 가입 |
| `reauthMarkIsUsedOnce` | 이메일 회원도 소셜 재인증으로 탈퇴, 틀린 비밀번호를 보내면 비밀번호로 판단(401) |

## 6. 자주 하는 실수와 함정

- **state를 안 쓰거나, 쓰기만 하고 브라우저와 묶지 않음**: Redis에 "있는 값인가"만 보면 공격자가 자기 흐름의 콜백 주소를 피해자에게 열게 하는 로그인 CSRF가 그대로 된다. 시작한 브라우저와 맞춰 봐야 한다(4.2).
- **state를 여러 번 쓸 수 있게 둠**: 새로고침·재전송으로 같은 흐름이 두 번 끝난다. 읽고 지우기, 지우기에 성공한 한 번만(3.8).
- **state 쿠키를 `SameSite=Strict`로**: 제공사·localhost에서 오는 이동에 쿠키가 실리지 않아 모든 소셜 로그인이 실패한다. `Lax`(4.3).
- **콜백 응답에서 `.blog.test` 쿠키를 주려 함**: 콜백이 localhost면 브라우저가 버린다. 로그인은 된 것 같은데 쿠키가 없다(3.6).
- **클라이언트 시크릿을 프론트 코드에**: 빌드된 자바스크립트는 누구나 읽는다. 토큰 교환은 서버에서만.
- **리다이렉트 URI가 콘솔과 한 글자 다름**: `localhost`와 `127.0.0.1`, 끝의 `/`, 포트, `http`와 `https`. 제공사가 `redirect_uri_mismatch` 같은 오류 화면을 보인다.
- **이메일로 회원 찾기·합치기**: 남의 이메일로 만든 소셜 계정이 그 회원 계정을 연다(3.7). 찾는 기준은 `(제공사, 제공사 회원 번호)`뿐.
- **제공사 회원 번호를 주소에 넣어 가입 화면으로**: 남이 번호를 바꿔 다른 사람 소셜 계정으로 가입을 끝낼 수 있다. 서버에 둔 임의 토큰만 주소에.
- **처음 보는 계정을 바로 회원으로 만들고 닉네임은 나중에**: 닉네임 없는 회원, 중복 닉네임 처리 등이 흩어진다. 이 프로젝트는 닉네임을 받은 뒤 회원과 연동을 한 트랜잭션으로.
- **해제할 때 세고 지우기를 잠금 없이**: 동시에 두 개를 해제하면 로그인 수단이 0개인 회원이 생긴다. 회원 행을 먼저 잠근다.
- **재인증을 "아무 소셜 로그인"으로 인정**: 남의 카카오로 다시 로그인해도 통과하면 의미가 없다. 그 회원에 연결된 계정인지 본다. 또 이미 제공사에 로그인해 있으면 묻지 않고 넘어가므로 `prompt=login`·`max_age=0`.
- **구글에 `prompt=login`**: 구글은 `login`을 받지 않는다. `max_age=0`.
- **`redirect`를 검사 없이 302**: 열린 리다이렉트. 우리 경로(단, `//`·`/\` 제외)와 우리 호스트만.
- **배포 환경의 제약을 확인하지 않고 단정함**: 이 프로젝트는 2026-10-12에 "학교 nginx는 http뿐"이라고 보고 구글 로그인을 뺐다. 근거는 nginx 안내문 예시가 `listen 80`만 있다는 것뿐이었고, 다음 날 `curl -v https://now-log.java21.net`으로 보니 Let's Encrypt 인증서로 https가 열려 있었다. 기능을 빼기 전에 한 줄 명령으로 확인한다(7.6).
- **제공사 오류를 화면에 그대로**: 토큰 교환 실패 내용에는 설정·키 이야기가 섞일 수 있다. 로그에만 남기고 화면에는 `OAUTH_FAILED`.

이 프로젝트에 남은 것:

- **PKCE를 쓰지 않는다.** PKCE는 시작할 때 만든 비밀(code_verifier)의 해시를 authorize에 보내고, 토큰 교환 때 원래 값을 보내 "code를 요청한 쪽과 바꾸는 쪽이 같은가"를 제공사가 확인하는 장치다. 원래 공개 클라이언트용이지만, OAuth 보안 모범 사례(RFC 9700)는 기밀 클라이언트에도 권한다. 이 프로젝트는 클라이언트 시크릿과 state(브라우저에 묶음)로 막고 있고, 더하려면 state 데이터에 code_verifier를 함께 두면 된다.
- **구글 재인증의 `auth_time`을 확인하지 않는다.** `max_age=0`은 "다시 로그인시켜 달라"는 요청이고, 실제로 다시 로그인했는지는 ID 토큰의 `auth_time`으로 확인하라고 OIDC가 권한다. 이 프로젝트는 ID 토큰을 읽지 않는다.
- **Redis `put`이 두 명령이다**(`HSET` 뒤 `EXPIRE`). 사이에서 서버가 죽으면 수명 없는 키가 남을 수 있다. 값은 무작위 키라 다시 쓰일 일은 없지만 메모리에 남는다.
- **제공사 쪽 연결 끊기를 하지 않는다**(5.6).
- **진짜 제공사로는 운영에서 확인했다.** 카카오와, 같은 날 되살린 구글(7.6) 모두 2026-10-13 운영(`https://now-log.java21.net`)에서 지원이 로그인까지 확인했다.

## 7. 직접 해 보기

### 7.1 키 없이 흐름 보기

키가 없으면 버튼을 눌러도 "지금은 이 소셜 로그인을 쓸 수 없습니다"로 돌아온다.

```bash
curl -si 'http://blog.test:8080/api/auth/oauth/kakao/authorize?mode=login' | grep -i '^location'
# Location: http://blog.test:8080/login?error=OAUTH_UNAVAILABLE
```

### 7.2 가짜 키로 authorize만 보기

`config/application-dev.yml`의 카카오 `client-id`에 아무 글자(예: `dummy`)를 넣고 서버를 다시 띄운 뒤:

```bash
curl -si 'http://blog.test:8080/api/auth/oauth/kakao/authorize?mode=login' | grep -iE '^(location|set-cookie)'
```

- `Location: https://kauth.kakao.com/oauth/authorize?response_type=code&client_id=dummy&redirect_uri=http://localhost:8080/api/auth/oauth/kakao/callback&state=…`
- `Set-Cookie: oauth_state=…; Path=/api/auth/oauth; Max-Age=600; …; HttpOnly; SameSite=Lax`

`Location`의 state와 쿠키의 값이 같은지 본다. Redis에서도 본다.

```bash
docker compose exec redis redis-cli --scan --pattern 'oauth:*'
docker compose exec redis redis-cli HGETALL 'oauth:state:{위의 state}'
docker compose exec redis redis-cli TTL 'oauth:state:{위의 state}'
```

`provider`, `mode`, `origin`이 보이고 TTL은 600 아래로 줄어든다. 같은 state로 콜백을 두 번 불러 보면 두 번째는 `/login?error=OAUTH_FAILED`다.

```bash
curl -si 'http://localhost:8080/api/auth/oauth/kakao/callback?state={state}&error=access_denied' | grep -i '^location'  # 취소
curl -si 'http://localhost:8080/api/auth/oauth/kakao/callback?state={state}&error=access_denied' | grep -i '^location'  # 이미 씀
```

### 7.3 진짜 카카오·구글로 (키를 받은 뒤)

1. **카카오 developers** → 내 애플리케이션 → 앱 만들기 → 앱 키의 **REST API 키**(= `client-id`). 보안에서 클라이언트 시크릿을 켜면 그 값(= `client-secret`). 카카오 로그인 활성화, **Redirect URI**에 `http://localhost:8080/api/auth/oauth/kakao/callback` 등록. 동의 항목은 켜지 않는다.
2. **Google Cloud 콘솔** → API 및 서비스 → OAuth 동의 화면(테스트 사용자에 내 구글 계정) → 사용자 인증 정보 → OAuth 2.0 클라이언트 ID(웹 애플리케이션) → **승인된 리디렉션 URI**에 `http://localhost:8080/api/auth/oauth/google/callback`. 클라이언트 ID·보안 비밀을 받는다.
3. `cp config/application-dev.yml.example config/application-dev.yml`(없으면) → `app.oauth.kakao`·`google`의 `client-id`, `client-secret`을 채운다. `redirect-uri`는 1·2에 등록한 것과 글자까지 같게. 이 파일은 git에 올라가지 않는다. 키를 대화창·PR에 붙이지 않는다.
4. 서버를 다시 띄우고 `http://blog.test:8080/login` → "카카오로 계속하기" → 카카오 로그인 → 처음이면 닉네임 화면 → 가입 → 블로그 개설 안내.
5. 개발자 도구 Network 탭에서 `authorize`(302) → 카카오 → `callback`(localhost, 302) → `complete`(blog.test, 302, `Set-Cookie: access_token…`) 순서를 본다. `callback` 응답에는 로그인 쿠키가 없고 `complete`에만 있다(3.6).
6. 로그아웃 → 다시 "카카오로 계속하기" → 이번엔 바로 로그인.
7. 이메일 회원으로 로그인 → 마이페이지 → 소셜 계정 연동 → 구글 "연결" → "구글 계정을 연결했습니다." → 해제.
8. 소셜 회원으로 → 마이페이지 → 회원 탈퇴 → "카카오로 본인 확인" → 카카오가 이미 로그인 상태여도 **다시 로그인 화면**이 나오는지(`prompt=login`), 구글은 다시 로그인하라는지(`max_age=0`) 본다.

### 7.6 운영(https)에 올릴 때

운영 주소가 https인지 먼저 확인한다. 인증서가 있으면 `SSL certificate verify ok`와 인증서 이름이 나온다.

```bash
curl -sv https://now-log.java21.net/ 2>&1 | grep -E 'Connected|subject|issuer|verify'
# * Connected to now-log.java21.net (…) port 443
# *  subject: CN=now-log.java21.net
# *  issuer: C=US; O=Let's Encrypt; CN=…
# *  SSL certificate verify ok.
```

https가 되면 운영 설정(`application-prod.yml`)은 이렇게 둔다.

| 설정 | 값 | 이유 |
|---|---|---|
| `app.oauth.kakao.redirect-uri` | `https://now-log.java21.net/api/auth/oauth/kakao/callback` | 카카오는 http도 받지만, http 콜백이면 인가 코드와 쿠키가 첫 요청 한 번은 암호화 없이 지나간다 |
| `app.oauth.google.redirect-uri` | `https://now-log.java21.net/api/auth/oauth/google/callback` | 구글은 https만 받는다(localhost만 예외, 3.3) |
| `app.auth.cookie-secure` | `true` | 로그인 쿠키가 http 요청에 실리지 않는다 |

콘솔 등록은 **배포보다 먼저** 한다. 배포된 서버가 보내는 `redirect_uri`가 콘솔에 없으면 제공사가 오류 화면을 보인다.

1. 카카오 developers → 카카오 로그인 → Redirect URI에 https 주소를 **더한다**(옛 http 주소는 배포가 끝나고 확인한 뒤 지운다).
2. Google Cloud 콘솔 → 사용자 인증 정보 → OAuth 클라이언트 → 승인된 리디렉션 URI에 https 주소를 더한다. OAuth 동의 화면의 승인된 도메인에 `java21.net`. 동의 화면이 "테스트" 상태면 테스트 사용자로 넣은 계정만 로그인할 수 있으니, 누구나 쓰게 하려면 "프로덕션으로 게시"한다(이름·회원 번호만 받는 기본 범위라 심사 대상이 아니다).
3. GitHub secrets에 `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`. 워크플로가 서버로 넘기고, 비어 있으면 구글 버튼만 "지금은 쓸 수 없습니다"가 된다.

### 7.4 공격 흉내: 로그인 CSRF

7.3의 상태에서 브라우저 A로 authorize를 시작하고, 카카오에서 돌아오는 `callback?code=…&state=…` 주소를 Network 탭에서 복사한다(따라가기 전에 멈추려면 "Preserve log"를 켜고 바로 뒤로 가기). 그 주소를 **다른 브라우저 B**에서 연다. B는 `/login?error=OAUTH_FAILED`로 가고 로그인되지 않아야 한다. B에는 `oauth_state` 쿠키가 없어서다.

### 7.5 테스트

```bash
./mvnw test -Dtest=SocialLoginIntegrationTest
cd frontend && npx vitest run src/app/social.test.ts
```

공부용 브랜치에서 `SocialAuthService.complete`의 `.filter(data -> data.get("state").equals(stateCookie))`를 지우고 돌려 보면, `stateMustComeFromThisBrowserAndBeUsedOnce`가 "쿠키 없이도 로그인됨"으로 실패한다. 이 한 줄이 로그인 CSRF를 막는 줄임을 확인할 수 있다.

## 8. 확인 문제

1. 인가 코드 흐름에서 제공사가 브라우저에 토큰을 바로 주지 않고 code를 주는 이유는?
<details><summary>답</summary>브라우저를 오가는 주소는 기록·로그·Referer 등 여러 곳에 남는다. 그 길에는 혼자서는 쓸모없는 짧은 일회용 code만 지나가게 하고, 진짜 토큰은 서버가 클라이언트 시크릿과 함께 서버끼리 바꿔 받는다. code를 훔쳐도 시크릿이 없으면 토큰으로 바꿀 수 없다.</details>

2. 리다이렉트 URI를 제공사 콘솔에 미리 등록하게 하는 이유는?
<details><summary>답</summary>등록이 없으면 공격자가 authorize 주소의 redirect_uri를 자기 서버로 바꿔 피해자의 code를 받아 갈 수 있다. 제공사는 등록한 주소와 글자까지 같을 때만 돌려보낸다.</details>

3. 로그인 CSRF란 무엇이고, state를 Redis에만 두면 왜 막지 못하나?
<details><summary>답</summary>공격자가 자기 계정으로 로그인한 흐름의 콜백 주소(자기 code·state)를 피해자에게 열게 해 피해자를 공격자 계정으로 로그인시키는 공격이다. Redis만 보면 그 state는 우리가 만든 진짜 값이라 통과한다. state가 "이 브라우저가 시작한 것"인지(쿠키) 맞춰 봐야 막힌다.</details>

4. 이 프로젝트가 state를 쿠키에만 두지 않고 Redis에도 두는 이유는?
<details><summary>답</summary>콜백 주소가 localhost라 blog.test에 둔 쿠키가 콜백에 오지 않는다. 콜백에서 state가 진짜인지·안 썼는지 보고, 어디로 돌려보낼지(origin), 무엇을 하려던 것인지(mode), 누가 시작했는지(memberId)를 알려면 서버 쪽 저장소가 필요하다.</details>

5. 콜백에서 바로 로그인 쿠키를 주지 않고 complete로 한 번 더 보내는 이유는?
<details><summary>답</summary>로그인 쿠키는 Domain=.blog.test라 localhost 응답으로는 브라우저가 받지 않는다. 구글은 https가 아니면 localhost만 콜백으로 등록할 수 있다. 그래서 콜백은 표만 만들고, 로그인을 시작한 플랫폼 주소의 complete에서 state 쿠키를 확인하고 로그인 쿠키를 준다.</details>

6. state 쿠키를 SameSite=Strict로 하면 어떻게 되나?
<details><summary>답</summary>complete로 오는 이동은 다른 사이트(제공사, localhost)에서 시작된 이동이라 Strict 쿠키가 실리지 않는다. 늘 쿠키가 없어 모든 소셜 로그인이 OAUTH_FAILED가 된다. 다른 사이트에서 온 최상위 GET 이동에도 쿠키를 보내는 Lax여야 한다.</details>

7. 같은 표(ticket)로 동시에 두 요청이 와도 한 번만 통과하는 이유는?
<details><summary>답</summary>take는 읽은 뒤 DEL의 결과가 true(내가 지웠다)일 때만 값을 쓴다. DEL은 한 명령이라 둘 중 하나만 1을 받고 다른 하나는 0(이미 없음)을 받는다.</details>

8. 가입 토큰은 왜 take가 아니라 read로 읽고, 성공한 뒤에 지우나?
<details><summary>답</summary>닉네임이 겹쳐 409가 나면 사용자가 다른 닉네임으로 같은 토큰을 다시 써야 한다. 읽을 때 지우면 다시 처음부터 소셜 로그인을 해야 한다. 두 번 가입되는 것은 social_account의 UNIQUE와 한 트랜잭션이 막는다.</details>

9. 카카오 이메일이 우리 회원 이메일과 같을 때 자동으로 합치면 생기는 위험은?
<details><summary>답</summary>제공사 이메일이 확인된 것이라는 보장이 없으면, 공격자가 남의 이메일로 소셜 계정을 만들어 그 사람의 우리 계정에 들어올 수 있다. 그래서 묶는 길은 로그인한 상태의 마이페이지 연동 하나뿐이고, 제공사 이메일은 받지도 저장하지도 않는다.</details>

10. 해제할 때 회원 행을 먼저 잠그지 않으면 생기는 일은?
<details><summary>답</summary>카카오·구글이 연결된 소셜 회원이 둘을 동시에 해제하면 두 요청 모두 "지금 2개라 하나는 남는다"를 보고 둘 다 지워, 로그인 수단이 0개인 계정이 생긴다. 잠그면 두 번째가 기다렸다가 1개를 보고 409를 낸다.</details>

11. 탈퇴 재인증에서 카카오는 prompt=login, 구글은 max_age=0을 쓰는 이유는? 붙이지 않으면?
<details><summary>답</summary>둘 다 "이미 로그인해 있어도 다시 로그인시켜라"는 뜻인데, 구글의 prompt는 login을 받지 않아 OIDC의 max_age=0을 쓴다. 붙이지 않으면 제공사에 로그인된 채 자리를 비운 PC에서 남이 버튼만 눌러도 본인 확인이 끝난다.</details>

12. `redirect=//evil.example`이 왜 위험하고, 서버는 어떻게 거르나?
<details><summary>답</summary>브라우저는 `//evil.example`을 "같은 프로토콜의 evil.example"로 읽어 다른 사이트로 간다. safeRedirect는 `/`로 시작해도 `//`·`/\`로 시작하면 빼고, 절대 주소는 http·https이면서 호스트가 우리 플랫폼·블로그 주소일 때만 받는다. 나머지는 홈(`/`)이다.</details>

## 9. 더 읽을거리

- RFC 6749 "The OAuth 2.0 Authorization Framework" 4.1(인가 코드), 10.6(리다이렉트 URI 조작), 10.12(CSRF와 state)
- RFC 9700 "Best Current Practice for OAuth 2.0 Security"(PKCE, state, 열린 리다이렉트)
- RFC 7636 "Proof Key for Code Exchange (PKCE)"
- OpenID Connect Core 1.0: `scope=openid`, `sub`, `max_age`·`auth_time`, `prompt`
- Google Identity "OpenID Connect" 문서(`sub`를 식별자로, `prompt` 값, 리디렉션 URI 규칙)
- Kakao Developers "카카오 로그인 REST API"(인가 코드 받기의 `prompt`, 토큰 받기, 사용자 정보 가져오기)
- OWASP Cheat Sheet "Unvalidated Redirects and Forwards"
