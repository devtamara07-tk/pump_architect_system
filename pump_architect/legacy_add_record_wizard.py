import datetime

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


def render_add_record_wizard(db_file):
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

    if st.button("Back to Dashboard", use_container_width=True):
        st.session_state.page = "dashboard"
        st.rerun()

    draft = legacy_add_record_setup.initialize_add_record_draft()

    baseline_exists = legacy_db_utils.has_baseline_record(db_file, project_id)
    latest_record = legacy_db_utils.get_latest_record(db_file, project_id)

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

    if not legacy_record_phases.render_phase1(draft, baseline_exists, legacy_ui_event_utils.queue_confirmation):
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
                legacy_ui_event_utils.queue_confirmation("Phase 2 confirmed. Time distribution calculated.")
                st.rerun()

    if not draft.get("phase2_confirmed", False):
        return

    water_tanks = st.session_state.get("water_tanks", [])
    if not legacy_record_phases.render_phase3(draft, water_tanks, legacy_ui_event_utils.queue_confirmation):
        return

    st.markdown("<p class='col-header'>Phase 4: Targeted Hardware Polling</p>", unsafe_allow_html=True)
    limits_df = st.session_state.get("limits_df", pd.DataFrame(columns=["Pump ID", "Max Stator Temp (°C)", "Max Current (A)"]))
    extra_limits_df = st.session_state.get("extra_limits_df", pd.DataFrame(columns=["Formula Name", "Min Value", "Max Value", "Applies To"]))
    limits_lookup = legacy_phase4_utils.build_limits_lookup(limits_df)

    temp_units, clamp_units = legacy_state_utils.build_phase4_hardware_plan(pump_ids, draft["status_grid"])
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
            pump_ids,
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

    st.markdown("<p class='col-header'>Phase 5/6: Safety Validation, Review & Commit</p>", unsafe_allow_html=True)
    ambient = float(draft.get("ambient_temp", 0.0) or 0.0)
    tank_temps = draft.get("tank_temps", {}) if isinstance(draft.get("tank_temps", {}), dict) else {}
    formulas_df = st.session_state.get("formulas_df", pd.DataFrame(columns=["Formula Name", "Target", "Equation"]))
    var_mapping_df = st.session_state.get("var_mapping_df", pd.DataFrame(columns=["Variable", "Mapped Sensor"]))

    review_rows, all_alarms, formula_debug_rows = legacy_phase56_utils.build_phase56_review_data(
        pump_ids,
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
            saved_record_id = legacy_record_save_utils.save_project_record(
                db_file,
                project_id,
                draft,
                all_alarms,
                alarm_ack,
            )

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
