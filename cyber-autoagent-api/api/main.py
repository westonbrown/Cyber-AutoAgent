# api/main.py
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import uuid4

from .models import JobCreate, JobResponse
from .db.session import get_db
from .db import models as db_models
from .db.init_db import init_db

app = FastAPI(title="Cyber-AutoAgent API", version="0.1.0")


@app.on_event("startup")
def _bootstrap_tables() -> None:
    init_db()


@app.post("/v1/jobs", response_model=JobResponse, status_code=202)
def create_job(job: JobCreate, db: Session = Depends(get_db)):
    job_id = str(uuid4())
    db_job = db_models.Job(id=job_id, status="PENDING")
    db.add(db_job)
    db.commit()
    # TODO: push to queue
    return JobResponse(job_id=job_id, status=db_job.status)


@app.get("/v1/jobs/{job_id}", response_model=JobResponse)
def read_job(job_id: str, db: Session = Depends(get_db)):
    db_job = db.query(db_models.Job).filter_by(id=job_id).first()
    if not db_job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse(job_id=db_job.id, status=db_job.status)
