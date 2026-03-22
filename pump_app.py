
import streamlit as st
import pandas as pd
import sqlite3
import datetime
import json
from pump_architect.legacy_formula_utils import (
    parse_ts,
    safe_float,
    aggregate_temperature_for_pump,
    evaluate_math_expression,
    get_formula_target_specificity,
    get_sensor_assignment,
    get_sensor_hardware,
    build_formula_variables_for_pump,
    evaluate_formula_for_pump,
)
from pump_architect import legacy_db_utils
from pump_architect import legacy_ui_event_utils
from pump_architect import legacy_state_utils
from pump_architect import legacy_maintenance_wizard
from pump_architect import legacy_add_record_setup
from pump_architect import legacy_phase2_utils
from pump_architect import legacy_record_phases
from pump_architect import legacy_phase4_utils
from pump_architect import legacy_phase56_utils
from pump_architect import legacy_record_save_utils
from pump_architect import legacy_add_record_wizard
from pump_architect import legacy_project_form
from pump_architect import legacy_router
from pump_architect import legacy_home_page
from pump_architect import legacy_dashboard_page

current_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# --- 1. INITIALIZATION & DATABASE ---
DB_FILE = "architect_system.db"

# --- ADD THIS LINE EXACTLY HERE ---
st.set_page_config(page_title="Pump Architect", layout="wide")
# ---------------------------------
# --- 1. INITIALIZATION & DATABASE ---
DB_FILE = "architect_system.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # --- Ensure pumps table schema is correct ---
    try:
        # Try to select from the quoted column name
        c.execute('SELECT "Pump Model" FROM pumps LIMIT 1')
    except Exception:
        # If it fails, drop and recreate the table
        c.execute('DROP TABLE IF EXISTS pumps')
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
    # Fixed Table Schema
    c.execute('''CREATE TABLE IF NOT EXISTS projects (
        project_id TEXT PRIMARY KEY, type TEXT, test_type TEXT, 
        run_mode TEXT, target_val TEXT, created_at DATETIME)''')
    c.execute('''CREATE TABLE IF NOT EXISTS projects (
        project_id TEXT PRIMARY KEY, type TEXT, test_type TEXT,
        run_mode TEXT, target_val TEXT, created_at DATETIME, tanks TEXT)''')



    # --- MIGRATION: Add tanks column if missing ---
    try:
        c.execute("ALTER TABLE projects ADD COLUMN tanks TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists, ignore error

    # --- MIGRATION: Add layout column if missing ---
    try:
        c.execute("ALTER TABLE projects ADD COLUMN layout TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists, ignore error

    # --- MIGRATION: Add hardware/sensor mapping columns if missing ---
    for col in ["hardware_list", "hardware_dfs", "hardware_ds"]:
        try:
            c.execute(f"ALTER TABLE projects ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass

    # --- MIGRATION: Add Step 6 columns if missing ---
    for col in ["step6_watchdogs", "step6_limits", "step6_event_log", "watchdog_sync_ts", "step6_extra_limits", "step6_dashboard_tracker"]:
        try:
            c.execute(f"ALTER TABLE projects ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass

    # --- MIGRATION: Add Step 5 formula columns if missing ---
    for col in ["step5_var_mapping", "step5_formulas"]:
        try:
            c.execute(f"ALTER TABLE projects ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass

    # --- RECORDS TABLE: Stores Add New Record payloads from dashboard ---
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

    # Migration for older DBs created before maintenance_status field existed
    try:
        c.execute("ALTER TABLE maintenance_events ADD COLUMN maintenance_status TEXT")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

if "page" not in st.session_state: st.session_state.page = "home"
if "wizard_step" not in st.session_state: st.session_state.wizard_step = 1

# --- 2. RESTORED INDUSTRIAL DARK UI CSS (18px Fonts) ---
def inject_industrial_css():
    return legacy_ui_event_utils.inject_industrial_css()

def queue_confirmation(message):
    return legacy_ui_event_utils.queue_confirmation(message)

def render_confirmation_banner():
    return legacy_ui_event_utils.render_confirmation_banner()

def get_project_records(project_id):
    return legacy_db_utils.get_project_records(DB_FILE, project_id)

def get_latest_record(project_id):
    return legacy_db_utils.get_latest_record(DB_FILE, project_id)

def build_phase4_hardware_plan(pump_ids, status_grid):
    return legacy_state_utils.build_phase4_hardware_plan(pump_ids, status_grid)

def has_baseline_record(project_id):
    return legacy_db_utils.has_baseline_record(DB_FILE, project_id)

def clear_project_records(project_id):
    return legacy_db_utils.clear_project_records(DB_FILE, project_id)

def clear_project_maintenance_events(project_id):
    return legacy_db_utils.clear_project_maintenance_events(DB_FILE, project_id)

def restore_project_formula_state(project_id):
    return legacy_state_utils.restore_project_formula_state(DB_FILE, project_id)

def persist_event_log_for_project(project_id):
    return legacy_ui_event_utils.persist_event_log_for_project(DB_FILE, project_id)

def add_event_log_entry(text):
    return legacy_ui_event_utils.add_event_log_entry(text)

def auto_close_maintenance_for_stable_pumps(project_id, stable_pumps):
    return legacy_ui_event_utils.auto_close_maintenance_for_stable_pumps(
        DB_FILE,
        project_id,
        stable_pumps,
        get_maintenance_events,
    )

def build_dashboard_report_csv(project_id):
    return legacy_ui_event_utils.build_dashboard_report_csv(
        project_id,
        get_latest_record,
        get_maintenance_events,
    )

def restore_project_hardware_state(project_id):
    return legacy_state_utils.restore_project_hardware_state(DB_FILE, project_id)

def get_maintenance_events(project_id):
    return legacy_db_utils.get_maintenance_events(DB_FILE, project_id)

def render_add_maintenance_wizard():
    return legacy_maintenance_wizard.render_add_maintenance_wizard(
        DB_FILE,
        inject_industrial_css,
        parse_ts,
        get_maintenance_events,
        add_event_log_entry,
        persist_event_log_for_project,
        queue_confirmation,
    )

def render_add_record_wizard():
    return legacy_add_record_wizard.render_add_record_wizard(DB_FILE)

# --- 3. THE WIZARD (FULL STEPS RESTORED) ---
def render_project_form():
    return legacy_project_form.render_project_form(DB_FILE)
# --- HELPER FUNCTIONS ---
def handle_open_project(project_id):
    conn = sqlite3.connect(DB_FILE)
    # 1. Load the core project info
    proj_row = conn.execute("SELECT project_id, type, test_type, run_mode, target_val, tanks, step6_watchdogs, step6_limits, step6_event_log, watchdog_sync_ts, step6_extra_limits, layout, step6_dashboard_tracker, step5_var_mapping, step5_formulas FROM projects WHERE project_id = ?", (project_id,)).fetchone()
    
    if proj_row:
        st.session_state.current_project = project_id
        st.session_state.proj_type = proj_row[1]
        st.session_state.test_type = proj_row[2]
        st.session_state.run_mode = proj_row[3]
        st.session_state.target_val = proj_row[4]
        st.session_state.water_tanks = proj_row[5].split("||") if proj_row[5] else ["Water Tank 1"]
        
        # 2. Load the pumps into the active session
        try:
            query = "SELECT * FROM pumps WHERE project_id = ?"
            st.session_state.active_pumps_df = pd.read_sql_query(query, conn, params=(project_id,))
        except:
            st.session_state.active_pumps_df = pd.DataFrame()

        try:
            st.session_state.layout_df = pd.read_json(proj_row[11]) if len(proj_row) > 11 and proj_row[11] else pd.DataFrame()
        except Exception:
            st.session_state.layout_df = pd.DataFrame()

        # 3. Load Step 6 configuration for dashboard display
        try:
            st.session_state.watchdogs_df = pd.read_json(proj_row[6]) if proj_row[6] else pd.DataFrame(columns=["Data Entry Method", "Watchdog Type"])
        except Exception:
            st.session_state.watchdogs_df = pd.DataFrame(columns=["Data Entry Method", "Watchdog Type"])
        try:
            loaded_limits = pd.read_json(proj_row[7]) if proj_row[7] else pd.DataFrame(columns=["Pump ID", "Max Stator Temp (°C)", "Max Current (A)"])
            if not isinstance(loaded_limits, pd.DataFrame) or loaded_limits.empty and len(loaded_limits.columns) == 0:
                loaded_limits = pd.DataFrame(columns=["Pump ID", "Max Stator Temp (°C)", "Max Current (A)"])
            for col in ["Pump ID", "Max Stator Temp (°C)", "Max Current (A)"]:
                if col not in loaded_limits.columns:
                    loaded_limits[col] = "" if col == "Pump ID" else 0.0
            st.session_state.limits_df = loaded_limits[["Pump ID", "Max Stator Temp (°C)", "Max Current (A)"]]
        except Exception:
            st.session_state.limits_df = pd.DataFrame(columns=["Pump ID", "Max Stator Temp (°C)", "Max Current (A)"])
        try:
            import json
            st.session_state.event_log = json.loads(proj_row[8]) if proj_row[8] else []
        except Exception:
            st.session_state.event_log = []
        st.session_state.watchdog_sync_ts = proj_row[9] if len(proj_row) > 9 and proj_row[9] else None
        try:
            st.session_state.extra_limits_df = pd.read_json(proj_row[10]) if len(proj_row) > 10 and proj_row[10] else pd.DataFrame(columns=["Formula Name", "Min Value", "Max Value", "Applies To"])
        except Exception:
            st.session_state.extra_limits_df = pd.DataFrame(columns=["Formula Name", "Min Value", "Max Value", "Applies To"])
        st.session_state.dashboard_main_tracker = proj_row[12] if len(proj_row) > 12 and proj_row[12] in ["Temperature", "Current"] else "Temperature"
        restore_project_hardware_state(project_id)
        restore_project_formula_state(project_id)

        # 3. Switch to Dashboard Page
        st.session_state.page = "dashboard"
        conn.close()
        st.rerun()
    conn.close()

def handle_modify_project(project_id):
    conn = sqlite3.connect(DB_FILE)
    # Fetch all columns for project
    proj_row = conn.execute("SELECT project_id, type, test_type, run_mode, target_val, tanks, layout, hardware_list, hardware_dfs, hardware_ds, step6_watchdogs, step6_limits, step6_event_log, watchdog_sync_ts, step6_extra_limits, step6_dashboard_tracker, step5_var_mapping, step5_formulas FROM projects WHERE project_id = ?", (project_id,)).fetchone()


    if proj_row:
        # --- Step 0: Clear previous session state for tables ---
        for k in ["specs_df", "layout_df"]:
            if k in st.session_state:
                del st.session_state[k]
        # Also clear all hardware config DataFrames and Data Source lists
        extra_keys = [k for k in st.session_state.keys() if k.startswith("df_") or k.startswith("ds_")]
        for k in extra_keys:
            del st.session_state[k]

        # --- Step 1: Restore project metadata ---
        st.session_state.project_name = proj_row[0]
        st.session_state.proj_type = proj_row[1]
        st.session_state.test_type = proj_row[2]
        st.session_state.run_mode = proj_row[3]
        st.session_state.target_val = proj_row[4]
        st.session_state.current_project = project_id

        # --- Step 3: Restore tanks ---
        if proj_row[5]:
            st.session_state.water_tanks = proj_row[5].split("||")
        else:
            st.session_state.water_tanks = ["Water Tank 1"]

        # --- Step 3: Restore layout_df ---
        if proj_row[6]:
            try:
                st.session_state.layout_df = pd.read_json(proj_row[6])
            except Exception as e:
                st.warning(f"Could not restore installation layout: {e}. Starting with blank layout.")
                st.session_state.layout_df = pd.DataFrame()
        else:
            st.session_state.layout_df = pd.DataFrame()

        # --- Step 4: Restore hardware mapping DataFrames and lists ---
        import json
        # hardware_list
        if len(proj_row) > 7 and proj_row[7]:
            try:
                st.session_state.hardware_list = json.loads(proj_row[7])
            except Exception as e:
                st.session_state.hardware_list = []
        else:
            st.session_state.hardware_list = []
        # hardware_dfs
        if len(proj_row) > 8 and proj_row[8]:
            try:
                dfs = json.loads(proj_row[8])
                for k, v in dfs.items():
                    st.session_state[k] = pd.read_json(v)
            except Exception as e:
                pass
        # hardware_ds
        if len(proj_row) > 9 and proj_row[9]:
            try:
                dss = json.loads(proj_row[9])
                for k, v in dss.items():
                    st.session_state[k] = v
            except Exception as e:
                pass

        # --- Step 2: Restore Pump Specification Table ---
        try:
            query = "SELECT * FROM pumps WHERE project_id = ?"
            pumps_df = pd.read_sql_query(query, conn, params=(project_id,))
            if not pumps_df.empty:
                keep_cols = ["Pump Model", "Pump ID", "ISO No.", "HP", "kW", "Voltage (V)", "Amp Min", "Amp Max", "Phase", "Hertz", "Insulation"]
                # Ensure Pump ID column exists
                if "pump_id" in pumps_df.columns:
                    pumps_df = pumps_df.rename(columns={"pump_id": "Pump ID"})
                # Fill missing columns with default values
                for col in keep_cols:
                    if col not in pumps_df.columns:
                        pumps_df[col] = "" if col not in ["HP", "kW", "Amp Min", "Amp Max", "Phase"] else 0
                st.session_state.specs_df = pumps_df[keep_cols]
        except Exception as e:
            st.warning(f"Could not restore pump specification table: {e}")

        # --- Step 4: Restore hardware mapping DataFrames (if present) ---
        # (REMOVED: Deletion of df_*/ds_* keys after restore, as this wipes out restored state)

        # --- Step 5: Restore formulas and variable mapping ---
        try:
            restore_project_formula_state(project_id)
        except Exception as e:
            st.warning(f"Could not restore formulas or variable mapping: {e}")

        # --- Step 6: Restore watchdogs, safety limits, and event log ---
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
            import json
            if len(proj_row) > 12 and proj_row[12]:
                st.session_state.event_log = json.loads(proj_row[12])
            else:
                st.session_state.event_log = []
        except Exception:
            st.session_state.event_log = []

        st.session_state.watchdog_sync_ts = proj_row[13] if len(proj_row) > 13 and proj_row[13] else None
        try:
            st.session_state.extra_limits_df = pd.read_json(proj_row[14]) if len(proj_row) > 14 and proj_row[14] else pd.DataFrame(columns=["Formula Name", "Min Value", "Max Value", "Applies To"])
        except Exception:
            st.session_state.extra_limits_df = pd.DataFrame(columns=["Formula Name", "Min Value", "Max Value", "Applies To"])
        st.session_state.dashboard_main_tracker = proj_row[15] if len(proj_row) > 15 and proj_row[15] in ["Temperature", "Current"] else "Temperature"

        # --- Set wizard state and rerun ---
        st.session_state.page = "create"
        st.session_state.wizard_step = 1
        conn.close()
        st.rerun()
    conn.close()

# --- 4. MAIN ROUTING & HOME (Original 18px Headers) ---
init_db()
inject_industrial_css()
render_confirmation_banner()

simple_page_handled = legacy_router.route_simple_pages(
    st.session_state.page,
    render_project_form,
    render_add_record_wizard,
    render_add_maintenance_wizard,
)

if not simple_page_handled and st.session_state.page == "home":
    legacy_home_page.render_home_page(
        DB_FILE,
        handle_open_project,
        handle_modify_project,
    )

elif not simple_page_handled and st.session_state.page == "dashboard":
    legacy_dashboard_page.render_dashboard_page(
        DB_FILE,
        get_latest_record,
        get_project_records,
        get_maintenance_events,
        build_dashboard_report_csv,
        add_event_log_entry,
        persist_event_log_for_project,
        clear_project_records,
        clear_project_maintenance_events,
        queue_confirmation,
    )
