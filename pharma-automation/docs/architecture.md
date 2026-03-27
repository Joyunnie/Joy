# Pharmacy Inventory & Prescription Automation - Architecture

## 1. Component Interaction

```mermaid
graph TB
    subgraph Pharmacy["약국 (Local)"]
        PM20["PM+20 EMR<br/>(MariaDB)"]
        ATDPS["ATDPS<br/>(자동정제분포기)"]
        Agent1["Agent1<br/>(Windows Service)"]
    end

    subgraph Cloud["Cloud"]
        Backend["Cloud Backend<br/>(REST API)"]
        PG["PostgreSQL"]
        Batch["Batch Processor<br/>(매일 새벽)"]
    end

    App["Mobile App"]

    Agent1 -->|"REST + API Key<br/>5분 폴링"| Backend
    Agent1 -->|"카세트 매핑 읽기"| ATDPS
    Agent1 -->|"재고 수량 읽기<br/>(MariaDB)"| PM20
    Backend --> PG
    Batch --> PG
    Backend -->|"WebSocket<br/>(앱 내 알림)"| App
```

## 2. Data Flow

```mermaid
flowchart LR
    subgraph Sources["Data Sources"]
        ATDPS["ATDPS Program<br/>(카세트 매핑)"]
        PM20["PM+20 MariaDB<br/>(재고 수량)"]
    end

    Agent1["Agent1"]

    subgraph Cloud["Cloud PostgreSQL"]
        PI["prescription_inventory"]
        PVH["patient_visit_history"]
        VD["visit_drugs"]
        VP["visit_predictions"]
    end

    SQLite["SQLite Queue<br/>(offline buffer)"]

    ATDPS -->|"매핑 동기화"| Agent1
    PM20 -->|"수량 동기화"| Agent1
    Agent1 -->|"5분 폴링<br/>REST POST"| PI
    Agent1 -->|"조제 이벤트"| PVH
    Agent1 -->|"약품별 수량"| VD
    Agent1 -.->|"네트워크 끊김"| SQLite
    SQLite -.->|"복구 시<br/>batch POST"| Cloud
    PVH -->|"매일 새벽 배치"| VP
```

## 3. Network Topology

```mermaid
graph LR
    subgraph Pharmacy["약국 네트워크"]
        PC["Agent1 PC<br/>(Windows)"]
        PM20["PM+20 서버"]
        ATDPS["ATDPS 기계"]
        PC --- PM20
        PC --- ATDPS
    end

    Internet((Internet))

    subgraph Cloud["Cloud"]
        LB["Load Balancer"]
        API["API Server"]
        DB["PostgreSQL 16"]
        LB --> API --> DB
    end

    Pharmacy -->|"HTTPS"| Internet -->|"HTTPS"| Cloud

    Phone["Mobile App"] -->|"WSS"| Internet
```

## 4. OCR + RPA Sequence

```mermaid
sequenceDiagram
    participant Rx as 처방전
    participant OCR as OCR Engine
    participant Map as 약품 매핑
    participant ATDPS as ATDPS 조제
    participant Cloud as Cloud DB

    Rx->>OCR: 이미지 입력
    OCR->>OCR: 텍스트 추출
    OCR->>Map: 약품명 매칭
    Map->>Map: drugs 테이블 조회
    Map->>ATDPS: 조제 명령
    ATDPS->>ATDPS: 물리적 배출
    ATDPS->>Cloud: patient_visit_history 기록
    ATDPS->>Cloud: visit_drugs 기록
    Cloud->>Cloud: prescription_ocr_records 저장
    Cloud->>Cloud: prescription_ocr_drugs 저장
```

## 5. ATDPS Cassette & Visit Alert Flow

```mermaid
flowchart TD
    subgraph Sync["Agent1 동기화 (5분)"]
        A1["ATDPS 카세트 매핑 읽기"]
        A2["PM+20 재고 수량 읽기"]
        A3["Cloud prescription_inventory 갱신"]
        A1 --> A3
        A2 --> A3
    end

    subgraph StockCheck["재고 확인"]
        B1["drug_thresholds 조회"]
        B2{"재고 < min_quantity?"}
        B3["LOW_STOCK 알림 생성"]
        A3 --> B1 --> B2
        B2 -->|"Yes"| B3
    end

    subgraph Dispense["조제 완료"]
        C1["patient_visit_history 기록"]
        C2["visit_drugs 기록"]
    end

    subgraph Batch["매일 새벽 Cloud 배치"]
        D1["전체 활성 환자 스캔"]
        D2["방법1: last_visit_date +<br/>prescription_days = predicted_visit_date"]
        D3["방법2: 최근 N회 방문<br/>간격 평균 (옵션)"]
        D4["alert_date = predicted_visit_date -<br/>COALESCE(override, default_alert_days_before)"]
        D5{"오늘 >= alert_date?"}
        D6["VISIT_APPROACHING 앱 내 알림"]
        D7["visit_drugs로 필요 약품 확인<br/>→ 재고 부족 사전 경고"]
        D1 --> D2
        D1 --> D3
        D2 --> D4
        D3 --> D4
        D4 --> D5
        D5 -->|"Yes"| D6
        D6 --> D7
    end
```

## Design Decisions (Phase 1)

| 항목 | 결정 |
|------|------|
| Agent1 ↔ Cloud 인증 | API key (`pharmacies.api_key_hash`) |
| 폴링 주기 | 5분 (configurable) |
| 동기화 방향 | ATDPS(매핑) + PM+20(수량) → Cloud 단방향 |
| visit_predictions 생성 | Cloud 매일 새벽 배치 |
| 알림 채널 | 앱 내 알림만 (`IN_APP`) |
| 재고 source of truth | PM+20 로컬 MariaDB |
| 카세트 매핑 출처 | ATDPS 프로그램 |

## Undecided / Phase 2

- deployment strategy, monitoring, error handling 세부
- RPA 구현 상세, scheduling (cron vs OS scheduler)
- prescription_days 최대값 한계 대안: per-drug 예측 → 약별로 visit_date + 해당약 처방일수로 재고 예측 (현재는 max 기반)
- optimistic locking 충돌 재시도: 3회, 100ms backoff, 초과 시 에러
