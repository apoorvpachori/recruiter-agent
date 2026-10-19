import os

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage, ToolMessage

from recruiter_agent.agent.graph import create_agent_graph
from recruiter_agent.profile.models import CandidateProfile
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


def empty_test_profile() -> CandidateProfile:
    return CandidateProfile(schema_version=1)


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
    monkeypatch.setattr(
        "recruiter_agent.agent.tools._web_search_provider.search",
        lambda query, max_results=5: {"query": query, "results": []},
    )
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


def test_react_graph_exposes_deterministic_fit_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    from recruiter_agent.jobs.models import JobPageExtraction

    class FakeExtractionModel:
        def with_structured_output(self, schema):
            assert schema is JobPageExtraction
            return self

        def invoke(self, prompt):
            return JobPageExtraction()

    def fake_read_page(url: str) -> PageContent:
        return PageContent(
            url=url,
            final_url=url,
            title="Example job",
            text="Example job description.",
        )

    monkeypatch.setattr("recruiter_agent.agent.tools.get_page_url", fake_read_page)
    monkeypatch.setattr(
        "recruiter_agent.agent.tools.create_fireworks_model", lambda settings: FakeExtractionModel()
    )
    monkeypatch.setattr("recruiter_agent.agent.tools.load_profile", empty_test_profile)
    model = FakeToolCallingModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "evaluate_job_fit",
                        "args": {"job": {"source_url": "https://example.com/job"}},
                        "id": "evaluate-fit-1",
                    }
                ],
            ),
            AIMessage(content="This is a fit based on known preferences."),
        ]
    )
    graph = create_agent_graph(model)

    result = graph.invoke({"messages": [("user", "Check fit for https://example.com/job")]})

    assert isinstance(result["messages"][-2], ToolMessage)
    assert result["messages"][-2].name == "evaluate_job_fit"
    assert "fit based on known preferences" in result["messages"][-1].content


def test_react_graph_exposes_company_search_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import UTC, datetime

    from recruiter_agent.providers.search import SearchResult, WebSearchResponse

    monkeypatch.setattr(
        "recruiter_agent.agent.tools._web_search_provider.search",
        lambda query, max_results=5: WebSearchResponse(
            query=query,
            provider="brave",
            retrieved_at=datetime.now(UTC),
            results=[
                SearchResult(
                    title="Example Series B announcement",
                    url="https://example.com/news/series-b",
                    snippet="Example AI raised a Series B round.",
                )
            ],
        ),
    )
    model = FakeToolCallingModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_company_web",
                        "args": {"query": "Example AI funding stage"},
                        "id": "search-company-1",
                    }
                ],
            ),
            AIMessage(content="I found a source reporting a Series B round."),
        ]
    )

    result = create_agent_graph(model).invoke(
        {"messages": [("user", "Research Example AI's funding stage.")]}
    )

    assert isinstance(result["messages"][-2], ToolMessage)
    assert result["messages"][-2].name == "search_company_web"
    assert "Series B round" in result["messages"][-1].content


def test_fit_tool_stops_when_job_url_redirects_to_generic_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from recruiter_agent.agent.tools import evaluate_job_fit
    from recruiter_agent.tools.read_webpage import PageContent

    monkeypatch.setattr(
        "recruiter_agent.agent.tools.get_page_url",
        lambda url: PageContent(
            url=url,
            final_url="https://jobs.example.com/company?error=true",
            title="Jobs at Example Company",
            description=None,
            text="General job board listing text.",
        ),
    )

    result = evaluate_job_fit.invoke(
        {"job": {"source_url": "https://jobs.example.com/company/role-id"}}
    )

    assert result["job"]["page_issue"] is not None
    assert result["assessment"]["overall_status"] == "unknown"
    assert all(criterion["status"] == "unknown" for criterion in result["assessment"]["criteria"])


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
