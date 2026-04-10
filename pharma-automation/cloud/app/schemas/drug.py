from pydantic import BaseModel


class DrugOut(BaseModel):
    id: int
    standard_code: str | None = None
    name: str
    category: str


class DrugListResponse(BaseModel):
    items: list[DrugOut]
    total: int
