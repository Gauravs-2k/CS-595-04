from pydantic import BaseModel


class RecordSource(BaseModel):
    name: str | None = None
    ehr: str | None = None
    retrieved_at: str | None = None
    format: str | None = None


class PatientMatch(BaseModel):
    patient_id: str
    name: str
    dob: str
    mrn: str | None = None
    source_ehr: str | None = None
    last_discharge_date: str | None = None
