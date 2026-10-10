# 스텝 19. 블로그 꾸미기·이사·삭제, 회원 탈퇴

> 작업: T105, T086, T087, T106, T107, T108 · 코드 브랜치: `step-19-blog`(스텝 18 브랜치에서 이어 만듦) · 날짜: 2026-10-11 · 백로그를 크게 묶은 다섯 스텝 중 넷째(2026-10-11 지원 결정)

## 한눈에 보기

주인이 블로그 모양(스킨·포인트 색·목록 형태)과 사이드바를 고르고, 글을 내 다른 블로그로 옮기고, 블로그를 닫고, 회원은 서비스를 떠날 수 있다. 옛 링크(옮긴 글, 이사한 블로그)는 계속 새 주소로 이어진다. 테이블 칸(`skin`, `list_layout`, `accent_color`, `moved_to_blog_id`, `blog_sidebar_module`, `withdrawn_at`)과 "옮긴 글은 301"이라는 판단은 스텝 1·2에 이미 있었다.

| 작업 | 만든 것 | 핵심 파일 |
| --- | --- | --- |
| T105 꾸미기 (BLOG-05) | `PATCH /api/blog`의 `skin`(BASIC·MAGAZINE·NOTE)·`listLayout`·`accentColor`(모르는 값 400). 화면: 블로그 설정 "꾸미기", 모든 블로그 화면에 스킨·포인트 색, 썸네일 목록 | `Blog.changeDesign`, `Skin`, `BlogService.update`, `app/blogTheme.ts`, `useBlog`, `PostCard`, `index.css` |
| T086 사이드바 모듈 (BLOG-04, BLOG-05) | `blog_sidebar_module` 엔티티, 개설 때 8행(새 3종 숨김), 옛 블로그는 V4 마이그레이션으로 채움, 사이드바를 순서·표시대로, 방문자 수·인기 글 5·구독 데이터, `GET`·`PUT /api/blog/sidebar/modules`(8종 한 번씩, PROFILE 숨김 400) | `BlogSidebarModule`, `SidebarModules`, `SidebarService`, `SidebarResponse`, `BlogVisitCounter`, `V4__blog_sidebar_module_defaults.sql` |
| T087 사이드바 화면 | 끌어서 또는 ↑↓로 순서, 보이기·숨기기, 저장. 사이드바의 방문자·인기 글·구독 모듈(주인에게는 구독 버튼 없음) | `pages/manage/BlogDesignSections.tsx`, `sidebarModules.ts`, `components/Sidebar.tsx` |
| T106 이사 (BLOG-06) | `POST /api/blog/move-posts`(카테고리 미분류, 태그 이름으로, 번호·수정 시각 그대로), `PUT`·`DELETE /api/blog/moved-to`(연쇄는 최종, 이 블로그로 오던 블로그도 바꿈, 순환 400). 화면: 글 관리 "다른 블로그로 옮기기", 블로그 설정 "블로그 이사" | `BlogMoveService`, `BlogManageController`, `PostRepository.moveTo`, `BlogRepository.retarget`, `ManagePostsPage.tsx` |
| T107 삭제 (BLOG-07) | `GET /api/blog/deletion-preview`, `DELETE /api/blog`(주소 확인, 대표 409, 남은 글·댓글 소프트 삭제, 공감·알림 삭제). 지운 블로그도 이사했으면 301. 화면: 블로그 설정 "블로그 삭제" | `BlogDeletionService`, `BlogContentCleaner`, `SpaForwardController` |
| T108 탈퇴 (AUTH-06) | `DELETE /api/me {password}`: 블로그 모두 삭제, 누른 공감·구독 정리와 수치 맞추기, 댓글·방명록 소프트 삭제, 소셜 연동 끊기, 이메일·비밀번호 비우기. 화면: 마이페이지 "회원 탈퇴" → `/me/withdraw` | `WithdrawalService`, `MemberTraceCleaner`, `Member.withdraw`, `MeController`, `pages/me/WithdrawPage.tsx` |

## 요청 흐름

