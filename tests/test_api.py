import asyncio
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.anyio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_analyze_incident_validation(client):
    """Missing required field should return 422."""
    resp = await client.post("/ai/analyze-incident", json={})
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_search_validation(client):
    resp = await client.post("/ai/search", json={})
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_detect_anomalies_validation(client):
    resp = await client.post("/ai/detect-anomalies", json={})
    # empty body is valid (all fields have defaults) → should attempt processing
    assert resp.status_code in (200, 502)


@pytest.mark.anyio
async def test_prioritize_validation(client):
    resp = await client.post("/ai/prioritize", json={})
    assert resp.status_code in (200, 502)


@pytest.mark.anyio
async def test_live_stream():
    """SSE generator should yield status events with expected structure."""
    import json
    from unittest.mock import AsyncMock
    from app.api.live import _generate_stream

    # Mock a Request that isn't disconnected on first call, then is on second
    mock_request = AsyncMock()
    mock_request.is_disconnected = AsyncMock(side_effect=[False, True])

    gen = _generate_stream(mock_request)
    event = await gen.__anext__()
    assert event["event"] == "status"
    data = json.loads(event["data"])
    assert "timestamp" in data
    assert "status" in data
    assert "counts" in data
    assert data["counts"]["events"] > 0
    await gen.aclose()


@pytest.mark.anyio
async def test_replay_accepts_empty_body(client):
    """Replay with empty telemetry should process (may fail with 502 without LLM)."""
    resp = await client.post("/ai/replay-incident", json={})
    assert resp.status_code in (200, 502)


@pytest.mark.anyio
async def test_batch_rejects_too_many(client):
    """Batch should reject more than 20 incident IDs."""
    ids = [f"inc-{i}" for i in range(25)]
    resp = await client.post("/ai/analyze-batch", json={"incident_ids": ids})
    assert resp.status_code == 400
    assert "Maximum 20" in resp.json()["detail"]


@pytest.mark.anyio
async def test_batch_validation(client):
    """Batch missing incident_ids should return 422."""
    resp = await client.post("/ai/analyze-batch", json={})
    assert resp.status_code == 422
