"""CLI para cm-agents - Sistema de generación de diseños para redes sociales."""

from pathlib import Path
import typer
from rich.console import Console
from rich.table import Table

from .pipeline import GenerationPipeline
from .styles import get_available_style_keys

console = Console()
app = typer.Typer(
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)


@app.command()
def generate(
    product: str = typer.Argument(..., help="Nombre del producto"),
    brand: str = typer.Argument(..., help="Nombre de la marca"),
    style_ref: Path = typer.Argument(..., help="Path a la imagen de ESTILO (Pinterest)"),
    product_ref: Path = typer.Option(
        None,
        "--product-ref",
        "-p",
        help="Path a la imagen del PRODUCTO real (modo dual)",
    ),
    size: list[str] = typer.Option(
        ["feed"],
        "--size",
        "-s",
        help="Tamaños a generar (default: feed)",
    ),
    text: bool = typer.Option(
        True,
        "--text/--no-text",
        help="Agregar overlays de texto (default: Sí)",
    ),
    model: str = typer.Option(
        "gpt-image-1.5",
        "--model",
        "-m",
        help="Modelo de generación (default: gpt-image-1.5)",
    ),
    style: str | None = typer.Option(
        None,
        "--style",
        help="Estilo de diseño (key de knowledge base). Si no se especifica, se auto-detecta.",
    ),
    campaign: str | None = typer.Option(
        None,
        "--campaign",
        "-c",
        help="Nombre de la campaña (guarda output en campaigns/<nombre>/outputs/)",
    ),
):
    """
    Genera una o múltiples imágenes de producto basadas en referencias.

    MODO SIMPLE (solo estilo):
        cm generate sprite mi-marca references/producto_verde.jpg

    MODO DUAL (estilo + producto) - RECOMENDADO:
        cm generate sprite mi-marca references/producto_verde.jpg -p references/sprite.webp

    CON CAMPAÑA (guarda en carpeta de campaña):
        cm generate sprite mi-marca ref.jpg -p sprite.webp --campaign promo-verano

    ESTILOS DISPONIBLES (--style):
        minimal_clean     - Minimalista, fondo limpio, espacio negativo
        lifestyle_warm    - Cálido, contexto real, luz natural
        editorial_magazine - Alto contraste, composición dinámica, premium
        authentic_imperfect - Imperfecto intencional, artesanal, orgánico
        biophilic_nature   - Integración con naturaleza, plantas, sostenible
    """
    try:
        # Validar tamaños
        valid_sizes = {"feed", "story"}
        for s in size:
            if s not in valid_sizes:
                console.print(
                    f"[red][X] Error:[/red] Tamaño '{s}' no válido. Usa 'feed' o 'story'."
                )
                raise typer.Exit(1)

        # Validar estilo si se especificó
        design_style: str | None = None
        if style:
            available = set(get_available_style_keys())
            if style not in available:
                console.print(f"[red][X] Error:[/red] Estilo '{style}' no válido.")
                if available:
                    console.print(f"Estilos disponibles: {', '.join(sorted(available))}")
                else:
                    console.print(
                        "[yellow][!] No se pudieron cargar estilos desde knowledge/design_2026.json[/yellow]"
                    )
                raise typer.Exit(1)
            design_style = style

        # Si hay campaña, verificar y usar su estilo si no se especificó uno
        campaign_dir = None
        if campaign:
            campaign_dir = Path("brands") / brand / "campaigns" / campaign
            if not campaign_dir.exists():
                console.print(f"[red][X] Campaña '{campaign}' no encontrada en '{brand}'[/red]")
                raise typer.Exit(1)

            from .models.campaign import Campaign

            camp = Campaign.load(campaign_dir)

            # Usar estilo de campaña si no se especificó uno
            if not design_style and camp.theme.style_override:
                design_style = camp.theme.style_override
                console.print(f"[blue][Campaña][/blue] Usando estilo: {design_style}")

        pipeline = GenerationPipeline(
            generator_model=model,
            design_style=design_style,
        )
        results = pipeline.run(
            reference_path=style_ref,
            brand_dir=Path("brands") / brand,
            product_dir=Path("products") / brand / product,
            target_sizes=size,
            include_text=text,
            product_ref_path=product_ref,
            campaign_dir=campaign_dir,
        )

        # Mostrar info de campaña si aplica
        if campaign and results:
            console.print(
                f"\n[blue][Campaña][/blue] Imágenes guardadas en: brands/{brand}/campaigns/{campaign}/outputs/"
            )

    except FileNotFoundError as e:
        console.print(f"[red][X] Error:[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red][X] Error inesperado:[/red] {e}")
        raise typer.Exit(1)


# =============================================================================
# Comandos de Marca (Brand)
# =============================================================================


@app.command()
def brand_list():
    """Lista todas las marcas disponibles."""
    brands_dir = Path("brands")
    if not brands_dir.exists():
        console.print("[yellow]ℹ  Directorio 'brands' no encontrado.[/yellow]")
        return

    brands = [d.name for d in brands_dir.iterdir() if d.is_dir()]

    if not brands:
        console.print("[yellow]ℹ  No hay marcas configuradas.[/yellow]")
        return

    from .models.brand import Brand

    table = Table(title="Marcas disponibles")
    table.add_column("#", style="dim")
    table.add_column("Nombre", style="bold")
    table.add_column("Industria", style="cyan")
    table.add_column("Estilos", style="green")
    table.add_column("Estado")

    for i, brand_name in enumerate(brands, 1):
        brand_dir = brands_dir / brand_name
        brand_file = brand_dir / "brand.json"
        if brand_file.exists():
            try:
                brand = Brand.load(brand_dir)
                industry = brand.industry or "-"
                styles = ", ".join(brand.get_preferred_styles()[:2]) or "-"
                status = "[green][OK][/green]"
            except Exception:
                industry = "-"
                styles = "-"
                status = "[yellow][!] Error[/yellow]"
        else:
            industry = "-"
            styles = "-"
            status = "[red][X] Sin config[/red]"
        table.add_row(str(i), brand_name, industry, styles, status)

    console.print(table)


