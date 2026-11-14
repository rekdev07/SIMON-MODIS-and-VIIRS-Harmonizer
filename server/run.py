"""Entry point: ``python run.py`` starts the API with Flask's built-in server.

Host, port and debug mode come from ``API_HOST``, ``API_PORT`` and
``FLASK_DEBUG`` (see ``.env.example``). By default the API listens on every
network interface (``0.0.0.0``), so other devices on the same local network
(LAN) can reach it at ``http://<this computer's LAN IP>:5000``. The address to
share is printed at startup.

For a hackathon demo the built-in server is enough; for production use a WSGI
server such as gunicorn (``gunicorn -b 0.0.0.0:5000 "app:create_app()"``).
"""

from __future__ import annotations

from app import create_app
from app.config import Settings, load_settings
from app.network import get_lan_ip


def startup_urls(settings: Settings, lan_ip: str | None) -> list[str]:
    """Build the human-readable lines that tell people where the API is.

    Logic: ``0.0.0.0`` means "every interface", which is not an address anyone
    can type, so it is replaced by ``localhost`` (this computer) and by the LAN
    IP (other devices). Any other host is shown as-is; ``127.0.0.1``/``localhost``
    get a hint that the LAN cannot reach them.

    Args:
        settings: Settings with ``host`` and ``port``.
        lan_ip: This computer's LAN IP (see :func:`app.network.get_lan_ip`), or None.

    Returns:
        Lines to print, e.g. ``["Local:   http://localhost:5000", "Network: http://192.168.1.23:5000"]``.

    Example:
        >>> from pathlib import Path
        >>> startup_urls(Settings(db_path=Path("x"), host="0.0.0.0", port=5000), "192.168.1.23")
        ['Local:   http://localhost:5000', 'Network: http://192.168.1.23:5000  <- share this with your team']
    """
    port = settings.port
    if settings.host in {"0.0.0.0", "::"}:
        lines = [f"Local:   http://localhost:{port}"]
        if lan_ip:
            lines.append(f"Network: http://{lan_ip}:{port}  <- share this with your team")
        else:
            lines.append("Network: no LAN connection detected (connect to a network to share the API)")
        return lines
    lines = [f"Local:   http://{settings.host}:{port}"]
    if settings.host in {"127.0.0.1", "localhost", "::1"}:
        lines.append("Network: disabled (API_HOST is local-only; set API_HOST=0.0.0.0 to share on the LAN)")
    return lines


def main() -> None:
    """Load the settings, build the app, print where it is reachable and run it."""
    settings = load_settings()
    app = create_app(settings)
    print("\nHotspots API is starting:")
    for line in startup_urls(settings, get_lan_ip()):
        print(f"  {line}")
    print()
    app.run(host=settings.host, port=settings.port, debug=settings.debug)


if __name__ == "__main__":
    main()
