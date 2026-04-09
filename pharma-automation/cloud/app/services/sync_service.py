from datetime import datetime, timedelta, timezone

from app.exceptions import ServiceError
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import (
    AlertLog,
    Drug,
    DrugStock,
    DrugThreshold,
    PatientVisitHistory,
    PrescriptionInventory,
    VisitDrug,
)
from app.schemas.api import (
    LowStockAlertOut,
    SkippedDrugOut,
    SyncCassetteMappingRequest,
    SyncCassetteMappingResponse,
    SyncInventoryRequest,
    SyncInventoryResponse,
    SyncVisitsRequest,
    SyncVisitsResponse,
    VisitDrugIn,
)
from app.schemas.drug_stock import SyncDrugStockRequest, SyncDrugStockResponse
from app.schemas.drug_sync import SyncDrugsRequest, SyncDrugsResponse


# ---------------------------------------------------------------------------
# Helpers: bulk prefetch
# ---------------------------------------------------------------------------


async def _prefetch_drugs_by_code(
    db: AsyncSession, codes: set[str],
) -> dict[str, Drug]:
    """Fetch Drug rows by standard_code in one query. Returns {code: Drug}."""
    if not codes:
        return {}
    result = await db.execute(
        select(Drug).where(Drug.standard_code.in_(codes))
    )
    return {d.standard_code: d for d in result.scalars().all()}


async def _prefetch_drugs_by_insurance_code(
    db: AsyncSession, codes: set[str],
) -> dict[str, Drug]:
    """Fetch Drug rows by insurance_code in one query. Returns {insurance_code: Drug}."""
    if not codes:
        return {}
    result = await db.execute(
        select(Drug).where(Drug.insurance_code.in_(codes))
    )
    return {d.insurance_code: d for d in result.scalars().all() if d.insurance_code}


async def _prefetch_thresholds(
    db: AsyncSession, pharmacy_id: int, drug_ids: set[int],
) -> dict[int, DrugThreshold]:
    """Fetch active thresholds for a set of drug_ids. Returns {drug_id: DrugThreshold}."""
    if not drug_ids:
        return {}
    result = await db.execute(
        select(DrugThreshold).where(
            and_(
                DrugThreshold.pharmacy_id == pharmacy_id,
                DrugThreshold.drug_id.in_(drug_ids),
                DrugThreshold.is_active == True,  # noqa: E712
            )
        )
    )
    return {t.drug_id: t for t in result.scalars().all()}


async def _prefetch_recent_alerts(
    db: AsyncSession, pharmacy_id: int, alert_type: str,
    ref_table: str, drug_ids: set[int],
) -> set[int]:
    """Return set of drug_ids that already have an unread alert in the last 24h."""
    if not drug_ids:
        return set()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    result = await db.execute(
        select(AlertLog.ref_id).where(
            and_(
                AlertLog.pharmacy_id == pharmacy_id,
                AlertLog.alert_type == alert_type,
                AlertLog.ref_table == ref_table,
                AlertLog.ref_id.in_(drug_ids),
                AlertLog.sent_at >= cutoff,
                AlertLog.read_at.is_(None),
            )
        )
    )
    return {row[0] for row in result.all()}


def _maybe_create_low_stock_alert(
    pharmacy_id: int,
    drug_id: int,
    drug_name: str | None,
    current_quantity: float | int,
    threshold_map: dict[int, DrugThreshold],
    alerted_ids: set[int],
    db: AsyncSession,
    low_stock_alerts: list[LowStockAlertOut],
    ref_table: str,
) -> None:
    """Check threshold and create alert if needed (in-memory maps, no DB query)."""
    threshold = threshold_map.get(drug_id)
    if not threshold or current_quantity >= threshold.min_quantity:
        return
    if drug_id in alerted_ids:
        return
    alert = AlertLog(
        pharmacy_id=pharmacy_id,
        alert_type="LOW_STOCK" if ref_table != "narcotics_inventory" else "NARCOTICS_LOW",
        ref_table=ref_table,
        ref_id=drug_id,
        message=f"{drug_name} 재고 부족 (현재: {current_quantity}, 최소: {threshold.min_quantity})",
        sent_via="IN_APP",
    )
    db.add(alert)
    alerted_ids.add(drug_id)
    low_stock_alerts.append(
        LowStockAlertOut(
            drug_name=drug_name or "",
            current_quantity=round(current_quantity) if isinstance(current_quantity, float) else current_quantity,
            min_quantity=threshold.min_quantity,
        )
    )


# ---------------------------------------------------------------------------
# sync_inventory: ~4 queries (was 4N)
# ---------------------------------------------------------------------------


