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
        """Carga un producto desde su directorio.

        Si no existe `product.json`, intenta modo fallback leyendo fotos en `photos/`.
        """
        product_file = product_dir / "product.json"
        if product_file.exists():
            with open(product_file, encoding="utf-8") as f:
                data = json.load(f)
            return cls(**data)

        # Fallback sin product.json: construir producto mínimo desde carpeta/fotos
        photos_dir = product_dir / "photos"
        photo_paths: list[str] = []
        if photos_dir.exists():
            for pattern in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
                for p in sorted(photos_dir.glob(pattern)):
                    photo_paths.append(str(Path("photos") / p.name))

        if not photo_paths:
            raise FileNotFoundError(
                f"No se encontró product.json ni fotos en {photos_dir} para {product_dir}"
            )

        slug_name = product_dir.name.replace("-", " ").replace("_", " ").strip()
        inferred_name = " ".join(w.capitalize() for w in slug_name.split()) or product_dir.name

        return cls(
            name=inferred_name,
            price="N/A",
            description="",
            visual_description="",
            photos=photo_paths,
            category="general",
            tags=[],
        )

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
