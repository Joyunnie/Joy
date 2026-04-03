from __future__ import annotations

"""윈도우 찾기/포커스 유틸리티 (pygetwindow 래핑)."""

import logging
import time

logger = logging.getLogger("agent1.rpa.window")


def find_window_by_title(title_keyword: str, timeout: float = 5.0):
    """창 제목에 keyword가 포함된 윈도우를 찾아 반환. 없으면 None."""
    try:
        import pygetwindow as gw
    except ImportError:
        logger.error("pygetwindow not installed")
        return None

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        windows = gw.getWindowsWithTitle(title_keyword)
        if windows:
            return windows[0]
        time.sleep(0.3)
    return None


def activate_window(window) -> bool:
    """윈도우를 포그라운드로 활성화."""
    try:
        if window.isMinimized:
            window.restore()
        window.activate()
        time.sleep(0.3)
        return True
    except Exception as e:
        logger.error("Failed to activate window: %s", e)
        return False


def is_window_visible(title_keyword: str) -> bool:
    """특정 제목의 창이 현재 보이는지 확인."""
    try:
        import pygetwindow as gw
    except ImportError:
        return False
    windows = gw.getWindowsWithTitle(title_keyword)
    return len(windows) > 0
