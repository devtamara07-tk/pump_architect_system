"""
check_db.py – lightweight sanity check for the database connection.

Usage
-----
Ensure DATABASE_URL is exported (or defined in .streamlit/secrets.toml), then run:

    python tools/check_db.py

The script connects to whichever database is configured (Postgres or SQLite),
reads row counts from the three main tables, and prints the results.

Exit codes
----------
0 – all counts retrieved successfully
1 – connection or query failed
"""

import os
import sys

# Allow running from the project root without installing the package.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pump_architect.db.connection import get_database_url, get_db_connection


def main():
    db_url = get_database_url()
    if db_url:
        # Mask credentials in the printed URL for safety.
        safe_url = db_url.split("@")[-1] if "@" in db_url else db_url
        print(f"[check_db] Connecting to Postgres: ...@{safe_url}")
    else:
        print("[check_db] DATABASE_URL not set – using local SQLite fallback.")

    try:
        conn = get_db_connection()
    except Exception as exc:
        print(f"[check_db] ERROR: could not open connection: {exc}", file=sys.stderr)
        sys.exit(1)

    counts = {}
    tables = ["projects", "pumps", "project_records"]
    try:
        for table in tables:
            row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            counts[table] = row[0] if row else 0
        conn.close()
    except Exception as exc:
        print(f"[check_db] ERROR querying tables: {exc}", file=sys.stderr)
        try:
            conn.close()
        except Exception:
            pass
        sys.exit(1)

    print("[check_db] Row counts:")
    for table, count in counts.items():
        print(f"  {table}: {count}")
    print("[check_db] OK")


if __name__ == "__main__":
    main()
