"""Agente 2: Prompt Architect - Construye prompts optimizados para generación."""

import json

import anthropic
from rich.console import Console

from ..models.brand import Brand
from ..models.generation import GenerationParams, GenerationPrompt, ReferenceAnalysis
from ..models.product import Product
from .base import BaseAgent

console = Console()

ARCHITECT_SYSTEM_PROMPT = """Sos un experto en prompt engineering para modelos de generación de imágenes, especializado en GPT-5.2 y contenido para redes sociales.

## Tu conocimiento incluye:

### Best Practices Diseño 2026:
- Tamaño óptimo feed IG: 1080x1350 (4:5)
- Tamaño stories: 1080x1920 (9:16)
- Safe zones: evitar 250px arriba y 340px abajo en stories
- Tendencias: tactile craft, warm tones, imperfect aesthetics, elemental folk
- Texto: máximo 20% del área de imagen
- Rule of thirds para composición
- Shallow depth of field para productos

### Prompt Engineering para GPT Image:
- Usar lenguaje descriptivo y específico
- Incluir: lighting, mood, composition, camera angle, textures
- Describir el producto con máximo detalle visual
- Especificar dónde dejar espacio para texto overlay
- Quality tags: "professional product photography", "commercial quality", "8K detail", "sharp focus"

### Cómo integrar marca + referencia:
- Priorizar mood/estilo de la referencia de Pinterest
- Usar colores de la marca en elementos secundarios (props, fondo)
- Describir el producto fielmente (será generado por IA, no insertado)
- Adaptar text placement a zonas libres identificadas

## Tu tarea:
Dado:
1. Análisis de una imagen de Pinterest (referencia de estilo)
2. Configuración de una marca (colores, mood, estilo)
3. Información del producto (nombre, descripción, descripción visual)
4. Tamaño objetivo (feed 4:5 o story 9:16)

Generá un prompt optimizado para GPT-5.2 que:
- Replique el estilo/mood de la referencia
- Use los colores de la marca donde corresponda
- Describa el producto con suficiente detalle para generarlo fielmente
- Deje espacio para texto en las zonas correctas
- Siga best practices de composición 2026

## Formato de respuesta (JSON):
{
  "prompt": "prompt principal completo para el modelo de imagen",
  "visual_description": "descripción visual detallada del producto específico",
  "negative_prompt": "qué evitar en la generación",
  "params": {
    "aspect_ratio": "4:5 o 9:16",
    "quality": "high",
    "size": "1080x1350 o 1080x1920"
  }
}

## Notas:
- El prompt debe ser en inglés (mejor rendimiento con modelos)
- Sé muy descriptivo sobre el producto ya que será generado, no insertado
- Incluí detalles de textura, color exacto, forma, proporciones
- Mencioná explícitamente las zonas para texto overlay
"""


class PromptArchitectAgent(BaseAgent):
    """Agente que construye prompts optimizados combinando referencia + marca + producto."""

    def __init__(self):
        super().__init__()
        self.client = anthropic.Anthropic(api_key=self._get_env("ANTHROPIC_API_KEY"))
        self.model = "claude-sonnet-4-20250514"

    def _validate_env(self) -> None:
        """Valida que ANTHROPIC_API_KEY esté configurada."""
        if not self._get_env("ANTHROPIC_API_KEY"):
            raise ValueError("ANTHROPIC_API_KEY no configurada")

    @property
    def name(self) -> str:
        return "Prompt Architect"

    @property
    def description(self) -> str:
        return "Construye prompts optimizados para generación de imágenes"

    def build_prompt(
        self,
        reference_analysis: ReferenceAnalysis,
        brand: Brand,
        product: Product,
        target_size: str = "feed",
    ) -> GenerationPrompt:
        """
        Construye un prompt optimizado para generación de imagen.

        Args:
            reference_analysis: Análisis de la imagen de Pinterest
            brand: Configuración de la marca
            product: Información del producto
            target_size: "feed" (4:5) o "story" (9:16)

        Returns:
            GenerationPrompt con el prompt optimizado
        """
        console.print(f"[blue][Escribir] {self.name}:[/blue] Construyendo prompt...")

        # Preparar contexto para el LLM
        context = f"""
## Análisis de referencia (Pinterest):
{reference_analysis.to_prompt_context()}

## Configuración de marca:
- Nombre: {brand.name}
- Colores: primary {brand.palette.primary}, secondary {brand.palette.secondary}
- Mood de marca: {brand.get_mood_string()}
- Estilo fotografía: {brand.style.photography_style}
- Fondos preferidos: {brand.get_backgrounds_string()}

## Producto:
- Nombre: {product.name}
- Descripción: {product.description}
- Descripción visual existente: {product.visual_description if product.has_visual_description() else "No disponible - deberás inferir del nombre y descripción"}
- Precio: {product.price}
- Categoría: {product.category}

## Tamaño objetivo: {"Feed Instagram (4:5, 1080x1350)" if target_size == "feed" else "Story Instagram (9:16, 1080x1920)"}

## Configuración de texto overlay:
- Precio: {brand.text_overlay.price_badge.position}
- Título: {brand.text_overlay.title.position}

Generá el prompt optimizado en formato JSON.
"""

        # Llamar a Claude
        message = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=ARCHITECT_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": context,
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

        # Construir GenerationPrompt
        params_data = data.get("params", {})
        params = GenerationParams(
            aspect_ratio=params_data.get(
                "aspect_ratio", "4:5" if target_size == "feed" else "9:16"
            ),
            quality=params_data.get("quality", "high"),
            size=params_data.get("size", "1080x1350" if target_size == "feed" else "1080x1920"),
        )

        generation_prompt = GenerationPrompt(
            prompt=data.get("prompt", ""),
            visual_description=data.get("visual_description", ""),
            negative_prompt=data.get("negative_prompt", "blurry, low quality, text, watermark"),
            params=params,
        )

        console.print(
            f"[green][OK][/green] Prompt generado ({len(generation_prompt.prompt)} chars)"
        )
        console.print(f"[dim]   Aspect ratio: {params.aspect_ratio}[/dim]")

        return generation_prompt

    def build_prompts_batch(
        self,
        reference_analyses: list[ReferenceAnalysis],
        brand: Brand,
        product: Product,
        target_size: str = "feed",
    ) -> list[GenerationPrompt]:
        """
        Construye múltiples prompts para diferentes referencias.

        Args:
            reference_analyses: Lista de análisis de referencias
            brand: Configuración de la marca
            product: Información del producto
            target_size: "feed" o "story"

        Returns:
            Lista de GenerationPrompt
        """
        results = []
        for i, analysis in enumerate(reference_analyses, 1):
            console.print(f"\n[dim]Prompt {i}/{len(reference_analyses)}[/dim]")
            results.append(self.build_prompt(analysis, brand, product, target_size))
        return results
