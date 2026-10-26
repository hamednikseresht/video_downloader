import os
import re
import time

from src.constants import (
    FRAGMENT_CONCURRENCY,
    SOCKET_TIMEOUT_SEC,
    _WINDOWS_DENO_PATHS,
    _WINDOWS_NODE_PATHS,
)
from src.platforms.instagram import instagram_format_selector
from src.platforms.youtube import video_format_selector
from src.settings import resolve_ffmpeg_location

_JS_RUNTIME_CACHE: dict | None = None
_JS_RUNTIME_CACHE_AT = 0.0
_JS_RUNTIME_TTL_SEC = 300.0


def _runtime_from_path(name: str, path: str):
    from yt_dlp.globals import supported_js_runtimes

    runtime_cls = supported_js_runtimes.value.get(name)
    if runtime_cls is None:
        return None
    return runtime_cls(path).info


def runtime_status(*, force: bool = False) -> dict:
    global _JS_RUNTIME_CACHE, _JS_RUNTIME_CACHE_AT
    now = time.monotonic()
    if (
        not force
        and _JS_RUNTIME_CACHE is not None
        and (now - _JS_RUNTIME_CACHE_AT) < _JS_RUNTIME_TTL_SEC
    ):
        return _JS_RUNTIME_CACHE

    from yt_dlp.globals import supported_js_runtimes

    result = {"name": None, "version": "", "supported": False, "path": ""}
    for name in ("deno", "node", "quickjs", "bun"):
        runtime_cls = supported_js_runtimes.value.get(name)
        if runtime_cls is None:
            continue

        info = runtime_cls().info
        if info is None:
            continue

        result = {
            "name": name,
            "version": info.version,
            "supported": info.supported,
            "path": info.path,
        }
        break

    _JS_RUNTIME_CACHE = result
    _JS_RUNTIME_CACHE_AT = now
    return result


def detect_js_runtime() -> tuple[str | None, str]:
    status = runtime_status()
    if status["supported"]:
        return status["name"], status["version"]
    if status["name"]:
        return None, f"{status['name']} {status['version']} (upgrade to Node 22+ or Deno 2.3+)"
    return None, "not installed"


def get_base_ydl_opts(
    cookiefile: str | None = None,
    cookies_from_browser: str | None = None,
) -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "retries": 8,
        "fragment_retries": 8,
        "file_access_retries": 8,
        "sleep_interval_requests": 0.75,
        "concurrent_fragment_downloads": FRAGMENT_CONCURRENCY,
        "socket_timeout": SOCKET_TIMEOUT_SEC,
        "windowsfilenames": True,
        "restrictfilenames": True,
        "retry_sleep_functions": {
            "http": lambda n: min(3 * (2**n), 30),
            "fragment": lambda n: min(3 * (2**n), 30),
        },
    }

    from src.utils.cookies import apply_auth_to_ydl_opts

    apply_auth_to_ydl_opts(opts, cookiefile=cookiefile, cookies_from_browser=cookies_from_browser)
    impersonate = get_impersonate_target()
    if impersonate is not None:
        opts["impersonate"] = impersonate

    runtime_name, _ = detect_js_runtime()
    if runtime_name:
        opts["js_runtimes"] = {runtime_name: {}}
        return opts

    if os.name == "nt":
        for path in _WINDOWS_DENO_PATHS + _WINDOWS_NODE_PATHS:
            if not os.path.isfile(path):
                continue
            name = "deno" if "deno" in os.path.basename(path).lower() else "node"
            info = _runtime_from_path(name, path)
            if info and info.supported:
                opts["js_runtimes"] = {name: {"path": path}}
                break

    return opts


def curl_cffi_available() -> bool:
    try:
        import curl_cffi  # noqa: F401
    except ImportError:
        return False
    return True


def get_impersonate_target():
    if not curl_cffi_available():
        return None

    from yt_dlp.networking.impersonate import ImpersonateTarget

    if os.name == "nt":
        return ImpersonateTarget("edge", "101", "windows", "10")
    return ImpersonateTarget("chrome", "131", "macos", "15")


def get_curl_impersonate() -> str:
    return "edge101" if os.name == "nt" else "chrome131"


def get_subtitle_rate_limit_opts() -> dict:
    opts = {
        "sleep_interval_subtitles": 2,
        "sleep_interval_requests": 1.5,
        "socket_timeout": SOCKET_TIMEOUT_SEC,
        "retries": 10,
        "fragment_retries": 10,
        "file_access_retries": 10,
        "retry_sleep_functions": {
            "http": lambda n: min(5 * (2**n), 60),
            "fragment": lambda n: min(5 * (2**n), 60),
            "extractor": lambda n: min(5 * (2**n), 60),
        },
    }
    impersonate = get_impersonate_target()
    if impersonate is not None:
        opts["impersonate"] = impersonate
    return opts


