from pydantic import BaseModel, Field


class DrugMasterIn(BaseModel):
    standard_code: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=200)
    manufacturer: str | None = None
    category: str = Field(default="PRESCRIPTION", pattern=r"^(PRESCRIPTION|OTC|NARCOTIC)$")


class SyncDrugsRequest(BaseModel):
    drugs: list[DrugMasterIn]


class SyncDrugsResponse(BaseModel):
    synced_count: int
    new_count: int
    updated_count: int
