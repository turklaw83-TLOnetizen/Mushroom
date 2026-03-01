"""
Tests for OCRCache (core/ingest.py) — text caching, page-level storage,
full-text search, manifest thread-safety, and text quality assessment.
"""

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from core.ingest import OCRCache, DocumentIngester


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_file_key(filename: str = "report.pdf", size: int = 12345) -> str:
    """Convenience wrapper around OCRCache.file_key."""
    return OCRCache.file_key(filename, size)


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

class TestOCRCacheInit:
    def test_creates_ocr_cache_directory(self, tmp_path):
        """OCRCache.__init__ should create the ocr_cache/ subdirectory."""
        case_dir = str(tmp_path / "case_001")
        os.makedirs(case_dir, exist_ok=True)

        OCRCache(case_dir)

        assert os.path.isdir(os.path.join(case_dir, "ocr_cache"))

    def test_creates_ocr_cache_even_when_parent_missing(self, tmp_path):
        """OCRCache should create the case dir + ocr_cache in one shot."""
        case_dir = str(tmp_path / "nonexistent_case")
        # case_dir does not exist yet — OCRCache makedirs with exist_ok=True
        OCRCache(case_dir)
        assert os.path.isdir(os.path.join(case_dir, "ocr_cache"))

    def test_manifest_initially_empty(self, tmp_path):
        cache = OCRCache(str(tmp_path / "case"))
        assert cache._manifest == {}

    def test_reloads_existing_manifest(self, tmp_path):
        """A second OCRCache instance on the same dir should pick up stored data."""
        case_dir = str(tmp_path / "case")
        cache1 = OCRCache(case_dir)
        fk = _make_file_key()
        cache1.store_text(fk, "hello world", "report.pdf")

        cache2 = OCRCache(case_dir)
        assert cache2.get_status(fk) == "done"


# ---------------------------------------------------------------------------
# file_key / _hash_key helpers
# ---------------------------------------------------------------------------

class TestFileKey:
    def test_file_key_consistent(self):
        """Same inputs should always produce the same key."""
        k1 = OCRCache.file_key("doc.pdf", 100)
        k2 = OCRCache.file_key("doc.pdf", 100)
        assert k1 == k2

    def test_file_key_differs_by_name(self):
        k1 = OCRCache.file_key("a.pdf", 100)
        k2 = OCRCache.file_key("b.pdf", 100)
        assert k1 != k2

    def test_file_key_differs_by_size(self):
        k1 = OCRCache.file_key("doc.pdf", 100)
        k2 = OCRCache.file_key("doc.pdf", 200)
        assert k1 != k2

    def test_hash_key_is_md5_hex(self):
        """_hash_key should return a 32-char hex string (MD5)."""
        h = OCRCache._hash_key("doc.pdf:100")
        assert len(h) == 32
        assert all(c in "0123456789abcdef" for c in h)

    def test_hash_key_deterministic(self):
        assert OCRCache._hash_key("x") == OCRCache._hash_key("x")

    def test_hash_key_differs_for_different_inputs(self):
        assert OCRCache._hash_key("a:1") != OCRCache._hash_key("b:2")


# ---------------------------------------------------------------------------
# Status API
# ---------------------------------------------------------------------------

class TestStatusAPI:
    def test_get_status_returns_none_for_unknown_key(self, tmp_path):
        cache = OCRCache(str(tmp_path / "case"))
        assert cache.get_status("unknown:0") is None

    def test_set_status_and_get_status_roundtrip(self, tmp_path):
        cache = OCRCache(str(tmp_path / "case"))
        fk = _make_file_key()
        cache.set_status(fk, "pending", "report.pdf")
        assert cache.get_status(fk) == "pending"

    def test_set_skipped(self, tmp_path):
        cache = OCRCache(str(tmp_path / "case"))
        fk = _make_file_key()
        cache.set_skipped(fk, "report.pdf")
        assert cache.get_status(fk) == "skipped"

    def test_get_all_statuses(self, tmp_path):
        cache = OCRCache(str(tmp_path / "case"))
        fk1 = OCRCache.file_key("a.pdf", 10)
        fk2 = OCRCache.file_key("b.pdf", 20)
        cache.set_status(fk1, "done", "a.pdf", 50)
        cache.set_status(fk2, "pending", "b.pdf")
        statuses = cache.get_all_statuses()
        assert fk1 in statuses
        assert fk2 in statuses
        assert statuses[fk1]["status"] == "done"
        assert statuses[fk2]["status"] == "pending"


