"""HTML summary of a finished batch, opened in the browser so mornings start
with one glance: what ran, what failed, and the command to resume each one."""

import html
import os
import shutil
import subprocess
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

from . import markdown, store

_STATUS = {
    store.DONE: ("done", "✅"),
    store.FAILED: ("failed", "❌"),
    store.PENDING: ("requeued", "⏸️"),
}


def render(batch: list[store.Job], stamp: str, earlier=()) -> str:
    from . import archive

    try:
        when = datetime.strptime(stamp, "%Y-%m-%d-%H%M").strftime("%A %d %B, %H:%M")
    except ValueError:
        when = stamp
    counts = archive.counts(batch)
    cards = "\n".join(_card(job) for job in batch) or _empty_card()
    return _PAGE.format(
        stamp=html.escape(stamp),
        when=html.escape(when),
        tiles=_tiles(counts, batch),
        cards=cards,
        footer=_footer(earlier),
    )


def open_in_browser(path: Path) -> bool:
    """Open the summary. Returns whether the open was handed off successfully —
    the caller logs the path either way, since a scheduler-launched process
    cannot always reach a browser."""
    url = path.as_uri()
    if sys.platform == "darwin" and os.path.exists("/usr/bin/open"):
        # More reliable than webbrowser from a launchd context.
        result = subprocess.run(["/usr/bin/open", url], capture_output=True)
        if result.returncode == 0:
            return True
    try:
        return webbrowser.open(url)
    except Exception:
        return False


def write(batch: list[store.Job]) -> Path:
    """Record the batch and return the page to open."""
    from . import archive

    archive.write_batch(batch)
    return archive.latest_html_path()


def _tiles(counts: dict[str, int], batch: list[store.Job]) -> str:
    tiles = [
        ("done", counts["done"], "done"),
        ("failed", counts["failed"], "failed"),
        ("requeued", counts["requeued"], "requeued"),
    ]
    cells = [
        f'<div class="tile {cls}"><span class="num">{value}</span>'
        f'<span class="label">{label}</span></div>'
        for cls, value, label in tiles
    ]
    elapsed = _batch_duration(batch)
    if elapsed:
        cells.append(
            f'<div class="tile"><span class="num">{html.escape(elapsed)}</span>'
            f'<span class="label">elapsed</span></div>'
        )
    return "\n".join(cells)


def _card(job: store.Job) -> str:
    cls, icon = _STATUS.get(job.status, ("done", "•"))
    prompt = html.escape(job.prompt)
    meta = _meta(job)
    body = _body(job)
    if body:
        return (
            f'<article class="card {cls}">'
            f'<details><summary><span class="icon">{icon}</span>'
            f'<span class="prompt">{prompt}</span>{meta}</summary>'
            f'<div class="report">{body}</div></details></article>'
        )
    return (
        f'<article class="card {cls}"><div class="head">'
        f'<span class="icon">{icon}</span>'
        f'<span class="prompt">{prompt}</span>{meta}</div></article>'
    )


def _meta(job: store.Job) -> str:
    bits = []
    if job.status == store.DONE:
        bits.append(f"<code>overnight resume {html.escape(job.id[-6:])}</code>")
    elif job.status == store.FAILED:
        bits.append(f'<span class="err">{html.escape((job.error or "failed")[:200])}</span>')
    else:
        bits.append("requeued — hit a usage limit, runs next window")
    if job.repo:
        branch = job.extra.get("branch")
        bits.append(f"<code>{html.escape(branch)}</code>" if branch
                    else html.escape(os.path.basename(job.repo.rstrip("/"))))
    duration = _job_duration(job)
    if duration:
        bits.append(html.escape(duration))
    return f'<div class="meta">{" · ".join(bits)}</div>'


def _body(job: store.Job) -> str:
    if not job.result_path:
        return ""
    try:
        text = Path(job.result_path).read_text()
    except OSError:
        return ""
    # Reports open with a title and provenance block above a --- rule; the
    # card header already says all of that.
    _, sep, rest = text.partition("\n---\n")
    return markdown.render(rest if sep else text)


def _empty_card() -> str:
    return '<article class="card"><div class="head"><span class="prompt">Nothing ran.</span></div></article>'


def _footer(earlier) -> str:
    if not earlier:
        return ""
    links = "\n".join(
        f'<li><a href="{html.escape(_href(b))}">{html.escape(b.title)}</a>'
        + (f' <span class="stats">{html.escape(b.stats)}</span>' if b.stats else "")
        + "</li>"
        for b in earlier
    )
    return f'<section class="earlier"><h2>Earlier batches</h2><ul>{links}</ul></section>'


def _href(batch) -> str:
    # Absolute, because this page is served from two places: results/latest.html
    # and results/batches/<stamp>.html. A relative link cannot satisfy both.
    target = batch.html_path or batch.md_path
    return target.as_uri()


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _format_delta(seconds: float) -> str:
    if seconds < 90:
        return f"{int(seconds)}s"
    minutes = seconds / 60
    if minutes < 90:
        return f"{int(round(minutes))}m"
    return f"{minutes / 60:.1f}h"


