import streamlit as st


def render_phase1(draft, baseline_exists, queue_confirmation_fn):
    st.markdown("<p class='col-header'>Phase 1: Initialization & Pre-Flight Checks</p>", unsafe_allow_html=True)
    selected_phase = st.radio(
        "Select Record Phase",
        ["Baseline Calibration (Cold State)", "Routine/Daily Record"],
        index=0 if draft.get("record_phase") == "Baseline Calibration (Cold State)" else 1,
        horizontal=True,
        key="add_record_phase_radio",
    )
    draft["record_phase"] = selected_phase

    can_continue_phase1 = True
    if selected_phase == "Routine/Daily Record" and not baseline_exists:
        can_continue_phase1 = False
        st.error("ERROR: No baseline found. Complete Baseline Calibration first.")
    if selected_phase == "Baseline Calibration (Cold State)" and baseline_exists:
        st.warning("WARNING: Overwriting existing baseline.")

    if st.button("Confirm Record Phase", use_container_width=True, key="confirm_record_phase"):
        if can_continue_phase1:
            draft["phase1_confirmed"] = True
            draft["phase2_confirmed"] = False
            draft["phase3_confirmed"] = False
            draft["phase4_confirmed"] = False
            queue_confirmation_fn("Record phase confirmed.")
            st.rerun()

    return bool(draft.get("phase1_confirmed", False))


def render_phase3(draft, water_tanks, queue_confirmation_fn):
    st.markdown("<p class='col-header'>Phase 3: Global Environmental Capture</p>", unsafe_allow_html=True)
    method = st.radio("Record Method", ["Manual Input", "Voice Recording"], horizontal=True, key="add_record_method")
    ambient_temp = st.number_input(
        "Ambient Room Temperature (C)",
        value=float(draft.get("ambient_temp", 25.0)),
        step=0.1,
        format="%.1f",
        key="ambient_temp_input",
    )

    tank_temps = {}
    for tank in water_tanks:
        tank_key = f"tank_temp_{tank}"
        tank_temps[tank] = st.number_input(
            f"{tank} Temperature (C)",
            value=float(draft.get("tank_temps", {}).get(tank, 25.0)),
            step=0.1,
            format="%.1f",
            key=tank_key,
        )

    if st.button("Confirm Global Capture", use_container_width=True, key="confirm_phase3"):
        draft["method"] = method
        draft["ambient_temp"] = float(ambient_temp)
        draft["tank_temps"] = tank_temps
        draft["phase3_confirmed"] = True
        queue_confirmation_fn("Phase 3 confirmed. Global inputs captured.")
        st.rerun()

    return bool(draft.get("phase3_confirmed", False))
