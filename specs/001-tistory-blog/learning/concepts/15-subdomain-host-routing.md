# 15. 서브도메인과 Host 헤더로 블로그 찾기

> 관련 스텝: [스텝 3](../step-03.md) (T009), 개발 환경 보강 2026-10-09(dnsmasq) · 관련 개념: [10-http-cookies](./10-http-cookies.md), [13-csrf-samesite-cors](./13-csrf-samesite-cors.md), [16-authorization-visibility](./16-authorization-visibility.md), [18-spa-server-routing](./18-spa-server-routing.md)

## 1. 이 문서로 배우는 것

- 도메인 이름이 어떤 부분으로 이루어지는지(최상위 도메인, 서브도메인)
- 브라우저가 `alpha.blog.com`을 열 때 DNS가 이름을 IP 주소로 바꾸는 과정
- 블로그가 수천 개여도 DNS 설정은 한 줄이면 되는 이유(와일드카드 DNS)
- 로컬 개발에서 `/etc/hosts`를 고치는 이유와 `*.localhost`를 쓰지 않는 이유
- `/etc/hosts`의 한계(블로그마다 한 줄)와, dnsmasq + `/etc/resolver`로 `*.blog.test` 전체를 한 번에 내 컴퓨터로 보내는 법
- 실제 배포에서 DNS 와일드카드 레코드와 와일드카드 HTTPS 인증서를 설정하는 법
- 한 서버가 여러 주소의 요청을 받고 구분하는 방법(HTTP `Host` 헤더, 가상 호스트)
- 멀티테넌시: 하나의 서비스 안에 블로그(테넌트)가 여럿 사는 구조
- 서브도메인 방식과 경로 방식(`blog.com/@alpha`)의 장단점
- 이 프로젝트의 `BlogHostResolver`, `BlogAddressRule`, `DomainProperties`, `@CurrentBlog`가 각각 하는 일

**먼저 알면 좋은 것**: HTTP 요청이 메서드·경로·헤더·본문으로 이루어진다는 것, Spring MVC 컨트롤러의 기본(`@GetMapping`), Java의 `record`. 몰라도 이 문서에서 필요한 만큼은 설명한다.

## 2. 왜 필요한가

티스토리처럼 회원마다 자기 블로그 주소를 갖는 서비스를 생각해 보자. A의 블로그는 `alpha.blog.com`, B의 블로그는 `beta.blog.com`이다.

서버를 블로그마다 하나씩 띄울 수는 없다. 블로그가 만 개면 서버도 만 대가 된다. 그래서 **서버 한 대(또는 같은 서버 여러 대)가 모든 블로그 주소의 요청을 받고, 요청이 어느 블로그를 향하는지 알아내야** 한다.

이걸 알아내지 못하면 이런 일이 생긴다.

- `alpha.blog.com/15`와 `beta.blog.com/15`를 구분하지 못한다. 경로는 둘 다 `/15`다.
- 블로그 A의 관리 화면에 B가 들어와도, 서버는 "어느 블로그의 관리 화면인지" 모르니 주인 검사를 할 수 없다.
- 삭제된 블로그나 없는 주소로 와도 막을 기준이 없다.

이 프로젝트는 요청의 **Host 헤더**에서 서브도메인(`alpha`)을 읽어 블로그를 찾는다(research.md R-04). 이 문서는 그 바탕이 되는 개념과 코드를 다룬다.

## 3. 기본 개념

### 3.1 도메인 이름의 구조

도메인 이름은 점(`.`)으로 나뉜 **라벨**들이고, **오른쪽으로 갈수록 상위**다.

```
        alpha  .  blog  .  com
        ─────    ─────    ───
        서브도메인  2단계    최상위 도메인(TLD)
                 도메인
        └────────── 전체를 FQDN이라고도 부른다 ──────────┘
```

| 용어 | 뜻 | 예 |
| --- | --- | --- |
| TLD(Top-Level Domain, 최상위 도메인) | 가장 오른쪽 라벨 | `com`, `net`, `kr`, `test` |
| 2단계 도메인 | TLD 바로 왼쪽. 보통 돈을 내고 등록하는 이름 | `blog.com`의 `blog` |
| 서브도메인 | 등록한 도메인 왼쪽에 붙이는 이름. 등록한 사람이 마음대로 만든다 | `alpha.blog.com`, `www.blog.com` |
| 호스트 이름(hostname) | 특정 컴퓨터(또는 서비스)를 가리키는 전체 이름 | `alpha.blog.com` |

`blog.com`을 가진 사람은 `alpha.blog.com`, `beta.blog.com`, `www.blog.com`을 추가 비용 없이 원하는 만큼 만들 수 있다. 서브도메인은 "등록"하는 것이 아니라 내 DNS 설정에 **이름을 적는** 것이기 때문이다.

> `test` TLD는 테스트용으로 예약된 이름이라 인터넷의 실제 DNS에는 존재하지 않는다(RFC 2606). 그래서 로컬 개발용 `blog.test`가 실제 사이트와 겹칠 걱정이 없다.

### 3.2 DNS: 이름을 IP 주소로 바꾸는 전화번호부

컴퓨터끼리는 IP 주소(`203.0.113.10` 같은 숫자)로 통신한다. 사람이 쓰는 이름을 IP로 바꿔 주는 것이 **DNS(Domain Name System)**다.

브라우저 주소창에 `http://alpha.blog.com/15`를 치면:

```
1. 브라우저 캐시, 운영체제 캐시에 alpha.blog.com의 IP가 있나?   → 있으면 바로 사용
2. 운영체제가 hosts 파일(/etc/hosts)을 본다                     → 적혀 있으면 그 IP 사용
3. 없으면 DNS 리졸버(보통 통신사나 8.8.8.8)에 묻는다
4. 리졸버가 루트 서버 → .com 서버 → blog.com의 네임서버 순으로 물어 답을 얻는다
5. "alpha.blog.com = 203.0.113.10" 을 받아 캐시에 저장(TTL 동안)
6. 브라우저가 203.0.113.10의 80번 포트로 TCP 연결을 열고 HTTP 요청을 보낸다
```

중요한 점: **DNS는 IP만 알려 준다.** 어느 블로그인지는 DNS가 아니라 이후 HTTP 요청 안의 정보(Host 헤더)로 구분한다.

DNS에 적는 기록(레코드)의 대표적인 종류:

| 레코드 | 뜻 | 예 |
| --- | --- | --- |
| A | 이름 → IPv4 주소 | `blog.com. A 203.0.113.10` |
| AAAA | 이름 → IPv6 주소 | |
| CNAME | 이름 → 다른 이름(별칭) | `www.blog.com. CNAME blog.com.` |

