import os
import re
import sqlite3

DB_URL_ENV = "DATABASE_URL"

# Resolve DB path relative to the project root (two levels up from this file:
#   pump_architect/db/connection.py  →  pump_architect/db  →  pump_architect  →  project root)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_FILE = os.path.join(_PROJECT_ROOT, "architect_system.db")

# ---------------------------------------------------------------------------
# SQL-translation patterns (SQLite → Postgres)
# ---------------------------------------------------------------------------

_BACKTICK_RE = re.compile(r'`([^`]+)`')
_ALTER_ADD_COLUMN_RE = re.compile(
    r'(ALTER\s+TABLE\s+\S+\s+ADD\s+COLUMN\s+)(?!IF\s+NOT\s+EXISTS\s+)(\S.*)',
    re.IGNORECASE | re.DOTALL,
)
_INSERT_OR_REPLACE_RE = re.compile(
    r'INSERT\s+OR\s+REPLACE\s+INTO\s+(\w+)\s*\(([^)]+)\)\s+VALUES\s*\(([^)]+)\)',
    re.IGNORECASE | re.DOTALL,
)
_DATETIME_FUNC_RE = re.compile(r'\bdatetime\s*\(\s*(\w+)\s*\)', re.IGNORECASE)

# Tables where INSERT OR REPLACE requires a DELETE of the existing row first
# (i.e., tables that have a unique TEXT primary key rather than a serial id).
_REPLACE_NEEDS_DELETE = {"projects"}


def get_database_url() -> str | None:
    """
    Return the Postgres connection string if configured, else None.

    Lookup order:
    1. ``DATABASE_URL`` environment variable (Codespaces, local terminal, CI).
    2. ``st.secrets["DATABASE_URL"]`` (Streamlit Community Cloud).
    """
    url = os.getenv(DB_URL_ENV)
    if url:
        return url
    try:
        import streamlit as st

        return st.secrets.get(DB_URL_ENV) or None
    except Exception:
        return None


def get_connection():
    """
    Return a DB-API connection.

    - If DATABASE_URL is set (env var or Streamlit secrets), connect to Postgres (Neon).
    - Otherwise, fall back to local SQLite file.
    """
    db_url = get_database_url()
    if db_url:
        import psycopg2  # provided by psycopg2-binary

        # Neon requires TLS; your URL already includes sslmode=require.
        return psycopg2.connect(db_url)

    return sqlite3.connect(DB_FILE)


def get_legacy_conn(db_file: str):
    """
    Return a DB-API connection for use by legacy modules.

    - If DATABASE_URL is configured, returns a :class:`_PostgresConnAdapter` that
      wraps a psycopg2 connection and transparently translates SQLite-style SQL
      (``?`` placeholders, backtick identifiers, ``INSERT OR REPLACE``, etc.) to
      Postgres-compatible SQL.  ``db_file`` is ignored in this case.
    - Otherwise returns a plain ``sqlite3`` connection to ``db_file``.
    """
    db_url = get_database_url()
    if db_url:
        import psycopg2  # provided by psycopg2-binary

        return _PostgresConnAdapter(psycopg2.connect(db_url))

    return sqlite3.connect(db_file)


# ---------------------------------------------------------------------------
# Postgres compatibility adapter
# ---------------------------------------------------------------------------


class _PostgresCursorAdapter:
    """Wraps a psycopg2 cursor to accept SQLite-style SQL."""

    def __init__(self, pg_cursor):
        self._cursor = pg_cursor
        self.lastrowid = None
        self.rowcount = None

    # ------------------------------------------------------------------
    # SQL translation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _translate(sql: str) -> str:
        """Apply non-structural SQL translations (no INSERT OR REPLACE)."""
        # Backtick identifiers → double-quoted identifiers
        sql = _BACKTICK_RE.sub(r'"\1"', sql)
        # ? → %s (positional placeholders)
        sql = sql.replace("?", "%s")
        # ALTER TABLE … ADD COLUMN col TYPE  →  … ADD COLUMN IF NOT EXISTS col TYPE
        sql = _ALTER_ADD_COLUMN_RE.sub(r'\1IF NOT EXISTS \2', sql)
        # SQLite datetime() function → CAST(… AS TIMESTAMP)
        sql = _DATETIME_FUNC_RE.sub(r'CAST(\1 AS TIMESTAMP)', sql)
        return sql

    # ------------------------------------------------------------------
    # Core DBAPI interface
    # ------------------------------------------------------------------

    def execute(self, sql, params=()):
        params = params if params is not None else ()

        m = _INSERT_OR_REPLACE_RE.match(sql.strip())
        if m:
            table = m.group(1)
            cols_raw = m.group(2)
            vals_raw = m.group(3)
            cols = [c.strip().strip('"').strip('`') for c in cols_raw.split(',')]
            pk_col = cols[0]

            if table in _REPLACE_NEEDS_DELETE and params:
                del_sql = f'DELETE FROM {table} WHERE "{pk_col}" = %s'
                self._cursor.execute(del_sql, (params[0],))

            clean_cols = _BACKTICK_RE.sub(r'"\1"', cols_raw)
            clean_vals = vals_raw.replace("?", "%s")
            ins_sql = f"INSERT INTO {table} ({clean_cols}) VALUES ({clean_vals})"
            self._cursor.execute(ins_sql, params or None)
        else:
            self._cursor.execute(self._translate(sql), params or None)

        self.rowcount = self._cursor.rowcount
        self.lastrowid = None
        if sql.strip().upper().startswith("INSERT"):
            try:
                self._cursor.execute("SELECT lastval()")
                row = self._cursor.fetchone()
                if row:
                    self.lastrowid = row[0]
            except Exception:
                pass
        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def fetchmany(self, size=None):
        return self._cursor.fetchmany() if size is None else self._cursor.fetchmany(size)

    @property
    def description(self):
        return self._cursor.description

    def __iter__(self):
        return iter(self._cursor)


class _PostgresConnAdapter:
    """Wraps a psycopg2 connection to accept SQLite-style SQL from legacy code."""

    def __init__(self, pg_conn):
        self._conn = pg_conn

    def cursor(self):
        return _PostgresCursorAdapter(self._conn.cursor())

    def execute(self, sql, params=()):
        c = self.cursor()
        c.execute(sql, params)
        return c

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self._conn.rollback()
        else:
            self._conn.commit()
        self._conn.close()