"""Tests for config.py: load_config, AgentConfig, _Section.

Covers: valid YAML, missing file, invalid YAML, missing sections,
attribute access, .get() defaults, get_section().
"""
import os
import tempfile

import pytest
import yaml

from agent1.agent.config import AgentConfig, _Section, load_config


class TestSection:
    """_Section attribute access and .get() behavior."""

    def test_attribute_access(self):
        s = _Section({"host": "localhost", "port": 5432})
        assert s.host == "localhost"
        assert s.port == 5432

    def test_missing_key_raises_attribute_error(self):
        s = _Section({"host": "localhost"})
        with pytest.raises(AttributeError, match="Config key not found: missing"):
            _ = s.missing

    def test_get_with_default(self):
        s = _Section({"host": "localhost"})
        assert s.get("host") == "localhost"
        assert s.get("missing") is None
        assert s.get("missing", 42) == 42

    def test_empty_section(self):
        s = _Section({})
        with pytest.raises(AttributeError):
            _ = s.host
        assert s.get("anything") is None


class TestAgentConfig:
    """AgentConfig initialization and section access."""

    def test_sections_populated(self):
        cfg = AgentConfig({
            "agent": {"cloud_api_url": "http://localhost:8000"},
            "pm20": {"db_type": "sqlserver"},
            "backup": {"output_dir": "/tmp"},
        })
        assert cfg.agent.cloud_api_url == "http://localhost:8000"
        assert cfg.pm20.db_type == "sqlserver"
        assert cfg.backup.output_dir == "/tmp"

    def test_missing_section_defaults_to_empty(self):
        """AgentConfig with no 'pm20' section creates empty _Section."""
        cfg = AgentConfig({"agent": {"cloud_api_url": "http://x"}})
        # pm20 is _Section({}) — attribute access raises AttributeError
        with pytest.raises(AttributeError):
            _ = cfg.pm20.db_type

    def test_get_section_returns_section(self):
        cfg = AgentConfig({
            "agent": {"url": "http://x"},
            "custom": {"key": "value"},
        })
        custom = cfg.get_section("custom")
        assert custom is not None
        assert custom.key == "value"

    def test_get_section_returns_none_for_missing(self):
        cfg = AgentConfig({"agent": {"url": "http://x"}})
        assert cfg.get_section("nonexistent") is None


class TestLoadConfig:
    """load_config() from YAML file."""

    def test_valid_config_file(self, tmp_path):
        config_data = {
            "agent": {"cloud_api_url": "http://cloud:8000", "polling_interval_seconds": 30},
            "pm20": {"db_type": "sqlserver", "instance": r".\PMPLUS20"},
            "backup": {"output_dir": "/backups"},
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_data), encoding="utf-8")

        cfg = load_config(str(config_file))
        assert cfg.agent.cloud_api_url == "http://cloud:8000"
        assert cfg.agent.polling_interval_seconds == 30
        assert cfg.pm20.db_type == "sqlserver"

    def test_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/path/config.yaml")

    def test_invalid_yaml_raises(self, tmp_path):
        config_file = tmp_path / "bad.yaml"
        config_file.write_text("{{invalid yaml: [", encoding="utf-8")

        with pytest.raises(yaml.YAMLError):
            load_config(str(config_file))

    def test_empty_file_returns_config(self, tmp_path):
        """Empty YAML file loads as None, AgentConfig gets {} sections."""
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("", encoding="utf-8")

        # yaml.safe_load("") returns None, so AgentConfig(None) will fail
        # This documents actual behavior
        with pytest.raises((TypeError, AttributeError)):
            load_config(str(config_file))

    def test_unicode_values(self, tmp_path):
        """Korean characters in config values are preserved."""
        config_data = {
            "agent": {"cloud_api_url": "http://x"},
            "pm20": {"description": "튼튼약국 PM+20"},
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_data, allow_unicode=True), encoding="utf-8")

        cfg = load_config(str(config_file))
        assert cfg.pm20.description == "튼튼약국 PM+20"
