from schemas.clinical import ClinicalSummary, PatientRecords


def search_patient(patient_data: dict) -> list[dict]:
    first = patient_data.get("first_name", "")
    last = patient_data.get("last_name", "")
    return [
        {
            "patient_id": "demo-patient-001",
            "name": f"{first} {last}".strip() or "Demo Patient",
            "dob": patient_data.get("dob", ""),
            "mrn": "MRN-10231",
            "source_ehr": "Epic (Mock)",
            "last_discharge_date": "2026-04-01",
        }
    ]


def retrieve_records(patient_id: str) -> PatientRecords:
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


def get_summary(patient_id: str) -> ClinicalSummary:
    return ClinicalSummary(
        summary_text="Patient discharged after hypertensive urgency stabilization.",
        key_events=["Discharge medication started", "Follow-up requested"],
        medications_changed=["Lisinopril initiated"],
    )
