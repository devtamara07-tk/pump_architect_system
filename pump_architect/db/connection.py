import os
import re
import sqlite3

import pandas as pd

DB_URL_ENV = "DATABASE_URL"

# Resolve DB path relative to the project root (two levels up from this file:
#   pump_architect/db/connection.py  →  pump_architect/db  →  pump_architect  →  project root)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_FILE = os.path.join(_PROJECT_ROOT, "architect_system.db")

# ---------------------------------------------------------------------------
# SQL adaptation helpers
# ---------------------------------------------------------------------------

_PH_RE = re.compile(r"\?")
_BACKTICK_RE = re.compile(r"`([^`]+)`")
_PRAGMA_RE = re.compile(r"^\s*PRAGMA\b", re.IGNORECASE)
_ALTER_ADD_RE = re.compile(
    r"^\s*ALTER\s+TABLE\b.+ADD\s+COLUMN\b", re.IGNORECASE | re.DOTALL
)
_INSERT_OR_REPLACE_RE = re.compile(
    r"\bINSERT\s+OR\s+REPLACE\s+INTO\b", re.IGNORECASE
)


def _adapt_sql(sql: str) -> str:
    """Convert SQLite SQL syntax to PostgreSQL (? → %s, backtick → double-quote)."""
    sql = _PH_RE.sub("%s", sql)
    sql = _BACKTICK_RE.sub(r'"\1"', sql)
    return sql


# ---------------------------------------------------------------------------
# Postgres connection wrappers (make psycopg2 look like sqlite3)
# ---------------------------------------------------------------------------


class _PgCursorProxy:
    """Proxies a psycopg2 cursor with automatic SQLite→Postgres SQL adaptation."""

    def __init__(self, pg_cur):
        self._cur = pg_cur

    def execute(self, sql, params=None):
        # Silently skip SQLite-only statements that have no Postgres equivalent.
        if _PRAGMA_RE.match(sql):
            return self
        if _ALTER_ADD_RE.match(sql):
            # Tables are already migrated in Postgres – ignore ADD COLUMN.
            return self

        sql = _adapt_sql(sql)

        # INSERT OR REPLACE has no direct Postgres equivalent.
        # Callers ensure uniqueness via an explicit DELETE before INSERT, so
        # converting to a plain INSERT is safe.
        if _INSERT_OR_REPLACE_RE.search(sql):
            sql = _INSERT_OR_REPLACE_RE.sub("INSERT INTO", sql)

        if params is not None:
            self._cur.execute(sql, params)
        else:
            self._cur.execute(sql)
        return self

    def fetchall(self):
        return self._cur.fetchall()

    def fetchone(self):
        return self._cur.fetchone()

    @property
    def description(self):
        return self._cur.description

    @property
    def rowcount(self):
        return self._cur.rowcount

    @property
    def lastrowid(self):
        # Use the RETURNING id pattern for Postgres instead.
        return None

    def __iter__(self):
        return iter(self._cur)


class _PgConnWrapper:
    """
    Wraps a psycopg2 connection so that legacy code using the sqlite3 API
    (conn.execute(), conn.cursor(), conn.commit(), conn.close()) works
    transparently with Postgres.
    """

    def __init__(self, pg_conn):
        self._conn = pg_conn

    def cursor(self):
        return _PgCursorProxy(self._conn.cursor())

    def execute(self, sql, params=None):
        """sqlite3-compatible conn.execute() – creates a fresh cursor each time."""
        cur = _PgCursorProxy(self._conn.cursor())
        return cur.execute(sql, params)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *args):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        self.close()


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def get_database_url() -> str | None:
    """
    Return the Postgres connection string if configured, else None.

    Resolution order:
    1. ``DATABASE_URL`` environment variable (local dev, Codespaces).
    2. ``st.secrets["DATABASE_URL"]`` (Streamlit Community Cloud).
    """
    url = os.getenv(DB_URL_ENV)
    if url:
        return url
    try:
        import streamlit as st  # noqa: PLC0415

        return st.secrets.get(DB_URL_ENV)
    except Exception:
        return None


def is_postgres(conn) -> bool:
    """Return True if *conn* is a Postgres (``_PgConnWrapper``) connection."""
    return isinstance(conn, _PgConnWrapper)


def get_connection():
    """
    Return a DB-API connection for the *new-style* db/ modules.

    - If ``DATABASE_URL`` is set, return a ``_PgConnWrapper`` around a
      psycopg2 connection (Neon / Postgres).
    - Otherwise fall back to a local SQLite file.
    """
    db_url = get_database_url()
    if db_url:
        import psycopg2  # provided by psycopg2-binary  # noqa: PLC0415

        return _PgConnWrapper(psycopg2.connect(db_url))
    return sqlite3.connect(DB_FILE)


def get_db_connection(db_file: str = None):
    """
    Return a DB-API connection for *legacy* modules that pass ``db_file``.

    When ``DATABASE_URL`` is configured, the ``db_file`` argument is ignored
    and a Postgres connection is returned.  Otherwise a SQLite connection to
    ``db_file`` (or the default ``DB_FILE``) is returned.
    """
    db_url = get_database_url()
    if db_url:
        import psycopg2  # noqa: PLC0415

        return _PgConnWrapper(psycopg2.connect(db_url))
    return sqlite3.connect(db_file or DB_FILE)


def _read_df(sql: str, conn, params=None) -> pd.DataFrame:
    """
    ``pd.read_sql_query`` wrapper that handles both sqlite3 and psycopg2.

    When *conn* is a ``_PgConnWrapper``, the SQL is adapted (``?`` → ``%s``)
    and the underlying raw psycopg2 connection is passed directly to pandas,
    which supports psycopg2 natively.
    """
    if is_postgres(conn):
        sql = _adapt_sql(sql)
        return pd.read_sql_query(sql, conn._conn, params=params)
    return pd.read_sql_query(sql, conn, params=params)