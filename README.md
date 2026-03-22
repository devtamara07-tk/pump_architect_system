# Pump Test Architect

A Streamlit-based web application for managing pump testing projects. Organise
pump models, assign them to water tanks, and view a dashboard of your test
installation layout.

---

## Project structure

```
pump_architect_system/
├── pump_architect/          # Main Python package
│   ├── app.py               # Streamlit entrypoint (run this)
│   ├── db/
│   │   ├── connection.py    # DB path + connection helper
│   │   ├── schema.py        # Table creation (init_db)
│   │   └── repositories.py  # CRUD helpers
│   └── ui/
│       ├── assets.py        # Image / base64 helpers
│       ├── styles.py        # CSS injection
│       └── pages/
│           ├── home.py      # Project list page
│           ├── project_form.py  # Create / modify project
│           └── dashboard.py # Tank & pump dashboard
├── pump_app.py              # Legacy shim (redirects to new entrypoint)
├── pump_icon.png
├── pump_icon2.png
├── requirements.txt
└── README.md
```

---

## Installation

> Works on **Windows**, **macOS/Linux**, and **GitHub Codespaces**.

```bash
# 1. (Optional) create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux / Codespaces
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt
```

---

## Running the app

```bash
streamlit run pump_app.py
```

Open the URL shown in the terminal (usually `http://localhost:8501`) in your
browser.  
In **GitHub Codespaces**, the port is forwarded automatically – click the pop-up
link or open the **Ports** tab.

---

## Database

The app uses a local **SQLite** database (`architect_system.db`).  
It is **created automatically** the first time you run the app – you do not need
to create it manually.  
The file is listed in `.gitignore` and will not be committed to the repository.

---

## Quick smoke-test checklist

After starting the app, verify the following in your browser:

1. **Home page** loads and shows *Pump Test Architect 1.0*.
2. Click **➕ Create New Project** → form opens.
3. Enter a **Test Type** (e.g., *Endurance Test*) and at least one pump model in
   the **Pump Model** column.  Pump IDs (`P-01`, `P-02`, …) auto-fill.
4. Click **➕ Add Water Tank** if needed, then assign pumps to tanks via the
   multiselect boxes.
5. Click **💾 Save Project** → success message appears and you are returned to
   the home page.
6. The project now appears in the **Current Project List**.
7. Click **OPEN** → dashboard shows tanks and pump tiles.
8. Click **Modify** → form loads the existing data correctly.
9. Click **Delete** → project is removed from the list.

All nine steps passing means the app is working correctly.
