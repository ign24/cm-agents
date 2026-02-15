"""Image generation routes."""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException

from ...models.product import Product
from ...pipeline import GenerationPipeline
from ..config import settings
from ..schemas import GenerateRequest, GenerateResponse, GenerationResult
from ..security import RateLimitDep, safe_slug, validate_slug
from ..websocket.manager import manager

logger = logging.getLogger(__name__)
router = APIRouter()


def get_plans_dir() -> Path:
    """Get plans directory path."""
    return Path(settings.OUTPUTS_DIR) / "plans"


async def execute_generation(
    plan_id: str,
    item_ids: list[str] | None = None,
    session_id: str | None = None,
):
    """
    Execute image generation for approved plan items using GenerationPipeline.

    This is the BUILD mode execution - validates plan is ready before starting.

    Sends progress updates via WebSocket if session_id is provided.
    """
    try:
        from ..services.plan_manager import plan_manager

        # Load plan using PlanManager
        plan = plan_manager.load_plan(plan_id)

        # Validate one more time before building
        validation = plan_manager.validate_plan_for_build(plan)
        if not validation["valid"]:
            error_msg = f"Plan not ready for BUILD: {', '.join(validation['errors'])}"
            logger.error(error_msg)
            if session_id:
                await manager.send_error(session_id, error_msg)
            return

        # Notify BUILD mode started
        if session_id:
            await manager.send_to_session(
                session_id,
                {
                    "type": "build_started",
                    "data": {
                        "plan_id": plan_id,
                        "ready_items": len(validation["ready_items"]),
                        "message": f"BUILD mode iniciado - Generando {len(validation['ready_items'])} items...",
                    },
                },
            )

        # Get items to generate
        items_to_generate = []
        for item in plan.items:
            if item.status != "approved":
                continue
            if item_ids and item.id not in item_ids:
                continue
            items_to_generate.append(item)

        if not items_to_generate:
            if session_id:
                await manager.send_error(session_id, "No approved items to generate")
            return

        # Validate plan slugs (defense in depth: plan comes from our API but could be edited on disk)
        if not validate_slug(plan.brand):
            error_msg = f"Invalid brand slug in plan: '{plan.brand}'"
            logger.error(error_msg)
            if session_id:
                await manager.send_error(session_id, error_msg)
            return

        # Load brand
        brand_dir = Path(settings.BRANDS_DIR) / plan.brand
        if not brand_dir.exists():
            error_msg = f"Brand directory not found: {brand_dir}"
            logger.error(error_msg)
            if session_id:
                await manager.send_error(session_id, error_msg)
            return

        # Determine campaign directory if exists
        campaign_dir = None
        if plan.campaign:
            campaign_dir = brand_dir / "campaigns" / plan.campaign
            if not campaign_dir.exists():
                campaign_dir = None  # Campaign doesn't exist, use default output

        # Initialize pipeline
        pipeline = GenerationPipeline(
            generator_model="gpt-image-1.5",
            design_style=None,  # Will auto-detect from brand/product
        )

        # Generate each item
        for i, item in enumerate(items_to_generate):
            item_id = item.id

            # Send progress: processing
            if session_id:
                variants_msg = (
                    f" ({item.variants_count} variants)" if item.variants_count > 1 else ""
                )
                await manager.send_progress(
                    session_id,
                    plan_id,
                    item_id,
                    status="processing",
                    progress=int((i / len(items_to_generate)) * 100),
                    message=f"Generating {item.product} ({item.size}){variants_msg}...",
                )

            try:
                # Validate product slug (defense in depth)
                if not validate_slug(item.product):
                    logger.warning(
                        f"Invalid product slug in plan item {item_id}: '{item.product}', skipping"
                    )
                    plan.mark_failed(item_id, f"Invalid product slug: {item.product}")
                    if session_id:
                        await manager.send_progress(
                            session_id,
                            plan_id,
                            item_id,
                            status="failed",
                            progress=int(((i + 1) / len(items_to_generate)) * 100),
                            message=f"Invalid product slug: {item.product}",
                        )
                    continue

                # Load product (standard structure: products/{marca}/{producto}/)
                product_dir = Path("products") / plan.brand / item.product
                if not product_dir.exists():
                    raise FileNotFoundError(
                        f"Product not found: products/{plan.brand}/{item.product}/\n"
                        f"Expected structure: products/{{marca}}/{{producto}}/product.json"
                    )

                product = Product.load(product_dir)

                # Get reference image path
                # Priority: 1) reference_local_paths, 2) brand references, 3) product photos
                reference_path = None
                product_ref_path = None

                # Try to use local paths from Pinterest MCP (NEW - most reliable)
                if item.reference_local_paths:
                    # Use first local path from Pinterest download
                    local_path = Path(item.reference_local_paths[0])
                    if local_path.exists():
                        reference_path = local_path
                        logger.info(f"Using Pinterest reference (local_path): {reference_path}")
                    else:
                        logger.warning(f"Local path not found: {local_path}")

                # Fallback: Try to find by URLs (old behavior)
                if not reference_path and item.reference_urls:
                    # Pinterest MCP downloads images to references/ directory
                    # Try to find downloaded files by checking recent files
                    refs_dir = Path("references")
                    if refs_dir.exists():
                        # Get most recent image files (Pinterest MCP downloads them)
                        ref_files = sorted(
                            list(refs_dir.glob("*.jpg"))
                            + list(refs_dir.glob("*.png"))
                            + list(refs_dir.glob("*.webp")),
                            key=lambda p: p.stat().st_mtime,
                            reverse=True,
                        )
                        # Use most recent file (likely from Pinterest search)
                        if ref_files:
                            reference_path = ref_files[0]
                            logger.info(
                                f"Using Pinterest reference (most recent): {reference_path}"
                            )
                        else:
                            logger.warning(
                                "Pinterest URLs provided but no images found in references/"
                            )

                # Fallback: use default reference from brand references or product photos
                if not reference_path:
                    # Try brand references directory
                    refs_dir = brand_dir / "references"
                    if refs_dir.exists():
                        ref_files = (
                            list(refs_dir.glob("*.jpg"))
                            + list(refs_dir.glob("*.png"))
                            + list(refs_dir.glob("*.webp"))
                        )
                        if ref_files:
                            reference_path = ref_files[0]
                            logger.info(f"Using brand reference: {reference_path}")

                # If still no reference, use product photo
                if not reference_path:
                    try:
                        reference_path = product.get_main_photo(product_dir)
                        logger.info(f"Using product photo as reference: {reference_path}")
                    except ValueError:
                        error_msg = f"No reference image found for {item.product}. Please add a reference image to {brand_dir / 'references'} or product photos."
                        logger.error(error_msg)
                        if session_id:
                            await manager.send_progress(
                                session_id,
                                plan_id,
                                item_id,
                                status="failed",
                                progress=int(((i + 1) / len(items_to_generate)) * 100),
                                message=error_msg,
                            )
                        plan.mark_failed(item_id, error_msg)
                        continue

                # Try to get product reference (dual mode) - use product photo if available
                try:
                    product_ref_path = product.get_main_photo(product_dir)
                    logger.info(f"Using product photo for dual mode: {product_ref_path}")
                except ValueError:
                    product_ref_path = None  # Single mode (only style reference)

                # Determine target size
                target_size = [item.size]  # Convert to list for pipeline

                # Get number of variants for this item
                num_variants = item.variants_count

                # Update status to generating
                for plan_item in plan.items:
                    if plan_item.id == item_id:
                        plan_item.status = "generating"
                        break

                # Run pipeline with variants
                results = pipeline.run(
                    reference_path=reference_path,
                    brand_dir=brand_dir,
                    product_dir=product_dir,
                    target_sizes=target_size,
                    include_text=True,
                    product_ref_path=product_ref_path,
                    campaign_dir=campaign_dir,
                    num_variants=num_variants,
                    price_override=item.price_override,
                )

                if results:
                    # Add all variants to the item
                    from ...models.plan import VariantResult

                    for variant_idx, result in enumerate(results, 1):
                        variant = VariantResult(
                            variant_number=variant_idx,
                            output_path=str(result.image_path),
                            cost_usd=result.cost_usd,
                            status="generated",
                            variation_type=f"variant_{variant_idx}",
                        )
                        plan.add_variant(item_id, variant)

                    # Update progress
                    successful_variants = len(
                        [v for v in plan.items if v.id == item_id][0].get_successful_variants()
                    )
                    total_variants = num_variants

                    if session_id:
                        await manager.send_progress(
                            session_id,
                            plan_id,
                            item_id,
                            status="completed"
                            if successful_variants == total_variants
                            else "partially_generated",
                            progress=int(((i + 1) / len(items_to_generate)) * 100),
                            message=f"Generated {successful_variants}/{total_variants} variants for {item.product}",
                        )
                else:
                    raise ValueError("Pipeline returned no results")

            except Exception as e:
                logger.error(f"Generation failed for {item_id}: {e}", exc_info=True)
                error_msg = str(e)
                plan.mark_failed(item_id, error_msg)
                if session_id:
                    await manager.send_progress(
                        session_id,
                        plan_id,
                        item_id,
                        status="failed",
                        progress=int(((i + 1) / len(items_to_generate)) * 100),
                        message=error_msg,
                    )

        # Save updated plan using PlanManager
        plan_manager.save_plan(plan)

        # Notify BUILD mode completion
        if session_id:
            completed, total = plan.get_progress()
            await manager.send_to_session(
                session_id,
                {
                    "type": "build_completed",
                    "data": {
                        "plan_id": plan_id,
                        "completed": completed,
                        "total": total,
                        "message": f"BUILD mode completado: {completed}/{total} imágenes generadas",
                    },
                },
            )

    except FileNotFoundError as e:
        error_msg = f"Plan not found: {e}"
        logger.error(error_msg)
        if session_id:
            await manager.send_error(session_id, error_msg)
    except Exception as e:
        logger.error(f"Generation execution failed: {e}", exc_info=True)
        if session_id:
            await manager.send_error(session_id, str(e))


