from unittest.mock import patch

from services.agentic_gap_engine import detect_gaps as detect_agentic_gaps
from services.gap_engine import detect_gaps as detect_rule_gaps


def _sample_entities():
    discharge = {
        "medications": [
            {"name": "Lisinopril", "rxnorm_code": "29046", "dose": "20 mg", "frequency": "daily", "source_line": 1},
            {"name": "Furosemide", "rxnorm_code": "4603", "dose": "60 mg", "frequency": "daily", "source_line": 2},
        ],
        "diagnoses": [
            {"text": "Heart failure", "snomed_code": "84114007", "source_line": 3},
            {"text": "Obesity", "snomed_code": "414915002", "source_line": 4},
        ],
        "labs": [
            {"name": "BMP", "loinc_code": "24323-8", "value": "abnormal", "status": "pending", "source_line": 5}
        ],
        "referrals": [{"specialty": "Cardiology", "source_line": 6}],
        "follow_up_tasks": [{"description": "Cardiology follow-up in 7 days", "source_line": 7}],
    }

    pcp = {
        "medications": [
            {"name": "Lisinopril", "rxnorm_code": "29046", "dose": "10 mg", "frequency": "daily", "source_line": 10}
        ],
        "diagnoses": [{"text": "Heart failure", "snomed_code": "84114007", "source_line": 11}],
        "labs": [],
        "care_plan": [{"description": "Diet counseling"}],
    }
    return discharge, pcp


def test_agentic_matches_rule_engine_when_enabled():
    discharge, pcp = _sample_entities()

    with patch("services.agentic_gap_engine.get_settings") as mock_get_settings:
        mock_get_settings.return_value.use_langchain_agents = True
        agentic = detect_agentic_gaps(discharge=discharge, pcp=pcp)

    rule = detect_rule_gaps(discharge=discharge, pcp=pcp)

    # IDs are random UUIDs; compare stable fields only.
    def normalize(gaps):
        return sorted(
            [
                (
                    g["category"],
                    g["severity"],
                    g["title"],
                    g["description"],
                    g.get("source_text"),
                    g.get("source_line"),
                    g.get("standard_code"),
                    g.get("standard_system"),
                )
                for g in gaps
            ]
        )

    assert normalize(agentic) == normalize(rule)


def test_agentic_falls_back_when_langchain_disabled():
    discharge, pcp = _sample_entities()

    with patch("services.agentic_gap_engine.get_settings") as mock_get_settings:
        mock_get_settings.return_value.use_langchain_agents = False
        result = detect_agentic_gaps(discharge=discharge, pcp=pcp)

    rule = detect_rule_gaps(discharge=discharge, pcp=pcp)
    assert len(result) == len(rule)
