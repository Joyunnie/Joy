from datetime import datetime

from pydantic import BaseModel, Field


# --- Requests ---


class NarcoticsCreateRequest(BaseModel):
    drug_id: int
    lot_number: str = Field(..., max_length=50)
    quantity: int = Field(..., gt=0)
    notes: str | None = Field(None, max_length=2000)


class NarcoticsUpdateRequest(BaseModel):
    """실사조정 (ADJUST). quantity 변동 시 자동으로 ADJUST 트랜잭션 생성."""

    current_quantity: int = Field(..., ge=0)
    last_inspected_at: datetime | None = None
    notes: str | None = Field(None, max_length=2000)
    version: int


class NarcoticsDeleteRequest(BaseModel):
    """폐기 처리. notes 필수."""

    notes: str = Field(..., min_length=1)
    version: int


class NarcoticsDispenseRequest(BaseModel):
    quantity: int = Field(..., gt=0)
    # PM+20에서 마약류통합관리시스템 법적 보고 처리. 여기선 내부 참조용.
    patient_hash: str | None = Field(None, max_length=64)
    prescription_number: str | None = Field(None, max_length=50)
    notes: str | None = Field(None, max_length=2000)
    version: int


class NarcoticsReturnRequest(BaseModel):
    """도매상에 반품 (재고 감소)."""

    quantity: int = Field(..., gt=0)
    notes: str = Field(..., min_length=1)
    version: int


# --- Responses ---


class NarcoticsItemResponse(BaseModel):
    id: int
    pharmacy_id: int
    drug_id: int
    drug_name: str | None = None
    lot_number: str
    current_quantity: int
    is_active: bool
    last_inspected_at: datetime | None = None
    version: int
    created_at: datetime
    updated_at: datetime
    is_low_stock: bool = False
    min_quantity: int | None = None


class NarcoticsListResponse(BaseModel):
    items: list[NarcoticsItemResponse]
    total: int


class NarcoticsTransactionOut(BaseModel):
    id: int
    transaction_type: str
    quantity: int
    remaining_quantity: int
    patient_hash: str | None = None
    prescription_number: str | None = None
    performed_by: int | None = None
    notes: str | None = None
    created_at: datetime


class NarcoticsTransactionListResponse(BaseModel):
    transactions: list[NarcoticsTransactionOut]
    total: int
