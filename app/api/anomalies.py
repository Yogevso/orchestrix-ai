import logging

from fastapi import APIRouter, Depends, HTTPException
from app.schemas import DetectAnomaliesRequest, DetectAnomaliesResponse
from app.services.analyzer import AnalyzerService
from app.dependencies import get_analyzer, verify_api_key

router = APIRouter(prefix="/ai", tags=["anomalies"], dependencies=[Depends(verify_api_key)])
logger = logging.getLogger(__name__)


@router.post("/detect-anomalies", response_model=DetectAnomaliesResponse)
async def detect_anomalies(
    req: DetectAnomaliesRequest,
    service: AnalyzerService = Depends(get_analyzer),
):
    try:
        return await service.detect_anomalies(req.time_range, req.anomaly_type.value)
    except Exception as exc:
        logger.exception("Anomaly detection failed")
        raise HTTPException(status_code=502, detail="Anomaly detection failed — check server logs")
