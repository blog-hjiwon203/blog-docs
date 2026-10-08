# 스텝 5. 글쓰기

> 작업: T029, T030, T031, T032, T033, T034, T035, T035a, T040 · 코드 브랜치: `step-5-write-posts` · 날짜: 2026-10-08

## 한눈에 보기

블로그 주인이 관리 화면에서 카테고리를 만들고, 에디터로 글을 써서 발행·수정·삭제하고, 공개·비공개를 바꾼다. 발행한 글은 블로그 메인과 사이드바에 보이고, 비공개로 바꾸면 다른 사람에게서 사라진다.

| 기능 | API | 핵심 파일 |
| --- | --- | --- |
| 카테고리 (CAT-01) | `GET·POST /api/categories`, `PATCH·DELETE /api/categories/{id}` | `category/application/CategoryService`, `CategoryController`, `PostRepository.uncategorize` |
| 카테고리별 목록 (CAT-02) | `GET /api/posts?categoryId=` | 스텝 4에서 이미 만듦(`PostQueryService.inCategory`) |
| 발행 (POST-01) | `POST /api/posts` (`Idempotency-Key`) | `post/application/PostService.publish`, `PostManageController`, `PostSaveRequest` |
| 편집용 조회·수정 (POST-02) | `GET /api/manage/posts/{id}`, `PUT /api/posts/{id}` | `PostService.findOwned`, `findEditable`, `edit`, `Post.edit` |
| 삭제 (POST-03) | `DELETE /api/posts/{id}` | `PostService.delete`, `CommentRepository.softDeleteByPostId`, `PostRepository.deleteLikes·deleteNotifications` |
| 공개 범위 (POST-06) | `PATCH /api/posts/{id}/visibility` | `PostService.changeVisibility`, `VisibilityRequest` |
| 화면 | `{주소}/manage/write`, `/manage/posts/{id}/edit`, `/manage/categories` | `frontend/src/components/editor/Editor.tsx`, `pages/manage/PostWritePage.tsx`, `CategoriesPage.tsx` |
| 마크다운 입력 (T035a) | API 변화 없음 | `components/editor/markdown.ts`, `Editor.tsx`의 `MarkdownLinkInput`·`handlePaste`, `@tiptap/markdown` |

**T035a는 스텝 5를 병합한 뒤 지원 결정으로 더한 작업이다**(브랜치 `step-5-markdown-input`). WYSIWYG와 마크다운 중 하나를 고르는 것이 아니라 한 에디터에서 섞어 쓴다. `## `, `**굵게**`, `- `, `[글자](https://...)`를 치면 바로 서식이 되고, 마크다운 글을 붙여넣어도 서식으로 바뀐다. 저장은 HTML 그대로다.

## 요청 흐름

### 발행 버튼 한 번

```
PostWritePage (alpha.blog.test/manage/write)
  useRef(newIdempotencyKey())  ← 화면을 열 때 키 하나. HTTP 주소라 randomUUID가 없으면 getRandomValues로 만든다
  POST /api/posts  Idempotency-Key: K, X-Requested-With, 쿠키
   │
   ▼ 보안 필터(CSRF 헤더, JWT) → IdempotencyInterceptor: SET NX idempotency:{회원}:POST:/api/posts:K
   ▼ PostManageController.publish
     ├ @CurrentBlog            Host → 블로그 (없으면 404)
     ├ BlogOwnerGuard          비회원 401, 남이면 403
     ├ RequestValidator        제목 1~200자, 공개 범위 필수 → 400
     ├ checkSupported()        임시저장·예약·구독자 공개·태그·대표 이미지·댓글 막기 → 400 (아직 없는 기능)
     └ PostService.publish     HtmlSanitizer로 정화 → SummaryExtractor로 요약 → published_at = 지금 → 저장
   ▼ 201 { id, status, url } + Location
   │  (같은 K로 다시 오면 인터셉터가 이 응답을 그대로 돌려준다)
   ▼
화면이 /{id}로 이동 (글 상세 화면은 스텝 6)
```

### 남의 글에 수정 요청이 오면

`PostService.findOwned`가 스텝 3의 `PostVisibilityPolicy.decide` 결과를 상태 코드로 바꾼다.

| 판단 결과 | 응답 | 예 |
| --- | --- | --- |
| `Owner` | 진행 (숨긴 글이면 수정만 403 `POST_BLINDED`) | 주인 |
| `NotFound`, `MovedTo` | 404 | 없는 글, 지운 글, 다른 블로그 글, 남의 비공개 글 |
| `Visible`, `SubscribersOnly` | 비회원 401, 회원 403 | 남의 공개 글 |

