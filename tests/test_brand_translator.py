"""Tests para BrandTranslator."""

import pytest

from cm_agents.agents.brand_translator import BrandTranslator
from cm_agents.models.brand import Brand, BrandIdentity, ColorPalette, StyleConfig


@pytest.fixture
def translator():
    """Fixture para BrandTranslator."""
    return BrandTranslator()


@pytest.fixture
def test_brand():
    """Fixture para Brand de prueba."""
    return Brand(
        name="Test Brand",
        palette=ColorPalette(primary="#FF0000", secondary="#00FF00"),
        style=StyleConfig(
            mood=["cálido", "familiar"],
            photography_style="warm natural lighting",
            preferred_backgrounds=["rustic wooden table", "warm restaurant ambiance"],
        ),
        identity=BrandIdentity(
            values=["calidad", "tradición"],
            voice=["familiar", "cercano"],
        ),
    )


def test_mood_to_visual(translator):
    """Test traducción de mood a keywords visuales."""
    mood = ["cálido", "familiar"]
    result = translator.mood_to_visual(mood)

    assert "cálido" in result
    assert "familiar" in result
    assert len(result["cálido"]) > 0
    assert len(result["familiar"]) > 0
    assert "warm tones" in result["cálido"]
    assert "homey setting" in result["familiar"]


def test_mood_to_visual_unknown(translator):
    """Test mood desconocido genera fallback."""
    mood = ["mood_desconocido"]
    result = translator.mood_to_visual(mood)

    assert "mood_desconocido" in result
    assert len(result["mood_desconocido"]) > 0


def test_values_to_visual(translator):
    """Test traducción de values a elementos visuales."""
    values = ["calidad", "tradición"]
    result = translator.values_to_visual(values)

    assert len(result) > 0
    assert any("premium" in kw.lower() or "quality" in kw.lower() for kw in result)
    assert any("classic" in kw.lower() or "timeless" in kw.lower() for kw in result)


def test_values_to_visual_unknown(translator):
    """Test values desconocidos generan fallback."""
    values = ["value_desconocido"]
    result = translator.values_to_visual(values)

    assert len(result) > 0
    assert "value_desconocido" in result[0].lower() or "reflected" in result[0].lower()


def test_build_brand_context(translator, test_brand):
    """Test construcción de contexto visual completo."""
    context = translator.build_brand_context(test_brand)

    assert isinstance(context, str)
    assert len(context) > 0
    # Debe incluir mood traducido
    assert "warm" in context.lower() or "golden" in context.lower()
    # Debe incluir colores
    assert "#FF0000" in context or "FF0000" in context
    # Debe incluir photography style
    assert "warm natural lighting" in context.lower()


def test_build_brand_context_minimal_brand(translator):
    """Test con marca mínima (sin mood ni values)."""
    minimal_brand = Brand(
        name="Minimal Brand",
        palette=ColorPalette(primary="#000000", secondary="#FFFFFF"),
    )
    context = translator.build_brand_context(minimal_brand)

    assert isinstance(context, str)
    # Debe incluir al menos colores
    assert "#000000" in context or "000000" in context


def test_get_mood_keywords_flat(translator):
    """Test obtención de keywords planos."""
    mood = ["cálido", "premium"]
    keywords = translator.get_mood_keywords_flat(mood)

    assert isinstance(keywords, list)
    assert len(keywords) > 0
    assert "warm tones" in keywords or "golden hour" in keywords
    # Verificar que tiene keywords de premium (luxury o elegant)
    assert any("luxury" in kw.lower() or "elegant" in kw.lower() or "refined" in kw.lower() for kw in keywords)


def test_brand_context_includes_avoid(translator):
    """Test que contexto incluye elementos a evitar."""
    brand = Brand(
        name="Test",
        palette=ColorPalette(primary="#FF0000", secondary="#00FF00"),
        style=StyleConfig(avoid=["cold colors", "clinical look"]),
    )
    context = translator.build_brand_context(brand)

    assert "avoid" in context.lower() or "cold" in context.lower()


def test_brand_context_includes_preferred_backgrounds(translator, test_brand):
    """Test que contexto incluye fondos preferidos."""
    context = translator.build_brand_context(test_brand)

    assert "rustic" in context.lower() or "wooden" in context.lower()


def test_mood_keywords_no_duplicates(translator):
    """Test que get_mood_keywords_flat no tiene duplicados."""
    mood = ["cálido", "cálido"]  # Duplicado intencional
    keywords = translator.get_mood_keywords_flat(mood)

    assert len(keywords) == len(set(keywords))  # Sin duplicados
