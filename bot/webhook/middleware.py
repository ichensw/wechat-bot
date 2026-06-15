"""WebHook middleware - authentication, rate limiting, CORS.

Middleware follows Flask's before_request/after_request pattern.
Each middleware is encapsulated in its own class for clean composition.
"""

from __future__ import annotations

import logging
import time
from typing import List, Optional, Set

from flask import Flask, Response, jsonify, request

from bot.config.settings import WebHookSettings
from bot.core.exceptions import WebHookAuthError, WebHookRateLimitError
from bot.utils.rate_limit import RateLimiter

logger = logging.getLogger("WeChatBot.WebHook.MW")


class AuthMiddleware:
    """Bearer token authentication middleware.

    Skips auth for health check endpoint.
    All other endpoints require a valid Bearer token in the Authorization header.
    """

    def __init__(self, token: str, skip_paths: Optional[Set[str]] = None):
        self._token = token
        self._skip_paths = skip_paths or {"/api/health"}

    def register(self, app: Flask) -> None:
        """Register auth middleware on a Flask app."""

        @app.before_request
        def authenticate():
            if request.path in self._skip_paths:
                return None

            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return jsonify({
                    "error": "Unauthorized",
                    "message": "Missing or invalid Authorization header. Use: Bearer <token>",
                    "code": "AUTH_MISSING",
                }), 401

            provided_token = auth_header[7:]
            if provided_token != self._token:
                logger.warning("Auth failed from %s for %s", request.remote_addr, request.path)
                return jsonify({
                    "error": "Forbidden",
                    "message": "Invalid token",
                    "code": "AUTH_INVALID",
                }), 403

            return None


class RateLimitMiddleware:
    """Rate limiting middleware using sliding window algorithm.

    Limits requests per IP address within a configurable time window.
    Returns 429 with Retry-After header when limit is exceeded.
    """

    def __init__(self, max_requests: int, window_seconds: int = 60, skip_paths: Optional[Set[str]] = None):
        self._limiter = RateLimiter(max_requests=max_requests, window_seconds=window_seconds)
        self._skip_paths = skip_paths or {"/api/health"}

    def register(self, app: Flask) -> None:
        """Register rate limit middleware on a Flask app."""

        @app.before_request
        def check_rate_limit():
            if request.path in self._skip_paths:
                return None

            client_key = request.remote_addr or "unknown"
            if not self._limiter.check(client_key):
                remaining_window = self._limiter.window_seconds
                logger.warning("Rate limit exceeded for %s on %s", client_key, request.path)
                response = jsonify({
                    "error": "Too Many Requests",
                    "message": f"Rate limit exceeded. Max {self._limiter.max_requests} requests per {self._limiter.window_seconds}s.",
                    "code": "RATE_LIMITED",
                    "retry_after": remaining_window,
                })
                response.status_code = 429
                response.headers["Retry-After"] = str(remaining_window)
                return response

            return None

        @app.after_request
        def add_rate_limit_headers(response: Response):
            """Add X-RateLimit headers to all responses."""
            client_key = request.remote_addr or "unknown"
            remaining = self._limiter.remaining(client_key)
            response.headers["X-RateLimit-Limit"] = str(self._limiter.max_requests)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Window"] = str(self._limiter.window_seconds)
            return response


class CORSMiddleware:
    """CORS middleware for cross-origin requests.

    Adds Access-Control-Allow-* headers to responses.
    Only enabled when cors_origins is non-empty in config.
    """

    def __init__(self, allowed_origins: List[str], allowed_methods: Optional[List[str]] = None):
        self._origins = allowed_origins
        self._methods = allowed_methods or ["GET", "POST", "PUT", "DELETE", "OPTIONS"]

    def register(self, app: Flask) -> None:
        """Register CORS middleware on a Flask app."""
        if not self._origins:
            return

        @app.after_request
        def add_cors_headers(response: Response):
            origin = request.headers.get("Origin", "")
            if origin in self._origins or "*" in self._origins:
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Methods"] = ", ".join(self._methods)
                response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
                response.headers["Access-Control-Max-Age"] = "86400"
            return response

        @app.before_request
        def handle_preflight():
            if request.method == "OPTIONS":
                response = jsonify({})
                response.status_code = 204
                origin = request.headers.get("Origin", "")
                if origin in self._origins or "*" in self._origins:
                    response.headers["Access-Control-Allow-Origin"] = origin
                    response.headers["Access-Control-Allow-Methods"] = ", ".join(self._methods)
                    response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
                    response.headers["Access-Control-Max-Age"] = "86400"
                return response
            return None


class RequestLoggingMiddleware:
    """Request logging middleware for debugging and monitoring."""

    def register(self, app: Flask) -> None:
        """Register request logging middleware."""

        @app.before_request
        def log_request():
            logger.debug(
                "→ %s %s from %s",
                request.method,
                request.path,
                request.remote_addr,
            )

        @app.after_request
        def log_response(response: Response):
            elapsed = getattr(request, "_start_time", time.time()) - time.time()
            logger.debug(
                "← %s %s %d (%.0fms)",
                request.method,
                request.path,
                response.status_code,
                abs(elapsed) * 1000,
            )
            return response

        @app.before_request
        def record_start_time():
            request._start_time = time.time()  # noqa: SLF001


class ErrorHandlingMiddleware:
    """Global error handling middleware."""

    def register(self, app: Flask) -> None:
        """Register error handling middleware."""

        @app.errorhandler(400)
        def bad_request(e):
            return jsonify({"error": "Bad Request", "message": str(e), "code": "BAD_REQUEST"}), 400

        @app.errorhandler(404)
        def not_found(e):
            return jsonify({"error": "Not Found", "message": "The requested resource was not found", "code": "NOT_FOUND"}), 404

        @app.errorhandler(405)
        def method_not_allowed(e):
            return jsonify({"error": "Method Not Allowed", "message": "The HTTP method is not allowed for this endpoint", "code": "METHOD_NOT_ALLOWED"}), 405

        @app.errorhandler(500)
        def internal_error(e):
            logger.error("Internal server error: %s", e)
            return jsonify({"error": "Internal Server Error", "message": "An unexpected error occurred", "code": "INTERNAL_ERROR"}), 500
