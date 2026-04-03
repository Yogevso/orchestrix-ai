import logging

from fastapi import APIRouter, Depends, HTTPException
from app.schemas import SearchRequest, SearchResponse
from app.services.analyzer import AnalyzerService
from app.dependencies import get_analyzer, verify_api_key

router = APIRouter(prefix="/ai", tags=["search"], dependencies=[Depends(verify_api_key)])
logger = logging.getLogger(__name__)


@router.post("/search", response_model=SearchResponse)
async def search(
    req: SearchRequest,
    service: AnalyzerService = Depends(get_analyzer),
):
    try:
        return await service.search(req.query)
    except Exception as exc:
        logger.exception("Search failed for query: %s", req.query)
        raise HTTPException(status_code=502, detail="Search failed — check server logs")
