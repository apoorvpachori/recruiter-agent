"""Factory and invocation helpers for the text-only ReAct agent graph."""

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_fireworks import ChatFireworks

from recruiter_agent.agent.prompts import RECRUITER_SYSTEM_PROMPT
from recruiter_agent.settings import Settings, get_settings


def create_model(settings: Settings | None = None) -> BaseChatModel:
    """Create the configured Fireworks chat model."""
    settings = settings or get_settings()
    if not settings.fireworks_api_key or not settings.fireworks_api_key.get_secret_value():
        raise RuntimeError("Set FIREWORKS_API_KEY in .env before invoking the agent.")
    if not settings.fireworks_model:
        raise RuntimeError("Set FIREWORKS_MODEL in .env before invoking the agent.")

    return ChatFireworks(
        model=settings.fireworks_model,
        api_key=settings.fireworks_api_key,
    )


def create_agent_graph(model: BaseChatModel):
    """Build an uncheckpointed LangChain v1 agent graph with no tools."""
    return create_agent(
        model=model,
        tools=[],
        system_prompt=RECRUITER_SYSTEM_PROMPT,
    )


def invoke_agent(text: str) -> str:
    """Run one stateless text turn and return the final assistant response."""
    result = create_agent_graph(create_model()).invoke({"messages": [("user", text)]})
    messages = result["messages"]
    if not messages:
        raise RuntimeError("The agent returned no messages.")
    return str(messages[-1].content)
