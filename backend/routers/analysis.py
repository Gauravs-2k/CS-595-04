from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.database import get_db
from models.gap import Gap
from models.session import AnalysisSession
from schemas.clinical import GapPatchRequest
from services.abstractive import AbstractiveClient, get_patient_meta
from services.gap_engine import detect_gaps
from services.nlp import extract_entities

router = APIRouter(prefix="/analyze", tags=["analysis"])
client = AbstractiveClient()


def _serialize_session(session: AnalysisSession, gaps: list[Gap]) -> dict:
    return {
        "session_id": session.id,
        "patient": {
            "id": session.patient_id,
            "name": session.patient_name,
            "dob": session.patient_dob,
        },
        "gaps": [
            {
                "id": g.id,
                "category": g.category,
                "severity": g.severity,
                "title": g.title,
                "description": g.description,
                "source_text": g.source_text,
                "source_line": g.source_line,
                "standard_code": g.standard_code,
                "standard_system": g.standard_system,
                "suggested_action": g.suggested_action,
                "resolved": g.resolved,
            }
            for g in gaps
        ],
        "sources": session.sources or [],
        "created_at": session.created_at,
    }


@router.post("/{patient_id}")
async def analyze_patient(patient_id: str, db: Session = Depends(get_db)):
    records = await client.retrieve_records(patient_id=patient_id)

    discharge_struct = records.discharge_summary.structured
    pcp_struct = records.pcp_chart.structured

    if discharge_struct is None:
        discharge_entities = await extract_entities(records.discharge_summary.raw_text)
    else:
        discharge_entities = discharge_struct.model_dump()

    if pcp_struct is None:
        pcp_entities = await extract_entities(records.pcp_chart.raw_text)
    else:
        pcp_entities = pcp_struct.model_dump()

    gaps = detect_gaps(discharge=discharge_entities, pcp=pcp_entities)

    meta = get_patient_meta(patient_id)
    session = AnalysisSession(
        patient_id=patient_id,
        patient_name=meta.get("name", "Unknown"),
        patient_dob=meta.get("dob", "Unknown"),
        sources=[s.model_dump() for s in records.sources],
        discharge_entities=discharge_entities,
        pcp_entities=pcp_entities,
    )
    db.add(session)
    db.flush()

    gap_rows = []
    for gap in gaps:
        row = Gap(
            id=gap["id"],
            session_id=session.id,
            category=gap["category"],
            severity=gap["severity"],
            title=gap["title"],
            description=gap["description"],
            source_text=gap["source_text"],
            source_line=gap.get("source_line"),
            standard_code=gap.get("standard_code"),
            standard_system=gap.get("standard_system"),
            suggested_action=gap["suggested_action"],
            resolved=False,
        )
        db.add(row)
        gap_rows.append(row)

    db.commit()
    db.refresh(session)

    return _serialize_session(session, gap_rows)


@router.get("/{session_id}")
def get_analysis_session(session_id: UUID, db: Session = Depends(get_db)):
    session = db.query(AnalysisSession).filter(AnalysisSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    gaps = db.query(Gap).filter(Gap.session_id == session.id).all()
    return _serialize_session(session, gaps)


@router.patch("/{session_id}/gaps/{gap_id}")
def patch_gap(session_id: UUID, gap_id: UUID, payload: GapPatchRequest, db: Session = Depends(get_db)):
    gap = db.query(Gap).filter(Gap.id == gap_id, Gap.session_id == session_id).first()
    if not gap:
        raise HTTPException(status_code=404, detail="Gap not found")

    gap.resolved = payload.resolved
    gap.resolved_at = datetime.now(timezone.utc) if payload.resolved else None
    db.commit()

    return {
        "id": gap.id,
        "resolved": gap.resolved,
        "resolved_at": gap.resolved_at,
    }
