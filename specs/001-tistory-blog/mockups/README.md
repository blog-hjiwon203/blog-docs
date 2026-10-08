# 화면 목업

> **이 문서는?** 지원 서비스의 화면 목업 목록과, 화면마다 부르는 API다. 목업은 정적 HTML이라 브라우저로 `index.html`을 열면 바로 보인다. API 경로와 응답 규칙은 [REST API 명세](../contracts/rest-api.md)에, 전체 문서 안내는 [README](../../../README.md)에 있다.

## 보는 법

- `index.html`을 브라우저로 연다. 화면 안의 파란 번호를 누르면 그 화면 아래 API 표의 줄로 간다.
- 글자 번호(A, B, C)는 같은 틀을 쓰는 화면이 모두 부르는 공통 API다(로그인 상태, 블로그 정보, 사이드바).
- 각 화면 아래 **다른 상태**에 빈 목록, 오류 문구, 권한별로 달라지는 부분을 모았다.

## 고치는 법

HTML은 `build.py`가 만든다. 화면을 고치려면 `build.py`의 `PAGES`를 고치고 다시 실행한다. 실행하면 화면에 적은 API 경로가 REST API 명세에 모두 있는지도 확인한다.

```bash
python3 specs/001-tistory-blog/mockups/build.py
```

## 화면 주소

기능 명세와 원본 6장에 있는 주소(`/`, `/login`, `/signup`, `/admin/...`, `/{글 번호}`, `/category/{id}`, `/tag/{이름}`, `/manage/...`) 말고는 목업을 만들며 정했다. 아래 표의 나머지 주소(`/feed`, `/ranking/...`, `/me/...`, `/blogs/new`, `/guestbook`, `/search`, `/manage/` 아래 세부 경로 등)는 바꿔도 된다.

## 화면별 API

### 플랫폼

| 화면 | 주소 | 기능 | 부르는 API |
| --- | --- | --- | --- |
| [플랫폼 홈](home.html) | `blog.com/` | HOME-01, HOME-02, HOME-03, HOME-04, ADMIN-06, AUTH-04 | `GET /api/me`<br>`GET /api/me/notifications/unread-count`<br>`GET /api/notices/latest`<br>`GET /api/home/popular`<br>`GET /api/topics`<br>`GET /api/home/topics/{topic}`<br>`GET /api/home/bloggers`<br>`GET /api/home/latest?cursor=` |
| [전체 검색](search.html) | `blog.com/search?q=spring&type=post` | SRCH-02 | `GET /api/me`<br>`GET /api/me/notifications/unread-count`<br>`GET /api/search?q=&type=post&page=`<br>`GET /api/search?q=&type=blog&page=` |
| [구독 피드](feed.html) | `blog.com/feed` | SUB-02, SUB-06, SUB-01 | `GET /api/me`<br>`GET /api/me/notifications/unread-count`<br>`GET /api/feed?cursor=`<br>`GET /api/recommend/blogs`<br>`PUT /api/blogs/{blogId}/subscription`<br>`DELETE /api/blogs/{blogId}/subscription` |
| [랭킹 전체보기](ranking.html) | `blog.com/ranking/posts` | HOME-05, HOME-02, HOME-04 | `GET /api/me`<br>`GET /api/me/notifications/unread-count`<br>`GET /api/ranking/posts?snapshotAt=&offset=`<br>`GET /api/ranking/bloggers?snapshotAt=&offset=` |
| [공지](notices.html) | `blog.com/notices` | ADMIN-06 | `GET /api/me`<br>`GET /api/me/notifications/unread-count`<br>`GET /api/notices?page=`<br>`GET /api/notices/{id}` |

### 회원

