# 34. 조회수: 누가 봤는지 알아보기, 5분 중복 판정, 동시 새로고침

> 관련 스텝: [스텝 8](../step-08.md) (T053) · 관련 개념: [10-http-cookies](./10-http-cookies.md), [23-transactions-locking](./23-transactions-locking.md), [33-isolation-deadlock](./33-isolation-deadlock.md), [16-authorization-visibility](./16-authorization-visibility.md), [25-react-forms-data](./25-react-forms-data.md)

## 1. 이 문서로 배우는 것

- "조회수"가 생각보다 어려운 이유: **누가** 봤는지, **언제 다시 본 것을 새 조회로 칠지**, **동시에 온 요청**을 어떻게 하나로 볼지
- 조회자를 구분하는 키 `viewer_key`: 회원은 회원 id, 비회원은 서버가 준 **방문자 쿠키**(`visitor_id`)
- 쿠키 값을 믿지 않는 법: UUID 모양만 받기
- 시간 창(time window) 중복 판정: "최근 5분 안에 본 기록이 있나"를 인덱스 하나로 묻기
- 조회 기록 테이블(`view_log`)과 누적 칸(`post.view_count`)을 **둘 다** 두는 이유
- 같은 사람이 새로고침을 연타할 때 생기는 경쟁 조건과, 글 행 잠금(`lockById`)으로 줄 세우기
- **잠금이 트랜잭션의 첫 문장이어야 하는 이유**(REPEATABLE READ의 스냅샷, [33](./33-isolation-deadlock.md)의 버그 2와 같은 원리)
- 가시성 확인과 기록을 **다른 트랜잭션**으로 나눈 이유
- 화면: 본문이 보인 뒤 한 번만 보내기, 개발 모드(StrictMode)에서 effect가 두 번 도는 문제

**먼저 알면 좋은 것**: 쿠키 속성(`HttpOnly`, `Domain`, `Max-Age`, [10](./10-http-cookies.md)), `@Transactional`과 `FOR UPDATE`([23](./23-transactions-locking.md)), 일관된 읽기와 잠금 읽기, 외래 키 공유 잠금([33](./33-isolation-deadlock.md)).

## 2. 왜 필요한가

명세 POST-09는 한 줄이다. "글을 열면 조회수가 오른다. 같은 사용자가 5분 안에 다시 열면 1회만 센다. 최근 1시간 조회수를 셀 수 있게 조회마다 시각을 남긴다."

이 한 줄에 질문이 세 개 숨어 있다.

1. **"같은 사용자"를 어떻게 알아보나?** 회원은 로그인 쿠키에 회원 id가 있다. 비회원은? 명세(data-model)는 "익명 식별자"라고만 적었다.
2. **"5분 안에 다시"를 어떻게 판단하나?** 마지막으로 본 시각을 어딘가에 둬야 한다. 그리고 "최근 1시간 조회수"(인기 점수, 스텝 8의 T063)도 세야 한다.
3. **새로고침을 빠르게 연타하면?** 요청 여러 개가 거의 동시에 서버에 온다. 모두 "5분 안에 본 기록 없음"을 보고 각각 센다면 조회수가 부풀려진다. 공감 버튼에서 겪은 것과 같은 종류의 문제다([33](./33-isolation-deadlock.md)).

조회수를 그냥 `view_count = view_count + 1`로 매번 올리면 1·2·3 모두 무시하는 것이다. 새로고침만 해도 숫자가 오르고, 그 숫자로 인기 글을 매기면 순위를 조작하기도 쉽다.

## 3. 기본 개념

### 3.1 조회자 키(viewer key)

조회 기록 한 행은 "어떤 글을, **누가**, 언제 봤나"다. "누가"를 문자열 하나로 나타낸 것이 `view_log.viewer_key`(VARCHAR 64)다. 이 프로젝트는 이렇게 정했다.

| 보는 사람 | viewer_key | 예 |
| --- | --- | --- |
| 회원 | `m:` + 회원 id | `m:42` |
| 비회원 | `a:` + 방문자 쿠키 값(UUID) | `a:3f1c...-...` |

앞의 `m:`·`a:`는 둘이 겹치지 않게 하는 이름표다. 회원 id 42와, 우연히 "42"라는 값을 가진 비회원 쿠키가 같은 사람으로 보이면 안 된다.

나중에 블로그 방문 통계(`blog_visit.visitor_key`, MNG-03)도 같은 방식을 쓴다고 명세에 적혀 있어서, 키를 만드는 코드는 조회수 기능(`post/`)이 아니라 공용 자리(`global/web/VisitorKeys`)에 두었다.

### 3.2 비회원은 쿠키로 알아본다

비회원을 알아볼 방법은 몇 가지가 있다.

| 방법 | 장점 | 단점 |
| --- | --- | --- |
| IP 주소 | 아무것도 저장하지 않음 | 회사·학교·카페처럼 여러 사람이 IP 하나를 같이 쓰면 한 사람으로 보임. 휴대폰은 IP가 자주 바뀜 |
| 브라우저 지문(화면 크기, 글꼴 등 조합) | 쿠키를 지워도 남음 | 정확하지 않고, 사생활 침해 논란 |
| **서버가 준 임의 값 쿠키** | 브라우저마다 정확히 하나, 구현 간단 | 쿠키를 지우거나 시크릿 창이면 새 사람 |

