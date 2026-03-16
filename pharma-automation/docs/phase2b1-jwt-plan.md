# Phase 2B-1: JWT 인증 시스템

## Context

Phase 2A에서 Agent1용 API key 인증만 구현했다. 앱 사용자(약사, 직원)용 JWT 인증이 필요하다. 기존 ORM 모델(`User`, `RefreshToken`)과 DB 테이블(`users`, `refresh_tokens`)은 Phase 1 DDL에 이미 존재한다.

**목표**: 회원가입/로그인/토큰갱신/로그아웃 4개 엔드포인트 + 기존 app-dev 엔드포인트에 JWT 보호 적용 + pharmacy_id 기반 데이터 격리

---

## Design Decisions (Phase 2B-1 확정)

- **회원가입 보안**: invite_code 방식 (c) 채택. `pharmacies.invite_code VARCHAR(20)` 추가, 가입 시 필수 입력. DDL ALTER TABLE 필요.
- **Refresh token 관리**: soft delete — `is_revoked BOOLEAN DEFAULT FALSE` + `revoked_at TIMESTAMPTZ` 추가. 만료+30일 후 배치 정리. DDL ALTER TABLE 필요.
- **get_current_user DB 조회**: 매 요청 DB 조회 유지 (is_active 체크 필요). 성능 이슈 시 Phase 2C에서 Redis 캐시 도입. 코드에 트레이드오프 주석 삽입.
- **DDL 확인 완료**: users (password_hash, role, is_active) ✓, refresh_tokens (token_hash VARCHAR(128), expires_at, user_id FK) ✓ — ALTER TABLE 불필요. invite_code와 is_revoked/revoked_at만 추가 필요.

---

## 파일 목록 + 역할

| # | 파일 | 작업 | 역할 |
|---|------|------|------|
| 1 | `docs/db-schema.sql` | **수정** | pharmacies에 `invite_code` 추가, refresh_tokens에 `is_revoked`, `revoked_at` 추가 |
| 2 | `cloud/app/models/tables.py` | **수정** | Pharmacy에 `invite_code`, RefreshToken에 `is_revoked`, `revoked_at` 컬럼 추가 |
| 3 | `cloud/requirements.txt` | **수정** | `bcrypt>=4.0`, `PyJWT>=2.8` 추가 |
| 4 | `cloud/app/config.py` | **수정** | JWT 설정 4개 추가 |
| 5 | `cloud/app/schemas/auth.py` | **신규** | 인증 관련 Pydantic 스키마 |
| 6 | `cloud/app/services/auth_service.py` | **신규** | 인증 비즈니스 로직 (register, login, refresh, logout) |
| 7 | `cloud/app/routers/auth.py` | **신규** | 4개 POST 엔드포인트 |
| 8 | `cloud/app/dependencies.py` | **수정** | `get_current_user` JWT dependency 추가 (기존 `verify_api_key` 유지) |
| 9 | `cloud/app/main.py` | **수정** | auth router 등록 |
| 10 | `cloud/app/routers/alerts.py` | **수정** | JWT 적용, pharmacy_id query param 제거 |
| 11 | `cloud/app/routers/inventory.py` | **수정** | JWT 적용, pharmacy_id query param 제거 |
| 12 | `cloud/app/routers/predictions.py` | **수정** | JWT 적용, pharmacy_id query param 제거 |
| 13 | `cloud/app/services/alert_service.py` | **수정** | `mark_alert_read`에 pharmacy_id 소유권 검증 추가 |
| 14 | `cloud/tests/test_auth.py` | **신규** | JWT 인증 테스트 (21개) |
| 15 | `cloud/tests/conftest.py` | **수정** | 사용자 seed fixture + auth_headers 헬퍼 |
| 16 | `cloud/tests/test_sync.py` | **수정** | alerts/inventory/predictions 테스트에 JWT 헤더 적용 |

---

## 1. 의존성 추가 (`requirements.txt`)

```
bcrypt>=4.0
PyJWT>=2.8
```

PyJWT 선택 이유: python-jose 대비 경량, 활발한 유지보수, JWE/JWK 불필요.

---

## 2. Config 변경 (`app/config.py`)

```python
class Settings(BaseSettings):
    # 기존
    database_url: str = ...
    api_key_hash_algorithm: str = "sha256"
    # 추가
    jwt_secret_key: str = "CHANGE-ME-IN-PRODUCTION"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
```

환경변수: `PHARMA_JWT_SECRET_KEY`, `PHARMA_ACCESS_TOKEN_EXPIRE_MINUTES` 등 (기존 `PHARMA_` prefix).

---

## 3. DDL 변경

