"""Application context - dependency injection container.

Centralizes all component initialization and provides a single point
of access for services. Components access each other through the
ApplicationContext rather than direct imports.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from bot.config.loader import ConfigLoader
from bot.config.settings import Settings
from bot.core.event_bus import EventBus
from bot.db.manager import DatabaseManager
from bot.db.repository import Repository
from bot.group.cache import GroupCache
from bot.group.filter import GroupFilter
from bot.group.monitor import GroupMonitor
from bot.admin.manager import AdminManager
from bot.core.sender import ThreadSafeSender
from bot.handlers.pipeline import HandlerPipeline
from bot.handlers.registry import HandlerRegistry
from bot.scheduler.manager import TaskScheduler
from bot.webhook.server import WebHookServer
from bot.wcf.client import WcfClient, create_wcf_client

logger = logging.getLogger("WeChatBot.AppContext")


class ApplicationContext:
    """Application-wide dependency injection container.

    Initializes all components in the correct order and provides
    them to any part of the application that needs them.

    Initialization order:
      1. Config (loaded and validated)
      2. Logging (configured)
      3. Event Bus (ready for subscriptions)
      4. Database (connection and schema)
      5. WCF Client (connected to WeChat)
      6. Group Filter (initialized from config)
      7. Group Cache (empty, ready to be populated)
      8. Group Monitor (depends on filter, cache, db, wcf)
      9. Handler Registry & Pipeline (depends on monitor, admin)
      10. Admin Manager (depends on filter, monitor, wcf, db)
      11. WebHook Server (depends on all above)
      12. Task Scheduler (for periodic tasks)
    """

    def __init__(self, config_path: str = "config.yaml"):
        self._config_loader = ConfigLoader(config_path)
        self._services: Dict[str, Any] = {}

    def initialize(self) -> None:
        """Initialize all application components.

        Raises:
            ConfigError: If configuration is invalid.
            WcfConnectionError: If WCF client cannot connect.
        """
        logger.info("Initializing application context...")

        # 1. Config
        settings = self._config_loader.load()
        self._services["settings"] = settings

        # 2. Logging
        from bot.utils.logger import setup_logging
        setup_logging(settings.logging)

        # 3. Event Bus
        event_bus = EventBus(max_history=2000, max_workers=4)
        self._services["event_bus"] = event_bus

        # 4. Database
        db_manager = DatabaseManager(settings.database)
        repository = Repository(db_manager)
        self._services["db_manager"] = db_manager
        self._services["db"] = repository

        # 5. WCF Client
        wcf_client = create_wcf_client(settings.bot)
        wcf_client.connect()
        self._services["wcf"] = wcf_client

        # Verify login
        if not wcf_client.is_login():
            raise WcfConnectionError("WeChat is not logged in. Please login first.")

        user_info = wcf_client.get_user_info()
        logger.info("Logged in as: %s (%s)", user_info.name, user_info.wxid)

        # 6. Group Filter
        group_filter = GroupFilter(self._config_loader)
        self._services["group_filter"] = group_filter

        # 7. Group Cache
        group_cache = GroupCache(settings.monitor)
        self._services["group_cache"] = group_cache

        # 8. Thread-Safe Sender (wraps WCF client for concurrent send safety)
        sender = ThreadSafeSender(wcf_client)
        self._services["sender"] = sender

        # 9. Group Monitor
        send_func = lambda msg, receiver: sender.send_text(msg, receiver)  # noqa: E731
        group_monitor = GroupMonitor(
            settings=settings.monitor,
            db=repository,
            group_filter=group_filter,
            group_cache=group_cache,
            wcf_client=wcf_client,
            event_bus=event_bus,
            send_msg_func=send_func,
        )
        self._services["group_monitor"] = group_monitor

        # 9. Handler Registry & Pipeline
        handler_registry = HandlerRegistry()
        self._services["handler_registry"] = handler_registry

        handler_pipeline = HandlerPipeline(handler_registry, event_bus)
        self._services["handler_pipeline"] = handler_pipeline

        # 10. Admin Manager
        admin_manager = AdminManager(
            config_loader=self._config_loader,
            db=repository,
            group_filter=group_filter,
            group_monitor=group_monitor,
            wcf_client=wcf_client,
            event_bus=event_bus,
            sender=sender,
        )
        self._services["admin_manager"] = admin_manager

        # Register handlers now that all dependencies are available
        from bot.handlers.group_message import GroupMessageHandler, PrivateMessageHandler, SystemMessageHandler
        handler_registry.register(GroupMessageHandler(
            group_filter=group_filter,
            group_monitor=group_monitor,
            admin_manager=admin_manager,
            bot_settings=settings.bot,
            sender=sender,
        ))
        handler_registry.register(PrivateMessageHandler(
            admin_manager=admin_manager,
            bot_settings=settings.bot,
            sender=sender,
        ))
        handler_registry.register(SystemMessageHandler())

        # 11. WebHook Server
        webhook_server = WebHookServer(
            config_loader=self._config_loader,
            db=repository,
            group_filter=group_filter,
            wcf_client=wcf_client,
        )
        self._services["webhook_server"] = webhook_server

        # 12. Task Scheduler
        scheduler = TaskScheduler()
        self._services["scheduler"] = scheduler

        logger.info("Application context initialized successfully")

    def get(self, name: str) -> Any:
        """Get a service by name.

        Args:
            name: Service identifier (e.g., "wcf", "db", "group_filter").

        Returns:
            The service instance.

        Raises:
            KeyError: If the service is not found.
        """
        if name not in self._services:
            raise KeyError(f"Service not found: {name}. Available: {list(self._services.keys())}")
        return self._services[name]

    @property
    def settings(self) -> Settings:
        """Get current settings."""
        return self._config_loader.settings

    @property
    def config_loader(self) -> ConfigLoader:
        """Get config loader."""
        return self._config_loader

    @property
    def wcf(self) -> WcfClient:
        """Get WCF client."""
        return self.get("wcf")

    @property
    def db(self) -> Repository:
        """Get database repository."""
        return self.get("db")

    @property
    def event_bus(self) -> EventBus:
        """Get event bus."""
        return self.get("event_bus")

    @property
    def group_filter(self) -> GroupFilter:
        """Get group filter."""
        return self.get("group_filter")

    @property
    def group_monitor(self) -> GroupMonitor:
        """Get group monitor."""
        return self.get("group_monitor")

    @property
    def admin_manager(self) -> AdminManager:
        """Get admin manager."""
        return self.get("admin_manager")

    @property
    def handler_pipeline(self) -> HandlerPipeline:
        """Get handler pipeline."""
        return self.get("handler_pipeline")

    @property
    def webhook_server(self) -> WebHookServer:
        """Get webhook server."""
        return self.get("webhook_server")

    @property
    def scheduler(self) -> TaskScheduler:
        """Get task scheduler."""
        return self.get("scheduler")

    def shutdown(self) -> None:
        """Gracefully shutdown all components in reverse order."""
        logger.info("Shutting down application context...")

        # Stop scheduler
        scheduler = self._services.get("scheduler")
        if scheduler:
            scheduler.stop()

        # Stop webhook
        webhook = self._services.get("webhook_server")
        if webhook:
            webhook.stop()

        # Stop WCF receiving
        wcf = self._services.get("wcf")
        if wcf:
            wcf.disable_receiving_msg()

        # Close database
        db_mgr = self._services.get("db_manager")
        if db_mgr:
            db_mgr.close()

        # Disconnect WCF
        if wcf:
            wcf.disconnect()

        # Shutdown event bus
        event_bus = self._services.get("event_bus")
        if event_bus:
            event_bus.shutdown()

        logger.info("Application context shutdown complete")
