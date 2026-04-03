import logging

from fastapi import APIRouter, Depends, HTTPException
from app.schemas import AnalyzeIncidentRequest, AnalyzeIncidentResponse
from app.services.analyzer import AnalyzerService
from app.dependencies import get_analyzer, verify_api_key

router = APIRouter(prefix="/ai", tags=["analyze"], dependencies=[Depends(verify_api_key)])
logger = logging.getLogger(__name__)


@router.post("/analyze-incident", response_model=AnalyzeIncidentResponse)
async def analyze_incident(
    req: AnalyzeIncidentRequest,
    service: AnalyzerService = Depends(get_analyzer),
):
    try:
        return await service.analyze_incident(req.incident_id, req.time_range)
    except Exception as exc:
        logger.exception("Analysis failed for %s", req.incident_id)
        raise HTTPException(status_code=502, detail="Analysis failed — check server logs")
