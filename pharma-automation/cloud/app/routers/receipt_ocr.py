"""영수증 OCR 라우터. P32: OCR 엔진 미설정 시 503 반환."""
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.database import get_db
from app.dependencies import get_current_user
from app.models.tables import User
from app.rate_limit import get_pharmacy_key, limiter
from app.schemas.receipt_ocr import (
    ConfirmResponse,
    ReceiptItemUpdateRequest,
    ReceiptListResponse,
    ReceiptOcrDetailResponse,
    ReceiptOcrItemOut,
    ReceiptOcrResponse,
)
from app.services import receipt_ocr_service
from app.services.ocr_engine import is_ocr_available

router = APIRouter(prefix="/api/v1/receipt-ocr", tags=["receipt-ocr"])


def _check_ocr_available():
    """P32: OCR 엔진이 초기화되지 않으면 503."""
    if not is_ocr_available():
        raise HTTPException(
            status_code=503,
            detail="OCR 서비스를 사용할 수 없습니다. PHARMA_GOOGLE_VISION_API_KEY를 설정하세요.",
        )


@router.post("/upload", response_model=ReceiptOcrResponse, status_code=201)
@limiter.limit("10/minute", key_func=get_pharmacy_key)
async def upload_receipt(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _check_ocr_available()
    return await receipt_ocr_service.upload_and_process(db, user.pharmacy_id, file)


@router.get("", response_model=ReceiptListResponse)
async def list_receipts(
    status: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await receipt_ocr_service.list_receipts(
        db, user.pharmacy_id, status, date_from, date_to, limit, offset,
    )


@router.get("/{record_id}", response_model=ReceiptOcrDetailResponse)
async def get_receipt_detail(
    record_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await receipt_ocr_service.get_receipt_detail(db, user.pharmacy_id, record_id)


@router.put("/{record_id}/items/{item_id}", response_model=ReceiptOcrItemOut)
async def update_receipt_item(
    record_id: int,
    item_id: int,
    body: ReceiptItemUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await receipt_ocr_service.update_item(
        db, user.pharmacy_id, record_id, item_id, body.drug_id, body.quantity,
    )


@router.post("/{record_id}/confirm", response_model=ConfirmResponse)
async def confirm_intake(
    record_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await receipt_ocr_service.confirm_intake(db, user.pharmacy_id, record_id, user)


@router.delete("/{record_id}", status_code=204)
async def cancel_receipt(
    record_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await receipt_ocr_service.cancel_receipt(db, user.pharmacy_id, record_id)
