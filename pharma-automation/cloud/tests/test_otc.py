import pytest
from httpx import AsyncClient
from sqlalchemy import select

from tests.conftest import seed_session_factory
from app.models.tables import AlertLog, InventoryAuditLog, OtcInventory


# === CRUD 기본 ===


@pytest.mark.asyncio
async def test_create_otc_item(
    client: AsyncClient, auth_headers: dict, seed_data: dict, otc_drug_seed: dict, cleanup_otc
):
    resp = await client.post(
        "/api/v1/otc-inventory",
        json={
            "drug_id": otc_drug_seed["drug_id"],
            "current_quantity": 50,
            "display_location": "A열 3번",
            "storage_location": "창고2-B",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["drug_name"] == "타이레놀"
    assert data["current_quantity"] == 50
    assert data["display_location"] == "A열 3번"
    assert data["storage_location"] == "창고2-B"
    assert data["version"] == 1
    assert data["is_low_stock"] is False


@pytest.mark.asyncio
async def test_create_duplicate_drug(
    client: AsyncClient, auth_headers: dict, seed_data: dict, otc_drug_seed: dict, cleanup_otc
):
    # 첫 번째 생성
    await client.post(
        "/api/v1/otc-inventory",
        json={"drug_id": otc_drug_seed["drug_id"], "current_quantity": 10},
        headers=auth_headers,
    )
    # 중복 생성 시도
    resp = await client.post(
        "/api/v1/otc-inventory",
        json={"drug_id": otc_drug_seed["drug_id"], "current_quantity": 20},
        headers=auth_headers,
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_invalid_drug(
    client: AsyncClient, auth_headers: dict, cleanup_otc
):
    resp = await client.post(
        "/api/v1/otc-inventory",
        json={"drug_id": 999999, "current_quantity": 10},
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_otc_items(
    client: AsyncClient, auth_headers: dict, seed_data: dict, otc_drug_seed: dict, cleanup_otc
):
    await client.post(
        "/api/v1/otc-inventory",
        json={"drug_id": otc_drug_seed["drug_id"], "current_quantity": 50},
        headers=auth_headers,
    )
    resp = await client.get("/api/v1/otc-inventory", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_list_low_stock_only(
    client: AsyncClient, auth_headers: dict, seed_data: dict, otc_drug_seed: dict, cleanup_otc
):
    # threshold=10이므로 quantity=5는 low stock
    await client.post(
        "/api/v1/otc-inventory",
        json={"drug_id": otc_drug_seed["drug_id"], "current_quantity": 5},
        headers=auth_headers,
    )
    resp = await client.get(
        "/api/v1/otc-inventory?low_stock_only=true", headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert item["is_low_stock"] is True


@pytest.mark.asyncio
async def test_get_otc_item(
    client: AsyncClient, auth_headers: dict, seed_data: dict, otc_drug_seed: dict, cleanup_otc
):
    create_resp = await client.post(
        "/api/v1/otc-inventory",
        json={"drug_id": otc_drug_seed["drug_id"], "current_quantity": 30},
        headers=auth_headers,
    )
    item_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/otc-inventory/{item_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == item_id


@pytest.mark.asyncio
async def test_get_otc_item_not_found(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/otc-inventory/999999", headers=auth_headers)
    assert resp.status_code == 404


# === 수정 + Optimistic Lock ===


@pytest.mark.asyncio
async def test_update_otc_item(
    client: AsyncClient, auth_headers: dict, seed_data: dict, otc_drug_seed: dict, cleanup_otc
):
    create_resp = await client.post(
        "/api/v1/otc-inventory",
        json={"drug_id": otc_drug_seed["drug_id"], "current_quantity": 50},
        headers=auth_headers,
    )
    item_id = create_resp.json()["id"]

    resp = await client.put(
        f"/api/v1/otc-inventory/{item_id}",
        json={"current_quantity": 30, "display_location": "B열 1번", "version": 1},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["current_quantity"] == 30
    assert data["display_location"] == "B열 1번"
    assert data["version"] == 2


@pytest.mark.asyncio
async def test_update_version_conflict(
    client: AsyncClient, auth_headers: dict, seed_data: dict, otc_drug_seed: dict, cleanup_otc
):
    create_resp = await client.post(
        "/api/v1/otc-inventory",
        json={"drug_id": otc_drug_seed["drug_id"], "current_quantity": 50},
        headers=auth_headers,
    )
    item_id = create_resp.json()["id"]

    # 첫 번째 업데이트 (version 1 → 2)
    await client.put(
        f"/api/v1/otc-inventory/{item_id}",
        json={"current_quantity": 30, "version": 1},
        headers=auth_headers,
    )
    # stale version으로 재시도
    resp = await client.put(
        f"/api/v1/otc-inventory/{item_id}",
        json={"current_quantity": 25, "version": 1},
        headers=auth_headers,
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_update_not_found(client: AsyncClient, auth_headers: dict):
    resp = await client.put(
        "/api/v1/otc-inventory/999999",
        json={"current_quantity": 10, "version": 1},
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_location_fields(
    client: AsyncClient, auth_headers: dict, seed_data: dict, otc_drug_seed: dict, cleanup_otc
):
    create_resp = await client.post(
        "/api/v1/otc-inventory",
        json={
            "drug_id": otc_drug_seed["drug_id"],
            "current_quantity": 20,
            "display_location": "원래위치",
            "storage_location": "원래창고",
        },
        headers=auth_headers,
    )
    item_id = create_resp.json()["id"]

    resp = await client.put(
        f"/api/v1/otc-inventory/{item_id}",
        json={
            "current_quantity": 20,
            "display_location": "새위치",
            "storage_location": "새창고",
            "version": 1,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["display_location"] == "새위치"
    assert data["storage_location"] == "새창고"


# === 삭제 + Audit Log (P16) ===


@pytest.mark.asyncio
async def test_delete_otc_item(
    client: AsyncClient, auth_headers: dict, seed_data: dict, otc_drug_seed: dict, cleanup_otc
):
    create_resp = await client.post(
        "/api/v1/otc-inventory",
        json={"drug_id": otc_drug_seed["drug_id"], "current_quantity": 10},
        headers=auth_headers,
    )
    item_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/v1/otc-inventory/{item_id}", headers=auth_headers)
    assert resp.status_code == 204

    # audit log에 OTC_DELETE 기록 확인
    async with seed_session_factory() as db:
        result = await db.execute(
            select(InventoryAuditLog).where(
                InventoryAuditLog.record_id == item_id,
                InventoryAuditLog.action == "OTC_DELETE",
            )
        )
        audit = result.scalar_one_or_none()
        assert audit is not None


@pytest.mark.asyncio
async def test_delete_audit_log_contents(
    client: AsyncClient, auth_headers: dict, seed_data: dict, otc_drug_seed: dict, cleanup_otc
):
    create_resp = await client.post(
        "/api/v1/otc-inventory",
        json={
            "drug_id": otc_drug_seed["drug_id"],
            "current_quantity": 15,
            "display_location": "A열",
            "storage_location": "창고1",
        },
        headers=auth_headers,
    )
    item_id = create_resp.json()["id"]

    await client.delete(f"/api/v1/otc-inventory/{item_id}", headers=auth_headers)

    async with seed_session_factory() as db:
        result = await db.execute(
            select(InventoryAuditLog).where(
                InventoryAuditLog.record_id == item_id,
                InventoryAuditLog.action == "OTC_DELETE",
            )
        )
        audit = result.scalar_one()
        old = audit.old_values
        assert old["drug_id"] == otc_drug_seed["drug_id"]
        assert old["current_quantity"] == 15
        assert old["display_location"] == "A열"
        assert old["storage_location"] == "창고1"
        assert old["version"] == 1


@pytest.mark.asyncio
async def test_delete_not_found(client: AsyncClient, auth_headers: dict):
    resp = await client.delete("/api/v1/otc-inventory/999999", headers=auth_headers)
    assert resp.status_code == 404


# === PUT 전체 덮어쓰기 (P17) ===


@pytest.mark.asyncio
async def test_update_null_clears_location(
    client: AsyncClient, auth_headers: dict, seed_data: dict, otc_drug_seed: dict, cleanup_otc
):
    create_resp = await client.post(
        "/api/v1/otc-inventory",
        json={
            "drug_id": otc_drug_seed["drug_id"],
            "current_quantity": 20,
            "display_location": "A열 3번",
            "storage_location": "창고2",
        },
        headers=auth_headers,
    )
    item_id = create_resp.json()["id"]

    # null 전송 → NULL로 저장
    resp = await client.put(
        f"/api/v1/otc-inventory/{item_id}",
        json={
            "current_quantity": 20,
            "display_location": None,
            "storage_location": None,
            "version": 1,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["display_location"] is None
    assert data["storage_location"] is None


# === LOW_STOCK 알림 ===


@pytest.mark.asyncio
async def test_create_triggers_low_stock_alert(
    client: AsyncClient, auth_headers: dict, seed_data: dict, otc_drug_seed: dict, cleanup_otc
):
    # threshold=10, quantity=5 → LOW_STOCK
    resp = await client.post(
        "/api/v1/otc-inventory",
        json={"drug_id": otc_drug_seed["drug_id"], "current_quantity": 5},
        headers=auth_headers,
    )
    assert resp.status_code == 201

    async with seed_session_factory() as db:
        result = await db.execute(
            select(AlertLog).where(
                AlertLog.pharmacy_id == seed_data["pharmacy_id"],
                AlertLog.alert_type == "LOW_STOCK",
                AlertLog.ref_table == "otc_inventory",
            )
        )
        alert = result.scalar_one_or_none()
        assert alert is not None
        assert "타이레놀" in alert.message


@pytest.mark.asyncio
async def test_update_triggers_low_stock_alert(
    client: AsyncClient, auth_headers: dict, seed_data: dict, otc_drug_seed: dict, cleanup_otc
):
    create_resp = await client.post(
        "/api/v1/otc-inventory",
        json={"drug_id": otc_drug_seed["drug_id"], "current_quantity": 50},
        headers=auth_headers,
    )
    item_id = create_resp.json()["id"]

    # 수량을 threshold(10) 이하로 수정
    resp = await client.put(
        f"/api/v1/otc-inventory/{item_id}",
        json={"current_quantity": 3, "version": 1},
        headers=auth_headers,
    )
    assert resp.status_code == 200

    async with seed_session_factory() as db:
        result = await db.execute(
            select(AlertLog).where(
                AlertLog.pharmacy_id == seed_data["pharmacy_id"],
                AlertLog.alert_type == "LOW_STOCK",
                AlertLog.ref_table == "otc_inventory",
            )
        )
        alert = result.scalar_one_or_none()
        assert alert is not None


# === 데이터 격리 ===


@pytest.mark.asyncio
async def test_cross_pharmacy_isolation(
    client: AsyncClient, auth_headers: dict, seed_data: dict, otc_drug_seed: dict, cleanup_otc
):
    # 다른 약국에 직접 OTC 항목 삽입
    async with seed_session_factory() as db:
        other_pharmacy = Pharmacy(
            name="다른약국_otc_test",
            patient_hash_salt="other-salt",
            patient_hash_algorithm="SHA-256",
            default_alert_days_before=3,
        )
        db.add(other_pharmacy)
        await db.flush()

        other_inv = OtcInventory(
            pharmacy_id=other_pharmacy.id,
            drug_id=otc_drug_seed["drug_id"],
            current_quantity=100,
        )
        db.add(other_inv)
        await db.commit()
        other_item_id = other_inv.id

    # JWT는 테스트약국 소속 → 다른 약국 item 접근 불가
    resp = await client.get(
        f"/api/v1/otc-inventory/{other_item_id}", headers=auth_headers
    )
    assert resp.status_code == 404


# import for cross_pharmacy test
from app.models.tables import Pharmacy
