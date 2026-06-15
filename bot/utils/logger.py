"""Structured logging setup for WeChat Bot.

Features:
  - Console + rotating file handlers
  - Configurable log level and format
  - Context-enriched logger factory
  - Module-level loggers with consistent naming
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Optional

from bot.config.settings import LoggingSettings


def setup_logging(settings: LoggingSettings) -> None:
    """Configure the root WeChatBot logger.

    Sets up console handler (always) and file handler (if configured).
    Applies rotating file handler with size-based rotation.

    Args:
        settings: Logging configuration settings.
    """
    # Get the root bot logger
    root_logger = logging.getLogger("WeChatBot")
    root_logger.setLevel(getattr(logging, settings.level.upper(), logging.INFO))

    # Remove existing handlers (for hot-reload safety)
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.level.upper(), logging.INFO))
    console_handler.setFormatter(logging.Formatter(settings.format, datefmt="%Y-%m-%d %H:%M:%S"))
    root_logger.addHandler(console_handler)

    # File handler (rotating)
    if settings.file:
        log_path = Path(settings.file)
        log_dir = log_path.parent
        if log_dir and not log_dir.exists():
            log_dir.mkdir(parents=True, exist_ok=True)

        max_bytes = settings.max_size_mb * 1024 * 1024
        file_handler = logging.handlers.RotatingFileHandler(
            str(log_path),
            maxBytes=max_bytes,
            backupCount=settings.backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(getattr(logging, settings.level.upper(), logging.INFO))
        file_handler.setFormatter(logging.Formatter(settings.format, datefmt="%Y-%m-%d %H:%M:%S"))
        root_logger.addHandler(file_handler)

    # Silence noisy third-party loggers
    for noisy in ("urllib3", "requests", "apscheduler", "werkzeug", "flask"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a child logger under the WeChatBot namespace.

    Usage:
        logger = get_logger("GroupMonitor")
        logger.info("Monitoring started")

    This creates a logger named "WeChatBot.GroupMonitor" that inherits
    configuration from the root WeChatBot logger.

    Args:
        name: Sub-component name (e.g., "GroupMonitor", "WebHook").

    Returns:
        A configured Logger instance.
    """
    return logging.getLogger(f"WeChatBot.{name}")


class ContextLogger:
    """Logger wrapper that injects context (room_id, msg_id, etc.) into messages.

    Usage:
        ctx_log = ContextLogger(logger, room_id="123@chatroom", sender="wxid_xxx")
        ctx_log.info("Message processed")
        # Output: [WeChatBot.Monitor] INFO: [room=123@chatroom sender=wxid_xxx] Message processed
    """

    def __init__(self, logger: logging.Logger, **context: str):
        self._logger = logger
        self._context = context

    def _format_msg(self, msg: str) -> str:
        """Prepend context to message."""
        parts = [f"{k}={v}" for k, v in self._context.items() if v]
        if parts:
            return f"[{', '.join(parts)}] {msg}"
        return msg

    def debug(self, msg: str, *args, **kwargs) -> None:
        self._logger.debug(self._format_msg(msg), *args, **kwargs)

    def info(self, msg: str, *args, **kwargs) -> None:
        self._logger.info(self._format_msg(msg), *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs) -> None:
        self._logger.warning(self._format_msg(msg), *args, **kwargs)

    def error(self, msg: str, *args, **kwargs) -> None:
        self._logger.error(self._format_msg(msg), *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs) -> None:
        self._logger.critical(self._format_msg(msg), *args, **kwargs)
