import json
import sqlite3

import pandas as pd


def get_project_records(db_file, project_id):
    conn = sqlite3.connect(db_file)
    rows = conn.execute(
        """
        SELECT id, project_id, record_phase, record_ts, method, ambient_temp,
               tank_temps_json, status_grid_json, pump_readings_json, alarms_json,
               ack_alarm, created_at
        FROM project_records
        WHERE project_id = ?
        ORDER BY datetime(record_ts) DESC, id DESC
        """,
        (project_id,),
    ).fetchall()
    conn.close()
    cols = [
        "id", "project_id", "record_phase", "record_ts", "method", "ambient_temp",
        "tank_temps_json", "status_grid_json", "pump_readings_json", "alarms_json",
        "ack_alarm", "created_at"
    ]
    return pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame(columns=cols)


def get_latest_record(db_file, project_id):
    records_df = get_project_records(db_file, project_id)
    if records_df.empty:
        return None
    latest = records_df.iloc[0].to_dict()
    try:
        latest["status_grid"] = json.loads(latest.get("status_grid_json") or "{}")
    except Exception:
        latest["status_grid"] = {}
    try:
        latest["pump_readings"] = json.loads(latest.get("pump_readings_json") or "{}")
    except Exception:
        latest["pump_readings"] = {}
    try:
        latest["alarms"] = json.loads(latest.get("alarms_json") or "[]")
    except Exception:
        latest["alarms"] = []
    return latest


def has_baseline_record(db_file, project_id):
    conn = sqlite3.connect(db_file)
    row = conn.execute(
        "SELECT COUNT(*) FROM project_records WHERE project_id = ? AND record_phase = ?",
        (project_id, "Baseline Calibration (Cold State)"),
    ).fetchone()
    conn.close()
    return bool(row and row[0] > 0)


def clear_project_records(db_file, project_id):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM project_records WHERE project_id = ?", (project_id,))
    deleted_rows = cursor.rowcount if cursor.rowcount is not None else 0
    conn.commit()
    conn.close()
    return deleted_rows


def clear_project_maintenance_events(db_file, project_id):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM maintenance_events WHERE project_id = ?", (project_id,))
    deleted_rows = cursor.rowcount if cursor.rowcount is not None else 0
    conn.commit()
    conn.close()
    return deleted_rows


def get_maintenance_events(db_file, project_id):
    conn = sqlite3.connect(db_file)
    rows = conn.execute(
        """
         SELECT id, project_id, event_ts, affected_pumps_json, event_type, severity,
             maintenance_status, action_taken, notes, source_record_id, created_at
        FROM maintenance_events
        WHERE project_id = ?
        ORDER BY datetime(event_ts) DESC, id DESC
        """,
        (project_id,),
    ).fetchall()
    conn.close()
    cols = [
        "id", "project_id", "event_ts", "affected_pumps_json", "event_type", "severity",
        "maintenance_status", "action_taken", "notes", "source_record_id", "created_at"
    ]
    return pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame(columns=cols)
