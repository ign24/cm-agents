"""CreativeEngine - Agente unificado que analiza referencias y genera prompts para campañas.

Fusiona la funcionalidad de ExtractorAgent + DesignerAgent en un solo agente
optimizado para generar múltiples prompts coherentes en una sola llamada.
"""

import json
from pathlib import Path

import anthropic
from rich.console import Console

from ..models.brand import Brand
from ..models.campaign_plan import CampaignPlan
from ..models.generation import GenerationParams, GenerationPrompt
from ..models.product import Product
from .base import BaseAgent, get_image_media_type, load_image_as_base64

console = Console()

CREATIVE_ENGINE_SYSTEM_PROMPT = """Sos un director creativo experto en campañas de redes sociales con 15+ años de experiencia.

## Tu Rol
Analizás imágenes de referencia y generás MÚLTIPLES prompts coherentes para una campaña completa.
Todo en UNA sola respuesta - eficiencia máxima.

## Proceso
1. ANALIZAR las imágenes de referencia (estilo, composición, iluminación, colores)
2. ENTENDER el plan de campaña (días, temas, progresión)
3. GENERAR N prompts que:
   - Mantengan coherencia visual entre sí
   - Varíen según el tema de cada día
   - Apliquen la progresión de urgencia/mood
   - Incluyan texto integrado (nombre producto, precio)

## Reglas Críticas
- Los prompts DEBEN estar en INGLÉS (mejor rendimiento con modelos de imagen)
- Cada prompt debe replicar el producto EXACTAMENTE (la imagen del producto se pasa como referencia)
- El texto (precio, nombre) se genera DENTRO de la imagen, no como overlay
- Mantener elementos consistentes: posición del logo, estilo de badge de precio, colores de marca

## Output Format (JSON estricto)
{
  "reference_analysis": {
    "style": "descripción del estilo visual de las referencias",
    "lighting": "tipo de iluminación detectada",
    "composition": "técnica de composición",
    "colors": ["#HEX1", "#HEX2", ...],
    "mood": "mood/atmósfera general"
  },
  "prompts": [
    {
      "day": 1,
      "theme": "teaser",
      "prompt": "El prompt completo en inglés...",
      "negative_prompt": "Elementos a evitar...",
      "visual_notes": "Notas sobre variaciones específicas de este día"
    },
    ...
  ],
  "coherence_strategy": "Breve explicación de cómo se mantiene la coherencia visual"
}

## Tips para Prompts de Imagen AI
- Estructura: ESCENA + PRODUCTO + ILUMINACIÓN + COMPOSICIÓN + TEXTO INTEGRADO + CALIDAD
- Quality tags: "professional product photography", "8K detail", "sharp focus"
- Evitar: "AI generated", "digital art", "render" (queremos fotorrealismo)
- El producto se copia de la imagen de referencia - enfocate en el CONTEXTO y ESTILO
"""


