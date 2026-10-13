# 64. 캐시 저장소 고르기: 꼭 Redis여야 할까

> 관련 스텝: [스텝 8](../step-08.md) (T063), [스텝 9](../step-09.md) (T064), [스텝 20](../step-20.md) · 관련 개념: [35-spring-cache-redis](./35-spring-cache-redis.md), [17-idempotency-redis](./17-idempotency-redis.md), [40-attempt-limit](./40-attempt-limit.md), [11-jwt](./11-jwt.md), [59-hourly-snapshot-ranking](./59-hourly-snapshot-ranking.md), [02-configuration-profiles](./02-configuration-profiles.md)

> **한 줄 답**: 캐시만 보면 **꼭 Redis일 필요는 없다.** `@Cacheable` 코드는 그대로 두고 설정만 바꿔 서버 메모리(Caffeine 등)에 둘 수 있다. 그런데 이 프로젝트는 캐시 말고도 로그인 토큰·시도 횟수·연타 방지를 Redis에 두기 때문에 Redis 자체는 빠지지 않는다. 이미 있는 Redis에 캐시도 함께 두는 것이 지금 구조다.

## 1. 이 문서로 배우는 것

- 캐시 저장소의 세 갈래: **자바 Map**(`ConcurrentMapCacheManager`), **Caffeine**(서버 메모리 + 만료), **Redis**(밖의 저장소)
- 고르는 기준: 만료(TTL), 서버 재시작, 서버 여러 대, 직렬화, 준비물
- **로컬 캐시**와 **원격(분산) 캐시**의 차이
- 이 프로젝트에서 Redis가 하는 일 전부: 캐시 세 곳 + **캐시가 아닌 임시 데이터** 열한 가지 키
- 캐시만 Caffeine으로 바꾸면 무엇이 바뀌고 무엇이 그대로인가
- 두 단계 캐시(Caffeine 앞 + Redis 뒤)라는 선택지

**먼저 알면 좋은 것**: Spring 캐시 추상화와 `@Cacheable`([35](./35-spring-cache-redis.md) 3.4~3.5), Redis 기초와 TTL([17](./17-idempotency-redis.md) 3.5).

## 2. 왜 필요한가

[35](./35-spring-cache-redis.md)에서 인기 글을 5분 동안 Redis에 기억해 두는 법을 배웠다. 그러면 자연스럽게 이런 질문이 생긴다.

- "캐시 하나 때문에 Redis 컨테이너를 따로 띄워야 하나? 자바 메모리에 두면 안 되나?"
- "Redis를 빼면 무엇이 깨지나?"

저장소를 고르는 건 "빠른 것"만의 문제가 아니다. 서버를 다시 켜면 값이 남아야 하는지, 서버가 두 대가 되면 값을 같이 봐야 하는지에 따라 답이 달라진다. 이 기준을 알아야 "학습 프로젝트니까 아무거나"가 아니라 이유를 대고 고를 수 있다.

## 3. 기본 개념

### 3.1 로컬 캐시와 원격 캐시

| | 로컬 캐시 | 원격(분산) 캐시 |
| --- | --- | --- |
| 어디에 | 내 서버(JVM)의 힙 메모리 | 네트워크 너머 다른 프로세스(Redis 등) |
| 예 | `ConcurrentHashMap`, Caffeine | Redis, Memcached |
| 읽는 속도 | 나노초~마이크로초(메서드 호출) | 밀리초 안쪽(네트워크 왕복 + 직렬화) |
| 서버 재시작 | 사라짐 | 남음(Redis가 살아 있으면) |
| 서버 여러 대 | 서버마다 따로. A 서버가 지운 값이 B에는 남음 | 모두 같은 값을 봄 |
| 값 모양 | 자바 객체 그대로 | 바이트로 바꿔(직렬화) 저장 |

### 3.2 세 저장소 비교

Spring Boot는 클래스패스와 `spring.cache.type`을 보고 `CacheManager`를 고른다. 코드의 `@Cacheable`은 셋 중 무엇이든 똑같다.

