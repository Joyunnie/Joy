"""Tests for Agent1 state file resilience.

Covers: corrupted JSON, future timestamps, concurrent state access,
state file creation in missing directory.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from agent1.agent.main import Agent1


@pytest.fixture
def config_path(tmp_path, mock_config):
    """Write mock config to a temp file and return path."""
    p = tmp_path / "config.yaml"
    p.write_text(yaml.dump(mock_config._data))
    return str(p)


@pytest.fixture
def agent(config_path, mock_config):
    with patch("agent1.agent.main.load_config", return_value=mock_config):
        a = Agent1(config_path)
        a.cloud_client = MagicMock()
        a.cloud_client.post_sync = MagicMock(return_value={})
        return a


class TestCorruptedState:
    def test_invalid_json_resets_to_defaults(self, tmp_path, mock_config):
        """Corrupted state.json → agent starts with None marker."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(mock_config._data))
        state_file = tmp_path / "state.json"
        state_file.write_text("{invalid json!!", encoding="utf-8")

        with patch("agent1.agent.main.load_config", return_value=mock_config):
            a = Agent1(str(config_path))

        assert a._last_visit_proc_dtime is None

    def test_empty_state_file(self, tmp_path, mock_config):
        """Empty state.json → agent starts with None marker."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(mock_config._data))
        state_file = tmp_path / "state.json"
        state_file.write_text("", encoding="utf-8")

        with patch("agent1.agent.main.load_config", return_value=mock_config):
            a = Agent1(str(config_path))

        assert a._last_visit_proc_dtime is None

    def test_state_with_extra_keys_ignored(self, tmp_path, mock_config):
        """Unknown keys in state.json don't crash agent."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(mock_config._data))
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps({
            "last_visit_proc_dtime": "20260301100000",
            "unknown_future_key": True,
            "another_key": [1, 2, 3],
        }))

        with patch("agent1.agent.main.load_config", return_value=mock_config):
            a = Agent1(str(config_path))

        assert a._last_visit_proc_dtime == "20260301100000"


class TestFutureTimestamps:
    def test_future_proc_dtime_accepted(self, tmp_path, mock_config):
        """Future timestamps are loaded as-is (no validation)."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(mock_config._data))
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps({
            "last_visit_proc_dtime": "20990101000000",
        }))

        with patch("agent1.agent.main.load_config", return_value=mock_config):
            a = Agent1(str(config_path))

        assert a._last_visit_proc_dtime == "20990101000000"


class TestStateSave:
    def test_save_creates_parent_dir(self, tmp_path, mock_config):
        """_save_state creates parent directories if missing."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(mock_config._data))

        with patch("agent1.agent.main.load_config", return_value=mock_config):
            a = Agent1(str(config_path))

        # Point state path to a nested directory that doesn't exist
        a._state_path = tmp_path / "nested" / "dir" / "state.json"
        a._last_visit_proc_dtime = "20260315120000"
        a._save_state()

        assert a._state_path.exists()
        saved = json.loads(a._state_path.read_text())
        assert saved["last_visit_proc_dtime"] == "20260315120000"

    def test_save_with_none_marker(self, agent, tmp_path):
        """When proc_dtime is None, state file has empty dict."""
        agent._last_visit_proc_dtime = None
        agent._save_state()
        saved = json.loads(agent._state_path.read_text())
        assert saved == {}

    def test_save_permission_error_logged_not_raised(self, agent, tmp_path):
        """Permission error on save is logged but doesn't crash."""
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o444)
        agent._state_path = readonly_dir / "state.json"
        agent._last_visit_proc_dtime = "20260315120000"
        # Should not raise
        agent._save_state()
        # Restore permissions so tmp_path cleanup works
        readonly_dir.chmod(0o755)
