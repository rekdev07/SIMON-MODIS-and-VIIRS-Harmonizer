"""Application settings loaded from environment variables.

All runtime configuration of the API lives in a single immutable
:class:`Settings` object. Values come from environment variables, optionally
pre-loaded from a ``server/.env`` file with python-dotenv (variables that are
already set in the real environment always win over the file).

Why environment variables: they work the same way locally, in Docker and in
any hosting platform, and they keep paths and origins out of the code.

Example:
    >>> settings = load_settings()
    >>> settings.max_limit
    50000
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from app.network import PRIVATE_NETWORK_ORIGIN
from harmonizer.config import HarmonizationConfig, load_config

#: Absolute path of the ``server/`` directory. Relative paths in the
#: configuration (such as the database path) are resolved against it, so the
#: API finds its data no matter which directory it is started from.
SERVER_DIR: Path = Path(__file__).resolve().parent.parent

DEFAULT_DB_PATH = "data/hotspots.duckdb"
DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://localhost:3000"
#: Listen on every network interface so other devices on the LAN can reach the API.
#: Use ``API_HOST=127.0.0.1`` to accept connections from this computer only.
DEFAULT_HOST = "0.0.0.0"


@dataclass(frozen=True)
class Settings:
    """Immutable API configuration.

    Attributes:
        db_path: Absolute path to the DuckDB database file.
        cors_origins: Origins allowed to call the API from a browser
            (``["*"]`` allows any origin).
        cors_allow_lan: Also allow any origin on this computer or a private
            network (see :data:`app.network.PRIVATE_NETWORK_ORIGIN`), so the
            frontend works when opened from another device on the LAN.
        default_limit: Rows returned by ``/api/v1/hotspots`` when no ``limit`` is sent.
        max_limit: Largest ``limit`` a client may request.
        host: Interface used by ``run.py``: ``0.0.0.0`` = all interfaces (LAN),
            ``127.0.0.1`` = this computer only.
        port: Port used by ``run.py``.
        debug: Whether ``run.py`` starts Flask in debug mode.
        harmonization: Fit periods and source cutoffs of the harmonized
            calendar (``HARMONIZE_*`` variables, see :mod:`harmonizer.config`).
    """

    db_path: Path
    cors_origins: list[str] = field(default_factory=list)
    cors_allow_lan: bool = False
    default_limit: int = 10_000
    max_limit: int = 50_000
    host: str = DEFAULT_HOST
    port: int = 5000
    debug: bool = False
    harmonization: HarmonizationConfig = field(default_factory=HarmonizationConfig)


def allowed_cors_origins(settings: Settings) -> list[str | re.Pattern[str]]:
    """List what flask-cors should accept as the ``Origin`` of a browser request.

    The result is the explicit ``CORS_ORIGINS`` list plus, when
    ``cors_allow_lan`` is on, the :data:`~app.network.PRIVATE_NETWORK_ORIGIN`
    pattern. flask-cors accepts both plain strings (exact match) and compiled
    regular expressions in the same list, and allows a request if **any** entry
    matches.

    Why: LAN IPs change with every network, so matching "any private address"
    keeps the frontend working on teammates' devices without editing ``.env``,
    while public websites stay blocked.

    Args:
        settings: The application settings.

    Returns:
        Origins and patterns for ``flask_cors.CORS(origins=...)``.

    Example:
        >>> allowed_cors_origins(Settings(db_path=Path("x"), cors_origins=["http://a.com"]))
        ['http://a.com']
    """
    origins: list[str | re.Pattern[str]] = list(settings.cors_origins)
    if settings.cors_allow_lan:
        origins.append(PRIVATE_NETWORK_ORIGIN)
    return origins


def resolve_path(raw_path: str | os.PathLike[str]) -> Path:
    """Turn a configured path into an absolute path.

    Relative paths are interpreted relative to ``server/`` (not to the current
    working directory) so ``HOTSPOTS_DB_PATH=data/hotspots.duckdb`` always points
    to ``server/data/hotspots.duckdb``.

    Args:
        raw_path: Absolute or ``server/``-relative path.

    Returns:
        The absolute path.
    """
    path = Path(raw_path).expanduser()
    return path if path.is_absolute() else (SERVER_DIR / path).resolve()


def _parse_origins(raw: str) -> list[str]:
    """Split a comma-separated list of origins, dropping blanks and spaces.

    Args:
        raw: Value such as ``"http://localhost:5173, http://localhost:3000"``.

    Returns:
        The list of origins, e.g. ``["http://localhost:5173", "http://localhost:3000"]``.
    """
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def _parse_bool(raw: str) -> bool:
    """Interpret common truthy strings (``1``, ``true``, ``yes``, ``on``).

    Args:
        raw: Raw environment value.

    Returns:
        True when the value is one of the truthy strings (case-insensitive).
    """
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _parse_positive_int(name: str, raw: str) -> int:
    """Parse a strictly positive integer environment variable.

    Args:
        name: Variable name, used in the error message.
        raw: Raw value.

    Returns:
        The parsed integer.

    Raises:
        ValueError: If the value is not an integer greater than zero.
    """
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc
    if value <= 0:
        raise ValueError(f"{name} must be greater than 0, got {value}")
    return value


def load_settings() -> Settings:
    """Build :class:`Settings` from the environment (and ``server/.env`` if present).

    Returns:
        The settings for this process.

    Raises:
        ValueError: If a numeric variable is invalid or ``DEFAULT_LIMIT`` exceeds
            ``MAX_LIMIT``.
    """
    load_dotenv(SERVER_DIR / ".env", override=False)

    default_limit = _parse_positive_int("DEFAULT_LIMIT", os.getenv("DEFAULT_LIMIT", "10000"))
    max_limit = _parse_positive_int("MAX_LIMIT", os.getenv("MAX_LIMIT", "50000"))
    if default_limit > max_limit:
        raise ValueError("DEFAULT_LIMIT cannot be greater than MAX_LIMIT")

    return Settings(
        db_path=resolve_path(os.getenv("HOTSPOTS_DB_PATH", DEFAULT_DB_PATH)),
        cors_origins=_parse_origins(os.getenv("CORS_ORIGINS", DEFAULT_CORS_ORIGINS)),
        cors_allow_lan=_parse_bool(os.getenv("CORS_ALLOW_LAN", "1")),
        default_limit=default_limit,
        max_limit=max_limit,
        host=os.getenv("API_HOST", DEFAULT_HOST),
        port=_parse_positive_int("API_PORT", os.getenv("API_PORT", "5000")),
        debug=_parse_bool(os.getenv("FLASK_DEBUG", "0")),
        harmonization=load_config(),
    )
