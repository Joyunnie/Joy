# Phase 2B-3: Narcotics Inventory/Transaction CRUD -- Implementation Plan

## 0. Design Decisions (Resolved)

**Decision 1 -- Transaction type naming:** Keep the DDL naming convention (short uppercase verbs: `RECEIVE`, `DISPENSE`, `DISPOSE`, `ADJUST`) and add `RETURN`. These are internal constants; the Korean UI labels (구입, 조제출고, 폐기, 실사조정, 반품) belong in the frontend. Rationale: the existing DDL already uses this style, and changing four existing values for cosmetic reasons introduces unnecessary migration risk.

**Decision 2 -- DELETE endpoint behavior:** The DELETE endpoint sets `is_active = false` (soft delete) AND auto-creates a `DISPOSE` transaction with mandatory `notes` field (reason for disposal). This satisfies the legal requirement that every quantity change is traced and no records are physically deleted. The `current_quantity` is zeroed out as part of the disposal.

**Decision 3 -- DISPOSE transaction requires notes:** Yes, `notes` is mandatory for `DISPOSE` and `RETURN` transaction types. For `RECEIVE`, `DISPENSE`, and `ADJUST`, it remains optional. This is enforced at the service layer, not the DDL.

---

## 1. DDL Changes

Five ALTER statements are needed. There is no migrations framework in the project, so these go into a new SQL file.

```sql
-- 1a. Add version column for optimistic locking
ALTER TABLE narcotics_inventory
    ADD COLUMN version INTEGER NOT NULL DEFAULT 1;

-- 1b. Add is_active column for soft delete
ALTER TABLE narcotics_inventory
    ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE;

-- 1c. Expand transaction_type CHECK to include RETURN
ALTER TABLE narcotics_transactions
    DROP CONSTRAINT narcotics_transactions_transaction_type_check;
ALTER TABLE narcotics_transactions
    ADD CONSTRAINT narcotics_transactions_transaction_type_check
    CHECK (transaction_type IN ('RECEIVE', 'DISPENSE', 'DISPOSE', 'ADJUST', 'RETURN'));

-- 1d. Expand inventory_audit_log action CHECK for narcotics actions
ALTER TABLE inventory_audit_log
    DROP CONSTRAINT inventory_audit_log_action_check;
ALTER TABLE inventory_audit_log
    ADD CONSTRAINT inventory_audit_log_action_check
    CHECK (action IN ('INSERT', 'UPDATE', 'DELETE', 'OTC_DELETE', 'NARCOTICS_DEACTIVATE'));
```

The DDL doc file (`docs/db-schema.sql`) should also be updated with these columns inline in the CREATE TABLE statements so it stays the single source of truth.

---

## 2. ORM Model Changes

**File:** `cloud/app/models/tables.py`

Add two columns to `NarcoticsInventory`:

```python
version: Mapped[int] = mapped_column(Integer, default=1)
is_active: Mapped[bool] = mapped_column(Boolean, default=True)
```

Update the comment on `NarcoticsTransaction.transaction_type` to include `RETURN`:

```python
transaction_type: Mapped[str] = mapped_column(String(20))  # RECEIVE | DISPENSE | DISPOSE | ADJUST | RETURN
```

---

## 3. File List with Roles

| File | Role | Action |
|------|------|--------|
| `docs/db-schema.sql` | DDL source of truth | UPDATE (add version, is_active, expand CHECKs) |
| `docs/migration_2b3.sql` | Migration script | CREATE NEW |
| `cloud/app/models/tables.py` | ORM models | UPDATE (add 2 columns to NarcoticsInventory, update comment) |
| `cloud/app/schemas/narcotics.py` | Pydantic request/response schemas | CREATE NEW |
| `cloud/app/services/narcotics_service.py` | Business logic (CRUD + transactions) | CREATE NEW |
| `cloud/app/routers/narcotics.py` | FastAPI router | CREATE NEW |
| `cloud/app/main.py` | App entry point | UPDATE (register narcotics router) |
| `cloud/tests/conftest.py` | Test fixtures | UPDATE (add narcotics seed fixtures) |
| `cloud/tests/test_narcotics.py` | Tests | CREATE NEW |

---

## 4. Endpoint Specifications

Base path: `/api/v1/narcotics-inventory`

### 4.1 POST `/api/v1/narcotics-inventory` -- Create (입고/RECEIVE)