@app.command()
def brand_create(
    name: str = typer.Argument(..., help="Nombre de la marca (slug, ej: mi-tienda)"),
):
    """
    Crea una nueva marca con wizard interactivo.

    Ejemplo:
        cm brand-create farmacia-central
    """
    import re

    brands_dir = Path("brands")
    brand_dir = brands_dir / name

    if brand_dir.exists():
        console.print(f"[red][X] La marca '{name}' ya existe en {brand_dir}[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold]Crear nueva marca: {name}[/bold]\n")

    # Wizard interactivo
    display_name = typer.prompt("Nombre para mostrar", default=name.replace("-", " ").title())
    handle = typer.prompt("Handle de Instagram", default=f"@{name.replace('-', '')}")

    # Industria
    industries = [
        "food_restaurant",
        "food_delivery",
        "pharmacy",
        "wine_spirits",
        "retail",
        "fashion",
        "tech",
        "services",
        "other",
    ]
    console.print(f"\n[dim]Industrias: {', '.join(industries)}[/dim]")
    industry = typer.prompt("Industria", default="retail")

    # Tagline
    tagline = typer.prompt("Tagline/eslogan", default="")

    # Colores
    console.print("\n[bold]Colores (formato hex #RRGGBB)[/bold]")
    primary = typer.prompt("Color primario", default="#2196F3")
    secondary = typer.prompt("Color secundario", default="#FFC107")
    accent = typer.prompt("Color de acento", default="#4CAF50")

    # Validar colores
    color_pattern = re.compile(r"^#[0-9A-Fa-f]{6}$")
    for color_name, color_val in [
        ("primario", primary),
        ("secundario", secondary),
        ("acento", accent),
    ]:
        if not color_pattern.match(color_val):
            console.print(f"[red][X] Color {color_name} inválido: {color_val}[/red]")
            raise typer.Exit(1)

    # Cargar template
    template_path = Path("templates/brand_template.json")
    if not template_path.exists():
        console.print("[red][X] Template no encontrado en templates/brand_template.json[/red]")
        raise typer.Exit(1)

    with open(template_path, encoding="utf-8") as f:
        template = f.read()

    # Reemplazar placeholders
    brand_json = template.replace("{{BRAND_NAME}}", display_name)
    brand_json = brand_json.replace("{{HANDLE}}", handle.lstrip("@"))
    brand_json = brand_json.replace("{{INDUSTRY}}", industry)
    brand_json = brand_json.replace("{{TAGLINE}}", tagline)
    brand_json = brand_json.replace("{{PRIMARY_COLOR}}", primary)
    brand_json = brand_json.replace("{{SECONDARY_COLOR}}", secondary)
    brand_json = brand_json.replace("{{ACCENT_COLOR}}", accent)
    brand_json = brand_json.replace("{{HASHTAG}}", display_name.replace(" ", ""))

    # Crear estructura de directorios
    brand_dir.mkdir(parents=True, exist_ok=True)
    (brand_dir / "assets").mkdir(exist_ok=True)
    (brand_dir / "fonts").mkdir(exist_ok=True)
    (brand_dir / "references").mkdir(exist_ok=True)
    (brand_dir / "campaigns").mkdir(exist_ok=True)

    # Guardar brand.json
    with open(brand_dir / "brand.json", "w", encoding="utf-8") as f:
        f.write(brand_json)

    # Crear directorio de productos (estructura preferida dentro de la marca)
    products_dir = brand_dir / "products"
    products_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"\n[green][OK] Marca '{display_name}' creada exitosamente![/green]")
    console.print("\n[bold]Estructura creada:[/bold]")
    console.print(f"  brands/{name}/")
    console.print("    brand.json      - Configuración de marca")
    console.print("    assets/         - Logos e iconos")
    console.print("    fonts/          - Fuentes")
    console.print("    references/     - Referencias de estilo")
    console.print("    campaigns/      - Campañas")
    console.print(f"  brands/{name}/products/  - Productos")
    console.print(f"\n[dim]Próximo paso: agrega tu logo en brands/{name}/assets/logo.png[/dim]")


@app.command()
def brand_show(
    name: str = typer.Argument(..., help="Nombre de la marca"),
):
    """
    Muestra la configuración completa de una marca.

    Ejemplo:
        cm brand-show mi-marca
    """
    from rich.panel import Panel

    from .models.brand import Brand

    brand_dir = Path("brands") / name
    if not brand_dir.exists():
        console.print(f"[red][X] Marca '{name}' no encontrada[/red]")
        raise typer.Exit(1)

    try:
        brand = Brand.load(brand_dir)
    except Exception as e:
        console.print(f"[red][X] Error cargando marca: {e}[/red]")
        raise typer.Exit(1)

    # Identidad
    console.print(
        Panel(
            f"[bold]{brand.name}[/bold]\n"
            f"Handle: {brand.handle or '-'}\n"
            f"Industria: {brand.industry or '-'}\n"
            f"Tagline: {brand.identity.tagline or '-'}\n"
            f"Voz: {', '.join(brand.identity.voice)}\n"
            f"Valores: {', '.join(brand.identity.values) or '-'}",
            title="Identidad",
            border_style="blue",
        )
    )

    # Colores
    console.print(
        Panel(
            f"Primary: {brand.palette.primary}\n"
            f"Secondary: {brand.palette.secondary}\n"
            f"Accent: {brand.palette.accent or '-'}\n"
            f"Background: {brand.palette.background}\n"
            f"Text: {brand.palette.text}",
            title="Paleta de Colores",
            border_style="magenta",
        )
    )

    # Estilo
    console.print(
        Panel(
            f"Mood: {', '.join(brand.style.mood)}\n"
            f"Foto: {brand.style.photography_style}\n"
            f"Estilos preferidos: {', '.join(brand.get_preferred_styles()) or '-'}\n"
            f"Evitar: {', '.join(brand.get_avoid_styles()) or '-'}",
            title="Estilo Visual",
            border_style="green",
        )
    )

    # Assets
    assets_status = []
    for asset in ["logo", "logo_white", "icon", "watermark"]:
        path = brand.get_asset_path(brand_dir, asset)
        status = "[green]✓[/green]" if path else "[dim]-[/dim]"
        assets_status.append(f"{asset}: {status}")

    console.print(Panel("\n".join(assets_status), title="Assets", border_style="cyan"))

    # Campañas
    campaigns_dir = brand_dir / "campaigns"
    if campaigns_dir.exists():
        campaigns = [d.name for d in campaigns_dir.iterdir() if d.is_dir()]
        if campaigns:
            console.print(
                Panel(
                    "\n".join(campaigns),
                    title=f"Campañas ({len(campaigns)})",
                    border_style="yellow",
                )
            )

    console.print(f"\n[dim]Directorio: {brand_dir}[/dim]")


# =============================================================================
# Comandos de Campaña (Campaign)
# =============================================================================


