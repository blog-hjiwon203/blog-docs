# 스텝 11. 마무리

> 작업: T070, T071, T072, T073 · 코드 브랜치: `step-11-finish` · 날짜: 2026-10-10

## 한눈에 보기

제출할 수 있는 상태로 다듬었다. quickstart 시나리오를 그대로 따라가는 테스트를 넣고, 휴대폰(360px) 화면을 16개 확인해 깨진 곳을 고치고, 글 링크를 공유할 때 미리보기 카드가 나오게 했다. 쓰지 않는 기본 보안 계정을 끄고 README·quickstart를 지금 실행 방법에 맞췄다.

| 작업 | 만든 것 | 핵심 파일 |
| --- | --- | --- |
| T070 | quickstart "P0 한 바퀴" 1~6과 "권한·가시성" 표 8줄을 가입부터 실제 API·쿠키로 따라가는 테스트 | `QuickstartScenarioIntegrationTest` |
| T071 | 360px 화면 16개 자동 점검(헤드리스 Chrome), 내 글 관리 표를 휴대폰에서 카드로, "모두" 체크박스 | `pages/manage/ManagePostsPage.tsx`, `index.css` |
| T072 | 비회원도 볼 수 있는 글의 화면 주소면 index.html에 Open Graph 태그(이스케이프, 절대 주소), HTML 응답에 charset=UTF-8 | `post/application/PostPreviewService`·`PostPreview`, `global/config/SpaForwardController` |
| T073 | 쓰지 않는 Spring Security 기본 계정 끄기(시작 로그의 임시 비밀번호 제거), README(실행·테스트·접속 정보·운영 환경 변수·구조), quickstart 갱신 | `BlogApplication`, `README.md`, blog-docs `quickstart.md` |

## 요청 흐름

```
메신저에 http://alpha.blog.com/12 붙임 → 미리보기 봇이 GET (로그인 없음, 자바스크립트 실행 안 함)
  SpaForwardController: 블로그·글 확인 → 비회원이 볼 수 있나(PostPreviewService)
    예: index.html의 <title>을 "제목 - 블로그"로, </head> 앞에 og:title·description·image·url…
    아니오(비공개·구독자 공개·숨김): 그냥 index.html
  ← text/html;charset=UTF-8
```

## 이 스텝을 이해하려면 (읽는 순서)

| 순서 | 개념 문서 | 이 스텝에서 쓰인 곳 |
| --- | --- | --- |
| 1 | [43 글 공유 미리보기: Open Graph](./concepts/43-open-graph-preview.md) | 봇이 자바스크립트를 안 돌리는 문제, 서버가 넣는 og 태그, 이스케이프, 절대 주소, charset, 비회원 기준 |
| 2 | [44 휴대폰 화면: 반응형과 헤드리스 Chrome 점검](./concepts/44-mobile-responsive-check.md) | viewport, 미디어 쿼리, 표를 카드로, CDP로 360px 화면 재기·스크린숏 |
| 3 | [05 Spring 테스트](./concepts/05-spring-testing.md)의 5.8 | 사용자 순서대로 따라가는 시나리오 테스트, 쿠키 들고 다니기, 간섭과 약한 단언 |

## 막혔던 점

- **넘침은 없는데 깨진 화면**: 16개 화면 모두 "가로 넘침 없음"으로 측정됐지만, 스크린숏을 보니 내 글 관리 표의 제목 칸이 한 글자 폭으로 눌려 있었다(표가 가로 스크롤 상자 안이라 측정에 안 걸림). 기계로 먼저 재고, 그래도 눈으로 본다([44](./concepts/44-mobile-responsive-check.md)).
- **미리보기 한글이 깨짐**: 테스트에서 og 태그의 한글이 `ì ëª©`처럼 나왔다. 응답 헤더에 charset이 없어 테스트 도구가 ISO-8859-1로 읽은 것. 헤더에 `charset=UTF-8`을 붙였다([43](./concepts/43-open-graph-preview.md)).
- **시나리오 테스트가 전체 실행에서만 실패**: 홈 최신 글 첫 페이지를 다른 테스트의 2099년 글이 차지했다. 그 글 자리에 커서를 맞춰 확인하게 바꿨다([05](./concepts/05-spring-testing.md) 5.8).
- **스텝 10 PR이 아직 병합 전**: main에서 만든 스텝 11 브랜치에 스텝 10 코드가 없어 테스트 수가 적었다(282개). 스텝 11 브랜치를 스텝 10 위로 다시 얹어(rebase) 둘을 합친 상태로 전체 테스트(289개)와 휴대폰 화면(비슷한 글 카드 포함)을 다시 확인했다. 스텝 10 PR을 먼저 병합해야 한다.
- **확인용 데이터가 개발 DB에 남음**: 로그인이 필요한 화면을 보려고 개발 DB에 확인용 회원(`mobile-check-560022@example.com`)·블로그(`mobile560022`)·글 3개를 만들었다.

## 명세와 다르거나 아직 채우지 않은 것

| 항목 | 지금 | 언제 |
| --- | --- | --- |
| quickstart "주소 영속성" | 글 옮기기·블로그 이사·삭제(BLOG-06·07)가 백로그라 화면·API가 없다. 서버의 301·404와 삭제된 주소 재사용 거절만 기존 테스트가 확인 | 백로그 |
| 화면 자동 점검 도구 | 확인용 스크립트를 임시 폴더에서 돌렸고 저장소에는 넣지 않았다 | 화면 테스트를 저장소에 넣으려면 Playwright 등 |
| 실제 메신저 카드 | 로컬 주소는 메신저 서버가 닿지 않아 확인 못 함. HTML의 태그로 확인 | 배포 뒤 공유 디버거로 |
| macOS Netty DNS 경고 | Redis 클라이언트가 Mac에서 내는 경고. 동작에 영향 없어 둠 | — |

## 직접 해 보기

```bash
./mvnw test -Dtest='QuickstartScenarioIntegrationTest,SpaForwardIntegrationTest'
curl -s -D - http://{주소}.blog.test:8080/{공개 글 id} | grep -iE "content-type|og:|<title>"
```

브라우저 개발자 도구의 기기 툴바에서 폭 360으로 홈·글 상세·`/manage/posts`를 열어 본다. 내 글 관리는 글마다 카드로 보인다.
