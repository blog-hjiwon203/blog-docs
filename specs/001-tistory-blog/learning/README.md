# 구현 노트 (지원 공부용)

> **이 문서는?** 스텝마다 Claude Code가 무엇을 어떤 방식으로 만들었는지 공부할 수 있게 정리한 노트다. 대화 기록이 아니라 **최종 결과 기준**으로, 쓴 개념·고른 이유·요청이 지나가는 흐름·막혔던 점·직접 해 볼 명령을 적는다. 명세는 [spec.md](../spec.md)와 [plan.md](../plan.md)가 기준이고, 이 노트는 그 명세를 코드로 옮긴 과정의 설명이다.

코드 경로는 코드 저장소(`~/IdeaProjects/blog`, GitHub [AIP-1/blog-basic-AIGJ_01_017-blog](https://github.com/AIP-1/blog-basic-AIGJ_01_017-blog)) 기준이다. 자바 경로의 `…/blog/`는 `src/main/java/com/nhnacademy/blog/`를 줄인 것이다.

| 스텝 | 노트 | 핵심 개념 |
| --- | --- | --- |
| 1 | [실행 환경](./step-01.md) | Maven 의존성, Spring 프로필, Flyway, Docker Compose, Testcontainers, Vite |
| 2 | [모든 기능이 쓰는 바닥](./step-02.md) | JPA 엔티티 매핑, JPA Auditing, 전역 예외 처리, 페이지·커서, XSS 정화, CSP |
| 3 | [로그인·주소·권한 판단 장치](./step-03.md) | JWT, 쿠키 보안 속성, Spring Security 필터 체인, CSRF, 서브도메인, 가시성 판단, 멱등성 키 |

## 노트 읽는 법

1. 각 노트의 **한눈에 보기**로 그 스텝이 무엇을 남겼는지 본다.
2. **개념** 절에서 모르는 개념을 먼저 익힌다. 각 개념 끝의 "코드에서"가 실제 파일을 가리킨다.
3. **요청 흐름**을 따라가며 IntelliJ에서 파일을 열어 본다(디버거 중단점을 걸어 보면 더 좋다).
4. **직접 해 보기**의 명령을 실행해 결과를 눈으로 확인한다.
5. **더 공부할 거리**는 시간이 날 때 찾아본다.
