# Phase 2B-2: OTC 재고 관리 CRUD

## Context

약국에서 ATDPS 카세트에 들어가지 않는 일반의약품(OTC)의 재고를 관리한다. 전문의약품(prescription_inventory)은 ATDPS/PM+20에서 자동 동기화되지만, OTC는 약사가 직접 앱에서 CRUD로 관리한다. 매장 진열 위치(display_location)와 창고 위치(storage_location)를 분리하여 기록하고, 재고가 임계값 이하로 떨어지면 LOW_STOCK 알림을 생성한다.

**현재 상태:**
- `otc_inventory` 테이블 DDL/ORM 존재 (Phase 1)
- `drug_thresholds` 테이블 존재 (OTC/전문약 공용)
- `inventory_audit_log` 테이블 존재 (action: INSERT/UPDATE/DELETE, JSONB old/new_values)
- `display_location`, `storage_location` 컬럼 **미존재** → ALTER TABLE 필요
- OTC 전용 라우터/서비스/스키마 **없음** → 신규 생성
- 약품 검색 API **없음** → 신규 생성 (클라이언트가 drug_id 조회 필요)

### Review Feedback 반영

| # | 이슈 | 결정 |
|---|------|------|
| P16 | DELETE가 물리 삭제인데 audit log 미기록 | 물리 삭제 유지 + **삭제 전 `inventory_audit_log`에 action='OTC_DELETE' 기록** (old_values에 drug_id, quantity, location 등 현재 상태 JSONB 저장, performed_by = user.id). CHECK 제약조건에 `'OTC_DELETE'` 추가 필요 |
| P17 | PUT에서 null이면 기존 값 유지인지 NULL 덮어쓰기인지 불명확 | **PUT = 전체 덮어쓰기** (null 보내면 NULL로 저장). PATCH 미구현. 스키마에 docstring 명시 |
| P18 | 클라이언트가 drug_id를 알 방법 없음 | **`GET /api/v1/drugs` 약품 검색 엔드포인트 포함** (search ILIKE, category: OTC/PRESCRIPTION/ALL) |
| M8 | last_counted_at 수동 입력 불가 | 현재는 **자동 now()** 유지. 향후 필요 시 request에 optional 필드 추가 |

---

## 1. DDL 변경

```sql
-- pharma-automation/docs/db-schema.sql

-- 1) otc_inventory에 위치 컬럼 추가
ALTER TABLE otc_inventory
  ADD COLUMN display_location VARCHAR(100),   -- 매장 진열 위치 (e.g. "A열 3번 선반")
  ADD COLUMN storage_location VARCHAR(100);   -- 창고 내 위치 (e.g. "창고2-B선반")

-- 2) inventory_audit_log CHECK 제약조건에 'OTC_DELETE' 추가 (P16)
ALTER TABLE inventory_audit_log
  DROP CONSTRAINT IF EXISTS inventory_audit_log_action_check,
  ADD CONSTRAINT inventory_audit_log_action_check
    CHECK (action IN ('INSERT', 'UPDATE', 'DELETE', 'OTC_DELETE'));
```

ORM 모델 (`tables.py`)에도 동일 컬럼 추가:
```python
display_location: Mapped[str | None] = mapped_column(String(100))
storage_location: Mapped[str | None] = mapped_column(String(100))
```

---

## 2. 파일 목록

| # | 파일 | 역할 | 변경 |
|---|------|------|------|
| 1 | `docs/db-schema.sql` | DDL | otc_inventory ALTER TABLE + inventory_audit_log CHECK 변경 |
| 2 | `cloud/app/models/tables.py` | ORM | OtcInventory에 2개 컬럼 추가 |
| 3 | `cloud/app/schemas/otc.py` | **신규** | OTC CRUD Pydantic 스키마 |
| 4 | `cloud/app/schemas/drug.py` | **신규** | 약품 검색 Pydantic 스키마 (P18) |
| 5 | `cloud/app/services/otc_service.py` | **신규** | OTC CRUD 비즈니스 로직 + audit log |
| 6 | `cloud/app/services/drug_service.py` | **신규** | 약품 검색 서비스 (P18) |
| 7 | `cloud/app/routers/otc.py` | **신규** | OTC CRUD 엔드포인트 |
| 8 | `cloud/app/routers/drugs.py` | **신규** | 약품 검색 엔드포인트 (P18) |
| 9 | `cloud/app/main.py` | 라우터 등록 | `include_router` 추가 (otc + drugs) |
| 10 | `cloud/tests/test_otc.py` | **신규** | OTC CRUD 테스트 |
| 11 | `cloud/tests/test_drugs.py` | **신규** | 약품 검색 테스트 (P18) |
| 12 | `cloud/tests/conftest.py` | 시드 데이터 | OTC drug + threshold 시드 추가 |

