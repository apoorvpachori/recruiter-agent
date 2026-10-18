import os

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage, ToolMessage

from recruiter_agent.agent.graph import create_agent_graph
from recruiter_agent.providers.fireworks import create_fireworks_model
from recruiter_agent.settings import Settings
from recruiter_agent.tools.read_webpage import PageContent


class FakeToolCallingModel(FakeListChatModel):
    responses: list[str | AIMessage]

    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        from langchain_core.outputs import ChatGeneration, ChatResult

        response = self.responses[self.i]
        self.i = (self.i + 1) % len(self.responses)
        if isinstance(response, AIMessage):
            message = response
        else:
            message = AIMessage(content=response)
        return ChatResult(generations=[ChatGeneration(message=message)])


def test_react_graph_returns_fake_model_response() -> None:
    graph = create_agent_graph(FakeToolCallingModel(responses=["Hello from the test model."]))

    result = graph.invoke({"messages": [("user", "Hello, agent.")]})

    assert result["messages"][-1].content == "Hello from the test model."


def test_react_graph_exposes_webpage_reader_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_read_webpage(url: str) -> PageContent:
        return PageContent(
            url=url,
            final_url=url,
            title="Example role",
            description=None,
            text="Build AI systems.",
            truncated=False,
        )

    monkeypatch.setattr("recruiter_agent.agent.tools.get_page_url", fake_read_webpage)
    model = FakeToolCallingModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "read_webpage",
                        "args": {"url": "https://example.com/job"},
                        "id": "read-page-1",
                    }
                ],
            ),
            AIMessage(content="This looks like an Applied AI role building AI systems."),
        ]
    )
    graph = create_agent_graph(model)

    result = graph.invoke({"messages": [("user", "Read https://example.com/job")]})

    assert isinstance(result["messages"][-2], ToolMessage)
    assert result["messages"][-2].name == "read_webpage"
    assert "Applied AI role" in result["messages"][-1].content


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
