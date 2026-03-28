"""RPA 메인 루프: 커맨드 폴링 + 디스패치.

P35: 폴링 주기를 config rpa.polling_interval_seconds에서 설정 (기본 2초).
"""

import logging
import threading

from agent1.agent.cloud_client import CloudClient
from agent1.agent.rpa.failsafe import FailsafeManager
from agent1.agent.rpa.narcotic_handler import NarcoticHandler
from agent1.agent.rpa.prescription_handler import PrescriptionHandler

logger = logging.getLogger("agent1.rpa.manager")


class RpaManager:
    def __init__(
        self,
        cloud_client: CloudClient,
        polling_interval: float = 2.0,
        rpa_coordinates: dict | None = None,
    ):
        self.cloud_client = cloud_client
        self.polling_interval = polling_interval
        self._enabled = False
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

        # Components
        self.failsafe = FailsafeManager()
        self.narcotic_handler = NarcoticHandler(
            self.failsafe,
            coordinates=rpa_coordinates.get("narcotics", {}) if rpa_coordinates else None,
        )
        self.prescription_handler = PrescriptionHandler(
            self.failsafe,
            coordinates=rpa_coordinates.get("prescription", {}) if rpa_coordinates else None,
        )

        # Auto-OFF callback
        self.failsafe.set_auto_off_callback(self._auto_off)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def toggle(self) -> bool:
        """ON/OFF 토글. 새 상태를 반환."""
        if self._enabled:
            self.disable()
        else:
            self.enable()
        return self._enabled

    def enable(self):
        if self._enabled:
            return
        self._enabled = True
        self._stop_event.clear()
        self.failsafe.reset()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="rpa-poll")
        self._thread.start()
        logger.info("RPA enabled (polling every %.1fs)", self.polling_interval)

    def disable(self):
        if not self._enabled:
            return
        self._enabled = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        self._thread = None
        logger.info("RPA disabled")

    def _auto_off(self):
        """Failsafe에 의한 자동 OFF."""
        logger.warning("Auto-OFF triggered by failsafe")
        self._enabled = False
        self._stop_event.set()

    def _poll_loop(self):
        """커맨드 폴링 루프."""
        while not self._stop_event.is_set():
            try:
                commands = self.cloud_client.get_pending_rpa_commands()
                for cmd in commands:
                    if self._stop_event.is_set():
                        break
                    self._execute_command(cmd)
            except Exception as e:
                logger.error("Poll loop error: %s", e)

            self._stop_event.wait(timeout=self.polling_interval)

    def _execute_command(self, cmd: dict):
        """단일 커맨드 실행."""
        cmd_id = cmd["id"]
        cmd_type = cmd["command_type"]
        payload = cmd.get("payload", {})

        logger.info("Executing command #%d: %s", cmd_id, cmd_type)
        self.cloud_client.update_rpa_command_status(cmd_id, "EXECUTING")

        if cmd_type == "NARCOTICS_INPUT":
            success, message = self.narcotic_handler.execute(payload)
        elif cmd_type == "PRESCRIPTION_INPUT":
            success, message = self.prescription_handler.execute(payload)
        else:
            success, message = False, f"Unknown command type: {cmd_type}"

        if success:
            self.failsafe.record_success()
            self.cloud_client.update_rpa_command_status(cmd_id, "SUCCESS")
            logger.info("Command #%d completed: %s", cmd_id, message)
        else:
            auto_off = self.failsafe.record_failure(message)
            self.cloud_client.update_rpa_command_status(cmd_id, "FAILED", message)
            logger.warning("Command #%d failed: %s (auto_off=%s)", cmd_id, message, auto_off)

    def stop(self):
        """Graceful shutdown."""
        self.disable()
