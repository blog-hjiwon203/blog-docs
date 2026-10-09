# 33. 격리 수준, 스냅샷, 데드락: 공감 버튼에서 겪은 두 버그

> 관련 스텝: [스텝 7](../step-07.md) (T046, T049, T044), [스텝 8](../step-08.md) (T053) · 관련 개념: [34-view-count](./34-view-count.md), [23-transactions-locking](./23-transactions-locking.md), [27-soft-delete-bulk-update](./27-soft-delete-bulk-update.md), [29-comments-design](./29-comments-design.md), [17-idempotency-redis](./17-idempotency-redis.md), [06-jpa-entity-mapping](./06-jpa-entity-mapping.md)

## 1. 이 문서로 배우는 것

- 트랜잭션 **격리 수준** 네 가지(READ UNCOMMITTED, READ COMMITTED, REPEATABLE READ, SERIALIZABLE)와 각각이 막는 이상 현상
- MySQL InnoDB의 기본값 REPEATABLE READ와 **MVCC**(여러 버전을 두고 읽기): "스냅샷"이 무엇이고 언제 정해지나
- **일관된 읽기**(평범한 SELECT)와 **잠금 읽기**(`SELECT … FOR UPDATE`, `FOR SHARE`)가 보는 값이 다르다는 것
- **공유 잠금(S)**과 **배타 잠금(X)**, 그리고 외래 키 확인이 부모 행에 공유 잠금을 건다는 것
- 실제로 겪은 버그 1: 같은 글에 여러 사람이 동시에 공감하면 **데드락** → 글 행을 먼저 배타 잠금(`lockById`)
- 실제로 겪은 버그 2: 같은 사람이 공감을 동시에 여러 번 누르면 최종 수는 맞는데 **응답의 공감 수가 0** → 공감 수를 잠금 읽기로
- `INSERT IGNORE` + UNIQUE로 만든 멱등 PUT, "실제로 바뀐 행이 있을 때만 수를 고친다"
- 동시성 테스트를 읽고, 데드락 기록(`SHOW ENGINE INNODB STATUS`)을 읽는 법

**먼저 알면 좋은 것**: 트랜잭션과 `@Transactional`, `SELECT … FOR UPDATE`, 데드락의 기본 뜻([23](./23-transactions-locking.md)), 댓글 수를 원자적 UPDATE로 고치는 방법([29](./29-comments-design.md) 5.6, [27](./27-soft-delete-bulk-update.md)).

## 2. 왜 필요한가

스텝 7에서 공감(SOC-01)을 만들었다. 규칙은 단순하다.

- 회원은 글 하나에 공감을 **최대 한 번** 한다. 켜기는 `PUT /api/posts/{id}/like`, 끄기는 `DELETE`. 몇 번 보내도 결과가 같다(멱등).
- 글에는 `like_count` 칸이 있어서 목록에서 매번 세지 않고 바로 보여 준다(비정규화, 댓글 수와 같은 방식).
- 응답은 `{ "liked": true, "likeCount": 7 }`. 화면은 이 값으로 버튼을 맞춘다.

스텝 4·6에서 배운 도구(UNIQUE, 원자적 UPDATE, 비관적 잠금)를 다 썼는데도 두 번 틀렸다.

1. **T049 동시성 테스트**(여러 회원이 같은 글에 동시에 켜기·끄기)에서 가끔 `CannotAcquireLockException`이 났다. 원인은 데드락이었다. 잠금을 하나도 안 썼다고 생각했는데, MySQL이 **보이지 않게** 잠금을 걸고 있었다.
2. 데드락을 고친 뒤, 실제 서버에 curl로 **같은 회원이 PUT을 5번 동시에** 보냈다. DB의 공감 수는 1로 맞았는데, 응답 다섯 개 중 네 개가 `"likeCount":0`이었다. 화면은 응답 값으로 버튼을 맞추므로, 사용자는 "공감했는데 0"을 본다.

```
{"liked":true,"likeCount":1}{"liked":true,"likeCount":0}{"liked":true,"likeCount":0}{"liked":true,"likeCount":0}{"liked":true,"likeCount":0}
```

두 버그 모두 "트랜잭션 안에서 SELECT가 **무엇을** 보고, 어떤 문장이 **어떤 잠금을** 거는가"를 알아야 설명된다. 그것이 격리 수준과 InnoDB 잠금이다.

## 3. 기본 개념

### 3.1 격리 수준과 이상 현상

ACID의 I(격리성)는 "동시에 도는 트랜잭션이 서로의 중간 상태를 **어느 정도** 안 본다"였다([23](./23-transactions-locking.md) 3.1). 그 "어느 정도"를 정하는 것이 **격리 수준(isolation level)**이다. 표준 SQL은 네 단계와, 각 단계에서 생길 수 있는 이상 현상을 정해 두었다.

| 이상 현상 | 뜻 | 예 |
| --- | --- | --- |
| Dirty read | 아직 **커밋 안 된** 다른 트랜잭션의 변경을 읽는다 | B가 공감 수를 1로 바꾸고 아직 커밋 전인데 A가 1을 읽음. B가 롤백하면 A는 없던 값을 본 것 |
| Non-repeatable read | 같은 행을 두 번 읽었는데 그 사이 다른 트랜잭션이 고치고 커밋해서 값이 다르다 | A: 0 읽음 → B: 1로 커밋 → A: 다시 읽으니 1 |
| Phantom read | 같은 조건으로 두 번 셌는데 그 사이 다른 트랜잭션이 **행을 추가**해서 개수가 다르다 | A: 공감 행 3개 → B: INSERT, 커밋 → A: 4개 |

| 격리 수준 | Dirty read | Non-repeatable read | Phantom read (표준 기준) |
| --- | --- | --- | --- |
| READ UNCOMMITTED | 생김 | 생김 | 생김 |
| READ COMMITTED | 막음 | 생김 | 생김 |
| REPEATABLE READ | 막음 | 막음 | 생김(표준). InnoDB는 일관된 읽기에서는 스냅샷 덕분에 안 보임 |
| SERIALIZABLE | 막음 | 막음 | 막음 |

