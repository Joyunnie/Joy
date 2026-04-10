from datetime import datetime, timezone

from app.exceptions import ServiceError
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import (
    Drug,
    DrugThreshold,
    InventoryAuditLog,
    NarcoticsInventory,
    NarcoticsTransaction,
)
from app.schemas.narcotics import (
    NarcoticsCreateRequest,
    NarcoticsDeleteRequest,
    NarcoticsDispenseRequest,
    NarcoticsItemResponse,
    NarcoticsListResponse,
    NarcoticsReturnRequest,
    NarcoticsTransactionListResponse,
    NarcoticsTransactionOut,
    NarcoticsUpdateRequest,
)
from app.services.alert_utils import check_and_create_low_stock_alert


# --- Helpers ---


def _build_item_response(
    inv: NarcoticsInventory,
    drug_name: str | None,
    min_quantity: int | None,
) -> NarcoticsItemResponse:
    is_low = (
        inv.current_quantity < min_quantity if min_quantity is not None else False
    )
    return NarcoticsItemResponse(
        id=inv.id,
        pharmacy_id=inv.pharmacy_id,
        drug_id=inv.drug_id,
        drug_name=drug_name,
        lot_number=inv.lot_number,
        current_quantity=inv.current_quantity,
        is_active=inv.is_active,
        last_inspected_at=inv.last_inspected_at,
        version=inv.version,
        created_at=inv.created_at,
        updated_at=inv.updated_at,
        is_low_stock=is_low,
        min_quantity=min_quantity,
    )


async def _get_drug_and_threshold(
    db: AsyncSession, pharmacy_id: int, drug_id: int
) -> tuple[str | None, int | None]:
    drug_result = await db.execute(select(Drug).where(Drug.id == drug_id))
    drug = drug_result.scalar_one_or_none()
    drug_name = drug.name if drug else None

    th_result = await db.execute(
        select(DrugThreshold).where(
            and_(
                DrugThreshold.pharmacy_id == pharmacy_id,
                DrugThreshold.drug_id == drug_id,
                DrugThreshold.is_active == True,  # noqa: E712
            )
        )
    )
    th = th_result.scalar_one_or_none()
    min_qty = th.min_quantity if th else None

    return drug_name, min_qty


async def _get_active_inventory(
    db: AsyncSession, pharmacy_id: int, item_id: int
) -> NarcoticsInventory:
    """Fetch inventory record. 404 if not found or is_active=false."""
    result = await db.execute(
        select(NarcoticsInventory)
        .where(
            and_(
                NarcoticsInventory.id == item_id,
                NarcoticsInventory.pharmacy_id == pharmacy_id,
                NarcoticsInventory.is_active == True,  # noqa: E712
            )
        )
        .with_for_update()
    )
    inv = result.scalar_one_or_none()
    if not inv:
        raise ServiceError("Narcotics inventory item not found", 404)
    return inv


async def _record_transaction(
    db: AsyncSession,
    pharmacy_id: int,
    inventory_id: int,
    tx_type: str,
    quantity: int,
    remaining: int,
    user_id: int,
    **kwargs,
) -> NarcoticsTransaction:
    tx = NarcoticsTransaction(
        pharmacy_id=pharmacy_id,
        narcotics_inventory_id=inventory_id,
        transaction_type=tx_type,
        quantity=quantity,
        remaining_quantity=remaining,
        performed_by=user_id,
        patient_hash=kwargs.get("patient_hash"),
        prescription_number=kwargs.get("prescription_number"),
        notes=kwargs.get("notes"),
    )
    db.add(tx)
    await db.flush()
    return tx


async def _record_audit(
    db: AsyncSession,
    pharmacy_id: int,
    record_id: int,
    action: str,
    old_values: dict | None,
    new_values: dict | None,
    user_id: int,
) -> None:
    audit = InventoryAuditLog(
        pharmacy_id=pharmacy_id,
        table_name="narcotics_inventory",
        record_id=record_id,
        action=action,
        old_values=old_values,
        new_values=new_values,
        performed_by=user_id,
    )
    db.add(audit)


# --- Core CRUD ---


