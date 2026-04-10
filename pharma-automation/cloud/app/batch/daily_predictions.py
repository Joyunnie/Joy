"""Daily prediction batch job.

Usage:
    python -m app.batch.daily_predictions [--dry-run] [--pharmacy-id ID] [--lookback-days N]
"""

import argparse
import asyncio
import logging
import sys

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session, engine
from app.services.prediction_service import run_daily_predictions
from app.services.auth_service import cleanup_expired_tokens

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main(args: argparse.Namespace) -> None:
    async with async_session() as db:
        stats = await run_daily_predictions(
            db,
            pharmacy_id=args.pharmacy_id,
            lookback_days=args.lookback_days,
            dry_run=args.dry_run,
        )
        if not args.dry_run:
            expired = await cleanup_expired_tokens(db)
            stats["expired_tokens_cleaned"] = expired
            await db.commit()

    await engine.dispose()

    prefix = "[DRY-RUN] " if args.dry_run else ""
    logger.info(
        "%sBatch complete — pharmacies: %d, patients: %d, predictions: %d, alerts: %d",
        prefix,
        stats["pharmacies"],
        stats["patients"],
        stats["predictions_upserted"],
        stats["alerts_created"],
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Daily visit prediction batch job")
    parser.add_argument("--dry-run", action="store_true", help="Log only, no DB changes")
    parser.add_argument("--pharmacy-id", type=int, default=None, help="Run for specific pharmacy only")
    parser.add_argument("--lookback-days", type=int, default=180, help="Active patient lookback (default: 180)")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(args))
