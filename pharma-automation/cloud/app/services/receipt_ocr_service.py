"""영수증 OCR 서비스: 업로드 → OCR → 매칭 → 중복감지 → 입고확정."""
import logging
import os
import shutil
import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import UploadFile
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.tables import (
    Drug,
    DrugStock,
    OtcInventory,
    ReceiptOcrItem,
    ReceiptOcrRecord,
    User,
)
from app.schemas.receipt_ocr import (
    ConfirmResponse,
    ReceiptListResponse,
    ReceiptOcrDetailResponse,
    ReceiptOcrItemOut,
    ReceiptOcrRecordOut,
    ReceiptOcrResponse,
)
from app.services.drug_matcher import match_drug
from app.services.ocr_engine import get_ocr_engine
from app.services.receipt_parser import parse_receipt_text

logger = logging.getLogger(__name__)

ALLOWED_TYPES = {"image/jpeg", "image/png"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def _upload_dir() -> str:
    return settings.upload_dir


def _record_to_out(record: ReceiptOcrRecord, item_count: int = 0) -> ReceiptOcrRecordOut:
    return ReceiptOcrRecordOut(
        id=record.id,
        pharmacy_id=record.pharmacy_id,
        image_path=record.image_path,
        ocr_status=record.ocr_status,
        supplier_name=record.supplier_name,
        receipt_date=record.receipt_date,
        receipt_number=record.receipt_number,
        total_amount=record.total_amount,
        intake_status=record.intake_status,
        confirmed_at=record.confirmed_at,
        duplicate_of=record.duplicate_of,
        ocr_engine=record.ocr_engine,
        processed_at=record.processed_at,
        created_at=record.created_at,
        item_count=item_count,
    )


def _item_to_out(item: ReceiptOcrItem) -> ReceiptOcrItemOut:
    return ReceiptOcrItemOut.model_validate(item)


# ─── 업로드 + OCR + 매칭 ───


async def upload_and_process(
    db: AsyncSession,
    pharmacy_id: int,
    file: UploadFile,
) -> ReceiptOcrResponse:
    """이미지 업로드 → OCR → 파싱 → 매칭 → 중복감지 → DB 저장."""

    # 1. 파일 검증
    if file.content_type not in ALLOWED_TYPES:
        from app.exceptions import ServiceError
        raise ServiceError(f"지원하지 않는 파일 형식: {file.content_type}", 422)

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        from app.exceptions import ServiceError
        raise ServiceError("파일 크기가 10MB를 초과합니다", 422)

    # 2. 이미지 저장
    ext = "jpg" if file.content_type == "image/jpeg" else "png"
    filename = f"{uuid.uuid4()}.{ext}"
    upload_path = os.path.join(_upload_dir(), str(pharmacy_id))
    os.makedirs(upload_path, exist_ok=True)
    file_path = os.path.join(upload_path, filename)
    with open(file_path, "wb") as f:
        f.write(contents)

    # 3. OCR 처리
    engine = get_ocr_engine()
    ocr_engine_name = type(engine).__name__
    try:
        raw_text = await engine.extract_text(contents)
    except Exception as e:
        logger.error(f"OCR failed: {e}")
        record = ReceiptOcrRecord(
            pharmacy_id=pharmacy_id,
            image_path=file_path,
            ocr_status="FAILED",
            ocr_engine=ocr_engine_name,
            processed_at=datetime.now(timezone.utc),
        )
        db.add(record)
        await db.flush()
        return ReceiptOcrResponse(
            record=_record_to_out(record),
            items=[],
            duplicate_warning=None,
        )

    # 4. 텍스트 파싱
    parsed = parse_receipt_text(raw_text)

    # 5. 중복 감지
    duplicate_warning, duplicate_of = await _check_duplicate(
        db, pharmacy_id, parsed.receipt_number, parsed.supplier_name,
        parsed.receipt_date, parsed.total_amount,
    )

    # 6. 레코드 저장
    receipt_date_val = None
    if parsed.receipt_date:
        try:
            receipt_date_val = date.fromisoformat(parsed.receipt_date)
        except ValueError:
            pass

    record = ReceiptOcrRecord(
        pharmacy_id=pharmacy_id,
        image_path=file_path,
        ocr_status="COMPLETED",
        raw_text=raw_text,
        supplier_name=parsed.supplier_name,
        receipt_date=receipt_date_val,
        receipt_number=parsed.receipt_number,
        total_amount=parsed.total_amount,
        intake_status="PENDING",
        duplicate_of=duplicate_of,
        ocr_engine=ocr_engine_name,
        processed_at=datetime.now(timezone.utc),
    )
    db.add(record)
    await db.flush()

    # 7. 품목별 약품 매칭 + 아이템 저장
    items_out: list[ReceiptOcrItemOut] = []
    for parsed_item in parsed.items:
        match = await match_drug(db, parsed_item.name, pharmacy_id)
        confidence_val = match.score

        item = ReceiptOcrItem(
            record_id=record.id,
            drug_id=match.drug_id,
            item_name=parsed_item.name,
            quantity=parsed_item.quantity,
            unit_price=parsed_item.unit_price,
            confidence=confidence_val,
            match_score=match.score,
            matched_drug_name=match.drug_name,
            is_confirmed=False,
            confirmed_drug_id=None,
            confirmed_quantity=None,
        )
        db.add(item)
        await db.flush()
        items_out.append(_item_to_out(item))

    return ReceiptOcrResponse(
        record=_record_to_out(record, item_count=len(items_out)),
        items=items_out,
        duplicate_warning=duplicate_warning,
    )


# ─── 중복 감지 ───


async def _check_duplicate(
    db: AsyncSession,
    pharmacy_id: int,
    receipt_number: str | None,
    supplier_name: str | None,
    receipt_date_str: str | None,
    total_amount: int | None,
) -> tuple[str | None, int | None]:
    """3단계 중복 감지. (warning 문자열, duplicate_of ID) 반환."""

    # 1단계: 영수증 번호 정확 매칭
    if receipt_number:
        result = await db.execute(
            select(ReceiptOcrRecord).where(
                ReceiptOcrRecord.pharmacy_id == pharmacy_id,
                ReceiptOcrRecord.receipt_number == receipt_number,
                ReceiptOcrRecord.intake_status != "CANCELLED",
            )
        )
        existing = result.scalars().first()
        if existing:
            return (
                f"동일 영수증번호가 이미 등록되어 있습니다 (ID: {existing.id})",
                existing.id,
            )

    # 2단계: 거래처 + 날짜 + 총액
    if supplier_name and receipt_date_str and total_amount:
        try:
            rd = date.fromisoformat(receipt_date_str)
        except ValueError:
            rd = None
        if rd:
            result = await db.execute(
                select(ReceiptOcrRecord).where(
                    ReceiptOcrRecord.pharmacy_id == pharmacy_id,
                    ReceiptOcrRecord.supplier_name == supplier_name,
                    ReceiptOcrRecord.receipt_date == rd,
                    ReceiptOcrRecord.total_amount == total_amount,
                    ReceiptOcrRecord.intake_status != "CANCELLED",
                )
            )
            existing = result.scalars().first()
            if existing:
                return (
                    f"동일 거래처+날짜+총액 영수증이 등록되어 있습니다 (ID: {existing.id})",
                    existing.id,
                )

    # 3단계: 7일 이내 유사 영수증 (경고만, duplicate_of 안 설정)
    if supplier_name and total_amount:
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        result = await db.execute(
            select(ReceiptOcrRecord).where(
                ReceiptOcrRecord.pharmacy_id == pharmacy_id,
                ReceiptOcrRecord.supplier_name == supplier_name,
                ReceiptOcrRecord.intake_status != "CANCELLED",
                ReceiptOcrRecord.created_at >= cutoff,
                ReceiptOcrRecord.total_amount.isnot(None),
            )
        )
        similar_records = result.scalars().all()
        for rec in similar_records:
            if rec.total_amount and abs(rec.total_amount - total_amount) <= total_amount * 0.1:
                return (
                    f"최근 7일 내 유사 영수증이 있습니다 (ID: {rec.id}, ±10% 총액)",
                    None,
                )

    return None, None


# ─── 목록 조회 ───


async def list_receipts(
    db: AsyncSession,
    pharmacy_id: int,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 20,
    offset: int = 0,
) -> ReceiptListResponse:
    base = select(ReceiptOcrRecord).where(ReceiptOcrRecord.pharmacy_id == pharmacy_id)
    count_q = select(func.count(ReceiptOcrRecord.id)).where(ReceiptOcrRecord.pharmacy_id == pharmacy_id)

    if status:
        base = base.where(ReceiptOcrRecord.intake_status == status)
        count_q = count_q.where(ReceiptOcrRecord.intake_status == status)
    if date_from:
        base = base.where(ReceiptOcrRecord.receipt_date >= date_from)
        count_q = count_q.where(ReceiptOcrRecord.receipt_date >= date_from)
    if date_to:
        base = base.where(ReceiptOcrRecord.receipt_date <= date_to)
        count_q = count_q.where(ReceiptOcrRecord.receipt_date <= date_to)

    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    result = await db.execute(
        base.order_by(ReceiptOcrRecord.created_at.desc()).offset(offset).limit(limit)
    )
    records = result.scalars().all()

    # 단일 쿼리로 모든 레코드의 item 수 가져오기 (N+1 → 2 쿼리)
    record_ids = [rec.id for rec in records]
    if record_ids:
        count_result = await db.execute(
            select(
                ReceiptOcrItem.record_id,
                func.count(ReceiptOcrItem.id).label("cnt"),
            )
            .where(ReceiptOcrItem.record_id.in_(record_ids))
            .group_by(ReceiptOcrItem.record_id)
        )
        count_map = {row.record_id: row.cnt for row in count_result.all()}
    else:
        count_map = {}

    items_out = [
        _record_to_out(rec, count_map.get(rec.id, 0))
        for rec in records
    ]

    return ReceiptListResponse(items=items_out, total=total)


# ─── 상세 조회 ───


async def get_receipt_detail(
    db: AsyncSession,
    pharmacy_id: int,
    record_id: int,
) -> ReceiptOcrDetailResponse:
    result = await db.execute(
        select(ReceiptOcrRecord).where(
            ReceiptOcrRecord.id == record_id,
            ReceiptOcrRecord.pharmacy_id == pharmacy_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        from app.exceptions import ServiceError
        raise ServiceError("영수증을 찾을 수 없습니다", 404)

    items_result = await db.execute(
        select(ReceiptOcrItem).where(ReceiptOcrItem.record_id == record_id)
    )
    items = items_result.scalars().all()
    item_count = len(items)

    return ReceiptOcrDetailResponse(
        record=_record_to_out(record, item_count),
        items=[_item_to_out(i) for i in items],
        raw_text=record.raw_text,
    )


# ─── 항목 수정 ───


async def update_item(
    db: AsyncSession,
    pharmacy_id: int,
    record_id: int,
    item_id: int,
    drug_id: int | None,
    quantity: int | None,
) -> ReceiptOcrItemOut:
    # 레코드 소유권 확인
    rec_result = await db.execute(
        select(ReceiptOcrRecord).where(
            ReceiptOcrRecord.id == record_id,
            ReceiptOcrRecord.pharmacy_id == pharmacy_id,
        )
    )
    if not rec_result.scalar_one_or_none():
        from app.exceptions import ServiceError
        raise ServiceError("영수증을 찾을 수 없습니다", 404)

    result = await db.execute(
        select(ReceiptOcrItem).where(
            ReceiptOcrItem.id == item_id,
            ReceiptOcrItem.record_id == record_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        from app.exceptions import ServiceError
        raise ServiceError("항목을 찾을 수 없습니다", 404)

    if drug_id is not None:
        # drug 존재 확인
        drug_result = await db.execute(select(Drug).where(Drug.id == drug_id))
        drug = drug_result.scalar_one_or_none()
        if not drug:
            from app.exceptions import ServiceError
            raise ServiceError("약품을 찾을 수 없습니다", 422)
        item.confirmed_drug_id = drug_id
        item.matched_drug_name = drug.name

    if quantity is not None:
        item.confirmed_quantity = quantity

    item.is_confirmed = True

    return _item_to_out(item)


# ─── 입고 확정 (P31: OTC/drug_stock 분기) ───


async def confirm_intake(
    db: AsyncSession,
    pharmacy_id: int,
    record_id: int,
    user: User,
) -> ConfirmResponse:
    """입고 확정 → 재고 반영.

    P31 분기 로직:
    - 약품의 category가 'OTC'이고 otc_inventory에 해당 약품이 존재하면
      → otc_inventory.current_quantity 증가
    - 그 외 (PRESCRIPTION, NARCOTIC, 또는 otc_inventory에 없는 OTC)
      → drug_stock.current_quantity 증가 (없으면 신규 INSERT)
    """
    result = await db.execute(
        select(ReceiptOcrRecord).where(
            ReceiptOcrRecord.id == record_id,
            ReceiptOcrRecord.pharmacy_id == pharmacy_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        from app.exceptions import ServiceError
        raise ServiceError("영수증을 찾을 수 없습니다", 404)

    if record.intake_status != "PENDING":
        from app.exceptions import ServiceError
        raise ServiceError(f"입고 확정 불가 (현재 상태: {record.intake_status})", 422)

    # 모든 아이템 확인 여부 체크
    items_result = await db.execute(
        select(ReceiptOcrItem).where(ReceiptOcrItem.record_id == record_id)
    )
    items = items_result.scalars().all()

    unconfirmed = [i for i in items if not i.is_confirmed]
    if unconfirmed:
        from app.exceptions import ServiceError
        raise ServiceError(
            f"미확인 항목이 {len(unconfirmed)}개 있습니다. 모든 항목을 확인 후 입고 확정하세요.", 422,
        )

    confirmed_count = 0
    updated_stocks: list[dict] = []

    for item in items:
        # 최종 drug_id와 수량 결정
        final_drug_id = item.confirmed_drug_id or item.drug_id
        final_quantity = item.confirmed_quantity if item.confirmed_quantity is not None else item.quantity

        if not final_drug_id or not final_quantity:
            continue

        # 약품 정보 조회 (category 확인)
        drug_result = await db.execute(select(Drug).where(Drug.id == final_drug_id))
        drug = drug_result.scalar_one_or_none()
        if not drug:
            continue

        # P31: OTC 분기 로직
        if drug.category == "OTC":
            # OTC 약품이면 otc_inventory에 해당 약품이 있는지 확인
            otc_result = await db.execute(
                select(OtcInventory).where(
                    and_(
                        OtcInventory.pharmacy_id == pharmacy_id,
                        OtcInventory.drug_id == final_drug_id,
                    )
                )
            )
            otc_item = otc_result.scalar_one_or_none()

            if otc_item:
                # OTC이고 otc_inventory에 존재 → otc_inventory 수량 증가
                otc_item.current_quantity += final_quantity
                otc_item.updated_at = datetime.now(timezone.utc)
                otc_item.version += 1
                updated_stocks.append({
                    "drug_id": final_drug_id,
                    "drug_name": drug.name,
                    "table": "otc_inventory",
                    "added_quantity": final_quantity,
                    "new_quantity": otc_item.current_quantity,
                })
                confirmed_count += 1
                continue

        # OTC가 아니거나, OTC이지만 otc_inventory에 없는 경우 → drug_stock에 반영
        stock_result = await db.execute(
            select(DrugStock).where(
                and_(
                    DrugStock.pharmacy_id == pharmacy_id,
                    DrugStock.drug_id == final_drug_id,
                )
            )
        )
        stock = stock_result.scalar_one_or_none()

        if stock:
            stock.current_quantity = float(stock.current_quantity) + final_quantity
            stock.updated_at = datetime.now(timezone.utc)
        else:
            # drug_stock 신규 INSERT
            stock = DrugStock(
                pharmacy_id=pharmacy_id,
                drug_id=final_drug_id,
                current_quantity=final_quantity,
                is_narcotic=(drug.category == "NARCOTIC"),
                quantity_source="OCR_INTAKE",
                synced_at=datetime.now(timezone.utc),
            )
            db.add(stock)
            await db.flush()

        updated_stocks.append({
            "drug_id": final_drug_id,
            "drug_name": drug.name,
            "table": "drug_stock",
            "added_quantity": final_quantity,
            "new_quantity": float(stock.current_quantity),
        })
        confirmed_count += 1

    # 레코드 상태 변경
    record.intake_status = "CONFIRMED"
    record.confirmed_at = datetime.now(timezone.utc)
    record.confirmed_by = user.id

    return ConfirmResponse(
        confirmed_count=confirmed_count,
        updated_stocks=updated_stocks,
    )


# ─── 삭제 (취소 처리) ───


async def cancel_receipt(
    db: AsyncSession,
    pharmacy_id: int,
    record_id: int,
) -> None:
    result = await db.execute(
        select(ReceiptOcrRecord).where(
            ReceiptOcrRecord.id == record_id,
            ReceiptOcrRecord.pharmacy_id == pharmacy_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        from app.exceptions import ServiceError
        raise ServiceError("영수증을 찾을 수 없습니다", 404)

    record.intake_status = "CANCELLED"
