# 57. 스팸 막기: 블로그별 차단과 금칙어

> 관련 스텝: [스텝 20](../step-20.md) (T084·T085 스팸·차단) · 관련 개념: [50 같은 규칙의 두 기능을 한 코드로](./50-shared-rules-comment-guestbook.md)(댓글·방명록), [51 구독과 알림](./51-subscription-notification.md), [53 서비스 관리](./53-admin-moderation-audit.md)(서비스 전체 제재와 비교), [56 저장한 글](./56-bookmark-snapshot.md)(INSERT IGNORE), [16 인가와 가시성 판단](./16-authorization-visibility.md)

## 1. 이 문서로 배우는 것

- 서비스 관리자의 제재(정지)와 **블로그 주인의 차단**은 무엇이 다른가
- 검사를 **한 곳(SpamGuard)**에 두고 여러 입구(댓글·방명록·구독)가 부르게 하기
- 차단할 때 **함께 정리할 데이터**(기존 구독)
- 금칙어 검사: 대소문자 무시, 포함 검사의 한계, DB 콜레이션과 UNIQUE
- 개수 한도와 중복을 DB와 코드 중 어디서 막나
- 상태 코드 고르기: 차단은 403, 금칙어는 400, 이미 차단은 409

## 2. 왜 필요한가

명세 MNG-04: "블로그 주인이 회원을 차단하고 금칙어를 정한다. 차단된 회원은 그 블로그에 댓글·방명록을 쓸 수 없고 구독할 수 없으며, 차단하면 기존 구독도 지워진다. 차단 사실은 따로 알리지 않는다. 금칙어는 블로그당 100개까지, 댓글·방명록을 새로 쓸 때 대소문자를 무시하고 검사한다. 이미 있던 댓글은 그대로 두고 주인이 MNG-02에서 지운다."

댓글 관리(스텝 14)로 주인은 광고 댓글을 **지울** 수 있었다. 하지만 같은 사람이 또 쓰면 또 지워야 한다. 차단과 금칙어는 **쓰기 전에** 막는 장치다.

## 3. 기본 개념

### 3.1 누가, 어디까지 막나

| | 서비스 정지(스텝 18) | 블로그 차단(이번) |
| --- | --- | --- |
| 누가 | 서비스 관리자 | 그 블로그 주인 |
| 범위 | 서비스 전체(로그인부터) | 그 블로그 한 곳의 댓글·방명록·구독 |
| 기록 | 관리 이력(고치지 않음) | `blog_blocked_member` 한 행(해제하면 지움) |
| 알림 | 정지 안내(사유·기간) | 알리지 않음 |

블로그 차단은 "내 집에 못 오게 하기"다. 차단된 사람도 다른 블로그에서는 평소대로 쓰고, 이 블로그의 공개 글도 **읽을 수는 있다**. 명세가 막는 것은 쓰기와 구독뿐이다. 글까지 숨기면 로그아웃해 다시 보면 그만이라 의미가 없다.

### 3.2 차단 사실을 알리지 않기

차단된 사람이 댓글을 쓰면 403 `BLOCKED_BY_BLOG`, "이 블로그에서 차단되었습니다."가 나온다. 이것이 알리는 것 아니냐고 물을 수 있다. 명세의 "따로 알리지 않는다"는 **차단하는 순간 알림을 보내지 않는다**는 뜻이다(구독 알림처럼 알림함에 넣지 않음). 쓰려는 순간에 이유를 말하지 않으면 사용자는 "서버 오류인가?" 하고 계속 시도한다. 그래서 그때는 짧게 알린다.

### 3.3 함께 정리할 데이터

차단은 "앞으로 못 하게"만이 아니라 "지금 이어진 관계"도 정리해야 한다.

- **구독**: 차단된 사람이 구독 중이면 피드에 이 블로그 새 글이 계속 나온다. 명세대로 차단할 때 지운다.
- **이미 쓴 댓글**: 지우지 않는다(명세: 주인이 MNG-02에서 지움). 차단이 실수였을 때 되돌릴 수 없는 일을 만들지 않으려는 것이다.
- **알림**: 차단된 사람이 전에 받은 알림은 그대로다.

