"""Prescription inventory status service."""
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import Drug, DrugThreshold, PrescriptionInventory
from app.schemas.api import InventoryStatusItem, InventoryStatusResponse


async def get_inventory_status(
    db: AsyncSession,
    pharmacy_id: int,
    low_stock_only: bool = False,
) -> InventoryStatusResponse:
    base = (
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
        .where(PrescriptionInventory.pharmacy_id == pharmacy_id)
    )

    if low_stock_only:
        base = base.where(
            and_(
                DrugThreshold.min_quantity.isnot(None),
                PrescriptionInventory.current_quantity < DrugThreshold.min_quantity,
            )
        )

    result = await db.execute(
        base.order_by(PrescriptionInventory.cassette_number)
    )
    rows = result.all()

    items = []
    for inv, drug, threshold in rows:
        min_qty = threshold.min_quantity if threshold else None
        is_low = bool(min_qty is not None and inv.current_quantity < min_qty)
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
