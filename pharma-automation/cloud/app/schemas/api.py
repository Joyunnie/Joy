from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator


# === Sync: Inventory ===

class InventoryItemIn(BaseModel):
    cassette_number: int
    drug_standard_code: str | None = None
    current_quantity: int
    quantity_source: str = "PM20"


class SyncInventoryRequest(BaseModel):
    items: list[InventoryItemIn]
    synced_at: datetime


class LowStockAlertOut(BaseModel):
    drug_name: str
    current_quantity: int
    min_quantity: int


class SyncInventoryResponse(BaseModel):
    synced_count: int
    low_stock_alerts: list[LowStockAlertOut] = []


# === Sync: Cassette Mapping ===

class CassetteMappingIn(BaseModel):
    cassette_number: int
    drug_standard_code: str
    mapping_source: str = "ATDPS"


class SyncCassetteMappingRequest(BaseModel):
    mappings: list[CassetteMappingIn]
    synced_at: datetime


class SyncCassetteMappingResponse(BaseModel):
    synced_count: int
    new_mappings: int
    updated_mappings: int


# === Sync: Visits ===

class VisitDrugIn(BaseModel):
    drug_insurance_code: str | None = None  # 건강보험 약품코드 (TBSID040_04.DRUG_CODE)
    drug_standard_code: str | None = None   # TBSIM040_01.TITLECODE (barcode, optional)
    quantity_dispensed: int

    @model_validator(mode="after")
    def require_at_least_one_code(self):
        if not self.drug_insurance_code and not self.drug_standard_code:
            raise ValueError("At least one of drug_insurance_code or drug_standard_code is required")
        return self


class VisitIn(BaseModel):
    patient_hash: str
    visit_date: date
    prescription_days: int
    source: str = "PM20_SYNC"
    drugs: list[VisitDrugIn] = []


class SyncVisitsRequest(BaseModel):
    visits: list[VisitIn]


class SkippedDrugOut(BaseModel):
    drug_code: str  # insurance_code or standard_code — whichever was sent
    reason: str


class SyncVisitsResponse(BaseModel):
    synced_count: int
    visit_ids: list[int]
    skipped_drugs: list[SkippedDrugOut] = []


# === Alerts ===

class AlertOut(BaseModel):
    id: int
    alert_type: str
    message: str
    sent_at: datetime
    read_at: datetime | None = None


class AlertListResponse(BaseModel):
    alerts: list[AlertOut]
    total: int


class AlertReadResponse(BaseModel):
    id: int
    read_at: datetime


# === Inventory Status ===

class InventoryStatusItem(BaseModel):
    cassette_number: int
    drug_name: str | None = None
    current_quantity: int
    min_quantity: int | None = None
    is_low_stock: bool
    quantity_synced_at: datetime | None = None


class InventoryStatusResponse(BaseModel):
    items: list[InventoryStatusItem]


# === Predictions ===

class NeededDrugOut(BaseModel):
    drug_name: str
    quantity: int
    in_stock: int | None = None


class PredictionOut(BaseModel):
    id: int
    patient_hash: str
    predicted_visit_date: date
    alert_date: date
    alert_sent: bool
    prediction_method: str
    based_on_visit_date: date | None = None
    is_overdue: bool
    needed_drugs: list[NeededDrugOut] = []


class PredictionListResponse(BaseModel):
    predictions: list[PredictionOut]
