from __future__ import annotations

r"""PM+20 SQL Server 구현체.

SQL Server 인스턴스 .\PMPLUS20, 데이터베이스 PM_MAIN에서
약품 마스터, 재고, 방문 이력을 읽는다.
"""

import hashlib
import logging
import os
from collections import defaultdict
from datetime import date

import pymssql

from agent1.agent.config import AgentConfig
from agent1.agent.interfaces.pm20_reader import (
    DrugDispensed,
    DrugMasterItem,
    DrugStockItem,
    InventoryItem,
    PM20Reader,
    VisitRecord,
)

logger = logging.getLogger("agent1.pm20_reader")

# TEMP_STOCK.DRUG_CODE = 건강보험 약품코드 (nvarchar 18)
# TBSIM040_01.DRUG_CODE = 건강보험 약품코드 마스터 (nvarchar 18)
# TRIM only the small-table side (TEMP_STOCK) — leave TBSIM040_01 (186K rows) unwrapped
# so SQL Server can use its index on DRUG_CODE.
SQL_DRUG_STOCK = """
SELECT
    ts.DRUG_CODE        AS insurance_code,
    m.ARTCNM            AS drug_name,
    ts.MDCN_MQTY        AS current_quantity
FROM TEMP_STOCK ts
    INNER JOIN TBSIM040_01 m ON LTRIM(RTRIM(ts.DRUG_CODE)) = m.DRUG_CODE
WHERE ts.DRUG_CODE IS NOT NULL AND ts.DRUG_CODE <> ''
"""

SQL_DRUG_MASTER = """
SELECT
    m.DRUG_CODE       AS insurance_code,
    m.ARTCNM          AS name,
    m.MNF_CO_NM       AS manufacturer,
    m.TITLECODE       AS standard_code,
    CASE WHEN md.DRUGCODE IS NOT NULL THEN 'NARCOTIC'
         ELSE 'PRESCRIPTION'
    END AS category
FROM (SELECT DISTINCT DRUG_CODE FROM TBSID040_04) d
    INNER JOIN TBSIM040_01 m ON d.DRUG_CODE = m.DRUG_CODE
    LEFT JOIN CD_MINDRUG md ON m.TITLECODE = md.DRUGCODE
ORDER BY m.DRUG_CODE
"""

# TBSID040_03 + TBSID040_04: 조제완료 방문 이력
# PRES_PRGRS_STATE='3': 조제완료, PRES_GUBUN != 'E': 재고조정 제외
# PROC_DTIME 기반 증분 동기화 (ASC 정렬 → 마지막 값이 다음 마커)
SQL_RECENT_VISITS = """
SELECT
    h.DRUG_SEQ         AS serial,
    h.CHRTNO           AS patient_code,
    h.MPRSC_GRANT_DT   AS visit_date,
    h.TOT_DD_CNT       AS prescription_days,
    h.PROC_DTIME       AS proc_datetime,
    d.DRUG_CODE        AS drug_code,
    d.MDCN_MQTY        AS quantity_dispensed
FROM TBSID040_03 h
    INNER JOIN TBSID040_04 d ON h.DRUG_SEQ = d.DRUG_SEQ
WHERE h.PRES_PRGRS_STATE = '3'
    AND h.PRES_GUBUN != 'E'
    AND h.PROC_DTIME > %s
ORDER BY h.PROC_DTIME ASC
"""


