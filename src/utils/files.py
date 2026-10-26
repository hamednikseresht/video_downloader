import os
import subprocess


def open_folder(path: str) -> bool:
    path = os.path.abspath(path)
    if not os.path.isdir(path):
        return False
    try:
        if os.name == "nt":
            os.startfile(path)  # noqa: S606
        elif os.uname().sysname == "Darwin":
            subprocess.run(["open", path], check=False)
        else:
            subprocess.run(["xdg-open", path], check=False)
        return True
    except OSError:
        return False


def read_clipboard_text() -> str:
    """Read text from the OS clipboard. The app runs locally, so the server clipboard is the user's."""
    if os.name == "nt":
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
                capture_output=True,
                timeout=8,
                check=False,
            )
            return out.stdout.decode("utf-8", errors="replace")
        except (OSError, subprocess.SubprocessError):
            return ""
    try:
        import tkinter

        root = tkinter.Tk()
        root.withdraw()
        try:
            return root.clipboard_get()
        finally:
            root.destroy()
    except Exception:
        return ""

