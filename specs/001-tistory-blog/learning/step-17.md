# 스텝 17. 글·댓글·카테고리·태그 설정

> 작업: T060a, T097, T098, T101, T102, T103, T104 · 코드 브랜치: `step-17-post-settings` · 날짜: 2026-10-11 · 백로그를 크게 묶은 다섯 스텝 중 둘째(2026-10-11 지원 결정)

## 한눈에 보기

주인이 글과 블로그를 다듬는 설정을 연다. 카테고리를 끌어서 놓아 순서와 상하위를 바꾸고, 카테고리를 비공개로 돌리고, 태그 이름을 바꾸거나 지운다. 글마다 댓글을 막을 수 있고, 정한 시각에 저절로 발행되게 예약한다. 독자는 비밀댓글을 쓰고, 글 아래에서 같은 카테고리의 다른 글을 본다. 대부분 테이블 칸(`is_private`, `is_comment_allowed`, `scheduled_at`, `is_secret`)과 판단 코드는 이미 있었고, 이번에는 입력을 열고 화면을 붙였다. 새로 생긴 것은 **1분마다 도는 예약 발행 작업**이다.

| 작업 | 만든 것 | 핵심 파일 |
| --- | --- | --- |
| T060a 카테고리 순서 (CAT-04) | `PUT /api/categories/order`(전체 한 번에, 빠짐·중복 400, 3단계 409 `CATEGORY_DEPTH`, 같은 자리 같은 이름 409). 화면: 끌어서 놓기, "하위로 넣기"·"최상위 맨 아래로" 칸, "순서 저장"·"되돌리기" | `CategoryService.reorder`, `Category.moveTo`, `pages/manage/categoryOrder.ts`, `CategoriesPage.tsx` |
| T097 비공개 카테고리 (CAT-05) | `PATCH /api/categories/{id}`의 `isPrivate`. 비공개 카테고리와 그 하위의 글은 주인 말고는 목록·글 수·상세·검색·홈·피드에서 없음 | `Category.isHidden`, `PostVisibilityPolicy`, `PostSpecifications.visibleTo` |
| T098 태그 관리 (TAG-03, TAG-04) | `PATCH`·`DELETE /api/tags/{id}`: 글에 달 때와 같은 이름 규칙, 다른 태그와 같은 이름 409, 지우면 연결만 끊기고(외래 키 CASCADE) 글은 남음. 관리 전용 목록 `GET /api/manage/tags`(초안·예약 글의 태그 포함, 발행 글 수). 글을 지우거나 고쳐 글이 남지 않은 태그는 자동 삭제, 볼 수 있는 글이 없는 태그 주소는 404. 화면: 태그 표의 "이름 변경"·"삭제", 발행 글이 없으면 "1 (발행 0)"에 링크 없음 | `TagManageService`, `TagNames.normalizeOne`, `TagService.removeUnused`, `TagRepository.deleteUnused`·`findLockedByIdIn`, `TagListService.managed`, `PostService`, `TagController` |
| T101 비밀댓글 (CMT-06) | 댓글 쓰기의 `secret: true`를 받음(전에는 400). 화면: 댓글·답글 칸 "비밀댓글" | `CommentRequest`, `CommentService.write`, `CommentForm.tsx`, `Comments.tsx` |
| T102 댓글 허용 (CMT-07) | 글 저장의 `commentAllowed`(보내지 않으면 새 글은 허용, 수정은 그대로). 화면: 글쓰기 "댓글 허용" | `PostSaveRequest`, `PostService`, `Post.changeCommentAllowed`, `PostWritePage.tsx` |
| T103 예약 발행 (POST-13) | 글 저장의 `SCHEDULED`·`scheduledAt`(지금보다 뒤), 1분마다 도는 작업이 그 시각을 발행 시각으로 공개 발행, 편집용 조회에 `scheduledAt`. 화면: 글쓰기 "예약 발행"과 시각, 글 관리 "예약" 필터 | `Post.schedule`·`publishScheduled`, `ScheduledPublisher`, `SchedulingConfig`, `PostWritePage.tsx`, `ManagePostsPage.tsx` |
| T104 같은 카테고리 글 (OWN-05) | `GET /api/posts/{id}/same-category?size=5`: 볼 수 있는 글만 최신순, 이 글 빼고, 미분류면 빈 목록. 화면: 글 상세 아래 "'여행' 카테고리의 다른 글" | `PostQueryService.sameCategory`, `PostController`, `components/SameCategoryPosts.tsx` |

