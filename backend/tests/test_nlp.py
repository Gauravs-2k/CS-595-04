"""Unit tests for NLP entity classification."""

from services.nlp import _classify


# ── Medications ──────────────────────────────────────────────────────────────

def test_known_med_by_name():
    assert _classify("metoprolol") == "med"
    assert _classify("lisinopril") == "med"
    assert _classify("atorvastatin") == "med"


def test_med_by_suffix():
    assert _classify("amlodipine") == "med"
    assert _classify("losartan") == "med"
    assert _classify("omeprazole") == "med"


def test_med_with_dosage_keyword():
    assert _classify("aspirin 81 mg daily") == "med"


# ── Labs ─────────────────────────────────────────────────────────────────────

def test_known_lab():
    assert _classify("HbA1c") == "lab"
    assert _classify("CBC") == "lab"
    assert _classify("creatinine") == "lab"
    assert _classify("troponin") == "lab"


def test_lab_with_result():
    assert _classify("glucose level") == "lab"


# ── Diagnoses ────────────────────────────────────────────────────────────────

def test_known_dx():
    assert _classify("hypertension") == "dx"
    assert _classify("diabetes") == "dx"
    assert _classify("heart failure") == "dx"
    assert _classify("pneumonia") == "dx"


def test_dx_with_qualifier():
    assert _classify("chronic kidney disease") == "dx"
    assert _classify("atrial fibrillation") == "dx"


# ── Referrals ────────────────────────────────────────────────────────────────

def test_referral_keyword():
    assert _classify("referral to cardiology") == "referral"
    assert _classify("nephrology consult") == "referral"


def test_specialty_name_is_referral():
    assert _classify("cardiology") == "referral"
    assert _classify("endocrinology") == "referral"


# ── Skip junk ────────────────────────────────────────────────────────────────

def test_short_text_skipped():
    assert _classify("ab") == "skip"
    assert _classify("") == "skip"


def test_stopword_skipped():
    assert _classify("patient") == "skip"
    assert _classify("history") == "skip"


def test_numeric_skipped():
    assert _classify("123") == "skip"
    assert _classify("45.6") == "skip"


# ── Default fallback ────────────────────────────────────────────────────────

def test_unknown_entity_defaults_to_dx():
    assert _classify("some uncommon condition") == "dx"
