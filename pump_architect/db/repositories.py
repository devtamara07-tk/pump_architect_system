import datetime
import pandas as pd
from pump_architect.db.connection import get_connection


def get_projects():
    """Return a DataFrame of all projects."""
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM projects", conn)
    conn.close()
    return df


def delete_project(project_id):
    """Delete a project and its associated pumps."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM projects WHERE project_id=%s", (project_id,))
    c.execute("DELETE FROM pumps WHERE project_id=%s", (project_id,))
    conn.commit()
    conn.close()


def save_project(project_name, p_type, t_type, pumps_df, tanks, edit_id=None):
    """Insert or replace a project and its pump rows.

    Args:
        project_name: Derived project identifier (e.g. 'Centrifugal_Endurance Test').
        p_type: Pump type string.
        t_type: Test type string.
        pumps_df: DataFrame of pump rows (must include 'Pump ID' column).
        tanks: Dict mapping tank name -> list of pump IDs.
        edit_id: If provided, the existing project with this ID is deleted first.

    Returns:
        None on success. Raises on database error.
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        if edit_id:
            c.execute("DELETE FROM projects WHERE project_id=%s", (edit_id,))
            c.execute("DELETE FROM pumps WHERE project_id=%s", (edit_id,))

        c.execute(
            "INSERT INTO projects VALUES (?,?,?,?)",
            (project_name, p_type, t_type, datetime.datetime.now()),
        )
        for _, row in pumps_df.dropna(subset=["Pump ID"]).iterrows():
            p_id = row["Pump ID"]
            tank = next(
                (t for t, p_list in tanks.items() if p_id in p_list), "Unassigned"
            )
            c.execute(
                "INSERT INTO pumps VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    p_id,
                    project_name,
                    row["Pump Model"],
                    row["ISO No."],
                    row["HP"],
                    row["kW"],
                    row["Voltage (V)"],
                    row["Amp (A)"],
                    row["Phase"],
                    row["Hertz"],
                    row["Insulation"],
                    tank,
                ),
            )
        conn.commit()
    finally:
        conn.close()
