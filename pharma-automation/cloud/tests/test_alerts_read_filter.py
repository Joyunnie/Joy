"""Tests for GET /alerts is_read filter.

Covers: is_read=true returns only read, is_read=false returns only unread,
no param returns all.
"""
import pytest
import pytest_asyncio
from datetime import datetime, timezone
from httpx import AsyncClient

from app.models.tables import AlertLog
from tests.conftest import seed_session_factory

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture(autouse=True)
async def cleanup_and_seed(seed_data):
    """Seed 2 read + 1 unread alerts, clean before/after."""
    pid = seed_data["pharmacy_id"]

    async def _clean():
        async with seed_session_factory() as db:
            await db.execute(AlertLog.__table__.delete().where(AlertLog.pharmacy_id == pid))
            await db.commit()

    await _clean()

    async with seed_session_factory() as db:
        db.add(AlertLog(
            pharmacy_id=pid, alert_type="LOW_STOCK",
            message="Read alert 1", sent_via="IN_APP",
            read_at=datetime.now(timezone.utc),
        ))
        db.add(AlertLog(
            pharmacy_id=pid, alert_type="LOW_STOCK",
            message="Read alert 2", sent_via="IN_APP",
            read_at=datetime.now(timezone.utc),
        ))
        db.add(AlertLog(
            pharmacy_id=pid, alert_type="NARCOTICS_LOW",
            message="Unread alert", sent_via="IN_APP",
        ))
        await db.commit()

    yield
    await _clean()


async def test_is_read_true_returns_only_read(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/alerts", params={"is_read": True}, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert all(a["read_at"] is not None for a in data["alerts"])


async def test_is_read_false_returns_only_unread(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/alerts", params={"is_read": False}, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["alerts"][0]["read_at"] is None
    assert data["alerts"][0]["message"] == "Unread alert"


async def test_no_is_read_returns_all(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/alerts", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 3
