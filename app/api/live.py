import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from app.services.tools import get_recent_events, get_failed_jobs, get_alerts, get_high_cpu_processes

router = APIRouter(prefix="/ai", tags=["live"])
logger = logging.getLogger(__name__)

POLL_INTERVAL = 5  # seconds


async def _generate_stream(request: Request):
    """Yield a system status snapshot every POLL_INTERVAL seconds. Exits on client disconnect."""
    while not await request.is_disconnected():
        try:
            events = await get_recent_events()
            jobs = await get_failed_jobs()
            alerts = await get_alerts()
            metrics = await get_high_cpu_processes()

            critical_events = [e for e in events if e.severity == "critical"]
            critical_alerts = [a for a in alerts if a.severity == "critical"]

            snapshot = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "critical" if (critical_events or critical_alerts) else "healthy",
                "counts": {
                    "events": len(events),
                    "failed_jobs": len(jobs),
                    "alerts": len(alerts),
                    "high_cpu": len(metrics),
                },
                "critical_items": [
                    {"type": "event", "id": e.id, "message": e.message}
                    for e in critical_events
                ] + [
                    {"type": "alert", "id": a.id, "message": a.message}
                    for a in critical_alerts
                ],
            }

            yield {"event": "status", "data": json.dumps(snapshot)}

        except Exception as exc:
            logger.error("Live stream error: %s", exc)
            yield {
                "event": "error",
                "data": json.dumps({"error": str(exc)}),
            }

        await asyncio.sleep(POLL_INTERVAL)


@router.get("/live")
async def live_stream(request: Request):
    """SSE endpoint — streams system status snapshots in real time."""
    return EventSourceResponse(_generate_stream(request))
