# 17. 멱등성과 Redis: 같은 요청이 두 번 와도 한 번만

> 관련 스텝: [스텝 3](../step-03.md) (T016), [스텝 1](../step-01.md) (T016a Redis) · 관련 개념: [04-docker-compose](./04-docker-compose.md), [07-spring-mvc-exception-handling](./07-spring-mvc-exception-handling.md), [11-jwt](./11-jwt.md), [12-spring-security-filter-chain](./12-spring-security-filter-chain.md), [19-react-router-api-client](./19-react-router-api-client.md)

## 1. 이 문서로 배우는 것

- 멱등성(idempotency)의 뜻: 수학에서, HTTP에서
- HTTP 메서드별로 무엇이 멱등이고 무엇이 아닌지
- 같은 요청이 두 번 오는 경로(더블 클릭, 재전송, 타임아웃 뒤 재시도)
- 중복을 막는 방법 세 가지(버튼 막기, DB UNIQUE, 멱등성 키) 비교
- Idempotency-Key 패턴
- Redis 기초: 인메모리 키-값 저장소, 자료형, TTL, 명령의 원자성
- `SET NX`로 "여러 요청 중 하나만 통과"를 만드는 원리와 경쟁 조건
- 이 프로젝트의 `IdempotencyInterceptor`, `ResponseCachingFilter` 코드 단계별 해설
- 이 프로젝트가 Redis를 쓰는 다른 곳(캐시, 로그인 토큰)과 redis-cli로 들여다보기

**먼저 알면 좋은 것**: HTTP 메서드(GET/POST/PUT/DELETE), Spring MVC 컨트롤러, 서블릿 필터와 인터셉터가 요청 앞뒤에 끼어든다는 정도.

## 2. 왜 필요한가

사용자가 글을 다 쓰고 "발행" 버튼을 누른다. 이런 일이 실제로 일어난다.

- **더블 클릭**: 반응이 늦어 보여서 한 번 더 누른다. 요청이 두 개 간다.
- **네트워크 재전송**: 요청은 서버에 도착해 글이 저장됐는데, 응답이 돌아오는 길에 연결이 끊긴다. 브라우저나 앱이 "실패했다"고 보고 다시 보낸다.
- **타임아웃 뒤 재시도**: 서버가 느려서 프론트가 10초 뒤 "실패"로 처리하고 사용자가 다시 누른다. 그런데 서버는 11초째에 첫 요청을 끝냈다.

결과: **같은 글이 두 개** 발행된다. 댓글이 두 번 달린다. 결제라면 두 번 결제된다.

프론트에서 버튼을 막는 것만으로는 부족하다. 재전송과 재시도는 버튼과 상관없이 일어나고, API를 직접 부르는 사람도 있다. 그래서 기능 명세(POST-01 "버튼 비활성화 + 서버 측 중복 방지", CMT-01)와 R-09가 서버에서 막으라고 요구한다.

## 3. 기본 개념

### 3.1 멱등성이란

**멱등(冪等, idempotent)**: 같은 연산을 여러 번 해도 결과가 한 번 했을 때와 같은 성질.

- 수학: `f(f(x)) = f(x)`. 예: 절댓값 `|(|-3|)| = |-3| = 3`. 0을 곱하기. 
- 멱등이 아닌 예: `x + 1`. 두 번 하면 2가 늘어난다.

HTTP에서는 "**같은 요청을 여러 번 보냈을 때 서버 상태에 미치는 효과가 한 번 보낸 것과 같다**"는 뜻이다(RFC 9110). 응답 내용이 같아야 한다는 뜻은 아니다.

### 3.2 HTTP 메서드별 멱등성

| 메서드 | 멱등? | 안전?(상태 안 바꿈) | 예 | 두 번 보내면 |
| --- | --- | --- | --- | --- |
| GET | 예 | 예 | 글 읽기 | 그냥 두 번 읽음 |
| PUT | 예 | 아니오 | 공감 켜기 `PUT /posts/1/like` | 이미 켜진 걸 또 켬 → 상태 같음 |
| DELETE | 예 | 아니오 | 공감 끄기 | 이미 꺼진 걸 또 끔 → 상태 같음 |
| POST | **아니오** | 아니오 | 글 발행 `POST /posts` | **글이 두 개** |
| PATCH | 보장 안 됨 | 아니오 | 일부 수정 | 내용에 따라 다름 |

