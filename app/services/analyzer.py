"""Analyzer service — orchestrates tools, correlator, RAG, and LLM for each capability.

Includes:
- Correlation engine (deterministic, pre-LLM)
- Quality scoring (signal_strength, data_coverage, confidence)
- Rule-based fallback when LLM is unavailable
- Prompt versioning
- TTL caching
- Replay mode (custom data)
- Batch analysis
"""

import json
import logging
from statistics import mean, stdev

from app.schemas import (
    AnalyzeIncidentResponse,
    IncidentType,
    TimelineEntry,
    QualityScore,
    Correlation,
    DetectAnomaliesResponse,
    Anomaly,
    SearchResponse,
    SearchResult,
    PrioritizeResponse,
    RankedItem,
    SystemEvent,
    Job,
    Alert,
    Metric,
)
from app.services.llm import LLMService
from app.services.rag import RAGRetriever
from app.services.correlator import detect_correlations
from app.services.cache import incident_cache
from app.services.tools import (
    get_recent_events,
    get_failed_jobs,
    get_high_cpu_processes,
    get_alerts,
)

logger = logging.getLogger(__name__)

PROMPT_VERSION = "v1.2"


class AnalyzerService:
    def __init__(self) -> None:
        self.llm = LLMService()
        self.rag = RAGRetriever()

    # ── 1. Incident Analysis ──

    async def analyze_incident(
        self, incident_id: str, time_range: str
    ) -> AnalyzeIncidentResponse:
        # Check cache
        cache_key = f"incident:{incident_id}:{time_range}"
        cached = incident_cache.get(cache_key)
        if cached is not None:
            return cached

        events = await get_recent_events(time_range)
        jobs = await get_failed_jobs(time_range)
        metrics = await get_high_cpu_processes(time_range)
        alerts = await get_alerts(time_range)

        result = await self._run_analysis(incident_id, events, jobs, metrics, alerts)

        # Cache result
        incident_cache.set(cache_key, result)
        return result

    async def replay_incident(
        self,
        events_raw: list[dict],
        jobs_raw: list[dict],
        alerts_raw: list[dict],
        metrics_raw: list[dict],
    ) -> AnalyzeIncidentResponse:
        """Replay mode: analyze custom data for reproducible debugging."""
        events = [SystemEvent(**e) for e in events_raw] if events_raw else []
        jobs = [Job(**j) for j in jobs_raw] if jobs_raw else []
        alerts = [Alert(**a) for a in alerts_raw] if alerts_raw else []
        metrics = [Metric(**m) for m in metrics_raw] if metrics_raw else []

        return await self._run_analysis("replay", events, jobs, metrics, alerts)

    async def analyze_batch(
        self, incident_ids: list[str], time_range: str
    ) -> list[AnalyzeIncidentResponse]:
        """Batch mode: analyze multiple incidents."""
        results = []
        for iid in incident_ids:
            try:
                result = await self.analyze_incident(iid, time_range)
                results.append(result)
            except Exception as exc:
                logger.error("Batch analysis failed for %s: %s", iid, exc)
        return results

    async def _run_analysis(
        self,
        incident_id: str,
        events: list[SystemEvent],
        jobs: list[Job],
        metrics: list[Metric],
        alerts: list[Alert],
    ) -> AnalyzeIncidentResponse:
        """Core analysis pipeline: correlate → build context → LLM (or fallback)."""
        # 1. Deterministic correlation
        correlations = detect_correlations(events, jobs, alerts, metrics)

        # 2. Quality: data coverage
        sources_with_data = sum([
            1 if events else 0,
            1 if jobs else 0,
            1 if metrics else 0,
            1 if alerts else 0,
        ])
        data_coverage = sources_with_data / 4.0

        # 3. Signal strength from correlations
        severity_weights = {"critical": 1.0, "warning": 0.6, "info": 0.3}
        if correlations:
            signal_strength = min(
                1.0,
                sum(severity_weights.get(c.severity, 0.3) for c in correlations)
                / len(correlations),
            )
        else:
            signal_strength = 0.2

        # 4. Build context
        context = self._build_context(events, jobs, metrics, alerts, correlations)

        # 5. Try LLM, fallback to rules
        try:
            result = await self.llm.analyze_incident(context)
            source = "ai"
        except Exception as exc:
            logger.warning("LLM unavailable (%s), using rule-based fallback", exc)
            result = self._rule_based_analysis(events, jobs, alerts, metrics, correlations)
            source = "rule-based"

        # 6. Parse response
        timeline = [
            TimelineEntry(**entry) for entry in result.get("timeline", [])
        ]

        raw_type = result.get("incident_type", "unknown")
        try:
            incident_type = IncidentType(raw_type)
        except ValueError:
            incident_type = IncidentType.UNKNOWN

        confidence = result.get("confidence", 0.5)

        return AnalyzeIncidentResponse(
            incident_id=incident_id,
            incident_type=incident_type,
            summary=result.get("summary", ""),
            root_cause=result.get("root_cause", ""),
            reasoning_steps=result.get("reasoning_steps", []),
            correlations=correlations,
            timeline=timeline,
            recommended_action=result.get("recommended_action", ""),
            quality=QualityScore(
                confidence=confidence,
                signal_strength=signal_strength,
                data_coverage=data_coverage,
            ),
            source=source,
            prompt_version=PROMPT_VERSION,
        )

    @staticmethod
    def _build_context(
        events: list[SystemEvent],
        jobs: list[Job],
        metrics: list[Metric],
        alerts: list[Alert],
        correlations: list[Correlation],
    ) -> str:
        sections = [
            "Events:\n" + "\n".join(e.model_dump_json() for e in events),
            "Failed Jobs:\n" + "\n".join(j.model_dump_json() for j in jobs),
            "High CPU Metrics:\n" + "\n".join(m.model_dump_json() for m in metrics),
            "Alerts:\n" + "\n".join(a.model_dump_json() for a in alerts),
        ]
        if correlations:
            sections.append(
                "Pre-computed Correlations:\n"
                + "\n".join(c.model_dump_json() for c in correlations)
            )
        return "\n\n".join(sections)

    @staticmethod
    def _rule_based_analysis(
        events: list[SystemEvent],
        jobs: list[Job],
        alerts: list[Alert],
        metrics: list[Metric],
        correlations: list[Correlation],
    ) -> dict:
        """Deterministic fallback when LLM is unavailable."""
        critical_events = [e for e in events if e.severity == "critical"]
        failed_jobs = [j for j in jobs if j.status == "failed"]
        critical_alerts = [a for a in alerts if a.severity == "critical"]

        # Classify incident type
        has_oom = any("oom" in e.message.lower() or "memory" in e.message.lower() for e in events)
        has_deploy = any(e.type == "deployment" for e in events)
        has_cpu = any(m.value > 90 for m in metrics)

        if has_oom or any(a.metric and "memory" in a.metric for a in alerts):
            incident_type = "resource_exhaustion"
        elif has_deploy and critical_events:
            incident_type = "deployment_issue"
        elif failed_jobs and not critical_events:
            incident_type = "job_failure"
        elif len(critical_events) >= 2 and failed_jobs:
            incident_type = "cascading_failure"
        else:
            incident_type = "unknown"

        # Build reasoning
        steps = []
        if has_deploy:
            steps.append("Detected deployment event")
        if has_oom:
            steps.append("Detected OOM/memory-related event")
        if has_cpu:
            steps.append(f"High CPU detected (>{max(m.value for m in metrics):.0f}%)")
        if failed_jobs:
            steps.append(f"{len(failed_jobs)} failed job(s) detected")
        if critical_alerts:
            steps.append(f"{len(critical_alerts)} critical alert(s) active")
        for c in correlations:
            steps.append(f"Correlation: {c.pattern}")

        # Build summary
        parts = []
        if critical_events:
            parts.append(f"{len(critical_events)} critical event(s)")
        if failed_jobs:
            parts.append(f"{len(failed_jobs)} failed job(s)")
        if critical_alerts:
            parts.append(f"{len(critical_alerts)} critical alert(s)")
        summary = "Detected: " + ", ".join(parts) if parts else "No critical issues detected"

        # Timeline from events
        timeline = [
            {"timestamp": e.timestamp, "event": e.message, "severity": e.severity}
            for e in sorted(events, key=lambda e: e.timestamp)
        ]

        return {
            "incident_type": incident_type,
            "summary": summary,
            "root_cause": correlations[0].pattern if correlations else "Unable to determine — insufficient signal",
            "reasoning_steps": steps,
            "timeline": timeline,
            "recommended_action": "Investigate correlated signals; check recent deployments and resource limits",
            "confidence": 0.4,
        }

    # ── 2. Anomaly Detection ──

    async def detect_anomalies(
        self, time_range: str, anomaly_type: str
    ) -> DetectAnomaliesResponse:
        metrics = await get_high_cpu_processes(time_range)
        alerts = await get_alerts(time_range)

        # Threshold-based detection from alerts
        anomalies: list[Anomaly] = []
        for alert in alerts:
            if alert.value is not None and alert.threshold is not None:
                anomalies.append(
                    Anomaly(
                        metric=alert.metric or "unknown",
                        value=alert.value,
                        threshold=alert.threshold,
                        severity=alert.severity,
                        description=alert.message,
                    )
                )

        # Z-score detection on CPU metrics
        if anomaly_type == "zscore" and len(metrics) >= 2:
            values = [m.value for m in metrics]
            mu = mean(values)
            sigma = stdev(values) if len(values) > 1 else 1.0
            for m in metrics:
                z = (m.value - mu) / sigma if sigma else 0
                if abs(z) > 1.5:
                    anomalies.append(
                        Anomaly(
                            metric=m.name,
                            value=m.value,
                            threshold=mu + 1.5 * sigma,
                            severity="warning",
                            description=f"Z-score {z:.2f} on {m.source}",
                        )
                    )

        context = json.dumps([a.model_dump() for a in anomalies], indent=2)
        llm_result = await self.llm.detect_anomalies(context)

        return DetectAnomaliesResponse(
            anomalies=anomalies,
            summary=llm_result.get("summary", ""),
        )

    # ── 3. Semantic Search (RAG) ──

    async def search(self, query: str) -> SearchResponse:
        context = await self.rag.retrieve(query)
        result = await self.llm.search(query, context)

        sources = [SearchResult(**s) for s in result.get("sources", [])]

        return SearchResponse(
            query=query,
            answer=result.get("answer", ""),
            sources=sources,
        )

    # ── 4. Prioritization ──

    async def prioritize(self, time_range: str) -> PrioritizeResponse:
        events = await get_recent_events(time_range)
        jobs = await get_failed_jobs(time_range)
        alerts = await get_alerts(time_range)

        items: list[dict] = []
        for e in events:
            items.append({"id": e.id, "type": "event", "title": e.message, "severity": e.severity})
        for j in jobs:
            items.append({"id": j.id, "type": "job", "title": f"{j.name}: {j.error or j.status}", "severity": "critical" if j.status == "failed" else "info"})
        for a in alerts:
            items.append({"id": a.id, "type": "alert", "title": a.message, "severity": a.severity})

        context = json.dumps(items, indent=2)
        result = await self.llm.prioritize(context)

        ranked = [RankedItem(**r) for r in result.get("ranked_items", [])]

        return PrioritizeResponse(
            ranked_items=ranked,
            reasoning=result.get("reasoning", ""),
        )
