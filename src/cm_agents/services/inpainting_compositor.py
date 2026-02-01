"""Servicio de composición con Inpainting - Integración realista del producto."""

import base64
import io
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFilter
from rich.console import Console

if TYPE_CHECKING:
    from ..models.campaign_style import CampaignStyleGuide

console = Console()


class InpaintingCompositor:
    """Compone productos usando inpainting para integración realista.

    A diferencia del compositing simple (pegar sobre fondo), el inpainting
    permite que el modelo AI integre el producto con:
    - Sombras coherentes con la iluminación de la escena
    - Reflejos en superficies
    - Adaptación a la perspectiva
    - Interacción con elementos de la escena (ej: sobre una mesa)

    Flujo:
    1. Generar escena con área designada para el producto (placeholder)
    2. Crear máscara de esa área
    3. Usar inpainting con imagen del producto como referencia
    """

    def __init__(self, model: str = "gpt-image-1.5"):
        from openai import OpenAI

        self.client = OpenAI()
        self.model = model

    def create_product_mask(
        self,
        image_size: tuple[int, int],
        position: str = "center",
        product_scale: float = 0.4,
        shape: str = "ellipse",
        feather: int = 20,
    ) -> Image.Image:
        """Crea una máscara para el área del producto.

        La máscara indica al modelo dónde debe "pintar" el producto.
        Blanco = área a editar, Negro = área a preservar.

        Args:
            image_size: (width, height) de la imagen
            position: "center", "left", "right", "bottom-center"
            product_scale: Proporción del área respecto al ancho (0.0-1.0)
            shape: "ellipse", "rectangle", "bottle" (forma adaptada)
            feather: Cantidad de difuminado en los bordes (píxeles)

        Returns:
            Imagen RGBA donde transparente = preservar, blanco = editar
        """
        width, height = image_size

        # Calcular dimensiones del área del producto
        mask_width = int(width * product_scale)
        mask_height = int(mask_width * 1.5)  # Proporción típica de producto vertical

        # No exceder 70% de la altura
        if mask_height > height * 0.7:
            mask_height = int(height * 0.7)
            mask_width = int(mask_height / 1.5)

        # Calcular posición
        if position == "center":
            x = (width - mask_width) // 2
            y = (height - mask_height) // 2
        elif position == "left":
            x = int(width * 0.15)
            y = (height - mask_height) // 2
        elif position == "right":
            x = width - mask_width - int(width * 0.15)
            y = (height - mask_height) // 2
        elif position == "bottom-center":
            x = (width - mask_width) // 2
            y = height - mask_height - int(height * 0.1)
        else:
            x = (width - mask_width) // 2
            y = (height - mask_height) // 2

        # Crear máscara base (transparente = preservar)
        mask = Image.new("RGBA", image_size, (0, 0, 0, 255))
        draw = ImageDraw.Draw(mask)

        # Dibujar área de edición (blanco)
        if shape == "ellipse":
            draw.ellipse([x, y, x + mask_width, y + mask_height], fill=(255, 255, 255, 255))
        elif shape == "rectangle":
            # Rectángulo con esquinas redondeadas
            radius = min(mask_width, mask_height) // 8
            draw.rounded_rectangle(
                [x, y, x + mask_width, y + mask_height], radius=radius, fill=(255, 255, 255, 255)
            )
        elif shape == "bottle":
            # Forma de botella: elipse arriba + rectángulo abajo
            neck_width = mask_width // 3
            neck_height = mask_height // 4

            # Cuello
            neck_x = x + (mask_width - neck_width) // 2
            draw.ellipse(
                [neck_x, y, neck_x + neck_width, y + neck_height], fill=(255, 255, 255, 255)
            )
            # Cuerpo
            draw.ellipse(
                [x, y + neck_height - 20, x + mask_width, y + mask_height],
                fill=(255, 255, 255, 255),
            )

        # Aplicar feather (difuminado) para transición suave
        if feather > 0:
            # Convertir a escala de grises para blur
            alpha = mask.split()[3]
            alpha = alpha.filter(ImageFilter.GaussianBlur(radius=feather))
            mask.putalpha(alpha)

        return mask

    def generate_scene_with_placeholder(
        self,
        prompt: str,
        size: str = "1024x1536",
        position: str = "center",
        product_scale: float = 0.4,
    ) -> tuple[Image.Image, Image.Image]:
        """Genera escena con área vacía para el producto.

        El prompt debe describir la escena SIN el producto.
        El modelo dejará un espacio natural donde irá el producto.

        Args:
            prompt: Descripción de la escena (sin producto)
            size: Tamaño de la imagen
            position: Dónde dejar espacio para el producto
            product_scale: Qué proporción del ancho ocupará el producto

        Returns:
            Tuple de (imagen_escena, máscara)
        """
        console.print("[blue][Inpainting][/blue] Generando escena base...")

        # Modificar prompt para indicar área vacía
        placeholder_instructions = f"""
[IMPORTANT: Leave a clear, prominent empty space in the {position} of the image for a product to be added later.
The empty area should be approximately {int(product_scale * 100)}% of the image width.
Do NOT put any object in this reserved space - it should be a natural-looking empty area
(e.g., empty table surface, empty shelf space, clear podium, etc.)]

"""
        full_prompt = placeholder_instructions + prompt

        # Parsear tamaño
        w, h = map(int, size.split("x"))

        # Generar escena
        try:
            result = self.client.images.generate(
                model=self.model,
                prompt=full_prompt,
                size=size,
                n=1,
            )

            # Obtener imagen
            if result.data[0].b64_json:
                image_bytes = base64.b64decode(result.data[0].b64_json)
            elif result.data[0].url:
                import httpx

                response = httpx.get(result.data[0].url)
                image_bytes = response.content
            else:
                raise ValueError("No se recibió imagen")

            scene = Image.open(io.BytesIO(image_bytes)).convert("RGBA")

            # Crear máscara correspondiente
            mask = self.create_product_mask(
                scene.size,
                position=position,
                product_scale=product_scale,
            )

            console.print("[green][OK][/green] Escena generada")
            return scene, mask

        except Exception as e:
            console.print(f"[red][X] Error generando escena:[/red] {e}")
            raise

    def inpaint_product(
        self,
        scene: Image.Image | Path,
        mask: Image.Image | Path,
        product_reference: Path,
        product_description: str,
        quality: str = "high",
    ) -> Image.Image:
        """Usa inpainting para integrar el producto en la escena.

        El modelo "pinta" el producto en el área de la máscara,
        adaptándolo a la iluminación y perspectiva de la escena.

        Args:
            scene: Imagen de la escena (con área vacía)
            mask: Máscara indicando dónde va el producto
            product_reference: Foto del producto real
            product_description: Descripción del producto para guiar el inpainting
            quality: "low", "medium", "high"

        Returns:
            Imagen final con producto integrado
        """
        console.print("[blue][Inpainting][/blue] Integrando producto con Responses API...")

        # Cargar imágenes si son paths
        if isinstance(scene, Path):
            scene = Image.open(scene).convert("RGBA")
        if isinstance(mask, Path):
            mask = Image.open(mask).convert("RGBA")

        # Convertir imágenes a base64
        def image_to_base64(img: Image.Image) -> str:
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            return base64.b64encode(buffer.getvalue()).decode("utf-8")

        def path_to_base64(path: Path) -> str:
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")

        scene_b64 = image_to_base64(scene)
        mask_b64 = image_to_base64(mask)
        product_b64 = path_to_base64(product_reference)

        # Prompt detallado para inpainting con referencia de producto
        inpaint_prompt = f"""
TASK: Paint the product from the REFERENCE IMAGE into the MASKED AREA of the SCENE.

PRODUCT REFERENCE IMAGE: The second image shows the EXACT product you must paint.
SCENE IMAGE: The first image is the scene where you'll add the product.
MASK: The white area in the mask indicates WHERE to paint the product.

PRODUCT DESCRIPTION: {product_description}

CRITICAL REQUIREMENTS:
1. Copy the product from the reference EXACTLY - same shape, colors, labels, brand, every detail
2. Integrate it naturally into the scene:
   - Add shadows that match the scene's lighting direction
   - Add reflections if the surface is reflective
   - Match the perspective and scale to the scene
3. The product should look like it BELONGS in the scene, not pasted on top
4. Blend the edges naturally - no hard cutout appearance
5. If on a table/surface, product should cast a soft shadow beneath it

Paint the product NOW in the masked area.
"""

        try:
            # Usar Responses API con imagen de producto como referencia
            # Esto permite que el modelo "vea" el producto real
            content_parts = [
                {"type": "input_text", "text": inpaint_prompt},
                {
                    "type": "input_text",
                    "text": "SCENE IMAGE (paint the product in the empty area):",
                },
                {
                    "type": "input_image",
                    "image_url": f"data:image/png;base64,{scene_b64}",
                },
                {"type": "input_text", "text": "PRODUCT REFERENCE (copy this EXACT product):"},
                {
                    "type": "input_image",
                    "image_url": f"data:image/png;base64,{product_b64}",
                },
            ]

            # Determinar tamaño
            size = "1024x1536" if scene.height > scene.width else "1024x1024"
            if scene.width == scene.height:
                size = "1024x1024"

            # Intentar con diferentes modelos de chat
            chat_models = ["gpt-4o-mini", "gpt-4-turbo", "gpt-4"]
            response = None

            for chat_model in chat_models:
                try:
                    console.print(f"[dim]   Usando {chat_model} + {self.model}...[/dim]")
                    response = self.client.responses.create(
                        model=chat_model,
                        input=[{"role": "user", "content": content_parts}],
                        tools=[
                            {
                                "type": "image_generation",
                                "model": self.model,
                                "size": size,
                                "quality": quality if quality != "auto" else "medium",
                                "input_image_mask": {
                                    "image_url": f"data:image/png;base64,{mask_b64}",
                                },
                            }
                        ],
                    )
                    break
                except Exception as e:
                    error_str = str(e).lower()
                    if "403" in error_str or "not supported" in error_str:
                        continue
                    # Si el error es por input_image_mask, intentar sin máscara
                    if "mask" in error_str:
                        console.print(
                            "[yellow][!] Máscara no soportada, usando generación directa[/yellow]"
                        )
                        response = self.client.responses.create(
                            model=chat_model,
                            input=[{"role": "user", "content": content_parts}],
                            tools=[
                                {
                                    "type": "image_generation",
                                    "model": self.model,
                                    "size": size,
                                    "quality": quality if quality != "auto" else "medium",
                                }
                            ],
                        )
                        break
                    raise

            if response is None:
                raise ValueError("No se pudo generar con ningún modelo de chat")

            # Extraer imagen generada
            image_data = [
                output.result
                for output in response.output
                if output.type == "image_generation_call"
            ]

            if not image_data:
                raise ValueError("No se generó imagen en la respuesta")

            image_bytes = base64.b64decode(image_data[0])
            final = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            console.print("[green][OK][/green] Producto integrado")
            return final

        except Exception as e:
            console.print(f"[red][X] Error en inpainting:[/red] {e}")
            # Fallback: usar Image Edit API simple
            console.print("[yellow][!] Intentando fallback con Image Edit API...[/yellow]")
            return self._fallback_inpaint(scene, mask, product_description)

    def _fallback_inpaint(
        self,
        scene: Image.Image,
        mask: Image.Image,
        product_description: str,
    ) -> Image.Image:
        """Fallback usando Image Edit API sin referencia de producto.

        Menos preciso pero más compatible.
        """

        def image_to_bytes(img: Image.Image) -> bytes:
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            return buffer.getvalue()

        scene_bytes = image_to_bytes(scene)
        mask_bytes = image_to_bytes(mask)

        prompt = f"""
Paint this product in the masked area: {product_description}

Requirements:
- Realistic product photography style
- Natural shadows matching the scene lighting
- Professional product presentation
- The product should look like it belongs in this scene
"""

        # Determinar tamaño
        size = "1024x1536" if scene.height > scene.width else "1024x1024"
        if scene.width == scene.height:
            size = "1024x1024"

        try:
            result = self.client.images.edit(
                model=self.model,
                image=scene_bytes,
                mask=mask_bytes,
                prompt=prompt,
                size=size,
            )

            if result.data[0].b64_json:
                image_bytes = base64.b64decode(result.data[0].b64_json)
            elif result.data[0].url:
                import httpx

                response = httpx.get(result.data[0].url)
                image_bytes = response.content
            else:
                raise ValueError("No image returned")

            return Image.open(io.BytesIO(image_bytes)).convert("RGB")

        except Exception as e:
            console.print(f"[red][X] Fallback también falló:[/red] {e}")
            raise

    def generate_with_inpainting(
        self,
        scene_prompt: str,
        product_photo: Path,
        product_description: str,
        output_path: Path,
        size: str = "1024x1536",
        position: str = "center",
        product_scale: float = 0.4,
        quality: str = "high",
    ) -> tuple[Path, float]:
        """Proceso completo: generar escena + inpaint producto.

        Args:
            scene_prompt: Descripción de la escena/fondo
            product_photo: Foto real del producto
            product_description: Descripción del producto
            output_path: Dónde guardar el resultado
            size: Tamaño de la imagen
            position: Posición del producto
            product_scale: Escala del producto
            quality: Calidad del inpainting

        Returns:
            Tuple de (path_imagen_final, costo_estimado)
        """
        console.print("\n[bold cyan]>> Generación con Inpainting[/bold cyan]")
        console.print(f"[dim]   Producto: {product_photo.name}[/dim]")
        console.print(f"[dim]   Posición: {position}[/dim]")

        # 1. Generar escena con placeholder
        scene, mask = self.generate_scene_with_placeholder(
            prompt=scene_prompt,
            size=size,
            position=position,
            product_scale=product_scale,
        )

        # Guardar escena intermedia (para debug)
        scene_path = output_path.parent / f"_scene_{output_path.stem}.png"
        scene.save(scene_path)

        # 2. Inpaint producto
        final = self.inpaint_product(
            scene=scene,
            mask=mask,
            product_reference=product_photo,
            product_description=product_description,
            quality=quality,
        )

        # 3. Guardar resultado
        output_path.parent.mkdir(parents=True, exist_ok=True)
        final.save(output_path, "PNG", quality=95)

        # Costo estimado (2 generaciones: escena + inpaint)
        cost = 0.06 * 2  # gpt-image-1.5 ~$0.06 por imagen

        console.print(f"[bold green][OK][/bold green] Guardado: {output_path}")
        console.print(f"[dim]   Costo estimado: ${cost:.3f}[/dim]")

        return output_path, cost


