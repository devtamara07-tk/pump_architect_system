import argparse
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_METHOD = "Excel Import"


@dataclass
class ImportStats:
    rows_total: int = 0
    rows_in_window: int = 0
    groups_total: int = 0
    groups_skipped_duplicate: int = 0
    groups_skipped_invalid_tank: int = 0
    groups_inserted: int = 0
    pump_rows_skipped: int = 0
    alarm_rows: int = 0


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            if pd.isna(value):
                return None
            return float(value)
        except Exception:
            return None
    text = str(value).strip()
    if not text or text in {"--", "-", "nan", "NaN", "None"}:
        return None
    try:
        return float(text)
    except Exception:
        return None


def _is_alarm(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip().upper()
    if text in {"1", "TRUE", "Y", "YES", "ALARM"}:
        return True
    num = _to_float(value)
    return bool(num and num > 0)


def _normalize_col(name: str) -> str:
    return str(name).strip().replace("\n", "").replace(" ", "")


def _build_column_lookup(df: pd.DataFrame) -> dict[str, str]:
    normalized = {_normalize_col(c): c for c in df.columns}

    aliases = {
        "date": ["日期", "Date"],
        "time": ["時間", "时间", "Time"],
        "tank": ["測試槽", "测试槽", "水槽", "WaterTankNo", "WaterTank", "Tank"],
        "pump_id": ["泵浦編號", "泵浦编号", "PumpID", "Pump Id", "Pump"],
        "sn": ["序號", "序号", "SN", "Serial", "SerialNo"],
        "temp_a": ["定子溫度A", "定子温度A", "StatTempA", "StatorTempA", "定子溫度ACH1", "定子温度ACH1"],
        "temp_b": ["定子溫度B", "定子温度B", "StatTempB", "StatorTempB", "定子溫度BCH2", "定子温度BCH2"],
        "ambient": ["環境溫度", "环境温度", "TAmb", "Ambient", "AmbientTemp"],
        "current": ["運轉電流(A)", "运转电流(A)", "運轉電流", "运转电流", "Current", "Current(A)"],
        "alarm": ["Alarm", "警報", "警报"],
        "tank_temp_1": ["1號水槽水溫", "1號水槽水溫度", "1号水槽水温", "1号水槽水温度", "WaterTankTemp1", "TankTemp1"],
        "tank_temp_2": ["2號水槽水溫", "2號水槽水溫度", "2号水槽水温", "2号水槽水温度", "WaterTankTemp2", "TankTemp2"],
        "op_status": ["運行狀態", "运行状态", "OperatingStatus", "OperateStatus", "RunStatus", "RunState"],
    }

    result: dict[str, str] = {}
    for key, candidates in aliases.items():
        for alias in candidates:
            normalized_alias = _normalize_col(alias)
            if normalized_alias in normalized:
                result[key] = normalized[normalized_alias]
                break
    return result


def _normalize_tank_name(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    if text.startswith("Water Tank"):
        return text

    if "1" in text:
        return "Water Tank 1"
    if "2" in text:
        return "Water Tank 2"
    if "3" in text:
        return "Water Tank 3"
    if "4" in text:
        return "Water Tank 4"

    return text


def _build_record_ts(date_value: Any, time_value: Any) -> datetime | None:
    dt_text = f"{str(date_value).strip()} {str(time_value).strip()}".strip()
    if not dt_text:
        return None
    parsed = pd.to_datetime(dt_text, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime()


def _load_source(path: Path, sheet: str | None) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)

    if suffix in {".xlsx", ".xls"}:
        try:
            return pd.read_excel(path, sheet_name=sheet) if sheet else pd.read_excel(path)
        except ImportError as exc:
            raise RuntimeError(
                "Excel engine is missing. Install openpyxl to read .xlsx files."
            ) from exc

    raise RuntimeError(f"Unsupported file type: {suffix}. Use .xlsx, .xls, or .csv")


def _ensure_project_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS project_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            record_phase TEXT NOT NULL,
            record_ts TEXT NOT NULL,
            method TEXT,
            ambient_temp REAL,
            tank_temps_json TEXT,
            status_grid_json TEXT,
            pump_readings_json TEXT,
            alarms_json TEXT,
            ack_alarm INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    try:
        conn.execute("ALTER TABLE project_records ADD COLUMN active_tanks TEXT DEFAULT 'ALL'")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE projects ADD COLUMN tank_start_dates TEXT")
    except sqlite3.OperationalError:
        pass


def _load_project_context(conn: sqlite3.Connection, project_id: str) -> tuple[list[str], set[str], dict[str, str]]:
    row = conn.execute(
        "SELECT tanks, layout FROM projects WHERE project_id = ?",
        (project_id,),
    ).fetchone()
    if not row:
        raise RuntimeError(f"Project not found: {project_id}")

    tanks_text, layout_json = row
    tanks = [t.strip() for t in str(tanks_text or "Water Tank 1").split("||") if t.strip()]

    pump_rows = conn.execute(
        "SELECT pump_id FROM pumps WHERE project_id = ?",
        (project_id,),
    ).fetchall()
    valid_pumps = {str(r[0]).strip() for r in pump_rows if str(r[0]).strip()}

    pump_tank_lookup: dict[str, str] = {}
    if layout_json:
        try:
            layout_df = pd.read_json(StringIO(layout_json))
            if {"Pump ID", "Assigned Tank"}.issubset(set(layout_df.columns)):
                for _, row_df in layout_df.iterrows():
                    pid = str(row_df.get("Pump ID", "")).strip()
                    tname = str(row_df.get("Assigned Tank", "")).strip()
                    if pid and tname:
                        pump_tank_lookup[pid] = tname
        except Exception:
            pass

    return tanks, valid_pumps, pump_tank_lookup


def _load_existing_state(conn: sqlite3.Connection, project_id: str) -> tuple[dict[str, Any], dict[str, datetime], dict[str, datetime], set[str], dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT record_ts, status_grid_json, pump_readings_json, COALESCE(active_tanks, 'ALL')
        FROM project_records
        WHERE project_id = ?
        ORDER BY datetime(record_ts) ASC, id ASC
        """,
        (project_id,),
    ).fetchall()

    last_grid: dict[str, Any] = {}
    last_ts_by_tank: dict[str, datetime] = {}
    last_ts_by_pump: dict[str, datetime] = {}
    baseline_done: set[str] = set()

    baseline_rows = conn.execute(
        """
        SELECT COALESCE(active_tanks, 'ALL')
        FROM project_records
        WHERE project_id = ? AND record_phase = 'Baseline Calibration (Cold State)'
        """,
        (project_id,),
    ).fetchall()
    for (active_tanks,) in baseline_rows:
        if active_tanks == "ALL":
            # Existing legacy data may not track tanks; importer still keeps per-group active_tanks.
            continue
        for tank_name in str(active_tanks or "").split("||"):
            tank_name = tank_name.strip()
            if tank_name:
                baseline_done.add(tank_name)

    for rec_ts, status_grid_json, pump_readings_json, active_tanks in rows:
        try:
            parsed_ts = pd.to_datetime(rec_ts).to_pydatetime()
        except Exception:
            continue

        try:
            grid = json.loads(status_grid_json or "{}")
            if isinstance(grid, dict):
                last_grid = grid
        except Exception:
            pass

        try:
            readings = json.loads(pump_readings_json or "{}")
            if isinstance(readings, dict):
                for pid in readings.keys():
                    pid = str(pid).strip()
                    if pid:
                        last_ts_by_pump[pid] = parsed_ts
        except Exception:
            pass

        if active_tanks and active_tanks != "ALL":
            for tname in str(active_tanks).split("||"):
                tname = tname.strip()
                if tname:
                    last_ts_by_tank[tname] = parsed_ts

    project_row = conn.execute(
        "SELECT tank_start_dates FROM projects WHERE project_id = ?",
        (project_id,),
    ).fetchone()
    tank_start_dates = {}
    if project_row and project_row[0]:
        try:
            tank_start_dates = json.loads(project_row[0])
        except Exception:
            tank_start_dates = {}

    return last_grid, last_ts_by_tank, last_ts_by_pump, baseline_done, tank_start_dates


def _in_window(ts: datetime, start_date: datetime | None, end_date: datetime | None) -> bool:
    if start_date and ts.date() < start_date.date():
        return False
    if end_date and ts.date() > end_date.date():
        return False
    return True


def run_import(
    db_file: Path,
    project_id: str,
    source_file: Path,
    sheet: str | None,
    start_date: datetime | None,
    end_date: datetime | None,
    dry_run: bool,
    method: str,
) -> tuple[ImportStats, list[str]]:
    stats = ImportStats()
    warnings: list[str] = []

    src_df = _load_source(source_file, sheet)
    stats.rows_total = len(src_df.index)

    col_map = _build_column_lookup(src_df)
    required = ["date", "time", "tank", "pump_id"]
    missing = [k for k in required if k not in col_map]
    if missing:
        raise RuntimeError(f"Missing required source columns: {', '.join(missing)}")

    src_df = src_df.copy()
    src_df["_record_ts"] = src_df.apply(
        lambda r: _build_record_ts(r[col_map["date"]], r[col_map["time"]]), axis=1
    )
    src_df = src_df[src_df["_record_ts"].notna()].copy()

    if "tank" in col_map:
        src_df["_tank_norm"] = src_df[col_map["tank"]].map(_normalize_tank_name)
    else:
        src_df["_tank_norm"] = ""

    if start_date or end_date:
        src_df = src_df[src_df["_record_ts"].map(lambda x: _in_window(x, start_date, end_date))]
    stats.rows_in_window = len(src_df.index)

    if src_df.empty:
        return stats, ["No rows found in date window after parsing Date+Time."]

    src_df.sort_values(by=["_record_ts", "_tank_norm"], inplace=True)

    conn = sqlite3.connect(str(db_file))
    try:
        _ensure_project_schema(conn)
        project_tanks, valid_pumps, pump_tank_lookup = _load_project_context(conn, project_id)
        last_grid, last_ts_by_tank, last_ts_by_pump, baseline_done, tank_start_dates = _load_existing_state(conn, project_id)

        # Work on mutable global status snapshot.
        global_grid: dict[str, Any] = dict(last_grid) if isinstance(last_grid, dict) else {}

        grouped = src_df.groupby(["_record_ts", "_tank_norm"], dropna=False)

        for (record_ts, tank_name), group_df in grouped:
            stats.groups_total += 1
            tank_name = str(tank_name or "").strip()

            if not tank_name or tank_name not in project_tanks:
                stats.groups_skipped_invalid_tank += 1
                warnings.append(
                    f"Skip group @ {record_ts}: unknown tank '{tank_name}'."
                )
                continue

            active_tanks_str = tank_name
            record_ts_text = record_ts.strftime("%Y-%m-%d %H:%M:%S")

            dup_row = conn.execute(
                """
                SELECT id FROM project_records
                WHERE project_id = ? AND record_ts = ? AND method = ?
                  AND COALESCE(active_tanks, 'ALL') = ?
                LIMIT 1
                """,
                (project_id, record_ts_text, method, active_tanks_str),
            ).fetchone()
            if dup_row:
                stats.groups_skipped_duplicate += 1
                continue

            # Phase policy: first import event per tank is baseline unless baseline already exists for that tank.
            is_baseline = tank_name not in baseline_done
            record_phase = "Baseline Calibration (Cold State)" if is_baseline else "Routine/Daily Record"

            # Build per-pump latest row in this event.
            per_pump_rows: dict[str, pd.Series] = {}
            for _, row in group_df.iterrows():
                pid = str(row[col_map["pump_id"]]).strip()
                if not pid:
                    stats.pump_rows_skipped += 1
                    continue
                if valid_pumps and pid not in valid_pumps:
                    stats.pump_rows_skipped += 1
                    warnings.append(f"Unknown pump '{pid}' @ {record_ts_text}; row skipped.")
                    continue

                # If layout mapping exists, enforce tank consistency when possible.
                mapped_tank = pump_tank_lookup.get(pid)
                if mapped_tank and mapped_tank != tank_name:
                    stats.pump_rows_skipped += 1
                    warnings.append(
                        f"Pump '{pid}' belongs to '{mapped_tank}', not '{tank_name}' @ {record_ts_text}; row skipped."
                    )
                    continue

                per_pump_rows[pid] = row

            if not per_pump_rows:
                warnings.append(f"No valid pump rows in group @ {record_ts_text} {tank_name}; group skipped.")
                continue

            pump_readings: dict[str, Any] = {}
            alarms: list[dict[str, Any]] = []

            for pid, row in per_pump_rows.items():
                temp_a = _to_float(row[col_map["temp_a"]]) if "temp_a" in col_map else None
                temp_b = _to_float(row[col_map["temp_b"]]) if "temp_b" in col_map else None
                amps = _to_float(row[col_map["current"]]) if "current" in col_map else None
                amps = amps if amps is not None else 0.0

                # CH1/CH2 consolidation: if both sensors exist, pick the hotter stator reading.
                temps = [t for t in [temp_a, temp_b] if t is not None]
                temp_combined = max(temps) if temps else None

                # Status: a logged record means the pump is active unless an explicit standby/
                # maintenance flag is present. Missing current (NaN/0) only means the reading
                # wasn't taken that cycle — not that the pump stopped.
                _STANDBY_STATUS_VALUES = {
                    "待機", "停機", "停机", "維修", "维修",
                    "STANDBY", "MAINTENANCE", "STOPPED", "PAUSED",
                }
                if is_baseline:
                    status = "STANDBY"
                elif "op_status" in col_map:
                    raw_op = str(row[col_map["op_status"]] or "").strip()
                    status = "STANDBY" if raw_op in _STANDBY_STATUS_VALUES else "RUNNING"
                else:
                    status = "RUNNING"

                prev = global_grid.get(pid, {}) if isinstance(global_grid, dict) else {}
                prev_status = str(prev.get("status", "STANDBY")).upper()
                prev_acc = float(prev.get("acc_hours", 0.0) or 0.0)

                # Runtime accumulation should follow each pump's own cadence from source rows.
                previous_pump_ts = last_ts_by_pump.get(pid)
                delta_hours = 0.0
                if previous_pump_ts and not is_baseline:
                    delta_hours = max(0.0, (record_ts - previous_pump_ts).total_seconds() / 3600.0)

                added_hours = delta_hours if (prev_status == "RUNNING" and status == "RUNNING" and not is_baseline) else 0.0

                global_grid[pid] = {
                    "status": status,
                    "prev_status": prev_status,
                    "acc_hours_prev": round(prev_acc, 3),
                    "added_hours": round(added_hours, 3),
                    "acc_hours": round(prev_acc + added_hours, 3),
                    "failure_ts": "",
                }

                pump_payload = {"amps": round(float(amps), 3)}
                if temp_combined is not None:
                    pump_payload["temp"] = round(float(temp_combined), 3)
                if temp_a is not None:
                    pump_payload["temp_ch1"] = round(float(temp_a), 3)
                if temp_b is not None:
                    pump_payload["temp_ch2"] = round(float(temp_b), 3)
                pump_readings[pid] = pump_payload
                last_ts_by_pump[pid] = record_ts

                if "alarm" in col_map and _is_alarm(row[col_map["alarm"]]):
                    alarms.append({
                        "pump_id": pid,
                        "alarms": ["Imported alarm flag from Excel source"],
                    })

            stats.alarm_rows += len(alarms)

            ambient_temp = 0.0
            if "ambient" in col_map:
                ambient_vals = [_to_float(v) for v in group_df[col_map["ambient"]].tolist()]
                ambient_vals = [v for v in ambient_vals if v is not None]
                if ambient_vals:
                    ambient_temp = float(ambient_vals[0])

            tank_temps: dict[str, Any] = {}
            if "tank_temp_1" in col_map and "Water Tank 1" in project_tanks:
                vals = [_to_float(v) for v in group_df[col_map["tank_temp_1"]].tolist()]
                vals = [v for v in vals if v is not None]
                if vals:
                    tank_temps["Water Tank 1"] = float(vals[0])
            if "tank_temp_2" in col_map and "Water Tank 2" in project_tanks:
                vals = [_to_float(v) for v in group_df[col_map["tank_temp_2"]].tolist()]
                vals = [v for v in vals if v is not None]
                if vals:
                    tank_temps["Water Tank 2"] = float(vals[0])

            if not dry_run:
                conn.execute(
                    """
                    INSERT INTO project_records (
                        project_id, record_phase, record_ts, method, ambient_temp,
                        tank_temps_json, status_grid_json, pump_readings_json, alarms_json,
                        ack_alarm, active_tanks
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        record_phase,
                        record_ts_text,
                        method,
                        ambient_temp,
                        json.dumps(tank_temps),
                        json.dumps(global_grid),
                        json.dumps(pump_readings),
                        json.dumps(alarms),
                        1 if alarms else 0,
                        active_tanks_str,
                    ),
                )

            if is_baseline:
                baseline_done.add(tank_name)
            last_ts_by_tank[tank_name] = record_ts
            if not tank_start_dates.get(tank_name):
                tank_start_dates[tank_name] = record_ts_text

            stats.groups_inserted += 1

        if not dry_run:
            conn.execute(
                "UPDATE projects SET tank_start_dates = ? WHERE project_id = ?",
                (json.dumps(tank_start_dates), project_id),
            )
            conn.commit()

    finally:
        conn.close()

    return stats, warnings


def _parse_date(text: str | None) -> datetime | None:
    if not text:
        return None
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        raise RuntimeError(f"Invalid date: {text}")
    return parsed.to_pydatetime()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Hidden reusable fixture: import legacy Excel/CSV recordings into project_records."
    )
    parser.add_argument("--project-id", required=True, help="Target project_id in architect_system.db")
    parser.add_argument("--source-file", required=True, help="Path to source .xlsx/.xls/.csv")
    parser.add_argument("--db-file", default="architect_system.db", help="SQLite database path")
    parser.add_argument("--sheet", default=None, help="Excel sheet name (optional)")
    parser.add_argument("--start-date", default=None, help="Import window start, e.g. 2026/02/04")
    parser.add_argument("--end-date", default=None, help="Import window end, e.g. 2026/02/13")
    parser.add_argument("--method", default=DEFAULT_METHOD, help="Method label stored in records")
    parser.add_argument("--dry-run", action="store_true", help="Validate and simulate without writing DB")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    db_file = Path(args.db_file).resolve()
    source_file = Path(args.source_file).resolve()

    if not source_file.exists():
        raise RuntimeError(f"Source file not found: {source_file}")

    stats, warnings = run_import(
        db_file=db_file,
        project_id=args.project_id,
        source_file=source_file,
        sheet=args.sheet,
        start_date=_parse_date(args.start_date),
        end_date=_parse_date(args.end_date),
        dry_run=bool(args.dry_run),
        method=str(args.method).strip() or DEFAULT_METHOD,
    )

    print("\n=== Import Summary ===")
    print(f"rows_total: {stats.rows_total}")
    print(f"rows_in_window: {stats.rows_in_window}")
    print(f"groups_total: {stats.groups_total}")
    print(f"groups_inserted: {stats.groups_inserted}")
    print(f"groups_skipped_duplicate: {stats.groups_skipped_duplicate}")
    print(f"groups_skipped_invalid_tank: {stats.groups_skipped_invalid_tank}")
    print(f"pump_rows_skipped: {stats.pump_rows_skipped}")
    print(f"alarm_rows: {stats.alarm_rows}")
    print(f"mode: {'DRY RUN' if args.dry_run else 'COMMIT'}")

    if warnings:
        print("\n=== Warnings ===")
        for item in warnings:
            print(f"- {item}")


if __name__ == "__main__":
    main()
