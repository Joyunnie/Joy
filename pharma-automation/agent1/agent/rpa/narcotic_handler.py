from __future__ import annotations

"""P34 / Phase 5B: 마약류 조제 보고 RPA 핸들러.

흐름:
  1) 마약류 조제 보고 팝업 감지 (창 제목 기반)
     - 참고: F2로 처방조제 화면을 열 필요 없음. 굿팜 OFF 여부는 약사가 수동 확인.
  2) 재고 목록에서 위→아래 순서로 더블클릭 (조제수량 = 사용수량 될 때까지)
  3) "완료" 버튼 클릭
  4) [선택] 질병기호 팝업 → "계속 진행" 클릭
  5) [선택] DUR 처방검토 화면 → F12 전송.
     사유 선택이 필요한 약품이 있으면: 해당 행 클릭 → A 체크 → 확인. 여러 약품이면 각각 반복.
  6) [선택] 운전 경고 팝업 → Enter (법 개정으로 추가, 마약류 외 약품에도 뜰 수 있음)
  7) [선택, 약품 7종 이상] 수납 화면 → ESC 키
  8) [선택, 약품 7종 이상] 봉투 약품 선택 화면 → 가운데 버튼 클릭

각 선택 단계는 1초 대기 후 화면 감지 → 없으면 스킵.
"""

import logging
import time

from agent1.agent.rpa import input_utils, window_utils
from agent1.agent.rpa.failsafe import FailsafeManager

logger = logging.getLogger("agent1.rpa.narcotic")

# 창 제목 키워드
NARCOTICS_REPORT_TITLE = "마약류"
DISEASE_CODE_POPUP_TITLE = "질병"
DUR_REVIEW_TITLE = "DUR"
DRIVING_WARNING_TITLE = "운전"
PAYMENT_SCREEN_TITLE = "수납"
BAG_SELECTION_TITLE = "봉투"

# 약품 7종 이상일 때만 결제/봉투 화면이 뜸
MULTI_DRUG_THRESHOLD = 7

# 좌표 설정 (PM+20 마약류 조제 보고 화면 기준)
# 실제 환경에서 config로 오버라이드 가능
INVENTORY_LIST_START_X = 200
INVENTORY_LIST_START_Y = 150
INVENTORY_LIST_ROW_HEIGHT = 22
COMPLETE_BUTTON_X = 400
COMPLETE_BUTTON_Y = 450
CONTINUE_BUTTON_X = 300
CONTINUE_BUTTON_Y = 350

# DUR 처방검토 화면 좌표
DUR_DRUG_ROW_START_X = 150
DUR_DRUG_ROW_START_Y = 200
DUR_DRUG_ROW_HEIGHT = 22
DUR_CHECKBOX_A_X = 350
DUR_CONFIRM_BUTTON_X = 450
DUR_CONFIRM_BUTTON_Y = 500

# 봉투 약품 선택 화면 - 가운데 버튼
BAG_MIDDLE_BUTTON_X = 400
BAG_MIDDLE_BUTTON_Y = 350

STEP_TIMEOUT = 30.0  # 각 단계 타임아웃
OPTIONAL_WAIT = 1.0  # 선택적 팝업 대기 시간


