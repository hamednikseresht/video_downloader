import os
import threading
import time
from datetime import datetime

import streamlit as st

from src.constants import MAX_BROWSER_DOWNLOAD_BYTES, PROJECT_ROOT
from src.download.formats import format_size
from src.download.worker import do_download, ProgressState
from src.security import assert_under_download_dir

_ACTIVE_DOWNLOAD = "active_download"
_ERROR_LOG_DIR = os.path.join(PROJECT_ROOT, "logs")


def offer_browser_download(filepath: str, download_dir: str, key: str | None = None):
    if not filepath or not os.path.isfile(filepath):
        return

    try:
        safe_path = assert_under_download_dir(filepath, download_dir)
    except ValueError:
        st.warning("File is outside the download folder and cannot be served.")
        return

    file_size = os.path.getsize(safe_path)
    basename = os.path.basename(safe_path)
    file_ext = os.path.splitext(safe_path)[1].lower()

    icon = {".mp4": "Video", ".mp3": "Audio", ".srt": "Subtitles", ".vtt": "Subtitles"}.get(
        file_ext, "File"
    )

    if file_size > MAX_BROWSER_DOWNLOAD_BYTES:
        st.info(
            f"{icon} **{basename}** ({format_size(file_size)}) saved to `{download_dir}` "
            "(too large for in-browser download)."
        )
        return

    mime_map = {
        ".mp4": "video/mp4",
        ".mp3": "audio/mpeg",
        ".srt": "text/plain",
        ".vtt": "text/vtt",
    }
    mime = mime_map.get(file_ext, "application/octet-stream")
    with open(safe_path, "rb") as fh:
        st.download_button(
            label=f"{icon} {basename} ({format_size(file_size)})",
            data=fh,
            file_name=basename,
            mime=mime,
            width="stretch",
            key=key or basename,
        )


def cancel_active_download() -> None:
    slot = st.session_state.get(_ACTIVE_DOWNLOAD)
    if slot and slot.get("state") is not None:
        slot["state"].request_cancel()


def begin_download_thread(
    url: str,
    ydl_opts: dict,
    state: ProgressState,
    download_dir: str,
    output_basename: str,
    ext: str,
    download_kind: str = "video",
    extra_basenames: list[tuple[str, str]] | None = None,
    cached_info: dict | None = None,
    subtitle: dict | None = None,
    subtitle_format: str = "srt",
    ffmpeg_path: str = "",
) -> threading.Thread:
    thread = threading.Thread(
        target=do_download,
        args=(
            url,
            ydl_opts,
            state,
            download_dir,
            output_basename,
            ext,
            download_kind,
            extra_basenames,
            cached_info,
            subtitle,
            subtitle_format,
            ffmpeg_path,
        ),
        daemon=True,
    )
    thread.start()
    return thread


def save_download_failure_log(url: str, error: str, extra: str = "") -> str:
    """Write a failure report the user can open later. Returns the log path."""
    os.makedirs(_ERROR_LOG_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(_ERROR_LOG_DIR, f"download-error-{stamp}.log")
    lines = [
        f"time: {datetime.now().isoformat(timespec='seconds')}",
        f"url: {url}",
        f"error: {error}",
    ]
    if extra:
        lines.append("details:")
        lines.append(extra)
    try:
        from src.logutil import read_log_tail

        tail = read_log_tail(limit=120)
        if tail:
            lines.append("")
            lines.append("--- app.log tail ---")
            lines.append(tail)
    except Exception:
        pass
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")
    return path


def run_download_with_progress(
    url: str,
    ydl_opts: dict,
    state: ProgressState,
    download_dir: str,
    output_basename: str,
    ext: str,
    download_kind: str = "video",
    extra_basenames: list[tuple[str, str]] | None = None,
    cached_info: dict | None = None,
    subtitle: dict | None = None,
    subtitle_format: str = "srt",
    ffmpeg_path: str = "",
    status_prefix: str = "",
):
    """Start the download and wait in this script run until it finishes.

    Staying in one run avoids Streamlit losing the Start-download click on refresh.
    """
    thread = begin_download_thread(
        url,
        ydl_opts,
        state,
        download_dir,
        output_basename,
        ext,
        download_kind,
        extra_basenames,
        cached_info,
        subtitle,
        subtitle_format,
        ffmpeg_path,
    )
    st.session_state[_ACTIVE_DOWNLOAD] = {
        "token": f"{url}|{output_basename}|{download_kind}",
        "thread": thread,
        "state": state,
    }

    prefix = f"{status_prefix} " if status_prefix else ""
    progress_box = st.empty()
    caption_box = st.empty()

    while thread.is_alive():
        snap = state.snapshot()
        pct = min(float(snap.get("percent") or 0), 100.0)
        progress_box.progress(max(int(pct), 1) / 100.0, text=f"{prefix}{pct:.0f}%")
        if snap.get("phase") == "postprocessing":
            caption_box.caption(f"{prefix}Merging with FFmpeg…")
        elif snap.get("error"):
            caption_box.caption(f"{prefix}{snap['error']}")
        elif snap.get("speed") or snap.get("eta"):
            caption_box.caption(
                f"{prefix}{pct:.0f}% · {snap.get('speed') or ''} · ETA {snap.get('eta') or ''}".strip()
            )
        else:
            caption_box.caption(f"{prefix}Downloading… {pct:.0f}%")
        time.sleep(0.4)

    snap = state.snapshot()
    st.session_state.pop(_ACTIVE_DOWNLOAD, None)
    thread.join(timeout=10)

    if snap.get("status") == "finished":
        progress_box.progress(1.0, text=f"{prefix}100%")
        caption_box.caption(f"{prefix}Finished.")
    elif snap.get("status") == "error":
        caption_box.error(snap.get("error") or "Download failed.")
    elif snap.get("status") == "cancelled":
        caption_box.warning("Cancelled.")

    if not snap.get("status"):
        snap["status"] = "error"
        snap["error"] = snap.get("error") or "Download ended without a status."
    return snap


def has_active_download() -> bool:
    slot = st.session_state.get(_ACTIVE_DOWNLOAD)
    thread = (slot or {}).get("thread")
    return bool(thread and thread.is_alive())
