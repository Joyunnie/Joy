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


class TestSyncDrugStock:
    """POST /api/v1/sync/drug-stock — 약품별 재고 동기화."""

    async def test_sync_drug_stock_basic(
        self, client, seed_data, otc_drug_seed, cleanup_drug_stock
    ):
        """정상 동기화."""
        resp = await client.post(
            "/api/v1/sync/drug-stock",
            headers={"X-API-Key": seed_data["api_key"]},
            json={
                "items": [
                    {
                        "drug_standard_code": "KD67890",
                        "current_quantity": 50.0,
                        "is_narcotic": False,
                    }
                ],
                "synced_at": "2026-03-27T00:00:00Z",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["synced_count"] == 1
        assert data["skipped_count"] == 0

    async def test_sync_drug_stock_upsert(
        self, client, seed_data, otc_drug_seed, cleanup_drug_stock
    ):
        """UPSERT: 두 번 동기화 시 업데이트."""
        headers = {"X-API-Key": seed_data["api_key"]}
        payload = {
            "items": [
                {"drug_standard_code": "KD67890", "current_quantity": 50.0, "is_narcotic": False}
            ],
            "synced_at": "2026-03-27T00:00:00Z",
        }
        await client.post("/api/v1/sync/drug-stock", headers=headers, json=payload)

        payload["items"][0]["current_quantity"] = 30.0
        payload["synced_at"] = "2026-03-27T01:00:00Z"
        resp = await client.post("/api/v1/sync/drug-stock", headers=headers, json=payload)
        assert resp.status_code == 200
        assert resp.json()["synced_count"] == 1

    async def test_sync_drug_stock_unknown_drug_skipped(
        self, client, seed_data, cleanup_drug_stock
    ):
        """미등록 약품 건너뛰기."""
        resp = await client.post(
            "/api/v1/sync/drug-stock",
            headers={"X-API-Key": seed_data["api_key"]},
            json={
                "items": [
                    {"drug_standard_code": "UNKNOWN_999", "current_quantity": 10.0}
                ],
                "synced_at": "2026-03-27T00:00:00Z",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["synced_count"] == 0
        assert data["skipped_count"] == 1

    async def test_sync_drug_stock_low_stock_alert(
        self, client, seed_data, otc_drug_seed, cleanup_drug_stock
    ):
        """threshold(10) 미만 시 LOW_STOCK 알림 생성."""
        resp = await client.post(
            "/api/v1/sync/drug-stock",
            headers={"X-API-Key": seed_data["api_key"]},
            json={
                "items": [
                    {"drug_standard_code": "KD67890", "current_quantity": 5.0, "is_narcotic": False}
                ],
                "synced_at": "2026-03-27T00:00:00Z",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["low_stock_alerts"]) == 1
        alert = data["low_stock_alerts"][0]
        assert alert["current_quantity"] == 5
        assert alert["min_quantity"] == 10

    async def test_sync_drug_stock_negative_quantity_triggers_alert(
        self, client, seed_data, otc_drug_seed, cleanup_drug_stock
    ):
        """음수 재고도 LOW_STOCK 알림 생성 (TEMP_STOCK 음수값은 실재고 마이너스)."""
        resp = await client.post(
            "/api/v1/sync/drug-stock",
            headers={"X-API-Key": seed_data["api_key"]},
            json={
                "items": [
                    {"drug_standard_code": "KD67890", "current_quantity": -3.0, "is_narcotic": False}
                ],
                "synced_at": "2026-03-27T00:00:00Z",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["low_stock_alerts"]) == 1
        assert data["low_stock_alerts"][0]["current_quantity"] == -3

    async def test_sync_drug_stock_duplicate_alert_suppressed(
        self, client, seed_data, otc_drug_seed, cleanup_drug_stock
    ):
        """24시간 내 중복 LOW_STOCK 알림 방지."""
        headers = {"X-API-Key": seed_data["api_key"]}
        payload = {
            "items": [{"drug_standard_code": "KD67890", "current_quantity": 3.0}],
            "synced_at": "2026-03-27T00:00:00Z",
        }
        resp1 = await client.post("/api/v1/sync/drug-stock", headers=headers, json=payload)
        assert len(resp1.json()["low_stock_alerts"]) == 1

        payload["synced_at"] = "2026-03-27T00:05:00Z"
        resp2 = await client.post("/api/v1/sync/drug-stock", headers=headers, json=payload)
        assert len(resp2.json()["low_stock_alerts"]) == 0

    async def test_sync_drug_stock_no_api_key(self, client):
        """잘못된 API 키면 401/403."""
        resp = await client.post(
            "/api/v1/sync/drug-stock",
            headers={"X-API-Key": "invalid-key-xyz"},
            json={"items": [], "synced_at": "2026-03-27T00:00:00Z"},
        )
        assert resp.status_code in (401, 403)
