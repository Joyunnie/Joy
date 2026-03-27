"""처방전 텍스트 파싱. 정규식 기반으로 환자/처방의/약품 추출."""
import re
from dataclasses import dataclass, field


@dataclass
class ParsedDrug:
    name: str
    dosage: str | None = None       # "1정", "2.5mg"
    frequency: str | None = None    # "3", "3회"
    days: int | None = None         # 7
    total_quantity: float | None = None


@dataclass
class ParsedPrescription:
    patient_name: str | None = None
    patient_dob: str | None = None
    insurance_type: str | None = None
    prescriber_name: str | None = None
    prescriber_clinic: str | None = None
    prescription_date: str | None = None  # YYYY-MM-DD
    prescription_number: str | None = None
    drugs: list[ParsedDrug] = field(default_factory=list)


# 환자명
_PATIENT_NAME_RE = re.compile(
    r"(?:환자\s*(?:성명|이름|명)|성\s*명)\s*[:\s]\s*([가-힣]{2,5})"
)

# 생년월일 / 주민번호 앞 6자리
_PATIENT_DOB_RE = re.compile(
    r"(?:주민|생년월일|생\s*년)\s*[:\s]\s*(\d{6})"
)

# 보험유형
_INSURANCE_RE = re.compile(
    r"(?:보험|급여)\s*(?:유형|종류|구분)?\s*[:\s]\s*(건강보험|의료급여|산재|자동차|비급여|자비)",
)

# 처방의
_PRESCRIBER_RE = re.compile(
    r"(?:처방\s*(?:의|의사)|의사\s*(?:성명|명)?|담당\s*의)\s*[:\s]\s*([가-힣]{2,5})"
)

# 의료기관
_CLINIC_RE = re.compile(
    r"(?:의료기관|병원|의원|기관)\s*(?:명칭?)?\s*[:\s]\s*(.+)"
)

# 날짜: YYYY-MM-DD, YYYY.MM.DD, YYYYMMDD
_DATE_RE = re.compile(
    r"(?:처방일|발행일|날짜|일자)?\s*[:\s]?\s*"
    r"(20\d{2})[.\-/]?(0[1-9]|1[0-2])[.\-/]?(0[1-9]|[12]\d|3[01])"
)

# 교부번호 / 처방전 번호
_PRESCRIPTION_NO_RE = re.compile(
    r"(?:교부\s*번호|처방전?\s*번호|No\.?)\s*[:\s]\s*([A-Za-z0-9\-]+)",
    re.IGNORECASE,
)

# 약품 행: 약품명  투약량  횟수  일수 [총량]
_DRUG_RE = re.compile(
    r"^(.+?)\s{2,}(\d+(?:\.\d+)?\s*(?:정|캡슐|mg|ml|g|포|환|매|T|C)?)\s+"
    r"(\d+)\s*(?:회)?\s+"
    r"(\d+)\s*(?:일)?"
    r"(?:\s+(\d+(?:\.\d+)?))?"  # 총량 (optional)
)

# 헤더 행 감지 (무시)
_HEADER_RE = re.compile(
    r"약품명|품목명|1회투약|투약량|투약횟수|투약일수|총투약|횟수|일수|^-+$",
    re.IGNORECASE,
)


def _parse_float(s: str) -> float | None:
    try:
        return float(s.replace(",", ""))
    except (ValueError, TypeError):
        return None


def _parse_int(s: str) -> int | None:
    try:
        return int(s.replace(",", ""))
    except (ValueError, TypeError):
        return None


def parse_prescription_text(raw_text: str) -> ParsedPrescription:
    """OCR raw_text를 파싱하여 구조화된 처방전 데이터를 반환."""
    result = ParsedPrescription()
    lines = raw_text.split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 환자명
        if result.patient_name is None:
            m = _PATIENT_NAME_RE.search(line)
            if m:
                result.patient_name = m.group(1).strip()
                continue

        # 생년월일
        if result.patient_dob is None:
            m = _PATIENT_DOB_RE.search(line)
            if m:
                result.patient_dob = m.group(1).strip()
                continue

        # 보험유형
        if result.insurance_type is None:
            m = _INSURANCE_RE.search(line)
            if m:
                result.insurance_type = m.group(1).strip()
                continue

        # 처방의
        if result.prescriber_name is None:
            m = _PRESCRIBER_RE.search(line)
            if m:
                result.prescriber_name = m.group(1).strip()
                continue

        # 의료기관
        if result.prescriber_clinic is None:
            m = _CLINIC_RE.search(line)
            if m:
                result.prescriber_clinic = m.group(1).strip()
                continue

        # 날짜
        if result.prescription_date is None:
            m = _DATE_RE.search(line)
            if m:
                result.prescription_date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
                continue

        # 교부번호
        if result.prescription_number is None:
            m = _PRESCRIPTION_NO_RE.search(line)
            if m:
                result.prescription_number = m.group(1).strip()
                continue

        # 헤더/구분선 무시
        if _HEADER_RE.search(line):
            continue

        # 약품 행
        m = _DRUG_RE.match(line)
        if m:
            name = m.group(1).strip()
            dosage = m.group(2).strip()
            frequency = m.group(3).strip()
            days = _parse_int(m.group(4))
            total_str = m.group(5)
            total_quantity = _parse_float(total_str) if total_str else None

            # total_quantity 자동 계산 (파싱 실패 시)
            if total_quantity is None and days:
                dosage_num = _parse_float(re.sub(r"[^\d.]", "", dosage))
                freq_num = _parse_float(frequency)
                if dosage_num and freq_num:
                    total_quantity = dosage_num * freq_num * days

            result.drugs.append(ParsedDrug(
                name=name,
                dosage=dosage,
                frequency=frequency,
                days=days,
                total_quantity=total_quantity,
            ))

    return result
