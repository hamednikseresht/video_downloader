import html
import os
import time

import streamlit as st

from src.constants import BATCH_ITEM_PAUSE_SEC, BATCH_QUEUE_FILE, BATCH_REPORT_FILE
from src.download.batch_plan import classify_batch_urls, split_by_platform
from src.download.batch_report import new_batch_id, write_batch_report
from src.download.errors import classify_download_error, pauses_queue
from src.download.fetch import fetch_formats, fetch_video_info
from src.download.formats import preferred_audio_format, preferred_video_format, quality_note
from src.history import is_url_saved
from src.platforms.detect import detect_platform, merge_url_blocks, normalize_media_url, trim_url_state
from src.queue_store import clear_queue, load_queue, restore_queue, save_queue
from src.ui.components import section_label
from src.ui.download_ui import cancel_active_download, offer_browser_download
from src.ui.execute import execute_download, finish_background_download
from src.ui.queue_controls import pause_message, render_extra_download_options
from src.ui.url_file import render_url_file_uploader, take_uploaded_urls
from src.utils.cookies import auth_for_batch, get_auth_cache_key


_BATCH_JOB_KEY = "batch_job"


def _show_html(markup: str) -> None:
    """Render HTML without Streamlit markdown eating the spaces."""
    if hasattr(st, "html"):
        st.html(markup)
        return
    st.markdown(markup, unsafe_allow_html=True)


def render_batch_queue_tab(download_dir: str, settings: dict) -> None:
    section_label("Batch download")
    st.caption(
        "Paste YouTube or Instagram links, or load a .txt or .csv file. "
        "The batch first cleans the links, splits YouTube and Instagram, "
        "checks each video, then downloads. Both platforms run together when both are present."
    )

    _restore_batch_job()
    pending = st.session_state.pop("batch_urls_pending", None)
    if pending:
        st.session_state["batch_urls"] = merge_url_blocks(
            st.session_state.get("batch_urls") or "",
            pending,
        )
    _show_saved_report(BATCH_REPORT_FILE, "batch")

    uploaded = render_url_file_uploader("Load URLs from a text or CSV file", "batch_url_file")
    found = take_uploaded_urls(st.session_state, uploaded, "batch_url_file_token")
    if found is not None:
        if found:
            st.session_state["batch_urls"] = merge_url_blocks(
                st.session_state.get("batch_urls") or "",
                found,
            )
            st.success(f"Loaded {len(found)} link(s) from `{uploaded.name}`.")
        else:
            st.warning(f"No YouTube or Instagram links found in `{uploaded.name}`.")

    trim_url_state(st.session_state, "batch_urls", multiline=True)

    urls_text = st.text_area(
        "URLs",
        placeholder="https://youtube.com/watch?v=...\nhttps://instagram.com/reel/...",
        height=140,
        label_visibility="collapsed",
        key="batch_urls",
    )

    plan = classify_batch_urls(urls_text or "")
    already_count = sum(1 for url in plan["videos"] if is_url_saved(download_dir, url))
    st.caption(
        f"{len(plan['videos'])} video link(s) · {len(plan['playlists'])} playlist/channel link(s)"
        + (f" · {already_count} already in the download folder" if already_count else "")
    )
    if plan["playlists"]:
        st.info(
            "Playlist and channel links are not downloaded in this tab. "
            "Open the Playlist tab for those."
        )
        for url in plan["playlists"]:
            st.caption(url)

    batch_type = st.radio(
        "Download type",
        ["Video", "Audio"],
        horizontal=True,
        key="batch_type",
    )
    prefer_height = st.selectbox(
        "Video quality (when available)",
        [1080, 720, 480, 360],
        index=1,
        key="batch_video_height",
    )
    if plan["videos"]:
        _show_quality_hint(plan["videos"][0], int(prefer_height), settings)
    extras = render_extra_download_options("batch")

    job = st.session_state.get(_BATCH_JOB_KEY)

    if job:
        st.caption(f"Batch {job.get('batch_id', '')} stays saved if you refresh this page.")
        if job.get("message"):
            st.info(job["message"])
        restart_col, new_col = st.columns(2)
        with restart_col:
            if st.button("Restart", type="secondary", width="stretch", key="batch_restart"):
                _restart_batch(job)
                st.rerun()
        with new_col:
            if st.button("Start new", type="primary", width="stretch", key="batch_start_new"):
                cancel_active_download()
                _clear_batch()
                st.rerun()
        _process_batch_job(download_dir, settings)
    elif st.button("Prepare and download", type="primary", width="stretch", key="batch_start"):
        _start_batch_job(plan["videos"], batch_type, int(prefer_height), extras, download_dir, settings)

    st.caption(f"Files save to `{download_dir}`")


