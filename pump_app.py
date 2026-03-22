
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
    inject_industrial_css()
    project_id = st.session_state.get("current_project", "")
    if not project_id:
        st.error("No active project selected. Open a project dashboard first.")
        if st.button("Back to Home", use_container_width=True):
            st.session_state.page = "home"
            st.rerun()
        return

    st.markdown("<div class='step-title'>Add New Record Wizard</div>", unsafe_allow_html=True)
    st.markdown(f"<p style='color:white; font-size:16px;'>Project: {project_id}</p>", unsafe_allow_html=True)

    if st.button("Back to Dashboard", use_container_width=True):
        st.session_state.page = "dashboard"
        st.rerun()

    draft = legacy_add_record_setup.initialize_add_record_draft()

    baseline_exists = has_baseline_record(project_id)
    latest_record = get_latest_record(project_id)

    pumps_df = legacy_add_record_setup.ensure_active_pumps_df(DB_FILE, project_id)
    legacy_add_record_setup.ensure_hardware_and_formula_state(
        project_id,
        restore_project_hardware_state,
        restore_project_formula_state,
    )

    if pumps_df.empty:
        st.warning("No pumps found for this project.")
        return

    pump_ids = legacy_add_record_setup.build_pump_ids(pumps_df)
    pump_tank_lookup = legacy_add_record_setup.load_layout_and_pump_tank_lookup(DB_FILE, project_id)

    if not legacy_record_phases.render_phase1(draft, baseline_exists, queue_confirmation):
        return

    # Phase 2
    st.markdown("<p class='col-header'>Phase 2: Time Math & State Management</p>", unsafe_allow_html=True)

    default_record_dt = legacy_phase2_utils.get_default_record_datetime(draft, parse_ts)

    work_start = datetime.time(8, 0)
    work_end = datetime.time(17, 0)
    default_time = legacy_phase2_utils.clamp_time_to_work_window(default_record_dt, work_start, work_end)

    c_date, c_time = st.columns(2)
    with c_date:
        record_date = st.date_input("Record Date", value=default_record_dt.date(), key="add_record_date")
    with c_time:
        record_time = st.time_input("Record Time", value=default_time, step=300, key="add_record_time")

    record_ts = datetime.datetime.combine(record_date, record_time)
    draft["record_ts"] = record_ts.strftime("%Y-%m-%d %H:%M:%S")

    ts_valid, work_window_error = legacy_phase2_utils.evaluate_timestamp_window(record_time, work_start, work_end)
    if work_window_error:
        st.error(work_window_error)

    last_ts = legacy_phase2_utils.parse_last_timestamp(latest_record, parse_ts)
    ts_valid, global_delta, time_error = legacy_phase2_utils.compute_global_delta(
        draft["record_phase"],
        ts_valid,
        record_ts,
        last_ts,
    )
    if time_error:
        st.error(time_error)

    last_record_suffix = "" if not last_ts else f" (Last record: {last_ts.strftime('%Y-%m-%d %H:%M:%S')})"
    st.markdown(
        f"<p style='color:white;'>Record Timestamp: <b>{draft['record_ts']}</b><br/>Global Delta: <b>{global_delta:.2f} hrs</b>{last_record_suffix}</p>",
        unsafe_allow_html=True,
    )

    previous_grid = latest_record.get("status_grid", {}) if latest_record else {}
    status_df = legacy_phase2_utils.build_status_rows(pump_ids, previous_grid, draft["record_phase"])
    if draft["record_phase"] == "Baseline Calibration (Cold State)":
        st.dataframe(status_df[["Pump ID", "Previous Status", "Accumulated Time (hrs)", "New Status"]], use_container_width=True, hide_index=True)
        edited_status_df = status_df.copy()
    else:
        edited_status_df = st.data_editor(
            status_df,
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            key="status_grid_editor",
            column_config={
                "Pump ID": st.column_config.TextColumn("Pump ID", disabled=True),
                "Previous Status": st.column_config.TextColumn("Previous Status", disabled=True),
                "Accumulated Time (hrs)": st.column_config.NumberColumn("Accumulated Time (hrs)", disabled=True, format="%.2f"),
                "New Status": st.column_config.SelectboxColumn("New Status", options=["RUNNING", "STANDBY", "PAUSED", "FAILED"], required=True),
                "Failure DateTime (YYYY-MM-DD HH:MM:SS)": st.column_config.TextColumn("Failure DateTime (YYYY-MM-DD HH:MM:SS)"),
            },
        )

    if st.button("Confirm Status Grid & Time Distribution", use_container_width=True, key="confirm_phase2"):
        if not ts_valid:
            st.error("Fix timestamp issues before confirming Phase 2.")
        else:
            errors, maintenance_candidates, computed_grid = legacy_phase2_utils.process_phase2_confirmation(
                edited_status_df,
                draft["record_phase"],
                global_delta,
                last_ts,
                record_ts,
                parse_ts,
            )

            if errors:
                for err in errors:
                    st.error(err)
            else:
                draft["status_grid"] = computed_grid
                draft["maintenance_candidates"] = maintenance_candidates
                draft["phase2_confirmed"] = True
                queue_confirmation("Phase 2 confirmed. Time distribution calculated.")
                st.rerun()

    if not draft.get("phase2_confirmed", False):
        return

    water_tanks = st.session_state.get("water_tanks", [])
    if not legacy_record_phases.render_phase3(draft, water_tanks, queue_confirmation):
        return

    # Phase 4
    st.markdown("<p class='col-header'>Phase 4: Targeted Hardware Polling</p>", unsafe_allow_html=True)
    limits_df = st.session_state.get("limits_df", pd.DataFrame(columns=["Pump ID", "Max Stator Temp (°C)", "Max Current (A)"]))
    extra_limits_df = st.session_state.get("extra_limits_df", pd.DataFrame(columns=["Formula Name", "Min Value", "Max Value", "Applies To"]))
    limits_lookup = legacy_phase4_utils.build_limits_lookup(limits_df)

    temp_units, clamp_units = build_phase4_hardware_plan(pump_ids, draft["status_grid"])
    pump_readings = {}
    previous_readings = draft.get("pump_readings", {})
    saved_temp_tables = draft.get("phase4_temp_tables", {})
    saved_clamp_tables = draft.get("phase4_clamp_tables", {})

    st.markdown(
        "<p style='color:white;'>Temperature polling follows HIOKI Temp hardware by channel first. Current polling follows HIOKI Clamp hardware by mapped pump after temperature is complete.</p>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='color:white; font-size:13px;'>Temperature consolidation rule: Exact takes priority, otherwise Max Temp uses the hottest channel, then Average uses the mean of assigned channels.</p>",
        unsafe_allow_html=True,
    )

    rendered_temp_pumps = set()
    temp_tables = {}
    has_temp_hardware = len(temp_units) > 0
    if temp_units:
        st.markdown("<p class='white-text' style='color:#0d6efd !important;'>Temperature Devices</p>", unsafe_allow_html=True)
        for unit in temp_units:
            hw_name = unit["hardware"]
            st.markdown(f"<p style='color:#4DA3FF; font-size:16px; font-weight:bold; margin-top:10px;'>{hw_name}</p>", unsafe_allow_html=True)
            source_text = ", ".join(unit.get("data_source", [])) if isinstance(unit.get("data_source"), list) else str(unit.get("data_source", "Manual Input"))
            st.markdown(f"<p style='color:white; font-size:13px;'>Data Source: {source_text}</p>", unsafe_allow_html=True)
            editor_rows = legacy_phase4_utils.build_temp_editor_rows(
                unit,
                saved_temp_tables,
                previous_readings,
                safe_float,
                rendered_temp_pumps,
            )

            temp_tables[hw_name] = st.data_editor(
                pd.DataFrame(editor_rows),
                hide_index=True,
                use_container_width=True,
                num_rows="fixed",
                key=f"phase4_temp_editor_{hw_name}",
                column_order=["CH", "Sensor Name", "Reading (C)"],
                column_config={
                    "CH": st.column_config.TextColumn("Channel", disabled=True),
                    "Sensor Name": st.column_config.TextColumn("Sensor Name", disabled=True),
                    "Pump ID": st.column_config.TextColumn("Pump ID", disabled=True),
                    "Status": st.column_config.TextColumn("Status", disabled=True),
                    "Measurement Type": st.column_config.TextColumn("Measurement Type", disabled=True),
                    "Reading (C)": st.column_config.NumberColumn("Reading (C)", required=True, format="%.1f"),
                },
            )

    unmapped_temp_pumps, fallback_temp_pumps = legacy_phase4_utils.classify_temp_mapping_gaps(
        pump_ids,
        draft["status_grid"],
        rendered_temp_pumps,
        has_temp_hardware,
    )

    if has_temp_hardware and unmapped_temp_pumps:
        st.markdown(
            f"<p style='color:#F59E0B; font-size:13px;'>Unmapped temperature channels for pump(s): {', '.join(unmapped_temp_pumps)}. Map them in Step 4 HIOKI Temp configuration (Assigned To) to enter by CH.</p>",
            unsafe_allow_html=True,
        )

    if fallback_temp_pumps:
        st.markdown("<p class='white-text' style='color:#0d6efd !important;'>Temperature Inputs Without HIOKI Temp Mapping</p>", unsafe_allow_html=True)
        st.markdown("<p style='color:white; font-size:13px;'>These pumps do not have an active HIOKI Temp channel assignment, so they remain as direct fallback inputs.</p>", unsafe_allow_html=True)
        for pid, status in fallback_temp_pumps:
            lim = limits_lookup.get(pid)
            max_temp = safe_float(lim.get("Max Stator Temp (°C)", 0.0) if lim is not None else 0.0, 0.0)
            label = f"{pid} Live Stator Temp (C) [Max: {max_temp:.1f}]" if status == "RUNNING" else f"{pid} Cold/Cool-down Stator Temp (C)"
            temp_value = st.number_input(
                label,
                value=safe_float(previous_readings.get(pid, {}).get("temp"), 0.0),
                step=0.1,
                format="%.1f",
                key=f"phase4_temp_fallback_{pid}",
            )
            pump_readings[pid] = {"temp": float(temp_value), "amps": 0.0 if status in ["STANDBY", "PAUSED"] else None, "status": status}

    rendered_clamp_pumps = set()
    clamp_tables = {}
    has_clamp_hardware = len(clamp_units) > 0
    if clamp_units:
        st.markdown("<p class='white-text' style='color:#0d6efd !important;'>Current Devices</p>", unsafe_allow_html=True)
        for unit in clamp_units:
            hw_name = unit["hardware"]
            st.markdown(f"<p style='color:#4DA3FF; font-size:16px; font-weight:bold; margin-top:10px;'>{hw_name}</p>", unsafe_allow_html=True)
            source_text = ", ".join(unit.get("data_source", [])) if isinstance(unit.get("data_source"), list) else str(unit.get("data_source", "Manual Input"))
            st.markdown(f"<p style='color:white; font-size:13px;'>Data Source: {source_text}</p>", unsafe_allow_html=True)
            editor_rows = legacy_phase4_utils.build_clamp_editor_rows(
                unit,
                saved_clamp_tables,
                previous_readings,
                limits_lookup,
                safe_float,
                rendered_clamp_pumps,
            )

            clamp_tables[hw_name] = st.data_editor(
                pd.DataFrame(editor_rows),
                hide_index=True,
                use_container_width=True,
                num_rows="fixed",
                key=f"phase4_clamp_editor_{hw_name}",
                column_config={
                    "Pump ID": st.column_config.TextColumn("Pump ID", disabled=True),
                    "Sensor Name": st.column_config.TextColumn("Sensor Name", disabled=True),
                    "Status": st.column_config.TextColumn("Status", disabled=True),
                    "Max Current (A)": st.column_config.NumberColumn("Max Current (A)", disabled=True, format="%.2f"),
                    "Reading (A)": st.column_config.NumberColumn("Reading (A)", required=True, format="%.2f"),
                },
            )

    unmapped_clamp_pumps, fallback_clamp_pumps = legacy_phase4_utils.classify_clamp_mapping_gaps(
        pump_ids,
        draft["status_grid"],
        rendered_clamp_pumps,
        has_clamp_hardware,
    )

    if has_clamp_hardware and unmapped_clamp_pumps:
        st.markdown(
            f"<p style='color:#F59E0B; font-size:13px;'>Unmapped current channels for running pump(s): {', '.join(unmapped_clamp_pumps)}. Map them in Step 4 HIOKI Clamp configuration (Read Status On) for hardware-based current polling.</p>",
            unsafe_allow_html=True,
        )

    if fallback_clamp_pumps:
        st.markdown("<p class='white-text' style='color:#0d6efd !important;'>Current Inputs Without HIOKI Clamp Mapping</p>", unsafe_allow_html=True)
        st.markdown("<p style='color:white; font-size:13px;'>These running pumps do not have an active HIOKI Clamp mapping, so they remain as direct fallback inputs.</p>", unsafe_allow_html=True)
        for pid in fallback_clamp_pumps:
            lim = limits_lookup.get(pid)
            max_current = safe_float(lim.get("Max Current (A)", 0.0) if lim is not None else 0.0, 0.0)
            amps_value = st.number_input(
                f"{pid} Live Measured Current (A) [Max: {max_current:.2f}]",
                value=safe_float(previous_readings.get(pid, {}).get("amps"), 0.0),
                step=0.01,
                format="%.2f",
                key=f"phase4_clamp_fallback_{pid}",
            )
            existing = pump_readings.get(pid, {})
            pump_readings[pid] = {
                "temp": existing.get("temp"),
                "amps": float(amps_value),
                "status": "RUNNING",
            }

    pump_readings = legacy_phase4_utils.ensure_default_pump_readings(
        pump_ids,
        draft["status_grid"],
        pump_readings,
        previous_readings,
        safe_float,
    )

    if st.button("Confirm Targeted Polling", use_container_width=True, key="confirm_phase4"):
        errors = []
        temp_tables_payload = {}
        clamp_tables_payload = {}
        temp_candidates = {}
        current_candidates = {}

        for hw_name, edited_df in temp_tables.items():
            temp_tables_payload[hw_name] = edited_df.to_dict("records")
            for _, row in edited_df.iterrows():
                pump_id = str(row.get("Pump ID", "")).strip()
                status = str(row.get("Status", "STANDBY")).upper()
                reading = row.get("Reading (C)")
                if pump_id and status in ["RUNNING", "STANDBY", "PAUSED"]:
                    if pd.isna(reading):
                        errors.append(f"{hw_name} {row.get('CH', '')} for {pump_id}: temperature is required.")
                        continue
                    temp_candidates.setdefault(pump_id, []).append({
                        "measurement_type": row.get("Measurement Type", "Exact"),
                        "value": float(reading),
                    })

        for pid, _ in fallback_temp_pumps:
            temp_candidates.setdefault(pid, []).append({
                "measurement_type": "Exact",
                "value": safe_float(st.session_state.get(f"phase4_temp_fallback_{pid}"), 0.0),
            })

        for hw_name, edited_df in clamp_tables.items():
            clamp_tables_payload[hw_name] = edited_df.to_dict("records")
            for _, row in edited_df.iterrows():
                pump_id = str(row.get("Pump ID", "")).strip()
                status = str(row.get("Status", "STANDBY")).upper()
                reading = row.get("Reading (A)")
                if not pump_id:
                    continue
                if status == "RUNNING":
                    if pd.isna(reading):
                        errors.append(f"{hw_name} {pump_id}: current is required.")
                        continue
                    current_candidates.setdefault(pump_id, []).append(float(reading))
                elif status in ["STANDBY", "PAUSED"]:
                    current_candidates.setdefault(pump_id, []).append(0.0)

        for pid in fallback_clamp_pumps:
            current_candidates.setdefault(pid, []).append(safe_float(st.session_state.get(f"phase4_clamp_fallback_{pid}"), 0.0))

        if errors:
            for err in errors:
                st.error(err)
        else:
            for pid in pump_ids:
                status = str(draft["status_grid"].get(pid, {}).get("status", "STANDBY")).upper()
                if status == "FAILED":
                    pump_readings[pid] = {"temp": None, "amps": None, "status": status}
                    continue

                derived_temp = aggregate_temperature_for_pump(temp_candidates.get(pid, []))
                if derived_temp is None:
                    derived_temp = safe_float(previous_readings.get(pid, {}).get("temp"), 0.0)

                if status in ["STANDBY", "PAUSED"]:
                    derived_amps = 0.0
                else:
                    current_values = current_candidates.get(pid, [])
                    derived_amps = max(current_values) if current_values else safe_float(previous_readings.get(pid, {}).get("amps"), 0.0)

                pump_readings[pid] = {
                    "temp": float(derived_temp),
                    "amps": float(derived_amps),
                    "status": status,
                }

            draft["phase4_temp_tables"] = temp_tables_payload
            draft["phase4_clamp_tables"] = clamp_tables_payload
            draft["pump_readings"] = pump_readings
            draft["phase4_confirmed"] = True
            queue_confirmation("Phase 4 confirmed. Hardware readings captured.")
            st.rerun()

    if not draft.get("phase4_confirmed", False):
        return

    # Phase 5 and 6
    st.markdown("<p class='col-header'>Phase 5/6: Safety Validation, Review & Commit</p>", unsafe_allow_html=True)
    ambient = float(draft.get("ambient_temp", 0.0) or 0.0)
    tank_temps = draft.get("tank_temps", {}) if isinstance(draft.get("tank_temps", {}), dict) else {}
    formulas_df = st.session_state.get("formulas_df", pd.DataFrame(columns=["Formula Name", "Target", "Equation"]))
    var_mapping_df = st.session_state.get("var_mapping_df", pd.DataFrame(columns=["Variable", "Mapped Sensor"]))

    review_rows = []
    all_alarms = []
    formula_debug_rows = []
    for pid in pump_ids:
        grid = draft["status_grid"].get(pid, {})
        reading = draft["pump_readings"].get(pid, {})
        status = str(grid.get("status", "STANDBY")).upper()
        acc = float(grid.get("acc_hours", 0.0) or 0.0)
        temp = reading.get("temp", None)
        amps = reading.get("amps", None)
        tank_name = str(pump_tank_lookup.get(pid, "")).strip()
        resolved_variables = build_formula_variables_for_pump(
            pid,
            reading,
            ambient,
            tank_temps,
            pump_tank_lookup,
            var_mapping_df,
        )
        rise = None
        rise_formula_name = ""
        rise_formula_target = ""
        applicable_temp_rise = []
        if isinstance(formulas_df, pd.DataFrame) and not formulas_df.empty and "Formula Name" in formulas_df.columns:
            for _, formula_row in formulas_df.iterrows():
                formula_name = str(formula_row.get("Formula Name", "")).strip()
                if formula_name.lower() not in ["temperature rise", "temp rise"]:
                    continue
                specificity = get_formula_target_specificity(formula_row.get("Target", ""), pid, tank_name)
                if specificity >= 0:
                    applicable_temp_rise.append((specificity, formula_name))
        if applicable_temp_rise:
            applicable_temp_rise.sort(reverse=True)
            rise_formula_name = applicable_temp_rise[0][1]
            rise, rise_formula_target = evaluate_formula_for_pump(
                pid,
                tank_name,
                rise_formula_name,
                formulas_df,
                var_mapping_df,
                reading,
                ambient,
                tank_temps,
                pump_tank_lookup,
            )
        if rise is None and temp is not None:
            rise = float(temp) - ambient

        lim = limits_lookup.get(pid)
        max_temp = float(lim.get("Max Stator Temp (°C)", 0.0) if lim is not None else 0.0)
        max_current = float(lim.get("Max Current (A)", 0.0) if lim is not None else 0.0)

        pump_alarm_list = []
        formula_limit_debug = []
        if status == "RUNNING":
            if temp is not None and float(temp) > max_temp:
                pump_alarm_list.append(f"Temp {float(temp):.1f}C > {max_temp:.1f}C")
            if amps is not None and float(amps) > max_current:
                pump_alarm_list.append(f"Current {float(amps):.2f}A > {max_current:.2f}A")
            if isinstance(extra_limits_df, pd.DataFrame) and not extra_limits_df.empty and "Formula Name" in extra_limits_df.columns:
                for _, ex in extra_limits_df.iterrows():
                    formula_name = str(ex.get("Formula Name", "")).strip()
                    applies = str(ex.get("Applies To", "")).strip()
                    if get_formula_target_specificity(applies, pid, tank_name) < 0:
                        continue
                    formula_value, _ = evaluate_formula_for_pump(
                        pid,
                        tank_name,
                        formula_name,
                        formulas_df,
                        var_mapping_df,
                        reading,
                        ambient,
                        tank_temps,
                        pump_tank_lookup,
                        preferred_target=applies,
                    )
                    if formula_value is None:
                        continue
                    min_value = safe_float(ex.get("Min Value"), None)
                    max_value = safe_float(ex.get("Max Value"), None)
                    formula_limit_debug.append(
                        f"{formula_name}={float(formula_value):.2f} [Target={applies}]"
                    )
                    if min_value is not None and float(formula_value) < float(min_value):
                        pump_alarm_list.append(f"{formula_name} {float(formula_value):.2f} < {float(min_value):.2f}")
                    if max_value is not None and float(formula_value) > float(max_value):
                        pump_alarm_list.append(f"{formula_name} {float(formula_value):.2f} > {float(max_value):.2f}")

        if pump_alarm_list:
            all_alarms.append({"pump_id": pid, "alarms": pump_alarm_list})

        review_rows.append({
            "Pump ID": pid,
            "Status": status,
            "Acc. Time (hrs)": round(acc, 2),
            "Temp (C)": "-" if temp is None else round(float(temp), 1),
            "Amps (A)": "-" if amps is None else round(float(amps), 2),
            "Rise (C)": "-" if rise is None else round(float(rise), 1),
            "Alarms": " | ".join(pump_alarm_list) if pump_alarm_list else "OK",
        })

        debug_variables_text = ", ".join([f"{key}={value:.2f}" for key, value in sorted(resolved_variables.items())]) if resolved_variables else "-"
        debug_rise_formula = "-"
        if rise_formula_name:
            target_text = rise_formula_target if rise_formula_target else "matched"
            debug_rise_formula = f"{rise_formula_name} [{target_text}]"
        formula_debug_rows.append({
            "Pump ID": pid,
            "Tank": tank_name or "-",
            "Resolved Variables": debug_variables_text,
            "Rise Formula": debug_rise_formula,
            "Rise Value": "-" if rise is None else f"{float(rise):.2f}",
            "Formula Limit Values": " | ".join(formula_limit_debug) if formula_limit_debug else "-",
        })

    review_df = pd.DataFrame(review_rows)
    st.dataframe(review_df, use_container_width=True, hide_index=True)

    with st.expander("Formula Debug Panel", expanded=False):
        st.markdown("<p style='color:white; font-size:13px;'>Resolved variables, selected rise formula, and evaluated Step 6 formula values used during Add Record review.</p>", unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(formula_debug_rows), use_container_width=True, hide_index=True)

    alarm_ack = True
    if all_alarms:
        st.markdown(
            "<div style='background:#3B1F24; border:1px solid #7F1D1D; color:#FFFFFF; padding:10px; border-radius:6px; margin-top:8px;'>ALARM: One or more pumps exceeded safety limits.</div>",
            unsafe_allow_html=True,
        )
        alarm_ack = st.checkbox("I acknowledge safety limits have been exceeded", key="ack_alarm_checkbox")

    can_save = (alarm_ack if all_alarms else True)
    if st.button("Save Record", use_container_width=True, type="primary", disabled=not can_save, key="save_record_button"):
        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            if draft["record_phase"] == "Baseline Calibration (Cold State)":
                c.execute(
                    "DELETE FROM project_records WHERE project_id = ? AND record_phase = ?",
                    (project_id, "Baseline Calibration (Cold State)"),
                )

            c.execute(
                """
                INSERT INTO project_records (
                    project_id, record_phase, record_ts, method, ambient_temp,
                    tank_temps_json, status_grid_json, pump_readings_json, alarms_json, ack_alarm
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    draft["record_phase"],
                    draft["record_ts"],
                    draft.get("method", "Manual Input"),
                    float(draft.get("ambient_temp", 0.0) or 0.0),
                    json.dumps(draft.get("tank_temps", {})),
                    json.dumps(draft.get("status_grid", {})),
                    json.dumps(draft.get("pump_readings", {})),
                    json.dumps(all_alarms),
                    1 if all_alarms and alarm_ack else 0,
                ),
            )
            saved_record_id = c.lastrowid
            conn.commit()
            conn.close()

            add_event_log_entry(f"New record saved ({draft['record_phase']}).")
            for alarm_item in all_alarms:
                add_event_log_entry(f"ALARM {alarm_item['pump_id']}: {'; '.join(alarm_item['alarms'])}")

            alarm_pump_ids = set()
            for alarm_item in all_alarms:
                pid = str(alarm_item.get("pump_id", "")).strip()
                if pid:
                    alarm_pump_ids.add(pid)
            stable_running_pumps = []
            for pid, grid in (draft.get("status_grid", {}) or {}).items():
                if str(grid.get("status", "")).upper() == "RUNNING" and pid not in alarm_pump_ids:
                    stable_running_pumps.append(str(pid))

            closed_ids = auto_close_maintenance_for_stable_pumps(project_id, stable_running_pumps)
            if closed_ids:
                add_event_log_entry(f"Auto-closed maintenance events: {', '.join([str(x) for x in closed_ids])}.")

            persist_event_log_for_project(project_id)

            draft["save_completed"] = True
            draft["saved_record_id"] = saved_record_id
            draft["review_rows"] = review_rows
            draft["alarms"] = all_alarms
            queue_confirmation("Record saved successfully.")
            st.rerun()
        except Exception as e:
            st.error(f"Could not save record: {e}")

    if draft.get("save_completed", False):
        maintenance_candidates = draft.get("maintenance_candidates", [])
        if maintenance_candidates:
            pumps_text = ", ".join(maintenance_candidates)
            st.markdown(
                f"<div style='background:#1E293B; border:1px solid #334155; color:#FFFFFF; padding:10px; border-radius:6px; margin-top:10px;'>Pump(s) {pumps_text} were taken offline. Would you like to log a Maintenance Event now?</div>",
                unsafe_allow_html=True,
            )
            c1, c2 = st.columns(2)
            if c1.button("Yes, Log Maintenance", use_container_width=True, key="log_maintenance_yes"):
                st.session_state.maintenance_prefill_pumps = maintenance_candidates
                st.session_state.maintenance_source_record_id = draft.get("saved_record_id")
                st.session_state.page = "add_maintenance"
                st.session_state.add_record_draft = {}
                st.rerun()
            if c2.button("No, Return to Dashboard", use_container_width=True, key="log_maintenance_no"):
                st.session_state.page = "dashboard"
                st.session_state.add_record_draft = {}
                st.rerun()
        else:
            st.session_state.page = "dashboard"
            st.session_state.add_record_draft = {}
            st.rerun()

# --- 3. THE WIZARD (FULL STEPS RESTORED) ---
def render_project_form():
    inject_industrial_css()
    step = st.session_state.wizard_step
    st.markdown(f"<p style='text-align:right; color:white; font-size:18px;'>Step {step} of 6</p>", unsafe_allow_html=True)
    st.progress(step / 6.0)

    if st.button("Cancel & Return"):
        st.session_state.page = "home"; st.rerun()
    
    # STEP 1: TEST DEFINITION ---
    # --- STEP 1: TEST DEFINITION ---
    if step == 1:
        st.markdown("<div class='step-title'>1. Test Definition</div>", unsafe_allow_html=True)

        # 1. PUMP TYPE (Radio, 2 options, row)
        p_types = ["Centrifugal", "Submersible"]
        saved_p_type = st.session_state.get("proj_type", "Centrifugal")
        proj_type = st.radio("Pump Type", p_types, index=p_types.index(saved_p_type) if saved_p_type in p_types else 0, horizontal=True)
        st.session_state.proj_type = proj_type

        # 2. TEST TYPE (Text Input)
        saved_t_type = st.session_state.get("test_type", "")
        test_type = st.text_input("Test Type", value=saved_t_type)
        st.session_state.test_type = test_type

        # 3. RUN MODE (Radio, 2 options, row)
        r_modes = ["Continuous", "Intermittent"]
        saved_r_mode = st.session_state.get("run_mode", "Continuous")
        run_mode = st.radio("Run Mode", r_modes, index=r_modes.index(saved_r_mode) if saved_r_mode in r_modes else 0, horizontal=True)
        st.session_state.run_mode = run_mode

        # 4. TARGET VALUE (free text numeric input)
        if "target_val_input" not in st.session_state:
            st.session_state.target_val_input = str(st.session_state.get("target_val", "1.0"))

        target_val_text = st.text_input("Target Value", value=st.session_state.target_val_input, key="target_val_input")
        target_value_valid = True
        try:
            parsed_target = float(str(target_val_text).strip())
            if parsed_target <= 0:
                raise ValueError
            st.session_state.target_val = parsed_target
        except (ValueError, TypeError):
            target_value_valid = False
            st.markdown(
                "<p style='color: white; background:#1E293B; border:1px solid #334155; padding:8px; border-radius:6px;'>Please enter a valid positive numeric Target Value.</p>",
                unsafe_allow_html=True,
            )

        unit_options = ["HR", "Days", "Cycles"]
        saved_unit = st.session_state.get("target_unit", "HR")
        target_unit = st.radio("Unit", unit_options, index=unit_options.index(saved_unit) if saved_unit in unit_options else 0, horizontal=True)
        st.session_state.target_unit = target_unit

        # 5. PROJECT NAME (auto-generated, displayed at bottom)
        project_name = f"{proj_type} {test_type} {run_mode} {st.session_state.get('target_val', target_val_text)} {target_unit}"
        st.session_state.project_name = project_name

        st.markdown(f"<div style='margin-top:20px; color:#0d6efd; font-size:20px; font-weight:bold;'>Project Name: {project_name}</div>", unsafe_allow_html=True)

        st.write("")
        if st.button("Next Step"):
            if target_value_valid:
                st.session_state.wizard_step = 2
                st.rerun()
            else:
                st.error("Please fix Target Value before continuing.")

   # STEP 2: Full Pump Specification
    elif step == 2:
        st.markdown("<div class='step-title'>2. Pump Specification</div>", unsafe_allow_html=True)
        
        # 1. Initialize DataFrame
        if "specs_df" not in st.session_state or st.session_state.specs_df is None:
            st.session_state.specs_df = pd.DataFrame(columns=[
                "Pump Model", "Pump ID", "ISO No.", "HP", "kW", 
                "Voltage (V)", "Amp Min", "Amp Max", "Phase", "Hertz", "Insulation"
            ])

        # 2. Wrap the Table in a FORM to stop the vibration
        with st.form("pump_spec_form", clear_on_submit=False):
            st.markdown("<p style='color: white;'>⚠️ Type all data, then click 'Confirm Table Entries' below to lock in IDs.</p>", unsafe_allow_html=True)

            step2_config = {
                "Pump Model": st.column_config.TextColumn("Pump Model", required=True, default=""),
                "Pump ID": st.column_config.TextColumn("Pump ID", disabled=True),
                "Hertz": st.column_config.SelectboxColumn("Hertz", options=["50", "60"], default="60"),
                "Phase": st.column_config.SelectboxColumn("Phase", options=[1, 3], default=3),
            }

            # Ensure required columns always exist before editing
            required_cols = ["Pump Model", "Pump ID", "ISO No.", "HP", "kW", "Voltage (V)", "Amp Min", "Amp Max", "Phase", "Hertz", "Insulation"]
            for col in required_cols:
                if col not in st.session_state.specs_df.columns:
                    st.session_state.specs_df[col] = "" if col not in ["HP", "kW", "Amp Min", "Amp Max", "Phase"] else 0

            # This editor is now "silent" - it won't vibrate!
            updated_df = st.data_editor(
                st.session_state.specs_df[required_cols],
                num_rows="dynamic",
                use_container_width=True,
                hide_index=True,
                column_config=step2_config,
                key="pump_editor_form_mode"
            )

            # The "Enter" clause - This processes everything at once
            submitted = st.form_submit_button("Confirm Table Entries", use_container_width=True)

            if submitted:
                # Defensive: Check if 'Pump Model' column exists after editing
                if "Pump Model" not in updated_df.columns:
                    st.error("'Pump Model' column is missing. Please do not remove required columns.")
                else:
                    final_df = updated_df.dropna(subset=["Pump Model"]).reset_index(drop=True)
                    final_df["Pump ID"] = [f"P-{str(i+1).zfill(2)}" for i in range(len(final_df))]
                    st.session_state.specs_df = final_df
                    queue_confirmation("Table synced. Pump IDs generated. You can now click Next.")
                    st.rerun()

        # 3. Navigation Buttons (Outside the form)
        st.write("") 
        b1, b2 = st.columns(2)
        with b1:
            if st.button("Back", use_container_width=True):
                st.session_state.wizard_step = 1
                st.rerun()
        with b2:
            if st.button("Next", use_container_width=True):
                # Check if they confirmed the table first
                if not st.session_state.specs_df.empty:
                    st.session_state.wizard_step = 3
                    st.rerun()
                else:
                    st.error("Please confirm your table entries first!")

    # STEP 3: Installation Layout
    elif step == 3:
        st.markdown("<div class='step-title'>3. Installation Layout</div>", unsafe_allow_html=True)
        
        # 1. Initialize Water Tanks list if not present
        if "water_tanks" not in st.session_state:
            st.session_state.water_tanks = ["Water Tank 1"]

        # 2. Buttons to Manage Tanks (Now on Top)
        col_t1, col_t2, col_t3 = st.columns([2, 1, 1])
        
        with col_t2:
            if st.button("Add Tank", use_container_width=True, key="add_tank_btn"):
                new_tank_num = len(st.session_state.water_tanks) + 1
                st.session_state.water_tanks.append(f"Water Tank {new_tank_num}")
                st.rerun()
                
        with col_t3:
            # We disable the delete button if there is only 1 tank left
            disable_delete = len(st.session_state.water_tanks) <= 1
            if st.button("Remove Last Tank", use_container_width=True, disabled=disable_delete, key="remove_tank_btn"):
                removed_tank = st.session_state.water_tanks.pop()
                
                # SAFETY CHECK: Reassign orphaned pumps back to Tank 1
                if "layout_df" in st.session_state and isinstance(st.session_state.layout_df, pd.DataFrame):
                    if "Assigned Tank" in st.session_state.layout_df.columns:
                        st.session_state.layout_df.loc[
                            st.session_state.layout_df["Assigned Tank"] == removed_tank, 
                            "Assigned Tank"
                        ] = "Water Tank 1"
                st.rerun()

        # 3. Display Active Tanks (Moved Below, Larger Font, Left Aligned)
        st.markdown(
            f"<div style='text-align: left; margin-top: 15px; margin-bottom: 10px;'>"
            f"<span style='color: white; font-size: 22px; font-weight: bold;'>Active Tanks: </span>"
            f"<span style='color: #4DA3FF; font-size: 22px; font-weight: 500;'>{' &nbsp;|&nbsp; '.join(st.session_state.water_tanks)}</span>"
            f"</div>", 
            unsafe_allow_html=True
        )

        st.divider()

        # 4. Prepare the Master Mapping Table
        if "specs_df" in st.session_state and not st.session_state.specs_df.empty:
            pumps_from_step2 = st.session_state.specs_df[["Pump ID", "Pump Model"]].copy()
            
            needs_rebuild = True
            if "layout_df" in st.session_state and isinstance(st.session_state.layout_df, pd.DataFrame):
                if "Assigned Tank" in st.session_state.layout_df.columns and len(st.session_state.layout_df) == len(pumps_from_step2):
                    needs_rebuild = False
                    
            if needs_rebuild:
                st.session_state.layout_df = pumps_from_step2
                st.session_state.layout_df["Assigned Tank"] = st.session_state.water_tanks[0]
                
        else:
            st.warning("No pumps found from Step 2. Please go back and add pumps first.")
            st.stop()

        # 5. The Form 
        with st.form("layout_mapping_form"):
            st.markdown("<p style='color: white;'>⚠️ Assign each pump to a Water Tank and click Confirm.</p>", unsafe_allow_html=True)
            
            layout_config = {
                "Pump ID": st.column_config.TextColumn("Pump ID", disabled=True),
                "Pump Model": st.column_config.TextColumn("Pump Model", disabled=True),
                "Assigned Tank": st.column_config.SelectboxColumn(
                    "Assigned Tank", 
                    options=st.session_state.water_tanks,
                    required=True
                )
            }

            updated_layout = st.data_editor(
                st.session_state.layout_df,
                use_container_width=True,
                hide_index=True,
                column_config=layout_config,
                key="layout_master_editor"
            )
            
            confirm = st.form_submit_button("Confirm Layout Changes", use_container_width=True)
            if confirm:
                st.session_state.layout_df = updated_layout.reset_index(drop=True)
                queue_confirmation("Layout mappings saved.")
                st.rerun()

        # 6. Navigation
        st.write("")
        b1, b2 = st.columns(2)
        with b1:
            if st.button("Back", use_container_width=True, key="back_step3"):
                st.session_state.wizard_step = 2
                st.rerun()
        with b2:
            if st.button("Next", use_container_width=True, key="next_step3"):
                if "updated_layout" in locals():
                    st.session_state.layout_df = updated_layout.reset_index(drop=True)
                st.session_state.wizard_step = 4
                st.rerun()

    # STEP 4: Hardware & Sensor Mapping
    elif step == 4:
        st.markdown("<div class='step-title'>4. Hardware & Sensor Mapping</div>", unsafe_allow_html=True)

        # --- FORCE REHYDRATE HARDWARE STATE IF RESTORING ---
        if st.session_state.get("_restoring_project", False):
            import json
            conn = sqlite3.connect(DB_FILE)
            proj_row = conn.execute("SELECT hardware_list, hardware_dfs, hardware_ds FROM projects WHERE project_id = ?", (st.session_state.get("current_project", ""),)).fetchone()
            conn.close()
            if proj_row:
                # hardware_list
                try:
                    st.session_state.hardware_list = json.loads(proj_row[0]) if proj_row[0] else []
                except Exception:
                    st.session_state.hardware_list = []
                # hardware_dfs
                try:
                    dfs = json.loads(proj_row[1]) if proj_row[1] else {}
                    for k, v in dfs.items():
                        st.session_state[k] = pd.read_json(v)
                except Exception:
                    pass
                # hardware_ds
                try:
                    dss = json.loads(proj_row[2]) if proj_row[2] else {}
                    for k, v in dss.items():
                        st.session_state[k] = v
                except Exception:
                    pass
            st.session_state._restoring_project = False

        # 1. Build the Master Assignment Lists
        if "specs_df" in st.session_state and not st.session_state.specs_df.empty:
            available_pumps = st.session_state.specs_df["Pump ID"].tolist()
        else:
            available_pumps = ["P-01"] # Fallback
        if "water_tanks" in st.session_state:
            available_tanks = st.session_state.water_tanks
        else:
            available_tanks = ["Water Tank 1"]
        assignment_options = ["None (Unused)", "Global (Ambient Room)"] + available_tanks + available_pumps

        # 2. Hardware Inventory Initialization
        if "hardware_list" not in st.session_state:
            st.session_state.hardware_list = []

        # 3. Add & Remove Hardware Buttons
        st.markdown("<p class='col-header'>1. Add Hardware Units</p>", unsafe_allow_html=True)
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            if st.button("HIOKI Temp", use_container_width=True, key="add_htemp"):
                count = sum(1 for hw in st.session_state.hardware_list if "HIOKI Temp" in hw)
                st.session_state.hardware_list.append(f"HIOKI Temp {count + 1}")
                st.rerun()
        with col2:
            if st.button("HIOKI Power", use_container_width=True, key="add_hpower"):
                count = sum(1 for hw in st.session_state.hardware_list if "HIOKI Power" in hw)
                st.session_state.hardware_list.append(f"HIOKI Power {count + 1}")
                st.rerun()
        with col3:
            if st.button("HIOKI Clamp", use_container_width=True, key="add_hclamp"):
                count = sum(1 for hw in st.session_state.hardware_list if "HIOKI Clamp" in hw)
                st.session_state.hardware_list.append(f"HIOKI Clamp {count + 1}")
                st.rerun()
        with col4:
            if st.button("General HW", use_container_width=True, key="add_gen"):
                count = sum(1 for hw in st.session_state.hardware_list if "General HW" in hw)
                st.session_state.hardware_list.append(f"General HW {count + 1}")
                st.rerun()
        with col5:
            disable_del = len(st.session_state.hardware_list) == 0
            if st.button("🗑️ Remove Last", use_container_width=True, disabled=disable_del, key="del_hw"):
                removed_hw = st.session_state.hardware_list.pop()
                if f"df_{removed_hw}" in st.session_state:
                    del st.session_state[f"df_{removed_hw}"]
                if f"ds_{removed_hw}" in st.session_state:
                    del st.session_state[f"ds_{removed_hw}"]
                st.rerun()

        # Display Active Hardware
        if st.session_state.hardware_list:
            st.markdown(
                f"<div style='margin-top: 10px; margin-bottom: 20px;'>"
                f"<span style='color: white; font-size: 18px; font-weight: bold;'>Active Units: </span>"
                f"<span style='color: #0d6efd; font-size: 18px; font-weight: 500;'>{' &nbsp;|&nbsp; '.join(st.session_state.hardware_list)}</span>"
                f"</div>", 
                unsafe_allow_html=True
            )
        else:
            st.info("No hardware added yet. Please add a unit above.")

        st.divider()

        # 4. Hardware Configuration Form 
        if st.session_state.hardware_list:
            with st.form("hardware_mapping_form"):
                st.markdown("<p style='color: white;'>⚠️ Configure channels and data sources, then click 'Confirm Hardware Setup' below.</p>", unsafe_allow_html=True)
                
                updated_dfs = {}
                updated_ds = {} 

                for hw_name in st.session_state.hardware_list:
                    st.markdown(f"<p class='white-text' style='color:#0d6efd !important; font-size: 20px !important;'>{hw_name} Configuration</p>", unsafe_allow_html=True)
                    df_key = f"df_{hw_name}"
                    ds_key = f"ds_{hw_name}" 
                    
                    # Forcefully deletes the "Data Source" column from old memory if it exists
                    if df_key in st.session_state and isinstance(st.session_state[df_key], pd.DataFrame):
                        if "Data Source" in st.session_state[df_key].columns:
                            st.session_state[df_key] = st.session_state[df_key].drop(columns=["Data Source"])
                    
                    # Set allowed Data Source options
                    if "General HW" in hw_name:
                        ds_options = ["Manual Input", "Voice Recording", "ESP32 Pulse", "Direct Analog"]
                    elif "HIOKI Clamp" in hw_name:
                        ds_options = ["Manual Input", "Voice Recording", "ESP32 CAM (OCR)"]
                    else:
                        ds_options = ["Manual Input", "Voice Recording", "ESP32 CAM (OCR)"]
                        
                    if ds_key not in st.session_state:
                        st.session_state[ds_key] = ["Manual Input"]
                    
                    # --- A. HIOKI TEMP METER ---
                    if "HIOKI Temp" in hw_name:
                        if df_key not in st.session_state:
                            st.session_state[df_key] = pd.DataFrame([{"CH": f"CH{i}", "Sensor Name": "", "Assigned To": "None (Unused)", "Measurement Type": "Exact"} for i in range(1, 11)])
                        
                        config = {"CH": st.column_config.TextColumn("Channel", disabled=True), "Sensor Name": st.column_config.TextColumn("Sensor Name"), "Assigned To": st.column_config.SelectboxColumn("Assigned To", options=assignment_options), "Measurement Type": st.column_config.SelectboxColumn("Measurement Type", options=["Exact", "Max Temp", "Average"])}
                        updated_dfs[df_key] = st.data_editor(st.session_state[df_key], use_container_width=True, hide_index=True, column_config=config, key=f"edit_{hw_name}")

                    # --- B. HIOKI POWER METER ---
                    elif "HIOKI Power" in hw_name:
                        if df_key not in st.session_state:
                            st.session_state[df_key] = pd.DataFrame([{"Terminal": t, "Assigned To": "None (Unused)"} for t in ["U1", "V1", "W1", "A1", "A2", "A3"]])
                        
                        config = {"Terminal": st.column_config.TextColumn("Terminal", disabled=True), "Assigned To": st.column_config.SelectboxColumn("Assigned To", options=assignment_options)}
                        updated_dfs[df_key] = st.data_editor(st.session_state[df_key], use_container_width=True, hide_index=True, column_config=config, key=f"edit_{hw_name}")

                    # --- C. HIOKI CLAMP METER ---
                    elif "HIOKI Clamp" in hw_name:
                        if df_key not in st.session_state:
                            st.session_state[df_key] = pd.DataFrame([{"Pump ID": p, "Sensor Name": "Clamp Meter", "Read Status": "On (Yes Read)"} for p in available_pumps])
                        
                        config = {
                            "Pump ID": st.column_config.TextColumn("Pump ID", disabled=True),
                            "Sensor Name": st.column_config.TextColumn("Sensor Name", required=True),
                            "Read Status": st.column_config.SelectboxColumn("Read Status", options=["On (Yes Read)", "Off (No Read)"])
                        }
                        updated_dfs[df_key] = st.data_editor(st.session_state[df_key], use_container_width=True, hide_index=True, column_config=config, key=f"edit_{hw_name}")

                    # --- D. GENERAL HARDWARE ---
                    elif "General HW" in hw_name:
                        if df_key not in st.session_state:
                            st.session_state[df_key] = pd.DataFrame([{"Sensor Name": "", "Parameter": "Counter", "Assigned To": "None (Unused)"}])
                        
                        config = {"Sensor Name": st.column_config.TextColumn("Sensor Name", required=True), "Parameter": st.column_config.SelectboxColumn("Parameter", options=["Counter", "Temperature", "Voltage", "Current", "Flow", "Other"]), "Assigned To": st.column_config.SelectboxColumn("Assigned To", options=assignment_options)}
                        updated_dfs[df_key] = st.data_editor(st.session_state[df_key], num_rows="dynamic", use_container_width=True, hide_index=True, column_config=config, key=f"edit_{hw_name}")
                    
                    # --- MULTISELECT FOR ENTRY METHODS (No HTML Box around it) ---
                    st.write("") # Just a small space for visual padding
                    updated_ds[ds_key] = st.multiselect(
                        f"Allowed Data Entry Methods for {hw_name}:",
                        options=ds_options,
                        default=st.session_state[ds_key],
                        key=f"multi_ds_{hw_name}"
                    )
                    st.divider()

                confirm = st.form_submit_button("Confirm Hardware Setup", use_container_width=True)
                if confirm:
                    for key, edited_df in updated_dfs.items():
                        st.session_state[key] = edited_df
                    for key, selected_ds in updated_ds.items():
                        st.session_state[key] = selected_ds
                    queue_confirmation("All hardware configurations saved.")
                    st.rerun()

        # 5. Navigation
        st.write("")
        b1, b2 = st.columns(2)
        with b1:
            if st.button("Back", use_container_width=True, key="back_step4"):
                st.session_state.wizard_step = 3
                st.rerun()
        with b2:
            if st.button("Next", use_container_width=True, key="next_step4"):
                if 'updated_dfs' in locals():
                    for key, edited_df in updated_dfs.items():
                        st.session_state[key] = edited_df
                    for key, selected_ds in updated_ds.items():
                        st.session_state[key] = selected_ds
                st.session_state.wizard_step = 5
                st.rerun()

    # STEP 5: Variable Mapping & Custom Formulas
    elif step == 5:
        st.markdown("<div class='step-title'>5. Formulas & Calculations</div>", unsafe_allow_html=True)
        
        # 1. GATHER ALL ACTIVE SENSORS FROM STEP 4 (Label Logic Updated)
        active_sensors = []
        if "hardware_list" in st.session_state:
            for hw in st.session_state.hardware_list:
                df_key = f"df_{hw}"
                if df_key in st.session_state and isinstance(st.session_state[df_key], pd.DataFrame):
                    df = st.session_state[df_key]
                    
                    # Logic to identify the assignment column (Assigned To or Pump ID)
                    assign_col = "Assigned To" if "Assigned To" in df.columns else "Pump ID"
                    
                    if assign_col in df.columns:
                        for _, row in df.iterrows():
                            assigned = row.get(assign_col, "None (Unused)")
                            if assigned != "None (Unused)":
                                # Extract Name and Channel/Terminal info
                                s_name = row.get("Sensor Name", row.get("Name", "Unnamed"))
                                ch_or_term = row.get("CH", row.get("Terminal", "General"))
                                
                                # This creates the label: "STATOR SENSOR (P-01) [HIOKI Temp 1 - CH1]"
                                full_label = f"{s_name.upper()} ({assigned}) [{hw} - {ch_or_term}]"
                                active_sensors.append(full_label)
        
        if not active_sensors:
            active_sensors = ["No Active Sensors Found"]

        # Pull available pumps and tanks for formula assignment
        pump_options = ["Global (Apply to All Compatible Pumps)"]
        # Add water tank options if available
        if "water_tanks" in st.session_state and st.session_state.water_tanks:
            pump_options += [f"Water Tank: {tank}" for tank in st.session_state.water_tanks]
        # Add individual pumps
        if "specs_df" in st.session_state and not st.session_state.specs_df.empty:
            pump_options += st.session_state.specs_df["Pump ID"].tolist()
        else:
            pump_options += ["P-01"]

        # 2. INITIALIZE DATAFRAMES
        if "var_mapping_df" not in st.session_state:
            st.session_state.var_mapping_df = pd.DataFrame([
                {"Variable": "T_amb", "Mapped Sensor": active_sensors[0] if active_sensors else "None"},
                {"Variable": "T_stat", "Mapped Sensor": active_sensors[0] if active_sensors else "None"}
            ])
            
        if "formulas_df" not in st.session_state:
            st.session_state.formulas_df = pd.DataFrame([
                {"Formula Name": "Temperature Rise", "Target": "Global (Apply to All Compatible Pumps)", "Equation": "T_stat - T_amb"}
            ])

        # 3. THE FORM (Using your exact layout and clear_on_submit fix)
        with st.form("formula_builder_form", clear_on_submit=False):
            st.markdown("<p style='color: white;'>⚠️ Define your variables, write your equations, and hit Confirm.</p>", unsafe_allow_html=True)
            
            # --- SECTION 1: VARIABLE MAPPING ---
            st.markdown("<p class='white-text' style='color:#0d6efd !important; font-size: 20px !important;'>1. Variable Mapping</p>", unsafe_allow_html=True)
            st.markdown("<p style='color: #ccc; font-size: 14px;'>Assign a short Variable name (like 'V1' or 'T_amb') to a physical sensor.</p>", unsafe_allow_html=True)
            
            var_config = {
                "Variable": st.column_config.TextColumn("Variable (e.g., T_amb)", required=True),
                "Mapped Sensor": st.column_config.SelectboxColumn("Hardware Sensor Source", options=active_sensors, required=True)
            }
            
            updated_vars = st.data_editor(
                st.session_state.var_mapping_df, 
                num_rows="dynamic", 
                use_container_width=True, 
                hide_index=True, 
                column_config=var_config, 
                key="edit_vars_stable"
            )
            
            st.write("")
            st.divider()
            
            # --- SECTION 2: CUSTOM FORMULA BUILDER ---
            st.markdown("<p class='white-text' style='color:#0d6efd !important; font-size: 20px !important;'>2. Custom Formula Builder</p>", unsafe_allow_html=True)
            st.markdown("<p style='color: #ccc; font-size: 14px;'>Use the exact Variable names from above to write your math equations.</p>", unsafe_allow_html=True)
            
            form_config = {
                "Formula Name": st.column_config.TextColumn("Formula Name", required=True),
                "Target": st.column_config.SelectboxColumn("Target Pump(s)", options=pump_options, required=True),
                "Equation": st.column_config.TextColumn("Equation (Math)", required=True)
            }
            
            updated_forms = st.data_editor(
                st.session_state.formulas_df, 
                num_rows="dynamic", 
                use_container_width=True, 
                hide_index=True, 
                column_config=form_config, 
                key="edit_formulas_stable"
            )

            st.write("")
            confirm = st.form_submit_button("Confirm Formulas", use_container_width=True)
            if confirm:
                st.session_state.var_mapping_df = updated_vars.reset_index(drop=True)
                st.session_state.formulas_df = updated_forms.reset_index(drop=True)
                queue_confirmation("Variables and formulas saved.")
                st.rerun()

        # 4. NAVIGATION
        st.write("")
        b1, b2 = st.columns(2)
        with b1:
            if st.button("Back", use_container_width=True, key="back_step5"):
                st.session_state.wizard_step = 4
                st.rerun()
        with b2:
            if st.button("Next", use_container_width=True, key="next_step5"):
                if 'updated_vars' in locals():
                    st.session_state.var_mapping_df = updated_vars.reset_index(drop=True)
                    st.session_state.formulas_df = updated_forms.reset_index(drop=True)
                st.session_state.wizard_step = 6
                st.rerun()

    # STEP 6 (DASHBOARD & REPORT SET UP) ---

    elif step == 6:
        # Auto-scroll to top
        st.markdown("<script>window.scrollTo(0, 0);</script>", unsafe_allow_html=True)
        st.markdown("<div class='step-title'>6. Dashboard and Report Set up</div>", unsafe_allow_html=True)

        # --- PREPARE DATA FROM PREVIOUS STEPS ---
        if "specs_df" in st.session_state and not st.session_state.specs_df.empty:
            valid_pumps = st.session_state.specs_df["Pump ID"].tolist()
            pumps_df = st.session_state.specs_df.copy()
        else:
            valid_pumps = ["P-01"]
            pumps_df = pd.DataFrame({"Pump ID": ["P-01"], "Amp Max": [10.0]})

        # --- 1. SYSTEM WATCHDOGS (One row per method, multiple types per method) ---
        st.markdown("<p style='color: white; font-size: 18px; font-weight: bold;'>1. System Watchdogs & Safety Limits</p>", unsafe_allow_html=True)
        allowed_methods = []
        if "hardware_list" in st.session_state:
            for hw in st.session_state.hardware_list:
                ds_key = f"ds_{hw}"
                if ds_key in st.session_state:
                    allowed_methods.extend(st.session_state[ds_key])
        allowed_methods = sorted(list(set(allowed_methods)))
        if not allowed_methods:
            allowed_methods = ["Manual Input"]
        watchdog_types = ["ON/OFF", "Connection Status (ONLINE/OFFLINE)", "ESP32 Internal Temperature"]

        # --- Initialization for Create/Modify ---
        if st.session_state.get("_restoring_project", False):
            # On Modify, restore tables from DB (already handled in restore logic)
            pass
        else:
            # On Create New Project, initialize empty/default tables
            if "watchdogs_df" not in st.session_state or st.session_state.page == "create" and st.session_state.get("_new_project", False):
                st.session_state.watchdogs_df = pd.DataFrame(columns=["Data Entry Method", "Watchdog Type"])
            if "watchdog_matrix_df" not in st.session_state or st.session_state.page == "create" and st.session_state.get("_new_project", False):
                st.session_state.watchdog_matrix_df = pd.DataFrame()
            if "limits_df" not in st.session_state or st.session_state.page == "create" and st.session_state.get("_new_project", False):
                limits = []
                for _, row in pumps_df.iterrows():
                    insulation = row.get("Insulation", "")
                    if str(insulation).strip().upper() == "F":
                        max_stator_temp = 155.0
                    elif str(insulation).strip().upper() == "H":
                        max_stator_temp = 180.0
                    else:
                        max_stator_temp = 130.0
                    try:
                        amp_max = float(row.get("Amp Max", 0.0))
                    except (ValueError, TypeError):
                        amp_max = 0.0
                    limits.append({
                        "Pump ID": row.get("Pump ID", "Unknown"),
                        "Max Stator Temp (°C)": max_stator_temp,
                        "Max Current (A)": amp_max
                    })
                st.session_state.limits_df = pd.DataFrame(limits)
            if "extra_limits_df" not in st.session_state or st.session_state.page == "create" and st.session_state.get("_new_project", False):
                st.session_state.extra_limits_df = pd.DataFrame(columns=["Formula Name", "Min Value", "Max Value", "Applies To"])
            if "event_log" not in st.session_state or st.session_state.page == "create" and st.session_state.get("_new_project", False):
                st.session_state.event_log = []

        # Build/refresh watchdog matrix from allowed methods + previous selections.
        existing_selected = {}
        existing_wd = st.session_state.get("watchdogs_df", pd.DataFrame(columns=["Data Entry Method", "Watchdog Type"]))
        if isinstance(existing_wd, pd.DataFrame) and not existing_wd.empty:
            for _, row in existing_wd.iterrows():
                method = str(row.get("Data Entry Method", "")).strip()
                wd_type = str(row.get("Watchdog Type", "")).strip()
                if method and wd_type:
                    existing_selected.setdefault(method, set()).add(wd_type)

        matrix_rows = []
        for method in allowed_methods:
            selected = existing_selected.get(method, set())
            matrix_rows.append({
                "Data Entry Method": method,
                "ON/OFF": "ON/OFF" in selected,
                "Connection Status (ONLINE/OFFLINE)": "Connection Status (ONLINE/OFFLINE)" in selected,
                "ESP32 Internal Temperature": "ESP32 Internal Temperature" in selected,
            })

        wd_matrix_df = pd.DataFrame(matrix_rows)
        if "watchdog_matrix_df" not in st.session_state or not isinstance(st.session_state.watchdog_matrix_df, pd.DataFrame):
            st.session_state.watchdog_matrix_df = wd_matrix_df.copy()

        with st.form("watchdog_setup_form", clear_on_submit=False):
            st.markdown("<p style='color: #ccc; font-size: 14px;'>Each row maps one allowed Data Entry Method from Step 4. Check one or more watchdogs per row.</p>", unsafe_allow_html=True)

            wd_config = {
                "Data Entry Method": st.column_config.TextColumn("Data Entry Method", disabled=True),
                "ON/OFF": st.column_config.CheckboxColumn("ON/OFF"),
                "Connection Status (ONLINE/OFFLINE)": st.column_config.CheckboxColumn("Connection Status (ONLINE/OFFLINE)"),
                "ESP32 Internal Temperature": st.column_config.CheckboxColumn("ESP32 Internal Temperature"),
            }
            edited_wd_matrix = st.data_editor(
                wd_matrix_df,
                hide_index=True,
                use_container_width=True,
                column_config=wd_config,
                key="watchdogs_matrix_edit",
                num_rows="fixed"
            )

            save_watchdogs = st.form_submit_button("Confirm Watchdog Setup", use_container_width=True)
            if save_watchdogs:
                st.session_state.watchdog_matrix_df = edited_wd_matrix.reset_index(drop=True)
                expanded = []
                for _, row in st.session_state.watchdog_matrix_df.iterrows():
                    method = row.get("Data Entry Method", "")
                    if row.get("ON/OFF", False):
                        expanded.append({"Data Entry Method": method, "Watchdog Type": "ON/OFF"})
                    if row.get("Connection Status (ONLINE/OFFLINE)", False):
                        expanded.append({"Data Entry Method": method, "Watchdog Type": "Connection Status (ONLINE/OFFLINE)"})
                    if row.get("ESP32 Internal Temperature", False):
                        expanded.append({"Data Entry Method": method, "Watchdog Type": "ESP32 Internal Temperature"})

                st.session_state.watchdogs_df = pd.DataFrame(expanded, columns=["Data Entry Method", "Watchdog Type"])
                st.session_state.watchdog_sync_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                queue_confirmation("Watchdog table saved.")
                st.rerun()

        # --- 2. SAFETY LIMITS ---
        st.markdown("<p style='color: white; font-size: 18px; font-weight: bold;'>2. Safety Limits</p>", unsafe_allow_html=True)

        # Sync base limits with current pump list (always rebuild one row per Step 2 pump, then overlay saved edits)
        current_pump_ids = pumps_df["Pump ID"].tolist() if not pumps_df.empty else []
        existing_limits = st.session_state.get("limits_df", pd.DataFrame(columns=["Pump ID", "Max Stator Temp (°C)", "Max Current (A)"]))
        if not isinstance(existing_limits, pd.DataFrame):
            existing_limits = pd.DataFrame(columns=["Pump ID", "Max Stator Temp (°C)", "Max Current (A)"])
        for col in ["Pump ID", "Max Stator Temp (°C)", "Max Current (A)"]:
            if col not in existing_limits.columns:
                existing_limits[col] = "" if col == "Pump ID" else 0.0

        existing_lookup = {}
        for _, existing_row in existing_limits.iterrows():
            pid = existing_row.get("Pump ID", "")
            if pid:
                existing_lookup[pid] = existing_row

        rebuilt_limits = []
        for _, row in pumps_df.iterrows():
            pid = row.get("Pump ID", "")
            if not pid:
                continue
            ins = row.get("Insulation", "")
            default_temp = 155.0 if str(ins).strip().upper() == "F" else (180.0 if str(ins).strip().upper() == "H" else 130.0)
            try:
                default_amp = float(row.get("Amp Max", 0.0))
            except (ValueError, TypeError):
                default_amp = 0.0

            if pid in existing_lookup:
                saved_row = existing_lookup[pid]
                max_temp = saved_row.get("Max Stator Temp (°C)", default_temp)
                max_current = saved_row.get("Max Current (A)", default_amp)
                if pd.isna(max_temp) or max_temp == "":
                    max_temp = default_temp
                if pd.isna(max_current) or max_current == "":
                    max_current = default_amp
            else:
                max_temp = default_temp
                max_current = default_amp

            rebuilt_limits.append({
                "Pump ID": pid,
                "Max Stator Temp (°C)": float(max_temp),
                "Max Current (A)": float(max_current),
            })

        st.session_state.limits_df = pd.DataFrame(rebuilt_limits, columns=["Pump ID", "Max Stator Temp (°C)", "Max Current (A)"])

        # Formula names from Step 5 for extra limits dropdown
        formula_names = []
        if "formulas_df" in st.session_state and isinstance(st.session_state.formulas_df, pd.DataFrame):
            if "Formula Name" in st.session_state.formulas_df.columns:
                formula_names = st.session_state.formulas_df["Formula Name"].dropna().tolist()
        if not formula_names:
            formula_names = ["(No formulas defined in Step 5)"]

        # Target options for extra limits (mirrors Step 5)
        extra_target_options = ["Global (All Pumps)"]
        if "water_tanks" in st.session_state:
            extra_target_options += [f"Water Tank: {t}" for t in st.session_state.water_tanks]
        if "specs_df" in st.session_state and not st.session_state.specs_df.empty:
            extra_target_options += st.session_state.specs_df["Pump ID"].tolist()

        lim_df = st.session_state.limits_df.copy() if "limits_df" in st.session_state else pd.DataFrame(columns=["Pump ID", "Max Stator Temp (°C)", "Max Current (A)"])
        extra_lim_df = st.session_state.extra_limits_df.copy() if "extra_limits_df" in st.session_state else pd.DataFrame(columns=["Formula Name", "Min Value", "Max Value", "Applies To"])

        with st.form("limits_setup_form", clear_on_submit=False):
            # --- Section A: Default per-pump limits ---
            st.markdown("<p style='color: white; font-size: 15px; font-weight: bold;'>Default Pump Limits</p>", unsafe_allow_html=True)
            st.markdown("<p style='color: #ccc; font-size: 13px;'>Auto-populated from Step 2. Pump ID is locked. Edit temperature and current thresholds as needed.</p>", unsafe_allow_html=True)
            base_lim_config = {
                "Pump ID": st.column_config.TextColumn("Pump ID", disabled=True),
                "Max Stator Temp (°C)": st.column_config.NumberColumn("Max Stator Temp (°C)", required=True, format="%.1f"),
                "Max Current (A)": st.column_config.NumberColumn("Max Current (A)", required=True, format="%.2f"),
            }
            edited_lim = st.data_editor(
                lim_df,
                hide_index=True,
                use_container_width=True,
                column_config=base_lim_config,
                key="limits_base_edit",
                num_rows="fixed"
            )

            st.write("")
            # --- Section B: Additional formula-based limits ---
            st.markdown("<p style='color: white; font-size: 15px; font-weight: bold;'>Additional Formula Safety Limits</p>", unsafe_allow_html=True)
            st.markdown("<p style='color: #ccc; font-size: 13px;'>Select a formula from Step 5, set Min (optional) and Max thresholds, and choose which pumps apply. Use the \u271a row button to add entries.</p>", unsafe_allow_html=True)
            extra_lim_config = {
                "Formula Name": st.column_config.SelectboxColumn("Formula Name", options=formula_names, required=True),
                "Min Value": st.column_config.NumberColumn("Min Value (optional)", format="%.2f"),
                "Max Value": st.column_config.NumberColumn("Max Value", required=True, format="%.2f"),
                "Applies To": st.column_config.SelectboxColumn("Applies To", options=extra_target_options, required=True),
            }
            edited_extra_lim = st.data_editor(
                extra_lim_df,
                hide_index=True,
                use_container_width=True,
                column_config=extra_lim_config,
                key="limits_extra_edit",
                num_rows="dynamic"
            )

            save_limits = st.form_submit_button("Confirm Safety Limits", use_container_width=True)
            if save_limits:
                st.session_state.limits_df = edited_lim.reset_index(drop=True)
                st.session_state.extra_limits_df = edited_extra_lim.reset_index(drop=True)
                queue_confirmation("Safety limits saved.")
                st.rerun()

        st.divider()

        # --- 3. EVENT ALERT LOG (Dynamic, Scrollable) ---
        st.markdown("<p style='color: white; font-size: 18px; font-weight: bold;'>2. Event Alert Log</p>", unsafe_allow_html=True)
        if "event_log" not in st.session_state:
            st.session_state.event_log = []
        def log_event(msg):
            import datetime
            st.session_state.event_log.insert(0, f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")
        # Example: log project start if log is empty
        if not st.session_state.event_log:
            log_event("Project started.")
        # Display log
        st.write("")
        st.markdown("<div style='max-height:200px; overflow-y:auto; background:#181b20; border-radius:6px; padding:8px;'>", unsafe_allow_html=True)
        for entry in st.session_state.event_log:
            st.markdown(f"<div style='color:#eee; font-size:14px; margin-bottom:2px;'>{entry}</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.divider()

        # --- 4. DASHBOARD LAYOUT: 3x3 GRID PER TANK ---
        st.markdown("<p style='color: white; font-size: 18px; font-weight: bold;'>3. Dashboard Visual Layout Preview</p>", unsafe_allow_html=True)
        if "dashboard_main_tracker" not in st.session_state:
            st.session_state.dashboard_main_tracker = "Temperature"

        st.selectbox(
            "Main Dashboard Tracker",
            options=["Temperature", "Current"],
            index=0 if st.session_state.dashboard_main_tracker == "Temperature" else 1,
            key="dashboard_main_tracker",
        )

        if "layout_df" in st.session_state and "water_tanks" in st.session_state:
            layout_df = st.session_state.layout_df
            tanks = st.session_state.water_tanks
            limits_df = st.session_state.get("limits_df", pd.DataFrame(columns=["Pump ID", "Max Stator Temp (°C)", "Max Current (A)"]))
            extra_limits_df = st.session_state.get("extra_limits_df", pd.DataFrame(columns=["Formula Name", "Min Value", "Max Value", "Applies To"]))
            maint_by_pump = {}
            is_cycle_test = "Cycle" in st.session_state.get("test_type", "") or "Intermittent" in st.session_state.get("test_type", "") or "Cycle" in st.session_state.get("run_mode", "")
            target_val = st.session_state.get("target_val", "0")
            running_time_unit = "cycles" if is_cycle_test else "hrs"
            running_time_value = f"0 / {target_val} {running_time_unit}"

            limits_lookup = {}
            if isinstance(limits_df, pd.DataFrame) and not limits_df.empty and "Pump ID" in limits_df.columns:
                for _, limit_row in limits_df.iterrows():
                    limits_lookup[str(limit_row.get("Pump ID", ""))] = limit_row

            for tank in tanks:
                st.markdown(f"<div style='color:#4DA3FF; font-size:20px; font-weight:bold; margin-top:16px;'>Water Tank: {tank}</div>", unsafe_allow_html=True)
                tank_pumps = layout_df[layout_df["Assigned Tank"] == tank]["Pump ID"].tolist() if "Assigned Tank" in layout_df.columns and "Pump ID" in layout_df.columns else []

                if not tank_pumps:
                    st.info("No pumps assigned to this tank.")
                    continue

                for row_start in range(0, len(tank_pumps), 3):
                    row_pumps = tank_pumps[row_start:row_start+3]
                    cols = st.columns(3)
                    for i, p_id in enumerate(row_pumps):
                        pump_limits = limits_lookup.get(str(p_id))
                        try:
                            amp_max = float((pump_limits.get("Max Current (A)") if pump_limits is not None else 0.0) or 0.0)
                        except (ValueError, TypeError, AttributeError):
                            amp_max = 0.0
                        try:
                            temp_max = float((pump_limits.get("Max Stator Temp (°C)") if pump_limits is not None else 0.0) or 0.0)
                        except (ValueError, TypeError, AttributeError):
                            temp_max = 0.0

                        status_color = "value-grey"
                        light_class = "status-light-stop"
                        current_val = "0.00A"
                        temperature_val = "00.0°C"
                        svg_color = "#555"

                        formula_limits_html = '<div style="font-size: 10px; color: #666; margin-top: 10px;">No additional formula safety limits</div>'
                        if isinstance(extra_limits_df, pd.DataFrame) and not extra_limits_df.empty and "Applies To" in extra_limits_df.columns:
                            applicable_limits = []
                            for _, extra_row in extra_limits_df.iterrows():
                                applies_to = str(extra_row.get("Applies To", "")).strip()
                                matches_global = applies_to in ["Global (All Pumps)", "Global (Apply to All Compatible Pumps)"]
                                matches_pump = applies_to == str(p_id)
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
                            status_color = "#9CA3AF" if m_status == "Closed" else "#F59E0B"
                            m_ts = maintenance_info.get("event_ts", "")
                            m_type = maintenance_info.get("event_type", "")
                            maintenance_html = (
                                f'<div style="display:flex; justify-content:space-between; align-items:center; margin-top:8px;">'
                                f'<span style="font-size:10px; color:#BFC7D5;">{m_type} @ {m_ts}</span>'
                                f'<span style="font-size:10px; color:{status_color}; border:1px solid {status_color}; padding:1px 6px; border-radius:999px;">{m_status}</span>'
                                '</div>'
                                f'<div style="display:flex; justify-content:flex-end; margin-top:4px;">'
                                f'<span style="font-size:10px; color:{sev_color}; border:1px solid {sev_color}; padding:1px 6px; border-radius:999px;">{sev}</span>'
                                '</div>'
                            )

                        if st.session_state.dashboard_main_tracker == "Temperature":
                            primary_label = f"TEMPERATURE (MAX: {temp_max:.1f}°C)"
                            primary_val = temperature_val
                            secondary_label = f"CURRENT (MAX: {amp_max:.2f}A)"
                            secondary_val = current_val
                        else:
                            primary_label = f"LIVE CURRENT (MAX: {amp_max:.2f}A)"
                            primary_val = current_val
                            secondary_label = f"TEMPERATURE (MAX: {temp_max:.1f}°C)"
                            secondary_val = temperature_val

                        sparkline_tracker_label = st.session_state.dashboard_main_tracker.upper()
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
                                f'<div style="font-size: 10px; color: {svg_color}; font-weight: bold; margin-top: 3px;">STANDBY</div>'
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
        else:
            st.warning("No tank or pump layout found. Please complete previous steps.")

        if st.button("Confirm Dashboard Visual Layout Preview", use_container_width=True, key="confirm_dashboard_preview"):
            queue_confirmation("Dashboard visual layout preview confirmed.")
            st.rerun()

        st.divider()

        # --- 5. FINAL SAVE LOGIC ---
        st.markdown("<p style='color: white; font-size: 18px; font-weight: bold;'>4. Finalize & Save</p>", unsafe_allow_html=True)
        c1, c2 = st.columns([1, 4])
        if c1.button("Back", key="back_s6"): st.session_state.wizard_step = 5; st.rerun()
        if c2.button("Finish & Save Project", type="primary", use_container_width=True, key="finish_btn"):
            proj_type = st.session_state.get("proj_type", "Project")
            test_type = st.session_state.get("test_type", "Test")
            
            # --- NEW: GET TARGET VAL AND RUN MODE ---
            target_val = str(st.session_state.get("target_val", "0"))
            run_mode = st.session_state.get("run_mode", "Continuous")
            
            # --- NEW: DETERMINE UNIT (Hrs or Cycles) ---
            is_cycle = "Cycle" in test_type or "Intermittent" in test_type or "Cycle" in run_mode
            unit = "Cycles" if is_cycle else "Hrs"
            
            # --- NEW: CREATE THE COMBINED PROJECT NAME ---
            project_name = f"{proj_type} {test_type} {target_val} {unit}"
            
            # --- THE DATE (TIMESTAMP) ---
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            
            try:
                run_mode = st.session_state.get("run_mode", "Continuous")
                target_val = str(st.session_state.get("target_val", "0"))

                # --- CLEAN SAVE TO DATABASE ---
                # 6 values in exact order: ID, Type, Test Type, Run Mode, Target, Date

                tanks_str = "||".join(st.session_state.get("water_tanks", ["Water Tank 1"]))
                layout_json = None
                if "layout_df" in st.session_state and isinstance(st.session_state.layout_df, pd.DataFrame):
                    layout_json = st.session_state.layout_df.to_json()
                # Upsert with layout

                # --- NEW: Save hardware_list, all df_/ds_ DataFrames as JSON ---
                hardware_list = st.session_state.get("hardware_list", [])
                hardware_dfs = {}
                hardware_ds = {}
                for k in st.session_state.keys():
                    if k.startswith("df_") and isinstance(st.session_state[k], pd.DataFrame):
                        hardware_dfs[k] = st.session_state[k].to_json()
                    if k.startswith("ds_") and isinstance(st.session_state[k], list):
                        hardware_ds[k] = st.session_state[k]
                import json
                hardware_dfs_json = json.dumps(hardware_dfs)
                hardware_ds_json = json.dumps(hardware_ds)
                hardware_list_json = json.dumps(hardware_list)

                step6_watchdogs_json = st.session_state.get("watchdogs_df", pd.DataFrame(columns=["Data Entry Method", "Watchdog Type"])).to_json()
                step6_limits_json = st.session_state.get("limits_df", pd.DataFrame(columns=["Pump ID", "Max Stator Temp (°C)", "Max Current (A)"])).to_json()
                step6_extra_limits_json = st.session_state.get("extra_limits_df", pd.DataFrame(columns=["Formula Name", "Min Value", "Max Value", "Applies To"])).to_json()
                step6_event_log_json = json.dumps(st.session_state.get("event_log", []))
                step6_dashboard_tracker = st.session_state.get("dashboard_main_tracker", "Temperature")
                watchdog_sync_ts = st.session_state.get("watchdog_sync_ts", timestamp)
                step5_var_mapping_json = st.session_state.get("var_mapping_df", pd.DataFrame(columns=["Variable", "Mapped Sensor"])).to_json()
                step5_formulas_json = st.session_state.get("formulas_df", pd.DataFrame(columns=["Formula Name", "Target", "Equation"])).to_json()

                try:
                    c.execute("ALTER TABLE projects ADD COLUMN watchdog_sync_ts TEXT")
                except sqlite3.OperationalError:
                    pass

                c.execute("INSERT OR REPLACE INTO projects (project_id, type, test_type, run_mode, target_val, created_at, tanks, layout, hardware_list, hardware_dfs, hardware_ds, step6_watchdogs, step6_limits, step6_event_log, watchdog_sync_ts, step6_extra_limits, step6_dashboard_tracker, step5_var_mapping, step5_formulas) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (project_name, proj_type, test_type, run_mode, target_val, timestamp, tanks_str, layout_json, hardware_list_json, hardware_dfs_json, hardware_ds_json, step6_watchdogs_json, step6_limits_json, step6_event_log_json, watchdog_sync_ts, step6_extra_limits_json, step6_dashboard_tracker, step5_var_mapping_json, step5_formulas_json))

                # --- Delete old pump records for this project to prevent duplicates ---
                c.execute("DELETE FROM pumps WHERE project_id = ?", (project_name,))

                # Save Pumps Specs (Insulation only, no tank assignment, columns must match schema)
                for _, row in st.session_state.specs_df.dropna(subset=["Pump ID"]).iterrows():
                    p_id = row["Pump ID"]
                    c.execute("INSERT OR REPLACE INTO pumps (pump_id, project_id, `Pump Model`, `ISO No.`, HP, kW, `Voltage (V)`, `Amp Min`, `Amp Max`, Phase, Hertz, Insulation) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            p_id,
                            project_name,
                            row.get("Pump Model", ""),
                            row.get("ISO No.", ""),
                            str(row.get("HP", "")),
                            str(row.get("kW", "")),
                            row.get("Voltage (V)", ""),
                            str(row.get("Amp Min", "")),
                            str(row.get("Amp Max", "")),
                            str(row.get("Phase", "")),
                            str(row.get("Hertz", "")),
                            row.get("Insulation", "")
                        )
                    )
                
                conn.commit()
                queue_confirmation(f"Project '{project_name}' successfully saved.")
                
                # Cleanup and Go Home
                for k in ["specs_df", "wizard_step", "proj_type", "test_type", "layout_df", "watchdogs_df", "watchdog_matrix_df", "limits_df", "extra_limits_df", "event_log", "dashboard_main_tracker", "add_record_draft", "maintenance_prefill_pumps", "maintenance_source_record_id"]:
                    if k in st.session_state: del st.session_state[k]
                st.session_state.page = "home"
                st.rerun()

            except Exception as e:
                st.error(f"Database Error: {e}")
            finally:
                conn.close()

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