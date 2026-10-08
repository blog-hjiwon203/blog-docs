# 스텝 7. 이미지·태그·공감·검색·답글

> 작업: T036, T037, T038, T039, T046, T047, T048, T049, T069 · 코드 브랜치: `step-7-media-tags-search` · 날짜: 2026-10-09

## 한눈에 보기

글을 풍성하게 하는 기능들을 만들었다. 에디터에서 사진을 올려 본문에 넣고, 글에 태그를 달고, 남의 글에 공감하고, 블로그 안에서 검색하고, 댓글에 답글을 단다. 목록에는 본문 첫 사진의 썸네일이 붙는다.

| 기능 | API | 핵심 파일 |
| --- | --- | --- |
| 이미지 올리기 (POST-05) | `POST /api/images` (multipart `file`) → `{ id, url, thumbnailUrl }`, 파일은 `/uploads/**` | `image/application/ImageService`, `image/domain/ImageType`, `global/config/WebConfig`, `UploadProperties` |
| 목록 썸네일 | 글 목록·홈 응답의 `thumbnailUrl` | `image/application/PostThumbnails` |
| 에디터 사진 버튼 (T037) | — | `frontend/src/components/editor/Editor.tsx`, `api/client.ts`의 `uploadFile` |
| 태그 (TAG-01) | 글 발행·수정 요청의 `tagNames`, 상세의 `tags` | `tag/domain/Tag`, `TagNames`, `tag/application/TagService`, `Post.tags` |
| 태그별 목록 (TAG-02) | `GET /api/posts?tag={이름}`, 화면 `/tag/{이름}` | `post/application/PostQueryService.taggedWith`, `BlogMainPage` |
| 공감 (SOC-01) | `PUT`·`DELETE /api/posts/{id}/like` → `{ liked, likeCount }`, 상세의 `viewer.liked` | `reaction/application/LikeService`, `reaction/domain/PostLikeRepository` |
| 블로그 안 검색 (SRCH-01) | `GET /api/search?q=&page=` (블로그 주소에서) | `search/application/SearchService`, Flyway `V3__post_content_text.sql` |
| 답글 (CMT-05) | 댓글 쓰기의 `parentId`, 목록의 `replies`, `state: DELETED` | `comment/application/CommentService`, `components/Comments.tsx`, `commentList.ts` |
| 화면 | 공감 버튼, 검색 상자·결과, 태그 입력·칩, 답글 | `LikeButton`, `BlogHeader`, `pages/search/BlogSearchPage`, `editor/TagInput`, `PostItem` |
| 테스트 (T049) | — | `LikeIntegrationTest`, `CountConsistencyIntegrationTest`, `ImageUploadIntegrationTest`, `TagIntegrationTest`, `SearchIntegrationTest`, `ReplyIntegrationTest` |

**지원이 정한 것 (2026-10-09)**

- 이미지 처리: Thumbnailator로 줄이고 TwelveMonkeys로 WebP를 읽는다. jpg·png는 긴 변 1920px로 줄이고 EXIF 방향을 반영한다. gif·webp는 움직임을 지키려고 원본 그대로 두고, 썸네일만 만든다(research R-15).
- 검색: 본문 HTML이 아니라 **태그를 뺀 글자만 담은 칸** `post.content_text`를 새로 두고 거기서 찾는다(ERD 버전 79, Flyway V3, research R-16).

## 요청 흐름

### 사진 넣은 글을 발행하기까지

```
alpha.blog.test/manage/write       PostWritePage + Editor
  [이미지] 버튼 → 사진 두 장 고름
  POST /api/images (사진 1)          ImageService.upload
                                       비었나(400) → 10MB 넘나(IMAGE_TOO_LARGE)
                                       → 앞 몇 바이트(매직 넘버)로 형식 판단, 아니면 UNSUPPORTED_IMAGE
                                       → jpg·png: 긴 변 1920px로, EXIF 방향 반영 / gif·webp: 원본 그대로
                                       → 400px 썸네일 t_{uuid}.jpg|png
                                       → image 행 저장 (path = /uploads/{uuid}.png)
                                     ← 201 { url, thumbnailUrl }
  에디터가 <img src="/uploads/..."> 를 선택 뒤에 넣음
  POST /api/images (사진 2)          (같음, 고른 순서대로 하나씩)
  태그 칸에 "바다, 산" → 칩 두 개
  [발행]
  POST /api/posts  { contentHtml, tagNames: ["바다","산"], ... }
                                     PostService: 본문 정화 → PostBody(html, 글자만, 요약)
                                       TagNames.normalize → TagService.resolve(없는 태그는 만듦)
                                       → post + post_tag 저장
```

