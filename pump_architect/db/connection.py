import os
import sqlite3

DB_URL_ENV = "DATABASE_URL"

# Resolve DB path relative to the project root (two levels up from this file:
#   pump_architect/db/connection.py  →  pump_architect/db  →  pump_architect  →  project root)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_FILE = os.path.join(_PROJECT_ROOT, "architect_system.db")


def get_database_url() -> str | None:
    """
    Return the Postgres connection string if configured, else None.

    Streamlit Community Cloud exposes secrets as environment variables,
    so os.getenv() is sufficient here.
    """
    return os.getenv(DB_URL_ENV) or None


def get_connection():
    """
    Return a DB-API connection.

    - If DATABASE_URL is set, connect to Postgres (Neon).
    - Otherwise, fall back to local SQLite file.
    """
    db_url = get_database_url()
    if db_url:
        import psycopg2  # provided by psycopg2-binary

        # Neon requires TLS; your URL already includes sslmode=require.
        return psycopg2.connect(db_url)

    return sqlite3.connect(DB_FILE)