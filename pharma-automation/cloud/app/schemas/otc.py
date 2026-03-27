from datetime import datetime

from pydantic import BaseModel, Field


class OtcCreateRequest(BaseModel):
    drug_id: int
    current_quantity: int = Field(..., ge=0)
    display_location: str | None = Field(None, max_length=100)
    storage_location: str | None = Field(None, max_length=100)


class OtcUpdateRequest(BaseModel):
    """PUT은 전체 덮어쓰기. null 전송 시 해당 필드 NULL로 저장됨. 부분 수정은 지원하지 않음."""

    current_quantity: int = Field(..., ge=0)
    display_location: str | None = Field(None, max_length=100)
    storage_location: str | None = Field(None, max_length=100)
    version: int


class OtcItemResponse(BaseModel):
    id: int
    pharmacy_id: int
    drug_id: int
    drug_name: str | None = None
    current_quantity: int
    display_location: str | None = None
    storage_location: str | None = None
    last_counted_at: datetime | None = None
    version: int
    created_at: datetime
    updated_at: datetime
    is_low_stock: bool = False
    min_quantity: int | None = None


class OtcListResponse(BaseModel):
    items: list[OtcItemResponse]
    total: int


# --- Batch Location ---


class LocationAssignment(BaseModel):
    item_id: int
    row: int = Field(..., ge=0)
    col: int = Field(..., ge=0)


class BatchLocationRequest(BaseModel):
    layout_id: int
    assignments: list[LocationAssignment] = Field(..., max_length=100)


class BatchLocationRemoveRequest(BaseModel):
    layout_id: int
    item_ids: list[int] = Field(..., max_length=100)
