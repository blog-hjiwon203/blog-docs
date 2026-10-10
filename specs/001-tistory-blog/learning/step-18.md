# 스텝 18. 관리자·신고·공지

> 작업: T094, T095, T096, T109, T110, T111, T112 · 코드 브랜치: `step-18-admin` · 날짜: 2026-10-11 · 백로그를 크게 묶은 다섯 스텝 중 셋째(2026-10-11 지원 결정)

## 한눈에 보기

서비스 관리자가 문제 회원·게시물·블로그를 한 영역(`blog.com/admin`)에서 처리하고, 독자는 신고하고, 홈 상단에 공지가 보인다. 테이블(`report`, `moderation_log`, `notice`)과 "숨긴 것·정지된 것을 어떻게 보이나"(가시성 판단, 정지 안내, 숨김 사유)는 스텝 1·3·13·14에 이미 있었다. 이번에는 그 상태를 **바꾸는 입구**를 만들었다.

| 작업 | 만든 것 | 핵심 파일 |
| --- | --- | --- |
| T094 회원 정지 (ADMIN-02, SUB-04) | `GET /api/admin/members`(검색·상태 필터, 상태는 지금 기준), 상세(보유 블로그·받은 신고 수·정지 사유·제재 이력), 정지 7일/30일/영구·해제, 조치마다 관리 이력과 SANCTION 알림. 기간이 지나면 저절로 풀림 | `admin/application/ModerationService`, `AdminMemberService`, `Sanction`, `SuspensionPeriod`, `Member.suspend` |
| T095 숨김 (ADMIN-03) | `POST`·`DELETE /api/admin/posts/{id}/blind`, `/api/admin/comments/{id}/blind`. 작성자의 수정 시각을 바꾸지 않음 | `ModerationService`, `PostRepository.changeBlinded`, `CommentRepository.changeBlinded` |
| T096 관리 화면 | `/admin` 틀과 회원 화면(검색·필터·상세·정지·해제), 글 상세·댓글의 "숨기기 (관리자)", 관리 이력 표의 "해제" | `pages/admin/AdminPage.tsx`, `AdminMembersPage.tsx`, `LogTable.tsx`, `components/AdminBlindButton.tsx`, `app/admin.ts` |
| T109 블로그 제한 (ADMIN-05) | `POST`·`DELETE /api/admin/blogs/{id}/restriction`, 회원 상세의 보유 블로그 줄 "이용 제한"·"제한 해제" | `ModerationService.restrictBlog`, `AdminMembersPage.tsx` |
| T110 신고 (ADMIN-04) | `POST /api/reports`(볼 수 없는 대상 404, 같은 대상 409), 대상별 묶음 목록, 대상의 신고 목록, 처리(블라인드·블로그 제한·작성자 정지·기각 → 그 대상 신고 모두 완료). 화면: 글·댓글·블로그 프로필의 "신고", `/admin/reports` | `ReportService`, `AdminReportService`, `ReportRepository`, `components/ReportButton.tsx`, `AdminReportsPage.tsx` |
| T111 공지 (ADMIN-06) | 관리자 쓰기·고치기·지우기, `GET /api/notices`·`/latest`·`/{id}`. 화면: 홈 상단 띠, 머리글 "공지", `/notices`, `/notices/{id}` | `NoticeService`, `NoticeController`, `components/NoticeBand.tsx`, `pages/notice/` |
| T112 이력·대시보드 (ADMIN-06) | `GET /api/admin/moderation-logs`(대상·관리자·기간 검색, 조회만), `GET /api/admin/dashboard`(오늘 가입·새 글·처리 대기 대상 수·최근 조치 5) | `ModerationLogService`, `DashboardService`, `ModerationTargets`, `AdminDashboardPage.tsx`, `AdminLogsPage.tsx` |

## 요청 흐름

