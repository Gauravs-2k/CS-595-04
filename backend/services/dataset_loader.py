"""Loads TransitionGuard_Scaled_Dataset ground-truth gaps for P1–P5 patients."""

import json
import os
import re
import uuid
from pathlib import Path

_DATASET_DIR = Path(os.environ.get("DATASET_DIR", "/dataset"))

DATASET_PATIENTS = {
    "dataset-P1": {"name": "Maria Alvarez", "dob": "1959-04-22", "gender": "F", "folder": "P1"},
    "dataset-P2": {"name": "John Thompson", "dob": "1955-11-12", "gender": "M", "folder": "P2"},
    "dataset-P3": {"name": "Maria Gonzalez", "dob": "1955-11-22", "gender": "F", "folder": "P3"},
    "dataset-P4": {"name": "Maria Thompson", "dob": "1989-11-15", "gender": "F", "folder": "P4"},
    "dataset-P5": {"name": "Carlos Reyes", "dob": "1955-10-09", "gender": "M", "folder": "P5"},
}

_DEFAULT_VISIT = "V1"
_VISITS = [f"V{i}" for i in range(1, 6)]

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


def _normalize_visit(visit: str | None) -> str:
    visit_upper = (visit or _DEFAULT_VISIT).upper()
    return visit_upper if visit_upper in _VISITS else _DEFAULT_VISIT


def _split_dataset_patient_id(patient_id: str) -> tuple[str, str] | None:
    if patient_id in DATASET_PATIENTS:
        return patient_id, _DEFAULT_VISIT

    match = re.fullmatch(r"dataset-(P[1-5])-(V[1-5])", patient_id, flags=re.IGNORECASE)
    if not match:
        return None

    base_id = f"dataset-{match.group(1).upper()}"
    visit = match.group(2).upper()
    if base_id not in DATASET_PATIENTS:
        return None
    return base_id, visit


def _patient_dir(patient_id: str, visit: str = _DEFAULT_VISIT) -> Path:
    parsed = _split_dataset_patient_id(patient_id)
    if parsed is None:
        raise KeyError(f"Unknown dataset patient id: {patient_id}")
    base_id, visit_from_id = parsed
    meta = DATASET_PATIENTS[base_id]
    resolved_visit = _normalize_visit(visit_from_id if "-V" in patient_id.upper() else visit)
    return _DATASET_DIR / meta["folder"] / resolved_visit


def is_dataset_patient(patient_id: str) -> bool:
    return _split_dataset_patient_id(patient_id) is not None


def get_dataset_patient_meta(patient_id: str) -> dict | None:
    parsed = _split_dataset_patient_id(patient_id)
    if parsed is None:
        return None

    base_id, visit = parsed
    base_meta = DATASET_PATIENTS[base_id]
    folder = base_meta["folder"]
    variant_id = f"{folder}-{visit}"
    return {
        **base_meta,
        "base_patient_id": base_id,
        "dataset_patient_id": f"{base_id}-{visit}",
        "visit": visit,
        "variant_id": variant_id,
    }


def list_dataset_patients() -> list[dict]:
    rows: list[dict] = []
    for pid, meta in DATASET_PATIENTS.items():
        for visit in _VISITS:
            folder = meta["folder"]
            variant_id = f"{folder}-{visit}"
            rows.append(
                {
                    "patient_id": f"{pid}-{visit}",
                    "base_patient_id": pid,
                    "variant_id": variant_id,
                    "name": meta["name"],
                    "dob": meta["dob"],
                    "gender": meta.get("gender", ""),
                    "mrn": variant_id,
                    "source_ehr": "TransitionGuard Dataset",
                    "last_discharge_date": "2024-06-01",
                }
            )
    return rows


def _make_title(description: str) -> str:
    first = description.split(".")[0].strip()
    return (first[:80] + "…") if len(first) > 80 else first


def load_dataset_gaps(patient_id: str, visit: str = _DEFAULT_VISIT) -> list[dict]:
    gt_path = _patient_dir(patient_id, visit) / "ground_truth.json"
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


def load_dataset_documents(patient_id: str, visit: str = _DEFAULT_VISIT) -> dict:
    base = _patient_dir(patient_id, visit)
    return {
        "history_text": (base / "patient_history.md").read_text(encoding="utf-8"),
        "discharge_text": (base / "discharge_summary.md").read_text(encoding="utf-8"),
    }


def load_dataset_ground_truth(patient_id: str, visit: str = _DEFAULT_VISIT) -> list[dict]:
    gt_path = _patient_dir(patient_id, visit) / "ground_truth.json"
    return json.loads(gt_path.read_text(encoding="utf-8"))


def get_dataset_demo_handoff(patient_id: str, visit: str = _DEFAULT_VISIT) -> str | None:
    """Return the real discharge summary text for upload-page prefill."""
    if not is_dataset_patient(patient_id):
        return None
    try:
        docs = load_dataset_documents(patient_id, visit=visit)
    except Exception:
        return None
    return docs["discharge_text"]
