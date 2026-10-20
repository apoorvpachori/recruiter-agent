"""Single-table SQLModel model for tracked jobs."""

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import Column, DateTime, Enum, String, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


class JobStatus(StrEnum):
    """Initial application-tracking statuses stored on the job row."""

    SAVED = "saved"
    RESEARCHING = "researching"
    INTERESTED = "interested"
    DRAFT_READY = "draft_ready"
    APPLIED = "applied"
    INTERVIEWING = "interviewing"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    ON_HOLD = "on_hold"


class Job(SQLModel, table=True):
    """One row for each tracked job posting and its current application status."""

    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("url", name="uq_jobs_url"),)

    id: int | None = Field(default=None, primary_key=True)
    url: str = Field(sa_type=String(2048), unique=True, index=True)
    company: str | None = Field(default=None, sa_type=String(300))
    title: str | None = Field(default=None, sa_type=String(300))
    status: JobStatus = Field(
        default=JobStatus.SAVED,
        sa_column=Column(
            Enum(
                JobStatus,
                native_enum=False,
                values_callable=lambda enum: [item.value for item in enum],
                length=30,
            ),
            nullable=False,
        ),
    )
    notes: str | None = Field(default=None, sa_type=Text)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_type=DateTime(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_type=DateTime(timezone=True),
    )
