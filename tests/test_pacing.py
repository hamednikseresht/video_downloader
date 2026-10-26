import random

from src.download.batch_plan import split_by_platform
from src.download.pacing import MIN_DELAY_SEC, PLATFORM_ORDER, check_delay, next_delay
from src.platforms.detect import extract_urls, merge_url_blocks


def test_instagram_group_runs_first():
    assert PLATFORM_ORDER == ("instagram", "youtube")


def test_delay_respects_floor_and_is_random():
    rng = random.Random(1)
    values = {next_delay("instagram", 1.5, rng) for _ in range(20)}
    assert min(values) >= MIN_DELAY_SEC["instagram"] * 0.75
    assert len(values) > 5
    assert next_delay("youtube", 60, rng) >= 45


def test_check_delay_instagram_longer_than_youtube():
    assert check_delay("instagram", random.Random(2)) >= 1.0
    assert check_delay("youtube") == 0.2


def test_clipboard_text_keeps_only_youtube_and_instagram():
    text = """see (https://www.instagram.com/reel/AAA/?igsh=xyz).
    https://example.com/skip https://youtu.be/BBB, https://www.youtube.com/watch?v=CCC
    https://www.instagram.com/reel/AAA/"""
    urls = extract_urls(text)
    assert all("example.com" not in u for u in urls)
    groups = split_by_platform(urls)
    assert len(groups["instagram"]) == 1
    assert len(groups["youtube"]) == 2
    merged = merge_url_blocks("", urls).splitlines()
    assert len(merged) == len(set(merged)) == 3
