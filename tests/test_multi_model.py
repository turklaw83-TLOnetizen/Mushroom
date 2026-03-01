"""Tests for multi-model comparison (Phase 16)."""
import pytest
from unittest.mock import patch, MagicMock


class TestMultiModel:
    def test_import(self):
        from core.multi_model import ModelComparer
        assert ModelComparer is not None

    def test_model_costs_defined(self):
        from core.multi_model import MODEL_COSTS
        assert "claude-sonnet" in MODEL_COSTS or len(MODEL_COSTS) > 0

    def test_comparer_init(self):
        from core.multi_model import ModelComparer
        comparer = ModelComparer()
        assert comparer is not None

    def test_diff_outputs(self):
        from core.multi_model import ModelComparer
        comparer = ModelComparer()
        diff = comparer.diff_outputs(
            "The defendant is guilty based on evidence.",
            "The evidence suggests defendant may be guilty.",
        )
        assert isinstance(diff, dict) or isinstance(diff, str)


class TestVectorStore:
    def test_import(self):
        from core.vector_store import VectorStore
        assert VectorStore is not None

    def test_init(self, tmp_path):
        try:
            from core.vector_store import VectorStore
            vs = VectorStore(str(tmp_path))
            assert vs is not None
        except ImportError:
            pytest.skip("sentence-transformers not installed")


class TestDocumentSummarizer:
    def test_import(self):
        from core.document_summarizer import summarize_document
        assert summarize_document is not None


class TestCasePrediction:
    def test_import(self):
        from core.case_prediction import predict_outcome, predict_settlement_range
        assert predict_outcome is not None
        assert predict_settlement_range is not None
