import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.core.config import Settings
from backend.app.main import create_app


@pytest.mark.anyio
async def test_health_reports_database_ready_without_requiring_an_llm_key(
    database_url,
):
    settings = Settings(
        _env_file=None,
        database_url=database_url,
        chat_provider="deepseek",
        chat_llm_base_url="https://example.test/v1",
        chat_llm_model="chat-model",
        chat_llm_api_key="",
    )
    transport = ASGITransport(app=create_app(settings=settings))

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {
            "status": "ok",
            "database": "ok",
            "chat_provider": "mock",
        },
        "message": "ok",
    }
