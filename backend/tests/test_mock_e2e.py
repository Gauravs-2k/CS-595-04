from services.gap_engine import detect_gaps
from services.mock_abstractive import retrieve_records


def test_mock_record_pipeline_detects_expected_gaps() -> None:
    records = retrieve_records("demo-patient-001")

    discharge = records.discharge_summary.structured.model_dump()
    pcp = records.pcp_chart.structured.model_dump()

    gaps = detect_gaps(discharge=discharge, pcp=pcp)

    categories = {gap["category"] for gap in gaps}

    assert "missing" in categories
    assert "unscheduled" in categories
    assert "unaddressed" in categories
    assert len(gaps) >= 3
