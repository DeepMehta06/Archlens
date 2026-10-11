"""Shared rate limiter. Imported by main.py for the app-wide default and by
individual routes that need a stricter limit because they call the LLM.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings

settings = get_settings()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    enabled=settings.RATE_LIMIT_ENABLED,
)

llm_limit = settings.RATE_LIMIT_LLM
