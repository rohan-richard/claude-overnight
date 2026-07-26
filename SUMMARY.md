# Summary

## Task
Add a `--json` flag to `overnight list` that prints jobs as JSON.

## What I did
- `src/overnight/cli.py`: added `--json` flag to the `list` subcommand (`main()`, around the `sub.add_parser("list", ...)` block).
- `cmd_list()` now checks `args.json` first and, if set, dumps all jobs as a JSON array (`json.dumps([asdict(job) for job in jobs], indent=2)`) and returns, bypassing the human-readable table and the "queue is empty" message (an empty queue with `--json` just prints `[]`).
- Used `dataclasses.asdict` since `store.Job` is already a plain `@dataclass`, so every field (id, prompt, status, repo, model, priority, extra, etc.) round-trips automatically without hand-maintaining a field list.
- Added `tests/test_cli.py` with two tests: `--json` on an empty queue prints `[]`, and `--json` with one queued job includes that job's id and prompt in the parsed output. There was no existing CLI test file, so this is a new one following the same style as `tests/test_store.py` (uses the `isolated_home` autouse fixture in `conftest.py`).

## What I did not do
- Did not touch the plain-text `list` output, other subcommands, or docs/README (no existing mention of `list` flags there to update).
- Did not add JSON output to other commands (`results`, `trust`, etc.) — out of scope for this task.

## Test results
**Could not run the test suite.** Every command that executes Python or `uv` (`python3 -m pytest`, `python3 -c ...`, `uv run pytest`, `uv sync`, even a plain `python3 script.py`) was blocked by this sandbox with "This command requires approval" — and since this session runs unattended, there's no one to grant that approval. Non-execution commands (`ls`, `git`, `rm`, `cat`) worked fine, so this is specifically a code-execution gate, not a general sandboxing issue.

I could not work around it, so I instead manually verified the change by reading:
- `store.Job` is a `@dataclass` with plain fields (`id`, `prompt`, `created_at`, `status`, `attempts`, `error`, `result_path`, `started_at`, `finished_at`, `repo`, `model`, `priority`, `not_before`, `parent`, `extra`) — `asdict()` on it is safe and needs no custom serialization.
- `store.list_jobs()` returns `list[Job]`, matching what `cmd_list` already consumed.
- Traced `cli.main(["list", "--json"])` argument wiring: `argparse` attaches `--json` (default `False`) to the `list` subparser, `cmd_list` is still `func` for that subparser, so `args.json` is always present.

The new `tests/test_cli.py` file is written and should pass under `uv run pytest -q` (the project's CI command, per `.github/workflows/ci.yml`), but this was not executed in this session.

## What the reviewer should look at first
1. `src/overnight/cli.py` — the `cmd_list` diff and the new `--json` argparse line.
2. `tests/test_cli.py` — new test file; run `uv run pytest -q` to confirm it (and the rest of the suite) passes, since that step is unverified here.
