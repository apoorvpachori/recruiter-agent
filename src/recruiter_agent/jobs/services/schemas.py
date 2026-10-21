"""Validated inputs and outputs shared by the jobs API and agent tools."""

from datetime import datetime

from pydantic import ConfigDict, Field, HttpUrl, model_validator
from sqlmodel import SQLModel

from recruiter_agent.jobs.repository import JobStatus


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

    @model_validator(mode="after")
    def require_a_change(self) -> "JobUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one job field must be provided.")
        if "url" in self.model_fields_set and self.url is None:
            raise ValueError("Job URL cannot be cleared.")
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("Job status cannot be cleared.")
        return self


class JobRead(SQLModel):
    """Public representation of a tracked job row."""

    id: int
    url: str
    company: str | None
    title: str | None
    status: JobStatus
    notes: str | None
    created_at: datetime
    updated_at: datetime
