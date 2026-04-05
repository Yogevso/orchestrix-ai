"""Engine connector — queries Orchestrix Engine API for execution data.

Uses the Engine's REST endpoints to fetch job events, job details,
workflow run states, and worker health for downstream analysis.
"""

import logging
from datetime import datetime, timedelta, timezone

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(5.0, connect=3.0)


def _base_url() -> str:
    return get_settings().orchestrix_api_url.rstrip("/")


async def _get_json(path: str, params: dict | None = None) -> dict | list | None:
    """GET from Engine. Returns parsed JSON or None on failure."""
    url = f"{_base_url()}{path}"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        logger.warning("Engine unreachable (%s): %s", path, exc)
        return None
    except httpx.HTTPStatusError as exc:
        logger.warning("Engine error (%s): %s", path, exc.response.status_code)
        return None


async def fetch_events(
    since: datetime | None = None,
    event_type: str | None = None,
    limit: int = 200,
) -> list[dict]:
    """Fetch job events from Engine GET /events endpoint."""
    params: dict = {"limit": limit}
    if since:
        params["since"] = since.isoformat()
    if event_type:
        params["event_type"] = event_type

    data = await _get_json("/events", params=params)
    if data is None:
        return []
    # Engine returns { events: [...], total: int }
    return data.get("events", []) if isinstance(data, dict) else data


async def fetch_failed_jobs(limit: int = 50) -> list[dict]:
    """Fetch jobs with FAILED or DEAD_LETTER status."""
    params = {"status": "FAILED", "limit": limit}
    data = await _get_json("/jobs", params=params)
    if data is None:
        return []
    jobs = data.get("jobs", []) if isinstance(data, dict) else data

    # Also get dead-lettered jobs
    params_dl = {"status": "DEAD_LETTER", "limit": limit}
    data_dl = await _get_json("/jobs", params=params_dl)
    if data_dl:
        dl_jobs = data_dl.get("jobs", []) if isinstance(data_dl, dict) else data_dl
        jobs.extend(dl_jobs)

    return jobs


async def fetch_job_events(job_id: str) -> list[dict]:
    """Fetch the event timeline for a specific job."""
    data = await _get_json(f"/jobs/{job_id}/events")
    return data if isinstance(data, list) else []


async def fetch_workers() -> list[dict]:
    """Fetch current worker pool status."""
    data = await _get_json("/workers")
    return data if isinstance(data, list) else []


async def fetch_queue_stats() -> list[dict]:
    """Fetch per-queue statistics."""
    data = await _get_json("/jobs/stats")
    return data if isinstance(data, list) else []


async def fetch_workflow_runs(status: str | None = None, limit: int = 50) -> list[dict]:
    """Fetch workflow runs, optionally filtered by status."""
    params: dict = {"limit": limit}
    if status:
        params["status"] = status
    data = await _get_json("/workflows/runs", params=params)
    return data if isinstance(data, list) else []
