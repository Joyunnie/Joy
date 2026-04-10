"""Import cassette mapping from TSV into prescription_inventory table.

Usage:
    docker exec -it pharma-automation-cloud-1 python -m scripts.import_cassette_mapping --pharmacy-id 7
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import os
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models.tables import Drug, PrescriptionInventory

DATABASE_URL = os.environ.get(
    "PHARMA_DATABASE_URL",
    "postgresql+asyncpg://pharma_user:postgres@db:5432/pharma",
)

TSV_PATH = Path(__file__).resolve().parent.parent / "data" / "cassette_mapping.tsv"


async def main(pharmacy_id: int) -> None:
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # Prefetch all drugs by insurance_code
        result = await db.execute(
            select(Drug).where(Drug.insurance_code.isnot(None))
        )
        drug_by_insurance = {d.insurance_code: d for d in result.scalars().all()}

        # Prefetch existing prescription_inventory for this pharmacy
        existing_result = await db.execute(
            select(PrescriptionInventory).where(
                PrescriptionInventory.pharmacy_id == pharmacy_id,
            )
        )
        existing_map = {
            inv.cassette_number: inv for inv in existing_result.scalars().all()
        }

        rows = _parse_tsv(TSV_PATH)
        total = 0
        matched = 0
        unmatched = 0

        for row in rows:
            insurance_code = row["insurance_code"]
            cassette_number = row["cassette_number"]

            drug = drug_by_insurance.get(insurance_code)
            drug_id = drug.id if drug else None

            inv = existing_map.get(cassette_number)

            if inv:
                inv.drug_id = drug_id
                inv.drug_insurance_code = insurance_code
                inv.drug_name = row["drug_name"]
                inv.drug_type = row["drug_type"]
                inv.is_active = row["is_active"]
                inv.dispensing_mode = row["dispensing_mode"]
            else:
                inv = PrescriptionInventory(
                    pharmacy_id=pharmacy_id,
                    drug_id=drug_id,
                    drug_insurance_code=insurance_code,
                    drug_name=row["drug_name"],
                    cassette_number=cassette_number,
                    drug_type=row["drug_type"],
                    is_active=row["is_active"],
                    dispensing_mode=row["dispensing_mode"],
                )
                db.add(inv)

            total += 1
            if drug_id:
                matched += 1
            else:
                unmatched += 1

        await db.commit()

    await engine.dispose()

    print(f"=== Cassette Mapping Import (pharmacy_id={pharmacy_id}) ===")
    print(f"Total imported: {total}")
    print(f"Matched to drug_id: {matched}")
    print(f"Unmatched (drug_id=NULL): {unmatched}")


def _parse_tsv(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            rows.append({
                "insurance_code": row["약품코드"].strip(),
                "drug_name": row["일반약품명"].strip(),
                "cassette_number": int(row["캐니스터번호"].strip()),
                "drug_type": row["약품종류"].strip(),
                "is_active": row["캐니스터 사용"].strip() == "○",
                "dispensing_mode": row["순차/동시"].strip(),
            })
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import cassette mapping TSV")
    parser.add_argument("--pharmacy-id", type=int, required=True, help="Target pharmacy ID")
    args = parser.parse_args()
    asyncio.run(main(args.pharmacy_id))
