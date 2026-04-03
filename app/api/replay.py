import logging

from fastapi import APIRouter, Depends, HTTPException
from app.schemas import ReplayIncidentRequest, AnalyzeIncidentResponse
from app.services.analyzer import AnalyzerService
from app.dependencies import get_analyzer, verify_api_key

router = APIRouter(prefix="/ai", tags=["replay"], dependencies=[Depends(verify_api_key)])
logger = logging.getLogger(__name__)


@router.post("/replay-incident", response_model=AnalyzeIncidentResponse)
async def replay_incident(
    req: ReplayIncidentRequest,
    service: AnalyzerService = Depends(get_analyzer),
):
    """Replay mode: submit custom telemetry for reproducible incident debugging."""
    try:
        return await service.replay_incident(
            events_raw=req.events,
            jobs_raw=req.jobs,
            alerts_raw=req.alerts,
            metrics_raw=req.metrics,
        )
    except Exception as exc:
        logger.exception("Replay analysis failed")
        raise HTTPException(status_code=502, detail="Replay analysis failed — check server logs")
