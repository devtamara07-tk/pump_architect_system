from pump_architect.db.connection import get_connection

import pandas as pd
import streamlit as st


def initialize_add_record_draft():
    if "add_record_draft" not in st.session_state:
        st.session_state.add_record_draft = {}
    draft = st.session_state.add_record_draft

    if "record_phase" not in draft:
        draft["record_phase"] = "Routine/Daily Record"
    if "record_ts" not in draft:
        draft["record_ts"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    if "phase1_confirmed" not in draft:
        draft["phase1_confirmed"] = False
    if "phase2_confirmed" not in draft:
        draft["phase2_confirmed"] = False
    if "phase3_confirmed" not in draft:
        draft["phase3_confirmed"] = False
    if "phase4_confirmed" not in draft:
        draft["phase4_confirmed"] = False
    if "save_completed" not in draft:
        draft["save_completed"] = False

    if "activating_tanks" not in draft:
        draft["activating_tanks"] = []
    if "active_tanks" not in draft:
        draft["active_tanks"] = []

    return draft


def ensure_active_pumps_df(db_file, project_id):
    if "active_pumps_df" not in st.session_state or st.session_state.active_pumps_df.empty:
        conn = get_connection()
        st.session_state.active_pumps_df = pd.read_sql_query("SELECT * FROM pumps WHERE project_id = %s", conn, params=(project_id,))
        # conn.close()  # Removed: do not close cached connection
    return st.session_state.get("active_pumps_df", pd.DataFrame())


def ensure_hardware_and_formula_state(project_id, restore_project_hardware_state_fn, restore_project_formula_state_fn):
    if "hardware_list" not in st.session_state:
        st.session_state.hardware_list = []

    hardware_df_keys = [key for key in st.session_state.keys() if key.startswith("df_HIOKI")]
    if not st.session_state.hardware_list or not hardware_df_keys:
        restore_project_hardware_state_fn(project_id)

    if "var_mapping_df" not in st.session_state or "formulas_df" not in st.session_state:
        restore_project_formula_state_fn(project_id)


def build_pump_ids(pumps_df):
    pump_ids = []
    for _, row in pumps_df.iterrows():
        pid = str(row.get("pump_id", row.get("Pump ID", ""))).strip()
        if pid:
            pump_ids.append(pid)
    return pump_ids


def load_layout_and_pump_tank_lookup(db_file, project_id):
    if "layout_df" not in st.session_state or st.session_state.layout_df.empty:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT layout, tanks FROM projects WHERE project_id = %s", (project_id,))
        row = cur.fetchone()
        cur.close()
        # conn.close()  # Removed: do not close cached connection
        if row and row[0]:
            try:
                st.session_state.layout_df = pd.read_json(row[0])
            except Exception:
                st.session_state.layout_df = pd.DataFrame()
        if row and row[1]:
            st.session_state.water_tanks = row[1].split("||")

    layout_df = st.session_state.get("layout_df", pd.DataFrame())
    pump_tank_lookup = {}
    if isinstance(layout_df, pd.DataFrame) and not layout_df.empty and "Pump ID" in layout_df.columns and "Assigned Tank" in layout_df.columns:
        for _, lr in layout_df.iterrows():
            pump_tank_lookup[str(lr.get("Pump ID", ""))] = str(lr.get("Assigned Tank", ""))

    return pump_tank_lookup
