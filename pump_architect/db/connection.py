import os
import re
import sqlite3

DB_URL_ENV = "DATABASE_URL"

# Resolve DB path relative to the project root (two levels up from this file:
#   pump_architect/db/connection.py  →  pump_architect/db  →  pump_architect  →  project root)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_FILE = os.path.join(_PROJECT_ROOT, "architect_system.db")


def get_database_url() -> str | None:
    """
    Return the Postgres connection string if configured, else None.

    Checks, in order:
    1. ``DATABASE_URL`` environment variable (Codespaces, CI, env-var deployments).
    2. ``st.secrets["DATABASE_URL"]`` (Streamlit Community Cloud secrets).
    """
    url = os.getenv(DB_URL_ENV)
    if url:
        return url

    # Streamlit secrets (only available when running inside a Streamlit app)
    try:
        import streamlit as st  # noqa: PLC0415

        return st.secrets.get(DB_URL_ENV) or None
    except Exception:
        return None


def is_postgres(conn) -> bool:
    """Return True if *conn* is a psycopg2 (Postgres) connection."""
    return hasattr(conn, "server_version")


def adapt_sql(conn, sql: str) -> str:
    """Adapt an SQL statement for the connection's dialect.

    Applied transformations when *conn* is a Postgres connection:

    * ``?`` parameter placeholders  →  ``%s``
    * SQLite ``datetime(col)`` calls  →  bare ``col`` (ISO-format timestamps
      already sort lexicographically, so the wrapping call is unnecessary)
    * Backtick-quoted identifiers  →  double-quoted identifiers
    """
    if not is_postgres(conn):
        return sql
    sql = sql.replace("?", "%s")
    sql = re.sub(r"\bdatetime\((\w+)\)", r"\1", sql)
    sql = re.sub(r"`([^`]+)`", r'"\1"', sql)
    return sql


def get_connection(db_file: str | None = None):
    """
    Return a DB-API connection.

    - If DATABASE_URL is set, connect to Postgres (Neon).
    - Otherwise, fall back to local SQLite (using *db_file* if given, else DB_FILE).
    """
    db_url = get_database_url()
    if db_url:
        import psycopg2  # provided by psycopg2-binary

        # Neon requires TLS; your URL already includes sslmode=require.
        return psycopg2.connect(db_url)

    return sqlite3.connect(db_file if db_file else DB_FILE)