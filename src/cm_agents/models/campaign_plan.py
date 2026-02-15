"""Modelo para planes de campaña estructurados."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from .campaign_style import CampaignStyleGuide


@dataclass
class DayPlan:
    """Plan para un día específico de la campaña."""

    day: int
    date: date | None = None
    theme: Literal[
        "teaser",
        "countdown",
        "reveal",
        "anticipation",
        "main_offer",
        "extended",
        "last_chance",
        "cyber_monday",
        "closing",
    ] = "main_offer"
    products: list[str] = field(default_factory=list)  # slugs de productos
    copy_suggestion: str = ""
    visual_direction: str = ""  # "dark, mysterious", "urgency, red accents", etc.
    urgency_level: Literal["low", "medium", "high", "critical"] = "medium"
    size: Literal["feed", "story"] = "feed"
    price_override: str | None = None  # Para ofertas especiales


@dataclass
class VisualCoherence:
    """Define la coherencia visual de toda la campaña."""

    base_style: str = "bold_contrast"  # Estilo base compartido
    color_scheme: list[str] = field(default_factory=lambda: ["#000000", "#FF0000"])
    typography_style: str = "impact, bold"
    mood_progression: list[str] = field(
        default_factory=lambda: ["mysterious", "exciting", "urgent", "celebratory"]
    )
    consistent_elements: list[str] = field(
        default_factory=lambda: ["logo_position", "price_badge_style", "brand_colors"]
    )


@dataclass
class CampaignPlan:
    """Plan completo de campaña con múltiples días."""

    name: str
    brand_slug: str
    days: list[DayPlan] = field(default_factory=list)
    visual_coherence: VisualCoherence = field(default_factory=VisualCoherence)
    style_guide: CampaignStyleGuide | None = None  # Guía de estilo detallada
    total_images: int = 0
    estimated_cost_usd: float = 0.0

    def __post_init__(self):
        self.total_images = len(self.days)
        # Estimación base (GeneratorAgent): ~$0.04 por imagen + overhead fijo.
        # Nota: otros flujos (inpainting, overlays, etc.) pueden costar más.
        self.estimated_cost_usd = (self.total_images * 0.04) + 0.015

    def get_all_products(self) -> list[str]:
        """Retorna lista única de todos los productos en la campaña."""
        products = set()
        for day in self.days:
            products.update(day.products)
        return list(products)

    def to_prompt_context(self) -> str:
        """Genera contexto para el CreativeEngine."""
        lines = [
            f"CAMPAÑA: {self.name}",
            f"MARCA: {self.brand_slug}",
            f"DÍAS: {len(self.days)}",
            "",
        ]

        # Si hay StyleGuide, usarlo; sino usar VisualCoherence básico
        if self.style_guide:
            lines.append("STYLE GUIDE (OBLIGATORIO - APLICAR A TODAS LAS IMÁGENES):")
            lines.append(self.style_guide.to_prompt_header())
        else:
            lines.extend(
                [
                    "COHERENCIA VISUAL:",
                    f"  - Estilo base: {self.visual_coherence.base_style}",
                    f"  - Colores: {', '.join(self.visual_coherence.color_scheme)}",
                    f"  - Tipografía: {self.visual_coherence.typography_style}",
                    f"  - Elementos consistentes: {', '.join(self.visual_coherence.consistent_elements)}",
                ]
            )

        lines.extend(["", "PLAN POR DÍA:"])

        for day in self.days:
            products_str = ", ".join(day.products) if day.products else "Sin producto específico"
            lines.append(f"  DÍA {day.day} ({day.theme}):")
            lines.append(f"    - Productos: {products_str}")
            lines.append(f"    - Visual: {day.visual_direction}")
            lines.append(f"    - Urgencia: {day.urgency_level}")
            lines.append(
                f"    - Copy: {day.copy_suggestion[:80]}..." if day.copy_suggestion else ""
            )

        return "\n".join(lines)

    @classmethod
    def load(cls, path: Path) -> CampaignPlan:
        """Carga un plan de campaña desde un archivo JSON."""
        from .campaign_style import CampaignStyleGuide

        with open(path) as f:
            data = json.load(f)

        # Parsear días
        days = []
        for day_data in data.get("days", []):
            day = DayPlan(
                day=day_data.get("day", 1),
                date=date.fromisoformat(day_data["date"]) if day_data.get("date") else None,
                theme=day_data.get("theme", "main_offer"),
                products=day_data.get("products", []),
                copy_suggestion=day_data.get("copy_suggestion", ""),
                visual_direction=day_data.get("visual_direction", ""),
                urgency_level=day_data.get("urgency_level", "medium"),
                size=day_data.get("size", "feed"),
                price_override=day_data.get("price_override"),
            )
            days.append(day)

        # Parsear coherencia visual
        vc_data = data.get("visual_coherence", {})
        visual_coherence = VisualCoherence(
            base_style=vc_data.get("base_style", "bold_contrast"),
            color_scheme=vc_data.get("color_scheme", ["#000000", "#FF0000"]),
            typography_style=vc_data.get("typography_style", "impact, bold"),
            mood_progression=vc_data.get("mood_progression", []),
            consistent_elements=vc_data.get("consistent_elements", []),
        )

        # Parsear StyleGuide si existe
        style_guide = None
        if "style_guide" in data and data["style_guide"]:
            style_guide = CampaignStyleGuide.from_dict(data["style_guide"])

        return cls(
            name=data.get("name", "Campaign"),
            brand_slug=data.get("brand_slug", data.get("brand", "")),
            days=days,
            visual_coherence=visual_coherence,
            style_guide=style_guide,
        )

    def save(self, path: Path) -> None:
        """Guarda el plan de campaña a un archivo JSON."""
        data = {
            "name": self.name,
            "brand_slug": self.brand_slug,
            "total_images": self.total_images,
            "estimated_cost_usd": self.estimated_cost_usd,
            "days": [
                {
                    "day": day.day,
                    "date": day.date.isoformat() if day.date else None,
                    "theme": day.theme,
                    "products": day.products,
                    "copy_suggestion": day.copy_suggestion,
                    "visual_direction": day.visual_direction,
                    "urgency_level": day.urgency_level,
                    "size": day.size,
                    "price_override": day.price_override,
                }
                for day in self.days
            ],
            "visual_coherence": {
                "base_style": self.visual_coherence.base_style,
                "color_scheme": self.visual_coherence.color_scheme,
                "typography_style": self.visual_coherence.typography_style,
                "mood_progression": self.visual_coherence.mood_progression,
                "consistent_elements": self.visual_coherence.consistent_elements,
            },
            "style_guide": self.style_guide.to_dict() if self.style_guide else None,
        }

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