### 다른 사람이 읽고 공감·검색·답글

```
alpha.blog.test/                   BlogMainPage
  GET /api/posts?page=1              글 10개 + PostThumbnails(본문 첫 <img>의 썸네일, 쿼리 한 번)

alpha.blog.test/12                 PostPage
  GET /api/posts/12                  tags, likeCount, viewer.liked(LikeService.likes)
  [♡ 공감] 클릭                      LikeButton: 화면부터 ♥ 1 (낙관적 갱신)
  PUT /api/posts/12/like             LikeService.like
                                       readable(404·403) → 비회원 401
                                       → 글 행 잠금(lockById, 데드락 예방)
                                       → INSERT IGNORE post_like (이미 있으면 0행)
                                       → 1행 넣었을 때만 like_count + 1
                                       → 잠금 읽기로 지금 공감 수
                                     ← { liked: true, likeCount: 1 } → 화면을 이 값으로 맞춤

  [답글] → POST /api/posts/12/comments { content, parentId: 31 }
                                     CommentService.write: 부모가 같은 글의 지우지 않은 최상위 댓글인가(아니면 400)

  검색 상자 "고양이" → /search?q=고양이   BlogSearchPage
  GET /api/search?q=고양이&page=1    SearchService: 볼 수 있는 글 AND
                                       (제목 LIKE OR content_text LIKE OR EXISTS 태그 이름 LIKE)

  #바다 칩 → /tag/바다               BlogMainPage
  GET /api/posts?tag=바다            PostQueryService.taggedWith (없는 태그 404)
```

## 이 스텝을 이해하려면 (읽는 순서)

| 순서 | 개념 문서 | 이 스텝에서 그 개념이 쓰인 곳 |
| --- | --- | --- |
| 1 | [30 이미지 업로드와 처리](./concepts/30-image-upload.md) | multipart, 매직 넘버, Thumbnailator, `/uploads/**` 내보내기, 목록 썸네일, 에디터 사진 버튼 |
| 2 | [31 태그와 다대다 관계](./concepts/31-tags-many-to-many.md) | `@ManyToMany`와 `post_tag`, 태그 이름 정리 규칙, 태그별 목록, 태그 입력 칸 |
| 3 | [32 블로그 안 검색: LIKE와 비정규화 칸](./concepts/32-search-like.md) | `content_text`와 V3 마이그레이션, LIKE 이스케이프, EXISTS, 검색 화면 |
| 4 | [33 격리 수준, 스냅샷, 데드락](./concepts/33-isolation-deadlock.md) | 공감·댓글의 `lockById`, 잠금 읽기 `findLikeCount`, 동시성 테스트 |
| 5 | [29 댓글 설계](./concepts/29-comments-design.md)의 5.11 | 답글 한 단계, 삭제된 댓글 자리, 부모 묶음 + 답글 한 번에 |
| 6 | [25 React 폼과 데이터 불러오기](./concepts/25-react-forms-data.md)의 5.12 | 낙관적 갱신, key 중복 버그, 검색어를 주소에, `FormData` |
| 7 | [26 WYSIWYG 에디터와 Tiptap](./concepts/26-wysiwyg-editor-tiptap.md)의 5.10 | 이미지 노드, 선택이 노드를 감쌀 때의 삽입 |

먼저 알고 있으면 좋은 문서: [23 트랜잭션과 동시성](./concepts/23-transactions-locking.md)(33의 바탕), [27 소프트 삭제와 일괄 수정](./concepts/27-soft-delete-bulk-update.md)(공감 수도 댓글 수와 같은 원자적 UPDATE), [06 JPA 엔티티 매핑](./concepts/06-jpa-entity-mapping.md)(Specification, N+1), [03 Flyway](./concepts/03-flyway-migration.md)(V3).

## 막혔던 점

