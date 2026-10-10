# 53. 서비스 관리: 역할로 막기, 시간이 지나면 풀리는 제재, 고치지 않는 이력, 묶어 보는 신고

> 관련 스텝: [스텝 18](../step-18.md) (T094~T096, T109~T112) · 관련 개념: [16 인가와 가시성](./16-authorization-visibility.md), [11 JWT](./11-jwt.md), [27 소프트 삭제와 일괄 수정](./27-soft-delete-bulk-update.md), [51 구독과 알림](./51-subscription-notification.md), [31 태그와 다대다](./31-tags-many-to-many.md), [08 페이지 처리](./08-pagination.md), [19 React Router와 API 클라이언트](./19-react-router-api-client.md)

## 1. 이 문서로 배우는 것

- **역할 기반 접근 제어**: `/api/admin/**`을 주소 한 줄로 관리자만 통과시키는 방법과, 401·403이 갈리는 지점
- **시간이 지나면 풀리는 상태**: 정지 기간이 끝났을 때 "누가 풀어 주나"를 배치 작업 없이 푸는 방법(읽을 때 판단)
- **고치지 않는 이력(감사 로그)**: 관리 이력을 INSERT만 하고, 제재 사유를 대상 행이 아니라 이력의 최신 줄에서 읽는 이유
- **"숨기기만 하고 지우지 않는" 제재**와, 관리자가 바꿔도 작성자의 "수정 시각"이 바뀌지 않게 하는 UPDATE
- **신고를 대상별로 묶어 보기**: `GROUP BY`와 페이지, 묶음 수를 세는 쿼리, 인터페이스 프로젝션
- **한 번만 받는 신고**: UNIQUE 제약과 `INSERT IGNORE`의 넣은 행 수
- 화면: 관리 영역 안의 하위 주소(중첩 라우트), 검색 조건을 주소에 두기

## 2. 왜 필요한가

글을 쓰고 읽는 서비스는 언젠가 스팸, 음란물, 욕설, 남의 사진을 만난다. 운영자가 할 수 있는 일이 "DB에 들어가 직접 지우기"뿐이면 세 가지가 무너진다.

1. **누가 했는지 모른다.** 어느 관리자가 언제 왜 지웠는지 남지 않으면, 잘못된 조치를 되돌리거나 항의에 답할 수 없다.
2. **되돌릴 수 없다.** 지운 글은 돌아오지 않는다. 신고가 틀렸어도 복구할 길이 없다.
3. **당사자가 모른다.** 자기 글이 왜 사라졌는지 모르는 작성자는 같은 일을 반복하거나 떠난다.

이 프로젝트의 헌법 원칙 V가 이것을 막는다. "관리자는 남의 내용을 고치거나 지우지 않고 **숨기거나 제한만** 하며, 모든 제재에는 **사유**를 남긴다." 스텝 18은 이 원칙을 기능으로 만든다. 관리자만 들어가는 영역, 정해진 사유, 고치지 않는 이력, 당사자에게 가는 알림, 독자의 신고가 그 기능이다.

## 3. 기본 개념

### 3.1 역할 기반 접근 제어 (RBAC)

사람마다 권한을 따로 적지 않고 **역할**(role)에 권한을 붙인 뒤 사람에게 역할을 준다. 이 프로젝트의 역할은 둘뿐이다. 일반 회원(`USER`)과 서비스 관리자(`ADMIN`)다(spec 권한 절). "블로그 주인"은 역할이 아니라 요청마다 판단하는 관계다([16](./16-authorization-visibility.md)).

| 묻는 것 | 판단하는 곳 | 실패하면 |
| --- | --- | --- |
| 로그인했나 | 인증 필터(쿠키의 토큰) | 401 |
| 관리자인가 | 주소 규칙 `hasRole("ADMIN")` | 403 |
| 이 블로그의 주인인가 | 서비스 코드(`BlogOwnerGuard`) | 403 |

Spring Security에서 `hasRole("ADMIN")`은 사용자의 권한 목록에 `ROLE_ADMIN`이 있는지 본다. `ROLE_` 앞붙이는 `hasRole`이 알아서 붙인다.

### 3.2 시간이 지나면 풀리는 상태

"7일 정지"는 7일 뒤 누군가 풀어 줘야 하는 것처럼 보인다. 방법은 두 가지다.

| 방법 | 어떻게 | 장점 | 단점 |
| --- | --- | --- | --- |
| 정해진 때 풀기(배치) | 1분마다 "기간이 지난 정지"를 찾아 ACTIVE로 바꾼다 | DB의 상태가 늘 맞다 | 최대 1분 늦다. 작업이 멈추면 아무도 안 풀린다 |
| 읽을 때 판단(lazy) | 정지 종료 시각만 저장하고, 쓸 때마다 "지금 < 종료 시각"인지 본다 | 정확히 그 순간 풀린다. 작업이 없다 | DB의 `status` 칸만 보면 틀릴 수 있다(기간이 지났는데 SUSPENDED) |

이 프로젝트는 둘째다. 스텝 4부터 `Member.isSuspendedAt(now)`가 그렇게 판단하고 있었다. 대신 "DB의 칸만 보는 곳"을 만들지 않도록 조심해야 한다. 관리자 회원 목록의 상태 필터가 그런 곳이다(5.3).

