"""Application preparation and explicit per-draft confirmation endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from recruiter_agent.applications.ashby import ApplicationBlockedError
from recruiter_agent.applications.models import (
    AnswerUpdate,
    ApplicationDraft,
    FileUpload,
    PrepareApplicationRequest,
    SubmissionConfirmation,
)
from recruiter_agent.applications.service import (
    DraftConflictError,
    DraftNotFoundError,
    application_service,
)
from recruiter_agent.database import get_db_session
from recruiter_agent.jobs.services.jobs import (
    JobAlreadyExistsError,
    JobNotFoundError,
)

router = APIRouter(prefix="/v1/applications", tags=["applications"])
DB_SESSION = Depends(get_db_session)


@router.post("/prepare", response_model=ApplicationDraft)
async def prepare_application(
    request: PrepareApplicationRequest,
    session: Session = DB_SESSION,
) -> ApplicationDraft:
    """Prepare an Ashby form without submitting it."""
    try:
        return await application_service.prepare(session, request.application_url)
    except (ApplicationBlockedError, FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (JobAlreadyExistsError, DraftConflictError) as exc:
        raise HTTPException(
            status_code=409, detail=str(exc) or "Application could not be prepared."
        ) from exc


@router.get("/{draft_id}", response_model=ApplicationDraft)
async def get_application_draft(draft_id: str) -> ApplicationDraft:
    try:
        return await application_service.get(draft_id)
    except DraftNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail="Application draft expired or was not found."
        ) from exc


@router.patch("/{draft_id}/answers", response_model=ApplicationDraft)
async def update_application_answers(
    draft_id: str,
    request: AnswerUpdate,
) -> ApplicationDraft:
    try:
        return await application_service.update_answers(draft_id, request.values)
    except DraftNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail="Application draft expired or was not found."
        ) from exc
    except (ApplicationBlockedError, DraftConflictError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{draft_id}/fields/{field_id}/file", response_model=ApplicationDraft)
async def attach_application_file(
    draft_id: str,
    field_id: str,
    request: FileUpload,
) -> ApplicationDraft:
    try:
        return await application_service.attach_file(draft_id, field_id, request)
    except DraftNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail="Application draft expired or was not found."
        ) from exc
    except (ApplicationBlockedError, DraftConflictError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{draft_id}/confirm", response_model=ApplicationDraft)
async def confirm_application_submission(
    draft_id: str,
    request: SubmissionConfirmation,
    session: Session = DB_SESSION,
) -> ApplicationDraft:
    """Submit one reviewed application after explicit UI confirmation."""
    try:
        return await application_service.confirm(
            session, draft_id, request.review_token, request.user_confirmed
        )
    except DraftNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail="Application draft expired or was not found."
        ) from exc
    except (ApplicationBlockedError, DraftConflictError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (JobNotFoundError, JobAlreadyExistsError) as exc:
        raise HTTPException(status_code=409, detail="Could not update the job tracker.") from exc
