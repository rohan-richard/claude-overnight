from datetime import datetime

from overnight import archive, paths, store


def job(prompt, status=store.DONE, result=None, error=None):
    j = store.add(prompt)
    j.status = status
    j.error = error
    if result:
        path = paths.results_dir() / "2026-07-27" / f"{j.id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(result)
        j.result_path = str(path)
    store.save(j)
    return j


AT = datetime(2026, 7, 27, 1, 10)


class TestWriteBatch:
    def test_writes_md_and_html_for_the_batch(self):
        archive.write_batch([job("q1", result="# q1\n\n---\n\nbody")], now=AT)
        assert (archive.batches_dir() / "2026-07-27-0110.md").exists()
        assert (archive.batches_dir() / "2026-07-27-0110.html").exists()

    def test_copies_newest_page_to_latest_html(self):
        archive.write_batch([job("q1")], now=AT)
        latest = archive.latest_html_path().read_text()
        assert "q1" in latest

    def test_stats_line_records_counts(self):
        archive.write_batch(
            [job("a"), job("b", status=store.FAILED, error="boom"),
             job("c", status=store.PENDING)],
            now=AT)
        text = (archive.batches_dir() / "2026-07-27-0110.md").read_text()
        assert "1 done · 1 failed · 1 requeued" in text

    def test_stats_line_omits_empty_categories(self):
        archive.write_batch([job("a")], now=AT)
        assert "> 1 done\n" in (archive.batches_dir() / "2026-07-27-0110.md").read_text()

    def test_same_minute_batches_do_not_overwrite(self):
        archive.write_batch([job("first")], now=AT)
        archive.write_batch([job("second")], now=AT)
        assert len(archive.list_batches()) == 2


class TestListBatches:
    def test_newest_first(self):
        archive.write_batch([job("older")], now=datetime(2026, 7, 26, 1, 0))
        archive.write_batch([job("newer")], now=datetime(2026, 7, 27, 1, 0))
        assert [b.stamp for b in archive.list_batches()] == [
            "2026-07-27-0100", "2026-07-26-0100"]

    def test_empty_when_nothing_written(self):
        assert archive.list_batches() == []

    def test_title_is_human_readable(self):
        archive.write_batch([job("q")], now=AT)
        assert archive.list_batches()[0].title == "Mon 27 Jul 2026, 01:10"


class TestIndex:
    def test_index_is_a_table_of_contents_not_a_transcript(self):
        archive.write_batch([job("a long prompt that should not appear")], now=AT)
        index = archive.index_path().read_text()
        assert "a long prompt" not in index
        assert "batches/2026-07-27-0110.md" in index

    def test_index_does_not_grow_with_each_batch(self):
        archive.write_batch([job("a")], now=datetime(2026, 7, 25, 1, 0))
        one = archive.index_path().read_text()
        archive.write_batch([job("b")], now=datetime(2026, 7, 26, 1, 0))
        two = archive.index_path().read_text()
        # One line added per batch, not a whole appended section.
        assert len(two.splitlines()) == len(one.splitlines()) + 1

    def test_index_lists_newest_first(self):
        archive.write_batch([job("a")], now=datetime(2026, 7, 25, 1, 0))
        archive.write_batch([job("b")], now=datetime(2026, 7, 26, 1, 0))
        index = archive.index_path().read_text()
        assert index.index("2026-07-26") < index.index("2026-07-25")

    def test_regenerates_after_a_batch_is_deleted_by_hand(self):
        archive.write_batch([job("a")], now=datetime(2026, 7, 25, 1, 0))
        archive.write_batch([job("b")], now=datetime(2026, 7, 26, 1, 0))
        (archive.batches_dir() / "2026-07-25-0100.md").unlink()
        archive.regenerate_index()
        assert "2026-07-25" not in archive.index_path().read_text()


class TestLegacyMigration:
    def test_moves_old_append_only_index_aside(self):
        paths.ensure_dirs()
        archive.index_path().write_text("# Overnight results\n\n## Batch 2026-07-17\n- old stuff\n")
        archive.write_batch([job("new")], now=AT)
        legacy = (archive.batches_dir() / archive.LEGACY_NAME).read_text()
        assert "old stuff" in legacy
        assert "old stuff" not in archive.index_path().read_text()
        assert "Batches before v0.7" in archive.index_path().read_text()

    def test_legacy_sorts_last(self):
        paths.ensure_dirs()
        archive.index_path().write_text("# Overnight results\n\n- old\n")
        archive.write_batch([job("new")], now=AT)
        assert archive.list_batches()[-1].stamp == "legacy"

    def test_runs_only_once(self):
        paths.ensure_dirs()
        archive.index_path().write_text("original\n")
        archive.write_batch([job("a")], now=datetime(2026, 7, 25, 1, 0))
        archive.write_batch([job("b")], now=datetime(2026, 7, 26, 1, 0))
        assert (archive.batches_dir() / archive.LEGACY_NAME).read_text() == "original\n"


class TestCurrentBatch:
    def test_returns_only_the_newest_batch(self):
        archive.write_batch([job("older")], now=datetime(2026, 7, 25, 1, 0))
        archive.write_batch([job("newer")], now=datetime(2026, 7, 26, 1, 0))
        current = archive.current_batch_markdown()
        assert "newer" in current
        assert "older" not in current

    def test_none_when_no_batches(self):
        assert archive.current_batch_markdown() is None

    def test_skips_legacy_when_a_real_batch_exists(self):
        paths.ensure_dirs()
        archive.index_path().write_text("legacy content\n")
        archive.write_batch([job("real")], now=AT)
        assert "real" in archive.current_batch_markdown()
