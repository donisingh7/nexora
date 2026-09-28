from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_session
from app.main import app


@pytest.mark.parametrize("path", ["/health", "/api/v1/health"])
def test_health_does_not_require_database(path: str) -> None:
    with TestClient(app) as client:
        response = client.get(path)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize("path", ["/ready", "/api/v1/ready"])
def test_ready_checks_database(path: str) -> None:
    session = AsyncMock()

    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    try:
        with TestClient(app) as client:
            response = client.get(path)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    session.execute.assert_awaited_once()
