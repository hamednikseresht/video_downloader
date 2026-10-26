"""Classify download failures so the batch report can explain each one and skip hopeless retries."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Problem:
    code: str
    title: str
    advice: str
    retryable: bool


_PROBLEMS = (
    Problem(
        "empty_response",
        "Instagram sent an empty response",
        "The post is private or needs login, or the browser cookies expired. Open it in a "
        "logged-out browser window: if it plays, refresh cookies or run `pip install -U yt-dlp`.",
        False,
    ),
    Problem(
        "restricted",
        "Restricted audience",
        "The post is limited by age, region or audience, or the account is blocked. Nothing in "
        "the app can fix this.",
        False,
    ),
    Problem(
        "no_video",
        "No video in this post",
        "Photo post, or a carousel slide that is a photo. Use the reel link or a slide that is a video.",
        False,
    ),
    Problem(
        "login_required",
        "Login required",
        "Log into the site in Firefox, set Settings > cookies to that browser, then retry.",
        False,
    ),
    Problem(
        "rate_limit",
        "Rate limited (HTTP 429)",
        "Too many requests. Wait a few minutes, raise the pause between links, then retry.",
        True,
    ),
    Problem(
        "windows_path",
        "Windows could not write the file (Errno 22)",
        "The app retries with a simpler file name and format. Retry if it still failed.",
        True,
    ),
    Problem(
        "network",
        "Network problem",
        "Connection dropped or timed out. Check the connection and retry.",
        True,
    ),
    Problem(
        "unknown",
        "Other error",
        "See the error text and logs/app.log.",
        True,
    ),
)
_BY_CODE = {problem.code: problem for problem in _PROBLEMS}

_MATCHERS = (
    ("empty_response", ("empty media response",)),
    ("restricted", ("seen by certain audiences", "isn't available to everyone", "not available to everyone")),
    (
        "no_video",
        ("no video formats", "no video in this post", "photo carousel", "there is no video", "photos only", "did not return a video"),
    ),
    ("rate_limit", ("429", "too many requests", "rate-limit")),
    ("login_required", ("login required", "sign in to confirm", "not a bot", "private video")),
    ("windows_path", ("errno 22", "invalid argument", "could not be saved on windows")),
    ("network", ("timed out", "timeout", "connection reset", "network is unreachable", "temporarily unavailable")),
)


def classify_problem(error: str) -> Problem:
    text = (error or "").lower()
    for code, needles in _MATCHERS:
        if any(needle in text for needle in needles):
            return _BY_CODE[code]
    return _BY_CODE["unknown"]


def is_hopeless(error: str) -> bool:
    """True when retrying the same link cannot help."""
    problem = classify_problem(error)
    return problem.code != "unknown" and not problem.retryable


def group_problems(results: list[dict]) -> list[dict]:
    """Failed items grouped by problem, most frequent first."""
    groups: dict[str, dict] = {}
    for item in results:
        if item.get("status") != "error":
            continue
        problem = classify_problem(item.get("error") or "")
        group = groups.setdefault(
            problem.code, {"problem": problem, "items": []}
        )
        group["items"].append(item)
    return sorted(groups.values(), key=lambda g: len(g["items"]), reverse=True)


def problems_text(results: list[dict], title: str, finished_at: str) -> str:
    """Plain-text list of every failed link, grouped by cause."""
    ok = sum(1 for r in results if r.get("status") in ("ok", "skipped"))
    failed = sum(1 for r in results if r.get("status") == "error")
    lines = [
        f"{title}",
        f"Finished: {finished_at}",
        f"Total {len(results)} · succeeded {ok} · failed {failed}",
        "",
    ]
    groups = group_problems(results)
    if not groups:
        lines.append("No problems. Every link succeeded.")
    for group in groups:
        problem = group["problem"]
        lines.append(f"== {problem.title} ({len(group['items'])}) ==")
        lines.append(f"What to do: {problem.advice}")
        for item in group["items"]:
            label = item.get("title") or item.get("url") or ""
            lines.append(f"  - [{(item.get('platform') or '').title()}] {label}")
            lines.append(f"    {item.get('url') or ''}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
