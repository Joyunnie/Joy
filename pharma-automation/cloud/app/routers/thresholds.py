from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.tables import User
from app.schemas.threshold import (
    ThresholdCreateRequest,
    ThresholdItemResponse,
    ThresholdListResponse,
    ThresholdUpdateRequest,
)
from app.services import threshold_service

router = APIRouter(prefix="/api/v1/thresholds", tags=["app-dev"])


@router.post("", response_model=ThresholdItemResponse, status_code=status.HTTP_201_CREATED)
async def create_threshold(
    req: ThresholdCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await threshold_service.create_threshold(db, user.pharmacy_id, req)


@router.get("", response_model=ThresholdListResponse)
async def list_thresholds(
    user: User = Depends(get_current_user),
    search: str | None = Query(None),
    category: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    return await threshold_service.list_thresholds(
        db, user.pharmacy_id,
        search=search, category=category,
        limit=limit, offset=offset,
    )


@router.put("/{threshold_id}", response_model=ThresholdItemResponse)
async def update_threshold(
    threshold_id: int,
    req: ThresholdUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await threshold_service.update_threshold(
        db, user.pharmacy_id, threshold_id, req
    )


@router.delete("/{threshold_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_threshold(
    threshold_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await threshold_service.delete_threshold(db, user.pharmacy_id, threshold_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
