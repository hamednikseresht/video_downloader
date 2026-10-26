"""Plan a batch or playlist run before it starts."""

from src.platforms.detect import detect_platform, is_youtube_playlist_or_channel, parse_url_lines

LARGE_PLAYLIST_COUNT = 50
CONFIRM_RANGE_COUNT = 20

SUBTITLE_LANGS = (
    ("en", "English"),
    ("es", "Spanish"),
    ("fr", "French"),
    ("de", "German"),
    ("fa", "Persian"),
    ("ar", "Arabic"),
    ("hi", "Hindi"),
    ("pt", "Portuguese"),
    ("ru", "Russian"),
    ("ja", "Japanese"),
)


def split_by_platform(urls: list[str]) -> dict[str, list[str]]:
    grouped = {"youtube": [], "instagram": []}
    for url in urls:
        platform = detect_platform(url)
        if platform in grouped:
            grouped[platform].append(url)
    return grouped


def classify_batch_urls(text: str) -> dict[str, list[str]]:
    videos: list[str] = []
    playlists: list[str] = []
    for url in parse_url_lines(text):
        if is_youtube_playlist_or_channel(url):
            playlists.append(url)
        elif detect_platform(url):
            videos.append(url)
    return {"videos": videos, "playlists": playlists}


def subtitle_choice(lang: str, source: str) -> dict:
    kind = "auto" if source == "auto" else "manual"
    return {"lang": lang, "source": kind, "label": f"{lang} ({kind})"}


def range_needs_confirm(total: int, selected: int) -> bool:
    return total >= LARGE_PLAYLIST_COUNT or selected > CONFIRM_RANGE_COUNT
