from datetime import datetime, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ServiceError
from app.models.tables import (
    Drug,
    DrugThreshold,
    InventoryAuditLog,
    OtcInventory,
    ShelfLayout,
)
from app.schemas.otc import (
    BatchLocationRemoveRequest,
    BatchLocationRequest,
    OtcCreateRequest,
    OtcItemResponse,
    OtcListResponse,
    OtcUpdateRequest,
)
from app.services.alert_utils import check_and_create_low_stock_alert


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
        raise ServiceError("Drug not found", 404)

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
        raise ServiceError("OTC inventory item already exists for this drug", 409)

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

    await check_and_create_low_stock_alert(
        db, pharmacy_id, req.drug_id, req.current_quantity, drug.name,
        "LOW_STOCK", "otc_inventory",
    )

    _, min_qty = await _get_drug_and_threshold(db, pharmacy_id, req.drug_id)
    return _build_item_response(inv, drug.name, min_qty)


async def list_otc_items(
    db: AsyncSession,
    pharmacy_id: int,
    low_stock_only: bool = False,
    search: str | None = None,
    layout_id: int | None = None,
    unplaced_for_layout: int | None = None,
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

    if layout_id is not None:
        # 특정 레이아웃에 배치된 약만 필터
        layout_result = await db.execute(
            select(ShelfLayout).where(
                and_(ShelfLayout.id == layout_id, ShelfLayout.pharmacy_id == pharmacy_id)
            )
        )
        layout = layout_result.scalar_one_or_none()
        if layout:
            loc_field = (
                OtcInventory.display_location
                if layout.location_type == "DISPLAY"
                else OtcInventory.storage_location
            )
            base = base.where(loc_field.like(f"{layout_id}:%"))

    if unplaced_for_layout is not None:
        # 특정 레이아웃 type에 아직 미배치된 약만 필터
        layout_result = await db.execute(
            select(ShelfLayout).where(
                and_(ShelfLayout.id == unplaced_for_layout, ShelfLayout.pharmacy_id == pharmacy_id)
            )
        )
        layout = layout_result.scalar_one_or_none()
        if layout:
            loc_field = (
                OtcInventory.display_location
                if layout.location_type == "DISPLAY"
                else OtcInventory.storage_location
            )
            base = base.where(loc_field.is_(None))

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
        raise ServiceError("OTC inventory item not found", 404)

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
        raise ServiceError("OTC inventory item not found", 404)

    # Optimistic locking
    if inv.version != req.version:
        raise ServiceError("Data has been modified by another user", 409)

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

    await check_and_create_low_stock_alert(
        db, pharmacy_id, inv.drug_id, req.current_quantity, drug_name,
        "LOW_STOCK", "otc_inventory",
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
        raise ServiceError("OTC inventory item not found", 404)

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


async def batch_update_locations(
    db: AsyncSession,
    pharmacy_id: int,
    req: BatchLocationRequest,
) -> list[OtcItemResponse]:
    """여러 약품의 위치를 일괄 업데이트."""
    # layout 조회
    layout_result = await db.execute(
        select(ShelfLayout).where(
            and_(ShelfLayout.id == req.layout_id, ShelfLayout.pharmacy_id == pharmacy_id)
        )
    )
    layout = layout_result.scalar_one_or_none()
    if not layout:
        raise ServiceError("Shelf layout not found", 404)

    # 범위 검증 + 중복 칸 검증
    seen_positions: set[tuple[int, int]] = set()
    for a in req.assignments:
        if a.row >= layout.rows or a.col >= layout.cols:
            raise ServiceError(
                f"Position ({a.row},{a.col}) is out of bounds for {layout.rows}x{layout.cols} layout", 422
            )
        pos = (a.row, a.col)
        if pos in seen_positions:
            raise ServiceError(f"Duplicate position ({a.row},{a.col})", 422)
        seen_positions.add(pos)

    loc_field_key = (
        "display_location" if layout.location_type == "DISPLAY" else "storage_location"
    )

    results: list[OtcItemResponse] = []
    for a in req.assignments:
        inv_result = await db.execute(
            select(OtcInventory).where(
                and_(
                    OtcInventory.id == a.item_id,
                    OtcInventory.pharmacy_id == pharmacy_id,
                )
            )
        )
        inv = inv_result.scalar_one_or_none()
        if not inv:
            raise ServiceError(f"OTC inventory item {a.item_id} not found", 404)

        loc_value = f"{req.layout_id}:{a.row},{a.col}"
        setattr(inv, loc_field_key, loc_value)

        drug_name, min_qty = await _get_drug_and_threshold(db, pharmacy_id, inv.drug_id)
        results.append(_build_item_response(inv, drug_name, min_qty))

    return results


async def batch_remove_locations(
    db: AsyncSession,
    pharmacy_id: int,
    req: BatchLocationRemoveRequest,
) -> None:
    """여러 약품의 위치를 null로 초기화."""
    layout_result = await db.execute(
        select(ShelfLayout).where(
            and_(ShelfLayout.id == req.layout_id, ShelfLayout.pharmacy_id == pharmacy_id)
        )
    )
    layout = layout_result.scalar_one_or_none()
    if not layout:
        raise ServiceError("Shelf layout not found", 404)

    loc_field_key = (
        "display_location" if layout.location_type == "DISPLAY" else "storage_location"
    )

    for item_id in req.item_ids:
        inv_result = await db.execute(
            select(OtcInventory).where(
                and_(
                    OtcInventory.id == item_id,
                    OtcInventory.pharmacy_id == pharmacy_id,
                )
            )
        )
        inv = inv_result.scalar_one_or_none()
        if not inv:
            raise ServiceError(f"OTC inventory item {item_id} not found", 404)
        setattr(inv, loc_field_key, None)
