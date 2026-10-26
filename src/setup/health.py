"""Requirements and system health checks (shared by CLI and Streamlit)."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from src.constants import PROJECT_ROOT

REQUIREMENTS_FILE = Path(PROJECT_ROOT) / "requirements.txt"
MIN_PYTHON = (3, 10)
RECOMMENDED_PYTHON = (3, 11)

REQUIRED_PACKAGES = (
    ("streamlit", "streamlit"),
    ("yt_dlp", "yt-dlp"),
    ("curl_cffi", "curl_cffi"),
)


@dataclass
class CheckResult:
    name: str
    status: str  # ok | warn | fail
    message: str
    fix: str = ""


@dataclass
class HealthReport:
    python_version: str
    runtime: str
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def can_start(self) -> bool:
        return not any(c.status == "fail" for c in self.checks)

    @property
    def has_warnings(self) -> bool:
        return any(c.status == "warn" for c in self.checks)


def _python_version_ok() -> tuple[bool, str]:
    v = sys.version_info
    label = f"{v.major}.{v.minor}.{v.micro}"
    ok = (v.major, v.minor) >= MIN_PYTHON
    return ok, label


def _module_installed(import_name: str) -> bool:
    return importlib.util.find_spec(import_name) is not None


def check_python() -> CheckResult:
    ok, label = _python_version_ok()
    v = sys.version_info
    if not ok:
        return CheckResult(
            "python",
            "fail",
            f"Python {label} is too old (need {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+)",
            fix=(
                "Install Python 3.11+ from https://www.python.org/downloads/ "
                'and enable "Add python.exe to PATH".'
            ),
        )
    if (v.major, v.minor) < RECOMMENDED_PYTHON:
        return CheckResult(
            "python",
            "warn",
            f"Python {label} works but Streamlit recommends 3.11+ (you may see deprecation notices)",
            fix=(
                "Upgrade: recreate .venv with Python 3.11+, or run "
                "conda install -n youtube-downloader python=3.12"
            ),
        )
    return CheckResult("python", "ok", f"Python {label}")


def check_packages() -> list[CheckResult]:
    results = []
    for import_name, label in REQUIRED_PACKAGES:
        if _module_installed(import_name):
            results.append(CheckResult(f"package_{import_name}", "ok", f"{label} installed"))
        elif import_name == "curl_cffi":
            results.append(
                CheckResult(
                    f"package_{import_name}",
                    "warn",
                    f"{label} not installed (subtitle rate-limit protection reduced)",
                    fix='Run: pip install "yt-dlp[default,curl-cffi]" curl_cffi',
                )
            )
        else:
            results.append(
                CheckResult(
                    f"package_{import_name}",
                    "fail",
                    f"{label} not installed",
                    fix=f"Run: pip install -r requirements.txt  (from {PROJECT_ROOT})",
                )
            )
    return results


def check_ffmpeg() -> CheckResult:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return CheckResult("ffmpeg", "ok", f"FFmpeg found ({ffmpeg})")

    win_paths = (
        os.path.expandvars(r"%LocalAppData%\Microsoft\WinGet\Links\ffmpeg.exe"),
        r"C:\ffmpeg\bin\ffmpeg.exe",
    )
    for path in win_paths:
        if os.path.isfile(path):
            return CheckResult("ffmpeg", "ok", f"FFmpeg found ({path})")

    fix_lines = [
        "FFmpeg is required for video+audio merge and MP3 conversion.",
        "Windows: winget install Gyan.FFmpeg",
        "Or: winget install ffmpeg",
        "Or download: https://ffmpeg.org/download.html",
        "Then add ffmpeg to PATH or set the path in app Settings.",
    ]
    return CheckResult("ffmpeg", "warn", "FFmpeg not found on PATH", fix="\n".join(fix_lines))


def check_js_runtime() -> CheckResult:
    try:
        from yt_dlp.globals import supported_js_runtimes

        for name in ("deno", "node", "quickjs", "bun"):
            runtime_cls = supported_js_runtimes.value.get(name)
            if runtime_cls is None:
                continue
            info = runtime_cls().info
            if info is None:
                continue
            if info.supported:
                return CheckResult("js_runtime", "ok", f"{name} {info.version}")
            return CheckResult(
                "js_runtime",
                "warn",
                f"{name} {info.version} is outdated for YouTube HD",
                fix="Install Node.js 22+ (https://nodejs.org) or Deno 2.3+ (https://deno.com)",
            )
    except Exception:
        pass

    return CheckResult(
        "js_runtime",
        "warn",
        "No supported JS runtime (YouTube may cap at 360p)",
        fix="Install Node.js 22+ (https://nodejs.org) or Deno 2.3+ (https://deno.com)",
    )


def _numpy_import_ok() -> tuple[bool, str]:
    try:
        import numpy as np  # noqa: F401

        return True, getattr(np, "__version__", "unknown")
    except ImportError as e:
        return False, str(e).splitlines()[0]


def check_numpy() -> CheckResult:
    ok, detail = _numpy_import_ok()
    if ok:
        return CheckResult("numpy", "ok", f"numpy {detail}")
    return CheckResult(
        "numpy",
        "fail",
        f"numpy is broken or missing ({detail})",
        fix=(
            "Streamlit needs a working numpy install for some UI features.\n"
            "Run: pip install --force-reinstall numpy\n"
            "If using Conda: conda install -n youtube-downloader numpy --force-reinstall"
        ),
    )


def repair_numpy() -> tuple[bool, str]:
    cmd = [sys.executable, "-m", "pip", "install", "--force-reinstall", "numpy"]
    try:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as e:
        return False, str(e)

    if result.returncode != 0:
        tail = (result.stderr or result.stdout or "").strip()[-800:]
        return False, tail or f"pip exited with code {result.returncode}"

    ok, _ = _numpy_import_ok()
    if not ok:
        return False, "numpy reinstall finished but import still fails."
    return True, "numpy reinstalled successfully."


def check_download_dir(download_dir: str | None = None) -> CheckResult:
    from src.download.paths import resolve_download_dir

    target = Path(
        resolve_download_dir(download_dir or "downloads", create=False)
    )
    try:
        target.mkdir(parents=True, exist_ok=True)
        test_file = target / ".write_test"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink()
        return CheckResult("download_dir", "ok", f"Writable folder: {target}")
    except OSError as e:
        return CheckResult(
            "download_dir",
            "fail",
            f"Cannot write to download folder: {e}",
            fix="Choose another download folder in Settings or fix folder permissions.",
        )


def check_settings_integrity() -> CheckResult:
    from src.constants import SETTINGS_FILE

    path = Path(SETTINGS_FILE)
    if not path.is_file():
        return CheckResult("settings", "ok", "Using default settings (no settings.json yet)")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return CheckResult(
                "settings",
                "warn",
                "settings.json is not an object — defaults will be used",
                fix="Delete or fix settings.json",
            )
        return CheckResult("settings", "ok", "settings.json readable")
    except (OSError, json.JSONDecodeError) as e:
        return CheckResult(
            "settings",
            "warn",
            f"settings.json unreadable: {e}",
            fix="Delete settings.json to regenerate defaults",
        )


def run_health_check(download_dir: str | None = None) -> HealthReport:
    checks = [
        check_python(),
        *check_packages(),
        check_ffmpeg(),
        check_js_runtime(),
        check_numpy(),
        check_download_dir(download_dir),
        check_settings_integrity(),
    ]
    runtime = os.environ.get("YTD_RUNTIME", "unknown")
    return HealthReport(
        python_version=sys.version.split()[0],
        runtime=runtime,
        checks=checks,
    )


def install_requirements() -> tuple[bool, str]:
    if not REQUIREMENTS_FILE.is_file():
        return False, f"Missing {REQUIREMENTS_FILE}"

    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "-r",
        str(REQUIREMENTS_FILE),
        "--upgrade",
    ]
    try:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as e:
        return False, str(e)

    if result.returncode != 0:
        tail = (result.stderr or result.stdout or "").strip()[-800:]
        return False, tail or f"pip exited with code {result.returncode}"

    return True, "Dependencies installed successfully."


def ensure_dependencies() -> tuple[bool, str]:
    missing = [
        label
        for import_name, label in REQUIRED_PACKAGES
        if import_name != "curl_cffi" and not _module_installed(import_name)
    ]
    if missing:
        ok, msg = install_requirements()
        if not ok:
            return ok, msg

    if not _numpy_import_ok()[0]:
        ok, msg = repair_numpy()
        if not ok:
            return False, f"numpy repair failed: {msg}"

    return True, "All required packages are installed."


def try_install_ffmpeg_windows() -> tuple[bool, str]:
    if os.name != "nt":
        return False, "Automatic FFmpeg install is only supported on Windows."

    if shutil.which("ffmpeg"):
        return True, "FFmpeg already available."

    if not shutil.which("winget"):
        return False, (
            "winget not found. Install FFmpeg manually:\n"
            "  winget install Gyan.FFmpeg\n"
            "Or: https://ffmpeg.org/download.html"
        )

    for pkg in ("Gyan.FFmpeg", "ffmpeg"):
        try:
            result = subprocess.run(
                [
                    "winget",
                    "install",
                    "-e",
                    "--id",
                    pkg,
                    "--accept-package-agreements",
                    "--accept-source-agreements",
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=600,
            )
            if result.returncode == 0 or shutil.which("ffmpeg"):
                return (
                    True,
                    f"FFmpeg install attempted via winget ({pkg}). "
                    "Restart the terminal if PATH did not update.",
                )
        except (OSError, subprocess.TimeoutExpired):
            continue

    return False, (
        "Could not install FFmpeg automatically.\n"
        "Run in an admin terminal: winget install Gyan.FFmpeg\n"
        "Or download: https://ffmpeg.org/download.html"
    )


def print_report(report: HealthReport, verbose: bool = True) -> None:
    print()
    print("=" * 50)
    print("  HEALTH CHECK")
    print("=" * 50)
    print(f"  Python:  {report.python_version}")
    print(f"  Runtime: {report.runtime}")
    print("-" * 50)
    for check in report.checks:
        icon = {"ok": "[OK]", "warn": "[!!]", "fail": "[XX]"}[check.status]
        print(f"  {icon} {check.name}: {check.message}")
        if verbose and check.fix and check.status != "ok":
            for line in check.fix.splitlines():
                print(f"         -> {line}")
    print("-" * 50)
    if report.can_start:
        if report.has_warnings:
            print("  Result: READY (with warnings — some features may be limited)")
        else:
            print("  Result: READY")
    else:
        print("  Result: NOT READY — fix failed checks above")
    print("=" * 50)
    print()


def report_to_json(report: HealthReport) -> str:
    return json.dumps(asdict(report), indent=2)
