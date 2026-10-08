#!/usr/bin/env python3
"""화면 목업 생성기.

화면 하나하나를 PAGES에 데이터로 적고, 이 스크립트가 HTML 파일과 README.md를 만든다.
목업을 고칠 때는 HTML을 직접 고치지 말고 이 파일을 고친 뒤 다시 실행한다.

    python3 specs/001-tistory-blog/mockups/build.py

실행하면 각 화면의 API 경로가 contracts/rest-api.md에 있는지도 확인한다.
"""
from __future__ import annotations

import html
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
API_DOC = HERE.parent / "contracts" / "rest-api.md"

FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    'family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans+KR:wght@400;600;700&display=swap">'
)


def P(n) -> str:
    """API 번호 핀. 아래 API 표의 같은 번호 줄로 이어진다."""
    return f'<a class="pin" href="#api-{n}" title="API {n}">{n}</a>'


def esc(s: str) -> str:
    return html.escape(s, quote=True)


# ---------------------------------------------------------------- 공통 틀

PLATFORM_COMMON = [
    ("A", "화면 열 때", "GET", "/api/me", "로그인 상태·닉네임·대표 블로그. 401이면 비회원 머리글"),
    ("B", "화면 열 때(회원)", "GET", "/api/me/notifications/unread-count", "종 아이콘의 읽지 않은 알림 수"),
]
BLOG_COMMON = [
    ("A", "화면 열 때", "GET", "/api/me", "로그인 상태. 401이면 비회원"),
    ("B", "화면 열 때", "GET", "/api/blog", "블로그 이름·주인·구독 여부. 404면 404 화면"),
    ("C", "화면 열 때", "GET", "/api/blog/sidebar", "사이드바 전체(카테고리 트리, 태그, 최근 글·댓글 5)"),
]
MANAGE_COMMON = [
    ("A", "화면 열 때", "GET", "/api/me", "401이면 로그인 화면으로(돌아올 주소 포함)"),
    ("B", "화면 열 때", "GET", "/api/blog", "viewer.isOwner가 false면 403 화면. 이용 제한이면 restriction 사유 띠"),
]
ADMIN_COMMON = [
    ("A", "화면 열 때", "GET", "/api/me", "role이 ADMIN이 아니면 403 화면"),
]


def platform_head(active: str = "", logged: bool = True) -> str:
    links = [("home", "홈", "home.html"), ("feed", "구독 피드", "feed.html"), ("ranking", "랭킹", "ranking.html"), ("notices", "공지", "notices.html")]
    nav = "".join(
        f'<a href="{href}" class="{"on" if key == active else ""}">{label}</a>' for key, label, href in links
    )
    if logged:
        right = (
            f'<a class="btn ghost" href="notifications.html" aria-label="알림">알림 <span class="chip brand num">2</span> {P("B")}</a>'
            '<a class="btn primary" href="manage-write.html">글쓰기</a>'
            f'<a class="row" href="mypage.html" style="text-decoration:none"><span class="avatar"></span>{P("A")}</a>'
        )
    else:
        right = f'<a class="btn" href="login.html">로그인</a><a class="btn primary" href="signup.html">회원가입</a> {P("A")}'
    return (
        '<header class="site-head">'
        '<a class="logo" href="home.html">blog.com</a>'
        f'<nav class="nav-links">{nav}</nav>'
        '<form class="search-box" role="search" onsubmit="return false">'
        '<input type="search" id="gsearch" placeholder="글·블로그 검색" aria-label="전체 검색">'
        '<a class="btn" href="search.html">검색</a></form>'
        '<span class="grow"></span>'
        f'<div class="row">{right}</div>'
        "</header>"
    )


def blog_head(logged: bool = True) -> str:
    who = (
        f'<a class="btn" href="mypage.html">마이페이지</a>{P("A")}'
        if logged
        else f'<a class="btn" href="login.html">로그인</a>{P("A")}'
    )
    return (
        '<header class="site-head">'
        '<a class="logo" href="home.html" title="플랫폼 홈">blog.com</a>'
        f'<a href="blog-main.html" style="text-decoration:none;font-weight:700;font-size:17px">지원의 기록</a>{P("B")}'
        '<nav class="nav-links"><a href="blog-main.html">홈</a><a href="guestbook.html">방명록</a></nav>'
        '<span class="grow"></span>'
        '<form class="search-box" role="search" onsubmit="return false">'
        '<input type="search" id="bsearch" placeholder="이 블로그에서 검색" aria-label="블로그 내 검색">'
        '<a class="btn" href="blog-search.html">검색</a></form>'
        f'<div class="row">{who}</div>'
        "</header>"
    )


def blog_sidebar() -> str:
    return f"""
<aside class="sidebar" aria-label="사이드바">
  <div class="row">{P("C")}<span class="small muted">사이드바 전체가 API C 하나</span></div>
  <div class="box"><div class="row"><span class="avatar lg"></span><div><b>지원의 기록</b><div class="small muted">백엔드 공부와 여행 메모</div></div></div>
    <div class="small muted num">구독자 18명</div></div>
  <div><h4>카테고리</h4>
    <ul><li><a href="blog-main.html">전체 글 <span class="muted num">(42)</span></a></li>
      <li><a href="blog-main.html">개발 <span class="muted num">(30)</span></a>
        <ul><li><a href="blog-main.html">Spring <span class="muted num">(12)</span></a></li><li><a href="blog-main.html">JPA <span class="muted num">(9)</span></a></li><li><a href="blog-main.html">React <span class="muted num">(9)</span></a></li></ul></li>
      <li><a href="blog-main.html">여행 <span class="muted num">(9)</span></a></li>
      <li><a href="blog-main.html">미분류 <span class="muted num">(3)</span></a></li></ul></div>
  <div><h4>태그</h4><div class="tag-cloud"><a class="chip" href="blog-main.html">spring 14</a><a class="chip" href="blog-main.html">jpa 9</a><a class="chip" href="blog-main.html">제주 4</a><a class="chip" href="blog-main.html">security 3</a></div></div>
  <div><h4>최근 글</h4><ul><li><a href="post-detail.html">Spring Security 필터 체인 정리</a></li><li><a href="post-detail.html">JPA N+1과 fetch join</a></li><li><a href="post-detail.html">제주 3박 4일 동선</a></li><li><a href="post-detail.html">React Query 캐시 키 설계</a></li><li><a href="post-detail.html">MySQL 인덱스 읽는 법</a></li></ul></div>
  <div><h4>최근 댓글</h4><ul><li class="small">잘 읽었습니다! · 하늘</li><li class="small">fetch join 페이징은요? · 민수</li><li class="small">비밀댓글입니다</li><li class="small">사진 예뻐요 · 여름</li><li class="small">감사합니다 · 지원</li></ul></div>
</aside>"""


def manage_nav(active: str) -> str:
    items = [
        ("sec", "블로그 관리"),
        ("manage-home", "관리 홈"),
        ("manage-write", "글쓰기"),
        ("manage-posts", "글 관리"),
        ("manage-comments", "댓글·방명록"),
        ("manage-categories", "카테고리·태그"),
        ("sec", "통계"),
        ("manage-stats", "방문 통계"),
        ("sec", "설정"),
        ("manage-settings", "블로그 설정"),
        ("manage-spam", "스팸·차단"),
    ]
    out = []
    for key, label in items:
        if key == "sec":
            out.append(f'<div class="sec">{label}</div>')
        else:
            out.append(f'<a href="{key}.html" class="{"on" if key == active else ""}">{label}</a>')
    return f'<nav class="manage-nav" aria-label="관리 메뉴">{"".join(out)}</nav>'


def manage_head() -> str:
    return (
        '<header class="site-head">'
        '<a class="logo" href="home.html">blog.com</a>'
        f'<a href="blog-main.html" style="text-decoration:none;font-weight:700">지원의 기록</a><span class="chip">관리</span>{P("B")}'
        '<span class="grow"></span>'
        f'<a class="btn" href="blog-main.html">블로그 보기</a><a class="row" href="mypage.html"><span class="avatar"></span></a>{P("A")}'
        "</header>"
    )


def admin_nav(active: str) -> str:
    items = [("admin-dashboard", "대시보드"), ("admin-members", "회원"), ("admin-reports", "신고"), ("admin-logs", "관리 이력·공지")]
    links = "".join(f'<a href="{k}.html" class="{"on" if k == active else ""}">{v}</a>' for k, v in items)
    return f'<nav class="manage-nav" aria-label="서비스 관리 메뉴"><div class="sec">서비스 관리</div>{links}</nav>'


def admin_head() -> str:
    return (
        '<header class="site-head">'
        '<a class="logo" href="home.html">blog.com</a><span class="chip warn">서비스 관리</span>'
        f'<span class="grow"></span><span class="small muted">관리자 운영팀</span>{P("A")}'
        "</header>"
    )


# ---------------------------------------------------------------- 화면 데이터
# chrome: platform | platform-guest | blog | blog-guest | manage | admin | bare
# apis: (번호, 언제, 메서드, 경로, 설명)

PAGES: list[dict] = []


def page(**kw):
    kw.setdefault("states", [])
    kw.setdefault("notes", [])
    kw.setdefault("active", "")
    PAGES.append(kw)


# ---- 플랫폼: 홈·탐색

page(
    slug="home", group="플랫폼", title="플랫폼 홈", url="blog.com/",
    codes=["HOME-01", "HOME-02", "HOME-03", "HOME-04", "ADMIN-06", "AUTH-04"],
    chrome="platform", active="home",
    lead="처음 들어오는 화면. 섹션마다 API가 따로라 동시에 불러 오고(Promise.all), 하나가 실패해도 나머지는 보인다.",
    body=f"""
<div class="box brand"><div class="row between"><span>{P(1)} <b>공지</b> 10월 정기 점검 안내 (10/12 02:00~04:00)</span><a class="small" href="notices.html">공지 전체</a></div></div>
<div class="cols">
  <div class="stack" style="gap:24px">
    <section class="section"><h2>인기 글 {P(2)} <small>최근 1시간 · 10:35 기준</small></h2>
      <div class="rank-list">
        <div class="rank"><b>1</b><a href="post-detail.html">Spring Security 필터 체인 정리</a><span class="small muted">지원의 기록</span></div>
        <div class="rank"><b>2</b><a href="post-detail.html">퇴사하고 3개월, 돈 이야기</a><span class="small muted">여름의 일기</span></div>
        <div class="rank"><b>3</b><a href="post-detail.html">성수동 브런치 다섯 곳</a><span class="small muted">먹는 게 남는 것</span></div>
        <div class="rank"><b>4</b><a href="post-detail.html">JPA N+1과 fetch join</a><span class="small muted">지원의 기록</span></div>
        <div class="rank"><b>5</b><a href="post-detail.html">하프 마라톤 첫 완주 후기</a><span class="small muted">달리는 민수</span></div>
      </div>
      <a class="small" href="ranking.html">랭킹 전체보기 (100위까지)</a>
    </section>
    <section class="section"><h2>주제별 글 {P(3)}{P(4)}</h2>
      <nav class="tabs"><a class="on" href="#">IT·개발</a><a href="#">여행</a><a href="#">맛집·요리</a><a href="#">일상</a><a href="#">리뷰</a><a href="#">취미</a><a href="#">경제·재테크</a><a href="#">건강·운동</a><a href="#">문화·연예</a><a href="#">교육·학습</a></nav>
      <div class="grid-cards">
        <a class="card" href="post-detail.html" style="text-decoration:none"><div class="thumb"></div><h3>Spring Security 필터 체인 정리</h3><span class="meta">지원의 기록 · 공감 5</span></a>
        <a class="card" href="post-detail.html" style="text-decoration:none"><div class="thumb"></div><h3>Next.js 앱 라우터 넘어가기</h3><span class="meta">프론트 노트 · 공감 12</span></a>
        <a class="card" href="post-detail.html" style="text-decoration:none"><div class="thumb"></div><h3>Kafka 컨슈머 랙 줄이기</h3><span class="meta">데이터 엔지니어링 · 공감 3</span></a>
      </div>
    </section>
    <section class="section"><h2>최신 글 {P(6)}</h2>
      <div class="post-list">
        <article class="post-item"><div><h3><a href="post-detail.html">MySQL 인덱스 읽는 법</a></h3><p>EXPLAIN 결과에서 type, key, rows를 어떻게 읽는지 예제로 정리했다.</p><div class="meta"><span>지원의 기록</span><span>2026.10.08 09:12</span><span>공감 2</span><span>댓글 1</span></div></div><div class="thumb"></div></article>
        <article class="post-item"><div><h3><a href="post-detail.html">가을 북한산 백운대 코스</a></h3><p>우이동에서 출발해 하루재를 넘는 가장 흔한 코스. 단풍은 다음 주가 절정.</p><div class="meta"><span>주말 산행</span><span>2026.10.08 08:40</span><span>공감 0</span></div></div><div class="thumb"></div></article>
      </div>
      <button class="btn more" type="button">더보기 {P(6)}</button>
    </section>
  </div>
  <aside class="sidebar">
    <section class="section"><h2>인기 블로거 {P(5)}</h2>
      <div class="rank-list">
        <div class="rank"><b>1</b><span>지원의 기록</span><span class="small muted">구독 18</span></div>
        <div class="rank"><b>2</b><span>여름의 일기</span><span class="small muted">구독 240</span></div>
        <div class="rank"><b>3</b><span>먹는 게 남는 것</span><span class="small muted">구독 97</span></div>
        <div class="rank"><b>4</b><span>달리는 민수</span><span class="small muted">구독 41</span></div>
        <div class="rank"><b>5</b><span>프론트 노트</span><span class="small muted">구독 63</span></div>
      </div></section>
    <div class="box"><b>내 블로그</b><span class="small muted">글쓰기를 누르면 대표 블로그 글쓰기로, 블로그가 없으면 블로그 개설로 간다(API A의 primaryBlog).</span><a class="btn primary" href="manage-write.html">글쓰기</a></div>
  </aside>
</div>""",
    apis=[
        (1, "화면 열 때", "GET", "/api/notices/latest", "최신 공지 1개. null이면 띠를 숨김"),
        (2, "화면 열 때", "GET", "/api/home/popular", "인기 글 10과 snapshotAt(5분 스냅숏)"),
        (3, "화면 열 때", "GET", "/api/topics", "주제 탭 10개"),
        (4, "탭 고를 때", "GET", "/api/home/topics/{topic}", "주제별 6. 처음엔 첫 탭"),
        (5, "화면 열 때", "GET", "/api/home/bloggers", "인기 블로거 5(1시간 스냅숏)"),
        (6, "화면 열 때·더보기", "GET", "/api/home/latest?cursor=", "최신 글 20씩. nextCursor가 null이면 더보기 숨김"),
    ],
    notes=["볼 수 없는 글(비공개, 구독자 공개, 숨김, 제한 블로그)은 어느 섹션에도 나오지 않는다. 서버가 거른다."],
)

