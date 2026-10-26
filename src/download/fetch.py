import yt_dlp
import streamlit as st

from src.constants import FETCH_CACHE_VERSION
from src.download.formats import parse_formats_for_platform, parse_subtitles
from src.download.ydl import get_base_ydl_opts
from src.platforms.detect import detect_platform
from src.utils.cookies import (
    auth_from_cache_key,
    format_cookie_read_help,
    format_youtube_auth_help,
    is_cookie_read_error,
    is_youtube_bot_error,
)


@st.cache_data(show_spinner=False, ttl=600)
def fetch_video_info(
    url: str,
    auth_key: str = "",
    _cache_version: int = FETCH_CACHE_VERSION,
) -> dict:
    platform = detect_platform(url)
    if not platform:
        raise ValueError("Unsupported URL. Paste a YouTube or Instagram link.")
    browser, cookiefile = auth_from_cache_key(auth_key)
    ydl_opts = get_base_ydl_opts(cookiefile=cookiefile, cookies_from_browser=browser)
    if platform == "instagram":
        ydl_opts["ignore_no_formats_error"] = True
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    if platform == "instagram" and (info or {}).get("_type") == "playlist":
        videos = [
            entry
            for entry in (info.get("entries") or [])
            if entry and (entry.get("formats") or entry.get("url"))
        ]
        if not videos:
            raise ValueError(
                "This Instagram post is a photo carousel with no video. "
                "Open a reel or a slide that is a video."
            )
        first = videos[0]
        first = dict(first)
        first["title"] = info.get("title") or first.get("title") or "Instagram post"
        first["uploader"] = info.get("uploader") or first.get("uploader") or ""
        first["_playlist_videos"] = len(videos)
        return first
    if platform == "instagram" and info and not (info.get("formats") or []):
        raise ValueError(
            "Instagram did not return a video for this link. "
            "Photo posts have no video."
        )
    return info


@st.cache_data(show_spinner=False, ttl=600)
def fetch_formats(url: str, auth_key: str = "", _cache_version: int = FETCH_CACHE_VERSION):
    platform = detect_platform(url)
    if not platform:
        raise ValueError("Unsupported URL. Paste a YouTube or Instagram link.")

    try:
        info = fetch_video_info(url, auth_key, _cache_version)
    except Exception as e:
        msg = str(e)
        if is_cookie_read_error(msg):
            raise ValueError(format_cookie_read_help(msg)) from e
        if platform == "youtube" and is_youtube_bot_error(msg):
            raise ValueError(format_youtube_auth_help(msg)) from e
        if platform == "instagram" and "no video formats" in msg.lower():
            raise ValueError(
                "Instagram did not return a video for this link. "
                "Log into Instagram in your browser, then set Settings → YouTube cookies "
                "to that browser, and try again. Photo posts have no video."
            ) from e
        raise

    video_formats, audio_formats = parse_formats_for_platform(
        info.get("formats", []),
        platform,
    )
    subtitle_options = []
    if platform == "youtube":
        subtitle_options = parse_subtitles(
            info.get("subtitles") or {},
            info.get("automatic_captions") or {},
        )
    return (
        platform,
        info.get("title", "Unknown Title"),
        info.get("thumbnail", ""),
        info.get("duration", 0),
        info.get("uploader", "Unknown"),
        video_formats,
        audio_formats,
        subtitle_options,
    )


@st.cache_data(show_spinner=False, ttl=600)
def fetch_playlist_entries(
    url: str,
    auth_key: str = "",
    _cache_version: int = FETCH_CACHE_VERSION,
) -> tuple[str, list[dict]]:
    browser, cookiefile = auth_from_cache_key(auth_key)
    ydl_opts = {
        **get_base_ydl_opts(cookiefile=cookiefile, cookies_from_browser=browser),
        "extract_flat": "in_playlist",
        "lazy_playlist": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        msg = str(e)
        if is_cookie_read_error(msg):
            raise ValueError(format_cookie_read_help(msg)) from e
        if is_youtube_bot_error(msg):
            raise ValueError(format_youtube_auth_help(msg)) from e
        raise

    playlist_title = info.get("title") or "Playlist"
    entries: list[dict] = []

    for index, entry in enumerate(info.get("entries") or [], start=1):
        if not entry:
            continue
        entry_url = entry.get("url") or entry.get("webpage_url")
        if not entry_url and entry.get("id"):
            entry_url = f"https://www.youtube.com/watch?v={entry['id']}"
        if not entry_url:
            continue
        entries.append(
            {
                "index": index,
                "id": entry.get("id") or "",
                "title": entry.get("title") or f"Video {index}",
                "url": entry_url,
                "duration": entry.get("duration") or 0,
            }
        )

    return playlist_title, entries


@st.cache_data(show_spinner=False, ttl=600)
def fetch_profile_entries(
    url: str,
    limit: int = 10,
    auth_key: str = "",
    _cache_version: int = FETCH_CACHE_VERSION,
) -> tuple[str, str, list[dict]]:
    """Return (platform, profile title, newest entries up to limit)."""
    from src.platforms.detect import (
        detect_platform,
        is_profile_url,
        profile_listing_url,
    )

    if not is_profile_url(url) and detect_platform(url) not in ("youtube", "instagram"):
        raise ValueError("Paste a YouTube channel or Instagram profile link.")

    listing = profile_listing_url(url)
    platform = detect_platform(listing) or detect_platform(url) or "youtube"
    count = max(1, min(int(limit or 10), 100))
    browser, cookiefile = auth_from_cache_key(auth_key)
    ydl_opts = {
        **get_base_ydl_opts(cookiefile=cookiefile, cookies_from_browser=browser),
        "extract_flat": "in_playlist",
        "lazy_playlist": True,
        "playlistend": count,
    }
    if platform == "instagram":
        ydl_opts["ignore_no_formats_error"] = True

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(listing, download=False)
    except Exception as e:
        msg = str(e)
        if is_cookie_read_error(msg):
            raise ValueError(format_cookie_read_help(msg)) from e
        if platform == "youtube" and is_youtube_bot_error(msg):
            raise ValueError(format_youtube_auth_help(msg)) from e
        raise

    title = info.get("title") or info.get("uploader") or info.get("id") or "Profile"
    entries: list[dict] = []
    for index, entry in enumerate(info.get("entries") or [], start=1):
        if not entry or index > count:
            break
        entry_url = entry.get("url") or entry.get("webpage_url") or ""
        entry_id = entry.get("id") or ""
        if not entry_url and entry_id:
            if platform == "youtube":
                entry_url = f"https://www.youtube.com/watch?v={entry_id}"
            elif platform == "instagram":
                entry_url = f"https://www.instagram.com/p/{entry_id}/"
        if entry_url and entry_url.startswith("http") is False and platform == "instagram":
            entry_url = f"https://www.instagram.com/p/{entry_url.strip('/')}/"
        if not entry_url:
            continue
        entries.append(
            {
                "index": index,
                "id": entry_id,
                "title": entry.get("title") or f"Video {index}",
                "url": entry_url,
                "duration": entry.get("duration") or 0,
            }
        )

    return platform, title, entries


def clear_fetch_cache() -> None:
    fetch_formats.clear()
    fetch_video_info.clear()
    fetch_playlist_entries.clear()
    fetch_profile_entries.clear()
