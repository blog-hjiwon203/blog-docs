-- Crowfoot 문서 665 버전 62 (2026-10-08)에서 내보낸 MySQL DDL. 직접 고치지 말고 Crowfoot을 고친 뒤 다시 내보낸다.
-- https://crowfoot.java21.net/workspaces/49/models/665

CREATE TABLE member (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '회원 번호',
    profile_image_id BIGINT COMMENT '프로필 이미지',
    email VARCHAR(255) COMMENT '이메일-----이메일 가입 회원만 값이 있고 모두 인증됨. 소셜 가입·탈퇴 회원은 NULL',
    password_hash VARCHAR(100) COMMENT '비밀번호 해시-----bcrypt',
    nickname VARCHAR(20) NOT NULL COMMENT '닉네임',
    role VARCHAR(10) NOT NULL DEFAULT 'USER' COMMENT '역할-----가입은 항상 USER. ADMIN은 data.sql로만',
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE' COMMENT '상태-----모든 로그인 경로에서 먼저 확인',
    suspended_until DATETIME COMMENT '정지 종료 시각-----SUSPENDED + NULL = 영구 정지. 사유는 moderation_log 최신 SUSPEND 행',
    withdrawn_at DATETIME COMMENT '탈퇴 시각',
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '가입 시각',
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '수정 시각',
    PRIMARY KEY (id),
    CONSTRAINT uk_member_email UNIQUE (email),
    CONSTRAINT uk_member_nickname UNIQUE (nickname),
    CONSTRAINT ck_member_role CHECK (role IN ('USER', 'ADMIN')),
    CONSTRAINT ck_member_status CHECK (status IN ('ACTIVE', 'SUSPENDED', 'WITHDRAWN'))
) COMMENT='회원-----이메일 가입·소셜 가입 회원. 탈퇴해도 행은 남는다';
CREATE TABLE social_account (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT 'ID',
    member_id BIGINT NOT NULL COMMENT '회원 번호',
    provider VARCHAR(10) NOT NULL COMMENT '제공사',
    provider_user_id VARCHAR(100) NOT NULL COMMENT '제공사 회원 식별자',
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '생성 일시',
    PRIMARY KEY (id),
    CONSTRAINT uk_social_account_provider_provider_user_id UNIQUE (provider, provider_user_id),
    CONSTRAINT uk_social_account_member_id_provider UNIQUE (member_id, provider),
    CONSTRAINT ck_social_account_provider CHECK (provider IN ('KAKAO', 'GOOGLE'))
) COMMENT='소셜 연동';
CREATE TABLE email_verification (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT 'ID',
    email VARCHAR(255) NOT NULL COMMENT '이메일',
    code VARCHAR(10) NOT NULL COMMENT '인증 코드',
    expires_at DATETIME NOT NULL COMMENT '만료 시각',
    verified_at DATETIME COMMENT '인증 완료 시각',
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '생성 일시',
    PRIMARY KEY (id)
) COMMENT='이메일 인증-----가입 전 단계라 회원과 연결하지 않는다';
CREATE TABLE password_reset_token (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT 'ID',
    member_id BIGINT NOT NULL COMMENT '회원 번호',
    token_hash VARCHAR(64) NOT NULL COMMENT '토큰 해시-----링크 토큰의 SHA-256. 원문은 저장하지 않는다',
    expires_at DATETIME NOT NULL COMMENT '만료 시각-----발급 후 30분',
    used_at DATETIME COMMENT '사용 시각-----한 번 쓰면 기록',
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '생성 일시',
    PRIMARY KEY (id),
    CONSTRAINT uk_password_reset_token_token_hash UNIQUE (token_hash)
) COMMENT='비밀번호 재설정 토큰';
CREATE TABLE image (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT 'ID',
    uploader_id BIGINT NOT NULL COMMENT '올린 회원-----member.id. 회원 ↔ 이미지 순환 참조를 피하려고 외래 키 없이 둔다. 서버가 로그인 회원으로 채운다',
    path VARCHAR(255) NOT NULL COMMENT '저장 경로',
    thumbnail_path VARCHAR(255) COMMENT '썸네일 경로',
    original_name VARCHAR(255) NOT NULL COMMENT '원래 파일명',
    content_type VARCHAR(20) NOT NULL COMMENT '파일 형식-----image/jpeg, image/png, image/gif, image/webp',
    size BIGINT NOT NULL COMMENT '크기(바이트)',
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '생성 일시',
    PRIMARY KEY (id),
    CONSTRAINT ck_image_size CHECK (size <= 10485760)
) COMMENT='이미지-----업로드 파일. ./uploads/{uuid}.{ext}';
CREATE TABLE blog (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT 'ID',
    moved_to_blog_id BIGINT COMMENT '이사 대상 블로그-----연쇄 이사 시 최종 대상으로 갱신',
    profile_image_id BIGINT COMMENT '프로필 이미지',
    member_id BIGINT NOT NULL COMMENT '회원 번호',
    address VARCHAR(32) NOT NULL COMMENT '주소-----영문 소문자·숫자·하이픈 4~32자, 불변',
    name VARCHAR(50) NOT NULL COMMENT '이름',
    description VARCHAR(500) COMMENT '소개글',
    is_primary TINYINT(1) NOT NULL DEFAULT 0 COMMENT '대표 블로그 여부',
    skin VARCHAR(20) NOT NULL DEFAULT 'BASIC' COMMENT '스킨',
    list_layout VARCHAR(10) NOT NULL DEFAULT 'LIST' COMMENT '메인 글 목록 형태',
    is_restricted TINYINT(1) NOT NULL DEFAULT 0 COMMENT '이용 제한 여부-----사유는 moderation_log 최신 RESTRICT_BLOG 행',
    deleted_at DATETIME COMMENT '삭제 시각',
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '생성 일시',
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '수정 일시',
    primary_owner_id BIGINT GENERATED ALWAYS AS (CASE WHEN is_primary = 1 AND deleted_at IS NULL THEN member_id END) STORED COMMENT '대표 블로그 주인(유니크용)-----회원당 대표 블로그 하나를 DB에서 보장하는 계산 컬럼',
    total_visitor_count BIGINT NOT NULL DEFAULT 0 COMMENT '누적 방문자-----매일 새벽 전날 방문자 수를 더한다. 오늘 방문자는 포함하지 않는다',
    PRIMARY KEY (id),
    CONSTRAINT uk_blog_address UNIQUE (address),
    CONSTRAINT uk_blog_primary_owner_id UNIQUE (primary_owner_id),
    CONSTRAINT ck_blog_list_layout CHECK (list_layout IN ('LIST', 'THUMBNAIL'))
) COMMENT='블로그-----주소는 삭제돼도 행이 남아 영구 예약';
CREATE TABLE category (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT 'ID',
    parent_id BIGINT COMMENT '상위 카테고리-----NULL 또는 1단계 상위',
    blog_id BIGINT NOT NULL COMMENT 'blog ID',
    name VARCHAR(30) NOT NULL COMMENT '이름',
    sort_order INT NOT NULL DEFAULT 0 COMMENT '순서',
    is_private TINYINT(1) NOT NULL DEFAULT 0 COMMENT '비공개 여부',
    parent_key BIGINT GENERATED ALWAYS AS (IFNULL(parent_id, 0)) STORED NOT NULL COMMENT '상위 키(유니크용)-----MySQL UNIQUE는 NULL끼리 중복을 허용하므로 최상위 이름 중복을 막기 위한 계산 컬럼',
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '수정 일시',
    PRIMARY KEY (id),
    CONSTRAINT uk_category_blog_id_parent_key_name UNIQUE (blog_id, parent_key, name)
) COMMENT='카테고리-----''전체 글''·''미분류''는 행이 아니라 가상 항목';
CREATE TABLE post (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '글 번호',
    blog_id BIGINT NOT NULL COMMENT 'blog ID',
    category_id BIGINT COMMENT '분류 ID',
    thumbnail_image_id BIGINT COMMENT '대표 이미지',
    title VARCHAR(200) NOT NULL COMMENT '제목',
    content_html MEDIUMTEXT NOT NULL COMMENT '본문-----서버 정화 후 저장',
    summary VARCHAR(300) COMMENT '요약-----jsoup으로 태그 제거',
    status VARCHAR(20) NOT NULL DEFAULT 'DRAFT' COMMENT '상태',
    visibility VARCHAR(20) NOT NULL DEFAULT 'PUBLIC' COMMENT '공개 범위',
    topic VARCHAR(20) COMMENT '주제-----NULL = 주제 없음',
    published_at DATETIME(6) COMMENT '처음 발행 시각-----정렬 기준, 수정해도 불변',
    scheduled_at DATETIME COMMENT '예약 발행 시각',
    view_count BIGINT NOT NULL DEFAULT 0 COMMENT '조회수',
    like_count INT NOT NULL DEFAULT 0 COMMENT '공감 수-----비정규화, 같은 트랜잭션에서 갱신',
    comment_count INT NOT NULL DEFAULT 0 COMMENT '댓글 수-----비정규화, 같은 트랜잭션에서 갱신',
    is_comment_allowed TINYINT(1) NOT NULL DEFAULT 1 COMMENT '댓글 허용 여부',
    is_blinded TINYINT(1) NOT NULL DEFAULT 0 COMMENT '숨김 여부-----사유는 moderation_log 최신 BLIND 행',
    deleted_at DATETIME COMMENT '삭제 시각',
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '생성 일시',
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '수정 시각',
    PRIMARY KEY (id),
    CONSTRAINT ck_post_status CHECK (status IN ('DRAFT', 'PUBLISHED', 'SCHEDULED')),
    CONSTRAINT ck_post_visibility CHECK (visibility IN ('PUBLIC', 'PRIVATE', 'SUBSCRIBERS')),
    CONSTRAINT ck_post_topic CHECK (topic IS NULL OR topic IN ('IT_DEV', 'TRAVEL', 'FOOD', 'DAILY', 'REVIEW', 'HOBBY', 'FINANCE', 'HEALTH', 'CULTURE', 'EDUCATION'))
) COMMENT='글-----글 주소 {주소}.blog.com/{id}. 이사하면 blog_id가 바뀌고 옛 주소는 301';
CREATE TABLE tag (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT 'ID',
    blog_id BIGINT NOT NULL COMMENT 'blog ID',
    name VARCHAR(30) NOT NULL COMMENT '이름',
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '수정 일시',
    PRIMARY KEY (id),
    CONSTRAINT uk_tag_blog_id_name UNIQUE (blog_id, name)
) COMMENT='태그';
CREATE TABLE post_tag (
    post_id BIGINT NOT NULL COMMENT '글 번호',
    tag_id BIGINT NOT NULL COMMENT '태그 ID',
    PRIMARY KEY (post_id, tag_id)
) COMMENT='글 태그-----글당 최대 10개는 서비스에서 검사';
CREATE TABLE view_log (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT 'ID',
    post_id BIGINT NOT NULL COMMENT '글 번호',
    viewer_key VARCHAR(64) NOT NULL COMMENT '조회자 키-----회원 id 또는 익명 식별자',
    viewed_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '조회 시각',
    PRIMARY KEY (id)
) COMMENT='조회 기록-----같은 viewer_key가 5분 안에 다시 열면 기록하지 않는다. 최근 1시간 인기 점수와 최근 7일 블로그 점수 집계. 7일보다 오래된 행은 매일 지운다';
CREATE TABLE post_like (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT 'ID',
    post_id BIGINT NOT NULL COMMENT '글 번호',
    member_id BIGINT NOT NULL COMMENT '회원 번호',
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '공감 시각',
    PRIMARY KEY (id),
    CONSTRAINT uk_post_like_member_id_post_id UNIQUE (member_id, post_id)
) COMMENT='공감';
CREATE TABLE comment (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT 'ID',
    parent_id BIGINT COMMENT '부모 댓글-----NULL 또는 1단계',
    post_id BIGINT NOT NULL COMMENT '글 번호',
    member_id BIGINT NOT NULL COMMENT '회원 번호',
    content VARCHAR(1000) NOT NULL COMMENT '내용',
    is_secret TINYINT(1) NOT NULL DEFAULT 0 COMMENT '비밀댓글 여부',
    is_blinded TINYINT(1) NOT NULL DEFAULT 0 COMMENT '숨김 여부-----사유는 moderation_log 최신 BLIND 행',
    deleted_at DATETIME COMMENT '삭제 시각-----답글이 있으면 ''삭제된 댓글입니다''로 표시',
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '생성 일시',
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '수정 일시',
    PRIMARY KEY (id)
) COMMENT='댓글';
CREATE TABLE guestbook (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT 'ID',
    parent_id BIGINT COMMENT '부모 글',
    blog_id BIGINT NOT NULL COMMENT 'blog ID',
    member_id BIGINT NOT NULL COMMENT '회원 번호',
    content VARCHAR(1000) NOT NULL COMMENT '내용',
    is_secret TINYINT(1) NOT NULL DEFAULT 0 COMMENT '비밀글 여부',
    deleted_at DATETIME COMMENT '삭제 시각',
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '생성 일시',
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '수정 일시',
    PRIMARY KEY (id)
) COMMENT='방명록-----규칙은 댓글과 같다';
CREATE TABLE subscription (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT 'ID',
    blog_id BIGINT NOT NULL COMMENT 'blog ID',
    member_id BIGINT NOT NULL COMMENT '회원 번호',
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '구독 시각',
    PRIMARY KEY (id),
    CONSTRAINT uk_subscription_member_id_blog_id UNIQUE (member_id, blog_id)
) COMMENT='구독';
CREATE TABLE notification (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT 'ID',
    receiver_id BIGINT NOT NULL COMMENT '받는 회원',
    type VARCHAR(20) NOT NULL COMMENT '종류',
    target_type VARCHAR(20) NOT NULL COMMENT '대상 종류',
    target_id BIGINT NOT NULL COMMENT '대상 번호',
    message VARCHAR(255) NOT NULL COMMENT '표시 문구',
    read_at DATETIME COMMENT '읽은 시각',
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '생성 일시',
    PRIMARY KEY (id),
    CONSTRAINT ck_notification_type CHECK (type IN ('COMMENT', 'REPLY', 'LIKE', 'SUBSCRIBE', 'SANCTION')),
    CONSTRAINT ck_notification_target_type CHECK (target_type IN ('POST', 'COMMENT', 'BLOG', 'MEMBER'))
) COMMENT='알림';
CREATE TABLE report (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT 'ID',
    reporter_id BIGINT NOT NULL COMMENT '신고한 회원',
    target_type VARCHAR(20) NOT NULL COMMENT '대상 종류',
    target_id BIGINT NOT NULL COMMENT '대상 번호',
    reason VARCHAR(20) NOT NULL COMMENT '사유',
    description VARCHAR(500) COMMENT '설명-----사유가 ETC면 필수',
    status VARCHAR(10) NOT NULL DEFAULT 'PENDING' COMMENT '처리 상태',
    result VARCHAR(20) COMMENT '처리 결과',
    processed_at DATETIME COMMENT '처리 시각',
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '생성 일시',
    PRIMARY KEY (id),
    CONSTRAINT uk_report_reporter_id_target_type_target_id UNIQUE (reporter_id, target_type, target_id),
    CONSTRAINT ck_report_target_type CHECK (target_type IN ('POST', 'COMMENT', 'BLOG')),
    CONSTRAINT ck_report_reason CHECK (reason IN ('SPAM', 'ADULT', 'ABUSE', 'COPYRIGHT', 'ETC')),
    CONSTRAINT ck_report_etc_description CHECK (reason <> 'ETC' OR description IS NOT NULL),
    CONSTRAINT ck_report_status CHECK (status IN ('PENDING', 'DONE')),
    CONSTRAINT ck_report_result CHECK (result IS NULL OR result IN ('BLIND', 'RESTRICT_BLOG', 'SUSPEND', 'REJECT'))
) COMMENT='신고';
CREATE TABLE moderation_log (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT 'ID',
    admin_id BIGINT NOT NULL COMMENT '처리한 관리자',
    action VARCHAR(20) NOT NULL COMMENT '조치',
    target_type VARCHAR(20) NOT NULL COMMENT '대상 종류',
    target_id BIGINT NOT NULL COMMENT '대상 번호',
    reason VARCHAR(20) COMMENT '사유-----제재(BLIND, SUSPEND, RESTRICT_BLOG)에는 필수. 안내 문구는 Java enum 필드에 둔다',
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '생성 일시',
    reason_detail VARCHAR(200) COMMENT '사유 설명-----사유가 ETC면 필수',
    PRIMARY KEY (id),
    CONSTRAINT ck_moderation_log_action CHECK (action IN ('BLIND', 'UNBLIND', 'SUSPEND', 'UNSUSPEND', 'RESTRICT_BLOG', 'UNRESTRICT_BLOG', 'REJECT_REPORT')),
    CONSTRAINT ck_moderation_log_target_type CHECK (target_type IN ('POST', 'COMMENT', 'BLOG', 'MEMBER', 'REPORT')),
    CONSTRAINT ck_moderation_log_reason CHECK (reason IS NULL OR reason IN ('SPAM', 'ADULT', 'ABUSE', 'COPYRIGHT', 'ETC')),
    CONSTRAINT ck_moderation_log_sanction_reason CHECK (action NOT IN ('BLIND', 'SUSPEND', 'RESTRICT_BLOG') OR reason IS NOT NULL),
    CONSTRAINT ck_moderation_log_etc_detail CHECK (reason IS NULL OR reason <> 'ETC' OR reason_detail IS NOT NULL)
) COMMENT='관리 이력-----INSERT만, 수정·삭제 API 없음. 제재 사유의 유일한 저장 위치: 대상의 최신 제재 행에서 사유를 읽는다';
CREATE TABLE notice (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT 'ID',
    admin_id BIGINT NOT NULL COMMENT '작성한 관리자',
    title VARCHAR(200) NOT NULL COMMENT '제목',
    content TEXT NOT NULL COMMENT '내용',
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '생성 일시',
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '수정 일시',
    PRIMARY KEY (id)
) COMMENT='공지';
CREATE TABLE post_bookmark (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT 'ID',
    post_id BIGINT NOT NULL COMMENT '글 번호',
    member_id BIGINT NOT NULL COMMENT '회원 번호',
    title_snapshot VARCHAR(200) NOT NULL COMMENT '저장 시점 글 제목',
    blog_name_snapshot VARCHAR(50) NOT NULL COMMENT '저장 시점 블로그 이름',
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '저장 시각',
    PRIMARY KEY (id),
    CONSTRAINT uk_post_bookmark_member_id_post_id UNIQUE (member_id, post_id)
) COMMENT='저장-----회원이 저장한 글. 볼 수 없게 된 글도 행을 남기고 저장 시점 제목·블로그 이름만 보여 준다(헌법 원칙 II 예외)';
CREATE TABLE blog_visit (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT 'ID',
    blog_id BIGINT NOT NULL COMMENT 'blog ID',
    visit_date DATE NOT NULL COMMENT '방문 날짜',
    visitor_key VARCHAR(64) NOT NULL COMMENT '방문자 키-----회원 id 또는 익명 식별자(view_log와 같은 방식)',
    referrer_type VARCHAR(10) NOT NULL DEFAULT 'DIRECT' COMMENT '유입 종류-----SEARCH, SNS, DIRECT, INTERNAL, OTHER',
    referrer_host VARCHAR(100) NOT NULL DEFAULT '' COMMENT '유입 호스트-----Referer의 호스트. 직접 방문이면 빈 값',
    PRIMARY KEY (id),
    CONSTRAINT uk_blog_visit_blog_id_visit_date_visitor_key UNIQUE (blog_id, visit_date, visitor_key),
    CONSTRAINT ck_blog_visit_referrer_type CHECK (referrer_type IN ('SEARCH','SNS','DIRECT','INTERNAL','OTHER'))
) COMMENT='블로그 방문-----블로그·날짜·방문자마다 한 행(하루 1회). 주인 본인 방문은 세지 않는다. 매일 새벽 blog_daily_stat·blog_referrer_daily로 모으고 7일 뒤 지운다';
CREATE TABLE blog_daily_stat (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT 'ID',
    blog_id BIGINT NOT NULL COMMENT 'blog ID',
    stat_date DATE NOT NULL COMMENT '날짜',
    visitor_count INT NOT NULL DEFAULT 0 COMMENT '방문자 수',
    view_count INT NOT NULL DEFAULT 0 COMMENT '글 조회 수',
    PRIMARY KEY (id),
    CONSTRAINT uk_blog_daily_stat_blog_id_stat_date UNIQUE (blog_id, stat_date)
) COMMENT='블로그 일별 통계-----전날 blog_visit을 모은 일별 방문자 수와 글 조회 수. 어제 방문자와 일·주·월 그래프에 쓴다';
CREATE TABLE blog_referrer_daily (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT 'ID',
    blog_id BIGINT NOT NULL COMMENT 'blog ID',
    stat_date DATE NOT NULL COMMENT '날짜',
    referrer_type VARCHAR(10) NOT NULL COMMENT '유입 종류',
    referrer_host VARCHAR(100) NOT NULL DEFAULT '' COMMENT '유입 호스트',
    visit_count INT NOT NULL DEFAULT 0 COMMENT '방문 수',
    PRIMARY KEY (id),
    CONSTRAINT uk_blog_referrer_daily_blog_id_stat_date_referrer_type_referrer_host UNIQUE (blog_id, stat_date, referrer_type, referrer_host)
) COMMENT='블로그 일별 유입 경로-----전날 blog_visit을 유입 종류·호스트별로 센 값';
CREATE TABLE blog_blocked_member (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT 'ID',
    blocked_member_id BIGINT NOT NULL COMMENT '차단 회원 번호',
    blog_id BIGINT NOT NULL COMMENT 'blog ID',
    memo VARCHAR(200) COMMENT '메모',
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '차단 시각',
    PRIMARY KEY (id),
    CONSTRAINT uk_blog_block_blog_id_blocked_member_id UNIQUE (blog_id, blocked_member_id)
) COMMENT='차단 회원-----블로그 주인이 차단한 회원. 그 블로그에 댓글·방명록을 쓰거나 구독할 수 없다. 주인이 쓰는 기능이라 관리 이력에 남기지 않는다';
CREATE TABLE blog_banned_word (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT 'ID',
    blog_id BIGINT NOT NULL COMMENT 'blog ID',
    word VARCHAR(30) NOT NULL COMMENT '금칙어',
    PRIMARY KEY (id),
    CONSTRAINT uk_blog_banned_word_blog_id_word UNIQUE (blog_id, word)
) COMMENT='금칙어-----블로그별 금칙어. 최대 100개, 대소문자 무시 포함 검사';

