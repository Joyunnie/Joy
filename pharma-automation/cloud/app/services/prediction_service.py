from datetime import date, datetime, timedelta, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import (
    AlertLog,
    Drug,
    DrugThreshold,
    PatientVisitHistory,
    Pharmacy,
    PrescriptionInventory,
    VisitDrug,
    VisitPrediction,
)
from app.schemas.api import (
    NeededDrugOut,
    PredictionListResponse,
    PredictionOut,
)


async def get_predictions(
    db: AsyncSession,
    pharmacy_id: int,
    days_ahead: int = 7,
    include_alerted: bool = True,
) -> PredictionListResponse:
    today = date.today()
    cutoff = today + timedelta(days=days_ahead)

    # Get pharmacy for default_alert_days_before
    pharm_result = await db.execute(
        select(Pharmacy).where(Pharmacy.id == pharmacy_id)
    )
    pharmacy = pharm_result.scalar_one_or_none()
    if not pharmacy:
        return PredictionListResponse(predictions=[])

    conditions = [
        VisitPrediction.pharmacy_id == pharmacy_id,
        VisitPrediction.predicted_visit_date <= cutoff,
    ]
    if not include_alerted:
        conditions.append(VisitPrediction.alert_sent == False)  # noqa: E712

    result = await db.execute(
        select(VisitPrediction).where(and_(*conditions)).order_by(VisitPrediction.predicted_visit_date)
    )
    predictions = result.scalars().all()

    out: list[PredictionOut] = []
    for vp in predictions:
        alert_days = vp.alert_days_before or pharmacy.default_alert_days_before
        alert_date = vp.predicted_visit_date - timedelta(days=alert_days)
        is_overdue = vp.predicted_visit_date < today

        # Get based_on_visit_date and needed drugs
        based_on_visit_date = None
        needed_drugs: list[NeededDrugOut] = []
        if vp.last_visit_id:
            visit_result = await db.execute(
                select(PatientVisitHistory).where(PatientVisitHistory.id == vp.last_visit_id)
            )
            last_visit = visit_result.scalar_one_or_none()
            if last_visit:
                based_on_visit_date = last_visit.visit_date

            # Get visit_drugs with drug info and inventory
            vd_result = await db.execute(
                select(VisitDrug, Drug)
                .join(Drug, VisitDrug.drug_id == Drug.id)
                .where(VisitDrug.visit_id == vp.last_visit_id)
            )
            for vd, drug in vd_result.all():
                inv_result = await db.execute(
                    select(PrescriptionInventory).where(
                        and_(
                            PrescriptionInventory.pharmacy_id == pharmacy_id,
                            PrescriptionInventory.drug_id == drug.id,
                        )
                    )
                )
                inv = inv_result.scalars().first()
                needed_drugs.append(
                    NeededDrugOut(
                        drug_name=drug.name,
                        quantity=vd.quantity_dispensed,
                        in_stock=inv.current_quantity if inv else None,
                    )
                )

        out.append(
            PredictionOut(
                id=vp.id,
                patient_hash=vp.patient_hash,
                predicted_visit_date=vp.predicted_visit_date,
                alert_date=alert_date,
                alert_sent=vp.alert_sent,
                prediction_method=vp.prediction_method,
                based_on_visit_date=based_on_visit_date,
                is_overdue=is_overdue,
                needed_drugs=needed_drugs,
            )
        )

    return PredictionListResponse(predictions=out)


