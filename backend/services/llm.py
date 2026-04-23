import asyncio
import json
import logging
from math import ceil

from openai import AsyncOpenAI

from config import get_settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a clinical NLP assistant. Given extracted clinical entities and surrounding \
context from a medical document, map each entity to its standard code.

For each entity, return the original fields plus the resolved code. Return a JSON \
object with a single key "entities" containing an array of objects.

Entity types and expected fields:
- Diagnoses: {"text": "...", "snomed_code": "123456" or null, "negated": true/false}
- Medications: {"name": "...", "rxnorm_code": "123456" or null, "dose": "10 mg" or null, "frequency": "daily" or null}
- Labs: {"name": "...", "loinc_code": "12345-6" or null, "value": "..." or null, "status": "resulted"|"pending"}

Use SNOMED CT codes for diagnoses, RxNorm codes for medications, LOINC codes for labs. \
If you cannot determine a code with confidence, return null for that field. \
Do not invent codes. Return JSON only."""


def _chunk_context(text: str, chunk_chars: int = 12000) -> list[str]:
    """Split text on paragraph/sentence boundaries to avoid cutting mid-entity."""
    if not text:
        return [""]
    if len(text) <= chunk_chars:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_chars
        if end >= len(text):
            chunks.append(text[start:])
            break
        # Try to break at a paragraph boundary first, then sentence
        break_at = text.rfind("\n\n", start, end)
        if break_at == -1 or break_at <= start:
            break_at = text.rfind(". ", start, end)
        if break_at == -1 or break_at <= start:
            break_at = text.rfind("\n", start, end)
        if break_at == -1 or break_at <= start:
            break_at = end  # fallback: hard cut
        else:
            break_at += 1  # include the delimiter
        chunks.append(text[start:break_at])
        start = break_at

    return chunks


def _make_client() -> tuple[AsyncOpenAI, str] | None:
    """Return (client, model) using OpenRouter if key is set, else direct OpenAI."""
    settings = get_settings()
    if settings.openrouter_api_key:
        client = AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "https://transitionguard.app",
                "X-Title": "TransitionGuard",
            },
        )
        return client, settings.openrouter_model
    if settings.openai_api_key:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        return client, "gpt-4o"
    return None


async def resolve_entities(raw_entities: list[dict], context: str) -> list[dict]:
    if not raw_entities:
        return raw_entities

    result = _make_client()
    if result is None:
        return raw_entities

    client, model = result
    context_chunks = _chunk_context(context)
    merged: list[dict] = []

    for idx, chunk in enumerate(context_chunks):
        payload = {
            "entities": raw_entities,
            "context": chunk,
            "chunk_index": idx,
            "chunk_total": len(context_chunks),
        }

        for attempt in range(2):
            try:
                response = await client.chat.completions.create(
                    model=model,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": json.dumps(payload)},
                    ],
                    temperature=0,
                )

                content = response.choices[0].message.content or "{}"
                parsed = json.loads(content)
                resolved = parsed.get("entities", [])
                if isinstance(resolved, list):
                    merged.extend(resolved)
                break
            except (json.JSONDecodeError, KeyError, IndexError) as exc:
                logger.warning("LLM returned invalid JSON (chunk %d): %s", idx, exc)
                break
            except Exception as exc:
                if attempt == 0:
                    logger.warning("LLM API call failed (chunk %d), retrying: %s", idx, exc)
                    await asyncio.sleep(2)
                else:
                    logger.error("LLM API call failed after retry (chunk %d): %s", idx, exc)

    return merged or raw_entities
