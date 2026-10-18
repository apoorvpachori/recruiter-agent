"""Deterministic comparison of normalized job facts to candidate preferences."""

import re
from collections.abc import Iterable

from recruiter_agent.jobs.models import (
    Compensation,
    CriterionResult,
    FitAssessment,
    FitStatus,
    JobFact,
    JobPosting,
)
from recruiter_agent.profile.models import CandidateProfile, Preferences

_STAGE_ORDER = {
    "seed": 0,
    "pre-seed": 0,
    "series a": 1,
    "series b": 2,
    "series c": 3,
    "series d": 4,
    "series e": 5,
    "series f": 6,
    "public": 7,
}
_DEFENSE_TERMS = re.compile(
    r"\b(defen[cs]e|military|weapons?|munition|armed forces|national security)\b", re.I
)
_LOCATION_ALIASES = {
    "san francisco": ("san francisco", "sf bay area", "bay area", "san francisco bay area"),
    "new york city": ("new york city", "new york, ny", "nyc", "new york"),
}


def _criteria(
    criterion: str,
    preference: str | int | list[str] | None,
    fact: JobFact,
    *,
    evaluator,
) -> CriterionResult:
    if preference is None or preference == []:
        return CriterionResult(
            criterion=criterion,
            status=FitStatus.UNKNOWN,
            rationale="No explicit preference is configured.",
        )
    if fact.value is None:
        return CriterionResult(
            criterion=criterion,
            status=FitStatus.UNKNOWN,
            rationale="The job page does not provide this fact clearly.",
            preference=preference,
        )

    status, rationale = evaluator(preference, fact.value)
    return CriterionResult(
        criterion=criterion,
        status=status,
        rationale=rationale,
        job_evidence=fact.evidence,
        preference=preference,
    )


def _title_evaluator(
    preferences: list[str], value: str | int | float | bool
) -> tuple[FitStatus, str]:
    title = str(value).casefold()
    if any(
        preference.casefold() in title or title in preference.casefold()
        for preference in preferences
    ):
        return FitStatus.MATCH, "The advertised title matches one of the target titles."
    return FitStatus.MISMATCH, "The advertised title does not match the configured target titles."


def _location_tokens(preference: str) -> tuple[str, ...]:
    normalized = preference.casefold()
    for canonical, aliases in _LOCATION_ALIASES.items():
        if canonical in normalized or any(alias in normalized for alias in aliases):
            return aliases
    if "remote" in normalized:
        return ("remote", "distributed", "work from anywhere")
    return (normalized.strip(),)


def _location_evaluator(
    preferences: list[str], value: str | int | float | bool
) -> tuple[FitStatus, str]:
    location = str(value).casefold()
    if any(
        token and token in location
        for preference in preferences
        for token in _location_tokens(preference)
    ):
        return (
            FitStatus.MATCH,
            "The advertised location/work arrangement matches a listed location preference.",
        )
    return (
        FitStatus.MISMATCH,
        "The advertised location does not match any listed location preference.",
    )


def _arrangement_evaluator(
    preference: str, value: str | int | float | bool
) -> tuple[FitStatus, str]:
    arrangement = str(value).casefold()
    expected = preference.casefold()
    if "in-office" in expected or "office" in expected:
        if any(
            term in arrangement
            for term in ("in-office", "in office", "on-site", "onsite", "hybrid")
        ):
            return (
                FitStatus.MATCH,
                "The stated arrangement allows in-office work, which is acceptable.",
            )
        if "remote" in arrangement:
            return (
                FitStatus.MATCH,
                "Remote work is explicitly acceptable in the configured preference.",
            )
    if "remote" in expected and "remote" in arrangement:
        return FitStatus.MATCH, "The advertised role is remote and remote work is acceptable."
    return (
        FitStatus.MISMATCH,
        "The advertised work arrangement conflicts with the configured preference.",
    )


