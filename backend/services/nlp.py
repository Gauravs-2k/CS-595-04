from collections import defaultdict

import spacy

from services.llm import resolve_entities

_NLP_MODEL = "en_core_sci_lg"

_nlp = None


def _get_nlp():
    """Load spaCy model on first use; falls back to a blank English pipeline if unavailable."""
    global _nlp
    if _nlp is None:
        try:
            _nlp = spacy.load(_NLP_MODEL)
        except OSError:
            _nlp = spacy.blank("en")
    return _nlp


def _group_entities(doc) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for ent in doc.ents:
        line_no = doc.text[: ent.start_char].count("\n") + 1
        item = {
            "text": ent.text,
            "label": ent.label_,
            "source_line": line_no,
        }
        grouped[ent.label_].append(item)
    return grouped


async def extract_entities(text: str) -> dict:
    if not text:
        return {
            "diagnoses": [],
            "medications": [],
            "labs": [],
            "referrals": [],
            "follow_up_tasks": [],
            "care_plan": [],
        }

    doc = _get_nlp()(text)
    grouped = _group_entities(doc)

    diagnoses = [
        {"text": d["text"], "snomed_code": None, "negated": False, "source_line": d["source_line"]}
        # en_core_web_md doesn't produce DISEASE; rely on keyword extraction below
        for d in grouped.get("DISEASE", [])
    ]
    meds = [
        {
            "name": m["text"],
            "rxnorm_code": None,
            "dose": None,
            "frequency": None,
            "source_line": m["source_line"],
        }
        # en_core_web_md doesn't produce CHEMICAL; rely on keyword extraction below
        for m in grouped.get("CHEMICAL", [])
    ]
    labs = [
        {"name": l["text"], "loinc_code": None, "value": None, "status": "resulted", "source_line": l["source_line"]}
        for l in grouped.get("LAB_VALUE", [])
    ]

    # Heuristic keyword extraction complements/supplements the NER model
    referrals = []
    follow_up_tasks = []
    for idx, line in enumerate(text.splitlines(), start=1):
        lower = line.lower()
        if "referral" in lower or "consult" in lower:
            referrals.append({"specialty": line.strip(), "provider": None, "urgency": None, "source_line": idx})
        if "follow" in lower or "return" in lower or "appointment" in lower:
            follow_up_tasks.append({"description": line.strip(), "timeframe": None, "source_line": idx})
        if "pending" in lower and line.strip():
            labs.append({"name": line.strip(), "loinc_code": None, "value": None, "status": "pending", "source_line": idx})

    raw_entities = diagnoses + meds + labs
    resolved = await resolve_entities(raw_entities=raw_entities, context=text)

    for item in resolved:
        if "snomed_code" in item:
            for diag in diagnoses:
                if diag["text"].lower() == item.get("text", "").lower():
                    diag["snomed_code"] = item.get("snomed_code")
                    diag["negated"] = bool(item.get("negated", False))
        if "rxnorm_code" in item:
            for med in meds:
                if med["name"].lower() == item.get("text", "").lower() or med["name"].lower() == item.get("name", "").lower():
                    med["rxnorm_code"] = item.get("rxnorm_code")
                    med["dose"] = item.get("dose")
                    med["frequency"] = item.get("frequency")
        if "loinc_code" in item:
            for lab in labs:
                if lab["name"].lower() == item.get("text", "").lower() or lab["name"].lower() == item.get("name", "").lower():
                    lab["loinc_code"] = item.get("loinc_code")
                    lab["value"] = item.get("value")
                    lab["status"] = item.get("status", lab["status"])

    return {
        "diagnoses": diagnoses,
        "medications": meds,
        "labs": labs,
        "referrals": referrals,
        "follow_up_tasks": follow_up_tasks,
        "care_plan": [],
    }