### 3.3 와일드카드 DNS

블로그가 생길 때마다 DNS에 `alpha.blog.com A ...`, `beta.blog.com A ...`를 추가할 수는 없다. 그래서 **와일드카드 레코드**를 한 줄 둔다.

```
*.blog.com.   A   203.0.113.10
```

이러면 `alpha.blog.com`, `beta.blog.com`, `아무거나.blog.com`이 모두 같은 IP로 간다. 블로그가 존재하는지는 DNS가 아니라 **서버가 DB를 보고** 판단한다. 그래서 `nobody-here.blog.com`도 DNS 단계에서는 우리 서버로 오고, 서버가 404를 준다.

> 와일드카드 `*`는 라벨 하나에만 대응한다. `*.blog.com`은 `a.b.blog.com`(라벨 두 개)을 덮지 않는다. 이 프로젝트도 서브도메인이 두 단계인 주소는 블로그로 보지 않는다(아래 5.1).

HTTPS를 쓰려면 인증서도 와일드카드 인증서(`*.blog.com`)가 필요하다. 이것도 한 단계만 덮는다.

**실제로 설정하는 곳.** 도메인(`blog.com`)을 산 곳(가비아, Cloudflare, AWS Route 53 등)의 DNS 관리 화면에서 레코드를 더한다. 화면 모양은 달라도 넣는 값은 같다.

| 타입 | 이름(호스트) | 값 | TTL | 뜻 |
| --- | --- | --- | --- | --- |
| A | `@` (도메인 자신) | 서버 IP | 300 등 | 플랫폼 주소 `blog.com` |
| A | `*` | 서버 IP | 300 등 | 모든 블로그 주소 `{주소}.blog.com` |
| A 또는 CNAME | `www` | 서버 IP 또는 `blog.com` | | `www.blog.com`도 플랫폼 (`*`가 덮지만 따로 두면 의도가 분명하다) |

- **TTL**은 다른 DNS 서버가 이 답을 몇 초 동안 기억해도 되는지다. 처음 설정할 때는 짧게(300초) 두면 잘못 넣었을 때 빨리 바로잡힌다.
- 레코드는 바로 퍼지지 않는다. 몇 분에서 길게는 TTL만큼 걸린다.
- **와일드카드 인증서**: 무료 인증서인 Let's Encrypt는 `*.blog.com` 인증서를 **DNS-01 방식**으로만 준다. "이 도메인의 주인이 맞다"를 DNS에 `_acme-challenge.blog.com` TXT 레코드를 넣어 증명하는 방식이다. DNS 회사가 API를 주면 certbot 같은 도구가 자동으로 넣고 갱신한다.
- 앱 쪽은 설정값 하나만 바꾼다. `app.domain.platform`(운영은 환경 변수 `APP_PLATFORM_DOMAIN`)을 실제 도메인으로 두면, 블로그 주소 해석과 로그인 쿠키 도메인(`Domain=.blog.com`)이 모두 그 값을 따른다(5.3).

### 3.4 /etc/hosts: 내 컴퓨터만의 DNS

`/etc/hosts`(Windows는 `C:\Windows\System32\drivers\etc\hosts`)는 운영체제가 DNS보다 먼저 보는 파일이다. 한 줄에 "IP 이름 이름 ..."을 적는다.

```
127.0.0.1   blog.test alpha.blog.test beta.blog.test gamma.blog.test
```

이렇게 적으면 내 컴퓨터에서만 `alpha.blog.test`가 `127.0.0.1`(내 컴퓨터 자신)을 가리킨다. 그래서 로컬에서 돌리는 Spring Boot(8080)에 `http://alpha.blog.test:8080`으로 접속할 수 있다.

- **와일드카드를 쓸 수 없다.** hosts 파일은 `*.blog.test`를 지원하지 않아서, 테스트할 블로그 주소를 하나씩 적어야 한다. quickstart.md가 `alpha`, `beta`, `gamma`를 적게 하는 이유다.
- 관리자 권한이 필요하다(`sudo vi /etc/hosts`).

- **새 블로그를 만들 때마다 한 줄씩 더해야 한다.** 화면에서 블로그를 개설하면 바로 그 주소(`myfirst.blog.test`)로 이동하는데, hosts에 없으면 브라우저가 `DNS_PROBE_FINISHED_NXDOMAIN`(그런 이름 없음) 오류를 낸다. 서버까지 요청이 가지도 않은 것이라 서버 로그에는 아무것도 없다.

**왜 `*.localhost`를 쓰지 않나**: 요즘 브라우저는 `alpha.localhost`처럼 `.localhost`로 끝나는 이름을 hosts 없이도 127.0.0.1로 보내 준다. 편해 보이지만, 이 프로젝트는 **모든 블로그 주소가 로그인 쿠키를 같이 써야** 한다(`Domain=.blog.test`, [10-http-cookies](./10-http-cookies.md)). `localhost`에 대한 쿠키 도메인 처리는 브라우저마다 달라서, `Domain=.localhost` 쿠키가 하위 주소에 공유되지 않는 경우가 있다(research.md R-03 "로컬 개발"). 그래서 실제 운영과 같은 구조(`blog.test` + 하위 주소)를 hosts로 흉내 낸다.

### 3.5 dnsmasq와 /etc/resolver: 내 컴퓨터의 와일드카드 DNS

hosts는 와일드카드가 안 되니, 내 컴퓨터 안에 **작은 DNS 서버**를 띄워 와일드카드 규칙을 주는 방법이 있다. 그 DNS 서버 프로그램이 **dnsmasq**다.

```
address=/blog.test/127.0.0.1
```

dnsmasq 설정에 이 한 줄을 두면 `blog.test`와 그 아래 모든 이름(`alpha.blog.test`, `아무거나.blog.test`)을 127.0.0.1로 답한다. 3.3의 `*.blog.com A ...` 레코드와 같은 일을 내 컴퓨터 안에서 하는 셈이다.

그런데 운영체제는 평소에 통신사·공유기 DNS에 묻지, 내 컴퓨터의 dnsmasq에 묻지 않는다. macOS는 **`/etc/resolver/{끝 이름}` 파일**로 "이 끝 이름은 이 DNS 서버에 물어라"를 정할 수 있다.

```
/etc/resolver/test 의 내용:
nameserver 127.0.0.1
```

파일 이름이 `test`라서 `.test`로 끝나는 이름만 127.0.0.1(dnsmasq)에 묻는다. `naver.com` 같은 나머지는 원래 DNS로 가므로 다른 인터넷 사용에는 영향이 없다.