page(
    slug="search", group="플랫폼", title="전체 검색", url="blog.com/search?q=spring&type=post",
    codes=["SRCH-02"], chrome="platform",
    lead="글 탭과 블로그 탭. 탭마다 같은 API를 type만 바꿔 부른다.",
    body=f"""
<div class="row"><input type="search" id="q" value="spring" aria-label="검색어" style="max-width:360px"><a class="btn primary" href="#">검색</a></div>
<nav class="tabs"><a class="on" href="#">글 {P(1)}</a><a href="#">블로그 {P(2)}</a></nav>
<p class="small muted num">글 128개</p>
<div class="post-list">
  <article class="post-item"><div><h3><a href="post-detail.html"><mark>Spring</mark> Security 필터 체인 정리</a></h3><p>SecurityFilterChain이 요청을 어떤 순서로 거치는지…</p><div class="meta"><span>지원의 기록</span><span>2026.10.08</span></div></div><div class="thumb"></div></article>
  <article class="post-item"><div><h3><a href="post-detail.html"><mark>Spring</mark> Batch 청크 크기 정하기</a></h3><p>커밋 간격과 메모리 사이에서…</p><div class="meta"><span>데이터 엔지니어링</span><span>2026.10.06</span></div></div><div class="thumb"></div></article>
</div>
<nav class="pager"><a href="#">이전</a><a class="on" href="#">1</a><a href="#">2</a><a href="#">3</a><a href="#">다음</a></nav>""",
    states=[("블로그 탭", f"""<div class="row"><span class="avatar"></span><div><b>스프링 일기</b><div class="small muted">주인 하늘 · 구독 12</div></div>{P(2)}</div>"""),
            ("결과 없음", '<p class="muted">\'spring\'에 맞는 글이 없습니다. 다른 검색어로 찾아 보세요.</p>')],
    apis=[
        (1, "검색·탭·페이지", "GET", "/api/search?q=&type=post&page=", "글 10개씩, 페이지 번호"),
        (2, "블로그 탭", "GET", "/api/search?q=&type=blog&page=", "블로그 이름·소개 검색"),
    ],
)

page(
    slug="feed", group="플랫폼", title="구독 피드", url="blog.com/feed",
    codes=["SUB-02", "SUB-06", "SUB-01"], chrome="platform", active="feed",
    lead="회원만 들어온다. 비회원이 열면 로그인 화면으로 보내고 로그인 후 돌아온다(API A가 401).",
    body=f"""
<div class="cols">
  <section class="section"><h2>구독한 블로그의 새 글 {P(1)}</h2>
    <div class="post-list">
      <article class="post-item"><div><h3><a href="post-detail.html">퇴사하고 3개월, 돈 이야기</a></h3><p>고정비를 줄이는 게 생각보다 어려웠다.</p><div class="meta"><span>여름의 일기</span><span>2026.10.08 07:30</span><span class="chip">구독자 공개</span></div></div><div class="thumb"></div></article>
      <article class="post-item"><div><h3><a href="post-detail.html">하프 마라톤 첫 완주 후기</a></h3><p>21.0975km, 2시간 4분.</p><div class="meta"><span>달리는 민수</span><span>2026.10.07 21:02</span></div></div><div class="thumb"></div></article>
    </div>
    <button class="btn more" type="button">더보기 {P(1)}</button>
  </section>
  <aside class="sidebar"><section class="section"><h2>추천 블로그 {P(2)}</h2>
    <div class="stack">
      <div class="row between"><div><b>먹는 게 남는 것</b><div class="small muted">구독 97 · 성수동 브런치 다섯 곳</div></div><button class="btn" type="button">구독 {P(3)}</button></div>
      <div class="row between"><div><b>프론트 노트</b><div class="small muted">구독 63 · Next.js 앱 라우터</div></div><button class="btn on" type="button">구독 중 {P(4)}</button></div>
      <div class="row between"><div><b>주말 산행</b><div class="small muted">구독 22 · 북한산 백운대</div></div><button class="btn" type="button">구독</button></div>
    </div></section></aside>
</div>""",
    states=[("구독한 블로그가 없을 때", '<p class="muted">아직 구독한 블로그가 없습니다. 오른쪽 추천 블로그나 홈에서 마음에 드는 블로그를 구독해 보세요.</p><p class="small muted">추천 블로그는 그대로 보인다(SUB-06).</p>')],
    apis=[
        (1, "화면 열 때·더보기", "GET", "/api/feed?cursor=", "구독한 블로그 새 글 20씩"),
        (2, "화면 열 때", "GET", "/api/recommend/blogs", "인기 블로거에서 내 블로그·구독 중 블로그를 뺀 5"),
        (3, "구독 누를 때", "PUT", "/api/blogs/{blogId}/subscription", "구독. 차단된 블로그면 403 BLOCKED_BY_BLOG 안내"),
        (4, "구독 중 누를 때", "DELETE", "/api/blogs/{blogId}/subscription", "구독 취소"),
    ],
)

page(
    slug="ranking", group="플랫폼", title="랭킹 전체보기", url="blog.com/ranking/posts",
    codes=["HOME-05", "HOME-02", "HOME-04"], chrome="platform", active="ranking",
    lead="홈과 같은 스냅숏을 100위까지 20개씩. 더보기 때 처음 받은 snapshotAt을 함께 보낸다.",
    body=f"""
<nav class="tabs"><a class="on" href="#">인기 글 {P(1)}</a><a href="#">인기 블로거 {P(2)}</a></nav>
<p class="small muted">2026.10.08 10:35 기준 · 최근 1시간 조회×1 + 공감×3 + 댓글×5</p>
<div class="table-wrap"><table><thead><tr><th class="num">순위</th><th>글</th><th>블로그</th><th class="num">공감</th></tr></thead><tbody>
<tr><td class="num">1</td><td><a href="post-detail.html">Spring Security 필터 체인 정리</a></td><td>지원의 기록</td><td class="num">5</td></tr>
<tr><td class="num">2</td><td>퇴사하고 3개월, 돈 이야기</td><td>여름의 일기</td><td class="num">31</td></tr>
<tr><td class="num">3</td><td>성수동 브런치 다섯 곳</td><td>먹는 게 남는 것</td><td class="num">18</td></tr>
<tr><td class="num">…</td><td class="muted">20위까지</td><td></td><td></td></tr>
</tbody></table></div>
<button class="btn more" type="button">21~40위 더보기 {P(1)}</button>""",
    states=[("더보기 중 순위가 바뀌었을 때 (409 RANKING_UPDATED)", '<div class="box warn">순위가 새로 계산됐습니다. 10:40 기준으로 처음부터 다시 보여 드릴게요.</div>'),
            ("인기 블로거 탭", '<p class="small muted">최근 7일 블로그 점수 · 1시간마다 갱신. 열: 순위, 블로그, 주인, 구독자 수.</p>')],
    apis=[
        (1, "탭 열 때·더보기", "GET", "/api/ranking/posts?snapshotAt=&offset=", "처음엔 snapshotAt 없이. 이후 같은 값과 offset 20, 40…"),
        (2, "블로거 탭", "GET", "/api/ranking/bloggers?snapshotAt=&offset=", "같은 규칙"),
    ],
)

page(
    slug="notices", group="플랫폼", title="공지", url="blog.com/notices",
    codes=["ADMIN-06"], chrome="platform", active="notices",
    lead="목록과 상세. 상세 주소는 blog.com/notices/{id}.",
    body=f"""
<div class="table-wrap"><table><thead><tr><th>제목 {P(1)}</th><th>작성일</th></tr></thead><tbody>
<tr><td><a href="#">10월 정기 점검 안내</a></td><td class="num">2026.10.07</td></tr>
<tr><td><a href="#">구독자 공개 글 기능이 열렸습니다</a></td><td class="num">2026.10.01</td></tr>
<tr><td><a href="#">서비스 이용 정책 개정</a></td><td class="num">2026.09.20</td></tr>
</tbody></table></div>
<nav class="pager"><a class="on" href="#">1</a><a href="#">2</a></nav>""",
    states=[("상세", f'<h3>10월 정기 점검 안내 {P(2)}</h3><p class="small muted">2026.10.07</p><p>10월 12일 02:00부터 04:00까지 서비스를 쓸 수 없습니다.</p>')],
    apis=[
        (1, "화면 열 때·페이지", "GET", "/api/notices?page=", "공지 10개씩"),
        (2, "상세 열 때", "GET", "/api/notices/{id}", "제목·내용"),
    ],
)

# ---- 플랫폼: 회원

page(
    slug="login", group="회원", title="로그인", url="blog.com/login?redirect=https://jiwon.blog.com/1532",
    codes=["AUTH-01", "AUTH-03", "ADMIN-02"], chrome="platform-guest",
    lead="로그인이 필요한 화면에서 넘어오면 redirect에 원래 주소가 붙고, 로그인 후 그 주소로 돌아간다(우리 서비스 주소만).",
    body=f"""
<div class="page narrow" style="padding:0">
  <h2 style="font-size:22px">로그인</h2>
  <label class="field"><span>이메일</span><input type="email" id="lemail" value="jiwon@example.com"></label>
  <label class="field"><span>비밀번호</span><input type="password" id="lpw" value="password1"></label>
  <label class="row small"><input type="checkbox" id="remember" checked> 로그인 상태 유지</label>
  <button class="btn primary" type="button">로그인 {P(1)}</button>
  <div class="row between small"><a href="password-reset.html">비밀번호를 잊었어요</a><a href="signup.html">회원가입</a></div>
  <div class="stack"><span class="small muted">또는</span>
    <a class="btn" href="#">카카오로 계속하기 {P(2)}</a><a class="btn" href="#">구글로 계속하기 {P(2)}</a></div>
</div>""",
    states=[("실패 (401 LOGIN_FAILED)", '<p class="err">이메일 또는 비밀번호가 맞지 않습니다.</p><p class="small muted">탈퇴 회원도 같은 문구(없는 계정 취급).</p>'),
            ("정지 회원 (403 MEMBER_SUSPENDED)", '<div class="box danger"><b>이용이 정지된 계정입니다</b><span>사유: 스팸·광고 — 광고성 글을 반복해서 올려 이용이 정지되었습니다.</span><span class="num">정지 기한: 2026.11.07 13:00까지</span></div>')],
    apis=[
        (1, "로그인 누를 때", "POST", "/api/auth/login", "{ email, password, rememberMe } → Me + 쿠키"),
        (2, "소셜 버튼", "GET", "/api/auth/oauth/{provider}/authorize?mode=&redirect=", "mode=login. 처음 보는 소셜 계정이면 닉네임 확인 화면으로 돌아온다"),
    ],
)

