# 58. 방문 통계: 하루 한 번 세기, 새벽에 모으기, 다시 돌려도 같은 작업

> 관련 스텝: [스텝 20](../step-20.md) (T082·T083·T085 방문 통계, T079 조회 기록 정리) · 관련 개념: [52 예약 작업과 프록시 자기 호출](./52-scheduled-jobs-proxy.md)(`@Scheduled`), [36 집계 쿼리로 순위 매기기](./36-ranking-aggregation.md)(`GROUP BY`·`UNION ALL`), [34 조회수](./34-view-count.md), [18 SPA와 서버 라우팅](./18-spa-server-routing.md)(화면 주소 요청), [10 HTTP 쿠키](./10-http-cookies.md)

## 1. 이 문서로 배우는 것

- "방문자 수"를 무엇으로 셀지 정하기: 요청 수, 조회 수, 하루 방문자(순 방문자)
- 원본 기록(`blog_visit`)과 **모아 둔 표**(`blog_daily_stat`, `blog_referrer_daily`)를 나누는 이유
- **멱등한 배치 작업**: "지우고 다시 넣기"와 "다시 계산하기"로 두 번 돌려도 같은 결과
- 오늘(아직 모으지 않은 날)과 어제까지(모아 둔 날)를 합쳐 보여 주기
- `Referer` 헤더로 유입 경로 나누기와 그 한계
- 그래프의 빈 칸을 0으로 채우기, 일·주·월 칸 만들기
- SPA에서 "방문"을 서버가 아는 곳

## 2. 왜 필요한가

명세 MNG-03: "블로그 주인은 관리 홈에서 오늘·어제·누적 방문자 수를 보고, 통계 화면에서 일·주·월 방문자 그래프, 인기 글(누적·최근 7일), 유입 경로(검색·SNS·직접 등)를 본다. 주인 본인의 방문은 세지 않는다."

조회수(스텝 8)는 **글** 단위였다. 방문 통계는 **블로그** 단위이고, 날짜별로 쌓여 그래프가 된다. 방문이 쌓이는 속도는 글보다 훨씬 빠르다. 매번 원본을 다 세면 블로그가 커질수록 관리 화면이 느려진다.

## 3. 기본 개념

### 3.1 무엇을 "방문자"로 세나

| 지표 | 정의 | 이 프로젝트 |
| --- | --- | --- |
| 페이지뷰(요청 수) | 화면을 연 횟수. 새로고침도 하나 | 세지 않음 |
| 글 조회 수 | 글을 연 횟수, 같은 사람 5분 안 중복 제외(스텝 8) | `view_log`로, 그래프의 "조회" |
| **하루 방문자(순 방문자)** | 그날 그 블로그에 온 서로 다른 사람 수 | `blog_visit`, 그래프의 "방문자" |

"서로 다른 사람"은 조회 기록과 같은 **방문자 키**로 정한다(`VisitorKeys`): 로그인했으면 `m:{회원 번호}`, 아니면 방문자 쿠키의 임의 값으로 `a:{값}`. 쿠키를 지우거나 다른 브라우저로 오면 다른 사람으로 센다. 비회원으로 왔다가 같은 날 로그인하면 키가 바뀌어 두 명이 된다. 웹 통계는 원래 이 정도의 근사값이다.

### 3.2 원본과 요약

```
blog_visit (원본, 7일만)              blog_daily_stat (요약, 계속)
blog  date   visitor  type   host      blog  date   visitors  views
1     10/10  m:5      SEARCH google    1     10/10  2         7
1     10/10  a:x1     DIRECT           1     10/09  …
1     10/11  a:x1     SNS    x.com
```

- **원본**은 한 사람 한 줄이라 크다. 하지만 유입 경로처럼 "다시 나눠 보고 싶은 것"이 남아 있다.
- **요약**은 블로그·날짜마다 한 줄이라 작다. 1년 그래프도 365줄이면 된다.
- 매일 새벽 원본을 요약으로 모으고, 오래된 원본은 지운다. 데이터 창고(DW)·로그 분석에서 흔한 방식이고, 명세 R-14가 정한 구조다.

