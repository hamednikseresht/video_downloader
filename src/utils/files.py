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
