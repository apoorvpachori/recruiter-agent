from fastapi.testclient import TestClient

from recruiter_agent.main import app

client = TestClient(app)
JOB_URL = "https://jobs.ashbyhq.com/example-company/12345"


def test_accepts_bare_job_url() -> None:
    response = client.post("/v1/agent/input", json={"text": JOB_URL})

    assert response.status_code == 202
    assert response.json()["job_url"] == JOB_URL
    assert response.json()["status"] == "accepted"


def test_extracts_job_url_from_natural_language() -> None:
    response = client.post(
        "/v1/agent/input",
        json={"text": f"Can you apply to this job for me? {JOB_URL}"},
    )

    assert response.status_code == 202
    assert response.json()["job_url"] == JOB_URL


def test_rejects_missing_or_unsupported_url() -> None:
    missing_url = client.post("/v1/agent/input", json={"text": "Find a good AI job"})
    unsupported_url = client.post(
        "/v1/agent/input",
        json={"text": "https://example.com/jobs/123"},
    )

    assert missing_url.status_code == 422
    assert unsupported_url.status_code == 422


def test_rejects_multiple_urls() -> None:
    response = client.post(
        "/v1/agent/input",
        json={"text": f"Compare {JOB_URL} and {JOB_URL}"},
    )

    assert response.status_code == 422
