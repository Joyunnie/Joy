from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.tables import User
from app.schemas.api import InventoryStatusResponse
from app.services import inventory_service

router = APIRouter()


@router.get("/status", response_model=InventoryStatusResponse)
async def get_inventory_status(
    user: User = Depends(get_current_user),
    low_stock_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    return await inventory_service.get_inventory_status(
        db, user.pharmacy_id, low_stock_only=low_stock_only,
    )
