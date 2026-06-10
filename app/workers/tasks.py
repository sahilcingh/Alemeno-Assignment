import os
import uuid
import logging
from datetime import datetime

from app.workers.celery_app import celery
from app.database import SessionLocal
from app.models.job import Job
from app.models.transaction import Transaction
from app.models.job_summary import JobSummary
from app.services.cleaner import clean_csv
from app.services.anomaly import detect_anomalies
from app.services.llm import classify_categories, generate_narrative
from app.config import settings

logger = logging.getLogger(__name__)


@celery.task(bind=True, max_retries=0)
def process_job(self, job_id: str):
    db = SessionLocal()
    job_uuid = uuid.UUID(job_id)

    try:
        job = db.query(Job).filter(Job.id == job_uuid).first()
        if not job:
            logger.error(f"process_job: job {job_id} not found in DB")
            return

        job.status = "processing"
        db.commit()
        logger.info(f"[{job_id}] started processing")

        csv_path = os.path.join(settings.upload_dir, f"{job_id}.csv")

        # --- step 1: clean ---
        cleaned_df = clean_csv(csv_path)
        logger.info(f"[{job_id}] cleaned: {len(cleaned_df)} rows")

        # --- step 2: flag anomalies ---
        cleaned_df = detect_anomalies(cleaned_df)

        # --- step 3: persist transactions ---
        txn_rows = []
        for _, row in cleaned_df.iterrows():
            txn_rows.append(Transaction(
                job_id=job_uuid,
                txn_id=row.get("txn_id") or None,
                date=row.get("date"),
                merchant=row.get("merchant"),
                amount=row.get("amount"),
                currency=row.get("currency"),
                status=row.get("status"),
                category=row.get("category"),
                account_id=row.get("account_id"),
                notes=row.get("notes") or None,
                is_anomaly=bool(row.get("is_anomaly", False)),
                anomaly_reason=row.get("anomaly_reason") or None,
            ))
        db.add_all(txn_rows)
        db.commit()

        # --- step 4: LLM category classification ---
        # TODO: could parallelise batches here with concurrent.futures if throughput matters
        db_txns = db.query(Transaction).filter(Transaction.job_id == job_uuid).all()
        classify_categories(db_txns, db)

        # --- step 5: narrative summary ---
        all_txns = db.query(Transaction).filter(Transaction.job_id == job_uuid).all()
        summary_data = generate_narrative(all_txns)

        db.add(JobSummary(
            job_id=job_uuid,
            total_spend_inr=summary_data.get("total_spend_inr"),
            total_spend_usd=summary_data.get("total_spend_usd"),
            top_merchants=summary_data.get("top_merchants"),
            anomaly_count=summary_data.get("anomaly_count", 0),
            narrative=summary_data.get("narrative"),
            risk_level=summary_data.get("risk_level", "low"),
        ))

        job.status = "completed"
        job.completed_at = datetime.utcnow()
        job.row_count_clean = len(cleaned_df)
        db.commit()

        logger.info(f"[{job_id}] done. {len(cleaned_df)} clean rows, "
                    f"{summary_data.get('anomaly_count', 0)} anomalies")

    except Exception as exc:
        logger.exception(f"[{job_id}] failed: {exc}")
        try:
            job = db.query(Job).filter(Job.id == job_uuid).first()
            if job:
                job.status = "failed"
                job.error_message = str(exc)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()