```
"xyz.blog.test의 IP는?"
  → /etc/hosts에 없음
  → 끝이 .test → /etc/resolver/test → 127.0.0.1의 dnsmasq에 물음
  → dnsmasq: address=/blog.test/127.0.0.1 규칙에 맞음 → 127.0.0.1
  → 브라우저가 127.0.0.1:8080에 연결, Host: xyz.blog.test로 요청 → BlogHostResolver(5.1)
```

`.test`는 실제 인터넷에서 쓰지 않기로 예약된 끝 이름이라(RFC 2606) 진짜 사이트와 겹칠 걱정이 없다.

| | /etc/hosts | dnsmasq + /etc/resolver |
| --- | --- | --- |
| 와일드카드 | 안 됨, 이름마다 한 줄 | `address=/blog.test/127.0.0.1` 한 줄 |
| 설치 | 필요 없음 | `brew install dnsmasq` |
| 새 블로그 | 매번 추가 | 할 일 없음 |
| 운영과 닮은 정도 | 낮음 | 운영의 와일드카드 레코드와 같은 구조 |

명령 모음은 7장 실습 6에 있다.

### 3.6 DNS 오류와 서버의 주소 해석은 다른 단계

"블로그 주소 라우팅 기능이 있으면 이 오류도 해결되지 않나?" 아니다. 요청은 두 단계를 지난다.

```
① 이름 찾기(DNS)         내 컴퓨터가 함: alpha.blog.test → 127.0.0.1    ← NXDOMAIN은 여기서 실패
② 블로그 고르기(Host)     서버가 함: Host: alpha.blog.test → alpha 블로그  ← BlogHostResolver
```

①이 실패하면 요청이 서버에 닿지 않으니 서버 코드로는 고칠 수 없다. 개발에서는 hosts나 dnsmasq가, 운영에서는 DNS 와일드카드 레코드가 ①을 맡는다.

### 3.7 HTTP Host 헤더

HTTP/1.1 요청에는 **Host 헤더가 반드시** 들어간다. 브라우저가 주소창의 호스트 이름(과 포트)을 그대로 넣는다.

```http
GET /15 HTTP/1.1
Host: alpha.blog.test:8080
Cookie: access_token=...
Accept: text/html
```

- 포트가 기본값(http 80, https 443)이면 생략되고, 아니면 `:8080`처럼 붙는다.
- 같은 IP로 온 요청이라도 Host가 다르면 "다른 사이트를 향한 요청"이다.
- HTTP/2에서는 `:authority`라는 의사 헤더가 같은 역할을 하고, 서블릿 API에서는 똑같이 `getServerName()`으로 읽힌다.

서블릿(`HttpServletRequest`)에서 읽는 법:

| 메서드 | `Host: alpha.blog.test:8080`일 때 |
| --- | --- |
| `getServerName()` | `alpha.blog.test` (포트를 뺀 이름) |
| `getServerPort()` | `8080` |
| `getHeader("Host")` | `alpha.blog.test:8080` (원문) |

> 운영에서 앞에 로드밸런서나 리버스 프록시(Nginx)를 두면, 프록시가 Host를 바꿔 넘기거나 `X-Forwarded-Host`에 원래 값을 담는다. 그때는 Spring Boot의 `server.forward-headers-strategy` 설정이 필요할 수 있다. 지금 프로젝트는 프록시 없이 직접 받는 구조다.

### 3.8 가상 호스트: 한 서버, 여러 사이트

**가상 호스트(virtual host)**는 서버 하나가 Host 헤더를 보고 여러 사이트를 나눠 서빙하는 방식이다. Nginx의 `server_name`, Apache의 `<VirtualHost>`가 대표적이다.

```
            ┌─────────────────────────────┐
요청 ──────▶│ 서버 (IP 203.0.113.10:80)    │
Host: a.com │  Host == a.com → 사이트 A    │
Host: b.com │  Host == b.com → 사이트 B    │
            └─────────────────────────────┘
```

이 프로젝트는 같은 생각을 **애플리케이션 안에서** 한다. Spring Boot 앱 하나가 모든 Host를 받고, 코드(`BlogHostResolver`)가 Host를 보고 플랫폼 화면인지, 어느 블로그인지 정한다.

### 3.9 멀티테넌시

**테넌트(tenant)**는 "세입자"라는 뜻이다. 하나의 서비스(건물)에 여러 고객(세입자)이 각자의 공간을 갖는 구조를 **멀티테넌시**라고 한다. 이 프로젝트에서 테넌트는 **블로그**다.

| 멀티테넌시 방식 | 데이터 분리 | 이 프로젝트 |
| --- | --- | --- |
| 테넌트마다 DB 따로 | 가장 강함, 비용 큼 | 아님 |
| 테넌트마다 스키마 따로 | 중간 | 아님 |
| **테이블 공유 + 테넌트 id 컬럼** | 코드가 조건을 빠뜨리지 않아야 함 | **이 방식**: `post.blog_id`, `category.blog_id` |

테이블을 공유하는 방식에서는 "모든 조회에 `blog_id` 조건이 붙었나"가 생명이다. 그래서 요청이 들어오는 입구에서 **현재 블로그를 한 번 정해 두고**(`@CurrentBlog`), 모든 기능이 그 블로그를 기준으로 일하게 만든다.

### 3.10 서브도메인 방식 vs 경로 방식

블로그를 구분하는 방법은 크게 두 가지다.

| | 서브도메인 방식 `alpha.blog.com/15` | 경로 방식 `blog.com/@alpha/15` |
| --- | --- | --- |
| 쓰는 곳 | 티스토리, 기존 블로그 서비스 | 미디엄, 벨로그 |
| 주소 느낌 | 블로그가 독립된 사이트처럼 보임 | 플랫폼 안의 페이지처럼 보임 |
| DNS·인증서 | 와일드카드 DNS, 와일드카드 인증서 필요 | 필요 없음 |
| 로그인 공유 | 상위 도메인 쿠키(`Domain=.blog.com`)가 필요 | 같은 출처라 저절로 됨 |
| 보안 | 다른 블로그와 출처가 달라 어느 정도 분리됨. 그러나 같은 사이트(same-site)라 CSRF는 더 신경 써야 함([13](./13-csrf-samesite-cors.md)) | 모든 블로그가 같은 출처라 한 블로그의 XSS가 전체에 영향 |
| 로컬 개발 | hosts 파일 필요 | 필요 없음 |
| 구현 | Host 해석 장치 필요(이 문서) | 경로 변수로 끝 |

