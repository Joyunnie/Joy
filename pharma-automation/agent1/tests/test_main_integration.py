"""Agent1 sync_cycle 통합 테스트 — Reader + CloudClient mock."""

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from agent1.agent.interfaces.pm20_reader import (
    DrugDispensed,
    DrugMasterItem,
    DrugStockItem,
    VisitRecord,
)
from agent1.agent.main import Agent1


@pytest.fixture
def agent(tmp_path, mock_config):
    """Agent1 with mocked dependencies."""
    config_path = tmp_path / "config.yaml"
    import yaml
    config_path.write_text(yaml.dump(mock_config._data))

    with patch("agent1.agent.main.load_config", return_value=mock_config):
        a = Agent1(str(config_path))
        a.cloud_client = MagicMock()
        a.cloud_client.post_sync = MagicMock(return_value={})
        return a


class TestSyncCycleOrder:
    def test_drugs_stock_visits_order(self, agent):
        """sync_cycle은 drugs → drug-stock → visits 순서로 호출."""
        mock_reader = MagicMock()
        mock_reader.read_drug_master.return_value = [
            DrugMasterItem("KD12345", "아모시실린", "제약사A", "PRESCRIPTION"),
        ]
        mock_reader.read_drug_stock.return_value = [
            DrugStockItem("KD12345", "아모시실린", 50.0, False),
        ]
        mock_reader.read_recent_visits.return_value = [
            VisitRecord(
                patient_hash="abc123",
                visit_date=date(2026, 3, 1),
                prescription_days=7,
                drugs=[DrugDispensed("KD12345", 30)],
            ),
        ]
        mock_reader.read_inventory.return_value = []
        agent.pm20_reader = mock_reader

        agent.sync_cycle()

        calls = agent.cloud_client.post_sync.call_args_list
        sync_types = [c[0][0] for c in calls]
        assert sync_types == ["drugs", "drug-stock", "visits"]

    def test_drug_master_only_once_per_day(self, agent):
        """약품 마스터는 하루 1회만 동기화."""
        mock_reader = MagicMock()
        mock_reader.read_drug_master.return_value = [
            DrugMasterItem("KD12345", "아모시실린", None, "PRESCRIPTION"),
        ]
        mock_reader.read_drug_stock.return_value = []
        mock_reader.read_recent_visits.return_value = []
        mock_reader.read_inventory.return_value = []
        agent.pm20_reader = mock_reader

        # 첫 사이클: drugs 호출됨
        agent.sync_cycle()
        assert mock_reader.read_drug_master.call_count == 1

        # 두 번째 사이클: drugs 호출 안 됨 (24시간 미경과)
        agent.sync_cycle()
        assert mock_reader.read_drug_master.call_count == 1


class TestSyncCycleErrorHandling:
    def test_drug_stock_error_does_not_block_visits(self, agent):
        """drug-stock 에러 시에도 visits 동기화 진행."""
        mock_reader = MagicMock()
        mock_reader.read_drug_master.return_value = []
        mock_reader.read_drug_stock.side_effect = Exception("DB error")
        mock_reader.read_recent_visits.return_value = [
            VisitRecord("hash1", date(2026, 3, 1), 7, []),
        ]
        mock_reader.read_inventory.return_value = []
        agent.pm20_reader = mock_reader
        agent._last_drug_master_sync = datetime.now(timezone.utc)

        agent.sync_cycle()

        # visits는 여전히 호출됨
        mock_reader.read_recent_visits.assert_called_once()

    def test_cloud_unreachable_queues(self, agent):
        """Cloud 장애 시 오프라인 큐에 저장."""
        mock_reader = MagicMock()
        mock_reader.read_drug_master.return_value = []
        mock_reader.read_drug_stock.return_value = [
            DrugStockItem("KD12345", "아모시실린", 50.0, False),
        ]
        mock_reader.read_recent_visits.return_value = []
        mock_reader.read_inventory.return_value = []
        agent.pm20_reader = mock_reader
        agent._last_drug_master_sync = datetime.now(timezone.utc)

        agent.cloud_client.post_sync.side_effect = ConnectionError("timeout")
        agent.offline_queue = MagicMock()

        agent.sync_cycle()

        agent.offline_queue.enqueue.assert_called_once()
        call_args = agent.offline_queue.enqueue.call_args
        assert call_args[0][0] == "drug-stock"


class TestSyncPayloadFormat:
    def test_drug_stock_payload(self, agent):
        """drug-stock 페이로드 형식 확인."""
        mock_reader = MagicMock()
        mock_reader.read_drug_master.return_value = []
        mock_reader.read_drug_stock.return_value = [
            DrugStockItem("KD12345", "아모시실린", 50.5, False),
            DrugStockItem("NC00001", "펜타닐패치", 3.0, True),
        ]
        mock_reader.read_recent_visits.return_value = []
        mock_reader.read_inventory.return_value = []
        agent.pm20_reader = mock_reader
        agent._last_drug_master_sync = datetime.now(timezone.utc)

        agent.sync_cycle()

        call_args = agent.cloud_client.post_sync.call_args_list
        drug_stock_call = next(c for c in call_args if c[0][0] == "drug-stock")
        payload = drug_stock_call[0][1]
        assert "items" in payload
        assert "synced_at" in payload
        assert len(payload["items"]) == 2
        assert payload["items"][0]["drug_standard_code"] == "KD12345"
        assert payload["items"][0]["current_quantity"] == 50.5
        assert payload["items"][1]["is_narcotic"] is True

    def test_visits_payload(self, agent):
        """visits 페이로드 형식 확인."""
        mock_reader = MagicMock()
        mock_reader.read_drug_master.return_value = []
        mock_reader.read_drug_stock.return_value = []
        mock_reader.read_recent_visits.return_value = [
            VisitRecord(
                patient_hash="abc123def456",
                visit_date=date(2026, 3, 15),
                prescription_days=14,
                drugs=[DrugDispensed("KD12345", 30)],
            ),
        ]
        mock_reader.read_inventory.return_value = []
        agent.pm20_reader = mock_reader
        agent._last_drug_master_sync = datetime.now(timezone.utc)

        agent.sync_cycle()

        call_args = agent.cloud_client.post_sync.call_args_list
        visits_call = next(c for c in call_args if c[0][0] == "visits")
        payload = visits_call[0][1]
        assert "visits" in payload
        visit = payload["visits"][0]
        assert visit["patient_hash"] == "abc123def456"
        assert visit["visit_date"] == "2026-03-15"
        assert visit["prescription_days"] == 14
        assert visit["source"] == "PM20_SYNC"
        assert visit["drugs"][0]["drug_standard_code"] == "KD12345"
        assert visit["drugs"][0]["quantity_dispensed"] == 30
