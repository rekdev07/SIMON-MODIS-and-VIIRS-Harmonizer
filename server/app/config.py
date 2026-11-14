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
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

#: Absolute path of the ``server/`` directory. Relative paths in the
#: configuration (such as the database path) are resolved against it, so the
#: API finds its data no matter which directory it is started from.
SERVER_DIR: Path = Path(__file__).resolve().parent.parent

DEFAULT_DB_PATH = "data/hotspots.duckdb"
DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://localhost:3000"


@dataclass(frozen=True)
class Settings:
    """Immutable API configuration.

    Attributes:
        db_path: Absolute path to the DuckDB database file.
        cors_origins: Origins allowed to call the API from a browser.
        default_limit: Rows returned by ``/api/v1/hotspots`` when no ``limit`` is sent.
        max_limit: Largest ``limit`` a client may request.
        host: Interface used by ``run.py``.
        port: Port used by ``run.py``.
        debug: Whether ``run.py`` starts Flask in debug mode.
    """

    db_path: Path
    cors_origins: list[str] = field(default_factory=list)
    default_limit: int = 10_000
    max_limit: int = 50_000
    host: str = "127.0.0.1"
    port: int = 5000
    debug: bool = False


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
        default_limit=default_limit,
        max_limit=max_limit,
        host=os.getenv("API_HOST", "127.0.0.1"),
        port=_parse_positive_int("API_PORT", os.getenv("API_PORT", "5000")),
        debug=_parse_bool(os.getenv("FLASK_DEBUG", "0")),
    )
