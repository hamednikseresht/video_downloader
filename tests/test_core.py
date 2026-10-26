from src.download.batch_plan import classify_batch_urls, range_needs_confirm, split_by_platform
from src.download.batch_report import write_batch_report
from src.download.formats import (
    build_output_basename,
    clean_download_title,
    closest_height,
    match_subtitle,
    preferred_audio_format,
    preferred_video_format,
    quality_note,
    sanitize_title,
)
from src.download.paths import find_file_for_media
from src.history import history_to_csv, history_to_txt
from src.platforms.detect import (
    clean_pasted_url,
    clean_pasted_url_block,
    detect_platform,
    is_instagram_profile,
    is_profile_url,
    is_youtube_playlist_or_channel,
    is_youtube_profile,
    media_id,
    merge_url_blocks,
    parse_url_lines,
    profile_listing_url,
    urls_from_file,
)
from src.platforms.instagram import instagram_format_selector
from src.queue_store import clear_queue, load_queue, save_queue
from src.subtitles.convert import vtt_to_srt


def test_detect_youtube():
    assert detect_platform("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "youtube"
    assert detect_platform("https://youtu.be/dQw4w9WgXcQ") == "youtube"
    assert detect_platform("https://www.youtube.com/shorts/abc123XYZ00") == "youtube"


def test_detect_instagram():
    assert detect_platform("https://www.instagram.com/reel/ABC123/") == "instagram"
    assert detect_platform("https://www.instagram.com/p/ABC123/") == "instagram"
    assert detect_platform("https://www.instagram.com/natgeo/") == "instagram"
    assert is_instagram_profile("https://www.instagram.com/natgeo/")
    assert not is_instagram_profile("https://www.instagram.com/reel/ABC123/")
    assert is_youtube_profile("https://www.youtube.com/@MrBeast")
    assert is_profile_url("https://www.youtube.com/@MrBeast")
    assert profile_listing_url("https://www.youtube.com/@MrBeast") == "https://www.youtube.com/@MrBeast/videos"
    assert profile_listing_url("https://www.instagram.com/natgeo").endswith("natgeo/")


def test_detect_unsupported():
    assert detect_platform("https://example.com/video") is None
    assert detect_platform("") is None


def test_parse_url_lines_dedupes():
    text = "https://youtu.be/a\n\nhttps://youtu.be/a\nhttps://youtu.be/b"
    assert parse_url_lines(text) == ["https://youtu.be/a", "https://youtu.be/b"]


def test_clean_pasted_url_strips_surrounding_text():
    text = "watch this https://www.youtube.com/watch?v=dQw4w9WgXcQ thanks"
    assert clean_pasted_url(text) == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    wrapped = "See (https://youtu.be/dQw4w9WgXcQ)."
    assert clean_pasted_url(wrapped) == "https://youtu.be/dQw4w9WgXcQ"
    assert clean_pasted_url("https://youtu.be/dQw4w9WgXcQ") == "https://youtu.be/dQw4w9WgXcQ"
    assert clean_pasted_url("not a link") == "not a link"


def test_clean_pasted_url_block_extracts_each_link():
    text = (
        "first https://youtu.be/aaa wow\n"
        "reel https://www.instagram.com/reel/ABC123/ now\n"
        "https://youtu.be/aaa"
    )
    assert clean_pasted_url_block(text) == (
        "https://youtu.be/aaa\nhttps://www.instagram.com/reel/ABC123/"
    )
    playlist = "playlist: https://www.youtube.com/playlist?list=PLtest"
    assert clean_pasted_url(playlist) == "https://www.youtube.com/playlist?list=PLtest"


def test_urls_from_text_and_csv_files():
    txt = b"see https://youtu.be/aaa thanks\nhttps://www.instagram.com/reel/ABC123/\n"
    assert urls_from_file("links.txt", txt) == [
        "https://youtu.be/aaa",
        "https://www.instagram.com/reel/ABC123/",
    ]
    csv_data = (
        "title,url\n"
        "One,https://youtu.be/aaa\n"
        "Two,watch https://www.youtube.com/watch?v=dQw4w9WgXcQ now\n"
    ).encode("utf-8")
    assert urls_from_file("links.csv", csv_data) == [
        "https://youtu.be/aaa",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    ]
    assert merge_url_blocks("https://youtu.be/aaa", ["https://youtu.be/aaa", "https://youtu.be/bbb"]) == (
        "https://youtu.be/aaa\nhttps://youtu.be/bbb"
    )


def test_playlist_detection():
    assert is_youtube_playlist_or_channel(
        "https://www.youtube.com/playlist?list=PLtest"
    )
    assert is_youtube_playlist_or_channel(
        "https://www.youtube.com/watch?v=abc&list=PLtest"
    )
    assert not is_youtube_playlist_or_channel(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    )


def test_classify_batch_urls_splits_playlists():
    text = (
        "https://youtu.be/aaa\n"
        "https://www.youtube.com/playlist?list=PLtest\n"
        "https://www.instagram.com/reel/ABC123/"
    )
    plan = classify_batch_urls(text)
    assert plan["videos"] == [
        "https://youtu.be/aaa",
        "https://www.instagram.com/reel/ABC123/",
    ]
    assert plan["playlists"] == ["https://www.youtube.com/playlist?list=PLtest"]
    assert range_needs_confirm(50, 10)
    assert range_needs_confirm(12, 21)
    assert not range_needs_confirm(12, 10)
    grouped = split_by_platform(plan["videos"])
    assert grouped["youtube"] == ["https://youtu.be/aaa"]
    assert grouped["instagram"] == ["https://www.instagram.com/reel/ABC123/"]


def test_history_export_and_queue_file():
    entries = [
        {
            "title": "Demo",
            "url": "https://youtu.be/aaa",
            "kind": "video",
            "platform": "youtube",
            "filepath": "downloads/demo.mp4",
            "timestamp": "2026-09-24T11:00:00",
        }
    ]
    csv_text = history_to_csv(entries)
    txt_text = history_to_txt(entries)
    assert "title,url,kind,platform,file,time" in csv_text
    assert "https://youtu.be/aaa" in csv_text
    assert "Demo\thttps://youtu.be/aaa\tvideo" in txt_text

    import os
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "queue.json")
        save_queue(path, {"index": 1, "urls": ["https://youtu.be/aaa"]})
        assert load_queue(path)["index"] == 1
        clear_queue(path)
        assert load_queue(path) is None


