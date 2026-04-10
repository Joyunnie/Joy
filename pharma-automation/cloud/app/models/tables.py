from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB

TIMESTAMPTZ = TIMESTAMP(timezone=True)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# 1. pharmacies
class Pharmacy(Base):
    __tablename__ = "pharmacies"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    address: Mapped[str | None] = mapped_column(String(255))
    business_number: Mapped[str | None] = mapped_column(String(20))
    patient_hash_salt: Mapped[str] = mapped_column(String(64))
    patient_hash_algorithm: Mapped[str] = mapped_column(String(20), default="SHA-256")
    api_key_hash: Mapped[str | None] = mapped_column(String(128))
    invite_code: Mapped[str | None] = mapped_column(String(20))
    default_alert_days_before: Mapped[int] = mapped_column(SmallInteger, default=3)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default="now()")


# 2. users
class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("pharmacy_id", "username"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    pharmacy_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pharmacies.id"))
    username: Mapped[str] = mapped_column(String(50))
    password_hash: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(20))  # PHARMACIST | STAFF | ADMIN
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default="now()")


# 3. refresh_tokens
class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    revoked_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default="now()")


# 4. drugs
class Drug(Base):
    __tablename__ = "drugs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    standard_code: Mapped[str | None] = mapped_column(String(20))
    insurance_code: Mapped[str | None] = mapped_column(
        String(20), unique=True, comment="건강보험 약품코드 (TBSIM040_01.DRUG_CODE)"
    )
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str | None] = mapped_column(String(30))  # PRESCRIPTION | OTC | NARCOTIC
    manufacturer: Mapped[str | None] = mapped_column(String(100))
    unit: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default="now()")


# 5. otc_inventory
class OtcInventory(Base):
    __tablename__ = "otc_inventory"
    __table_args__ = (UniqueConstraint("pharmacy_id", "drug_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    pharmacy_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pharmacies.id"))
    drug_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("drugs.id"))
    current_quantity: Mapped[int] = mapped_column(Integer, default=0)
    display_location: Mapped[str | None] = mapped_column(String(100))
    storage_location: Mapped[str | None] = mapped_column(String(100))
    last_counted_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default="now()")


# 6. prescription_inventory
class PrescriptionInventory(Base):
    __tablename__ = "prescription_inventory"
    __table_args__ = (
        UniqueConstraint("pharmacy_id", "cassette_number"),
        Index("idx_prescription_inventory_insurance_code", "drug_insurance_code"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    pharmacy_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pharmacies.id"))
    drug_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("drugs.id"))
    drug_insurance_code: Mapped[str | None] = mapped_column(String(20), comment="건강보험 약품코드")
    drug_name: Mapped[str | None] = mapped_column(String(200))
    cassette_number: Mapped[int] = mapped_column(SmallInteger)
    current_quantity: Mapped[int] = mapped_column(Integer, default=0)
    drug_type: Mapped[str | None] = mapped_column(String(50))
    dispensing_mode: Mapped[str | None] = mapped_column(String(20), comment="순차 or 동시")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    last_refill_date: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)
    mapping_synced_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)
    quantity_synced_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)
    mapping_source: Mapped[str] = mapped_column(String(20), default="ATDPS")
    quantity_source: Mapped[str] = mapped_column(String(20), default="PM20")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default="now()")


# 7. drug_thresholds
class DrugThreshold(Base):
    __tablename__ = "drug_thresholds"
    __table_args__ = (UniqueConstraint("pharmacy_id", "drug_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    pharmacy_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pharmacies.id"))
    drug_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("drugs.id"))
    min_quantity: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default="now()")


# 8. shelf_layouts
class ShelfLayout(Base):
    __tablename__ = "shelf_layouts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    pharmacy_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pharmacies.id"))
    name: Mapped[str] = mapped_column(String(50))
    location_type: Mapped[str] = mapped_column(String(10))  # DISPLAY | STORAGE
    position: Mapped[str] = mapped_column(String(10), default="front")  # front | left | right
    rows: Mapped[int] = mapped_column(Integer, default=4)
    cols: Mapped[int] = mapped_column(Integer, default=6)
    cell_drugs: Mapped[dict | None] = mapped_column(JSONB, default=dict)  # {"row,col": ["drug1", "drug2", ...]}
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default="now()")


