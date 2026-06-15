"""Custom exception hierarchy for WeChat Bot.

All exceptions inherit from WeChatBotError for easy catch-all.
Specific subtypes enable fine-grained error handling.

Hierarchy:
    WeChatBotError (base)
    ├── ConfigError → ConfigValidationError
    ├── WcfError → WcfConnectionError, WcfNotLoggedInError, WcfMessageError, WcfSendError
    ├── HandlerError → HandlerNotFoundError, HandlerPipelineError
    ├── AdminError → AdminAlreadyBoundError, AdminNotBoundError, AdminPermissionDeniedError
    ├── DatabaseError → DatabaseConnectionError, DatabaseMigrationError
    ├── GroupError → GroupNotFoundError
    └── WebHookError → WebHookAuthError, WebHookRateLimitError
"""

from __future__ import annotations


# ── Base ──────────────────────────────────────────────────────────────

class WeChatBotError(Exception):
    """Base exception for all WeChat Bot errors."""

    def __init__(self, message: str = "", *args, **kwargs):
        self.message = message
        super().__init__(message, *args, **kwargs)

    def __str__(self) -> str:
        return self.message or super().__str__()


# ── Config ────────────────────────────────────────────────────────────

class ConfigError(WeChatBotError):
    """Configuration-related error."""


class ConfigValidationError(ConfigError):
    """Configuration validation failed."""

    def __init__(self, field: str = "", reason: str = "", *args, **kwargs):
        self.field = field
        self.reason = reason
        msg = f"Config validation error: {field} - {reason}" if field else reason or "Validation failed"
        super().__init__(msg, *args, **kwargs)


# ── WCF ──────────────────────────────────────────────────────────────

class WcfError(WeChatBotError):
    """WeChatFerry-related error."""


class WcfConnectionError(WcfError):
    """Failed to connect to WCF."""


class WcfNotLoggedInError(WcfError):
    """WeChat is not logged in."""


class WcfMessageError(WcfError):
    """Error processing a WCF message."""


class WcfSendError(WcfError):
    """Failed to send a message via WCF."""


# ── Handler ──────────────────────────────────────────────────────────

class HandlerError(WeChatBotError):
    """Handler-related error."""


class HandlerNotFoundError(HandlerError):
    """Requested handler was not found."""


class HandlerPipelineError(HandlerError):
    """Error in the handler pipeline execution."""


# ── Admin ────────────────────────────────────────────────────────────

class AdminError(WeChatBotError):
    """Admin-related error."""


class AdminAlreadyBoundError(AdminError):
    """An admin is already bound to the bot."""

    def __init__(self, current_admin: str = "", *args, **kwargs):
        self.current_admin = current_admin
        msg = f"Admin already bound: {current_admin}" if current_admin else "Admin already bound"
        super().__init__(msg, *args, **kwargs)


class AdminNotBoundError(AdminError):
    """No admin is currently bound."""


class AdminPermissionDeniedError(AdminError):
    """Admin permission denied for the requested action."""

    def __init__(self, wxid: str = "", action: str = "", *args, **kwargs):
        self.wxid = wxid
        self.action = action
        msg = f"Permission denied for {wxid}: {action}" if action else f"Permission denied for {wxid}"
        super().__init__(msg, *args, **kwargs)


# ── Database ─────────────────────────────────────────────────────────

class DatabaseError(WeChatBotError):
    """Database-related error."""


class DatabaseConnectionError(DatabaseError):
    """Failed to connect to the database."""


class DatabaseMigrationError(DatabaseError):
    """Database migration failed."""

    def __init__(self, version: int = 0, reason: str = "", *args, **kwargs):
        self.version = version
        msg = f"Migration v{version} failed: {reason}" if version else reason or "Migration failed"
        super().__init__(msg, *args, **kwargs)


# ── Group ────────────────────────────────────────────────────────────

class GroupError(WeChatBotError):
    """Group-related error."""


class GroupNotFoundError(GroupError):
    """Group was not found."""

    def __init__(self, room_id: str = "", *args, **kwargs):
        self.room_id = room_id
        msg = f"Group not found: {room_id}" if room_id else "Group not found"
        super().__init__(msg, *args, **kwargs)


# ── WebHook ─────────────────────────────────────────────────────────

class WebHookError(WeChatBotError):
    """WebHook-related error."""


class WebHookAuthError(WebHookError):
    """WebHook authentication failed."""


class WebHookRateLimitError(WebHookError):
    """WebHook rate limit exceeded."""
