"""Modelos para el proceso de generación de imágenes."""

import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class LayoutAnalysis(BaseModel):
    """Análisis del layout de una imagen de referencia."""

    product_position: str = Field(..., description="Posición del producto en la imagen")
    text_zones: list[str] = Field(default_factory=list, description="Zonas disponibles para texto")
    composition: str = Field(default="", description="Técnica de composición usada")
    composition_technique: str | None = Field(
        default=None, description="Técnica específica: rule_of_thirds, golden_ratio, centered, etc."
    )
    negative_space_distribution: str | None = Field(
        default=None, description="Distribución de negative space: top, bottom, sides, balanced"
    )
    camera_angle: str | None = Field(
        default=None, description="Ángulo de cámara: eye-level, overhead, low-angle, bird-eye"
    )
    depth_of_field: str | None = Field(
        default=None, description="Profundidad de campo: shallow, deep, medium"
    )


class StyleAnalysis(BaseModel):
    """Análisis del estilo visual de una imagen."""

    lighting: str = Field(default="", description="Descripción de la iluminación")
    background: str = Field(default="", description="Descripción del fondo")
    mood: str = Field(default="", description="Mood/sensación de la imagen")


class ColorAnalysis(BaseModel):
    """Análisis de colores de una imagen."""

    dominant: str = Field(..., pattern=r"^#[0-9A-Fa-f]{6}$", description="Color dominante")
    accent: str | None = Field(default=None, description="Color de acento")
    palette: list[str] = Field(default_factory=list, description="Paleta completa de colores")


class TypographyAnalysis(BaseModel):
    """Análisis de tipografía en una imagen."""

    style: str = Field(default="", description="Estilo tipográfico detectado")
    placement: str = Field(default="", description="Ubicación del texto en la imagen")


class ProductVisualAnalysis(BaseModel):
    """Análisis visual HIPER-DETALLADO del producto real para réplica exacta."""

    # Campos nuevos para réplica exacta
    brand_name: str = Field(default="", description="Marca exacta del producto")
    product_type: str = Field(default="", description="Tipo de envase (botella PET, lata, etc)")
    exact_shape: str = Field(default="", description="Forma/silueta exacta del producto")
    label_design: str = Field(default="", description="Diseño detallado de la etiqueta")
    material_finish: str = Field(default="", description="Material y acabado")
    cap_description: str = Field(default="", description="Descripción de la tapa")
    liquid_visible: str = Field(default="", description="Líquido visible (color, transparencia)")
    unique_features: list[str] = Field(
        default_factory=list, description="Detalles únicos identificadores"
    )
    full_description: str = Field(default="", description="Párrafo completo para réplica exacta")

    # Campos legacy (compatibilidad)
    description: str = Field(default="", description="Descripción visual detallada del producto")
    key_features: list[str] = Field(default_factory=list, description="Características distintivas")
    colors: list[str] = Field(default_factory=list, description="Colores del producto en HEX")

    def get_exact_description(self) -> str:
        """Retorna la descripción más completa disponible para réplica exacta."""
        if self.full_description:
            return self.full_description

        parts = []
        if self.brand_name:
            parts.append(f"Brand: {self.brand_name}")
        if self.product_type:
            parts.append(f"Type: {self.product_type}")
        if self.exact_shape:
            parts.append(f"Shape: {self.exact_shape}")
        if self.label_design:
            parts.append(f"Label: {self.label_design}")
        if self.material_finish:
            parts.append(f"Material: {self.material_finish}")
        if self.cap_description:
            parts.append(f"Cap: {self.cap_description}")
        if self.liquid_visible:
            parts.append(f"Liquid: {self.liquid_visible}")
        if self.unique_features:
            parts.append(f"Unique features: {', '.join(self.unique_features)}")

        if parts:
            return ". ".join(parts)
        return self.description


