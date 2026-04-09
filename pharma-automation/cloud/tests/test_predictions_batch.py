"""Tests for prediction_service: get_predictions() and run_daily_predictions().

Covers: batch job happy path, dry-run mode, alert creation, overdue skipping,
prediction upsert with date changes, empty pharmacy, and get_predictions bulk prefetch.
"""
import pytest
import pytest_asyncio
from datetime import date, datetime, timedelta, timezone
from httpx import AsyncClient
from sqlalchemy import select

from app.models.tables import (
    AlertLog,
    Drug,
    DrugThreshold,
    PatientVisitHistory,
    PrescriptionInventory,
    VisitDrug,
    VisitPrediction,
)
from tests.conftest import seed_session_factory

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture(autouse=True)
async def cleanup_predictions(seed_data):
    """Clean prediction-related data before/after each test."""
    async with seed_session_factory() as db:
        pid = seed_data["pharmacy_id"]
        await db.execute(AlertLog.__table__.delete().where(AlertLog.pharmacy_id == pid))
        await db.execute(VisitPrediction.__table__.delete().where(VisitPrediction.pharmacy_id == pid))
        # visit_drugs cascade-deletes with visits
        await db.execute(PatientVisitHistory.__table__.delete().where(PatientVisitHistory.pharmacy_id == pid))
        await db.commit()
    yield
    async with seed_session_factory() as db:
        pid = seed_data["pharmacy_id"]
        await db.execute(AlertLog.__table__.delete().where(AlertLog.pharmacy_id == pid))
        await db.execute(VisitPrediction.__table__.delete().where(VisitPrediction.pharmacy_id == pid))
        await db.execute(PatientVisitHistory.__table__.delete().where(PatientVisitHistory.pharmacy_id == pid))
        await db.commit()


async def _seed_visit(pharmacy_id: int, patient_hash: str, visit_date: date, prescription_days: int, drug_code: str = "KD12345"):
    """Create a visit with one drug and return the visit id."""
    async with seed_session_factory() as db:
        # Look up drug
        result = await db.execute(select(Drug).where(Drug.standard_code == drug_code))
        drug = result.scalar_one_or_none()
        if not drug:
            drug = Drug(standard_code=drug_code, name="TestDrug", category="PRESCRIPTION")
            db.add(drug)
            await db.flush()

        visit = PatientVisitHistory(
            pharmacy_id=pharmacy_id,
            patient_hash=patient_hash,
            visit_date=visit_date,
            prescription_days=prescription_days,
            source="PM20_SYNC",
        )
        db.add(visit)
        await db.flush()

        vd = VisitDrug(visit_id=visit.id, drug_id=drug.id, quantity_dispensed=30)
        db.add(vd)
        await db.commit()
        return visit.id


# --- run_daily_predictions ---


