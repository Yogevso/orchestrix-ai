"""MCP-lite tool layer — functions that retrieve system telemetry data.

Calls the live Orchestrix backend API. Falls back to mock data when the
backend is unreachable (for local development / demos).
"""

import logging
from datetime import datetime, timedelta, timezone

import httpx

from app.config import get_settings
from app.schemas import SystemEvent, Job, Alert, Metric

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(5.0, connect=3.0)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _base_url() -> str:
    return get_settings().orchestrix_api_url.rstrip("/")


# ── HTTP helpers ──


async def _get(path: str, params: dict | None = None) -> list[dict] | None:
    """GET from Orchestrix backend. Returns parsed JSON list or None on failure."""
    url = f"{_base_url()}{path}"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else data.get("items", data.get("results", []))
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        logger.warning("Orchestrix API unreachable (%s %s): %s — using mock data", "GET", path, exc)
        return None
    except httpx.HTTPStatusError as exc:
        logger.warning("Orchestrix API error (%s %s): %s — using mock data", "GET", path, exc.response.status_code)
        return None


# ── Public tool functions ──


async def get_recent_events(time_range: str = "last_10_minutes") -> list[SystemEvent]:
    """Return recent system events within the given time range."""
    logger.info("get_recent_events(%s)", time_range)

    data = await _get("/events", params={"time_range": time_range})
    if data is not None:
        return [SystemEvent(**item) for item in data]

    return _mock_events()


async def get_failed_jobs(time_range: str = "last_10_minutes") -> list[Job]:
    """Return jobs that failed within the given time range."""
    logger.info("get_failed_jobs(%s)", time_range)

    data = await _get("/jobs", params={"status": "failed", "time_range": time_range})
    if data is not None:
        return [Job(**item) for item in data]

    return _mock_failed_jobs()


async def get_high_cpu_processes(time_range: str = "last_10_minutes") -> list[Metric]:
    """Return CPU metrics for processes exceeding normal thresholds."""
    logger.info("get_high_cpu_processes(%s)", time_range)

    data = await _get("/metrics", params={"name": "cpu_usage", "min_value": "80", "time_range": time_range})
    if data is not None:
        return [Metric(**item) for item in data]

    return _mock_high_cpu()


async def get_alerts(time_range: str = "last_10_minutes") -> list[Alert]:
    """Return active alerts within the given time range."""
    logger.info("get_alerts(%s)", time_range)

    data = await _get("/alerts", params={"time_range": time_range})
    if data is not None:
        return [Alert(**item) for item in data]

    return _mock_alerts()


# Registry of available tools — used by the analyzer for context building.
TOOL_REGISTRY: dict[str, callable] = {
    "get_recent_events": get_recent_events,
    "get_failed_jobs": get_failed_jobs,
    "get_high_cpu_processes": get_high_cpu_processes,
    "get_alerts": get_alerts,
}


# ── Mock data fallbacks ──


def _mock_events() -> list[SystemEvent]:
    base = _now()
    return [
        SystemEvent(
            id="evt-001",
            timestamp=(base - timedelta(minutes=8)).isoformat(),
            type="deployment",
            source="k8s/prod-cluster",
            message="Deployment orchestrix-worker rolled out (v2.4.1)",
            severity="info",
        ),
        SystemEvent(
            id="evt-002",
            timestamp=(base - timedelta(minutes=5)).isoformat(),
            type="error",
            source="orchestrix-worker-7f8b4",
            message="OOMKilled: container exceeded 512Mi memory limit",
            severity="critical",
        ),
        SystemEvent(
            id="evt-003",
            timestamp=(base - timedelta(minutes=3)).isoformat(),
            type="restart",
            source="orchestrix-worker-7f8b4",
            message="Container restarted (attempt 3/5)",
            severity="warning",
        ),
        SystemEvent(
            id="evt-004",
            timestamp=(base - timedelta(minutes=1)).isoformat(),
            type="alert",
            source="prometheus",
            message="High error rate detected: 23% of requests returning 500",
            severity="critical",
        ),
    ]


def _mock_failed_jobs() -> list[Job]:
    base = _now()
    return [
        Job(
            id="job-042",
            name="data-pipeline-sync",
            status="failed",
            started_at=(base - timedelta(minutes=9)).isoformat(),
            finished_at=(base - timedelta(minutes=7)).isoformat(),
            error="TimeoutError: upstream API did not respond within 30s",
        ),
        Job(
            id="job-043",
            name="report-generator",
            status="failed",
            started_at=(base - timedelta(minutes=6)).isoformat(),
            finished_at=(base - timedelta(minutes=4)).isoformat(),
            error="MemoryError: unable to allocate 1.2GB for dataset",
        ),
    ]


def _mock_high_cpu() -> list[Metric]:
    base = _now()
    return [
        Metric(
            name="cpu_usage",
            value=94.5,
            unit="percent",
            timestamp=(base - timedelta(minutes=4)).isoformat(),
            source="orchestrix-worker-7f8b4",
        ),
        Metric(
            name="cpu_usage",
            value=87.2,
            unit="percent",
            timestamp=(base - timedelta(minutes=2)).isoformat(),
            source="data-pipeline-sync",
        ),
    ]


def _mock_alerts() -> list[Alert]:
    base = _now()
    return [
        Alert(
            id="alert-101",
            timestamp=(base - timedelta(minutes=6)).isoformat(),
            severity="critical",
            source="prometheus",
            message="Memory usage exceeded 90% on orchestrix-worker-7f8b4",
            metric="memory_usage_percent",
            value=93.0,
            threshold=90.0,
        ),
        Alert(
            id="alert-102",
            timestamp=(base - timedelta(minutes=2)).isoformat(),
            severity="warning",
            source="prometheus",
            message="CPU usage exceeded 80% on data-pipeline-sync",
            metric="cpu_usage_percent",
            value=87.2,
            threshold=80.0,
        ),
    ]
