import datetime
import json
from pump_architect.db.connection import get_connection

import pandas as pd
import streamlit as st

from pump_architect import legacy_ui_event_utils


def render_project_form(db_file):
    legacy_ui_event_utils.inject_industrial_css()
    step = st.session_state.wizard_step
    st.markdown(
        """
        <style>
            .wizard-step-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 0.5rem;
            }

            .wizard-project-name {
                margin-top: 1.25rem;
                padding: 0.9rem 1rem;
                border-radius: 12px;
                border: 1px solid rgba(77, 163, 255, 0.28);
                background: rgba(13, 110, 253, 0.12);
                color: #d7e9ff;
                font-size: 1.1rem;
                font-weight: 600;
            }

            .wizard-project-name strong {
                color: #4DA3FF !important;
                letter-spacing: 0.02em;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(f"<p style='text-align:right; color:white; font-size:18px;'>Step {step} of 6</p>", unsafe_allow_html=True)
    st.progress(step / 6.0)

    cancel_col, _ = st.columns([1.2, 6])
    with cancel_col:
        if st.button("Cancel & Return", use_container_width=True):
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

        target_val_text = st.text_input("Target Value", key="target_val_input")
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

        st.markdown(
            f"<div class='wizard-project-name'>Project Name: <strong>{project_name}</strong></div>",
            unsafe_allow_html=True,
        )

        st.write("")
        next_col, _ = st.columns([1.15, 5.85])
        with next_col:
            if st.button("Next Step", type="primary", use_container_width=True):
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
            submitted = st.form_submit_button("Confirm Table Entries", use_container_width=True, type="primary")

            if submitted:
                # Defensive: Check if 'Pump Model' column exists after editing
                if "Pump Model" not in updated_df.columns:
                    st.error("'Pump Model' column is missing. Please do not remove required columns.")
                else:
                    final_df = updated_df.dropna(subset=["Pump Model"]).reset_index(drop=True)
                    final_df["Pump ID"] = [f"P-{str(i+1).zfill(2)}" for i in range(len(final_df))]
                    st.session_state.specs_df = final_df
                    legacy_ui_event_utils.queue_confirmation("Table synced. Pump IDs generated. You can now click Next.")
                    st.rerun()

        # 3. Navigation Buttons (Outside the form)
        st.write("")
        b1, b2, _ = st.columns([1.1, 1.1, 3.8])
        with b1:
            if st.button("Back", use_container_width=True):
                st.session_state.wizard_step = 1
                st.rerun()
        with b2:
            if st.button("Next", use_container_width=True, type="primary"):
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
        _, col_t2, col_t3 = st.columns([3.5, 1.1, 1.2])

        with col_t2:
            if st.button("Add Tank", use_container_width=True, type="primary", key="add_tank_btn"):
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
        # 3. Display Active Tanks (Moved Below, Larger Font, Left Aligned)
        st.markdown(
            f"<div style='text-align: left; margin-top: 15px; margin-bottom: 10px;'>"
            f"<span style='color: white; font-size: 22px; font-weight: bold;'>Active Tanks: </span>"
            f"<span style='color: #4DA3FF; font-size: 22px; font-weight: 500;'>{' &nbsp;|&nbsp; '.join(st.session_state.water_tanks)}</span>"
            f"</div>",
            unsafe_allow_html=True
        )

        if len(st.session_state.water_tanks) > 1:
            st.info(
                "Multiple tanks configured. Each tank's **start date** is recorded automatically "
                "the first time you activate it inside the **Add New Record** wizard. "
                "Pumps in tanks that have not yet been activated are locked to STANDBY "
                "and do not accumulate run hours until their tank is activated."
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

            confirm = st.form_submit_button("Confirm Layout Changes", use_container_width=True, type="primary")
            if confirm:
                st.session_state.layout_df = updated_layout.reset_index(drop=True)
                legacy_ui_event_utils.queue_confirmation("Layout mappings saved.")
                st.rerun()

        # 6. Navigation
        st.write("")
        b1, b2, _ = st.columns([1.1, 1.1, 3.8])
        with b1:
            if st.button("Back", use_container_width=True, key="back_step3"):
                st.session_state.wizard_step = 2
                st.rerun()
        with b2:
            if st.button("Next", use_container_width=True, type="primary", key="next_step3"):
                if "updated_layout" in locals():
                    st.session_state.layout_df = updated_layout.reset_index(drop=True)
                st.session_state.wizard_step = 4
                st.rerun()

    # STEP 4: Hardware & Sensor Mapping
    elif step == 4:
        st.markdown("<div class='step-title'>4. Hardware & Sensor Mapping</div>", unsafe_allow_html=True)

        # --- FORCE REHYDRATE HARDWARE STATE IF RESTORING ---
        if st.session_state.get("_restoring_project", False):
            conn = get_connection()
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
            available_pumps = ["P-01"]  # Fallback
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
            if st.button("HIOKI Temp", use_container_width=True, type="primary", key="add_htemp"):
                count = sum(1 for hw in st.session_state.hardware_list if "HIOKI Temp" in hw)
                st.session_state.hardware_list.append(f"HIOKI Temp {count + 1}")
                st.rerun()
        with col2:
            if st.button("HIOKI Power", use_container_width=True, type="primary", key="add_hpower"):
                count = sum(1 for hw in st.session_state.hardware_list if "HIOKI Power" in hw)
                st.session_state.hardware_list.append(f"HIOKI Power {count + 1}")
                st.rerun()
        with col3:
            if st.button("HIOKI Clamp", use_container_width=True, type="primary", key="add_hclamp"):
                count = sum(1 for hw in st.session_state.hardware_list if "HIOKI Clamp" in hw)
                st.session_state.hardware_list.append(f"HIOKI Clamp {count + 1}")
                st.rerun()
        with col4:
            if st.button("General HW", use_container_width=True, type="primary", key="add_gen"):
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
                    st.write("")  # Just a small space for visual padding
                    updated_ds[ds_key] = st.multiselect(
                        f"Allowed Data Entry Methods for {hw_name}:",
                        options=ds_options,
                        default=st.session_state[ds_key],
                        key=f"multi_ds_{hw_name}"
                    )
                    st.divider()

                confirm = st.form_submit_button("Confirm Hardware Setup", use_container_width=True, type="primary")
                if confirm:
                    for key, edited_df in updated_dfs.items():
                        st.session_state[key] = edited_df
                    for key, selected_ds in updated_ds.items():
                        st.session_state[key] = selected_ds
                    legacy_ui_event_utils.queue_confirmation("All hardware configurations saved.")
                    st.rerun()

        # 5. Navigation
        st.write("")
        b1, b2, _ = st.columns([1.1, 1.1, 3.8])
        with b1:
            if st.button("Back", use_container_width=True, key="back_step4"):
                st.session_state.wizard_step = 3
                st.rerun()
        with b2:
            if st.button("Next", use_container_width=True, type="primary", key="next_step4"):
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
            confirm = st.form_submit_button("Confirm Formulas", use_container_width=True, type="primary")
            if confirm:
                st.session_state.var_mapping_df = updated_vars.reset_index(drop=True)
                st.session_state.formulas_df = updated_forms.reset_index(drop=True)
                legacy_ui_event_utils.queue_confirmation("Variables and formulas saved.")
                st.rerun()

        # 4. NAVIGATION
        st.write("")
        b1, b2, _ = st.columns([1.1, 1.1, 3.8])
        with b1:
            if st.button("Back", use_container_width=True, key="back_step5"):
                st.session_state.wizard_step = 4
                st.rerun()
        with b2:
            if st.button("Next", use_container_width=True, type="primary", key="next_step5"):
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

            save_watchdogs = st.form_submit_button("Confirm Watchdog Setup", use_container_width=True, type="primary")
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
                legacy_ui_event_utils.queue_confirmation("Watchdog table saved.")
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

            save_limits = st.form_submit_button("Confirm Safety Limits", use_container_width=True, type="primary")
            if save_limits:
                st.session_state.limits_df = edited_lim.reset_index(drop=True)
                st.session_state.extra_limits_df = edited_extra_lim.reset_index(drop=True)
                legacy_ui_event_utils.queue_confirmation("Safety limits saved.")
                st.rerun()

        st.divider()

        # --- 3. EVENT ALERT LOG (Dynamic, Scrollable) ---
        st.markdown("<p style='color: white; font-size: 18px; font-weight: bold;'>2. Event Alert Log</p>", unsafe_allow_html=True)
        if "event_log" not in st.session_state:
            st.session_state.event_log = []

        def log_event(msg):
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
                    row_pumps = tank_pumps[row_start:row_start + 3]
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

        if st.button("Confirm Dashboard Visual Layout Preview", use_container_width=True, type="primary", key="confirm_dashboard_preview"):
            legacy_ui_event_utils.queue_confirmation("Dashboard visual layout preview confirmed.")
            st.rerun()

        st.divider()

        # --- 5. FINAL SAVE LOGIC ---
        st.markdown("<p style='color: white; font-size: 18px; font-weight: bold;'>4. Finalize & Save</p>", unsafe_allow_html=True)
        c1, c2, _ = st.columns([1.1, 1.5, 3.4])
        if c1.button("Back", key="back_s6"):
            st.session_state.wizard_step = 5
            st.rerun()
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

            conn = get_connection()
            c = conn.cursor()

            try:
                run_mode = st.session_state.get("run_mode", "Continuous")
                target_val = str(st.session_state.get("target_val", "0"))

                # --- CLEAN SAVE TO DATABASE ---
                tanks_str = "||".join(st.session_state.get("water_tanks", ["Water Tank 1"]))
                layout_json = None
                if "layout_df" in st.session_state and isinstance(st.session_state.layout_df, pd.DataFrame):
                    layout_json = st.session_state.layout_df.to_json()

                # --- NEW: Save hardware_list, all df_/ds_ DataFrames as JSON ---
                hardware_list = st.session_state.get("hardware_list", [])
                hardware_dfs = {}
                hardware_ds = {}
                for k in st.session_state.keys():
                    if k.startswith("df_") and isinstance(st.session_state[k], pd.DataFrame):
                        hardware_dfs[k] = st.session_state[k].to_json()
                    if k.startswith("ds_") and isinstance(st.session_state[k], list):
                        hardware_ds[k] = st.session_state[k]
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
                legacy_ui_event_utils.queue_confirmation(f"Project '{project_name}' successfully saved.")

                # Cleanup and Go Home
                for k in ["specs_df", "wizard_step", "proj_type", "test_type", "layout_df", "watchdogs_df", "watchdog_matrix_df", "limits_df", "extra_limits_df", "event_log", "dashboard_main_tracker", "add_record_draft", "maintenance_prefill_pumps", "maintenance_source_record_id"]:
                    if k in st.session_state:
                        del st.session_state[k]
                st.session_state.page = "home"
                st.rerun()

            except Exception as e:
                st.error(f"Database Error: {e}")
            finally:
                conn.close()