def _restore_batch_job() -> None:
    restore_queue(st.session_state, _BATCH_JOB_KEY, BATCH_QUEUE_FILE)
    job = st.session_state.get(_BATCH_JOB_KEY)
    if not job:
        return
    changed = False
    for item in job.get("items") or []:
        if item.get("status") == "downloading":
            item["status"] = "ready"
            item["error"] = ""
            changed = True
    if changed:
        job["message"] = (
            f"Batch {job.get('batch_id', '')} was restored after a refresh. "
            "Downloads that were in progress will continue."
        )
        _store_batch(job)


def _restart_batch(job: dict) -> None:
    for slot in (st.session_state.get("batch_workers") or {}).values():
        state = (slot or {}).get("state")
        if state is not None:
            state.request_cancel()
    st.session_state.pop("batch_workers", None)
    for item in job.get("items") or []:
        item["status"] = "pending"
        item["error"] = ""
        item["filepath"] = ""
    job["phase"] = "check"
    job["index"] = 0
    job["results"] = []
    job["paused"] = False
    job["message"] = f"Restarting batch {job.get('batch_id', '')} from the first link."
    _store_batch(job)


def _store_batch(job: dict | None) -> None:
    if not job:
        _clear_batch()
        return
    st.session_state[_BATCH_JOB_KEY] = job
    save_queue(BATCH_QUEUE_FILE, job)


def _clear_batch() -> None:
    for slot in (st.session_state.get("batch_workers") or {}).values():
        state = (slot or {}).get("state")
        if state is not None:
            state.request_cancel()
    st.session_state.pop("batch_workers", None)
    st.session_state[_BATCH_JOB_KEY] = None
    clear_queue(BATCH_QUEUE_FILE)


def start_batch_from_urls(
    urls: list[str],
    batch_type: str,
    prefer_height: int,
    extras: dict,
    download_dir: str,
    settings: dict,
) -> None:
    """Public entry used by Profile and other tabs to start the batch plan."""
    _start_batch_job(urls, batch_type, prefer_height, extras, download_dir, settings)


def _start_batch_job(
    valid_urls: list[str],
    batch_type: str,
    prefer_height: int,
    extras: dict,
    download_dir: str,
    settings: dict,
) -> None:
    if not valid_urls:
        st.error("No video links to download. Playlist links belong on the Playlist tab.")
        return

    grouped = split_by_platform([normalize_media_url(url) for url in valid_urls])
    items = []
    for platform in ("youtube", "instagram"):
        for url in grouped[platform]:
            items.append(
                {
                    "url": url,
                    "platform": platform,
                    "title": _title_from_url(url),
                    "status": "pending",
                    "error": "",
                    "filepath": "",
                }
            )
    batch_id = new_batch_id("batch")
    output_dir = os.path.join(download_dir, batch_id)
    os.makedirs(os.path.join(output_dir, "youtube"), exist_ok=True)
    os.makedirs(os.path.join(output_dir, "instagram"), exist_ok=True)
    browser, cookiefile = auth_for_batch(settings, output_dir)
    yt_count = len(grouped["youtube"])
    ig_count = len(grouped["instagram"])
    cookie_note = " Cookies ready." if cookiefile else ""
    _store_batch(
        {
            "phase": "check",
            "index": 0,
            "urls": [item["url"] for item in items],
            "items": items,
            "batch_type": batch_type,
            "prefer_height": prefer_height,
            "results": [],
            "paused": False,
            "include_subtitles": extras["include_subtitles"],
            "selected_subtitle": extras["selected_subtitle"],
            "subtitle_format": extras["subtitle_format"],
            "include_thumbnail": extras["include_thumbnail"],
            "skip_existing": extras["skip_existing"],
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "batch_id": batch_id,
            "output_dir": output_dir,
            "auth_browser": browser or "",
            "auth_cookiefile": cookiefile or "",
            "message": (
                f"Cleaned {len(items)} link(s). YouTube {yt_count}, Instagram {ig_count}."
                f"{cookie_note} Checking each video next."
            ),
        }
    )
    st.rerun()