## 요청 흐름

```
[순서] 주인이 "개발" 줄을 끌어 "여행" 위에 놓음 → moveBefore(draft) → 저장 전 순서(화면에만)
        "순서 저장" → PUT /api/categories/order [{id,parentId,sortOrder}…전부]
        → 빠짐·중복? 400 → 3단계? 409 → 같은 자리 같은 이름? 409 → 자리마다 0,1,2… moveTo → 204

[비공개] "여행" 비공개로 → PATCH /api/categories/3 {isPrivate:true}
        남이 여행/제주의 글 → GET /api/posts/24 → PostVisibilityPolicy: category.isHidden() → 404
        남이 블로그 목록 → visibleTo: NOT EXISTS(숨은 카테고리) → 그 글들 빠짐, 사이드바에서도 빠짐

[예약] 글쓰기 "예약 발행" 켜고 10:30 → POST /api/posts {status:SCHEDULED, scheduledAt:"…T10:30:00"}
        → 지금보다 뒤? → Post(SCHEDULED) → 글 관리 ?status=SCHEDULED 로 이동
        10:30 지나고 1분 안에: ScheduledPublisher.run() (트랜잭션)
        → SCHEDULED이고 scheduledAt <= 지금인 글 → publishScheduled() (PUBLISHED, PUBLIC, publishedAt=10:30)
        → 커밋 → 블로그 목록·피드에 나타남

[글 없는 태그] 주인이 글 29(태그: 지울태그, jpa) 삭제 → DELETE /api/posts/29
        → 달려 있던 태그 번호 {지울태그, jpa}를 들고 → deleted_at 채움
        → DELETE FROM tag WHERE id IN (…) AND NOT EXISTS(지우지 않은 글의 연결) → 지울태그만 지워짐(jpa는 다른 글이 씀)
        관리 → GET /api/manage/tags → 지울태그 없음 / GET /api/posts?tag=지울태그 → 404

[같은 카테고리] 글 상세 → GET /api/posts/24/same-category?size=5
        → 이 글을 볼 수 있나(글 상세와 같은 판단) → listedIn(블로그, 보는 사람) AND category=같음 AND id≠24 → 최신 5개
```

## 이 스텝을 이해하려면 (읽는 순서)

| 순서 | 개념 문서 | 이 스텝에서 쓰인 곳 |
| --- | --- | --- |
| 1 | [52 예약 작업과 프록시 자기 호출](./concepts/52-scheduled-jobs-proxy.md) (새 문서) | `@Scheduled`와 1분마다 DB 훑기, 정한 시각과 돈 시각, 글 상태 기계에 예약 더하기, 같은 객체 안 호출에 트랜잭션이 안 걸린 실제 버그, 테스트에서 작업 끄기 |
| 2 | [39 계층 데이터](./concepts/39-category-hierarchy.md) 5.8, 5.9, 7.5 | 비공개 카테고리의 글 숨기기(정책과 NOT EXISTS 부분 쿼리), 전체 순서 한 번에 저장의 검사 순서, 끌어서 놓기 순수 함수와 HTML5 드래그 이벤트 |
| 3 | [31 태그와 다대다](./concepts/31-tags-many-to-many.md) 5.12, 5.13 | 이름 바꾸기에 같은 규칙 쓰기, 자기 자신을 빼고 같은 이름 찾기, 외래 키 CASCADE로 태그 지우기, 글 없는 태그 자동 삭제(`NOT EXISTS`, flush), 관리 전용 목록, 지워지는 태그를 잠그며 읽기와 빈 자리 잠금 데드락 |
| 4 | [29 댓글 설계](./concepts/29-comments-design.md) 5.13 | 이미 있던 판단에 입력만 열기(비밀댓글, 댓글 허용) |
| 5 | (복습) [16 인가와 가시성](./concepts/16-authorization-visibility.md), [23 트랜잭션과 잠금](./concepts/23-transactions-locking.md) | 가시성 판단을 한 곳에 둔 덕에 조건 하나로 모든 목록이 바뀐 것, `@Transactional`이 프록시로 걸리는 원리 |

## 막혔던 점

