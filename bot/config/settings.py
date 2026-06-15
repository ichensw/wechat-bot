"""Pydantic-style dataclass configuration with validation.

All config values are validated at load time. Environment variable overrides are supported.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field, fields
from typing import Any, Dict, List, Optional, Tuple

from bot.core.exceptions import ConfigValidationError


# ── Helper ──────────────────────────────────────────────────────────────────

def _env(key: str, default: Optional[str] = None) -> Optional[str]:
    """Read environment variable."""
    return os.environ.get(key, default)


def _parse_bool(val: Optional[str]) -> Optional[bool]:
    """Parse boolean from string."""
    if val is None:
        return None
    return val.lower() in ("1", "true", "yes", "on")


def _parse_int(val: Optional[str]) -> Optional[int]:
    """Parse int from string."""
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _parse_list(val: Optional[str]) -> Optional[List[str]]:
    """Parse comma-separated list from string."""
    if val is None:
        return None
    if not val.strip():
        return []
    return [item.strip() for item in val.split(",") if item.strip()]


# ── Settings Dataclasses ───────────────────────────────────────────────────


@dataclass
class BotSettings:
    """Bot core settings."""

    name: str = "WeChatBot"
    admin_wxid: Optional[str] = None
    command_prefix: str = "#"
    wcf_mode: str = "local"
    wcf_remote_url: str = ""
    at_me_required: bool = True  # Bot only responds in groups when @mentioned
    private_whitelist: List[str] = field(default_factory=list)  # wxids allowed to private chat

    def __post_init__(self) -> None:
        if self.wcf_mode not in ("local", "remote", "mock"):
            raise ConfigValidationError("bot.wcf_mode", f"must be 'local', 'remote', or 'mock', got '{self.wcf_mode}'")
        if self.wcf_mode == "remote" and not self.wcf_remote_url:
            raise ConfigValidationError("bot.wcf_remote_url", "required when wcf_mode is 'remote'")
        if self.wcf_mode == "remote" and not self.wcf_remote_url.startswith(("http://", "https://")):
            raise ConfigValidationError("bot.wcf_remote_url", f"must start with http:// or https://, got '{self.wcf_remote_url}'")
        if self.command_prefix and len(self.command_prefix) > 3:
            raise ConfigValidationError("bot.command_prefix", f"max length is 3, got {len(self.command_prefix)}")

    def is_private_allowed(self, wxid: str) -> bool:
        """Check if a wxid is allowed to private chat with the bot.

        Admin is always allowed. Others must be in private_whitelist.
        """
        if self.admin_wxid and wxid == self.admin_wxid:
            return True
        return wxid in self.private_whitelist

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BotSettings":
        """Create from dict with environment variable overrides."""
        d = {}
        for f in fields(cls):
            env_key = f"BOT_{f.name.upper()}"
            env_val = _env(env_key)
            if env_val is not None:
                if f.type == "Optional[str]" or f.type == Optional[str] or f.type == str:
                    d[f.name] = env_val
                elif f.type == int or f.type == "int":
                    d[f.name] = _parse_int(env_val)
                elif f.type == bool:
                    d[f.name] = _parse_bool(env_val)
                elif f.type == "List[str]" or f.type == List[str]:
                    # Comma-separated env var → list
                    d[f.name] = [x.strip() for x in env_val.split(",") if x.strip()]
                else:
                    d[f.name] = env_val
            elif f.name in data:
                d[f.name] = data[f.name]
        return cls(**d)


@dataclass
class GroupFilterSettings:
    """Group filter settings."""

    mode: str = "whitelist"
    whitelist: List[str] = field(default_factory=list)
    blacklist: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        valid_modes = ("whitelist", "blacklist", "all")
        if self.mode not in valid_modes:
            raise ConfigValidationError("group_filter.mode", f"must be one of {valid_modes}, got '{self.mode}'")
        # Validate roomid format
        for room_id in self.whitelist:
            if not room_id.endswith("@chatroom"):
                raise ConfigValidationError("group_filter.whitelist", f"invalid roomid format: '{room_id}' (must end with @chatroom)")
        for room_id in self.blacklist:
            if not room_id.endswith("@chatroom"):
                raise ConfigValidationError("group_filter.blacklist", f"invalid roomid format: '{room_id}' (must end with @chatroom)")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GroupFilterSettings":
        """Create from dict with environment variable overrides."""
        mode = _env("GROUP_FILTER_MODE") or data.get("mode", "whitelist")
        whitelist = _parse_list(_env("GROUP_FILTER_WHITELIST")) or data.get("whitelist", [])
        blacklist = _parse_list(_env("GROUP_FILTER_BLACKLIST")) or data.get("blacklist", [])
        return cls(mode=mode, whitelist=whitelist, blacklist=blacklist)


@dataclass
class MonitorSettings:
    """Group monitoring settings."""

    member_count: bool = True
    member_count_interval: int = 300
    message: bool = True
    message_types: List[int] = field(default_factory=list)
    alert_member_change: bool = True
    member_change_threshold: int = 5
    group_cache_ttl: int = 600

    def __post_init__(self) -> None:
        if self.member_count_interval < 30:
            raise ConfigValidationError("monitor.member_count_interval", f"minimum is 30s, got {self.member_count_interval}")
        if self.member_change_threshold < 1:
            raise ConfigValidationError("monitor.member_change_threshold", f"minimum is 1, got {self.member_change_threshold}")
        if self.group_cache_ttl < 60:
            raise ConfigValidationError("monitor.group_cache_ttl", f"minimum is 60s, got {self.group_cache_ttl}")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MonitorSettings":
        """Create from dict with environment variable overrides."""
        return cls(
            member_count=_parse_bool(_env("MONITOR_MEMBER_COUNT")) if _env("MONITOR_MEMBER_COUNT") else data.get("member_count", True),
            member_count_interval=_parse_int(_env("MONITOR_MEMBER_COUNT_INTERVAL")) or data.get("member_count_interval", 300),
            message=_parse_bool(_env("MONITOR_MESSAGE")) if _env("MONITOR_MESSAGE") else data.get("message", True),
            message_types=data.get("message_types", []),
            alert_member_change=_parse_bool(_env("MONITOR_ALERT_MEMBER_CHANGE")) if _env("MONITOR_ALERT_MEMBER_CHANGE") else data.get("alert_member_change", True),
            member_change_threshold=_parse_int(_env("MONITOR_MEMBER_CHANGE_THRESHOLD")) or data.get("member_change_threshold", 5),
            group_cache_ttl=_parse_int(_env("MONITOR_GROUP_CACHE_TTL")) or data.get("group_cache_ttl", 600),
        )


@dataclass
class WebHookSettings:
    """WebHook server settings."""

    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = 8080
    token: str = "change-me-to-a-secure-token"
    rate_limit: int = 60
    cors_origins: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.enabled:
            if self.token == "change-me-to-a-secure-token" or len(self.token) < 16:
                import logging
                logging.getLogger("WeChatBot.Config").warning(
                    "⚠️  webhook.token is insecure (too short or default). "
                    "Please set a strong random token (>= 32 chars) before production deployment!"
                )
            if not (1 <= self.port <= 65535):
                raise ConfigValidationError("webhook.port", f"must be 1-65535, got {self.port}")
            if self.rate_limit < 1:
                raise ConfigValidationError("webhook.rate_limit", f"minimum is 1, got {self.rate_limit}")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WebHookSettings":
        """Create from dict with environment variable overrides."""
        enabled = _parse_bool(_env("WEBHOOK_ENABLED")) if _env("WEBHOOK_ENABLED") else data.get("enabled", True)
        return cls(
            enabled=enabled,
            host=_env("WEBHOOK_HOST") or data.get("host", "0.0.0.0"),
            port=_parse_int(_env("WEBHOOK_PORT")) or data.get("port", 8080),
            token=_env("WEBHOOK_TOKEN") or data.get("token", "change-me-to-a-secure-token"),
            rate_limit=_parse_int(_env("WEBHOOK_RATE_LIMIT")) or data.get("rate_limit", 60),
            cors_origins=data.get("cors_origins", []),
        )


@dataclass
class DatabaseSettings:
    """Database settings."""

    path: str = "data/wechat_bot.db"
    wal_mode: bool = True
    busy_timeout: int = 5000
    batch_size: int = 100
    batch_flush_interval: int = 10

    def __post_init__(self) -> None:
        if self.batch_size < 1:
            raise ConfigValidationError("database.batch_size", f"minimum is 1, got {self.batch_size}")
        if self.batch_flush_interval < 1:
            raise ConfigValidationError("database.batch_flush_interval", f"minimum is 1s, got {self.batch_flush_interval}")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DatabaseSettings":
        """Create from dict with environment variable overrides."""
        return cls(
            path=_env("DATABASE_PATH") or data.get("path", "data/wechat_bot.db"),
            wal_mode=data.get("wal_mode", True),
            busy_timeout=data.get("busy_timeout", 5000),
            batch_size=data.get("batch_size", 100),
            batch_flush_interval=data.get("batch_flush_interval", 10),
        )


@dataclass
class LoggingSettings:
    """Logging settings."""

    level: str = "INFO"
    file: Optional[str] = "data/wechat_bot.log"
    max_size_mb: int = 10
    backup_count: int = 5
    format: str = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"

    def __post_init__(self) -> None:
        valid_levels = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
        if self.level.upper() not in valid_levels:
            raise ConfigValidationError("logging.level", f"must be one of {valid_levels}, got '{self.level}'")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LoggingSettings":
        """Create from dict with environment variable overrides."""
        return cls(
            level=_env("LOG_LEVEL") or data.get("level", "INFO"),
            file=_env("LOG_FILE") or data.get("file", "data/wechat_bot.log"),
            max_size_mb=_parse_int(_env("LOG_MAX_SIZE_MB")) or data.get("max_size_mb", 10),
            backup_count=_parse_int(_env("LOG_BACKUP_COUNT")) or data.get("backup_count", 5),
            format=data.get("format", "%(asctime)s [%(name)s] %(levelname)s: %(message)s"),
        )


@dataclass
class Settings:
    """Root settings object - aggregates all config sections."""

    bot: BotSettings = field(default_factory=BotSettings)
    group_filter: GroupFilterSettings = field(default_factory=GroupFilterSettings)
    monitor: MonitorSettings = field(default_factory=MonitorSettings)
    webhook: WebHookSettings = field(default_factory=WebHookSettings)
    database: DatabaseSettings = field(default_factory=DatabaseSettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Settings":
        """Create Settings from a raw dict (loaded from YAML)."""
        return cls(
            bot=BotSettings.from_dict(data.get("bot", {})),
            group_filter=GroupFilterSettings.from_dict(data.get("group_filter", {})),
            monitor=MonitorSettings.from_dict(data.get("monitor", {})),
            webhook=WebHookSettings.from_dict(data.get("webhook", {})),
            database=DatabaseSettings.from_dict(data.get("database", {})),
            logging=LoggingSettings.from_dict(data.get("logging", {})),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize settings to a dict suitable for YAML output."""
        import dataclasses
        result = {}
        for f in fields(self):
            section = getattr(self, f.name)
            if dataclasses.is_dataclass(section):
                result[f.name] = dataclasses.asdict(section)
            else:
                result[f.name] = section
        return result
