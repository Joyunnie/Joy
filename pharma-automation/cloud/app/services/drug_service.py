from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import Drug
from app.schemas.drug import DrugListResponse, DrugOut


async def list_drugs(
    db: AsyncSession,
    search: str | None = None,
    category: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> DrugListResponse:
    conditions = []

    if search:
        conditions.append(Drug.name.ilike(f"%{search}%"))

    if category and category.upper() != "ALL":
        conditions.append(Drug.category == category.upper())

    where_clause = and_(*conditions) if conditions else True

    count_result = await db.execute(
        select(func.count(Drug.id)).where(where_clause)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(Drug)
        .where(where_clause)
        .order_by(Drug.name)
        .offset(offset)
        .limit(limit)
    )
    drugs = result.scalars().all()

    return DrugListResponse(
        items=[
            DrugOut(
                id=d.id,
                standard_code=d.standard_code,
                name=d.name,
                category=d.category,
            )
            for d in drugs
        ],
        total=total,
    )
