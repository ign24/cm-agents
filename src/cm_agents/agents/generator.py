"""Generator Agent - Genera imágenes con GPT-Image (Responses API)."""

import asyncio
import base64
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from openai import OpenAI
from rich.console import Console

from ..models.brand import Brand
from ..models.generation import GenerationPrompt, GenerationResult
from ..models.product import Product
from .base import BaseAgent, get_image_media_type, load_image_as_base64

console = Console()

# Costos estimados por modelo (según documentación de OpenAI)
COST_PER_IMAGE = {
    "gpt-image-1": 0.04,
    "gpt-image-1.5": 0.06,
    "gpt-image-1-mini": 0.02,
}

# Tamanos validos para OpenAI Images API gpt-image-1.5
# Supported: '1024x1024', '1024x1536', '1536x1024', and 'auto'
OPENAI_SIZES = {
    "1024x1024": "1024x1024",
    "1024x1536": "1024x1536",
    "1536x1024": "1536x1024",
}

# Mapeo de nuestros tamanos a tamanos de OpenAI
SIZE_MAPPINGS = {
    "1080x1080": "1024x1024",
    "1080x1350": "1024x1536",  # 4:5 vertical (feed IG)
    "1080x1920": "1024x1536",  # 9:16 vertical (story) - closest match
    "1920x1080": "1536x1024",  # 16:9 horizontal
}


