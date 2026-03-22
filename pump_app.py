
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

if st.session_state.page == "home":
    st.markdown('<div class="hero-bg"><h1 style="color:white; letter-spacing:2px; font-size:3rem;">PUMP ARCHITECT SYSTEM</h1><p style="color:#aaa; font-size:1.5rem;">Control Center v2.0</p></div>', unsafe_allow_html=True)
    
    if st.button("Create New Project"):
        # Clear all user input fields and Step 2 table
        for k in [
            "project_name", "proj_type", "test_type", "run_mode", "target_val", "target_unit",
            "specs_df", "layout_df", "water_tanks", "hardware_list", "var_mapping_df", "formulas_df",
            "watchdogs_df", "watchdog_matrix_df", "limits_df", "extra_limits_df", "event_log", "wizard_step", "current_project", "dashboard_main_tracker",
            "add_record_draft", "maintenance_prefill_pumps", "maintenance_source_record_id"
        ]:
            if k in st.session_state:
                del st.session_state[k]
        # Also clear all hardware config DataFrames and Data Source lists
        extra_keys = [k for k in st.session_state.keys() if k.startswith("df_") or k.startswith("ds_")]
        for k in extra_keys:
            del st.session_state[k]
        st.session_state.page = "create"
        st.session_state.wizard_step = 1
        st.rerun()
    
    st.write("")
    st.markdown("<div class='table-title' style='color:white; font-size:24px; font-weight:bold;'>CURRENT PROJECTS</div>", unsafe_allow_html=True)
    
    # Original Ratios [0.4, 1.2, 2.5, 1.3, 3.6]
    h = st.columns([0.4, 1.2, 2.5, 1.3, 3.6])
    for col, txt in zip(h, ["No.", "Status", "Name", "Date", "Actions"]):
        col.markdown(f"<div class='col-header'>{txt}</div>", unsafe_allow_html=True)

    conn = sqlite3.connect(DB_FILE)
    projs = conn.execute("SELECT project_id, type, test_type, created_at FROM projects ORDER BY created_at DESC").fetchall()
    
    for idx, p in enumerate(projs):
        # Actions column (3.6) split into three 1.2 buttons
        c = st.columns([0.4, 1.2, 2.5, 1.3, 1.2, 1.2, 1.2])
        
        c[0].markdown(f"<div class='white-text'>{idx+1}</div>", unsafe_allow_html=True)
        c[1].markdown('<div class="status-pill">Standby</div>', unsafe_allow_html=True)
        # Existing Status, Name, and Date rendering...
        c[2].markdown(f"<div class='white-text'>{p[0]}</div>", unsafe_allow_html=True)
        date_str = str(p[3])[:10] if p[3] else "N/A"
        c[3].markdown(f"<div class='white-text'>{date_str}</div>", unsafe_allow_html=True)
        
        # ACTIONS
        if c[4].button("Open", key=f"o{idx}", use_container_width=True): 
            handle_open_project(p[0]) # p[0] is the project_id/name
            
        # --- UPDATED MODIFY BUTTON ---
        if c[5].button("Modify", key=f"m{idx}", use_container_width=True):
            handle_modify_project(p[0]) # p[0] is project_id from your SELECT
            
        # --- CLEAN DELETE WITH CONFIRMATION ---
        confirm_key = f"delete_confirm_{idx}"

        if st.session_state.get(confirm_key, False):
            # We use a single column here to keep the "SURE?" button from squishing
            if c[6].button("⚠️ CONFIRM", key=f"conf_{idx}", use_container_width=True, type="primary"):
                conn = sqlite3.connect(DB_FILE)
                # 1. Delete from projects
                conn.execute("DELETE FROM projects WHERE project_id=?", (p[0],))
                
                # 2. Delete from pumps (Using the first column as the reference)
                # If project_name fails, we use positional index if needed
                try:
                    conn.execute("DELETE FROM pumps WHERE project_name=?", (p[0],))
                except sqlite3.OperationalError:
                    # Fallback: In some versions of your DB, the column is the 2nd one
                    # We try to find the column name dynamically
                    cursor = conn.execute("PRAGMA table_info(pumps)")
                    cols = [info[1] for info in cursor.fetchall()]
                    actual_col = cols[1] # Usually the 2nd column is the project link
                    conn.execute(f"DELETE FROM pumps WHERE {actual_col}=?", (p[0],))
                
                conn.commit()
                conn.close()
                del st.session_state[confirm_key]
                st.rerun()
            
            # Small "cancel" text link instead of a bulky button to save the layout
            if c[6].button("Cancel", key=f"can_{idx}", use_container_width=True):
                del st.session_state[confirm_key]
                st.rerun()
        else:
            if c[6].button("Delete", key=f"d{idx}", use_container_width=True):
                st.session_state[confirm_key] = True
                st.rerun()