[52](./52-scheduled-jobs-proxy.md)의 예약 발행은 왜 첫째(배치)였나? 예약 글은 시각이 되면 **다른 사람들의 목록에 나타나야** 해서, 목록 쿼리마다 "예약 시각이 지난 예약 글도 발행 글로 친다"를 넣기보다 상태를 바꾸는 쪽이 단순했다. 정지는 판단하는 곳이 "이 회원인가"를 보는 몇 군데(인증 필터, 블로그 가시성)뿐이라 읽을 때 판단이 단순하다.

### 3.3 감사 이력(audit log)은 INSERT만

감사 이력은 "누가, 언제, 무엇을, 왜"를 남긴 기록이다. 고칠 수 있으면 기록이 아니다. 그래서:

- **INSERT만** 한다. 수정·삭제 API가 없다(contracts ADMIN-06 "조회만").
- 해제도 지우기가 아니라 **해제 줄을 하나 더** 넣는다(`SUSPEND` 다음에 `UNSUSPEND`).
- 대상 테이블에는 "지금 상태"(숨김 여부, 정지 종료 시각)만 두고, **사유는 이력의 최신 제재 줄**에서 읽는다(ERD 주석 "제재 사유의 유일한 저장 위치").

사유를 대상 행(`post.blind_reason`)에도 두면 같은 사실이 두 곳에 있게 되고, 언젠가 둘이 달라진다. 이력에만 두면 "지금 사유"는 "가장 최근의 BLIND 줄"로 정해진다.

### 3.4 숨기기는 상태 하나, 지우기는 아님

숨긴 글은 `is_blinded = 1`일 뿐 그대로 있다. 보이느냐는 가시성 판단([16](./16-authorization-visibility.md))이 정한다. 남에게는 404이고, 작성자에게는 사유와 함께 보이며, 작성자는 수정할 수 없지만 지울 수는 있다. 스텝 3부터 이 판단은 있었고, 스텝 18은 그 칸을 바꾸는 **입구**를 만든다.

### 3.5 GROUP BY와 페이지

신고 100건이 같은 글 하나에 몰리면 관리자는 100줄이 아니라 "이 글, 신고 100" 한 줄을 봐야 한다. SQL로는 `GROUP BY target_type, target_id`이고, 정렬은 `COUNT(*) DESC`다.

페이지를 나누려면 "전체 몇 묶음인가"도 세야 한다. `SELECT COUNT(*) ... GROUP BY`는 묶음마다 한 줄씩 돌려줘서 전체 수가 아니다. 묶음 수는 `COUNT(DISTINCT 묶는 칸)`으로 센다.

### 3.6 한 번만 받기: UNIQUE + `INSERT IGNORE`

한 회원이 같은 글을 백 번 신고하면 신고 수가 부풀려진다. `report` 테이블의 `UNIQUE (reporter_id, target_type, target_id)`가 막는다. "이미 있나 보고 넣기"는 동시에 두 번 누르면 둘 다 "없다"를 보고 넣다가 늦은 쪽이 UNIQUE 위반 500이 된다. 그래서 공감·구독·태그처럼 `INSERT IGNORE`로 넣고 **넣은 행 수**(0이면 이미 있음)로 409를 정한다([51](./51-subscription-notification.md) 3.2).

## 4. 동작 원리

**관리자 요청 하나가 거치는 길** (글 숨기기):

```
브라우저 POST /api/admin/posts/26/blind {reason: "COPYRIGHT"}
  │ (1) CsrfHeaderFilter: X-Requested-With 있나          없으면 403 CSRF_REJECTED
  │ (2) JwtAuthenticationFilter: 쿠키 → 회원 → DB에서 읽기  탈퇴면 비회원, 정지면 403 MEMBER_SUSPENDED
  │      LoginMember(id, role=ADMIN)을 SecurityContext에
  │ (3) authorizeHttpRequests: /api/admin/** hasRole(ADMIN)  비회원 401, 일반 회원 403
  ▼
AdminController.blindPost
  │ moderationService.post(26)          없거나 지운 글 404   ← 상태 코드 순서 404 → 400
  │ Sanction.of("COPYRIGHT", null)      목록 밖 사유 400, 기타인데 설명 없음 400
  ▼
ModerationService.blindPost  (한 트랜잭션)
  ├ UPDATE post SET is_blinded=1, updated_at=updated_at WHERE id=26
  ├ INSERT moderation_log (admin, BLIND, POST, 26, COPYRIGHT)
  └ INSERT notification (작성자, SANCTION, POST 26, "...숨김 처리되었습니다.")
  ▼
204
```

- (2)에서 역할을 **토큰이 아니라 DB에서 읽은 회원**에서 꺼낸다. 토큰 안의 역할을 믿으면, 역할이 바뀌어도 토큰이 끝날 때까지 옛 역할이 통한다.
- (3)이 컨트롤러보다 먼저라, 일반 회원은 없는 글 번호를 보내도 404가 아니라 403이다. "관리자 영역이 있는지"는 숨길 것이 아니라서 괜찮다.
- 조치·이력·알림이 한 트랜잭션이라, 알림 저장이 실패하면 숨김도 되돌아간다. 셋 중 하나만 남는 일이 없다.

**정지된 회원의 다음 요청**:

