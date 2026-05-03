from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.database import get_db
from models.gap import Gap
from models.session import AnalysisSession
from services.dataset_loader import load_dataset_ground_truth
from services.evaluator import score_detected_vs_ground_truth

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.get("/run/{session_id}")
def run_session_evaluation(session_id: str, db: Session = Depends(get_db)):
    session = db.query(AnalysisSession).filter(AnalysisSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    patient_id = session.patient_id
    if not patient_id.startswith("dataset-"):
        raise HTTPException(status_code=400, detail="Evaluation is only available for dataset sessions")

    visit = "V1"
    for src in session.sources or []:
        if isinstance(src, dict) and src.get("visit"):
            visit = src["visit"]
            break

    gt = load_dataset_ground_truth(patient_id, visit=visit)
    gaps = db.query(Gap).filter(Gap.session_id == session.id).all()

    detected = [
        {
            "id": str(g.id),
            "category": g.category,
            "title": g.title,
            "description": g.description,
            "source_text": g.source_text,
        }
        for g in gaps
    ]

    score = score_detected_vs_ground_truth(detected, gt)
    return {
        "session_id": str(session.id),
        "patient_id": patient_id,
        "visit": visit,
        **score,
    }