볼 수 없는 글에는 401·403 대신 404라서, 남의 비공개 글이 있는지조차 알 수 없다(헌법 원칙 II).

## 이 스텝을 이해하려면 (읽는 순서)

Thymeleaf로 화면을 만들어 봤고 React는 처음이라면 [28 Thymeleaf에서 React로](./concepts/28-thymeleaf-to-react.md)를 먼저 읽는다. 컨트롤러가 JSON만 주는 이유, 빌드 스크립트가 필요한 이유가 여기 있다.

| 순서 | 개념 문서 | 이 스텝에서 그 개념이 쓰인 곳 |
| --- | --- | --- |
| 1 | [26 WYSIWYG 에디터와 Tiptap](./concepts/26-wysiwyg-editor-tiptap.md) | `Editor.tsx`, 서버 허용 목록과 맞춘 서식, 이중 정화, 마크다운 입력 규칙과 붙여넣기(T035a) |
| 2 | [14 XSS, HTML 정화, CSP](./concepts/14-xss-sanitize-csp.md)의 스텝 5 부분 | 발행·수정이 `HtmlSanitizer`·`SummaryExtractor`를 지나는 곳 |
| 3 | [16 인가와 가시성 판단](./concepts/16-authorization-visibility.md)의 스텝 5 부분 | `findOwned`의 404/401/403, `POST_BLINDED` 순서 |
| 4 | [22 입력 검증과 JSON 바인딩](./concepts/22-bean-validation.md)의 스텝 5 부분 | `PostSaveRequest.checkSupported`, `@Null parentId` |
| 5 | [17 멱등성과 Redis](./concepts/17-idempotency-redis.md)의 스텝 5 부분 | 발행 API의 `@Idempotent`, 화면당 키 하나 |
| 6 | [27 소프트 삭제와 일괄 수정](./concepts/27-soft-delete-bulk-update.md) | 글 삭제와 딸린 데이터, `@Modifying`, 변경 감지, 수정 시각 지키기 |
| 7 | [19 React Router와 API 클라이언트](./concepts/19-react-router-api-client.md)의 스텝 5 부분 | `newIdempotencyKey`의 `randomUUID` 대체, 새 라우트 |
| 8 | [25 React 폼과 데이터 불러오기](./concepts/25-react-forms-data.md)의 스텝 5 부분 | `PostWritePage`, `CategoriesPage` |

## 막혔던 점

- **HTTP 개발 주소에 `crypto.randomUUID`가 없음**: 스텝 3에서 남긴 문제를 이 스텝에서 고쳤다. 헤드리스 Chrome으로 `http://e2e27410.blog.test:8081/manage/write`를 열어 확인하니 실제로 `typeof crypto.randomUUID`가 `undefined`였다. `crypto.getRandomValues`로 UUID v4를 만들게 바꾸고, 같은 화면에서 입력 → 굵게 → 발행까지 눌러 `/7`로 이동하는 것을 확인했다.
- **숨긴 글에 잘못된 본문을 보내면 400이 먼저 남**: 수정 API는 주인 확인 → 입력 검증 → 숨김 확인 순서였다. 상태 코드 순서(403이 400보다 먼저)에 맞게 숨김 확인을 `findEditable`로 빼서 검증보다 앞에 두었다.
- **카테고리를 지우면 글의 수정 시각이 바뀜**: `post.updated_at`은 MySQL `ON UPDATE CURRENT_TIMESTAMP`라 일괄 수정 때도 바뀐다. 작성자가 고친 것이 아니어서 `p.updatedAt = p.updatedAt`으로 그대로 다시 넣었다([27](./concepts/27-soft-delete-bulk-update.md)).
- **댓글 일괄 수정 뒤 글이 저장되지 않을 뻔함**: `@Modifying(clearAutomatically = true)`가 영속성 컨텍스트를 비워, 그 전에 읽은 글 엔티티가 더는 관리되지 않는다. 삭제는 일괄 수정 뒤 글을 다시 읽어 지운다.
- **마크다운 확장이 붙여넣기를 처리하지 않음**: `@tiptap/markdown`은 마크다운을 해석해 주지만 붙여넣기를 스스로 가로채지 않는다. `editorProps.handlePaste`를 직접 달았다. 처리기 안에서 에디터를 쓰려고 ref를 그리는 중에 바꿨다가 oxlint 경고(`react(refs)`)를 받아 `useEffect`로 옮겼다.
- **8080 포트가 이미 쓰는 중**: 지원이 띄운 서버였다. 끄지 않고 확인용 서버를 `--server.port=8081`로 따로 띄웠다.
- **카테고리 행의 버튼이 아래로 떨어짐**: `.box`의 `display: grid`가 `.row`의 flex를 덮었다. 목업 CSS의 `.box.row { display: flex; }`를 옮겼다.

