import logging
from fastapi import FastAPI, Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from app.config import get_settings
from app.api import analyze, search, anomalies, prioritize, live, replay, batch

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject request bodies larger than the configured limit."""

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        max_bytes = settings.max_request_body_kb * 1024
        if content_length and int(content_length) > max_bytes:
            raise HTTPException(status_code=413, detail="Request body too large")
        return await call_next(request)


app = FastAPI(
    title="Orchestrix AI",
    description="AI reasoning layer for analyzing incidents, detecting anomalies, and generating insights from distributed system telemetry.",
    version="0.4.0",
)

app.add_middleware(RequestSizeLimitMiddleware)

app.include_router(analyze.router)
app.include_router(search.router)
app.include_router(anomalies.router)
app.include_router(prioritize.router)
app.include_router(live.router)
app.include_router(replay.router)
app.include_router(batch.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
