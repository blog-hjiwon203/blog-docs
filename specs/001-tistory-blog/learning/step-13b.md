# 스텝 13b. 보완: 화면·명세 점검에서 나온 빈 곳

> 작업: T023a, T045a, T054a, T055d, T034a, T033a, T030a, T067a, T051a, T055e, T008a · 코드 브랜치: `step-13b-gaps` · 날짜: 2026-10-11 · 스텝 13 뒤 점검의 높음·중간 3개, 이어서 "스텝 14 전에 기능 명세 기준으로 화면에 연결 안 된 것을 전부 찾아 고친다"(지원 결정)는 전체 점검에서 나온 것

## 한눈에 보기

스텝 13을 올린 뒤, 완료로 체크된 작업을 명세 문장과 하나씩 대조했다. 오류도 실패한 테스트도 없는데 명세의 한 부분이 API나 화면에서 빠져 있는 곳이 나왔다. 먼저 높음·중간 셋(T023a·T045a·T054a)을 채워 PR을 올렸다. 지원이 "스텝 14 전에 전부"라고 정해 서버 API 45개와 `[X]` 작업의 명세 문장 전체를 다시 대조했다([49](./concepts/49-requirement-traceability.md) 5.7). 거기서 나온 여덟 가지(T055d~T008a)와 T023a에서 빠뜨린 자리 하나를 더 고쳤다. 새 테이블·새 API는 없고, 이미 있던 칸·API·응답 값을 끝까지 이었다. 백로그로 미룬 기능(비밀댓글, 구독, 태그 이름 변경, 꾸미기·이사·삭제, 서비스 관리 기능 본체)은 빈 곳으로 세지 않았다.

| 작업 | 빠져 있던 것 | 채운 것 | 핵심 파일 |
| --- | --- | --- | --- |
| T023a (BLOG-02) | 블로그 프로필 이미지: 요청 칸 없음, 응답은 늘 `null`, 설정 화면에 사진 칸 없음, 사이드바는 빈 동그라미 | `PATCH /api/blog`의 `profileImageId`(주인이 올린 이미지만, 아니면 400), `Blog`·사이드바 PROFILE의 `profileImageUrl`(썸네일), 설정 화면 "이미지 바꾸기"(고르면 올리고 미리 보기, 저장할 때 반영), 사이드바 사진, 블로그 메인 위쪽 프로필 상자 사진 | `BlogService.updateInfo`, `image/application/ProfileImages`, `BlogQueryService`, `SidebarService`, `BlogSettingsPage.tsx`, `Sidebar.tsx`, `BlogMainPage.tsx`, `BlogInfoIntegrationTest` |
| T045a (BLOG-08) | 댓글·글 작성자 닉네임이 그냥 글자. 서버는 스텝 6부터 `primaryBlogAddress`를 줬다 | `AuthorName` 컴포넌트: 대표 블로그가 있으면 그 블로그로 가는 `<a>`, 없거나 볼 수 없으면 글자만 | `components/AuthorName.tsx`, `Comments.tsx`, `PostPage.tsx`, `CommentIntegrationTest`, `support/TestBlogs.createPrimary` |
| T054a (TAG-03) | `GET /api/tags`를 부르는 화면이 없음(사이드바는 사이드바 응답 안에서 받음) | 관리 → "카테고리·태그" 화면 아래 태그 표(이름 → 태그별 글 목록, 글 수, 주인이라 비공개 글도 셈), 메뉴 이름 바꿈 | `pages/manage/CategoriesPage.tsx`(`TagSection`), `ManagePage.tsx` |
| T055d (AUTH-05) | 글쓴이·댓글 작성자·블로그 주인의 사진: `MemberSummaryResponse`가 `profileImageUrl`에 `null`을 써 둠 | 썸네일 주소로 채움(댓글은 작성자 사진을 `findAllById` 한 번), 댓글 옆 동그라미에 사진 | `ProfileImages.thumbnailUrls`, `CommentService`, `PostReadService`, `BlogQueryService`, `MemberSummaryResponse`, `Comments.tsx`, `CommentIntegrationTest` |
| T034a (POST-06) | 글 상세에서 공개 범위 바꾸기(목업 post-detail 12번). API는 있는데 부르는 화면이 없음 | 주인에게 "공개/비공개" 고르기, 바꾸면 `PATCH /api/posts/{id}/visibility` | `PostPage.tsx` |
| T033a (POST-03) | 글 상세 삭제가 실패해도 아무 반응 없음 | 오류 문장을 보이고 화면에 남음 | `PostPage.tsx` |
| T030a (CAT-02) | 글 상세·목록·글 관리의 카테고리 이름이 글자 | 블로그 쪽은 `/category/{id}`(미분류 `/category/0`), 글 관리는 그 카테고리로 거르기 | `PostPage.tsx`, `PostItem.tsx`, `ManagePostsPage.tsx` |
| T067a (MNG-01) | 상태 필터에 백로그 기능 "예약" | 뺌 | `ManagePostsPage.tsx` |
| T051a (ADMIN-01) | `/admin`으로 가는 입구 없음 | 서비스 관리자에게 세 머리글의 "서비스 관리" | `PlatformHeader.tsx`, `BlogHeader.tsx`, `ManagePage.tsx` |
| T055e (BLOG-08) | "내 블로그"가 플랫폼 머리글에만 | 블로그·관리 머리글에도(내 대표 블로그가 아닌 곳에서) | `BlogHeader.tsx`, `ManagePage.tsx` |
| T008a (ADMIN-02) | 로그인한 채로 정지되면 사유 없이 로그아웃된 것처럼 보임, 블로그 글은 500 화면 | 머리글 아래 정지 사유·기한, 로그인 화면으로 보내지 않음, api 클라이언트가 사유를 적어 두고 읽기 요청은 비회원으로 다시 받음 | `api/client.ts`, `app/useMe.ts`, `components/SuspensionNotice.tsx`, `client.test.ts`, `useMe.test.ts` |