```
정지된 갑의 브라우저 GET /api/me (쿠키는 그대로)
  JwtAuthenticationFilter: member.isSuspendedAt(지금)? → 예
    → 쿠키 지우기 + 403 MEMBER_SUSPENDED {reason, reasonMessage, suspendedUntil}
```

토큰은 서버가 기억하지 않는 증표(stateless, [11](./11-jwt.md))라서, 정지해도 이미 나간 토큰을 "취소"할 방법이 없다. 이 프로젝트는 요청마다 회원을 DB에서 읽어 상태를 보므로, 정지한 바로 다음 요청부터 막힌다(spec US9 3번). 요청마다 SELECT 한 번이 드는 대신 얻는 것이다.

## 5. 이 프로젝트에서는

### 5.1 주소 한 줄로 관리자만: `global/config/SecurityConfig`

```java
.authorizeHttpRequests(auth -> auth
        .requestMatchers("/api/admin/**").hasRole("ADMIN")
        .anyRequest().permitAll())
.exceptionHandling(exceptions -> exceptions
        .authenticationEntryPoint((request, response, e) ->
                errorResponseWriter.write(response, ErrorCode.UNAUTHORIZED))
        .accessDeniedHandler((request, response, e) ->
                errorResponseWriter.write(response, ErrorCode.FORBIDDEN)))
```

- 스텝 4(T051)에서 만들어 둔 규칙이다. 스텝 18은 그 아래에 API를 채웠을 뿐 이 줄을 건드리지 않았다. `/api/admin/`으로 시작하는 주소를 만들면 **자동으로** 관리자 전용이 된다.
- 비회원이 오면 `authenticationEntryPoint`(401), 로그인했지만 역할이 없으면 `accessDeniedHandler`(403)다. 둘 다 우리 오류 본문(JSON)으로 쓴다.
- 반대로 공지 읽기(`GET /api/notices`)는 `/api/admin/` 밖이라 누구나다. 같은 `NoticeController` 안에 읽기(`/api/notices`)와 쓰기(`/api/admin/notices`)가 있어도 **주소**가 권한을 가른다.
- Thymeleaf로 만든 관리 화면이었다면 `/admin/**` 화면 주소에 같은 규칙을 걸었을 것이다. 여기서는 화면이 React라 화면 주소의 검사(`AdminPage`의 403 안내)는 안내용이고, 진짜 문은 API 주소다(헌법 원칙 IV).

### 5.2 사유 고르기: `admin/application/Sanction`

```java
public record Sanction(SanctionReason reason, String reasonDetail) {

    public static Sanction of(String reason, String reasonDetail) {
        SanctionReason parsed = parseReason("reason", reason);
        String detail = reasonDetail == null || reasonDetail.isBlank() ? null : reasonDetail.strip();
        if (parsed == SanctionReason.ETC && detail == null) {
            throw BusinessException.invalidField("reasonDetail", "기타를 고르면 설명을 써 주세요.");
        }
        if (detail != null && detail.length() > DETAIL_LENGTH) {
            throw BusinessException.invalidField("reasonDetail", "설명은 " + DETAIL_LENGTH + "자까지입니다.");
        }
        return new Sanction(parsed, detail);
    }
```

- 관리자는 사유를 **직접 쓰지 않고 목록에서 고른다**(2026-10-08 지원 결정). 자유 글이면 "스팸", "광고", "spam"이 섞여 이력을 검색·집계할 수 없고, 받는 사람에게 보일 안내 문구도 정할 수 없다.
- 목록은 enum `SanctionReason`이고, 안내 문구도 enum 필드에 있다(DB가 아니라 코드에, ERD 주석). 문구를 바꾸려면 배포가 필요하지만, 다섯 개뿐이고 자주 바뀌지 않는다.
- 기타(`ETC`)만 설명이 필수다. DB에도 같은 규칙이 CHECK 제약으로 있다(`ck_moderation_log_etc_detail`). 자바에서 먼저 400으로 막고, DB는 마지막 방어선이다.
- 요청 DTO(`SanctionRequest`)에는 문자열로 받고 여기서 enum으로 바꾼다. DTO에 enum을 바로 두면, 목록 밖 값이 왔을 때 JSON을 읽는 단계에서 터져 "어느 칸이 틀렸는지"를 알려 주기 어렵다.

### 5.3 정지와 "지금 기준" 상태: `ModerationService.suspend`, `AdminMemberService`

```java
// Member
public void suspend(LocalDateTime until) {       // until이 null이면 영구
    this.status = MemberStatus.SUSPENDED;
    this.suspendedUntil = until;
}

public boolean isSuspendedAt(LocalDateTime now) { // 스텝 4부터 있던 판단
    return status == MemberStatus.SUSPENDED && (suspendedUntil == null || suspendedUntil.isAfter(now));
}
```

```java
// SuspensionPeriod: 요청 값 7D, 30D, PERMANENT
public LocalDateTime until(LocalDateTime now) {
    return this == PERMANENT ? null : now.plusDays(days);
}
```

- "기간이 끝나면 자동으로 풀린다"(spec ADMIN-02)는 `isSuspendedAt`이 지금과 종료 시각을 비교해서 이뤄진다. 따로 풀어 주는 작업이 없다(3.2).
- 종료 시각이 null인 것을 "영구"로 쓴다(ERD 주석 "SUSPENDED + NULL = 영구 정지"). 칸 하나로 두 뜻을 담는 대신, 해석을 `isSuspendedAt` 한 곳에 모았다.