### 3.3 하루 한 번: UNIQUE + INSERT IGNORE

`blog_visit`에 `UNIQUE(blog_id, visit_date, visitor_key)`가 있다. 방문마다 `INSERT IGNORE`를 하면 그날 첫 방문만 행이 되고 나머지는 0행으로 끝난다. "오늘 이 사람이 왔었나?"를 따로 찾을 필요가 없고 동시에 들어와도 한 줄이다([56](./56-bookmark-snapshot.md) 3.2와 같은 방법).

그래서 **유입 경로는 그날 첫 방문의 것**이 남는다. 아침에 구글 검색으로 왔다가 오후에 즐겨찾기로 오면 "검색" 한 번이다.

### 3.4 멱등한 배치: 몇 번 돌려도 같은 결과

새벽 작업을 "어제 방문 수를 누적에 **더하기**"로 만들면 생기는 일:

- 작업이 실수로 두 번 돌면(서버 재시작, 사람이 손으로 한 번 더) 어제가 두 번 더해진다.
- 서버가 꺼져 있던 날은 영영 빠진다.

그래서 이 프로젝트의 작업은 **더하지 않는다**.

1. 그날 요약 행을 **지우고 다시 넣는다**(`DELETE` → `INSERT … SELECT`). 몇 번 해도 그날 행은 원본에서 다시 계산한 한 벌이다.
2. 어제 하루가 아니라 **지난 7일**을 다시 모은다. 원본을 7일 남기므로 7일 안의 어느 날이 빠졌어도 다음 새벽에 채워진다.
3. 누적 방문자는 "어제를 더하기"가 아니라 **요약 표의 합으로 다시 계산**한다.

이런 작업을 **멱등한 배치(idempotent batch)**라고 한다. 배치 작업은 실패·재시도·중복 실행이 늘 생기므로, "다시 돌려도 안전한가?"가 가장 먼저 물을 질문이다.

### 3.5 오늘은 바로, 어제까지는 요약에서

요약은 새벽에만 만들어지므로 오늘 값은 요약에 없다. 화면은 둘을 합친다.

```
관리 홈의 "오늘"  = blog_visit에서 오늘 행 수(바로 셈)
          "어제"  = blog_daily_stat의 어제 행
          "누적"  = blog.total_visitor_count(요약 합) + 오늘
그래프           = 요약 행 + 오늘 칸만 바로 센 값
```

오늘 하루치 원본을 세는 일은 블로그 하나·하루 하나라 가볍다(인덱스의 앞 칸이 `blog_id, visit_date`).

### 3.6 Referer로 유입 경로 나누기

브라우저는 링크를 눌러 다른 페이지로 갈 때 `Referer` 헤더에 **앞 페이지 주소**를 보낸다(철자가 틀린 채로 표준이 됐다).

| Referer | 분류 |
| --- | --- |
| 없음 | 직접(DIRECT): 주소를 쳤거나 즐겨찾기, 앱에서 열기 |
| `blog.com`이나 `*.blog.com` | 블로그 안(INTERNAL): 이 서비스의 다른 화면에서 |
| `google.com`, `search.naver.com` … | 검색(SEARCH) |
| `x.com`, `facebook.com`, `kakao.com` … | SNS |
| 그 밖 | 기타(OTHER) |

한계를 알고 써야 한다.

- 요즘 브라우저의 기본 정책(`Referrer-Policy: strict-origin-when-cross-origin`)은 다른 사이트로 갈 때 **경로 없이 도메인만** 보낸다. 그래서 검색어는 알 수 없고, 도메인으로만 나눈다.
- HTTPS 페이지에서 HTTP 페이지로 가면 아예 보내지 않는다. 사이트가 `no-referrer`를 걸면 보내지 않는다. 이런 방문은 "직접"으로 잡힌다. 그래서 "직접"은 실제보다 많게 나온다.
- 헤더는 누구나 지어 보낼 수 있다. 통계용이지 보안 판단에 쓰면 안 된다.

