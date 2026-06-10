# Transaction Processing Pipeline

A backend API that accepts messy financial CSVs, processes them through a job queue, uses an LLM to classify transactions and flag anomalies, and exposes the results via a polling API.

## Stack

- **FastAPI** — async API framework, auto Swagger docs at `/docs`
- **Celery + Redis** — background job queue with retry support
- **PostgreSQL** — stores jobs, cleaned transactions, and summaries
- **Groq (LLaMA 3.1 8B)** — free-tier LLM for category classification and narrative generation
- **Docker Compose** — single command to run everything

## Setup

**Prerequisites:** Docker and Docker Compose installed.

1. Clone the repo
2. Copy the example env file and add your Groq API key:
   ```bash
   cp .env.example .env
   # edit .env and set GROQ_API_KEY=your_actual_key
   ```
   Get a free Groq API key at [console.groq.com](https://console.groq.com)

3. Start everything:
   ```bash
   docker compose up --build
   ```

API is available at `http://localhost:8000`  
Swagger UI at `http://localhost:8000/docs`

---

## API Usage

### Upload a CSV

```bash
curl -X POST http://localhost:8000/jobs/upload \
  -F "file=@transactions.csv"
```

Response:
```json
{
  "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "pending"
}
```

### Poll job status

```bash
curl http://localhost:8000/jobs/3fa85f64-5717-4562-b3fc-2c963f66afa6/status
```

When completed, the `summary` field appears with high-level stats.

### Get full results

```bash
curl http://localhost:8000/jobs/3fa85f64-5717-4562-b3fc-2c963f66afa6/results
```

Returns cleaned transactions list, flagged anomalies, per-category spend breakdown, and the LLM narrative.

### List all jobs

```bash
# all jobs
curl http://localhost:8000/jobs

# filter by status
curl "http://localhost:8000/jobs?status=completed"
```

---

## Processing Pipeline

When a CSV is uploaded:

1. Job created in DB with `status=pending`, task enqueued in Redis
2. Worker picks it up → `status=processing`
3. **Data cleaning** — normalise dates to ISO 8601, strip `$` from amounts, uppercase status/currency, fill blank categories with `Uncategorised`, remove exact duplicates
4. **Anomaly detection** — flag amounts > 3× the account's median as `statistical_outlier`; flag USD charges on domestic-only merchants (Swiggy, Ola, IRCTC etc.) as `currency_mismatch`
5. **LLM classification** — transactions still `Uncategorised` after cleaning get batched (20 at a time) and sent to the LLM for category assignment
6. **LLM narrative** — one final call produces total spend by currency, top 3 merchants, anomaly count, a 2-3 sentence narrative, and a `risk_level`
7. `status=completed`, results queryable

LLM calls retry up to 3 times with exponential backoff. If a batch exhausts all retries, those rows are marked `llm_failed=true` and the job continues — it won't fail the whole thing over one bad API response.

---

## Architecture Diagram

[View Architecture Diagram](https://drive.google.com/file/d/1vrqwT_VDcnjzOVwrE0xtWu86m5wi42nH/view?usp=sharing)

---

## Notes

- Tables are created automatically on API startup via `Base.metadata.create_all`. For a production setup you'd swap this for Alembic migrations.
- Both `api` and `worker` use the same Docker image, just different start commands. The `uploads` volume is shared between them so the worker can read the CSV the API saved.
- Groq's free tier has generous rate limits — classification of 90 rows completes in a couple of seconds.
