"""Tests for PATCH /api/v1/alerts/{alert_id}/read — mark alert as read.

Covers: happy path, 404 not found, 403 cross-pharmacy isolation,
idempotent re-read, filtering read/unread alerts.
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.models.tables import AlertLog, Pharmacy
from tests.conftest import seed_session_factory

pytestmark = pytest.mark.asyncio

BASE = "/api/v1/alerts"


@pytest_asyncio.fixture(autouse=True)
async def cleanup_alerts(seed_data):
    """Clean alert_logs before/after each test."""
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


async def _create_alert(pharmacy_id: int, **kwargs) -> int:
    """Insert an alert directly and return its id."""
    async with seed_session_factory() as db:
        alert = AlertLog(
            pharmacy_id=pharmacy_id,
            alert_type=kwargs.get("alert_type", "LOW_STOCK"),
            ref_table=kwargs.get("ref_table", "drug_stock"),
            ref_id=kwargs.get("ref_id", 1),
            message=kwargs.get("message", "Test alert"),
            sent_via="IN_APP",
        )
        db.add(alert)
        await db.flush()
        alert_id = alert.id
        await db.commit()
        return alert_id


# --- Happy Path ---


class TestMarkAlertRead:
    async def test_mark_as_read_success(self, client: AsyncClient, auth_headers, seed_data):
        """PATCH /{id}/read returns 200 with read_at timestamp."""
        alert_id = await _create_alert(seed_data["pharmacy_id"])

        resp = await client.patch(f"{BASE}/{alert_id}/read", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == alert_id
        assert data["read_at"] is not None

    async def test_idempotent_mark_read(self, client: AsyncClient, auth_headers, seed_data):
        """Marking the same alert as read twice doesn't fail."""
        alert_id = await _create_alert(seed_data["pharmacy_id"])

        resp1 = await client.patch(f"{BASE}/{alert_id}/read", headers=auth_headers)
        assert resp1.status_code == 200
        first_read_at = resp1.json()["read_at"]

        resp2 = await client.patch(f"{BASE}/{alert_id}/read", headers=auth_headers)
        assert resp2.status_code == 200
        # read_at may be updated to a newer timestamp (not an error)

    async def test_unread_filter_excludes_read_alerts(
        self, client: AsyncClient, auth_headers, seed_data
    ):
        """After marking as read, is_read=false filter excludes it."""
        alert_id = await _create_alert(seed_data["pharmacy_id"])

        # Before read: appears in unread list
        resp = await client.get(f"{BASE}?is_read=false", headers=auth_headers)
        ids_before = [a["id"] for a in resp.json()["alerts"]]
        assert alert_id in ids_before

        # Mark as read
        await client.patch(f"{BASE}/{alert_id}/read", headers=auth_headers)

        # After read: excluded from unread list
        resp = await client.get(f"{BASE}?is_read=false", headers=auth_headers)
        ids_after = [a["id"] for a in resp.json()["alerts"]]
        assert alert_id not in ids_after


# --- Error Cases ---


class TestMarkAlertReadErrors:
    async def test_alert_not_found_returns_404(self, client: AsyncClient, auth_headers):
        """PATCH on non-existent alert returns 404."""
        resp = await client.patch(f"{BASE}/999999/read", headers=auth_headers)
        assert resp.status_code == 404

    async def test_cross_pharmacy_returns_403(
        self, client: AsyncClient, auth_headers, seed_data
    ):
        """Cannot mark another pharmacy's alert as read."""
        # Create alert for a different pharmacy
        async with seed_session_factory() as db:
            other = Pharmacy(
                name="다른약국_alert_test",
                patient_hash_salt="s",
                patient_hash_algorithm="SHA-256",
                default_alert_days_before=3,
            )
            db.add(other)
            await db.flush()
            other_id = other.id
            alert = AlertLog(
                pharmacy_id=other_id,
                alert_type="LOW_STOCK",
                message="Other pharmacy alert",
                sent_via="IN_APP",
            )
            db.add(alert)
            await db.flush()
            alert_id = alert.id
            await db.commit()

        resp = await client.patch(f"{BASE}/{alert_id}/read", headers=auth_headers)
        assert resp.status_code == 403

    async def test_no_auth_returns_401(self, client: AsyncClient, seed_data):
        """PATCH without JWT returns 401/403."""
        alert_id = await _create_alert(seed_data["pharmacy_id"])
        resp = await client.patch(f"{BASE}/{alert_id}/read")
        assert resp.status_code in (401, 403)


# --- List Filtering ---


class TestAlertListFiltering:
    async def test_filter_by_alert_type(self, client: AsyncClient, auth_headers, seed_data):
        """GET with alert_type filter returns only matching alerts."""
        pid = seed_data["pharmacy_id"]
        await _create_alert(pid, alert_type="LOW_STOCK", message="low")
        await _create_alert(pid, alert_type="NARCOTICS_LOW", message="narcotics")

        resp = await client.get(f"{BASE}?alert_type=LOW_STOCK", headers=auth_headers)
        assert resp.status_code == 200
        for a in resp.json()["alerts"]:
            assert a["alert_type"] == "LOW_STOCK"

    async def test_pagination(self, client: AsyncClient, auth_headers, seed_data):
        """GET with limit/offset paginates correctly."""
        pid = seed_data["pharmacy_id"]
        for i in range(5):
            await _create_alert(pid, message=f"Alert {i}")

        resp = await client.get(f"{BASE}?limit=2&offset=0", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["alerts"]) == 2
