from datetime import date, datetime, timedelta, timezone
import logging

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import (
    AlertLog,
    AtdpsCanister,
    Drug,
    PatientVisitHistory,
    Pharmacy,
    VisitDrug,
    VisitPrediction,
)
from app.schemas.api import (
    NeededDrugOut,
    PredictionListResponse,
    PredictionOut,
)

logger = logging.getLogger(__name__)


async def get_predictions(
    db: AsyncSession,
    pharmacy_id: int,
    days_ahead: int = 7,
    include_alerted: bool = True,
    limit: int = 200,
    offset: int = 0,
) -> PredictionListResponse:
    today = date.today()
    cutoff = today + timedelta(days=days_ahead)

    # Get pharmacy for default_alert_days_before
    pharm_result = await db.execute(
        select(Pharmacy).where(Pharmacy.id == pharmacy_id)
    )
    pharmacy = pharm_result.scalar_one_or_none()
    if not pharmacy:
        return PredictionListResponse(predictions=[], total=0)

    conditions = [
        VisitPrediction.pharmacy_id == pharmacy_id,
        VisitPrediction.predicted_visit_date <= cutoff,
    ]
    if not include_alerted:
        conditions.append(VisitPrediction.alert_sent == False)  # noqa: E712

    total_result = await db.execute(
        select(func.count(VisitPrediction.id)).where(and_(*conditions))
    )
    total = total_result.scalar() or 0

    result = await db.execute(
        select(VisitPrediction)
        .where(and_(*conditions))
        .order_by(VisitPrediction.predicted_visit_date)
        .limit(limit)
        .offset(offset)
    )
    predictions = result.scalars().all()

    # Bulk prefetch visits, drugs, and inventory (~3 queries instead of 2+N per prediction)
    visit_ids = [vp.last_visit_id for vp in predictions if vp.last_visit_id]

    # Prefetch last visits
    if visit_ids:
        visit_result = await db.execute(
            select(PatientVisitHistory).where(PatientVisitHistory.id.in_(visit_ids))
        )
        visit_map = {v.id: v for v in visit_result.scalars().all()}
    else:
        visit_map = {}

    # Prefetch visit_drugs + drug info for all visit_ids at once
    visit_drug_map: dict[int, list[tuple]] = {}  # {visit_id: [(vd, drug), ...]}
    if visit_ids:
        vd_result = await db.execute(
            select(VisitDrug, Drug)
            .join(Drug, VisitDrug.drug_id == Drug.id)
            .where(VisitDrug.visit_id.in_(visit_ids))
        )
        for vd, drug in vd_result.all():
            visit_drug_map.setdefault(vd.visit_id, []).append((vd, drug))

    # Build response in memory
    out: list[PredictionOut] = []
    for vp in predictions:
        alert_days = vp.alert_days_before or pharmacy.default_alert_days_before
        alert_date = vp.predicted_visit_date - timedelta(days=alert_days)
        is_overdue = vp.predicted_visit_date < today

        based_on_visit_date = None
        needed_drugs: list[NeededDrugOut] = []
        if vp.last_visit_id:
            last_visit = visit_map.get(vp.last_visit_id)
            if last_visit:
                based_on_visit_date = last_visit.visit_date

            for vd, drug in visit_drug_map.get(vp.last_visit_id, []):
                needed_drugs.append(
                    NeededDrugOut(
                        drug_name=drug.name,
                        quantity=vd.quantity_dispensed,
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

    return PredictionListResponse(predictions=out, total=total)


async def run_daily_predictions(
    db: AsyncSession,
    pharmacy_id: int | None = None,
    lookback_days: int = 180,
    dry_run: bool = False,
) -> dict:
    """Run daily prediction batch job. Returns stats.

    Bulk-prefetch pattern: ~5 queries per pharmacy instead of ~500.
    """
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

        # 1. Bulk: get last visit per patient using window function
        #    ROW_NUMBER() OVER (PARTITION BY patient_hash ORDER BY visit_date DESC)
        subq = (
            select(
                PatientVisitHistory,
                func.row_number()
                .over(
                    partition_by=PatientVisitHistory.patient_hash,
                    order_by=PatientVisitHistory.visit_date.desc(),
                )
                .label("rn"),
            )
            .where(
                and_(
                    PatientVisitHistory.pharmacy_id == pharmacy.id,
                    PatientVisitHistory.visit_date >= lookback_date,
                )
            )
            .subquery()
        )
        last_visits_result = await db.execute(
            select(PatientVisitHistory)
            .join(subq, PatientVisitHistory.id == subq.c.id)
            .where(subq.c.rn == 1)
        )
        last_visits = list(last_visits_result.scalars().all())
        stats["patients"] += len(last_visits)

        # Filter to patients with prescription_days > 0
        valid_visits = [v for v in last_visits if v.prescription_days]
        if not valid_visits:
            continue

        if dry_run:
            stats["predictions_upserted"] += len(valid_visits)
            continue

        # 2. Bulk: prefetch existing predictions for this pharmacy
        patient_hashes = [v.patient_hash for v in valid_visits]
        vp_result = await db.execute(
            select(VisitPrediction).where(
                and_(
                    VisitPrediction.pharmacy_id == pharmacy.id,
                    VisitPrediction.patient_hash.in_(patient_hashes),
                )
            )
        )
        vp_map: dict[str, VisitPrediction] = {
            vp.patient_hash: vp for vp in vp_result.scalars().all()
        }

        # 3. Collect alert candidates
        visit_ids_for_alerts: list[int] = []

        # Process predictions in memory
        now = datetime.now(timezone.utc)
        alert_candidates: list[tuple] = []  # (patient_hash, predicted_date, visit, vp)

        for visit in valid_visits:
            predicted_date = visit.visit_date + timedelta(days=visit.prescription_days)

            vp = vp_map.get(visit.patient_hash)
            if vp:
                if vp.predicted_visit_date != predicted_date:
                    vp.alert_sent = False
                vp.predicted_visit_date = predicted_date
                vp.prediction_method = "PRESCRIPTION_DAYS"
                vp.last_visit_id = visit.id
                vp.updated_at = now
            else:
                vp = VisitPrediction(
                    pharmacy_id=pharmacy.id,
                    patient_hash=visit.patient_hash,
                    prediction_method="PRESCRIPTION_DAYS",
                    predicted_visit_date=predicted_date,
                    last_visit_id=visit.id,
                    alert_sent=False,
                )
                db.add(vp)

            stats["predictions_upserted"] += 1

            # Collect alert candidates (not overdue, not already alerted)
            if predicted_date >= today:
                alert_days = vp.alert_days_before or pharmacy.default_alert_days_before
                alert_date = predicted_date - timedelta(days=alert_days)
                if today >= alert_date and not vp.alert_sent:
                    alert_candidates.append((visit.patient_hash, predicted_date, visit, vp))
                    visit_ids_for_alerts.append(visit.id)

        # 4. Bulk: fetch drugs for alert candidates + canister drug codes
        if visit_ids_for_alerts:
            canister_result = await db.execute(
                select(AtdpsCanister.drug_code, AtdpsCanister.drug_name)
                .where(AtdpsCanister.pharmacy_id == pharmacy.id)
            )
            canister_name_by_code: dict[str, str] = {
                row.drug_code: row.drug_name for row in canister_result.all()
            }

            vd_result = await db.execute(
                select(VisitDrug, Drug)
                .join(Drug, VisitDrug.drug_id == Drug.id)
                .where(VisitDrug.visit_id.in_(visit_ids_for_alerts))
            )
            visit_drugs_map: dict[int, list[tuple]] = {}
            for vd, drug in vd_result.all():
                visit_drugs_map.setdefault(vd.visit_id, []).append((vd, drug))
        else:
            canister_name_by_code = {}
            visit_drugs_map = {}

        # 5. Create alerts — only for patients with at least one canister drug
        for patient_hash, predicted_date, visit, vp in alert_candidates:
            canister_drugs = sorted({
                canister_name_by_code[drug.insurance_code]
                for vd, drug in visit_drugs_map.get(visit.id, [])
                if drug.insurance_code and drug.insurance_code in canister_name_by_code
            })
            if not canister_drugs:
                continue  # Don't mark alert_sent — re-evaluate if canisters change

            alert = AlertLog(
                pharmacy_id=pharmacy.id,
                alert_type="VISIT_APPROACHING",
                ref_table="visit_predictions",
                ref_id=vp.id,
                message=f"환자 {patient_hash[:8]}... 예상 내원일: {predicted_date} — 캐니스터 약품: {', '.join(canister_drugs)}",
                sent_via="IN_APP",
            )
            db.add(alert)
            vp.alert_sent = True
            stats["alerts_created"] += 1

    return stats
