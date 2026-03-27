"""처방전 파서 단위 테스트."""
from app.services.prescription_parser import parse_prescription_text


def test_parse_full_prescription():
    """전체 처방전 파싱: 환자+처방의+약품."""
    text = (
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
    result = parse_prescription_text(text)

    assert result.patient_name == "홍길동"
    assert result.patient_dob == "900101"
    assert result.insurance_type == "건강보험"
    assert result.prescriber_name == "김의사"
    assert result.prescriber_clinic == "서울내과의원"
    assert result.prescription_date == "2026-03-27"
    assert result.prescription_number == "RX-20260327-001"

    assert len(result.drugs) == 2
    assert result.drugs[0].name == "아모시실린캡슐250mg"
    assert result.drugs[0].dosage == "1정"
    assert result.drugs[0].frequency == "3"
    assert result.drugs[0].days == 7
    assert result.drugs[0].total_quantity == 21.0  # 1 * 3 * 7

    assert result.drugs[1].name == "타이레놀정500mg"
    assert result.drugs[1].dosage == "2정"
    assert result.drugs[1].total_quantity == 42.0  # 2 * 3 * 7


def test_parse_various_dosage_formats():
    """다양한 투약량 형식."""
    text = (
        "약품명                 1회투약량  1일투약횟수  총투약일수\n"
        "가스모틴정5mg          1정       3           7\n"
        "아목시실린캡슐         2캡슐     2           5\n"
    )
    result = parse_prescription_text(text)

    assert len(result.drugs) == 2
    assert result.drugs[0].dosage == "1정"
    assert result.drugs[1].dosage == "2캡슐"
    assert result.drugs[1].frequency == "2"
    assert result.drugs[1].days == 5


def test_parse_drugs_only():
    """약품만 있고 환자정보 없는 텍스트."""
    text = (
        "아모시실린캡슐250mg    1정       3           7\n"
    )
    result = parse_prescription_text(text)

    assert result.patient_name is None
    assert result.prescriber_name is None
    assert len(result.drugs) == 1
    assert result.drugs[0].name == "아모시실린캡슐250mg"


def test_parse_empty_text():
    """빈 텍스트."""
    result = parse_prescription_text("")
    assert result.patient_name is None
    assert result.drugs == []


def test_parse_with_total_quantity():
    """총투약량이 명시된 경우."""
    text = (
        "아모시실린캡슐250mg    1정       3           7  21\n"
    )
    result = parse_prescription_text(text)
    assert len(result.drugs) == 1
    assert result.drugs[0].total_quantity == 21.0