그런데 관리자 회원 목록의 "정지" 필터는 DB 쿼리다. `status = 'SUSPENDED'`만 보면 기간이 지난 회원까지 나온다. 그래서 필터도 같은 판단을 SQL로 옮겼다.

```java
case "SUSPENDED" -> (root, query, cb) -> cb.and(
        cb.equal(root.get("status"), MemberStatus.SUSPENDED),
        cb.or(cb.isNull(root.get("suspendedUntil")), cb.greaterThan(root.get("suspendedUntil"), now)));
case "ACTIVE" -> (root, query, cb) -> cb.or(
        cb.equal(root.get("status"), MemberStatus.ACTIVE),
        cb.and(cb.equal(root.get("status"), MemberStatus.SUSPENDED),
                cb.lessThanOrEqualTo(root.get("suspendedUntil"), now)));
```

- "활동" 필터는 ACTIVE에 **기간이 지난 SUSPENDED**를 더한다. 목록의 상태 글자도 `effectiveStatus`로 같은 판단을 한다.
- 읽을 때 판단하는 방식의 비용이 이것이다. DB 칸만 보는 곳마다 같은 판단을 다시 써야 한다. 그런 곳이 늘면 배치(3.2의 첫째)로 바꾸는 것을 생각한다.
- 해제(`unsuspend`)는 정지 중이 아니면 이력·알림 없이 상태만 정리한다. 기간이 지나 이미 풀린 회원에게 "해제되었습니다" 알림이 가면 이상하다.
- 관리자는 정지할 수 없다(400 `member`). 관리자끼리 서로 막아 서비스를 운영할 수 없게 되는 일을 막는다.

### 5.4 조치 = 상태 + 이력 + 알림: `admin/application/ModerationService`

```java
@Transactional
public void blindPost(Long adminId, Long postId, Sanction sanction) {
    Post post = post(postId);
    Long ownerId = post.getBlog().getMember().getId();
    String title = post.getTitle();
    postRepository.changeBlinded(postId, true);
    record(adminId, ModerationAction.BLIND, ModerationTargetType.POST, postId, sanction);
    notificationService.sanctioned(ownerId, NotificationTargetType.POST, postId,
            "\"" + shorten(title) + "\" 글이 운영 정책 위반(" + sanction.label() + ")으로 숨김 처리되었습니다.");
}
```

- 조치 여섯 가지(정지·해제, 글 숨김·해제, 댓글 숨김·해제, 블로그 제한·해제)가 모두 이 모양이다. **상태 바꾸기 → 이력 INSERT → 알림 INSERT**가 한 트랜잭션이다.
- 알림은 [51](./51-subscription-notification.md)의 `NotificationService`에 `sanctioned`를 더해 보낸다. 댓글·공감 알림과 달리 "내가 한 일은 알리지 않는다" 검사가 없다. 관리자가 한 일을 당사자에게 알리는 것이라서다.
- `ownerId`와 `title`을 **UPDATE 전에** 꺼내 둔다. 다음 절의 UPDATE가 영속성 컨텍스트를 비워서(`clearAutomatically`), 그 뒤에 `post.getBlog().getMember()`를 지연 로딩하면 `LazyInitializationException`이 날 수 있다.
- `record`의 관리자는 `memberRepository.getReferenceById(adminId)`다. 관리자 회원을 SELECT하지 않고 "이 번호의 회원"이라는 참조만 만들어 외래 키에 넣는다.

### 5.5 수정 시각을 건드리지 않는 숨김

처음에는 엔티티에 `post.changeBlinded(true)`를 두고 불렀다. 브라우저로 확인하다가, 숨김을 해제한 글 머리에 **"수정 2026.10.11 04:42"**가 붙은 것을 봤다. 작성자는 아무것도 고치지 않았는데 고친 글처럼 보였다.

원인은 두 겹이다.

1. 엔티티를 고치면 JPA 변경 감지가 UPDATE를 만들고, `@LastModifiedDate`(Spring Data 감사 기능)가 `updatedAt`을 지금으로 바꾼다.
2. 그것이 아니어도 `updated_at` 칸은 DB에서 `ON UPDATE CURRENT_TIMESTAMP(6)`다. 행의 다른 칸이 바뀌면 MySQL이 이 칸을 지금으로 바꾼다.

그래서 엔티티 대신 UPDATE 한 문장으로 바꿨다.

```java
// PostRepository
@Modifying(clearAutomatically = true, flushAutomatically = true)
@Query("update Post p set p.blinded = :blinded, p.updatedAt = p.updatedAt where p.id = :id")
int changeBlinded(@Param("id") Long id, @Param("blinded") boolean blinded);
```