plan.md "복잡도 기록"에 적힌 대로, 이 프로젝트는 티스토리와 같은 경험을 위해 서브도메인을 골랐고, 그 대가로 상위 도메인 쿠키와 CSRF 대책을 떠안았다.

## 4. 동작 원리

로컬에서 로그인한 사용자가 `http://alpha.blog.test:8080/api/test/blog`(블로그 API, 테스트 전용)를 부를 때 일어나는 일을 단계별로 보자.

```
① 운영체제: /etc/hosts에서 alpha.blog.test → 127.0.0.1
② 브라우저: 127.0.0.1:8080으로 연결, 요청에 Host: alpha.blog.test:8080
③ 톰캣: 요청을 받아 HttpServletRequest를 만든다. getServerName() = "alpha.blog.test"
④ 보안 필터: 쿠키로 로그인 회원을 정해 SecurityContext에 둔다 ([12](./12-spring-security-filter-chain.md))
⑤ DispatcherServlet: 경로로 컨트롤러 메서드를 찾는다
⑥ 인자 준비: 메서드 인자에 @CurrentBlog Blog가 있다
      → CurrentBlogArgumentResolver.resolveArgument()
         → BlogHostResolver.resolve("alpha.blog.test")
              플랫폼("blog.test")인가? 아니오
              ".blog.test"로 끝나나? 예 → 앞부분 "alpha"
              주소 규칙에 맞나, 예약어가 아닌가? 예 → BlogAddress("alpha")
         → blogRepository.findByAddress("alpha")  (DB 조회)
         → 볼 수 있는 블로그인가(BlogVisibilityPolicy) / 이사했나
         → 통과하면 Blog 객체를 인자로 넘김, 아니면 404 예외
⑦ 컨트롤러 메서드 실행: 이미 "어느 블로그인지"가 정해진 상태
```

핵심은 ⑥이다. 컨트롤러마다 Host를 읽고 블로그를 찾는 코드를 반복하지 않고, **인자 해석기(HandlerMethodArgumentResolver)** 한 곳에 모았다.

### 4.1 HandlerMethodArgumentResolver

Spring MVC는 컨트롤러 메서드를 부르기 전에, 인자 하나하나를 **인자 해석기 목록**에 물어 채운다.

```
@GetMapping("/api/posts/{id}")
public PostResponse get(@PathVariable Long id,          ← PathVariableMethodArgumentResolver
                        @RequestParam int page,          ← RequestParamMethodArgumentResolver
                        @AuthenticationPrincipal LoginMember me,  ← AuthenticationPrincipalArgumentResolver
                        @CurrentBlog Blog blog)          ← 우리가 만든 CurrentBlogArgumentResolver
```

각 해석기는 두 메서드를 가진다.
- `supportsParameter(parameter)`: "이 인자는 내가 맡는다"를 true/false로 답한다.
- `resolveArgument(...)`: 실제 값을 만들어 돌려준다. 예외를 던지면 컨트롤러는 실행되지 않고, 그 예외가 `@RestControllerAdvice`로 간다([07](./07-spring-mvc-exception-handling.md)).

직접 만든 해석기는 `WebMvcConfigurer.addArgumentResolvers`로 등록한다. Spring은 직접 등록한 해석기를 기본 해석기들 뒤, 그러나 "무엇이든 받는" 마지막 해석기(애노테이션 없는 객체를 `@ModelAttribute`로 보는 것)보다는 앞에서 물어본다.

## 5. 이 프로젝트에서는

### 5.1 BlogHostResolver: Host를 세 종류로 나누기

`src/main/java/com/nhnacademy/blog/global/host/RequestHost.java`

```java
public sealed interface RequestHost {
    record Platform() implements RequestHost { }
    record BlogAddress(String address) implements RequestHost { }
    record Unknown() implements RequestHost { }
}
```

- `sealed interface`: 이 인터페이스를 구현할 수 있는 타입을 **정해 둔** 인터페이스다. 여기서는 같은 파일 안의 세 record만 구현할 수 있다. 그래서 `switch`에서 세 경우를 모두 다뤘는지 컴파일러가 확인해 준다([16](./16-authorization-visibility.md)에서 자세히).
- `record`: 값을 담는 불변 클래스를 짧게 쓰는 문법이다. `BlogAddress("alpha")`는 생성자, `address()` 접근자, `equals`/`hashCode`/`toString`이 자동으로 생긴다. 그래서 테스트에서 `isEqualTo(new RequestHost.BlogAddress("alpha"))`로 비교할 수 있다.

`src/main/java/com/nhnacademy/blog/global/host/BlogHostResolver.java`

```java
public RequestHost resolve(String serverName) {
    if (serverName == null) {
        return new RequestHost.Unknown();                       // (1)
    }
    String host = serverName.toLowerCase(Locale.ROOT);          // (2)
    String platform = domainProperties.platform();              // (3) "blog.test" 또는 "blog.com"
    if (host.equals(platform) || host.equals("www." + platform)) {
        return new RequestHost.Platform();                      // (4)
    }
    String suffix = "." + platform;
    if (!host.endsWith(suffix)) {
        return new RequestHost.Unknown();                       // (5)
    }
    String address = host.substring(0, host.length() - suffix.length());  // (6)
    if (!BlogAddressRule.isUsable(address)) {
        return new RequestHost.Unknown();                       // (7)
    }
    return new RequestHost.BlogAddress(address);                // (8)
}
```

1. Host가 없으면(테스트 등) 알 수 없는 주소다.
2. 도메인 이름은 대소문자를 구분하지 않는다. `ALPHA.Blog.Test`도 같은 주소라 소문자로 맞춘다. `Locale.ROOT`를 주는 이유는 터키어 로케일 같은 환경에서 `I`의 소문자가 `i`가 아닌 문자로 바뀌는 문제를 피하기 위해서다.
3. 플랫폼 주소는 설정값이다(아래 5.3). 코드에 `blog.com`을 박지 않아서 개발(`blog.test`)과 운영(`blog.com`)이 같은 코드로 돈다.
4. `blog.test`, `www.blog.test`는 플랫폼(홈, 로그인, 가입 화면).
5. `.blog.test`로 끝나지 않으면 이 서비스의 주소가 아니다. 예: `other.com`, `evilblog.test`(점이 없어서 `.blog.test`로 끝나지 않는다). `endsWith("blog.test")`가 아니라 앞에 점을 붙인 `endsWith(".blog.test")`로 검사하는 것이 핵심이다. 점이 없으면 `evilblog.test`가 통과해 버린다.
6. 뒷부분을 잘라 서브도메인만 남긴다. `alpha.blog.test` → `alpha`, `a.b.blog.test` → `a.b`.
7. 주소 규칙(아래 5.2)에 맞지 않으면 블로그 주소가 아니다. `a.b`는 점이 규칙에 없어 여기서 걸린다. 그래서 두 단계 서브도메인은 자연스럽게 막힌다.
8. 통과하면 블로그 주소. 아직 **DB에 그 블로그가 있는지는 모른다**(주석: "블로그가 실제로 있는지는 아직 모른다").

