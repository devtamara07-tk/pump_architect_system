import streamlit as st
import pandas as pd
import sqlite3
import datetime
import base64
import time
import os

def get_base64_image(image_path):
	try:
		with open(image_path, "rb") as img_file:
			return base64.b64encode(img_file.read()).decode()
	except:
		return ""

# --- 1. DATABASE SETUP ---
DB_FILE = "architect_system.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS projects 
                 (project_id TEXT PRIMARY KEY, type TEXT, test_type TEXT, created_at DATETIME)''')
    c.execute('''CREATE TABLE IF NOT EXISTS pumps 
                 (pump_id TEXT, project_id TEXT, model TEXT, iso_no TEXT, hp REAL, 
                  kw REAL, voltage TEXT, amp TEXT, phase INTEGER, hertz TEXT, insulation TEXT, 
                  tank_name TEXT, PRIMARY KEY (pump_id, project_id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS status_logs 
                 (log_id INTEGER PRIMARY KEY AUTOINCREMENT, pump_id TEXT, project_id TEXT, 
                  status TEXT, start_ts DATETIME, end_ts DATETIME)''')
    c.execute('''CREATE TABLE IF NOT EXISTS test_targets 
                 (project_id TEXT PRIMARY KEY, run_type TEXT, test_category TEXT, 
                  duration REAL, duration_unit TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS sensors 
                 (sensor_id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT, 
                  param_type TEXT, name TEXT, location TEXT, hardware TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS hardware_setup 
                 (setup_id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT, 
                  sensor_id INTEGER, channel TEXT, record_method TEXT, 
                  allow_ai BOOLEAN, allow_manual BOOLEAN)''')
    conn.commit()
    conn.close()

# --- 2. HELPER FUNCTIONS ---
def get_projects():
	conn = sqlite3.connect(DB_FILE)
	df = pd.read_sql("SELECT * FROM projects", conn)
	conn.close()
	return df

# Define the standard column configuration for both Create and Modify tables
def get_column_config():
	return {
		"Pump ID": st.column_config.TextColumn("Pump ID", disabled=True, width="small"),
		"Pump Model": st.column_config.TextColumn("Pump Model", width="medium"),
		"ISO No.": st.column_config.TextColumn("ISO No.", width="medium"),
		"HP": st.column_config.NumberColumn("HP", width="small"),
		"kW": st.column_config.NumberColumn("kW", width="small"),
		"Voltage (V)": st.column_config.TextColumn("Voltage (V)", width="small"),
		"Amp (A)": st.column_config.TextColumn("Amp (A)", width="small"),
		"Phase": st.column_config.NumberColumn("Phase", width="small"),
		"Hertz": st.column_config.SelectboxColumn("Hertz", options=["50", "60"], width="small"),
		"Insulation": st.column_config.TextColumn("Insulation", width="small")
	}

# --- 3. UI WIZARD: CREATE PROJECT ---
def render_create_project():
    st.header("🛠️ Create a New Project")
    col1, col2 = st.columns(2)
    with col1:
        p_type = st.radio("1. Pump Type", ["Centrifugal", "Submersible"])
    with col2:
        t_type = st.text_input("2. Test Type", placeholder="e.g., Endurance Test")
    project_name = f"{p_type}_{t_type}" if t_type else p_type
    st.subheader(f"Project Name: **{project_name}**")
    st.divider()
    st.write("### 3. Pump Specs")
    if "specs_df" not in st.session_state:
        st.session_state.specs_df = pd.DataFrame(columns=["Pump ID", "Pump Model", "ISO No.", "HP", "kW", "Voltage (V)", "Amp (A)", "Phase", "Hertz", "Insulation"])
    edited_df = st.data_editor(
        st.session_state.specs_df, 
        num_rows="dynamic", 
        use_container_width=True,
        hide_index=True, 
        column_config=get_column_config(),
        key="create_pump_table"
    )
    new_ids = []
    counter = 1
    for _, row in edited_df.iterrows():
        model = row.get("Pump Model")
        if pd.notna(model) and str(model).strip() != "":
            new_ids.append(f"P-{str(counter).zfill(2)}")
            counter += 1
        else:
            new_ids.append(None)
    current_ids = [str(x) if pd.notna(x) else None for x in edited_df["Pump ID"]]
    if current_ids != new_ids:
        edited_df["Pump ID"] = new_ids
        st.session_state.specs_df = edited_df
        if "create_pump_table" in st.session_state:
            del st.session_state["create_pump_table"]
        st.rerun()
    st.divider()
    st.write("### 4. Installation Layout")
    valid_pump_ids = edited_df["Pump ID"].dropna().tolist()
    if len(valid_pump_ids) > 0:
        if "tanks" not in st.session_state:
            st.session_state.tanks = {"Water Tank 1": []}
        col_t1, col_t2 = st.columns([1, 4])
        with col_t1:
            if st.button("➕ Add Water Tank"):
                new_tank_name = f"Water Tank {len(st.session_state.tanks) + 1}"
                st.session_state.tanks[new_tank_name] = []
                st.rerun()
        unassigned_pumps = set(valid_pump_ids)
        for tank, assigned in st.session_state.tanks.items():
            valid_assigned = [p for p in assigned if p in valid_pump_ids]
            st.session_state.tanks[tank] = valid_assigned
            unassigned_pumps -= set(valid_assigned)
        for tank in st.session_state.tanks.keys():
            with st.container(border=True):
                st.write(f"**{tank}**")
                current_assigned = st.session_state.tanks[tank]
                options = current_assigned + list(unassigned_pumps)
                selected = st.multiselect(f"Assign pumps to {tank}:", options, default=current_assigned, key=tank)
                st.session_state.tanks[tank] = selected
        if st.button("💾 Save Project & Layout", type="primary"):
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            try:
                c.execute("INSERT INTO projects VALUES (?,?,?,?)", 
                          (project_name, p_type, t_type, datetime.datetime.now()))
                for index, row in edited_df.dropna(subset=["Pump ID"]).iterrows():
                    p_id = row["Pump ID"]
                    assigned_tank = next((t for t, p_list in st.session_state.tanks.items() if p_id in p_list), "Unassigned")
                    c.execute("INSERT INTO pumps VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                              (p_id, project_name, row.get("Pump Model", ""), row.get("ISO No.", ""), 
                               row.get("HP", 0), row.get("kW", 0), row.get("Voltage (V)", ""), 
                               row.get("Amp (A)", ""), row.get("Phase", 3), row.get("Hertz", "60"), 
                               row.get("Insulation", "F"), assigned_tank))
                    c.execute("INSERT INTO status_logs (pump_id, project_id, status, start_ts) VALUES (?,?,?,?)",
                              (p_id, project_name, "Running", datetime.datetime.now()))
                conn.commit()
                st.success(f"Project '{project_name}' created successfully!")
                if "specs_df" in st.session_state: del st.session_state.specs_df
                if "tanks" in st.session_state: del st.session_state.tanks
                st.session_state.selected_project = project_name
                st.session_state.page = "test_config"
                st.rerun()
            except sqlite3.IntegrityError:
                st.error("Project with this name already exists. Please change Test Type.")
            finally:
                conn.close()
    else:
        st.info("Add a Pump Model in the specs table to generate a Pump ID and configure the layout.")

def render_modify_project(project_id):
    st.button("⬅️ Cancel & Go Back", on_click=lambda: st.session_state.update(page="home"))
    st.header(f"✏️ Modify Project: {project_id}")
    conn = sqlite3.connect(DB_FILE)
    if "modify_init" not in st.session_state or st.session_state.modify_init != project_id:
        df = pd.read_sql("""SELECT pump_id as 'Pump ID', model as 'Pump Model', 
                            iso_no as 'ISO No.', hp as 'HP', kw as 'kW', 
                            voltage as 'Voltage (V)', amp as 'Amp (A)', phase as 'Phase', hertz as 'Hertz', insulation as 'Insulation', tank_name FROM pumps WHERE project_id=?""", conn, params=(project_id,))
        tanks_dict = {}
        for _, row in df.iterrows():
            tank = row['tank_name']
            if tank and tank != "Unassigned":
                if tank not in tanks_dict:
                    tanks_dict[tank] = []
                tanks_dict[tank].append(row['Pump ID'])
        st.session_state.mod_specs_df = df.drop(columns=['tank_name'])
        st.session_state.mod_tanks = tanks_dict if tanks_dict else {"Water Tank 1": []}
        st.session_state.modify_init = project_id
    st.write("### Pump Specs")
    edited_df = st.data_editor(
        st.session_state.mod_specs_df, 
        num_rows="dynamic", 
        use_container_width=True,
        hide_index=True,  
        column_config=get_column_config(),
        key="mod_pump_table"
    )
    changed = False
    all_pids = [pid for pid in edited_df["Pump ID"].tolist() if pd.notna(pid)]
    highest_id = 0
    for pid in all_pids:
        try:
            num = int(pid.split('-')[1])
            if num > highest_id: highest_id = num
        except: pass
    for idx, row in edited_df.iterrows():
        pid = row.get("Pump ID")
        model = row.get("Pump Model")
        has_model = pd.notna(model) and str(model).strip() != ""
        if (pd.isna(pid) or pid is None) and has_model:
            highest_id += 1
            edited_df.at[idx, "Pump ID"] = f"P-{str(highest_id).zfill(2)}"
            changed = True
    if changed:
        st.session_state.mod_specs_df = edited_df
        if "mod_pump_table" in st.session_state:
            del st.session_state["mod_pump_table"]
        st.rerun()
    st.divider()
    st.write("### Installation Layout")
    valid_pump_ids = edited_df["Pump ID"].dropna().tolist()
    if len(valid_pump_ids) > 0:
        col_t1, col_t2 = st.columns([1, 4])
        with col_t1:
            if st.button("➕ Add Water Tank", key="mod_add_tank"):
                new_tank_name = f"Water Tank {len(st.session_state.mod_tanks) + 1}"
                st.session_state.mod_tanks[new_tank_name] = []
                st.rerun()
        unassigned_pumps = set(valid_pump_ids)
        for tank, assigned in st.session_state.mod_tanks.items():
            valid_assigned = [p for p in assigned if p in valid_pump_ids]
            st.session_state.mod_tanks[tank] = valid_assigned
            unassigned_pumps -= set(valid_assigned)
        for tank in st.session_state.mod_tanks.keys():
            with st.container(border=True):
                st.write(f"**{tank}**")
                current_assigned = st.session_state.mod_tanks[tank]
                options = current_assigned + list(unassigned_pumps)
                selected = st.multiselect(f"Assign pumps to {tank}:", options, default=current_assigned, key=f"mod_{tank}")
                st.session_state.mod_tanks[tank] = selected
        if st.button("💾 Save Modifications", type="primary"):
            c = conn.cursor()
            try:
                existing_pumps = pd.read_sql("SELECT pump_id FROM pumps WHERE project_id=?", conn, params=(project_id,))['pump_id'].tolist()
                c.execute("DELETE FROM pumps WHERE project_id=?", (project_id,))
                for index, row in edited_df.dropna(subset=["Pump ID"]).iterrows():
                    p_id = row["Pump ID"]
                    assigned_tank = next((t for t, p_list in st.session_state.mod_tanks.items() if p_id in p_list), "Unassigned")
                    c.execute("INSERT INTO pumps VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                              (p_id, project_id, row.get("Pump Model", ""), row.get("ISO No.", ""), 
                               row.get("HP", 0), row.get("kW", 0), row.get("Voltage (V)", ""), 
                               row.get("Amp (A)", ""), row.get("Phase", 3), row.get("Hertz", "60"), 
                               row.get("Insulation", "F"), assigned_tank))
                    if p_id not in existing_pumps:
                        c.execute("INSERT INTO status_logs (pump_id, project_id, status, start_ts) VALUES (?,?,?,?)",
                                  (p_id, project_id, "Running", datetime.datetime.now()))
                conn.commit()
                st.success(f"Project '{project_id}' updated successfully!")
                if "mod_specs_df" in st.session_state: del st.session_state.mod_specs_df
                if "modify_init" in st.session_state: del st.session_state.modify_init
                st.session_state.page = "home"
                st.rerun()
            except Exception as e:
                st.error(f"Error saving modifications: {e}")
            finally:
                conn.close()

def render_test_config(project_id):
    st.button("⬅️ Back to Dashboard", on_click=lambda: st.session_state.update(page="dashboard"))
    st.header(f"⚙️ Test Specifics & Hardware Setup: {project_id}")
    conn = sqlite3.connect(DB_FILE)
    pumps_df = pd.read_sql("SELECT pump_id, tank_name FROM pumps WHERE project_id=?", conn, params=(project_id,))
    locations = pumps_df['pump_id'].tolist() + [t for t in pumps_df['tank_name'].unique() if t != "Unassigned"] + ["Ambient"]
    st.markdown("<h3 style='color: #0055A4;'>1. Test Target</h3>", unsafe_allow_html=True)
    with st.container(border=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            run_type = st.radio("Run Type", ["Continuous Run", "Intermittent Run"])
        with col2:
            if run_type == "Continuous Run":
                test_cat = st.selectbox("Test Category", ["Life Cycle Test", "Endurance Test", "Reliability Test", "Other"])
            else:
                test_cat = st.selectbox("Test Category", ["On/Off Cycles", "Custom Cycles"])
        with col3:
            if run_type == "Continuous Run":
                duration = st.number_input("Duration Target", min_value=1.0, value=3000.0)
                unit = st.selectbox("Unit", ["Hours", "Days"])
            else:
                duration = st.number_input("Target Cycle Count", min_value=1, value=10000)
                unit = "Cycles"
    st.markdown("<h3 style='color: #0055A4;'>2. Parameters & Hardware Selection</h3>", unsafe_allow_html=True)
    st.write("Select the parameters you are recording for this test:")
    use_temp = st.checkbox("🌡️ Temperature")
    use_volt = st.checkbox("⚡ Voltage / Current")
    use_count = st.checkbox("🔄 Counter")
    if use_temp:
        st.info("💡 **Tip:** To assign multiple sensors to the same pump, simply type in the empty bottom row and select the same Location again.")
        st.subheader("Temperature Sensors")
        if "temp_df" not in st.session_state:
            st.session_state.temp_df = pd.DataFrame(columns=["Name (e.g., Stator Temp)", "Location", "Hardware"])
        temp_config = {
            "Location": st.column_config.SelectboxColumn("Location", options=locations, required=True),
            "Hardware": st.column_config.SelectboxColumn("Hardware", options=["HIOKI Thermometer", "General Thermometer", "Other"], required=True)
        }
        st.session_state.temp_df = st.data_editor(
            st.session_state.temp_df, 
            column_config=temp_config, 
            num_rows="dynamic", 
            key="temp_edit", 
            hide_index=True, 
            use_container_width=True
        )
    if use_volt:
        st.subheader("Voltage/Current Sensors")
        if "volt_df" not in st.session_state:
            st.session_state.volt_df = pd.DataFrame(columns=["Name", "Location", "Hardware"])
        volt_config = {
            "Location": st.column_config.SelectboxColumn("Location", options=locations, required=True),
            "Hardware": st.column_config.SelectboxColumn("Hardware", options=["HIOKI Power Meter", "Multimeter", "Other"], required=True)
        }
        st.session_state.volt_df = st.data_editor(
            st.session_state.volt_df, 
            column_config=volt_config, 
            num_rows="dynamic", 
            key="volt_edit", 
            hide_index=True, 
            use_container_width=True
        )
    st.markdown("<h3 style='color: #0055A4;'>3. Hardware Installation & Recording Method</h3>", unsafe_allow_html=True)
    with st.container(border=True):
        st.write("Configure channels and methods for your assigned sensors:")
        all_sensors = []
        if use_temp and not st.session_state.temp_df.empty:
            all_sensors.extend([{"type": "Temp", **row} for _, row in st.session_state.temp_df.iterrows() if pd.notna(row["Name (e.g., Stator Temp)"])])
        if use_volt and not st.session_state.volt_df.empty:
            all_sensors.extend([{"type": "Volt", **row} for _, row in st.session_state.volt_df.iterrows() if pd.notna(row["Name"])])
        if not all_sensors:
            st.info("Please add at least one sensor in Step 2 to configure installation.")
        else:
            for idx, sensor in enumerate(all_sensors):
                s_name = sensor.get("Name (e.g., Stator Temp)") or sensor.get("Name")
                s_loc = sensor.get("Location")
                s_hw = sensor.get("Hardware")
                with st.expander(f"⚙️ {s_name} at {s_loc} ({s_hw})", expanded=True):
                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        if "HIOKI Thermometer" in s_hw:
                            ch_options = [f"CH {i}" for i in range(1, 16)]
                        elif "HIOKI Power Meter" in s_hw:
                            ch_options = ["U1", "U2", "U3", "I1", "I2", "I3"]
                        else:
                            ch_options = ["N/A", "Display 1", "Display 2"]
                        st.selectbox("Hardware Channel", ch_options, key=f"ch_{idx}")
                    with col_b:
                        st.selectbox("Data Calculation", ["Exact Measurement", "Max Measurement", "Average Measurement"], key=f"calc_{idx}")
                    with col_c:
                        st.write("Recording Integrations:")
                        st.checkbox("Allow AI/Camera Integration", value=True, key=f"ai_{idx}")
                        st.checkbox("Allow Manual Input", value=True, key=f"man_{idx}")
        if st.button("💾 Save Test Configuration", type="primary", use_container_width=True):
            c = conn.cursor()
            try:
                c.execute("DELETE FROM test_targets WHERE project_id=?", (project_id,))
                c.execute("INSERT INTO test_targets VALUES (?,?,?,?,?)", 
                          (project_id, run_type, test_cat, duration, unit))
                c.execute("DELETE FROM sensors WHERE project_id=?", (project_id,))
                c.execute("DELETE FROM hardware_setup WHERE project_id=?", (project_id,))
                for idx, sensor in enumerate(all_sensors):
                    s_type = sensor.get("type")
                    s_name = sensor.get("Name (e.g., Stator Temp)") or sensor.get("Name")
                    s_loc = sensor.get("Location")
                    s_hw = sensor.get("Hardware")
                    c.execute("INSERT INTO sensors (project_id, param_type, name, location, hardware) VALUES (?,?,?,?,?)",
                              (project_id, s_type, s_name, s_loc, s_hw))
                    sensor_id = c.lastrowid
                    ch_val = st.session_state.get(f"ch_{idx}", "N/A")
                    calc_val = st.session_state.get(f"calc_{idx}", "Exact Measurement")
                    ai_val = st.session_state.get(f"ai_{idx}", True)
                    man_val = st.session_state.get(f"man_{idx}", True)
                    c.execute("INSERT INTO hardware_setup (project_id, sensor_id, channel, record_method, allow_ai, allow_manual) VALUES (?,?,?,?,?,?)",
                              (project_id, sensor_id, ch_val, calc_val, ai_val, man_val))
                conn.commit()
                st.success("Test Configuration Saved successfully! 🚀")
                time.sleep(1)
                st.session_state.page = "dashboard"
                st.rerun()
            except Exception as e:
                st.error(f"Error saving configuration: {e}")
    conn.close()

def render_dashboard(project_name):
    st.button("⬅️ Back to Projects", on_click=lambda: st.session_state.update(page="home"))
    col1, col2 = st.columns([4, 1])
    with col1:
        st.header(f"📊 Dashboard: {project_name}")
    with col2:
        if st.button("⚙️ Configure Test Plan", use_container_width=True):
            st.session_state.page = "test_config"
            st.rerun()
    conn = sqlite3.connect(DB_FILE)
    proj_df = pd.read_sql("SELECT type FROM projects WHERE project_id=?", conn, params=(project_name,))
    project_type = proj_df['type'].iloc[0] if not proj_df.empty else "Centrifugal"
    icon_filename = "pump_icon.png" if project_type == "Centrifugal" else "pump_icon2.png"
    dynamic_icon_base64 = get_base64_image(icon_filename)
    pumps_df = pd.read_sql("SELECT * FROM pumps WHERE project_id=?", conn, params=(project_name,))
    if pumps_df.empty:
        st.warning("No pumps found for this project.")
        return
    tanks = pumps_df['tank_name'].unique()
    for tank in tanks:
        st.markdown(f"### 🟦 {tank}")
        tank_pumps = pumps_df[pumps_df['tank_name'] == tank]
        with st.container(border=True):
            cols = st.columns(len(tank_pumps) if len(tank_pumps) > 0 else 1)
            for idx, (_, row) in enumerate(tank_pumps.iterrows()):
                p_id = row['pump_id']
                with cols[idx]:
                    status_df = pd.read_sql("SELECT * FROM status_logs WHERE pump_id=? AND project_id=? ORDER BY log_id DESC LIMIT 1", 
                                            conn, params=(p_id, project_name))
                    current_status = status_df['status'].iloc[0] if not status_df.empty else "Unknown"
                    m_start = status_df['start_ts'].iloc[0] if current_status == "Downtime" and not status_df.empty else "-"
                    img_html = f"<img src='data:image/png;base64,{dynamic_icon_base64}' width='60' style='margin-bottom: 10px;'>" if dynamic_icon_base64 else "🚰"
                    if current_status == "Running":
                        border_color = "#0085CA"
                    elif current_status == "Stop":
                        border_color = "#E4002B"
                    else:
                        border_color = "#FF8200"
                    st.markdown(f"""
                    <div style='text-align: center; padding: 15px; border: 3px solid {border_color}; border-radius: 8px; background-color: #002F6C; color: white; box-shadow: 2px 4px 10px rgba(0, 47, 108, 0.2);'>
                        {img_html}
                        <h3 style='color: white; margin-top: 0px; font-weight: bold;'>{p_id}</h3>
                        <p style='font-size: 13px; color: #E0E7ED; margin-bottom: 0px;'>
                            {row['model']}<br>
                            <span style='color: #FF8200;'>{row['hp']}HP</span> ({row['hertz']}Hz)
                        </p>
                    </div>
                    """, unsafe_allow_html=True)
                    st.caption(f"Status: **{current_status}**")
                    if current_status == "Downtime":
                        st.caption(f"Down since: {m_start[:16]}")
                    with st.expander("Update Status"):
                        new_status = st.selectbox("Change Status", ["Running", "Stop", "Downtime"], key=f"stat_{p_id}")
                        if st.button("Save Status", key=f"btn_{p_id}"):
                            c = conn.cursor()
                            c.execute("UPDATE status_logs SET end_ts=? WHERE pump_id=? AND project_id=? AND end_ts IS NULL",
                                      (datetime.datetime.now(), p_id, project_name))
                            c.execute("INSERT INTO status_logs (pump_id, project_id, status, start_ts) VALUES (?,?,?,?)",
                                      (p_id, project_name, new_status, datetime.datetime.now()))
                            conn.commit()
                            st.rerun()
    conn.close()

# --- 7. MAIN APP ROUTING ---
st.set_page_config(page_title="Pump Test Architect", layout="wide")
init_db()

if "page" not in st.session_state:
    st.session_state.page = "home"

if st.session_state.page == "home":
    icon_centi = get_base64_image("pump_icon.png")
    icon_sub = get_base64_image("pump_icon2.png")
    imgs_html: str = ""
    if icon_centi:
        imgs_html += f"<img src='data:image/png;base64,{icon_centi}' width='55' style='margin-right: 10px;'>"
    if icon_sub:
        imgs_html += f"<img src='data:image/png;base64,{icon_sub}' width='55' style='margin-right: 15px;'>"
    if imgs_html != "":
        st.markdown(f"""
<h1 style='display: flex; align-items: center; color: #002F6C; margin-bottom: 0px;'>
    {imgs_html}
    Pump Test Architect System
</h1>
""", unsafe_allow_html=True)
    else:
        st.title("🚰 Pump Test Architect System")
    st.write("---")
    col_new, col_exist = st.columns([1, 3])
    with col_new:
        if st.button("📝 Create New Project", type="primary", use_container_width=True):
            st.session_state.page = "create"
            st.rerun()
    with col_exist:
        st.subheader("Current Projects")
        projects = get_projects()
        if projects.empty:
            st.info("No active projects. Create one to get started!")
        else:
            grid_cols = st.columns(3)
            for idx, (_, row) in enumerate(projects.iterrows()):
                with grid_cols[idx % 3]:
                    with st.container(border=True):
                            st.write(f"### {row['project_id']}")
                            st.caption(f"Type: {row['type']} | Started: {row['created_at'][:10]}")
                            col_a, col_b, col_c = st.columns(3)
                            with col_a:
                                if st.button("📊 Open", key=f"open_{row['project_id']}", use_container_width=True):
                                    st.session_state.selected_project = row['project_id']
                                    st.session_state.page = "dashboard"
                                    st.rerun()
                            with col_b:
                                if st.button("✏️ Mod", key=f"mod_{row['project_id']}", use_container_width=True):
                                    st.session_state.selected_project = row['project_id']
                                    st.session_state.page = "modify"
                                    st.rerun()
                            with col_c:
                                if st.button("🗑️ Del", key=f"del_{row['project_id']}", use_container_width=True):
                                    conn = sqlite3.connect(DB_FILE)
                                    conn.execute("DELETE FROM projects WHERE project_id=?", (row['project_id'],))
                                    conn.execute("DELETE FROM pumps WHERE project_id=?", (row['project_id'],))
                                    conn.commit()
                                    conn.close()
                                    st.rerun()
    if st.button("⬅️ Cancel & Go Back"):
        if "specs_df" in st.session_state: del st.session_state.specs_df
        if "tanks" in st.session_state: del st.session_state.tanks
        st.session_state.page = "home"
        st.rerun()
    render_create_project()
elif st.session_state.page == "modify":
    render_modify_project(st.session_state.selected_project)
elif st.session_state.page == "test_config":
    render_test_config(st.session_state.selected_project)
elif st.session_state.page == "dashboard":
    render_dashboard(st.session_state.selected_project)