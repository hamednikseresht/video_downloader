"""Bundle finished downloads into zip parts small enough to send through the browser."""

from __future__ import annotations

import os
import zipfile

# Streamlit holds a served file in memory, so keep each part modest.
PART_LIMIT_BYTES = 300 * 1024 * 1024


def plan_parts(files: list[tuple[str, int]], limit: int = PART_LIMIT_BYTES) -> list[list[str]]:
    """Group (path, size) pairs into parts that stay under `limit` (a bigger file gets its own part)."""
    parts: list[list[str]] = []
    current: list[str] = []
    used = 0
    for path, size in files:
        if current and used + size > limit:
            parts.append(current)
            current, used = [], 0
        current.append(path)
        used += size
    if current:
        parts.append(current)
    return parts


def build_zip_parts(paths: list[str], dest_dir: str, base: str, limit: int = PART_LIMIT_BYTES) -> list[str]:
    """Write `<base>-part1.zip` ... into dest_dir. Videos are already compressed, so store them."""
    existing = [p for p in paths if p and os.path.isfile(p)]
    sized = [(p, os.path.getsize(p)) for p in existing]
    parts = plan_parts(sized, limit)
    os.makedirs(dest_dir, exist_ok=True)
    out: list[str] = []
    for number, members in enumerate(parts, start=1):
        zip_path = os.path.join(dest_dir, f"{base}-part{number}.zip")
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
            seen: set[str] = set()
            for member in members:
                name = os.path.basename(member)
                if name in seen:
                    name = f"{number}_{name}"
                seen.add(name)
                archive.write(member, arcname=name)
        out.append(zip_path)
    return out
