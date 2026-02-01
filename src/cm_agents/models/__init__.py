"""Modelos de datos del sistema."""

from .brand import Brand, PriceBadgeConfig, TextOverlayConfig, TitleConfig
from .generation import GenerationPrompt, GenerationResult, ReferenceAnalysis
from .product import Product

__all__ = [
    "Brand",
    "TextOverlayConfig",
    "PriceBadgeConfig",
    "TitleConfig",
    "Product",
    "ReferenceAnalysis",
    "GenerationPrompt",
    "GenerationResult",
]
