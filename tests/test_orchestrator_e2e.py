"""End-to-end tests for OrchestratorCampaignService."""

from __future__ import annotations

import base64
import io
import json
import os
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from cm_agents.services.agent_campaign import OrchestratorCampaignService


BRAND_JSON = {
    "name": "Test Brand",
    "handle": "@testbrand",
    "industry": "food_restaurant",
    "identity": {
        "tagline": "Sabor de casa",
        "voice": ["familiar"],
        "values": ["calidad"],
    },
    "palette": {
        "primary": "#D32F2F",
        "secondary": "#FFC107",
        "accent": "#4CAF50",
    },
    "style": {
        "mood": ["calido", "familiar"],
        "photography_style": "close-up, warm lighting",
        "preferred_design_styles": ["minimal_clean"],
        "avoid": ["cold colors"],
    },
    "text_overlay": {
        "price_badge": {
            "bg_color": "#D32F2F",
            "text_color": "#FFFFFF",
            "position": "bottom-left",
        },
        "title": {"position": "top-center"},
        "logo": {"position": "top-right", "size": "small"},
    },
}

STYLES_JSON = {
    "styles": {
        "minimal_clean": {
            "name": "Minimal Clean",
            "description": "Clean and simple style",
            "lighting": "soft_studio",
            "composition": "centered",
            "background": ["white", "light gray"],
            "prompt_template": "professional product photo, clean minimal background",
            "negative_prompt": "clutter, busy",
        }
    }
}