async def sync_inventory(
    db: AsyncSession, pharmacy_id: int, req: SyncInventoryRequest
) -> SyncInventoryResponse:
    low_stock_alerts: list[LowStockAlertOut] = []
    synced = 0

    # 1. Prefetch drugs
    codes = {item.drug_standard_code for item in req.items if item.drug_standard_code}
    drug_map = await _prefetch_drugs_by_code(db, codes)

    # 2. Prefetch existing prescription_inventory for this pharmacy
    cassette_numbers = [item.cassette_number for item in req.items]
    if cassette_numbers:
        inv_result = await db.execute(
            select(PrescriptionInventory).where(
                and_(
                    PrescriptionInventory.pharmacy_id == pharmacy_id,
                    PrescriptionInventory.cassette_number.in_(cassette_numbers),
                )
            )
        )
        inv_map: dict[int, PrescriptionInventory] = {
            inv.cassette_number: inv for inv in inv_result.scalars().all()
        }
    else:
        inv_map = {}

    # 3. Prefetch thresholds + recent alerts for resolved drug_ids
    resolved_drug_ids = {d.id for d in drug_map.values()}
    threshold_map = await _prefetch_thresholds(db, pharmacy_id, resolved_drug_ids)
    alerted_ids = await _prefetch_recent_alerts(
        db, pharmacy_id, "LOW_STOCK", "prescription_inventory", resolved_drug_ids,
    )

    # 4. Loop in memory
    for item in req.items:
        drug = drug_map.get(item.drug_standard_code) if item.drug_standard_code else None
        drug_id = drug.id if drug else None
        drug_name = drug.name if drug else None

        inv = inv_map.get(item.cassette_number)

        if inv:
            inv.current_quantity = item.current_quantity
            inv.quantity_source = item.quantity_source
            inv.quantity_synced_at = req.synced_at
            inv.version += 1
            inv.updated_at = datetime.now(timezone.utc)
            if drug_id:
                inv.drug_id = drug_id
        else:
            if not drug_id:
                synced += 1
                continue
            new_inv = PrescriptionInventory(
                pharmacy_id=pharmacy_id,
                drug_id=drug_id,
                cassette_number=item.cassette_number,
                current_quantity=item.current_quantity,
                quantity_source=item.quantity_source,
                quantity_synced_at=req.synced_at,
            )
            db.add(new_inv)

        synced += 1

        if drug_id:
            _maybe_create_low_stock_alert(
                pharmacy_id, drug_id, drug_name, item.current_quantity,
                threshold_map, alerted_ids, db, low_stock_alerts,
                "prescription_inventory",
            )

    return SyncInventoryResponse(synced_count=synced, low_stock_alerts=low_stock_alerts)


# ---------------------------------------------------------------------------
# sync_cassette_mapping: 2 queries (was 2N)
# ---------------------------------------------------------------------------


async def sync_cassette_mapping(
    db: AsyncSession, pharmacy_id: int, req: SyncCassetteMappingRequest
) -> SyncCassetteMappingResponse:
    new_count = 0
    updated_count = 0

    # 1. Prefetch drugs
    codes = {m.drug_standard_code for m in req.mappings}
    drug_map = await _prefetch_drugs_by_code(db, codes)

    # Validate all drugs exist upfront
    for mapping in req.mappings:
        if mapping.drug_standard_code not in drug_map:
            raise ServiceError(f"Drug not found: {mapping.drug_standard_code}", 422)

    # 2. Prefetch existing inventories
    cassette_numbers = [m.cassette_number for m in req.mappings]
    if cassette_numbers:
        inv_result = await db.execute(
            select(PrescriptionInventory).where(
                and_(
                    PrescriptionInventory.pharmacy_id == pharmacy_id,
                    PrescriptionInventory.cassette_number.in_(cassette_numbers),
                )
            )
        )
        inv_map = {inv.cassette_number: inv for inv in inv_result.scalars().all()}
    else:
        inv_map = {}

    # 3. Loop in memory
    for mapping in req.mappings:
        drug = drug_map[mapping.drug_standard_code]
        inv = inv_map.get(mapping.cassette_number)

        if inv:
            inv.drug_id = drug.id
            inv.mapping_source = mapping.mapping_source
            inv.mapping_synced_at = req.synced_at
            inv.updated_at = datetime.now(timezone.utc)
            updated_count += 1
        else:
            new_inv = PrescriptionInventory(
                pharmacy_id=pharmacy_id,
                drug_id=drug.id,
                cassette_number=mapping.cassette_number,
                current_quantity=0,
                mapping_source=mapping.mapping_source,
                mapping_synced_at=req.synced_at,
            )
            db.add(new_inv)
            new_count += 1

    return SyncCassetteMappingResponse(
        synced_count=new_count + updated_count,
        new_mappings=new_count,
        updated_mappings=updated_count,
    )