이 프로젝트는 쿠키를 골랐다. 처음 오는 비회원에게 임의의 값(UUID)을 만들어 `visitor_id` 쿠키로 주고, 다음부터는 브라우저가 그 쿠키를 자동으로 보낸다. 쿠키를 지운 사람이 한 번 더 세지는 정도는 받아들인다. 조회수는 "대략 몇 명이 읽었나"를 보여 주는 숫자지 돈 계산이 아니기 때문이다.

쿠키 속성은 로그인 쿠키([10](./10-http-cookies.md))와 맞췄다.

| 속성 | 값 | 이유 |
| --- | --- | --- |
| `Domain` | `.blog.test`(운영은 `.blog.com`) | `alpha.blog.test`에서 받은 쿠키를 `beta.blog.test`에서도 보내야 같은 비회원으로 보인다 |
| `Path` | `/` | 모든 경로 |
| `HttpOnly` | 켬 | 화면 스크립트가 읽을 필요가 없다. XSS로 훔쳐 가지 못하게 |
| `Secure` | 운영 켬, 개발 끔 | 로그인 쿠키와 같은 설정값 `app.auth.cookie-secure` |
| `SameSite` | `Lax` | 다른 사이트에서 몰래 보내는 요청에는 안 붙게 |
| `Max-Age` | 365일 | 브라우저를 닫아도 남아야 "같은 사람"이 유지된다 |

### 3.3 쿠키 값은 사용자가 바꿀 수 있다

쿠키는 브라우저에 저장된 글자일 뿐이라, 개발자 도구나 curl로 아무 값이나 보낼 수 있다. `visitor_id=' OR 1=1 --` 같은 값이 그대로 `viewer_key`에 들어가면?

- SQL 주입은 일어나지 않는다. JPA가 값을 **바인딩 변수**로 보내기 때문이다(SQL 문장과 값이 따로 간다).
- 그래도 이상한 값, 아주 긴 값(칸은 64자)이 DB에 쌓이는 것은 막고 싶다.

그래서 서버는 **UUID 모양일 때만** 받고, 아니면 쿠키가 없는 것으로 보고 새 값을 준다. "받을 수 있는 모양을 정해 두고 나머지는 버린다"는 허용 목록 방식이다([14](./14-xss-sanitize-csp.md)의 HTML 정화와 같은 생각).

UUID를 바꿔 보내면 그냥 "다른 비회원"이 될 뿐이다. 이걸로 조회수를 부풀리는 건 막지 못한다(쿠키를 매번 안 보내는 것과 같다). 완전히 막으려면 요청 횟수 제한(IP당 분당 몇 번) 같은 다른 장치가 필요하다. 이 프로젝트 범위 밖이다.

### 3.4 시간 창 중복 판정

"5분 안에 다시 열면 1회"는 이렇게 묻는 것과 같다.

> 이 글(post_id)에 이 조회자(viewer_key)가 **지금 − 5분 이후**에 본 기록이 있나?

```sql
SELECT 1 FROM view_log
WHERE post_id = ? AND viewer_key = ? AND viewed_at > (지금 - 5분)
LIMIT 1
```

있으면 세지 않고, 없으면 기록을 하나 넣고 조회수를 1 올린다. ERD에는 이 질문을 위한 인덱스가 처음부터 있다.

```sql
CREATE INDEX idx_view_log_post_id_viewer_key_viewed_at ON view_log (post_id ASC, viewer_key ASC, viewed_at ASC);
```

인덱스는 칸 순서대로 정렬된 목차다. `post_id`가 같고 `viewer_key`가 같은 행들이 붙어 있고, 그 안에서 `viewed_at` 순이다. 그래서 MySQL은 "글 8, 조회자 m:42" 구간으로 바로 가서 마지막 시각 근처만 본다. 조회 기록이 수백만 행이어도 빠르다.

### 3.5 기록 테이블과 누적 칸을 둘 다 두는 이유

`post.view_count`(누적 숫자)만 있으면 "5분 안에 본 적 있나"와 "최근 1시간에 몇 번 읽혔나"를 알 수 없다. 반대로 `view_log`만 있으면 글 목록마다 `COUNT(*)`를 해야 해서 느리다. 그래서 둘 다 둔다.

| 저장 | 쓰는 곳 |
| --- | --- |
| `view_log` 행 (조회마다 하나, 시각 포함) | 5분 중복 판정, 최근 1시간 인기 점수(HOME-02), 앞으로 최근 7일 블로그 점수·통계 |
| `post.view_count` (누적) | 글 상세의 "조회 120" 표시, 앞으로 사이드바 인기 글(누적 조회수 순) |

이것은 공감 수(`like_count`)·댓글 수(`comment_count`)와 같은 **비정규화**다([27](./27-soft-delete-bulk-update.md), [29](./29-comments-design.md)). 기록과 숫자가 어긋나지 않으려면 **같은 트랜잭션**에서 함께 바꾼다.

`view_log`는 계속 쌓이므로, 명세는 "7일보다 오래된 행은 매일 지운다"고 정했다(data-model). 이 정리 작업은 아직 만들지 않았다(스텝 노트의 "아직 채우지 않은 것").

## 4. 동작 원리

### 4.1 한 번의 조회

