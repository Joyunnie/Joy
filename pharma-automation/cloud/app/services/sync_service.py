from datetime import datetime, timedelta, timezone

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
)
from app.schemas.drug_stock import SyncDrugStockRequest, SyncDrugStockResponse
from app.schemas.drug_sync import SyncDrugsRequest, SyncDrugsResponse


async def sync_inventory(
    db: AsyncSession, pharmacy_id: int, req: SyncInventoryRequest
) -> SyncInventoryResponse:
    low_stock_alerts: list[LowStockAlertOut] = []
    synced = 0

    for item in req.items:
        # Resolve drug_id if standard_code provided
        drug_id = None
        drug_name = None
        if item.drug_standard_code:
            result = await db.execute(
                select(Drug).where(Drug.standard_code == item.drug_standard_code)
            )
            drug = result.scalar_one_or_none()
            if drug:
                drug_id = drug.id
                drug_name = drug.name

        # UPSERT prescription_inventory
        result = await db.execute(
            select(PrescriptionInventory).where(
                and_(
                    PrescriptionInventory.pharmacy_id == pharmacy_id,
                    PrescriptionInventory.cassette_number == item.cassette_number,
                )
            )
        )
        inv = result.scalar_one_or_none()

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
                # No drug mapping and no existing record — create with placeholder
                inv = PrescriptionInventory(
                    pharmacy_id=pharmacy_id,
                    drug_id=drug_id or 0,  # Will need drug mapping later
                    cassette_number=item.cassette_number,
                    current_quantity=item.current_quantity,
                    quantity_source=item.quantity_source,
                    quantity_synced_at=req.synced_at,
                )
                # Skip insert if no drug_id — can't create without FK
                synced += 1
                continue
            inv = PrescriptionInventory(
                pharmacy_id=pharmacy_id,
                drug_id=drug_id,
                cassette_number=item.cassette_number,
                current_quantity=item.current_quantity,
                quantity_source=item.quantity_source,
                quantity_synced_at=req.synced_at,
            )
            db.add(inv)

        synced += 1

        # LOW_STOCK check (only if drug_id exists)
        if drug_id:
            threshold_result = await db.execute(
                select(DrugThreshold).where(
                    and_(
                        DrugThreshold.pharmacy_id == pharmacy_id,
                        DrugThreshold.drug_id == drug_id,
                        DrugThreshold.is_active == True,  # noqa: E712
                    )
                )
            )
            threshold = threshold_result.scalar_one_or_none()
            if threshold and item.current_quantity < threshold.min_quantity:
                # Check for duplicate alert in last 24h
                cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
                dup_result = await db.execute(
                    select(AlertLog).where(
                        and_(
                            AlertLog.pharmacy_id == pharmacy_id,
                            AlertLog.alert_type == "LOW_STOCK",
                            AlertLog.ref_table == "prescription_inventory",
                            AlertLog.ref_id == drug_id,
                            AlertLog.sent_at >= cutoff,
                            AlertLog.read_at.is_(None),
                        )
                    )
                )
                if not dup_result.scalar_one_or_none():
                    alert = AlertLog(
                        pharmacy_id=pharmacy_id,
                        alert_type="LOW_STOCK",
                        ref_table="prescription_inventory",
                        ref_id=drug_id,
                        message=f"{drug_name} 재고 부족 (현재: {item.current_quantity}, 최소: {threshold.min_quantity})",
                        sent_via="IN_APP",
                    )
                    db.add(alert)
                    low_stock_alerts.append(
                        LowStockAlertOut(
                            drug_name=drug_name or "",
                            current_quantity=item.current_quantity,
                            min_quantity=threshold.min_quantity,
                        )
                    )

    return SyncInventoryResponse(synced_count=synced, low_stock_alerts=low_stock_alerts)


async def sync_cassette_mapping(
    db: AsyncSession, pharmacy_id: int, req: SyncCassetteMappingRequest
) -> SyncCassetteMappingResponse:
    new_count = 0
    updated_count = 0

    for mapping in req.mappings:
        # Lookup drug_id
        drug_result = await db.execute(
            select(Drug).where(Drug.standard_code == mapping.drug_standard_code)
        )
        drug = drug_result.scalar_one_or_none()
        if not drug:
            from app.exceptions import ValidationError
            raise ValidationError(f"Drug not found: {mapping.drug_standard_code}")

        # UPSERT
        result = await db.execute(
            select(PrescriptionInventory).where(
                and_(
                    PrescriptionInventory.pharmacy_id == pharmacy_id,
                    PrescriptionInventory.cassette_number == mapping.cassette_number,
                )
            )
        )
        inv = result.scalar_one_or_none()

        if inv:
            inv.drug_id = drug.id
            inv.mapping_source = mapping.mapping_source
            inv.mapping_synced_at = req.synced_at
            inv.updated_at = datetime.now(timezone.utc)
            updated_count += 1
        else:
            inv = PrescriptionInventory(
                pharmacy_id=pharmacy_id,
                drug_id=drug.id,
                cassette_number=mapping.cassette_number,
                current_quantity=0,
                mapping_source=mapping.mapping_source,
                mapping_synced_at=req.synced_at,
            )
            db.add(inv)
            new_count += 1

    return SyncCassetteMappingResponse(
        synced_count=new_count + updated_count,
        new_mappings=new_count,
        updated_mappings=updated_count,
    )