def _job_duration(job: store.Job) -> str | None:
    start, end = _parse(job.started_at), _parse(job.finished_at)
    if not start or not end or end < start:
        return None
    return _format_delta((end - start).total_seconds())


def _batch_duration(batch: list[store.Job]) -> str | None:
    starts = [d for d in (_parse(j.started_at) for j in batch) if d]
    ends = [d for d in (_parse(j.finished_at) for j in batch) if d]
    if not starts or not ends:
        return None
    span = (max(ends) - min(starts)).total_seconds()
    return _format_delta(span) if span >= 0 else None


_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>claude-overnight — {stamp}</title>
<style>
  :root {{
    --bg: #0d1117; --panel: #161b22; --panel-2: #1c232c; --line: #21262d;
    --text: #e6edf3; --muted: #8b949e; --link: #58a6ff;
    --done: #3fb950; --failed: #f85149; --requeued: #d29922;
  }}
  @media (prefers-color-scheme: light) {{
    :root {{
      --bg: #ffffff; --panel: #f6f8fa; --panel-2: #eef1f4; --line: #d8dee4;
      --text: #1f2328; --muted: #636c76; --link: #0969da;
      --done: #1a7f37; --failed: #cf222e; --requeued: #9a6700;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font: 15px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    max-width: 860px; margin: 0 auto; padding: 48px 20px 96px;
    background: var(--bg); color: var(--text);
  }}
  header {{ margin-bottom: 28px; }}
  h1 {{ font-size: 22px; font-weight: 600; margin: 0 0 4px; letter-spacing: -0.01em; }}
  .when {{ color: var(--muted); font-size: 14px; }}
  .tiles {{ display: flex; flex-wrap: wrap; gap: 10px; margin: 24px 0 32px; }}
  .tile {{
    flex: 1 1 110px; background: var(--panel); border: 1px solid var(--line);
    border-radius: 10px; padding: 14px 16px; display: flex; flex-direction: column; gap: 2px;
  }}
  .tile .num {{ font-size: 24px; font-weight: 600; line-height: 1.1; }}
  .tile .label {{ font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; }}
  .tile.done .num {{ color: var(--done); }}
  .tile.failed .num {{ color: var(--failed); }}
  .tile.requeued .num {{ color: var(--requeued); }}
  .card {{
    background: var(--panel); border: 1px solid var(--line); border-left: 3px solid var(--muted);
    border-radius: 8px; margin-bottom: 10px; overflow: hidden;
  }}
  .card.done {{ border-left-color: var(--done); }}
  .card.failed {{ border-left-color: var(--failed); }}
  .card.requeued {{ border-left-color: var(--requeued); }}
  summary, .head {{ padding: 14px 16px; cursor: pointer; list-style: none; }}
  .head {{ cursor: default; }}
  summary::-webkit-details-marker {{ display: none; }}
  summary:hover {{ background: var(--panel-2); }}
  .icon {{ margin-right: 8px; }}
  .prompt {{ font-weight: 500; }}
  .meta {{ margin: 6px 0 0 26px; font-size: 13px; color: var(--muted); }}
  .meta .err {{ color: var(--failed); }}
  code {{
    background: var(--panel-2); border: 1px solid var(--line); padding: 1px 6px;
    border-radius: 5px; font-size: 12px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }}
  .report {{ padding: 4px 20px 20px; border-top: 1px solid var(--line); }}
  .report h1 {{ font-size: 18px; }}
  .report h2 {{ font-size: 16px; margin-top: 22px; }}
  .report h3 {{ font-size: 14px; margin-top: 18px; }}
  .report pre {{
    background: var(--bg); border: 1px solid var(--line); border-radius: 8px;
    padding: 12px 14px; overflow-x: auto;
  }}
  .report pre code {{ background: none; border: 0; padding: 0; font-size: 12.5px; }}
  .report blockquote {{
    margin: 12px 0; padding: 2px 0 2px 14px; border-left: 3px solid var(--line); color: var(--muted);
  }}
  .table-wrap {{ overflow-x: auto; margin: 14px 0; }}
  .report table {{ border-collapse: collapse; font-size: 13.5px; min-width: 100%; }}
  .report th, .report td {{
    border: 1px solid var(--line); padding: 7px 11px; text-align: left; vertical-align: top;
  }}
  .report th {{ background: var(--panel-2); font-weight: 600; white-space: nowrap; }}
  .report img {{ max-width: 100%; }}
  a {{ color: var(--link); text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .earlier {{ margin-top: 48px; border-top: 1px solid var(--line); padding-top: 20px; }}
  .earlier h2 {{ font-size: 13px; text-transform: uppercase; letter-spacing: .04em; color: var(--muted); font-weight: 600; }}
  .earlier ul {{ list-style: none; padding: 0; }}
  .earlier li {{ padding: 5px 0; font-size: 14px; }}
  .earlier .stats {{ color: var(--muted); font-size: 13px; }}
</style>
</head>
<body>
<header>
  <h1>Overnight batch</h1>
  <div class="when">{when}</div>
</header>
<div class="tiles">
{tiles}
</div>
{cards}
{footer}
</body>
</html>
"""
