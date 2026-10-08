# 30. 이미지 업로드와 처리

> 관련 스텝: [스텝 7](../step-07.md) (T036, T037) · 관련 개념: [01-spring-boot-basics](./01-spring-boot-basics.md)(`@ConfigurationProperties`), [07-spring-mvc-exception-handling](./07-spring-mvc-exception-handling.md), [14-xss-sanitize-csp](./14-xss-sanitize-csp.md), [06-jpa-entity-mapping](./06-jpa-entity-mapping.md)(N+1), [26-wysiwyg-editor-tiptap](./26-wysiwyg-editor-tiptap.md), [28-thymeleaf-to-react](./28-thymeleaf-to-react.md)

## 1. 이 문서로 배우는 것

- 브라우저가 파일을 서버로 보내는 방법: `multipart/form-data`와 Spring의 `MultipartFile`, `@RequestPart`
- 업로드 크기 제한을 두 곳(Spring 설정, 서비스 코드)에서 거는 이유와 `MaxUploadSizeExceededException`
- 확장자와 `Content-Type`을 믿으면 안 되는 이유, 파일 앞부분의 **매직 넘버**로 실제 형식을 알아내는 법
- 이미지를 다 풀지 않고 **머리 정보만 읽어** 가로·세로를 알아내는 법(`ImageIO`의 `ImageReader`)
- Thumbnailator로 원본 줄이기(긴 변 1920px)와 썸네일 만들기(400px), 휴대폰 사진의 EXIF 방향
- WebP를 읽게 해 주는 TwelveMonkeys 플러그인과 Java의 플러그인 방식(SPI)
- GIF·WebP 원본은 손대지 않는 이유
- 저장 파일 이름을 UUID로 짓는 이유(경로 조작, 이름 겹침), 실패하면 쓴 파일을 지우는 이유
- 업로드 폴더를 `/uploads/**` 주소로 내보내기(`addResourceHandlers`)와 30일 캐시가 안전한 이유
- 글 목록 한 줄마다 썸네일을 붙이면서 쿼리는 한 번만 하기(`PostThumbnails`)
- 화면 쪽: `FormData`로 파일 보내기, 에디터의 이미지 버튼, 그리고 **실제로 겪은 "두 장 골랐는데 한 장만 남는" 버그**

**먼저 알면 좋은 것**: 설정값을 객체로 받는 `@ConfigurationProperties`([01](./01-spring-boot-basics.md)), 예외를 오류 응답으로 바꾸는 `@RestControllerAdvice`([07](./07-spring-mvc-exception-handling.md)), 본문 HTML 정화([14](./14-xss-sanitize-csp.md)), Tiptap 에디터([26](./26-wysiwyg-editor-tiptap.md)).

## 2. 왜 필요한가

"사진 올리기"는 파일을 받아서 폴더에 넣으면 끝날 것 같지만, 실제로는 이런 문제가 생긴다.

- **위장 파일**: `evil.jpg`라는 이름에 `Content-Type: image/jpeg`를 붙여 보냈는데 내용은 HTML·스크립트라면? 이름과 헤더는 보내는 사람이 마음대로 정한다.
- **무거운 원본**: 요즘 휴대폰 사진은 4000px 넘고 몇 MB다. 그대로 본문에 넣으면 글을 열 때마다 몇 MB를 받는다. 목록에 작은 그림 하나 보여 주는 데도 원본을 받으면 더 심하다.
- **누운 사진**: 휴대폰은 사진을 찍은 방향 그대로 픽셀을 저장하고 "이 사진은 90도 돌려서 보여 줘"라는 표시(EXIF Orientation)만 붙인다. 이 표시를 무시하고 줄이면 사진이 눕는다.
- **파일 이름**: 두 사람이 `image.png`를 올리면 덮어쓴다. 이름에 `../../`를 넣으면 업로드 폴더 밖에 쓸 수도 있다.
- **반쯤 남은 파일**: 원본은 썼는데 썸네일을 만들다 실패하면, DB에 행은 없고 파일만 남는다.
- **애니메이션 GIF**: 줄이려고 다시 저장하면 첫 장면만 남아 움직이지 않는다.

기능 명세는 이렇게 정한다.

- POST-05: 본문에 jpg/png/gif/webp 이미지를 넣는다. 파일당 10MB. 목록에는 작게 줄인 이미지를 보여 준다. 여러 장은 고른 순서대로 들어간다.
- spec US2 시나리오 6: 형식이 틀리거나 10MB를 넘으면 그 파일만 거절하고 이유를 알린다. 본문은 그대로다.
- research R-15(지원 결정): Thumbnailator + TwelveMonkeys `imageio-webp`. 원본은 긴 변 1920px, 썸네일은 400px. GIF·WebP 원본은 그대로. 썸네일은 jpg 원본이면 jpg, 나머지는 png.

## 3. 기본 개념

### 3.1 multipart/form-data: 파일을 담는 요청 본문

보통 폼은 `title=안녕&content=...`처럼 글자만 보낸다(`application/x-www-form-urlencoded`). 파일은 바이트 덩어리라 이 방식에 담을 수 없다. 그래서 **본문을 여러 조각(part)으로 나누는** 형식을 쓴다.

```
POST /api/images HTTP/1.1
Content-Type: multipart/form-data; boundary=----abc123

------abc123
Content-Disposition: form-data; name="file"; filename="cat.png"
Content-Type: image/png

(PNG 바이트들...)
------abc123--
```

- `boundary`는 조각 사이를 가르는 구분 문자열이다. 브라우저가 파일 내용과 겹치지 않게 지어서 `Content-Type` 헤더에 함께 적는다.
- 조각마다 이름(`name="file"`), 원래 파일 이름(`filename`), 그 조각의 `Content-Type`이 붙는다. **`filename`과 조각의 `Content-Type`은 브라우저(또는 curl, 공격자)가 적은 값**이라 믿을 수 없다.

Thymeleaf로 화면을 만들 때는 이렇게 썼을 것이다.

```html
<form th:action="@{/images}" method="post" enctype="multipart/form-data">
  <input type="file" name="file">
  <button>올리기</button>
</form>
```

`enctype="multipart/form-data"`가 바로 이 형식으로 보내라는 뜻이다. 이 프로젝트는 폼 제출로 페이지를 바꾸지 않고 자바스크립트 `fetch`로 같은 형식의 요청을 보낸다(5.7).

### 3.2 Spring에서 받기: MultipartFile과 @RequestPart

Spring Boot는 multipart 요청이 오면 서블릿 컨테이너(Tomcat)가 조각을 나누고, 파일 조각을 `MultipartFile` 객체로 준다.

| 메서드 | 돌려주는 것 |
| --- | --- |
| `getBytes()` | 파일 내용 전체(byte[]) |
| `getSize()` | 바이트 수 |
| `isEmpty()` | 파일을 고르지 않았거나 0바이트 |
| `getOriginalFilename()` | 보낸 쪽이 적은 파일 이름(믿으면 안 됨) |
| `getContentType()` | 보낸 쪽이 적은 형식(믿으면 안 됨) |

컨트롤러에서는 `@RequestPart(name = "file") MultipartFile file`처럼 조각 이름으로 받는다. `@RequestParam`으로도 파일을 받을 수 있지만, `@RequestPart`는 "multipart의 한 조각"이라는 뜻이 분명하다.

### 3.3 크기 제한은 두 겹

Spring Boot 설정 `spring.servlet.multipart.max-file-size`(파일 하나)와 `max-request-size`(요청 전체)를 넘으면, **컨트롤러에 오기 전에** 요청을 나누는 단계에서 `MaxUploadSizeExceededException`이 난다. 컨트롤러 메서드는 불리지도 않으니, 이 예외는 `@RestControllerAdvice`에서 잡아 우리 오류 응답으로 바꿔야 한다. 안 잡으면 Spring 기본 오류 응답이 나간다.