@app.command()
def campaign_create(
    brand: str = typer.Argument(..., help="Nombre de la marca"),
    name: str = typer.Argument(..., help="Nombre de la campaña (slug, ej: promo-verano)"),
):
    """
    Crea una nueva campaña para una marca.

    Ejemplo:
        cm campaign-create mi-marca promo-verano-2026
    """
    from datetime import date, timedelta

    brand_dir = Path("brands") / brand
    if not brand_dir.exists():
        console.print(f"[red][X] Marca '{brand}' no encontrada[/red]")
        raise typer.Exit(1)

    campaign_dir = brand_dir / "campaigns" / name
    if campaign_dir.exists():
        console.print(f"[red][X] La campaña '{name}' ya existe[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold]Crear campaña: {name}[/bold]\n")

    # Wizard
    display_name = typer.prompt("Nombre para mostrar", default=name.replace("-", " ").title())
    description = typer.prompt("Descripción", default="")

    # Fechas
    today = date.today()
    default_end = today + timedelta(days=30)
    start_date = typer.prompt("Fecha inicio (YYYY-MM-DD)", default=today.isoformat())
    end_date = typer.prompt("Fecha fin (YYYY-MM-DD)", default=default_end.isoformat())

    # Estilo override opcional
    style_keys = get_available_style_keys()
    if style_keys:
        console.print(f"\n[dim]Estilos disponibles: {', '.join(style_keys[:6])}...[/dim]")
    else:
        console.print("\n[dim]Estilos disponibles: (no cargados)[/dim]")
    style_override = typer.prompt("Estilo (dejar vacío para usar el de la marca)", default="")

    # Crear estructura
    campaign_dir.mkdir(parents=True, exist_ok=True)
    (campaign_dir / "outputs").mkdir(exist_ok=True)

    # Crear campaign.json
    from .models.campaign import Campaign, CampaignDates, CampaignTheme

    campaign = Campaign(
        name=display_name,
        description=description,
        dates=CampaignDates(start=start_date, end=end_date),
        theme=CampaignTheme(
            style_override=style_override if style_override else None,
        ),
        products=[],
        content_plan=[],
        hashtags_extra=[],
    )
    campaign.save(campaign_dir)

    console.print(f"\n[green][OK] Campaña '{display_name}' creada![/green]")
    console.print("\n[bold]Estructura:[/bold]")
    console.print(f"  brands/{brand}/campaigns/{name}/")
    console.print("    campaign.json   - Configuración")
    console.print("    outputs/        - Imágenes generadas")
    console.print("\n[dim]Edita campaign.json para agregar productos y plan de contenido[/dim]")


@app.command()
def campaign_list(
    brand: str = typer.Argument(..., help="Nombre de la marca"),
):
    """
    Lista las campañas de una marca.

    Ejemplo:
        cm campaign-list mi-marca
    """
    from .models.campaign import Campaign

    brand_dir = Path("brands") / brand
    if not brand_dir.exists():
        console.print(f"[red][X] Marca '{brand}' no encontrada[/red]")
        raise typer.Exit(1)

    campaigns_dir = brand_dir / "campaigns"
    if not campaigns_dir.exists():
        console.print(f"[yellow]ℹ  No hay campañas para '{brand}'[/yellow]")
        return

    campaigns = [d for d in campaigns_dir.iterdir() if d.is_dir()]
    if not campaigns:
        console.print(f"[yellow]ℹ  No hay campañas para '{brand}'[/yellow]")
        return

    table = Table(title=f"Campañas de {brand}")
    table.add_column("#", style="dim")
    table.add_column("Nombre", style="bold")
    table.add_column("Fechas", style="cyan")
    table.add_column("Progreso", style="green")
    table.add_column("Estado")

    for i, camp_dir in enumerate(campaigns, 1):
        try:
            camp = Campaign.load(camp_dir)
            dates = f"{camp.dates.start} → {camp.dates.end}"
            completed, total = camp.get_progress()
            progress = f"{completed}/{total}" if total > 0 else "-"
            status = "[green]Activa[/green]" if camp.is_active() else "[dim]Inactiva[/dim]"
        except Exception:
            dates = "-"
            progress = "-"
            status = "[red]Error[/red]"
        table.add_row(str(i), camp_dir.name, dates, progress, status)

    console.print(table)


@app.command()
def campaign_show(
    brand: str = typer.Argument(..., help="Nombre de la marca"),
    name: str = typer.Argument(..., help="Nombre de la campaña"),
):
    """
    Muestra detalles de una campaña.

    Ejemplo:
        cm campaign-show mi-marca promo-verano-2026
    """
    from rich.panel import Panel

    from .models.campaign import Campaign

    campaign_dir = Path("brands") / brand / "campaigns" / name
    if not campaign_dir.exists():
        console.print(f"[red][X] Campaña '{name}' no encontrada en '{brand}'[/red]")
        raise typer.Exit(1)

    try:
        campaign = Campaign.load(campaign_dir)
    except Exception as e:
        console.print(f"[red][X] Error cargando campaña: {e}[/red]")
        raise typer.Exit(1)

    # Info general
    status = "[green]ACTIVA[/green]" if campaign.is_active() else "[dim]INACTIVA[/dim]"
    console.print(
        Panel(
            f"[bold]{campaign.name}[/bold] {status}\n"
            f"Descripción: {campaign.description or '-'}\n"
            f"Fechas: {campaign.dates.start} → {campaign.dates.end}\n"
            f"Productos: {', '.join(campaign.products) or '-'}\n"
            f"Hashtags extra: {', '.join(campaign.hashtags_extra) or '-'}",
            title="Campaña",
            border_style="blue",
        )
    )

    # Tema
    if campaign.theme.style_override or campaign.theme.mood:
        console.print(
            Panel(
                f"Estilo: {campaign.theme.style_override or 'Heredado de marca'}\n"
                f"Color acento: {campaign.theme.color_accent or '-'}\n"
                f"Mood: {', '.join(campaign.theme.mood) or '-'}",
                title="Tema Visual",
                border_style="magenta",
            )
        )

    # Plan de contenido
    if campaign.content_plan:
        completed, total = campaign.get_progress()
        content_lines = []
        for item in campaign.content_plan:
            status_icon = {
                "pending": "[yellow]○[/yellow]",
                "generated": "[green]✓[/green]",
                "published": "[blue]✓✓[/blue]",
            }.get(item.status, "○")
            content_lines.append(f"{status_icon} {item.date} - {item.product} ({item.size})")

        console.print(
            Panel(
                "\n".join(content_lines),
                title=f"Plan de Contenido ({completed}/{total})",
                border_style="green",
            )
        )
    else:
        console.print("[dim]Sin plan de contenido definido[/dim]")

    console.print(f"\n[dim]Directorio: {campaign_dir}[/dim]")


@app.command()
def product_list(brand: str = typer.Argument(..., help="Nombre de la marca")):
    """Lista todos los productos de una marca."""
    product_dir = Path("brands") / brand / "products"
    legacy_product_dir = Path("products") / brand
    if not product_dir.exists() and legacy_product_dir.exists():
        product_dir = legacy_product_dir

    if not product_dir.exists():
        console.print(
            f"[red][X] Marca '{brand}' no encontrada en brands/{brand}/products (ni en products/{brand}).[/red]"
        )
        raise typer.Exit(1)

    products = [d.name for d in product_dir.iterdir() if d.is_dir()]

    if not products:
        console.print(f"[yellow]ℹ  No hay productos configurados para '{brand}'.[/yellow]")
        return

    table = Table(title=f"Productos de {brand}")
    table.add_column("#", style="dim")
    table.add_column("Nombre", style="bold")
    table.add_column("Precio", style="green")

    for i, product_name in enumerate(products, 1):
        product_json = product_dir / product_name / "product.json"
        price = "N/A"
        if product_json.exists():
            import json

            with open(product_json) as f:
                data = json.load(f)
                price = data.get("price", "N/A")
        table.add_row(str(i), product_name, price)

    console.print(table)


