# 구현 계획 (Implementation Plan): 학습 문서 — 캐시 저장소, PostgreSQL vs MySQL

**Branch**: `docs/learning-cache-db` | **Date**: 2026-10-13 | **Spec**: [spec.md](./spec.md)

## 요약

개념 문서 두 개(64, 65)를 `specs/001-tistory-blog/learning/concepts/`에 새로 쓰고 학습 자료 목차에 넣는다. 내용의 사실은 코드 저장소(AIP-1/blog-basic-AIGJ_01_017-blog, main `ab0b5dd`)에서 확인한 것만 쓴다.

## 기술 맥락

| 항목 | 값 |
| --- | --- |
| 문서 형식 | Markdown, 기존 개념 문서의 9개 절 순서 |
| 근거 코드 | `global/config/CacheConfig.java`, `application.yml`의 `spring.cache.*`, `home/application/PopularRanking.java`, `ranking/application/BloggerRanking.java`, Redis를 쓰는 7개 클래스, `docker-compose.yml`, `deploy/deploy.sh`, `db/migration/V1__init.sql`, `db/recommend/V1__post_embedding.sql`, `recommend/config/RecommendDataSourceConfig.java` |
| 이어지는 문서 | 17(Redis 기초), 35(Spring Cache), 41(pgvector), 42(두 번째 DB), 32(검색·콜레이션), 23·33(잠금) |

## 헌법 점검

| 원칙 | 이 작업에서 |
| --- | --- |
| I 명세는 동작, 계획은 기술 | 서비스 명세(001)를 건드리지 않는다. 기술 비교는 학습 문서에만 |
| VII 기능 코드 | 관련 기능 코드(HOME-02, HOME-03, OWN-06, R-02)를 문서에 적는다 |
| 그 밖 | 코드·명세 동작을 바꾸지 않으므로 해당 없음 |

## 조사 (research)

코드에서 확인한 사실:

- 캐시: `spring.cache.type: redis`, `time-to-live: 5m`, `key-prefix: "blog:"`. `@Cacheable`은 `popularPosts`, `topicPosts`(PopularRanking), `popularBloggers`(BloggerRanking) 세 곳, 모두 `sync = true`.
- 캐시가 아닌 Redis 사용(키 접두어): `auth:refresh:`, `auth:blocked-access:`(TokenStore), `attempt:`(AttemptLimiter), `email-verification:cooldown:`(EmailVerificationService), `password-reset:cooldown:`, `password-reset:lock-notice:`(PasswordResetService), `oauth:state:`, `oauth:ticket:`, `oauth:signup:`(SocialAuthService), `oauth:reauth:`(CredentialService), `idempotency:`(IdempotencyInterceptor).
- 운영 Redis는 `--appendonly yes`로 디스크에도 남긴다(deploy.sh).
- DB: 개발은 MySQL 8.4 + PostgreSQL 17(pgvector) 두 개. 운영은 `DB_ADDRESS`로 받는 외부 MySQL이고, 추천은 `APP_RECOMMEND_ENABLED` 기본 false.
- MySQL 전용 문법 사용: `INSERT IGNORE` 8곳(주석 제외), `UPDATE … JOIN` 4곳, `ON UPDATE CURRENT_TIMESTAMP` 9곳, 계산 칸(`GENERATED ALWAYS AS … STORED`) 2곳(`primary_owner_id`, `parent_key`), 콜레이션 `utf8mb4_0900_ai_ci`(대소문자 무시 검색이 기대는 것). ENUM 칸은 없다.

## 문서 구조

- `64-cache-store-choice.md`: 한 줄 답 → 9개 절. 핵심 표: Map / Caffeine / Redis 비교, 이 프로젝트의 Redis 사용처 표, Caffeine으로 바꾸는 예시.
- `65-postgresql-vs-mysql.md`: 한 줄 답 → 9개 절. 핵심 표: 두 DB 차이, 선택지 셋 비교, PostgreSQL로 옮길 때 고칠 곳.

## 결정

- 번호: 64, 65 (마지막 63 다음).
- "설계상 가장 나은 방안"은 65에서 분명히 쓰되, 운영 제약을 함께 적어 "왜 지금은 아닌가"도 답한다.
