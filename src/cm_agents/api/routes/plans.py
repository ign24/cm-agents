"""Content plan management routes."""

import json
import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ...agents.strategist import StrategistAgent
from ...models.brand import Brand
from ..config import settings
from ..schemas import (
    ContentIntentResponse,
    ContentPlanItemResponse,
    ContentPlanResponse,
    PlanApproveRequest,
    PlanCreateRequest,
    VariantResultResponse,
)
from ..security import RateLimitDep, safe_slug

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize strategist agent
strategist = StrategistAgent(knowledge_dir=Path(settings.KNOWLEDGE_DIR))


def get_plans_dir() -> Path:
    """Get plans directory path."""
    plans_dir = Path(settings.OUTPUTS_DIR) / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    return plans_dir


@router.post("/plans", response_model=ContentPlanResponse)
async def create_plan(request: PlanCreateRequest, _: RateLimitDep):
    """
    Create a content plan from natural language prompt.

    This uses the StrategistAgent to interpret the request and generate a plan.
    """
    # Validate brand slug
    brand_slug = safe_slug(request.brand)
    brand_path = Path(settings.BRANDS_DIR) / brand_slug
    if not brand_path.exists():
        raise HTTPException(status_code=404, detail=f"Brand '{request.brand}' not found")

    try:
        brand = Brand.load(brand_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load brand: {e}")

    # Create plan with StrategistAgent
    try:
        plan = strategist.create_plan(
            prompt=request.prompt,
            brand=brand,
            brand_dir=brand_path,
            campaign=request.campaign,
        )
    except Exception as e:
        logger.error(f"Failed to create plan: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create plan: {e}")

    # Save plan to file
    plan_file = get_plans_dir() / f"{plan.id}.json"
    plan_data = {
        "id": plan.id,
        "brand": plan.brand,
        "campaign": plan.campaign,
        "intent": {
            "objective": plan.intent.objective,
            "product": plan.intent.product,
            "occasion": plan.intent.occasion,
            "tone": plan.intent.tone,
            "constraints": plan.intent.constraints,
        },
        "items": [
            {
                "id": item.id,
                "product": item.product,
                "size": item.size,
                "style": item.style,
                "copy_suggestion": item.copy_suggestion,
                "reference_query": item.reference_query,
                "reference_urls": item.reference_urls,
                "variants_count": item.variants_count,
                "status": item.status,
                "variants": [
                    {
                        "variant_number": v.variant_number,
                        "output_path": v.output_path,
                        "cost_usd": v.cost_usd,
                        "status": v.status,
                        "error": v.error,
                        "variation_type": v.variation_type,
                    }
                    for v in item.variants
                ],
                "output_path": item.output_path,
            }
            for item in plan.items
        ],
        "created_at": plan.created_at.isoformat(),
        "approved_at": plan.approved_at.isoformat() if plan.approved_at else None,
        "estimated_cost": plan.estimated_cost,
    }

    with open(plan_file, "w", encoding="utf-8") as f:
        json.dump(plan_data, f, indent=2, ensure_ascii=False)

    return ContentPlanResponse(
        id=plan.id,
        brand=plan.brand,
        intent=ContentIntentResponse(
            objective=plan.intent.objective,
            product=plan.intent.product,
            occasion=plan.intent.occasion,
            tone=plan.intent.tone,
            constraints=plan.intent.constraints,
        ),
        items=[
            ContentPlanItemResponse(
                id=item.id,
                product=item.product,
                size=item.size,
                style=item.style,
                copy_suggestion=item.copy_suggestion,
                reference_query=item.reference_query,
                reference_urls=item.reference_urls,
                variants_count=item.variants_count,
                status=item.status,
                variants=[
                    VariantResultResponse(
                        variant_number=v.variant_number,
                        output_path=v.output_path,
                        cost_usd=v.cost_usd,
                        status=v.status,
                        error=v.error,
                        variation_type=v.variation_type,
                    )
                    for v in item.variants
                ],
                output_path=item.output_path,
            )
            for item in plan.items
        ],
        created_at=plan.created_at,
        approved_at=plan.approved_at,
        estimated_cost=plan.estimated_cost,
    )


@router.get("/plans", response_model=list[ContentPlanResponse])
async def list_plans(brand: str | None = None, _: RateLimitDep = None):
    """List all content plans, optionally filtered by brand."""
    # Load from files
    plans_dir = get_plans_dir()
    result = []

    for plan_file in plans_dir.glob("*.json"):
        try:
            with open(plan_file, encoding="utf-8") as f:
                plan = json.load(f)

            if brand and plan.get("brand") != brand:
                continue

            result.append(
                ContentPlanResponse(
                    id=plan["id"],
                    brand=plan["brand"],
                    intent=ContentIntentResponse(**plan["intent"]),
                    items=[ContentPlanItemResponse(**item) for item in plan["items"]],
                    created_at=datetime.fromisoformat(plan["created_at"]),
                    approved_at=(
                        datetime.fromisoformat(plan["approved_at"])
                        if plan.get("approved_at")
                        else None
                    ),
                    estimated_cost=plan["estimated_cost"],
                )
            )
        except Exception as e:
            logger.warning(f"Failed to load plan {plan_file}: {e}")
            continue

    return result


@router.get("/plans/{plan_id}", response_model=ContentPlanResponse)
async def get_plan(plan_id: str, _: RateLimitDep):
    """Get a specific content plan."""
    plan_id = safe_slug(plan_id)
    plan_file = get_plans_dir() / f"{plan_id}.json"

    if not plan_file.exists():
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")

    try:
        with open(plan_file, encoding="utf-8") as f:
            plan = json.load(f)

        return ContentPlanResponse(
            id=plan["id"],
            brand=plan["brand"],
            intent=ContentIntentResponse(**plan["intent"]),
            items=[ContentPlanItemResponse(**item) for item in plan["items"]],
            created_at=datetime.fromisoformat(plan["created_at"]),
            approved_at=(
                datetime.fromisoformat(plan["approved_at"]) if plan.get("approved_at") else None
            ),
            estimated_cost=plan["estimated_cost"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/plans/{plan_id}/approve", response_model=ContentPlanResponse)
async def approve_plan(plan_id: str, request: PlanApproveRequest, _: RateLimitDep):
    """
    Approve a content plan for execution (PLAN mode → BUILD mode transition).

    This endpoint validates the plan before approval and returns validation results.
    Optionally specify specific item IDs to approve.
    """
    plan_id = safe_slug(plan_id)

    try:
        from ..services.plan_manager import PlanValidationError, plan_manager

        # Approve and validate plan
        plan, validation = plan_manager.approve_plan(
            plan_id=plan_id,
            item_ids=request.item_ids if request.item_ids else None,
            auto_approve=False,  # REST API always validates
        )

        # Convert to response
        return ContentPlanResponse(
            id=plan.id,
            brand=plan.brand,
            intent=ContentIntentResponse(
                objective=plan.intent.objective,
                product=plan.intent.product,
                occasion=plan.intent.occasion,
                tone=plan.intent.tone,
                constraints=plan.intent.constraints,
            ),
            items=[
                ContentPlanItemResponse(
                    id=item.id,
                    product=item.product,
                    size=item.size,
                    style=item.style,
                    copy_suggestion=item.copy_suggestion,
                    reference_query=item.reference_query,
                    reference_urls=item.reference_urls,
                    status=item.status,
                )
                for item in plan.items
            ],
            created_at=plan.created_at,
            approved_at=plan.approved_at,
            estimated_cost=plan.estimated_cost,
        )

    except PlanValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Plan approval failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/plans/{plan_id}/status")
async def get_plan_status(plan_id: str, _: RateLimitDep):
    """
    Get detailed status of a plan including validation results.

    Returns:
        - Plan status (draft, approved, generated counts)
        - Progress (completed/total)
        - Validation results (ready for BUILD mode?)
    """
    plan_id = safe_slug(plan_id)

    try:
        from ..services.plan_manager import plan_manager

        status = plan_manager.get_plan_status(plan_id)

        if not status["exists"]:
            raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")

        return status

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get plan status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/plans/{plan_id}")
async def delete_plan(plan_id: str):
    """Delete a content plan."""
    plan_file = get_plans_dir() / f"{plan_id}.json"

    if not plan_file.exists():
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")

    plan_file.unlink()
    return {"status": "deleted", "plan_id": plan_id}