### 3.7 SPA에서 "방문"은 어디서 아나

React 앱(SPA)에서는 첫 화면만 서버에서 받고, 그 뒤의 화면 이동은 브라우저 안에서 일어난다([18](./18-spa-server-routing.md)). 그래서 서버가 확실히 아는 순간은 **블로그 주소로 화면(index.html)을 달라는 요청**이다.

- 이 프로젝트는 그 요청을 받는 `SpaForwardController`에서 방문을 남긴다. 블로그를 처음 열거나 새로고침할 때다.
- 블로그 안에서 글을 눌러 이동하는 것은 세지 않는다. 그건 같은 날 같은 사람이라 어차피 하루 한 번으로 묶인다.
- 다른 방법은 화면이 열릴 때 프론트가 "방문했음" API를 부르는 것이다(Google Analytics가 이 방식). 자바스크립트가 꺼진 크롤러는 안 세지는 장점이 있지만 API가 하나 늘고, 화면마다 부르는 것을 빠뜨리기 쉽다.

## 4. 동작 원리

```
[방문] GET http://gap.blog.com/20  (화면 주소, Referer: https://www.google.com/)
  → SpaForwardController: 블로그 확인 → 글 확인(볼 수 있음) → visited(…)
      → VisitRecorder.record: 주인 본인? → 넘어감
           ReferrerType.classify(Referer, "blog.com") → (SEARCH, "google.com")
           INSERT IGNORE blog_visit(blog, 오늘, "m:7", SEARCH, "google.com")
  ← index.html (방문 기록이 실패해도 화면은 그대로)

[새벽 0:10] StatsAggregator.run()   (@Scheduled cron, 한 트랜잭션)
  for 7일 전 … 어제:
     DELETE blog_daily_stat WHERE stat_date = d
     INSERT blog_daily_stat SELECT … (blog_visit 행 수 + view_log 조회 수) GROUP BY blog
     DELETE blog_referrer_daily WHERE stat_date = d
     INSERT blog_referrer_daily SELECT … GROUP BY blog, type, host
  UPDATE blog JOIN (SELECT blog_id, SUM(visitor_count) … GROUP BY blog_id) SET total_visitor_count
  DELETE blog_visit WHERE visit_date < 오늘 − 7일
  DELETE view_log  WHERE viewed_at  < 지금 − 7일 − 1시간

[관리 화면] GET /api/manage/stats/visitors?unit=week
  → 요약 행(from~to) + 오늘은 바로 센 값 → 날짜마다 그 주 월요일 칸에 더함 → 빈 칸 0
  ← [{ date: "2026-07-27", visitorCount, viewCount }, … 12칸]
```

## 5. 이 프로젝트에서는

### 5.1 방문 남기기: `manage/application/VisitRecorder`

```java
public void record(Blog blog, HttpServletRequest request, HttpServletResponse response) {
    if (blog.isOwnedBy(LoginMembers.currentId())) {
        return;
    }
    try {
        ReferrerType.Classified referrer = ReferrerType.classify(request.getHeader(HttpHeaders.REFERER),
                domainProperties.platform());
        blogStatsRepository.recordVisit(blog.getId(), LocalDate.now(clock), visitorKeys.resolve(request, response),
                referrer.type(), referrer.host());
    } catch (RuntimeException e) {
        log.warn("방문 기록 실패 blog={}", blog.getId(), e);
    }
}
```

- 줄 2: **주인 본인은 세지 않는다**(명세). 주인은 자기 블로그를 가장 자주 여는 사람이라, 세면 통계가 주인 방문으로 채워진다.
- `try … catch`: 통계는 **부가 기능**이다. DB가 잠깐 느리거나 값이 이상해 기록이 실패해도 방문자는 블로그를 봐야 한다. 실패는 로그로만 남긴다. 반대로 글 저장 같은 본 기능에서 오류를 삼키면 안 된다.
- `visitorKeys.resolve(request, response)`: 방문자 쿠키가 없으면 새로 만들어 응답에 싣는다. 그래서 `response`를 넘긴다.
- `LocalDate.now(clock)`: 날짜는 서버 시간대(Asia/Seoul) 기준이다. 자정 직전과 직후의 방문은 다른 날이다.

