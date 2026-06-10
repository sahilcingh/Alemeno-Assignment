from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional, List, Any


class JobCreateResponse(BaseModel):
    job_id: UUID
    status: str


class SummaryOut(BaseModel):
    total_spend_inr: Optional[float]
    total_spend_usd: Optional[float]
    top_merchants: Optional[Any]
    anomaly_count: int
    narrative: Optional[str]
    risk_level: Optional[str]


class JobStatusResponse(BaseModel):
    job_id: UUID
    status: str
    filename: str
    row_count_raw: Optional[int]
    row_count_clean: Optional[int]
    created_at: datetime
    completed_at: Optional[datetime]
    error_message: Optional[str]
    summary: Optional[SummaryOut] = None


class JobListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: UUID
    status: str
    filename: str
    row_count_raw: Optional[int]
    created_at: datetime
