"""Modelo de datos para campañas publicitarias."""

import json
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class CampaignTheme(BaseModel):
    """Tema/configuración visual de la campaña."""

    style_override: str | None = Field(
        default=None, description="Estilo de diseño para esta campaña (override del brand)"
    )
    color_accent: str | None = Field(
        default=None,
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="Color de acento específico para la campaña",
    )
    mood: list[str] = Field(default_factory=list, description="Mood específico de la campaña")


class ContentItem(BaseModel):
    """Item individual del plan de contenido."""

    date: str = Field(..., description="Fecha de publicación (YYYY-MM-DD)")
    product: str = Field(..., description="Nombre del producto")
    size: Literal["feed", "story"] = Field(default="feed", description="Formato")
    text_copy: str | None = Field(default=None, description="Copy/texto para el post")
    status: Literal["pending", "generated", "published"] = Field(
        default="pending", description="Estado del contenido"
    )
    output_path: str | None = Field(default=None, description="Path a la imagen generada")


class CampaignDates(BaseModel):
    """Fechas de la campaña."""

    start: str = Field(..., description="Fecha de inicio (YYYY-MM-DD)")
    end: str = Field(..., description="Fecha de fin (YYYY-MM-DD)")


class Campaign(BaseModel):
    """Configuración completa de una campaña publicitaria."""

    name: str = Field(..., description="Nombre de la campaña")
    description: str = Field(default="", description="Descripción de la campaña")
    dates: CampaignDates = Field(..., description="Fechas de inicio y fin")
    theme: CampaignTheme = Field(
        default_factory=CampaignTheme, description="Tema visual de la campaña"
    )
    products: list[str] = Field(default_factory=list, description="Lista de productos incluidos")
    content_plan: list[ContentItem] = Field(default_factory=list, description="Plan de contenido")
    hashtags_extra: list[str] = Field(
        default_factory=list, description="Hashtags adicionales para la campaña"
    )

    @classmethod
    def load(cls, campaign_dir: Path) -> "Campaign":
        """Carga una campaña desde su directorio."""
        campaign_file = campaign_dir / "campaign.json"
        if not campaign_file.exists():
            raise FileNotFoundError(f"No se encontró campaign.json en {campaign_dir}")

        with open(campaign_file, encoding="utf-8") as f:
            data = json.load(f)

        return cls(**data)

    def save(self, campaign_dir: Path) -> None:
        """Guarda la campaña en su directorio."""
        campaign_dir.mkdir(parents=True, exist_ok=True)
        campaign_file = campaign_dir / "campaign.json"

        with open(campaign_file, "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f, indent=2, ensure_ascii=False)

    def get_pending_items(self) -> list[ContentItem]:
        """Retorna los items pendientes de generar."""
        return [item for item in self.content_plan if item.status == "pending"]

    def get_generated_items(self) -> list[ContentItem]:
        """Retorna los items ya generados."""
        return [item for item in self.content_plan if item.status == "generated"]

    def get_progress(self) -> tuple[int, int]:
        """Retorna (completados, total) para mostrar progreso."""
        total = len(self.content_plan)
        completed = len([i for i in self.content_plan if i.status != "pending"])
        return completed, total

    def is_active(self) -> bool:
        """Verifica si la campaña está activa (entre fechas)."""
        today = date.today().isoformat()
        return self.dates.start <= today <= self.dates.end

    def update_item_status(
        self, product: str, item_date: str, status: str, output_path: str | None = None
    ) -> bool:
        """Actualiza el estado de un item del plan."""
        for item in self.content_plan:
            if item.product == product and item.date == item_date:
                item.status = status  # type: ignore
                if output_path:
                    item.output_path = output_path
                return True
        return False
