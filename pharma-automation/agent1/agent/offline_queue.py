from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone

logger = logging.getLogger("agent1.offline_queue")

MAX_RETRY_COUNT = 100


class OfflineQueue:
    """Offline SQLite queue for storing sync payloads when Cloud is unreachable."""

    def __init__(self, config: dict | object):
        if isinstance(config, dict):
            agent_cfg = config.get("agent", {})
            db_path = agent_cfg.get("sqlite_queue_path", "sync_queue.db")
            self.max_queue_items = agent_cfg.get("max_queue_items", 10000)
        else:
            db_path = config.agent.get("sqlite_queue_path", "sync_queue.db")
            self.max_queue_items = config.agent.get("max_queue_items", 10000)

        self.conn = sqlite3.connect(db_path)
        self._init_table()

    def _init_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sync_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                retry_count INTEGER DEFAULT 0
            )
        """)
        self.conn.commit()

    def enqueue(self, sync_type: str, data: dict):
        """Add item to queue. Evicts oldest if over max_queue_items."""
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "INSERT INTO queue (sync_type, payload, created_at) VALUES (?, ?, ?)",
            (sync_type, json.dumps(data), now),
        )
        self.conn.commit()

        # Evict oldest if over limit
        count = self.pending_count()
        if count > self.max_queue_items:
            overflow = count - self.max_queue_items
            self.conn.execute(
                "DELETE FROM queue WHERE id IN (SELECT id FROM queue ORDER BY id ASC LIMIT ?)",
                (overflow,),
            )
            self.conn.commit()
            logger.critical("Queue overflow: deleted %d oldest items (max: %d)", overflow, self.max_queue_items)

    def flush(self, client) -> int:
        """Send all queued items via client. Returns number of successfully sent items."""
        cursor = self.conn.execute("SELECT id, sync_type, payload, retry_count FROM queue ORDER BY id ASC")
        rows = cursor.fetchall()
        sent = 0

        for row_id, sync_type, payload_str, retry_count in rows:
            try:
                data = json.loads(payload_str)
                client.post_sync(sync_type, data)
                self.conn.execute("DELETE FROM queue WHERE id = ?", (row_id,))
                self.conn.commit()
                sent += 1
            except Exception:
                new_count = retry_count + 1
                if new_count > MAX_RETRY_COUNT:
                    logger.critical(
                        "Queue item %d exceeded max retries (%d), deleting (data loss)",
                        row_id, MAX_RETRY_COUNT,
                    )
                    self.conn.execute("DELETE FROM queue WHERE id = ?", (row_id,))
                else:
                    self.conn.execute(
                        "UPDATE queue SET retry_count = ? WHERE id = ?",
                        (new_count, row_id),
                    )
                self.conn.commit()
                break  # Stop on first failure to maintain FIFO order

        return sent

    def pending_count(self) -> int:
        cursor = self.conn.execute("SELECT COUNT(*) FROM queue")
        return cursor.fetchone()[0]
