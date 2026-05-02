from schemas.clinical import ClinicalDocument, ClinicalEntities, ClinicalSummary, PatientRecords
from services.dataset_loader import (
    get_dataset_demo_handoff,
    is_dataset_patient,
    list_dataset_patients,
)
from services.mimic_loader import (
    MIMIC_PATIENT_META,
    get_mimic_discharge_text,
    is_mimic_patient,
    list_mimic_patients,
    load_mimic_pcp_only,
    load_mimic_records,
)


def search_patient(patient_data: dict) -> list[dict]:
    first = patient_data.get("first_name", "").strip().lower()
    last = patient_data.get("last_name", "").strip().lower()
    dob = patient_data.get("dob", "").strip()

    if len(last) < 2:
        return []

    candidates = list_mimic_patients() + list_dataset_patients()
    results = [
        p for p in candidates
        if first in p["name"].lower() or last in p["name"].lower()
    ]

    if dob:
        results = [p for p in results if p["dob"] == dob]

    return results


def retrieve_records(patient_id: str) -> PatientRecords:
    if is_mimic_patient(patient_id):
        return load_mimic_records(patient_id)
    return PatientRecords.model_validate(
        {
            "discharge_summary": {
                "raw_text": "Discharged with lisinopril 10 mg daily. Follow up cardiology in 7 days. BMP pending.",
                "structured": {
                    "diagnoses": [
                        {"text": "Hypertension", "snomed_code": "38341003", "negated": False, "source_line": 1}
                    ],
                    "medications": [
                        {
                            "name": "Lisinopril",
                            "rxnorm_code": "29046",
                            "dose": "10 mg",
                            "frequency": "daily",
                            "source_line": 1,
                        }
                    ],
                    "labs": [
                        {
                            "name": "Basic metabolic panel",
                            "loinc_code": "24323-8",
                            "value": "",
                            "status": "pending",
                            "source_line": 1,
                        }
                    ],
                    "referrals": [
                        {
                            "specialty": "Cardiology",
                            "provider": "",
                            "urgency": "within 14 days",
                            "source_line": 1,
                        }
                    ],
                    "follow_up_tasks": [
                        {
                            "description": "Schedule cardiology follow-up",
                            "timeframe": "7 days",
                            "source_line": 1,
                        }
                    ],
                },
            },
            "pcp_chart": {
                "raw_text": "Problem list includes hypertension. No cardiology appointment yet. Current meds: none.",
                "structured": {
                    "diagnoses": [
                        {"text": "Hypertension", "snomed_code": "38341003", "negated": False, "source_line": 1}
                    ],
                    "medications": [],
                    "labs": [],
                    "referrals": [],
                    "care_plan": [
                        {
                            "description": "Primary care follow-up",
                            "timeframe": "30 days",
                            "source_line": 1,
                        }
                    ],
                },
            },
            "sources": [
                {
                    "name": "Abstractive Mock",
                    "ehr": "Demo EHR",
                    "retrieved_at": "2026-04-14T10:00:00Z",
                    "format": "FHIR Bundle",
                }
            ],
        }
    )


def retrieve_pcp_chart(patient_id: str) -> ClinicalDocument:
    """Return only the PCP chart (the 'before' data) for a patient."""
    if is_mimic_patient(patient_id):
        return load_mimic_pcp_only(patient_id)
    # Demo patient — return the hardcoded PCP chart
    return ClinicalDocument(
        raw_text="Problem list includes hypertension. No cardiology appointment yet. Current meds: none.",
        structured=ClinicalEntities(
            diagnoses=[{"text": "Hypertension", "snomed_code": "38341003", "negated": False, "source_line": 1}],
            medications=[],
        ),
    )


def get_demo_handoff_text(patient_id: str) -> str | None:
    """Return discharge text for demo pre-fill. Available for MIMIC and dataset patients."""
    if is_mimic_patient(patient_id):
        return get_mimic_discharge_text(patient_id)
    if is_dataset_patient(patient_id):
        return get_dataset_demo_handoff(patient_id)
    return None


def get_summary(patient_id: str) -> ClinicalSummary:
    return ClinicalSummary(
        summary_text="Patient discharged after hypertensive urgency stabilization.",
        key_events=["Discharge medication started", "Follow-up requested"],
        medications_changed=["Lisinopril initiated"],
    )