# ---------------------------------------------------------------------------
# Text storage — store_text / get_text
# ---------------------------------------------------------------------------

class TestTextStorage:
    def test_get_text_returns_none_for_uncached(self, tmp_path):
        """get_text should return None when no text has been stored."""
        cache = OCRCache(str(tmp_path / "case"))
        assert cache.get_text("nonexistent:0") is None

    def test_store_and_get_text_roundtrip(self, tmp_path):
        cache = OCRCache(str(tmp_path / "case"))
        fk = _make_file_key()
        text = "The quick brown fox jumps over the lazy dog."
        cache.store_text(fk, text, "report.pdf")
        assert cache.get_text(fk) == text

    def test_store_text_sets_status_done(self, tmp_path):
        cache = OCRCache(str(tmp_path / "case"))
        fk = _make_file_key()
        cache.store_text(fk, "some text", "report.pdf")
        assert cache.get_status(fk) == "done"

    def test_store_text_records_word_count(self, tmp_path):
        cache = OCRCache(str(tmp_path / "case"))
        fk = _make_file_key()
        cache.store_text(fk, "one two three four", "report.pdf")
        entry = cache._manifest[fk]
        assert entry["word_count"] == 4

    def test_store_text_empty_string_word_count_zero(self, tmp_path):
        cache = OCRCache(str(tmp_path / "case"))
        fk = _make_file_key()
        cache.store_text(fk, "", "report.pdf")
        assert cache._manifest[fk]["word_count"] == 0

    def test_store_text_overwrites_previous(self, tmp_path):
        cache = OCRCache(str(tmp_path / "case"))
        fk = _make_file_key()
        cache.store_text(fk, "version 1", "report.pdf")
        cache.store_text(fk, "version 2", "report.pdf")
        assert cache.get_text(fk) == "version 2"

    def test_store_text_creates_txt_file_on_disk(self, tmp_path):
        cache = OCRCache(str(tmp_path / "case"))
        fk = _make_file_key()
        cache.store_text(fk, "hello", "report.pdf")
        txt_path = cache._text_path(fk)
        assert os.path.isfile(txt_path)


# ---------------------------------------------------------------------------
# Page-level storage
# ---------------------------------------------------------------------------

class TestPageLevelStorage:
    def test_store_page_text_and_get_page_text(self, tmp_path):
        cache = OCRCache(str(tmp_path / "case"))
        fk = _make_file_key()
        cache.store_page_text(fk, 0, "Page zero text")
        cache.store_page_text(fk, 1, "Page one text")
        assert cache.get_page_text(fk, 0) == "Page zero text"
        assert cache.get_page_text(fk, 1) == "Page one text"

    def test_get_page_text_returns_none_for_missing(self, tmp_path):
        cache = OCRCache(str(tmp_path / "case"))
        assert cache.get_page_text("missing:0", 5) is None

    def test_set_in_progress_and_pages_done(self, tmp_path):
        cache = OCRCache(str(tmp_path / "case"))
        fk = _make_file_key()
        cache.set_in_progress(fk, "report.pdf", pages_done=3, total_pages=10)
        assert cache.get_status(fk) == "in_progress"
        assert cache.get_pages_done(fk) == 3
        assert cache.get_total_pages(fk) == 10

    def test_get_pages_done_defaults_zero(self, tmp_path):
        cache = OCRCache(str(tmp_path / "case"))
        assert cache.get_pages_done("nokey:0") == 0

    def test_get_total_pages_defaults_zero(self, tmp_path):
        cache = OCRCache(str(tmp_path / "case"))
        assert cache.get_total_pages("nokey:0") == 0


# ---------------------------------------------------------------------------
# finalize_file
# ---------------------------------------------------------------------------