def _job_settings(job: dict, settings: dict) -> dict:
    merged = dict(settings)
    cookiefile = job.get("auth_cookiefile") or ""
    browser = job.get("auth_browser") or ""
    if cookiefile:
        merged["cookies_path"] = cookiefile
        merged["cookies_from_browser"] = ""
    elif browser:
        merged["cookies_from_browser"] = browser
    return merged


def _job_auth_key(job: dict, settings: dict) -> str:
    return get_auth_cache_key(_job_settings(job, settings))


def _title_from_url(url: str) -> str:
    from src.download.formats import clean_download_title
    from src.platforms.detect import media_id

    short = media_id(url)
    if short:
        return short
    return clean_download_title(url, url)


def _process_batch_job(download_dir: str, settings: dict) -> None:
    job = st.session_state.get(_BATCH_JOB_KEY)
    if not job:
        return
    # Do not steal the script run while Single tab is downloading.
    if st.session_state.get("single_download_lock") or st.session_state.get("single_active"):
        st.caption("Batch is paused while a Single download finishes.")
        return
    if job.get("phase") == "check":
        _check_next_item(job, download_dir, settings)
        return
    if job.get("phase") == "download":
        _run_platform_jobs(job, download_dir, settings)
        return
    st.warning("This saved batch is from an older run. Start a new batch.")
    _clear_batch()


def _check_next_item(job: dict, download_dir: str, settings: dict) -> None:
    items = job.get("items") or []
    index = int(job.get("index") or 0)
    total = len(items)
    st.info(job.get("message") or "Preparing the batch.")
    _render_plan_list(items)
    if index >= total:
        ready = [item for item in items if item["status"] == "ready"]
        platforms = sorted({item["platform"] for item in ready})
        if not ready:
            job["message"] = "Step 4 · Nothing left to download. Writing the report."
            job["results"] = _results_from_items(items)
            _store_batch(job)
            _finish_batch(job, download_dir)
            return
        names = " and ".join(platform.title() for platform in platforms)
        together = " together" if len(platforms) > 1 else ""
        job["phase"] = "download"
        job["message"] = (
            f"Step 4 · Folder check finished. {len(ready)} video(s) will download. "
            f"Step 5 · Starting {names}{together}."
        )
        _store_batch(job)
        st.rerun()
        return

    item = items[index]
    kind = "video" if job.get("batch_type") == "Video" else "audio"
    st.caption(f"Step 3 · Checking {index + 1} of {total} · {item['platform'].title()}")
    try:
        info = fetch_video_info(item["url"], _job_auth_key(job, settings))
        item["title"] = info.get("title") or item["title"]
        item["status"] = "ready"
        item["error"] = ""
    except Exception as exc:
        item["status"] = "unavailable"
        item["error"] = _short_reason(str(exc))
        job["message"] = f"Checking {index + 1} of {total}. {item['title']} needs attention. The rest continue."
    if item["status"] == "ready" and is_url_saved(download_dir, item["url"], item["title"], kind):
        item["status"] = "already_saved"
        item["error"] = "Already in the download folder"
        job["message"] = f"Checking {index + 1} of {total}. {item['title']} is already saved."
    elif item["status"] == "ready":
        job["message"] = f"Checking {index + 1} of {total}. {item['title']} is available."
    job["index"] = index + 1
    _store_batch(job)
    time.sleep(0.2)
    st.rerun()