PUT이 멱등인 이유는 "이 상태로 **만들어라**"이기 때문이다. POST는 "새로 **하나 만들어라**"라서 두 번이면 두 개다.

그래서 이 프로젝트는 R-09에서 이렇게 나눴다.
- **공감·저장·구독**: 켜기 `PUT`, 끄기 `DELETE` + DB UNIQUE 제약. 이미 켜진 것을 켜도 200(rest-api.md "연타 방지").
- **글 발행·임시저장 생성, 댓글·방명록 작성**: POST라 멱등이 아니다 → **Idempotency-Key**로 멱등하게 만든다.

### 3.3 중복을 막는 세 가지 방법

| 방법 | 어떻게 | 막는 것 | 못 막는 것 |
| --- | --- | --- | --- |
| 버튼 비활성화 | 누르면 응답 올 때까지 버튼 끔 | 더블 클릭 | 재전송, 재시도, API 직접 호출 |
| DB UNIQUE 제약 | `UNIQUE(member_id, post_id)` | "한 사람이 한 글에 공감 하나"처럼 **자연스러운 중복 기준이 있는** 경우 | 글·댓글처럼 같은 내용을 여러 번 쓰는 게 정상인 경우 |
| 멱등성 키 | 요청마다 클라이언트가 고유 키를 붙이고, 서버가 키를 기억 | 모든 재전송·재시도 | 사용자가 **새로** 쓴 요청(키가 다름)은 막지 않음(막으면 안 됨) |

댓글은 같은 사람이 같은 글에 "감사합니다"를 두 번 쓸 수도 있다. 그래서 UNIQUE로는 "실수로 두 번 간 것"과 "일부러 두 번 쓴 것"을 구분할 수 없다. **키**는 "같은 버튼 누름에서 나온 요청"을 묶어 주므로 둘을 구분한다.

### 3.4 Idempotency-Key 패턴

```
클라이언트                                            서버
  │ 발행 버튼 누름 → 키 K = 새 UUID 생성
  │── POST /api/posts  Idempotency-Key: K ──────────▶│ K 처음 봄 → 실행 → 글 #31 생성
  │◀──────────── (응답이 중간에 사라짐) ──────────────│ "K → 201 {id:31}" 기억
  │ 실패로 보고 재시도 (같은 K!)
  │── POST /api/posts  Idempotency-Key: K ──────────▶│ K 본 적 있음 → 실행 안 함
  │◀──────────── 201 {id:31} (기억해 둔 응답) ────────│
```

규칙:
- 키는 **클라이언트가 만든다**. 서버가 만들면 첫 요청이 실패했을 때 클라이언트는 키를 모른다.
- **같은 행동의 재시도에는 같은 키**, 새 행동에는 새 키. 프론트에서는 "발행 버튼을 누를 때 한 번" 만들어 재시도에 재사용한다.
- 서버는 키를 **일정 시간만** 기억한다(이 프로젝트 10분). 영원히 기억하면 저장소가 끝없이 커진다.
- 결제 API(예: Stripe)들이 같은 이름의 `Idempotency-Key` 헤더를 쓰는 업계 관행이고, IETF에서 표준 헤더로 정리하는 초안도 있다.

### 3.5 Redis 기초

**Redis**는 데이터를 **메모리**에 두는 키-값 저장소다.

| 특징 | 뜻 | 그래서 |
| --- | --- | --- |
| 인메모리 | 디스크가 아니라 RAM에 저장 | 매우 빠름(보통 1ms 미만). 대신 용량이 비싸고, 설정에 따라 재시작 시 사라질 수 있음 |
| 키-값 | `키 → 값` 사전 | SQL처럼 조인·복잡한 검색은 못 함 |
| 자료형 | 문자열(String), 리스트(List), 해시(Hash), 셋(Set), 정렬된 셋(Sorted Set) 등 | 랭킹은 Sorted Set, 카운터는 String + INCR 등 |
| TTL | 키마다 수명(초)을 줄 수 있음. 시간이 지나면 Redis가 지움 | 캐시, 임시 기록, 세션에 딱 맞음 |
| 명령 단위 원자성 | 명령을 **하나씩 차례로** 실행한다(명령 처리는 단일 스레드) | 명령 하나는 중간에 다른 명령이 끼어들 수 없음 |

