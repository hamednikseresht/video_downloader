from src.queue_store import clear_queue, load_queue, restore_queue, save_queue


def test_queue_roundtrip_and_clear(tmp_path):
    path = str(tmp_path / "q.json")
    assert load_queue(path) is None
    save_queue(path, {"index": 2, "items": [1]})
    assert load_queue(path) == {"index": 2, "items": [1]}
    clear_queue(path)
    assert load_queue(path) is None


def test_queue_rejects_corrupt_and_malformed(tmp_path):
    path = tmp_path / "q.json"
    path.write_text("{bad", encoding="utf-8")
    assert load_queue(str(path)) is None
    path.write_text('{"no_index": 1}', encoding="utf-8")
    assert load_queue(str(path)) is None


def test_restore_queue_does_not_overwrite_existing(tmp_path):
    path = str(tmp_path / "q.json")
    save_queue(path, {"index": 1})
    state = {"job": {"index": 9}}
    restore_queue(state, "job", path)
    assert state["job"] == {"index": 9}
    state = {}
    restore_queue(state, "job", path)
    assert state["job"] == {"index": 1}
