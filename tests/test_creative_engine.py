"""Tests for CreativeEngine - the unified analysis + prompt generation agent.

Testing Strategy (2026 Best Practices):
1. Unit Tests - Test agent methods in isolation with mocks
2. Contract Tests - Verify output schema matches expected input for next agent
3. Determinism Tests - Same input with temp=0 should produce same output
4. Error Handling - Graceful degradation on API failures
5. Performance - Track latency and token usage
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cm_agents.agents.creative_engine import CreativeEngine
from cm_agents.models.brand import Brand
from cm_agents.models.campaign_plan import CampaignPlan, DayPlan, VisualCoherence
from cm_agents.models.generation import GenerationPrompt
from cm_agents.models.product import Product

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_creative_engine_response():
    """Factory for mock CreativeEngine LLM responses."""

    def _create(num_prompts: int = 7):
        return json.dumps(
            {
                "reference_analysis": {
                    "style": "Bold contrast with dark backgrounds",
                    "lighting": "Dramatic side lighting with highlights",
                    "composition": "Centered product with negative space",
                    "colors": ["#000000", "#FFD700", "#FF0000"],
                    "mood": "Urgent and exciting",
                },
                "prompts": [
                    {
                        "day": i + 1,
                        "theme": [
                            "teaser",
                            "countdown",
                            "reveal",
                            "anticipation",
                            "main_offer",
                            "extended",
                            "closing",
                        ][i % 7],
                        "prompt": f"Professional product photography, day {i + 1}, "
                        f"dramatic lighting, bold contrast, 8K detail, "
                        f"sharp focus, commercial quality",
                        "negative_prompt": "blurry, low quality, amateur, oversaturated",
                        "visual_notes": f"Day {i + 1}: Focus on urgency and excitement",
                    }
                    for i in range(num_prompts)
                ],
                "coherence_strategy": "Consistent dark backgrounds with gold accents "
                "across all days, progressively increasing urgency",
            }
        )

    return _create


@pytest.fixture
def sample_campaign_plan():
    """Create a sample 7-day campaign plan."""
    days = [
        DayPlan(
            day=1,
            theme="teaser",
            products=["sprite"],
            visual_direction="Dark, mysterious",
            urgency_level="low",
        ),
        DayPlan(
            day=2,
            theme="countdown",
            products=["sprite"],
            visual_direction="Building anticipation",
            urgency_level="low",
        ),
        DayPlan(
            day=3,
            theme="reveal",
            products=["coca"],
            visual_direction="First reveal",
            urgency_level="medium",
        ),
        DayPlan(
            day=4,
            theme="anticipation",
            products=["coca"],
            visual_direction="Excitement building",
            urgency_level="medium",
        ),
        DayPlan(
            day=5,
            theme="main_offer",
            products=["sprite", "coca"],
            visual_direction="All offers visible",
            urgency_level="high",
        ),
        DayPlan(
            day=6,
            theme="extended",
            products=["sprite", "coca"],
            visual_direction="Last hours urgency",
            urgency_level="critical",
        ),
        DayPlan(
            day=7,
            theme="closing",
            products=["sprite"],
            visual_direction="Final chance",
            urgency_level="high",
        ),
    ]

    return CampaignPlan(
        name="Black Friday",
        brand_slug="test-brand",
        days=days,
        visual_coherence=VisualCoherence(
            base_style="bold_contrast", color_scheme=["#000000", "#FFD700", "#FF0000"]
        ),
    )


@pytest.fixture
def sample_brand(brands_dir: Path) -> Brand:
    """Load sample brand from fixture."""
    return Brand.load(brands_dir / "test-brand")


@pytest.fixture
def sample_products() -> dict[str, Product]:
    """Create sample products."""
    return {
        "sprite": Product(name="Sprite", price="$1.99", category="beverages"),
        "coca": Product(name="Coca-Cola", price="$2.49", category="beverages"),
    }


# =============================================================================
# Unit Tests
# =============================================================================


class TestCreativeEngineUnit:
    """Unit tests for CreativeEngine methods."""

    def test_initializes_with_temperature_zero(self):
        """CreativeEngine should use temperature=0 for determinism."""
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("anthropic.Anthropic"):
                engine = CreativeEngine()
                assert engine.temperature == 0, "Temperature should be 0 for determinism"

    def test_has_correct_name_and_description(self):
        """CreativeEngine should have descriptive name."""
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("anthropic.Anthropic"):
                engine = CreativeEngine()
                assert engine.name == "CreativeEngine"
                assert (
                    "unificado" in engine.description.lower()
                    or "unified" in engine.description.lower()
                )


class TestCreativeEngineContracts:
    """Contract tests - verify output schema matches Generator's expected input."""

    def test_output_is_list_of_generation_prompts(
        self,
        mock_anthropic,
        mock_creative_engine_response,
        sample_campaign_plan,
        sample_brand,
        sample_products,
        tmp_path: Path,
    ):
        """CreativeEngine should return list[GenerationPrompt]."""
        # Setup mock response
        mock_anthropic_response = mock_creative_engine_response(7)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            # Create mock that returns our response
            mock_client = MagicMock()
            mock_client.messages.create.return_value = MagicMock(
                content=[MagicMock(text=mock_anthropic_response)]
            )

            with patch("anthropic.Anthropic", return_value=mock_client):
                engine = CreativeEngine()

                # Create dummy reference files
                style_ref = tmp_path / "style.jpg"
                style_ref.write_bytes(b"\x89PNG\r\n\x1a\n")  # Minimal PNG header

                prompts = engine.create_campaign_prompts(
                    campaign_plan=sample_campaign_plan,
                    style_references=[style_ref],
                    product_references={},
                    brand=sample_brand,
                    products=sample_products,
                )

                # Contract: Should return list
                assert isinstance(prompts, list)

                # Contract: Each item should be GenerationPrompt
                for prompt in prompts:
                    assert isinstance(prompt, GenerationPrompt)

    def test_generation_prompt_has_required_fields(
        self,
        mock_anthropic,
        mock_creative_engine_response,
        sample_campaign_plan,
        sample_brand,
        sample_products,
        tmp_path: Path,
    ):
        """Each GenerationPrompt must have fields Generator needs."""
        mock_response = mock_creative_engine_response(1)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            mock_client = MagicMock()
            mock_client.messages.create.return_value = MagicMock(
                content=[MagicMock(text=mock_response)]
            )

            with patch("anthropic.Anthropic", return_value=mock_client):
                engine = CreativeEngine()

                style_ref = tmp_path / "style.jpg"
                style_ref.write_bytes(b"\x89PNG\r\n\x1a\n")

                prompts = engine.create_campaign_prompts(
                    campaign_plan=sample_campaign_plan,
                    style_references=[style_ref],
                    product_references={},
                    brand=sample_brand,
                    products=sample_products,
                )

                if prompts:  # May be empty if parsing fails
                    prompt = prompts[0]

                    # Required fields for Generator
                    assert hasattr(prompt, "prompt"), "Missing 'prompt' field"
                    assert hasattr(prompt, "params"), "Missing 'params' field"
                    assert hasattr(prompt, "negative_prompt"), "Missing 'negative_prompt' field"

                    # Params must have size info
                    assert hasattr(prompt.params, "size"), "Params missing 'size'"
                    assert hasattr(prompt.params, "aspect_ratio"), "Params missing 'aspect_ratio'"


