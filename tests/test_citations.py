# ---- Tests for core/citations.py ------------------------------------------

import pytest
from core.citations import (
    CITATION_INSTRUCTION,
    format_docs_with_sources,
    render_with_references,
)


class MockDocument:
    """Mimics a LangChain Document for testing."""
    def __init__(self, page_content, metadata=None):
        self.page_content = page_content
        self.metadata = metadata or {}


class TestFormatDocsWithSources:
    def test_empty_docs(self):
        assert format_docs_with_sources([]) == "(No documents provided)"

    def test_single_doc(self):
        doc = MockDocument("Test content", {"source": "file.pdf", "page": 1})
        result = format_docs_with_sources([doc])
        assert "SOURCE: file.pdf" in result
        assert "Page 1" in result
        assert "Test content" in result

    def test_multiple_docs(self):
        docs = [
            MockDocument("Content A", {"source": "a.pdf"}),
            MockDocument("Content B", {"source": "b.pdf", "page": 3}),
        ]
        result = format_docs_with_sources(docs)
        assert "SOURCE: a.pdf" in result
        assert "SOURCE: b.pdf" in result

    def test_max_docs_limit(self):
        docs = [MockDocument(f"Content {i}", {"source": f"file{i}.pdf"})
                for i in range(10)]
        result = format_docs_with_sources(docs, max_docs=3)
        assert result.count("SOURCE:") == 3

    def test_max_chars_limit(self):
        docs = [MockDocument("x" * 1000, {"source": f"file{i}.pdf"})
                for i in range(10)]
        result = format_docs_with_sources(docs, max_chars=500)
        assert len(result) <= 600  # Some overhead from headers

    def test_file_tag(self):
        doc = MockDocument("Content", {"source": "report.pdf", "file_tag": "Police Report"})
        result = format_docs_with_sources([doc])
        assert "Police Report" in result

    def test_section_title(self):
        doc = MockDocument("Content", {"source": "brief.pdf", "section_title": "Introduction"})
        result = format_docs_with_sources([doc])
        assert "Section: Introduction" in result


class TestRenderWithReferences:
    def test_empty_text(self):
        assert render_with_references("") == ""

    def test_no_citations(self):
        text = "This text has no citations."
        assert render_with_references(text) == text

    def test_single_citation(self):
        text = "The defendant was present [[source: report.pdf, p.3]] at the scene."
        result = render_with_references(text)
        assert "[^1]" in result
        assert "report.pdf, p.3" in result

    def test_multiple_citations(self):
        text = "Fact one [[source: a.pdf, p.1]] and fact two [[source: b.pdf, p.5]]."
        result = render_with_references(text)
        assert "[^1]" in result
        assert "[^2]" in result

    def test_duplicate_citation_reuses_number(self):
        text = "First [[source: a.pdf, p.1]] and again [[source: a.pdf, p.1]]."
        result = render_with_references(text)
        # Both inline refs should be [^1], plus one footnote definition [^1]:
        # So total occurrences of "[^1]" = 3 (2 inline + 1 footnote)
        assert result.count("[^1]") == 3
        # Only one footnote definition
        assert result.count("[^1]:") == 1

    def test_citation_without_page(self):
        text = "See [[source: document.pdf]] for details."
        result = render_with_references(text)
        assert "[^1]" in result
        assert "document.pdf" in result


class TestCitationInstruction:
    def test_instruction_exists(self):
        assert "CITATION RULE" in CITATION_INSTRUCTION
        assert "[[source:" in CITATION_INSTRUCTION