기본 명령:

```
SET k v            k에 v 저장
GET k              k의 값
DEL k              k 지우기
EXPIRE k 600       k의 수명을 600초로
TTL k              k의 남은 수명(초). -1은 수명 없음, -2는 키 없음
SET k v NX EX 600  k가 "없을 때만" 저장하고 수명 600초. 저장했으면 OK, 이미 있으면 nil
KEYS 패턴           패턴에 맞는 키 목록 (운영 서버에서는 느려서 쓰지 않는다. SCAN을 쓴다)
```

DB(MySQL)가 아니라 Redis에 두는 이유: 멱등성 키는 10분만 필요한 임시 데이터고, 요청마다 읽고 쓰므로 빨라야 한다. TTL로 알아서 지워지는 것도 딱 맞다.

### 3.6 `SET NX`로 "하나만 통과"

두 요청이 **동시에** 같은 키로 왔다고 하자. 이렇게 짜면 안 된다.

```java
// 나쁜 예: 확인과 저장이 두 단계
if (redis.get(key) == null) {      // 요청 A: 없음 확인  ┐  같은 순간
                                   // 요청 B: 없음 확인  ┘  B도 없다고 봄
    redis.set(key, "PENDING");     // A, B 둘 다 저장
    실행();                         // 둘 다 실행 → 글 두 개
}
```

"확인"과 "저장" 사이에 다른 요청이 끼어드는 것을 **경쟁 조건(race condition)**이라 한다. 해결은 확인과 저장을 **명령 하나**로 하는 것이다.

```java
// 좋은 예: SET NX 한 번
if (redis.setIfAbsent(key, "PENDING", ttl)) {   // SET key PENDING NX PX ...
    실행();      // 저장에 성공한 딱 한 요청만 여기로
} else {
    // 이미 누가 먼저 저장함 → 처음 요청의 결과를 기다렸다 돌려준다
}
```

Redis는 명령을 하나씩 실행하므로, A와 B의 `SET NX`가 동시에 와도 하나가 먼저 실행되고 다른 하나는 "이미 있음"을 받는다. 이 방식은 간단한 **분산 락**을 만들 때도 쓴다. 서버가 여러 대여도 Redis가 하나면 모든 서버가 같은 판정을 받는다(서버 메모리의 `HashMap`으로는 서버끼리 공유가 안 된다).

## 4. 동작 원리

이 프로젝트에서 `@Idempotent`가 붙은 POST API로 요청이 오면:

```
요청 ─▶ [Spring Security 필터들] ─▶ ResponseCachingFilter ─▶ DispatcherServlet
                                     (응답을 메모리에 잡는         │
                                      wrapper로 감쌈)              ▼
                                                     IdempotencyInterceptor.preHandle
                                                       ├ @Idempotent 아니면 통과
                                                       ├ 키 없거나 UUID 아님 → 400
                                                       ├ SET NX 성공 → 통과(컨트롤러 실행)
                                                       └ SET NX 실패 → 첫 응답 기다려 그대로 씀, 컨트롤러 실행 안 함
                                                                   │
                                                     컨트롤러 실행 → 응답 본문이 wrapper에 쌓임
                                                                   │
                                                     IdempotencyInterceptor.afterCompletion
                                                       ├ 2xx면 (상태, Content-Type, Location, 본문)을 같은 키에 저장
                                                       └ 아니면 키 삭제(다시 시도 가능)
                                                                   │
                     ResponseCachingFilter: wrapper.copyBodyToResponse() → 실제 응답으로 내보냄
```

### 4.1 필터와 인터셉터를 둘 다 쓰는 이유

- **인터셉터(HandlerInterceptor)**는 DispatcherServlet 안에서 동작해서 **어느 컨트롤러 메서드가 실행되는지** 안다. 그래서 `@Idempotent` 애노테이션을 볼 수 있다.
- 그런데 인터셉터는 응답 본문을 다시 읽을 수 없다. 서블릿 응답은 **한 번 쓰면 흘러가 버리는 스트림**이기 때문이다.
- **필터**는 DispatcherServlet 바깥에서 응답 객체 자체를 **바꿔 끼울** 수 있다. `ContentCachingResponseWrapper`로 감싸면, 컨트롤러가 쓴 본문이 바로 나가지 않고 메모리에 모인다. 인터셉터는 그 메모리에서 본문을 읽어 Redis에 저장한다.
- 다 끝나면 필터가 `copyBodyToResponse()`로 모아 둔 본문을 진짜 응답으로 보낸다. **이걸 빼먹으면 클라이언트는 빈 응답을 받는다.**

