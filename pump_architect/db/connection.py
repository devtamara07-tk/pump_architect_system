
import os

def get_database_url() -> str:
    """
    Return the Postgres connection string. Raises if not set.
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL environment variable must be set for Postgres connection.")
    return db_url

def get_connection():
    """
    Return a Postgres DB-API connection. Raises if DATABASE_URL is not set.
    Uses st.cache_resource to persist connection in Streamlit.
    """
    import psycopg2  # provided by psycopg2-binary
    import streamlit as st
    db_url = get_database_url()
    try:
        @st.cache_resource(show_spinner=False)
        def _get_conn():
            return psycopg2.connect(db_url)
        return _get_conn()
    except Exception as e:
        # Defensive: never print db_url (may contain password)
        raise RuntimeError(f"Could not connect to Postgres: {e}")