```
alpha.blog.test/8  (PostPage)
  GET /api/posts/8                     본문을 받아 그린다
  POST /api/posts/8/views              본문이 보인 뒤 한 번
    PostController.view
      ① postReadService.readable(...)   볼 수 있는 글인가? 아니면 404·403   [트랜잭션 1, 읽기 전용]
      ② visitorKeys.resolve(...)        회원 → "m:42" / 비회원 → 쿠키 → "a:uuid" (없으면 새로 만들어 Set-Cookie)
      ③ viewService.record(8, key)                                           [트랜잭션 2]
           SELECT id FROM post WHERE id = 8 FOR UPDATE      글 행 배타 잠금
           SELECT ... FROM view_log WHERE ... viewed_at > 지금-5분   있으면 끝(false)
           INSERT INTO view_log (post_id, viewer_key, viewed_at) ...
           UPDATE post SET view_count = view_count + 1 ... WHERE id = 8
           COMMIT
  ← 204 (셌든 안 셌든 같은 응답)
```

응답이 늘 204인 이유: 화면은 셌는지 알 필요가 없다. 그리고 "이번엔 안 셌다"를 알려 주면 오히려 조회수 조작을 시험해 보기 쉬워진다.

### 4.2 새로고침 연타: 잠금이 없으면

같은 회원(m:42)이 새로고침을 빠르게 두 번 눌러 요청 A, B가 동시에 왔다고 하자. 잠금 없이 "확인 → 넣기"를 하면:

```
A: view_log에 5분 안 기록 있나? → 없음
B: view_log에 5분 안 기록 있나? → 없음 (A가 아직 안 넣었거나 커밋 전)
A: INSERT view_log, view_count + 1, COMMIT
B: INSERT view_log, view_count + 1, COMMIT     → 같은 사람인데 2번 셈
```

전형적인 **확인 후 행동(check-then-act)** 경쟁 조건이다([23](./23-transactions-locking.md)). 공감은 UNIQUE(member_id, post_id)가 있어서 `INSERT IGNORE` 한 문장으로 해결했지만([33](./33-isolation-deadlock.md) 5.2), 조회 기록은 같은 사람이 5분 뒤에 또 넣어야 하므로 UNIQUE를 걸 수 없다.

실제로 잠금을 빼고 동시성 테스트(같은 사람 둘이 다섯 번씩 동시에)를 돌려 보니, 중복으로 세기 전에 **데드락**이 먼저 났다.

```
WARN ... Deadlock found when trying to get lock; try restarting transaction
java.lang.AssertionError: expected: 204 but was: 500
```

공감 때와 같은 원인이다. `view_log` INSERT의 외래 키 확인이 글 행에 **공유(S) 잠금**을 걸고, 이어지는 `view_count` UPDATE가 같은 글 행의 **배타(X) 잠금**을 원한다. 두 트랜잭션이 S를 쥔 채 서로의 S가 풀리기를 기다린다([33](./33-isolation-deadlock.md) 4.1).

### 4.3 글 행부터 잠그면

```
A: SELECT ... FROM post WHERE id = 8 FOR UPDATE    X 잠금 얻음
B: SELECT ... FROM post WHERE id = 8 FOR UPDATE    A가 끝날 때까지 기다림
A: 5분 안 기록 없음 → INSERT, view_count + 1, COMMIT (잠금 풀림)
B: X 잠금 얻음 → 5분 안 기록 있나? → 있음(A가 넣은 행) → 세지 않음
```

같은 글에 대한 조회 기록 처리가 한 줄로 선다. 데드락도 사라진다. 처음부터 X를 쥐므로 "S를 쥔 채 X를 기다리는" 순간이 없다.

대가는 같은 글의 조회 기록이 차례로 처리된다는 것이다. 트랜잭션이 아주 짧아서(쿼리 네 개) 블로그 규모에서는 문제가 안 된다. 다른 글끼리는 서로 기다리지 않는다.

### 4.4 잠금이 첫 문장이어야 하는 이유

B가 잠금을 얻은 뒤 하는 "5분 안 기록 있나?"는 **평범한 SELECT**(일관된 읽기)다. MySQL 기본 격리 수준 REPEATABLE READ에서 평범한 SELECT는 **그 트랜잭션의 첫 일관된 읽기 때 정해진 스냅샷**을 본다([33](./33-isolation-deadlock.md) 3.2). `FOR UPDATE` 같은 잠금 읽기는 스냅샷을 정하지 않는다.

- B의 첫 문장이 `FOR UPDATE`면: 잠금을 얻은 **뒤에** 첫 평범한 SELECT를 하므로, 그때 스냅샷이 정해진다. A가 이미 커밋한 행이 보인다. 
- B가 잠금 **전에** 평범한 SELECT를 하나라도 했다면(예: 같은 트랜잭션 안에서 글을 읽어 가시성 확인): 스냅샷이 A의 커밋 전으로 정해진다. 잠금을 얻은 뒤에도 A의 행이 안 보여서 **또 센다**.

두 번째가 바로 [33](./33-isolation-deadlock.md)의 버그 2(응답의 공감 수가 0)와 같은 함정이다. 그래서 가시성 확인(`readable`)을 `record` 안에서 부르지 않고 **컨트롤러에서 먼저, 다른 트랜잭션으로** 한다. `readable`의 `@Transactional(readOnly = true)`는 바깥에 트랜잭션이 없으면 **자기 트랜잭션을 열고 끝낸다**(전파 `REQUIRED`). 이 프로젝트는 `open-in-view: false`라 컨트롤러에는 트랜잭션이 없다([24](./24-layered-architecture-dto.md)).

