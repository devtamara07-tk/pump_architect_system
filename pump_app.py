import streamlit as st
import pandas as pd
import sqlite3
import datetime
import base64
import os

# --- INDUSTRIAL DARK UI CSS ---
def inject_industrial_css():
    st.markdown("""
        <style>
            .main { background-color: #121417; color: #E0E0E0; }
            [data-testid="stHeader"] { background: rgba(0,0,0,0); }
            
            /* Hero Section */
            .hero-bg {
                background: linear-gradient(rgba(0,0,0,0.7), rgba(0,0,0,0.7)), 
                            url('https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?q=80&w=2070&auto=format&fit=crop');
                background-size: cover; background-position: center;
                padding: 40px; border-radius: 15px; text-align: center;
                margin-bottom: 25px; border: 1px solid #333;
            }
            
            /* Table Styling - LARGER WHITE HEADERS */
            .table-title { color: white !important; font-size: 1.3rem; margin-bottom: 15px; font-weight: bold; }
            .col-header { 
                color: white !important; 
                font-size: 16px !important; 
                font-weight: bold; 
                text-transform: uppercase; 
                border-bottom: 2px solid #444; 
                padding-bottom: 8px; 
                margin-bottom: 10px;
            }
            
            /* 1. Increased Font Size for List */
            .white-text { color: white !important; font-size: 16px !important; font-weight: 500; }
            
            /* Status Pills */
            .status-pill {
                padding: 4px 0px; border-radius: 4px; font-size: 12px;
                font-weight: bold; text-align: center; color: white;
                width: 100%; display: inline-block;
            }
            .bg-running { background-color: #28a745; }
            .bg-stopped { background-color: #dc3545; }
            .bg-standby { background-color: #0d6efd; }
            .bg-completed { background-color: #6c757d; }

            /* 2. Action Buttons (Styled identical to Status Pills) */
            button[aria-label="Open"], 
            button[aria-label="Modify"], 
            button[aria-label="Delete"] {
                border-radius: 4px !important;
                font-size: 12px !important;
                font-weight: bold !important;
                min-height: 26px !important; 
                height: 26px !important; 
                padding: 0 5px !important;
                border: none !important; /* Removes default border */
            }
            button[aria-label="Open"] { background-color: #0d6efd !important; color: white !important; }
            button[aria-label="Modify"] { background-color: #ffc107 !important; color: black !important; }
            button[aria-label="Delete"] { background-color: #dc3545 !important; color: white !important; }

            button[aria-label="Open"]:hover { background-color: #0b5ed7 !important; color: white !important; }
            button[aria-label="Modify"]:hover { background-color: #ffca2c !important; color: black !important; }
            button[aria-label="Delete"]:hover { background-color: #bb2d3b !important; color: white !important; }

            /* 3. Warning Confirmation Buttons (Black Text) */
            button[aria-label="Yes, Delete Project"],
            button[aria-label="Cancel"] {
                background-color: #E0E0E0 !important;
                color: black !important;
                border: 1px solid #ccc !important;
                font-weight: bold !important;
            }
            button[aria-label="Yes, Delete Project"]:hover,
            button[aria-label="Cancel"]:hover {
                background-color: #C0C0C0 !important;
                color: black !important;
            }
            
            /* Form overrides */
            h2 { color: #3498DB !important; font-size: 1.4rem !important; }
            .stDataEditor { background-color: #1C1F24 !important; }
        </style>
    """, unsafe_allow_html=True)

# --- DATABASE SETUP ---
DB_FILE = "architect_system.db"
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS projects (project_id TEXT PRIMARY KEY, type TEXT, test_type TEXT, created_at DATETIME)')
    c.execute('CREATE TABLE IF NOT EXISTS pumps (pump_id TEXT, project_id TEXT, model TEXT, iso_no TEXT, hp REAL, kw REAL, voltage TEXT, amp TEXT, phase INTEGER, hertz TEXT, insulation TEXT, tank_name TEXT, PRIMARY KEY (pump_id, project_id))')
    conn.commit(); conn.close()

# --- STEP 3 & 4 LOGIC (Create/Modify Form) ---
def get_column_config():
    return {
        "Pump Model": st.column_config.TextColumn("Pump Model", width="medium"),
        "Pump ID": st.column_config.TextColumn("Pump ID", disabled=True, width="small"),
        "Hertz": st.column_config.SelectboxColumn("Hertz", options=["50", "60"], width="small"),
    }

