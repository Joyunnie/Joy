"""Shared low-stock alert creation utility.

Consolidates the threshold check → 24h dedup → AlertLog creation pattern
used by narcotics, OTC, and sync services.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import AlertLog, DrugThreshold


async def check_and_create_low_stock_alert(
    db: AsyncSession,
    pharmacy_id: int,
    drug_id: int,
    current_quantity: float | int,
    drug_name: str | None,
    alert_type: str,
    ref_table: str,
) -> None:
    """Check threshold and create alert if below minimum (with 24h dedup).

    Args:
        alert_type: "LOW_STOCK" for OTC/drug_stock, "NARCOTICS_LOW" for narcotics.
        ref_table: Table name for alert dedup (e.g. "otc_inventory", "narcotics_inventory").
    """
    threshold_result = await db.execute(
        select(DrugThreshold).where(
            and_(
                DrugThreshold.pharmacy_id == pharmacy_id,
                DrugThreshold.drug_id == drug_id,
                DrugThreshold.is_active == True,  # noqa: E712
            )
        )
    )
    threshold = threshold_result.scalar_one_or_none()
    if not threshold or current_quantity >= threshold.min_quantity:
        return

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    dup_result = await db.execute(
        select(AlertLog.id).where(
            and_(
                AlertLog.pharmacy_id == pharmacy_id,
                AlertLog.alert_type == alert_type,
                AlertLog.ref_table == ref_table,
                AlertLog.ref_id == drug_id,
                AlertLog.sent_at >= cutoff,
                AlertLog.read_at.is_(None),
            )
        )
    )
    if dup_result.first():
        return

    label = "마약류 재고 부족" if alert_type == "NARCOTICS_LOW" else "재고 부족"
    db.add(AlertLog(
        pharmacy_id=pharmacy_id,
        alert_type=alert_type,
        ref_table=ref_table,
        ref_id=drug_id,
        message=f"{drug_name} {label} (현재: {current_quantity}, 최소: {threshold.min_quantity})",
        sent_via="IN_APP",
    ))
