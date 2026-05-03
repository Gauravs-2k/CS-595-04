"""
NLP entity extraction using scispaCy en_core_sci_lg.

scispaCy labels ALL biomedical entities as ENTITY (not DISEASE/CHEMICAL/LAB_VALUE).
We classify them into medications, diagnoses, labs, and referrals using keyword
heuristics after the NER pass.
"""

import re

import spacy

from services.llm import resolve_entities
from services.normalize import extract_specialty, normalize_dx_text, normalize_med_name

_NLP_MODEL = "en_core_sci_lg"
_nlp = None

# ── Stopwords and junk filter ────────────────────────────────────────────────
_SKIP_WORDS = {
    "patient", "patients", "the", "was", "were", "has", "had", "been",
    "with", "for", "this", "that", "from", "history", "noted", "report",
    "reported", "see", "also", "per", "status", "post", "day", "days",
    "time", "none", "normal", "plan", "date", "use", "continue",
    "current", "medications", "labs", "visit", "chart", "list",
    "problem", "annual", "recheck", "months", "month", "week", "weeks",
    "year", "years", "de-identified", "primary", "care", "follow",
    "follow-up", "discharge", "summary", "admission", "results",
    "review", "pending", "completed", "ordered", "scheduled",
    "diabetic", "cardiac", "surgical", "medical", "clinical",
    "outpatient", "inpatient", "daily", "weekly", "monthly",
    "twice", "once", "every", "morning", "evening", "night",
    "twice daily", "once daily", "as needed",
}

# Drug suffixes / common stems for medication classification
_MED_SUFFIXES = (
    "ol", "pril", "sartan", "statin", "prazole", "mycin", "cillin",
    "azole", "mab", "nib", "tide", "dipine", "olol", "afil", "triptan",
    "gliptin", "flozin", "lukast", "setron", "poetin", "parin", "navir",
    "vudine", "cycline", "semide", "thiazide",
)
# Known drug names — presence of any of these means it's a medication
_MED_NAMES = {
    "metoprolol", "lisinopril", "atorvastatin", "aspirin", "warfarin",
    "insulin", "metformin", "amlodipine", "furosemide", "omeprazole",
    "losartan", "hydrochlorothiazide", "levothyroxine", "gabapentin",
    "pantoprazole", "rosuvastatin", "clopidogrel", "carvedilol",
    "prednisone", "albuterol", "simvastatin", "tramadol", "amoxicillin",
    "azithromycin", "ciprofloxacin", "doxycycline", "fluoxetine",
    "sertraline", "escitalopram", "duloxetine", "venlafaxine",
    "oxycodone", "hydrocodone", "morphine", "fentanyl", "heparin",
    "enoxaparin", "apixaban", "rivaroxaban", "digoxin", "diltiazem",
    "verapamil", "spironolactone", "acetaminophen", "ibuprofen",
    "nicardipine", "naproxen",
}
# Dosing context words — only classify as med if entity also contains a drug name or suffix
_MED_CONTEXT = {
    "mg", "tablet", "capsule", "dose", "qd", "bid", "tid", "qid", "prn",
    "infusion", "injection",
}
_LAB_KEYWORDS = {
    "hba1c", "a1c", "bmp", "cmp", "cbc", "hemoglobin", "glucose",
    "creatinine", "potassium", "sodium", "tsh", "ldl", "hdl", "rna",
    "tma", "hiv", "chlamydia", "gonorrhoeae", "culture", "panel",
    "level", "test", "result", "negative", "positive", "pending",
    "troponin", "bnp", "inr", "ptt", "pt", "albumin", "bilirubin",
    "ast", "alt", "alkaline", "phosphatase", "lipase", "amylase",
    "ferritin", "iron", "magnesium", "calcium", "phosphorus",
    "urinalysis", "urine", "blood gas", "abg", "lactate", "procalcitonin",
    "esr", "crp", "d-dimer", "fibrinogen", "hematocrit",
    "cholesterol",
}
_DX_KEYWORDS = {
    "diabetes", "hypertension", "failure", "disease", "disorder",
    "syndrome", "infection", "pneumonia", "ischemia", "infarction",
    "cancer", "carcinoma", "fibrillation", "stenosis", "insufficiency",
    "major depressive", "anxiety", "obesity", "hyperlipidemia", "hypothyroid",
    "hyperthyroid", "cirrhosis", "hepatitis", "embolism", "thrombosis",
    "anemia", "sepsis", "asthma", "copd", "stroke", "hemorrhage",
    "fracture", "neuropathy", "retinopathy", "nephropathy", "edema",
    "arrhythmia", "angina", "myocardial", "cerebrovascular",
}
_REFERRAL_KEYWORDS = {
    "referral", "consult", "consultation", "specialist", "referred",
    "cardiology", "nephrology", "neurology", "pulmonology", "oncology",
    "endocrinology", "gastroenterology", "rheumatology", "urology",
    "orthopedics", "dermatology", "psychiatry", "ophthalmology",
    "hematology", "physical therapy", "surgery", "surgical",
    "palliative", "geriatrics", "pain management",
}


