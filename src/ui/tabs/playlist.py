import os
import time

import streamlit as st

from src.constants import BATCH_ITEM_PAUSE_SEC, PLAYLIST_QUEUE_FILE, PLAYLIST_REPORT_FILE
from src.download.batch_plan import range_needs_confirm
from src.download.batch_report import new_batch_id, write_batch_report
from src.download.errors import classify_download_error, pauses_queue
from src.download.fetch import clear_fetch_cache, fetch_formats, fetch_playlist_entries
from src.download.formats import (
    format_duration,
    preferred_audio_format,
    preferred_video_format,
    quality_note,
    sanitize_title,
)
from src.history import is_url_saved
from src.platforms.detect import detect_platform, is_youtube_playlist_or_channel, trim_url_state
from src.queue_store import clear_queue, load_queue, restore_queue, save_queue
from src.ui.download_ui import cancel_active_download
from src.ui.execute import execute_download
from src.ui.components import section_label
from src.ui.queue_controls import pause_message, render_extra_download_options, render_queue_pause
from src.ui.url_file import render_url_file_uploader, take_uploaded_urls
from src.utils.cookies import get_auth_cache_key

_PLAYLIST_JOB_KEY = "playlist_job"


def render_playlist_tab(download_dir: str, settings: dict) -> None:
    section_label("Playlist or channel URL")
    st.caption(
        "YouTube playlists, channels, and URLs with `list=` are supported. "
        "Downloads use preferred quality (no per-item format fetch) with a short pause between items. "
        "Extra text around the link is removed automatically. "
        "You can also load a .txt or .csv file."
    )

    restore_queue(st.session_state, _PLAYLIST_JOB_KEY, PLAYLIST_QUEUE_FILE)
    job = st.session_state.get(_PLAYLIST_JOB_KEY)
    if job:
        _render_playlist_job(download_dir, settings, job)
        return

    uploaded = render_url_file_uploader("Load a text or CSV file", "playlist_url_file")
    found = take_uploaded_urls(st.session_state, uploaded, "playlist_url_file_token")
    if found is not None:
        pick = next((url for url in found if is_youtube_playlist_or_channel(url)), None)
        if pick:
            st.session_state["playlist_url"] = pick
            st.success(f"Loaded playlist link from `{uploaded.name}`.")
        else:
            st.warning("No playlist or channel link in that file. Use Batch queue for single videos.")

    trim_url_state(st.session_state, "playlist_url")

    url = st.text_input(
        "Playlist URL",
        placeholder="https://youtube.com/playlist?list=... or https://youtube.com/@channel",
        label_visibility="collapsed",
        key="playlist_url",
    )

    if not url:
        st.info("Paste a YouTube playlist or channel URL above.")
        return

    if not is_youtube_playlist_or_channel(url) and detect_platform(url) != "youtube":
        st.error("Playlist downloads support **YouTube** playlists and channels only.")
        return

    auth_key = get_auth_cache_key(settings)

    if st.button("Load playlist", type="primary", key="load_playlist"):
        st.session_state.playlist_fetch = True

    if st.session_state.get("playlist_fetch"):
        with st.spinner("Loading playlist entries…"):
            try:
                playlist_title, entries = fetch_playlist_entries(url, auth_key)
                st.session_state.playlist_data = {
                    "url": url,
                    "title": playlist_title,
                    "entries": entries,
                }
                st.session_state.playlist_fetch = False
            except Exception as e:
                st.error(f"Could not load playlist: `{e}`")
                st.session_state.playlist_fetch = False
                return

    data = st.session_state.get("playlist_data")
    if not data or data.get("url") != url.strip():
        return

    entries = data["entries"]
    if not entries:
        st.warning("No videos found in this playlist.")
        return

    st.subheader(data["title"])
    total = len(entries)
    st.caption(f"{total} videos")
    if total >= 50:
        st.warning(
            f"This playlist or channel has **{total}** videos. "
            "Choose a short range, such as items 1–20, before downloading."
        )

    batch_type = st.radio(
        "Download as",
        ["Video", "Audio"],
        horizontal=True,
        key="playlist_type",
    )
    prefer_height = st.selectbox(
        "Video quality (when available)",
        [1080, 720, 480, 360],
        index=1,
        key="playlist_height",
    )
    if entries:
        try:
            sample = fetch_formats(entries[0]["url"], auth_key)
            heights = [item.get("height") or 0 for item in sample[5]]
            note = quality_note(int(prefer_height), heights)
            if note:
                (st.warning if "tops out" in note else st.caption)(note)
        except Exception as exc:
            st.caption(f"Could not check quality for the first video: {exc}")

    range_col1, range_col2 = st.columns(2)
    with range_col1:
        from_idx = st.number_input("From item", min_value=1, max_value=total, value=1, key="playlist_from")
    with range_col2:
        to_idx = st.number_input(
            "To item", min_value=1, max_value=total, value=min(total, 10), key="playlist_to"
        )

    from_i = int(from_idx)
    to_i = int(to_idx)
    if from_i > to_i:
        st.error("“From” must be less than or equal to “To”.")
        return

    slice_entries = entries[from_i - 1 : to_i]

    with st.expander(f"Preview items {from_i}–{to_i}", expanded=False):
        for entry in slice_entries:
            dur = format_duration(entry.get("duration", 0))
            st.text(f"{entry['index']}. {entry['title']} · {dur}")

    extras = render_extra_download_options("playlist")
    needs_confirm = range_needs_confirm(total, len(slice_entries))
    confirmed = True
    if needs_confirm:
        confirmed = st.checkbox(
            f"Download items {from_i}–{to_i} ({len(slice_entries)} videos) from this list of {total}",
            key="playlist_confirm_range",
        )

    if st.button(
        f"Download {len(slice_entries)} items",
        type="primary",
        width="stretch",
        key="playlist_download",
        disabled=not confirmed,
    ):
        batch_id = new_batch_id("playlist")
        output_dir = os.path.join(download_dir, batch_id)
        os.makedirs(output_dir, exist_ok=True)
        _store_playlist(
            {
                "entries": slice_entries,
                "index": 0,
                "batch_type": batch_type,
                "prefer_height": prefer_height,
                "batch_id": batch_id,
                "output_dir": output_dir,
                "playlist_title": data.get("title") or "",
                "paused": False,
                "include_subtitles": extras["include_subtitles"],
                "selected_subtitle": extras["selected_subtitle"],
                "subtitle_format": extras["subtitle_format"],
                "include_thumbnail": extras["include_thumbnail"],
                "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "skip_existing": extras["skip_existing"],
            }
        )
        st.rerun()

    if st.button("Clear playlist cache", key="clear_playlist"):
        clear_fetch_cache()
        st.session_state.pop("playlist_data", None)
        _clear_playlist()
        st.rerun()


