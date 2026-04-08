from __future__ import annotations

"""P36 / Phase 5B: 처방전 PM+20 입력 RPA 핸들러.

_ensure_prescription_screen()은 처방조제 창이 이미 열려 있으면 활성화만 하고,
닫혀 있으면 pm20.navigate_to_prescription()으로 자동 이동한다.
마약류 처리에는 처방조제 화면이 불필요하므로 NarcoticHandler에서는 호출하지 않는다.
F2 전송 로직은 Phase 5B에서 제거됨.
"""

import logging
import time

from agent1.agent.rpa import input_utils, window_utils
from agent1.agent.rpa.failsafe import FailsafeManager
from agent1.agent.rpa.pm20_controller import PM20Controller

logger = logging.getLogger("agent1.rpa.prescription")

PRESCRIPTION_TITLE = "처방조제"

# 좌표 설정 (PM+20 처방조제 화면 기준)
PATIENT_SEARCH_X = 200
PATIENT_SEARCH_Y = 60
DRUG_INPUT_X = 150
DRUG_INPUT_Y = 200
DRUG_ROW_HEIGHT = 22
DOSAGE_X = 350
FREQUENCY_X = 420
DAYS_X = 490
SAVE_BUTTON_X = 600
SAVE_BUTTON_Y = 500

# 선택적 팝업 창 제목 키워드
DUR_REVIEW_TITLE = "DUR"
DRIVING_WARNING_TITLE = "운전"
PAYMENT_SCREEN_TITLE = "수납"
BAG_SELECTION_TITLE = "봉투"

# DUR 처방검토 화면 좌표 (일괄적용 방식)
DUR_CHECKBOX_A_X = 350
DUR_CHECKBOX_A_Y = 400
DUR_BULK_APPLY_X = 500
DUR_BULK_APPLY_Y = 400

# 약품 7종 이상일 때만 결제/봉투 화면이 뜸
MULTI_DRUG_THRESHOLD = 7

STEP_TIMEOUT = 30.0
OPTIONAL_WAIT = 1.0


