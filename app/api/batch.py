import logging

from fastapi import APIRouter, Depends, HTTPException
from app.schemas import BatchAnalyzeRequest, BatchAnalyzeResponse
from app.services.analyzer import AnalyzerService
from app.dependencies import get_analyzer, verify_api_key

router = APIRouter(prefix="/ai", tags=["batch"], dependencies=[Depends(verify_api_key)])
logger = logging.getLogger(__name__)


@router.post("/analyze-batch", response_model=BatchAnalyzeResponse)
async def analyze_batch(
    req: BatchAnalyzeRequest,
    service: AnalyzerService = Depends(get_analyzer),
):
    """Batch mode: analyze multiple incidents in a single request."""
    if len(req.incident_ids) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 incidents per batch")

    results = await service.analyze_batch(req.incident_ids, req.time_range)

    return BatchAnalyzeResponse(
        results=results,
        total=len(req.incident_ids),
        succeeded=len(results),
        failed=len(req.incident_ids) - len(results),
    )
