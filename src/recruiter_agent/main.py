"""FastAPI application entry point."""

from fastapi import FastAPI

app = FastAPI(
    title="Recruiter Agent",
    description="A personal AI job-search copilot.",
    version="0.1.0",
)


@app.get("/healthz", tags=["health"])
def health_check() -> dict[str, str]:
    """Report whether the API process is responding."""
    return {"status": "ok"}
