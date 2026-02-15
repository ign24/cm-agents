import json
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from cm_agents.cli import app
from cm_agents.models.plan import ContentIntent, ContentPlan, ContentPlanItem

runner = CliRunner()  # Global runner instance


@pytest.fixture
def mock_pipeline_run():
    """Mock the GenerationPipeline.run method to return a dummy result."""
    with patch("cm_agents.pipeline.GenerationPipeline.run") as mock_run:
        # Configure the mock to return a list containing a dummy GenerationResult
        dummy_result = MagicMock()
        dummy_result.image_path = Path("outputs/test/image.png")
        dummy_result.cost_usd = 0.05
        mock_run.return_value = [dummy_result]  # pipeline.run returns a list of results
        yield mock_run


@pytest.fixture(autouse=True)
def change_test_dir(tmp_path):
    """Change current working directory to tmp_path for each test."""
    original_cwd = Path.cwd()
    os.chdir(tmp_path)
    yield
    os.chdir(original_cwd)


@pytest.fixture
def setup_test_data(tmp_path: Path):
    """
    Sets up a temporary directory with necessary brand, product, and plan data.
    Returns:
        tuple: (brand_dir, product_dir, plan_dir, plan)
    """
    # Setup directories
    brands_dir = tmp_path / "brands"
    products_root_dir = tmp_path / "products"  # Root for products, not per brand
    outputs_dir = tmp_path / "outputs"
    plans_dir = outputs_dir / "plans"
    references_dir = tmp_path / "references"  # For global references

    # Create directories
    brands_dir.mkdir()
    products_root_dir.mkdir()
    plans_dir.mkdir(parents=True)
    references_dir.mkdir()

    # Create dummy brand data
    brand_name = "test-brand"
    brand_dir = brands_dir / brand_name
    brand_dir.mkdir()
    (brand_dir / "brand.json").write_text(
        json.dumps(
            {
                "name": "Test Brand",
                "industry": "food_restaurant",
                "identity": {"tagline": "Sabor"},
                "assets": {"logo": "assets/logo.png"},
                "palette": {"primary": "#FFF"},
                "style": {"mood": ["happy"]},
                "text_overlay": {"price_badge": {"position": "bottom-left"}},
            }
        )
    )
    (brand_dir / "assets").mkdir()
    (brand_dir / "assets" / "logo.png").write_text("dummy_logo_content")  # Dummy logo
    (brand_dir / "references").mkdir()
    (brand_dir / "references" / "style_ref.jpg").write_text(
        "dummy_style_content"
    )  # Dummy style reference

    # Create dummy product data
    product_name = "test-product"
    product_dir = products_root_dir / brand_name / product_name
    product_dir.mkdir(parents=True)
    (product_dir / "product.json").write_text(
        json.dumps(
            {
                "name": "Test Product",
                "price": "$10.00",
                "category": "food",
                "visual_description": "A delicious test product.",
                "photos": ["photos/main.png"],
            }
        )
    )
    (product_dir / "photos").mkdir()
    (product_dir / "photos" / "main.png").write_text("dummy_photo_content")  # Dummy product photo

    # Create a plan
    plan_id = "test-plan-123"
    test_plan = ContentPlan(
        id=plan_id,
        brand=brand_name,
        campaign="test-campaign",
        intent=ContentIntent(objective="promocionar"),
        created_at=datetime.now(),
        estimated_cost=0.0,
    )
    # Add an item to the plan
    item = ContentPlanItem(
        product=product_name,
        size="feed",
        style="minimal_clean",
        variants_count=1,
        status="approved",  # Must be approved for execution
    )
    test_plan.items.append(item)
    test_plan.approved_at = datetime.now()
    test_plan.estimated_cost = 0.15  # Set an estimated cost

    # Save the plan to the temporary outputs directory
    plan_path = plans_dir / f"{plan_id}.json"
    test_plan.save(plan_path)

    # Mock settings.BRANDS_DIR and settings.OUTPUTS_DIR for the test
    with (
        patch("cm_agents.api.config.settings.BRANDS_DIR", str(brands_dir)),
        patch("cm_agents.api.config.settings.OUTPUTS_DIR", str(tmp_path)),
    ):
        yield brand_dir, product_dir, plans_dir, test_plan