**Request body:**
```json
{
  "drug_id": 123,
  "lot_number": "LOT-2026-001",
  "quantity": 100,
  "notes": "도매상 A에서 입고"
}
```

**Behavior:**
1. Validate `drug_id` exists and has `category = 'NARCOTIC'`
2. Check for existing active record with same `(pharmacy_id, drug_id, lot_number)`
   - If exists and `is_active = true`: HTTP 409
   - If exists and `is_active = false`: reactivate it (set `is_active = true`, add `quantity` to `current_quantity`, bump `version`)
3. If new: INSERT `narcotics_inventory` with `current_quantity = quantity`
4. INSERT `narcotics_transactions` with `transaction_type = 'RECEIVE'`, `remaining_quantity = current_quantity`
5. INSERT `inventory_audit_log` with `action = 'INSERT'`
6. Check `NARCOTICS_LOW` alert threshold

**Response:** `201 Created` with `NarcoticsItemResponse`

### 4.2 GET `/api/v1/narcotics-inventory` -- List

**Query params:**
- `search: str | None` -- drug name ilike filter
- `active_only: bool = true` -- filter by `is_active`
- `low_stock_only: bool = false`
- `limit: int = 50` (max 200)
- `offset: int = 0`

**Response:** `200 OK` with `NarcoticsListResponse`

### 4.3 GET `/api/v1/narcotics-inventory/{item_id}` -- Get single

**Response:** `200 OK` with `NarcoticsItemResponse` (includes recent transactions)

### 4.4 PUT `/api/v1/narcotics-inventory/{item_id}` -- Update (실사조정/ADJUST)

**Request body:**
```json
{
  "current_quantity": 95,
  "last_inspected_at": "2026-03-17T09:00:00Z",
  "notes": "실사 결과 5개 차이",
  "version": 1
}
```

**Behavior:**
1. Fetch record, verify `pharmacy_id` match and `is_active = true`
2. Optimistic lock check (`version` mismatch -> 409)
3. Compute `quantity_delta = new_quantity - old_quantity`
4. If `quantity_delta != 0`: INSERT `narcotics_transactions` with `transaction_type = 'ADJUST'`, `quantity = quantity_delta`, `remaining_quantity = new_quantity`
5. UPDATE `narcotics_inventory`: set `current_quantity`, `last_inspected_at`, bump `version`, set `updated_at`
6. INSERT `inventory_audit_log` with `action = 'UPDATE'`, `old_values`, `new_values`
7. Check `NARCOTICS_LOW` alert

**Response:** `200 OK` with `NarcoticsItemResponse`

### 4.5 DELETE `/api/v1/narcotics-inventory/{item_id}` -- Dispose/Deactivate (폐기)

**Request body (required):**
```json
{
  "notes": "유효기간 만료로 폐기",
  "version": 2
}
```

**Behavior:**
1. Fetch record, verify `pharmacy_id` match, `is_active = true`, version check
2. INSERT `narcotics_transactions` with `transaction_type = 'DISPOSE'`, `quantity = -current_quantity`, `remaining_quantity = 0`, `notes = req.notes`
3. UPDATE `narcotics_inventory`: `current_quantity = 0`, `is_active = false`, bump `version`, `updated_at`
4. INSERT `inventory_audit_log` with `action = 'NARCOTICS_DEACTIVATE'`

**Response:** `200 OK` with `NarcoticsItemResponse` (NOT 204, because we return the final state for the legal record)

Note: This is NOT a standard REST DELETE returning 204. Returning the final state is intentional so the caller can confirm and archive the disposal record. The HTTP method remains DELETE for semantic clarity (the resource is being deactivated).

### 4.6 POST `/api/v1/narcotics-inventory/{item_id}/dispense` -- Dispense (조제출고)

**Request body:**
```json
{
  "quantity": 5,
  "patient_hash": "abc123...",
  "prescription_number": "RX-2026-001",
  "notes": null,
  "version": 2
}
```

**Behavior:**
1. Fetch record, verify active, pharmacy match, version check
2. Validate `quantity > 0` and `current_quantity >= quantity`
3. UPDATE `current_quantity -= quantity`, bump `version`
4. INSERT `narcotics_transactions` with `transaction_type = 'DISPENSE'`, `quantity = -quantity`, `remaining_quantity = new_current_quantity`
5. INSERT `inventory_audit_log` with `action = 'UPDATE'`
6. Check `NARCOTICS_LOW` alert

