"""shelf_layouts CRUD + batch-location 엔드포인트 테스트."""

import pytest

from app.models.tables import Drug, OtcInventory, ShelfLayout
from tests.conftest import seed_session_factory

from sqlalchemy import select


# ---------- helpers ----------

async def _get_drug_id(standard_code: str) -> int:
    async with seed_session_factory() as db:
        result = await db.execute(
            select(Drug).where(Drug.standard_code == standard_code)
        )
        return result.scalar_one().id


async def _seed_layout(pharmacy_id: int, name: str, location_type: str, rows: int = 4, cols: int = 6) -> int:
    async with seed_session_factory() as db:
        layout = ShelfLayout(
            pharmacy_id=pharmacy_id,
            name=name,
            location_type=location_type,
            rows=rows,
            cols=cols,
        )
        db.add(layout)
        await db.flush()
        layout_id = layout.id
        await db.commit()
        return layout_id


async def _seed_otc_item(pharmacy_id: int, drug_id: int, display_location: str | None = None, storage_location: str | None = None) -> int:
    async with seed_session_factory() as db:
        # 기존 항목 확인
        result = await db.execute(
            select(OtcInventory).where(
                OtcInventory.pharmacy_id == pharmacy_id,
                OtcInventory.drug_id == drug_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.display_location = display_location
            existing.storage_location = storage_location
            await db.commit()
            return existing.id

        inv = OtcInventory(
            pharmacy_id=pharmacy_id,
            drug_id=drug_id,
            current_quantity=100,
            display_location=display_location,
            storage_location=storage_location,
        )
        db.add(inv)
        await db.flush()
        inv_id = inv.id
        await db.commit()
        return inv_id


# ---------- SHELF LAYOUT CRUD ----------

@pytest.mark.asyncio
async def test_create_layout(client, auth_headers, seed_data, cleanup_shelf_layouts):
    resp = await client.post(
        "/api/v1/shelf-layouts",
        json={"name": "매장 약장 A", "location_type": "DISPLAY", "rows": 4, "cols": 6},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "매장 약장 A"
    assert body["location_type"] == "DISPLAY"
    assert body["rows"] == 4
    assert body["cols"] == 6


@pytest.mark.asyncio
async def test_create_layout_invalid_type(client, auth_headers, seed_data):
    resp = await client.post(
        "/api/v1/shelf-layouts",
        json={"name": "Invalid", "location_type": "INVALID", "rows": 4, "cols": 6},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_layout_invalid_rows(client, auth_headers, seed_data):
    resp = await client.post(
        "/api/v1/shelf-layouts",
        json={"name": "Bad", "location_type": "DISPLAY", "rows": 0, "cols": 6},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_layouts(client, auth_headers, seed_data, cleanup_shelf_layouts):
    await _seed_layout(seed_data["pharmacy_id"], "매장 A", "DISPLAY")
    await _seed_layout(seed_data["pharmacy_id"], "창고 B", "STORAGE")

    resp = await client.get("/api/v1/shelf-layouts", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 2


@pytest.mark.asyncio
async def test_list_layouts_filter(client, auth_headers, seed_data, cleanup_shelf_layouts):
    await _seed_layout(seed_data["pharmacy_id"], "매장 A", "DISPLAY")
    await _seed_layout(seed_data["pharmacy_id"], "창고 B", "STORAGE")

    resp = await client.get(
        "/api/v1/shelf-layouts", params={"location_type": "DISPLAY"}, headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["location_type"] == "DISPLAY"


@pytest.mark.asyncio
async def test_update_layout(client, auth_headers, seed_data, cleanup_shelf_layouts):
    layout_id = await _seed_layout(seed_data["pharmacy_id"], "Old Name", "DISPLAY")

    resp = await client.put(
        f"/api/v1/shelf-layouts/{layout_id}",
        json={"name": "New Name", "rows": 5, "cols": 8},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "New Name"
    assert body["rows"] == 5
    assert body["cols"] == 8


@pytest.mark.asyncio
async def test_update_layout_not_found(client, auth_headers, seed_data):
    resp = await client.put(
        "/api/v1/shelf-layouts/999999",
        json={"name": "X", "rows": 4, "cols": 6},
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_layout(client, auth_headers, seed_data, cleanup_shelf_layouts):
    layout_id = await _seed_layout(seed_data["pharmacy_id"], "To Delete", "DISPLAY")

    resp = await client.delete(f"/api/v1/shelf-layouts/{layout_id}", headers=auth_headers)
    assert resp.status_code == 204

    list_resp = await client.get("/api/v1/shelf-layouts", headers=auth_headers)
    assert all(item["id"] != layout_id for item in list_resp.json()["items"])


@pytest.mark.asyncio
async def test_delete_layout_clears_locations(client, auth_headers, seed_data, cleanup_shelf_layouts, cleanup_otc, otc_drug_seed):
    """P26: 레이아웃 삭제 시 해당 layout을 참조하는 otc_inventory 위치가 null로 초기화."""
    layout_id = await _seed_layout(seed_data["pharmacy_id"], "To Delete", "DISPLAY")
    drug_id = otc_drug_seed["drug_id"]

    # 약품을 해당 레이아웃에 배치
    otc_id = await _seed_otc_item(
        seed_data["pharmacy_id"], drug_id,
        display_location=f"{layout_id}:1,2",
    )

    # 레이아웃 삭제
    resp = await client.delete(f"/api/v1/shelf-layouts/{layout_id}", headers=auth_headers)
    assert resp.status_code == 204

    # 약품의 display_location이 null인지 확인
    item_resp = await client.get(f"/api/v1/otc-inventory/{otc_id}", headers=auth_headers)
    assert item_resp.status_code == 200
    assert item_resp.json()["display_location"] is None


@pytest.mark.asyncio
async def test_delete_layout_not_found(client, auth_headers, seed_data):
    resp = await client.delete("/api/v1/shelf-layouts/999999", headers=auth_headers)
    assert resp.status_code == 404


# ---------- BATCH LOCATION ----------

@pytest.mark.asyncio
async def test_batch_location(client, auth_headers, seed_data, cleanup_shelf_layouts, cleanup_otc, otc_drug_seed):
    layout_id = await _seed_layout(seed_data["pharmacy_id"], "매장 A", "DISPLAY")
    drug_id = otc_drug_seed["drug_id"]
    otc_id = await _seed_otc_item(seed_data["pharmacy_id"], drug_id)

    resp = await client.post(
        "/api/v1/otc-inventory/batch-location",
        json={
            "layout_id": layout_id,
            "assignments": [{"item_id": otc_id, "row": 2, "col": 3}],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["display_location"] == f"{layout_id}:2,3"


@pytest.mark.asyncio
async def test_batch_location_out_of_bounds(client, auth_headers, seed_data, cleanup_shelf_layouts, cleanup_otc, otc_drug_seed):
    layout_id = await _seed_layout(seed_data["pharmacy_id"], "Small", "DISPLAY", rows=2, cols=2)
    drug_id = otc_drug_seed["drug_id"]
    otc_id = await _seed_otc_item(seed_data["pharmacy_id"], drug_id)

    resp = await client.post(
        "/api/v1/otc-inventory/batch-location",
        json={
            "layout_id": layout_id,
            "assignments": [{"item_id": otc_id, "row": 5, "col": 0}],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_batch_location_duplicate_position(client, auth_headers, seed_data, cleanup_shelf_layouts, cleanup_otc, otc_drug_seed):
    layout_id = await _seed_layout(seed_data["pharmacy_id"], "매장 A", "DISPLAY")
    drug_id = otc_drug_seed["drug_id"]
    otc_id = await _seed_otc_item(seed_data["pharmacy_id"], drug_id)

    resp = await client.post(
        "/api/v1/otc-inventory/batch-location",
        json={
            "layout_id": layout_id,
            "assignments": [
                {"item_id": otc_id, "row": 1, "col": 1},
                {"item_id": otc_id, "row": 1, "col": 1},
            ],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_batch_location_remove(client, auth_headers, seed_data, cleanup_shelf_layouts, cleanup_otc, otc_drug_seed):
    layout_id = await _seed_layout(seed_data["pharmacy_id"], "매장 A", "DISPLAY")
    drug_id = otc_drug_seed["drug_id"]
    otc_id = await _seed_otc_item(
        seed_data["pharmacy_id"], drug_id,
        display_location=f"{layout_id}:1,2",
    )

    resp = await client.post(
        "/api/v1/otc-inventory/batch-location-remove",
        json={"layout_id": layout_id, "item_ids": [otc_id]},
        headers=auth_headers,
    )
    assert resp.status_code == 204

    # 위치가 null인지 확인
    item_resp = await client.get(f"/api/v1/otc-inventory/{otc_id}", headers=auth_headers)
    assert item_resp.json()["display_location"] is None


@pytest.mark.asyncio
async def test_list_otc_by_layout(client, auth_headers, seed_data, cleanup_shelf_layouts, cleanup_otc, otc_drug_seed):
    layout_id = await _seed_layout(seed_data["pharmacy_id"], "매장 A", "DISPLAY")
    drug_id = otc_drug_seed["drug_id"]
    await _seed_otc_item(
        seed_data["pharmacy_id"], drug_id,
        display_location=f"{layout_id}:0,0",
    )

    resp = await client.get(
        "/api/v1/otc-inventory",
        params={"layout_id": layout_id},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["display_location"] == f"{layout_id}:0,0"


@pytest.mark.asyncio
async def test_list_otc_unplaced(client, auth_headers, seed_data, cleanup_shelf_layouts, cleanup_otc, otc_drug_seed):
    layout_id = await _seed_layout(seed_data["pharmacy_id"], "매장 A", "DISPLAY")
    drug_id = otc_drug_seed["drug_id"]
    await _seed_otc_item(seed_data["pharmacy_id"], drug_id)  # no location set

    resp = await client.get(
        "/api/v1/otc-inventory",
        params={"unplaced_for_layout": layout_id},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


@pytest.mark.asyncio
async def test_update_layout_shrink_clears_locations(client, auth_headers, seed_data, cleanup_shelf_layouts, cleanup_otc, otc_drug_seed):
    """격자 축소 시 범위 밖 약품 위치가 null로 초기화."""
    layout_id = await _seed_layout(seed_data["pharmacy_id"], "Big", "DISPLAY", rows=5, cols=5)
    drug_id = otc_drug_seed["drug_id"]
    otc_id = await _seed_otc_item(
        seed_data["pharmacy_id"], drug_id,
        display_location=f"{layout_id}:4,3",  # row=4 will be out of bounds after shrink to 3 rows
    )

    # 축소
    resp = await client.put(
        f"/api/v1/shelf-layouts/{layout_id}",
        json={"name": "Small", "rows": 3, "cols": 5},
        headers=auth_headers,
    )
    assert resp.status_code == 200

    # 약품 위치 확인
    item_resp = await client.get(f"/api/v1/otc-inventory/{otc_id}", headers=auth_headers)
    assert item_resp.json()["display_location"] is None
