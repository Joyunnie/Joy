"""처방전 OCR API 테스트."""
import io

import pytest
from httpx import AsyncClient

from app.services.ocr_engine import MockOcrEngine, init_ocr_engine


@pytest.fixture(autouse=True)
def setup_mock_prescription_ocr():
    """모든 테스트에서 처방전 MockOcrEngine 사용."""
    mock_text = MockOcrEngine.default_prescription_text()
    init_ocr_engine("mock")
    # Replace engine with prescription-specific mock
    import app.services.ocr_engine as ocr_mod
    ocr_mod._engine_instance = MockOcrEngine(mock_text)
    yield


# --- cleanup ---


@pytest.fixture(autouse=True)
async def cleanup_prescription_data(seed_data):
    """테스트 후 prescription 데이터 정리."""
    from tests.conftest import seed_session_factory
    from app.models.tables import PrescriptionOcrDrug, PrescriptionOcrRecord

    yield
    async with seed_session_factory() as db:
        pharmacy_id = seed_data["pharmacy_id"]
        from sqlalchemy import select
        records = await db.execute(
            select(PrescriptionOcrRecord.id).where(
                PrescriptionOcrRecord.pharmacy_id == pharmacy_id
            )
        )
        record_ids = [r[0] for r in records.all()]
        if record_ids:
            await db.execute(
                PrescriptionOcrDrug.__table__.delete().where(
                    PrescriptionOcrDrug.record_id.in_(record_ids)
                )
            )
            await db.execute(
                PrescriptionOcrRecord.__table__.delete().where(
                    PrescriptionOcrRecord.pharmacy_id == pharmacy_id
                )
            )
        await db.commit()


def _make_jpeg_bytes() -> bytes:
    return b"\xff\xd8\xff\xe0" + b"\x00" * 100


# --- Upload Tests ---


