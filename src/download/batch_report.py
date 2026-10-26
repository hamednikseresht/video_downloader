"""Write a self-contained HTML report for one finished batch or playlist run."""

from __future__ import annotations

import html
import os
from datetime import datetime

from src.constants import PROJECT_ROOT, REPORTS_DIR


def new_batch_id(kind: str = "batch") -> str:
    """Folder and report name: date and time, safe on Windows."""
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def write_batch_report(
    results: list[dict],
    meta: dict | None = None,
    dest_dir: str | None = None,
    report_name: str | None = None,
) -> str:
    info = dict(meta or {})
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    kind = (info.get("kind") or "batch").replace(" ", "-")
    folder = dest_dir or REPORTS_DIR
    os.makedirs(folder, exist_ok=True)
    name = report_name or f"{kind}-{stamp}.html"
    if not name.lower().endswith(".html"):
        name = f"{name}.html"
    path = os.path.join(folder, name)
    info["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    path_tmp = path + ".tmp"
    with open(path_tmp, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(_render(results, info))
    os.replace(path_tmp, path)
    return path


def _counts(results: list[dict]) -> dict[str, int]:
    ok = sum(1 for item in results if item.get("status") == "ok")
    skipped = sum(1 for item in results if item.get("status") == "skipped")
    failed = sum(1 for item in results if item.get("status") == "error")
    return {"total": len(results), "ok": ok, "skipped": skipped, "failed": failed}


def _render(results: list[dict], meta: dict) -> str:
    counts = _counts(results)
    title = html.escape(str(meta.get("title") or "Batch download"))
    rows = "\n".join(_row(index, item) for index, item in enumerate(results, start=1))
    if not rows:
        rows = '<tr><td colspan="5" class="empty">No items in this run.</td></tr>'
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{
    color-scheme: light;
    --bg: #fafafa;
    --card: #ffffff;
    --ink: #09090b;
    --muted: #71717a;
    --line: #e4e4e7;
    --ok: #047857;
    --ok-bg: #ecfdf5;
    --skip: #b45309;
    --skip-bg: #fffbeb;
    --bad: #b91c1c;
    --bad-bg: #fef2f2;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    background: var(--bg);
    color: var(--ink);
    font: 15px/1.5 Inter, "Segoe UI", sans-serif;
  }}
  main {{ max-width: 980px; margin: 0 auto; padding: 40px 20px 64px; }}
  h1 {{ font-size: 1.75rem; letter-spacing: -0.03em; margin: 0 0 6px; }}
  .sub {{ color: var(--muted); margin: 0 0 24px; }}
  .cards {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 24px; }}
  .card {{ background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: 16px; }}
  .card b {{ display: block; font-size: 1.5rem; letter-spacing: -0.03em; }}
  .card span {{ color: var(--muted); font-size: 0.8rem; }}
  table {{ width: 100%; border-collapse: collapse; background: var(--card); border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }}
  th, td {{ text-align: left; padding: 12px 14px; border-bottom: 1px solid var(--line); vertical-align: top; }}
  th {{ font-size: 0.75rem; letter-spacing: 0.04em; text-transform: uppercase; color: var(--muted); background: #f4f4f5; }}
  tr:last-child td {{ border-bottom: 0; }}
  a {{ color: inherit; }}
  .badge {{ display: inline-block; border-radius: 999px; padding: 2px 8px; font-size: 0.75rem; font-weight: 600; }}
  .ok {{ color: var(--ok); background: var(--ok-bg); }}
  .skipped {{ color: var(--skip); background: var(--skip-bg); }}
  .error {{ color: var(--bad); background: var(--bad-bg); }}
  .error-text {{ margin: 8px 0 0; white-space: pre-wrap; color: var(--bad); font-size: 0.85rem; }}
  .path {{ color: var(--muted); font-size: 0.8rem; word-break: break-all; }}
  .empty {{ color: var(--muted); }}
  @media (max-width: 720px) {{
    .cards {{ grid-template-columns: 1fr 1fr; }}
    table, thead, tbody, th, td, tr {{ display: block; }}
    thead {{ display: none; }}
    td {{ border-bottom: 0; }}
    tr {{ border-bottom: 1px solid var(--line); padding: 8px 0; }}
  }}
</style>
</head>
<body>
<main>
  <h1>{title}</h1>
  <p class="sub">{html.escape(str(meta.get("finished_at") or ""))} · {html.escape(str(meta.get("detail") or "Download report"))}</p>
  <section class="cards">
    <div class="card"><b>{counts["total"]}</b><span>Items</span></div>
    <div class="card"><b>{counts["ok"]}</b><span>Saved</span></div>
    <div class="card"><b>{counts["skipped"]}</b><span>Skipped</span></div>
    <div class="card"><b>{counts["failed"]}</b><span>Failed</span></div>
  </section>
  <table>
    <thead><tr><th>#</th><th>Title</th><th>Status</th><th>File</th><th>Link</th></tr></thead>
    <tbody>
{rows}
    </tbody>
  </table>
</main>
</body>
</html>
"""


def _row(index: int, item: dict) -> str:
    status = str(item.get("status") or "error")
    label = {"ok": "Saved", "skipped": "Skipped", "error": "Failed"}.get(status, status)
    badge = status if status in {"ok", "skipped", "error"} else "error"
    title = html.escape(str(item.get("title") or "Untitled"))
    url = str(item.get("url") or "")
    link = f'<a href="{html.escape(url, quote=True)}">{html.escape(url)}</a>' if url else ""
    path = item.get("filepath") or ""
    file_cell = f'<div class="path">{html.escape(str(path))}</div>' if path else ""
    error = str(item.get("error") or "").strip()
    error_html = f'<pre class="error-text">{html.escape(error)}</pre>' if error else ""
    return (
        "<tr>"
        f"<td>{index}</td>"
        f"<td>{title}{error_html}</td>"
        f'<td><span class="badge {badge}">{html.escape(label)}</span></td>'
        f"<td>{file_cell}</td>"
        f"<td>{link}</td>"
        "</tr>"
    )


def report_folder() -> str:
    return os.path.abspath(REPORTS_DIR or os.path.join(PROJECT_ROOT, "reports"))
