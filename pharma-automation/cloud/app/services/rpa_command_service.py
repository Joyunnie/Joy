from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import RpaCommand

# Valid status transitions
_VALID_TRANSITIONS = {
    "PENDING": {"SENT", "EXECUTING", "SKIPPED"},
    "SENT": {"EXECUTING", "FAILED", "SKIPPED"},
    "EXECUTING": {"SUCCESS", "FAILED"},
}


async def create_command(
    db: AsyncSession,
    pharmacy_id: int,
    command_type: str,
    payload: dict,
) -> RpaCommand:
    if command_type not in ("NARCOTICS_INPUT", "PRESCRIPTION_INPUT"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid command_type")

    cmd = RpaCommand(
        pharmacy_id=pharmacy_id,
        command_type=command_type,
        payload=payload,
        status="PENDING",
    )
    db.add(cmd)
    await db.flush()
    await db.refresh(cmd)
    return cmd


async def get_pending_commands(
    db: AsyncSession,
    pharmacy_id: int,
) -> list[RpaCommand]:
    result = await db.execute(
        select(RpaCommand)
        .where(and_(RpaCommand.pharmacy_id == pharmacy_id, RpaCommand.status == "PENDING"))
        .order_by(RpaCommand.created_at.asc())
    )
    commands = list(result.scalars().all())
    now = datetime.now(timezone.utc)
    for cmd in commands:
        cmd.status = "SENT"
        cmd.sent_at = now
    await db.flush()
    return commands


async def update_command_status(
    db: AsyncSession,
    command_id: int,
    pharmacy_id: int,
    new_status: str,
    error_message: str | None = None,
) -> RpaCommand:
    result = await db.execute(
        select(RpaCommand).where(
            and_(RpaCommand.id == command_id, RpaCommand.pharmacy_id == pharmacy_id)
        )
    )
    cmd = result.scalar_one_or_none()
    if not cmd:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Command not found")

    allowed = _VALID_TRANSITIONS.get(cmd.status, set())
    if new_status not in allowed:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Cannot transition from {cmd.status} to {new_status}",
        )

    now = datetime.now(timezone.utc)
    cmd.status = new_status
    if new_status == "EXECUTING":
        cmd.started_at = now
    elif new_status in ("SUCCESS", "FAILED", "SKIPPED"):
        cmd.completed_at = now
    if error_message:
        cmd.error_message = error_message
    if new_status == "FAILED":
        cmd.retry_count = (cmd.retry_count or 0) + 1

    await db.flush()
    await db.refresh(cmd)
    return cmd


async def list_commands(
    db: AsyncSession,
    pharmacy_id: int,
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[RpaCommand], int]:
    conditions = [RpaCommand.pharmacy_id == pharmacy_id]
    if status_filter:
        conditions.append(RpaCommand.status == status_filter)

    count_result = await db.execute(
        select(func.count(RpaCommand.id)).where(and_(*conditions))
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(RpaCommand)
        .where(and_(*conditions))
        .order_by(RpaCommand.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all()), total