def _run_platform_jobs(job: dict, download_dir: str, settings: dict) -> None:
    st.info(job.get("message") or "Downloading.")
    workers = st.session_state.setdefault("batch_workers", {})
    kind = "video" if job.get("batch_type") == "Video" else "audio"
    selected_format = (
        preferred_video_format(int(job.get("prefer_height") or 720))
        if kind == "video"
        else preferred_audio_format()
    )
    alive = False
    for platform in ("youtube", "instagram"):
        slot = workers.get(platform)
        if slot and slot.get("thread") is not None and not slot["thread"].is_alive():
            result = finish_background_download(slot, download_dir)
            _apply_download_result(job, slot.get("item_index"), result)
            workers[platform] = None
            slot = None
        if slot and slot.get("thread") is not None and slot["thread"].is_alive():
            alive = True
            snap = slot["state"].snapshot()
            pct = min(float(snap.get("percent") or 0), 100.0)
            label = "YouTube" if platform == "youtube" else "Instagram"
            st.progress(pct / 100.0, text=f"{label} · {pct:.0f}% · {slot.get('title') or ''}")
            continue
        nxt = _next_ready(job, platform)
        if nxt is None:
            continue
        item_index, item = nxt
        item["status"] = "downloading"
        platform_dir = os.path.join(job["output_dir"], platform)
        os.makedirs(platform_dir, exist_ok=True)
        position = sum(1 for entry in job["items"] if entry["platform"] == platform and entry["status"] != "pending")
        launched = execute_download(
            url=item["url"],
            platform=platform,
            title=item["title"],
            download_dir=platform_dir,
            settings=_job_settings(job, settings),
            download_kind=kind,
            is_video=kind == "video",
            selected_format=selected_format,
            selected_subtitle=job.get("selected_subtitle") if job.get("include_subtitles") else None,
            subtitle_format=job.get("subtitle_format") or "srt",
            include_subtitles=bool(job.get("include_subtitles")) and platform == "youtube",
            include_thumbnail=bool(job.get("include_thumbnail")),
            name_index=position,
            library_dir=download_dir,
            wait=False,
        )
        if launched.get("status") != "running":
            _apply_download_result(job, item_index, launched)
            continue
        launched["item_index"] = item_index
        launched["title"] = item["title"]
        workers[platform] = launched
        alive = True
        label = "YouTube" if platform == "youtube" else "Instagram"
        st.caption(f"Step 5 · {label} download started · {item['title']}")

    running = [name.title() for name, slot in workers.items() if slot and slot.get("thread") and slot["thread"].is_alive()]
    if running:
        job["message"] = "Step 5 · Downloading " + " and ".join(running) + "."
    _render_plan_list(job.get("items") or [])
    if alive:
        _store_batch(job)
        time.sleep(0.4)
        st.rerun()
        return

    ready_left = any(item["status"] == "ready" for item in job.get("items") or [])
    if ready_left:
        _store_batch(job)
        st.rerun()
        return

    job["results"] = _results_from_items(job.get("items") or [])
    job["message"] = "Step 6 · Downloads finished. Writing the report and statistics."
    _store_batch(job)
    _finish_batch(job, download_dir)


def _next_ready(job: dict, platform: str) -> tuple[int, dict] | None:
    for index, item in enumerate(job.get("items") or []):
        if item.get("platform") == platform and item.get("status") == "ready":
            return index, item
    return None


