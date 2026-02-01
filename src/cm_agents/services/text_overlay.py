"""Servicio para agregar texto a imágenes usando Pillow."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from rich.console import Console

from ..models.brand import Brand
from ..models.product import Product

console = Console()

# Tamaños de fuente relativos al tamaño de imagen
FONT_SIZE_RATIOS = {
    "1080x1080": {"title": 48, "price": 72},
    "1080x1350": {"title": 48, "price": 72},
    "1080x1920": {"title": 64, "price": 96},
}

# Posiciones de texto (en pixels desde la esquina correspondiente)
POSITIONS = {
    "top-left": {"x": 30, "y": 30},
    "top-center": {"x": 540, "y": 30},
    "top-right": {"x": 1050, "y": 30},
    "bottom-left": {"x": 30, "y": 1320},
    "bottom-center": {"x": 540, "y": 1850},
    "bottom-right": {"x": 1050, "y": 1320},
}


def get_font_sizes(image_size: str) -> dict[str, int]:
    """Obiene tamaños de fuente basados en el tamaño de imagen."""
    return FONT_SIZE_RATIOS.get(image_size, FONT_SIZE_RATIOS["1080x1080"])


def get_position(position: str, image_width: int, image_height: int) -> dict[str, int]:
    """Calcula la posición de texto basada en el tamaño de imagen."""
    base_pos = POSITIONS.get(position, POSITIONS["top-center"])

    # Ajustar para anchos diferentes
    if position in ["top-center", "bottom-center"]:
        base_pos["x"] = image_width // 2
    elif position in ["top-right", "bottom-right"]:
        base_pos["x"] = image_width - 50

    # Ajustar para alturas diferentes
    if position in ["bottom-left", "bottom-right"]:
        base_pos["y"] = image_height - 120
    elif position in ["bottom-center"]:
        base_pos["y"] = image_height - 100

    return base_pos


class TextOverlayService:
    """Servicio para agregar texto a imágenes."""

    def __init__(self, brand_dir: Path, brand: Brand):
        """Inicializa el servicio.

        Args:
            brand_dir: Path al directorio de la marca
            brand: Configuración de la marca
        """
        self.brand_dir = brand_dir
        self.brand = brand

    def load_font(self, font_type: str, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
        """Carga una fuente de la marca.

        Args:
            font_type: "heading", "body", o "price"
            size: Tamaño de la fuente
            bold: Si es bold

        Returns:
            ImageFont cargado o fuente del sistema si no existe

        Raises:
            FileNotFoundError: Si no existe la fuente
        """
        font_path = self.brand.get_font_path(self.brand_dir, font_type)

        if font_path.exists():
            try:
                return ImageFont.truetype(str(font_path), size)
            except Exception as e:
                console.print(f"[yellow][!] No se pudo cargar {font_path}: {e}[/yellow]")
                console.print("[yellow]   Usando fuente del sistema...[/yellow]")
                return self._get_system_font(size, bold)
        else:
            console.print(f"[yellow][!] Fuente no encontrada: {font_path}[/yellow]")
            console.print("[yellow]   Usando fuente del sistema...[/yellow]")
            return self._get_system_font(size, bold)

    def _get_system_font(self, size: int, bold: bool) -> ImageFont.FreeTypeFont:
        """Obiene una fuente del sistema."""
        font_names = ["Arial", "Helvetica", "DejaVu Sans"]
        for name in font_names:
            try:
                return ImageFont.truetype(name, size, index=1 if bold else 0)
            except OSError:
                continue
        return ImageFont.load_default()

    def draw_price_badge(
        self, draw: ImageDraw.ImageDraw, price: str, font_size: int, img_size: tuple[int, int]
    ) -> tuple[int, int, int, int]:
        """Dibuja el badge de precio en la imagen.

        Args:
            draw: ImageDraw sobre la imagen
            price: Texto del precio
            font_size: Tamano de fuente
            img_size: Tamano de la imagen (width, height)

        Returns:
            (x1, y1, x2, y2) bounding box del texto
        """
        config = self.brand.text_overlay.price_badge
        font = self.load_font("price", font_size, bold=True)

        # Calcular tamano del texto
        text_bbox = draw.textbbox((0, 0), price, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]

        # Calcular posicion del badge
        padding = config.padding
        badge_width = text_width + (padding * 2)
        badge_height = text_height + (padding * 2)

        img_width, img_height = img_size
        pos = get_position(config.position, img_width, img_height)

        # Dibujar rectangulo del badge
        badge_x = pos["x"] - padding
        badge_y = pos["y"] - padding

        draw.rounded_rectangle(
            [badge_x, badge_y, badge_x + badge_width, badge_y + badge_height],
            radius=15,
            fill=config.bg_color,
        )

        # Dibujar texto del precio
        text_x = badge_x + padding
        text_y = badge_y + (badge_height - text_height) // 2

        draw.text(
            (text_x, text_y),
            price,
            font=font,
            fill=config.text_color,
        )

        return badge_x, badge_y, badge_x + badge_width, badge_y + badge_height

    def draw_title(
        self, draw: ImageDraw.ImageDraw, title: str, font_size: int, img_size: tuple[int, int]
    ) -> None:
        """Dibuja el titulo del producto en la imagen.

        Args:
            draw: ImageDraw sobre la imagen
            title: Texto del titulo
            font_size: Tamano de fuente
            img_size: Tamano de la imagen (width, height)
        """
        config = self.brand.text_overlay.title
        font = self.load_font("heading", font_size, bold=True)

        # Calcular tamano del texto
        text_bbox = draw.textbbox((0, 0), title, font=font)
        text_width = text_bbox[2] - text_bbox[0]

        # Calcular posicion centrada
        img_width, img_height = img_size
        pos = get_position(config.position, img_width, img_height)

        text_x = pos["x"] - (text_width // 2)

        # Dibujar sombra si está activado
        if config.shadow:
            draw.text(
                (text_x + 3, pos["y"] + 3),
                title,
                font=font,
                fill="#000000",
            )

        # Dibujar texto principal
        draw.text((text_x, pos["y"]), title, font=font, fill=config.color)

    def apply_overlay(
        self,
        image_path: Path,
        product: Product,
        output_path: Path | None = None,
    ) -> Path:
        """Aplica overlays de texto a una imagen.

        Args:
            image_path: Path a la imagen generada
            product: Información del producto
            output_path: Path de salida (opcional, default: sobreescribe la original)

        Returns:
            Path a la imagen con overlay aplicado

        Raises:
            FileNotFoundError: Si no existe la imagen
        """
        if not image_path.exists():
            raise FileNotFoundError(f"Imagen no encontrada: {image_path}")

        console.print(
            f"\n[blue][Texto] Text Overlay:[/blue] Agregando texto a {image_path.name}..."
        )

        # Cargar imagen
        img = Image.open(image_path)
        if img.mode != "RGBA":
            img = img.convert("RGBA")

        draw = ImageDraw.Draw(img)

        # Obtener tamaños de fuente
        img_size = f"{img.width}x{img.height}"
        font_sizes = get_font_sizes(img_size)

        # Dibujar título
        if product.name:
            self.draw_title(draw, product.name, font_sizes["title"], (img.width, img.height))

        # Dibujar precio
        if product.price:
            self.draw_price_badge(draw, product.price, font_sizes["price"], (img.width, img.height))

        # Guardar
        if output_path is None:
            output_path = image_path

        img.save(output_path, "PNG", quality=95)

        console.print(f"[green][OK][/green] Texto agregado: {output_path.name}")

        return output_path

    def apply_overlays_batch(
        self,
        image_paths: list[Path],
        product: Product,
    ) -> list[Path]:
        """Aplica overlays a múltiples imágenes.

        Args:
            image_paths: Lista de paths a imágenes
            product: Información del producto

        Returns:
            Lista de paths a imágenes con overlay
        """
        console.print(f"\n[bold]Aplicando texto a {len(image_paths)} imágenes...[/bold]")

        results = []
        for i, path in enumerate(image_paths, 1):
            console.print(f"\n[dim]Imagen {i}/{len(image_paths)}[/dim]")
            results.append(self.apply_overlay(path, product))

        return results
