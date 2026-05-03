"""String normalization utilities for clinical entity matching."""

import re
from difflib import SequenceMatcher

# Common dosage/form words to strip from medication names
_FORM_WORDS = re.compile(
    r"\b(\d+\s*(mg|mcg|ml|g|iu|units?|meq)(/\w+)?|"
    r"tablet|capsule|cap|tab|oral|injection|solution|cream|gel|patch|"
    r"inhaler|suspension|syrup|drops|extended[- ]release|er|sr|cr|dr|xl|xr)\b",
    re.IGNORECASE,
)

_NON_CORE_MED_WORDS = re.compile(
    r"\b(sulfate|hydrochloride|hcl|sodium|potassium|calcium|acetate|"
    r"nebulized|nebuliser|nebulizer|respules?|puffs?|inhalation|maintenance|"
    r"rescue|prn|needed|as needed|recent|completed|therapy)\b",
    re.IGNORECASE,
)

_MED_CANONICAL_ALIASES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bamoxicillin\s*[-/ ]?clavulan(ate|ic acid)\b", re.IGNORECASE), "amoxicillin clavulanate"),
    (re.compile(r"\baugmentin\b", re.IGNORECASE), "amoxicillin clavulanate"),
    (re.compile(r"\balbuterol\s+sulfate\b", re.IGNORECASE), "albuterol"),
    (re.compile(r"\btiotropium\s+bromide\b", re.IGNORECASE), "tiotropium"),
]

_DRUG_CLASS_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(penicillin|amoxicillin|ampicillin|dicloxacillin|augmentin|amoxicillin clavulanate)\b", re.IGNORECASE), "penicillin"),
    (re.compile(r"\b(cephalexin|cefazolin|ceftriaxone|cefpodoxime|cefepime|cephalosporin)\b", re.IGNORECASE), "cephalosporin"),
    (re.compile(r"\b(sulfa|sulfamethoxazole|sulfadiazine|sulfonamide|bactrim|trimethoprim sulfamethoxazole)\b", re.IGNORECASE), "sulfonamide"),
    (re.compile(r"\b(albuterol|levalbuterol|salbutamol)\b", re.IGNORECASE), "beta2-agonist"),
    (re.compile(r"\b(tiotropium|ipratropium|umeclidinium|aclidinium)\b", re.IGNORECASE), "anticholinergic bronchodilator"),
    (re.compile(r"\b(prednisone|prednisolone|methylprednisolone|dexamethasone|hydrocortisone|corticosteroid|steroid)\b", re.IGNORECASE), "corticosteroid"),
]

# Specialty keywords to extract from referral text
_SPECIALTIES = [
    "diabetes educator",
    "cardiology", "nephrology", "neurology", "pulmonology", "oncology",
    "endocrinology", "gastroenterology", "rheumatology", "urology",
    "orthopedics", "dermatology", "psychiatry", "ophthalmology",
    "hematology", "infectious disease", "physical therapy", "ent",
    "otolaryngology", "allergy", "immunology", "surgery", "surgical",
    "palliative", "geriatrics", "podiatry", "pain management",
]


def normalize_med_name(name: str) -> str:
    """Lowercase, strip dosage info and form words from a medication name."""
    text = name.lower().strip()
    for pattern, canonical in _MED_CANONICAL_ALIASES:
        text = pattern.sub(canonical, text)
    text = _FORM_WORDS.sub("", text)
    text = _NON_CORE_MED_WORDS.sub("", text)
    text = re.sub(r"[^a-z0-9\s-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_dx_text(text: str) -> str:
    """Lowercase, normalize disease variants, and strip non-essential qualifiers."""
    text = text.lower().strip()
    text = text.split("\n")[0]
    text = re.sub(r"\*+", "", text)
    text = re.sub(r"\b[a-z]\s*:\s*$", "", text)
    text = re.sub(r"\(.*?\)", " ", text)
    text = re.sub(r"\bchronic obstructive pulmonary disease\b", "copd", text)
    text = re.sub(r"\btype\s*2\b", "type 2", text)
    text = re.sub(r"\bwithout complications\b", "", text)
    text = re.sub(r"\bcommunity[- ]acquired\b", "", text)
    text = re.sub(r"\b(acute|chronic|severe|moderate|mild|stable|controlled)\b", "", text)
    text = re.sub(r"\bexacerbation of\b", "", text)
    text = re.sub(r"\b(unspecified|likely|possible|probable)\b", "", text)
    text = re.sub(r"^(the|a|an)\s+", "", text)
    text = re.sub(r"\s+", " ", text).strip(" -:,")

    if "copd" in text:
        return "copd"
    if "diabetes" in text:
        return "diabetes mellitus"
    if "pneumonia" in text:
        return "pneumonia"
    if "hypertension" in text:
        return "hypertension"
    return text


def fuzzy_match(a: str, b: str, threshold: float = 0.8) -> bool:
    """Check if two strings are similar enough using SequenceMatcher."""
    if not a or not b:
        return False
    a, b = a.lower().strip(), b.lower().strip()
    if a == b:
        return True
    # Short-circuit: if one contains the other
    if a in b or b in a:
        return True
    return SequenceMatcher(None, a, b).ratio() >= threshold


def extract_specialty(text: str) -> str:
    """Extract a specialty keyword from referral/consult text."""
    lower = text.lower()
    for spec in _SPECIALTIES:
        pattern = r"\b" + re.escape(spec) + r"\b"
        if re.search(pattern, lower):
            return spec
    # Fallback: return the original text stripped
    return text.strip()


def medication_classes(name: str) -> set[str]:
    """Return normalized medication/allergen class labels inferred from text."""
    text = normalize_med_name(name)
    if not text:
        return set()

    classes = {label for pattern, label in _DRUG_CLASS_RULES if pattern.search(text)}
    return classes