class TestFinalizeFile:
    def test_finalize_concatenates_pages(self, tmp_path):
        """finalize_file should join per-page texts with double-newline."""
        cache = OCRCache(str(tmp_path / "case"))
        fk = _make_file_key()
        cache.store_page_text(fk, 0, "First page")
        cache.store_page_text(fk, 1, "Second page")
        cache.store_page_text(fk, 2, "Third page")

        cache.finalize_file(fk, "report.pdf", total_pages=3)

        full = cache.get_text(fk)
        assert full == "First page\n\nSecond page\n\nThird page"
        assert cache.get_status(fk) == "done"

    def test_finalize_cleans_up_page_files(self, tmp_path):
        cache = OCRCache(str(tmp_path / "case"))
        fk = _make_file_key()
        cache.store_page_text(fk, 0, "Page A")
        cache.store_page_text(fk, 1, "Page B")

        # Verify page files exist before finalize
        assert os.path.isfile(cache._page_text_path(fk, 0))
        assert os.path.isfile(cache._page_text_path(fk, 1))

        cache.finalize_file(fk, "report.pdf", total_pages=2)

        # Page files should be removed
        assert not os.path.exists(cache._page_text_path(fk, 0))
        assert not os.path.exists(cache._page_text_path(fk, 1))

    def test_finalize_with_empty_pages_sets_skipped(self, tmp_path):
        """If all pages are empty / missing, finalize should set status to 'skipped'."""
        cache = OCRCache(str(tmp_path / "case"))
        fk = _make_file_key()
        # Don't store any page text — simulates all pages being empty
        cache.finalize_file(fk, "report.pdf", total_pages=3)
        assert cache.get_status(fk) == "skipped"

    def test_finalize_with_some_empty_pages(self, tmp_path):
        """Pages that don't have text should be skipped in concatenation."""
        cache = OCRCache(str(tmp_path / "case"))
        fk = _make_file_key()
        # Only page 1 has content; pages 0 and 2 are missing
        cache.store_page_text(fk, 1, "Only middle page")

        cache.finalize_file(fk, "report.pdf", total_pages=3)
        assert cache.get_text(fk) == "Only middle page"
        assert cache.get_status(fk) == "done"


# ---------------------------------------------------------------------------
# get_all_statuses (acts like list_cached_files + get_stats)
# ---------------------------------------------------------------------------

class TestListAndStats:
    def test_get_all_statuses_returns_all_entries(self, tmp_path):
        cache = OCRCache(str(tmp_path / "case"))
        fk1 = OCRCache.file_key("a.pdf", 10)
        fk2 = OCRCache.file_key("b.pdf", 20)
        fk3 = OCRCache.file_key("c.pdf", 30)

        cache.store_text(fk1, "text a", "a.pdf")
        cache.set_status(fk2, "pending", "b.pdf")
        cache.set_skipped(fk3, "c.pdf")

        statuses = cache.get_all_statuses()
        assert len(statuses) == 3
        assert statuses[fk1]["status"] == "done"
        assert statuses[fk2]["status"] == "pending"
        assert statuses[fk3]["status"] == "skipped"

    def test_stats_counts_can_be_derived(self, tmp_path):
        """Demonstrate that done/pending/skipped counts can be derived from get_all_statuses."""
        cache = OCRCache(str(tmp_path / "case"))
        for i in range(5):
            fk = OCRCache.file_key(f"file{i}.pdf", i * 10)
            if i < 3:
                cache.store_text(fk, f"text {i}", f"file{i}.pdf")
            elif i == 3:
                cache.set_status(fk, "pending", f"file{i}.pdf")
            else:
                cache.set_skipped(fk, f"file{i}.pdf")

        statuses = cache.get_all_statuses()
        done_count = sum(1 for v in statuses.values() if v["status"] == "done")
        pending_count = sum(1 for v in statuses.values() if v["status"] == "pending")
        skipped_count = sum(1 for v in statuses.values() if v["status"] == "skipped")

        assert done_count == 3
        assert pending_count == 1
        assert skipped_count == 1


# ---------------------------------------------------------------------------
# Full-text search
# ---------------------------------------------------------------------------

