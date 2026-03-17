import streamlit as st
import pandas as pd
import sqlite3
import datetime

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
    # Fixed Table Schema
    c.execute('''CREATE TABLE IF NOT EXISTS projects (
        project_id TEXT PRIMARY KEY, type TEXT, test_type TEXT, 
        run_mode TEXT, target_val TEXT, created_at DATETIME)''')
    c.execute('''CREATE TABLE IF NOT EXISTS pumps (
        pump_id TEXT, project_id TEXT, model TEXT, iso_no TEXT, hp REAL, kw REAL, 
        voltage TEXT, amp_min REAL, amp_max REAL, phase INTEGER, hertz TEXT, 
        insulation TEXT, tank_name TEXT, PRIMARY KEY (pump_id, project_id))''')
    conn.commit()
    conn.close()

if "page" not in st.session_state: st.session_state.page = "home"
if "wizard_step" not in st.session_state: st.session_state.wizard_step = 1

# --- 2. RESTORED INDUSTRIAL DARK UI CSS (18px Fonts) ---
def inject_industrial_css():
    st.markdown("""
        <style>
            /* Main Background */
            .main { background-color: #121417; color: #E0E0E0; }
            [data-testid="stHeader"] { background: rgba(0,0,0,0); }
            
            /* Hero Section */
            .hero-bg {
                background: linear-gradient(rgba(0,0,0,0.7), rgba(0,0,0,0.7)), 
                            url('https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?q=80&w=2070&auto=format&fit=crop');
                background-size: cover; background-position: center;
                padding: 60px; border-radius: 15px; text-align: center; margin-bottom: 30px; border: 1px solid #333;
            }
            
            /* Typography & Text Sizes */
            .step-title { color: white !important; font-size: 2.2rem !important; font-weight: bold !important; margin-bottom: 20px; }
            .col-header { color: white !important; font-size: 18px !important; font-weight: bold; border-bottom: 2px solid #444; padding-bottom: 10px; text-transform: uppercase; }
            .white-text { color: white !important; font-size: 18px !important; font-weight: 500; margin-top: 8px; }
            
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
            
            /* PRIMARY BUTTON (Finish & Save) */
            div.stButton > button[kind="primary"] {
                background-color: #0d6efd !important;
                color: white !important;
                border: none !important;
            }

            /* --- INDUSTRIAL UI FIXES --- */
            /* Table/Input Data Editor Sizes */
            div[data-testid="stDataEditor"] { background-color: #1C1F24 !important; border: 1px solid #444 !important; font-size: 16px !important; }
            div[data-testid="stTextInput"] input, div[data-testid="stNumberInput"] input { background-color: #1C1F24 !important; color: white !important; border: 1px solid #444 !important; font-size: 16px !important; }

            /* --- THE FINAL WARNING COLOR FIX --- */
            /* Changes the text of any warning-class paragraph to white */
            div[data-testid="stMarkdownContainer"] p.stWarning {
                color: white !important;
            }
        </style>
    """, unsafe_allow_html=True)

