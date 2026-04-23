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

# Specialty keywords to extract from referral text
_SPECIALTIES = [
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
    text = _FORM_WORDS.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_dx_text(text: str) -> str:
    """Lowercase and strip articles from a diagnosis description."""
    text = text.lower().strip()
    text = re.sub(r"^(the|a|an)\s+", "", text)
    return re.sub(r"\s+", " ", text).strip()


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
        if spec in lower:
            return spec
    # Fallback: return the original text stripped
    return text.strip()
