"""RPA Commands API tests."""

import pytest
import pytest_asyncio

from tests.conftest import seed_session_factory
from app.models.tables import RpaCommand


@pytest_asyncio.fixture(autouse=True)
async def _cleanup(seed_data):
    """Clean up rpa_commands before each test."""
    async with seed_session_factory() as db:
        await db.execute(
            RpaCommand.__table__.delete().where(
                RpaCommand.pharmacy_id == seed_data["pharmacy_id"]
            )
        )
        await db.commit()
    yield
    async with seed_session_factory() as db:
        await db.execute(
            RpaCommand.__table__.delete().where(
                RpaCommand.pharmacy_id == seed_data["pharmacy_id"]
            )
        )
        await db.commit()


@pytest.mark.asyncio
async def test_create_narcotics_command(client, auth_headers, seed_data):
    resp = await client.post(
        "/api/v1/rpa-commands",
        json={
            "command_type": "NARCOTICS_INPUT",
            "payload": {"drug_name": "펜타닐패치", "quantity": 1},
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["command_type"] == "NARCOTICS_INPUT"
    assert data["status"] == "PENDING"
    assert data["payload"]["drug_name"] == "펜타닐패치"


@pytest.mark.asyncio
async def test_create_prescription_command(client, auth_headers, seed_data):
    resp = await client.post(
        "/api/v1/rpa-commands",
        json={
            "command_type": "PRESCRIPTION_INPUT",
            "payload": {
                "prescription_ocr_record_id": 1,
                "patient_name": "홍길동",
                "drugs": [{"drug_name": "아모시실린", "dosage": "1정", "frequency": "3", "days": 7}],
            },
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["command_type"] == "PRESCRIPTION_INPUT"
    assert len(data["payload"]["drugs"]) == 1


@pytest.mark.asyncio
async def test_create_invalid_command_type(client, auth_headers, seed_data):
    resp = await client.post(
        "/api/v1/rpa-commands",
        json={"command_type": "INVALID_TYPE", "payload": {}},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_pending_commands(client, auth_headers, seed_data):
    for i in range(2):
        await client.post(
            "/api/v1/rpa-commands",
            json={"command_type": "NARCOTICS_INPUT", "payload": {"index": i}},
            headers=auth_headers,
        )

    resp = await client.get(
        "/api/v1/rpa-commands/pending",
        headers={"X-API-Key": seed_data["api_key"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["commands"]) == 2
    for cmd in data["commands"]:
        assert cmd["status"] == "SENT"


@pytest.mark.asyncio
async def test_pending_empty_after_poll(client, auth_headers, seed_data):
    await client.post(
        "/api/v1/rpa-commands",
        json={"command_type": "NARCOTICS_INPUT", "payload": {}},
        headers=auth_headers,
    )
    await client.get(
        "/api/v1/rpa-commands/pending",
        headers={"X-API-Key": seed_data["api_key"]},
    )
    resp = await client.get(
        "/api/v1/rpa-commands/pending",
        headers={"X-API-Key": seed_data["api_key"]},
    )
    assert resp.status_code == 200
    assert len(resp.json()["commands"]) == 0


@pytest.mark.asyncio
async def test_status_executing_to_success(client, auth_headers, seed_data):
    create_resp = await client.post(
        "/api/v1/rpa-commands",
        json={"command_type": "NARCOTICS_INPUT", "payload": {}},
        headers=auth_headers,
    )
    cmd_id = create_resp.json()["id"]
    await client.get(
        "/api/v1/rpa-commands/pending",
        headers={"X-API-Key": seed_data["api_key"]},
    )

    resp = await client.patch(
        f"/api/v1/rpa-commands/{cmd_id}/status",
        json={"status": "EXECUTING"},
        headers={"X-API-Key": seed_data["api_key"]},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "EXECUTING"
    assert resp.json()["started_at"] is not None

    resp = await client.patch(
        f"/api/v1/rpa-commands/{cmd_id}/status",
        json={"status": "SUCCESS"},
        headers={"X-API-Key": seed_data["api_key"]},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "SUCCESS"
    assert resp.json()["completed_at"] is not None


@pytest.mark.asyncio
async def test_status_to_failed(client, auth_headers, seed_data):
    create_resp = await client.post(
        "/api/v1/rpa-commands",
        json={"command_type": "NARCOTICS_INPUT", "payload": {}},
        headers=auth_headers,
    )
    cmd_id = create_resp.json()["id"]
    await client.get(
        "/api/v1/rpa-commands/pending",
        headers={"X-API-Key": seed_data["api_key"]},
    )
    await client.patch(
        f"/api/v1/rpa-commands/{cmd_id}/status",
        json={"status": "EXECUTING"},
        headers={"X-API-Key": seed_data["api_key"]},
    )
    resp = await client.patch(
        f"/api/v1/rpa-commands/{cmd_id}/status",
        json={"status": "FAILED", "error_message": "PM+20 not found"},
        headers={"X-API-Key": seed_data["api_key"]},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "FAILED"
    assert resp.json()["error_message"] == "PM+20 not found"
    assert resp.json()["retry_count"] == 1


@pytest.mark.asyncio
async def test_invalid_status_transition(client, auth_headers, seed_data):
    create_resp = await client.post(
        "/api/v1/rpa-commands",
        json={"command_type": "NARCOTICS_INPUT", "payload": {}},
        headers=auth_headers,
    )
    cmd_id = create_resp.json()["id"]
    resp = await client.patch(
        f"/api/v1/rpa-commands/{cmd_id}/status",
        json={"status": "SUCCESS"},
        headers={"X-API-Key": seed_data["api_key"]},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_commands_with_filter(client, auth_headers, seed_data):
    for _ in range(3):
        await client.post(
            "/api/v1/rpa-commands",
            json={"command_type": "NARCOTICS_INPUT", "payload": {}},
            headers=auth_headers,
        )
    resp = await client.get("/api/v1/rpa-commands", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 3

    resp = await client.get(
        "/api/v1/rpa-commands",
        params={"status": "PENDING"},
        headers=auth_headers,
    )
    assert resp.json()["total"] == 3


@pytest.mark.asyncio
async def test_command_not_found(client, seed_data):
    resp = await client.patch(
        "/api/v1/rpa-commands/99999/status",
        json={"status": "EXECUTING"},
        headers={"X-API-Key": seed_data["api_key"]},
    )
    assert resp.status_code == 404
