import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ServiceError
from app.models.tables import (
    Drug,
    DrugStock,
    PatientVisitHistory,
    PrescriptionInventory,
    VisitDrug,
)
from app.schemas.api import (
    SkippedDrugOut,
    SyncCassetteMappingRequest,
    SyncCassetteMappingResponse,
    SyncInventoryRequest,
    SyncInventoryResponse,
    SyncVisitsRequest,
    SyncVisitsResponse,
)
from app.schemas.drug_sync import SyncDrugsRequest, SyncDrugsResponse
from app.services.alert_utils import check_and_create_low_stock_alert
from app.services.drug_resolver import DrugResolver

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers: bulk prefetch
# ---------------------------------------------------------------------------


async def _prefetch_drugs_by_code(
    db: AsyncSession, codes: set[str],
) -> dict[str, Drug]:
    """Fetch Drug rows by standard_code in one query. Returns {code: Drug}.

    Note: standard_code is no longer unique in DB; callers assume no collisions in practice.
    """
    if not codes:
        return {}
    result = await db.execute(
        select(Drug).where(Drug.standard_code.in_(codes))
    )
    drug_map: dict[str, Drug] = {}
    for d in result.scalars().all():
        if d.standard_code in drug_map:
            logger.warning(
                "standard_code collision: %s maps to drug_id %d and %d — keeping first",
                d.standard_code, drug_map[d.standard_code].id, d.id,
            )
            continue
        drug_map[d.standard_code] = d
    return drug_map


async def _prefetch_drugs_by_insurance_code(
    db: AsyncSession, codes: set[str]
) -> dict[str, Drug]:
    """Fetch Drug rows by insurance_code. Returns {insurance_code: Drug}."""
    if not codes:
        return {}
    result = await db.execute(
        select(Drug).where(Drug.insurance_code.in_(codes))
    )
    return {d.insurance_code: d for d in result.scalars().all() if d.insurance_code}


# ---------------------------------------------------------------------------
# sync_inventory: ~4 queries (was 4N)
# ---------------------------------------------------------------------------


async def sync_inventory(
    db: AsyncSession, pharmacy_id: int, req: SyncInventoryRequest
) -> SyncInventoryResponse:
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

    # 3. Loop in memory
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

    return SyncInventoryResponse(synced_count=synced, low_stock_alerts=[])


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


async def _deduct_dispensed_from_stock(
    db: AsyncSession,
    pharmacy_id: int,
    deductions: dict[int, int],
    resolved_drugs: dict[int, Drug],
) -> None:
    """Deduct dispensed quantities from drug_stock. Clamps to 0 if negative."""
    if not deductions:
        return
    stock_result = await db.execute(
        select(DrugStock).where(
            and_(
                DrugStock.pharmacy_id == pharmacy_id,
                DrugStock.drug_id.in_(deductions.keys()),
            )
        )
    )
    stock_map = {s.drug_id: s for s in stock_result.scalars().all()}

    for drug_id, qty in deductions.items():
        stock = stock_map.get(drug_id)
        if not stock:
            continue  # drug_stock not initialized yet — skip
        new_qty = float(stock.current_quantity) - qty
        if new_qty < 0:
            logger.warning(
                "Stock for drug_id=%d would go negative (%.1f - %d), clamping to 0",
                drug_id, float(stock.current_quantity), qty,
            )
            new_qty = 0
        stock.current_quantity = new_qty
        stock.updated_at = datetime.now(timezone.utc)

        drug = resolved_drugs[drug_id]
        await check_and_create_low_stock_alert(
            db, pharmacy_id, drug_id, new_qty, drug.name,
            "LOW_STOCK", "drug_stock",
        )


# ---------------------------------------------------------------------------
# sync_visits: ~6 queries (resolver 2 + existing visits 1 + visit drugs 1 + drug_stock 1 + alerts)
# ---------------------------------------------------------------------------


