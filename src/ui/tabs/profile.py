"""Download the newest videos from a YouTube or Instagram profile."""

from __future__ import annotations

import streamlit as st

from src.download.fetch import clear_fetch_cache, fetch_profile_entries
from src.download.formats import format_duration
from src.platforms.detect import (
    detect_platform,
    is_instagram_profile,
    is_profile_url,
    is_youtube_profile,
    profile_listing_url,
    trim_url_state,
)
from src.ui.components import section_label
from src.ui.queue import start_batch_from_urls
from src.ui.queue_controls import render_extra_download_options
from src.utils.cookies import get_auth_cache_key


def render_profile_tab(download_dir: str, settings: dict) -> None:
    section_label("Profile · latest videos")
    st.caption(
        "Paste a YouTube channel or Instagram profile. "
        "Choose how many of the newest posts to download."
    )

    trim_url_state(st.session_state, "profile_url")
    url = st.text_input(
        "Profile URL",
        placeholder="https://www.youtube.com/@channel  or  https://www.instagram.com/username/",
        key="profile_url",
        label_visibility="collapsed",
    ).strip()

    count = st.number_input(
        "How many latest videos",
        min_value=1,
        max_value=50,
        value=10,
        step=1,
        key="profile_count",
    )

    batch_type = st.radio(
        "Download type",
        ["Video", "Audio"],
        horizontal=True,
        key="profile_type",
    )
    prefer_height = st.selectbox(
        "Video quality (when available)",
        [1080, 720, 480, 360],
        index=1,
        key="profile_height",
    )
    extras = render_extra_download_options("profile")

    if not url:
        st.info("Paste a YouTube channel or Instagram profile link above.")
        return

    platform = detect_platform(url)
    if not is_profile_url(url):
        if platform == "youtube":
            st.warning("This looks like a single video or playlist. Use Single, Playlist, or Batch.")
        elif platform == "instagram":
            st.warning("This looks like a single post or reel. Use Single or Batch.")
        else:
            st.error("Paste a YouTube channel (`/@name`) or Instagram profile (`/username`).")
        return

    label = "Instagram profile" if is_instagram_profile(url) else "YouTube channel"
    st.caption(f"{label} · listing `{profile_listing_url(url)}`")

    load_col, clear_col = st.columns([2, 1])
    with load_col:
        load = st.button("Load latest videos", type="primary", width="stretch", key="profile_load")
    with clear_col:
        if st.button("Clear", width="stretch", key="profile_clear"):
            clear_fetch_cache()
            st.session_state.pop("profile_data", None)
            st.rerun()

    if load:
        with st.spinner(f"Loading the latest {int(count)} posts…"):
            try:
                plat, title, entries = fetch_profile_entries(
                    url, int(count), get_auth_cache_key(settings)
                )
                st.session_state.profile_data = {
                    "url": url,
                    "platform": plat,
                    "title": title,
                    "entries": entries,
                    "limit": int(count),
                }
            except Exception as exc:
                st.error(str(exc))
                return

    data = st.session_state.get("profile_data")
    if not data or data.get("url") != url:
        return

    entries = data.get("entries") or []
    st.markdown(f"**{data.get('title') or 'Profile'}** · {len(entries)} of {data.get('limit', count)} loaded")
    if not entries:
        st.warning("No videos found on this profile. Instagram often needs browser cookies.")
        return

    with st.container(border=True):
        for entry in entries[:20]:
            duration = format_duration(entry.get("duration") or 0)
            extra = f" · {duration}" if entry.get("duration") else ""
            st.caption(f"{entry['index']}. {entry.get('title') or entry.get('url')}{extra}")
        if len(entries) > 20:
            st.caption(f"…and {len(entries) - 20} more")

    if st.button("Download these videos", type="primary", width="stretch", key="profile_download"):
        urls = [entry["url"] for entry in entries if entry.get("url")]
        start_batch_from_urls(
            urls,
            batch_type,
            int(prefer_height),
            extras,
            download_dir,
            settings,
        )
        st.session_state["main_tabs"] = "Batch queue"
        st.success(f"Sent {len(urls)} link(s) to the batch plan. Open the Batch queue tab.")
        st.rerun()
