"""Loads MIMIC-IV-style sample discharge/PCP note pairs for pipeline validation."""

import time
from pathlib import Path

from schemas.clinical import ClinicalDocument, PatientRecords, SourceInfo

_SAMPLES_DIR = Path(__file__).parent.parent / "data" / "mimic_samples"

# Each sample is a (discharge_file, pcp_file) pair keyed by scenario name
MIMIC_SAMPLES = {
    "mimic-cardiac-001": ("cardiac_discharge.txt", "cardiac_pcp.txt"),
    "mimic-diabetes-001": ("diabetes_discharge.txt", "diabetes_pcp.txt"),
    "mimic-surgical-001": ("surgical_discharge.txt", "surgical_pcp.txt"),
}

MIMIC_PATIENT_META = {
    "mimic-cardiac-001": {"name": "MIMIC Cardiac Patient", "dob": "1956-05-12"},
    "mimic-diabetes-001": {"name": "MIMIC Diabetes Patient", "dob": "1979-08-23"},
    "mimic-surgical-001": {"name": "MIMIC Surgical Patient", "dob": "1952-11-07"},
}


def list_mimic_patients() -> list[dict]:
    """Return search results for all available MIMIC sample patients."""
    return [
        {
            "patient_id": pid,
            "name": MIMIC_PATIENT_META[pid]["name"],
            "dob": MIMIC_PATIENT_META[pid]["dob"],
            "mrn": pid,
            "source_ehr": "MIMIC-IV",
            "last_discharge_date": "2024-01-22",
        }
        for pid in MIMIC_SAMPLES
    ]


def load_mimic_records(patient_id: str) -> PatientRecords:
    """Load a MIMIC sample pair into the PatientRecords schema."""
    discharge_file, pcp_file = MIMIC_SAMPLES[patient_id]

    discharge_text = (_SAMPLES_DIR / discharge_file).read_text()
    pcp_text = (_SAMPLES_DIR / pcp_file).read_text()

    return PatientRecords(
        discharge_summary=ClinicalDocument(raw_text=discharge_text, structured=None),
        pcp_chart=ClinicalDocument(raw_text=pcp_text, structured=None),
        sources=[
            SourceInfo(
                name="MIMIC-IV",
                ehr="MIMIC-IV De-identified",
                retrieved_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                format="Plain text",
            )
        ],
    )


def load_mimic_pcp_only(patient_id: str) -> ClinicalDocument:
    """Return only the PCP chart for a MIMIC sample (the 'before' data)."""
    _, pcp_file = MIMIC_SAMPLES[patient_id]
    pcp_text = (_SAMPLES_DIR / pcp_file).read_text()
    return ClinicalDocument(raw_text=pcp_text, structured=None)


def get_mimic_discharge_text(patient_id: str) -> str:
    """Return raw discharge summary text for a MIMIC sample (for upload pre-fill)."""
    discharge_file, _ = MIMIC_SAMPLES[patient_id]
    return (_SAMPLES_DIR / discharge_file).read_text()


def is_mimic_patient(patient_id: str) -> bool:
    return patient_id in MIMIC_SAMPLES
