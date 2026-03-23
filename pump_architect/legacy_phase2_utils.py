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
def compute_global_delta(record_phase, ts_valid, record_ts, last_ts):
    if record_phase == "Baseline Calibration (Cold State)":
        return ts_valid, 0.0, None

    if last_ts is None or not ts_valid:
        return ts_valid, 0.0, None

    global_delta = max(0.0, (record_ts - last_ts).total_seconds() / 3600.0)
    if record_ts < last_ts:
        return False, global_delta, "Record timestamp cannot be earlier than the last saved record timestamp."
    return ts_valid, global_delta, None


def compute_per_tank_deltas(record_phase, ts_valid, record_ts, active_tank_names, latest_records_by_tank, parse_ts_fn):
    """Return (ts_valid, tank_deltas, error_msg).

    tank_deltas = {tank_name: hours_since_last_record_for_that_tank}
    For baseline records every delta is 0.  For tanks with no prior record the
    delta is 0 (first entry — they are being activated this session).
    """
    if record_phase == "Baseline Calibration (Cold State)":
        return ts_valid, {t: 0.0 for t in active_tank_names}, None

    tank_deltas = {}
    for tank_name in active_tank_names:
        tank_latest = latest_records_by_tank.get(tank_name)
        last_ts = None
        if tank_latest and tank_latest.get("record_ts"):
            try:
                last_ts = parse_ts_fn(tank_latest["record_ts"])
            except Exception:
                pass

        if last_ts is None or not ts_valid:
            tank_deltas[tank_name] = 0.0
            continue

        if record_ts < last_ts:
            return (
                False,
                tank_deltas,
                f"Record timestamp cannot be earlier than the last saved record for "
                f"{tank_name} ({last_ts.strftime('%Y-%m-%d %H:%M:%S')}).",
            )

        tank_deltas[tank_name] = max(0.0, (record_ts - last_ts).total_seconds() / 3600.0)

    return ts_valid, tank_deltas, None


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


def process_phase2_confirmation(
    edited_status_df, record_phase, global_delta, last_ts, record_ts, parse_ts_fn,
    tank_deltas=None, pump_tank_lookup=None, last_ts_by_tank=None,
):
    """Compute the status grid for the current record.

    When tank_deltas and pump_tank_lookup are supplied the per-pump delta is
    resolved from the pump's assigned tank instead of global_delta.  The
    last_ts_by_tank dict provides the per-tank last timestamp needed for
    RUNNING→FAILED micro-delta calculations.
    """
    errors = []
    maintenance_candidates = []
    computed_grid = {}

    for _, row in edited_status_df.iterrows():
        pid = str(row.get("Pump ID", "")).strip()
        prev_status = str(row.get("Previous Status", "STANDBY")).upper()
        new_status = str(row.get("New Status", prev_status)).upper()
        prev_acc = float(row.get("Accumulated Time (hrs)", 0.0) or 0.0)
        failure_ts_text = str(row.get("Failure DateTime (YYYY-MM-DD HH:MM:SS)", "")).strip()
        added_hours = 0.0

        if record_phase == "Baseline Calibration (Cold State)":
            new_status = "STANDBY"
            added_hours = 0.0
        elif prev_status == "RUNNING" and new_status == "RUNNING":
            if tank_deltas and pump_tank_lookup:
                tank_name = pump_tank_lookup.get(pid, "")
                added_hours = tank_deltas.get(tank_name, global_delta)
            else:
                added_hours = global_delta
        elif prev_status in ["STANDBY", "PAUSED", "FAILED"] and new_status == prev_status:
            added_hours = 0.0
        elif prev_status == "STANDBY" and new_status == "RUNNING":
            added_hours = 0.0
        elif prev_status == "RUNNING" and new_status in ["PAUSED", "FAILED"]:
            if not failure_ts_text:
                errors.append(f"{pid}: failure datetime is required for RUNNING -> {new_status}.")
            else:
                try:
                    failure_ts = parse_ts_fn(failure_ts_text)
                    # Resolve the effective last timestamp: per-tank if available
                    effective_last_ts = last_ts
                    if last_ts_by_tank and pump_tank_lookup:
                        tank_name = pump_tank_lookup.get(pid, "")
                        effective_last_ts = last_ts_by_tank.get(tank_name, last_ts)
                    if effective_last_ts is None:
                        errors.append(f"{pid}: cannot calculate micro-delta without a previous record.")
                    elif failure_ts < effective_last_ts or failure_ts > record_ts:
                        errors.append(f"{pid}: failure datetime must be between last record and current record timestamp.")
                    else:
                        added_hours = (failure_ts - effective_last_ts).total_seconds() / 3600.0
                        maintenance_candidates.append(pid)
                except Exception:
                    errors.append(f"{pid}: invalid failure datetime format.")
        else:
            added_hours = 0.0

        computed_grid[pid] = {
            "status": new_status,
            "prev_status": prev_status,
            "acc_hours_prev": round(prev_acc, 3),
            "added_hours": round(added_hours, 3),
            "acc_hours": round(prev_acc + added_hours, 3),
            "failure_ts": failure_ts_text,
        }

    return errors, sorted(list(set(maintenance_candidates))), computed_grid
