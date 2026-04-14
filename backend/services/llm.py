import json
from math import ceil

from openai import AsyncOpenAI

from config import get_settings

SYSTEM_PROMPT = (
    "You are a clinical NLP assistant. Given extracted clinical entities and surrounding context from a medical "
    "document, map each entity to its standard code (SNOMED CT for diagnoses, RxNorm for medications, "
    "LOINC for labs). Return JSON only."
)


def _chunk_context(text: str, chunk_chars: int = 12000) -> list[str]:
    if not text:
        return [""]
    chunks = ceil(len(text) / chunk_chars)
    return [text[i * chunk_chars : (i + 1) * chunk_chars] for i in range(chunks)]


async def resolve_entities(raw_entities: list[dict], context: str) -> list[dict]:
    settings = get_settings()
    if not settings.openai_api_key or not raw_entities:
        return raw_entities

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    context_chunks = _chunk_context(context)
    merged: list[dict] = []

    for idx, chunk in enumerate(context_chunks):
        payload = {
            "entities": raw_entities,
            "context": chunk,
            "chunk_index": idx,
            "chunk_total": len(context_chunks),
        }
        response = await client.chat.completions.create(
            model="gpt-4o",
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

    return merged or raw_entities
