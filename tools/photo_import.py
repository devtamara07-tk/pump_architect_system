"""
Quick photo-based record inserter.

Usage (from workspace root):
    python3 tools/photo_import.py \
        --hioki 1 \
        --date 2026-03-06 --time 16:30 \
        --ch 77.4 76.6 79.0 82.6 83.7 83.1 106.2 107.0 103.5 101.8 \
        --ambient 24 \
        --tank-temp 33.6

    python3 tools/photo_import.py \
        --hioki 2 \
        --date 2026-03-06 --time 16:40 \
        --ch 62.5 62.3 65.8 68.2 68.5 0 90.3 89.4 112.1 0 \
        --ambient 24 \
        --tank-temp 33.2

Notes:
    - --ch takes exactly 10 values (CH1..CH10) in order.
    - For P-08 (HIOKI 2 CH6), value is ignored (pump not installed).
    - Missing amps does NOT mean pump stopped; status stays RUNNING if temp > 0.
    - Use --dry-run to preview without writing.
"""
import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DB_FILE = Path(__file__).resolve().parent.parent / "architect_system.db"
PROJECT_ID = "Submersible Endurance Test 3000.0 Hrs"
METHOD = "Photo Import"

# Channel-to-pump mapping  (index 0 = CH1, index 9 = CH10)
# Each entry: (pump_id, "A" or "B" or "only")
HIOKI_1_MAP = [
    ("P-01", "A"), ("P-01", "B"),
    ("P-02", "only"),
    ("P-05", "A"), ("P-05", "B"),
    ("P-06", "only"),
    ("P-09", "A"), ("P-09", "B"),
    ("P-10", "A"), ("P-10", "B"),
]
HIOKI_2_MAP = [
    ("P-03", "A"), ("P-03", "B"),
    ("P-04", "only"),
    ("P-07", "A"), ("P-07", "B"),
    ("P-08", "only"),  # not installed — ignored
    ("P-11", "A"), ("P-11", "B"),
    ("P-12", "A"), ("P-12", "B"),
]

HIOKI_TO_TANK = {1: "Water Tank 1", 2: "Water Tank 2"}

SKIP_PUMPS = {"P-08"}  # not installed


def _resolve_temps(ch_values: list[float], ch_map: list[tuple[str, str]]) -> dict[str, dict]:
    """Resolve 10 CH values into per-pump temp_a / temp_b / combined."""
    raw: dict[str, dict] = {}
    for i, (pid, role) in enumerate(ch_map):
        if pid in SKIP_PUMPS:
            continue
        raw.setdefault(pid, {})
        val = ch_values[i]
        if role == "A":
            raw[pid]["temp_a"] = val
        elif role == "B":
            raw[pid]["temp_b"] = val
        else:
            raw[pid]["temp_a"] = val

    result = {}
    for pid, temps in raw.items():
        a = temps.get("temp_a")
        b = temps.get("temp_b")
        vals = [v for v in [a, b] if v is not None and v > 0]
        combined = max(vals) if vals else 0.0
        entry = {"temp": round(combined, 1), "amps": 0.0}
        if a is not None:
            entry["temp_ch1"] = round(a, 1)
        if b is not None:
            entry["temp_ch2"] = round(b, 1)
        result[pid] = entry
    return result


