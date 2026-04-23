import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from db.database import get_db
from models.gap import Gap
from models.session import AnalysisSession
from services.pdf_export import render_pdf

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/pdf/{session_id}")
def export_pdf(session_id: str, db: Session = Depends(get_db)):
    session = db.query(AnalysisSession).filter(AnalysisSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    gaps = db.query(Gap).filter(Gap.session_id == session.id).all()
    payload = {
        "patient": {
            "id": session.patient_id,
            "name": session.patient_name or "Unknown",
            "dob": session.patient_dob or "Unknown",
        },
        "gaps": [
            {
                "severity": g.severity,
                "category": g.category,
                "title": g.title,
                "description": g.description,
                "suggested_action": g.suggested_action,
            }
            for g in gaps
        ],
        "created_at": session.created_at.isoformat() if session.created_at else datetime.utcnow().isoformat(),
    }

    try:
        output_dir = Path("/tmp/transitionguard")
        output_dir.mkdir(parents=True, exist_ok=True)
        slug_name = (session.patient_name or "patient").replace(" ", "_")
        filename = f"transitionguard_{slug_name}_{datetime.utcnow().date().isoformat()}.pdf"
        output_path = output_dir / filename

        render_pdf(session_payload=payload, output_path=str(output_path))
    except OSError as exc:
        logger.exception("PDF generation I/O error for session %s", session_id)
        raise HTTPException(status_code=500, detail="Failed to generate PDF report") from exc
    except Exception as exc:
        logger.exception("PDF generation failed for session %s", session_id)
        raise HTTPException(status_code=500, detail="Failed to generate PDF report") from exc

    return FileResponse(str(output_path), media_type="application/pdf", filename=filename)