`SpaForwardController`는 정상 화면을 줄 때만 이것을 부른다.

```java
case PostAccess.Visible visible -> visited(blog, request, response, postPage(request, blog, postId));
case PostAccess.SubscribersOnly subscribersOnly -> visited(blog, request, response, app(HttpStatus.OK));
…
return isManagePath(path) ? app(HttpStatus.OK) : visited(blog, request, response, app(HttpStatus.OK));
```

404 화면, 301 이동, 관리 화면(`/manage/**`)은 방문이 아니다. 구독자 공개 글은 내용은 못 봐도 블로그에 온 것이니 센다.

### 5.2 유입 나누기: `manage/domain/ReferrerType.classify`

```java
public static Classified classify(String referer, String platform) {
    if (referer == null || referer.isBlank()) {
        return new Classified(DIRECT, "");
    }
    String host;
    try {
        host = URI.create(referer.strip()).getHost();
    } catch (IllegalArgumentException e) {
        return new Classified(DIRECT, "");
    }
    …
    host = host.toLowerCase(Locale.ROOT);
    if (host.startsWith("www.")) {
        host = host.substring(4);
    }
    if (host.length() > 100) {
        host = host.substring(0, 100);
    }
    String platformHost = platform.toLowerCase(Locale.ROOT);
    if (host.equals(platformHost) || host.endsWith("." + platformHost)) {
        return new Classified(INTERNAL, host);
    }
    if (matches(host, SEARCH_HOSTS)) { return new Classified(SEARCH, host); }
    if (matches(host, SNS_HOSTS))    { return new Classified(SNS, host); }
    return new Classified(OTHER, host);
}
```

- **헤더는 아무 값이나 올 수 있다.** `URI.create`가 실패하면(공백, 이상한 글자) 직접으로 본다. 예외가 밖으로 나가면 방문 기록 전체가 실패한다.
- `www.`를 떼어 `www.google.com`과 `google.com`을 한 사이트로 센다.
- 100자로 자르는 것은 DB 칸(`referrer_host VARCHAR(100)`) 때문이다. 자르지 않으면 긴 호스트 하나로 INSERT가 실패한다.
- 블로그 안 판단에 `endsWith("." + platform)`을 쓴다. `contains("blog.com")`이면 `evilblog.com`도 블로그 안이 된다.
- 검색 목록의 `"google."`처럼 점으로 끝나는 항목은 `google.co.kr`, `google.com`을 한꺼번에 잡으려는 것이다(`matches`가 앞부분이나 `.google.`로 비교).

### 5.3 모으기: `manage/domain/BlogStatsRepository.aggregateDay`

```java
public void aggregateDay(LocalDate date) {
    jdbc.update("DELETE FROM blog_daily_stat WHERE stat_date = ?", date);
    jdbc.update("""
            INSERT INTO blog_daily_stat (blog_id, stat_date, visitor_count, view_count)
            SELECT blog_id, ?, SUM(visitors), SUM(views) FROM (
                SELECT blog_id, COUNT(*) AS visitors, 0 AS views FROM blog_visit WHERE visit_date = ? GROUP BY blog_id
                UNION ALL
                SELECT p.blog_id, 0, COUNT(*) FROM view_log l JOIN post p ON p.id = l.post_id
                WHERE l.viewed_at >= ? AND l.viewed_at < ? GROUP BY p.blog_id
            ) t GROUP BY blog_id""", date, date, date.atStartOfDay(), date.plusDays(1).atStartOfDay());
    …
}
```

