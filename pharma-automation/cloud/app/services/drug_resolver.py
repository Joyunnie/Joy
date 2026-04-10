"""DrugResolver: single-location dual-code drug lookup.

Consolidates the insurance_code-first, standard_code-fallback resolution
pattern used by sync_drug_stock and sync_visits.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import Drug


class DrugResolver:
    """Resolves drug codes (insurance or standard) to Drug ORM objects.

    Built once per sync request with bulk-prefetched maps.
    """

    def __init__(
        self,
        insurance_map: dict[str, Drug],
        standard_map: dict[str, Drug],
    ):
        self._insurance_map = insurance_map
        self._standard_map = standard_map

    @classmethod
    async def build(
        cls,
        db: AsyncSession,
        insurance_codes: set[str],
        standard_codes: set[str],
    ) -> DrugResolver:
        """Bulk-fetch drugs by both code systems in at most 2 queries."""
        insurance_map: dict[str, Drug] = {}
        if insurance_codes:
            result = await db.execute(
                select(Drug).where(Drug.insurance_code.in_(insurance_codes))
            )
            insurance_map = {
                d.insurance_code: d
                for d in result.scalars().all()
                if d.insurance_code
            }

        standard_map: dict[str, Drug] = {}
        if standard_codes:
            result = await db.execute(
                select(Drug).where(Drug.standard_code.in_(standard_codes))
            )
            standard_map = {d.standard_code: d for d in result.scalars().all()}

        return cls(insurance_map, standard_map)

    def resolve(
        self,
        insurance_code: str | None = None,
        standard_code: str | None = None,
    ) -> Drug | None:
        """Try insurance_code first, fall back to standard_code."""
        if insurance_code:
            found = self._insurance_map.get(insurance_code)
            if found:
                return found
        if standard_code:
            found = self._standard_map.get(standard_code)
            if found:
                return found
        return None

    @property
    def all_drug_ids(self) -> set[int]:
        """All resolved drug IDs (union of both maps). Useful for prefetching thresholds/alerts."""
        return {d.id for d in self._insurance_map.values()} | {
            d.id for d in self._standard_map.values()
        }
