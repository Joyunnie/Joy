"""Agent1 — 메인 폴링 루프.

Usage:
    python -m agent1.agent.main --config agent1/config.example.yaml
    python -m agent1.agent.main --help
"""

import argparse
import logging
import signal
import threading

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
        self._stop_event = threading.Event()

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

        logger.info("Agent1 shutting down gracefully.")

    def _handle_signal(self, signum, frame):
        logger.info("Received signal %s, stopping...", signum)
        self._stop_event.set()

    def sync_cycle(self):
        """1회 동기화 사이클."""
        # 1. 오프라인 큐에 미전송 데이터가 있으면 먼저 전송
        self.offline_queue.flush(self.cloud_client)

        # 2. PM+20 재고 읽기 (구현체 없으면 스킵)
        if self.pm20_reader:
            inventory = self.pm20_reader.read_inventory()
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
            logger.info("Synced %s (%d items)", sync_type, len(data.get("items", data.get("mappings", []))))
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
    agent.run()


if __name__ == "__main__":
    main()
