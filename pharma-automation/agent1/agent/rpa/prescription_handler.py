"""P36: 처방전 PM+20 입력 RPA 핸들러.

PM+20 처방조제 화면이 닫혀 있으면 자동으로
"조제판매 → 처방조제" 메뉴 이동 후 입력 시작.
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

STEP_TIMEOUT = 30.0


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
            # P36: 처방조제 화면 자동 이동
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

            for idx, drug in enumerate(drugs):
                if not self._input_drug(idx, drug):
                    return False, f"약품 입력 실패: {drug.get('drug_name', '?')}"

            # 저장
            if not self._save():
                return False, "저장 실패"

            logger.info("처방전 입력 완료 (%d건)", len(drugs))
            return True, f"처방전 입력 완료 ({len(drugs)}건)"

        except Exception as e:
            logger.error("처방전 입력 실패: %s", e)
            return False, str(e)

    def _ensure_prescription_screen(self) -> bool:
        """P36: 처방조제 화면 확인, 없으면 자동 이동."""
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
        drug_y = self._get("drug_input_y", DRUG_INPUT_Y) + (idx * self._get("drug_row_height", DRUG_ROW_HEIGHT))

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
