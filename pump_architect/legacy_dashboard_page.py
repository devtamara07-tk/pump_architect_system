import datetime
import json
import sqlite3

import pandas as pd
import streamlit as st


def render_dashboard_page(
    db_file,
    get_latest_record,
    get_project_records,
    get_maintenance_events,
    build_dashboard_report_csv,
    add_event_log_entry,
    persist_event_log_for_project,
    clear_project_records,
    clear_project_maintenance_events,
    queue_confirmation,
):
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
        .status-light-alarm { height: 20px; width: 20px; background-color: #E67E22; border-radius: 50%; display: inline-block; box-shadow: 0 0 10px #E67E22; }
        .header-title { font-size: 22px; font-weight: bold; letter-spacing: 1px; color: #3498DB; text-transform: uppercase; margin-bottom: 5px; }
        .event-log-text { font-size: 13px; color: #AAA; font-family: monospace; margin-bottom: 4px; }
        .event-alert { color: #E74C3C; font-weight: bold; }

        div[data-testid="stHorizontalBlock"]:has(> div:nth-child(3) button) > div:nth-child(1) button {
            background: linear-gradient(180deg, #0d6efd 0%, #0b5ed7 100%) !important;
            color: #FFFFFF !important;
            border: none !important;
        }
        div[data-testid="stHorizontalBlock"]:has(> div:nth-child(3) button) > div:nth-child(1) button * {
            color: #FFFFFF !important;
            fill: #FFFFFF !important;
        }
        div[data-testid="stHorizontalBlock"]:has(> div:nth-child(3) button) > div:nth-child(2) button {
            background: linear-gradient(180deg, #ffd978 0%, #f3b63f 100%) !important;
            color: #201300 !important;
            border: 1px solid #d19a2d !important;
        }
        div[data-testid="stHorizontalBlock"]:has(> div:nth-child(3) button) > div:nth-child(2) button * {
            color: #201300 !important;
            fill: #201300 !important;
        }
        div[data-testid="stHorizontalBlock"]:has(> div:nth-child(3) button) > div:nth-child(3) button {
            background: linear-gradient(180deg, #f4f7fb 0%, #dce4ef 100%) !important;
            color: #09111a !important;
            border: 1px solid #c4d1de !important;
        }
        div[data-testid="stHorizontalBlock"]:has(> div:nth-child(3) button) > div:nth-child(3) button * {
            color: #09111a !important;
            fill: #09111a !important;
        }

        button[aria-label="DANGER Confirm Delete Run Test Inputs"],
        button[aria-label="DANGER Confirm Delete Maintenance Inputs"] {
            background: linear-gradient(180deg, #ff7f7f 0%, #dc4c4c 100%) !important;
            color: #FFFFFF !important;
            border: 1px solid #b53737 !important;
        }
        button[aria-label="DANGER Confirm Delete Run Test Inputs"] *,
        button[aria-label="DANGER Confirm Delete Maintenance Inputs"] * {
            color: #FFFFFF !important;
            fill: #FFFFFF !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # 2. Fetch REAL Database Info for this Project
    project_name = st.session_state.get('current_project', 'UNKNOWN PROJECT')

    conn = sqlite3.connect(db_file)
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
    elapsed_runtime_value = 0.0
    running_pump_count = 0
    displayed_pump_count = 0
    if isinstance(latest_status_grid, dict) and latest_status_grid:
        try:
            acc_values = [float(item.get("acc_hours", 0.0) or 0.0) for item in latest_status_grid.values()]
            total_acc_value = sum(acc_values)
            elapsed_runtime_value = max(acc_values) if acc_values else 0.0
            displayed_pump_count = len(acc_values)
            running_pump_count = sum(1 for item in latest_status_grid.values() if str(item.get("status", "")).upper() == "RUNNING")
        except Exception:
            total_acc_value = 0.0
            elapsed_runtime_value = 0.0
            running_pump_count = 0
            displayed_pump_count = 0
    try:
        target_val_num = float(target_val)
    except Exception:
        target_val_num = 0.0
    progress_pct = 0.0 if target_val_num <= 0 else max(0.0, min(100.0, (elapsed_runtime_value / target_val_num) * 100.0))

    if is_cycle_test:
        bar_title = "TOTAL MISSION CYCLES"
        bar_value = f"{elapsed_runtime_value:.1f} / {target_val} cycles"
        secondary_value = f"Aggregate load: {total_acc_value:.1f} pump-cycles across {displayed_pump_count} pump(s)"
        bar_color = "#3498DB" 
    else:
        bar_title = "TOTAL MISSION ELAPSED TIME"
        bar_value = f"{elapsed_runtime_value:.1f} / {target_val} hrs"
        secondary_value = f"Aggregate load: {total_acc_value:.1f} pump-hours | Running now: {running_pump_count} pump(s)"
        bar_color = "#EEDD82" 

    st.markdown(f"""
        <div class="panel" style="margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between;"><span class="panel-title">{bar_title}</span> <span style="font-weight:bold; color:white; font-size:16px;">{bar_value}</span></div>
            <div style="background: #333; height: 12px; border-radius: 6px; margin-top: 8px;"><div style="background: {bar_color}; width: {progress_pct:.1f}%; height: 100%; border-radius: 6px;"></div></div>
            <div style="margin-top:8px; font-size:12px; color:#AAB2BF;">{secondary_value}</div>
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
        action_col1, action_col2, action_col3 = st.columns(3)
        with action_col1:
            if st.button("Add New Record", use_container_width=True, type="primary", key="btn_add_record"):
                st.session_state.page = "add_record"
                st.session_state.add_record_draft = {}
                st.rerun()

        with action_col2:
            if st.button("Add New Maintenance", use_container_width=True, key="btn_add_maint"):
                st.session_state.maintenance_prefill_pumps = []
                st.session_state.maintenance_source_record_id = None
                st.session_state.page = "add_maintenance"
                st.rerun()

        report_csv = build_dashboard_report_csv(project_name)
        report_name_ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        with action_col3:
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
            st.warning("Delete run test inputs is permanent. Project setup remains intact.")
            rec_cancel_col, rec_confirm_col, _ = st.columns([1.3, 1.7, 3.0])
            with rec_cancel_col:
                if st.button("Cancel Delete Run Test Inputs", use_container_width=True, key="btn_clear_records_cancel"):
                    st.session_state.pop(debug_confirm_key, None)
                    st.rerun()
            with rec_confirm_col:
                if st.button("DANGER Confirm Delete Run Test Inputs", use_container_width=True, type="primary", key="btn_clear_records_confirm"):
                    deleted_rows = clear_project_records(project_name)
                    st.session_state.add_record_draft = {}
                    st.session_state.maintenance_prefill_pumps = []
                    st.session_state.maintenance_source_record_id = None
                    st.session_state.pop(debug_confirm_key, None)
                    queue_confirmation(
                        f"Deleted {deleted_rows} saved run test input record(s). "
                        "Tank activation state has also been reset for this project."
                    )
                    st.rerun()
        else:
            _danger_col, _ = st.columns([2, 4])
            with _danger_col:
                if st.button("DANGER Begin Delete Run Test Inputs", use_container_width=True, key="btn_clear_records"):
                    st.session_state[debug_confirm_key] = True
                    st.rerun()

        st.markdown(
            f"<p style='color:white; font-size:13px; margin-top:8px;'>Saved maintenance inputs: <b>{maintenance_count}</b></p>",
            unsafe_allow_html=True,
        )

        maint_debug_confirm_key = f"clear_maintenance_confirm_{project_name}"
        if st.session_state.get(maint_debug_confirm_key, False):
            st.warning("Delete maintenance inputs is permanent. Project setup remains intact.")
            maint_cancel_col, maint_confirm_col, _ = st.columns([1.3, 1.7, 3.0])
            with maint_cancel_col:
                if st.button("Cancel Delete Maintenance Inputs", use_container_width=True, key="btn_clear_maintenance_cancel"):
                    st.session_state.pop(maint_debug_confirm_key, None)
                    st.rerun()
            with maint_confirm_col:
                if st.button("DANGER Confirm Delete Maintenance Inputs", use_container_width=True, type="primary", key="btn_clear_maintenance_confirm"):
                    deleted_rows = clear_project_maintenance_events(project_name)
                    st.session_state.maintenance_prefill_pumps = []
                    st.session_state.maintenance_source_record_id = None
                    st.session_state.pop(maint_debug_confirm_key, None)
                    queue_confirmation(f"Deleted {deleted_rows} saved maintenance input record(s). Project setup remains intact.")
                    st.rerun()
        else:
            _maint_danger_col, _ = st.columns([2, 4])
            with _maint_danger_col:
                if st.button("DANGER Begin Delete Maintenance Inputs", use_container_width=True, key="btn_clear_maintenance"):
                    st.session_state[maint_debug_confirm_key] = True
                    st.rerun()
    
        st.write("")
        _exit_col, _ = st.columns([1.2, 4.8])
        with _exit_col:
            if st.button("Exit Dashboard", use_container_width=True):
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

            # For staggered multi-tank recording, the latest global record can be from a different
            # tank and may not contain fresh readings for all pumps. Build a per-pump fallback from
            # most-recent records so Tank 2 cards still show their latest known values.
            latest_readings_by_pump = dict(latest_readings) if isinstance(latest_readings, dict) else {}
            try:
                records_df = get_project_records(project_name)
                if isinstance(records_df, pd.DataFrame) and not records_df.empty and "pump_readings_json" in records_df.columns:
                    for _, rec_row in records_df.iterrows():
                        try:
                            readings_payload = json.loads(rec_row.get("pump_readings_json") or "{}")
                        except Exception:
                            readings_payload = {}
                        if not isinstance(readings_payload, dict):
                            continue
                        for pid_key, payload in readings_payload.items():
                            pid_key = str(pid_key).strip()
                            if pid_key and pid_key not in latest_readings_by_pump:
                                latest_readings_by_pump[pid_key] = payload
            except Exception:
                pass

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
                        record_reading = latest_readings_by_pump.get(p_id, {}) if isinstance(latest_readings_by_pump, dict) else {}
                        record_status = str(record_grid.get("status", "STANDBY")).upper()
                        record_alarm = p_id in alarm_pump_ids
                        acc_hours_raw = float(record_grid.get('acc_hours', 0.0) or 0.0)
                        acc_hours_display = int(round(acc_hours_raw))
                        try:
                            target_display = int(round(float(target_val)))
                        except Exception:
                            target_display = target_val
                        running_time_value = f"{acc_hours_display} / {target_display} {running_time_unit}"

                        if record_status == "RUNNING":
                            status_color = "value-green"
                            light_class = "status-light-run"
                            svg_color = "#2ECC71"
                            op_state_text = "RUNNING"
                            op_state_color = "#2ECC71"
                            op_state_bg = "rgba(46, 204, 113, 0.18)"
                            op_state_border = "#2ECC71"
                        elif record_status == "PAUSED":
                            status_color = "value-grey"
                            light_class = "status-light-stop"
                            svg_color = "#EEDD82"
                            op_state_text = "PAUSED"
                            op_state_color = "#EEDD82"
                            op_state_bg = "rgba(238, 221, 130, 0.18)"
                            op_state_border = "#EEDD82"
                        elif record_status == "FAILED":
                            status_color = "value-grey"
                            light_class = "status-light-stop"
                            svg_color = "#E74C3C"
                            op_state_text = "FAILED"
                            op_state_color = "#E74C3C"
                            op_state_bg = "rgba(231, 76, 60, 0.18)"
                            op_state_border = "#E74C3C"
                        else:
                            status_color = "value-grey"
                            light_class = "status-light-stop"
                            svg_color = "#777"
                            op_state_text = "STANDBY"
                            op_state_color = "#9CA3AF"
                            op_state_bg = "rgba(156, 163, 175, 0.16)"
                            op_state_border = "#6B7280"

                        alarm_state_text = "NO ALARM"
                        alarm_state_color = "#2ECC71"
                        alarm_state_bg = "rgba(46, 204, 113, 0.16)"
                        alarm_state_border = "#2ECC71"

                        if record_alarm:
                            light_class = "status-light-alarm"
                            svg_color = "#E67E22"
                            alarm_state_text = "ALARM"
                            alarm_state_color = "#E67E22"
                            alarm_state_bg = "rgba(230, 126, 34, 0.18)"
                            alarm_state_border = "#E67E22"

                        op_state_badge_html = (
                            f'<span style="display:inline-block; padding:2px 7px; border-radius:999px; '
                            f'border:1px solid {op_state_border}; color:{op_state_color}; '
                            f'background:{op_state_bg}; font-size:10px; font-weight:700; letter-spacing:0.04em; '
                            f'text-transform:uppercase; margin-top:4px;">{op_state_text}</span>'
                        )
                        alarm_state_badge_html = (
                            f'<span style="display:inline-block; padding:2px 7px; border-radius:999px; '
                            f'border:1px solid {alarm_state_border}; color:{alarm_state_color}; '
                            f'background:{alarm_state_bg}; font-size:10px; font-weight:700; letter-spacing:0.04em; '
                            f'text-transform:uppercase; margin-top:4px;">{alarm_state_text}</span>'
                        )

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
                                '<div style="font-size: 9px; color: #8D96A7; margin-top: 6px; letter-spacing: 0.05em; text-transform: uppercase;">Operational</div>'
                                f'{op_state_badge_html}'
                                '<div style="font-size: 9px; color: #8D96A7; margin-top: 6px; letter-spacing: 0.05em; text-transform: uppercase;">Alarm</div>'
                                f'{alarm_state_badge_html}'
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
