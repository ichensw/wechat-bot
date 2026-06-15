"""Configuration loader - YAML file with environment variable overrides and hot reload."""

from __future__ import annotations

import hashlib
import logging
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml

from bot.config.settings import Settings
from bot.core.exceptions import ConfigError, ConfigValidationError

logger = logging.getLogger("WeChatBot.Config")


class ConfigLoader:
    """Load and manage configuration with hot-reload support.

    Features:
      - YAML file loading
      - Environment variable overrides
      - Validation on load
      - Hot-reload with file change detection
      - Change notification callbacks
    """

    def __init__(self, config_path: str = "config.yaml"):
        self._config_path = Path(config_path)
        self._settings: Optional[Settings] = None
        self._raw_data: Dict[str, Any] = {}
        self._file_hash: str = ""
        self._last_load_time: float = 0.0
        self._change_callbacks: List[Callable[[Settings], None]] = []

    @property
    def settings(self) -> Settings:
        """Get current settings, loading if necessary."""
        if self._settings is None:
            self.load()
        return self._settings

    @property
    def config_path(self) -> Path:
        """Get config file path."""
        return self._config_path

    def load(self) -> Settings:
        """Load configuration from YAML file, validate, and apply env overrides.

        Raises:
            ConfigError: If the file cannot be loaded.
            ConfigValidationError: If validation fails.
        """
        logger.info("Loading configuration from %s", self._config_path)

        if not self._config_path.exists():
            raise ConfigError(f"Configuration file not found: {self._config_path}")

        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                self._raw_data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ConfigError(f"Invalid YAML in {self._config_path}: {e}") from e
        except OSError as e:
            raise ConfigError(f"Cannot read {self._config_path}: {e}") from e

        # Compute file hash for change detection
        self._file_hash = self._compute_file_hash()
        self._last_load_time = time.time()

        try:
            self._settings = Settings.from_dict(self._raw_data)
        except ConfigValidationError as e:
            raise
        except Exception as e:
            raise ConfigError(f"Failed to parse configuration: {e}") from e

        logger.info("Configuration loaded successfully")
        return self._settings

    def reload_if_changed(self) -> bool:
        """Reload configuration if the file has changed.

        Returns:
            True if reloaded, False if unchanged.
        """
        if not self._config_path.exists():
            return False

        current_hash = self._compute_file_hash()
        if current_hash == self._file_hash:
            return False

        logger.info("Configuration file changed, reloading...")
        try:
            old_settings = self._settings
            self.load()
            self._notify_change_callbacks()
            return True
        except (ConfigError, ConfigValidationError) as e:
            logger.error("Failed to reload config: %s. Keeping old settings.", e)
            self._settings = old_settings
            return False

    def save(self) -> None:
        """Save current settings back to YAML file."""
        if self._settings is None:
            return

        data = self._settings.to_dict()
        try:
            with open(self._config_path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            self._file_hash = self._compute_file_hash()
            logger.info("Configuration saved to %s", self._config_path)
        except OSError as e:
            logger.error("Failed to save config: %s", e)

    def update_section(self, section: str, key: str, value: Any) -> None:
        """Update a single config value and save.

        Args:
            section: Config section name (e.g., "bot", "group_filter")
            key: Key within the section
            value: New value
        """
        if self._settings is None:
            return

        # Update in raw data
        self._raw_data.setdefault(section, {})[key] = value

        # Update in settings object
        section_obj = getattr(self._settings, section, None)
        if section_obj and hasattr(section_obj, key):
            setattr(section_obj, key, value)
            self.save()

    def on_change(self, callback: Callable[[Settings], None]) -> None:
        """Register a callback to be called when config changes."""
        self._change_callbacks.append(callback)

    def _notify_change_callbacks(self) -> None:
        """Notify all registered change callbacks."""
        if self._settings:
            for callback in self._change_callbacks:
                try:
                    callback(self._settings)
                except Exception as e:
                    logger.error("Config change callback error: %s", e)

    def _compute_file_hash(self) -> str:
        """Compute SHA256 hash of the config file for change detection."""
        try:
            content = self._config_path.read_bytes()
            return hashlib.sha256(content).hexdigest()
        except OSError:
            return ""
