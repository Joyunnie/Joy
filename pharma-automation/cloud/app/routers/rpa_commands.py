from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, verify_api_key
from app.models.tables import Pharmacy, User
from app.schemas.rpa_command import (
    RpaCommandCreateRequest,
    RpaCommandListResponse,
    RpaCommandOut,
    RpaCommandStatusUpdate,
    RpaPendingResponse,
)
from app.services import rpa_command_service

router = APIRouter(prefix="/api/v1/rpa-commands", tags=["rpa"])


def _to_out(cmd) -> RpaCommandOut:
    return RpaCommandOut(
        id=cmd.id,
        pharmacy_id=cmd.pharmacy_id,
        command_type=cmd.command_type,
        payload=cmd.payload,
        status=cmd.status,
        created_at=cmd.created_at,
        sent_at=cmd.sent_at,
        started_at=cmd.started_at,
        completed_at=cmd.completed_at,
        error_message=cmd.error_message,
        retry_count=cmd.retry_count or 0,
    )


@router.post("", response_model=RpaCommandOut, status_code=201)
async def create_command(
    body: RpaCommandCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cmd = await rpa_command_service.create_command(
        db, user.pharmacy_id, body.command_type, body.payload,
    )
    return _to_out(cmd)


@router.get("/pending", response_model=RpaPendingResponse)
async def get_pending_commands(
    pharmacy: Pharmacy = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Agent1이 폴링하는 엔드포인트. API-Key 인증."""
    commands = await rpa_command_service.get_pending_commands(db, pharmacy.id)
    return RpaPendingResponse(commands=[_to_out(c) for c in commands])


@router.patch("/{command_id}/status", response_model=RpaCommandOut)
async def update_command_status(
    command_id: int,
    body: RpaCommandStatusUpdate,
    pharmacy: Pharmacy = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Agent1이 상태를 업데이트하는 엔드포인트. API-Key 인증."""
    cmd = await rpa_command_service.update_command_status(
        db, command_id, pharmacy.id, body.status, body.error_message,
    )
    return _to_out(cmd)


@router.get("", response_model=RpaCommandListResponse)
async def list_commands(
    status: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    commands, total = await rpa_command_service.list_commands(
        db, user.pharmacy_id, status_filter=status, limit=limit, offset=offset,
    )
    return RpaCommandListResponse(items=[_to_out(c) for c in commands], total=total)
