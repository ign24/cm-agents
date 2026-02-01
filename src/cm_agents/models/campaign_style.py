"""Modelo CampaignStyleGuide - Guía de estilo visual para campañas coherentes.

Define todos los elementos visuales que deben mantenerse consistentes
a lo largo de todas las imágenes de una campaña.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass
class TypographyGuide:
    """Guía de tipografía para la campaña."""

    headline_style: str = "Impact Bold, all caps"
    headline_position: str = "top-center"
    headline_color: str = "#FFFFFF"

    price_style: str = "Extra Bold, large numbers"
    price_color: str = "#FFFFFF"

    text_shadow: str = "subtle black drop shadow"
    text_effects: list[str] = field(default_factory=list)

    def to_prompt(self) -> str:
        """Genera instrucciones de tipografía para el prompt."""
        effects = f", effects: {', '.join(self.text_effects)}" if self.text_effects else ""
        return (
            f"Headline: {self.headline_style}, {self.headline_color}, "
            f"positioned {self.headline_position}, {self.text_shadow}{effects}. "
            f"Price text: {self.price_style}, {self.price_color}."
        )


@dataclass
class PriceBadgeStyle:
    """Estilo del badge de precio."""

    shape: Literal["circular", "rectangular", "pill", "starburst"] = "circular"
    bg_color: str = "#FF0000"
    text_color: str = "#FFFFFF"
    border: str | None = None
    position: str = "bottom-left"
    size: str = "medium"
    effects: list[str] = field(default_factory=list)

    def to_prompt(self) -> str:
        """Genera instrucciones del badge para el prompt."""
        border_str = f", {self.border} border" if self.border else ""
        effects_str = f", {', '.join(self.effects)}" if self.effects else ""
        return (
            f"{self.shape} price badge, {self.bg_color} background, "
            f"{self.text_color} text{border_str}, {self.size} size, "
            f"positioned {self.position}{effects_str}"
        )


@dataclass
class ProductPresentation:
    """Configuración de presentación del producto."""

    position: str = "center"
    scale: float = 0.4
    angle: str = "front-facing, slight angle"
    shadow_style: str = "soft reflection"
    highlight_style: str = "rim lighting on edges"
    surface: str = "reflective dark surface"

    def to_prompt(self) -> str:
        """Genera instrucciones de presentación del producto."""
        return (
            f"Product {self.position}, {int(self.scale * 100)}% of frame, "
            f"{self.angle}, on {self.surface}, "
            f"{self.shadow_style}, {self.highlight_style}"
        )


@dataclass
class CampaignStyleGuide:
    """Guía de estilo visual completa para toda la campaña.

    Define todos los elementos que deben mantenerse consistentes
    entre todas las imágenes de la campaña para lograr coherencia visual.
    """

    # Identificación
    name: str = "Campaign Style Guide"
    occasion: str = ""  # "black_friday", "christmas", "summer_promo", etc.

    # Estilo base (del knowledge base)
    base_style: str = "bold_contrast"
    base_style_prompt: str = ""  # Template del estilo cargado del KB

    # Paleta de colores
    color_scheme: list[str] = field(default_factory=lambda: ["#000000", "#FFD700", "#FF0000"])
    primary_color: str = "#000000"
    accent_color: str = "#FFD700"
    highlight_color: str = "#FF0000"

    # Tipografía
    typography: TypographyGuide = field(default_factory=TypographyGuide)

    # Iluminación (desde knowledge base)
    lighting_style: str = "dramatic_contrast"
    lighting_prompt: str = "dramatic lighting, high contrast, defined shadows, chiaroscuro effect"

    # Background
    background_treatment: Literal["gradient", "solid", "textured", "scene", "blurred"] = "gradient"
    background_colors: list[str] = field(default_factory=lambda: ["#1a1a1a", "#2d2d2d"])
    background_prompt: str = "dark gradient background"

    # Producto
    product: ProductPresentation = field(default_factory=ProductPresentation)

    # Elementos visuales
    visual_effects: list[str] = field(default_factory=lambda: ["subtle_lens_flare", "reflection"])
    atmosphere: str = "premium, professional"
    mood: str = "exciting, urgent"

    # Badge de precio
    price_badge: PriceBadgeStyle = field(default_factory=PriceBadgeStyle)

    # Logo
    logo_placement: str = "top-right"
    logo_size: str = "small"
    logo_style: str = "white version, subtle"

    # Restricciones
    negative_prompts: list[str] = field(
        default_factory=lambda: [
            "blurry",
            "low quality",
            "pixelated",
            "watermark",
            "text artifacts",
            "cluttered background",
            "distracting elements",
        ]
    )
    forbidden_elements: list[str] = field(
        default_factory=lambda: ["neon colors", "3d render", "cartoon style", "anime"]
    )

    # Variaciones permitidas por día
    allowed_variations: list[str] = field(
        default_factory=lambda: ["camera_angle", "props", "urgency_level", "copy_text"]
    )

    # Progresión de mood (para campañas multi-día)
    mood_progression: list[str] = field(
        default_factory=lambda: ["mysterious", "building_excitement", "peak_urgency", "last_chance"]
    )

    # Calidad técnica
    quality_tags: list[str] = field(
        default_factory=lambda: [
            "8K detail",
            "sharp focus",
            "professional product photography",
            "commercial quality",
            "high resolution",
        ]
    )

    def to_prompt_header(self) -> str:
        """Genera el header del prompt con instrucciones de estilo."""
        return f"""[CAMPAIGN STYLE GUIDE - MANDATORY FOR ALL IMAGES]
