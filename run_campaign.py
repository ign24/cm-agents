#!/usr/bin/env python
"""Script para ejecutar una campaña completa.

Uso:
    python run_campaign.py [--mode direct|inpainting]

Modos disponibles:

DIRECT (nuevo, recomendado):
    - Usuario sube 1 imagen del producto
    - Pinterest busca referencias de estilo
    - Responses API genera imagen base (producto + escena, sin texto)
    - Responses API agrega texto profesional (headline, precio)
    - CascadeStyleManager mantiene coherencia entre días

INPAINTING (legacy):
    - Genera escenas publicitarias con área vacía para el producto
    - Usa AI para "pintar" el producto REAL en la escena
    - El producto se integra con sombras, reflejos y perspectiva

Requiere:
    - ANTHROPIC_API_KEY en .env
    - OPENAI_API_KEY en .env
    - Foto de producto en products/{brand}/{product}/photos/
"""

import argparse
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

console = Console(force_terminal=True, legacy_windows=False)


def get_pinterest_refs(brand_dir: Path) -> list[Path]:
    """Busca referencias de Pinterest descargadas."""
    refs_dir = brand_dir / "references"
    if not refs_dir.exists():
        # Buscar en directorio global de referencias
        refs_dir = Path("references")

    if refs_dir.exists():
        refs = (
            list(refs_dir.glob("*.jpg"))
            + list(refs_dir.glob("*.png"))
            + list(refs_dir.glob("*.webp"))
        )
        # Ordenar por fecha de modificación (más recientes primero)
        refs = sorted(refs, key=lambda p: p.stat().st_mtime, reverse=True)
        return refs[:5]  # Máximo 5 referencias

    return []


def run_direct_mode(
    brand_dir: Path,
    product_image: Path,
    campaign_name: str,
    days: int,
    skip_confirm: bool = False,
):
    """Ejecuta campaña en modo DIRECT (Responses API)."""
    from cm_agents.agents.strategist import StrategistAgent
    from cm_agents.models.brand import Brand
    from cm_agents.pipeline import CampaignPipeline

    console.print(
        Panel(
            f"[bold magenta]Campaña: {campaign_name}[/bold magenta]\n"
            f"Marca: {brand_dir.name}\n"
            f"Días: {days}\n"
            f"Producto: {product_image.name}\n\n"
            f"[bold]Modo: DIRECT (Responses API)[/bold]\n"
            f"(Imagen base + Texto AI profesional)",
            title="Configuración",
            border_style="magenta",
        )
    )

    # 1. Cargar marca
    console.print("\n[bold]1. Cargando marca...[/bold]")
    brand = Brand.load(brand_dir)
    console.print(f"   [green][OK][/green] {brand.name}")

    # 2. Verificar imagen del producto
    console.print("\n[bold]2. Imagen del producto...[/bold]")
    if not product_image.exists():
        console.print(f"[red][ERROR] No se encuentra: {product_image}[/red]")
        return
    console.print(f"   [green][OK][/green] {product_image}")

    # 3. Buscar referencias de Pinterest
    console.print("\n[bold]3. Referencias de Pinterest...[/bold]")
    pinterest_refs = get_pinterest_refs(brand_dir)
    if pinterest_refs:
        for ref in pinterest_refs[:3]:
            console.print(f"   [green][OK][/green] {ref.name}")
        console.print(f"   Total: {len(pinterest_refs)} referencias")
    else:
        console.print(
            "   [yellow][!][/yellow] Sin referencias - se usará solo el estilo del StyleGuide"
        )

    # 4. Crear plan de campaña
    console.print("\n[bold]4. Creando plan de campaña...[/bold]")
    strategist = StrategistAgent()
    campaign_plan = strategist.plan_campaign(
        prompt=f"{campaign_name} {days} dias",
        brand=brand,
        brand_dir=brand_dir,
        days=days,
        products=[product_image.stem],
    )

    console.print(f"   [green][OK][/green] Plan creado: {campaign_plan.name}")
    console.print(f"   Días: {len(campaign_plan.days)}")

    # Mostrar StyleGuide
    if campaign_plan.style_guide:
        sg = campaign_plan.style_guide
        console.print(f"\n[bold blue]StyleGuide:[/bold blue] {sg.name}")
        console.print(f"   Estilo base: {sg.base_style}")
        console.print(f"   Iluminación: {sg.lighting_style}")
        console.print(f"   Colores: {sg.primary_color}, {sg.accent_color}, {sg.highlight_color}")

    # Mostrar plan
    console.print("\n[bold]Plan de campaña:[/bold]")
    for day in campaign_plan.days:
        console.print(f"   Día {day.day}: {day.theme} | Urgencia: {day.urgency_level}")

    # 5. Confirmar
    if not skip_confirm:
        console.print("\n")
        confirm = Prompt.ask("¿Ejecutar campaña en modo DIRECT?", choices=["s", "n"], default="s")
        if confirm != "s":
            console.print("[yellow]Cancelado[/yellow]")
            return

    # 6. Ejecutar pipeline DIRECT
    console.print("\n[bold]5. Ejecutando pipeline DIRECT...[/bold]")
    pipeline = CampaignPipeline()

    try:
        results = pipeline.run_direct(
            campaign_plan=campaign_plan,
            brand_dir=brand_dir,
            product_image=product_image,
            pinterest_refs=pinterest_refs,
            use_cascade=True,
        )

        # Mostrar resultados
        console.print("\n")
        console.print(
            Panel(
                f"[bold green]Campaña completada[/bold green]\n\n"
                f"Imágenes generadas: {len(results)}\n"
                f"Costo total: ${sum(r.cost_usd for r in results):.2f}\n\n"
                f"[bold magenta]Modo: DIRECT (Responses API + Text AI)[/bold magenta]\n\n"
                f"[bold]Archivos:[/bold]\n" + "\n".join(f"  - {r.image_path}" for r in results),
                title="Resultados",
                border_style="green",
            )
        )

    except Exception as e:
        console.print(f"\n[red][ERROR] {e}[/red]")
        import traceback

        traceback.print_exc()


