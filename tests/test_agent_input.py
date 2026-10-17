from fastapi.testclient import TestClient

from recruiter_agent.main import app

client = TestClient(app)


def test_accepts_bare_url_as_plain_text() -> None:
    text = "https://careers.example.com/jobs/12345"
    response = client.post("/v1/agent/input", json={"text": text})

    assert response.status_code == 202
    assert response.json()["status"] == "accepted"


def test_accepts_natural_language_without_extracting_url() -> None:
    text = "Can you apply to this job for me? https://jobs.ashbyhq.com/example/12345"
    response = client.post(
        "/v1/agent/input",
        json={"text": text},
    )

    assert response.status_code == 202
    assert "job_url" not in response.json()


def test_accepts_text_without_any_url() -> None:
    response = client.post("/v1/agent/input", json={"text": "Find a good AI job"})

    assert response.status_code == 202


def test_rejects_empty_or_oversized_text() -> None:
    empty = client.post("/v1/agent/input", json={"text": ""})
    oversized = client.post("/v1/agent/input", json={"text": "x" * 4001})

    assert empty.status_code == 422
    assert oversized.status_code == 422
