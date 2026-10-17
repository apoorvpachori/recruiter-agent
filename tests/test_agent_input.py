from unittest.mock import patch

from fastapi.testclient import TestClient

from recruiter_agent.main import app

client = TestClient(app)


def test_endpoint_passes_plain_text_to_agent_and_returns_response() -> None:
    text = "https://careers.example.com/jobs/12345"
    with patch(
        "recruiter_agent.api.agent_input.invoke_agent",
        return_value="I received the link.",
    ) as invoke:
        response = client.post("/v1/agent/input", json={"text": text})

    assert response.status_code == 200
    assert response.json() == {
        "status": "accepted",
        "response": "I received the link.",
        "message": "Agent response generated.",
    }
    invoke.assert_called_once_with(text)


def test_accepts_natural_language_without_extracting_url() -> None:
    text = "Can you apply to this job for me? https://jobs.ashbyhq.com/example/12345"
    with patch("recruiter_agent.api.agent_input.invoke_agent", return_value="Draft response."):
        response = client.post("/v1/agent/input", json={"text": text})

    assert response.status_code == 200
    assert "response" in response.json()


def test_accepts_text_without_any_url() -> None:
    with patch("recruiter_agent.api.agent_input.invoke_agent", return_value="Noted."):
        response = client.post("/v1/agent/input", json={"text": "Find a good AI job"})

    assert response.status_code == 200


def test_rejects_empty_or_oversized_text() -> None:
    empty = client.post("/v1/agent/input", json={"text": ""})
    oversized = client.post("/v1/agent/input", json={"text": "x" * 4001})

    assert empty.status_code == 422
    assert oversized.status_code == 422