가시성 확인과 기록 사이에 글이 비공개로 바뀌면? 그 짧은 틈에 조회 하나가 더 세질 수 있다. 조회수 하나라서 받아들였다. 돈이나 권한이 걸린 일이었다면 같은 트랜잭션 안에서 잠금 **뒤에** 다시 확인해야 한다.

## 5. 이 프로젝트에서는

### 5.1 `post/domain/ViewLog.java`

```java
@Entity
@Table(name = "view_log")
public class ViewLog {

    public static final int MAX_VIEWER_KEY_LENGTH = 64;

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "post_id", nullable = false)
    private Post post;

    /** 회원이면 "m:{회원 id}", 비회원이면 "a:{방문자 쿠키 값}" (VisitorKeys). */
    @Column(name = "viewer_key", nullable = false, length = MAX_VIEWER_KEY_LENGTH)
    private String viewerKey;

    @Column(name = "viewed_at", nullable = false)
    private LocalDateTime viewedAt;
    ...
    public static ViewLog of(Post post, String viewerKey, LocalDateTime viewedAt) {
        return new ViewLog(post, viewerKey, viewedAt);
    }
```

- 테이블 칸을 그대로 옮겼다(schema.sql의 `view_log`). `ddl-auto=validate`라 칸 이름·타입이 다르면 서버가 뜨지 않는다([03](./03-flyway-migration.md)).
- `viewed_at`은 DB 기본값(`CURRENT_TIMESTAMP(6)`)이 있지만 일부러 **자바에서 `Clock`으로** 넣는다. 5분 판정의 "지금"도 `Clock`에서 오므로 둘이 같은 시계를 써야 한다. 테스트에서 시계를 바꿀 수도 있다.
- 공통 부모(`BaseCreatedEntity`)를 쓰지 않는다. 이 테이블에는 `created_at`이 없고 `viewed_at`이 그 역할이다.
- 수정할 일이 없는 기록이라 setter가 없다.

### 5.2 `post/domain/ViewLogRepository.java`

```java
public interface ViewLogRepository extends JpaRepository<ViewLog, Long> {

    /** 이 조회자가 since 뒤에 이 글을 본 기록이 있는가. 인덱스 (post_id, viewer_key, viewed_at)를 탄다. */
    boolean existsByPostIdAndViewerKeyAndViewedAtAfter(Long postId, String viewerKey, LocalDateTime since);

}
```

메서드 이름으로 쿼리를 만든다(파생 쿼리, [06](./06-jpa-entity-mapping.md)). 이름을 쪼개 읽으면:

| 조각 | 뜻 |
| --- | --- |
| `exists` | 행이 있나(true/false). Hibernate는 한 행만 찾으면 멈추는 쿼리를 만든다 |
| `ByPostId` | `post.id = ?` (연관 엔티티의 id) |
| `AndViewerKey` | `viewer_key = ?` |
| `AndViewedAtAfter` | `viewed_at > ?` |

`After`는 `>`(초과)다. 정확히 5분 전에 본 기록은 "5분 안"이 아니라서 다시 센다.

### 5.3 `PostRepository.increaseViewCount`

```java
/** 조회수 하나 올리기 (POST-09). 댓글 수와 같은 한 줄 UPDATE이고, 조회는 글을 고친 것이 아니라 updated_at을 그대로 둔다. */
@Modifying(clearAutomatically = true)
@Query("update Post p set p.viewCount = p.viewCount + 1, p.updatedAt = p.updatedAt where p.id = :postId")
int increaseViewCount(@Param("postId") Long postId);
```

- `view_count = view_count + 1`: DB가 **최신 값**에 1을 더하는 원자적 UPDATE([27](./27-soft-delete-bulk-update.md)). 자바에서 읽고 +1 해서 저장하면 동시에 두 요청이 같은 값을 읽어 하나를 잃는다.
- `p.updatedAt = p.updatedAt`: `post.updated_at`에는 MySQL의 `ON UPDATE CURRENT_TIMESTAMP`가 걸려 있어서 행을 고치면 자동으로 지금 시각이 된다. 글 상세에 "수정 2026.10.09"가 뜨면 안 되므로 같은 값을 다시 넣어 막는다. 공감 수·댓글 수와 같은 요령이다.

### 5.4 `post/application/ViewService.java`

```java
@Service
public class ViewService {

    /** 이 시간 안에 같은 조회자가 다시 열면 한 번으로 본다 (spec Q2). */
    public static final Duration DUPLICATE_WINDOW = Duration.ofMinutes(5);
    ...
    @Transactional
    public boolean record(Long postId, String viewerKey) {
        postRepository.lockById(postId).orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));
        LocalDateTime now = LocalDateTime.now(clock);
        if (viewLogRepository.existsByPostIdAndViewerKeyAndViewedAtAfter(postId, viewerKey,
                now.minus(DUPLICATE_WINDOW))) {
            return false;
        }
        viewLogRepository.save(ViewLog.of(postRepository.getReferenceById(postId), viewerKey, now));
        postRepository.increaseViewCount(postId);
        return true;
    }
```

