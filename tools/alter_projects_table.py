from pump_architect.db.connection import get_connection

ALTER_STATEMENTS = [
    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS tanks TEXT;",
    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS layout TEXT;",
    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS hardware_list TEXT;",
    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS hardware_dfs TEXT;",
    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS hardware_ds TEXT;",
    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS step6_watchdogs TEXT;",
    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS step6_limits TEXT;",
    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS step6_event_log TEXT;",
    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS watchdog_sync_ts TEXT;",
    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS step6_extra_limits TEXT;",
    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS step6_dashboard_tracker TEXT;",
    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS step5_var_mapping TEXT;",
    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS step5_formulas TEXT;",
    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS run_mode TEXT;",
    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS target_val TEXT;",
    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS tank_start_dates TEXT;",
]

def alter_projects_table():
    conn = get_connection()
    cur = conn.cursor()
    for stmt in ALTER_STATEMENTS:
        try:
            cur.execute(stmt)
            print(f"Executed: {stmt}")
        except Exception as e:
            print(f"Error executing '{stmt}': {e}")
    conn.commit()
    cur.close()
    conn.close()

if __name__ == "__main__":
    alter_projects_table()
    print("Schema alteration complete.")