class CascadeStyleManager:
    """Gestiona coherencia visual entre imágenes de una campaña.

    Usa el CampaignStyleGuide como fuente principal de consistencia,
    y la primera imagen generada como "ancla visual" para refuerzo.
    """

    def __init__(self, style_guide: "CampaignStyleGuide | None" = None):
        from ..models.campaign_style import CampaignStyleGuide

        self.style_guide: CampaignStyleGuide | None = style_guide
        self.style_anchor: Image.Image | None = None
        self.style_anchor_path: Path | None = None
        self.extracted_tokens: dict = {}  # Tokens extraídos del anchor
        self.image_count: int = 0

    def set_style_guide(self, style_guide: "CampaignStyleGuide") -> None:
        """Establece el StyleGuide para la campaña."""
        self.style_guide = style_guide
        console.print("[blue][Style][/blue] StyleGuide configurado")
        console.print(f"[dim]   Ocasión: {style_guide.occasion}[/dim]")
        console.print(f"[dim]   Estilo base: {style_guide.base_style}[/dim]")

    def set_anchor(self, image: Image.Image | Path) -> None:
        """Establece la imagen ancla de estilo.

        Las siguientes generaciones usarán esta imagen como referencia visual.
        """
        if isinstance(image, Path):
            self.style_anchor = Image.open(image)
            self.style_anchor_path = image
        else:
            self.style_anchor = image
            self.style_anchor_path = None

        # Extraer tokens de estilo de la imagen
        self._extract_style_tokens()
        console.print("[blue][Style][/blue] Ancla visual establecida")

    def _extract_style_tokens(self) -> None:
        """Extrae tokens de estilo de la imagen anchor.

        Analiza colores dominantes, luminosidad, etc.
        """
        if self.style_anchor is None:
            return

        import numpy as np

        # Convertir a numpy array
        img_array = np.array(self.style_anchor)

        # Extraer estadísticas de color
        if len(img_array.shape) == 3:
            # Colores promedio
            avg_colors = img_array.mean(axis=(0, 1))
            self.extracted_tokens["avg_r"] = int(avg_colors[0])
            self.extracted_tokens["avg_g"] = int(avg_colors[1])
            self.extracted_tokens["avg_b"] = int(avg_colors[2])

            # Luminosidad promedio
            luminance = 0.299 * avg_colors[0] + 0.587 * avg_colors[1] + 0.114 * avg_colors[2]
            self.extracted_tokens["luminance"] = "dark" if luminance < 128 else "bright"

            # Contraste (desviación estándar)
            std = img_array.std()
            self.extracted_tokens["contrast"] = "high" if std > 50 else "low"

            # Saturación aproximada
            r, g, b = avg_colors[0], avg_colors[1], avg_colors[2]
            max_c = max(r, g, b)
            min_c = min(r, g, b)
            saturation = (max_c - min_c) / max_c if max_c > 0 else 0
            self.extracted_tokens["saturation"] = "vivid" if saturation > 0.3 else "muted"

        console.print(f"[dim]   Tokens extraídos: {self.extracted_tokens}[/dim]")

    def get_style_reference_prompt(self) -> str:
        """Genera instrucciones de estilo detalladas.

        Combina el StyleGuide con los tokens extraídos del anchor.
        """
        parts = []

        # Instrucciones del StyleGuide (prioridad alta)
        if self.style_guide:
            parts.append("[CAMPAIGN STYLE GUIDE - MANDATORY]")
            parts.append(self.style_guide.to_prompt_header())

        # Instrucciones basadas en el anchor visual
        if self.style_anchor is not None:
            parts.append("\n[VISUAL ANCHOR - Match these characteristics:]")

            if self.extracted_tokens:
                luminance = self.extracted_tokens.get("luminance", "balanced")
                contrast = self.extracted_tokens.get("contrast", "medium")
                saturation = self.extracted_tokens.get("saturation", "balanced")

                parts.append(f"- Overall brightness: {luminance}")
                parts.append(f"- Contrast level: {contrast}")
                parts.append(f"- Color saturation: {saturation}")

            parts.append("- Same lighting setup and direction as reference")
            parts.append("- Same color temperature and mood")
            parts.append("- Same photographic style and polish level")
            parts.append("- Same background treatment")

        return "\n".join(parts)

    def prepare_cascaded_generation(
        self,
        base_prompt: str,
        is_first: bool = False,
        day_index: int = 0,
    ) -> tuple[str, list[Path]]:
        """Prepara prompt y referencias para generación en cascada.

        Args:
            base_prompt: Prompt base para la generación
            is_first: Si es la primera imagen (no hay ancla aún)
            day_index: Índice del día (para mood progression)

        Returns:
            Tuple de (prompt_modificado, lista_de_referencias)
        """
        self.image_count += 1
        parts = []
        references = []

        # Siempre incluir StyleGuide si existe
        if self.style_guide:
            # Ajustar mood según el día
            day_mood = self.style_guide.get_day_mood(day_index)
            parts.append(f"[DAY {day_index + 1} MOOD: {day_mood}]")
            parts.append(self.style_guide.to_prompt_header())

        # Si no es la primera imagen, agregar referencia al anchor
        if not is_first and self.style_anchor is not None:
            parts.append("\n[VISUAL CONSISTENCY WITH PREVIOUS IMAGES]")
            parts.append("Match the visual style of the first campaign image:")

            if self.extracted_tokens:
                parts.append(f"- Luminance: {self.extracted_tokens.get('luminance', 'match')}")
                parts.append(f"- Contrast: {self.extracted_tokens.get('contrast', 'match')}")
                parts.append(f"- Saturation: {self.extracted_tokens.get('saturation', 'match')}")

            # Incluir anchor como referencia visual
            if self.style_anchor_path and self.style_anchor_path.exists():
                references.append(self.style_anchor_path)

        # Agregar el prompt base
        parts.append("\n[SCENE PROMPT]")
        parts.append(base_prompt)

        # Agregar negative prompt del StyleGuide
        if self.style_guide:
            parts.append(f"\n[AVOID]\n{self.style_guide.to_negative_prompt()}")

        enhanced_prompt = "\n".join(parts)
        return enhanced_prompt, references

    def get_consistency_summary(self) -> str:
        """Retorna un resumen de la configuración de consistencia."""
        summary = []

        if self.style_guide:
            summary.append(
                f"StyleGuide: {self.style_guide.occasion} ({self.style_guide.base_style})"
            )

        if self.style_anchor is not None:
            summary.append(f"Visual Anchor: Set ({self.extracted_tokens.get('luminance', 'N/A')})")

        summary.append(f"Images generated: {self.image_count}")

        return " | ".join(summary) if summary else "No consistency configured"


# Singleton
_inpainting_compositor: InpaintingCompositor | None = None
_cascade_manager: CascadeStyleManager | None = None


def get_inpainting_compositor(model: str = "gpt-image-1.5") -> InpaintingCompositor:
    """Obtiene instancia singleton del compositor."""
    global _inpainting_compositor
    if _inpainting_compositor is None or _inpainting_compositor.model != model:
        _inpainting_compositor = InpaintingCompositor(model=model)
    return _inpainting_compositor


def get_cascade_manager() -> CascadeStyleManager:
    """Obtiene instancia singleton del manager de cascada."""
    global _cascade_manager
    if _cascade_manager is None:
        _cascade_manager = CascadeStyleManager()
    return _cascade_manager
