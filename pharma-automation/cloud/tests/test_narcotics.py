import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.tables import (
    AlertLog,
    Drug,
    InventoryAuditLog,
    NarcoticsInventory,
    NarcoticsTransaction,
    Pharmacy,
)
from tests.conftest import seed_session_factory

BASE = "/api/v1/narcotics-inventory"


# === Helper ===


async def _create_item(client, headers, drug_id, lot="LOT-001", qty=100, notes=None):
    body = {"drug_id": drug_id, "lot_number": lot, "quantity": qty}
    if notes:
        body["notes"] = notes
    resp = await client.post(BASE, json=body, headers=headers)
    return resp


# === CRUD 기본 ===


@pytest.mark.asyncio
async def test_create_narcotics_item(
    client: AsyncClient, auth_headers, seed_data, narcotic_drug_seed, cleanup_narcotics
):
    resp = await _create_item(client, auth_headers, narcotic_drug_seed["drug_id"])
    assert resp.status_code == 201
    data = resp.json()
    assert data["drug_name"] == "펜타닐패치"
    assert data["current_quantity"] == 100
    assert data["lot_number"] == "LOT-001"
    assert data["version"] == 1
    assert data["is_active"] is True
    assert data["is_low_stock"] is False


@pytest.mark.asyncio
async def test_create_duplicate_lot(
    client: AsyncClient, auth_headers, seed_data, narcotic_drug_seed, cleanup_narcotics
):
    await _create_item(client, auth_headers, narcotic_drug_seed["drug_id"])
    resp = await _create_item(client, auth_headers, narcotic_drug_seed["drug_id"])
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_invalid_drug(
    client: AsyncClient, auth_headers, cleanup_narcotics
):
    resp = await _create_item(client, auth_headers, 999999)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_non_narcotic_drug(
    client: AsyncClient, auth_headers, seed_data, otc_drug_seed, cleanup_narcotics
):
    resp = await _create_item(client, auth_headers, otc_drug_seed["drug_id"])
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_generates_receive_transaction(
    client: AsyncClient, auth_headers, seed_data, narcotic_drug_seed, cleanup_narcotics
):
    resp = await _create_item(client, auth_headers, narcotic_drug_seed["drug_id"])
    item_id = resp.json()["id"]

    async with seed_session_factory() as db:
        result = await db.execute(
            select(NarcoticsTransaction).where(
                NarcoticsTransaction.narcotics_inventory_id == item_id,
                NarcoticsTransaction.transaction_type == "RECEIVE",
            )
        )
        tx = result.scalar_one_or_none()
        assert tx is not None
        assert tx.quantity == 100
        assert tx.remaining_quantity == 100


@pytest.mark.asyncio
async def test_create_generates_audit_log(
    client: AsyncClient, auth_headers, seed_data, narcotic_drug_seed, cleanup_narcotics
):
    resp = await _create_item(client, auth_headers, narcotic_drug_seed["drug_id"])
    item_id = resp.json()["id"]

    async with seed_session_factory() as db:
        result = await db.execute(
            select(InventoryAuditLog).where(
                InventoryAuditLog.record_id == item_id,
                InventoryAuditLog.table_name == "narcotics_inventory",
                InventoryAuditLog.action == "INSERT",
            )
        )
        audit = result.scalar_one_or_none()
        assert audit is not None


