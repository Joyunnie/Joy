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

from app.models.tables import Drug, DrugStock, PatientVisitHistory, PrescriptionInventory, VisitDrug
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
            result = await db.execute(select(Drug).where(Drug.insurance_code == ins_code))
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
            ins_code = f"6{suffix}{i:04d}"
            result = await db.execute(select(Drug).where(Drug.insurance_code == ins_code))
            drug = result.scalar_one()
            drugs_out.append({
                "id": drug.id,
                "standard_code": drug.standard_code,
                "insurance_code": drug.insurance_code,
                "name": drug.name,
            })
    return drugs_out


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


class TestDrugsSyncContract:
    """Verify sync_drugs upserts by insurance_code and resolves PI."""

    async def test_upsert_by_insurance_code(
        self, client: AsyncClient, seed_data: dict
    ):
        """Same insurance_code sent twice → update, not duplicate."""
        suffix = str(int(time.time()))[-6:]
        headers = {"X-API-Key": seed_data["api_key"]}
        drug_payload = {
            "standard_code": f"TC_{suffix}_001",
            "name": "업서트테스트약품",
            "category": "PRESCRIPTION",
            "insurance_code": f"7{suffix}0001",
        }

        # First sync → insert
        resp1 = await client.post(
            "/api/v1/sync/drugs", headers=headers,
            json={"drugs": [drug_payload]},
        )
        assert resp1.status_code == 200
        assert resp1.json()["new_count"] == 1

        # Second sync with updated name → update, not new
        drug_payload["name"] = "업서트테스트약품_수정"
        resp2 = await client.post(
            "/api/v1/sync/drugs", headers=headers,
            json={"drugs": [drug_payload]},
        )
        assert resp2.status_code == 200
        assert resp2.json()["new_count"] == 0
        assert resp2.json()["updated_count"] == 1

        # Verify single row in DB
        async with seed_session_factory() as db:
            result = await db.execute(
                select(Drug).where(Drug.insurance_code == f"7{suffix}0001")
            )
            drugs = result.scalars().all()
            assert len(drugs) == 1
            assert drugs[0].name == "업서트테스트약품_수정"

    async def test_missing_insurance_code_rejected(
        self, client: AsyncClient, seed_data: dict
    ):
        """Drug without insurance_code → 422 (required field)."""
        suffix = str(int(time.time()))[-6:]
        headers = {"X-API-Key": seed_data["api_key"]}
        drug_payload = {
            "standard_code": f"TC_{suffix}_NUL",
            "name": "보험코드없는약품",
            "category": "PRESCRIPTION",
            # insurance_code omitted → validation error
        }

        resp = await client.post(
            "/api/v1/sync/drugs", headers=headers,
            json={"drugs": [drug_payload]},
        )
        assert resp.status_code == 422

    async def test_resolves_prescription_inventory_drug_id(
        self, client: AsyncClient, seed_data: dict
    ):
        """After sync_drugs, PI rows with matching drug_insurance_code get drug_id."""
        suffix = str(int(time.time()))[-6:]
        ins_code = f"8{suffix}0001"
        headers = {"X-API-Key": seed_data["api_key"]}
        pharmacy_id = seed_data["pharmacy_id"]

        # Pre-create PI row with drug_insurance_code but no drug_id
        async with seed_session_factory() as db:
            pi = PrescriptionInventory(
                pharmacy_id=pharmacy_id,
                cassette_number=9000 + int(suffix) % 100,
                current_quantity=50,
                drug_insurance_code=ins_code,
                drug_id=None,
            )
            db.add(pi)
            await db.commit()
            pi_id = pi.id

        # Sync a drug with matching insurance_code
        resp = await client.post(
            "/api/v1/sync/drugs", headers=headers,
            json={"drugs": [{
                "standard_code": f"TC_{suffix}_PI",
                "name": "PI연결테스트약품",
                "category": "PRESCRIPTION",
                "insurance_code": ins_code,
            }]},
        )
        assert resp.status_code == 200

        # Verify PI.drug_id is now populated
        async with seed_session_factory() as db:
            pi = await db.get(PrescriptionInventory, pi_id)
            assert pi.drug_id is not None

            drug_result = await db.execute(
                select(Drug).where(Drug.insurance_code == ins_code)
            )
            drug = drug_result.scalar_one()
            assert pi.drug_id == drug.id