- **지우고 넣기**(3.4). 같은 날을 열 번 모아도 결과는 한 벌이다.
- 방문자와 조회를 따로 센 뒤 `UNION ALL`로 붙이고 블로그마다 `SUM`한다([36](./36-ranking-aggregation.md)과 같은 모양). 방문은 있는데 조회가 없는 블로그(블로그 메인만 본 날)와, 조회는 있는데 방문이 없는 블로그(주인만 글을 본 날, 주인은 방문에서 빠짐) 둘 다 한 줄이 된다. `JOIN`으로 붙이면 한쪽만 있는 블로그가 빠진다.
- 하루의 범위는 `[그날 0시, 다음 날 0시)`, 끝을 **포함하지 않는다**. `BETWEEN 0시 AND 23:59:59`로 쓰면 `23:59:59.5`에 생긴 조회(이 DB는 마이크로초까지 저장)가 빠진다.
- 엔티티를 쓰지 않고 `JdbcTemplate`으로 SQL을 바로 쓴다. 행 하나를 읽고 고치는 일이 없고 모으고 세는 일뿐이라, 엔티티를 거치면 행을 메모리에 모두 올려야 한다. `JdbcTemplate`도 같은 DB 연결을 쓰므로 `@Transactional` 안에서는 JPA와 같은 트랜잭션이다.

누적 다시 계산:

```java
public void refreshTotals() {
    jdbc.update("""
            UPDATE blog b JOIN (SELECT blog_id, SUM(visitor_count) AS total FROM blog_daily_stat GROUP BY blog_id) s
              ON s.blog_id = b.id
            SET b.total_visitor_count = s.total, b.updated_at = b.updated_at""");
}
```

- MySQL의 **여러 테이블 UPDATE**(`UPDATE … JOIN`)다. 스텝 19의 수치 맞추기([54](./54-theme-move-delete-withdraw.md))와 같은 문법이다.
- `b.updated_at = b.updated_at`: `blog.updated_at`에 `ON UPDATE CURRENT_TIMESTAMP`가 걸려 있어, 아무것도 안 하면 통계 작업이 모든 블로그의 "수정 시각"을 새벽 0시 10분으로 바꾼다. 같은 값을 직접 넣으면 MySQL이 자동 갱신을 하지 않는다. 스텝 18의 숨김에서 배운 것과 같다([53](./53-admin-moderation-audit.md)).

### 5.4 작업: `manage/application/StatsAggregator`

```java
@Scheduled(cron = "${app.scheduling.stats-cron:0 10 0 * * *}")
@Transactional
public void run() {
    LocalDate today = LocalDate.now(clock);
    for (int back = KEEP_DAYS; back >= 1; back--) {
        blogStatsRepository.aggregateDay(today.minusDays(back));
    }
    blogStatsRepository.refreshTotals();
    int visits = blogStatsRepository.deleteVisitsBefore(today.minusDays(KEEP_DAYS));
    // 블로거 순위는 "정시 기준 7일"을 보므로 지금 기준 7일보다 최대 1시간 앞의 기록까지 필요하다
    int views = blogStatsRepository.deleteViewsBefore(LocalDateTime.now(clock).minusDays(KEEP_DAYS).minusHours(1));
    log.info("통계 모으기 끝: 지운 방문 기록 {}행, 조회 기록 {}행", visits, views);
}
```

