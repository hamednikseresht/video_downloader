import os
import tempfile

from src.constants import PROJECT_ROOT
from src.security import (
    assert_under_download_dir,
    cleanup_partial_downloads,
    is_safe_ffmpeg_path,
    is_under_directory,
    normalize_user_path,
    sanitize_browser_choice,
    sanitize_cookies_path,
)


def test_normalize_relative_under_project():
    path = normalize_user_path("downloads")
    assert path.startswith(PROJECT_ROOT)
    assert path.endswith("downloads")


def test_normalize_rejects_dotdot_escape_to_sibling():
    # Joining PROJECT_ROOT + ../outside still normalizes; product allows absolute
    # paths, but relative .. should not leave surprising unresolved segments.
    path = normalize_user_path("../outside")
    assert ".." not in path.split(os.sep)


def test_is_under_directory():
    with tempfile.TemporaryDirectory() as tmp:
        nested = os.path.join(tmp, "a", "b.txt")
        os.makedirs(os.path.dirname(nested))
        open(nested, "w", encoding="utf-8").write("x")
        assert is_under_directory(nested, tmp)
        assert not is_under_directory(tmp, nested)


def test_assert_under_download_dir_blocks_escape():
    with tempfile.TemporaryDirectory() as tmp:
        outside = os.path.join(tempfile.gettempdir(), "ytd_escape_test.txt")
        with open(outside, "w", encoding="utf-8") as fh:
            fh.write("nope")
        try:
            raised = False
            try:
                assert_under_download_dir(outside, tmp)
            except ValueError:
                raised = True
            assert raised
        finally:
            try:
                os.remove(outside)
            except OSError:
                pass


def test_sanitize_browser_and_cookies():
    assert sanitize_browser_choice("firefox") == "firefox"
    assert sanitize_browser_choice("evil") == ""
    safe = sanitize_cookies_path("cookies.txt")
    assert safe.endswith("cookies.txt")
    assert PROJECT_ROOT in safe or safe.startswith(PROJECT_ROOT)


def test_ffmpeg_path_allowlist():
    assert is_safe_ffmpeg_path("")
    assert not is_safe_ffmpeg_path("C:\\Windows\\System32\\cmd.exe")


def test_cleanup_partials():
    with tempfile.TemporaryDirectory() as tmp:
        part = os.path.join(tmp, "video.mp4.part")
        keep = os.path.join(tmp, "video.mp4")
        open(part, "w", encoding="utf-8").write("x")
        open(keep, "w", encoding="utf-8").write("y")
        removed = cleanup_partial_downloads(tmp)
        assert removed == 1
        assert not os.path.isfile(part)
        assert os.path.isfile(keep)