page(
    slug="signup", group="회원", title="회원가입", url="blog.com/signup",
    codes=["AUTH-01", "OWN-01"], chrome="platform-guest",
    lead="이메일 인증 코드를 확인해야 가입 버튼이 켜진다. 인증 전에는 회원이 만들어지지 않는다.",
    body=f"""
<div class="page narrow" style="padding:0">
  <h2 style="font-size:22px">회원가입</h2>
  <label class="field"><span>이메일</span><div class="row" style="flex-wrap:nowrap"><input type="email" id="semail" value="jiwon@example.com"><button class="btn" type="button">코드 받기 {P(1)}</button></div><span class="ok">인증 코드를 보냈습니다. 10분 안에 입력해 주세요.</span></label>
  <label class="field"><span>인증 코드</span><div class="row" style="flex-wrap:nowrap"><input type="text" id="scode" value="482913" inputmode="numeric"><button class="btn" type="button">확인 {P(2)}</button></div><span class="ok">이메일이 확인되었습니다.</span></label>
  <label class="field"><span>비밀번호</span><input type="password" id="spw" value="password1"><span class="hint">8자 이상, 영문과 숫자를 함께</span></label>
  <label class="field"><span>닉네임</span><input type="text" id="snick" value="지원"><span class="ok">쓸 수 있는 닉네임입니다. {P(3)}</span></label>
  <button class="btn primary" type="button">가입하기 {P(4)}</button>
</div>""",
    states=[("이미 가입한 이메일 (409 EMAIL_TAKEN)", '<p class="err">이미 가입한 이메일입니다. 로그인하거나 비밀번호를 재설정해 주세요.</p>'),
            ("코드 오류", '<p class="err">인증 코드가 맞지 않습니다.</p><p class="err">인증 코드가 만료되었습니다. 코드를 다시 받아 주세요.</p>'),
            ("1분 안에 다시 받기 (429)", '<p class="err">잠시 후 다시 시도해 주세요. (42초)</p>')],
    apis=[
        (1, "코드 받기", "POST", "/api/auth/email-verifications", "{ email } → 202"),
        (2, "코드 확인", "POST", "/api/auth/email-verifications/verify", "{ email, code } → 200. 화면 단계 확인"),
        (3, "닉네임 입력 후", "GET", "/api/auth/nickname-availability?nickname=", "{ available }"),
        (4, "가입하기", "POST", "/api/auth/signup", "{ email, code, password, nickname } → 201 + 쿠키. 블로그 개설로 이동"),
    ],
)

page(
    slug="signup-social", group="회원", title="소셜 가입 닉네임 확인", url="blog.com/signup/social?token=…",
    codes=["AUTH-01"], chrome="platform-guest",
    lead="처음 보는 카카오·구글 계정으로 로그인하면 여기로 온다. 제공사 이메일은 저장하지 않는다.",
    body=f"""
<div class="page narrow" style="padding:0">
  <h2 style="font-size:22px">닉네임을 정해 주세요</h2>
  <p class="small muted">카카오 계정으로 새로 가입합니다. 이미 이메일로 가입했다면 그 계정으로 로그인한 뒤 마이페이지에서 카카오를 연동해 주세요.</p>
  <label class="field"><span>닉네임</span><input type="text" id="snnick" value="지원"><span class="err">이미 쓰는 닉네임입니다. {P(1)}</span></label>
  <button class="btn primary" type="button">가입 완료 {P(2)}</button>
</div>""",
    states=[("토큰 만료(10분)", '<p class="err">가입 시간이 지났습니다. 처음부터 다시 로그인해 주세요.</p>')],
    apis=[
        (1, "닉네임 입력 후", "GET", "/api/auth/nickname-availability?nickname=", "{ available }"),
        (2, "가입 완료", "POST", "/api/auth/oauth/signup", "{ signupToken, nickname } → 201 + 쿠키"),
    ],
)

page(
    slug="password-reset", group="회원", title="비밀번호 재설정", url="blog.com/password-reset",
    codes=["OWN-02"], chrome="platform-guest",
    lead="두 단계. 메일 요청 화면과, 메일 링크(blog.com/password-reset?token=…)로 여는 새 비밀번호 화면.",
    body=f"""
<div class="page narrow" style="padding:0">
  <h2 style="font-size:22px">비밀번호 재설정</h2>
  <label class="field"><span>가입한 이메일</span><input type="email" id="remail" value="jiwon@example.com"></label>
  <button class="btn primary" type="button">재설정 메일 받기 {P(1)}</button>
  <p class="ok">메일을 보냈습니다. 30분 안에 링크를 눌러 주세요.</p>
  <p class="small muted">가입하지 않은 이메일이어도 같은 문구를 보인다(가입 여부를 드러내지 않음).</p>
</div>""",
    states=[("링크로 연 화면", f'<label class="field"><span>새 비밀번호</span><input type="password" id="rnew" value="newpass12"></label><button class="btn primary" type="button">변경하기 {P(2)}</button>'),
            ("링크 만료·사용됨 (400 RESET_TOKEN_INVALID)", '<p class="err">링크가 만료되었거나 이미 사용되었습니다. 메일을 다시 받아 주세요.</p>')],
    apis=[
        (1, "메일 받기", "POST", "/api/auth/password-reset", "{ email } → 202"),
        (2, "변경하기", "PUT", "/api/auth/password-reset", "{ token, newPassword } → 204. 로그인 화면으로"),
    ],
)

page(
    slug="mypage", group="회원", title="마이페이지", url="blog.com/me",
    codes=["AUTH-05", "OWN-03", "BLOG-08", "AUTH-04"], chrome="platform",
    lead="회원 정보, 로그인 수단, 내 블로그. 저장한 글·알림·탈퇴는 옆 화면.",
    body=f"""
<nav class="tabs"><a class="on" href="mypage.html">내 정보</a><a href="bookmarks.html">저장한 글</a><a href="notifications.html">알림</a></nav>
<div class="cols">
  <div class="stack" style="gap:24px">
    <section class="section"><h2>프로필</h2>
      <div class="row"><span class="avatar lg"></span><button class="btn" type="button">사진 바꾸기 {P(2)}</button></div>
      <label class="field"><span>닉네임</span><input type="text" id="mnick" value="지원"></label>
      <button class="btn primary" type="button" style="justify-self:start">저장 {P(3)}</button></section>
    <section class="section"><h2>비밀번호 변경</h2>
      <label class="field"><span>지금 비밀번호</span><input type="password" id="mcur"></label>
      <label class="field"><span>새 비밀번호</span><input type="password" id="mnew"></label>
      <button class="btn" type="button" style="justify-self:start">변경 {P(4)}</button>
      <p class="small muted">소셜로 가입한 회원에게는 이 칸이 없다(hasPassword=false).</p></section>
    <section class="section"><h2>소셜 계정 연동</h2>
      <p class="small muted">다른 소셜 계정도 연결해 두면 로그인 수단을 잃었을 때 대비할 수 있어요.</p>
      <div class="row between box"><span>카카오 <span class="chip brand">연결됨 2026.10.08</span></span><button class="btn" type="button">해제 {P(5)}</button></div>
      <div class="row between box"><span>구글 <span class="chip">연결 안 됨</span></span><a class="btn" href="#">연결 {P(6)}</a></div></section>
  </div>
  <aside class="sidebar"><section class="section"><h2>내 블로그 {P(7)}</h2>
    <div class="stack">
      <div class="box"><div class="row between"><b>지원의 기록</b><span class="chip brand">대표</span></div><span class="small muted">jiwon.blog.com · 글 42</span></div>
      <div class="box"><div class="row between"><b>지원 여행기</b><button class="btn" type="button">대표로 {P(8)}</button></div><span class="small muted">jiwon-travel.blog.com · 글 9</span></div>
      <a class="btn" href="blog-create.html">블로그 만들기 (2/5)</a>
    </div></section>
    <button class="btn" type="button">로그아웃 {P(9)}</button>
    <a class="small muted" href="withdraw.html">회원 탈퇴</a></aside>
</div>""",
    states=[("연동 실패 (돌아온 주소의 error)", '<p class="err">이미 다른 계정에 연결된 소셜 계정입니다.</p><p class="err">구글 계정은 이미 하나 연결되어 있습니다.</p>'),
            ("해제 거절 (409 LAST_LOGIN_METHOD)", '<p class="err">로그인 수단이 하나도 남지 않아 해제할 수 없습니다.</p>')],
    apis=[
        (1, "화면 열 때", "GET", "/api/me", "공통 A와 같은 응답을 그대로 씀(이메일, 소셜 목록, hasPassword)"),
        (2, "사진 고를 때", "POST", "/api/images", "업로드 → id"),
        (3, "저장", "PATCH", "/api/me", "{ nickname, profileImageId }. 닉네임 중복 409"),
        (4, "비밀번호 변경", "PUT", "/api/me/password", "{ currentPassword, newPassword }"),
        (5, "연동 해제", "DELETE", "/api/me/social/{provider}", "204 또는 409 LAST_LOGIN_METHOD"),
        (6, "연결", "GET", "/api/auth/oauth/{provider}/authorize?mode=&redirect=", "mode=link. 돌아오면 blog.com/me?linked=google"),
        (7, "화면 열 때", "GET", "/api/me/blogs", "내 활성 블로그"),
        (8, "대표로", "PUT", "/api/me/primary-blog", "{ blogId }"),
        (9, "로그아웃", "POST", "/api/auth/logout", "모든 블로그 주소에서 로그아웃, 홈으로"),
    ],
)

page(
    slug="bookmarks", group="회원", title="저장한 글", url="blog.com/me/bookmarks",
    codes=["SOC-03"], chrome="platform",
    lead="본인만 본다. 저장 최신순 20개씩 더보기. 볼 수 없게 된 글도 저장할 때 제목으로 남는다.",
    body=f"""
<nav class="tabs"><a href="mypage.html">내 정보</a><a class="on" href="bookmarks.html">저장한 글</a><a href="notifications.html">알림</a></nav>
<div class="post-list">
  <article class="post-item"><div><h3><a href="post-detail.html">Kafka 컨슈머 랙 줄이기</a></h3><div class="meta"><span>데이터 엔지니어링</span><span>저장 2026.10.08</span></div></div><button class="btn" type="button">저장 취소 {P(2)}</button></article>
  <article class="post-item"><div><h3 class="muted">하프 마라톤 준비 12주 계획</h3><div class="meta"><span>달리는 민수</span><span class="chip">볼 수 없는 글</span><span>저장 2026.09.30</span></div></div><button class="btn" type="button">저장 취소 {P(2)}</button></article>
</div>
<button class="btn more" type="button">더보기 {P(1)}</button>""",
    states=[("볼 수 없는 글을 눌렀을 때", '<div class="box">더 이상 볼 수 없는 글입니다.</div><p class="small muted">이유(삭제·비공개 등)는 알려 주지 않는다.</p>'),
            ("비어 있을 때", '<p class="muted">저장한 글이 없습니다. 글 아래 저장 버튼으로 나중에 읽을 글을 모아 보세요.</p>')],
    apis=[
        (1, "화면 열 때·더보기", "GET", "/api/me/bookmarks?cursor=", "visible=false 항목은 titleSnapshot·blogNameSnapshot만"),
        (2, "저장 취소", "DELETE", "/api/me/bookmarks/{postId}", "목록에서 바로 빠짐"),
    ],
)

page(
    slug="notifications", group="회원", title="알림", url="blog.com/me/notifications",
    codes=["SUB-04"], chrome="platform",
    lead="내 글의 댓글·답글·공감, 새 구독자, 제재·해제 알림. 누르면 읽음 처리 후 그 화면으로 간다.",
    body=f"""
<nav class="tabs"><a href="mypage.html">내 정보</a><a href="bookmarks.html">저장한 글</a><a class="on" href="notifications.html">알림</a></nav>
<div class="row between"><span class="small muted">읽지 않은 알림 2</span><button class="btn" type="button">모두 읽음 {P(3)}</button></div>
<div class="stack">
  <a class="box brand" href="post-detail.html" style="text-decoration:none"><b>하늘님이 "Spring Security 필터 체인 정리"에 댓글을 남겼습니다.</b><span class="small muted">5분 전 {P(2)}</span></a>
  <a class="box brand" href="blog-main.html" style="text-decoration:none"><b>민수님이 지원의 기록을 구독했습니다.</b><span class="small muted">1시간 전</span></a>
  <div class="box"><span>여름님이 "JPA N+1과 fetch join"에 공감했습니다.</span><span class="small muted">어제</span></div>
</div>
<button class="btn more" type="button">더보기 {P(1)}</button>""",
    apis=[
        (1, "화면 열 때·더보기", "GET", "/api/me/notifications?cursor=", "20개씩. 대상이 사라진 알림은 빠짐"),
        (2, "알림 누를 때", "PUT", "/api/me/notifications/{id}/read", "읽음 후 link로 이동"),
        (3, "모두 읽음", "PUT", "/api/me/notifications/read-all", ""),
    ],
)