- cron `0 10 0 * * *`: 초 분 시 일 월 요일 순서다(Spring은 초가 맨 앞). 매일 0시 10분. 자정 바로 다음이 아니라 10분 뒤인 이유는, 자정 직전에 시작한 요청이 끝나 어제 기록이 다 들어올 시간을 주려는 것이다.
- `@Transactional`이 `run()`에 있다. 스케줄러는 프록시를 통해 `run()`을 부르므로 여기서 트랜잭션이 시작된다. 안쪽 메서드에 걸면 자기 호출이라 안 걸린다([52](./52-scheduled-jobs-proxy.md) 3.4, 스텝 17에서 겪은 버그).
- 한 트랜잭션이라 중간에 실패하면 모두 되돌아간다. "요약은 지웠는데 다시 넣지 못한" 상태가 남지 않는다.
- **순서**: 모으기 → 누적 → 지우기. 지우기를 먼저 하면 7일 전 날을 모을 원본이 없다.
- 조회 기록(`view_log`)도 여기서 지운다(T079). 조회 기록은 인기 글(1시간)과 인기 블로거(7일, [59](./59-hourly-snapshot-ranking.md))에만 쓰인다. 블로거 순위는 "정시까지의 7일"을 보는데 정시는 지금보다 최대 1시간 앞이라 1시간을 더 남긴다. 글의 누적 조회 수는 `post.view_count`에 따로 있어 기록을 지워도 그대로다.

### 5.5 그래프: 빈 칸 채우기와 주·월 칸

```java
Map<LocalDate, long[]> buckets = new LinkedHashMap<>();
for (LocalDate date = from; !date.isAfter(to); date = date.plusDays(1)) {
    LocalDate key = switch (unit) {
        case "week" -> date.with(TemporalAdjusters.previousOrSame(DayOfWeek.MONDAY));
        case "month" -> date.withDayOfMonth(1);
        default -> date;
    };
    long[] sums = buckets.computeIfAbsent(key, k -> new long[2]);
    BlogStatsRepository.Day day = days.get(date);
    if (day != null) {
        sums[0] += day.visitors();
        sums[1] += day.views();
    }
}
```

- 날짜를 **하루씩 다 돌며** 칸을 만든다. DB는 방문이 있는 날만 행이 있으므로 DB 결과만 쓰면 그래프에서 날짜가 빠진다(10/3, 10/5, 10/9처럼 띄엄띄엄). 빈 날은 0으로 둔다.
- 주 칸의 이름은 그 주 **월요일**, 월 칸은 1일이다. `TemporalAdjusters.previousOrSame(MONDAY)`: 오늘이 월요일이면 오늘, 아니면 지난 월요일.
- `LinkedHashMap`: 넣은 순서(날짜 순)를 지킨다. `HashMap`이면 칸 순서가 섞인다.
- 기간은 400일까지다. 아주 긴 기간을 요청해 서버가 수만 칸을 만드는 것을 막는다.
- 기본 기간은 일 14칸, 주 12칸, 월 12칸이다.

### 5.6 화면

- **관리 홈**(`pages/manage/ManageHomePage.tsx`): 오늘·어제·누적 숫자와 최근 댓글 5·최근 글 5. 비밀·숨김·삭제 댓글은 내용 대신 "비밀댓글입니다." 같은 상태 문구로(확인 중에 "(내용 없음)"으로 보이던 것을 고침).
- **방문 통계**(`pages/manage/ManageStatsPage.tsx`, `/manage/stats`, 관리 메뉴 "통계 › 방문 통계"): 일·주·월 탭, 막대 그래프, 인기 글(누적·최근 7일 탭), 유입 경로(종류별 칩과 사이트별 표).
- 막대 그래프는 차트 라이브러리 없이 **CSS grid와 div 높이**로 그렸다. 칸이 최대 14~12개라 라이브러리를 들일 이유가 없다. 높이 계산은 `app/stats.ts`의 순수 함수 `barHeights`(가장 큰 값 = 100%, 값이 있으면 최소 2%)로 떼어 Vitest로 시험한다. Thymeleaf로 치면 `th:style="'height:' + ${h} + 'px'"`로 막대를 그리는 것과 같다.
- 그래프에는 `role="img"`와 `aria-label`을 달아 화면 낭독기가 "방문자 막대 그래프"로 읽게 했다.

### 5.7 테스트: `StatsIntegrationTest.visitsAreCountedOncePerDayExceptOwnerAndAggregatedAtNight`

