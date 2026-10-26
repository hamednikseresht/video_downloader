"""Persist an in-progress batch or playlist job across refreshes."""

import json
import os

from src.history import _atomic_write_json


def load_queue(path: str) -> dict | None:
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict) or "index" not in data:
        return None
    return data


def save_queue(path: str, job: dict) -> None:
    _atomic_write_json(path, job)


def clear_queue(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def restore_queue(state: dict, key: str, path: str) -> None:
    if state.get(key):
        return
    job = load_queue(path)
    if job:
        state[key] = job