```
[신고] 을이 글 26의 "신고" → 저작권 침해 → POST /api/reports {targetType: POST, targetId: 26, reason: COPYRIGHT}
        → 을이 볼 수 있는 글인가(404) → 로그인(401) → 사유(400) → INSERT IGNORE report → 1행이면 201, 0행이면 409

[처리] 관리자 /admin/reports → GET /api/admin/reports (GROUP BY 대상, 신고 수 많은 순)
        "처리" → GET /api/admin/reports/POST/26 (신고 목록) → 블라인드·저작권 침해 → POST …/POST/26/resolve
        → ModerationService.blindPost (UPDATE is_blinded, 수정 시각 그대로 + 이력 BLIND + 알림 SANCTION)
        → UPDATE report SET status=DONE WHERE 대상=POST 26 AND PENDING   (한 트랜잭션)

[결과] 을 → GET /api/posts/26 → 숨긴 글, 작성자 아님 → 404
       갑(작성자) → 200 + blind {reason: COPYRIGHT, reasonMessage} → "관리자가 숨긴 글입니다 사유: 저작권 침해"

[정지] 관리자 회원 상세 → 7일·스팸 → POST /api/admin/members/9/suspension
        → Member.suspend(지금+7일) + 이력 SUSPEND + 알림
        갑의 다음 요청 → JwtAuthenticationFilter: isSuspendedAt(지금) → 403 MEMBER_SUSPENDED + 쿠키 지움
        다른 사람 → 갑의 블로그 → BlogVisibilityPolicy: 주인 정지 → 404
        7일 뒤 → isSuspendedAt(지금) false → 저절로 풀림(작업 없음)
```

## 이 스텝을 이해하려면 (읽는 순서)

| 순서 | 개념 문서 | 이 스텝에서 쓰인 곳 |
| --- | --- | --- |
| 1 | [53 서비스 관리](./concepts/53-admin-moderation-audit.md) (새 문서) | 주소 규칙으로 관리자만(401·403), 읽을 때 판단하는 정지 기간과 그 비용(상태 필터), 고치지 않는 이력과 "사유는 최신 이력 줄에서", 수정 시각을 바꾸지 않는 숨김(실제 버그), 신고 묶음의 GROUP BY·countQuery·인터페이스 프로젝션, 신고 처리가 조치를 그대로 부르기, 중첩 라우트와 주소에 둔 검색 조건 |
| 2 | [51 구독과 알림](./concepts/51-subscription-notification.md) 5.9 | 제재·해제 알림(SANCTION): "내가 한 일" 검사가 없는 이유, 누르면 갈 곳 |
| 3 | (복습) [27 소프트 삭제와 일괄 수정](./concepts/27-soft-delete-bulk-update.md) | `updated_at = updated_at`과 MySQL `ON UPDATE`, `clearAutomatically` |
| 4 | (복습) [16 인가와 가시성](./concepts/16-authorization-visibility.md), [11 JWT](./concepts/11-jwt.md) | 숨긴 글·제한 블로그·정지 회원의 블로그가 404인 판단(스텝 3부터), 토큰을 취소할 수 없어 요청마다 회원 상태를 보는 이유 |
| 5 | (복습) [51 구독과 알림](./concepts/51-subscription-notification.md) 3.2 | 신고를 한 번만 받는 `INSERT IGNORE`와 넣은 행 수 |

## 막혔던 점

