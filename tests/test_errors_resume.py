from src.download.errors import classify_download_error, pauses_queue
from src.download.paths import find_partial_download
import os
import tempfile


def test_classify_bot_and_ffmpeg():
    bot = classify_download_error("Sign in to confirm you're not a bot")
    assert bot.actions and "open_cookies" in bot.actions
    ff = classify_download_error("ffmpeg not found", "video")
    assert "install_ffmpeg" in ff.actions
    rate = classify_download_error("HTTP Error 429: Too Many Requests")
    assert "wait" in rate.actions or "retry" in rate.actions
    assert pauses_queue(bot)
    assert pauses_queue(ff)
    assert pauses_queue(rate)
    unsupported = classify_download_error("Unsupported URL")
    assert not pauses_queue(unsupported)
    win = classify_download_error("Unable to download video: [Errno 22] Invalid argument")
    assert "Windows" in win.title or "quality" in win.title.lower()
    assert "retry" in win.actions


def test_find_partial_download():
    with tempfile.TemporaryDirectory() as tmp:
        part = os.path.join(tmp, "MyVideo_720p.mp4.part")
        open(part, "w", encoding="utf-8").write("x")
        found = find_partial_download(tmp, "MyVideo_720p")
        assert found == part
        assert find_partial_download(tmp, "Other") is None