class GeneratorAgent(BaseAgent):
    """Agente que genera imágenes usando GPT-Image de OpenAI (Responses API)."""

    def __init__(self, model: str = "gpt-image-1.5"):
        super().__init__()
        self.client = OpenAI(api_key=self._get_env("OPENAI_API_KEY"))
        self.model = model

    def _validate_env(self) -> None:
        """Valida que OPENAI_API_KEY esté configurada."""
        if not self._get_env("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY no configurada")

    @property
    def name(self) -> str:
        return "Generator"

    @property
    def description(self) -> str:
        return f"Genera imágenes usando {self.model}"

    def _get_size_param(self, size: str) -> str:
        """Convierte tamaño string al parámetro de OpenAI."""
        return SIZE_MAPPINGS.get(size, "1024x1024")

    def generate(
        self,
        prompt: GenerationPrompt,
        brand: Brand,
        product: Product,
        output_dir: Path,
        variant_number: int = 1,
    ) -> GenerationResult:
        """
        Genera una imagen basada en el prompt.

        Args:
            prompt: Prompt de generación
            brand: Marca para el output
            product: Producto para el output
            output_dir: Directorio donde guardar la imagen
            variant_number: Número de variante

        Returns:
            GenerationResult con la imagen generada
        """
        generation_id = str(uuid.uuid4())[:8]

        console.print(f"\n[blue][Gen] {self.name}:[/blue] Generando variante {variant_number}...")
        console.print(f"[dim]   Modelo: {self.model}[/dim]")
        console.print(f"[dim]   Tamaño: {prompt.params.size}[/dim]")

        console.print("[dim]   Generando...[/dim]")

        # Generar imagen usando GPT Image o DALL-E
        try:
            import httpx

            if self.model.startswith("gpt-image") or self.model.startswith("dall-e"):
                # Usar Image API
                size_param = self._get_size_param(prompt.params.size)

                # DALL-E 3 solo soporta ciertos tamanos
                if self.model == "dall-e-3":
                    if size_param == "1024x1536":
                        size_param = "1024x1792"  # DALL-E 3 usa 1024x1792
                    elif size_param not in ["1024x1024", "1024x1792", "1792x1024"]:
                        size_param = "1024x1024"

                result = self.client.images.generate(
                    model=self.model,
                    prompt=prompt.get_full_prompt(),
                    n=1,
                    size=size_param,
                )

                # Descargar imagen desde URL
                image_url = result.data[0].url
                if image_url:
                    response = httpx.get(image_url)
                    image_bytes = response.content
                else:
                    raise ValueError("No se recibio URL de imagen")
            else:
                raise NotImplementedError(f"Modelo {self.model} no implementado")

            # Guardar imagen
            filename = f"{product.name}_v{variant_number}.png"
            image_path = output_dir / filename

            import io

            from PIL import Image

            img = Image.open(io.BytesIO(image_bytes))
            img.save(image_path, "PNG", quality=95)

            # Calcular costo
            cost = COST_PER_IMAGE.get(self.model, 0.05)

            # Crear resultado
            gen_result = GenerationResult(
                id=generation_id,
                image_path=image_path,
                prompt_used=prompt.get_full_prompt(),
                brand_name=brand.name,
                product_name=product.name,
                variant_number=variant_number,
                cost_usd=cost,
            )

            console.print(f"[green][OK][/green] Generado: {filename}")
            console.print(f"[dim]   Costo: ${cost:.4f}[/dim]")
            console.print(f"[dim]   Guardado en: {image_path}[/dim]")

            return gen_result

        except Exception as e:
            console.print(f"[red][X] Error:[/red] {str(e)}")
            raise

    def generate_batch(
        self,
        prompts: list[GenerationPrompt],
        brand: Brand,
        product: Product,
        output_dir: Path,
    ) -> list[GenerationResult]:
        """
        Genera múltiples imágenes basado en múltiples prompts.

        Args:
            prompts: Lista de prompts
            brand: Marca
            product: Producto
            output_dir: Directorio de salida

        Returns:
            Lista de GenerationResult
        """
        results = []
        total_cost = 0.0

        console.print(f"\n[bold]Generando {len(prompts)} variantes...[/bold]")

        for i, prompt in enumerate(prompts, 1):
            result = self.generate(prompt, brand, product, output_dir, variant_number=i)
            results.append(result)
            total_cost += result.cost_usd

        console.print("\n[bold]Resumen:[/bold]")
        console.print(f"[dim]   Total variantes: {len(results)}[/dim]")
        console.print(f"[dim]   Costo total: ${total_cost:.4f}[/dim]")

        return results

    def get_cost_estimate(self, num_images: int) -> float:
        """
        Calcula costo estimado para N imágenes.

        Args:
            num_images: Cantidad de imágenes a generar

        Returns:
            Costo total estimado en USD
        """
        cost_per_image = COST_PER_IMAGE.get(self.model, 0.05)
        return cost_per_image * num_images

    async def generate_batch_parallel(
        self,
        prompts: list[GenerationPrompt],
        brand: Brand,
        products: dict[str, Product],  # {slug: Product}
        output_dir: Path,
        reference_images: list[Path] | None = None,
        max_concurrent: int = 5,
    ) -> list[GenerationResult]:
        """
        Genera múltiples imágenes EN PARALELO usando asyncio.

        Args:
            prompts: Lista de prompts a generar
            brand: Marca
            products: Dict de slug -> Product
            output_dir: Directorio de salida
            reference_images: Imágenes de referencia compartidas (opcional)
            max_concurrent: Máximo de generaciones simultáneas

        Returns:
            Lista de GenerationResult
        """
        import time

        start_time = time.time()
        console.print(
            f"\n[bold blue]Generando {len(prompts)} imágenes en paralelo (max {max_concurrent} simultáneas)...[/bold blue]"
        )

        output_dir.mkdir(parents=True, exist_ok=True)

        # Usar ThreadPoolExecutor para llamadas síncronas de OpenAI
        loop = asyncio.get_event_loop()
        executor = ThreadPoolExecutor(max_workers=max_concurrent)

        async def generate_one(idx: int, prompt: GenerationPrompt) -> GenerationResult:
            """Genera una imagen en un thread del pool."""
            # Determinar producto (usar el primero si hay varios)
            product_list = list(products.values())
            product = (
                product_list[idx % len(product_list)]
                if product_list
                else Product(name="producto", price="")
            )

            if reference_images:
                return await loop.run_in_executor(
                    executor,
                    lambda: self.generate_with_image_refs(
                        prompt, reference_images, brand, product, output_dir, variant_number=idx + 1
                    ),
                )
            else:
                return await loop.run_in_executor(
                    executor,
                    lambda: self.generate(
                        prompt, brand, product, output_dir, variant_number=idx + 1
                    ),
                )

        # Crear todas las tareas
        tasks = [generate_one(i, prompt) for i, prompt in enumerate(prompts)]

        # Ejecutar con semáforo para limitar concurrencia
        semaphore = asyncio.Semaphore(max_concurrent)

        async def bounded_generate(idx: int, prompt: GenerationPrompt) -> GenerationResult:
            async with semaphore:
                return await generate_one(idx, prompt)

        tasks = [bounded_generate(i, prompt) for i, prompt in enumerate(prompts)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filtrar errores y calcular stats
        successful_results = []
        errors = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                errors.append((i, result))
                console.print(f"[red][X] Error en imagen {i + 1}: {result}[/red]")
            else:
                successful_results.append(result)

        executor.shutdown(wait=False)

        elapsed = time.time() - start_time
        total_cost = sum(r.cost_usd for r in successful_results)

        console.print("\n[bold green]Batch completado:[/bold green]")
        console.print(f"[dim]   Imágenes generadas: {len(successful_results)}/{len(prompts)}[/dim]")
        console.print(
            f"[dim]   Tiempo total: {elapsed:.1f}s ({elapsed / len(prompts):.1f}s/imagen)[/dim]"
        )
        console.print(f"[dim]   Costo total: ${total_cost:.4f}[/dim]")

        if errors:
            console.print(f"[yellow]   Errores: {len(errors)}[/yellow]")

        return successful_results

    def generate_batch_parallel_sync(
        self,
        prompts: list[GenerationPrompt],
        brand: Brand,
        products: dict[str, Product],
        output_dir: Path,
        reference_images: list[Path] | None = None,
        max_concurrent: int = 5,
    ) -> list[GenerationResult]:
        """
        Genera múltiples imágenes en paralelo usando threads (completamente síncrono).

        Args:
            prompts: Lista de prompts a generar
            brand: Marca
            products: Dict de slug -> Product
            output_dir: Directorio de salida
            reference_images: Imágenes de referencia compartidas
            max_concurrent: Máximo de generaciones simultáneas
        """
        import time
        from concurrent.futures import ThreadPoolExecutor, as_completed

        start_time = time.time()
        console.print(
            f"\n[bold blue]Generando {len(prompts)} imágenes en paralelo (max {max_concurrent})...[/bold blue]"
        )

        output_dir.mkdir(parents=True, exist_ok=True)
        product_list = list(products.values())

        def generate_one(idx: int, prompt: GenerationPrompt) -> GenerationResult | Exception:
            """Genera una imagen."""
            try:
                product = (
                    product_list[idx % len(product_list)]
                    if product_list
                    else Product(name="producto", price="")
                )
                if reference_images:
                    return self.generate_with_image_refs(
                        prompt, reference_images, brand, product, output_dir, variant_number=idx + 1
                    )
                else:
                    return self.generate(prompt, brand, product, output_dir, variant_number=idx + 1)
            except Exception as e:
                return e

        results = []
        errors = []

        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            futures = {executor.submit(generate_one, i, p): i for i, p in enumerate(prompts)}

            for future in as_completed(futures):
                idx = futures[future]
                result = future.result()
                if isinstance(result, Exception):
                    errors.append((idx, result))
                    console.print(f"[red][X] Error en imagen {idx + 1}: {result}[/red]")
                else:
                    results.append(result)

        elapsed = time.time() - start_time
        total_cost = sum(r.cost_usd for r in results)

        console.print("\n[bold green]Batch completado:[/bold green]")
        console.print(f"[dim]   Imágenes generadas: {len(results)}/{len(prompts)}[/dim]")
        console.print(f"[dim]   Tiempo total: {elapsed:.1f}s[/dim]")
        console.print(f"[dim]   Costo total: ${total_cost:.4f}[/dim]")

        return results

    def generate_with_image_refs(
        self,
        prompt: GenerationPrompt,
        reference_images: list[Path],
        brand: Brand,
        product: Product,
        output_dir: Path,
        variant_number: int = 1,
    ) -> GenerationResult:
        """
        Genera una imagen usando Responses API con imágenes de referencia.

        Args:
            prompt: Prompt de generación
            reference_images: Lista de paths a imágenes de referencia
            brand: Marca para el output
            product: Producto para el output
            output_dir: Directorio donde guardar la imagen
            variant_number: Número de variante

        Returns:
            GenerationResult con la imagen generada
        """
        generation_id = str(uuid.uuid4())[:8]

        console.print(
            f"\n[blue][Gen] {self.name}:[/blue] Generando variante {variant_number} con referencias..."
        )
        console.print(f"[dim]   Modelo: {self.model}[/dim]")
        console.print(f"[dim]   Referencias: {len(reference_images)} imagen(es)[/dim]")
        console.print(f"[dim]   Tamaño: {prompt.params.size}[/dim]")

        console.print("[dim]   Generando...[/dim]")

        # Preparar contenido con imágenes de referencia ETIQUETADAS
        content_parts = []

        # Detectar si hay logo (3ra imagen)
        has_logo = len(reference_images) >= 3

        # Instrucciones explícitas sobre las imágenes
        if has_logo:
            intro_text = f"""INSTRUCCIONES IMPORTANTES:

Vas a recibir 3 imágenes:
1. IMAGEN DE ESTILO: Usar como referencia para composición, iluminación, fondo y estilo visual
2. IMAGEN DEL PRODUCTO: Copiar este producto EXACTAMENTE - misma forma, colores, etiqueta, marca, TODO idéntico
3. LOGO DE LA MARCA: Insertar este logo en una esquina de la imagen (preferiblemente arriba a la derecha o izquierda)

El producto final DEBE verse EXACTAMENTE como el producto en la imagen 2, pero en el estilo/escena de la imagen 1.
El logo debe aparecer pequeño y elegante en una esquina, sin tapar el producto.

{prompt.get_full_prompt()}

RECORDATORIO FINAL:
- El producto debe ser una COPIA EXACTA de la imagen del producto. NO cambies la forma, marca, colores ni etiqueta del producto.
- El logo debe aparecer visible pero discreto en una esquina.
"""
        else:
            intro_text = f"""INSTRUCCIONES IMPORTANTES:

Vas a recibir 2 imágenes:
1. IMAGEN DE ESTILO: Usar como referencia para composición, iluminación, fondo y estilo visual
2. IMAGEN DEL PRODUCTO: Copiar este producto EXACTAMENTE - misma forma, colores, etiqueta, marca, TODO idéntico

El producto final DEBE verse EXACTAMENTE como el producto en la imagen 2, pero en el estilo/escena de la imagen 1.

{prompt.get_full_prompt()}

RECORDATORIO FINAL: El producto debe ser una COPIA EXACTA de la imagen del producto. NO cambies la forma, marca, colores ni etiqueta del producto.
"""
        content_parts.append({"type": "input_text", "text": intro_text})

        # Agregar imágenes de referencia CON ETIQUETAS
        for i, img_path in enumerate(reference_images):
            if not img_path.exists():
                console.print(f"[yellow][!] Imagen no encontrada: {img_path}[/yellow]")
                continue

            # Etiquetar cada imagen
            if i == 0:
                label = "IMAGEN 1 - ESTILO (copiar composición, iluminación, fondo):"
            elif i == 1:
                label = "IMAGEN 2 - PRODUCTO (copiar EXACTAMENTE este producto, misma forma/marca/etiqueta):"
            else:
                label = "IMAGEN 3 - LOGO (insertar este logo en una esquina de la imagen):"

            content_parts.append({"type": "input_text", "text": label})

            img_data = load_image_as_base64(img_path)
            media_type = get_image_media_type(img_path)

            content_parts.append(
                {"type": "input_image", "image_url": f"data:{media_type};base64,{img_data}"}
            )

        # Generar imagen usando Responses API
        try:
            # Mapear tamaño
            size_param = self._get_size_param(prompt.params.size)

            # DALL-E 3 no soporta Responses API, usar Image API fallback
            if self.model == "dall-e-3" or self.model == "dall-e-2":
                console.print(
                    "[yellow][!] DALL-E no soporta Responses API con referencias, usando generación simple[/yellow]"
                )
                return self.generate(prompt, brand, product, output_dir, variant_number)

            # Determinar modelo de chat según el modelo de imagen
            # Intentar con diferentes modelos según disponibilidad
            chat_models_to_try = ["gpt-4o-mini", "gpt-4-turbo", "gpt-4"]

            image_model = self.model

            # Si el usuario eligió gpt-image-1.5, usar ese
            if self.model == "gpt-image-1.5":
                image_model = "gpt-image-1.5"
            elif self.model == "gpt-image-1":
                image_model = "gpt-image-1"
            elif self.model == "gpt-image-1-mini":
                image_model = "gpt-image-1-mini"
            else:
                # Para otros casos, usar gpt-image-1 por default
                image_model = "gpt-image-1"

            # Intentar con diferentes modelos de chat
            response = None
            for chat_model in chat_models_to_try:
                try:
                    console.print(f"[dim]   Intentando con {chat_model}...[/dim]")
                    response = self.client.responses.create(
                        model=chat_model,
                        input=[{"role": "user", "content": content_parts}],
                        tools=[
                            {
                                "type": "image_generation",
                                "model": image_model,
                                "size": size_param,
                                "quality": prompt.params.quality
                                if prompt.params.quality != "auto"
                                else "medium",
                            }
                        ],
                    )
                    break  # Si llegamos aquí, funcionó
                except Exception as e:
                    error_str = str(e).lower()
                    if "403" in error_str or "not supported" in error_str or "tool" in error_str:
                        continue  # Probar siguiente modelo
                    else:
                        raise  # Error diferente, re-lanzar
            else:
                # Si todos los modelos de chat fallaron, hacer fallback a generación simple
                console.print(
                    "[yellow][!] Responses API no disponible, usando generación simple sin referencias[/yellow]"
                )
                return self.generate(prompt, brand, product, output_dir, variant_number)

            # Extraer imagen generada
            image_data = [
                output.result
                for output in response.output
                if output.type == "image_generation_call"
            ]

            if not image_data:
                raise ValueError("No se generó imagen en la respuesta")

            # Guardar imagen
            filename = f"{product.name}_v{variant_number}.png"
            image_path = output_dir / filename

            import io

            from PIL import Image

            image_bytes = base64.b64decode(image_data[0])
            img = Image.open(io.BytesIO(image_bytes))
            img.save(image_path, "PNG", quality=95)

            # Calcular costo
            cost = COST_PER_IMAGE.get(self.model, 0.05)

            # Crear resultado
            gen_result = GenerationResult(
                id=generation_id,
                image_path=image_path,
                prompt_used=prompt.get_full_prompt(),
                brand_name=brand.name,
                product_name=product.name,
                variant_number=variant_number,
                cost_usd=cost,
            )

            console.print(f"[green][OK][/green] Generado: {filename}")
            console.print(f"[dim]   Costo: ${cost:.4f}[/dim]")
            console.print(f"[dim]   Guardado en: {image_path}[/dim]")

            return gen_result

        except Exception as e:
            console.print(f"[red][X] Error:[/red] {str(e)}")
            raise
