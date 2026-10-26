import json

from src import history


def _point_history(monkeypatch, tmp_path):
    path = tmp_path / "download_history.json"
    monkeypatch.setattr(history, "HISTORY_FILE", str(path))
    monkeypatch.setattr(history, "_FILE_LOCK_PATH", str(path) + ".lock")
    return path


def test_corrupt_history_is_backed_up_not_lost(monkeypatch, tmp_path):
    path = _point_history(monkeypatch, tmp_path)
    path.write_text("{not json", encoding="utf-8")
    assert history.load_history() == []
    assert (tmp_path / "download_history.json.corrupt.bak").read_text(encoding="utf-8") == "{not json"


def test_entries_without_id_get_stable_id_and_can_be_deleted(monkeypatch, tmp_path):
    path = _point_history(monkeypatch, tmp_path)
    path.write_text(json.dumps([{"url": "u", "title": "t", "timestamp": "x"}, "junk"]), encoding="utf-8")
    first = history.load_history()
    assert len(first) == 1 and first[0]["id"]
    assert history.load_history()[0]["id"] == first[0]["id"]
    assert history.delete_history_entry(first[0]["id"]) is True
    assert history.load_history() == []


def test_batch_file_found_under_subfolder(monkeypatch, tmp_path):
    _point_history(monkeypatch, tmp_path)
    folder = tmp_path / "dl" / "2026-01-01_00-00-00" / "instagram"
    folder.mkdir(parents=True)
    (folder / "001_abc.mp4").write_bytes(b"x")
    found = history.resolve_history_filepath("001_abc.mp4", str(tmp_path / "dl"))
    assert found.endswith("001_abc.mp4")


def test_stale_job_detection(tmp_path):
    from datetime import datetime, timedelta

    from src.ui.queue import _is_stale_job

    now = datetime.now()
    fresh = {"started_at": now.strftime("%Y-%m-%d %H:%M:%S")}
    old = {"started_at": (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")}
    gone_cookie = {**fresh, "auth_cookiefile": str(tmp_path / "missing.txt")}
    assert not _is_stale_job(fresh)
    assert _is_stale_job(old)
    assert _is_stale_job(gone_cookie)
    assert _is_stale_job({})