[54](./54-theme-move-delete-withdraw.md)의 "삭제·탈퇴 정리 순서"와 같은 질문이다. **새 상태를 만들 때마다 "이것과 이어진 데이터는?"을 묻는다.**

### 3.4 금칙어 검사의 방식

| 방식 | 예 | 장단점 |
| --- | --- | --- |
| 포함 검사(이 프로젝트) | 내용에 "카지노"가 들어 있나 | 단순. "카 지 노", "ㅋr지노"처럼 바꿔 쓰면 못 잡고, 짧은 낱말은 엉뚱한 글도 막는다 |
| 낱말 단위 | 띄어쓰기로 나눈 낱말이 같은가 | 영어엔 맞지만 한국어 조사("카지노에서")를 못 잡는다 |
| 정규식·자모 분해·기계학습 | 바꿔 쓴 것까지 | 복잡하고 틀린 차단도 늘어난다 |

명세는 "대소문자를 무시하고 검사"까지만 정했다. 이 서비스의 금칙어는 주인이 자기 블로그에 거는 **가벼운 필터**라 포함 검사로 충분하다. 바꿔 쓴 것까지 잡는 일은 차단과 댓글 관리가 맡는다.

### 3.5 대소문자 무시: 자바와 DB 두 곳

- **검사(자바)**: 내용과 낱말을 모두 `toLowerCase(Locale.ROOT)`로 바꿔 `contains`. `Locale.ROOT`를 쓰는 이유: 기본 로케일이 터키어면 `"I".toLowerCase()`가 점 없는 `ı`가 되어 비교가 깨진다. 언어와 상관없는 비교에는 `Locale.ROOT`를 쓴다.
- **중복(DB)**: `blog_banned_word`에 `UNIQUE(blog_id, word)`가 있다. 이 DB의 문자열 비교 규칙(콜레이션)은 MySQL 8 기본 `utf8mb4_0900_ai_ci`이고, `ci`는 case-insensitive(대소문자 무시)다. 그래서 "Casino"가 있으면 "casino"는 UNIQUE에 걸린다. 테스트가 이것을 확인한다(5.6).

### 3.6 상태 코드 고르기

| 상황 | 코드 | 이유 |
| --- | --- | --- |
| 차단된 회원이 댓글·방명록·구독 | 403 `BLOCKED_BY_BLOG` | 누구인지는 알지만(인증됨) 이 일은 허락되지 않음 |
| 금칙어가 든 댓글 | 400 `BANNED_WORD` | 요청 **내용**이 규칙에 맞지 않음. 내용을 고치면 된다 |
| 이미 차단한 회원을 또 차단 | 409 `ALREADY_BLOCKED` | 지금 상태와 충돌 |
| 금칙어 101번째 | 409 `BANNED_WORD_LIMIT` | 지금 상태(100개)와 충돌 |
| 같은 금칙어 | 409 `NAME_TAKEN` | 기존 "이름 중복"과 같은 코드(카테고리·태그) |
| 자기 자신 차단 | 400 `memberId` | 입력 값이 틀림 |

차단은 왜 멱등하게(이미 차단이면 그냥 201) 하지 않았나? 구독·저장은 버튼 하나로 "이 상태로"를 말하는 일이지만, 차단은 주인이 **메모와 함께** 하는 관리 작업이다. 이미 차단된 사람이라는 사실을 알려 주는 편이 쓸모 있다(메모가 덮어써지지 않는다는 것도). 해제는 멱등(204)이다. 없는 차단을 풀어도 원하는 상태는 이미 이뤄져 있다.

## 4. 동작 원리