설정만으로 충분해 보이지만 서비스 코드에서도 크기를 다시 본다. 설정은 바뀔 수 있고(운영에서 누가 50MB로 올리면?), 테스트의 `MockMvc`는 실제 Tomcat의 multipart 해석을 거치지 않아 설정 제한이 걸리지 않는다. **규칙(10MB)은 코드에 두고, 설정은 너무 큰 요청이 메모리에 다 올라오기 전에 끊는 앞문**으로 본다.

### 3.4 매직 넘버: 파일 앞 몇 바이트가 말해 주는 형식

대부분의 파일 형식은 맨 앞에 정해진 바이트를 둔다. 이것을 **매직 넘버**(파일 시그니처)라 한다.

| 형식 | 앞부분 바이트 | 글자로 보면 |
| --- | --- | --- |
| JPEG | `FF D8 FF` | (글자 아님) |
| PNG | `89 50 4E 47 0D 0A 1A 0A` | `.PNG\r\n.\n` |
| GIF | `47 49 46 38 37 61` 또는 `...39 61` | `GIF87a`, `GIF89a` |
| WebP | `52 49 46 46 ?? ?? ?? ?? 57 45 42 50` | `RIFF....WEBP` (가운데 4바이트는 파일 길이) |

확장자(`.jpg`)는 이름일 뿐이고, `Content-Type`도 보낸 쪽이 적은 값이다. 실제 내용의 첫 바이트를 보면 "적어도 이 형식인 척하는 파일"인지 알 수 있다.

하지만 매직 넘버도 **앞부분만** 본다. PNG 머리 8바이트를 붙이고 뒤는 엉터리인 파일도 통과한다. 그래서 한 단계 더, 실제 이미지 읽기 도구로 열어 본다(3.5).

### 3.5 머리 정보만 읽기: ImageIO와 ImageReader

Java 표준 라이브러리 `javax.imageio.ImageIO`는 이미지를 읽고 쓴다. `ImageIO.read(...)`는 이미지를 **전부 풀어** 픽셀 배열(`BufferedImage`)을 만든다. 4000×3000 사진이면 픽셀만 1,200만 개라 메모리를 꽤 쓴다.

가로·세로만 알고 싶으면 `ImageReader`를 쓴다.

1. `ImageIO.createImageInputStream(...)`으로 바이트를 읽을 통로를 만든다.
2. `ImageIO.getImageReaders(input)`가 이 내용을 읽을 수 있는 읽기 도구를 찾는다. 없으면 이미지가 아니다.
3. `reader.getWidth(0)`, `reader.getHeight(0)`은 첫 번째 그림의 가로·세로를 **파일 머리에서** 읽는다. 픽셀은 풀지 않는다.
4. 머리가 망가져 있으면 `IOException`이 난다. 엉터리 파일을 여기서 거른다.

### 3.6 Thumbnailator: 줄이기와 EXIF 방향