- JPQL 일괄 UPDATE는 엔티티 리스너를 거치지 않아 1번이 일어나지 않는다.
- `p.updatedAt = p.updatedAt`이 2번을 막는다. MySQL은 같은 UPDATE에서 그 칸에 **직접 값을 넣으면**(지금 값 그대로라도) 자동 갱신을 하지 않는다. 글 삭제 때 댓글을 일괄 소프트 삭제하는 쿼리([27](./27-soft-delete-bulk-update.md))와 같은 방법이다.
- `flushAutomatically`: 같은 트랜잭션에서 JPA로 바꾼 것이 있으면 먼저 DB로 보낸다. `clearAutomatically`: 일괄 UPDATE는 영속성 컨텍스트를 모르고 DB만 바꾸므로, 컨텍스트에 남은 옛 `Post`(`blinded = false`)를 비워 다시 읽게 한다.
- 댓글(`CommentRepository.changeBlinded`)도 같다. 댓글에는 "수정됨" 표시가 있다.
- 블로그 제한(`Blog.changeRestricted`)과 회원 정지(`Member.suspend`)는 엔티티를 고친다. 둘의 `updated_at`은 화면에 "수정 시각"으로 보이는 곳이 없다.
- 테스트(`blindedPostIsNotFoundForOthersAndShowsReasonToAuthor`)가 숨김·해제 전후의 `updated_at`이 같은지 DB에서 본다.

### 5.6 사유는 이력의 최신 줄에서: 읽는 쪽

```java
// SuspensionDetails (스텝 13), CommentViews (스텝 14)
moderationLogRepository
        .findFirstByTargetTypeAndTargetIdAndActionOrderByCreatedAtDescIdDesc(
                ModerationTargetType.MEMBER, member.getId(), ModerationAction.SUSPEND)
        .map(ModerationLog::getReason)
```

- 정지 안내, 숨긴 글·댓글의 사유, 제한된 블로그의 사유를 보여 주는 쪽은 스텝 13~14에 이미 있었다. 그때는 이력을 만드는 API가 없어서 테스트가 SQL로 이력을 넣었다. 스텝 18이 그 이력을 만드는 쪽이다.
- `OrderByCreatedAtDescIdDesc`: 같은 밀리초에 두 줄이 생겨도 번호가 큰(나중) 줄이 이긴다.

### 5.7 신고 받기: `admin/application/ReportService`

```java
Long viewerId = member == null ? null : member.id();
requireVisible(targetType, targetId, viewerId);      // 볼 수 없는 대상 404
if (member == null) {
    throw new BusinessException(ErrorCode.UNAUTHORIZED);  // 비회원 401
}
SanctionReason reason = Sanction.parseReason("reason", rawReason);
...
int inserted = reportRepository.insertIfAbsent(member.id(), targetType.name(), targetId, reason.name(),
        description);
if (inserted == 0) {
    throw new BusinessException(ErrorCode.ALREADY_REPORTED);   // 같은 대상 다시 409
}
```

- 상태 코드 순서(404 → 401 → 403 → 400 → 409, contracts)를 지키려고 **대상 확인을 로그인 확인보다 먼저** 한다. 비회원에게도 "없는 글"은 404다.
- "볼 수 있나"는 글 상세·블로그 화면과 같은 판단(`PostVisibilityPolicy`, `BlogVisibilityPolicy`)을 쓴다. 비공개 글, 내가 볼 수 없는 비밀댓글, 이미 숨긴 댓글은 404다. 볼 수 없는 것을 신고하게 두면 "이 번호에 무언가 있다"가 새어 나간다(헌법 원칙 II).
- UNIQUE가 회원·대상마다 하나라, 처리가 끝난 뒤에도 같은 대상을 다시 신고할 수 없다. 숨김이 풀린 뒤 다시 문제가 되면 다른 회원의 신고를 받거나 관리자가 직접 숨긴다.

### 5.8 대상별로 묶기: `ReportRepository.findPendingTargets`

```java
@Query(value = """
        select r.targetType as targetType, r.targetId as targetId, count(r) as reportCount,
               min(r.createdAt) as firstReportedAt
        from Report r where r.status = com.nhnacademy.blog.admin.domain.ReportStatus.PENDING
        group by r.targetType, r.targetId
        order by count(r) desc, min(r.createdAt) asc""",
        countQuery = """
        select count(distinct concat(r.targetType, ':', r.targetId)) from Report r
        where r.status = com.nhnacademy.blog.admin.domain.ReportStatus.PENDING""")
Page<PendingTarget> findPendingTargets(Pageable pageable);

interface PendingTarget {
    ReportTargetType getTargetType();
    Long getTargetId();
    Long getReportCount();
    LocalDateTime getFirstReportedAt();
}
```

- 결과가 엔티티가 아니라 묶음 한 줄이라 **인터페이스 프로젝션**으로 받는다. `select ... as targetType`의 별칭과 `getTargetType()`의 이름이 맞으면 Spring Data가 구현을 만들어 준다. 클래스를 따로 만들지 않아도 된다.
- `countQuery`: Spring Data는 `Page`를 만들려고 전체 개수 쿼리를 따로 보낸다. 묶은 쿼리에서 자동으로 만든 개수 쿼리는 묶음 수가 아니므로 직접 준다. 두 칸(종류, 번호)의 서로 다른 조합 수를 세려고 `concat(종류, ':', 번호)`를 `count(distinct …)`했다.
- 정렬은 신고 수가 많은 순, 같으면 먼저 신고된 순(spec US14 2번). 오래 기다린 신고가 뒤로 밀리지 않게 둘째 기준을 뒀다.
- 묶음마다 사유별 수(`{ COPYRIGHT: 6, ETC: 1 }`)와 대상 이름은 서비스가 따로 읽는다. 한 쪽에 20묶음이라 쿼리가 몇십 개 더 나가지만, 관리자 화면이라 받아들였다.