DB 조회는 따로 한다.

```java
public Optional<Blog> findBlog(HttpServletRequest request) {
    if (resolve(request) instanceof RequestHost.BlogAddress(String address)) {
        return blogRepository.findByAddress(address);
    }
    return Optional.empty();
}
```

`instanceof RequestHost.BlogAddress(String address)`는 Java 21의 **record 패턴**이다. "BlogAddress이면, 그 안의 `address` 값을 꺼내 `address` 변수에 넣어라"를 한 줄로 쓴 것이다. 예전 방식으로 쓰면 이렇다.

```java
RequestHost host = resolve(request);
if (host instanceof RequestHost.BlogAddress) {
    String address = ((RequestHost.BlogAddress) host).address();
    ...
}
```

`findByAddress`는 삭제된 블로그도 돌려준다(주소는 삭제돼도 영구 예약, R-08). 볼 수 있는지는 부르는 쪽에서 판단한다. 이렇게 "주소 해석"과 "볼 수 있나 판단"을 나눠 둔 덕에 API(`@CurrentBlog`)와 화면 주소 처리([18](./18-spa-server-routing.md))가 같은 해석기를 쓰면서 각자 다르게 대응한다.

### 5.2 BlogAddressRule: 정규식과 예약어

`src/main/java/com/nhnacademy/blog/blog/domain/BlogAddressRule.java`

```java
private static final Pattern FORMAT = Pattern.compile("^[a-z0-9][a-z0-9-]{2,30}[a-z0-9]$");
```

정규식을 조각내 읽어 보자.

| 조각 | 뜻 |
| --- | --- |
| `^` | 문자열 시작 |
| `[a-z0-9]` | 첫 글자: 영문 소문자나 숫자 **한 글자**(하이픈 불가) |
| `[a-z0-9-]{2,30}` | 가운데: 소문자·숫자·하이픈 **2~30글자** |
| `[a-z0-9]` | 마지막 글자: 소문자나 숫자 한 글자(하이픈 불가) |
| `$` | 문자열 끝 |

전체 길이는 1 + (2~30) + 1 = **4~32자**다. 블로그 주소 규칙(spec: 영문 소문자·숫자·하이픈 4~32자)과 같다.

| 입력 | 결과 | 이유 |
| --- | --- | --- |
| `alpha` | 통과 | |
| `my-blog` | 통과 | 하이픈은 가운데만 |
| `abc` | 실패 | 3자. 가운데가 최소 2자라 최소 4자 |
| `-alpha`, `alpha-` | 실패 | 처음·끝 하이픈 |
| `Alpha` | 실패 | 대문자. 단, Host는 소문자로 바꾼 뒤 검사하므로 `Alpha.blog.test`는 `alpha`로 통과 |
| `al_pha`, `al.pha` | 실패 | 밑줄·점은 허용 문자가 아님 |

처음과 끝을 하이픈 불가로 둔 이유는 DNS 라벨 규칙 때문이기도 하다. DNS 라벨(호스트 이름의 한 칸)은 하이픈으로 시작하거나 끝날 수 없다(RFC 1123 호스트 이름 규칙).

`Pattern.compile`을 `static final`로 한 번만 만드는 이유: 정규식을 컴파일하는 비용이 있어서, 요청마다 새로 만들지 않는다.

**예약어**:

```java
private static final Set<String> RESERVED = Set.of(
        "www", "api", "admin", "static", "mail", "login", "logout", "signup", "manage", "assets", "uploads",
        "blog", "help", "support", "notice", "cdn", "smtp", "imap", "ftp", "test", "dev", "root", "system");
```

누가 `admin`이라는 블로그를 만들면 `admin.blog.com`이 관리자 화면처럼 보여 피싱에 쓰일 수 있고, 나중에 플랫폼이 `api.blog.com`, `cdn.blog.com` 같은 서브도메인을 쓰고 싶어도 이미 남의 블로그가 된다. 그래서 미리 막아 둔다. 이 목록은 블로그 개설(스텝 4, T022)에서도 같이 쓴다. 규칙이 한 곳에 있으니 "개설할 때는 막았는데 주소 해석에서는 통과" 같은 불일치가 생기지 않는다.

`www`는 예약어이면서 동시에 `BlogHostResolver`의 (4)에서 플랫폼으로 먼저 처리된다.

### 5.3 DomainProperties: 설정값으로 플랫폼 주소 받기

`src/main/java/com/nhnacademy/blog/global/host/DomainProperties.java`

```java
@ConfigurationProperties(prefix = "app.domain")
public record DomainProperties(String platform) {
    public String cookieDomain() { return "." + platform; }
    public String blogHost(String address) { return address + "." + platform; }
}
```

- `@ConfigurationProperties(prefix = "app.domain")`: 설정 파일의 `app.domain.platform` 값을 이 record의 `platform`에 넣는다. `BlogApplication`의 `@ConfigurationPropertiesScan`이 이런 클래스를 찾아 빈으로 만든다([02](./02-configuration-profiles.md)).
- 값: `application.yml`은 `blog.com`, `application-dev.yml`은 `blog.test`, `application-prod.yml`은 `${APP_PLATFORM_DOMAIN:blog.com}`.
- `cookieDomain()`: 로그인 쿠키를 `.blog.test`에 둬서 모든 블로그 주소가 함께 받는다([10](./10-http-cookies.md)). 주소 해석과 쿠키 도메인이 **같은 설정값**에서 나오므로 둘이 어긋날 일이 없다.
- `blogHost("gamma")` → `gamma.blog.test`. 301 리다이렉트 주소를 만들 때 쓴다.

### 5.4 @CurrentBlog: 블로그 API의 입구

`src/main/java/com/nhnacademy/blog/global/host/CurrentBlogArgumentResolver.java`

```java
@Override
public boolean supportsParameter(MethodParameter parameter) {
    return parameter.hasParameterAnnotation(CurrentBlog.class) && Blog.class.equals(parameter.getParameterType());
}
```

`@CurrentBlog`가 붙어 있고 타입이 `Blog`인 인자만 맡는다.