def test_instagram_audio_and_short_names():
    chosen = instagram_format_selector("dash-1080", height=1080)
    assert chosen.startswith("best[height<=1080][ext=mp4]")
    assert "dash-1080" in chosen
    assert "+bestaudio" not in chosen
    assert chosen.endswith("/best")
    batch = instagram_format_selector("bestvideo[height<=720][ext=mp4]")
    assert "best[height<=720]" in batch
    assert batch.endswith("/best")
    assert "bestvideo" not in batch
    title = clean_download_title(
        "https://www.instagram.com/reel/ABC123xy/?stkn=zzzz",
        "https://www.instagram.com/reel/ABC123xy/",
        "Jane Doe",
    )
    assert "http" not in title.lower()
    assert "ABC123xy" in title
    assert "Jane Doe" in title


def test_batch_html_report_includes_status_and_error():
    import os

    path = write_batch_report(
        [
            {"url": "https://example.com/a", "title": "Good clip", "status": "ok", "filepath": "a.mp4"},
            {"url": "https://example.com/b", "title": "<script>", "status": "error", "error": "No video formats found"},
        ],
        {"kind": "batch", "title": "Batch 2026-09-24_12-20-45"},
        report_name="2026-09-24_12-20-45",
    )
    assert os.path.basename(path) == "2026-09-24_12-20-45.html"
    try:
        text = open(path, encoding="utf-8").read()
    finally:
        os.remove(path)
    assert "Saved" in text
    assert "Failed" in text
    assert "No video formats found" in text
    assert "<script>" not in text
    assert "&lt;script&gt;" in text


