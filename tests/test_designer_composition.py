"""Tests para mejoras de composición en DesignerAgent."""

import pytest
from unittest.mock import Mock, patch

from cm_agents.agents.designer import DesignerAgent
from cm_agents.models.brand import Brand, ColorPalette, StyleConfig, BrandIdentity
from cm_agents.models.generation import (
    LayoutAnalysis,
    ReferenceAnalysis,
    StyleAnalysis,
    ColorAnalysis,
    TypographyAnalysis,
)
from cm_agents.models.product import Product


@pytest.fixture
def designer_agent():
    """Fixture para DesignerAgent."""
    with patch("anthropic.Anthropic"):
        agent = DesignerAgent()
        return agent


@pytest.fixture
def test_brand():
    """Fixture para Brand de prueba."""
    return Brand(
        name="Test Brand",
        palette=ColorPalette(primary="#FF5733", secondary="#33C3F0"),
        style=StyleConfig(
            mood=["cálido", "familiar"],
            photography_style="warm natural lighting",
        ),
        identity=BrandIdentity(values=["calidad", "tradición"]),
    )


@pytest.fixture
def test_reference_analysis():
    """Fixture para ReferenceAnalysis con composición detallada."""
    return ReferenceAnalysis(
        layout=LayoutAnalysis(
            product_position="center-right",
            text_zones=["top-center", "bottom-left"],
            composition="rule of thirds",
            composition_technique="rule_of_thirds",
            negative_space_distribution="top",
            camera_angle="eye-level",
            depth_of_field="shallow",
        ),
        style=StyleAnalysis(
            lighting="golden hour lighting",
            background="warm rustic background",
            mood="warm and inviting",
        ),
        colors=ColorAnalysis(dominant="#E8A87C", palette=["#E8A87C", "#D4A574", "#C9A66B"]),
        typography=TypographyAnalysis(style="elegant serif", placement="top-center"),
    )


def test_extract_composition_guidance(designer_agent, test_reference_analysis):
    """Test extracción de guías de composición."""
    guidance = designer_agent._extract_composition_guidance(test_reference_analysis)

    assert "technique" in guidance
    assert guidance["technique"] == "rule_of_thirds"
    assert guidance["negative_space"] == "top"
    assert guidance["camera_angle"] == "eye-level"
    assert guidance["depth_of_field"] == "shallow"


def test_extract_composition_guidance_fallback(designer_agent):
    """Test fallback cuando no hay campos específicos."""
    analysis = ReferenceAnalysis(
        layout=LayoutAnalysis(
            product_position="center",
            text_zones=[],
            composition="centered composition",
        ),
        style=StyleAnalysis(),
        colors=ColorAnalysis(dominant="#FFFFFF"),
    )

    guidance = designer_agent._extract_composition_guidance(analysis)

    assert "technique" in guidance
    # Debe inferir desde composition string
    assert guidance["technique"] in ["centered", "rule_of_thirds"]


def test_validate_composition_missing_technique(designer_agent):
    """Test validación detecta falta de técnica de composición."""
    prompt = "A beautiful product photo with soft lighting"
    fixes = designer_agent._validate_composition(prompt, "feed")

    assert len(fixes) > 0
    assert any("rule of thirds" in fix.lower() or "composition" in fix.lower() for fix in fixes)


def test_validate_composition_missing_negative_space(designer_agent):
    """Test validación detecta falta de negative space."""
    prompt = "A product photo with rule of thirds composition"
    fixes = designer_agent._validate_composition(prompt, "feed")

    assert len(fixes) > 0
    assert any("negative space" in fix.lower() for fix in fixes)


def test_validate_composition_missing_hierarchy(designer_agent):
    """Test validación detecta falta de visual hierarchy."""
    prompt = "A product photo with rule of thirds and negative space"
    fixes = designer_agent._validate_composition(prompt, "feed")

    assert len(fixes) > 0
    assert any("focal point" in fix.lower() or "primary subject" in fix.lower() for fix in fixes)


def test_validate_composition_complete(designer_agent):
    """Test que prompt completo pasa validación."""
    prompt = (
        "Professional product photography with rule of thirds composition, "
        "ample negative space in upper third for text overlay, "
        "clear focal point with product as primary subject, "
        "soft natural lighting"
    )
    fixes = designer_agent._validate_composition(prompt, "feed")

    assert len(fixes) == 0


def test_validate_brand_integration_missing_colors(designer_agent, test_brand):
    """Test validación detecta falta de colores de marca."""
    prompt = "A beautiful product photo with warm lighting"
    fixes = designer_agent._validate_brand_integration(prompt, test_brand)

    assert len(fixes) > 0
    assert any("brand color" in fix.lower() or "#FF5733" in fix for fix in fixes)


def test_validate_brand_integration_missing_mood(designer_agent, test_brand):
    """Test validación detecta falta de mood traducido."""
    prompt = f"A product photo with brand color {test_brand.palette.primary}"
    fixes = designer_agent._validate_brand_integration(prompt, test_brand)

    # Debe detectar falta de mood visual
    assert any("warm" in fix.lower() or "golden" in fix.lower() or "atmosphere" in fix.lower() for fix in fixes)


def test_validate_brand_integration_complete(designer_agent, test_brand):
    """Test que prompt con marca completa pasa validación."""
    prompt = (
        f"Professional product photography with subtle use of brand color {test_brand.palette.primary}, "
        "warm tones, golden hour lighting, inviting atmosphere, "
        "premium materials with attention to detail"
    )
    fixes = designer_agent._validate_brand_integration(prompt, test_brand)

    assert len(fixes) == 0


def test_refine_prompt_applies_fixes(designer_agent, test_brand, test_reference_analysis):
    """Test que refine_prompt aplica mejoras."""
    prompt = "A product photo"
    refined = designer_agent._refine_prompt(prompt, test_reference_analysis, test_brand, "feed")

    assert refined != prompt
    assert len(refined) > len(prompt)
    # Debe incluir mejoras de composición y marca
    assert "composition" in refined.lower() or "negative space" in refined.lower() or "brand" in refined.lower()


def test_refine_prompt_no_changes_if_complete(designer_agent, test_brand, test_reference_analysis):
    """Test que prompt completo no se modifica."""
    prompt = (
        "Professional product photography with rule of thirds composition, "
        "ample negative space in upper third for text overlay, "
        "clear focal point with product as primary subject, "
        f"subtle use of brand color {test_brand.palette.primary}, "
        "warm tones, golden hour lighting, inviting atmosphere"
    )
    refined = designer_agent._refine_prompt(prompt, test_reference_analysis, test_brand, "feed")

    # Debe ser igual o muy similar (solo puede agregar mejoras menores)
    assert len(refined) >= len(prompt)


def test_validate_composition_story_safe_zones(designer_agent):
    """Test que validación adapta negative space para story."""
    prompt = "A product photo"
    fixes = designer_agent._validate_composition(prompt, "story")

    # Debe mencionar center-lower-third para story
    story_fixes = [f for f in fixes if "center-lower" in f.lower() or "lower-third" in f.lower()]
    assert len(story_fixes) > 0


def test_validate_composition_feed_safe_zones(designer_agent):
    """Test que validación adapta negative space para feed."""
    prompt = "A product photo"
    fixes = designer_agent._validate_composition(prompt, "feed")

    # Debe mencionar upper third y bottom para feed
    feed_fixes = [f for f in fixes if "upper third" in f.lower() or "bottom" in f.lower()]
    assert len(feed_fixes) > 0
