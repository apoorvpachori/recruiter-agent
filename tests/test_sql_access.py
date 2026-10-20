from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine

from recruiter_agent.jobs.repository import Job, JobStatus
from recruiter_agent.jobs.sql_access import get_jobs_schema, run_jobs_sql


@pytest.fixture
def jobs_database(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    database_path = tmp_path / "jobs.sqlite3"
    engine = create_engine(f"sqlite:///{database_path}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            Job(
                url="https://example.com/job/1",
                company="Example AI",
                title="Applied AI Engineer",
                status=JobStatus.SAVED,
            )
        )
        session.commit()
    monkeypatch.setattr(
        "recruiter_agent.jobs.sql_access._database_path",
        lambda: database_path,
    )
    yield database_path
    engine.dispose()


def test_schema_describes_only_jobs_table() -> None:
    schema = get_jobs_schema()

    assert schema["table"] == "jobs"
    assert schema["access"] == "read_only"
    assert {column["name"] for column in schema["columns"]} >= {"id", "url", "status"}


def test_run_sql_reads_jobs_rows(jobs_database: Path) -> None:
    result = run_jobs_sql("SELECT company, title, status FROM jobs")

    assert result["row_count"] == 1
    assert result["rows"][0] == {
        "company": "Example AI",
        "title": "Applied AI Engineer",
        "status": "saved",
    }


@pytest.mark.parametrize(
    "query",
    [
        "UPDATE jobs SET status='applied'",
        "DELETE FROM jobs",
        "SELECT * FROM sqlite_master",
        "SELECT * FROM main.sqlite_master",
        "SELECT load_extension('evil') FROM jobs",
        "SELECT * FROM jobs; DELETE FROM jobs",
        "DROP TABLE jobs",
    ],
)
def test_run_sql_rejects_writes_or_other_tables(query: str) -> None:
    with pytest.raises(ValueError):
        run_jobs_sql(query)


def test_run_sql_applies_default_row_limit(jobs_database: Path) -> None:
    result = run_jobs_sql("SELECT * FROM jobs")

    assert result["row_count"] <= 100
