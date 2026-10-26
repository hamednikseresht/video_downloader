import copy
import os
import re
import subprocess
import time

import yt_dlp

from src.constants import SUBTITLE_PREFETCH_PAUSE_SEC
from src.download.paths import (
    get_expected_output_path,
    resolve_subtitle_filepath,
)
from src.download.ydl import (
    get_base_ydl_opts,
    get_curl_impersonate,
    get_impersonate_target,
    get_subtitle_rate_limit_opts,
)
from src.settings import resolve_ffmpeg_location


def pick_subtitle_track(tracks: list[dict], subtitle_format: str) -> tuple[dict, str]:
    for ext in (subtitle_format, "vtt", "srv1", "srv2", "srv3", "json3", "ttml"):
        track = next((t for t in tracks if t.get("ext") == ext), None)
        if track and track.get("url"):
            return track, ext
    raise ValueError("No downloadable subtitle track found for the selected language.")


def vtt_to_srt(vtt_text: str) -> str:
    lines = []
    for raw in vtt_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("WEBVTT") or line.startswith("NOTE"):
            continue
        if "-->" in line:
            line = re.sub(r"(\d{2}:\d{2}:\d{2})\.(\d{3})", r"\1,\2", line)
            line = re.sub(r"\s+align:.*$", "", line)
            line = re.sub(r"\s+position:.*$", "", line)
        else:
            line = re.sub(r"<[^>]+>", "", line)
        lines.append(line)
    return "\n".join(lines).strip() + "\n"


def convert_subtitle_file(
    source_path: str,
    target_path: str,
    target_format: str,
    ffmpeg_path: str = "",
) -> str:
    source_ext = os.path.splitext(source_path)[1].lower().lstrip(".")
    if source_ext == target_format:
        if source_path != target_path:
            os.replace(source_path, target_path)
        return target_path

    if source_ext == "vtt" and target_format == "srt":
        with open(source_path, encoding="utf-8", errors="replace") as fh:
            srt_text = vtt_to_srt(fh.read())
        with open(target_path, "w", encoding="utf-8") as fh:
            fh.write(srt_text)
        os.remove(source_path)
        return target_path

    ffmpeg_location = resolve_ffmpeg_location(ffmpeg_path)
    if not ffmpeg_location:
        raise ValueError(
            f"Downloaded {source_ext.upper()} but FFmpeg is required to convert to "
            f"{target_format.upper()}."
        )

    ffmpeg_bin = os.path.join(
        ffmpeg_location, "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    )
    subprocess.run(
        [ffmpeg_bin, "-y", "-i", source_path, target_path],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    os.remove(source_path)
    return target_path


def fetch_subtitle_bytes(sub_url: str, ydl: yt_dlp.YoutubeDL) -> bytes:
    from urllib.parse import urlparse

    host = (urlparse(sub_url).hostname or "").lower()
    allowed_suffixes = (
        "youtube.com",
        "googlevideo.com",
        "ytimg.com",
        "ggpht.com",
        "googleusercontent.com",
    )
    if not any(host == s or host.endswith("." + s) for s in allowed_suffixes):
        raise ValueError(f"Blocked subtitle host: {host or 'unknown'}")

    impersonate = get_impersonate_target()
    if impersonate is not None:
        from yt_dlp.networking.common import Request

        response = ydl.urlopen(Request(sub_url, extensions={"impersonate": impersonate}))
        return response.read()

    from curl_cffi import requests as curl_requests

    response = curl_requests.get(sub_url, impersonate=get_curl_impersonate(), timeout=60)
    response.raise_for_status()
    return response.content


def download_subtitle_direct(
    cached_info: dict,
    subtitle: dict,
    subtitle_format: str,
    download_dir: str,
    output_basename: str,
    ffmpeg_path: str = "",
    cookiefile: str | None = None,
    cookies_from_browser: str | None = None,
) -> str:
    subs_key = "subtitles" if subtitle["source"] == "manual" else "automatic_captions"
    tracks = (cached_info.get(subs_key) or {}).get(subtitle["lang"]) or []
    track, downloaded_ext = pick_subtitle_track(tracks, subtitle_format)

    output_path = get_expected_output_path(download_dir, output_basename, subtitle_format)
    raw_path = get_expected_output_path(download_dir, output_basename, downloaded_ext)

    time.sleep(SUBTITLE_PREFETCH_PAUSE_SEC)
    ydl_opts = {
        **get_base_ydl_opts(
            cookiefile=cookiefile,
            cookies_from_browser=cookies_from_browser,
        ),
        **get_subtitle_rate_limit_opts(),
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        data = fetch_subtitle_bytes(track["url"], ydl)

    with open(raw_path, "wb") as fh:
        fh.write(data)

    if downloaded_ext == subtitle_format:
        if raw_path != output_path:
            os.replace(raw_path, output_path)
        return output_path

    return convert_subtitle_file(raw_path, output_path, subtitle_format, ffmpeg_path)


def download_subtitle_with_ytdlp(
    cached_info: dict,
    ydl_opts: dict,
    download_dir: str,
    output_basename: str,
    ext: str,
    subtitle: dict,
    ffmpeg_path: str = "",
) -> str | None:
    info = copy.deepcopy(cached_info)
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.process_ie_result(info, download=True)
        return resolve_subtitle_filepath(
            download_dir,
            output_basename,
            subtitle["lang"],
            ext,
            ffmpeg_path,
        )