```
[차단] POST /api/manage/blocked-members { memberId, memo }   (블로그 주소, 주인만)
  → BlogOwnerGuard: 주인이 아니면 403
  → BlogSpamService.block
       회원 없음·탈퇴 → 404 / 자기 자신 → 400 memberId / 메모 200자 초과 → 400 memo
       INSERT IGNORE blog_blocked_member → 0행이면 409 ALREADY_BLOCKED
       DELETE subscription WHERE member_id = ? AND blog_id = ?       ← 같은 트랜잭션
  ← 201

[댓글 쓰기] POST /api/posts/{id}/comments
  → CommentService.writablePost: 볼 수 있는 글?(404) → 회원?(401) → 댓글 허용?(403 COMMENTS_DISABLED)
       → SpamGuard.requireNotBlocked(403 BLOCKED_BY_BLOG)
  → write: SpamGuard.requireNoBannedWord(400) → 저장

[방명록 쓰기] GuestbookService.requireWritable → SpamGuard.requireNotBlocked → write: requireNoBannedWord
[구독] SubscriptionService.subscribe → … → SpamGuard.requireNotBlocked
```

## 5. 이 프로젝트에서는

### 5.1 검사를 한 곳에: `manage/application/SpamGuard`

```java
@Component
public class SpamGuard {

    /** 이 블로그에서 차단된 회원이면 403 BLOCKED_BY_BLOG. */
    @Transactional(readOnly = true)
    public void requireNotBlocked(Blog blog, Long memberId) {
        if (memberId != null && blockedMemberRepository.existsByBlogIdAndBlockedMemberId(blog.getId(), memberId)) {
            throw new BusinessException(ErrorCode.BLOCKED_BY_BLOG);
        }
    }

    /** 내용에 이 블로그의 금칙어가 들어 있으면(대소문자 무시) 400 BANNED_WORD. */
    @Transactional(readOnly = true)
    public void requireNoBannedWord(Blog blog, String content) {
        if (content == null) {
            return;
        }
        String text = content.toLowerCase(Locale.ROOT);
        for (BlogBannedWord word : bannedWordRepository.findByBlogIdOrderByIdAsc(blog.getId())) {
            if (text.contains(word.getWord().toLowerCase(Locale.ROOT))) {
                throw new BusinessException(ErrorCode.BANNED_WORD);
            }
        }
    }
}
```

- 댓글·방명록·구독 세 서비스가 이 클래스 하나를 부른다. 검사 규칙이 바뀌면(예: 금칙어를 정규식으로) 여기만 고친다. 댓글과 방명록이 같은 규칙을 한 코드로 쓰는 것([50](./50-shared-rules-comment-guestbook.md))과 같은 생각이다.
- `memberId != null`: 비회원은 원래 댓글을 쓸 수 없어 그 전에 401로 끝나지만, 이 메서드만 떼어 봐도 안전하게 둔다.
- 금칙어는 블로그당 최대 100개라 쓸 때마다 다 읽어도 가볍다. 많아지면 캐시하거나 Aho-Corasick 같은 여러 낱말 동시 검색 알고리즘을 쓴다.
- `SpamGuard`는 `manage` 기능에 있고, `comment`·`subscription`이 부른다. 의존 방향은 "application → 다른 기능의 application"이라 계층 규칙([55](./55-module-boundary-archunit.md))에 맞다.

### 5.2 입구에 연결하기: 순서가 중요하다

```java
// CommentService.writablePost (발췌)
Post post = postReadService.readable(blog, postId, member == null ? null : member.id());   // 404
if (member == null) throw new BusinessException(ErrorCode.UNAUTHORIZED);                    // 401
if (!post.isCommentAllowed()) throw new BusinessException(ErrorCode.COMMENTS_DISABLED);     // 403
spamGuard.requireNotBlocked(post.getBlog(), member.id());                                   // 403 BLOCKED_BY_BLOG

// CommentService.write (발췌)
spamGuard.requireNoBannedWord(post.getBlog(), content);                                     // 400 BANNED_WORD
```