page(
    slug="withdraw", group="회원", title="회원 탈퇴", url="blog.com/me/withdraw",
    codes=["AUTH-06"], chrome="platform",
    lead="본인 확인(비밀번호 또는 소셜 재인증)과 한 번 더 확인.",
    body=f"""
<div class="page narrow" style="padding:0">
  <h2 style="font-size:22px">회원 탈퇴</h2>
  <div class="box danger"><b>탈퇴하면 되돌릴 수 없습니다</b><span>블로그 2개와 글 51개, 댓글이 모두 삭제됩니다. 블로그 주소는 다시 쓸 수 없고, 누른 공감과 구독도 사라집니다.</span></div>
  <label class="field"><span>비밀번호</span><input type="password" id="wpw"></label>
  <p class="small muted">소셜로 가입했다면 비밀번호 대신 "카카오로 본인 확인" 버튼 {P(1)}</p>
  <label class="row small"><input type="checkbox" id="wok"> 위 내용을 확인했고 탈퇴합니다</label>
  <button class="btn danger" type="button">탈퇴하기 {P(2)}</button>
</div>""",
    apis=[
        (1, "소셜 본인 확인", "GET", "/api/auth/oauth/{provider}/authorize?mode=&redirect=", "mode=reauth. 10분 안에 탈퇴"),
        (2, "탈퇴하기", "DELETE", "/api/me", "{ password } 또는 {}. 204 후 홈으로"),
    ],
)

page(
    slug="blog-create", group="회원", title="블로그 개설", url="blog.com/blogs/new",
    codes=["BLOG-01", "AUTH-04"], chrome="platform",
    lead="블로그가 없는 회원이 글쓰기를 누르거나 가입 직후 오는 화면. 주소는 바꿀 수 없다고 미리 알린다.",
    body=f"""
<div class="page narrow" style="padding:0">
  <h2 style="font-size:22px">블로그 만들기</h2>
  <label class="field"><span>블로그 주소</span><div class="row" style="flex-wrap:nowrap"><input type="text" id="baddr" value="jiwon"><span class="muted">.blog.com</span></div>
    <span class="ok">쓸 수 있는 주소입니다. {P(1)}</span><span class="hint">영문 소문자·숫자·하이픈 4~32자. <b>개설한 뒤에는 주소를 바꿀 수 없습니다.</b></span></label>
  <label class="field"><span>블로그 이름</span><input type="text" id="bname" value="지원의 기록"><span class="hint">1~50자, 나중에 바꿀 수 있습니다</span></label>
  <label class="field"><span>소개 (선택)</span><textarea id="bdesc">백엔드 공부와 여행 메모</textarea></label>
  <button class="btn primary" type="button">만들기 {P(2)}</button>
</div>""",
    states=[("주소 확인 결과", '<p class="err">이미 쓰는 주소입니다. (TAKEN, 삭제된 블로그 주소 포함)</p><p class="err">쓸 수 없는 주소입니다. (RESERVED: www, api, admin…)</p><p class="err">영문 소문자·숫자·하이픈만, 하이픈으로 시작하거나 끝날 수 없습니다. (INVALID)</p>'),
            ("6번째 (409 BLOG_LIMIT_EXCEEDED)", '<p class="err">블로그는 5개까지 만들 수 있습니다.</p>')],
    apis=[
        (1, "주소 입력 후", "GET", "/api/blogs/address-availability?address=", "{ available, reason }"),
        (2, "만들기", "POST", "/api/blogs", "201 후 새 블로그 관리 홈(jiwon.blog.com/manage)으로"),
    ],
)

# ---- 블로그 화면

page(
    slug="blog-main", group="블로그", title="블로그 메인", url="jiwon.blog.com/",
    codes=["BLOG-03", "BLOG-04", "CAT-02", "TAG-02", "SUB-01", "SUB-03", "BLOG-05"], chrome="blog",
    lead="카테고리별(/category/{id})·태그별(/tag/{name}) 목록도 같은 화면에 조건만 붙인다. 목록 형태(리스트/썸네일)는 블로그 꾸미기 값을 따른다.",
    body=f"""
<div class="cols">
  <div class="stack" style="gap:18px">
    <div class="box"><div class="row between"><div class="row"><span class="avatar lg"></span><div><h2 style="font-size:20px">지원의 기록</h2><div class="small muted">백엔드 공부와 여행 메모 · 구독자 18명</div></div></div>
      <button class="btn primary" type="button">구독하기 {P(2)}</button></div></div>
    <div class="row between"><h2 style="font-size:17px">전체 글 <span class="muted num">42</span></h2><span class="small muted">카테고리를 고르면 "개발 (30)", 태그면 "#spring (14)"</span></div>
    <div class="post-list">
      <article class="post-item"><div><h3><a href="post-detail.html">Spring Security 필터 체인 정리</a></h3><p>SecurityFilterChain이 요청을 어떤 순서로 거치는지, 우리 서비스의 JWT 필터는 어디에 넣는지.</p><div class="meta"><span>Spring</span><span>2026.10.08</span><span>공감 5</span><span>댓글 2</span></div></div><div class="thumb"></div></article>
      <article class="post-item"><div><h3><a href="post-detail.html">JPA N+1과 fetch join</a></h3><p>연관 컬렉션을 fetch join하면 페이징이 메모리에서 일어난다.</p><div class="meta"><span>JPA</span><span>2026.10.06</span><span>공감 8</span></div></div><div class="thumb"></div></article>
      <article class="post-item"><div><h3><a href="post-detail.html">제주 3박 4일 동선</a></h3><p>동쪽에서 시작해 시계 방향으로.</p><div class="meta"><span>여행</span><span>2026.10.03</span><span>공감 3</span></div></div><div class="thumb"></div></article>
    </div>
    <nav class="pager"><a href="#">이전</a><a class="on" href="#">1</a><a href="#">2</a><a href="#">3</a><a href="#">4</a><a href="#">5</a><a href="#">다음</a></nav>
    <span class="small muted">{P(1)} 페이지 번호 10개씩 묶음</span>
  </div>
  {blog_sidebar()}
</div>""",
    states=[("글이 없을 때", '<p class="muted">아직 글이 없습니다.</p><p class="small muted">주인에게는 "첫 글 쓰기" 버튼.</p>'),
            ("구독 중일 때", f'<button class="btn on" type="button">구독 중 {P(3)}</button>'),
            ("차단된 회원이 구독 (403 BLOCKED_BY_BLOG)", '<p class="err">이 블로그는 구독할 수 없습니다.</p>')],
    apis=[
        (1, "화면 열 때·페이지", "GET", "/api/posts?page=&size=&categoryId=&tag=", "10개씩. 카테고리·태그 주소면 조건을 붙임"),
        (2, "구독하기", "PUT", "/api/blogs/{blogId}/subscription", "{ subscribed, subscriberCount }로 숫자 갱신. 비회원이면 401 → 로그인"),
        (3, "구독 취소", "DELETE", "/api/blogs/{blogId}/subscription", ""),
    ],
    notes=["이사한 블로그 주소로 들어오면 서버가 화면 주소 단계에서 새 블로그로 301한다. 프론트가 할 일은 없다."],
)

page(
    slug="blog-search", group="블로그", title="블로그 내 검색", url="jiwon.blog.com/search?q=jpa",
    codes=["SRCH-01"], chrome="blog",
    lead="제목·본문·태그에서 찾는다. 10개씩 페이지.",
    body=f"""
<div class="cols">
  <div class="stack">
    <h2 style="font-size:17px">'jpa' 검색 결과 <span class="muted num">9</span> {P(1)}</h2>
    <div class="post-list">
      <article class="post-item"><div><h3><a href="post-detail.html"><mark>JPA</mark> N+1과 fetch join</a></h3><div class="meta"><span>JPA</span><span>2026.10.06</span></div></div><div class="thumb"></div></article>
      <article class="post-item"><div><h3><a href="post-detail.html">영속성 컨텍스트 한 장 정리</a></h3><p>태그: <mark>jpa</mark></p><div class="meta"><span>JPA</span><span>2026.09.28</span></div></div><div class="thumb"></div></article>
    </div>
    <nav class="pager"><a class="on" href="#">1</a></nav>
  </div>
  {blog_sidebar()}
</div>""",
    apis=[(1, "검색·페이지", "GET", "/api/search?q=&page=", "블로그 Host에서 부르면 이 블로그만")],
)

