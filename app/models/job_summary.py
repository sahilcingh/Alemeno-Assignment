import uuid
import decimal
from typing import Optional
from sqlalchemy import String, Integer, Numeric, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base


class JobSummary(Base):
    __tablename__ = "job_summaries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id"), unique=True)
    total_spend_inr: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    total_spend_usd: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    top_merchants: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    anomaly_count: Mapped[int] = mapped_column(Integer, default=0)
    narrative: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risk_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    job = relationship("Job", back_populates="summary")
