import datetime
import json

import pandas as pd
import streamlit as st

from pump_architect import legacy_add_record_setup
from pump_architect import legacy_db_utils
from pump_architect import legacy_phase2_utils
from pump_architect import legacy_phase4_utils
from pump_architect import legacy_phase56_utils
from pump_architect import legacy_record_phases
from pump_architect import legacy_record_save_utils
from pump_architect import legacy_state_utils
from pump_architect import legacy_ui_event_utils
from pump_architect.legacy_formula_utils import (
    aggregate_temperature_for_pump,
    build_formula_variables_for_pump,
    evaluate_formula_for_pump,
    get_formula_target_specificity,
    parse_ts,
    safe_float,
)


def render_add_record_wizard():
    legacy_ui_event_utils.inject_industrial_css()
    project_id = st.session_state.get("current_project", "")
    if not project_id:
        st.error("No active project selected. Open a project dashboard first.")
        if st.button("Back to Home", use_container_width=True):
            st.session_state.page = "home"
            st.rerun()
        return

    st.markdown("<div class='step-title'>Add New Record Wizard</div>", unsafe_allow_html=True)
    st.markdown(f"<p style='color:white; font-size:16px;'>Project: {project_id}</p>", unsafe_allow_html=True)

    back_col, _ = st.columns([1.2, 5.8])
    with back_col:
        if st.button("Back to Dashboard", use_container_width=True):
            st.session_state.page = "dashboard"
            st.rerun()

    draft = legacy_add_record_setup.initialize_add_record_draft()

    pumps_df = legacy_add_record_setup.ensure_active_pumps_df(db_file, project_id)
    legacy_add_record_setup.ensure_hardware_and_formula_state(
        project_id,
        lambda pid: legacy_state_utils.restore_project_hardware_state(db_file, pid),
        lambda pid: legacy_state_utils.restore_project_formula_state(db_file, pid),
    )

    if pumps_df.empty:
        st.warning("No pumps found for this project.")
        return

    pump_ids = legacy_add_record_setup.build_pump_ids(pumps_df)
    pump_tank_lookup = legacy_add_record_setup.load_layout_and_pump_tank_lookup(db_file, project_id)
    water_tanks = st.session_state.get("water_tanks", [])

    # ── Phase 0: Select Active Tanks ─────────────────────────────────────────────
    st.markdown("<p class='col-header'>Phase 0: Select Active Tanks</p>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#9CA3AF; font-size:13px;'>"
        "Choose which tank(s) are included in this record. Only selected active tanks "
        "will appear in Phase 3, Phase 4, and the final review."
        "</p>",
        unsafe_allow_html=True,
    )

    tank_start_dates = legacy_db_utils.get_tank_start_dates(db_file, project_id)
    established_active = [t for t in water_tanks if tank_start_dates.get(t)]
    pending_activation = [
        t for t in draft.get("activating_tanks", []) if t in water_tanks and not tank_start_dates.get(t)
    ]
    not_yet_started = [
        t for t in water_tanks if not tank_start_dates.get(t) and t not in pending_activation
    ]

    included_established = []

    for tank in established_active:
        include_key = f"p0_include_{tank.replace(' ', '_')}"
        if include_key not in st.session_state:
            st.session_state[include_key] = True
        include_for_record = bool(st.session_state.get(include_key, True))
        card_bg = "#0d1f0d" if include_for_record else "#1a1f26"
        card_border = "#2d4a1e" if include_for_record else "#39424e"
        card_text = "#22C55E" if include_for_record else "#9CA3AF"
        status_badge = "Included in this record" if include_for_record else "Skipped for this record"
        status_badge_color = "#22C55E" if include_for_record else "#F59E0B"
        card_col, control_col = st.columns([5.1, 1.4])
        with card_col:
            st.markdown(
                f"<div style='padding:10px 12px; border-radius:6px; background:{card_bg}; "
                f"border:1px solid {card_border}; color:{card_text}; font-weight:600; margin-bottom:6px;'>"
                f"✔ {tank} &nbsp;<span style='color:#9CA3AF; font-weight:400; font-size:13px;'>"
                f"Started on {tank_start_dates[tank]}</span>"
                f"<span style='float:right; color:{status_badge_color}; font-size:12px; font-weight:700;'>"
                f"{status_badge}</span></div>",
                unsafe_allow_html=True,
            )
        with control_col:
            include_for_record = st.checkbox(
                "Include",
                key=include_key,
                label_visibility="visible",
            )
        if include_for_record:
            included_established.append(tank)

    for tank in pending_activation:
        st.markdown(
            f"<div style='padding:8px 12px; border-radius:6px; background:#1c1a0d; "
            f"border:1px solid #4a3d00; color:#F59E0B; font-weight:600; margin-bottom:6px;'>"
            f"⚡ {tank} &nbsp;<span style='color:#9CA3AF; font-weight:400; font-size:13px;'>"
            f"Will be activated with this record — pumps start in STANDBY</span></div>",
            unsafe_allow_html=True,
        )
        _undo_col, _ = st.columns([1.0, 5.0])
        with _undo_col:
            if st.button(f"Undo Activate {tank}", key=f"p0_undo_{tank.replace(' ', '_')}"):
                draft["activating_tanks"] = [x for x in draft["activating_tanks"] if x != tank]
                st.rerun()

    for tank in not_yet_started:
        st.markdown(
            f"<div style='padding:8px 12px; border-radius:6px; background:#111418; "
            f"border:1px solid #333; color:#9CA3AF; font-weight:600; margin-bottom:6px;'>"
            f"○ {tank} &nbsp;<span style='color:#6B7280; font-weight:400; font-size:13px;'>"
            f"Not yet started</span></div>",
            unsafe_allow_html=True,
        )
        _act_col, _ = st.columns([1.0, 5.0])
        with _act_col:
            if st.button(f"Activate {tank}", key=f"p0_activate_{tank.replace(' ', '_')}", type="primary"):
                if tank not in draft["activating_tanks"]:
                    draft["activating_tanks"].append(tank)
                st.rerun()

    active_tanks_for_record = included_established + pending_activation
    draft["active_tanks"] = active_tanks_for_record

    current_selection_label = ", ".join(active_tanks_for_record) if active_tanks_for_record else "None"
    st.markdown(
        f"<div style='margin:10px 0 12px; padding:10px 12px; border-radius:8px; "
        f"background:#1E293B; border:1px solid #334155; color:#FFFFFF;'>"
        f"<span style='color:#94A3B8; font-size:12px; text-transform:uppercase; letter-spacing:0.06em;'>"
        f"Current Selection</span><br/>"
        f"<span style='font-size:15px; font-weight:700;'>{current_selection_label}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    if not active_tanks_for_record:
        st.warning("No tanks are selected for this record. Include at least one active tank or activate a new tank to continue.")
        return

    # Pumps split by active / inactive tank
    active_pump_ids = [p for p in pump_ids if pump_tank_lookup.get(p) in active_tanks_for_record]
    inactive_pump_ids = [p for p in pump_ids if p not in active_pump_ids]

    # Phase 1 ── baseline check uses the active tanks
    baseline_exists_for_active = all(
        legacy_db_utils.has_baseline_record_for_tank(db_file, project_id, t)
        for t in included_established
    ) if included_established else False

    if not legacy_record_phases.render_phase1(
        draft, baseline_exists_for_active, legacy_ui_event_utils.queue_confirmation,
        activating_tanks=pending_activation,
    ):
        return

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

    # Per-tank last records and deltas
    latest_records_by_tank = {
        t: legacy_db_utils.get_latest_record_for_tank(db_file, project_id, t)
        for t in active_tanks_for_record
    }
    ts_valid, tank_deltas, time_error = legacy_phase2_utils.compute_per_tank_deltas(
        draft["record_phase"], ts_valid, record_ts,
        active_tanks_for_record, latest_records_by_tank, parse_ts,
    )
    if time_error:
        st.error(time_error)

    last_ts_by_tank = {}
    for t, rec in latest_records_by_tank.items():
        if rec and rec.get("record_ts"):
            try:
                last_ts_by_tank[t] = parse_ts(rec["record_ts"])
            except Exception:
                pass

    # Display per-tank delta summary
    st.markdown(
        f"<p style='color:white;'>Record Timestamp: <b>{draft['record_ts']}</b></p>",
        unsafe_allow_html=True,
    )
    delta_rows = []
    for t in active_tanks_for_record:
        lr = latest_records_by_tank.get(t)
        last_str = lr["record_ts"] if lr and lr.get("record_ts") else "New (first entry)"
        delta_rows.append({
            "Tank": t,
            "Last Record": last_str,
            "Delta (hrs)": f"{tank_deltas.get(t, 0.0):.2f}",
        })
    if delta_rows:
        st.dataframe(pd.DataFrame(delta_rows), use_container_width=True, hide_index=True)

    # Combine previous grids using all tanks so inactive-tank carry-forward
    # reflects each tank's latest known status.
    latest_records_by_all_tanks = {
        t: legacy_db_utils.get_latest_record_for_tank(db_file, project_id, t)
        for t in water_tanks
    }
    previous_grid = {}
    for t, rec in latest_records_by_all_tanks.items():
        if not rec or not rec.get("status_grid"):
            continue
        for pid, payload in rec["status_grid"].items():
            pid = str(pid).strip()
            if not pid:
                continue
            if pump_tank_lookup.get(pid) != t:
                continue
            previous_grid[pid] = payload

    # Status editor: active-tank pumps only
    status_editor_source_sig = "|".join(
        f"{tank}:{(latest_records_by_tank.get(tank) or {}).get('id', 'none')}"
        for tank in active_tanks_for_record
    )
    status_editor_key = f"status_grid_editor::{draft['record_phase']}::{','.join(active_tanks_for_record)}::{status_editor_source_sig}"

    status_df = legacy_phase2_utils.build_status_rows(active_pump_ids, previous_grid, draft["record_phase"])
    if draft["record_phase"] == "Baseline Calibration (Cold State)":
        baseline_display_df = status_df[["Pump ID", "Previous Status", "Accumulated Time (hrs)", "New Status"]].copy()
        baseline_display_df["Accumulated Time (hrs)"] = pd.to_numeric(
            baseline_display_df["Accumulated Time (hrs)"], errors="coerce"
        ).fillna(0).round(0).astype(int)
        st.dataframe(
            baseline_display_df,
            use_container_width=True, hide_index=True,
        )
        edited_status_df = status_df.copy()
    else:
        edited_status_df = st.data_editor(
            status_df,
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            key=status_editor_key,
            column_config={
                "Pump ID": st.column_config.TextColumn("Pump ID", disabled=True),
                "Previous Status": st.column_config.TextColumn("Previous Status", disabled=True),
                "Accumulated Time (hrs)": st.column_config.NumberColumn("Accumulated Time (hrs)", disabled=True, format="%.0f"),
                "New Status": st.column_config.SelectboxColumn("New Status", options=["RUNNING", "STANDBY", "PAUSED", "FAILED"], required=True),
                "Failure DateTime (YYYY-MM-DD HH:MM:SS)": st.column_config.TextColumn("Failure DateTime (YYYY-MM-DD HH:MM:SS)"),
            },
        )

    # Show inactive-tank pumps as read-only STANDBY
    if inactive_pump_ids:
        with st.expander(f"Inactive tanks — {len(inactive_pump_ids)} pump(s) locked to STANDBY", expanded=False):
            inactive_df = legacy_phase2_utils.build_status_rows(inactive_pump_ids, previous_grid, "Baseline Calibration (Cold State)")
            inactive_pump_list = ", ".join(inactive_df["Pump ID"].tolist())
            st.markdown(
                f"<p style='color:#9CA3AF; font-size:13px;'>Inactive pumps carried forward unchanged: <b>{inactive_pump_list}</b>.</p>",
                unsafe_allow_html=True,
            )

    phase2_col, _ = st.columns([1.7, 4.3])
    with phase2_col:
        if st.button("Confirm Status Grid & Time Distribution", use_container_width=True, type="primary", key="confirm_phase2"):
            if not ts_valid:
                st.error("Fix timestamp issues before confirming Phase 2.")
            else:
                errors, maintenance_candidates, computed_grid = legacy_phase2_utils.process_phase2_confirmation(
                    edited_status_df,
                    draft["record_phase"],
                    0.0,   # unused — per-tank deltas used instead
                    None,  # unused — per-tank last_ts used instead
                    record_ts,
                    parse_ts,
                    tank_deltas=tank_deltas,
                    pump_tank_lookup=pump_tank_lookup,
                    last_ts_by_tank=last_ts_by_tank,
                )

                if errors:
                    for err in errors:
                        st.error(err)
                else:
                    # Carry inactive-tank pumps forward unchanged (0 added hours)
                    for pid in inactive_pump_ids:
                        prev = previous_grid.get(pid, {})
                        prev_acc = float(prev.get("acc_hours", 0.0) or 0.0)
                        computed_grid[pid] = {
                            "status": str(prev.get("status", "STANDBY")).upper(),
                            "prev_status": str(prev.get("status", "STANDBY")).upper(),
                            "acc_hours_prev": round(prev_acc, 3),
                            "added_hours": 0.0,
                            "acc_hours": round(prev_acc, 3),
                            "failure_ts": "",
                        }

                    draft["status_grid"] = computed_grid
                    draft["maintenance_candidates"] = maintenance_candidates
                    draft["phase2_confirmed"] = True
                    legacy_ui_event_utils.queue_confirmation("Phase 2 confirmed. Time distribution calculated.")
                    st.rerun()

    if not draft.get("phase2_confirmed", False):
        return

    active_tanks_label = ", ".join(active_tanks_for_record)
    st.markdown(
        f"<p style='color:#9CA3AF; font-size:13px; margin-top:4px;'>"
        f"This record currently covers <b>{active_tanks_label}</b>."
        f"</p>",
        unsafe_allow_html=True,
    )

    if not legacy_record_phases.render_phase3(draft, active_tanks_for_record, legacy_ui_event_utils.queue_confirmation):
        return

    st.markdown("<p class='col-header'>Phase 4: Targeted Hardware Polling</p>", unsafe_allow_html=True)
    st.markdown(
        f"<p style='color:#9CA3AF; font-size:13px;'>"
        f"Phase 4 only shows pumps assigned to the active tank(s): <b>{active_tanks_label}</b>."
        f"</p>",
        unsafe_allow_html=True,
    )
    limits_df = st.session_state.get("limits_df", pd.DataFrame(columns=["Pump ID", "Max Stator Temp (°C)", "Max Current (A)"]))
    extra_limits_df = st.session_state.get("extra_limits_df", pd.DataFrame(columns=["Formula Name", "Min Value", "Max Value", "Applies To"]))
    limits_lookup = legacy_phase4_utils.build_limits_lookup(limits_df)

    temp_units, clamp_units = legacy_state_utils.build_phase4_hardware_plan(active_pump_ids, draft["status_grid"])
    pump_readings = {}
    previous_readings = draft.get("pump_readings", {})
    if not isinstance(previous_readings, dict):
        previous_readings = {}

    # Seed missing per-pump readings from each tank's latest record so
    # inactive-tank standby cards keep their latest known values.
    for t, rec in latest_records_by_all_tanks.items():
        if not rec:
            continue
        try:
            rec_readings = json.loads(rec.get("pump_readings_json") or "{}")
        except Exception:
            rec_readings = {}
        if not isinstance(rec_readings, dict):
            continue
        for pid, payload in rec_readings.items():
            pid = str(pid).strip()
            if not pid:
                continue
            if pump_tank_lookup.get(pid) != t:
                continue
            if pid not in previous_readings:
                previous_readings[pid] = payload
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
        active_pump_ids,
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
        active_pump_ids,
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

    phase4_col, _ = st.columns([1.7, 4.3])
    with phase4_col:
        if st.button("Confirm Targeted Polling", use_container_width=True, type="primary", key="confirm_phase4"):
            fallback_temp_values = {
                pid: st.session_state.get(f"phase4_temp_fallback_{pid}")
                for pid, _ in fallback_temp_pumps
            }
            fallback_clamp_values = {
                pid: st.session_state.get(f"phase4_clamp_fallback_{pid}")
                for pid in fallback_clamp_pumps
            }

            errors, temp_tables_payload, clamp_tables_payload, pump_readings = legacy_phase4_utils.process_phase4_confirmation(
                temp_tables,
                clamp_tables,
                fallback_temp_values,
                fallback_clamp_values,
                fallback_temp_pumps,
                fallback_clamp_pumps,
                active_pump_ids,
                draft["status_grid"],
                previous_readings,
                pump_readings,
                safe_float,
                aggregate_temperature_for_pump,
            )

            if errors:
                for err in errors:
                    st.error(err)
            else:
                draft["phase4_temp_tables"] = temp_tables_payload
                draft["phase4_clamp_tables"] = clamp_tables_payload
                draft["pump_readings"] = pump_readings
                draft["phase4_confirmed"] = True
                legacy_ui_event_utils.queue_confirmation("Phase 4 confirmed. Hardware readings captured.")
                st.rerun()

    if not draft.get("phase4_confirmed", False):
        return

    ambient = safe_float(draft.get("ambient_temp", 0.0), 0.0)
    tank_temps = draft.get("tank_temps", {}) if isinstance(draft.get("tank_temps", {}), dict) else {}
    formulas_df = st.session_state.get("formulas_df", pd.DataFrame(columns=["Formula Name", "Target", "Equation"]))
    var_mapping_df = st.session_state.get("var_mapping_df", pd.DataFrame(columns=["Variable", "Mapped Sensor"]))

    review_rows, all_alarms, formula_debug_rows = legacy_phase56_utils.build_phase56_review_data(
        active_pump_ids,
        draft,
        ambient,
        tank_temps,
        pump_tank_lookup,
        formulas_df,
        var_mapping_df,
        limits_lookup,
        extra_limits_df,
        build_formula_variables_for_pump,
        get_formula_target_specificity,
        evaluate_formula_for_pump,
        safe_float,
    )

    st.markdown(
        f"<p class='col-header'>Phase 5/6: Review for Active Tank(s) - {active_tanks_label}</p>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<p style='color:#9CA3AF; font-size:13px;'>"
        f"Only pumps in the active tank(s) are evaluated for temperature rise, limits, and alarms in this record."
        f"</p>",
        unsafe_allow_html=True,
    )

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
    save_col, _ = st.columns([1.2, 4.8])
    with save_col:
        if st.button("Save Record", use_container_width=True, type="primary", disabled=not can_save, key="save_record_button"):
            try:
                saved_record_id = legacy_record_save_utils.save_project_record(
                    db_file,
                    project_id,
                    draft,
                    all_alarms,
                    alarm_ack,
                    active_tanks=active_tanks_for_record,
                )

                # Persist start dates for any tanks being activated this session
                if pending_activation:
                    updated_tsd = legacy_db_utils.get_tank_start_dates(db_file, project_id)
                    for tank in pending_activation:
                        if not updated_tsd.get(tank):
                            updated_tsd[tank] = draft["record_ts"]
                    legacy_db_utils.save_tank_start_dates(db_file, project_id, updated_tsd)
                    draft["activating_tanks"] = []

                legacy_ui_event_utils.add_event_log_entry(f"New record saved ({draft['record_phase']}).")
                for alarm_item in all_alarms:
                    legacy_ui_event_utils.add_event_log_entry(f"ALARM {alarm_item['pump_id']}: {'; '.join(alarm_item['alarms'])}")

                stable_running_pumps = legacy_record_save_utils.compute_stable_running_pumps(draft, all_alarms)

                closed_ids = legacy_ui_event_utils.auto_close_maintenance_for_stable_pumps(
                    db_file,
                    project_id,
                    stable_running_pumps,
                    lambda pid: legacy_db_utils.get_maintenance_events(db_file, pid),
                )
                if closed_ids:
                    legacy_ui_event_utils.add_event_log_entry(f"Auto-closed maintenance events: {', '.join([str(x) for x in closed_ids])}.")

                legacy_ui_event_utils.persist_event_log_for_project(db_file, project_id)

                legacy_record_save_utils.finalize_record_save(
                    draft,
                    review_rows,
                    all_alarms,
                    saved_record_id,
                )
                legacy_ui_event_utils.queue_confirmation("Record saved successfully.")
                st.rerun()
            except Exception as e:
                st.error(f"Could not save record: {e}")

    if draft.get("save_completed", False):
        legacy_record_save_utils.render_post_save_navigation(draft)
