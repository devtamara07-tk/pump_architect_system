import streamlit as st
from pump_architect.constants import FORM_STATE_KEYS
from pump_architect.db.schema import init_db
from pump_architect.ui.styles import inject_compact_css
from pump_architect.ui.pages.home import render_home
from pump_architect.ui.pages.project_form import render_project_form
from pump_architect.ui.pages.dashboard import render_dashboard

st.set_page_config(page_title="Pump Test Architect", layout="wide")
inject_compact_css()
init_db()

if "page" not in st.session_state:
    st.session_state.page = "home"

# Clear transient form state when returning to the home page
if st.session_state.page == "home":
    for k in FORM_STATE_KEYS:
        if k in st.session_state:
            del st.session_state[k]

# Page routing
if st.session_state.page == "home":
    render_home()
elif st.session_state.page == "create":
    render_project_form()
elif st.session_state.page == "modify":
    render_project_form(edit_id=st.session_state.edit_project_id)
elif st.session_state.page == "dashboard":
    render_dashboard(st.session_state.selected_project)