@router.post("/generate", response_model=GenerateResponse)
async def generate_images(
    request: GenerateRequest,
    background_tasks: BackgroundTasks,
    _: RateLimitDep,
):
    """
    Start image generation for approved plan items.

    Generation runs in background. Use WebSocket for progress updates.
    """
    plan_id = safe_slug(request.plan_id)
    plan_file = get_plans_dir() / f"{plan_id}.json"

    if not plan_file.exists():
        raise HTTPException(status_code=404, detail=f"Plan '{request.plan_id}' not found")

    try:
        with open(plan_file, encoding="utf-8") as f:
            plan = json.load(f)

        # Check for approved items
        approved_items = [
            item
            for item in plan["items"]
            if item["status"] == "approved"
            and (not request.item_ids or item["id"] in request.item_ids)
        ]

        if not approved_items:
            raise HTTPException(
                status_code=400,
                detail="No approved items to generate. Approve the plan first.",
            )

        # Start generation in background
        background_tasks.add_task(
            execute_generation,
            request.plan_id,
            request.item_ids,
            None,  # No session_id for REST API
        )

        # Return immediate response
        return GenerateResponse(
            plan_id=request.plan_id,
            results=[
                GenerationResult(
                    item_id=item["id"],
                    success=True,
                    output_path=None,  # Will be filled after generation
                    cost_usd=0.0,
                )
                for item in approved_items
            ],
            total_cost=len(approved_items) * 0.15,  # Placeholder cost
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/generate/{plan_id}/status")
async def get_generation_status(plan_id: str, _: RateLimitDep):
    """Get generation status for a plan."""
    plan_id = safe_slug(plan_id)
    plan_file = get_plans_dir() / f"{plan_id}.json"

    if not plan_file.exists():
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")

    try:
        with open(plan_file, encoding="utf-8") as f:
            plan = json.load(f)

        items_status = {
            "draft": 0,
            "approved": 0,
            "generated": 0,
        }

        for item in plan["items"]:
            status = item.get("status", "draft")
            if status in items_status:
                items_status[status] += 1

        return {
            "plan_id": plan_id,
            "total_items": len(plan["items"]),
            "status": items_status,
            "is_complete": items_status["generated"] == len(plan["items"]),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
