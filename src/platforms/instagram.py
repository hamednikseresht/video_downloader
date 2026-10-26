def instagram_format_selector(
    format_id: str, *, audio_only: bool = False, height: int = 0
) -> str:
    """Prefer a muxed MP4. Merging dash+audio on Windows often hits Errno 22."""
    if audio_only:
        return "bestaudio/best"
    fid = (format_id or "").strip()
    parts: list[str] = []
    limit = int(height or 0)
    if not limit and "height<=" in fid:
        raw = fid.split("height<=", 1)[1].split("]", 1)[0]
        if raw.isdigit():
            limit = int(raw)
    if limit:
        parts.append(f"best[height<={limit}][ext=mp4]")
        parts.append(f"best[height<={limit}]")
    if fid and fid != "0" and "best" not in fid:
        parts.append(fid)
    parts.append("best[ext=mp4]")
    parts.append("best")
    return "/".join(parts)


def parse_instagram_formats(formats: list) -> tuple[list, list]:
    """Instagram posts/reels usually ship as a single muxed MP4 per quality."""
    video_formats = []
    seen_labels: set[str] = set()

    for f in formats:
        ext = f.get("ext", "")
        vcodec = f.get("vcodec", "none")
        acodec = f.get("acodec") or "none"
        if vcodec == "none" or ext not in ("mp4", "webm", "mkv", "m4v"):
            continue

        height = f.get("height") or 0
        filesize = f.get("filesize") or f.get("filesize_approx") or 0
        label = f"{height}p" if height else (f.get("format_note") or "Best quality")
        has_audio = acodec != "none"
        if label in seen_labels and not has_audio:
            continue
        seen_labels.add(label)

        video_formats.append(
            {
                "format_id": f["format_id"],
                "label": label,
                "has_audio": has_audio,
                "height": height or 720,
                "ext": "mp4",
                "fps": f.get("fps") or 0,
                "filesize": filesize,
                "tbr": f.get("tbr") or 0,
            }
        )

    video_formats.sort(key=lambda x: (x["height"], x["filesize"], x["tbr"]), reverse=True)

    audio_formats = []
    if video_formats:
        best = video_formats[0]
        audio_formats.append(
            {
                "format_id": best["format_id"],
                "label": "Best available",
                "abr": best.get("tbr") or 0,
                "ext": best["ext"],
                "filesize": best["filesize"],
            }
        )

    return video_formats, audio_formats
