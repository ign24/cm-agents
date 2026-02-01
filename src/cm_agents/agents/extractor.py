"""Agente 1: Extractor - Analiza imágenes de referencia con Claude Vision.

.. deprecated:: 2.2.0
    Este agente está deprecado. Usar CreativeEngine en su lugar,
    que fusiona Extractor + Designer en un solo agente optimizado.
"""

import json
import warnings
from pathlib import Path

import anthropic
from rich.console import Console

from ..models.generation import (
    ColorAnalysis,
    LayoutAnalysis,
    ReferenceAnalysis,
    StyleAnalysis,
    TypographyAnalysis,
)
from .base import BaseAgent, get_image_media_type, load_image_as_base64

console = Console()

EXTRACTOR_SYSTEM_PROMPT = """Sos un experto en diseño gráfico y redes sociales con 10+ años de experiencia.

Tu tarea es analizar imágenes de Pinterest y extraer los elementos de diseño que las hacen efectivas para redes sociales, especialmente Instagram.

## Tu expertise incluye:
- Composición visual y regla de tercios
- Teoría del color y paletas efectivas
- Tipografía para redes sociales
- Fotografía de productos
- Tendencias de diseño 2026

## Respondé SIEMPRE en JSON con esta estructura exacta:
{
  "layout": {
    "product_position": "descripción de dónde está el producto principal",
    "text_zones": ["lista de zonas libres para poner texto"],
    "composition": "técnica de composición usada (rule of thirds, centered, etc)",
    "composition_technique": "técnica específica: rule_of_thirds, golden_ratio, centered, o null si no es claro",
    "negative_space_distribution": "distribución de espacio vacío: top, bottom, sides, balanced, o null",
    "camera_angle": "ángulo de cámara: eye-level, overhead, low-angle, bird-eye, o null",
    "depth_of_field": "profundidad de campo: shallow, deep, medium, o null"
  },
  "style": {
    "lighting": "descripción detallada de la iluminación",
    "background": "descripción del fondo y elementos secundarios",
    "mood": "sensación/emoción que transmite la imagen"
  },
  "colors": {
    "dominant": "#HEX del color dominante",
    "accent": "#HEX del color de acento (o null si no hay)",
    "palette": ["lista completa de colores en HEX"]
  },
  "typography": {
    "style": "descripción del estilo tipográfico si hay texto visible",
    "placement": "dónde está ubicado el texto en la imagen"
  },
  "what_makes_it_work": "1-2 oraciones explicando qué hace que este diseño sea efectivo"
}

## Notas importantes:
- Los colores DEBEN estar en formato #RRGGBB
- Sé específico en las descripciones para que puedan ser usadas en prompts de generación
- Si no hay texto visible, indicalo en typography.style como "no visible text"
- Enfocate en elementos que se puedan replicar con IA generativa
"""

DUAL_EXTRACTOR_SYSTEM_PROMPT = """Sos un experto en diseño gráfico y fotografía de productos con 15+ años de experiencia.

Te voy a dar DOS imágenes:
1. IMAGEN DE ESTILO: Una referencia de Pinterest con el estilo visual que queremos replicar
2. IMAGEN DE PRODUCTO: El producto real (la imagen se usará directamente como referencia visual)

Tu tarea es SOLO analizar la IMAGEN DE ESTILO para extraer:
- Layout y composición
- Iluminación y mood
- Colores y paleta
- Tipografía (si hay texto visible)

NOTA: No necesitás describir el producto - la imagen del producto se pasará directamente al generador como referencia visual.

## Respondé SIEMPRE en JSON con esta estructura exacta:
{
  "layout": {
    "product_position": "descripción de dónde posicionar el producto (basado en la referencia de estilo)",
    "text_zones": ["lista de zonas libres para poner texto"],
    "composition": "técnica de composición usada en la referencia de estilo",
    "composition_technique": "técnica específica: rule_of_thirds, golden_ratio, centered, o null si no es claro",
    "negative_space_distribution": "distribución de espacio vacío: top, bottom, sides, balanced, o null",
    "camera_angle": "ángulo de cámara: eye-level, overhead, low-angle, bird-eye, o null",
    "depth_of_field": "profundidad de campo: shallow, deep, medium, o null"
  },
  "style": {
    "lighting": "descripción detallada de la iluminación de la referencia de estilo",
    "background": "descripción del fondo y elementos secundarios de la referencia",
    "mood": "sensación/emoción que transmite la referencia de estilo"
  },
  "colors": {
    "dominant": "#HEX del color dominante de la referencia de estilo",
    "accent": "#HEX del color de acento (o null si no hay)",
    "palette": ["lista completa de colores en HEX de la referencia"]
  },
  "typography": {
    "style": "descripción del estilo tipográfico si hay texto visible en la referencia",
    "placement": "dónde está ubicado el texto en la referencia"
  },
  "what_makes_it_work": "1-2 oraciones explicando qué hace que el estilo de la referencia sea efectivo"
}

## Notas:
- Los colores DEBEN estar en formato #RRGGBB
- Enfocate SOLO en el estilo visual de la referencia de Pinterest
- NO describas el producto - su imagen se usa directamente como referencia
"""


