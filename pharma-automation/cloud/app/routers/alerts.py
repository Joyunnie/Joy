from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.tables import User
from app.schemas.api import AlertListResponse, AlertReadResponse
from app.services import alert_service

router = APIRouter()


@router.get("", response_model=AlertListResponse)
async def get_alerts(
    user: User = Depends(get_current_user),
    alert_type: str | None = Query(None),
    unread_only: bool = Query(False),
    read_only: bool = Query(False),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    return await alert_service.get_alerts(
        db, user.pharmacy_id,
        alert_type=alert_type,
        unread_only=unread_only,
        read_only=read_only,
        limit=limit,
        offset=offset,
    )


@router.patch("/{alert_id}/read", response_model=AlertReadResponse)
async def mark_alert_read(
    alert_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await alert_service.mark_alert_read(db, alert_id, user.pharmacy_id)