- **예약 글이 매분 "발행"되는데 발행되지 않음**: 테스트는 통과했는데 브라우저 확인 중 서버 로그에 `예약 발행 1개`가 1분마다 찍히고 글은 그대로 예약 목록에 있었다. 작업의 입구 `run()`이 같은 객체의 `publishDue()`를 불러 프록시를 거치지 않았고, 그래서 `publishDue()`의 `@Transactional`이 걸리지 않아 바뀐 상태가 저장되지 않았다. 테스트는 `publishDue()`를 바깥에서(프록시로) 불러서 못 잡았다. `run()`에 `@Transactional`을 걸고, `run()`을 부르는 테스트(`schedulerEntryPointPersistsThePublishing`)를 더했다. 고치기 전 코드에서 이 테스트가 실패하는 것도 확인했다. 다시 띄운 서버에서 로그가 한 번만 찍히고 `published_at`이 정한 시각으로 저장됐다([52](./concepts/52-scheduled-jobs-proxy.md) 5.4).
- **같은 카테고리 글이 500**: 글 요약을 만들며 카테고리 이름을 읽는데, 목록 쿼리가 카테고리를 같이 읽지 않아 트랜잭션 밖에서 `LazyInitializationException`. 다른 목록처럼 `project("category")`로 같이 읽게 했다([06](./concepts/06-jpa-entity-mapping.md)).
- **"아직 없다"를 기대하던 테스트**: 비밀댓글 400, 예약·댓글 허용 400을 확인하던 기존 테스트(`CommentIntegrationTest`, `PostWriteIntegrationTest`)를 새 규칙(201, 저장됨, 대신 잘못된 예약 시각은 400)으로 고쳤다.
- **테스트 중 작업이 돌면**: 1분마다 도는 작업이 테스트 데이터를 건드리면 결과가 시점에 따라 달라진다. `app.scheduling.enabled=false`로 테스트에서는 작업을 끄고(`SchedulingConfig`의 `@ConditionalOnProperty`), 테스트는 작업 메서드를 직접 부른다.
- **글을 지워도 관리 표에서만 사라지던 태그**: 스텝을 마친 뒤 지원이 "태그 달린 글이 삭제되면 관리창에서 태그가 사라지는지 등 여러 경우를 고려해 보라"고 했다. 관리 표가 사이드바와 같은 API를 써서 발행 글의 태그만 보였고, 화면에서 사라진 태그가 DB에는 남아 이름 바꾸기에서 보이지 않는 409를 냈다. 초안에만 단 태그는 관리할 방법이 없었다. 지원이 "글이 남지 않은 태그는 자동으로 지우기"로 정해, 글 삭제·수정 뒤 정리, 관리 전용 목록, 태그 주소 404를 넣었다([31](./concepts/31-tags-many-to-many.md) 5.13).
- **이름으로 잠갔더니 데드락**: 태그가 지워질 수 있게 되자, 글 저장이 읽은 태그가 커밋 전에 지워지면 500이 날 수 있었다. 있는 태그를 잠그며 읽게 했는데 처음에 이름으로 잠갔더니, 같은 새 태그를 동시에 넣는 기존 테스트가 데드락으로 깨졌다(없는 이름의 빈 자리 잠금). 찾은 행만 기본 키로 잠가 고쳤다.
- **틀렸던 설명**: 처음에 "외래 키가 있으니 연결을 먼저 지워야 태그를 지울 수 있다"고 쓰고 그렇게 만들었다. 스키마의 `ON DELETE CASCADE`를 보고 그 문장을 지우고 문서도 고쳤다. `flushAutomatically`도 "빼면 태그가 남는다"고 쓰려다 직접 빼고 돌려 보니 통과했다(Hibernate가 네이티브 쿼리 앞에서 스스로 flush). 문서에는 실험 결과대로 적었다.
- **끌어서 놓기를 자동으로 확인**: 헤드리스 Chrome에서 `new DragEvent('dragstart', { dataTransfer: new DataTransfer() })`를 끄는 줄에, `dragover`·`drop`을 놓을 곳에 보내 확인했다. 판단은 순수 함수라 Vitest로 먼저 시험했다.
- **화면은 실제 브라우저로 확인**: 8081 확인용 서버와 헤드리스 Chrome으로
  - 갑: 카테고리 "개발"을 끌어 "여행" 위로, "제주"를 "여행"의 하위로 → "순서 저장" → 새로고침해도 그 순서
  - 갑: 태그 `spring` → `여행기`로 이름 변경, 태그 `secret` 삭제(글은 남음)
  - 갑: "여행" 비공개로 → 줄에 "비공개", "제주"에 "상위 비공개" / 을: 여행·제주의 글 404, 사이드바에 두 카테고리 없음
  - 갑: 글쓰기 "댓글 허용" 끄고 발행 → 을: "이 글에는 댓글을 쓸 수 없습니다.", 입력 칸 없음
  - 을: "비밀댓글"로 댓글 → 정에게는 "비밀댓글입니다.", 갑에게는 내용
  - 갑: "예약 발행" 켜고 2분 뒤 → 글 관리 "예약" 목록, 을에게는 404 → 그 시각이 지나자 실제 작업이 발행, 발행 시각은 정한 시각
  - 글 상세 아래 "'개발' 카테고리의 다른 글" 목록
  - 갑: 글 상세 "삭제"로 글 30(태그 또지울, jpa)을 지움 → 관리 표에서 "또지울"만 사라지고 jpa는 2 → 1. 그 뒤 "지울태그"를 "또지울"로 이름 변경이 됨(409 없음). 초안에만 단 "초안태그"는 "1 (발행 0)"으로 링크 없이 나오고, `/tag/초안태그`는 404 화면
  - 확인용으로 갑 블로그(`b13a22029`)에 카테고리 여행(비공개)·제주(하위)·개발과 글 24~30(29·30은 지움, 28은 "초안태그"를 단 임시저장 글)이 개발 DB에 남아 있다.