class ReferenceAnalysis(BaseModel):
    """Análisis completo de una imagen de referencia visual."""

    layout: LayoutAnalysis = Field(..., description="Análisis del layout")
    style: StyleAnalysis = Field(..., description="Análisis del estilo")
    colors: ColorAnalysis = Field(..., description="Análisis de colores")
    typography: TypographyAnalysis = Field(
        default_factory=TypographyAnalysis, description="Análisis tipográfico"
    )
    product_visual: ProductVisualAnalysis | None = Field(
        default=None, description="Análisis visual del producto real (si se proporcionó)"
    )
    what_makes_it_work: str = Field(
        default="", description="Explicación de por qué funciona el diseño"
    )

    def to_prompt_context(self) -> str:
        """Convierte el análisis a contexto para el CreativeEngine."""
        composition_details = []
        if self.layout.composition_technique:
            composition_details.append(f"technique: {self.layout.composition_technique}")
        if self.layout.negative_space_distribution:
            composition_details.append(f"negative space: {self.layout.negative_space_distribution}")
        if self.layout.camera_angle:
            composition_details.append(f"camera angle: {self.layout.camera_angle}")
        if self.layout.depth_of_field:
            composition_details.append(f"depth of field: {self.layout.depth_of_field}")

        composition_str = f", {', '.join(composition_details)}" if composition_details else ""

        return f"""
Layout: {self.layout.product_position}, composición {self.layout.composition}{composition_str}
Text zones: {", ".join(self.layout.text_zones)}
Lighting: {self.style.lighting}
Background: {self.style.background}
Mood: {self.style.mood}
Colors: dominant {self.colors.dominant}, palette {", ".join(self.colors.palette)}
Typography: {self.typography.style}, placed at {self.typography.placement}
Key insight: {self.what_makes_it_work}

NOTA: La imagen del producto real se pasa directamente como referencia visual al generador.
"""


class GenerationParams(BaseModel):
    """Parámetros para la generación de imagen."""

    aspect_ratio: Literal["1:1", "4:5", "9:16", "16:9"] = Field(
        default="4:5", description="Aspect ratio de la imagen"
    )
    quality: Literal["low", "medium", "high", "auto"] = Field(
        default="high", description="Calidad de generación"
    )
    size: str = Field(default="1080x1350", description="Tamaño en pixels")


class GenerationPrompt(BaseModel):
    """Prompt generado por el CreativeEngine."""

    prompt: str = Field(..., description="Prompt principal para el modelo de imagen")
    visual_description: str = Field(
        default="", description="Descripción visual detallada del producto"
    )
    negative_prompt: str = Field(
        default="blurry, low quality, text, watermark, logo",
        description="Lo que debe evitar el modelo",
    )
    params: GenerationParams = Field(default_factory=GenerationParams)

    def get_full_prompt(self) -> str:
        """Combina prompt principal con descripción visual."""
        parts = []
        if self.visual_description:
            parts.append(f"Product: {self.visual_description}")
        parts.append(self.prompt)
        return "\n\n".join(parts)


class GenerationResult(BaseModel):
    """Resultado de una generación de imagen."""

    id: str = Field(..., description="ID único de la generación")
    image_path: Path = Field(..., description="Path a la imagen generada")
    prompt_used: str = Field(..., description="Prompt que se usó")
    reference_path: Path | None = Field(default=None, description="Path a la imagen de referencia")
    brand_name: str = Field(..., description="Nombre de la marca")
    product_name: str = Field(..., description="Nombre del producto")
    variant_number: int = Field(default=1, description="Número de variante")
    timestamp: datetime = Field(default_factory=datetime.now)
    cost_usd: float = Field(default=0.0, description="Costo estimado en USD")
    has_text_overlay: bool = Field(default=False, description="Si tiene texto superpuesto")

    def save_metadata(self) -> None:
        """Guarda los metadatos junto a la imagen."""
        meta_path = self.image_path.with_suffix(".json")
        with open(meta_path, "w", encoding="utf-8") as f:
            data = self.model_dump()
            data["image_path"] = str(data["image_path"])
            data["reference_path"] = str(data["reference_path"]) if data["reference_path"] else None
            data["timestamp"] = data["timestamp"].isoformat()
            json.dump(data, f, indent=2, ensure_ascii=False)
