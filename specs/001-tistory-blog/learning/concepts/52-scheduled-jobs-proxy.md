# 52. 예약 작업: @Scheduled, 시각의 의미, 프록시 자기 호출

> 관련 스텝: [스텝 17](../step-17.md) (T103 예약 발행) · 관련 개념: [23 트랜잭션과 동시성](./23-transactions-locking.md), [35 캐시: Spring Cache와 Redis](./35-spring-cache-redis.md)(프록시), [42 두 번째 DB와 비동기 이벤트](./42-second-db-async-events.md), [47 임시저장과 자동 저장](./47-draft-autosave.md)(글의 상태), [05 Spring 테스트](./05-spring-testing.md)

## 1. 이 문서로 배우는 것

- 요청 없이 서버가 스스로 일을 하는 **예약 작업**: `@Scheduled`, `@EnableScheduling`, fixedDelay와 fixedRate와 cron
- "예약 시각"과 "작업이 실제로 돈 시각"이 다를 때 어느 것을 기록하나
- 글 상태 기계에 예약(SCHEDULED)을 더할 때 막아야 할 이동
- **프록시 자기 호출(self-invocation)**: 같은 객체 안에서 부른 `@Transactional` 메서드에 트랜잭션이 걸리지 않는 이유와, 이번 스텝에서 실제로 난 버그
- 예약 작업을 테스트하는 법: 백그라운드 작업은 끄고, 작업 메서드를 직접 부르되 **진짜 입구**도 한 번은 거치기

## 2. 왜 필요한가

명세 POST-13: "정한 날짜·시각에 공개로 바뀌고, 그 시각이 처음 발행 시각이다." 수용 시나리오(US11 2번): "내일 10시 예약 글은 그 전에 다른 사람이 보면 보이지 않는다. 10시에 공개로 바뀌고 그 시각이 발행 시각이다."

지금까지 서버의 모든 일은 **누군가의 요청**으로 시작했다. 글을 저장하라는 요청, 목록을 달라는 요청. 그런데 내일 10시에는 아무도 요청하지 않는다. 서버가 스스로 시계를 보고 일을 해야 한다.

## 3. 기본 개념

### 3.1 예약 작업을 만드는 방법들

| 방법 | 어떻게 | 언제 |
| --- | --- | --- |
| 주기적으로 훑기(polling) | 1분마다 "시각이 지난 예약 글"을 찾아 발행 | 단순, 늦어도 최대 1분. 이 프로젝트 |
| 정확한 시각에 하나씩 걸기 | 글마다 "10:00에 이 글 발행" 타이머를 메모리에 건다 | 정확하지만 서버가 재시작하면 타이머가 사라진다 |
| 외부 스케줄러·큐 | 지연 메시지 큐(예: 지연 시간을 둔 메시지), Quartz(DB에 일정 저장) | 서버 여러 대, 많은 일정 |

예약 글의 상태와 시각은 이미 DB(`post.status`, `post.scheduled_at`)에 있다. 그래서 **DB를 훑는 방식**은 서버가 꺼졌다 켜져도 놓치지 않는다. 켜진 뒤 첫 훑기에서 밀린 것을 한꺼번에 발행한다(이번 스텝에서 실제로 그랬다, 5.4).

### 3.2 Spring의 `@Scheduled`

```java
@Configuration
@EnableScheduling                         // 이 애플리케이션에서 @Scheduled를 켠다
public class SchedulingConfig { }

@Component
public class ScheduledPublisher {
    @Scheduled(fixedDelayString = "${app.scheduling.publish-delay:60000}")
    public void run() { … }
}
```

- `@EnableScheduling`이 있으면 Spring이 시작할 때 `@Scheduled` 메서드를 찾아, 스케줄러 스레드(기본 이름 `scheduling-1`)에서 주기적으로 부른다. 요청 스레드와 따로 돈다.
- **fixedDelay**: 앞 실행이 **끝난 뒤** 이만큼 쉬고 다시. 실행이 길어져도 겹치지 않는다.
- **fixedRate**: 앞 실행이 **시작한 뒤** 이만큼마다. 실행이 주기보다 길면 밀린다.
- **cron**: `"0 0 4 * * *"`(매일 4시)처럼 달력 기준. 새벽 집계(스텝 20의 방문 통계)에 맞다.
- `${app.scheduling.publish-delay:60000}`: 설정값이 있으면 그것, 없으면 60000ms(1분). 설정으로 바꿀 수 있게 열어 둔다.

