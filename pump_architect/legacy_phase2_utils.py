import datetime

import pandas as pd


def get_default_record_datetime(draft, parse_ts_fn):
    default_record_dt = datetime.datetime.now()
    saved_record_ts = str(draft.get("record_ts", "")).strip()
    if saved_record_ts:
        try:
            default_record_dt = parse_ts_fn(saved_record_ts)
        except Exception:
            pass
    return default_record_dt


def clamp_time_to_work_window(default_record_dt, work_start, work_end):
    default_time = default_record_dt.time().replace(second=0, microsecond=0)
    if default_time < work_start:
        default_time = work_start
    if default_time > work_end:
        default_time = work_end
    return default_time


def evaluate_timestamp_window(record_time, work_start, work_end):
    if record_time < work_start or record_time > work_end:
        return False, "Record Time must be within working hours: 08:00 to 17:00."
    return True, None


def parse_last_timestamp(latest_record, parse_ts_fn):
    last_ts = None
    if latest_record and latest_record.get("record_ts"):
        try:
            last_ts = parse_ts_fn(latest_record["record_ts"])
        except Exception:
            last_ts = None
    return last_ts


def compute_global_delta(record_phase, ts_valid, record_ts, last_ts):
    if record_phase == "Baseline Calibration (Cold State)":
        return ts_valid, 0.0, None

    if last_ts is None or not ts_valid:
        return ts_valid, 0.0, None

    global_delta = max(0.0, (record_ts - last_ts).total_seconds() / 3600.0)
    if record_ts < last_ts:
        return False, global_delta, "Record timestamp cannot be earlier than the last saved record timestamp."
    return ts_valid, global_delta, None


def build_status_rows(pump_ids, previous_grid, record_phase):
    status_rows = []
    for pid in pump_ids:
        prev = previous_grid.get(pid, {}) if isinstance(previous_grid, dict) else {}
        prev_status = str(prev.get("status", "STANDBY")).upper()
        prev_acc = float(prev.get("acc_hours", 0.0) or 0.0)
        status_rows.append({
            "Pump ID": pid,
            "Previous Status": prev_status,
            "Accumulated Time (hrs)": prev_acc,
            "New Status": "STANDBY" if record_phase == "Baseline Calibration (Cold State)" else prev_status,
            "Failure DateTime (YYYY-MM-DD HH:MM:SS)": "",
        })
    return pd.DataFrame(status_rows)
