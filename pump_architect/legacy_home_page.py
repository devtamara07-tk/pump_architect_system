import sqlite3

import streamlit as st


def render_home_page(db_file, handle_open_project, handle_modify_project):
    st.markdown('<div class="hero-bg"><h1 style="color:white; letter-spacing:2px; font-size:3rem;">PUMP ARCHITECT SYSTEM</h1><p style="color:#aaa; font-size:1.5rem;">Control Center v2.0</p></div>', unsafe_allow_html=True)

    if st.button("Create New Project"):
        for k in [
            "project_name", "proj_type", "test_type", "run_mode", "target_val", "target_unit",
            "specs_df", "layout_df", "water_tanks", "hardware_list", "var_mapping_df", "formulas_df",
            "watchdogs_df", "watchdog_matrix_df", "limits_df", "extra_limits_df", "event_log", "wizard_step", "current_project", "dashboard_main_tracker",
            "add_record_draft", "maintenance_prefill_pumps", "maintenance_source_record_id"
        ]:
            if k in st.session_state:
                del st.session_state[k]
        extra_keys = [k for k in st.session_state.keys() if k.startswith("df_") or k.startswith("ds_")]
        for k in extra_keys:
            del st.session_state[k]
        st.session_state.page = "create"
        st.session_state.wizard_step = 1
        st.rerun()

    st.write("")
    st.markdown("<div class='table-title' style='color:white; font-size:24px; font-weight:bold;'>CURRENT PROJECTS</div>", unsafe_allow_html=True)

    h = st.columns([0.4, 1.2, 2.5, 1.3, 3.6])
    for col, txt in zip(h, ["No.", "Status", "Name", "Date", "Actions"]):
        col.markdown(f"<div class='col-header'>{txt}</div>", unsafe_allow_html=True)

    conn = sqlite3.connect(db_file)
    projs = conn.execute("SELECT project_id, type, test_type, created_at FROM projects ORDER BY created_at DESC").fetchall()

    for idx, p in enumerate(projs):
        c = st.columns([0.4, 1.2, 2.5, 1.3, 1.2, 1.2, 1.2])

        c[0].markdown(f"<div class='white-text'>{idx+1}</div>", unsafe_allow_html=True)
        c[1].markdown('<div class="status-pill">Standby</div>', unsafe_allow_html=True)
        c[2].markdown(f"<div class='white-text'>{p[0]}</div>", unsafe_allow_html=True)
        date_str = str(p[3])[:10] if p[3] else "N/A"
        c[3].markdown(f"<div class='white-text'>{date_str}</div>", unsafe_allow_html=True)

        if c[4].button("Open", key=f"o{idx}", use_container_width=True):
            handle_open_project(p[0])

        if c[5].button("Modify", key=f"m{idx}", use_container_width=True):
            handle_modify_project(p[0])

        confirm_key = f"delete_confirm_{idx}"

        if st.session_state.get(confirm_key, False):
            if c[6].button("⚠️ CONFIRM", key=f"conf_{idx}", use_container_width=True, type="primary"):
                conn = sqlite3.connect(db_file)
                conn.execute("DELETE FROM projects WHERE project_id=?", (p[0],))

                try:
                    conn.execute("DELETE FROM pumps WHERE project_name=?", (p[0],))
                except sqlite3.OperationalError:
                    cursor = conn.execute("PRAGMA table_info(pumps)")
                    cols = [info[1] for info in cursor.fetchall()]
                    actual_col = cols[1]
                    conn.execute(f"DELETE FROM pumps WHERE {actual_col}=?", (p[0],))

                conn.commit()
                conn.close()
                del st.session_state[confirm_key]
                st.rerun()

            if c[6].button("Cancel", key=f"can_{idx}", use_container_width=True):
                del st.session_state[confirm_key]
                st.rerun()
        else:
            if c[6].button("Delete", key=f"d{idx}", use_container_width=True):
                st.session_state[confirm_key] = True
                st.rerun()