# Clinical phrases that should NOT be classified as diagnoses
_FALSE_POSITIVE_DX = {
    "st depression", "st elevation", "st segment", "st changes",
    "respiratory depression", "bone marrow depression", "cns depression",
    "point depression", "spreading depression",
}


def _classify(text: str) -> str:
    lower = text.lower()
    words = set(lower.split())

    # Skip junk: too short, stopwords, or purely numeric
    stripped = lower.strip()
    if len(stripped) < 3 or stripped in _SKIP_WORDS or stripped.replace(".", "").isdigit():
        return "skip"

    # Skip known clinical false positives (e.g. "ST depression" is not psychiatric depression)
    if any(fp in stripped for fp in _FALSE_POSITIVE_DX):
        return "skip"

    # Skip section headings (all caps) and pure stopword entities
    if text.strip().isupper():
        return "skip"
    if words <= _SKIP_WORDS:
        return "skip"

    # Check referral first (more specific)
    if words & _REFERRAL_KEYWORDS:
        return "referral"
    # Medication: known drug name, known suffix, or dosing context + drug name/suffix
    has_drug_name = bool(words & _MED_NAMES)
    # Check if the last word looks like a drug name (ends with a pharma suffix)
    last_word = lower.split()[-1] if lower.split() else ""
    _NOT_DRUGS = {
        "control", "protocol", "alcohol", "patrol", "aerosol", "parasol", "esterol",
        "cholesterol", "total cholesterol", "ldl", "hdl", "triglycerides",
    }
    has_drug_suffix = (
        any(last_word.endswith(s) for s in _MED_SUFFIXES)
        and len(last_word) > 4
        and last_word not in _NOT_DRUGS
    )
    has_dosing_context = bool(words & _MED_CONTEXT)
    if has_drug_name or has_drug_suffix or (has_dosing_context and (has_drug_name or has_drug_suffix)):
        return "med"
    if words & _LAB_KEYWORDS:
        return "lab"
    if words & _DX_KEYWORDS:
        return "dx"
    return "skip"  # skip unrecognized entities — only classify what we're confident about


def _get_nlp():
    global _nlp
    if _nlp is None:
        try:
            _nlp = spacy.load(_NLP_MODEL)
        except OSError:
            _nlp = spacy.blank("en")
    return _nlp


_NEGATION_PREFIXES = re.compile(
    r"\b(no|not|without|denies|denied|absence of|no evidence of|no signs? of|"
    r"rules? out|ruled out|negative for|no history of|no acute|no new)\b",
    re.IGNORECASE,
)

