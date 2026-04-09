"""Contract test: agent1 → cloud sync endpoint.

Verifies that the payload format agent1 actually sends (DrugStockItem dataclass
→ dict) is accepted by the cloud Pydantic schema (SyncDrugStockRequest).

This is the single most valuable test not previously in the suite — if someone
renames a field in the Pydantic schema, all other cloud tests still pass
(they construct schemas directly), all agent1 tests still pass (they mock HTTP),
and production breaks. This test catches that.
"""
import time

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.models.tables import Drug, DrugStock
from tests.conftest import seed_session_factory

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture(autouse=True)
async def cleanup_contract_data(seed_data):
    """Clean drug_stock created by contract tests."""
    yield
    async with seed_session_factory() as db:
        await db.execute(
            DrugStock.__table__.delete().where(
                DrugStock.pharmacy_id == seed_data["pharmacy_id"]
            )
        )
        await db.commit()


async def _ensure_drugs(count: int) -> list[dict]:
    """Ensure N drugs exist in DB and return their standard_codes + names."""
    suffix = str(int(time.time()))[-6:]
    drugs_out = []
    async with seed_session_factory() as db:
        for i in range(count):
            code = f"CONTRACT_{suffix}_{i:03d}"
            result = await db.execute(select(Drug).where(Drug.standard_code == code))
            drug = result.scalar_one_or_none()
            if not drug:
                drug = Drug(
                    standard_code=code,
                    name=f"계약테스트약품{i}",
                    category="PRESCRIPTION",
                )
                db.add(drug)
        await db.commit()

        # Re-fetch to get IDs
        for i in range(count):
            code = f"CONTRACT_{suffix}_{i:03d}"
            result = await db.execute(select(Drug).where(Drug.standard_code == code))
            drug = result.scalar_one()
            drugs_out.append({
                "id": drug.id,
                "standard_code": drug.standard_code,
                "name": drug.name,
            })
    return drugs_out


class TestDrugStockSyncContract:
    """Verify agent1's DrugStockItem shape matches cloud's SyncDrugStockRequest."""

    async def test_50_item_sync_matches_schema(
        self, client: AsyncClient, seed_data: dict
    ):
        """Agent1 sends 50 DrugStockItems; cloud accepts and persists all 50."""
        drugs = await _ensure_drugs(50)

        # Build the payload exactly as agent1's CloudClient would:
        # agent1 reads DrugStockItem dataclass fields → dict → json
        # Fields: drug_standard_code, current_quantity, is_narcotic
        items = [
            {
                "drug_standard_code": d["standard_code"],
                "current_quantity": 100.0 + i,
            }
            for i, d in enumerate(drugs)
        ]

        resp = await client.post(
            "/api/v1/sync/drug-stock",
            headers={"X-API-Key": seed_data["api_key"]},
            json={
                "items": items,
                "synced_at": "2026-04-09T00:00:00Z",
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["synced_count"] == 50
        assert data["skipped_count"] == 0

        # Verify all 50 records exist in DB with correct values
        async with seed_session_factory() as db:
            result = await db.execute(
                select(DrugStock).where(
                    DrugStock.pharmacy_id == seed_data["pharmacy_id"]
                )
            )
            stock_rows = result.scalars().all()
            stock_by_drug = {s.drug_id: s for s in stock_rows}

            for i, d in enumerate(drugs):
                stock = stock_by_drug.get(d["id"])
                assert stock is not None, f"DrugStock missing for {d['standard_code']}"
                assert float(stock.current_quantity) == 100.0 + i
                # is_narcotic determined server-side from drug.category
                assert stock.is_narcotic is False  # test drugs are PRESCRIPTION

    async def test_field_names_match_agent1_dataclass(self, client, seed_data):
        """Verify the exact field names agent1 uses are accepted.

        agent1.agent.interfaces.pm20_reader.DrugStockItem has:
          - drug_standard_code: str
          - drug_name: str          (NOT sent in sync — cloud looks up by code)
          - current_quantity: float
          - is_narcotic: bool

        Cloud's DrugStockItemIn expects:
          - drug_standard_code: str
          - current_quantity: float
          - is_narcotic: bool = False

        This test sends the minimal required fields and verifies acceptance.
        """
        drugs = await _ensure_drugs(1)
        resp = await client.post(
            "/api/v1/sync/drug-stock",
            headers={"X-API-Key": seed_data["api_key"]},
            json={
                "items": [
                    {
                        "drug_standard_code": drugs[0]["standard_code"],
                        "current_quantity": 42.5,
                        # is_narcotic omitted — should default to False
                    }
                ],
                "synced_at": "2026-04-09T00:00:00Z",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["synced_count"] == 1

    async def test_negative_quantity_accepted(self, client, seed_data):
        """Agent1 sends negative TEMP_STOCK quantities (deficit). Cloud must accept."""
        drugs = await _ensure_drugs(1)
        resp = await client.post(
            "/api/v1/sync/drug-stock",
            headers={"X-API-Key": seed_data["api_key"]},
            json={
                "items": [
                    {
                        "drug_standard_code": drugs[0]["standard_code"],
                        "current_quantity": -5.0,
                        "is_narcotic": False,
                    }
                ],
                "synced_at": "2026-04-09T00:00:00Z",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["synced_count"] == 1

    async def test_unknown_drug_code_skipped_not_500(self, client, seed_data):
        """Agent1 may send codes for drugs not yet synced. Cloud skips, not 500."""
        resp = await client.post(
            "/api/v1/sync/drug-stock",
            headers={"X-API-Key": seed_data["api_key"]},
            json={
                "items": [
                    {
                        "drug_standard_code": "DOES_NOT_EXIST_99999",
                        "current_quantity": 10.0,
                    }
                ],
                "synced_at": "2026-04-09T00:00:00Z",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["synced_count"] == 0
        assert resp.json()["skipped_count"] == 1

    async def test_wrong_api_key_rejected(self, client):
        """Agent1 with wrong API key is rejected before reaching sync logic."""
        resp = await client.post(
            "/api/v1/sync/drug-stock",
            headers={"X-API-Key": "wrong-key"},
            json={
                "items": [],
                "synced_at": "2026-04-09T00:00:00Z",
            },
        )
        assert resp.status_code == 401
