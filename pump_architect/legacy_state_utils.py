import json
import sqlite3

import pandas as pd
import streamlit as st

from pump_architect.db.connection import connect


def build_phase4_hardware_plan(pump_ids, status_grid):
    temp_units = []
    clamp_units = []

    for hw_name in st.session_state.get("hardware_list", []):
        df_key = f"df_{hw_name}"
        df = st.session_state.get(df_key)
        if not isinstance(df, pd.DataFrame) or df.empty:
            continue

        if "HIOKI Temp" in hw_name:
            rows = []
            for _, row in df.iterrows():
                pump_id = str(row.get("Assigned To", "None (Unused)")).strip()
                if pump_id not in pump_ids:
                    continue
                status = str(status_grid.get(pump_id, {}).get("status", "STANDBY")).upper()
                if status == "FAILED":
                    continue
                rows.append({
                    "CH": str(row.get("CH", "")).strip(),
                    "Sensor Name": str(row.get("Sensor Name", "")).strip(),
                    "Pump ID": pump_id,
                    "Status": status,
                    "Measurement Type": str(row.get("Measurement Type", "Exact")).strip() or "Exact",
                })
            if rows:
                temp_units.append({
                    "hardware": hw_name,
                    "data_source": st.session_state.get(f"ds_{hw_name}", ["Manual Input"]),
                    "rows": rows,
                })

        elif "HIOKI Clamp" in hw_name:
            rows = []
            for _, row in df.iterrows():
                pump_id = str(row.get("Pump ID", "")).strip()
                if pump_id not in pump_ids:
                    continue
                if str(row.get("Read Status", "On (Yes Read)")).strip() != "On (Yes Read)":
                    continue
                status = str(status_grid.get(pump_id, {}).get("status", "STANDBY")).upper()
                if status == "FAILED":
                    continue
                rows.append({
                    "Pump ID": pump_id,
                    "Sensor Name": str(row.get("Sensor Name", "Clamp Meter")).strip() or "Clamp Meter",
                    "Status": status,
                })
            if rows:
                clamp_units.append({
                    "hardware": hw_name,
                    "data_source": st.session_state.get(f"ds_{hw_name}", ["Manual Input"]),
                    "rows": rows,
                })

    return temp_units, clamp_units


def restore_project_formula_state(db_file, project_id):
    default_var_mapping = pd.DataFrame(columns=["Variable", "Mapped Sensor"])
    default_formulas = pd.DataFrame(columns=["Formula Name", "Target", "Equation"])

    conn = connect(db_file)
    proj_row = conn.execute(
        "SELECT step5_var_mapping, step5_formulas FROM projects WHERE project_id = ?",
        (project_id,),
    ).fetchone()
    conn.close()

    if not proj_row:
        st.session_state.var_mapping_df = default_var_mapping
        st.session_state.formulas_df = default_formulas
        return

    try:
        st.session_state.var_mapping_df = pd.read_json(proj_row[0]) if proj_row[0] else default_var_mapping
    except Exception:
        st.session_state.var_mapping_df = default_var_mapping

    try:
        st.session_state.formulas_df = pd.read_json(proj_row[1]) if proj_row[1] else default_formulas
    except Exception:
        st.session_state.formulas_df = default_formulas


def restore_project_hardware_state(db_file, project_id):
    conn = connect(db_file)
    proj_row = conn.execute(
        "SELECT hardware_list, hardware_dfs, hardware_ds FROM projects WHERE project_id = ?",
        (project_id,),
    ).fetchone()
    conn.close()

    if not proj_row:
        st.session_state.hardware_list = []
        return

    try:
        st.session_state.hardware_list = json.loads(proj_row[0]) if proj_row[0] else []
    except Exception:
        st.session_state.hardware_list = []

    try:
        dfs = json.loads(proj_row[1]) if proj_row[1] else {}
        for key, value in dfs.items():
            st.session_state[key] = pd.read_json(value)
    except Exception:
        pass

    try:
        dss = json.loads(proj_row[2]) if proj_row[2] else {}
        for key, value in dss.items():
            st.session_state[key] = value
    except Exception:
        pass