### `pharmacies` 테이블에 `invite_code` 추가
```sql
ALTER TABLE pharmacies ADD COLUMN invite_code VARCHAR(20);
-- DDL 파일(db-schema.sql)에도 반영
```

### `refresh_tokens` 테이블에 soft delete 컬럼 추가
```sql
ALTER TABLE refresh_tokens ADD COLUMN is_revoked BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE refresh_tokens ADD COLUMN revoked_at TIMESTAMPTZ;
-- DDL 파일(db-schema.sql)에도 반영
```

---

## 4. 스키마 (`app/schemas/auth.py`)

```python
class RegisterRequest(BaseModel):
    pharmacy_id: int
    invite_code: str = Field(..., min_length=1, max_length=20)  # P11: 보안
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=8)
    role: str = Field(default="STAFF", pattern="^(PHARMACIST|STAFF|ADMIN)$")

class RegisterResponse(BaseModel):
    id: int
    pharmacy_id: int
    username: str
    role: str

class LoginRequest(BaseModel):
    pharmacy_id: int
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshRequest(BaseModel):
    refresh_token: str

class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class LogoutRequest(BaseModel):
    refresh_token: str

class LogoutResponse(BaseModel):
    detail: str = "Logged out successfully"
```

---

## 5. JWT Payload 구조

**Access token** (JWT, HS256):
```json
{
  "sub": "42",               // user_id (문자열 — JWT 표준)
  "pharmacy_id": 1,          // 데이터 스코프 (매 요청 DB 조회 불필요)
  "role": "PHARMACIST",      // 향후 RBAC용
  "type": "access",          // refresh와 구분
  "exp": 1710600000,         // 발급 후 30분
  "iat": 1710598200
}
```

**Refresh token**: JWT 아님. `secrets.token_urlsafe(32)` 랜덤 문자열.
- 클라이언트에 원본 반환 (1회)
- DB에는 `hashlib.sha256(token).hexdigest()` 저장 (`refresh_tokens.token_hash`)
- 만료: 7일 (`refresh_tokens.expires_at`)

---

## 6. 서비스 (`app/services/auth_service.py`)

기존 서비스 패턴 준수: async 함수, `db: AsyncSession` 첫 번째 인자, HTTPException 직접 raise.

| 함수 | 역할 |
|------|------|
| `hash_password(password) → str` | bcrypt.hashpw |
| `verify_password(password, hash) → bool` | bcrypt.checkpw |
| `create_access_token(user_id, pharmacy_id, role) → str` | jwt.encode (30분 만료) |
| `create_refresh_token(db, user_id) → str` | secrets.token_urlsafe → SHA-256 해시 → DB INSERT (7일 만료) → 원본 반환 |
| `register_user(db, req) → RegisterResponse` | 약국 존재 확인(404) → **invite_code 검증(403)** → 중복 검사(409) → bcrypt 해시 → User INSERT |
| `login(db, req) → TokenResponse` | (pharmacy_id, username) 조회 → is_active 확인 → bcrypt 검증 → 실패 시 401 → 토큰 2개 생성 |
| `refresh_access_token(db, req) → AccessTokenResponse` | 토큰 SHA-256 → DB 조회 → **is_revoked 확인** → 만료 확인 → user 조회 + is_active → 새 access_token |
| `logout(db, req) → LogoutResponse` | 토큰 SHA-256 → **soft delete: is_revoked=True, revoked_at=now()** (멱등: 미존재 시에도 성공) |

**에러 코드**: 401(인증 실패/만료/폐기), 403(잘못된 invite_code), 404(약국 미존재), 409(중복 username), 422(Pydantic validation)

---

## 7. 엔드포인트 상세 (`app/routers/auth.py`)

### `POST /api/v1/auth/register`
```
Request:  RegisterRequest { pharmacy_id, invite_code, username, password, role? }
Response: 201 RegisterResponse { id, pharmacy_id, username, role }
Errors:   403 (invalid invite_code), 404 (pharmacy not found), 409 (duplicate username), 422 (validation)
```

### `POST /api/v1/auth/login`
```
Request:  LoginRequest { pharmacy_id, username, password }
Response: 200 TokenResponse { access_token, refresh_token, token_type }
Errors:   401 (bad credentials or inactive user)
```

### `POST /api/v1/auth/refresh`
```
Request:  RefreshRequest { refresh_token }
Response: 200 AccessTokenResponse { access_token, token_type }
Errors:   401 (expired/invalid/revoked token, inactive user)
```

### `POST /api/v1/auth/logout`
```
Request:  LogoutRequest { refresh_token }
Response: 200 LogoutResponse { detail }
(항상 성공 — 멱등)
```

`main.py` 등록:
```python
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
```

---

## 8. JWT Dependency (`app/dependencies.py`)

