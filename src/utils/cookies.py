"""YouTube / Instagram authentication via cookies file or browser."""

from __future__ import annotations

import os

from src.constants import DEFAULT_COOKIES_FILE

BROWSER_COOKIE_CHOICES: list[tuple[str, str]] = [
    ("", "None"),
    ("firefox", "Mozilla Firefox (often works while Edge/Chrome are open)"),
    ("edge", "Microsoft Edge"),
    ("chrome", "Google Chrome"),
    ("brave", "Brave"),
]


def resolve_cookiefile(settings: dict) -> str | None:
    from src.security import sanitize_cookies_path

    path = sanitize_cookies_path(settings.get("cookies_path") or DEFAULT_COOKIES_FILE)
    if path and os.path.isfile(path):
        return os.path.abspath(path)
    return None


def resolve_cookies_from_browser(settings: dict) -> str | None:
    from src.security import sanitize_browser_choice

    return sanitize_browser_choice(settings.get("cookies_from_browser") or "") or None


def get_auth_cache_key(settings: dict) -> str:
    browser = resolve_cookies_from_browser(settings) or ""
    cookiefile = resolve_cookiefile(settings) or ""
    return f"{browser}|{cookiefile}"


def parse_auth_cache_key(auth_key: str) -> tuple[str | None, str | None]:
    if "|" not in auth_key:
        return None, auth_key or None
    browser, _, cookiefile = auth_key.partition("|")
    return (browser or None, cookiefile or None)


def apply_auth_to_ydl_opts(
    opts: dict,
    cookiefile: str | None = None,
    cookies_from_browser: str | None = None,
) -> dict:
    browser = (cookies_from_browser or "").strip().lower()
    if browser:
        opts["cookiesfrombrowser"] = (browser,)
    elif cookiefile and os.path.isfile(cookiefile):
        opts["cookiefile"] = cookiefile
    return opts


def auth_from_settings(settings: dict) -> tuple[str | None, str | None]:
    browser = resolve_cookies_from_browser(settings)
    if browser:
        return browser, None
    return None, resolve_cookiefile(settings)


def auth_from_cache_key(auth_key: str) -> tuple[str | None, str | None]:
    browser, cookiefile = parse_auth_cache_key(auth_key)
    if browser:
        return browser, None
    return None, cookiefile


def is_youtube_bot_error(error: str) -> bool:
    text = error.lower()
    return (
        "sign in to confirm" in text
        or "not a bot" in text
        or "cookies-from-browser" in text
        or "use --cookies" in text
    )


def is_cookie_read_error(error: str) -> bool:
    text = (error or "").lower()
    cookieish = "cookie" in text or "cookies database" in text or "browser profile" in text
    if not cookieish:
        return False
    return (
        ("could not copy" in text and "cookie" in text)
        or ("could not find" in text and "cookies database" in text)
        or ("errno 22" in text and "invalid argument" in text)
    )


def materialize_browser_cookies(browser: str, dest_path: str) -> str | None:
    """Copy browser cookies to a Netscape file once so later jobs do not re-open the DB."""
    import yt_dlp

    browser = (browser or "").strip().lower()
    if not browser:
        return None
    folder = os.path.dirname(dest_path) or "."
    os.makedirs(folder, exist_ok=True)
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "cookiesfrombrowser": (browser,),
        "cookiefile": dest_path,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            _ = list(ydl.cookiejar)
    except Exception:
        if os.path.isfile(dest_path) and os.path.getsize(dest_path) > 0:
            return os.path.abspath(dest_path)
        return None
    if os.path.isfile(dest_path) and os.path.getsize(dest_path) > 0:
        return os.path.abspath(dest_path)
    return None


def auth_for_batch(settings: dict, batch_dir: str) -> tuple[str | None, str | None]:
    """Prefer a one-shot cookie file under the batch folder over live browser reads."""
    browser = resolve_cookies_from_browser(settings)
    if browser:
        dest = os.path.join(batch_dir, f"cookies-{browser}.txt")
        path = materialize_browser_cookies(browser, dest)
        if path:
            return None, path
        return browser, None
    return None, resolve_cookiefile(settings)


def format_cookie_read_help(error: str = "") -> str:
    return (
        "**Could not read browser cookies.** The browser profile is locked or not installed.\n\n"
        "**Try this:**\n"
        "1. **Close the browser completely** (all windows), then **Refresh** the video URL.\n"
        "2. Pick a different browser you use for YouTube — **Firefox** often works while Edge/Chrome are open.\n"
        "3. Or upload a **`cookies.txt`** file instead (see sidebar → **YouTube cookies**).\n\n"
        "See [yt-dlp issue #7271](https://github.com/yt-dlp/yt-dlp/issues/7271) for details."
        + (f"\n\n`{error.strip()}`" if error else "")
    )


def format_youtube_auth_help(error: str = "") -> str:
    return (
        "**YouTube bot check** — YouTube wants a signed-in session for this video.\n\n"
        "**Fix (sidebar → Settings → YouTube cookies):**\n"
        "1. Set **Use browser cookies** to the browser where you are **logged into YouTube** "
        "(Firefox, Microsoft Edge, or Chrome).\n"
        "2. Click **Save**, then click **Refresh** on the video URL.\n"
        "3. If cookie read fails, **close that browser completely** and refresh again.\n\n"
        "**Or upload cookies.txt:**\n"
        "Export Netscape-format cookies while logged into YouTube "
        "(see [yt-dlp cookie guide](https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies)).\n\n"
        "**Tips:**\n"
        "- Firefox is often easiest when Edge/Chrome are still running.\n"
        "- Close other apps using the browser profile if cookie read fails.\n"
        + (f"\n`{error.strip()}`" if error else "")
    )
