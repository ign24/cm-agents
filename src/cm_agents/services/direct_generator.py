"""Direct Generator - Generación directa con Responses API.

Flujo:
1. Usuario sube imagen de producto + ocasión
2. Pinterest refs para estilo visual
3. Responses API genera imagen BASE (sin texto)
4. Responses API agrega texto profesional (edit)
5. CascadeStyleManager mantiene coherencia
"""

import base64
import logging
from pathlib import Path

from openai import OpenAI
from rich.console import Console

from ..models.campaign_style import CampaignStyleGuide
from ..models.product import Product

console = Console()
logger = logging.getLogger(__name__)

# Costos estimados
COST_PER_IMAGE = {
    "gpt-image-1": 0.04,
    "gpt-image-1.5": 0.06,
}


def load_image_as_base64(path: Path) -> str:
    """Carga imagen como base64."""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def get_media_type(path: Path) -> str:
    """Obtiene media type de imagen."""
    suffix = path.suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(suffix, "image/png")


class DirectGenerator:
    """Generador directo usando Responses API de OpenAI.

    Flujo de 2 pasos:
    1. generate_base_image(): Producto + Pinterest refs → Imagen sin texto
    2. add_text_overlay(): Imagen base + StyleGuide → Imagen con texto AI
    """

    def __init__(
        self,
        model: str = "gpt-image-1.5",
        chat_model: str = "gpt-4.1",
    ):
        """
        Args:
            model: Modelo de generación de imágenes (gpt-image-1.5 recomendado)
            chat_model: Modelo de chat para Responses API
        """
        self.client = OpenAI()
        self.model = model
        self.chat_model = chat_model
        self.cost_accumulated = 0.0

    def generate_base_image(
        self,
        product_image: Path,
        pinterest_refs: list[Path],
        scene_prompt: str,
        style_guide: CampaignStyleGuide | None = None,
        output_path: Path | None = None,
        size: str = "1024x1536",
    ) -> tuple[Path, float]:
        """Genera imagen base con producto y estilo de Pinterest.

        Args:
            product_image: Imagen del producto subida por el usuario
            pinterest_refs: Referencias de estilo de Pinterest
            scene_prompt: Descripción de la escena (sin mencionar texto)
            style_guide: Guía de estilo para coherencia
            output_path: Dónde guardar la imagen
            size: Tamaño de salida

        Returns:
            Tuple de (path a imagen generada, costo en USD)
        """
        console.print("\n[blue][DirectGen][/blue] Generando imagen base...")
        console.print(f"[dim]   Producto: {product_image.name}[/dim]")
        console.print(f"[dim]   Referencias Pinterest: {len(pinterest_refs)}[/dim]")

        # Construir contenido multimodal
        content_parts = []

        # Instrucciones principales
        style_instructions = ""
        if style_guide:
            style_instructions = f"""
STYLE GUIDE:
- Base style: {style_guide.base_style}
- Lighting: {style_guide.lighting_style}
- Color scheme: {", ".join(style_guide.color_scheme[:3])}
- Mood: {style_guide.atmosphere}
"""

        main_prompt = f"""You are a professional advertising photographer and art director.

TASK: Create a promotional image for the product shown below.

{style_instructions}

SCENE DESCRIPTION:
{scene_prompt}

CRITICAL REQUIREMENTS:
1. PRODUCT FIDELITY: The product must be EXACTLY as shown in the product image - same shape, colors, labels, brand, packaging. Do NOT modify the product appearance.
2. NO TEXT: Do NOT add any text, prices, headlines, or typography to the image. Text will be added in a separate step.
3. COMPOSITION: Leave clear space for text overlay (approximately top 20% or bottom 25% of the image).
4. STYLE: Match the visual style, lighting, and mood from the Pinterest reference images.
5. PROFESSIONAL QUALITY: Studio-quality lighting, sharp focus on product, cohesive color grading.

Generate a single promotional image following these requirements."""

        content_parts.append({"type": "input_text", "text": main_prompt})

        # Agregar imagen del producto (CRÍTICA - debe replicarse exactamente)
        content_parts.append(
            {"type": "input_text", "text": "\n--- PRODUCT IMAGE (replicate this EXACTLY) ---"}
        )

        product_b64 = load_image_as_base64(product_image)
        product_media = get_media_type(product_image)
        content_parts.append(
            {"type": "input_image", "image_url": f"data:{product_media};base64,{product_b64}"}
        )

        # Agregar referencias de Pinterest (para estilo visual)
        if pinterest_refs:
            content_parts.append(
                {
                    "type": "input_text",
                    "text": "\n--- STYLE REFERENCES (use these for composition, lighting, mood) ---",
                }
            )

            for i, ref_path in enumerate(pinterest_refs[:3]):  # Máximo 3 refs
                if ref_path.exists():
                    ref_b64 = load_image_as_base64(ref_path)
                    ref_media = get_media_type(ref_path)
                    content_parts.append(
                        {"type": "input_image", "image_url": f"data:{ref_media};base64,{ref_b64}"}
                    )
                    console.print(f"[dim]   + Ref {i + 1}: {ref_path.name}[/dim]")

        # Llamar a Responses API
        console.print("[dim]   Generando con Responses API...[/dim]")

        try:
            response = self.client.responses.create(
                model=self.chat_model,
                input=[{"role": "user", "content": content_parts}],
                tools=[
                    {
                        "type": "image_generation",
                        "size": size,
                        "quality": "high",
                    }
                ],
            )

            # Extraer imagen generada
            image_data = None
            for output in response.output:
                if output.type == "image_generation_call":
                    image_data = output.result
                    break

            if not image_data:
                raise ValueError("No se generó imagen en la respuesta")

            # Guardar imagen
            if output_path is None:
                output_path = Path("outputs") / "direct" / "base_image.png"

            output_path.parent.mkdir(parents=True, exist_ok=True)

            image_bytes = base64.b64decode(image_data)
            with open(output_path, "wb") as f:
                f.write(image_bytes)

            cost = COST_PER_IMAGE.get(self.model, 0.08)
            self.cost_accumulated += cost

            console.print(f"[green][OK][/green] Imagen base generada: {output_path}")
            console.print(f"[dim]   Costo: ${cost:.4f}[/dim]")

            return output_path, cost

        except Exception as e:
            console.print(f"[red][X] Error generando imagen base: {e}[/red]")
            raise

    def generate_scene_with_product(
        self,
        product_ref: Path,
        scene_ref: Path,
        output_path: Path | None = None,
        size: str = "1024x1536",
        style_guide: CampaignStyleGuide | None = None,
        angle_hint: str = "",
    ) -> tuple[Path, float]:
        """Genera fondo + producto en una sola llamada (replica exacta del producto).

        Usa la referencia de escena como estilo/ambiente y coloca una replica
        exacta del producto de la referencia. Una sola generación para mejor
        coherencia de luz y perspectiva.

        Args:
            product_ref: Imagen del producto (replica exacta)
            scene_ref: Imagen de la escena/fondo (estilo y ambiente)
            output_path: Dónde guardar la imagen
            size: Tamaño de salida
            style_guide: Guía de estilo opcional

        Returns:
            Tuple de (path a imagen generada, costo en USD)
        """
        console.print(
            "\n[blue][DirectGen][/blue] Generando escena + producto (una sola llamada)..."
        )
        console.print(f"[dim]   Producto: {product_ref.name}[/dim]")
        console.print(f"[dim]   Escena: {scene_ref.name}[/dim]")
        if angle_hint:
            console.print(f"[dim]   Angulo: {angle_hint}[/dim]")

        style_instructions = ""
        if style_guide:
            style_instructions = f"""
STYLE NOTES (optional): {style_guide.base_style}, {style_guide.lighting_style}.
"""

        angle_instructions = ""
        if angle_hint:
            angle_instructions = f"""
PRODUCT ANGLE & COMPOSITION: {angle_hint}
Place the product according to this direction to create variation across a campaign.
"""

        main_prompt = f"""You are a professional advertising photographer and art director.

TASK: Create ONE image that combines:
1. The SCENE REFERENCE as the background, environment, lighting, and mood. Use that image as the exact visual reference for the setting.
2. An EXACT REPLICA of the PRODUCT from the product reference. The product must be a precise replica: same shape, colors, labels, brand, packaging, every detail. Place it naturally in the scene.

{style_instructions}{angle_instructions}

CRITICAL REQUIREMENTS:
1. PRODUCT: The product must be an exact replica of the product reference image - do not modify, reinterpret, or stylize it. Same shape, colors, labels, brand, every detail.
2. SCENE: Match the background, lighting, atmosphere, and mood from the scene reference. The product should look like it belongs in that environment.
3. NO TEXT: Do NOT add any text, prices, headlines, or typography. Text will be added in a separate step.
4. Leave clear space for text overlay (approximately top 20% or bottom 25% of the image).
5. Professional quality: sharp focus on product, cohesive lighting.

Generate a single promotional image following these requirements."""

        content_parts = [
            {"type": "input_text", "text": main_prompt},
            {
                "type": "input_text",
                "text": "\n--- PRODUCT REFERENCE (exact replica of this product) ---",
            },
            {
                "type": "input_image",
                "image_url": f"data:{get_media_type(product_ref)};base64,{load_image_as_base64(product_ref)}",
            },
            {
                "type": "input_text",
                "text": "\n--- SCENE REFERENCE (use this as background, lighting, mood) ---",
            },
            {
                "type": "input_image",
                "image_url": f"data:{get_media_type(scene_ref)};base64,{load_image_as_base64(scene_ref)}",
            },
        ]

        console.print("[dim]   Generando con Responses API...[/dim]")

        try:
            response = self.client.responses.create(
                model=self.chat_model,
                input=[{"role": "user", "content": content_parts}],
                tools=[{"type": "image_generation", "size": size, "quality": "high"}],
            )

            image_data = None
            for output in response.output:
                if output.type == "image_generation_call":
                    image_data = output.result
                    break

            if not image_data:
                raise ValueError("No se generó imagen en la respuesta")

            if output_path is None:
                output_path = Path("outputs") / "refs" / "scene_with_product.png"

            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(base64.b64decode(image_data))

            cost = COST_PER_IMAGE.get(self.model, 0.08)
            self.cost_accumulated += cost
            console.print(f"[green][OK][/green] Escena + producto generados: {output_path}")
            console.print(f"[dim]   Costo: ${cost:.4f}[/dim]")
            return output_path, cost

        except Exception as e:
            console.print(f"[red][X] Error generando escena + producto: {e}[/red]")
            raise

    def add_text_overlay(
        self,
        base_image: Path,
        style_guide: CampaignStyleGuide,
        product: Product,
        headline: str,
        subheadline: str | None = None,
        show_price: bool = False,
        output_path: Path | None = None,
        font_ref: Path | None = None,
    ) -> tuple[Path, float]:
        """Agrega texto profesional a la imagen base usando AI.

        Este paso usa Responses API para EDITAR la imagen base
        y agregar texto con diseño profesional.

        Args:
            base_image: Imagen base sin texto
            style_guide: Guía de estilo (tipografía, colores, posiciones)
            product: Datos del producto (nombre, precio)
            headline: Texto principal (ej: "BLACK FRIDAY")
            subheadline: Texto secundario opcional
            show_price: Si mostrar el precio (actualmente no se agrega precio en este flujo)
            output_path: Dónde guardar la imagen final
            font_ref: Imagen de referencia de tipografía (opcional)

        Returns:
            Tuple de (path a imagen final, costo en USD)
        """
        console.print("\n[blue][DirectGen][/blue] Agregando texto profesional...")
        console.print(f"[dim]   Headline: {headline}[/dim]")
        console.print(f"[dim]   Producto: {product.name}[/dim]")
        if font_ref:
            console.print(f"[dim]   Fuente ref: {font_ref.name}[/dim]")

        # Construir prompt para overlay de texto
        # Nota: este flujo no agrega precio; show_price se mantiene solo por compatibilidad.
        typography_guide = f"""
TYPOGRAPHY REQUIREMENTS:
- Headline font style: {style_guide.typography.headline_style} (bold, impactful)
- Headline color: {style_guide.typography.headline_color}
- Headline position: {style_guide.typography.headline_position}
- Text should have subtle shadow or outline for readability
- Professional marketing typography - clean, modern, high contrast"""

        font_ref_instruction = ""
        if font_ref and font_ref.exists():
            font_ref_instruction = """
REFERENCE IMAGE (SOURCE): Use it ONLY for style. Replicate the typography look (font, weight, character) from that image. Do NOT copy the words shown in the reference. Write ONLY the exact texts we give you below (headline, subheadline). Same visual style as the reference — our content."""

        subheadline_instruction = ""
        if subheadline:
            subheadline_instruction = f"""
SUBHEADLINE (exact text, in the reference style):
- Text: "{subheadline}"
- Smaller than headline, same typography style as the reference image
- Position below or near the headline"""

        edit_prompt = f"""You are a professional graphic designer. Add text to the image using the SOURCE REFERENCE image for style only.

RULES:
1. SOURCE REFERENCE (the reference image): Take the typography STYLE from it — font, weight, look. Replicate that style. Do NOT copy the words written in that image.
2. REPLICA: The letters must look like the reference (same font, same weight). The words must be exactly what we specify below — our headline and our subheadline.
3. Write ONLY these exact texts (nothing else):

HEADLINE (once only): "{headline}"
{subheadline_instruction}

CRITICAL:
- Style from reference image; content from us. No extra text, no "SUPER Descuento", no repeated headline, no text from the reference image.
- Do NOT add any price, price badge, currency, or monetary amount to the image.
- Do not modify product or background. High contrast, readable."""

        content_parts = [
            {"type": "input_text", "text": edit_prompt},
        ]

        # Agregar referencia de fuente si existe (antes de la imagen base para que el modelo la vea como estilo)
        if font_ref and font_ref.exists():
            font_b64 = load_image_as_base64(font_ref)
            font_media = get_media_type(font_ref)
            content_parts.append(
                {
                    "type": "input_text",
                    "text": "\n--- SOURCE REFERENCE (fuente.jpg): use this image ONLY for typography style; replicate that style but write our exact headline and subheadline ---",
                }
            )
            content_parts.append(
                {"type": "input_image", "image_url": f"data:{font_media};base64,{font_b64}"}
            )

        # Agregar imagen base para editar
        base_b64 = load_image_as_base64(base_image)
        base_media = get_media_type(base_image)
        content_parts.append(
            {
                "type": "input_text",
                "text": "\n--- IMAGE TO EDIT (add text overlay to this image) ---",
            }
        )
        content_parts.append(
            {"type": "input_image", "image_url": f"data:{base_media};base64,{base_b64}"}
        )

        # Llamar a Responses API para editar
        console.print("[dim]   Generando texto con AI...[/dim]")

        try:
            response = self.client.responses.create(
                model=self.chat_model,
                input=[{"role": "user", "content": content_parts}],
                tools=[
                    {
                        "type": "image_generation",
                        "quality": "high",
                    }
                ],
            )

            # Extraer imagen editada
            image_data = None
            for output in response.output:
                if output.type == "image_generation_call":
                    image_data = output.result
                    break

            if not image_data:
                raise ValueError("No se generó imagen con texto")

            # Guardar imagen final
            if output_path is None:
                output_path = base_image.parent / f"{base_image.stem}_final.png"

            output_path.parent.mkdir(parents=True, exist_ok=True)

            image_bytes = base64.b64decode(image_data)
            with open(output_path, "wb") as f:
                f.write(image_bytes)

            cost = COST_PER_IMAGE.get(self.model, 0.08)
            self.cost_accumulated += cost

            console.print(f"[green][OK][/green] Texto agregado: {output_path}")
            console.print(f"[dim]   Costo: ${cost:.4f}[/dim]")

            return output_path, cost

        except Exception as e:
            console.print(f"[red][X] Error agregando texto: {e}[/red]")
            raise

    def generate_complete(
        self,
        product_image: Path,
        pinterest_refs: list[Path],
        scene_prompt: str,
        style_guide: CampaignStyleGuide,
        product: Product,
        headline: str,
        subheadline: str | None = None,
        show_price: bool = True,
        output_dir: Path | None = None,
        variant_number: int = 1,
    ) -> tuple[Path, float]:
        """Genera imagen completa en 2 pasos: base + texto.

        Args:
            product_image: Imagen del producto
            pinterest_refs: Referencias de Pinterest
            scene_prompt: Descripción de escena
            style_guide: Guía de estilo
            product: Datos del producto
            headline: Texto principal
            subheadline: Texto secundario
            show_price: Mostrar precio
            output_dir: Directorio de salida
            variant_number: Número de variante

        Returns:
            Tuple de (path a imagen final, costo total)
        """
        console.print(f"\n[bold cyan]═══ Generando imagen {variant_number} ═══[/bold cyan]")

        if output_dir is None:
            output_dir = Path("outputs") / "direct"

        output_dir.mkdir(parents=True, exist_ok=True)

        # Paso 1: Imagen base
        base_path = output_dir / f"{product.name}_v{variant_number}_base.png"
        base_path, cost1 = self.generate_base_image(
            product_image=product_image,
            pinterest_refs=pinterest_refs,
            scene_prompt=scene_prompt,
            style_guide=style_guide,
            output_path=base_path,
        )

        # Paso 2: Agregar texto
        final_path = output_dir / f"{product.name}_v{variant_number}.png"
        final_path, cost2 = self.add_text_overlay(
            base_image=base_path,
            style_guide=style_guide,
            product=product,
            headline=headline,
            subheadline=subheadline,
            show_price=show_price,
            output_path=final_path,
        )

        total_cost = cost1 + cost2
        console.print("\n[bold green][OK] Imagen completa generada[/bold green]")
        console.print(f"[dim]   Base: {base_path}[/dim]")
        console.print(f"[dim]   Final: {final_path}[/dim]")
        console.print(f"[dim]   Costo total: ${total_cost:.4f}[/dim]")

        return final_path, total_cost


# Factory function
def get_direct_generator(model: str = "gpt-image-1.5") -> DirectGenerator:
    """Obtiene instancia de DirectGenerator."""
    return DirectGenerator(model=model)
