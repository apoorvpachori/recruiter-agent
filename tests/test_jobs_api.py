from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

from recruiter_agent.database import get_db_session
from recruiter_agent.jobs.repository import Job, JobStatus
from recruiter_agent.main import app


@pytest.fixture
def client() -> Generator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def override_session() -> Generator[Session]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    SQLModel.metadata.drop_all(engine)
    engine.dispose()


def test_create_list_get_and_update_job(client: TestClient) -> None:
    created = client.post(
        "/v1/jobs",
        json={
            "url": "https://jobs.example.com/role-1",
            "company": "Example AI",
            "title": "Applied AI Engineer",
        },
    )

    assert created.status_code == 201
    job = created.json()
    assert job["status"] == "saved"
    assert job["company"] == "Example AI"

    assert client.get("/v1/jobs").json()[0]["id"] == job["id"]
    assert client.get(f"/v1/jobs/{job['id']}").json()["url"] == job["url"]

    updated = client.patch(f"/v1/jobs/{job['id']}", json={"status": "applied"})
    assert updated.status_code == 200
    assert updated.json()["status"] == "applied"
    assert client.get("/v1/jobs", params={"status": "applied"}).json()[0]["id"] == job["id"]
    assert client.get("/v1/jobs", params={"status": "saved"}).json() == []


def test_create_duplicate_url_returns_conflict(client: TestClient) -> None:
    payload = {"url": "https://jobs.example.com/duplicate"}

    assert client.post("/v1/jobs", json=payload).status_code == 201
    duplicate = client.post("/v1/jobs", json=payload)

    assert duplicate.status_code == 409


def test_get_and_update_unknown_job_return_404(client: TestClient) -> None:
    assert client.get("/v1/jobs/999").status_code == 404
    assert client.patch("/v1/jobs/999", json={"status": "applied"}).status_code == 404


def test_job_model_is_single_table_with_expected_fields() -> None:
    assert set(Job.__table__.columns.keys()) == {
        "id",
        "url",
        "company",
        "title",
        "status",
        "notes",
        "created_at",
        "updated_at",
    }


def test_job_status_values_remain_single_table_enum() -> None:
    assert JobStatus.SAVED.value == "saved"
    assert JobStatus.APPLIED.value == "applied"
