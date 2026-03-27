from datetime import date, datetime

from pydantic import BaseModel, Field


# --- Request schemas ---


class ReceiptItemUpdateRequest(BaseModel):
    drug_id: int | None = None
    quantity: int | None = None


class ReceiptListParams(BaseModel):
    status: str | None = None  # PENDING | CONFIRMED | CANCELLED
    date_from: date | None = None
    date_to: date | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


# --- Response schemas ---


class ReceiptOcrItemOut(BaseModel):
    id: int
    record_id: int
    drug_id: int | None
    item_name: str | None
    quantity: int | None
    unit_price: int | None
    confidence: float | None
    match_score: float | None
    matched_drug_name: str | None
    is_confirmed: bool
    confirmed_drug_id: int | None
    confirmed_quantity: int | None

    model_config = {"from_attributes": True}


class ReceiptOcrRecordOut(BaseModel):
    id: int
    pharmacy_id: int
    image_path: str | None
    ocr_status: str
    supplier_name: str | None
    receipt_date: date | None
    receipt_number: str | None
    total_amount: int | None
    intake_status: str
    confirmed_at: datetime | None
    duplicate_of: int | None
    ocr_engine: str | None
    processed_at: datetime | None
    created_at: datetime
    item_count: int = 0

    model_config = {"from_attributes": True}


class ReceiptOcrResponse(BaseModel):
    """업로드 후 반환되는 전체 OCR 결과."""
    record: ReceiptOcrRecordOut
    items: list[ReceiptOcrItemOut]
    duplicate_warning: str | None = None


class ReceiptOcrDetailResponse(BaseModel):
    """상세 조회 응답."""
    record: ReceiptOcrRecordOut
    items: list[ReceiptOcrItemOut]
    raw_text: str | None = None


class ReceiptListResponse(BaseModel):
    items: list[ReceiptOcrRecordOut]
    total: int


class ConfirmResponse(BaseModel):
    confirmed_count: int
    updated_stocks: list[dict]
