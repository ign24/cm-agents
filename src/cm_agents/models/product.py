"""Modelo de datos para productos."""

import json
from pathlib import Path

from pydantic import BaseModel, Field


class Product(BaseModel):
    """Configuración de un producto."""

    name: str = Field(..., description="Nombre del producto")
    price: str = Field(..., description="Precio formateado (ej: '$8.99')")
    description: str = Field(default="", description="Descripción corta del producto")
    visual_description: str = Field(
        default="",
        description="Descripción visual detallada para generación de imágenes",
    )
    photos: list[str] = Field(
        default_factory=lambda: ["photos/product.png"],
        description="Rutas a las fotos del producto",
    )
    category: str = Field(default="general", description="Categoría del producto")
    tags: list[str] = Field(default_factory=list, description="Tags del producto")

    @classmethod
    def load(cls, product_dir: Path) -> "Product":
        """Carga un producto desde su directorio."""
        product_file = product_dir / "product.json"
        if not product_file.exists():
            raise FileNotFoundError(f"No se encontró product.json en {product_dir}")

        with open(product_file, encoding="utf-8") as f:
            data = json.load(f)

        return cls(**data)

    def save(self, product_dir: Path) -> None:
        """Guarda el producto en su directorio."""
        product_dir.mkdir(parents=True, exist_ok=True)
        product_file = product_dir / "product.json"

        with open(product_file, "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f, indent=2, ensure_ascii=False)

    def get_photo_paths(self, product_dir: Path) -> list[Path]:
        """Obtiene los paths completos a las fotos del producto."""
        return [product_dir / photo for photo in self.photos]

    def get_main_photo(self, product_dir: Path) -> Path:
        """Obtiene el path a la foto principal."""
        if not self.photos:
            raise ValueError(f"El producto {self.name} no tiene fotos")
        return product_dir / self.photos[0]

    def has_visual_description(self) -> bool:
        """Verifica si el producto tiene descripción visual."""
        return bool(self.visual_description.strip())
