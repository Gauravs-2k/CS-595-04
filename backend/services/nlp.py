"""
NLP entity extraction using scispaCy en_core_sci_lg.

scispaCy labels ALL biomedical entities as ENTITY (not DISEASE/CHEMICAL/LAB_VALUE).
We classify them into medications, diagnoses, and labs using keyword heuristics
after the NER pass.
"""
from collections import defaultdict

import spacy

from services.llm import resolve_entities

_NLP_MODEL = "en_core_sci_lg"
_nlp = None

# Drug suffixes / common stems for medication classification
_MED_SUFFIXES = (
    "ol", "pril", "sartan", "statin", "prazole", "mycin", "cillin",
    "azole", "mab", "nib", "tide", "ine", "ate", "ide", "one",
)
_MED_KEYWORDS = {
    "mg", "tablet", "capsule", "dose", "daily", "twice", "qd", "bid",
    "tid", "qid", "prn", "oral", "iv", "infusion", "injection",
    "metoprolol", "lisinopril", "atorvastatin", "aspirin", "warfarin",
    "insulin", "metformin", "amlodipine", "furosemide", "omeprazole",
}
_LAB_KEYWORDS = {
    "hba1c", "bmp", "cmp", "cbc", "hemoglobin", "glucose", "creatinine",
    "potassium", "sodium", "tsh", "ldl", "hdl", "rna", "tma", "hiv",
    "chlamydia", "gonorrhoeae", "culture", "panel", "level", "test",
    "result", "negative", "positive", "pending",
}
_DX_KEYWORDS = {
    "diabetes", "hypertension", "failure", "disease", "disorder",
    "syndrome", "infection", "pneumonia", "ischemia", "infarction",
    "cancer", "carcinoma", "fibrillation", "stenosis", "insufficiency",
    "depression", "anxiety", "obesity", "hyperlipidemia", "hypothyroid",
}


def _classify(text: str) -> str:
    lower = text.lower()
    words = set(lower.split())
    if words & _MED_KEYWORDS or any(lower.endswith(s) for s in _MED_SUFFIXES):
        return "med"
    if words & _LAB_KEYWORDS:
        return "lab"
    if words & _DX_KEYWORDS:
        return "dx"
    return "dx"   # default: treat unknown biomedical entity as diagnosis


def _get_nlp():
    global _nlp
    if _nlp is None:
        try:
            _nlp = spacy.load(_NLP_MODEL)
        except OSError:
            _nlp = spacy.blank("en")
    return _nlp


async def extract_entities(text: str) -> dict:
    if not text:
        return {"diagnoses": [], "medications": [], "labs": [],
                "referrals": [], "follow_up_tasks": [], "care_plan": []}

    doc = _get_nlp()(text)

    diagnoses, meds, labs = [], [], []

    for ent in doc.ents:
        line_no = doc.text[: ent.start_char].count("\n") + 1
        kind = _classify(ent.text)
        if kind == "med":
            meds.append({
                "name": ent.text, "rxnorm_code": None,
                "dose": None, "frequency": None, "source_line": line_no,
            })
        elif kind == "lab":
            labs.append({
                "name": ent.text, "loinc_code": None,
                "value": None, "status": "resulted", "source_line": line_no,
            })
        else:
            diagnoses.append({
                "text": ent.text, "snomed_code": None,
                "negated": False, "source_line": line_no,
            })

    # Keyword-based extraction for referrals, follow-ups, pending labs
    referrals, follow_up_tasks = [], []
    for idx, line in enumerate(text.splitlines(), start=1):
        lower = line.lower()
        if "referral" in lower or "consult" in lower:
            referrals.append({"specialty": line.strip(), "provider": None,
                               "urgency": None, "source_line": idx})
        if "follow" in lower or "return" in lower or "appointment" in lower:
            follow_up_tasks.append({"description": line.strip(),
                                    "timeframe": None, "source_line": idx})
        if "pending" in lower and line.strip():
            labs.append({"name": line.strip(), "loinc_code": None,
                         "value": None, "status": "pending", "source_line": idx})

    # Optional: resolve standard codes via GPT-4o if OPENAI_API_KEY is set
    raw_entities = diagnoses + meds + labs
    resolved = await resolve_entities(raw_entities=raw_entities, context=text)

    for item in resolved:
        if "snomed_code" in item:
            for d in diagnoses:
                if d["text"].lower() == item.get("text", "").lower():
                    d["snomed_code"] = item.get("snomed_code")
                    d["negated"] = bool(item.get("negated", False))
        if "rxnorm_code" in item:
            for m in meds:
                if m["name"].lower() in (item.get("text", "").lower(),
                                          item.get("name", "").lower()):
                    m["rxnorm_code"] = item.get("rxnorm_code")
                    m["dose"]        = item.get("dose")
                    m["frequency"]   = item.get("frequency")
        if "loinc_code" in item:
            for l in labs:
                if l["name"].lower() in (item.get("text", "").lower(),
                                          item.get("name", "").lower()):
                    l["loinc_code"] = item.get("loinc_code")
                    l["value"]      = item.get("value")
                    l["status"]     = item.get("status", l["status"])

    return {
        "diagnoses": diagnoses, "medications": meds, "labs": labs,
        "referrals": referrals, "follow_up_tasks": follow_up_tasks,
        "care_plan": [],
    }
