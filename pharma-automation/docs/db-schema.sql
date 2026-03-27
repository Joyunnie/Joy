-- ============================================================================
-- Pharmacy Inventory & Prescription Automation - Cloud PostgreSQL Schema
-- 20 Tables
-- ============================================================================
--
-- patient_hash: SHA-256, per-pharmacy salt (pharmacies.patient_hash_salt)
-- cross-pharmacy analysis not supported by design
-- prescription_inventory: mapping_source=ATDPS (카세트↔약품), quantity_source=PM20 (수량)
-- 수량 흐름: PM+20 처방→재고 차감 → ATDPS는 물리적 배출만 → PM+20이 source of truth
-- backup_logs: 실행 이력 기록용. alert_logs(BACKUP_FAIL): 실패 알림 전달용 (별개 역할)
--

-- 1. pharmacies: 약국 마스터
CREATE TABLE pharmacies (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    address VARCHAR(255),
    business_number VARCHAR(20),
    patient_hash_salt VARCHAR(64) NOT NULL,
    patient_hash_algorithm VARCHAR(20) NOT NULL DEFAULT 'SHA-256',
    api_key_hash VARCHAR(128),
    invite_code VARCHAR(20),
    default_alert_days_before SMALLINT NOT NULL DEFAULT 3,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. users: 약국 소속 사용자 (약사, 직원)
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    pharmacy_id BIGINT NOT NULL REFERENCES pharmacies(id),
    username VARCHAR(50) NOT NULL,
    password_hash VARCHAR(128) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('PHARMACIST', 'STAFF', 'ADMIN')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(pharmacy_id, username)
);