| 항목 | 자바 Map (`simple`) | Caffeine (`caffeine`) | Redis (`redis`) |
| --- | --- | --- | --- |
| 준비물 | 없음(기본값) | `com.github.ben-manes.caffeine:caffeine` 의존성 | Redis 서버 + `spring-boot-starter-data-redis` |
| 만료(TTL) | **없음**. 한 번 넣으면 지울 때까지 남음 | `expireAfterWrite=5m` 등 | `spring.cache.redis.time-to-live` |
| 크기 제한 | 없음(메모리가 찰 때까지) | `maximumSize`, 자주 안 쓰는 것부터 버림 | Redis `maxmemory`와 버리는 규칙 |
| 서버 재시작 | 사라짐 | 사라짐 | 남음 |
| 서버 여러 대 | 서버마다 따로 | 서버마다 따로 | 함께 씀 |
| 직렬화 | 필요 없음 | 필요 없음 | 필요(`Serializable` 또는 JSON 설정) |
| `sync = true` | 한 서버 안에서 | 한 서버 안에서 | 한 서버 안에서(여러 서버 사이는 아님, [35](./35-spring-cache-redis.md) 3.8) |
| 어울리는 곳 | 테스트, 바뀌지 않는 값 | 서버 1대, 잠깐 기억할 값 | 서버 여러 대, 재시작에도 남아야 할 값 |

"5분마다 갱신"(HOME-02)처럼 **만료가 꼭 필요하면** 자바 Map은 빠진다. 남는 것은 Caffeine과 Redis다.

### 3.3 고르는 질문 네 개

1. **만료가 필요한가?** 필요하면 Map은 탈락.
2. **서버가 여러 대인가(또는 될 것인가)?** 여러 대에서 같은 값을 봐야 하면 Redis. 순위처럼 "서버마다 5분 안에서 조금 달라도 되는" 값이면 Caffeine도 된다.
3. **재시작해도 남아야 하나?** 캐시는 보통 "없으면 다시 계산"이라 사라져도 된다. 그래서 캐시만 놓고 보면 이 질문은 대개 "아니오"다.
4. **이미 Redis가 있나?** 있으면 캐시를 Redis에 두는 추가 비용은 의존성·설정 몇 줄이다. 없으면 캐시 하나 때문에 띄우기엔 무겁다.

### 3.4 캐시와 "캐시가 아닌 임시 데이터"

Redis에 들어 있다고 다 캐시는 아니다.

- **캐시**: 원본이 따로 있고(DB), 지워져도 다시 계산하면 된다. 예: 인기 글 순위.
- **임시 데이터(원본)**: Redis에만 있고, 지워지면 **다시 만들 수 없다.** 예: 로그인 Refresh 토큰, "5번 틀렸음" 횟수, 연타 방지 키.

임시 데이터는 지워지면 기능이 틀린다. 토큰이 사라지면 모두 로그아웃되고, 틀린 횟수가 사라지면 잠금이 풀린다. 그래서 임시 데이터는 **서버 여러 대가 같이 봐야 하고, 재시작에도 남아야** 한다. 이 요구가 Redis를 꼭 필요하게 만드는 쪽이다.

## 4. 동작 원리

### 4.1 같은 `@Cacheable`, 다른 저장소

```
HomeService.popular()
   └─ PopularRanking.snapshot()   ← @Cacheable(cacheNames = "popularPosts", key = "'home'")
         │  (프록시가 가로챔)
         ▼
     CacheManager.getCache("popularPosts").get("home")
         │
         ├─ simple   : ConcurrentHashMap.get("home")              → 자바 객체 그대로
         ├─ caffeine : Caffeine 캐시.get("home") (5분 지났으면 없음) → 자바 객체 그대로
         └─ redis    : GET blog:popularPosts::home                  → 바이트 → 역직렬화
```

어느 쪽이든 없으면 메서드 본문을 실행하고 결과를 넣는다. 바뀌는 건 맨 아래 한 줄뿐이다.

### 4.2 서버 두 대일 때

```
         ┌─ 서버 A (Caffeine) ─ popularPosts: 10:00에 계산한 순위
요청 ─ LB ┤
         └─ 서버 B (Caffeine) ─ popularPosts: 10:03에 계산한 순위
```

같은 홈을 새로고침하는데 서버에 따라 순위가 조금 다를 수 있다. 인기 글은 "최대 5분 늦어도 된다"는 명세라 이 정도는 괜찮다. 하지만 로그인 토큰을 서버 A 메모리에만 두면 서버 B로 간 요청은 "모르는 토큰"이 된다. 그래서 임시 데이터는 로컬에 둘 수 없다.

### 4.3 두 단계 캐시