### 5.9 처리: 결과 하나, 대기 신고 모두 완료

```java
switch (result) {
    case BLIND -> ...            // 글·댓글 숨김. 블로그는 400
    case RESTRICT_BLOG -> ...    // 블로그, 또는 글이 속한 블로그. 댓글은 400
    case SUSPEND -> ...          // 글·블로그 주인, 댓글 작성자를 정지(period 필수)
    case REJECT -> moderationService.rejectReport(adminId, type.toModerationTarget(), targetId);
}
reportRepository.resolveAll(type, targetId, result, LocalDateTime.now(clock));
```

- 신고 처리는 새 조치를 만들지 않고 5.4의 조치를 **그대로 부른다**. 그래서 신고로 숨겨도, 글 상세의 관리자 버튼으로 숨겨도 이력·알림이 같다.
- `resolveAll`은 그 대상의 **대기 신고를 모두** 처리 완료로 바꾸는 UPDATE 한 문장이다(spec US14 3번). 같은 트랜잭션이라, 조치가 실패(예: 대상이 지워져 404)하면 신고도 대기로 남는다.
- 기각(`REJECT`)의 이력은 대상 종류를 `REPORT`가 아니라 **신고된 대상 그대로**(글 26) 적는다. "글 26에 무슨 일이 있었나"를 이력에서 대상으로 검색하면 숨김·해제·기각이 한 번에 나온다(목업은 `REPORT`로 그렸는데, 검색이 쉬운 쪽으로 정해 API 명세에 적었다).
- 댓글 신고에 "블로그 이용 제한"을 막은 이유: 댓글의 블로그(그 글이 있는 블로그)는 피해자 쪽이고, 댓글 작성자의 블로그는 하나로 정할 수 없다.

### 5.10 대상 한 줄: `ModerationTargets`

관리 이력에는 "POST 26"만 있다. 화면에는 "글 · 댓글 막은 글"처럼 이름과 링크가 필요하다. `ModerationTargets.of(type, id)`가 지금 대상을 읽어 `{ label, blogAddress, postId, exists, sanctioned }`를 만든다. 신고 목록, 관리 이력, 대시보드, 회원 상세가 같이 쓴다.

- 관리자 화면이라 숨김·비공개와 상관없이 이름을 보여 준다. 남에게 보이는 화면이 아니라서 가시성 판단을 거치지 않는다.
- `sanctioned`(지금 숨김·제한·정지 중)는 화면이 "해제" 버튼을 둘지 정하는 데 쓴다(5.12).

### 5.11 대시보드와 이력 검색

- 오늘 가입·오늘 새 글은 "한국 시간 0시부터"다(`LocalDate.now(clock).atStartOfDay()`, 서버 시간대는 Asia/Seoul).
- "처리 대기 신고"는 신고 **건수**가 아니라 처리할 **대상** 수다. 관리자가 할 일의 수는 묶음 수라서다. 목업의 숫자와 다를 수 있어 API 명세에 적었다.
- 이력 검색은 `Specification`을 조건마다 하나씩 붙인다(대상 종류, 번호, 관리자, 시작·끝 날짜). 끝 날짜는 "그날 끝까지"라 `< 다음 날 0시`로 비교한다. `<= 그날 23:59:59`로 쓰면 59.5초에 생긴 줄을 놓친다.

### 5.12 화면

**중첩 라우트**. `/admin/*` 아래에 대시보드·회원·신고·이력이 있다. `AdminPage`가 틀(머리글, 왼쪽 메뉴)을 그리고, 그 안의 `<Routes>`가 하위 주소마다 본문을 바꾼다.

```tsx
<div className="manage">
  <nav className="manage-nav" aria-label="서비스 관리 메뉴">
    <NavLink to="/admin" end>대시보드</NavLink>
    <NavLink to="/admin/members">회원</NavLink>
    ...
  </nav>
  <Routes>
    <Route index element={<AdminDashboardPage />} />
    <Route path="members" element={<AdminMembersPage />} />
    ...
  </Routes>
</div>
```

Thymeleaf로 치면 레이아웃 템플릿 하나(`layout:decorate`)에 본문 조각(`layout:fragment="content"`)만 갈아 끼우는 것이다. 관리자 검사(403 안내)도 틀에서 한 번만 한다.

**검색 조건은 주소에**. 회원 화면은 `?q=&status=&page=&id=`, 이력 화면은 `?targetType=&targetId=&adminId=&from=&to=`다. `useSearchParams`로 읽고 쓴다. 새로고침해도, 링크로 보내도 같은 화면이다. Thymeleaf에서 `@RequestParam`으로 받아 다시 폼에 채우던 것과 같은 효과이고, 상태가 컴포넌트 안이 아니라 주소에 있다.

**입구**(feature-needs-visible-entry):

| 기능 | 입구 |
| --- | --- |
| 서비스 관리 | 플랫폼 머리글 "서비스 관리"(관리자에게만) |
| 글·댓글 숨기기 | 글 상세의 "숨기기 (관리자)", 댓글마다 "숨기기 (관리자)" |
| 숨김·제한·정지 해제 | 관리 이력·회원 상세 표의 "해제"(그 대상의 가장 최근 줄, 지금 조치 중일 때만) |
| 블로그 이용 제한 | 회원 상세의 보유 블로그 줄 "이용 제한" |
| 신고 | 글 상세 공유 옆 "신고", 댓글마다 "신고", 블로그 프로필 상자 "신고" |
| 공지 | 홈 상단 띠, 머리글 "공지", 관리 이력·공지 화면의 쓰기·수정·삭제 |

