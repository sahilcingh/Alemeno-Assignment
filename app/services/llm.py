import json
import logging
from groq import Groq
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings

logger = logging.getLogger(__name__)

_client = Groq(api_key=settings.groq_api_key)
MODEL = "llama-3.1-8b-instant"

VALID_CATEGORIES = {
    "Food", "Shopping", "Travel", "Transport",
    "Utilities", "Cash Withdrawal", "Entertainment", "Other",
}

BATCH_SIZE = 20


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=5, max=60),
)
def _call_llm(prompt: str) -> str:
    resp = _client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    return resp.choices[0].message.content


def _strip_fences(text: str) -> str:
    """remove markdown code fences that models sometimes add"""
    return text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()


def classify_categories(transactions, db) -> None:
    uncategorised = [t for t in transactions if not t.category or t.category == "Uncategorised"]
    if not uncategorised:
        return

    batches = [uncategorised[i:i + BATCH_SIZE] for i in range(0, len(uncategorised), BATCH_SIZE)]

    for batch in batches:
        items = [
            {
                "index": i,
                "merchant": t.merchant,
                "amount": str(t.amount),
                "notes": t.notes or "",
            }
            for i, t in enumerate(batch)
        ]

        prompt = (
            "You are a financial transaction classifier.\n\n"
            "Classify each transaction into exactly one of:\n"
            "Food, Shopping, Travel, Transport, Utilities, Cash Withdrawal, Entertainment, Other\n\n"
            f"Transactions:\n{json.dumps(items, indent=2)}\n\n"
            "Return ONLY a JSON array, no explanation, no markdown:\n"
            '[{"index": 0, "category": "Food"}, ...]'
        )

        try:
            raw = _call_llm(prompt)
            results = json.loads(_strip_fences(raw))
            for item in results:
                idx = item.get("index")
                cat = item.get("category", "Other")
                if cat not in VALID_CATEGORIES:
                    cat = "Other"
                if idx is not None and idx < len(batch):
                    batch[idx].llm_category = cat
            db.commit()
        except Exception as exc:
            logger.warning(f"LLM classification batch failed after retries: {exc}")
            for t in batch:
                t.llm_failed = True
            db.commit()


def generate_narrative(transactions) -> dict:
    inr_total = sum(float(t.amount or 0) for t in transactions if str(t.currency).upper() == "INR")
    usd_total = sum(float(t.amount or 0) for t in transactions if str(t.currency).upper() == "USD")
    anomaly_count = sum(1 for t in transactions if t.is_anomaly)

    merchant_spend: dict = {}
    for t in transactions:
        m = t.merchant or "Unknown"
        merchant_spend[m] = merchant_spend.get(m, 0) + float(t.amount or 0)
    top_3 = sorted(merchant_spend.items(), key=lambda x: x[1], reverse=True)[:3]

    prompt = (
        "You are a financial analyst. Given this transaction summary, produce a JSON report.\n\n"
        f"- Total INR spend: {inr_total:.2f}\n"
        f"- Total USD spend: {usd_total:.2f}\n"
        f"- Flagged anomalies: {anomaly_count}\n"
        f"- Top merchants by spend: {top_3}\n"
        f"- Total transactions: {len(transactions)}\n\n"
        "Return ONLY this JSON (no markdown):\n"
        '{"narrative": "<2-3 sentences>", "risk_level": "<low|medium|high>"}'
    )

    try:
        raw = _call_llm(prompt)
        data = json.loads(_strip_fences(raw))
    except Exception as exc:
        logger.warning(f"Narrative generation failed: {exc}")
        data = {"narrative": "Narrative unavailable due to LLM error.", "risk_level": "medium"}

    return {
        "total_spend_inr": round(inr_total, 2),
        "total_spend_usd": round(usd_total, 2),
        "top_merchants": [{"merchant": m, "total": round(v, 2)} for m, v in top_3],
        "anomaly_count": anomaly_count,
        "narrative": data.get("narrative"),
        "risk_level": data.get("risk_level", "low"),
    }