async def create_narcotics_item(
    db: AsyncSession,
    pharmacy_id: int,
    user_id: int,
    req: NarcoticsCreateRequest,
) -> NarcoticsItemResponse:
    # drug_id 존재 + NARCOTIC 카테고리 확인
    drug_result = await db.execute(select(Drug).where(Drug.id == req.drug_id))
    drug = drug_result.scalar_one_or_none()
    if not drug:
        raise ServiceError("Drug not found", 404)
    if drug.category != "NARCOTIC":
        raise ServiceError("Drug is not a NARCOTIC category", 400)

    # 중복 확인 (pharmacy_id, drug_id, lot_number) — lock row for reactivation
    dup_result = await db.execute(
        select(NarcoticsInventory)
        .where(
            and_(
                NarcoticsInventory.pharmacy_id == pharmacy_id,
                NarcoticsInventory.drug_id == req.drug_id,
                NarcoticsInventory.lot_number == req.lot_number,
            )
        )
        .with_for_update()
    )
    existing = dup_result.scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if existing:
        if existing.is_active:
            raise ServiceError("Narcotics inventory item already exists for this drug and lot", 409)
        # Reactivate soft-deleted record
        existing.is_active = True
        existing.current_quantity += req.quantity
        existing.version += 1
        existing.updated_at = now
        inv = existing
    else:
        inv = NarcoticsInventory(
            pharmacy_id=pharmacy_id,
            drug_id=req.drug_id,
            lot_number=req.lot_number,
            current_quantity=req.quantity,
        )
        db.add(inv)
        await db.flush()

    # RECEIVE transaction
    await _record_transaction(
        db, pharmacy_id, inv.id, "RECEIVE", req.quantity,
        inv.current_quantity, user_id, notes=req.notes,
    )

    # Audit log
    await _record_audit(
        db, pharmacy_id, inv.id, "INSERT", None,
        {
            "drug_id": inv.drug_id,
            "lot_number": inv.lot_number,
            "current_quantity": inv.current_quantity,
            "version": inv.version,
        },
        user_id,
    )

    await check_and_create_low_stock_alert(
        db, pharmacy_id, req.drug_id, inv.current_quantity, drug.name,
        "NARCOTICS_LOW", "narcotics_inventory",
    )

    _, min_qty = await _get_drug_and_threshold(db, pharmacy_id, req.drug_id)
    return _build_item_response(inv, drug.name, min_qty)


