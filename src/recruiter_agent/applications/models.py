"""Contracts for short-lived application drafts and explicit submission approval."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


FieldKind = Literal["text", "email", "phone", "url", "textarea", "select", "checkbox", "file"]
FieldSource = Literal["profile", "user", "unanswered"]
DraftState = Literal["ready_for_review", "blocked", "submitting", "submitted", "uncertain"]


class ApplicationField(StrictModel):
    """One visible Ashby application field and its proposed answer."""

    id: str
    label: str
    kind: FieldKind
    required: bool = False
    value: str | bool | None = None
    options: list[str] = Field(default_factory=list)
    source: FieldSource = "unanswered"
    file_name: str | None = None


class ApplicationDraft(StrictModel):
    """The current, local-only application snapshot shown to the user."""

    id: str
    job_id: int
    job_title: str | None = None
    company: str | None = None
    application_url: str
    state: DraftState
    fields: list[ApplicationField]
    review_token: str | None = None
    expires_at: datetime
    message: str | None = None

    @computed_field
    @property
    def ready_to_submit(self) -> bool:
        return self.state == "ready_for_review" and all(
            not field.required
            or (field.value is not None and field.value is not False and field.value != "")
            for field in self.fields
        )


class PrepareApplicationRequest(StrictModel):
    application_url: str = Field(min_length=1, max_length=2048)


class AnswerUpdate(StrictModel):
    values: dict[str, str | bool | None]


class FileUpload(StrictModel):
    name: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=150)
    content_base64: str = Field(min_length=1, max_length=20_000_000)


class SubmissionConfirmation(StrictModel):
    review_token: str = Field(min_length=32, max_length=256)
    user_confirmed: Literal[True]
