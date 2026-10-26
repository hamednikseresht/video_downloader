import os
from datetime import datetime

import streamlit as st

from src.download.formats import format_size
from src.history import (
    clear_history_filepath,
    delete_history_file,
    history_to_csv,
    history_to_txt,
    load_history,
    resolve_history_filepath,
)
from src.ui.execute import execute_download, show_download_result
from src.ui.components import section_label
from src.ui.download_ui import offer_browser_download


def _format_timestamp(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return ts


def render_history_tab(download_dir: str, settings: dict) -> None:
    section_label("Download history")
    st.caption("Re-download or remove past downloads.")

    entries = load_history()
    if not entries:
        st.info("No downloads recorded yet. Completed downloads appear here.")
        return

    query = st.text_input("Search title or URL", key="history_search")
    platform_filter = st.selectbox("Platform", ["All", "youtube", "instagram"], key="history_platform")
    kind_filter = st.selectbox(
        "Kind",
        ["All", "video", "audio", "subtitle", "thumbnail"],
        key="history_kind",
    )
    needle = query.strip().lower()
    visible = []
    for entry in entries:
        if platform_filter != "All" and entry.get("platform") != platform_filter:
            continue
        if kind_filter != "All" and entry.get("kind") != kind_filter:
            continue
        blob = f"{entry.get('title', '')} {entry.get('url', '')}".lower()
        if needle and needle not in blob:
            continue
        visible.append(entry)
    entries = visible
    st.caption(f"{len(entries)} shown")
    if entries and st.button("Send shown links to Batch", key="history_to_batch"):
        st.session_state["batch_urls_pending"] = [entry.get("url") for entry in entries if entry.get("url")]
        st.success("Open the Batch queue tab. Those links will be added.")
        st.rerun()
    if not entries:
        st.info("No history rows match this filter.")
        return
    csv_col, txt_col, _ = st.columns([1, 1, 2])
    with csv_col:
        st.download_button(
            "Download CSV",
            data=history_to_csv(entries).encode("utf-8-sig"),
            file_name="download_history.csv",
            mime="text/csv",
            width="stretch",
            key="history_csv",
        )
    with txt_col:
        st.download_button(
            "Download text",
            data=history_to_txt(entries).encode("utf-8"),
            file_name="download_history.txt",
            mime="text/plain",
            width="stretch",
            key="history_txt",
        )

    for entry in entries:
        stored = entry.get("filepath", "")
        filepath = resolve_history_filepath(stored, download_dir) if stored else ""
        exists = bool(filepath and os.path.isfile(filepath))
        size = entry.get("size") or 0
        if exists:
            size = os.path.getsize(filepath)

        kind = entry.get("kind", "video")
        platform = entry.get("platform", "youtube")
        title = entry.get("title", "Unknown")
        url = entry.get("url", "")
        ts = _format_timestamp(entry.get("timestamp", ""))

        with st.container(border=True):
            st.text(title)
            st.caption(
                f"{kind.upper()} · {platform} · {format_size(size)} · {ts}"
            )
            if url:
                st.caption(url)

            btn1, btn2, btn3 = st.columns(3)
            with btn1:
                if exists:
                    offer_browser_download(filepath, download_dir, key=f"hist-dl-{entry['id']}")
                else:
                    st.caption("File missing")
            with btn2:
                if st.button("Re-download", key=f"hist-redl-{entry['id']}", width="stretch"):
                    _redownload_entry(entry, download_dir, settings)
            with btn3:
                if st.button("Remove", key=f"hist-del-{entry['id']}", width="stretch"):
                    delete_history_file(entry, delete_file=False, download_dir=download_dir)
                    st.rerun()

            del_col1, del_col2 = st.columns(2)
            with del_col1:
                if st.button(
                    "Delete file only",
                    key=f"hist-delfile-{entry['id']}",
                    width="stretch",
                    disabled=not exists,
                ):
                    if exists:
                        try:
                            from src.security import assert_under_download_dir

                            safe = assert_under_download_dir(filepath, download_dir)
                            os.remove(safe)
                            clear_history_filepath(entry["id"])
                            st.toast("File deleted.")
                            st.rerun()
                        except (OSError, ValueError) as e:
                            st.error(str(e))
            with del_col2:
                if st.button(
                    "Delete file + history",
                    key=f"hist-delfull-{entry['id']}",
                    width="stretch",
                ):
                    delete_history_file(entry, delete_file=True, download_dir=download_dir)
                    st.rerun()


def _redownload_entry(entry: dict, download_dir: str, settings: dict) -> None:
    url = entry.get("url", "")
    if not url:
        st.error("No URL stored for this entry.")
        return

    from src.download.fetch import fetch_formats
    from src.download.formats import pick_default_audio_format, pick_default_video_format
    from src.utils.cookies import get_auth_cache_key

    auth_key = get_auth_cache_key(settings)
    kind = entry.get("kind", "video")

    try:
        (
            platform,
            title,
            _t,
            _d,
            _u,
            video_formats,
            audio_formats,
            _subs,
        ) = fetch_formats(url, auth_key)
    except Exception as e:
        st.error(f"Could not fetch: `{e}`")
        return

    if kind == "thumbnail":
        download_kind = "thumbnail"
        is_video = False
        selected_format = {"format_id": "0"}
    elif kind == "audio":
        download_kind = "audio"
        is_video = False
        selected_format = pick_default_audio_format(audio_formats) or {}
    elif kind == "subtitle":
        st.warning("Re-download subtitles from the Single tab (language selection required).")
        return
    else:
        download_kind = "video"
        is_video = True
        selected_format = pick_default_video_format(video_formats) or {}

    if not selected_format and kind != "thumbnail":
        st.error("No formats available.")
        return

    result = execute_download(
        url=url,
        platform=platform,
        title=title,
        download_dir=download_dir,
        settings=settings,
        download_kind=download_kind,
        is_video=is_video,
        selected_format=selected_format,
        record_history=True,
    )
    show_download_result(result, download_dir, key_prefix=f"redl-{entry['id']}")
