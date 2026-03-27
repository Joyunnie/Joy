from datetime import date, datetime

from pydantic import BaseModel, Field


# --- Request schemas ---


class PrescriptionDrugUpdateRequest(BaseModel):
    drug_id: int | None = None
    dosage: str | None = None
    frequency: str | None = None
    days: int | None = None


class PrescriptionListParams(BaseModel):
    status: str | None = None  # PENDING | COMPLETED | CONFIRMED | CANCELLED
    date_from: date | None = None
    date_to: date | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


# --- Response schemas ---


class PrescriptionOcrDrugOut(BaseModel):
    id: int
    record_id: int
    drug_id: int | None
    drug_name_raw: str | None
    dosage: str | None
    frequency: str | None
    days: int | None
    total_quantity: float | None
    confidence: float | None
    match_score: float | None
    matched_drug_name: str | None
    is_narcotic: bool
    is_confirmed: bool
    confirmed_drug_id: int | None
    confirmed_dosage: str | None
    confirmed_frequency: str | None
    confirmed_days: int | None

    model_config = {"from_attributes": True}


class PrescriptionOcrRecordOut(BaseModel):
    id: int
    pharmacy_id: int
    image_path: str | None
    ocr_status: str
    patient_name: str | None
    patient_dob: str | None
    insurance_type: str | None
    prescriber_name: str | None
    prescriber_clinic: str | None
    prescription_date: date | None
    prescription_number: str | None
    ocr_engine: str | None
    confirmed_at: datetime | None
    duplicate_of: int | None
    processed_at: datetime | None
    created_at: datetime
    drug_count: int = 0

    model_config = {"from_attributes": True}


class PrescriptionOcrResponse(BaseModel):
    """업로드 후 반환되는 전체 OCR 결과."""
    record: PrescriptionOcrRecordOut
    drugs: list[PrescriptionOcrDrugOut]
    duplicate_warning: str | None = None


class PrescriptionOcrDetailResponse(BaseModel):
    """상세 조회 응답."""
    record: PrescriptionOcrRecordOut
    drugs: list[PrescriptionOcrDrugOut]
    raw_text: str | None = None


class PrescriptionListResponse(BaseModel):
    items: list[PrescriptionOcrRecordOut]
    total: int


class PrescriptionConfirmResponse(BaseModel):
    confirmed_count: int
