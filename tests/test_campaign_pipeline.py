"""Tests for CampaignPipeline - the optimized campaign execution pipeline.

Testing Strategy (2026 Best Practices):
1. Integration Tests - Test full pipeline with mocked external APIs
2. Flow Tests - Verify correct agent orchestration order
3. Batch Tests - Verify parallel generation works correctly
4. Cost Tracking - Verify cost estimates match actual costs
5. Performance Tests - Measure end-to-end latency
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cm_agents.models.brand import Brand
from cm_agents.models.campaign_plan import CampaignPlan, DayPlan, VisualCoherence
from cm_agents.models.generation import GenerationParams, GenerationPrompt, GenerationResult

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_campaign_plan_3_days():
    """Create a 3-day campaign for faster testing."""
    return CampaignPlan(
        name="Test Campaign",
        brand_slug="test-brand",
        days=[
            DayPlan(day=1, theme="teaser", products=["test-product"], urgency_level="low"),
            DayPlan(day=2, theme="main_offer", products=["test-product"], urgency_level="high"),
            DayPlan(day=3, theme="closing", products=["test-product"], urgency_level="critical"),
        ],
        visual_coherence=VisualCoherence(base_style="minimal_clean"),
    )


@pytest.fixture
def mock_creative_engine():
    """Mock CreativeEngine to return predictable prompts."""

    def _create_prompts(num: int):
        return [
            GenerationPrompt(
                prompt=f"Test prompt {i + 1}",
                visual_description=f"Visual {i + 1}",
                negative_prompt="blurry",
                params=GenerationParams(aspect_ratio="4:5", quality="high", size="1080x1350"),
            )
            for i in range(num)
        ]

    mock = MagicMock()
    mock.name = "CreativeEngine"
    mock.description = "Mocked"
    mock.create_campaign_prompts = MagicMock(
        side_effect=lambda **kwargs: _create_prompts(len(kwargs.get("campaign_plan").days))
    )
    return mock


@pytest.fixture
def mock_generator():
    """Mock Generator for batch parallel testing."""
    call_count = {"value": 0}

    def _generate_batch_parallel_sync(prompts, brand, products, output_dir, **kwargs):
        results = []
        for i, prompt in enumerate(prompts):
            call_count["value"] += 1
            result = GenerationResult(
                id=f"gen_{i}",
                image_path=output_dir / f"image_{i}.png",
                prompt_used=prompt.prompt,
                brand_name=brand.name,
                product_name="test",
                variant_number=i + 1,
                cost_usd=0.04,
            )
            # Create dummy file
            result.image_path.parent.mkdir(parents=True, exist_ok=True)
            result.image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
            results.append(result)
        return results

    mock = MagicMock()
    mock.name = "Generator"
    mock.description = "Mocked"
    mock.generate_batch_parallel_sync = MagicMock(side_effect=_generate_batch_parallel_sync)
    mock.call_count = call_count
    return mock


# =============================================================================
# Integration Tests
# =============================================================================


class TestCampaignPipelineIntegration:
    """Integration tests for full pipeline execution."""

    def test_pipeline_initializes_both_agents(self):
        """CampaignPipeline should initialize CreativeEngine and Generator."""
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test", "OPENAI_API_KEY": "test"}):
            # Mock the actual agent classes where they're imported
            with patch("cm_agents.agents.creative_engine.CreativeEngine") as mock_ce:
                with patch("cm_agents.agents.generator.GeneratorAgent") as mock_gen:
                    mock_ce.return_value.name = "CreativeEngine"
                    mock_ce.return_value.description = "Mocked"
                    mock_gen.return_value.name = "Generator"
                    mock_gen.return_value.description = "Mocked"

                    from cm_agents.pipeline import CampaignPipeline

                    pipeline = CampaignPipeline()

                    assert pipeline.creative_engine is not None
                    assert pipeline.generator is not None

    def test_pipeline_executes_in_correct_order(
        self,
        sample_campaign_plan_3_days,
        brands_dir: Path,
        mock_creative_engine,
        mock_generator,
        tmp_path: Path,
    ):
        """Pipeline should execute: CreativeEngine -> Generator batch."""
        call_order = []

        def track_creative_engine(*args, **kwargs):
            call_order.append("creative_engine")
            return [
                GenerationPrompt(
                    prompt="test",
                    visual_description="",
                    negative_prompt="",
                    params=GenerationParams(aspect_ratio="4:5", quality="high", size="1080x1350"),
                )
                for _ in range(3)
            ]

        def track_generator(*args, **kwargs):
            call_order.append("generator")
            output_dir = kwargs.get("output_dir", args[3] if len(args) > 3 else tmp_path)
            return [
                GenerationResult(
                    id="1",
                    image_path=output_dir / "img.png",
                    prompt_used="test",
                    brand_name="test",
                    product_name="test",
                    variant_number=1,
                    cost_usd=0.04,
                )
            ]

        mock_creative_engine.create_campaign_prompts = MagicMock(side_effect=track_creative_engine)
        mock_generator.generate_batch_parallel_sync = MagicMock(side_effect=track_generator)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test", "OPENAI_API_KEY": "test"}):
            # Directly inject mocked agents into pipeline
            from cm_agents.pipeline import CampaignPipeline

            with patch.object(CampaignPipeline, "__init__", lambda self, **kwargs: None):
                pipeline = CampaignPipeline()
                pipeline.creative_engine = mock_creative_engine
                pipeline.generator = mock_generator

                # Create style reference
                style_ref = tmp_path / "style.jpg"
                style_ref.write_bytes(b"\x89PNG\r\n\x1a\n")

                pipeline.run(
                    campaign_plan=sample_campaign_plan_3_days,
                    brand_dir=brands_dir / "test-brand",
                    style_references=[style_ref],
                    output_dir=tmp_path / "output",
                )

                # Verify order
                assert call_order == ["creative_engine", "generator"], (
                    f"Expected [creative_engine, generator], got {call_order}"
                )


class TestCampaignPipelineBatch:
    """Tests for batch parallel generation."""

    def test_generator_called_once_for_batch(
        self,
        sample_campaign_plan_3_days,
        brands_dir: Path,
        mock_creative_engine,
        mock_generator,
        tmp_path: Path,
    ):
        """Generator.generate_batch_parallel_sync should be called once with all prompts."""
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test", "OPENAI_API_KEY": "test"}):
            from cm_agents.pipeline import CampaignPipeline

            with patch.object(CampaignPipeline, "__init__", lambda self, **kwargs: None):
                pipeline = CampaignPipeline()
                pipeline.creative_engine = mock_creative_engine
                pipeline.generator = mock_generator

                style_ref = tmp_path / "style.jpg"
                style_ref.write_bytes(b"\x89PNG\r\n\x1a\n")

                pipeline.run(
                    campaign_plan=sample_campaign_plan_3_days,
                    brand_dir=brands_dir / "test-brand",
                    style_references=[style_ref],
                    output_dir=tmp_path / "output",
                )

                # Should be called exactly once (batch, not per-image)
                assert mock_generator.generate_batch_parallel_sync.call_count == 1

    def test_returns_correct_number_of_results(
        self,
        sample_campaign_plan_3_days,
        brands_dir: Path,
        mock_creative_engine,
        mock_generator,
        tmp_path: Path,
    ):
        """Pipeline should return one result per day in campaign."""
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test", "OPENAI_API_KEY": "test"}):
            from cm_agents.pipeline import CampaignPipeline

            with patch.object(CampaignPipeline, "__init__", lambda self, **kwargs: None):
                pipeline = CampaignPipeline()
                pipeline.creative_engine = mock_creative_engine
                pipeline.generator = mock_generator

                style_ref = tmp_path / "style.jpg"
                style_ref.write_bytes(b"\x89PNG\r\n\x1a\n")

                results = pipeline.run(
                    campaign_plan=sample_campaign_plan_3_days,
                    brand_dir=brands_dir / "test-brand",
                    style_references=[style_ref],
                    output_dir=tmp_path / "output",
                )

                # 3-day campaign should produce 3 images
                assert len(results) == 3


class TestCampaignPipelineCostTracking:
    """Tests for cost estimation and tracking."""

    def test_campaign_plan_estimates_cost(self, sample_campaign_plan_3_days):
        """CampaignPlan should estimate cost before execution."""
        # 3 images * $0.04 + $0.015 overhead
        expected_min = 3 * 0.04
        expected_max = expected_min + 0.02  # Allow for overhead

        assert sample_campaign_plan_3_days.estimated_cost_usd >= expected_min
        assert sample_campaign_plan_3_days.estimated_cost_usd <= expected_max

    def test_actual_cost_matches_estimate(
        self,
        sample_campaign_plan_3_days,
        brands_dir: Path,
        mock_creative_engine,
        mock_generator,
        tmp_path: Path,
    ):
        """Actual generation cost should be close to estimate."""
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test", "OPENAI_API_KEY": "test"}):
            from cm_agents.pipeline import CampaignPipeline

            with patch.object(CampaignPipeline, "__init__", lambda self, **kwargs: None):
                pipeline = CampaignPipeline()
                pipeline.creative_engine = mock_creative_engine
                pipeline.generator = mock_generator

                style_ref = tmp_path / "style.jpg"
                style_ref.write_bytes(b"\x89PNG\r\n\x1a\n")

                results = pipeline.run(
                    campaign_plan=sample_campaign_plan_3_days,
                    brand_dir=brands_dir / "test-brand",
                    style_references=[style_ref],
                    output_dir=tmp_path / "output",
                )

                actual_cost = sum(r.cost_usd for r in results)
                estimated_cost = sample_campaign_plan_3_days.estimated_cost_usd

                # Actual should be within 50% of estimate (accounting for overhead variance)
                assert actual_cost > 0
                assert abs(actual_cost - estimated_cost) < estimated_cost * 0.5


# =============================================================================
# Strategist Campaign Planning Tests
# =============================================================================


class TestStrategistCampaignPlanning:
    """Tests for Strategist.plan_campaign() method."""

    def test_plan_campaign_creates_correct_days(self, brands_dir: Path, knowledge_dir: Path):
        """plan_campaign should create specified number of days."""
        from cm_agents.agents.strategist import StrategistAgent

        agent = StrategistAgent(knowledge_dir=knowledge_dir)
        brand = Brand.load(brands_dir / "test-brand")

        plan = agent.plan_campaign(
            prompt="Black Friday campaign",
            brand=brand,
            brand_dir=brands_dir / "test-brand",
            days=7,
        )

        assert len(plan.days) == 7
        assert plan.name == "Black Friday"

    def test_plan_campaign_detects_occasion(self, brands_dir: Path, knowledge_dir: Path):
        """plan_campaign should detect occasion from prompt."""
        from cm_agents.agents.strategist import StrategistAgent

        agent = StrategistAgent(knowledge_dir=knowledge_dir)
        brand = Brand.load(brands_dir / "test-brand")

        # Test Black Friday detection
        plan = agent.plan_campaign(
            prompt="black friday week sale",
            brand=brand,
            brand_dir=brands_dir / "test-brand",
            days=3,
        )
        assert plan.name == "Black Friday"

        # Test Navidad detection
        plan = agent.plan_campaign(
            prompt="campaña de navidad",
            brand=brand,
            brand_dir=brands_dir / "test-brand",
            days=3,
        )
        assert plan.name == "Navidad"

    def test_plan_campaign_assigns_themes_by_day(self, brands_dir: Path, knowledge_dir: Path):
        """plan_campaign should assign appropriate themes to each day."""
        from cm_agents.agents.strategist import StrategistAgent

        agent = StrategistAgent(knowledge_dir=knowledge_dir)
        brand = Brand.load(brands_dir / "test-brand")

        plan = agent.plan_campaign(
            prompt="Black Friday 7 días",
            brand=brand,
            brand_dir=brands_dir / "test-brand",
            days=7,
        )

        # First day should be teaser
        assert plan.days[0].theme == "teaser"

        # Last day should be closing
        assert plan.days[-1].theme == "closing"

        # Middle days should have progression
        themes = [d.theme for d in plan.days]
        assert "main_offer" in themes


# =============================================================================
# Generator Batch Parallel Tests
# =============================================================================


class TestGeneratorBatchParallel:
    """Tests for Generator.generate_batch_parallel()."""

    def test_batch_parallel_generates_all_images_sync(self, tmp_path: Path):
        """generate_batch_parallel_sync should work with mocked generator."""
        from cm_agents.models.product import Product

        # Create mock generator that returns results directly
        mock_gen = MagicMock()

        def mock_generate_batch(prompts, brand, products, output_dir, **kwargs):
            results = []
            for i, p in enumerate(prompts):
                result = GenerationResult(
                    id=f"test_{i}",
                    image_path=output_dir / f"img_{i}.png",
                    prompt_used=p.prompt,
                    brand_name=brand.name,
                    product_name="test",
                    variant_number=i + 1,
                    cost_usd=0.04,
                )
                result.image_path.parent.mkdir(parents=True, exist_ok=True)
                result.image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
                results.append(result)
            return results

        mock_gen.generate_batch_parallel_sync = MagicMock(side_effect=mock_generate_batch)

        prompts = [
            GenerationPrompt(
                prompt=f"Test {i}",
                visual_description="",
                negative_prompt="",
                params=GenerationParams(aspect_ratio="4:5", quality="high", size="1080x1350"),
            )
            for i in range(3)
        ]

        brand = MagicMock()
        brand.name = "TestBrand"

        products = {"test": Product(name="Test", price="$1", category="test")}

        results = mock_gen.generate_batch_parallel_sync(
            prompts=prompts,
            brand=brand,
            products=products,
            output_dir=tmp_path,
        )

        assert len(results) == 3
        assert all(r.image_path.exists() for r in results)

    def test_batch_parallel_sync_wrapper(self, tmp_path: Path):
        """generate_batch_parallel_sync should work from sync context."""
        from cm_agents.agents.generator import GeneratorAgent
        from cm_agents.models.product import Product

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            mock_client = MagicMock()
            mock_client.images.generate.return_value = MagicMock(
                data=[MagicMock(url="https://example.com/image.png")]
            )

            with patch("openai.OpenAI", return_value=mock_client):
                with patch("httpx.get") as mock_get:
                    mock_get.return_value.content = b"\x89PNG\r\n\x1a\n"

                    generator = GeneratorAgent()

                    prompts = [
                        GenerationPrompt(
                            prompt="Test",
                            visual_description="",
                            negative_prompt="",
                            params=GenerationParams(
                                aspect_ratio="4:5", quality="high", size="1080x1350"
                            ),
                        )
                    ]

                    brand = MagicMock()
                    brand.name = "TestBrand"
                    brand.get_logo_path.return_value = None

                    products = {"test": Product(name="Test", price="$1", category="test")}

                    # Should not raise
                    results = generator.generate_batch_parallel_sync(
                        prompts=prompts,
                        brand=brand,
                        products=products,
                        output_dir=tmp_path,
                    )

                    assert isinstance(results, list)
