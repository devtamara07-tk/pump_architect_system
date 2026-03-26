import json
import sqlite3

import pandas as pd
import streamlit as st

from pump_architect.db.connection import get_legacy_conn, get_database_url


def _init_db_postgres(c):
    """Create all application tables on Postgres if they do not already exist."""
    c.execute('''CREATE TABLE IF NOT EXISTS pumps (
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
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS projects (
        project_id TEXT PRIMARY KEY,
        type TEXT,
        test_type TEXT,
        run_mode TEXT,
        target_val TEXT,
        created_at TIMESTAMPTZ,
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
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS project_records (
        id BIGSERIAL PRIMARY KEY,
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
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        active_tanks TEXT DEFAULT \'ALL\'
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS maintenance_events (
        id BIGSERIAL PRIMARY KEY,
        project_id TEXT NOT NULL,
        event_ts TEXT NOT NULL,
        affected_pumps_json TEXT NOT NULL,
        event_type TEXT,
        severity TEXT,
        maintenance_status TEXT,
        action_taken TEXT,
        notes TEXT,
        source_record_id INTEGER,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    )''')


def init_db(db_file):
    conn = get_legacy_conn(db_file)
    c = conn.cursor()

    if get_database_url():
        # Postgres path: create all tables at once with proper types.
        # No PRAGMA or ALTER TABLE migrations needed for a correctly provisioned DB.
        _init_db_postgres(c)
        conn.commit()
        conn.close()
        return

    # SQLite path: keep the original migration logic unchanged.
    c.execute('''CREATE TABLE IF NOT EXISTS pumps (
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
    )''')

    required_pumps_cols = [
        "pump_id",
        "project_id",
        "Pump Model",
        "ISO No.",
        "HP",
        "kW",
        "Voltage (V)",
        "Amp Min",
        "Amp Max",
        "Phase",
        "Hertz",
        "Insulation",
    ]
    pump_info = c.execute("PRAGMA table_info(pumps)").fetchall()
    existing_pump_cols = [row[1] for row in pump_info]
    if any(col not in existing_pump_cols for col in required_pumps_cols):
        c.execute("DROP TABLE IF EXISTS pumps_legacy_backup")
        c.execute("ALTER TABLE pumps RENAME TO pumps_legacy_backup")
        c.execute('''CREATE TABLE IF NOT EXISTS pumps (
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
        )''')

        legacy_cols = [
            row[1]
            for row in c.execute("PRAGMA table_info(pumps_legacy_backup)").fetchall()
        ]

        def _pick(*candidates):
            for name in candidates:
                if name in legacy_cols:
                    return f'"{name}"'
            return "''"

        c.execute(
            """
            INSERT INTO pumps (
                pump_id, project_id, "Pump Model", "ISO No.", HP, kW,
                "Voltage (V)", "Amp Min", "Amp Max", Phase, Hertz, Insulation
            )
            SELECT
                {pump_id},
                {project_id},
                {pump_model},
                {iso_no},
                {hp},
                {kw},
                {voltage},
                {amp_min},
                {amp_max},
                {phase},
                {hertz},
                {insulation}
            FROM pumps_legacy_backup
            """.format(
                pump_id=_pick("pump_id", "Pump ID"),
                project_id=_pick("project_id", "project_name"),
                pump_model=_pick("Pump Model", "model"),
                iso_no=_pick("ISO No.", "iso_no"),
                hp=_pick("HP", "hp"),
                kw=_pick("kW", "kw"),
                voltage=_pick("Voltage (V)", "voltage"),
                amp_min=_pick("Amp Min", "amp_min", "amp"),
                amp_max=_pick("Amp Max", "amp_max"),
                phase=_pick("Phase", "phase"),
                hertz=_pick("Hertz", "hertz"),
                insulation=_pick("Insulation", "insulation"),
            )
        )

    c.execute('''CREATE TABLE IF NOT EXISTS projects (
        project_id TEXT PRIMARY KEY, type TEXT, test_type TEXT,
        run_mode TEXT, target_val TEXT, created_at DATETIME)''')
    c.execute('''CREATE TABLE IF NOT EXISTS projects (
        project_id TEXT PRIMARY KEY, type TEXT, test_type TEXT,
        run_mode TEXT, target_val TEXT, created_at DATETIME, tanks TEXT)''')

    for col_def in [
        "type TEXT",
        "test_type TEXT",
        "run_mode TEXT",
        "target_val TEXT",
        "created_at DATETIME",
    ]:
        try:
            c.execute(f"ALTER TABLE projects ADD COLUMN {col_def}")
        except sqlite3.OperationalError:
            pass

    try:
        c.execute("ALTER TABLE projects ADD COLUMN tanks TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        c.execute("ALTER TABLE projects ADD COLUMN layout TEXT")
    except sqlite3.OperationalError:
        pass

    for col in ["hardware_list", "hardware_dfs", "hardware_ds"]:
        try:
            c.execute(f"ALTER TABLE projects ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass

    for col in ["step6_watchdogs", "step6_limits", "step6_event_log", "watchdog_sync_ts", "step6_extra_limits", "step6_dashboard_tracker"]:
        try:
            c.execute(f"ALTER TABLE projects ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass

    for col in ["step5_var_mapping", "step5_formulas"]:
        try:
            c.execute(f"ALTER TABLE projects ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass

    # Per-tank start dates: JSON {"Water Tank 1": "YYYY-MM-DD HH:MM:SS", ...}
    try:
        c.execute("ALTER TABLE projects ADD COLUMN tank_start_dates TEXT")
    except sqlite3.OperationalError:
        pass

    c.execute('''CREATE TABLE IF NOT EXISTS project_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    # active_tanks: "ALL" or "||"-delimited tank names contributed to this record
    try:
        c.execute("ALTER TABLE project_records ADD COLUMN active_tanks TEXT DEFAULT 'ALL'")
    except sqlite3.OperationalError:
        pass

    c.execute('''CREATE TABLE IF NOT EXISTS maintenance_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id TEXT NOT NULL,
        event_ts TEXT NOT NULL,
        affected_pumps_json TEXT NOT NULL,
        event_type TEXT,
        severity TEXT,
        maintenance_status TEXT,
        action_taken TEXT,
        notes TEXT,
        source_record_id INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    try:
        c.execute("ALTER TABLE maintenance_events ADD COLUMN maintenance_status TEXT")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()


def handle_open_project(
    db_file,
    project_id,
    restore_project_hardware_state,
    restore_project_formula_state,
):
    conn = get_legacy_conn(db_file)
    proj_row = conn.execute(
        "SELECT project_id, type, test_type, run_mode, target_val, tanks, "
        "step6_watchdogs, step6_limits, step6_event_log, watchdog_sync_ts, "
        "step6_extra_limits, layout, step6_dashboard_tracker, "
        "step5_var_mapping, step5_formulas "
        "FROM projects WHERE project_id = ?",
        (project_id,),
    ).fetchone()

    if proj_row:
        st.session_state.current_project = project_id
        st.session_state.proj_type = proj_row[1]
        st.session_state.test_type = proj_row[2]
        st.session_state.run_mode = proj_row[3]
        st.session_state.target_val = proj_row[4]
        st.session_state.water_tanks = proj_row[5].split("||") if proj_row[5] else ["Water Tank 1"]

        try:
            query = "SELECT * FROM pumps WHERE project_id = ?"
            st.session_state.active_pumps_df = pd.read_sql_query(query, conn, params=(project_id,))
        except Exception:
            st.session_state.active_pumps_df = pd.DataFrame()

        try:
            st.session_state.layout_df = (
                pd.read_json(proj_row[11])
                if len(proj_row) > 11 and proj_row[11]
                else pd.DataFrame()
            )
        except Exception:
            st.session_state.layout_df = pd.DataFrame()

        try:
            st.session_state.watchdogs_df = (
                pd.read_json(proj_row[6])
                if proj_row[6]
                else pd.DataFrame(columns=["Data Entry Method", "Watchdog Type"])
            )
        except Exception:
            st.session_state.watchdogs_df = pd.DataFrame(columns=["Data Entry Method", "Watchdog Type"])
        try:
            loaded_limits = (
                pd.read_json(proj_row[7])
                if proj_row[7]
                else pd.DataFrame(
                    columns=["Pump ID", "Max Stator Temp (°C)", "Max Current (A)"]
                )
            )
            if not isinstance(loaded_limits, pd.DataFrame) or loaded_limits.empty and len(loaded_limits.columns) == 0:
                loaded_limits = pd.DataFrame(columns=["Pump ID", "Max Stator Temp (°C)", "Max Current (A)"])
            for col in ["Pump ID", "Max Stator Temp (°C)", "Max Current (A)"]:
                if col not in loaded_limits.columns:
                    loaded_limits[col] = "" if col == "Pump ID" else 0.0
            st.session_state.limits_df = loaded_limits[["Pump ID", "Max Stator Temp (°C)", "Max Current (A)"]]
        except Exception:
            st.session_state.limits_df = pd.DataFrame(columns=["Pump ID", "Max Stator Temp (°C)", "Max Current (A)"])
        try:
            st.session_state.event_log = json.loads(proj_row[8]) if proj_row[8] else []
        except Exception:
            st.session_state.event_log = []
        st.session_state.watchdog_sync_ts = proj_row[9] if len(proj_row) > 9 and proj_row[9] else None
        try:
            st.session_state.extra_limits_df = (
                pd.read_json(proj_row[10])
                if len(proj_row) > 10 and proj_row[10]
                else pd.DataFrame(
                    columns=["Formula Name", "Min Value", "Max Value", "Applies To"]
                )
            )
        except Exception:
            st.session_state.extra_limits_df = pd.DataFrame(columns=["Formula Name", "Min Value", "Max Value", "Applies To"])
        st.session_state.dashboard_main_tracker = proj_row[12] if len(proj_row) > 12 and proj_row[12] in ["Temperature", "Current"] else "Temperature"
        restore_project_hardware_state(project_id)
        restore_project_formula_state(project_id)

        st.session_state.page = "dashboard"
        conn.close()
        st.rerun()
    conn.close()


def handle_modify_project(db_file, project_id, restore_project_formula_state):
    conn = get_legacy_conn(db_file)
    proj_row = conn.execute(
        "SELECT project_id, type, test_type, run_mode, target_val, tanks, "
        "layout, hardware_list, hardware_dfs, hardware_ds, step6_watchdogs, "
        "step6_limits, step6_event_log, watchdog_sync_ts, step6_extra_limits, "
        "step6_dashboard_tracker, step5_var_mapping, step5_formulas "
        "FROM projects WHERE project_id = ?",
        (project_id,),
    ).fetchone()

    if proj_row:
        for k in ["specs_df", "layout_df"]:
            if k in st.session_state:
                del st.session_state[k]

        extra_keys = [k for k in st.session_state.keys() if k.startswith("df_") or k.startswith("ds_")]
        for k in extra_keys:
            del st.session_state[k]

        st.session_state.project_name = proj_row[0]
        st.session_state.proj_type = proj_row[1]
        st.session_state.test_type = proj_row[2]
        st.session_state.run_mode = proj_row[3]
        st.session_state.target_val = proj_row[4]
        st.session_state.current_project = project_id

        if proj_row[5]:
            st.session_state.water_tanks = proj_row[5].split("||")
        else:
            st.session_state.water_tanks = ["Water Tank 1"]

        if proj_row[6]:
            try:
                st.session_state.layout_df = pd.read_json(proj_row[6])
            except Exception as e:
                st.warning(f"Could not restore installation layout: {e}. Starting with blank layout.")
                st.session_state.layout_df = pd.DataFrame()
        else:
            st.session_state.layout_df = pd.DataFrame()

        if len(proj_row) > 7 and proj_row[7]:
            try:
                st.session_state.hardware_list = json.loads(proj_row[7])
            except Exception:
                st.session_state.hardware_list = []
        else:
            st.session_state.hardware_list = []

        if len(proj_row) > 8 and proj_row[8]:
            try:
                dfs = json.loads(proj_row[8])
                for k, v in dfs.items():
                    st.session_state[k] = pd.read_json(v)
            except Exception:
                pass

        if len(proj_row) > 9 and proj_row[9]:
            try:
                dss = json.loads(proj_row[9])
                for k, v in dss.items():
                    st.session_state[k] = v
            except Exception:
                pass

        try:
            query = "SELECT * FROM pumps WHERE project_id = ?"
            pumps_df = pd.read_sql_query(query, conn, params=(project_id,))
            if not pumps_df.empty:
                keep_cols = [
                    "Pump Model",
                    "Pump ID",
                    "ISO No.",
                    "HP",
                    "kW",
                    "Voltage (V)",
                    "Amp Min",
                    "Amp Max",
                    "Phase",
                    "Hertz",
                    "Insulation",
                ]
                if "pump_id" in pumps_df.columns:
                    pumps_df = pumps_df.rename(columns={"pump_id": "Pump ID"})
                for col in keep_cols:
                    if col not in pumps_df.columns:
                        pumps_df[col] = "" if col not in ["HP", "kW", "Amp Min", "Amp Max", "Phase"] else 0
                st.session_state.specs_df = pumps_df[keep_cols]
        except Exception as e:
            st.warning(f"Could not restore pump specification table: {e}")

        try:
            restore_project_formula_state(project_id)
        except Exception as e:
            st.warning(f"Could not restore formulas or variable mapping: {e}")

        try:
            if len(proj_row) > 10 and proj_row[10]:
                st.session_state.watchdogs_df = pd.read_json(proj_row[10])
            else:
                st.session_state.watchdogs_df = pd.DataFrame(columns=["Data Entry Method", "Watchdog Type"])
        except Exception:
            st.session_state.watchdogs_df = pd.DataFrame(columns=["Data Entry Method", "Watchdog Type"])

        try:
            if len(proj_row) > 11 and proj_row[11]:
                loaded_limits = pd.read_json(proj_row[11])
            else:
                loaded_limits = pd.DataFrame(columns=["Pump ID", "Max Stator Temp (°C)", "Max Current (A)"])
            if not isinstance(loaded_limits, pd.DataFrame) or loaded_limits.empty and len(loaded_limits.columns) == 0:
                loaded_limits = pd.DataFrame(columns=["Pump ID", "Max Stator Temp (°C)", "Max Current (A)"])
            for col in ["Pump ID", "Max Stator Temp (°C)", "Max Current (A)"]:
                if col not in loaded_limits.columns:
                    loaded_limits[col] = "" if col == "Pump ID" else 0.0
            st.session_state.limits_df = loaded_limits[["Pump ID", "Max Stator Temp (°C)", "Max Current (A)"]]
        except Exception:
            st.session_state.limits_df = pd.DataFrame(columns=["Pump ID", "Max Stator Temp (°C)", "Max Current (A)"])

        try:
            if len(proj_row) > 12 and proj_row[12]:
                st.session_state.event_log = json.loads(proj_row[12])
            else:
                st.session_state.event_log = []
        except Exception:
            st.session_state.event_log = []

        st.session_state.watchdog_sync_ts = proj_row[13] if len(proj_row) > 13 and proj_row[13] else None
        try:
            st.session_state.extra_limits_df = (
                pd.read_json(proj_row[14])
                if len(proj_row) > 14 and proj_row[14]
                else pd.DataFrame(
                    columns=["Formula Name", "Min Value", "Max Value", "Applies To"]
                )
            )
        except Exception:
            st.session_state.extra_limits_df = pd.DataFrame(columns=["Formula Name", "Min Value", "Max Value", "Applies To"])
        st.session_state.dashboard_main_tracker = proj_row[15] if len(proj_row) > 15 and proj_row[15] in ["Temperature", "Current"] else "Temperature"

        st.session_state.page = "create"
        st.session_state.wizard_step = 1
        conn.close()
        st.rerun()
    conn.close()
