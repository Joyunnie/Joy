"""Tests for security fixes: rate limiting, health check, offset validation, optimistic locking."""
import pytest
from httpx import AsyncClient

from app.main import app
from tests.conftest import seed_session_factory


# === Health Check ===


@pytest.mark.asyncio
async def test_health_check_ok(client: AsyncClient):
    """Health endpoint returns 200 when DB is reachable."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_health_check_db_failure(client: AsyncClient):
    """Health endpoint returns 503 when DB is unreachable."""
    from unittest.mock import AsyncMock, patch

    mock_conn = AsyncMock()
    mock_conn.execute.side_effect = Exception("connection refused")
    mock_connect = AsyncMock()
    mock_connect.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_connect.__aexit__ = AsyncMock(return_value=False)

    with patch("app.main.engine") as mock_engine:
        mock_engine.connect.return_value = mock_connect
        resp = await client.get("/health")
        assert resp.status_code == 503
        assert resp.json()["status"] == "error"


# === Rate Limiting ===


@pytest.mark.asyncio
async def test_login_rate_limit(client: AsyncClient, seed_data):
    """Login endpoint returns 429 after exceeding 5 attempts/minute."""
    # Enable rate limiter for this test
    app.state.limiter.enabled = True
    app.state.limiter.reset()
    try:
        for i in range(6):
            resp = await client.post("/api/v1/auth/login", json={
                "pharmacy_id": seed_data["pharmacy_id"],
                "username": "nonexistent",
                "password": "wrongpass123",
            })
            if i < 5:
                # Could be 401 (wrong creds) — that's fine, not 429
                assert resp.status_code in (401, 429)
            else:
                # 6th attempt must be rate limited
                assert resp.status_code == 429
    finally:
        app.state.limiter.enabled = False
        app.state.limiter.reset()


# === Offset Validation ===


@pytest.mark.asyncio
async def test_negative_offset_rejected(client: AsyncClient, auth_headers):
    """Negative offset should return 422."""
    endpoints = [
        "/api/v1/alerts?offset=-1",
        "/api/v1/narcotics-inventory?offset=-1",
        "/api/v1/drugs?offset=-1",
        "/api/v1/todos?offset=-1",
    ]
    for url in endpoints:
        resp = await client.get(url, headers=auth_headers)
        assert resp.status_code == 422, f"Expected 422 for {url}, got {resp.status_code}"


# === Optimistic Locking (DB-level) ===


@pytest.mark.asyncio
async def test_narcotics_concurrent_dispense_conflict(
    client: AsyncClient, auth_headers, seed_data, narcotic_drug_seed, cleanup_narcotics
):
    """Two dispense requests with same version: first succeeds, second gets 409."""
    BASE = "/api/v1/narcotics-inventory"

    # Create item with qty=100, version=1
    create_resp = await client.post(BASE, json={
        "drug_id": narcotic_drug_seed["drug_id"],
        "lot_number": "LOCK-TEST-001",
        "quantity": 100,
    }, headers=auth_headers)
    assert create_resp.status_code == 201
    item_id = create_resp.json()["id"]

    # First dispense: version=1 → success
    resp1 = await client.post(f"{BASE}/{item_id}/dispense", json={
        "quantity": 10,
        "version": 1,
    }, headers=auth_headers)
    assert resp1.status_code == 200
    assert resp1.json()["version"] == 2

    # Second dispense with stale version=1 → conflict
    resp2 = await client.post(f"{BASE}/{item_id}/dispense", json={
        "quantity": 10,
        "version": 1,
    }, headers=auth_headers)
    assert resp2.status_code == 409
