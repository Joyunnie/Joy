"""Tests for Agent1 lifecycle: run loop, signal handling, error recovery.

Covers: immediate shutdown, network failure mid-sync, drug master interval.
"""
import signal
import threading
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
import yaml

from agent1.agent.interfaces.pm20_reader import DrugMasterItem, VisitRecord
from agent1.agent.main import Agent1


@pytest.fixture
def config_path(tmp_path, mock_config):
    p = tmp_path / "config.yaml"
    p.write_text(yaml.dump(mock_config._data))
    return str(p)


@pytest.fixture
def agent(config_path, mock_config):
    with patch("agent1.agent.main.load_config", return_value=mock_config):
        a = Agent1(config_path)
        a.cloud_client = MagicMock()
        a.cloud_client.post_sync = MagicMock(return_value={})
        return a


class TestRunLoop:
    def test_stop_event_exits_loop(self, agent):
        """Setting _stop_event causes run() to exit."""
        agent._stop_event.set()
        # run() should return immediately since stop_event is already set
        agent.run()
        # If we get here, it didn't hang

    def test_run_executes_at_least_one_cycle(self, agent):
        """run() executes sync_cycle at least once before stop."""
        call_count = 0
        original_sync = agent.sync_cycle

        def counting_sync():
            nonlocal call_count
            call_count += 1
            agent._stop_event.set()  # Stop after first cycle

        agent.sync_cycle = counting_sync
        agent.run()
        assert call_count == 1

    def test_exception_in_sync_does_not_crash_loop(self, agent):
        """Exception in sync_cycle is caught, loop continues."""
        calls = []

        def failing_sync():
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("simulated crash")
            agent._stop_event.set()

        agent.sync_cycle = failing_sync
        agent.run()
        assert len(calls) == 2  # First fails, second stops


class TestSignalHandling:
    def test_handle_signal_sets_stop_event(self, agent):
        """_handle_signal sets the stop event."""
        assert not agent._stop_event.is_set()
        agent._handle_signal(signal.SIGINT, None)
        assert agent._stop_event.is_set()


class TestDrugMasterInterval:
    def test_first_cycle_syncs_drug_master(self, agent):
        """First cycle always syncs drug master."""
        mock_reader = MagicMock()
        mock_reader.read_drug_master.return_value = [
            DrugMasterItem("KD001", "약품", None, "PRESCRIPTION", insurance_code="INS001"),
        ]
        mock_reader.read_recent_visits.return_value = []
        mock_reader.read_inventory.return_value = []
        agent.pm20_reader = mock_reader

        agent.sync_cycle()
        mock_reader.read_drug_master.assert_called_once()

    def test_skip_if_recently_synced(self, agent):
        """Drug master skipped if synced within interval."""
        mock_reader = MagicMock()
        mock_reader.read_drug_master.return_value = []
        mock_reader.read_recent_visits.return_value = []
        mock_reader.read_inventory.return_value = []
        agent.pm20_reader = mock_reader

        # Mark as recently synced
        agent._last_drug_master_sync = datetime.now(timezone.utc)

        agent.sync_cycle()
        mock_reader.read_drug_master.assert_not_called()

    def test_syncs_after_interval_elapsed(self, agent):
        """Drug master syncs if interval has elapsed."""
        mock_reader = MagicMock()
        mock_reader.read_drug_master.return_value = [
            DrugMasterItem("KD001", "약품", None, "PRESCRIPTION", insurance_code="INS001"),
        ]
        mock_reader.read_recent_visits.return_value = []
        mock_reader.read_inventory.return_value = []
        agent.pm20_reader = mock_reader

        # Mark as synced 25 hours ago (interval is 24 hours)
        agent._last_drug_master_sync = datetime.now(timezone.utc) - timedelta(hours=25)

        agent.sync_cycle()
        mock_reader.read_drug_master.assert_called_once()


class TestNetworkFailureMidSync:
    def test_visits_fail_inventory_continues(self, agent):
        """Network failure on visits doesn't block inventory sync."""
        mock_reader = MagicMock()
        mock_reader.read_drug_master.return_value = []
        mock_reader.read_recent_visits.side_effect = ConnectionError("network down")
        mock_reader.read_inventory.return_value = []
        agent.pm20_reader = mock_reader
        agent._last_drug_master_sync = datetime.now(timezone.utc)

        # Should not raise
        agent.sync_cycle()
        mock_reader.read_inventory.assert_called_once()

    def test_drug_master_fail_visits_continue(self, agent):
        """Drug master failure doesn't block visit sync."""
        mock_reader = MagicMock()
        mock_reader.read_drug_master.side_effect = Exception("DB timeout")
        mock_reader.read_recent_visits.return_value = []
        mock_reader.read_inventory.return_value = []
        agent.pm20_reader = mock_reader

        # Should not raise
        agent.sync_cycle()
        mock_reader.read_recent_visits.assert_called_once()

    def test_cloud_down_queues_all(self, agent):
        """Cloud down → all sync types queued."""
        mock_reader = MagicMock()
        mock_reader.read_drug_master.return_value = [
            DrugMasterItem("KD001", "약품", None, "PRESCRIPTION", insurance_code="INS001"),
        ]
        mock_reader.read_recent_visits.return_value = []
        mock_reader.read_inventory.return_value = []
        agent.pm20_reader = mock_reader

        agent.cloud_client.post_sync.side_effect = ConnectionError("refused")
        agent.offline_queue = MagicMock()

        agent.sync_cycle()

        # Drug master should have been queued
        agent.offline_queue.enqueue.assert_called()
        queued_types = [c[0][0] for c in agent.offline_queue.enqueue.call_args_list]
        assert "drugs" in queued_types
