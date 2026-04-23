import logging

from fastapi import APIRouter, HTTPException

from schemas.clinical import PatientSearchRequest
from services.abstractive import AbstractiveClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/patients", tags=["patients"])
client = AbstractiveClient()


@router.post("/search")
async def search_patients(payload: PatientSearchRequest):
    try:
        return await client.search_patient(patient_data=payload.model_dump())
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Patient search failed")
        raise HTTPException(status_code=502, detail="Patient search service unavailable") from exc


@router.get("/{patient_id}/demo-handoff")
async def get_demo_handoff(patient_id: str):
    text = client.get_demo_handoff(patient_id)
    if text is None:
        raise HTTPException(status_code=404, detail="No demo handoff available for this patient")
    return {"handoff_text": text}


@router.get("/{patient_id}/records")
async def get_patient_records(patient_id: str):
    try:
        records = await client.retrieve_records(patient_id=patient_id)
        return records.model_dump()
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to retrieve records for patient %s", patient_id)
        raise HTTPException(status_code=502, detail="Failed to retrieve patient records") from exc