기존 `verify_api_key`는 그대로 유지. 새로 `get_current_user` 추가:

```python
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

_bearer_scheme = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    JWT에서 user_id를 추출하고 DB에서 사용자를 조회한다.
    # P13 트레이드오프: 매 요청 DB 조회 (is_active 실시간 검증 필요).
    # JWT payload만으로 pharmacy_id/role 확인 가능하나, 비활성화된 사용자 차단을 위해 DB 조회 유지.
    # 성능 병목 발생 시 Phase 2C에서 Redis 캐시(user_id → is_active) 도입 검토.
    """
    token = credentials.credentials
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    # ExpiredSignatureError → 401 "Token expired"
    # InvalidTokenError → 401 "Invalid token"
    # type != "access" → 401 "Invalid token type"
    user = db.execute(select(User).where(User.id == int(payload["sub"])))
    # user is None or not is_active → 401
    return user
```

`HTTPBearer` 사용 → Swagger UI에 "Authorize" 버튼 자동 제공, 헤더 누락 시 403.

---

## 9. 기존 엔드포인트 수정 범위

### 핵심 변경: `pharmacy_id` query param → JWT에서 추출

**수정 전** (3개 라우터 공통 패턴):
```python
async def get_alerts(pharmacy_id: int = Query(...), ...):
```

**수정 후**:
```python
from app.dependencies import get_current_user
from app.models.tables import User

async def get_alerts(user: User = Depends(get_current_user), ...):
    # user.pharmacy_id 사용 — 클라이언트가 pharmacy_id 지정 불가
```

### 라우터별 변경

| 라우터 | 변경 사항 |
|--------|----------|
| `alerts.py` | `get_alerts`: pharmacy_id param → `user.pharmacy_id`. `mark_alert_read`: `get_current_user` 추가 + `alert.pharmacy_id == user.pharmacy_id` 소유권 검증(403 if mismatch) |
| `inventory.py` | `get_inventory_status`: pharmacy_id param → `user.pharmacy_id` |
| `predictions.py` | `get_predictions`: pharmacy_id param → `user.pharmacy_id` |
| `sync.py` | **변경 없음** — API key 인증 유지 |

### `alert_service.mark_alert_read` 수정

```python
async def mark_alert_read(db, alert_id, pharmacy_id) -> AlertReadResponse:
    # 기존: alert_id로만 조회
    # 변경: alert.pharmacy_id == pharmacy_id 검증 추가 (불일치 시 403)
```

---

## 10. 테스트

### 10-1. `conftest.py` 추가 fixture

```python
TEST_USER_PASSWORD = "testpass123"
TEST_INVITE_CODE = "TEST-INVITE"

# seed_data에서 pharmacies.invite_code = TEST_INVITE_CODE 설정 추가

@pytest_asyncio.fixture
async def user_seed_data(seed_data):
    """테스트 약국에 테스트 사용자 생성 (invite_code로 가입), 비밀번호 반환."""
    # POST /auth/register 호출 또는 직접 DB INSERT (bcrypt 해시)
    # → return {pharmacy_id, username, password, user_id}

@pytest_asyncio.fixture
async def auth_headers(client, user_seed_data):
    """로그인 → Authorization: Bearer <token> 헤더 반환."""
    resp = await client.post("/api/v1/auth/login", json={...})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}
```

### 10-2. `test_auth.py` 신규 (21개 테스트)

| 테스트 | 검증 내용 |
|--------|----------|
| `test_register_success` | 201, 응답 필드 확인 |
| `test_register_duplicate_username` | 같은 pharmacy + username → 409 |
| `test_register_invalid_pharmacy` | 미존재 pharmacy_id → 404 |
| `test_register_invalid_invite_code` | 잘못된 invite_code → 403 |
| `test_register_weak_password` | 8자 미만 → 422 |
| `test_register_invalid_role` | 허용되지 않는 role 값 → 422 (M6) |
| `test_login_success` | access_token + refresh_token + token_type 반환 |
| `test_login_wrong_password` | 401 |
| `test_login_nonexistent_user` | 401 |
| `test_login_inactive_user` | is_active=False → 401 |
| `test_refresh_success` | 유효한 refresh_token → 새 access_token |
| `test_refresh_expired` | 만료된 refresh_token → 401 |
| `test_refresh_after_logout` | 로그아웃 후 refresh → 401 (is_revoked 검증) |
| `test_logout_success` | 200, is_revoked=True 확인, 이후 refresh 실패 |
| `test_logout_idempotent` | 이중 로그아웃 → 둘 다 200 |
| `test_jwt_protects_alerts` | Authorization 없이 GET /alerts → 403 |
| `test_jwt_protects_inventory` | Authorization 없이 GET /inventory/status → 403 |
| `test_jwt_protects_predictions` | Authorization 없이 GET /predictions → 403 |
| `test_alerts_with_jwt` | 유효 JWT → 200, 자기 약국 데이터만 |
| `test_cross_pharmacy_isolation` | 약국 A 사용자 → 약국 B 데이터 접근 불가 |
| `test_expired_access_token` | 만료된 access_token → 401 |

