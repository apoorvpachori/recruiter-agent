import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from recruiter_agent.agent.graph import create_agent_graph, create_model
from recruiter_agent.settings import Settings


def test_react_graph_returns_fake_model_response() -> None:
    graph = create_agent_graph(FakeListChatModel(responses=["Hello from the test model."]))

    result = graph.invoke({"messages": [("user", "Hello, agent.")]})

    assert result["messages"][-1].content == "Hello from the test model."


def test_model_configuration_requires_a_fireworks_key() -> None:
    settings = Settings(fireworks_api_key="", fireworks_model="accounts/fireworks/models/test")

    with pytest.raises(RuntimeError, match="FIREWORKS_API_KEY"):
        create_model(settings)
