# 스텝 13. 임시저장·대표 이미지

> 작업: T059, T058, T055c(보완) · 코드 브랜치: `step-13-draft-thumbnail` · 날짜: 2026-10-10 · 백로그 추천 순서의 두 번째 스텝

## 한눈에 보기

쓰다 만 글을 저장해 두었다가 이어 쓰고, 목록에 걸릴 사진을 직접 고를 수 있게 했다. 테이블(`post.status`, `post.thumbnail_image_id`)과 API 칸은 처음부터 있었고, 서버 규칙·화면을 채웠다.

| 작업 | 만든 것 | 핵심 파일 |
| --- | --- | --- |
| T059 | 임시저장(제목 없이도), 다시 저장, 임시저장 글을 발행하면 그때가 처음 발행 시각, 발행 글은 임시저장으로 못 돌림(400). 화면: 임시저장 버튼, 1분 자동 저장(바뀐 것만, 한 번에 하나씩, 불러오기 전에는 안 함), "임시저장됨 hh:mm", 임시저장 목록 링크와 수 | `PostSaveRequest`, `PostService.create`·`edit`, `Post.publish`, `components/editor/draft.ts`, `pages/manage/PostWritePage.tsx`, `DraftIntegrationTest` |
| T055c | 보완: 마이페이지 "내 블로그" — 활성 블로그 목록(글 수·대표·이사 표시), "대표로" 버튼, "블로그 만들기 (n/5)"(5개면 안내). 5개 한도 규칙은 스텝 4부터 있었는데, 블로그가 있는 회원이 두 번째 블로그를 만들러 갈 화면 입구가 없었다 | `blog/application/MyBlogService`, `blog/presentation/MyBlogController`, `pages/me/MyPage.tsx`, `MyBlogIntegrationTest` |
| T058 | 대표 이미지: 본문 이미지 중 고름, 안 고르면 본문 첫 이미지, 본문에 없는 이미지는 400. 목록 썸네일·공유 미리보기가 고른 이미지를 씀. 편집용 조회에 고른 번호와 후보 본문 이미지. 화면: 본문 아래 "대표 이미지" 칸 | `image/application/PostThumbnails`, `ManagedPostResponse`, `components/editor/thumbnail.ts`, `Editor.tsx`(`onImageUploaded`), `ThumbnailIntegrationTest` |

## 요청 흐름

```
[T059] 새 글 → 1분 → POST /api/posts {DRAFT} + Idempotency-Key → 201 {id: 16}
       → 1분 → PUT /api/posts/16 {DRAFT} → 200        (바뀐 것이 없으면 안 보냄)
       → 발행 → PUT /api/posts/16 {PUBLISHED} → 서버: 제목 검사, post.publish(now)
       남이 GET /api/posts/16 → 발행 전 404, 발행 뒤 200

[T058] GET /api/manage/posts/16 → { thumbnailImageId: null, images: [{id:41…}, {id:42…}] }
       42를 고르고 PUT {thumbnailImageId: 42} → 정화된 본문에 42의 주소가 있나 → 저장
       GET /api/posts → PostThumbnails.of: 고른 이미지(findAllById 한 번) + 나머지 첫 이미지(findByPathIn 한 번)
```

## 이 스텝을 이해하려면 (읽는 순서)

| 순서 | 개념 문서 | 이 스텝에서 쓰인 곳 |
| --- | --- | --- |
| 1 | [47 임시저장과 자동 저장](./concepts/47-draft-autosave.md) | 글의 상태와 되돌릴 수 없는 이동, 상태별 검증, 처음 POST 그 뒤 PUT과 연타 방지 키, `setInterval`과 낡은 값·`useRef`, 저장 줄 세우기, 스냅숏, 불러오기 전 저장 금지 |
| 2 | [48 대표 이미지](./concepts/48-representative-image.md) | 고른 번호 검증(본문 안에 있나, 정화된 본문으로), `null` = 자동, `ON DELETE SET NULL`, 한 페이지 쿼리 두 번, 파생 값, 편집용 응답의 후보 목록 |
| 3 | [23 트랜잭션과 동시성](./concepts/23-transactions-locking.md) 5.6 (보강) | 대표 블로그 바꾸기: 옛 대표 끄고 `flush`, 새 대표 켜기. 빼면 `Duplicate entry`인 것을 직접 확인 |
| 4 | (복습) [17 멱등성](./concepts/17-idempotency-redis.md), [16 인가와 가시성](./concepts/16-authorization-visibility.md), [25 React 폼](./concepts/25-react-forms-data.md) | 첫 POST의 키, 임시저장 글이 남에게 안 보이는 이유, 제어 컴포넌트와 `useEffect` |

## 막혔던 점

