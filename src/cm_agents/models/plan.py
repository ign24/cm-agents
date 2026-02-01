"""Content plan models for the planning system."""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class ContentIntent(BaseModel):
    """
    What the user wants to achieve.

    Extracted from natural language by the StrategistAgent.
    """

    objective: Literal["promocionar", "informar", "engagement", "branding", "lanzamiento"] = (
        "promocionar"
    )
    product: str | None = None
    occasion: str | None = None  # "dia del padre", "black friday", etc.
    tone: list[str] = Field(default_factory=lambda: ["profesional"])
    constraints: list[str] = Field(default_factory=list)  # "sin texto", "vertical", etc.


class VariantResult(BaseModel):
    """Result of a single variant generation."""

    variant_number: int = Field(..., description="Variant number (1-based)")
    output_path: str = Field(..., description="Path to generated image")
    cost_usd: float = Field(default=0.0, description="Cost for this variant")
    status: Literal["generated", "failed"] = "generated"
    error: str | None = None
    variation_type: str | None = Field(
        default=None, description="Type of variation (composition, lighting, angle, etc.)"
    )


class ContentPlanItem(BaseModel):
    """
    Single item in a content plan.

    Represents one image specification that can generate multiple variants.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    product: str
    size: Literal["feed", "story"] = "feed"
    style: str = "minimal_clean"
    copy_suggestion: str = ""
    reference_query: str = ""  # Query for Pinterest search
    reference_urls: list[str] = Field(default_factory=list)  # Found references
    reference_local_paths: list[str] = Field(
        default_factory=list, description="Local paths to downloaded reference images"
    )
    variants_count: int = Field(
        default=1, ge=1, le=10, description="Number of variants to generate (1-10)"
    )
    price_override: str | None = Field(
        default=None, description="Custom price for this promo (overrides product.json price)"
    )
    status: Literal[
        "draft", "approved", "generating", "partially_generated", "generated", "failed"
    ] = "draft"
    variants: list[VariantResult] = Field(default_factory=list, description="Generated variants")
    output_path: str | None = Field(
        default=None, description="Legacy: path to first variant (for backward compatibility)"
    )
    error: str | None = None

    def get_successful_variants(self) -> list[VariantResult]:
        """Get all successfully generated variants."""
        return [v for v in self.variants if v.status == "generated"]

    def update_status(self) -> None:
        """Update item status based on variants."""
        if not self.variants:
            if self.error:
                self.status = "failed"
            return

        successful = len(self.get_successful_variants())

        if successful == 0:
            self.status = "failed"
        elif successful == self.variants_count:
            self.status = "generated"
        elif successful > 0:
            self.status = "partially_generated"
        else:
            self.status = "generating"

        # Update legacy output_path for backward compatibility
        if successful > 0:
            self.output_path = self.get_successful_variants()[0].output_path


class ContentPlan(BaseModel):
    """
    Full content plan.

    Created by the StrategistAgent, approved by user, executed by pipeline.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    brand: str
    campaign: str | None = None
    intent: ContentIntent = Field(default_factory=ContentIntent)
    items: list[ContentPlanItem] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    approved_at: datetime | None = None
    estimated_cost: float = 0.0

    def add_item(
        self,
        product: str,
        size: Literal["feed", "story"] = "feed",
        style: str = "minimal_clean",
        copy_suggestion: str = "",
        reference_query: str = "",
    ) -> ContentPlanItem:
        """Add an item to the plan."""
        item = ContentPlanItem(
            product=product,
            size=size,
            style=style,
            copy_suggestion=copy_suggestion,
            reference_query=reference_query,
        )
        self.items.append(item)
        self._update_cost()
        return item

    def approve(self, item_ids: list[str] | None = None) -> None:
        """Approve items in the plan."""
        for item in self.items:
            if item_ids is None or item.id in item_ids:
                item.status = "approved"
        self.approved_at = datetime.now()

    def get_approved_items(self) -> list[ContentPlanItem]:
        """Get all approved items."""
        return [item for item in self.items if item.status == "approved"]

    def get_pending_items(self) -> list[ContentPlanItem]:
        """Get items pending approval."""
        return [item for item in self.items if item.status == "draft"]

    def get_generated_items(self) -> list[ContentPlanItem]:
        """Get generated items."""
        return [item for item in self.items if item.status == "generated"]

    def mark_generated(self, item_id: str, output_path: str) -> None:
        """Mark an item as generated (legacy method for single variant)."""
        for item in self.items:
            if item.id == item_id:
                if not item.variants:
                    # Create variant from legacy output_path
                    item.variants.append(
                        VariantResult(variant_number=1, output_path=output_path, status="generated")
                    )
                item.update_status()
                break

    def add_variant(self, item_id: str, variant: VariantResult) -> None:
        """Add a variant result to an item."""
        for item in self.items:
            if item.id == item_id:
                item.variants.append(variant)
                item.update_status()
                break

    def mark_failed(self, item_id: str, error: str) -> None:
        """Mark an item as failed."""
        for item in self.items:
            if item.id == item_id:
                item.status = "failed"
                item.error = error
                break

    def _update_cost(self) -> None:
        """Update estimated cost based on items and variants."""
        # Approximate cost per image
        cost_per_image = 0.15
        total_variants = sum(item.variants_count for item in self.items)
        self.estimated_cost = total_variants * cost_per_image

    def get_progress(self) -> tuple[int, int]:
        """Get progress as (completed variants, total variants)."""
        total_variants = sum(item.variants_count for item in self.items)
        completed_variants = sum(len(item.get_successful_variants()) for item in self.items)
        return completed_variants, total_variants

    def save(self, path: Path) -> None:
        """Save plan to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = self.model_dump()
        # Convert datetime to ISO format
        data["created_at"] = self.created_at.isoformat()
        if self.approved_at:
            data["approved_at"] = self.approved_at.isoformat()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: Path) -> "ContentPlan":
        """Load plan from JSON file."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        # Parse datetime strings
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        if data.get("approved_at"):
            data["approved_at"] = datetime.fromisoformat(data["approved_at"])
        return cls(**data)

    def to_summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            f"📋 Plan: {self.id}",
            f"   Marca: {self.brand}",
            f"   Objetivo: {self.intent.objective}",
        ]
        if self.intent.occasion:
            lines.append(f"   Ocasión: {self.intent.occasion}")
        lines.append(f"   Items: {len(self.items)}")
        lines.append(f"   Costo estimado: ${self.estimated_cost:.2f}")

        completed, total = self.get_progress()
        if total > 0:
            lines.append(f"   Progreso: {completed}/{total}")

        return "\n".join(lines)
