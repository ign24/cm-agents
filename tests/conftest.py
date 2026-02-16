"""Pytest configuration and fixtures."""

import os
import sys
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Set test environment
os.environ["ENVIRONMENT"] = "test"


@pytest.fixture
def brands_dir(tmp_path: Path) -> Path:
    """Create a temporary brands directory with test brand."""
    brands = tmp_path / "brands"
    brands.mkdir()

    # Create test brand
    test_brand = brands / "test-brand"
    test_brand.mkdir()

    brand_json = test_brand / "brand.json"
    brand_json.write_text(
        """{
  "name": "Test Brand",
  "handle": "@testbrand",
  "industry": "food_restaurant",
  "palette": {
    "primary": "#FF0000",
    "secondary": "#00FF00"
  },
  "style": {
    "mood": ["professional"],
    "preferred_design_styles": ["minimal_clean"]
  }
}""",
        encoding="utf-8",
    )

    return brands


@pytest.fixture
def knowledge_dir(tmp_path: Path) -> Path:
    """Create a temporary knowledge directory."""
    knowledge = tmp_path / "knowledge"
    knowledge.mkdir()

    # Create minimal design_2026.json
    design_json = knowledge / "design_2026.json"
    design_json.write_text(
        """{
  "styles": {
    "minimal_clean": {
      "name": "Minimal Clean",
      "description": "Clean and simple style"
    }
  }
}""",
        encoding="utf-8",
    )

    return knowledge


@pytest.fixture
def products_dir(tmp_path: Path) -> Path:
    """Create a temporary products directory with test product."""
    products = tmp_path / "products"
    products.mkdir()

    # Create test-brand products
    brand_products = products / "test-brand"
    brand_products.mkdir()

    # Create test product
    test_product = brand_products / "test-product"
    test_product.mkdir()

    product_json = test_product / "product.json"
    product_json.write_text(
        """{
  "name": "Test Product",
  "description": "A test product for testing",
  "price": "$9.99",
  "category": "food"
}""",
        encoding="utf-8",
    )

    # Create photos directory with placeholder
    photos = test_product / "photos"
    photos.mkdir()

    return products


@pytest.fixture
def mock_anthropic_response():
    """Factory for mock Anthropic responses."""

    def _create_response(content: str):
        class MockTextBlock:
            def __init__(self, text):
                self.text = text
                self.type = "text"

        class MockUsage:
            input_tokens = 100
            output_tokens = 200

        class MockMessage:
            def __init__(self, content):
                self.content = [MockTextBlock(content)]
                self.usage = MockUsage()
                self.model = "claude-sonnet-4-20250514"
                self.stop_reason = "end_turn"

        return MockMessage(content)

    return _create_response


@pytest.fixture
def mock_anthropic(monkeypatch, mock_anthropic_response):
    """Mock Anthropic client for testing agents without real API calls."""
    call_log = []

    class MockMessages:
        def create(self, **kwargs):
            call_log.append(
                {
                    "method": "messages.create",
                    "model": kwargs.get("model"),
                    "messages": kwargs.get("messages", []),
                }
            )
            # Return different responses based on context
            messages = kwargs.get("messages", [])
            if messages and "analyze" in str(messages).lower():
                # Extractor response
                return mock_anthropic_response(
                    '{"layout": {"composition": "centered"}, "style": {"mood": "warm"}}'
                )
            elif messages and "prompt" in str(messages).lower():
                # Designer response
                return mock_anthropic_response(
                    '{"prompt": "A beautiful product photo", "negative_prompt": "blurry"}'
                )
            else:
                # Default strategist response
                return mock_anthropic_response(
                    "Entendido. Te ayudo a crear contenido para tu marca."
                )

    class MockClient:
        def __init__(self, *args, **kwargs):
            self.messages = MockMessages()

    monkeypatch.setattr("anthropic.Anthropic", MockClient)
    return call_log


@pytest.fixture
def mock_openai(monkeypatch):
    """Mock OpenAI client for testing image generation without real API calls."""
    call_log = []

    class MockImageData:
        def __init__(self):
            # Minimal valid PNG (1x1 transparent pixel)
            import base64

            self.b64_json = base64.b64encode(b"\x89PNG\r\n\x1a\n").decode()

    class MockImageResponse:
        def __init__(self):
            self.data = [MockImageData()]

    class MockImages:
        def generate(self, **kwargs):
            call_log.append(
                {
                    "method": "images.generate",
                    "model": kwargs.get("model"),
                    "prompt": kwargs.get("prompt", "")[:100],
                }
            )
            return MockImageResponse()

    class MockClient:
        def __init__(self, *args, **kwargs):
            self.images = MockImages()

    monkeypatch.setattr("openai.OpenAI", MockClient)
    return call_log


@pytest.fixture
def mock_mcp_service(monkeypatch):
    """Mock MCP service for testing Pinterest search without real MCP calls."""
    call_log = []

    class MockMCPService:
        async def search_pinterest(self, query: str, limit: int = 10, download: bool = True):
            call_log.append(
                {
                    "method": "search_pinterest",
                    "query": query,
                    "limit": limit,
                }
            )
            return [
                {"url": "https://pinterest.com/pin/123", "local_path": "/tmp/ref1.jpg"},
                {"url": "https://pinterest.com/pin/456", "local_path": "/tmp/ref2.jpg"},
            ]

        async def list_tools(self, server_name: str):
            return [{"name": "search", "description": "Search images"}]

    monkeypatch.setattr("cm_agents.services.mcp_client.MCPClientService", MockMCPService)
    return call_log
