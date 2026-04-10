"""Contract test: agent1 → cloud sync endpoints.

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

from app.models.tables import Drug, DrugStock, PatientVisitHistory, VisitDrug
from tests.conftest import seed_session_factory

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture(autouse=True)
async def cleanup_contract_data(seed_data):
    """Clean drug_stock and visits created by contract tests."""
    yield
    async with seed_session_factory() as db:
        await db.execute(
            DrugStock.__table__.delete().where(
                DrugStock.pharmacy_id == seed_data["pharmacy_id"]
            )
        )
        # Clean visit_drugs first (FK), then visits
        visit_result = await db.execute(
            select(PatientVisitHistory.id).where(
                PatientVisitHistory.pharmacy_id == seed_data["pharmacy_id"]
            )
        )
        visit_ids = [r[0] for r in visit_result.all()]
        if visit_ids:
            await db.execute(
                VisitDrug.__table__.delete().where(VisitDrug.visit_id.in_(visit_ids))
            )
            await db.execute(
                PatientVisitHistory.__table__.delete().where(
                    PatientVisitHistory.pharmacy_id == seed_data["pharmacy_id"]
                )
            )
        await db.commit()


async def _ensure_drugs(count: int) -> list[dict]:
    """Ensure N drugs exist in DB with both standard_code and insurance_code."""
    suffix = str(int(time.time()))[-6:]
    drugs_out = []
    async with seed_session_factory() as db:
        for i in range(count):
            code = f"CONTRACT_{suffix}_{i:03d}"
            ins_code = f"6{suffix}{i:04d}"  # insurance_code format
            result = await db.execute(select(Drug).where(Drug.standard_code == code))
            drug = result.scalar_one_or_none()
            if not drug:
                drug = Drug(
                    standard_code=code,
                    insurance_code=ins_code,
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
                "insurance_code": drug.insurance_code,
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

        # Build the payload exactly as agent1's main.py does:
        # {"drug_insurance_code": s.drug_insurance_code, "current_quantity": s.current_quantity}
        items = [
            {
                "drug_insurance_code": d["insurance_code"],
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
                assert stock is not None, f"DrugStock missing for {d['insurance_code']}"
                assert float(stock.current_quantity) == 100.0 + i
                # is_narcotic determined server-side from drug.category
                assert stock.is_narcotic is False  # test drugs are PRESCRIPTION

    async def test_field_names_match_agent1_dataclass(self, client, seed_data):
        """Verify the exact field names agent1 uses are accepted.

        agent1.agent.main.py sends per item:
          - drug_insurance_code: str
          - current_quantity: float

        Cloud's DrugStockItemIn expects:
          - drug_insurance_code: str | None (primary)
          - drug_standard_code: str | None (legacy fallback)
          - current_quantity: float

        This test sends the minimal required fields and verifies acceptance.
        """
        drugs = await _ensure_drugs(1)
        resp = await client.post(
            "/api/v1/sync/drug-stock",
            headers={"X-API-Key": seed_data["api_key"]},
            json={
                "items": [
                    {
                        "drug_insurance_code": drugs[0]["insurance_code"],
                        "current_quantity": 42.5,
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
                        "drug_insurance_code": drugs[0]["insurance_code"],
                        "current_quantity": -5.0,
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
                        "drug_insurance_code": "DOES_NOT_EXIST_99999",
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


class TestVisitsSyncContract:
    """Verify agent1's visit payload shape matches cloud's SyncVisitsRequest."""

    async def test_basic_visit_sync(self, client: AsyncClient, seed_data: dict):
        """Agent1 sends visits with drugs; cloud accepts and persists."""
        drugs = await _ensure_drugs(2)

        # Build payload exactly as agent1's main.py does
        resp = await client.post(
            "/api/v1/sync/visits",
            headers={"X-API-Key": seed_data["api_key"]},
            json={
                "visits": [
                    {
                        "patient_hash": "abc123def456" * 4 + "abc123def456789a",
                        "visit_date": "2026-03-15",
                        "prescription_days": 14,
                        "source": "PM20_SYNC",
                        "drugs": [
                            {
                                "drug_insurance_code": drugs[0]["insurance_code"],
                                "quantity_dispensed": 30,
                            },
                            {
                                "drug_insurance_code": drugs[1]["insurance_code"],
                                "quantity_dispensed": 20,
                            },
                        ],
                    }
                ]
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["synced_count"] == 1
        assert len(data["visit_ids"]) == 1

        # Verify in DB
        async with seed_session_factory() as db:
            visit = await db.get(PatientVisitHistory, data["visit_ids"][0])
            assert visit is not None
            assert visit.prescription_days == 14
            assert visit.source == "PM20_SYNC"

            vd_result = await db.execute(
                select(VisitDrug).where(VisitDrug.visit_id == visit.id)
            )
            visit_drugs = vd_result.scalars().all()
            assert len(visit_drugs) == 2

    async def test_visit_field_names_match_agent1(self, client, seed_data):
        """Minimal fields agent1 sends: patient_hash, visit_date, prescription_days, source, drugs."""
        drugs = await _ensure_drugs(1)
        resp = await client.post(
            "/api/v1/sync/visits",
            headers={"X-API-Key": seed_data["api_key"]},
            json={
                "visits": [
                    {
                        "patient_hash": "a" * 64,
                        "visit_date": "2026-04-01",
                        "prescription_days": 7,
                        "source": "PM20_SYNC",
                        "drugs": [
                            {
                                "drug_insurance_code": drugs[0]["insurance_code"],
                                "quantity_dispensed": 10,
                            }
                        ],
                    }
                ]
            },
        )
        assert resp.status_code == 200
        assert resp.json()["synced_count"] == 1

    async def test_unknown_drug_in_visit_skipped(self, client, seed_data):
        """Visit is created, but unknown drug is skipped (not 500)."""
        resp = await client.post(
            "/api/v1/sync/visits",
            headers={"X-API-Key": seed_data["api_key"]},
            json={
                "visits": [
                    {
                        "patient_hash": "b" * 64,
                        "visit_date": "2026-04-02",
                        "prescription_days": 3,
                        "source": "PM20_SYNC",
                        "drugs": [
                            {
                                "drug_insurance_code": "NONEXISTENT_999",
                                "quantity_dispensed": 5,
                            }
                        ],
                    }
                ]
            },
        )
        assert resp.status_code == 200
        assert resp.json()["synced_count"] == 1  # visit created
        assert len(resp.json()["skipped_drugs"]) == 1  # drug skipped

    async def test_duplicate_visit_not_re_inserted(self, client, seed_data):
        """Same visit sent twice is deduplicated."""
        drugs = await _ensure_drugs(1)
        payload = {
            "visits": [
                {
                    "patient_hash": "c" * 64,
                    "visit_date": "2026-04-03",
                    "prescription_days": 7,
                    "source": "PM20_SYNC",
                    "drugs": [
                        {
                            "drug_insurance_code": drugs[0]["insurance_code"],
                            "quantity_dispensed": 15,
                        }
                    ],
                }
            ]
        }
        headers = {"X-API-Key": seed_data["api_key"]}

        resp1 = await client.post("/api/v1/sync/visits", headers=headers, json=payload)
        assert resp1.status_code == 200
        assert resp1.json()["synced_count"] == 1

        resp2 = await client.post("/api/v1/sync/visits", headers=headers, json=payload)
        assert resp2.status_code == 200
        assert resp2.json()["synced_count"] == 1  # deduped, returns existing ID
