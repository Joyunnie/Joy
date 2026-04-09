from datetime import datetime

from pydantic import BaseModel

from app.schemas.api import LowStockAlertOut


class DrugStockItemIn(BaseModel):
    drug_insurance_code: str | None = None  # 건강보험 약품코드 (primary)
    drug_standard_code: str | None = None   # DA_Goods.Goods_RegNo (legacy fallback)
    current_quantity: float


class SyncDrugStockRequest(BaseModel):
    items: list[DrugStockItemIn]
    synced_at: datetime


class SyncDrugStockResponse(BaseModel):
    synced_count: int
    skipped_count: int = 0
    low_stock_alerts: list[LowStockAlertOut] = []
