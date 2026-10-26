import os

from src.constants import PROJECT_ROOT
from src.download.formats import format_size
from src.security import ensure_directory, normalize_user_path


def resolve_download_dir(path: str = "", *, create: bool = False) -> str:
    """Resolve the download folder.

    Relative paths (e.g. ``downloads``) are resolved under the project root.
    Directories are created only when ``create=True`` (save / download), not on
    every sidebar keystroke.
    """
    resolved = normalize_user_path(path, default_relative="downloads")
    if create:
        return ensure_directory(resolved)
    return os.path.normpath(resolved)


def download_dir_setting_value(resolved_dir: str) -> str:
    """Store project-default folder as ``downloads``; keep custom paths as-is."""
    default = os.path.normpath(os.path.join(PROJECT_ROOT, "downloads"))
    if os.path.normpath(resolved_dir) == default:
        return "downloads"
    return resolved_dir


def get_expected_output_path(download_dir: str, output_basename: str, ext: str) -> str:
    if not ext.startswith("."):
        ext = f".{ext}"
    return os.path.join(download_dir, f"{output_basename}{ext}")


_KIND_EXTS = {
    "video": {".mp4", ".mkv", ".webm", ".m4v"},
    "audio": {".mp3", ".m4a", ".wav"},
    "thumbnail": {".jpg", ".jpeg", ".webp", ".png"},
    "subtitle": {".srt", ".vtt"},
}


def find_saved_download(
    download_dir: str,
    url: str = "",
    title: str = "",
    kind: str = "video",
) -> str | None:
    """Find a finished file in the download folder for this link or title."""
    from src.download.formats import sanitize_title
    from src.platforms.detect import media_id

    if not download_dir or not os.path.isdir(download_dir):
        return None
    key = (media_id(url) or "").lower()
    title_key = sanitize_title(title).lower().replace(" ", "_")
    if len(title_key) < 6:
        title_key = ""
    if not key and not title_key:
        return None
    allowed = _KIND_EXTS.get(kind) or _KIND_EXTS["video"]
    base = os.path.abspath(download_dir)
    for root, dirs, files in os.walk(base):
        rel = os.path.relpath(root, base)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth > 2:
            dirs.clear()
            continue
        for name in files:
            ext = os.path.splitext(name)[1].lower()
            if ext not in allowed or name.endswith(".part"):
                continue
            stem = os.path.splitext(name)[0].lower()
            if key and key in stem:
                return os.path.join(root, name)
            if title_key and title_key in stem:
                return os.path.join(root, name)
    return None


def find_file_for_media(download_dir: str, media_key: str) -> str | None:
    """Return a finished file whose name contains this media id."""
    key = (media_key or "").strip().lower()
    if not key or not download_dir or not os.path.isdir(download_dir):
        return None
    skip_ext = {".part", ".ytdl", ".tmp", ".json"}
    base = os.path.abspath(download_dir)
    for root, dirs, files in os.walk(base):
        rel = os.path.relpath(root, base)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth > 2:
            dirs.clear()
            continue
        for name in files:
            ext = os.path.splitext(name)[1].lower()
            if ext in skip_ext or name.endswith(".part"):
                continue
            if key in name.lower():
                return os.path.join(root, name)
    return None


def find_existing_download(download_dir: str, output_basename: str, ext: str) -> str | None:
    expected = get_expected_output_path(download_dir, output_basename, ext)
    if os.path.isfile(expected):
        return expected
    return None


def find_partial_download(download_dir: str, output_basename: str) -> str | None:
    """Return a leftover .part / .ytdl path for this basename, if any."""
    if not download_dir or not os.path.isdir(download_dir):
        return None
    try:
        names = os.listdir(download_dir)
    except OSError:
        return None
    matches = []
    for name in names:
        lower = name.lower()
        if not name.startswith(output_basename):
            continue
        if lower.endswith(".part") or lower.endswith(".ytdl"):
            matches.append(os.path.join(download_dir, name))
    if not matches:
        return None
    return max(matches, key=os.path.getmtime)


def partial_looks_broken(path: str) -> bool:
    """Fragment leftovers and non-ASCII names often break resume on Windows."""
    name = os.path.basename(path or "")
    lower = name.lower()
    if "frag" in lower:
        return True
    if lower.count(".part") >= 2:
        return True
    try:
        name.encode("ascii")
    except UnicodeEncodeError:
        return True
    return False


