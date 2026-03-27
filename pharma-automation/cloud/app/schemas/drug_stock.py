from datetime import datetime

from pydantic import BaseModel

from app.schemas.api import LowStockAlertOut


class DrugStockItemIn(BaseModel):
    drug_standard_code: str
    current_quantity: float
    is_narcotic: bool = False


class SyncDrugStockRequest(BaseModel):
    items: list[DrugStockItemIn]
    synced_at: datetime


class SyncDrugStockResponse(BaseModel):
    synced_count: int
    skipped_count: int = 0
    low_stock_alerts: list[LowStockAlertOut] = []
