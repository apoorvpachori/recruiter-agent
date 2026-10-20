"""Register API routes."""

from fastapi import APIRouter

from recruiter_agent.api.agent_input import router as agent_input_router
from recruiter_agent.api.health import router as health_router
from recruiter_agent.api.jobs import router as jobs_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(agent_input_router)
api_router.include_router(jobs_router)