```
[꾸미기] 블로그 설정 "매거진·분홍·썸네일" → PATCH /api/blog {skin, accentColor, listLayout}
        → 응답 Blog → setBlog → applyBlogTheme: <html data-skin="MAGAZINE" style="--brand:#c0306e">
        블로그 홈 → useBlog → 같은 테마 + listLayout THUMBNAIL이면 카드 목록

[사이드바] "구독"을 끌어 "카테고리" 위로, 보이기 체크 → PUT /api/blog/sidebar/modules [8개]
        → 8종 한 번씩? PROFILE 보임? → 자리 번호대로 sort_order
        방문자 → GET /api/blog/sidebar → 보이는 모듈만 그 순서로, 숨긴 모듈 데이터는 읽지 않음

[옮기기] 글 관리에서 글 31 → "갑의 이사 블로그" → POST /api/blog/move-posts
        → 태그 이름으로 다시 연결 → UPDATE post SET blog_id, category_id=NULL (수정 시각 그대로)
        a.blog.com/31 → 31번은 지금 move 소속 → 301 move.blog.com/31

[삭제] 블로그 설정 → GET deletion-preview "옮기지 않은 글 1개" → 주소 입력 → DELETE /api/blog
        → 남은 글의 공감·알림 삭제, 댓글·글 소프트 삭제, 블로그 deleted_at → 마이페이지로

[탈퇴] /me/withdraw → 비밀번호 → DELETE /api/me
        → 블로그마다 삭제 → 공감 수 -1, 공감 삭제 → 구독 삭제 → 글마다 댓글 수 -n, 댓글·방명록 삭제
        → 소셜 연동 삭제 → WITHDRAWN, 이메일·비밀번호 비움 → 쿠키 삭제 → 홈(비회원)
```

## 이 스텝을 이해하려면 (읽는 순서)

| 순서 | 개념 문서 | 이 스텝에서 쓰인 곳 |
| --- | --- | --- |
| 1 | [54 꾸미기와 블로그의 수명](./concepts/54-theme-move-delete-withdraw.md) (새 문서) | CSS 변수 하나로 포인트 색, `data-skin`으로 스킨, 8종 전체 교체 API와 행이 없는 옛 블로그(V4, 기본값), 번호를 그대로 둔 이사와 301, 연쇄를 최종으로 저장하기, 지운 블로그의 옛 주소(실제 버그), 블로그 단위 SQL 삭제, 탈퇴 정리 순서와 저장된 수치 맞추기 |
| 2 | (복습) [27 소프트 삭제와 일괄 수정](./concepts/27-soft-delete-bulk-update.md) | `updated_at = updated_at`, `clearAutomatically` 뒤에는 엔티티를 고쳐도 반영되지 않음 |
| 3 | (복습) [39 계층 데이터](./concepts/39-category-hierarchy.md) 5.9 | 순서 바꾸기를 순수 함수로, 전체 한 번에 저장 |
| 4 | (복습) [31 태그와 다대다](./concepts/31-tags-many-to-many.md) 5.13 | 옮긴 뒤 옛 블로그에 글이 없어진 태그 지우기 |
| 5 | (복습) [03 Flyway 마이그레이션](./concepts/03-flyway-migration.md) | 이미 적용한 파일은 고치지 않고 V4를 더함 |

## 막혔던 점

