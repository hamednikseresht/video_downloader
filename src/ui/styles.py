import streamlit as st


def inject_custom_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        :root {
            --background: #ffffff;
            --foreground: #09090b;
            --card: #ffffff;
            --muted: #f4f4f5;
            --muted-foreground: #71717a;
            --border: #e4e4e7;
            --primary: #18181b;
            --primary-foreground: #fafafa;
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
        .status-ok { color: #047857; }
        .status-warn { color: #b45309; }
        .status-bad { color: #b91c1c; }

        div[data-testid="stTabs"] button[data-baseweb="tab"] {
            font-weight: 500;
            border-radius: var(--radius) var(--radius) 0 0;
        }
        .stButton > button {
            border-radius: var(--radius);
            min-height: 40px;
            font-weight: 500;
            border: 1px solid var(--border);
            transition: background-color 160ms ease, border-color 160ms ease;
        }
        .stButton > button[kind="primary"],
        .stButton > button[data-testid="stBaseButton-primary"] {
            background: var(--primary);
            color: var(--primary-foreground);
            border-color: var(--primary);
        }
        .stButton > button:focus-visible {
            outline: 2px solid #18181b;
            outline-offset: 2px;
        }
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
        .plan-stat b { display: block; font-size: 1.25rem; letter-spacing: -0.03em; }
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
            color: #b91c1c;
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
        }
        @media (max-width: 768px) {
            .block-container { padding-left: 1rem; padding-right: 1rem; }
            .app-hero h1 { font-size: 1.4rem !important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
