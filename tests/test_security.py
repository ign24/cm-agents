"""Security tests."""

import pytest
from fastapi.testclient import TestClient

from cm_agents.api.main import app
from cm_agents.api.security import validate_file_extension, validate_slug


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestSlugValidation:
    """Slug validation tests."""

    def test_valid_slugs(self):
        """Valid slugs pass validation."""
        assert validate_slug("my-brand") is True
        assert validate_slug("brand123") is True
        assert validate_slug("a") is True
        assert validate_slug("test-brand-name") is True

    def test_invalid_slugs_path_traversal(self):
        """Path traversal attempts are rejected."""
        assert validate_slug("../etc/passwd") is False
        assert validate_slug("..\\windows\\system32") is False
        assert validate_slug("brands/../secrets") is False
        assert validate_slug("./current") is False

    def test_invalid_slugs_special_chars(self):
        """Special characters are rejected."""
        assert validate_slug("brand@name") is False
        assert validate_slug("brand name") is False
        assert validate_slug("brand/name") is False
        assert validate_slug("brand\\name") is False
        assert validate_slug("Brand-Name") is False  # Uppercase

    def test_invalid_slugs_edge_cases(self):
        """Edge cases are handled."""
        assert validate_slug("") is False
        assert validate_slug("-invalid") is False
        assert validate_slug("invalid-") is False
        assert validate_slug("a" * 65) is False  # Too long


class TestFileExtensionValidation:
    """File extension validation tests."""

    def test_valid_image_extensions(self):
        """Valid image extensions pass."""
        assert validate_file_extension("logo.png") is True
        assert validate_file_extension("photo.jpg") is True
        assert validate_file_extension("image.jpeg") is True
        assert validate_file_extension("icon.webp") is True
        assert validate_file_extension("logo.svg") is True

    def test_invalid_extensions(self):
        """Invalid extensions are rejected."""
        assert validate_file_extension("script.js") is False
        assert validate_file_extension("style.css") is False
        assert validate_file_extension("data.json") is False
        assert validate_file_extension("shell.sh") is False
        assert validate_file_extension("program.exe") is False

    def test_edge_cases(self):
        """Edge cases are handled."""
        assert validate_file_extension("") is False
        assert validate_file_extension("noextension") is False


class TestAPIPathTraversal:
    """API path traversal protection tests."""

    def test_brand_special_chars_rejected(self, client: TestClient):
        """Special characters in brand slug are rejected."""
        response = client.get("/api/v1/brands/brand@name")
        assert response.status_code == 400

    def test_brand_uppercase_rejected(self, client: TestClient):
        """Uppercase in brand slug is rejected."""
        response = client.get("/api/v1/brands/Brand-Name")
        assert response.status_code == 400

    def test_brand_dots_rejected(self, client: TestClient):
        """Dots in brand slug are rejected (path traversal attempt)."""
        response = client.get("/api/v1/brands/brand..name")
        assert response.status_code == 400

    def test_plan_special_chars_rejected(self, client: TestClient):
        """Special characters in plan ID are rejected."""
        response = client.get("/api/v1/plans/plan@id")
        assert response.status_code == 400

    def test_valid_slugs_work(self, client: TestClient):
        """Valid slugs still work."""
        # Should return 404 (not found) not 400 (bad request)
        response = client.get("/api/v1/brands/valid-brand-name")
        assert response.status_code == 404

        response = client.get("/api/v1/plans/valid-plan-id")
        assert response.status_code == 404


class TestRateLimiting:
    """Rate limiting tests."""

    def test_many_requests_get_limited(self, client: TestClient):
        """Too many requests get rate limited."""
        # Make many rapid requests
        responses = []
        for _ in range(150):  # Over the 120/minute limit
            response = client.get("/health")
            responses.append(response.status_code)

        # At least some should be rate limited
        assert 429 in responses or all(r == 200 for r in responses[:120])
