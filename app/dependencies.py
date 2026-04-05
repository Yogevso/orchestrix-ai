"""FastAPI dependencies — service lifecycle and authentication."""

import logging
from functools import lru_cache

import jwt as pyjwt
from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.services.analyzer import AnalyzerService

logger = logging.getLogger(__name__)

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_bearer = HTTPBearer(auto_error=False)


@lru_cache
def get_analyzer() -> AnalyzerService:
    """Singleton AnalyzerService — reuses LLM client and RAG retriever across requests."""
    return AnalyzerService()


async def verify_api_key(
    api_key: str | None = Security(_api_key_header),
    bearer: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> None:
    """Validate API key or IAM JWT token. Skip auth when neither is configured."""
    settings = get_settings()

    # Try IAM JWT first
    if bearer and settings.iam_jwt_secret_key:
        try:
            payload = pyjwt.decode(
                bearer.credentials,
                settings.iam_jwt_secret_key,
                algorithms=["HS256"],
                issuer=settings.iam_jwt_issuer,
                options={"require": ["sub", "tenant_id", "role", "type", "exp", "iss"]},
            )
            if payload.get("type") == "access":
                return  # Valid IAM token
        except pyjwt.InvalidTokenError:
            pass  # Not a valid IAM token — try API key

    # Fall back to API key
    if not settings.api_key:
        return  # No auth configured — allow all requests
    if api_key == settings.api_key:
        return
    if bearer:
        raise HTTPException(status_code=401, detail="Invalid token or API key")
    raise HTTPException(status_code=401, detail="Invalid or missing API key")
