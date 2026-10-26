import csv
import io
import re

YOUTUBE_URL_RE = re.compile(
    r"(?:https?://)?(?:\w+\.)?(?:youtube\.com/(?:watch\?(?:[^&]*&)*v=|shorts/|embed/|live/|playlist\?|channel/|@)|youtu\.be/)",
    re.I,
)
INSTAGRAM_URL_RE = re.compile(
    r"(?:https?://)?(?:\w+\.)?instagram\.com/(?:"
    r"(?:[\w.-]+/)?(?:p|reel|reels|tv)/[\w-]+|"
    r"stories/[\w.-]+/\d+|"
    r"share/(?:p|reel)/[\w-]+|"
    r"(?!p/|reel/|reels/|tv/|stories/|share/|explore/|accounts/|reel/audio)"
    r"[\w.]{2,}/?"
    r")",
    re.I,
)

_IG_RESERVED = {
    "p",
    "reel",
    "reels",
    "tv",
    "stories",
    "share",
    "explore",
    "accounts",
    "about",
    "legal",
    "developer",
    "directory",
}


def media_id(url: str) -> str:
    """Stable id used in filenames so a file can be matched after history is cleared."""
    text = (url or "").strip()
    if not text:
        return ""
    watch = re.search(r"[?&]v=([\w-]{6,})", text, re.I)
    if watch:
        return watch.group(1)
    short = re.search(r"youtu\.be/([\w-]{6,})", text, re.I)
    if short:
        return short.group(1)
    kind = re.search(r"/(?:shorts|embed|live)/([\w-]{6,})", text, re.I)
    if kind:
        return kind.group(1)
    ig = re.search(r"instagram\.com/(?:[\w.-]+/)?(?:p|reel|reels|tv)/([\w-]+)", text, re.I)
    if ig:
        return ig.group(1)
    share = re.search(r"instagram\.com/share/(?:p|reel)/([\w-]+)", text, re.I)
    if share:
        return share.group(1)
    return ""


def detect_platform(url: str) -> str | None:
    cleaned = url.strip()
    if not cleaned:
        return None
    if YOUTUBE_URL_RE.search(cleaned):
        return "youtube"
    if INSTAGRAM_URL_RE.search(cleaned):
        return "instagram"
    return None


_MEDIA_URL_RE = re.compile(
    r"(?:https?://)?(?:[\w-]+\.)?(?:youtube\.com|youtu\.be|instagram\.com)/\S+",
    re.I,
)
_TRAILING_URL_JUNK = ".,);:!?]>\"'`»"


def _trim_url_token(token: str) -> str:
    token = token.strip().strip("<>()[]{}\"'`")
    while token and token[-1] in _TRAILING_URL_JUNK:
        token = token[:-1]
    return normalize_media_url(token.rstrip())


def normalize_media_url(url: str) -> str:
    """Drop share tokens and other query noise that break Windows downloads."""
    text = (url or "").strip()
    if not text:
        return ""
    if "instagram.com" in text.lower():
        base = text.split("#", 1)[0]
        if "?" in base:
            path, _, query = base.partition("?")
            keep = []
            for part in query.split("&"):
                key = part.split("=", 1)[0].lower()
                if key == "img_index":
                    keep.append(part)
            base = f"{path}?{'&'.join(keep)}" if keep else path
        return base.rstrip("/") + "/"
    return text.split("#", 1)[0].rstrip()


def extract_urls(text: str) -> list[str]:
    """Pull YouTube and Instagram links out of pasted text."""
    seen: set[str] = set()
    urls: list[str] = []
    for match in _MEDIA_URL_RE.finditer(text or ""):
        url = _trim_url_token(match.group(0))
        if url and url not in seen and detect_platform(url):
            seen.add(url)
            urls.append(url)
    return urls


def clean_pasted_url(text: str) -> str:
    """Return the first media URL in text, or the original text if none is found."""
    raw = (text or "").strip()
    if not raw:
        return ""
    found = extract_urls(raw)
    return found[0] if found else raw


def clean_pasted_url_block(text: str) -> str:
    """Turn messy pasted text into one media URL per line."""
    raw = text or ""
    if not raw.strip():
        return ""
    urls = extract_urls(raw)
    if not urls:
        return raw
    return "\n".join(urls)


def trim_url_state(state: dict, key: str, *, multiline: bool = False) -> None:
    raw = state.get(key)
    if not isinstance(raw, str) or not raw.strip():
        return
    cleaned = clean_pasted_url_block(raw) if multiline else clean_pasted_url(raw)
    if cleaned != raw:
        state[key] = cleaned


def parse_url_lines(text: str) -> list[str]:
    return extract_urls(text)


def urls_from_file(filename: str, data: bytes) -> list[str]:
    """Read YouTube and Instagram links from a .txt or .csv upload."""
    text = (data or b"").decode("utf-8-sig", errors="replace")
    name = (filename or "").lower()
    if name.endswith(".csv"):
        cells: list[str] = []
        for row in csv.reader(io.StringIO(text)):
            cells.extend(cell.strip() for cell in row if cell and cell.strip())
        text = "\n".join(cells)
    return extract_urls(text)


def merge_url_blocks(existing: str, new_urls: list[str]) -> str:
    """Append new links to an existing URL list without duplicates."""
    current = extract_urls(existing or "")
    seen = set(current)
    for url in new_urls:
        if url not in seen:
            seen.add(url)
            current.append(url)
    return "\n".join(current)


YOUTUBE_PLAYLIST_RE = re.compile(
    r"(?:youtube\.com/(?:playlist\?|channel/|@)|youtu\.be/).*"
    r"|youtube\.com/watch\?.*list=",
    re.I,
)


def is_youtube_playlist_or_channel(url: str) -> bool:
    cleaned = url.strip()
    if not cleaned or detect_platform(cleaned) != "youtube":
        return False
    if "list=" in cleaned:
        return True
    if "/playlist" in cleaned.lower():
        return True
    if "/channel/" in cleaned.lower():
        return True
    if re.search(r"youtube\.com/@[\w.-]+/?$", cleaned, re.I):
        return True
    return False


def is_instagram_profile(url: str) -> bool:
    cleaned = (url or "").strip().rstrip("/")
    match = re.search(r"instagram\.com/([^/?#]+)/?$", cleaned, re.I)
    if not match:
        return False
    name = match.group(1).lower()
    return name not in _IG_RESERVED and bool(re.fullmatch(r"[\w.]{2,}", name))


def is_youtube_profile(url: str) -> bool:
    cleaned = (url or "").strip()
    if detect_platform(cleaned) != "youtube":
        return False
    lower = cleaned.lower()
    if "list=" in lower or "/playlist" in lower:
        return False
    if re.search(r"youtube\.com/@[\w.-]+", cleaned, re.I):
        return True
    if "/channel/" in lower or "/c/" in lower or "/user/" in lower:
        return True
    return False


def is_profile_url(url: str) -> bool:
    return is_youtube_profile(url) or is_instagram_profile(url)


def profile_listing_url(url: str) -> str:
    """URL yt-dlp should open to list the newest uploads."""
    cleaned = normalize_media_url(url) if "instagram.com" in (url or "").lower() else (url or "").strip()
    if is_instagram_profile(cleaned):
        return cleaned.rstrip("/") + "/"
    if is_youtube_profile(cleaned):
        base = cleaned.split("?", 1)[0].rstrip("/")
        for suffix in ("/videos", "/shorts", "/streams", "/featured", "/playlists"):
            if base.lower().endswith(suffix):
                base = base[: -len(suffix)]
        return base + "/videos"
    return cleaned