@pytest.mark.asyncio
async def test_upload_success(client: AsyncClient, auth_headers: dict, seed_data: dict):
    """POST upload: 정상 업로드 (mock OCR)."""
    resp = await client.post(
        "/api/v1/prescription-ocr/upload",
        headers=auth_headers,
        files={"file": ("test.jpg", io.BytesIO(_make_jpeg_bytes()), "image/jpeg")},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["record"]["ocr_status"] == "COMPLETED"
    assert body["record"]["patient_name"] == "홍길동"
    assert body["record"]["prescriber_name"] == "김의사"
    assert body["record"]["prescription_number"] == "RX-20260327-001"
    assert len(body["drugs"]) >= 1


@pytest.mark.asyncio
async def test_upload_unsupported_type(client: AsyncClient, auth_headers: dict, seed_data: dict):
    """POST upload: 지원하지 않는 파일 형식."""
    resp = await client.post(
        "/api/v1/prescription-ocr/upload",
        headers=auth_headers,
        files={"file": ("test.gif", io.BytesIO(b"GIF89a"), "image/gif")},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_prescriptions(client: AsyncClient, auth_headers: dict, seed_data: dict):
    """GET 목록."""
    await client.post(
        "/api/v1/prescription-ocr/upload",
        headers=auth_headers,
        files={"file": ("test.jpg", io.BytesIO(_make_jpeg_bytes()), "image/jpeg")},
    )
    resp = await client.get("/api/v1/prescription-ocr", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1


@pytest.mark.asyncio
async def test_list_filter_by_status(client: AsyncClient, auth_headers: dict, seed_data: dict):
    """GET 목록: 상태 필터."""
    await client.post(
        "/api/v1/prescription-ocr/upload",
        headers=auth_headers,
        files={"file": ("test.jpg", io.BytesIO(_make_jpeg_bytes()), "image/jpeg")},
    )
    resp = await client.get("/api/v1/prescription-ocr?status=COMPLETED", headers=auth_headers)
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["ocr_status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_get_detail(client: AsyncClient, auth_headers: dict, seed_data: dict):
    """GET 상세: drugs 포함."""
    upload_resp = await client.post(
        "/api/v1/prescription-ocr/upload",
        headers=auth_headers,
        files={"file": ("test.jpg", io.BytesIO(_make_jpeg_bytes()), "image/jpeg")},
    )
    record_id = upload_resp.json()["record"]["id"]

    resp = await client.get(f"/api/v1/prescription-ocr/{record_id}", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["record"]["id"] == record_id
    assert "drugs" in body
    assert body["raw_text"] is not None


@pytest.mark.asyncio
async def test_update_drug(client: AsyncClient, auth_headers: dict, seed_data: dict):
    """PUT drug 수정."""
    upload_resp = await client.post(
        "/api/v1/prescription-ocr/upload",
        headers=auth_headers,
        files={"file": ("test.jpg", io.BytesIO(_make_jpeg_bytes()), "image/jpeg")},
    )
    record_id = upload_resp.json()["record"]["id"]
    drugs = upload_resp.json()["drugs"]
    if not drugs:
        pytest.skip("No drugs parsed")

    drug_item_id = drugs[0]["id"]
    resp = await client.put(
        f"/api/v1/prescription-ocr/{record_id}/drugs/{drug_item_id}",
        headers=auth_headers,
        json={"dosage": "2정", "frequency": "2", "days": 5},
    )
    assert resp.status_code == 200
    assert resp.json()["confirmed_dosage"] == "2정"
    assert resp.json()["confirmed_frequency"] == "2"
    assert resp.json()["confirmed_days"] == 5
    assert resp.json()["is_confirmed"] is True


@pytest.mark.asyncio
async def test_confirm_with_unconfirmed(client: AsyncClient, auth_headers: dict, seed_data: dict):
    """POST confirm: 미확인 항목 있으면 422."""
    upload_resp = await client.post(
        "/api/v1/prescription-ocr/upload",
        headers=auth_headers,
        files={"file": ("test.jpg", io.BytesIO(_make_jpeg_bytes()), "image/jpeg")},
    )
    record_id = upload_resp.json()["record"]["id"]

    resp = await client.post(
        f"/api/v1/prescription-ocr/{record_id}/confirm",
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_confirm_success(client: AsyncClient, auth_headers: dict, seed_data: dict):
    """POST confirm: 모든 항목 확인 후 성공."""
    upload_resp = await client.post(
        "/api/v1/prescription-ocr/upload",
        headers=auth_headers,
        files={"file": ("test.jpg", io.BytesIO(_make_jpeg_bytes()), "image/jpeg")},
    )
    record_id = upload_resp.json()["record"]["id"]
    drugs = upload_resp.json()["drugs"]

    # 모든 항목 확인
    for drug in drugs:
        drug_id = drug["drug_id"]
        if drug_id:
            await client.put(
                f"/api/v1/prescription-ocr/{record_id}/drugs/{drug['id']}",
                headers=auth_headers,
                json={"drug_id": drug_id},
            )
        else:
            await client.put(
                f"/api/v1/prescription-ocr/{record_id}/drugs/{drug['id']}",
                headers=auth_headers,
                json={"dosage": drug.get("dosage", "1정")},
            )

    resp = await client.post(
        f"/api/v1/prescription-ocr/{record_id}/confirm",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["confirmed_count"] >= 1

    # 상태 확인
    detail = await client.get(f"/api/v1/prescription-ocr/{record_id}", headers=auth_headers)
    assert detail.json()["record"]["ocr_status"] == "CONFIRMED"


@pytest.mark.asyncio
async def test_duplicate_detection(client: AsyncClient, auth_headers: dict, seed_data: dict):
    """POST upload: 중복 감지 (동일 교부번호)."""
    # First upload
    await client.post(
        "/api/v1/prescription-ocr/upload",
        headers=auth_headers,
        files={"file": ("test1.jpg", io.BytesIO(_make_jpeg_bytes()), "image/jpeg")},
    )

    # Second upload (same mock → same prescription_number)
    resp = await client.post(
        "/api/v1/prescription-ocr/upload",
        headers=auth_headers,
        files={"file": ("test2.jpg", io.BytesIO(_make_jpeg_bytes()), "image/jpeg")},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["duplicate_warning"] is not None
    assert "교부번호" in body["duplicate_warning"]


@pytest.mark.asyncio
async def test_cancel_prescription(client: AsyncClient, auth_headers: dict, seed_data: dict):
    """DELETE: 취소 처리."""
    upload_resp = await client.post(
        "/api/v1/prescription-ocr/upload",
        headers=auth_headers,
        files={"file": ("test.jpg", io.BytesIO(_make_jpeg_bytes()), "image/jpeg")},
    )
    record_id = upload_resp.json()["record"]["id"]

    resp = await client.delete(f"/api/v1/prescription-ocr/{record_id}", headers=auth_headers)
    assert resp.status_code == 204

    detail = await client.get(f"/api/v1/prescription-ocr/{record_id}", headers=auth_headers)
    assert detail.json()["record"]["ocr_status"] == "CANCELLED"
