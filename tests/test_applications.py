import asyncio
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

from recruiter_agent.applications import ashby
from recruiter_agent.applications.models import (
    ApplicationDraft,
    ApplicationField,
    SubmissionConfirmation,
)
from recruiter_agent.applications.service import (
    ActiveDraft,
    ApplicationService,
    DraftConflictError,
)
from recruiter_agent.database import create_schema, get_db_session
from recruiter_agent.jobs.repository import Job, JobStatus
from recruiter_agent.main import app, make_lifespan
from recruiter_agent.profile.models import CandidateProfile


@pytest.fixture
def api_client() -> Generator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def override_session() -> Generator[Session]:
        with Session(engine) as session:
            yield session

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = make_lifespan(lambda: create_schema(engine))
    app.dependency_overrides[get_db_session] = override_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.router.lifespan_context = original_lifespan
        SQLModel.metadata.drop_all(engine)
        engine.dispose()


def test_ashby_url_validation_is_host_and_https_scoped(monkeypatch) -> None:
    monkeypatch.setattr(ashby, "_validate_public_http_url", lambda _url: None)

    assert ashby.validate_ashby_url("https://jobs.ashbyhq.com/acme/role") == (
        "https://jobs.ashbyhq.com/acme/role"
    )
    for url in (
        "http://jobs.ashbyhq.com/acme/role",
        "https://ashbyhq.com/acme/role",
        "https://jobs.ashbyhq.com.attacker.example/acme/role",
        "https://user@jobs.ashbyhq.com/acme/role",
    ):
        with pytest.raises(ashby.ApplicationBlockedError):
            ashby.validate_ashby_url(url)


def test_browser_traffic_policy_tightens_after_form_discovery(monkeypatch) -> None:
    policy = ashby.TrafficPolicy()
    monkeypatch.setattr(ashby, "_validate_browser_destination", lambda _url: True)

    assert ashby._allows_page_request("GET", policy)
    assert not ashby._allows_page_request("POST", policy)
    assert not ashby._allows_websocket("wss://jobs.ashbyhq.com/socket", policy)

    policy.review_locked = True
    assert not ashby._allows_page_request("GET", policy)
    assert not ashby._allows_page_request("POST", policy)

    policy.submission_authorized = True
    assert ashby._allows_page_request("POST", policy)
    assert ashby._allows_websocket("wss://jobs.ashbyhq.com/socket", policy)


@pytest.mark.anyio
async def test_application_form_detection_ignores_a_newsletter_form(monkeypatch) -> None:
    class Forms:
        async def count(self):
            return 2

        def nth(self, index):
            return index

    async def read_fields(form):
        fields = (
            [ApplicationField(id="field-0", label="Email", kind="email")]
            if form == 0
            else [
                ApplicationField(id="field-0", label="Full name", kind="text"),
                ApplicationField(id="field-1", label="Email", kind="email"),
            ]
        )
        return fields, {}

    monkeypatch.setattr(ashby, "_read_fields", read_fields)

    assert await ashby._application_form_indexes(Forms()) == [1]


@pytest.mark.anyio
async def test_application_form_lookup_preserves_selected_form_index(monkeypatch) -> None:
    class Forms:
        async def count(self):
            return 2

        def nth(self, index):
            return index

    class Body:
        async def inner_text(self):
            return ""

    class Page:
        def __init__(self):
            self.forms = Forms()

        def locator(self, selector):
            return self.forms if selector == "form" else Body()

    async def selected_index(_forms):
        return [0]

    monkeypatch.setattr(ashby, "_application_form_indexes", selected_index)

    form, form_index = await ashby._find_application_form(Page())

    assert form == 0
    assert form_index == 0


def test_prefill_maps_only_exact_contact_field_labels() -> None:
    profile = CandidateProfile.model_validate(
        {
            "schema_version": 1,
            "contact": {
                "full_name": "Taylor Candidate",
                "email": "taylor@example.test",
                "phone": "+1 555 0100",
                "linkedin_url": "https://www.linkedin.com/in/taylor-candidate",
            },
        }
    )
    fields = [
        ApplicationField(id="field-0", label="Full name", kind="text"),
        ApplicationField(id="field-1", label="Email address", kind="email"),
        ApplicationField(id="field-2", label="Why do you want this job?", kind="textarea"),
        ApplicationField(id="field-3", label="LinkedIn URL", kind="url"),
    ]

    assert ashby._profile_values(fields, profile) == {
        "field-0": "Taylor Candidate",
        "field-1": "taylor@example.test",
        "field-3": "https://www.linkedin.com/in/taylor-candidate",
    }


def test_submission_requires_literal_user_confirmation() -> None:
    with pytest.raises(ValidationError):
        SubmissionConfirmation.model_validate({"review_token": "x" * 32, "user_confirmed": False})


class FakeAshbySession:
    def __init__(self, fields: list[ApplicationField], outcome: str = "submitted") -> None:
        self.fields = fields
        self.outcome = outcome
        self.submit_count = 0
        self.closed = False

    async def update_values(self, values, *, sources=None):
        for field in self.fields:
            if field.id in values:
                field.value = values[field.id]
                field.source = (sources or {}).get(field.id, "user")
        return self.fields

    async def attach_file(self, *_args):
        return self.fields

    async def matches_review(self, reviewed):
        return [field.model_dump() for field in self.fields] == [
            field.model_dump() for field in reviewed
        ]

    async def validate_before_submit(self):
        return None

    async def submit_once(self):
        self.submit_count += 1
        return self.outcome

    async def close(self):
        self.closed = True


