from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class CassetteMapping:
    cassette_number: int
    drug_standard_code: str


class ATDPSReader(ABC):
    """ATDPS 프로그램에서 카세트↔약품 매핑을 읽는 인터페이스.
    실제 구현은 ATDPS 파일 형식 확보 후 작성."""

    @abstractmethod
    def read_cassette_mappings(self) -> list[CassetteMapping]:
        """현재 카세트↔약품 매핑 전체 조회."""

    @abstractmethod
    def is_available(self) -> bool:
        """ATDPS 프로그램 접근 가능 여부 확인."""
