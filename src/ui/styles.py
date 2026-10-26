import streamlit as st


def inject_custom_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        :root {
            --background: #ffffff;
            --foreground: #0f172a;
            --card: #ffffff;
            --muted: #f1f5f4;
            --muted-foreground: #475569;
            --border: #d5dedc;
            --primary: #0f766e;
            --primary-hover: #115e59;
            --primary-foreground: #ffffff;
            --accent: #c2410c;
            --ring: #0f766e;
            --ok: #047857;
            --warn: #b45309;
            --bad: #b91c1c;
            --radius: 8px;
        }

        html, body, [class*="css"], .stApp, .stMarkdown, button, input, textarea, select {
            font-family: Inter, ui-sans-serif, system-ui, sans-serif;
        }
        .stApp { background: var(--muted); color: var(--foreground); }
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 3rem;
            max-width: 1040px;
        }
        [data-testid="stSidebar"] {
            background: var(--background);
            border-right: 1px solid var(--border);
        }
        [data-testid="stSidebar"] .block-container { padding-top: 1.25rem; }

        .app-hero {
            background: var(--background);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.25rem 1.5rem;
            margin-bottom: 1rem;
            box-shadow: 0 1px 2px rgba(9, 9, 11, 0.04);
        }
        .app-kicker {
            margin: 0 0 0.35rem 0;
            font-size: 0.75rem;
            font-weight: 600;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            color: var(--muted-foreground);
        }
        .app-hero h1 {
            color: var(--foreground) !important;
            font-size: 1.75rem !important;
            font-weight: 600 !important;
            letter-spacing: -0.03em;
            line-height: 1.2 !important;
            margin: 0 !important;
        }
        .app-hero h1 span {
            font-size: 0.85rem;
            font-weight: 500;
            color: var(--muted-foreground);
            letter-spacing: 0;
        }
        .app-hero p {
            color: var(--muted-foreground) !important;
            margin: 0.4rem 0 0 0 !important;
            font-size: 0.95rem;
            line-height: 1.5;
            max-width: 42rem;
        }

        .section-label {
            font-size: 0.8rem;
            font-weight: 600;
            letter-spacing: -0.01em;
            text-transform: none;
            color: var(--foreground);
            margin: 0.75rem 0 0.35rem 0;
        }
        .stat-row { display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0.75rem 0 0.25rem 0; }
        .stat-pill {
            display: inline-flex;
            align-items: center;
            background: var(--muted);
            border: 1px solid var(--border);
            border-radius: 999px;
            padding: 0.2rem 0.65rem;
            font-size: 0.8rem;
            font-weight: 500;
            color: var(--foreground);
        }
        .selection-box {
            border: 1px solid var(--border);
            background: var(--background);
            border-radius: var(--radius);
            padding: 0.75rem 0.9rem;
            margin: 0.75rem 0;
            font-size: 0.9rem;
            line-height: 1.5;
        }
        .empty-state {
            text-align: left;
            padding: 1.5rem;
            border: 1px dashed var(--border);
            border-radius: 12px;
            background: var(--background);
            margin-top: 0.5rem;
        }
        .empty-state h2 {
            margin: 0;
            font-size: 1.05rem;
            font-weight: 600;
            letter-spacing: -0.02em;
        }
        .empty-state p {
            margin: 0.35rem 0 0 0;
            color: var(--muted-foreground);
            font-size: 0.9rem;
            line-height: 1.5;
        }
        .sidebar-status { font-size: 0.85rem; line-height: 1.7; color: var(--foreground); }
        .status-ok { color: var(--ok); }
        .status-warn { color: var(--warn); }
        .status-bad { color: var(--bad); }

        div[data-testid="stTabs"] button[data-baseweb="tab"] {
            font-weight: 500;
            border-radius: var(--radius) var(--radius) 0 0;
            cursor: pointer;
            min-height: 44px;
        }
        div[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] {
            color: var(--primary);
        }
        div[data-testid="stTabs"] [data-baseweb="tab-highlight"] { background: var(--primary); }
        div[data-testid="stTabs"] button[data-baseweb="tab"]:focus-visible {
            outline: 2px solid var(--ring);
            outline-offset: -2px;
        }
        .stButton > button {
            border-radius: var(--radius);
            min-height: 40px;
            font-weight: 500;
            border: 1px solid var(--border);
            cursor: pointer;
            transition: background-color 160ms ease, border-color 160ms ease;
        }
        .stButton > button:hover { border-color: var(--primary); color: var(--primary); }
        .stButton > button:disabled { cursor: not-allowed; opacity: 0.55; }
        .stButton > button[kind="primary"],
        .stButton > button[data-testid="stBaseButton-primary"] {
            background: var(--primary);
            color: var(--primary-foreground);
            border-color: var(--primary);
        }
        .stButton > button[kind="primary"]:hover,
        .stButton > button[data-testid="stBaseButton-primary"]:hover {
            background: var(--primary-hover);
            border-color: var(--primary-hover);
            color: var(--primary-foreground);
        }
        .stButton > button:focus-visible,
        a:focus-visible,
        input:focus-visible,
        textarea:focus-visible,
        [role="checkbox"]:focus-visible,
        [role="radio"]:focus-visible {
            outline: 2px solid var(--ring);
            outline-offset: 2px;
        }
        div[data-baseweb="input"]:focus-within > div,
        div[data-baseweb="textarea"]:focus-within > div,
        div[data-baseweb="select"]:focus-within > div {
            border-color: var(--ring) !important;
            box-shadow: 0 0 0 1px var(--ring);
        }
        [data-testid="stProgress"] [role="progressbar"] > div > div,
        [data-testid="stProgress"] > div > div > div > div { background-color: var(--primary); }
        ::selection { background: #99f6e4; color: var(--foreground); }
        div[data-baseweb="input"] > div,
        div[data-baseweb="textarea"] > div,
        div[data-baseweb="select"] > div {
            border-radius: var(--radius) !important;
            border-color: var(--border) !important;
            background: var(--background);
        }
        [data-testid="stAlert"] { border-radius: var(--radius); }
        [data-testid="stMetric"] {
            background: var(--background);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 0.65rem 0.8rem;
        }
        [data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 12px !important;
            border-color: var(--border) !important;
            background: var(--background);
        }
        img { border-radius: var(--radius); }
        .plan-board { margin: 0.25rem 0 0.75rem; }
        .plan-stats {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 8px;
        }
        .plan-stat {
            background: var(--background);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 10px 12px;
        }
        .plan-stat b {
            display: block;
            font-size: 1.25rem;
            letter-spacing: -0.03em;
            font-variant-numeric: tabular-nums;
        }
        .plan-stat span { color: var(--muted-foreground); font-size: 0.8rem; }
        .plan-issues { list-style: none; margin: 8px 0 0; padding: 0; }
        .plan-issues li {
            background: var(--background);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 10px 12px;
            margin-top: 8px;
        }
        .plan-issues strong { display: block; white-space: normal; word-spacing: normal; }
        .plan-issues span {
            display: block;
            color: var(--bad);
            font-size: 0.875rem;
            white-space: normal;
            word-spacing: normal;
            letter-spacing: normal;
        }
        @media (max-width: 768px) {
            .plan-stats { grid-template-columns: 1fr 1fr; }
        }
        @media (prefers-reduced-motion: reduce) {
            .stButton > button { transition: none; }
            * { scroll-behavior: auto !important; animation-duration: 0.01ms !important; }
        }
        @media (max-width: 768px) {
            .block-container { padding-left: 1rem; padding-right: 1rem; }
            .app-hero h1 { font-size: 1.4rem !important; }
            .stButton > button { min-height: 44px; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