- **지운 블로그의 옮긴 글이 404**: 테스트를 쓰다 찾았다. 이사 블로그로 글을 옮긴 뒤 옛 블로그를 지우면, 옮긴 글의 옛 주소가 301이 아니라 404였다. spec 표는 "이사함, 삭제 여부 무관 → 301"이다. 화면 주소 처리가 블로그를 찾자마자 "지웠으면 404"로 끝내고 있었다. 글 주소 판단을 먼저 하고, 블로그 주소는 "지웠고 이사도 안 했으면 404"로 고쳤다. 이사한 블로그를 지운 뒤 301, 최종 블로그까지 지우면 404도 테스트로 확인했다([54](./concepts/54-theme-move-delete-withdraw.md) 5.5).
- **방문자 수 모듈은 아직 0**: 오늘 방문을 남기는 쪽과 새벽 집계가 스텝 20(T082)이다. 읽는 쪽(오늘·어제·누적)만 만들었고, 그 전에는 0으로 보인다. API 명세에 적었다.
- **"적용했습니다"가 사라짐**: 꾸미기 칸을 블로그 값마다 다시 그리게(`key`) 해 두었더니, 적용 뒤 블로그 값이 바뀌면서 칸이 처음부터 다시 그려져 안내 문장이 지워졌다. `key`를 뺐다.
- **주인에게 보이던 구독 버튼**: 사이드바 구독 모듈을 블로그 주인도 보면서 "구독하기"가 그려졌다(누르면 400). 화면이 주인 여부를 사이드바에 넘겨 주인에게는 버튼을 그리지 않게 했다.
- **탈퇴의 비밀번호 401**: API 명세대로 본인 확인 실패는 401이다. api 클라이언트는 401이면 로그인 화면으로 보내므로, 탈퇴 화면은 `allowAnonymous`로 불러 "비밀번호가 맞지 않습니다."를 그 자리에 보인다.
- **테스트 데이터의 글자 깨짐**: 브라우저 확인용 회원을 MySQL 명령줄로 넣으면서 클라이언트 문자 집합을 맞추지 않아 닉네임이 깨졌다. 앱 문제가 아니라 확인용 데이터라 `--default-character-set=utf8mb4`로 다시 넣었다.
- **화면은 실제 브라우저로 확인**: 8081 확인용 서버와 헤드리스 Chrome으로
  - 갑: 꾸미기 "매거진·분홍·썸네일" → 적용 → `<html data-skin="MAGAZINE">`, `--brand: #c0306e` / "노트·보라" → 적용 안내, 노트 바탕
  - 갑: 사이드바 "구독"을 끌어 "카테고리" 위로, 방문자·인기 글·구독 보이기, 인기 글 ↑ → 저장 / 을: 사이드바가 프로필·구독·카테고리·태그·최근 글·최근 댓글·인기 글·방문자 순, 블로그 홈이 카드 5장
  - 갑: 글 관리에서 "이사 보낼 글"을 "갑의 이사 블로그"로 옮기기 → "글 1개를 … 옮겼습니다." → 옛 주소가 `move22029.blog.test/31`로
  - 갑: 이사 블로그 설정 "블로그 이사"로 대표 블로그 지정 → 을이 이사 블로그를 열면 대표 블로그로 → 지정 취소
  - 갑: 이사 블로그 "옮기지 않은 글 1개가 함께 삭제됩니다" → 주소 입력 → 삭제 → 마이페이지 / 을: 그 블로그 404, 옮겼던 글 404 / 대표 블로그 설정은 삭제 대신 "대표를 바꿔 주세요"
  - 탈퇴테스트 회원: 마이페이지 "회원 탈퇴" → 틀린 비밀번호 "비밀번호가 맞지 않습니다." → 탈퇴 → 홈이 비회원 머리글 / 그 회원의 블로그 404 / 글 20의 공감 2→1, 댓글 6→5
  - 확인용으로 개발 DB에 탈퇴 회원 1명(탈퇴테스트19)과 지운 블로그 2개(move22029, leave22029)가 남고, 갑의 블로그는 노트·보라·썸네일과 바꾼 사이드바 순서로 남아 있다. 개발 DB는 V4 마이그레이션까지 적용됐다(8080 서버가 V4 파일이 없는 main으로 다시 떠도 Flyway가 이미 적용된 뒤 버전을 기본으로 건너뛴다).

## 명세와 다르거나 아직 채우지 않은 것

| 항목 | 지금 | 언제 |
| --- | --- | --- |
| 스킨 이름, 사이드바·이사·삭제·탈퇴의 세부 규칙(오류 칸, 이 블로그의 글만 옮김, 지운 블로그의 301, 탈퇴 처리 순서·횟수 제한) | API 명세에 적음 | 반영함 |
| 방문자 수 모듈의 숫자 | 0(방문 기록 전) | 스텝 20 T082 |
| 소셜 가입 회원의 탈퇴 본인 확인 | 없음(소셜 가입이 아직 없음) | 스텝 20 T099에 붙임(tasks에 적음) |
| 탈퇴 때 저장한 글 지우기 | 저장 기능이 아직 없음 | 스텝 20 T077 |
| 이사 지정을 취소하면 이 블로그로 오던 블로그들 | 이미 최종으로 바뀐 그대로(되돌리지 않음) | 그대로 |

## 직접 해 보기

```bash
./mvnw test -Dtest='BlogDecorateMoveDeleteIntegrationTest,WithdrawalIntegrationTest,SidebarIntegrationTest'
cd frontend && npx vitest run src/app/blogTheme.test.ts src/pages/manage/sidebarModules.test.ts && cd ..
```

화면: [54](./concepts/54-theme-move-delete-withdraw.md) 7.1(꾸미기 → 사이드바 → 옮기기 → 이사 → 삭제 → 탈퇴), 7.2(301 직접 보기), 7.4(정리 순서 바꿔 보기).
