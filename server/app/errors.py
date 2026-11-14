"""API exceptions and the global Flask error handlers.

Every error leaves the API with the same JSON shape::

    {"error": {"code": "INVALID_PARAMETER", "message": "...", "parameter": "lat1"}}

``parameter`` is only present for invalid-parameter errors. Unexpected
exceptions are logged with their stack trace on the server but the client only
receives a generic ``INTERNAL_ERROR`` message, so internals are never exposed.
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Flask, Response, jsonify
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """Base class for errors that map directly to an HTTP response.

    Attributes:
        status_code: HTTP status to return.
        code: Stable machine-readable error code.
        message: Human-readable English message.
    """

    status_code: int = 500
    code: str = "INTERNAL_ERROR"

    def __init__(self, message: str) -> None:
        """Create the error.

        Args:
            message: Human-readable English message sent to the client.
        """
        super().__init__(message)
        self.message = message

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON body for this error.

        Returns:
            ``{"error": {"code": ..., "message": ...}}``.
        """
        return {"error": {"code": self.code, "message": self.message}}


class InvalidParameterError(ApiError):
    """A query parameter is missing or invalid (HTTP 400).

    Attributes:
        parameter: Name of the parameter that failed, so the client can show it.
    """

    status_code = 400
    code = "INVALID_PARAMETER"

    def __init__(self, parameter: str, message: str) -> None:
        """Create the error.

        Args:
            parameter: Name of the offending query parameter (e.g. ``"lat1"``).
            message: Explanation of what is wrong.
        """
        super().__init__(message)
        self.parameter = parameter

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON body, including the failing parameter name.

        Returns:
            ``{"error": {"code": ..., "message": ..., "parameter": ...}}``.
        """
        body = super().to_dict()
        body["error"]["parameter"] = self.parameter
        return body


class DatabaseUnavailableError(ApiError):
    """The DuckDB file is missing, locked or has no ``hotspots`` table (HTTP 503)."""

    status_code = 503
    code = "DATABASE_UNAVAILABLE"

    def __init__(self, message: str = "The hotspots database is not available") -> None:
        """Create the error.

        Args:
            message: Explanation for the client; never includes file system details.
        """
        super().__init__(message)


#: Codes used for standard HTTP errors raised by Flask/Werkzeug (404, 405, ...).
_HTTP_CODES: dict[int, str] = {
    400: "BAD_REQUEST",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
}


def _error_response(status: int, code: str, message: str) -> tuple[Response, int]:
    """Build a JSON error response with the standard shape.

    Args:
        status: HTTP status code.
        code: Machine-readable error code.
        message: Human-readable message.

    Returns:
        A ``(response, status)`` tuple accepted by Flask.
    """
    return jsonify({"error": {"code": code, "message": message}}), status


def register_error_handlers(app: Flask) -> None:
    """Attach the global error handlers to the application.

    Three handlers are registered, from most to least specific:

    1. :class:`ApiError`: our own errors, returned as-is.
    2. ``HTTPException``: Werkzeug errors such as 404 or 405, reshaped to our format.
    3. ``Exception``: anything else; logged with stack trace, answered with a generic 500.

    Args:
        app: The Flask application.
    """

    @app.errorhandler(ApiError)
    def handle_api_error(error: ApiError) -> tuple[Response, int]:
        return jsonify(error.to_dict()), error.status_code

    @app.errorhandler(HTTPException)
    def handle_http_exception(error: HTTPException) -> tuple[Response, int]:
        status = error.code or 500
        code = _HTTP_CODES.get(status, "HTTP_ERROR")
        message = error.description or error.name
        if status == 404:
            message = "The requested URL was not found"
        return _error_response(status, code, message)

    @app.errorhandler(Exception)
    def handle_unexpected(error: Exception) -> tuple[Response, int]:
        logger.exception("Unhandled error while processing request")
        return _error_response(500, "INTERNAL_ERROR", "An internal error occurred")
