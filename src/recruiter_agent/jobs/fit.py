"""LLM-based job-fit recommendation over structured, sourced facts."""

import json

from langchain_core.language_models.chat_models import BaseChatModel

from recruiter_agent.jobs.models import FitAssessment, JobPosting
from recruiter_agent.profile.models import CandidateProfile

FIT_REVIEW_PROMPT = """You recommend whether a job fits a candidate's explicit preferences.
Use only the supplied structured job facts and candidate preferences. Do not browse,
search, infer unstated facts, or add outside knowledge. Job and company facts include
evidence and source URLs: preserve that provenance in each criterion result.

For every relevant preference, return a criterion with status match, mismatch, or unknown.
- Use mismatch only when supplied evidence directly contradicts a stated preference.
- Use unknown when evidence is absent, ambiguous, contradictory, or not comparable.
- A salary range that overlaps a minimum but whose lower bound is below it is unknown.
- Currency mismatch or missing currency is unknown; do not convert currencies.
- For exclusions/dealbreakers (especially defense companies), lack of evidence is unknown,
  never a match or clearance. Only explicit, reliable evidence can identify a mismatch.
- Overall match means no known explicit preference failure; describe it as provisional if
  important criteria are unknown. Overall mismatch requires an explicit contradiction.
  If there is too little information for any useful comparison, use overall unknown.

Summarize the recommendation clearly, state uncertainty and conflicts, and avoid making
application decisions for the candidate."""


def _recommendation_confidence(assessment: FitAssessment) -> FitAssessment:
    """Cap confidence when unresolved criteria or dealbreakers remain."""
    unknown_count = sum(criterion.status.value == "unknown" for criterion in assessment.criteria)
    defense_unknown = any(
        criterion.criterion == "excluded_criteria:defense" and criterion.status.value == "unknown"
        for criterion in assessment.criteria
    )
    if defense_unknown or unknown_count >= 2:
        assessment.confidence = "low"
    elif unknown_count == 1:
        assessment.confidence = "medium"
    return assessment


def evaluate_fit(
    job: JobPosting,
    profile: CandidateProfile,
    model: BaseChatModel,
) -> FitAssessment:
    """Ask the configured model for a recommendation grounded only in supplied facts."""
    structured_model = model.with_structured_output(FitAssessment)
    result = structured_model.invoke(
        f"{FIT_REVIEW_PROMPT}\n\n"
        f"Candidate preferences:\n{profile.preferences.model_dump_json(indent=2)}\n\n"
        f"Job facts and evidence:\n{job.model_dump_json(indent=2)}"
    )
    if not isinstance(result, FitAssessment):
        if hasattr(result, "content"):
            content = result.content
            if isinstance(content, str):
                try:
                    result = json.loads(content)
                except json.JSONDecodeError as exc:
                    raise ValueError("Fit model returned invalid structured JSON.") from exc
        result = FitAssessment.model_validate(result)
    result = _recommendation_confidence(result)

    defense_criterion = next(
        (
            criterion
            for criterion in result.criteria
            if criterion.criterion == "excluded_criteria:defense"
        ),
        None,
    )
    defense_preference_exists = any(
        "defense" in exclusion.casefold() for exclusion in profile.preferences.excluded_criteria
    )
    if defense_preference_exists and defense_criterion is not None:
        if defense_criterion.status.value == "match" and not defense_criterion.job_evidence:
            defense_criterion.status = "unknown"
            defense_criterion.rationale = (
                "No explicit defense evidence was provided; absence of evidence is not clearance."
            )
            if result.overall_status.value == "match":
                result.overall_status = "unknown"
                result.summary = (
                    "Overall fit is unknown because the defense-company dealbreaker "
                    "is not cleared by the supplied evidence."
                )
            result.confidence = "low"
    return result
