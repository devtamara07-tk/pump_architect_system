
import streamlit as st
import pandas as pd
import sqlite3
import datetime

current_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
    # --- Ensure pumps table schema is correct ---
    try:
        # Try to select from the quoted column name
        c.execute('SELECT "Pump Model" FROM pumps LIMIT 1')
    except Exception:
        # If it fails, drop and recreate the table
        c.execute('DROP TABLE IF EXISTS pumps')
        c.execute('''CREATE TABLE IF NOT EXISTS pumps (
            pump_id TEXT,
            project_id TEXT,
            "Pump Model" TEXT,
            "ISO No." TEXT,
            HP TEXT,
            kW TEXT,
            "Voltage (V)" TEXT,
            "Amp Min" TEXT,
            "Amp Max" TEXT,
            Phase TEXT,
            Hertz TEXT,
            Insulation TEXT
        )''')
    # Fixed Table Schema
    c.execute('''CREATE TABLE IF NOT EXISTS projects (
        project_id TEXT PRIMARY KEY, type TEXT, test_type TEXT, 
        run_mode TEXT, target_val TEXT, created_at DATETIME)''')
    c.execute('''CREATE TABLE IF NOT EXISTS projects (
        project_id TEXT PRIMARY KEY, type TEXT, test_type TEXT,
        run_mode TEXT, target_val TEXT, created_at DATETIME, tanks TEXT)''')



    # --- MIGRATION: Add tanks column if missing ---
    try:
        c.execute("ALTER TABLE projects ADD COLUMN tanks TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists, ignore error

    # --- MIGRATION: Add layout column if missing ---
    try:
        c.execute("ALTER TABLE projects ADD COLUMN layout TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists, ignore error

    # --- MIGRATION: Add hardware/sensor mapping columns if missing ---
    for col in ["hardware_list", "hardware_dfs", "hardware_ds"]:
        try:
            c.execute(f"ALTER TABLE projects ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass

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

        # 4. TARGET VALUE (Number + Unit)
        try:
            saved_target = float(st.session_state.get("target_val", 1.0))
        except:
            saved_target = 1.0
        target_val = st.number_input("Target Value", min_value=1.0, value=saved_target)
        st.session_state.target_val = target_val

        unit_options = ["HR", "Days", "Cycles"]
        saved_unit = st.session_state.get("target_unit", "HR")
        target_unit = st.radio("Unit", unit_options, index=unit_options.index(saved_unit) if saved_unit in unit_options else 0, horizontal=True)
        st.session_state.target_unit = target_unit

        # 5. PROJECT NAME (auto-generated, displayed at bottom)
        project_name = f"{proj_type} {test_type} {run_mode} {target_val} {target_unit}"
        st.session_state.project_name = project_name

        st.markdown(f"<div style='margin-top:20px; color:#0d6efd; font-size:20px; font-weight:bold;'>Project Name: {project_name}</div>", unsafe_allow_html=True)

        st.write("")
        if st.button("Next Step"): st.session_state.wizard_step = 2; st.rerun()

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
            submitted = st.form_submit_button("Confirm Table Entries", use_container_width=True)

            if submitted:
                # Defensive: Check if 'Pump Model' column exists after editing
                if "Pump Model" not in updated_df.columns:
                    st.error("'Pump Model' column is missing. Please do not remove required columns.")
                else:
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

        # --- FORCE REHYDRATE HARDWARE STATE IF RESTORING ---
        if st.session_state.get("_restoring_project", False):
            import json
            conn = sqlite3.connect(DB_FILE)
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

        # --- 1. SYSTEM WATCHDOGS (Editable Table, Multiple per Method) ---
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
                    limits.append({
                        "Pump ID": row.get("Pump ID", "Unknown"),
                        "Max Stator Temp (°C)": max_stator_temp,
                        "Max Current (A)": row.get("Amp Max", 0.0)
                    })
                st.session_state.limits_df = pd.DataFrame(limits)
            if "event_log" not in st.session_state or st.session_state.page == "create" and st.session_state.get("_new_project", False):
                st.session_state.event_log = []

        # --- Editable Watchdogs Table (Multiple per Method, fully dynamic) ---
        wd_df = st.session_state.watchdogs_df.copy() if "watchdogs_df" in st.session_state else pd.DataFrame(columns=["Data Entry Method", "Watchdog Type"])
        col_wd1, col_wd2 = st.columns([3,1])
        with col_wd2:
            if st.button("Add Watchdog Row", use_container_width=True, key="add_wd_row"):
                new_row = {"Data Entry Method": allowed_methods[0], "Watchdog Type": watchdog_types[0]}
                wd_df = pd.concat([wd_df, pd.DataFrame([new_row])], ignore_index=True)
                st.session_state.watchdogs_df = wd_df
                st.experimental_rerun()
        wd_config = {
            "Data Entry Method": st.column_config.SelectboxColumn("Data Entry Method", options=allowed_methods, required=True),
            "Watchdog Type": st.column_config.SelectboxColumn("Watchdog Type", options=watchdog_types, required=True)
        }
        updated_wd = st.data_editor(
            wd_df,
            hide_index=True,
            use_container_width=True,
            column_config=wd_config,
            key="watchdogs_edit",
            num_rows="dynamic"
        )
        st.session_state.watchdogs_df = updated_wd

        # --- Editable Safety Limits Table (add/edit/delete) ---
        lim_df = st.session_state.limits_df.copy() if "limits_df" in st.session_state else pd.DataFrame(columns=["Pump ID", "Max Stator Temp (°C)", "Max Current (A)"])
        col_lim1, col_lim2 = st.columns([3,1])
        with col_lim2:
            if st.button("Add Safety Limit", use_container_width=True, key="add_limit_row"):
                new_row = {"Pump ID": "", "Max Stator Temp (°C)": 130.0, "Max Current (A)": 0.0}
                lim_df = pd.concat([lim_df, pd.DataFrame([new_row])], ignore_index=True)
                st.session_state.limits_df = lim_df
                st.experimental_rerun()
        lim_config = {
            "Pump ID": st.column_config.TextColumn("Pump ID", disabled=False),
            "Max Stator Temp (°C)": st.column_config.NumberColumn(required=True),
            "Max Current (A)": st.column_config.NumberColumn(required=True)
        }
        updated_lim = st.data_editor(
            lim_df,
            hide_index=True,
            use_container_width=True,
            column_config=lim_config,
            key="limits_edit",
            num_rows="dynamic"
        )
        st.session_state.limits_df = updated_lim

        st.divider()

        # --- 3. EVENT ALERT LOG (Dynamic, Scrollable) ---
        st.markdown("<p style='color: white; font-size: 18px; font-weight: bold;'>2. Event Alert Log</p>", unsafe_allow_html=True)
        if "event_log" not in st.session_state:
            st.session_state.event_log = []
        def log_event(msg):
            import datetime
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
        if "layout_df" in st.session_state and "water_tanks" in st.session_state:
            layout_df = st.session_state.layout_df
            tanks = st.session_state.water_tanks
            for tank in tanks:
                st.markdown(f"<div style='color:#4CAF50; font-size:20px; font-weight:bold; margin-top:16px;'>Water Tank: {tank}</div>", unsafe_allow_html=True)
                tank_pumps = layout_df[layout_df["Assigned Tank"] == tank]["Pump ID"].tolist()
                rows = [tank_pumps[i:i+3] for i in range(0, len(tank_pumps), 3)]
                for row in rows:
                    cols = st.columns(3)
                    for i, p_id in enumerate(row):
                        with cols[i]:
                            # Example: show formulas and running time (placeholder)
                            st.markdown(f"""
                                <div style='border: 1px solid #444; padding: 10px; margin-bottom: 10px; border-radius: 5px; background: #1C1F24; text-align: center;'>
                                    <p style='margin:0; font-weight: bold; color: #3498DB; font-size: 18px;'>{p_id}</p>
                                    <p style='margin:0; font-size: 14px; color: #2ecc71; font-weight: bold;'>0.00A &nbsp;&nbsp; 🟢 RUN</p>
                                    <p style='margin:0; font-size: 12px; color: #888;'>Temp: 00.0°C | Rise: 00.0°C</p>
                                    <p style='margin:0; font-size: 12px; color: #aaa;'>Formula: [calculated]</p>
                                    <p style='margin:0; font-size: 12px; color: #aaa;'>Running Time: 0 HR / 0 Cycles</p>
                                </div>
                            """, unsafe_allow_html=True)
                if not tank_pumps:
                    st.info("No pumps assigned to this tank.")
        else:
            st.warning("No tank or pump layout found. Please complete previous steps.")

        st.divider()

        # --- 5. FINAL SAVE LOGIC ---
        st.markdown("<p style='color: white; font-size: 18px; font-weight: bold;'>4. Finalize & Save</p>", unsafe_allow_html=True)
        c1, c2 = st.columns([1, 4])
        if c1.button("Back", key="back_s6"): st.session_state.wizard_step = 5; st.rerun()
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
            
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            
            try:
                run_mode = st.session_state.get("run_mode", "Continuous")
                target_val = str(st.session_state.get("target_val", "0"))

                # --- CLEAN SAVE TO DATABASE ---
                # 6 values in exact order: ID, Type, Test Type, Run Mode, Target, Date

                tanks_str = "||".join(st.session_state.get("water_tanks", ["Water Tank 1"]))
                layout_json = None
                if "layout_df" in st.session_state and isinstance(st.session_state.layout_df, pd.DataFrame):
                    layout_json = st.session_state.layout_df.to_json()
                # Upsert with layout

                # --- NEW: Save hardware_list, all df_/ds_ DataFrames as JSON ---
                hardware_list = st.session_state.get("hardware_list", [])
                hardware_dfs = {}
                hardware_ds = {}
                for k in st.session_state.keys():
                    if k.startswith("df_") and isinstance(st.session_state[k], pd.DataFrame):
                        hardware_dfs[k] = st.session_state[k].to_json()
                    if k.startswith("ds_") and isinstance(st.session_state[k], list):
                        hardware_ds[k] = st.session_state[k]
                import json
                hardware_dfs_json = json.dumps(hardware_dfs)
                hardware_ds_json = json.dumps(hardware_ds)
                hardware_list_json = json.dumps(hardware_list)

                c.execute("INSERT OR REPLACE INTO projects (project_id, type, test_type, run_mode, target_val, created_at, tanks, layout, hardware_list, hardware_dfs, hardware_ds) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (project_name, proj_type, test_type, run_mode, target_val, timestamp, tanks_str, layout_json, hardware_list_json, hardware_dfs_json, hardware_ds_json))

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
                st.success(f"Project '{project_name}' Successfully Saved!")
                
                # Cleanup and Go Home
                for k in ["specs_df", "wizard_step", "proj_type", "test_type", "layout_df", "watchdogs_df"]: 
                    if k in st.session_state: del st.session_state[k]
                st.session_state.page = "home"
                st.rerun()

            except Exception as e:
                st.error(f"Database Error: {e}")
            finally:
                conn.close()

# --- HELPER FUNCTIONS ---
def handle_open_project(project_id):
    conn = sqlite3.connect(DB_FILE)
    # 1. Load the core project info
    proj_row = conn.execute("SELECT project_id, type, test_type, run_mode, target_val, tanks FROM projects WHERE project_id = ?", (project_id,)).fetchone()
    
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
    # Fetch all columns for project
    proj_row = conn.execute("SELECT project_id, type, test_type, run_mode, target_val, tanks, layout, hardware_list, hardware_dfs, hardware_ds FROM projects WHERE project_id = ?", (project_id,)).fetchone()


    if proj_row:
        # --- Step 0: Clear previous session state for tables ---
        for k in ["specs_df", "layout_df"]:
            if k in st.session_state:
                del st.session_state[k]
        # Also clear all hardware config DataFrames and Data Source lists
        extra_keys = [k for k in st.session_state.keys() if k.startswith("df_") or k.startswith("ds_")]
        for k in extra_keys:
            del st.session_state[k]

        # --- Step 1: Restore project metadata ---
        st.session_state.project_name = proj_row[0]
        st.session_state.proj_type = proj_row[1]
        st.session_state.test_type = proj_row[2]
        st.session_state.run_mode = proj_row[3]
        st.session_state.target_val = proj_row[4]
        st.session_state.current_project = project_id

        # --- Step 3: Restore tanks ---
        if proj_row[5]:
            st.session_state.water_tanks = proj_row[5].split("||")
        else:
            st.session_state.water_tanks = ["Water Tank 1"]

        # --- Step 3: Restore layout_df ---
        if proj_row[6]:
            try:
                st.session_state.layout_df = pd.read_json(proj_row[6])
            except Exception as e:
                st.warning(f"Could not restore installation layout: {e}. Starting with blank layout.")
                st.session_state.layout_df = pd.DataFrame()
        else:
            st.session_state.layout_df = pd.DataFrame()

        # --- Step 4: Restore hardware mapping DataFrames and lists ---
        import json
        # hardware_list
        if len(proj_row) > 7 and proj_row[7]:
            try:
                st.session_state.hardware_list = json.loads(proj_row[7])
            except Exception as e:
                st.session_state.hardware_list = []
        else:
            st.session_state.hardware_list = []
        # hardware_dfs
        if len(proj_row) > 8 and proj_row[8]:
            try:
                dfs = json.loads(proj_row[8])
                for k, v in dfs.items():
                    st.session_state[k] = pd.read_json(v)
            except Exception as e:
                pass
        # hardware_ds
        if len(proj_row) > 9 and proj_row[9]:
            try:
                dss = json.loads(proj_row[9])
                for k, v in dss.items():
                    st.session_state[k] = v
            except Exception as e:
                pass

        # --- Step 2: Restore Pump Specification Table ---
        try:
            query = "SELECT * FROM pumps WHERE project_id = ?"
            pumps_df = pd.read_sql_query(query, conn, params=(project_id,))
            if not pumps_df.empty:
                keep_cols = ["Pump Model", "Pump ID", "ISO No.", "HP", "kW", "Voltage (V)", "Amp Min", "Amp Max", "Phase", "Hertz", "Insulation"]
                # Ensure Pump ID column exists
                if "pump_id" in pumps_df.columns:
                    pumps_df = pumps_df.rename(columns={"pump_id": "Pump ID"})
                # Fill missing columns with default values
                for col in keep_cols:
                    if col not in pumps_df.columns:
                        pumps_df[col] = "" if col not in ["HP", "kW", "Amp Min", "Amp Max", "Phase"] else 0
                st.session_state.specs_df = pumps_df[keep_cols]
        except Exception as e:
            st.warning(f"Could not restore pump specification table: {e}")

        # --- Step 4: Restore hardware mapping DataFrames (if present) ---
        # (REMOVED: Deletion of df_*/ds_* keys after restore, as this wipes out restored state)

        # --- Step 5: Restore formulas and variable mapping (if present) ---
        try:
            # Example: restore formulas_df, var_mapping_df, etc. (pseudo-code)
            # formulas_row = conn.execute("SELECT formulas FROM projects WHERE project_id = ?", (project_id,)).fetchone()
            # if formulas_row and formulas_row[0]:
            #     st.session_state.formulas_df = pd.read_json(formulas_row[0])
            # varmap_row = conn.execute("SELECT var_mapping FROM projects WHERE project_id = ?", (project_id,)).fetchone()
            # if varmap_row and varmap_row[0]:
            #     st.session_state.var_mapping_df = pd.read_json(varmap_row[0])
            pass
        except Exception as e:
            st.warning(f"Could not restore formulas or variable mapping: {e}")

        # --- Set wizard state and rerun ---
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
        # Clear all user input fields and Step 2 table
        for k in [
            "project_name", "proj_type", "test_type", "run_mode", "target_val", "target_unit",
            "specs_df", "layout_df", "water_tanks", "hardware_list", "var_mapping_df", "formulas_df",
            "watchdogs_df", "limits_df", "event_log", "wizard_step", "current_project"
        ]:
            if k in st.session_state:
                del st.session_state[k]
        # Also clear all hardware config DataFrames and Data Source lists
        extra_keys = [k for k in st.session_state.keys() if k.startswith("df_") or k.startswith("ds_")]
        for k in extra_keys:
            del st.session_state[k]
        st.session_state.page = "create"
        st.session_state.wizard_step = 1
        st.rerun()
    
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
        .header-title { font-size: 22px; font-weight: bold; letter-spacing: 1px; color: #3498DB; text-transform: uppercase; margin-bottom: 5px; }
        .event-log-text { font-size: 13px; color: #AAA; font-family: monospace; margin-bottom: 4px; }
        .event-alert { color: #E74C3C; font-weight: bold; }
        </style>
    """, unsafe_allow_html=True)

    # 2. Fetch REAL Database Info for this Project
    project_name = st.session_state.get('current_project', 'UNKNOWN PROJECT')
    
    conn = sqlite3.connect(DB_FILE)
    proj_row = conn.execute("SELECT run_mode, target_val, test_type FROM projects WHERE project_id = ?", (project_name,)).fetchone()
    conn.close()
    
    # Extract data or default if missing
    run_mode = proj_row[0] if proj_row and proj_row[0] else "Continuous"
    target_val = proj_row[1] if proj_row and proj_row[1] else "0"
    test_type = proj_row[2] if proj_row and proj_row[2] else ""

    # Main Header
    st.markdown(f"""
        <div style="background:#1C1F24; padding:20px; border-radius:10px; border-left: 5px solid #3498DB; margin-bottom:20px;">
            <div class="header-title">PUMP ARCHITECT SYSTEM</div>
            <div style="color:white; font-size: 28px; font-weight: bold; letter-spacing: 1px;">PROJECT: {project_name}</div>
        </div>
    """, unsafe_allow_html=True)

    # 3. Dynamic Progress Bar (Uses real target values from the database)
    is_cycle_test = "Cycle" in test_type or "Intermittent" in test_type or "Cycle" in run_mode
    
    if is_cycle_test:
        bar_title = "TOTAL MISSION CYCLES"
        bar_value = f"0 / {target_val} cycles"
        bar_color = "#3498DB" 
    else:
        bar_title = "TOTAL MISSION RUN TIME"
        bar_value = f"0 / {target_val} hrs"
        bar_color = "#EEDD82" 

    # Progress bar starts at 0% because the test hasn't physically run yet
    st.markdown(f"""
        <div class="panel" style="margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between;"><span class="panel-title">{bar_title}</span> <span style="font-weight:bold; color:white; font-size:16px;">{bar_value}</span></div>
            <div style="background: #333; height: 12px; border-radius: 6px; margin-top: 8px;"><div style="background: {bar_color}; width: 0%; height: 100%; border-radius: 6px;"></div></div>
        </div>
    """, unsafe_allow_html=True)

    # 4. Main Grid Split (Left: Watchdog & Actions, Right: Pumps)
    col_left, col_right = st.columns([1.2, 3])

    with col_left:
        st.markdown("<div class='header-title' style='font-size: 18px; color:white;'>SYSTEM WATCHDOG</div>", unsafe_allow_html=True)
        
        # --- DATA ENTRY STATUS (Real configuration from Step 4) ---
        man_status = "ON" if st.session_state.get("use_manual", True) else "OFF"
        man_color = "#2ECC71" if man_status == "ON" else "#555"
        
        voice_status = "ON" if st.session_state.get("use_voice", False) else "OFF"
        voice_color = "#2ECC71" if voice_status == "ON" else "#555"
        
        esp_status = "SYSTEM ACTIVE" if st.session_state.get("use_ocr", False) else "STANDBY"
        esp_color = "#3498DB" if esp_status == "SYSTEM ACTIVE" else "#555"

        st.markdown(f"""
            <div class="panel">
                <div class="panel-title">DATA ENTRY MODULES</div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                    <span style="color:white; font-size:14px;">Manual Input</span>
                    <span style="color:{man_color}; font-weight:bold;">{man_status}</span>
                </div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                    <span style="color:white; font-size:14px;">Voice Recording</span>
                    <span style="color:{voice_color}; font-weight:bold;">{voice_status}</span>
                </div>
                <div style="display: flex; justify-content: space-between; border-top: 1px solid #333; padding-top: 8px;">
                    <span style="color:white; font-size:14px;">ESP32 CAM</span>
                    <span style="color:{esp_color}; font-weight:bold;">{esp_status}</span>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        # --- EVENT ALARM LOG ---
        st.markdown("""
            <div class="panel" style="height: 200px; overflow-y: auto;">
                <div class="panel-title">EVENT ALARM LOG</div>
                <div class="event-log-text">SYSTEM IN STANDBY</div>
                <div class="event-log-text">AWAITING TEST INITIATION...</div>
            </div>
        """, unsafe_allow_html=True)

        st.divider()

        # --- ACTION BUTTONS (Icons Removed) ---
        st.button("Add New Record", use_container_width=True, key="btn_add_record")
        st.button("Add New Maintenance", use_container_width=True, key="btn_add_maint")
        st.button("Print Report", use_container_width=True, key="btn_print_report")
        
        st.write("")
        if st.button("Exit Dashboard", use_container_width=True, type="primary"):
            st.session_state.page = "home"
            st.rerun()

    with col_right:
        # Pull actual saved pumps from the Database via active_pumps_df
        if "active_pumps_df" in st.session_state and not st.session_state.active_pumps_df.empty:
            cols = st.columns(3)
            
            for i, row in st.session_state.active_pumps_df.iterrows():
                # Extract real data from your dataframe (safely checking both potential column names)
                p_id = row.get("pump_id", row.get("Pump ID", "Unknown"))
                amp_max = row.get("amp_max", row.get("Amp Max", 0.0))
                
                # Real Case Status: Since the test hasn't started, everything is at zero/standby
                status_color = "value-grey"
                light_class = "status-light-stop"
                current_val = "0.00A"
                svg_color = "#555"
                
                # Flat sparkline indicating 0 current flow
                sparkline = f"""<svg viewBox="0 0 100 20" style="width:100%; height:30px; margin-top:10px;"><polyline fill="none" stroke="{svg_color}" stroke-width="2" points="0,15 10,15 20,15 30,15 40,15 50,15 60,15 70,15 80,15 90,15 100,15" /></svg>"""

                with cols[i % 3]:
                    st.markdown(f"""
                        <div class="panel">
                            <div class="panel-title">{p_id}</div>
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div>
                                    <div style="font-size: 10px; color: #888;">LIVE CURRENT (MAX: {amp_max}A)</div>
                                    <div class="{status_color}">{current_val}</div>
                                </div>
                                <div style="text-align: center;">
                                    <div style="font-size: 10px; color: #888; margin-bottom: 5px;">STATUS LIGHT</div>
                                    <div class="{light_class}"></div>
                                    <div style="font-size: 10px; color: {svg_color}; font-weight: bold; margin-top: 3px;">STANDBY</div>
                                </div>
                            </div>
                            <div style="font-size: 10px; color: #888; margin-top: 10px;">SPARKLINE</div>
                            {sparkline}
                            <div style="display: flex; justify-content: space-between; font-size: 9px; color: #666; margin-top: 5px;"><span>CURRENT</span><span>10 MINUTES</span></div>
                        </div>
                    """, unsafe_allow_html=True)
        else:
            st.warning("No pump data found for this project. Please modify the project to add pumps.")

# --- FIX: Ensure the wizard only renders on the Create page ---
elif st.session_state.page == "create":
    render_project_form()