### 3.3 시각 두 개: 정한 시각과 돈 시각

1분마다 훑으면 10:00 예약 글은 10:00:00~10:00:59 사이에 발행된다. 서버가 꺼져 있었다면 훨씬 늦을 수도 있다. 이때 `published_at`에 무엇을 넣나?

- **정한 시각(10:00)**: 명세가 "그 시각이 처음 발행 시각"이라고 정했다. 글 목록은 발행 시각 순이라, 작업이 늦게 돌아도 글이 **정한 자리**에 놓인다. 주인이 "10시 글, 11시 글"을 예약했다면 순서가 지켜진다.
- **돈 시각(10:00:37)**: "실제로 사람들에게 보이기 시작한 때". 이것을 따로 알고 싶으면 다른 칸이 필요하다.

이 프로젝트는 명세대로 정한 시각을 쓴다. 확인용 서버에서 03:31 예약 글이 (버그 때문에) 03:35에 발행됐을 때도 `publishedAt`은 `03:31:00`이었다(5.4).

### 3.4 프록시와 자기 호출

Spring의 `@Transactional`, `@Cacheable`([35](./35-spring-cache-redis.md)), `@Async`([42](./42-second-db-async-events.md))는 모두 **프록시**로 동작한다. 다른 빈이 받는 것은 진짜 객체가 아니라 그 객체를 감싼 대리 객체이고, 대리 객체가 메서드 호출을 가로채 "트랜잭션 시작 → 진짜 메서드 → 커밋"을 한다.

```
[다른 빈] ──→ [프록시: 트랜잭션 시작] ──→ [진짜 객체.publishDue()] ──→ [프록시: 커밋]
```

그런데 진짜 객체 **안에서** 자기 메서드를 부르면 프록시를 거치지 않는다.

```
[스케줄러] ──→ [프록시] ──→ [진짜 객체.run()] ──→ this.publishDue()   ← 프록시를 안 거침, 트랜잭션 없음
```

`this.publishDue()`의 `this`는 진짜 객체다. 그래서 `publishDue`에 `@Transactional`이 붙어 있어도 아무 일도 일어나지 않는다. 이것이 **자기 호출(self-invocation) 문제**다. Spring 문서도 프록시 방식의 한계로 명시한다.

### 3.5 트랜잭션이 없으면 무슨 일이 생기나

JPA에서 엔티티를 고치면(변경 감지) 트랜잭션이 **커밋할 때** UPDATE가 나간다([06](./06-jpa-entity-mapping.md)). 트랜잭션이 없으면:

- `findAll`은 그 호출만의 짧은 트랜잭션(Spring Data 리포지토리 메서드에 기본으로 걸린 읽기 트랜잭션)에서 읽고 끝난다. 돌려받은 엔티티는 이미 영속성 컨텍스트 밖이다.
- `post.publishScheduled()`로 자바 객체의 상태를 바꿔도, 그 객체를 지켜보는 영속성 컨텍스트가 없어서 UPDATE가 나가지 않는다.
- 오류는 없다. 로그에는 "예약 발행 1개"가 찍힌다. DB는 그대로다.
- 1분 뒤 같은 글을 또 찾아 또 "발행"한다.

## 4. 동작 원리

```
1분마다(scheduling-1 스레드, 앞 실행이 끝난 뒤 60초)
  ScheduledPublisher 프록시.run()        ← @Transactional: 여기서 트랜잭션 시작
    → publishDue()                       ← 같은 트랜잭션 안
        SELECT … WHERE status = 'SCHEDULED' AND deleted_at IS NULL AND scheduled_at <= 지금
        글마다: status = PUBLISHED, published_at = scheduled_at, visibility = PUBLIC, scheduled_at = NULL
                PostContentChangedEvent → (커밋 뒤) 추천 임베딩
  ← 커밋: UPDATE post … (글마다)
```

예약 시각 전의 글은 남에게 보이지 않는다. 이것을 위해 따로 짠 코드는 없다. 가시성 판단이 처음부터 "`PUBLISHED`인 글만 남에게"였기 때문이다([16](./16-authorization-visibility.md), [47](./47-draft-autosave.md)의 임시저장과 같다).

