from datetime import date

from recruiter_agent.jobs.fit import evaluate_fit
from recruiter_agent.jobs.models import Compensation, FitStatus, JobFact, JobPosting
from recruiter_agent.profile.models import (
    CandidateProfile,
    Preferences,
)


def _profile() -> CandidateProfile:
    return CandidateProfile(
        schema_version=1,
        last_updated=date(2026, 10, 18),
        preferences=Preferences(
            target_titles=["Applied AI Engineer", "AI Engineer"],
            location_preferences=[
                "San Francisco preferred",
                "Open to remote",
                "Open to New York City",
            ],
            remote_preference="In-office up to 5 days per week is acceptable",
            compensation_minimum=180_000,
            compensation_currency="USD",
            company_size_preferences=["At least 10 employees", "Series B or later"],
            excluded_criteria=["Defense companies"],
        ),
    )


def _criterion(assessment, name: str):
    return next(criterion for criterion in assessment.criteria if criterion.criterion == name)


def test_evaluate_fit_matches_known_preferences_but_keeps_unverified_dealbreaker_unknown() -> None:
    job = JobPosting(
        source_url="https://jobs.example.com/role",
        title=JobFact(value="Applied AI Engineer", evidence="Title: Applied AI Engineer"),
        company=JobFact(value="Example AI", evidence="Company: Example AI"),
        location=JobFact(value="San Francisco, CA", evidence="Location: San Francisco, CA"),
        work_arrangement=JobFact(value="On-site", evidence="This role is on-site."),
        compensation=Compensation(
            minimum=200_000,
            maximum=240_000,
            currency="USD",
            basis="base salary",
            evidence="$200,000–$240,000 USD base salary",
        ),
        employee_count=JobFact(value=25, evidence="25 employees"),
        funding_stage=JobFact(value="Series B", evidence="Raised a Series B round"),
        industry=JobFact(value="AI software", evidence="AI software products"),
    )

    assessment = evaluate_fit(job, _profile())

    assert _criterion(assessment, "target_title").status == FitStatus.MATCH
    assert _criterion(assessment, "location").status == FitStatus.MATCH
    assert _criterion(assessment, "work_arrangement").status == FitStatus.MATCH
    assert _criterion(assessment, "compensation_minimum").status == FitStatus.MATCH
    assert _criterion(assessment, "employee_count").status == FitStatus.MATCH
    assert _criterion(assessment, "funding_stage").status == FitStatus.MATCH
    assert _criterion(assessment, "domain").status == FitStatus.UNKNOWN
    assert _criterion(assessment, "excluded_criteria:defense").status == FitStatus.UNKNOWN
    assert assessment.overall_status == FitStatus.MATCH
    assert "Provisional match" in assessment.summary
    assert "not a fully verified fit" in assessment.summary


def test_evaluate_fit_flags_defense_dealbreaker_and_low_salary() -> None:
    job = JobPosting(
        source_url="https://jobs.example.com/role",
        title=JobFact(value="AI Engineer", evidence="AI Engineer"),
        company=JobFact(value="Defense Systems Inc", evidence="Defense contractor"),
        compensation=Compensation(
            minimum=150_000,
            maximum=175_000,
            currency="USD",
            evidence="$150,000–$175,000 USD",
        ),
    )

    assessment = evaluate_fit(job, _profile())

    assert _criterion(assessment, "compensation_minimum").status == FitStatus.MISMATCH
    assert _criterion(assessment, "excluded_criteria:defense").status == FitStatus.MISMATCH
    assert assessment.overall_status == FitStatus.MISMATCH


def test_evaluate_fit_returns_unknown_for_missing_or_uncertain_facts() -> None:
    job = JobPosting(
        source_url="https://jobs.example.com/role",
        title=JobFact(value="AI Engineer", evidence="AI Engineer"),
        compensation=Compensation(
            minimum=170_000,
            maximum=210_000,
            currency="USD",
            evidence="$170,000–$210,000 USD",
        ),
        employee_count=JobFact(value="11-50", evidence="Company size 11–50 employees"),
        funding_stage=JobFact(value="venture-backed", evidence="Venture-backed company"),
    )

    assessment = evaluate_fit(job, _profile())

    assert _criterion(assessment, "compensation_minimum").status == FitStatus.UNKNOWN
    assert _criterion(assessment, "location").status == FitStatus.UNKNOWN
    assert _criterion(assessment, "employee_count").status == FitStatus.UNKNOWN
    assert _criterion(assessment, "funding_stage").status == FitStatus.UNKNOWN
    assert assessment.overall_status == FitStatus.MATCH
    assert "Provisional match" in assessment.summary


def test_defense_dealbreaker_uses_only_explicit_supplied_evidence() -> None:
    job = JobPosting(
        source_url="https://jobs.example.com/role",
        company=JobFact(value="Aero Example", evidence="Company: Aero Example"),
        industry=JobFact(value="Aerospace software", evidence="Aerospace software company."),
    )

    assessment = evaluate_fit(job, _profile())

    assert _criterion(assessment, "excluded_criteria:defense").status == FitStatus.UNKNOWN
    assert "does not verify" in _criterion(assessment, "excluded_criteria:defense").rationale


def test_unverified_defense_dealbreaker_is_unknown_but_overall_match_is_loose() -> None:
    job = JobPosting(
        source_url="https://jobs.example.com/role",
        title=JobFact(value="Applied AI Engineer", evidence="Job title"),
        location=JobFact(value="San Francisco", evidence="Job location"),
        work_arrangement=JobFact(value="On-site", evidence="On-site role"),
        compensation=Compensation(minimum=200_000, currency="USD", evidence="$200,000 USD"),
        employee_count=JobFact(value=25, evidence="25 employees"),
        funding_stage=JobFact(value="Series B", evidence="Series B"),
        company=JobFact(value="Example AI", evidence="Example AI"),
        industry=JobFact(value="AI software", evidence="AI software"),
    )

    assessment = evaluate_fit(job, _profile())

    assert assessment.overall_status == FitStatus.MATCH
    assert "criteria remain unknown or unverified" in assessment.summary
