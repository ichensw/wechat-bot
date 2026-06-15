"""Tests for configuration settings and validation."""

import pytest
from bot.config.settings import (
    BotSettings,
    GroupFilterSettings,
    MonitorSettings,
    WebHookSettings,
    DatabaseSettings,
    LoggingSettings,
    Settings,
)
from bot.core.exceptions import ConfigValidationError


class TestBotSettings:
    """Tests for BotSettings validation."""

    def test_default_settings(self):
        settings = BotSettings()
        assert settings.name == "WeChatBot"
        assert settings.admin_wxid is None
        assert settings.wcf_mode == "local"

    def test_valid_remote_mode(self):
        settings = BotSettings(wcf_mode="remote", wcf_remote_url="http://192.168.1.100:8080")
        assert settings.wcf_mode == "remote"

    def test_valid_mock_mode(self):
        settings = BotSettings(wcf_mode="mock")
        assert settings.wcf_mode == "mock"

    def test_invalid_wcf_mode(self):
        with pytest.raises(ConfigValidationError, match="wcf_mode"):
            BotSettings(wcf_mode="invalid")

    def test_remote_without_url(self):
        with pytest.raises(ConfigValidationError, match="wcf_remote_url"):
            BotSettings(wcf_mode="remote")

    def test_remote_invalid_url(self):
        with pytest.raises(ConfigValidationError, match="http"):
            BotSettings(wcf_mode="remote", wcf_remote_url="ftp://invalid")

    def test_command_prefix_too_long(self):
        with pytest.raises(ConfigValidationError, match="command_prefix"):
            BotSettings(command_prefix="toolongprefix")

    def test_from_dict(self):
        data = {"name": "MyBot", "wcf_mode": "local", "command_prefix": "!"}
        settings = BotSettings.from_dict(data)
        assert settings.name == "MyBot"
        assert settings.command_prefix == "!"


class TestGroupFilterSettings:
    """Tests for GroupFilterSettings validation."""

    def test_valid_whitelist_mode(self):
        settings = GroupFilterSettings(mode="whitelist", whitelist=["test@chatroom"])
        assert settings.mode == "whitelist"
        assert len(settings.whitelist) == 1

    def test_invalid_mode(self):
        with pytest.raises(ConfigValidationError, match="mode"):
            GroupFilterSettings(mode="invalid")

    def test_invalid_roomid_format(self):
        with pytest.raises(ConfigValidationError, match="roomid"):
            GroupFilterSettings(whitelist=["invalid_id"])

    def test_all_mode(self):
        settings = GroupFilterSettings(mode="all")
        assert settings.mode == "all"

    def test_from_dict_with_env(self, monkeypatch):
        monkeypatch.setenv("GROUP_FILTER_MODE", "blacklist")
        settings = GroupFilterSettings.from_dict({"mode": "whitelist"})
        assert settings.mode == "blacklist"


class TestMonitorSettings:
    """Tests for MonitorSettings validation."""

    def test_defaults(self):
        settings = MonitorSettings()
        assert settings.member_count is True
        assert settings.member_count_interval == 300

    def test_interval_too_small(self):
        with pytest.raises(ConfigValidationError, match="member_count_interval"):
            MonitorSettings(member_count_interval=10)


class TestWebHookSettings:
    """Tests for WebHookSettings validation."""

    def test_defaults(self):
        settings = WebHookSettings(enabled=False)
        assert settings.enabled is False

    def test_invalid_port(self):
        with pytest.raises(ConfigValidationError, match="port"):
            WebHookSettings(port=99999)

    def test_insecure_token_warning(self, caplog):
        """Default token should produce a warning."""
        import logging
        with caplog.at_level(logging.WARNING, logger="WeChatBot.Config"):
            WebHookSettings()  # Uses default token
        assert any("insecure" in r.message.lower() for r in caplog.records)


class TestSettings:
    """Tests for root Settings composition."""

    def test_from_dict(self, sample_config_data):
        settings = Settings.from_dict(sample_config_data)
        assert settings.bot.name == "TestBot"
        assert settings.group_filter.mode == "whitelist"
        assert settings.monitor.member_count is True
        assert settings.webhook.enabled is False

    def test_to_dict(self, sample_config_data):
        settings = Settings.from_dict(sample_config_data)
        result = settings.to_dict()
        assert "bot" in result
        assert result["bot"]["name"] == "TestBot"
        assert "group_filter" in result