def render_project_form(edit_id=None):
    if st.button("⬅️ Back to Main"):
        for key in ["specs_df", "edit_loaded", "p_type_default", "t_type_default", "tanks"]:
            if key in st.session_state: del st.session_state[key]
        st.session_state.page = "home"; st.rerun()

    st.header(f"🛠️ {'Modify' if edit_id else 'Create New'} Project")

    if edit_id and "edit_loaded" not in st.session_state:
        conn = sqlite3.connect(DB_FILE)
        pumps = pd.read_sql("SELECT * FROM pumps WHERE project_id=?", conn, params=(edit_id,))
        proj = pd.read_sql("SELECT * FROM projects WHERE project_id=?", conn, params=(edit_id,))
        st.session_state.p_type_default = proj.iloc[0]['type']
        st.session_state.t_type_default = proj.iloc[0]['test_type']
        st.session_state.specs_df = pumps.rename(columns={'model': 'Pump Model', 'pump_id': 'Pump ID'})
        st.session_state.tanks = {t: pumps[pumps['tank_name']==t]['pump_id'].tolist() for t in pumps['tank_name'].unique() if t != "Unassigned"}
        st.session_state.edit_loaded = True; conn.close()

    c1, c2 = st.columns([1, 2])
    p_type = c1.radio("1. Pump Type", ["Centrifugal", "Submersible"], horizontal=True, index=0 if st.session_state.get("p_type_default") != "Submersible" else 1)
    t_type = c2.text_input("2. Test Type", value=st.session_state.get("t_type_default", ""))
    project_name = f"{p_type}_{t_type}" if t_type else p_type
    
    st.subheader("3. Pump Specification")
    if "specs_df" not in st.session_state: st.session_state.specs_df = pd.DataFrame(columns=["Pump Model", "Pump ID", "ISO No.", "HP", "kW", "Voltage (V)", "Amp (A)", "Phase", "Hertz", "Insulation"])
    
    edited_df = st.data_editor(st.session_state.specs_df, num_rows="dynamic", use_container_width=True, hide_index=True, column_config=get_column_config(), key="editor")
    
    new_ids = [f"P-{str(i+1).zfill(2)}" if pd.notna(r["Pump Model"]) and str(r["Pump Model"]).strip() else None for i, r in edited_df.iterrows()]
    if [str(x) if pd.notna(x) else None for x in edited_df["Pump ID"]] != new_ids:
        edited_df["Pump ID"] = new_ids; st.session_state.specs_df = edited_df; st.rerun()

    valid_pumps = edited_df["Pump ID"].dropna().tolist()
    if valid_pumps:
        st.divider(); st.subheader("4. Installation Layout")
        if "tanks" not in st.session_state: st.session_state.tanks = {"Water Tank 1": []}
        if st.button("➕ Add Water Tank"): st.session_state.tanks[f"Water Tank {len(st.session_state.tanks)+1}"] = []; st.rerun()
            
        cols = st.columns(3)
        for i, tank in enumerate(list(st.session_state.tanks.keys())):
            with cols[i % 3]:
                with st.container(border=True):
                    others = [p for t, p_list in st.session_state.tanks.items() if t != tank for p in p_list]
                    avail = [p for p in valid_pumps if p not in others]
                    st.session_state.tanks[tank] = st.multiselect(f"{tank}", avail, default=[p for p in st.session_state.tanks[tank] if p in valid_pumps], key=f"sel_{tank}")

        if st.button("💾 Save Project", type="primary"):
            conn = sqlite3.connect(DB_FILE); c = conn.cursor()
            if edit_id: c.execute("DELETE FROM projects WHERE project_id=?", (edit_id,)); c.execute("DELETE FROM pumps WHERE project_id=?", (edit_id,))
            c.execute("INSERT INTO projects VALUES (?,?,?,?)", (project_name, p_type, t_type, datetime.datetime.now()))
            for _, row in edited_df.dropna(subset=["Pump ID"]).iterrows():
                tank = next((t for t, pl in st.session_state.tanks.items() if row["Pump ID"] in pl), "Unassigned")
                c.execute("INSERT INTO pumps VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (row["Pump ID"], project_name, row["Pump Model"], row["ISO No."], row["HP"], row["kW"], row["Voltage (V)"], row["Amp (A)"], row["Phase"], row["Hertz"], row["Insulation"], tank))
            conn.commit(); conn.close(); st.session_state.page = "home"; st.rerun()

# --- MAIN APP ---
st.set_page_config(page_title="Pump Architect", layout="wide")
inject_industrial_css()
init_db()

if "page" not in st.session_state: st.session_state.page = "home"

if st.session_state.page == "home":
    st.markdown('<div class="hero-bg"><h1 style="color:white; letter-spacing:2px;">PUMP ARCHITECT SYSTEM</h1><p style="color:#aaa;">Control Center v2.0</p></div>', unsafe_allow_html=True)
    
    c_btn, _ = st.columns([1, 5])
    if c_btn.button("+ Create New Project", type="primary", use_container_width=True): 
        st.session_state.page = "create"; st.rerun()
    
    st.markdown("<div class='table-title'>CURRENT PROJECTS</div>", unsafe_allow_html=True)
    
    # Custom High-Visibility Warning Message
    if "confirm_delete" in st.session_state and st.session_state.confirm_delete:
        del_target = st.session_state.confirm_delete
        st.markdown(f"""
            <div style="background-color: rgba(220, 53, 69, 0.2); border: 1px solid #dc3545; padding: 15px; border-radius: 5px; margin-bottom: 15px;">
                <span style="color: white; font-size: 16px; font-weight: bold;">⚠️ Are you sure you want to permanently delete {del_target}?</span>
                <span style="color: #ccc; font-size: 14px; margin-left: 10px;">This cannot be undone.</span>
            </div>
        """, unsafe_allow_html=True)
        
        warn_c1, warn_c2, _ = st.columns([1.5, 1.5, 4])
        with warn_c1:
            if st.button("Yes, Delete Project", key="yes_del", use_container_width=True):
                conn = sqlite3.connect(DB_FILE)
                conn.execute("DELETE FROM projects WHERE project_id=?", (del_target,))
                conn.execute("DELETE FROM pumps WHERE project_id=?", (del_target,))
                conn.commit(); conn.close()
                st.session_state.confirm_delete = None
                st.rerun()
        with warn_c2:
            if st.button("Cancel", key="no_del", use_container_width=True):
                st.session_state.confirm_delete = None
                st.rerun()
        st.divider()
    
    # Table Headers
    h1, h2, h3, h4, h5 = st.columns([0.5, 1.2, 3.5, 1.5, 3])
    h1.markdown("<div class='col-header'>No.</div>", unsafe_allow_html=True)
    h2.markdown("<div class='col-header'>Status</div>", unsafe_allow_html=True)
    h3.markdown("<div class='col-header'>Project Name</div>", unsafe_allow_html=True)
    h4.markdown("<div class='col-header'>Date</div>", unsafe_allow_html=True)
    h5.markdown("<div class='col-header'>Actions</div>", unsafe_allow_html=True)
    
    conn = sqlite3.connect(DB_FILE)
    projects = conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
    conn.close()
    
    for idx, p in enumerate(projects):
        pid, ptype, ttype, created = p
        date_str = created.split()[0]
        
        # Determine status pill logically
        if "Endurance" in pid:
            status_class = "bg-running"
            status_text = "Running"
        elif "Fail" in pid:
            status_class = "bg-stopped"
            status_text = "Stopped"
        else:
            status_class = "bg-standby"
            status_text = "Standby"

        with st.container():
            c1, c2, c3, c4, c5, c6, c7 = st.columns([0.5, 1.2, 3.5, 1.5, 1, 1, 1])
            
            c1.markdown(f"<div class='white-text' style='padding-top:5px;'>{idx + 1}</div>", unsafe_allow_html=True)
            c2.markdown(f'<div class="status-pill {status_class}">{status_text}</div>', unsafe_allow_html=True)
            c3.markdown(f"<div class='white-text' style='padding-top:5px;'>{pid}</div>", unsafe_allow_html=True)
            c4.markdown(f"<div class='white-text' style='padding-top:5px;'>{date_str}</div>", unsafe_allow_html=True)
            
            # Action Buttons
            if c5.button("Open", key=f"o_{pid}", use_container_width=True): 
                st.session_state.selected_project = pid; st.session_state.page = "dash"; st.rerun()
            if c6.button("Modify", key=f"m_{pid}", use_container_width=True): 
                st.session_state.edit_id = pid; st.session_state.page = "modify"; st.rerun()
            if c7.button("Delete", key=f"d_{pid}", use_container_width=True): 
                st.session_state.confirm_delete = pid; st.rerun()

elif st.session_state.page == "create": render_project_form()
elif st.session_state.page == "modify": render_project_form(edit_id=st.session_state.edit_id)