"""Batch records. Each finished batch becomes its own pair of files under
`results/batches/`, and `index.md` is regenerated from them as a table of
contents. Nothing is appended, so the index cannot grow without bound.

The batch list is derived by globbing the directory rather than tracked in
state: deleting a batch file by hand leaves everything else consistent.
"""

import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import paths, store

LEGACY_NAME = "legacy.md"
_STATS_LINE = re.compile(r"^>\s*(.*)$", re.M)

_ICON = {store.DONE: "✅", store.FAILED: "❌", store.PENDING: "⏸️"}


@dataclass
class Batch:
    stamp: str
    md_path: Path
    html_path: Path | None
    stats: str

    @property
    def title(self) -> str:
        if self.stamp == "legacy":
            return "Batches before v0.7"
        try:
            dt = datetime.strptime(self.stamp, "%Y-%m-%d-%H%M")
        except ValueError:
            return self.stamp
        return dt.strftime("%a %d %b %Y, %H:%M")


def batches_dir() -> Path:
    return paths.results_dir() / "batches"


def index_path() -> Path:
    return paths.results_dir() / "index.md"


def latest_html_path() -> Path:
    return paths.results_dir() / "latest.html"


def stamp_now(now: datetime | None = None) -> str:
    """A minute-resolution stamp, suffixed if a batch already claimed it.
    Two batches inside one minute is unusual but a collision would silently
    overwrite the earlier record."""
    base = (now or datetime.now()).strftime("%Y-%m-%d-%H%M")
    stamp, n = base, 2
    while (batches_dir() / f"{stamp}.md").exists():
        stamp = f"{base}-{n}"
        n += 1
    return stamp


def counts(batch: list[store.Job]) -> dict[str, int]:
    return {
        "done": sum(1 for j in batch if j.status == store.DONE),
        "failed": sum(1 for j in batch if j.status == store.FAILED),
        "requeued": sum(1 for j in batch if j.status == store.PENDING),
    }


def stats_line(batch: list[store.Job]) -> str:
    c = counts(batch)
    parts = [f"{c['done']} done"]
    if c["failed"]:
        parts.append(f"{c['failed']} failed")
    if c["requeued"]:
        parts.append(f"{c['requeued']} requeued")
    return " · ".join(parts)


def migrate_legacy() -> Path | None:
    """Move a pre-v0.7 append-only index.md aside so it stays readable and
    linked. Runs once: after this, batches/ exists and the check is skipped."""
    index = index_path()
    if batches_dir().exists() or not index.exists():
        return None
    batches_dir().mkdir(parents=True, exist_ok=True)
    target = batches_dir() / LEGACY_NAME
    shutil.move(str(index), str(target))
    return target


def list_batches() -> list[Batch]:
    """Newest first. The legacy record, if present, always sorts last."""
    directory = batches_dir()
    if not directory.exists():
        return []
    found = []
    for md in directory.glob("*.md"):
        stamp = "legacy" if md.name == LEGACY_NAME else md.stem
        html_path = md.with_suffix(".html")
        found.append(Batch(
            stamp=stamp,
            md_path=md,
            html_path=html_path if html_path.exists() else None,
            stats=_read_stats(md),
        ))
    found.sort(key=lambda b: (b.stamp != "legacy", b.stamp), reverse=True)
    return found


def _read_stats(md: Path) -> str:
    try:
        match = _STATS_LINE.search(md.read_text())
    except OSError:
        return ""
    return match.group(1).strip() if match else ""


def write_batch(batch: list[store.Job], now: datetime | None = None) -> Path:
    """Record a finished batch and refresh the index. Returns the path to the
    batch's HTML page (also copied to latest.html)."""
    from . import summary  # imported here to keep the module dependency one-way

    migrate_legacy()
    batches_dir().mkdir(parents=True, exist_ok=True)
    stamp = stamp_now(now)

    md_path = batches_dir() / f"{stamp}.md"
    md_path.write_text(_render_markdown(batch, stamp))

    html_path = batches_dir() / f"{stamp}.html"
    html_path.write_text(summary.render(batch, stamp, earlier=list_batches()[1:]))
    shutil.copyfile(html_path, latest_html_path())

    regenerate_index()
    return html_path


def _render_markdown(batch: list[store.Job], stamp: str) -> str:
    lines = [f"# Batch {stamp}", "", f"> {stats_line(batch)}", ""]
    for job in batch:
        icon = _ICON.get(job.status, "•")
        if job.status == store.DONE and job.result_path:
            rel = os.path.relpath(job.result_path, batches_dir())
            lines.append(f"- {icon} [{job.prompt[:80]}]({rel}) · resume `{job.id[-6:]}`")
        elif job.status == store.PENDING:
            lines.append(f"- {icon} requeued (hit limit): {job.prompt[:80]}")
        else:
            lines.append(f"- {icon} {job.prompt[:80]} — {job.error or 'failed'}")
    return "\n".join(lines) + "\n"


def regenerate_index() -> Path:
    """Rewrite index.md as a table of contents over the batch records."""
    entries = list_batches()
    lines = ["# Overnight results", ""]
    if not entries:
        lines.append("No batches yet.")
    else:
        lines.append("Newest first. Each batch links to its own page.")
        lines.append("")
        for batch in entries:
            rel = os.path.relpath(batch.md_path, paths.results_dir())
            stats = f" — {batch.stats}" if batch.stats else ""
            lines.append(f"- [{batch.title}]({rel}){stats}")
    index = index_path()
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text("\n".join(lines) + "\n")
    return index


def current_batch_markdown() -> str | None:
    """The most recent batch record, for `overnight results`."""
    entries = list_batches()
    for batch in entries:
        if batch.stamp != "legacy":
            return batch.md_path.read_text()
    return entries[0].md_path.read_text() if entries else None
