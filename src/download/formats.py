import re

from src.platforms.instagram import parse_instagram_formats

_LANG_NAMES = {
    "en": "English",
    "fa": "Persian",
    "ar": "Arabic",
    "de": "German",
    "es": "Spanish",
    "fr": "French",
    "hi": "Hindi",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "pt": "Portuguese",
    "ru": "Russian",
    "tr": "Turkish",
    "ur": "Urdu",
    "zh": "Chinese",
}


def _video_format_score(fmt: dict) -> tuple:
    protocol = (fmt.get("protocol") or "").lower()
    # Prefer progressive HTTPS over HLS fragment streams on Windows.
    progressive = 2 if protocol.startswith("http") and "m3u8" not in protocol else 0
    ext_rank = {"mp4": 2, "webm": 1}.get(fmt["ext"], 0)
    return (progressive, ext_rank, fmt["filesize"], fmt["tbr"], fmt["fps"])


def parse_youtube_formats(formats: list) -> tuple[list, list]:
    """Pick the best stream per resolution/bitrate for the quality picker."""
    best_video_by_height: dict[int, dict] = {}
    audio_formats = []
    seen_audio: set[str] = set()

    for f in formats:
        ext = f.get("ext", "")
        filesize = f.get("filesize") or f.get("filesize_approx") or 0
        vcodec = f.get("vcodec", "none")
        acodec = f.get("acodec", "none")

        if vcodec != "none":
            height = f.get("height")
            if not height or ext not in ("mp4", "webm"):
                continue

            fps = f.get("fps") or 0
            label = f"{height}p"
            if fps > 30:
                label += f" {int(fps)}fps"
            protocol = f.get("protocol") or ""
            if "m3u8" in protocol:
                label += " · stream"

            candidate = {
                "format_id": f["format_id"],
                "label": label,
                "height": height,
                "ext": ext,
                "fps": fps,
                "filesize": filesize,
                "tbr": f.get("tbr") or 0,
                "protocol": protocol,
            }
            current = best_video_by_height.get(height)
            if current is None or _video_format_score(candidate) > _video_format_score(current):
                best_video_by_height[height] = candidate
        elif acodec != "none":
            abr = f.get("abr") or 0
            if not abr:
                continue

            label = f"{int(abr)}kbps ({ext})"
            if label in seen_audio:
                continue
            seen_audio.add(label)
            audio_formats.append(
                {
                    "format_id": f["format_id"],
                    "label": label,
                    "abr": abr,
                    "ext": ext,
                    "filesize": filesize,
                }
            )

    video_formats = sorted(best_video_by_height.values(), key=lambda x: x["height"], reverse=True)
    audio_formats.sort(key=lambda x: x["abr"], reverse=True)
    return video_formats, audio_formats


def parse_formats_for_platform(formats: list, platform: str) -> tuple[list, list]:
    if platform == "instagram":
        return parse_instagram_formats(formats)
    return parse_youtube_formats(formats)


def _subtitle_label(lang: str, source: str) -> str:
    name = _LANG_NAMES.get(lang, lang.upper())
    kind = "Manual" if source == "manual" else "Auto-generated"
    return f"{name} ({lang}) — {kind}"


def parse_subtitles(manual: dict, automatic: dict) -> list[dict]:
    options = []
    for lang in sorted(manual.keys()):
        options.append(
            {"lang": lang, "source": "manual", "label": _subtitle_label(lang, "manual")}
        )
    for lang in sorted(automatic.keys()):
        if lang in manual:
            continue
        options.append(
            {"lang": lang, "source": "auto", "label": _subtitle_label(lang, "auto")}
        )
    return options


def format_size(size_bytes: int) -> str:
    if not size_bytes:
        return "Unknown size"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def format_duration(seconds: int) -> str:
    if not seconds:
        return "Unknown"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m}m {s}s"
    return f"{m}m {s}s"


def clean_download_title(title: str, url: str = "", uploader: str = "") -> str:
    """Turn a URL-shaped Instagram title into a short readable name."""
    from src.platforms.detect import media_id

    raw = " ".join((title or "").split())
    lowered = raw.lower()
    looks_like_url = (
        "http://" in lowered
        or "https://" in lowered
        or "instagram.com" in lowered
        or "youtube.com" in lowered
        or "youtu.be" in lowered
    )
    short = media_id(url)
    if looks_like_url or not raw or lowered in {"unknown", "unknown title"}:
        who = " ".join((uploader or "").split())
        if who and short:
            return f"{who} {short}"
        if short:
            return short
        if "instagram" in lowered or "instagram.com" in (url or "").lower():
            return "Instagram video"
        return "download"
    if len(raw) > 80:
        raw = raw[:80].rstrip()
    return raw