def test_media_id_names_and_folder_match():
    assert media_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert media_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert media_id("https://www.instagram.com/reel/ABC123/") == "ABC123"
    name = build_output_basename(
        "Hello",
        {"height": 720, "fps": 0},
        True,
        uploader="Channel",
        index=2,
        video_id="dQw4w9WgXcQ",
        stamp="20260924",
    )
    assert name.startswith("002_Channel_20260924_Hello_720p_dQw4w9WgXcQ")
    chosen, note = match_subtitle(
        [{"lang": "fa", "source": "auto", "label": "Persian"}],
        {"lang": "en", "source": "auto"},
    )
    assert chosen["lang"] == "fa"
    assert "not available" in note
    assert closest_height(1080, [360, 720]) == 720
    assert closest_height(360, [720, 1080]) == 720
    assert "Using 720p" in quality_note(1080, [360, 720])
    import os
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "002_Hello_720p_dQw4w9WgXcQ.mp4")
        open(path, "w", encoding="utf-8").write("x")
        assert find_file_for_media(tmp, "dQw4w9WgXcQ") == path
        titled = os.path.join(tmp, "My_Video_Title_720p.mp4")
        open(titled, "w", encoding="utf-8").write("x")
        from src.download.paths import find_saved_download
        assert find_saved_download(tmp, "https://youtu.be/otherid99", "My Video Title") == titled


def test_sanitize_title_unicode_and_length():
    assert sanitize_title("Hello / World!") == "Hello_World"
    assert sanitize_title("ویدیو فارسی") == "download"
    assert sanitize_title("از تنگه_cPPg-SakP5E") == "cPPg-SakP5E"
    long = "a" * 200
    assert len(sanitize_title(long)) <= 120


def test_partial_looks_broken():
    from src.download.paths import partial_looks_broken

    assert partial_looks_broken(r"C:\tmp\video.mp4.part-Frag1.part")
    assert partial_looks_broken("عنوان_720p.mp4.part")
    assert not partial_looks_broken(r"C:\tmp\video_720p.mp4.part")


def test_youtube_selector_prefers_progressive():
    from src.platforms.youtube import progressive_fallback_selector, video_format_selector

    selector = video_format_selector(720, "95", protocol="m3u8")
    assert selector.startswith("best[height<=720][protocol^=http][protocol!*=m3u8]")
    assert "95" in selector
    progressive = video_format_selector(360, "18", protocol="https")
    assert progressive.startswith("18/")
    fallback = progressive_fallback_selector(0)
    assert "18" in fallback
    assert "m3u8" in fallback


def test_pick_default_prefers_progressive():
    from src.download.formats import pick_default_video_format

    formats = [
        {"format_id": "95", "height": 720, "label": "720p · stream", "protocol": "m3u8"},
        {"format_id": "18", "height": 360, "label": "360p", "protocol": "https"},
    ]
    picked = pick_default_video_format(formats, 720)
    assert picked["format_id"] == "18"


def test_preferred_formats():
    video = preferred_video_format(720)
    assert video["height"] == 720
    assert "720" in video["format_id"]
    audio = preferred_audio_format(192)
    assert audio["abr"] == 192


def test_vtt_to_srt():
    vtt = """WEBVTT

00:00:01.000 --> 00:00:03.000 align:start
Hello <b>world</b>

00:00:04.000 --> 00:00:05.500
Second line
"""
    srt = vtt_to_srt(vtt)
    assert "00:00:01,000 --> 00:00:03,000" in srt
    assert "Hello world" in srt
    assert "WEBVTT" not in srt
    assert "<b>" not in srt