---

## 3. 엔드포인트 상세

### 3.0 약품 검색 API (P18)

**Prefix:** `/api/v1/drugs` — tag: `"app-dev"`, JWT 인증 필수

| Method | Path | 설명 | Status | Request | Response |
|--------|------|------|--------|---------|----------|
| GET | `/` | 약품 목록 검색 | 200 | Query params | `DrugListResponse` |

```python
# schemas/drug.py
class DrugOut(BaseModel):
    id: int
    standard_code: str
    name: str
    category: str  # PRESCRIPTION | OTC

class DrugListResponse(BaseModel):
    items: list[DrugOut]
    total: int
```

Query Parameters:
```python
search: str | None = Query(None)         # Drug.name ILIKE "%search%"
category: str | None = Query(None)       # "OTC" | "PRESCRIPTION" | "ALL" (default: ALL — 필터 미적용)
limit: int = Query(50, le=200)
offset: int = Query(0)
```

서비스 (`services/drug_service.py`):
- `pharmacy_id` 무관 (drugs는 전역 마스터)
- `search` → `Drug.name.ilike(f"%{search}%")`
- `category` → `None` 또는 `"ALL"` 이면 필터 미적용, 그 외 `Drug.category == category`

Response 예시:
```json
{
  "items": [
    {"id": 2, "standard_code": "KD67890", "name": "타이레놀", "category": "OTC"}
  ],
  "total": 1
}
```

### 3.1 OTC 재고 CRUD

**Prefix:** `/api/v1/otc-inventory` — tag: `"app-dev"`, JWT 인증 필수

| Method | Path | 설명 | Status | Request | Response |
|--------|------|------|--------|---------|----------|
| POST | `/` | OTC 재고 항목 생성 | 201 | `OtcCreateRequest` | `OtcItemResponse` |
| GET | `/` | OTC 재고 목록 조회 | 200 | Query params | `OtcListResponse` |
| GET | `/{item_id}` | OTC 재고 단건 조회 | 200 | path param | `OtcItemResponse` |
| PUT | `/{item_id}` | OTC 재고 수정 (optimistic lock) | 200 | `OtcUpdateRequest` | `OtcItemResponse` |
| DELETE | `/{item_id}` | OTC 재고 삭제 (audit log 기록 후 물리 삭제) | 204 | path param | — |

### 3.2 Pydantic 스키마 (`schemas/otc.py`)

```python
class OtcCreateRequest(BaseModel):
    drug_id: int
    current_quantity: int = Field(..., ge=0)
    display_location: str | None = Field(None, max_length=100)
    storage_location: str | None = Field(None, max_length=100)

class OtcUpdateRequest(BaseModel):
    """PUT은 전체 덮어쓰기. null 전송 시 해당 필드 NULL로 저장됨. 부분 수정은 지원하지 않음."""
    current_quantity: int = Field(..., ge=0)
    display_location: str | None = Field(None, max_length=100)
    storage_location: str | None = Field(None, max_length=100)
    version: int  # optimistic locking — 클라이언트가 보유한 version 전송

class OtcItemResponse(BaseModel):
    id: int
    pharmacy_id: int
    drug_id: int
    drug_name: str | None = None       # JOIN으로 채움
    current_quantity: int
    display_location: str | None = None
    storage_location: str | None = None
    last_counted_at: datetime | None = None
    version: int
    created_at: datetime
    updated_at: datetime
    is_low_stock: bool = False          # threshold 비교 결과
    min_quantity: int | None = None     # threshold 값 (있으면)

class OtcListResponse(BaseModel):
    items: list[OtcItemResponse]
    total: int
```

### 3.3 GET 목록 Query Parameters

```python
low_stock_only: bool = Query(False)     # LOW_STOCK 필터
search: str | None = Query(None)        # drug_name ILIKE 검색
limit: int = Query(50, le=200)
offset: int = Query(0)
```

---

## 4. 서비스 로직 (`services/otc_service.py`)

### 4.1 create_otc_item
1. `drug_id` 존재 확인 → 404
2. `UNIQUE(pharmacy_id, drug_id)` 중복 확인 → 409
3. INSERT `otc_inventory` (pharmacy_id from JWT)
4. LOW_STOCK 체크 → 알림 생성 (임계값 이하인 경우)
5. `last_counted_at = now()` 설정
6. Return item + drug_name (JOIN)