# Section headers that introduce allergy/adverse-reaction content — entities
# found on these lines should not be classified as medications or diagnoses.
_ALLERGY_SECTION_RE = re.compile(
    r"##?\s*(\d+\.?\s*)?(allerg(y|ies)|allergy\s+record|allergy\s+list|"
    r"adverse\s+reactions?|drug\s+reactions?)",
    re.IGNORECASE,
)
_NEXT_SECTION_RE = re.compile(r"^##", re.MULTILINE)
_NEGATED_REFERRAL_RE = re.compile(
    r"\b(no|not|without|denies|declines)\b.{0,24}\b(referral|consult(ation)?|specialist)\b"
    r"|\b(referral|consult(ation)?|specialist)\b.{0,24}\b(not needed|unnecessary|none)\b",
    re.IGNORECASE,
)
_ALLERGY_CONTEXT_RE = re.compile(r"\ballerg(y|ies)\b|\bavoided\b|\bintolerance\b", re.IGNORECASE)
_ALLERGY_SKIP_TOKENS = {
    "allergen", "reaction", "severity", "date", "record", "allergy",
}
_MED_FALLBACK_PATTERNS = [
    re.compile(r"\bamoxicillin\s*[-/ ]?clavulan(ate|ic acid)\b", re.IGNORECASE),
    re.compile(r"\baugmentin\b", re.IGNORECASE),
    re.compile(r"\bamoxicillin\b", re.IGNORECASE),
    re.compile(r"\bprednisone\b", re.IGNORECASE),
]
_HOME_MED_SECTION_RE = re.compile(
    r"##?\s*(home medications?\b.*prior to admission|medications? prior to admission)",
    re.IGNORECASE,
)
_FOLLOWUP_SECTION_RE = re.compile(r"##?\s*(follow[- ]?up|discharge follow[- ]?up)", re.IGNORECASE)
_METADATA_LINE_RE = re.compile(
    r"\*\*\s*(patient\s+variant\s+id|archetype|base\s+conditions|prepared\s+by|date)\s*:\s*\*\*",
    re.IGNORECASE,
)


def _build_allergy_line_set(text: str) -> set[int]:
    """Return the set of 1-based line numbers that fall inside an Allergies section."""
    lines = text.splitlines()
    allergy_lines: set[int] = set()
    in_allergy = False
    for i, line in enumerate(lines, start=1):
        if _ALLERGY_SECTION_RE.search(line):
            in_allergy = True
            allergy_lines.add(i)
            continue
        if in_allergy:
            if _NEXT_SECTION_RE.match(line):
                in_allergy = False
            else:
                allergy_lines.add(i)
    return allergy_lines


def _is_negated(text: str, line_text: str) -> bool:
    """Return True if the entity text appears to be negated on this line."""
    entity_lower = text.lower()
    line_lower = line_text.lower()
    # Find where entity appears in line
    pos = line_lower.find(entity_lower)
    if pos == -1:
        return False
    # Look at the ~60 chars before the entity for a negation prefix
    window = line_lower[max(0, pos - 60): pos]
    return bool(_NEGATION_PREFIXES.search(window))


def _is_negated_referral_line(line_text: str) -> bool:
    return bool(_NEGATED_REFERRAL_RE.search(line_text or ""))


def _extract_allergies(lines: list[str], allergy_lines: set[int]) -> list[dict]:
    """Extract allergen names from lines under an Allergies section."""
    allergies: list[dict] = []
    seen = set()

    for line_no in sorted(allergy_lines):
        if line_no <= 0 or line_no > len(lines):
            continue
        raw = lines[line_no - 1].strip()
        if not raw:
            continue

        candidate = ""
        if raw.startswith("|"):
            cells = [c.strip() for c in raw.strip("|").split("|")]
            if cells:
                candidate = cells[0]
        else:
            candidate = raw.lstrip("-•●* ").split(":")[0].strip()

        candidate = re.sub(r"\*+", "", candidate).strip()
        candidate_lower = candidate.lower()
        if (
            not candidate
            or candidate.startswith("#")
            or candidate_lower in _ALLERGY_SKIP_TOKENS
            or "allergy" in candidate_lower and "penicillin" not in candidate_lower and "sulfa" not in candidate_lower
            or set(candidate) <= {"-", "|", " "}
            or "---" in candidate
        ):
            continue

        key = candidate_lower
        if key in seen:
            continue
        seen.add(key)
        allergies.append({"name": candidate, "source_line": line_no})

    return allergies


