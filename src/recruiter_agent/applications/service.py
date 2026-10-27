"""In-memory application drafts with a one-use, user-confirmed submit transition."""

from __future__ import annotations

import asyncio
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlmodel import Session, select

from recruiter_agent.applications.ashby import (
    AshbyFormSession,
    validate_ashby_url,
)
from recruiter_agent.applications.models import (
    ApplicationDraft,
    FileUpload,
)
from recruiter_agent.jobs.repository import Job, JobStatus
from recruiter_agent.jobs.services.jobs import create_job, update_job
from recruiter_agent.jobs.services.schemas import JobCreate, JobUpdate
from recruiter_agent.profile.loader import load_profile

SESSION_TTL = timedelta(minutes=20)


class DraftNotFoundError(Exception):
    """The in-memory application draft is missing or expired."""


class DraftConflictError(Exception):
    """The application is no longer in a state that permits this operation."""


@dataclass
class ActiveDraft:
    draft: ApplicationDraft
    browser_session: AshbyFormSession | None
    lock: asyncio.Lock


class ApplicationService:
    """Own browser-backed drafts; do not expose browser controls to the agent model."""

    def __init__(self) -> None:
        self._drafts: dict[str, ActiveDraft] = {}
        self._expiry_tasks: dict[str, asyncio.Task] = {}

    async def prepare(self, db: Session, application_url: str) -> ApplicationDraft:
        """Open one Ashby form, prefill known facts, and create/update its job tracker row."""
        safe_url = validate_ashby_url(application_url)
        try:
            profile = load_profile()
        except Exception:
            raise ValueError(
                "Set up a valid local candidate profile before preparing an application."
            ) from None
        browser_session = await AshbyFormSession.open(safe_url, profile)
        try:
            existing = db.exec(select(Job).where(Job.url == safe_url)).first()
            if existing and existing.status not in {
                JobStatus.SAVED,
                JobStatus.RESEARCHING,
                JobStatus.INTERESTED,
                JobStatus.DRAFT_READY,
            }:
                raise DraftConflictError(
                    "This job's tracker status does not allow a new application."
                )
            if existing:
                job = update_job(
                    db,
                    existing.id,
                    JobUpdate(status=JobStatus.DRAFT_READY),
                )
            else:
                job = create_job(
                    db,
                    JobCreate(url=safe_url, status=JobStatus.DRAFT_READY),
                )
        except Exception:
            await browser_session.close()
            raise

        draft = ApplicationDraft(
            id=str(uuid4()),
            job_id=job.id,
            job_title=job.title,
            company=job.company,
            application_url=safe_url,
            state="ready_for_review",
            fields=browser_session.fields,
            expires_at=datetime.now(UTC) + SESSION_TTL,
            review_token=secrets.token_urlsafe(32),
        )
        self._drafts[draft.id] = ActiveDraft(draft, browser_session, asyncio.Lock())
        self._expiry_tasks[draft.id] = asyncio.create_task(self._expire_draft(draft.id))
        return draft

    async def get(self, draft_id: str) -> ApplicationDraft:
        active = await self._active(draft_id)
        return active.draft

    async def update_answers(
        self,
        draft_id: str,
        values: dict[str, str | bool | None],
    ) -> ApplicationDraft:
        active = await self._active(draft_id)
        async with active.lock:
            self._require_editable(active)
            browser = self._browser(active)
            await browser.update_values(values)
            active.draft.fields = browser.fields
            active.draft.review_token = secrets.token_urlsafe(32)
            active.draft.expires_at = datetime.now(UTC) + SESSION_TTL
            return active.draft

    async def attach_file(
        self, draft_id: str, field_id: str, payload: FileUpload
    ) -> ApplicationDraft:
        active = await self._active(draft_id)
        async with active.lock:
            self._require_editable(active)
            browser = self._browser(active)
            active.draft.fields = await browser.attach_file(
                field_id,
                payload.name,
                payload.content_type,
                payload.content_base64,
            )
            active.draft.review_token = secrets.token_urlsafe(32)
            active.draft.expires_at = datetime.now(UTC) + SESSION_TTL
            return active.draft

    async def confirm(
        self,
        db: Session,
        draft_id: str,
        review_token: str,
        user_confirmed: bool,
    ) -> ApplicationDraft:
        active = await self._active(draft_id)
        async with active.lock:
            self._require_editable(active)
            if user_confirmed is not True:
                raise DraftConflictError("Explicit user confirmation is required.")
            if not active.draft.ready_to_submit:
                raise DraftConflictError("Complete every required answer before submitting.")
            if not secrets.compare_digest(active.draft.review_token or "", review_token):
                raise DraftConflictError(
                    "The review changed. Check the latest answers and confirm again."
                )
            browser = self._browser(active)
            if not await browser.matches_review(active.draft.fields):
                active.draft.fields = browser.fields
                active.draft.review_token = secrets.token_urlsafe(32)
                raise DraftConflictError("The Ashby form changed after review. Review it again.")
            await browser.validate_before_submit()

            active.draft.state = "submitting"
            active.draft.review_token = None
            try:
                outcome = await browser.submit_once()
            except Exception:
                outcome = "uncertain"
            try:
                await browser.close()
            except Exception:
                pass
            active.browser_session = None

            if outcome == "submitted":
                active.draft.state = "submitted"
                try:
                    update_job(
                        db,
                        active.draft.job_id,
                        JobUpdate(status=JobStatus.APPLIED),
                    )
                except Exception:
                    active.draft.message = (
                        "Ashby confirmed the application, but the tracker could not be updated. "
                        "Mark this job as applied manually."
                    )
            else:
                active.draft.state = "uncertain"
                active.draft.message = (
                    "The form was submitted, but Ashby did not show a recognizable success "
                    "message. Verify the application on Ashby before trying again."
                )
            for field in active.draft.fields:
                field.value = None
                field.file_name = None
                field.source = "unanswered"
            active.draft.expires_at = datetime.now(UTC) + SESSION_TTL
            return active.draft

    async def close_all(self) -> None:
        """Close live browser sessions during application shutdown."""
        for task in self._expiry_tasks.values():
            task.cancel()
        if self._expiry_tasks:
            await asyncio.gather(*self._expiry_tasks.values(), return_exceptions=True)
        self._expiry_tasks.clear()
        for active in self._drafts.values():
            if active.browser_session is not None:
                try:
                    await active.browser_session.close()
                except Exception:
                    pass
                active.browser_session = None

    async def _expire_draft(self, draft_id: str) -> None:
        """Close the browser and discard answers when a draft's idle TTL elapses."""
        try:
            while (active := self._drafts.get(draft_id)) is not None:
                delay = (active.draft.expires_at - datetime.now(UTC)).total_seconds()
                if delay > 0:
                    await asyncio.sleep(delay)
                active = self._drafts.get(draft_id)
                if active is None:
                    return
                async with active.lock:
                    if active.draft.expires_at > datetime.now(UTC):
                        continue
                    if active.browser_session is not None:
                        try:
                            await active.browser_session.close()
                        except Exception:
                            pass
                    active.browser_session = None
                    self._drafts.pop(draft_id, None)
                    return
        except asyncio.CancelledError:
            raise
        finally:
            current = asyncio.current_task()
            if self._expiry_tasks.get(draft_id) is current:
                self._expiry_tasks.pop(draft_id, None)

    async def _active(self, draft_id: str) -> ActiveDraft:
        active = self._drafts.get(draft_id)
        if active is None:
            raise DraftNotFoundError
        if active.draft.expires_at < datetime.now(UTC):
            if active.browser_session is not None:
                try:
                    await active.browser_session.close()
                except Exception:
                    pass
            del self._drafts[draft_id]
            raise DraftNotFoundError
        return active

    @staticmethod
    def _require_editable(active: ActiveDraft) -> None:
        if active.draft.state != "ready_for_review":
            raise DraftConflictError("This application draft can no longer be edited.")

    @staticmethod
    def _browser(active: ActiveDraft) -> AshbyFormSession:
        if active.browser_session is None:
            raise DraftNotFoundError
        return active.browser_session


application_service = ApplicationService()