줄별로:

- `@Transactional`: 잠금·확인·기록·숫자가 한 트랜잭션이다. 기록은 남았는데 숫자는 안 오르는 일이 없다. 잠금은 커밋할 때 풀린다.
- `lockById(postId)`: `SELECT p.id FROM Post p WHERE p.id = ? FOR UPDATE`(`@Lock(PESSIMISTIC_WRITE)`). 공감·댓글이 쓰는 바로 그 메서드다. **이 트랜잭션의 첫 문장**이다(4.4). 지워진 글 번호가 아니라 아예 없는 번호면 빈 값이라 404.
- `LocalDateTime.now(clock)`: 시계는 빈으로 주입한다(`ClockConfig`).
- `exists...After(now − 5분)`: 잠금 뒤의 평범한 SELECT. 이 트랜잭션의 첫 일관된 읽기라 앞 요청이 커밋한 기록이 보인다.
- `getReferenceById(postId)`: 글을 SELECT하지 않고 id만 든 **프록시**를 만든다. `ViewLog`에는 글의 id만 있으면 되므로 쿼리 하나를 아낀다.
- 반환값 `boolean`: 지금은 컨트롤러가 쓰지 않지만, 셌는지를 테스트·로그에서 볼 수 있게 남겼다.

### 5.5 `global/web/VisitorKeys.java`

```java
@Component
public class VisitorKeys {

    public static final String COOKIE = "visitor_id";

    private static final Duration COOKIE_TTL = Duration.ofDays(365);
    ...
    /** 지금 요청한 사람의 키. 쿠키가 없거나 망가진 비회원에게는 새 쿠키를 응답에 싣는다. */
    public String resolve(HttpServletRequest request, HttpServletResponse response) {
        Long memberId = LoginMembers.currentId();
        if (memberId != null) {
            return "m:" + memberId;
        }
        String visitorId = readCookie(request).orElseGet(() -> issue(response));
        return "a:" + visitorId;
    }
```

- `LoginMembers.currentId()`: JWT 필터가 채운 SecurityContext에서 회원 id를 꺼낸다([12](./12-spring-security-filter-chain.md)). 비회원이면 null.
- 회원에게는 방문자 쿠키를 주지 않는다. 필요 없는 쿠키를 만들지 않는다.
- `orElseGet(() -> issue(response))`: 쿠키가 없을 때**만** 새로 만든다. `orElse(issue(response))`로 쓰면 쿠키가 있어도 `issue`가 먼저 실행되어 매번 새 쿠키가 나간다. `orElse`는 값을 미리 계산하고, `orElseGet`은 필요할 때만 함수를 부른다.

```java
    /** 쿠키 값은 사용자가 바꿀 수 있으므로 UUID 모양만 받는다(아무 글자나 viewer_key에 들어가지 않게). */
    private static Optional<String> parseUuid(String value) {
        try {
            return Optional.of(UUID.fromString(value).toString());
        } catch (IllegalArgumentException e) {
            return Optional.empty();
        }
    }
```

- `UUID.fromString`은 모양이 틀리면 `IllegalArgumentException`을 던진다. 받아서 "쿠키 없음"으로 바꾼다.
- `.toString()`으로 다시 쓰는 이유: 대문자로 보낸 UUID도 소문자 한 가지 모양으로 맞춘다. 같은 사람이 대소문자만 바꿔 다른 키가 되지 않는다.

```java
    private String issue(HttpServletResponse response) {
        String visitorId = UUID.randomUUID().toString();
        ResponseCookie cookie = ResponseCookie.from(COOKIE, visitorId)
                .domain(domainProperties.cookieDomain())
                .path("/")
                .httpOnly(true)
                .secure(authProperties.cookieSecure())
                .sameSite("Lax")
                .maxAge(COOKIE_TTL)
                .build();
        response.addHeader(HttpHeaders.SET_COOKIE, cookie.toString());
        return visitorId;
    }
```

- `UUID.randomUUID()`: 버전 4 UUID, 122비트가 무작위라 겹칠 걱정이 없다. 내부적으로 `SecureRandom`을 쓴다.
- `ResponseCookie`: 스프링이 주는 쿠키 만들기 도구. 서블릿의 `Cookie` 클래스는 `SameSite`를 바로 지원하지 않아서 로그인 쿠키(`AuthCookieManager`)와 같은 방식을 썼다.

### 5.6 `PostController.view`

```java
/**
 * 글을 본 기록. 화면이 본문을 보여 준 뒤 부른다. 같은 조회자가 5분 안에 다시 부르면 세지 않지만 응답은 같다(204).
 * 볼 수 없는 글이면 상세와 같이 404·403이다. 가시성 확인과 기록은 다른 트랜잭션이다(ViewService.record 설명).
 */
@PostMapping("/api/posts/{id}/views")
@ResponseStatus(HttpStatus.NO_CONTENT)
public void view(@CurrentBlog Blog blog, @PathVariable Long id, HttpServletRequest request,
                 HttpServletResponse response) {
    postReadService.readable(blog, id, LoginMembers.currentId());
    viewService.record(id, visitorKeys.resolve(request, response));
}
```

