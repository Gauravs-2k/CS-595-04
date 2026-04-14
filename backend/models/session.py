import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.database import Base


class AnalysisSession(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[str] = mapped_column(String, nullable=False)
    patient_name: Mapped[str | None] = mapped_column(String, nullable=True)
    patient_dob: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sources: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    discharge_entities: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    pcp_entities: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    gaps = relationship("Gap", back_populates="session", cascade="all, delete-orphan")
