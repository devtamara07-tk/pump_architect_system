import os
import streamlit as st
from pump_architect.legacy_formula_utils import (
    parse_ts,
)
from pump_architect import legacy_db_utils
from pump_architect import legacy_ui_event_utils
from pump_architect import legacy_state_utils
from pump_architect import legacy_maintenance_wizard
from pump_architect import legacy_add_record_wizard
from pump_architect import legacy_project_form
from pump_architect import legacy_pages
from pump_architect import legacy_project_state

# --- 1. INITIALIZATION & DATABASE ---

DB_FILE = "architect_system.db"

def get_database_url():
    # 1) Prefer environment variable (Codespaces, local terminal, etc.)
    url = os.getenv("DATABASE_URL")
    if url:
        return url

    # 2) Fall back to Streamlit secrets (Streamlit Community Cloud)
    try:
        return st.secrets["DATABASE_URL"]
    except Exception:
        return None

DATABASE_URL = get_database_url()
USE_POSTGRES = DATABASE_URL is not None

def init_db():
    if USE_POSTGRES:
        return legacy_project_state.init_db_postgres(DATABASE_URL)  # example name
    return legacy_project_state.init_db(DB_FILE)

if "page" not in st.session_state: st.session_state.page = "home"
if "wizard_step" not in st.session_state: st.session_state.wizard_step = 1

# --- 2. RESTORED INDUSTRIAL DARK UI CSS (18px Fonts) ---
def inject_industrial_css():
    return legacy_ui_event_utils.inject_industrial_css()

def queue_confirmation(message):
    return legacy_ui_event_utils.queue_confirmation(message)

def render_confirmation_banner():
    return legacy_ui_event_utils.render_confirmation_banner()

def get_project_records(project_id):
    return legacy_db_utils.get_project_records(DB_FILE, project_id)

def get_latest_record(project_id):
    return legacy_db_utils.get_latest_record(DB_FILE, project_id)

def build_phase4_hardware_plan(pump_ids, status_grid):
    return legacy_state_utils.build_phase4_hardware_plan(pump_ids, status_grid)

def has_baseline_record(project_id):
    return legacy_db_utils.has_baseline_record(DB_FILE, project_id)

def clear_project_records(project_id):
    return legacy_db_utils.clear_project_records(DB_FILE, project_id)

def clear_project_maintenance_events(project_id):
    return legacy_db_utils.clear_project_maintenance_events(DB_FILE, project_id)

def restore_project_formula_state(project_id):
    return legacy_state_utils.restore_project_formula_state(DB_FILE, project_id)

def persist_event_log_for_project(project_id):
    return legacy_ui_event_utils.persist_event_log_for_project(DB_FILE, project_id)

def add_event_log_entry(text):
    return legacy_ui_event_utils.add_event_log_entry(text)

def auto_close_maintenance_for_stable_pumps(project_id, stable_pumps):
    return legacy_ui_event_utils.auto_close_maintenance_for_stable_pumps(
        DB_FILE,
        project_id,
        stable_pumps,
        get_maintenance_events,
    )

def build_dashboard_report_csv(project_id):
    return legacy_ui_event_utils.build_dashboard_report_csv(
        project_id,
        get_latest_record,
        get_maintenance_events,
    )

def restore_project_hardware_state(project_id):
    return legacy_state_utils.restore_project_hardware_state(DB_FILE, project_id)

def get_maintenance_events(project_id):
    return legacy_db_utils.get_maintenance_events(DB_FILE, project_id)

def render_add_maintenance_wizard():
    return legacy_maintenance_wizard.render_add_maintenance_wizard(
        DB_FILE,
        inject_industrial_css,
        parse_ts,
        get_maintenance_events,
        add_event_log_entry,
        persist_event_log_for_project,
        queue_confirmation,
    )

def render_add_record_wizard():
    return legacy_add_record_wizard.render_add_record_wizard(DB_FILE)

# --- 3. THE WIZARD (FULL STEPS RESTORED) ---
def render_project_form():
    return legacy_project_form.render_project_form(DB_FILE)
# --- HELPER FUNCTIONS ---
def handle_open_project(project_id):
    return legacy_project_state.handle_open_project(
        DB_FILE,
        project_id,
        restore_project_hardware_state,
        restore_project_formula_state,
    )

def handle_modify_project(project_id):
    return legacy_project_state.handle_modify_project(
        DB_FILE,
        project_id,
        restore_project_formula_state,
    )

# --- 4. MAIN ROUTING & HOME (Original 18px Headers) ---
init_db()
inject_industrial_css()
render_confirmation_banner()

simple_page_handled = legacy_pages.route_simple_pages(
    st.session_state.page,
    render_project_form,
    render_add_record_wizard,
    render_add_maintenance_wizard,
)

if not simple_page_handled and st.session_state.page == "home":
    legacy_pages.render_home_page(
        DB_FILE,
        handle_open_project,
        handle_modify_project,
    )

elif not simple_page_handled and st.session_state.page == "dashboard":
    legacy_pages.render_dashboard_page(
        DB_FILE,
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