def run_inpainting_mode(
    brand_dir: Path,
    products_dir: Path,
    product_slugs: list[str],
    campaign_name: str,
    days: int,
    skip_confirm: bool = False,
):
    """Ejecuta campaña en modo INPAINTING (legacy)."""
    from cm_agents.agents.strategist import StrategistAgent
    from cm_agents.models.brand import Brand
    from cm_agents.pipeline import CampaignPipeline

    console.print(
        Panel(
            f"[bold magenta]Campaña: {campaign_name}[/bold magenta]\n"
            f"Marca: {brand_dir.name}\n"
            f"Días: {days}\n"
            f"Productos: {', '.join(product_slugs)}\n\n"
            f"[bold]Modo: INPAINTING[/bold]\n"
            f"(Integración realista con sombras y reflejos)",
            title="Configuración",
            border_style="magenta",
        )
    )

    # 1. Cargar marca
    console.print("\n[bold]1. Cargando marca...[/bold]")
    brand = Brand.load(brand_dir)
    console.print(f"   [green][OK][/green] {brand.name}")

    # 2. Cargar fotos de producto
    console.print("\n[bold]2. Cargando fotos de producto...[/bold]")
    product_photos: dict[str, Path] = {}

    for product_slug in product_slugs:
        product_dir = products_dir / product_slug
        photo_patterns = ["photos/product.webp", "photos/product.jpg", "photos/product.png"]
        for pattern in photo_patterns:
            photo_path = product_dir / pattern
            if photo_path.exists():
                product_photos[product_slug] = photo_path
                console.print(f"   [green][OK][/green] {product_slug}: {photo_path.name}")
                break
        else:
            console.print(f"   [yellow][!][/yellow] {product_slug}: Sin foto")

    if not product_photos:
        console.print("[red][ERROR] No hay fotos de producto disponibles[/red]")
        return

    # 3. Crear plan
    console.print("\n[bold]3. Creando plan de campaña...[/bold]")
    strategist = StrategistAgent()
    campaign_plan = strategist.plan_campaign(
        prompt=f"{campaign_name} {days} dias",
        brand=brand,
        brand_dir=brand_dir,
        days=days,
        products=list(product_photos.keys()),
    )

    console.print(f"   [green][OK][/green] Plan creado: {campaign_plan.name}")

    # Mostrar StyleGuide
    if campaign_plan.style_guide:
        sg = campaign_plan.style_guide
        console.print(f"\n[bold blue]StyleGuide:[/bold blue] {sg.name}")
        console.print(f"   Estilo: {sg.base_style}, Iluminación: {sg.lighting_style}")

    # 4. Confirmar
    if not skip_confirm:
        console.print("\n")
        confirm = Prompt.ask("¿Ejecutar campaña con INPAINTING?", choices=["s", "n"], default="s")
        if confirm != "s":
            console.print("[yellow]Cancelado[/yellow]")
            return

    # 5. Ejecutar
    console.print("\n[bold]4. Ejecutando pipeline INPAINTING...[/bold]")
    pipeline = CampaignPipeline()

    try:
        results = pipeline.run_with_inpainting(
            campaign_plan=campaign_plan,
            brand_dir=brand_dir,
            product_photos=product_photos,
            use_cascade=True,
        )

        console.print("\n")
        console.print(
            Panel(
                f"[bold green]Campaña completada[/bold green]\n\n"
                f"Imágenes generadas: {len(results)}\n"
                f"Costo total: ${sum(r.cost_usd for r in results):.2f}\n\n"
                f"[bold]Archivos:[/bold]\n" + "\n".join(f"  - {r.image_path}" for r in results),
                title="Resultados",
                border_style="green",
            )
        )

    except Exception as e:
        console.print(f"\n[red][ERROR] {e}[/red]")
        import traceback

        traceback.print_exc()