ALTER TABLE social_account ADD CONSTRAINT fk_social_account_member FOREIGN KEY (member_id) REFERENCES member (id);
ALTER TABLE password_reset_token ADD CONSTRAINT fk_password_reset_token_member FOREIGN KEY (member_id) REFERENCES member (id);
ALTER TABLE member ADD CONSTRAINT fk_member_image FOREIGN KEY (profile_image_id) REFERENCES image (id) ON DELETE SET NULL;
ALTER TABLE blog ADD CONSTRAINT fk_blog_member FOREIGN KEY (member_id) REFERENCES member (id);
ALTER TABLE blog ADD CONSTRAINT fk_blog_image FOREIGN KEY (profile_image_id) REFERENCES image (id) ON DELETE SET NULL;
ALTER TABLE blog ADD CONSTRAINT fk_blog_blog FOREIGN KEY (moved_to_blog_id) REFERENCES blog (id);
ALTER TABLE category ADD CONSTRAINT fk_category_blog FOREIGN KEY (blog_id) REFERENCES blog (id);
ALTER TABLE category ADD CONSTRAINT fk_category_category FOREIGN KEY (parent_id) REFERENCES category (id);
ALTER TABLE post ADD CONSTRAINT fk_post_blog FOREIGN KEY (blog_id) REFERENCES blog (id);
ALTER TABLE post ADD CONSTRAINT fk_post_category FOREIGN KEY (category_id) REFERENCES category (id) ON DELETE SET NULL;
ALTER TABLE post ADD CONSTRAINT fk_post_image FOREIGN KEY (thumbnail_image_id) REFERENCES image (id) ON DELETE SET NULL;
ALTER TABLE tag ADD CONSTRAINT fk_tag_blog FOREIGN KEY (blog_id) REFERENCES blog (id);
ALTER TABLE post_tag ADD CONSTRAINT fk_post_tag_post FOREIGN KEY (post_id) REFERENCES post (id) ON DELETE CASCADE;
ALTER TABLE post_tag ADD CONSTRAINT fk_post_tag_tag FOREIGN KEY (tag_id) REFERENCES tag (id) ON DELETE CASCADE;
ALTER TABLE view_log ADD CONSTRAINT fk_view_log_post FOREIGN KEY (post_id) REFERENCES post (id);
ALTER TABLE post_like ADD CONSTRAINT fk_post_like_member FOREIGN KEY (member_id) REFERENCES member (id);
ALTER TABLE post_like ADD CONSTRAINT fk_post_like_post FOREIGN KEY (post_id) REFERENCES post (id);
ALTER TABLE comment ADD CONSTRAINT fk_comment_post FOREIGN KEY (post_id) REFERENCES post (id);
ALTER TABLE comment ADD CONSTRAINT fk_comment_member FOREIGN KEY (member_id) REFERENCES member (id);
ALTER TABLE comment ADD CONSTRAINT fk_comment_comment FOREIGN KEY (parent_id) REFERENCES comment (id);
ALTER TABLE guestbook ADD CONSTRAINT fk_guestbook_blog FOREIGN KEY (blog_id) REFERENCES blog (id);
ALTER TABLE guestbook ADD CONSTRAINT fk_guestbook_member FOREIGN KEY (member_id) REFERENCES member (id);
ALTER TABLE guestbook ADD CONSTRAINT fk_guestbook_guestbook FOREIGN KEY (parent_id) REFERENCES guestbook (id);
ALTER TABLE subscription ADD CONSTRAINT fk_subscription_member FOREIGN KEY (member_id) REFERENCES member (id);
ALTER TABLE subscription ADD CONSTRAINT fk_subscription_blog FOREIGN KEY (blog_id) REFERENCES blog (id);
ALTER TABLE notification ADD CONSTRAINT fk_notification_member FOREIGN KEY (receiver_id) REFERENCES member (id);
ALTER TABLE report ADD CONSTRAINT fk_report_member FOREIGN KEY (reporter_id) REFERENCES member (id);
ALTER TABLE moderation_log ADD CONSTRAINT fk_moderation_log_member FOREIGN KEY (admin_id) REFERENCES member (id);
ALTER TABLE notice ADD CONSTRAINT fk_notice_member FOREIGN KEY (admin_id) REFERENCES member (id);
ALTER TABLE post_bookmark ADD CONSTRAINT fk_post_bookmark_member FOREIGN KEY (member_id) REFERENCES member (id);
ALTER TABLE post_bookmark ADD CONSTRAINT fk_post_bookmark_post FOREIGN KEY (post_id) REFERENCES post (id);
ALTER TABLE blog_visit ADD CONSTRAINT fk_blog_visit_blog FOREIGN KEY (blog_id) REFERENCES blog (id);
ALTER TABLE blog_daily_stat ADD CONSTRAINT fk_blog_daily_stat_blog FOREIGN KEY (blog_id) REFERENCES blog (id);
ALTER TABLE blog_referrer_daily ADD CONSTRAINT fk_blog_referrer_daily_blog FOREIGN KEY (blog_id) REFERENCES blog (id);
ALTER TABLE blog_blocked_member ADD CONSTRAINT fk_blog_block_blog FOREIGN KEY (blog_id) REFERENCES blog (id);
ALTER TABLE blog_blocked_member ADD CONSTRAINT fk_blog_block_blocked_member FOREIGN KEY (blocked_member_id) REFERENCES member (id);
ALTER TABLE blog_banned_word ADD CONSTRAINT fk_blog_banned_word_blog FOREIGN KEY (blog_id) REFERENCES blog (id);

