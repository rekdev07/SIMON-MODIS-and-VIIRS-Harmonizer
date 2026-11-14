"""Hotspots API: a small read-only Flask service over a DuckDB file of FIRMS hotspots.

Use :func:`create_app` (application factory) to build the app::

    from app import create_app
    app = create_app()

``flask --app app run`` finds the factory automatically.
"""

from __future__ import annotations

import logging

from flask import Flask
from flask_cors import CORS

from app.config import Settings, load_settings
from app.db import init_db
from app.errors import register_error_handlers
from app.routes import register_blueprints


def create_app(settings: Settings | None = None) -> Flask:
    """Create and configure the Flask application.

    Steps: load settings, configure JSON output, enable CORS for the configured
    origins, open the read-only database, register error handlers and routes.

    Why a factory: tests can build an app pointing at a temporary database by
    passing their own :class:`Settings`, without touching environment variables.

    Args:
        settings: Settings to use; loaded from the environment when omitted.

    Returns:
        The configured application.
    """
    settings = settings or load_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    app = Flask(__name__)
    app.config["SETTINGS"] = settings
    # Keep keys in insertion order so GeoJSON reads naturally ("type" first).
    app.json.sort_keys = False  # type: ignore[attr-defined]

    CORS(app, origins=settings.cors_origins)
    init_db(app, settings.db_path)
    register_error_handlers(app)
    register_blueprints(app)
    return app