## 5. 이 프로젝트에서는

### 5.1 상태 기계에 예약 더하기: `Post`

```java
public static Post scheduled(Blog blog, Category category, String title, PostBody body, Visibility visibility,
                             Topic topic, LocalDateTime scheduledAt) { … status = SCHEDULED … }

public void schedule(LocalDateTime scheduledAt) { this.status = PostStatus.SCHEDULED; this.scheduledAt = scheduledAt; }

public void unschedule() {
    if (status == PostStatus.SCHEDULED) { this.status = PostStatus.DRAFT; this.scheduledAt = null; }
}

public void publishScheduled() {
    if (status != PostStatus.SCHEDULED) {
        return;
    }
    this.status = PostStatus.PUBLISHED;
    this.publishedAt = scheduledAt;
    this.visibility = Visibility.PUBLIC;
    this.scheduledAt = null;
}
```

가능한 이동:

```
        ┌────────── 저장(SCHEDULED) ──────────┐
 DRAFT ─┤                                     ▼
   ▲    └── 저장(PUBLISHED) ──→ PUBLISHED ◀── SCHEDULED ── 시각이 됨(작업)
   │                               ▲              │
   └────── 저장(DRAFT): 예약 풀기 ──┼──────────────┘
                                   └── 저장(PUBLISHED): 지금 바로 발행
```

- **발행한 글은 예약으로 못 간다**(400 `status`). 이미 사람들이 본 글을 "내일 발행"으로 되돌리는 것은 뜻이 없다. 임시저장으로도 못 간다(스텝 13).
- 예약 글을 지금 발행하면(`publish(now)`) `scheduledAt`을 지운다. 남겨 두면 작업이 다시 찾지는 않지만(status가 PUBLISHED), 화면에 "예약 시각"이 남아 헷갈린다.
- `publishScheduled`는 상태가 SCHEDULED일 때만 바꾼다. 같은 글이 두 번 불려도 두 번째는 아무것도 하지 않는다(멱등, [51](./51-subscription-notification.md) 3.1).
- 공개 범위는 발행할 때 **공개**로 바뀐다(API 명세 "그 시각에 서버가 PUBLISHED·PUBLIC으로"). 화면은 예약을 켜면 "예약 글은 정한 시각에 공개로 발행됩니다"라고 알린다.

### 5.2 입력 검사: 시계를 아는 곳에서

```java
// PostSaveRequest.checkSupported (형식)
if (status == PostStatus.SCHEDULED && scheduledAt == null) → 400 scheduledAt "예약 시각을 골라 주세요."
if (status != PostStatus.SCHEDULED && scheduledAt != null) → 400 scheduledAt "예약 시각은 예약 발행에서만 …"

// PostService.futureSchedule (지금과 비교)
if (!scheduledAt.isAfter(LocalDateTime.now(clock))) → 400 scheduledAt "예약 시각은 지금보다 뒤여야 합니다."
return scheduledAt.withNano(0);
```

- "지금보다 뒤"는 **주입받은 `Clock`**으로 본다. 요청 DTO는 시계를 모르고, 테스트가 시간을 다루기 어려워진다. 서비스에 `Clock`을 두는 이 프로젝트의 방식(스텝 8 조회 기록부터)과 같다.
- `withNano(0)`: 입력칸은 분까지 보내지만 다른 클라이언트가 나노초까지 보낼 수 있다. 초 아래를 버려 저장한 값과 화면 값이 어긋나지 않게 한다.

### 5.3 작업: `post/application/ScheduledPublisher`

```java
@Scheduled(fixedDelayString = "${app.scheduling.publish-delay:60000}")
@Transactional
public void run() {
    int published = publishDue();
    if (published > 0) {
        log.info("예약 발행 {}개", published);
    }
}

@Transactional
public int publishDue() {
    LocalDateTime now = LocalDateTime.now(clock);
    List<Post> due = postRepository.findAll((root, query, cb) -> cb.and(
            cb.equal(root.get("status"), PostStatus.SCHEDULED),
            cb.isNull(root.get("deletedAt")),
            cb.lessThanOrEqualTo(root.get("scheduledAt"), now)));
    for (Post post : due) {
        post.publishScheduled();
        events.publishEvent(new PostContentChangedEvent(post.getId()));
    }
    return due.size();
}
```

