
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
    """
    import psycopg2  # provided by psycopg2-binary
    db_url = get_database_url()
    return psycopg2.connect(db_url)
