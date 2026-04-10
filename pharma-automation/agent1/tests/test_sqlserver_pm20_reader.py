from __future__ import annotations

"""SqlServerPM20Reader 단위 테스트 — pymssql mock 사용."""

import hashlib
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from agent1.agent.interfaces.pm20_reader import (
    DrugMasterItem,
    VisitRecord,
)
from agent1.agent.readers.sqlserver_pm20_reader import SqlServerPM20Reader


@pytest.fixture
def reader(mock_config):
    """Mock pymssql 연결을 사용하는 SqlServerPM20Reader."""
    with patch("agent1.agent.readers.sqlserver_pm20_reader.pymssql") as mock_pymssql:
        mock_conn = MagicMock()
        mock_pymssql.connect.return_value = mock_conn
        r = SqlServerPM20Reader(mock_config)
        r._conn = mock_conn
        yield r, mock_conn


class TestReadDrugMaster:
    def test_all_have_insurance_code(self, reader):
        """All returned items have insurance_code set (TBSIM040_01 source)."""
        r, mock_conn = reader
        cursor = MagicMock()
        mock_conn.cursor.return_value = cursor
        cursor.fetchall.return_value = [
            {"insurance_code": "643507086", "name": "아모시실린",
             "manufacturer": "제약사A", "standard_code": "8806717024900", "category": "PRESCRIPTION"},
            {"insurance_code": "671806320", "name": "펜타닐패치",
             "manufacturer": None, "standard_code": "8800735008105", "category": "NARCOTIC"},
        ]

        result = r.read_drug_master()
        assert len(result) == 2
        assert all(item.insurance_code for item in result)
        assert result[0].insurance_code == "643507086"
        assert result[0].name == "아모시실린"
        assert result[0].manufacturer == "제약사A"
        assert result[0].standard_code == "8806717024900"
        assert result[1].insurance_code == "671806320"
        assert result[1].category == "NARCOTIC"

    def test_null_titlecode(self, reader):
        """TITLECODE가 NULL인 약품 → standard_code is None."""
        r, mock_conn = reader
        cursor = MagicMock()
        mock_conn.cursor.return_value = cursor
        cursor.fetchall.return_value = [
            {"insurance_code": "643507086", "name": "아모시실린",
             "manufacturer": None, "standard_code": None, "category": "PRESCRIPTION"},
        ]

        result = r.read_drug_master()
        assert len(result) == 1
        assert result[0].standard_code is None
        assert result[0].insurance_code == "643507086"

    def test_deduplication(self, reader):
        """TBSIM040_01에 동일 DRUG_CODE 중복 행 → 첫 번째만 사용."""
        r, mock_conn = reader
        cursor = MagicMock()
        mock_conn.cursor.return_value = cursor
        cursor.fetchall.return_value = [
            {"insurance_code": "643507086", "name": "아모시실린캡슐250mg",
             "manufacturer": "제약사A", "standard_code": "8806717024900", "category": "PRESCRIPTION"},
            {"insurance_code": "643507086", "name": "아모시실린캡슐250mg",
             "manufacturer": "제약사A", "standard_code": "8806717024901", "category": "PRESCRIPTION"},
        ]

        result = r.read_drug_master()
        assert len(result) == 1
        assert result[0].insurance_code == "643507086"

    def test_narcotic_classification(self, reader):
        """CD_MINDRUG JOIN 결과 category='NARCOTIC'."""
        r, mock_conn = reader
        cursor = MagicMock()
        mock_conn.cursor.return_value = cursor
        cursor.fetchall.return_value = [
            {"insurance_code": "671806320", "name": "펜타닐패치",
             "manufacturer": "얀센", "standard_code": "8800735008105", "category": "NARCOTIC"},
            {"insurance_code": "643507086", "name": "아모시실린",
             "manufacturer": "제약사A", "standard_code": "8806717024900", "category": "PRESCRIPTION"},
        ]

        result = r.read_drug_master()
        narcotic = next(i for i in result if i.insurance_code == "671806320")
        prescription = next(i for i in result if i.insurance_code == "643507086")
        assert narcotic.category == "NARCOTIC"
        assert prescription.category == "PRESCRIPTION"

    def test_empty_insurance_code_skipped(self, reader):
        """insurance_code가 빈 문자열이면 스킵."""
        r, mock_conn = reader
        cursor = MagicMock()
        mock_conn.cursor.return_value = cursor
        cursor.fetchall.return_value = [
            {"insurance_code": "", "name": "빈코드약품",
             "manufacturer": None, "standard_code": None, "category": "PRESCRIPTION"},
            {"insurance_code": "643507086", "name": "정상약품",
             "manufacturer": None, "standard_code": None, "category": "PRESCRIPTION"},
        ]

        result = r.read_drug_master()
        assert len(result) == 1
        assert result[0].insurance_code == "643507086"

    def test_empty_result(self, reader):
        """쿼리 결과 빈 리스트."""
        r, mock_conn = reader
        cursor = MagicMock()
        mock_conn.cursor.return_value = cursor
        cursor.fetchall.return_value = []

        result = r.read_drug_master()
        assert result == []

    def test_data_error_skipped(self, reader):
        """데이터 오류 행은 스킵, 정상 행은 반환."""
        r, mock_conn = reader
        cursor = MagicMock()
        mock_conn.cursor.return_value = cursor
        cursor.fetchall.return_value = [
            {"insurance_code": "643507086", "name": "정상약품",
             "manufacturer": None, "standard_code": None, "category": "PRESCRIPTION"},
            {"insurance_code": "671806320"},  # missing 'category' key → KeyError
        ]

        result = r.read_drug_master()
        assert len(result) == 1
        assert result[0].insurance_code == "643507086"