-- 3. refresh_tokens: 사용자 인증 리프레시 토큰
CREATE TABLE refresh_tokens (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(128) NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    is_revoked BOOLEAN NOT NULL DEFAULT FALSE,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. drugs: 약품 마스터 카탈로그
CREATE TABLE drugs (
    id BIGSERIAL PRIMARY KEY,
    standard_code VARCHAR(20) UNIQUE,
    name VARCHAR(200) NOT NULL,
    category VARCHAR(30) CHECK (category IN ('PRESCRIPTION', 'OTC', 'NARCOTIC')),
    manufacturer VARCHAR(100),
    unit VARCHAR(20),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. otc_inventory: OTC(일반의약품) 재고
CREATE TABLE otc_inventory (
    id BIGSERIAL PRIMARY KEY,
    pharmacy_id BIGINT NOT NULL REFERENCES pharmacies(id),
    drug_id BIGINT NOT NULL REFERENCES drugs(id),
    current_quantity INTEGER NOT NULL DEFAULT 0,
    display_location VARCHAR(100),       -- 매장 진열 위치 (e.g. "A열 3번 선반")
    storage_location VARCHAR(100),       -- 창고 내 위치 (e.g. "창고2-B선반")
    last_counted_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(pharmacy_id, drug_id)
);

-- 6. prescription_inventory: 전문의약품/ATDPS 카세트 재고 (PM+20 동기화 사본)
-- mapping_source: 카세트↔약품 매핑 출처 (ATDPS 프로그램 or 수동 설정)
-- quantity_source: 수량 출처 (PM+20 DB or 수동 입력)
-- 수량 흐름: PM+20 처방→재고 차감 → ATDPS 물리적 배출만 → PM+20이 source of truth
-- ATDPS 프로그램 수량 표시는 참고용, 동기화하지 않음
CREATE TABLE prescription_inventory (
    id BIGSERIAL PRIMARY KEY,
    pharmacy_id BIGINT NOT NULL REFERENCES pharmacies(id),
    drug_id BIGINT NOT NULL REFERENCES drugs(id),
    cassette_number SMALLINT NOT NULL,
    current_quantity INTEGER NOT NULL DEFAULT 0,
    last_refill_date TIMESTAMPTZ,
    mapping_synced_at TIMESTAMPTZ,
    quantity_synced_at TIMESTAMPTZ,
    mapping_source VARCHAR(20) NOT NULL DEFAULT 'ATDPS' CHECK (mapping_source IN ('ATDPS', 'MANUAL')),
    quantity_source VARCHAR(20) NOT NULL DEFAULT 'PM20' CHECK (quantity_source IN ('PM20', 'MANUAL')),
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(pharmacy_id, cassette_number)
);

-- 7. drug_thresholds: 약품별 최소 재고 임계값 설정
CREATE TABLE drug_thresholds (
    id BIGSERIAL PRIMARY KEY,
    pharmacy_id BIGINT NOT NULL REFERENCES pharmacies(id),
    drug_id BIGINT NOT NULL REFERENCES drugs(id),
    min_quantity INTEGER NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(pharmacy_id, drug_id)
);

-- 8. shelf_layouts: 약장/창고 레이아웃 (격자 구조)
CREATE TABLE shelf_layouts (
    id BIGSERIAL PRIMARY KEY,
    pharmacy_id BIGINT NOT NULL REFERENCES pharmacies(id),
    name VARCHAR(50) NOT NULL,
    location_type VARCHAR(10) NOT NULL CHECK (location_type IN ('DISPLAY', 'STORAGE')),
    rows INTEGER NOT NULL DEFAULT 4,
    cols INTEGER NOT NULL DEFAULT 6,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 9. drug_stock: PM+20 TEMP_STOCK 약품별 재고 (카세트가 아닌 약품 단위)
CREATE TABLE drug_stock (
    id BIGSERIAL PRIMARY KEY,
    pharmacy_id BIGINT NOT NULL REFERENCES pharmacies(id),
    drug_id BIGINT NOT NULL REFERENCES drugs(id),
    current_quantity NUMERIC(10,2) NOT NULL DEFAULT 0,
    is_narcotic BOOLEAN NOT NULL DEFAULT FALSE,
    quantity_source VARCHAR(20) NOT NULL DEFAULT 'PM20',
    synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(pharmacy_id, drug_id)
);

-- 10. patient_visit_history: 환자 방문 이력
-- source 의미:
--   PM20_SYNC: PM+20 DB에서 동기화된 방문 기록
--   DISPENSE_EVENT: ATDPS 조제 완료 이벤트로 자동 생성 (원본 데이터는 PM+20 처방)
--   OCR: 처방전 OCR로 생성
--   MANUAL: 수동 입력
-- prescription_days: 해당 방문에서의 최대 처방일수
CREATE TABLE patient_visit_history (
    id BIGSERIAL PRIMARY KEY,
    pharmacy_id BIGINT NOT NULL REFERENCES pharmacies(id),
    patient_hash VARCHAR(64) NOT NULL,
    visit_date DATE NOT NULL,
    prescription_days SMALLINT NOT NULL,
    source VARCHAR(20) NOT NULL CHECK (source IN ('PM20_SYNC', 'DISPENSE_EVENT', 'OCR', 'MANUAL')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_visit_history_pharmacy_patient ON patient_visit_history(pharmacy_id, patient_hash);
CREATE INDEX idx_visit_history_visit_date ON patient_visit_history(visit_date);

-- 9. visit_drugs: 방문-약품 연결
-- 이 테이블로 "환자가 다음에 어떤 약을 필요로 하는지" 판단 가능
-- → prescription_inventory + drug_thresholds와 조인하여 재고 부족 사전 알림
CREATE TABLE visit_drugs (
    id BIGSERIAL PRIMARY KEY,
    visit_id BIGINT NOT NULL REFERENCES patient_visit_history(id) ON DELETE CASCADE,
    drug_id BIGINT NOT NULL REFERENCES drugs(id),
    quantity_dispensed INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_visit_drugs_visit ON visit_drugs(visit_id);

-- 10. visit_predictions: 환자별 예상 내원일 + 알림 여부 (환자 단위, drug_id 없음)
-- alert_date는 서비스 레이어에서 계산:
--   COALESCE(alert_days_before, pharmacies.default_alert_days_before)
--   predicted_visit_date - 위 값 = alert_date
-- 매일 새벽 Cloud 배치에서 생성/갱신
CREATE TABLE visit_predictions (
    id BIGSERIAL PRIMARY KEY,
    pharmacy_id BIGINT NOT NULL REFERENCES pharmacies(id),
    patient_hash VARCHAR(64) NOT NULL,
    prediction_method VARCHAR(20) NOT NULL CHECK (prediction_method IN ('PRESCRIPTION_DAYS', 'PATTERN_AVG')),
    predicted_visit_date DATE NOT NULL,
    alert_days_before SMALLINT,
    alert_sent BOOLEAN NOT NULL DEFAULT FALSE,
    last_visit_id BIGINT REFERENCES patient_visit_history(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_predictions_pharmacy_patient ON visit_predictions(pharmacy_id, patient_hash);
CREATE INDEX idx_predictions_date ON visit_predictions(predicted_visit_date);

-- 11. receipt_ocr_records: 영수증 OCR 처리 기록 (입고 영수증)
CREATE TABLE receipt_ocr_records (
    id BIGSERIAL PRIMARY KEY,
    pharmacy_id BIGINT NOT NULL REFERENCES pharmacies(id),
    image_path TEXT,
    ocr_status VARCHAR(20) NOT NULL CHECK (ocr_status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')),
    raw_text TEXT,
    supplier_name VARCHAR(100),
    receipt_date DATE,
    receipt_number VARCHAR(50),
    total_amount INTEGER,
    intake_status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (intake_status IN ('PENDING', 'CONFIRMED', 'CANCELLED')),
    confirmed_at TIMESTAMPTZ,
    confirmed_by BIGINT REFERENCES users(id),
    duplicate_of BIGINT REFERENCES receipt_ocr_records(id),
    ocr_engine VARCHAR(30) DEFAULT 'GOOGLE_VISION',
    processed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 12. receipt_ocr_items: 영수증 OCR 개별 항목
CREATE TABLE receipt_ocr_items (
    id BIGSERIAL PRIMARY KEY,
    record_id BIGINT NOT NULL REFERENCES receipt_ocr_records(id) ON DELETE CASCADE,
    drug_id BIGINT REFERENCES drugs(id),
    item_name VARCHAR(200),
    quantity INTEGER,
    unit_price INTEGER,
    confidence REAL,
    match_score REAL,
    matched_drug_name VARCHAR(200),
    is_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
    confirmed_drug_id BIGINT REFERENCES drugs(id),
    confirmed_quantity INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 13. alert_logs: 알림 발송 기록
-- 알림 전달용. backup_logs와 별개 역할.
CREATE TABLE alert_logs (
    id BIGSERIAL PRIMARY KEY,
    pharmacy_id BIGINT NOT NULL REFERENCES pharmacies(id),
    alert_type VARCHAR(30) NOT NULL CHECK (alert_type IN ('LOW_STOCK', 'VISIT_APPROACHING', 'NARCOTICS_LOW', 'BACKUP_FAIL')),
    ref_table VARCHAR(50),
    ref_id BIGINT,
    message TEXT NOT NULL,
    sent_via VARCHAR(20) NOT NULL CHECK (sent_via IN ('IN_APP')),
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    read_at TIMESTAMPTZ
);

CREATE INDEX idx_alert_logs_pharmacy ON alert_logs(pharmacy_id);

-- 14. atdps_commands: ATDPS 기계 명령 큐
CREATE TABLE atdps_commands (
    id BIGSERIAL PRIMARY KEY,
    pharmacy_id BIGINT NOT NULL REFERENCES pharmacies(id),
    command_type VARCHAR(20) NOT NULL CHECK (command_type IN ('CASSETTE_SCAN', 'REFILL', 'DISPENSE', 'STATUS')),
    payload JSONB,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'SENT', 'ACK', 'FAILED', 'TIMEOUT')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at TIMESTAMPTZ,
    executed_at TIMESTAMPTZ,
    error_message TEXT
);

-- 15. prescription_ocr_records: 처방전 OCR 처리 기록
CREATE TABLE prescription_ocr_records (
    id BIGSERIAL PRIMARY KEY,
    pharmacy_id BIGINT NOT NULL REFERENCES pharmacies(id),
    image_path TEXT,
    ocr_status VARCHAR(20) NOT NULL CHECK (ocr_status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'CONFIRMED', 'FAILED', 'CANCELLED')),
    raw_text TEXT,
    patient_hash VARCHAR(64),
    visit_id BIGINT REFERENCES patient_visit_history(id),
    patient_name VARCHAR(100),
    patient_dob VARCHAR(20),
    insurance_type VARCHAR(30),
    prescriber_name VARCHAR(100),
    prescriber_clinic VARCHAR(200),
    prescription_date DATE,
    prescription_number VARCHAR(50),
    ocr_engine VARCHAR(30) DEFAULT 'GOOGLE_VISION',
    confirmed_at TIMESTAMPTZ,
    confirmed_by BIGINT REFERENCES users(id),
    duplicate_of BIGINT REFERENCES prescription_ocr_records(id),
    processed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 16. prescription_ocr_drugs: 처방전 OCR 개별 약품
CREATE TABLE prescription_ocr_drugs (
    id BIGSERIAL PRIMARY KEY,
    record_id BIGINT NOT NULL REFERENCES prescription_ocr_records(id) ON DELETE CASCADE,
    drug_id BIGINT REFERENCES drugs(id),
    drug_name_raw VARCHAR(200),
    dosage VARCHAR(50),
    frequency VARCHAR(50),
    days INTEGER,
    total_quantity NUMERIC(10,2),
    confidence REAL,
    match_score REAL,
    matched_drug_name VARCHAR(200),
    is_narcotic BOOLEAN DEFAULT FALSE,
    is_confirmed BOOLEAN DEFAULT FALSE,
    confirmed_drug_id BIGINT REFERENCES drugs(id),
    confirmed_dosage VARCHAR(50),
    confirmed_frequency VARCHAR(50),
    confirmed_days INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 17. narcotics_inventory: 마약류 현재 재고 (마약류관리법 실사 대응)
-- 법적으로 현재 재고 현황과 입출고 이력을 독립적으로 보관/제출해야 함
CREATE TABLE narcotics_inventory (
    id BIGSERIAL PRIMARY KEY,
    pharmacy_id BIGINT NOT NULL REFERENCES pharmacies(id),
    drug_id BIGINT NOT NULL REFERENCES drugs(id),
    lot_number VARCHAR(50) NOT NULL,
    current_quantity INTEGER NOT NULL DEFAULT 0,
    last_inspected_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(pharmacy_id, drug_id, lot_number)
);

-- 18. narcotics_transactions: 마약류 입출고 이력 (감사 추적, 법적 보관 의무)
CREATE TABLE narcotics_transactions (
    id BIGSERIAL PRIMARY KEY,
    pharmacy_id BIGINT NOT NULL REFERENCES pharmacies(id),
    narcotics_inventory_id BIGINT NOT NULL REFERENCES narcotics_inventory(id),
    transaction_type VARCHAR(20) NOT NULL CHECK (transaction_type IN ('RECEIVE', 'DISPENSE', 'DISPOSE', 'ADJUST', 'RETURN')),
    quantity INTEGER NOT NULL,
    remaining_quantity INTEGER NOT NULL,
    patient_hash VARCHAR(64),
    prescription_number VARCHAR(50),
    performed_by BIGINT REFERENCES users(id),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_narcotics_tx_inventory ON narcotics_transactions(narcotics_inventory_id);

-- 19. inventory_audit_log: 재고 변경 감사 로그
CREATE TABLE inventory_audit_log (
    id BIGSERIAL PRIMARY KEY,
    pharmacy_id BIGINT NOT NULL REFERENCES pharmacies(id),
    table_name VARCHAR(50) NOT NULL,
    record_id BIGINT NOT NULL,
    action VARCHAR(20) NOT NULL CHECK (action IN ('INSERT', 'UPDATE', 'DELETE', 'OTC_DELETE', 'NARCOTICS_DEACTIVATE')),
    old_values JSONB,
    new_values JSONB,
    performed_by BIGINT REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_log_pharmacy ON inventory_audit_log(pharmacy_id);
CREATE INDEX idx_audit_log_table ON inventory_audit_log(table_name, record_id);

-- 20. backup_logs: 백업 실행 이력
-- 실행 이력용. 실패 시 alert_logs에 BACKUP_FAIL 알림도 별도 생성.
CREATE TABLE backup_logs (
    id BIGSERIAL PRIMARY KEY,
    pharmacy_id BIGINT NOT NULL REFERENCES pharmacies(id),
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED', 'ABORTED')),
    backup_path TEXT,
    file_count INTEGER,
    total_bytes BIGINT,
    error_message TEXT,
    reported_at TIMESTAMPTZ
);

CREATE INDEX idx_backup_logs_pharmacy ON backup_logs(pharmacy_id);
