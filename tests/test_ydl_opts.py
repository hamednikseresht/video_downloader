from src.constants import FRAGMENT_CONCURRENCY, SOCKET_TIMEOUT_SEC
from src.download.ydl import get_base_ydl_opts, get_subtitle_rate_limit_opts


def test_base_opts_have_timeout_and_fragment_concurrency():
    opts = get_base_ydl_opts()
    assert opts["socket_timeout"] == SOCKET_TIMEOUT_SEC
    assert opts["concurrent_fragment_downloads"] == FRAGMENT_CONCURRENCY
    assert 1 <= FRAGMENT_CONCURRENCY <= 16


def test_subtitle_opts_have_timeout_and_no_per_item_sleep():
    opts = get_subtitle_rate_limit_opts()
    assert opts["socket_timeout"] == SOCKET_TIMEOUT_SEC
    assert "sleep_interval" not in opts


def test_fallback_forces_single_fragment():
    from src.download.worker import _apply_format_fallback

    out = _apply_format_fallback(get_base_ydl_opts(), 0)
    assert out["concurrent_fragment_downloads"] == 1
