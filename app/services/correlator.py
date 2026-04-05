"""Correlation engine — detects cross-source signal patterns BEFORE sending to LLM.

This is deterministic pattern matching, not AI. It finds correlations like:
  - deployment followed by errors
  - CPU spike correlated with failed jobs
  - memory alerts matching OOM events

The correlations are passed to the LLM as pre-computed context so it can
focus on reasoning rather than discovery.
"""

import logging
from app.schemas import SystemEvent, Job, Alert, Metric, Correlation

logger = logging.getLogger(__name__)


def detect_correlations(
    events: list[SystemEvent],
    jobs: list[Job],
    alerts: list[Alert],
    metrics: list[Metric],
) -> list[Correlation]:
    """Run all correlation rules and return detected patterns."""
    correlations: list[Correlation] = []

    correlations.extend(_deployment_error_correlation(events))
    correlations.extend(_cpu_job_failure_correlation(jobs, metrics))
    correlations.extend(_memory_oom_correlation(events, alerts))
    correlations.extend(_cascading_failure_correlation(events, jobs))
    correlations.extend(_engine_worker_resource_correlation(events, alerts, metrics))
    correlations.extend(_engine_queue_backlog_correlation(events, alerts))
    correlations.extend(_engine_telemetry_resource_exhaustion(jobs, metrics, alerts))

    logger.info("Detected %d correlations", len(correlations))
    return correlations


# ── Correlation rules ──


def _deployment_error_correlation(events: list[SystemEvent]) -> list[Correlation]:
    """Detect deployment followed by errors/restarts."""
    results = []
    deployments = [e for e in events if e.type == "deployment"]
    errors = [e for e in events if e.severity in ("critical", "error") or e.type == "error"]

    if deployments and errors:
        results.append(Correlation(
            sources=[d.source for d in deployments] + [e.source for e in errors],
            pattern="Deployment event followed by errors — possible bad rollout",
            severity="critical",
        ))
    return results


def _cpu_job_failure_correlation(jobs: list[Job], metrics: list[Metric]) -> list[Correlation]:
    """Detect high CPU correlated with job failures."""
    results = []
    failed = [j for j in jobs if j.status == "failed"]
    high_cpu = [m for m in metrics if m.name == "cpu_usage" and m.value > 80]

    if failed and high_cpu:
        sources = list({m.source for m in high_cpu} | {j.name for j in failed})
        results.append(Correlation(
            sources=sources,
            pattern=f"{len(failed)} failed job(s) with CPU > 80% on {len(high_cpu)} source(s)",
            severity="warning",
        ))
    return results


def _memory_oom_correlation(events: list[SystemEvent], alerts: list[Alert]) -> list[Correlation]:
    """Detect memory alerts correlated with OOM events."""
    results = []
    oom_events = [e for e in events if "oom" in e.message.lower() or "memory" in e.message.lower()]
    mem_alerts = [a for a in alerts if a.metric and "memory" in a.metric.lower()]

    if oom_events and mem_alerts:
        sources = [e.source for e in oom_events] + [a.source for a in mem_alerts]
        results.append(Correlation(
            sources=sources,
            pattern="Memory threshold breach correlated with OOM kill events",
            severity="critical",
        ))
    return results


def _cascading_failure_correlation(events: list[SystemEvent], jobs: list[Job]) -> list[Correlation]:
    """Detect restart loops or multiple failures suggesting cascading issues."""
    results = []
    restarts = [e for e in events if e.type == "restart"]
    critical_events = [e for e in events if e.severity == "critical"]
    failed_jobs = [j for j in jobs if j.status == "failed"]

    # Multiple restarts + multiple failures = cascading
    if len(restarts) >= 2 or (len(critical_events) >= 2 and len(failed_jobs) >= 2):
        results.append(Correlation(
            sources=list({e.source for e in restarts + critical_events}),
            pattern=f"Cascading failure pattern: {len(restarts)} restart(s), "
                    f"{len(critical_events)} critical event(s), {len(failed_jobs)} failed job(s)",
            severity="critical",
        ))
    return results


# ── Cross-platform correlation rules (Engine × system-insights) ──


def _engine_worker_resource_correlation(
    events: list[SystemEvent],
    alerts: list[Alert],
    metrics: list[Metric],
) -> list[Correlation]:
    """Detect worker offline/heartbeat miss correlated with resource pressure."""
    results = []
    worker_events = [e for e in events if "worker" in e.source.lower() and
                     e.type in ("job.failed", "job.dead_lettered")]
    worker_alerts = [a for a in alerts if "worker" in a.source.lower() and "offline" in a.message.lower()]
    resource_alerts = [a for a in alerts if a.source.startswith("insights/")]
    high_cpu = [m for m in metrics if m.source.startswith("insights/") and m.name == "cpu_usage" and m.value > 80]
    high_mem = [m for m in metrics if m.source.startswith("insights/") and m.name == "memory_usage"]

    if (worker_events or worker_alerts) and (resource_alerts or high_cpu or high_mem):
        sources = (
            [e.source for e in worker_events[:3]] +
            [a.source for a in worker_alerts[:3]] +
            [a.source for a in resource_alerts[:3]] +
            [m.source for m in high_cpu[:3]]
        )
        results.append(Correlation(
            sources=list(set(sources)),
            pattern="Engine worker issues correlated with host resource pressure — "
                    "workers may be failing due to CPU/memory exhaustion on the host",
            severity="critical",
        ))
    return results


def _engine_queue_backlog_correlation(
    events: list[SystemEvent],
    alerts: list[Alert],
) -> list[Correlation]:
    """Detect queue backlog combined with repeated job failures."""
    results = []
    backlog_alerts = [a for a in alerts if a.metric == "queue_backlog"]
    dead_letter_alerts = [a for a in alerts if a.metric == "dead_letter_count"]
    failure_events = [e for e in events if e.type in ("job.failed", "job.dead_lettered")]

    if backlog_alerts and (dead_letter_alerts or len(failure_events) >= 3):
        queue_names = [a.source.split("/")[-1] for a in backlog_alerts]
        results.append(Correlation(
            sources=list(set(
                [a.source for a in backlog_alerts] +
                [a.source for a in dead_letter_alerts] +
                [e.source for e in failure_events[:5]]
            )),
            pattern=f"Queue backlog on {', '.join(queue_names)} with repeated failures — "
                    "jobs are piling up and failing, possible systemic issue",
            severity="critical",
        ))
    return results


def _engine_telemetry_resource_exhaustion(
    jobs: list[Job],
    metrics: list[Metric],
    alerts: list[Alert],
) -> list[Correlation]:
    """Detect Engine job failures coinciding with system-insights resource metrics."""
    results = []
    failed_jobs = [j for j in jobs if j.status in ("failed", "dead_letter")]
    system_peak_cpu = [m for m in metrics if m.name == "system_peak_cpu" and m.value > 85]
    active_alert_metrics = [m for m in metrics if m.name == "active_alerts" and m.value > 5]

    if failed_jobs and (system_peak_cpu or active_alert_metrics):
        sources = (
            [f"engine/job/{j.id[:8]}" for j in failed_jobs[:3]] +
            [m.source for m in system_peak_cpu] +
            [m.source for m in active_alert_metrics]
        )
        cpu_val = system_peak_cpu[0].value if system_peak_cpu else 0
        results.append(Correlation(
            sources=list(set(sources)),
            pattern=f"{len(failed_jobs)} Engine job failure(s) while system CPU peaked at "
                    f"{cpu_val:.0f}% — resource contention likely contributing to failures",
            severity="critical",
        ))
    return results
