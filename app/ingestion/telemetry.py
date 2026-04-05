"""System Insights telemetry ingestion — enriches analysis with host/service metrics.

Fetches telemetry from system-insights-api and converts it into
Metric and Alert models for the correlation engine.
"""

import logging
from datetime import datetime, timedelta, timezone

from app.connectors.insights_client import (
    fetch_host_metrics,
    fetch_alerts,
    fetch_stats,
)
from app.schemas import Metric, Alert

logger = logging.getLogger(__name__)


async def ingest_telemetry(
    since_minutes: int = 10,
) -> tuple[list[Metric], list[Alert]]:
    """Fetch system-insights data and convert to analysis-ready signals.

    Returns:
        Tuple of (metrics as Metric, alerts as Alert)
    """
    now = datetime.now(timezone.utc)
    start = now - timedelta(minutes=since_minutes)

    raw_hosts = await fetch_host_metrics(start_time=start)
    raw_alerts = await fetch_alerts(start_time=start)
    raw_stats = await fetch_stats(start_time=start)

    metrics = _convert_host_metrics(raw_hosts, now)
    alerts = _convert_alerts(raw_alerts)

    # Generate synthetic metrics from stats if available
    if raw_stats:
        metrics.extend(_extract_stats_metrics(raw_stats, now))

    logger.info(
        "Ingested from system-insights: %d metrics, %d alerts",
        len(metrics), len(alerts),
    )
    return metrics, alerts


def _convert_host_metrics(raw_hosts: list[dict], now: datetime) -> list[Metric]:
    """Convert host-level aggregates into Metric objects."""
    metrics = []
    ts = now.isoformat()
    for h in raw_hosts:
        source = h.get("source", "unknown")
        if h.get("peak_cpu", 0) > 0:
            metrics.append(Metric(
                name="cpu_usage",
                value=h["avg_cpu"],
                unit="percent",
                timestamp=ts,
                source=f"insights/{source}",
            ))
        if h.get("peak_mem_kb", 0) > 0:
            metrics.append(Metric(
                name="memory_usage",
                value=h["peak_mem_kb"],
                unit="kb",
                timestamp=ts,
                source=f"insights/{source}",
            ))
    return metrics


def _convert_alerts(raw_alerts: list[dict]) -> list[Alert]:
    """Convert system-insights alerts to the AI Alert format."""
    alerts = []
    for a in raw_alerts:
        alerts.append(Alert(
            id=f"insights-alert-{a.get('id', '')}",
            timestamp=a.get("timestamp", ""),
            severity=_map_severity(a.get("type", "")),
            source=f"insights/{a.get('source', 'unknown')}",
            message=a.get("message", ""),
        ))
    return alerts


def _extract_stats_metrics(raw_stats: dict, now: datetime) -> list[Metric]:
    """Extract high-level stats into synthetic metrics."""
    metrics = []
    ts = now.isoformat()
    proc = raw_stats.get("processes", {})
    if proc.get("peak_cpu"):
        metrics.append(Metric(
            name="system_peak_cpu",
            value=proc["peak_cpu"],
            unit="percent",
            timestamp=ts,
            source="insights/aggregate",
        ))
    if proc.get("peak_mem_kb"):
        metrics.append(Metric(
            name="system_peak_memory",
            value=proc["peak_mem_kb"],
            unit="kb",
            timestamp=ts,
            source="insights/aggregate",
        ))
    alert_stats = raw_stats.get("alerts", {})
    if alert_stats.get("total_count", 0) > 0:
        metrics.append(Metric(
            name="active_alerts",
            value=float(alert_stats["total_count"]),
            unit="count",
            timestamp=ts,
            source="insights/aggregate",
        ))
    return metrics


def _map_severity(alert_type: str) -> str:
    """Map system-insights alert types to severity levels."""
    critical_types = {"high_cpu", "oom", "memory_critical", "disk_full"}
    warning_types = {"high_memory", "connection_spike", "process_spike"}
    if alert_type.lower() in critical_types:
        return "critical"
    if alert_type.lower() in warning_types:
        return "warning"
    return "info"
