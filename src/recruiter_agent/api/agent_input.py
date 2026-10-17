"""Text input endpoint for starting agent work."""

import re
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/v1/agent", tags=["agent"])

URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
SUPPORTED_HOSTS = {"ashbyhq.com", "jobs.ashbyhq.com"}


class AgentInputRequest(BaseModel):
    """A natural-language instruction that may include an Ashby job URL."""

    text: str = Field(min_length=1, max_length=4000)


class AgentInputResponse(BaseModel):
    """Acknowledgement of a recognized job URL input."""

    status: str
    job_url: str
    message: str


def extract_ashby_job_url(text: str) -> str:
    """Extract exactly one supported Ashby URL from a text prompt."""
    urls = URL_PATTERN.findall(text)
    if len(urls) != 1:
        raise HTTPException(
            status_code=422,
            detail="Include exactly one Ashby job URL in your message.",
        )

    url = urls[0].rstrip(".,!?;:)")
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()

    if (
        parsed.scheme.lower() != "https"
        or host not in SUPPORTED_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
    ):
        raise HTTPException(
            status_code=422,
            detail="For now, provide one HTTPS Ashby job link (jobs.ashbyhq.com).",
        )

    return url


@router.post("/input", response_model=AgentInputResponse, status_code=202)
def submit_agent_input(request: AgentInputRequest) -> AgentInputResponse:
    """Accept a text prompt and acknowledge a supported job URL."""
    job_url = extract_ashby_job_url(request.text.strip())
    return AgentInputResponse(
        status="accepted",
        job_url=job_url,
        message="Job link received. Agent processing is not implemented yet.",
    )
