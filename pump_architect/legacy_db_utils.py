import json
import sqlite3

import pandas as pd

from pump_architect.db.connection import get_legacy_conn


def get_project_records(db_file, project_id):
    conn = get_legacy_conn(db_file)
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
    conn = get_legacy_conn(db_file)
    row = conn.execute(
        "SELECT COUNT(*) FROM project_records WHERE project_id = ? AND record_phase = ?",
        (project_id, "Baseline Calibration (Cold State)"),
    ).fetchone()
    conn.close()
    return bool(row and row[0] > 0)


def clear_project_records(db_file, project_id):
    conn = get_legacy_conn(db_file)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM project_records WHERE project_id = ?", (project_id,))
    deleted_rows = cursor.rowcount if cursor.rowcount is not None else 0

    # Clearing all run-test records should also reset per-tank activation history.
    # Otherwise Phase 0 still shows tanks as active even though no baseline/data remains.
    project_row = cursor.execute(
        "SELECT tanks FROM projects WHERE project_id = ?",
        (project_id,),
    ).fetchone()
    tanks = project_row[0].split("||") if project_row and project_row[0] else ["Water Tank 1"]
    reset_start_dates = json.dumps({tank_name: None for tank_name in tanks})
    cursor.execute(
        "UPDATE projects SET tank_start_dates = ? WHERE project_id = ?",
        (reset_start_dates, project_id),
    )

    conn.commit()
    conn.close()
    return deleted_rows


def clear_project_maintenance_events(db_file, project_id):
    conn = get_legacy_conn(db_file)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM maintenance_events WHERE project_id = ?", (project_id,))
    deleted_rows = cursor.rowcount if cursor.rowcount is not None else 0
    conn.commit()
    conn.close()
    return deleted_rows


def get_maintenance_events(db_file, project_id):
    conn = get_legacy_conn(db_file)
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


# Per-tank start-date helpers

def get_tank_start_dates(db_file, project_id):
    """Return {tank_name: start_ts_str_or_None}.

    Backward-compat migration: if the project already has records but no
    tank_start_dates, auto-activate all tanks using the project created_at so
    the wizard doesn't block existing single-tank projects.
    """
    conn = get_legacy_conn(db_file)
    row = conn.execute(
        "SELECT tanks, tank_start_dates, created_at FROM projects WHERE project_id = ?",
        (project_id,),
    ).fetchone()
    if not row:
        conn.close()
        return {}

    tanks_str, tsd_json, created_at = row
    tanks = tanks_str.split("||") if tanks_str else ["Water Tank 1"]

    try:
        tsd = json.loads(tsd_json) if tsd_json else {}
    except Exception:
        tsd = {}

    result = {t: tsd.get(t) for t in tanks}

    # Migration: if this project already has records but no start dates, auto-fill
    if not any(result.values()):
        has_records = conn.execute(
            "SELECT COUNT(*) FROM project_records WHERE project_id = ?", (project_id,)
        ).fetchone()[0]
        if has_records > 0:
            fallback_ts = created_at or "2025-01-01 08:00:00"
            result = {t: fallback_ts for t in tanks}
            conn.execute(
                "UPDATE projects SET tank_start_dates = ? WHERE project_id = ?",
                (json.dumps(result), project_id),
            )
            conn.commit()

    conn.close()
    return result


def save_tank_start_dates(db_file, project_id, tank_start_dates_dict):
    """Persist the full {tank_name: ts_str} dict to projects.tank_start_dates."""
    conn = get_legacy_conn(db_file)
    conn.execute(
        "UPDATE projects SET tank_start_dates = ? WHERE project_id = ?",
        (json.dumps(tank_start_dates_dict), project_id),
    )
    conn.commit()
    conn.close()


def get_latest_record_for_tank(db_file, project_id, tank_name):
    """Return the most-recent record that included tank_name.

    Existing records without the active_tanks column are treated as 'ALL'.
    """
    conn = get_legacy_conn(db_file)
    rows = conn.execute(
        """
        SELECT id, project_id, record_phase, record_ts, method, ambient_temp,
               tank_temps_json, status_grid_json, pump_readings_json, alarms_json,
               ack_alarm, created_at,
               COALESCE(active_tanks, 'ALL') AS active_tanks
        FROM project_records
        WHERE project_id = ?
        ORDER BY datetime(record_ts) DESC, id DESC
        """,
        (project_id,),
    ).fetchall()
    conn.close()

    col_names = [
        "id", "project_id", "record_phase", "record_ts", "method", "ambient_temp",
        "tank_temps_json", "status_grid_json", "pump_readings_json", "alarms_json",
        "ack_alarm", "created_at", "active_tanks",
    ]
    for row in rows:
        active = row[12]
        if active == "ALL" or tank_name in active.split("||"):
            rec = dict(zip(col_names, row))
            try:
                rec["status_grid"] = json.loads(rec.get("status_grid_json") or "{}")
            except Exception:
                rec["status_grid"] = {}
            return rec
    return None


def has_baseline_record_for_tank(db_file, project_id, tank_name):
    """True if at least one baseline record covers tank_name."""
    conn = get_legacy_conn(db_file)
    rows = conn.execute(
        """
        SELECT COALESCE(active_tanks, 'ALL')
        FROM project_records
        WHERE project_id = ? AND record_phase = ?
        """,
        (project_id, "Baseline Calibration (Cold State)"),
    ).fetchall()
    conn.close()
    for (active_tanks,) in rows:
        if active_tanks == "ALL" or tank_name in active_tanks.split("||"):
            return True
    return False
