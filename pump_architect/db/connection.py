import os
import re
import sqlite3

DB_URL_ENV = "DATABASE_URL"

# Resolve DB path relative to the project root (two levels up from this file:
#   pump_architect/db/connection.py  →  pump_architect/db  →  pump_architect  →  project root)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_FILE = os.path.join(_PROJECT_ROOT, "architect_system.db")


def get_database_url() -> "str | None":
    """
    Return the Postgres connection string if configured, else None.

    Priority order:
      1. Environment variable DATABASE_URL (works in Codespaces, CI, local terminal)
      2. Streamlit secrets DATABASE_URL (works on Streamlit Community Cloud)
    """
    url = os.getenv(DB_URL_ENV)
    if url:
        return url
    try:
        import streamlit as st
        return st.secrets.get(DB_URL_ENV) or None
    except Exception:
        return None


def _is_postgres(conn) -> bool:
    """Return True if conn is a Postgres (psycopg2) connection or wrapper."""
    return isinstance(conn, _PgConnection)


class _PgCursor:
    """
    Cursor wrapper for psycopg2 that adapts SQLite-style SQL to Postgres:
    - Translates ``?`` parameter placeholders to ``%s``.
    - Translates backtick identifier quoting to double-quote quoting.
    - Rewrites ``ALTER TABLE t ADD COLUMN c TYPE`` to the IF NOT EXISTS form.
    - Rewrites ``INSERT OR REPLACE INTO t`` to a DELETE-then-INSERT.
    """

    _ALTER_ADD_RE = re.compile(
        r"(?i)ALTER\s+TABLE\s+(\S+)\s+ADD\s+COLUMN\s+(?!IF\s+NOT\s+EXISTS\s+)(.+)$",
        re.DOTALL,
    )

    def __init__(self, cur):
        self._cur = cur
        self._last_insert_id = None

    # ------------------------------------------------------------------
    # SQL adaptation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _adapt(query: str) -> str:
        """Apply all SQLite→Postgres query rewrites."""
        # 1. Backtick → double-quote for identifiers
        query = query.replace("`", '"')
        # 2. ? → %s for parameter placeholders
        query = query.replace("?", "%s")
        # 3. ALTER TABLE t ADD COLUMN c TYPE → ADD COLUMN IF NOT EXISTS c TYPE
        query = _PgCursor._ALTER_ADD_RE.sub(
            lambda m: f"ALTER TABLE {m.group(1)} ADD COLUMN IF NOT EXISTS {m.group(2)}",
            query,
        )
        return query

    def _exec_insert_or_replace(self, raw_query: str, params=None):
        """
        Translate ``INSERT OR REPLACE INTO t (cols) VALUES (...)`` to a
        DELETE-then-INSERT for Postgres.
        """
        # Extract: INSERT OR REPLACE INTO <table> (cols) VALUES (...)
        m = re.match(
            r"(?i)INSERT\s+OR\s+REPLACE\s+INTO\s+(\S+)\s*\(([^)]+)\)\s*VALUES\s*\(([^)]+)\)",
            raw_query.strip(),
            re.DOTALL,
        )
        if not m:
            # Fallback: just change to INSERT
            adapted = self._adapt("INSERT INTO" + raw_query.strip()[len("INSERT OR REPLACE INTO"):])
            self._cur.execute(adapted, params)
            return

        table = m.group(1).strip('"').strip("`")
        cols_raw = [c.strip().strip("`").strip('"') for c in m.group(2).split(",")]
        n_cols = len(cols_raw)
        ph = ", ".join(["%s"] * n_cols)
        cols_quoted = ", ".join(f'"{c}"' for c in cols_raw)
        insert_sql = f'INSERT INTO {table} ({cols_quoted}) VALUES ({ph})'

        # For tables with a primary key (projects), delete the existing row first
        # using the first column value as the PK.
        if table.lower() == "projects" and params:
            pk_col = cols_raw[0]
            self._cur.execute(f'DELETE FROM {table} WHERE "{pk_col}" = %s', (params[0],))

        self._cur.execute(insert_sql, params)

    # ------------------------------------------------------------------
    # DB-API interface
    # ------------------------------------------------------------------

    def execute(self, query: str, params=None):
        stripped = query.strip()
        if re.match(r"(?i)INSERT\s+OR\s+REPLACE\s+INTO", stripped):
            self._exec_insert_or_replace(stripped, params)
        else:
            adapted = self._adapt(stripped)
            if params is not None:
                self._cur.execute(adapted, params)
            else:
                self._cur.execute(adapted)
        return self

    def execute_returning(self, query: str, params=None):
        """Execute an INSERT … RETURNING id and store the returned id."""
        adapted = self._adapt(query)
        if params is not None:
            self._cur.execute(adapted, params)
        else:
            self._cur.execute(adapted)
        row = self._cur.fetchone()
        self._last_insert_id = row[0] if row else None
        return self

    def fetchall(self):
        return self._cur.fetchall()

    def fetchone(self):
        return self._cur.fetchone()

    @property
    def rowcount(self):
        return self._cur.rowcount

    @property
    def lastrowid(self):
        return self._last_insert_id

    @property
    def description(self):
        return self._cur.description

    def __iter__(self):
        return iter(self._cur)


