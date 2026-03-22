import streamlit as st
from pump_architect.db.repositories import get_projects, delete_project


def render_home():
    """Render the home page with the project list."""
    st.title("🚰 Pump Test Architect 1.0")

    col_new, _ = st.columns([1, 4])
    with col_new:
        if st.button("➕ Create New Project", type="primary", use_container_width=True):
            st.session_state.page = "create"
            st.rerun()

    st.divider()
    st.write("### Current Project List")
    projects = get_projects()

    if projects.empty:
        st.info("No projects found. Click 'Create New Project' to get started.")
    else:
        col1, col2, col3, col4 = st.columns([4, 1, 1, 1])
        col1.markdown("**Project Name**")
        col2.markdown("**Action**")
        st.markdown("<hr style='margin: 0.2em 0px; border-color: #e0e0e0;'>", unsafe_allow_html=True)

        for _, row in projects.iterrows():
            col1, col2, col3, col4 = st.columns([4, 1, 1, 1])
            with col1:
                st.write(f"📁 **{row['project_id']}**")
            with col2:
                if st.button("OPEN", key=f"open_{row['project_id']}", use_container_width=True):
                    st.session_state.selected_project = row['project_id']
                    st.session_state.page = "dashboard"
                    st.rerun()
            with col3:
                if st.button("Modify", key=f"mod_{row['project_id']}", use_container_width=True):
                    st.session_state.edit_project_id = row['project_id']
                    st.session_state.page = "modify"
                    st.rerun()
            with col4:
                if st.button("Delete", key=f"del_{row['project_id']}", use_container_width=True):
                    delete_project(row['project_id'])
                    st.rerun()
            st.markdown("<hr style='margin: 0.2em 0px; border-color: #f0f0f0;'>", unsafe_allow_html=True)
