from app.schemas import (
    AnalyzeIncidentResponse,
    IncidentType,
    TimelineEntry,
    QualityScore,
    Correlation,
    BatchAnalyzeResponse,
)


def test_incident_response_with_full_schema():
    """Verify the full response model with quality scoring, correlations, prompt versioning."""
    resp = AnalyzeIncidentResponse(
        incident_id="test-1",
        incident_type=IncidentType.RESOURCE_EXHAUSTION,
        summary="Memory exceeded on worker",
        root_cause="OOM after deployment",
        reasoning_steps=[
            "Detected deployment event",
            "Found OOMKilled error",
            "Correlated with memory alert",
        ],
        correlations=[
            Correlation(
                sources=["worker-pod", "prometheus"],
                pattern="Memory alert correlated with OOM event",
                severity="critical",
            ),
        ],
        timeline=[
            TimelineEntry(timestamp="2026-04-03T10:00:00Z", event="Deploy", severity="info"),
            TimelineEntry(timestamp="2026-04-03T10:03:00Z", event="OOM", severity="critical"),
        ],
        recommended_action="Increase memory limit",
        quality=QualityScore(confidence=0.85, signal_strength=0.9, data_coverage=1.0),
        source="ai",
        prompt_version="v1.2",
    )

    assert resp.incident_type == IncidentType.RESOURCE_EXHAUSTION
    assert len(resp.reasoning_steps) == 3
    assert len(resp.correlations) == 1
    assert resp.quality.confidence == 0.85
    assert resp.quality.signal_strength == 0.9
    assert resp.quality.data_coverage == 1.0
    assert resp.source == "ai"
    assert resp.prompt_version == "v1.2"


def test_rule_based_response():
    """Verify source field can be rule-based."""
    resp = AnalyzeIncidentResponse(
        incident_id="test-2",
        incident_type=IncidentType.UNKNOWN,
        summary="No critical issues",
        root_cause="Unknown",
        reasoning_steps=[],
        correlations=[],
        timeline=[],
        recommended_action="Monitor",
        quality=QualityScore(confidence=0.4, signal_strength=0.2, data_coverage=0.5),
        source="rule-based",
        prompt_version="v1.2",
    )
    assert resp.source == "rule-based"


def test_incident_type_enum_values():
    """All expected incident types should be valid."""
    assert IncidentType("resource_exhaustion") == IncidentType.RESOURCE_EXHAUSTION
    assert IncidentType("network_anomaly") == IncidentType.NETWORK_ANOMALY
    assert IncidentType("job_failure") == IncidentType.JOB_FAILURE
    assert IncidentType("deployment_issue") == IncidentType.DEPLOYMENT_ISSUE
    assert IncidentType("cascading_failure") == IncidentType.CASCADING_FAILURE
    assert IncidentType("unknown") == IncidentType.UNKNOWN