class _PgConnection:
    """
    Connection wrapper for psycopg2 that:
    - Exposes ``execute()`` directly on the connection object (sqlite3 API compat).
    - Returns ``_PgCursor`` from ``cursor()``.
    """

    def __init__(self, raw_conn):
        self._conn = raw_conn

    # Expose server_version so _is_postgres works on raw psycopg2 too
    @property
    def server_version(self):
        return self._conn.server_version

    def cursor(self) -> _PgCursor:
        return _PgCursor(self._conn.cursor())

    def execute(self, query: str, params=None) -> _PgCursor:
        cur = self.cursor()
        cur.execute(query, params)
        return cur

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()

    def __getattr__(self, name):
        return getattr(self._conn, name)


def connect(db_file_or_url: str):
    """
    Return a database connection for either SQLite or Postgres.

    - If *db_file_or_url* starts with ``postgresql://`` or ``postgres://``
      a psycopg2-based :class:`_PgConnection` is returned.
    - Otherwise a standard ``sqlite3.Connection`` to the given file path is
      returned.

    All legacy code that previously called ``sqlite3.connect(db_file)``
    should call this function instead so that the Postgres path is
    automatically used when ``DATABASE_URL`` is configured.
    """
    if db_file_or_url and (
        db_file_or_url.startswith("postgresql://")
        or db_file_or_url.startswith("postgres://")
    ):
        import psycopg2  # provided by psycopg2-binary
        return _PgConnection(psycopg2.connect(db_file_or_url))
    return sqlite3.connect(db_file_or_url)


def read_sql(conn, query: str, params=None):
    """
    Execute *query* and return the result as a :class:`pandas.DataFrame`.

    Compatible with both SQLite (``sqlite3.Connection``) and Postgres
    (``_PgConnection``).  For Postgres, pandas' ``read_sql_query`` is not
    used because it requires SQLAlchemy; instead we build the DataFrame
    directly from the cursor.
    """
    import pandas as pd

    if _is_postgres(conn):
        cur = conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description] if cur.description else []
        return pd.DataFrame(rows, columns=cols)
    # sqlite3: use raw connection (pd.read_sql_query expects the native object)
    raw = conn._conn if isinstance(conn, _PgConnection) else conn
    return pd.read_sql_query(query, raw, params=params)


def get_connection():
    """
    Return a DB-API connection.

    - If DATABASE_URL is set, connect to Postgres (Neon) via :func:`connect`.
    - Otherwise, fall back to the local SQLite file.
    """
    db_url = get_database_url()
    if db_url:
        return connect(db_url)
    return sqlite3.connect(DB_FILE)