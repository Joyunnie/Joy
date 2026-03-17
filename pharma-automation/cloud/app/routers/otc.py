from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.tables import User
from app.schemas.otc import (
    OtcCreateRequest,
    OtcItemResponse,
    OtcListResponse,
    OtcUpdateRequest,
)
from app.services import otc_service

router = APIRouter(prefix="/api/v1/otc-inventory", tags=["app-dev"])


@router.post("", response_model=OtcItemResponse, status_code=status.HTTP_201_CREATED)
async def create_otc_item(
    req: OtcCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await otc_service.create_otc_item(db, user.pharmacy_id, user.id, req)


@router.get("", response_model=OtcListResponse)
async def list_otc_items(
    user: User = Depends(get_current_user),
    low_stock_only: bool = Query(False),
    search: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    return await otc_service.list_otc_items(
        db, user.pharmacy_id,
        low_stock_only=low_stock_only, search=search,
        limit=limit, offset=offset,
    )


@router.get("/{item_id}", response_model=OtcItemResponse)
async def get_otc_item(
    item_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await otc_service.get_otc_item(db, user.pharmacy_id, item_id)


@router.put("/{item_id}", response_model=OtcItemResponse)
async def update_otc_item(
    item_id: int,
    req: OtcUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await otc_service.update_otc_item(
        db, user.pharmacy_id, user.id, item_id, req
    )


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_otc_item(
    item_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await otc_service.delete_otc_item(db, user.pharmacy_id, user.id, item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