@pytest.mark.anyio
async def test_application_confirmation_is_single_use_and_updates_tracker(
    tmp_path, anyio_backend
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'applications.sqlite3'}")
    create_schema(engine)
    service = ApplicationService()
    fields = [
        ApplicationField(
            id="field-0",
            label="Full name",
            kind="text",
            required=True,
            value=None,
        )
    ]
    draft = ApplicationDraft(
        id="draft-one",
        job_id=1,
        application_url="https://jobs.ashbyhq.com/acme/role",
        state="ready_for_review",
        fields=fields,
        review_token="initial-review-token-which-is-long-enough",
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    browser = FakeAshbySession(fields)
    service._drafts[draft.id] = ActiveDraft(draft, browser, asyncio.Lock())

    with Session(engine) as db:
        db.add(
            Job(
                id=1,
                url=draft.application_url,
                status=JobStatus.DRAFT_READY,
            )
        )
        db.commit()

        with pytest.raises(DraftConflictError, match="required answer"):
            await service.confirm(db, draft.id, draft.review_token, user_confirmed=True)
        assert browser.submit_count == 0

        updated = await service.update_answers(draft.id, {"field-0": "Taylor Candidate"})
        with pytest.raises(DraftConflictError, match="review changed"):
            await service.confirm(
                db,
                draft.id,
                "initial-review-token-which-is-long-enough",
                user_confirmed=True,
            )
        assert browser.submit_count == 0

        submitted = await service.confirm(db, draft.id, updated.review_token, user_confirmed=True)
        assert submitted.state == "submitted"
        assert browser.submit_count == 1
        assert browser.closed
        assert submitted.fields[0].value is None
        assert db.get(Job, 1).status == JobStatus.APPLIED

        with pytest.raises(DraftConflictError, match="no longer be edited"):
            await service.confirm(db, draft.id, updated.review_token, user_confirmed=True)
        assert browser.submit_count == 1

    engine.dispose()


@pytest.mark.anyio
async def test_uncertain_submission_is_not_retried_or_marked_applied(
    tmp_path, anyio_backend
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'uncertain-application.sqlite3'}")
    create_schema(engine)
    service = ApplicationService()
    draft = ApplicationDraft(
        id="draft-uncertain",
        job_id=1,
        application_url="https://jobs.ashbyhq.com/acme/role",
        state="ready_for_review",
        fields=[ApplicationField(id="field-0", label="Name", kind="text")],
        review_token="initial-review-token-which-is-long-enough",
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    browser = FakeAshbySession(draft.fields, outcome="uncertain")
    service._drafts[draft.id] = ActiveDraft(draft, browser, asyncio.Lock())

    with Session(engine) as db:
        db.add(Job(id=1, url=draft.application_url, status=JobStatus.DRAFT_READY))
        db.commit()

        with pytest.raises(DraftConflictError, match="Explicit user confirmation"):
            await service.confirm(db, draft.id, draft.review_token, user_confirmed=False)
        assert browser.submit_count == 0

        result = await service.confirm(db, draft.id, draft.review_token, user_confirmed=True)
        assert result.state == "uncertain"
        assert result.message and "Verify the application" in result.message
        assert browser.submit_count == 1
        assert db.get(Job, 1).status == JobStatus.DRAFT_READY
        with pytest.raises(DraftConflictError, match="no longer be edited"):
            await service.confirm(db, draft.id, draft.review_token or "", user_confirmed=True)
        assert browser.submit_count == 1

    engine.dispose()


@pytest.mark.anyio
async def test_expired_draft_closes_browser_and_discards_answers(anyio_backend) -> None:
    service = ApplicationService()
    draft = ApplicationDraft(
        id="draft-expired",
        job_id=1,
        application_url="https://jobs.ashbyhq.com/acme/role",
        state="ready_for_review",
        fields=[
            ApplicationField(id="field-0", label="Email", kind="email", value="taylor@example.test")
        ],
        review_token="initial-review-token-which-is-long-enough",
        expires_at=datetime.now(UTC) + timedelta(milliseconds=10),
    )
    browser = FakeAshbySession(draft.fields)
    service._drafts[draft.id] = ActiveDraft(draft, browser, asyncio.Lock())
    task = asyncio.create_task(service._expire_draft(draft.id))
    service._expiry_tasks[draft.id] = task

    await task

    assert browser.closed
    assert draft.id not in service._drafts


def test_application_routes_reject_untrusted_host_and_missing_confirmation(
    api_client: TestClient,
) -> None:
    prepare = api_client.post(
        "/v1/applications/prepare",
        json={"application_url": "https://attacker.example/apply"},
    )
    confirmation = api_client.post(
        "/v1/applications/draft-id/confirm",
        json={"review_token": "x" * 32, "user_confirmed": False},
    )

    assert prepare.status_code == 422
    assert confirmation.status_code == 422
