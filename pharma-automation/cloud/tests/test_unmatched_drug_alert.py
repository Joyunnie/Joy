"""Tests for DRUG_CODE_UNMATCHED alerts in sync_drugs."""
import time

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.models.tables import AlertLog, Drug
from tests.conftest import seed_session_factory

pytestmark = pytest.mark.asyncio

SUFFIX = str(int(time.time()))[-6:]


@pytest_asyncio.fixture(autouse=True)
async def cleanup_alert_test_data(seed_data):
    """Clean drugs and alerts created by these tests."""
    yield
    async with seed_session_factory() as db:
        # Delete alerts for test drugs
        await db.execute(
            AlertLog.__table__.delete().where(
                AlertLog.alert_type == "DRUG_CODE_UNMATCHED",
                AlertLog.pharmacy_id == seed_data["pharmacy_id"],
            )
        )
        # Delete test drugs
        await db.execute(
            Drug.__table__.delete().where(Drug.standard_code.like(f"UA_{SUFFIX}_%"))
        )
        await db.commit()


class TestUnmatchedDrugAlert:
    async def test_drug_without_insurance_code_creates_alert(
        self, client: AsyncClient, seed_data: dict
    ):
        """Drug synced with insurance_code=None → DRUG_CODE_UNMATCHED alert."""
        code = f"UA_{SUFFIX}_001"
        resp = await client.post(
            "/api/v1/sync/drugs",
            headers={"X-API-Key": seed_data["api_key"]},
            json={"drugs": [
                {"standard_code": code, "name": "매칭실패약품", "category": "PRESCRIPTION"}
                # insurance_code omitted → None
            ]},
        )
        assert resp.status_code == 200

        async with seed_session_factory() as db:
            result = await db.execute(
                select(AlertLog).where(
                    AlertLog.pharmacy_id == seed_data["pharmacy_id"],
                    AlertLog.alert_type == "DRUG_CODE_UNMATCHED",
                    AlertLog.ref_table == "drugs",
                )
            )
            alerts = result.scalars().all()
            matching = [a for a in alerts if "매칭실패약품" in a.message]
            assert len(matching) == 1
            assert "PAM-Pro에서 확인 필요" in matching[0].message

    async def test_drug_with_insurance_code_no_alert(
        self, client: AsyncClient, seed_data: dict
    ):
        """Drug synced with insurance_code populated → no alert."""
        code = f"UA_{SUFFIX}_002"
        resp = await client.post(
            "/api/v1/sync/drugs",
            headers={"X-API-Key": seed_data["api_key"]},
            json={"drugs": [
                {
                    "standard_code": code,
                    "name": "정상약품",
                    "category": "PRESCRIPTION",
                    "insurance_code": "643507086",
                }
            ]},
        )
        assert resp.status_code == 200

        async with seed_session_factory() as db:
            drug_result = await db.execute(
                select(Drug).where(Drug.standard_code == code)
            )
            drug = drug_result.scalar_one()
            alert_result = await db.execute(
                select(AlertLog).where(
                    AlertLog.alert_type == "DRUG_CODE_UNMATCHED",
                    AlertLog.ref_id == drug.id,
                )
            )
            assert alert_result.scalar_one_or_none() is None

    async def test_duplicate_alert_not_created(
        self, client: AsyncClient, seed_data: dict
    ):
        """Second sync of same unmatched drug → no duplicate alert."""
        code = f"UA_{SUFFIX}_003"
        headers = {"X-API-Key": seed_data["api_key"]}
        payload = {"drugs": [
            {"standard_code": code, "name": "중복테스트약품", "category": "PRESCRIPTION"}
        ]}

        # First sync → creates alert
        await client.post("/api/v1/sync/drugs", headers=headers, json=payload)
        # Second sync → should NOT create duplicate
        await client.post("/api/v1/sync/drugs", headers=headers, json=payload)

        async with seed_session_factory() as db:
            drug_result = await db.execute(
                select(Drug).where(Drug.standard_code == code)
            )
            drug = drug_result.scalar_one()
            alert_result = await db.execute(
                select(AlertLog).where(
                    AlertLog.alert_type == "DRUG_CODE_UNMATCHED",
                    AlertLog.ref_id == drug.id,
                )
            )
            alerts = alert_result.scalars().all()
            assert len(alerts) == 1

    async def test_multiple_unmatched_drugs_each_get_alert(
        self, client: AsyncClient, seed_data: dict
    ):
        """3 unmatched drugs → 3 separate alerts."""
        drugs = [
            {"standard_code": f"UA_{SUFFIX}_M{i}", "name": f"미매칭약품{i}", "category": "PRESCRIPTION"}
            for i in range(3)
        ]
        resp = await client.post(
            "/api/v1/sync/drugs",
            headers={"X-API-Key": seed_data["api_key"]},
            json={"drugs": drugs},
        )
        assert resp.status_code == 200

        async with seed_session_factory() as db:
            result = await db.execute(
                select(AlertLog).where(
                    AlertLog.pharmacy_id == seed_data["pharmacy_id"],
                    AlertLog.alert_type == "DRUG_CODE_UNMATCHED",
                )
            )
            alerts = result.scalars().all()
            test_alerts = [a for a in alerts if "미매칭약품" in a.message]
            assert len(test_alerts) == 3