## 5. 이 프로젝트에서는

### 5.1 @Idempotent

`src/main/java/com/nhnacademy/blog/global/web/Idempotent.java`

```java
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
public @interface Idempotent {
}
```

- `@Target(METHOD)`: 메서드에만 붙인다.
- `@Retention(RUNTIME)`: 실행 중에도 애노테이션 정보가 남아, 인터셉터가 `hasMethodAnnotation`으로 읽을 수 있다(기본값 CLASS면 실행 중에 사라진다).

스텝 5부터 글 발행 API에 이렇게 붙인다.

```java
@Idempotent
@PostMapping("/api/posts")
public ResponseEntity<PostResponse> create(...) { ... }
```

### 5.2 ResponseCachingFilter

`src/main/java/com/nhnacademy/blog/global/web/ResponseCachingFilter.java`

```java
@Override
protected boolean shouldNotFilter(HttpServletRequest request) {
    return !("POST".equals(request.getMethod()) && request.getRequestURI().startsWith("/api/"));
}

@Override
protected void doFilterInternal(...) {
    ContentCachingResponseWrapper wrapper = new ContentCachingResponseWrapper(response);
    try {
        chain.doFilter(request, wrapper);     // 뒤쪽(컨트롤러)에는 wrapper를 넘긴다
    } finally {
        wrapper.copyBodyToResponse();         // 무슨 일이 있어도 본문을 실제 응답으로 보낸다
    }
}
```

- `OncePerRequestFilter`: 한 요청에 한 번만 실행되는 것을 보장하는 Spring의 필터 부모 클래스.
- `shouldNotFilter`: POST API만 감싼다. 모든 응답을 메모리에 모으면 큰 파일 응답 등에서 메모리를 낭비하기 때문이다.
- `finally`: 예외가 나도 본문을 보내야 하므로.
- `@Component`라서 Spring Boot가 서블릿 필터로 자동 등록한다. Spring Security 필터 체인 뒤에 실행된다([12](./12-spring-security-filter-chain.md)).

### 5.3 IdempotencyInterceptor 단계별

`src/main/java/com/nhnacademy/blog/global/web/IdempotencyInterceptor.java`

**상수**

```java
public static final String HEADER = "Idempotency-Key";
private static final String KEY_PREFIX = "idempotency:";
private static final String PENDING = "PENDING";
private static final Duration WAIT_LIMIT = Duration.ofSeconds(3);
private static final long WAIT_STEP_MILLIS = 100;
```

**① 대상인지 확인**

```java
if (!(handler instanceof HandlerMethod method) || !method.hasMethodAnnotation(Idempotent.class)) {
    return true;
}
```

`handler`는 이 요청을 처리할 대상이다. 컨트롤러 메서드면 `HandlerMethod`다(정적 파일 처리 등은 다른 타입). `instanceof HandlerMethod method`는 타입 확인과 변수 선언을 한 번에 하는 패턴 매칭이다. `@Idempotent`가 없으면 바로 통과(`true` = 계속 진행).

**② 키 읽기와 검증**

```java
private String readKey(HttpServletRequest request) {
    String key = request.getHeader(HEADER);
    try {
        return UUID.fromString(key == null ? "" : key.strip()).toString();
    } catch (IllegalArgumentException e) {
        throw new BusinessException(ErrorCode.IDEMPOTENCY_KEY_REQUIRED);
    }
}
```

- 키가 없거나 UUID 형식이 아니면 400 `IDEMPOTENCY_KEY_REQUIRED`. 인터셉터에서 던진 예외도 `GlobalExceptionHandler`가 받아 COM-02 모양으로 만든다([07](./07-spring-mvc-exception-handling.md)).
- `UUID.fromString(...).toString()`으로 다시 문자열로 만들면 대문자로 온 키도 소문자 표준형으로 맞춰진다. 같은 키를 다르게 적어 다른 키로 취급되는 일을 막는다.
- 형식을 UUID로 제한하는 이유: 아무 문자열이나 받으면 너무 짧은 키(`"1"`)가 우연히 겹치거나, 아주 긴 키로 Redis를 채울 수 있다.

