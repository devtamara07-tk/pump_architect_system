import pandas as pd


def build_phase56_review_data(
    pump_ids,
    draft,
    ambient,
    tank_temps,
    pump_tank_lookup,
    formulas_df,
    var_mapping_df,
    limits_lookup,
    extra_limits_df,
    build_formula_variables_for_pump_fn,
    get_formula_target_specificity_fn,
    evaluate_formula_for_pump_fn,
    safe_float_fn,
):
    review_rows = []
    all_alarms = []
    formula_debug_rows = []

    for pid in pump_ids:
        grid = draft["status_grid"].get(pid, {})
        reading = draft["pump_readings"].get(pid, {})
        status = str(grid.get("status", "STANDBY")).upper()
        acc = float(grid.get("acc_hours", 0.0) or 0.0)
        temp = reading.get("temp", None)
        amps = reading.get("amps", None)
        tank_name = str(pump_tank_lookup.get(pid, "")).strip()

        resolved_variables = build_formula_variables_for_pump_fn(
            pid,
            reading,
            ambient,
            tank_temps,
            pump_tank_lookup,
            var_mapping_df,
        )

        rise = None
        rise_formula_name = ""
        rise_formula_target = ""
        applicable_temp_rise = []
        if isinstance(formulas_df, pd.DataFrame) and not formulas_df.empty and "Formula Name" in formulas_df.columns:
            for _, formula_row in formulas_df.iterrows():
                formula_name = str(formula_row.get("Formula Name", "")).strip()
                if formula_name.lower() not in ["temperature rise", "temp rise"]:
                    continue
                specificity = get_formula_target_specificity_fn(formula_row.get("Target", ""), pid, tank_name)
                if specificity >= 0:
                    applicable_temp_rise.append((specificity, formula_name))

        if applicable_temp_rise:
            applicable_temp_rise.sort(reverse=True)
            rise_formula_name = applicable_temp_rise[0][1]
            rise, rise_formula_target = evaluate_formula_for_pump_fn(
                pid,
                tank_name,
                rise_formula_name,
                formulas_df,
                var_mapping_df,
                reading,
                ambient,
                tank_temps,
                pump_tank_lookup,
            )

        if rise is None and temp is not None:
            rise = float(temp) - ambient

        lim = limits_lookup.get(pid)
        max_temp = float(lim.get("Max Stator Temp (°C)", 0.0) if lim is not None else 0.0)
        max_current = float(lim.get("Max Current (A)", 0.0) if lim is not None else 0.0)

        pump_alarm_list = []
        formula_limit_debug = []
        if status == "RUNNING":
            if temp is not None and float(temp) > max_temp:
                pump_alarm_list.append(f"Temp {float(temp):.1f}C > {max_temp:.1f}C")
            if amps is not None and float(amps) > max_current:
                pump_alarm_list.append(f"Current {float(amps):.2f}A > {max_current:.2f}A")
            if isinstance(extra_limits_df, pd.DataFrame) and not extra_limits_df.empty and "Formula Name" in extra_limits_df.columns:
                for _, ex in extra_limits_df.iterrows():
                    formula_name = str(ex.get("Formula Name", "")).strip()
                    applies = str(ex.get("Applies To", "")).strip()
                    if get_formula_target_specificity_fn(applies, pid, tank_name) < 0:
                        continue
                    formula_value, _ = evaluate_formula_for_pump_fn(
                        pid,
                        tank_name,
                        formula_name,
                        formulas_df,
                        var_mapping_df,
                        reading,
                        ambient,
                        tank_temps,
                        pump_tank_lookup,
                        preferred_target=applies,
                    )
                    if formula_value is None:
                        continue
                    min_value = safe_float_fn(ex.get("Min Value"), None)
                    max_value = safe_float_fn(ex.get("Max Value"), None)
                    formula_limit_debug.append(
                        f"{formula_name}={float(formula_value):.2f} [Target={applies}]"
                    )
                    if min_value is not None and float(formula_value) < float(min_value):
                        pump_alarm_list.append(f"{formula_name} {float(formula_value):.2f} < {float(min_value):.2f}")
                    if max_value is not None and float(formula_value) > float(max_value):
                        pump_alarm_list.append(f"{formula_name} {float(formula_value):.2f} > {float(max_value):.2f}")

        if pump_alarm_list:
            all_alarms.append({"pump_id": pid, "alarms": pump_alarm_list})

        review_rows.append({
            "Pump ID": pid,
            "Status": status,
            "Acc. Time (hrs)": round(acc, 2),
            "Temp (C)": "-" if temp is None else round(float(temp), 1),
            "Amps (A)": "-" if amps is None else round(float(amps), 2),
            "Rise (C)": "-" if rise is None else round(float(rise), 1),
            "Alarms": " | ".join(pump_alarm_list) if pump_alarm_list else "OK",
        })

        debug_variables_text = ", ".join([f"{key}={value:.2f}" for key, value in sorted(resolved_variables.items())]) if resolved_variables else "-"
        debug_rise_formula = "-"
        if rise_formula_name:
            target_text = rise_formula_target if rise_formula_target else "matched"
            debug_rise_formula = f"{rise_formula_name} [{target_text}]"
        formula_debug_rows.append({
            "Pump ID": pid,
            "Tank": tank_name or "-",
            "Resolved Variables": debug_variables_text,
            "Rise Formula": debug_rise_formula,
            "Rise Value": "-" if rise is None else f"{float(rise):.2f}",
            "Formula Limit Values": " | ".join(formula_limit_debug) if formula_limit_debug else "-",
        })

    return review_rows, all_alarms, formula_debug_rows