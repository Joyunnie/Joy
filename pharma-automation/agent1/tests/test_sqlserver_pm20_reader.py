from __future__ import annotations

"""SqlServerPM20Reader 단위 테스트 — pymssql mock 사용."""

import hashlib
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from agent1.agent.interfaces.pm20_reader import (
    DrugMasterItem,
    DrugStockItem,
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


class TestReadDrugStock:
    def test_basic(self, reader):
        r, mock_conn = reader
        cursor = MagicMock()
        mock_conn.cursor.return_value = cursor
        cursor.fetchall.return_value = [
            {
                "insurance_code": "643507086",
                "drug_name": "아모시실린",
                "current_quantity": Decimal("50.00"),
            },
            {
                "insurance_code": "671806320",
                "drug_name": "펜타닐패치",
                "current_quantity": Decimal("5.50"),
            },
        ]

        result = r.read_drug_stock()

        assert len(result) == 2
        assert isinstance(result[0], DrugStockItem)
        assert result[0].drug_insurance_code == "643507086"
        assert result[0].drug_name == "아모시실린"
        assert result[0].current_quantity == 50.0

    def test_empty_temp_stock(self, reader):
        r, mock_conn = reader
        cursor = MagicMock()
        mock_conn.cursor.return_value = cursor
        cursor.fetchall.return_value = []

        result = r.read_drug_stock()
        assert result == []

    def test_negative_quantity(self, reader):
        """음수 재고 처리."""
        r, mock_conn = reader
        cursor = MagicMock()
        mock_conn.cursor.return_value = cursor
        cursor.fetchall.return_value = [
            {
                "insurance_code": "643507086",
                "drug_name": "아모시실린",
                "current_quantity": Decimal("-3.50"),
            },
        ]

        result = r.read_drug_stock()
        assert result[0].current_quantity == -3.5

    def test_data_error_skipped(self, reader):
        """JOIN 실패 또는 데이터 이상 행은 스킵."""
        r, mock_conn = reader
        cursor = MagicMock()
        mock_conn.cursor.return_value = cursor
        cursor.fetchall.return_value = [
            {"insurance_code": None, "drug_name": "??", "current_quantity": 10},
            {"insurance_code": "643507086", "drug_name": "정상", "current_quantity": Decimal("5")},
        ]

        result = r.read_drug_stock()
        # None insurance_code → strip() 실패 → 스킵
        assert len(result) == 1
        assert result[0].drug_insurance_code == "643507086"


class TestReadDrugMaster:
    def test_pass1_code_match(self, reader):
        """Pass 1: TBSID040_04 goods_code → insurance_code mapping."""
        r, mock_conn = reader
        cursor = MagicMock()
        mock_conn.cursor.return_value = cursor
        # Query 1: SQL_DRUG_MASTER, Query 2: SQL_GOODS_CODE_TO_INSURANCE, Query 3: SQL_INSURANCE_CODE_BY_NAME
        cursor.fetchall.side_effect = [
            [
                {"standard_code": "KD12345", "goods_code": "ZD0001", "name": "아모시실린",
                 "manufacturer": "제약사A", "category": "PRESCRIPTION"},
                {"standard_code": "NC00001", "goods_code": "ZD0002", "name": "펜타닐패치",
                 "manufacturer": None, "category": "NARCOTIC"},
            ],
            [
                {"goods_code": "ZD0001", "insurance_code": "643507086"},
                {"goods_code": "ZD0002", "insurance_code": "671806320"},
            ],
            [],  # pass 2 not needed
        ]

        result = r.read_drug_master()
        assert len(result) == 2
        assert result[0].standard_code == "KD12345"
        assert result[0].insurance_code == "643507086"
        assert result[1].insurance_code == "671806320"

    def test_pass2_name_fallback(self, reader):
        """Pass 2: name-based matching for items not matched in pass 1."""
        r, mock_conn = reader
        cursor = MagicMock()
        mock_conn.cursor.return_value = cursor
        cursor.fetchall.side_effect = [
            [{"standard_code": "KD12345", "goods_code": "ZD0001", "name": "아모시실린",
              "manufacturer": None, "category": "PRESCRIPTION"}],
            [],  # pass 1 returns nothing
            [{"insurance_code": "643507086", "drug_name": "아모시실린"}],  # pass 2 matches by name
        ]

        result = r.read_drug_master()
        assert result[0].insurance_code == "643507086"

    def test_pass2_name_collision_skips_both(self, reader):
        """이름 충돌 시 양쪽 모두 스킵 (잘못된 매칭보다 매칭 없음이 안전)."""
        r, mock_conn = reader
        cursor = MagicMock()
        mock_conn.cursor.return_value = cursor
        cursor.fetchall.side_effect = [
            [{"standard_code": "KD12345", "goods_code": "", "name": "다이아벡스정",
              "manufacturer": None, "category": "PRESCRIPTION"}],
            [],  # pass 1 no match
            [
                {"insurance_code": "641600370", "drug_name": "다이아벡스정"},
                {"insurance_code": "641600390", "drug_name": "다이아벡스정"},  # collision!
            ],
        ]

        result = r.read_drug_master()
        assert result[0].insurance_code is None  # collision → no match

    def test_pass1_takes_priority_over_pass2(self, reader):
        """Pass 1 매칭 결과는 pass 2에서 덮어쓰지 않음."""
        r, mock_conn = reader
        cursor = MagicMock()
        mock_conn.cursor.return_value = cursor
        cursor.fetchall.side_effect = [
            [{"standard_code": "KD12345", "goods_code": "ZD0001", "name": "아모시실린",
              "manufacturer": None, "category": "PRESCRIPTION"}],
            [{"goods_code": "ZD0001", "insurance_code": "643507086"}],  # pass 1 match
            [{"insurance_code": "999999999", "drug_name": "아모시실린"}],  # pass 2 would differ
        ]

        result = r.read_drug_master()
        assert result[0].insurance_code == "643507086"  # pass 1 wins

    def test_unmatched_both_passes_leaves_none(self, reader):
        """양쪽 모두 불일치 시 insurance_code는 None."""
        r, mock_conn = reader
        cursor = MagicMock()
        mock_conn.cursor.return_value = cursor
        cursor.fetchall.side_effect = [
            [{"standard_code": "KD99999", "goods_code": "ZD9999", "name": "미등록약품",
              "manufacturer": None, "category": "PRESCRIPTION"}],
            [],  # pass 1 no match
            [{"insurance_code": "999999999", "drug_name": "완전다른이름"}],  # pass 2 no match
        ]

        result = r.read_drug_master()
        assert result[0].insurance_code is None

    def test_pass1_query_failure_falls_through_to_pass2(self, reader):
        """Pass 1 실패 시 pass 2로 fallback."""
        r, mock_conn = reader
        cursor = MagicMock()
        mock_conn.cursor.return_value = cursor
        cursor.fetchall.side_effect = [
            [{"standard_code": "KD12345", "goods_code": "ZD0001", "name": "아모시실린",
              "manufacturer": None, "category": "PRESCRIPTION"}],
            Exception("TBSID040_04 connection failed"),  # pass 1 fails
            [{"insurance_code": "643507086", "drug_name": "아모시실린"}],  # pass 2 works
        ]

        result = r.read_drug_master()
        assert result[0].insurance_code == "643507086"

    def test_both_passes_fail_returns_items_without_insurance(self, reader):
        """양쪽 모두 실패해도 items는 정상 반환."""
        r, mock_conn = reader
        cursor = MagicMock()
        mock_conn.cursor.return_value = cursor
        cursor.fetchall.side_effect = [
            [{"standard_code": "KD12345", "goods_code": "", "name": "아모시실린",
              "manufacturer": None, "category": "PRESCRIPTION"}],
            Exception("pass 1 fail"),
            Exception("pass 2 fail"),
        ]

        result = r.read_drug_master()
        assert len(result) == 1
        assert result[0].insurance_code is None

    def test_name_collision_logs_warning(self, reader, caplog):
        """이름 충돌 시 경고 로그 출력."""
        import logging
        r, mock_conn = reader
        cursor = MagicMock()
        mock_conn.cursor.return_value = cursor
        cursor.fetchall.side_effect = [
            [{"standard_code": "KD12345", "goods_code": "", "name": "다이아벡스정",
              "manufacturer": None, "category": "PRESCRIPTION"}],
            [],
            [
                {"insurance_code": "641600370", "drug_name": "다이아벡스정"},
                {"insurance_code": "641600390", "drug_name": "다이아벡스정"},
            ],
        ]

        with caplog.at_level(logging.WARNING, logger="agent1.pm20_reader"):
            r.read_drug_master()
        assert "Name collision" in caplog.text
        assert "다이아벡스정" in caplog.text

    def test_mixed_pass1_and_pass2_results(self, reader):
        """3 drugs: pass1 match, pass2 match, unmatched."""
        r, mock_conn = reader
        cursor = MagicMock()
        mock_conn.cursor.return_value = cursor
        cursor.fetchall.side_effect = [
            [
                {"standard_code": "KD001", "goods_code": "ZD0001", "name": "약품A",
                 "manufacturer": None, "category": "PRESCRIPTION"},
                {"standard_code": "KD002", "goods_code": "ZD0002", "name": "약품B",
                 "manufacturer": None, "category": "PRESCRIPTION"},
                {"standard_code": "KD003", "goods_code": "ZD0003", "name": "약품C",
                 "manufacturer": None, "category": "PRESCRIPTION"},
            ],
            [{"goods_code": "ZD0001", "insurance_code": "111111111"}],  # pass 1: only 약품A
            [{"insurance_code": "222222222", "drug_name": "약품B"}],    # pass 2: only 약품B
        ]

        result = r.read_drug_master()
        assert result[0].insurance_code == "111111111"  # pass 1
        assert result[1].insurance_code == "222222222"  # pass 2
        assert result[2].insurance_code is None          # unmatched

    def test_null_goods_regno_filtered(self, reader):
        """Goods_RegNo가 null인 약품은 SQL WHERE에서 제외 (DB 레벨)."""
        r, mock_conn = reader
        cursor = MagicMock()
        mock_conn.cursor.return_value = cursor
        cursor.fetchall.side_effect = [[], [], []]  # All three queries return empty

        result = r.read_drug_master()
        assert result == []


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

            r.read_drug_stock()
            mock_pymssql.connect.assert_called_once()