**③ Redis 키 만들기: 회원·경로마다 따로**

```java
private String redisKey(HttpServletRequest request, String key) {
    Long memberId = LoginMembers.currentId();
    return KEY_PREFIX + (memberId == null ? "anonymous" : memberId) + ":" + request.getMethod() + ":"
            + request.getRequestURI() + ":" + key;
}
```

예: `idempotency:42:POST:/api/posts:3f2b...`

- **회원 id를 넣는 이유**: 키만 쓰면 다른 사람이 같은 UUID를 보냈을 때(실수든 악의든) **남의 응답(남의 글 내용)**을 받게 된다. 회원별로 나누면 그럴 수 없다.
- **경로를 넣는 이유**: 같은 키를 실수로 댓글 API와 글 API에 함께 쓰면, 댓글 요청에 글 응답이 나가는 일이 생긴다.

**④ SET NX: 하나만 통과**

```java
if (Boolean.TRUE.equals(redis.opsForValue().setIfAbsent(redisKey, PENDING, properties.ttl()))) {
    request.setAttribute(ATTRIBUTE, redisKey);
    return true;
}
replay(response, waitForFirstResponse(redisKey));
return false;
```

- `setIfAbsent(key, value, ttl)`는 Redis의 `SET key value NX PX ttl` 한 명령이다. 처음 온 요청만 `true`를 받는다.
- 값은 `PENDING`(처리 중). TTL은 `app.idempotency.ttl`(10분).
- 통과한 요청은 키를 요청 속성(`request.setAttribute`)에 적어 둔다. `afterCompletion`에서 "내가 키 주인인가"를 알기 위해서다.
- `Boolean.TRUE.equals(...)`로 비교하는 이유: Redis 템플릿이 `null`을 돌려줄 수 있어서(파이프라인·트랜잭션 중), `if (result)`로 쓰면 NPE가 날 수 있다.
- 실패한 요청은 첫 요청의 응답을 기다렸다가 그대로 쓰고, `false`를 돌려 **컨트롤러를 실행하지 않는다**.

**⑤ 기다리기: 동시에 온 두 번째 요청**

```java
private StoredResponse waitForFirstResponse(String redisKey) {
    long deadline = System.nanoTime() + WAIT_LIMIT.toNanos();
    while (System.nanoTime() < deadline) {
        String value = redis.opsForValue().get(redisKey);
        if (value != null && !PENDING.equals(value)) {
            return jsonMapper.readValue(value, StoredResponse.class);   // 첫 응답이 저장됨
        }
        if (value == null) {
            break;                       // 첫 요청이 실패해 키가 지워짐
        }
        sleep();                         // 아직 PENDING → 0.1초 쉬고 다시
    }
    throw new BusinessException(ErrorCode.TOO_MANY_REQUESTS, Map.of("retryAfterSeconds", 1));
}
```

| 상황 | 결과 |
| --- | --- |
| 첫 요청이 끝나 응답이 저장됨 | 그 응답을 돌려줌 |
| 첫 요청이 3초 넘게 처리 중 | 429 `TOO_MANY_REQUESTS`, `retryAfterSeconds: 1` |
| 첫 요청이 실패해 키가 지워짐 | 429. 클라이언트가 같은 키로 다시 보내면 이번엔 처음 요청이 된다 |

`System.nanoTime()`은 경과 시간을 잴 때 쓰는 시계다. `System.currentTimeMillis()`는 시스템 시계를 사람이 바꾸면 거꾸로 갈 수 있어 경과 시간 측정에 맞지 않다.

**⑥ 첫 응답 다시 쓰기(replay)**

```java
response.setStatus(stored.status());
if (stored.contentType() != null) response.setContentType(stored.contentType());
if (stored.location() != null) response.setHeader(HttpHeaders.LOCATION, stored.location());
response.setCharacterEncoding(StandardCharsets.UTF_8.name());
response.getWriter().write(stored.body());
```

상태 코드(201), `Location`(새 글 주소), 본문을 첫 응답과 같게 쓴다.

**⑦ 끝난 뒤: 저장하거나 지우기**

