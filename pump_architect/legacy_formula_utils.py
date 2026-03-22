import ast
import datetime
import operator

import pandas as pd

MATH_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}

MATH_UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def parse_ts(ts_text):
    return datetime.datetime.strptime(str(ts_text).strip(), "%Y-%m-%d %H:%M:%S")


def safe_float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def aggregate_temperature_for_pump(temp_rows):
    if not temp_rows:
        return None

    exact_values = [safe_float(row.get("value"), None) for row in temp_rows if str(row.get("measurement_type", "Exact")).strip().lower() == "exact"]
    exact_values = [value for value in exact_values if value is not None]
    if exact_values:
        return max(exact_values)

    max_values = [safe_float(row.get("value"), None) for row in temp_rows if str(row.get("measurement_type", "")).strip().lower() == "max temp"]
    max_values = [value for value in max_values if value is not None]
    if max_values:
        return max(max_values)

    avg_values = [safe_float(row.get("value"), None) for row in temp_rows if str(row.get("measurement_type", "")).strip().lower() == "average"]
    avg_values = [value for value in avg_values if value is not None]
    if avg_values:
        return sum(avg_values) / len(avg_values)

    fallback_values = [safe_float(row.get("value"), None) for row in temp_rows]
    fallback_values = [value for value in fallback_values if value is not None]
    return fallback_values[0] if fallback_values else None


def evaluate_math_expression(expression, variables):
    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.Num):
            return float(node.n)
        if isinstance(node, ast.Name):
            if node.id not in variables:
                raise KeyError(node.id)
            return float(variables[node.id])
        if isinstance(node, ast.BinOp) and type(node.op) in MATH_BINARY_OPERATORS:
            return MATH_BINARY_OPERATORS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in MATH_UNARY_OPERATORS:
            return MATH_UNARY_OPERATORS[type(node.op)](_eval(node.operand))
        raise ValueError("Unsupported formula expression")

    parsed = ast.parse(str(expression).strip(), mode="eval")
    return float(_eval(parsed))


def get_formula_target_specificity(target, pump_id, tank_name):
    target = str(target).strip()
    if target in ["Global (Apply to All Compatible Pumps)", "Global (All Pumps)"]:
        return 1
    if target == f"Water Tank: {tank_name}":
        return 2
    if target == pump_id:
        return 3
    return -1


def get_sensor_assignment(mapped_sensor):
    mapped_sensor = str(mapped_sensor).strip()
    start = mapped_sensor.find("(")
    end = mapped_sensor.find(")", start + 1)
    if start == -1 or end == -1:
        return ""
    return mapped_sensor[start + 1:end].strip()


def get_sensor_hardware(mapped_sensor):
    mapped_sensor = str(mapped_sensor).strip()
    start = mapped_sensor.find("[")
    end = mapped_sensor.find("]", start + 1)
    if start == -1 or end == -1:
        return ""
    return mapped_sensor[start + 1:end].strip()


def build_formula_variables_for_pump(pid, reading, ambient_temp, tank_temps, pump_tank_lookup, var_mapping_df):
    variables = {}
    assigned_tank = str(pump_tank_lookup.get(pid, "")).strip()
    stat_temp = safe_float(reading.get("temp"), None)
    current_val = safe_float(reading.get("amps"), None)

    if stat_temp is not None:
        variables["T_stat"] = stat_temp
    variables["T_amb"] = float(ambient_temp)
    if assigned_tank and assigned_tank in tank_temps:
        tank_value = safe_float(tank_temps.get(assigned_tank), None)
        if tank_value is not None:
            variables[assigned_tank.replace(" ", "_")] = tank_value

    if not isinstance(var_mapping_df, pd.DataFrame) or var_mapping_df.empty:
        return variables

    for _, row in var_mapping_df.iterrows():
        variable = str(row.get("Variable", "")).strip()
        mapped_sensor = str(row.get("Mapped Sensor", "")).strip()
        if not variable:
            continue

        assignment = get_sensor_assignment(mapped_sensor)
        hardware = get_sensor_hardware(mapped_sensor)
        value = None

        if assignment == "Global (Ambient Room)":
            value = float(ambient_temp)
        elif assignment.startswith("Water Tank "):
            value = safe_float(tank_temps.get(assignment), None)
        elif assignment == pid:
            if "HIOKI Clamp" in hardware:
                value = current_val
            else:
                value = stat_temp

        if value is None:
            lowered = variable.lower()
            if lowered == "t_stat":
                value = stat_temp
            elif lowered == "t_amb":
                value = float(ambient_temp)
            elif lowered.startswith("t_water") and assigned_tank:
                value = safe_float(tank_temps.get(assigned_tank), None)
            elif lowered.startswith("i_") or lowered in ["i_stat", "current", "amps"]:
                value = current_val

        if value is not None:
            variables[variable] = float(value)

    return variables


def evaluate_formula_for_pump(pid, tank_name, formula_name, formulas_df, var_mapping_df, reading, ambient_temp, tank_temps, pump_tank_lookup, preferred_target=None):
    if not isinstance(formulas_df, pd.DataFrame) or formulas_df.empty:
        return None, None

    candidates = []
    for index, row in formulas_df.iterrows():
        current_name = str(row.get("Formula Name", "")).strip()
        target = str(row.get("Target", "")).strip()
        equation = str(row.get("Equation", "")).strip()
        if not current_name or not equation:
            continue
        if current_name != formula_name:
            continue
        specificity = get_formula_target_specificity(target, pid, tank_name)
        if specificity < 0:
            continue
        preferred_bonus = 1 if preferred_target and target == preferred_target else 0
        candidates.append((specificity, preferred_bonus, -index, target, equation))

    if not candidates:
        return None, None

    candidates.sort(reverse=True)
    _, _, _, matched_target, equation = candidates[0]
    variables = build_formula_variables_for_pump(pid, reading, ambient_temp, tank_temps, pump_tank_lookup, var_mapping_df)
    try:
        return evaluate_math_expression(equation, variables), matched_target
    except Exception:
        return None, matched_target
