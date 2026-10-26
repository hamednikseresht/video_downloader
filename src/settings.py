import json
import os
import shutil
import tempfile

import streamlit as st

from src.constants import (
    DEFAULT_COOKIES_FILE,
    SETTINGS_FILE,
    _WINDOWS_FFMPEG_PATHS,
)
from src.download.paths import (
    download_dir_setting_value,
    list_recent_downloads,
    resolve_download_dir,
)
from src.security import (
    is_safe_ffmpeg_path,
    sanitize_browser_choice,
    sanitize_cookies_path,
)
from src.ui.cookies_panel import render_cookies_settings


def default_ffmpeg_path() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    for path in _WINDOWS_FFMPEG_PATHS:
        if os.path.isfile(path):
            return path
    return ""


def default_settings() -> dict:
    return {
        "download_dir": resolve_download_dir("downloads", create=False),
        "ffmpeg_path": default_ffmpeg_path(),
        "cookies_path": DEFAULT_COOKIES_FILE,
        "cookies_from_browser": "",
        "batch_pause_sec": 1.5,
    }


def load_settings() -> dict:
    settings = default_settings()
    if not os.path.isfile(SETTINGS_FILE):
        return settings

    try:
        with open(SETTINGS_FILE, encoding="utf-8") as fh:
            saved = json.load(fh)
        if isinstance(saved.get("download_dir"), str) and saved["download_dir"].strip():
            settings["download_dir"] = resolve_download_dir(saved["download_dir"], create=False)
        if isinstance(saved.get("ffmpeg_path"), str):
            candidate = saved["ffmpeg_path"].strip()
            settings["ffmpeg_path"] = candidate if is_safe_ffmpeg_path(candidate) else ""
        if isinstance(saved.get("cookies_path"), str):
            settings["cookies_path"] = sanitize_cookies_path(saved["cookies_path"])
        if isinstance(saved.get("cookies_from_browser"), str):
            settings["cookies_from_browser"] = sanitize_browser_choice(
                saved["cookies_from_browser"]
            )
        try:
            pause = float(saved.get("batch_pause_sec", 1.5))
        except (TypeError, ValueError):
            pause = 1.5
        settings["batch_pause_sec"] = min(120.0, max(0.0, pause))
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        settings["_load_warning"] = f"Could not read settings.json ({exc}). Using defaults."
        _backup_corrupt_settings()

    settings["download_dir"] = resolve_download_dir(settings["download_dir"], create=False)
    return settings


def _backup_corrupt_settings() -> None:
    if not os.path.isfile(SETTINGS_FILE):
        return
    bak = SETTINGS_FILE + ".corrupt.bak"
    try:
        shutil.copy2(SETTINGS_FILE, bak)
    except OSError:
        pass