```java
public void afterCompletion(HttpServletRequest request, HttpServletResponse response, Object handler, Exception ex) {
    String redisKey = (String) request.getAttribute(ATTRIBUTE);
    if (redisKey == null) return;                                 // 키 주인이 아니면 할 일 없음
    ContentCachingResponseWrapper cached = WebUtils.getNativeResponse(response, ContentCachingResponseWrapper.class);
    boolean success = ex == null && response.getStatus() >= 200 && response.getStatus() < 300;
    if (!success || cached == null) {
        redis.delete(redisKey);                                   // 실패 → 키를 지워 재시도 허용
        return;
    }
    StoredResponse stored = new StoredResponse(response.getStatus(), response.getContentType(),
            response.getHeader(HttpHeaders.LOCATION),
            new String(cached.getContentAsByteArray(), StandardCharsets.UTF_8));
    redis.opsForValue().set(redisKey, jsonMapper.writeValueAsString(stored), properties.ttl());
}
```

- `afterCompletion`은 컨트롤러와 예외 처리가 다 끝난 뒤 불린다. 예외가 `@RestControllerAdvice`에서 400·409 같은 응답으로 바뀌었으면 `ex`는 null이지만 상태 코드가 2xx가 아니다.
- **실패하면 지우는 이유**: 입력 오류(400)로 실패한 요청에 같은 키를 다시 보내면, 지우지 않았다면 "400"을 영원히(10분) 돌려받는다. 사용자가 입력을 고쳐 다시 보내도 통과하지 못한다.
- `WebUtils.getNativeResponse`: 응답이 여러 겹으로 감싸여 있을 때 그중 `ContentCachingResponseWrapper`를 찾아 준다.
- 저장 형식은 JSON 문자열이다. 예: `{"status":201,"contentType":"application/json","location":"/api/test/idempotent/7","body":"{\"id\":7}"}`

### 5.4 테스트로 확인한 것

`src/test/.../global/web/IdempotencyIntegrationTest.java`, 테스트 전용 API `src/test/.../support/TestIdempotentController.java`(실제로 실행된 횟수를 `AtomicInteger`로 센다).

| 테스트 | 확인하는 것 |
| --- | --- |
| `missingOrMalformedKeyIs400` | 키가 없거나 UUID가 아니면 400, 컨트롤러 실행 안 됨 |
| `sameKeyTwiceGivesOneResult` | 같은 키 두 번 → 실행 1번, 두 응답의 본문·Location이 같음 |
| `differentKeysOrMembersAreDifferentRequests` | 다른 키, 같은 키라도 다른 회원 → 각각 실행 |
| `failedFirstRequestCanBeRetriedWithSameKey` | 409로 실패하면 같은 키로 다시 실행됨 |
| `concurrentDoubleClickRunsOnce` | 두 스레드가 **동시에** 같은 키로 요청(컨트롤러가 0.3초 걸림) → 실행 1번, 두 응답 모두 201이고 같음 |

마지막 테스트가 `SET NX`의 원자성을 실제로 확인한다. 두 번째 요청은 ⑤에서 0.1초씩 기다리다가 첫 응답을 받는다.

### 5.5 공감·구독은 다른 방법(R-09)

공감은 `post_like`에 `UNIQUE(member_id, post_id)`가 있다(ERD). 켜기 `PUT`이 두 번 와도:
- 두 번째 INSERT는 UNIQUE 위반 → 서비스가 "이미 켜짐"으로 처리하고 200.
- 그래서 멱등성 키가 필요 없다. 자연스러운 중복 기준(한 사람, 한 글)이 있기 때문이다.

### 5.6 Redis를 쓰는 다른 곳

| 용도 | 키 모양 | TTL | 코드 |
| --- | --- | --- | --- |
| 멱등성 키 | `idempotency:{회원}:{메서드}:{경로}:{UUID}` | 10분 | `IdempotencyInterceptor` |
| Refresh 토큰(살아 있는 것만) | `auth:refresh:{토큰 id}` | 로그인 유지 14일 / 아니면 무활동 30분, 요청마다 연장 | `TokenStore` ([11](./11-jwt.md)) |
| 로그아웃한 Access 토큰 | `auth:blocked-access:{토큰 id}` | 토큰 만료 때까지 | `TokenStore` |
| Spring Cache | `blog:`로 시작 | 5분 | `CacheConfig`, `application.yml`의 `spring.cache` (인기 글 등 스텝 8) |

