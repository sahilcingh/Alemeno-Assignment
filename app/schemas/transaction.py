from pydantic import BaseModel, ConfigDict
from uuid import UUID
from typing import Optional
from decimal import Decimal


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    txn_id: Optional[str]
    date: Optional[str]
    merchant: Optional[str]
    amount: Optional[Decimal]
    currency: Optional[str]
    status: Optional[str]
    category: Optional[str]
    account_id: Optional[str]
    notes: Optional[str]
    is_anomaly: bool
    anomaly_reason: Optional[str]
    llm_category: Optional[str]
