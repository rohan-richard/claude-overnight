from datetime import datetime

from overnight import archive, paths, store, summary

STAMP = "2026-07-27-0110"


def job(prompt, status=store.DONE, result=None, error=None,
        started=None, finished=None):
    j = store.add(prompt)
    j.status = status
    j.error = error
    j.started_at = started
    j.finished_at = finished
    if result is not None:
        path = paths.results_dir() / "2026-07-27" / f"{j.id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(result)
        j.result_path = str(path)
    store.save(j)
    return j


class TestRender:
    def test_counts_appear_in_the_stat_header(self):
        page = summary.render(
            [job("a"), job("b"), job("c", status=store.FAILED, error="boom"),
             job("d", status=store.PENDING)],
            STAMP)
        assert '<span class="num">2</span><span class="label">done</span>' in page
        assert '<span class="num">1</span><span class="label">failed</span>' in page
        assert '<span class="num">1</span><span class="label">requeued</span>' in page

    def test_one_details_block_per_job_with_a_report(self):
        page = summary.render(
            [job("a", result="# a\n\n---\n\nbody a"),
             job("b", result="# b\n\n---\n\nbody b")],
            STAMP)
        assert page.count("<details>") == 2

    def test_report_body_is_rendered_not_linked(self):
        page = summary.render([job("q", result="# q\n\n---\n\n## Findings\n\ntext")], STAMP)
        assert "<h2>Findings</h2>" in page
        assert ".md" not in page

    def test_provenance_header_is_stripped_from_the_body(self):
        page = summary.render(
            [job("q", result="# q\n\n> Queued yesterday\n\n---\n\nreal body")], STAMP)
        assert "real body" in page
        assert "Queued yesterday" not in page

    def test_job_without_report_has_no_details_block(self):
        page = summary.render([job("q", status=store.FAILED, error="boom")], STAMP)
        assert "<details>" not in page
        assert "boom" in page

    def test_failed_job_shows_its_error(self):
        page = summary.render(
            [job("q", status=store.FAILED, error="not a git repo: /tmp/x")], STAMP)
        assert "not a git repo: /tmp/x" in page

    def test_done_job_shows_the_resume_command(self):
        j = job("q")
        page = summary.render([j], STAMP)
        assert f"overnight resume {j.id[-6:]}" in page

    def test_report_content_cannot_inject_markup(self):
        page = summary.render(
            [job("q", result="# q\n\n---\n\n<script>alert(1)</script>")], STAMP)
        assert "<script>alert(1)</script>" not in page

    def test_prompt_is_escaped(self):
        page = summary.render([job("<img src=x onerror=1>")], STAMP)
        assert "<img src=x" not in page

    def test_empty_batch_renders(self):
        assert "Nothing ran." in summary.render([], STAMP)

    def test_header_shows_a_readable_date(self):
        assert "Monday 27 July, 01:10" in summary.render([job("q")], STAMP)

    def test_light_mode_variant_is_present(self):
        assert "prefers-color-scheme: light" in summary.render([job("q")], STAMP)

    def test_earlier_batches_footer_links_absolute(self):
        archive.write_batch([job("older")], now=datetime(2026, 7, 25, 1, 0))
        page = summary.render([job("new")], STAMP, earlier=archive.list_batches())
        assert "Earlier batches" in page
        assert 'href="file://' in page

    def test_no_footer_without_earlier_batches(self):
        assert "Earlier batches" not in summary.render([job("q")], STAMP)


class TestDurations:
    def test_batch_elapsed_spans_first_start_to_last_finish(self):
        page = summary.render([
            job("a", started="2026-07-27T01:10:00+00:00",
                finished="2026-07-27T01:14:00+00:00"),
            job("b", started="2026-07-27T01:14:00+00:00",
                finished="2026-07-27T01:40:00+00:00"),
        ], STAMP)
        assert '<span class="num">30m</span>' in page

    def test_job_duration_shown_in_meta(self):
        page = summary.render([
            job("a", started="2026-07-27T01:10:00+00:00",
                finished="2026-07-27T01:10:45+00:00")], STAMP)
        assert "45s" in page

    def test_missing_timestamps_are_tolerated(self):
        page = summary.render([job("a")], STAMP)
        assert "elapsed" not in page
