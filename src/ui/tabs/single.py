import os

import streamlit as st

from src.download.fetch import clear_fetch_cache, fetch_formats
from src.download.formats import format_size, is_progressive_format, pick_default_video_format
from src.platforms.detect import detect_platform, is_youtube_playlist_or_channel, trim_url_state
from src.ui.url_file import render_url_file_uploader, take_uploaded_urls
from src.ui.execute import execute_download, show_download_result
from src.logutil import get_logger
from src.ui.components import (
    render_empty_state,
    render_platform_badge,
    render_selection_summary,
    render_stat_pills,
    render_video_card,
    section_label,
    selection_summary_html,
)
from src.utils.cookies import get_auth_cache_key

log = get_logger("single")
_SINGLE_DL_RESULT = "single_dl_result"


def _on_url_changed() -> None:
    st.session_state.fetch_pending = True


def render_single_tab(download_dir: str, settings: dict) -> None:
    st.session_state.pop("single_dl_request", None)
    st.session_state.pop("single_active", None)
    st.session_state["single_download_lock"] = False

    section_label("Step 1 · Video URL")
    st.caption("Paste a URL or load a .txt or .csv file. Extra text around the link is removed automatically.")

    uploaded = render_url_file_uploader("Load a text or CSV file", "single_url_file")
    found = take_uploaded_urls(st.session_state, uploaded, "single_url_file_token")
    if found is not None:
        videos = [url for url in found if not is_youtube_playlist_or_channel(url)]
        playlists = [url for url in found if is_youtube_playlist_or_channel(url)]
        if videos:
            st.session_state["single_url"] = videos[0]
            st.session_state.fetch_pending = True
            if len(videos) > 1:
                st.session_state["single_extra_urls"] = videos[1:]
                st.info(f"Using the first video link. {len(videos) - 1} more link(s) can go to Batch queue.")
        elif playlists:
            st.info("That file has a playlist or channel link. Use the Playlist tab for it.")
        else:
            st.warning(f"No YouTube or Instagram links found in `{uploaded.name}`.")

    extra_urls = st.session_state.get("single_extra_urls") or []
    if extra_urls and st.button(f"Send {len(extra_urls)} other link(s) to Batch", key="single_send_batch"):
        from src.platforms.detect import merge_url_blocks

        st.session_state["batch_urls"] = merge_url_blocks(
            st.session_state.get("batch_urls") or "",
            extra_urls,
        )
        st.session_state["single_extra_urls"] = []
        st.success("Added those links to Batch queue. Open that tab.")

    trim_url_state(st.session_state, "single_url")

    url_col, refresh_col = st.columns([5, 1])
    with url_col:
        st.text_input(
            "Video URL",
            placeholder="https://youtube.com/watch?v=... or playlist URL in Playlist tab",
            label_visibility="collapsed",
            key="single_url",
            on_change=_on_url_changed,
        )
    with refresh_col:
        if st.button("Refresh", help="Refresh video info", width="stretch", key="single_refresh"):
            clear_fetch_cache()
            st.session_state.fetch_pending = True
            st.rerun()

    url = (st.session_state.get("single_url") or "").strip()

    if not url:
        render_empty_state()
        return

    if is_youtube_playlist_or_channel(url):
        st.info("This looks like a **playlist or channel** link. Use the **Playlist** tab for batch downloads.")
        return

    platform = detect_platform(url)
    if not platform:
        st.error("Unsupported URL. Paste a **YouTube** or **Instagram** link.")
        return

    auth_key = get_auth_cache_key(settings)
    loaded_url = st.session_state.get("loaded_url", "")
    fetch_pending = st.session_state.get("fetch_pending", False)

    if fetch_pending or loaded_url != url:
        with st.spinner("Checking the link and loading available formats…"):
            try:
                data = fetch_formats(url, auth_key)
                st.session_state.media_cache = {
                    "url": url,
                    "platform": data[0],
                    "title": data[1],
                    "thumbnail": data[2],
                    "duration": data[3],
                    "uploader": data[4],
                    "video_formats": data[5],
                    "audio_formats": data[6],
                    "subtitle_options": data[7],
                }
                st.session_state.loaded_url = url
                st.session_state.fetch_pending = False
                log.info(
                    "Fetched formats url=%s platform=%s videos=%s audios=%s",
                    url,
                    data[0],
                    len(data[5] or []),
                    len(data[6] or []),
                )
            except Exception as e:
                log.exception("Fetch failed for %s", url)
                st.error(f"Could not fetch video info: `{e}`")
                if platform == "instagram":
                    st.info(
                        "Instagram tip: public Reels, posts, and IGTV work best. "
                        "Private/login-only content is not supported."
                    )
                st.session_state.fetch_pending = False
                return

    media = st.session_state.get("media_cache")
    if not media or media.get("url") != url:
        st.warning("Video data is not loaded yet. Press Refresh.")
        return

    platform = media["platform"]
    title = media["title"]
    thumbnail = media["thumbnail"]
    duration = media["duration"]
    uploader = media["uploader"]
    video_formats = media["video_formats"]
    audio_formats = media["audio_formats"]
    subtitle_options = media["subtitle_options"]

    render_platform_badge(platform)
    render_stat_pills(video_formats, audio_formats, subtitle_options, platform)
    render_video_card(title, thumbnail, uploader, duration, platform)

    section_label("Step 2 · Download type")

    type_options = ["Video", "Audio", "Thumbnail"] if platform == "instagram" else [
        "Video", "Audio", "Subtitles", "Thumbnail"
    ]
    download_type = st.segmented_control(
        "Download type",
        options=type_options,
        default="Video",
        label_visibility="collapsed",
        key="single_download_type",
    ) if hasattr(st, "segmented_control") else st.radio(
        "Download type",
        type_options,
        horizontal=True,
        label_visibility="collapsed",
        key="single_download_type_radio",
    )

    is_subtitle = download_type == "Subtitles"
    is_video = download_type == "Video"
    is_thumbnail = download_type == "Thumbnail"

    selected_format: dict = {}
    selected_subtitle: dict | None = None
    subtitle_format = "srt"
    include_subtitles = False
    download_kind = (
        "thumbnail" if is_thumbnail
        else "subtitle" if is_subtitle
        else "video" if is_video
        else "audio"
    )

    section_label("Step 3 · Quality & options")

    if is_thumbnail:
        render_selection_summary(
            selection_summary_html(Thumbnail=f"best available image for {title}")
        )
    elif is_subtitle:
        if not subtitle_options:
            st.warning("No subtitles are available for this video.")
            return

        sub_col1, sub_col2 = st.columns(2)
        with sub_col1:
            subtitle_labels = [opt["label"] for opt in subtitle_options]
            subtitle_idx = st.selectbox(
                "Language",
                range(len(subtitle_labels)),
                format_func=lambda i: subtitle_labels[i],
            )
            selected_subtitle = subtitle_options[subtitle_idx]
        with sub_col2:
            subtitle_format = st.selectbox("Format", ["srt", "vtt"])
        render_selection_summary(
            selection_summary_html(
                Subtitle=selected_subtitle["label"],
                Format=subtitle_format.upper(),
            )
        )
    elif is_video:
        if not video_formats:
            st.warning("No video formats found for this URL.")
            return

        preferred = pick_default_video_format(video_formats, 720) or video_formats[0]
        default_q = video_formats.index(preferred)
        if not is_progressive_format(preferred) and preferred.get("height"):
            st.caption(
                f"Only stream qualities are listed. Default is {preferred['height']}p; "
                "if that fails the app switches to a simpler file automatically."
            )
        elif preferred.get("height") and preferred["height"] != 720:
            st.caption(
                f"720p progressive is not available. Defaulting to {preferred['height']}p "
                "so the download can finish."
            )

        quality_labels = [
            f"{f['label']}  ·  {format_size(f['filesize'])}" for f in video_formats
        ]
        selected_idx = st.selectbox(
            "Video quality",
            range(len(quality_labels)),
            index=default_q,
            format_func=lambda i: quality_labels[i],
        )
        selected_format = video_formats[selected_idx]
        render_selection_summary(
            selection_summary_html(
                Video=selected_format["label"],
                Size=f"~{format_size(selected_format['filesize'])}",
                Container="MP4",
            )
        )

        if subtitle_options and platform == "youtube":
            include_subtitles = st.toggle("Include subtitles", value=False)
            if include_subtitles:
                s1, s2 = st.columns(2)
                with s1:
                    subtitle_labels = [opt["label"] for opt in subtitle_options]
                    subtitle_idx = st.selectbox(
                        "Subtitle language",
                        range(len(subtitle_labels)),
                        format_func=lambda i: subtitle_labels[i],
                        key="single_video_subtitle_lang",
                    )
                    selected_subtitle = subtitle_options[subtitle_idx]
                with s2:
                    subtitle_format = st.selectbox(
                        "Subtitle format", ["srt", "vtt"], key="single_video_subtitle_fmt"
                    )
    else:
        if not audio_formats:
            st.warning("No audio formats found for this URL.")
            return

        quality_labels = [
            f"{f['label']}  ·  {format_size(f['filesize'])}" for f in audio_formats
        ]
        selected_idx = st.selectbox(
            "Audio quality",
            range(len(quality_labels)),
            format_func=lambda i: quality_labels[i],
        )
        selected_format = audio_formats[selected_idx]
        render_selection_summary(
            selection_summary_html(
                Audio=selected_format["label"],
                Output=f"MP3 · ~{format_size(selected_format['filesize'])}",
            )
        )

    section_label("Step 4 · Download")
    from src.download.paths import find_saved_download

    already_saved = find_saved_download(download_dir, url, title, download_kind)
    if already_saved:
        st.info(
            f"Already in the download folder: `{os.path.basename(already_saved)}`. "
            "Start download will reuse that file."
        )

    if is_thumbnail:
        selected_format = {"format_id": "0"}

    if st.button("Start download", type="primary", width="stretch", key="single_start"):
        st.session_state.pop(_SINGLE_DL_RESULT, None)
        st.info(f"Downloading to `{download_dir}`…")
        log.info(
            "Start download url=%s kind=%s format=%s dir=%s",
            url,
            download_kind,
            (selected_format or {}).get("format_id"),
            download_dir,
        )
        try:
            result = execute_download(
                url=url,
                platform=platform,
                title=title,
                download_dir=download_dir,
                settings=settings,
                download_kind=download_kind,
                is_video=is_video,
                selected_format=selected_format,
                selected_subtitle=selected_subtitle,
                subtitle_format=subtitle_format,
                include_subtitles=include_subtitles,
                wait=True,
            )
        except Exception as exc:
            log.exception("Single download crashed for %s", url)
            result = {
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
                "download_kind": download_kind,
                "url": url,
                "title": title,
            }
            from src.ui.download_ui import save_download_failure_log

            result["error_log"] = save_download_failure_log(
                url,
                result["error"],
                extra=f"title: {title}\ndownload_kind: {download_kind}\n",
            )
        st.session_state[_SINGLE_DL_RESULT] = result
        log.info(
            "Single download status=%s file=%s error=%s",
            result.get("status"),
            result.get("filename"),
            (result.get("error") or "")[:200],
        )

    result = st.session_state.get(_SINGLE_DL_RESULT)
    if result:
        show_download_result(result, download_dir, key_prefix="single")
        if st.button("Clear download status", key="single_clear_status"):
            st.session_state.pop(_SINGLE_DL_RESULT, None)
            st.rerun()

    st.caption(f"Files save to `{download_dir}`")