# 9. drug_stock
class DrugStock(Base):
    __tablename__ = "drug_stock"
    __table_args__ = (UniqueConstraint("pharmacy_id", "drug_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    pharmacy_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pharmacies.id"))
    drug_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("drugs.id"))
    current_quantity: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    is_narcotic: Mapped[bool] = mapped_column(Boolean, default=False)
    quantity_source: Mapped[str] = mapped_column(String(20), default="PM20")
    synced_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default="now()")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default="now()")


# 10. patient_visit_history
class PatientVisitHistory(Base):
    __tablename__ = "patient_visit_history"
    __table_args__ = (
        Index("idx_visit_history_pharmacy_patient", "pharmacy_id", "patient_hash"),
        Index("idx_visit_history_visit_date", "visit_date"),
        Index("idx_visit_history_pharmacy_date", "pharmacy_id", "visit_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    pharmacy_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pharmacies.id"))
    patient_hash: Mapped[str] = mapped_column(String(64))
    visit_date: Mapped[date] = mapped_column(Date)
    prescription_days: Mapped[int] = mapped_column(SmallInteger)
    source: Mapped[str] = mapped_column(String(20))  # PM20_SYNC | DISPENSE_EVENT | OCR | MANUAL
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default="now()")


# 11. visit_drugs
class VisitDrug(Base):
    __tablename__ = "visit_drugs"
    __table_args__ = (
        Index("idx_visit_drugs_visit", "visit_id"),
        Index("idx_visit_drugs_drug_id", "drug_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    visit_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("patient_visit_history.id", ondelete="CASCADE"))
    drug_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("drugs.id"))
    quantity_dispensed: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default="now()")


# 12. visit_predictions
class VisitPrediction(Base):
    __tablename__ = "visit_predictions"
    __table_args__ = (
        Index("idx_predictions_pharmacy_patient", "pharmacy_id", "patient_hash"),
        Index("idx_predictions_date", "predicted_visit_date"),
        Index("idx_predictions_pharmacy_date", "pharmacy_id", "predicted_visit_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    pharmacy_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pharmacies.id"))
    patient_hash: Mapped[str] = mapped_column(String(64))
    prediction_method: Mapped[str] = mapped_column(String(20))  # PRESCRIPTION_DAYS | PATTERN_AVG
    predicted_visit_date: Mapped[date] = mapped_column(Date)
    alert_days_before: Mapped[int | None] = mapped_column(SmallInteger)
    alert_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    last_visit_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("patient_visit_history.id"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default="now()")


# 13. receipt_ocr_records
class ReceiptOcrRecord(Base):
    __tablename__ = "receipt_ocr_records"
    __table_args__ = (
        Index("idx_receipt_ocr_pharmacy_created", "pharmacy_id", "created_at"),
        Index("idx_receipt_ocr_pharmacy_receipt_num", "pharmacy_id", "receipt_number"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    pharmacy_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pharmacies.id"))
    image_path: Mapped[str | None] = mapped_column(Text)
    ocr_status: Mapped[str] = mapped_column(String(20))  # PENDING | PROCESSING | COMPLETED | FAILED
    raw_text: Mapped[str | None] = mapped_column(Text)
    supplier_name: Mapped[str | None] = mapped_column(String(100))
    receipt_date: Mapped[date | None] = mapped_column(Date)
    receipt_number: Mapped[str | None] = mapped_column(String(50))
    total_amount: Mapped[int | None] = mapped_column(Integer)
    intake_status: Mapped[str] = mapped_column(String(20), default="PENDING")  # PENDING | CONFIRMED | CANCELLED
    confirmed_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)
    confirmed_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    duplicate_of: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("receipt_ocr_records.id"))
    ocr_engine: Mapped[str | None] = mapped_column(String(30), default="GOOGLE_VISION")
    processed_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default="now()")


# 14. receipt_ocr_items
class ReceiptOcrItem(Base):
    __tablename__ = "receipt_ocr_items"
    __table_args__ = (
        Index("idx_receipt_ocr_items_record", "record_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    record_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("receipt_ocr_records.id", ondelete="CASCADE"))
    drug_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("drugs.id"))
    item_name: Mapped[str | None] = mapped_column(String(200))
    quantity: Mapped[int | None] = mapped_column(Integer)
    unit_price: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[float | None] = mapped_column(Float)
    match_score: Mapped[float | None] = mapped_column(Float)
    matched_drug_name: Mapped[str | None] = mapped_column(String(200))
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmed_drug_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("drugs.id"))
    confirmed_quantity: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default="now()")


