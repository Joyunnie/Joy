from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import (
    AlertLog,
    Drug,
    DrugThreshold,
    InventoryAuditLog,
    OtcInventory,
)
from app.schemas.otc import (
    OtcCreateRequest,
    OtcItemResponse,
    OtcListResponse,
    OtcUpdateRequest,
)


async def _check_low_stock_alert(
    db: AsyncSession,
    pharmacy_id: int,
    drug_id: int,
    current_quantity: int,
    drug_name: str | None,
) -> None:
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
    if not threshold or current_quantity >= threshold.min_quantity:
        return

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    dup_result = await db.execute(
        select(AlertLog).where(
            and_(
                AlertLog.pharmacy_id == pharmacy_id,
                AlertLog.alert_type == "LOW_STOCK",
                AlertLog.ref_table == "otc_inventory",
                AlertLog.ref_id == drug_id,
                AlertLog.sent_at >= cutoff,
                AlertLog.read_at.is_(None),
            )
        )
    )
    if dup_result.scalar_one_or_none():
        return

    alert = AlertLog(
        pharmacy_id=pharmacy_id,
        alert_type="LOW_STOCK",
        ref_table="otc_inventory",
        ref_id=drug_id,
        message=f"{drug_name} 재고 부족 (현재: {current_quantity}, 최소: {threshold.min_quantity})",
        sent_via="IN_APP",
    )
    db.add(alert)


def _build_item_response(
    inv: OtcInventory,
    drug_name: str | None,
    min_quantity: int | None,
) -> OtcItemResponse:
    is_low = (
        inv.current_quantity < min_quantity
        if min_quantity is not None
        else False
    )
    return OtcItemResponse(
        id=inv.id,
        pharmacy_id=inv.pharmacy_id,
        drug_id=inv.drug_id,
        drug_name=drug_name,
        current_quantity=inv.current_quantity,
        display_location=inv.display_location,
        storage_location=inv.storage_location,
        last_counted_at=inv.last_counted_at,
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


async def create_otc_item(
    db: AsyncSession,
    pharmacy_id: int,
    user_id: int,
    req: OtcCreateRequest,
) -> OtcItemResponse:
    # drug_id 존재 확인
    drug_result = await db.execute(select(Drug).where(Drug.id == req.drug_id))
    drug = drug_result.scalar_one_or_none()
    if not drug:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Drug not found"
        )

    # 중복 확인
    dup_result = await db.execute(
        select(OtcInventory).where(
            and_(
                OtcInventory.pharmacy_id == pharmacy_id,
                OtcInventory.drug_id == req.drug_id,
            )
        )
    )
    if dup_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="OTC inventory item already exists for this drug",
        )

    now = datetime.now(timezone.utc)
    inv = OtcInventory(
        pharmacy_id=pharmacy_id,
        drug_id=req.drug_id,
        current_quantity=req.current_quantity,
        display_location=req.display_location,
        storage_location=req.storage_location,
        last_counted_at=now,
    )
    db.add(inv)
    await db.flush()

    await _check_low_stock_alert(
        db, pharmacy_id, req.drug_id, req.current_quantity, drug.name
    )

    _, min_qty = await _get_drug_and_threshold(db, pharmacy_id, req.drug_id)
    return _build_item_response(inv, drug.name, min_qty)


async def list_otc_items(
    db: AsyncSession,
    pharmacy_id: int,
    low_stock_only: bool = False,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> OtcListResponse:
    base = (
        select(
            OtcInventory,
            Drug.name.label("drug_name"),
            DrugThreshold.min_quantity.label("min_qty"),
        )
        .join(Drug, OtcInventory.drug_id == Drug.id)
        .outerjoin(
            DrugThreshold,
            and_(
                DrugThreshold.pharmacy_id == OtcInventory.pharmacy_id,
                DrugThreshold.drug_id == OtcInventory.drug_id,
                DrugThreshold.is_active == True,  # noqa: E712
            ),
        )
        .where(OtcInventory.pharmacy_id == pharmacy_id)
    )

    if search:
        base = base.where(Drug.name.ilike(f"%{search}%"))

    if low_stock_only:
        base = base.where(
            and_(
                DrugThreshold.min_quantity.isnot(None),
                OtcInventory.current_quantity < DrugThreshold.min_quantity,
            )
        )

    # count
    count_q = select(func.count()).select_from(base.subquery())
    count_result = await db.execute(count_q)
    total = count_result.scalar() or 0

    # fetch
    result = await db.execute(
        base.order_by(OtcInventory.id).offset(offset).limit(limit)
    )
    rows = result.all()

    items = [
        _build_item_response(row.OtcInventory, row.drug_name, row.min_qty)
        for row in rows
    ]
    return OtcListResponse(items=items, total=total)


async def get_otc_item(
    db: AsyncSession, pharmacy_id: int, item_id: int
) -> OtcItemResponse:
    result = await db.execute(
        select(OtcInventory).where(
            and_(
                OtcInventory.id == item_id,
                OtcInventory.pharmacy_id == pharmacy_id,
            )
        )
    )
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OTC inventory item not found",
        )

    drug_name, min_qty = await _get_drug_and_threshold(
        db, pharmacy_id, inv.drug_id
    )
    return _build_item_response(inv, drug_name, min_qty)


async def update_otc_item(
    db: AsyncSession,
    pharmacy_id: int,
    user_id: int,
    item_id: int,
    req: OtcUpdateRequest,
) -> OtcItemResponse:
    result = await db.execute(
        select(OtcInventory).where(
            and_(
                OtcInventory.id == item_id,
                OtcInventory.pharmacy_id == pharmacy_id,
            )
        )
    )
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OTC inventory item not found",
        )

    # Optimistic locking
    if inv.version != req.version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Data has been modified by another user",
        )

    now = datetime.now(timezone.utc)
    # PUT = 전체 덮어쓰기
    inv.current_quantity = req.current_quantity
    inv.display_location = req.display_location
    inv.storage_location = req.storage_location
    inv.version += 1
    inv.updated_at = now
    inv.last_counted_at = now

    drug_name, min_qty = await _get_drug_and_threshold(
        db, pharmacy_id, inv.drug_id
    )

    await _check_low_stock_alert(
        db, pharmacy_id, inv.drug_id, req.current_quantity, drug_name
    )

    return _build_item_response(inv, drug_name, min_qty)


async def delete_otc_item(
    db: AsyncSession, pharmacy_id: int, user_id: int, item_id: int
) -> None:
    result = await db.execute(
        select(OtcInventory).where(
            and_(
                OtcInventory.id == item_id,
                OtcInventory.pharmacy_id == pharmacy_id,
            )
        )
    )
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OTC inventory item not found",
        )

    # P16: audit log 기록
    audit = InventoryAuditLog(
        pharmacy_id=pharmacy_id,
        table_name="otc_inventory",
        record_id=inv.id,
        action="OTC_DELETE",
        old_values={
            "drug_id": inv.drug_id,
            "current_quantity": inv.current_quantity,
            "display_location": inv.display_location,
            "storage_location": inv.storage_location,
            "version": inv.version,
        },
        new_values=None,
        performed_by=user_id,
    )
    db.add(audit)

    await db.delete(inv)
