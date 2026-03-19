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
	- Set up system watchdogs in a table format, where each row corresponds to a selected Allowed Data Entry Method (Column: Data Entry Method). For each method, the user selects the type of watchdog that wants to be displayed (ON/OFF, Connection Status(ONLINE/OFFLINE), ESP32 Internal Temperature) from a dropdown menu (Column: Watchdog Type). One allowed Data Entry Method can have multiple Watchdog types. 
	Once the watchdog is selected, there is a transition to main dashboard in OPEN file function. For example: If Watchdog Manual Input and ON/OFF was input. Then, in the dashboard should show ON

	- Safety limits are displayed in a table, automatically listing all pumps configured in Step 2. For each pump, default values are provided for Max Stator Temperature (based on insulation class) and Max Current (from Step 2). The user can add (add button) or edit additional safety limits as needed. The additional safety limits comes from step custom formula builder, formula name. the user will input the formula min (left in blank if no used), and max values and applicable to Target Pumps function like in step 4.

	- The Event Alert Log displays a scrollable, timestamped list of project events (e.g., project start, new record, alerts), ordered from newest to oldest.
	
	
	- The dashboard preview shows a 3x3 grid layout for each water tank (from Step 3), with each tank's assigned pumps displayed in their respective grids. "Main Dashboard Tracker" selectbox added. When Temperature is selected (default): Large primary metric → TEMPERATURE (MAX: X°C) with the big value-grey display。Secondary row → CURRENT (MAX: X.XXA) in smaller text Sparkline footer label → TEMPERATURE / 10 MINUTES. When Current is selected: Large primary metric → LIVE CURRENT (MAX: X.XXA). Secondary row → TEMPERATURE (MAX: X°C). Sparkline footer label → CURRENT / 10 MINUTES. Once the layout is set up. Click confirm Dashboard Visual Layout Preview button.

	- When the user goest to step 6. The windows goes automatically to the top of the page. 

**Table Initialization Logic:**
- When using Create New Project, all tables (including watchdogs, safety limits, and event log) are initialized with default/empty data.
- When using Modify, all tables are restored with the latest saved data for the selected project, including any custom safety limits, event log history, and dashboard assignments.

**Note:**
You do NOT need to delete architect_system.db unless you are missing columns (e.g., after a schema change). The app will automatically create or migrate columns as needed. Only delete the database if you encounter migration errors or want to reset all data.


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
