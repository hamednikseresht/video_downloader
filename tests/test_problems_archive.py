import os
import zipfile

from src.download.archive import build_zip_parts, plan_parts
from src.download.batch_report import write_batch_report
from src.download.problems import classify_problem, group_problems, is_hopeless, problems_text

EMPTY = "ERROR: [Instagram] X: Instagram sent an empty media response. Check if this post is accessible"
RESTRICTED = "ERROR: [Instagram] X: This content isn't available to everyone: It can't be seen by certain audiences."
NOVIDEO = "ERROR: [Instagram] X: No video formats found!"


def test_classification_of_real_errors():
    assert classify_problem(EMPTY).code == "empty_response"
    assert classify_problem(RESTRICTED).code == "restricted"
    assert classify_problem(NOVIDEO).code == "no_video"
    assert classify_problem("HTTP Error 429: Too Many Requests").code == "rate_limit"
    assert classify_problem("[Errno 22] Invalid argument").code == "windows_path"
    assert classify_problem("something odd").code == "unknown"


def test_hopeless_errors_are_not_retried_but_transient_ones_are():
    assert is_hopeless(EMPTY) and is_hopeless(RESTRICTED) and is_hopeless(NOVIDEO)
    assert not is_hopeless("HTTP Error 429")
    assert not is_hopeless("[Errno 22] Invalid argument")
    assert not is_hopeless("totally unknown failure")


def _results():
    return [
        {"url": "u1", "title": "a", "status": "ok", "platform": "instagram"},
        {"url": "u2", "title": "b", "status": "error", "error": NOVIDEO, "platform": "instagram"},
        {"url": "u3", "title": "c", "status": "error", "error": NOVIDEO, "platform": "instagram"},
        {"url": "u4", "title": "d", "status": "error", "error": EMPTY, "platform": "instagram"},
    ]


def test_group_problems_orders_by_count_and_text_lists_every_link():
    groups = group_problems(_results())
    assert [g["problem"].code for g in groups] == ["no_video", "empty_response"]
    text = problems_text(_results(), "Batch x", "2026-01-01 00:00:00")
    for url in ("u2", "u3", "u4"):
        assert url in text
    assert "failed 3" in text


def test_report_writes_html_and_problem_text(tmp_path):
    path = write_batch_report(_results(), {"title": "T"}, dest_dir=str(tmp_path), report_name="b1")
    assert "Problems" in open(path, encoding="utf-8").read()
    assert (tmp_path / "b1-problems.txt").is_file()


def test_plan_parts_and_zip(tmp_path):
    assert plan_parts([("a", 5), ("b", 5), ("c", 5)], limit=10) == [["a", "b"], ["c"]]
    assert plan_parts([("big", 99)], limit=10) == [["big"]]
    files = []
    for name in ("one.mp4", "two.mp4", "three.mp4"):
        f = tmp_path / name
        f.write_bytes(b"x" * 10)
        files.append(str(f))
    zips = build_zip_parts(files, str(tmp_path / "out"), "b", limit=20)
    assert len(zips) == 2
    names = [n for z in zips for n in zipfile.ZipFile(z).namelist()]
    assert sorted(names) == ["one.mp4", "three.mp4", "two.mp4"]
    assert build_zip_parts([str(tmp_path / "missing.mp4")], str(tmp_path / "o2"), "b") == []