@app.command()
def status():
    """Muestra el estado de la configuracion."""
    console.print("\n[bold]Estado de CM Agents[/bold]\n")

    # Verificar .env
    from pathlib import Path

    env_file = Path(".env")
    if env_file.exists():
        console.print("[green][OK][/green] .env encontrado")
    else:
        console.print("[yellow][!] .env no encontrado - crea uno desde .env.example[/yellow]")

    # Verificar brands
    brands_dir = Path("brands")
    if brands_dir.exists():
        brand_count = len([d for d in brands_dir.iterdir() if d.is_dir()])
        console.print(f"[green][OK][/green] {brand_count} marca(s) configurada(s)")
    else:
        console.print("[yellow][!] brands/ no existe[/yellow]")

    # Verificar products (nueva estructura + legacy)
    products_dir = Path("brands")
    product_count = 0
    if products_dir.exists():
        for brand in (d for d in products_dir.iterdir() if d.is_dir()):
            brand_products = brand / "products"
            if brand_products.exists():
                product_count += len([d for d in brand_products.iterdir() if d.is_dir()])
    legacy_products_dir = Path("products")
    if legacy_products_dir.exists():
        product_count += sum(
            len([d for d in brand.iterdir() if d.is_dir()])
            for brand in (legacy_products_dir.iterdir() if legacy_products_dir.is_dir() else [])
        )

    if product_count > 0:
        console.print(f"[green][OK][/green] {product_count} producto(s) configurado(s)")
    else:
        console.print("[yellow][!] No hay productos configurados[/yellow]")

    # Verificar references
    refs_dir = Path("references")
    if refs_dir.exists():
        ref_count = len(list(refs_dir.glob("*")))
        console.print(f"[green][OK][/green] {ref_count} referencia(s) encontrada(s)")
    else:
        console.print("[yellow][!] references/ no existe[/yellow]")


@app.command()
def estimate():
    """Estima el costo de generar imágenes."""
    from dotenv import load_dotenv

    load_dotenv()
    import os

    if not os.getenv("OPENAI_API_KEY"):
        console.print("[red][X] OPENAI_API_KEY no configurada en .env[/red]")
        raise typer.Exit(1)

    model = typer.prompt("Modelo", default="gpt-image-1.5", show_default=True)
    count = typer.prompt("Cantidad de imágenes", type=int, default=10)

    from .agents.generator import GeneratorAgent

    agent = GeneratorAgent(model=model)
    cost = agent.get_cost_estimate(count)

    console.print("\n[bold]Estimación de costo[/bold]\n")
    console.print(f"  Modelo: {model}")
    console.print(f"  Imágenes: {count}")
    console.print(f"  Costo por imagen: ${cost / count:.4f}")
    console.print(f"  [bold]Costo total: ${cost:.2f}[/bold]\n")


@app.command()
def pinterest_search(
    query: str = typer.Argument(..., help="Término de búsqueda"),
    limit: int = typer.Option(10, "--limit", "-l", help="Cantidad de imágenes"),
    download: bool = typer.Option(True, "--download/--no-download", help="Descargar imágenes"),
):
    """
    Busca imágenes en Pinterest usando MCP.

    Ejemplo:
        cm pinterest-search "food photography minimal" --limit 5
    """
    import asyncio

    from .services.mcp_client import MCPClientService

    async def run_search():
        service = MCPClientService()
        try:
            results = await service.search_pinterest(query, limit, download)
            console.print(
                f"\n[green][OK][/green] {len(results) if results else 0} imágenes encontradas"
            )
            if download:
                console.print("[dim]Imágenes descargadas en references/[/dim]")
            return results
        except Exception as e:
            console.print(f"[red][X] Error:[/red] {e}")
            raise typer.Exit(1)

    asyncio.run(run_search())


@app.command()
def mcp_tools(
    server: str = typer.Argument("pinterest", help="Nombre del servidor MCP"),
):
    """
    Lista los tools disponibles en un servidor MCP.

    Ejemplo:
        cm mcp-tools pinterest
    """
    import asyncio

    from rich.table import Table

    from .services.mcp_client import MCPClientService

    async def list_tools():
        service = MCPClientService()
        try:
            tools = await service.list_tools(server)
            table = Table(title=f"Tools de {server}")
            table.add_column("Tool", style="bold")
            table.add_column("Descripción")
            for tool in tools:
                table.add_row(tool["name"], tool.get("description", "N/A"))
            console.print(table)
        except Exception as e:
            console.print(f"[red][X] Error:[/red] {e}")
            raise typer.Exit(1)

    asyncio.run(list_tools())


@app.command()
def styles(
    category: str | None = typer.Argument(
        None, help="Filtrar por categoría (ej: food, pharmacy, wine_spirits)"
    ),
):
    """
    Lista los estilos de diseño disponibles.

    Los estilos se cargan dinámicamente desde knowledge/design_2026.json,
    por lo que podés agregar nuevos estilos sin modificar código.

    Ejemplos:
        cm styles              # Lista todos los estilos
        cm styles pharmacy     # Estilos recomendados para farmacia
    """
    import json
    from pathlib import Path

    # Cargar knowledge base completo
    knowledge_path = Path("knowledge/design_2026.json")
    if not knowledge_path.exists():
        console.print("[red][X] knowledge/design_2026.json no encontrado[/red]")
        raise typer.Exit(1)

    with open(knowledge_path, encoding="utf-8") as f:
        kb = json.load(f)

    styles_data = kb.get("styles", {})
    categories = kb.get("category_guidelines", {})

    if category:
        # Mostrar estilos recomendados para una categoría
        if category not in categories:
            console.print(f"[red][X] Categoría '{category}' no encontrada.[/red]")
            console.print(f"Categorías disponibles: {', '.join(categories.keys())}")
            raise typer.Exit(1)

        cat_info = categories[category]
        recommended = cat_info.get("recommended_styles", [])

        table = Table(title=f"Estilos recomendados para '{category}'")
        table.add_column("Estilo", style="bold green")
        table.add_column("Nombre")
        table.add_column("Descripción")

        for style_key in recommended:
            style = styles_data.get(style_key, {})
            table.add_row(
                style_key, style.get("name", "N/A"), style.get("description", "N/A")[:60] + "..."
            )

        console.print(table)
        console.print(f"\n[dim]Props sugeridos: {', '.join(cat_info.get('props', [])[:4])}[/dim]")
        console.print(f"[dim]Evitar: {', '.join(cat_info.get('avoid', [])[:3])}[/dim]")
    else:
        # Listar todos los estilos
        table = Table(title="Estilos de Diseño Disponibles (2026)")
        table.add_column("#", style="dim")
        table.add_column("Estilo (--style)", style="bold cyan")
        table.add_column("Nombre")
        table.add_column("Descripción")

        for i, (key, style) in enumerate(styles_data.items(), 1):
            table.add_row(
                str(i), key, style.get("name", "N/A"), style.get("description", "N/A")[:50] + "..."
            )

        console.print(table)
        console.print(f"\n[green]{len(styles_data)} estilos disponibles[/green]")
        console.print("\n[dim]Uso: cm generate producto marca ref.jpg --style ESTILO[/dim]")
        console.print("[dim]Ver estilos por categoría: cm styles CATEGORIA[/dim]")
        console.print(f"[dim]Categorías: {', '.join(list(categories.keys())[:6])}...[/dim]")


