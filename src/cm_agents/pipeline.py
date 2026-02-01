"""Pipeline orquestador - Conecta los 3 agentes."""

from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from .agents.architect import PromptArchitectAgent
from .agents.designer import DesignerAgent, DesignStyle
from .agents.extractor import ExtractorAgent
from .agents.generator import GeneratorAgent
from .models.brand import Brand
from .models.campaign_plan import CampaignPlan
from .models.generation import GenerationPrompt, GenerationResult
from .models.product import Product

console = Console(force_terminal=True, legacy_windows=False)


class GenerationPipeline:
    """Pipeline completo que conecta los 3 agentes."""

    def __init__(
        self,
        generator_model: str = "gpt-image-1.5",
        use_designer: bool = True,
        design_style: DesignStyle | None = None,
    ):
        """Inicializa el pipeline.

        Args:
            generator_model: Modelo de generación (default: gpt-image-1.5)
            use_designer: Si usar DesignerAgent (default: True) o PromptArchitectAgent
            design_style: Estilo de diseño (None = auto-detectar)
        """
        self.extractor = ExtractorAgent()
        self.use_designer = use_designer
        self.design_style = design_style

        if use_designer:
            self.prompt_agent = DesignerAgent()
        else:
            self.prompt_agent = PromptArchitectAgent()

        self.generator = GeneratorAgent(model=generator_model)

        console.print("[bold]Pipeline inicializado:[/bold]")
        console.print(f"  - {self.extractor.name}: {self.extractor.description}")
        console.print(f"  - {self.prompt_agent.name}: {self.prompt_agent.description}")
        console.print(f"  - {self.generator.name}: {self.generator.description}")
        if use_designer and design_style:
            console.print(f"  - Estilo: {design_style}")

    def run(
        self,
        reference_path: Path,
        brand_dir: Path,
        product_dir: Path,
        target_sizes: list[str] = ["feed"],
        include_text: bool = True,
        product_ref_path: Path | None = None,
        campaign_dir: Path | None = None,
        num_variants: int = 1,
        price_override: str | None = None,
    ) -> list[GenerationResult]:
        """
        Ejecuta el pipeline completo para generar imágenes.

        Args:
            reference_path: Path a la imagen de ESTILO (Pinterest)
            brand_dir: Path al directorio de la marca
            product_dir: Path al directorio del producto
            target_sizes: Lista de tamaños ["feed", "story"]
            include_text: Si agregar overlays de texto
            product_ref_path: Path a la imagen del PRODUCTO real (opcional)
            campaign_dir: Path a la campaña (opcional, para guardar outputs)

        Returns:
            Lista de GenerationResult con las imágenes generadas
        """
        # Determinar modo
        dual_mode = product_ref_path is not None
        mode_str = "Dual (estilo + producto)" if dual_mode else "Simple"

        console.print("\n")
        console.print(
            Panel(
                f"[bold]>> Iniciando Pipeline[/bold]\n"
                f"  Modo: {mode_str}\n"
                f"  Referencia estilo: {reference_path.name}\n"
                + (f"  Referencia producto: {product_ref_path.name}\n" if dual_mode else "")
                + f"  Tamanos: {', '.join(target_sizes)}\n"
                f"  Text overlay: {'Si' if include_text else 'No'}",
                title="Configuracion",
                border_style="blue",
            )
        )

        # 1. Cargar configuracion
        console.print("\n[bold]1. Cargando configuracion...[/bold]")
        brand = Brand.load(brand_dir)
        product = Product.load(product_dir)

        # Use price_override if provided (for campaign promos)
        display_price = price_override if price_override else product.price

        console.print(f"  [OK] Marca: {brand.name}")
        console.print(f"  [OK] Producto: {product.name}")
        console.print(f"  [OK] Precio: {display_price}")
        if price_override:
            console.print(f"  [blue][Promo][/blue] Precio override: {price_override}")

        # Cargar logo si existe
        logo_path = brand.get_logo_path(brand_dir)
        if logo_path:
            console.print(f"  [OK] Logo: {logo_path.name}")
        else:
            console.print("  [dim]Logo: No configurado[/dim]")

        # 2. Analizar referencia(s) (Extractor)
        console.print("\n[bold]2. Analizando referencia(s)...[/bold]")
        if dual_mode:
            reference_analysis = self.extractor.analyze_dual(reference_path, product_ref_path)
        else:
            reference_analysis = self.extractor.analyze(reference_path)

        # 3. Construir prompts (Designer/Architect)
        agent_name = "Designer" if self.use_designer else "Architect"
        console.print(f"\n[bold]3. Construyendo prompts ({agent_name})...[/bold]")
        if not product.has_visual_description():
            console.print(
                "[yellow][!] El producto no tiene visual_description."
                f" El {agent_name} va a inferir del nombre y descripcion.[/yellow]"
            )

        # Use price_override if provided (create modified product instance)
        product_for_prompt = product
        if price_override:
            # Create a copy of the product with overridden price
            import copy

            product_for_prompt = copy.deepcopy(product)
            product_for_prompt.price = price_override

        # Para cada tamaño, generar prompts
        all_prompts: list[GenerationPrompt] = []
        for size in target_sizes:
            if self.use_designer:
                prompts = self.prompt_agent.build_prompt(
                    reference_analysis, brand, product_for_prompt, size, style=self.design_style
                )
            else:
                prompts = self.prompt_agent.build_prompt(
                    reference_analysis, brand, product_for_prompt, size
                )
            all_prompts.append(prompts)

        # 4. Generar imagenes (Generator)
        console.print("\n[bold]4. Generando imagenes...[/bold]")

        # Preparar directorio de salida
        # Si hay campaña, guardar en campaigns/<name>/outputs/
        if campaign_dir:
            output_dir = campaign_dir / "outputs"
            console.print(f"[blue][Campaña][/blue] Output: {output_dir}")
        else:
            timestamp = datetime.now().strftime("%Y-%m-%d")
            output_dir = Path("outputs") / brand.name / timestamp
        output_dir.mkdir(parents=True, exist_ok=True)

        # Preparar lista de imágenes de referencia para Responses API
        # Orden: [estilo, producto, logo (opcional)]
        ref_images = []
        if dual_mode:
            ref_images = [reference_path, product_ref_path]
        else:
            ref_images = [reference_path]

        # Agregar logo si existe
        logo_path = brand.get_logo_path(brand_dir)
        if logo_path:
            ref_images.append(logo_path)

        # Generar imágenes: una por tamaño × num_variants
        results: list[GenerationResult] = []
        variant_counter = 1

        for size_idx, (base_prompt, size) in enumerate(zip(all_prompts, target_sizes), 1):
            # Ajustar tamaño base
            base_prompt.params.aspect_ratio = "4:5" if size == "feed" else "9:16"
            base_prompt.params.size = "1080x1350" if size == "feed" else "1080x1920"

            # Generar variantes para este tamaño
            if num_variants > 1:
                from ..services.variant_generator import VariantStrategy

                variant_prompts = VariantStrategy.create_diverse_variants(base_prompt, num_variants)
            else:
                # Sin variaciones, usar prompt base
                variant_prompts = [(base_prompt, "base")]

            for variant_prompt, variation_type in variant_prompts:
                # Usar Responses API con imágenes de referencia
                result = self.generator.generate_with_image_refs(
                    variant_prompt,
                    ref_images,
                    brand,
                    product,
                    output_dir,
                    variant_number=variant_counter,
                )
                results.append(result)
                variant_counter += 1

        # 5. Guardar metadatos (el texto ya viene integrado en la imagen generada)
        console.print("\n[bold]5. Guardando metadatos...[/bold]")
        for result in results:
            result.save_metadata()

        # Resumen
        total_cost = sum(r.cost_usd for r in results)
        console.print("\n")
        console.print(
            Panel(
                f"[bold green][OK] Pipeline completo![/bold green]\n\n"
                f"Imagenes generadas: {len(results)}\n"
                f"Directorio de salida: {output_dir}\n"
                f"Costo total: ${total_cost:.4f}",
                title="Resumen",
                border_style="green",
            )
        )

        return results

    def run_batch(
        self,
        reference_paths: list[Path],
        brand_dir: Path,
        product_dir: Path,
        target_size: str = "feed",
        include_text: bool = True,
    ) -> list[GenerationResult]:
        """
        Ejecuta el pipeline con múltiples referencias (una variante por referencia).

        Args:
            reference_paths: Lista de paths a referencias de Pinterest
            brand_dir: Path al directorio de la marca
            product_dir: Path al directorio del producto
            target_size: Tamaño objetivo ("feed" o "story")
            include_text: Si agregar overlays de texto

        Returns:
            Lista de GenerationResult (una por referencia)
        """
        console.print("\n")
        console.print(
            Panel(
                f"[bold]>> Pipeline Batch[/bold]\n"
                f"  Referencias: {len(reference_paths)}\n"
                f"  Tamano: {target_size}\n"
                f"  Text overlay: {'Si' if include_text else 'No'}",
                title="Configuracion",
                border_style="blue",
            )
        )

        # Cargar configuración
        brand = Brand.load(brand_dir)
        product = Product.load(product_dir)

        # Analizar todas las referencias
        analyses = self.extractor.analyze_batch(reference_paths)

        # Construir prompts
        if self.use_designer:
            prompts = self.prompt_agent.build_prompt_batch(
                analyses, brand, product, target_size, style=self.design_style
            )
        else:
            prompts = self.prompt_agent.build_prompts_batch(analyses, brand, product, target_size)

        # Generar imágenes
        timestamp = datetime.now().strftime("%Y-%m-%d")
        output_dir = Path("outputs") / brand.name / timestamp
        output_dir.mkdir(parents=True, exist_ok=True)

        results = self.generator.generate_batch(prompts, brand, product, output_dir)

        # Guardar metadatos (el texto ya viene integrado en la imagen generada)
        for result in results:
            result.save_metadata()

        # Resumen
        total_cost = sum(r.cost_usd for r in results)
        console.print("\n")
        console.print(
            Panel(
                f"[bold green][OK] Batch completo![/bold green]\n\n"
                f"Imagenes generadas: {len(results)}\n"
                f"Directorio de salida: {output_dir}\n"
                f"Costo total: ${total_cost:.4f}",
                title="Resumen",
                border_style="green",
            )
        )

        return results


