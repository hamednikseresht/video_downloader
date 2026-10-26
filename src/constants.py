import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DOWNLOAD_DIR = os.path.join(PROJECT_ROOT, "downloads")
SETTINGS_FILE = os.path.join(PROJECT_ROOT, "settings.json")
DEFAULT_COOKIES_FILE = os.path.join(PROJECT_ROOT, "cookies.txt")
HISTORY_FILE = os.path.join(PROJECT_ROOT, "download_history.json")
BATCH_QUEUE_FILE = os.path.join(PROJECT_ROOT, "batch_queue.json")
PLAYLIST_QUEUE_FILE = os.path.join(PROJECT_ROOT, "playlist_queue.json")
REPORTS_DIR = os.path.join(PROJECT_ROOT, "reports")
BATCH_REPORT_FILE = os.path.join(PROJECT_ROOT, "batch_report.json")
PLAYLIST_REPORT_FILE = os.path.join(PROJECT_ROOT, "playlist_report.json")

MAX_BROWSER_DOWNLOAD_BYTES = 200 * 1024 * 1024  # 200 MB

# Bump when fetch logic changes so Streamlit drops stale cached format lists.
FETCH_CACHE_VERSION = 14

# Pause before subtitle fetch so back-to-back metadata + subtitle requests are less likely to 429.
SUBTITLE_PREFETCH_PAUSE_SEC = 2

# Pause between playlist/batch items to reduce YouTube rate limits.
BATCH_ITEM_PAUSE_SEC = 1.5

# Network timeout (seconds) so a stalled connection fails and retries instead of hanging.
SOCKET_TIMEOUT_SEC = 30

# Parallel fragment downloads for DASH/HLS (override with YTDL_FRAGMENTS, 1-16).
# The Errno 22 fallback in worker.py still drops to 1.
def _fragment_concurrency() -> int:
    from src.env import env_str

    try:
        return min(16, max(1, int(env_str("YTDL_FRAGMENTS") or 4)))
    except ValueError:
        return 4


FRAGMENT_CONCURRENCY = _fragment_concurrency()

# App version shown in UI / health.
APP_VERSION = "3.0"

# App-level download attempts (all download kinds). yt-dlp also retries fragments internally.
DOWNLOAD_TRANSIENT_RETRIES = 4

_WINDOWS_FFMPEG_PATHS = (
    os.path.expandvars(r"%LocalAppData%\Microsoft\WinGet\Links\ffmpeg.exe"),
    r"C:\ffmpeg\bin\ffmpeg.exe",
)

_WINDOWS_DENO_PATHS = (
    os.path.expandvars(r"%LocalAppData%\Microsoft\WinGet\Links\deno.exe"),
    os.path.expandvars(r"%UserProfile%\.deno\bin\deno.exe"),
)
_WINDOWS_NODE_PATHS = (
    r"C:\Program Files\nodejs\node.exe",
    os.path.expandvars(r"%ProgramFiles%\nodejs\node.exe"),
    os.path.expandvars(r"%LocalAppData%\Programs\node\node.exe"),
)