class NarcoticHandler:
    def __init__(self, failsafe: FailsafeManager, coordinates: dict | None = None):
        self.failsafe = failsafe
        self._coords = coordinates or {}

    def _get(self, key: str, default: int) -> int:
        return self._coords.get(key, default)

    def execute(self, payload: dict) -> tuple[bool, str]:
        """마약류 조제 보고 전체 흐름 실행.

        Returns:
            (success: bool, message: str)
        """
        try:
            drug_count = len(payload.get("drugs", [])) or payload.get("drug_count", 1)

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

            # Step 4: [선택] 질병기호 팝업 → 계속 진행
            logger.info("Step 4: 질병기호 팝업 확인")
            self._step4_handle_disease_code_popup()

            # Step 5: [선택] DUR 처방검토 화면 → F12
            logger.info("Step 5: DUR 처방검토 화면 확인")
            self._step5_handle_dur_review(drug_count)

            # Step 6: [선택] 운전 경고 팝업 → Enter
            logger.info("Step 6: 운전 경고 팝업 확인")
            self._step6_handle_driving_warning()

            # Step 7: [선택, 7종 이상] 수납 화면 → ESC
            if drug_count >= MULTI_DRUG_THRESHOLD:
                logger.info("Step 7: 수납 화면 확인 (약품 %d종)", drug_count)
                self._step7_handle_payment_screen()

            # Step 8: [선택, 7종 이상] 봉투 약품 선택 화면 → 가운데 버튼
            if drug_count >= MULTI_DRUG_THRESHOLD:
                logger.info("Step 8: 봉투 약품 선택 화면 확인 (약품 %d종)", drug_count)
                self._step8_handle_bag_selection()

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
        """[선택] 질병기호 팝업 감지 → '계속 진행' 클릭.

        1초 대기 후 팝업이 없으면 스킵.
        """
        time.sleep(OPTIONAL_WAIT)
        if not window_utils.is_window_visible(DISEASE_CODE_POPUP_TITLE):
            logger.debug("질병기호 팝업 없음 → 스킵")
            return

        logger.info("질병기호 팝업 감지 → 계속 진행 클릭")
        window = window_utils.find_window_by_title(DISEASE_CODE_POPUP_TITLE, timeout=2.0)
        if window:
            window_utils.activate_window(window)
        x = self._get("continue_button_x", CONTINUE_BUTTON_X)
        y = self._get("continue_button_y", CONTINUE_BUTTON_Y)
        input_utils.click(x, y)
        time.sleep(0.5)

    def _step5_handle_dur_review(self, drug_count: int):
        """[선택] DUR 처방검토 화면 → F12 전송.

        사유 선택이 필요한 약품이 있으면:
          - 해당 약품 행 클릭 → A 체크박스 클릭 → 확인 버튼 클릭
          - 여러 약품이면 각각 반복 (최대 drug_count 회)
        1초 대기 후 화면이 없으면 스킵.
        """
        time.sleep(OPTIONAL_WAIT)
        if not window_utils.is_window_visible(DUR_REVIEW_TITLE):
            logger.debug("DUR 처방검토 화면 없음 → 스킵")
            return

        logger.info("DUR 처방검토 화면 감지 → F12 전송")
        window = window_utils.find_window_by_title(DUR_REVIEW_TITLE, timeout=2.0)
        if window:
            window_utils.activate_window(window)

        input_utils.press_key("f12")
        time.sleep(1.0)

        # 사유 선택 화면이 뜨는 경우 처리 (약품별 반복)
        max_attempts = max(drug_count, 1)
        for attempt in range(max_attempts):
            if not window_utils.is_window_visible(DUR_REVIEW_TITLE):
                break

            logger.info("DUR 사유 선택 처리 (%d/%d)", attempt + 1, max_attempts)
            row_x = self._get("dur_drug_row_x", DUR_DRUG_ROW_START_X)
            row_y = (
                self._get("dur_drug_row_y", DUR_DRUG_ROW_START_Y)
                + attempt * self._get("dur_row_height", DUR_DRUG_ROW_HEIGHT)
            )
            # 약품 행 클릭
            input_utils.click(row_x, row_y)
            time.sleep(0.3)

            # A 체크박스 클릭
            checkbox_x = self._get("dur_checkbox_a_x", DUR_CHECKBOX_A_X)
            input_utils.click(checkbox_x, row_y)
            time.sleep(0.3)

            # 확인 버튼 클릭
            confirm_x = self._get("dur_confirm_button_x", DUR_CONFIRM_BUTTON_X)
            confirm_y = self._get("dur_confirm_button_y", DUR_CONFIRM_BUTTON_Y)
            input_utils.click(confirm_x, confirm_y)
            time.sleep(0.5)

        logger.info("DUR 처방검토 처리 완료")

    def _step6_handle_driving_warning(self):
        """[선택] 운전 경고 팝업 감지 → Enter 키 전송.

        법 개정으로 추가된 단계. 마약류 외 약품에도 뜰 수 있음.
        1초 대기 후 팝업이 없으면 스킵.
        """
        time.sleep(OPTIONAL_WAIT)
        if not window_utils.is_window_visible(DRIVING_WARNING_TITLE):
            logger.debug("운전 경고 팝업 없음 → 스킵")
            return

        logger.info("운전 경고 팝업 감지 → Enter 전송")
        window = window_utils.find_window_by_title(DRIVING_WARNING_TITLE, timeout=2.0)
        if window:
            window_utils.activate_window(window)
        input_utils.press_key("enter")
        time.sleep(0.5)

    def _step7_handle_payment_screen(self):
        """[선택, 약품 7종 이상] 수납 화면 감지 → ESC 키 전송.

        1초 대기 후 화면이 없으면 스킵.
        """
        time.sleep(OPTIONAL_WAIT)
        if not window_utils.is_window_visible(PAYMENT_SCREEN_TITLE):
            logger.debug("결제 화면 없음 → 스킵")
            return

        logger.info("결제 화면 감지 → ESC 전송")
        window = window_utils.find_window_by_title(PAYMENT_SCREEN_TITLE, timeout=2.0)
        if window:
            window_utils.activate_window(window)
        input_utils.press_key("escape")
        time.sleep(0.5)

    def _step8_handle_bag_selection(self):
        """[선택, 약품 7종 이상] 봉투 약품 선택 화면 감지 → 가운데 버튼 클릭.

        1초 대기 후 화면이 없으면 스킵.
        가운데 버튼 = "자동 선택" 류 버튼 (정확한 텍스트는 추후 확인).
        """
        time.sleep(OPTIONAL_WAIT)
        if not window_utils.is_window_visible(BAG_SELECTION_TITLE):
            logger.debug("봉투 약품 선택 화면 없음 → 스킵")
            return

        logger.info("봉투 약품 선택 화면 감지 → 가운데 버튼 클릭")
        window = window_utils.find_window_by_title(BAG_SELECTION_TITLE, timeout=2.0)
        if window:
            window_utils.activate_window(window)
        x = self._get("bag_middle_button_x", BAG_MIDDLE_BUTTON_X)
        y = self._get("bag_middle_button_y", BAG_MIDDLE_BUTTON_Y)
        input_utils.click(x, y)
        time.sleep(0.5)
