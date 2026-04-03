"""FastAPI dependencies — service lifecycle and authentication."""

import logging
from functools import lru_cache

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import get_settings
from app.services.analyzer import AnalyzerService

logger = logging.getLogger(__name__)

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


@lru_cache
def get_analyzer() -> AnalyzerService:
    """Singleton AnalyzerService — reuses LLM client and RAG retriever across requests."""
    return AnalyzerService()


async def verify_api_key(key: str | None = Security(_api_key_header)) -> None:
    """Validate API key if one is configured. Skip auth when API_KEY is unset."""
    settings = get_settings()
    if not settings.api_key:
        return  # No auth configured — allow all requests
    if key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
