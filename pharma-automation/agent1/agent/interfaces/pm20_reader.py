from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date


@dataclass
class DrugDispensed:
    drug_standard_code: str
    quantity_dispensed: int


@dataclass
class InventoryItem:
    cassette_number: int
    drug_standard_code: str
    current_quantity: int


@dataclass
class VisitRecord:
    patient_hash: str
    visit_date: date
    prescription_days: int
    drugs: list[DrugDispensed] = field(default_factory=list)


class PM20Reader(ABC):
    """PM+20 MariaDB에서 데이터를 읽는 인터페이스.
    실제 구현은 PM+20 DB 스키마 확보 후 작성."""

    @abstractmethod
    def read_inventory(self) -> list[InventoryItem]:
        """현재 약품 재고 수량 조회."""

    @abstractmethod
    def read_recent_visits(self, since: date) -> list[VisitRecord]:
        """지정 날짜 이후 방문 이력 조회."""
