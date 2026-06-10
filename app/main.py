from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.database import engine, Base
from app.models import Job, Transaction, JobSummary  # noqa: F401 — needed for Base.metadata
from app.routers import jobs


@asynccontextmanager
async def lifespan(app: FastAPI):
    # create tables if they don't exist yet
    # for a production setup you'd use alembic migrations instead
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Transaction Processing API", version="1.0.0", lifespan=lifespan)

app.include_router(jobs.router)


@app.get("/health")
def health():
    return {"status": "ok"}