def sanitize_title(title: str, max_len: int = 120) -> str:
    """ASCII-only names so Windows fragment resume does not hit Errno 22."""
    chars: list[str] = []
    for c in title or "":
        if c.isascii() and (c.isalnum() or c in " _-"):
            chars.append(c)
        elif c.isalnum() or c.isspace():
            chars.append("_")
    safe = re.sub(r"[_\s]+", "_", "".join(chars)).strip(" _-")
    safe = safe or "download"
    if len(safe) > max_len:
        safe = safe[:max_len].rstrip(" _-")
    return safe or "download"


def match_subtitle(options: list[dict], wanted: dict | None) -> tuple[dict | None, str]:
    """Pick the requested track, or the closest track that exists."""
    if not wanted:
        return None, ""
    lang = wanted.get("lang") or ""
    source = wanted.get("source") or "auto"
    for opt in options:
        if opt.get("lang") == lang and opt.get("source") == source:
            return opt, ""
    for opt in options:
        if opt.get("lang") == lang:
            return opt, f"Using {opt.get('label', lang)}."
    if options:
        first = options[0]
        return first, f"{lang or 'That language'} is not available. Using {first.get('label', 'the first track')}."
    return None, "No subtitles are available for this video."


def closest_height(prefer_height: int, heights: list[int]) -> int | None:
    """Exact height, otherwise the nearest lower one, otherwise the lowest higher one."""
    available = sorted({int(h) for h in heights if h})
    if not available:
        return None
    if prefer_height in available:
        return prefer_height
    lower = [h for h in available if h < prefer_height]
    if lower:
        return lower[-1]
    return available[0]


def quality_note(prefer_height: int, heights: list[int]) -> str:
    available = [int(h) for h in heights if h]
    chosen = closest_height(prefer_height, available)
    if chosen is None:
        return ""
    top = max(available)
    if chosen != prefer_height:
        return f"{prefer_height}p is not available. Using {chosen}p instead."
    return f"First video offers up to {top}p."


def build_output_basename(
    title: str,
    selected_format: dict,
    is_video: bool,
    *,
    uploader: str = "",
    index: int | None = None,
    video_id: str = "",
    stamp: str = "",
) -> str:
    parts: list[str] = []
    if index:
        parts.append(f"{int(index):03d}")
    if uploader:
        parts.append(sanitize_title(uploader, 40))
    if stamp:
        parts.append(stamp)
    parts.append(sanitize_title(title))

    if is_video:
        height = selected_format.get("height")
        if height:
            parts.append(f"{height}p")
        fps = int(selected_format.get("fps") or 0)
        if fps > 30:
            parts.append(f"{fps}fps")
    else:
        abr = selected_format.get("abr")
        if abr:
            parts.append(f"{int(abr)}kbps")

    if video_id:
        parts.append(sanitize_title(video_id, 32))

    return "_".join(parts)[:200]


def build_subtitle_basename(title: str, lang: str, source: str) -> str:
    parts = [sanitize_title(title), lang]
    if source == "auto":
        parts.append("auto")
    parts.append("subtitle")
    return "_".join(parts)[:200]


def build_video_subtitle_basename(video_basename: str, lang: str) -> str:
    return f"{video_basename}.{lang}"


def build_thumbnail_basename(title: str) -> str:
    return f"{sanitize_title(title)}_thumbnail"[:200]


def preferred_video_format(prefer_height: int = 720) -> dict:
    """Synthetic format for playlist/batch quick downloads (no per-item format fetch)."""
    return {
        "format_id": f"bestvideo[height<={prefer_height}][ext=mp4]",
        "height": prefer_height,
        "label": f"≤{prefer_height}p",
        "filesize": 0,
        "fps": 0,
        "ext": "mp4",
        "tbr": 0,
    }


def preferred_audio_format(abr: int = 192) -> dict:
    return {
        "format_id": "bestaudio",
        "abr": abr,
        "label": f"{abr}kbps",
        "filesize": 0,
        "ext": "m4a",
    }


def is_progressive_format(fmt: dict | None) -> bool:
    if not fmt:
        return False
    protocol = (fmt.get("protocol") or "").lower()
    label = (fmt.get("label") or "").lower()
    if "m3u8" in protocol or "hls" in protocol or "stream" in label:
        return False
    return protocol.startswith("http") or not protocol


def pick_default_video_format(video_formats: list[dict], prefer_height: int = 720) -> dict | None:
    """Pick a format that is likely to finish. Progressive HTTP beats HLS streams."""
    if not video_formats:
        return None
    progressive = [fmt for fmt in video_formats if is_progressive_format(fmt)]
    pool = progressive or video_formats
    chosen = closest_height(prefer_height, [fmt.get("height") or 0 for fmt in pool])
    if chosen is not None:
        for fmt in pool:
            if fmt.get("height") == chosen:
                return fmt
    return pool[0]


def pick_default_audio_format(audio_formats: list[dict]) -> dict | None:
    return audio_formats[0] if audio_formats else None