- `run()`에도 `@Transactional`이 있는 이유가 5.4의 버그다. 스케줄러는 **프록시를 통해** `run()`을 부르므로 여기서 트랜잭션이 시작되고, 안에서 부르는 `publishDue()`는 그 트랜잭션 안에서 돈다.
- 다른 고칠 방법도 있다: (1) `publishDue`를 다른 빈으로 옮긴다(가장 정석), (2) 자기 프록시를 주입받아 `self.publishDue()`, (3) `TransactionTemplate`으로 코드에서 트랜잭션을 연다. 메서드 둘이 한 클래스에 있는 지금은 입구에 트랜잭션을 거는 것이 가장 작았다.
- 지운 글(`deletedAt`)은 발행하지 않는다.
- 발행한 글은 바로 발행한 글처럼 `PostContentChangedEvent`를 낸다. 추천 임베딩(스텝 10)은 커밋 뒤에 만들어진다([42](./42-second-db-async-events.md)).
- **서버가 여러 대**가 되면 두 서버가 같은 글을 동시에 찾을 수 있다. 상태 확인(`publishScheduled`의 if)만으로는 둘 다 SCHEDULED를 읽을 수 있어서, 그때는 `SELECT … FOR UPDATE SKIP LOCKED`나 ShedLock 같은 "한 서버만 돌기" 장치가 필요하다. 지금은 한 대라 두지 않았다(코드 주석에 남김).

### 5.4 실제로 난 버그: "예약 발행 1개"가 매분

처음 코드는 `run()`에 `@Transactional`이 없었다. 통합 테스트는 모두 통과했다. 테스트가 `scheduledPublisher.publishDue()`를 **바깥에서**(프록시를 통해) 불렀기 때문이다.

확인용 서버(8081)에서 03:31 예약 글을 만들고 기다렸더니 로그가 이랬다.

```
03:32:20 … ScheduledPublisher : 예약 발행 1개
03:33:20 … ScheduledPublisher : 예약 발행 1개
```

글은 블로그 목록에 나오지 않았다. 매분 같은 글을 찾아 "발행"하고, 저장은 되지 않은 것이다(3.5). 원인을 찾은 뒤:

1. 스케줄러가 실제로 부르는 `run()`을 거쳐 DB 상태를 확인하는 테스트(`schedulerEntryPointPersistsThePublishing`)를 먼저 썼다.
2. 고치기 전 코드로 돌려 **실패하는 것**을 확인했다(`expected: "PUBLISHED"`).
3. `run()`에 `@Transactional`을 걸고 다시 돌려 통과.
4. 확인용 서버를 다시 띄우니 첫 훑기에서 밀린 글이 한 번 발행되고(`03:35:31 예약 발행 1개`), 그 뒤로는 로그가 없다. 블로그 목록의 `publishedAt`은 `03:31:00`(정한 시각).

배울 점: **테스트가 진짜 입구를 거치지 않으면 입구의 문제를 못 잡는다.** 테스트가 편하려고 안쪽 메서드를 직접 부르는 것은 좋지만, 입구를 한 번은 그대로 거쳐야 한다. 브라우저로 직접 확인하는 단계([49](./49-requirement-traceability.md) 4.3)가 없었다면 이 버그는 그대로 나갔을 것이다.

### 5.5 테스트에서는 백그라운드 작업을 끈다

```java
// global/config/SchedulingConfig.java
@Configuration
@EnableScheduling
@ConditionalOnProperty(name = "app.scheduling.enabled", havingValue = "true", matchIfMissing = true)
public class SchedulingConfig { }
```

```java
// IntegrationTestSupport
@SpringBootTest(properties = {"app.upload.dir=…", "app.scheduling.enabled=false"})
```

- `@ConditionalOnProperty`: 설정값이 `true`이거나 없을 때만 이 설정을 만든다. 테스트에서 `false`로 두면 `@EnableScheduling`이 없어 `@Scheduled`가 돌지 않는다.
- 왜 끄나: "예약 시각 전에는 안 보인다"를 확인하는 테스트에서 SQL로 예약 시각을 과거로 바꾸는 순간, 백그라운드 작업이 먼저 발행해 버리면 테스트 결과가 실행할 때마다 달라진다(가끔 실패하는 테스트). 테스트는 작업 메서드를 **원하는 때에** 직접 부른다.
- 모든 통합 테스트가 같은 설정을 써야 Spring이 컨텍스트를 재사용한다([05](./05-spring-testing.md)). 그래서 부모 클래스 한 곳에 넣었다.

