from __future__ import annotations

"""Agent1 — 메인 폴링 루프.

Usage:
    python -m agent1.agent.main --config agent1/config.example.yaml
    python -m agent1.agent.main --help
"""

import argparse
import logging
import signal
import threading
from datetime import date, datetime, timedelta, timezone

from agent1.agent.cloud_client import CloudClient
from agent1.agent.config import load_config
from agent1.agent.interfaces.atdps_reader import ATDPSReader
from agent1.agent.interfaces.pm20_reader import PM20Reader
from agent1.agent.logging_config import setup_logging
from agent1.agent.offline_queue import OfflineQueue

logger = logging.getLogger("agent1")


class Agent1:
    def __init__(self, config_path: str):
        self.config = load_config(config_path)
        self.cloud_client = CloudClient(self.config)
        self.offline_queue = OfflineQueue(self.config)
        self.pm20_reader: PM20Reader | None = None
        self.atdps_reader: ATDPSReader | None = None
        self.rpa_manager = None
        self.tray_manager = None
        self._stop_event = threading.Event()
        self._last_drug_master_sync: datetime | None = None
        self._last_visit_proc_dtime: str | None = None

    def run(self):
        """메인 루프: config의 polling_interval_seconds 간격으로 sync 실행."""
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        logger.info(
            "Agent1 started (polling every %ds)",
            self.config.agent.polling_interval_seconds,
        )

        while not self._stop_event.is_set():
            try:
                self.sync_cycle()
            except Exception as e:
                logger.error("Sync cycle failed: %s", e)
            self._stop_event.wait(timeout=self.config.agent.polling_interval_seconds)

        # Graceful shutdown: RPA + tray
        if self.rpa_manager:
            self.rpa_manager.stop()
        if self.tray_manager:
            self.tray_manager.stop()
        logger.info("Agent1 shutting down gracefully.")

    def _handle_signal(self, signum, frame):
        logger.info("Received signal %s, stopping...", signum)
        self._stop_event.set()

    def _should_sync_drug_master(self) -> bool:
        """약품 마스터 동기화 주기 확인."""
        if self._last_drug_master_sync is None:
            return True
        interval_hours = self.config.pm20.get("drug_master_sync_interval_hours", 24)
        elapsed = datetime.now(timezone.utc) - self._last_drug_master_sync
        return elapsed.total_seconds() >= interval_hours * 3600

    def sync_cycle(self):
        """1회 동기화 사이클."""
        # 1. 오프라인 큐에 미전송 데이터가 있으면 먼저 전송
        self.offline_queue.flush(self.cloud_client)

        # 2. PM+20 동기화
        if self.pm20_reader:
            # 2a. 약품 마스터 동기화 (하루 1회)
            if self._should_sync_drug_master():
                try:
                    drugs = self.pm20_reader.read_drug_master()
                    if drugs:
                        self._sync_or_queue(
                            "drugs",
                            {
                                "drugs": [
                                    {
                                        "standard_code": d.standard_code,
                                        "name": d.name,
                                        "manufacturer": d.manufacturer,
                                        "category": d.category,
                                    }
                                    for d in drugs
                                ]
                            },
                        )
                    self._last_drug_master_sync = datetime.now(timezone.utc)
                except Exception as e:
                    logger.error("Drug master sync failed: %s", e)

            # 2b. 약품별 재고 동기화 (매 사이클)
            try:
                stock = self.pm20_reader.read_drug_stock()
                if stock:
                    self._sync_or_queue(
                        "drug-stock",
                        {
                            "items": [
                                {
                                    "drug_standard_code": s.drug_standard_code,
                                    "current_quantity": s.current_quantity,
                                    "is_narcotic": s.is_narcotic,
                                }
                                for s in stock
                            ],
                            "synced_at": datetime.now(timezone.utc).isoformat(),
                        },
                    )
            except Exception as e:
                logger.error("Drug stock sync failed: %s", e)

            # 2c. 방문 이력 동기화 (매 사이클, PROC_DTIME 증분)
            try:
                visits = self.pm20_reader.read_recent_visits(self._last_visit_proc_dtime)
                if visits:
                    self._sync_or_queue(
                        "visits",
                        {
                            "visits": [
                                {
                                    "patient_hash": v.patient_hash,
                                    "visit_date": v.visit_date.isoformat(),
                                    "prescription_days": v.prescription_days,
                                    "source": "PM20_SYNC",
                                    "drugs": [
                                        {
                                            "drug_insurance_code": d.drug_insurance_code,
                                            "quantity_dispensed": d.quantity_dispensed,
                                        }
                                        for d in v.drugs
                                    ],
                                }
                                for v in visits
                            ]
                        },
                    )
                    # Update incremental marker to max proc_dtime from this batch
                    dtime_values = [v.proc_dtime for v in visits if v.proc_dtime]
                    if dtime_values:
                        self._last_visit_proc_dtime = max(dtime_values)
            except Exception as e:
                logger.error("Visit sync failed: %s", e)

            # 2d. ATDPS 카세트 재고 (기존, read_inventory — Phase 4B에서 활성화)
            inventory = self.pm20_reader.read_inventory()
            if inventory:
                self._sync_or_queue(
                    "inventory",
                    {
                        "items": [
                            {
                                "cassette_number": item.cassette_number,
                                "drug_standard_code": item.drug_standard_code,
                                "current_quantity": item.current_quantity,
                                "quantity_source": "PM20",
                            }
                            for item in inventory
                        ]
                    },
                )

        # 3. ATDPS 카세트 매핑 읽기 (구현체 없으면 스킵)
        if self.atdps_reader and self.atdps_reader.is_available():
            mappings = self.atdps_reader.read_cassette_mappings()
            self._sync_or_queue(
                "cassette-mapping",
                {
                    "mappings": [
                        {
                            "cassette_number": m.cassette_number,
                            "drug_standard_code": m.drug_standard_code,
                            "mapping_source": "ATDPS",
                        }
                        for m in mappings
                    ]
                },
            )

    def _sync_or_queue(self, sync_type: str, data: dict):
        """Cloud 전송 시도, 실패 시 오프라인 큐에 저장."""
        try:
            self.cloud_client.post_sync(sync_type, data)
            count = len(data.get("items", data.get("mappings", data.get("drugs", data.get("visits", [])))))
            logger.info("Synced %s (%d items)", sync_type, count)
        except ConnectionError:
            logger.warning("Cloud unreachable, queuing %s", sync_type)
            self.offline_queue.enqueue(sync_type, data)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Agent1 — Pharmacy sync agent")
    parser.add_argument("--config", required=True, help="Path to config YAML file")
    return parser.parse_args()


