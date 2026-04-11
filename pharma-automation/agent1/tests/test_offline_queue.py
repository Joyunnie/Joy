"""Tests for OfflineQueue: enqueue, flush, eviction, context manager, close.

Covers: happy path FIFO ordering, max retry eviction, overflow eviction,
context manager protocol, close idempotency, and flush error handling.
"""
import os
import tempfile
from unittest.mock import MagicMock

import pytest

from agent1.agent.offline_queue import MAX_RETRY_COUNT, OfflineQueue


@pytest.fixture
def queue_path(tmp_path):
    """Return a temp file path for SQLite DB."""
    return str(tmp_path / "test_queue.db")


@pytest.fixture
def queue(queue_path):
    """Create a fresh OfflineQueue with small max."""
    q = OfflineQueue({"agent": {"sqlite_queue_path": queue_path, "max_queue_items": 5}})
    yield q
    q.close()


class TestEnqueueAndFlush:
    """Basic enqueue/flush behavior."""

    def test_enqueue_and_pending_count(self, queue):
        assert queue.pending_count() == 0
        queue.enqueue("inventory", {"items": []})
        assert queue.pending_count() == 1
        queue.enqueue("inventory", {"items": [1, 2]})
        assert queue.pending_count() == 2

    def test_flush_sends_all_items_in_fifo_order(self, queue):
        queue.enqueue("inventory", {"order": 1})
        queue.enqueue("inventory", {"order": 2})
        queue.enqueue("visits", {"order": 3})

        sent_types = []
        mock_client = MagicMock()
        mock_client.post_sync.side_effect = lambda t, d: sent_types.append(t)

        count = queue.flush(mock_client)
        assert count == 3
        assert sent_types == ["inventory", "inventory", "visits"]
        assert queue.pending_count() == 0

    def test_flush_empty_queue_returns_zero(self, queue):
        mock_client = MagicMock()
        assert queue.flush(mock_client) == 0
        mock_client.post_sync.assert_not_called()

    def test_flush_preserves_json_payload(self, queue):
        payload = {"items": [{"code": "KD123", "qty": 50.5}]}
        queue.enqueue("inventory", payload)

        received = []
        mock_client = MagicMock()
        mock_client.post_sync.side_effect = lambda t, d: received.append(d)

        queue.flush(mock_client)
        assert received == [payload]


class TestFlushErrorHandling:
    """Flush behavior when client.post_sync raises."""

    def test_flush_stops_on_first_failure(self, queue):
        """FIFO guarantee: stops on first failure, doesn't skip."""
        queue.enqueue("a", {"i": 1})
        queue.enqueue("b", {"i": 2})
        queue.enqueue("c", {"i": 3})

        mock_client = MagicMock()
        mock_client.post_sync.side_effect = [None, ConnectionError("offline"), None]

        count = queue.flush(mock_client)
        assert count == 1  # Only first item sent
        assert queue.pending_count() == 2  # b and c remain

    def test_retry_count_increments_on_failure(self, queue):
        queue.enqueue("test", {"x": 1})

        mock_client = MagicMock()
        mock_client.post_sync.side_effect = ConnectionError("fail")

        queue.flush(mock_client)
        # Item still in queue with retry_count=1
        assert queue.pending_count() == 1

        # Flush again — retry_count increments to 2
        queue.flush(mock_client)
        assert queue.pending_count() == 1

    def test_item_deleted_after_max_retries(self, queue):
        """Items exceeding MAX_RETRY_COUNT are deleted (data loss)."""
        queue.enqueue("stuck", {"x": 1})

        # Manually set retry_count to MAX_RETRY_COUNT
        queue.conn.execute(
            "UPDATE queue SET retry_count = ? WHERE id = 1",
            (MAX_RETRY_COUNT,),
        )
        queue.conn.commit()

        mock_client = MagicMock()
        mock_client.post_sync.side_effect = ConnectionError("fail")

        queue.flush(mock_client)
        # Item should be deleted after exceeding max retries
        assert queue.pending_count() == 0


class TestOverflowEviction:
    """Queue overflow: oldest items evicted when over max_queue_items."""

    def test_evicts_oldest_when_over_max(self, queue):
        """max_queue_items=5; adding 7 items evicts 2 oldest."""
        for i in range(7):
            queue.enqueue("test", {"seq": i})

        assert queue.pending_count() == 5

        # Verify oldest were evicted: flush and check seq values
        received = []
        mock_client = MagicMock()
        mock_client.post_sync.side_effect = lambda t, d: received.append(d["seq"])

        queue.flush(mock_client)
        # Items 0 and 1 were evicted; 2, 3, 4, 5, 6 remain
        assert received == [2, 3, 4, 5, 6]

    def test_no_eviction_at_boundary(self, queue):
        """Exactly max_queue_items items: no eviction."""
        for i in range(5):
            queue.enqueue("test", {"seq": i})
        assert queue.pending_count() == 5


class TestContextManager:
    """__enter__/__exit__ and close()."""

    def test_context_manager_closes_connection(self, queue_path):
        with OfflineQueue({"agent": {"sqlite_queue_path": queue_path}}) as q:
            q.enqueue("test", {"x": 1})
            assert q.pending_count() == 1
        # After __exit__, connection should be closed
        assert q.conn is None

    def test_close_is_idempotent(self, queue):
        queue.close()
        assert queue.conn is None
        queue.close()  # Should not raise
        assert queue.conn is None

    def test_context_manager_on_exception(self, queue_path):
        """Connection is closed even if body raises."""
        q = None
        try:
            with OfflineQueue({"agent": {"sqlite_queue_path": queue_path}}) as q:
                q.enqueue("test", {"x": 1})
                raise ValueError("deliberate error")
        except ValueError:
            pass
        assert q is not None
        assert q.conn is None


class TestConfigParsing:
    """Constructor config handling."""

    def test_dict_config(self, tmp_path):
        path = str(tmp_path / "dict_q.db")
        q = OfflineQueue({"agent": {"sqlite_queue_path": path, "max_queue_items": 42}})
        assert q.max_queue_items == 42
        q.close()

    def test_object_config(self, tmp_path):
        path = str(tmp_path / "obj_q.db")

        class FakeConfig:
            class agent:
                @staticmethod
                def get(key, default=None):
                    return {"sqlite_queue_path": path, "max_queue_items": 99}.get(key, default)

        q = OfflineQueue(FakeConfig())
        assert q.max_queue_items == 99
        q.close()

    def test_default_max_queue_items(self, tmp_path):
        path = str(tmp_path / "default_q.db")
        q = OfflineQueue({"agent": {"sqlite_queue_path": path}})
        assert q.max_queue_items == 10000
        q.close()