def test_plan_execute_success(mock_pipeline_run, setup_test_data, tmp_path: Path):
    """Test that cm plan-execute successfully runs the pipeline and updates the plan."""
    brand_dir, product_dir, plans_dir, initial_plan = setup_test_data
    plan_id = initial_plan.id

    # Use CliRunner to invoke the command
    result = runner.invoke(app, ["plan-execute", plan_id])

    # Assert command execution was successful
    assert result.exit_code == 0, f"Command failed with output: {result.stdout}"
    assert "Proceso de ejecución de plan finalizado." in result.stdout

    # Load the updated plan
    updated_plan = ContentPlan.load(plans_dir / f"{plan_id}.json")

    # Assert pipeline was called
    mock_pipeline_run.assert_called_once()
    call_args, call_kwargs = mock_pipeline_run.call_args
    assert call_kwargs["reference_path"].name == "style_ref.jpg"
    assert call_kwargs["brand_dir"] == brand_dir
    assert call_kwargs["product_dir"] == product_dir
    assert call_kwargs["target_sizes"] == ["feed"]

    # Assert plan status updated
    assert len(updated_plan.items) == 1
    assert updated_plan.items[0].status == "generated"
    assert len(updated_plan.items[0].variants) == 1
    assert updated_plan.items[0].variants[0].status == "generated"
    assert updated_plan.items[0].variants[0].cost_usd == 0.05
    assert updated_plan.items[0].variants[0].output_path == str(Path("outputs/test/image.png"))


def test_plan_execute_no_approved_items(setup_test_data, tmp_path: Path):
    """Test plan-execute when there are no approved items."""
    brand_dir, product_dir, plans_dir, initial_plan = setup_test_data
    plan_id = initial_plan.id

    # Change item status to draft so no items are approved
    initial_plan.items[0].status = "draft"
    initial_plan.save(plans_dir / f"{plan_id}.json")

    result = runner.invoke(app, ["plan-execute", plan_id])

    assert result.exit_code == 1, (
        f"Expected command to fail, but exited with {result.exit_code}. Output: {result.stdout}"
    )
    assert "No hay items aprobados. Primero ejecutá: cm plan-approve" in result.stdout


def test_plan_execute_missing_brand_dir(mock_pipeline_run, setup_test_data, tmp_path: Path):
    """Test plan-execute when brand directory is missing."""
    brand_dir, product_dir, plans_dir, initial_plan = setup_test_data
    plan_id = initial_plan.id

    # Remove the temporary brand directory
    import shutil

    shutil.rmtree(brand_dir)

    result = runner.invoke(app, ["plan-execute", plan_id])

    assert result.exit_code == 1, (
        f"Expected command to fail, but exited with {result.exit_code}. Output: {result.stdout}"
    )
    assert "Directorio de marca no encontrado" in result.stdout and brand_dir.name in result.stdout
    mock_pipeline_run.assert_not_called()  # Pipeline should not run


def test_plan_execute_missing_product_dir(mock_pipeline_run, setup_test_data, tmp_path: Path):
    """Test plan-execute when product directory is missing."""
    brand_dir, product_dir, plans_dir, initial_plan = setup_test_data
    plan_id = initial_plan.id

    # Remove the temporary product directory
    import shutil

    shutil.rmtree(product_dir)

    result = runner.invoke(app, ["plan-execute", plan_id])

    assert result.exit_code == 0, (
        f"Expected command to complete (item failed), but exited with {result.exit_code}. Output: {result.stdout}"
    )
    assert "Falló la generación para el item" in result.stdout and product_dir.name in result.stdout
    mock_pipeline_run.assert_not_called()  # Pipeline should not run