def save_settings(settings: dict) -> None:
    payload = {k: v for k, v in settings.items() if not str(k).startswith("_")}
    if isinstance(payload.get("download_dir"), str):
        # Create only when the user explicitly saves.
        resolved = resolve_download_dir(payload["download_dir"], create=True)
        payload["download_dir"] = download_dir_setting_value(resolved)
    if isinstance(payload.get("cookies_path"), str):
        payload["cookies_path"] = sanitize_cookies_path(payload["cookies_path"])
    if isinstance(payload.get("cookies_from_browser"), str):
        payload["cookies_from_browser"] = sanitize_browser_choice(
            payload["cookies_from_browser"]
        )
    if isinstance(payload.get("ffmpeg_path"), str) and not is_safe_ffmpeg_path(
        payload["ffmpeg_path"]
    ):
        payload["ffmpeg_path"] = ""

    directory = os.path.dirname(SETTINGS_FILE) or "."
    fd, tmp_path = tempfile.mkstemp(prefix=".settings_", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        os.replace(tmp_path, SETTINGS_FILE)
    except Exception:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


def resolve_ffmpeg_location(ffmpeg_path: str) -> str | None:
    path = (ffmpeg_path or "").strip()
    if not path:
        path = default_ffmpeg_path()
    if not path:
        return None
    if not is_safe_ffmpeg_path(path):
        return None

    if os.path.isdir(path):
        exe = os.path.join(path, "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
        return path if os.path.isfile(exe) else None

    if os.path.isfile(path):
        return os.path.dirname(os.path.abspath(path))

    return None


def validate_settings(settings: dict) -> list[str]:
    errors = []
    download_dir = (settings.get("download_dir") or "").strip()
    if not download_dir:
        errors.append("Download folder cannot be empty.")
    else:
        resolved = resolve_download_dir(download_dir, create=False)
        parent = os.path.dirname(os.path.abspath(resolved))
        if not os.path.isdir(parent):
            errors.append(f"Parent folder does not exist: `{parent}`")
        elif os.path.isdir(resolved) and not os.access(resolved, os.W_OK):
            errors.append(f"Download folder is not writable: `{resolved}`")

    ffmpeg_path = settings.get("ffmpeg_path", "").strip()
    if ffmpeg_path:
        if not is_safe_ffmpeg_path(ffmpeg_path):
            errors.append("FFmpeg path must point to an `ffmpeg` binary or its folder.")
        elif resolve_ffmpeg_location(ffmpeg_path) is None:
            errors.append(f"FFmpeg not found at `{ffmpeg_path}`.")

    browser = settings.get("cookies_from_browser", "")
    if browser and not sanitize_browser_choice(str(browser)):
        errors.append("Invalid browser cookie choice.")

    return errors


def init_settings_state() -> None:
    if "settings" not in st.session_state:
        st.session_state.settings = load_settings()


def render_settings_sidebar(
    *,
    show_open_folder: bool = True,
    key_prefix: str = "app",
) -> dict:
    init_settings_state()
    saved = st.session_state.settings

    with st.sidebar:
        st.markdown("### Settings")
        st.caption("Paths, cookies, and download folder.")

        warning = saved.get("_load_warning")
        if warning:
            st.warning(warning)

        with st.expander("Paths", expanded=True):
            download_dir = st.text_input(
                "Download folder",
                value=download_dir_setting_value(saved["download_dir"]),
                help="Folder where completed downloads are saved (default: downloads in this project).",
            )
            ffmpeg_path = st.text_input(
                "FFmpeg path",
                value=saved["ffmpeg_path"],
                placeholder="Auto-detect from PATH",
                help="Path to ffmpeg.exe or the folder that contains it.",
            )
            batch_pause_sec = st.number_input(
                "Pause between batch items (seconds)",
                min_value=0.0,
                max_value=120.0,
                value=float(saved.get("batch_pause_sec", 1.5)),
                step=0.5,
                help="Longer pauses reduce YouTube HTTP 429 errors.",
                key=f"{key_prefix}_batch_pause",
            )

        cookie_fields = render_cookies_settings(saved, key_prefix=key_prefix)

        # Do not create directories while typing — only resolve for display/open.
        folder_path = resolve_download_dir(download_dir, create=False)
        if show_open_folder:
            from src.utils.files import open_folder

            if st.button(
                "Open downloads folder",
                width="stretch",
                key=f"{key_prefix}_open_downloads_folder",
            ):
                if os.path.isdir(folder_path) and open_folder(folder_path):
                    st.toast(f"Opened `{folder_path}`")
                else:
                    st.error("Folder does not exist yet. Click Save first.")

        save_col, reset_col = st.columns(2)
        with save_col:
            save_clicked = st.button("Save", type="primary", width="stretch")
        with reset_col:
            reset_clicked = st.button("Reset", width="stretch")

        if save_clicked:
            settings = {
                "download_dir": resolve_download_dir(
                    download_dir.strip() or "downloads", create=True
                ),
                "ffmpeg_path": ffmpeg_path.strip(),
                "cookies_path": sanitize_cookies_path(
                    saved.get("cookies_path", DEFAULT_COOKIES_FILE)
                ),
                "cookies_from_browser": sanitize_browser_choice(
                    cookie_fields["cookies_from_browser"]
                ),
                "batch_pause_sec": float(batch_pause_sec),
            }
            errors = validate_settings(settings)
            if errors:
                for err in errors:
                    st.error(err)
            else:
                st.session_state.settings = settings
                save_settings(settings)
                from src.download.fetch import clear_fetch_cache

                clear_fetch_cache()
                st.success("Settings saved.")

        if reset_clicked:
            st.session_state.settings = default_settings()
            save_settings(st.session_state.settings)
            st.rerun()

        # Defer listing until expander is opened (avoids disk scan every rerun).
        with st.expander("Recent files", expanded=False):
            recent = list_recent_downloads(folder_path)
            if recent:
                for name, size in recent:
                    st.caption(f"**{name}** · {size}")
            else:
                st.caption("No files yet.")

    # Active session uses the last saved download folder — typing does not create dirs until Save.
    active_dir = resolve_download_dir(saved["download_dir"], create=True)
    return {
        "download_dir": active_dir,
        "ffmpeg_path": ffmpeg_path.strip(),
        "cookies_path": sanitize_cookies_path(
            saved.get("cookies_path", DEFAULT_COOKIES_FILE)
        ),
        "cookies_from_browser": sanitize_browser_choice(
            cookie_fields.get("cookies_from_browser")
            or saved.get("cookies_from_browser", "")
        ),
        "batch_pause_sec": float(batch_pause_sec),
    }
