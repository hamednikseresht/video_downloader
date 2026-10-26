"""Path and input hardening for a local desktop product."""

from __future__ import annotations

import os
import re
from pathlib import Path

from src.constants import DEFAULT_COOKIES_FILE, PROJECT_ROOT
from src.utils.cookies import BROWSER_COOKIE_CHOICES

_ALLOWED_BROWSERS = {value for value, _ in BROWSER_COOKIE_CHOICES if value}
_FFMPEG_NAME_RE = re.compile(r"^ffmpeg(\.exe)?$", re.I)


def real_path(path: str) -> str:
    return os.path.realpath(os.path.abspath(path))


def is_under_directory(path: str, root: str) -> bool:
    """True if path is inside root (after resolving symlinks)."""
    if not path or not root:
        return False
    try:
        real = Path(real_path(path))
        base = Path(real_path(root))
        return real == base or base in real.parents
    except (OSError, ValueError):
        return False


def normalize_user_path(path: str, *, default_relative: str = "downloads") -> str:
    """Normalize a user path without creating directories.

    Relative paths resolve under PROJECT_ROOT. Absolute paths are allowed
    (local desktop app) but ``..`` segments are normalized away.
    """
    raw = (path or default_relative).strip() or default_relative
    if os.path.isabs(raw):
        return os.path.normpath(raw)
    # Block sneaky absolute-looking tricks after join
    joined = os.path.normpath(os.path.join(PROJECT_ROOT, raw))
    return joined


def ensure_directory(path: str) -> str:
    """Create directory if missing; return real path."""
    resolved = real_path(path) if os.path.exists(path) else os.path.normpath(path)
    os.makedirs(resolved, exist_ok=True)
    return real_path(resolved)


def assert_under_download_dir(filepath: str, download_dir: str) -> str:
    """Return real filepath if it lives under download_dir; else raise ValueError."""
    if not filepath:
        raise ValueError("Empty filepath.")
    real_file = real_path(filepath)
    real_root = real_path(download_dir)
    if not is_under_directory(real_file, real_root):
        raise ValueError("File is outside the configured download folder.")
    return real_file


def sanitize_browser_choice(value: str) -> str:
    browser = (value or "").strip().lower()
    return browser if browser in _ALLOWED_BROWSERS else ""


def sanitize_cookies_path(path: str) -> str:
    """Cookies file must stay under the project directory."""
    raw = (path or DEFAULT_COOKIES_FILE).strip() or DEFAULT_COOKIES_FILE
    if not os.path.isabs(raw):
        raw = os.path.normpath(os.path.join(PROJECT_ROOT, raw))
    else:
        raw = os.path.normpath(raw)
    if not is_under_directory(raw, PROJECT_ROOT):
        return DEFAULT_COOKIES_FILE
    # Must be a .txt file name (no directory traversal leftovers)
    if not raw.lower().endswith(".txt"):
        return DEFAULT_COOKIES_FILE
    return raw


def is_safe_ffmpeg_path(path: str) -> bool:
    """Accept empty (auto), a directory containing ffmpeg, or ffmpeg binary path."""
    text = (path or "").strip()
    if not text:
        return True
    if os.path.isdir(text):
        exe = os.path.join(text, "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
        return os.path.isfile(exe)
    if os.path.isfile(text):
        return bool(_FFMPEG_NAME_RE.match(os.path.basename(text)))
    return False


def write_private_file(path: str, data: bytes) -> None:
    """Write bytes and restrict permissions to the current user when possible."""
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def cleanup_partial_downloads(download_dir: str, basename_prefix: str = "") -> int:
    """Remove leftover .part / .ytdl files in download_dir. Returns count removed."""
    if not download_dir or not os.path.isdir(download_dir):
        return 0
    removed = 0
    for name in os.listdir(download_dir):
        lower = name.lower()
        if not (lower.endswith(".part") or lower.endswith(".ytdl")):
            continue
        if basename_prefix and not name.startswith(basename_prefix):
            continue
        path = os.path.join(download_dir, name)
        if not os.path.isfile(path):
            continue
        try:
            assert_under_download_dir(path, download_dir)
            os.remove(path)
            removed += 1
        except (OSError, ValueError):
            continue
    return removed
