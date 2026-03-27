import streamlit as st
from pump_architect.db.repositories import get_projects, delete_project


def render_home():
    """Render the home page with the project list."""
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

    st.markdown(
        """
        <div class="hero-panel">
            <div class="hero-kicker">Pump Architect System</div>
            <h1 class="hero-title">Pump Test Architect 1.0</h1>
            <p class="hero-subtitle">Industrial project control for pump configuration, tank layout planning, and dashboard review.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_new, _ = st.columns(2)
    with col_new:
        if st.button("Create New Project", type="primary", use_container_width=True):
            st.session_state.page = "create"
            st.rerun()

    st.markdown("<div class='section-heading'>Current Projects</div>", unsafe_allow_html=True)
    projects = get_projects()

    if projects.empty:
        st.info("No projects found. Click 'Create New Project' to get started.")
    else:
        if "created_at" in projects.columns:
            projects = projects.sort_values(by="created_at", ascending=False, na_position="last")

        with st.container(border=True):
            header_cols = st.columns(7)
            for col, title in zip(header_cols, ["No.", "Status", "Name", "Date", "Open", "Modify", "Delete"]):
                col.markdown(f"<div class='project-table-header'>{title}</div>", unsafe_allow_html=True)

            for idx, (_, row) in enumerate(projects.iterrows(), start=1):
                date_str = str(row.get("created_at", ""))[:10] if row.get("created_at") else "N/A"
                row_cols = st.columns(7)
                confirm_key = f"delete_confirm_{row['project_id']}"

                row_cols[0].markdown(f"<div class='project-cell'>{idx}</div>", unsafe_allow_html=True)
                row_cols[1].markdown("<div class='status-pill'>Standby</div>", unsafe_allow_html=True)
                row_cols[2].markdown(f"<div class='project-cell'>{row['project_id']}</div>", unsafe_allow_html=True)
                row_cols[3].markdown(f"<div class='project-cell'>{date_str}</div>", unsafe_allow_html=True)

                if row_cols[4].button("Open", key=f"open_{row['project_id']}", use_container_width=True):
                    st.session_state.selected_project = row['project_id']
                    st.session_state.page = "dashboard"
                    st.rerun()

                if row_cols[5].button("Modify", key=f"mod_{row['project_id']}", use_container_width=True):
                    st.session_state.edit_project_id = row['project_id']
                    st.session_state.page = "modify"
                    st.rerun()

                if st.session_state.get(confirm_key, False):
                    if row_cols[6].button("Cancel", key=f"cancel_{row['project_id']}", use_container_width=True):
                        st.session_state.pop(confirm_key, None)
                        st.rerun()
                    if row_cols[6].button("DANGER Confirm Delete Project", key=f"conf_{row['project_id']}", use_container_width=True, type="primary"):
                        delete_project(row['project_id'])
                        st.session_state.pop(confirm_key, None)
                        st.rerun()
                else:
                    if row_cols[6].button("Delete Project", key=f"del_{row['project_id']}", use_container_width=True):
                        st.session_state[confirm_key] = True
                        st.rerun()

                if idx < len(projects.index):
                    st.markdown("<hr>", unsafe_allow_html=True)