```java
@Override
public Blog resolveArgument(...) {
    HttpServletRequest request = webRequest.getNativeRequest(HttpServletRequest.class);  // (1)
    Long viewerId = LoginMembers.currentId();                                             // (2)
    Blog blog = blogHostResolver.findBlog(request)                                        // (3)
            .filter(found -> blogVisibilityPolicy.canView(found, viewerId))               // (4)
            .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));               // (5)
    // 이사한 블로그는 주인만 옛 주소의 API를 쓴다 (BLOG-06)
    if (blog.isMoved() && !blog.isOwnedBy(viewerId)) {                                    // (6)
        throw new BusinessException(ErrorCode.NOT_FOUND);
    }
    return blog;
}
```

1. Spring의 요청 추상화(`NativeWebRequest`)에서 서블릿 요청을 꺼낸다.
2. 보안 필터가 SecurityContext에 넣어 둔 로그인 회원 id. 비회원이면 null.
3. Host → 블로그(없으면 빈 `Optional`).
4. 볼 수 있는 블로그만 남긴다. 삭제된 블로그는 아무도, 이용 제한·주인 정지 블로그는 주인만 본다([16](./16-authorization-visibility.md)).
5. 남은 게 없으면 404. **없는 블로그와 볼 수 없는 블로그를 같은 404로** 돌려준다. 응답만 보고 "이 주소에 블로그가 있긴 하구나"를 알 수 없게 한다.
6. 이사한 블로그(`moved_to_blog_id`가 있음)의 옛 주소로 부르는 API는 주인만 쓸 수 있다. 주인은 옛 블로그 관리 화면을 계속 쓰고(BLOG-06), 다른 사람은 화면 단계에서 이미 새 주소로 301을 받으므로 이 404를 볼 일이 거의 없다(rest-api.md "주소와 Host 범위").

컨트롤러는 이렇게 쓴다(테스트 전용 API `src/test/.../support/TestApiController.java`).

```java
@PutMapping("/api/test/blog/settings")
public Map<String, String> ownerOnly(@CurrentBlog Blog blog, @AuthenticationPrincipal LoginMember member) {
    blogOwnerGuard.requireOwner(blog, member);   // 비회원 401, 남 403
    return Map.of("result", "ok");
}
```

인자 해석이 컨트롤러 실행 **전에** 일어나므로, 없는 블로그면 로그인 검사(401)보다 404가 먼저 나간다. rest-api.md의 상태 코드 순서(404 → 401 → 403)가 구조적으로 지켜진다.

등록은 `src/main/java/com/nhnacademy/blog/global/config/WebConfig.java`:

```java
@Override
public void addArgumentResolvers(List<HandlerMethodArgumentResolver> resolvers) {
    resolvers.add(currentBlogArgumentResolver);
}
```

### 5.5 이사한 블로그

블로그 A가 C로 이사하면 `blog.moved_to_blog_id = C`가 된다(R-08, 연쇄 이사도 최종 대상으로 갱신).

| 요청 | 처리하는 곳 | 결과 |
| --- | --- | --- |
| 화면 `a.blog.com/category/3` | `SpaForwardController` | 301 → `c.blog.com/category/3` |
| 화면 `a.blog.com/manage/...`(주인) | `SpaForwardController` | 200 (옛 블로그 관리) |
| API `a.blog.com/api/...`(주인 아님) | `@CurrentBlog` | 404 |
| API `a.blog.com/api/...`(주인) | `@CurrentBlog` | 통과 |
| 화면 `a.blog.com/15`(A에 남은 글) | `SpaForwardController` | 200 ([18](./18-spa-server-routing.md) "글 확인이 먼저") |

301 주소는 `BlogHostResolver.blogUrl`이 만든다.

```java
StringBuilder url = new StringBuilder()
        .append(request.getScheme()).append("://")                 // http 또는 https
        .append(domainProperties.blogHost(blog.getAddress()));     // c.blog.test
int port = request.getServerPort();
boolean defaultPort = ("http".equals(request.getScheme()) && port == 80)
        || ("https".equals(request.getScheme()) && port == 443);
if (!defaultPort && port > 0) {
    url.append(':').append(port);                                  // 개발에서는 :8080 또는 :5173
}
return url.append(pathAndQuery).toString();                        // 경로와 쿼리는 그대로
```

요청이 들어온 스킴과 포트를 그대로 쓰기 때문에, 개발(`http://...:8080`)과 운영(`https://...`, 포트 생략)에서 같은 코드가 맞는 주소를 만든다.

### 5.6 프론트: Vite 개발 서버의 allowedHosts와 Host 전달

`frontend/vite.config.ts`

```ts
server: {
  allowedHosts: ['.blog.test'],
  proxy: {
    '/api': 'http://localhost:8080',
    '/uploads': 'http://localhost:8080',
  },
},
```

- **allowedHosts**: Vite 개발 서버는 보안상(DNS 리바인딩 공격 방지) 처음 보는 Host로 온 요청을 403으로 거절한다. `'.blog.test'`처럼 점으로 시작하면 `blog.test`와 그 모든 하위 주소를 허용한다. 실제로 확인한 결과: `Host: alpha.blog.test:5173` → 200, `Host: evil.example:5173` → 403.
- **proxy**: 브라우저가 `alpha.blog.test:5173/api/...`로 보낸 요청을 Vite가 8080으로 넘긴다. `changeOrigin` 옵션을 켜지 않았으므로(기본값 false) **원래 Host 헤더(`alpha.blog.test:5173`)를 그대로** 넘긴다. 그래서 백엔드의 `BlogHostResolver`가 `alpha`를 찾을 수 있다. `changeOrigin: true`로 바꾸면 Host가 `localhost:8080`으로 바뀌어 모든 블로그 API가 404가 된다.

프론트에도 같은 판단이 있다. `frontend/src/app/host.ts`의 `parseHost`는 `window.location.hostname`으로 플랫폼/블로그를 나눠 다른 라우트를 그린다([19](./19-react-router-api-client.md)). 프론트는 주소 규칙(정규식, 예약어)을 검사하지 않는다. 없는 블로그는 서버가 화면을 주기 전에 404로 막기 때문이다.

## 6. 자주 하는 실수와 함정

