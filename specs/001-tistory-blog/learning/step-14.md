# 스텝 14. 댓글 수정·방명록·댓글 관리

> 작업: T066, T068 · 코드 브랜치: `step-14-comments` · 날짜: 2026-10-11 · 백로그 추천 순서의 세 번째 스텝

## 한눈에 보기

내 댓글을 고치고, 블로그마다 방명록을 남기고, 블로그 주인이 받은 댓글·방명록을 한 화면에서 지우거나 답글을 단다. 테이블(`guestbook`)은 스텝 1부터 있었고, 엔티티·API·화면을 새로 만들었다. 명세가 "방명록은 댓글과 같은 규칙"이라고 해서, 보는 사람 기준의 판단(비밀·지운 자리·숨김·고치기·지우기 권한)을 댓글·방명록·관리 화면이 **한 코드**로 쓰게 묶었다.

| 작업 | 만든 것 | 핵심 파일 |
| --- | --- | --- |
| T066 댓글 수정 (CMT-03) | `PATCH /api/comments/{id}`: 본인만(주인도 403), 숨긴 댓글 403, 404 → 401 → 403 → 400, 응답 `updatedAt`과 `viewer.canEdit`. 화면: 내 댓글의 "수정", 그 자리에서 고치기, "수정됨" | `CommentService.edit`, `CommentController`, `CommentEditRequest`, `components/CommentItem.tsx`, `commentList.ts`(`afterEdit`), `CommentEditIntegrationTest` |
| T066 방명록 (CMT-04) | `Guestbook` 엔티티, `/api/guestbook` 목록(최상위 글 기준 최신순 20 페이지, 답글은 부모 안)·쓰기(회원, `Idempotency-Key`, 비밀·답글 한 단계)·고치기(본인)·지우기(본인·주인, 답글 있으면 자리만). 화면: 블로그 머리글 "방명록", `/guestbook` | `comment/domain/Guestbook`, `GuestbookService`, `GuestbookController`, `pages/blog/GuestbookPage.tsx`, `components/CommentForm.tsx`(비밀글 칸), `GuestbookIntegrationTest` |
| T066 공통 | 댓글·방명록이 같은 판단을 쓰도록 `CommentEntry`(공통 모양)와 `CommentViews`(판단 한 곳)로 나눔 | `comment/domain/CommentEntry`, `comment/application/CommentViews`, `CommentView` |
| T068 댓글 관리 (MNG-02) | `GET /api/manage/comments?type=comment|guestbook&page=`: 주인만, 남이 쓴 것 최신순 20(답글도 한 줄씩), 지운 것·지운 글의 댓글 제외, 댓글은 달린 글. 화면: 관리 메뉴 "댓글·방명록", 탭, 삭제, 답글 바로 쓰기 | `manage/application/ManageCommentService`, `ManageCommentController`, `ReceivedCommentResponse`, `pages/manage/ManageCommentsPage.tsx`, `ManageCommentIntegrationTest` |

## 요청 흐름

```
[CMT-03] 글 상세 "수정" → PATCH /api/comments/88 { content }
         → checkEditable: 이 블로그 글의 지우지 않은 댓글? 글을 볼 수 있나? → 로그인? → 작성자이고 숨기지 않았나?
         → 입력 검사(1~1,000자) → comment.edit → flush(updatedAt 채움) → CommentViews.one → 200 Comment

[CMT-04] 블로그 머리글 "방명록" → /guestbook
         GET /api/guestbook?page=1 → 최상위 글 20(+전체 수) 한 번, 그 글들의 답글 한 번
                                   → CommentViews.threads(보는 사람 기준: 비밀이면 주인·작성자만 내용)
         "등록"(비밀글 체크) → POST /api/guestbook { content, parentId, secret } + Idempotency-Key → 201
         → 지금 페이지 다시 받기(2페이지에서 새 글이면 1페이지로)

[MNG-02] 관리 → "댓글·방명록" → GET /api/manage/comments?type=comment&page=1
         → 주인 확인 → 이 블로그 글의 남이 쓴 댓글(글 제목 함께) → CommentViews.flat(보는 사람 = 주인)
         "답글" → POST /api/posts/{글}/comments { parentId: 그 댓글(답글 줄이면 그 부모) }  ← 글 상세와 같은 API
         "삭제" → DELETE /api/comments/{id} 또는 /api/guestbook/{id} → 다시 받기
```

## 이 스텝을 이해하려면 (읽는 순서)

| 순서 | 개념 문서 | 이 스텝에서 쓰인 곳 |
| --- | --- | --- |
| 1 | [29 댓글 설계](./concepts/29-comments-design.md) (복습 + 5.12 보강) | 스텝 6·7의 댓글 규칙(가시성 물려받기, 상태 코드 순서, 보는 사람마다 다른 응답, 답글 한 단계). 5.12 댓글 고치기: 본인만·숨김 403, 주인은 고칠 수 없는 이유, `flush`와 `@LastModifiedDate` |
| 2 | [50 같은 규칙의 두 기능을 한 코드로](./concepts/50-shared-rules-comment-guestbook.md) (새 문서) | 복사·상속·한 테이블·인터페이스+조립기 비교, `CommentEntry`와 `default` 메서드, `CommentViews`, 와일드카드 `? extends`, 방명록 페이지(최상위 글 기준)와 `findBy`의 `project`·`page`, `PageImpl`, "받은" 댓글, 화면 부품 나누기와 그 자리에서 고치기, 다시 받기 vs 화면에서 고치기 |
| 3 | (복습) [08 페이지 처리](./concepts/08-pagination.md), [17 멱등성](./concepts/17-idempotency-redis.md), [49 완료의 정의](./concepts/49-requirement-traceability.md) | 정렬에 id를 더하는 이유와 `PageQuery`, 방명록 쓰기의 연타 방지 키, 스텝 끝의 입구 확인 |

