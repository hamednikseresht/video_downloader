import os
import threading
import time

import yt_dlp

from src.constants import DOWNLOAD_TRANSIENT_RETRIES, SUBTITLE_PREFETCH_PAUSE_SEC
from src.download.paths import (
    clear_resume_files,
    resolve_downloaded_filepath,
    resolve_thumbnail_filepath,
)
from src.logutil import get_logger
from src.platforms.youtube import progressive_fallback_selector
from src.subtitles.convert import download_subtitle_direct, download_subtitle_with_ytdlp

log = get_logger("download")


class DownloadCancelled(Exception):
    """Raised from the progress hook when the user cancels the active file."""


class ProgressState:
    def __init__(self):
        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self.reset()

    def request_cancel(self) -> None:
        self._cancel.set()

    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def reset(self):
        with self._lock:
            self.percent = 0.0
            self.speed = ""
            self.eta = ""
            self.status = "downloading"
            self.phase = "downloading"
            self.filename = ""
            self.extra_files = []
            self.error = ""

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "percent": self.percent,
                "speed": self.speed,
                "eta": self.eta,
                "status": self.status,
                "phase": self.phase,
                "filename": self.filename,
                "extra_files": list(self.extra_files),
                "error": self.error,
            }


def make_progress_hook(state: ProgressState):
    def progress_hook(d):
        if state.cancelled():
            raise DownloadCancelled("Cancelled by user")
        with state._lock:
            status = d.get("status")
            if status == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes", 0)
                state.percent = (downloaded / total * 100) if total else state.percent
                state.speed = d.get("_speed_str", "").strip()
                state.eta = d.get("_eta_str", "").strip()
                state.phase = "downloading"
                state.status = "downloading"
            elif status == "postprocessing":
                state.phase = "postprocessing"
                state.status = "downloading"
                state.percent = max(state.percent, 95.0)
                state.speed = ""
                state.eta = ""
            elif status == "finished":
                state.percent = max(state.percent, 90.0)
            elif status == "error":
                state.status = "error"
                state.error = str(d.get("error", "Unknown error"))

    return progress_hook


def _is_transient_error(message: str) -> bool:
    text = message.lower()
    return (
        "429" in message
        or "too many requests" in text
        or "timed out" in text
        or "timeout" in text
        or "temporarily unavailable" in text
        or "connection reset" in text
        or "network is unreachable" in text
    )


def _is_windows_path_error(message: str) -> bool:
    text = message.lower()
    return "errno 22" in text or "invalid argument" in text


def _apply_format_fallback(opts: dict, attempt: int) -> dict:
    """After HLS/Errno 22, switch to a progressive HTTP file that Windows can write."""
    next_opts = dict(opts)
    next_opts["format"] = progressive_fallback_selector(attempt)
    next_opts["concurrent_fragment_downloads"] = 1
    next_opts["windowsfilenames"] = True
    next_opts["restrictfilenames"] = True
    next_opts["continuedl"] = False
    next_opts["overwrites"] = True
    return next_opts


def do_download(
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
):
    involves_subtitles = download_kind == "subtitle" or ydl_opts.get("writesubtitles") or ydl_opts.get(
        "writeautomaticsub"
    )
    max_attempts = max(DOWNLOAD_TRANSIENT_RETRIES, 3)
    if involves_subtitles:
        max_attempts = max(max_attempts, 4)
    last_error = ""
    opts = dict(ydl_opts)

    for attempt in range(max_attempts):
        try:
            filepath: str | None = None
            extra_files: list[str] = []

            if attempt > 0:
                with state._lock:
                    state.phase = "downloading"
                    state.status = "downloading"
                    state.error = f"Retrying ({attempt + 1}/{max_attempts})…"
                    state.percent = 0.0

            if download_kind == "subtitle" and cached_info and subtitle:
                if attempt == 0:
                    time.sleep(SUBTITLE_PREFETCH_PAUSE_SEC)
                try:
                    filepath = download_subtitle_with_ytdlp(
                        cached_info,
                        opts,
                        download_dir,
                        output_basename,
                        ext,
                        subtitle,
                        ffmpeg_path,
                    )
                except Exception as primary_error:
                    last_error = str(primary_error)
                    is_rate_limited = _is_transient_error(last_error)
                    if is_rate_limited or attempt >= max_attempts - 1:
                        browser = None
                        cookie_tuple = opts.get("cookiesfrombrowser")
                        if cookie_tuple:
                            browser = cookie_tuple[0] if isinstance(cookie_tuple, tuple) else cookie_tuple
                        filepath = download_subtitle_direct(
                            cached_info,
                            subtitle,
                            subtitle_format,
                            download_dir,
                            output_basename,
                            ffmpeg_path,
                            cookiefile=opts.get("cookiefile"),
                            cookies_from_browser=browser,
                        )
                        last_error = ""
                    else:
                        raise
            else:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    if download_kind == "thumbnail":
                        filepath = resolve_thumbnail_filepath(download_dir, output_basename)
                    else:
                        filepath = resolve_downloaded_filepath(
                            info, ydl, download_dir, output_basename, ext
                        )
                    for basename, file_ext in extra_basenames or []:
                        extra_path = resolve_downloaded_filepath(
                            info, ydl, download_dir, basename, file_ext
                        )
                        if extra_path and os.path.isfile(extra_path):
                            extra_files.append(extra_path)

            with state._lock:
                if filepath and os.path.isfile(filepath):
                    state.status = "finished"
                    state.phase = "finished"
                    state.percent = 100.0
                    state.filename = filepath
                    state.extra_files = extra_files
                    log.info("Finished %s → %s", download_kind, filepath)
                else:
                    state.status = "error"
                    state.error = (
                        "Download finished but the output file was not found. "
                        f"Check `{download_dir}` or review FFmpeg settings."
                    )
                    clear_resume_files(download_dir, output_basename)
            return
        except DownloadCancelled:
            clear_resume_files(download_dir, output_basename)
            with state._lock:
                state.status = "cancelled"
                state.error = "Cancelled."
            log.info("Download cancelled for %s", url)
            return
        except Exception as e:
            if state.cancelled():
                clear_resume_files(download_dir, output_basename)
                with state._lock:
                    state.status = "cancelled"
                    state.error = "Cancelled."
                log.info("Download cancelled for %s", url)
                return
            last_error = str(e)
            log.warning("Attempt %s/%s failed for %s: %s", attempt + 1, max_attempts, url, last_error)
            clear_resume_files(download_dir, output_basename)
            if attempt >= max_attempts - 1:
                break
            if _is_windows_path_error(last_error) and download_kind in ("video", "audio"):
                opts = _apply_format_fallback(opts, attempt)
                log.info("Falling back to a progressive format for %s", url)
                wait = 1
            elif _is_transient_error(last_error):
                wait = 8 * (2**attempt)
            else:
                wait = 3 * (attempt + 1)
            with state._lock:
                state.phase = "downloading"
                state.status = "downloading"
                state.error = f"Retrying ({attempt + 2}/{max_attempts})…"
            time.sleep(wait)
            continue

    clear_resume_files(download_dir, output_basename)
    with state._lock:
        state.status = "error"
        state.error = last_error
    log.error("Download failed for %s: %s", url, last_error)
