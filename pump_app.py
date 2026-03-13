import streamlit as st
import pandas as pd
import sqlite3
import datetime
import base64
import time
import os

# --- 1. UTILITY FUNCTIONS ---
def get_base64_image(image_path):
    """Loads images from the same folder as the script for the dashboard icons."""
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception:
        return ""

# --- 2. DATABASE SETUP ---
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

def get_projects():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql("SELECT * FROM projects", conn)
    conn.close()
    return df

def get_column_config():
    return {
        "Pump Model": st.column_config.TextColumn("Pump Model", width="medium"),
        "Pump ID": st.column_config.TextColumn("Pump ID", disabled=True, width="small"),
        "ISO No.": st.column_config.TextColumn("ISO No.", width="medium"),
        "HP": st.column_config.NumberColumn("HP", width="small"),
        "kW": st.column_config.NumberColumn("kW", width="small"),
        "Voltage (V)": st.column_config.TextColumn("Voltage (V)", width="small"),
        "Amp (A)": st.column_config.TextColumn("Amp (A)", width="small"),
        "Phase": st.column_config.NumberColumn("Phase", width="small"),
        "Hertz": st.column_config.SelectboxColumn("Hertz", options=["50", "60"], width="small"),
        "Insulation": st.column_config.TextColumn("Insulation", width="small")
    }

# --- 3. PAGE ROUTING & UI ---
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
    
    # --- The requested remark for the users ---
    st.info("💡 **Remark:** Please add a row (Index) and key in the **Pump Model**. The **Pump ID** will be generated automatically.")
    
    # --- New Column Order: Model first, then ID ---
    desired_columns = ["Pump Model", "Pump ID", "ISO No.", "HP", "kW", "Voltage (V)", "Amp (A)", "Phase", "Hertz", "Insulation"]
    
    if "specs_df" not in st.session_state:
        st.session_state.specs_df = pd.DataFrame(columns=desired_columns)
    else:
        # Safety check: if the app remembers the old column order, this forces the new one
        if set(st.session_state.specs_df.columns) == set(desired_columns):
            st.session_state.specs_df = st.session_state.specs_df[desired_columns]
    
    edited_df = st.data_editor(
        st.session_state.specs_df, 
        num_rows="dynamic", 
        use_container_width=True,
        hide_index=False, # --- Index is now unhidden ---
        column_config=get_column_config(),
        key="create_table"
    )
    
    # Logic to auto-generate IDs based on Model entry
    new_ids = []
    counter = 1
    for _, row in edited_df.iterrows():
        if pd.notna(row.get("Pump Model")) and str(row.get("Pump Model")).strip() != "":
            new_ids.append(f"P-{str(counter).zfill(2)}")
            counter += 1
        else:
            new_ids.append(None)
            
    if [str(x) if pd.notna(x) else None for x in edited_df["Pump ID"]] != new_ids:
        edited_df["Pump ID"] = new_ids
        st.session_state.specs_df = edited_df
        if "create_table" in st.session_state: del st.session_state["create_table"]
        st.rerun()

    valid_pumps = edited_df["Pump ID"].dropna().tolist()
    if valid_pumps:
        st.divider()
        if "tanks" not in st.session_state: st.session_state.tanks = {"Water Tank 1": []}
        for tank in list(st.session_state.tanks.keys()):
            with st.container(border=True):
                st.write(f"**{tank}**")
                st.session_state.tanks[tank] = st.multiselect(f"Assign to {tank}:", valid_pumps, default=[p for p in st.session_state.tanks[tank] if p in valid_pumps], key=tank)
        
        if st.button("💾 Save Project", type="primary"):
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            try:
                c.execute("INSERT INTO projects VALUES (?,?,?,?)", (project_name, p_type, t_type, datetime.datetime.now()))
                for _, row in edited_df.dropna(subset=["Pump ID"]).iterrows():
                    p_id = row["Pump ID"]
                    tank = next((t for t, p_list in st.session_state.tanks.items() if p_id in p_list), "Unassigned")
                    c.execute("INSERT INTO pumps VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (p_id, project_name, row["Pump Model"], row["ISO No."], row["HP"], row["kW"], row["Voltage (V)"], row["Amp (A)"], row["Phase"], row["Hertz"], row["Insulation"], tank))
                conn.commit()
                st.success("Project Saved!")
                st.session_state.page = "home"
                st.rerun()
            except Exception as e: st.error(f"Error: {e}")
            finally: conn.close()

def render_dashboard(project_name):
    st.button("⬅️ Back", on_click=lambda: st.session_state.update(page="home"))
    st.header(f"📊 Dashboard: {project_name}")
    conn = sqlite3.connect(DB_FILE)
    pumps_df = pd.read_sql("SELECT * FROM pumps WHERE project_id=?", conn, params=(project_name,))
    
    # Dynamic Icons
    proj_type = pd.read_sql("SELECT type FROM projects WHERE project_id=?", conn, params=(project_name,)).iloc[0]['type']
    icon_file = "pump_icon.png" if proj_type == "Centrifugal" else "pump_icon2.png"
    icon_b64 = get_base64_image(icon_file)

    for tank in pumps_df['tank_name'].unique():
        st.subheader(f"🟦 {tank}")
        tank_pumps = pumps_df[pumps_df['tank_name'] == tank]
        cols = st.columns(len(tank_pumps))
        for idx, (_, row) in enumerate(tank_pumps.iterrows()):
            with cols[idx]:
                st.markdown(f"<div style='text-align:center; border:2px solid #0085CA; border-radius:10px; padding:10px; background-color:#002F6C; color:white;'><img src='data:image/png;base64,{icon_b64}' width='50'><br><b>{row['pump_id']}</b><br>{row['model']}</div>", unsafe_allow_html=True)
    conn.close()

# --- MAIN APP ---
st.set_page_config(page_title="Walrus Pump Architect", layout="wide")
init_db()

if "page" not in st.session_state: st.session_state.page = "home"

if st.session_state.page == "home":
    st.title("🚰 Walrus Pump Test Architect")
    if st.button("➕ Create New Project"):
        st.session_state.page = "create"
        st.rerun()
    
    projects = get_projects()
    for _, row in projects.iterrows():
        with st.expander(f"Project: {row['project_id']}"):
            if st.button("Open Dashboard", key=row['project_id']):
                st.session_state.selected_project = row['project_id']
                st.session_state.page = "dashboard"
                st.rerun()

elif st.session_state.page == "create":
    render_create_project()
elif st.session_state.page == "dashboard":
    render_dashboard(st.session_state.selected_project)