"""Loads TransitionGuard_Scaled_Dataset ground-truth gaps for P1–P5 patients."""

import json
import os
import uuid
from pathlib import Path

_DATASET_DIR = Path(os.environ.get("DATASET_DIR", "/dataset"))

DATASET_PATIENTS = {
    "dataset-P1": {"name": "Dataset Patient 1", "dob": "1952-03-15", "folder": "P1"},
    "dataset-P2": {"name": "Dataset Patient 2", "dob": "1965-07-22", "folder": "P2"},
    "dataset-P3": {"name": "Dataset Patient 3", "dob": "1978-11-08", "folder": "P3"},
    "dataset-P4": {"name": "Dataset Patient 4", "dob": "1943-05-30", "folder": "P4"},
    "dataset-P5": {"name": "Dataset Patient 5", "dob": "1959-09-14", "folder": "P5"},
}

_CATEGORY_MAP = {
    "Medication": "changed",
    "Lab": "missing_from_pcp",
    "Follow-up": "action_needed",
    "Instruction": "action_needed",
    "Diagnosis": "missing_from_pcp",
}

_SEVERITY_MAP = {
    "Warning": "warning",
    "Info": "info",
    "Urgent": "critical",
    "Critical": "critical",
}


def is_dataset_patient(patient_id: str) -> bool:
    return patient_id in DATASET_PATIENTS


def list_dataset_patients() -> list[dict]:
    return [
        {
            "patient_id": pid,
            "name": meta["name"],
            "dob": meta["dob"],
            "mrn": pid.upper(),
            "source_ehr": "TransitionGuard Dataset",
            "last_discharge_date": "2024-06-01",
        }
        for pid, meta in DATASET_PATIENTS.items()
    ]


def _make_title(description: str) -> str:
    first = description.split(".")[0].strip()
    return (first[:80] + "…") if len(first) > 80 else first


def load_dataset_gaps(patient_id: str, visit: str = "V1") -> list[dict]:
    meta = DATASET_PATIENTS[patient_id]
    gt_path = _DATASET_DIR / meta["folder"] / visit / "ground_truth.json"
    raw = json.loads(gt_path.read_text(encoding="utf-8"))

    gaps = []
    for item in raw:
        gt_category = item.get("category", "Follow-up")
        category = _CATEGORY_MAP.get(gt_category, "action_needed")
        severity = _SEVERITY_MAP.get(item.get("severity", "Info"), "info")
        gaps.append({
            "id": str(uuid.uuid4()),
            "category": category,
            "severity": severity,
            "title": _make_title(item["description"]),
            "description": item["description"],
            "source_text": item.get("evidence_in_summary", ""),
            "source_line": None,
            "standard_code": None,
            "standard_system": None,
            "suggested_action": item.get("suggested_correction", ""),
            "resolved": False,
        })
    return gaps


def get_dataset_demo_handoff(patient_id: str, visit: str = "V1") -> str | None:
    """Assemble a readable placeholder discharge text from ground-truth evidence fields."""
    if patient_id not in DATASET_PATIENTS:
        return None
    meta = DATASET_PATIENTS[patient_id]
    gt_path = _DATASET_DIR / meta["folder"] / visit / "ground_truth.json"
    try:
        raw = json.loads(gt_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    lines = [f"DISCHARGE SUMMARY — {meta['name']} (DOB: {meta['dob']})", ""]
    for item in raw:
        evidence = item.get("evidence_in_summary", "").strip()
        if evidence:
            lines.append(f"[{item.get('category', 'Note')}] {evidence}")
    return "\n".join(lines)