async def sync_visits(
    db: AsyncSession, pharmacy_id: int, req: SyncVisitsRequest
) -> SyncVisitsResponse:
    visit_ids: list[int] = []
    skipped_drugs: list[SkippedDrugOut] = []

    for visit_in in req.visits:
        # Soft duplicate check
        result = await db.execute(
            select(PatientVisitHistory).where(
                and_(
                    PatientVisitHistory.pharmacy_id == pharmacy_id,
                    PatientVisitHistory.patient_hash == visit_in.patient_hash,
                    PatientVisitHistory.visit_date == visit_in.visit_date,
                    PatientVisitHistory.source == visit_in.source,
                )
            )
        )
        existing = result.scalars().all()

        # Check if same drug combination already exists
        is_duplicate = False
        incoming_codes = sorted([d.drug_standard_code for d in visit_in.drugs])
        for ex_visit in existing:
            vd_result = await db.execute(
                select(VisitDrug, Drug).join(Drug, VisitDrug.drug_id == Drug.id).where(
                    VisitDrug.visit_id == ex_visit.id
                )
            )
            existing_codes = sorted([row[1].standard_code for row in vd_result.all()])
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

        # INSERT visit_drugs (skip drugs not found in drugs master)
        for drug_in in visit_in.drugs:
            drug_result = await db.execute(
                select(Drug).where(Drug.standard_code == drug_in.drug_standard_code)
            )
            drug = drug_result.scalar_one_or_none()
            if not drug:
                skipped_drugs.append(
                    SkippedDrugOut(
                        drug_standard_code=drug_in.drug_standard_code,
                        reason="not_found_in_drugs_master",
                    )
                )
                continue

            visit_drug = VisitDrug(
                visit_id=visit.id,
                drug_id=drug.id,
                quantity_dispensed=drug_in.quantity_dispensed,
            )
            db.add(visit_drug)

    return SyncVisitsResponse(
        synced_count=len(visit_ids),
        visit_ids=visit_ids,
        skipped_drugs=skipped_drugs,
    )


async def sync_drugs(
    db: AsyncSession, req: SyncDrugsRequest
) -> SyncDrugsResponse:
    """DA_Goods → drugs 테이블 UPSERT. standard_code 기준."""
    new_count = 0
    updated_count = 0

    for drug_in in req.drugs:
        result = await db.execute(
            select(Drug).where(Drug.standard_code == drug_in.standard_code)
        )
        existing = result.scalar_one_or_none()

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
            if changed:
                existing.updated_at = datetime.now(timezone.utc)
                updated_count += 1
        else:
            drug = Drug(
                standard_code=drug_in.standard_code,
                name=drug_in.name,
                manufacturer=drug_in.manufacturer,
                category=drug_in.category,
            )
            db.add(drug)
            new_count += 1

    return SyncDrugsResponse(
        synced_count=new_count + updated_count,
        new_count=new_count,
        updated_count=updated_count,
    )


async def sync_drug_stock(
    db: AsyncSession, pharmacy_id: int, req: SyncDrugStockRequest
) -> SyncDrugStockResponse:
    """PM+20 TEMP_STOCK → drug_stock 테이블 UPSERT. (pharmacy_id, drug_id) 기준."""
    low_stock_alerts: list[LowStockAlertOut] = []
    synced = 0
    skipped = 0

    for item in req.items:
        # drug_standard_code → Drug.id
        result = await db.execute(
            select(Drug).where(Drug.standard_code == item.drug_standard_code)
        )
        drug = result.scalar_one_or_none()
        if not drug:
            skipped += 1
            continue

        # UPSERT drug_stock
        result = await db.execute(
            select(DrugStock).where(
                and_(
                    DrugStock.pharmacy_id == pharmacy_id,
                    DrugStock.drug_id == drug.id,
                )
            )
        )
        stock = result.scalar_one_or_none()

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

        # LOW_STOCK check
        # TEMP_STOCK 음수값은 실재고 마이너스. threshold 비교 시 음수 < min_quantity이므로
        # LOW_STOCK 알림 자동 생성
        threshold_result = await db.execute(
            select(DrugThreshold).where(
                and_(
                    DrugThreshold.pharmacy_id == pharmacy_id,
                    DrugThreshold.drug_id == drug.id,
                    DrugThreshold.is_active == True,  # noqa: E712
                )
            )
        )
        threshold = threshold_result.scalar_one_or_none()
        if threshold and item.current_quantity < threshold.min_quantity:
            # Dedup: no duplicate alert in last 24h
            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            dup_result = await db.execute(
                select(AlertLog).where(
                    and_(
                        AlertLog.pharmacy_id == pharmacy_id,
                        AlertLog.alert_type == "LOW_STOCK",
                        AlertLog.ref_table == "drug_stock",
                        AlertLog.ref_id == drug.id,
                        AlertLog.sent_at >= cutoff,
                        AlertLog.read_at.is_(None),
                    )
                )
            )
            if not dup_result.scalar_one_or_none():
                alert = AlertLog(
                    pharmacy_id=pharmacy_id,
                    alert_type="LOW_STOCK",
                    ref_table="drug_stock",
                    ref_id=drug.id,
                    message=f"{drug.name} 재고 부족 (현재: {item.current_quantity}, 최소: {threshold.min_quantity})",
                    sent_via="IN_APP",
                )
                db.add(alert)
                low_stock_alerts.append(
                    LowStockAlertOut(
                        drug_name=drug.name,
                        current_quantity=int(item.current_quantity),
                        min_quantity=threshold.min_quantity,
                    )
                )

    return SyncDrugStockResponse(
        synced_count=synced,
        skipped_count=skipped,
        low_stock_alerts=low_stock_alerts,
    )