def _compensation_result(preferences: Preferences, compensation: Compensation) -> CriterionResult:
    minimum = preferences.compensation_minimum
    currency = preferences.compensation_currency
    if minimum is None:
        return CriterionResult(
            criterion="compensation_minimum",
            status=FitStatus.UNKNOWN,
            rationale="No minimum compensation preference is configured.",
        )
    if compensation.minimum is None:
        return CriterionResult(
            criterion="compensation_minimum",
            status=FitStatus.UNKNOWN,
            rationale="The job page does not provide a clear compensation minimum.",
            preference=minimum,
        )
    if not compensation.currency or not currency:
        return CriterionResult(
            criterion="compensation_minimum",
            status=FitStatus.UNKNOWN,
            rationale="Cannot compare compensation without a known currency on both sides.",
            job_evidence=compensation.evidence,
            preference=minimum,
        )
    if compensation.currency.casefold() != currency.casefold():
        return CriterionResult(
            criterion="compensation_minimum",
            status=FitStatus.UNKNOWN,
            rationale="Job and preference currencies differ; no conversion is performed.",
            job_evidence=compensation.evidence,
            preference=minimum,
        )
    if compensation.maximum is not None and compensation.maximum < minimum:
        status = FitStatus.MISMATCH
        rationale = "The advertised compensation range is below the configured minimum."
    elif compensation.minimum >= minimum:
        status = FitStatus.MATCH
        rationale = "The advertised compensation minimum meets the configured minimum."
    else:
        status = FitStatus.UNKNOWN
        rationale = "The compensation range overlaps the minimum; offer placement is not known."
    return CriterionResult(
        criterion="compensation_minimum",
        status=status,
        rationale=rationale,
        job_evidence=compensation.evidence,
        preference=minimum,
    )


def _employee_count_result(preferences: list[str], fact: JobFact) -> CriterionResult:
    threshold = _employee_threshold(preferences)
    if threshold is None:
        return CriterionResult(
            criterion="employee_count",
            status=FitStatus.UNKNOWN,
            rationale="No numeric company-size preference is configured.",
        )
    if not isinstance(fact.value, (int, float)):
        return CriterionResult(
            criterion="employee_count",
            status=FitStatus.UNKNOWN,
            rationale="The job page does not provide a numeric employee count.",
            job_evidence=fact.evidence,
            preference=preferences,
        )
    status = FitStatus.MATCH if fact.value >= threshold else FitStatus.MISMATCH
    rationale = (
        f"The company has at least {threshold} employees."
        if status == FitStatus.MATCH
        else f"The company has fewer than the preferred {threshold} employees."
    )
    return CriterionResult(
        criterion="employee_count",
        status=status,
        rationale=rationale,
        job_evidence=fact.evidence,
        preference=preferences,
    )


def _employee_threshold(preferences: Iterable[str]) -> int | None:
    for preference in preferences:
        match = re.search(
            r"\b(?:at least|minimum of|min(?:imum)?)\s+(\d[\d,]*)\s+employees?\b", preference, re.I
        )
        if match:
            return int(match.group(1).replace(",", ""))
    return None


def _funding_stage_result(preferences: list[str], fact: JobFact) -> CriterionResult:
    required_stage = next(
        (
            stage
            for stage in _STAGE_ORDER
            if f"{stage} or later" in " ".join(preferences).casefold()
        ),
        None,
    )
    if required_stage is None:
        return CriterionResult(
            criterion="funding_stage",
            status=FitStatus.UNKNOWN,
            rationale="No recognized minimum funding-stage preference is configured.",
        )
    actual = str(fact.value).casefold() if fact.value is not None else ""
    if not actual:
        return CriterionResult(
            criterion="funding_stage",
            status=FitStatus.UNKNOWN,
            rationale="The job page does not state a funding stage.",
            preference=f"{required_stage.title()} or later",
        )
    actual_stage = next((stage for stage in _STAGE_ORDER if stage in actual), None)
    if actual_stage is None:
        return CriterionResult(
            criterion="funding_stage",
            status=FitStatus.UNKNOWN,
            rationale="The stated funding information does not map to a recognized stage.",
            job_evidence=fact.evidence,
            preference=f"{required_stage.title()} or later",
        )
    status = (
        FitStatus.MATCH
        if _STAGE_ORDER[actual_stage] >= _STAGE_ORDER[required_stage]
        else FitStatus.MISMATCH
    )
    rationale = (
        f"The stated funding stage is {actual_stage.title()}, meeting the minimum."
        if status == FitStatus.MATCH
        else f"The stated funding stage is earlier than {required_stage.title()}."
    )
    return CriterionResult(
        criterion="funding_stage",
        status=status,
        rationale=rationale,
        job_evidence=fact.evidence,
        preference=f"{required_stage.title()} or later",
    )