## 요청 흐름

```
[T023a] 설정 화면에서 사진 고르기 → POST /api/images → { id: 57, thumbnailUrl: "/uploads/t_….png" } (미리 보기만)
        저장 → PATCH /api/blog { name, description, profileImageId: 57 }
             → BlogOwnerGuard(주인인가) → 입력 검사 → image 57의 uploader_id == 나? → blog.profile_image_id = 57
             → BlogQueryService.detail → ProfileImages.thumbnailUrl(57) → Blog.profileImageUrl
        블로그 홈 → GET /api/blog/sidebar → SidebarService → PROFILE.data.profileImageUrl → <img class="avatar lg">

[T045a] GET /api/posts/20/comments → content[].author = { nickname, primaryBlogAddress }
        (서버 PrimaryBlogAddresses: 대표 블로그가 없거나 이용 제한·주인 정지면 null)
        → AuthorName: 주소 있으면 <a href="http://{주소}.blog.test:8080/">닉네임</a>, 없으면 <span>

[T054a] 관리 → 카테고리·태그 → GET /api/tags (보는 사람 = 주인 → 비공개 글도 셈) → 표

[T055d] GET /api/posts/20/comments → CommentService: 작성자들 → PrimaryBlogAddresses.of(한 번) + ProfileImages.thumbnailUrls(한 번)
        → content[].author.profileImageUrl → <img class="avatar">

[T034a] 글 상세(주인) "비공개" 고르기 → PATCH /api/posts/22/visibility { visibility: PRIVATE } → 204 → 화면 값만 바꿈
        비회원 GET /api/posts/22 → 404

[T008a] 정지된 회원이 글 상세 열기 ─┬─ GET /api/me ──────── 403 MEMBER_SUSPENDED (쿠키 삭제) → useMe: 비회원 + 사유
                                  ├─ GET /api/blog ────── 403 → api(): 사유 기억, 다시 보냄 → 200(비회원)
                                  └─ GET /api/posts/20 ── 403 → 같음 → 200
        → 머리글 아래 "이용이 정지된 계정입니다 / 정지 기한: …"
```