Occasion: {self.occasion}
Style: {self.base_style}

COLORS:
- Primary: {self.primary_color}
- Accent: {self.accent_color}
- Highlight: {self.highlight_color}
- Background: {" → ".join(self.background_colors)}

TYPOGRAPHY:
{self.typography.to_prompt()}

LIGHTING:
{self.lighting_prompt}

PRODUCT PRESENTATION:
{self.product.to_prompt()}

PRICE BADGE:
{self.price_badge.to_prompt()}

LOGO:
{self.logo_placement}, {self.logo_size}, {self.logo_style}

VISUAL EFFECTS:
{", ".join(self.visual_effects)}

ATMOSPHERE:
{self.atmosphere}, {self.mood}

QUALITY:
{", ".join(self.quality_tags)}

AVOID:
{", ".join(self.forbidden_elements)}
"""

    def to_negative_prompt(self) -> str:
        """Genera el negative prompt completo."""
        all_negatives = self.negative_prompts + self.forbidden_elements
        return ", ".join(all_negatives)

    def to_scene_prompt(self, day_theme: str = "", copy_text: str = "") -> str:
        """Genera un prompt de escena base usando el StyleGuide."""
        effects_str = ", ".join(self.visual_effects) if self.visual_effects else ""

        scene = f"""Professional product photography scene,
{self.background_prompt},
{self.lighting_prompt},
{self.product.surface},
{effects_str},
{self.atmosphere} atmosphere,
clear space in {self.typography.headline_position} for headline text,
{self.price_badge.to_prompt()} area reserved,
logo space {self.logo_placement},
{", ".join(self.quality_tags)}"""

        if day_theme:
            scene = f"{day_theme} theme: {scene}"

        if copy_text:
            scene += f", featuring text: '{copy_text}'"

        return scene

    def get_day_mood(self, day_index: int) -> str:
        """Obtiene el mood para un día específico de la campaña."""
        if not self.mood_progression:
            return self.mood

        idx = min(day_index, len(self.mood_progression) - 1)
        return self.mood_progression[idx]

    def to_dict(self) -> dict:
        """Serializa el StyleGuide a diccionario."""
        return {
            "name": self.name,
            "occasion": self.occasion,
            "base_style": self.base_style,
            "base_style_prompt": self.base_style_prompt,
            "color_scheme": self.color_scheme,
            "primary_color": self.primary_color,
            "accent_color": self.accent_color,
            "highlight_color": self.highlight_color,
            "typography": {
                "headline_style": self.typography.headline_style,
                "headline_position": self.typography.headline_position,
                "headline_color": self.typography.headline_color,
                "price_style": self.typography.price_style,
                "price_color": self.typography.price_color,
                "text_shadow": self.typography.text_shadow,
                "text_effects": self.typography.text_effects,
            },
            "lighting_style": self.lighting_style,
            "lighting_prompt": self.lighting_prompt,
            "background_treatment": self.background_treatment,
            "background_colors": self.background_colors,
            "background_prompt": self.background_prompt,
            "product": {
                "position": self.product.position,
                "scale": self.product.scale,
                "angle": self.product.angle,
                "shadow_style": self.product.shadow_style,
                "highlight_style": self.product.highlight_style,
                "surface": self.product.surface,
            },
            "visual_effects": self.visual_effects,
            "atmosphere": self.atmosphere,
            "mood": self.mood,
            "price_badge": {
                "shape": self.price_badge.shape,
                "bg_color": self.price_badge.bg_color,
                "text_color": self.price_badge.text_color,
                "border": self.price_badge.border,
                "position": self.price_badge.position,
                "size": self.price_badge.size,
                "effects": self.price_badge.effects,
            },
            "logo_placement": self.logo_placement,
            "logo_size": self.logo_size,
            "logo_style": self.logo_style,
            "negative_prompts": self.negative_prompts,
            "forbidden_elements": self.forbidden_elements,
            "allowed_variations": self.allowed_variations,
            "mood_progression": self.mood_progression,
            "quality_tags": self.quality_tags,
        }

    @classmethod
    def from_dict(cls, data: dict) -> CampaignStyleGuide:
        """Crea un StyleGuide desde un diccionario."""
        typography_data = data.get("typography", {})
        typography = TypographyGuide(
            headline_style=typography_data.get("headline_style", "Impact Bold, all caps"),
            headline_position=typography_data.get("headline_position", "top-center"),
            headline_color=typography_data.get("headline_color", "#FFFFFF"),
            price_style=typography_data.get("price_style", "Extra Bold, large numbers"),
            price_color=typography_data.get("price_color", "#FFFFFF"),
            text_shadow=typography_data.get("text_shadow", "subtle black drop shadow"),
            text_effects=typography_data.get("text_effects", []),
        )

        product_data = data.get("product", {})
        product = ProductPresentation(
            position=product_data.get("position", "center"),
            scale=product_data.get("scale", 0.4),
            angle=product_data.get("angle", "front-facing, slight angle"),
            shadow_style=product_data.get("shadow_style", "soft reflection"),
            highlight_style=product_data.get("highlight_style", "rim lighting on edges"),
            surface=product_data.get("surface", "reflective dark surface"),
        )

        badge_data = data.get("price_badge", {})
        price_badge = PriceBadgeStyle(
            shape=badge_data.get("shape", "circular"),
            bg_color=badge_data.get("bg_color", "#FF0000"),
            text_color=badge_data.get("text_color", "#FFFFFF"),
            border=badge_data.get("border"),
            position=badge_data.get("position", "bottom-left"),
            size=badge_data.get("size", "medium"),
            effects=badge_data.get("effects", []),
        )

        return cls(
            name=data.get("name", "Campaign Style Guide"),
            occasion=data.get("occasion", ""),
            base_style=data.get("base_style", "bold_contrast"),
            base_style_prompt=data.get("base_style_prompt", ""),
            color_scheme=data.get("color_scheme", ["#000000", "#FFD700", "#FF0000"]),
            primary_color=data.get("primary_color", "#000000"),
            accent_color=data.get("accent_color", "#FFD700"),
            highlight_color=data.get("highlight_color", "#FF0000"),
            typography=typography,
            lighting_style=data.get("lighting_style", "dramatic_contrast"),
            lighting_prompt=data.get("lighting_prompt", ""),
            background_treatment=data.get("background_treatment", "gradient"),
            background_colors=data.get("background_colors", ["#1a1a1a", "#2d2d2d"]),
            background_prompt=data.get("background_prompt", ""),
            product=product,
            visual_effects=data.get("visual_effects", []),
            atmosphere=data.get("atmosphere", "premium, professional"),
            mood=data.get("mood", "exciting"),
            price_badge=price_badge,
            logo_placement=data.get("logo_placement", "top-right"),
            logo_size=data.get("logo_size", "small"),
            logo_style=data.get("logo_style", "white version, subtle"),
            negative_prompts=data.get("negative_prompts", []),
            forbidden_elements=data.get("forbidden_elements", []),
            allowed_variations=data.get("allowed_variations", []),
            mood_progression=data.get("mood_progression", []),
            quality_tags=data.get("quality_tags", []),
        )

    def save(self, path: Path) -> None:
        """Guarda el StyleGuide a un archivo JSON."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: Path) -> CampaignStyleGuide:
        """Carga un StyleGuide desde un archivo JSON."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)


# Presets para ocasiones comunes
STYLE_PRESETS: dict[str, dict] = {
    "black_friday": {
        "occasion": "black_friday",
        "base_style": "bold_contrast",
        "color_scheme": ["#000000", "#FFD700", "#FF0000"],
        "primary_color": "#000000",
        "accent_color": "#FFD700",
        "highlight_color": "#FF0000",
        "lighting_style": "dramatic_contrast",
        "background_treatment": "gradient",
        "background_colors": ["#1a1a1a", "#2d2d2d"],
        "visual_effects": ["subtle_lens_flare", "gold_particles", "reflection"],
        "atmosphere": "premium, exclusive, urgent",
        "mood": "exciting, must-have",
        "mood_progression": [
            "mysterious_teaser",
            "building_anticipation",
            "peak_urgency",
            "last_chance",
        ],
    },
    "christmas": {
        "occasion": "christmas",
        "base_style": "lifestyle_warm",
        "color_scheme": ["#165B33", "#BB2528", "#F8B229", "#FFFFFF"],
        "primary_color": "#165B33",
        "accent_color": "#BB2528",
        "highlight_color": "#F8B229",
        "lighting_style": "golden_hour",
        "background_treatment": "scene",
        "background_colors": ["#1a1a1a", "#2d1810"],
        "visual_effects": ["warm_glow", "bokeh_lights", "snow_particles"],
        "atmosphere": "warm, festive, magical",
        "mood": "joyful, giving",
        "mood_progression": ["anticipation", "celebration", "giving_spirit", "new_year_transition"],
    },
    "summer_promo": {
        "occasion": "summer_promo",
        "base_style": "minimal_clean",
        "color_scheme": ["#00B4D8", "#FF6B35", "#FFFFFF", "#FFE66D"],
        "primary_color": "#00B4D8",
        "accent_color": "#FF6B35",
        "highlight_color": "#FFE66D",
        "lighting_style": "backlit_glow",
        "background_treatment": "gradient",
        "background_colors": ["#E0F7FA", "#B2EBF2"],
        "visual_effects": ["sun_flare", "water_droplets", "fresh_condensation"],
        "atmosphere": "fresh, refreshing, vibrant",
        "mood": "energetic, fun",
        "mood_progression": ["fresh_start", "peak_summer", "cool_refresh"],
    },
    "valentines": {
        "occasion": "valentines",
        "base_style": "editorial_magazine",
        "color_scheme": ["#FF1744", "#FF4081", "#FFFFFF", "#880E4F"],
        "primary_color": "#FF1744",
        "accent_color": "#FF4081",
        "highlight_color": "#FFFFFF",
        "lighting_style": "soft_studio",
        "background_treatment": "gradient",
        "background_colors": ["#FCE4EC", "#F8BBD9"],
        "visual_effects": ["soft_glow", "heart_bokeh", "romantic_lighting"],
        "atmosphere": "romantic, elegant, intimate",
        "mood": "loving, passionate",
        "mood_progression": ["hint_of_love", "romantic_peak", "perfect_gift"],
    },
    "cyber_monday": {
        "occasion": "cyber_monday",
        "base_style": "tech_futuristic",
        "color_scheme": ["#00E5FF", "#7C4DFF", "#000000", "#FFFFFF"],
        "primary_color": "#000000",
        "accent_color": "#00E5FF",
        "highlight_color": "#7C4DFF",
        "lighting_style": "dramatic_contrast",
        "background_treatment": "gradient",
        "background_colors": ["#0a0a0a", "#1a1a2e"],
        "visual_effects": ["neon_glow", "digital_particles", "tech_grid"],
        "atmosphere": "futuristic, digital, cutting-edge",
        "mood": "innovative, urgent",
        "mood_progression": ["tech_reveal", "digital_rush", "final_download"],
    },
}


def get_preset(occasion: str) -> CampaignStyleGuide:
    """Obtiene un preset de estilo para una ocasión."""
    if occasion in STYLE_PRESETS:
        return CampaignStyleGuide.from_dict(STYLE_PRESETS[occasion])

    # Default
    return CampaignStyleGuide(occasion=occasion)