@pytest.mark.asyncio
async def test_list_narcotics(
    client: AsyncClient, auth_headers, seed_data, narcotic_drug_seed, cleanup_narcotics
):
    await _create_item(client, auth_headers, narcotic_drug_seed["drug_id"])
    resp = await client.get(BASE, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_list_active_only_default(
    client: AsyncClient, auth_headers, seed_data, narcotic_drug_seed, cleanup_narcotics
):
    create_resp = await _create_item(client, auth_headers, narcotic_drug_seed["drug_id"])
    item_id = create_resp.json()["id"]

    # Deactivate
    await client.request(
        "DELETE", f"{BASE}/{item_id}",
        json={"notes": "폐기", "version": 1},
        headers=auth_headers,
    )

    resp = await client.get(BASE, headers=auth_headers)
    data = resp.json()
    ids = [item["id"] for item in data["items"]]
    assert item_id not in ids


@pytest.mark.asyncio
async def test_list_with_search(
    client: AsyncClient, auth_headers, seed_data, narcotic_drug_seed, cleanup_narcotics
):
    await _create_item(client, auth_headers, narcotic_drug_seed["drug_id"])
    resp = await client.get(f"{BASE}?search=펜타닐", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


@pytest.mark.asyncio
async def test_list_low_stock_only(
    client: AsyncClient, auth_headers, seed_data, narcotic_drug_seed, cleanup_narcotics
):
    # threshold=10, qty=5 -> low stock
    await _create_item(client, auth_headers, narcotic_drug_seed["drug_id"], qty=5)
    resp = await client.get(f"{BASE}?low_stock_only=true", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert item["is_low_stock"] is True


@pytest.mark.asyncio
async def test_get_narcotics_item(
    client: AsyncClient, auth_headers, seed_data, narcotic_drug_seed, cleanup_narcotics
):
    create_resp = await _create_item(client, auth_headers, narcotic_drug_seed["drug_id"])
    item_id = create_resp.json()["id"]

    resp = await client.get(f"{BASE}/{item_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == item_id


@pytest.mark.asyncio
async def test_get_not_found(client: AsyncClient, auth_headers):
    resp = await client.get(f"{BASE}/999999", headers=auth_headers)
    assert resp.status_code == 404


# === Update (ADJUST) ===


@pytest.mark.asyncio
async def test_update_narcotics_item(
    client: AsyncClient, auth_headers, seed_data, narcotic_drug_seed, cleanup_narcotics
):
    create_resp = await _create_item(client, auth_headers, narcotic_drug_seed["drug_id"])
    item_id = create_resp.json()["id"]

    resp = await client.put(
        f"{BASE}/{item_id}",
        json={"current_quantity": 95, "notes": "실사 조정", "version": 1},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["current_quantity"] == 95
    assert data["version"] == 2


@pytest.mark.asyncio
async def test_update_version_conflict(
    client: AsyncClient, auth_headers, seed_data, narcotic_drug_seed, cleanup_narcotics
):
    create_resp = await _create_item(client, auth_headers, narcotic_drug_seed["drug_id"])
    item_id = create_resp.json()["id"]

    await client.put(
        f"{BASE}/{item_id}",
        json={"current_quantity": 90, "version": 1},
        headers=auth_headers,
    )
    resp = await client.put(
        f"{BASE}/{item_id}",
        json={"current_quantity": 80, "version": 1},
        headers=auth_headers,
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_update_not_found(client: AsyncClient, auth_headers):
    resp = await client.put(
        f"{BASE}/999999",
        json={"current_quantity": 10, "version": 1},
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_generates_adjust_transaction(
    client: AsyncClient, auth_headers, seed_data, narcotic_drug_seed, cleanup_narcotics
):
    create_resp = await _create_item(client, auth_headers, narcotic_drug_seed["drug_id"])
    item_id = create_resp.json()["id"]

    await client.put(
        f"{BASE}/{item_id}",
        json={"current_quantity": 95, "version": 1},
        headers=auth_headers,
    )

    async with seed_session_factory() as db:
        result = await db.execute(
            select(NarcoticsTransaction).where(
                NarcoticsTransaction.narcotics_inventory_id == item_id,
                NarcoticsTransaction.transaction_type == "ADJUST",
            )
        )
        tx = result.scalar_one_or_none()
        assert tx is not None
        assert tx.quantity == -5
        assert tx.remaining_quantity == 95


@pytest.mark.asyncio
async def test_update_no_quantity_change_no_transaction(
    client: AsyncClient, auth_headers, seed_data, narcotic_drug_seed, cleanup_narcotics
):
    create_resp = await _create_item(client, auth_headers, narcotic_drug_seed["drug_id"])
    item_id = create_resp.json()["id"]

    await client.put(
        f"{BASE}/{item_id}",
        json={"current_quantity": 100, "version": 1},
        headers=auth_headers,
    )

    async with seed_session_factory() as db:
        result = await db.execute(
            select(NarcoticsTransaction).where(
                NarcoticsTransaction.narcotics_inventory_id == item_id,
                NarcoticsTransaction.transaction_type == "ADJUST",
            )
        )
        tx = result.scalar_one_or_none()
        assert tx is None


@pytest.mark.asyncio
async def test_update_generates_audit_log(
    client: AsyncClient, auth_headers, seed_data, narcotic_drug_seed, cleanup_narcotics
):
    create_resp = await _create_item(client, auth_headers, narcotic_drug_seed["drug_id"])
    item_id = create_resp.json()["id"]

    await client.put(
        f"{BASE}/{item_id}",
        json={"current_quantity": 90, "version": 1},
        headers=auth_headers,
    )

    async with seed_session_factory() as db:
        result = await db.execute(
            select(InventoryAuditLog).where(
                InventoryAuditLog.record_id == item_id,
                InventoryAuditLog.table_name == "narcotics_inventory",
                InventoryAuditLog.action == "UPDATE",
            )
        )
        audit = result.scalar_one_or_none()
        assert audit is not None
        assert audit.old_values["current_quantity"] == 100
        assert audit.new_values["current_quantity"] == 90


# === Delete (DISPOSE) ===


@pytest.mark.asyncio
async def test_delete_narcotics_item(
    client: AsyncClient, auth_headers, seed_data, narcotic_drug_seed, cleanup_narcotics
):
    create_resp = await _create_item(client, auth_headers, narcotic_drug_seed["drug_id"])
    item_id = create_resp.json()["id"]

    resp = await client.request(
        "DELETE", f"{BASE}/{item_id}",
        json={"notes": "유효기간 만료", "version": 1},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_active"] is False
    assert data["current_quantity"] == 0


@pytest.mark.asyncio
async def test_delete_requires_notes(
    client: AsyncClient, auth_headers, seed_data, narcotic_drug_seed, cleanup_narcotics
):
    create_resp = await _create_item(client, auth_headers, narcotic_drug_seed["drug_id"])
    item_id = create_resp.json()["id"]

    resp = await client.request(
        "DELETE", f"{BASE}/{item_id}",
        json={"notes": "", "version": 1},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_version_conflict(
    client: AsyncClient, auth_headers, seed_data, narcotic_drug_seed, cleanup_narcotics
):
    create_resp = await _create_item(client, auth_headers, narcotic_drug_seed["drug_id"])
    item_id = create_resp.json()["id"]

    # Bump version via update
    await client.put(
        f"{BASE}/{item_id}",
        json={"current_quantity": 100, "version": 1},
        headers=auth_headers,
    )

    resp = await client.request(
        "DELETE", f"{BASE}/{item_id}",
        json={"notes": "폐기", "version": 1},
        headers=auth_headers,
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_delete_generates_dispose_transaction(
    client: AsyncClient, auth_headers, seed_data, narcotic_drug_seed, cleanup_narcotics
):
    create_resp = await _create_item(client, auth_headers, narcotic_drug_seed["drug_id"])
    item_id = create_resp.json()["id"]

    await client.request(
        "DELETE", f"{BASE}/{item_id}",
        json={"notes": "폐기 처리", "version": 1},
        headers=auth_headers,
    )

    async with seed_session_factory() as db:
        result = await db.execute(
            select(NarcoticsTransaction).where(
                NarcoticsTransaction.narcotics_inventory_id == item_id,
                NarcoticsTransaction.transaction_type == "DISPOSE",
            )
        )
        tx = result.scalar_one_or_none()
        assert tx is not None
        assert tx.quantity == -100
        assert tx.remaining_quantity == 0
        assert tx.notes == "폐기 처리"


@pytest.mark.asyncio
async def test_delete_generates_audit_log(
    client: AsyncClient, auth_headers, seed_data, narcotic_drug_seed, cleanup_narcotics
):
    create_resp = await _create_item(client, auth_headers, narcotic_drug_seed["drug_id"])
    item_id = create_resp.json()["id"]

    await client.request(
        "DELETE", f"{BASE}/{item_id}",
        json={"notes": "폐기", "version": 1},
        headers=auth_headers,
    )

    async with seed_session_factory() as db:
        result = await db.execute(
            select(InventoryAuditLog).where(
                InventoryAuditLog.record_id == item_id,
                InventoryAuditLog.table_name == "narcotics_inventory",
                InventoryAuditLog.action == "NARCOTICS_DEACTIVATE",
            )
        )
        audit = result.scalar_one_or_none()
        assert audit is not None


@pytest.mark.asyncio
async def test_delete_no_hard_delete(
    client: AsyncClient, auth_headers, seed_data, narcotic_drug_seed, cleanup_narcotics
):
    create_resp = await _create_item(client, auth_headers, narcotic_drug_seed["drug_id"])
    item_id = create_resp.json()["id"]

    await client.request(
        "DELETE", f"{BASE}/{item_id}",
        json={"notes": "폐기", "version": 1},
        headers=auth_headers,
    )

    # Record still exists in DB (is_active=false)
    async with seed_session_factory() as db:
        result = await db.execute(
            select(NarcoticsInventory).where(NarcoticsInventory.id == item_id)
        )
        inv = result.scalar_one_or_none()
        assert inv is not None
        assert inv.is_active is False


@pytest.mark.asyncio
async def test_delete_already_inactive(
    client: AsyncClient, auth_headers, seed_data, narcotic_drug_seed, cleanup_narcotics
):
    create_resp = await _create_item(client, auth_headers, narcotic_drug_seed["drug_id"])
    item_id = create_resp.json()["id"]

    await client.request(
        "DELETE", f"{BASE}/{item_id}",
        json={"notes": "폐기", "version": 1},
        headers=auth_headers,
    )

    resp = await client.request(
        "DELETE", f"{BASE}/{item_id}",
        json={"notes": "재폐기", "version": 2},
        headers=auth_headers,
    )
    assert resp.status_code == 404


# === Dispense ===


@pytest.mark.asyncio
async def test_dispense_success(
    client: AsyncClient, auth_headers, seed_data, narcotic_drug_seed, cleanup_narcotics
):
    create_resp = await _create_item(client, auth_headers, narcotic_drug_seed["drug_id"])
    item_id = create_resp.json()["id"]

    resp = await client.post(
        f"{BASE}/{item_id}/dispense",
        json={"quantity": 5, "version": 1},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["current_quantity"] == 95
    assert data["version"] == 2

    async with seed_session_factory() as db:
        result = await db.execute(
            select(NarcoticsTransaction).where(
                NarcoticsTransaction.narcotics_inventory_id == item_id,
                NarcoticsTransaction.transaction_type == "DISPENSE",
            )
        )
        tx = result.scalar_one_or_none()
        assert tx is not None
        assert tx.quantity == -5
        assert tx.remaining_quantity == 95


@pytest.mark.asyncio
async def test_dispense_insufficient_stock(
    client: AsyncClient, auth_headers, seed_data, narcotic_drug_seed, cleanup_narcotics
):
    create_resp = await _create_item(client, auth_headers, narcotic_drug_seed["drug_id"], qty=5)
    item_id = create_resp.json()["id"]

    resp = await client.post(
        f"{BASE}/{item_id}/dispense",
        json={"quantity": 10, "version": 1},
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_dispense_version_conflict(
    client: AsyncClient, auth_headers, seed_data, narcotic_drug_seed, cleanup_narcotics
):
    create_resp = await _create_item(client, auth_headers, narcotic_drug_seed["drug_id"])
    item_id = create_resp.json()["id"]

    # Bump version
    await client.post(
        f"{BASE}/{item_id}/dispense",
        json={"quantity": 1, "version": 1},
        headers=auth_headers,
    )

    resp = await client.post(
        f"{BASE}/{item_id}/dispense",
        json={"quantity": 1, "version": 1},
        headers=auth_headers,
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_dispense_with_patient_hash(
    client: AsyncClient, auth_headers, seed_data, narcotic_drug_seed, cleanup_narcotics
):
    create_resp = await _create_item(client, auth_headers, narcotic_drug_seed["drug_id"])
    item_id = create_resp.json()["id"]

    await client.post(
        f"{BASE}/{item_id}/dispense",
        json={
            "quantity": 3,
            "patient_hash": "abc123hash",
            "prescription_number": "RX-2026-001",
            "version": 1,
        },
        headers=auth_headers,
    )

    async with seed_session_factory() as db:
        result = await db.execute(
            select(NarcoticsTransaction).where(
                NarcoticsTransaction.narcotics_inventory_id == item_id,
                NarcoticsTransaction.transaction_type == "DISPENSE",
            )
        )
        tx = result.scalar_one_or_none()
        assert tx is not None
        assert tx.patient_hash == "abc123hash"
        assert tx.prescription_number == "RX-2026-001"


@pytest.mark.asyncio
async def test_dispense_inactive_item(
    client: AsyncClient, auth_headers, seed_data, narcotic_drug_seed, cleanup_narcotics
):
    create_resp = await _create_item(client, auth_headers, narcotic_drug_seed["drug_id"])
    item_id = create_resp.json()["id"]

    await client.request(
        "DELETE", f"{BASE}/{item_id}",
        json={"notes": "폐기", "version": 1},
        headers=auth_headers,
    )

    resp = await client.post(
        f"{BASE}/{item_id}/dispense",
        json={"quantity": 1, "version": 2},
        headers=auth_headers,
    )
    assert resp.status_code == 404


# === Return ===


@pytest.mark.asyncio
async def test_return_success(
    client: AsyncClient, auth_headers, seed_data, narcotic_drug_seed, cleanup_narcotics
):
    create_resp = await _create_item(client, auth_headers, narcotic_drug_seed["drug_id"])
    item_id = create_resp.json()["id"]

    resp = await client.post(
        f"{BASE}/{item_id}/return",
        json={"quantity": 10, "notes": "도매상 반품", "version": 1},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["current_quantity"] == 90
    assert data["version"] == 2

    async with seed_session_factory() as db:
        result = await db.execute(
            select(NarcoticsTransaction).where(
                NarcoticsTransaction.narcotics_inventory_id == item_id,
                NarcoticsTransaction.transaction_type == "RETURN",
            )
        )
        tx = result.scalar_one_or_none()
        assert tx is not None
        assert tx.quantity == -10
        assert tx.remaining_quantity == 90


@pytest.mark.asyncio
async def test_return_requires_notes(
    client: AsyncClient, auth_headers, seed_data, narcotic_drug_seed, cleanup_narcotics
):
    create_resp = await _create_item(client, auth_headers, narcotic_drug_seed["drug_id"])
    item_id = create_resp.json()["id"]

    resp = await client.post(
        f"{BASE}/{item_id}/return",
        json={"quantity": 5, "notes": "", "version": 1},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_return_insufficient_stock(
    client: AsyncClient, auth_headers, seed_data, narcotic_drug_seed, cleanup_narcotics
):
    create_resp = await _create_item(client, auth_headers, narcotic_drug_seed["drug_id"], qty=5)
    item_id = create_resp.json()["id"]

    resp = await client.post(
        f"{BASE}/{item_id}/return",
        json={"quantity": 10, "notes": "반품", "version": 1},
        headers=auth_headers,
    )
    assert resp.status_code == 400


# === Alerts ===


@pytest.mark.asyncio
async def test_create_triggers_narcotics_low_alert(
    client: AsyncClient, auth_headers, seed_data, narcotic_drug_seed, cleanup_narcotics
):
    # threshold=10, qty=5 -> NARCOTICS_LOW
    await _create_item(client, auth_headers, narcotic_drug_seed["drug_id"], qty=5)

    async with seed_session_factory() as db:
        result = await db.execute(
            select(AlertLog).where(
                AlertLog.pharmacy_id == seed_data["pharmacy_id"],
                AlertLog.alert_type == "NARCOTICS_LOW",
                AlertLog.ref_table == "narcotics_inventory",
            )
        )
        alert = result.scalar_one_or_none()
        assert alert is not None
        assert "펜타닐패치" in alert.message


@pytest.mark.asyncio
async def test_dispense_triggers_narcotics_low_alert(
    client: AsyncClient, auth_headers, seed_data, narcotic_drug_seed, cleanup_narcotics
):
    create_resp = await _create_item(client, auth_headers, narcotic_drug_seed["drug_id"], qty=15)
    item_id = create_resp.json()["id"]

    # Dispense to drop below threshold (15 - 10 = 5 < 10)
    await client.post(
        f"{BASE}/{item_id}/dispense",
        json={"quantity": 10, "version": 1},
        headers=auth_headers,
    )

    async with seed_session_factory() as db:
        result = await db.execute(
            select(AlertLog).where(
                AlertLog.pharmacy_id == seed_data["pharmacy_id"],
                AlertLog.alert_type == "NARCOTICS_LOW",
            )
        )
        alert = result.scalar_one_or_none()
        assert alert is not None


@pytest.mark.asyncio
async def test_update_triggers_narcotics_low_alert(
    client: AsyncClient, auth_headers, seed_data, narcotic_drug_seed, cleanup_narcotics
):
    create_resp = await _create_item(client, auth_headers, narcotic_drug_seed["drug_id"], qty=50)
    item_id = create_resp.json()["id"]

    # Adjust to below threshold
    await client.put(
        f"{BASE}/{item_id}",
        json={"current_quantity": 3, "version": 1},
        headers=auth_headers,
    )

    async with seed_session_factory() as db:
        result = await db.execute(
            select(AlertLog).where(
                AlertLog.pharmacy_id == seed_data["pharmacy_id"],
                AlertLog.alert_type == "NARCOTICS_LOW",
            )
        )
        alert = result.scalar_one_or_none()
        assert alert is not None


# === Isolation ===


@pytest.mark.asyncio
async def test_cross_pharmacy_isolation(
    client: AsyncClient, auth_headers, seed_data, narcotic_drug_seed, cleanup_narcotics
):
    async with seed_session_factory() as db:
        other_pharmacy = Pharmacy(
            name="다른약국_narcotics_test",
            patient_hash_salt="other-salt",
            patient_hash_algorithm="SHA-256",
            default_alert_days_before=3,
        )
        db.add(other_pharmacy)
        await db.flush()

        other_inv = NarcoticsInventory(
            pharmacy_id=other_pharmacy.id,
            drug_id=narcotic_drug_seed["drug_id"],
            lot_number="OTHER-LOT",
            current_quantity=100,
        )
        db.add(other_inv)
        await db.commit()
        other_item_id = other_inv.id

    resp = await client.get(f"{BASE}/{other_item_id}", headers=auth_headers)
    assert resp.status_code == 404


# === Transaction History ===


@pytest.mark.asyncio
async def test_list_transactions(
    client: AsyncClient, auth_headers, seed_data, narcotic_drug_seed, cleanup_narcotics
):
    create_resp = await _create_item(client, auth_headers, narcotic_drug_seed["drug_id"])
    item_id = create_resp.json()["id"]

    # Create additional transactions
    await client.post(
        f"{BASE}/{item_id}/dispense",
        json={"quantity": 5, "version": 1},
        headers=auth_headers,
    )

    resp = await client.get(f"{BASE}/{item_id}/transactions", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2  # RECEIVE + DISPENSE
    assert len(data["transactions"]) == 2


@pytest.mark.asyncio
async def test_list_transactions_filter_by_type(
    client: AsyncClient, auth_headers, seed_data, narcotic_drug_seed, cleanup_narcotics
):
    create_resp = await _create_item(client, auth_headers, narcotic_drug_seed["drug_id"])
    item_id = create_resp.json()["id"]

    await client.post(
        f"{BASE}/{item_id}/dispense",
        json={"quantity": 5, "version": 1},
        headers=auth_headers,
    )

    resp = await client.get(
        f"{BASE}/{item_id}/transactions?transaction_type=RECEIVE",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["transactions"][0]["transaction_type"] == "RECEIVE"


# === Reactivation ===


@pytest.mark.asyncio
async def test_reactivate_soft_deleted_item(
    client: AsyncClient, auth_headers, seed_data, narcotic_drug_seed, cleanup_narcotics
):
    create_resp = await _create_item(client, auth_headers, narcotic_drug_seed["drug_id"])
    item_id = create_resp.json()["id"]

    # Dispose
    await client.request(
        "DELETE", f"{BASE}/{item_id}",
        json={"notes": "폐기", "version": 1},
        headers=auth_headers,
    )

    # Reactivate with same drug_id + lot_number
    resp = await _create_item(client, auth_headers, narcotic_drug_seed["drug_id"], qty=50)
    assert resp.status_code == 201
    data = resp.json()
    assert data["is_active"] is True
    assert data["current_quantity"] == 50
