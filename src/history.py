import csv
import io
import json
import os
import tempfile
import threading
import time
import uuid

from src.constants import HISTORY_FILE, PROJECT_ROOT
from src.download.paths import find_saved_download
from src.security import assert_under_download_dir, is_under_directory, real_path

_HISTORY_LOCK = threading.Lock()
_FILE_LOCK_PATH = HISTORY_FILE + ".lock"


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


class _ProcessFileLock:
    """Cross-process lock via exclusive lock-file creation."""

    def __init__(self, path: str, timeout: float = 8.0):
        self.path = path
        self.timeout = timeout
        self._fd: int | None = None

    def __enter__(self):
        deadline = time.time() + self.timeout
        while True:
            try:
                self._fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self._fd, str(os.getpid()).encode("ascii", errors="ignore"))
                return self
            except FileExistsError:
                if time.time() >= deadline:
                    # Stale lock recovery: if older than 60s, steal it.
                    try:
                        age = time.time() - os.path.getmtime(self.path)
                        if age > 60:
                            os.remove(self.path)
                            continue
                    except OSError:
                        pass
                    raise TimeoutError(f"Could not acquire history lock: {self.path}")
                time.sleep(0.05)

    def __exit__(self, exc_type, exc, tb):
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None
        try:
            os.remove(self.path)
        except OSError:
            pass
        return False


def _atomic_write_json(path: str, data) -> None:
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".history_", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


def load_history() -> list[dict]:
    if not os.path.isfile(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError, TypeError):
        return []


def save_history(entries: list[dict]) -> None:
    with _HISTORY_LOCK, _ProcessFileLock(_FILE_LOCK_PATH):
        _atomic_write_json(HISTORY_FILE, entries)


def filepath_for_storage(filepath: str, download_dir: str = "") -> str:
    """Prefer paths relative to download_dir (or project root) for portability."""
    if not filepath:
        return filepath
    abs_path = os.path.abspath(filepath)
    bases = []
    if download_dir:
        bases.append(os.path.abspath(download_dir))
    bases.append(PROJECT_ROOT)
    for base in bases:
        try:
            rel = os.path.relpath(abs_path, base)
            if not rel.startswith("..") and not os.path.isabs(rel):
                return rel.replace("\\", "/")
        except ValueError:
            continue
    return abs_path


def resolve_history_filepath(filepath: str, download_dir: str = "") -> str:
    """Resolve a history path; only return files under download_dir when set."""
    if not filepath:
        return ""

    candidates: list[str] = []
    if download_dir and not os.path.isabs(filepath):
        candidates.append(os.path.join(download_dir, filepath))
    if os.path.isabs(filepath):
        candidates.append(filepath)
    candidates.append(os.path.join(PROJECT_ROOT, filepath))
    candidates.append(filepath)

    for path in candidates:
        try:
            if not os.path.isfile(path):
                continue
            abs_path = real_path(path)
            if download_dir and not is_under_directory(abs_path, download_dir):
                continue
            return abs_path
        except OSError:
            continue
    return ""


def add_history_entry(
    url: str,
    title: str,
    filepath: str,
    kind: str,
    platform: str = "youtube",
    download_dir: str = "",
) -> dict:
    abs_path = ""
    size = 0
    if filepath:
        try:
            if download_dir:
                abs_path = assert_under_download_dir(filepath, download_dir)
            else:
                abs_path = real_path(filepath)
            size = os.path.getsize(abs_path) if os.path.isfile(abs_path) else 0
        except (OSError, ValueError):
            abs_path = os.path.abspath(filepath)

    stored_path = filepath_for_storage(abs_path, download_dir) if abs_path else filepath
    entry = {
        "id": uuid.uuid4().hex[:12],
        "url": url,
        "title": title,
        "filepath": stored_path,
        "kind": kind,
        "platform": platform,
        "size": size,
        "timestamp": _now_iso(),
    }
    with _HISTORY_LOCK, _ProcessFileLock(_FILE_LOCK_PATH):
        entries = load_history()
        entries.insert(0, entry)
        _atomic_write_json(HISTORY_FILE, entries[:500])
    return entry


def _norm_url(url: str) -> str:
    return (url or "").strip().rstrip("/")


def saved_history_urls(download_dir: str) -> set[str]:
    """URLs whose saved file is still on disk."""
    found: set[str] = set()
    for entry in load_history():
        url = _norm_url(entry.get("url") or "")
        if not url:
            continue
        path = resolve_history_filepath(entry.get("filepath") or "", download_dir)
        if path and os.path.isfile(path):
            found.add(url)
    return found


def is_url_saved(download_dir: str, url: str, title: str = "", kind: str = "video") -> bool:
    cleaned = _norm_url(url)
    if cleaned and cleaned in saved_history_urls(download_dir):
        return True
    return find_saved_download(download_dir, url, title, kind) is not None


def history_to_csv(entries: list[dict]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["title", "url", "kind", "platform", "file", "time"])
    for entry in entries:
        writer.writerow(
            [
                entry.get("title") or "",
                entry.get("url") or "",
                entry.get("kind") or "",
                entry.get("platform") or "",
                entry.get("filepath") or "",
                entry.get("timestamp") or "",
            ]
        )
    return buf.getvalue()


def history_to_txt(entries: list[dict]) -> str:
    lines = ["title\turl\tkind\tplatform\tfile\ttime"]
    for entry in entries:
        lines.append(
            "\t".join(
                [
                    entry.get("title") or "",
                    entry.get("url") or "",
                    entry.get("kind") or "",
                    entry.get("platform") or "",
                    entry.get("filepath") or "",
                    entry.get("timestamp") or "",
                ]
            )
        )
    return "\n".join(lines) + "\n"


def delete_history_entry(entry_id: str) -> bool:
    with _HISTORY_LOCK, _ProcessFileLock(_FILE_LOCK_PATH):
        entries = load_history()
        new_entries = [e for e in entries if e.get("id") != entry_id]
        if len(new_entries) == len(entries):
            return False
        _atomic_write_json(HISTORY_FILE, new_entries)
    return True


def clear_history_filepath(entry_id: str) -> bool:
    """Mark file as deleted but keep the history row."""
    with _HISTORY_LOCK, _ProcessFileLock(_FILE_LOCK_PATH):
        entries = load_history()
        changed = False
        for entry in entries:
            if entry.get("id") == entry_id:
                entry["filepath"] = ""
                entry["size"] = 0
                changed = True
                break
        if changed:
            _atomic_write_json(HISTORY_FILE, entries)
        return changed


def delete_history_file(entry: dict, delete_file: bool = False, download_dir: str = "") -> bool:
    if delete_file and entry.get("filepath") and download_dir:
        path = resolve_history_filepath(entry["filepath"], download_dir)
        if path:
            try:
                assert_under_download_dir(path, download_dir)
                os.remove(path)
            except (OSError, ValueError):
                pass
    return delete_history_entry(entry["id"])
