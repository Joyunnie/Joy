from datetime import datetime

from pydantic import BaseModel, Field


class ShelfLayoutCreateRequest(BaseModel):
    name: str = Field(..., max_length=50)
    location_type: str  # DISPLAY | STORAGE
    rows: int = Field(4, ge=1, le=10)
    cols: int = Field(6, ge=1, le=10)


class ShelfLayoutUpdateRequest(BaseModel):
    name: str = Field(..., max_length=50)
    rows: int = Field(..., ge=1, le=10)
    cols: int = Field(..., ge=1, le=10)


class ShelfLayoutResponse(BaseModel):
    id: int
    pharmacy_id: int
    name: str
    location_type: str
    rows: int
    cols: int
    created_at: datetime
    updated_at: datetime


class ShelfLayoutListResponse(BaseModel):
    items: list[ShelfLayoutResponse]
