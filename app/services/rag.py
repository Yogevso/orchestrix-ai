"""RAG retrieval layer.

MVP: keyword-based filtering over tool data.
Future: vector search via FAISS / SQLite-VSS.
"""

import logging
from app.schemas import SystemEvent, Job, Alert, Metric
from app.services.tools import (
    get_recent_events,
    get_failed_jobs,
    get_high_cpu_processes,
    get_alerts,
)

logger = logging.getLogger(__name__)


class RAGRetriever:
    """Simple retrieval layer that fetches and filters system data by keyword relevance."""

    async def retrieve(self, query: str, time_range: str = "last_10_minutes") -> str:
        """Retrieve context relevant to *query* by pulling tool data and filtering."""
        logger.info("RAG retrieve: query=%r, time_range=%s", query, time_range)

        events = await get_recent_events(time_range)
        jobs = await get_failed_jobs(time_range)
        metrics = await get_high_cpu_processes(time_range)
        alerts = await get_alerts(time_range)

        tokens = query.lower().split()

        relevant_events = self._filter(events, tokens)
        relevant_jobs = self._filter(jobs, tokens)
        relevant_metrics = self._filter(metrics, tokens)
        relevant_alerts = self._filter(alerts, tokens)

        sections: list[str] = []
        if relevant_events:
            sections.append(
                "## Events\n" + "\n".join(e.model_dump_json() for e in relevant_events)
            )
        if relevant_jobs:
            sections.append(
                "## Jobs\n" + "\n".join(j.model_dump_json() for j in relevant_jobs)
            )
        if relevant_metrics:
            sections.append(
                "## Metrics\n"
                + "\n".join(m.model_dump_json() for m in relevant_metrics)
            )
        if relevant_alerts:
            sections.append(
                "## Alerts\n"
                + "\n".join(a.model_dump_json() for a in relevant_alerts)
            )

        # Fall back to returning everything when no keyword matches
        if not sections:
            sections.append(
                "## Events\n" + "\n".join(e.model_dump_json() for e in events)
            )
            sections.append(
                "## Jobs\n" + "\n".join(j.model_dump_json() for j in jobs)
            )
            sections.append(
                "## Metrics\n" + "\n".join(m.model_dump_json() for m in metrics)
            )
            sections.append(
                "## Alerts\n" + "\n".join(a.model_dump_json() for a in alerts)
            )

        return "\n\n".join(sections)

    # ── helpers ──

    @staticmethod
    def _filter[T](items: list[T], tokens: list[str]) -> list[T]:
        """Keep items whose JSON representation contains any query token."""
        result: list[T] = []
        for item in items:
            dump = item.model_dump_json().lower()
            if any(tok in dump for tok in tokens):
                result.append(item)
        return result