page(
    slug="post-detail", group="블로그", title="글 상세", url="jiwon.blog.com/1532",
    codes=["POST-04", "POST-09", "POST-10", "SOC-01", "SOC-02", "SOC-03", "CMT-01", "CMT-02", "CMT-03", "CMT-05", "CMT-06", "OWN-05", "OWN-06", "ADMIN-04"], chrome="blog",
    lead="글, 사이드바, 댓글을 동시에 부른다. 글 API가 404면 404 화면, 403 SUBSCRIBERS_ONLY면 구독 안내.",
    body=f"""
<div class="cols">
  <article class="stack" style="gap:18px">
    <header class="post-head"><span class="small muted">Spring · IT·개발</span><h1>Spring Security 필터 체인 정리 {P(1)}</h1>
      <div class="meta"><span>지원</span><span>2026.10.08 09:00</span><span>수정 2026.10.08 11:30</span><span>조회 120 {P(2)}</span></div></header>
    <div class="prose"><p>요청 하나가 들어오면 DelegatingFilterProxy가 FilterChainProxy를 부르고, 그 안의 SecurityFilterChain 중 주소가 맞는 하나를 고른다.</p>
      <div class="thumb" style="max-width:420px"></div>
      <pre>http.addFilterBefore(jwtFilter, UsernamePasswordAuthenticationFilter.class);</pre>
      <p>우리 서비스는 쿠키에서 토큰을 꺼내므로 이 위치에 둔다.</p></div>
    <div class="row"><a class="chip" href="blog-main.html">#spring</a><a class="chip" href="blog-main.html">#security</a></div>
    <div class="row">
      <button class="btn on" type="button">공감 5 {P(3)}</button>
      <button class="btn" type="button">저장 {P(4)}</button>
      <button class="btn" type="button">주소 복사</button><button class="btn" type="button">공유</button>
      <span class="grow"></span><button class="btn ghost small" type="button">신고 {P(10)}</button></div>
    <nav class="row between box small"><span>이전 글 <a href="#">JPA N+1과 fetch join</a></span><span class="muted">다음 글 없음</span></nav>
    <section class="section"><h2>'Spring' 카테고리의 다른 글 {P(8)}</h2>
      <ul class="small" style="margin:0;padding-left:18px"><li>Spring Boot 3 마이그레이션 메모</li><li>@Transactional 전파 정리</li></ul></section>
    <section class="section"><h2>비슷한 글 {P(9)}</h2>
      <div class="grid-cards"><div class="card"><div class="thumb"></div><span class="small">JWT를 쿠키에 담을 때 CSRF</span><span class="meta">프론트 노트</span></div><div class="card"><div class="thumb"></div><span class="small">OAuth2 로그인 흐름 그림으로</span><span class="meta">스프링 일기</span></div></div></section>
    <section class="section"><h2>댓글 <span class="muted num">4</span> {P(5)}</h2>
      <div class="comment"><span class="avatar"></span><div><div class="row small"><b>하늘</b><span class="muted">2026.10.08 10:02</span><span class="grow"></span><button class="btn ghost small" type="button">답글</button><button class="btn ghost small" type="button">신고</button></div><div>잘 읽었습니다! addFilterAt과 차이도 궁금해요.</div></div></div>
      <div class="comment reply"><span class="avatar"></span><div><div class="row small"><b>지원</b><span class="chip brand">주인</span><span class="muted">10:20</span><span class="grow"></span><button class="btn ghost small" type="button">수정 {P(7)}</button><button class="btn ghost small" type="button">삭제 {P(11)}</button></div><div>at은 같은 자리에 하나 더 넣는 거예요.</div></div></div>
      <div class="comment"><span class="avatar"></span><div><div class="small gone">비밀댓글입니다.</div></div></div>
      <div class="comment"><span class="avatar"></span><div><div class="small gone">삭제된 댓글입니다.</div></div></div>
      <div class="comment reply"><span class="avatar"></span><div><div class="row small"><b>민수</b><span class="muted">11:02</span></div><div>저도 같은 데서 막혔어요.</div></div></div>
      <button class="btn more" type="button">댓글 더보기</button>
      <div class="box"><textarea id="cnew" aria-label="댓글">좋은 정리 감사합니다</textarea><div class="row between"><label class="row small"><input type="checkbox" id="csecret"> 비밀댓글</label><span class="small muted num">12/1000</span><button class="btn primary" type="button">등록 {P(6)}</button></div></div>
    </section>
  </article>
  {blog_sidebar()}
</div>""",
    states=[
        ("구독자 공개 글, 구독 안 함 (403 SUBSCRIBERS_ONLY)", f'<div class="box brand"><b>구독자 공개 글입니다</b><span>지원의 기록을 구독하면 읽을 수 있어요.</span><button class="btn primary" type="button">구독하기</button></div><p class="small muted">제목·본문은 응답에 없다. detail의 blogName만 쓴다. 사이드바는 그대로.</p>'),
        ("숨긴 글, 작성자 본인", '<div class="box danger"><b>관리자가 숨긴 글입니다</b><span>사유: 저작권 침해 — 다른 사람의 저작물을 허락 없이 올려 숨김 처리되었습니다.</span><span class="small">수정할 수 없고 삭제는 할 수 있습니다.</span></div>'),
        ("주인이 볼 때", f'<div class="row"><select id="pvis" aria-label="공개 범위" style="max-width:140px"><option>공개</option><option selected>비공개</option><option>구독자 공개</option></select>{P(12)}<a class="btn" href="manage-write.html">수정</a><button class="btn danger" type="button">삭제 {P(13)}</button></div><p class="small muted">삭제는 확인 창을 거친다.</p>'),
        ("댓글을 막은 글", '<p class="muted">이 글에는 댓글을 쓸 수 없습니다.</p>'),
        ("댓글 쓰기 실패", '<p class="err">이 블로그에는 댓글을 쓸 수 없습니다. (403 BLOCKED_BY_BLOG)</p><p class="err">쓸 수 없는 단어가 들어 있습니다. (400 BANNED_WORD)</p>'),
        ("신고 창", f'<label class="field"><span>사유</span><select id="rreason"><option>스팸·광고</option><option>음란·유해</option><option>욕설·비방</option><option>저작권 침해</option><option>기타</option></select></label><label class="field"><span>설명 (기타일 때 필수)</span><textarea id="rdesc"></textarea></label><button class="btn danger" type="button">신고 {P(10)}</button><p class="small muted">같은 대상을 다시 신고하면 "이미 신고한 글입니다"(409).</p>'),
    ],
    apis=[
        (1, "화면 열 때", "GET", "/api/posts/{id}", "PostDetail. 404 / 403 SUBSCRIBERS_ONLY 분기"),
        (2, "본문 보인 뒤", "POST", "/api/posts/{id}/views", "조회 기록(5분 중복 제외)"),
        (3, "공감", "PUT", "/api/posts/{id}/like", "다시 누르면 DELETE /api/posts/{id}/like. { liked, likeCount }"),
        (4, "저장", "PUT", "/api/posts/{id}/bookmark", "다시 누르면 DELETE /api/posts/{id}/bookmark"),
        (5, "화면 열 때·더보기", "GET", "/api/posts/{id}/comments?cursor=", "20개씩 작성순, 답글은 부모 안에"),
        (6, "등록", "POST", "/api/posts/{id}/comments", "{ content, parentId, secret } + Idempotency-Key"),
        (7, "수정", "PATCH", "/api/comments/{id}", "본인만"),
        (8, "화면 열 때", "GET", "/api/posts/{id}/same-category?size=5", "같은 카테고리 글"),
        (9, "화면 열 때", "GET", "/api/posts/{id}/similar?size=5", "비슷한 글. 빈 배열이면 섹션 숨김"),
        (10, "신고", "POST", "/api/reports", "{ targetType: POST|COMMENT, targetId, reason, description }"),
        (11, "삭제", "DELETE", "/api/comments/{id}", "본인 또는 주인. 답글이 있으면 '삭제된 댓글입니다'"),
        (12, "주인: 공개 범위", "PATCH", "/api/posts/{id}/visibility", "{ visibility }"),
        (13, "주인: 글 삭제", "DELETE", "/api/posts/{id}", "확인 후 블로그 메인으로"),
    ],
    notes=["공유는 API가 없다. 주소 복사와 SNS 공유 주소 열기만 하고, 미리보기 메타 태그는 서버가 화면 주소 단계에서 넣는다.",
           "주인에게는 공개 범위와 상관없이 본문이 보인다."],
)

page(
    slug="guestbook", group="블로그", title="방명록", url="jiwon.blog.com/guestbook",
    codes=["CMT-04", "MNG-04"], chrome="blog",
    lead="댓글과 같은 규칙(비밀·답글 한 단계·차단·금칙어). 20개씩 페이지 번호.",
    body=f"""
<div class="cols">
  <div class="stack">
    <div class="box"><textarea id="gnew" aria-label="방명록">블로그 잘 보고 있어요!</textarea><div class="row between"><label class="row small"><input type="checkbox" id="gsecret"> 비밀글</label><button class="btn primary" type="button">남기기 {P(2)}</button></div></div>
    <div class="comment"><span class="avatar"></span><div><div class="row small"><b>여름</b><span class="muted">2026.10.07</span><span class="grow"></span><button class="btn ghost small" type="button">수정 {P(3)}</button><button class="btn ghost small" type="button">삭제 {P(4)}</button></div><div>제주 글 보고 다녀왔어요. 동선 최고!</div></div></div>
    <div class="comment reply"><span class="avatar"></span><div><div class="row small"><b>지원</b><span class="chip brand">주인</span></div><div>와 다녀오셨군요 :)</div></div></div>
    <div class="comment"><span class="avatar"></span><div><div class="small gone">비밀글입니다.</div></div></div>
    <nav class="pager"><a class="on" href="#">1</a><a href="#">2</a></nav><span class="small muted">{P(1)}</span>
  </div>
  {blog_sidebar()}
</div>""",
    apis=[
        (1, "화면 열 때·페이지", "GET", "/api/guestbook?page=", "20개씩 최신순"),
        (2, "남기기", "POST", "/api/guestbook", "{ content, parentId, secret } + Idempotency-Key. 차단 403, 금칙어 400"),
        (3, "수정", "PATCH", "/api/guestbook/{id}", "본인만"),
        (4, "삭제", "DELETE", "/api/guestbook/{id}", "본인 또는 주인"),
    ],
)

# ---- 블로그 관리

page(
    slug="manage-home", group="블로그 관리", title="관리 홈", url="jiwon.blog.com/manage",
    codes=["MNG-03", "ADMIN-05"], chrome="manage", active="manage-home",
    lead="방문자 요약과 최근 댓글·글. 주인이 아니면 403 화면.",
    body=f"""
<div class="stat-row">
  <div class="stat"><span class="small muted">오늘 방문자</span><b>37</b></div>
  <div class="stat"><span class="small muted">어제</span><b>52</b></div>
  <div class="stat"><span class="small muted">누적</span><b>4,318</b></div>
</div><span class="small muted">{P(1)} 주인 본인 방문은 세지 않음</span>
<div class="cols" style="grid-template-columns:minmax(0,1fr) minmax(0,1fr)">
  <section class="section"><h2>최근 댓글</h2><div class="stack small"><div>하늘 · 잘 읽었습니다! addFilterAt과… <span class="muted">Spring Security 필터 체인 정리</span></div><div>민수 · fetch join 페이징은요? <span class="muted">JPA N+1과 fetch join</span></div></div><a class="small" href="manage-comments.html">댓글 관리</a></section>
  <section class="section"><h2>최근 글</h2><div class="stack small"><div>Spring Security 필터 체인 정리 <span class="muted">조회 120</span></div><div>JPA N+1과 fetch join <span class="muted">조회 88</span></div></div><a class="small" href="manage-posts.html">글 관리</a></section>
</div>""",
    states=[("이용 제한된 블로그 (공통 B의 restriction)", '<div class="box danger"><b>이 블로그는 이용이 제한되었습니다</b><span>사유: 스팸·광고 — 광고성 글이 반복되어 다른 사람에게 보이지 않습니다.</span></div>')],
    apis=[(1, "화면 열 때", "GET", "/api/manage/stats", "today, yesterday, total, 최근 댓글·글 5")],
)

page(
    slug="manage-write", group="블로그 관리", title="글쓰기", url="jiwon.blog.com/manage/write",
    codes=["POST-01", "POST-02", "POST-05", "POST-06", "POST-07", "POST-08", "POST-11", "POST-13", "TAG-01", "CMT-07"], chrome="manage", active="manage-write",
    lead="새 글은 /manage/write, 수정은 /manage/write/{id}. 1분마다 자동 임시저장.",
    body=f"""
<div class="row between"><span class="small muted">자동 저장됨 10:41 {P(5)}</span><div class="row"><a class="btn" href="manage-posts.html">임시저장 목록 3 {P(7)}</a><button class="btn" type="button">임시저장 {P(4)}</button><button class="btn primary" type="button">발행 {P(4)}</button></div></div>
<input type="text" id="wtitle" value="Spring Security 필터 체인 정리" aria-label="제목" style="font-size:20px;font-weight:600">
<div class="row"><select id="wcat" aria-label="카테고리" style="max-width:200px"><option>미분류</option><option selected>개발 / Spring</option></select>{P(2)}
  <select id="wtopic" aria-label="주제" style="max-width:200px"><option>주제 없음</option><option selected>IT·개발</option></select>{P(3)}</div>
<div><div class="editor-bar"><button class="btn" type="button">문단 제목</button><button class="btn" type="button"><b>굵게</b></button><button class="btn" type="button"><i>기울임</i></button><button class="btn" type="button">목록</button><button class="btn" type="button">인용</button><button class="btn" type="button">코드</button><button class="btn" type="button">링크</button><button class="btn" type="button">이미지 {P(6)}</button></div>
  <div class="editor-area"><p>요청 하나가 들어오면 DelegatingFilterProxy가…</p><div class="row"><div class="thumb" style="width:200px"></div><span class="chip brand">대표 이미지</span></div><p>우리 서비스는 쿠키에서 토큰을 꺼내므로…</p></div></div>
<label class="field"><span>태그 (최대 10개)</span><input type="text" id="wtags" value="spring, security"></label>
<div class="box"><b>발행 설정</b>
  <div class="row"><label class="row small"><input type="radio" name="vis" id="v1" checked> 공개</label><label class="row small"><input type="radio" name="vis" id="v2"> 비공개</label><label class="row small"><input type="radio" name="vis" id="v3"> 구독자 공개</label></div>
  <div class="row"><label class="row small"><input type="checkbox" id="wsched"> 예약 발행</label><input type="datetime-local" id="wat" value="2026-10-09T09:00" style="max-width:220px"></div>
  <label class="row small"><input type="checkbox" id="wcmt" checked> 댓글 허용</label></div>""",
    states=[("수정 화면 열 때", f'<p class="small">{P(1)} 편집용 글을 불러온다. 숨긴 글이면 사유 띠와 함께 저장 버튼이 꺼진다(403 POST_BLINDED).</p>'),
            ("발행 검증", '<p class="err">제목을 입력해 주세요.</p><p class="err">태그는 10개까지 달 수 있습니다.</p>'),
            ("이미지 거절", '<p class="err">jpg, png, gif, webp만 올릴 수 있습니다.</p><p class="err">10MB 이하 파일만 올릴 수 있습니다.</p>'),
            ("구독자 공개를 아직 못 고를 때", '<p class="small muted">SUB-01을 만들기 전(1주차)에는 "구독자 공개" 칸을 숨긴다.</p>')],
    apis=[
        (1, "수정 화면 열 때", "GET", "/api/manage/posts/{id}", "본문·상태·숨김 사유"),
        (2, "화면 열 때", "GET", "/api/categories", "카테고리 고르기(주인이라 비공개 카테고리 포함)"),
        (3, "화면 열 때", "GET", "/api/topics", "주제 10개"),
        (4, "발행·임시저장", "POST", "/api/posts", "새 글. status PUBLISHED / DRAFT / SCHEDULED + Idempotency-Key. 발행 후 글 주소로"),
        (5, "1분마다·수정 저장", "PUT", "/api/posts/{id}", "처음 저장 뒤에는 이 경로. 자동 저장은 status DRAFT일 때만"),
        (6, "이미지 넣기", "POST", "/api/images", "{ id, url, thumbnailUrl }을 본문에 넣음"),
        (7, "임시저장 목록", "GET", "/api/manage/posts?status=&visibility=&categoryId=&q=&page=", "status=DRAFT"),
    ],
)

