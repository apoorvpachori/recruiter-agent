"""Factory and invocation helpers for the text-only ReAct agent graph."""

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langsmith import traceable

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


@traceable(name="recruiter_agent.invoke", run_type="chain")
def invoke_agent(text: str) -> str:
    """Run one stateless text turn and return the final assistant response."""
    settings = get_settings()
    settings.configure_langsmith()

    graph = create_agent_graph(create_fireworks_model(settings))
    metadata = {
        key: value
        for key, value in {
            "agent_id": settings.langsmith_agent_id,
            "agent_environment": settings.langsmith_agent_environment,
        }.items()
        if value
    }
    result = graph.invoke(
        {"messages": [("user", text)]},
        config={
            "callbacks": [make_langsmith_tracer(settings)],
            "run_name": "recruiter_agent.graph",
            "metadata": metadata,
            "tags": ["recruiter-agent", "langgraph"],
        },
    )
    messages = result["messages"]
    if not messages:
        raise RuntimeError("The agent returned no messages.")
    return str(messages[-1].content)


def make_langsmith_tracer(settings):
    """Build a LangChain tracer backed by the configured LangSmith client."""
    from langchain_core.tracers import LangChainTracer
    from langsmith import Client

    if not settings.langsmith_api_key or not settings.langsmith_api_key.get_secret_value():
        raise RuntimeError("Set LANGSMITH_API_KEY in .env to enable LangSmith tracing.")
    client = Client(
        api_url=settings.langsmith_endpoint,
        api_key=settings.langsmith_api_key.get_secret_value(),
    )
    return LangChainTracer(project_name=settings.langsmith_project, client=client)
