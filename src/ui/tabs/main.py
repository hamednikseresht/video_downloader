import os

import streamlit as st

from src.constants import APP_VERSION
from src.logutil import get_logger
from src.settings import render_settings_sidebar
from src.setup.health_ui import render_health_expander_sidebar, render_startup_health_gate
from src.ui.tabs.history import render_history_tab
from src.ui.tabs.playlist import render_playlist_tab
from src.ui.tabs.profile import render_profile_tab
from src.ui.tabs.single import render_single_tab
from src.ui.queue import render_batch_queue_tab
from src.ui.status import render_sidebar_status
from src.ui.styles import inject_custom_css

log = get_logger("app")


def render_app_header() -> None:
    st.markdown(
        f"""
        <div class="app-hero">
            <p class="app-kicker">Local media tool</p>
            <h1>YouTube & Instagram Downloader <span>v{APP_VERSION}</span></h1>
            <p>Download video, audio, subtitles, playlists, and the latest posts from a profile.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def run_app() -> None:
    st.set_page_config(
        page_title=f"YouTube Downloader v{APP_VERSION}",
        page_icon=":material/download:",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    if not st.session_state.get("_app_started_logged"):
        log.info("App start v%s", APP_VERSION)
        st.session_state["_app_started_logged"] = True
    inject_custom_css()
    settings = render_settings_sidebar(show_open_folder=True, key_prefix="app")
    download_dir = settings["download_dir"]
    os.makedirs(download_dir, exist_ok=True)
    render_health_expander_sidebar()
    render_sidebar_status(download_dir, settings["ffmpeg_path"])

    if not render_startup_health_gate():
        st.stop()

    main_col, _ = st.columns([1, 0.08])
    with main_col:
        render_app_header()

        tab_single, tab_playlist, tab_profile, tab_batch, tab_history = st.tabs(
            ["Single", "Playlist", "Profile", "Batch queue", "History"]
        )

        with tab_single:
            render_single_tab(download_dir, settings)

        with tab_playlist:
            render_playlist_tab(download_dir, settings)

        with tab_profile:
            render_profile_tab(download_dir, settings)

        with tab_batch:
            render_batch_queue_tab(download_dir, settings)

        with tab_history:
            render_history_tab(download_dir, settings)
