# Pump Architect System

Pump Architect System is a Streamlit-based application for managing, configuring, and monitoring industrial pump test projects. It features a multi-step wizard for project creation, hardware mapping, formula setup, and dashboard visualization, all with a modern industrial UI.

## Features
- **Project Wizard:** Step-by-step creation and configuration of pump test projects.
- **Database Integration:** Uses SQLite for persistent storage of projects and pump specifications.
- **Customizable Hardware Mapping:** Assign sensors and hardware units to pumps and tanks.
- **Formula Builder:** Map variables and create custom formulas for calculations.
- **Dashboard:** Visual overview of project status, pump data, and system watchdogs.
- **Industrial Dark UI:** Custom CSS for a professional, readable interface.

## Setup
1. **Install requirements:**
	 ```bash
	 pip install -r requirements.txt
	 ```
2. **Run the app:**
	 ```bash
	 streamlit run pump_app.py
	 ```

## Database Tables

### projects
| Column       | Type    | Description                       |
|--------------|---------|-----------------------------------|
| project_id   | TEXT    | Primary key, project name         |
| type         | TEXT    | Pump type                         |
| test_type    | TEXT    | Test type                         |
| run_mode     | TEXT    | Run mode                          |
| target_val   | TEXT    | Target value (Hrs or Cycles)      |
| created_at   | DATETIME| Creation timestamp                |

### pumps
| Column        | Type    | Description                       |
|---------------|---------|-----------------------------------|
| pump_id       | TEXT    | Pump ID (e.g., P-01)              |
| project_id    | TEXT    | Linked project                    |
| model         | TEXT    | Pump model                        |
| iso_no        | TEXT    | ISO number                        |
| hp            | REAL    | Horsepower                        |
| kw            | REAL    | Kilowatts                         |
| voltage       | TEXT    | Voltage (V)                       |
| amp_min       | REAL    | Minimum current (A)               |
| amp_max       | REAL    | Maximum current (A)               |
| phase         | INTEGER | Phase (1 or 3)                    |
| hertz         | TEXT    | Frequency (Hz)                    |
| insulation    | TEXT    | Insulation type                   |
| tank_name     | TEXT    | Assigned tank                     |

## Application Flow & Functions

### 1. Initialization & Database
- Sets up SQLite database and tables (`projects`, `pumps`).
- Applies custom industrial CSS for UI.

### 2. Project Wizard Steps
#### Step 1: Test Definition
	- Select pump type: Centrifugal or Submersible, input test type, select run mode: Continuous or Intermittent, and input the test target value for Continuos: HR or Days, for Intermittent: Cycles. Then, the code automatically assign the Project Name: Pump type + Test type + Run Mode and displays the name at the bottom of the page. 
#### Step 2: Pump Specification
	- Add pump details in a table with columns: Pump Model, ISO No., HP, kW(decimal number allowed), Voltage (V), Amp Min (decimal number allowed), Amp Max(decimal number allowed), Phase, Hertz, Motor Insulation. Then, click confirm table to assign and lock the Pump IDs.
#### Step 3: Installation Layout
	- Assign pumps to water tanks. Manage tank list and map each pump to a tank.
#### Step 4: Hardware & Sensor Mapping
	- Add hardware units (HIOKI Temp, HIOKI Power, HIOKI Clamp, General HW). Configure channels, assign sensors, and set data entry methods. All hardware and sensor mapping tables are saved per project. When you use Modify, the latest saved configuration for all hardware and sensor mapping is restored exactly as it was last saved. When you create a new project, all hardware and sensor mapping tables start empty/default.
#### Step 5: Variable Mapping & Formulas
	- Map variables to sensors and define custom formulas for calculations.At Custom Formula Builder, the taget pump(s) can be assigned by: Globally (all pumps), per Water Tank(s) (only pumps that were assigned in the specific water tank in step 3), or per pump (each individual pump assigned in step 2)
#### Step 6: Dashboard & Report Setup
	- Set up system watchdogs according to the selected Allowed Data Entry Methods and their system status (e.g. ONLINE/OFFLINE, ON/OFF), or specific watchdog set up: Connection Lost, ESP32 Internal Temperature. Safety limits. Envent Alert Log to display date and time of new project start, new record, alerts, etc. in a list format arranged from the newest to the oldest information. The oldest information can be reached by dragging down the cursor. And preview dashboard layout that is in 3x3 format according to the Water Tank assignment in step 3. The dashboard shows Water Tank number and its assigned pumps in 3x3 format. The dashboard for each pump displays according to the selected formula and calculations and the current runnig time in HR or cycle amount.


### 3. Main Routing & Dashboard
- **Home:** Lists all projects with options to create, open, modify, or delete.
- **Create New Project:** Starts a new project with all fields and tables (including hardware and sensor mapping) in their default/empty state. No previous data is pre-filled.
- **Open:** Dashboard displays live status, pump data, and event logs for the selected project.
- **Modify:** Returns to the Project Wizard with all information (including all tables and hardware/sensor mapping) restored exactly as last saved. Any changes made and saved will overwrite previous data. Deleted rows or hardware are removed, new entries are added, and all tables reflect the latest saved state. When you use Modify, the wizard always retrieves and displays the most recently saved data for every step, including Step 4 Hardware & Sensor Mapping.

## Screenshots

> **Add your screenshots here:**

| Wizard Step Example | Dashboard Example |
|--------------------|------------------|
| ![Step 1](screenshots/step1.png) | ![Dashboard](screenshots/dashboard.png) |

## Notes
- All table column names in the UI and database are consistent and match exactly as defined in the code.
- For best results, use the app in a wide browser window.

---
For any issues or feature requests, please open an issue on the repository.