- **같은 글에 동시에 공감하면 데드락**: 여러 회원이 동시에 공감하는 테스트에서 `CannotAcquireLockException`이 났다. `post_like`를 넣을 때 외래 키 검사가 글 행에 공유 잠금을 걸고, 이어서 `like_count`를 고치려면 배타 잠금이 필요한데, 두 트랜잭션이 서로의 공유 잠금을 기다렸다. 공감·댓글 쓰기·지우기의 맨 앞에서 글 행을 먼저 배타 잠금(`lockById`)하게 바꿨다([33](./concepts/33-isolation-deadlock.md)).
- **동시에 누르면 응답의 공감 수가 0**: 최종 수는 1로 맞는데, 같은 회원의 동시 요청 5개 중 늦게 처리된 4개가 `likeCount: 0`을 돌려줬다. curl로 동시에 보내 보고서야 알았다. 잠금을 기다리기 전에 이미 글을 읽어(`readable`) 그때의 스냅샷이 정해졌고, 잠금 뒤의 평범한 SELECT가 그 옛 스냅샷을 읽은 것이다(MySQL 기본 REPEATABLE READ). 공감 수 조회를 잠금 읽기(`FOR UPDATE`)로 바꿨다. 테스트에 "모든 응답이 1"을 더해 고치기 전에 실패하는 것을 먼저 확인했다([33](./concepts/33-isolation-deadlock.md)).
- **공감 버튼이 두 개**: 헤드리스 Chrome 확인에서 글 상세에 공감 버튼이 두 개 그려졌다. `LikeButton`과 `Comments`에 같은 `key={post.id}`를 줘서, 댓글 수가 바뀌어 다시 그릴 때 React가 형제를 구분하지 못했다([25](./concepts/25-react-forms-data.md) 5.12).
- **사진 두 장을 골랐는데 한 장만**: 방금 넣은 이미지가 선택된 상태에서 다음 `setImage`가 그것을 바꿨다. 선택의 끝 뒤에 넣도록(`insertContentAt`) 고쳤다([26](./concepts/26-wysiwyg-editor-tiptap.md) 5.10).
- **"바다,산"을 붙여 넣으면 태그 하나**: 쉼표를 키 누름(keydown)에서만 처리해서 붙여 넣은 쉼표는 나누지 못했다. 입력값이 바뀔 때 쉼표로 나누게 하고, 규칙을 `tagNames.ts` 순수 함수로 떼어 Vitest를 붙였다([31](./concepts/31-tags-many-to-many.md)).
- **악센트만 다른 태그(Café·cafe)와 동시에 만든 같은 새 태그가 500**: 학습 문서를 쓰다 의심이 들어 테스트로 확인했다. DB 정렬 규칙은 악센트까지 무시하는데 Java는 `toLowerCase`로만 비교했고, "없으면 저장"을 동시에 하면 늦은 쪽이 UNIQUE에 걸렸다. Java 비교를 DB처럼(`Collator` PRIMARY) 바꾸고, 새 태그는 `INSERT IGNORE` 뒤 공유 잠금 읽기로 가져온다. 처음엔 `FOR UPDATE`로 읽어 데드락이 나서 `FOR SHARE`로 바꿨다([31](./concepts/31-tags-many-to-many.md)).
- **`/tag/node.js`를 바로 열면 404**: 서버의 화면 주소 처리가 점을 확장자로 봤다. 태그 주소만 점을 허용하게 따로 받았다.
- **본문 HTML로 검색하면 태그 이름이 걸림**: `content_html LIKE '%strong%'`이면 `<strong>`을 쓴 모든 글이 나온다. 글자만 담은 칸이 필요해 지원에게 물어 `content_text`를 더했다. 이미 적용된 V1은 고치지 않고 V3로 칸 추가 → 기존 글 채우기 → NOT NULL 순서로 바꿨다([32](./concepts/32-search-like.md)).
- **테스트가 올린 파일이 개발용 uploads 폴더에 섞이지 않게**: 통합 테스트에서는 `app.upload.dir`을 임시 폴더로 바꿨다(`IntegrationTestSupport`).
- **지원이 8080에 띄운 서버**: 끄지 않고 확인용 서버를 8081로 따로 띄웠다(스텝 5·6과 같음).

## 명세와 다르거나 아직 채우지 않은 것

