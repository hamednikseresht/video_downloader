from src import env


def test_load_dotenv_parses_and_respects_real_env(tmp_path, monkeypatch):
    f = tmp_path / ".env"
    f.write_text('# c\nYTDL_A=1\nexport YTDL_B="two words"\nYTDL_C=from_file\n', encoding="utf-8")
    monkeypatch.setattr(env, "_loaded", False)
    monkeypatch.setenv("YTDL_C", "from_env")
    monkeypatch.delenv("YTDL_A", raising=False)
    monkeypatch.delenv("YTDL_B", raising=False)
    env.load_dotenv(str(f))
    import os

    assert os.environ["YTDL_A"] == "1"
    assert os.environ["YTDL_B"] == "two words"
    assert os.environ["YTDL_C"] == "from_env"
    monkeypatch.delenv("YTDL_A")
    monkeypatch.delenv("YTDL_B")


def test_env_overrides_only_set_keys(monkeypatch):
    monkeypatch.setattr(env, "_loaded", True)
    for n in ("YTDL_DOWNLOAD_DIR", "YTDL_FFMPEG_PATH", "YTDL_COOKIES_PATH", "YTDL_COOKIES_BROWSER"):
        monkeypatch.delenv(n, raising=False)
    monkeypatch.setenv("YTDL_COOKIES_BROWSER", "firefox")
    monkeypatch.setenv("YTDL_BATCH_PAUSE_SEC", "bad")
    assert env.env_overrides() == {"cookies_from_browser": "firefox"}