- `@CurrentBlog Blog blog`: 요청 주소의 서브도메인으로 찾은 블로그([15](./15-subdomain-host-routing.md)). 다른 블로그의 글 번호면 `readable`이 404.
- `readable(...)`: 글 상세와 **같은 판단**이다. 비공개·숨김·삭제 글, 이용 제한 블로그의 글은 404, 구독자 공개를 구독 안 한 사람은 403 `SUBSCRIBERS_ONLY`. 볼 수 없는 글의 조회수가 오르면 안 되고, 404/200 차이로 글이 있는지 알려 주지도 않는다([16](./16-authorization-visibility.md)).
- 주인이 자기 비공개 글을 보면 `readable`이 통과하므로 센다. 명세가 주인을 빼라고 하지 않았다(블로그 방문 통계 MNG-03은 주인을 뺀다고 명시돼 있다).
- POST라서 CSRF 대책 헤더 `X-Requested-With`가 필요하다([13](./13-csrf-samesite-cors.md)). 화면의 `api()`가 자동으로 붙인다.
- `@ResponseStatus(NO_CONTENT)` + `void`: 본문 없는 204.

### 5.7 화면: `pages/post/PostPage.tsx`

```tsx
// 개발 모드(StrictMode)는 effect를 두 번 부른다. 같은 글에 조회 기록을 두 번 보내지 않게 마지막으로 보낸 글을 기억한다
const viewedPostId = useRef<number | null>(null)
...
const shownPostId = state.status === 'ok' ? state.post.id : null
useEffect(() => {
  if (shownPostId === null || viewedPostId.current === shownPostId) {
    return
  }
  viewedPostId.current = shownPostId
  // 응답은 늘 204다(5분 안에 다시 보면 서버가 세지 않는다). 실패해도 글 읽기에는 지장이 없어 무시한다
  api(`/api/posts/${shownPostId}/views`, { method: 'POST', allowAnonymous: true }).catch(() => undefined)
}, [shownPostId])
```

Thymeleaf로 치면 "글 상세 컨트롤러가 화면을 돌려주면서 조회수를 올리는" 대신, 화면이 그려진 뒤 브라우저가 따로 한 번 알려 주는 구조다([28](./28-thymeleaf-to-react.md)).

- `shownPostId`: 글을 **받은 뒤**에만 숫자가 된다. 404·403인 글은 null이라 보내지 않는다. 목업(post-detail)의 "본문 보인 뒤"와 같다.
- `useEffect(..., [shownPostId])`: 글 번호가 바뀔 때만 다시 돈다. 이전·다음 글 링크로 다른 글로 가면 새 번호라 한 번 더 보낸다. 댓글 수가 바뀌어 `state`가 새로 만들어져도 번호는 같아서 다시 보내지 않는다.
- `useRef`: 다시 그려도 값이 유지되는 상자다. 값을 바꿔도 화면을 다시 그리지 않는다(`useState`와 다른 점).
- **StrictMode와 effect 두 번**: `main.tsx`가 `<StrictMode>`로 감싸 두어서, 개발 서버에서는 React가 컴포넌트를 붙였다 떼었다 다시 붙이며 effect를 두 번 부른다(정리 함수를 잘 썼는지 확인하려는 장치, 운영 빌드에서는 안 함). 회원이면 서버의 5분 판정이 막아 주지만, **처음 온 비회원**은 두 요청 모두 쿠키 없이 가서 서로 다른 `visitor_id`를 받고 둘 다 세진다. ref로 "이미 보낸 글"을 기억해 막았다. StrictMode의 두 번째 실행에서도 같은 컴포넌트라 ref 값이 남아 있다.
- 화면의 "조회 N"은 `GET /api/posts/8`의 `viewCount`라 **이번 조회를 세기 전** 값이다. 처음 연 사람은 N, 새로고침하면 N+1, 5분 안에 또 새로고침하면 그대로 N+1이다.

### 5.8 테스트 `ViewCountIntegrationTest`

| 테스트 | 확인하는 것 |
| --- | --- |
| `sameViewerWithinFiveMinutesCountsOnce` | 같은 회원 두 번 → 1. 기록 시각을 6분 앞으로 옮기면(`UPDATE view_log SET viewed_at = viewed_at - INTERVAL 6 MINUTE`) 다시 셈 → 2 |
| `anonymousViewerIsKnownByVisitorCookie` | 처음 비회원에게 `visitor_id` 쿠키(HttpOnly, `Domain=.blog.test`), 같은 쿠키로 다시 보면 안 셈·쿠키도 다시 안 줌, 쿠키 없음·UUID 아닌 값(`' OR 1=1 --`)은 새 비회원, 저장된 키가 모두 `a:` + UUID 모양 |
| `invisiblePostIsNotFoundAndNotCounted` | 비공개·숨김·삭제 글과 없는 번호는 404이고 기록·숫자 그대로. 주인은 자기 비공개 글을 보면 셈 |
| `concurrentRefreshesBySameViewerCountOnce` | 회원 두 명이 스레드 10개로 다섯 번씩 동시에 → 모두 204, 조회수 2, 기록 2행 |

5분을 기다릴 수는 없으니, 시계를 바꾸는 대신 **기록을 과거로 옮겼다**. 판정은 "기록 시각 > 지금 − 5분"이라 둘은 같은 효과다.