def _apply_download_result(job: dict, item_index: int | None, result: dict) -> None:
    if item_index is None:
        return
    item = job["items"][item_index]
    status = result.get("status")
    if status in ("finished", "ok") and result.get("filename"):
        item["status"] = "ok"
        item["filepath"] = result.get("filename") or ""
        item["error"] = ""
        job["message"] = f"Saved {item['title']}."
    elif status == "skipped":
        item["status"] = "already_saved"
        item["filepath"] = result.get("filename") or ""
        item["error"] = "Already in the download folder"
        job["message"] = f"Step 4 · {item['title']} is already in the download folder."
    elif status == "cancelled":
        item["status"] = "error"
        item["error"] = result.get("error") or "Cancelled"
        job["message"] = f"{item['title']} was cancelled."
    else:
        item["status"] = "error"
        item["error"] = result.get("error") or "Download failed"
        guide = classify_download_error(item["error"], result.get("download_kind") or "video")
        if pauses_queue(guide):
            job["message"] = pause_message(guide)
        else:
            job["message"] = f"{item['title']} failed. The other downloads continue. {item['error']}"


def _results_from_items(items: list[dict]) -> list[dict]:
    rows = []
    for item in items:
        status = item.get("status")
        if status == "ok":
            mapped = "ok"
        elif status in ("already_saved", "skipped"):
            mapped = "skipped"
        else:
            mapped = "error"
        rows.append(
            {
                "url": item.get("url") or "",
                "title": item.get("title") or "",
                "status": mapped,
                "error": item.get("error") or "",
                "filepath": item.get("filepath") or "",
                "platform": item.get("platform") or "",
            }
        )
    return rows


def _short_reason(error: str) -> str:
    text = " ".join((error or "").split())
    lower = text.lower()
    if "no video formats" in lower or "there is no video" in lower or "photo carousel" in lower:
        return "No video in this post. It may be photos only, or Instagram needs a logged-in browser."
    if "errno 22" in lower or "invalid argument" in lower:
        return "This quality could not be saved on Windows. Retry uses a simpler file automatically."
    if "already in" in lower:
        return "Already in the download folder."
    if "error:" in lower:
        text = text.split(":", 1)[-1].strip()
    if len(text) > 140:
        text = text[:140].rstrip() + "…"
    return text or "Could not use this link."


def _render_plan_list(items: list[dict]) -> None:
    if not items:
        return
    counts = {
        "Waiting": sum(1 for item in items if item.get("status") in ("pending", "ready")),
        "Downloading": sum(1 for item in items if item.get("status") == "downloading"),
        "Saved": sum(1 for item in items if item.get("status") in ("ok", "already_saved")),
        "Need attention": sum(1 for item in items if item.get("status") in ("unavailable", "error")),
    }
    stats = "".join(
        f'<div class="plan-stat"><b>{count}</b><span>{html.escape(label)}</span></div>'
        for label, count in counts.items()
    )
    _show_html(f'<div class="plan-board"><div class="plan-stats">{stats}</div></div>')

    problems = [item for item in items if item.get("status") in ("unavailable", "error")]
    if problems:
        rows = []
        for item in problems[:8]:
            title = html.escape(str(item.get("title") or item.get("url") or "Link"))
            reason = html.escape(_short_reason(item.get("error") or ""))
            rows.append(f"<li><strong>{title}</strong><span>{reason}</span></li>")
        extra = ""
        if len(problems) > 8:
            extra = (
                f"<li><strong>{html.escape(str(len(problems) - 8))} more</strong>"
                f"<span>Open the full list below.</span></li>"
            )
        _show_html(f'<ul class="plan-issues">{"".join(rows)}{extra}</ul>')

    with st.expander(f"All {len(items)} links", expanded=False):
        labels = {
            "pending": "Waiting",
            "ready": "Ready",
            "unavailable": "Not available",
            "already_saved": "Already saved",
            "downloading": "Downloading",
            "ok": "Saved",
            "error": "Failed",
        }
        for item in items:
            label = labels.get(item.get("status") or "", "Waiting")
            title = item.get("title") or item.get("url") or "Link"
            st.caption(f"{item.get('platform', '').title()} · {label} · {title}")


