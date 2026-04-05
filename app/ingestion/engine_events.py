"""Engine event ingestion — converts raw Engine events into analysis-ready signals.

Processes job lifecycle events from Orchestrix Engine and identifies
failure patterns, dead-letter sequences, and incident candidates.
"""

import logging
from datetime import datetime, timedelta, timezone
from collections import defaultdict

from app.connectors.engine_client import (
    fetch_events,
    fetch_failed_jobs,
    fetch_job_events,
    fetch_workers,
    fetch_queue_stats,
)
from app.schemas import SystemEvent, Job, Alert

logger = logging.getLogger(__name__)

# Event types that indicate problems
FAILURE_EVENTS = {"FAILED", "DEAD_LETTERED", "RETRIED", "CANCELLED"}
LIFECYCLE_EVENTS = {"CREATED", "QUEUED", "LEASED", "RUNNING", "HEARTBEAT", "SUCCEEDED"}


async def ingest_engine_events(
    since_minutes: int = 10,
) -> tuple[list[SystemEvent], list[Job], list[Alert]]:
    """Fetch and convert Engine data into analysis-ready signals.

    Returns:
        Tuple of (events as SystemEvent, failed jobs as Job, alerts as Alert)
    """
    since = datetime.now(timezone.utc) - timedelta(minutes=since_minutes)

    raw_events = await fetch_events(since=since, limit=500)
    raw_failed = await fetch_failed_jobs(limit=100)
    raw_workers = await fetch_workers()
    raw_stats = await fetch_queue_stats()

    events = _convert_events(raw_events)
    jobs = _convert_jobs(raw_failed)
    alerts = _generate_alerts(raw_events, raw_workers, raw_stats)

    logger.info(
        "Ingested from Engine: %d events, %d failed jobs, %d alerts",
        len(events), len(jobs), len(alerts),
    )
    return events, jobs, alerts


def _convert_events(raw_events: list[dict]) -> list[SystemEvent]:
    """Convert Engine job events to SystemEvent format for the analyzer."""
    events = []
    for evt in raw_events:
        event_type = evt.get("event_type", "UNKNOWN")
        severity = "critical" if event_type in {"FAILED", "DEAD_LETTERED"} else \
                   "warning" if event_type in {"RETRIED", "CANCELLED"} else "info"

        events.append(SystemEvent(
            id=evt.get("id", ""),
            timestamp=evt.get("created_at", ""),
            type=f"job.{event_type.lower()}",
            source=f"engine/job/{evt.get('job_id', 'unknown')}",
            message=evt.get("message") or f"Job event: {event_type}",
            severity=severity,
            metadata=evt.get("metadata_"),
        ))
    return events


def _convert_jobs(raw_jobs: list[dict]) -> list[Job]:
    """Convert Engine jobs to Job format for the analyzer."""
    jobs = []
    for j in raw_jobs:
        jobs.append(Job(
            id=j.get("id", ""),
            name=j.get("type", "unknown"),
            status=j.get("status", "unknown").lower(),
            started_at=j.get("created_at", ""),
            finished_at=j.get("updated_at"),
            error=j.get("last_error"),
            metadata={
                "queue": j.get("queue_name"),
                "attempts": j.get("attempts"),
                "max_attempts": j.get("max_attempts"),
                "worker_id": j.get("worker_id"),
                "tenant_id": j.get("tenant_id"),
            },
        ))
    return jobs


def _generate_alerts(
    raw_events: list[dict],
    raw_workers: list[dict],
    raw_stats: list[dict],
) -> list[Alert]:
    """Analyze Engine data and generate synthetic alerts for incident detection."""
    alerts: list[Alert] = []
    now = datetime.now(timezone.utc).isoformat()

    # Detect repeated failures per job type
    failure_counts: dict[str, int] = defaultdict(int)
    for evt in raw_events:
        if evt.get("event_type") in FAILURE_EVENTS:
            job_id = evt.get("job_id", "unknown")
            failure_counts[job_id] += 1

    for job_id, count in failure_counts.items():
        if count >= 3:
            alerts.append(Alert(
                id=f"alert-engine-repeat-fail-{job_id[:8]}",
                timestamp=now,
                severity="critical",
                source=f"engine/job/{job_id}",
                message=f"Job {job_id[:8]}… has {count} failure events — possible repeated failure loop",
                metric="job_failure_count",
                value=float(count),
                threshold=3.0,
            ))

    # Detect offline workers
    for w in raw_workers:
        if w.get("status") == "OFFLINE":
            alerts.append(Alert(
                id=f"alert-engine-worker-offline-{w.get('id', '')[:8]}",
                timestamp=now,
                severity="warning",
                source=f"engine/worker/{w.get('id', 'unknown')}",
                message=f"Worker '{w.get('name', 'unknown')}' is OFFLINE",
                metric="worker_status",
            ))

    # Detect queue backlog
    for q in raw_stats:
        queued = q.get("queued", 0)
        dead_letter = q.get("dead_letter", 0)
        if queued > 50:
            alerts.append(Alert(
                id=f"alert-engine-backlog-{q.get('queue_name', 'default')}",
                timestamp=now,
                severity="warning",
                source=f"engine/queue/{q.get('queue_name', 'default')}",
                message=f"Queue '{q.get('queue_name', 'default')}' has {queued} queued jobs — possible backlog",
                metric="queue_backlog",
                value=float(queued),
                threshold=50.0,
            ))
        if dead_letter > 10:
            alerts.append(Alert(
                id=f"alert-engine-deadletter-{q.get('queue_name', 'default')}",
                timestamp=now,
                severity="critical",
                source=f"engine/queue/{q.get('queue_name', 'default')}",
                message=f"Queue '{q.get('queue_name', 'default')}' has {dead_letter} dead-lettered jobs",
                metric="dead_letter_count",
                value=float(dead_letter),
                threshold=10.0,
            ))

    return alerts
