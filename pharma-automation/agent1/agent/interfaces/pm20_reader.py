from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date


@dataclass
class DrugDispensed:
    drug_insurance_code: str  # 건강보험 약품코드 (TBSID040_04.DRUG_CODE)
    quantity_dispensed: int


@dataclass
class InventoryItem:
    """ATDPS 카세트 기반 재고. Phase 4B에서 사용."""
    cassette_number: int
    drug_standard_code: str
    current_quantity: int


@dataclass
class DrugStockItem:
    """PM+20 TEMP_STOCK 약품별 재고 (카세트가 아닌 약품 단위)."""
    drug_standard_code: str   # DA_Goods.Goods_RegNo
    drug_name: str            # DA_Goods.Goods_Name
    current_quantity: float   # TEMP_STOCK.MDCN_MQTY (decimal, 음수 가능)
    is_narcotic: bool         # CD_MINDRUG 존재 여부


@dataclass
class DrugMasterItem:
    """PM+20 DA_Goods 약품 마스터."""
    standard_code: str        # DA_Goods.Goods_RegNo
    name: str                 # DA_Goods.Goods_Name
    manufacturer: str | None  # DA_Goods.Goods_Company
    # TODO: Goods_Gubun 값 확인 후 OTC 카테고리 매핑 추가
    category: str             # PRESCRIPTION | NARCOTIC (OTC 구분 현재 불가)
    insurance_code: str | None = None  # 건강보험 약품코드 (TBSIM040_01.DRUG_CODE via TEMP_STOCK)


@dataclass
class VisitRecord:
    patient_hash: str
    visit_date: date
    prescription_days: int
    drugs: list[DrugDispensed] = field(default_factory=list)
    proc_dtime: str = ""  # TBSID040_03.PROC_DTIME — incremental sync marker


class PM20Reader(ABC):
    r"""PM+20 DB에서 데이터를 읽는 인터페이스.
    SQL Server (.\PMPLUS20, PM_MAIN) 접속."""

    @abstractmethod
    def read_inventory(self) -> list[InventoryItem]:
        """ATDPS 카세트 기반 재고 조회. ATDPS 미연동 시 빈 리스트 반환."""

    @abstractmethod
    def read_drug_stock(self) -> list[DrugStockItem]:
        """TEMP_STOCK + DA_Goods JOIN: 약품별 현재 재고 수량 조회."""

    @abstractmethod
    def read_drug_master(self) -> list[DrugMasterItem]:
        """DA_Goods: 약품 마스터 전체 조회."""

    @abstractmethod
    def read_recent_visits(self, since_marker: str | None = None) -> list[VisitRecord]:
        """TBSID040_03 + TBSID040_04: 조제완료 방문 이력 조회.

        Args:
            since_marker: PROC_DTIME 기반 증분 동기화 마커 (예: '20260101000000').
                          None이면 초기 백필 시작점 사용.

        Returns:
            VisitRecord 리스트. 각 레코드의 proc_dtime 중 최대값을 다음 호출의 마커로 사용.
        """
