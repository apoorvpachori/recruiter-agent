"""Generic text input endpoint for starting agent work."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/v1/agent", tags=["agent"])


class AgentInputRequest(BaseModel):
    """A natural-language message supplied to the agent."""

    text: str = Field(min_length=1, max_length=4000)


class AgentInputResponse(BaseModel):
    """Acknowledgement of an accepted text message."""

    status: str
    message: str


@router.post("/input", response_model=AgentInputResponse, status_code=202)
def submit_agent_input(request: AgentInputRequest) -> AgentInputResponse:
    """Accept a text prompt without interpreting or processing it."""
    return AgentInputResponse(
        status="accepted",
        message="Text input received. Agent processing is not implemented yet.",
    )