# 15. alert_logs
class AlertLog(Base):
    __tablename__ = "alert_logs"
    __table_args__ = (
        Index("idx_alert_logs_pharmacy", "pharmacy_id"),
        Index("idx_alert_logs_pharmacy_sent", "pharmacy_id", "sent_at"),
        Index(
            "idx_alert_dedup",
            "pharmacy_id", "alert_type", "ref_table", "ref_id", "sent_at",
            postgresql_where="read_at IS NULL",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    pharmacy_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pharmacies.id"))
    alert_type: Mapped[str] = mapped_column(String(30))  # LOW_STOCK | VISIT_APPROACHING | NARCOTICS_LOW | BACKUP_FAIL
    ref_table: Mapped[str | None] = mapped_column(String(50))
    ref_id: Mapped[int | None] = mapped_column(BigInteger)
    message: Mapped[str] = mapped_column(Text)
    sent_via: Mapped[str] = mapped_column(String(20), default="IN_APP")
    sent_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default="now()")
    read_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)


# 16. narcotics_inventory
class NarcoticsInventory(Base):
    __tablename__ = "narcotics_inventory"
    __table_args__ = (UniqueConstraint("pharmacy_id", "drug_id", "lot_number"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    pharmacy_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pharmacies.id"))
    drug_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("drugs.id"))
    lot_number: Mapped[str] = mapped_column(String(50))
    current_quantity: Mapped[int] = mapped_column(Integer, default=0)
    last_inspected_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default="now()")


# 17. narcotics_transactions
class NarcoticsTransaction(Base):
    __tablename__ = "narcotics_transactions"
    __table_args__ = (
        Index("idx_narcotics_tx_inventory", "narcotics_inventory_id"),
        Index("idx_narcotics_tx_pharmacy", "pharmacy_id", "narcotics_inventory_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    pharmacy_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pharmacies.id"))
    narcotics_inventory_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("narcotics_inventory.id"))
    transaction_type: Mapped[str] = mapped_column(String(20))  # RECEIVE | DISPENSE | DISPOSE | ADJUST | RETURN
    quantity: Mapped[int] = mapped_column(Integer)
    remaining_quantity: Mapped[int] = mapped_column(Integer)
    patient_hash: Mapped[str | None] = mapped_column(String(64))
    prescription_number: Mapped[str | None] = mapped_column(String(50))
    performed_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default="now()")


# 18. inventory_audit_log
class InventoryAuditLog(Base):
    __tablename__ = "inventory_audit_log"
    __table_args__ = (
        Index("idx_audit_log_pharmacy", "pharmacy_id"),
        Index("idx_audit_log_table", "table_name", "record_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    pharmacy_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pharmacies.id"))
    table_name: Mapped[str] = mapped_column(String(50))
    record_id: Mapped[int] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(20))  # INSERT | UPDATE | DELETE | OTC_DELETE | NARCOTICS_DEACTIVATE
    old_values: Mapped[dict | None] = mapped_column(JSONB)
    new_values: Mapped[dict | None] = mapped_column(JSONB)
    performed_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default="now()")


# 19. backup_logs
class BackupLog(Base):
    __tablename__ = "backup_logs"
    __table_args__ = (
        Index("idx_backup_logs_pharmacy", "pharmacy_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    pharmacy_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pharmacies.id"))
    started_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ)
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)
    status: Mapped[str] = mapped_column(String(20))  # RUNNING | SUCCESS | FAILED | ABORTED
    backup_path: Mapped[str | None] = mapped_column(Text)
    file_count: Mapped[int | None] = mapped_column(Integer)
    total_bytes: Mapped[int | None] = mapped_column(BigInteger)
    error_message: Mapped[str | None] = mapped_column(Text)
    reported_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)


# 20. todos
class Todo(Base):
    __tablename__ = "todos"
    __table_args__ = (
        CheckConstraint("priority BETWEEN 1 AND 4", name="ck_todos_priority"),
        Index(
            "idx_todos_pharmacy_due",
            "pharmacy_id",
            "due_date",
            postgresql_where="NOT is_completed",
        ),
        Index(
            "idx_todos_pharmacy_completed",
            "pharmacy_id",
            "is_completed",
            "completed_at",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    pharmacy_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pharmacies.id"))
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    due_date: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)
    priority: Mapped[int] = mapped_column(SmallInteger, default=4)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)
    completed_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default="now()")
