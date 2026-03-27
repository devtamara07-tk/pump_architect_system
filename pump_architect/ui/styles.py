import streamlit as st


def inject_compact_css():
    """Apply the legacy-aligned industrial theme to the modular UI."""
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

            :root {
                --bg: #121417;
                --bg-elevated: #171b20;
                --panel: #1c1f24;
                --panel-2: #20252c;
                --border: #313843;
                --text: #f4f7fb;
                --muted: #9aa7b7;
                --accent: #4da3ff;
                --accent-strong: #0d6efd;
                --accent-soft: rgba(77, 163, 255, 0.14);
                --warn: #eedd82;
                --success: #2ecc71;
                --danger: #ff6b6b;
            }

            html, body, [data-testid="stAppViewContainer"], .stApp, .main {
                background:
                    radial-gradient(circle at top right, rgba(77, 163, 255, 0.14), transparent 24%),
                    linear-gradient(180deg, #171a20 0%, #121417 42%, #101216 100%) !important;
                color: var(--text) !important;
                font-family: 'Barlow', sans-serif !important;
            }

            [data-testid="stHeader"] {
                background: transparent !important;
            }

            [data-testid="stMainBlockContainer"], .block-container {
                width: 100vw !important;
                max-width: 100vw !important;
                padding-top: 2rem !important;
                padding-bottom: 2rem !important;
                padding-left: 2rem !important;
                padding-right: 2rem !important;
            }

            h1, h2, h3, h4, h5, h6,
            p, li, span, label, div {
                font-family: 'Barlow', sans-serif !important;
            }

            h1, h2, h3, h4, h5, h6 {
                color: var(--accent) !important;
                letter-spacing: 0.04em;
            }

            p, li, span, div[data-testid="stMarkdownContainer"] p {
                color: var(--text);
            }

            code, pre {
                font-family: 'IBM Plex Mono', monospace !important;
            }

            .hero-panel {
                background:
                    linear-gradient(135deg, rgba(7, 15, 26, 0.9), rgba(15, 26, 42, 0.78)),
                    url('https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?q=80&w=2070&auto=format&fit=crop');
                background-size: cover;
                background-position: center;
                border: 1px solid var(--border);
                border-radius: 18px;
                padding: 2.5rem 2rem;
                box-shadow: 0 20px 50px rgba(0, 0, 0, 0.28);
                margin-bottom: 1.6rem;
                width: 100%;
                max-width: 100%;
                box-sizing: border-box;
            }

            .hero-kicker {
                color: var(--muted) !important;
                text-transform: uppercase;
                letter-spacing: 0.24em;
                font-size: 0.82rem;
                font-weight: 700;
                margin-bottom: 0.7rem;
            }

            .hero-title {
                color: #ffffff !important;
                font-size: 2.7rem;
                font-weight: 700;
                line-height: 1.05;
                margin: 0;
            }

            .hero-subtitle {
                color: #c5d2e2 !important;
                font-size: 1.08rem;
                margin-top: 0.6rem;
                margin-bottom: 0;
                max-width: 48rem;
            }

            .section-heading {
                color: var(--accent) !important;
                font-size: 1.25rem;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.1em;
                margin: 0.4rem 0 0.8rem;
            }

            .panel-shell {
                background: linear-gradient(180deg, rgba(31, 36, 43, 0.95), rgba(24, 28, 34, 0.95));
                border: 1px solid var(--border);
                border-radius: 16px;
                padding: 1rem 1.1rem;
                box-shadow: inset 0 1px 0 rgba(255,255,255,0.02);
            }

            .project-table-header {
                color: var(--accent) !important;
                font-size: 0.96rem;
                font-weight: 700;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                border-bottom: 1px solid rgba(255,255,255,0.08);
                padding-bottom: 0.5rem;
            }

            .project-cell {
                color: var(--text) !important;
                font-size: 1rem;
                font-weight: 500;
                padding-top: 0.25rem;
            }

            .status-pill {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                min-width: 5.5rem;
                padding: 0.38rem 0.78rem;
                border-radius: 999px;
                background: linear-gradient(180deg, rgba(13, 110, 253, 0.95), rgba(11, 93, 214, 0.95));
                color: #ffffff !important;
                font-size: 0.8rem;
                font-weight: 700;
                letter-spacing: 0.08em;
                text-transform: uppercase;
            }

            .muted-note {
                color: var(--muted) !important;
                font-size: 0.96rem;
            }

            .project-badge {
                display: inline-block;
                background: var(--accent-soft);
                border: 1px solid rgba(77, 163, 255, 0.28);
                color: #d8ebff !important;
                padding: 0.7rem 0.9rem;
                border-radius: 12px;
                font-weight: 600;
                margin-bottom: 1rem;
            }

            .project-badge strong {
                color: #ffffff !important;
            }

            .dashboard-shell {
                background: linear-gradient(180deg, rgba(28, 31, 36, 0.98), rgba(22, 25, 30, 0.98));
                border: 1px solid var(--border);
                border-left: 5px solid var(--accent);
                border-radius: 16px;
                padding: 1.15rem 1.25rem;
                margin-bottom: 1.25rem;
            }

            .dashboard-kicker {
                color: var(--accent) !important;
                text-transform: uppercase;
                letter-spacing: 0.16em;
                font-size: 0.8rem;
                font-weight: 700;
                margin-bottom: 0.35rem;
            }

            .dashboard-title {
                color: #ffffff !important;
                font-size: 1.95rem;
                font-weight: 700;
                margin: 0;
            }

            .tank-title {
                color: #ffffff !important;
                font-size: 1.15rem;
                font-weight: 700;
                margin-bottom: 0.7rem;
            }

            .metric-chip {
                display: inline-block;
                margin-right: 0.55rem;
                margin-top: 0.35rem;
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 999px;
                padding: 0.34rem 0.68rem;
                color: #d3deea !important;
                font-size: 0.84rem;
                font-weight: 600;
            }

            .pump-card {
                text-align: center;
                border: 1px solid rgba(77, 163, 255, 0.28);
                border-radius: 16px;
                padding: 1rem 0.8rem;
                min-height: 11rem;
                background: linear-gradient(180deg, #15304f 0%, #10243a 100%);
                color: #ffffff !important;
                box-shadow: 0 12px 24px rgba(5, 14, 25, 0.28);
            }

            .pump-card img {
                display: block;
                margin: 0 auto 0.7rem;
            }

            .pump-card-id {
                color: #ffffff !important;
                font-size: 1.05rem;
                font-weight: 700;
                margin-bottom: 0.25rem;
            }

            .pump-card-model {
                color: #d8e7f7 !important;
                font-size: 0.95rem;
            }

            hr {
                border-color: rgba(255,255,255,0.08) !important;
                margin-top: 0.75rem !important;
                margin-bottom: 0.75rem !important;
            }

            div[data-testid="stAlert"] {
                background: linear-gradient(180deg, rgba(30, 41, 59, 0.96), rgba(24, 32, 45, 0.96)) !important;
                border: 1px solid #334155 !important;
                border-radius: 14px !important;
                color: #ffffff !important;
            }

            div[data-testid="stAlert"] p,
            div[data-testid="stAlert"] span,
            div[data-testid="stAlert"] div {
                color: #ffffff !important;
            }

            div[data-testid="stDataEditor"] {
                background-color: var(--panel) !important;
                border: 1px solid var(--border) !important;
                border-radius: 14px !important;
                overflow: hidden;
            }

            div[data-testid="stDataEditor"] * {
                color: var(--text) !important;
            }

            div[data-testid="stTextInput"] input,
            div[data-testid="stNumberInput"] input,
            div[data-testid="stTextArea"] textarea,
            div[data-baseweb="select"] > div,
            div[data-baseweb="base-input"] > div,
            div[data-testid="stMultiSelect"] [data-baseweb="select"] > div {
                background-color: var(--panel) !important;
                color: var(--text) !important;
                border: 1px solid var(--border) !important;
                border-radius: 12px !important;
            }

            /* --- DROPDOWN POPUP MENU (selectbox / multiselect) --- */
            [data-baseweb="popover"] > div,
            [data-baseweb="menu"] {
                background-color: var(--panel) !important;
                border: 1px solid var(--border) !important;
                border-radius: 12px !important;
            }
            [data-baseweb="menu"] [role="option"],
            [role="listbox"] [role="option"] {
                background-color: var(--panel) !important;
                color: var(--text) !important;
                font-size: 0.95rem !important;
            }
            [data-baseweb="menu"] [role="option"]:hover,
            [data-baseweb="menu"] [aria-selected="true"],
            [role="listbox"] [role="option"][aria-selected="true"] {
                background-color: var(--accent-soft) !important;
                color: var(--accent) !important;
            }

            div[role="radiogroup"] label,
            label p,
            .stRadio label p,
            .stTextInput label p,
            .stNumberInput label p,
            .stSelectbox label p,
            .stMultiSelect label p {
                color: #ffffff !important;
                font-size: 1rem !important;
                font-weight: 600 !important;
            }

            div[role="radiogroup"] label div {
                color: #d9e4f0 !important;
                font-size: 0.95rem !important;
            }

            div.stButton > button,
            div[data-testid="stDownloadButton"] > button {
                background: linear-gradient(180deg, #f4f7fb 0%, #dce4ef 100%) !important;
                color: #09111a !important;
                border: 1px solid #c4d1de !important;
                border-radius: 12px !important;
                font-size: 0.95rem !important;
                font-weight: 700 !important;
                min-height: 2.85rem !important;
                box-shadow: none !important;
            }

            div.stButton > button *,
            div[data-testid="stDownloadButton"] > button * {
                color: #09111a !important;
                fill: #09111a !important;
            }

            div.stButton > button[kind="primary"],
            div[data-testid="stDownloadButton"] > button[kind="primary"] {
                background: linear-gradient(180deg, var(--accent-strong) 0%, #0b5ed7 100%) !important;
                color: #ffffff !important;
                border: none !important;
            }

            div.stButton > button[kind="primary"] *,
            div[data-testid="stDownloadButton"] > button[kind="primary"] * {
                color: #ffffff !important;
                fill: #ffffff !important;
            }

            div.stButton > button:hover,
            div[data-testid="stDownloadButton"] > button:hover {
                border-color: var(--accent) !important;
                color: #081018 !important;
            }

            div.stButton > button:hover *,
            div[data-testid="stDownloadButton"] > button:hover * {
                color: #081018 !important;
                fill: #081018 !important;
            }

            button[aria-label^="DANGER "] {
                background: linear-gradient(180deg, #ff7f7f 0%, #dc4c4c 100%) !important;
                color: #FFFFFF !important;
                border: 1px solid #b53737 !important;
            }

            button[aria-label^="DANGER "] * {
                color: #FFFFFF !important;
                fill: #FFFFFF !important;
            }

            div[data-testid="stVerticalBlockBorderWrapper"] {
                background: linear-gradient(180deg, rgba(28, 31, 36, 0.98), rgba(22, 25, 30, 0.98));
                border: 1px solid var(--border) !important;
                border-radius: 16px !important;
            }

            @media (max-width: 900px) {
                [data-testid="stMainBlockContainer"] {
                    padding-left: 0.5rem !important;
                    padding-right: 0.5rem !important;
                }
                .hero-panel {
                    padding: 1.2rem 0.5rem;
                }
                .hero-title {
                    font-size: 1.5rem;
                }
            }

            /* Extra mobile-friendly tweaks for phones */
            @media (max-width: 600px) {
                [data-testid="stMainBlockContainer"] {
                    padding-left: 0.1rem !important;
                    padding-right: 0.1rem !important;
                }
                .hero-panel {
                    padding: 0.4rem 0.1rem;
                }
                .hero-title {
                    font-size: 1.1rem;
                }
                .hero-subtitle {
                    font-size: 0.8rem;
                }
                .section-heading {
                    font-size: 0.9rem;
                }
                .dashboard-title {
                    font-size: 1rem;
                }
                .project-table-header, .project-cell {
                    font-size: 0.75rem;
                }
                img, .stImage {
                    max-width: 100% !important;
                    height: auto !important;
                }
                .stButton > button, .stDownloadButton > button {
                    min-height: 2rem !important;
                    font-size: 0.8rem !important;
                }
                /* Stack columns vertically for project table */
                .stHorizontalBlock {
                    flex-direction: column !important;
                }
            }
        </style>
    """, unsafe_allow_html=True)
