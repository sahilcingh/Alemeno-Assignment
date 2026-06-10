import uuid
import decimal
from typing import Optional
from sqlalchemy import String, Boolean, Numeric, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id"))
    txn_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    date: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    merchant: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    amount: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    account_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False)
    anomaly_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    llm_category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    llm_failed: Mapped[bool] = mapped_column(Boolean, default=False)

    job = relationship("Job", back_populates="transactions")