def _build_home_med_line_set(text: str) -> set[int]:
    """Return lines that belong to 'home meds prior to admission' sections."""
    lines = text.splitlines()
    section_lines: set[int] = set()
    in_home_med = False
    for i, line in enumerate(lines, start=1):
        if _HOME_MED_SECTION_RE.search(line):
            in_home_med = True
            section_lines.add(i)
            continue
        if in_home_med:
            if _NEXT_SECTION_RE.match(line):
                in_home_med = False
            else:
                section_lines.add(i)
    return section_lines


def _build_followup_line_set(text: str) -> set[int]:
    """Return lines that belong to follow-up sections."""
    lines = text.splitlines()
    section_lines: set[int] = set()
    in_followup = False
    for i, line in enumerate(lines, start=1):
        if _FOLLOWUP_SECTION_RE.search(line):
            in_followup = True
            section_lines.add(i)
            continue
        if in_followup:
            if _NEXT_SECTION_RE.match(line):
                in_followup = False
            else:
                section_lines.add(i)
    return section_lines


async def extract_entities(text: str) -> dict:
    if not text:
        return {"diagnoses": [], "medications": [], "labs": [],
                "referrals": [], "follow_up_tasks": [], "care_plan": []}

    allergy_lines = _build_allergy_line_set(text)
    home_med_lines = _build_home_med_line_set(text)
    followup_lines = _build_followup_line_set(text)
    text_lines = text.splitlines()
    allergies = _extract_allergies(text_lines, allergy_lines)

    doc = _get_nlp()(text)

    diagnoses, meds, labs, referrals_from_ner = [], [], [], []

    for ent in doc.ents:
        line_no = doc.text[: ent.start_char].count("\n") + 1

        # Skip entities whose source line is inside an Allergies section
        if line_no in allergy_lines:
            continue

        line_text = text_lines[line_no - 1] if line_no <= len(text_lines) else ""
        if line_text.strip().startswith("#") or _METADATA_LINE_RE.search(line_text):
            continue

        ent_text = re.sub(r"\s+", " ", ent.text).strip()
        if not ent_text or "**" in ent_text:
            continue

        lower_ent_text = ent_text.lower()
        if "archetype" in lower_ent_text or "base conditions" in lower_ent_text:
            continue

        kind = _classify(ent_text)
        if kind == "skip":
            continue

        if kind == "med":
            if line_no in home_med_lines:
                continue
            if _ALLERGY_CONTEXT_RE.search(line_text):
                continue
            meds.append({
                "name": ent_text, "rxnorm_code": None,
                "dose": None, "frequency": None, "source_line": line_no,
            })
        elif kind == "lab":
            labs.append({
                "name": ent_text, "loinc_code": None,
                "value": None, "status": "resulted", "source_line": line_no,
            })
        elif kind == "referral":
            if _is_negated_referral_line(line_text):
                continue
            if followup_lines and line_no not in followup_lines and not ("referral" in line_text.lower() or "consult" in line_text.lower()):
                continue
            specialty = extract_specialty(ent_text)
            if specialty and specialty.lower() not in ("referral", "consult", "consultation", "referred", "specialist"):
                referrals_from_ner.append({
                    "specialty": specialty, "provider": None,
                    "urgency": None, "source_line": line_no,
                })
        else:
            if lower_ent_text.startswith(("no ", "without ", "denies ", "negative for ")):
                continue
            negated = _is_negated(ent_text, line_text)
            if not negated:
                diagnoses.append({
                    "text": ent_text, "snomed_code": None,
                    "negated": False, "source_line": line_no,
                })

    # Fallback medication extraction for high-value meds that NER may skip.
    seen_med_names = {normalize_med_name(m.get("name", "")) for m in meds if m.get("name")}
    for idx, line in enumerate(text_lines, start=1):
        if idx in allergy_lines:
            continue
        if idx in home_med_lines:
            continue
        for pattern in _MED_FALLBACK_PATTERNS:
            if pattern.pattern == r"\bamoxicillin\b" and re.search(r"clavulan", line, re.IGNORECASE):
                continue
            match = pattern.search(line)
            if not match:
                continue
            med_name = match.group(0).strip()
            norm = normalize_med_name(med_name)
            if not norm or norm in seen_med_names:
                continue
            seen_med_names.add(norm)
            meds.append({
                "name": med_name,
                "rxnorm_code": None,
                "dose": None,
                "frequency": None,
                "source_line": idx,
            })

    # Keyword-based extraction for referrals, follow-ups, pending labs
    referrals, follow_up_tasks = list(referrals_from_ner), []
    seen_referral_lines = {r["source_line"] for r in referrals}

    seen_specialties = {r["specialty"].lower() for r in referrals if r.get("specialty")}
    seen_followup_text = set()

    for idx, line in enumerate(text.splitlines(), start=1):
        lower = line.lower()
        if ("referral" in lower or "consult" in lower) and idx not in seen_referral_lines:
            if _is_negated_referral_line(line):
                continue
            specialty = extract_specialty(line.strip())
            # Skip generic "referral" with no identified specialty
            if specialty and specialty.lower() not in ("referral", "consult", "consultation"):
                if specialty.lower() not in seen_specialties:
                    seen_specialties.add(specialty.lower())
                    referrals.append({"specialty": specialty, "provider": None,
                                       "urgency": None, "source_line": idx})
        if ("follow" in lower or "appointment" in lower):
            if followup_lines and idx not in followup_lines:
                continue
            desc = line.strip().lstrip("-•● ").strip()
            if desc.startswith("#"):
                continue
            desc = re.sub(r"^(follow[- ]?up\s*:?\s*)", "", desc, flags=re.IGNORECASE).strip()
            desc = re.sub(r"^(appointment\s*:?\s*)", "", desc, flags=re.IGNORECASE).strip()
            desc_key = desc.lower()
            # Skip section headers and instructions to return to ED
            if (desc_key.rstrip(":") in ("follow-up", "follow up", "followup")
                    or "return to ed" in desc_key or "return to er" in desc_key
                    or "return to emergency" in desc_key):
                continue
            if desc_key not in seen_followup_text and len(desc) > 10:
                seen_followup_text.add(desc_key)
                follow_up_tasks.append({"description": desc,
                                        "timeframe": None, "source_line": idx})
        if "pending" in lower and line.strip() and lower.strip() != "pending results:":
            # Extract the meaningful part, not section headers
            clean = line.strip().lstrip("-•● ").strip()
            if len(clean) > 5 and not clean.isupper():
                labs.append({"name": clean, "loinc_code": None,
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

    # Deduplicate by normalized name/text
    seen_meds = set()
    deduped_meds = []
    for m in meds:
        key = normalize_med_name(m.get("name", ""))
        if key and key not in seen_meds:
            seen_meds.add(key)
            deduped_meds.append(m)

    # Prefer the specific combination product over plain amoxicillin when both were extracted.
    has_amox_clav = any(normalize_med_name(m.get("name", "")) == "amoxicillin clavulanate" for m in deduped_meds)
    if has_amox_clav:
        deduped_meds = [m for m in deduped_meds if normalize_med_name(m.get("name", "")) != "amoxicillin"]

    seen_dx = set()
    deduped_dx = []
    for d in diagnoses:
        key = normalize_dx_text(d.get("text", ""))
        if key and key not in seen_dx:
            seen_dx.add(key)
            deduped_dx.append(d)

    seen_labs = set()
    deduped_labs = []
    for l in labs:
        key = l.get("name", "").lower().strip()
        if key and key not in seen_labs:
            seen_labs.add(key)
            deduped_labs.append(l)

    return {
        "diagnoses": deduped_dx, "medications": deduped_meds, "labs": deduped_labs,
        "referrals": referrals, "follow_up_tasks": follow_up_tasks,
        "care_plan": [], "allergies": allergies, "document_text": text,
    }
