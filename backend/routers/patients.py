from fastapi import APIRouter

from schemas.clinical import PatientSearchRequest
from services.abstractive import AbstractiveClient

router = APIRouter(prefix="/patients", tags=["patients"])
client = AbstractiveClient()


@router.post("/search")
async def search_patients(payload: PatientSearchRequest):
    return await client.search_patient(patient_data=payload.model_dump())


@router.get("/{patient_id}/records")
async def get_patient_records(patient_id: str):
    records = await client.retrieve_records(patient_id=patient_id)
    return records.model_dump()
