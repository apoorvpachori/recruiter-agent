"""CRUD endpoints for the single-table local job tracker."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ConfigDict, Field, HttpUrl
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, select

from recruiter_agent.database import get_db_session
from recruiter_agent.jobs.repository import Job, JobStatus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/jobs", tags=["jobs"])
DB_SESSION = Depends(get_db_session)
STATUS_FILTER = Query(default=None, alias="status")


class JobCreate(SQLModel):
    """Fields needed to start tracking one job."""

    model_config = ConfigDict(extra="forbid")

    url: HttpUrl
    company: str | None = Field(default=None, max_length=300)
    title: str | None = Field(default=None, max_length=300)
    status: JobStatus = JobStatus.SAVED
    notes: str | None = None


class JobUpdate(SQLModel):
    """Optional job fields to update; omitted values remain unchanged."""

    model_config = ConfigDict(extra="forbid")

    url: HttpUrl | None = None
    company: str | None = Field(default=None, max_length=300)
    title: str | None = Field(default=None, max_length=300)
    status: JobStatus | None = None
    notes: str | None = None


class JobRead(SQLModel):
    """Public representation of a tracked job row."""

    id: int
    url: str
    company: str | None
    title: str | None
    status: JobStatus
    notes: str | None
    created_at: str
    updated_at: str


def _serialize(job: Job) -> JobRead:
    return JobRead(
        id=job.id,
        url=job.url,
        company=job.company,
        title=job.title,
        status=job.status,
        notes=job.notes,
        created_at=job.created_at.isoformat(),
        updated_at=job.updated_at.isoformat(),
    )


@router.post("", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def create_job(payload: JobCreate, session: Session = DB_SESSION) -> JobRead:
    job = Job(
        url=str(payload.url),
        company=payload.company,
        title=payload.title,
        status=payload.status,
        notes=payload.notes,
    )
    session.add(job)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409, detail="A job with this URL is already tracked."
        ) from exc
    session.refresh(job)
    logger.info("job_created", extra={"event": "job_created", "job_id": job.id})
    return _serialize(job)


@router.get("", response_model=list[JobRead])
def list_jobs(
    status_filter: JobStatus | None = STATUS_FILTER,
    session: Session = DB_SESSION,
) -> list[JobRead]:
    statement = select(Job).order_by(Job.updated_at.desc(), Job.id.desc())
    if status_filter is not None:
        statement = statement.where(Job.status == status_filter)
    return [_serialize(job) for job in session.scalars(statement).all()]


@router.get("/{job_id}", response_model=JobRead)
def get_job(job_id: int, session: Session = DB_SESSION) -> JobRead:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Tracked job not found.")
    return _serialize(job)


@router.patch("/{job_id}", response_model=JobRead)
def update_job(
    job_id: int,
    payload: JobUpdate,
    session: Session = DB_SESSION,
) -> JobRead:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Tracked job not found.")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(job, field, str(value) if field == "url" and value is not None else value)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409, detail="A job with this URL is already tracked."
        ) from exc
    session.refresh(job)
    logger.info("job_updated", extra={"event": "job_updated", "job_id": job.id})
    return _serialize(job)