## 이 스텝을 이해하려면 (읽는 순서)

| 순서 | 개념 문서 | 이 스텝에서 쓰인 곳 |
| --- | --- | --- |
| 1 | [49 완료의 정의와 요구사항 추적](./concepts/49-requirement-traceability.md) (새 문서) | 명세 문장을 항목으로 쪼개 API·화면·입구를 대조하는 법, 반쯤 된 기능이 숨는 자리(`null` 응답 칸, 번호 없는 "나중에", 부르지 않는 API), 세 작업의 화면 코드, 테스트 고정 데이터가 조건을 숨긴 일, 5.7 두 번째 전체 점검(API 대조 스크립트, 영역별 명세 대조, 결과 표, `Map.of().get(null)`) |
| 2 | [19 React Router와 API 클라이언트](./concepts/19-react-router-api-client.md) 5.8 (보강) | 동시에 나간 요청이 같은 상태 변화(정지 → 쿠키 삭제)를 만날 때: 한 곳에 기억하고 읽기만 다시 보내기, `/api/me`는 다시 보내지 않는 이유, 모듈 변수와 테스트 순서 |
| 3 | [38 회원정보 수정](./concepts/38-member-profile-update.md) 5.7 (보강) | 블로그 프로필 이미지: 회원 사진과 같은 IDOR 검사, 주소 만드는 부품(`ProfileImages`), 올리기와 저장을 나눈 이유와 고아 이미지 |
| 4 | (복습) [46 상태에 따라 갈 곳 정하기](./concepts/46-entry-routing-write-button.md) 3.3 | 다른 호스트로 가는 닉네임·"내 블로그"·"서비스 관리"는 `<a href>`, 같은 블로그의 태그·카테고리 목록은 `<Link>` |
| 5 | (복습) [16 인가와 가시성](./concepts/16-authorization-visibility.md), [31 태그](./concepts/31-tags-many-to-many.md), [48 대표 이미지](./concepts/48-representative-image.md) | 볼 수 없는 대표 블로그면 링크가 없는 이유(서버가 판단), 태그 글 수가 보는 사람마다 다른 이유, 한 페이지 이미지를 쿼리 한 번으로(N+1) |

## 막혔던 점