- 차단 검사는 **볼 수 있는 글인지(404), 로그인(401), 댓글 허용(403 `COMMENTS_DISABLED`) 뒤**다. 댓글을 막은 글이면 누구에게나 같은 403이니 차단 여부를 볼 필요가 없다. 차단 검사를 먼저 하면 차단된 사람이 비공개 글 번호에 댓글을 보내 "403(있음)"과 "404(없음)"로 글의 존재를 알아낼 수 있다.
- 블로그는 `post.getBlog()`로 정한다. 주소의 블로그가 아니라 **글이 속한 블로그**다. 이사한 글처럼 주소와 소속이 다를 수 있는 경우에도 맞는 블로그의 차단 목록을 본다.
- 방명록은 `GuestbookService.requireWritable(blog, member)`를 새로 두어 컨트롤러가 쓰기 전에 부른다. 구독은 `SubscriptionService.subscribe`가 "볼 수 있는 블로그 → 자기 블로그 아님" 다음에 부른다.

### 5.3 차단: `BlogSpamService.block`

```java
@Transactional
public void block(Blog blog, Long memberId, String rawMemo) {
    if (memberId == null) {
        throw BusinessException.invalidField("memberId", "차단할 회원을 골라 주세요.");
    }
    Member member = memberRepository.findById(memberId)
            .filter(found -> !found.isWithdrawn())
            .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));
    if (blog.isOwnedBy(member.getId())) {
        throw BusinessException.invalidField("memberId", "자기 자신은 차단할 수 없습니다.");
    }
    String memo = rawMemo == null || rawMemo.isBlank() ? null : rawMemo.strip();
    if (memo != null && memo.length() > BlogBlockedMember.MEMO_LENGTH) {
        throw BusinessException.invalidField("memo", "메모는 " + BlogBlockedMember.MEMO_LENGTH + "자까지입니다.");
    }
    if (blockedMemberRepository.insertIfAbsent(blog.getId(), memberId, memo) == 0) {
        throw new BusinessException(ErrorCode.ALREADY_BLOCKED);
    }
    subscriptionRepository.deleteIfPresent(memberId, blog.getId());
}
```

- **탈퇴한 회원은 404**: 탈퇴 회원은 이미 쓸 수 없고, 목록에 "알 수 없음"으로 남는 행만 생긴다.
- `insertIfAbsent`가 돌려준 행 수로 "이미 차단"을 안다. `exists` 후 `insert`보다 동시 요청에 안전하다([56](./56-bookmark-snapshot.md) 3.2, [51](./51-subscription-notification.md)).
- 차단과 구독 삭제가 **한 트랜잭션**이다. 차단만 되고 구독은 남는 중간 상태가 생기지 않는다.
- 구독자 수(`subscriberCount`)는 행을 세어 보여 주므로(스텝 16) 따로 고칠 칸이 없다.

### 5.4 금칙어 더하기: 한도와 중복

```java
@Transactional
public BlogBannedWord addBannedWord(Blog blog, String rawWord) {
    String word = rawWord == null ? "" : rawWord.strip();
    if (word.isEmpty() || word.length() > BlogBannedWord.WORD_LENGTH) {
        throw BusinessException.invalidField("word", "금칙어는 1~" + BlogBannedWord.WORD_LENGTH + "자입니다.");
    }
    if (bannedWordRepository.countByBlogId(blog.getId()) >= BlogBannedWord.MAX_PER_BLOG) {
        throw new BusinessException(ErrorCode.BANNED_WORD_LIMIT);
    }
    if (bannedWordRepository.insertIfAbsent(blog.getId(), word) == 0) {
        throw new BusinessException(ErrorCode.NAME_TAKEN);
    }
    …
}
```

- 앞뒤 공백을 지운다. `" 카지노"`와 `"카지노"`가 다른 금칙어가 되면 안 되고, 공백만 있는 금칙어는 모든 글을 막는다(공백 한 칸은 거의 모든 댓글에 들어 있다).
- **한도는 코드에서, 중복은 DB에서** 막는다. 중복은 UNIQUE가 있어 동시 요청에도 정확하다. 한도는 "세고 → 넣기"라 주인이 두 탭에서 동시에 100번째를 넣으면 101개가 될 수 있다. 한 사람이 자기 블로그에 거는 설정이라 이 틈은 받아들였다. 정확히 막으려면 블로그 행을 잠그고(`SELECT … FOR UPDATE`) 세면 된다([23](./23-transactions-locking.md)).

