from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from datetime import datetime


# ── Incident Analysis ──


class IncidentType(str, Enum):
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    NETWORK_ANOMALY = "network_anomaly"
    JOB_FAILURE = "job_failure"
    DEPLOYMENT_ISSUE = "deployment_issue"
    CASCADING_FAILURE = "cascading_failure"
    UNKNOWN = "unknown"


class AnalyzeIncidentRequest(BaseModel):
    incident_id: str
    time_range: str = "last_10_minutes"


class TimelineEntry(BaseModel):
    timestamp: str
    event: str
    severity: str = "info"


class QualityScore(BaseModel):
    """Measures how trustworthy the AI analysis is."""
    confidence: float = Field(ge=0.0, le=1.0, description="LLM self-assessed confidence")
    signal_strength: float = Field(ge=0.0, le=1.0, description="Strength of correlated signals")
    data_coverage: float = Field(ge=0.0, le=1.0, description="Fraction of data sources that returned data")


class Correlation(BaseModel):
    """A detected cross-source signal correlation."""
    sources: list[str]
    pattern: str
    severity: str


class AnalyzeIncidentResponse(BaseModel):
    incident_id: str
    incident_type: IncidentType
    summary: str
    root_cause: str
    reasoning_steps: list[str]
    correlations: list[Correlation]
    timeline: list[TimelineEntry]
    recommended_action: str
    quality: QualityScore
    source: str = "ai"  # "ai" or "rule-based"
    prompt_version: str = "v1"


# ── Replay (Debug mode) ──


class ReplayIncidentRequest(BaseModel):
    """Submit custom telemetry data for reproducible incident analysis."""
    events: list[dict] = []
    jobs: list[dict] = []
    alerts: list[dict] = []
    metrics: list[dict] = []


# ── Batch Analysis ──


class BatchAnalyzeRequest(BaseModel):
    incident_ids: list[str]
    time_range: str = "last_10_minutes"


class BatchAnalyzeResponse(BaseModel):
    results: list[AnalyzeIncidentResponse]
    total: int
    succeeded: int
    failed: int


# ── Anomaly Detection ──


class AnomalyType(str, Enum):
    THRESHOLD = "threshold"
    ZSCORE = "zscore"


class DetectAnomaliesRequest(BaseModel):
    time_range: str = "last_10_minutes"
    anomaly_type: AnomalyType = AnomalyType.THRESHOLD


class Anomaly(BaseModel):
    metric: str
    value: float
    threshold: float
    severity: str
    description: str


class DetectAnomaliesResponse(BaseModel):
    anomalies: list[Anomaly]
    summary: str


# ── Semantic Search (RAG) ──


class SearchRequest(BaseModel):
    query: str


class SearchResult(BaseModel):
    content: str
    source: str
    relevance: float = Field(ge=0.0, le=1.0)


class SearchResponse(BaseModel):
    query: str
    answer: str
    sources: list[SearchResult]


# ── Prioritization ──


class PrioritizeRequest(BaseModel):
    time_range: str = "last_10_minutes"


class RankedItem(BaseModel):
    id: str
    type: str  # "event", "job", "alert"
    title: str
    priority: int = Field(ge=1, le=5)
    reason: str


class PrioritizeResponse(BaseModel):
    ranked_items: list[RankedItem]
    reasoning: str


# ── Internal data models ──


class SystemEvent(BaseModel):
    id: str
    timestamp: str
    type: str
    source: str
    message: str
    severity: str = "info"
    metadata: dict | None = None


class Job(BaseModel):
    id: str
    name: str
    status: str
    started_at: str
    finished_at: str | None = None
    error: str | None = None
    metadata: dict | None = None


class Alert(BaseModel):
    id: str
    timestamp: str
    severity: str
    source: str
    message: str
    metric: str | None = None
    value: float | None = None
    threshold: float | None = None


class Metric(BaseModel):
    name: str
    value: float
    unit: str
    timestamp: str
    source: str