- **서버 버그처럼 보인 테스트 실패**: 댓글 작성자의 `primaryBlogAddress`를 확인하는 테스트를 더했더니 `expected:<td98c7bfea2> but was:<null>`. 화면 링크가 없던 원인이 서버였나 싶었지만, 테스트 도우미 `TestBlogs.create`가 **대표가 아닌** 블로그를 만드는 것이 원인이었다(서비스의 "첫 블로그는 대표" 규칙을 거치지 않는다). 서버는 맞게 `null`을 줬다. `create`의 뜻은 그대로 두고 `createPrimary`를 더했다([49](./concepts/49-requirement-traceability.md) 5.4).
- **확인 스크립트의 칸 이름**: 브라우저 확인용 글을 만들 때 저장 본문에 `tags`라고 써서(실제는 `tagNames`) 태그 표가 비어 나왔다. 서버는 모르는 칸을 무시한다. 화면 코드를 의심하기 전에 `GET /api/tags`를 직접 불러 데이터부터 확인했다.
- **zsh와 헤더 변수**: `H='-H X-Requested-With:...'` 같은 변수를 `curl $H`로 쓰면 zsh는 단어를 나누지 않아 헤더가 하나로 붙고, 서버가 403 `CSRF_REJECTED`를 줬다. bash 배열(`H=(-H "..." -H "...")`, `"${H[@]}"`)로 바꿨다.
- **올리기와 저장 사이**: 설정 화면은 사진을 고르면 바로 올리고 저장 때 블로그에 반영한다(목업의 두 단계). 올리는 중에 저장하면 새 번호 없이 저장되므로 그동안 저장 버튼을 막았다. 고르고 저장하지 않으면 이미지가 쓰이지 않은 채 남는다(아래 표).
- **사진이 보이는 곳을 하나 빠뜨림**: 사이드바에만 사진을 넣고, 블로그 메인 위쪽 프로필 상자(`BlogMainPage.tsx`의 `BlogProfile`)는 빈 동그라미로 남겼다. PR을 올린 뒤 전체 점검에서 찾아 고쳤다. 같은 값(`profileImageUrl`)을 그리는 곳을 `grep -rn 'className="avatar' frontend/src`로 모두 찾아봤어야 했다([49](./concepts/49-requirement-traceability.md) 4.2).
- **"전부"는 손으로 떠올려서는 안 된다**: 첫 점검은 생각나는 화면을 본 것이라 낮은 항목 넷만 적었다. 두 번째에는 서버 API 목록을 기계로 뽑아 화면 호출과 대조하고, `[X]` 작업의 기능 코드를 모두 뽑아 세 영역으로 나눠 명세 문장을 대조했다. 그래서 작성자 사진(`null` 응답 칸), 삭제 실패 무반응, 목록의 카테고리 링크, 블로그 머리글의 "내 블로그", 로그인 중 정지 안내가 더 나왔다([49](./concepts/49-requirement-traceability.md) 5.7).
- **고친 뒤 눌러 보다 찾은 500 (T008a)**: 정지 안내만 띄우면 될 줄 알았는데, 정지 회원으로 글 상세를 열어 보니 500 화면이었다. 글 상세가 API 넷을 동시에 부르고, 첫 응답이 쿠키를 지워도 이미 떠난 요청은 옛 쿠키를 실어 모두 403이었다. 점검 표에는 "사유가 안 보인다"만 있었다. 브라우저로 직접 정지 회원이 되어 열어 봐서 찾았다([19](./concepts/19-react-router-api-client.md) 5.8).
- **`Map.of().get(null)`**: 사진이 없는 회원의 사진 번호는 `null`이고, 작성자 사진 맵에서 `get(null)`로 꺼낸다. 처음 쓴 코드는 빈 경우 `Map.of()`를 돌려줬는데, 불변 맵은 `get(null)`에 `NullPointerException`이다. 테스트를 돌리기 전에 알아채 `HashMap`으로 돌려준다([49](./concepts/49-requirement-traceability.md) 5.7).
- **화면 확인 스크립트에서 select 바꾸기**: 헤드리스 Chrome에서 `select.value = 'PRIVATE'`만 하면 React가 바뀐 줄 모른다(React는 값 설정을 가로채 자기 상태와 비교한다). `HTMLSelectElement.prototype`의 원래 `value` 설정자로 값을 넣고 `change` 이벤트를 보내야 `onChange`가 불린다.
- **화면은 실제 브라우저로 확인**: 8081 확인용 서버와 헤드리스 Chrome으로 확인했다.
  - 처음 세 작업: (1) 설정에서 사진 고르기 → "저장을 눌러야…" → 저장 → 사이드바에 같은 썸네일(실제로 읽힘), (2) 글 상세에서 갑·을 닉네임은 각자 블로그 링크, 병은 글자, (3) 관리 → 카테고리·태그에 spring 2·jpa 1·secret 1(같은 API를 비회원이 부르면 spring 1·jpa 1).
  - 전체 점검 뒤, 회원 넷(갑 주인, 을 사진 있음, 병 정지, 정 관리자)으로: (4) 글 상세 카테고리 링크 `/category/12`, 공개 범위 "비공개" → 비회원 404, 새로고침해도 비공개, (5) 댓글 옆 을의 사진, 병은 빈 동그라미, (6) 이미 지운 글을 화면에서 삭제 → "요청한 내용을 찾을 수 없습니다"를 보이고 그 글에 남음, (7) 목록 카테고리 `개발→/category/12`·`미분류→/category/0`, 글 관리 상태 필터에 예약 없음, 카테고리 "개발"을 누르면 `?categoryId=12`로 거름, (8) 을이 갑의 블로그에서 "내 블로그→을의 블로그", 자기 블로그에서는 없음, (9) 정에게 플랫폼·블로그 머리글의 "서비스 관리" → `/admin`, (10) 병(로그인한 채로 정지)이 글 상세·블로그 메인·홈·관리·마이페이지를 열면 다섯 곳 모두 정지 사유·기한, 글은 비회원처럼 읽힘.
  - 확인용 회원(`b13-a-22029@example.com`~`b13-d-22029@example.com`, 비밀번호 `check1234`)·블로그(`b13a22029`, `b13b22029`)가 개발 DB에 남아 있다. 병(`b13-c-…`)은 SQL로 7일 정지, 정(`b13-d-…`)은 `role='ADMIN'`으로 바꿔 두었다. 글 21은 지웠고 글 22는 비공개다.

