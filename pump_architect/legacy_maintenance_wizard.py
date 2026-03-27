import datetime
import json
from pump_architect.db.connection import get_connection

import pandas as pd
import streamlit as st


def render_add_maintenance_wizard(
    inject_css_fn,
    parse_ts_fn,
    get_maintenance_events_fn,
    add_event_log_entry_fn,
    persist_event_log_for_project_fn,
    queue_confirmation_fn,
):
    inject_css_fn()
    project_id = st.session_state.get("current_project", "")
    if not project_id:
        st.error("No active project selected. Open a project dashboard first.")
        if st.button("Back to Home", use_container_width=True):
            st.session_state.page = "home"
            st.rerun()
        return

    st.markdown("<div class='step-title'>Add New Maintenance</div>", unsafe_allow_html=True)
    st.markdown(f"<p style='color:white; font-size:16px;'>Project: {project_id}</p>", unsafe_allow_html=True)

    if st.button("Back to Dashboard", use_container_width=True):
        st.session_state.page = "dashboard"
        st.rerun()

    if "active_pumps_df" not in st.session_state or st.session_state.active_pumps_df.empty:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM pumps WHERE project_id = %s", (project_id,))
        rows = cur.fetchall()
        st.session_state.active_pumps_df = pd.DataFrame(rows, columns=[desc[0] for desc in cur.description])
        cur.close()
        conn.close()

    pumps_df = st.session_state.get("active_pumps_df", pd.DataFrame())
    pump_ids = []
    if not pumps_df.empty:
        for _, row in pumps_df.iterrows():
            pid = str(row.get("pump_id", row.get("Pump ID", ""))).strip()
            if pid:
                pump_ids.append(pid)
    pump_ids = sorted(list(set(pump_ids)))

    prefill_pumps = st.session_state.get("maintenance_prefill_pumps", [])
    prefill_record_id = st.session_state.get("maintenance_source_record_id", None)
    default_selection = [p for p in prefill_pumps if p in pump_ids]

    if "maintenance_event_ts" not in st.session_state:
        st.session_state.maintenance_event_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if "maintenance_action_taken" not in st.session_state:
        st.session_state.maintenance_action_taken = ""
    if "maintenance_notes" not in st.session_state:
        st.session_state.maintenance_notes = ""

    event_ts = st.text_input("Maintenance Timestamp (YYYY-MM-DD HH:MM:SS)", key="maintenance_event_ts")
    ts_ok = True
    try:
        _ = parse_ts_fn(event_ts)
    except Exception:
        ts_ok = False
        st.error("Invalid timestamp format. Use YYYY-MM-DD HH:MM:SS.")

    affected_pumps = st.multiselect(
        "Affected Pumps",
        options=pump_ids,
        default=default_selection,
        key="maintenance_pumps_select",
    )
    event_type = st.selectbox(
        "Event Type",
        options=["Inspection", "Corrective", "Preventive", "Calibration", "Other"],
        key="maintenance_event_type",
    )
    severity = st.selectbox(
        "Severity",
        options=["Low", "Medium", "High", "Critical"],
        key="maintenance_severity",
    )
    maintenance_status = st.selectbox(
        "Maintenance Status",
        options=["Open", "In Progress", "Closed"],
        index=0,
        key="maintenance_status",
    )
    action_taken = st.text_area("Action Taken", key="maintenance_action_taken", height=120)
    notes = st.text_area("Notes", key="maintenance_notes", height=120)

    can_save = ts_ok and len(affected_pumps) > 0
    if not affected_pumps:
        st.markdown("<p style='color:white;'>Select at least one pump to save maintenance.</p>", unsafe_allow_html=True)

    if st.button("Save Maintenance Event", use_container_width=True, type="primary", disabled=not can_save):
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO maintenance_events (
                    project_id, event_ts, affected_pumps_json, event_type, severity,
                    maintenance_status, action_taken, notes, source_record_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    project_id,
                    event_ts,
                    json.dumps(affected_pumps),
                    event_type,
                    severity,
                    maintenance_status,
                    action_taken,
                    notes,
                    prefill_record_id,
                ),
            )
            conn.commit()
            cur.close()
            conn.close()

            add_event_log_entry_fn(f"Maintenance logged ({event_type}, {severity}) for pump(s): {', '.join(affected_pumps)}.")
            persist_event_log_for_project_fn(project_id)

            st.session_state.maintenance_prefill_pumps = []
            st.session_state.maintenance_source_record_id = None
            st.session_state.pop("maintenance_event_ts", None)
            st.session_state.pop("maintenance_action_taken", None)
            st.session_state.pop("maintenance_notes", None)
            queue_confirmation_fn("Maintenance event saved.")
            st.session_state.page = "dashboard"
            st.rerun()
        except Exception as e:
            st.error(f"Could not save maintenance event: {e}")

    st.write("")
    st.markdown("<p class='col-header'>Recent Maintenance Events</p>", unsafe_allow_html=True)
    maint_df = get_maintenance_events_fn(project_id)
    if maint_df.empty:
        st.markdown("<p style='color:white;'>No maintenance events yet.</p>", unsafe_allow_html=True)
    else:
        preview_rows = []
        for _, row in maint_df.head(10).iterrows():
            try:
                pumps = ", ".join(json.loads(row.get("affected_pumps_json", "[]")))
            except Exception:
                pumps = "-"
            preview_rows.append({
                "When": row.get("event_ts", ""),
                "Pumps": pumps,
                "Type": row.get("event_type", ""),
                "Severity": row.get("severity", ""),
                "Status": row.get("maintenance_status", "Open"),
                "Action": row.get("action_taken", ""),
            })
        st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)

        st.write("")
        st.markdown("<p class='col-header'>Update Maintenance Status</p>", unsafe_allow_html=True)
        open_like_df = maint_df[maint_df["maintenance_status"].fillna("Open") != "Closed"].copy() if "maintenance_status" in maint_df.columns else maint_df.copy()
        if open_like_df.empty:
            st.markdown("<p style='color:white;'>No open maintenance events to update.</p>", unsafe_allow_html=True)
        else:
            update_options = []
            for _, row in open_like_df.iterrows():
                try:
                    pumps = ", ".join(json.loads(row.get("affected_pumps_json", "[]") or "[]"))
                except Exception:
                    pumps = "-"
                label = f"#{row.get('id')} | {row.get('event_ts')} | {row.get('event_type')} | {row.get('maintenance_status', 'Open')} | {pumps}"
                update_options.append((label, int(row.get("id"))))

            selected_label = st.selectbox("Select Maintenance Event", options=[x[0] for x in update_options], key="maintenance_update_select")
            new_status = st.selectbox("New Status", options=["Open", "In Progress", "Closed"], key="maintenance_update_status")
            if st.button("Apply Status Update", use_container_width=True, type="primary", key="maintenance_update_apply"):
                selected_id = None
                for label, eid in update_options:
                    if label == selected_label:
                        selected_id = eid
                        break
                if selected_id is not None:
                    conn = get_connection()
                    cur = conn.cursor()
                    cur.execute("UPDATE maintenance_events SET maintenance_status = %s WHERE id = %s", (new_status, selected_id))
                    conn.commit()
                    cur.close()
                    conn.close()
                    add_event_log_entry_fn(f"Maintenance event #{selected_id} status updated to {new_status}.")
                    persist_event_log_for_project_fn(project_id)
                    queue_confirmation_fn("Maintenance status updated.")
                    st.rerun()