1. **`endsWith(platform)`에서 점 빼먹기**: `host.endsWith("blog.test")`로 쓰면 `evilblog.test`가 통과한다. 반드시 `"." + platform`.
2. **`getHeader("Host")`를 그대로 쓰기**: 포트(`:8080`)가 붙어 있어 비교가 틀어진다. `getServerName()`을 쓴다.
3. **대소문자**: 도메인은 대소문자를 구분하지 않는다. 소문자로 맞추지 않으면 `Alpha.blog.test`가 다른 블로그 취급된다.
4. **hosts에 와일드카드 적기**: `127.0.0.1 *.blog.test`는 동작하지 않는다. 주소를 하나씩 적는다.
5. **새 블로그를 만들고 hosts에 안 적기**: 스텝 4에서 `mytest`라는 블로그를 만들면, `mytest.blog.test`도 hosts에 추가해야 브라우저로 열린다.
6. **"없음"과 "볼 수 없음"을 다른 응답으로 주기**: 403을 주면 "있긴 있다"는 정보가 샌다. 둘 다 404.
7. **테넌트 조건 빠뜨리기**: 블로그 API에서 글을 찾을 때 `postRepository.findById(id)`만 쓰면 다른 블로그의 글이 나온다. `@CurrentBlog`로 받은 블로그와 글의 소속을 꼭 비교한다(가시성 판단 ②).
8. **Vite 프록시에 `changeOrigin: true`**: 위 5.6. 백엔드가 블로그를 못 찾는다.
9. **운영에서 리버스 프록시 뒤에 둘 때 Host가 바뀜**: 프록시가 원래 Host를 넘기도록 설정해야 한다.
10. **dnsmasq만 켜고 `/etc/resolver/test`를 안 만듦**: macOS가 dnsmasq에 묻지 않아 여전히 NXDOMAIN이다.
11. **`dig`·`nslookup`으로 확인**: 이 둘은 macOS의 `/etc/resolver`를 거치지 않고 DNS 서버에 바로 물어서, 설정이 맞아도 "없음"이 나올 수 있다. `ping`이나 `dscacheutil -q host -a name xyz.blog.test`로 확인한다.
12. **설정을 바꿨는데 그대로**: 운영체제가 예전 답을 기억(캐시)하고 있다. `sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder`로 비우고, 브라우저는 새로 연다.
13. **dnsmasq를 쓰면서 hosts에 옛 줄을 남김**: hosts가 먼저라 그 이름은 hosts 값을 쓴다. 지금은 둘 다 127.0.0.1이라 문제없지만, 헷갈리지 않게 지운다.
14. **와일드카드 레코드만 두고 인증서는 `blog.com`용 하나만**: 블로그 주소에서 HTTPS 오류가 난다. `*.blog.com` 인증서가 따로 필요하다.

## 7. 직접 해 보기

**실습 1. hosts 등록과 Host 헤더 보기**

```bash
# 관리자 권한으로 hosts에 추가 (한 번만)
sudo sh -c 'echo "127.0.0.1 blog.test alpha.blog.test beta.blog.test gamma.blog.test" >> /etc/hosts'
ping -c 1 alpha.blog.test          # 127.0.0.1에서 응답하면 성공

./mvnw spring-boot:run
curl -v http://alpha.blog.test:8080/ 2>&1 | grep -i "^> host"   # 보낸 Host 헤더 확인
```

기대 결과: `> Host: alpha.blog.test:8080`. hosts 없이도 `curl -H "Host: alpha.blog.test" localhost:8080/`처럼 Host만 바꿔 같은 실험을 할 수 있다(curl은 IP로 연결하고 헤더만 바꾼다).

**실습 2. 주소 해석 결과 보기**

```bash
curl -s -o /dev/null -w "%{http_code}\n" -H "Host: blog.test" localhost:8080/              # 200 (플랫폼)
curl -s -o /dev/null -w "%{http_code}\n" -H "Host: nobody-here.blog.test" localhost:8080/  # 404 (없는 블로그)
curl -s -o /dev/null -w "%{http_code}\n" -H "Host: admin.blog.test" localhost:8080/        # 404 (예약어)
curl -s -o /dev/null -w "%{http_code}\n" -H "Host: a.b.blog.test" localhost:8080/          # 404 (두 단계)
curl -s -o /dev/null -w "%{http_code}\n" -H "Host: localhost" localhost:8080/              # 200 (플랫폼 밖 주소는 플랫폼처럼)
```

**실습 3. 규칙을 바꿔 테스트 깨 보기**

1. `BlogHostResolver`의 `String suffix = "." + platform;`을 `String suffix = platform;`으로 바꾼다.
2. `./mvnw test -Dtest=BlogHostResolverTest`를 돌린다.
3. 기대 결과: `unknownHosts` 테스트의 `evilblog.com` 줄이 실패한다(`Unknown`이어야 하는데 이상한 주소가 나온다). 원래대로 되돌린다.

**실습 4. 예약어 추가**

`BlogAddressRule.RESERVED`에 `"alpha"`를 넣고 `./mvnw test -Dtest=BlogAddressRuleTest`를 돌리면 `usable("alpha")`가 실패한다. 예약어 목록이 주소 해석과 규칙 테스트에 함께 영향을 준다는 것을 확인하고 되돌린다.

**실습 5. Vite 프록시의 Host**

`frontend/vite.config.ts`의 `'/api': 'http://localhost:8080'`을 `'/api': { target: 'http://localhost:8080', changeOrigin: true }`로 바꾸고, hosts가 있는 상태에서 `npm run dev` 후 `curl -i -H "Host: alpha.blog.test:5173" localhost:5173/api/test/blog`(테스트 API는 테스트 소스에만 있으므로, 실제로는 스텝 4 이후 블로그 API로 확인)를 부르면 블로그를 못 찾는다. 원래대로 되돌린다.

**실습 6. dnsmasq로 바꾸기 (명령 모음)**

`/etc/hosts`에 블로그 주소를 하나씩 넣던 방식을 dnsmasq로 바꾸고, 옛 hosts 줄을 지운다. 위에서부터 차례로 실행한다.

```bash
# ── 1. dnsmasq 설치와 규칙 ─────────────────────────────
brew install dnsmasq
echo 'address=/blog.test/127.0.0.1' >> "$(brew --prefix)/etc/dnsmasq.conf"
grep 'blog.test' "$(brew --prefix)/etc/dnsmasq.conf"      # 규칙이 들어갔는지

# ── 2. dnsmasq 켜기 (53번 포트를 쓰므로 sudo, 컴퓨터를 켤 때 자동 시작) ──
sudo brew services start dnsmasq
sudo brew services list | grep dnsmasq                  # started 이면 성공

# ── 3. .test 이름은 dnsmasq에 묻게 하기 ───────────────
sudo mkdir -p /etc/resolver
echo 'nameserver 127.0.0.1' | sudo tee /etc/resolver/test
scutil --dns | grep -A3 'domain   : test'               # resolver 등록 확인

# ── 4. 기존 /etc/hosts의 blog.test 줄 되돌리기 ─────────
sudo cp /etc/hosts /etc/hosts.backup-$(date +%Y%m%d)    # 혹시 몰라 백업
grep -n 'blog\.test' /etc/hosts                         # 지울 줄 미리 보기
sudo sed -i '' '/blog\.test/d' /etc/hosts                # blog.test가 들어간 줄만 삭제
grep -c 'blog\.test' /etc/hosts                         # 0 이면 다 지워짐

# ── 5. 캐시 비우고 확인 ───────────────────────────────
sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder
ping -c 1 alpha.blog.test                              # 127.0.0.1에서 응답
ping -c 1 xyz-anything.blog.test                       # 처음 보는 이름도 127.0.0.1
dscacheutil -q host -a name myfirst.blog.test          # ip_address: 127.0.0.1
```

