from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class TodoCreate(BaseModel):
    title: str = Field(..., max_length=500)
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: int = Field(4, ge=1, le=4)


class TodoUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: Optional[int] = Field(None, ge=1, le=4)


class TodoReschedule(BaseModel):
    due_date: datetime


class TodoResponse(BaseModel):
    id: int
    pharmacy_id: int
    title: str
    description: Optional[str]
    due_date: Optional[datetime]
    priority: int
    is_completed: bool
    completed_at: Optional[datetime]
    completed_by: Optional[int]
    created_by: int
    created_at: datetime
    updated_at: datetime
    sort_order: int

    model_config = {"from_attributes": True}


class TodoListResponse(BaseModel):
    items: list[TodoResponse]
    total: int


TodoFilter = Literal["today", "upcoming", "completed", "overdue", "no_date", "all"]
