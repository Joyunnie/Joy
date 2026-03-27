from datetime import datetime

from pydantic import BaseModel


class RpaCommandCreateRequest(BaseModel):
    command_type: str  # NARCOTICS_INPUT | PRESCRIPTION_INPUT
    payload: dict


class RpaCommandStatusUpdate(BaseModel):
    status: str  # EXECUTING | SUCCESS | FAILED | SKIPPED
    error_message: str | None = None


class RpaCommandOut(BaseModel):
    id: int
    pharmacy_id: int
    command_type: str
    payload: dict
    status: str
    created_at: datetime
    sent_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    retry_count: int


class RpaCommandListResponse(BaseModel):
    items: list[RpaCommandOut]
    total: int


class RpaPendingResponse(BaseModel):
    commands: list[RpaCommandOut]