# =============================================================================
# Comandos del Servidor API
# =============================================================================


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host del servidor"),
    port: int = typer.Option(8000, "--port", "-p", help="Puerto del servidor"),
    reload: bool = typer.Option(False, "--reload", help="Hot reload para desarrollo"),
    api_only: bool = typer.Option(False, "--api-only", help="Solo iniciar API sin UI"),
):
    """
    Inicia el servidor API de CM Agents.

    Ejemplos:
        cm serve                    # Inicia en localhost:8000
        cm serve --port 3001        # Puerto personalizado
        cm serve --reload           # Con hot reload
    """
    import uvicorn

    console.print("\n[bold]CM Agents API Server[/bold]")
    console.print(f"  URL: http://{host}:{port}")
    console.print(f"  Docs: http://{host}:{port}/docs")
    console.print(f"  Reload: {'Sí' if reload else 'No'}")
    console.print()

    uvicorn.run(
        "cm_agents.api.main:app",
        host=host,
        port=port,
        reload=reload,
    )


# =============================================================================
# Comandos de Plan (Content Planning)
# =============================================================================


@app.command("plan-create")
def plan_create(
    prompt: str = typer.Argument(..., help="Descripción del contenido a crear"),
    brand: str = typer.Option(..., "--brand", "-b", help="Marca para el plan"),
    campaign: str | None = typer.Option(None, "--campaign", "-c", help="Campaña"),
):
    """
    Crea un plan de contenido desde lenguaje natural.

    Ejemplos:
        cm plan-create "posts para el día del padre" --brand mi-marca
        cm plan-create "promoción de verano" -b farmacia-central -c verano-2026
    """
    from pathlib import Path

    from .models.plan import ContentIntent, ContentPlan

    # Verificar marca existe
    brand_dir = Path("brands") / brand
    if not brand_dir.exists():
        console.print(f"[red][X] Marca '{brand}' no encontrada[/red]")
        raise typer.Exit(1)

    # Crear plan placeholder (TODO: integrar StrategistAgent)
    plan = ContentPlan(
        brand=brand,
        campaign=campaign,
        intent=ContentIntent(
            objective="promocionar",
            tone=["profesional"],
        ),
    )

    # Agregar item de ejemplo
    plan.add_item(
        product="producto-ejemplo",
        size="feed",
        style="minimal_clean",
        copy_suggestion=f"Basado en: {prompt[:100]}",
        reference_query="food photography minimal",
    )

    # Guardar plan
    plans_dir = Path("outputs/plans")
    plans_dir.mkdir(parents=True, exist_ok=True)
    plan_path = plans_dir / f"{plan.id}.json"
    plan.save(plan_path)

    console.print("\n[green][OK] Plan creado:[/green]")
    console.print(plan.to_summary())
    console.print(f"\n[dim]Archivo: {plan_path}[/dim]")
    console.print(f"\n[yellow]Próximo paso: cm plan-approve {plan.id}[/yellow]")


@app.command("agent-chat")
def agent_chat(
    brand: str | None = typer.Option(None, "--brand", "-b", help="Marca (slug) opcional"),
):
    """Chat interactivo con Strategist (ida y vuelta) para reunir contexto y planificar."""
    from .agents.strategist import StrategistAgent
    from .models.brand import Brand

    strategist = StrategistAgent()
    context: list[dict] = []
    brand_obj: Brand | None = None

    if brand:
        brand_dir = Path("brands") / brand
        if brand_dir.exists():
            try:
                brand_obj = Brand.load(brand_dir)
            except Exception as e:
                console.print(f"[yellow][!] No se pudo cargar la marca '{brand}': {e}[/yellow]")
        else:
            console.print(
                f"[yellow][!] Marca '{brand}' no encontrada. Continuo sin contexto de marca.[/yellow]"
            )

    console.print("\n[bold]Agent Chat (Strategist Orchestrator)[/bold]")
    console.print("Escribí tu pedido. El Strategist te va a preguntar lo que falte.")
    console.print(
        "Comandos: [dim]'exit'[/dim] para salir, [dim]'/build'[/dim] para ejecutar agent-campaign con el último pedido."
    )
    console.print(
        "[dim]Nota: solo hay generación real cuando se ejecuta /build (o cuando confirmás aprobación).[/dim]\n"
    )

    last_user_request: str | None = None
    pending_build_request: str | None = None

    def _execute_real_build(request_text: str) -> None:
        if not brand:
            console.print("[red][X] Para ejecutar build necesitás --brand.[/red]")
            return

        from .services.agent_campaign import OrchestratorCampaignService

        console.print("[cyan]Ejecutando Orchestrator REAL con el pedido confirmado...[/cyan]")
        try:
            result = OrchestratorCampaignService().run_from_user_input(
                brand_slug=brand,
                user_request=request_text,
                require_llm_orchestrator=True,
            )
            artifacts = result["artifacts"]
            wp = artifacts.get("worker_plan", {})
            generated = len([g for g in artifacts.get("generation", []) if "image_path" in g])
            errors = len([g for g in artifacts.get("generation", []) if "error" in g])

            console.print("[green][OK] Build REAL completado[/green]")
            console.print(f"  Run ID: {result['run_id']}")
            console.print(f"  Orchestrator mode: {wp.get('mode', '-')}")
            console.print(f"  Worker sequence: {', '.join(wp.get('sequence', []))}")
            console.print(f"  Imágenes generadas: {generated}")
            console.print(f"  Errores: {errors}")
            console.print(f"  Artefactos: {result['run_dir'] / 'artifacts.json'}")
        except Exception as e:
            console.print(f"[red][X] Error en build REAL:[/red] {e}")

    while True:
        user_msg = typer.prompt("Tu mensaje").strip()
        if user_msg.lower() in {"exit", "quit", "salir"}:
            console.print("[green][OK] Cerrando chat.[/green]")
            break

        approval_words = {
            "ok",
            "dale",
            "aprobado",
            "apruebo",
            "si",
            "sí",
            "genera",
            "ejecuta",
            "adelante",
        }
        if user_msg.lower() in approval_words and pending_build_request:
            _execute_real_build(pending_build_request)
            pending_build_request = None
            continue

        if user_msg == "/build":
            target_request = pending_build_request or last_user_request
            if not target_request:
                console.print("[yellow][!] Primero enviá un pedido en lenguaje natural.[/yellow]")
                continue
            _execute_real_build(target_request)
            pending_build_request = None
            continue

        last_user_request = user_msg
        reply, plan = strategist.chat(
            message=user_msg,
            brand=brand_obj,
            context=context,
            workflow_mode="plan",
            brand_slug=brand,
        )

        console.print(f"\n[bold cyan]Strategist:[/bold cyan] {reply}\n")
        context.append({"role": "user", "content": user_msg})
        context.append({"role": "assistant", "content": reply})

        if plan:
            console.print("[green][OK] Plan detectado en la conversación[/green]")
            console.print(plan.to_summary())
            pending_build_request = last_user_request
            console.print("[dim]Tip: escribí /build para ejecutar con el orquestador LLM.[/dim]\n")


