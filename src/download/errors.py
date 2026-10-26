"""User-facing download error guides and recovery hints."""

from __future__ import annotations

from dataclasses import dataclass

from src.download.ydl import curl_cffi_available, strip_ansi
from src.utils.cookies import (
    format_cookie_read_help,
    format_youtube_auth_help,
    is_cookie_read_error,
    is_youtube_bot_error,
)


@dataclass
class ErrorGuide:
    title: str
    detail: str
    steps: list[str]
    actions: list[str]  # machine keys: install_ffmpeg, open_cookies, install_packages, retry, wait


def classify_download_error(error: str, download_kind: str = "video") -> ErrorGuide:
    clean = strip_ansi(error or "").strip()
    lower = clean.lower()

    if "unable to download video" in lower and ("errno 22" in lower or "invalid argument" in lower):
        return ErrorGuide(
            title="This quality could not be saved on Windows",
            detail=clean,
            steps=[
                "The app already retries with a simpler progressive file (often 360p).",
                "If it still fails, pick a quality that is not labeled “stream”.",
                "Then click Start download again.",
            ],
            actions=["retry"],
        )

    if is_cookie_read_error(clean):
        return ErrorGuide(
            title="Could not read browser cookies",
            detail=format_cookie_read_help(clean),
            steps=[
                "Fully quit the browser (check the system tray), then try again.",
                "Or export a Netscape cookies.txt while logged into YouTube and upload it in Settings.",
                "Firefox often works better than Chrome/Edge while the browser is open.",
            ],
            actions=["open_cookies", "retry"],
        )

    if is_youtube_bot_error(clean):
        return ErrorGuide(
            title="YouTube asked you to sign in",
            detail=format_youtube_auth_help(clean),
            steps=[
                "Open Settings → YouTube cookies.",
                "Choose a browser where you are logged into YouTube (try Firefox).",
                "Click Save, then Refresh the video URL and download again.",
            ],
            actions=["open_cookies", "retry"],
        )

    if "429" in clean or "too many requests" in lower:
        steps = [
            "Wait 1–2 minutes before trying again.",
            "Avoid rapid Refresh / Download clicks.",
            "For playlists, use a smaller item range.",
        ]
        if not curl_cffi_available():
            steps.append('Install: pip install "yt-dlp[default,curl-cffi]" then restart the app.')
        return ErrorGuide(
            title="Rate limited (HTTP 429)",
            detail=clean,
            steps=steps,
            actions=["wait", "install_packages", "retry"],
        )

    if any(
        x in lower
        for x in (
            "ffmpeg",
            "ffprobe",
            "postprocessing",
            "merger",
            "requested format is not available",
        )
    ) or (download_kind in ("video", "audio") and "converter" in lower):
        return ErrorGuide(
            title="FFmpeg is missing or misconfigured",
            detail=clean,
            steps=[
                "Video+audio merge and MP3 conversion need FFmpeg.",
                "Windows: run winget install Gyan.FFmpeg (or use Fix setup in the app).",
                "Then set the FFmpeg path in Settings, or restart the app so PATH updates.",
            ],
            actions=["install_ffmpeg", "retry"],
        )

    if any(x in lower for x in ("private video", "login required", "members-only", "join this channel")):
        return ErrorGuide(
            title="This video needs login / membership",
            detail=clean,
            steps=[
                "Enable browser cookies for an account that can watch the video.",
                "Age-restricted and private videos need a logged-in session.",
                "Instagram private content is not supported.",
            ],
            actions=["open_cookies", "retry"],
        )

    if any(x in lower for x in ("network", "timed out", "timeout", "connection", "ssl", "unreachable", "getaddrinfo")):
        return ErrorGuide(
            title="Network problem",
            detail=clean,
            steps=[
                "Check your internet connection.",
                "If you use a VPN/proxy, try another server or turn it off.",
                "Click Download again to retry from the start.",
            ],
            actions=["retry"],
        )

    if "errno 22" in lower or "invalid argument" in lower:
        return ErrorGuide(
            title="This quality could not be saved on Windows",
            detail=clean,
            steps=[
                "The app already retries with a simpler progressive file (often 360p).",
                "If it still fails, pick a quality that is not labeled “stream”.",
                "Then click Start download again.",
            ],
            actions=["retry"],
        )

    if any(x in lower for x in ("no space", "disk", "errno 28", "not enough space")):
        return ErrorGuide(
            title="Disk space or folder problem",
            detail=clean,
            steps=[
                "Free disk space on the download drive.",
                "Or choose another Download folder in Settings.",
            ],
            actions=["retry"],
        )

    if "only images are available" in lower or "unsupported url" in lower:
        return ErrorGuide(
            title="Unsupported or unavailable media",
            detail=clean,
            steps=[
                "Confirm the link is a public YouTube or Instagram video/reel.",
                "Stories and some private posts are not supported.",
            ],
            actions=["retry"],
        )

    if download_kind == "subtitle":
        return ErrorGuide(
            title="Subtitle download failed",
            detail=clean,
            steps=[
                "Try another language or switch SRT/VTT.",
                "Wait a minute if YouTube is rate-limiting.",
                "Auto-generated captions fail more often than manual ones.",
            ],
            actions=["wait", "retry"],
        )

    return ErrorGuide(
        title="Download failed",
        detail=clean or "Unknown error",
        steps=[
            "Click Download again to retry from the start.",
            "Open Health check in the sidebar and fix any red items.",
            "For YouTube bot checks, enable cookies in Settings.",
        ],
        actions=["retry", "install_packages"],
    )


_QUEUE_PAUSE_TITLES = {
    "Could not read browser cookies",
    "YouTube asked you to sign in",
    "Rate limited (HTTP 429)",
    "FFmpeg is missing or misconfigured",
}


def pauses_queue(guide: ErrorGuide) -> bool:
    """True when the same failure would hit every remaining item."""
    return guide.title in _QUEUE_PAUSE_TITLES


def format_guide_markdown(guide: ErrorGuide) -> str:
    lines = [f"**{guide.title}**", "", guide.detail, "", "**What to do:**"]
    for i, step in enumerate(guide.steps, 1):
        lines.append(f"{i}. {step}")
    return "\n".join(lines)
