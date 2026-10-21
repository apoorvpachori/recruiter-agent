"""CRUD endpoints for the single-table local job tracker."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from recruiter_agent.database import get_db_session
from recruiter_agent.jobs.repository import JobStatus
from recruiter_agent.jobs.services.jobs import (
    JobAlreadyExistsError,
    JobNotFoundError,
)
from recruiter_agent.jobs.services.jobs import (
    create_job as create_job_record,
)
from recruiter_agent.jobs.services.jobs import (
    get_job as get_job_record,
)
from recruiter_agent.jobs.services.jobs import (
    list_jobs as list_job_records,
)
from recruiter_agent.jobs.services.jobs import (
    update_job as update_job_record,
)
from recruiter_agent.jobs.services.schemas import JobCreate, JobRead, JobUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/jobs", tags=["jobs"])
DB_SESSION = Depends(get_db_session)
STATUS_FILTER = Query(default=None, alias="status")


@router.post("", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def create_job(payload: JobCreate, session: Session = DB_SESSION) -> JobRead:
    try:
        job = create_job_record(session, payload)
    except JobAlreadyExistsError as exc:
        raise HTTPException(
            status_code=409, detail="A job with this URL is already tracked."
        ) from exc
    logger.info("job_created", extra={"event": "job_created", "job_id": job.id})
    return job


@router.get("", response_model=list[JobRead])
def list_jobs(
    status_filter: JobStatus | None = STATUS_FILTER,
    session: Session = DB_SESSION,
) -> list[JobRead]:
    return list_job_records(session, status_filter)


@router.get("/{job_id}", response_model=JobRead)
def get_job(job_id: int, session: Session = DB_SESSION) -> JobRead:
    try:
        return get_job_record(session, job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Tracked job not found.") from exc


@router.patch("/{job_id}", response_model=JobRead)
def update_job(
    job_id: int,
    payload: JobUpdate,
    session: Session = DB_SESSION,
) -> JobRead:
    try:
        job = update_job_record(session, job_id, payload)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Tracked job not found.") from exc
    except JobAlreadyExistsError as exc:
        raise HTTPException(
            status_code=409, detail="A job with this URL is already tracked."
        ) from exc
    logger.info("job_updated", extra={"event": "job_updated", "job_id": job.id})
    return job