큰 서비스는 둘을 겹쳐 쓰기도 한다. 먼저 Caffeine(아주 빠름, 짧은 수명)을 보고, 없으면 Redis(공유)를 보고, 그래도 없으면 DB. 네트워크 왕복을 줄이면서 서버끼리 값도 맞춘다. 대신 무효화가 두 군데라 복잡해진다. 이 프로젝트 규모에는 필요 없다.

## 5. 이 프로젝트에서는

### 5.1 캐시 설정 (`application.yml`, `global/config/CacheConfig.java`)

```yaml
spring:
  cache:
    type: redis
    redis:
      time-to-live: 5m
      key-prefix: "blog:"
```

`CacheConfig`는 `@EnableCaching`만 있고 내용이 비어 있다. 저장소 종류와 수명은 전부 위 설정이 정한다. 그래서 저장소를 바꿀 때 **자바 코드는 거의 안 고친다.**

### 5.2 캐시를 쓰는 곳 세 군데

| 캐시 이름 | 클래스 | 키 | 무엇 |
| --- | --- | --- | --- |
| `popularPosts` | `home/application/PopularRanking` | `'home'` | 홈 인기 글 순위(HOME-02) |
| `topicPosts` | `home/application/PopularRanking` | `#topic.name()` | 주제별 인기 글(HOME-03) |
| `popularBloggers` | `ranking/application/BloggerRanking` | `#hourStart.toString()` | 정시 칸 블로거 순위([59](./59-hourly-snapshot-ranking.md)) |

셋 다 `sync = true`이고, 값은 글·블로그 번호와 점수(`PostScore` 등, `Serializable`)다. 셋 다 "원본은 DB, 없으면 다시 계산"이라 **진짜 캐시**다. Caffeine으로 옮겨도 기능은 같다.

### 5.3 캐시가 아닌 Redis 사용처

코드에서 `StringRedisTemplate`을 직접 쓰는 곳이다. 지워지면 다시 만들 수 없는 값들이다.

| 키 접두어 | 클래스 | 무엇 | 지워지면 |
| --- | --- | --- | --- |
| `auth:refresh:` | `auth/domain/TokenStore` | 살아 있는 Refresh 토큰 | 모두 로그아웃 |
| `auth:blocked-access:` | `auth/domain/TokenStore` | 로그아웃한 Access 토큰 막기 | 로그아웃한 토큰이 다시 통함 |
| `attempt:` | `auth/application/AttemptLimiter` | 틀린 횟수([40](./40-attempt-limit.md)) | 잠금이 풀림 |
| `email-verification:cooldown:` | `auth/application/EmailVerificationService` | 인증 메일 1분 재요청 간격 | 메일 폭탄 가능 |
| `password-reset:cooldown:`, `password-reset:lock-notice:` | `auth/application/PasswordResetService` | 재설정 메일 간격, 잠금 안내 메일 한 번만 | 메일 여러 번 |
| `oauth:state:`, `oauth:ticket:`, `oauth:signup:` | `auth/application/SocialAuthService` | 소셜 로그인 흐름 중간값([61](./61-oauth-social-login.md)) | 진행 중이던 소셜 로그인 실패 |
| `oauth:reauth:` | `auth/application/CredentialService` | 소셜 재인증 표시 | 재인증 다시 |
| `idempotency:` | `global/web/IdempotencyInterceptor` | 연타 방지 키와 첫 응답([17](./17-idempotency-redis.md)) | 같은 글·댓글이 두 번 생길 수 있음 |

여기에 쓰인 Redis 기능(`SET NX`, `INCR`, `EXPIRE`)은 **여러 요청이 동시에 와도 하나만 통과**하게 해 준다([40](./40-attempt-limit.md) 3.3~3.4, [17](./17-idempotency-redis.md) 3.6). 자바 Map으로 흉내 낼 수는 있지만 서버 한 대 안에서만 맞고, 재시작하면 잠금·토큰이 다 사라진다.

운영 서버(`deploy/deploy.sh`)는 Redis를 `--appendonly yes`로 띄운다. 컨테이너를 다시 만들어도 이 값들이 디스크에서 돌아오게 하려는 것이다. 캐시만 있었다면 필요 없는 설정이다.

### 5.4 그래서 이 프로젝트의 답