Spring Cache(`@Cacheable`)는 메서드 결과를 저장해 두었다가, 같은 인자로 다시 부르면 메서드를 실행하지 않고 저장해 둔 결과를 준다. `spring.cache.type: redis`라 저장소가 Redis이고, `time-to-live: 5m`이라 5분 뒤 다시 계산한다.

```java
@Cacheable("popularPosts")              // 스텝 8에서 이런 식으로 쓴다
public List<PostSummary> popularPosts() { ... 무거운 계산 ... }
```

## 6. 자주 하는 실수와 함정

1. **확인과 저장을 두 명령으로**: `GET` 후 `SET`은 동시 요청에 뚫린다. `SET NX` 한 명령.
2. **`copyBodyToResponse()` 빼먹기**: 클라이언트가 빈 응답을 받는다. 반드시 `finally`에서.
3. **실패한 응답까지 저장**: 400이 10분간 굳는다. 2xx만 저장한다.
4. **키를 회원·경로와 섞지 않기**: 남의 응답이 새거나 다른 API 응답이 나갈 수 있다.
5. **재시도에 새 키 만들기**: 프론트가 재시도할 때마다 `newIdempotencyKey()`를 새로 부르면 중복 방지가 안 된다. 키는 "사용자 행동 한 번"에 하나다([19](./19-react-router-api-client.md)).
6. **`@Idempotent`를 POST가 아닌 메서드에 붙이기**: `ResponseCachingFilter`는 POST API만 감싸므로, PUT 등에 붙이면 응답을 저장하지 못하고(`cached == null`) 매번 키를 지운다. 결과적으로 **조용히 중복 방지가 안 된다**. 지금 대상 API는 모두 POST라 문제없지만, 다른 메서드에 붙일 일이 생기면 필터 조건도 함께 바꿔야 한다.
7. **서버가 처리 중에 죽음**: 키가 `PENDING`으로 남아, 같은 키로 다시 보내면 TTL(10분)이 끝날 때까지 429를 받는다. 사용자가 새로 누르면 새 키라 괜찮지만, 같은 키로 자동 재시도하는 클라이언트는 10분을 기다려야 한다.
8. **replay는 일부 헤더만 되살린다**: 상태, Content-Type, Location, 본문만 저장한다. 첫 응답에 `Set-Cookie` 같은 다른 헤더가 있었다면 두 번째 응답에는 없다. 지금 대상 API(글·댓글 생성)에는 그런 헤더가 없다.
9. **운영 Redis에서 `KEYS *`**: 키가 많으면 Redis 전체가 멈춘다. 운영에서는 `SCAN`을 쓴다.

## 7. 직접 해 보기

**실습 1. Redis 명령 직접 쳐 보기**

```bash
docker compose up -d
docker exec -it blog-redis redis-cli
```

```
127.0.0.1:6379> SET demo hello NX EX 30
OK
127.0.0.1:6379> SET demo world NX EX 30
(nil)                                 ← 이미 있어서 실패
127.0.0.1:6379> GET demo
"hello"
127.0.0.1:6379> TTL demo
(integer) 25                          ← 남은 초
127.0.0.1:6379> DEL demo
```

두 터미널을 열고 동시에 `SET lock 1 NX EX 30`을 쳐 보면 하나만 OK를 받는다.

**실습 2. 연타 방지 테스트 돌리기**

```bash
./mvnw test -Dtest=IdempotencyIntegrationTest
```

**실습 3. 경쟁 조건을 일부러 만들어 보기**

1. `IdempotencyInterceptor.preHandle`의 `setIfAbsent` 줄을 아래처럼 "확인 후 저장"으로 바꾼다.
   ```java
   if (redis.opsForValue().get(redisKey) == null) {
       try { Thread.sleep(50); } catch (InterruptedException e) { }   // 틈을 넓힌다
       redis.opsForValue().set(redisKey, PENDING, properties.ttl());
       request.setAttribute(ATTRIBUTE, redisKey);
       return true;
   }
   ```
2. `./mvnw test -Dtest=IdempotencyIntegrationTest#concurrentDoubleClickRunsOnce`
3. 기대 결과: 실행 횟수가 2가 되어 실패한다. 원래대로 되돌린다.

**실습 4. copyBodyToResponse를 지워 보기**