[Thumbnailator](https://github.com/coobird/thumbnailator)는 이미지 줄이기를 짧게 쓰게 해 주는 라이브러리다.

```java
Thumbnails.of(입력)          // 파일, InputStream, BufferedImage 등
        .size(1920, 1920)     // 이 상자 안에 들어가게, 비율은 지키며
        .outputFormat("jpg")
        .outputQuality(0.9)   // jpg 품질(0~1)
        .toFile(저장할 파일);
```

- `size(w, h)`는 가로·세로 비율을 유지하면서 `w×h` 상자 안에 들어가게 맞춘다. 3000×1000을 `size(1920, 1920)`에 넣으면 1920×640이 된다.
- `scale(1.0)`은 크기를 그대로 둔다. Thumbnailator는 `size`와 `scale` 중 하나를 꼭 정해야 해서, "줄일 필요가 없을 때"는 `scale(1.0)`을 쓴다.
- **EXIF 방향**: JPEG 사진에는 카메라가 적은 부가 정보(EXIF)가 붙는다. 그중 Orientation은 "보여 줄 때 몇 도 돌려라"는 표시다. Thumbnailator는 JPEG를 읽을 때 이 표시를 읽어 **픽셀을 실제로 돌린** 결과를 만든다(기본으로 켜져 있다). 새로 저장한 파일은 이미 바로 선 픽셀이라, 표시를 몰라도 바로 보인다.

### 3.7 WebP와 ImageIO 플러그인(SPI)

Java 표준 `ImageIO`는 JPEG, PNG, GIF, BMP 등을 읽지만 **WebP는 읽지 못한다.** TwelveMonkeys `imageio-webp`는 WebP 읽기 도구를 `ImageIO`에 더해 주는 플러그인이다.

"플러그인"이 되는 원리는 Java의 **SPI(Service Provider Interface)**다. 라이브러리 jar 안의 `META-INF/services/...` 파일에 "나는 이런 ImageReader를 제공한다"고 적혀 있고, `ImageIO`는 클래스패스에서 이 파일들을 찾아 읽기 도구 목록에 넣는다. 그래서 **의존성만 추가하면 코드를 고치지 않아도** `ImageIO.getImageReaders`·`ImageIO.read`가 WebP를 읽는다. Spring Boot 스타터를 넣으면 자동 설정이 켜지는 것과 비슷한 느낌이다.

이 플러그인은 WebP **읽기**만 한다. Java로 WebP를 **쓸** 방법이 없어서, WebP 원본은 받은 그대로 두고 썸네일은 PNG로 저장한다(R-15).

### 3.8 GIF·WebP 원본은 그대로

GIF는 여러 장면이 들어 있는 애니메이션일 수 있다. `ImageIO.read`는 **첫 장면 하나만** 읽는다. 그걸 줄여 다시 저장하면 움직이지 않는 그림이 된다. 그래서 GIF 원본은 받은 바이트를 그대로 쓰고, 썸네일만 첫 장면으로 만든다. WebP도 애니메이션이 있을 수 있고, 위처럼 쓸 수도 없어서 그대로 둔다.

### 3.9 저장 이름은 UUID

받은 파일 이름(`getOriginalFilename()`)으로 저장하면:

- 다른 사람의 `photo.jpg`와 겹쳐 덮어쓴다.
- 이름에 `../`나 `/`를 넣으면 업로드 폴더 밖 경로가 될 수 있다(경로 조작, path traversal).
- 한글·공백·특수문자 이름이 주소(`/uploads/...`)에서 말썽을 부린다.

그래서 저장 이름은 서버가 `UUID.randomUUID()`로 짓고, 확장자도 **매직 넘버로 알아낸 형식**에서 붙인다. 원래 이름은 DB의 `original_name`에만 기록용으로 둔다.

### 3.10 정적 파일 내보내기와 캐시

올린 파일은 `app.upload.dir` 폴더(개발: 코드 저장소 아래 `uploads/`, git 제외)에 있다. 이걸 브라우저가 `/uploads/{파일명}` 주소로 열 수 있어야 한다. Spring MVC의 `addResourceHandlers`는 "이 주소 패턴은 이 폴더의 파일로 답하라"는 설정이다. `src/main/resources/static`의 파일을 내보내는 것과 같은 장치를, 클래스패스 대신 디스크 폴더(`file:`)에 쓰는 것이다.

캐시: 응답에 `Cache-Control: max-age=2592000, public`(30일)을 붙이면 브라우저(와 중간 캐시)는 30일 동안 서버에 다시 묻지 않고 저장해 둔 것을 쓴다. 보통 오래 캐시하면 "파일이 바뀌었는데 옛 그림이 보이는" 문제가 생긴다. 여기서는 **파일 이름이 UUID라서 같은 이름의 내용이 바뀌는 일이 없다.** 새 그림은 늘 새 이름이다. 그래서 길게 캐시해도 안전하다.

## 4. 동작 원리

에디터에서 사진 두 장을 고르고 발행하기까지:

```
브라우저: 에디터의 [이미지] 버튼 → 숨긴 <input type="file" multiple> 열기 → a.jpg, b.png 고름
  for 고른 순서대로:
    FormData { file: a.jpg }
    POST /api/images   (multipart/form-data, 쿠키로 로그인)
     │
     ▼ Tomcat이 조각을 나눔 ── 10MB 넘으면 여기서 MaxUploadSizeExceededException
     │                          → GlobalExceptionHandler → 400 IMAGE_TOO_LARGE
     ▼ JWT 필터 → @PreAuthorize("isAuthenticated()")  비회원이면 401
     ▼ ImageController.upload(member, file)
     ▼ ImageService.upload  ── 트랜잭션 ──
          ├ 비었나? → 400 (file 칸)        ├ 10MB 넘나? → 400 IMAGE_TOO_LARGE
          ├ 첫 12바이트 매직 넘버 → JPEG/PNG/GIF/WEBP, 아니면 400 UNSUPPORTED_IMAGE
          ├ ImageReader로 머리 읽기 → 긴 변 길이, 못 읽으면 400 UNSUPPORTED_IMAGE
          ├ 이름 = UUID  →  {uuid}.jpg, t_{uuid}.jpg
          ├ 원본 쓰기: jpg/png는 Thumbnailator(긴 변 > 1920이면 줄임, EXIF 반영)
          │            gif/webp는 바이트 그대로
          ├ 썸네일 쓰기: 긴 변 400(작으면 그대로), jpg→jpg, 나머지→png
          ├ image 행 저장 (path=/uploads/{uuid}.jpg, thumbnail_path=/uploads/t_{uuid}.jpg)
          └ 중간에 실패하면 쓴 파일 두 개를 지우고 예외를 다시 던짐
     ▼ 201 { id, url: "/uploads/{uuid}.jpg", thumbnailUrl: "/uploads/t_{uuid}.jpg" }
    에디터: 현재 선택 끝 뒤에 <img src="/uploads/{uuid}.jpg" alt="a.jpg"> 넣기
  발행: POST /api/posts  contentHtml에 <img src="/uploads/...">가 들어 있음
     ▼ HtmlSanitizer: img는 src가 ^/uploads/[A-Za-z0-9_-]+\.(jpg|jpeg|png|gif|webp)$ 일 때만 남김

나중에 글 목록: GET /api/posts
     ▼ PostThumbnails.of(이 페이지의 글들)
          각 글 본문에서 첫 <img src="/uploads/...">를 정규식으로 찾음
          image 테이블을 path IN (...)으로 한 번에 읽어 thumbnail_path를 붙임
     ▼ 목록 한 줄마다 thumbnailUrl
브라우저가 /uploads/t_{uuid}.jpg 요청
     ▼ ResourceHttpRequestHandler: 업로드 폴더의 파일 + Cache-Control: max-age=2592000, public
```

## 5. 이 프로젝트에서는

### 5.1 설정: 폴더와 크기 제한

`src/main/resources/application.yml`

```yaml
spring:
  servlet:
    multipart:
      # 이미지는 파일당 10MB까지 (POST-05). 넘으면 400 IMAGE_TOO_LARGE
      max-file-size: 10MB
      max-request-size: 11MB
...
app:
  upload:
    dir: ${APP_UPLOAD_DIR:./uploads}
```

- `max-file-size: 10MB`: 파일 하나가 10MB를 넘으면 요청을 나누는 단계에서 끊는다.
- `max-request-size: 11MB`: 요청 전체 한도. 파일 조각 말고도 경계 문자열과 조각 머리가 붙으므로 파일 한도보다 조금 크게 둔다.
- `app.upload.dir`: 환경 변수 `APP_UPLOAD_DIR`가 있으면 그것, 없으면 `./uploads`. 개발 프로필(`application-dev.yml`)은 `/Users/chosun-nhn54/IdeaProjects/blog/uploads`, 운영은 `${APP_UPLOAD_DIR}`(반드시 줘야 함)로 덮어쓴다. `.gitignore`에 `uploads/`가 있어 올린 파일이 커밋되지 않는다.

`global/config/UploadProperties.java`

```java
@ConfigurationProperties(prefix = "app.upload")
public record UploadProperties(Path dir) {
}
```

- `app.upload.dir` 글자를 Spring이 `java.nio.file.Path`로 바꿔 넣는다. 레코드 하나라 짧다.
- `BlogApplication`의 `@ConfigurationPropertiesScan`이 이 레코드를 찾아 빈으로 등록한다([01](./01-spring-boot-basics.md)).

크기 초과 예외는 `global/error/GlobalExceptionHandler.java`에서 바꾼다.

```java
/** 업로드 크기 제한(spring.servlet.multipart.max-file-size)을 넘음. 컨트롤러에 오기 전에 난다. */
@ExceptionHandler(MaxUploadSizeExceededException.class)
public ResponseEntity<ErrorResponse> handleTooLarge(MaxUploadSizeExceededException e) {
    return error(ErrorCode.IMAGE_TOO_LARGE);
}
```

`ErrorCode`에는 `UNSUPPORTED_IMAGE(400, "jpg, png, gif, webp 이미지만 올릴 수 있습니다.")`와 `IMAGE_TOO_LARGE(400, "10MB 이하 이미지만 올릴 수 있습니다.")`가 있다.

### 5.2 컨트롤러: `image/presentation/ImageController.java`

```java
/** 201 { id, url, thumbnailUrl }. jpg/png/gif/webp가 아니면 400 UNSUPPORTED_IMAGE, 10MB 초과 400 IMAGE_TOO_LARGE. */
@PostMapping("/api/images")
@PreAuthorize("isAuthenticated()")
@ResponseStatus(HttpStatus.CREATED)
public ImageResponse upload(@AuthenticationPrincipal LoginMember member,
                            @RequestPart(name = "file", required = false) MultipartFile file) {
    return ImageResponse.from(imageService.upload(member.id(), file));
}
```

- `@PreAuthorize("isAuthenticated()")`: 회원만. 비회원은 401([12](./12-spring-security-filter-chain.md)의 메서드 보안).
- `@RequestPart(name = "file", required = false)`: `file` 조각을 받는다. `required = false`인 이유는, 조각이 아예 없을 때 Spring 기본 예외 대신 **우리 규칙의 400(칸 이름 `file`)**을 서비스에서 주려는 것이다.
- 블로그 주소(`@CurrentBlog`)를 받지 않는다. 본문 이미지뿐 아니라 프로필·블로그 이미지에도 같이 쓰는 API라 어느 주소에서 불러도 같다.
- 응답 `ImageResponse(id, url, thumbnailUrl)`는 엔티티의 `path`, `thumbnailPath`를 그대로 담는다.

### 5.3 형식 판단: `image/domain/ImageType.java`

```java
JPEG("image/jpeg", "jpg", "jpg"),
PNG("image/png", "png", "png"),
GIF("image/gif", "gif", "png"),
WEBP("image/webp", "webp", "png");
```

- 세 값은 차례로 응답·DB에 적을 `Content-Type`, 원본 확장자, 썸네일 저장 형식이다. GIF·WebP는 투명한 부분이 있을 수 있어 썸네일을 png로 둔다(jpg는 투명도가 없다).

```java
public static Optional<ImageType> detect(byte[] head) {
    return Arrays.stream(values()).filter(type -> type.matches(head)).findFirst();
}

private boolean matches(byte[] h) {
    return switch (this) {
        case JPEG -> h.length >= 3 && (h[0] & 0xFF) == 0xFF && (h[1] & 0xFF) == 0xD8 && (h[2] & 0xFF) == 0xFF;
        case PNG -> h.length >= 8 && (h[0] & 0xFF) == 0x89 && h[1] == 'P' && h[2] == 'N' && h[3] == 'G'
                && h[4] == 0x0D && h[5] == 0x0A && h[6] == 0x1A && h[7] == 0x0A;
        case GIF -> h.length >= 6 && h[0] == 'G' && h[1] == 'I' && h[2] == 'F' && h[3] == '8'
                && (h[4] == '7' || h[4] == '9') && h[5] == 'a';
        case WEBP -> h.length >= 12 && h[0] == 'R' && h[1] == 'I' && h[2] == 'F' && h[3] == 'F'
                && h[8] == 'W' && h[9] == 'E' && h[10] == 'B' && h[11] == 'P';
    };
}
```

- `detect`: 네 형식을 차례로 대 보고 처음 맞는 것을 돌려준다. 없으면 빈 `Optional`.
- `h[0] & 0xFF`: Java의 `byte`는 부호가 있어 -128~127이다. `0xFF`(255)는 byte로 -1이라 `h[0] == 0xFF`는 늘 거짓이 된다. `& 0xFF`로 0~255 정수로 바꾼 뒤 비교한다. 127 이하 값(`'P'` 같은 글자)은 그대로 비교해도 된다.
- `h.length >= 3` 같은 길이 확인이 먼저다. 3바이트짜리 파일에서 `h[7]`을 읽으면 `ArrayIndexOutOfBoundsException`이 난다.
- WebP는 4~7번째 바이트(파일 길이)를 건너뛰고 8~11번째의 `WEBP`를 본다.

```java
/** 원본을 줄여 다시 저장해도 되는 형식인가. GIF는 애니메이션, WebP는 Java로 쓸 수 없어서 원본 그대로 둔다. */
public boolean resizable() {
    return this == JPEG || this == PNG;
}
```

### 5.4 올리기: `image/application/ImageService.java`

```java
@Transactional
public Image upload(Long uploaderId, MultipartFile file) {
    if (file == null || file.isEmpty()) {
        throw BusinessException.invalidField("file", "이미지 파일을 골라 주세요.");
    }
    if (file.getSize() > MAX_SIZE) {
        throw new BusinessException(ErrorCode.IMAGE_TOO_LARGE);
    }
    byte[] bytes = readAll(file);
    ImageType type = ImageType.detect(Arrays.copyOf(bytes, Math.min(bytes.length, 12)))
            .orElseThrow(() -> new BusinessException(ErrorCode.UNSUPPORTED_IMAGE));
    int longestSide = longestSide(bytes);
```

- 줄 1~3: 조각이 없거나(`null`) 비었으면 칸 오류 400. 화면은 `file` 칸 옆에 문구를 붙일 수 있다([22](./22-bean-validation.md)의 칸별 오류 모양).
- 줄 4~6: `MAX_SIZE = 10L * 1024 * 1024`. 설정과 같은 한도를 코드에서 한 번 더 본다(3.3).
- `readAll`: `file.getBytes()`. 10MB 이하라 메모리에 올려도 괜찮다. 같은 바이트를 형식 판단·머리 읽기·원본 쓰기·썸네일 쓰기에 여러 번 쓰므로 한 번 읽어 둔다.
- `Arrays.copyOf(bytes, Math.min(bytes.length, 12))`: 앞 12바이트만 잘라 `detect`에 준다. 파일이 12바이트보다 짧으면 있는 만큼만.
- `longestSide(bytes)`: 머리를 읽어 긴 변 길이를 얻는다. 여기서 엉터리 파일이 걸린다.

```java
    String name = UUID.randomUUID().toString();
    String originalFile = name + "." + type.getExtension();
    String thumbnailFile = "t_" + name + "." + type.getThumbnailFormat();
    try {
        Files.createDirectories(uploadDir);
        writeOriginal(bytes, type, longestSide, uploadDir.resolve(originalFile));
        writeThumbnail(bytes, type, longestSide, uploadDir.resolve(thumbnailFile));
        return imageRepository.save(Image.uploaded(uploaderId, URL_PREFIX + originalFile,
                URL_PREFIX + thumbnailFile, originalName(file), type.getContentType(), bytes.length));
    } catch (IOException e) {
        deleteFiles(originalFile, thumbnailFile);
        throw new UncheckedIOException(e);
    } catch (RuntimeException e) {
        deleteFiles(originalFile, thumbnailFile);
        throw e;
    }
}
```

- 파일 이름: `{uuid}.{확장자}`와 `t_{uuid}.{썸네일 형식}`. 확장자는 **매직 넘버로 알아낸 형식**에서 온다. `cat.png`라고 보낸 JPEG는 `.jpg`로 저장된다.
- `Files.createDirectories(uploadDir)`: 폴더가 없으면 만든다(있으면 아무 일도 안 함). 처음 실행해도 미리 폴더를 만들 필요가 없다.
- `uploadDir.resolve(originalFile)`: 폴더 경로 + 파일 이름. 이름이 UUID라 `../`가 끼어들 틈이 없다.
- DB에는 `URL_PREFIX + 파일명`, 즉 `/uploads/{uuid}.jpg`를 저장한다. 화면이 그대로 `<img src>`로 쓰는 주소이고, 본문 HTML의 `src`와 **같은 글자**라서 나중에 본문에서 이미지를 찾을 수 있다(5.6).
- **실패 정리**: 원본을 쓴 뒤 썸네일에서 실패하거나, 저장(`save`)이 실패하면 쓴 파일 둘을 지운다. 트랜잭션은 DB만 되돌리고 **디스크 파일은 되돌리지 않는다.** 직접 지우지 않으면 DB에 행이 없는 고아 파일이 쌓인다. `IOException`(검사 예외)은 `UncheckedIOException`으로 감싸 다시 던져 트랜잭션이 롤백되게 한다.

생성자에서 폴더 경로를 절대 경로로 바꿔 둔다.

```java
this.uploadDir = uploadProperties.dir().toAbsolutePath().normalize();
```

`./uploads` 같은 상대 경로는 서버를 어느 폴더에서 띄웠느냐에 따라 위치가 달라진다. 시작할 때 한 번 절대 경로로 굳힌다. `normalize()`는 `a/./b/../c` 같은 표기를 `a/c`로 정리한다.

#### 머리만 읽기

```java
private int longestSide(byte[] bytes) {
    try (ImageInputStream input = ImageIO.createImageInputStream(new ByteArrayInputStream(bytes))) {
        Iterator<ImageReader> readers = ImageIO.getImageReaders(input);
        if (!readers.hasNext()) {
            throw new BusinessException(ErrorCode.UNSUPPORTED_IMAGE);
        }
        ImageReader reader = readers.next();
        try {
            reader.setInput(input);
            return Math.max(reader.getWidth(0), reader.getHeight(0));
        } finally {
            reader.dispose();
        }
    } catch (IOException e) {
        // 앞부분만 이미지처럼 꾸민 파일 등
        throw new BusinessException(ErrorCode.UNSUPPORTED_IMAGE);
    }
}
```

- `try (...)`: `ImageInputStream`은 닫아야 하는 자원이라 try-with-resources로 연다.
- `getImageReaders(input)`: 이 바이트를 읽을 수 있는 도구 목록. WebP는 TwelveMonkeys 플러그인 덕에 여기서 도구가 나온다(3.7).
- `getWidth(0)`, `getHeight(0)`: 0번 그림(GIF라면 첫 장면)의 크기. 머리만 읽는다.
- `reader.dispose()`: 읽기 도구가 잡은 자원을 놓는다. `finally`라 예외가 나도 부른다.
- PNG 머리만 붙인 엉터리 파일은 `getWidth`에서 `IOException`이 나고, 400 `UNSUPPORTED_IMAGE`로 바뀐다.

#### 원본과 썸네일 쓰기

```java
private void writeOriginal(byte[] bytes, ImageType type, int longestSide, Path target) throws IOException {
    if (!type.resizable()) {
        Files.write(target, bytes);
        return;
    }
    // Thumbnailator는 JPEG의 EXIF 방향을 읽어 픽셀을 돌린다(휴대폰 사진이 눕지 않게)
    Thumbnails.Builder<?> builder = Thumbnails.of(new ByteArrayInputStream(bytes));
    fit(builder, longestSide, MAX_SIDE).outputFormat(type.getExtension()).outputQuality(0.9).toFile(target.toFile());
}
```

- GIF·WebP: 받은 바이트를 그대로 쓴다. 애니메이션이 살아 있다.
- JPEG·PNG: Thumbnailator로 다시 쓴다. **줄일 필요가 없는 작은 사진도 다시 쓰는 이유**는 EXIF 방향을 픽셀에 반영하기 위해서다. 그대로 두면 휴대폰 사진이 브라우저·환경에 따라 누워 보일 수 있다.
- `outputQuality(0.9)`: JPEG 압축 품질. 1.0에 가까울수록 크고 선명하다. PNG는 무손실이라 품질 값의 영향이 없다.

```java
private void writeThumbnail(byte[] bytes, ImageType type, int longestSide, Path target) throws IOException {
    Thumbnails.Builder<?> builder;
    if (type.resizable()) {
        builder = Thumbnails.of(new ByteArrayInputStream(bytes));
    } else {
        // GIF는 첫 장면, WebP는 TwelveMonkeys 플러그인으로 읽는다
        BufferedImage image = ImageIO.read(new ByteArrayInputStream(bytes));
        if (image == null) {
            throw new BusinessException(ErrorCode.UNSUPPORTED_IMAGE);
        }
        builder = Thumbnails.of(image);
    }
    fit(builder, longestSide, THUMBNAIL_SIDE).outputFormat(type.getThumbnailFormat()).toFile(target.toFile());
}
```

- GIF·WebP는 `ImageIO.read`로 픽셀을 먼저 만든다(GIF는 첫 장면). `ImageIO.read`는 읽을 도구가 없으면 예외가 아니라 `null`을 돌려주므로 `null`을 확인한다.
- 썸네일 형식은 `getThumbnailFormat()`(jpg 또는 png).

```java
/** 긴 변이 limit보다 크면 limit 안으로 줄이고, 작으면 그대로(키우지 않는다). */
private static Thumbnails.Builder<?> fit(Thumbnails.Builder<?> builder, int longestSide, int limit) {
    return longestSide > limit ? builder.size(limit, limit) : builder.scale(1.0);
}
```

- `size(limit, limit)`: 정사각형 상자 안에 맞추니 결국 **긴 변이 limit**가 된다. 3000×1000 → 1920×640, 썸네일은 400×133.
- 작은 그림은 `scale(1.0)`으로 그대로 둔다. 50×30 그림을 400px로 키우면 흐릿해질 뿐이다. 앞에서 `ImageReader`로 긴 변을 미리 알아 둔 이유가 이 분기다.

#### 원래 이름 다듬기

```java
private static String originalName(MultipartFile file) {
    String name = file.getOriginalFilename();
    if (name == null || name.isBlank()) {
        return "image";
    }
    // 경로가 붙어 오는 브라우저도 있어 마지막 이름만 남기고, 컬럼 길이(255)에 맞춘다
    String last = name.substring(Math.max(name.lastIndexOf('/'), name.lastIndexOf('\\')) + 1);
    return last.length() > 255 ? last.substring(last.length() - 255) : last;
}
```

기록용이라도 DB 컬럼(255자)을 넘으면 저장이 실패하므로 자른다. 끝 255자를 남기는 것은 확장자를 살리려는 것이다. 이 값은 파일 경로에 절대 쓰지 않는다.

### 5.5 내보내기: `global/config/WebConfig.java`

```java
@Override
public void addResourceHandlers(ResourceHandlerRegistry registry) {
    String location = uploadProperties.dir().toAbsolutePath().normalize().toUri().toString();
    registry.addResourceHandler("/uploads/**")
            .addResourceLocations(location.endsWith("/") ? location : location + "/")
            .setCacheControl(CacheControl.maxAge(Duration.ofDays(30)).cachePublic());
}
```

- `toUri().toString()`: 경로를 `file:///Users/.../uploads/` 꼴 주소로 바꾼다. `addResourceLocations`는 `classpath:`나 `file:`로 시작하는 위치를 받는다.
- **끝의 `/`가 중요하다.** 위치가 `file:/.../uploads`(슬래시 없음)이면 Spring은 이것을 폴더가 아니라 파일처럼 보고 그 옆에서 찾으려 해 파일을 못 찾는다. 그래서 없으면 붙인다.
- `/uploads/**`: `/uploads/abc.jpg` 요청이 오면 폴더에서 `abc.jpg`를 찾아 돌려준다. 없으면 `NoResourceFoundException` → 404. Spring의 리소스 처리기는 `../`로 폴더 밖을 읽으려는 요청을 막는다.
- `CacheControl.maxAge(Duration.ofDays(30)).cachePublic()`: `Cache-Control: max-age=2592000, public`. UUID 이름이라 길게 캐시해도 된다(3.10).
- `Content-Type`은 확장자로 정해진다(`.png` → `image/png`). 확장자를 매직 넘버로 붙였기 때문에 실제 내용과 맞는다. 형식을 속인 파일이 다른 형식으로 해석되는 일을 줄인다.

보안 설정은 `/api/admin/**`만 관리자로 막고 나머지는 `permitAll`이다. 그래서 `/uploads/**`는 로그인 없이 열린다. 비공개 글의 이미지도 주소를 알면 열린다는 뜻인데, 주소가 추측할 수 없는 UUID라 이 단계에서는 이것으로 둔다.

### 5.6 엔티티와 본문 속 이미지: `Image`, `HtmlSanitizer`, `PostThumbnails`

`image/domain/Image.java`의 칸은 `uploader_id`, `path`, `thumbnail_path`, `original_name`, `content_type`, `size`다. `uploader_id`는 외래 키 없이 회원 id만 둔다(회원 ↔ 이미지 순환 참조를 피하려는 ERD 결정).

본문 정화(`global/security/HtmlSanitizer.java`)는 `img`의 `src`를 이렇게 제한한다.

```java
/** 이미지는 이 서비스에 올린 파일만 (/uploads/{uuid}.{ext}). */
... Pattern.compile("^/uploads/[A-Za-z0-9_-]+\\.(jpg|jpeg|png|gif|webp)$", Pattern.CASE_INSENSITIVE);
...
.allowElements("img")
.allowAttributes("src").matching(UPLOADED_IMAGE_SRC).onElements("img")
.allowAttributes("alt").onElements("img")
```

- 남의 서버 이미지(`https://...`)나 `data:` 이미지는 `src`가 지워진다. 본문 이미지는 **이 서비스에 올린 파일뿐**이다([14](./14-xss-sanitize-csp.md)).
- 그 덕에 저장된 본문의 `<img>`는 늘 `src="/uploads/..."` 꼴이고, 이 글자가 `image.path`와 같다.

`image/application/PostThumbnails.java`는 목록 한 줄의 썸네일을 정한다.

```java
private static final Pattern FIRST_IMAGE = Pattern.compile("<img[^>]*\\ssrc=\"(/uploads/[^\"]+)\"");

@Transactional(readOnly = true)
public Map<Long, String> of(Collection<Post> posts) {
    Map<Long, String> firstImageByPost = new HashMap<>();
    for (Post post : posts) {
        firstImage(post.getContentHtml()).ifPresent(path -> firstImageByPost.put(post.getId(), path));
    }
    if (firstImageByPost.isEmpty()) {
        return Map.of();
    }
    Map<String, Image> images = imageRepository.findByPathIn(firstImageByPost.values()).stream()
            .collect(Collectors.toMap(Image::getPath, Function.identity(), (first, second) -> first));
    Map<Long, String> thumbnails = new HashMap<>();
    firstImageByPost.forEach((postId, path) -> {
        Image image = images.get(path);
        if (image != null && image.getThumbnailPath() != null) {
            thumbnails.put(postId, image.getThumbnailPath());
        }
    });
    return thumbnails;
}
```

- 정규식: `<img` 뒤 아무 속성(`[^>]*`)을 지나 공백 뒤 `src="/uploads/..."`의 주소 부분을 잡는다. HTML을 정규식으로 읽는 것은 보통 위험하지만, 여기 본문은 **서버가 정화해 모양이 정해진 HTML**이라 이 꼴만 남아 있다.
- 1단계: 글마다 첫 이미지 주소를 찾아 `글 id → 주소` 맵을 만든다(DB를 안 씀).
- 2단계: 그 주소들로 `findByPathIn` **한 번**. Spring Data가 메서드 이름에서 `where path in (...)`을 만든다. 글 20개에 이미지 쿼리 20번(N+1)이 아니라 1번이다([06](./06-jpa-entity-mapping.md)).
- `toMap`의 세 번째 인자 `(first, second) -> first`: 같은 주소의 행이 둘 나오면(원래 없어야 하지만) 예외 대신 첫 번째를 쓴다.
- 3단계: `글 id → 썸네일 주소`. 이미지가 없는 글, 행을 못 찾은 글은 맵에 없고, 응답에서 `thumbnailUrl: null`이 된다.
- 대표 이미지 고르기(POST-07, `thumbnail_image_id`)는 백로그라 아직 보지 않는다. 지금 글쓰기 API는 `thumbnailImageId`가 오면 400으로 돌려보낸다.

이 맵을 글 목록(`PostController`), 홈(`HomeController`), 검색(`SearchController`)이 같이 쓴다. `PostSummaryResponse.of(post, blog, thumbnails.get(post.getId()))`처럼 붙인다.

### 5.7 화면: `FormData`로 보내기 (`frontend/src/api/client.ts`)

```ts
/**
 * 파일 올리기 (multipart/form-data, T037). 본문 이미지 등.
 * Content-Type은 브라우저가 경계 문자열(boundary)과 함께 정하므로 직접 넣지 않는다.
 */
export async function uploadFile<T>(path: string, file: File, field = 'file'): Promise<T> {
  const form = new FormData()
  form.append(field, file)
  const response = await fetch(path, {
    method: 'POST',
    headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
    credentials: 'same-origin',
    body: form,
  })
  if (response.ok) {
    return (await response.json()) as T
  }
  const error = new ApiError(response.status, await readError(response))
  if (response.status === 401) {
    redirectToLogin()
  }
  throw error
}
```

- `FormData`: 자바스크립트로 만드는 "폼 내용". `form.append('file', file)`은 Thymeleaf 폼의 `<input type="file" name="file">`과 같은 조각을 만든다. `body`에 `FormData`를 주면 브라우저가 multipart 본문을 만든다.
- **`Content-Type`을 직접 넣지 않는다.** 직접 `multipart/form-data`라고만 적으면 `boundary`가 빠져 서버가 조각을 나누지 못한다. 비워 두면 브라우저가 `multipart/form-data; boundary=...`를 알맞게 붙인다. JSON 요청을 보내는 `api()` 함수와 따로 둔 이유다.
- `X-Requested-With`: 이 프로젝트의 CSRF 대책([13](./13-csrf-samesite-cors.md)). 다른 사이트의 폼은 이 헤더를 붙일 수 없다.
- `credentials: 'same-origin'`: 로그인 쿠키를 같이 보낸다.
- 401이면 로그인 화면으로 보낸다(로그인이 풀린 상태).

### 5.8 화면: 에디터의 이미지 버튼 (`frontend/src/components/editor/Editor.tsx`)

```ts
// 서버 허용 목록과 같게 src·alt만 쓴다. base64 이미지(data:)는 서버가 지우므로 받지 않는다
Image.configure({ inline: false, allowBase64: false }),
```

- Tiptap의 Image 확장. `inline: false`는 이미지를 문단 안 글자 사이가 아니라 **한 덩어리(블록)**로 둔다. `allowBase64: false`는 `data:image/...` 이미지를 받지 않는다. 서버 정화가 어차피 지우므로, 화면에서도 넣지 못하게 맞춘다([26](./26-wysiwyg-editor-tiptap.md)의 "허용 서식 맞추기").

```tsx
<button type="button" className="btn" disabled={uploading}
        onMouseDown={(event) => event.preventDefault()} onClick={() => fileInput.current?.click()}>
  {uploading ? '올리는 중…' : '이미지'}
</button>
<input ref={fileInput} type="file" accept="image/jpeg,image/png,image/gif,image/webp" multiple hidden
       onChange={insertImages} />
```

- 파일 고르기 창은 `<input type="file">`만 열 수 있다. 모양을 다른 버튼과 맞추려고 입력은 숨기고(`hidden`), 버튼을 누르면 `ref`로 숨긴 입력을 `click()`한다.
- `accept`: 파일 고르기 창에서 이미지 형식만 먼저 보이게 하는 **안내**다. 사용자가 "모든 파일"로 바꿔 고를 수 있으니 검사는 서버가 한다.
- `multiple`: 여러 장을 한 번에 고른다.
- `onMouseDown`의 `preventDefault()`: 버튼을 누를 때 에디터가 포커스(커서 위치)를 잃지 않게 한다. 다른 서식 버튼과 같은 방법이다.

```ts
async function insertImages(event: ChangeEvent<HTMLInputElement>) {
  const files = Array.from(event.target.files ?? [])
  event.target.value = ''
  if (!editor || files.length === 0) {
    return
  }
  setUploading(true)
  setUploadError(null)
  for (const file of files) {
    try {
      const image = await uploadFile<UploadedImage>('/api/images', file)
      // 방금 넣은 사진이 선택된 채라 setImage는 그 사진을 바꿔 버린다. 선택의 끝 뒤에 넣어 고른 순서를 지킨다
      editor.chain().focus().insertContentAt(editor.state.selection.to,
        { type: 'image', attrs: { src: image.url, alt: file.name } }).run()
    } catch (error) {
      setUploadError(`${file.name}: ${errorMessage(error)}`)
    }
  }
  setUploading(false)
}
```

- `Array.from(event.target.files ?? [])`: 고른 파일 목록(`FileList`)을 배열로. 순서는 고른 순서다.
- `event.target.value = ''`: 입력을 비운다. 안 비우면 같은 파일을 다시 골랐을 때 "바뀐 게 없다"고 보고 `onChange`가 안 불린다.
- `for ... of` + `await`: **하나씩 차례로** 올린다. `Promise.all`로 한꺼번에 올리면 먼저 끝난 것부터 들어가 고른 순서가 섞일 수 있다(POST-05 "고른 순서대로").
- `try/catch`가 반복 **안**에 있다. 한 장이 거절돼도(형식·크기) 나머지는 계속 올리고, 거절된 파일 이름과 이유만 알린다(spec US2 시나리오 6).
- `insertContentAt(위치, 노드)`: 문서의 지정 위치에 이미지 노드를 넣는다. 위치는 지금 선택의 끝(`selection.to`).

#### 실제로 겪은 버그: 두 장 골랐는데 한 장만

처음 코드는 Tiptap Image 확장의 기본 명령을 썼다.

```ts
editor.chain().focus().setImage({ src: image.url, alt: file.name }).run()
```

헤드리스 Chrome으로 사진 두 장을 골라 확인해 보니 본문에 **두 번째 사진 한 장만** 남았다. 이유는 이렇다.

1. 첫 사진을 `setImage`로 넣으면, 에디터의 선택이 **방금 넣은 이미지 노드 전체**(노드 선택, NodeSelection)가 된다.
2. 두 번째 `setImage`는 "지금 선택한 자리에 넣기"다. 글자를 선택하고 타자를 치면 선택한 글자가 바뀌듯, 선택돼 있던 첫 사진이 두 번째 사진으로 **바뀌어 버렸다.**

고친 방법은 "선택한 것을 바꾸기" 대신 "선택의 **끝 뒤에** 넣기"다. `insertContentAt(editor.state.selection.to, ...)`는 첫 사진 바로 뒤에 두 번째 사진을 넣으므로 둘 다 남고 순서도 지켜진다. 커서가 글자 사이에 있을 때(선택이 비었을 때)는 `to`가 커서 자리라 이전과 똑같이 동작한다. 다시 확인하니 `alt`가 `blogmain.png`, `after-publish.png` 순서로 두 장이 들어갔다(커밋 e7d7d26).

교훈: 에디터 명령은 대개 **"지금 선택"을 기준으로** 움직인다. 같은 명령을 연달아 부를 때는 명령 뒤 선택이 어디로 가는지 확인해야 한다.

### 5.9 테스트: `ImageUploadIntegrationTest`

테스트 부모 `IntegrationTestSupport`는 업로드 폴더를 임시 폴더로 바꾼다.

```java
@SpringBootTest(properties = "app.upload.dir=${java.io.tmpdir}/blog-test-uploads")
```

테스트가 개발용 `uploads/`에 파일을 쌓지 않게 한다. 모든 통합 테스트가 같은 속성을 써야 Spring이 컨텍스트를 재사용하므로 부모 클래스에 둔다([05](./05-spring-testing.md)).

테스트 이미지는 `BufferedImage`에 주황색을 칠하고 `ImageIO.write`로 jpg/png/gif/bmp 바이트를 만든다. Java는 WebP를 쓸 수 없으므로 1×1 WebP 바이트를 base64 글자로 넣어 둔다(`TINY_WEBP`).

| 테스트 | 확인하는 것 |
| --- | --- |
| `bigJpegIsShrunkAndThumbnailed` | 3000×1000 jpg → 원본 1920×640, 썸네일 가로 400, 주소가 `/uploads/{uuid}.jpg`·`/uploads/t_{uuid}.jpg`, DB에 올린 사람·원래 이름·형식 |
| `smallPngIsNotEnlargedAndIsServed` | 50×30 png는 키우지 않음, `/uploads/...`로 열면 `image/png`와 `Cache-Control: max-age` |
| `gifIsKeptAsIsAndWebpIsAccepted` | GIF 원본 바이트가 그대로, 썸네일은 png. WebP는 받고 썸네일을 만듦 |
| `disguisedOrBrokenFilesAreRejected` | 이름·형식만 jpg인 글자 파일, PNG 머리만 붙인 엉터리, BMP → 모두 400 `UNSUPPORTED_IMAGE` |
| `overTenMegabytesIsRejected` | 10MB+1바이트 → 400 `IMAGE_TOO_LARGE` (MockMvc라 서비스의 검사가 걸린다) |
| `listShowsThumbnailOfFirstImageInBody` | 이미지를 넣어 발행한 글의 목록 `thumbnailUrl`이 그 이미지의 썸네일 |
| `loginIsRequired` | 비회원 401 |

`PostThumbnailsTest`는 DB 없이 `firstImage` 정규식만 확인하는 단위 테스트다.

## 6. 자주 하는 실수와 함정

1. **확장자나 `getContentType()`으로 형식 판단**: 보낸 쪽이 마음대로 적는 값이다. 매직 넘버 + 실제로 읽어 보기.
2. **매직 넘버만 보고 끝**: 머리 몇 바이트만 붙인 파일이 통과한다. 이미지 읽기 도구로 열어 본다.
3. **받은 파일 이름으로 저장**: 덮어쓰기, `../` 경로 조작. 서버가 UUID로 짓는다.
4. **`byte`를 `0xFF`와 바로 비교**: Java `byte`는 부호가 있어 늘 거짓. `& 0xFF`.
5. **크기 초과 예외를 컨트롤러에서 잡으려 함**: `MaxUploadSizeExceededException`은 컨트롤러 전에 난다. `@RestControllerAdvice`에서 잡는다.
6. **`fetch`에 `Content-Type: multipart/form-data`를 직접 적음**: boundary가 빠져 서버가 못 읽는다. `FormData`면 비워 둔다.
7. **트랜잭션이 파일도 되돌려 줄 거라 믿음**: DB만 롤백된다. 쓴 파일은 직접 지운다.
8. **GIF를 줄여 다시 저장**: 애니메이션이 첫 장면만 남는다.
9. **작은 그림도 늘림**: 흐려진다. 긴 변이 한도 이하면 그대로.
10. **EXIF 방향 무시**: 휴대폰 세로 사진이 눕는다. JPEG는 다시 써서 픽셀에 반영한다.
11. **`addResourceLocations`의 끝 `/` 빠뜨림**: 폴더를 파일로 보고 404가 난다.
12. **목록에서 글마다 이미지 조회**: N+1. 주소를 모아 `IN` 한 번.
13. **에디터 명령을 연달아 부르며 선택을 잊음**: `setImage`가 방금 넣은 이미지를 바꿨다. 위치를 정해 넣는다.
14. **여러 장을 `Promise.all`로 올림**: 끝난 순서대로 들어가 고른 순서가 섞인다.

## 7. 직접 해 보기

**실습 1. 테스트**

```bash
./mvnw test -Dtest='ImageUploadIntegrationTest,PostThumbnailsTest'
```

**실습 2. curl로 올리기** (bash, `docker compose up -d && ./mvnw spring-boot:run`)

```bash
P=8080; R="--resolve blog.test:$P:127.0.0.1"
H='-H X-Requested-With:XMLHttpRequest'
# 로그인해서 쿠키를 jar에 받기
curl -s $R $H -H Content-Type:application/json -c jar -X POST http://blog.test:$P/api/auth/login \
  -d '{"email":"내 이메일","password":"내 비밀번호"}' -o /dev/null -w '%{http_code}\n'
# 실제 png 올리기 → 201 {id, url, thumbnailUrl}
curl -s $R $H -b jar -F file=@./사진.png http://blog.test:$P/api/images; echo
```

`-F file=@경로`가 curl의 multipart 조각 만들기다. `-F`를 쓰면 curl이 `Content-Type: multipart/form-data; boundary=...`를 알아서 붙인다(5.7과 같은 이유로 직접 적지 않는다). `-v`를 붙이면 boundary가 보인다.

**실습 3. 위장 파일**

```bash
echo '<script>alert(1)</script>' > fake.png
curl -s $R $H -b jar -F 'file=@fake.png;type=image/png' http://blog.test:$P/api/images; echo
# {"code":"UNSUPPORTED_IMAGE",...}
xxd fake.png | head -1   # 앞 바이트가 3c 73 63 72 ('<scr')라 PNG가 아님
xxd ./사진.png | head -1  # 8950 4e47 0d0a 1a0a 로 시작
```

`;type=image/png`로 조각의 `Content-Type`을 속여도 거절된다.

**실습 4. 줄인 크기와 캐시 헤더**

```bash
URL=/uploads/{응답의 url 파일명}; TH=/uploads/{응답의 thumbnailUrl 파일명}
sips -g pixelWidth -g pixelHeight ./사진.png                 # 원래 크기
curl -s $R http://blog.test:$P$URL -o o.bin && sips -g pixelWidth -g pixelHeight o.bin   # 긴 변 1920 이하
curl -s $R http://blog.test:$P$TH -o t.bin && sips -g pixelWidth -g pixelHeight t.bin    # 긴 변 400 이하
curl -s $R -D - -o /dev/null http://blog.test:$P$TH | grep -i -E 'cache-control|content-type'
# Cache-Control: max-age=2592000, public
ls ~/IdeaProjects/blog/uploads | tail -4   # UUID 이름 파일들
```

`sips`는 macOS에 들어 있는 이미지 도구다. 1920px보다 큰 사진(휴대폰 사진, 큰 스크린숏)으로 해 보면 줄어든 것이 보인다.

**실습 5. DB와 본문 비교**

```bash
docker exec blog-mysql mysql -ublog -pblog blog -e "SELECT id, path, thumbnail_path, original_name, content_type, size FROM image ORDER BY id DESC LIMIT 3"
```

에디터로 이 이미지를 넣은 글을 발행하고 `GET /api/posts/{id}`의 `contentHtml`에서 `src`가 `path`와 같은지, 목록 `GET /api/posts`의 `thumbnailUrl`이 `thumbnail_path`와 같은지 본다.

**실습 6. 버그 다시 만들기**

`Editor.tsx`의 `insertContentAt(...)` 줄을 `editor.chain().focus().setImage({ src: image.url, alt: file.name }).run()`로 바꾸고 `npm run dev`로 띄워 사진 두 장을 한 번에 고른다. 한 장만 남는다. 되돌린다.

**실습 7. 실패 정리 보기**

`ImageService.upload`의 `catch (RuntimeException e)` 블록에서 `deleteFiles(...)` 줄을 지우고, `imageRepository.save` 바로 앞에 `if (true) throw new IllegalStateException("x");`를 넣어 업로드해 본다. `uploads/`에 DB 행 없는 파일이 남는다. 되돌린다.

## 8. 확인 문제

1. 파일 이름이 `cat.jpg`이고 `Content-Type: image/jpeg`인데도 거절될 수 있는 이유는?
<details><summary>답</summary>둘 다 보낸 쪽이 적는 값이라 믿지 않는다. 서버는 파일 앞 바이트(매직 넘버)로 실제 형식을 보고, 이미지 읽기 도구로 머리를 읽어 본다. 내용이 JPEG가 아니면 400 UNSUPPORTED_IMAGE다.</details>

2. 매직 넘버 검사가 있는데 `ImageReader`로 한 번 더 읽는 이유는?
<details><summary>답</summary>매직 넘버는 앞 몇 바이트만 본다. PNG 머리 8바이트만 붙이고 나머지는 엉터리인 파일도 통과한다. 실제로 머리 정보(가로·세로)를 읽어 봐야 이미지인지 안다. 그 긴 변 길이는 줄일지 말지를 정하는 데도 쓴다.</details>

3. `(h[0] & 0xFF) == 0xFF`에서 `& 0xFF`가 필요한 이유는?
<details><summary>답</summary>Java의 byte는 부호가 있어 -128~127이다. 바이트 0xFF는 -1로 읽혀 정수 255와 같지 않다. & 0xFF로 0~255 정수로 바꿔 비교한다.</details>

4. 10MB 제한을 설정(`max-file-size`)과 서비스 코드 두 곳에 두는 이유는?
<details><summary>답</summary>설정은 큰 요청을 메모리에 다 받기 전에 끊는 앞문이고, 바뀔 수 있다. 규칙(10MB)은 코드에 둬야 설정이 바뀌거나 MockMvc처럼 설정 제한을 거치지 않는 경로에서도 지켜진다. 설정 쪽 예외(MaxUploadSizeExceededException)는 컨트롤러 전에 나서 @RestControllerAdvice에서 같은 IMAGE_TOO_LARGE로 바꾼다.</details>

5. GIF 원본을 줄이지 않고 그대로 두는 이유는? 썸네일은 어떻게 만드나?
<details><summary>답</summary>ImageIO는 GIF의 첫 장면만 읽으므로 줄여 다시 저장하면 애니메이션이 사라진다. 원본은 바이트 그대로 두고, 썸네일만 첫 장면을 읽어 400px png로 만든다.</details>

6. pom.xml에 `imageio-webp`를 넣기만 했는데 `ImageIO.read`가 WebP를 읽게 된 원리는?
<details><summary>답</summary>Java SPI. 플러그인 jar의 META-INF/services에 ImageReader 제공자가 적혀 있고, ImageIO가 클래스패스에서 이를 찾아 읽기 도구 목록에 넣는다. 코드를 고칠 필요가 없다.</details>

7. `/uploads/**`에 30일 캐시를 걸어도 "옛 그림이 보이는" 문제가 없는 이유는?
<details><summary>답</summary>파일 이름이 UUID라 한 주소의 내용은 바뀌지 않는다. 새 그림은 늘 새 주소다.</details>

8. 썸네일 쓰기에서 실패하면 `ImageService`는 무엇을 하고, 왜 직접 해야 하나?
<details><summary>답</summary>이미 쓴 원본·썸네일 파일을 지우고 예외를 다시 던진다. 트랜잭션 롤백은 DB만 되돌리고 디스크 파일은 되돌리지 않아, 지우지 않으면 DB 행 없는 고아 파일이 남는다.</details>

9. 글 목록 20개의 썸네일을 구할 때 이미지 쿼리가 한 번인 이유는?
<details><summary>답</summary>PostThumbnails가 먼저 본문 정규식으로 글마다 첫 이미지 주소를 모으고, findByPathIn(주소들)로 where path in (...) 한 번에 읽은 뒤 맵으로 짝짓는다. 글마다 찾으면 N+1이다. 본문 src와 image.path가 같은 글자(/uploads/...)라 가능하다.</details>

10. `uploadFile`에서 `Content-Type` 헤더를 적지 않는 이유는?
<details><summary>답</summary>multipart 본문은 boundary로 조각을 나누는데, boundary는 브라우저가 지어 Content-Type에 함께 적는다. 직접 multipart/form-data만 적으면 boundary가 빠져 서버가 조각을 나누지 못한다. body가 FormData면 브라우저가 알맞게 붙인다.</details>

11. 사진 두 장을 골랐는데 한 장만 남았던 버그의 원인과 고친 방법은?
<details><summary>답</summary>첫 사진을 setImage로 넣으면 선택이 그 이미지 노드(NodeSelection)가 되고, 두 번째 setImage가 그 선택을 바꿔 첫 사진을 덮었다. insertContentAt(editor.state.selection.to, 이미지)로 선택의 끝 뒤에 넣어 둘 다 남고 순서도 지켜지게 했다.</details>

12. 여러 장을 `Promise.all`이 아니라 `for ... of` + `await`로 올리는 이유는?
<details><summary>답</summary>한꺼번에 올리면 먼저 끝난 것부터 본문에 들어가 고른 순서가 섞일 수 있다. 하나씩 차례로 올려야 고른 순서대로 들어간다(POST-05). 반복 안의 try/catch로 한 장이 거절돼도 나머지는 계속한다.</details>

## 9. 더 읽을거리

- research.md R-15(이미지 처리 결정), data-model.md의 image, contracts/rest-api.md `POST /api/images`
- Spring Boot 레퍼런스 "Web → Servlet Web Applications → Multipart File Uploads"(`spring.servlet.multipart.*`)
- Spring Framework 레퍼런스 "Web MVC → Multipart Resolver", "@RequestPart", "MVC Config → Static Resources"(`addResourceHandlers`, `CacheControl`)
- Thumbnailator 위키: https://github.com/coobird/thumbnailator/wiki
- TwelveMonkeys ImageIO: https://github.com/haraldk/TwelveMonkeys
- Java `javax.imageio` 패키지 문서(`ImageIO`, `ImageReader`), `java.util.ServiceLoader`(SPI)
- MDN "Using FormData Objects", "File signatures"(매직 넘버), "Cache-Control"
- OWASP "File Upload Cheat Sheet": https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html
- Tiptap 문서 "Image extension", "Commands → insertContentAt"
