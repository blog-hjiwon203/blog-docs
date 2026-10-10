# 스텝 13b. 보완: 화면·명세 점검에서 나온 빈 곳

> 작업: T023a, T045a, T054a · 코드 브랜치: `step-13b-gaps` · 날짜: 2026-10-11 · 스텝 13 뒤 점검 결과 중 높음·중간 3개(지원 결정)

## 한눈에 보기

스텝 13을 올린 뒤, 완료로 체크된 작업을 명세 문장과 하나씩 대조했다. 오류도 실패한 테스트도 없는데 명세의 한 부분이 API나 화면에서 빠져 있는 곳이 나왔다. 그중 셋을 채웠다. 새 테이블·새 API는 없고, 이미 있던 칸·API·응답 값을 끝까지 이었다.

| 작업 | 빠져 있던 것 | 채운 것 | 핵심 파일 |
| --- | --- | --- | --- |
| T023a (BLOG-02) | 블로그 프로필 이미지: 요청 칸 없음, 응답은 늘 `null`, 설정 화면에 사진 칸 없음, 사이드바는 빈 동그라미 | `PATCH /api/blog`의 `profileImageId`(주인이 올린 이미지만, 아니면 400), `Blog`·사이드바 PROFILE의 `profileImageUrl`(썸네일), 설정 화면 "이미지 바꾸기"(고르면 올리고 미리 보기, 저장할 때 반영), 사이드바 사진 | `BlogService.updateInfo`, `image/application/ProfileImages`, `BlogQueryService`, `SidebarService`, `BlogSettingsPage.tsx`, `Sidebar.tsx`, `BlogInfoIntegrationTest` |
| T045a (BLOG-08) | 댓글·글 작성자 닉네임이 그냥 글자. 서버는 스텝 6부터 `primaryBlogAddress`를 줬다 | `AuthorName` 컴포넌트: 대표 블로그가 있으면 그 블로그로 가는 `<a>`, 없거나 볼 수 없으면 글자만 | `components/AuthorName.tsx`, `Comments.tsx`, `PostPage.tsx`, `CommentIntegrationTest`, `support/TestBlogs.createPrimary` |
| T054a (TAG-03) | `GET /api/tags`를 부르는 화면이 없음(사이드바는 사이드바 응답 안에서 받음) | 관리 → "카테고리·태그" 화면 아래 태그 표(이름 → 태그별 글 목록, 글 수, 주인이라 비공개 글도 셈), 메뉴 이름 바꿈 | `pages/manage/CategoriesPage.tsx`(`TagSection`), `ManagePage.tsx` |

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
```

## 이 스텝을 이해하려면 (읽는 순서)

| 순서 | 개념 문서 | 이 스텝에서 쓰인 곳 |
| --- | --- | --- |
| 1 | [49 완료의 정의와 요구사항 추적](./concepts/49-requirement-traceability.md) (새 문서) | 명세 문장을 항목으로 쪼개 API·화면·입구를 대조하는 법, 반쯤 된 기능이 숨는 자리(`null` 응답 칸, 번호 없는 "나중에", 부르지 않는 API), 세 작업의 화면 코드, 테스트 고정 데이터가 조건을 숨긴 일 |
| 2 | [38 회원정보 수정](./concepts/38-member-profile-update.md) 5.7 (보강) | 블로그 프로필 이미지: 회원 사진과 같은 IDOR 검사, 주소 만드는 부품(`ProfileImages`), 올리기와 저장을 나눈 이유와 고아 이미지 |
| 3 | (복습) [46 상태에 따라 갈 곳 정하기](./concepts/46-entry-routing-write-button.md) 3.3 | 다른 호스트로 가는 닉네임 링크는 `<a href>`, 같은 블로그의 태그 목록은 `<Link>` |
| 4 | (복습) [16 인가와 가시성](./concepts/16-authorization-visibility.md), [31 태그](./concepts/31-tags-many-to-many.md) | 볼 수 없는 대표 블로그면 링크가 없는 이유(서버가 판단), 태그 글 수가 보는 사람마다 다른 이유 |

## 막혔던 점

- **서버 버그처럼 보인 테스트 실패**: 댓글 작성자의 `primaryBlogAddress`를 확인하는 테스트를 더했더니 `expected:<td98c7bfea2> but was:<null>`. 화면 링크가 없던 원인이 서버였나 싶었지만, 테스트 도우미 `TestBlogs.create`가 **대표가 아닌** 블로그를 만드는 것이 원인이었다(서비스의 "첫 블로그는 대표" 규칙을 거치지 않는다). 서버는 맞게 `null`을 줬다. `create`의 뜻은 그대로 두고 `createPrimary`를 더했다([49](./concepts/49-requirement-traceability.md) 5.4).
- **확인 스크립트의 칸 이름**: 브라우저 확인용 글을 만들 때 저장 본문에 `tags`라고 써서(실제는 `tagNames`) 태그 표가 비어 나왔다. 서버는 모르는 칸을 무시한다. 화면 코드를 의심하기 전에 `GET /api/tags`를 직접 불러 데이터부터 확인했다.
- **zsh와 헤더 변수**: `H='-H X-Requested-With:...'` 같은 변수를 `curl $H`로 쓰면 zsh는 단어를 나누지 않아 헤더가 하나로 붙고, 서버가 403 `CSRF_REJECTED`를 줬다. bash 배열(`H=(-H "..." -H "...")`, `"${H[@]}"`)로 바꿨다.
- **올리기와 저장 사이**: 설정 화면은 사진을 고르면 바로 올리고 저장 때 블로그에 반영한다(목업의 두 단계). 올리는 중에 저장하면 새 번호 없이 저장되므로 그동안 저장 버튼을 막았다. 고르고 저장하지 않으면 이미지가 쓰이지 않은 채 남는다(아래 표).
- **화면은 실제 브라우저로 확인**: 8081 확인용 서버와 헤드리스 Chrome으로 회원 셋(갑: 주인, 을: 대표 블로그 있음, 병: 블로그 없음)을 만들어 (1) 설정에서 사진 고르기 → "저장을 눌러야…" → 저장 → 사이드바에 같은 썸네일(실제로 읽힘), (2) 글 상세에서 갑·을 닉네임은 각자 블로그 링크, 병은 글자, (3) 관리 → 카테고리·태그에 spring 2·jpa 1·secret 1(같은 API를 비회원이 부르면 spring 1·jpa 1). 확인용 회원(`b13-a-22029@example.com` 등, 비밀번호 `check1234`)·블로그(`b13a22029`, `b13b22029`)가 개발 DB에 남아 있다.

## 명세와 다르거나 아직 채우지 않은 것

| 항목 | 지금 | 언제 |
| --- | --- | --- |
| `PATCH /api/blog` 계약 | 칸은 처음부터 있었다. 규칙(주인이 올린 이미지만, 아니면 400)과 응답 `profileImageUrl`이 썸네일이라는 것을 API 명세에 적음 | 반영함 |
| 블로그 프로필 이미지 지우기 | 바꾸기만 된다. 안 보낸 칸과 `null`을 구분하지 못한다(회원 사진과 같음, [38](./concepts/38-member-profile-update.md) 확인 문제 2) | 필요하면 |
| 쓰이지 않는 이미지 정리 | 사진을 고르고 저장하지 않거나, 본문에 넣었다 지운 이미지는 행·파일이 남는다 | 백로그(예약 정리 작업) |
| 댓글·글 작성자 프로필 사진 | `MemberSummary.profileImageUrl`은 아직 늘 `null`이라 댓글 옆은 빈 동그라미 | 점검 목록에 더함(이번 범위 밖) |
| 태그 이름 변경·삭제(TAG-04) | 표만 있고 버튼 없음 | 백로그 |
| 점검의 낮은 항목 | 글 상세에서 공개 범위 바꾸기(목업 12번), `/admin` 입구, 글 상세 카테고리 링크, 글 관리 필터의 "예약" | 지원이 정하면 |

## 직접 해 보기

```bash
./mvnw test -Dtest='BlogInfoIntegrationTest,CommentIntegrationTest,TagIntegrationTest'
grep -rn "'/api/tags'" frontend/src        # 이제 CategoriesPage가 부른다
grep -rn ", null" src/main/java --include='*Response.java'   # 남은 null 응답 칸 찾기
```

화면: [49](./concepts/49-requirement-traceability.md) 7.3(사진 저장 → 사이드바, 닉네임 링크 두 경우, 태그 표).
