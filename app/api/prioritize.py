import logging

from fastapi import APIRouter, Depends, HTTPException
from app.schemas import PrioritizeRequest, PrioritizeResponse
from app.services.analyzer import AnalyzerService
from app.dependencies import get_analyzer, verify_api_key

router = APIRouter(prefix="/ai", tags=["prioritize"], dependencies=[Depends(verify_api_key)])
logger = logging.getLogger(__name__)


@router.post("/prioritize", response_model=PrioritizeResponse)
async def prioritize(
    req: PrioritizeRequest,
    service: AnalyzerService = Depends(get_analyzer),
):
    try:
        return await service.prioritize(req.time_range)
    except Exception as exc:
        logger.exception("Prioritization failed")
        raise HTTPException(status_code=502, detail="Prioritization failed — check server logs")
