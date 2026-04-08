from datetime import datetime, timezone

from app.exceptions import ServiceError
from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import Drug, DrugThreshold
from app.schemas.threshold import (
    ThresholdCreateRequest,
    ThresholdItemResponse,
    ThresholdListResponse,
    ThresholdUpdateRequest,
)


def _build_item_response(
    th: DrugThreshold,
    drug_name: str | None,
    drug_category: str | None,
) -> ThresholdItemResponse:
    return ThresholdItemResponse(
        id=th.id,
        pharmacy_id=th.pharmacy_id,
        drug_id=th.drug_id,
        drug_name=drug_name,
        drug_category=drug_category,
        min_quantity=th.min_quantity,
        is_active=th.is_active,
        created_at=th.created_at,
        updated_at=th.updated_at,
    )


async def create_threshold(
    db: AsyncSession,
    pharmacy_id: int,
    req: ThresholdCreateRequest,
) -> ThresholdItemResponse:
    # drug_id 존재 확인
    drug_result = await db.execute(select(Drug).where(Drug.id == req.drug_id))
    drug = drug_result.scalar_one_or_none()
    if not drug:
        raise ServiceError("Drug not found", 404)

    th = DrugThreshold(
        pharmacy_id=pharmacy_id,
        drug_id=req.drug_id,
        min_quantity=req.min_quantity,
        is_active=True,
    )
    db.add(th)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise ServiceError("Threshold already exists for this drug", 409)

    return _build_item_response(th, drug.name, drug.category)


async def list_thresholds(
    db: AsyncSession,
    pharmacy_id: int,
    search: str | None = None,
    category: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> ThresholdListResponse:
    base = (
        select(
            DrugThreshold,
            Drug.name.label("drug_name"),
            Drug.category.label("drug_category"),
        )
        .join(Drug, DrugThreshold.drug_id == Drug.id)
        .where(DrugThreshold.pharmacy_id == pharmacy_id)
    )

    if search:
        base = base.where(Drug.name.ilike(f"%{search}%"))

    if category:
        base = base.where(Drug.category == category)

    # count
    count_q = select(func.count()).select_from(base.subquery())
    count_result = await db.execute(count_q)
    total = count_result.scalar() or 0

    # fetch
    result = await db.execute(
        base.order_by(DrugThreshold.id).offset(offset).limit(limit)
    )
    rows = result.all()

    items = [
        _build_item_response(row.DrugThreshold, row.drug_name, row.drug_category)
        for row in rows
    ]
    return ThresholdListResponse(items=items, total=total)


async def update_threshold(
    db: AsyncSession,
    pharmacy_id: int,
    threshold_id: int,
    req: ThresholdUpdateRequest,
) -> ThresholdItemResponse:
    result = await db.execute(
        select(DrugThreshold).where(
            and_(
                DrugThreshold.id == threshold_id,
                DrugThreshold.pharmacy_id == pharmacy_id,
            )
        )
    )
    th = result.scalar_one_or_none()
    if not th:
        raise ServiceError("Threshold not found", 404)

    th.min_quantity = req.min_quantity
    th.is_active = req.is_active
    th.updated_at = datetime.now(timezone.utc)

    # drug info for response
    drug_result = await db.execute(select(Drug).where(Drug.id == th.drug_id))
    drug = drug_result.scalar_one_or_none()

    return _build_item_response(
        th,
        drug.name if drug else None,
        drug.category if drug else None,
    )


async def delete_threshold(
    db: AsyncSession,
    pharmacy_id: int,
    threshold_id: int,
) -> None:
    result = await db.execute(
        select(DrugThreshold).where(
            and_(
                DrugThreshold.id == threshold_id,
                DrugThreshold.pharmacy_id == pharmacy_id,
            )
        )
    )
    th = result.scalar_one_or_none()
    if not th:
        raise ServiceError("Threshold not found", 404)

    await db.delete(th)
