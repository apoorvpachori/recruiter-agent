"""Factory and invocation helpers for the text-only ReAct agent graph."""

import logging
import time

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tracers.context import tracing_v2_enabled
from langsmith import traceable

from recruiter_agent.agent.prompts import RECRUITER_SYSTEM_PROMPT
from recruiter_agent.agent.tools import read_webpage
from recruiter_agent.providers.fireworks import create_fireworks_model
from recruiter_agent.settings import get_settings

logger = logging.getLogger(__name__)


def create_agent_graph(model: BaseChatModel):
    """Build an uncheckpointed LangChain v1 agent graph with no tools."""
    return create_agent(
        model=model,
        tools=[read_webpage],
        system_prompt=RECRUITER_SYSTEM_PROMPT,
    )


@traceable(name="recruiter_agent.invoke", run_type="chain")
def invoke_agent(text: str) -> str:
    """Run one stateless text turn and return the final assistant response."""
    settings = get_settings()
    settings.configure_langsmith()

    graph = create_agent_graph(create_fireworks_model(settings))
    started = time.perf_counter()
    metadata = {
        key: value
        for key, value in {
            "agent_id": settings.langsmith_agent_id,
            "agent_environment": settings.langsmith_agent_environment,
        }.items()
        if value
    }
    with tracing_v2_enabled(
        project_name=settings.langsmith_project,
        client=make_langsmith_client(settings),
    ) as tracer:
        result = graph.invoke(
            {"messages": [("user", text)]},
            config={"callbacks": [tracer], "metadata": metadata},
        )
    messages = result["messages"]
    if not messages:
        raise RuntimeError("The agent returned no messages.")
    logger.info(
        "agent_run_completed",
        extra={
            "event": "agent_run_completed",
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            "message_count": len(messages),
        },
    )
    return str(messages[-1].content)


def make_langsmith_client(settings):
    """Build an explicit LangSmith client for the configured endpoint/key."""
    from langsmith import Client

    api_key = settings.langsmith_api_key.get_secret_value()
    return Client(api_url=settings.langsmith_endpoint, api_key=api_key)