### 10-3. `test_sync.py` 기존 테스트 수정

```python
# 변경 전 (alerts/inventory/predictions 테스트):
resp = await client.get("/api/v1/alerts", params={"pharmacy_id": ...})

# 변경 후:
resp = await client.get("/api/v1/alerts", headers=auth_headers)
```

sync 테스트 3개는 변경 없음.

---

## 11. 구현 순서

앱이 각 단계마다 정상 동작하도록 점진적 적용:

1. `docs/db-schema.sql` + `app/models/tables.py` — DDL 변경 (invite_code, is_revoked, revoked_at)
2. `requirements.txt` — bcrypt, PyJWT 추가 + pip install
3. `config.py` — JWT 설정 추가
4. `schemas/auth.py` — 스키마 생성
5. `services/auth_service.py` — 비즈니스 로직
6. `routers/auth.py` — 엔드포인트 4개
7. `main.py` — auth router 등록 (여기까지 **기존 엔드포인트 미변경**)
8. `dependencies.py` — `get_current_user` 추가
9. `routers/alerts.py`, `inventory.py`, `predictions.py` — JWT 적용 (Breaking change)
10. `services/alert_service.py` — mark_alert_read 소유권 검증
11. `tests/conftest.py` — user fixture + invite_code seed
12. `tests/test_auth.py` — 인증 테스트 (21개)
13. `tests/test_sync.py` — 기존 테스트 JWT 헤더 적용

---

## 12. Verification (Phase 2B-1 전용)

```bash
# 1. DDL 변경 적용
sudo -u postgres psql -d pharma -c "ALTER TABLE pharmacies ADD COLUMN IF NOT EXISTS invite_code VARCHAR(20);"
sudo -u postgres psql -d pharma -c "ALTER TABLE refresh_tokens ADD COLUMN IF NOT EXISTS is_revoked BOOLEAN NOT NULL DEFAULT FALSE;"
sudo -u postgres psql -d pharma -c "ALTER TABLE refresh_tokens ADD COLUMN IF NOT EXISTS revoked_at TIMESTAMPTZ;"
# 테스트 약국에 invite_code 설정
sudo -u postgres psql -d pharma -c "UPDATE pharmacies SET invite_code='TEST-INVITE' WHERE name='테스트약국';"

# 2. 패키지 설치
pip install bcrypt PyJWT

# 3. 서버 기동
cd pharma-automation/cloud && \
PHARMA_DATABASE_URL="postgresql+asyncpg://pharma_user:pharma_pass@localhost:5432/pharma" \
PHARMA_JWT_SECRET_KEY="test-secret-key-for-dev" \
PYTHONPATH=. uvicorn app.main:app --host 0.0.0.0 --port 8000

# 4. 회원가입 (invite_code 필수)
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"pharmacy_id":1,"invite_code":"TEST-INVITE","username":"pharmacist1","password":"securepass123","role":"PHARMACIST"}'
# → 201

# 5. 잘못된 invite_code → 403
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"pharmacy_id":1,"invite_code":"WRONG","username":"test2","password":"securepass123"}'
# → 403

# 6. 로그인 → 토큰 획득
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"pharmacy_id":1,"username":"pharmacist1","password":"securepass123"}'
# → 200 {access_token, refresh_token, token_type}

# 7. JWT로 보호된 엔드포인트 접근
curl http://localhost:8000/api/v1/alerts -H "Authorization: Bearer <access_token>"
# → 200

# 8. JWT 없이 접근 → 403
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/alerts
# → 403

# 9. 토큰 갱신
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" -d '{"refresh_token":"<refresh_token>"}'
# → 200

# 10. 로그아웃 (soft delete 확인)
curl -X POST http://localhost:8000/api/v1/auth/logout \
  -H "Content-Type: application/json" -d '{"refresh_token":"<refresh_token>"}'
# → 200, DB에서 is_revoked=TRUE, revoked_at 설정됨

# 11. 전체 pytest
cd pharma-automation/cloud && \
PHARMA_DATABASE_URL="postgresql+asyncpg://pharma_user:pharma_pass@localhost:5432/pharma" \
PHARMA_JWT_SECRET_KEY="test-secret-key-for-dev" \
PYTHONPATH=. python -m pytest tests/ -v
# → 전체 통과 (기존 7개 수정 + 신규 21개 = 28개)
```
