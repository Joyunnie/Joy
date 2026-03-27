"""drug_thresholds CRUD 엔드포인트 테스트."""

import pytest

from app.models.tables import Drug, DrugThreshold
from tests.conftest import seed_session_factory

from sqlalchemy import select


# ---------- helpers ----------

async def _get_drug_id(standard_code: str) -> int:
    """DB에서 약품 ID 조회."""
    async with seed_session_factory() as db:
        result = await db.execute(
            select(Drug).where(Drug.standard_code == standard_code)
        )
        drug = result.scalar_one()
        return drug.id


async def _seed_threshold(pharmacy_id: int, drug_id: int, min_quantity: int = 10) -> int:
    """테스트용 threshold 직접 삽입. id 반환."""
    async with seed_session_factory() as db:
        th = DrugThreshold(
            pharmacy_id=pharmacy_id,
            drug_id=drug_id,
            min_quantity=min_quantity,
            is_active=True,
        )
        db.add(th)
        await db.flush()
        th_id = th.id
        await db.commit()
        return th_id


# ---------- CREATE ----------

@pytest.mark.asyncio
async def test_create_threshold(client, auth_headers, seed_data, cleanup_thresholds):
    drug_id = await _get_drug_id("KD67890")  # 타이레놀 OTC
    resp = await client.post(
        "/api/v1/thresholds",
        json={"drug_id": drug_id, "min_quantity": 15},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["drug_id"] == drug_id
    assert body["min_quantity"] == 15
    assert body["is_active"] is True
    assert body["drug_name"] == "타이레놀"
    assert body["drug_category"] == "OTC"
    assert "id" in body
    assert "created_at" in body


@pytest.mark.asyncio
async def test_create_threshold_duplicate(client, auth_headers, seed_data, cleanup_thresholds):
    drug_id = await _get_drug_id("KD67890")
    resp1 = await client.post(
        "/api/v1/thresholds",
        json={"drug_id": drug_id, "min_quantity": 10},
        headers=auth_headers,
    )
    assert resp1.status_code == 201

    resp2 = await client.post(
        "/api/v1/thresholds",
        json={"drug_id": drug_id, "min_quantity": 20},
        headers=auth_headers,
    )
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_create_threshold_invalid_drug(client, auth_headers, seed_data):
    resp = await client.post(
        "/api/v1/thresholds",
        json={"drug_id": 999999, "min_quantity": 10},
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_threshold_invalid_min_quantity(client, auth_headers, seed_data):
    drug_id = await _get_drug_id("KD67890")
    resp = await client.post(
        "/api/v1/thresholds",
        json={"drug_id": drug_id, "min_quantity": 0},
        headers=auth_headers,
    )
    assert resp.status_code == 422


# ---------- LIST ----------

@pytest.mark.asyncio
async def test_list_thresholds(client, auth_headers, seed_data, cleanup_thresholds):
    drug_id_otc = await _get_drug_id("KD67890")
    drug_id_rx = await _get_drug_id("KD12345")
    await _seed_threshold(seed_data["pharmacy_id"], drug_id_otc, 10)
    await _seed_threshold(seed_data["pharmacy_id"], drug_id_rx, 20)

    resp = await client.get("/api/v1/thresholds", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2


@pytest.mark.asyncio
async def test_list_thresholds_search(client, auth_headers, seed_data, cleanup_thresholds):
    drug_id_otc = await _get_drug_id("KD67890")
    drug_id_rx = await _get_drug_id("KD12345")
    await _seed_threshold(seed_data["pharmacy_id"], drug_id_otc, 10)
    await _seed_threshold(seed_data["pharmacy_id"], drug_id_rx, 20)

    resp = await client.get(
        "/api/v1/thresholds", params={"search": "타이레놀"}, headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["drug_name"] == "타이레놀"


@pytest.mark.asyncio
async def test_list_thresholds_category_filter(client, auth_headers, seed_data, cleanup_thresholds):
    drug_id_otc = await _get_drug_id("KD67890")
    drug_id_rx = await _get_drug_id("KD12345")
    await _seed_threshold(seed_data["pharmacy_id"], drug_id_otc, 10)
    await _seed_threshold(seed_data["pharmacy_id"], drug_id_rx, 20)

    resp = await client.get(
        "/api/v1/thresholds", params={"category": "OTC"}, headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["drug_category"] == "OTC"


@pytest.mark.asyncio
async def test_list_thresholds_pagination(client, auth_headers, seed_data, cleanup_thresholds):
    drug_id_otc = await _get_drug_id("KD67890")
    drug_id_rx = await _get_drug_id("KD12345")
    await _seed_threshold(seed_data["pharmacy_id"], drug_id_otc, 10)
    await _seed_threshold(seed_data["pharmacy_id"], drug_id_rx, 20)

    resp = await client.get(
        "/api/v1/thresholds", params={"limit": 1, "offset": 0}, headers=auth_headers
    )
    body = resp.json()
    assert body["total"] == 2
    assert len(body["items"]) == 1

    resp2 = await client.get(
        "/api/v1/thresholds", params={"limit": 1, "offset": 1}, headers=auth_headers
    )
    body2 = resp2.json()
    assert body2["total"] == 2
    assert len(body2["items"]) == 1
    assert body2["items"][0]["id"] != body["items"][0]["id"]


# ---------- UPDATE ----------

@pytest.mark.asyncio
async def test_update_threshold(client, auth_headers, seed_data, cleanup_thresholds):
    drug_id = await _get_drug_id("KD67890")
    th_id = await _seed_threshold(seed_data["pharmacy_id"], drug_id, 10)

    resp = await client.put(
        f"/api/v1/thresholds/{th_id}",
        json={"min_quantity": 25, "is_active": False},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["min_quantity"] == 25
    assert body["is_active"] is False


@pytest.mark.asyncio
async def test_update_threshold_not_found(client, auth_headers, seed_data):
    resp = await client.put(
        "/api/v1/thresholds/999999",
        json={"min_quantity": 10, "is_active": True},
        headers=auth_headers,
    )
    assert resp.status_code == 404


# ---------- DELETE ----------

@pytest.mark.asyncio
async def test_delete_threshold(client, auth_headers, seed_data, cleanup_thresholds):
    drug_id = await _get_drug_id("KD67890")
    th_id = await _seed_threshold(seed_data["pharmacy_id"], drug_id, 10)

    resp = await client.delete(f"/api/v1/thresholds/{th_id}", headers=auth_headers)
    assert resp.status_code == 204

    # 목록에서 사라졌는지 확인
    list_resp = await client.get("/api/v1/thresholds", headers=auth_headers)
    items = list_resp.json()["items"]
    assert all(item["id"] != th_id for item in items)


@pytest.mark.asyncio
async def test_delete_threshold_not_found(client, auth_headers, seed_data):
    resp = await client.delete("/api/v1/thresholds/999999", headers=auth_headers)
    assert resp.status_code == 404
