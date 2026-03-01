"""Multi-model comparison — run the same analysis on multiple LLMs."""

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Cost per 1M tokens (approximate, as of 2026)
MODEL_COSTS = {
    "claude-sonnet": {"input": 3.0, "output": 15.0},
    "claude-haiku": {"input": 0.25, "output": 1.25},
    "claude-opus": {"input": 15.0, "output": 75.0},
    "grok-2": {"input": 2.0, "output": 10.0},
    "gpt-4o": {"input": 2.5, "output": 10.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.6},
}


@dataclass
class ModelResult:
    model_name: str
    output: str = ""
    tokens_input: int = 0
    tokens_output: int = 0
    duration_seconds: float = 0.0
    cost_estimate: float = 0.0
    error: Optional[str] = None


@dataclass
class ComparisonResult:
    results: list[ModelResult] = field(default_factory=list)
    total_duration: float = 0.0


def _get_available_models() -> list[str]:
    models = []
    if os.getenv("ANTHROPIC_API_KEY"):
        models.extend(["claude-sonnet", "claude-haiku", "claude-opus"])
    if os.getenv("XAI_API_KEY"):
        models.append("grok-2")
    if os.getenv("OPENAI_API_KEY"):
        models.extend(["gpt-4o", "gpt-4o-mini"])
    return models


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    costs = MODEL_COSTS.get(model, {"input": 5.0, "output": 15.0})
    return (input_tokens * costs["input"] + output_tokens * costs["output"]) / 1_000_000


def _run_single_model(model: str, prompt: str, system_prompt: str = "") -> ModelResult:
    """Run a single model and return the result."""
    start = time.time()
    result = ModelResult(model_name=model)

    try:
        if model.startswith("claude"):
            import anthropic
            client = anthropic.Anthropic()
            model_id = {
                "claude-sonnet": "claude-sonnet-4-20250514",
                "claude-haiku": "claude-haiku-4-20250514",
                "claude-opus": "claude-opus-4-20250514",
            }.get(model, "claude-sonnet-4-20250514")
            messages = [{"role": "user", "content": prompt}]
            kwargs = {"model": model_id, "max_tokens": 8192, "messages": messages}
            if system_prompt:
                kwargs["system"] = system_prompt
            resp = client.messages.create(**kwargs)
            result.output = resp.content[0].text
            result.tokens_input = resp.usage.input_tokens
            result.tokens_output = resp.usage.output_tokens

        elif model == "grok-2":
            from openai import OpenAI
            client = OpenAI(api_key=os.getenv("XAI_API_KEY"), base_url="https://api.x.ai/v1")
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            resp = client.chat.completions.create(model="grok-2-latest", messages=messages, max_tokens=8192)
            result.output = resp.choices[0].message.content or ""
            result.tokens_input = resp.usage.prompt_tokens if resp.usage else 0
            result.tokens_output = resp.usage.completion_tokens if resp.usage else 0

        elif model.startswith("gpt"):
            from openai import OpenAI
            client = OpenAI()
            model_id = {"gpt-4o": "gpt-4o", "gpt-4o-mini": "gpt-4o-mini"}.get(model, "gpt-4o")
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            resp = client.chat.completions.create(model=model_id, messages=messages, max_tokens=8192)
            result.output = resp.choices[0].message.content or ""
            result.tokens_input = resp.usage.prompt_tokens if resp.usage else 0
            result.tokens_output = resp.usage.completion_tokens if resp.usage else 0

    except Exception as e:
        result.error = str(e)
        logger.error("Model %s failed: %s", model, e)

    result.duration_seconds = round(time.time() - start, 2)
    result.cost_estimate = _estimate_cost(model, result.tokens_input, result.tokens_output)
    return result


def compare_models(
    prompt: str,
    models: list[str],
    system_prompt: str = "",
    max_workers: int = 3,
) -> ComparisonResult:
    """Run the same prompt on multiple models in parallel."""
    start = time.time()
    available = set(_get_available_models())
    valid_models = [m for m in models if m in available]

    if not valid_models:
        return ComparisonResult(results=[], total_duration=0)

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_run_single_model, m, prompt, system_prompt): m
            for m in valid_models
        }
        for future in as_completed(futures):
            results.append(future.result())

    return ComparisonResult(
        results=sorted(results, key=lambda r: r.model_name),
        total_duration=round(time.time() - start, 2),
    )


def diff_outputs(text_a: str, text_b: str) -> dict:
    """Simple diff between two model outputs."""
    lines_a = text_a.splitlines()
    lines_b = text_b.splitlines()
    common = set(lines_a) & set(lines_b)
    only_a = [l for l in lines_a if l not in common]
    only_b = [l for l in lines_b if l not in common]
    similarity = len(common) / max(len(set(lines_a) | set(lines_b)), 1)
    return {
        "similarity": round(similarity, 3),
        "lines_only_a": len(only_a),
        "lines_only_b": len(only_b),
        "common_lines": len(common),
        "sample_differences_a": only_a[:5],
        "sample_differences_b": only_b[:5],
    }
