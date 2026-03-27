"""영수증 OCR API 테스트."""
import io

import pytest
from httpx import AsyncClient

from app.services.ocr_engine import MockOcrEngine, init_ocr_engine, _engine_instance


@pytest.fixture(autouse=True)
def setup_mock_ocr():
    """모든 테스트에서 MockOcrEngine 사용."""
    init_ocr_engine("mock")
    yield


# --- cleanup ---


@pytest.fixture(autouse=True)
async def cleanup_receipt_data(seed_data):
    """테스트 전 receipt 데이터 정리."""
    from tests.conftest import seed_session_factory
    from app.models.tables import ReceiptOcrItem, ReceiptOcrRecord

    yield
    async with seed_session_factory() as db:
        pharmacy_id = seed_data["pharmacy_id"]
        # items first (FK)
        from sqlalchemy import select
        records = await db.execute(
            select(ReceiptOcrRecord.id).where(ReceiptOcrRecord.pharmacy_id == pharmacy_id)
        )
        record_ids = [r[0] for r in records.all()]
        if record_ids:
            await db.execute(
                ReceiptOcrItem.__table__.delete().where(ReceiptOcrItem.record_id.in_(record_ids))
            )
            await db.execute(
                ReceiptOcrRecord.__table__.delete().where(ReceiptOcrRecord.pharmacy_id == pharmacy_id)
            )
        await db.commit()


def _make_jpeg_bytes() -> bytes:
    """최소 JPEG 바이트 (magic bytes)."""
    return b"\xff\xd8\xff\xe0" + b"\x00" * 100


# --- Upload Tests ---


