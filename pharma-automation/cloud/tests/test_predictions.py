"""Prediction API tests."""

from datetime import date, timedelta

import pytest

from tests.conftest import seed_session_factory
from app.models.tables import Drug, PatientVisitHistory, VisitDrug, VisitPrediction


@pytest.mark.asyncio
async def test_predictions_empty(client, auth_headers, seed_data, cleanup_predictions):
    resp = await client.get("/api/v1/predictions", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["predictions"] == []


@pytest.mark.asyncio
async def test_predictions_with_data(client, auth_headers, seed_data, cleanup_predictions):
    pharmacy_id = seed_data["pharmacy_id"]
    today = date.today()

    async with seed_session_factory() as db:
        # Create visit
        visit = PatientVisitHistory(
            pharmacy_id=pharmacy_id,
            patient_hash="abc123hash",
            visit_date=today - timedelta(days=5),
            prescription_days=7,
            source="PM20_SYNC",
        )
        db.add(visit)
        await db.flush()

        # Create prediction (2 days from now)
        db.add(VisitPrediction(
            pharmacy_id=pharmacy_id,
            patient_hash="abc123hash",
            prediction_method="PRESCRIPTION_DAYS",
            predicted_visit_date=today + timedelta(days=2),
            last_visit_id=visit.id,
            alert_sent=False,
        ))
        await db.commit()

    resp = await client.get("/api/v1/predictions", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["predictions"]) == 1
    p = data["predictions"][0]
    assert p["patient_hash"] == "abc123hash"
    assert p["prediction_method"] == "PRESCRIPTION_DAYS"
    assert p["is_overdue"] is False


@pytest.mark.asyncio
async def test_predictions_days_ahead_narrow(client, auth_headers, seed_data, cleanup_predictions):
    pharmacy_id = seed_data["pharmacy_id"]
    today = date.today()

    async with seed_session_factory() as db:
        visit = PatientVisitHistory(
            pharmacy_id=pharmacy_id,
            patient_hash="narrow_test",
            visit_date=today - timedelta(days=10),
            prescription_days=14,
            source="PM20_SYNC",
        )
        db.add(visit)
        await db.flush()

        # Predicted 4 days from now
        db.add(VisitPrediction(
            pharmacy_id=pharmacy_id,
            patient_hash="narrow_test",
            prediction_method="PRESCRIPTION_DAYS",
            predicted_visit_date=today + timedelta(days=4),
            last_visit_id=visit.id,
            alert_sent=False,
        ))
        await db.commit()

    # days_ahead=1 should NOT include prediction 4 days away
    resp = await client.get(
        "/api/v1/predictions", params={"days_ahead": 1}, headers=auth_headers
    )
    assert resp.status_code == 200
    assert len(resp.json()["predictions"]) == 0

    # days_ahead=7 should include it
    resp = await client.get(
        "/api/v1/predictions", params={"days_ahead": 7}, headers=auth_headers
    )
    assert len(resp.json()["predictions"]) == 1


@pytest.mark.asyncio
async def test_predictions_needed_drugs(client, auth_headers, seed_data, cleanup_predictions):
    pharmacy_id = seed_data["pharmacy_id"]
    today = date.today()

    async with seed_session_factory() as db:
        # Get drug
        from sqlalchemy import select
        drug_result = await db.execute(select(Drug).where(Drug.standard_code == "KD12345"))
        drug = drug_result.scalar_one()

        visit = PatientVisitHistory(
            pharmacy_id=pharmacy_id,
            patient_hash="drug_test_hash",
            visit_date=today - timedelta(days=3),
            prescription_days=7,
            source="PM20_SYNC",
        )
        db.add(visit)
        await db.flush()

        db.add(VisitDrug(
            visit_id=visit.id,
            drug_id=drug.id,
            quantity_dispensed=10,
        ))

        db.add(VisitPrediction(
            pharmacy_id=pharmacy_id,
            patient_hash="drug_test_hash",
            prediction_method="PRESCRIPTION_DAYS",
            predicted_visit_date=today + timedelta(days=4),
            last_visit_id=visit.id,
            alert_sent=False,
        ))
        await db.commit()

    resp = await client.get("/api/v1/predictions", headers=auth_headers)
    assert resp.status_code == 200
    preds = resp.json()["predictions"]
    assert len(preds) == 1
    assert len(preds[0]["needed_drugs"]) == 1
    assert preds[0]["needed_drugs"][0]["drug_name"] == "아모시실린"
    assert preds[0]["needed_drugs"][0]["quantity"] == 10


@pytest.mark.asyncio
async def test_predictions_overdue(client, auth_headers, seed_data, cleanup_predictions):
    pharmacy_id = seed_data["pharmacy_id"]
    today = date.today()

    async with seed_session_factory() as db:
        visit = PatientVisitHistory(
            pharmacy_id=pharmacy_id,
            patient_hash="overdue_hash",
            visit_date=today - timedelta(days=20),
            prescription_days=7,
            source="PM20_SYNC",
        )
        db.add(visit)
        await db.flush()

        # Prediction in the past → overdue
        db.add(VisitPrediction(
            pharmacy_id=pharmacy_id,
            patient_hash="overdue_hash",
            prediction_method="PRESCRIPTION_DAYS",
            predicted_visit_date=today - timedelta(days=3),
            last_visit_id=visit.id,
            alert_sent=False,
        ))
        await db.commit()

    resp = await client.get("/api/v1/predictions", headers=auth_headers)
    preds = resp.json()["predictions"]
    assert len(preds) == 1
    assert preds[0]["is_overdue"] is True


@pytest.mark.asyncio
async def test_predictions_alert_sent_included(client, auth_headers, seed_data, cleanup_predictions):
    pharmacy_id = seed_data["pharmacy_id"]
    today = date.today()

    async with seed_session_factory() as db:
        visit = PatientVisitHistory(
            pharmacy_id=pharmacy_id,
            patient_hash="alerted_hash",
            visit_date=today - timedelta(days=3),
            prescription_days=7,
            source="PM20_SYNC",
        )
        db.add(visit)
        await db.flush()

        db.add(VisitPrediction(
            pharmacy_id=pharmacy_id,
            patient_hash="alerted_hash",
            prediction_method="PRESCRIPTION_DAYS",
            predicted_visit_date=today + timedelta(days=4),
            last_visit_id=visit.id,
            alert_sent=True,
        ))
        await db.commit()

    # include_alerted defaults to True → should show
    resp = await client.get("/api/v1/predictions", headers=auth_headers)
    assert len(resp.json()["predictions"]) == 1
    assert resp.json()["predictions"][0]["alert_sent"] is True
