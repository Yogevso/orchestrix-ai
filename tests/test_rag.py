import pytest
from app.services.rag import RAGRetriever


@pytest.mark.anyio
async def test_retrieve_with_keyword():
    rag = RAGRetriever()
    result = await rag.retrieve("CPU")
    assert "cpu" in result.lower() or "CPU" in result


@pytest.mark.anyio
async def test_retrieve_fallback():
    """With a nonsense query, RAG falls back to returning all data."""
    rag = RAGRetriever()
    result = await rag.retrieve("xyznonexistent")
    assert "Events" in result
    assert "Jobs" in result