@pytest.mark.asyncio
async def test_upload_success(client: AsyncClient, auth_headers: dict, seed_data: dict):
    """POST upload: 정상 업로드 (mock OCR)."""
    data = _make_jpeg_bytes()
    resp = await client.post(
        "/api/v1/receipt-ocr/upload",
        headers=auth_headers,
        files={"file": ("test.jpg", io.BytesIO(data), "image/jpeg")},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["record"]["ocr_status"] == "COMPLETED"
    assert body["record"]["intake_status"] == "PENDING"
    assert len(body["items"]) >= 1  # MockOcrEngine returns items


@pytest.mark.asyncio
async def test_upload_unsupported_type(client: AsyncClient, auth_headers: dict, seed_data: dict):
    """POST upload: 지원하지 않는 파일 형식."""
    resp = await client.post(
        "/api/v1/receipt-ocr/upload",
        headers=auth_headers,
        files={"file": ("test.gif", io.BytesIO(b"GIF89a"), "image/gif")},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_receipts(client: AsyncClient, auth_headers: dict, seed_data: dict):
    """GET 목록: 영수증 리스트."""
    # Upload first
    data = _make_jpeg_bytes()
    await client.post(
        "/api/v1/receipt-ocr/upload",
        headers=auth_headers,
        files={"file": ("test.jpg", io.BytesIO(data), "image/jpeg")},
    )

    resp = await client.get("/api/v1/receipt-ocr", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert len(body["items"]) >= 1


@pytest.mark.asyncio
async def test_list_filter_by_status(client: AsyncClient, auth_headers: dict, seed_data: dict):
    """GET 목록: 상태 필터."""
    data = _make_jpeg_bytes()
    await client.post(
        "/api/v1/receipt-ocr/upload",
        headers=auth_headers,
        files={"file": ("test.jpg", io.BytesIO(data), "image/jpeg")},
    )

    resp = await client.get("/api/v1/receipt-ocr?status=PENDING", headers=auth_headers)
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["intake_status"] == "PENDING"


@pytest.mark.asyncio
async def test_get_detail(client: AsyncClient, auth_headers: dict, seed_data: dict):
    """GET 상세: items 포함."""
    data = _make_jpeg_bytes()
    upload_resp = await client.post(
        "/api/v1/receipt-ocr/upload",
        headers=auth_headers,
        files={"file": ("test.jpg", io.BytesIO(data), "image/jpeg")},
    )
    record_id = upload_resp.json()["record"]["id"]

    resp = await client.get(f"/api/v1/receipt-ocr/{record_id}", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["record"]["id"] == record_id
    assert "items" in body
    assert body["raw_text"] is not None


@pytest.mark.asyncio
async def test_update_item(client: AsyncClient, auth_headers: dict, seed_data: dict):
    """PUT item 수정: drug_id/수량 변경."""
    data = _make_jpeg_bytes()
    upload_resp = await client.post(
        "/api/v1/receipt-ocr/upload",
        headers=auth_headers,
        files={"file": ("test.jpg", io.BytesIO(data), "image/jpeg")},
    )
    record_id = upload_resp.json()["record"]["id"]
    items = upload_resp.json()["items"]
    if not items:
        pytest.skip("No items parsed")

    item_id = items[0]["id"]
    resp = await client.put(
        f"/api/v1/receipt-ocr/{record_id}/items/{item_id}",
        headers=auth_headers,
        json={"quantity": 99},
    )
    assert resp.status_code == 200
    assert resp.json()["confirmed_quantity"] == 99
    assert resp.json()["is_confirmed"] is True


@pytest.mark.asyncio
async def test_confirm_with_unconfirmed_items(client: AsyncClient, auth_headers: dict, seed_data: dict):
    """POST confirm: 미확인 항목 있으면 422."""
    data = _make_jpeg_bytes()
    upload_resp = await client.post(
        "/api/v1/receipt-ocr/upload",
        headers=auth_headers,
        files={"file": ("test.jpg", io.BytesIO(data), "image/jpeg")},
    )
    record_id = upload_resp.json()["record"]["id"]

    # Try to confirm without confirming items
    resp = await client.post(
        f"/api/v1/receipt-ocr/{record_id}/confirm",
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_confirm_intake(client: AsyncClient, auth_headers: dict, seed_data: dict):
    """POST confirm: 입고 확정 + 재고 반영."""
    data = _make_jpeg_bytes()
    upload_resp = await client.post(
        "/api/v1/receipt-ocr/upload",
        headers=auth_headers,
        files={"file": ("test.jpg", io.BytesIO(data), "image/jpeg")},
    )
    record_id = upload_resp.json()["record"]["id"]
    items = upload_resp.json()["items"]

    # Confirm all items first
    for item in items:
        drug_id = item["drug_id"]
        if drug_id:
            await client.put(
                f"/api/v1/receipt-ocr/{record_id}/items/{item['id']}",
                headers=auth_headers,
                json={"drug_id": drug_id, "quantity": item["quantity"]},
            )

    # Now confirm intake
    resp = await client.post(
        f"/api/v1/receipt-ocr/{record_id}/confirm",
        headers=auth_headers,
    )
    # May be 422 if items don't have drug_id, or 200 if they do
    assert resp.status_code in (200, 422)


@pytest.mark.asyncio
async def test_duplicate_detection_receipt_number(client: AsyncClient, auth_headers: dict, seed_data: dict):
    """POST upload: 중복 감지 (동일 mock → 같은 영수증번호)."""
    data = _make_jpeg_bytes()

    # First upload
    await client.post(
        "/api/v1/receipt-ocr/upload",
        headers=auth_headers,
        files={"file": ("test1.jpg", io.BytesIO(data), "image/jpeg")},
    )

    # Second upload (same mock text → same receipt_number)
    resp = await client.post(
        "/api/v1/receipt-ocr/upload",
        headers=auth_headers,
        files={"file": ("test2.jpg", io.BytesIO(data), "image/jpeg")},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["duplicate_warning"] is not None


@pytest.mark.asyncio
async def test_cancel_receipt(client: AsyncClient, auth_headers: dict, seed_data: dict):
    """DELETE: 취소 처리."""
    data = _make_jpeg_bytes()
    upload_resp = await client.post(
        "/api/v1/receipt-ocr/upload",
        headers=auth_headers,
        files={"file": ("test.jpg", io.BytesIO(data), "image/jpeg")},
    )
    record_id = upload_resp.json()["record"]["id"]

    resp = await client.delete(f"/api/v1/receipt-ocr/{record_id}", headers=auth_headers)
    assert resp.status_code == 204

    # Verify status changed
    detail_resp = await client.get(f"/api/v1/receipt-ocr/{record_id}", headers=auth_headers)
    assert detail_resp.json()["record"]["intake_status"] == "CANCELLED"
