"""영수증 텍스트 파싱. 정규식 기반으로 거래처/날짜/총액/품목 추출."""
import re
from dataclasses import dataclass, field


@dataclass
class ParsedItem:
    name: str
    quantity: int | None = None
    unit_price: int | None = None
    amount: int | None = None


@dataclass
class ParsedReceipt:
    supplier_name: str | None = None
    receipt_date: str | None = None  # YYYY-MM-DD 형식
    receipt_number: str | None = None
    total_amount: int | None = None
    items: list[ParsedItem] = field(default_factory=list)


# 거래처명 패턴: "거래처:", "상호:", "공급자:" 등
_SUPPLIER_RE = re.compile(
    r"(?:거래처|상호|공급자|업체명?)\s*[:\s]\s*(.+)", re.IGNORECASE
)

# 날짜 패턴: YYYY-MM-DD, YYYY.MM.DD, YYYY/MM/DD, YYYYMMDD
_DATE_RE = re.compile(
    r"(?:날짜|일자|거래일|작성일)?\s*[:\s]?\s*"
    r"(20\d{2})[.\-/]?(0[1-9]|1[0-2])[.\-/]?(0[1-9]|[12]\d|3[01])"
)

# 영수증 번호 패턴
_RECEIPT_NO_RE = re.compile(
    r"(?:번호|No\.?|영수증\s*(?:번호)?)\s*[:\s]\s*([A-Za-z0-9\-]+)", re.IGNORECASE
)

# 합계/총액 패턴
_TOTAL_RE = re.compile(
    r"(?:합계|총액|TOTAL|총\s*금액)\s*[:\s]?\s*([0-9,]+)", re.IGNORECASE
)

# 품목 행 패턴: 약품명 + 숫자들 (수량, 단가, 금액)
# 예: "아모시실린캡슐250mg  10  3,000  30,000"
_ITEM_RE = re.compile(
    r"^(.+?)\s{2,}(\d+)\s+([0-9,]+)\s+([0-9,]+)\s*$"
)

# 헤더 행 감지 (무시할 행)
_HEADER_RE = re.compile(
    r"품목명|품명|상품명|수량|단가|금액|합계|총액|거래처|날짜|번호|^-+$",
    re.IGNORECASE
)


def _parse_int(s: str) -> int | None:
    """콤마 제거 후 정수 변환."""
    try:
        return int(s.replace(",", ""))
    except (ValueError, TypeError):
        return None


def parse_receipt_text(raw_text: str) -> ParsedReceipt:
    """OCR raw_text를 파싱하여 구조화된 영수증 데이터를 반환."""
    result = ParsedReceipt()
    lines = raw_text.split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 거래처
        if result.supplier_name is None:
            m = _SUPPLIER_RE.search(line)
            if m:
                result.supplier_name = m.group(1).strip()
                continue

        # 날짜
        if result.receipt_date is None:
            m = _DATE_RE.search(line)
            if m:
                result.receipt_date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
                continue

        # 영수증 번호
        if result.receipt_number is None:
            m = _RECEIPT_NO_RE.search(line)
            if m:
                result.receipt_number = m.group(1).strip()
                continue

        # 합계
        if result.total_amount is None:
            m = _TOTAL_RE.search(line)
            if m:
                result.total_amount = _parse_int(m.group(1))
                continue

        # 헤더/구분선 무시
        if _HEADER_RE.search(line):
            continue

        # 품목 행
        m = _ITEM_RE.match(line)
        if m:
            name = m.group(1).strip()
            qty = _parse_int(m.group(2))
            price = _parse_int(m.group(3))
            amount = _parse_int(m.group(4))
            result.items.append(ParsedItem(
                name=name,
                quantity=qty,
                unit_price=price,
                amount=amount,
            ))

    return result
