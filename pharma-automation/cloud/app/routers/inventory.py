from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.tables import Drug, DrugThreshold, PrescriptionInventory, User
from app.schemas.api import InventoryStatusItem, InventoryStatusResponse

router = APIRouter()


@router.get("/status", response_model=InventoryStatusResponse)
async def get_inventory_status(
    user: User = Depends(get_current_user),
    low_stock_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PrescriptionInventory, Drug, DrugThreshold)
        .outerjoin(Drug, PrescriptionInventory.drug_id == Drug.id)
        .outerjoin(
            DrugThreshold,
            and_(
                DrugThreshold.pharmacy_id == PrescriptionInventory.pharmacy_id,
                DrugThreshold.drug_id == PrescriptionInventory.drug_id,
                DrugThreshold.is_active == True,  # noqa: E712
            ),
        )
        .where(PrescriptionInventory.pharmacy_id == user.pharmacy_id)
        .order_by(PrescriptionInventory.cassette_number)
    )
    rows = result.all()

    items = []
    for inv, drug, threshold in rows:
        min_qty = threshold.min_quantity if threshold else None
        is_low = bool(min_qty is not None and inv.current_quantity < min_qty)

        if low_stock_only and not is_low:
            continue

        items.append(
            InventoryStatusItem(
                cassette_number=inv.cassette_number,
                drug_name=drug.name if drug else None,
                current_quantity=inv.current_quantity,
                min_quantity=min_qty,
                is_low_stock=is_low,
                quantity_synced_at=inv.quantity_synced_at,
            )
        )

    return InventoryStatusResponse(items=items)
