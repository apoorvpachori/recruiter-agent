"""Validated job persistence operations shared by HTTP and agent callers."""

from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from recruiter_agent.jobs.repository import Job, JobStatus
from recruiter_agent.jobs.services.schemas import JobCreate, JobRead, JobUpdate


class JobAlreadyExistsError(Exception):
    """Raised when a job URL is already tracked."""


class JobNotFoundError(Exception):
    """Raised when an operation references an unknown job ID."""


def create_job(session: Session, payload: JobCreate) -> JobRead:
    """Validate, persist, and return a new tracked job."""
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
        raise JobAlreadyExistsError from exc
    session.refresh(job)
    return serialize_job(job)


def list_jobs(session: Session, status_filter: JobStatus | None = None) -> list[JobRead]:
    """Return tracked jobs, newest updates first, optionally filtered by status."""
    statement = select(Job).order_by(Job.updated_at.desc(), Job.id.desc())
    if status_filter is not None:
        statement = statement.where(Job.status == status_filter)
    return [serialize_job(job) for job in session.scalars(statement).all()]


def get_job(session: Session, job_id: int) -> JobRead:
    """Return one tracked job or raise when it does not exist."""
    job = session.get(Job, job_id)
    if job is None:
        raise JobNotFoundError
    return serialize_job(job)


def update_job(session: Session, job_id: int, payload: JobUpdate) -> JobRead:
    """Apply a validated partial update and return the resulting job."""
    job = session.get(Job, job_id)
    if job is None:
        raise JobNotFoundError

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(job, field, str(value) if field == "url" and value is not None else value)
    job.updated_at = datetime.now(UTC)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise JobAlreadyExistsError from exc
    session.refresh(job)
    return serialize_job(job)


def serialize_job(job: Job) -> JobRead:
    """Convert a persistence model to the shared API/tool response contract."""
    return JobRead(
        id=job.id,
        url=job.url,
        company=job.company,
        title=job.title,
        status=job.status,
        notes=job.notes,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )
