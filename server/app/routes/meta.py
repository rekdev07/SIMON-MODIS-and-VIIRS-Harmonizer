"""Metadata endpoints: ``GET /api/v1/dataset`` and ``GET /health``."""

from __future__ import annotations

import logging

import duckdb
from flask import Blueprint, Response, jsonify

from app.db import get_cursor
from app.errors import DatabaseUnavailableError
from app.repository import dataset_summary, ping
from app.schemas import DatasetSummary

logger = logging.getLogger(__name__)

bp = Blueprint("meta", __name__)


@bp.get("/api/v1/dataset")
def get_dataset() -> Response:
    """Summarize the loaded data (used by the frontend for its date pickers).

    Returns:
        ``total_records``, ``min_date``, ``max_date``, ``instruments`` (count per
        instrument) and ``bbox`` covering all data.

    Raises:
        DatabaseUnavailableError: If the database cannot be opened (503).
    """
    summary = DatasetSummary.model_validate(dataset_summary(get_cursor()))
    return jsonify(summary.model_dump())


@bp.get("/health")
def health() -> tuple[Response, int]:
    """Report whether the API can query its database.

    Why a real query: a file that opens but has a broken table should not be
    reported as healthy, so a trivial ``SELECT`` on ``hotspots`` is executed.

    Returns:
        200 ``{"status": "ok", "database": "connected"}`` or
        503 ``{"status": "error", "database": "unavailable"}``.
    """
    try:
        ping(get_cursor())
    except (DatabaseUnavailableError, duckdb.Error):
        logger.warning("Health check failed: database unavailable")
        return jsonify({"status": "error", "database": "unavailable"}), 503
    return jsonify({"status": "ok", "database": "connected"}), 200
