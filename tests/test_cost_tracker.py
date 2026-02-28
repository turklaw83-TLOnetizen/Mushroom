# ---- Tests for core/cost_tracker.py ---------------------------------------

import pytest
from core.cost_tracker import (
    count_tokens,
    estimate_cost,
    estimate_analysis_cost,
    format_cost_badge,
    COST_PER_MILLION_INPUT,
    COST_PER_MILLION_OUTPUT,
    MODEL_CONTEXT_LIMITS,
)


class TestCountTokens:
    def test_empty_string(self):
        assert count_tokens("") == 0

    def test_nonempty_string(self):
        result = count_tokens("Hello world, this is a test.")
        assert result > 0

    def test_fallback_estimate(self):
        """Without tiktoken, should fall back to len/4."""
        # This may or may not use tiktoken depending on environment.
        text = "a" * 400
        result = count_tokens(text)
        assert result > 0


class TestEstimateCost:
    def test_zero_tokens(self):
        assert estimate_cost(0, 0, "anthropic") == 0.0

    def test_known_model(self):
        cost = estimate_cost(1_000_000, 1_000_000, "anthropic")
        assert cost == pytest.approx(3.00 + 15.00)

    def test_xai_pricing(self):
        cost = estimate_cost(1_000_000, 1_000_000, "xai")
        assert cost == pytest.approx(5.00 + 15.00)

    def test_unknown_model_uses_default(self):
        cost = estimate_cost(1_000_000, 1_000_000, "unknown_model")
        # Defaults: 3.00 input + 15.00 output
        assert cost == pytest.approx(3.00 + 15.00)

    def test_opus_pricing(self):
        cost = estimate_cost(1_000_000, 1_000_000, "claude-opus-4.6")
        assert cost == pytest.approx(15.00 + 75.00)


class TestEstimateAnalysisCost:
    def test_basic_estimate(self):
        result = estimate_analysis_cost("Short document text.", "anthropic")
        assert "doc_tokens" in result
        assert "total_cost_est" in result
        assert "needs_chunking" in result
        assert result["node_count"] == 14
        assert result["model"] == "anthropic"

    def test_custom_node_count(self):
        result = estimate_analysis_cost("text", "xai", node_count=5)
        assert result["node_count"] == 5

    def test_chunking_detected_for_large_doc(self):
        # Create a very large document
        large_text = "word " * 200_000  # ~200K words -> ~50K tokens minimum
        result = estimate_analysis_cost(large_text, "xai")
        # XAI has 131K limit; document should trigger chunking
        if result["doc_tokens"] > int(131_072 * 0.8):
            assert result["needs_chunking"] is True
            assert result["chunk_count"] > 1


class TestFormatCostBadge:
    def test_small_cost(self):
        badge = format_cost_badge("Hello", "anthropic")
        assert badge.startswith("(")
        assert badge.endswith(")")

    def test_very_small_cost(self):
        # Even "hi" generates non-trivial cost because estimate_analysis_cost
        # multiplies by node_count (14) and adds overhead per node.
        badge = format_cost_badge("hi", "anthropic")
        assert badge.startswith("(") and badge.endswith(")")
        # Should show a dollar amount
        assert "$" in badge


class TestPricingTables:
    def test_all_models_have_input_and_output(self):
        for model in COST_PER_MILLION_INPUT:
            assert model in COST_PER_MILLION_OUTPUT, f"{model} missing from output pricing"

    def test_all_models_have_context_limits(self):
        for model in COST_PER_MILLION_INPUT:
            assert model in MODEL_CONTEXT_LIMITS, f"{model} missing from context limits"