## 명세와 다르거나 아직 채우지 않은 것

| 항목 | 지금 | 언제 |
| --- | --- | --- |
| 임시저장·예약 발행 (`status` DRAFT·SCHEDULED) | 400 | 백로그 POST-08, POST-13 |
| 구독자 공개 (`SUBSCRIBERS`) | 400 (contracts에 적힌 대로) | SUB-01 |
| 태그·대표 이미지·댓글 막기 (`tagNames`, `thumbnailImageId`, `commentAllowed: false`) | 보내면 400. 조용히 버리지 않는다 | 스텝 7, POST-07, CMT-07 |
| 주제 (`topic`) | API는 받음, 화면에는 고르는 칸 없음 | 스텝 9 (T056) |
| 하위 카테고리 (`parentId`), 카테고리 순서·비공개 | `parentId`를 보내면 400 | 스텝 9 (T060), 백로그 |
| 카테고리 T030 | 스텝 4에서 API·화면·테스트를 이미 만들어 이 스텝에서 더한 것이 없음 | — |
| 발행 뒤 이동한 글 상세 화면 | 아직 자리만 있음 | 스텝 6 (T041, T045) |

## 남은 문제

| 문제 | 영향 | 언제 | 자세히 |
| --- | --- | --- | --- |
| `Idempotency-Key`가 없으면 블로그 확인(404)·주인 검사(401·403)보다 먼저 400이 난다(인터셉터가 컨트롤러 앞) | 키 없이 보내면 없는 블로그도, 비회원도 400 | 정리할 때 | [17](./concepts/17-idempotency-redis.md) |
| 본문 길이에 상한이 없다(`mediumtext`는 16MB) | 아주 큰 요청 | 정리할 때 | |
| 카테고리 이름 중복은 DB 정렬 규칙(대소문자 무시)으로 판단한다 | `Java`와 `java`를 같은 이름으로 본다 | 명세 확인 필요 시 | |

스텝 3의 남은 문제 중 `crypto.randomUUID()`를 이 스텝에서 고쳤다.

## 직접 해 보기

```bash
./mvnw test -Dtest='CategoryIntegrationTest,PostWriteIntegrationTest,PostLifecycleIntegrationTest'
cd frontend && npm test
```

브라우저로 (`/etc/hosts`에 블로그 주소가 있어야 한다):

1. `docker compose up -d && ./scripts/build-frontend.sh && ./mvnw spring-boot:run`
2. 내 블로그 `http://{주소}.blog.test:8080/manage/categories`에서 카테고리 `Java` 추가
3. `/manage/write`에서 제목·본문(제목·굵게·목록·인용·코드·링크)·카테고리를 넣고 발행 → `/{글 번호}`로 이동
4. 블로그 메인에서 글 옆 "수정" → 제목을 고쳐도 목록 순서와 주소가 그대로인지
5. 수정 화면에서 비공개로 저장 → 로그아웃하거나 시크릿 창에서 블로그 메인을 열면 글이 없고, 글 수도 줄어 있다
6. 카테고리 `Java` 삭제 → 그 글이 미분류로
7. 수정 화면에서 삭제 → 목록에서 사라짐

```bash
# Redis에 남은 연타 방지 키 (10분)
docker exec blog-redis redis-cli --scan --pattern 'idempotency:*'
# 지운 글은 행이 남아 있다(소프트 삭제)
docker exec blog-mysql mysql -ublog -pblog blog -e "SELECT id, title, deleted_at FROM post ORDER BY id DESC LIMIT 5"
```

## 더 공부할 거리

- ProseMirror의 문서 모델과 스키마, Tiptap 확장 만들기
- JPA 변경 감지와 플러시 시점, 일괄 수정과 영속성 컨텍스트
- 소프트 삭제를 Hibernate `@SoftDelete`·`@SQLRestriction`으로 하는 방법과, 이 프로젝트가 조회 조건에 직접 넣은 이유
- 보안 컨텍스트(Secure Context)에서만 되는 웹 API들
- Chrome DevTools Protocol로 화면 자동 확인하기(Playwright가 내부에서 쓰는 방식)
