"""Agent1 RPA module unit tests (mock pyautogui/pygetwindow)."""

import threading
from unittest.mock import MagicMock, patch

import pytest

from agent1.agent.rpa.failsafe import FailsafeManager
from agent1.agent.rpa.rpa_manager import RpaManager


class TestFailsafe:
    def test_record_success_resets_count(self):
        fs = FailsafeManager(max_failures=3)
        fs.record_failure("err1")
        fs.record_failure("err2")
        assert fs.failure_count == 2
        fs.record_success()
        assert fs.failure_count == 0

    def test_auto_off_after_consecutive_failures(self):
        callback = MagicMock()
        fs = FailsafeManager(max_failures=3)
        fs.set_auto_off_callback(callback)

        fs.record_failure("err1")
        fs.record_failure("err2")
        assert not callback.called
        triggered = fs.record_failure("err3")
        assert triggered is True
        callback.assert_called_once()
        # Count resets after auto-off
        assert fs.failure_count == 0

    def test_no_auto_off_below_threshold(self):
        callback = MagicMock()
        fs = FailsafeManager(max_failures=5)
        fs.set_auto_off_callback(callback)
        for _ in range(4):
            fs.record_failure("err")
        assert not callback.called

    def test_reset(self):
        fs = FailsafeManager()
        fs.record_failure("err")
        fs.record_failure("err")
        fs.reset()
        assert fs.failure_count == 0


class TestNarcoticHandler:
    @patch("agent1.agent.rpa.narcotic_handler.window_utils")
    @patch("agent1.agent.rpa.narcotic_handler.input_utils")
    def test_execute_success(self, mock_input, mock_window):
        from agent1.agent.rpa.narcotic_handler import NarcoticHandler

        fs = FailsafeManager()
        handler = NarcoticHandler(fs)

        # Mock window detection
        mock_win = MagicMock()
        mock_window.find_window_by_title.return_value = mock_win
        mock_window.activate_window.return_value = True
        mock_window.is_window_visible.return_value = False

        success, msg = handler.execute({"quantity": 2})
        assert success is True
        assert "완료" in msg

    @patch("agent1.agent.rpa.narcotic_handler.window_utils")
    def test_execute_popup_not_found(self, mock_window):
        from agent1.agent.rpa.narcotic_handler import NarcoticHandler

        fs = FailsafeManager()
        handler = NarcoticHandler(fs)
        mock_window.find_window_by_title.return_value = None

        success, msg = handler.execute({"quantity": 1})
        assert success is False
        assert "팝업" in msg


class TestPrescriptionHandler:
    @patch("agent1.agent.rpa.prescription_handler.window_utils")
    @patch("agent1.agent.rpa.prescription_handler.input_utils")
    def test_execute_success(self, mock_input, mock_window):
        from agent1.agent.rpa.pm20_controller import PM20Controller
        from agent1.agent.rpa.prescription_handler import PrescriptionHandler

        fs = FailsafeManager()
        pm20 = PM20Controller()

        mock_window.is_window_visible.return_value = True
        mock_win = MagicMock()
        mock_window.find_window_by_title.return_value = mock_win
        mock_window.activate_window.return_value = True

        handler = PrescriptionHandler(fs, pm20)
        payload = {
            "patient_name": "홍길동",
            "patient_dob": "900101",
            "drugs": [
                {"drug_name": "아모시실린", "dosage": "1정", "frequency": "3", "days": 7},
            ],
        }
        success, msg = handler.execute(payload)
        assert success is True
        assert "1건" in msg

    @patch("agent1.agent.rpa.prescription_handler.window_utils")
    @patch("agent1.agent.rpa.prescription_handler.input_utils")
    def test_execute_no_drugs(self, mock_input, mock_window):
        from agent1.agent.rpa.pm20_controller import PM20Controller
        from agent1.agent.rpa.prescription_handler import PrescriptionHandler

        fs = FailsafeManager()
        pm20 = PM20Controller()
        mock_window.is_window_visible.return_value = True
        mock_win = MagicMock()
        mock_window.find_window_by_title.return_value = mock_win

        handler = PrescriptionHandler(fs, pm20)
        success, msg = handler.execute({"patient_name": "홍길동", "drugs": []})
        assert success is False
        assert "약품이 없습니다" in msg


class TestRpaManager:
    def test_toggle_on_off(self):
        mock_client = MagicMock()
        mock_client.get_pending_rpa_commands.return_value = []
        mgr = RpaManager(mock_client, polling_interval=0.1)

        assert not mgr.enabled
        mgr.toggle()
        assert mgr.enabled
        mgr.toggle()
        assert not mgr.enabled

    def test_enable_starts_thread(self):
        mock_client = MagicMock()
        mock_client.get_pending_rpa_commands.return_value = []
        mgr = RpaManager(mock_client, polling_interval=0.1)

        mgr.enable()
        assert mgr.enabled
        assert mgr._thread is not None
        assert mgr._thread.is_alive()
        mgr.stop()
        assert not mgr.enabled

    def test_execute_command_success(self):
        mock_client = MagicMock()
        mock_client.get_pending_rpa_commands.return_value = []
        mgr = RpaManager(mock_client, polling_interval=0.1)

        # Mock narcotic handler
        mgr.narcotic_handler.execute = MagicMock(return_value=(True, "ok"))
        cmd = {"id": 1, "command_type": "NARCOTICS_INPUT", "payload": {}}
        mgr._execute_command(cmd)

        mock_client.update_rpa_command_status.assert_any_call(1, "EXECUTING")
        mock_client.update_rpa_command_status.assert_any_call(1, "SUCCESS")

    def test_execute_command_failure(self):
        mock_client = MagicMock()
        mgr = RpaManager(mock_client, polling_interval=0.1)

        mgr.narcotic_handler.execute = MagicMock(return_value=(False, "window not found"))
        cmd = {"id": 2, "command_type": "NARCOTICS_INPUT", "payload": {}}
        mgr._execute_command(cmd)

        mock_client.update_rpa_command_status.assert_any_call(2, "EXECUTING")
        mock_client.update_rpa_command_status.assert_any_call(2, "FAILED", "window not found")
