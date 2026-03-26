from pump_architect.db.connection import get_connection


def _is_postgres(conn) -> bool:
    # psycopg2 connections have a "server_version" attribute; sqlite3 doesn't.
    return hasattr(conn, "server_version")


def init_db():
    """Create all required tables if they do not already exist."""
    conn = get_connection()
    c = conn.cursor()

    is_pg = _is_postgres(conn)

    # For Postgres, use BIGSERIAL for auto-incrementing primary keys.
    # For SQLite, keep AUTOINCREMENT.
    if is_pg:
        status_log_id = "log_id BIGSERIAL PRIMARY KEY"
        sensor_id = "sensor_id BIGSERIAL PRIMARY KEY"
        setup_id = "setup_id BIGSERIAL PRIMARY KEY"
    else:
        status_log_id = "log_id INTEGER PRIMARY KEY AUTOINCREMENT"
        sensor_id = "sensor_id INTEGER PRIMARY KEY AUTOINCREMENT"
        setup_id = "setup_id INTEGER PRIMARY KEY AUTOINCREMENT"

    c.execute(
        """CREATE TABLE IF NOT EXISTS projects
           (project_id TEXT PRIMARY KEY, type TEXT, test_type TEXT, created_at DATETIME)"""
    )

    c.execute(
        """CREATE TABLE IF NOT EXISTS pumps
           (pump_id TEXT, project_id TEXT, model TEXT, iso_no TEXT, hp REAL,
            kw REAL, voltage TEXT, amp TEXT, phase INTEGER, hertz TEXT, insulation TEXT,
            tank_name TEXT, PRIMARY KEY (pump_id, project_id))"""
    )

    c.execute(
        f"""CREATE TABLE IF NOT EXISTS status_logs
            ({status_log_id}, pump_id TEXT, project_id TEXT,
             status TEXT, start_ts DATETIME, end_ts DATETIME)"""
    )

    c.execute(
        """CREATE TABLE IF NOT EXISTS test_targets
           (project_id TEXT PRIMARY KEY, run_type TEXT, test_category TEXT,
            duration REAL, duration_unit TEXT)"""
    )

    c.execute(
        f"""CREATE TABLE IF NOT EXISTS sensors
            ({sensor_id}, project_id TEXT,
             param_type TEXT, name TEXT, location TEXT, hardware TEXT)"""
    )

    c.execute(
        f"""CREATE TABLE IF NOT EXISTS hardware_setup
            ({setup_id}, project_id TEXT,
             sensor_id INTEGER, channel TEXT, record_method TEXT,
             allow_ai BOOLEAN, allow_manual BOOLEAN)"""
    )

    conn.commit()
    conn.close()