"""Tests for sync endpoint Pydantic validation.

Covers: negative inventory quantity rejected, zero/negative visit drug
quantity rejected.
"""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestSyncInventoryValidation:
    async def test_negative_quantity_rejected(self, client: AsyncClient, seed_data: dict):
        """POST /sync/inventory with current_quantity=-1 returns 422."""
        resp = await client.post(
            "/api/v1/sync/inventory",
            headers={"X-API-Key": seed_data["api_key"]},
            json={
                "items": [
                    {
                        "cassette_number": 1,
                        "current_quantity": -1,
                    }
                ],
                "synced_at": "2026-04-11T12:00:00Z",
            },
        )
        assert resp.status_code == 422


class TestSyncVisitDrugValidation:
    async def test_zero_quantity_dispensed_rejected(self, client: AsyncClient, seed_data: dict):
        """POST /sync/visits with quantity_dispensed=0 returns 422."""
        resp = await client.post(
            "/api/v1/sync/visits",
            headers={"X-API-Key": seed_data["api_key"]},
            json={
                "visits": [
                    {
                        "patient_hash": "a" * 64,
                        "visit_date": "2026-04-11",
                        "prescription_days": 7,
                        "drugs": [
                            {
                                "drug_insurance_code": "999999999",
                                "quantity_dispensed": 0,
                            }
                        ],
                    }
                ]
            },
        )
        assert resp.status_code == 422

    async def test_negative_quantity_dispensed_rejected(self, client: AsyncClient, seed_data: dict):
        """POST /sync/visits with quantity_dispensed=-5 returns 422."""
        resp = await client.post(
            "/api/v1/sync/visits",
            headers={"X-API-Key": seed_data["api_key"]},
            json={
                "visits": [
                    {
                        "patient_hash": "b" * 64,
                        "visit_date": "2026-04-11",
                        "prescription_days": 7,
                        "drugs": [
                            {
                                "drug_insurance_code": "999999999",
                                "quantity_dispensed": -5,
                            }
                        ],
                    }
                ]
            },
        )
        assert resp.status_code == 422
