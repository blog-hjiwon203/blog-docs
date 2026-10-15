# 구현 노트와 학습 자료 (지원 공부용)

> **이 문서는?** 이 프로젝트를 만들며 쓴 기술과 개념을 공부하기 위한 자료다. 두 종류가 있다.
> - **개념 문서**(`concepts/`): 개념 하나를 처음부터 설명한다. 왜 필요한지, 어떻게 동작하는지, 이 프로젝트 코드에서 어떻게 쓰였는지, 직접 해 볼 실습과 확인 문제까지 담았다.
> - **스텝 노트**(`스텝-NN.md`): 그 스텝에서 무엇을 만들었는지, 이해하려면 어떤 개념 문서를 어떤 순서로 읽으면 되는지, 막혔던 점을 정리한 지도다.

코드 경로는 코드 저장소(`~/IdeaProjects/blog`, GitHub [blog-hjiwon203/now-log](https://github.com/blog-hjiwon203/now-log), 2026-10-14 전 PR 링크는 제출용 원본 AIP-1/blog-basic-AIGJ_01_017-blog를 가리킨다) 기준이다.

## 스텝 노트

| 스텝 | 노트 | 만든 것 |
| --- | --- | --- |
| 1 | [실행 환경](./스텝-01.md) | Docker로 MySQL·Redis, Flyway로 테이블 26개, Testcontainers, Vite |
| 2 | [모든 기능이 쓰는 바닥](./스텝-02.md) | 엔티티, 오류 응답, 페이지 처리, 관리자 계정, 본문 정화 |
| 3 | [로그인·주소·권한 판단 장치](./스텝-03.md) | JWT 쿠키 인증, 서브도메인 해석, 글 가시성, 연타 방지, 프론트 라우터 |
| 4 | [가입과 블로그 개설](./스텝-04.md) | 이메일 인증, 가입·로그인·로그아웃, 블로그 개설·정보, 블로그 메인 글 목록, 사이드바, 첫 화면들 |
| 5 | [글쓰기](./스텝-05.md) | 카테고리 관리, 글 발행·수정·삭제·공개 범위, Tiptap 에디터 |
| 6 | [읽기·댓글·권한 (P0 완성)](./스텝-06.md) | 글 상세·이전·다음 글, 홈 최신 글, 댓글, 오류 화면, 관리자 영역 보호, 권한 시험 |
| 7 | [이미지·태그·공감·검색·답글](./스텝-07.md) | 사진 올리기와 썸네일, 태그와 태그별 목록, 공감, 블로그 안 검색, 답글, 동시성 버그 두 개 |
| 8 | [조회수·인기 글](./스텝-08.md) | 조회 기록과 5분 중복 판정, 방문자 쿠키, 사이드바 태그 목록, 인기 점수 집계와 5분 Redis 캐시 |
| 9 | [회원정보·주제·하위 카테고리·내 글 관리](./스텝-09.md) | 닉네임·사진·비밀번호 바꾸기, 비밀번호·인증 코드 시도 제한, 글 주제와 홈 주제별 글, 하위 카테고리, 내 글 거르기·일괄 처리, 테스트 간섭 |
| 9a | [보완: 이미지 확장자 검사, 태그 중간 엔티티](./스텝-09a.md) | 스텝 1~7 대조에서 나온 빈 곳: 확장자 허용 목록, EXIF 테스트, `@ManyToMany`를 `PostTag` 엔티티로 |
| 10 | [비슷한 글 추천](./스텝-10.md) | Ollama bge-m3 임베딩, PostgreSQL pgvector, 두 번째 DB, 커밋 뒤 비동기, 비슷한 글 API와 카드 |
| 11 | [마무리](./스텝-11.md) | quickstart 시나리오 테스트, 휴대폰 360px 점검과 표→카드, 글 공유 미리보기(Open Graph), README·quickstart 정리 |
| 12 | [글쓰기 버튼 안내·로그인 유지](./스텝-12.md) | 대표 블로그 글쓰기 또는 개설 안내 → 만든 뒤 글쓰기, Access 재발급 API, 브라우저 재시작 시나리오 테스트, 로그인 유지 안내 |
| 13 | [임시저장·대표 이미지](./스텝-13.md) | 제목 없이 임시저장, 1분 자동 저장, 불러와 이어 쓰고 발행, 대표 이미지 고르기와 본문 첫 이미지 기본값, 보완: 마이페이지 내 블로그(두 번째 블로그 입구, 대표 바꾸기) |
| 13b | [보완: 화면·명세 점검에서 나온 빈 곳](./스텝-13b.md) | 블로그 프로필 이미지, 닉네임 → 대표 블로그 링크, 관리 화면 태그 목록, 작성자 사진, 글 상세 공개 범위·삭제 오류, 카테고리 링크, 서비스 관리·내 블로그 입구, 로그인 중 정지 안내(동시 요청과 500), 명세 문장에서 입구까지 전부 대조하는 법 |
| 14 | [댓글 수정·방명록·댓글 관리](./스텝-14.md) | 내 댓글 고치기, 블로그 방명록(비밀·답글·페이지), 관리 화면 받은 댓글·방명록(삭제, 답글 바로 쓰기), 댓글·방명록이 같은 규칙을 쓰는 구조 |
| 15 | [전체 검색](./스텝-15.md) | 플랫폼 주소의 글·블로그 검색, 같은 경로를 Host로 나누기, 검색 범위만 바꾸는 Specification, 한 페이지의 구독자 수를 한 번에 세기 |
| 16 | [구독·공유·알림](./스텝-16.md) | 블로그 구독(멱등 PUT·DELETE), 구독 피드, 구독자 공개 글, 글 주소 복사·SNS 공유, 알림(만들기·읽을 때 거르기·읽음) |
| 17 | [글·댓글·카테고리·태그 설정](./스텝-17.md) | 카테고리 끌어서 놓기·비공개, 태그 이름 바꾸기·지우기, 비밀댓글, 댓글 허용, 예약 발행(1분 작업과 프록시 자기 호출 버그), 같은 카테고리 글 |
| 18 | [관리자·신고·공지](./스텝-18.md) | 회원 정지(기간이 지나면 저절로 풀림)·해제, 글·댓글 숨김(수정 시각 그대로), 블로그 이용 제한, 신고와 대상별 묶음 처리, 공지, 관리 이력 검색, 대시보드 |
| 19 | [블로그 꾸미기·이사·삭제, 회원 탈퇴](./스텝-19.md) | 스킨·포인트 색·목록 형태, 사이드바 모듈 순서·표시, 글 옮기기와 옛 주소 301, 이사 대상(연쇄·순환), 블로그 삭제(지운 블로그의 301), 회원 탈퇴와 수치 맞추기 |
| 19b | [인증 경계 정리](./스텝-19b.md) | 서비스 분리 대신 모듈러 모놀리스, 인증의 속을 auth로 옮기기, 본인 확인·로그인 끝내기 입구, ArchUnit 경계·계층 테스트 |
| 20 | [저장한 글·스팸 차단·방문 통계·랭킹·기기 쿠키](./스텝-20.md) | 저장(스냅숏, 볼 수 없는 글), 블로그별 차단과 금칙어, 하루 방문자와 새벽 모으기, 일·주·월 그래프와 유입 경로, 인기 블로거(정시 칸 캐시)·랭킹 전체보기(409)·추천 블로그, 잠금 악용을 줄이는 기기 쿠키. 메일·소셜(T088·T099·T100)은 키를 받은 뒤 |
| 20b | [비밀번호 재설정·메일·카카오·구글 로그인](./스텝-20b.md) | 재설정 링크 메일(256비트 토큰·SHA-256·30분·한 번만), 로그인이 막히면 메일로 잠금 풀기, SMTP 발송과 Mailpit, 카카오·구글 인가 코드 흐름(state를 Redis와 쿠키에, callback → complete), 닉네임 확인 뒤 소셜 가입, 연동·해제(마지막 수단 지키기), 소셜 회원 탈퇴 재인증 |
| 21 | [블로그 주소를 경로로](./스텝-21.md) | 서브도메인(`alpha.blog.com`)을 경로(`blog.com/@alpha`)로(배포 서버에 와일드카드 DNS가 없어서), 블로그 API는 `X-Blog-Address` 헤더(①안), 쿠키 Domain 없앰, `/@주소` 화면의 404·301·공유 미리보기, React Router basename, 같은 출처 기준 열린 리다이렉트 |
| 22 | [의미 검색](./스텝-22.md) | 검색 화면 "글자로 찾기 / 의미로 찾기" 탭(전체·블로그 안), 검색어를 같은 모델로 임베딩(Redis 캐시), 유사도 기준값 0.40(bge-m3로 잼), 두 DB에서 뽑고 → 거르고 → 자르기, 블로그 안은 범위를 먼저, HNSW `ef_search` 40개 함정, 임베딩에 태그를 넣고 `text_version`으로 다시 만들기, 안 되면 503 |
| 23 | [주 DB를 PostgreSQL로](./스텝-23.md) | MySQL과 추천 DB를 PostgreSQL 하나로(개념 65): PostgreSQL용 Flyway V1, citext와 드라이버 `stringtype` 함정, `ON CONFLICT`·`UPDATE … FROM`·`DELETE … USING`, `updated_at`을 JPA에만, READ COMMITTED와 `FOR KEY SHARE`, 의미 검색·비슷한 글을 Criteria 한 쿼리로(hibernate-vector), 테스트 SQL 차이 |
| 24 | [운영 데이터 옮기기·배포·문서](./스텝-24.md) | 서버·Docker·포트·docker 네트워크와 개발용·운영용 두 벌, `deploy.sh`가 같은 컨테이너에 `blog` DB를 만들고 앱을 붙임, MySQL → PostgreSQL 이전 스크립트(COPY 글자 형식, `sql_mode`와 상관없는 이스케이프, 외래 키 순서, 시퀀스), 행 수·내용 대조, 운영 전환과 되돌리기, 비밀번호를 명령줄에 쓰지 않기 |
| 25 | [이중화·무중단 배포](./스텝-25.md) | 앱 두 대 + 학교 nginx upstream + 롤링 배포(블루·그린이 아닌 이유), 예약 발행을 조건부 UPDATE로(두 앱 중 한쪽만 발행), 지원 리뷰로 찾은 발행 직전 취소 경합과 읽기 전 행 잠금(비관적 잠금을 고른 이유), 새벽 통계 advisory lock, Actuator readiness, 꺼질 때 비동기 작업 실험(`await-termination`을 넣지 않는 이유), `deploy.sh` 롤링·되돌리기 규칙·Redis 유지, 가짜 docker로 시험 |

## 개념 문서

모든 개념 문서는 같은 순서로 되어 있다: 배우는 것 → 왜 필요한가 → 기본 개념 → 동작 원리 → 이 프로젝트에서는 → 자주 하는 실수 → 직접 해 보기 → 확인 문제 → 더 읽을거리.

### 1부. 환경과 도구

| 문서 | 다루는 것 |
| --- | --- |
| [01 Spring Boot 기초](./concepts/01-Spring-Boot-기초.md) | 스프링 컨테이너와 빈, 의존성 주입, 스타터와 자동 설정, Maven, Spring Boot 4에서 바뀐 점, `@ConfigurationProperties` |
| [02 설정 파일과 프로필](./concepts/02-설정과-프로필.md) | `application.yml`, dev/prod 프로필, 설정 우선순위, 환경 변수, 이 프로젝트의 설정값 하나하나 |
| [03 Flyway와 스키마 마이그레이션](./concepts/03-Flyway-마이그레이션.md) | 마이그레이션, 체크섬, `ddl-auto`, ERD → schema.sql → V1 흐름 |
| [04 Docker와 Docker Compose](./concepts/04-Docker와-Docker-Compose.md) | 이미지와 컨테이너, compose 파일 항목, 볼륨, 포트, healthcheck |
| [05 Spring 테스트와 Testcontainers](./concepts/05-Spring-테스트.md) | 단위·통합·슬라이스 테스트, 컨텍스트 캐싱, `@ServiceConnection`, MockMvc |
| [69 CI/CD 개념](./concepts/69-CI-CD-개념.md) | CI와 지속적 전달·배포, 파이프라인·잡·스텝·러너, 산출물과 레지스트리, SHA 태그, 브랜치 전략과 브랜치 보호, 환경과 승인, 배포 전략(다시 띄우기·롤링·블루그린·카나리), 헬스 체크와 되돌리기, 마이그레이션과 늘리기→옮기기→줄이기, 비밀값과 OIDC, 캐시·동시 실행 제어 |
| [70 CI/CD 설정 방법 여러 가지](./concepts/70-CI-CD-설정-방법.md) | 방법 고르기(push·pull 방식), 배포 전용 SSH 키와 되돌리는 배포 스크립트, A GitHub Actions PR CI, B Actions + GHCR + SSH, C 셀프 호스티드 러너, D Jenkins(Jenkinsfile·Credentials·Multibranch), E GitLab CI(dind·manual·resource_group), F AWS OIDC + ECR + ECS, G 쿠버네티스 + Argo CD(GitOps) |
| [71 이 프로젝트의 CI/CD](./concepts/71-CI-CD-우리-프로젝트-적용.md) | now-log의 `deploy.yml`·`deploy.sh`·`Dockerfile` 읽기, 비밀값이 서버까지 가는 길, 잘된 점과 빈 곳, 고치는 순서 7단계(PR CI, 브랜치 보호, 배포 키, production 환경, SHA 태그·GHCR·자동 되돌리기, Actuator, 정리), 되돌리기와 Flyway |
| [73 이중화와 롤링 배포](./concepts/73-이중화와-롤링-배포.md) | 이중화의 범위, 롤링·블루·그린·우리 nginx 비교, upstream과 수동 헬스 판단(`max_fails`·`fail_timeout`·`proxy_next_upstream`, POST는 다시 안 보냄), 앱을 늘리는 조건(상태를 앱 밖에), liveness·readiness와 Actuator, SIGTERM·graceful shutdown·종료 단계와 비동기 작업 실험(`await-termination`), 옛·새 버전 공존(늘리기→옮기기→줄이기, JS 404), `deploy.sh`의 준비 확인·되돌리기 규칙·Redis 유지, 가짜 docker 시험 (스텝 25) |

### 2부. 데이터와 웹

| 문서 | 다루는 것 |
| --- | --- |
| [06 JPA 엔티티 매핑](./concepts/06-JPA와-엔티티-매핑.md) | ORM, 영속성 컨텍스트, 연관관계와 LAZY, N+1과 join fetch, Auditing, Specification |
| [07 Spring MVC 요청 흐름과 예외 처리](./concepts/07-Spring-MVC-요청과-예외-처리.md) | DispatcherServlet, 필터·인터셉터·인자 해석기, `@RestControllerAdvice`, 콘텐츠 협상, HTTP 상태 코드 |
| [08 페이지네이션](./concepts/08-페이지네이션.md) | offset과 keyset(커서), 정렬 안정성, 인덱스, Spring Data `Pageable` |
| [09 비밀번호 해시와 bcrypt](./concepts/09-비밀번호-해시.md) | 해시와 암호화, salt, cost, bcrypt 구조와 72바이트 제한 |
| [22 입력 검증과 JSON 바인딩](./concepts/22-입력-검증과-JSON-바인딩.md) | Jackson 3 바인딩, Bean Validation, `@Valid`와 상태 코드 순서, 기본형 칸 누락 |
| [29 댓글 설계](./concepts/29-댓글-설계.md) | 글에 딸린 데이터의 권한, 보는 사람마다 다른 댓글, 댓글 수, 연타 두 겹, 답글 한 단계, 댓글 고치기(상태 코드 순서, `updatedAt`), 비밀댓글·댓글 허용(400을 지워 기능 열기) |
| [50 같은 규칙의 두 기능을 한 코드로](./concepts/50-댓글과-방명록-같은-규칙.md) | 댓글과 방명록: 공통 인터페이스(`CommentEntry`)와 조립기(`CommentViews`), 상속·복사와 비교, 페이지 번호 목록의 기준(최상위 글), Spring Data `findBy`의 `project`·`page`, "받은" 댓글 목록, 화면 부품 나누기와 그 자리에서 고치기 |
| [51 구독과 알림](./concepts/51-구독과-알림.md) | 멱등한 PUT·DELETE와 INSERT IGNORE의 "넣은 행 수", 부수 효과(알림)를 같은 트랜잭션에서 만들기와 다른 방법(이벤트·비동기), 쓸 때 정하는 것(문구)과 읽을 때 정하는 것(링크·가시성), 거르는 커서 목록, 구독자 공개와 "있지만 못 보는" 403, 클립보드와 보안 컨텍스트, 제재·해제 알림(SANCTION) |
| [52 예약 작업과 프록시 자기 호출](./concepts/52-예약-작업과-프록시.md) | `@Scheduled`(fixedDelay·fixedRate·cron), DB 훑기 vs 메모리 타이머, 정한 시각과 돈 시각, 글 상태 기계에 예약 더하기, 같은 객체 안 호출에 `@Transactional`이 안 걸리는 이유와 실제 버그, 테스트에서 백그라운드 작업 끄기 |
| [53 서비스 관리](./concepts/53-서비스-관리와-제재-이력.md) | 주소 규칙으로 관리자만(401·403), 읽을 때 판단하는 정지 기간, 고치지 않는 감사 이력과 "사유는 최신 이력 줄에서", 수정 시각을 바꾸지 않는 숨김, 신고 묶음(GROUP BY·countQuery·인터페이스 프로젝션), 중첩 라우트와 주소에 둔 검색 조건 |
| [54 꾸미기와 블로그의 수명](./concepts/54-테마-이사-삭제-탈퇴.md) | CSS 변수 하나로 테마, `data-skin` 스킨, 정해진 칸 전체 교체 API와 V4 채우기, 번호를 그대로 둔 이사와 301, 연쇄를 최종으로 저장, 지운 블로그의 옛 주소, 블로그 단위 SQL 삭제, 탈퇴 정리 순서와 UPDATE … JOIN으로 수치 맞추기 |
| [55 모듈 경계](./concepts/55-모듈-경계와-ArchUnit.md) | 패키지·빌드 모듈·서비스 비교, 분산 모놀리스, 공개 입구와 속, 판단을 한 곳에, ArchUnit 규칙(바이트코드, 상수는 잡히지 않음) |
| [56 저장한 글](./concepts/56-저장한-글과-스냅숏.md) | 멱등한 PUT·DELETE와 INSERT IGNORE, 스냅숏(정규화의 예외), 저장할 때와 읽을 때의 판단, 이유를 말하지 않는 "볼 수 없음", `@JsonInclude(NON_NULL)`, 목록에서 바로 취소, 탈퇴 정리 |
| [57 스팸 막기](./concepts/57-스팸-차단과-금칙어.md) | 서비스 정지와 블로그 차단, 검사를 한 곳(SpamGuard)에, 검사 순서와 존재 숨기기, 차단과 함께 지우는 구독, 포함 검사의 한계, `Locale.ROOT`와 DB 콜레이션, 한도와 중복을 어디서 막나, 403·400·409 고르기 |
| [58 방문 통계](./concepts/58-방문-통계와-새벽-집계.md) | 하루 방문자(순 방문자), 원본과 요약 표, 멱등한 배치(지우고 넣기, 다시 계산, 지난 7일), 오늘은 바로·어제까지는 요약, Referer로 유입 나누기와 한계, SPA에서 방문을 아는 곳, `UPDATE … JOIN`과 `ON UPDATE`, 그래프 빈 칸·주·월 칸 |
| [59 시간 칸 스냅숏](./concepts/59-시간-칸-스냅숏과-순위.md) | 작업 대신 시간 칸을 키로 한 캐시, 결정적 계산(끝을 정시로), 더보기 중 순위 고정과 409 `RANKING_UPDATED`, 블로그 점수 SQL, 캐시엔 번호만, 추천은 같은 순위표에서, 테스트의 캐시·시간대 |
| [31 태그와 다대다 관계](./concepts/31-태그와-다대다-관계.md) | `@ManyToMany`와 조인 테이블, 이름 정리 규칙, 태그별 목록, 태그 입력 칸, 태그 이름 바꾸기·지우기(같은 이름 규칙, CASCADE), 글 없는 태그 자동 삭제와 빈 자리 잠금 데드락 |
| [32 블로그 안 검색: LIKE와 비정규화 칸](./concepts/32-블로그-안-검색-LIKE.md) | 글자만 담은 칸과 마이그레이션, LIKE 이스케이프, EXISTS 서브쿼리, 인덱스 한계, 검색어를 주소에, 전체 검색(범위만 바꾸는 Specification, 블로그 검색, 구독자 수 한 번에) |
| [47 임시저장과 자동 저장](./concepts/47-임시저장과-자동-저장.md) | 글의 상태와 되돌릴 수 없는 이동, 상태별 검증, 처음 POST 그 뒤 PUT, `setInterval`과 낡은 값·`useRef`, 저장 줄 세우기, 스냅숏 |
| [48 대표 이미지](./concepts/48-대표-이미지.md) | 고른 번호 검증(본문 안에 있나), `null` = 자동, `ON DELETE SET NULL`, 한 페이지 쿼리 두 번, 파생 값 |
| [27 소프트 삭제와 일괄 수정](./concepts/27-소프트-삭제와-일괄-수정.md) | 소프트 삭제, 딸린 데이터 처리, 변경 감지, `@Modifying`, 수정 시각 지키기 |
| [23 트랜잭션과 동시성](./concepts/23-트랜잭션과-잠금.md) | `@Transactional`, 경쟁 조건, 비관적 잠금(`FOR UPDATE`), UNIQUE 제약, 동시성 테스트, 대표 블로그 바꾸기(끄고 flush 켜기) |
| [33 격리 수준, 스냅샷, 데드락](./concepts/33-격리-수준과-데드락.md) | 격리 수준과 MVCC, 일관된 읽기와 잠금 읽기, 외래 키 공유 잠금과 데드락, 공감 버튼에서 겪은 두 버그 |
| [72 동시 수정 막기](./concepts/72-동시-수정-막기.md) | 읽고→판단하고→쓰기와 갱신 손실, READ COMMITTED에서 UPDATE가 WHERE를 다시 보는 동작(DB가 "바뀐 것"을 막아 주지 않음), 변경 감지의 모든 칸 UPDATE, 조건부 UPDATE·비관적 잠금·낙관적 잠금(`@Version`)·advisory lock 비교와 틈의 길이로 고르기, 예약 발행·새벽 통계·지원 리뷰로 찾은 발행 직전 취소, 그 순간을 고정하는 테스트(래치·`pg_stat_activity`) (스텝 25) |
| [34 조회수: 누가 봤는지, 5분 중복, 동시 새로고침](./concepts/34-조회수.md) | 조회자 키와 방문자 쿠키, 시간 창 중복 판정, 기록 테이블과 누적 칸, 잠금을 첫 문장으로, StrictMode effect 두 번 |
| [36 집계 쿼리로 순위 매기기](./concepts/36-집계-쿼리로-순위-매기기.md) | `GROUP BY`·`SUM`, `UNION ALL`로 가중치 점수, 시각 인덱스, 동점 처리, `NamedParameterJdbcTemplate`, 태그별 글 수 |
| [43 글 공유 미리보기: Open Graph](./concepts/43-Open-Graph-공유-미리보기.md) | 봇은 자바스크립트를 안 돌린다, 서버가 넣는 og 태그, 이스케이프, 절대 주소, charset, 비회원 기준 |
| [44 휴대폰 화면: 반응형과 헤드리스 Chrome 점검](./concepts/44-휴대폰-화면-반응형-점검.md) | viewport, 미디어 쿼리, `minmax(0, 1fr)`, 표를 카드로, CDP로 360px 화면 재기·스크린숏 |
| [41 임베딩과 벡터 검색](./concepts/41-임베딩과-벡터-검색.md) | 임베딩, 코사인 유사도·거리, pgvector `<=>`와 HNSW, pgvector 이미지와 확장 켜기, Ollama bge-m3와 "요청을 기다리는 서버"(누가 언제 부르나), 임베딩을 만드는 다른 방법, 추천에서 볼 수 없는 글 거르기(한 쿼리), 가짜 임베딩 테스트 |
| [42 두 번째 DB와 커밋 뒤 비동기 처리](./concepts/42-두-번째-DB와-비동기-처리.md) | `@Bean(defaultCandidate = false)` DataSource, DB별 Flyway, 최종 일관성, 이벤트·`@TransactionalEventListener`·`@Async`, 비동기 테스트 |
| [65 MySQL과 PostgreSQL: 비교, 옮기는 이유, 옮기는 법](./concepts/65-PostgreSQL-vs-MySQL.md) | 두 DB의 같은 점과 다른 점(문법·타입·글자 비교·격리 수준·확장), PostgreSQL이 들어온 이유와 벡터를 pgvector에 두는 이유, 두 DB를 합치는 장단점과 선택지, 옮기기의 세 겹, **대소문자 구분 문제와 해결**(citext, JDBC `varchar` 함정과 `stringtype=unspecified`, ILIKE, 자바 비교), `updated_at`, 격리 수준·잠금, Criteria 한 쿼리 벡터 검색(hibernate-vector), 데이터 옮기기(COPY 형식·이스케이프·외래 키 순서·시퀀스·대조), 전환과 되돌리기 (옛 65·67과 68의 데이터 부분을 합침, 스텝 23·24)
| [66 의미 검색: 낱말이 아니라 뜻으로 찾기](./concepts/66-의미-검색.md) | 글자 검색과 의미 검색, 검색어도 같은 모델로, 기준값을 재서 정하기, 최대 결과 수, 가시성·블로그 조건을 같은 쿼리에(스텝 22의 두 DB 뽑고 → 거르고 → 자르기와 비교), HNSW `hnsw.ef_search`와 `iterative_scan`, 검색어 임베딩 캐시와 프록시, 넣는 글자 버전(`text_version`), Ollama 실패는 503·DB 오류는 500 |
| [68 서버와 Docker: 개발용과 운영용](./concepts/68-서버와-Docker-개발용-운영용.md) | 서버·이미지·컨테이너, Docker는 컴퓨터마다 따로, 서버에서도 Docker를 쓰는 이유, 건물·방·현관문으로 본 포트와 docker 네트워크, 개발용과 운영용 두 벌과 연결 정보가 있는 곳, 누가 운영 컨테이너를 띄우나(Actions → deploy.sh), 볼륨, 같은 컨테이너에 DB 하나 더, 비밀번호를 `ps`에 안 보이게 (스텝 24) |
| [37 거르기 조건이 있는 목록과 일괄 처리](./concepts/37-조건-목록과-일괄-처리.md) | 동적 Specification, `COALESCE` 정렬과 개수 쿼리, 주인 확인 뒤 값 검사, 일괄 변경·삭제, `LikePatterns`, 주소에 둔 거르기 조건 |
| [39 계층 데이터: 카테고리 2단계와 주제](./concepts/39-카테고리-계층.md) | 자기 참조 트리, 2단계 제한, 계산 칸 `parent_key`와 UNIQUE, 주제 enum, 주제별 글 채우기, 비공개 카테고리의 글 숨기기(NOT EXISTS 부분 쿼리), 전체 순서 한 번에 저장과 끌어서 놓기 순수 함수 |
| [30 이미지 업로드와 처리](./concepts/30-이미지-업로드.md) | multipart, 크기 제한, 매직 넘버, Thumbnailator·EXIF, WebP 플러그인, `/uploads` 내보내기와 캐시, 목록 썸네일 |

### 3부. 보안

| 문서 | 다루는 것 |
| --- | --- |
| [10 HTTP 쿠키](./concepts/10-HTTP-쿠키와-로그인-상태.md) | 쿠키 속성 하나하나, 세션과 토큰, 서브도메인 쿠키 공유 |
| [11 JWT와 로그인 토큰 설계](./concepts/11-JWT-로그인-토큰.md) | JWT 구조와 서명, Access/Refresh, 무효화, 무활동 로그아웃 |
| [12 Spring Security 필터 체인](./concepts/12-Spring-Security-필터-체인.md) | FilterChainProxy, SecurityContext, 인가 설정, 메서드 보안, 커스텀 필터 |
| [13 CSRF, SameSite, CORS](./concepts/13-CSRF-SameSite-CORS.md) | 출처와 사이트, CSRF 공격과 대책, preflight, CORS가 아닌 것 |
| [14 XSS, HTML 정화, CSP](./concepts/14-XSS-방어-본문-정화와-CSP.md) | XSS 종류, 허용 목록 정화, CSP 지시어 |
| [20 이메일 인증 코드와 요청 제한](./concepts/20-이메일-인증-코드.md) | 인증 코드 설계, `SecureRandom`, Redis로 1분 재요청 제한, 메일 발송 인터페이스 |
| [40 시도 횟수 제한](./concepts/40-시도-횟수-제한.md) | 온라인 무차별 대입, 대상별(15분·5번)·IP별(20번) 실패 횟수, Redis `INCR`로 동시 시도까지 막기, 가입 여부 숨기기, 잠금 악용, 프록시 뒤의 IP |
| [60 기기 쿠키](./concepts/60-기기-쿠키.md) | 잠금 악용과 OWASP 기기 쿠키, HMAC 서명(저장 없이 확인), nonce와 `SecureRandom`, 고정 시간 비교, 용도별 키, 시도 키를 바꿔 기능 더하기, 막지 못하는 것 |
| [62 비밀번호 재설정과 메일 보내기](./concepts/62-비밀번호-재설정과-메일.md) | 링크 토큰(`SecureRandom` 256비트), 해시만 저장(bcrypt가 아니라 SHA-256인 이유), 30분·한 번만·다른 링크 은퇴와 행 잠금, 가입 여부 숨기기와 메일 폭탄, 응답 시간으로 새는 가입 여부와 커밋 뒤 비동기 발송, 잠금 안내 메일로 잠금 풀기, SMTP·`JavaMailSender`, `@ConditionalOnProperty`로 구현 고르기, Mailpit·Gmail 앱 비밀번호, `@Primary` 기록용 메일함 |
| [38 회원정보 수정](./concepts/38-회원정보-수정.md) | PATCH 부분 수정, 나를 뺀 닉네임 중복, 지금 비밀번호 확인, IDOR(남의 것을 가리키는 번호), 마이페이지, 블로그 프로필 이미지(올리기와 저장 나누기) |
| [21 가입·로그인·로그아웃 설계](./concepts/21-가입-로그인-로그아웃.md) | 가입 트랜잭션, 계정 열거·타이밍 공격 방어, 정지 안내, 로그아웃, 열린 리다이렉트 |
| [45 로그인 유지](./concepts/45-로그인-유지.md) | 세션 쿠키와 영속 쿠키, 브라우저 재시작, 미끄러지는 만료와 고정 만료, 필터 재발급과 재발급 API, 재시작 흉내 테스트 |
| [61 소셜 로그인: OAuth 2.0](./concepts/61-OAuth-소셜-로그인.md) | 인가 코드 흐름과 등장인물, 리다이렉트 URI 등록, OpenID Connect `sub`·카카오 `id`, `state`와 로그인 CSRF(Redis와 쿠키 두 곳), 콜백과 쿠키 주는 곳 나누기, Redis 읽고 지우기, 이메일로 합치지 않기, 연동 규칙과 회원 행 잠금, 재인증(`prompt=login`·`max_age=0`), 열린 리다이렉트 |

### 4부. 이 블로그의 구조와 프론트

| 문서 | 다루는 것 |
| --- | --- |
| [15 서브도메인과 Host 라우팅](./concepts/15-서브도메인과-Host-헤더.md) | DNS, `/etc/hosts`, Host 헤더, 멀티테넌시, 인자 해석기, 같은 경로를 Host로 나누기 |
| [63 블로그 주소를 경로로](./concepts/63-블로그-주소를-경로로.md) | 서브도메인과 경로 주소(와일드카드 DNS·nginx `server_name`·인증서), `@`를 붙이는 이유, API에 블로그 알리기(Host·사용자 지정 헤더·경로 칸, ①안과 ②안), 헤더는 권한이 아님, 같은 출처와 사전 요청, 한 출처의 XSS 영향, host-only 쿠키, `/@주소` 서버 확인과 화면·파일 주소 구분, React Router `basename`, 같은 출처 열린 리다이렉트, 경로 패턴에 `/` 넣기 함정 (스텝 21, 15의 다음 이야기) |
| [16 인가와 가시성 판단](./concepts/16-인가와-가시성.md) | 인증과 인가, 존재를 숨기는 404, 정책 객체, sealed 타입과 switch |
| [17 멱등성과 Redis](./concepts/17-멱등성과-Redis.md) | 멱등성, 중복 요청, Idempotency-Key, Redis 기초와 `SET NX` |
| [35 캐시: Spring Cache와 Redis](./concepts/35-Spring-Cache와-Redis.md) | 캐시와 오래된 값, TTL, `@Cacheable`과 프록시, Redis 키·Java 직렬화, `sync`, 캐시에 번호만 두기 |
| [64 캐시 저장소 고르기: 꼭 Redis여야 할까](./concepts/64-캐시-저장소-고르기.md) | 로컬 캐시와 원격 캐시, 자바 Map·Caffeine·Redis 비교, 고르는 질문 네 개, 캐시와 캐시가 아닌 임시 데이터(토큰·시도 횟수·연타 방지), 캐시만 Caffeine으로 바꾸는 법, 두 단계 캐시 |
| [18 SPA와 서버 라우팅](./concepts/18-SPA와-서버-라우팅.md) | History API, 서버 폴백, 301/302, Vite 개발 서버와 빌드 |
| [28 Thymeleaf에서 React로](./concepts/28-Thymeleaf에서-React로.md) | 서버 렌더링과 클라이언트 렌더링, 같은 화면 두 가지 구현, 빌드가 하는 일, 개발 서버와 빌드 스크립트 (Thymeleaf를 알면 React 문서보다 먼저) |
| [19 React Router와 API 클라이언트](./concepts/19-React-화면-나누기와-API-클라이언트.md) | React 기초, React Router 7, fetch, TypeScript, Vitest, 동시에 나간 요청과 정지 응답(한 곳에 기억하고 읽기만 다시 보내기) |
| [46 상태에 따라 갈 곳 정하기: 글쓰기 버튼](./concepts/46-글쓰기-버튼-갈-곳-정하기.md) | 판단을 순수 함수 하나에, `Pick`과 단위 테스트, 호스트를 넘는 이동, `?from=`으로 하려던 일 넘기기와 열린 리다이렉트, 버튼은 안내이고 권한은 서버 |
| [49 완료의 정의와 요구사항 추적](./concepts/49-완료의-정의와-요구사항-추적.md) | 완료의 정의, 명세 문장을 항목으로 쪼개 API·화면·입구 대조, 반쯤 된 기능이 숨는 자리(`null` 응답 칸, 번호 없는 "나중에", 부르지 않는 API), 수평·수직으로 만들기, 테스트 고정 데이터가 조건을 숨길 때 |
| [24 계층 구조와 DTO](./concepts/24-계층-구조와-DTO.md) | presentation/application/domain, 엔티티 대신 DTO, `open-in-view`와 지연 로딩 |
| [25 React 폼과 데이터 불러오기](./concepts/25-React-폼과-데이터-불러오기.md) | 제어 컴포넌트, 폼 제출과 칸별 오류, `useEffect`와 커스텀 훅, 중첩 라우트, 낙관적 갱신, key, `FormData` |
| [26 WYSIWYG 에디터와 Tiptap](./concepts/26-WYSIWYG-에디터와-Tiptap.md) | ProseMirror와 Tiptap, 허용 서식 맞추기, 이중 정화, 에디터 상태 |

## 공부하는 법

1. **스텝 노트**의 "한눈에 보기"로 그 스텝이 무엇을 남겼는지 본다.
2. 스텝 노트의 **"이 스텝을 이해하려면"** 표 순서대로 개념 문서를 읽는다.
3. 개념 문서의 **"이 프로젝트에서는"** 절을 IntelliJ에서 실제 파일을 열어 놓고 읽는다. 디버거 중단점을 걸고 테스트를 돌리면 흐름이 눈으로 보인다.
4. **"직접 해 보기"**를 실행한다. 코드를 바꿔 보는 실습은 브랜치를 따로 만들어서 하고, 끝나면 되돌린다(`git switch -c study/xxx`, `git restore .`).
5. **확인 문제**를 답을 보기 전에 먼저 풀어 본다.