**Response:** `200 OK` with `NarcoticsItemResponse`

### 4.7 POST `/api/v1/narcotics-inventory/{item_id}/return` -- Return (반품)

**Request body:**
```json
{
  "quantity": 10,
  "notes": "도매상 반품 처리",
  "version": 3
}
```

**Behavior:**
1. Fetch, verify active, pharmacy, version
2. Validate `quantity > 0` and `current_quantity >= quantity`
3. UPDATE `current_quantity -= quantity`, bump `version`
4. INSERT `narcotics_transactions` with `transaction_type = 'RETURN'`, `quantity = -quantity`, `remaining_quantity = new_current_quantity`
5. INSERT `inventory_audit_log` with `action = 'UPDATE'`

**Response:** `200 OK` with `NarcoticsItemResponse`

### 4.8 GET `/api/v1/narcotics-inventory/{item_id}/transactions` -- Transaction history

**Query params:** `limit`, `offset`, `transaction_type` filter

**Response:** `200 OK` with `NarcoticsTransactionListResponse`

---

## 5. Schema Definitions

**File:** `cloud/app/schemas/narcotics.py`

```python
from datetime import datetime
from pydantic import BaseModel, Field

# --- Requests ---

class NarcoticsCreateRequest(BaseModel):
    drug_id: int
    lot_number: str = Field(..., max_length=50)
    quantity: int = Field(..., gt=0)
    notes: str | None = None

class NarcoticsUpdateRequest(BaseModel):
    """실사조정 (ADJUST). quantity 변동 시 자동으로 ADJUST 트랜잭션 생성."""
    current_quantity: int = Field(..., ge=0)
    last_inspected_at: datetime | None = None
    notes: str | None = None
    version: int

class NarcoticsDeleteRequest(BaseModel):
    """폐기 처리. notes 필수."""
    notes: str = Field(..., min_length=1)
    version: int

class NarcoticsDispenseRequest(BaseModel):
    quantity: int = Field(..., gt=0)
    patient_hash: str | None = Field(None, max_length=64)
    prescription_number: str | None = Field(None, max_length=50)
    notes: str | None = None
    version: int

class NarcoticsReturnRequest(BaseModel):
    quantity: int = Field(..., gt=0)
    notes: str = Field(..., min_length=1)
    version: int

# --- Responses ---

class NarcoticsItemResponse(BaseModel):
    id: int
    pharmacy_id: int
    drug_id: int
    drug_name: str | None = None
    lot_number: str
    current_quantity: int
    is_active: bool
    last_inspected_at: datetime | None = None
    version: int
    created_at: datetime
    updated_at: datetime
    is_low_stock: bool = False
    min_quantity: int | None = None

class NarcoticsListResponse(BaseModel):
    items: list[NarcoticsItemResponse]
    total: int

class NarcoticsTransactionOut(BaseModel):
    id: int
    transaction_type: str
    quantity: int
    remaining_quantity: int
    patient_hash: str | None = None
    prescription_number: str | None = None
    performed_by: int | None = None
    notes: str | None = None
    created_at: datetime

class NarcoticsTransactionListResponse(BaseModel):
    transactions: list[NarcoticsTransactionOut]
    total: int
```

---

## 6. Service Logic Details

**File:** `cloud/app/services/narcotics_service.py`

### Architecture

The service follows the same pattern as `otc_service.py` with these key differences:

1. **Every mutation creates a transaction record** -- the `narcotics_transactions` table serves as the legally mandated immutable audit trail.
2. **No hard delete** -- `delete_narcotics_item` sets `is_active = false` and zeroes quantity.
3. **Atomic operations** -- each service function performs inventory update + transaction insert + audit log insert within a single DB session (auto-committed by `get_db`).

### Helper Functions

