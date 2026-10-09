# 스텝 9a. 보완: 이미지 확장자 검사, 태그 중간 엔티티

> 작업: T036a, T038a · 코드 브랜치: `step-9a-fixes` · 날짜: 2026-10-09

## 한눈에 보기

스텝 9를 마친 뒤, 스텝 1~7의 작업 56개를 코드·테스트와 하나씩 대조했다(그때까지 tasks.md 체크박스가 비어 있었다). 54개는 설명대로였고, 두 개가 설명과 달랐다. 지원 결정으로 둘 다 고쳤다.

| 작업 | 무엇이 달랐나 | 고친 것 | 핵심 파일 |
| --- | --- | --- | --- |
| T036a | T036 설명은 "확장자+실제 내용 검사"인데 확장자 검사가 없었다. EXIF 방향 보정은 라이브러리 기본 동작에 맡기고 테스트가 없었다 | 확장자 허용 목록(jpg·jpeg·png·gif·webp)이면서 실제 형식과 같아야 함, 아니면 400 `UNSUPPORTED_IMAGE`. EXIF 방향 테스트 | `image/domain/ImageType.matchesFileName`, `ImageService.upload`, `ImageUploadIntegrationTest` |
| T038a | `post_tag`를 엔티티 없이 `@ManyToMany`로 매핑. DB 설계는 지켰지만 연결 테이블에 칸을 더하기 어렵고 나가는 SQL이 보이지 않는 단점이 그대로였다 | `PostTag` 중간 엔티티(`@EmbeddedId` + `@MapsId`), `Post`는 `@OneToMany(cascade, orphanRemoval)`, 태그 수정은 바뀐 연결 행만, `Tag`에 `@BatchSize` | `tag/domain/PostTag`, `PostTagId`, `Post.replaceTags`, `PostQueryService`, `SearchService`, `PostCountRepositoryImpl` |

API와 화면은 바뀌지 않았다. 바뀐 것은 이미지 업로드의 거절 조건 하나다.

## 요청 흐름

```
POST /api/images (file: photo.jpg)
  ImageService.upload
    비었나 → 10MB 넘나
    매직 넘버로 실제 형식 → 이미지가 아니면 400
    (T036a) 이름 확장자가 그 형식의 것인가(jpg·jpeg / png / gif / webp, 대소문자 무시) → 아니면 400
    줄이기(EXIF 방향 반영)·썸네일 → 저장 이름은 서버가 정함(uuid.jpg)

PUT /api/posts/12 { tagNames: ["jpa", "mysql"] }   (전: spring, jpa)
  PostService.edit → post.replaceTags(...)
    postTags에서 spring 연결 제거 → orphanRemoval → DELETE FROM post_tag WHERE post_id=12 AND tag_id=(spring)
    mysql 연결 추가 → cascade → INSERT INTO post_tag (12, mysql)
    jpa 연결은 그대로
```

## 이 스텝을 이해하려면 (읽는 순서)

| 순서 | 개념 문서 | 이 스텝에서 쓰인 곳 |
| --- | --- | --- |
| 1 | [31 태그와 다대다 관계](./concepts/31-tags-many-to-many.md)의 3.2와 5.11 | `@ManyToMany`의 단점, `PostTag`·`@MapsId`·cascade·orphanRemoval, 실제 SQL, `@BatchSize` |
| 2 | [30 이미지 업로드](./concepts/30-image-upload.md)의 5.10 | 확장자 허용 목록 + 내용 검사, EXIF 테스트 만들기 |
| 3 | [06 JPA 엔티티 매핑](./concepts/06-jpa-entity-mapping.md) | N+1, 지연 로딩 |

## 막혔던 점

- **"DB 설계와 다르다"는 지적**: 처음에는 "중간 테이블은 DB에 있고 `@JoinTable`이 그것을 쓰므로 설계와 맞다, 고칠 필요는 없다"고 설명했다. 지원이 "결국 `@ManyToMany`의 단점은 그대로"라고 짚었고, 그 말이 맞아 연결 엔티티로 바꿨다. 데이터가 틀리지 않는 것과 좋은 설계인 것은 다르다.
- **바꾸고 나니 N+1**: `show-sql`로 보니 태그 이름을 읽을 때 태그마다 SELECT가 하나씩 나갔다(`PostTag.tag`가 LAZY). `Tag`에 `@BatchSize(size = 10)`를 붙여 `id in (...)` 한 번으로 줄였다.
- **EXIF 테스트가 정말 잡아내나**: 방향 정보를 넣은 JPEG를 직접 만들어 테스트했고, 방향 값을 1로 바꾸면 실패하는 것("expected: 20 but was: 40")까지 확인했다.
- **처음 체크할 때 커밋만 봤다**: 스텝 1~7 체크박스를 채우며 처음에는 "작업 번호가 적힌 커밋이 있다"만 확인했다. 지원이 "전부 구현된 것 확인했나"를 물어, 56개를 설명과 하나씩 대조했고 그때 이 두 곳이 나왔다. 체크박스는 커밋이 아니라 설명의 모든 항목을 기준으로 한다.

## 직접 해 보기

```bash
./mvnw test -Dtest='ImageUploadIntegrationTest,TagIntegrationTest,SearchIntegrationTest,SidebarIntegrationTest'
# 태그 수정 때 나가는 SQL 보기
./mvnw test -Dtest='TagIntegrationTest#editingReplacesTagsButKeepsBlogTags' -Dspring.jpa.show-sql=true | grep -i post_tag
```

브라우저로(코드 저장소 맨 위 폴더에서 `./scripts/build-frontend.sh && ./mvnw spring-boot:run`):

1. 에디터에서 사진 파일의 이름을 `photo.txt`로 바꿔 올리면 "jpg, png, gif, webp 이미지만 올릴 수 있습니다. 파일 이름의 확장자도 실제 형식과 같아야 합니다."가 나온다. PNG를 `photo.jpg`로 바꿔도 같다.
2. 태그를 단 글을 고쳐 태그를 바꾸고, 글 상세·태그별 목록·검색·사이드바 태그 글 수가 전과 같은지 본다.