def _store_playlist(job: dict | None) -> None:
    if not job:
        _clear_playlist()
        return
    st.session_state[_PLAYLIST_JOB_KEY] = job
    save_queue(PLAYLIST_QUEUE_FILE, job)


def _clear_playlist() -> None:
    st.session_state[_PLAYLIST_JOB_KEY] = None
    clear_queue(PLAYLIST_QUEUE_FILE)


def _render_playlist_job(download_dir: str, settings: dict, job: dict) -> None:
    if job.get("paused"):
        action = render_queue_pause(job, "playlist")
        if action == "resume":
            job["paused"] = False
            _store_playlist(job)
            st.rerun()
        elif action == "skip":
            job["index"] = job.get("index", 0) + 1
            job["paused"] = False
            _store_playlist(job)
            st.rerun()
        elif action == "stop":
            _clear_playlist()
            st.warning("Playlist download stopped.")
            st.rerun()
        return

    if st.button("Stop playlist", type="secondary", key="playlist_stop"):
        cancel_active_download()
        _clear_playlist()
        st.warning("Playlist download stopped.")
        st.rerun()
    # Do not steal the script run while Single tab is downloading.
    if st.session_state.get("single_download_lock") or st.session_state.get("single_active"):
        st.caption("Playlist is paused while a Single download finishes.")
        return
    _process_playlist_job(download_dir, settings, job)


