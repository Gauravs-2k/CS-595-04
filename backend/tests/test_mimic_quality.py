"""MIMIC-IV pipeline quality evaluation tests.

Validates that the NLP + gap detection pipeline:
1. Does not crash on real clinical text
2. Extracts a non-trivial number of entities from each sample
3. Detects expected gap categories for each clinical scenario
4. Produces well-formed gap output

Note: Without the en_core_sci_lg model (~800MB, Docker only), scispaCy NER
falls back to spacy.blank("en") which has no entity detection. In that case,
only the keyword-based line scanner (referrals, follow-ups, pending labs) runs.
Full NER extraction requires the model installed via:
  pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_core_sci_lg-0.5.4.tar.gz
"""

import asyncio

import pytest

from services.gap_engine import detect_gaps
from services.mimic_loader import MIMIC_SAMPLES, load_mimic_records
from services.nlp import extract_entities


def _run(coro):
    """Run an async coroutine synchronously."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── Pipeline does not crash on any sample ────────────────────────────────────

@pytest.mark.parametrize("patient_id", list(MIMIC_SAMPLES.keys()))
def test_pipeline_no_crash(patient_id):
    """Full pipeline should complete without exceptions on every MIMIC sample."""
    records = load_mimic_records(patient_id)
    discharge = _run(extract_entities(records.discharge_summary.raw_text))
    pcp = _run(extract_entities(records.pcp_chart.raw_text))
    gaps = detect_gaps(discharge, pcp)
    assert isinstance(gaps, list)


@pytest.mark.parametrize("patient_id", list(MIMIC_SAMPLES.keys()))
def test_entities_extracted(patient_id):
    """Each sample should produce at least some entities (from NER or keyword scan)."""
    records = load_mimic_records(patient_id)
    discharge = _run(extract_entities(records.discharge_summary.raw_text))

    total = (
        len(discharge["diagnoses"])
        + len(discharge["medications"])
        + len(discharge["labs"])
        + len(discharge["referrals"])
        + len(discharge["follow_up_tasks"])
    )
    assert total > 0, f"No entities extracted from {patient_id} discharge summary"


@pytest.mark.parametrize("patient_id", list(MIMIC_SAMPLES.keys()))
def test_gaps_detected(patient_id):
    """Each MIMIC sample pair should produce at least one gap."""
    records = load_mimic_records(patient_id)
    discharge = _run(extract_entities(records.discharge_summary.raw_text))
    pcp = _run(extract_entities(records.pcp_chart.raw_text))
    gaps = detect_gaps(discharge, pcp)
    assert len(gaps) > 0, f"No gaps detected for {patient_id}"


@pytest.mark.parametrize("patient_id", list(MIMIC_SAMPLES.keys()))
def test_gap_structure(patient_id):
    """All gaps should have required fields."""
    records = load_mimic_records(patient_id)
    discharge = _run(extract_entities(records.discharge_summary.raw_text))
    pcp = _run(extract_entities(records.pcp_chart.raw_text))
    gaps = detect_gaps(discharge, pcp)

    for gap in gaps:
        assert "id" in gap
        assert "category" in gap
        assert gap["category"] in ("missing_from_pcp", "missing_from_handoff", "action_needed", "changed")
        assert "severity" in gap
        assert gap["severity"] in ("critical", "warning", "info")
        assert "title" in gap
        assert "description" in gap
        assert "suggested_action" in gap


# ── Scenario-specific expectations ───────────────────────────────────────────

def test_cardiac_has_pending_labs():
    """Cardiac sample has pending BMP — should flag action_needed."""
    records = load_mimic_records("mimic-cardiac-001")
    discharge = _run(extract_entities(records.discharge_summary.raw_text))
    pcp = _run(extract_entities(records.pcp_chart.raw_text))
    gaps = detect_gaps(discharge, pcp)
    assert any(g["category"] == "action_needed" and "Pending" in g["title"] for g in gaps)


def test_cardiac_has_follow_up_referrals():
    """Cardiac sample has cardiology/nephrology referrals — should flag action_needed."""
    records = load_mimic_records("mimic-cardiac-001")
    discharge = _run(extract_entities(records.discharge_summary.raw_text))
    pcp = _run(extract_entities(records.pcp_chart.raw_text))
    gaps = detect_gaps(discharge, pcp)
    unscheduled = [g for g in gaps if g["category"] == "action_needed" and "Referral" in g["title"]]
    assert len(unscheduled) >= 2, f"Expected >=2 referral actions, got {len(unscheduled)}"


def test_diabetes_has_follow_ups():
    """Diabetes sample has endocrinology/psychiatry follow-ups."""
    records = load_mimic_records("mimic-diabetes-001")
    discharge = _run(extract_entities(records.discharge_summary.raw_text))
    pcp = _run(extract_entities(records.pcp_chart.raw_text))
    gaps = detect_gaps(discharge, pcp)
    assert any(g["category"] == "action_needed" for g in gaps)


def test_surgical_has_pending_labs():
    """Surgical sample has pending INR recheck and wound cultures."""
    records = load_mimic_records("mimic-surgical-001")
    discharge = _run(extract_entities(records.discharge_summary.raw_text))
    pcp = _run(extract_entities(records.pcp_chart.raw_text))
    gaps = detect_gaps(discharge, pcp)
    assert any(g["category"] == "action_needed" and "Pending" in g["title"] for g in gaps)