def clear_resume_files(download_dir: str, output_basename: str, media_key: str = "") -> int:
    from src.security import cleanup_partial_downloads

    removed = cleanup_partial_downloads(download_dir, output_basename)
    key = (media_key or "").strip()
    if not key or not download_dir or not os.path.isdir(download_dir):
        return removed
    try:
        names = os.listdir(download_dir)
    except OSError:
        return removed
    for name in names:
        lower = name.lower()
        if not (lower.endswith(".part") or lower.endswith(".ytdl")):
            continue
        if key.lower() not in name.lower():
            continue
        path = os.path.join(download_dir, name)
        try:
            os.remove(path)
            removed += 1
        except OSError:
            continue
    return removed


def list_recent_downloads(download_dir: str, limit: int = 8) -> list[tuple[str, str]]:
    if not os.path.isdir(download_dir):
        return []
    files = []
    try:
        names = os.listdir(download_dir)
    except OSError:
        return []
    for name in names:
        path = os.path.join(download_dir, name)
        try:
            if os.path.isfile(path) and not name.startswith("."):
                lower = name.lower()
                if lower.endswith((".part", ".ytdl")):
                    continue
                files.append((name, os.path.getmtime(path), os.path.getsize(path)))
        except OSError:
            continue
    files.sort(key=lambda x: x[1], reverse=True)
    return [(n, format_size(s)) for n, _, s in files[:limit]]


def resolve_subtitle_filepath(
    download_dir: str,
    output_basename: str,
    lang: str,
    ext: str,
    ffmpeg_path: str = "",
) -> str | None:
    if not ext.startswith("."):
        ext = f".{ext}"

    candidates = [
        get_expected_output_path(download_dir, output_basename, ext),
        os.path.join(download_dir, f"{output_basename}.{lang}{ext}"),
        get_expected_output_path(download_dir, output_basename, ".vtt"),
        os.path.join(download_dir, f"{output_basename}.{lang}.vtt"),
    ]

    for path in candidates:
        if os.path.isfile(path):
            if path.lower().endswith(".vtt") and ext == ".srt":
                from src.subtitles.convert import convert_subtitle_file

                target = get_expected_output_path(download_dir, output_basename, ".srt")
                return convert_subtitle_file(path, target, "srt", ffmpeg_path)
            return path

    if not os.path.isdir(download_dir):
        return None

    matches = [
        os.path.join(download_dir, name)
        for name in os.listdir(download_dir)
        if name.lower().endswith((".srt", ".vtt"))
        and name.startswith(output_basename)
    ]
    if not matches:
        return None

    path = max(matches, key=os.path.getmtime)
    if path.lower().endswith(".vtt") and ext == ".srt":
        from src.subtitles.convert import convert_subtitle_file

        target = get_expected_output_path(download_dir, output_basename, ".srt")
        return convert_subtitle_file(path, target, "srt", ffmpeg_path)
    return path


def resolve_downloaded_filepath(
    info: dict,
    ydl,
    download_dir: str,
    output_basename: str,
    ext: str,
) -> str | None:
    if not ext.startswith("."):
        ext = f".{ext}"

    filepath = info.get("filepath")
    if filepath and os.path.isfile(filepath):
        return filepath

    for entry in reversed(info.get("requested_downloads") or []):
        entry_path = entry.get("filepath")
        if entry_path and os.path.isfile(entry_path):
            return entry_path

    try:
        prepared = ydl.prepare_filename(info)
        if prepared and os.path.isfile(prepared):
            return prepared
    except Exception:
        pass

    expected = get_expected_output_path(download_dir, output_basename, ext)
    if os.path.isfile(expected):
        return expected

    if not os.path.isdir(download_dir):
        return None

    matches = [
        os.path.join(download_dir, name)
        for name in os.listdir(download_dir)
        if name.lower().endswith(ext)
        and (name.startswith(output_basename) or output_basename.lower() in name.lower())
    ]
    if not matches:
        return None

    return max(matches, key=os.path.getmtime)


def resolve_thumbnail_filepath(download_dir: str, output_basename: str) -> str | None:
    for ext in (".jpg", ".webp", ".png", ".jpeg"):
        path = get_expected_output_path(download_dir, output_basename, ext)
        if os.path.isfile(path):
            return path

    if not os.path.isdir(download_dir):
        return None

    matches = [
        os.path.join(download_dir, name)
        for name in os.listdir(download_dir)
        if name.lower().endswith((".jpg", ".webp", ".png", ".jpeg"))
        and name.startswith(output_basename)
    ]
    if not matches:
        return None
    return max(matches, key=os.path.getmtime)