```python
async def _check_narcotics_low_alert(db, pharmacy_id, drug_id, current_quantity, drug_name):
    """Same pattern as otc_service._check_low_stock_alert but uses alert_type='NARCOTICS_LOW'
    and ref_table='narcotics_inventory'."""

def _build_item_response(inv: NarcoticsInventory, drug_name, min_quantity) -> NarcoticsItemResponse:
    """Maps ORM object to response schema. Computes is_low_stock."""

async def _get_drug_and_threshold(db, pharmacy_id, drug_id) -> tuple[str|None, int|None]:
    """Reusable helper, identical pattern to OTC."""

async def _get_active_inventory(db, pharmacy_id, item_id) -> NarcoticsInventory:
    """Fetches inventory record, raises 404 if not found or is_active=false.
    Used by update/delete/dispense/return."""

async def _record_transaction(db, pharmacy_id, inventory_id, tx_type, quantity, remaining, user_id, **kwargs):
    """Creates NarcoticsTransaction row. Centralizes transaction creation."""

async def _record_audit(db, pharmacy_id, record_id, action, old_values, new_values, user_id):
    """Creates InventoryAuditLog row. Centralizes audit creation."""
```

### Core Functions

**`create_narcotics_item`** -- validates drug category is NARCOTIC, checks unique constraint on `(pharmacy_id, drug_id, lot_number)`, handles reactivation of soft-deleted records, creates RECEIVE transaction.

**`list_narcotics_items`** -- joins `Drug` and `DrugThreshold`, filters by `is_active`, supports search/low_stock_only/pagination. Default filters to `is_active = true` only.

**`get_narcotics_item`** -- single item fetch. Does NOT filter by `is_active` (allows viewing disposed items for legal audit).

**`update_narcotics_item`** -- optimistic lock check, computes delta, creates ADJUST transaction only if quantity changed, always updates `last_inspected_at` if provided.

**`delete_narcotics_item`** -- requires `NarcoticsDeleteRequest` body (notes + version). Sets `is_active = false`, zeroes quantity, creates DISPOSE transaction.

**`dispense_narcotics`** -- decrements quantity, validates sufficient stock, creates DISPENSE transaction with patient_hash and prescription_number.

**`return_narcotics`** -- decrements quantity (returns to supplier), creates RETURN transaction with mandatory notes.

**`list_transactions`** -- paginated read of `narcotics_transactions` for a given inventory item, with optional `transaction_type` filter.

### Quantity Sign Convention

The `quantity` field in `narcotics_transactions` uses signed values:
- `RECEIVE`: positive (stock increases)
- `DISPENSE`: negative (stock decreases)
- `DISPOSE`: negative (stock decreases to zero)
- `ADJUST`: signed (positive or negative delta)
- `RETURN`: negative (stock decreases, returned to supplier)

The `remaining_quantity` always stores the absolute `current_quantity` after the transaction.

---

## 7. Router

**File:** `cloud/app/routers/narcotics.py`

```python
router = APIRouter(prefix="/api/v1/narcotics-inventory", tags=["app-dev"])
```

Eight endpoint functions, each following the exact pattern from `routers/otc.py`:
- `Depends(get_current_user)` for JWT auth
- `Depends(get_db)` for database session
- `user.pharmacy_id` for isolation

The DELETE endpoint is unique in that it accepts a request body (`NarcoticsDeleteRequest`). Since HTTP DELETE with a body is technically allowed but unusual, the router function uses a Pydantic model parameter directly (FastAPI supports this).

### Registration in main.py

```python
from app.routers import narcotics
app.include_router(narcotics.router)
```

---

## 8. Test List

**File:** `cloud/tests/test_narcotics.py`

### Fixtures (in conftest.py)

- `narcotic_drug_seed` -- creates a `Drug` with `category='NARCOTIC'` and a `DrugThreshold` with `min_quantity=10`
- `cleanup_narcotics` -- deletes `narcotics_inventory`, `narcotics_transactions`, related `inventory_audit_log`, and `alert_logs` for the test pharmacy before each test

### Test Cases

**CRUD Basics:**
1. `test_create_narcotics_item` -- POST, verify 201, response fields, version=1
2. `test_create_duplicate_lot` -- same drug_id+lot_number -> 409
3. `test_create_invalid_drug` -- nonexistent drug_id -> 404
4. `test_create_non_narcotic_drug` -- drug with category=OTC -> 400 (wrong category)
5. `test_create_generates_receive_transaction` -- verify narcotics_transactions row with type=RECEIVE
6. `test_create_generates_audit_log` -- verify inventory_audit_log with action=INSERT
7. `test_list_narcotics` -- POST then GET list, verify total >= 1
8. `test_list_active_only_default` -- deactivated items excluded by default
9. `test_list_with_search` -- search by drug name
10. `test_list_low_stock_only` -- quantity below threshold
11. `test_get_narcotics_item` -- GET by id, verify fields
12. `test_get_not_found` -- nonexistent id -> 404