# 마약류에서는 이 핸들러를 호출하지 않음
class PrescriptionHandler:
    def __init__(
        self,
        failsafe: FailsafeManager,
        pm20_controller: PM20Controller,
        coordinates: dict | None = None,
    ):
        self.failsafe = failsafe
        self.pm20 = pm20_controller
        self._coords = coordinates or {}

    def _get(self, key: str, default: int) -> int:
        return self._coords.get(key, default)

    def execute(self, payload: dict) -> tuple[bool, str]:
        """처방전 PM+20 입력 전체 흐름.

        Returns:
            (success: bool, message: str)
        """
        try:
            # 처방조제 화면 확인/이동
            if not self._ensure_prescription_screen():
                return False, "처방조제 화면 이동 실패"

            # 환자 검색
            patient_name = payload.get("patient_name", "")
            patient_dob = payload.get("patient_dob", "")
            if not self._search_patient(patient_name, patient_dob):
                return False, f"환자 검색 실패: {patient_name}"

            # 약품 입력
            drugs = payload.get("drugs", [])
            if not drugs:
                return False, "입력할 약품이 없습니다"

            drug_count = len(drugs)
            for idx, drug in enumerate(drugs):
                if not self._input_drug(idx, drug):
                    return False, f"약품 입력 실패: {drug.get('drug_name', '?')}"

            # 저장
            if not self._save():
                return False, "저장 실패"

            # [선택] DUR 처방검토 화면 → 사유 A 일괄적용 → F12
            self._handle_dur_review()

            # [선택] 운전 경고 팝업 → Enter
            self._handle_driving_warning()

            # [선택, 7종 이상] 수납 화면 → ESC
            if drug_count >= MULTI_DRUG_THRESHOLD:
                self._handle_payment_screen()

            # [선택, 7종 이상] 봉투 약품 선택 화면 → Ctrl+2
            if drug_count >= MULTI_DRUG_THRESHOLD:
                self._handle_bag_selection()

            logger.info("처방전 입력 완료 (%d건)", drug_count)
            return True, f"처방전 입력 완료 ({drug_count}건)"

        except Exception as e:
            logger.error("처방전 입력 실패: %s", e)
            return False, str(e)

    def _ensure_prescription_screen(self) -> bool:
        """처방조제 화면 확인, 없으면 자동 이동.

        Phase 5B: F2 전송 로직 제거됨.
        마약류 처리(NarcoticHandler)에서는 이 메서드를 호출하지 않는다.
        처방전 입력(PRESCRIPTION_INPUT) 커맨드 전용.
        """
        if window_utils.is_window_visible(PRESCRIPTION_TITLE):
            window = window_utils.find_window_by_title(PRESCRIPTION_TITLE, timeout=2.0)
            if window:
                window_utils.activate_window(window)
            return True

        logger.info("처방조제 화면이 닫혀 있음 → 자동 메뉴 이동")
        return self.pm20.navigate_to_prescription()

    def _search_patient(self, name: str, dob: str) -> bool:
        """환자 검색 (이름 + 생년월일)."""
        x = self._get("patient_search_x", PATIENT_SEARCH_X)
        y = self._get("patient_search_y", PATIENT_SEARCH_Y)

        input_utils.click(x, y)
        time.sleep(0.3)

        # 기존 텍스트 지우고 환자명 입력
        input_utils.hotkey("ctrl", "a")
        search_text = name
        if dob:
            search_text = f"{name} {dob}"
        input_utils.type_text(search_text)
        time.sleep(0.3)
        input_utils.press_key("enter")
        time.sleep(1.0)

        # TODO: 검색 결과 확인 (이미지 매칭 또는 좌표 기반)
        logger.info("환자 검색 완료: %s", name)
        return True

    def _input_drug(self, idx: int, drug: dict) -> bool:
        """단일 약품 정보 입력."""
        drug_x = self._get("drug_input_x", DRUG_INPUT_X)
        drug_y = (
            self._get("drug_input_y", DRUG_INPUT_Y)
            + idx * self._get("drug_row_height", DRUG_ROW_HEIGHT)
        )

        # 약품명 입력
        input_utils.click(drug_x, drug_y)
        time.sleep(0.2)
        input_utils.type_text(drug.get("drug_name", ""))
        time.sleep(0.3)
        input_utils.press_key("enter")
        time.sleep(0.5)

        # 투약량 입력
        dosage = drug.get("dosage", "")
        if dosage:
            input_utils.press_key("tab")
            input_utils.type_text(dosage)

        # 횟수 입력
        frequency = drug.get("frequency", "")
        if frequency:
            input_utils.press_key("tab")
            input_utils.type_text(frequency)

        # 일수 입력
        days = drug.get("days")
        if days:
            input_utils.press_key("tab")
            input_utils.type_text(str(days))

        input_utils.press_key("enter")
        time.sleep(0.3)

        logger.debug("Drug #%d input: %s", idx + 1, drug.get("drug_name", ""))
        return True

    def _save(self) -> bool:
        """저장 버튼 클릭."""
        x = self._get("save_button_x", SAVE_BUTTON_X)
        y = self._get("save_button_y", SAVE_BUTTON_Y)
        input_utils.click(x, y)
        time.sleep(1.0)
        logger.info("저장 완료")
        return True

    def _handle_dur_review(self):
        """[선택] DUR 처방검토 화면 → 사유 A 일괄적용 → F12.

        1. 사유선택 섹션에서 A 체크박스 클릭
        2. "일괄적용" 버튼 클릭 (모든 약품에 사유 A 적용)
        3. F12 (확인)
        1초 대기 후 화면이 없으면 스킵.
        """
        time.sleep(OPTIONAL_WAIT)
        if not window_utils.is_window_visible(DUR_REVIEW_TITLE):
            logger.debug("DUR 처방검토 화면 없음 → 스킵")
            return

        logger.info("DUR 처방검토 화면 감지 → 일괄적용")
        window = window_utils.find_window_by_title(DUR_REVIEW_TITLE, timeout=2.0)
        if window:
            window_utils.activate_window(window)

        # 사유 A 체크박스 클릭
        checkbox_x = self._get("dur_checkbox_a_x", DUR_CHECKBOX_A_X)
        checkbox_y = self._get("dur_checkbox_a_y", DUR_CHECKBOX_A_Y)
        input_utils.click(checkbox_x, checkbox_y)
        time.sleep(0.3)

        # 일괄적용 버튼 클릭
        bulk_x = self._get("dur_bulk_apply_x", DUR_BULK_APPLY_X)
        bulk_y = self._get("dur_bulk_apply_y", DUR_BULK_APPLY_Y)
        input_utils.click(bulk_x, bulk_y)
        time.sleep(0.5)

        # F12 확인
        input_utils.press_key("f12")
        time.sleep(0.5)

        logger.info("DUR 처방검토 일괄적용 완료")

    def _handle_driving_warning(self):
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

    def _handle_payment_screen(self):
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

    def _handle_bag_selection(self):
        """[선택, 약품 7종 이상] 봉투 약품 선택 화면 감지 → Ctrl+2.

        Ctrl+2 = "자동(6품목)" 버튼 단축키. 팝업이 자동으로 닫힘.
        1초 대기 후 화면이 없으면 스킵.
        """
        time.sleep(OPTIONAL_WAIT)
        if not window_utils.is_window_visible(BAG_SELECTION_TITLE):
            logger.debug("봉투 약품 선택 화면 없음 → 스킵")
            return

        logger.info("봉투 약품 선택 화면 감지 → Ctrl+2 (자동 6품목)")
        window = window_utils.find_window_by_title(BAG_SELECTION_TITLE, timeout=2.0)
        if window:
            window_utils.activate_window(window)
        input_utils.hotkey("ctrl", "2")
        time.sleep(0.5)
