
from pump_architect.db.connection import get_connection

import streamlit as st

from pump_architect import legacy_dashboard_page


def route_simple_pages(page, render_project_form, render_add_record_wizard, render_add_maintenance_wizard):
    if page == "create":
        render_project_form()
        return True

    if page == "add_record":
        render_add_record_wizard()
        return True

    if page == "add_maintenance":
        render_add_maintenance_wizard()
        return True

    return False


def render_home_page(handle_open_project, handle_modify_project):
    st.markdown(
        """
        <style>
            div[data-testid="stHorizontalBlock"]:has(> div:nth-child(7) button) > div:nth-child(5) button {
                background: linear-gradient(180deg, #f4f7fb 0%, #dce4ef 100%) !important;
                color: #09111a !important;
                border: 1px solid #c4d1de !important;
            }

            div[data-testid="stHorizontalBlock"]:has(> div:nth-child(7) button) > div:nth-child(5) button * {
                color: #09111a !important;
                fill: #09111a !important;
            }

            div[data-testid="stHorizontalBlock"]:has(> div:nth-child(7) button) > div:nth-child(6) button {
                background: linear-gradient(180deg, #ffd978 0%, #f3b63f 100%) !important;
                color: #201300 !important;
                border: 1px solid #d19a2d !important;
            }

            div[data-testid="stHorizontalBlock"]:has(> div:nth-child(7) button) > div:nth-child(6) button * {
                color: #201300 !important;
                fill: #201300 !important;
            }

            div[data-testid="stHorizontalBlock"]:has(> div:nth-child(7) button) > div:nth-child(7) button {
                background: linear-gradient(180deg, #ff7f7f 0%, #dc4c4c 100%) !important;
                color: #ffffff !important;
                border: 1px solid #b53737 !important;
            }

            div[data-testid="stHorizontalBlock"]:has(> div:nth-child(7) button) > div:nth-child(7) button * {
                color: #ffffff !important;
                fill: #ffffff !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="hero-bg"><h1 style="color:white; letter-spacing:2px; font-size:3rem;">PUMP ARCHITECT SYSTEM</h1><p style="color:#aaa; font-size:1.5rem;">Control Center v2.0</p></div>', unsafe_allow_html=True)

    if st.button("Create New Project", type="primary"):
        for k in [
            "project_name", "proj_type", "test_type", "run_mode", "target_val", "target_unit",
            "specs_df", "layout_df", "water_tanks", "hardware_list", "var_mapping_df", "formulas_df",
            "watchdogs_df", "watchdog_matrix_df", "limits_df", "extra_limits_df", "event_log", "wizard_step", "current_project", "dashboard_main_tracker",
            "add_record_draft", "maintenance_prefill_pumps", "maintenance_source_record_id", "target_val_input"
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

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT project_id, type, test_type, created_at FROM projects ORDER BY created_at DESC")
    projs = cur.fetchall()

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
            if c[6].button("Cancel", key=f"can_{idx}", use_container_width=True):
                del st.session_state[confirm_key]
                st.rerun()

            if c[6].button("DANGER Confirm Delete Project", key=f"conf_{idx}", use_container_width=True, type="primary"):
                conn = get_connection()
                cur.execute("DELETE FROM projects WHERE project_id=?", (p[0],))

                try:
                    cur.execute("DELETE FROM pumps WHERE project_name=?", (p[0],))
                except Exception:
                    cur.execute("PRAGMA table_info(pumps)")
                    cols = [info[1] for info in cur.fetchall()]
                    actual_col = cols[1]
                    cur.execute(f"DELETE FROM pumps WHERE {actual_col}=?", (p[0],))

                conn.commit()
                conn.close()
                del st.session_state[confirm_key]
                st.rerun()
        else:
            if c[6].button("Delete Project", key=f"d{idx}", use_container_width=True):
                st.session_state[confirm_key] = True
                st.rerun()


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
    return legacy_dashboard_page.render_dashboard_page(
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
    )
