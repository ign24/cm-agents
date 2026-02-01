"""Modelo de datos para marcas."""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

# =============================================================================
# Identidad de Marca
# =============================================================================


class BrandIdentity(BaseModel):
    """Identidad y voz de la marca."""

    tagline: str | None = Field(default=None, description="Eslogan de la marca")
    voice: list[str] = Field(
        default_factory=lambda: ["profesional"],
        description="Tono de voz de la marca (ej: familiar, cercano, formal)",
    )
    values: list[str] = Field(
        default_factory=list,
        description="Valores de la marca (ej: calidad, tradición, innovación)",
    )


# =============================================================================
# Assets de Marca
# =============================================================================


class BrandAssets(BaseModel):
    """Assets gráficos de la marca."""

    logo: str | None = Field(default=None, description="Logo principal")
    logo_white: str | None = Field(default=None, description="Logo en blanco (para fondos oscuros)")
    logo_dark: str | None = Field(default=None, description="Logo oscuro (para fondos claros)")
    icon: str | None = Field(default=None, description="Icono/favicon de la marca")
    watermark: str | None = Field(default=None, description="Marca de agua")


# =============================================================================
# Colores
# =============================================================================


class ColorPalette(BaseModel):
    """Paleta de colores de la marca."""

    primary: str = Field(..., pattern=r"^#[0-9A-Fa-f]{6}$", description="Color principal")
    secondary: str = Field(..., pattern=r"^#[0-9A-Fa-f]{6}$", description="Color secundario")
    background: str = Field(
        default="#FFFFFF", pattern=r"^#[0-9A-Fa-f]{6}$", description="Color de fondo"
    )
    text: str = Field(default="#212121", pattern=r"^#[0-9A-Fa-f]{6}$", description="Color de texto")
    accent: str | None = Field(
        default=None, pattern=r"^#[0-9A-Fa-f]{6}$", description="Color de acento"
    )
    gradient: list[str] | None = Field(default=None, description="Colores para gradientes de marca")


# =============================================================================
# Tipografía
# =============================================================================


class FontStyle(BaseModel):
    """Configuración de una fuente específica."""

    font: str = Field(..., description="Path a la fuente")
    style: str = Field(default="normal", description="Descripción del estilo (ej: bold, impactful)")


class FontConfig(BaseModel):
    """Configuración de fuentes de la marca (formato simple legacy)."""

    heading: str = Field(default="fonts/heading.ttf", description="Fuente para títulos")
    body: str = Field(default="fonts/body.ttf", description="Fuente para cuerpo")
    price: str = Field(default="fonts/heading.ttf", description="Fuente para precios")


class TypographyConfig(BaseModel):
    """Configuración de tipografía extendida."""

    heading: FontStyle = Field(
        default_factory=lambda: FontStyle(font="fonts/heading.ttf", style="bold, impactful")
    )
    body: FontStyle = Field(
        default_factory=lambda: FontStyle(font="fonts/body.ttf", style="readable, friendly")
    )
    price: FontStyle = Field(
        default_factory=lambda: FontStyle(
            font="fonts/heading.ttf", style="bold, attention-grabbing"
        )
    )


class StyleConfig(BaseModel):
    """Configuración de estilo visual de la marca."""

    mood: list[str] = Field(
        default_factory=lambda: ["profesional", "moderno"],
        description="Palabras que describen el mood de la marca",
    )
    photography_style: str = Field(
        default="professional product photography",
        description="Estilo de fotografía preferido",
    )
    preferred_backgrounds: list[str] = Field(
        default_factory=lambda: ["clean white background", "neutral surface"],
        description="Fondos preferidos para productos",
    )
    preferred_design_styles: list[str] = Field(
        default_factory=list,
        description="Estilos de diseño preferidos (ej: lifestyle_warm, minimal_clean)",
    )
    avoid: list[str] = Field(
        default_factory=list,
        description="Estilos o elementos a evitar (ej: cold colors, clinical look)",
    )


class PriceBadgeConfig(BaseModel):
    """Configuración del badge de precio."""

    bg_color: str = Field(default="#D32F2F", description="Color de fondo del badge")
    text_color: str = Field(default="#FFFFFF", description="Color del texto del precio")
    position: Literal["top-left", "top-right", "bottom-left", "bottom-right"] = Field(
        default="bottom-left", description="Posición del badge"
    )
    padding: int = Field(default=20, description="Padding en pixels")


class TitleConfig(BaseModel):
    """Configuración del título del producto."""

    color: str = Field(default="#FFFFFF", description="Color del título")
    shadow: bool = Field(default=True, description="Aplicar sombra al texto")
    position: Literal["top-left", "top-center", "top-right", "bottom-center"] = Field(
        default="top-center", description="Posición del título"
    )


class LogoOverlayConfig(BaseModel):
    """Configuración del logo en imágenes generadas."""

    position: Literal["top-left", "top-right", "bottom-left", "bottom-right"] = Field(
        default="top-right", description="Posición del logo"
    )
    size: Literal["small", "medium", "large"] = Field(
        default="small", description="Tamaño del logo"
    )
    opacity: float = Field(default=1.0, ge=0.0, le=1.0, description="Opacidad del logo")


class TextOverlayConfig(BaseModel):
    """Configuración de overlays de texto."""

    price_badge: PriceBadgeConfig = Field(default_factory=PriceBadgeConfig)
    title: TitleConfig = Field(default_factory=TitleConfig)
    logo: LogoOverlayConfig = Field(default_factory=LogoOverlayConfig)