- **MySQL InnoDB의 기본은 REPEATABLE READ**다. 이 프로젝트도 설정을 바꾸지 않았으니 REPEATABLE READ다. (PostgreSQL·Oracle의 기본은 READ COMMITTED라, 다른 DB 예제를 볼 때 헷갈리기 쉽다.)
- 격리 수준이 높을수록 "다른 트랜잭션의 변경을 덜 본다". 언뜻 안전해 보이지만, 이번 버그 2처럼 **최신 값을 봐야 할 때 못 보는** 문제가 된다.

### 3.2 MVCC와 스냅샷

InnoDB는 읽는 쪽이 쓰는 쪽을 기다리지 않게 하려고 **MVCC(Multi-Version Concurrency Control, 다중 버전 동시성 제어)**를 쓴다.

- 행을 UPDATE하면 InnoDB는 바뀌기 전 값을 **undo log**에 남긴다. 그래서 한 행에 대해 "지금 값"과 "예전 값들"을 거슬러 만들 수 있다.
- 평범한 SELECT는 **어느 시점의 사진(스냅샷, InnoDB 용어로 read view)**을 정해 두고, 그 시점에 커밋되어 있던 값을 보여 준다. 그 뒤에 커밋된 변경은 undo log로 되돌려 "그 시점의 값"을 만든다.
- 이렇게 읽는 것을 **일관된 읽기(consistent read, consistent nonlocking read)**라 한다. 잠금을 걸지 않으므로 다른 트랜잭션이 같은 행을 고치고 있어도 기다리지 않는다.

**스냅샷은 언제 정해지나.** MySQL 문서의 표현은 이렇다. REPEATABLE READ에서는 "같은 트랜잭션 안의 모든 일관된 읽기가, 그 트랜잭션의 **첫 번째 일관된 읽기**가 만든 스냅샷을 읽는다." 즉:

- `BEGIN`(또는 `START TRANSACTION`)하는 순간이 아니다. 트랜잭션 안에서 **처음으로 평범한 SELECT를 한 순간**이다. (`START TRANSACTION WITH CONSISTENT SNAPSHOT`이라고 쓰면 시작할 때 바로 정한다.)
- 한 번 정해지면 그 트랜잭션이 끝날 때까지 같은 사진을 본다. 그래서 "같은 행을 두 번 읽으면 같은 값"(repeatable read)이 된다.
- READ COMMITTED에서는 **문장마다** 새 스냅샷을 만든다. 그래서 다른 트랜잭션이 커밋한 값을 다음 SELECT에서 바로 본다.

### 3.3 일관된 읽기 vs 잠금 읽기

스냅샷 규칙에는 중요한 예외가 있다. **잠금 읽기와 쓰기 문장은 스냅샷이 아니라 최신 커밋 값을 본다.**

| 문장 | 무엇을 보나 | 잠금 |
| --- | --- | --- |
| `SELECT …` (평범한) | 스냅샷(REPEATABLE READ면 첫 일관된 읽기 시점) | 안 걺 |
| `SELECT … FOR SHARE` | **최신 커밋 값** | 읽은 행에 공유(S) 잠금 |
| `SELECT … FOR UPDATE` | **최신 커밋 값** | 읽은 행에 배타(X) 잠금 |
| `UPDATE`, `DELETE` | **최신 커밋 값**(그 값을 바탕으로 고친다) | 고친 행에 배타(X) 잠금 |
| `INSERT` | — | 새 행에 배타 잠금, 외래 키가 있으면 부모 행 확인(3.5) |

그래서 원자적 UPDATE `SET like_count = like_count + 1`은 REPEATABLE READ에서도 안전하다. UPDATE는 스냅샷 값이 아니라 최신 값에 더하기 때문이다([29](./29-comments-design.md) 5.6에서 "DB가 지금 값에 더한다"고 한 이유).

반대로, **같은 트랜잭션 안에서** "최신 값으로 UPDATE한 뒤 평범한 SELECT로 다시 읽으면" 이상한 일이 생길 수 있다. 내 트랜잭션이 고친 행은 내 변경이 보이지만, **다른 트랜잭션이 내 스냅샷 이후에 커밋한 변경은 안 보인다.** 이것이 버그 2의 정체다(4.2).

### 3.4 공유 잠금(S)과 배타 잠금(X)

InnoDB의 행 잠금은 두 종류다.

| | 다른 트랜잭션의 S 요청 | 다른 트랜잭션의 X 요청 |
| --- | --- | --- |
| 내가 S를 가짐 | 허락(둘 다 S를 가질 수 있음) | **기다림** |
| 내가 X를 가짐 | **기다림** | **기다림** |

- **S(shared, 공유)**: "읽는 중이니 바꾸지 마". 여럿이 동시에 가질 수 있다.
- **X(exclusive, 배타)**: "내가 바꾼다". 혼자만 가진다.
- 이미 S를 가진 트랜잭션이 같은 행의 X를 원하면, **다른 트랜잭션이 가진 S가 모두 풀려야** 얻는다.
- 잠금은 트랜잭션이 끝날 때(커밋·롤백) 풀린다.

### 3.5 외래 키 확인이 거는 잠금

`post_like`에는 외래 키가 있다.

```sql
ALTER TABLE post_like ADD CONSTRAINT fk_post_like_post FOREIGN KEY (post_id) REFERENCES post (id);
```

`INSERT INTO post_like (post_id, …) VALUES (10, …)`를 하면 InnoDB는 "글 10이 정말 있나"를 확인해야 한다. 확인하고 나서 커밋하기 전에 누가 글 10을 지우면 외래 키가 깨지므로, MySQL 문서대로 **InnoDB는 외래 키 확인 때 부모 행(글 10)에 공유(S) 잠금을 건다.** 이 잠금도 트랜잭션 끝까지 간다. 개발자가 SQL에 `FOR SHARE`를 쓰지 않았는데도 생기는 잠금이다. 댓글(`comment.post_id → post.id`)도 똑같다.

### 3.6 데드락과 InnoDB의 처리