class ExtractorAgent(BaseAgent):
    """Agente que analiza imágenes de referencia usando Claude Vision.

    .. deprecated:: 2.2.0
        Usar CreativeEngine en su lugar.
    """

    def __init__(self):
        warnings.warn(
            "ExtractorAgent is deprecated. Use CreativeEngine instead, "
            "which combines Extractor + Designer in a single optimized agent.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__()
        self.client = anthropic.Anthropic(api_key=self._get_env("ANTHROPIC_API_KEY"))
        self.model = "claude-sonnet-4-20250514"

    def _validate_env(self) -> None:
        """Valida que ANTHROPIC_API_KEY esté configurada."""
        if not self._get_env("ANTHROPIC_API_KEY"):
            raise ValueError("ANTHROPIC_API_KEY no configurada")

    @property
    def name(self) -> str:
        return "Extractor"

    @property
    def description(self) -> str:
        return "Analiza imágenes de Pinterest y extrae elementos de diseño"

    def analyze(self, image_path: Path) -> ReferenceAnalysis:
        """
        Analiza una imagen de referencia y extrae sus elementos de diseño.

        Args:
            image_path: Path a la imagen de referencia

        Returns:
            ReferenceAnalysis con el análisis completo
        """
        if not image_path.exists():
            raise FileNotFoundError(f"Imagen no encontrada: {image_path}")

        console.print(f"[blue][Analisis] {self.name}:[/blue] Analizando {image_path.name}...")

        # Cargar imagen
        image_data = load_image_as_base64(image_path)
        media_type = get_image_media_type(image_path)

        # Llamar a Claude Vision
        message = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=EXTRACTOR_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": "Analizá esta imagen de Pinterest y extraé los elementos de diseño en formato JSON.",
                        },
                    ],
                }
            ],
        )

        # Parsear respuesta
        response_text = message.content[0].text

        # Extraer JSON de la respuesta
        try:
            # Intentar parsear directamente
            data = json.loads(response_text)
        except json.JSONDecodeError:
            # Buscar JSON en la respuesta
            import re

            json_match = re.search(r"\{[\s\S]*\}", response_text)
            if json_match:
                data = json.loads(json_match.group())
            else:
                raise ValueError(f"No se pudo parsear la respuesta: {response_text}")

        # Construir ReferenceAnalysis
        analysis = ReferenceAnalysis(
            layout=LayoutAnalysis(**data.get("layout", {})),
            style=StyleAnalysis(**data.get("style", {})),
            colors=ColorAnalysis(**data.get("colors", {"dominant": "#FFFFFF"})),
            typography=TypographyAnalysis(**data.get("typography", {})),
            what_makes_it_work=data.get("what_makes_it_work", ""),
        )

        console.print(f"[green][OK][/green] Layout: {analysis.layout.product_position}")
        if analysis.layout.composition_technique:
            console.print(f"[dim]   Composición: {analysis.layout.composition_technique}[/dim]")
        if analysis.layout.negative_space_distribution:
            console.print(f"[dim]   Negative space: {analysis.layout.negative_space_distribution}[/dim]")
        if analysis.layout.camera_angle:
            console.print(f"[dim]   Ángulo: {analysis.layout.camera_angle}[/dim]")
        console.print(f"[green][OK][/green] Mood: {analysis.style.mood}")
        console.print(f"[green][OK][/green] Colores: {', '.join(analysis.colors.palette[:3])}")

        return analysis

    def analyze_dual(self, style_ref_path: Path, product_ref_path: Path) -> ReferenceAnalysis:
        """
        Analiza DOS imágenes: una de estilo y otra del producto real.

        Args:
            style_ref_path: Path a la imagen de referencia de ESTILO (Pinterest)
            product_ref_path: Path a la imagen del PRODUCTO real

        Returns:
            ReferenceAnalysis combinando estilo de la primera + producto de la segunda
        """
        if not style_ref_path.exists():
            raise FileNotFoundError(f"Imagen de estilo no encontrada: {style_ref_path}")
        if not product_ref_path.exists():
            raise FileNotFoundError(f"Imagen de producto no encontrada: {product_ref_path}")

        console.print(
            f"[blue][Analisis] {self.name}:[/blue] Analizando estilo de {style_ref_path.name} "
            f"+ producto de {product_ref_path.name}..."
        )

        # Cargar ambas imágenes
        style_data = load_image_as_base64(style_ref_path)
        style_media = get_image_media_type(style_ref_path)

        product_data = load_image_as_base64(product_ref_path)
        product_media = get_image_media_type(product_ref_path)

        # Llamar a Claude Vision con ambas imágenes
        message = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=DUAL_EXTRACTOR_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "IMAGEN 1 - REFERENCIA DE ESTILO (Pinterest):",
                        },
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": style_media,
                                "data": style_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": "IMAGEN 2 - PRODUCTO REAL:",
                        },
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": product_media,
                                "data": product_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": "Analizá la IMAGEN 1 (estilo) y extraé layout, iluminación, colores, mood y tipografía. La imagen 2 es solo para que veas el producto - NO la describas, se usará directamente como referencia. Respondé en JSON.",
                        },
                    ],
                }
            ],
        )

        # Parsear respuesta
        response_text = message.content[0].text

        try:
            data = json.loads(response_text)
        except json.JSONDecodeError:
            import re

            json_match = re.search(r"\{[\s\S]*\}", response_text)
            if json_match:
                data = json.loads(json_match.group())
            else:
                raise ValueError(f"No se pudo parsear la respuesta: {response_text}")

        # Construir ReferenceAnalysis (sin product_visual - la imagen se usa directamente)
        analysis = ReferenceAnalysis(
            layout=LayoutAnalysis(**data.get("layout", {})),
            style=StyleAnalysis(**data.get("style", {})),
            colors=ColorAnalysis(**data.get("colors", {"dominant": "#FFFFFF"})),
            typography=TypographyAnalysis(**data.get("typography", {})),
            product_visual=None,  # No se usa - la imagen es la referencia
            what_makes_it_work=data.get("what_makes_it_work", ""),
        )

        console.print(f"[green][OK][/green] Layout: {analysis.layout.product_position}")
        if analysis.layout.composition_technique:
            console.print(f"[dim]   Composición: {analysis.layout.composition_technique}[/dim]")
        if analysis.layout.negative_space_distribution:
            console.print(f"[dim]   Negative space: {analysis.layout.negative_space_distribution}[/dim]")
        if analysis.layout.camera_angle:
            console.print(f"[dim]   Ángulo: {analysis.layout.camera_angle}[/dim]")
        console.print(f"[green][OK][/green] Mood: {analysis.style.mood}")
        console.print(f"[green][OK][/green] Colores: {', '.join(analysis.colors.palette[:3])}")

        return analysis

    def analyze_batch(self, image_paths: list[Path]) -> list[ReferenceAnalysis]:
        """
        Analiza múltiples imágenes de referencia.

        Args:
            image_paths: Lista de paths a imágenes

        Returns:
            Lista de ReferenceAnalysis
        """
        results = []
        for i, path in enumerate(image_paths, 1):
            console.print(f"\n[dim]Referencia {i}/{len(image_paths)}[/dim]")
            results.append(self.analyze(path))
        return results
