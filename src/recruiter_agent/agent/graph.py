"""Factory and invocation helpers for the text-only ReAct agent graph."""

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tracers.context import tracing_v2_enabled

from recruiter_agent.agent.prompts import RECRUITER_SYSTEM_PROMPT
from recruiter_agent.providers.fireworks import create_fireworks_model
from recruiter_agent.settings import get_settings


def create_agent_graph(model: BaseChatModel):
    """Build an uncheckpointed LangChain v1 agent graph with no tools."""
    return create_agent(
        model=model,
        tools=[],
        system_prompt=RECRUITER_SYSTEM_PROMPT,
    )


def invoke_agent(text: str) -> str:
    """Run one stateless text turn and return the final assistant response."""
    settings = get_settings()
    settings.configure_langsmith()

    graph = create_agent_graph(create_fireworks_model(settings))
    if settings.langsmith_tracing:
        with tracing_v2_enabled(project_name=settings.langsmith_project):
            result = graph.invoke({"messages": [("user", text)]})
    else:
        result = graph.invoke({"messages": [("user", text)]})
    messages = result["messages"]
    if not messages:
        raise RuntimeError("The agent returned no messages.")
    return str(messages[-1].content)