데드락은 서로가 쥔 잠금을 서로 기다리는 상태다([23](./23-transactions-locking.md) 3.5). InnoDB는 기본으로 데드락을 **감지**해서(`innodb_deadlock_detect`, 기본 ON) 한쪽 트랜잭션을 골라 **롤백**시키고, 그쪽에 오류를 돌려준다.

```
ERROR 1213 (40001): Deadlock found when trying to get lock; try restarting transaction
```

Spring은 이 오류를 `CannotAcquireLockException`(`PessimisticLockingFailureException`의 하위)으로 바꿔 던진다. 이 프로젝트에서는 따로 처리하지 않으므로 500이 된다. 남은 한쪽은 정상으로 계속 진행한다.

데드락을 막는 일반 원칙:

1. **잠금 순서를 모두 같게**: 여러 자원을 잠글 때 모든 코드가 같은 순서로 잠근다.
2. **필요한 가장 강한 잠금을 처음부터**: S를 쥐고 있다가 X로 올리는(lock upgrade) 모양을 피한다. 버그 1이 바로 이 모양이다.
3. 트랜잭션을 짧게, 잠금 범위를 작게.
4. 그래도 날 수 있으면 재시도한다(문서도 "try restarting transaction"이라고 한다).

## 4. 동작 원리

### 4.1 버그 1: 공감 INSERT + 공감 수 UPDATE의 데드락

잠금을 넣기 전의 `LikeService.like`는 이 순서였다.

1. `readable()`: 글을 평범한 SELECT로 읽어 볼 수 있는지 판단(잠금 없음)
2. `INSERT IGNORE INTO post_like …` → 외래 키 확인으로 **글 행에 S**
3. 새로 넣었으면 `UPDATE post SET like_count = like_count + 1 …` → **글 행에 X 필요**

회원 A와 B가 **같은 글 10**에 동시에 공감하면:

```
시간 ─────────────────────────────────────────────────────────────────▶
A  INSERT post_like(10, A)  → 글 10에 S ✔
B  INSERT post_like(10, B)  → 글 10에 S ✔   (S끼리는 같이 가질 수 있다)
A  UPDATE post id=10        → X 필요. B의 S가 풀리길 기다림 …
B  UPDATE post id=10        → X 필요. A의 S가 풀리길 기다림 …   ← 서로 기다림 = 데드락
InnoDB: 데드락 감지 → 한쪽(예: B)을 롤백, B는 오류(1213) → Spring CannotAcquireLockException → 500
A  X 얻음 → UPDATE → COMMIT
```

- **서로 다른 회원**이라 `post_like` 행은 다르다(UNIQUE 충돌 없음). 그런데 둘 다 **같은 부모 행(글 10)**을 S로 쥐었다가 X로 올리려 해서 막혔다. 3.6의 "S를 쥐고 X로 올리기" 모양이다.
- 같은 회원이 연타할 때는 대부분 UNIQUE 쪽에서 줄을 서서 잘 안 드러난다. **여러 회원**이 같은 글에 몰릴 때 터진다. 인기 글일수록 잘 난다.
- 댓글도 같다. `INSERT comment`(글 행에 S) → `UPDATE post SET comment_count …`(X).
- 테스트 `likeCountMatchesRowsUnderConcurrentToggling`(5명 × 6번을 스레드 10개로 섞어 보냄)이 가끔 실패해서 찾았다.

**고친 방법: 처음부터 X를 잡는다.**

```
A  SELECT id FROM post WHERE id=10 FOR UPDATE  → X ✔
B  SELECT id FROM post WHERE id=10 FOR UPDATE  → 기다림 ……………………………………… ✔ (A 커밋 뒤)
A  INSERT post_like  (글 행은 이미 내 X라 FK 확인이 막히지 않음)
A  UPDATE post like_count+1
A  COMMIT  → X 풀림
                                                        B INSERT → UPDATE → COMMIT
```

같은 글에 대한 공감·댓글 쓰기가 **글 행 하나로 줄을 선다.** S를 쥐고 X를 기다리는 순간이 없으니 데드락이 없다. 다른 글끼리는 다른 행을 잠그므로 서로 기다리지 않는다([23](./23-transactions-locking.md)에서 블로그 개설을 회원 행으로 줄 세운 것과 같은 생각).

대가: 같은 글에 공감이 동시에 100개 오면 100개가 차례로 처리된다. 한 건이 수 밀리초라 이 블로그 규모에서는 문제가 아니다. 아주 큰 서비스라면 카운터를 따로 모아 나중에 더하는 방식을 쓰기도 한다(9장).

### 4.2 버그 2: 응답의 공감 수가 옛 스냅샷

데드락을 고친 뒤, 같은 회원(B)이 이미 공감하지 않은 글에 **PUT을 5번 동시에** 보냈다. 트랜잭션 다섯 개(T1~T5)가 거의 같은 순간 시작한다.

```
시간 ──────────────────────────────────────────────────────────────────────────────▶
T1..T5  readable(): SELECT post …            ← 평범한 SELECT. 이 순간 각자의 스냅샷이 정해진다(like_count = 0)
T1      lockById: FOR UPDATE ✔
T2..T5  lockById: FOR UPDATE ……… 기다림
T1      INSERT IGNORE → 1행 → UPDATE like_count = 0 + 1
T1      SELECT p.likeCount  → 1 (내가 고친 행이라 내 변경이 보임)
T1      COMMIT → 응답 {"liked":true,"likeCount":1}
T2      lockById ✔ (최신 값을 보는 잠금 읽기)
T2      INSERT IGNORE → 0행(UNIQUE에 이미 있음) → UPDATE 안 함
T2      SELECT p.likeCount  → 0 !!  ← 평범한 SELECT라 T2의 스냅샷(맨 위, T1 커밋 전)을 본다
T2      COMMIT → 응답 {"liked":true,"likeCount":0}
T3..T5  T2와 같음
```

