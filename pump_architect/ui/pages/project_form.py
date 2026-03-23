import pandas as pd
import streamlit as st
from pump_architect.constants import FORM_STATE_KEYS
from pump_architect.db.connection import get_connection
from pump_architect.db.repositories import save_project


def _get_column_config():
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
        "Insulation": st.column_config.TextColumn("Insulation", width="small"),
    }


def _clear_form_state():
    for key in FORM_STATE_KEYS:
        if key in st.session_state:
            del st.session_state[key]


def render_project_form(edit_id=None):
    """Render the create / modify project form.

    Args:
        edit_id: project_id of an existing project to edit, or None to create new.
    """
    if st.button("Back to Main Page"):
        _clear_form_state()
        st.session_state.page = "home"
        st.rerun()

    st.markdown(
        f"""
        <div class="dashboard-shell">
            <div class="dashboard-kicker">Project Configuration</div>
            <h1 class="dashboard-title">{'Modify Project: ' + edit_id if edit_id else 'Create a New Project'}</h1>
        </div>
        """,
        unsafe_allow_html=True,
    )

    conn = get_connection()
    try:
        if edit_id and "edit_loaded" not in st.session_state:
            proj_data = pd.read_sql("SELECT * FROM projects WHERE project_id=?", conn, params=(edit_id,))
            pump_data = pd.read_sql("SELECT * FROM pumps WHERE project_id=?", conn, params=(edit_id,))

            st.session_state.p_type_default = proj_data.iloc[0]['type'] if not proj_data.empty else "Centrifugal"
            st.session_state.t_type_default = proj_data.iloc[0]['test_type'] if not proj_data.empty else ""

            df = pd.DataFrame()
            if not pump_data.empty:
                df["Pump Model"] = pump_data["model"]
                df["Pump ID"] = pump_data["pump_id"]
                df["ISO No."] = pump_data["iso_no"]
                df["HP"] = pump_data["hp"]
                df["kW"] = pump_data["kw"]
                df["Voltage (V)"] = pump_data["voltage"]
                df["Amp (A)"] = pump_data["amp"]
                df["Phase"] = pump_data["phase"]
                df["Hertz"] = pump_data["hertz"]
                df["Insulation"] = pump_data["insulation"]

            st.session_state.specs_df = df

            st.session_state.tanks = {"Water Tank 1": []}
            if not pump_data.empty:
                for tank_name in pump_data['tank_name'].unique():
                    if tank_name != "Unassigned":
                        if tank_name not in st.session_state.tanks:
                            st.session_state.tanks[tank_name] = []
                        st.session_state.tanks[tank_name] = pump_data[pump_data['tank_name'] == tank_name]['pump_id'].tolist()

            st.session_state.edit_loaded = True
    finally:
        conn.close()

    col1, col2 = st.columns([1.5, 2.5])
    with col1:
        p_type = st.radio(
            "1. Pump Type",
            ["Centrifugal", "Submersible"],
            index=0 if st.session_state.get("p_type_default", "Centrifugal") == "Centrifugal" else 1,
            horizontal=True,
        )
    with col2:
        t_type = st.text_input(
            "2. Test Type",
            value=st.session_state.get("t_type_default", ""),
            placeholder="e.g., Endurance Test",
        )

    project_name = f"{p_type}_{t_type}" if t_type else p_type
    st.markdown(
        f"<div class='project-badge'>Project Name: <strong>{project_name}</strong></div>",
        unsafe_allow_html=True,
    )
    st.divider()

    st.markdown("<div class='section-heading'>3. Pump Specs</div>", unsafe_allow_html=True)
    st.info("Remark: To add a pump, type the model name into the Pump Model column. Remove unused rows directly from the table.")

    desired_columns = ["Pump Model", "Pump ID", "ISO No.", "HP", "kW", "Voltage (V)", "Amp (A)", "Phase", "Hertz", "Insulation"]

    if "specs_df" not in st.session_state or st.session_state.specs_df is None:
        df = pd.DataFrame(columns=desired_columns)
        st.session_state.specs_df = df
    else:
        if "No." in st.session_state.specs_df.columns:
            st.session_state.specs_df = st.session_state.specs_df.drop(columns=["No."])
        if set(st.session_state.specs_df.columns) == set(desired_columns):
            st.session_state.specs_df = st.session_state.specs_df[desired_columns]

    edited_df = st.data_editor(
        st.session_state.specs_df,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config=_get_column_config(),
        key="create_table",
    )

    edited_df = edited_df.reset_index(drop=True)

    new_ids = []
    counter = 1
    for _, row in edited_df.iterrows():
        if pd.notna(row.get("Pump Model")) and str(row.get("Pump Model")).strip() != "":
            new_ids.append(f"P-{str(counter).zfill(2)}")
            counter += 1
        else:
            new_ids.append(None)

    current_ids = [str(x) if pd.notna(x) else None for x in edited_df["Pump ID"]]

    if current_ids != new_ids:
        edited_df["Pump ID"] = new_ids
        st.session_state.specs_df = edited_df
        if "create_table" in st.session_state:
            del st.session_state["create_table"]
        st.rerun()

    valid_pumps = edited_df["Pump ID"].dropna().tolist()
    if valid_pumps:
        st.divider()
        st.markdown("<div class='section-heading'>4. Pump Test Installation Layout</div>", unsafe_allow_html=True)

        if "tanks" not in st.session_state:
            st.session_state.tanks = {"Water Tank 1": []}

        col_btn, _ = st.columns([1, 4])
        with col_btn:
            if st.button("Add Water Tank", use_container_width=True):
                next_num = len(st.session_state.tanks) + 1
                new_tank_name = f"Water Tank {next_num}"
                while new_tank_name in st.session_state.tanks:
                    next_num += 1
                    new_tank_name = f"Water Tank {next_num}"
                st.session_state.tanks[new_tank_name] = []
                st.rerun()

        for tank in list(st.session_state.tanks.keys()):
            widget_key = f"select_{tank}"
            if widget_key in st.session_state:
                st.session_state.tanks[tank] = [p for p in st.session_state[widget_key] if p in valid_pumps]

        tank_names = list(st.session_state.tanks.keys())
        cols = st.columns(3)

        for i, tank in enumerate(tank_names):
            with cols[i % 3]:
                with st.container(border=True):
                    st.markdown(f"<div class='tank-title'>{tank}</div>", unsafe_allow_html=True)
                    st.markdown("<div class='muted-note'>Assign each pump to one active water tank.</div>", unsafe_allow_html=True)

                    assigned_to_others = []
                    for other_tank, p_list in st.session_state.tanks.items():
                        if other_tank != tank:
                            assigned_to_others.extend(p_list)

                    available_pumps = [p for p in valid_pumps if p not in assigned_to_others]

                    st.multiselect(
                        "Assign Pumps:",
                        options=available_pumps,
                        default=st.session_state.tanks[tank],
                        key=f"select_{tank}",
                        label_visibility="collapsed",
                    )

        st.write("")
        col_save, _ = st.columns([1, 4])
        with col_save:
            if st.button("Save Project", type="primary", use_container_width=True):
                try:
                    save_project(project_name, p_type, t_type, edited_df, st.session_state.tanks, edit_id=edit_id)
                    st.success("Project Saved!")
                    _clear_form_state()
                    st.session_state.page = "home"
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