| 항목 | 지금 | 언제 |
| --- | --- | --- |
| `post.content_text` 칸 | 새로 더함(ERD v79, V3). data-model·research R-16 반영 | 지원 결정 |
| 썸네일 형식 | jpg 원본은 jpg, 그 밖은 png(contracts 예시의 webp가 아님). 예시를 jpg로 고침 | research R-15 |
| 대표 이미지 고르기 (POST-07) | `thumbnailImageId`를 보내면 400. 목록 썸네일은 본문 첫 이미지 | 백로그 |
| 검색 | 블로그 주소에서만(`/api/search`). 서비스 전체 검색은 없음. LIKE라 글이 많아지면 느려짐 | 전문 검색은 필요할 때 |
| 쓰지 않는 이미지·태그 정리 | 올렸지만 본문에 안 쓴 이미지 파일, 글이 없는 태그가 남는다 | 정리 작업 스텝 |
| 사이드바 태그 목록 | 없음 | 스텝 8 |
| 태그 이름의 `/` | `a/b` 태그는 주소가 `%2F`가 되어 Spring Security 방화벽이 태그 목록 화면을 거절한다 | 지원 결정 필요 |

## 직접 해 보기

```bash
./mvnw test -Dtest='ImageUploadIntegrationTest,PostThumbnailsTest,TagIntegrationTest,LikeIntegrationTest,CountConsistencyIntegrationTest,SearchIntegrationTest,ReplyIntegrationTest'
cd frontend && npm test
```

브라우저로 (quickstart 3, 공감·검색·답글):

1. `./scripts/build-frontend.sh && ./mvnw spring-boot:run`
2. A로 로그인해 `http://{A주소}.blog.test:8080/manage/write`에서 [이미지]로 사진 두 장을 한 번에 고른다. 고른 순서대로 들어가는지 본다. 태그 칸에 `바다, 산`을 붙여 넣고 발행한다.
3. 블로그 메인 목록에 썸네일이 보이는지, 글 상세의 `#바다`를 누르면 `/tag/바다` 목록이 나오는지 본다.
4. B로 로그인해 그 글의 공감을 빠르게 여러 번 누른다. 새로고침해도 공감 수가 0 또는 1이다.
5. 머리글 검색 상자에 본문 낱말을 넣는다. 결과 주소(`/search?q=...`)를 시크릿 창에 붙여 넣어도 같은 결과(비공개 글 제외)인지 본다.
6. B가 댓글을 달고 A가 답글을 단 뒤, B가 자기 댓글을 지운다. "삭제된 댓글입니다" 아래에 답글이 남는다.

```bash
# 화면 없이 (bash). A의 주소가 alpha, 쿠키 파일 jarA·jarB가 있다고 할 때
R="--resolve alpha.blog.test:8080:127.0.0.1"; H="-H X-Requested-With:XMLHttpRequest"
curl -s $R $H -b jarA -F file=@photo.jpg alpha.blog.test:8080/api/images            # 201 {url, thumbnailUrl}
echo hello > fake.png; curl -s $R $H -b jarA -F file=@fake.png alpha.blog.test:8080/api/images   # 400 UNSUPPORTED_IMAGE
for i in 1 2 3 4 5; do curl -s $R $H -b jarB -X PUT alpha.blog.test:8080/api/posts/{글 id}/like & done; wait   # 모두 likeCount 1
curl -s $R -G alpha.blog.test:8080/api/search --data-urlencode 'q=%'                  # % 글자 그대로 찾음(전부가 아님)
curl -s $R -G alpha.blog.test:8080/api/posts --data-urlencode 'tag=없는태그' -o /dev/null -w '%{http_code}\n'   # 404
```

## 더 공부할 거리

- MySQL 전문 검색(`FULLTEXT`와 한국어용 ngram 파서), 검색 엔진(Elasticsearch·OpenSearch)이 필요해지는 때
- 이미지 저장을 서버 폴더 대신 객체 저장소(S3 같은 것)와 CDN으로 옮길 때 바뀌는 것
- 올렸지만 쓰지 않은 파일 정리(고아 파일), 글이 없는 태그 정리를 언제·어떻게 할지
- 격리 수준 READ COMMITTED와 REPEATABLE READ의 차이가 다른 기능(조회수, 인기 글)에 주는 영향