- **DB의 최종 값은 1로 맞다.** UPDATE는 최신 값을 보고 했고, 실제로 넣은 트랜잭션만 더했으니까.
- 틀린 것은 **T2~T5의 마지막 SELECT**다. 이 트랜잭션들은 잠금을 기다리기 **전에** `readable()`에서 이미 일관된 읽기를 해서 스냅샷이 "T1 커밋 전"으로 정해졌다. 잠금 읽기(`lockById`)는 최신 값을 봤지만, 그 뒤의 평범한 SELECT는 다시 옛 스냅샷으로 돌아간다.
- T1은 왜 맞았나: 자기가 UPDATE한 행은 자기 변경이 보인다(MVCC에서 내 트랜잭션의 변경은 언제나 보인다).

**고친 방법: 공감 수도 잠금 읽기로 읽는다.**

```java
@Lock(LockModeType.PESSIMISTIC_WRITE)
@Query("select p.likeCount from Post p where p.id = :postId")
int findLikeCount(@Param("postId") Long postId);
```

`FOR UPDATE`는 스냅샷이 아니라 최신 커밋 값을 본다(3.3). 이 행은 `lockById`로 이미 내가 X를 쥐고 있으므로 더 기다리지도 않는다.

**다른 방법들과 비교**

| 방법 | 장점 | 단점 |
| --- | --- | --- |
| **공감 수를 잠금 읽기로 (선택)** | 한 줄. 이미 잠근 행이라 비용 없음 | "왜 여기만 `@Lock`이지?"를 주석으로 남겨야 함 |
| 그 트랜잭션만 READ COMMITTED (`@Transactional(isolation = READ_COMMITTED)`) | 문장마다 새 스냅샷이라 최신 값 | 서비스 전체의 읽기 규칙이 바뀌어 다른 판단(가시성 등)에도 영향. 설정이 흩어짐 |
| `lockById`가 `id` 대신 `likeCount`를 돌려주게 | 쿼리 하나 줄어듦 | 넣기·지우기 **전** 값이라 ±1을 자바에서 계산해야 함. 댓글도 같은 메서드를 써서 의미가 섞임 |
| 응답을 "INSERT 결과 + 읽은 값"으로 계산 | 쿼리 없음 | 결국 읽은 값이 스냅샷이면 같은 문제 |
| 트랜잭션 맨 앞에서 잠금부터 (`readable()`보다 먼저 `lockById`) | 첫 읽기가 잠금 읽기라 이후 스냅샷이 커밋 뒤로 정해짐 | 볼 수 없는 글(404)인지 판단하기 전에 남의 글 행을 잠근다. 순서(404 → 401)도 꼬임 |

## 5. 이 프로젝트에서는

### 5.1 `LikeService`: 판단 → 잠금 → 넣기 → 수 → 읽기

`src/main/java/com/nhnacademy/blog/reaction/application/LikeService.java`

```java
@Transactional
public LikeResult like(Blog blog, Long postId, LoginMember member) {
    Post post = likable(blog, postId, member);
    postRepository.lockById(post.getId());
    if (postLikeRepository.insertIfAbsent(post.getId(), member.id()) == 1) {
        postRepository.addLikeCount(post.getId(), 1);
    }
    return new LikeResult(true, currentCount(post.getId()));
}
```

- `@Transactional`: 아래 네 일이 한 트랜잭션이다. 공감 행과 공감 수가 하나만 반영되는 일이 없다.
- `likable(...)`: 안에서 `postReadService.readable(...)`(404, 구독자 공개 403)을 먼저 하고, 비회원이면 401. 상태 코드 순서 404 → 401([29](./29-comments-design.md) 3.2). `readable`에 붙은 `@Transactional(readOnly = true)`는 기본 전파 `REQUIRED`라 **바깥 트랜잭션에 합류**한다. 그래서 여기서 한 평범한 SELECT가 이 트랜잭션의 **첫 일관된 읽기**가 되어 스냅샷을 정한다(4.2).
- `postRepository.lockById(...)`: 글 행 X 잠금. 같은 글의 공감·댓글 쓰기를 줄 세운다(4.1). 가시성 판단 **뒤**에 두어서 볼 수 없는 글은 잠그지 않는다.
- `insertIfAbsent(...) == 1`: 실제로 새 행을 넣었을 때만 1. 이미 공감했으면 0이고 수를 건드리지 않는다. **"바뀐 행이 있을 때만 수를 고친다"**가 연타·재시도에도 수가 어긋나지 않는 핵심이다.
- `addLikeCount(..., 1)`: 원자적 UPDATE(최신 값 + 1).
- `currentCount(...)` → `findLikeCount`: 잠금 읽기로 최신 값(4.2).

끄기도 같은 모양이다.

```java
@Transactional
public LikeResult unlike(Blog blog, Long postId, LoginMember member) {
    Post post = likable(blog, postId, member);
    postRepository.lockById(post.getId());
    if (postLikeRepository.deleteIfPresent(post.getId(), member.id()) == 1) {
        postRepository.addLikeCount(post.getId(), -1);
    }
    return new LikeResult(false, currentCount(post.getId()));
}
```

`deleteIfPresent`가 지운 행 수(0 또는 1)를 돌려주므로, 이미 꺼진 공감을 또 꺼도 수가 음수로 가지 않는다.

### 5.2 `PostLikeRepository`: 한 문장으로 멱등 PUT

`src/main/java/com/nhnacademy/blog/reaction/domain/PostLikeRepository.java`

```java
@Modifying
@Query(value = "INSERT IGNORE INTO post_like (post_id, member_id) VALUES (:postId, :memberId)", nativeQuery = true)
int insertIfAbsent(@Param("postId") Long postId, @Param("memberId") Long memberId);
```