| 화면 | 주소 | 기능 | 부르는 API |
| --- | --- | --- | --- |
| [로그인](login.html) | `blog.com/login?redirect=https://jiwon.blog.com/1532` | AUTH-01, AUTH-03, ADMIN-02 | `GET /api/me`<br>`POST /api/auth/login`<br>`GET /api/auth/oauth/{provider}/authorize?mode=&redirect=` |
| [회원가입](signup.html) | `blog.com/signup` | AUTH-01, OWN-01 | `GET /api/me`<br>`POST /api/auth/email-verifications`<br>`POST /api/auth/email-verifications/verify`<br>`GET /api/auth/nickname-availability?nickname=`<br>`POST /api/auth/signup` |
| [소셜 가입 닉네임 확인](signup-social.html) | `blog.com/signup/social?token=…` | AUTH-01 | `GET /api/me`<br>`GET /api/auth/nickname-availability?nickname=`<br>`POST /api/auth/oauth/signup` |
| [비밀번호 재설정](password-reset.html) | `blog.com/password-reset` | OWN-02 | `GET /api/me`<br>`POST /api/auth/password-reset`<br>`PUT /api/auth/password-reset` |
| [마이페이지](mypage.html) | `blog.com/me` | AUTH-05, OWN-03, BLOG-08, AUTH-04 | `GET /api/me`<br>`GET /api/me/notifications/unread-count`<br>`GET /api/me`<br>`POST /api/images`<br>`PATCH /api/me`<br>`PUT /api/me/password`<br>`DELETE /api/me/social/{provider}`<br>`GET /api/auth/oauth/{provider}/authorize?mode=&redirect=`<br>`GET /api/me/blogs`<br>`PUT /api/me/primary-blog`<br>`POST /api/auth/logout` |
| [저장한 글](bookmarks.html) | `blog.com/me/bookmarks` | SOC-03 | `GET /api/me`<br>`GET /api/me/notifications/unread-count`<br>`GET /api/me/bookmarks?cursor=`<br>`DELETE /api/me/bookmarks/{postId}` |
| [알림](notifications.html) | `blog.com/me/notifications` | SUB-04 | `GET /api/me`<br>`GET /api/me/notifications/unread-count`<br>`GET /api/me/notifications?cursor=`<br>`PUT /api/me/notifications/{id}/read`<br>`PUT /api/me/notifications/read-all` |
| [회원 탈퇴](withdraw.html) | `blog.com/me/withdraw` | AUTH-06 | `GET /api/me`<br>`GET /api/me/notifications/unread-count`<br>`GET /api/auth/oauth/{provider}/authorize?mode=&redirect=`<br>`DELETE /api/me` |
| [블로그 개설](blog-create.html) | `blog.com/blogs/new` | BLOG-01, AUTH-04 | `GET /api/me`<br>`GET /api/me/notifications/unread-count`<br>`GET /api/blogs/address-availability?address=`<br>`POST /api/blogs` |

### 블로그

| 화면 | 주소 | 기능 | 부르는 API |
| --- | --- | --- | --- |
| [블로그 메인](blog-main.html) | `jiwon.blog.com/` | BLOG-03, BLOG-04, CAT-02, TAG-02, SUB-01, SUB-03, BLOG-05 | `GET /api/me`<br>`GET /api/blog`<br>`GET /api/blog/sidebar`<br>`GET /api/posts?page=&size=&categoryId=&tag=`<br>`PUT /api/blogs/{blogId}/subscription`<br>`DELETE /api/blogs/{blogId}/subscription` |
| [블로그 내 검색](blog-search.html) | `jiwon.blog.com/search?q=jpa` | SRCH-01 | `GET /api/me`<br>`GET /api/blog`<br>`GET /api/blog/sidebar`<br>`GET /api/search?q=&page=` |
| [글 상세](post-detail.html) | `jiwon.blog.com/1532` | POST-04, POST-09, POST-10, SOC-01, SOC-02, SOC-03, CMT-01, CMT-02, CMT-03, CMT-05, CMT-06, OWN-05, OWN-06, ADMIN-04 | `GET /api/me`<br>`GET /api/blog`<br>`GET /api/blog/sidebar`<br>`GET /api/posts/{id}`<br>`POST /api/posts/{id}/views`<br>`PUT /api/posts/{id}/like`<br>`PUT /api/posts/{id}/bookmark`<br>`GET /api/posts/{id}/comments?cursor=`<br>`POST /api/posts/{id}/comments`<br>`PATCH /api/comments/{id}`<br>`GET /api/posts/{id}/same-category?size=5`<br>`GET /api/posts/{id}/similar?size=5`<br>`POST /api/reports`<br>`DELETE /api/comments/{id}`<br>`PATCH /api/posts/{id}/visibility`<br>`DELETE /api/posts/{id}` |
| [방명록](guestbook.html) | `jiwon.blog.com/guestbook` | CMT-04, MNG-04 | `GET /api/me`<br>`GET /api/blog`<br>`GET /api/blog/sidebar`<br>`GET /api/guestbook?page=`<br>`POST /api/guestbook`<br>`PATCH /api/guestbook/{id}`<br>`DELETE /api/guestbook/{id}` |

### 블로그 관리

