from __future__ import annotations

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

        # Mock window detection: 마약류 팝업만 있고 나머지 선택 팝업은 없음
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

    @patch("agent1.agent.rpa.narcotic_handler.window_utils")
    @patch("agent1.agent.rpa.narcotic_handler.input_utils")
    def test_disease_code_popup_skipped_when_absent(self, mock_input, mock_window):
        """질병기호 팝업이 없으면 스킵해야 함."""
        from agent1.agent.rpa.narcotic_handler import NarcoticHandler

        fs = FailsafeManager()
        handler = NarcoticHandler(fs)

        mock_win = MagicMock()
        mock_window.find_window_by_title.return_value = mock_win
        mock_window.activate_window.return_value = True
        mock_window.is_window_visible.return_value = False  # 모든 선택 팝업 없음

        success, msg = handler.execute({"quantity": 1})
        assert success is True
        # 질병기호 클릭(continue_button)이 호출되지 않았어야 함
        # is_window_visible이 False 반환 → click은 완료 버튼(step3)에서만 호출됨
        assert mock_input.click.call_count == 1  # complete_button_click 1회만

    @patch("agent1.agent.rpa.narcotic_handler.window_utils")
    @patch("agent1.agent.rpa.narcotic_handler.input_utils")
    def test_disease_code_popup_handled(self, mock_input, mock_window):
        """질병기호 팝업이 뜨면 '계속 진행' 클릭."""
        from agent1.agent.rpa.narcotic_handler import DISEASE_CODE_POPUP_TITLE, NarcoticHandler

        fs = FailsafeManager()
        handler = NarcoticHandler(fs)

        mock_win = MagicMock()
        mock_window.find_window_by_title.return_value = mock_win
        mock_window.activate_window.return_value = True

        # 질병기호 팝업만 True, 나머지는 False
        def is_visible(title):
            return title == DISEASE_CODE_POPUP_TITLE

        mock_window.is_window_visible.side_effect = is_visible

        success, msg = handler.execute({"quantity": 1})
        assert success is True
        # complete_button(1) + continue_button(1) = 2회 클릭
        assert mock_input.click.call_count == 2

    @patch("agent1.agent.rpa.narcotic_handler.window_utils")
    @patch("agent1.agent.rpa.narcotic_handler.input_utils")
    def test_dur_review_handled_with_f12(self, mock_input, mock_window):
        """DUR 처방검토 화면이 뜨면 F12 전송."""
        from agent1.agent.rpa.narcotic_handler import DUR_REVIEW_TITLE, NarcoticHandler

        fs = FailsafeManager()
        handler = NarcoticHandler(fs)

        mock_win = MagicMock()
        mock_window.find_window_by_title.return_value = mock_win
        mock_window.activate_window.return_value = True

        # DUR만 True, 그 이후엔 False (사유 선택 팝업 없음)
        call_counts = {"dur": 0}

        def is_visible(title):
            if title == DUR_REVIEW_TITLE:
                call_counts["dur"] += 1
                # 첫 번째 is_window_visible(DUR) = True (화면 감지)
                # 두 번째 이후(사유선택 루프) = False
                return call_counts["dur"] == 1
            return False

        mock_window.is_window_visible.side_effect = is_visible

        success, msg = handler.execute({"quantity": 1})
        assert success is True
        # F12 키 전송 확인
        f12_calls = [c for c in mock_input.press_key.call_args_list if c.args[0] == "f12"]
        assert len(f12_calls) == 1

    @patch("agent1.agent.rpa.narcotic_handler.window_utils")
    @patch("agent1.agent.rpa.narcotic_handler.input_utils")
    def test_payment_and_bag_screen_skipped_below_threshold(self, mock_input, mock_window):
        """약품 7종 미만이면 결제/봉투 화면 처리 스킵."""
        from agent1.agent.rpa.narcotic_handler import NarcoticHandler

        fs = FailsafeManager()
        handler = NarcoticHandler(fs)

        mock_win = MagicMock()
        mock_window.find_window_by_title.return_value = mock_win
        mock_window.activate_window.return_value = True
        mock_window.is_window_visible.return_value = False

        # drug_count=6 (< 7) → 결제/봉투 화면 감지 시도 자체를 안 함
        success, msg = handler.execute({"quantity": 1, "drug_count": 6})
        assert success is True
        # is_window_visible 호출 횟수: 질병기호(1) + DUR(1) = 2회
        # 결제/봉투는 is_window_visible 호출 없음
        visible_titles = [c.args[0] for c in mock_window.is_window_visible.call_args_list]
        from agent1.agent.rpa.narcotic_handler import BAG_SELECTION_TITLE, PAYMENT_SCREEN_TITLE
        assert PAYMENT_SCREEN_TITLE not in visible_titles
        assert BAG_SELECTION_TITLE not in visible_titles

    @patch("agent1.agent.rpa.narcotic_handler.window_utils")
    @patch("agent1.agent.rpa.narcotic_handler.input_utils")
    def test_payment_screen_handled_with_esc(self, mock_input, mock_window):
        """약품 7종 이상이고 결제 화면이 뜨면 ESC 전송."""
        from agent1.agent.rpa.narcotic_handler import PAYMENT_SCREEN_TITLE, NarcoticHandler

        fs = FailsafeManager()
        handler = NarcoticHandler(fs)

        mock_win = MagicMock()
        mock_window.find_window_by_title.return_value = mock_win
        mock_window.activate_window.return_value = True

        def is_visible(title):
            return title == PAYMENT_SCREEN_TITLE

        mock_window.is_window_visible.side_effect = is_visible

        success, msg = handler.execute({"quantity": 1, "drug_count": 7})
        assert success is True
        esc_calls = [c for c in mock_input.press_key.call_args_list if c.args[0] == "escape"]
        assert len(esc_calls) == 1

    @patch("agent1.agent.rpa.narcotic_handler.window_utils")
    @patch("agent1.agent.rpa.narcotic_handler.input_utils")
    def test_bag_selection_handled_with_middle_button(self, mock_input, mock_window):
        """약품 7종 이상이고 봉투 선택 화면이 뜨면 가운데 버튼 클릭."""
        from agent1.agent.rpa.narcotic_handler import BAG_SELECTION_TITLE, NarcoticHandler

        fs = FailsafeManager()
        handler = NarcoticHandler(fs)

        mock_win = MagicMock()
        mock_window.find_window_by_title.return_value = mock_win
        mock_window.activate_window.return_value = True

        def is_visible(title):
            return title == BAG_SELECTION_TITLE

        mock_window.is_window_visible.side_effect = is_visible

        success, msg = handler.execute({"quantity": 1, "drug_count": 7})
        assert success is True
        # complete_button(1) + bag_middle_button(1) = 2회
        assert mock_input.click.call_count == 2


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