## 명세와 다르거나 아직 채우지 않은 것

| 항목 | 지금 | 언제 |
| --- | --- | --- |
| `PATCH /api/blog` 계약 | 칸은 처음부터 있었다. 규칙(주인이 올린 이미지만, 아니면 400)과 응답 `profileImageUrl`이 썸네일이라는 것을 API 명세에 적음 | 반영함 |
| `MemberSummary.profileImageUrl`, 정지 응답과 동시 요청 | API 명세에 "썸네일 주소", "읽기 요청은 비회원으로 다시 받는다"를 적음 | 반영함 |
| 블로그 프로필 이미지 지우기 | 바꾸기만 된다. 안 보낸 칸과 `null`을 구분하지 못한다(회원 사진과 같음, [38](./concepts/38-member-profile-update.md) 확인 문제 2) | 필요하면 |
| 쓰이지 않는 이미지 정리 | 사진을 고르고 저장하지 않거나, 본문에 넣었다 지운 이미지는 행·파일이 남는다 | 백로그(예약 정리 작업) |
| 태그 이름 변경·삭제(TAG-04) | 표만 있고 버튼 없음 | 백로그 |
| 글 관리의 공개 범위 거르기 | 서버는 `visibility` 조건을 받지만 화면에 칸이 없다. 명세(MNG-01 "상태·카테고리 필터")와 목업에 없어 빈 곳이 아니다 | 그대로 |
| 수정 화면의 구독자 공개 글 | 구독자 공개 글을 수정 화면에서 열면 "공개"로 들어간다. 지금은 구독자 공개 글을 만들 수 없어 생기지 않는다 | 구독(SUB) 스텝에서 |
| 서비스 관리 화면 | 입구만 생겼고 화면은 "뒤 스텝에서" 안내뿐(ADMIN-02 회원 관리 등 본체는 백로그) | 백로그 |

## 직접 해 보기

```bash
./mvnw test -Dtest='BlogInfoIntegrationTest,CommentIntegrationTest,TagIntegrationTest'
cd frontend && npx vitest run src/api/client.test.ts src/app/useMe.test.ts && cd ..
grep -rn "'/api/tags'" frontend/src        # 이제 CategoriesPage가 부른다
grep -rn ", null" src/main/java --include='*Response.java'   # 남은 null 응답 칸 찾기
```

화면: [49](./concepts/49-requirement-traceability.md) 7.3(사진 저장 → 사이드바, 닉네임 링크 두 경우, 태그 표). 전체 점검 스크립트(서버 API → 화면 호출 대조)는 [49](./concepts/49-requirement-traceability.md) 5.7 (가).

정지 안내는 개발 DB에서 내 확인용 회원을 잠깐 정지해 본다(끝나면 되돌린다).

```bash
docker exec blog-mysql mysql -ublog -pblog blog -e \
  "UPDATE member SET status='SUSPENDED', suspended_until=DATE_ADD(NOW(), INTERVAL 1 DAY) WHERE email='내확인용@example.com'"
# 로그인한 채로 아무 블로그 글을 연다 → 머리글 아래 정지 사유·기한, 글은 그대로 보임
docker exec blog-mysql mysql -ublog -pblog blog -e \
  "UPDATE member SET status='ACTIVE', suspended_until=NULL WHERE email='내확인용@example.com'"
```
