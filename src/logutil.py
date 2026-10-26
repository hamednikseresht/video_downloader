"""Lightweight app logging — all modules share one file handler."""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

from src.constants import PROJECT_ROOT

_CONFIGURED = False
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
LOG_FILE = os.path.join(LOG_DIR, "app.log")
_ROOT_NAME = "ytd"


def _configure_root() -> logging.Logger:
    global _CONFIGURED
    root = logging.getLogger(_ROOT_NAME)
    if _CONFIGURED and root.handlers:
        return root

    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    root.addHandler(stream)

    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=2_000_000,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError as exc:
        stream.write = stream.stream.write  # noqa: keep console at least
        root.warning("Could not open log file %s: %s", LOG_FILE, exc)

    _CONFIGURED = True
    return root


def get_logger(name: str = "ytd") -> logging.Logger:
    """Return a child logger that always writes to logs/app.log."""
    root = _configure_root()
    if not name or name in (_ROOT_NAME, "ytd"):
        return root
    # Strip accidental ytd. prefix so ytd.download stays one level deep.
    short = name[len(_ROOT_NAME) + 1 :] if name.startswith(_ROOT_NAME + ".") else name
    child = logging.getLogger(f"{_ROOT_NAME}.{short}")
    child.setLevel(logging.INFO)
    child.propagate = True
    return child


def read_log_tail(limit: int = 80) -> str:
    if not os.path.isfile(LOG_FILE):
        return ""
    try:
        with open(LOG_FILE, encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError:
        return ""
    return "".join(lines[-limit:])
