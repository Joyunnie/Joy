# DEPLOYMENT.md — Operations Reference

## 1. Architecture Overview

| Component | Host | Role |
|-----------|------|------|
| Cloud Server | Mac Mini M4 | Docker host — FastAPI + PostgreSQL + Frontend (nginx) |
| Pharmacy PC (Front PC) | Windows | PM+20 EMR, GoodPharm, PAM-Pro, SQL Server `.\PMPLUS20` |
| Notebook | Windows | ATDPS program (`C:\PAM-Pro\`), JVM JV-156DOC20 |

**Network**
- External IP: `220.71.178.7`
- Internal IP (Mac Mini): `192.168.0.42`
- iptime port forwarding: `80` (frontend), `8000` (API)

---

## 2. Cloud Server (Mac Mini)

### Docker

```bash
# 기동 (빌드 포함)
docker compose up --build -d

# 중지
docker compose down

# 업데이트 배포
git pull && docker compose up --build -d

# 로그 확인
docker compose logs -f cloud
docker compose logs -f db
```

**컨테이너명**
- `pharma-automation-db-1`
- `pharma-automation-cloud-1`
- `pharma-automation-frontend-1`

### DB 직접 접속

```bash
docker exec -it pharma-automation-db-1 psql -U pharma_user -d pharma
```

### Alembic

cloud 컨테이너 시작 시 `alembic upgrade head` 자동 실행.
**스키마 변경은 반드시 alembic migration으로만** — DDL 직접 실행 금지.

```bash
# 새 migration 생성 (cloud 컨테이너 내부 또는 로컬)
alembic revision --autogenerate -m "description"
alembic upgrade head
```

---

## 3. Environment Variables (.env)

파일 위치: `pharma-automation/cloud/.env` (git 커밋 금지)

```env
POSTGRES_PASSWORD=<DB 비밀번호>
PHARMA_JWT_SECRET_KEY=<JWT 서명 키>
PHARMA_INVITE_CODE=<회원가입 초대코드>
```

> `.env`는 절대 git에 커밋하지 않는다.

---

## 4. Database

- **Engine**: PostgreSQL 16
- **DB**: `pharma`
- **User**: `pharma_user`

**주요 레코드**

| 항목 | 값 |
|------|----|
| 약국 record | `id=7`, `name=튼튼약국` |
| 앱 계정 | `username=jw` / `password=12341234` |
| Agent1 API 키 | SHA-256 해시로 `pharmacies.api_key_hash`에 저장 |

---

## 5. Agent1 (약국 PC)

### 설치 정보

| 항목 | 값 |
|------|----|
| 설치 경로 | `C:\pharma-agent` |
| Python | 3.14.3 (PATH 등록됨) |
| Config | `C:\pharma-agent\agent1\config.yaml` |
| Cloud endpoint | `http://220.71.178.7:8000` |
| 코드 업데이트 | GitHub에서 ZIP 다운로드 (약국 PC에 Git 미설치) |

### SQL Server 계정 (읽기 전용)

```
계정: agent1_reader
비밀번호: Ag3nt1!Read2024
인스턴스: .\PMPLUS20
```

### 환경변수 (setx — 영구 설정)

```bat
setx PM20_DB_PASSWORD "Ag3nt1!Read2024"
setx PM20_HASH_SALT "pharma-auto-salt-2024"
setx PHARMA_API_KEY "31b963d9f12985fa369d0e73d54c47581a08e737022dc25b5ba287f1ca7ba025"
```

> **PYTHONPATH**는 `setx`로 설정해도 Windows 서비스에 반영되지 않는다.
> NSSM `AppEnvironmentExtra`에 직접 설정 → `install_service.bat`이 처리함.

### 수동 실행 (테스트용)

```bat
set PYTHONPATH=C:\pharma-agent
python -m agent1.agent.main --config C:\pharma-agent\agent1\config.yaml
```

### Windows 서비스 (PharmaAgent1)

```bat
# 설치 (관리자 권한)
agent1\scripts\install_service.bat

# 제거 (관리자 권한)
agent1\scripts\uninstall_service.bat

# 상태 확인
sc query PharmaAgent1

# 로그
C:\pharma-agent\agent1\logs\service.log
```

---

## 6. API Authentication

| 클라이언트 | 방식 |
|-----------|------|
| Frontend 사용자 | JWT — `/api/v1/auth/` 로그인 후 Bearer 토큰 |
| Agent1 | `X-API-Key` 헤더 → SHA-256 해시 → `pharmacies.api_key_hash` 대조 |

**Agent1 API Key**
```
31b963d9f12985fa369d0e73d54c47581a08e737022dc25b5ba287f1ca7ba025
```

> API 키는 반드시 ASCII/영문만 사용. 한글 포함 시 HTTP 헤더 latin-1 인코딩 오류 발생.

---

## 7. Frontend

- React 18 TypeScript PWA
- nginx Docker 컨테이너로 서빙 (`port 80`)
- **탭 구성**: 대시보드, 처방전, 재고, 투두, 방문 예측, 알림

---

## 8. Troubleshooting

| 증상 | 원인 | 해결 |
|------|------|------|
| Agent1 `'latin-1' codec can't encode` | `PHARMA_API_KEY`에 비ASCII 문자 포함 | ASCII 전용 키로 교체 |
| Agent1 `ModuleNotFoundError: No module named 'agent1'` | `PYTHONPATH` 미설정 | 서비스: `install_service.bat` 재실행 / 수동: `set PYTHONPATH=C:\pharma-agent` |
| Agent1 SQL Server 로그인 실패 (Error 18456) | `PM20_DB_PASSWORD` 환경변수 미설정 또는 세션 미반영 | `setx` 후 새 cmd 창에서 실행, 서비스는 재시작 |
| Cloud API `401 Unauthorized` | API 키 미등록 또는 해시 불일치 | `pharmacies` 테이블의 `api_key_hash` 확인 |
| Cloud API `500` after migration | alembic 미적용 | `docker compose up --build -d` (자동 upgrade) 또는 수동 `alembic upgrade head` |
