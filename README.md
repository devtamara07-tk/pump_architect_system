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
├── tools/
│   └── check_db.py                # DB connectivity sanity check
├── pump_architect/
│   ├── db/
│   │   ├── connection.py          # DB-agnostic connection factory (Postgres / SQLite)
│   │   ├── schema.py              # Table creation helpers
│   │   └── repositories.py        # High-level CRUD helpers
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

### Local development (SQLite – default)

When `DATABASE_URL` is **not** set the app uses a local SQLite file:

- File: `architect_system.db`
- Created automatically on first run
- Local runtime artifact (not intended for source control; already in `.gitignore`)

### Production (Neon Postgres)

When `DATABASE_URL` **is** set, all database operations are routed to Postgres
automatically. SQLite is not used.

The Postgres schema expected by the app:

| Table | Key columns |
|-------|-------------|
| `public.projects` | `project_id TEXT PRIMARY KEY`, plus layout / hardware / formula JSON columns |
| `public.pumps` | `pump_id TEXT`, `project_id TEXT`, `"Pump Model"`, `"ISO No."`, etc. |
| `public.project_records` | `id BIGSERIAL PRIMARY KEY`, `project_id TEXT`, record JSON columns |
| `public.maintenance_events` | `id BIGSERIAL PRIMARY KEY`, `project_id TEXT`, event columns |

#### Streamlit Community Cloud

1. Deploy the app from this repository.
2. Open **App settings → Secrets** and add:

```toml
DATABASE_URL = "postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require"
```

Replace `USER`, `PASSWORD`, `HOST`, and `DBNAME` with your Neon credentials.
**Do not commit credentials** – the secret lives only in Streamlit's settings.

#### Local dev with Postgres (optional)

Export the variable in your shell before starting Streamlit:

```bash
export DATABASE_URL="postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require"
streamlit run pump_app.py
```

Or add it to `.streamlit/secrets.toml` (already git-ignored):

```toml
DATABASE_URL = "postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require"
```

#### Verify the connection

```bash
python tools/check_db.py
```

This connects to whichever database is configured and prints row counts for
the three main tables.

