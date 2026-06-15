"""Core bot - main orchestrator with state machine and lifecycle management.

The bot manages the message loop, scheduled tasks, and component lifecycle.
It uses a state machine to track its operational state.
"""

from __future__ import annotations

import logging
import signal
import sys
import threading
import time
from enum import Enum, auto
from typing import Optional

from bot.core.app import ApplicationContext
from bot.core.event_bus import EventTypes
from bot.wcf.models import WxMessage

logger = logging.getLogger("WeChatBot")


class BotState(Enum):
    """Bot operational state machine."""

    UNINITIALIZED = auto()
    INITIALIZING = auto()
    RUNNING = auto()
    DEGRADED = auto()  # WCF connection issues, trying to recover
    STOPPING = auto()
    STOPPED = auto()

    @property
    def is_operational(self) -> bool:
        """Check if the bot can process messages."""
        return self in (BotState.RUNNING, BotState.DEGRADED)


class WeChatBot:
    """Main bot orchestrator.

    Lifecycle:
      1. Initialize ApplicationContext (DI container)
      2. Connect to WCF and verify login
      3. Start message receiving loop
      4. Start scheduled tasks
      5. Start WebHook server
      6. Block main thread until shutdown signal

    State transitions:
      UNINITIALIZED -> INITIALIZING -> RUNNING
      RUNNING -> DEGRADED (on WCF connection issues)
      DEGRADED -> RUNNING (on recovery)
      RUNNING/DEGRADED -> STOPPING -> STOPPED
    """

    def __init__(self, config_path: str = "config.yaml"):
        self._config_path = config_path
        self._ctx: Optional[ApplicationContext] = None
        self._state = BotState.UNINITIALIZED
        self._running = False
        self._msg_thread: Optional[threading.Thread] = None

    @property
    def state(self) -> BotState:
        """Current bot state."""
        return self._state

    def start(self) -> None:
        """Start the bot (blocking)."""
        self._transition(BotState.INITIALIZING)

        logger.info("=" * 60)
        logger.info("  WeChatBot v2.0.0 starting...")
        logger.info("=" * 60)

        try:
            # Initialize all components
            self._ctx = ApplicationContext(self._config_path)
            self._ctx.initialize()
        except Exception as e:
            logger.error("Failed to initialize: %s", e)
            self._transition(BotState.STOPPED)
            sys.exit(1)

        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Start message receiving
        wcf = self._ctx.wcf
        wcf.enable_receiving_msg()

        # Refresh groups on startup
        try:
            groups = self._ctx.group_monitor.refresh_groups()
            logger.info("Initial group scan: %d groups found", len(groups))
        except Exception as e:
            logger.warning("Initial group scan failed: %s", e)

        logger.info("Group filter: %s", self._ctx.group_filter.get_status())

        # Start scheduled tasks
        self._setup_scheduled_tasks()
        self._ctx.scheduler.start()

        # Start WebHook server
        if self._ctx.settings.webhook.enabled:
            self._ctx.webhook_server.start(blocking=False)
            logger.info(
                "WebHook: http://%s:%d/api/",
                self._ctx.settings.webhook.host,
                self._ctx.settings.webhook.port,
            )

        # Start message processing thread
        self._running = True
        self._msg_thread = threading.Thread(
            target=self._message_loop,
            name="MessageLoopThread",
            daemon=True,
        )
        self._msg_thread.start()

        self._transition(BotState.RUNNING)
        self._ctx.event_bus.publish(EventTypes.BOT_STARTED, source="WeChatBot")

        logger.info("=" * 60)
        logger.info("  WeChatBot is running! Press Ctrl+C to stop.")
        logger.info("=" * 60)

        # Block main thread
        try:
            while self._running:
                time.sleep(1)
                # Periodic health check
                if self._state == BotState.RUNNING and not wcf.is_connected():
                    self._transition(BotState.DEGRADED)
                    logger.warning("WCF connection lost, entering degraded state")
                elif self._state == BotState.DEGRADED and wcf.is_connected():
                    self._transition(BotState.RUNNING)
                    logger.info("WCF connection recovered")
        except KeyboardInterrupt:
            pass

        self.stop()

    def stop(self) -> None:
        """Stop the bot gracefully."""
        if self._state == BotState.STOPPED:
            return

        self._transition(BotState.STOPPING)
        self._running = False

        logger.info("Stopping WeChatBot...")

        if self._ctx:
            self._ctx.event_bus.publish(EventTypes.BOT_STOPPING, source="WeChatBot")
            self._ctx.shutdown()

        self._transition(BotState.STOPPED)
        logger.info("WeChatBot stopped.")

    def _message_loop(self) -> None:
        """Main message processing loop (daemon thread)."""
        logger.info("Message loop started")

        while self._running:
            try:
                wcf = self._ctx.wcf
                msg = wcf.get_msg(timeout=1.0)
                if msg is None:
                    continue

                # Enrich message with sender name
                self._enrich_sender_name(msg)

                # Process through handler pipeline
                result = self._ctx.handler_pipeline.process(msg)

                # Send response if handler provided one
                if result.response and result.action == "handled":
                    receiver = msg.room_id if msg.is_group else msg.sender
                    try:
                        wcf.send_text(result.response, receiver)
                    except Exception as e:
                        logger.error("Failed to send response to %s: %s", receiver, e)

            except Exception as e:
                if self._running:
                    logger.error("Message loop error: %s", e)
                    time.sleep(0.1)

        logger.info("Message loop exiting")

    def _enrich_sender_name(self, msg: WxMessage) -> None:
        """Enrich message with sender display name."""
        try:
            contact = self._ctx.wcf.get_info_by_wxid(msg.sender)
            if contact:
                msg.sender_name = contact.name or contact.remark or contact.alias or ""
        except Exception:
            pass

    def _setup_scheduled_tasks(self) -> None:
        """Register all periodic tasks."""
        scheduler = self._ctx.scheduler
        monitor_settings = self._ctx.settings.monitor

        # Member count check
        if monitor_settings.member_count:
            scheduler.add_interval_task(
                task_id="member_count_check",
                func=self._ctx.group_monitor.check_member_counts,
                interval_seconds=monitor_settings.member_count_interval,
                description="Check group member count changes",
            )

        # Group cache refresh
        scheduler.add_interval_task(
            task_id="group_cache_refresh",
            func=self._ctx.group_monitor.refresh_groups,
            interval_seconds=monitor_settings.group_cache_ttl,
            description="Refresh group cache from WeChat",
        )

        # Daily DB cleanup (at 3 AM)
        scheduler.add_cron_task(
            task_id="db_cleanup",
            func=lambda: self._ctx.db.cleanup_old_messages(days=90),
            hour=3,
            minute=0,
            description="Clean up messages older than 90 days",
        )

        # Daily DB vacuum (at 4 AM)
        scheduler.add_cron_task(
            task_id="db_vacuum",
            func=self._ctx.db.vacuum,
            hour=4,
            minute=0,
            description="Vacuum SQLite database",
        )

    def _signal_handler(self, signum, frame) -> None:
        """Handle shutdown signals."""
        logger.info("Received signal %s, shutting down...", signum)
        self._running = False

    def _transition(self, new_state: BotState) -> None:
        """Transition to a new state with logging."""
        old_state = self._state
        self._state = new_state
        if old_state != new_state:
            logger.info("State: %s -> %s", old_state.name, new_state.name)
