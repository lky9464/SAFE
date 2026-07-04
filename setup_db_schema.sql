-- SAFE MariaDB schema (from installation guide v3.0)

USE safe_db;

CREATE TABLE IF NOT EXISTS tb_checklist (
    checklist_id    INT             NOT NULL AUTO_INCREMENT  COMMENT '체크리스트 ID',
    checklist_nm    VARCHAR(100)    NOT NULL                 COMMENT '체크리스트명',
    data_type       CHAR(1)         NOT NULL                 COMMENT '자료유형',
    base_law        VARCHAR(200)    NULL                     COMMENT '기준 법령·지침명',
    source_file     VARCHAR(500)    NULL                     COMMENT '생성에 사용된 지식DB 파일명',
    item_cnt        INT             NOT NULL DEFAULT 0       COMMENT '점검항목 수',
    created_by      VARCHAR(50)     NOT NULL                 COMMENT '생성자',
    created_at      DATETIME        NOT NULL DEFAULT NOW()   COMMENT '생성일시',
    updated_at      DATETIME        NOT NULL DEFAULT NOW()   COMMENT '수정일시',
    use_yn          CHAR(1)         NOT NULL DEFAULT 'Y'     COMMENT '사용여부',
    CONSTRAINT pk_checklist PRIMARY KEY (checklist_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS tb_checklist_item (
    item_id         INT             NOT NULL AUTO_INCREMENT,
    checklist_id    INT             NOT NULL,
    item_no         INT             NOT NULL,
    category        VARCHAR(50)     NOT NULL,
    item_content    TEXT            NOT NULL,
    judge_criteria  TEXT            NULL,
    law_ref         VARCHAR(200)    NULL,
    risk_level      CHAR(1)         NOT NULL DEFAULT 'M',
    created_at      DATETIME        NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_checklist_item PRIMARY KEY (item_id),
    CONSTRAINT fk_item_checklist FOREIGN KEY (checklist_id) REFERENCES tb_checklist (checklist_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS tb_review (
    review_id       INT             NOT NULL AUTO_INCREMENT,
    business_nm     VARCHAR(200)    NOT NULL,
    data_type       CHAR(1)         NOT NULL,
    checklist_id    INT             NOT NULL,
    file_nm         VARCHAR(300)    NOT NULL,
    file_path       VARCHAR(500)    NOT NULL,
    file_size       BIGINT          NULL,
    file_ext        VARCHAR(10)     NULL,
    ocr_yn          CHAR(1)         NOT NULL DEFAULT 'N',
    total_item_cnt  INT             NOT NULL DEFAULT 0,
    pass_cnt        INT             NOT NULL DEFAULT 0,
    warn_cnt        INT             NOT NULL DEFAULT 0,
    fail_cnt        INT             NOT NULL DEFAULT 0,
    final_result    CHAR(1)         NOT NULL DEFAULT 'W',
    reviewer        VARCHAR(50)     NOT NULL,
    review_at       DATETIME        NOT NULL DEFAULT NOW(),
    remark          VARCHAR(500)    NULL,
    CONSTRAINT pk_review PRIMARY KEY (review_id),
    CONSTRAINT fk_review_checklist FOREIGN KEY (checklist_id) REFERENCES tb_checklist (checklist_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS tb_review_detail (
    detail_id       INT             NOT NULL AUTO_INCREMENT,
    review_id       INT             NOT NULL,
    item_id         INT             NOT NULL,
    item_no         INT             NOT NULL,
    category        VARCHAR(50)     NOT NULL,
    item_content    TEXT            NOT NULL,
    extracted_val   TEXT            NULL,
    judge_result    CHAR(1)         NOT NULL,
    judge_reason    TEXT            NULL,
    law_ref         VARCHAR(200)    NULL,
    similarity      DECIMAL(5,4)    NULL,
    CONSTRAINT pk_review_detail PRIMARY KEY (detail_id),
    CONSTRAINT fk_detail_review FOREIGN KEY (review_id) REFERENCES tb_review (review_id) ON DELETE CASCADE,
    CONSTRAINT fk_detail_item FOREIGN KEY (item_id) REFERENCES tb_checklist_item (item_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS tb_duplicate_detect (
    detect_id       INT             NOT NULL AUTO_INCREMENT,
    review_id       INT             NOT NULL,
    file_nm_a       VARCHAR(300)    NOT NULL,
    file_nm_b       VARCHAR(300)    NOT NULL,
    file_hash_a     VARCHAR(64)     NOT NULL,
    file_hash_b     VARCHAR(64)     NOT NULL,
    amount_a        DECIMAL(15,0)   NULL,
    amount_b        DECIMAL(15,0)   NULL,
    detect_type     VARCHAR(50)     NOT NULL,
    detected_at     DATETIME        NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_duplicate PRIMARY KEY (detect_id),
    CONSTRAINT fk_dup_review FOREIGN KEY (review_id) REFERENCES tb_review (review_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS tb_system_config (
    config_key      VARCHAR(100)    NOT NULL,
    config_val      TEXT            NULL,
    config_desc     VARCHAR(200)    NULL,
    updated_by      VARCHAR(50)     NULL,
    updated_at      DATETIME        NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_config PRIMARY KEY (config_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS tb_access_log (
    log_id          BIGINT          NOT NULL AUTO_INCREMENT,
    user_id         VARCHAR(50)     NOT NULL,
    action_type     VARCHAR(50)     NOT NULL,
    target_id       INT             NULL,
    target_type     VARCHAR(50)     NULL,
    ip_addr         VARCHAR(45)     NULL,
    user_agent      VARCHAR(200)    NULL,
    logged_at       DATETIME        NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_access_log PRIMARY KEY (log_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE INDEX idx_checklist_type     ON tb_checklist      (data_type, use_yn);
CREATE INDEX idx_review_type        ON tb_review         (data_type);
CREATE INDEX idx_review_result      ON tb_review         (final_result);
CREATE INDEX idx_review_reviewer    ON tb_review         (reviewer);
CREATE INDEX idx_review_at          ON tb_review         (review_at);
CREATE INDEX idx_detail_review      ON tb_review_detail  (review_id, judge_result);
CREATE INDEX idx_log_at             ON tb_access_log     (logged_at);
CREATE INDEX idx_log_user           ON tb_access_log     (user_id, logged_at);

INSERT INTO tb_system_config (config_key, config_val, config_desc, updated_by) VALUES
('GEMINI_API_KEY',    '',          'Gemini API 키 (체크리스트 생성용)',        'admin'),
('OCR_LANG',          'kor+eng',   'Tesseract OCR 언어팩',                    'admin'),
('UPLOAD_PATH',       './uploads', '업로드 파일 임시 저장 경로',               'admin'),
('AUTO_DEL_DAYS',     '7',         '업로드 파일 자동 삭제 일수 (0=삭제안함)',   'admin'),
('MAX_FILE_SIZE_MB',  '100',       '업로드 최대 파일 크기 (MB)',               'admin'),
('DB_HOST',           'localhost', 'MariaDB 호스트',                          'admin'),
('DB_NAME',           'safe_db',   'MariaDB 데이터베이스명',                  'admin'),
('DB_USER',           'safe_user', 'MariaDB 접속 계정',                       'admin');