def insert_record(
    hioki: int,
    date_str: str,
    time_str: str,
    ch_values: list[float],
    ambient: float,
    tank_temp: float,
    dry_run: bool = False,
) -> dict:
    ch_map = HIOKI_1_MAP if hioki == 1 else HIOKI_2_MAP
    tank_name = HIOKI_TO_TANK[hioki]
    record_ts = f"{date_str} {time_str}:00" if len(time_str) == 5 else f"{date_str} {time_str}"

    pump_readings = _resolve_temps(ch_values, ch_map)

    conn = sqlite3.connect(str(DB_FILE))
    try:
        # Check for duplicate
        dup = conn.execute(
            "SELECT id FROM project_records WHERE project_id=? AND record_ts=? AND COALESCE(active_tanks,'ALL')=? LIMIT 1",
            (PROJECT_ID, record_ts, tank_name),
        ).fetchone()
        if dup:
            return {"status": "skip", "reason": f"Duplicate: existing id={dup[0]} at {record_ts} {tank_name}"}

        # Load latest status grid to carry forward
        row = conn.execute(
            "SELECT status_grid_json FROM project_records WHERE project_id=? ORDER BY datetime(record_ts) DESC, id DESC LIMIT 1",
            (PROJECT_ID,),
        ).fetchone()
        global_grid = json.loads(row[0]) if row and row[0] else {}

        # Update grid for pumps in this reading
        for pid, reading in pump_readings.items():
            prev = global_grid.get(pid, {})
            prev_status = prev.get("status", "STANDBY")
            prev_acc = float(prev.get("acc_hours", 0.0) or 0.0)

            # Calculate delta hours from last record for this tank
            last_ts_row = conn.execute(
                """SELECT record_ts FROM project_records
                   WHERE project_id=? AND COALESCE(active_tanks,'ALL')=?
                   ORDER BY datetime(record_ts) DESC, id DESC LIMIT 1""",
                (PROJECT_ID, tank_name),
            ).fetchone()

            delta_hours = 0.0
            if last_ts_row:
                last_dt = datetime.strptime(last_ts_row[0], "%Y-%m-%d %H:%M:%S")
                curr_dt = datetime.strptime(record_ts, "%Y-%m-%d %H:%M:%S")
                delta_hours = max(0.0, (curr_dt - last_dt).total_seconds() / 3600.0)

            # Status: RUNNING if temp > 0 (pump is active), otherwise STANDBY
            status = "RUNNING" if reading["temp"] > 0 else "STANDBY"
            added = delta_hours if (prev_status == "RUNNING" and status == "RUNNING") else 0.0

            global_grid[pid] = {
                "status": status,
                "prev_status": prev_status,
                "acc_hours_prev": round(prev_acc, 3),
                "added_hours": round(added, 3),
                "acc_hours": round(prev_acc + added, 3),
                "failure_ts": "",
            }

        # Tank temps
        tank_temps = {}
        if hioki == 1:
            tank_temps["Water Tank 1"] = tank_temp
        else:
            tank_temps["Water Tank 2"] = tank_temp

        record_phase = "Routine/Daily Record"

        if dry_run:
            return {
                "status": "dry_run",
                "record_ts": record_ts,
                "tank": tank_name,
                "pumps": {pid: {"temp": r["temp"], "acc": global_grid[pid]["acc_hours"]} for pid, r in pump_readings.items()},
            }

        conn.execute(
            """INSERT INTO project_records (
                project_id, record_phase, record_ts, method, ambient_temp,
                tank_temps_json, status_grid_json, pump_readings_json, alarms_json,
                ack_alarm, active_tanks
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                PROJECT_ID, record_phase, record_ts, METHOD, ambient,
                json.dumps(tank_temps), json.dumps(global_grid),
                json.dumps(pump_readings), json.dumps([]),
                0, tank_name,
            ),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()

        return {
            "status": "inserted",
            "id": new_id,
            "record_ts": record_ts,
            "tank": tank_name,
            "pumps": {pid: {"temp": r["temp"], "acc": global_grid[pid]["acc_hours"]} for pid, r in pump_readings.items()},
        }
    finally:
        # conn.close()  # Removed: do not close cached connection


def main():
    p = argparse.ArgumentParser(description="Insert a record from HIOKI photo readings")
    p.add_argument("--hioki", type=int, required=True, choices=[1, 2], help="HIOKI device number")
    p.add_argument("--date", required=True, help="Record date YYYY-MM-DD")
    p.add_argument("--time", required=True, help="Record time HH:MM")
    p.add_argument("--ch", nargs=10, type=float, required=True, help="CH1..CH10 values in order")
    p.add_argument("--ambient", type=float, default=0.0, help="Ambient temperature")
    p.add_argument("--tank-temp", type=float, default=0.0, help="Tank water temperature")
    p.add_argument("--dry-run", action="store_true", help="Preview without writing")

    args = p.parse_args()
    result = insert_record(args.hioki, args.date, args.time, args.ch, args.ambient, args.tank_temp, args.dry_run)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
