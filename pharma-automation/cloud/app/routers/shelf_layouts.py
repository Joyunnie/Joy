from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.tables import User
from app.schemas.shelf_layout import (
    ShelfLayoutCreateRequest,
    ShelfLayoutListResponse,
    ShelfLayoutResponse,
    ShelfLayoutUpdateRequest,
)
from app.services import shelf_layout_service

router = APIRouter(prefix="/api/v1/shelf-layouts", tags=["app-dev"])


@router.post("", response_model=ShelfLayoutResponse, status_code=status.HTTP_201_CREATED)
async def create_layout(
    req: ShelfLayoutCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await shelf_layout_service.create_layout(db, user.pharmacy_id, req)


@router.get("", response_model=ShelfLayoutListResponse)
async def list_layouts(
    user: User = Depends(get_current_user),
    location_type: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await shelf_layout_service.list_layouts(
        db, user.pharmacy_id, location_type=location_type
    )


@router.put("/{layout_id}", response_model=ShelfLayoutResponse)
async def update_layout(
    layout_id: int,
    req: ShelfLayoutUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await shelf_layout_service.update_layout(
        db, user.pharmacy_id, layout_id, req
    )


@router.delete("/{layout_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_layout(
    layout_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await shelf_layout_service.delete_layout(db, user.pharmacy_id, layout_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