- 테이블에 `CONSTRAINT uk_post_like_member_id_post_id UNIQUE (member_id, post_id)`가 있다. 같은 회원·같은 글의 두 번째 행은 DB가 거절한다.
- `INSERT IGNORE`: MySQL 문법. UNIQUE 위반 같은 오류를 **경고로 바꾸고 그 행을 건너뛴다.** 영향받은 행 수가 0이 된다. 오류가 안 나니 트랜잭션도 롤백 표시가 되지 않는다.
- "있나 보고(`exists`) 없으면 save"로 두 번에 나누면 check-then-act 틈이 생긴다([23](./23-transactions-locking.md) 2장). 동시에 온 두 요청이 둘 다 "없음"을 보고 둘 다 INSERT하면 하나는 `DataIntegrityViolationException`이 난다. 한 문장이면 틈이 없다.
- `nativeQuery = true`: `INSERT IGNORE`는 JPQL에 없는 MySQL 전용 문법이라 SQL을 그대로 쓴다.
- 주의: `INSERT IGNORE`는 UNIQUE 말고 다른 오류(예: 외래 키 위반, 잘린 값)도 경고로 삼킨다. 여기서는 앞에서 글이 있는 것을 확인했고, 회원 id는 로그인 토큰에서 오므로 받아들였다.

### 5.3 `PostRepository`: 세 개의 쿼리와 주석

`src/main/java/com/nhnacademy/blog/post/domain/PostRepository.java`

```java
/** 공감 수 늘리기·줄이기 (SOC-01). 댓글 수와 같은 방식이다. */
@Modifying(clearAutomatically = true)
@Query("update Post p set p.likeCount = p.likeCount + :delta, p.updatedAt = p.updatedAt where p.id = :postId")
int addLikeCount(@Param("postId") Long postId, @Param("delta") int delta);
```

- `p.likeCount + :delta`: 최신 값에 더한다(3.3).
- `p.updatedAt = p.updatedAt`: 공감은 글을 고친 것이 아니라 `ON UPDATE CURRENT_TIMESTAMP`로 수정 시각이 바뀌지 않게 같은 값을 넣는다([27](./27-soft-delete-bulk-update.md)). 테스트 `likeAndUnlikeAreIdempotent`가 공감 뒤 상세의 `updatedAt`이 없는지 본다.
- `clearAutomatically = true`: JPQL UPDATE는 영속성 컨텍스트(1차 캐시)를 거치지 않고 DB에 바로 간다. 그래서 메모리의 `Post` 객체는 옛 `likeCount`를 들고 있게 된다. 끝난 뒤 영속성 컨텍스트를 비워서, 다음에 읽을 때 DB에서 다시 읽게 한다. **이것은 JPA 메모리와 DB 사이의 문제**고, 이 문서의 스냅샷 문제는 **DB 안에서 트랜잭션끼리**의 문제다. 이름이 비슷하게 "옛 값"이라 헷갈리기 쉽다. 컨텍스트를 비워도 다시 읽는 SELECT가 평범한 SELECT면 여전히 스냅샷을 본다.

```java
@Lock(LockModeType.PESSIMISTIC_WRITE)
@Query("select p.likeCount from Post p where p.id = :postId")
int findLikeCount(@Param("postId") Long postId);
```

- `@Lock(PESSIMISTIC_WRITE)`: Spring Data JPA가 이 쿼리를 잠금 모드와 함께 실행하고, Hibernate의 MySQL 방언이 `… for update`를 붙인다. 엔티티 전체가 아니라 숫자 한 칸을 고르는 쿼리에도 붙일 수 있다.
- 주석에 "왜 잠금 읽기인가"를 남겼다. 나중에 누군가 "읽기만 하는데 왜 잠그지?" 하고 지우면 버그 2가 돌아온다. 테스트가 그것을 잡는다(5.5).

```java
@Lock(LockModeType.PESSIMISTIC_WRITE)
@Query("select p.id from Post p where p.id = :postId")
Optional<Long> lockById(@Param("postId") Long postId);
```

- 엔티티 대신 `p.id`만 고른다. 필요한 것은 "잠금"뿐이라 행 내용(본문 `mediumtext` 같은 큰 칸)을 읽어 올 필요가 없다.
- 반환값은 쓰지 않는다. 글이 있는지는 앞의 `readable`에서 이미 확인했다.

### 5.4 `CommentService`: 같은 잠금을 같은 순서로

`src/main/java/com/nhnacademy/blog/comment/application/CommentService.java`

```java
@Transactional
public CommentView write(Blog blog, Long postId, LoginMember member, String content, Long parentId) {
    Post post = writablePost(blog, postId, member);
    // 댓글 INSERT(외래 키 공유 잠금) 뒤 댓글 수 UPDATE(배타 잠금)가 동시에 엇갈리면 데드락이라 글 행부터 잠근다
    postRepository.lockById(post.getId());
    Member author = memberRepository.getReferenceById(member.id());
    Comment comment = commentRepository.save(parentId == null
            ? Comment.write(post, author, content.trim(), false)
            : Comment.reply(parentOf(post, parentId), author, content.trim(), false));
    postRepository.addCommentCount(post.getId(), 1);
    ...
}
```

지우기도 `postRepository.lockById(comment.getPost().getId());`를 `comment.delete(...)`와 `addCommentCount(..., -1)` 앞에 둔다.

- 공감과 댓글이 **같은 글 행을 같은 순서(글 행 먼저)로** 잠근다. 한쪽은 글 → 공감, 다른 쪽은 댓글 → 글처럼 순서가 다르면 둘 사이에서 또 데드락이 날 수 있다(3.6 원칙 1).
- 댓글 응답은 공감 수를 돌려주지 않는다. 그래서 버그 2 같은 "응답 숫자" 문제는 없다. 목록의 `totalCount`는 다른 요청(다른 트랜잭션)에서 읽으므로 최신 값이다.

### 5.5 테스트: 빨강 → 초록

`src/test/java/com/nhnacademy/blog/reaction/LikeIntegrationTest.java`

```java
@Test
void rapidConcurrentClicksCountOnce() throws Exception {
    List<Callable<MockHttpServletResponse>> clicks = new ArrayList<>();
    for (int i = 0; i < 10; i++) {
        clicks.add(() -> send(put("/api/posts/" + post.getId() + "/like"), reader).andReturn().getResponse());
    }
    try (ExecutorService executor = Executors.newFixedThreadPool(10)) {
        for (Future<MockHttpServletResponse> result : executor.invokeAll(clicks)) {
            assertThat(result.get().getStatus()).isEqualTo(200);
            // 늦게 처리된 요청도 앞 요청이 커밋한 수를 돌려줘야 한다(옛 스냅샷의 0이 아니라)
            assertThat(result.get().getContentAsString()).contains("\"likeCount\":1");
        }
    }

    assertThat(jdbcTemplate.queryForObject("SELECT COUNT(*) FROM post_like WHERE post_id = ?", Integer.class,
            post.getId())).isEqualTo(1);
    assertThat(jdbcTemplate.queryForObject("SELECT like_count FROM post WHERE id = ?", Integer.class,
            post.getId())).isEqualTo(1);
}
```