def main():
    args = parse_args()
    config = load_config(args.config)
    setup_logging(
        log_file=config.agent.get("log_file"),
        max_bytes=config.agent.get("log_max_bytes", 10485760),
        backup_count=config.agent.get("log_backup_count", 5),
    )
    agent = Agent1(args.config)

    # PM+20 SQL Server 리더 생성
    db_type = config.pm20.get("db_type")
    if db_type == "sqlserver":
        try:
            from agent1.agent.readers.sqlserver_pm20_reader import SqlServerPM20Reader
            agent.pm20_reader = SqlServerPM20Reader(config)
            logger.info("PM20Reader initialized (SQL Server)")
        except ImportError:
            logger.warning("pymssql not installed, PM20Reader disabled")
        except Exception as e:
            logger.error("Failed to initialize PM20Reader: %s", e)

    # RPA 모듈 초기화 (P35: polling_interval from config)
    rpa_enabled = config.get_section("rpa").get("enabled", False) if config.get_section("rpa") else False
    if rpa_enabled:
        try:
            from agent1.agent.rpa.rpa_manager import RpaManager
            from agent1.agent.rpa.tray import TrayManager

            rpa_polling = config.get_section("rpa").get("polling_interval_seconds", 2)
            rpa_coords = config.get_section("rpa").get("coordinates", {})
            agent.rpa_manager = RpaManager(
                agent.cloud_client,
                polling_interval=rpa_polling,
                rpa_coordinates=rpa_coords,
            )
            agent.tray_manager = TrayManager(agent.rpa_manager)
            agent.tray_manager.start()
            logger.info("RPA module initialized (polling every %ds)", rpa_polling)
        except ImportError as e:
            logger.warning("RPA dependencies not installed: %s", e)
        except Exception as e:
            logger.error("Failed to initialize RPA: %s", e)

    agent.run()


if __name__ == "__main__":
    main()