class CampaignPipeline:
    """Pipeline optimizado para campañas - usa CreativeEngine + Generator batch.

    Flujo: CampaignPlan -> CreativeEngine (1 llamada) -> Generator (batch paralelo)

    Ventajas sobre GenerationPipeline:
    - 1 sola llamada a Claude analiza refs Y genera N prompts
    - Generación en paralelo (asyncio)
    - Coherencia visual garantizada entre imágenes de la campaña
    - ~6x más rápido para 7 imágenes
    """

    def __init__(self, generator_model: str = "gpt-image-1.5"):
        from .agents.creative_engine import CreativeEngine
        from .agents.generator import GeneratorAgent

        self.creative_engine = CreativeEngine()
        self.generator = GeneratorAgent(model=generator_model)

        console.print("[bold]CampaignPipeline inicializado:[/bold]")
        console.print(f"  - {self.creative_engine.name}: {self.creative_engine.description}")
        console.print(f"  - {self.generator.name}: {self.generator.description}")

    def run(
        self,
        campaign_plan: "CampaignPlan",
        brand_dir: Path,
        style_references: list[Path],
        output_dir: Path | None = None,
    ) -> list[GenerationResult]:
        """
        Ejecuta una campaña completa.

        Args:
            campaign_plan: Plan de campaña con días y temas
            brand_dir: Path al directorio de la marca
            style_references: Imágenes de referencia de estilo
            output_dir: Directorio de salida (default: outputs/{brand}/{fecha})

        Returns:
            Lista de GenerationResult con todas las imágenes generadas
        """

        console.print("\n")
        console.print(
            Panel(
                f"[bold]>> CampaignPipeline[/bold]\n"
                f"  Campaña: {campaign_plan.name}\n"
                f"  Días: {len(campaign_plan.days)}\n"
                f"  Productos: {len(campaign_plan.get_all_products())}\n"
                f"  Costo estimado: ${campaign_plan.estimated_cost_usd:.2f}",
                title="Configuración",
                border_style="blue",
            )
        )

        # 1. Cargar configuración
        console.print("\n[bold]1. Cargando configuración...[/bold]")
        brand = Brand.load(brand_dir)
        console.print(f"  [OK] Marca: {brand.name}")

        # Cargar productos
        products: dict[str, Product] = {}
        product_photos: dict[str, Path] = {}
        products_dir = Path("products") / brand_dir.name

        for product_slug in campaign_plan.get_all_products():
            product_dir = products_dir / product_slug
            if product_dir.exists():
                product = Product.load(product_dir)
                products[product_slug] = product
                # Buscar foto del producto
                try:
                    photo = product.get_main_photo(product_dir)
                    product_photos[product_slug] = photo
                    console.print(f"  [OK] Producto: {product.name} (con foto)")
                except ValueError:
                    console.print(f"  [yellow][!] Producto {product_slug} sin foto[/yellow]")
            else:
                console.print(f"  [yellow][!] Producto {product_slug} no encontrado[/yellow]")

        # Logo
        logo_path = brand.get_logo_path(brand_dir)
        if logo_path:
            console.print(f"  [OK] Logo: {logo_path.name}")

        # 2. Generar prompts con CreativeEngine (1 sola llamada)
        console.print("\n[bold]2. Generando prompts con CreativeEngine...[/bold]")
        prompts = self.creative_engine.create_campaign_prompts(
            campaign_plan=campaign_plan,
            style_references=style_references,
            product_references=product_photos,
            brand=brand,
            products=products,
        )

        # 3. Preparar directorio de salida
        if output_dir is None:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
            output_dir = Path("outputs") / brand.name / f"campaign_{timestamp}"
        output_dir.mkdir(parents=True, exist_ok=True)
        console.print(f"\n[bold]3. Output:[/bold] {output_dir}")

        # 4. Preparar referencias para el Generator
        ref_images = list(style_references[:2])  # Max 2 referencias de estilo
        # Agregar primera foto de producto
        if product_photos:
            ref_images.append(list(product_photos.values())[0])
        # Agregar logo
        if logo_path:
            ref_images.append(logo_path)

        # 5. Generar imágenes en paralelo
        console.print("\n[bold]4. Generando imágenes en paralelo...[/bold]")
        results = self.generator.generate_batch_parallel_sync(
            prompts=prompts,
            brand=brand,
            products=products,
            output_dir=output_dir,
            reference_images=ref_images,
            max_concurrent=5,
        )

        # 6. Guardar metadatos
        console.print("\n[bold]5. Guardando metadatos...[/bold]")
        for result in results:
            result.save_metadata()

        # Resumen
        total_cost = sum(r.cost_usd for r in results)
        console.print("\n")
        console.print(
            Panel(
                f"[bold green][OK] Campaña completada![/bold green]\n\n"
                f"Imágenes generadas: {len(results)}/{len(campaign_plan.days)}\n"
                f"Directorio de salida: {output_dir}\n"
                f"Costo total: ${total_cost:.4f}",
                title="Resumen",
                border_style="green",
            )
        )

        return results

    def run_with_pinterest_search_sync(
        self,
        campaign_plan: "CampaignPlan",
        brand_dir: Path,
        pinterest_query: str,
        output_dir: Path | None = None,
        num_references: int = 3,
    ) -> list[GenerationResult]:
        """
        Ejecuta campaña buscando referencias en Pinterest (versión síncrona).

        Args:
            campaign_plan: Plan de campaña
            brand_dir: Path a la marca
            pinterest_query: Query para buscar en Pinterest
            output_dir: Directorio de salida
            num_references: Cuántas referencias descargar
        """
        from .services.mcp_client import search_pinterest_sync

        console.print("\n[bold blue]Buscando referencias en Pinterest...[/bold blue]")
        console.print(f"[dim]   Query: {pinterest_query}[/dim]")

        # Buscar y descargar referencias (síncrono)
        try:
            results = search_pinterest_sync(
                query=pinterest_query,
                limit=num_references,
                download=True,
            )
            console.print(f"[green][OK][/green] {len(results)} referencias encontradas")
        except Exception as e:
            console.print(f"[yellow][!] Pinterest search failed: {e}[/yellow]")
            console.print("[yellow]   Usando referencias existentes...[/yellow]")
            results = []

        # Obtener paths de las imágenes descargadas
        style_references = []
        refs_dir = Path("references")
        if refs_dir.exists():
            downloaded = sorted(
                list(refs_dir.glob("*.jpg"))
                + list(refs_dir.glob("*.png"))
                + list(refs_dir.glob("*.webp")),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            style_references = downloaded[:num_references]
            console.print(f"[dim]   Referencias: {[p.name for p in style_references]}[/dim]")

        if not style_references:
            console.print("[red][X] No hay referencias de estilo disponibles[/red]")
            return []

        # Ejecutar pipeline normal
        return self.run(
            campaign_plan=campaign_plan,
            brand_dir=brand_dir,
            style_references=style_references,
            output_dir=output_dir,
        )

    def run_with_inpainting(
        self,
        campaign_plan: "CampaignPlan",
        brand_dir: Path,
        product_photos: dict[str, Path],
        output_dir: Path | None = None,
        product_scale: float | None = None,
        product_position: str | None = None,
        use_cascade: bool = True,
    ) -> list[GenerationResult]:
        """
        Ejecuta campaña con INPAINTING - integración realista del producto.

        A diferencia del compositing simple, el inpainting permite que el
        modelo AI integre el producto con sombras, reflejos y perspectiva
        coherentes con la escena.

        Flujo:
        1. CreativeEngine genera prompts para escenas
        2. Para cada imagen:
           a. Genera escena con área vacía para producto
           b. Usa inpainting para "pintar" el producto real
           c. Si cascade=True, usa imagen anterior como referencia de estilo

        Args:
            campaign_plan: Plan de la campaña
            brand_dir: Path al directorio de la marca
            product_photos: Dict {product_slug: Path} con fotos REALES del producto
            output_dir: Directorio de salida
            product_scale: Escala del producto (0.3-0.5 recomendado)
            product_position: "center", "left", "right", "bottom-center"
            use_cascade: Si usar cascada de referencias para coherencia

        Returns:
            Lista de GenerationResult con imágenes finales
        """
        from .services.inpainting_compositor import (
            get_cascade_manager,
            get_inpainting_compositor,
        )

        console.print("\n")
        console.print(
            Panel(
                f"[bold]>> CampaignPipeline con Inpainting[/bold]\n"
                f"  Campaña: {campaign_plan.name}\n"
                f"  Días: {len(campaign_plan.days)}\n"
                f"  Productos con foto: {len(product_photos)}\n"
                f"  Modo: INPAINTING (integración realista)\n"
                f"  Cascada de estilo: {'Sí' if use_cascade else 'No'}",
                title="Configuración",
                border_style="magenta",
            )
        )

        # Validar que hay fotos de producto
        if not product_photos:
            raise ValueError(
                "Se requiere al menos una foto de producto para inpainting. "
                "Proporciona product_photos={slug: path}"
            )

        # Obtener valores del StyleGuide si existen, o usar defaults
        style_guide = campaign_plan.style_guide
        if style_guide:
            # Usar configuración del StyleGuide
            effective_position = product_position or style_guide.product.position
            effective_scale = (
                product_scale if product_scale is not None else style_guide.product.scale
            )
            console.print(f"[blue][StyleGuide][/blue] {style_guide.name}")
            console.print(f"[dim]   Base style: {style_guide.base_style}[/dim]")
            console.print(f"[dim]   Product: {effective_position}, scale={effective_scale}[/dim]")
        else:
            # Defaults
            effective_position = product_position or "center"
            effective_scale = product_scale if product_scale is not None else 0.4
            console.print("[yellow][!] No StyleGuide - using defaults[/yellow]")

        # 1. Cargar configuración
        console.print("\n[bold]1. Cargando configuración...[/bold]")
        brand = Brand.load(brand_dir)
        console.print(f"  [OK] Marca: {brand.name}")

        # Cargar productos
        products: dict[str, Product] = {}
        products_dir = Path("products") / brand_dir.name

        for product_slug in campaign_plan.get_all_products():
            product_dir = products_dir / product_slug
            if product_dir.exists():
                product = Product.load(product_dir)
                products[product_slug] = product
                has_photo = product_slug in product_photos
                status = "[green]con foto[/green]" if has_photo else "[yellow]sin foto[/yellow]"
                console.print(f"  [OK] Producto: {product.name} ({status})")
            else:
                console.print(f"  [yellow][!] Producto {product_slug} no encontrado[/yellow]")

        # Logo
        logo_path = brand.get_logo_path(brand_dir)
        if logo_path:
            console.print(f"  [OK] Logo: {logo_path.name}")

        # 2. Generar prompts con CreativeEngine
        console.print("\n[bold]2. Generando prompts con CreativeEngine...[/bold]")
        prompts = self.creative_engine.create_campaign_prompts(
            campaign_plan=campaign_plan,
            style_references=[],
            product_references=product_photos,
            brand=brand,
            products=products,
        )

        # 3. Preparar directorio de salida
        if output_dir is None:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
            output_dir = Path("outputs") / brand.name / f"campaign_inpaint_{timestamp}"
        output_dir.mkdir(parents=True, exist_ok=True)
        console.print(f"\n[bold]3. Output:[/bold] {output_dir}")

        # 4. Inicializar servicios
        inpainter = get_inpainting_compositor(model=self.generator.model)
        cascade_manager = get_cascade_manager() if use_cascade else None

        # Configurar StyleGuide en el CascadeStyleManager
        if cascade_manager and style_guide:
            cascade_manager.set_style_guide(style_guide)
            console.print("[blue][Cascade][/blue] StyleGuide aplicado al gestor de coherencia")

        # 5. Generar imágenes con inpainting
        console.print("\n[bold]4. Generando imágenes con inpainting...[/bold]")

        results: list[GenerationResult] = []
        product_list = list(product_photos.items())
        total_cost = 0.0

        for i, prompt in enumerate(prompts):
            # Seleccionar producto
            product_slug, photo_path = product_list[i % len(product_list)]
            product = products.get(product_slug, Product(name=product_slug, price=""))

            console.print(f"\n[bold cyan]Imagen {i + 1}/{len(prompts)}[/bold cyan]")
            console.print(f"[dim]   Producto: {product.name}[/dim]")

            try:
                # Preparar prompt con cascada si corresponde
                scene_prompt = prompt.get_full_prompt()
                if cascade_manager and i > 0:
                    scene_prompt, _ = cascade_manager.prepare_cascaded_generation(
                        scene_prompt, is_first=False
                    )

                # Generar con inpainting
                filename = f"{product.name}_v{i + 1}.png"
                output_path = output_dir / filename

                final_path, cost = inpainter.generate_with_inpainting(
                    scene_prompt=scene_prompt,
                    product_photo=photo_path,
                    product_description=product.visual_description
                    or f"{product.name} - {product.description}",
                    output_path=output_path,
                    size="1024x1536",  # Formato vertical para social
                    position=effective_position,
                    product_scale=effective_scale,
                )

                total_cost += cost

                # Actualizar cascada con la imagen generada
                if cascade_manager and i == 0:
                    cascade_manager.set_anchor(final_path)

                # Crear resultado
                import uuid

                gen_result = GenerationResult(
                    id=str(uuid.uuid4())[:8],
                    image_path=final_path,
                    prompt_used=scene_prompt,
                    brand_name=brand.name,
                    product_name=product.name,
                    variant_number=i + 1,
                    cost_usd=cost,
                )
                results.append(gen_result)

            except Exception as e:
                console.print(f"[red][X] Error en imagen {i + 1}: {e}[/red]")
                import traceback

                traceback.print_exc()

        # 6. Guardar metadatos
        console.print("\n[bold]5. Guardando metadatos...[/bold]")
        for result in results:
            result.save_metadata()

        # Resumen
        console.print("\n")
        console.print(
            Panel(
                f"[bold green][OK] Campaña completada![/bold green]\n\n"
                f"Imágenes generadas: {len(results)}/{len(prompts)}\n"
                f"Directorio de salida: {output_dir}\n"
                f"Costo total: ${total_cost:.4f}\n\n"
                f"[magenta]Modo: INPAINTING (integración realista)[/magenta]\n"
                f"[dim]Cascada de estilo: {'Activada' if use_cascade else 'Desactivada'}[/dim]",
                title="Resumen",
                border_style="green",
            )
        )

        return results

    def run_direct(
        self,
        campaign_plan: "CampaignPlan",
        brand_dir: Path,
        product_image: Path,
        pinterest_refs: list[Path],
        output_dir: Path | None = None,
        use_cascade: bool = True,
    ) -> list[GenerationResult]:
        """
        Ejecuta campaña usando DirectGenerator (Responses API).

        Flujo:
        1. Para cada día del plan:
           a) Genera imagen BASE (producto + escena, sin texto)
           b) Agrega texto profesional con AI (headline, precio)
        2. CascadeStyleManager mantiene coherencia entre días

        Args:
            campaign_plan: Plan de campaña con días y StyleGuide
            brand_dir: Directorio de la marca
            product_image: Imagen del producto (subida por usuario)
            pinterest_refs: Referencias de Pinterest para estilo
            output_dir: Directorio de salida
            use_cascade: Si usar coherencia visual entre días

        Returns:
            Lista de GenerationResult con imágenes finales
        """
        from .models.brand import Brand
        from .models.product import Product
        from .services.direct_generator import get_direct_generator
        from .services.inpainting_compositor import get_cascade_manager

        console.print("\n")
        console.print(
            Panel(
                f"[bold magenta]Campaña: {campaign_plan.name}[/bold magenta]\n"
                f"Días: {len(campaign_plan.days)}\n"
                f"Modo: [bold]DIRECT (Responses API)[/bold]\n"
                f"Coherencia visual: {'Activada' if use_cascade else 'Desactivada'}",
                title="Direct Generation",
                border_style="magenta",
            )
        )

        # 1. Cargar marca y producto
        console.print("\n[bold]1. Cargando configuración...[/bold]")
        brand = Brand.load(brand_dir)
        console.print(f"   [green][OK][/green] Marca: {brand.name}")

        # Crear producto desde imagen
        product = Product(
            name=product_image.stem,
            price=brand.text_overlay.price_badge.text_color if brand.text_overlay else "",
        )
        console.print(f"   [green][OK][/green] Producto: {product.name}")
        console.print(f"   [green][OK][/green] Pinterest refs: {len(pinterest_refs)}")

        # 2. Obtener StyleGuide
        style_guide = campaign_plan.style_guide
        if style_guide:
            console.print(f"\n[bold]2. StyleGuide:[/bold] {style_guide.name}")
            console.print(f"   Estilo: {style_guide.base_style}")
            console.print(f"   Iluminación: {style_guide.lighting_style}")
        else:
            console.print("\n[yellow][!] Sin StyleGuide - usando defaults[/yellow]")

        # 3. Preparar output
        if output_dir is None:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
            output_dir = Path("outputs") / brand.name / f"campaign_direct_{timestamp}"
        output_dir.mkdir(parents=True, exist_ok=True)
        console.print(f"\n[bold]3. Output:[/bold] {output_dir}")

        # 4. Inicializar DirectGenerator y CascadeManager
        generator = get_direct_generator(model="gpt-image-1.5")
        cascade_manager = get_cascade_manager() if use_cascade else None

        if cascade_manager and style_guide:
            cascade_manager.set_style_guide(style_guide)

        # 5. Generar imágenes por día
        console.print("\n[bold]4. Generando imágenes...[/bold]")

        results: list[GenerationResult] = []
        total_cost = 0.0

        for i, day_plan in enumerate(campaign_plan.days):
            console.print(f"\n[bold cyan]═══ Día {day_plan.day}: {day_plan.theme} ═══[/bold cyan]")

            # Determinar headline según el tema del día
            headline = self._get_headline_for_theme(day_plan.theme, campaign_plan.name)
            subheadline = self._get_subheadline_for_theme(day_plan.theme, day_plan.urgency_level)

            console.print(f"   Headline: {headline}")
            if subheadline:
                console.print(f"   Subheadline: {subheadline}")

            # Construir scene_prompt basado en el día
            scene_prompt = self._build_scene_prompt(
                day_plan=day_plan,
                style_guide=style_guide,
                coherence=campaign_plan.visual_coherence,
            )

            # Si es el primer día y usamos cascada, preparar para coherencia
            effective_refs = pinterest_refs
            if cascade_manager and i > 0:
                # Obtener referencia de estilo del anchor
                style_ref_prompt = cascade_manager.get_style_reference_prompt()
                scene_prompt = f"{scene_prompt}\n\nSTYLE CONTINUITY: {style_ref_prompt}"

            try:
                # Generar imagen completa (base + texto)
                final_path, cost = generator.generate_complete(
                    product_image=product_image,
                    pinterest_refs=effective_refs,
                    scene_prompt=scene_prompt,
                    style_guide=style_guide,
                    product=product,
                    headline=headline,
                    subheadline=subheadline,
                    show_price=True,
                    output_dir=output_dir,
                    variant_number=i + 1,
                )

                total_cost += cost

                # Si es el primer día, establecer como anchor para coherencia
                if cascade_manager and i == 0:
                    cascade_manager.set_anchor(final_path)
                    console.print("[blue][Cascade][/blue] Imagen anchor establecida")

                # Crear resultado
                import uuid

                gen_result = GenerationResult(
                    id=str(uuid.uuid4())[:8],
                    image_path=final_path,
                    prompt_used=scene_prompt,
                    brand_name=brand.name,
                    product_name=product.name,
                    variant_number=i + 1,
                    cost_usd=cost,
                )
                results.append(gen_result)

            except Exception as e:
                console.print(f"[red][X] Error en día {day_plan.day}: {e}[/red]")
                import traceback

                traceback.print_exc()

        # 6. Resumen final
        console.print("\n")
        console.print(
            Panel(
                f"[bold green][OK] Campaña completada![/bold green]\n\n"
                f"Imágenes generadas: {len(results)}/{len(campaign_plan.days)}\n"
                f"Directorio de salida: {output_dir}\n"
                f"Costo total: ${total_cost:.4f}\n\n"
                f"[magenta]Modo: DIRECT (Responses API + Text Overlay AI)[/magenta]\n"
                f"[dim]Coherencia visual: {'Activada' if use_cascade else 'Desactivada'}[/dim]",
                title="Resumen",
                border_style="green",
            )
        )

        return results

    def run_reference_driven_campaign(
        self,
        product_ref: Path,
        scene_ref: Path,
        font_ref: Path,
        brand_dir: Path,
        campaign_plan: CampaignPlan | None = None,
        output_dir: Path | None = None,
        product_name: str | None = None,
        price: str = "",
        size: str = "1024x1536",
        campaign_title: str | None = None,
    ) -> list[GenerationResult]:
        """
        Campaña por referencias: 1 producto + 1 escena + 1 fuente.

        Flujo:
        1. Genera fondo + producto en una sola llamada (replica exacta).
        2. Por cada día: agrega texto (headline/copy del día) con referencia de fuente.

        Args:
            product_ref: Imagen del producto (replica exacta).
            scene_ref: Imagen de la escena/fondo.
            font_ref: Imagen de referencia de tipografía.
            brand_dir: Directorio de la marca.
            campaign_plan: Plan con N días (None = 3 días por defecto: teaser, main_offer, last_chance).
            output_dir: Directorio de salida.
            product_name: Nombre del producto (default: stem de product_ref).
            price: Precio a mostrar (default: vacío).
            size: Tamaño de imagen (ej. 1024x1536).
            campaign_title: Título de campaña para headlines (ej. "BLACK FRIDAY"). Si no se pasa y el plan es por defecto, se usa "PROMO".

        Returns:
            Lista de GenerationResult (una por día).
        """
        from .models.brand import Brand
        from .models.campaign_style import CampaignStyleGuide, get_preset
        from .models.product import Product
        from .services.direct_generator import get_direct_generator

        console.print("\n")
        console.print(
            Panel(
                f"[bold magenta]Campaña por referencias[/bold magenta]\n"
                f"Producto: {product_ref.name}\n"
                f"Escena: {scene_ref.name}\n"
                f"Fuente: {font_ref.name}\n"
                f"Modo: fondo + producto (una llamada) + texto por día",
                title="Reference-driven campaign",
                border_style="magenta",
            )
        )

        # Plan por defecto: 3 días
        if campaign_plan is None:
            from .models.campaign_plan import DayPlan, VisualCoherence

            plan_name = (campaign_title or "PROMO").strip() or "PROMO"
            campaign_plan = CampaignPlan(
                name=plan_name,
                brand_slug=brand_dir.name,
                days=[
                    DayPlan(day=1, theme="teaser", visual_direction="mysterious"),
                    DayPlan(day=2, theme="main_offer", visual_direction="bold"),
                    DayPlan(day=3, theme="last_chance", visual_direction="urgent"),
                ],
                visual_coherence=VisualCoherence(),
                style_guide=get_preset("black_friday"),
            )

        brand = Brand.load(brand_dir)
        style_guide = campaign_plan.style_guide or get_preset("promo")
        product = Product(
            name=product_name or product_ref.stem,
            price=price or "",
        )

        if output_dir is None:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
            output_dir = Path("outputs") / brand.name / f"campaign_refs_{timestamp}"
        output_dir.mkdir(parents=True, exist_ok=True)
        console.print(f"\n[bold]Output:[/bold] {output_dir}")

        generator = get_direct_generator(model="gpt-image-1.5")

        # 1. Generar escena + producto UNA vez (replica)
        console.print("\n[bold]1. Generando escena + producto (una llamada)...[/bold]")
        base_path = output_dir / f"{product.name}_base.png"
        base_path, cost_base = generator.generate_scene_with_product(
            product_ref=product_ref,
            scene_ref=scene_ref,
            output_path=base_path,
            size=size,
            style_guide=style_guide,
        )
        total_cost = cost_base

        # 2. Por cada día: agregar texto (headline/copy) con font_ref
        console.print("\n[bold]2. Agregando texto por día...[/bold]")
        results: list[GenerationResult] = []
        total_cost = 0.0

        for i, day_plan in enumerate(campaign_plan.days):
            headline = self._get_headline_for_theme(day_plan.theme, campaign_plan.name)
            subheadline = self._get_subheadline_for_theme(day_plan.theme, day_plan.urgency_level)
            display_price = day_plan.price_override or product.price

            product_for_day = Product(name=product.name, price=display_price)
            final_path = output_dir / f"{product.name}_day{day_plan.day}.png"

            try:
                final_path, cost = generator.add_text_overlay(
                    base_image=base_path,
                    style_guide=style_guide,
                    product=product_for_day,
                    headline=headline,
                    subheadline=subheadline,
                    show_price=bool(display_price),
                    output_path=final_path,
                    font_ref=font_ref,
                )
                total_cost += cost
                import uuid

                results.append(
                    GenerationResult(
                        id=str(uuid.uuid4())[:8],
                        image_path=final_path,
                        prompt_used=f"refs: {product_ref.name} + {scene_ref.name} + {font_ref.name}",
                        brand_name=brand.name,
                        product_name=product.name,
                        variant_number=day_plan.day,
                        cost_usd=cost,
                    )
                )
            except Exception as e:
                console.print(f"[red][X] Error día {day_plan.day}: {e}[/red]")
                import traceback

                traceback.print_exc()

        for r in results:
            r.save_metadata()

        console.print("\n")
        console.print(
            Panel(
                f"[bold green][OK] Campaña por referencias completada[/bold green]\n\n"
                f"Imágenes: {len(results)}/{len(campaign_plan.days)}\n"
                f"Output: {output_dir}\n"
                f"Costo total: ${total_cost:.4f}",
                title="Resumen",
                border_style="green",
            )
        )
        return results

    def _get_headline_for_theme(self, theme: str, campaign_name: str) -> str:
        """Genera headline según el tema del día."""
        headlines = {
            "teaser": "COMING SOON",
            "countdown": "STARTS TOMORROW",
            "reveal": campaign_name.upper(),
            "anticipation": "GET READY",
            "main_offer": campaign_name.upper(),
            "extended": "EXTENDED",
            "last_chance": "LAST CHANCE",
            "cyber_monday": "CYBER MONDAY",
            "closing": "FINAL HOURS",
        }
        return headlines.get(theme, campaign_name.upper())

    def _get_subheadline_for_theme(self, theme: str, urgency: str) -> str | None:
        """Genera subheadline según tema y urgencia."""
        subheadlines = {
            "teaser": "Something big is coming",
            "countdown": "Don't miss out",
            "main_offer": "Limited time offer",
            "extended": "One more chance",
            "last_chance": "Ends tonight",
            "closing": "Don't miss it",
        }

        # Agregar urgencia si es alta
        base = subheadlines.get(theme)
        if urgency in ["high", "critical"] and base:
            return f"{base}!"
        return base

    def _build_scene_prompt(
        self,
        day_plan,
        style_guide,
        coherence,
    ) -> str:
        """Construye prompt de escena para el día."""

        # Base del prompt
        mood_map = {
            "teaser": "mysterious, anticipation, subtle hints",
            "countdown": "exciting, building tension, dynamic",
            "reveal": "dramatic reveal, impactful, celebration",
            "main_offer": "bold, confident, premium quality",
            "extended": "continued celebration, opportunity",
            "last_chance": "urgent, final opportunity, dramatic",
            "closing": "finale, grand conclusion, memorable",
        }

        mood = mood_map.get(day_plan.theme, "professional, appealing")

        prompt_parts = [
            f"Create a {day_plan.theme} promotional scene.",
            f"Mood: {mood}",
            f"Visual direction: {day_plan.visual_direction}",
        ]

        # Agregar estilo si hay StyleGuide
        if style_guide:
            prompt_parts.extend(
                [
                    f"Style: {style_guide.base_style}",
                    f"Lighting: {style_guide.lighting_style}",
                    f"Atmosphere: {style_guide.atmosphere}",
                ]
            )

        # Agregar coherencia visual
        if coherence:
            prompt_parts.append(f"Consistent elements: {', '.join(coherence.consistent_elements)}")

        return "\n".join(prompt_parts)
