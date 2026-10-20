"""Typed job facts and evidence-backed fit assessment results."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    """Reject unexpected fields to catch extraction and schema mistakes."""

    model_config = ConfigDict(extra="forbid")


class FitStatus(StrEnum):
    """Three-state evaluation; unknown is never treated as a match."""

    MATCH = "match"
    MISMATCH = "mismatch"
    UNKNOWN = "unknown"


class JobFact(StrictModel):
    """One extracted fact with the exact evidence supporting it."""

    value: str | int | float | bool | None = None
    evidence: str | None = None
    source_url: str | None = None


class Compensation(StrictModel):
    """Compensation values as advertised, preserving range/currency context."""

    minimum: int | None = Field(default=None, ge=0)
    maximum: int | None = Field(default=None, ge=0)
    currency: str | None = None
    basis: str | None = None
    evidence: str | None = None


class JobPosting(StrictModel):
    """Normalized job facts; absent facts remain null/unknown."""

    source_url: str
    title: JobFact = Field(default_factory=JobFact)
    company: JobFact = Field(default_factory=JobFact)
    location: JobFact = Field(default_factory=JobFact)
    work_arrangement: JobFact = Field(default_factory=JobFact)
    compensation: Compensation = Field(default_factory=Compensation)
    employee_count: JobFact = Field(default_factory=JobFact)
    funding_stage: JobFact = Field(default_factory=JobFact)
    industry: JobFact = Field(default_factory=JobFact)
    description: str | None = None
    page_issue: str | None = None


class JobPageExtraction(StrictModel):
    """Facts extracted by the model from fetched, untrusted page text."""

    title: JobFact = Field(default_factory=JobFact)
    company: JobFact = Field(default_factory=JobFact)
    location: JobFact = Field(default_factory=JobFact)
    work_arrangement: JobFact = Field(default_factory=JobFact)
    compensation: Compensation = Field(default_factory=Compensation)
    employee_count: JobFact = Field(default_factory=JobFact)
    funding_stage: JobFact = Field(default_factory=JobFact)
    industry: JobFact = Field(default_factory=JobFact)
    description: str | None = None


class CriterionResult(StrictModel):
    """Outcome and rationale for one explicit preference criterion."""

    criterion: str
    status: FitStatus
    rationale: str
    job_evidence: str | None = None
    preference: str | int | list[str] | None = None


class FitAssessment(StrictModel):
    """LLM recommendation with per-criterion evidence-backed assessments."""

    overall_status: FitStatus
    summary: str
    criteria: list[CriterionResult]
    rationale: str = ""
    confidence: str = "medium"
