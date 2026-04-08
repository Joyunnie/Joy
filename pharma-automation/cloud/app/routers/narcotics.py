from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.tables import User
from app.schemas.narcotics import (
    NarcoticsCreateRequest,
    NarcoticsDeleteRequest,
    NarcoticsDispenseRequest,
    NarcoticsItemResponse,
    NarcoticsListResponse,
    NarcoticsReturnRequest,
    NarcoticsTransactionListResponse,
    NarcoticsUpdateRequest,
)
from app.services import narcotics_service

router = APIRouter(prefix="/api/v1/narcotics-inventory", tags=["app-dev"])


@router.post("", response_model=NarcoticsItemResponse, status_code=status.HTTP_201_CREATED)
async def create_narcotics_item(
    req: NarcoticsCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await narcotics_service.create_narcotics_item(db, user.pharmacy_id, user.id, req)


@router.get("", response_model=NarcoticsListResponse)
async def list_narcotics_items(
    user: User = Depends(get_current_user),
    active_only: bool = Query(True),
    low_stock_only: bool = Query(False),
    search: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await narcotics_service.list_narcotics_items(
        db, user.pharmacy_id,
        active_only=active_only, low_stock_only=low_stock_only,
        search=search, limit=limit, offset=offset,
    )


@router.get("/{item_id}", response_model=NarcoticsItemResponse)
async def get_narcotics_item(
    item_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await narcotics_service.get_narcotics_item(db, user.pharmacy_id, item_id)


@router.put("/{item_id}", response_model=NarcoticsItemResponse)
async def update_narcotics_item(
    item_id: int,
    req: NarcoticsUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await narcotics_service.update_narcotics_item(
        db, user.pharmacy_id, user.id, item_id, req
    )


@router.delete("/{item_id}", response_model=NarcoticsItemResponse)
async def delete_narcotics_item(
    item_id: int,
    req: NarcoticsDeleteRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await narcotics_service.delete_narcotics_item(
        db, user.pharmacy_id, user.id, item_id, req
    )


@router.post("/{item_id}/dispense", response_model=NarcoticsItemResponse)
async def dispense_narcotics(
    item_id: int,
    req: NarcoticsDispenseRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await narcotics_service.dispense_narcotics(
        db, user.pharmacy_id, user.id, item_id, req
    )


@router.post("/{item_id}/return", response_model=NarcoticsItemResponse)
async def return_narcotics(
    item_id: int,
    req: NarcoticsReturnRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await narcotics_service.return_narcotics(
        db, user.pharmacy_id, user.id, item_id, req
    )


@router.get("/{item_id}/transactions", response_model=NarcoticsTransactionListResponse)
async def list_transactions(
    item_id: int,
    user: User = Depends(get_current_user),
    transaction_type: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await narcotics_service.list_transactions(
        db, user.pharmacy_id, item_id,
        transaction_type=transaction_type, limit=limit, offset=offset,
    )
