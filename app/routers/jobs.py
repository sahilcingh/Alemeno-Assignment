import os
import uuid
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.job import Job
from app.models.transaction import Transaction
from app.schemas.job import JobCreateResponse, JobStatusResponse, JobListItem, SummaryOut
from app.schemas.transaction import TransactionOut
from app.workers.tasks import process_job
from app.config import settings

router = APIRouter(prefix="/jobs", tags=["jobs"])

REQUIRED_COLUMNS = {
    "txn_id", "date", "merchant", "amount",
    "currency", "status", "category", "account_id", "notes"
}


@router.post("/upload", response_model=JobCreateResponse, status_code=202)
def upload_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")

    content = file.file.read()
    decoded = content.decode("utf-8", errors="replace")

    # validate headers before doing anything else
    header_line = decoded.split("\n")[0]
    cols = {c.strip().lower() for c in header_line.split(",")}
    missing = REQUIRED_COLUMNS - cols
    if missing:
        raise HTTPException(status_code=422, detail=f"Missing required columns: {missing}")

    job_id = uuid.uuid4()

    os.makedirs(settings.upload_dir, exist_ok=True)
    save_path = os.path.join(settings.upload_dir, f"{job_id}.csv")
    with open(save_path, "wb") as f:
        f.write(content)

    # rough row count (subtract header line)
    raw_rows = max(0, decoded.count("\n") - 1)

    job = Job(
        id=job_id,
        filename=file.filename,
        status="pending",
        row_count_raw=raw_rows,
    )
    db.add(job)
    db.commit()

    process_job.delay(str(job_id))

    return {"job_id": job_id, "status": "pending"}


@router.get("/{job_id}/status", response_model=JobStatusResponse)
def get_job_status(job_id: uuid.UUID, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    summary_out = None
    if job.status == "completed" and job.summary:
        s = job.summary
        summary_out = SummaryOut(
            total_spend_inr=float(s.total_spend_inr) if s.total_spend_inr else None,
            total_spend_usd=float(s.total_spend_usd) if s.total_spend_usd else None,
            top_merchants=s.top_merchants,
            anomaly_count=s.anomaly_count,
            narrative=s.narrative,
            risk_level=s.risk_level,
        )

    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        filename=job.filename,
        row_count_raw=job.row_count_raw,
        row_count_clean=job.row_count_clean,
        created_at=job.created_at,
        completed_at=job.completed_at,
        error_message=job.error_message,
        summary=summary_out,
    )


@router.get("/{job_id}/results")
def get_job_results(job_id: uuid.UUID, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "completed":
        raise HTTPException(status_code=400, detail=f"Job is still {job.status}")

    transactions = db.query(Transaction).filter(Transaction.job_id == job_id).all()
    anomalies = [t for t in transactions if t.is_anomaly]

    # per-category spend breakdown using final category (llm overrides original)
    category_spend: dict = {}
    for t in transactions:
        cat = t.llm_category or t.category or "Uncategorised"
        category_spend[cat] = round(category_spend.get(cat, 0) + float(t.amount or 0), 2)

    summary_out = None
    if job.summary:
        s = job.summary
        summary_out = {
            "total_spend_inr": float(s.total_spend_inr) if s.total_spend_inr else None,
            "total_spend_usd": float(s.total_spend_usd) if s.total_spend_usd else None,
            "top_merchants": s.top_merchants,
            "anomaly_count": s.anomaly_count,
            "narrative": s.narrative,
            "risk_level": s.risk_level,
        }

    return {
        "job_id": str(job_id),
        "transactions": [TransactionOut.model_validate(t) for t in transactions],
        "anomalies": [TransactionOut.model_validate(t) for t in anomalies],
        "category_breakdown": category_spend,
        "summary": summary_out,
    }


@router.get("", response_model=list[JobListItem])
def list_jobs(status: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Job)
    if status:
        q = q.filter(Job.status == status)
    jobs = q.order_by(Job.created_at.desc()).all()
    return [
        JobListItem(
            job_id=j.id,
            status=j.status,
            filename=j.filename,
            row_count_raw=j.row_count_raw,
            created_at=j.created_at,
        )
        for j in jobs
    ]
