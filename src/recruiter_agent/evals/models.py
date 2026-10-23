"""Typed scenario and report models for local agent evaluations."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from recruiter_agent.jobs.models import FitStatus
from recruiter_agent.jobs.repository import JobStatus
from recruiter_agent.providers.search import SearchResult
from recruiter_agent.tools.read_webpage import PageContent


class StrictModel(BaseModel):
    """Reject unexpected case fields so misspelled expectations fail loudly."""

    model_config = ConfigDict(extra="forbid")


class ToolCallFixture(StrictModel):
    """One scripted tool call emitted by the offline model."""

    name: str
    args: dict[str, Any] = Field(default_factory=dict)


class ScriptedTurn(StrictModel):
    """One assistant response in a deterministic scenario."""

    content: str = ""
    tool_calls: list[ToolCallFixture] = Field(default_factory=list)


class SearchFixture(StrictModel):
    """Synthetic search result returned for one exact query or wildcard."""

    query: str = "*"
    provider: str = "fixture"
    retrieved_at: datetime
    results: list[SearchResult] = Field(default_factory=list)


class FixtureData(StrictModel):
    """Local data returned by tool adapters during an eval case."""

    pages: dict[str, PageContent] = Field(default_factory=dict)
    searches: list[SearchFixture] = Field(default_factory=list)
    job_extraction: dict[str, Any] = Field(default_factory=dict)
    fit_assessment: dict[str, Any] = Field(
        default_factory=lambda: {
            "overall_status": FitStatus.UNKNOWN.value,
            "summary": "There is not enough evidence to assess this role.",
            "criteria": [],
            "confidence": "low",
        }
    )


class JobFixture(StrictModel):
    """Synthetic initial job row seeded into the temporary eval database."""

    id: int | None = None
    url: str
    company: str | None = None
    title: str | None = None
    status: JobStatus = JobStatus.SAVED
    notes: str | None = None


class ExpectedJob(StrictModel):
    """Expected complete public job row after a scenario."""

    id: int
    url: str
    company: str | None = None
    title: str | None = None
    status: JobStatus
    notes: str | None = None

    @model_validator(mode="after")
    def require_full_row_expectation(self) -> ExpectedJob:
        required_fields = {"id", "url", "company", "title", "status", "notes"}
        missing = required_fields - self.model_fields_set
        if missing:
            raise ValueError(
                "Expected job rows must specify every tracked field, using null where needed."
            )
        return self


class ExpectedToolCall(StrictModel):
    """Required tool call matched by name and a subset of its arguments."""

    name: str
    args_subset: dict[str, Any] = Field(default_factory=dict)


class Expectations(StrictModel):
    """Machine-checkable behavior expected from one run."""

    required_tool_calls: list[ExpectedToolCall] = Field(default_factory=list)
    forbidden_tools: list[str] = Field(default_factory=list)
    expected_jobs: list[ExpectedJob] | None = None
    database_unchanged: bool = False
    response_contains: list[str] = Field(default_factory=list)
    response_excludes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_at_least_one_assertion(self) -> Expectations:
        if not any(
            (
                self.required_tool_calls,
                self.forbidden_tools,
                self.expected_jobs is not None,
                self.database_unchanged,
                self.response_contains,
                self.response_excludes,
            )
        ):
            raise ValueError("Each eval case must define at least one hard expectation.")
        return self


class EvalCase(StrictModel):
    """One synthetic user request, fixture environment, and expectation set."""

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    description: str
    user_input: str
    profile: dict[str, Any] = Field(default_factory=lambda: {"schema_version": 1})
    initial_jobs: list[JobFixture] = Field(default_factory=list)
    fixtures: FixtureData = Field(default_factory=FixtureData)
    scripted_turns: list[ScriptedTurn] = Field(default_factory=list)
    expectations: Expectations


class ToolTrace(StrictModel):
    """Observed tool call with its arguments and corresponding result, if any."""

    name: str
    args: dict[str, Any] = Field(default_factory=dict)
    result: Any = None
    error: bool = False


class HardCheck(StrictModel):
    """One deterministic check and its human-readable outcome."""

    name: str
    passed: bool
    detail: str


class JudgeScore(StrictModel):
    """LLM judge scores with short evidence-based explanations."""

    answer_relevance: int = Field(ge=0, le=2)
    evidence_grounding: int = Field(ge=0, le=2)
    uncertainty_calibration: int = Field(ge=0, le=2)
    rationale: str


class CaseResult(StrictModel):
    """Local evaluation output for one case."""

    case_id: str
    passed: bool
    hard_checks: list[HardCheck]
    tool_trace: list[ToolTrace]
    response: str
    judge: JudgeScore | None = None
    error: str | None = None
