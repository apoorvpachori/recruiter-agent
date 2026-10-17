import os

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from recruiter_agent.agent.graph import create_agent_graph
from recruiter_agent.providers.fireworks import create_fireworks_model
from recruiter_agent.settings import Settings


def test_react_graph_returns_fake_model_response() -> None:
    graph = create_agent_graph(FakeListChatModel(responses=["Hello from the test model."]))

    result = graph.invoke({"messages": [("user", "Hello, agent.")]})

    assert result["messages"][-1].content == "Hello from the test model."


def test_model_configuration_requires_a_fireworks_key() -> None:
    settings = Settings(fireworks_api_key="", fireworks_model="accounts/fireworks/models/test")

    with pytest.raises(RuntimeError, match="FIREWORKS_API_KEY"):
        create_fireworks_model(settings)


def test_langsmith_tracing_sets_project_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        langsmith_tracing=True,
        langsmith_api_key="test-key",
        langsmith_project="recruiter-agent-test",
    )

    settings.configure_langsmith()

    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGCHAIN_TRACING_V2"] == "true"
    assert os.environ["LANGSMITH_PROJECT"] == "recruiter-agent-test"
    assert os.environ["LANGSMITH_API_KEY"] == "test-key"