@app.command("agent-campaign")
def agent_campaign(
    brand: str = typer.Option(..., "--brand", "-b", help="Marca (slug)"),
    message: str | None = typer.Option(
        None,
        "--message",
        "-m",
        help="Pedido libre del usuario; el Strategist lo traduce y dispara workers",
    ),
    products: str | None = typer.Option(
        None,
        "--products",
        "-p",
        help="Productos separados por coma (opcional: autodetecta en brands/<marca>/products)",
    ),
    objective: str = typer.Option(
        "promocionar campaña visual con consistencia de marca",
        "--objective",
        "-o",
        help="Objetivo de la campaña",
    ),
    days: int = typer.Option(3, "--days", "-d", help="Cantidad de días/items por producto"),
    build: bool = typer.Option(True, "--build/--no-build", help="Ejecutar generación de imágenes"),
    max_retries: int = typer.Option(
        1,
        "--max-retries",
        help="Reintentos máximos por item cuando falla generación/QA",
    ),
    style_ref: Path | None = typer.Option(
        None,
        "--style-ref",
        "-s",
        help="Referencia de estilo (requerida si --build y no hay refs en marca)",
    ),
    require_llm_orchestrator: bool = typer.Option(
        False,
        "--require-llm-orchestrator",
        help="Falla si no hay ANTHROPIC_API_KEY (evita fallback determinístico)",
    ),
):
    """Ejecuta un flujo Orchestrator->Workers para campaña (MVP)."""
    from .services.agent_campaign import OrchestratorCampaignService

    product_slugs = [p.strip() for p in products.split(",") if p.strip()] if products else None

    if days < 1 or days > 14:
        console.print("[red][X] --days debe estar entre 1 y 14[/red]")
        raise typer.Exit(1)

    console.print("\n[bold]Agent Campaign (MVP)[/bold]")
    console.print(f"  Marca: {brand}")
    if message:
        console.print(f"  Input dinámico: {message}")
        console.print("  Modo: Strategist traduce input y orquesta workers")
    else:
        console.print(f"  Productos: {', '.join(product_slugs) if product_slugs else 'auto'}")
        console.print(f"  Objetivo: {objective}")
        console.print(f"  Días: {days}")
        console.print(f"  Build: {'Sí' if build else 'No (solo plan)'}")
        if build:
            console.print(f"  Max retries por item: {max_retries}")

    service = OrchestratorCampaignService()
    llm_required = require_llm_orchestrator or bool(message)
    try:
        if message:
            result = service.run_from_user_input(
                brand_slug=brand,
                user_request=message,
                style_ref=style_ref,
                max_retries=max_retries,
                require_llm_orchestrator=llm_required,
            )
        else:
            result = service.run(
                brand_slug=brand,
                product_slugs=product_slugs,
                objective=objective,
                days=days,
                build=build,
                style_ref=style_ref,
                max_retries=max_retries,
                require_llm_orchestrator=llm_required,
            )
    except Exception as e:
        console.print(f"[red][X] Error ejecutando agent-campaign:[/red] {e}")
        raise typer.Exit(1)

    run_dir = result["run_dir"]
    artifacts = result["artifacts"]
    generated = len([g for g in artifacts.get("generation", []) if "image_path" in g])
    errors = len([g for g in artifacts.get("generation", []) if "error" in g])

    console.print("\n[green][OK] Agent run completado[/green]")
    console.print(f"  Run ID: {result['run_id']}")
    console.print(f"  Directorio: {run_dir}")
    translation = artifacts.get("input_translation")
    if translation:
        console.print(f"  Input translation mode: {translation.get('mode', '-')}")
        console.print(f"  Input translation reason: {translation.get('reason', '-')}")
        console.print(
            f"  Input translation params: days={translation.get('days')} build={translation.get('build')} products={translation.get('products') or 'auto'}"
        )
    worker_plan = artifacts.get("worker_plan", {})
    if worker_plan:
        seq = worker_plan.get("sequence", [])
        console.print(f"  Orchestrator mode: {worker_plan.get('mode', '-')}")
        console.print(f"  Worker sequence: {', '.join(seq)}")
        console.print(f"  Worker plan reason: {worker_plan.get('reason', '-')}")
    console.print(f"  Estilo seleccionado: {artifacts.get('selected_style')}")
    console.print(f"  Items de campaña: {len(artifacts.get('campaign_items', []))}")
    if build:
        console.print(f"  Imágenes generadas: {generated}")
        console.print(f"  Errores de generación: {errors}")
    console.print(f"  Artefactos: {run_dir / 'artifacts.json'}")
    console.print(f"  Reporte: {run_dir / 'report.md'}")


@app.command("plan-list")
def plan_list(
    brand: str | None = typer.Option(None, "--brand", "-b", help="Filtrar por marca"),
):
    """
    Lista todos los planes de contenido.

    Ejemplo:
        cm plan-list
        cm plan-list --brand mi-marca
    """
    from pathlib import Path

    from .models.plan import ContentPlan

    plans_dir = Path("outputs/plans")
    if not plans_dir.exists():
        console.print("[yellow]ℹ No hay planes creados[/yellow]")
        return

    table = Table(title="Planes de Contenido")
    table.add_column("ID", style="bold")
    table.add_column("Marca")
    table.add_column("Items")
    table.add_column("Estado")
    table.add_column("Costo Est.")

    for plan_file in plans_dir.glob("*.json"):
        try:
            plan = ContentPlan.load(plan_file)
            if brand and plan.brand != brand:
                continue

            completed, total = plan.get_progress()
            if plan.approved_at:
                status = f"[green]Aprobado ({completed}/{total})[/green]"
            else:
                status = "[yellow]Pendiente[/yellow]"

            table.add_row(
                plan.id,
                plan.brand,
                str(total),
                status,
                f"${plan.estimated_cost:.2f}",
            )
        except Exception:
            continue

    console.print(table)


@app.command("plan-show")
def plan_show(
    plan_id: str = typer.Argument(..., help="ID del plan"),
):
    """
    Muestra detalles de un plan.

    Ejemplo:
        cm plan-show abc123
    """
    from pathlib import Path

    from rich.panel import Panel

    from .models.plan import ContentPlan

    plan_path = Path("outputs/plans") / f"{plan_id}.json"
    if not plan_path.exists():
        console.print(f"[red][X] Plan '{plan_id}' no encontrado[/red]")
        raise typer.Exit(1)

    plan = ContentPlan.load(plan_path)

    # Info general
    status = "[green]APROBADO[/green]" if plan.approved_at else "[yellow]PENDIENTE[/yellow]"
    console.print(
        Panel(
            f"[bold]Plan {plan.id}[/bold] {status}\n"
            f"Marca: {plan.brand}\n"
            f"Objetivo: {plan.intent.objective}\n"
            f"Ocasión: {plan.intent.occasion or '-'}\n"
            f"Costo estimado: ${plan.estimated_cost:.2f}",
            title="Plan de Contenido",
            border_style="blue",
        )
    )

    # Items
    if plan.items:
        table = Table(title=f"Items ({len(plan.items)})")
        table.add_column("ID", style="dim")
        table.add_column("Producto")
        table.add_column("Tamaño")
        table.add_column("Estilo")
        table.add_column("Estado")

        for item in plan.items:
            status_icon = {
                "draft": "[yellow]○[/yellow]",
                "approved": "[blue]✓[/blue]",
                "generated": "[green]✓✓[/green]",
                "failed": "[red]✗[/red]",
            }.get(item.status, "○")
            table.add_row(
                item.id,
                item.product,
                item.size,
                item.style,
                f"{status_icon} {item.status}",
            )

        console.print(table)


