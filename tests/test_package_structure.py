"""
Smoke tests that confirm the successful merge of the refactored Streamlit app
into the pump_architect package structure.

Run with:
    python -m pytest tests/test_package_structure.py -v
"""

import importlib
import os
import tempfile

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Package file-system structure
# ---------------------------------------------------------------------------

EXPECTED_FILES = [
    "pump_architect/__init__.py",
    "pump_architect/app.py",
    "pump_architect/constants.py",
    "pump_architect/db/__init__.py",
    "pump_architect/db/connection.py",
    "pump_architect/db/schema.py",
    "pump_architect/db/repositories.py",
    "pump_architect/ui/__init__.py",
    "pump_architect/ui/styles.py",
    "pump_architect/ui/assets.py",
    "pump_architect/ui/pages/__init__.py",
    "pump_architect/ui/pages/home.py",
    "pump_architect/ui/pages/project_form.py",
    "pump_architect/ui/pages/dashboard.py",
    "pump_app.py",
    "requirements.txt",
    "README.md",
]

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.mark.parametrize("relative_path", EXPECTED_FILES)
def test_file_exists(relative_path):
    """Every file that is part of the refactored package must be present."""
    full_path = os.path.join(PROJECT_ROOT, relative_path)
    assert os.path.isfile(full_path), f"Missing expected file: {relative_path}"


# ---------------------------------------------------------------------------
# Import checks (non-Streamlit modules)
# ---------------------------------------------------------------------------

NON_STREAMLIT_MODULES = [
    "pump_architect.constants",
    "pump_architect.db.connection",
    "pump_architect.db.schema",
    "pump_architect.db.repositories",
]


@pytest.mark.parametrize("module_name", NON_STREAMLIT_MODULES)
def test_module_importable(module_name):
    """All non-Streamlit package modules must import without errors."""
    mod = importlib.import_module(module_name)
    assert mod is not None


def test_constants_form_state_keys():
    """FORM_STATE_KEYS must be a non-empty list of strings."""
    from pump_architect.constants import FORM_STATE_KEYS

    assert isinstance(FORM_STATE_KEYS, list)
    assert len(FORM_STATE_KEYS) > 0
    assert all(isinstance(k, str) for k in FORM_STATE_KEYS)


def test_db_connection_exports():
    """db.connection must expose get_connection and DB_FILE."""
    from pump_architect.db.connection import DB_FILE, get_connection

    assert callable(get_connection)
    assert isinstance(DB_FILE, str)
    assert DB_FILE.endswith(".db")


def test_db_repositories_exports():
    """db.repositories must expose the three CRUD helpers."""
    from pump_architect.db import repositories

    assert callable(repositories.get_projects)
    assert callable(repositories.save_project)
    assert callable(repositories.delete_project)


# ---------------------------------------------------------------------------
# Database round-trip
# ---------------------------------------------------------------------------


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    """Redirect DB_FILE to a temporary file for each test."""
    import pump_architect.db.connection as conn_mod

    db_path = str(tmp_path / "test_pump.db")
    monkeypatch.setattr(conn_mod, "DB_FILE", db_path)
    return db_path


def test_init_db(isolated_db):
    """init_db must create the database file and all expected tables."""
    from pump_architect.db.schema import init_db
    import sqlite3

    init_db()
    assert os.path.isfile(isolated_db)

    conn = sqlite3.connect(isolated_db)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    # conn.close()  # Removed: do not close cached connection

    expected_tables = {
        "projects",
        "pumps",
        "status_logs",
        "test_targets",
        "sensors",
        "hardware_setup",
    }
    assert expected_tables.issubset(tables), (
        f"Missing tables: {expected_tables - tables}"
    )


def test_save_and_get_project(isolated_db):
    """save_project must persist a record retrievable by get_projects."""
    from pump_architect.db.schema import init_db
    from pump_architect.db.repositories import get_projects, save_project

    init_db()

    pumps = pd.DataFrame(
        [
            {
                "Pump ID": "P-01",
                "Pump Model": "TestModel",
                "ISO No.": "ISO-999",
                "HP": 5.0,
                "kW": 3.7,
                "Voltage (V)": "220V",
                "Amp (A)": "15A",
                "Phase": 3,
                "Hertz": "60Hz",
                "Insulation": "Class F",
            }
        ]
    )
    tanks = {"Tank A": ["P-01"]}
    save_project("Centrifugal_Endurance Test", "Centrifugal", "Endurance Test", pumps, tanks)

    df = get_projects()
    assert len(df) == 1
    assert df.iloc[0]["project_id"] == "Centrifugal_Endurance Test"
    assert df.iloc[0]["type"] == "Centrifugal"
    assert df.iloc[0]["test_type"] == "Endurance Test"


def test_delete_project(isolated_db):
    """delete_project must remove the project and its associated pumps."""
    from pump_architect.db.schema import init_db
    from pump_architect.db.repositories import delete_project, get_projects, save_project
    import sqlite3

    init_db()

    pumps = pd.DataFrame(
        [
            {
                "Pump ID": "P-01",
                "Pump Model": "M1",
                "ISO No.": "ISO-1",
                "HP": 1.0,
                "kW": 0.75,
                "Voltage (V)": "110V",
                "Amp (A)": "5A",
                "Phase": 1,
                "Hertz": "50Hz",
                "Insulation": "Class B",
            }
        ]
    )
    save_project("Centrifugal_Run Test", "Centrifugal", "Run Test", pumps, {})

    delete_project("Centrifugal_Run Test")

    df = get_projects()
    assert len(df) == 0

    conn = sqlite3.connect(isolated_db)
    pump_rows = conn.execute(
        "SELECT * FROM pumps WHERE project_id=?", ("Centrifugal_Run Test",)
    ).fetchall()
    # conn.close()  # Removed: do not close cached connection
    assert len(pump_rows) == 0


def test_save_project_edit(isolated_db):
    """Saving with edit_id must replace the original project."""
    from pump_architect.db.schema import init_db
    from pump_architect.db.repositories import get_projects, save_project

    init_db()

    pumps = pd.DataFrame(
        [
            {
                "Pump ID": "P-01",
                "Pump Model": "OldModel",
                "ISO No.": "ISO-0",
                "HP": 2.0,
                "kW": 1.5,
                "Voltage (V)": "220V",
                "Amp (A)": "10A",
                "Phase": 3,
                "Hertz": "60Hz",
                "Insulation": "Class F",
            }
        ]
    )
    save_project("Centrifugal_Load Test", "Centrifugal", "Load Test", pumps, {})

    pumps_updated = pumps.copy()
    pumps_updated["Pump Model"] = "NewModel"
    save_project(
        "Centrifugal_Load Test",
        "Centrifugal",
        "Load Test",
        pumps_updated,
        {},
        edit_id="Centrifugal_Load Test",
    )

    df = get_projects()
    assert len(df) == 1


# ---------------------------------------------------------------------------
# Legacy shim
# ---------------------------------------------------------------------------


def test_legacy_shim_exists():
    """pump_app.py (backward-compatibility shim) must still be present."""
    shim = os.path.join(PROJECT_ROOT, "pump_app.py")
    assert os.path.isfile(shim), "Legacy shim pump_app.py is missing"


def test_legacy_shim_imports_package():
    """pump_app.py must reference the new pump_architect package."""
    shim = os.path.join(PROJECT_ROOT, "pump_app.py")
    with open(shim) as fh:
        content = fh.read()
    assert "pump_architect" in content, (
        "pump_app.py does not import from pump_architect package"
    )
