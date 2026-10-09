# 스텝 12. 글쓰기 버튼 안내·로그인 유지

> 작업: T061, T062 · 코드 브랜치: `step-12-login-write` · 날짜: 2026-10-10 · 백로그 추천 순서(T061 → T062 → T059 → T058 → T066 → T068 → T065)의 첫 스텝

## 한눈에 보기

어디서 누르든 같은 곳으로 가는 글쓰기 버튼을 만들고(블로그가 있으면 대표 블로그의 글쓰기, 없으면 안내와 함께 블로그 개설 → 만든 뒤 바로 글쓰기), 스텝 3에서 대부분 만든 로그인 유지의 남은 부분을 채웠다.

| 작업 | 만든 것 | 핵심 파일 |
| --- | --- | --- |
| T061 | 글쓰기가 갈 곳을 정하는 함수와 테스트, 플랫폼 머리글·남의 블로그 머리글의 글쓰기 버튼, 개설 화면의 "먼저 블로그가 필요합니다" 안내와 만든 뒤 글쓰기로 | `frontend/src/app/writeLink.ts`(+`.test.ts`), `components/PlatformHeader.tsx`, `components/BlogHeader.tsx`, `pages/blog/BlogCreatePage.tsx` |
| T062 | `POST /api/auth/token/refresh`, 브라우저를 닫았다 연 상태를 흉내 낸 시나리오 테스트, 로그인 화면에 유지 기간 안내 | `auth/presentation/AuthController`, `KeepLoggedInIntegrationTest`, `pages/auth/LoginPage.tsx` |

스텝 3에서 이미 있던 것(이번에 다시 확인만 함): 로그인 유지면 Refresh 쿠키 14일(`Max-Age=1209600`), 아니면 세션 쿠키 + Redis 30분 무활동, 요청마다 연장, Access 만료 시 필터가 새로 줌(`LoginIntegrationTest`, `IdleTimeoutIntegrationTest`, `AuthenticationIntegrationTest`).

## 요청 흐름

```
[T061] 블로그 없는 회원, 플랫폼 홈
  GET /api/me → primaryBlog: null
  머리글 글쓰기 href = writeUrl(me) = http://blog.test:8080/blogs/new?from=write
  클릭 → 개설 화면: from=write → 안내 상자
  만들기 → POST /api/blogs → 201 {address: gamma}
  → http://gamma.blog.test:8080/manage/write

[T062] 로그인 유지를 고르고 로그인 → 브라우저 끝냄 → 다시 열기
  남은 쿠키: refresh_token(영속)만
  GET /api/me Cookie: refresh_token
    JwtAuthenticationFilter: Redis auth:refresh:{jti} 있음 → 회원, Set-Cookie: access_token=새것
  ← 200 Me
```

## 이 스텝을 이해하려면 (읽는 순서)

| 순서 | 개념 문서 | 이 스텝에서 쓰인 곳 |
| --- | --- | --- |
| 1 | [45 로그인 유지: 세션 쿠키와 영속 쿠키, 브라우저 재시작](./concepts/45-remember-me.md) | 체크박스가 바꾸는 쿠키·Redis 수명, 미끄러지는 만료와 고정 만료, 필터 재발급과 재발급 API, 재시작 흉내 테스트 |
| 2 | [46 상태에 따라 갈 곳 정하기: 글쓰기 버튼](./concepts/46-entry-routing-write-button.md) | `writeUrl` 순수 함수와 테스트, `<Link>`와 `<a href>`, `?from=write`로 하려던 일 넘기기, 버튼은 안내이고 권한은 서버 |
| 3 | (복습) [10 HTTP 쿠키](./concepts/10-http-cookies.md) 3.6, [11 JWT](./concepts/11-jwt.md) 3.5~3.8 | 세션 복원 함정, Access/Refresh, 무활동 로그아웃 |

## 막혔던 점

- **T062가 이미 거의 끝나 있었다**: 로그인 유지의 핵심(14일 쿠키, 30분 무활동, 필터 재발급)은 스텝 3·4에서 만들었고 테스트도 있었다. 체크박스만 비어 있던 것. 그래서 이번에는 (1) 명세(contracts)에 있는데 없던 재발급 API, (2) 수용 시나리오 "브라우저를 닫았다 열면 유지"를 그대로 따라가는 테스트, (3) 사용자가 고를 때 볼 안내만 채웠다.
- **재발급 API의 몸통이 비었다**: 필터가 이미 새 Access 쿠키를 주므로 컨트롤러가 또 주면 `Set-Cookie`가 두 번 나간다. 컨트롤러는 "로그인 상태로 왔나"만 답한다([45](./concepts/45-remember-me.md) 5.4).
- **재시작 흉내가 아무것도 증명하지 못할 뻔**: 남은 쿠키에 Access가 섞이면 Refresh가 없어도 통과한다. "남은 쿠키는 refresh_token 하나"를 먼저 단언했다([45](./concepts/45-remember-me.md) 5.5).
- **홈 사이드바의 "내 블로그" 상자**: 홈 목업에는 오른쪽 사이드바에 글쓰기 상자가 있지만 지금 홈은 한 단 구성이라, 모든 플랫폼 화면에 보이는 머리글에 글쓰기 버튼을 두었다.

## 명세와 다르거나 아직 채우지 않은 것

| 항목 | 지금 | 언제 |
| --- | --- | --- |
| 재발급 API에서 정지 회원 | API 명세는 처음에 "정지·탈퇴면 401"이었다. 정지면 다른 API와 같이 403 `MEMBER_SUSPENDED`(정지 사유 포함), 탈퇴는 401로 명세를 고쳤다 | 2026-10-10 지원 결정, 반영함 |
| 홈 사이드바 "내 블로그" 상자 | 머리글 버튼으로 대신 | 홈을 두 단으로 바꿀 때 |

## 직접 해 보기

```bash
./mvnw test -Dtest='KeepLoggedInIntegrationTest,IdleTimeoutIntegrationTest,LoginIntegrationTest'
cd frontend && npx vitest run src/app/writeLink.test.ts
```

화면: [46](./concepts/46-entry-routing-write-button.md) 7.1(새로 가입 → 홈 글쓰기 → 개설 → 글쓰기), [45](./concepts/45-remember-me.md) 7.1~7.2(쿠키 수명 보기, 브라우저를 `⌘Q`로 끝냈다 열기).
