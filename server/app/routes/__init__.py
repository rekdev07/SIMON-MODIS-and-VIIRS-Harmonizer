"""HTTP routes (Flask blueprints) of the hotspots API.

* :mod:`app.routes.hotspots`: ``GET /api/v1/hotspots``
* :mod:`app.routes.calendar`: ``GET /api/v1/calendar``
* :mod:`app.routes.meta`: ``GET /api/v1/dataset`` and ``GET /health``
* :mod:`app.routes.stats`: ``GET /api/v1/stats/*`` (dashboard aggregates)
* :mod:`app.routes.model`: ``GET /api/v1/model/metrics`` and
  ``POST /api/v1/model/predict``
"""

from __future__ import annotations

from flask import Flask

from app.routes import calendar, hotspots, meta, model, stats


def register_blueprints(app: Flask) -> None:
    """Register every blueprint on the application.

    Args:
        app: The Flask application.
    """
    app.register_blueprint(hotspots.bp)
    app.register_blueprint(calendar.bp)
    app.register_blueprint(meta.bp)
    app.register_blueprint(stats.bp)
    app.register_blueprint(model.bp)
