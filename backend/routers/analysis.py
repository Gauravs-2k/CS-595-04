import io
import logging
from datetime import datetime, timezone
from uuid import UUID

import pdfplumber
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from db.database import get_db
from models.gap import Gap
from models.session import AnalysisSession
from schemas.clinical import ClinicalDocument, GapPatchRequest
from services.abstractive import AbstractiveClient, get_patient_meta
from services.dataset_loader import DATASET_PATIENTS, is_dataset_patient, load_dataset_gaps
from services.gap_engine import detect_gaps
from services.mimic_loader import get_mimic_discharge_text, is_mimic_patient
from services.nlp import extract_entities

logger = logging.getLogger(__name__)

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


async def _extract_handoff_text(
    handoff_file: UploadFile | None,
    handoff_text: str | None,
    patient_id: str,
) -> str:
    """Resolve the handoff document text from file upload, pasted text, or MIMIC demo."""
    if handoff_file is not None:
        content = await handoff_file.read()
        filename = (handoff_file.filename or "").lower()
        if filename.endswith(".pdf"):
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                pages = [p.extract_text() or "" for p in pdf.pages]
            return "\n".join(pages)
        # Default: treat as UTF-8 text (.txt, .xml, .json, etc.)
        return content.decode("utf-8", errors="replace")

    if handoff_text:
        return handoff_text

    # Fallback for MIMIC demo patients
    if is_mimic_patient(patient_id):
        return get_mimic_discharge_text(patient_id)

    raise HTTPException(status_code=422, detail="Handoff document required. Upload a file or paste text.")


async def _analyze_dataset_patient(patient_id: str, db: Session) -> dict:
    """Skip NLP entirely and serve ground-truth gaps from the dataset."""
    meta = DATASET_PATIENTS[patient_id]
    gaps = load_dataset_gaps(patient_id)

    session = AnalysisSession(
        patient_id=patient_id,
        patient_name=meta["name"],
        patient_dob=meta["dob"],
        sources=[{
            "name": "TransitionGuard Dataset",
            "ehr": "Ground Truth Annotation",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "format": "JSON",
        }],
        discharge_entities={},
        pcp_entities={},
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


@router.post("/{patient_id}")
async def analyze_patient(
    patient_id: str,
    db: Session = Depends(get_db),
    handoff_file: UploadFile | None = File(None),
    handoff_text: str | None = Form(None),
):
    # Dataset patients: bypass NLP entirely and serve ground-truth gaps
    if is_dataset_patient(patient_id):
        return await _analyze_dataset_patient(patient_id, db)

    # 1. Get the handoff/discharge text (uploaded by user)
    try:
        discharge_text = await _extract_handoff_text(handoff_file, handoff_text, patient_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to read handoff document for patient %s", patient_id)
        raise HTTPException(status_code=400, detail="Could not read the uploaded document") from exc

    # 2. Fetch PCP chart from AH/mock (the patient's existing history)
    try:
        pcp_chart = await client.retrieve_pcp_chart(patient_id=patient_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to retrieve PCP chart for patient %s", patient_id)
        raise HTTPException(status_code=502, detail="Failed to retrieve patient records") from exc

    # 3. Build discharge document from uploaded text
    discharge_doc = ClinicalDocument(raw_text=discharge_text, structured=None)

    # 4. NLP extraction + gap detection
    try:
        discharge_entities = await extract_entities(discharge_doc.raw_text)

        pcp_struct = pcp_chart.structured
        if pcp_struct is None:
            pcp_entities = await extract_entities(pcp_chart.raw_text)
        else:
            pcp_entities = pcp_struct.model_dump()

        gaps = detect_gaps(discharge=discharge_entities, pcp=pcp_entities)
    except Exception as exc:
        logger.exception("NLP/gap detection failed for patient %s", patient_id)
        raise HTTPException(status_code=500, detail="Analysis pipeline failed") from exc

    # 5. Persist to DB
    try:
        meta = get_patient_meta(patient_id)
        session = AnalysisSession(
            patient_id=patient_id,
            patient_name=meta.get("name", "Unknown"),
            patient_dob=meta.get("dob", "Unknown"),
            sources=[],
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
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Database error saving analysis for patient %s", patient_id)
        raise HTTPException(status_code=500, detail="Failed to save analysis results") from exc

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