브라우저는 완전히 껐다 켜거나 시크릿 창으로 `http://{아무 블로그}.blog.test:8080`을 연다.

**되돌리기 (dnsmasq를 그만 쓰고 hosts로 돌아갈 때)**

```bash
sudo brew services stop dnsmasq
sudo rm /etc/resolver/test
sudo sed -i '' '/address=\/blog.test\//d' "$(brew --prefix)/etc/dnsmasq.conf"
sudo cp /etc/hosts.backup-YYYYMMDD /etc/hosts           # 4단계에서 만든 백업 날짜로
sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder
# brew uninstall dnsmasq                                # 아예 지우려면
```

## 8. 확인 문제

1. `alpha.blog.com`에서 TLD, 2단계 도메인, 서브도메인은 각각 무엇인가?
<details><summary>답</summary>TLD는 <code>com</code>, 2단계 도메인은 <code>blog</code>(<code>blog.com</code>), 서브도메인은 <code>alpha</code>다.</details>

2. 블로그가 1만 개인데 DNS 레코드는 몇 개면 되나? 어떻게?
<details><summary>답</summary>와일드카드 레코드 <code>*.blog.com A {서버 IP}</code> 한 줄(플랫폼용 <code>blog.com</code> 레코드까지 두 줄)이면 된다. 블로그가 실제로 있는지는 서버가 DB로 판단한다.</details>

3. DNS는 `alpha.blog.com`과 `beta.blog.com`의 요청을 구분해 주나? 서버는 무엇으로 구분하나?
<details><summary>답</summary>DNS는 둘 다 같은 IP를 알려 줄 뿐 구분하지 않는다. 서버는 HTTP 요청의 Host 헤더(서블릿의 <code>getServerName()</code>)로 구분한다.</details>

4. `host.endsWith("blog.com")`으로 검사하면 어떤 문제가 생기나?
<details><summary>답</summary><code>evilblog.com</code>처럼 남의 도메인도 <code>blog.com</code>으로 끝나서 통과한다. 앞에 점을 붙여 <code>".blog.com"</code>으로 검사해야 한다.</details>

5. 정규식 `^[a-z0-9][a-z0-9-]{2,30}[a-z0-9]$`가 받는 길이는? `abc`와 `ab-`는 통과하나?
<details><summary>답</summary>4~32자다. <code>abc</code>는 3자라 실패, <code>ab-</code>는 3자이고 하이픈으로 끝나서 실패한다.</details>

6. 없는 블로그와 이용 제한된 블로그(남이 볼 때)에 각각 몇을 주나? 왜 같게 주나?
<details><summary>답</summary>둘 다 404다. 403을 주면 "그 주소에 블로그가 있다"는 정보가 새므로, 존재를 숨기기 위해 같은 응답을 준다(헌법 II).</details>

7. 로컬 개발에서 `alpha.localhost` 대신 hosts에 `alpha.blog.test`를 적는 이유는?
<details><summary>답</summary>모든 블로그 주소가 <code>Domain=.blog.test</code> 로그인 쿠키를 공유해야 하는데, <code>localhost</code>의 하위 도메인 쿠키 공유는 브라우저마다 동작이 달라 운영과 같은 구조로 확인할 수 없기 때문이다.</details>

8. Vite 프록시에서 `changeOrigin: true`를 켜면 블로그 API가 왜 깨지나?
<details><summary>답</summary>프록시가 Host 헤더를 대상 서버 주소(<code>localhost:8080</code>)로 바꿔 보내서, 백엔드가 서브도메인을 읽지 못해 플랫폼이나 알 수 없는 주소로 판단하기 때문이다.</details>

9. 브라우저가 `DNS_PROBE_FINISHED_NXDOMAIN`을 낼 때 서버 로그에 아무것도 없는 이유는?
<details><summary>답</summary>이름을 IP로 바꾸는 단계(DNS)에서 실패해 요청이 서버에 닿지도 않았기 때문이다. 서버의 Host 해석(BlogHostResolver)은 그다음 단계라 이 오류와 관계없다.</details>

10. dnsmasq를 설치하고 규칙을 넣었는데도 `alpha.blog.test`가 열리지 않는다. 무엇을 빠뜨렸을 가능성이 큰가?
<details><summary>답</summary><code>/etc/resolver/test</code>(내용 <code>nameserver 127.0.0.1</code>)를 만들지 않아 macOS가 <code>.test</code> 이름을 dnsmasq에 묻지 않는 경우다. 또는 dnsmasq가 켜지지 않았거나(<code>sudo brew services list</code>), 예전 답이 캐시에 남아 있는 경우다.</details>

11. 실제 배포에서 블로그 1만 개를 HTTPS로 열려면 DNS와 인증서에 각각 무엇이 필요한가?
<details><summary>답</summary>DNS에는 <code>*</code> A 레코드 한 줄(플랫폼용 <code>@</code> 포함), 인증서는 <code>*.blog.com</code> 와일드카드 인증서 하나다. Let's Encrypt라면 DNS-01 방식(TXT 레코드로 소유 증명)으로 받는다.</details>

## 9. 더 읽을거리

- RFC 1034/1035 (DNS 개념과 구조), RFC 2606 (`test` 등 예약 TLD), RFC 4592 (와일드카드 DNS)
- dnsmasq 설명서 `man dnsmasq`의 `--address`, macOS `man 5 resolver` (`/etc/resolver` 파일)
- Let's Encrypt 문서 "Challenge Types"의 DNS-01: https://letsencrypt.org/docs/challenge-types/
- MDN Web Docs, "Host" 헤더: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Host
- MDN Web Docs, "What is a domain name?"
- Spring Framework 레퍼런스, Web MVC "Method Arguments"와 `HandlerMethodArgumentResolver`
- Spring Boot 레퍼런스, "Type-safe Configuration Properties" (`@ConfigurationProperties`)
- Vite 문서, `server.allowedHosts`, `server.proxy`
- Java 언어 명세(JEP 409 Sealed Classes, JEP 440 Record Patterns)
