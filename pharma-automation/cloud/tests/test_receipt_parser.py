"""영수증 텍스트 파싱 단위 테스트."""
from app.services.receipt_parser import parse_receipt_text


def test_parse_full_receipt():
    """정상 영수증: 거래처/날짜/번호/품목/총액 추출."""
    text = (
        "거래처: 대한제약\n"
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
    result = parse_receipt_text(text)

    assert result.supplier_name == "대한제약"
    assert result.receipt_date == "2026-03-27"
    assert result.receipt_number == "R-20260327-001"
    assert result.total_amount == 60000
    assert len(result.items) == 2
    assert result.items[0].name == "아모시실린캡슐250mg"
    assert result.items[0].quantity == 10
    assert result.items[0].unit_price == 3000
    assert result.items[1].name == "타이레놀정500mg"
    assert result.items[1].quantity == 20


def test_parse_dotted_date():
    """날짜 구분자 '.' 처리."""
    text = "날짜: 2026.03.27\n합계: 10000\n"
    result = parse_receipt_text(text)
    assert result.receipt_date == "2026-03-27"
    assert result.total_amount == 10000


def test_parse_incomplete_text():
    """불완전한 텍스트: 거래처/날짜 없이 품목만 있는 경우."""
    text = "아모시실린캡슐250mg  5  2000   10000\n"
    result = parse_receipt_text(text)
    assert result.supplier_name is None
    assert result.receipt_date is None
    assert len(result.items) == 1
    assert result.items[0].name == "아모시실린캡슐250mg"
    assert result.items[0].quantity == 5


def test_parse_empty_text():
    """빈 텍스트."""
    result = parse_receipt_text("")
    assert result.supplier_name is None
    assert result.receipt_date is None
    assert result.items == []


def test_parse_comma_in_amounts():
    """금액에 콤마가 포함된 경우."""
    text = "합계: 1,250,000\n"
    result = parse_receipt_text(text)
    assert result.total_amount == 1250000
