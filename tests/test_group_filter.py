"""Tests for the group filter module."""

import pytest
from bot.config.loader import ConfigLoader
from bot.config.settings import Settings, GroupFilterSettings
from bot.group.filter import GroupFilter


class TestGroupFilter:
    """Tests for GroupFilter."""

    def _make_filter(self, mode="whitelist", whitelist=None, blacklist=None):
        """Helper to create a GroupFilter with specific settings."""
        import tempfile, yaml
        wl = whitelist if whitelist is not None else ["test123@chatroom"]
        bl = blacklist or []
        config_data = {
            "bot": {"name": "Test"},
            "group_filter": {"mode": mode, "whitelist": wl, "blacklist": bl},
            "monitor": {"member_count_interval": 300, "group_cache_ttl": 600},
            "webhook": {"enabled": False, "token": "x" * 32},
            "database": {"path": ":memory:"},
            "logging": {"level": "DEBUG", "file": None},
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            f.flush()
            loader = ConfigLoader(f.name)
            loader.load()
            return GroupFilter(loader)

    def test_whitelist_mode_allowed(self):
        gf = self._make_filter(mode="whitelist", whitelist=["test@chatroom"])
        assert gf.is_allowed("test@chatroom") is True

    def test_whitelist_mode_blocked(self):
        gf = self._make_filter(mode="whitelist", whitelist=["test@chatroom"])
        assert gf.is_allowed("other@chatroom") is False

    def test_blacklist_mode_allowed(self):
        gf = self._make_filter(mode="blacklist", blacklist=["blocked@chatroom"])
        assert gf.is_allowed("other@chatroom") is True

    def test_blacklist_mode_blocked(self):
        gf = self._make_filter(mode="blacklist", blacklist=["blocked@chatroom"])
        assert gf.is_allowed("blocked@chatroom") is False

    def test_all_mode(self):
        gf = self._make_filter(mode="all")
        assert gf.is_allowed("any@chatroom") is True
        assert gf.is_allowed("other@chatroom") is True

    def test_add_to_whitelist(self):
        gf = self._make_filter(mode="whitelist", whitelist=["existing@chatroom"])
        assert gf.add_to_whitelist("new@chatroom") is True
        assert gf.is_allowed("new@chatroom") is True
        # Duplicate
        assert gf.add_to_whitelist("new@chatroom") is False

    def test_remove_from_whitelist(self):
        gf = self._make_filter(mode="whitelist", whitelist=["remove@chatroom"])
        assert gf.remove_from_whitelist("remove@chatroom") is True
        assert gf.is_allowed("remove@chatroom") is False
        # Not in list
        assert gf.remove_from_whitelist("remove@chatroom") is False

    def test_add_invalid_roomid(self):
        gf = self._make_filter(mode="whitelist")
        assert gf.add_to_whitelist("invalid_id") is False

    def test_get_status_all(self):
        gf = self._make_filter(mode="all")
        assert "全部" in gf.get_status()

    def test_get_status_whitelist_empty(self):
        gf = self._make_filter(mode="whitelist", whitelist=[])
        assert "0个群" in gf.get_status()
