# Pump Test Architect

Streamlit application for creating pump-test projects, assigning pumps to tanks,
capturing operating records, and tracking maintenance events.

## Current refactor stage

- Runtime behavior is preserved through the legacy-compatible entrypoint
  (`pump_app.py`).
- Core `pump_app.py` blocks have been extracted into
  `pump_architect/legacy_*` modules in incremental, behavior-preserving slices.
- Page routing/home/dashboard flow is consolidated via
  `pump_architect/legacy_pages.py`.
- Database/project open/modify orchestration is extracted in
  `pump_architect/legacy_project_state.py`.

## Project structure

```
pump_architect_system/
├── pump_app.py                    # Active Streamlit entrypoint
├── requirements.txt               # Python dependencies
├── tests/                          # Test suite
├── pump_architect/
│   ├── app.py                     # Alternate modular app path
│   ├── legacy_pages.py            # Consolidated page routing/home helpers
│   ├── legacy_dashboard_page.py   # Dashboard route renderer
│   ├── legacy_project_state.py    # DB init + project state orchestration
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

## Optional test run

```bash
pytest -q
```

## Database

This application now requires a Postgres database. You must set the `DATABASE_URL` environment variable to your Postgres connection string before running the app.

Example:

```bash
export DATABASE_URL="postgresql://username:password@host:port/dbname"
streamlit run pump_app.py
```

The app will not run without a valid Postgres connection.
