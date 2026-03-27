"""PM+20 창 제어: 찾기, 활성화, 메뉴 이동."""

import logging
import time

from agent1.agent.rpa import input_utils, window_utils

logger = logging.getLogger("agent1.rpa.pm20")

PM20_TITLE_KEYWORD = "PM"
PRESCRIPTION_MENU_TITLE = "처방조제"
NARCOTICS_POPUP_TITLE = "마약류"


class PM20Controller:
    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    def find_and_activate(self) -> bool:
        """PM+20 메인 윈도우를 찾고 활성화."""
        window = window_utils.find_window_by_title(PM20_TITLE_KEYWORD, self.timeout)
        if not window:
            logger.error("PM+20 window not found (timeout=%.1fs)", self.timeout)
            return False
        return window_utils.activate_window(window)

    def navigate_to_prescription(self) -> bool:
        """조제판매 → 처방조제 메뉴 이동.

        P36: PM+20 처방조제 화면이 닫혀 있으면 자동 메뉴 이동.
        """
        if window_utils.is_window_visible(PRESCRIPTION_MENU_TITLE):
            logger.info("처방조제 화면 already visible")
            return True

        if not self.find_and_activate():
            return False

        # 조제판매 메뉴 단축키: Alt+D (조제판매) → P (처방조제)
        logger.info("Navigating to 조제판매 → 처방조제")
        input_utils.hotkey("alt", "d")
        time.sleep(0.5)
        input_utils.press_key("p")
        time.sleep(1.0)

        # 처방조제 창 확인
        if window_utils.is_window_visible(PRESCRIPTION_MENU_TITLE):
            logger.info("처방조제 화면 opened successfully")
            return True

        logger.error("처방조제 화면 failed to open")
        return False

    def detect_narcotics_popup(self, timeout: float = 3.0) -> bool:
        """마약류 조제 보고 팝업 감지."""
        window = window_utils.find_window_by_title(NARCOTICS_POPUP_TITLE, timeout)
        return window is not None

    def detect_popup_by_title(self, title_keyword: str, timeout: float = 3.0) -> bool:
        """특정 팝업 감지."""
        window = window_utils.find_window_by_title(title_keyword, timeout)
        return window is not None

    def close_popup_with_esc(self):
        """현재 활성 팝업을 ESC로 닫기."""
        input_utils.press_key("escape")
        time.sleep(0.3)
