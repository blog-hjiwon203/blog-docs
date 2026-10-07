# Quickstart: 로컬 실행과 수용 시나리오 검증 (지원)

## 실행

```bash
# 백엔드 (H2, http://localhost:8080)
cd backend && ./gradlew bootRun

# 프론트 개발 서버 (/api → 8080 프록시)
cd frontend && npm install && npm run dev

# 배포용 jar (프론트 빌드 포함)
cd frontend && npm run build && cp -r dist/* ../backend/src/main/resources/static/
cd ../backend && ./gradlew bootJar
```

- 블로그 주소는 `{address}.localhost:8080`으로 연다. 대부분의 브라우저는 `*.localhost`를 127.0.0.1로 해석한다.
- 서비스 관리자 초기 계정은 `data.sql`로 들어간다.

## P0 한 바퀴 (spec SC-001, US1~US3)

1. `localhost:8080/signup`에서 A 가입 → 로그인 → 블로그 `alpha` 개설 (주소 변경 불가 안내 확인)
2. `alpha.localhost:8080` 블로그 메인: 빈 상태, 사이드바에 '전체 글'
3. 관리 화면에서 카테고리 'Java' 추가 → 글 작성(굵게·목록·코드 블록·이미지, 태그 2개) → 발행 → `alpha.localhost:8080/{id}`로 이동, 공감·댓글·조회수 0
4. 로그아웃 → `localhost:8080` 홈 최신 글에 그 글이 보임
5. B 가입·로그인 → 글 열람 → 댓글 작성, 공감 누르고 새로고침 → 1 유지
6. A로 로그인 → B 댓글 삭제 가능, 수정 버튼 없음

## 권한·가시성 (US4, SC-002·003)

| 시도 | 기대 |
| --- | --- |
| 비회원 `alpha.localhost:8080/manage/write` | 로그인 안내 → 로그인 후 원래 화면 |
| B 토큰으로 `PUT alpha.localhost:8080/api/posts/{A글}` | 403 |
| A 글을 비공개로 바꾼 뒤 B·비회원이 주소로 열기 | 404, 홈·목록·글 수에서 빠짐 |
| `beta.localhost:8080/{A글 id}` (B 블로그 주소에 A 글 번호) | A 글이 볼 수 있으면 `alpha...`로 301, 아니면 404 |
| B 토큰으로 `GET /api/admin/dashboard` | 403 |
| 본문에 `<img src=x onerror=alert(1)>`, `<script>` 넣고 발행 | 저장 시 제거, 실행 안 됨 (SC-007) |
| 발행 버튼 빠르게 두 번 / 같은 Idempotency-Key 두 번 | 글 1개 (SC-004) |
| `?page=999` | 빈 content, 200 |

## 주소 영속성 (SC-006, P2 이후)

1. `alpha` 글 15를 `gamma`로 이동 → `alpha.localhost:8080/15` 요청이 `gamma.localhost:8080/15`로 301
2. `alpha` 이사 대상을 `gamma`로 → `alpha.localhost:8080/` 301
3. `alpha` 삭제 후 같은 주소로 개설 → 거절
