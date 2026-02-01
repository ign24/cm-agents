"""API smoke tests."""

import pytest
from fastapi.testclient import TestClient

from cm_agents.api.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestHealth:
    """Health endpoint tests."""

    def test_health_returns_ok(self, client: TestClient):
        """Health endpoint returns healthy status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    def test_root_returns_api_info(self, client: TestClient):
        """Root endpoint returns API info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert data["docs"] == "/docs"


class TestBrands:
    """Brands endpoint tests."""

    def test_list_brands_returns_list(self, client: TestClient):
        """List brands returns array."""
        response = client.get("/api/v1/brands")
        assert response.status_code == 200
        data = response.json()
        assert "brands" in data
        assert "total" in data
        assert isinstance(data["brands"], list)

    def test_get_nonexistent_brand_returns_404(self, client: TestClient):
        """Get nonexistent brand returns 404."""
        response = client.get("/api/v1/brands/nonexistent-brand")
        assert response.status_code == 404


class TestPlans:
    """Plans endpoint tests."""

    def test_list_plans_returns_list(self, client: TestClient):
        """List plans returns array."""
        response = client.get("/api/v1/plans")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_nonexistent_plan_returns_404(self, client: TestClient):
        """Get nonexistent plan returns 404."""
        response = client.get("/api/v1/plans/nonexistent-plan")
        assert response.status_code == 404

    def test_create_plan_without_brand_returns_404(self, client: TestClient):
        """Create plan with nonexistent brand returns 404."""
        response = client.post(
            "/api/v1/plans",
            json={
                "prompt": "Test plan",
                "brand": "nonexistent-brand",
            },
        )
        assert response.status_code == 404


class TestChat:
    """Chat endpoint tests."""

    def test_chat_returns_response(self, client: TestClient):
        """Chat endpoint returns assistant message."""
        response = client.post(
            "/api/v1/chat",
            json={"message": "Hola, necesito ayuda"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["message"]["role"] == "assistant"
        assert len(data["message"]["content"]) > 0

    def test_chat_history_returns_history(self, client: TestClient):
        """Chat history endpoint works."""
        response = client.get("/api/v1/chat/history/test-session")
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "messages" in data
        assert data["session_id"] == "test-session"

    def test_clear_chat_history(self, client: TestClient):
        """Clear chat history works."""
        response = client.delete("/api/v1/chat/history/test-session")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cleared"
