import html

import streamlit as st

from src.download.formats import format_duration


def render_platform_badge(platform: str) -> None:
    labels = {"youtube": "YouTube", "instagram": "Instagram"}
    label = labels.get(platform)
    if label:
        st.markdown(
            f'<span class="stat-pill">{html.escape(label)}</span>',
            unsafe_allow_html=True,
        )


def render_stat_pills(
    video_formats,
    audio_formats,
    subtitle_options,
    platform: str = "youtube",
) -> None:
    pills = []
    if video_formats:
        heights = [f["height"] for f in video_formats if f.get("height")]
        if heights:
            pills.append(f"{len(video_formats)} qualities, up to {max(heights)}p")
        else:
            pills.append(f"{len(video_formats)} video options")
    if audio_formats:
        pills.append(f"{len(audio_formats)} audio tracks")
    if subtitle_options and platform == "youtube":
        pills.append(f"{len(subtitle_options)} subtitles")
    if not pills:
        return
    markup = '<div class="stat-row">' + "".join(
        f'<span class="stat-pill">{html.escape(p)}</span>' for p in pills
    ) + "</div>"
    st.markdown(markup, unsafe_allow_html=True)


def _render_thumbnail(thumbnail: str) -> None:
    """Show thumbnail without st.image so a broken numpy install cannot crash the app."""
    if not thumbnail:
        return
    if thumbnail.startswith(("http://", "https://")):
        safe_url = html.escape(thumbnail, quote=True)
        st.markdown(
            f'<img src="{safe_url}" alt="Video thumbnail" '
            'style="width:100%;border-radius:8px;display:block;" />',
            unsafe_allow_html=True,
        )
        return
    try:
        st.image(thumbnail, width="stretch")
    except ImportError:
        st.caption("Thumbnail preview unavailable (numpy issue). Video download still works.")


def render_video_card(
    title: str,
    thumbnail: str,
    uploader: str,
    duration: int,
    platform: str = "youtube",
) -> None:
    uploader_label = "Account" if platform == "instagram" else "Channel"
    thumb_col, meta_col = st.columns([1, 1.6], gap="medium")
    with thumb_col:
        with st.container(border=True):
            _render_thumbnail(thumbnail)
    with meta_col:
        st.markdown("##### " + html.escape(title))
        m1, m2 = st.columns(2)
        with m1:
            safe_uploader = uploader[:28] + ("…" if len(uploader) > 28 else "")
            st.metric(uploader_label, safe_uploader)
        with m2:
            st.metric("Duration", format_duration(duration))


def render_selection_summary(text: str) -> None:
    # Callers may pass simple HTML tags like <b>; escape user-derived parts first.
    st.markdown(f'<div class="selection-box">{text}</div>', unsafe_allow_html=True)


def selection_summary_html(**fields: str) -> str:
    """Build a selection summary with escaped field values."""
    parts = [f"<b>{html.escape(k)}:</b> {html.escape(v)}" for k, v in fields.items()]
    return " · ".join(parts)


def render_empty_state() -> None:
    st.markdown(
        """
        <div class="empty-state">
            <h2>Paste a YouTube or Instagram URL</h2>
            <p>YouTube supports video, audio, and subtitles. Instagram supports public Reels, posts, and IGTV.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_label(text: str) -> None:
    st.markdown(
        f'<p class="section-label">{html.escape(text)}</p>',
        unsafe_allow_html=True,
    )
