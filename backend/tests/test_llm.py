"""Unit tests for LLM service: chunking, fallback behavior."""

import asyncio

from services.llm import _chunk_context, resolve_entities


def test_chunk_empty_returns_single():
    assert _chunk_context("") == [""]


def test_chunk_short_text_returns_single():
    text = "This is short."
    result = _chunk_context(text)
    assert len(result) == 1
    assert result[0] == text


def test_chunk_splits_on_paragraph():
    text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
    result = _chunk_context(text, chunk_chars=30)
    assert len(result) >= 2
    # Each chunk should be a meaningful segment
    for chunk in result:
        assert len(chunk) > 0


def test_chunk_preserves_all_content():
    text = "A" * 100 + "\n\n" + "B" * 100 + "\n\n" + "C" * 100
    result = _chunk_context(text, chunk_chars=120)
    reassembled = "".join(result)
    assert reassembled == text


def test_resolve_entities_no_api_key_returns_raw():
    """Without an API key, resolve_entities should return raw_entities unchanged."""
    raw = [{"text": "Hypertension", "snomed_code": None}]
    result = asyncio.get_event_loop().run_until_complete(
        resolve_entities(raw, "Some clinical context")
    )
    assert result == raw


def test_resolve_entities_empty_returns_empty():
    result = asyncio.get_event_loop().run_until_complete(
        resolve_entities([], "Some context")
    )
    assert result == []
