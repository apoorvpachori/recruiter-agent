from datetime import date

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage

from recruiter_agent.jobs.fit import evaluate_fit
from recruiter_agent.jobs.models import Compensation, FitAssessment, FitStatus, JobFact, JobPosting
from recruiter_agent.profile.models import CandidateProfile, Preferences


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


class FakeStructuredFitModel(FakeListChatModel):
    responses: list[str | AIMessage]
    requested_schema: type | None = None

    def with_structured_output(self, schema, **kwargs):
        self.requested_schema = schema
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        from langchain_core.outputs import ChatGeneration, ChatResult

        response = self.responses[self.i]
        self.i = (self.i + 1) % len(self.responses)
        message = response if isinstance(response, AIMessage) else AIMessage(content=response)
        return ChatResult(generations=[ChatGeneration(message=message)])


def _job(**overrides) -> JobPosting:
    values = {
        "source_url": "https://jobs.example.com/role",
        "title": JobFact(value="Applied AI Engineer", evidence="Job title"),
        "company": JobFact(value="Example AI", evidence="Company name"),
        "location": JobFact(value="San Francisco, CA", evidence="Job location"),
        "work_arrangement": JobFact(value="On-site", evidence="On-site role"),
        "compensation": Compensation(
            minimum=200_000,
            maximum=240_000,
            currency="USD",
            evidence="Posted salary: $200,000 to $240,000 USD",
        ),
        "employee_count": JobFact(value=25, evidence="25 employees"),
        "funding_stage": JobFact(value="Series B", evidence="Series B"),
        "industry": JobFact(value="AI software", evidence="AI software product"),
    }
    values.update(overrides)
    return JobPosting(**values)


def test_evaluate_fit_uses_structured_llm_recommendation() -> None:
    model = FakeStructuredFitModel(
        responses=[
            '{"overall_status":"match","summary":"Provisional match with unknowns.",'
            '"rationale":"Known criteria align; defense remains unverified.","confidence":"medium",'
            '"criteria":[]}'
        ]
    )

    assessment = evaluate_fit(_job(), _profile(), model)

    assert assessment.overall_status == FitStatus.MATCH
    assert assessment.confidence == "medium"
    assert model.requested_schema is FitAssessment


def test_evaluate_fit_can_recommend_mismatch_for_explicit_conflict() -> None:
    model = FakeStructuredFitModel(
        responses=[
            AIMessage(
                content=(
                    '{"overall_status":"mismatch","summary":"Salary is below minimum.",'
                    '"rationale":"The advertised range is under $180,000.","confidence":"high",'
                    '"criteria":[]}'
                )
            )
        ]
    )

    assessment = evaluate_fit(
        _job(compensation=Compensation(minimum=150_000, maximum=170_000, currency="USD")),
        _profile(),
        model,
    )

    assert assessment.overall_status == FitStatus.MISMATCH


def test_evaluate_fit_keeps_insufficient_facts_unknown() -> None:
    model = FakeStructuredFitModel(
        responses=[
            '{"overall_status":"unknown","summary":"Need role location.",'
            '"rationale":"Posting omits location and defense clearance.","confidence":"low",'
            '"criteria":[]}'
        ]
    )

    assessment = evaluate_fit(
        _job(location=JobFact(), work_arrangement=JobFact(), compensation=Compensation()),
        _profile(),
        model,
    )

    assert assessment.overall_status == FitStatus.UNKNOWN


def test_evaluate_fit_does_not_clear_defense_exclusion_without_evidence() -> None:
    model = FakeStructuredFitModel(
        responses=[
            '{"overall_status":"match","summary":"Everything matches.",'
            '"rationale":"No defense work is mentioned.","confidence":"high",'
            '"criteria":[{"criterion":"excluded_criteria:defense","status":"match",'
            '"rationale":"No defense work found.","job_evidence":null,'
            '"preference":"No defense companies"}]}'
        ]
    )

    assessment = evaluate_fit(_job(), _profile(), model)

    defense = next(
        item for item in assessment.criteria if item.criterion == "excluded_criteria:defense"
    )
    assert defense.status == FitStatus.UNKNOWN
    assert assessment.overall_status == FitStatus.UNKNOWN
    assert assessment.confidence == "low"
