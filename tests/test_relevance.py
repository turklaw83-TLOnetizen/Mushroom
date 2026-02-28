# Tests for core/relevance.py — citation extraction and relevance scoring

import pytest
from core.relevance import extract_citations_from_state, compute_relevance_scores


class TestExtractCitations:
    def test_empty_state(self):
        assert extract_citations_from_state({}) == {}

    def test_string_field_citations(self):
        state = {
            "case_summary": (
                "The defendant was seen [[source: report.pdf, p.3]] "
                "leaving the scene [[source: video.mp4, p.1]]."
            ),
        }
        counts = extract_citations_from_state(state)
        assert counts["report.pdf"] == 1
        assert counts["video.mp4"] == 1

    def test_list_field_citations(self):
        state = {
            "witnesses": [
                {"name": "Smith", "notes": "Saw event [[source: statement.pdf, p.2]]"},
            ],
        }
        counts = extract_citations_from_state(state)
        assert counts["statement.pdf"] == 1

    def test_repeated_citations_across_fields(self):
        state = {
            "case_summary": "Fact A [[source: a.pdf, p.1]] and [[source: a.pdf, p.3]]",
            "strategy_notes": "Based on [[source: a.pdf, p.1]]",
        }
        counts = extract_citations_from_state(state)
        assert counts["a.pdf"] == 3

    def test_dict_field_citations(self):
        state = {
            "voir_dire": {"question": "Source is [[source: juror.pdf, p.5]]"},
        }
        counts = extract_citations_from_state(state)
        assert counts["juror.pdf"] == 1

    def test_no_citations_in_plain_text(self):
        state = {
            "case_summary": "This is plain text with no citations.",
        }
        counts = extract_citations_from_state(state)
        assert len(counts) == 0

    def test_citation_without_page(self):
        state = {
            "case_summary": "Referenced [[source: doc.pdf]]",
        }
        counts = extract_citations_from_state(state)
        assert counts["doc.pdf"] == 1


class TestComputeRelevanceScores:
    def test_empty_citations(self):
        scores = compute_relevance_scores({}, {})
        assert scores == {}

    def test_single_file_gets_max_base(self):
        state = {"case_summary": "Test [[source: report.pdf, p.1]]"}
        scores = compute_relevance_scores(state, {})
        assert "report.pdf" in scores
        assert scores["report.pdf"]["score"] == 85  # max normalized, no tag boost
        assert scores["report.pdf"]["citations"] == 1
        assert scores["report.pdf"]["boost"] == 0

    def test_tag_boost_applied(self):
        state = {"case_summary": "Test [[source: report.pdf, p.1]]"}
        tags = {"report.pdf": ["Police Report"]}
        scores = compute_relevance_scores(state, tags, "criminal")
        assert scores["report.pdf"]["score"] == 100  # 85 + 15
        assert scores["report.pdf"]["boost"] == 15

    def test_score_capped_at_100(self):
        state = {"case_summary": "Test [[source: report.pdf, p.1]]"}
        tags = {"report.pdf": ["Police Report"]}
        scores = compute_relevance_scores(state, tags, "criminal")
        assert scores["report.pdf"]["score"] <= 100

    def test_multiple_files_relative_scoring(self):
        state = {
            "case_summary": (
                "File A [[source: a.pdf, p.1]] [[source: a.pdf, p.2]] "
                "File B [[source: b.pdf, p.1]]"
            ),
        }
        scores = compute_relevance_scores(state, {})
        assert scores["a.pdf"]["score"] > scores["b.pdf"]["score"]

    def test_civil_plaintiff_tag_boost(self):
        state = {"case_summary": "Injury [[source: records.pdf, p.1]]"}
        tags = {"records.pdf": ["Medical Records"]}
        scores = compute_relevance_scores(state, tags, "civil-plaintiff")
        assert scores["records.pdf"]["boost"] == 15  # Medical Records boost for civil-plaintiff