CREATE INDEX idx_email_verification_email_created_at ON email_verification (email ASC, created_at DESC);
CREATE INDEX idx_image_uploader_id ON image (uploader_id ASC);
CREATE INDEX idx_post_blog_feed ON post (blog_id ASC, status ASC, visibility ASC, published_at DESC, id DESC);
CREATE INDEX idx_post_home_feed ON post (status ASC, visibility ASC, published_at DESC, id DESC);
CREATE INDEX idx_post_topic_feed ON post (topic ASC, status ASC, visibility ASC, published_at DESC);
CREATE INDEX idx_post_scheduled ON post (status ASC, scheduled_at ASC);
CREATE INDEX idx_view_log_viewed_at ON view_log (viewed_at ASC);
CREATE INDEX idx_view_log_post_id_viewer_key_viewed_at ON view_log (post_id ASC, viewer_key ASC, viewed_at ASC);
CREATE INDEX idx_post_like_created_at ON post_like (created_at ASC);
CREATE INDEX idx_comment_created_at ON comment (created_at ASC);
CREATE INDEX idx_comment_post_id_created_at ON comment (post_id ASC, created_at ASC);
CREATE INDEX idx_guestbook_blog_id_created_at ON guestbook (blog_id ASC, created_at ASC);
CREATE INDEX idx_notification_receiver_id_read_at ON notification (receiver_id ASC, read_at ASC);
CREATE INDEX idx_notification_target_type_target_id ON notification (target_type ASC, target_id ASC);
CREATE INDEX idx_report_status_target_type_target_id ON report (status ASC, target_type ASC, target_id ASC);
CREATE INDEX idx_moderation_log_target_type_target_id ON moderation_log (target_type ASC, target_id ASC, created_at DESC);
CREATE INDEX idx_moderation_log_created_at ON moderation_log (created_at ASC);
CREATE INDEX idx_notice_created_at ON notice (created_at DESC);
CREATE INDEX idx_post_bookmark_member_id_created_at_id ON post_bookmark (member_id ASC, created_at DESC, id DESC);
CREATE INDEX idx_blog_visit_visit_date ON blog_visit (visit_date ASC);
