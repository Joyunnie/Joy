"""Tests for SqlServerPM20Reader error handling.

Covers: connection refused, query timeout, empty result sets,
reconnection after failure.
"""
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
import pymssql

from agent1.agent.readers.sqlserver_pm20_reader import SqlServerPM20Reader


@pytest.fixture
def reader(mock_config):
    """SqlServerPM20Reader with mocked pymssql."""
    with patch("agent1.agent.readers.sqlserver_pm20_reader.pymssql") as mock_pymssql:
        mock_conn = MagicMock()
        mock_pymssql.connect.return_value = mock_conn
        r = SqlServerPM20Reader(mock_config)
        r._conn = mock_conn
        yield r, mock_conn, mock_pymssql


class TestConnectionErrors:
    def test_connection_refused(self, mock_config):
        """pymssql.connect raises → _get_connection propagates error."""
        with patch("agent1.agent.readers.sqlserver_pm20_reader.pymssql") as mock_pymssql:
            mock_pymssql.connect.side_effect = pymssql.OperationalError(
                "Cannot connect to server"
            )
            r = SqlServerPM20Reader(mock_config)
            r._conn = None

            with pytest.raises(pymssql.OperationalError):
                r.read_drug_master()

    def test_connection_timeout(self, mock_config):
        """Connection timeout raises OperationalError."""
        with patch("agent1.agent.readers.sqlserver_pm20_reader.pymssql") as mock_pymssql:
            mock_pymssql.connect.side_effect = pymssql.OperationalError(
                "Adaptive Server connection timed out"
            )
            r = SqlServerPM20Reader(mock_config)
            r._conn = None

            with pytest.raises(pymssql.OperationalError):
                r.read_recent_visits()


class TestQueryErrors:
    def test_query_timeout(self, reader):
        """SQL query execution timeout."""
        r, mock_conn, _ = reader
        cursor = MagicMock()
        mock_conn.cursor.return_value = cursor
        cursor.execute.side_effect = pymssql.OperationalError("query timed out")

        with pytest.raises(pymssql.OperationalError):
            r.read_drug_master()

    def test_query_error_on_visits(self, reader):
        """Database error during visit query."""
        r, mock_conn, _ = reader
        cursor = MagicMock()
        mock_conn.cursor.return_value = cursor
        cursor.execute.side_effect = pymssql.DatabaseError("table not found")

        with pytest.raises(pymssql.DatabaseError):
            r.read_recent_visits("20260101000000")


class TestEmptyResults:
    def test_empty_drug_master(self, reader):
        """Empty drug master returns empty list without error."""
        r, mock_conn, _ = reader
        cursor = MagicMock()
        mock_conn.cursor.return_value = cursor
        cursor.fetchall.return_value = []

        result = r.read_drug_master()
        assert result == []

    def test_empty_visits(self, reader):
        """No visits since marker returns empty list."""
        r, mock_conn, _ = reader
        cursor = MagicMock()
        mock_conn.cursor.return_value = cursor
        cursor.fetchall.return_value = []

        result = r.read_recent_visits("20260101000000")
        assert result == []

    def test_empty_inventory(self, reader):
        """Inventory always returns empty (ATDPS not connected)."""
        r, _, _ = reader
        assert r.read_inventory() == []


class TestReconnection:
    def test_reconnects_after_stale_connection(self, mock_config):
        """Stale connection detected → reconnect → retry succeeds."""
        with patch("agent1.agent.readers.sqlserver_pm20_reader.pymssql") as mock_pymssql:
            fresh_conn = MagicMock()
            mock_pymssql.connect.return_value = fresh_conn

            r = SqlServerPM20Reader(mock_config)
            # Simulate stale connection
            stale_conn = MagicMock()
            stale_cursor = MagicMock()
            stale_conn.cursor.return_value = stale_cursor
            stale_cursor.execute.side_effect = Exception("connection reset")
            r._conn = stale_conn

            # Fresh connection works
            fresh_cursor = MagicMock()
            fresh_conn.cursor.return_value = fresh_cursor
            fresh_cursor.fetchone.return_value = (1,)
            fresh_cursor.fetchall.return_value = []

            result = r.read_drug_master()
            assert result == []
            assert r._conn == fresh_conn


class TestClose:
    def test_close_idempotent(self, reader):
        """Calling close twice doesn't raise."""
        r, _, _ = reader
        r.close()
        r.close()

    def test_context_manager(self, mock_config):
        """Context manager protocol calls close."""
        with patch("agent1.agent.readers.sqlserver_pm20_reader.pymssql") as mock_pymssql:
            mock_conn = MagicMock()
            mock_pymssql.connect.return_value = mock_conn

            with SqlServerPM20Reader(mock_config) as r:
                pass

            assert r._conn is None