### 4.2 list_otc_items
1. `pharmacy_id` 필터 (필수)
2. LEFT JOIN `drugs` (drug_name)
3. LEFT JOIN `drug_thresholds` (min_quantity, is_low_stock 계산)
4. `low_stock_only` 필터: `current_quantity < min_quantity` 인 것만
5. `search` 필터: `Drug.name ILIKE f"%{search}%"`
6. `total` count + `limit/offset` 페이지네이션
7. `is_low_stock = current_quantity < threshold.min_quantity if threshold else False`

### 4.3 get_otc_item
1. `id` + `pharmacy_id` 조회 → 404
2. JOIN drug + threshold
3. Return single item

### 4.4 update_otc_item
1. `id` + `pharmacy_id` 조회 → 404
2. **Optimistic locking**: `WHERE version = req.version`
   - 불일치 시 → **409 Conflict** ("Data has been modified by another user")
3. **P17: PUT = 전체 덮어쓰기** — `current_quantity`, `display_location`, `storage_location` 모두 req 값으로 덮어씀 (null이면 NULL 저장)
4. `version += 1`, `updated_at = now()`, `last_counted_at = now()`
5. LOW_STOCK 체크 → 알림 생성 (기존 sync_service 패턴 재사용)
6. Return updated item

### 4.5 delete_otc_item (P16: audit log 기록)
1. `id` + `pharmacy_id` 조회 → 404
2. **`inventory_audit_log`에 삭제 전 상태 기록** INSERT:
   - `table_name = "otc_inventory"`
   - `record_id = item.id`
   - `action = "OTC_DELETE"`
   - `old_values = { "drug_id": item.drug_id, "current_quantity": item.current_quantity, "display_location": item.display_location, "storage_location": item.storage_location, "version": item.version }` (JSONB)
   - `new_values = None`
   - `performed_by = user.id` (JWT에서 추출)
3. DELETE (물리 삭제)
4. Return None (204)

### 4.6 LOW_STOCK 알림 체크 (내부 헬퍼)

```python
async def _check_low_stock_alert(
    db: AsyncSession, pharmacy_id: int, drug_id: int,
    current_quantity: int, drug_name: str | None,
) -> None:
```

- `drug_thresholds`에서 `(pharmacy_id, drug_id, is_active=True)` 조회
- `current_quantity < min_quantity` → 알림 생성
- **중복 방지**: 24시간 내 미읽은 동일 알림 존재 시 스킵
- `ref_table = "otc_inventory"` (prescription_inventory와 구분)
- sync_service.py의 기존 LOW_STOCK 패턴과 동일 로직

---

## 5. Optimistic Locking 상세

```
Client → PUT /otc-inventory/42  { "current_quantity": 10, "version": 3 }
Server → SELECT ... WHERE id=42 AND pharmacy_id=X
         if row.version != 3  → 409 Conflict
         UPDATE ... SET version=4, current_quantity=10, updated_at=now()
         → 200 { ..., "version": 4 }
```

- 클라이언트는 GET으로 받은 `version`을 PUT 시 그대로 전송
- 서버는 현재 DB의 version과 비교 → 불일치 시 409
- 성공 시 version을 +1 하여 반환

---

## 6. 구현 순서 (11단계)

| 단계 | 작업 | 파일 |
|------|------|------|
| 0 | 계획 문서 분리 (완료) | `docs/phase2b2-otc-plan.md` |
| 1 | DDL 변경 (ALTER TABLE) + DB 적용 | `db-schema.sql` |
| 2 | ORM 모델 컬럼 추가 | `models/tables.py` |
| 3 | OTC Pydantic 스키마 작성 | `schemas/otc.py` (신규) |
| 4 | 약품 검색 스키마 + 서비스 + 라우터 (P18) | `schemas/drug.py`, `services/drug_service.py`, `routers/drugs.py` (신규) |
| 5 | OTC 서비스 구현 (audit log 포함) | `services/otc_service.py` (신규) |
| 6 | OTC 라우터 구현 | `routers/otc.py` (신규) |
| 7 | main.py 라우터 등록 (otc + drugs) | `main.py` |
| 8 | 테스트 시드 데이터 | `conftest.py` |
| 9 | OTC 테스트 작성 | `test_otc.py` (신규) |
| 10 | 약품 검색 테스트 작성 | `test_drugs.py` (신규) |
| 11 | 검증 실행 | curl + pytest |

---

## 7. 테스트 목록 (`test_otc.py`)