async def sync_visits(
    db: AsyncSession, pharmacy_id: int, req: SyncVisitsRequest
) -> SyncVisitsResponse:
    visit_ids: list[int] = []
    skipped_drugs: list[SkippedDrugOut] = []

    # 1. Build drug resolver for all drugs referenced across all visits
    all_insurance_codes: set[str] = set()
    all_standard_codes: set[str] = set()
    for visit_in in req.visits:
        for d in visit_in.drugs:
            if d.drug_insurance_code:
                all_insurance_codes.add(d.drug_insurance_code)
            if d.drug_standard_code:
                all_standard_codes.add(d.drug_standard_code)
    resolver = await DrugResolver.build(db, all_insurance_codes, all_standard_codes)

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

    # 4. Build dedup lookup: (patient_hash, visit_date, source) → list of (visit_id, sorted_codes)
    dedup_lookup: dict[tuple, list[tuple[int, list[str]]]] = {}
    for ex_visit in all_existing_visits:
        key = (ex_visit.patient_hash, ex_visit.visit_date, ex_visit.source)
        codes = visit_drug_map.get(ex_visit.id, [])
        dedup_lookup.setdefault(key, []).append((ex_visit.id, codes))

    # 5. First pass: identify new visits, skip duplicates
    new_visits: list[PatientVisitHistory] = []
    # Parallel list: the original VisitIn for each new visit (to resolve drugs after flush)
    visit_inputs = []

    for visit_in in req.visits:
        incoming_codes = sorted(
            d.drug_insurance_code or d.drug_standard_code or "" for d in visit_in.drugs
        )

        # O(1) lookup for dedup candidates
        key = (visit_in.patient_hash, visit_in.visit_date, visit_in.source)
        candidates = dedup_lookup.get(key, [])
        is_duplicate = False
        for ex_id, ex_codes in candidates:
            if ex_codes == incoming_codes:
                is_duplicate = True
                visit_ids.append(ex_id)
                break

        if is_duplicate:
            continue

        visit = PatientVisitHistory(
            pharmacy_id=pharmacy_id,
            patient_hash=visit_in.patient_hash,
            visit_date=visit_in.visit_date,
            prescription_days=visit_in.prescription_days,
            source=visit_in.source,
        )
        new_visits.append(visit)
        visit_inputs.append(visit_in)

    # 6. Single flush for all new visits → assigns IDs in bulk
    if new_visits:
        db.add_all(new_visits)
        await db.flush()

    # 7. Now all new_visits have .id assigned — bulk-add VisitDrugs + collect deductions
    deductions: dict[int, int] = {}  # {drug_id: total_quantity_to_deduct}
    resolved_drugs: dict[int, Drug] = {}  # {drug_id: Drug} for alert names

    for visit, visit_in in zip(new_visits, visit_inputs):
        visit_ids.append(visit.id)
        for drug_in in visit_in.drugs:
            drug = resolver.resolve(drug_in.drug_insurance_code, drug_in.drug_standard_code)
            if not drug:
                skipped_drugs.append(
                    SkippedDrugOut(
                        drug_code=drug_in.drug_insurance_code or drug_in.drug_standard_code or "unknown",
                        reason="not_found_in_drugs_master",
                    )
                )
                continue
            db.add(VisitDrug(
                visit_id=visit.id,
                drug_id=drug.id,
                quantity_dispensed=drug_in.quantity_dispensed,
            ))
            deductions[drug.id] = deductions.get(drug.id, 0) + drug_in.quantity_dispensed
            resolved_drugs[drug.id] = drug

    # 8. Deduct dispensed quantities from drug_stock (only for new visits)
    await _deduct_dispensed_from_stock(db, pharmacy_id, deductions, resolved_drugs)

    return SyncVisitsResponse(
        synced_count=len(visit_ids),
        visit_ids=visit_ids,
        skipped_drugs=skipped_drugs,
    )


# ---------------------------------------------------------------------------
# sync_drugs: 1 query (was N)
# ---------------------------------------------------------------------------


async def sync_drugs(
    db: AsyncSession, pharmacy_id: int, req: SyncDrugsRequest
) -> SyncDrugsResponse:
    """TBSIM040_01 → drugs 테이블 UPSERT. insurance_code 기준."""
    new_count = 0
    updated_count = 0

    # 1. Prefetch all existing drugs by insurance_code
    codes = {d.insurance_code for d in req.drugs if d.insurance_code}
    existing_map = await _prefetch_drugs_by_insurance_code(db, codes)

    # 2. Loop in memory
    for drug_in in req.drugs:
        existing = existing_map.get(drug_in.insurance_code)

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
            if drug_in.standard_code and existing.standard_code != drug_in.standard_code:
                existing.standard_code = drug_in.standard_code
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

    # 3. Resolve PrescriptionInventory.drug_id for unlinked cassette mappings
    # NOTE: Raw SQL bypasses ORM change tracking (audit hooks won't fire).
    await db.flush()  # ensure new Drug rows have IDs
    unlinked = await db.execute(text(
        "SELECT 1 FROM prescription_inventory"
        " WHERE drug_id IS NULL AND pharmacy_id = :pharmacy_id LIMIT 1"
    ), {"pharmacy_id": pharmacy_id})
    if unlinked.first() is not None:
        await db.execute(text("""
            UPDATE prescription_inventory pi
            SET drug_id = d.id
            FROM drugs d
            WHERE pi.drug_insurance_code = d.insurance_code
              AND pi.drug_id IS NULL
              AND pi.pharmacy_id = :pharmacy_id
        """), {"pharmacy_id": pharmacy_id})

    return SyncDrugsResponse(
        synced_count=new_count + updated_count,
        new_count=new_count,
        updated_count=updated_count,
    )


