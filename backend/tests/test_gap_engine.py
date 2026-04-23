"""Unit tests for gap_engine.detect_gaps and severity logic."""

from services.gap_engine import _severity, detect_gaps


def _empty():
    return {"diagnoses": [], "medications": [], "labs": [],
            "referrals": [], "follow_up_tasks": [], "care_plan": []}


# ── Severity assignment ──────────────────────────────────────────────────────

def test_severity_missing_medication_is_critical():
    assert _severity("missing", "Missing medication: Lisinopril") == "critical"


def test_severity_unscheduled_urgent_is_critical():
    assert _severity("unscheduled", "Unscheduled referral", "urgent within 7 days") == "critical"


def test_severity_unaddressed_pending_is_critical():
    assert _severity("unaddressed", "Pending lab", "pending") == "critical"


def test_severity_changed_is_warning():
    assert _severity("changed", "Medication regimen changed") == "warning"


def test_severity_missing_non_med_is_warning():
    assert _severity("missing", "Diagnosis absent from PCP list") == "warning"


def test_severity_default_is_info():
    assert _severity("other", "Something else") == "info"


# ── Missing medications ──────────────────────────────────────────────────────

def test_missing_med_detected_with_codes():
    discharge = {**_empty(), "medications": [
        {"name": "Lisinopril", "rxnorm_code": "12345", "dose": "10 mg", "frequency": "daily"},
    ]}
    pcp = _empty()
    gaps = detect_gaps(discharge, pcp)
    assert any(g["category"] == "missing" and "Lisinopril" in g["title"] for g in gaps)


def test_missing_med_detected_without_codes():
    """Fuzzy name matching should work when rxnorm_code is None."""
    discharge = {**_empty(), "medications": [
        {"name": "Metoprolol 50mg", "rxnorm_code": None},
    ]}
    pcp = _empty()
    gaps = detect_gaps(discharge, pcp)
    assert any(g["category"] == "missing" and "Metoprolol" in g["title"] for g in gaps)


def test_matching_med_not_flagged_fuzzy():
    """Lisinopril 10mg in discharge should match 'lisinopril' in PCP."""
    discharge = {**_empty(), "medications": [
        {"name": "Lisinopril 10mg", "rxnorm_code": None},
    ]}
    pcp = {**_empty(), "medications": [
        {"name": "lisinopril", "rxnorm_code": None},
    ]}
    gaps = detect_gaps(discharge, pcp)
    assert not any(g["category"] == "missing" and "Lisinopril" in g["title"] for g in gaps)


# ── Missing diagnoses ────────────────────────────────────────────────────────

def test_missing_dx_detected_without_codes():
    discharge = {**_empty(), "diagnoses": [
        {"text": "Type 2 Diabetes Mellitus", "snomed_code": None},
    ]}
    pcp = {**_empty(), "diagnoses": [
        {"text": "Hypertension", "snomed_code": None},
    ]}
    gaps = detect_gaps(discharge, pcp)
    assert any(g["category"] == "missing" and "Diabetes" in g["title"] for g in gaps)


def test_matching_dx_not_flagged():
    discharge = {**_empty(), "diagnoses": [
        {"text": "Hypertension", "snomed_code": None},
    ]}
    pcp = {**_empty(), "diagnoses": [
        {"text": "hypertension", "snomed_code": None},
    ]}
    gaps = detect_gaps(discharge, pcp)
    assert not any(g["category"] == "missing" and "Hypertension" in g["title"] for g in gaps)


# ── Unscheduled referrals ────────────────────────────────────────────────────

def test_unscheduled_referral_detected():
    discharge = {**_empty(), "referrals": [
        {"specialty": "Cardiology follow-up in 14 days", "urgency": None},
    ]}
    pcp = _empty()
    gaps = detect_gaps(discharge, pcp)
    assert any(g["category"] == "unscheduled" for g in gaps)


# ── Pending labs ─────────────────────────────────────────────────────────────

def test_pending_lab_flagged():
    discharge = {**_empty(), "labs": [
        {"name": "BMP", "loinc_code": None, "value": None, "status": "pending"},
    ]}
    pcp = _empty()
    gaps = detect_gaps(discharge, pcp)
    assert any(g["category"] == "unaddressed" and "BMP" in g["title"] for g in gaps)


def test_resulted_lab_not_flagged_as_pending():
    discharge = {**_empty(), "labs": [
        {"name": "BMP", "loinc_code": None, "value": "normal", "status": "resulted"},
    ]}
    pcp = _empty()
    gaps = detect_gaps(discharge, pcp)
    assert not any(g["category"] == "unaddressed" for g in gaps)


# ── Changed medication ───────────────────────────────────────────────────────

def test_changed_dose_detected():
    discharge = {**_empty(), "medications": [
        {"name": "Lisinopril", "rxnorm_code": None, "dose": "20 mg", "frequency": "daily"},
    ]}
    pcp = {**_empty(), "medications": [
        {"name": "lisinopril", "rxnorm_code": None, "dose": "10 mg", "frequency": "daily"},
    ]}
    gaps = detect_gaps(discharge, pcp)
    assert any(g["category"] == "changed" and "Lisinopril" in g["title"] for g in gaps)


# ── No gaps ──────────────────────────────────────────────────────────────────

def test_no_gaps_when_documents_match():
    doc = {**_empty(), "medications": [
        {"name": "Aspirin", "rxnorm_code": "1234"},
    ], "diagnoses": [
        {"text": "Hypertension", "snomed_code": "5678"},
    ]}
    gaps = detect_gaps(doc, doc)
    missing_or_unaddressed = [g for g in gaps if g["category"] in ("missing", "unaddressed")]
    assert len(missing_or_unaddressed) == 0


def test_empty_inputs_produce_no_gaps():
    gaps = detect_gaps(_empty(), _empty())
    assert gaps == []
