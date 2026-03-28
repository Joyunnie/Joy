"""Daily predictions batch job tests (service function direct call)."""

from datetime import date, timedelta

import pytest
import pytest_asyncio

from tests.conftest import seed_session_factory
from app.models.tables import AlertLog, Drug, PatientVisitHistory, VisitDrug, VisitPrediction
from app.services.prediction_service import run_daily_predictions


@pytest_asyncio.fixture(autouse=True)
async def _cleanup(seed_data):
    """Clean up predictions/alerts/visits before and after each test."""
    async def _do_cleanup():
        async with seed_session_factory() as db:
            pid = seed_data["pharmacy_id"]
            await db.execute(VisitPrediction.__table__.delete().where(VisitPrediction.pharmacy_id == pid))
            await db.execute(AlertLog.__table__.delete().where(AlertLog.pharmacy_id == pid))
            await db.execute(PatientVisitHistory.__table__.delete().where(PatientVisitHistory.pharmacy_id == pid))
            await db.commit()

    await _do_cleanup()
    yield
    await _do_cleanup()


async def _seed_visit(pharmacy_id: int, patient_hash: str, days_ago: int, rx_days: int, drug_id: int | None = None):
    """Helper: create a visit with optional visit_drug."""
    async with seed_session_factory() as db:
        visit = PatientVisitHistory(
            pharmacy_id=pharmacy_id,
            patient_hash=patient_hash,
            visit_date=date.today() - timedelta(days=days_ago),
            prescription_days=rx_days,
            source="PM20_SYNC",
        )
        db.add(visit)
        await db.flush()
        if drug_id:
            db.add(VisitDrug(visit_id=visit.id, drug_id=drug_id, quantity_dispensed=10))
        await db.commit()
        return visit.id


@pytest.mark.asyncio
async def test_dry_run(seed_data):
    pharmacy_id = seed_data["pharmacy_id"]
    await _seed_visit(pharmacy_id, "dry_run_patient", days_ago=5, rx_days=7)

    async with seed_session_factory() as db:
        stats = await run_daily_predictions(db, pharmacy_id=pharmacy_id, dry_run=True)
        # dry_run: no commit, so no actual DB changes
        assert stats["pharmacies"] == 1
        assert stats["patients"] == 1
        assert stats["predictions_upserted"] == 1

    # Verify no prediction was actually created
    async with seed_session_factory() as db:
        from sqlalchemy import select, func
        count = await db.execute(
            select(func.count(VisitPrediction.id)).where(VisitPrediction.pharmacy_id == pharmacy_id)
        )
        assert count.scalar() == 0


@pytest.mark.asyncio
async def test_normal_execution(seed_data):
    pharmacy_id = seed_data["pharmacy_id"]
    await _seed_visit(pharmacy_id, "normal_patient", days_ago=5, rx_days=7)

    async with seed_session_factory() as db:
        stats = await run_daily_predictions(db, pharmacy_id=pharmacy_id)
        await db.commit()

    assert stats["predictions_upserted"] == 1

    # Verify prediction created
    async with seed_session_factory() as db:
        from sqlalchemy import select
        result = await db.execute(
            select(VisitPrediction).where(
                VisitPrediction.pharmacy_id == pharmacy_id,
                VisitPrediction.patient_hash == "normal_patient",
            )
        )
        vp = result.scalar_one()
        assert vp.prediction_method == "PRESCRIPTION_DAYS"
        expected_date = date.today() - timedelta(days=5) + timedelta(days=7)
        assert vp.predicted_visit_date == expected_date


@pytest.mark.asyncio
async def test_specific_pharmacy(seed_data):
    pharmacy_id = seed_data["pharmacy_id"]
    await _seed_visit(pharmacy_id, "specific_patient", days_ago=3, rx_days=7)

    async with seed_session_factory() as db:
        stats = await run_daily_predictions(db, pharmacy_id=pharmacy_id)
        await db.commit()

    assert stats["pharmacies"] == 1
    assert stats["predictions_upserted"] == 1


@pytest.mark.asyncio
async def test_alert_creation(seed_data):
    pharmacy_id = seed_data["pharmacy_id"]
    # Visit 10 days ago, rx_days=7 → predicted visit 3 days ago → overdue, no alert
    # Visit 3 days ago, rx_days=5 → predicted visit 2 days from now → within alert window
    await _seed_visit(pharmacy_id, "alert_patient", days_ago=3, rx_days=5)

    async with seed_session_factory() as db:
        stats = await run_daily_predictions(db, pharmacy_id=pharmacy_id)
        await db.commit()

    # Prediction 2 days from now; default_alert_days_before=3 → alert_date = predicted - 3 = today - 1 → should trigger
    assert stats["predictions_upserted"] == 1
    assert stats["alerts_created"] >= 1

    # Verify alert in DB
    async with seed_session_factory() as db:
        from sqlalchemy import select
        result = await db.execute(
            select(AlertLog).where(
                AlertLog.pharmacy_id == pharmacy_id,
                AlertLog.alert_type == "VISIT_APPROACHING",
            )
        )
        alerts = result.scalars().all()
        assert len(alerts) >= 1


@pytest.mark.asyncio
async def test_idempotent_rerun(seed_data):
    pharmacy_id = seed_data["pharmacy_id"]
    await _seed_visit(pharmacy_id, "idem_patient", days_ago=5, rx_days=7)

    # First run
    async with seed_session_factory() as db:
        stats1 = await run_daily_predictions(db, pharmacy_id=pharmacy_id)
        await db.commit()

    # Second run — should upsert but not duplicate
    async with seed_session_factory() as db:
        stats2 = await run_daily_predictions(db, pharmacy_id=pharmacy_id)
        await db.commit()

    assert stats1["predictions_upserted"] == 1
    assert stats2["predictions_upserted"] == 1

    # Still only 1 prediction in DB
    async with seed_session_factory() as db:
        from sqlalchemy import select, func
        count = await db.execute(
            select(func.count(VisitPrediction.id)).where(
                VisitPrediction.pharmacy_id == pharmacy_id,
                VisitPrediction.patient_hash == "idem_patient",
            )
        )
        assert count.scalar() == 1
