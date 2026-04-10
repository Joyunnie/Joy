"""Tests for GET /api/v1/inventory/status — prescription inventory status.

Covers: empty pharmacy, items with/without thresholds, low_stock_only filter,
auth required, item ordering by cassette_number.
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.models.tables import Drug, DrugThreshold, PrescriptionInventory
from tests.conftest import seed_session_factory

pytestmark = pytest.mark.asyncio

BASE = "/api/v1/inventory/status"


@pytest_asyncio.fixture(autouse=True)
async def cleanup_inventory(seed_data):
    """Clean prescription_inventory before/after each test."""
    pid = seed_data["pharmacy_id"]
    async with seed_session_factory() as db:
        await db.execute(
            PrescriptionInventory.__table__.delete().where(
                PrescriptionInventory.pharmacy_id == pid
            )
        )
        await db.commit()
    yield
    async with seed_session_factory() as db:
        await db.execute(
            PrescriptionInventory.__table__.delete().where(
                PrescriptionInventory.pharmacy_id == pid
            )
        )
        await db.commit()


async def _get_drug_id(code: str) -> int:
    """Get or create a drug by standard_code."""
    async with seed_session_factory() as db:
        result = await db.execute(select(Drug).where(Drug.standard_code == code))
        drug = result.scalar_one_or_none()
        if not drug:
            drug = Drug(standard_code=code, name=f"Drug_{code}", category="PRESCRIPTION")
            db.add(drug)
            await db.flush()
        await db.commit()
        return drug.id


async def _seed_inventory(pharmacy_id: int, cassette: int, drug_code: str, qty: int) -> None:
    drug_id = await _get_drug_id(drug_code)
    async with seed_session_factory() as db:
        db.add(PrescriptionInventory(
            pharmacy_id=pharmacy_id,
            drug_id=drug_id,
            cassette_number=cassette,
            current_quantity=qty,
        ))
        await db.commit()


async def _seed_threshold(pharmacy_id: int, drug_code: str, min_qty: int) -> None:
    drug_id = await _get_drug_id(drug_code)
    async with seed_session_factory() as db:
        result = await db.execute(
            select(DrugThreshold).where(
                DrugThreshold.pharmacy_id == pharmacy_id,
                DrugThreshold.drug_id == drug_id,
            )
        )
        if not result.scalar_one_or_none():
            db.add(DrugThreshold(
                pharmacy_id=pharmacy_id,
                drug_id=drug_id,
                min_quantity=min_qty,
                is_active=True,
            ))
            await db.commit()


class TestInventoryStatus:
    async def test_empty_returns_empty_list(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get(BASE, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []

    async def test_returns_items_with_drug_name(
        self, client: AsyncClient, auth_headers: dict, seed_data: dict,
    ):
        pid = seed_data["pharmacy_id"]
        await _seed_inventory(pid, 1, "INV_TEST_01", 100)

        resp = await client.get(BASE, headers=auth_headers)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["cassette_number"] == 1
        assert items[0]["current_quantity"] == 100
        assert items[0]["drug_name"] is not None

    async def test_ordered_by_cassette_number(
        self, client: AsyncClient, auth_headers: dict, seed_data: dict,
    ):
        pid = seed_data["pharmacy_id"]
        await _seed_inventory(pid, 50, "INV_TEST_02", 10)
        await _seed_inventory(pid, 5, "INV_TEST_03", 20)
        await _seed_inventory(pid, 100, "INV_TEST_04", 30)

        resp = await client.get(BASE, headers=auth_headers)
        numbers = [i["cassette_number"] for i in resp.json()["items"]]
        assert numbers == [5, 50, 100]

    async def test_low_stock_flag_with_threshold(
        self, client: AsyncClient, auth_headers: dict, seed_data: dict,
    ):
        pid = seed_data["pharmacy_id"]
        await _seed_inventory(pid, 1, "INV_LOW_01", 3)
        await _seed_threshold(pid, "INV_LOW_01", 10)

        resp = await client.get(BASE, headers=auth_headers)
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["is_low_stock"] is True
        assert items[0]["min_quantity"] == 10

    async def test_not_low_stock_when_above_threshold(
        self, client: AsyncClient, auth_headers: dict, seed_data: dict,
    ):
        pid = seed_data["pharmacy_id"]
        await _seed_inventory(pid, 1, "INV_HIGH_01", 50)
        await _seed_threshold(pid, "INV_HIGH_01", 10)

        resp = await client.get(BASE, headers=auth_headers)
        items = resp.json()["items"]
        assert items[0]["is_low_stock"] is False

    async def test_no_threshold_means_not_low_stock(
        self, client: AsyncClient, auth_headers: dict, seed_data: dict,
    ):
        pid = seed_data["pharmacy_id"]
        await _seed_inventory(pid, 1, "INV_NOTH_01", 1)

        resp = await client.get(BASE, headers=auth_headers)
        items = resp.json()["items"]
        assert items[0]["is_low_stock"] is False
        assert items[0]["min_quantity"] is None

    async def test_low_stock_only_filter(
        self, client: AsyncClient, auth_headers: dict, seed_data: dict,
    ):
        pid = seed_data["pharmacy_id"]
        await _seed_inventory(pid, 1, "INV_FILT_LOW", 2)
        await _seed_threshold(pid, "INV_FILT_LOW", 10)
        await _seed_inventory(pid, 2, "INV_FILT_OK", 50)
        await _seed_threshold(pid, "INV_FILT_OK", 10)

        # Without filter: both items
        resp = await client.get(BASE, headers=auth_headers)
        assert len(resp.json()["items"]) == 2

        # With filter: only low stock
        resp = await client.get(BASE, params={"low_stock_only": True}, headers=auth_headers)
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["cassette_number"] == 1

    async def test_requires_auth(self, client: AsyncClient):
        resp = await client.get(BASE)
        assert resp.status_code in (401, 403)
