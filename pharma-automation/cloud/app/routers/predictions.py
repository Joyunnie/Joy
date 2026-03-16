# TODO(Phase 2B): JWT 인증 추가 — 현재는 개발/테스트용
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.api import PredictionListResponse
from app.services import prediction_service

router = APIRouter()


@router.get("", response_model=PredictionListResponse)
async def get_predictions(
    pharmacy_id: int = Query(...),
    days_ahead: int = Query(7),
    include_alerted: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    return await prediction_service.get_predictions(
        db, pharmacy_id, days_ahead=days_ahead, include_alerted=include_alerted
    )