# ---------------------------------------------------------------------------
# sync_visits: ~3 queries (was M+E+D)
# ---------------------------------------------------------------------------


async def sync_visits(
    db: AsyncSession, pharmacy_id: int, req: SyncVisitsRequest
) -> SyncVisitsResponse:
    visit_ids: list[int] = []
    skipped_drugs: list[SkippedDrugOut] = []

    # 1. Prefetch all drugs referenced across all visits (by insurance_code and standard_code)
    all_insurance_codes: set[str] = set()
    all_standard_codes: set[str] = set()
    for visit_in in req.visits:
        for d in visit_in.drugs:
            if d.drug_insurance_code:
                all_insurance_codes.add(d.drug_insurance_code)
            if d.drug_standard_code:
                all_standard_codes.add(d.drug_standard_code)
    insurance_drug_map = await _prefetch_drugs_by_insurance_code(db, all_insurance_codes)
    standard_drug_map = await _prefetch_drugs_by_code(db, all_standard_codes)

    # 2. Prefetch existing visits for duplicate detection (bulk by pharmacy)
    #    We need visits matching any (patient_hash, visit_date, source) combo
    patient_hashes = {v.patient_hash for v in req.visits}
    if patient_hashes:
        existing_visits_result = await db.execute(
            select(PatientVisitHistory).where(
                and_(
                    PatientVisitHistory.pharmacy_id == pharmacy_id,
                    PatientVisitHistory.patient_hash.in_(patient_hashes),
                )
            )
        )
        all_existing_visits = existing_visits_result.scalars().all()
    else:
        all_existing_visits = []

    # 3. Prefetch VisitDrug+Drug for all existing visit IDs (for drug-combo dedup)
    #    Use insurance_code for comparison (primary), fallback to standard_code
    existing_visit_ids = [v.id for v in all_existing_visits]
    if existing_visit_ids:
        vd_result = await db.execute(
            select(VisitDrug, Drug)
            .join(Drug, VisitDrug.drug_id == Drug.id)
            .where(VisitDrug.visit_id.in_(existing_visit_ids))
        )
        visit_drug_map: dict[int, list[str]] = {}
        for vd, drug in vd_result.all():
            code = drug.insurance_code or drug.standard_code or ""
            visit_drug_map.setdefault(vd.visit_id, []).append(code)
        for codes_list in visit_drug_map.values():
            codes_list.sort()
    else:
        visit_drug_map = {}

    # Helper: resolve a VisitDrugIn to a Drug object
    def _resolve_drug(d: VisitDrugIn) -> Drug | None:
        if d.drug_insurance_code:
            found = insurance_drug_map.get(d.drug_insurance_code)
            if found:
                return found
        if d.drug_standard_code:
            found = standard_drug_map.get(d.drug_standard_code)
            if found:
                return found
        return None

    def _drug_dedup_code(d: VisitDrugIn) -> str:
        return d.drug_insurance_code or d.drug_standard_code or ""

    # 4. Loop in memory
    for visit_in in req.visits:
        incoming_codes = sorted([_drug_dedup_code(d) for d in visit_in.drugs])

        # Check for duplicate among existing visits
        is_duplicate = False
        for ex_visit in all_existing_visits:
            if (
                ex_visit.patient_hash == visit_in.patient_hash
                and ex_visit.visit_date == visit_in.visit_date
                and ex_visit.source == visit_in.source
            ):
                existing_codes = visit_drug_map.get(ex_visit.id, [])
                if existing_codes == incoming_codes:
                    is_duplicate = True
                    visit_ids.append(ex_visit.id)
                    break

        if is_duplicate:
            continue

        # INSERT visit
        visit = PatientVisitHistory(
            pharmacy_id=pharmacy_id,
            patient_hash=visit_in.patient_hash,
            visit_date=visit_in.visit_date,
            prescription_days=visit_in.prescription_days,
            source=visit_in.source,
        )
        db.add(visit)
        await db.flush()
        visit_ids.append(visit.id)

        # INSERT visit_drugs
        for drug_in in visit_in.drugs:
            drug = _resolve_drug(drug_in)
            if not drug:
                skipped_drugs.append(
                    SkippedDrugOut(
                        drug_standard_code=drug_in.drug_insurance_code or drug_in.drug_standard_code or "unknown",
                        reason="not_found_in_drugs_master",
                    )
                )
                continue
            db.add(VisitDrug(
                visit_id=visit.id,
                drug_id=drug.id,
                quantity_dispensed=drug_in.quantity_dispensed,
            ))

    return SyncVisitsResponse(
        synced_count=len(visit_ids),
        visit_ids=visit_ids,
        skipped_drugs=skipped_drugs,
    )