"해제" 버튼은 처음에 빠져 있었다. 글을 숨긴 뒤 "해제는 회원 상세·관리 이력에서"라고 안내했는데 두 곳 모두 버튼이 없었다. 브라우저 확인 계획을 쓰다 발견해 `LogTable`에 더했다. 어느 API를 부를지는 순수 함수 `releasePath`(`app/admin.ts`)가 정하고 단위 테스트가 있다.

## 6. 자주 하는 실수와 함정

- **역할을 토큰 안의 값만 믿는다.** 역할이 바뀌거나 정지돼도 토큰이 끝날 때까지 통한다. 요청마다 DB에서 상태를 보거나, 토큰을 짧게 하고 갱신 때 확인한다.
- **화면에서만 관리자 메뉴를 숨긴다.** API를 직접 부르면 그만이다. 서버 주소 규칙이 진짜 문이다.
- **기간 제재를 DB 칸만 보고 판단하는 곳을 만든다.** 읽을 때 판단하는 방식이면 모든 곳이 같은 판단(지금 < 종료 시각)을 써야 한다.
- **이력을 고칠 수 있게 만든다.** 감사 이력은 INSERT만. 해제도 줄을 하나 더 넣는다.
- **사유를 대상 행과 이력 두 곳에 둔다.** 언젠가 달라진다. 한 곳(최신 이력 줄)에서 읽는다.
- **관리자 조치로 작성자의 수정 시각을 바꾼다.** 변경 감지·`@LastModifiedDate`·DB `ON UPDATE` 세 겹을 다 피해야 한다(5.5).
- **일괄 UPDATE 뒤에 지연 로딩한다.** `clearAutomatically`가 컨텍스트를 비워 `LazyInitializationException`이 난다. 필요한 값을 먼저 꺼낸다.
- **묶은 쿼리에 자동 개수 쿼리를 쓴다.** 묶음 수가 아니라 엉뚱한 값이 나온다. `countQuery`를 직접 준다.
- **"있나 보고 넣기"로 중복을 막는다.** 동시에 두 번 오면 500. UNIQUE + `INSERT IGNORE`.
- **볼 수 없는 대상도 신고를 받는다.** "이 번호에 무언가 있다"가 새어 나간다. 같은 가시성 판단을 쓴다.
- **끝 날짜를 `<= 23:59:59`로 비교한다.** 밀리초를 놓친다. `< 다음 날 0시`.

## 7. 직접 해 보기

### 7.1 화면 (관리자: `admin@blog.test` / `admin1234!`)

1. 다른 회원으로 남의 글을 열고 공유 옆 "신고" → "저작권 침해" → 신고. 다시 열어 신고하면 "이미 신고한 글입니다."
2. 관리자로 `http://blog.test:8080/admin` → "처리 대기 신고" 수. "신고"에서 그 글 줄의 "처리" → 블라인드 → 처리.
3. 신고한 회원으로 그 글 주소 → 404. 글쓴이로 열면 "관리자가 숨긴 글입니다 사유: 저작권 침해", 알림에 숨김 알림.
4. 관리자 "회원"에서 글쓴이 닉네임 검색 → 상세 → 7일·스팸·광고 → 정지. 글쓴이가 아무 화면이나 새로고침하면 정지 안내, 다른 사람에게 그 블로그는 404.
5. 상세의 제재 이력에서 정지 줄의 "해제" → 블로그가 다시 보인다.
6. "관리 이력·공지"에서 공지를 쓰고 홈(`http://blog.test:8080/`) 상단 띠를 본다.

### 7.2 상태 코드 순서

```bash
# 쿠키는 브라우저 개발자 도구에서 복사하거나 curl -c로 로그인해 받는다
curl -s -o /dev/null -w '%{http_code}\n' -H 'X-Requested-With: XMLHttpRequest' http://blog.test:8080/api/admin/dashboard   # 401
curl -s -o /dev/null -w '%{http_code}\n' -b user.jar -H 'X-Requested-With: XMLHttpRequest' http://blog.test:8080/api/admin/dashboard   # 403
curl -s -X POST -b user.jar -H 'X-Requested-With: XMLHttpRequest' -H 'Content-Type: application/json' \
  http://blog.test:8080/api/reports -d '{"targetType":"POST","targetId":999999,"reason":"SPAM"}'   # 404 (없는 글)
```

### 7.3 DB에서

```sql
SELECT id, action, target_type, target_id, reason, created_at FROM moderation_log ORDER BY id DESC LIMIT 10;
SELECT target_type, target_id, COUNT(*) FROM report WHERE status = 'PENDING' GROUP BY target_type, target_id ORDER BY 3 DESC;
-- 7일 정지한 회원을 "기간이 끝난" 상태로 만들어 보기: 새로고침하면 바로 풀린다(풀어 주는 작업 없이)
UPDATE member SET suspended_until = NOW() - INTERVAL 1 MINUTE WHERE id = {회원 번호};
```

### 7.4 수정 시각 실험