def _defense_dealbreaker(preferences: list[str], facts: list[JobFact]) -> CriterionResult:
    excludes_defense = any("defense" in preference.casefold() for preference in preferences)
    if not excludes_defense:
        return CriterionResult(
            criterion="excluded_criteria:defense",
            status=FitStatus.UNKNOWN,
            rationale="No defense-company exclusion is configured.",
        )
    evidence_parts = [str(fact.value) for fact in facts if fact.value is not None]
    evidence_parts.extend(fact.evidence or "" for fact in facts)
    evidence = " ".join(evidence_parts)
    # Use explicit job-page text/facts only; do not infer sector from company name.
    matched = _DEFENSE_TERMS.search(evidence)
    if matched:
        return CriterionResult(
            criterion="excluded_criteria:defense",
            status=FitStatus.MISMATCH,
            rationale=(
                "The supplied job facts contain defense-related evidence, a stated dealbreaker."
            ),
            job_evidence=matched.group(0),
            preference="No defense companies",
        )
    known_company, known_industry = facts[0], facts[1]
    if known_company.value is None and known_industry.value is None:
        return CriterionResult(
            criterion="excluded_criteria:defense",
            status=FitStatus.UNKNOWN,
            rationale=(
                "The job page provides no company/domain facts to assess the defense exclusion."
            ),
            preference="No defense companies",
        )
    return CriterionResult(
        criterion="excluded_criteria:defense",
        status=FitStatus.UNKNOWN,
        rationale=(
            "No defense evidence was found, but that does not verify the dealbreaker is clear."
        ),
        preference="No defense companies",
    )


def evaluate_fit(job: JobPosting, profile: CandidateProfile) -> FitAssessment:
    """Compare only supplied job facts to explicit preferences; absent data stays unknown."""
    preferences = profile.preferences
    criteria = [
        _criteria("target_title", preferences.target_titles, job.title, evaluator=_title_evaluator),
        _criteria(
            "location",
            preferences.location_preferences,
            job.location,
            evaluator=_location_evaluator,
        ),
        _criteria(
            "work_arrangement",
            preferences.remote_preference,
            job.work_arrangement,
            evaluator=_arrangement_evaluator,
        ),
        _compensation_result(preferences, job.compensation),
        _employee_count_result(preferences.company_size_preferences, job.employee_count),
        _funding_stage_result(preferences.company_size_preferences, job.funding_stage),
        _criteria("domain", preferences.domains, job.industry, evaluator=_title_evaluator),
        _defense_dealbreaker(preferences.excluded_criteria, [job.company, job.industry, job.title]),
    ]

    relevant = [
        criterion
        for criterion in criteria
        if criterion.preference is not None
        and not criterion.criterion.startswith("excluded_criteria:")
    ]
    applicable = [criterion for criterion in relevant if criterion.status != FitStatus.UNKNOWN]
    statuses = {criterion.status for criterion in applicable}
    has_dealbreaker_mismatch = any(
        criterion.criterion.startswith("excluded_criteria:")
        and criterion.status == FitStatus.MISMATCH
        for criterion in criteria
    )
    if FitStatus.MISMATCH in statuses or has_dealbreaker_mismatch:
        overall = FitStatus.MISMATCH
        summary = (
            "At least one explicit preference or dealbreaker is contradicted by the job facts."
        )
    elif FitStatus.MATCH in statuses:
        overall = FitStatus.MATCH
        unknown_count = sum(criterion.status == FitStatus.UNKNOWN for criterion in relevant)
        if unknown_count:
            summary = (
                "Known preferences look like a fit; some criteria remain unknown "
                "and need verification."
            )
        else:
            summary = "The supplied job facts match the configured preferences."
    else:
        overall = FitStatus.UNKNOWN
        summary = "There are not enough known facts to assess overall fit."

    defense_unverified = any(
        criterion.criterion == "excluded_criteria:defense" and criterion.status == FitStatus.UNKNOWN
        for criterion in criteria
    )
    if defense_unverified and overall == FitStatus.MATCH:
        overall = FitStatus.UNKNOWN
        summary += (
            " The defense-company dealbreaker is not verified; "
            "absence of evidence is not clearance."
        )

    return FitAssessment(overall_status=overall, summary=summary, criteria=criteria)
