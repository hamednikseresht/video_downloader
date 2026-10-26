import os

import streamlit as st

from src.download.errors import classify_download_error, format_guide_markdown
from src.download.formats import (
    build_output_basename,
    clean_download_title,
    build_subtitle_basename,
    build_thumbnail_basename,
    build_video_subtitle_basename,
    match_subtitle,
    parse_subtitles,
)
from src.logutil import read_log_tail
from src.platforms.detect import media_id
from src.download.paths import (
    clear_resume_files,
    find_existing_download,
    find_saved_download,
    resolve_subtitle_filepath,
    resolve_thumbnail_filepath,
)
from src.download.worker import make_progress_hook, ProgressState
from src.download.ydl import build_ydl_opts, needs_ffmpeg_for_download
from src.history import add_history_entry
from src.download.fetch import fetch_video_info
from src.settings import resolve_ffmpeg_location, validate_settings
from src.ui.download_ui import (
    begin_download_thread,
    offer_browser_download,
    run_download_with_progress,
    save_download_failure_log,
)
from src.utils.cookies import auth_from_settings, get_auth_cache_key


def execute_download(
    url: str,
    platform: str,
    title: str,
    download_dir: str,
    settings: dict,
    download_kind: str,
    is_video: bool,
    selected_format: dict,
    selected_subtitle: dict | None = None,
    subtitle_format: str = "srt",
    include_subtitles: bool = False,
    include_thumbnail: bool = False,
    record_history: bool = True,
    name_index: int | None = None,
    name_uploader: str = "",
    name_stamp: str = "",
    status_prefix: str = "",
    library_dir: str = "",
    wait: bool = True,
) -> dict:
    """Run a download job and optionally record it in history. Returns result snapshot."""
    settings_errors = validate_settings(settings)
    if settings_errors:
        return {
            "status": "error",
            "error": "\n".join(settings_errors),
            "download_kind": download_kind,
            "url": url,
            "title": title,
        }

    library = library_dir or download_dir
    already = find_saved_download(library, url, title, download_kind)
    if already:
        return {
            "status": "skipped",
            "filename": already,
            "extra_files": [],
            "download_kind": download_kind,
            "reason": "already in download folder",
            "url": url,
            "title": title,
        }

    is_subtitle = download_kind == "subtitle"
    is_thumbnail = download_kind == "thumbnail"
    subtitle_note = ""
    media_key = media_id(url)

    if include_subtitles and selected_subtitle and download_kind in ("video", "audio") and platform == "youtube":
        try:
            auth_key = get_auth_cache_key(settings)
            info = fetch_video_info(url, auth_key)
            options = parse_subtitles(info.get("subtitles") or {}, info.get("automatic_captions") or {})
            selected_subtitle, subtitle_note = match_subtitle(options, selected_subtitle)
            if subtitle_note:
                st.info(subtitle_note)
            if not selected_subtitle:
                include_subtitles = False
            if not name_uploader:
                name_uploader = info.get("uploader") or info.get("channel") or ""
            if not name_stamp:
                name_stamp = str(info.get("upload_date") or "")
        except Exception:
            include_subtitles = False
            selected_subtitle = None

    if needs_ffmpeg_for_download(download_kind, platform, include_subtitles) and not resolve_ffmpeg_location(
        settings["ffmpeg_path"]
    ):
        return {
            "status": "error",
            "error": "FFmpeg is required for this download.",
            "download_kind": download_kind,
            "hint": "ffmpeg",
            "url": url,
            "title": title,
        }

    if is_subtitle:
        output_basename = build_subtitle_basename(
            title, selected_subtitle["lang"], selected_subtitle["source"]
        )
        output_ext = subtitle_format
    elif is_thumbnail:
        output_basename = build_thumbnail_basename(title)
        output_ext = "jpg"
    else:
        safe_title = clean_download_title(title, url, name_uploader)
        clip_id = media_key
        if clip_id and clip_id.lower() in safe_title.lower():
            clip_id = ""
        output_basename = build_output_basename(
            safe_title,
            selected_format,
            is_video,
            uploader="" if name_uploader and name_uploader.lower() in safe_title.lower() else name_uploader,
            index=name_index,
            video_id=clip_id,
            stamp=name_stamp,
        )
        output_ext = "mp4" if is_video else "mp3"

    existing_file = find_existing_download(download_dir, output_basename, output_ext)
    if is_subtitle and not existing_file and selected_subtitle:
        existing_file = resolve_subtitle_filepath(
            download_dir,
            output_basename,
            selected_subtitle["lang"],
            output_ext,
            settings["ffmpeg_path"],
        )
    if is_thumbnail and not existing_file:
        existing_file = resolve_thumbnail_filepath(download_dir, output_basename)

    extra_basenames: list[tuple[str, str]] = []
    existing_extras: list[str] = []

    if include_subtitles and selected_subtitle and download_kind in ("video", "audio"):
        sub_basename = build_video_subtitle_basename(
            output_basename, selected_subtitle["lang"]
        )
        extra_basenames.append((sub_basename, subtitle_format))
        sub_existing = find_existing_download(download_dir, sub_basename, subtitle_format)
        if sub_existing:
            existing_extras.append(sub_existing)

    all_files_exist = existing_file is not None
    if extra_basenames:
        all_files_exist = all_files_exist and len(existing_extras) == len(extra_basenames)

    if all_files_exist:
        return {
            "status": "skipped",
            "filename": existing_file,
            "extra_files": existing_extras,
            "download_kind": download_kind,
            "url": url,
            "title": title,
        }

    clear_resume_files(download_dir, output_basename, media_key)

    browser, cookiefile = auth_from_settings(settings)
    auth_key = get_auth_cache_key(settings)
    progress = ProgressState()
    cached_info = fetch_video_info(url, auth_key) if is_subtitle else None
    ydl_opts = build_ydl_opts(
        output_basename,
        selected_format,
        download_kind,
        make_progress_hook(progress),
        download_dir,
        settings["ffmpeg_path"],
        subtitle=selected_subtitle if (is_subtitle or include_subtitles) else None,
        subtitle_format=subtitle_format,
        platform=platform,
        cookiefile=cookiefile,
        cookies_from_browser=browser,
        include_thumbnail=include_thumbnail and download_kind in ("video", "audio"),
    )

    if not wait:
        thread = begin_download_thread(
            url,
            ydl_opts,
            progress,
            download_dir,
            output_basename,
            output_ext,
            download_kind,
            extra_basenames=extra_basenames or None,
            cached_info=cached_info,
            subtitle=selected_subtitle if is_subtitle else None,
            subtitle_format=subtitle_format,
            ffmpeg_path=settings["ffmpeg_path"],
        )
        return {
            "status": "running",
            "thread": thread,
            "state": progress,
            "download_kind": download_kind,
            "url": url,
            "title": title,
            "platform": platform,
            "record_history": record_history,
        }

    result = run_download_with_progress(
        url,
        ydl_opts,
        progress,
        download_dir,
        output_basename,
        output_ext,
        download_kind,
        extra_basenames=extra_basenames or None,
        cached_info=cached_info,
        subtitle=selected_subtitle if is_subtitle else None,
        subtitle_format=subtitle_format,
        ffmpeg_path=settings["ffmpeg_path"],
        status_prefix=status_prefix,
    )
    result["download_kind"] = download_kind
    result["url"] = url
    result["title"] = title
    if subtitle_note:
        result["subtitle_note"] = subtitle_note
    if result.get("status") == "cancelled":
        clear_resume_files(download_dir, output_basename, media_key)
        return {
            "status": "cancelled",
            "error": result.get("error") or "Cancelled.",
            "download_kind": download_kind,
            "url": url,
            "title": title,
        }
    if result.get("status") == "error":
        clear_resume_files(download_dir, output_basename, media_key)
        log_path = save_download_failure_log(
            url,
            result.get("error") or "Unknown error",
            extra=(
                f"title: {title}\n"
                f"platform: {platform}\n"
                f"download_kind: {download_kind}\n"
                f"format_id: {(selected_format or {}).get('format_id', '')}\n"
            ),
        )
        result["error_log"] = log_path
    elif result.get("status") == "finished" and record_history and result.get("filename"):
        add_history_entry(
            url,
            title,
            result["filename"],
            download_kind,
            platform,
            download_dir=download_dir,
        )

    return result


