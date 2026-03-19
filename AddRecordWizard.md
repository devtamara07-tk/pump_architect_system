## PHASE 1: Initialization & Pre-Flight Checks

* **Trigger:** Operator clicks "Add Record" on the Dashboard.
* **Branching Decision:** System prompts: "Select Record Phase"
    * **Options:** [Baseline Calibration (Cold State)] OR [Routine/Daily Record].
* **Validation Gates:**
    * **If [Routine]:** System checks the database for a Baseline. If none exists, block progress: "ERROR: No baseline found. Complete Baseline Calibration first."
    * **If [Baseline]:** System checks if one already exists. If yes, warn: "WARNING: Overwriting existing baseline."

---

## PHASE 2: Time Math & State Management (The Core Engine)

* **Determine Global Time Delta:**
    * **If Baseline:** Delta = 0.0 Hrs.
    * **If Routine:** System calculates exact time elapsed between Right Now and the Last Saved Record Timestamp (e.g., 24.0 Hrs).
* **Load the Status Grid:** System displays the project pumps with their last known Status and Accumulated Time.
    * **If Baseline:** System forces all pumps to STANDBY and locks them.
    * **If Routine:** System allows the operator to modify the statuses for today.
* **The State Evaluation & Time Distribution:**
    * **Rule A (Continuous RUN):** Pump was RUNNING yesterday and is RUNNING today. ➔ Add full Global Delta (e.g., +24.0 Hrs).
    * **Rule B (Staying Offline):** Pump was STANDBY, PAUSED, or FAILED yesterday and stays that way today. ➔ Add 0.0 Hrs.
    * **Rule C (Delayed Start):** Pump was STANDBY yesterday, but flipped to RUNNING today. ➔ Add 0.0 Hrs today. (It will begin accruing time on tomorrow's record).
    * **Rule D (The Mid-Cycle Intercept):** Pump was RUNNING yesterday, but flipped to PAUSED or FAILED today.
        * **Action:** System intercepts and prompts: "Pump [ID] went offline. Enter exact Date & Time of failure."
        * **Math:** System calculates the micro-delta (Failure Time - Last Record Time) and adds only those specific hours to the pump.

---

## PHASE 3: Global Environmental Capture

* **Timestamp:** System auto-generates current Date/Time (Operator can override if backlogging).
* **Method Selection:** Operator selects [Manual Input] or [Voice Recording].
* **Global Sensors:**
    * **Input:** Ambient Room Temperature
    * **Input:** Water Tank(s) Temperature 

---

## PHASE 4: Targeted Hardware Polling (The Cascade)

The system now iterates through Pumps P-01 to P-N. Input boxes dynamically adapt based on the finalized Status Grid from Phase 2.

* **If Pump is RUNNING:**
    * **Temp:** Ask for Live Stator Temp.
    * **Amps:** Ask for Live Measured Current.
    * **Visual Aid:** Display (Max: XX°C / XX A) next to inputs.
* **If Pump is STANDBY or PAUSED:**
    * **Temp:** Ask for "Cold/Cool-down" Stator Temp.
    * **Amps:** System forces and locks Current to 0.00A.
* **If Pump is FAILED:**
    * System hides all inputs. No data required.

---

## PHASE 5: Safety Engine & Limits Validation

* **Calculate Baseline Metrics:** For all pumps with a Temp input, calculate: Temp Rise = Measured Temp - Ambient Temp.
* **Evaluate Hard Limits (Only for RUNNING pumps):**
    * **Check 1:** Is Measured Temp > Max Stator Temp?
    * **Check 2:** Is Measured Current > Max Current (A)?
    * **Check 3:** Is Temp Rise > Max Temp Rise?
* **Flag Generation:** If any check fails, immediately tag the specific pump with a critical "ALARM" flag in the system memory.

---

## PHASE 6: Review, Commit & The Maintenance Bridge

* **Generate Review Matrix:** Render a final table for operator sign-off:
    [Pump ID] | [Status] | [Acc. Time] | [Temp] | [Amps] | [Rise] | [Alarms]
* **Forced Acknowledgment:** If any ALARM tags exist, display a red warning box. The operator must check a box stating: "I acknowledge safety limits have been exceeded" before the Save button unlocks.
* **Commit Payload:** Save all calculated times, states, and sensor data to the SQLite database.
* **The Maintenance Bridge:**
    * System checks if any pump was flipped to PAUSED or FAILED during this session.
    * **If Yes:** Prompt: "Pump [ID] was taken offline. Would you like to log a Maintenance Event now?"
        * **If Yes ➔** Route to "Add New Maintenance" wizard.
        * **If No ➔** Route to Dashboard.
* **Dashboard Update:** Return to Dashboard. Update progress bars, sparklines, and turn Status Lights to Green (Running), Amber (Paused/Alarms), Grey (Standby), or Red (Failed).