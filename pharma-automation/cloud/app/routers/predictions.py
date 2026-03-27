from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.tables import User
from app.schemas.api import PredictionListResponse
from app.services import prediction_service

router = APIRouter()


@router.get("", response_model=PredictionListResponse)
async def get_predictions(
    user: User = Depends(get_current_user),
    days_ahead: int = Query(7),
    include_alerted: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    return await prediction_service.get_predictions(
        db, user.pharmacy_id, days_ahead=days_ahead, include_alerted=include_alerted
    )
