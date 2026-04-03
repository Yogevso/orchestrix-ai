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