### 5.5 화면

- **댓글 관리에서 바로 차단**(`pages/manage/ManageCommentsPage.tsx`): 받은 댓글마다 작성자 옆 "차단" 버튼. 누르면 "차단할까요? 이 블로그에 댓글·방명록을 쓰거나 구독할 수 없게 되고, 구독 중이면 구독이 지워집니다."로 한 번 묻는다. 회원 번호를 따로 찾을 필요 없이, 광고 댓글을 본 그 자리에서 막는 것이 주인이 실제로 하는 흐름이다(목업 4번).
- **스팸·차단 화면**(`pages/manage/ManageSpamPage.tsx`, `/manage/spam`, 관리 메뉴 "스팸·차단"): 차단한 회원 목록(메모, 차단 시각, "해제")과 금칙어 칩 목록(입력칸, "추가", 칩마다 ×). 서버 오류 코드(`BANNED_WORD_LIMIT`, `NAME_TAKEN`)를 화면 문구로 바꿔 보인다.
- **쓰는 쪽**: 댓글·방명록 입력칸 아래에 서버 메시지("이 블로그에서 차단되었습니다.", "이 블로그에서 쓸 수 없는 단어가 들어 있습니다.")가 그대로 나온다. 구독 버튼도 같다.

### 5.6 테스트: `SpamIntegrationTest`

- `blockedMemberCannotCommentWriteGuestbookOrSubscribe`: 구독한 사람을 차단 → 주인이 아니면 403, 자기 자신 400, 메모와 함께 201, 다시 409 → 구독이 지워졌는지 DB로 → 댓글·방명록·구독 모두 403 `BLOCKED_BY_BLOG` → 목록에 메모 → 해제 뒤 댓글 201.
- `bannedWordsRejectNewCommentsIgnoringCase`: "Casino" 추가 → "casino"는 409 `NAME_TAKEN`(DB 콜레이션) → 공백만은 400 → "CASINO"가 든 댓글과 "casino" 방명록 400 → 금칙어를 지우면 같은 댓글 201.
- `atMostOneHundredBannedWords`: SQL로 100개를 넣고 101번째 409 `BANNED_WORD_LIMIT`. 100번 API를 부르지 않고 SQL로 채워 테스트를 빠르게 한다.

## 6. 자주 하는 실수와 함정

- **검사를 입구마다 복사**: 방명록에만 빠뜨리는 일이 생긴다. 한 클래스에 두고 부른다.
- **검사 순서를 틀림**: 차단 검사가 404보다 먼저면 비공개 글의 존재가 샌다.
- **주소의 블로그로 차단을 봄**: 글이 속한 블로그와 다를 수 있다. 글의 블로그로 본다.
- **차단만 하고 구독은 둠**: 피드에 계속 나온다. 이어진 데이터를 함께 정리한다.
- **`toLowerCase()`를 로케일 없이**: 기본 로케일에 따라 비교가 깨질 수 있다. `Locale.ROOT`.
- **자바에선 대소문자 무시, DB에선 구분(또는 반대)**: "Casino"와 "casino"가 둘 다 들어가거나, 넣을 땐 되는데 검사에선 같은 낱말로 보는 어긋남. 콜레이션을 확인한다.
- **공백 금칙어를 받음**: 모든 댓글이 막힌다. `strip` 후 비면 400.
- **이미 있는 댓글까지 지움**: 명세와 다르고 되돌릴 수 없다.
- **고치기(PATCH)를 잊음**: 깨끗한 댓글을 쓰고 고쳐서 금칙어를 넣을 수 있다. 명세는 "새로 쓸 때"만 정했으므로, 고치기에도 검사할지는 정해야 할 일이다(스텝 20 보고에서 지원에게 물음).

## 7. 직접 해 보기