연습 브랜치에서 `PostRepository.changeBlinded`의 `p.updatedAt = p.updatedAt`을 지우고 `AdminIntegrationTest#blindedPostIsNotFoundForOthersAndShowsReasonToAuthor`를 돌려 본다. 엔티티 리스너는 거치지 않는데도, DB의 `ON UPDATE CURRENT_TIMESTAMP(6)` 때문에 `updated_at`이 바뀌어 실패해야 한다.

### 7.5 테스트

```bash
./mvnw test -Dtest='AdminIntegrationTest,AccessControlIntegrationTest'
cd frontend && npx vitest run src/app/admin.test.ts
```

## 8. 확인 문제

1. `/api/admin/**`에 일반 회원이 없는 글 번호로 숨기기를 보내면 404가 아니라 403이다. 왜 그런가, 그리고 왜 괜찮은가?
<details><summary>답</summary>주소 규칙(hasRole)이 컨트롤러보다 먼저 검사해서 글을 찾기 전에 403이 된다. 감출 것은 "그 글이 있나"인데, 관리자가 아닌 사람은 어떤 글 번호를 보내도 똑같이 403이라 글이 있는지 알 수 없다. 관리자 영역이 있다는 사실은 숨길 정보가 아니다.</details>

2. 7일 정지가 끝났을 때 아무 작업도 돌지 않는데 어떻게 풀리나? 그 방식 때문에 조심해야 하는 곳은?
<details><summary>답</summary>정지 종료 시각만 저장하고, 쓸 때마다 isSuspendedAt(지금)으로 "지금이 종료 시각 전인가"를 본다. 시각이 지나면 판단 결과가 저절로 false가 된다. DB의 status 칸만 보는 쿼리(관리자 회원 목록의 상태 필터)는 기간이 지난 SUSPENDED를 정지로 잘못 셀 수 있어서, 같은 비교를 SQL에도 넣어야 한다.</details>

3. 제재 사유를 `post` 행에 두지 않고 관리 이력의 최신 BLIND 줄에서 읽는 이유는?
<details><summary>답</summary>같은 사실을 두 곳에 두면 언젠가 달라진다. 이력은 어차피 남겨야 하고 고치지 않으므로, "지금 사유 = 가장 최근 제재 줄"로 한 곳에서 정하는 것이 안전하다. 대상 행에는 지금 상태(is_blinded)만 둔다.</details>

4. 관리자가 글을 숨겼다 풀었는데 글 머리에 "수정 …"이 붙었다. 원인 두 가지와 막는 방법은?
<details><summary>답</summary>엔티티를 고치면 변경 감지 UPDATE에 @LastModifiedDate가 updatedAt을 지금으로 넣는다. 또 updated_at 칸이 DB에서 ON UPDATE CURRENT_TIMESTAMP라 다른 칸이 바뀌면 MySQL이 지금으로 바꾼다. 엔티티 대신 JPQL 일괄 UPDATE를 쓰고(리스너를 거치지 않음), 같은 UPDATE에서 updated_at = updated_at으로 직접 넣으면(자동 갱신 안 함) 둘 다 막힌다.</details>

5. 신고를 대상별로 묶은 쿼리에 `countQuery`를 직접 준 이유는?
<details><summary>답</summary>Page를 만들려면 전체 개수가 필요한데, 묶은 쿼리에서 만든 개수 쿼리는 묶음마다 한 줄씩 나와 "묶음 수"가 아니다. 서로 다른 (대상 종류, 번호) 조합 수를 count(distinct concat(...))로 세어 준다.</details>

6. 신고 받기에서 대상 확인(404)을 로그인 확인(401)보다 먼저 하는 이유는?
<details><summary>답</summary>상태 코드 순서 규칙(404 → 401 → 403 → 400 → 409)을 지키기 위해서다. 비회원에게도 없는 글이나 볼 수 없는 글은 404여야 "그 번호에 무언가 있다"가 드러나지 않는다.</details>

7. 신고 처리 결과가 블라인드일 때 새 코드를 쓰지 않고 `ModerationService.blindPost`를 그대로 부르면 좋은 점은?
<details><summary>답</summary>신고로 숨기든 글 상세의 관리자 버튼으로 숨기든 상태·이력·알림이 똑같이 남는다. 규칙(수정 시각을 바꾸지 않기 등)을 한 곳에서만 고치면 된다.</details>

## 9. 더 읽을거리

- Spring Security 레퍼런스, Authorize HttpServletRequests (`authorizeHttpRequests`, `hasRole`): https://docs.spring.io/spring-security/reference/servlet/authorization/authorize-http-requests.html
- Spring Data JPA 레퍼런스, Projections(인터페이스 프로젝션): https://docs.spring.io/spring-data/jpa/reference/repositories/projections.html
- Spring Data JPA 레퍼런스, Modifying Queries(`@Modifying`, `clearAutomatically`, `flushAutomatically`): https://docs.spring.io/spring-data/jpa/reference/jpa/query-methods.html#jpa.modifying-queries
- MySQL 8.0 레퍼런스, Automatic Initialization and Updating for TIMESTAMP and DATETIME: https://dev.mysql.com/doc/refman/8.0/en/timestamp-initialization.html
- OWASP Logging Cheat Sheet(무엇을 남기고 왜 고치지 않나): https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html
- React Router, Nested Routes와 `useSearchParams`: https://reactrouter.com/