- Redis는 5.3 때문에 **어차피 필요하다.**
- 캐시(5.2)는 Caffeine으로도 되지만, 이미 있는 Redis에 두면 추가 준비물이 없고, 서버를 늘려도 순위가 서버마다 갈리지 않는다.
- 그래서 "캐시도 Redis"는 꼭 필요해서라기보다 **한 군데로 모은 선택**이다. 설계 문서의 R-02가 이 결정이다.

### 5.5 캐시만 Caffeine으로 바꾼다면 (예시, 실제로 바꾸지 않음)

1. `pom.xml`에 의존성 추가:

```xml
<dependency>
    <groupId>com.github.ben-manes.caffeine</groupId>
    <artifactId>caffeine</artifactId>
</dependency>
```

2. `application.yml`:

```yaml
spring:
  cache:
    type: caffeine
    cache-names: popularPosts,topicPosts,popularBloggers
    caffeine:
      spec: maximumSize=500,expireAfterWrite=5m
```

3. 그대로인 것: `@Cacheable` 세 곳, `sync = true`, Redis 연결(5.3이 계속 씀).
4. 달라지는 것: Redis에 `blog:` 캐시 키가 더는 생기지 않는다. 값이 자바 객체 그대로 있어서 `Serializable`이 필요 없어진다. 테스트에서 캐시를 비우는 코드(`CacheManager`로 비움)는 그대로 동작한다. 서버를 재시작하면 순위를 다시 계산한다.

캐시마다 수명을 다르게 하고 싶으면 `CaffeineCacheManager`를 빈으로 만들어 캐시별로 등록한다. Redis 쪽은 `RedisCacheManagerBuilderCustomizer`로 같은 일을 한다.

## 6. 자주 하는 실수와 함정

- **"캐시니까 Redis"라고 외운다.** 캐시는 저장소가 아니라 쓰는 방법이다. 저장소는 설정으로 바꾼다.
- **임시 데이터를 캐시처럼 다룬다.** 토큰·시도 횟수를 "없으면 다시 계산"할 수 없는데 로컬 메모리나 만료 짧은 캐시에 두면 로그아웃·잠금이 풀린다.
- **자바 Map 캐시에 만료를 기대한다.** `spring.cache.type: simple`은 TTL이 없다. 인기 글이 서버를 다시 켤 때까지 그대로 남는다.
- **로컬 캐시인데 서버를 늘린다.** 서버마다 다른 값을 보여 준다. 지울 때(`@CacheEvict`)도 그 서버 것만 지워진다.
- **Redis 캐시에 `Serializable`이 아닌 값을 넣는다.** 로컬 캐시에서 잘 되던 코드가 Redis로 바꾸자마자 저장할 때 예외가 난다. 반대로 Caffeine으로 바꾸면 이 문제는 사라진다.
- **로컬 캐시 크기를 정하지 않는다.** 키가 많은 캐시(주제별, 사람별)를 크기 제한 없이 두면 힙이 찬다. Caffeine `maximumSize`를 준다.

## 7. 직접 해 보기

준비: `docker compose up -d`, `./mvnw spring-boot:run`.

### 7.1 Redis 안의 캐시와 임시 데이터 나눠 보기

```bash
# 홈 인기 글을 한 번 부르고, 로그인도 한 번 한 뒤
docker exec blog-redis redis-cli --scan --pattern 'blog:*'     # 캐시
docker exec blog-redis redis-cli --scan --pattern 'auth:*'     # 로그인 토큰(캐시 아님)
docker exec blog-redis redis-cli --scan --pattern 'attempt:*'  # 틀린 횟수(로그인을 일부러 틀려 본 뒤)
```

### 7.2 캐시를 지워도 괜찮고, 토큰을 지우면 안 괜찮은 것 확인

```bash
docker exec blog-redis redis-cli --scan --pattern 'blog:*' | xargs -r docker exec -i blog-redis redis-cli del
# 홈 새로고침 → 순위가 다시 계산될 뿐 정상

docker exec blog-redis redis-cli --scan --pattern 'auth:refresh:*' | xargs -r docker exec -i blog-redis redis-cli del
# 화면 새로고침 → Access 토큰이 만료되는 순간 로그인 화면으로
```

### 7.3 (공부용 브랜치에서) Caffeine으로 바꿔 보기

5.5대로 바꾸고 서버를 다시 띄운다. 홈을 부른 뒤 `redis-cli --scan --pattern 'blog:*'`가 비어 있는지 본다. `./mvnw test -Dtest=HomePopularIntegrationTest`가 그대로 통과하는지 본다. 확인 후 `git restore .`.

