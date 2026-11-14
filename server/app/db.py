"""Read-only DuckDB connection shared by the app, with one cursor per request.

Why one connection + one cursor per request:

* A DuckDB *connection* object is not meant to be used by several threads at
  the same time. Flask's development server (and most WSGI servers) handle
  requests in parallel threads, so sharing one connection directly would be
  unsafe.
* Opening a brand-new connection per request would re-open the file each time.
* ``connection.cursor()`` creates a lightweight duplicate connection to the
  **same** in-process database. Giving each request its own cursor makes
  concurrent requests safe while the database is opened only once.

Why read-only: the API never writes. Opening with ``read_only=True`` guarantees
that a bug cannot modify data and lets several API processes read the same file.
Note that DuckDB does not let another process *write* to the file while it is
open, so stop the API before running the importer.

If the file is missing at startup the app still starts; every request then
tries to open it again (cheap check) so the API recovers without a restart
once the database is created.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

import duckdb
from flask import Flask, current_app, g

from app.errors import DatabaseUnavailableError

logger = logging.getLogger(__name__)

_EXTENSION_KEY = "hotspots_db"


class Database:
    """Lazily opened, read-only DuckDB connection.

    Attributes:
        path: Absolute path to the ``.duckdb`` file.
    """

    def __init__(self, path: Path) -> None:
        """Create the holder without opening the file yet.

        Args:
            path: Absolute path to the DuckDB file.
        """
        self.path = path
        self._connection: duckdb.DuckDBPyConnection | None = None
        self._lock = threading.Lock()

    def connect(self) -> duckdb.DuckDBPyConnection:
        """Return the shared read-only connection, opening it if needed.

        The lock ensures that two threads arriving at the same time do not both
        open the file.

        Returns:
            The shared connection.

        Raises:
            DatabaseUnavailableError: If the file does not exist, cannot be
                opened, or has no ``hotspots`` table.
        """
        if self._connection is not None:
            return self._connection
        with self._lock:
            if self._connection is None:
                self._connection = self._open()
        return self._connection

    def _open(self) -> duckdb.DuckDBPyConnection:
        """Open the file read-only and check that the ``hotspots`` table exists.

        Returns:
            A new connection.

        Raises:
            DatabaseUnavailableError: On any failure (details only go to the log).
        """
        if not self.path.is_file():
            logger.warning("Database file not found: %s", self.path)
            raise DatabaseUnavailableError()
        try:
            connection = duckdb.connect(str(self.path), read_only=True)
        except duckdb.Error:
            logger.exception("Could not open database %s", self.path)
            raise DatabaseUnavailableError() from None
        tables = connection.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_name = 'hotspots'"
        ).fetchone()
        if not tables or tables[0] == 0:
            connection.close()
            logger.warning("Database %s has no 'hotspots' table", self.path)
            raise DatabaseUnavailableError()
        logger.info("Opened database %s (read-only)", self.path)
        return connection

    def cursor(self) -> duckdb.DuckDBPyConnection:
        """Create a new cursor (duplicate connection) for one request.

        Returns:
            A cursor that must be closed by the caller.

        Raises:
            DatabaseUnavailableError: If the database cannot be opened.
        """
        try:
            return self.connect().cursor()
        except duckdb.Error:
            logger.exception("Could not create a cursor")
            raise DatabaseUnavailableError() from None

    def close(self) -> None:
        """Close the shared connection (used by tests and on shutdown)."""
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None


def init_db(app: Flask, path: Path) -> Database:
    """Attach a :class:`Database` to the app and try to open it right away.

    A failure at startup is only logged: ``/health`` will report 503 and data
    endpoints will answer 503 until the file becomes available.

    Args:
        app: The Flask application.
        path: Absolute database path.

    Returns:
        The database holder stored in ``app.extensions``.
    """
    database = Database(path)
    app.extensions[_EXTENSION_KEY] = database
    try:
        database.connect()
    except DatabaseUnavailableError:
        logger.warning("Starting without a database; requests will return 503 until it exists")
    app.teardown_appcontext(_close_request_cursor)
    return database


def get_database() -> Database:
    """Return the :class:`Database` of the current app.

    Returns:
        The database holder.
    """
    return current_app.extensions[_EXTENSION_KEY]


def get_cursor() -> duckdb.DuckDBPyConnection:
    """Return the cursor of the current request, creating it on first use.

    The cursor is cached in ``flask.g`` so several queries in the same request
    share it, and it is closed automatically at the end of the request.

    Returns:
        The request's cursor.

    Raises:
        DatabaseUnavailableError: If the database cannot be opened.
    """
    if "db_cursor" not in g:
        g.db_cursor = get_database().cursor()
    return g.db_cursor


def _close_request_cursor(_exc: BaseException | None) -> None:
    """Close the request's cursor, if one was created (teardown callback).

    Args:
        _exc: Exception that ended the request, if any (unused).
    """
    cursor = g.pop("db_cursor", None)
    if cursor is not None:
        cursor.close()
