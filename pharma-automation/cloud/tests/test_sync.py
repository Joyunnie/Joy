import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_sync_inventory_no_auth(client: AsyncClient):
    """API key 없이 호출 시 422 (헤더 누락), 잘못된 키 시 401."""
    # No header → 422 (FastAPI Header validation)
    resp = await client.post(
        "/api/v1/sync/inventory",
        json={"items": [], "synced_at": "2026-03-16T02:00:00+09:00"},
    )
    assert resp.status_code == 422

    # Wrong key → 401
    resp = await client.post(
        "/api/v1/sync/inventory",
        json={"items": [], "synced_at": "2026-03-16T02:00:00+09:00"},
        headers={"X-API-Key": "wrong-key"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_sync_inventory_with_auth(client: AsyncClient, seed_data: dict):
    """Valid API key로 inventory sync."""
    resp = await client.post(
        "/api/v1/sync/inventory",
        json={
            "items": [
                {
                    "cassette_number": 1,
                    "drug_standard_code": "KD12345",
                    "current_quantity": 150,
                    "quantity_source": "PM20",
                }
            ],
            "synced_at": "2026-03-16T02:00:00+09:00",
        },
        headers={"X-API-Key": seed_data["api_key"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["synced_count"] == 1


@pytest.mark.asyncio
async def test_sync_visits_with_skipped_drugs(client: AsyncClient, seed_data: dict):
    """방문 sync 시 미등록 약품은 스킵되어야 함."""
    resp = await client.post(
        "/api/v1/sync/visits",
        json={
            "visits": [
                {
                    "patient_hash": "abc123def456",
                    "visit_date": "2026-03-15",
                    "prescription_days": 30,
                    "source": "PM20_SYNC",
                    "drugs": [
                        {"drug_standard_code": "KD12345", "quantity_dispensed": 30},
                        {"drug_standard_code": "UNKNOWN999", "quantity_dispensed": 10},
                    ],
                }
            ]
        },
        headers={"X-API-Key": seed_data["api_key"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["synced_count"] == 1
    assert len(data["visit_ids"]) == 1
    assert len(data["skipped_drugs"]) == 1
    assert data["skipped_drugs"][0]["drug_standard_code"] == "UNKNOWN999"
    assert data["skipped_drugs"][0]["reason"] == "not_found_in_drugs_master"


@pytest.mark.asyncio
async def test_sync_cassette_mapping(client: AsyncClient, seed_data: dict):
    """카세트 매핑 sync."""
    resp = await client.post(
        "/api/v1/sync/cassette-mapping",
        json={
            "mappings": [
                {
                    "cassette_number": 2,
                    "drug_standard_code": "KD12345",
                    "mapping_source": "ATDPS",
                }
            ],
            "synced_at": "2026-03-16T02:00:00+09:00",
        },
        headers={"X-API-Key": seed_data["api_key"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["synced_count"] == 1


@pytest.mark.asyncio
async def test_get_alerts(client: AsyncClient, seed_data: dict):
    """알림 목록 조회."""
    resp = await client.get(
        "/api/v1/alerts",
        params={"pharmacy_id": seed_data["pharmacy_id"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "alerts" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_get_inventory_status(client: AsyncClient, seed_data: dict):
    """재고 현황 조회."""
    resp = await client.get(
        "/api/v1/inventory/status",
        params={"pharmacy_id": seed_data["pharmacy_id"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data


@pytest.mark.asyncio
async def test_get_predictions(client: AsyncClient, seed_data: dict):
    """예측 목록 조회."""
    resp = await client.get(
        "/api/v1/predictions",
        params={"pharmacy_id": seed_data["pharmacy_id"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "predictions" in data
