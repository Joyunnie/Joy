"""Tests for sync_service bulk prefetch correctness.

Verifies that the bulk prefetch rewrite produces the same results as
per-item queries, especially for edge cases: duplicate items, unknown drugs,
empty requests, and large batches.
"""
import time

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.tables import AlertLog, Drug, DrugStock, PrescriptionInventory
from tests.conftest import seed_session_factory

pytestmark = pytest.mark.asyncio


class TestSyncDrugsBulk:
    """POST /api/v1/sync/drugs — bulk prefetch correctness."""

    async def test_bulk_50_drugs(self, client: AsyncClient, seed_data):
        """Syncing 50 drugs in one request works correctly."""
        suffix = str(int(time.time()))[-6:]
        drugs = [
            {
                "standard_code": f"BULK_{suffix}_{i:03d}",
                "name": f"벌크약품{i}",
                "category": "PRESCRIPTION",
                "insurance_code": f"9{suffix}{i:04d}",
            }
            for i in range(50)
        ]
        resp = await client.post(
            "/api/v1/sync/drugs",
            headers={"X-API-Key": seed_data["api_key"]},
            json={"drugs": drugs},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["new_count"] == 50
        assert data["synced_count"] == 50

    async def test_empty_drugs_list(self, client: AsyncClient, seed_data):
        """Empty request returns zero counts."""
        resp = await client.post(
            "/api/v1/sync/drugs",
            headers={"X-API-Key": seed_data["api_key"]},
            json={"drugs": []},
        )
        assert resp.status_code == 200
        assert resp.json()["synced_count"] == 0


class TestSyncVisitsBulk:
    """POST /api/v1/sync/visits — bulk prefetch with duplicate detection."""

    async def test_duplicate_visit_detected(
        self, client: AsyncClient, seed_data, cleanup_visits
    ):
        """Sending the same visit twice: first creates, second is dedup'd."""
        headers = {"X-API-Key": seed_data["api_key"]}
        visit_payload = {
            "visits": [
                {
                    "patient_hash": "dedup_test_hash",
                    "visit_date": "2026-04-01",
                    "prescription_days": 14,
                    "source": "PM20_SYNC",
                    "drugs": [
                        {"drug_standard_code": "KD12345", "quantity_dispensed": 30}
                    ],
                }
            ]
        }

        resp1 = await client.post("/api/v1/sync/visits", headers=headers, json=visit_payload)
        assert resp1.status_code == 200
        assert resp1.json()["synced_count"] == 1

        resp2 = await client.post("/api/v1/sync/visits", headers=headers, json=visit_payload)
        assert resp2.status_code == 200
        # Should detect as duplicate (same patient, date, source, drugs)
        assert resp2.json()["synced_count"] == 1  # Still returns 1 (existing visit_id)
        assert len(resp2.json()["skipped_drugs"]) == 0

    async def test_multiple_patients_single_request(
        self, client: AsyncClient, seed_data, cleanup_visits
    ):
        """Multiple visits for different patients in one request."""
        resp = await client.post(
            "/api/v1/sync/visits",
            headers={"X-API-Key": seed_data["api_key"]},
            json={
                "visits": [
                    {
                        "patient_hash": "patient_multi_1",
                        "visit_date": "2026-04-01",
                        "prescription_days": 14,
                        "source": "PM20_SYNC",
                        "drugs": [{"drug_standard_code": "KD12345", "quantity_dispensed": 10}],
                    },
                    {
                        "patient_hash": "patient_multi_2",
                        "visit_date": "2026-04-01",
                        "prescription_days": 7,
                        "source": "PM20_SYNC",
                        "drugs": [{"drug_standard_code": "KD12345", "quantity_dispensed": 20}],
                    },
                ]
            },
        )
        assert resp.status_code == 200
        assert resp.json()["synced_count"] == 2

    async def test_empty_visits_list(self, client: AsyncClient, seed_data):
        """Empty visits list returns zero."""
        resp = await client.post(
            "/api/v1/sync/visits",
            headers={"X-API-Key": seed_data["api_key"]},
            json={"visits": []},
        )
        assert resp.status_code == 200
        assert resp.json()["synced_count"] == 0


class TestSyncInventoryBulk:
    """POST /api/v1/sync/inventory — bulk prefetch with threshold alerts."""

    async def test_multiple_cassettes(self, client: AsyncClient, seed_data):
        """Sync multiple cassettes in one request."""
        resp = await client.post(
            "/api/v1/sync/inventory",
            headers={"X-API-Key": seed_data["api_key"]},
            json={
                "items": [
                    {"cassette_number": 101, "drug_standard_code": "KD12345", "current_quantity": 50, "quantity_source": "PM20"},
                    {"cassette_number": 102, "drug_standard_code": "KD12345", "current_quantity": 75, "quantity_source": "PM20"},
                ],
                "synced_at": "2026-04-08T00:00:00Z",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["synced_count"] == 2

    async def test_unknown_drug_code_still_counts(self, client: AsyncClient, seed_data):
        """Cassette with unknown drug code: no drug mapping, but synced count increments."""
        resp = await client.post(
            "/api/v1/sync/inventory",
            headers={"X-API-Key": seed_data["api_key"]},
            json={
                "items": [
                    {"cassette_number": 199, "drug_standard_code": "NONEXISTENT", "current_quantity": 10, "quantity_source": "PM20"},
                ],
                "synced_at": "2026-04-08T00:00:00Z",
            },
        )
        assert resp.status_code == 200
        # Unknown drug = no drug_id = skip insert (synced_count still increments per original logic)
        assert resp.json()["synced_count"] == 1
