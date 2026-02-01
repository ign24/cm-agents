"""Plan Manager - Handles plan approval and transition to build mode."""

import logging
from pathlib import Path
from typing import Any

from ...models.brand import Brand
from ...models.plan import ContentPlan
from ...models.product import Product
from ..config import settings

logger = logging.getLogger(__name__)


class PlanValidationError(Exception):
    """Raised when plan validation fails."""

    pass


class PlanManager:
    """
    Manages plan approval and validation before transitioning to build mode.

    Modes:
    - PLAN: Planning phase - StrategistAgent creates plans
    - BUILD: Build phase - GenerationPipeline executes approved plans
    """

    def __init__(self):
        self.plans_dir = Path(settings.OUTPUTS_DIR) / "plans"

    def get_plan_path(self, plan_id: str) -> Path:
        """Get path to plan file."""
        return self.plans_dir / f"{plan_id}.json"

    def load_plan(self, plan_id: str) -> ContentPlan:
        """Load a plan from disk."""
        plan_file = self.get_plan_path(plan_id)
        if not plan_file.exists():
            raise FileNotFoundError(f"Plan '{plan_id}' not found")
        return ContentPlan.load(plan_file)

    def save_plan(self, plan: ContentPlan) -> None:
        """Save a plan to disk."""
        self.plans_dir.mkdir(parents=True, exist_ok=True)
        plan_file = self.get_plan_path(plan.id)
        plan.save(plan_file)
        logger.info(f"Plan saved: {plan.id}")

    def validate_plan_for_build(self, plan: ContentPlan) -> dict[str, Any]:
        """
        Validate that a plan is ready for build mode.

        Returns:
            dict with validation results:
            - valid: bool
            - errors: list[str]
            - warnings: list[str]
            - ready_items: list[ContentPlanItem]
        """
        errors: list[str] = []
        warnings: list[str] = []
        ready_items = []

        # Check if plan has items
        if not plan.items:
            errors.append("Plan has no items to generate")

        # Check brand exists
        brand_dir = Path(settings.BRANDS_DIR) / plan.brand
        if not brand_dir.exists():
            errors.append(f"Brand directory not found: {plan.brand}")
        else:
            try:
                Brand.load(brand_dir)
            except Exception as e:
                errors.append(f"Failed to load brand: {e}")

        # Validate each item
        for item in plan.items:
            if item.status != "approved":
                continue

            item_errors = []
            item_warnings = []

            # Check product exists (standard structure: products/{marca}/{producto}/)
            product_dir = Path("products") / plan.brand / item.product
            if not product_dir.exists():
                item_errors.append(
                    f"Product not found: products/{plan.brand}/{item.product}/\n"
                    f"Expected: products/{{marca}}/{{producto}}/product.json + photos/"
                )
                continue

            try:
                product = Product.load(product_dir)
            except Exception as e:
                item_errors.append(f"Failed to load product: {e}")
                continue

            # Check for reference images
            has_reference = False

            # Check brand references
            refs_dir = brand_dir / "references"
            if refs_dir.exists():
                ref_files = (
                    list(refs_dir.glob("*.jpg"))
                    + list(refs_dir.glob("*.png"))
                    + list(refs_dir.glob("*.webp"))
                )
                if ref_files:
                    has_reference = True

            # Check product photos
            if not has_reference:
                try:
                    product.get_main_photo(product_dir)
                    has_reference = True
                except ValueError:
                    pass

            # Check reference URLs (if provided, should be downloaded)
            if item.reference_urls and not has_reference:
                item_warnings.append(
                    "Reference URLs provided but not downloaded. Will use default reference if available."
                )

            if not has_reference:
                item_errors.append(
                    f"No reference image found. Add images to {brand_dir / 'references'} or product photos."
                )

            if item_errors:
                errors.extend([f"Item {item.id} ({item.product}): {e}" for e in item_errors])
            if item_warnings:
                warnings.extend([f"Item {item.id} ({item.product}): {w}" for w in item_warnings])

            if not item_errors:
                ready_items.append(item)

        # Summary
        valid = len(errors) == 0 and len(ready_items) > 0

        return {
            "valid": valid,
            "errors": errors,
            "warnings": warnings,
            "ready_items": ready_items,
            "total_items": len(plan.items),
            "approved_items": len([i for i in plan.items if i.status == "approved"]),
        }

    def approve_plan(
        self, plan_id: str, item_ids: list[str] | None = None, auto_approve: bool = False
    ) -> tuple[ContentPlan, dict[str, Any]]:
        """
        Approve a plan and validate it for build mode.

        Args:
            plan_id: Plan ID to approve
            item_ids: Specific item IDs to approve (None = all items)
            auto_approve: If True, skip validation (for auto-approval flows)

        Returns:
            Tuple of (approved_plan, validation_result)

        Raises:
            PlanValidationError: If validation fails and auto_approve=False
        """
        # Load plan
        plan = self.load_plan(plan_id)

        # Approve items
        plan.approve(item_ids=item_ids)

        # Validate if not auto-approving
        validation = self.validate_plan_for_build(plan)

        if not auto_approve and not validation["valid"]:
            # Save plan anyway (with approved status)
            self.save_plan(plan)
            raise PlanValidationError(f"Plan validation failed: {', '.join(validation['errors'])}")

        # Save approved plan
        self.save_plan(plan)

        logger.info(
            f"Plan {plan_id} approved: {validation['approved_items']} items, "
            f"{len(validation['ready_items'])} ready for build"
        )

        return plan, validation

    def get_plan_status(self, plan_id: str) -> dict[str, Any]:
        """Get current status of a plan."""
        try:
            plan = self.load_plan(plan_id)
        except FileNotFoundError:
            return {"exists": False}

        validation = self.validate_plan_for_build(plan)

        completed, total = plan.get_progress()

        return {
            "exists": True,
            "plan_id": plan.id,
            "brand": plan.brand,
            "campaign": plan.campaign,
            "status": {
                "draft": len([i for i in plan.items if i.status == "draft"]),
                "approved": len([i for i in plan.items if i.status == "approved"]),
                "generated": len([i for i in plan.items if i.status == "generated"]),
                "failed": len([i for i in plan.items if i.status == "failed"]),
            },
            "progress": {"completed": completed, "total": total},
            "validation": validation,
            "ready_for_build": validation["valid"],
        }


# Global instance
plan_manager = PlanManager()
