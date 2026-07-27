# Batch summary: archive, redesign, and the open bug

## Problem

Three issues surfaced by the 2026-07-27 test run.

**The summary page never opened.** The launchd agent runs the installed
`overnight` binary, which was still 0.5.0 while the repo was 0.6.0. The
installed package has no `summary.py` at all, so `latest.html` was never
written. `index.md` updated normally, which is why the batch otherwise looked
healthy. This is an install-staleness bug, not a defect in the page code.

**Every batch is shown at once.** `_update_index` appends a new `## Batch`
section to `index.md` forever and `cmd_results` prints the whole file. Nothing
rotates. The HTML side has the opposite failure: `latest.html` is overwritten
each run, so previous batches are lost rather than archived.

**The page is hard to read.** A flat `<ul>` with no run statistics, and the
per-job links point at `.md` files that browsers download instead of render,
which breaks the morning-review flow the page exists to serve.

## Design

### `markdown.py` (new)

A self-contained markdown-to-HTML renderer. The project has no runtime
dependencies and should not gain one for this.

Supports headings, fenced and inline code, bold/italic, links, ordered and
unordered lists, blockquotes, horizontal rules, and paragraphs. Everything is
HTML-escaped before any markup is emitted: report bodies are model output and
must never be able to inject markup into the page.

### `archive.py` (new)

Owns batch-record bookkeeping and nothing else.

- `write_batch(batch)` — writes `results/batches/<stamp>.md` and `.html`
- `list_batches()` — newest-first, derived by globbing `results/batches/`
- `regenerate_index()` — rewrites `index.md` as a table of contents

The batch list is derived from the filesystem rather than tracked in state, so
deleting a batch file by hand leaves the archive consistent.

### `summary.py` (rewritten)

Turns one batch into an HTML page. Gains:

- a stat header: done / failed / requeued counts and batch wall-time, computed
  from `min(started_at)` to `max(finished_at)`
- per-status colour accents
- each report rendered inline inside a collapsible `<details>`
- a light-mode variant via `prefers-color-scheme`
- an "earlier batches" footer built from `archive.list_batches()`

`open_in_browser` shells out to `/usr/bin/open` on darwin and falls back to
`webbrowser`, and returns a bool instead of discarding the result. The current
code swallows both the exception and the `False` return, so a failure to open
is indistinguishable from success.

### `runner.py` / `cli.py`

`_update_index` stops appending and delegates to `archive.py`. `run_batch`
logs the summary path unconditionally, so a failure to open still leaves a
usable path in `runner.log`. `cmd_results` with no id prints only the current
batch plus a one-line pointer to the archive.

## Data flow

```
run_batch
  -> archive.write_batch(batch)
       -> batches/<stamp>.md
       -> batches/<stamp>.html   (via summary.render)
  -> archive.regenerate_index()  (globs batches/, newest first)
  -> copy newest html to latest.html
  -> summary.open_in_browser(latest)
```

`latest.html` is a real copy, not a symlink, so `file://` opening is
unambiguous and pruning the archive cannot leave a dangling target.

## Migration

There are no batch records to derive the three existing `index.md` sections
from. On first run under the new code, the existing `index.md` moves to
`batches/legacy.md` and is linked from the regenerated table of contents.
Nothing is deleted; per-job reports under `results/<date>/` are untouched and
still linked from the legacy file.

## Testing

- `markdown.py`: one test per construct, plus an escaping test asserting that
  `<script>` in report text cannot reach the page as markup.
- `archive.py`: index regeneration, newest-first ordering, legacy migration.
- `summary.py`: a rendered batch contains the right counts and one `<details>`
  per job.
- `test_runner.py`: update the assertions that depend on append behaviour.

The existing `cfg()` test helper defaults `open_browser_summary` to `True`, so
the suite currently opens a real browser tab on every run. The helper defaults
to `False`, and the opener is monkeypatched in the one test that covers it.

## Decisions taken

Batch records are kept unbounded. They are roughly 10KB each, so a year of
nightly runs is about 4MB; a pruning knob is not worth the configuration
surface.

Auto-open stays unconditional on time of day. The batch runs at 1am and the
tab waiting at 8am is the intended behaviour.

## Out of scope

`repo_job_timeout_minutes` is missing from the user's existing `config.toml`
because the file predates the key. It falls back to the default, so nothing is
broken. Left alone.
