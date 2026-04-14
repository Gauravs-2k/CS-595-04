from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class DiagnosisEntity(BaseModel):
    fhir_resource_type: Literal["Condition"] = "Condition"
    text: str
    snomed_code: str | None = None
    negated: bool = False
    source_line: int | None = None


class MedicationEntity(BaseModel):
    fhir_resource_type: Literal["MedicationRequest"] = "MedicationRequest"
    name: str
    rxnorm_code: str | None = None
    dose: str | None = None
    frequency: str | None = None
    source_line: int | None = None


class LabEntity(BaseModel):
    fhir_resource_type: Literal["ServiceRequest"] = "ServiceRequest"
    name: str
    loinc_code: str | None = None
    value: str | None = None
    status: str | None = None
    source_line: int | None = None


class ReferralEntity(BaseModel):
    fhir_resource_type: Literal["ServiceRequest"] = "ServiceRequest"
    specialty: str
    provider: str | None = None
    urgency: str | None = None
    source_line: int | None = None


class FollowUpTaskEntity(BaseModel):
    fhir_resource_type: Literal["CarePlan"] = "CarePlan"
    description: str
    timeframe: str | None = None
    source_line: int | None = None


class ClinicalEntities(BaseModel):
    diagnoses: list[DiagnosisEntity] = Field(default_factory=list)
    medications: list[MedicationEntity] = Field(default_factory=list)
    labs: list[LabEntity] = Field(default_factory=list)
    referrals: list[ReferralEntity] = Field(default_factory=list)
    follow_up_tasks: list[FollowUpTaskEntity] = Field(default_factory=list)
    care_plan: list[FollowUpTaskEntity] = Field(default_factory=list)


class SourceInfo(BaseModel):
    name: str | None = None
    ehr: str | None = None
    retrieved_at: str | None = None
    format: str | None = None


class ClinicalDocument(BaseModel):
    raw_text: str = ""
    structured: ClinicalEntities | None = None


class PatientRecords(BaseModel):
    discharge_summary: ClinicalDocument
    pcp_chart: ClinicalDocument
    sources: list[SourceInfo] = Field(default_factory=list)


class GapItem(BaseModel):
    id: UUID
    category: str
    severity: str
    title: str
    description: str
    source_text: str
    source_line: int | None = None
    standard_code: str | None = None
    standard_system: str | None = None
    suggested_action: str
    resolved: bool = False


class GapPatchRequest(BaseModel):
    resolved: bool


class PatientSearchRequest(BaseModel):
    first_name: str
    last_name: str
    dob: str          # YYYY-MM-DD
    gender: str       # M or F
    phone: str = ""
    email: str = ""
    address: str = ""
    city: str = ""
    state: str = ""
    zip: str = ""
    country: str = "USA"


class AnalysisResponse(BaseModel):
    session_id: UUID
    patient: dict
    gaps: list[GapItem]
    sources: list[SourceInfo]
    created_at: datetime


class ClinicalSummary(BaseModel):
    summary_text: str
    key_events: list[str] = Field(default_factory=list)
    medications_changed: list[str] = Field(default_factory=list)