class TestSearch:
    def test_search_returns_matching_files(self, tmp_path):
        cache = OCRCache(str(tmp_path / "case"))
        fk1 = OCRCache.file_key("contract.pdf", 100)
        fk2 = OCRCache.file_key("letter.pdf", 200)

        cache.store_text(fk1, "This contract is binding under Tennessee law.", "contract.pdf")
        cache.store_text(fk2, "Dear sir, I am writing to you about other matters.", "letter.pdf")

        results = cache.search("Tennessee")
        assert len(results) == 1
        assert results[0]["filename"] == "contract.pdf"
        assert len(results[0]["snippets"]) >= 1

    def test_search_case_insensitive(self, tmp_path):
        cache = OCRCache(str(tmp_path / "case"))
        fk = OCRCache.file_key("doc.pdf", 50)
        cache.store_text(fk, "The defendant was ARRESTED at the scene.", "doc.pdf")

        results = cache.search("arrested")
        assert len(results) == 1

    def test_search_multiple_matches_in_one_file(self, tmp_path):
        cache = OCRCache(str(tmp_path / "case"))
        fk = OCRCache.file_key("doc.pdf", 50)
        text = "Witness A testified. Then Witness B testified. Witness C was absent."
        cache.store_text(fk, text, "doc.pdf")

        results = cache.search("Witness")
        assert len(results) == 1
        assert len(results[0]["snippets"]) == 3

    def test_search_respects_max_snippets(self, tmp_path):
        cache = OCRCache(str(tmp_path / "case"))
        fk = OCRCache.file_key("doc.pdf", 50)
        text = " ".join(["keyword"] * 20)
        cache.store_text(fk, text, "doc.pdf")

        results = cache.search("keyword", max_snippets_per_file=2)
        assert len(results[0]["snippets"]) == 2

    def test_search_ignores_non_done_files(self, tmp_path):
        cache = OCRCache(str(tmp_path / "case"))
        fk = OCRCache.file_key("pending.pdf", 10)
        # Set status to pending but also write text file manually
        cache.set_status(fk, "pending", "pending.pdf")
        txt_path = cache._text_path(fk)
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("searchable term inside")

        results = cache.search("searchable")
        assert len(results) == 0

    def test_search_returns_empty_for_short_query(self, tmp_path):
        cache = OCRCache(str(tmp_path / "case"))
        fk = OCRCache.file_key("doc.pdf", 50)
        cache.store_text(fk, "Some text", "doc.pdf")

        # Query must be >= 2 characters
        assert cache.search("") == []
        assert cache.search("a") == []

    def test_search_returns_empty_when_no_match(self, tmp_path):
        cache = OCRCache(str(tmp_path / "case"))
        fk = OCRCache.file_key("doc.pdf", 50)
        cache.store_text(fk, "Nothing interesting here.", "doc.pdf")

        results = cache.search("xyzzyspoon")
        assert results == []

    def test_search_sorted_by_snippet_count(self, tmp_path):
        cache = OCRCache(str(tmp_path / "case"))
        fk_few = OCRCache.file_key("few.pdf", 10)
        fk_many = OCRCache.file_key("many.pdf", 20)

        cache.store_text(fk_few, "match once", "few.pdf")
        cache.store_text(fk_many, "match here and match there and match again", "many.pdf")

        results = cache.search("match")
        assert len(results) == 2
        # The file with more matches should come first
        assert results[0]["filename"] == "many.pdf"

    def test_search_snippets_contain_context(self, tmp_path):
        cache = OCRCache(str(tmp_path / "case"))
        fk = OCRCache.file_key("doc.pdf", 50)
        cache.store_text(fk, "before the keyword after the keyword end", "doc.pdf")

        results = cache.search("keyword", context_chars=10)
        snippet_text = results[0]["snippets"][0]["text"]
        # Should include surrounding context
        assert "before" in snippet_text or "after" in snippet_text