1. 독자가 구글 Referer로 블로그 메인, 이어 글 화면 → 주인이 메인과 관리 화면 → `blog_visit`에는 **SEARCH 한 줄**만(하루 한 번, 주인 제외, 첫 방문의 유입).
2. 관리 홈 `today = 1`, 주인이 아니면 403.
3. 어제 방문 둘(직접·SNS)·조회 하나, 10일 전 방문 하나를 SQL로 넣고 **작업을 두 번** 돌린다.
4. 어제 요약 `visitor_count = 2`, 누적 `2`(두 번 돌렸어도 4가 아님), 10일 전 원본은 지워짐.
5. 관리 홈 `yesterday = 2`, `total = 3`(누적 2 + 오늘 1). 그래프 14칸, 끝에서 두 번째가 어제(2, 조회 1), 마지막이 오늘(1). 월 단위 12칸, `unit=year`는 400. 유입 경로에 SEARCH·DIRECT·SNS와 `google.com` 1. 인기 글 7일·누적.

## 6. 자주 하는 실수와 함정

- **누적에 "더하기"**: 작업이 두 번 돌면 두 번 더해지고, 빠진 날은 영영 빠진다. 다시 계산한다.
- **지우기를 모으기보다 먼저**: 모을 원본이 사라진다.
- **안쪽 메서드에 `@Transactional`**: 스케줄러가 부르는 입구에 건다.
- **하루 범위를 `BETWEEN … 23:59:59`로**: 소수 초 기록이 빠진다. `[0시, 다음 날 0시)`.
- **DB 결과만으로 그래프**: 방문 없는 날이 빠져 x축이 띄엄띄엄해진다. 날짜를 다 돌며 0으로 채운다.
- **`ON UPDATE CURRENT_TIMESTAMP`를 잊음**: 통계 작업이 모든 블로그의 수정 시각을 바꾼다.
- **Referer를 믿음**: 지어 보낼 수 있고, 없으면 "직접"이 부풀려진다. 통계에만 쓴다.
- **`contains(platform)`으로 내부 판단**: `evilblog.com`도 내부가 된다. 같거나 `"." + platform`으로 끝나는지.
- **방문 기록 실패로 화면 오류**: 부가 기능의 실패는 삼키고 로그로.
- **주인 방문을 셈**: 통계가 주인 방문으로 채워진다.
- **테스트에서 DB의 `NOW()`로 시각을 넣음**: 테스트 DB 컨테이너는 UTC, 애플리케이션은 한국 시간이라 9시간 어긋난다. 자바에서 시각을 만들어 넣는다(이번 스텝 랭킹 테스트에서 겪음, [59](./59-hourly-snapshot-ranking.md) 5.6).

## 7. 직접 해 보기

준비: 갑(블로그 주인), 다른 브라우저(또는 시크릿 창).

1. 시크릿 창으로 갑의 블로그를 연다. 여러 번 새로고침한다.
2. 갑으로 관리 홈 → 오늘 방문자 1.
3. DB:

   ```sql
   SELECT blog_id, visit_date, visitor_key, referrer_type, referrer_host FROM blog_visit ORDER BY id DESC LIMIT 5;
   ```

4. 유입 경로를 바꿔 본다(브라우저는 헤더를 직접 못 바꾸므로 curl로).

   ```bash
   curl -s -o /dev/null -H 'Host: gap.blog.test' -H 'Referer: https://search.naver.com/search.naver?query=blog' http://localhost:8080/
   ```

5. 새벽 작업을 바로 돌려 보고 싶으면 설정으로 cron을 바꿔 띄운다(1분마다).

   ```bash
   ./mvnw spring-boot:run -Dspring-boot.run.arguments=--app.scheduling.stats-cron="0 * * * * *"
   ```

   로그 `통계 모으기 끝: …`를 보고 `SELECT * FROM blog_daily_stat ORDER BY stat_date DESC LIMIT 5;`. 두 번 돌아도 숫자가 그대로인지 본다.
6. 관리 → 통계 › 방문 통계 → 일·주·월 탭을 바꿔 본다.

```bash
./mvnw test -Dtest=StatsIntegrationTest
cd frontend && npx vitest run src/app/stats.test.ts
```