@app.command("plan-approve")
def plan_approve(
    plan_id: str = typer.Argument(..., help="ID del plan"),
    items: str | None = typer.Option(None, "--items", help="IDs de items (separados por coma)"),
):
    """
    Aprueba un plan para ejecución.

    Ejemplos:
        cm plan-approve abc123              # Aprobar todo
        cm plan-approve abc123 --items id1,id2  # Solo algunos items
    """
    from pathlib import Path

    from .models.plan import ContentPlan

    plan_path = Path("outputs/plans") / f"{plan_id}.json"
    if not plan_path.exists():
        console.print(f"[red][X] Plan '{plan_id}' no encontrado[/red]")
        raise typer.Exit(1)

    plan = ContentPlan.load(plan_path)

    item_ids = items.split(",") if items else None
    plan.approve(item_ids)
    plan.save(plan_path)

    approved_count = len(plan.get_approved_items())
    console.print(f"[green][OK] Plan aprobado: {approved_count} items[/green]")
    console.print(f"\n[yellow]Próximo paso: cm plan-execute {plan.id}[/yellow]")


@app.command("plan-execute")
def plan_execute(
    plan_id: str = typer.Argument(..., help="ID del plan"),
):
    """
    Ejecuta la generación de imágenes para un plan aprobado.

    Ejemplo:
        cm plan-execute abc123
    """
    from pathlib import Path

    from .models.plan import ContentPlan
    from .models.product import Product

    plan_path = Path("outputs/plans") / f"{plan_id}.json"
    if not plan_path.exists():
        console.print(f"[red][X] Plan '{plan_id}' no encontrado[/red]")
        raise typer.Exit(1)

    plan = ContentPlan.load(plan_path)

    approved_items = plan.get_approved_items()
    if not approved_items:
        console.print("[red][X] No hay items aprobados. Primero ejecutá: cm plan-approve[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold]Ejecutando plan {plan.id}[/bold]")
    console.print(f"  Items a generar: {len(approved_items)}")
    console.print(f"  Costo estimado: ${plan.estimated_cost:.2f}")

    try:
        # Load brand
        brand_dir = (Path("brands") / plan.brand).resolve()
        if not brand_dir.exists():
            console.print(f"[red][X] Directorio de marca no encontrado: {brand_dir}[/red]")
            raise typer.Exit(1)

        # Determine campaign directory
        campaign_dir = None
        if plan.campaign:
            campaign_dir = brand_dir / "campaigns" / plan.campaign
            if not campaign_dir.exists():
                campaign_dir = None

        # Initialize pipeline
        pipeline = GenerationPipeline(generator_model="gpt-image-1.5", design_style=None)

        for i, item in enumerate(approved_items, 1):
            console.print(
                f"\n[bold]({i}/{len(approved_items)}) Generando: {item.product} ({item.size})[/bold]"
            )
            try:
                # Load product
                product_dir = (Path("products") / plan.brand / item.product).resolve()
                if not product_dir.exists():
                    raise FileNotFoundError(f"Directorio de producto no encontrado: {product_dir}")
                product = Product.load(product_dir)

                # Find reference image
                reference_path = None
                brand_refs_dir = brand_dir / "references"
                if brand_refs_dir.exists():
                    brand_ref_files = list(brand_refs_dir.glob("*.jpg")) + list(
                        brand_refs_dir.glob("*.png")
                    )
                    if brand_ref_files:
                        reference_path = brand_ref_files[0]

                if not reference_path:
                    try:
                        reference_path = product.get_main_photo(product_dir)
                    except ValueError:
                        console.print(
                            f"[red][X] No se encontró imagen de referencia para {item.product} en la marca o el producto.[/red]"
                        )
                        plan.mark_failed(item.id, "No reference image found")
                        continue

                # Find product reference for dual mode
                product_ref_path = None
                try:
                    product_ref_path = product.get_main_photo(product_dir)
                except ValueError:
                    pass  # It's ok to not have a specific product ref

                # Run pipeline for the item
                results = pipeline.run(
                    reference_path=reference_path,
                    brand_dir=brand_dir,
                    product_dir=product_dir,
                    target_sizes=[item.size],
                    include_text=True,
                    product_ref_path=product_ref_path,
                    campaign_dir=campaign_dir,
                    num_variants=item.variants_count,
                    price_override=item.price_override,
                )

                if results:
                    from .models.plan import VariantResult

                    for variant_idx, result in enumerate(results, 1):
                        variant = VariantResult(
                            variant_number=variant_idx,
                            output_path=str(result.image_path),
                            cost_usd=result.cost_usd,
                            status="generated",
                        )
                        plan.add_variant(item.id, variant)
                    console.print(f"[green][OK] Generado con {len(results)} variante(s).[/green]")
                else:
                    raise ValueError("El pipeline no retornó resultados.")

            except Exception as e:
                console.print(f"[red][X] Falló la generación para el item {item.id}: {e}[/red]")
                plan.mark_failed(item.id, str(e))

        # Save the updated plan
        plan.save(plan_path)
        console.print("\n[bold green]Proceso de ejecución de plan finalizado.[/bold green]")
        completed, total = plan.get_progress()
        console.print(f"  Imágenes generadas: {completed}/{total}")

    except Exception as e:
        console.print(f"\n[red][X] Error fatal ejecutando el plan: {e}[/red]")
        raise typer.Exit(1)