## 막혔던 점

- **판단 코드를 어디에 둘까**: 처음에는 방명록 서비스에 댓글의 `view` 메서드를 옮겨 적으려 했다. 그러면 스텝 13b에서 더한 작성자 사진, 이번의 `canEdit`을 두 번 써야 한다. 판단을 `CommentViews`로 꺼내고, 두 엔티티가 `CommentEntry`를 따르게 했다. 옮긴 뒤 기존 댓글 테스트가 그대로 통과하는 것으로 동작이 같음을 확인했다.
- **숨김 사유를 함수로 넘기다가 되돌림**: 처음 `CommentViews`는 숨김 사유를 찾는 함수를 서비스에서 받았다(방명록은 숨김이 없어서). 관리 화면 서비스는 다른 패키지라 댓글 서비스의 그 메서드를 쓸 수 없었다. 사유 찾기를 조립기 안으로 옮겨 인자를 없앴다. 방명록은 `isBlinded()`가 늘 `false`라 부를 일이 없다.
- **`updatedAt`이 응답에 안 나올 뻔함**: `@LastModifiedDate`는 UPDATE 직전에 채워져서, 트랜잭션 끝까지 기다리면 응답을 만들 때는 아직 옛값이다. 고친 뒤 `flush()`([29](./concepts/29-comments-design.md) 5.12).
- **"받은"을 어떻게 읽나**: 명세 MNG-02는 "받은 댓글·방명록 목록"이다. 주인이 단 답글도 넣으면 주인이 답글을 달 때마다 자기 글이 목록 맨 위에 쌓인다. 주인 자신의 것은 빼고, API 명세에 적었다(아래 표).
- **화면은 실제 브라우저로 확인**: 8081 확인용 서버와 헤드리스 Chrome으로 회원 셋(갑 주인, 을 방문자, 정 다른 회원)과 비회원이 되어 확인했다.
  - 을: 글 20의 자기 댓글에 "답글|수정|삭제", 병의 댓글에는 "답글"만. 고쳐서 저장하면 "을이 고친 댓글"과 "수정됨", 새로고침해도 같음.
  - 을: 머리글 "방명록" → `/guestbook`, 비밀글 하나·보통 글 하나. 비밀글에 "비밀" 표시.
  - 정·비회원: 비밀글은 "비밀글입니다."(작성자 없음), 비회원은 "로그인하고 방명록 남기기".
  - 갑: 비밀글 내용이 보이고 버튼은 "답글|삭제"(남의 글이라 수정 없음). 을의 글에 답글 → 부모 아래에 바로 보임.
  - 갑: 관리 → "댓글·방명록" → 댓글 탭에 병·을의 댓글과 글 제목 "공개 글"(주인의 답글은 없음). 답글 → "답글을 달았습니다", 글 상세에 그 답글. 방명록 탭(`?type=guestbook`)에 을의 두 글과 "비밀" 표시.
  - 을: 방명록 글을 고치면 "(고침)"과 "수정됨".

## 명세와 다르거나 아직 채우지 않은 것

| 항목 | 지금 | 언제 |
| --- | --- | --- |
| 받은 댓글 목록에서 주인 자신의 글 | 뺀다(API 명세에 적음) | 반영함 |
| 받은 댓글 목록의 답글 | 묶지 않고 한 줄씩(`parentId`, `replies`는 빈 배열). API 명세에 적음 | 반영함 |
| 댓글 고치기·방명록 고치기의 상태 코드 순서 | 404 → 401 → 403 → 400. API 명세에 적음 | 반영함 |
| 작성자 차단·금칙어(목업 manage-comments 4번, guestbook 2번의 403·400) | 없음(MNG-04) | 백로그 T084, T085 |
| 댓글의 비밀댓글(CMT-06) | 방명록 비밀글은 됨. 댓글 쓰기의 `secret`은 여전히 400 | 백로그(판단 코드는 이미 같이 씀) |
| 방명록의 관리자 숨김 | ERD에 칸이 없어 없음 | 그대로 |

## 직접 해 보기

```bash
./mvnw test -Dtest='CommentEditIntegrationTest,GuestbookIntegrationTest,ManageCommentIntegrationTest'
cd frontend && npx vitest run src/components/commentList.test.ts && cd ..
```

화면: [50](./concepts/50-shared-rules-comment-guestbook.md) 7.1(고치기, 방명록 비밀글, 관리 화면 답글), 7.2(페이지 경계), 7.3(판단 한 곳을 바꾸면 세 기능이 같이 바뀌는 것).