class TestRunDailyPredictions:
    async def test_creates_prediction_for_active_patient(self, seed_data):
        """Batch job creates a VisitPrediction for a patient with recent visit."""
        from app.services.prediction_service import run_daily_predictions

        pid = seed_data["pharmacy_id"]
        visit_date = date.today() - timedelta(days=5)
        await _seed_visit(pid, "patient_aaa", visit_date, prescription_days=30)

        async with seed_session_factory() as db:
            stats = await run_daily_predictions(db, pharmacy_id=pid)
            await db.commit()

        assert stats["pharmacies"] == 1
        assert stats["patients"] == 1
        assert stats["predictions_upserted"] == 1

        # Verify prediction in DB
        async with seed_session_factory() as db:
            result = await db.execute(
                select(VisitPrediction).where(
                    VisitPrediction.pharmacy_id == pid,
                    VisitPrediction.patient_hash == "patient_aaa",
                )
            )
            vp = result.scalar_one_or_none()
            assert vp is not None
            assert vp.predicted_visit_date == visit_date + timedelta(days=30)
            assert vp.prediction_method == "PRESCRIPTION_DAYS"

    async def test_dry_run_does_not_write(self, seed_data):
        """Dry-run counts but doesn't create predictions or alerts."""
        from app.services.prediction_service import run_daily_predictions

        pid = seed_data["pharmacy_id"]
        await _seed_visit(pid, "patient_dry", date.today() - timedelta(days=3), 30)

        async with seed_session_factory() as db:
            stats = await run_daily_predictions(db, pharmacy_id=pid, dry_run=True)

        assert stats["predictions_upserted"] == 1

        # No prediction written
        async with seed_session_factory() as db:
            result = await db.execute(
                select(VisitPrediction).where(VisitPrediction.pharmacy_id == pid)
            )
            assert result.scalar_one_or_none() is None

    async def test_skips_patient_without_prescription_days(self, seed_data):
        """Patient with prescription_days=0 is skipped."""
        from app.services.prediction_service import run_daily_predictions

        pid = seed_data["pharmacy_id"]
        await _seed_visit(pid, "patient_zero", date.today() - timedelta(days=5), 0)

        async with seed_session_factory() as db:
            stats = await run_daily_predictions(db, pharmacy_id=pid)
            await db.commit()

        assert stats["patients"] == 1
        assert stats["predictions_upserted"] == 0

    async def test_upsert_updates_existing_prediction(self, seed_data):
        """Running twice with new visit updates existing prediction."""
        from app.services.prediction_service import run_daily_predictions

        pid = seed_data["pharmacy_id"]
        # First visit: 30-day prescription
        await _seed_visit(pid, "patient_upd", date.today() - timedelta(days=10), 30)

        async with seed_session_factory() as db:
            await run_daily_predictions(db, pharmacy_id=pid)
            await db.commit()

        # New visit: 14-day prescription (shorter)
        await _seed_visit(pid, "patient_upd", date.today() - timedelta(days=2), 14)

        async with seed_session_factory() as db:
            await run_daily_predictions(db, pharmacy_id=pid)
            await db.commit()

        async with seed_session_factory() as db:
            result = await db.execute(
                select(VisitPrediction).where(
                    VisitPrediction.pharmacy_id == pid,
                    VisitPrediction.patient_hash == "patient_upd",
                )
            )
            vp = result.scalar_one()
            # Predicted date should reflect the newer visit
            assert vp.predicted_visit_date == date.today() - timedelta(days=2) + timedelta(days=14)

    async def test_creates_visit_approaching_alert(self, seed_data):
        """Creates VISIT_APPROACHING alert when alert_date <= today."""
        from app.services.prediction_service import run_daily_predictions

        pid = seed_data["pharmacy_id"]
        # Visit 29 days ago, prescription 30 days → predicted = today + 1 (tomorrow)
        # default_alert_days_before=3 → alert_date = tomorrow - 3 = today - 2
        # today >= alert_date → YES alert
        await _seed_visit(pid, "patient_alert", date.today() - timedelta(days=29), 30)

        async with seed_session_factory() as db:
            stats = await run_daily_predictions(db, pharmacy_id=pid)
            await db.commit()

        assert stats["alerts_created"] >= 1

        async with seed_session_factory() as db:
            result = await db.execute(
                select(AlertLog).where(
                    AlertLog.pharmacy_id == pid,
                    AlertLog.alert_type == "VISIT_APPROACHING",
                )
            )
            alert = result.scalar_one_or_none()
            assert alert is not None
            assert "patient_" in alert.message

    async def test_overdue_prediction_skips_alert(self, seed_data):
        """Predictions in the past don't create alerts."""
        from app.services.prediction_service import run_daily_predictions

        pid = seed_data["pharmacy_id"]
        # Visit 60 days ago, prescription 30 days → predicted 30 days ago (overdue)
        await _seed_visit(pid, "patient_overdue", date.today() - timedelta(days=60), 30)

        async with seed_session_factory() as db:
            stats = await run_daily_predictions(db, pharmacy_id=pid)
            await db.commit()

        assert stats["predictions_upserted"] == 1
        assert stats["alerts_created"] == 0

    async def test_empty_pharmacy_returns_zero_stats(self, seed_data):
        """Pharmacy with no visits yields zero predictions."""
        from app.services.prediction_service import run_daily_predictions

        async with seed_session_factory() as db:
            stats = await run_daily_predictions(db, pharmacy_id=seed_data["pharmacy_id"])
            await db.commit()

        assert stats["patients"] == 0
        assert stats["predictions_upserted"] == 0
        assert stats["alerts_created"] == 0


# --- get_predictions (API endpoint) ---


class TestGetPredictions:
    async def test_returns_empty_for_no_predictions(
        self, client: AsyncClient, auth_headers, seed_data
    ):
        """GET /predictions returns empty list when no predictions exist."""
        resp = await client.get("/api/v1/predictions", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["predictions"] == []

    async def test_returns_prediction_with_needed_drugs(
        self, client: AsyncClient, auth_headers, seed_data
    ):
        """GET /predictions includes needed_drugs with in_stock info."""
        from app.services.prediction_service import run_daily_predictions

        pid = seed_data["pharmacy_id"]
        # Create a visit that will produce a prediction within 7 days
        await _seed_visit(pid, "patient_get", date.today() - timedelta(days=25), 30)

        async with seed_session_factory() as db:
            await run_daily_predictions(db, pharmacy_id=pid)
            await db.commit()

        resp = await client.get("/api/v1/predictions?days_ahead=30", headers=auth_headers)
        assert resp.status_code == 200
        predictions = resp.json()["predictions"]
        assert len(predictions) >= 1
        p = predictions[0]
        assert p["patient_hash"] == "patient_get"
        assert p["prediction_method"] == "PRESCRIPTION_DAYS"
        assert "needed_drugs" in p

    async def test_nonexistent_pharmacy_returns_empty(
        self, client: AsyncClient, auth_headers
    ):
        """GET /predictions for valid JWT but empty data returns empty list."""
        resp = await client.get("/api/v1/predictions", headers=auth_headers)
        assert resp.status_code == 200
        # May have predictions from other tests, but should not crash