async def run_daily_predictions(
    db: AsyncSession,
    pharmacy_id: int | None = None,
    lookback_days: int = 180,
    dry_run: bool = False,
) -> dict:
    """Run daily prediction batch job. Returns stats."""
    today = date.today()
    lookback_date = today - timedelta(days=lookback_days)

    # Get pharmacies
    if pharmacy_id:
        pharm_result = await db.execute(
            select(Pharmacy).where(Pharmacy.id == pharmacy_id)
        )
        pharmacies = list(pharm_result.scalars().all())
    else:
        pharm_result = await db.execute(select(Pharmacy))
        pharmacies = list(pharm_result.scalars().all())

    stats = {"pharmacies": 0, "patients": 0, "predictions_upserted": 0, "alerts_created": 0}

    for pharmacy in pharmacies:
        stats["pharmacies"] += 1

        # Active patients (visited within lookback_days)
        patient_result = await db.execute(
            select(func.distinct(PatientVisitHistory.patient_hash)).where(
                and_(
                    PatientVisitHistory.pharmacy_id == pharmacy.id,
                    PatientVisitHistory.visit_date >= lookback_date,
                )
            )
        )
        patient_hashes = [row[0] for row in patient_result.all()]
        stats["patients"] += len(patient_hashes)

        for patient_hash in patient_hashes:
            # Last visit
            visit_result = await db.execute(
                select(PatientVisitHistory)
                .where(
                    and_(
                        PatientVisitHistory.pharmacy_id == pharmacy.id,
                        PatientVisitHistory.patient_hash == patient_hash,
                    )
                )
                .order_by(PatientVisitHistory.visit_date.desc())
                .limit(1)
            )
            last_visit = visit_result.scalar_one_or_none()
            if not last_visit or not last_visit.prescription_days:
                continue

            predicted_date = last_visit.visit_date + timedelta(days=last_visit.prescription_days)

            if dry_run:
                stats["predictions_upserted"] += 1
                continue

            # UPSERT visit_predictions
            vp_result = await db.execute(
                select(VisitPrediction).where(
                    and_(
                        VisitPrediction.pharmacy_id == pharmacy.id,
                        VisitPrediction.patient_hash == patient_hash,
                    )
                )
            )
            vp = vp_result.scalar_one_or_none()

            date_changed = False
            if vp:
                if vp.predicted_visit_date != predicted_date:
                    date_changed = True
                    vp.alert_sent = False
                vp.predicted_visit_date = predicted_date
                vp.prediction_method = "PRESCRIPTION_DAYS"
                vp.last_visit_id = last_visit.id
                vp.updated_at = datetime.now(timezone.utc)
            else:
                date_changed = True
                vp = VisitPrediction(
                    pharmacy_id=pharmacy.id,
                    patient_hash=patient_hash,
                    prediction_method="PRESCRIPTION_DAYS",
                    predicted_visit_date=predicted_date,
                    last_visit_id=last_visit.id,
                    alert_sent=False,
                )
                db.add(vp)

            stats["predictions_upserted"] += 1

            # Skip alert for overdue predictions
            if predicted_date < today:
                continue

            # Alert check
            alert_days = vp.alert_days_before or pharmacy.default_alert_days_before
            alert_date = predicted_date - timedelta(days=alert_days)

            if today >= alert_date and not vp.alert_sent:
                # Create VISIT_APPROACHING alert
                alert = AlertLog(
                    pharmacy_id=pharmacy.id,
                    alert_type="VISIT_APPROACHING",
                    ref_table="visit_predictions",
                    ref_id=vp.id,
                    message=f"환자 {patient_hash[:8]}... 예상 내원일: {predicted_date}",
                    sent_via="IN_APP",
                )
                db.add(alert)
                vp.alert_sent = True
                stats["alerts_created"] += 1

                # Check needed drugs stock
                vd_result = await db.execute(
                    select(VisitDrug, Drug, PrescriptionInventory)
                    .join(Drug, VisitDrug.drug_id == Drug.id)
                    .outerjoin(
                        PrescriptionInventory,
                        and_(
                            PrescriptionInventory.pharmacy_id == pharmacy.id,
                            PrescriptionInventory.drug_id == Drug.id,
                        ),
                    )
                    .where(VisitDrug.visit_id == last_visit.id)
                )
                for vd, drug, inv in vd_result.all():
                    if not inv:
                        continue
                    threshold_result = await db.execute(
                        select(DrugThreshold).where(
                            and_(
                                DrugThreshold.pharmacy_id == pharmacy.id,
                                DrugThreshold.drug_id == drug.id,
                                DrugThreshold.is_active == True,  # noqa: E712
                            )
                        )
                    )
                    threshold = threshold_result.scalar_one_or_none()
                    if threshold and inv.current_quantity < threshold.min_quantity:
                        low_alert = AlertLog(
                            pharmacy_id=pharmacy.id,
                            alert_type="LOW_STOCK",
                            ref_table="prescription_inventory",
                            ref_id=drug.id,
                            message=f"{drug.name} 재고 부족 (현재: {inv.current_quantity}, 최소: {threshold.min_quantity}) — 환자 {patient_hash[:8]}... 내원 예정",
                            sent_via="IN_APP",
                        )
                        db.add(low_alert)
                        stats["alerts_created"] += 1

    return stats
