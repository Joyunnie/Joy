"""Alert service tests."""

import pytest
import pytest_asyncio

from tests.conftest import seed_session_factory
from app.models.tables import AlertLog


@pytest_asyncio.fixture(autouse=True)
async def _cleanup_alerts(seed_data):
    """Clean up alert_logs before and after each test."""
    async with seed_session_factory() as db:
        await db.execute(
            AlertLog.__table__.delete().where(
                AlertLog.pharmacy_id == seed_data["pharmacy_id"]
            )
        )
        await db.commit()
    yield
    async with seed_session_factory() as db:
        await db.execute(
            AlertLog.__table__.delete().where(
                AlertLog.pharmacy_id == seed_data["pharmacy_id"]
            )
        )
        await db.commit()


async def _create_alerts(pharmacy_id: int, count: int = 3):
    """Helper: create test alerts."""
    async with seed_session_factory() as db:
        for i in range(count):
            db.add(AlertLog(
                pharmacy_id=pharmacy_id,
                alert_type="LOW_STOCK" if i % 2 == 0 else "VISIT_APPROACHING",
                ref_table="drugs",
                ref_id=i + 1,
                message=f"Test alert {i + 1}",
                sent_via="IN_APP",
            ))
        await db.commit()


@pytest.mark.asyncio
async def test_get_alerts(client, auth_headers, seed_data):
    await _create_alerts(seed_data["pharmacy_id"], 3)
    resp = await client.get("/api/v1/alerts", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["alerts"]) == 3


@pytest.mark.asyncio
async def test_get_alerts_unread_only(client, auth_headers, seed_data):
    await _create_alerts(seed_data["pharmacy_id"], 2)
    # Mark first alert as read
    resp = await client.get("/api/v1/alerts", headers=auth_headers)
    alert_id = resp.json()["alerts"][0]["id"]
    await client.patch(f"/api/v1/alerts/{alert_id}/read", headers=auth_headers)

    resp = await client.get(
        "/api/v1/alerts", params={"unread_only": True}, headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    for a in resp.json()["alerts"]:
        assert a["read_at"] is None


@pytest.mark.asyncio
async def test_get_alerts_read_only(client, auth_headers, seed_data):
    await _create_alerts(seed_data["pharmacy_id"], 2)
    # Mark first alert as read
    resp = await client.get("/api/v1/alerts", headers=auth_headers)
    alert_id = resp.json()["alerts"][0]["id"]
    await client.patch(f"/api/v1/alerts/{alert_id}/read", headers=auth_headers)

    resp = await client.get(
        "/api/v1/alerts", params={"read_only": True}, headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    for a in resp.json()["alerts"]:
        assert a["read_at"] is not None


@pytest.mark.asyncio
async def test_get_alerts_unread_and_read_422(client, auth_headers, seed_data):
    resp = await client.get(
        "/api/v1/alerts",
        params={"unread_only": True, "read_only": True},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_alerts_type_filter(client, auth_headers, seed_data):
    await _create_alerts(seed_data["pharmacy_id"], 4)
    resp = await client.get(
        "/api/v1/alerts",
        params={"alert_type": "LOW_STOCK"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    for a in resp.json()["alerts"]:
        assert a["alert_type"] == "LOW_STOCK"


@pytest.mark.asyncio
async def test_mark_alert_read(client, auth_headers, seed_data):
    await _create_alerts(seed_data["pharmacy_id"], 1)
    resp = await client.get("/api/v1/alerts", headers=auth_headers)
    alert_id = resp.json()["alerts"][0]["id"]

    resp = await client.patch(f"/api/v1/alerts/{alert_id}/read", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["read_at"] is not None
    assert resp.json()["id"] == alert_id
