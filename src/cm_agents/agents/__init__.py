"""Agentes del sistema."""

from .architect import PromptArchitectAgent
from .creative_engine import CreativeEngine
from .designer import DESIGN_STYLES, DesignerAgent, DesignStyle, get_available_styles
from .extractor import ExtractorAgent
from .generator import GeneratorAgent
from .strategist import KnowledgeBase, StrategistAgent

__all__ = [
    # Agentes principales (v2.2+)
    "CreativeEngine",  # Recomendado - fusiona Extractor + Designer
    "GeneratorAgent",
    "StrategistAgent",
    "KnowledgeBase",
    # Deprecados (mantener para compatibilidad)
    "ExtractorAgent",  # Deprecated: usar CreativeEngine
    "DesignerAgent",  # Deprecated: usar CreativeEngine
    "PromptArchitectAgent",
    "DesignStyle",
    "DESIGN_STYLES",
    "get_available_styles",
]