def main():
    parser = argparse.ArgumentParser(description="Ejecutar campaña publicitaria con AI")
    parser.add_argument(
        "--mode",
        choices=["direct", "inpainting"],
        default="direct",
        help="Modo de generación (default: direct)",
    )
    parser.add_argument("--brand", default="mi-marca", help="Slug de la marca")
    parser.add_argument("--campaign", default="Black Friday", help="Nombre de la campaña")
    parser.add_argument("--days", type=int, default=3, help="Número de días")
    parser.add_argument("--product-image", help="Ruta a imagen del producto (modo direct)")
    parser.add_argument(
        "--products", nargs="+", default=["coca-cola"], help="Slugs de productos (modo inpainting)"
    )
    parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")

    args = parser.parse_args()

    brand_dir = Path("brands") / args.brand

    if not brand_dir.exists():
        console.print(f"[red][ERROR] Marca no encontrada: {brand_dir}[/red]")
        return

    if args.mode == "direct":
        # Modo DIRECT: imagen del producto como input
        if args.product_image:
            product_image = Path(args.product_image)
        else:
            # Buscar primera foto de producto disponible
            products_dir = Path("products") / args.brand
            product_image = None
            for product_slug in args.products:
                product_dir = products_dir / product_slug
                for pattern in ["photos/product.webp", "photos/product.jpg", "photos/product.png"]:
                    p = product_dir / pattern
                    if p.exists():
                        product_image = p
                        break
                if product_image:
                    break

            if not product_image:
                console.print("[red][ERROR] No se encontró imagen de producto[/red]")
                console.print("[dim]Usa --product-image para especificar la ruta[/dim]")
                return

        run_direct_mode(
            brand_dir=brand_dir,
            product_image=product_image,
            campaign_name=args.campaign,
            days=args.days,
            skip_confirm=args.yes,
        )

    else:
        # Modo INPAINTING (legacy)
        products_dir = Path("products") / args.brand
        run_inpainting_mode(
            brand_dir=brand_dir,
            products_dir=products_dir,
            product_slugs=args.products,
            campaign_name=args.campaign,
            days=args.days,
            skip_confirm=args.yes,
        )


if __name__ == "__main__":
    main()
