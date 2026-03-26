import datetime
import json
from pump_architect.db.connection import get_connection

import pandas as pd
import streamlit as st


def inject_industrial_css():
    st.markdown("""
        <style>
            /* Main Background */
            html, body, [data-testid="stAppViewContainer"], .stApp, .main {
                background-color: #121417 !important;
                color: #E0E0E0;
            }
            [data-testid="stMainBlockContainer"] {
                background-color: transparent !important;
            }
            [data-testid="stSidebar"] {
                background-color: #0F1115 !important;
            }
            [data-testid="stHeader"] { background: rgba(0,0,0,0); }

            /* Hero Section */
            .hero-bg {
                background: linear-gradient(rgba(0,0,0,0.7), rgba(0,0,0,0.7)),
                            url('https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?q=80&w=2070&auto=format&fit=crop');
                background-size: cover; background-position: center;
                padding: 60px; border-radius: 15px; text-align: center; margin-bottom: 30px; border: 1px solid #333;
            }

            /* Typography & Text Sizes */
            .step-title { color: #4DA3FF !important; font-size: 2.2rem !important; font-weight: bold !important; margin-bottom: 20px; }
            .col-header { color: #4DA3FF !important; font-size: 18px !important; font-weight: bold; border-bottom: 2px solid #444; padding-bottom: 10px; text-transform: uppercase; }
            .white-text { color: white !important; font-size: 18px !important; font-weight: 500; margin-top: 8px; }

            /* Title treatment: blue */
            .header-title, .table-title, .panel-title, h1, h2, h3, h4, h5, h6 {
                color: #4DA3FF !important;
            }

            /* Body text treatment: white */
            p, li, span, div[data-testid="stMarkdownContainer"] p {
                color: #FFFFFF;
            }

            /* --- INPUT LABELS (Pump Type, Test Type, etc.) --- */
            label p, .stRadio label p, .stTextInput label p, .stNumberInput label p, .stSelectbox label p {
                color: white !important;
                font-size: 18px !important;
                font-weight: 600 !important;
            }
            /* Radio Button Options Text */
            div[role="radiogroup"] label div {
                color: #E0E0E0 !important;
                font-size: 16px !important;
            }

            /* Status Pills */
            .status-pill { padding: 8px 0px; border-radius: 5px; font-size: 16px; font-weight: bold; text-align: center; color: white; width: 100%; display: inline-block; background-color: #0d6efd; }

            /* --- BUTTONS --- */
            div.stButton > button {
                background-color: #E0E0E0 !important;
                color: black !important;
                border: 1px solid #ccc !important;
                border-radius: 5px !important;
                font-weight: bold !important;
                font-size: 16px !important;
                height: 45px !important;
            }

            div.stButton > button * {
                color: #000000 !important;
                fill: #000000 !important;
            }

            /* PRIMARY BUTTON (Finish & Save) */
            div.stButton > button[kind="primary"] {
                background-color: #0d6efd !important;
                color: white !important;
                border: none !important;
            }

            div.stButton > button[kind="primary"] * {
                color: #FFFFFF !important;
                fill: #FFFFFF !important;
            }

            button[aria-label^="DANGER "] {
                background: linear-gradient(180deg, #ff7f7f 0%, #dc4c4c 100%) !important;
                color: #FFFFFF !important;
                border: 1px solid #b53737 !important;
            }

            button[aria-label^="DANGER "] * {
                color: #FFFFFF !important;
                fill: #FFFFFF !important;
            }

            /* --- INDUSTRIAL UI FIXES --- */
            /* Table/Input Data Editor Sizes */
            div[data-testid="stDataEditor"] { background-color: #1C1F24 !important; border: 1px solid #444 !important; font-size: 16px !important; }
            div[data-testid="stTextInput"] input, div[data-testid="stNumberInput"] input { background-color: #1C1F24 !important; color: white !important; border: 1px solid #444 !important; font-size: 16px !important; }

            /* --- DROPDOWN POPUP MENU (selectbox / multiselect) --- */
            [data-baseweb="popover"] > div,
            [data-baseweb="menu"] {
                background-color: #1C1F24 !important;
                border: 1px solid #444 !important;
                border-radius: 8px !important;
            }
            [data-baseweb="menu"] [role="option"],
            [role="listbox"] [role="option"] {
                background-color: #1C1F24 !important;
                color: #E0E0E0 !important;
                font-size: 15px !important;
            }
            [data-baseweb="menu"] [role="option"]:hover,
            [data-baseweb="menu"] [aria-selected="true"],
            [role="listbox"] [role="option"][aria-selected="true"] {
                background-color: #1E3A5F !important;
                color: #4DA3FF !important;
            }

            /* Alerts: replace yellow/red low-contrast with dark panel + white text */
            div[data-testid="stAlert"] {
                background-color: #1E293B !important;
                border: 1px solid #334155 !important;
                color: #FFFFFF !important;
            }
            div[data-testid="stAlert"] p,
            div[data-testid="stAlert"] span,
            div[data-testid="stAlert"] div {
                color: #FFFFFF !important;
            }
        </style>
    """, unsafe_allow_html=True)