class CreativeEngine(BaseAgent):
    """Motor creativo unificado - analiza y genera prompts en una sola llamada."""

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        super().__init__()
        self.client = anthropic.Anthropic(api_key=self._get_env("ANTHROPIC_API_KEY"))
        self.model = model
        self.temperature = 0  # Determinístico

    def _validate_env(self) -> None:
        """Valida que ANTHROPIC_API_KEY esté configurada."""
        if not self._get_env("ANTHROPIC_API_KEY"):
            raise ValueError("ANTHROPIC_API_KEY no configurada")

    @property
    def name(self) -> str:
        return "CreativeEngine"

    @property
    def description(self) -> str:
        return "Motor creativo unificado - analiza refs y genera N prompts en 1 llamada"

    def create_campaign_prompts(
        self,
        campaign_plan: CampaignPlan,
        style_references: list[Path],
        product_references: dict[str, Path],  # {product_slug: photo_path}
        brand: Brand,
        products: dict[str, Product],  # {product_slug: Product}
    ) -> list[GenerationPrompt]:
        """
        Genera todos los prompts para una campaña en una sola llamada.

        Args:
            campaign_plan: Plan de campaña con días y temas
            style_references: Imágenes de referencia de estilo (inspiración visual)
            product_references: Dict de slug -> path a foto del producto
            brand: Configuración de la marca
            products: Dict de slug -> Product

        Returns:
            Lista de GenerationPrompt, uno por cada día de la campaña
        """
        console.print(
            f"\n[blue][{self.name}][/blue] Generando {len(campaign_plan.days)} prompts para campaña '{campaign_plan.name}'..."
        )

        # Obtener StyleGuide si existe
        style_guide = campaign_plan.style_guide

        # Construir contenido multimodal
        content_parts = []

        # Texto de contexto - incluir StyleGuide si existe
        style_guide_section = ""
        if style_guide:
            style_guide_section = f"""
## STYLE GUIDE (MANDATORY - Apply to ALL images)
{style_guide.to_prompt_header()}

NEGATIVE PROMPTS (avoid these):
{style_guide.to_negative_prompt()}
"""
            console.print(f"[blue][StyleGuide][/blue] Aplicando {style_guide.name} a prompts")

        context = f"""## CAMPAÑA
{campaign_plan.to_prompt_context()}
{style_guide_section}

## MARCA
- Nombre: {brand.name}
- Industria: {brand.industry}
- Colores: primary={brand.palette.primary}, secondary={brand.palette.secondary}, accent={brand.palette.accent}
- Mood: {brand.get_mood_string()}
- Posición precio badge: {brand.text_overlay.price_badge.position}
- Color badge: bg={brand.text_overlay.price_badge.bg_color}, text={brand.text_overlay.price_badge.text_color}

## PRODUCTOS
"""
        for slug, product in products.items():
            price = product.price
            # Check if there's a price override in any day
            for day in campaign_plan.days:
                if slug in day.products and day.price_override:
                    price = day.price_override
                    break
            context += (
                f"- {slug}: {product.name} | Precio: {price} | Categoría: {product.category}\n"
            )

        context += "\n## INSTRUCCIONES\nAnalizá las imágenes de referencia y generá los prompts para cada día. Respondé en JSON."

        content_parts.append({"type": "text", "text": context})

        # Agregar imágenes de estilo
        content_parts.append(
            {
                "type": "text",
                "text": "\n\n## REFERENCIAS DE ESTILO (copiar composición, iluminación, mood):",
            }
        )
        for i, ref_path in enumerate(style_references[:3]):  # Max 3 referencias
            if ref_path.exists():
                img_data = load_image_as_base64(ref_path)
                media_type = get_image_media_type(ref_path)
                content_parts.append({"type": "text", "text": f"\nReferencia de estilo {i + 1}:"})
                content_parts.append(
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": img_data},
                    }
                )

        # Agregar imágenes de productos
        content_parts.append(
            {
                "type": "text",
                "text": "\n\n## PRODUCTOS (replicar EXACTAMENTE en las imágenes generadas):",
            }
        )
        for slug, photo_path in product_references.items():
            if photo_path.exists():
                img_data = load_image_as_base64(photo_path)
                media_type = get_image_media_type(photo_path)
                product_name = products.get(slug, Product(name=slug, price="")).name
                content_parts.append(
                    {"type": "text", "text": f"\nProducto '{product_name}' ({slug}):"}
                )
                content_parts.append(
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": img_data},
                    }
                )

        # Llamar a Claude
        console.print("[dim]   Analizando referencias y generando prompts...[/dim]")

        message = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            temperature=self.temperature,
            system=CREATIVE_ENGINE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content_parts}],
            timeout=120.0,
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
                raise ValueError(f"No se pudo parsear la respuesta: {response_text[:500]}")

        # Convertir a GenerationPrompt
        prompts = []
        prompts_data = data.get("prompts", [])

        for i, prompt_data in enumerate(prompts_data):
            day_num = prompt_data.get("day", i + 1)

            # Encontrar el DayPlan correspondiente
            day_plan = next((d for d in campaign_plan.days if d.day == day_num), None)
            if not day_plan:
                continue

            # Determinar tamaño
            size = day_plan.size
            aspect_ratio = "4:5" if size == "feed" else "9:16"
            size_px = "1080x1350" if size == "feed" else "1080x1920"

            # Combinar negative prompt del modelo con el del StyleGuide
            base_negative = prompt_data.get("negative_prompt", "")
            if style_guide:
                style_negative = style_guide.to_negative_prompt()
                combined_negative = (
                    f"{base_negative}, {style_negative}" if base_negative else style_negative
                )
            else:
                combined_negative = base_negative

            gen_prompt = GenerationPrompt(
                prompt=prompt_data.get("prompt", ""),
                visual_description=prompt_data.get("visual_notes", ""),
                negative_prompt=combined_negative,
                params=GenerationParams(
                    aspect_ratio=aspect_ratio,
                    quality="high",
                    size=size_px,
                ),
            )
            prompts.append(gen_prompt)

        # Log del análisis
        ref_analysis = data.get("reference_analysis", {})
        coherence = data.get("coherence_strategy", "")

        console.print("[green][OK][/green] Análisis completado:")
        console.print(f"[dim]   Estilo detectado: {ref_analysis.get('style', 'N/A')[:60]}...[/dim]")
        console.print(f"[dim]   Coherencia: {coherence[:80]}...[/dim]")
        console.print(f"[green][OK][/green] {len(prompts)} prompts generados")

        return prompts

    def create_single_prompt(
        self,
        style_reference: Path,
        product_reference: Path,
        brand: Brand,
        product: Product,
        target_size: str = "feed",
        visual_direction: str = "",
    ) -> GenerationPrompt:
        """
        Genera un solo prompt (para uso simple, no campaña).

        Mantiene compatibilidad con el flujo existente pero usando el nuevo engine.
        """
        console.print(f"\n[blue][{self.name}][/blue] Generando prompt individual...")

        # Construir contenido
        content_parts = []

        context = f"""## SOLICITUD INDIVIDUAL
Generá UN prompt para una imagen de producto.

## MARCA
- Nombre: {brand.name}
- Colores: primary={brand.palette.primary}, secondary={brand.palette.secondary}
- Mood: {brand.get_mood_string()}

## PRODUCTO
- Nombre: {product.name}
- Precio: {product.price}
- Categoría: {product.category}

## FORMATO
- Tamaño: {target_size} ({"4:5, 1080x1350" if target_size == "feed" else "9:16, 1080x1920"})

## DIRECCIÓN VISUAL
{visual_direction if visual_direction else "Usar el estilo de la referencia"}

Respondé en JSON con: {{"prompt": "...", "negative_prompt": "...", "visual_notes": "..."}}
"""
        content_parts.append({"type": "text", "text": context})

        # Agregar imágenes
        if style_reference.exists():
            img_data = load_image_as_base64(style_reference)
            media_type = get_image_media_type(style_reference)
            content_parts.append({"type": "text", "text": "\nREFERENCIA DE ESTILO:"})
            content_parts.append(
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type, "data": img_data},
                }
            )

        if product_reference.exists():
            img_data = load_image_as_base64(product_reference)
            media_type = get_image_media_type(product_reference)
            content_parts.append({"type": "text", "text": "\nPRODUCTO (replicar exactamente):"})
            content_parts.append(
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type, "data": img_data},
                }
            )

        message = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            temperature=self.temperature,
            system=CREATIVE_ENGINE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content_parts}],
            timeout=60.0,
        )

        response_text = message.content[0].text

        try:
            data = json.loads(response_text)
        except json.JSONDecodeError:
            import re

            json_match = re.search(r"\{[\s\S]*\}", response_text)
            if json_match:
                data = json.loads(json_match.group())
            else:
                raise ValueError(f"No se pudo parsear: {response_text[:300]}")

        aspect_ratio = "4:5" if target_size == "feed" else "9:16"
        size_px = "1080x1350" if target_size == "feed" else "1080x1920"

        gen_prompt = GenerationPrompt(
            prompt=data.get("prompt", ""),
            visual_description=data.get("visual_notes", ""),
            negative_prompt=data.get("negative_prompt", ""),
            params=GenerationParams(aspect_ratio=aspect_ratio, quality="high", size=size_px),
        )

        console.print(f"[green][OK][/green] Prompt generado ({len(gen_prompt.prompt)} chars)")

        return gen_prompt