`ResponseCachingFilter`의 `wrapper.copyBodyToResponse();`를 주석 처리하고 `sameKeyTwiceGivesOneResult`를 돌리면, 응답 본문이 비어 비교가 깨진다. 되돌린다.

**실습 5. 서버에서 키 들여다보기** (스텝 5에서 글 발행 API가 생긴 뒤)

```bash
docker exec blog-redis redis-cli --scan --pattern 'idempotency:*'
docker exec blog-redis redis-cli GET 'idempotency:...'     # 저장된 응답 JSON
docker exec blog-redis redis-cli --scan --pattern 'auth:*' # 로그인하면 생기는 토큰 키
```

## 8. 확인 문제

1. PUT은 멱등이고 POST는 아닌 이유를 공감 켜기와 글 발행으로 설명하라.
<details><summary>답</summary>공감 켜기 PUT은 "켜진 상태로 만들어라"라서 두 번 해도 켜진 상태 하나다. 글 발행 POST는 "새 글을 하나 만들어라"라서 두 번 하면 글이 둘이 된다.</details>

2. 댓글 중복을 DB UNIQUE 제약으로 막기 어려운 이유는?
<details><summary>답</summary>같은 사람이 같은 글에 같은 내용의 댓글을 일부러 여러 번 쓰는 것도 정상이라, "실수로 두 번 간 요청"과 구분할 자연스러운 중복 기준이 없기 때문이다.</details>

3. 멱등성 키를 서버가 아니라 클라이언트가 만드는 이유는?
<details><summary>답</summary>첫 요청의 응답이 사라지면 클라이언트는 서버가 만든 키를 받지 못해 재시도에 같은 키를 쓸 수 없다. 클라이언트가 보내기 전에 만들어야 재시도에 같은 키를 붙일 수 있다.</details>

4. `GET`으로 없는 것을 확인한 뒤 `SET`하는 코드가 동시 요청에 뚫리는 이유와 해결책은?
<details><summary>답</summary>두 요청이 둘 다 "없음"을 확인한 뒤 둘 다 저장하는 경쟁 조건이 생긴다. 확인과 저장을 한 명령으로 하는 <code>SET NX</code>(<code>setIfAbsent</code>)를 쓰면 Redis가 명령을 하나씩 실행하므로 하나만 성공한다.</details>

5. 인터셉터만으로 응답 본문을 저장할 수 없는 이유와, 필터가 하는 일은?
<details><summary>답</summary>서블릿 응답은 한 번 쓰면 흘러가는 스트림이라 나중에 다시 읽을 수 없다. 필터가 응답을 <code>ContentCachingResponseWrapper</code>로 바꿔 끼워 본문을 메모리에 모으고, 끝나면 <code>copyBodyToResponse()</code>로 실제 응답에 보낸다.</details>

6. 첫 요청이 400으로 실패했을 때 키를 지우는 이유는?
<details><summary>답</summary>지우지 않으면 같은 키로 다시 보낸 요청이 TTL 동안 계속 400을 돌려받아, 입력을 고쳐 다시 보내도 처리되지 않기 때문이다.</details>

7. Redis 키에 회원 id를 넣지 않으면 어떤 문제가 생기나?
<details><summary>답</summary>다른 사람이 같은 UUID를 보냈을 때 남의 첫 응답(글 내용 등)을 그대로 받을 수 있다.</details>

8. 이 프로젝트에서 Redis를 쓰는 곳 세 가지는?
<details><summary>답</summary>멱등성 키(10분), 로그인 토큰 상태(살아 있는 Refresh 토큰, 로그아웃한 Access 토큰), Spring Cache(<code>@Cacheable</code>, 5분).</details>

## 9. 더 읽을거리

- RFC 9110 HTTP Semantics, 9.2.2 "Idempotent Methods"
- IETF 초안 "The Idempotency-Key HTTP Header Field"
- Redis 공식 문서: SET 명령(NX, EX, PX 옵션), EXPIRE, Data types: https://redis.io/docs/
- Spring Data Redis 레퍼런스, `StringRedisTemplate`, `ValueOperations.setIfAbsent`
- Spring Framework 레퍼런스, `HandlerInterceptor`, `ContentCachingResponseWrapper`
- Spring Boot 레퍼런스, "Caching" (Redis 캐시 설정)
- research.md R-09 (연타 방지 결정)
