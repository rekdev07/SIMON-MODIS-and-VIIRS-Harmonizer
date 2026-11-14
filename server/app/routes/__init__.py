"""HTTP routes (Flask blueprints) of the hotspots API.

* :mod:`app.routes.hotspots`: ``GET /api/v1/hotspots``
* :mod:`app.routes.meta`: ``GET /api/v1/dataset`` and ``GET /health``
"""

from __future__ import annotations

from flask import Flask

from app.routes import hotspots, meta


def register_blueprints(app: Flask) -> None:
    """Register every blueprint on the application.

    Args:
        app: The Flask application.
    """
    app.register_blueprint(hotspots.bp)
    app.register_blueprint(meta.bp)
