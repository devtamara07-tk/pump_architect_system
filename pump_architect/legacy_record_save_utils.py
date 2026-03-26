import json
from pump_architect.db.connection import get_connection

import streamlit as st


def save_project_record(
    db_file,
    project_id,
    draft,
    all_alarms,
    alarm_ack,
    active_tanks=None,
):
    conn = get_connection()
    c = conn.cursor()
    if draft["record_phase"] == "Baseline Calibration (Cold State)":
        c.execute(
            "DELETE FROM project_records WHERE project_id = ? AND record_phase = ?",
            (project_id, "Baseline Calibration (Cold State)"),
        )

    active_tanks_str = "||".join(active_tanks) if active_tanks else "ALL"
    c.execute(
        """
        INSERT INTO project_records (
            project_id, record_phase, record_ts, method, ambient_temp,
            tank_temps_json, status_grid_json, pump_readings_json, alarms_json,
            ack_alarm, active_tanks
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            active_tanks_str,
        ),
    )
    saved_record_id = c.lastrowid
    conn.commit()
    cur.close()
    conn.close()
    return saved_record_id


def compute_stable_running_pumps(draft, all_alarms):
    alarm_pump_ids = set()
    for alarm_item in all_alarms:
        pid = str(alarm_item.get("pump_id", "")).strip()
        if pid:
            alarm_pump_ids.add(pid)

    stable_running_pumps = []
    for pid, grid in (draft.get("status_grid", {}) or {}).items():
        if str(grid.get("status", "")).upper() == "RUNNING" and pid not in alarm_pump_ids:
            stable_running_pumps.append(str(pid))

    return stable_running_pumps


def finalize_record_save(
    draft,
    review_rows,
    all_alarms,
    saved_record_id,
):
    draft["save_completed"] = True
    draft["saved_record_id"] = saved_record_id
    draft["review_rows"] = review_rows
    draft["alarms"] = all_alarms


def render_post_save_navigation(draft):
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
