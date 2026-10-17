"""Validated models for the single user's candidate profile."""

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    """Base model that rejects unexpected keys to catch profile typos."""

    model_config = ConfigDict(extra="forbid")


class VerificationState(StrEnum):
    """How well a profile fact is verified."""

    VERIFIED = "verified"
    NEEDS_REVIEW = "needs_review"
    NOT_PROVIDED = "not_provided"


class WorkAuthorization(StrictModel):
    """User-provided work authorization details, not an inferred conclusion."""

    country: str | None = None
    status: str | None = None
    requires_sponsorship: bool | None = None
    verified: bool = False
    source: str | None = None


class Contact(StrictModel):
    """Candidate contact information."""

    full_name: str | None = None
    location: str | None = None
    phone: str | None = None
    email: str | None = None
    linkedin_url: str | None = None


class Education(StrictModel):
    """An education entry extracted from a resume."""

    institution: str
    degree: str | None = None
    field_of_study: str | None = None
    expected_graduation: str | None = None
    status: str | None = None


class Experience(StrictModel):
    """A work experience entry extracted from a resume."""

    company: str
    title: str
    start_date: str | None = None
    end_date: str | None = None
    summary: str | None = None


class CandidateFacts(StrictModel):
    """Resume-backed facts used to prepare truthful application materials."""

    summary: str | None = None
    skills: list[str] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)


class Preferences(StrictModel):
    """Explicit job-search preferences. Unknown preferences stay unset."""

    target_titles: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    location_preferences: list[str] = Field(default_factory=list)
    remote_preference: str | None = None
    compensation_minimum: int | None = Field(default=None, ge=0)
    compensation_currency: str | None = None
    company_size_preferences: list[str] = Field(default_factory=list)
    excluded_criteria: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class CandidateProfile(StrictModel):
    """Versioned local profile for the single configured candidate."""

    schema_version: int = Field(ge=1)
    last_updated: date | None = None
    contact: Contact = Field(default_factory=Contact)
    work_authorization: WorkAuthorization = Field(default_factory=WorkAuthorization)
    facts: CandidateFacts = Field(default_factory=CandidateFacts)
    preferences: Preferences = Field(default_factory=Preferences)