준비: 갑(블로그 주인), 을(독자). 을이 갑의 블로그를 구독하고 댓글을 하나 쓴다.

1. 갑으로 관리 → 댓글·방명록 → 을의 댓글 옆 "차단" → 확인.
2. 을로 갑의 글에 댓글을 쓰면 "이 블로그에서 차단되었습니다." 구독 피드에서 갑의 글이 사라졌다.
3. DB 확인:

   ```sql
   SELECT * FROM blog_blocked_member;
   SELECT COUNT(*) FROM subscription WHERE member_id = (을 번호) AND blog_id = (갑 블로그 번호);
   ```

4. 갑으로 관리 → 스팸·차단 → 을 "해제". 을이 다시 댓글을 쓸 수 있다.
5. 금칙어 "카지노" 추가 → 을이 "카지노 홍보" 댓글 → 막힘. "Casino"를 넣고 "casino"를 또 넣어 본다.

```bash
./mvnw test -Dtest=SpamIntegrationTest
```

## 8. 확인 문제

1. 서비스 정지와 블로그 차단의 차이를 범위·주체·기록으로 말해 보라.
<details><summary>답</summary>정지는 서비스 관리자가 서비스 전체를 막고 관리 이력에 남긴다. 차단은 블로그 주인이 자기 블로그의 댓글·방명록·구독만 막고, 해제하면 행을 지운다.</details>

2. 차단된 회원도 그 블로그의 공개 글은 읽을 수 있게 둔 이유는?
<details><summary>답</summary>명세가 막는 것은 쓰기와 구독이다. 공개 글은 로그아웃하면 누구나 볼 수 있으므로 읽기를 막아도 효과가 없다.</details>

3. 차단 검사를 "볼 수 있는 글인지(404)" 뒤에 두는 이유는?
<details><summary>답</summary>차단 검사가 먼저면 차단된 사람이 비공개 글 번호로 403(있음)과 404(없음)를 구별해 글의 존재를 알 수 있다.</details>

4. 금칙어 "Casino"가 있을 때 "casino"를 더하면 409 NAME_TAKEN이 나오는 이유는? 자바 코드에 그런 비교가 없는데도.
<details><summary>답</summary>UNIQUE(blog_id, word)를 DB가 검사하고, 이 DB의 콜레이션(utf8mb4_0900_ai_ci)이 대소문자를 무시한다. 그래서 INSERT IGNORE가 0행을 돌려준다.</details>

5. 금칙어 개수 한도와 중복 중 동시 요청에 정확한 것은 어느 것이고, 왜인가?
<details><summary>답</summary>중복이다. DB의 UNIQUE가 막는다. 한도는 "세고 나서 넣기"라 두 요청이 동시에 99개를 보면 101개가 될 수 있다. 정확히 하려면 블로그 행을 잠그고 센다.</details>

6. 차단은 이미 차단이면 409, 해제는 없는 차단이어도 204다. 왜 다르게 했나?
<details><summary>답</summary>해제는 "차단 안 된 상태"가 이미 이뤄져 있으니 멱등하게 성공으로 둔다. 차단은 메모와 함께 하는 관리 작업이라, 이미 차단돼 있고 메모가 덮어써지지 않았다는 사실을 알려 주는 편이 쓸모 있다.</details>

7. 포함 검사의 약점 두 가지는?
<details><summary>답</summary>바꿔 쓴 표현(띄어 쓰기, 비슷한 글자)을 못 잡고, 짧은 금칙어가 다른 낱말 안에 들어 있으면 엉뚱한 댓글도 막는다.</details>

## 9. 더 읽을거리

- MySQL 문서 "Character Sets and Collations"(`utf8mb4_0900_ai_ci`, `_ci`·`_cs`·`_bin`)
- Java `String.toLowerCase(Locale)` 문서와 "Turkish I problem"
- Aho-Corasick 문자열 검색 알고리즘(여러 낱말을 한 번에 찾기)
- RFC 9110 "403 Forbidden", "409 Conflict"
