# YouTube & Instagram Downloader

Local Streamlit app to download YouTube and Instagram videos, audio (MP3), subtitles, thumbnails, and playlists — with **auto setup on a new PC**, **resume**, and **guided error recovery**.

## Features

- **YouTube**: MP4 video, MP3 audio, subtitles (SRT/VTT), thumbnails  
- **Playlists / channels**: download a range at preferred quality  
- **Instagram**: public Reels, posts, IGTV (private/login content not supported)  
- **Batch queue** with Stop between items  
- **Cookies** (browser or `cookies.txt`) for bot / age checks  
- **History**: re-download, remove entries, delete files  
- **Resume**: incomplete `.part` files are kept; click Download again to continue  
- **Auto setup**: on first launch, creates folders/settings and installs what it can  
- **Guided errors**: failed downloads show steps + one-click fixes (packages / FFmpeg)

## Requirements

| Need | Notes |
|------|--------|
| **Python 3.11+** | 3.10 works with Streamlit warnings |
| **FFmpeg** | Required for merge + MP3 |
| **Node.js 22+** or **Deno 2.3+** | Optional; needed for YouTube HD |
| Internet | To fetch media |

## Quick start (Windows)

1. Double-click **`run.bat`**
2. Choose Python (`.venv` recommended) if asked  
3. Wait for health check / auto setup  
4. Open [http://localhost:8501](http://localhost:8501)

Or manually:

```bash
pip install -r requirements.txt
python scripts/healthcheck.py --check
python app.py
```

## New PC / first-run auto setup

On a machine with **no** `settings.json` yet, the app will:

1. Create the default `downloads/` folder  
2. Write default `settings.json`  
3. Install Python packages from `requirements.txt`  
4. On Windows, try `winget install Gyan.FFmpeg`  
5. Mark setup complete (`.setup_complete`)

You can also click **Fix everything** anytime in the setup screen or sidebar **Health check**.

### If something is still missing

| Problem | What the app / you should do |
|--------|------------------------------|
| Packages missing | **Install packages** or `pip install -r requirements.txt` |
| FFmpeg missing | **Install FFmpeg** (Windows winget) or set path in Settings |
| YouTube “not a bot” | Settings → cookies → browser logged into YouTube (try Firefox) |
| Only 360p | Install Node 22+ or Deno 2.3+, restart app |
| HTTP 429 | Wait 1–2 minutes; avoid rapid clicks; resume later |
| Download interrupted | Click **Start download** again — resume uses leftover `.part` files |

## Configuration / auth (.env)

Machine paths and auth live in a local `.env` (gitignored), not in `settings.json`.
Copy `.env.example` to `.env` and set what you need:

| Variable | Purpose |
|----------|---------|
| `YTDL_COOKIES_BROWSER` | `firefox` / `edge` / `chrome` / `brave` |
| `YTDL_COOKIES_PATH` | Netscape `cookies.txt` |
| `YTDL_FFMPEG_PATH` | ffmpeg binary or folder |
| `YTDL_DOWNLOAD_DIR` | Download folder |
| `YTDL_BATCH_PAUSE_SEC` | Pause between batch items |

Real environment variables win over `.env`; both win over `settings.json` and are never saved back to it.

## Resume downloads

- yt-dlp **continuedl** is enabled  
- Failed or cancelled network downloads **keep** `.part` / `.ytdl` files  
- Starting the same quality again shows **Resuming previous download…**  
- Finished files are not overwritten (`nooverwrites`)

## Project layout

```
app.py                 Entry point
run.bat                Windows launcher
.streamlit/            Theme / server config
src/
  setup/               Health checks + auto setup
  download/            Fetch, formats, worker, error guides
  ui/tabs/             Single, Playlist, History
  security.py          Path hardening
scripts/               bootstrap.bat, healthcheck.py
tests/                 Unit tests
```

Local-only (gitignored): `downloads/`, `settings.json`, `cookies.txt`, `download_history.json`, `logs/`, `.setup_complete`.

## Troubleshooting

```bash
python scripts/healthcheck.py --check
python scripts/healthcheck.py --ensure-deps
python scripts/healthcheck.py --install-ffmpeg   # Windows
pytest                                          # optional
```

### YouTube “Sign in to confirm you’re not a bot”

1. Settings → **YouTube cookies**  
2. Pick a browser where you are logged in (Firefox if Edge/Chrome fail)  
3. **Save**, then **Refresh** the URL  
4. If cookie DB is locked, **quit that browser completely** and retry  
5. Or upload a Netscape `cookies.txt`

## License / use

For personal use with content you have the right to download. Respect YouTube/Instagram terms and copyright.
