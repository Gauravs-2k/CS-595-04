import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db.database import Base, engine
from routers import analysis, export, patients

logger = logging.getLogger(__name__)

app = FastAPI(title="TransitionGuard API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.on_event("startup")
def on_startup() -> None:
    try:
        from alembic import command
        from alembic.config import Config

        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations applied successfully")
    except Exception:
        logger.warning("Alembic migration failed, falling back to create_all")
        Base.metadata.create_all(bind=engine)


app.include_router(patients.router)
app.include_router(analysis.router)
app.include_router(export.router)
