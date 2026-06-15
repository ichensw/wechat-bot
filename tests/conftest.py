"""Test configuration for pytest."""

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def tmp_dir():
    """Create a temporary directory for test data."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def sample_config_data():
    """Minimal valid config data for testing."""
    return {
        "bot": {
            "name": "TestBot",
            "admin_wxid": None,
            "command_prefix": "#",
        },
        "group_filter": {
            "mode": "whitelist",
            "whitelist": ["test123@chatroom"],
            "blacklist": [],
        },
        "monitor": {
            "member_count": True,
            "member_count_interval": 300,
            "message": True,
            "message_types": [],
            "alert_member_change": True,
            "member_change_threshold": 5,
            "group_cache_ttl": 600,
        },
        "webhook": {
            "enabled": False,
            "host": "127.0.0.1",
            "port": 8080,
            "token": "test-token-12345678",
            "rate_limit": 60,
            "cors_origins": [],
        },
        "database": {
            "path": "data/test_wechat_bot.db",
            "wal_mode": True,
            "busy_timeout": 5000,
            "batch_size": 100,
            "batch_flush_interval": 10,
        },
        "logging": {
            "level": "DEBUG",
            "file": None,
            "max_size_mb": 10,
            "backup_count": 5,
            "format": "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        },
    }


@pytest.fixture
def sample_config_yaml(tmp_dir, sample_config_data):
    """Write sample config to a temp YAML file."""
    import yaml
    config_path = tmp_dir / "config.yaml"
    # Adjust database path to use tmp_dir
    sample_config_data["database"]["path"] = str(tmp_dir / "test.db")
    sample_config_data["logging"]["file"] = None
    with open(config_path, "w") as f:
        yaml.dump(sample_config_data, f)
    return str(config_path)


@pytest.fixture
def db_path(tmp_dir):
    """Path for test database."""
    return str(tmp_dir / "test_wechat_bot.db")
