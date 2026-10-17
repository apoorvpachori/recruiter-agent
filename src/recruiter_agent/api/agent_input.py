"""Generic text input endpoint for starting agent work."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from recruiter_agent.agent.graph import invoke_agent

router = APIRouter(prefix="/v1/agent", tags=["agent"])


class AgentInputRequest(BaseModel):
    """A natural-language message supplied to the agent."""

    text: str = Field(min_length=1, max_length=4000)


class AgentInputResponse(BaseModel):
    """Agent response to an accepted text message."""

    status: str
    response: str
    message: str


@router.post("/input", response_model=AgentInputResponse)
def submit_agent_input(request: AgentInputRequest) -> AgentInputResponse:
    """Run a single text-only agent turn."""
    response = invoke_agent(request.text)
    return AgentInputResponse(
        status="accepted",
        response=response,
        message="Agent response generated.",
    )
