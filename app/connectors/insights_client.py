"""System Insights API connector — queries telemetry data for cross-source correlation.

Fetches host metrics, service metrics, alerts, and timeline events
from the system-insights-api to enrich AI incident analysis.
"""

import logging
from datetime import datetime

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(5.0, connect=3.0)

# Default to localhost:8002 — override via INSIGHTS_API_URL env var.
_DEFAULT_INSIGHTS_URL = "http://localhost:8002"


def _base_url() -> str:
    url = getattr(get_settings(), "insights_api_url", _DEFAULT_INSIGHTS_URL)
    return url.rstrip("/")


async def _get_json(path: str, params: dict | None = None) -> dict | list | None:
    url = f"{_base_url()}{path}"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        logger.warning("Insights API unreachable (%s): %s", path, exc)
        return None
    except httpx.HTTPStatusError as exc:
        logger.warning("Insights API error (%s): %s", path, exc.response.status_code)
        return None


async def fetch_host_metrics(
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> list[dict]:
    """Fetch per-host aggregated metrics."""
    params: dict = {}
    if start_time:
        params["start_time"] = start_time.isoformat()
    if end_time:
        params["end_time"] = end_time.isoformat()
    data = await _get_json("/metrics/hosts", params=params)
    if data is None:
        return []
    return data.get("hosts", []) if isinstance(data, dict) else data


async def fetch_service_metrics(
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> list[dict]:
    """Fetch per-service aggregated metrics."""
    params: dict = {}
    if start_time:
        params["start_time"] = start_time.isoformat()
    if end_time:
        params["end_time"] = end_time.isoformat()
    data = await _get_json("/metrics/services", params=params)
    if data is None:
        return []
    return data.get("services", []) if isinstance(data, dict) else data


async def fetch_alerts(
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int = 100,
) -> list[dict]:
    """Fetch recent alerts from system-insights-api."""
    params: dict = {"limit": limit, "order": "desc"}
    if start_time:
        params["start_time"] = start_time.isoformat()
    if end_time:
        params["end_time"] = end_time.isoformat()
    data = await _get_json("/alerts", params=params)
    if data is None:
        return []
    return data.get("data", []) if isinstance(data, dict) else data


async def fetch_timeline(
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int = 200,
) -> list[dict]:
    """Fetch unified timeline events."""
    params: dict = {"limit": limit}
    if start_time:
        params["start_time"] = start_time.isoformat()
    if end_time:
        params["end_time"] = end_time.isoformat()
    data = await _get_json("/timeline", params=params)
    if data is None:
        return []
    return data.get("data", []) if isinstance(data, dict) else data


async def fetch_stats(
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> dict | None:
    """Fetch aggregate stats."""
    params: dict = {}
    if start_time:
        params["start_time"] = start_time.isoformat()
    if end_time:
        params["end_time"] = end_time.isoformat()
    return await _get_json("/stats", params=params)
