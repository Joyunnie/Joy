from datetime import datetime

from pydantic import BaseModel, Field


class ThresholdCreateRequest(BaseModel):
    drug_id: int
    min_quantity: int = Field(..., ge=1)


class ThresholdUpdateRequest(BaseModel):
    """PUT은 전체 덮어쓰기. min_quantity + is_active 모두 필수."""

    min_quantity: int = Field(..., ge=1)
    is_active: bool


class ThresholdItemResponse(BaseModel):
    id: int
    pharmacy_id: int
    drug_id: int
    drug_name: str | None = None
    drug_category: str | None = None
    min_quantity: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ThresholdListResponse(BaseModel):
    items: list[ThresholdItemResponse]
    total: int