## 8. 확인 문제

1. `@Cacheable` 코드를 그대로 두고 저장소를 바꿀 수 있는 이유는?
<details><summary>답</summary>Spring 캐시 추상화 때문이다. `@Cacheable`은 `CacheManager`에게 이름과 키로 값을 묻기만 하고, 어떤 `CacheManager`(Map, Caffeine, Redis)를 쓸지는 `spring.cache.type`과 의존성이 정한다.</details>

2. 인기 글 캐시에 `spring.cache.type: simple`(자바 Map)을 쓰면 안 되는 이유는?
<details><summary>답</summary>TTL이 없어서 "5분마다 갱신"(HOME-02)을 지킬 수 없다. 한 번 넣은 순위가 서버를 다시 켤 때까지 남는다.</details>

3. 서버가 한 대일 때 Caffeine과 Redis 중 인기 글 캐시에 더 빠른 것은? 이 프로젝트가 그래도 Redis를 쓰는 이유는?
<details><summary>답</summary>Caffeine(같은 JVM 메모리라 네트워크 왕복과 직렬화가 없다). 이 프로젝트는 토큰·시도 횟수·연타 방지 때문에 Redis가 어차피 있어서, 캐시도 함께 두면 준비물이 늘지 않고 서버를 늘려도 순위가 서버마다 갈리지 않는다.</details>

4. 캐시와 "캐시가 아닌 임시 데이터"를 가르는 기준은?
<details><summary>답</summary>지워졌을 때 원본에서 다시 만들 수 있는가. 인기 글 순위는 DB에서 다시 계산하면 되지만, Refresh 토큰이나 틀린 횟수는 Redis에만 있어서 지워지면 다시 만들 수 없다.</details>

5. 로그인 Refresh 토큰을 서버 메모리(Map)에 두면 서버 두 대에서 무슨 일이 생기나?
<details><summary>답</summary>A 서버에서 로그인해 A 메모리에 토큰이 있어도, 다음 요청이 B 서버로 가면 B는 그 토큰을 몰라 로그인이 풀린 것처럼 동작한다. 재시작해도 모두 로그아웃된다.</details>

6. 운영 Redis를 `--appendonly yes`로 띄우는 이유는? 캐시만 있었다면 필요했을까?
<details><summary>답</summary>컨테이너를 다시 만들어도 토큰·시도 횟수 같은 임시 데이터가 디스크에서 돌아오게 하려고. 캐시만 있었다면 사라져도 다시 계산하면 되므로 필요 없다.</details>

7. 캐시를 Caffeine으로 바꾸면 `PostScore`의 `Serializable`은 아직 필요한가?
<details><summary>답</summary>캐시 때문에는 필요 없다. Caffeine은 자바 객체를 그대로 들고 있어서 직렬화하지 않는다. 다시 Redis로 돌아갈 수 있게 남겨 둬도 해는 없다.</details>

8. 로컬 캐시를 쓰는데 서버를 두 대로 늘렸다. `@CacheEvict`로 캐시를 지우면 어떻게 되나?
<details><summary>답</summary>요청을 받은 서버의 캐시만 지워진다. 다른 서버는 수명이 끝날 때까지 옛 값을 보여 준다. 그래서 서버가 여러 대면 공유 캐시(Redis)나 서버 사이 알림이 필요하다.</details>

9. 두 단계 캐시(Caffeine + Redis)의 장점과 단점은?
<details><summary>답</summary>장점: 대부분의 읽기를 같은 JVM에서 끝내 빠르고, 없을 때만 Redis를 봐서 서버끼리 값도 맞춘다. 단점: 지울 곳이 두 군데라 무효화가 복잡하고, 로컬 쪽은 서버마다 잠깐 다를 수 있다.</details>

## 9. 더 읽을거리

- Spring Boot 레퍼런스, "Caching" → "Supported Cache Providers"(Simple, Caffeine, Redis 순서와 `spring.cache.type`)
- Caffeine 위키, "Eviction"(`maximumSize`, `expireAfterWrite`, `expireAfterAccess`)
- Redis 문서, "Persistence"(RDB와 AOF, `appendonly`)
- [35](./35-spring-cache-redis.md): 이 프로젝트의 Redis 캐시 동작을 처음부터
- [17](./17-idempotency-redis.md), [40](./40-attempt-limit.md): 캐시가 아닌 Redis 사용(연타 방지, 시도 횟수)
