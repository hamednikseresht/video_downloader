def is_hls_protocol(protocol: str = "") -> bool:
    text = (protocol or "").lower()
    return "m3u8" in text or "hls" in text


def video_format_selector(height: int, format_id: str, protocol: str = "") -> str:
    """Prefer progressive HTTP, then DASH merge, and only then HLS fragments.

    HLS (m3u8) often fails on Windows with Errno 22. The picker may show a
    720p stream, but the downloader should still try a working progressive
    file first and only use HLS if nothing else matches.
    """
    parts: list[str] = []
    fid = (format_id or "").strip()
    height = int(height or 0)
    hls = is_hls_protocol(protocol)

    # Exact progressive ids (18, 22, …) first — these are single HTTP files.
    if fid and fid.isdigit() and fid != "0" and not hls:
        parts.append(fid)

    if height:
        parts.append(f"best[height<={height}][protocol^=http][protocol!*=m3u8]")
        parts.append(f"best[height<={height}][ext=mp4][protocol^=http][protocol!*=m3u8]")
        parts.append(f"best[height<={height}][ext=mp4][protocol^=http]")
        parts.append(f"bestvideo[height<={height}][ext=mp4][protocol!*=m3u8]+bestaudio[ext=m4a]")
        parts.append(f"bestvideo[height<={height}][protocol!*=m3u8]+bestaudio")

    if fid and "best" not in fid and fid != "0":
        parts.append(fid)

    if height:
        parts.append(f"best[height<={height}]")
        parts.append(f"bestvideo[height<={height}]+bestaudio")

    parts.append("best[protocol^=http][protocol!*=m3u8]")
    parts.append("best[ext=mp4]")
    parts.append("best")
    return "/".join(parts)


def progressive_fallback_selector(attempt: int = 0) -> str:
    """Selectors used after Windows HLS / Errno 22 failures."""
    fallbacks = (
        "best[protocol^=http][protocol!*=m3u8]/best[ext=mp4][protocol^=http]/18/best[ext=mp4]/best",
        "18/best[height<=360][protocol^=http]/best[height<=360]/best[ext=mp4]/best",
        "best[ext=mp4]/best",
    )
    return fallbacks[min(max(attempt, 0), len(fallbacks) - 1)]
