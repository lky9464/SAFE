-- ============================================================
-- SAFE (Local Subsidy AI Fraud Detection System)
-- MariaDB 테이블 스키마
-- DB명: safe_db | Charset: utf8mb4 | Collation: utf8mb4_general_ci
-- ============================================================
-- [v3.0 변경내역] tb_checklist.source_file 컬럼 추가
--   - 지식DB 파일로 체크리스트를 생성/재생성할 때 출처 파일명을 저장합니다.
--   - 기존(v2.0) DB에 적용할 경우, 앱이 최초 기동 시 자동으로 컬럼을 추가하므로
--     별도 ALTER 작업 없이 그대로 사용해도 됩니다. (참고: checklist_db.py ensure_source_file_column)
-- ============================================================

USE safe_db;

-- ============================================================
-- 1. 체크리스트 마스터
--    공개자료 기반으로 Gemini API가 생성한 점검 규칙 저장
-- ============================================================
CREATE TABLE IF NOT EXISTS tb_checklist (
    checklist_id    INT             NOT NULL AUTO_INCREMENT  COMMENT '체크리스트 ID',
    checklist_nm    VARCHAR(100)    NOT NULL                 COMMENT '체크리스트명 (예: 지방보조금법_2026)',
    data_type       CHAR(1)         NOT NULL                 COMMENT '자료유형 (1:사업계획서 2:집행내역 3:지출증빙 4:정산보고서)',
    base_law        VARCHAR(200)    NULL                     COMMENT '기준 법령·지침명',
    source_file     VARCHAR(500)    NULL                     COMMENT '생성에 사용된 지식DB 파일명 (v3.0 추가)',
    item_cnt        INT             NOT NULL DEFAULT 0       COMMENT '점검항목 수',
    created_by      VARCHAR(50)     NOT NULL                 COMMENT '생성자',
    created_at      DATETIME        NOT NULL DEFAULT NOW()   COMMENT '생성일시',
    updated_at      DATETIME        NOT NULL DEFAULT NOW()   COMMENT '수정일시',
    use_yn          CHAR(1)         NOT NULL DEFAULT 'Y'     COMMENT '사용여부 (Y/N)',
    CONSTRAINT pk_checklist PRIMARY KEY (checklist_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci
  COMMENT='체크리스트 마스터';

-- ============================================================
-- 2. 체크리스트 항목
--    체크리스트별 세부 점검 항목
-- ============================================================
CREATE TABLE IF NOT EXISTS tb_checklist_item (
    item_id         INT             NOT NULL AUTO_INCREMENT  COMMENT '항목 ID',
    checklist_id    INT             NOT NULL                 COMMENT '체크리스트 ID (FK)',
    item_no         INT             NOT NULL                 COMMENT '항목 순번',
    category        VARCHAR(50)     NOT NULL                 COMMENT '분류 (예: 예산편성, 집행기준)',
    item_content    TEXT            NOT NULL                 COMMENT '점검항목 내용',
    judge_criteria  TEXT            NULL                     COMMENT '판단기준',
    law_ref         VARCHAR(200)    NULL                     COMMENT '법령 출처 (예: 지방보조금법 제15조)',
    risk_level      CHAR(1)         NOT NULL DEFAULT 'M'     COMMENT '위험등급 (H:높음 M:중간 L:낮음)',
    created_at      DATETIME        NOT NULL DEFAULT NOW()   COMMENT '생성일시',
    CONSTRAINT pk_checklist_item PRIMARY KEY (item_id),
    CONSTRAINT fk_item_checklist
        FOREIGN KEY (checklist_id)
        REFERENCES tb_checklist (checklist_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci
  COMMENT='체크리스트 항목';

-- ============================================================
-- 3. 검토 이력 마스터
--    사업계획서 등 자료 검토 건별 이력
-- ============================================================
CREATE TABLE IF NOT EXISTS tb_review (
    review_id       INT             NOT NULL AUTO_INCREMENT  COMMENT '검토 ID',
    business_nm     VARCHAR(200)    NOT NULL                 COMMENT '사업명',
    data_type       CHAR(1)         NOT NULL                 COMMENT '자료유형 (1:사업계획서 2:집행내역 3:지출증빙 4:정산보고서)',
    checklist_id    INT             NOT NULL                 COMMENT '적용 체크리스트 ID (FK)',
    file_nm         VARCHAR(300)    NOT NULL                 COMMENT '원본 파일명',
    file_path       VARCHAR(500)    NOT NULL                 COMMENT '로컬 저장 경로',
    file_size       BIGINT          NULL                     COMMENT '파일 크기 (byte)',
    file_ext        VARCHAR(10)     NULL                     COMMENT '파일 확장자 (pdf/hwp/xlsx/jpg)',
    ocr_yn          CHAR(1)         NOT NULL DEFAULT 'N'     COMMENT 'OCR 처리 여부 (Y/N)',
    total_item_cnt  INT             NOT NULL DEFAULT 0       COMMENT '전체 점검항목 수',
    pass_cnt        INT             NOT NULL DEFAULT 0       COMMENT '적합 항목 수',
    warn_cnt        INT             NOT NULL DEFAULT 0       COMMENT '주의 항목 수',
    fail_cnt        INT             NOT NULL DEFAULT 0       COMMENT '부적합 항목 수',
    final_result    CHAR(1)         NOT NULL DEFAULT 'W'     COMMENT '최종결과 (P:적합 W:주의 F:부적합)',
    reviewer        VARCHAR(50)     NOT NULL                 COMMENT '검토 담당자',
    review_at       DATETIME        NOT NULL DEFAULT NOW()   COMMENT '검토일시',
    remark          VARCHAR(500)    NULL                     COMMENT '비고',
    CONSTRAINT pk_review PRIMARY KEY (review_id),
    CONSTRAINT fk_review_checklist
        FOREIGN KEY (checklist_id)
        REFERENCES tb_checklist (checklist_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci
  COMMENT='검토 이력 마스터';

-- ============================================================
-- 4. 검토 결과 상세
--    항목별 점검 결과 저장
-- ============================================================
CREATE TABLE IF NOT EXISTS tb_review_detail (
    detail_id       INT             NOT NULL AUTO_INCREMENT  COMMENT '결과 상세 ID',
    review_id       INT             NOT NULL                 COMMENT '검토 ID (FK)',
    item_id         INT             NOT NULL                 COMMENT '체크리스트 항목 ID (FK)',
    item_no         INT             NOT NULL                 COMMENT '항목 순번',
    category        VARCHAR(50)     NOT NULL                 COMMENT '분류',
    item_content    TEXT            NOT NULL                 COMMENT '점검항목',
    extracted_val   TEXT            NULL                     COMMENT '문서에서 추출한 값',
    judge_result    CHAR(1)         NOT NULL                 COMMENT '판정결과 (P:적합 W:주의 F:부적합)',
    judge_reason    TEXT            NULL                     COMMENT '판정 근거',
    law_ref         VARCHAR(200)    NULL                     COMMENT '법령 출처',
    similarity      DECIMAL(5,4)    NULL                     COMMENT '유사도 점수 (0~1)',
    CONSTRAINT pk_review_detail PRIMARY KEY (detail_id),
    CONSTRAINT fk_detail_review
        FOREIGN KEY (review_id)
        REFERENCES tb_review (review_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_detail_item
        FOREIGN KEY (item_id)
        REFERENCES tb_checklist_item (item_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci
  COMMENT='검토 결과 상세';

-- ============================================================
-- 5. 중복 증빙 탐지 이력
--    지출증빙자료 중복 제출 탐지 결과
-- ============================================================
CREATE TABLE IF NOT EXISTS tb_duplicate_detect (
    detect_id       INT             NOT NULL AUTO_INCREMENT  COMMENT '탐지 ID',
    review_id       INT             NOT NULL                 COMMENT '검토 ID (FK)',
    file_nm_a       VARCHAR(300)    NOT NULL                 COMMENT '비교 파일A',
    file_nm_b       VARCHAR(300)    NOT NULL                 COMMENT '비교 파일B',
    file_hash_a     VARCHAR(64)     NOT NULL                 COMMENT '파일A SHA256 해시',
    file_hash_b     VARCHAR(64)     NOT NULL                 COMMENT '파일B SHA256 해시',
    amount_a        DECIMAL(15,0)   NULL                     COMMENT '파일A 금액',
    amount_b        DECIMAL(15,0)   NULL                     COMMENT '파일B 금액',
    detect_type     VARCHAR(50)     NOT NULL                 COMMENT '탐지유형 (HASH_MATCH:동일파일 AMOUNT_MATCH:금액일치)',
    detected_at     DATETIME        NOT NULL DEFAULT NOW()   COMMENT '탐지일시',
    CONSTRAINT pk_duplicate PRIMARY KEY (detect_id),
    CONSTRAINT fk_dup_review
        FOREIGN KEY (review_id)
        REFERENCES tb_review (review_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci
  COMMENT='중복 증빙 탐지 이력';

-- ============================================================
-- 6. 시스템 설정
--    SCR-006 설정 화면 값 저장
-- ============================================================
CREATE TABLE IF NOT EXISTS tb_system_config (
    config_key      VARCHAR(100)    NOT NULL                 COMMENT '설정 키',
    config_val      TEXT            NULL                     COMMENT '설정 값',
    config_desc     VARCHAR(200)    NULL                     COMMENT '설명',
    updated_by      VARCHAR(50)     NULL                     COMMENT '수정자',
    updated_at      DATETIME        NOT NULL DEFAULT NOW()   COMMENT '수정일시',
    CONSTRAINT pk_config PRIMARY KEY (config_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci
  COMMENT='시스템 설정';

-- ============================================================
-- 7. 접근 로그
--    감사 대응용 — 누가 언제 어떤 검토를 조회했는지
-- ============================================================
CREATE TABLE IF NOT EXISTS tb_access_log (
    log_id          BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '로그 ID',
    user_id         VARCHAR(50)     NOT NULL                 COMMENT '접속자',
    action_type     VARCHAR(50)     NOT NULL                 COMMENT '행위유형 (REVIEW_CREATE/VIEW/EXPORT 등)',
    target_id       INT             NULL                     COMMENT '대상 ID (review_id 등)',
    target_type     VARCHAR(50)     NULL                     COMMENT '대상 유형 (REVIEW/CHECKLIST 등)',
    ip_addr         VARCHAR(45)     NULL                     COMMENT '접속 IP (로컬: 127.0.0.1)',
    user_agent      VARCHAR(200)    NULL                     COMMENT '브라우저 정보',
    logged_at       DATETIME        NOT NULL DEFAULT NOW()   COMMENT '로그일시',
    CONSTRAINT pk_access_log PRIMARY KEY (log_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci
  COMMENT='접근 로그 (감사 대응)';

-- ============================================================
-- 인덱스 생성
-- ============================================================
-- 체크리스트: 자료유형별 조회
CREATE INDEX idx_checklist_type     ON tb_checklist      (data_type, use_yn);

-- 검토이력: 자주 쓰는 조회 조건
CREATE INDEX idx_review_type        ON tb_review         (data_type);
CREATE INDEX idx_review_result      ON tb_review         (final_result);
CREATE INDEX idx_review_reviewer    ON tb_review         (reviewer);
CREATE INDEX idx_review_at          ON tb_review         (review_at);

-- 검토상세: 검토ID + 판정결과
CREATE INDEX idx_detail_review      ON tb_review_detail  (review_id, judge_result);

-- 접근로그: 날짜별 감사 조회
CREATE INDEX idx_log_at             ON tb_access_log     (logged_at);
CREATE INDEX idx_log_user           ON tb_access_log     (user_id, logged_at);

-- ============================================================
-- 기초 데이터 입력 (시스템 설정 초기값)
-- ============================================================
INSERT INTO tb_system_config (config_key, config_val, config_desc, updated_by) VALUES
('GEMINI_API_KEY',    '',          'Gemini API 키 (체크리스트 생성용)',        'admin'),
('OCR_LANG',          'kor+eng',   'Tesseract OCR 언어팩',                    'admin'),
('UPLOAD_PATH',       './uploads', '업로드 파일 임시 저장 경로',               'admin'),
('AUTO_DEL_DAYS',     '7',         '업로드 파일 자동 삭제 일수 (0=삭제안함)',   'admin'),
('MAX_FILE_SIZE_MB',  '100',       '업로드 최대 파일 크기 (MB)',               'admin'),
('DB_HOST',           'localhost', 'MariaDB 호스트',                          'admin'),
('DB_NAME',           'safe_db',   'MariaDB 데이터베이스명',                  'admin'),
('DB_USER',           'safe_user', 'MariaDB 접속 계정',                       'admin');

-- ============================================================
-- 생성 결과 확인
-- ============================================================
SELECT
    TABLE_NAME      AS '테이블명',
    TABLE_COMMENT   AS '설명',
    TABLE_ROWS      AS '행수'
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = 'safe_db'
ORDER BY TABLE_NAME;

commit;