마지막 테스트가 잠금을 정말 필요로 하는지 확인하려고 `lockById` 줄을 잠시 빼고 세 번 돌렸다. 세 번 모두 데드락으로 500이 나서 실패했다(4.2). 테스트가 "버그가 있으면 실패한다"는 것을 확인한 뒤 되돌렸다.

## 6. 자주 하는 실수와 함정

- **GET 글 상세에서 조회수를 올린다.** GET은 안전한 메서드라 상태를 바꾸지 않는다는 약속이 있다([17](./17-idempotency-redis.md) 3.2). 미리 불러오기, 검색 엔진 로봇, 캐시가 GET을 마음대로 보내도 숫자가 올라 버린다. 따로 POST로 알린다.
- **"확인 → 넣기"를 잠금 없이 한다.** 연타하면 두 번 센다. 외래 키가 있는 자식 INSERT + 부모 UPDATE 조합이면 데드락까지 난다(4.2).
- **잠금 전에 같은 트랜잭션에서 평범한 SELECT를 한다.** 스냅샷이 잠금 전으로 정해져, 잠금을 얻은 뒤에도 앞 요청의 기록이 안 보인다(4.4). 잠금을 첫 문장으로, 아니면 확인 쿼리를 잠금 읽기로.
- **조회수를 자바에서 +1 해서 저장한다.** `post.setViewCount(post.getViewCount() + 1)`은 동시에 읽은 두 요청 중 하나를 잃는다. DB에서 더한다.
- **쿠키 값을 그대로 저장한다.** 길이 초과로 500이 나거나 이상한 값이 쌓인다. 모양을 검사한다.
- **`orElse(만들기())`를 쓴다.** 값이 있어도 `만들기()`가 실행된다. 부작용(쿠키 발급)이 있으면 `orElseGet`.
- **비회원 키를 IP로 한다.** 한 건물이 한 사람이 된다.
- **응답으로 "셌다/안 셌다"를 알려 준다.** 쓸모없고, 조작 시험을 돕는다.
- **개발 모드에서 조회수가 2씩 올라서 서버를 의심한다.** StrictMode의 effect 두 번이다. 운영 빌드에서는 한 번이지만, ref로 막아 두면 개발 중에도 헷갈리지 않는다.
- **`view_log`를 지우지 않는다.** 조회마다 한 행이라 금방 커진다. 쓰는 기간(최근 7일)이 지나면 지운다(아직 만들지 않음).

## 7. 직접 해 보기

준비: `docker compose up -d`, `./mvnw spring-boot:run`. 공개 글이 있는 블로그 주소를 `myfirst`, 글 번호를 `8`이라고 하자.

### 7.1 같은 쿠키로 세 번, 새 비회원으로 한 번

```bash
H="Host: myfirst.blog.test"; X="X-Requested-With: XMLHttpRequest"; rm -f jar.txt
for i in 1 2 3; do
  curl -s -o /dev/null -w "%{http_code}\n" -c jar.txt -b jar.txt -X POST -H "$H" -H "$X" localhost:8080/api/posts/8/views
done
grep visitor_id jar.txt                                    # #HttpOnly_.blog.test ... visitor_id <uuid>
curl -s -H "$H" localhost:8080/api/posts/8 | grep -o '"viewCount":[0-9]*'     # 1 늘었음
curl -s -o /dev/null -X POST -H "$H" -H "$X" localhost:8080/api/posts/8/views # 쿠키 없이 = 새 비회원
curl -s -H "$H" localhost:8080/api/posts/8 | grep -o '"viewCount":[0-9]*'     # 1 더 늘었음
```

스텝 8을 만들며 실제로 돌린 결과: 세 번 모두 204, 조회수 1 → 새 비회원 뒤 2.

### 7.2 DB에서 기록 보기

```bash
docker exec -it blog-mysql mysql -ublog -pblog blog \
  -e "SELECT post_id, viewer_key, viewed_at FROM view_log ORDER BY id DESC LIMIT 5;
      EXPLAIN SELECT 1 FROM view_log WHERE post_id = 8 AND viewer_key = 'm:1' AND viewed_at > NOW() - INTERVAL 5 MINUTE;"
```

`EXPLAIN`의 `key` 칸에 `idx_view_log_post_id_viewer_key_viewed_at`이 나오는지 본다.

### 7.3 5분 지난 척하기

```bash
docker exec blog-mysql mysql -ublog -pblog blog -e "UPDATE view_log SET viewed_at = viewed_at - INTERVAL 6 MINUTE WHERE post_id = 8"
# 7.1의 jar.txt로 다시 보내면 이번엔 센다
```

### 7.4 잠금을 빼고 테스트 (공부용 브랜치에서)

```bash
git switch -c study/no-view-lock
# ViewService.record의 lockById 줄을 지운다
./mvnw test -Dtest='ViewCountIntegrationTest#concurrentRefreshesBySameViewerCountOnce'   # 500, Deadlock found ...
git restore . && git switch -
```

### 7.5 화면

`http://myfirst.blog.test:5173/8`(개발 서버)을 열고 개발자 도구 네트워크 탭에서 `views` 요청이 **한 번**만 가는지 본다. `useRef` 확인 줄을 지우면 두 번 간다(StrictMode).

## 8. 확인 문제

