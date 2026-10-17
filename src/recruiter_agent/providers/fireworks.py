"""Fireworks chat-model construction."""

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_fireworks import ChatFireworks

from recruiter_agent.settings import Settings, get_settings


def create_fireworks_model(settings: Settings | None = None) -> BaseChatModel:
    """Create the configured Fireworks chat model."""
    settings = settings or get_settings()
    if not settings.fireworks_api_key or not settings.fireworks_api_key.get_secret_value():
        raise RuntimeError("Set FIREWORKS_API_KEY in .env before invoking the agent.")
    if not settings.fireworks_model:
        raise RuntimeError("Set FIREWORKS_MODEL in .env before invoking the agent.")

    return ChatFireworks(
        model=settings.fireworks_model,
        api_key=settings.fireworks_api_key,
    )