# --- 3. THE WIZARD (FULL STEPS RESTORED) ---
def render_project_form():
    inject_industrial_css()
    step = st.session_state.wizard_step
    st.markdown(f"<p style='text-align:right; color:white; font-size:18px;'>Step {step} of 6</p>", unsafe_allow_html=True)
    st.progress(step / 6.0)

    if st.button("Cancel & Return"):
        st.session_state.page = "home"; st.rerun()

    # STEP 1: Details & Test Target
    if step == 1:
        st.markdown("<div class='step-title'>1. Project Details & Target</div>", unsafe_allow_html=True)
        c1, c2 = st.columns([1, 2])
        st.session_state.proj_type = c1.radio("Pump Type", ["Centrifugal", "Submersible"], horizontal=True)
        st.session_state.test_type = c2.text_input("Test Type", value=st.session_state.get("test_type", ""))
        
        st.divider()
        st.markdown("<p style='color:white; font-weight:bold; font-size:20px;'>Test Target Selection</p>", unsafe_allow_html=True)
        rt1, rt2 = st.columns([1, 2])
        run_mode = rt1.radio("Run Mode", ["Continuous Run", "Intermittent Run"], key="rm_input")
        with rt2:
            if run_mode == "Continuous Run":
                unit = st.selectbox("Duration Unit", ["Hours", "Days"])
                st.number_input(f"Total {unit}", min_value=1, key="tv_input")
            else:
                st.number_input("Total Cycles", min_value=1, key="tv_input")

        # --- NEW: Project Name Display ---
        # Merging Pump Type + Test Type
        merged_name = f"{st.session_state.proj_type} {st.session_state.test_type}"
        
        st.write("") # Spacer
        st.markdown(f"""
            <p style='margin-bottom: 0px; color:white; font-weight:bold; font-size:20px;'>
                Project Name
            </p>
            <p style='margin-top: 5px; font-size:20px;'>
                <span style='color: white;'>Name: </span>
                <span style='color: #3498DB; font-weight: bold;'>{merged_name}</span>
            </p>
        """, unsafe_allow_html=True)
        
        # Step 1 Button
        st.write("") 
        if st.button("Next", use_container_width=True): 
            st.session_state.wizard_step = 2
            st.rerun()

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
            st.markdown("<p style='color: #ffc107;'>⚠️ Type all data, then click 'Confirm Table Entries' below to lock in IDs.</p>", unsafe_allow_html=True)
            
            step2_config = {
                "Pump Model": st.column_config.TextColumn("Pump Model", required=True, default=""),
                "Pump ID": st.column_config.TextColumn("Pump ID", disabled=True),
                "Hertz": st.column_config.SelectboxColumn("Hertz", options=["50", "60"], default="60"),
                "Phase": st.column_config.SelectboxColumn("Phase", options=[1, 3], default=3),
            }

            # This editor is now "silent" - it won't vibrate!
            updated_df = st.data_editor(
                st.session_state.specs_df,
                num_rows="dynamic",
                use_container_width=True,
                hide_index=True,
                column_config=step2_config,
                key="pump_editor_form_mode"
            )
            
            # The "Enter" clause - This processes everything at once
            submitted = st.form_submit_button("Confirm Table Entries", use_container_width=True)
            
            if submitted:
                # Apply the .reset_index(drop=True) and ID logic only on click
                final_df = updated_df.dropna(subset=["Pump Model"]).reset_index(drop=True)
                final_df["Pump ID"] = [f"P-{str(i+1).zfill(2)}" for i in range(len(final_df))]
                st.session_state.specs_df = final_df
                st.success("Table synced! IDs generated. You can now click Next.")
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
            f"<span style='color: #4CAF50; font-size: 22px; font-weight: 500;'>{' &nbsp;|&nbsp; '.join(st.session_state.water_tanks)}</span>"
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
                st.success("Layout Mappings Saved!")
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
                    st.success("All Hardware configurations saved successfully!")
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

        # Pull available pumps for formula assignment
        if "specs_df" in st.session_state and not st.session_state.specs_df.empty:
            pump_options = ["Global (Apply to All Compatible Pumps)"] + st.session_state.specs_df["Pump ID"].tolist()
        else:
            pump_options = ["Global (Apply to All Compatible Pumps)", "P-01"]

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
                st.success("Variables and Formulas saved securely!")
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

    # --- STEP 6 (DASHBOARD & REPORT SET UP) ---
    elif step == 6:
        st.markdown("<div class='step-title'>6. Dashboard and Report Set up</div>", unsafe_allow_html=True)

        # --- PREPARE DATA FROM PREVIOUS STEPS ---
        if "specs_df" in st.session_state and not st.session_state.specs_df.empty:
            valid_pumps = st.session_state.specs_df["Pump ID"].tolist()
            pumps_df = st.session_state.specs_df.copy()
        else:
            valid_pumps = ["P-01"]
            pumps_df = pd.DataFrame({"Pump ID": ["P-01"], "Amp Max": [10.0]})

        # Initialize Watchdogs DF
        if "watchdogs_df" not in st.session_state:
            st.session_state.watchdogs_df = pd.DataFrame([
                {"Watchdog Name": "ESP32 System", "Alert Limit": "Connection Lost"},
                {"Watchdog Name": "HIOKI Interface", "Alert Limit": "Timeout > 5s"},
                {"Watchdog Name": "MAX6675 Sensor", "Alert Limit": "Error 0xFFFF"}
            ])

        # Initialize Safety Limits DF
        if "limits_df" not in st.session_state:
            limits = []
            for _, row in pumps_df.iterrows():
                limits.append({
                    "Pump ID": row.get("Pump ID", "Unknown"),
                    "Max Stator Temp (°C)": 155.0, 
                    "Max Current (A)": row.get("Amp Max", 0.0), 
                    "Max Temp Rise (°C)": 115.0 
                })
            st.session_state.limits_df = pd.DataFrame(limits)

        # --- THE NO-SHAKE FORM ---
        with st.form("step6_dashboard_form", clear_on_submit=False):
            st.markdown("<p style='color: white; font-size: 18px; font-weight: bold;'>1. System Watchdogs & Safety Limits</p>", unsafe_allow_html=True)
            
            wd_config = {
                "Watchdog Name": st.column_config.TextColumn("Watchdog Parameter", required=True),
                "Alert Limit": st.column_config.TextColumn("Critical Trigger", required=True)
            }
            updated_wd = st.data_editor(st.session_state.watchdogs_df, hide_index=True, use_container_width=True, num_rows="dynamic", column_config=wd_config, key="watchdog_edit")

            st.divider()

            st.markdown("<p style='color: white; font-size: 18px; font-weight: bold;'>2. Pump Safety Thresholds</p>", unsafe_allow_html=True)
            lim_config = {
                "Pump ID": st.column_config.TextColumn("Pump ID", disabled=True),
                "Max Stator Temp (°C)": st.column_config.NumberColumn(required=True),
                "Max Current (A)": st.column_config.NumberColumn(required=True),
                "Max Temp Rise (°C)": st.column_config.NumberColumn(required=True)
            }
            updated_lim = st.data_editor(st.session_state.limits_df, hide_index=True, use_container_width=True, column_config=lim_config, key="limits_edit")

            st.write("")
            if st.form_submit_button("Confirm & Save Dashboard Settings", use_container_width=True):
                st.session_state.watchdogs_df = updated_wd
                st.session_state.limits_df = updated_lim
                st.rerun()

        st.divider()

        # 3. DASHBOARD VISUAL PREVIEW (3 Horizontal Lines)
        st.markdown("<p style='color: white; font-size: 18px; font-weight: bold;'>3. Dashboard Visual Layout Preview</p>", unsafe_allow_html=True)
        selected_dash_pumps = st.multiselect("Select Pumps to show on Main Dashboard", valid_pumps, default=valid_pumps)
        
        cols = st.columns(3)
        for i, p_id in enumerate(selected_dash_pumps):
            with cols[i % 3]:
                st.markdown(f"""
                    <div style="border: 1px solid #444; padding: 10px; margin-bottom: 10px; border-radius: 5px; background: #1C1F24; text-align: center;">
                        <p style="margin:0; font-weight: bold; color: #3498DB; font-size: 18px;">{p_id}</p>
                        <p style="margin:0; font-size: 14px; color: #2ecc71; font-weight: bold;">0.00A &nbsp;&nbsp; 🟢 RUN</p>
                        <p style="margin:0; font-size: 12px; color: #888;">Temp: 00.0°C | Rise: 00.0°C</p>
                    </div>
                """, unsafe_allow_html=True)

        st.divider()

        # 4. FINAL SAVE LOGIC (Positional Fix)
        st.markdown("<p style='color: white; font-size: 18px; font-weight: bold;'>4. Finalize & Save</p>", unsafe_allow_html=True)
        c1, c2 = st.columns([1, 4])
        if c1.button("Back", key="back_s6"): st.session_state.wizard_step = 5; st.rerun()
        
        if c2.button("Finish & Save Project", type="primary", use_container_width=True, key="finish_btn"):
            proj_type = st.session_state.get("proj_type", "Project")
            test_type = st.session_state.get("test_type", "Test")
            project_name = f"{proj_type} {test_type}"
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            
            # --- THE POSITIONAL FIX ---
            # Instead of naming columns, we just push 6 values into the 6 slots.
            # This bypasses the "no column named project_name" error.
            try:
                c.execute("INSERT OR REPLACE INTO projects VALUES (?, ?, ?, ?, ?, ?)", 
                         (project_name, proj_type, test_type, timestamp, "Active", "Operator"))
                
                # Save Pumps Specs
                for _, row in st.session_state.specs_df.dropna(subset=["Pump ID"]).iterrows():
                    p_id = row["Pump ID"]
                    tank_name = "Unassigned"
                    if "layout_df" in st.session_state:
                        match = st.session_state.layout_df[st.session_state.layout_df["Pump ID"] == p_id]
                        if not match.empty: tank_name = match.iloc[0]["Assigned Tank"]

                    # --- UPDATED: Added a 13th '?' and a 13th value ("N/A") ---
                    c.execute("INSERT OR REPLACE INTO pumps VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", 
                             (p_id, 
                              project_name, 
                              row.get("Pump Model", ""), 
                              row.get("ISO No.", ""), 
                              row.get("HP", 0), 
                              row.get("kW", 0), 
                              row.get("Voltage (V)", ""), 
                              row.get("Amp Max", 0), 
                              row.get("Phase", 3), 
                              row.get("Hertz", 60), 
                              row.get("Insulation", ""), 
                              tank_name,
                              "N/A" # This is the 13th value for the 13th column
                             ))
                
                conn.commit()
                st.success(f"Project '{project_name}' Successfully Saved!")
                
                # Cleanup and Go Home
                for k in ["specs_df", "wizard_step", "proj_type", "test_type", "layout_df", "watchdogs_df"]: 
                    if k in st.session_state: del st.session_state[k]
                st.session_state.page = "home"
                st.rerun()

            except Exception as e:
                st.error(f"Database Error: {e}. Ensure the 'projects' table has exactly 6 columns.")
            finally:
                conn.close()