def finish_background_download(slot: dict, download_dir: str) -> dict:
    thread = slot.get("thread")
    if thread is not None:
        thread.join(timeout=5)
    result = slot["state"].snapshot()
    result["download_kind"] = slot.get("download_kind")
    result["url"] = slot.get("url") or result.get("url") or ""
    result["title"] = slot.get("title") or result.get("title") or ""
    if result.get("status") in ("", "downloading", None) and not (thread and thread.is_alive()):
        result["status"] = "error"
        result["error"] = result.get("error") or "Download stopped before a file was saved."
    if result.get("status") == "finished" and slot.get("record_history") and result.get("filename"):
        add_history_entry(
            slot.get("url") or "",
            slot.get("title") or "",
            result["filename"],
            slot.get("download_kind") or "video",
            slot.get("platform") or "",
            download_dir=download_dir,
        )
    return result


def show_download_result(result: dict, download_dir: str, key_prefix: str = "saved") -> None:
    if not result:
        st.error("Download returned no result. Check the log below.")
        _render_log_tail(key_prefix)
        return

    status = result.get("status") or "error"
    if status == "error":
        kind = result.get("download_kind") or "video"
        raw = (result.get("error") or "").strip() or "Unknown error (no message from the downloader)."
        guide = classify_download_error(raw, kind)
        st.error(format_guide_markdown(guide))
        log_path = result.get("error_log")
        if not log_path:
            log_path = save_download_failure_log(
                result.get("url") or "",
                raw,
                extra=f"download_kind={kind}\ntitle={result.get('title') or ''}",
            )
            result["error_log"] = log_path
        st.caption(f"Full error log saved to `{log_path}`")
        _render_log_tail(key_prefix)
        _render_recovery_actions(guide.actions, key_prefix)
    elif status == "cancelled":
        st.warning(result.get("error") or "Cancelled.")
        _render_log_tail(key_prefix)
    elif status == "skipped":
        reason = result.get("reason") or "Already downloaded — using existing file."
        st.info(reason)
        path = result.get("filename") or ""
        if path:
            offer_browser_download(path, download_dir, key=f"{key_prefix}-main")
        for i, extra_path in enumerate(result.get("extra_files", [])):
            offer_browser_download(extra_path, download_dir, key=f"{key_prefix}-extra-{i}")
    elif status == "finished" or (result.get("filename") and os.path.isfile(result.get("filename") or "")):
        saved_files = [result["filename"], *result.get("extra_files", [])]
        with st.container(border=True):
            st.success("Download complete!")
            for i, path in enumerate(saved_files):
                st.caption(f"`{path}`")
                offer_browser_download(path, download_dir, key=f"{key_prefix}-{i}")
    else:
        st.error(
            f"Download ended with status `{status}` and no output file in `{download_dir}`.\n\n"
            f"{(result.get('error') or '').strip() or 'Open the log for details.'}"
        )
        _render_log_tail(key_prefix)


def _render_log_tail(key_prefix: str) -> None:
    tail = read_log_tail()
    if not tail:
        return
    with st.expander("Show log"):
        st.code(tail, language="text")


def _render_recovery_actions(actions: list[str], key_prefix: str) -> None:
    if not actions:
        return
    cols = st.columns(min(len(actions), 4))
    for i, action in enumerate(actions[:4]):
        with cols[i]:
            if action == "install_ffmpeg":
                if st.button("Install FFmpeg", key=f"{key_prefix}-ff-{i}", width="stretch"):
                    from src.setup.health import try_install_ffmpeg_windows

                    ok, msg = try_install_ffmpeg_windows()
                    (st.success if ok else st.warning)(msg)
            elif action == "install_packages":
                if st.button("Install packages", key=f"{key_prefix}-pkg-{i}", width="stretch"):
                    from src.setup.health import install_requirements

                    ok, msg = install_requirements()
                    (st.success if ok else st.error)(msg)
            elif action == "open_cookies":
                st.info("Open **Settings → YouTube cookies** in the sidebar.")
            elif action == "wait":
                st.caption("Wait 1–2 minutes, then download again.")
            elif action == "retry":
                st.caption("Click **Start download** again to retry.")