### CRUD 기본 (7건)
| # | 테스트 | 기대 |
|---|--------|------|
| 1 | `test_create_otc_item` | 201, drug_name 포함 |
| 2 | `test_create_duplicate_drug` | 409 (동일 pharmacy+drug) |
| 3 | `test_create_invalid_drug` | 404 (존재하지 않는 drug_id) |
| 4 | `test_list_otc_items` | 200, items + total |
| 5 | `test_list_low_stock_only` | 200, low_stock 필터 동작 |
| 6 | `test_get_otc_item` | 200, 단건 조회 |
| 7 | `test_get_otc_item_not_found` | 404 |

### 수정 + Optimistic Lock (4건)
| # | 테스트 | 기대 |
|---|--------|------|
| 8 | `test_update_otc_item` | 200, version 증가, 값 변경 |
| 9 | `test_update_version_conflict` | 409 (stale version) |
| 10 | `test_update_not_found` | 404 |
| 11 | `test_update_location_fields` | 200, display/storage_location 변경 확인 |

### 삭제 + Audit Log (3건, P16)
| # | 테스트 | 기대 |
|---|--------|------|
| 12 | `test_delete_otc_item` | 204, inventory_audit_log에 action='OTC_DELETE' 기록 존재 |
| 13 | `test_delete_audit_log_contents` | audit log의 old_values에 삭제 전 상태(drug_id, current_quantity, display_location, storage_location, version) 포함 |
| 14 | `test_delete_not_found` | 404 |

### PUT 전체 덮어쓰기 (1건, P17)
| # | 테스트 | 기대 |
|---|--------|------|
| 15 | `test_update_null_clears_location` | PUT에 `display_location: null` → DB에 NULL 저장 (기존 값 유지 아님) |

### LOW_STOCK 알림 (2건)
| # | 테스트 | 기대 |
|---|--------|------|
| 16 | `test_create_triggers_low_stock_alert` | threshold 설정 후 생성 → alert_logs에 LOW_STOCK 기록 |
| 17 | `test_update_triggers_low_stock_alert` | 수정으로 임계값 이하 → alert 생성 |

### 데이터 격리 (1건)
| # | 테스트 | 기대 |
|---|--------|------|
| 18 | `test_cross_pharmacy_isolation` | 다른 약국 item 접근 → 404 |

### 약품 검색 (`test_drugs.py`, 3건, P18)
| # | 테스트 | 기대 |
|---|--------|------|
| 19 | `test_search_drugs_by_name` | search=타이레놀 → 해당 약품 반환, items + total 구조 |
| 20 | `test_filter_drugs_by_category` | category=OTC → OTC만 반환, PRESCRIPTION 미포함 |
| 21 | `test_search_drugs_empty_result` | search=존재하지않는약 → items=[], total=0 |

**총 21건 신규 + 기존 28건 = 49건 예상**

---

## 8. 검증 방법

```bash
# 1. DDL 적용 확인
sudo -u postgres psql -d pharma -c "\d otc_inventory" | grep -E "display_location|storage_location"

# 2. 서버 기동
PHARMA_DATABASE_URL="..." PHARMA_JWT_SECRET_KEY="..." uvicorn app.main:app --port 8000

# 3. JWT 토큰 획득
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"pharmacy_id":1,"username":"testuser","password":"testpass123"}' | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# 4. 약품 검색 (P18) — drug_id 조회
curl -s http://localhost:8000/api/v1/drugs?search=타이레놀&category=OTC \
  -H "Authorization: Bearer $TOKEN"

# 5. POST 생성 (201)
curl -s -w "\n%{http_code}" -X POST http://localhost:8000/api/v1/otc-inventory \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"drug_id":2,"current_quantity":50,"display_location":"A열 3번","storage_location":"창고2-B"}'

# 6. GET 목록 (200)
curl -s http://localhost:8000/api/v1/otc-inventory -H "Authorization: Bearer $TOKEN"

# 6. GET 단건 (200)
curl -s http://localhost:8000/api/v1/otc-inventory/1 -H "Authorization: Bearer $TOKEN"

# 7. PUT 수정 + optimistic lock (200)
curl -s -X PUT http://localhost:8000/api/v1/otc-inventory/1 \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"current_quantity":30,"display_location":"B열 1번","version":1}'

# 8. PUT version conflict (409)
curl -s -w "\n%{http_code}" -X PUT http://localhost:8000/api/v1/otc-inventory/1 \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"current_quantity":25,"version":1}'

# 9. DELETE (204)
curl -s -w "\n%{http_code}" -X DELETE http://localhost:8000/api/v1/otc-inventory/1 \
  -H "Authorization: Bearer $TOKEN"

# 10. JWT 없이 접근 (401)
curl -s -w "\n%{http_code}" http://localhost:8000/api/v1/otc-inventory

# 11. pytest 전체 (49건 예상)
pytest tests/ -v
```