- 같은 회원(`reader`)이 PUT 10개를 스레드 10개로 동시에 보낸다. `invokeAll`은 모두 던지고 모두 끝날 때까지 기다린다([23](./23-transactions-locking.md) 5.5).
- 처음 이 테스트는 **상태 코드와 최종 수만** 봤다. 그래서 버그 2가 있어도 통과했다. curl로 실제 서버를 두드려 보고서야 알았다.
- 응답 본문마다 `"likeCount":1`을 확인하는 줄을 더하고, **고치기 전에** 돌려서 실패하는 것(빨강)을 먼저 봤다. 그다음 `findLikeCount`에 `@Lock`을 붙여 통과(초록)를 확인했다. 고친 코드가 정말 그 버그를 고쳤다는 증거다. 그리고 두 번 더 돌려 우연이 아님을 확인했다.

`src/test/java/com/nhnacademy/blog/reaction/CountConsistencyIntegrationTest.java`의 `likeCountMatchesRowsUnderConcurrentToggling`은 **다섯 명**이 켜기·끄기를 섞어 30번 동시에 보낸다. 모든 응답이 200(데드락 500이 없음)이고, 끝나고 `like_count`가 `post_like` 행 수와 같은지 본다(`assertCountsMatchRows`). 버그 1을 잡은 테스트다. 이 테스트는 응답 숫자를 보지 않는다. 여러 사람이 섞이면 각 응답의 "그 순간 수"가 정해진 값이 아니기 때문이다.

### 5.6 무엇을 고쳤나(커밋)

| 커밋 | 내용 |
| --- | --- |
| `e15146c` | `PostRepository.lockById` 추가, `LikeService.like/unlike`와 `CommentService.write/delete`에서 먼저 호출(버그 1) |
| `8580ac8` | `findLikeCount`에 `@Lock(PESSIMISTIC_WRITE)`, 테스트에 응답 본문 검사 추가(버그 2) |

### 5.7 (스텝 8) 조회수에서 다시 만난 두 문제

조회 기록(T053)도 "자식 행 INSERT(`view_log`) + 부모 행 숫자 UPDATE(`post.view_count`)"라 공감과 모양이 같다. 그래서 같은 두 문제가 그대로 나타난다.

- **데드락(버그 1과 같음)**: 잠금 없이 같은 글에 동시 조회를 보내는 테스트를 돌리자 `Deadlock found when trying to get lock`으로 500이 났다(스텝 8에서 `lockById`를 일부러 빼고 확인). `view_log`의 외래 키 확인이 글 행에 S 잠금, `view_count` UPDATE가 X 잠금을 원하는 같은 고리다. `ViewService.record`도 맨 앞에서 `lockById`를 부른다.
- **옛 스냅샷(버그 2와 같음)**: 조회는 "5분 안에 본 기록이 있나"를 평범한 SELECT로 묻는다. 잠금 **전에** 같은 트랜잭션에서 평범한 SELECT를 하면 스냅샷이 앞 요청의 커밋 전으로 정해져 같은 사람을 두 번 센다. 공감은 마지막 읽기를 잠금 읽기로 바꿔 고쳤지만, 조회는 다른 방법을 썼다. **잠금을 트랜잭션의 첫 문장으로** 두고, 가시성 확인(`readable`)은 컨트롤러에서 **다른 트랜잭션**으로 먼저 한다. 그러면 잠금을 얻은 뒤의 첫 평범한 SELECT가 스냅샷을 정하므로 앞 요청의 기록이 보인다.

두 방법의 차이: 공감처럼 같은 트랜잭션 안에서 확인해야 하면 "잠금 뒤의 읽기를 잠금 읽기로", 확인을 앞으로 뺄 수 있으면 "잠금을 첫 문장으로". 자세한 것은 [34](./34-view-count.md) 4.2~4.4.

## 6. 자주 하는 실수와 함정

1. **"잠금을 안 썼으니 데드락은 없다"**: 외래 키 확인(S), UPDATE(X), UNIQUE 확인처럼 DB가 스스로 거는 잠금이 있다. 자식 INSERT 뒤 부모 UPDATE는 대표적인 데드락 모양이다.
2. **S를 쥐고 X로 올리기**: 같은 행을 먼저 공유로 잡고(명시적 `FOR SHARE`든 외래 키든) 나중에 배타로 바꾸는 흐름은 동시에 둘이 하면 데드락이다. 처음부터 X.
3. **잠금 순서가 메서드마다 다름**: 공감은 글 → 공감 행, 댓글은 댓글 → 글처럼 다르면 교차 데드락. 공통 규칙("글 행부터")을 정하고 주석으로 남긴다.
4. **REPEATABLE READ에서 "업데이트 뒤 다시 읽으면 최신"이라고 믿기**: 내 변경은 보이지만, 남이 내 스냅샷 이후 커밋한 변경은 평범한 SELECT로는 안 보인다. 최신 값이 필요하면 잠금 읽기.
5. **스냅샷이 `BEGIN`에 정해진다고 생각하기**: 첫 일관된 읽기 때다. 그래서 "어디서 처음 읽었나"가 중요하다. 다른 서비스 메서드(`readable`) 안의 읽기도 같은 트랜잭션이면 해당된다.
6. **`clearAutomatically`로 스냅샷 문제가 풀린다고 생각하기**: 그건 JPA 1차 캐시 문제를 푼다. DB 스냅샷은 그대로다.
7. **동시성 테스트에서 최종 상태만 확인**: 중간 응답이 틀려도 통과한다. 사용자에게 보이는 값(응답 본문)도 검사한다.
8. **데드락 예외를 잡아 무시**: 롤백된 쪽의 작업은 없던 일이 된다. 무시하면 사용자는 "됐다"고 보는데 실제로는 안 된 상태가 된다. 고치거나, 재시도하거나, 오류를 알린다.
9. **잠금 범위를 넓게**: 블로그 전체나 테이블을 잠그면 관계없는 글끼리 기다린다. 글 행 하나처럼 경쟁하는 단위만.
10. **격리 수준을 전역으로 바꿔 해결**: 한 메서드의 문제를 고치려고 전체를 READ COMMITTED로 바꾸면 다른 곳의 가정(같은 트랜잭션 안에서 같은 값)이 깨질 수 있다. 바꾸려면 이유와 범위를 좁혀서.