def queue_confirmation(message):
    st.session_state["_queued_confirmation"] = message


def render_confirmation_banner():
    message = st.session_state.pop("_queued_confirmation", None)
    if message:
        st.markdown(
            (
                "<div style='background:#1E293B; border:1px solid #334155; color:#FFFFFF; "
                "padding:10px 12px; border-radius:6px; margin:10px 0; font-size:15px; font-weight:600;'>"
                f"{message}</div>"
            ),
            unsafe_allow_html=True,
        )


def persist_event_log_for_project(db_file, project_id):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE projects SET step6_event_log = ? WHERE project_id = ?",
            (json.dumps(st.session_state.get("event_log", [])), project_id),
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        pass


def add_event_log_entry(text):
    if "event_log" not in st.session_state:
        st.session_state.event_log = []
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.event_log.insert(0, f"[{ts}] {text}")


    if not stable_pumps:
        return []
    maint_df = get_maintenance_events_fn(project_id)
    if maint_df.empty:
        return []

    to_close_ids = []
    for _, row in maint_df.iterrows():
        m_status = str(row.get("maintenance_status", "Open") or "Open").strip()
        if m_status == "Closed":
            continue
        try:
            affected = [str(x).strip() for x in json.loads(row.get("affected_pumps_json", "[]") or "[]")]
        except Exception:
            affected = []
        if any(pid in stable_pumps for pid in affected):
            to_close_ids.append(int(row.get("id")))

    if not to_close_ids:
        return []

    conn = get_connection()
    cur = conn.cursor()
    for event_id in to_close_ids:
        cur.execute("UPDATE maintenance_events SET maintenance_status = ? WHERE id = ?", ("Closed", event_id))
    conn.commit()
    cur.close()
    conn.close()
    return to_close_ids


def build_dashboard_report_csv(project_id, get_latest_record_fn, get_maintenance_events_fn):
    latest_record = get_latest_record_fn(project_id)
    status_grid = latest_record.get("status_grid", {}) if latest_record else {}
    readings = latest_record.get("pump_readings", {}) if latest_record else {}
    alarms = latest_record.get("alarms", []) if latest_record else []

    alarm_lookup = {}
    if isinstance(alarms, list):
        for item in alarms:
            if isinstance(item, dict):
                pid = str(item.get("pump_id", "")).strip()
                if pid:
                    alarm_lookup[pid] = " | ".join(item.get("alarms", []))

    maint_df = get_maintenance_events_fn(project_id)
    open_maint_by_pump = {}
    if isinstance(maint_df, pd.DataFrame) and not maint_df.empty:
        for _, m_row in maint_df.iterrows():
            m_status = str(m_row.get("maintenance_status", "Open") or "Open").strip()
            if m_status == "Closed":
                continue
            try:
                affected = json.loads(m_row.get("affected_pumps_json", "[]") or "[]")
            except Exception:
                affected = []
            for pid in affected:
                pid = str(pid).strip()
                if pid and pid not in open_maint_by_pump:
                    open_maint_by_pump[pid] = f"{m_row.get('event_type', '')} ({m_row.get('severity', '')}) [{m_status}]"

    rows = []
    if isinstance(status_grid, dict) and status_grid:
        for pid, info in status_grid.items():
            reading = readings.get(pid, {}) if isinstance(readings, dict) else {}
            rows.append({
                "Project": project_id,
                "Record Timestamp": latest_record.get("record_ts", "") if latest_record else "",
                "Pump ID": pid,
                "Status": info.get("status", ""),
                "Accumulated Hours": info.get("acc_hours", ""),
                "Temp (C)": reading.get("temp", ""),
                "Current (A)": reading.get("amps", ""),
                "Alarms": alarm_lookup.get(pid, ""),
                "Open Maintenance": open_maint_by_pump.get(pid, ""),
            })
    else:
        rows.append({
            "Project": project_id,
            "Record Timestamp": "",
            "Pump ID": "",
            "Status": "",
            "Accumulated Hours": "",
            "Temp (C)": "",
            "Current (A)": "",
            "Alarms": "",
            "Open Maintenance": "",
        })

    return pd.DataFrame(rows).to_csv(index=False)