## 명세와 다르거나 아직 채우지 않은 것

| 항목 | 지금 | 언제 |
| --- | --- | --- |
| 예약 글의 공개 범위 | 예약 발행은 늘 공개(`PUBLIC`)로 발행. 글쓰기에서 예약을 켜면 안내 문구 | API 명세 `SCHEDULED` 줄에 원래 적힌 그대로 |
| 같은 카테고리 글의 범위 | 그 카테고리만(하위 카테고리 글은 넣지 않음), 미분류 글이면 빈 목록 | API 명세에 적음 |
| 순서 바꾸기·태그 이름 바꾸기의 오류 코드와 이름 규칙 | 400 `order`, 409 `CATEGORY_DEPTH`·`NAME_TAKEN`, 태그 이름은 글에 달 때와 같은 규칙 | API 명세에 적음 |
| 발행 시각의 정확도 | 1분마다 훑어서 정한 시각보다 최대 1분 늦게 나타남(발행 시각 값은 정한 시각) | 그대로, 글쓰기 안내에 "1분 안에" |
| 키보드로 카테고리 순서 바꾸기 | 끌어서 놓기만 있음 | 필요하면 |
| 태그 합치기 | 다른 태그 이름으로 바꾸면 409 | 필요하면 |
| 글 없는 태그 | 글을 지우거나 고쳐 지우지 않은 글이 하나도 남지 않으면 저절로 지움, 관리 표는 초안·예약 글의 태그까지 | 2026-10-11 지원 결정, spec TAG-03·04와 API 명세에 적음 |
| 글 삭제와 같은 태그로 글 저장이 같은 순간에 오면 | 드물게 저장한 글에서 그 태그가 빠질 수 있음 | 받아들임([31](./concepts/31-tags-many-to-many.md) 5.13) |
| 서버를 여러 대 띄울 때 예약 작업 중복 | 서버 한 대 기준. 여러 대면 같은 글을 두 번 훑을 수 있음(상태 조건으로 두 번 발행은 안 되지만 이벤트가 두 번) | 배포 구조를 정할 때([52](./concepts/52-scheduled-jobs-proxy.md) 6) |

## 직접 해 보기

```bash
./mvnw test -Dtest='PostSettingsIntegrationTest,TagIntegrationTest'
cd frontend && npx vitest run src/pages/manage/categoryOrder.test.ts && cd ..
```

화면: [52](./concepts/52-scheduled-jobs-proxy.md) 7.1(예약 발행 → 예약 목록 → 그 시각 뒤 블로그), 7.2(자기 호출 버그를 직접 만들어 보기), [39](./concepts/39-category-hierarchy.md) 7.5(비공개 카테고리, 끌어서 놓기), [31](./concepts/31-tags-many-to-many.md) 7.6(태그 이름 바꾸기·지우기).
