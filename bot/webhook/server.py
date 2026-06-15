"""WebHook server - Flask HTTP API for external integrations.

Composes middleware and routes into a fully configured Flask application.
Supports both embedded (development) and WSGI (production) deployment.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Optional

from flask import Flask

from bot.config.settings import WebHookSettings
from bot.webhook.middleware import (
    AuthMiddleware,
    CORSMiddleware,
    ErrorHandlingMiddleware,
    RateLimitMiddleware,
    RequestLoggingMiddleware,
)
from bot.webhook.routes import api_bp, register_routes

if TYPE_CHECKING:
    from bot.config.loader import ConfigLoader
    from bot.db.repository import Repository
    from bot.group.filter import GroupFilter
    from bot.wcf.client import WcfClient

logger = logging.getLogger("WeChatBot.WebHook")


class WebHookServer:
    """WebHook HTTP API server.

    Features:
      - Bearer token authentication
      - Rate limiting per IP
      - CORS support
      - Request logging
      - Error handling
      - Production-ready WSGI support
    """

    def __init__(
        self,
        config_loader: "ConfigLoader",
        db: "Repository",
        group_filter: "GroupFilter",
        wcf_client: "WcfClient",
    ):
        self._config_loader = config_loader
        self._db = db
        self._group_filter = group_filter
        self._wcf = wcf_client
        self._app: Optional[Flask] = None
        self._thread: Optional[threading.Thread] = None

    def create_app(self) -> Flask:
        """Create and configure the Flask application."""
        app = Flask(__name__)
        app.logger.setLevel(logging.WARNING)

        # Register middleware
        settings = self._config_loader.settings.webhook

        AuthMiddleware(token=settings.token).register(app)
        RateLimitMiddleware(max_requests=settings.rate_limit, window_seconds=60).register(app)
        CORSMiddleware(allowed_origins=settings.cors_origins).register(app)
        RequestLoggingMiddleware().register(app)
        ErrorHandlingMiddleware().register(app)

        # Register routes
        register_routes(api_bp, self._config_loader, self._db, self._group_filter, self._wcf)
        app.register_blueprint(api_bp)

        self._app = app
        return app

    def start(self, blocking: bool = False) -> None:
        """Start the WebHook server.

        Args:
            blocking: If True, run in current thread (blocks). If False, run in daemon thread.
        """
        settings = self._config_loader.settings.webhook
        if not settings.enabled:
            logger.info("WebHook server disabled in config")
            return

        app = self._app or self.create_app()

        logger.info("WebHook server starting on %s:%d", settings.host, settings.port)

        if blocking:
            app.run(host=settings.host, port=settings.port, threaded=True, debug=False)
        else:
            self._thread = threading.Thread(
                target=app.run,
                kwargs={"host": settings.host, "port": settings.port, "threaded": True, "debug": False},
                name="WebHookThread",
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        """Stop the WebHook server."""
        # Flask dev server doesn't have a clean shutdown API
        # In production, use gunicorn with SIGTERM
        logger.info("WebHook server stopping")

    def get_app(self) -> Optional[Flask]:
        """Get the Flask app instance for WSGI deployment.

        Usage with gunicorn:
            gunicorn "bot.webhook.server:create_app()"
        """
        return self._app or self.create_app()