def _make_valid_png(width: int = 200, height: int = 200) -> bytes:
    """Create a valid PNG image in memory."""
    image = Image.new("RGB", (width, height), color=(128, 64, 32))
    pixels = image.load()
    for x in range(width):
        for y in range(height):
            pixels[x, y] = (
                (x * 7 + y * 3) % 256,
                (x * 11 + y * 5) % 256,
                (y * 13 + x) % 256,
            )

    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _make_noisy_png(width: int = 500, height: int = 500) -> bytes:
    """Create a high-entropy PNG to avoid over-compression (<20KB)."""
    raw = os.urandom(width * height * 3)
    image = Image.frombytes("RGB", (width, height), raw)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _workers_by_name(artifacts: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {w["name"]: w for w in artifacts["worker_plan"]["workers"]}


@pytest.fixture
def orchestrator_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create full filesystem and env expected by the orchestrator."""
    brand_dir = tmp_path / "brands" / "test-brand"
    brand_dir.mkdir(parents=True)
    (brand_dir / "brand.json").write_text(json.dumps(BRAND_JSON), encoding="utf-8")

    product_dir = brand_dir / "products" / "demo-product"
    photos_dir = product_dir / "photos"
    photos_dir.mkdir(parents=True)
    (photos_dir / "main.png").write_bytes(_make_valid_png(100, 100))

    refs_dir = brand_dir / "references"
    refs_dir.mkdir()
    (refs_dir / "style_ref.png").write_bytes(_make_valid_png(100, 100))

    (brand_dir / "assets").mkdir()

    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    (knowledge_dir / "design_2026.json").write_text(json.dumps(STYLES_JSON), encoding="utf-8")

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("LANGSEARCH_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)

    return tmp_path


@pytest.fixture
def mock_openai_responses(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Mock OpenAI Responses API with valid PNG >= 20KB."""
    valid_png = _make_noisy_png(500, 500)
    valid_b64 = base64.b64encode(valid_png).decode()
    call_log: list[dict[str, Any]] = []

    class MockImageGenerationOutput:
        def __init__(self) -> None:
            self.type = "image_generation_call"
            self.result = valid_b64

    class MockResponsesResult:
        def __init__(self) -> None:
            self.output = [MockImageGenerationOutput()]

    class MockResponses:
        def create(self, **kwargs: Any) -> MockResponsesResult:
            call_log.append({"method": "responses.create", **kwargs})
            return MockResponsesResult()

    class MockImageData:
        def __init__(self) -> None:
            self.b64_json = valid_b64
            self.url = None

    class MockImagesResult:
        def __init__(self) -> None:
            self.data = [MockImageData()]

    class MockImages:
        def generate(self, **kwargs: Any) -> MockImagesResult:
            call_log.append({"method": "images.generate", **kwargs})
            return MockImagesResult()

    class MockOpenAIClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.responses = MockResponses()
            self.images = MockImages()

    monkeypatch.setattr("openai.OpenAI", MockOpenAIClient)
    monkeypatch.setattr("cm_agents.agents.generator.OpenAI", MockOpenAIClient)
    return call_log


@pytest.fixture
def mock_anthropic_creative(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Mock Anthropic client for CreativeEngine and Strategist calls."""
    call_log: list[dict[str, Any]] = []

    creative_engine_json = json.dumps(
        {
            "prompt": "A beautiful product photo with warm studio lighting.",
            "negative_prompt": "blurry, low quality, text artifacts",
            "visual_notes": "centered composition and clean background",
        }
    )

    class MockTextBlock:
        def __init__(self, text: str) -> None:
            self.text = text
            self.type = "text"

    class MockUsage:
        def __init__(self) -> None:
            self.input_tokens = 100
            self.output_tokens = 200

    class MockMessage:
        def __init__(self, text: str) -> None:
            self.content = [MockTextBlock(text)]
            self.usage = MockUsage()
            self.model = "claude-sonnet-4-20250514"
            self.stop_reason = "end_turn"

    class MockMessages:
        def create(self, **kwargs: Any) -> MockMessage:
            call_log.append(
                {
                    "method": "messages.create",
                    "model": kwargs.get("model"),
                    "max_tokens": kwargs.get("max_tokens"),
                }
            )

            messages = kwargs.get("messages", [])

            # CreativeEngine calls include multimodal blocks with type='image'.
            for msg in messages:
                content = msg.get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "image":
                            return MockMessage(creative_engine_json)

            # Default plain text makes worker planning fallback to deterministic policy.
            return MockMessage("Entendido. Te ayudo a crear contenido para tu marca.")

    class MockAnthropicClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.messages = MockMessages()

    monkeypatch.setattr("anthropic.Anthropic", MockAnthropicClient)
    return call_log


def test_orchestrator_build_full(
    orchestrator_env: Path,
    mock_anthropic_creative: list[dict[str, Any]],
    mock_openai_responses: list[dict[str, Any]],
) -> None:
    """build=True and trend request should run all workers."""
    service = OrchestratorCampaignService(knowledge_dir=Path("knowledge"))

    result = service.run(
        brand_slug="test-brand",
        product_slugs=None,
        objective="promo 2x1 con tendencias 2026",
        days=2,
        build=True,
        include_text=True,
        max_retries=1,
        require_llm_orchestrator=False,
    )
    artifacts = result["artifacts"]
    workers = _workers_by_name(artifacts)

    assert workers["research"]["run"] is True
    assert workers["copy"]["run"] is True
    assert workers["design"]["run"] is True
    assert workers["generate"]["run"] is True
    assert workers["qa"]["run"] is True

    assert len(artifacts["campaign_items"]) > 0
    assert all(item["headline"] for item in artifacts["campaign_items"])

    assert len(artifacts["generation"]) > 0
    assert all("image_path" in g for g in artifacts["generation"])
    assert all(g["cost_usd"] > 0 for g in artifacts["generation"] if "cost_usd" in g)

    assert (result["run_dir"] / "report.md").exists()


def test_orchestrator_no_text(
    orchestrator_env: Path,
    mock_anthropic_creative: list[dict[str, Any]],
    mock_openai_responses: list[dict[str, Any]],
) -> None:
    """build=True with no-text objective should skip copy but still generate."""
    service = OrchestratorCampaignService(knowledge_dir=Path("knowledge"))

    result = service.run(
        brand_slug="test-brand",
        product_slugs=None,
        objective="solo producto sin texto",
        days=1,
        build=True,
        include_text=None,
        max_retries=1,
        require_llm_orchestrator=False,
    )
    artifacts = result["artifacts"]
    workers = _workers_by_name(artifacts)

    assert artifacts["input"]["include_text"] is False
    assert workers["copy"]["run"] is False
    assert workers["generate"]["run"] is True

    for item in artifacts["campaign_items"]:
        assert item["headline"] == ""
        assert item["subheadline"] == ""

    assert len(artifacts["generation"]) > 0


def test_orchestrator_no_build(
    orchestrator_env: Path,
    mock_anthropic_creative: list[dict[str, Any]],
) -> None:
    """build=False should disable design/generate/qa and produce no generation outputs."""
    service = OrchestratorCampaignService(knowledge_dir=Path("knowledge"))

    result = service.run(
        brand_slug="test-brand",
        product_slugs=None,
        objective="planificar campaña de delivery",
        days=2,
        build=False,
        include_text=True,
        max_retries=1,
        require_llm_orchestrator=False,
    )
    artifacts = result["artifacts"]
    workers = _workers_by_name(artifacts)

    assert workers["design"]["run"] is False
    assert workers["generate"]["run"] is False
    assert workers["qa"]["run"] is False
    assert artifacts["generation"] == []
    assert len(artifacts["campaign_items"]) > 0


def test_orchestrator_with_style_ref(
    orchestrator_env: Path,
    mock_anthropic_creative: list[dict[str, Any]],
) -> None:
    """With explicit style_ref and build=False, research should be skipped."""
    service = OrchestratorCampaignService(knowledge_dir=Path("knowledge"))
    style_ref = Path("brands/test-brand/references/style_ref.png")

    result = service.run(
        brand_slug="test-brand",
        product_slugs=None,
        objective="campana de invierno",
        days=2,
        build=False,
        include_text=True,
        style_ref=style_ref,
        max_retries=0,
        require_llm_orchestrator=False,
    )
    workers = _workers_by_name(result["artifacts"])
    assert workers["research"]["run"] is False


def test_orchestrator_policy_decides_dynamically(
    orchestrator_env: Path,
    mock_anthropic_creative: list[dict[str, Any]],
) -> None:
    """Policy changes worker plan based on objective keywords."""
    service = OrchestratorCampaignService(knowledge_dir=Path("knowledge"))

    trends_result = service.run(
        brand_slug="test-brand",
        product_slugs=None,
        objective="quiero tendencias para esta campaña",
        days=1,
        build=False,
        include_text=True,
        max_retries=0,
        require_llm_orchestrator=False,
    )
    plain_result = service.run(
        brand_slug="test-brand",
        product_slugs=None,
        objective="armar post de promo",
        days=1,
        build=False,
        include_text=True,
        max_retries=0,
        require_llm_orchestrator=False,
    )

    trends_workers = _workers_by_name(trends_result["artifacts"])
    plain_workers = _workers_by_name(plain_result["artifacts"])

    assert trends_workers["research"]["run"] is True
    assert plain_workers["research"]["run"] is False


def test_orchestrator_artifacts_complete(
    orchestrator_env: Path,
    mock_anthropic_creative: list[dict[str, Any]],
    mock_openai_responses: list[dict[str, Any]],
) -> None:
    """Validate artifacts.json structure and report.md content."""
    service = OrchestratorCampaignService(knowledge_dir=Path("knowledge"))

    result = service.run(
        brand_slug="test-brand",
        product_slugs=None,
        objective="campana completa de verano",
        days=1,
        build=True,
        include_text=True,
        max_retries=1,
        require_llm_orchestrator=False,
    )
    artifacts = result["artifacts"]
    run_dir = result["run_dir"]

    expected = {
        "run_id",
        "created_at",
        "input",
        "worker_plan",
        "trend_brief",
        "selected_style",
        "visual_direction",
        "campaign_items",
        "orchestration_trace",
        "generation",
    }
    assert expected.issubset(set(artifacts.keys()))

    for key in (
        "brand",
        "products",
        "objective",
        "days",
        "build",
        "include_text",
        "max_retries",
    ):
        assert key in artifacts["input"]

    worker_names = {w["name"] for w in artifacts["worker_plan"]["workers"]}
    assert {"research", "copy", "design", "generate", "qa"}.issubset(worker_names)

    assert len(artifacts["campaign_items"]) >= 1
    assert len(artifacts["generation"]) >= 1
    assert "image_path" in artifacts["generation"][0]
    assert "qa" in artifacts["generation"][0]

    artifacts_file = run_dir / "artifacts.json"
    report_file = run_dir / "report.md"
    assert artifacts_file.exists()
    assert report_file.exists()

    report_text = report_file.read_text(encoding="utf-8")
    assert "test-brand" in report_text
    assert "Trend Brief" in report_text
    assert "Items" in report_text
    assert "Generated outputs" in report_text
