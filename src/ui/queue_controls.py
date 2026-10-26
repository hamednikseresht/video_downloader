"""Shared options for batch and playlist downloads."""

import streamlit as st

from src.download.batch_plan import SUBTITLE_LANGS, subtitle_choice
from src.download.errors import format_guide_markdown


def render_extra_download_options(key_prefix: str) -> dict:
    include_subtitles = st.checkbox(
        "Include subtitles",
        value=False,
        key=f"{key_prefix}_subs",
        help="YouTube only. Saved next to the video or audio file.",
    )
    selected_subtitle = None
    subtitle_format = "srt"
    if include_subtitles:
        lang_col, source_col, fmt_col = st.columns(3)
        labels = [name for _, name in SUBTITLE_LANGS]
        with lang_col:
            lang_idx = st.selectbox(
                "Subtitle language",
                range(len(labels)),
                format_func=lambda i: labels[i],
                key=f"{key_prefix}_sub_lang",
            )
        with source_col:
            source = st.selectbox(
                "Subtitle source",
                ["auto", "manual"],
                format_func=lambda value: "Auto-generated" if value == "auto" else "Manual",
                key=f"{key_prefix}_sub_source",
            )
        with fmt_col:
            subtitle_format = st.selectbox(
                "Subtitle format",
                ["srt", "vtt"],
                key=f"{key_prefix}_sub_fmt",
            )
        selected_subtitle = subtitle_choice(SUBTITLE_LANGS[lang_idx][0], source)

    include_thumbnail = st.checkbox(
        "Include thumbnail",
        value=False,
        key=f"{key_prefix}_thumb",
    )
    st.caption("Files already in the download folder are skipped.")
    return {
        "include_subtitles": include_subtitles,
        "selected_subtitle": selected_subtitle,
        "subtitle_format": subtitle_format,
        "include_thumbnail": include_thumbnail,
        "skip_existing": True,
    }


def render_queue_pause(job: dict, key_prefix: str) -> str | None:
    st.error(job.get("pause_message") or "Queue paused.")
    st.caption(job.get("pause_url") or "")
    resume_col, skip_col, stop_col = st.columns(3)
    with resume_col:
        if st.button("Resume", type="primary", key=f"{key_prefix}_resume", width="stretch"):
            return "resume"
    with skip_col:
        if st.button("Skip this item", key=f"{key_prefix}_skip_item", width="stretch"):
            return "skip"
    with stop_col:
        if st.button("Stop", key=f"{key_prefix}_pause_stop", width="stretch"):
            return "stop"
    return None


def pause_message(guide) -> str:
    return format_guide_markdown(guide)
