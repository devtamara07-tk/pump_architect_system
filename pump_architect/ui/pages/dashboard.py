import streamlit as st
import pandas as pd
from pump_architect.db.connection import get_connection
from pump_architect.ui.assets import get_base64_image


def render_dashboard(project_name):
    """Render the pump dashboard for a given project."""
    st.button("Back", on_click=lambda: st.session_state.update(page="home"))

    conn = get_connection()
    pumps_df = pd.read_sql("SELECT * FROM pumps WHERE project_id=?", conn, params=(project_name,))
    proj_type = pd.read_sql(
        "SELECT type FROM projects WHERE project_id=?", conn, params=(project_name,)
    ).iloc[0]['type']
    conn.close()

    tank_count = pumps_df['tank_name'].nunique() if not pumps_df.empty else 0
    pump_count = len(pumps_df.index)

    st.markdown(
        f"""
        <div class="dashboard-shell">
            <div class="dashboard-kicker">Project Dashboard</div>
            <h1 class="dashboard-title">{project_name}</h1>
            <div>
                <span class="metric-chip">Pump Type: {proj_type}</span>
                <span class="metric-chip">Water Tanks: {tank_count}</span>
                <span class="metric-chip">Pumps: {pump_count}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    icon_file = "pump_icon.png" if proj_type == "Centrifugal" else "pump_icon2.png"
    icon_b64 = get_base64_image(icon_file)

    for tank in pumps_df['tank_name'].unique():
        st.markdown(f"<div class='section-heading'>{tank}</div>", unsafe_allow_html=True)
        tank_pumps = pumps_df[pumps_df['tank_name'] == tank]
        cols = st.columns(len(tank_pumps))
        for idx, (_, row) in enumerate(tank_pumps.iterrows()):
            with cols[idx]:
                st.markdown(
                    f"<div class='pump-card'>"
                    f"<img src='data:image/png;base64,{icon_b64}' width='54'>"
                    f"<div class='pump-card-id'>{row['pump_id']}</div>"
                    f"<div class='pump-card-model'>{row['model']}</div>"
                    f"<div class='metric-chip'>ISO {row['iso_no'] or '-'}</div>"
                    f"<div class='metric-chip'>{row['hp'] or '-'} HP</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
