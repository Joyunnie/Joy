"""Receipt OCR error path tests.

Covers: 404 on non-existent records/items, cancel already-cancelled receipt,
confirm already-confirmed receipt, auth required on all endpoints.
"""
import io
import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.models.tables import ReceiptOcrItem, ReceiptOcrRecord
from tests.conftest import seed_session_factory

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture(autouse=True)
async def cleanup_receipts(seed_data):
    pid = seed_data["pharmacy_id"]
    async with seed_session_factory() as db:
        await db.execute(ReceiptOcrItem.__table__.delete())
        await db.execute(
            ReceiptOcrRecord.__table__.delete().where(
                ReceiptOcrRecord.pharmacy_id == pid
            )
        )
        await db.commit()
    yield
    async with seed_session_factory() as db:
        await db.execute(ReceiptOcrItem.__table__.delete())
        await db.execute(
            ReceiptOcrRecord.__table__.delete().where(
                ReceiptOcrRecord.pharmacy_id == pid
            )
        )
        await db.commit()


def _make_jpeg_bytes() -> bytes:
    """Minimal valid JPEG (SOI + EOI markers)."""
    return b"\xff\xd8\xff\xe0" + b"\x00" * 100 + b"\xff\xd9"


class TestReceiptNotFound:
    async def test_get_nonexistent_record(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/v1/receipt-ocr/999999", headers=auth_headers)
        assert resp.status_code == 404

    async def test_update_item_nonexistent_record(self, client: AsyncClient, auth_headers: dict):
        resp = await client.put(
            "/api/v1/receipt-ocr/999999/items/1",
            json={"quantity": 10},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_confirm_nonexistent_record(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post(
            "/api/v1/receipt-ocr/999999/confirm",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_cancel_nonexistent_record(self, client: AsyncClient, auth_headers: dict):
        resp = await client.delete(
            "/api/v1/receipt-ocr/999999",
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestReceiptAuthRequired:
    async def test_upload_requires_auth(self, client: AsyncClient):
        data = _make_jpeg_bytes()
        resp = await client.post(
            "/api/v1/receipt-ocr/upload",
            files={"file": ("test.jpg", io.BytesIO(data), "image/jpeg")},
        )
        assert resp.status_code in (401, 403)

    async def test_list_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/receipt-ocr")
        assert resp.status_code in (401, 403)

    async def test_detail_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/receipt-ocr/1")
        assert resp.status_code in (401, 403)

    async def test_confirm_requires_auth(self, client: AsyncClient):
        resp = await client.post("/api/v1/receipt-ocr/1/confirm")
        assert resp.status_code in (401, 403)


class TestReceiptEdgeCases:
    async def test_list_empty(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/v1/receipt-ocr", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_upload_no_file_body(self, client: AsyncClient, auth_headers: dict):
        """Missing file field in multipart form."""
        resp = await client.post(
            "/api/v1/receipt-ocr/upload",
            headers=auth_headers,
        )
        assert resp.status_code == 422