@app.command("campaign-inpaint")
def campaign_inpaint(
    brand: str = typer.Argument(..., help="Slug de la marca"),
    campaign: str = typer.Argument(..., help="Nombre de la campaña"),
    scale: float = typer.Option(
        0.4,
        "--scale",
        "-s",
        help="Escala del producto (0.3-0.5 recomendado)",
    ),
    position: str = typer.Option(
        "center",
        "--position",
        "-p",
        help="Posición del producto: center, left, right, bottom-center",
    ),
    cascade: bool = typer.Option(
        True,
        "--cascade/--no-cascade",
        help="Usar cascada de estilo para coherencia visual (default: Sí)",
    ),
    model: str = typer.Option(
        "gpt-image-1.5",
        "--model",
        "-m",
        help="Modelo de generación",
    ),
):
    """
    Ejecuta campaña con INPAINTING - integración realista del producto.

    A diferencia del compositing simple, el inpainting permite que el
    modelo AI integre el producto con sombras, reflejos y perspectiva
    coherentes con la escena.

    VENTAJAS:
    - Producto integrado realistamente en la escena
    - Sombras y reflejos coherentes con la iluminación
    - Coherencia visual entre las imágenes de la campaña (cascada)

    Ejemplo:
        cm campaign-inpaint mi-marca promo-verano
        cm campaign-inpaint mi-marca promo-verano --scale 0.35 --position bottom-center
    """
    from pathlib import Path

    from .models.campaign_plan import CampaignPlan
    from .models.product import Product
    from .pipeline import CampaignPipeline

    # Validar marca
    brand_dir = Path("brands") / brand
    if not brand_dir.exists():
        console.print(f"[red][X] Marca '{brand}' no encontrada[/red]")
        raise typer.Exit(1)

    # Buscar plan de campaña
    campaign_dir = brand_dir / "campaigns" / campaign
    plan_path = campaign_dir / "plan.json"

    if not plan_path.exists():
        # Intentar buscar en outputs/plans
        alt_plan_path = Path("outputs/plans") / f"{campaign}.json"
        if alt_plan_path.exists():
            plan_path = alt_plan_path
        else:
            console.print(f"[red][X] Plan de campaña no encontrado: {plan_path}[/red]")
            console.print("[dim]Crea primero un plan con: cm plan-create[/dim]")
            raise typer.Exit(1)

    # Cargar plan
    campaign_plan = CampaignPlan.load(plan_path)
    console.print(f"[green][OK][/green] Plan cargado: {campaign_plan.name}")
    console.print(f"[dim]   Días: {len(campaign_plan.days)}[/dim]")
    console.print(f"[dim]   Productos: {campaign_plan.get_all_products()}[/dim]")

    # Buscar fotos de productos
    products_dir = Path("products") / brand
    product_photos: dict[str, Path] = {}

    for product_slug in campaign_plan.get_all_products():
        product_dir = products_dir / product_slug
        if product_dir.exists():
            try:
                product = Product.load(product_dir)
                photo = product.get_main_photo(product_dir)
                product_photos[product_slug] = photo
                console.print(f"[green][OK][/green] Producto: {product_slug} -> {photo.name}")
            except ValueError:
                console.print(f"[yellow][!] Producto {product_slug} sin foto[/yellow]")
        else:
            console.print(f"[yellow][!] Producto {product_slug} no encontrado[/yellow]")

    if not product_photos:
        console.print("[red][X] No hay fotos de productos disponibles[/red]")
        raise typer.Exit(1)

    # Ejecutar pipeline con inpainting
    pipeline = CampaignPipeline(generator_model=model)

    output_dir = campaign_dir / "outputs" if campaign_dir.exists() else None

    results = pipeline.run_with_inpainting(
        campaign_plan=campaign_plan,
        brand_dir=brand_dir,
        product_photos=product_photos,
        output_dir=output_dir,
        product_scale=scale,
        product_position=position,
        use_cascade=cascade,
    )

    console.print(f"\n[bold green]Campaña completada con {len(results)} imágenes[/bold green]")


@app.command("campaign-refs")
def campaign_refs(
    brand: str = typer.Argument(..., help="Slug de la marca"),
    product: str = typer.Option(..., "--product", "-p", help="Path a la imagen del producto"),
    scene: str = typer.Option(..., "--scene", "-s", help="Path a la imagen de la escena/fondo"),
    font: str = typer.Option(
        ..., "--font", "-f", help="Path a la imagen de referencia de tipografía"
    ),
    days: int = typer.Option(
        3, "--days", "-d", help="Número de días (variaciones con copy distinto)"
    ),
    output: str | None = typer.Option(None, "--output", "-o", help="Directorio de salida"),
    title: str | None = typer.Option(
        None,
        "--title",
        "-t",
        help="Título de campaña para headlines (ej. BLACK FRIDAY). Día 2 lo usa como headline; default: PROMO",
    ),
    plan: str | None = typer.Option(
        None, "--plan", help="Path a plan.json (opcional; si no, se usan 3 días por defecto)"
    ),
):
    """
    Campaña por referencias: 1 producto + 1 escena + 1 fuente.

    Genera una variación distinta por día (cambiando ángulo del producto)
    y agrega texto por día usando la referencia de tipografía.
    Por defecto 3 días (teaser, main_offer, last_chance).

    Ejemplo:
        cm campaign-refs mi-marca --product foto.jpg --scene escena.png --font fuente.png
        cm campaign-refs mi-marca -p producto.png -s fondo.png -f tipografia.png --days 3
    """
    from pathlib import Path

    from .pipeline import CampaignPipeline

    brand_dir = Path("brands") / brand
    if not brand_dir.exists():
        console.print(f"[red][X] Marca '{brand}' no encontrada[/red]")
        raise typer.Exit(1)

    product_path = Path(product)
    scene_path = Path(scene)
    font_path = Path(font)

    for label, path in [("Producto", product_path), ("Escena", scene_path), ("Fuente", font_path)]:
        if not path.exists():
            console.print(f"[red][X] {label} no encontrado: {path}[/red]")
            raise typer.Exit(1)

    campaign_plan = None
    if plan:
        plan_path = Path(plan)
        if plan_path.exists():
            from .models.campaign_plan import CampaignPlan

            campaign_plan = CampaignPlan.load(plan_path)
            console.print(
                f"[green][OK][/green] Plan cargado: {campaign_plan.name} ({len(campaign_plan.days)} días)"
            )
        else:
            console.print(
                f"[yellow][!] Plan no encontrado: {plan_path}, usando {days} días por defecto[/yellow]"
            )
    if campaign_plan is None:
        from .models.campaign_plan import CampaignPlan, DayPlan, VisualCoherence
        from .models.campaign_style import get_preset

        plan_name = (title or "PROMO").strip() or "PROMO"
        themes = ["teaser", "main_offer", "last_chance", "extended", "closing"]
        campaign_plan = CampaignPlan(
            name=plan_name,
            brand_slug=brand,
            days=[DayPlan(day=i + 1, theme=themes[i % len(themes)]) for i in range(days)],
            visual_coherence=VisualCoherence(),
            style_guide=get_preset("black_friday"),
        )
        console.print(f"[dim]Plan por defecto: {days} días, título: {plan_name}[/dim]")

    output_dir = Path(output) if output else None

    pipeline = CampaignPipeline(generator_model="gpt-image-1.5")
    results = pipeline.run_reference_driven_campaign(
        product_ref=product_path,
        scene_ref=scene_path,
        font_ref=font_path,
        brand_dir=brand_dir,
        campaign_plan=campaign_plan,
        output_dir=output_dir,
        campaign_title=title,
    )

    console.print(
        f"\n[bold green]Campaña por referencias completada: {len(results)} imágenes[/bold green]"
    )


def version_callback(value: bool):
    """Callback para mostrar versión."""
    if value:
        from . import __version__

        console.print(f"CM Agents v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Muestra la versión y sale",
    ),
):
    """Sistema de agentes para automatizar diseños de redes sociales."""
    pass