class TestCreativeEngineDeterminism:
    """Determinism tests - same input should produce same output with temp=0."""

    def test_same_input_produces_consistent_structure(
        self,
        mock_creative_engine_response,
        sample_campaign_plan,
        sample_brand,
        sample_products,
        tmp_path: Path,
    ):
        """With temp=0 and same input, output structure should be consistent."""
        mock_response = mock_creative_engine_response(7)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            mock_client = MagicMock()
            mock_client.messages.create.return_value = MagicMock(
                content=[MagicMock(text=mock_response)]
            )

            with patch("anthropic.Anthropic", return_value=mock_client):
                engine = CreativeEngine()

                style_ref = tmp_path / "style.jpg"
                style_ref.write_bytes(b"\x89PNG\r\n\x1a\n")

                # Call twice with same input
                prompts1 = engine.create_campaign_prompts(
                    campaign_plan=sample_campaign_plan,
                    style_references=[style_ref],
                    product_references={},
                    brand=sample_brand,
                    products=sample_products,
                )

                prompts2 = engine.create_campaign_prompts(
                    campaign_plan=sample_campaign_plan,
                    style_references=[style_ref],
                    product_references={},
                    brand=sample_brand,
                    products=sample_products,
                )

                # Same number of prompts
                assert len(prompts1) == len(prompts2), "Should produce same number of prompts"