| 화면 | 주소 | 기능 | 부르는 API |
| --- | --- | --- | --- |
| [관리 홈](manage-home.html) | `jiwon.blog.com/manage` | MNG-03, ADMIN-05 | `GET /api/me`<br>`GET /api/blog`<br>`GET /api/manage/stats` |
| [글쓰기](manage-write.html) | `jiwon.blog.com/manage/write` | POST-01, POST-02, POST-05, POST-06, POST-07, POST-08, POST-11, POST-13, TAG-01, CMT-07 | `GET /api/me`<br>`GET /api/blog`<br>`GET /api/manage/posts/{id}`<br>`GET /api/categories`<br>`GET /api/topics`<br>`POST /api/posts`<br>`PUT /api/posts/{id}`<br>`POST /api/images`<br>`GET /api/manage/posts?status=&visibility=&categoryId=&q=&page=` |
| [글 관리](manage-posts.html) | `jiwon.blog.com/manage/posts` | MNG-01, POST-03, POST-06, POST-08, ADMIN-03, BLOG-06 | `GET /api/me`<br>`GET /api/blog`<br>`GET /api/manage/posts?status=&visibility=&categoryId=&q=&page=`<br>`PATCH /api/manage/posts`<br>`DELETE /api/manage/posts`<br>`POST /api/blog/move-posts` |
| [댓글·방명록 관리](manage-comments.html) | `jiwon.blog.com/manage/comments` | MNG-02, CMT-02, MNG-04 | `GET /api/me`<br>`GET /api/blog`<br>`GET /api/manage/comments?type=comment&#124;guestbook&page=`<br>`POST /api/posts/{id}/comments`<br>`DELETE /api/comments/{id}`<br>`POST /api/manage/blocked-members` |
| [카테고리·태그](manage-categories.html) | `jiwon.blog.com/manage/categories` | CAT-01, CAT-03, CAT-04, CAT-05, TAG-03, TAG-04 | `GET /api/me`<br>`GET /api/blog`<br>`GET /api/categories`<br>`POST /api/categories`<br>`PATCH /api/categories/{id}`<br>`DELETE /api/categories/{id}`<br>`PUT /api/categories/order`<br>`GET /api/tags`<br>`PATCH /api/tags/{id}`<br>`DELETE /api/tags/{id}` |
| [방문 통계](manage-stats.html) | `jiwon.blog.com/manage/stats` | MNG-03 | `GET /api/me`<br>`GET /api/blog`<br>`GET /api/manage/stats/visitors?unit=day&#124;week&#124;month&from=&to=`<br>`GET /api/manage/stats/popular-posts?range=all&#124;7d`<br>`GET /api/manage/stats/referrers?from=&to=` |
| [블로그 설정](manage-settings.html) | `jiwon.blog.com/manage/settings` | BLOG-02, BLOG-05, BLOG-06, BLOG-07, BLOG-08 | `GET /api/me`<br>`GET /api/blog`<br>`POST /api/images`<br>`PATCH /api/blog`<br>`PUT /api/blog/appearance`<br>`GET /api/me/blogs`<br>`PUT /api/blog/moved-to`<br>`DELETE /api/blog/moved-to`<br>`GET /api/blog/deletion-preview`<br>`DELETE /api/blog` |
| [스팸·차단](manage-spam.html) | `jiwon.blog.com/manage/spam` | MNG-04 | `GET /api/me`<br>`GET /api/blog`<br>`GET /api/manage/blocked-members?page=`<br>`DELETE /api/manage/blocked-members/{memberId}`<br>`GET /api/manage/banned-words`<br>`POST /api/manage/banned-words`<br>`DELETE /api/manage/banned-words/{id}` |

### 서비스 관리

| 화면 | 주소 | 기능 | 부르는 API |
| --- | --- | --- | --- |
| [관리 대시보드](admin-dashboard.html) | `blog.com/admin` | ADMIN-01, ADMIN-06 | `GET /api/me`<br>`GET /api/admin/dashboard` |
| [회원 관리](admin-members.html) | `blog.com/admin/members` | ADMIN-02 | `GET /api/me`<br>`GET /api/admin/members?q=&status=&page=`<br>`GET /api/admin/members/{id}`<br>`POST /api/admin/members/{id}/suspension`<br>`DELETE /api/admin/members/{id}/suspension` |
| [신고 처리](admin-reports.html) | `blog.com/admin/reports` | ADMIN-04, ADMIN-03, ADMIN-05 | `GET /api/me`<br>`GET /api/admin/reports?status=PENDING&page=`<br>`GET /api/admin/reports/{targetType}/{targetId}`<br>`POST /api/admin/reports/{targetType}/{targetId}/resolve` |
| [관리 이력·공지](admin-logs.html) | `blog.com/admin/logs` | ADMIN-06 | `GET /api/me`<br>`GET /api/admin/moderation-logs?targetType=&targetId=&adminId=&from=&to=&page=`<br>`POST /api/admin/notices`<br>`PUT /api/admin/notices/{id}`<br>`DELETE /api/admin/notices/{id}` |

### 공통

| 화면 | 주소 | 기능 | 부르는 API |
| --- | --- | --- | --- |
| [오류 화면](errors.html) | `(어느 주소든)` | COM-01, COM-02 | 없음 |