- **숨김을 풀었더니 "수정 …"이 붙음**: 처음에는 엔티티의 `changeBlinded`로 숨김을 바꿨다. 브라우저 확인에서 숨김을 해제한 글 머리에 "수정 2026.10.11 04:42"가 붙었다. 작성자는 고친 적이 없다. 변경 감지의 `@LastModifiedDate`와 DB의 `ON UPDATE CURRENT_TIMESTAMP(6)`가 둘 다 수정 시각을 바꾼 것이다. JPQL 일괄 UPDATE에 `updatedAt = updatedAt`을 넣어 고치고, 테스트에 숨김·해제 전후 `updated_at` 비교를 더했다([53](./concepts/53-admin-moderation-audit.md) 5.5).
- **안내는 있는데 버튼이 없음**: 글을 숨긴 관리자에게 "해제는 회원 상세·관리 이력에서"라고 안내했지만 그 두 곳에 해제 버튼이 없었다. 브라우저 확인 계획을 쓰다 발견해 관리 이력 표(`LogTable`)에 "해제"를 더했다. 대상의 가장 최근 줄이고 지금 조치 중일 때만 보인다. 어느 API를 부를지는 순수 함수 `releasePath`가 정하고 단위 테스트가 있다.
- **"아직 없음"을 기대하던 테스트**: 스텝 4의 접근 제어 테스트가 "관리자는 통과하지만 대시보드 API가 아직 없어 404"를 확인하고 있었다. 이제는 200으로 바꿨다.
- **일괄 UPDATE 뒤의 지연 로딩**: 숨김 UPDATE가 영속성 컨텍스트를 비우므로(`clearAutomatically`), 알림 문구에 쓸 작성자 번호와 제목을 UPDATE 전에 꺼내 두었다.
- **상태 필터와 "저절로 풀림"**: 정지는 읽을 때 판단하므로 DB의 `status`가 SUSPENDED로 남아 있을 수 있다. 관리자 회원 목록의 "정지"·"활동" 필터를 `status`만으로 쓰면 기간이 지난 회원이 정지로 나와서, 종료 시각 비교를 SQL에도 넣었다(`suspensionEndsByItselfWhenThePeriodIsOver`).
- **좁게 몰린 공지 화면**: 지원이 확인하다 "공지 내용 조회 화면이 이상하다"고 했다. 공지 목록·상세에 로그인·회원가입 화면용 틀(`page narrow`, 폭 460px)을 써서 본문이 화면 가운데에 좁게 몰리고, 제목·날짜·본문 사이에 구분도 없었다. 일반 화면 폭(760px)으로 바꾸고, 상세는 글 상세와 같은 머리(공지 표시, 제목, 날짜, 구분선)와 읽기 폭의 본문(`prose`)으로 고쳤다. 360px 휴대폰 폭에서 가로 넘침이 없는 것도 확인했다. 틀 클래스를 고를 때 "이 클래스가 원래 어느 화면용인가"를 보고 쓴다.
- **화면은 실제 브라우저로 확인**: 8081 확인용 서버와 헤드리스 Chrome으로
  - 을: 글 26 "신고" → 저작권 침해 → "신고했습니다." 다시 열어 신고 → "이미 신고한 글입니다."
  - 을: 글 20의 댓글 "신고" → 기타를 고르면 설명 없이 신고 버튼이 꺼짐 → 설명을 쓰고 신고
  - 관리자: `/admin` "처리 대기 신고 2" → `/admin/reports` 두 묶음 → 글 26 "처리" → 블라인드 → "이 대상의 신고 1건이 모두 처리 완료되었습니다."
  - 을: 글 26 → 404 화면 / 갑: "관리자가 숨긴 글입니다 사유: 저작권 침해", 알림에 숨김 알림
  - 관리자: 갑 검색 → 상세 → 7일 정지 → "정지 중: 스팸·광고 (2026.10.18 04:41까지)" / 을: 갑 블로그 404 / 갑: 홈에서 정지 안내
  - 관리자: 제재 이력의 정지 줄 "해제" → 블로그가 다시 보임. 보유 블로그 "이용 제한" → 을에게 404, 갑의 관리 화면에 "이 블로그는 이용이 제한되었습니다 사유: 스팸·광고" → "제한 해제"
  - 관리자: 관리 이력에 조치 줄들, "글" 필터, 공지 등록 → 홈 띠 "공지 10월 정기 점검 안내 공지 전체" → 목록 → 상세(줄바꿈 유지)
  - 관리자: 글 상세·댓글에 "숨기기 (관리자)" / 관리 이력의 숨김 줄 "해제" → 을에게 글 26이 다시 보임
  - 확인용으로 개발 DB에 공지 1개, 신고 2건(글 26 처리됨, 글 20의 댓글 대기), 관리 이력 몇 줄이 남아 있다.

## 명세와 다르거나 아직 채우지 않은 것

| 항목 | 지금 | 언제 |
| --- | --- | --- |
| 신고 처리·회원 상세·이력의 응답 모양, 대시보드 "처리 대기 신고"가 대상 수인 것, 최신 공지가 없을 때 본문 없는 200, 기각 이력의 대상 | API 명세에 적음 | 반영함 |
| 같은 대상을 처리 뒤 다시 신고 | 회원·대상마다 한 번(UNIQUE)이라 409 | 그대로(ERD) |
| 정지 기간이 끝났을 때의 알림·이력 | 없음(관리자가 한 일이 아니고, 풀어 주는 작업도 없음) | 그대로 |
| 관리자가 다른 관리자 정지 | 400 | 그대로 |
| 공지 알림(모든 회원에게) | 없음 | 보류(2026-10-08 지원 결정) |
| 관리자 목록·이력의 관리자 이름 검색 | 관리자 번호로만 | 필요하면 |

## 직접 해 보기

```bash
./mvnw test -Dtest='AdminIntegrationTest,AccessControlIntegrationTest'
cd frontend && npx vitest run src/app/admin.test.ts && cd ..
```

화면: [53](./concepts/53-admin-moderation-audit.md) 7.1(신고 → 처리 → 숨김 → 정지 → 해제 → 공지), 7.2(401·403·404 순서), 7.4(수정 시각 실험).
