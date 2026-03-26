from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import OtcInventory, ShelfLayout
from app.schemas.shelf_layout import (
    ShelfLayoutCreateRequest,
    ShelfLayoutListResponse,
    ShelfLayoutResponse,
    ShelfLayoutUpdateRequest,
)

VALID_LOCATION_TYPES = {"DISPLAY", "STORAGE"}


def _build_response(layout: ShelfLayout) -> ShelfLayoutResponse:
    return ShelfLayoutResponse(
        id=layout.id,
        pharmacy_id=layout.pharmacy_id,
        name=layout.name,
        location_type=layout.location_type,
        rows=layout.rows,
        cols=layout.cols,
        created_at=layout.created_at,
        updated_at=layout.updated_at,
    )


async def create_layout(
    db: AsyncSession,
    pharmacy_id: int,
    req: ShelfLayoutCreateRequest,
) -> ShelfLayoutResponse:
    if req.location_type not in VALID_LOCATION_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="location_type must be DISPLAY or STORAGE",
        )

    layout = ShelfLayout(
        pharmacy_id=pharmacy_id,
        name=req.name,
        location_type=req.location_type,
        rows=req.rows,
        cols=req.cols,
    )
    db.add(layout)
    await db.flush()
    return _build_response(layout)


async def list_layouts(
    db: AsyncSession,
    pharmacy_id: int,
    location_type: str | None = None,
) -> ShelfLayoutListResponse:
    q = select(ShelfLayout).where(ShelfLayout.pharmacy_id == pharmacy_id)
    if location_type:
        q = q.where(ShelfLayout.location_type == location_type)
    q = q.order_by(ShelfLayout.id)

    result = await db.execute(q)
    layouts = result.scalars().all()
    return ShelfLayoutListResponse(
        items=[_build_response(l) for l in layouts]
    )


async def update_layout(
    db: AsyncSession,
    pharmacy_id: int,
    layout_id: int,
    req: ShelfLayoutUpdateRequest,
) -> ShelfLayoutResponse:
    result = await db.execute(
        select(ShelfLayout).where(
            and_(
                ShelfLayout.id == layout_id,
                ShelfLayout.pharmacy_id == pharmacy_id,
            )
        )
    )
    layout = result.scalar_one_or_none()
    if not layout:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shelf layout not found",
        )

    old_rows, old_cols = layout.rows, layout.cols
    layout.name = req.name
    layout.rows = req.rows
    layout.cols = req.cols
    layout.updated_at = datetime.now(timezone.utc)

    # P26: 격자 축소 시 범위 밖 약품 위치 초기화
    if req.rows < old_rows or req.cols < old_cols:
        await _clear_out_of_bounds(db, pharmacy_id, layout_id, layout.location_type, req.rows, req.cols)

    return _build_response(layout)


async def delete_layout(
    db: AsyncSession,
    pharmacy_id: int,
    layout_id: int,
) -> None:
    result = await db.execute(
        select(ShelfLayout).where(
            and_(
                ShelfLayout.id == layout_id,
                ShelfLayout.pharmacy_id == pharmacy_id,
            )
        )
    )
    layout = result.scalar_one_or_none()
    if not layout:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shelf layout not found",
        )

    # P26: 삭제 전 해당 layout_id를 참조하는 otc_inventory 위치 null로 초기화
    prefix = f"{layout_id}:"
    loc_field = (
        OtcInventory.display_location
        if layout.location_type == "DISPLAY"
        else OtcInventory.storage_location
    )
    await db.execute(
        update(OtcInventory)
        .where(
            and_(
                OtcInventory.pharmacy_id == pharmacy_id,
                loc_field.like(f"{prefix}%"),
            )
        )
        .values(**{loc_field.key: None})
    )

    await db.delete(layout)


async def _clear_out_of_bounds(
    db: AsyncSession,
    pharmacy_id: int,
    layout_id: int,
    location_type: str,
    max_rows: int,
    max_cols: int,
) -> None:
    """격자 축소 시 범위 밖 위치의 약품 location을 null로 초기화."""
    prefix = f"{layout_id}:"
    loc_field = (
        OtcInventory.display_location
        if location_type == "DISPLAY"
        else OtcInventory.storage_location
    )

    # 해당 layout에 배치된 모든 약품 조회
    result = await db.execute(
        select(OtcInventory).where(
            and_(
                OtcInventory.pharmacy_id == pharmacy_id,
                loc_field.like(f"{prefix}%"),
            )
        )
    )
    items = result.scalars().all()

    for inv in items:
        loc_val = getattr(inv, loc_field.key)
        if not loc_val:
            continue
        try:
            coords = loc_val.split(":")[1]
            row, col = int(coords.split(",")[0]), int(coords.split(",")[1])
            if row >= max_rows or col >= max_cols:
                setattr(inv, loc_field.key, None)
        except (IndexError, ValueError):
            continue