### 5.6 화면

글쓰기 화면(발행하지 않은 글)에 "예약 발행" 칸이 있다. 켜면 `datetime-local` 입력칸이 열리고 버튼이 "예약 발행"으로 바뀐다. 저장하면 글 관리의 예약 목록(`/manage/posts?status=SCHEDULED`)으로 간다. 예약 글은 아직 블로그에 없어서 글 상세로 보내지 않는다.

- `datetime-local`의 값은 `"2026-10-12T09:00"`(시간대 없음, 이 컴퓨터 시계 기준)이다. 서버에 `":00"`을 붙여 보낸다. 서버는 한국 시간(Asia/Seoul, 스텝 1)으로 해석한다. 사용자와 서버의 시간대가 같다는 가정이다. 해외 사용자를 받으려면 시간대를 함께 보내야 한다.
- 예약 글은 **자동 저장하지 않는다**. 자동 저장은 `DRAFT`로 저장하는데, 예약 글을 `DRAFT`로 저장하면 예약이 풀린다(5.1). 자동 저장 판단(`autoSaveNeeded`, 스텝 13)이 이미 NEW·DRAFT일 때만 저장하도록 되어 있어 고칠 것이 없었다.
- 글 관리의 상태 필터 "예약"은 스텝 13b에서 "없는 기능의 칸"이라 뺐다(T067a). 기능이 생겨 다시 켰다.

## 6. 자주 하는 실수와 함정

- **같은 클래스 안에서 부른 `@Transactional`·`@Cacheable`·`@Async`가 동작한다고 믿는다**: 프록시를 거치지 않아 아무 일도 없다. 입구에 걸거나 다른 빈으로 옮긴다.
- **테스트가 안쪽 메서드만 부른다**: 입구(스케줄러가 부르는 메서드, 컨트롤러)의 문제를 못 잡는다. 한 번은 진짜 입구를 거친다.
- **로그만 보고 "됐다"고 믿는다**: "발행 1개"는 메서드가 돌았다는 뜻이지 저장됐다는 뜻이 아니다. DB나 API로 결과를 본다.
- **작업이 돈 시각을 발행 시각으로 쓴다**: 명세가 정한 시각과 다르고, 늦게 돌면 글 순서가 섞인다.
- **메모리 타이머로 예약한다**: 서버를 다시 켜면 사라진다. DB를 훑는다.
- **테스트에서 백그라운드 작업을 켜 둔다**: 가끔 실패하는 테스트가 생긴다. 끄고 직접 부른다.
- **서버 여러 대에서 그대로 쓴다**: 같은 글을 두 번 처리할 수 있다. 잠금이나 "한 서버만" 장치가 필요하다.
- **지난 시각 예약을 받는다**: 바로 발행과 헷갈리고 작업이 즉시 발행한다. 지금보다 뒤만 받는다.

## 7. 직접 해 보기

### 7.1 화면

준비: `./scripts/build-frontend.sh && ./mvnw spring-boot:run`, 블로그가 있는 회원.

1. 글쓰기 → 제목·본문 → "예약 발행"을 켜고 2분 뒤 시각 → "예약 발행". 글 관리의 예약 목록에 "예약 hh:mm".
2. 로그아웃하고 블로그를 보면 그 글이 없다.
3. 2~3분 뒤 새로 고치면 글이 있고, 발행 시각이 정한 시각이다. 서버 로그에 `예약 발행 1개`가 **한 번만** 찍힌다.

### 7.2 자기 호출 버그를 직접 만들어 보기

`ScheduledPublisher.run()`의 `@Transactional`을 지우고 테스트를 돌린다.

```bash
./mvnw test -Dtest='PostSettingsIntegrationTest#schedulerEntryPointPersistsThePublishing'
# expected: "PUBLISHED" but was: "SCHEDULED"
```

`publishDue()`를 직접 부르는 다른 테스트(`scheduledPostIsHiddenUntilItsTimeThenPublishedAtThatTime`)는 그래도 통과하는 것을 본다. 끝나면 `git restore .`.