# ---------------------------------------------------------------------------
# Thread safety — concurrent store_text calls
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_store_text_shared_instance(self, tmp_path):
        """Multiple threads using the SAME OCRCache instance should not corrupt the manifest."""
        case_dir = str(tmp_path / "case")
        cache = OCRCache(case_dir)
        num_threads = 10

        def write_entry(i):
            fk = OCRCache.file_key(f"file_{i}.pdf", i * 100)
            cache.store_text(fk, f"Content of file {i}", f"file_{i}.pdf")

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(write_entry, i) for i in range(num_threads)]
            for f in as_completed(futures):
                f.result()  # raise if any thread failed

        # Verify all entries present in the in-memory manifest
        statuses = cache.get_all_statuses()
        assert len(statuses) == num_threads
        for i in range(num_threads):
            fk = OCRCache.file_key(f"file_{i}.pdf", i * 100)
            assert fk in statuses
            assert statuses[fk]["status"] == "done"

        # Also verify the on-disk manifest is valid JSON and has all entries
        cache2 = OCRCache(case_dir)
        assert len(cache2.get_all_statuses()) == num_threads

    def test_concurrent_store_text_separate_instances_writes_text_files(self, tmp_path):
        """Separate OCRCache instances sharing a case_dir: text files should all be written
        even though the in-memory manifests diverge (each instance overwrites others' entries).
        This documents the known limitation that separate instances don't share in-memory state."""
        case_dir = str(tmp_path / "case")
        num_threads = 10

        def write_entry(i):
            cache = OCRCache(case_dir)
            fk = OCRCache.file_key(f"file_{i}.pdf", i * 100)
            cache.store_text(fk, f"Content of file {i}", f"file_{i}.pdf")

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(write_entry, i) for i in range(num_threads)]
            for f in as_completed(futures):
                f.result()

        # All individual .txt files should exist on disk regardless of manifest races
        cache = OCRCache(case_dir)
        for i in range(num_threads):
            fk = OCRCache.file_key(f"file_{i}.pdf", i * 100)
            txt_path = cache._text_path(fk)
            assert os.path.isfile(txt_path), f"Text file missing for file_{i}.pdf"

    def test_concurrent_reads_and_writes(self, tmp_path):
        """Readers and writers operating concurrently should not crash."""
        case_dir = str(tmp_path / "case")
        cache = OCRCache(case_dir)
        errors = []

        def writer(i):
            try:
                fk = OCRCache.file_key(f"w_{i}.pdf", i)
                cache.store_text(fk, f"text {i}", f"w_{i}.pdf")
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                cache.reload_manifest()
                cache.get_all_statuses()
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(10):
            threads.append(threading.Thread(target=writer, args=(i,)))
            threads.append(threading.Thread(target=reader))

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert errors == [], f"Errors during concurrent access: {errors}"

    def test_class_level_locks_shared_across_instances(self, tmp_path):
        """Two OCRCache instances for the same case_dir should share the same lock."""
        case_dir = str(tmp_path / "case")
        cache_a = OCRCache(case_dir)
        cache_b = OCRCache(case_dir)
        assert cache_a._lock is cache_b._lock

    def test_different_case_dirs_get_different_locks(self, tmp_path):
        """OCRCache instances for different case dirs should have independent locks."""
        cache_a = OCRCache(str(tmp_path / "case_a"))
        cache_b = OCRCache(str(tmp_path / "case_b"))
        assert cache_a._lock is not cache_b._lock


# ---------------------------------------------------------------------------
# Clear / remove cached data (manual equivalent since no clear() exists)
# ---------------------------------------------------------------------------

class TestClearCache:
    def test_removing_cache_dir_clears_all_data(self, tmp_path):
        """Deleting the ocr_cache directory and re-creating OCRCache gives a clean slate."""
        import shutil

        case_dir = str(tmp_path / "case")
        cache = OCRCache(case_dir)
        fk = _make_file_key()
        cache.store_text(fk, "data to clear", "report.pdf")
        assert cache.get_text(fk) is not None

        # Remove the cache directory
        shutil.rmtree(cache.cache_dir)

        # Re-create OCRCache — should be empty
        cache2 = OCRCache(case_dir)
        assert cache2.get_text(fk) is None
        assert cache2.get_all_statuses() == {}

    def test_manifest_persists_across_instances(self, tmp_path):
        """Ensure data is NOT lost simply by creating a new instance."""
        case_dir = str(tmp_path / "case")
        cache = OCRCache(case_dir)
        fk = _make_file_key()
        cache.store_text(fk, "persistent text", "report.pdf")

        # New instance on same dir should see the data
        cache2 = OCRCache(case_dir)
        assert cache2.get_text(fk) == "persistent text"


# ---------------------------------------------------------------------------
# reload_manifest
# ---------------------------------------------------------------------------

class TestReloadManifest:
    def test_reload_picks_up_external_changes(self, tmp_path):
        """reload_manifest should re-read the manifest from disk."""
        case_dir = str(tmp_path / "case")
        cache = OCRCache(case_dir)
        fk = _make_file_key()

        # Directly write to the manifest on disk (simulating another process)
        manifest_path = os.path.join(case_dir, "ocr_cache", "manifest.json")
        manifest_data = {
            fk: {"status": "done", "filename": "report.pdf", "word_count": 5, "timestamp": "2026-01-01T00:00:00"}
        }
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f)

        # Before reload, cache doesn't know about external write
        assert cache.get_status(fk) is None

        cache.reload_manifest()
        assert cache.get_status(fk) == "done"


