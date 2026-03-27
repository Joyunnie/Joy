"""RPA 실패 카운트 + 자동 OFF 로직."""

import logging
import threading

logger = logging.getLogger("agent1.rpa.failsafe")

DEFAULT_MAX_CONSECUTIVE_FAILURES = 3


class FailsafeManager:
    def __init__(self, max_failures: int = DEFAULT_MAX_CONSECUTIVE_FAILURES):
        self._max_failures = max_failures
        self._consecutive_failures = 0
        self._lock = threading.Lock()
        self._auto_off_callback = None

    def set_auto_off_callback(self, callback):
        """연속 실패 시 호출할 콜백 (예: tray OFF 토글)."""
        self._auto_off_callback = callback

    def record_success(self):
        with self._lock:
            self._consecutive_failures = 0

    def record_failure(self, error_message: str = "") -> bool:
        """실패 기록. 자동 OFF 발동 시 True 반환."""
        with self._lock:
            self._consecutive_failures += 1
            logger.warning(
                "RPA failure #%d: %s", self._consecutive_failures, error_message
            )
            if self._consecutive_failures >= self._max_failures:
                logger.error(
                    "Consecutive failures (%d) reached limit, triggering auto-OFF",
                    self._consecutive_failures,
                )
                self._consecutive_failures = 0
                if self._auto_off_callback:
                    self._auto_off_callback()
                return True
            return False

    @property
    def failure_count(self) -> int:
        with self._lock:
            return self._consecutive_failures

    def reset(self):
        with self._lock:
            self._consecutive_failures = 0