### 7.3 DB에서

```sql
SELECT id, title, status, scheduled_at, published_at, visibility FROM post WHERE status = 'SCHEDULED';
```

## 8. 확인 문제

1. 예약 발행을 "글마다 메모리 타이머"가 아니라 "1분마다 DB 훑기"로 한 이유는?
<details><summary>답</summary>예약 상태와 시각이 이미 DB에 있어서, 서버가 꺼졌다 켜져도 다음 훑기에서 밀린 글을 찾아 발행한다. 메모리 타이머는 재시작하면 사라진다. 대가는 최대 1분 늦는 것이다.</details>

2. fixedDelay와 fixedRate의 차이는? 이 작업이 fixedDelay인 이유는?
<details><summary>답</summary>fixedDelay는 앞 실행이 끝난 뒤 그만큼 쉬고, fixedRate는 앞 실행 시작부터 그만큼마다다. fixedDelay면 한 번이 오래 걸려도 다음 실행과 겹치지 않는다.</details>

3. 작업이 10:00:37에 돌았는데 published_at이 10:00인 이유는?
<details><summary>답</summary>명세가 "정한 시각이 처음 발행 시각"이라고 정했고, 그래야 작업이 늦게 돌아도 글 목록 순서가 주인이 정한 대로다.</details>

4. 같은 클래스 안에서 `this.publishDue()`를 부르면 `@Transactional`이 걸리지 않는 이유는?
<details><summary>답</summary>@Transactional은 프록시가 메서드 호출을 가로채 트랜잭션을 연다. this는 프록시가 아니라 진짜 객체라 호출이 프록시를 거치지 않는다.</details>

5. 트랜잭션 없이 `post.publishScheduled()`를 부르면 오류도 없이 저장이 안 되는 이유는?
<details><summary>답</summary>변경 감지는 영속성 컨텍스트가 트랜잭션 커밋 때 바뀐 엔티티를 찾아 UPDATE를 보내는 방식이다. 트랜잭션이 없으면 findAll이 끝날 때 엔티티가 컨텍스트 밖이 되어, 객체를 바꿔도 지켜보는 쪽이 없다.</details>

6. 통합 테스트가 다 통과했는데 이 버그를 못 잡은 이유와, 더한 테스트는?
<details><summary>답</summary>테스트가 publishDue()를 바깥에서(프록시로) 불러 트랜잭션이 걸렸다. 스케줄러가 실제로 부르는 run()을 거쳐 DB의 status가 PUBLISHED인지 확인하는 테스트를 더했고, 고치기 전 코드에서 실패하는 것을 확인했다.</details>

7. 테스트에서 `app.scheduling.enabled=false`로 백그라운드 작업을 끄는 이유는?
<details><summary>답</summary>테스트가 예약 시각을 과거로 바꾼 사이에 백그라운드 작업이 먼저 발행하면 결과가 실행마다 달라진다. 끄고 테스트가 원하는 때에 작업 메서드를 직접 부른다.</details>

8. 이미 발행한 글을 예약으로 저장하면 400인 이유는?
<details><summary>답</summary>이미 사람들이 본 글을 "나중에 발행"으로 되돌리는 것은 뜻이 없고, 발행 시각과 글 순서가 바뀐다. 상태 기계에서 PUBLISHED → SCHEDULED 이동을 막는다.</details>

9. 서버를 두 대로 늘리면 이 작업에 생길 수 있는 문제와 대책은?
<details><summary>답</summary>두 서버가 같은 시각에 같은 SCHEDULED 글을 읽어 둘 다 발행(이벤트 두 번)할 수 있다. FOR UPDATE SKIP LOCKED로 행을 나눠 잡거나, ShedLock처럼 한 서버만 작업을 돌리게 한다.</details>

## 9. 더 읽을거리

- Spring Framework 문서 "Task Execution and Scheduling"(`@Scheduled`, `@EnableScheduling`)
- Spring Framework 문서 "Understanding AOP Proxies"(자기 호출의 한계)
- Spring Boot 문서 "@ConditionalOnProperty"
- ShedLock(여러 서버에서 예약 작업 하나만 돌리기), Quartz Scheduler
- MySQL 문서 "Locking Reads"(`FOR UPDATE SKIP LOCKED`)
