"""P34: 마약류 조제 보고 RPA 핸들러.

흐름:
  1) 마약류 조제 보고 팝업 감지 (창 제목 기반)
  2) 재고 목록에서 위→아래 순서로 더블클릭 (조제수량 = 사용수량 될 때까지)
  3) "완료" 버튼 클릭
  4) 질병기호 팝업 감지 → "계속 진행" 클릭
  5) 금액 초과 화면 감지 → ESC 키 전송
"""

import logging
import time

from agent1.agent.rpa import input_utils, window_utils
from agent1.agent.rpa.failsafe import FailsafeManager

logger = logging.getLogger("agent1.rpa.narcotic")

# 창 제목 키워드
NARCOTICS_REPORT_TITLE = "마약류"
DISEASE_CODE_POPUP_TITLE = "질병"
PRICE_EXCEED_TITLE = "금액"

# 좌표 설정 (PM+20 마약류 조제 보고 화면 기준)
# 실제 환경에서 config로 오버라이드 가능
INVENTORY_LIST_START_X = 200
INVENTORY_LIST_START_Y = 150
INVENTORY_LIST_ROW_HEIGHT = 22
COMPLETE_BUTTON_X = 400
COMPLETE_BUTTON_Y = 450
CONTINUE_BUTTON_X = 300
CONTINUE_BUTTON_Y = 350

STEP_TIMEOUT = 30.0  # 각 단계 타임아웃


class NarcoticHandler:
    def __init__(self, failsafe: FailsafeManager, coordinates: dict | None = None):
        self.failsafe = failsafe
        # 좌표 오버라이드
        if coordinates:
            self._coords = coordinates
        else:
            self._coords = {}

    def _get(self, key: str, default: int) -> int:
        return self._coords.get(key, default)

    def execute(self, payload: dict) -> tuple[bool, str]:
        """마약류 조제 보고 전체 흐름 실행.

        Returns:
            (success: bool, message: str)
        """
        try:
            # Step 1: 마약류 조제 보고 팝업 감지
            logger.info("Step 1: 마약류 조제 보고 팝업 감지")
            if not self._step1_detect_popup():
                return False, "마약류 조제 보고 팝업을 찾을 수 없습니다"

            # Step 2: 재고 목록에서 더블클릭
            logger.info("Step 2: 재고 목록 더블클릭")
            required_qty = payload.get("quantity", 1)
            if not self._step2_select_inventory(required_qty):
                return False, "재고 목록 선택 실패"

            # Step 3: 완료 버튼 클릭
            logger.info("Step 3: 완료 버튼 클릭")
            if not self._step3_click_complete():
                return False, "완료 버튼 클릭 실패"

            # Step 4: 질병기호 팝업 → 계속 진행
            logger.info("Step 4: 질병기호 팝업 처리")
            self._step4_handle_disease_code_popup()

            # Step 5: 금액 초과 → ESC
            logger.info("Step 5: 금액 초과 화면 처리")
            self._step5_handle_price_exceed()

            logger.info("마약류 조제 보고 완료")
            return True, "마약류 조제 보고 완료"

        except Exception as e:
            logger.error("마약류 조제 보고 실패: %s", e)
            return False, str(e)

    def _step1_detect_popup(self) -> bool:
        """마약류 조제 보고 팝업 감지."""
        window = window_utils.find_window_by_title(NARCOTICS_REPORT_TITLE, timeout=STEP_TIMEOUT)
        if not window:
            return False
        window_utils.activate_window(window)
        time.sleep(0.5)
        return True

    def _step2_select_inventory(self, required_qty: int) -> bool:
        """재고 목록에서 위→아래 순서로 더블클릭.

        조제수량이 사용수량이 될 때까지 복수 항목 클릭.
        각 더블클릭은 1단위씩 사용수량에 추가되는 것으로 가정.
        """
        start_x = self._get("inventory_list_x", INVENTORY_LIST_START_X)
        start_y = self._get("inventory_list_y", INVENTORY_LIST_START_Y)
        row_height = self._get("row_height", INVENTORY_LIST_ROW_HEIGHT)
        max_rows = self._get("max_rows", 20)

        clicks_done = 0
        row_idx = 0

        while clicks_done < required_qty and row_idx < max_rows:
            y = start_y + (row_idx * row_height)
            input_utils.double_click(start_x, y)
            time.sleep(0.3)
            clicks_done += 1
            row_idx += 1
            logger.debug("Double-clicked row %d (total: %d/%d)", row_idx, clicks_done, required_qty)

        if clicks_done < required_qty:
            logger.warning(
                "Only %d/%d items selected (max rows reached)", clicks_done, required_qty
            )
            return False

        logger.info("Selected %d inventory items", clicks_done)
        return True

    def _step3_click_complete(self) -> bool:
        """완료 버튼 클릭."""
        x = self._get("complete_button_x", COMPLETE_BUTTON_X)
        y = self._get("complete_button_y", COMPLETE_BUTTON_Y)
        input_utils.click(x, y)
        time.sleep(1.0)
        return True

    def _step4_handle_disease_code_popup(self):
        """질병기호 팝업 감지 → '계속 진행' 클릭."""
        if window_utils.is_window_visible(DISEASE_CODE_POPUP_TITLE):
            logger.info("질병기호 팝업 감지 → 계속 진행 클릭")
            window = window_utils.find_window_by_title(DISEASE_CODE_POPUP_TITLE, timeout=2.0)
            if window:
                window_utils.activate_window(window)
            x = self._get("continue_button_x", CONTINUE_BUTTON_X)
            y = self._get("continue_button_y", CONTINUE_BUTTON_Y)
            input_utils.click(x, y)
            time.sleep(0.5)

    def _step5_handle_price_exceed(self):
        """금액 초과 화면 감지 → ESC 키 전송."""
        if window_utils.is_window_visible(PRICE_EXCEED_TITLE):
            logger.info("금액 초과 화면 감지 → ESC 전송")
            input_utils.press_key("escape")
            time.sleep(0.5)
