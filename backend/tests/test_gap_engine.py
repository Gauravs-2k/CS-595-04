"""Unit tests for gap_engine.detect_gaps and severity logic."""

from services.gap_engine import _severity, detect_gaps


def _empty():
    return {"diagnoses": [], "medications": [], "labs": [],
            "referrals": [], "follow_up_tasks": [], "care_plan": []}


# ── Severity assignment ──────────────────────────────────────────────────────

def test_severity_missing_medication_defaults_to_warning():
    assert _severity("missing_from_pcp", "New medication: Lisinopril") == "warning"


def test_severity_low_risk_medication_is_info():
    assert _severity("missing_from_pcp", "New medication: Acetaminophen") == "info"


def test_severity_unscheduled_urgent_is_critical():
    assert _severity("action_needed", "Follow-up to schedule", "urgent within 7 days") == "critical"


def test_severity_followup_without_timeframe_is_warning():
    assert _severity("action_needed", "Follow-up: PCP visit", "follow-up recommended") == "warning"


def test_severity_unaddressed_pending_is_critical():
    assert _severity("action_needed", "Pending lab", "pending") == "critical"


def test_severity_changed_is_warning():
    assert _severity("changed", "Medication regimen changed") == "warning"


def test_severity_missing_non_med_is_warning():
    assert _severity("missing_from_pcp", "New diagnosis: Diabetes") == "warning"


def test_severity_default_is_info():
    assert _severity("other", "Something else") == "info"


# ── Missing medications ──────────────────────────────────────────────────────

def test_missing_med_detected_with_codes():
    discharge = {**_empty(), "medications": [
        {"name": "Lisinopril", "rxnorm_code": "12345", "dose": "10 mg", "frequency": "daily"},
    ]}
    pcp = _empty()
    gaps = detect_gaps(discharge, pcp)
    assert any(g["category"] == "missing_from_pcp" and "Lisinopril" in g["title"] for g in gaps)


def test_missing_med_detected_without_codes():
    """Fuzzy name matching should work when rxnorm_code is None."""
    discharge = {**_empty(), "medications": [
        {"name": "Metoprolol 50mg", "rxnorm_code": None},
    ]}
    pcp = _empty()
    gaps = detect_gaps(discharge, pcp)
    assert any(g["category"] == "missing_from_pcp" and "Metoprolol" in g["title"] for g in gaps)


def test_matching_med_not_flagged_fuzzy():
    """Lisinopril 10mg in discharge should match 'lisinopril' in PCP."""
    discharge = {**_empty(), "medications": [
        {"name": "Lisinopril 10mg", "rxnorm_code": None},
    ]}
    pcp = {**_empty(), "medications": [
        {"name": "lisinopril", "rxnorm_code": None},
    ]}
    gaps = detect_gaps(discharge, pcp)
    assert not any(g["category"] == "missing_from_pcp" and "Lisinopril" in g["title"] for g in gaps)


def test_albuterol_variants_are_normalized_not_missed():
    discharge = {**_empty(), "medications": [
        {"name": "Albuterol Sulfate Inhaler 90 mcg", "rxnorm_code": None},
    ]}
    pcp = {**_empty(), "medications": [
        {"name": "nebulized albuterol", "rxnorm_code": None},
    ]}
    gaps = detect_gaps(discharge, pcp)
    assert not any(g["category"] == "missing_from_pcp" and "Albuterol" in g["title"] for g in gaps)
    assert not any(g["category"] == "missing_from_handoff" and "albuterol" in g["title"].lower() for g in gaps)


def test_allergy_class_conflict_detected_as_critical():
    discharge = {**_empty(), "medications": [
        {"name": "Amoxicillin-Clavulanate", "rxnorm_code": None, "source_line": 8},
    ]}
    pcp = {**_empty(), "allergies": [
        {"name": "Penicillin", "source_line": 20},
    ]}

    gaps = detect_gaps(discharge, pcp)
    conflict = next((g for g in gaps if g["title"].startswith("Allergy conflict risk")), None)
    assert conflict is not None
    assert conflict["category"] == "action_needed"
    assert conflict["severity"] == "critical"


# ── Missing diagnoses ────────────────────────────────────────────────────────

def test_missing_dx_detected_without_codes():
    discharge = {**_empty(), "diagnoses": [
        {"text": "Type 2 Diabetes Mellitus", "snomed_code": None},
    ]}
    pcp = {**_empty(), "diagnoses": [
        {"text": "Hypertension", "snomed_code": None},
    ]}
    gaps = detect_gaps(discharge, pcp)
    assert any(g["category"] == "missing_from_pcp" and "Diabetes" in g["title"] for g in gaps)


def test_matching_dx_not_flagged():
    discharge = {**_empty(), "diagnoses": [
        {"text": "Hypertension", "snomed_code": None},
    ]}
    pcp = {**_empty(), "diagnoses": [
        {"text": "hypertension", "snomed_code": None},
    ]}
    gaps = detect_gaps(discharge, pcp)
    assert not any(g["category"] == "missing_from_pcp" and "Hypertension" in g["title"] for g in gaps)


# ── Unscheduled referrals ────────────────────────────────────────────────────

def test_unscheduled_referral_detected():
    discharge = {**_empty(), "referrals": [
        {"specialty": "Cardiology follow-up in 14 days", "urgency": None},
    ]}
    pcp = _empty()
    gaps = detect_gaps(discharge, pcp)
    assert any(g["category"] == "action_needed" for g in gaps)


# ── Pending labs ─────────────────────────────────────────────────────────────

def test_pending_lab_flagged():
    discharge = {**_empty(), "labs": [
        {"name": "BMP", "loinc_code": None, "value": None, "status": "pending"},
    ]}
    pcp = _empty()
    gaps = detect_gaps(discharge, pcp)
    assert any(g["category"] == "action_needed" and "BMP" in g["title"] for g in gaps)


def test_resulted_lab_not_flagged_as_pending():
    discharge = {**_empty(), "labs": [
        {"name": "BMP", "loinc_code": None, "value": "normal", "status": "resulted"},
    ]}
    pcp = _empty()
    gaps = detect_gaps(discharge, pcp)
    assert not any(g["category"] == "action_needed" and "Pending" in g["title"] for g in gaps)


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
    missing_or_unaddressed = [g for g in gaps if g["category"] in ("missing_from_pcp", "action_needed")]
    assert len(missing_or_unaddressed) == 0


def test_empty_inputs_produce_no_gaps():
    gaps = detect_gaps(_empty(), _empty())
    assert gaps == []


def test_copd_exacerbation_without_steroid_flagged():
    discharge = {
        **_empty(),
        "document_text": "Discharge diagnosis includes acute exacerbation of COPD.",
        "diagnoses": [{"text": "Acute exacerbation of COPD", "snomed_code": None}],
        "medications": [{"name": "Albuterol", "rxnorm_code": None}],
    }
    gaps = detect_gaps(discharge, _empty())
    assert any("No corticosteroids prescribed for COPD exacerbation" in g["title"] for g in gaps)


def test_vte_prophylaxis_missing_flagged():
    discharge = {
        **_empty(),
        "document_text": "Patient admitted for pneumonia. Hospital course documented. No mention of thromboprophylaxis.",
        "diagnoses": [{"text": "Pneumonia", "snomed_code": None}],
    }
    gaps = detect_gaps(discharge, _empty())
    assert any("VTE prophylaxis not documented" in g["title"] for g in gaps)
