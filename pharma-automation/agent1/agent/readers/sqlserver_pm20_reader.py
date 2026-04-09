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

# TEMP_STOCK.DRUG_CODE(nvarchar 18)와 DA_Goods.Goods_code(nvarchar 10)의
# 타입 불일치 가능. LTRIM/RTRIM 적용하고, JOIN 실패 행은 로깅 후 스킵.
SQL_DRUG_STOCK = """
SELECT
    g.Goods_RegNo    AS standard_code,
    g.Goods_Name     AS drug_name,
    ts.MDCN_MQTY     AS current_quantity,
    CASE WHEN md.DRUGCODE IS NOT NULL THEN 1 ELSE 0 END AS is_narcotic
FROM TEMP_STOCK ts
    INNER JOIN DA_Goods g ON LTRIM(RTRIM(ts.DRUG_CODE)) = LTRIM(RTRIM(g.Goods_code))
    LEFT JOIN CD_MINDRUG md ON LTRIM(RTRIM(ts.DRUG_CODE)) = LTRIM(RTRIM(md.DRUGCODE))
WHERE g.Goods_RegNo IS NOT NULL AND g.Goods_RegNo <> ''
"""

SQL_DRUG_MASTER = """
SELECT
    g.Goods_RegNo    AS standard_code,
    g.Goods_Name     AS name,
    g.Goods_Company  AS manufacturer,
    CASE WHEN md.DRUGCODE IS NOT NULL THEN 'NARCOTIC'
         ELSE 'PRESCRIPTION'
    END AS category,
    ts.DRUG_CODE     AS insurance_code
FROM DA_Goods g
    LEFT JOIN CD_MINDRUG md ON LTRIM(RTRIM(g.Goods_code)) = LTRIM(RTRIM(md.DRUGCODE))
    LEFT JOIN TEMP_STOCK ts ON LTRIM(RTRIM(g.Goods_code)) = LTRIM(RTRIM(ts.DRUG_CODE))
WHERE g.Goods_RegNo IS NOT NULL AND g.Goods_RegNo <> ''
"""

# PreState = '1': 조제완료만 동기화
SQL_RECENT_VISITS = """
SELECT
    m.Preserial,
    m.CusCode,
    m.Indate,
    m.Tdays,
    sp.Inv_Quan       AS quantity_dispensed,
    g.Goods_RegNo     AS standard_code
FROM DA_Main m
    INNER JOIN DA_SUB_PHARM sp ON m.Preserial = sp.Preserial
    INNER JOIN DA_Goods g ON sp.Goods_Code = g.Goods_code
WHERE m.Indate >= %s
    AND m.PreState = '1'
ORDER BY m.Preserial
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
        """TEMP_STOCK + DA_Goods JOIN: 약품별 현재 재고."""
        rows = self._execute_query(SQL_DRUG_STOCK)
        items = []
        for row in rows:
            try:
                std_code = row["standard_code"]
                if not std_code:
                    raise ValueError("empty standard_code")
                items.append(DrugStockItem(
                    drug_standard_code=std_code.strip(),
                    drug_name=row["drug_name"].strip() if row["drug_name"] else "",
                    current_quantity=float(row["current_quantity"] or 0),
                    is_narcotic=bool(row["is_narcotic"]),
                ))
            except (KeyError, TypeError, ValueError, AttributeError) as e:
                # JOIN 실패 또는 데이터 이상 행은 로깅 후 스킵
                logger.warning("Skipping drug_stock row due to data error: %s (row=%s)", e, row)
        return items

    def read_drug_master(self) -> list[DrugMasterItem]:
        """DA_Goods + CD_MINDRUG: 약품 마스터."""
        rows = self._execute_query(SQL_DRUG_MASTER)
        items = []
        for row in rows:
            try:
                insurance_code_raw = row.get("insurance_code")
                insurance_code = insurance_code_raw.strip() if insurance_code_raw else None
                items.append(DrugMasterItem(
                    standard_code=row["standard_code"].strip(),
                    name=row["name"].strip() if row["name"] else "",
                    manufacturer=row["manufacturer"].strip() if row.get("manufacturer") else None,
                    # TODO: Goods_Gubun 값 확인 후 OTC 카테고리 매핑 추가
                    category=row["category"],
                    insurance_code=insurance_code,
                ))
            except (KeyError, TypeError, ValueError) as e:
                logger.warning("Skipping drug_master row due to data error: %s (row=%s)", e, row)
        return items

    def read_recent_visits(self, since: date) -> list[VisitRecord]:
        """DA_Main + DA_SUB_PHARM: 조제완료(PreState='1') 방문 이력."""
        since_str = since.strftime("%Y%m%d")
        rows = self._execute_query(SQL_RECENT_VISITS, (since_str,))

        # Preserial별로 그룹핑
        groups: dict[str, dict] = defaultdict(lambda: {
            "cuscode": "",
            "indate": "",
            "tdays": 0,
            "drugs": [],
        })

        for row in rows:
            preserial = row["Preserial"]
            g = groups[preserial]
            g["cuscode"] = row["CusCode"] or ""
            g["indate"] = row["Indate"] or ""
            tdays = row["Tdays"] or 0
            if tdays > g["tdays"]:
                g["tdays"] = tdays

            std_code = (row.get("standard_code") or "").strip()
            if std_code:
                qty = int(row.get("quantity_dispensed") or 0)
                g["drugs"].append(DrugDispensed(
                    drug_standard_code=std_code,
                    quantity_dispensed=qty,
                ))

        visits = []
        for g in groups.values():
            indate = g["indate"]
            if len(indate) != 8:
                continue
            try:
                visit_date = date(int(indate[:4]), int(indate[4:6]), int(indate[6:8]))
            except ValueError:
                continue

            visits.append(VisitRecord(
                patient_hash=self._hash_patient(g["cuscode"]),
                visit_date=visit_date,
                prescription_days=g["tdays"],
                drugs=g["drugs"],
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
