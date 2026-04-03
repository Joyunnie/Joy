from __future__ import annotations

import pytest

from agent1.agent.config import AgentConfig


@pytest.fixture
def mock_config():
    """테스트용 Agent1 config."""
    return AgentConfig({
        "pm20": {
            "db_type": "sqlserver",
            "instance": r".\PMPLUS20",
            "database": "PM_MAIN",
            "auth": "windows",
            "patient_hash_salt": "test-salt-12345",
            "visit_lookback_days": 7,
            "drug_master_sync_interval_hours": 24,
        },
        "agent": {
            "polling_interval_seconds": 10,
            "cloud_api_url": "http://localhost:8000",
            "sqlite_queue_path": ":memory:",
            "max_queue_items": 100,
        },
        "backup": {
            "output_dir": "/tmp/test_backups",
            "retention_days": 7,
            "retention_min_count": 1,
            "min_disk_space_gb": 1,
            "lock_file": "/tmp/test_backups/.lock",
        },
    })