def _build_outtmpl(
    download_dir: str, output_basename: str, subtitle_lang: str | None = None
) -> dict | str:
    default = os.path.join(download_dir, f"{output_basename}.%(ext)s")
    if subtitle_lang:
        return {
            "default": default,
            "subtitle": os.path.join(
                download_dir, f"{output_basename}.%(lang)s.%(ext)s"
            ),
        }
    return default


def _subtitle_opts(subtitle: dict, subtitle_format: str) -> dict:
    use_manual = subtitle["source"] == "manual"
    return {
        "writesubtitles": use_manual,
        "writeautomaticsub": not use_manual,
        "subtitleslangs": [subtitle["lang"]],
        "subtitlesformat": f"{subtitle_format}/best",
        **get_subtitle_rate_limit_opts(),
    }


def build_ydl_opts(
    output_basename: str,
    selected_format: dict,
    download_kind: str,
    progress_hook,
    download_dir: str,
    ffmpeg_path: str = "",
    subtitle: dict | None = None,
    subtitle_format: str = "srt",
    platform: str = "youtube",
    cookiefile: str | None = None,
    cookies_from_browser: str | None = None,
    include_thumbnail: bool = False,
) -> dict:
    base_opts = {
        **get_base_ydl_opts(
            cookiefile=cookiefile,
            cookies_from_browser=cookies_from_browser,
        ),
        "outtmpl": _build_outtmpl(
            download_dir,
            output_basename,
            subtitle["lang"] if subtitle and download_kind in ("video", "audio") else None,
        ),
        "progress_hooks": [progress_hook],
        # Always start a fresh download. Partial/fragment resume is unreliable on Windows.
        "continuedl": False,
        "nopart": False,
        "overwrites": True,
        "nooverwrites": False,
    }

    ffmpeg_location = resolve_ffmpeg_location(ffmpeg_path)
    if ffmpeg_location:
        base_opts["ffmpeg_location"] = ffmpeg_location

    if download_kind == "subtitle":
        return {
            **base_opts,
            "skip_download": True,
            "outtmpl": {
                "default": os.path.join(download_dir, f"{output_basename}.%(ext)s"),
                "subtitle": os.path.join(download_dir, f"{output_basename}.%(ext)s"),
            },
            **_subtitle_opts(subtitle, subtitle_format),
        }

    if download_kind == "thumbnail":
        return {
            **base_opts,
            "skip_download": True,
            "writethumbnail": True,
            "outtmpl": os.path.join(download_dir, f"{output_basename}.%(ext)s"),
        }

    if download_kind == "video":
        if platform == "instagram":
            format_selector = instagram_format_selector(
                selected_format.get("format_id", ""),
                height=int(selected_format.get("height") or 0),
            )
            merge_format = "mp4"
            opts = {
                **base_opts,
                "format": format_selector,
                "merge_output_format": merge_format,
                "ignore_no_formats_error": True,
            }
            if subtitle:
                opts.update(_subtitle_opts(subtitle, subtitle_format))
            if include_thumbnail:
                opts["writethumbnail"] = True
            return opts
        format_selector = video_format_selector(
            selected_format.get("height") or 0,
            selected_format.get("format_id") or "",
            protocol=selected_format.get("protocol") or "",
        )
        merge_format = "mp4"

        opts = {
            **base_opts,
            "format": format_selector,
        }
        if merge_format:
            opts["merge_output_format"] = merge_format
        if subtitle:
            opts.update(_subtitle_opts(subtitle, subtitle_format))
        if include_thumbnail:
            opts["writethumbnail"] = True
        return opts

    if platform == "instagram":
        opts = {
            **base_opts,
            "format": instagram_format_selector(selected_format.get("format_id", ""), audio_only=True),
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
        }
        if subtitle:
            opts.update(_subtitle_opts(subtitle, subtitle_format))
        if include_thumbnail:
            opts["writethumbnail"] = True
        return opts

    abr = selected_format.get("abr")
    opts = {
        **base_opts,
        "format": f"bestaudio[abr<={int(abr)}]/bestaudio" if abr else "bestaudio",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": str(int(abr)) if abr else "192",
            }
        ],
    }
    if subtitle:
        opts.update(_subtitle_opts(subtitle, subtitle_format))
    if include_thumbnail:
        opts["writethumbnail"] = True
    return opts


def strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def format_download_error(error: str, download_kind: str) -> str:
    from src.download.errors import classify_download_error, format_guide_markdown

    guide = classify_download_error(error, download_kind)
    return format_guide_markdown(guide)

def needs_ffmpeg_for_download(
    download_kind: str,
    platform: str,
    include_subtitles: bool = False,
) -> bool:
    if download_kind == "audio":
        return True
    if download_kind == "video" and (platform == "youtube" or include_subtitles):
        return True
    return False