class SqlServerPM20Reader(PM20Reader):
    """SQL Server PM+20 구현체."""

    def __init__(self, config: AgentConfig):
        self._config = config
        self._conn = None

        # SQL Server 접속 정보
        self._instance = config.pm20.get("instance", r".\PMPLUS20")
        self._database = config.pm20.get("database", "PM_MAIN")
        self._auth = config.pm20.get("auth", "windows")

        # Patient hash salt (환경변수 우선)
        salt_env = config.pm20.get("patient_hash_salt_env")
        if salt_env:
            self._patient_hash_salt = os.environ.get(salt_env, "")
        else:
            self._patient_hash_salt = config.pm20.get("patient_hash_salt", "")

    def _get_connection(self):
        """pymssql 연결 반환. 끊어졌으면 재연결."""
        if self._conn is not None:
            try:
                cursor = self._conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                return self._conn
            except Exception:
                self._conn = None

        kwargs = {
            "server": self._instance,
            "database": self._database,
            "charset": "utf8",
        }

        if self._auth == "sql":
            kwargs["user"] = self._config.pm20.get("username", "sa")
            pw_env = self._config.pm20.get("password_env", "PM20_DB_PASSWORD")
            kwargs["password"] = os.environ.get(pw_env, "")
        # Windows auth: pymssql uses current Windows credentials when no user/password

        self._conn = pymssql.connect(**kwargs)
        logger.info("Connected to SQL Server %s/%s", self._instance, self._database)
        return self._conn

    def _execute_query(self, sql: str, params=None) -> list[dict]:
        """쿼리 실행 후 dict 리스트 반환."""
        conn = self._get_connection()
        cursor = conn.cursor(as_dict=True)
        cursor.execute(sql, params)
        return cursor.fetchall()

    def _hash_patient(self, cuscode: str) -> str:
        """SHA-256(CusCode + patient_hash_salt)."""
        raw = (cuscode or "") + self._patient_hash_salt
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    # --- ABC 구현 ---

    def read_inventory(self) -> list[InventoryItem]:
        """ATDPS 카세트 기반 재고. ATDPS 미연동이므로 빈 리스트."""
        return []

    def read_drug_stock(self) -> list[DrugStockItem]:
        """TEMP_STOCK + TBSIM040_01 JOIN: 약품별 현재 재고."""
        rows = self._execute_query(SQL_DRUG_STOCK)
        items = []
        for row in rows:
            try:
                ins_code = row["insurance_code"]
                if not ins_code:
                    raise ValueError("empty insurance_code")
                items.append(DrugStockItem(
                    drug_insurance_code=ins_code.strip(),
                    drug_name=row["drug_name"].strip() if row["drug_name"] else "",
                    current_quantity=float(row["current_quantity"] or 0),
                ))
            except (KeyError, TypeError, ValueError, AttributeError) as e:
                logger.warning("Skipping drug_stock row due to data error: %s (row=%s)", e, row)
        return items

    def read_drug_master(self) -> list[DrugMasterItem]:
        """TBSID040_04 + TBSIM040_01: actually-dispensed prescription drug master."""
        rows = self._execute_query(SQL_DRUG_MASTER)
        items = []
        seen_codes: set[str] = set()  # deduplicate (3 DRUG_CODEs have 2 rows in TBSIM040_01)
        for row in rows:
            try:
                ins_code = (row.get("insurance_code") or "").strip()
                if not ins_code or ins_code in seen_codes:
                    continue
                seen_codes.add(ins_code)
                std_code = (row.get("standard_code") or "").strip()
                items.append(DrugMasterItem(
                    standard_code=std_code if std_code else None,
                    name=row["name"].strip() if row.get("name") else "",
                    manufacturer=row["manufacturer"].strip() if row.get("manufacturer") else None,
                    category=row["category"],
                    insurance_code=ins_code,
                ))
            except (KeyError, TypeError, ValueError) as e:
                logger.warning("Skipping drug_master row: %s", e)
        logger.info("Drug master: %d items loaded (all with insurance_code)", len(items))
        return items

    def read_recent_visits(self, since_marker: str | None = None) -> list[VisitRecord]:
        """TBSID040_03 + TBSID040_04: 조제완료 방문 이력.

        Args:
            since_marker: PROC_DTIME 증분 마커. None이면 '20260101000000' 사용.
        """
        if since_marker is None:
            since_marker = "20260101000000"
        rows = self._execute_query(SQL_RECENT_VISITS, (since_marker,))

        # DRUG_SEQ별로 그룹핑 (하나의 DRUG_SEQ = 하나의 조제 건)
        groups: dict[str, dict] = defaultdict(lambda: {
            "patient_code": "",
            "visit_date_str": "",
            "prescription_days": 0,
            "proc_dtime": "",
            "drugs": [],
        })

        for row in rows:
            serial = row["serial"]
            patient_code = (row.get("patient_code") or "").strip()

            # Skip empty patient codes
            if not patient_code:
                continue

            g = groups[serial]
            g["patient_code"] = patient_code
            g["visit_date_str"] = row.get("visit_date") or ""
            tdays = row.get("prescription_days") or 0
            if tdays > g["prescription_days"]:
                g["prescription_days"] = tdays
            g["proc_dtime"] = row.get("proc_datetime") or ""

            drug_code = (row.get("drug_code") or "").strip()

            # Skip internal adjustment codes (ZP prefix) and empty codes
            if not drug_code or drug_code.startswith("ZP"):
                continue

            qty = int(row.get("quantity_dispensed") or 0)
            g["drugs"].append(DrugDispensed(
                drug_insurance_code=drug_code,
                quantity_dispensed=qty,
            ))

        visits = []
        for g in groups.values():
            visit_date_str = g["visit_date_str"]
            if len(visit_date_str) != 8:
                continue
            try:
                visit_date = date(
                    int(visit_date_str[:4]),
                    int(visit_date_str[4:6]),
                    int(visit_date_str[6:8]),
                )
            except ValueError:
                continue

            prescription_days = g["prescription_days"] or 1  # default to 1 if zero/null

            visits.append(VisitRecord(
                patient_hash=self._hash_patient(g["patient_code"]),
                visit_date=visit_date,
                prescription_days=prescription_days,
                drugs=g["drugs"],
                proc_dtime=g["proc_dtime"],
            ))

        return visits

    def close(self):
        """연결 종료."""
        if self._conn:
            try:
                self._conn.close()
            except pymssql.Error:
                logger.debug("Error closing SQL Server connection (ignored)")
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