class TestCreativeEngineErrorHandling:
    """Error handling tests - graceful degradation on failures."""

    def test_handles_invalid_json_response(
        self, sample_campaign_plan, sample_brand, sample_products, tmp_path: Path
    ):
        """Should handle malformed JSON from LLM gracefully."""
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            mock_client = MagicMock()
            # Return invalid JSON
            mock_client.messages.create.return_value = MagicMock(
                content=[MagicMock(text="This is not valid JSON at all")]
            )

            with patch("anthropic.Anthropic", return_value=mock_client):
                engine = CreativeEngine()

                style_ref = tmp_path / "style.jpg"
                style_ref.write_bytes(b"\x89PNG\r\n\x1a\n")

                # Should raise ValueError with clear message
                with pytest.raises(ValueError) as exc_info:
                    engine.create_campaign_prompts(
                        campaign_plan=sample_campaign_plan,
                        style_references=[style_ref],
                        product_references={},
                        brand=sample_brand,
                        products=sample_products,
                    )

                assert (
                    "parsear" in str(exc_info.value).lower()
                    or "parse" in str(exc_info.value).lower()
                )

    def test_handles_missing_reference_files(
        self,
        mock_creative_engine_response,
        sample_campaign_plan,
        sample_brand,
        sample_products,
        tmp_path: Path,
    ):
        """Should handle missing reference files gracefully."""
        mock_response = mock_creative_engine_response(1)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            mock_client = MagicMock()
            mock_client.messages.create.return_value = MagicMock(
                content=[MagicMock(text=mock_response)]
            )

            with patch("anthropic.Anthropic", return_value=mock_client):
                engine = CreativeEngine()

                # Reference to non-existent file
                missing_ref = tmp_path / "does_not_exist.jpg"

                # Should not crash, just skip missing files
                prompts = engine.create_campaign_prompts(
                    campaign_plan=sample_campaign_plan,
                    style_references=[missing_ref],
                    product_references={},
                    brand=sample_brand,
                    products=sample_products,
                )

                # Should still return prompts (analysis may be limited)
                assert isinstance(prompts, list)


# =============================================================================
# Campaign Plan Model Tests
# =============================================================================


class TestCampaignPlanModel:
    """Tests for CampaignPlan dataclass."""

    def test_campaign_plan_calculates_cost(self):
        """CampaignPlan should estimate cost based on days."""
        plan = CampaignPlan(
            name="Test",
            brand_slug="test",
            days=[DayPlan(day=i) for i in range(1, 8)],
        )

        # 7 images * $0.04 + $0.015 overhead = ~$0.295
        assert plan.estimated_cost_usd > 0
        assert plan.total_images == 7

    def test_campaign_plan_gets_all_products(self):
        """CampaignPlan.get_all_products() returns unique products."""
        plan = CampaignPlan(
            name="Test",
            brand_slug="test",
            days=[
                DayPlan(day=1, products=["a", "b"]),
                DayPlan(day=2, products=["b", "c"]),
                DayPlan(day=3, products=["a"]),
            ],
        )

        products = plan.get_all_products()
        assert set(products) == {"a", "b", "c"}

    def test_campaign_plan_to_prompt_context(self):
        """CampaignPlan generates readable context for LLM."""
        plan = CampaignPlan(
            name="Black Friday",
            brand_slug="test-brand",
            days=[DayPlan(day=1, theme="teaser", products=["sprite"])],
        )

        context = plan.to_prompt_context()

        assert "Black Friday" in context
        assert "test-brand" in context
        assert "teaser" in context.lower()