- **규칙은 있는데 입구가 없었다 (T055c)**: 지원이 확인하다 "5개까지 만들 수 있는데 새 블로그 만들기 버튼이 없다"를 찾았다. 스텝 4에서 개설 API·5개 한도·개설 화면을 만들었지만, 두 번째 블로그로 가는 입구(목업 마이페이지의 "내 블로그")는 BLOG-08과 함께 백로그에 묶여 T번호가 없었고, 머리글의 "블로그 만들기"는 블로그가 없을 때만 보였다. 규칙을 만들 때 "사용자가 화면에서 그 규칙까지 어떻게 가나"를 끝까지 따라가 봐야 한다. 스텝 13 안에서 보완으로 채웠다. 채운 뒤에도 지원이 "마이페이지 가는 버튼이 안 보인다"를 찾았다: 플랫폼 머리글은 밑줄 친 닉네임 글자가 링크였고, 블로그·관리 화면 머리글은 닉네임이 링크도 아닌 글자였다. 세 머리글 모두 "마이페이지" 버튼으로 바꿨다(목업의 블로그 머리글과 같은 모양). 입구는 "있다"가 아니라 "보인다"여야 한다.
- **대표 바꾸기의 UNIQUE**: 옛 대표를 끄는 UPDATE보다 새 대표를 켜는 UPDATE가 먼저 나가면 `uk_blog_primary_owner_id` 위반이다. 끄고 `flush`한 뒤 켠다. `flush`를 빼고 테스트를 돌려 `Duplicate entry '7'`로 실패하는 것을 확인했다([23](./concepts/23-transactions-locking.md) 5.6).
- **불러오기 전에 자동 저장하면 글을 덮는다**: 처음 코드는 수정 화면을 `DRAFT` 상태로 시작했다. 글을 불러오기 전(또는 실패)에 1분이 지나면 빈 입력값을 그 글에 PUT하게 된다. `LOADING` 상태를 두어 막았다([47](./concepts/47-draft-autosave.md) 3.6).
- **저장 시각이 9시간 어긋남**: "임시저장됨" 시각을 `Date.toISOString()`으로 만들었더니 UTC라 9시간 전으로 나왔다. 이 컴퓨터 시계 기준(`toLocaleTimeString('ko-KR')`)으로 바꿨다.
- **수정 화면이 본문 이미지 번호를 모름**: 본문 HTML에는 주소만 있다. 편집용 조회 응답에 `thumbnailImageId`와 `images`를 더했다(API 명세에 반영, 아래 표).
- **가시성은 고칠 것이 없었다**: 임시저장 글이 남에게 새는지 걱정했지만, 가시성 판단과 블로그 목록이 처음부터 `PUBLISHED`만 봤다. 코드 대신 테스트로 확인했다.
- **화면은 실제 브라우저로 확인**: 8081에 확인용 서버를 띄우고 헤드리스 Chrome으로 (1) 새 글에 제목·본문을 넣고 64초 → 임시저장 글 +1, "임시저장됨 01:40", 1분 더 → 더 늘지 않음, (2) 임시저장 글을 열어 두 번째 이미지를 고르고 제목 넣어 발행 → 글 상세로 이동, 블로그 목록 썸네일이 두 번째 이미지. (3) 마이페이지(넓은 화면·360px)에서 내 블로그 두 개, "블로그 만들기 (2/5)", "대표로"를 누르면 대표 표시가 옮겨 가고 머리글의 내 블로그·글쓰기도 새 대표 블로그로 바뀜, 가로 넘침 없음. 확인용 회원(`draft-check-563974@example.com`)·블로그(`draft563974`, `draft563974b`)가 개발 DB에 남아 있다.

## 명세와 다르거나 아직 채우지 않은 것

| 항목 | 지금 | 언제 |
| --- | --- | --- |
| 편집용 글 조회 응답 | `thumbnailImageId`, `images: [{ id, url, thumbnailUrl }]`를 더함(API 명세에 반영) | 지원 확인 |
| 글쓰기 화면 주소 | 목업은 수정이 `/manage/write/{id}`, 구현은 스텝 5부터 `/manage/posts/{id}/edit` | 그대로 |
| 화면을 떠날 때 경고 | 저장 안 된 변경이 있어도 경고하지 않는다(최대 1분 치를 잃을 수 있음) | 필요하면 `beforeunload` |
| 예약 발행(POST-13) | `SCHEDULED`는 여전히 400 | 백로그 |

## 직접 해 보기

```bash
./mvnw test -Dtest='DraftIntegrationTest,ThumbnailIntegrationTest,MyBlogIntegrationTest'
cd frontend && npx vitest run src/components/editor
```

화면: [47](./concepts/47-draft-autosave.md) 7.1(제목만 쓰고 1분 → 목록에서 이어 쓰기 → 발행), [48](./concepts/48-representative-image.md) 7.1(사진 두 장, 두 번째를 대표로).