elif st.session_state.page == "create":
    render_project_form()

elif st.session_state.page == "add_record":
    render_add_record_wizard()

elif st.session_state.page == "add_maintenance":
    render_add_maintenance_wizard()

elif st.session_state.page == "dashboard":
    # 1. Custom CSS for the dark industrial look (No Icons)
    st.markdown("""
        <style>
        .dash-bg { background-color: #0E1117; color: white; font-family: sans-serif; }
        .panel { background-color: #1C1F24; border-radius: 8px; padding: 15px; margin-bottom: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); border: 1px solid #2A2D34; }
        .panel-title { font-size: 16px; color: #FFFFFF; font-weight: bold; letter-spacing: 1px; margin-bottom: 10px; text-transform: uppercase; }
        .value-green { color: #2ECC71; font-size: 36px; font-weight: bold; line-height: 1; margin: 5px 0; }
        .value-grey { color: #888; font-size: 36px; font-weight: bold; line-height: 1; margin: 5px 0; }
        .status-light-run { height: 20px; width: 20px; background-color: #2ECC71; border-radius: 50%; display: inline-block; box-shadow: 0 0 10px #2ECC71; }
        .status-light-stop { height: 20px; width: 20px; background-color: #555; border-radius: 50%; display: inline-block; }
        .header-title { font-size: 22px; font-weight: bold; letter-spacing: 1px; color: #3498DB; text-transform: uppercase; margin-bottom: 5px; }
        .event-log-text { font-size: 13px; color: #AAA; font-family: monospace; margin-bottom: 4px; }
        .event-alert { color: #E74C3C; font-weight: bold; }
        </style>
    """, unsafe_allow_html=True)

    # 2. Fetch REAL Database Info for this Project
    project_name = st.session_state.get('current_project', 'UNKNOWN PROJECT')
    
    conn = sqlite3.connect(DB_FILE)
    proj_row = conn.execute("SELECT run_mode, target_val, test_type FROM projects WHERE project_id = ?", (project_name,)).fetchone()
    conn.close()
    
    # Extract data or default if missing
    run_mode = proj_row[0] if proj_row and proj_row[0] else "Continuous"
    target_val = proj_row[1] if proj_row and proj_row[1] else "0"
    test_type = proj_row[2] if proj_row and proj_row[2] else ""
    latest_record = get_latest_record(project_name)
    latest_status_grid = latest_record.get("status_grid", {}) if latest_record else {}
    records_df = get_project_records(project_name)
    record_count = len(records_df)

    maintenance_df = get_maintenance_events(project_name)
    maintenance_count = len(maintenance_df) if isinstance(maintenance_df, pd.DataFrame) else 0
    maint_by_pump = {}
    unresolved_maintenance_rows = []
    if isinstance(maintenance_df, pd.DataFrame) and not maintenance_df.empty:
        for _, m_row in maintenance_df.iterrows():
            m_status = str(m_row.get("maintenance_status", "Open") or "Open").strip()
            try:
                affected = json.loads(m_row.get("affected_pumps_json", "[]") or "[]")
            except Exception:
                affected = []
            if m_status != "Closed":
                unresolved_maintenance_rows.append(m_row)

            for pid in affected:
                pid = str(pid).strip()
                if not pid:
                    continue
                if m_status != "Closed" and pid not in maint_by_pump:
                    maint_by_pump[pid] = {
                        "event_ts": m_row.get("event_ts", ""),
                        "event_type": m_row.get("event_type", ""),
                        "severity": m_row.get("severity", ""),
                        "maintenance_status": m_status,
                        "action_taken": m_row.get("action_taken", ""),
                    }

    # Main Header
    st.markdown(f"""
        <div style="background:#1C1F24; padding:20px; border-radius:10px; border-left: 5px solid #3498DB; margin-bottom:20px;">
            <div class="header-title">PUMP ARCHITECT SYSTEM</div>
            <div style="color:white; font-size: 28px; font-weight: bold; letter-spacing: 1px;">PROJECT: {project_name}</div>
        </div>
    """, unsafe_allow_html=True)

    # 3. Dynamic Progress Bar (Uses real target values from the database)
    is_cycle_test = "Cycle" in test_type or "Intermittent" in test_type or "Cycle" in run_mode
    
    total_acc_value = 0.0
    if isinstance(latest_status_grid, dict) and latest_status_grid:
        try:
            total_acc_value = sum(float(item.get("acc_hours", 0.0) or 0.0) for item in latest_status_grid.values())
        except Exception:
            total_acc_value = 0.0
    try:
        target_val_num = float(target_val)
    except Exception:
        target_val_num = 0.0
    progress_pct = 0.0 if target_val_num <= 0 else max(0.0, min(100.0, (total_acc_value / target_val_num) * 100.0))

    if is_cycle_test:
        bar_title = "TOTAL MISSION CYCLES"
        bar_value = f"{total_acc_value:.1f} / {target_val} cycles"
        bar_color = "#3498DB" 
    else:
        bar_title = "TOTAL MISSION RUN TIME"
        bar_value = f"{total_acc_value:.1f} / {target_val} hrs"
        bar_color = "#EEDD82" 

    st.markdown(f"""
        <div class="panel" style="margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between;"><span class="panel-title">{bar_title}</span> <span style="font-weight:bold; color:white; font-size:16px;">{bar_value}</span></div>
            <div style="background: #333; height: 12px; border-radius: 6px; margin-top: 8px;"><div style="background: {bar_color}; width: {progress_pct:.1f}%; height: 100%; border-radius: 6px;"></div></div>
        </div>
    """, unsafe_allow_html=True)

    # 4. Main Grid Split (Left: Watchdog & Actions, Right: Pumps)
    col_left, col_right = st.columns([1.2, 3])

    with col_left:
        st.markdown("<div class='header-title' style='font-size: 18px; color:white;'>SYSTEM WATCHDOG</div>", unsafe_allow_html=True)

        wd_df = st.session_state.get("watchdogs_df", pd.DataFrame(columns=["Data Entry Method", "Watchdog Type"]))
        watchdog_rows_html = ""
        if isinstance(wd_df, pd.DataFrame) and not wd_df.empty:
            grouped_watchdogs = {}
            for _, row in wd_df.iterrows():
                method = str(row.get("Data Entry Method", "-")).strip() or "-"
                wd_type = str(row.get("Watchdog Type", "-")).strip() or "-"
                grouped_watchdogs.setdefault(method, [])
                if wd_type not in grouped_watchdogs[method]:
                    grouped_watchdogs[method].append(wd_type)

            for method, wd_types in grouped_watchdogs.items():
                has_conn = "Connection Status (ONLINE/OFFLINE)" in wd_types
                has_onoff = "ON/OFF" in wd_types
                has_temp = "ESP32 Internal Temperature" in wd_types

                if has_conn and has_onoff and has_temp:
                    method_status = "HEALTHY"
                    method_status_color = "#2ECC71"
                elif has_conn and has_onoff:
                    method_status = "READY"
                    method_status_color = "#2ECC71"
                elif has_conn:
                    method_status = "ONLINE"
                    method_status_color = "#2ECC71"
                elif has_onoff:
                    method_status = "LOCAL ONLY"
                    method_status_color = "#EEDD82"
                elif has_temp:
                    method_status = "MONITOR"
                    method_status_color = "#3498DB"
                else:
                    method_status = "UNCONFIGURED"
                    method_status_color = "#888"

                watchdog_rows_html += (
                    f"<div style=\"display: flex; justify-content: space-between; align-items: center; margin-top: 8px; margin-bottom: 6px;\">"
                    f"<span style=\"color:#3498DB; font-size:13px; font-weight:700; text-transform: uppercase;\">{method}</span>"
                    f"<span style=\"color:{method_status_color}; border: 1px solid {method_status_color}; padding: 2px 8px; border-radius: 999px; font-size:11px; font-weight:700;\">{method_status}</span>"
                    "</div>"
                )
                for wd_type in wd_types:
                    if wd_type == "ON/OFF":
                        wd_value = "ON"
                        wd_color = "#2ECC71"
                    elif wd_type == "Connection Status (ONLINE/OFFLINE)":
                        wd_value = "ONLINE"
                        wd_color = "#2ECC71"
                    elif wd_type == "ESP32 Internal Temperature":
                        wd_value = "36.5°C"
                        wd_color = "#3498DB"
                    else:
                        wd_value = "ACTIVE"
                        wd_color = "#2ECC71"

                    watchdog_rows_html += (
                        f"<div style=\"display: flex; justify-content: space-between; margin-bottom: 8px; border-bottom: 1px solid #2A2D34; padding-bottom: 6px;\">"
                        f"<span style=\"color:white; font-size:13px;\">{wd_type}</span>"
                        f"<span style=\"color:{wd_color}; font-weight:bold;\">{wd_value}</span>"
                        "</div>"
                    )
        else:
            watchdog_rows_html = (
                "<div style=\"display: flex; justify-content: space-between; margin-bottom: 8px;\">"
                "<span style=\"color:white; font-size:14px;\">No watchdog configured</span>"
                "<span style=\"color:#888; font-weight:bold;\">STANDBY</span>"
                "</div>"
            )

        sync_ts = st.session_state.get("watchdog_sync_ts", None)
        sync_footer = (
            f"<div style=\"margin-top:10px; padding-top:6px; border-top:1px solid #333; color:#555; font-size:11px;\">Last config sync: {sync_ts}</div>"
            if sync_ts else
            "<div style=\"margin-top:10px; padding-top:6px; border-top:1px solid #333; color:#555; font-size:11px;\">Last config sync: not yet saved</div>"
        )
        st.markdown(f"""
            <div class="panel">
                <div class="panel-title">DATA ENTRY WATCHDOGS</div>
                {watchdog_rows_html}
                {sync_footer}
            </div>
        """, unsafe_allow_html=True)
        
        # --- EVENT ALARM LOG ---
        event_log = st.session_state.get("event_log", [])
        event_html = ""
        if event_log:
            for entry in event_log[:30]:
                event_html += f"<div class='event-log-text'>{entry}</div>"
        else:
            event_html = (
                "<div class='event-log-text'>SYSTEM IN STANDBY</div>"
                "<div class='event-log-text'>AWAITING TEST INITIATION...</div>"
            )

        st.markdown(f"""
            <div class="panel" style="height: 200px; overflow-y: auto;">
                <div class="panel-title">EVENT ALARM LOG</div>
                {event_html}
            </div>
        """, unsafe_allow_html=True)

        # --- MAINTENANCE SUMMARY ---
        maint_total = len(maintenance_df) if isinstance(maintenance_df, pd.DataFrame) else 0
        maint_open_total = len(unresolved_maintenance_rows)
        maint_critical_open = 0
        for m_row in unresolved_maintenance_rows:
            if str(m_row.get("severity", "")).strip().upper() == "CRITICAL":
                maint_critical_open += 1
        recent_maint_html = ""
        if maint_open_total > 0:
            unresolved_df = pd.DataFrame(unresolved_maintenance_rows)
            for _, m_row in unresolved_df.head(5).iterrows():
                try:
                    pumps = ", ".join(json.loads(m_row.get("affected_pumps_json", "[]") or "[]"))
                except Exception:
                    pumps = "-"
                recent_maint_html += (
                    f"<div style='font-size:12px; color:#E0E6F0; margin-bottom:6px;'>"
                    f"{m_row.get('event_ts', '')} | {m_row.get('event_type', '')} ({m_row.get('severity', '')}) [{m_row.get('maintenance_status', 'Open')}]"
                    f"<br/><span style='color:#9FB3C8;'>Pumps: {pumps}</span></div>"
                )
        else:
            recent_maint_html = "<div class='event-log-text'>No unresolved maintenance events</div>"

        st.markdown(
            f"""
            <div class="panel" style="max-height: 180px; overflow-y: auto;">
                <div class="panel-title">MAINTENANCE SUMMARY</div>
                <div style='font-size:12px; color:#FFFFFF; margin-bottom:8px;'>Total Events: <b>{maint_total}</b> | Open: <b>{maint_open_total}</b> | Critical Open: <b>{maint_critical_open}</b></div>
                {recent_maint_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div class="panel" style="max-height: 130px; overflow-y: auto;">
                <div class="panel-title">MAINTENANCE LEGEND</div>
                <div style='font-size:12px; color:#FFFFFF; margin-bottom:4px;'>Status: <span style='color:#F59E0B;'>Open / In Progress</span> | <span style='color:#9CA3AF;'>Closed</span></div>
                <div style='font-size:12px; color:#FFFFFF;'>Severity: <span style='color:#EF4444;'>Critical</span> | <span style='color:#F59E0B;'>High</span> | <span style='color:#3B82F6;'>Medium</span> | <span style='color:#22C55E;'>Low</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.divider()

        # --- ACTION BUTTONS (Icons Removed) ---
        if st.button("Add New Record", use_container_width=True, key="btn_add_record"):
            st.session_state.page = "add_record"
            st.session_state.add_record_draft = {}
            st.rerun()

        if st.button("Add New Maintenance", use_container_width=True, key="btn_add_maint"):
            st.session_state.maintenance_prefill_pumps = []
            st.session_state.maintenance_source_record_id = None
            st.session_state.page = "add_maintenance"
            st.rerun()
        report_csv = build_dashboard_report_csv(project_name)
        report_name_ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        report_clicked = st.download_button(
            "Print Report",
            data=report_csv,
            file_name=f"{project_name}_dashboard_report_{report_name_ts}.csv",
            mime="text/csv",
            use_container_width=True,
            key="btn_print_report",
        )
        if report_clicked:
            add_event_log_entry("Dashboard report exported.")
            persist_event_log_for_project(project_name)

        st.markdown(
            f"<p style='color:white; font-size:13px; margin-top:10px;'>Saved run test inputs: <b>{record_count}</b></p>",
            unsafe_allow_html=True,
        )

        debug_confirm_key = f"clear_records_confirm_{project_name}"
        if st.session_state.get(debug_confirm_key, False):
            if st.button("Debugger Confirm: Delete Run Test Inputs", use_container_width=True, type="primary", key="btn_clear_records_confirm"):
                deleted_rows = clear_project_records(project_name)
                st.session_state.add_record_draft = {}
                st.session_state.maintenance_prefill_pumps = []
                st.session_state.maintenance_source_record_id = None
                st.session_state.pop(debug_confirm_key, None)
                queue_confirmation(f"Deleted {deleted_rows} saved run test input record(s). Project setup remains intact.")
                st.rerun()
            if st.button("Cancel Delete Run Test Inputs", use_container_width=True, key="btn_clear_records_cancel"):
                st.session_state.pop(debug_confirm_key, None)
                st.rerun()
        else:
            if st.button("Debugger: Delete Run Test Inputs", use_container_width=True, key="btn_clear_records"):
                st.session_state[debug_confirm_key] = True
                st.rerun()

        st.markdown(
            f"<p style='color:white; font-size:13px; margin-top:8px;'>Saved maintenance inputs: <b>{maintenance_count}</b></p>",
            unsafe_allow_html=True,
        )

        maint_debug_confirm_key = f"clear_maintenance_confirm_{project_name}"
        if st.session_state.get(maint_debug_confirm_key, False):
            if st.button("Debugger Confirm: Delete Maintenance Inputs", use_container_width=True, type="primary", key="btn_clear_maintenance_confirm"):
                deleted_rows = clear_project_maintenance_events(project_name)
                st.session_state.maintenance_prefill_pumps = []
                st.session_state.maintenance_source_record_id = None
                st.session_state.pop(maint_debug_confirm_key, None)
                queue_confirmation(f"Deleted {deleted_rows} saved maintenance input record(s). Project setup remains intact.")
                st.rerun()
            if st.button("Cancel Delete Maintenance Inputs", use_container_width=True, key="btn_clear_maintenance_cancel"):
                st.session_state.pop(maint_debug_confirm_key, None)
                st.rerun()
        else:
            if st.button("Debugger: Delete Maintenance Inputs", use_container_width=True, key="btn_clear_maintenance"):
                st.session_state[maint_debug_confirm_key] = True
                st.rerun()
        
        st.write("")
        if st.button("Exit Dashboard", use_container_width=True, type="primary"):
            st.session_state.page = "home"
            st.rerun()

    with col_right:
        if "active_pumps_df" in st.session_state and not st.session_state.active_pumps_df.empty:
            limits_df = st.session_state.get("limits_df", pd.DataFrame(columns=["Pump ID", "Max Stator Temp (°C)", "Max Current (A)"]))
            extra_limits_df = st.session_state.get("extra_limits_df", pd.DataFrame(columns=["Formula Name", "Min Value", "Max Value", "Applies To"]))
            layout_df = st.session_state.get("layout_df", pd.DataFrame())
            tanks = st.session_state.get("water_tanks", [])
            main_tracker = st.session_state.get("dashboard_main_tracker", "Temperature")
            latest_record = get_latest_record(project_name)
            latest_status_grid = latest_record.get("status_grid", {}) if latest_record else {}
            latest_readings = latest_record.get("pump_readings", {}) if latest_record else {}
            latest_alarms = latest_record.get("alarms", []) if latest_record else []

            alarm_pump_ids = set()
            if isinstance(latest_alarms, list):
                for a in latest_alarms:
                    pid_alarm = str(a.get("pump_id", "")).strip() if isinstance(a, dict) else ""
                    if pid_alarm:
                        alarm_pump_ids.add(pid_alarm)

            limits_lookup = {}
            if isinstance(limits_df, pd.DataFrame) and not limits_df.empty and "Pump ID" in limits_df.columns:
                for _, limit_row in limits_df.iterrows():
                    limits_lookup[str(limit_row.get("Pump ID", ""))] = limit_row

            active_lookup = {}
            for _, pump_row in st.session_state.active_pumps_df.iterrows():
                active_pid = str(pump_row.get("pump_id", pump_row.get("Pump ID", "")))
                if active_pid:
                    active_lookup[active_pid] = pump_row

            if not tanks and isinstance(layout_df, pd.DataFrame) and not layout_df.empty and "Assigned Tank" in layout_df.columns:
                tanks = [t for t in layout_df["Assigned Tank"].dropna().tolist() if str(t).strip()]

            pump_tank_lookup = {}
            if isinstance(layout_df, pd.DataFrame) and not layout_df.empty and "Pump ID" in layout_df.columns and "Assigned Tank" in layout_df.columns:
                for _, lrow in layout_df.iterrows():
                    pid = str(lrow.get("Pump ID", "")).strip()
                    tname = str(lrow.get("Assigned Tank", "")).strip()
                    if pid and tname:
                        pump_tank_lookup[pid] = tname

            tank_open_counts = {}
            tank_critical_counts = {}
            if isinstance(maintenance_df, pd.DataFrame) and not maintenance_df.empty:
                for _, mrow in maintenance_df.iterrows():
                    m_status = str(mrow.get("maintenance_status", "Open") or "Open").strip()
                    if m_status == "Closed":
                        continue
                    m_sev = str(mrow.get("severity", "") or "").strip().upper()
                    try:
                        affected = [str(x).strip() for x in json.loads(mrow.get("affected_pumps_json", "[]") or "[]")]
                    except Exception:
                        affected = []
                    seen_tanks = set()
                    for pid in affected:
                        tank_name = pump_tank_lookup.get(pid, "")
                        if not tank_name or tank_name in seen_tanks:
                            continue
                        seen_tanks.add(tank_name)
                        tank_open_counts[tank_name] = tank_open_counts.get(tank_name, 0) + 1
                        if m_sev == "CRITICAL":
                            tank_critical_counts[tank_name] = tank_critical_counts.get(tank_name, 0) + 1

            running_time_unit = "cycles" if is_cycle_test else "hrs"

            rendered_any = False
            for tank in tanks:
                tank_pumps = []
                if isinstance(layout_df, pd.DataFrame) and not layout_df.empty and "Assigned Tank" in layout_df.columns and "Pump ID" in layout_df.columns:
                    tank_pumps = layout_df[layout_df["Assigned Tank"] == tank]["Pump ID"].tolist()

                if not tank_pumps:
                    continue

                rendered_any = True
                tank_open = tank_open_counts.get(str(tank), 0)
                tank_critical = tank_critical_counts.get(str(tank), 0)
                st.markdown(
                    f"<div style='display:flex; justify-content:space-between; align-items:center; color:#4DA3FF; font-size:20px; font-weight:bold; margin-top:10px;'>"
                    f"<span>Water Tank: {tank}</span>"
                    f"<span style='font-size:12px; color:#FFFFFF;'>Open Maint: <b>{tank_open}</b> | Critical: <b>{tank_critical}</b></span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

                for row_start in range(0, len(tank_pumps), 3):
                    row_pumps = tank_pumps[row_start:row_start+3]
                    cols = st.columns(3)
                    for i, p_id in enumerate(row_pumps):
                        p_id = str(p_id)
                        pump_limits = limits_lookup.get(p_id)
                        pump_row = active_lookup.get(p_id)

                        try:
                            amp_from_pump = pump_row.get("amp_max", pump_row.get("Amp Max", 0.0)) if pump_row is not None else 0.0
                            amp_max = float((pump_limits.get("Max Current (A)") if pump_limits is not None else amp_from_pump) or 0.0)
                        except (ValueError, TypeError, AttributeError):
                            amp_max = 0.0
                        try:
                            temp_max = float((pump_limits.get("Max Stator Temp (°C)") if pump_limits is not None else 0.0) or 0.0)
                        except (ValueError, TypeError, AttributeError):
                            temp_max = 0.0

                        record_grid = latest_status_grid.get(p_id, {}) if isinstance(latest_status_grid, dict) else {}
                        record_reading = latest_readings.get(p_id, {}) if isinstance(latest_readings, dict) else {}
                        record_status = str(record_grid.get("status", "STANDBY")).upper()
                        record_alarm = p_id in alarm_pump_ids
                        running_time_value = f"{float(record_grid.get('acc_hours', 0.0) or 0.0):.1f} / {target_val} {running_time_unit}"

                        if record_status == "RUNNING":
                            status_color = "value-green"
                            light_class = "status-light-run"
                            svg_color = "#2ECC71"
                            status_text = "RUNNING"
                        elif record_status == "PAUSED":
                            status_color = "value-grey"
                            light_class = "status-light-stop"
                            svg_color = "#EEDD82"
                            status_text = "PAUSED"
                        elif record_status == "FAILED":
                            status_color = "value-grey"
                            light_class = "status-light-stop"
                            svg_color = "#E74C3C"
                            status_text = "FAILED"
                        else:
                            status_color = "value-grey"
                            light_class = "status-light-stop"
                            svg_color = "#777"
                            status_text = "STANDBY"

                        if record_alarm:
                            svg_color = "#E67E22"
                            status_text = "ALARM"

                        try:
                            current_val = f"{float(record_reading.get('amps', 0.0) or 0.0):.2f}A"
                        except Exception:
                            current_val = "0.00A"
                        try:
                            temp_reading = record_reading.get("temp", None)
                            temperature_val = "--.-C" if temp_reading is None else f"{float(temp_reading):.1f}C"
                        except Exception:
                            temperature_val = "--.-C"

                        formula_limits_html = '<div style="font-size: 10px; color: #666; margin-top: 10px;">No additional formula safety limits</div>'
                        if isinstance(extra_limits_df, pd.DataFrame) and not extra_limits_df.empty and "Applies To" in extra_limits_df.columns:
                            applicable_limits = []
                            for _, extra_row in extra_limits_df.iterrows():
                                applies_to = str(extra_row.get("Applies To", "")).strip()
                                matches_global = applies_to in ["Global (All Pumps)", "Global (Apply to All Compatible Pumps)"]
                                matches_pump = applies_to == p_id
                                matches_tank = applies_to == f"Water Tank: {tank}"
                                if matches_global or matches_pump or matches_tank:
                                    formula_name = str(extra_row.get("Formula Name", "Formula")).strip() or "Formula"
                                    min_val = extra_row.get("Min Value", "")
                                    max_val = extra_row.get("Max Value", "")
                                    min_text = "-" if pd.isna(min_val) or min_val == "" else f"{float(min_val):.2f}"
                                    max_text = "-" if pd.isna(max_val) or max_val == "" else f"{float(max_val):.2f}"
                                    applicable_limits.append(
                                        f'<div style="display:flex; justify-content:space-between; font-size:10px; color:#BFC7D5; margin-top:4px;"><span>{formula_name}</span><span>Min {min_text} | Max {max_text}</span></div>'
                                    )
                            if applicable_limits:
                                formula_limits_html = "".join(applicable_limits)

                        maintenance_info = maint_by_pump.get(p_id)
                        maintenance_html = '<div style="font-size:10px; color:#666; margin-top:8px;">No open maintenance</div>'
                        if maintenance_info:
                            m_status = str(maintenance_info.get("maintenance_status", "Open")).strip() or "Open"
                            sev = str(maintenance_info.get("severity", "")).strip().upper() or "-"
                            sev_color = "#9CA3AF"
                            if sev == "CRITICAL":
                                sev_color = "#EF4444"
                            elif sev == "HIGH":
                                sev_color = "#F59E0B"
                            elif sev == "MEDIUM":
                                sev_color = "#3B82F6"
                            elif sev == "LOW":
                                sev_color = "#22C55E"
                            status_badge_color = "#9CA3AF" if m_status == "Closed" else "#F59E0B"
                            m_ts = maintenance_info.get("event_ts", "")
                            m_type = maintenance_info.get("event_type", "")
                            maintenance_html = (
                                f'<div style="display:flex; justify-content:space-between; align-items:center; margin-top:8px;">'
                                f'<span style="font-size:10px; color:#BFC7D5;">{m_type} @ {m_ts}</span>'
                                f'<span style="font-size:10px; color:{status_badge_color}; border:1px solid {status_badge_color}; padding:1px 6px; border-radius:999px;">{m_status}</span>'
                                '</div>'
                                f'<div style="display:flex; justify-content:flex-end; margin-top:4px;">'
                                f'<span style="font-size:10px; color:{sev_color}; border:1px solid {sev_color}; padding:1px 6px; border-radius:999px;">{sev}</span>'
                                '</div>'
                            )

                        if main_tracker == "Temperature":
                            primary_label = f"TEMPERATURE (MAX: {temp_max:.1f}°C)"
                            primary_val = temperature_val
                            secondary_label = f"CURRENT (MAX: {amp_max:.2f}A)"
                            secondary_val = current_val
                        else:
                            primary_label = f"LIVE CURRENT (MAX: {amp_max:.2f}A)"
                            primary_val = current_val
                            secondary_label = f"TEMPERATURE (MAX: {temp_max:.1f}°C)"
                            secondary_val = temperature_val

                        sparkline_tracker_label = main_tracker.upper()
                        sparkline = f'<svg viewBox="0 0 100 20" style="width:100%; height:30px; margin-top:10px;"><polyline fill="none" stroke="{svg_color}" stroke-width="2" points="0,15 10,15 20,15 30,15 40,15 50,15 60,15 70,15 80,15 90,15 100,15" /></svg>'

                        with cols[i]:
                            st.markdown(
                                '<div class="panel">'
                                f'<div class="panel-title">{p_id}</div>'
                                '<div style="display: flex; justify-content: space-between; align-items: center;">'
                                '<div>'
                                f'<div style="font-size: 10px; color: #888;">{primary_label}</div>'
                                f'<div class="{status_color}">{primary_val}</div>'
                                '</div>'
                                '<div style="text-align: center;">'
                                '<div style="font-size: 10px; color: #888; margin-bottom: 5px;">STATUS LIGHT</div>'
                                f'<div class="{light_class}"></div>'
                                f'<div style="font-size: 10px; color: {svg_color}; font-weight: bold; margin-top: 3px;">{status_text}</div>'
                                '</div>'
                                '</div>'
                                '<div style="display:flex; justify-content:space-between; gap:12px; margin-top:10px;">'
                                '<div style="flex:1;">'
                                f'<div style="font-size:10px; color:#888;">{secondary_label}</div>'
                                f'<div style="color:#BFC7D5; font-size:18px; font-weight:bold;">{secondary_val}</div>'
                                '</div>'
                                '<div style="flex:1; text-align:right;">'
                                '<div style="font-size:10px; color:#888;">RUNNING TIME</div>'
                                f'<div style="color:#BFC7D5; font-size:14px; font-weight:bold;">{running_time_value}</div>'
                                '</div>'
                                '</div>'
                                '<div style="font-size: 10px; color: #888; margin-top: 10px;">SPARKLINE</div>'
                                f'{sparkline}'
                                f'<div style="display: flex; justify-content: space-between; font-size: 9px; color: #666; margin-top: 5px;"><span>{sparkline_tracker_label}</span><span>10 MINUTES</span></div>'
                                '<div style="font-size:10px; color:#888; margin-top:12px; border-top:1px solid #2A2D34; padding-top:8px;">ADDITIONAL FORMULA SAFETY LIMITS</div>'
                                f'{formula_limits_html}'
                                '<div style="font-size:10px; color:#888; margin-top:10px; border-top:1px solid #2A2D34; padding-top:8px;">MAINTENANCE</div>'
                                f'{maintenance_html}'
                                '</div>',
                                unsafe_allow_html=True,
                            )

            if not rendered_any:
                st.warning("No pump layout found for this project. Please modify the project layout in Step 3.")
        else:
            st.warning("No pump data found for this project. Please modify the project to add pumps.")

# --- FIX: Ensure the wizard only renders on the Create page ---
elif st.session_state.page == "create":
    render_project_form()