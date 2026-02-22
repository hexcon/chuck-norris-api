"""Middleware for request logging, timing, and security event detection."""

import time
import uuid
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.logging_config import setup_logging

logger = setup_logging()

# In-memory tracker for auth failure detection (resets on restart)
_auth_failures: dict[str, list[float]] = defaultdict(list)
AUTH_FAILURE_WINDOW = 300  # 5 minutes
AUTH_FAILURE_THRESHOLD_IP = 10  # per IP
AUTH_FAILURE_THRESHOLD_GLOBAL = 20  # total


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with structured fields for SIEM consumption."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        client_ip = request.headers.get(
            "X-Forwarded-For", request.client.host if request.client else "unknown"
        )
        start_time = time.monotonic()

        response = await call_next(request)

        duration_ms = round((time.monotonic() - start_time) * 1000, 2)

        log_data = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "client_ip": client_ip,
            "user_agent": request.headers.get("User-Agent", "unknown"),
            "response_time_ms": duration_ms,
            "event_type": "http_request",
        }

        # Detect auth failures (401 or 403)
        if response.status_code in (401, 403):
            log_data["event_type"] = "auth_failure"
            logger.warning("Authentication failure", extra=log_data)
            self._track_auth_failure(client_ip)
        elif response.status_code >= 500:
            log_data["event_type"] = "server_error"
            logger.error("Server error", extra=log_data)
        elif response.status_code >= 400:
            logger.warning("Client error", extra=log_data)
        else:
            logger.info("Request completed", extra=log_data)

        # Add request ID to response headers for traceability
        response.headers["X-Request-ID"] = request_id
        return response

    @staticmethod
    def _track_auth_failure(client_ip: str) -> None:
        """Track auth failures and log critical alerts on threshold breach."""
        now = time.time()
        cutoff = now - AUTH_FAILURE_WINDOW

        # Clean old entries and add new one
        _auth_failures[client_ip] = [
            t for t in _auth_failures[client_ip] if t > cutoff
        ]
        _auth_failures[client_ip].append(now)

        # Per-IP brute force detection
        if len(_auth_failures[client_ip]) >= AUTH_FAILURE_THRESHOLD_IP:
            logger.critical(
                "Possible brute force attack detected",
                extra={
                    "event_type": "brute_force_detected",
                    "client_ip": client_ip,
                    "failure_count": len(_auth_failures[client_ip]),
                    "window_seconds": AUTH_FAILURE_WINDOW,
                },
            )

        # Global spray detection
        total_failures = sum(
            len(times)
            for ip, times in _auth_failures.items()
            if any(t > cutoff for t in times)
        )
        if total_failures >= AUTH_FAILURE_THRESHOLD_GLOBAL:
            logger.critical(
                "Possible credential spray attack detected",
                extra={
                    "event_type": "spray_attack_detected",
                    "total_failures": total_failures,
                    "window_seconds": AUTH_FAILURE_WINDOW,
                },
            )