page(
    slug="manage-posts", group="블로그 관리", title="글 관리", url="jiwon.blog.com/manage/posts",
    codes=["MNG-01", "POST-03", "POST-06", "POST-08", "ADMIN-03", "BLOG-06"], chrome="manage", active="manage-posts",
    lead="상태·공개 범위·카테고리 필터와 검색, 일괄 공개 범위 변경·삭제. 20개씩.",
    body=f"""
<div class="row"><select id="fstatus" style="max-width:140px" aria-label="상태"><option>전체 상태</option><option>발행</option><option>임시저장</option><option>예약</option></select>
<select id="fcat" style="max-width:160px" aria-label="카테고리"><option>전체 카테고리</option></select>
<input type="search" id="fq" placeholder="제목 검색" style="max-width:220px">{P(1)}</div>
<div class="row"><span class="small muted">2개 선택</span><select id="bvis" style="max-width:160px" aria-label="공개 범위"><option>비공개로</option><option>공개로</option><option>구독자 공개로</option></select><button class="btn" type="button">적용 {P(2)}</button><button class="btn danger" type="button">삭제 {P(3)}</button><a class="btn" href="manage-settings.html#move">다른 블로그로 옮기기 {P(4)}</a></div>
<div class="table-wrap"><table><thead><tr><th></th><th>제목</th><th>상태</th><th>공개</th><th>카테고리</th><th class="num">날짜</th></tr></thead><tbody>
<tr><td><input type="checkbox" id="c1" checked aria-label="선택"></td><td><a href="manage-write.html">Spring Security 필터 체인 정리</a></td><td><span class="chip brand">발행</span></td><td>공개</td><td>Spring</td><td class="num">10.08</td></tr>
<tr><td><input type="checkbox" id="c2" checked aria-label="선택"></td><td>JPA N+1과 fetch join</td><td><span class="chip brand">발행</span></td><td>구독자</td><td>JPA</td><td class="num">10.06</td></tr>
<tr><td><input type="checkbox" id="c3" aria-label="선택"></td><td>가을 사진 모음 <span class="chip danger">숨김: 저작권 침해</span></td><td><span class="chip brand">발행</span></td><td>공개</td><td>여행</td><td class="num">10.05</td></tr>
<tr><td><input type="checkbox" id="c4" aria-label="선택"></td><td class="muted">(제목 없음)</td><td><span class="chip">임시저장</span></td><td>—</td><td>미분류</td><td class="num">10.08</td></tr>
<tr><td><input type="checkbox" id="c5" aria-label="선택"></td><td>MySQL 인덱스 2편</td><td><span class="chip warn">예약 10.09 09:00</span></td><td>공개</td><td>개발</td><td class="num">—</td></tr>
</tbody></table></div>
<nav class="pager"><a class="on" href="#">1</a><a href="#">2</a><a href="#">3</a></nav>""",
    states=[("삭제 확인", '<div class="box warn">선택한 글 2개를 삭제할까요? 댓글과 공감도 함께 사라집니다. <div class="row"><button class="btn danger" type="button">삭제</button><button class="btn" type="button">취소</button></div></div>')],
    apis=[
        (1, "화면 열 때·필터", "GET", "/api/manage/posts?status=&visibility=&categoryId=&q=&page=", "숨긴 글은 blind 사유 포함"),
        (2, "적용", "PATCH", "/api/manage/posts", "{ postIds, visibility }"),
        (3, "삭제", "DELETE", "/api/manage/posts", "{ postIds }"),
        (4, "옮기기", "POST", "/api/blog/move-posts", "블로그 설정의 이사 칸에서 대상 블로그를 고른 뒤"),
    ],
)

page(
    slug="manage-comments", group="블로그 관리", title="댓글·방명록 관리", url="jiwon.blog.com/manage/comments",
    codes=["MNG-02", "CMT-02", "MNG-04"], chrome="manage", active="manage-comments",
    lead="받은 댓글과 방명록. 삭제, 답글 바로 쓰기, 작성자 차단.",
    body=f"""
<nav class="tabs"><a class="on" href="#">댓글 {P(1)}</a><a href="#">방명록 {P(1)}</a></nav>
<div class="stack">
  <div class="box"><div class="row between small"><span><b>하늘</b> · Spring Security 필터 체인 정리 · 10.08 10:02</span><span class="row"><button class="btn ghost" type="button">답글</button><button class="btn ghost" type="button">삭제 {P(3)}</button><button class="btn ghost" type="button">차단 {P(4)}</button></span></div><div>잘 읽었습니다! addFilterAt과 차이도 궁금해요.</div>
    <div class="row" style="flex-wrap:nowrap"><input type="text" id="rr" value="at은 같은 자리에 하나 더 넣는 거예요." aria-label="답글"><button class="btn primary" type="button">답글 {P(2)}</button></div></div>
  <div class="box"><div class="row between small"><span><b>광고봇</b> · JPA N+1과 fetch join · 10.08 03:12</span><span class="row"><button class="btn ghost" type="button">삭제</button><button class="btn ghost" type="button">차단</button></span></div><div>최저가 보장 ○○몰 바로가기</div></div>
</div>
<nav class="pager"><a class="on" href="#">1</a></nav>""",
    apis=[
        (1, "화면 열 때·탭", "GET", "/api/manage/comments?type=comment|guestbook&page=", "20개씩 최신순"),
        (2, "답글", "POST", "/api/posts/{id}/comments", "parentId를 붙여 쓴다. 방명록이면 POST /api/guestbook"),
        (3, "삭제", "DELETE", "/api/comments/{id}", "방명록이면 DELETE /api/guestbook/{id}"),
        (4, "차단", "POST", "/api/manage/blocked-members", "{ memberId }. 그 회원의 구독도 지움"),
    ],
)

page(
    slug="manage-categories", group="블로그 관리", title="카테고리·태그", url="jiwon.blog.com/manage/categories",
    codes=["CAT-01", "CAT-03", "CAT-04", "CAT-05", "TAG-03", "TAG-04"], chrome="manage", active="manage-categories",
    lead="카테고리는 2단계까지, 드래그로 순서와 상하위를 바꾼 뒤 한 번에 저장한다.",
    body=f"""
<section class="section"><h2>카테고리 {P(1)}</h2>
  <div class="stack">
    <div class="box"><div class="row between"><span>⋮⋮ <b>개발</b> <span class="muted num">30</span></span><span class="row"><button class="btn ghost" type="button">이름 변경 {P(3)}</button><button class="btn ghost" type="button">비공개</button><button class="btn ghost" type="button">삭제 {P(4)}</button></span></div>
      <div class="stack" style="padding-left:24px">
        <div class="row between"><span>⋮⋮ Spring <span class="muted num">12</span></span><span class="row"><button class="btn ghost" type="button">이름 변경</button><button class="btn ghost" type="button">삭제</button></span></div>
        <div class="row between"><span>⋮⋮ JPA <span class="muted num">9</span> <span class="chip warn">비공개</span></span><span class="row"><button class="btn ghost" type="button">이름 변경</button><button class="btn ghost" type="button">삭제</button></span></div></div></div>
    <div class="box"><div class="row between"><span>⋮⋮ <b>여행</b> <span class="muted num">9</span></span><span class="row"><button class="btn ghost" type="button">이름 변경</button><button class="btn ghost" type="button">삭제</button></span></div></div>
    <div class="row"><input type="text" id="newcat" placeholder="새 카테고리 이름 (1~30자)" style="max-width:260px"><button class="btn" type="button">추가 {P(2)}</button><span class="grow"></span><button class="btn primary" type="button">순서 저장 {P(5)}</button></div>
  </div></section>
<section class="section"><h2>태그 {P(6)}</h2>
  <div class="table-wrap"><table><thead><tr><th>태그</th><th class="num">글 수</th><th></th></tr></thead><tbody>
  <tr><td>spring</td><td class="num">14</td><td><button class="btn ghost" type="button">이름 변경 {P(7)}</button><button class="btn ghost" type="button">삭제 {P(8)}</button></td></tr>
  <tr><td>jpa</td><td class="num">9</td><td><button class="btn ghost" type="button">이름 변경</button><button class="btn ghost" type="button">삭제</button></td></tr>
  </tbody></table></div></section>""",
    states=[("삭제 거절", '<p class="err">하위 카테고리가 있어 삭제할 수 없습니다. 하위를 먼저 옮기거나 지워 주세요. (409)</p>'),
            ("삭제 확인", '<div class="box warn">"여행"을 삭제하면 글 9개가 미분류로 옮겨집니다.</div>'),
            ("이름 중복", '<p class="err">같은 이름이 이미 있습니다. (409 NAME_TAKEN)</p>')],
    apis=[
        (1, "화면 열 때", "GET", "/api/categories", "트리, 주인이라 비공개 포함"),
        (2, "추가", "POST", "/api/categories", "{ name, parentId }"),
        (3, "이름 변경·비공개", "PATCH", "/api/categories/{id}", "{ name } 또는 { isPrivate }"),
        (4, "삭제", "DELETE", "/api/categories/{id}", "글은 미분류로"),
        (5, "순서 저장", "PUT", "/api/categories/order", "[{ id, parentId, sortOrder }] 전체"),
        (6, "화면 열 때", "GET", "/api/tags", "글 수순"),
        (7, "이름 변경", "PATCH", "/api/tags/{id}", "{ name }"),
        (8, "삭제", "DELETE", "/api/tags/{id}", "글은 남는다"),
    ],
)