# --- HELPER FUNCTIONS ---
def handle_open_project(project_id):
    conn = sqlite3.connect(DB_FILE)
    # 1. Load the core project info
    proj_row = conn.execute("SELECT type, test_type FROM projects WHERE project_id = ?", (project_id,)).fetchone()
    
    if proj_row:
        st.session_state.current_project = project_id
        st.session_state.proj_type = proj_row[0]
        st.session_state.test_type = proj_row[1]
        
        # 2. Load the pumps into the active session
        try:
            query = "SELECT * FROM pumps WHERE project_name = ?"
            st.session_state.active_pumps_df = pd.read_sql_query(query, conn, params=(project_id,))
        except:
            st.session_state.active_pumps_df = pd.DataFrame()

        # 3. Switch to Dashboard Page
        st.session_state.page = "dashboard"
        conn.close()
        st.rerun()
    conn.close()

def handle_modify_project(project_id):
    conn = sqlite3.connect(DB_FILE)
    # Using 'type' and 'test_type' to match your projects table
    proj_row = conn.execute("SELECT type, test_type FROM projects WHERE project_id = ?", (project_id,)).fetchone()
    
    if proj_row:
        # 1. Fill the 'Desktop' (Session State) with Basic Info
        st.session_state.proj_type = proj_row[0]
        st.session_state.test_type = proj_row[1]
        
        # 2. Fill the 'Desktop' with the Pumps
        try:
            # We look in the pumps table for rows belonging to this project ID
            query = "SELECT * FROM pumps WHERE project_name = ?"
            pumps_df = pd.read_sql_query(query, conn, params=(project_id,))
            
            if not pumps_df.empty:
                # We drop the 'project_name' column so the table editor in Step 2 stays clean
                st.session_state.specs_df = pumps_df.drop(columns=['project_name'], errors='ignore')
        except:
            pass # If no pumps exist yet, it stays blank
            
        # 3. Open the 'Factory' (Wizard)
        st.session_state.page = "create"
        st.session_state.wizard_step = 1
        conn.close()
        st.rerun()
    conn.close()

