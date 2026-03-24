def build_limits_lookup(limits_df):
    limits_lookup = {}
    if limits_df is not None and not limits_df.empty and "Pump ID" in limits_df.columns:
        for _, row in limits_df.iterrows():
            limits_lookup[str(row.get("Pump ID", ""))] = row
    return limits_lookup


def build_temp_editor_rows(unit, saved_temp_tables, previous_readings, safe_float_fn, rendered_temp_pumps):
    hw_name = unit["hardware"]
    saved_rows = saved_temp_tables.get(hw_name, []) if isinstance(saved_temp_tables, dict) else []
    saved_lookup = {str(row.get("CH", "")).strip(): row for row in saved_rows}
    editor_rows = []

    for row in unit["rows"]:
        rendered_temp_pumps.add(row["Pump ID"])
        prior_temp = safe_float_fn(previous_readings.get(row["Pump ID"], {}).get("temp"), 0.0)
        saved_value = safe_float_fn(saved_lookup.get(row["CH"], {}).get("Reading (C)"), prior_temp)
        editor_rows.append({
            "CH": row["CH"],
            "Sensor Name": row["Sensor Name"],
            "Pump ID": row["Pump ID"],
            "Status": row["Status"],
            "Measurement Type": row["Measurement Type"],
            "Reading (C)": float(saved_value),
        })

    return editor_rows


def classify_temp_mapping_gaps(pump_ids, status_grid, rendered_temp_pumps, has_temp_hardware):
    unmapped_temp_pumps = []
    fallback_temp_pumps = []
    for pid in pump_ids:
        status = str(status_grid.get(pid, {}).get("status", "STANDBY")).upper()
        if status in ["RUNNING", "STANDBY", "PAUSED"] and pid not in rendered_temp_pumps:
            if has_temp_hardware:
                unmapped_temp_pumps.append(pid)
            else:
                fallback_temp_pumps.append((pid, status))
    return unmapped_temp_pumps, fallback_temp_pumps


def build_clamp_editor_rows(unit, saved_clamp_tables, previous_readings, limits_lookup, safe_float_fn, rendered_clamp_pumps):
    hw_name = unit["hardware"]
    saved_rows = saved_clamp_tables.get(hw_name, []) if isinstance(saved_clamp_tables, dict) else []
    saved_lookup = {str(row.get("Pump ID", "")).strip(): row for row in saved_rows}
    editor_rows = []

    for row in unit["rows"]:
        rendered_clamp_pumps.add(row["Pump ID"])
        pid = row["Pump ID"]
        lim = limits_lookup.get(pid)
        max_current = safe_float_fn(lim.get("Max Current (A)", 0.0) if lim is not None else 0.0, 0.0)
        prior_amps = safe_float_fn(previous_readings.get(pid, {}).get("amps"), 0.0)
        current_value = safe_float_fn(saved_lookup.get(pid, {}).get("Reading (A)"), prior_amps)
        editor_rows.append({
            "Pump ID": pid,
            "Sensor Name": row["Sensor Name"],
            "Status": row["Status"],
            "Max Current (A)": float(max_current),
            "Reading (A)": float(current_value),
        })

    return editor_rows


def classify_clamp_mapping_gaps(pump_ids, status_grid, rendered_clamp_pumps, has_clamp_hardware):
    unmapped_clamp_pumps = []
    fallback_clamp_pumps = []
    for pid in pump_ids:
        status = str(status_grid.get(pid, {}).get("status", "STANDBY")).upper()
        if status == "RUNNING" and pid not in rendered_clamp_pumps:
            if has_clamp_hardware:
                unmapped_clamp_pumps.append(pid)
            else:
                fallback_clamp_pumps.append(pid)
    return unmapped_clamp_pumps, fallback_clamp_pumps


def ensure_default_pump_readings(pump_ids, status_grid, pump_readings, previous_readings, safe_float_fn):
    for pid in pump_ids:
        status = str(status_grid.get(pid, {}).get("status", "STANDBY")).upper()
        if status == "FAILED":
            pump_readings[pid] = {"temp": None, "amps": None, "status": status}
        elif pid not in pump_readings:
            pump_readings[pid] = {
                "temp": safe_float_fn(previous_readings.get(pid, {}).get("temp"), 0.0),
                "amps": 0.0 if status in ["STANDBY", "PAUSED"] else safe_float_fn(previous_readings.get(pid, {}).get("amps"), 0.0),
                "status": status,
            }
    return pump_readings


def process_phase4_confirmation(
    temp_tables,
    clamp_tables,
    fallback_temp_values,
    fallback_clamp_values,
    fallback_temp_pumps,
    fallback_clamp_pumps,
    pump_ids,
    status_grid,
    previous_readings,
    pump_readings,
    safe_float_fn,
    aggregate_temperature_for_pump_fn,
):
    errors = []
    temp_tables_payload = {}
    clamp_tables_payload = {}
    temp_candidates = {}
    current_candidates = {}

    for hw_name, edited_df in temp_tables.items():
        temp_tables_payload[hw_name] = edited_df.to_dict("records")
        for _, row in edited_df.iterrows():
            pump_id = str(row.get("Pump ID", "")).strip()
            status = str(row.get("Status", "STANDBY")).upper()
            reading = row.get("Reading (C)")
            if pump_id and status in ["RUNNING", "STANDBY", "PAUSED"]:
                if reading != reading:
                    errors.append(f"{hw_name} {row.get('CH', '')} for {pump_id}: temperature is required.")
                    continue
                temp_candidates.setdefault(pump_id, []).append({
                    "measurement_type": row.get("Measurement Type", "Exact"),
                    "value": float(reading),
                })

    for pid, _ in fallback_temp_pumps:
        temp_candidates.setdefault(pid, []).append({
            "measurement_type": "Exact",
            "value": safe_float_fn(fallback_temp_values.get(pid), 0.0),
        })

    for hw_name, edited_df in clamp_tables.items():
        clamp_tables_payload[hw_name] = edited_df.to_dict("records")
        for _, row in edited_df.iterrows():
            pump_id = str(row.get("Pump ID", "")).strip()
            status = str(row.get("Status", "STANDBY")).upper()
            reading = row.get("Reading (A)")
            if not pump_id:
                continue
            if reading != reading:
                if status == "RUNNING":
                    errors.append(f"{hw_name} {pump_id}: current is required.")
                    continue
                current_candidates.setdefault(pump_id, []).append(0.0)
            else:
                current_candidates.setdefault(pump_id, []).append(float(reading))

    for pid in fallback_clamp_pumps:
        current_candidates.setdefault(pid, []).append(safe_float_fn(fallback_clamp_values.get(pid), 0.0))

    if errors:
        return errors, temp_tables_payload, clamp_tables_payload, pump_readings

    for pid in pump_ids:
        status = str(status_grid.get(pid, {}).get("status", "STANDBY")).upper()
        if status == "FAILED":
            pump_readings[pid] = {"temp": None, "amps": None, "status": status}
            continue

        derived_temp = aggregate_temperature_for_pump_fn(temp_candidates.get(pid, []))
        if derived_temp is None:
            derived_temp = safe_float_fn(previous_readings.get(pid, {}).get("temp"), 0.0)

        current_values = current_candidates.get(pid, [])
        derived_amps = max(current_values) if current_values else safe_float_fn(previous_readings.get(pid, {}).get("amps"), 0.0)

        pump_readings[pid] = {
            "temp": float(derived_temp),
            "amps": float(derived_amps),
            "status": status,
        }

    return errors, temp_tables_payload, clamp_tables_payload, pump_readings