def visitor_chart() -> str:
    vals = [41, 38, 55, 62, 47, 33, 29, 44, 58, 71, 66, 52, 49, 37]
    w, h, pad, top = 560, 180, 30, 10
    step = (w - pad - 10) / (len(vals) - 1)
    ymax = 80
    pts = [(pad + i * step, top + (h - top - 24) * (1 - v / ymax)) for i, v in enumerate(vals)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    base = h - 24
    area = f"{pad},{base} " + line + f" {pts[-1][0]:.1f},{base}"
    ticks = "".join(
        f'<line class="axis" x1="{pad}" x2="{w - 10}" y1="{top + (base - top) * (1 - t / ymax):.1f}" y2="{top + (base - top) * (1 - t / ymax):.1f}"/>'
        f'<text class="lbl" x="{pad - 6}" y="{top + (base - top) * (1 - t / ymax) + 4:.1f}" text-anchor="end">{t}</text>'
        for t in (0, 40, 80)
    )
    days = ["9/25", "9/28", "10/1", "10/4", "10/7"]
    labels = "".join(
        f'<text class="lbl" x="{pts[i * 3][0]:.1f}" y="{h - 6}" text-anchor="middle">{d}</text>'
        for i, d in enumerate(days)
    )
    last = pts[-1]
    return (
        f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="최근 14일 일별 방문자 수">{ticks}'
        f'<polygon class="area" points="{area}"/><polyline class="line" points="{line}"/>'
        f'<circle class="dot" cx="{last[0]:.1f}" cy="{last[1]:.1f}" r="4"/>{labels}</svg>'
    )


page(
    slug="manage-stats", group="블로그 관리", title="방문 통계", url="jiwon.blog.com/manage/stats",
    codes=["MNG-03"], chrome="manage", active="manage-stats",
    lead="어제까지의 통계는 매일 새벽에 모은 값. 일·주·월 단위 그래프, 인기 글, 유입 경로.",
    body=f"""
<section class="section"><h2>방문자 {P(1)} <small>최근 14일 · 일별</small></h2>
  <nav class="tabs"><a class="on" href="#">일</a><a href="#">주</a><a href="#">월</a></nav>
  <div class="chart">{visitor_chart()}</div></section>
<div class="cols" style="grid-template-columns:minmax(0,1fr) minmax(0,1fr)">
  <section class="section"><h2>인기 글 {P(2)}</h2><nav class="tabs"><a class="on" href="#">누적</a><a href="#">최근 7일</a></nav>
    <div class="rank-list"><div class="rank"><b>1</b><span>제주 3박 4일 동선</span><span class="small muted num">1,204</span></div><div class="rank"><b>2</b><span>JPA N+1과 fetch join</span><span class="small muted num">880</span></div><div class="rank"><b>3</b><span>Spring Security 필터 체인 정리</span><span class="small muted num">120</span></div></div></section>
  <section class="section"><h2>유입 경로 {P(3)}</h2>
    <div class="table-wrap"><table><thead><tr><th>종류</th><th>사이트</th><th class="num">방문</th></tr></thead><tbody>
    <tr><td>검색</td><td>google.com</td><td class="num">312</td></tr><tr><td>검색</td><td>search.naver.com</td><td class="num">188</td></tr>
    <tr><td>직접</td><td>—</td><td class="num">140</td></tr><tr><td>블로그 안</td><td>blog.com</td><td class="num">96</td></tr><tr><td>SNS</td><td>x.com</td><td class="num">21</td></tr></tbody></table></div></section>
</div>""",
    apis=[
        (1, "화면 열 때·단위", "GET", "/api/manage/stats/visitors?unit=day|week|month&from=&to=", "[{ date, visitorCount, viewCount }]"),
        (2, "화면 열 때·탭", "GET", "/api/manage/stats/popular-posts?range=all|7d", "10위까지"),
        (3, "화면 열 때", "GET", "/api/manage/stats/referrers?from=&to=", "종류별·사이트별"),
    ],
)

page(
    slug="manage-settings", group="블로그 관리", title="블로그 설정", url="jiwon.blog.com/manage/settings",
    codes=["BLOG-02", "BLOG-05", "BLOG-06", "BLOG-07", "BLOG-08"], chrome="manage", active="manage-settings",
    lead="블로그 정보, 꾸미기, 이사, 삭제. 주소는 바꿀 수 없어 보여 주기만 한다.",
    body=f"""
<section class="section"><h2>블로그 정보</h2>
  <div class="row"><span class="avatar lg"></span><button class="btn" type="button">이미지 바꾸기 {P(1)}</button></div>
  <label class="field"><span>주소</span><input type="text" id="saddr" value="jiwon.blog.com" disabled><span class="hint">주소는 바꿀 수 없습니다.</span></label>
  <label class="field"><span>이름</span><input type="text" id="sname" value="지원의 기록"></label>
  <label class="field"><span>소개</span><textarea id="sdesc">백엔드 공부와 여행 메모</textarea></label>
  <button class="btn primary" type="button" style="justify-self:start">저장 {P(2)}</button></section>
<section class="section"><h2>꾸미기</h2>
  <div class="row"><label class="row small"><input type="radio" name="skin" id="sk1" checked> 기본</label><label class="row small"><input type="radio" name="skin" id="sk2"> 매거진</label><label class="row small"><input type="radio" name="skin" id="sk3"> 노트</label></div>
  <div class="row"><label class="row small"><input type="radio" name="lay" id="l1" checked> 리스트</label><label class="row small"><input type="radio" name="lay" id="l2"> 썸네일</label></div>
  <button class="btn" type="button" style="justify-self:start">적용 {P(3)}</button></section>
<section class="section" id="move"><h2>블로그 이사</h2>
  <p class="small muted">글을 옮기면 카테고리는 미분류가 되고 태그는 이름으로 다시 연결됩니다. 옛 글 주소는 새 블로그로 이어집니다.</p>
  <label class="field"><span>대상 블로그</span><select id="mto"><option>지원 여행기 (jiwon-travel)</option></select></label>{P(4)}
  <div class="row"><button class="btn" type="button">이 블로그를 대상 블로그로 이사 지정 {P(5)}</button><button class="btn ghost" type="button">지정 취소 {P(6)}</button></div>
  <span class="small muted">글 고르기는 글 관리에서 (POST /api/blog/move-posts)</span></section>
<section class="section"><h2>블로그 삭제</h2>
  <div class="box danger"><b>옮기지 않은 글 33개가 함께 삭제됩니다. {P(7)}</b><span>주소 jiwon은 다시 쓸 수 없습니다. 대표 블로그는 대표를 바꾼 뒤에 삭제할 수 있습니다.</span>
    <label class="field"><span>확인을 위해 주소를 입력하세요</span><input type="text" id="dconfirm" placeholder="jiwon"></label>
    <button class="btn danger" type="button" style="justify-self:start">삭제 {P(8)}</button></div></section>""",
    states=[("대표 블로그 (409 PRIMARY_BLOG)", '<p class="err">대표 블로그는 삭제할 수 없습니다. 마이페이지에서 대표를 바꿔 주세요.</p>')],
    apis=[
        (1, "이미지 고를 때", "POST", "/api/images", ""),
        (2, "저장", "PATCH", "/api/blog", "{ name, description, profileImageId }"),
        (3, "적용", "PUT", "/api/blog/appearance", "{ skin, listLayout }"),
        (4, "화면 열 때", "GET", "/api/me/blogs", "이사 대상 후보(이 블로그 제외)"),
        (5, "이사 지정", "PUT", "/api/blog/moved-to", "{ targetBlogId }"),
        (6, "지정 취소", "DELETE", "/api/blog/moved-to", ""),
        (7, "화면 열 때", "GET", "/api/blog/deletion-preview", "{ remainingPostCount, isPrimary }"),
        (8, "삭제", "DELETE", "/api/blog", "{ confirmAddress }. 204 후 마이페이지로"),
    ],
)

page(
    slug="manage-spam", group="블로그 관리", title="스팸·차단", url="jiwon.blog.com/manage/spam",
    codes=["MNG-04"], chrome="manage", active="manage-spam",
    lead="차단 회원과 금칙어. 차단 사실은 상대에게 따로 알리지 않는다.",
    body=f"""
<section class="section"><h2>차단한 회원 {P(1)}</h2>
  <div class="table-wrap"><table><thead><tr><th>회원</th><th>메모</th><th class="num">차단일</th><th></th></tr></thead><tbody>
  <tr><td>광고봇</td><td>광고 댓글 반복</td><td class="num">10.08</td><td><button class="btn ghost" type="button">해제 {P(2)}</button></td></tr></tbody></table></div>
  <span class="small muted">차단은 댓글·방명록 관리에서 작성자를 골라 한다.</span></section>
<section class="section"><h2>금칙어 <small class="num">3 / 100</small> {P(3)}</h2>
  <div class="row"><span class="chip">최저가 <button class="btn ghost" type="button" aria-label="삭제">× {P(5)}</button></span><span class="chip">바로가기 <button class="btn ghost" type="button" aria-label="삭제">×</button></span><span class="chip">카지노 <button class="btn ghost" type="button" aria-label="삭제">×</button></span></div>
  <div class="row"><input type="text" id="bw" placeholder="금칙어 (30자까지)" style="max-width:240px"><button class="btn" type="button">추가 {P(4)}</button></div>
  <span class="small muted">새로 쓰는 댓글·방명록에만, 대소문자를 무시하고 검사한다.</span></section>""",
    states=[("한도", '<p class="err">금칙어는 100개까지 등록할 수 있습니다.</p>')],
    apis=[
        (1, "화면 열 때", "GET", "/api/manage/blocked-members?page=", ""),
        (2, "해제", "DELETE", "/api/manage/blocked-members/{memberId}", ""),
        (3, "화면 열 때", "GET", "/api/manage/banned-words", ""),
        (4, "추가", "POST", "/api/manage/banned-words", "{ word }. 중복·100개 초과 409"),
        (5, "삭제", "DELETE", "/api/manage/banned-words/{id}", ""),
    ],
)

# ---- 서비스 관리

page(
    slug="admin-dashboard", group="서비스 관리", title="관리 대시보드", url="blog.com/admin",
    codes=["ADMIN-01", "ADMIN-06"], chrome="admin", active="admin-dashboard",
    lead="서비스 관리자만. 일반 회원이 주소를 직접 쳐도 403 화면.",
    body=f"""
<div class="stat-row"><div class="stat"><span class="small muted">오늘 가입</span><b>14</b></div><div class="stat"><span class="small muted">오늘 새 글</span><b>63</b></div><div class="stat"><span class="small muted">처리 대기 신고</span><b>5</b></div></div>
<span class="small muted">{P(1)}</span>
<section class="section"><h2>최근 제재</h2><div class="table-wrap"><table><thead><tr><th>시각</th><th>조치</th><th>대상</th><th>사유</th><th>관리자</th></tr></thead><tbody>
<tr><td class="num">10.08 09:40</td><td>블라인드</td><td>글 1488</td><td>저작권 침해</td><td>운영팀</td></tr>
<tr><td class="num">10.07 22:15</td><td>정지 30일</td><td>회원 광고봇</td><td>스팸·광고</td><td>운영팀</td></tr></tbody></table></div></section>""",
    apis=[(1, "화면 열 때", "GET", "/api/admin/dashboard", "")],
)

page(
    slug="admin-members", group="서비스 관리", title="회원 관리", url="blog.com/admin/members",
    codes=["ADMIN-02"], chrome="admin", active="admin-members",
    lead="이메일·닉네임 검색과 상태 필터. 행을 누르면 상세와 정지·해제.",
    body=f"""
<div class="row"><input type="search" id="amq" placeholder="이메일 또는 닉네임" style="max-width:260px"><select id="ams" style="max-width:140px" aria-label="상태"><option>전체</option><option>활동</option><option>정지</option><option>탈퇴</option></select>{P(1)}</div>
<div class="table-wrap"><table><thead><tr><th>닉네임</th><th>이메일</th><th>상태</th><th class="num">가입일</th></tr></thead><tbody>
<tr><td>광고봇</td><td>ad@spam.test</td><td><span class="chip danger">정지 ~11.07</span></td><td class="num">10.01</td></tr>
<tr><td>하늘</td><td>(소셜 가입)</td><td><span class="chip brand">활동</span></td><td class="num">09.12</td></tr></tbody></table></div>
<div class="box"><div class="row between"><b>광고봇 상세 {P(2)}</b><span class="small muted">가입 2026.10.01 · 블로그 1 · 받은 신고 7</span></div>
  <div class="small">제재 이력: 10.07 정지 30일 (스팸·광고)</div>
  <div class="row"><select id="aperiod" style="max-width:120px" aria-label="기간"><option>7일</option><option selected>30일</option><option>영구</option></select><select id="areason" style="max-width:160px" aria-label="사유"><option>스팸·광고</option><option>음란·유해</option><option>욕설·비방</option><option>저작권 침해</option><option>기타</option></select><button class="btn danger" type="button">정지 {P(3)}</button><button class="btn" type="button">정지 해제 {P(4)}</button></div></div>""",
    apis=[
        (1, "검색·필터", "GET", "/api/admin/members?q=&status=&page=", ""),
        (2, "행 누를 때", "GET", "/api/admin/members/{id}", "가입일, 블로그, 받은 신고 수, 제재 이력"),
        (3, "정지", "POST", "/api/admin/members/{id}/suspension", "{ period, reason, reasonDetail }"),
        (4, "해제", "DELETE", "/api/admin/members/{id}/suspension", ""),
    ],
)

page(
    slug="admin-reports", group="서비스 관리", title="신고 처리", url="blog.com/admin/reports",
    codes=["ADMIN-04", "ADMIN-03", "ADMIN-05"], chrome="admin", active="admin-reports",
    lead="처리 대기 신고를 대상별로 묶어 신고 수 많은 순. 결과를 하나 고르면 그 대상의 신고가 모두 처리된다.",
    body=f"""
<div class="table-wrap"><table><thead><tr><th>대상 {P(1)}</th><th class="num">신고</th><th>사유</th><th class="num">처음 신고</th></tr></thead><tbody>
<tr><td>글 · 가을 사진 모음 (jiwon)</td><td class="num">7</td><td>저작권 침해 6, 기타 1</td><td class="num">10.07</td></tr>
<tr><td>댓글 · 최저가 보장 ○○몰…</td><td class="num">4</td><td>스팸·광고 4</td><td class="num">10.08</td></tr>
<tr><td>블로그 · casino-win</td><td class="num">2</td><td>스팸·광고 2</td><td class="num">10.08</td></tr></tbody></table></div>
<div class="box"><b>글 · 가을 사진 모음 {P(2)}</b>
  <ul class="small" style="margin:0;padding-left:18px"><li>여름 · 저작권 침해 · 10.07</li><li>민수 · 기타 "출처 없이 퍼 온 사진" · 10.07</li></ul>
  <div class="row"><label class="row small"><input type="radio" name="res" id="r1" checked> 블라인드</label><label class="row small"><input type="radio" name="res" id="r2"> 블로그 이용 제한</label><label class="row small"><input type="radio" name="res" id="r3"> 작성자 정지</label><label class="row small"><input type="radio" name="res" id="r4"> 기각</label></div>
  <div class="row"><select id="rres" style="max-width:160px" aria-label="사유"><option selected>저작권 침해</option></select><button class="btn primary" type="button">처리 {P(3)}</button></div></div>""",
    notes=["신고 없이 바로 숨기거나 해제할 때는 POST·DELETE /api/admin/posts/{id}/blind, /api/admin/comments/{id}/blind, /api/admin/blogs/{id}/restriction을 쓴다(글·댓글 상세의 관리자 메뉴)."],
    apis=[
        (1, "화면 열 때", "GET", "/api/admin/reports?status=PENDING&page=", "대상별 묶음"),
        (2, "행 누를 때", "GET", "/api/admin/reports/{targetType}/{targetId}", "신고 목록"),
        (3, "처리", "POST", "/api/admin/reports/{targetType}/{targetId}/resolve", "{ result, reason, reasonDetail, period }"),
    ],
)

page(
    slug="admin-logs", group="서비스 관리", title="관리 이력·공지", url="blog.com/admin/logs",
    codes=["ADMIN-06"], chrome="admin", active="admin-logs",
    lead="관리 이력은 조회만. 공지는 작성·수정·삭제.",
    body=f"""
<section class="section"><h2>관리 이력 {P(1)}</h2>
  <div class="row"><select id="lt" style="max-width:140px" aria-label="대상"><option>전체 대상</option><option>글</option><option>댓글</option><option>블로그</option><option>회원</option></select><input type="date" id="lf" value="2026-10-01" style="max-width:160px"><input type="date" id="lto" value="2026-10-08" style="max-width:160px"></div>
  <div class="table-wrap"><table><thead><tr><th>시각</th><th>관리자</th><th>조치</th><th>대상</th><th>사유</th></tr></thead><tbody>
  <tr><td class="num">10.08 09:40</td><td>운영팀</td><td>BLIND</td><td>POST 1488</td><td>저작권 침해</td></tr>
  <tr><td class="num">10.08 09:41</td><td>운영팀</td><td>REJECT_REPORT</td><td>REPORT 블로그 casino-win</td><td>—</td></tr></tbody></table></div></section>
<section class="section"><h2>공지 쓰기</h2>
  <label class="field"><span>제목</span><input type="text" id="nt" value="10월 정기 점검 안내"></label>
  <label class="field"><span>내용</span><textarea id="nc">10월 12일 02:00부터 04:00까지…</textarea></label>
  <div class="row"><button class="btn primary" type="button">등록 {P(2)}</button><button class="btn" type="button">수정 {P(3)}</button><button class="btn danger" type="button">삭제 {P(4)}</button></div></section>""",
    apis=[
        (1, "화면 열 때·검색", "GET", "/api/admin/moderation-logs?targetType=&targetId=&adminId=&from=&to=&page=", ""),
        (2, "등록", "POST", "/api/admin/notices", "{ title, content }"),
        (3, "수정", "PUT", "/api/admin/notices/{id}", ""),
        (4, "삭제", "DELETE", "/api/admin/notices/{id}", ""),
    ],
)

# ---- 공통

page(
    slug="errors", group="공통", title="오류 화면", url="(어느 주소든)",
    codes=["COM-01", "COM-02"], chrome="bare",
    lead="404·403·로그인 안내·예상하지 못한 오류. 볼 수 없는 글·블로그는 로그인 여부와 상관없이 404.",
    body="""
<div class="states">
  <div class="state"><span class="state-label">404</span><h3>페이지를 찾을 수 없습니다</h3><p class="muted">주소가 바뀌었거나 볼 수 없는 페이지입니다.</p><a class="btn" href="home.html">홈으로</a></div>
  <div class="state"><span class="state-label">403</span><h3>접근 권한이 없습니다</h3><p class="muted">이 화면은 블로그 주인만 볼 수 있습니다.</p><a class="btn" href="home.html">홈으로</a></div>
  <div class="state"><span class="state-label">401</span><h3>로그인이 필요합니다</h3><p class="muted">로그인하면 보던 화면으로 돌아옵니다.</p><a class="btn primary" href="login.html">로그인</a></div>
  <div class="state"><span class="state-label">500</span><h3>잠시 문제가 생겼습니다</h3><p class="muted">잠시 후 다시 시도해 주세요.</p><p class="small muted">스택·SQL 같은 내부 정보는 보이지 않는다.</p></div>
  <div class="state"><span class="state-label">입력 오류 400</span><label class="field"><span>제목</span><input type="text" id="e1" value=""><span class="err">제목을 입력해 주세요.</span></label><p class="small muted">fieldErrors로 어느 칸인지 알리고 입력값은 그대로 둔다.</p></div>
</div>""",
    apis=[],
    notes=["모든 API의 오류 본문은 { code, message, fieldErrors, detail } 모양이다(contracts/rest-api.md 오류 본문).",
           "API가 401을 주면 프론트는 지금 주소를 redirect에 담아 blog.com/login으로 보낸다."],
)


# ---------------------------------------------------------------- 렌더링

CHROME_COMMON = {
    "platform": PLATFORM_COMMON, "platform-guest": PLATFORM_COMMON[:1],
    "blog": BLOG_COMMON, "blog-guest": BLOG_COMMON,
    "manage": MANAGE_COMMON, "admin": ADMIN_COMMON, "bare": [],
}


def addr_of(p) -> str:
    u = p["url"]
    return u if u.startswith("(") else "https://" + u


def wrap_chrome(p) -> str:
    c = p["chrome"]
    if c in ("platform", "platform-guest"):
        head = platform_head(p["active"], logged=(c == "platform"))
        return head + f'<main class="page">{p["body"]}</main>'
    if c in ("blog", "blog-guest"):
        return blog_head(logged=(c == "blog")) + f'<main class="page">{p["body"]}</main>'
    if c == "manage":
        return manage_head() + f'<div class="manage">{manage_nav(p["active"])}<main class="page">{p["body"]}</main></div>'
    if c == "admin":
        return admin_head() + f'<div class="manage">{admin_nav(p["active"])}<main class="page">{p["body"]}</main></div>'
    return f'<main class="page">{p["body"]}</main>'


def api_rows(p):
    return [(str(n), w, m, path, d) for n, w, m, path, d in CHROME_COMMON[p["chrome"]]] + [
        (str(n), w, m, path, d) for n, w, m, path, d in p["apis"]
    ]


def render_page(p) -> str:
    codes = "".join(f'<span class="code">{c}</span>' for c in p["codes"])
    states = ""
    if p["states"]:
        states = '<section class="section"><h2>다른 상태</h2><div class="states">' + "".join(
            f'<div class="state"><span class="state-label">{esc(label)}</span>{h}</div>' for label, h in p["states"]
        ) + "</div></section>"
    rows = api_rows(p)
    if rows:
        trs = "".join(
            f'<tr id="api-{n}"><td>{P(n)}</td><td>{esc(w)}</td><td><span class="method">{m}</span> {esc(path)}</td><td>{esc(d)}</td></tr>'
            for n, w, m, path, d in rows
        )
        api = (
            '<section class="api"><h2>이 화면이 부르는 API</h2>'
            '<p class="small muted">화면의 파란 번호가 아래 줄이다. 글자 번호(A, B, C)는 같은 틀의 화면이 모두 부르는 공통 API다. '
            '경로와 응답은 <a href="../contracts/rest-api.md">REST API 명세</a>를 따른다.</p>'
            '<div class="table-wrap"><table><thead><tr><th>#</th><th>언제</th><th>요청</th><th>메모</th></tr></thead>'
            f"<tbody>{trs}</tbody></table></div></section>"
        )
    else:
        api = ""
    notes = ""
    if p["notes"]:
        notes = '<ul class="notes">' + "".join(f"<li>{esc(n)}</li>" for n in p["notes"]) + "</ul>"
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(p["title"])} 목업</title>
{FONTS}
<link rel="stylesheet" href="assets/mock.css">
</head>
<body>
<div class="wrap">
  <div class="mockbar"><a class="back" href="index.html">← 화면 목록</a><h1>{esc(p["title"])}</h1><span class="url">{esc(p["url"])}</span><div class="codes">{codes}</div></div>
  <p class="lead">{esc(p["lead"])}</p>
  <div class="frame"><div class="frame-top"><div class="dots"><i></i><i></i><i></i></div><div class="addr">{esc(addr_of(p))}</div></div>
  {wrap_chrome(p)}
  </div>
  {states}
  {api}
  {notes}
