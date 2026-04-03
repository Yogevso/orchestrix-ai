from app.schemas.models import SystemEvent, Job, Alert, Metric
from app.services.correlator import detect_correlations


def _make_event(**kw):
    defaults = {"id": "evt-1", "timestamp": "2026-04-03T10:00:00Z", "source": "svc-1", "type": "info", "message": "ok", "severity": "info"}
    defaults.update(kw)
    return SystemEvent(**defaults)


def _make_job(**kw):
    defaults = {"id": "job-1", "name": "job-1", "status": "running", "started_at": "2026-04-03T10:00:00Z"}
    defaults.update(kw)
    return Job(**defaults)


def _make_alert(**kw):
    defaults = {"id": "a1", "timestamp": "2026-04-03T10:00:00Z", "source": "prometheus", "severity": "warning", "message": "alert", "metric": None}
    defaults.update(kw)
    return Alert(**defaults)


def _make_metric(**kw):
    defaults = {"name": "cpu_usage", "value": 50.0, "unit": "%", "timestamp": "2026-04-03T10:00:00Z", "source": "host-1"}
    defaults.update(kw)
    return Metric(**defaults)


def test_deployment_error_correlation():
    events = [
        _make_event(type="deployment", source="deploy-svc"),
        _make_event(severity="critical", source="app-pod", type="error"),
    ]
    result = detect_correlations(events, [], [], [])
    assert len(result) == 1
    assert "Deployment" in result[0].pattern
    assert result[0].severity == "critical"


def test_cpu_job_failure_correlation():
    jobs = [_make_job(status="failed", name="etl-job")]
    metrics = [_make_metric(name="cpu_usage", value=95.0, source="worker-1")]
    result = detect_correlations([], jobs, [], metrics)
    assert len(result) == 1
    assert "CPU" in result[0].pattern
    assert result[0].severity == "warning"


def test_memory_oom_correlation():
    events = [_make_event(message="OOMKilled container app", source="k8s")]
    alerts = [_make_alert(metric="container_memory_usage", source="prometheus")]
    result = detect_correlations(events, [], alerts, [])
    assert len(result) == 1
    assert "OOM" in result[0].pattern or "Memory" in result[0].pattern


def test_cascading_failure_correlation():
    events = [
        _make_event(type="restart", source="pod-a"),
        _make_event(type="restart", source="pod-b"),
    ]
    result = detect_correlations(events, [], [], [])
    assert len(result) == 1
    assert "Cascading" in result[0].pattern


def test_no_correlations():
    events = [_make_event()]
    result = detect_correlations(events, [], [], [])
    assert len(result) == 0
