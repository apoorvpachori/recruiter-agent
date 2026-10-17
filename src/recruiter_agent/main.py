"""Compose the application and expose the ASGI entry point."""

from fastapi import FastAPI

from recruiter_agent.api.router import api_router

app = FastAPI(
    title="Recruiter Agent",
    description="A personal AI job-search copilot.",
    version="0.1.0",
)
app.include_router(api_router)
