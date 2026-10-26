"""In-app health check panel + first-run auto setup."""

from __future__ import annotations

import os
import sys

import streamlit as st

from src.constants import PROJECT_ROOT
from src.setup.auto_setup import is_first_run, run_auto_setup
from src.setup.health import (
    HealthReport,
    install_requirements,
    repair_numpy,
    run_health_check,
    try_install_ffmpeg_windows,
)


def _ensure_health_cache() -> HealthReport:
    if "health_report" not in st.session_state:
        download_dir = None
        if "settings" in st.session_state:
            download_dir = st.session_state.settings.get("download_dir")
        st.session_state.health_report = run_health_check(download_dir)
    return st.session_state.health_report


def refresh_health_report() -> HealthReport:
    download_dir = None
    if "settings" in st.session_state:
        download_dir = st.session_state.settings.get("download_dir")
    report = run_health_check(download_dir)
    st.session_state.health_report = report
    return report


def _run_auto_setup_ui() -> None:
    st.info("**New system detected** — setting up automatically…")
    with st.status("Auto setup in progress…", expanded=True) as status:
        steps = run_auto_setup(try_ffmpeg=(os.name == "nt"))
        for name, ok, msg in steps:
            if ok:
                st.write(f"✓ **{name}**: {msg}")
            else:
                st.write(f"• **{name}**: {msg}")
        if steps and steps[-1][0] == "ready" and steps[-1][1]:
            status.update(label="Setup complete", state="complete")
        else:
            status.update(label="Setup needs your attention", state="error")
    refresh_health_report()
    # Reload settings into session after bootstrap.
    from src.settings import load_settings

    st.session_state.settings = load_settings()
    st.session_state.auto_setup_done = True


def render_startup_health_gate() -> bool:
    """Return True if the app may continue. False blocks main UI."""
    if is_first_run() and not st.session_state.get("auto_setup_done"):
        _run_auto_setup_ui()
        st.rerun()

    report = _ensure_health_cache()

    if report.can_start:
        warnings = [c for c in report.checks if c.status == "warn"]
        if warnings and not st.session_state.get("health_dismissed"):
            with st.expander("Setup tips (optional improvements)", expanded=False):
                for w in warnings:
                    st.warning(f"**{w.name}**: {w.message}")
                    if w.fix:
                        st.caption(w.fix.replace("\n", "  \n"))
                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button("Re-check system", key="health_recheck_top"):
                        refresh_health_report()
                        st.rerun()
                with c2:
                    if st.button("Fix what we can", key="health_fix_warn"):
                        _fix_everything()
                        st.rerun()
                with c3:
                    if st.button("Dismiss", key="health_dismiss"):
                        st.session_state.health_dismissed = True
                        st.rerun()
        return True

    st.error("**Setup incomplete** — required components are missing. Fix the items below, then continue.")

    for check in report.checks:
        if check.status == "fail":
            st.markdown(f"**{check.name}**: {check.message}")
            if check.fix:
                st.info(check.fix)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("Fix everything", type="primary", key="health_fix_all"):
            _fix_everything()
            st.rerun()
    with col2:
        if st.button("Install packages", key="health_install_deps"):
            ok, msg = install_requirements()
            (st.success if ok else st.error)(msg)
            refresh_health_report()
            st.rerun()
    with col3:
        if st.button("Re-check", key="health_recheck_block"):
            refresh_health_report()
            st.rerun()
    with col4:
        if os.name == "nt" and st.button("Install FFmpeg", key="health_install_ffmpeg"):
            ok, msg = try_install_ffmpeg_windows()
            (st.success if ok else st.warning)(msg)
            refresh_health_report()
            st.rerun()

    with st.expander("Manual setup commands"):
        st.code(
            f"cd \"{PROJECT_ROOT}\"\n"
            f"{sys.executable} -m pip install -r requirements.txt\n"
            f"{sys.executable} scripts/healthcheck.py --check",
            language="powershell",
        )
        st.markdown(
            "- **Python**: [python.org/downloads](https://www.python.org/downloads/) (3.11+ recommended, add to PATH)\n"
            "- **FFmpeg**: `winget install Gyan.FFmpeg` or [ffmpeg.org](https://ffmpeg.org/download.html)\n"
            "- **YouTube HD**: Node.js 22+ or Deno 2.3+\n"
            "- Delete leftover `.part` files in the download folder if a previous attempt failed"
        )

    return False


def _fix_everything() -> None:
    with st.spinner("Installing packages and checking FFmpeg…"):
        steps = run_auto_setup(try_ffmpeg=(os.name == "nt"))
    for name, ok, msg in steps:
        (st.success if ok else st.warning)(f"{name}: {msg}")
    report = refresh_health_report()
    numpy_fail = next((c for c in report.checks if c.name == "numpy" and c.status == "fail"), None)
    if numpy_fail:
        ok, msg = repair_numpy()
        (st.success if ok else st.error)(msg)
        refresh_health_report()
    from src.settings import load_settings

    st.session_state.settings = load_settings()


def render_health_expander_sidebar() -> None:
    report = _ensure_health_cache()

    with st.sidebar:
        with st.expander("Health check", expanded=False):
            for check in report.checks:
                icon = {"ok": "OK", "warn": "!", "fail": "X"}[check.status]
                st.caption(f"[{icon}] **{check.name}**: {check.message}")

            if st.button("Re-run checks", key="sidebar_health_refresh", width="stretch"):
                refresh_health_report()
                st.rerun()

            if st.button("Fix everything", key="sidebar_fix_all", width="stretch"):
                _fix_everything()
                st.rerun()

            if any(c.status == "fail" for c in report.checks):
                if st.button("Install packages", key="sidebar_install_deps", width="stretch"):
                    ok, msg = install_requirements()
                    st.toast(msg, icon="✅" if ok else "❌")
                    refresh_health_report()
                    st.rerun()
