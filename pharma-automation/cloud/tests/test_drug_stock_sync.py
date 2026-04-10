"""drug-stock sync + drugs sync endpoint tests."""

import pytest

pytestmark = pytest.mark.asyncio


class TestSyncDrugs:
    """POST /api/v1/sync/drugs — 약품 마스터 동기화."""

    async def test_sync_new_drugs(self, client, seed_data):
        """신규 약품 등록."""
        import time
        suffix = str(int(time.time()))[-6:]
        resp = await client.post(
            "/api/v1/sync/drugs",
            headers={"X-API-Key": seed_data["api_key"]},
            json={
                "drugs": [
                    {
                        "standard_code": f"PM_NEW_A{suffix}",
                        "name": "테스트약품A",
                        "manufacturer": "제약사A",
                        "category": "PRESCRIPTION",
                        "insurance_code": f"6{suffix}01",
                    },
                    {
                        "name": "테스트약품B",
                        "category": "NARCOTIC",
                        "insurance_code": f"6{suffix}02",
                    },
                ]
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["new_count"] == 2
        assert data["synced_count"] == 2

    async def test_sync_update_existing_drug(self, client, seed_data):
        """기존 약품 업데이트."""
        import time
        ins_code = f"6{int(time.time()) % 100000}"
        headers = {"X-API-Key": seed_data["api_key"]}
        await client.post(
            "/api/v1/sync/drugs",
            headers=headers,
            json={
                "drugs": [
                    {"name": "원래이름", "category": "PRESCRIPTION", "insurance_code": ins_code}
                ]
            },
        )
        resp = await client.post(
            "/api/v1/sync/drugs",
            headers=headers,
            json={
                "drugs": [
                    {
                        "name": "변경이름",
                        "manufacturer": "새제약사",
                        "category": "NARCOTIC",
                        "insurance_code": ins_code,
                    }
                ]
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["updated_count"] == 1
        assert data["new_count"] == 0

    async def test_sync_drugs_missing_insurance_code_rejected(self, client, seed_data):
        """insurance_code 없으면 422."""
        resp = await client.post(
            "/api/v1/sync/drugs",
            headers={"X-API-Key": seed_data["api_key"]},
            json={
                "drugs": [{"name": "코드없음", "category": "PRESCRIPTION"}]
            },
        )
        assert resp.status_code == 422

    async def test_sync_drugs_no_api_key(self, client):
        """API 키 없으면 401/403."""
        resp = await client.post(
            "/api/v1/sync/drugs",
            headers={"X-API-Key": "invalid-key-xyz"},
            json={"drugs": [{"name": "Y", "category": "PRESCRIPTION", "insurance_code": "X"}]},
        )
        assert resp.status_code in (401, 403)


