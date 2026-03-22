import streamlit as st
import pandas as pd
from pump_architect.db.connection import get_connection
from pump_architect.ui.assets import get_base64_image


def render_dashboard(project_name):
    """Render the pump dashboard for a given project."""
    st.button("⬅️ Back", on_click=lambda: st.session_state.update(page="home"))
    st.header(f"📊 Dashboard: {project_name}")

    conn = get_connection()
    pumps_df = pd.read_sql("SELECT * FROM pumps WHERE project_id=?", conn, params=(project_name,))
    proj_type = pd.read_sql(
        "SELECT type FROM projects WHERE project_id=?", conn, params=(project_name,)
    ).iloc[0]['type']
    conn.close()

    icon_file = "pump_icon.png" if proj_type == "Centrifugal" else "pump_icon2.png"
    icon_b64 = get_base64_image(icon_file)

    for tank in pumps_df['tank_name'].unique():
        st.subheader(f"🟦 {tank}")
        tank_pumps = pumps_df[pumps_df['tank_name'] == tank]
        cols = st.columns(len(tank_pumps))
        for idx, (_, row) in enumerate(tank_pumps.iterrows()):
            with cols[idx]:
                st.markdown(
                    f"<div style='text-align:center; border:2px solid #0085CA; border-radius:10px; "
                    f"padding:10px; background-color:#002F6C; color:white;'>"
                    f"<img src='data:image/png;base64,{icon_b64}' width='50'><br>"
                    f"<b>{row['pump_id']}</b><br>{row['model']}</div>",
                    unsafe_allow_html=True,
                )
