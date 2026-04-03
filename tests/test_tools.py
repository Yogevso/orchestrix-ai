import pytest
from app.services.tools import (
    get_recent_events,
    get_failed_jobs,
    get_high_cpu_processes,
    get_alerts,
)


@pytest.mark.anyio
async def test_get_recent_events():
    events = await get_recent_events()
    assert len(events) > 0
    assert all(e.id for e in events)


@pytest.mark.anyio
async def test_get_failed_jobs():
    jobs = await get_failed_jobs()
    assert len(jobs) > 0
    assert all(j.status == "failed" for j in jobs)


@pytest.mark.anyio
async def test_get_high_cpu_processes():
    metrics = await get_high_cpu_processes()
    assert len(metrics) > 0
    assert all(m.value > 80 for m in metrics)


@pytest.mark.anyio
async def test_get_alerts():
    alerts = await get_alerts()
    assert len(alerts) > 0
    assert all(a.severity in ("critical", "warning", "info") for a in alerts)
