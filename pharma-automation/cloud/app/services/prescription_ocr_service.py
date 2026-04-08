"""처방전 OCR 서비스: 업로드 → OCR → 파싱 → 매칭 → 중복감지 → 확인."""
import logging
import os
import uuid
from datetime import date, datetime, timezone

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions import ServiceError
from app.models.tables import (
    Drug,
    PrescriptionOcrDrug,
    PrescriptionOcrRecord,
    User,
)
from app.schemas.prescription_ocr import (
    PrescriptionConfirmResponse,
    PrescriptionListResponse,
    PrescriptionOcrDetailResponse,
    PrescriptionOcrDrugOut,
    PrescriptionOcrRecordOut,
    PrescriptionOcrResponse,
)
from app.services.drug_matcher import match_drug
from app.services.ocr_engine import get_ocr_engine
from app.services.prescription_parser import parse_prescription_text

logger = logging.getLogger(__name__)

ALLOWED_TYPES = {"image/jpeg", "image/png"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def _upload_dir() -> str:
    return settings.upload_dir


def _record_to_out(record: PrescriptionOcrRecord, drug_count: int = 0) -> PrescriptionOcrRecordOut:
    return PrescriptionOcrRecordOut(
        id=record.id,
        pharmacy_id=record.pharmacy_id,
        image_path=record.image_path,
        ocr_status=record.ocr_status,
        patient_name=record.patient_name,
        patient_dob=record.patient_dob,
        insurance_type=record.insurance_type,
        prescriber_name=record.prescriber_name,
        prescriber_clinic=record.prescriber_clinic,
        prescription_date=record.prescription_date,
        prescription_number=record.prescription_number,
        ocr_engine=record.ocr_engine,
        confirmed_at=record.confirmed_at,
        duplicate_of=record.duplicate_of,
        processed_at=record.processed_at,
        created_at=record.created_at,
        drug_count=drug_count,
    )


def _drug_to_out(drug: PrescriptionOcrDrug) -> PrescriptionOcrDrugOut:
    return PrescriptionOcrDrugOut.model_validate(drug)


# ─── 업로드 + OCR + 매칭 ───


async def upload_and_process(
    db: AsyncSession,
    pharmacy_id: int,
    file: UploadFile,
) -> PrescriptionOcrResponse:
    """이미지 업로드 → OCR → 파싱 → 매칭 → 중복감지 → DB 저장."""


    # 1. 파일 검증
    if file.content_type not in ALLOWED_TYPES:
        raise ServiceError(f"지원하지 않는 파일 형식: {file.content_type}", 422)

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
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
        record = PrescriptionOcrRecord(
            pharmacy_id=pharmacy_id,
            image_path=file_path,
            ocr_status="FAILED",
            ocr_engine=ocr_engine_name,
            processed_at=datetime.now(timezone.utc),
        )
        db.add(record)
        await db.flush()
        return PrescriptionOcrResponse(
            record=_record_to_out(record),
            drugs=[],
            duplicate_warning=None,
        )

    # 4. 텍스트 파싱
    parsed = parse_prescription_text(raw_text)

    # 5. 중복 감지 (교부번호)
    duplicate_warning, duplicate_of = await _check_duplicate(
        db, pharmacy_id, parsed.prescription_number,
    )

    # 6. 레코드 저장
    rx_date_val = None
    if parsed.prescription_date:
        try:
            rx_date_val = date.fromisoformat(parsed.prescription_date)
        except ValueError:
            pass

    record = PrescriptionOcrRecord(
        pharmacy_id=pharmacy_id,
        image_path=file_path,
        ocr_status="COMPLETED",
        raw_text=raw_text,
        patient_name=parsed.patient_name,
        patient_dob=parsed.patient_dob,
        insurance_type=parsed.insurance_type,
        prescriber_name=parsed.prescriber_name,
        prescriber_clinic=parsed.prescriber_clinic,
        prescription_date=rx_date_val,
        prescription_number=parsed.prescription_number,
        duplicate_of=duplicate_of,
        ocr_engine=ocr_engine_name,
        processed_at=datetime.now(timezone.utc),
    )
    db.add(record)
    await db.flush()

    # 7. 약품별 매칭 + 저장
    drugs_out: list[PrescriptionOcrDrugOut] = []
    for parsed_drug in parsed.drugs:
        match = await match_drug(db, parsed_drug.name, pharmacy_id)

        # 마약류 여부 확인
        is_narcotic = False
        if match.drug_id:
            drug_result = await db.execute(select(Drug).where(Drug.id == match.drug_id))
            drug_obj = drug_result.scalar_one_or_none()
            if drug_obj and drug_obj.category == "NARCOTIC":
                is_narcotic = True

        drug_item = PrescriptionOcrDrug(
            record_id=record.id,
            drug_id=match.drug_id,
            drug_name_raw=parsed_drug.name,
            dosage=parsed_drug.dosage,
            frequency=parsed_drug.frequency,
            days=parsed_drug.days,
            total_quantity=parsed_drug.total_quantity,
            confidence=match.score,
            match_score=match.score,
            matched_drug_name=match.drug_name,
            is_narcotic=is_narcotic,
            is_confirmed=False,
        )
        db.add(drug_item)
        await db.flush()
        drugs_out.append(_drug_to_out(drug_item))

    return PrescriptionOcrResponse(
        record=_record_to_out(record, drug_count=len(drugs_out)),
        drugs=drugs_out,
        duplicate_warning=duplicate_warning,
    )


# ─── 중복 감지 ───


async def _check_duplicate(
    db: AsyncSession,
    pharmacy_id: int,
    prescription_number: str | None,
) -> tuple[str | None, int | None]:
    """교부번호로 중복 감지. (warning, duplicate_of ID) 반환."""
    if not prescription_number:
        return None, None

    result = await db.execute(
        select(PrescriptionOcrRecord).where(
            PrescriptionOcrRecord.pharmacy_id == pharmacy_id,
            PrescriptionOcrRecord.prescription_number == prescription_number,
            PrescriptionOcrRecord.ocr_status != "CANCELLED",
        )
    )
    existing = result.scalars().first()
    if existing:
        return (
            f"동일 교부번호가 이미 등록되어 있습니다 (ID: {existing.id})",
            existing.id,
        )

    return None, None


# ─── 목록 조회 ───


async def list_prescriptions(
    db: AsyncSession,
    pharmacy_id: int,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 20,
    offset: int = 0,
) -> PrescriptionListResponse:
    base = select(PrescriptionOcrRecord).where(PrescriptionOcrRecord.pharmacy_id == pharmacy_id)
    count_q = select(func.count(PrescriptionOcrRecord.id)).where(
        PrescriptionOcrRecord.pharmacy_id == pharmacy_id
    )

    if status:
        base = base.where(PrescriptionOcrRecord.ocr_status == status)
        count_q = count_q.where(PrescriptionOcrRecord.ocr_status == status)
    if date_from:
        base = base.where(PrescriptionOcrRecord.prescription_date >= date_from)
        count_q = count_q.where(PrescriptionOcrRecord.prescription_date >= date_from)
    if date_to:
        base = base.where(PrescriptionOcrRecord.prescription_date <= date_to)
        count_q = count_q.where(PrescriptionOcrRecord.prescription_date <= date_to)

    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    result = await db.execute(
        base.order_by(PrescriptionOcrRecord.created_at.desc()).offset(offset).limit(limit)
    )
    records = result.scalars().all()

    # 단일 쿼리로 모든 레코드의 drug 수 가져오기 (N+1 → 2 쿼리)
    record_ids = [rec.id for rec in records]
    if record_ids:
        count_result = await db.execute(
            select(
                PrescriptionOcrDrug.record_id,
                func.count(PrescriptionOcrDrug.id).label("cnt"),
            )
            .where(PrescriptionOcrDrug.record_id.in_(record_ids))
            .group_by(PrescriptionOcrDrug.record_id)
        )
        count_map = {row.record_id: row.cnt for row in count_result.all()}
    else:
        count_map = {}

    items_out = [
        _record_to_out(rec, count_map.get(rec.id, 0))
        for rec in records
    ]

    return PrescriptionListResponse(items=items_out, total=total)


# ─── 상세 조회 ───


async def get_prescription_detail(
    db: AsyncSession,
    pharmacy_id: int,
    record_id: int,
) -> PrescriptionOcrDetailResponse:


    result = await db.execute(
        select(PrescriptionOcrRecord).where(
            PrescriptionOcrRecord.id == record_id,
            PrescriptionOcrRecord.pharmacy_id == pharmacy_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise ServiceError("처방전을 찾을 수 없습니다", 404)

    drugs_result = await db.execute(
        select(PrescriptionOcrDrug).where(PrescriptionOcrDrug.record_id == record_id)
    )
    drugs = drugs_result.scalars().all()

    return PrescriptionOcrDetailResponse(
        record=_record_to_out(record, len(drugs)),
        drugs=[_drug_to_out(d) for d in drugs],
        raw_text=record.raw_text,
    )


# ─── 약품 항목 수정 ───


async def update_drug(
    db: AsyncSession,
    pharmacy_id: int,
    record_id: int,
    drug_item_id: int,
    drug_id: int | None,
    dosage: str | None,
    frequency: str | None,
    days: int | None,
) -> PrescriptionOcrDrugOut:


    # 레코드 소유권 확인
    rec_result = await db.execute(
        select(PrescriptionOcrRecord).where(
            PrescriptionOcrRecord.id == record_id,
            PrescriptionOcrRecord.pharmacy_id == pharmacy_id,
        )
    )
    if not rec_result.scalar_one_or_none():
        raise ServiceError("처방전을 찾을 수 없습니다", 404)

    result = await db.execute(
        select(PrescriptionOcrDrug).where(
            PrescriptionOcrDrug.id == drug_item_id,
            PrescriptionOcrDrug.record_id == record_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise ServiceError("약품 항목을 찾을 수 없습니다", 404)

    if drug_id is not None:
        drug_result = await db.execute(select(Drug).where(Drug.id == drug_id))
        drug = drug_result.scalar_one_or_none()
        if not drug:
            raise ServiceError("약품을 찾을 수 없습니다", 422)
        item.confirmed_drug_id = drug_id
        item.matched_drug_name = drug.name
        item.is_narcotic = drug.category == "NARCOTIC"

    if dosage is not None:
        item.confirmed_dosage = dosage
    if frequency is not None:
        item.confirmed_frequency = frequency
    if days is not None:
        item.confirmed_days = days

    item.is_confirmed = True

    return _drug_to_out(item)


# ─── 확인 완료 ───


async def confirm_prescription(
    db: AsyncSession,
    pharmacy_id: int,
    record_id: int,
    user: User,
) -> PrescriptionConfirmResponse:
    """확인 완료 → 상태만 CONFIRMED 변경 (재고 반영 없음)."""


    result = await db.execute(
        select(PrescriptionOcrRecord).where(
            PrescriptionOcrRecord.id == record_id,
            PrescriptionOcrRecord.pharmacy_id == pharmacy_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise ServiceError("처방전을 찾을 수 없습니다", 404)

    if record.ocr_status not in ("COMPLETED",):
        raise ServiceError(
            f"확인 불가 (현재 상태: {record.ocr_status})", 422,
        )

    # 모든 약품 확인 여부 체크
    drugs_result = await db.execute(
        select(PrescriptionOcrDrug).where(PrescriptionOcrDrug.record_id == record_id)
    )
    drugs = drugs_result.scalars().all()

    unconfirmed = [d for d in drugs if not d.is_confirmed]
    if unconfirmed:
        raise ServiceError(
            f"미확인 항목이 {len(unconfirmed)}개 있습니다. 모든 항목을 확인 후 처리하세요.", 422,
        )

    record.ocr_status = "CONFIRMED"
    record.confirmed_at = datetime.now(timezone.utc)
    record.confirmed_by = user.id

    return PrescriptionConfirmResponse(confirmed_count=len(drugs))


# ─── 취소 ───


async def cancel_prescription(
    db: AsyncSession,
    pharmacy_id: int,
    record_id: int,
) -> None:


    result = await db.execute(
        select(PrescriptionOcrRecord).where(
            PrescriptionOcrRecord.id == record_id,
            PrescriptionOcrRecord.pharmacy_id == pharmacy_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise ServiceError("처방전을 찾을 수 없습니다", 404)

    record.ocr_status = "CANCELLED"