def _process_playlist_job(download_dir: str, settings: dict, job: dict | None = None) -> None:
    job = job or st.session_state.get(_PLAYLIST_JOB_KEY)
    if not job:
        return

    entries = job["entries"]
    index = job["index"]
    total = len(entries)

    item_dir = job.get("output_dir") or download_dir
    if index >= total:
        _finish_playlist(job)
        return

    entry = entries[index]
    entry_url = entry["url"]
    title = entry["title"]
    is_video = job["batch_type"] == "Video"
    download_kind = "video" if is_video else "audio"
    selected_format = (
        preferred_video_format(job["prefer_height"]) if is_video else preferred_audio_format()
    )
    remaining = sum(int(item.get("duration") or 0) for item in entries[index:])

    st.text(f"{entry['index']}. {title} ({index + 1}/{total})")
    if remaining:
        st.caption(f"About {format_duration(remaining)} left in this range.")

    if is_url_saved(download_dir, entry_url, title, download_kind):
        st.info(f"Already in the download folder: {title}")
        job.setdefault("results", []).append(
            {"url": entry_url, "title": title, "status": "skipped", "error": "Already in the download folder"}
        )
        job["index"] = index + 1
        _store_playlist(job)
        if job["index"] >= total:
            _finish_playlist(job)
        else:
            time.sleep(_pause_seconds(settings))
            st.rerun()
        return

    result = execute_download(
        url=entry_url,
        platform="youtube",
        title=title,
        download_dir=item_dir,
        settings=settings,
        download_kind=download_kind,
        is_video=is_video,
        selected_format=selected_format,
        selected_subtitle=job.get("selected_subtitle") if job.get("include_subtitles") else None,
        subtitle_format=job.get("subtitle_format") or "srt",
        include_subtitles=bool(job.get("include_subtitles")),
        include_thumbnail=bool(job.get("include_thumbnail")),
        status_prefix=f"[{index + 1}/{total}]",
        name_index=entry.get("index") or (index + 1),
        name_uploader=entry.get("uploader") or "",
        library_dir=download_dir,
    )
    job.setdefault("results", [])
    if result["status"] == "cancelled":
        job["paused"] = True
        job["pause_message"] = result.get("error") or "Cancelled."
        job["pause_url"] = entry_url
        job["pause_title"] = title
        job["pause_error"] = job["pause_message"]
        _store_playlist(job)
        st.rerun()
        return
    if result["status"] == "error":
        guide = classify_download_error(result.get("error") or "", download_kind)
        if pauses_queue(guide):
            job["paused"] = True
            job["pause_message"] = pause_message(guide)
            job["pause_url"] = entry_url
            job["pause_title"] = title
            job["pause_error"] = result.get("error") or guide.title
            _store_playlist(job)
            st.rerun()
            return
        st.error(result["error"])
        job["results"].append({"url": entry_url, "title": title, "status": "error", "error": result.get("error")})
    elif result["status"] == "skipped":
        st.info(f"Skipped (exists): {title}")
        job["results"].append({"url": entry_url, "title": title, "status": "skipped"})
    elif result.get("filename"):
        st.success(f"Saved: {result['filename']}")
        job["results"].append({"url": entry_url, "title": title, "status": "ok"})
    else:
        job["results"].append({"url": entry_url, "title": title, "status": "error", "error": "Output file not found"})

    job["index"] = index + 1
    _store_playlist(job)

    if job["index"] >= total:
        _finish_playlist(job)
    else:
        time.sleep(_pause_seconds(settings))
        st.rerun()


def _finish_playlist(job: dict) -> None:
    results = job.get("results") or []
    title = job.get("playlist_title") or "Playlist download"
    batch_id = job.get("batch_id") or new_batch_id("playlist")
    report_path = write_batch_report(
        results,
        {
            "kind": "playlist",
            "title": f"{title} · {batch_id}",
            "detail": f"{job.get('batch_type', 'Video')} · {job.get('prefer_height', '')}p · started {job.get('started_at', '')}",
        },
        dest_dir=job.get("output_dir") or None,
        report_name=batch_id,
    )
    save_queue(PLAYLIST_REPORT_FILE, {"results": results, "html": report_path})
    st.session_state["last_playlist_report"] = report_path
    st.success(f"Playlist finished. Report saved: `{report_path}`")
    _clear_playlist()


def _pause_seconds(settings: dict) -> float:
    try:
        return float(settings.get("batch_pause_sec", BATCH_ITEM_PAUSE_SEC))
    except (TypeError, ValueError):
        return BATCH_ITEM_PAUSE_SEC