## 7. 직접 해 보기

MySQL 터미널 두 개를 연다(계정은 `docker-compose.yml`의 `blog`/`blog`, DB `blog`).

```bash
docker compose up -d
docker exec -it blog-mysql mysql -ublog -pblog blog     # 터미널 1
docker exec -it blog-mysql mysql -ublog -pblog blog     # 터미널 2
```

공감 수가 0인 공개 글 하나의 id를 고른다(`SELECT id, like_count FROM post WHERE deleted_at IS NULL LIMIT 5;`). 아래에서는 10이라고 한다.

**실습 1. 스냅샷 보기 (버그 2를 손으로)**

```sql
-- 터미널 1
SELECT @@transaction_isolation;                 -- REPEATABLE-READ
START TRANSACTION;
SELECT like_count FROM post WHERE id = 10;      -- 0. 이 순간 스냅샷이 정해진다

-- 터미널 2 (자동 커밋)
UPDATE post SET like_count = like_count + 1, updated_at = updated_at WHERE id = 10;

-- 터미널 1
SELECT like_count FROM post WHERE id = 10;              -- 여전히 0 (스냅샷)
SELECT like_count FROM post WHERE id = 10 FOR UPDATE;   -- 1 (잠금 읽기는 최신)
SELECT like_count FROM post WHERE id = 10;              -- 다시 0!
ROLLBACK;

-- 터미널 2: 되돌리기
UPDATE post SET like_count = like_count - 1, updated_at = updated_at WHERE id = 10;
```

같은 트랜잭션 안에서 잠금 읽기는 1, 평범한 읽기는 0을 보는 것이 버그 2와 똑같은 상황이다. 터미널 1에서 `START TRANSACTION` 바로 뒤에 SELECT 없이 터미널 2의 UPDATE를 먼저 하고, 그다음 첫 SELECT를 하면 1이 보인다. 스냅샷이 BEGIN이 아니라 첫 읽기 때 정해진다는 증거다.

**실습 2. 데드락 만들기 (버그 1을 손으로)**

공감하지 않은 회원 id 두 개를 고른다(예: 101, 102).

```sql
-- 터미널 1
START TRANSACTION;
INSERT INTO post_like (post_id, member_id) VALUES (10, 101);   -- 글 10에 S

-- 터미널 2
START TRANSACTION;
INSERT INTO post_like (post_id, member_id) VALUES (10, 102);   -- 글 10에 S (같이 가짐)

-- 터미널 1
UPDATE post SET like_count = like_count + 1, updated_at = updated_at WHERE id = 10;   -- 기다림

-- 터미널 2
UPDATE post SET like_count = like_count + 1, updated_at = updated_at WHERE id = 10;
-- 둘 중 한 터미널에 ERROR 1213 (40001): Deadlock found when trying to get lock; try restarting transaction
-- (대개 고리를 완성한 터미널 2. InnoDB가 고르므로 터미널 1일 수도 있다) 남은 쪽의 UPDATE는 그 순간 끝난다

-- 터미널 1
ROLLBACK;                                       -- 실습이니 되돌린다 (터미널 2도 ROLLBACK)
```

데드락 기록을 본다(root 계정이 필요할 수 있다: `docker exec -it blog-mysql mysql -uroot -proot blog`).

```sql
SHOW ENGINE INNODB STATUS\G
```

`LATEST DETECTED DEADLOCK` 절에 `(1) TRANSACTION`, `(2) TRANSACTION`이 나오고, 각각 `HOLDS THE LOCK(S)`(쥔 잠금)와 `WAITING FOR THIS LOCK TO BE GRANTED`(기다린 잠금), 마지막에 `WE ROLL BACK TRANSACTION (2)`가 있다. `lock mode S`와 `lock_mode X`가 같은 `post` 테이블 레코드에 걸린 것을 찾아본다.

이번에는 두 터미널 모두 맨 앞에 `SELECT id FROM post WHERE id = 10 FOR UPDATE;`를 넣고 같은 순서로 해 본다. 터미널 2는 첫 줄에서 기다렸다가 터미널 1이 끝나면 진행하고, 데드락은 나지 않는다.

**실습 3. 잠금을 빼고 테스트 돌리기**

```bash
git switch -c study/no-lock
```

1. `LikeService.like/unlike`의 `postRepository.lockById(post.getId());` 두 줄을 지운다.
2. `./mvnw test -Dtest=CountConsistencyIntegrationTest#likeCountMatchesRowsUnderConcurrentToggling`을 여러 번(5~10번) 돌린다. 가끔 상태 500(데드락)으로 실패한다. 매번은 아니다. 타이밍에 달려 있다.
3. 되돌리고, 이번에는 `findLikeCount`의 `@Lock` 줄만 지운다. `./mvnw test -Dtest=LikeIntegrationTest#rapidConcurrentClicksCountOnce`를 돌리면 `"likeCount":1`을 찾지 못해 실패하는 것을 본다.
4. `git restore . && git switch -`로 되돌리고 `git branch -D study/no-lock`.

**실습 4. 격리 수준 바꿔 보기**

실습 1을 터미널 1에서 `SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;`를 먼저 하고 다시 해 본다. 두 번째 평범한 SELECT가 바로 1을 본다. 끝나면 터미널을 닫거나 `SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ;`로 되돌린다.

## 8. 확인 문제