## 8. 확인 문제

1. 원본(`blog_visit`)을 계속 두지 않고 요약(`blog_daily_stat`)으로 모은 뒤 지우는 이유는?
<details><summary>답</summary>원본은 사람 한 명 하루 한 줄이라 빨리 커진다. 그래프·누적을 매번 원본에서 세면 블로그가 커질수록 느려진다. 블로그·날짜마다 한 줄인 요약이면 1년 그래프도 365줄이다.</details>

2. 같은 사람이 하루에 열 번 와도 한 명으로 세는 방법은? 그날 유입 경로는 어느 방문의 것인가?
<details><summary>답</summary>UNIQUE(blog_id, visit_date, visitor_key)와 INSERT IGNORE. 첫 방문만 행이 되므로 유입 경로도 그날 첫 방문의 것이다.</details>

3. 새벽 작업을 "어제 방문 수를 누적에 더하기"로 만들면 생기는 문제 두 가지와, 이 프로젝트의 해결은?
<details><summary>답</summary>작업이 두 번 돌면 두 번 더해지고, 서버가 꺼져 있던 날은 영영 빠진다. 그날 요약을 지우고 다시 넣고, 지난 7일을 매번 다시 모으고, 누적은 요약 합으로 다시 계산한다.</details>

4. 작업 안에서 "지우기"를 "모으기"보다 나중에 하는 이유는?
<details><summary>답</summary>7일 전 날을 다시 모으려면 그날 원본이 있어야 한다. 먼저 지우면 모을 것이 없다.</details>

5. 방문자와 조회 수를 `JOIN`이 아니라 `UNION ALL` 뒤 `SUM`으로 합친 이유는?
<details><summary>답</summary>방문만 있거나 조회만 있는 블로그도 한 줄이 되어야 한다. JOIN(내부 조인)은 양쪽 모두 있는 블로그만 남긴다.</details>

6. 누적 계산 UPDATE에 `b.updated_at = b.updated_at`을 넣은 이유는?
<details><summary>답</summary>blog.updated_at에 ON UPDATE CURRENT_TIMESTAMP가 있어, 그대로 두면 통계 작업이 모든 블로그의 수정 시각을 바꾼다. 같은 값을 직접 넣으면 자동 갱신이 일어나지 않는다.</details>

7. 브라우저가 구글 검색 결과에서 왔는데 "직접"으로 잡힐 수 있는 경우는?
<details><summary>답</summary>앞 페이지가 Referrer-Policy로 보내지 않게 했거나(no-referrer), HTTPS에서 HTTP로 넘어왔거나, 앱·메신저에서 열어 Referer가 없을 때.</details>

8. 방문을 화면 요청(SpaForwardController)에서 남겼다. React 안의 화면 이동은 왜 세지 않아도 되나?
<details><summary>답</summary>하루 방문자는 같은 날 같은 사람을 한 명으로 센다. 블로그 안의 이동은 이미 첫 화면 요청에서 센 사람이 같은 날 하는 것이라 숫자가 바뀌지 않는다.</details>

9. 블로그 메인에 `Referer: https://evilblog.com/`이 왔다. 플랫폼이 `blog.com`일 때 분류는? `contains`로 판단했다면?
<details><summary>답</summary>OTHER(evilblog.com은 blog.com이 아니고 .blog.com으로 끝나지도 않는다). contains("blog.com")이었다면 INTERNAL로 잘못 분류된다.</details>

## 9. 더 읽을거리

- MDN "Referer", "Referrer-Policy"
- MySQL 문서 "INSERT … SELECT", "UPDATE"(여러 테이블), "Automatic Initialization and Updating for TIMESTAMP and DATETIME"
- Spring Framework 문서 "Cron Expressions"(`@Scheduled(cron)`)
- Java `TemporalAdjusters` 문서
- Martin Kleppmann, 『데이터 중심 애플리케이션 설계』 10장 "일괄 처리"(멱등한 작업)
