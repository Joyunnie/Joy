"""처방전 OCR 라우터."""
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.database import get_db
from app.dependencies import get_current_user
from app.models.tables import User
from app.rate_limit import get_pharmacy_key, limiter
from app.schemas.prescription_ocr import (
    PrescriptionConfirmResponse,
    PrescriptionDrugUpdateRequest,
    PrescriptionListResponse,
    PrescriptionOcrDetailResponse,
    PrescriptionOcrDrugOut,
    PrescriptionOcrResponse,
)
from app.services import prescription_ocr_service
from app.services.ocr_engine import is_ocr_available

router = APIRouter(prefix="/api/v1/prescription-ocr", tags=["prescription-ocr"])


def _check_ocr_available():
    if not is_ocr_available():
        raise HTTPException(
            status_code=503,
            detail="OCR 서비스를 사용할 수 없습니다. PHARMA_GOOGLE_VISION_API_KEY를 설정하세요.",
        )


@router.post("/upload", response_model=PrescriptionOcrResponse, status_code=201)
@limiter.limit("10/minute", key_func=get_pharmacy_key)
async def upload_prescription(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _check_ocr_available()
    return await prescription_ocr_service.upload_and_process(db, user.pharmacy_id, file)


@router.get("", response_model=PrescriptionListResponse)
async def list_prescriptions(
    status: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await prescription_ocr_service.list_prescriptions(
        db, user.pharmacy_id, status, date_from, date_to, limit, offset,
    )


@router.get("/{record_id}", response_model=PrescriptionOcrDetailResponse)
async def get_prescription_detail(
    record_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await prescription_ocr_service.get_prescription_detail(db, user.pharmacy_id, record_id)


@router.put("/{record_id}/drugs/{drug_item_id}", response_model=PrescriptionOcrDrugOut)
async def update_prescription_drug(
    record_id: int,
    drug_item_id: int,
    body: PrescriptionDrugUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await prescription_ocr_service.update_drug(
        db, user.pharmacy_id, record_id, drug_item_id,
        body.drug_id, body.dosage, body.frequency, body.days,
    )


@router.post("/{record_id}/confirm", response_model=PrescriptionConfirmResponse)
async def confirm_prescription(
    record_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await prescription_ocr_service.confirm_prescription(db, user.pharmacy_id, record_id, user)


@router.delete("/{record_id}", status_code=204)
async def cancel_prescription(
    record_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await prescription_ocr_service.cancel_prescription(db, user.pharmacy_id, record_id)