**Update (ADJUST):**
13. `test_update_narcotics_item` -- PUT with new quantity, verify version bump
14. `test_update_version_conflict` -- stale version -> 409
15. `test_update_not_found` -- 404
16. `test_update_generates_adjust_transaction` -- verify ADJUST transaction with correct delta
17. `test_update_no_quantity_change_no_transaction` -- same quantity -> no ADJUST transaction created
18. `test_update_generates_audit_log` -- verify UPDATE audit log with old/new values

**Delete (DISPOSE):**
19. `test_delete_narcotics_item` -- verify is_active=false, current_quantity=0 in response
20. `test_delete_requires_notes` -- empty notes -> 422
21. `test_delete_version_conflict` -- stale version -> 409
22. `test_delete_generates_dispose_transaction` -- verify DISPOSE transaction
23. `test_delete_generates_audit_log` -- verify NARCOTICS_DEACTIVATE audit
24. `test_delete_no_hard_delete` -- after delete, record still exists in DB (query with is_active=false)
25. `test_delete_already_inactive` -- deleting inactive item -> 404

**Dispense:**
26. `test_dispense_success` -- quantity decremented, DISPENSE transaction created
27. `test_dispense_insufficient_stock` -- quantity > current -> 400
28. `test_dispense_version_conflict` -- 409
29. `test_dispense_with_patient_hash` -- patient_hash stored in transaction
30. `test_dispense_inactive_item` -- 404

**Return:**
31. `test_return_success` -- quantity decremented, RETURN transaction created
32. `test_return_requires_notes` -- empty notes -> 422
33. `test_return_insufficient_stock` -- 400

**Alerts:**
34. `test_create_triggers_narcotics_low_alert` -- quantity below threshold creates NARCOTICS_LOW alert
35. `test_dispense_triggers_narcotics_low_alert` -- dispense drops below threshold
36. `test_update_triggers_narcotics_low_alert` -- adjust to below threshold

**Isolation:**
37. `test_cross_pharmacy_isolation` -- JWT from pharmacy A cannot access pharmacy B items

**Transaction History:**
38. `test_list_transactions` -- GET transactions endpoint returns paginated results
39. `test_list_transactions_filter_by_type` -- filter by transaction_type

**Reactivation:**
40. `test_reactivate_soft_deleted_item` -- POST with same drug_id+lot_number after dispose -> reactivates

---

## 9. Verification Steps

After implementation, verify in this order:

1. **Migration:** Run `migration_2b3.sql` against the test database. Confirm `\d narcotics_inventory` shows `version` and `is_active` columns. Confirm constraint changes with `\d narcotics_transactions`.

2. **Unit tests:** Run `pytest cloud/tests/test_narcotics.py -v`. All 40 tests must pass.

3. **Existing tests unbroken:** Run `pytest cloud/tests/ -v`. Verify `test_otc.py`, `test_auth.py`, `test_drugs.py`, `test_sync.py` all still pass (the audit log CHECK constraint change should not break existing OTC_DELETE usage).

4. **Manual smoke test via curl/httpie:**
   - Create a NARCOTIC drug via the drugs endpoint
   - POST narcotics-inventory (receive)
   - GET list and single
   - POST dispense
   - PUT adjust
   - POST return
   - DELETE dispose
   - Verify GET still returns the disposed item (is_active=false)
   - GET transactions and verify the full chain

5. **Legal compliance check:**
   - Confirm no physical DELETE occurs on `narcotics_inventory` or `narcotics_transactions`
   - Confirm every quantity mutation has a corresponding transaction row
   - Confirm `inventory_audit_log` captures all changes with old/new values
   - Confirm disposed items are retrievable for audit

6. **Concurrency test:** Run two simultaneous PUT requests with the same version. One should succeed, the other should return 409.

---

## 10. Implementation Sequence

1. DDL migration script (standalone, can be applied first)
2. ORM model updates in `tables.py` (2 lines)
3. Schema file `schemas/narcotics.py`
4. Service file `services/narcotics_service.py`
5. Router file `routers/narcotics.py`
6. Register router in `main.py` (1 line)
7. Test fixtures in `conftest.py`
8. Test file `tests/test_narcotics.py`
9. Update `docs/db-schema.sql` to match

Steps 3-5 can be developed together. Step 8 depends on all prior steps.
