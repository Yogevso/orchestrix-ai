import json
import logging
from openai import AsyncOpenAI
from app.config import get_settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are an AI system engineer analyzing distributed system incidents.

You receive:
- events
- jobs
- alerts

Your task:
1. identify patterns
2. explain root cause
3. generate timeline
4. recommend actions

Return structured JSON.
"""


class LLMService:
    def __init__(self) -> None:
        settings = get_settings()
        self._client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=30.0)
        self._model = settings.llm_model

    async def analyze_incident(self, context: str) -> dict:
        """Send incident context to LLM and get structured analysis."""
        return await self._call(
            system=SYSTEM_PROMPT,
            user=(
                "Analyze the following incident data and return JSON with keys: "
                "incident_type (one of: resource_exhaustion, network_anomaly, "
                "job_failure, deployment_issue, cascading_failure, unknown), "
                "summary, root_cause, "
                "reasoning_steps (list of strings — each step in your reasoning chain, "
                "e.g. 'Detected CPU spike on worker pod', 'Found correlated OOM event'), "
                "timeline (list of {timestamp, event, severity}), "
                "recommended_action, confidence (0-1).\n\n"
                f"{context}"
            ),
        )

    async def detect_anomalies(self, context: str) -> dict:
        """Ask LLM to summarize detected anomalies."""
        return await self._call(
            system=SYSTEM_PROMPT,
            user=(
                "Given the following anomaly data, return JSON with keys: "
                "anomalies (list of {metric, value, threshold, severity, description}), "
                "summary.\n\n"
                f"{context}"
            ),
        )

    async def search(self, query: str, context: str) -> dict:
        """RAG-style search: answer query using retrieved context."""
        return await self._call(
            system=SYSTEM_PROMPT,
            user=(
                f"User query: {query}\n\n"
                "Relevant system data:\n"
                f"{context}\n\n"
                "Return JSON with keys: answer, sources (list of "
                "{content, source, relevance})."
            ),
        )

    async def prioritize(self, context: str) -> dict:
        """Prioritize items by severity/impact."""
        return await self._call(
            system=SYSTEM_PROMPT,
            user=(
                "Prioritize the following items by severity and impact. "
                "Return JSON with keys: ranked_items (list of "
                "{id, type, title, priority (1-5), reason}), reasoning.\n\n"
                f"{context}"
            ),
        )

    async def _call(self, system: str, user: str) -> dict:
        """Execute a chat completion and parse JSON from the response."""
        logger.info("LLM call: model=%s, prompt_len=%d", self._model, len(user))
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        raw = response.choices[0].message.content
        logger.debug("LLM raw response: %s", raw)
        return json.loads(raw)
