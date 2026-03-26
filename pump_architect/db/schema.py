from pump_architect.db.connection import get_connection, is_postgres as _is_postgres


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


def init_legacy_db():
    """Create (or verify) all tables required by the legacy Streamlit app.

    This is Postgres-compatible and is used instead of
    ``legacy_project_state.init_db()`` when a ``DATABASE_URL`` is configured.
    For SQLite, ``legacy_project_state.init_db()`` is still used so that
    backward-compatible column migrations are applied to existing databases.
    """
    conn = get_connection()
    c = conn.cursor()
    is_pg = _is_postgres(conn)

    # Dialect-specific type tokens
    int_pk = "BIGSERIAL PRIMARY KEY" if is_pg else "INTEGER PRIMARY KEY AUTOINCREMENT"
    ts_type = "TIMESTAMP" if is_pg else "DATETIME"

    # Full projects table with every column used by the legacy app
    c.execute(
        f"""CREATE TABLE IF NOT EXISTS projects (
            project_id TEXT PRIMARY KEY,
            type TEXT,
            test_type TEXT,
            run_mode TEXT,
            target_val TEXT,
            created_at {ts_type},
            tanks TEXT,
            layout TEXT,
            hardware_list TEXT,
            hardware_dfs TEXT,
            hardware_ds TEXT,
            step6_watchdogs TEXT,
            step6_limits TEXT,
            step6_event_log TEXT,
            watchdog_sync_ts TEXT,
            step6_extra_limits TEXT,
            step6_dashboard_tracker TEXT,
            step5_var_mapping TEXT,
            step5_formulas TEXT,
            tank_start_dates TEXT
        )"""
    )

    # Legacy pumps table (column names match the app's DataFrame column names)
    c.execute(
        """CREATE TABLE IF NOT EXISTS pumps (
            pump_id TEXT,
            project_id TEXT,
            "Pump Model" TEXT,
            "ISO No." TEXT,
            HP TEXT,
            kW TEXT,
            "Voltage (V)" TEXT,
            "Amp Min" TEXT,
            "Amp Max" TEXT,
            Phase TEXT,
            Hertz TEXT,
            Insulation TEXT
        )"""
    )

    # Project data-records table
    c.execute(
        f"""CREATE TABLE IF NOT EXISTS project_records (
            id {int_pk},
            project_id TEXT NOT NULL,
            record_phase TEXT NOT NULL,
            record_ts TEXT NOT NULL,
            method TEXT,
            ambient_temp REAL,
            tank_temps_json TEXT,
            status_grid_json TEXT,
            pump_readings_json TEXT,
            alarms_json TEXT,
            ack_alarm INTEGER DEFAULT 0,
            active_tanks TEXT DEFAULT 'ALL',
            created_at {ts_type} DEFAULT CURRENT_TIMESTAMP
        )"""
    )

    # Maintenance events table
    c.execute(
        f"""CREATE TABLE IF NOT EXISTS maintenance_events (
            id {int_pk},
            project_id TEXT NOT NULL,
            event_ts TEXT NOT NULL,
            affected_pumps_json TEXT NOT NULL,
            event_type TEXT,
            severity TEXT,
            maintenance_status TEXT,
            action_taken TEXT,
            notes TEXT,
            source_record_id INTEGER,
            created_at {ts_type} DEFAULT CURRENT_TIMESTAMP
        )"""
    )

    conn.commit()
    conn.close()