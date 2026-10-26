#!/usr/bin/env python3
"""CLI wrapper for pre-flight health checks."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.setup.health import (  # noqa: E402
    ensure_dependencies,
    install_requirements,
    print_report,
    report_to_json,
    run_health_check,
    try_install_ffmpeg_windows,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Downloader pre-flight checks")
    parser.add_argument("--check", action="store_true", help="Run checks and print report")
    parser.add_argument("--ensure-deps", action="store_true", help="Install requirements if packages missing")
    parser.add_argument("--install-deps", action="store_true", help="Always pip install requirements")
    parser.add_argument("--install-ffmpeg", action="store_true", help="Try to install FFmpeg (Windows winget)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--quiet", action="store_true", help="Minimal output")
    args = parser.parse_args()

    if args.install_deps:
        if not args.quiet:
            print("[SETUP] Installing Python dependencies...")
        ok, msg = install_requirements()
        if not ok:
            print(f"[ERROR] {msg}", file=sys.stderr)
            return 1
        if not args.quiet:
            print(f"[OK] {msg}")
    elif args.ensure_deps:
        if not args.quiet:
            print("[SETUP] Verifying Python dependencies...")
        ok, msg = ensure_dependencies()
        if not ok:
            print(f"[ERROR] {msg}", file=sys.stderr)
            return 1
        if not args.quiet and "installed" in msg.lower():
            print(f"[OK] {msg}")

    if args.install_ffmpeg:
        ok, msg = try_install_ffmpeg_windows()
        print(msg)
        if not ok:
            return 1

    report = run_health_check()

    if args.json:
        print(report_to_json(report))
    elif not args.quiet and (args.check or args.install_deps or args.ensure_deps or args.install_ffmpeg):
        print_report(report)

    if args.check:
        return 0 if report.can_start else 1

    return 0 if report.can_start else 1


if __name__ == "__main__":
    raise SystemExit(main())
