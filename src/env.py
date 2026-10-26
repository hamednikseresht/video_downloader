"""Load machine-specific config and auth from the environment / a local `.env` file."""

from __future__ import annotations

import os

_ENV_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
_loaded = False


def load_dotenv(path: str = _ENV_FILE) -> None:
    """Read KEY=VALUE lines into os.environ. Real environment variables win."""
    global _loaded
    if _loaded:
        return
    _loaded = True
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


def env_str(name: str) -> str | None:
    load_dotenv()
    value = os.environ.get(name, "").strip()
    return value or None


def env_float(name: str) -> float | None:
    value = env_str(name)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def env_overrides() -> dict:
    """Settings supplied via env. Only keys that are set are returned."""
    out: dict = {}
    for key, name in (
        ("download_dir", "YTDL_DOWNLOAD_DIR"),
        ("ffmpeg_path", "YTDL_FFMPEG_PATH"),
        ("cookies_path", "YTDL_COOKIES_PATH"),
        ("cookies_from_browser", "YTDL_COOKIES_BROWSER"),
    ):
        value = env_str(name)
        if value is not None:
            out[key] = value
    pause = env_float("YTDL_BATCH_PAUSE_SEC")
    if pause is not None:
        out["batch_pause_sec"] = pause
    return out