</div>
</body>
</html>
"""


GROUPS = ["플랫폼", "회원", "블로그", "블로그 관리", "서비스 관리", "공통"]


def render_index() -> str:
    parts = []
    for g in GROUPS:
        rows = "".join(
            f'<tr><td><a href="{p["slug"]}.html">{esc(p["title"])}</a></td><td><span class="url">{esc(p["url"])}</span></td>'
            f'<td>{" ".join(f"<span class=code>{c}</span>" for c in p["codes"])}</td><td class="num">{len(api_rows(p))}</td></tr>'
            for p in PAGES if p["group"] == g
        )
        parts.append(
            f'<section class="index-group"><h2>{g}</h2><div class="table-wrap"><table><thead><tr><th>화면</th><th>주소</th><th>기능</th><th class="num">API</th></tr></thead>'
            f"<tbody>{rows}</tbody></table></div></section>"
        )
    total_api = len({path.split("?")[0] + m for p in PAGES for _, _, m, path, _ in api_rows(p)})
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>블로그 화면 목업</title>
{FONTS}
<link rel="stylesheet" href="assets/mock.css">
</head>
<body>
<div class="wrap">
  <div class="mockbar"><h1>티스토리형 블로그 화면 목업</h1><span class="url">specs/001-tistory-blog/mockups</span></div>
  <p class="lead">화면 {len(PAGES)}개와 각 화면이 부르는 API(서로 다른 요청 {total_api}개)를 이어 둔 정적 목업이다. 화면 안의 파란 번호를 누르면 그 화면 아래 API 표의 줄로 간다. 화면은 휴대폰 너비(360px)에서도 가로 스크롤 없이 보이게 만들었다.</p>
  {"".join(parts)}
  <p class="foot">기능 코드는 <a href="../spec.md">기능 명세</a>, 경로와 응답은 <a href="../contracts/rest-api.md">REST API 명세</a>를 따른다. 이 목록과 화면은 <code>build.py</code>로 만든다.</p>
</div>
</body>
</html>
"""


def render_readme() -> str:
    lines = [
        "# 화면 목업",
        "",
        "> **이 문서는?** 지원 서비스의 화면 목업 목록과, 화면마다 부르는 API다. 목업은 정적 HTML이라 브라우저로 `index.html`을 열면 바로 보인다. API 경로와 응답 규칙은 [REST API 명세](../contracts/rest-api.md)에, 전체 문서 안내는 [README](../../../README.md)에 있다.",
        "",
        "## 보는 법",
        "",
        "- `index.html`을 브라우저로 연다. 화면 안의 파란 번호를 누르면 그 화면 아래 API 표의 줄로 간다.",
        "- 글자 번호(A, B, C)는 같은 틀을 쓰는 화면이 모두 부르는 공통 API다(로그인 상태, 블로그 정보, 사이드바).",
        "- 각 화면 아래 **다른 상태**에 빈 목록, 오류 문구, 권한별로 달라지는 부분을 모았다.",
        "",
        "## 고치는 법",
        "",
        "HTML은 `build.py`가 만든다. 화면을 고치려면 `build.py`의 `PAGES`를 고치고 다시 실행한다. 실행하면 화면에 적은 API 경로가 REST API 명세에 모두 있는지도 확인한다.",
        "",
        "```bash",
        "python3 specs/001-tistory-blog/mockups/build.py",
        "```",
        "",
        "## 화면 주소",
        "",
        "기능 명세와 원본 6장에 있는 주소(`/`, `/login`, `/signup`, `/admin/...`, `/{글 번호}`, `/category/{id}`, `/tag/{이름}`, `/manage/...`) 말고는 목업을 만들며 정했다. 아래 표의 나머지 주소(`/feed`, `/ranking/...`, `/me/...`, `/blogs/new`, `/guestbook`, `/search`, `/manage/` 아래 세부 경로 등)는 바꿔도 된다.",
        "",
        "## 화면별 API",
        "",
    ]
    for g in GROUPS:
        lines += [f"### {g}", "", "| 화면 | 주소 | 기능 | 부르는 API |", "| --- | --- | --- | --- |"]
        for p in PAGES:
            if p["group"] != g:
                continue
            apis = "<br>".join(
                f"`{m} {path}`" for _, _, m, path, _ in api_rows(p)
            ) or "없음"
            lines.append(
                f"| [{p['title']}]({p['slug']}.html) | `{p['url']}` | {', '.join(p['codes'])} | {apis.replace('|', '&#124;')} |"
            )
        lines.append("")
    return "\n".join(lines)


def check_api_paths() -> list[str]:
    doc = API_DOC.read_text(encoding="utf-8")
    missing = []
    for p in PAGES:
        for _, _, m, path, _ in api_rows(p):
            base = path.split("?")[0]
            if base not in doc:
                missing.append(f"{p['slug']}: {m} {base}")
    return missing


def main() -> None:
    for p in PAGES:
        (HERE / f"{p['slug']}.html").write_text(render_page(p), encoding="utf-8")
    (HERE / "index.html").write_text(render_index(), encoding="utf-8")
    (HERE / "README.md").write_text(render_readme(), encoding="utf-8")
    missing = check_api_paths()
    print(f"화면 {len(PAGES)}개를 만들었다.")
    if missing:
        print("REST API 명세에 없는 경로:")
        for m in missing:
            print("  -", m)
        raise SystemExit(1)
    print("모든 API 경로가 REST API 명세에 있다.")


if __name__ == "__main__":
    main()