# --- 4. MAIN ROUTING & HOME (Original 18px Headers) ---
init_db()
inject_industrial_css()

if st.session_state.page == "home":
    st.markdown('<div class="hero-bg"><h1 style="color:white; letter-spacing:2px; font-size:3rem;">PUMP ARCHITECT SYSTEM</h1><p style="color:#aaa; font-size:1.5rem;">Control Center v2.0</p></div>', unsafe_allow_html=True)
    if st.button("Create New Project"):
        st.session_state.page = "create"; st.session_state.wizard_step = 1; st.rerun()
    
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

elif st.session_state.page == "dashboard":
    # 1. Custom CSS to force the dark industrial look
    st.markdown("""
        <style>
        .dash-bg { background-color: #0E1117; color: white; font-family: sans-serif; }
        .panel { background-color: #1C1F24; border-radius: 8px; padding: 15px; margin-bottom: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); border: 1px solid #2A2D34; }
        .panel-title { font-size: 12px; color: #888; font-weight: bold; letter-spacing: 1px; margin-bottom: 10px; text-transform: uppercase; }
        .value-green { color: #2ECC71; font-size: 36px; font-weight: bold; line-height: 1; margin: 5px 0; }
        .value-grey { color: #888; font-size: 36px; font-weight: bold; line-height: 1; margin: 5px 0; }
        .status-light-run { height: 20px; width: 20px; background-color: #2ECC71; border-radius: 50%; display: inline-block; box-shadow: 0 0 10px #2ECC71; }
        .status-light-stop { height: 20px; width: 20px; background-color: #555; border-radius: 50%; display: inline-block; }
        .header-title { font-size: 18px; font-weight: bold; letter-spacing: 1px; margin-bottom: 15px; text-transform: uppercase; }
        </style>
    """, unsafe_allow_html=True)

    # 2. Main Header
    st.markdown(f"""
        <div class="header-title">PUMP ARCHITECT GEM: ENDURANCE TEST DASHBOARD <span style="color:#888; font-size:14px; font-weight:normal;">| PROJECT: {st.session_state.get('current_project', 'Unknown')}</span></div>
    """, unsafe_allow_html=True)

    # 3. Top Row (Progress Bars)
    st.markdown("""
        <div style="display: flex; gap: 20px; margin-bottom: 20px;">
            <div class="panel" style="flex: 1; margin-bottom: 0;">
                <div style="display: flex; justify-content: space-between;"><span class="panel-title">TOTAL MISSION OBJECTIVES:</span> <span style="font-weight:bold;">2,450 / 3,000 hrs</span></div>
                <div style="background: #333; height: 10px; border-radius: 5px; margin-top: 5px;"><div style="background: #EEDD82; width: 81%; height: 100%; border-radius: 5px;"></div></div>
            </div>
            <div class="panel" style="flex: 1; margin-bottom: 0;">
                <div style="display: flex; justify-content: space-between;"><span class="panel-title">TOTAL CYCLES</span> <span style="font-weight:bold;">8,912 / 11,000 cycles</span></div>
                <div style="background: #333; height: 10px; border-radius: 5px; margin-top: 5px;"><div style="background: #ddd; width: 81%; height: 100%; border-radius: 5px;"></div></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # 4. Main Grid Split (Left: Watchdog, Right: Pumps)
    col_left, col_right = st.columns([1.2, 3])

    with col_left:
        st.markdown("<div class='header-title' style='font-size: 14px;'>SYSTEM WATCHDOG</div>", unsafe_allow_html=True)
        
        # ESP32
        st.markdown("""
            <div class="panel">
                <div class="panel-title">ESP32 INTERNAL TEMP</div>
                <div style="text-align: center; color: #F39C12; font-size: 32px; font-weight: bold;">38°C</div>
                <div style="text-align: right; color: #F39C12; font-size: 10px; margin-top: 5px;">AMBER</div>
                <div style="border-bottom: 2px solid #F39C12; margin-top: 5px; margin-bottom: 5px;"></div>
                <div style="display: flex; justify-content: space-between; font-size: 10px; color: #888;"><span>AMBER WARNING THRESHOLD</span><span>38°C</span></div>
            </div>
        """, unsafe_allow_html=True)
        
        # MAX6675
        st.markdown("""
            <div class="panel">
                <div class="panel-title">MAX6675/TYPE-K</div>
                <div style="display: flex; align-items: center; justify-content: center; gap: 15px;">
                    <span style="color: #2ECC71; font-size: 32px; font-weight: bold;">OK</span>
                    <div style="text-align: left;"><span style="color:#888; font-size:10px;">SENSOR</span><br><span style="font-size:24px; font-weight:bold;">26.5°C</span></div>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        # HIOKI
        st.markdown("""
            <div class="panel">
                <div class="panel-title">HIOKI INTERFACE</div>
                <div style="text-align: center; color: #E74C3C; font-size: 24px; font-weight: bold; display: flex; align-items: center; justify-content: center; gap: 10px;">
                    <span style="font-size: 30px;">🚫</span> OFFLINE
                </div>
            </div>
        """, unsafe_allow_html=True)

        if st.button("⬅ Exit Dashboard", use_container_width=True):
            st.session_state.page = "home"
            st.rerun()

    with col_right:
        # Loop through actual saved pumps
        if "active_pumps_df" in st.session_state and not st.session_state.active_pumps_df.empty:
            pumps = st.session_state.active_pumps_df["Pump ID"].tolist()
            
            # Create a 3-column grid
            cols = st.columns(3)
            for i, p_id in enumerate(pumps):
                # Alternate statuses just to make the UI look alive (Running vs Stopped)
                is_running = i % 2 == 0 
                status_color = "value-green" if is_running else "value-grey"
                light_class = "status-light-run" if is_running else "status-light-stop"
                current_val = "1.25A" if is_running else "0.00A"
                svg_color = "#2ECC71" if is_running else "#555"
                
                # SVG Sparkline simulation
                sparkline = f"""<svg viewBox="0 0 100 20" style="width:100%; height:30px; margin-top:10px;"><polyline fill="none" stroke="{svg_color}" stroke-width="2" points="0,15 10,12 20,16 30,10 40,14 50,8 60,12 70,5 80,10 90,4 100,8" /></svg>"""

                with cols[i % 3]:
                    st.markdown(f"""
                        <div class="panel">
                            <div class="panel-title">{p_id}</div>
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div>
                                    <div style="font-size: 10px; color: #888;">LIVE CURRENT (A)</div>
                                    <div class="{status_color}">{current_val}</div>
                                </div>
                                <div style="text-align: center;">
                                    <div style="font-size: 10px; color: #888; margin-bottom: 5px;">STATUS LIGHT</div>
                                    <div class="{light_class}"></div>
                                    <div style="font-size: 10px; color: {svg_color}; font-weight: bold; margin-top: 3px;">{'RUN' if is_running else 'STOP'}</div>
                                </div>
                            </div>
                            <div style="font-size: 10px; color: #888; margin-top: 10px;">SPARKLINE</div>
                            {sparkline}
                            <div style="display: flex; justify-content: space-between; font-size: 9px; color: #666; margin-top: 5px;"><span>CURRENT</span><span>10 MINUTES</span></div>
                        </div>
                    """, unsafe_allow_html=True)
        else:
            st.warning("No pump data found for this project. Please modify the project to add pumps.")

    render_project_form()