# Pump Test Architect

Streamlit application for creating pump-test projects, assigning pumps to tanks,
capturing operating records, and tracking maintenance events.

## Current refactor stage

- Runtime behavior is preserved through the legacy-compatible entrypoint.
- Large `pump_app.py` logic has been extracted into `pump_architect/legacy_*`
  modules in safe, incremental slices.
- Route and home-page handling are now consolidated in
  `pump_architect/legacy_pages.py`.

## Project structure

```
pump_architect_system/
├── pump_app.py                    # Active Streamlit entrypoint
├── requirements.txt               # Python dependencies
├── pump_architect/
│   ├── app.py                     # Alternate modular app path
│   ├── legacy_pages.py            # Consolidated page routing/home helpers
│   ├── legacy_dashboard_page.py   # Dashboard route renderer
│   ├── legacy_add_record_wizard.py
│   ├── legacy_project_form.py
│   └── legacy_*.py                # Extracted behavior-preserving helpers
└── README.md
```

## Installation

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
streamlit run pump_app.py
```

Open the URL shown in terminal (typically `http://localhost:8501`).

## Database

- SQLite file: `architect_system.db`
- Created automatically on first run
- Local runtime artifact (not intended for source control)