1. 조회수를 글 상세 GET에서 올리지 않고 POST `/views`를 따로 둔 이유는?
<details><summary>답</summary>GET은 상태를 바꾸지 않는 안전한 메서드라는 약속이 있어서, 미리 불러오기·로봇·캐시가 마음대로 보낼 수 있다. 그때마다 조회수가 오르면 안 된다. 화면이 실제로 본문을 보여 준 뒤에만 POST로 알린다.</details>

2. 비회원을 IP가 아니라 쿠키로 알아보는 이유와, 쿠키 방식의 한계는?
<details><summary>답</summary>IP는 여러 사람이 공유하거나(회사, 카페) 자주 바뀐다(휴대폰). 쿠키는 브라우저마다 하나라 정확하다. 한계: 쿠키를 지우거나 시크릿 창이면 새 사람이 되고, 쿠키를 안 보내면 매번 새 사람이라 조작을 완전히 막지는 못한다.</details>

3. `visitor_id` 쿠키 값을 UUID 모양일 때만 받는 이유는? SQL 주입 때문인가?
<details><summary>답</summary>SQL 주입은 바인딩 변수 덕분에 원래 안 된다. 사용자가 바꿀 수 있는 값이라 길이 초과(64자)나 이상한 값이 DB에 쌓이지 않게, 받을 수 있는 모양만 허용한다.</details>

4. `view_log`와 `post.view_count`를 둘 다 두는 이유는?
<details><summary>답</summary><code>view_log</code>는 시각이 있는 기록이라 5분 중복 판정과 최근 1시간·7일 집계에 쓴다. <code>view_count</code>는 누적 숫자라 상세·목록에서 매번 세지 않고 바로 보여 준다. 둘을 같은 트랜잭션에서 바꿔 어긋나지 않게 한다.</details>

5. 잠금 없이 같은 사람이 새로고침을 동시에 두 번 하면 무엇이 잘못될 수 있나? 이 프로젝트에서 실제로 본 현상은?
<details><summary>답</summary>두 요청이 모두 "5분 안 기록 없음"을 보고 각각 센다(확인 후 행동 경쟁). 실제로는 그보다 먼저 데드락이 났다. view_log INSERT의 외래 키 확인이 글 행에 S 잠금을, view_count UPDATE가 X 잠금을 원해서 두 트랜잭션이 서로 기다렸다(500).</details>

6. `lockById`가 `record` 트랜잭션의 첫 문장이어야 하는 이유는?
<details><summary>답</summary>REPEATABLE READ에서 평범한 SELECT는 첫 일관된 읽기 때 정해진 스냅샷을 본다. 잠금 읽기는 스냅샷을 정하지 않는다. 잠금이 먼저면 잠금을 얻은 뒤 첫 SELECT에서 스냅샷이 정해져 앞 요청의 기록이 보인다. 잠금 전에 평범한 SELECT를 하면 스냅샷이 앞 요청의 커밋 전으로 정해져 또 센다.</details>

7. 그래서 가시성 확인 `readable`은 어디서 부르나? 그 결과 생기는 작은 틈은?
<details><summary>답</summary>컨트롤러에서 <code>record</code> 전에, 자기 읽기 전용 트랜잭션으로 부른다(open-in-view가 꺼져 있어 컨트롤러엔 트랜잭션이 없다). 확인과 기록 사이에 글이 비공개가 되면 조회 하나가 더 세질 수 있다. 조회수라 받아들였다.</details>

8. `existsBy...ViewedAtAfter(now - 5분)`에서 정확히 5분 전 기록은 "5분 안"인가?
<details><summary>답</summary>아니다. <code>After</code>는 <code>&gt;</code>(초과)라 정확히 5분 전 기록은 포함되지 않아 다시 센다.</details>

9. 개발 서버에서 처음 온 비회원이 글을 열면 조회수가 2 오르던 이유와 고친 방법은?
<details><summary>답</summary>StrictMode가 effect를 두 번 부르고, 두 요청 모두 쿠키 없이 가서 서로 다른 visitor_id를 받아 둘 다 세졌다. <code>useRef</code>로 마지막으로 보낸 글 번호를 기억해 같은 글이면 다시 보내지 않는다.</details>

10. 테스트에서 "5분 뒤"를 어떻게 흉내 냈나?
<details><summary>답</summary>시계를 바꾸는 대신 view_log의 viewed_at을 SQL로 6분 앞으로 옮겼다. 판정이 "기록 시각 &gt; 지금 − 5분"이라 같은 효과다.</details>

## 9. 더 읽을거리

- MySQL 8.4 레퍼런스, "Consistent Nonlocking Reads"(스냅샷이 정해지는 때), "Locking Reads", "Locks Set by Different SQL Statements in InnoDB"
- Spring Data JPA 레퍼런스, "Query Creation"(메서드 이름 키워드 `After`, `exists` 접두어), "Locking"
- MDN, "Using HTTP cookies", `Set-Cookie`의 `Domain`·`Max-Age`·`SameSite`
- `java.util.UUID` Javadoc(`randomUUID`, `fromString`), `Optional.orElse`와 `orElseGet`
- React 문서, "StrictMode"(개발 중 effect를 한 번 더 실행하는 이유), "useRef"
- 대규모 조회수: Redis `INCR`나 HyperLogLog(`PFADD`, 대략적인 고유 방문자 수)로 모았다가 주기적으로 DB에 반영하는 방식