# ---------------------------------------------------------------------------
# sync_drugs: 1 query (was N)
# ---------------------------------------------------------------------------


async def sync_drugs(
    db: AsyncSession, req: SyncDrugsRequest
) -> SyncDrugsResponse:
    """DA_Goods → drugs 테이블 UPSERT. standard_code 기준."""
    new_count = 0
    updated_count = 0

    # 1. Prefetch all existing drugs by standard_code
    codes = {d.standard_code for d in req.drugs}
    existing_map = await _prefetch_drugs_by_code(db, codes)

    # 2. Loop in memory
    for drug_in in req.drugs:
        existing = existing_map.get(drug_in.standard_code)

        if existing:
            changed = False
            if existing.name != drug_in.name:
                existing.name = drug_in.name
                changed = True
            if drug_in.manufacturer and existing.manufacturer != drug_in.manufacturer:
                existing.manufacturer = drug_in.manufacturer
                changed = True
            if existing.category != drug_in.category:
                existing.category = drug_in.category
                changed = True
            if drug_in.insurance_code and existing.insurance_code != drug_in.insurance_code:
                existing.insurance_code = drug_in.insurance_code
                changed = True
            if changed:
                existing.updated_at = datetime.now(timezone.utc)
                updated_count += 1
        else:
            drug = Drug(
                standard_code=drug_in.standard_code,
                name=drug_in.name,
                manufacturer=drug_in.manufacturer,
                category=drug_in.category,
                insurance_code=drug_in.insurance_code,
            )
            db.add(drug)
            new_count += 1

    return SyncDrugsResponse(
        synced_count=new_count + updated_count,
        new_count=new_count,
        updated_count=updated_count,
    )


# ---------------------------------------------------------------------------
# sync_drug_stock: ~4 queries (was 4N)
# ---------------------------------------------------------------------------


async def sync_drug_stock(
    db: AsyncSession, pharmacy_id: int, req: SyncDrugStockRequest
) -> SyncDrugStockResponse:
    """PM+20 TEMP_STOCK → drug_stock 테이블 UPSERT. (pharmacy_id, drug_id) 기준."""
    low_stock_alerts: list[LowStockAlertOut] = []
    synced = 0
    skipped = 0

    # 1. Prefetch drugs
    codes = {item.drug_standard_code for item in req.items}
    drug_map = await _prefetch_drugs_by_code(db, codes)

    # 2. Prefetch existing drug_stock for this pharmacy
    resolved_drug_ids = {d.id for d in drug_map.values()}
    if resolved_drug_ids:
        stock_result = await db.execute(
            select(DrugStock).where(
                and_(
                    DrugStock.pharmacy_id == pharmacy_id,
                    DrugStock.drug_id.in_(resolved_drug_ids),
                )
            )
        )
        stock_map: dict[int, DrugStock] = {
            s.drug_id: s for s in stock_result.scalars().all()
        }
    else:
        stock_map = {}

    # 3. Prefetch thresholds + recent alerts
    threshold_map = await _prefetch_thresholds(db, pharmacy_id, resolved_drug_ids)
    alerted_ids = await _prefetch_recent_alerts(
        db, pharmacy_id, "LOW_STOCK", "drug_stock", resolved_drug_ids,
    )

    # 4. Loop in memory
    for item in req.items:
        drug = drug_map.get(item.drug_standard_code)
        if not drug:
            skipped += 1
            continue

        stock = stock_map.get(drug.id)

        if stock:
            stock.current_quantity = item.current_quantity
            stock.is_narcotic = item.is_narcotic
            stock.synced_at = req.synced_at
            stock.updated_at = datetime.now(timezone.utc)
        else:
            stock = DrugStock(
                pharmacy_id=pharmacy_id,
                drug_id=drug.id,
                current_quantity=item.current_quantity,
                is_narcotic=item.is_narcotic,
                quantity_source="PM20",
                synced_at=req.synced_at,
            )
            db.add(stock)

        synced += 1

        _maybe_create_low_stock_alert(
            pharmacy_id, drug.id, drug.name, item.current_quantity,
            threshold_map, alerted_ids, db, low_stock_alerts,
            "drug_stock",
        )

    return SyncDrugStockResponse(
        synced_count=synced,
        skipped_count=skipped,
        low_stock_alerts=low_stock_alerts,
    )
