from datetime import datetime, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import AlertLog
from app.schemas.api import AlertListResponse, AlertOut, AlertReadResponse


async def get_alerts(
    db: AsyncSession,
    pharmacy_id: int,
    alert_type: str | None = None,
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> AlertListResponse:
    conditions = [AlertLog.pharmacy_id == pharmacy_id]
    if alert_type:
        conditions.append(AlertLog.alert_type == alert_type)
    if unread_only:
        conditions.append(AlertLog.read_at.is_(None))

    # Total count
    count_result = await db.execute(
        select(func.count(AlertLog.id)).where(and_(*conditions))
    )
    total = count_result.scalar() or 0

    # Fetch page
    result = await db.execute(
        select(AlertLog)
        .where(and_(*conditions))
        .order_by(AlertLog.sent_at.desc())
        .offset(offset)
        .limit(limit)
    )
    alerts = result.scalars().all()

    return AlertListResponse(
        alerts=[
            AlertOut(
                id=a.id,
                alert_type=a.alert_type,
                message=a.message,
                sent_at=a.sent_at,
                read_at=a.read_at,
            )
            for a in alerts
        ],
        total=total,
    )


async def mark_alert_read(db: AsyncSession, alert_id: int, pharmacy_id: int) -> AlertReadResponse:
    from app.exceptions import ServiceError

    result = await db.execute(select(AlertLog).where(AlertLog.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise ServiceError("Alert not found", 404)

    if alert.pharmacy_id != pharmacy_id:
        raise ServiceError("Access denied", 403)

    now = datetime.now(timezone.utc)
    alert.read_at = now

    return AlertReadResponse(id=alert.id, read_at=now)