class TestReadRecentVisits:
    def test_grouping_by_serial(self, reader):
        """DRUG_SEQ별로 VisitRecord 생성."""
        r, mock_conn = reader
        cursor = MagicMock()
        mock_conn.cursor.return_value = cursor
        cursor.fetchall.return_value = [
            {
                "serial": "20260301000001",
                "patient_code": "P001",
                "visit_date": "20260301",
                "prescription_days": 7,
                "proc_datetime": "20260301100000",
                "drug_code": "643507086",
                "quantity_dispensed": Decimal("30"),
            },
            {
                "serial": "20260301000001",
                "patient_code": "P001",
                "visit_date": "20260301",
                "prescription_days": 7,
                "proc_datetime": "20260301100000",
                "drug_code": "643507087",
                "quantity_dispensed": Decimal("20"),
            },
            {
                "serial": "20260302000001",
                "patient_code": "P002",
                "visit_date": "20260302",
                "prescription_days": 14,
                "proc_datetime": "20260302090000",
                "drug_code": "643507086",
                "quantity_dispensed": Decimal("10"),
            },
        ]

        result = r.read_recent_visits("20260101000000")
        assert len(result) == 2

        # 첫 번째 방문: P001, 약품 2개
        v1 = next(v for v in result if v.prescription_days == 7)
        assert len(v1.drugs) == 2
        assert v1.visit_date == date(2026, 3, 1)
        assert v1.proc_dtime == "20260301100000"

        # 두 번째 방문: P002, 약품 1개
        v2 = next(v for v in result if v.prescription_days == 14)
        assert len(v2.drugs) == 1
        assert v2.visit_date == date(2026, 3, 2)

    def test_patient_hash(self, reader):
        """SHA-256(CHRTNO + salt) 해시 검증."""
        r, mock_conn = reader
        cursor = MagicMock()
        mock_conn.cursor.return_value = cursor
        cursor.fetchall.return_value = [
            {
                "serial": "20260301000001",
                "patient_code": "P001",
                "visit_date": "20260301",
                "prescription_days": 7,
                "proc_datetime": "20260301100000",
                "drug_code": "643507086",
                "quantity_dispensed": Decimal("30"),
            },
        ]

        result = r.read_recent_visits("20260101000000")
        expected_hash = hashlib.sha256(("P001" + "test-salt-12345").encode("utf-8")).hexdigest()
        assert result[0].patient_hash == expected_hash

    def test_date_parsing(self, reader):
        """YYYYMMDD → date 변환."""
        r, mock_conn = reader
        cursor = MagicMock()
        mock_conn.cursor.return_value = cursor
        cursor.fetchall.return_value = [
            {
                "serial": "20261225000001",
                "patient_code": "P003",
                "visit_date": "20261225",
                "prescription_days": 3,
                "proc_datetime": "20261225080000",
                "drug_code": "643507086",
                "quantity_dispensed": Decimal("5"),
            },
        ]

        result = r.read_recent_visits("20260101000000")
        assert result[0].visit_date == date(2026, 12, 25)

    def test_invalid_date_skipped(self, reader):
        """유효하지 않은 날짜는 스킵."""
        r, mock_conn = reader
        cursor = MagicMock()
        mock_conn.cursor.return_value = cursor
        cursor.fetchall.return_value = [
            {
                "serial": "BAD0001",
                "patient_code": "P001",
                "visit_date": "INVALID",
                "prescription_days": 7,
                "proc_datetime": "20260101100000",
                "drug_code": "643507086",
                "quantity_dispensed": Decimal("10"),
            },
        ]

        result = r.read_recent_visits("20260101000000")
        assert len(result) == 0

    def test_empty_visits(self, reader):
        r, mock_conn = reader
        cursor = MagicMock()
        mock_conn.cursor.return_value = cursor
        cursor.fetchall.return_value = []

        result = r.read_recent_visits("20260101000000")
        assert result == []

    def test_zp_prefix_drugs_skipped(self, reader):
        """ZP로 시작하는 약품코드(재고조정)는 스킵."""
        r, mock_conn = reader
        cursor = MagicMock()
        mock_conn.cursor.return_value = cursor
        cursor.fetchall.return_value = [
            {
                "serial": "20260301000001",
                "patient_code": "P001",
                "visit_date": "20260301",
                "prescription_days": 7,
                "proc_datetime": "20260301100000",
                "drug_code": "ZP0000001354",
                "quantity_dispensed": Decimal("10"),
            },
            {
                "serial": "20260301000001",
                "patient_code": "P001",
                "visit_date": "20260301",
                "prescription_days": 7,
                "proc_datetime": "20260301100000",
                "drug_code": "643507086",
                "quantity_dispensed": Decimal("30"),
            },
        ]

        result = r.read_recent_visits("20260101000000")
        assert len(result) == 1
        assert len(result[0].drugs) == 1  # Only the non-ZP drug
        assert result[0].drugs[0].drug_insurance_code == "643507086"

    def test_zero_prescription_days_defaults_to_1(self, reader):
        """TOT_DD_CNT가 0이면 1로 기본값."""
        r, mock_conn = reader
        cursor = MagicMock()
        mock_conn.cursor.return_value = cursor
        cursor.fetchall.return_value = [
            {
                "serial": "20260301000001",
                "patient_code": "P001",
                "visit_date": "20260301",
                "prescription_days": 0,
                "proc_datetime": "20260301100000",
                "drug_code": "643507086",
                "quantity_dispensed": Decimal("30"),
            },
        ]

        result = r.read_recent_visits("20260101000000")
        assert result[0].prescription_days == 1

    def test_empty_patient_code_skipped(self, reader):
        """빈 CHRTNO는 스킵."""
        r, mock_conn = reader
        cursor = MagicMock()
        mock_conn.cursor.return_value = cursor
        cursor.fetchall.return_value = [
            {
                "serial": "20260301000001",
                "patient_code": "",
                "visit_date": "20260301",
                "prescription_days": 7,
                "proc_datetime": "20260301100000",
                "drug_code": "643507086",
                "quantity_dispensed": Decimal("30"),
            },
        ]

        result = r.read_recent_visits("20260101000000")
        assert len(result) == 0


class TestReadInventory:
    def test_returns_empty_without_atdps(self, reader):
        """ATDPS 미연동 시 빈 리스트."""
        r, _ = reader
        assert r.read_inventory() == []


class TestConnectionHandling:
    def test_reconnect_on_failure(self, mock_config):
        """연결 실패 시 재연결 시도."""
        with patch("agent1.agent.readers.sqlserver_pm20_reader.pymssql") as mock_pymssql:
            mock_conn = MagicMock()
            mock_pymssql.connect.return_value = mock_conn

            r = SqlServerPM20Reader(mock_config)
            r._conn = None  # 연결 없음

            cursor = MagicMock()
            mock_conn.cursor.return_value = cursor
            cursor.fetchone.return_value = (1,)
            cursor.fetchall.return_value = []

            r.read_drug_master()
            mock_pymssql.connect.assert_called_once()