1. MySQL InnoDB의 기본 격리 수준은? 그 수준에서 평범한 SELECT는 어느 시점의 값을 보나?
<details><summary>답</summary>REPEATABLE READ. 그 트랜잭션에서 처음 한 일관된 읽기(평범한 SELECT) 때 정해진 스냅샷의 값을 본다. BEGIN 시점이 아니다.</details>

2. REPEATABLE READ에서 `UPDATE post SET like_count = like_count + 1`이 다른 트랜잭션의 커밋을 놓치지 않는 이유는?
<details><summary>답</summary>UPDATE·DELETE와 잠금 읽기는 스냅샷이 아니라 최신 커밋 값을 보고 그 값에 더한다. 그래서 원자적 UPDATE는 격리 수준과 상관없이 수를 잃지 않는다.</details>

3. 서로 다른 회원 A, B가 같은 글에 동시에 공감할 때 데드락이 난 과정을 잠금 종류로 설명하라.
<details><summary>답</summary><code>post_like</code> INSERT의 외래 키 확인이 글 행에 공유(S) 잠금을 건다. A와 B 모두 S를 쥔다(S끼리는 같이 가능). 이어서 둘 다 <code>like_count</code> UPDATE를 위해 같은 글 행의 배타(X) 잠금을 원하는데, 상대의 S가 풀려야 얻을 수 있어 서로 기다린다. InnoDB가 감지해 한쪽을 롤백한다.</details>

4. `lockById`가 데드락을 없애는 이유와, 그 대가는?
<details><summary>답</summary>트랜잭션이 처음부터 글 행의 X 잠금을 잡으므로 S를 쥔 채 X를 기다리는 순간이 없다. 같은 글의 공감·댓글 쓰기가 차례로 처리된다. 대가는 같은 글에 대한 요청이 직렬화되는 것(다른 글끼리는 영향 없음).</details>

5. 같은 회원이 PUT을 동시에 5번 보냈을 때 DB의 공감 수는 1인데 응답 넷이 0이었던 이유는?
<details><summary>답</summary>늦은 트랜잭션들이 잠금을 기다리기 전에 <code>readable()</code>에서 평범한 SELECT를 해서 스냅샷이 첫 트랜잭션 커밋 전으로 정해졌다. 잠금을 얻은 뒤 INSERT IGNORE는 0행이라 UPDATE를 안 했고, 마지막의 평범한 SELECT가 옛 스냅샷의 0을 읽었다.</details>

6. 그 버그를 `findLikeCount`에 `@Lock(PESSIMISTIC_WRITE)`를 붙여 고친 이유와, 추가로 기다리지 않는 이유는?
<details><summary>답</summary>잠금 읽기(<code>FOR UPDATE</code>)는 스냅샷이 아니라 최신 커밋 값을 본다. 그 행은 앞의 <code>lockById</code>로 같은 트랜잭션이 이미 X 잠금을 쥐고 있어서 다시 기다리지 않는다.</details>

7. `@Modifying(clearAutomatically = true)`만으로 버그 2가 안 고쳐지는 이유는?
<details><summary>답</summary><code>clearAutomatically</code>는 JPA 영속성 컨텍스트(메모리)를 비워 다음에 DB에서 다시 읽게 할 뿐이다. 다시 읽는 SELECT가 평범한 SELECT면 DB는 여전히 그 트랜잭션의 스냅샷을 돌려준다.</details>

8. `INSERT IGNORE`와 UNIQUE로 PUT을 멱등하게 만든 방법과, 공감 수를 언제만 고치나?
<details><summary>답</summary>UNIQUE(member_id, post_id) 때문에 두 번째 INSERT는 무시되고 영향받은 행 수 0을 돌려준다. 한 문장이라 check-then-act 틈이 없다. 반환값이 1일 때만(실제로 넣었을 때만) <code>like_count</code>를 +1 한다. 끄기도 지운 행이 1일 때만 −1.</details>

9. 공감과 댓글 쓰기가 같은 글 행을 "같은 순서로" 잠가야 하는 이유는?
<details><summary>답</summary>잠금 순서가 다르면(예: 한쪽은 글 → 자식, 다른 쪽은 자식 → 글) 두 흐름이 서로의 잠금을 기다리는 교차 데드락이 생길 수 있다. 모든 코드가 "글 행부터"라는 같은 순서를 지키면 그런 고리가 생기지 않는다.</details>

10. 동시성 테스트가 처음에 버그 2를 못 잡은 이유와, 어떻게 고쳤나?
<details><summary>답</summary>상태 코드와 최종 DB 값만 확인했고, 응답 본문의 수는 보지 않았다. 각 응답에 <code>"likeCount":1</code>이 있는지 검사하는 줄을 더해, 고치기 전에 실패하는 것을 먼저 확인한 뒤 고쳤다.</details>

## 9. 더 읽을거리

- MySQL 8.4 레퍼런스, "Transaction Isolation Levels", "Consistent Nonlocking Reads", "Locking Reads"
- MySQL 8.4 레퍼런스, "InnoDB Locking"(Shared and Exclusive Locks, Record Locks), "Locks Set by Different SQL Statements in InnoDB"(외래 키 확인 시 공유 잠금)
- MySQL 8.4 레퍼런스, "Deadlocks in InnoDB", "Deadlock Detection", "How to Minimize and Handle Deadlocks", `SHOW ENGINE INNODB STATUS`
- MySQL 8.4 레퍼런스, "InnoDB Multi-Versioning", "Undo Logs"
- MySQL 8.4 레퍼런스, `INSERT` 문의 `IGNORE` 수정자
- Spring Data JPA 레퍼런스, "Locking"(`@Lock`), Spring Framework 레퍼런스 `@Transactional(isolation = …)`, 예외 변환(`DataAccessException` 계층, `CannotAcquireLockException`)
- 마틴 클레프만, 『데이터 중심 애플리케이션 설계』 7장 "트랜잭션": 스냅샷 격리, 갱신 손실, 쓰기 왜곡
- 대규모 카운터 설계: 카운터를 행 여러 개로 나눠 더하기(sharded counter), Redis `INCR`로 모았다가 주기적으로 DB에 반영하기