async def list_narcotics_items(
    db: AsyncSession,
    pharmacy_id: int,
    active_only: bool = True,
    low_stock_only: bool = False,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> NarcoticsListResponse:
    base = (
        select(
            NarcoticsInventory,
            Drug.name.label("drug_name"),
            DrugThreshold.min_quantity.label("min_qty"),
        )
        .join(Drug, NarcoticsInventory.drug_id == Drug.id)
        .outerjoin(
            DrugThreshold,
            and_(
                DrugThreshold.pharmacy_id == NarcoticsInventory.pharmacy_id,
                DrugThreshold.drug_id == NarcoticsInventory.drug_id,
                DrugThreshold.is_active == True,  # noqa: E712
            ),
        )
        .where(NarcoticsInventory.pharmacy_id == pharmacy_id)
    )

    if active_only:
        base = base.where(NarcoticsInventory.is_active == True)  # noqa: E712

    if search:
        base = base.where(Drug.name.ilike(f"%{search}%"))

    if low_stock_only:
        base = base.where(
            and_(
                DrugThreshold.min_quantity.isnot(None),
                NarcoticsInventory.current_quantity < DrugThreshold.min_quantity,
            )
        )

    count_q = select(func.count()).select_from(base.subquery())
    count_result = await db.execute(count_q)
    total = count_result.scalar() or 0

    result = await db.execute(
        base.order_by(NarcoticsInventory.id).offset(offset).limit(limit)
    )
    rows = result.all()

    items = [
        _build_item_response(row.NarcoticsInventory, row.drug_name, row.min_qty)
        for row in rows
    ]
    return NarcoticsListResponse(items=items, total=total)


async def get_narcotics_item(
    db: AsyncSession, pharmacy_id: int, item_id: int
) -> NarcoticsItemResponse:
    # pharmacy_id 필터 적용, is_active 필터만 미적용 (법적 감사용)
    result = await db.execute(
        select(NarcoticsInventory).where(
            and_(
                NarcoticsInventory.id == item_id,
                NarcoticsInventory.pharmacy_id == pharmacy_id,
            )
        )
    )
    inv = result.scalar_one_or_none()
    if not inv:
        raise ServiceError("Narcotics inventory item not found", 404)

    drug_name, min_qty = await _get_drug_and_threshold(
        db, pharmacy_id, inv.drug_id
    )
    return _build_item_response(inv, drug_name, min_qty)


async def update_narcotics_item(
    db: AsyncSession,
    pharmacy_id: int,
    user_id: int,
    item_id: int,
    req: NarcoticsUpdateRequest,
) -> NarcoticsItemResponse:
    inv = await _get_active_inventory(db, pharmacy_id, item_id)

    if inv.version != req.version:
        raise ServiceError("Data has been modified by another user", 409)

    now = datetime.now(timezone.utc)
    old_quantity = inv.current_quantity
    quantity_delta = req.current_quantity - old_quantity

    old_values = {
        "current_quantity": old_quantity,
        "last_inspected_at": inv.last_inspected_at.isoformat() if inv.last_inspected_at else None,
        "version": inv.version,
    }

    inv.current_quantity = req.current_quantity
    if req.last_inspected_at is not None:
        inv.last_inspected_at = req.last_inspected_at
    inv.version += 1
    inv.updated_at = now

    new_values = {
        "current_quantity": inv.current_quantity,
        "last_inspected_at": inv.last_inspected_at.isoformat() if inv.last_inspected_at else None,
        "version": inv.version,
    }

    # ADJUST transaction only if quantity changed
    if quantity_delta != 0:
        await _record_transaction(
            db, pharmacy_id, inv.id, "ADJUST", quantity_delta,
            inv.current_quantity, user_id, notes=req.notes,
        )

    await _record_audit(
        db, pharmacy_id, inv.id, "UPDATE", old_values, new_values, user_id,
    )

    drug_name, min_qty = await _get_drug_and_threshold(
        db, pharmacy_id, inv.drug_id
    )
    await check_and_create_low_stock_alert(
        db, pharmacy_id, inv.drug_id, inv.current_quantity, drug_name,
        "NARCOTICS_LOW", "narcotics_inventory",
    )

    return _build_item_response(inv, drug_name, min_qty)


async def delete_narcotics_item(
    db: AsyncSession,
    pharmacy_id: int,
    user_id: int,
    item_id: int,
    req: NarcoticsDeleteRequest,
) -> NarcoticsItemResponse:
    inv = await _get_active_inventory(db, pharmacy_id, item_id)

    if inv.version != req.version:
        raise ServiceError("Data has been modified by another user", 409)

    old_quantity = inv.current_quantity

    # DISPOSE transaction
    await _record_transaction(
        db, pharmacy_id, inv.id, "DISPOSE", -old_quantity,
        0, user_id, notes=req.notes,
    )

    now = datetime.now(timezone.utc)
    inv.current_quantity = 0
    inv.is_active = False
    inv.version += 1
    inv.updated_at = now

    await _record_audit(
        db, pharmacy_id, inv.id, "NARCOTICS_DEACTIVATE",
        {"current_quantity": old_quantity, "is_active": True, "version": inv.version - 1},
        {"current_quantity": 0, "is_active": False, "version": inv.version},
        user_id,
    )

    drug_name, min_qty = await _get_drug_and_threshold(
        db, pharmacy_id, inv.drug_id
    )
    return _build_item_response(inv, drug_name, min_qty)


async def dispense_narcotics(
    db: AsyncSession,
    pharmacy_id: int,
    user_id: int,
    item_id: int,
    req: NarcoticsDispenseRequest,
) -> NarcoticsItemResponse:
    inv = await _get_active_inventory(db, pharmacy_id, item_id)

    if inv.version != req.version:
        raise ServiceError("Data has been modified by another user", 409)

    if inv.current_quantity < req.quantity:
        raise ServiceError("Insufficient stock", 400)

    now = datetime.now(timezone.utc)
    inv.current_quantity -= req.quantity
    inv.version += 1
    inv.updated_at = now

    await _record_transaction(
        db, pharmacy_id, inv.id, "DISPENSE", -req.quantity,
        inv.current_quantity, user_id,
        patient_hash=req.patient_hash,
        prescription_number=req.prescription_number,
        notes=req.notes,
    )

    await _record_audit(
        db, pharmacy_id, inv.id, "UPDATE",
        {"current_quantity": inv.current_quantity + req.quantity, "version": inv.version - 1},
        {"current_quantity": inv.current_quantity, "version": inv.version},
        user_id,
    )

    drug_name, min_qty = await _get_drug_and_threshold(
        db, pharmacy_id, inv.drug_id
    )
    await check_and_create_low_stock_alert(
        db, pharmacy_id, inv.drug_id, inv.current_quantity, drug_name,
        "NARCOTICS_LOW", "narcotics_inventory",
    )

    return _build_item_response(inv, drug_name, min_qty)


async def return_narcotics(
    db: AsyncSession,
    pharmacy_id: int,
    user_id: int,
    item_id: int,
    req: NarcoticsReturnRequest,
) -> NarcoticsItemResponse:
    """도매상에 반품 (재고 감소)."""
    inv = await _get_active_inventory(db, pharmacy_id, item_id)

    if inv.version != req.version:
        raise ServiceError("Data has been modified by another user", 409)

    if inv.current_quantity < req.quantity:
        raise ServiceError("Insufficient stock", 400)

    now = datetime.now(timezone.utc)
    inv.current_quantity -= req.quantity
    inv.version += 1
    inv.updated_at = now

    await _record_transaction(
        db, pharmacy_id, inv.id, "RETURN", -req.quantity,
        inv.current_quantity, user_id, notes=req.notes,
    )

    await _record_audit(
        db, pharmacy_id, inv.id, "UPDATE",
        {"current_quantity": inv.current_quantity + req.quantity, "version": inv.version - 1},
        {"current_quantity": inv.current_quantity, "version": inv.version},
        user_id,
    )

    drug_name, min_qty = await _get_drug_and_threshold(
        db, pharmacy_id, inv.drug_id
    )
    return _build_item_response(inv, drug_name, min_qty)


async def list_transactions(
    db: AsyncSession,
    pharmacy_id: int,
    item_id: int,
    transaction_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> NarcoticsTransactionListResponse:
    # Verify item belongs to pharmacy (pharmacy_id 필터 적용, is_active 미적용)
    inv_result = await db.execute(
        select(NarcoticsInventory).where(
            and_(
                NarcoticsInventory.id == item_id,
                NarcoticsInventory.pharmacy_id == pharmacy_id,
            )
        )
    )
    if not inv_result.scalar_one_or_none():
        raise ServiceError("Narcotics inventory item not found", 404)

    base = select(NarcoticsTransaction).where(
        and_(
            NarcoticsTransaction.narcotics_inventory_id == item_id,
            NarcoticsTransaction.pharmacy_id == pharmacy_id,
        )
    )

    if transaction_type:
        base = base.where(NarcoticsTransaction.transaction_type == transaction_type)

    count_q = select(func.count()).select_from(base.subquery())
    count_result = await db.execute(count_q)
    total = count_result.scalar() or 0

    result = await db.execute(
        base.order_by(NarcoticsTransaction.id.desc()).offset(offset).limit(limit)
    )
    rows = result.scalars().all()

    transactions = [
        NarcoticsTransactionOut(
            id=tx.id,
            transaction_type=tx.transaction_type,
            quantity=tx.quantity,
            remaining_quantity=tx.remaining_quantity,
            patient_hash=tx.patient_hash,
            prescription_number=tx.prescription_number,
            performed_by=tx.performed_by,
            notes=tx.notes,
            created_at=tx.created_at,
        )
        for tx in rows
    ]
    return NarcoticsTransactionListResponse(transactions=transactions, total=total)
