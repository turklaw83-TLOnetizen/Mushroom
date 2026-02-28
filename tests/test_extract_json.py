# ---- Tests for extract_json (from core/nodes/_common.py) ------------------
# extract_json is also exposed via core/citations.py's sibling module.
# Here we test the standalone function that will live in core/nodes/_common.py.

import json
import sys
from pathlib import Path

# Inline the function for testing before nodes are fully ported
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def extract_json(text: str, expect_list: bool = False):
    """Extract the first balanced JSON object or array from LLM output."""
    if not text:
        return None
    cleaned = text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        pass
    openers = ('[', '{') if expect_list else ('{', '[')
    for open_char in openers:
        close_char = ']' if open_char == '[' else '}'
        start = cleaned.find(open_char)
        if start == -1:
            continue
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(cleaned)):
            ch = cleaned[i]
            if escape:
                escape = False
                continue
            if ch == '\\':
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == open_char:
                depth += 1
            elif ch == close_char:
                depth -= 1
                if depth == 0:
                    candidate = cleaned[start:i + 1]
                    try:
                        return json.loads(candidate)
                    except (json.JSONDecodeError, ValueError):
                        break
    return None


class TestExtractJSON:
    def test_pure_json_object(self):
        result = extract_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_pure_json_array(self):
        result = extract_json('[1, 2, 3]', expect_list=True)
        assert result == [1, 2, 3]

    def test_json_in_markdown_fence(self):
        text = '```json\n{"charges": [{"name": "Assault"}]}\n```'
        result = extract_json(text)
        assert result["charges"][0]["name"] == "Assault"

    def test_json_with_prose(self):
        text = 'Here is the analysis:\n\n{"summary": "Test case summary"}\n\nPlease review.'
        result = extract_json(text)
        assert result["summary"] == "Test case summary"

    def test_nested_objects(self):
        text = '{"outer": {"inner": {"deep": true}}}'
        result = extract_json(text)
        assert result["outer"]["inner"]["deep"] is True

    def test_array_preference_with_expect_list(self):
        text = 'Results: [{"name": "Alice"}, {"name": "Bob"}]'
        result = extract_json(text, expect_list=True)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_empty_input(self):
        assert extract_json("") is None
        assert extract_json(None) is None

    def test_no_json_found(self):
        assert extract_json("This is just plain text.") is None

    def test_malformed_json(self):
        assert extract_json('{"key": value}') is None

    def test_string_with_braces(self):
        text = '{"message": "Use { and } carefully"}'
        result = extract_json(text)
        assert result["message"] == "Use { and } carefully"

    def test_multiple_json_objects_returns_first(self):
        text = '{"first": true} {"second": true}'
        result = extract_json(text)
        assert result == {"first": True}
