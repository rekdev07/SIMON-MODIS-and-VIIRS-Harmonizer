"""Entry point: ``python run.py`` starts the API with Flask's built-in server.

Host, port and debug mode come from ``API_HOST``, ``API_PORT`` and
``FLASK_DEBUG`` (see ``.env.example``). For a hackathon demo the built-in server
is enough; for production use a WSGI server such as gunicorn
(``gunicorn "app:create_app()"``).
"""

from __future__ import annotations

from app import create_app
from app.config import load_settings


def main() -> None:
    """Load the settings, build the app and run it."""
    settings = load_settings()
    app = create_app(settings)
    app.run(host=settings.host, port=settings.port, debug=settings.debug)


if __name__ == "__main__":
    main()
