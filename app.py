import sys

# Allow `python app.py` — launch Streamlit in a child process before importing it.
if __name__ == "__main__" and "streamlit" not in sys.modules:
    import subprocess

    raise SystemExit(
        subprocess.call(
            [sys.executable, "-m", "streamlit", "run", __file__, *sys.argv[1:]]
        )
    )

from src.ui.tabs.main import run_app

run_app()