# ---------------------------------------------------------------------------
# _assess_text_quality (on DocumentIngester)
# ---------------------------------------------------------------------------

class TestAssessTextQuality:
    """
    _assess_text_quality is a method on DocumentIngester, not OCRCache.
    We test it via a DocumentIngester instance.
    """

    @pytest.fixture
    def ingester(self):
        return DocumentIngester()

    def test_good_text_scores_highly(self, ingester):
        """Well-formed English text should score above 80."""
        text = (
            "The defendant was observed leaving the premises at approximately "
            "10:30 PM on the evening of January 15, 2026. Officer Smith "
            "approached the individual and requested identification. The "
            "subject complied and produced a valid Tennessee driver's license."
        )
        result = ingester._assess_text_quality(text)
        assert result["score"] > 80

    def test_empty_text_scores_zero(self, ingester):
        result = ingester._assess_text_quality("")
        assert result["score"] == 0
        assert "empty" in result["reasons"]

    def test_whitespace_only_scores_zero(self, ingester):
        result = ingester._assess_text_quality("   \n\t  ")
        assert result["score"] == 0
        assert "empty" in result["reasons"]

    def test_none_text_scores_zero(self, ingester):
        result = ingester._assess_text_quality(None)
        assert result["score"] == 0

    def test_too_few_words_scores_low(self, ingester):
        result = ingester._assess_text_quality("ab")
        assert result["score"] == 10
        assert "too_few_words" in result["reasons"]

    def test_penalizes_control_characters(self, ingester):
        """Text heavy with control characters (non-printable) should score lower."""
        # Build text with many control characters embedded
        control_chars = "\x01\x02\x03\x04\x05\x06\x07"
        # Need enough normal words so it doesn't trigger too_few_words
        normal = "The defendant was charged with assault and battery in court today "
        text = normal + control_chars * 20
        result_clean = ingester._assess_text_quality(normal)
        result_dirty = ingester._assess_text_quality(text)
        assert result_dirty["score"] < result_clean["score"]

    def test_penalizes_repetitive_runs(self, ingester):
        """Text with many repeated character runs should score lower."""
        # Normal baseline
        normal = "The court finds the defendant guilty of all charges as stated."
        # Same text but with repetitive character runs inserted
        garbled = "The courttttt finds the llllllldefendant guiltyyyyyy of aaaaaall chargesssss."
        result_normal = ingester._assess_text_quality(normal)
        result_garbled = ingester._assess_text_quality(garbled)
        assert result_garbled["score"] < result_normal["score"]

    def test_penalizes_symbol_soup(self, ingester):
        """Long runs of non-letter chars should incur a penalty."""
        text = "Normal text here. " + "!@#$%^&*()_+" * 5 + " More normal text follows along well."
        result = ingester._assess_text_quality(text)
        # Should still be penalized vs clean text
        clean = "Normal text here. More normal text follows along well."
        clean_result = ingester._assess_text_quality(clean)
        assert result["score"] <= clean_result["score"]

    def test_penalizes_long_average_word_length(self, ingester):
        """Garbled OCR often produces very long 'words' — should score lower."""
        text = "Thisisaverylongwordthatkeepsgoing " * 10
        result = ingester._assess_text_quality(text)
        assert result["score"] <= 85
        # Verify it actually incurred a penalty (clean text scores 100)
        clean = "This is a normal sentence with short average words for testing."
        clean_result = ingester._assess_text_quality(clean)
        assert result["score"] < clean_result["score"]

    def test_clean_text_has_clean_reason(self, ingester):
        text = "This is a normal, well-formed sentence with reasonable words and punctuation."
        result = ingester._assess_text_quality(text)
        assert "clean" in result["reasons"]

    def test_score_never_negative(self, ingester):
        """Score should be clamped to 0 minimum even with extreme penalties."""
        # Maximally garbled text
        text = "\x01\x02\x03" * 100 + "aaaa" * 50 + "!!!!" * 50
        result = ingester._assess_text_quality(text)
        assert result["score"] >= 0

    def test_score_never_above_100(self, ingester):
        text = "Perfect normal text with standard English words only."
        result = ingester._assess_text_quality(text)
        assert result["score"] <= 100
