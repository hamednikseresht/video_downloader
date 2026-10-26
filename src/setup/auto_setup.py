"""First-run / new-PC automatic setup."""

from __future__ import annotations

import os
from pathlib import Path

from src.constants import PROJECT_ROOT, SETTINGS_FILE
from src.logutil import get_logger
from src.setup.health import (
    ensure_dependencies,
    run_health_check,
    try_install_ffmpeg_windows,
)

log = get_logger("setup")

SETUP_MARKER = Path(PROJECT_ROOT) / ".setup_complete"


def is_first_run() -> bool:
    return not SETUP_MARKER.is_file() and not os.path.isfile(SETTINGS_FILE)


def mark_setup_complete() -> None:
    try:
        SETUP_MARKER.write_text("ok\n", encoding="utf-8")
    except OSError as exc:
        log.warning("Could not write setup marker: %s", exc)


def bootstrap_default_settings() -> dict:
    """Create downloads folder + settings.json with safe defaults."""
    from src.download.paths import resolve_download_dir
    from src.settings import default_settings, save_settings

    settings = default_settings()
    settings["download_dir"] = resolve_download_dir(settings["download_dir"], create=True)
    save_settings(settings)
    log.info("Default settings saved to %s", SETTINGS_FILE)
    return settings


def run_auto_setup(*, try_ffmpeg: bool = True) -> list[tuple[str, bool, str]]:
    """Install what we can. Returns list of (step, ok, message)."""
    steps: list[tuple[str, bool, str]] = []

    try:
        settings = bootstrap_default_settings()
        steps.append(("settings", True, f"Download folder ready: {settings['download_dir']}"))
    except Exception as exc:
        steps.append(("settings", False, str(exc)))

    ok, msg = ensure_dependencies()
    steps.append(("packages", ok, msg))

    if try_ffmpeg and os.name == "nt":
        ok_ff, msg_ff = try_install_ffmpeg_windows()
        steps.append(("ffmpeg", ok_ff, msg_ff))
    else:
        report = run_health_check()
        ff = next((c for c in report.checks if c.name == "ffmpeg"), None)
        if ff and ff.status == "ok":
            steps.append(("ffmpeg", True, ff.message))
        else:
            steps.append(
                (
                    "ffmpeg",
                    False,
                    (ff.fix if ff and ff.fix else "Install FFmpeg and add it to PATH."),
                )
            )

    report = run_health_check()
    if report.can_start:
        mark_setup_complete()
        steps.append(("ready", True, "System is ready to download."))
    else:
        fails = [c.name for c in report.checks if c.status == "fail"]
        steps.append(("ready", False, f"Still missing: {', '.join(fails) or 'unknown'}"))

    return steps
