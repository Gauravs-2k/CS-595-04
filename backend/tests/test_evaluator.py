from services.evaluator import score_detected_vs_ground_truth


def test_evaluator_perfect_match_returns_one():
    detected = [
        {
            "category": "action_needed",
            "title": "Pending result: Potassium",
            "description": "Pending potassium lab from discharge",
            "source_text": "potassium pending",
        }
    ]
    gt = [
        {
            "category": "Lab",
            "description": "Potassium pending at discharge",
            "evidence_in_summary": "pending potassium result",
            "suggested_correction": "follow up potassium",
        }
    ]

    result = score_detected_vs_ground_truth(detected, gt)
    assert result["counts"]["true_positives"] == 1
    assert result["metrics"]["precision"] == 1.0
    assert result["metrics"]["recall"] == 1.0
    assert result["metrics"]["f1"] == 1.0


def test_evaluator_handles_mismatch():
    detected = [
        {
            "category": "missing_from_pcp",
            "title": "New diagnosis: Hypertension",
            "description": "Not in PCP list",
            "source_text": "hypertension",
        }
    ]
    gt = [
        {
            "category": "Medication",
            "description": "Furosemide dose discrepancy",
            "evidence_in_summary": "furosemide 60 mg",
            "suggested_correction": "update meds",
        }
    ]

    result = score_detected_vs_ground_truth(detected, gt)
    assert result["counts"]["true_positives"] == 0
    assert result["counts"]["false_positives"] == 1
    assert result["counts"]["false_negatives"] == 1