def _ensure_batch_folder(job: dict, download_dir: str) -> None:
    if not job.get("batch_id"):
        job["batch_id"] = new_batch_id("batch")
    folder = job.get("output_dir") or os.path.join(download_dir, job["batch_id"])
    os.makedirs(folder, exist_ok=True)
    job["output_dir"] = folder


def _finish_batch(job: dict, download_dir: str) -> None:
    _ensure_batch_folder(job, download_dir)
    results = job.get("results") or []
    batch_id = job["batch_id"]
    report_path = write_batch_report(
        results,
        {
            "kind": "batch",
            "title": f"Batch {batch_id}",
            "detail": _statistics_line(results, job),
        },
        dest_dir=job["output_dir"],
        report_name=batch_id,
    )
    save_queue(BATCH_REPORT_FILE, {"results": results, "html": report_path})
    st.session_state["last_batch_report"] = report_path
    _render_batch_summary(results, download_dir)
    st.success(f"Step 7 · Report saved: `{report_path}`")
    st.info(_statistics_line(results, job))
    _clear_batch()


def _statistics_line(results: list[dict], job: dict) -> str:
    saved = sum(1 for item in results if item.get("status") == "ok")
    skipped = sum(1 for item in results if item.get("status") == "skipped")
    failed = sum(1 for item in results if item.get("status") == "error")
    youtube = sum(1 for item in results if item.get("platform") == "youtube")
    instagram = sum(1 for item in results if item.get("platform") == "instagram")
    return (
        f"Batch {job.get('batch_id', '')} · {len(results)} links · "
        f"YouTube {youtube} · Instagram {instagram} · "
        f"saved {saved} · already in folder {skipped} · failed {failed}"
    )


def _render_batch_summary(results: list[dict], download_dir: str) -> None:
    if not results:
        return

    ok = sum(1 for r in results if r["status"] in ("ok", "skipped"))
    failed = sum(1 for r in results if r["status"] == "error")

    st.markdown("---")
    st.markdown(f"**Batch complete** — {ok} succeeded/skipped, {failed} failed")

    with st.container(border=True):
        for i, item in enumerate(results):
            if item["status"] in ("ok", "skipped") and item.get("filepath"):
                st.caption(f"✓ {item.get('title', item['url'])}")
                offer_browser_download(item["filepath"], download_dir, key=f"batch-result-{i}")
            elif item["status"] == "error":
                st.caption(f"✗ {item.get('title', item['url'])} — {item.get('error', 'failed')}")


def _pause_seconds(settings: dict) -> float:
    try:
        return float(settings.get("batch_pause_sec", BATCH_ITEM_PAUSE_SEC))
    except (TypeError, ValueError):
        return BATCH_ITEM_PAUSE_SEC


def _show_quality_hint(url: str, prefer_height: int, settings: dict) -> None:
    try:
        data = fetch_formats(url, get_auth_cache_key(settings))
        heights = [item.get("height") or 0 for item in data[5]]
        note = quality_note(prefer_height, heights)
    except Exception as exc:
        st.caption(f"Could not check quality for the first link: {exc}")
        return
    if not note:
        return
    if "not available" in note:
        st.warning(note)
    else:
        st.caption(note)


def _show_saved_report(path: str, key_prefix: str) -> None:
    report = load_queue(path)
    results = (report or {}).get("results") or []
    if not results:
        return
    failed = [item.get("url") for item in results if item.get("status") == "error" and item.get("url")]
    html_path = (report or {}).get("html") or st.session_state.get("last_batch_report")
    with st.expander(f"Last run · {len(results)} items, {len(failed)} failed", expanded=False):
        if html_path:
            st.caption(f"HTML report: `{html_path}`")
        for item in results:
            mark = "✓" if item.get("status") in ("ok", "skipped") else "✗"
            st.caption(f"{mark} {item.get('title') or item.get('url')}")
        if failed and st.button("Retry failed links", key=f"{key_prefix}_retry_failed"):
            st.session_state["batch_urls_pending"] = failed
            clear_queue(path)
            st.rerun()