# =============================================================================
# Social Media
# =============================================================================


class SocialMediaConfig(BaseModel):
    """Configuración de redes sociales."""

    instagram: str | None = Field(default=None, description="Handle de Instagram")
    facebook: str | None = Field(default=None, description="Página de Facebook")
    tiktok: str | None = Field(default=None, description="Handle de TikTok")
    platforms: list[str] = Field(
        default_factory=lambda: ["instagram"],
        description="Plataformas activas",
    )


# =============================================================================
# Modelo Principal de Marca
# =============================================================================


class Brand(BaseModel):
    """Configuración completa de una marca."""

    name: str = Field(..., description="Nombre de la marca")
    handle: str | None = Field(default=None, description="Handle de Instagram (@marca) - legacy")
    industry: str | None = Field(
        default=None, description="Industria/rubro (ej: food_restaurant, pharmacy, wine_spirits)"
    )

    # Nuevo: Identidad de marca
    identity: BrandIdentity = Field(
        default_factory=BrandIdentity, description="Identidad y voz de la marca"
    )

    # Nuevo: Assets centralizados
    assets: BrandAssets = Field(
        default_factory=BrandAssets, description="Assets gráficos de la marca"
    )

    # Legacy: logo directo (retrocompatibilidad)
    logo: str | None = Field(default=None, description="Path al logo (legacy - usar assets.logo)")

    palette: ColorPalette = Field(..., description="Paleta de colores")

    # Soporta ambos formatos: fonts (legacy) y typography (nuevo)
    fonts: FontConfig = Field(
        default_factory=FontConfig, description="Configuración de fuentes (legacy)"
    )
    typography: TypographyConfig | None = Field(
        default=None, description="Configuración de tipografía extendida"
    )

    style: StyleConfig = Field(default_factory=StyleConfig, description="Estilo visual")
    text_overlay: TextOverlayConfig = Field(
        default_factory=TextOverlayConfig, description="Configuración de texto"
    )

    # Nuevo: Social media config
    social_media: SocialMediaConfig | None = Field(
        default=None, description="Configuración de redes sociales"
    )

    hashtags: dict[str, list[str] | dict[str, list[str]]] = Field(
        default_factory=dict, description="Hashtags por categoria"
    )

    @classmethod
    def load(cls, brand_dir: Path) -> "Brand":
        """Carga una marca desde su directorio."""
        brand_file = brand_dir / "brand.json"
        if not brand_file.exists():
            raise FileNotFoundError(f"No se encontró brand.json en {brand_dir}")

        with open(brand_file, encoding="utf-8") as f:
            data = json.load(f)

        return cls(**data)

    def save(self, brand_dir: Path) -> None:
        """Guarda la marca en su directorio."""
        brand_dir.mkdir(parents=True, exist_ok=True)
        brand_file = brand_dir / "brand.json"

        with open(brand_file, "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f, indent=2, ensure_ascii=False)

    def get_font_path(self, brand_dir: Path, font_type: str = "heading") -> Path:
        """Obtiene el path completo a una fuente."""
        font_rel = getattr(self.fonts, font_type, self.fonts.heading)
        return brand_dir / font_rel

    def get_mood_string(self) -> str:
        """Retorna el mood como string para prompts."""
        return ", ".join(self.style.mood)

    def get_backgrounds_string(self) -> str:
        """Retorna los fondos preferidos como string para prompts."""
        return " or ".join(self.style.preferred_backgrounds)

    def get_logo_path(self, brand_dir: Path) -> Path | None:
        """Obtiene el path completo al logo si existe.

        Busca en orden:
        1. assets.logo (nuevo formato)
        2. logo (legacy formato)
        """
        # Primero intentar nuevo formato
        if self.assets and self.assets.logo:
            logo_path = brand_dir / self.assets.logo
            if logo_path.exists():
                return logo_path

        # Fallback a legacy
        if self.logo:
            logo_path = brand_dir / self.logo
            if logo_path.exists():
                return logo_path

        return None

    def get_asset_path(self, brand_dir: Path, asset_name: str) -> Path | None:
        """Obtiene el path a un asset específico.

        Args:
            brand_dir: Directorio de la marca
            asset_name: Nombre del asset (logo, logo_white, logo_dark, icon, watermark)

        Returns:
            Path al asset o None si no existe
        """
        if not self.assets:
            return None

        asset_rel = getattr(self.assets, asset_name, None)
        if not asset_rel:
            return None

        asset_path = brand_dir / asset_rel
        return asset_path if asset_path.exists() else None

    def get_preferred_styles(self) -> list[str]:
        """Retorna los estilos de diseño preferidos de la marca."""
        return self.style.preferred_design_styles

    def get_avoid_styles(self) -> list[str]:
        """Retorna los estilos/elementos a evitar."""
        return self.style.avoid

    def get_industry_category(self) -> str | None:
        """Retorna la categoría de industria para guidelines de diseño."""
        if not self.industry:
            return None

        # Mapear industrias a categorías del knowledge base
        industry_map = {
            "food_restaurant": "food",
            "food_delivery": "food",
            "pharmacy": "pharmacy",
            "drugstore": "pharmacy",
            "wine": "wine_spirits",
            "wine_spirits": "wine_spirits",
            "liquor": "wine_spirits",
            "medical": "medical",
            "healthcare": "medical",
        }
        return industry_map.get(self.industry, self.industry)
