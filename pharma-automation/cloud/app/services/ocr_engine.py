"""OCR 엔진 추상화. P32: config.ocr_engine 설정으로 엔진 선택."""
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class OcrEngine(ABC):
    @abstractmethod
    async def extract_text(self, image_bytes: bytes) -> str:
        ...


class GoogleVisionOcrEngine(OcrEngine):
    """Google Cloud Vision TEXT_DETECTION."""

    def __init__(self, api_key: str):
        self._api_key = api_key

    async def extract_text(self, image_bytes: bytes) -> str:
        import base64
        import httpx

        b64 = base64.b64encode(image_bytes).decode()
        payload = {
            "requests": [{
                "image": {"content": b64},
                "features": [{"type": "TEXT_DETECTION"}],
            }]
        }
        url = "https://vision.googleapis.com/v1/images:annotate"
        headers = {"x-goog-api-key": self._api_key}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()

        data = resp.json()
        responses = data.get("responses", [])
        if not responses:
            return ""
        annotations = responses[0].get("textAnnotations", [])
        if not annotations:
            return ""
        return annotations[0].get("description", "")


class MockOcrEngine(OcrEngine):
    """테스트/개발용 mock. 미리 정의된 텍스트 반환."""

    def __init__(self, mock_text: str | None = None):
        self._mock_text = mock_text or self._default_receipt_text()

    @staticmethod
    def _default_receipt_text() -> str:
        return (
            "거래처: 테스트제약\n"
            "날짜: 2026-03-27\n"
            "영수증번호: R-20260327-001\n"
            "-----------------------------------------\n"
            "품목명           수량  단가    금액\n"
            "-----------------------------------------\n"
            "아모시실린캡슐250mg  10  3000   30000\n"
            "타이레놀정500mg      20  1500   30000\n"
            "-----------------------------------------\n"
            "합계                               60000\n"
        )

    @staticmethod
    def default_prescription_text() -> str:
        return (
            "처방전\n"
            "환자 성명: 홍길동\n"
            "생년월일: 900101\n"
            "보험유형: 건강보험\n"
            "처방의: 김의사\n"
            "의료기관: 서울내과의원\n"
            "처방일: 2026-03-27\n"
            "교부번호: RX-20260327-001\n"
            "-----------------------------------------\n"
            "약품명                 1회투약량  1일투약횟수  총투약일수\n"
            "-----------------------------------------\n"
            "아모시실린캡슐250mg    1정       3           7\n"
            "타이레놀정500mg        2정       3           7\n"
        )

    async def extract_text(self, image_bytes: bytes) -> str:
        return self._mock_text


# --- 엔진 팩토리 ---


_engine_instance: OcrEngine | None = None


def get_ocr_engine() -> OcrEngine:
    """싱글톤 OCR 엔진 반환. 서버 시작 시 init_ocr_engine()으로 초기화."""
    if _engine_instance is None:
        raise RuntimeError("OCR engine not initialized. Call init_ocr_engine() first.")
    return _engine_instance


def init_ocr_engine(engine_type: str, api_key: str | None = None) -> None:
    """P32: config.ocr_engine 설정에 따라 OCR 엔진 초기화.

    - "google_vision": API 키 필수. 키 없으면 WARNING 로그 + 엔진 None 유지 (503 반환)
    - "mock": MockOcrEngine 사용.
    """
    global _engine_instance

    if engine_type == "mock":
        _engine_instance = MockOcrEngine()
        logger.info("OCR engine initialized: MockOcrEngine")
    elif engine_type == "google_vision":
        if not api_key:
            logger.warning(
                "PHARMA_GOOGLE_VISION_API_KEY not set. "
                "OCR endpoints will return 503 until configured."
            )
            _engine_instance = None
            return
        _engine_instance = GoogleVisionOcrEngine(api_key)
        logger.info("OCR engine initialized: GoogleVisionOcrEngine")
    else:
        logger.warning(f"Unknown OCR engine type: {engine_type}. Falling back to mock.")
        _engine_instance = MockOcrEngine()


def is_ocr_available() -> bool:
    """P32: OCR 엔진이 사용 가능한지 확인."""
    return _engine_instance is not None
